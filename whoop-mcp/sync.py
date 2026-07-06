# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
"""Sync de l'historique WHOOP vers un entrepôt SQLite local (~/.whoop-mcp/whoop.db).

Idempotent : relançable à volonté (upsert par id).
  - Premier run (table vide)  -> historique complet depuis FROM_DATE.
  - Runs suivants             -> fenêtre glissante (WINDOW_DAYS) pour capter les re-scorings.

Lance : uv run --python 3.11 --script ~/.whoop-mcp/sync.py
Réutilise la connexion OAuth créée par auth.py (credentials.json).
"""
import json, os, sqlite3, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx

DIR = Path.home() / ".whoop-mcp"
CRED = DIR / "credentials.json"
DB = DIR / "whoop.db"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API = "https://api.prod.whoop.com/developer"
FROM_DATE = "2020-01-01T00:00:00.000Z"
WINDOW_DAYS = 60

# --------------------------------------------------------------------------- #
#  OAuth (réutilise credentials.json)
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
    if t.get("refresh_token"):
        c["refresh_token"] = t["refresh_token"]
    _save(c)
    return c["access_token"]

def _get(path, params=None, _retry=True):
    r = httpx.get(f"{API}{path}", headers={"Authorization": f"Bearer {_token()}"}, params=params, timeout=30)
    if r.status_code == 401 and _retry:
        _token(force=True)
        return _get(path, params, False)
    if r.status_code == 429:  # rate limit : on souffle et on retente
        time.sleep(2)
        return _get(path, params, _retry)
    r.raise_for_status()
    return r.json()

def _pull(path, start):
    p = {"limit": 25, "start": start}
    while True:
        d = _get(path, p)
        for rec in d.get("records", []):
            yield rec
        nt = d.get("next_token")
        if not nt:
            break
        p["nextToken"] = nt

# --------------------------------------------------------------------------- #
#  Schéma + upserts
# --------------------------------------------------------------------------- #
def _schema(cx):
    cx.executescript("""
    CREATE TABLE IF NOT EXISTS cycles(
      id TEXT PRIMARY KEY, start TEXT, "end" TEXT, timezone_offset TEXT,
      score_state TEXT, strain REAL, kilojoule REAL,
      average_heart_rate REAL, max_heart_rate REAL, updated_at TEXT, raw TEXT);
    CREATE TABLE IF NOT EXISTS recovery(
      cycle_id TEXT PRIMARY KEY, sleep_id TEXT, created_at TEXT, updated_at TEXT,
      score_state TEXT, recovery_score REAL, resting_heart_rate REAL,
      hrv_rmssd_milli REAL, spo2_percentage REAL, skin_temp_celsius REAL, raw TEXT);
    CREATE TABLE IF NOT EXISTS sleep(
      id TEXT PRIMARY KEY, start TEXT, "end" TEXT, timezone_offset TEXT, nap INTEGER,
      score_state TEXT, sleep_performance_percentage REAL, sleep_efficiency_percentage REAL,
      sleep_consistency_percentage REAL, respiratory_rate REAL,
      total_in_bed_time_milli INTEGER, total_awake_time_milli INTEGER,
      total_light_sleep_time_milli INTEGER, total_slow_wave_sleep_time_milli INTEGER,
      total_rem_sleep_time_milli INTEGER, disturbance_count INTEGER,
      updated_at TEXT, raw TEXT);
    CREATE TABLE IF NOT EXISTS workouts(
      id TEXT PRIMARY KEY, start TEXT, "end" TEXT, timezone_offset TEXT, sport_name TEXT,
      score_state TEXT, strain REAL, average_heart_rate REAL, max_heart_rate REAL,
      kilojoule REAL, distance_meter REAL, updated_at TEXT, raw TEXT);
    """)

def up_cycle(cx, r):
    s = r.get("score") or {}
    cx.execute("INSERT OR REPLACE INTO cycles VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
        str(r.get("id")), r.get("start"), r.get("end"), r.get("timezone_offset"),
        r.get("score_state"), s.get("strain"), s.get("kilojoule"),
        s.get("average_heart_rate"), s.get("max_heart_rate"), r.get("updated_at"), json.dumps(r)))

def up_recovery(cx, r):
    s = r.get("score") or {}
    cx.execute("INSERT OR REPLACE INTO recovery VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
        str(r.get("cycle_id")), str(r.get("sleep_id")), r.get("created_at"), r.get("updated_at"),
        r.get("score_state"), s.get("recovery_score"), s.get("resting_heart_rate"),
        s.get("hrv_rmssd_milli"), s.get("spo2_percentage"), s.get("skin_temp_celsius"), json.dumps(r)))

def up_sleep(cx, r):
    s = r.get("score") or {}
    st = s.get("stage_summary") or {}
    cx.execute("INSERT OR REPLACE INTO sleep VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        str(r.get("id")), r.get("start"), r.get("end"), r.get("timezone_offset"),
        1 if r.get("nap") else 0, r.get("score_state"),
        s.get("sleep_performance_percentage"), s.get("sleep_efficiency_percentage"),
        s.get("sleep_consistency_percentage"), s.get("respiratory_rate"),
        st.get("total_in_bed_time_milli"), st.get("total_awake_time_milli"),
        st.get("total_light_sleep_time_milli"), st.get("total_slow_wave_sleep_time_milli"),
        st.get("total_rem_sleep_time_milli"), st.get("disturbance_count"),
        r.get("updated_at"), json.dumps(r)))

def up_workout(cx, r):
    s = r.get("score") or {}
    cx.execute("INSERT OR REPLACE INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        str(r.get("id")), r.get("start"), r.get("end"), r.get("timezone_offset"),
        r.get("sport_name"), r.get("score_state"), s.get("strain"),
        s.get("average_heart_rate"), s.get("max_heart_rate"), s.get("kilojoule"),
        s.get("distance_meter"), r.get("updated_at"), json.dumps(r)))

def _start_for(cx, table):
    if cx.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0:
        return FROM_DATE
    return (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

def main():
    DIR.mkdir(parents=True, exist_ok=True)
    if not CRED.exists():
        raise SystemExit("credentials.json introuvable. Lance d'abord auth.py.")
    cx = sqlite3.connect(DB)
    _schema(cx)
    jobs = [
        ("cycles",   "/v2/cycle",           up_cycle),
        ("recovery", "/v2/recovery",        up_recovery),
        ("sleep",    "/v2/activity/sleep",  up_sleep),
        ("workouts", "/v2/activity/workout", up_workout),
    ]
    for table, path, up in jobs:
        start = _start_for(cx, table)
        n = 0
        for rec in _pull(path, start):
            up(cx, rec)
            n += 1
        cx.commit()
        total = cx.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"{table:9s} : +{n} traités, {total} lignes au total (depuis {start[:10]})")
    cx.close()
    print("Sync terminé ->", DB)

if __name__ == "__main__":
    main()
