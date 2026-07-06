# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2.0", "httpx>=0.27"]
# ///
"""Serveur MCP WHOOP (API officielle v2, OAuth 2.0) pour Claude Code.

Deux familles d'outils :
  - lecture "live" (whoop_profile, whoop_recovery, whoop_sleep, ...) : appelle l'API à la demande ;
  - lecture "entrepôt" (whoop_tables, whoop_query) : interroge la base locale whoop.db
    remplie par sync.py, pour des tendances/corrélations sur tout l'historique sans noyer le contexte.
"""
import json, os, re, sqlite3, time
from pathlib import Path
import httpx
from mcp.server.fastmcp import FastMCP

DIR = Path.home() / ".whoop-mcp"
CRED = DIR / "credentials.json"
DB = DIR / "whoop.db"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API = "https://api.prod.whoop.com/developer"
mcp = FastMCP("whoop")

# --------------------------------------------------------------------------- #
#  OAuth + accès API live
# --------------------------------------------------------------------------- #
def _load():
    return json.loads(CRED.read_text())

def _save(c):
    CRED.write_text(json.dumps(c, indent=2))
    os.chmod(CRED, 0o600)

def _token(force=False):
    c = _load()
    if not force and c.get("access_token") and c.get("expires_at", 0) > time.time() + 60:
        return c["access_token"]
    r = httpx.post(TOKEN_URL, data={
        "grant_type": "refresh_token", "refresh_token": c["refresh_token"],
        "client_id": c["client_id"], "client_secret": c["client_secret"], "scope": "offline",
    }, timeout=30)
    r.raise_for_status()
    t = r.json()
    c["access_token"] = t["access_token"]
    c["expires_at"] = time.time() + int(t.get("expires_in", 3600))
    if t.get("refresh_token"):  # WHOOP fait tourner le refresh token, on garde le nouveau
        c["refresh_token"] = t["refresh_token"]
    _save(c)
    return c["access_token"]

def _get(path, params=None, _retry=True):
    r = httpx.get(f"{API}{path}", headers={"Authorization": f"Bearer {_token()}"}, params=params, timeout=30)
    if r.status_code == 401 and _retry:
        _token(force=True)
        return _get(path, params, False)
    r.raise_for_status()
    return r.json()

def _coll(path, start, end, limit):
    p = {"limit": 25}
    if start: p["start"] = start
    if end: p["end"] = end
    out = []
    while True:
        d = _get(path, p)
        out += d.get("records", [])
        nt = d.get("next_token")
        if not nt or len(out) >= limit:
            break
        p["nextToken"] = nt
    return out[:limit]

# --------------------------------------------------------------------------- #
#  Outils "live"
# --------------------------------------------------------------------------- #
@mcp.tool()
def whoop_profile() -> dict:
    """Profil WHOOP : prénom, nom, email, user id."""
    return _get("/v2/user/profile/basic")

@mcp.tool()
def whoop_body_measurement() -> dict:
    """Mensurations : taille (m), poids (kg), FC max (bpm)."""
    return _get("/v2/user/measurement/body")

@mcp.tool()
def whoop_recovery(start: str | None = None, end: str | None = None, max_records: int = 25) -> dict:
    """Recovery : score %, HRV (ms), FC de repos, SpO2, température de peau. start/end en ISO-8601 optionnels."""
    return {"records": _coll("/v2/recovery", start, end, max_records)}

@mcp.tool()
def whoop_sleep(start: str | None = None, end: str | None = None, max_records: int = 25) -> dict:
    """Sommeil : performance %, durée par stade, fréquence respiratoire, efficacité, consistance."""
    return {"records": _coll("/v2/activity/sleep", start, end, max_records)}

@mcp.tool()
def whoop_cycles(start: str | None = None, end: str | None = None, max_records: int = 25) -> dict:
    """Cycles physiologiques : strain du jour, FC moyenne/max, dépense (kJ)."""
    return {"records": _coll("/v2/cycle", start, end, max_records)}

@mcp.tool()
def whoop_workouts(start: str | None = None, end: str | None = None, max_records: int = 25) -> dict:
    """Séances : sport, strain, FC moyenne/max, zones de FC, distance."""
    return {"records": _coll("/v2/activity/workout", start, end, max_records)}

@mcp.tool()
def whoop_daily_summary() -> dict:
    """Snapshot du jour : dernier cycle (strain) + dernière recovery + dernier sommeil."""
    return {
        "latest_cycle": (_coll("/v2/cycle", None, None, 1) or [None])[0],
        "latest_recovery": (_coll("/v2/recovery", None, None, 1) or [None])[0],
        "latest_sleep": (_coll("/v2/activity/sleep", None, None, 1) or [None])[0],
    }

# --------------------------------------------------------------------------- #
#  Outils "entrepôt" (base locale whoop.db, remplie par sync.py)
# --------------------------------------------------------------------------- #
def _ro():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

@mcp.tool()
def whoop_tables() -> dict:
    """Schéma de l'entrepôt local whoop.db (tables + colonnes + nb de lignes).
    À consulter avant d'écrire une requête whoop_query."""
    if not DB.exists():
        return {"error": "whoop.db introuvable. Lance d'abord : uv run --python 3.11 --script ~/.whoop-mcp/sync.py"}
    cx = _ro()
    out = {}
    for (t,) in cx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        cols = [{"name": c[1], "type": c[2]} for c in cx.execute(f'PRAGMA table_info("{t}")')]
        n = cx.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        out[t] = {"rows": n, "columns": cols}
    cx.close()
    return out

_FORBIDDEN = {"insert", "update", "delete", "drop", "alter", "create",
              "attach", "detach", "pragma", "replace", "vacuum", "reindex", "trigger"}

@mcp.tool()
def whoop_query(sql: str, max_rows: int = 500) -> dict:
    """Exécute une requête SQL **lecture seule** (SELECT / WITH) sur l'entrepôt whoop.db.

    Permet de calculer n'importe quelle tendance ou corrélation sur des mois de données
    (ex. « corrélation strain de la veille vs recovery du lendemain », « HRV moyen par jour
    de la semaine », « performance de sommeil sur 90 jours »). Tables disponibles :
    cycles, recovery, sleep, workouts. Utilise whoop_tables pour voir les colonnes.
    """
    if not DB.exists():
        return {"error": "whoop.db introuvable. Lance d'abord : uv run --python 3.11 --script ~/.whoop-mcp/sync.py"}
    q = sql.strip().rstrip(";").strip()
    low = q.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return {"error": "Lecture seule : seules les requêtes SELECT / WITH sont autorisées."}
    if ";" in q:
        return {"error": "Une seule instruction autorisée (pas de ';')."}
    if set(re.findall(r"[a-z_]+", low)) & _FORBIDDEN:
        return {"error": "Mot-clé d'écriture détecté, requête refusée."}
    cx = _ro()  # connexion mode=ro : SQLite bloque toute écriture au niveau moteur
    cx.row_factory = sqlite3.Row
    try:
        rows = cx.execute(q).fetchmany(max(1, min(max_rows, 5000)))
        data = [dict(r) for r in rows]
    except Exception as e:
        return {"error": f"SQL: {e}"}
    finally:
        cx.close()
    return {"row_count": len(data), "rows": data}

if __name__ == "__main__":
    mcp.run()
