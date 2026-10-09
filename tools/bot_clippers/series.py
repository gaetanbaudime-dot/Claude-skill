"""Séries par compte Instagram (09/10, dashboard — Gaëtan : « je dois comprendre quel compte est en hausse ou en baisse de vues,
tout voir, le plus précis possible, pas de trucs pas précis »).

Contrat C1 de la spécification du dashboard : ce module est le SEUL à lire et écrire `DONNEES/series_comptes.json`
(`configurer({"lire_json", "ecrire_json", "FICHIER_SERIES"})`). Le scan des comptes (etats_comptes) y ajoute un relevé à chaque
passage qui a LU un compte ; Metricool y ajoute les siens (source « metricool ») ; le Dashboard les lit.

    {"v": 1,
     "comptes": {"<clé>": {"id": "<id Instagram ou ''>",
                           "releves": [{"t": iso, "source": "apify" | "metricool", "followers": int | None,
                                        "posts_total": int | None, "restreint": bool, "prive": bool,
                                        # facultatifs (09/10) : "reels_lus": bool, "couvre": iso | ""}],
                           "reels": {"<shortcode>": {"publie": iso, "type": "Video", "vues": [[iso, int], …],
                                                     # facultatif : "sources": ["apify", …]}}}},
     "alias": {"<ancienne clé>": "<nouvelle clé>"}}

Règles (jamais un faux 0) :
  - un relevé n'existe que pour un compte LU ; `followers: None` = illisible, jamais 0 par défaut ;
  - vues d'un Reel : `vues_post` — videoPlayCount si c'est un nombre, sinon videoViewCount, sinon absent (aucun point ajouté).
    La même règle partout (scan des comptes, cadence_reels) ;
  - Reels = vidéos non épinglées vues dans latestPosts, gardés 40 jours après publication, 20 points de vues au plus
    (6 au-delà de 15 jours), les points proches de 24 h / 48 h / 72 h / 7 j après la publication toujours gardés ;
  - un même Reel vu par deux sources sous deux codes (publié à 2 minutes près) n'est compté qu'une fois ;
  - `couvre` (facultatif) dit depuis quand le relevé voit TOUTES les publications du compte : "" = tout l'historique visible
    (moins de publications que latestPosts n'en montre), une date = la plus ancienne publication non épinglée vue (12 au plus),
    absent = les 48 h avant le relevé. `reels_publies` ne répond que si la période est entièrement couverte ;
  - un @ renommé (series.renommer, ou même id Instagram vu sous un autre @) : la série suit, l'ancienne clé devient un alias.

Calculs purs, testés : followers_a, delta_followers, vues_age_fixe, reels_publies, derniere_lecture. Les dates acceptent un
`datetime` (sans fuseau = UTC), une chaîne ISO, ou une `date` (= minuit à Paris).
Les écritures sont synchrones (lecture, modification, écriture sans `await` au milieu) : deux boucles asyncio ne peuvent pas
s'écraser. La lecture est gardée en cache tant que le fichier ne change pas (le Dashboard relit souvent)."""
import copy
import logging
import os
import re
import statistics
from datetime import date, datetime, time as dtime, timedelta, timezone

journal = logging.getLogger("series")

VERSION = 1
JOURS = 40                                   # relevés et Reels gardés 40 jours
POINTS_MAX = 20                              # points de vues par Reel
POINTS_MAX_ANCIENS = 6                       # au-delà de AGE_ANCIEN_J jours après la publication
AGE_ANCIEN_J = 15
MEME_REEL_S = 120                            # deux sources, deux codes, publiés à 2 minutes près = le même Reel
TOLERANCE_AGE_H = 18                         # vues à âge fixe : relevé à ±18 h de publie + âge, sinon le Reel est ignoré
PERIME_H = 60                                # un dernier relevé plus vieux que ça : pas d'écart de followers
OUVERT_H = 26                                # période « jusqu'à maintenant » : dernier relevé lisible de moins de 26 h
COUVERTURE_DEFAUT_H = 48                     # relevé sans `couvre` : il voit les 48 h qui le précèdent
CIBLES_H = (6, 12, 24, 36, 48, 60, 72, 96, 120, 168, 240, 336, 504, 720)
CIBLES_COURTES_H = (24, 48, 168)
_DEBUT_DES_TEMPS = datetime(2000, 1, 1, tzinfo=timezone.utc)

_deps = {}
_cache = {"d": None, "f": "", "sig": None}
_PARIS = None


def configurer(deps: dict):
    global _deps
    _deps = dict(deps or {})
    _cache["d"] = None


def actif() -> bool:
    return bool(_deps.get("FICHIER_SERIES") and callable(_deps.get("lire_json")) and callable(_deps.get("ecrire_json")))


# ------------------------------------------------------------------ outils
def _paris_tz():
    global _PARIS
    if _PARIS is None:
        try:
            from zoneinfo import ZoneInfo
            _PARIS = ZoneInfo("Europe/Paris")
        except Exception:                                                # noqa: BLE001
            _PARIS = timezone(timedelta(hours=2))
    return _PARIS


def _instant(x):
    """Un instant (datetime avec fuseau) depuis un datetime, une chaîne ISO ou une date (minuit à Paris) ; None si illisible."""
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if isinstance(x, date):
        return datetime.combine(x, dtime(0), tzinfo=_paris_tz())
    try:
        dt = datetime.fromisoformat(str(x).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _maintenant(x=None):
    return _instant(x) or datetime.now(timezone.utc)


def _entier(v):
    """Un nombre lu (int, float, chaîne de chiffres) → int ; tout le reste (None, booléen, texte, négatif) → None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v) if v == v and v >= 0 and v != float("inf") else None
    t = str(v).strip()
    return int(t) if t.isdigit() else None


def _cle(x) -> str:
    return str(x or "").strip().lstrip("@").lower()


_RE_CODE = re.compile(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def _code(x) -> str:
    """Le shortcode d'une publication : tel quel, ou tiré d'une URL instagram.com/p|reel/<code>/."""
    t = str(x or "").strip()
    m = _RE_CODE.search(t)
    return m.group(1) if m else (t if re.fullmatch(r"[A-Za-z0-9_-]+", t) else "")


def vues_post(post: dict):
    """La règle des vues, la même partout : videoPlayCount si c'est un nombre, sinon videoViewCount, sinon None (absent)."""
    for k in ("videoPlayCount", "videoViewCount"):
        v = _entier((post or {}).get(k)) if not isinstance((post or {}).get(k), str) else None
        if v is not None:
            return v
    return None


def code_post(post: dict) -> str:
    """Le shortcode d'une publication Apify (shortCode, sinon l'URL)."""
    return _code((post or {}).get("shortCode") or (post or {}).get("shortcode") or (post or {}).get("url") or "")


# ------------------------------------------------------------------ fichier
def _vide() -> dict:
    return {"v": VERSION, "comptes": {}, "alias": {}}


def _signature(f):
    try:
        st = os.stat(f)
        return (st.st_mtime_ns, st.st_size)
    except (OSError, TypeError, ValueError):
        return None


def _charger() -> dict:
    """Le contenu du fichier (en cache tant qu'il ne change pas). Sans configuration : une série vide."""
    if not actif():
        return _vide()
    f = _deps["FICHIER_SERIES"]
    sig = _signature(f)
    if _cache["d"] is not None and _cache["f"] == str(f) and sig is not None and _cache["sig"] == sig:
        return _cache["d"]
    d = _deps["lire_json"](f, None)
    if not isinstance(d, dict):
        d = _vide()
    d.setdefault("v", VERSION)
    if not isinstance(d.get("comptes"), dict):
        d["comptes"] = {}
    if not isinstance(d.get("alias"), dict):
        d["alias"] = {}
    _cache.update(d=d, f=str(f), sig=sig)
    return d


def _enregistrer(d: dict):
    try:
        _deps["ecrire_json"](_deps["FICHIER_SERIES"], d)
    finally:
        _cache["d"] = None                                              # relu au prochain appel (écrit ou pas)


def _resoudre(d: dict, cle: str) -> str:
    """La clé vivante d'un compte : suit les alias (@ renommés), 10 sauts au plus, sans boucle."""
    k, vus = _cle(cle), set()
    while k in d.get("alias", {}) and k not in d.get("comptes", {}) and k not in vus and len(vus) < 10:
        vus.add(k)
        k = _cle(d["alias"][k])
    return k


def _serie_brute(cle) -> dict:
    d = _charger()
    return d["comptes"].get(_resoudre(d, cle)) or {}


# ------------------------------------------------------------------ écriture
def _releve_propre(releve: dict, source=None, couvre=None):
    r = releve if isinstance(releve, dict) else {}
    t = _instant(r.get("t")) or datetime.now(timezone.utc)
    out = {"t": _iso(t), "source": str(source or r.get("source") or "apify").strip().lower(),
           "followers": _entier(r.get("followers")), "posts_total": _entier(r.get("posts_total")),
           "restreint": bool(r.get("restreint")), "prive": bool(r.get("prive"))}
    if "reels_lus" in r:
        out["reels_lus"] = bool(r.get("reels_lus"))
    c = couvre if couvre is not None else r.get("couvre")
    if c == "":
        out["couvre"] = ""
    elif c is not None and _instant(c) is not None:
        out["couvre"] = _iso(_instant(c))
    return out


def _amincir(points: list, publie, maxi: int) -> list:
    """Au plus `maxi` points : le premier, le dernier et le plus proche de chaque âge cible (24 h, 48 h…) sont gardés ; on retire
    d'abord le point le plus serré contre son voisin (là où les relevés sont les plus denses)."""
    pts = [p for p in points if isinstance(p, list) and len(p) == 2 and _instant(p[0]) is not None]
    if len(pts) <= maxi:
        return pts
    cibles = CIBLES_H if maxi >= 16 else CIBLES_COURTES_H
    while len(pts) > maxi:
        temps = [_instant(p[0]) for p in pts]
        gardes = {0, len(pts) - 1}
        for h in cibles:
            but = publie + timedelta(hours=h)
            gardes.add(min(range(len(pts)), key=lambda i: abs((temps[i] - but).total_seconds())))
        libres = [i for i in range(1, len(pts) - 1) if i not in gardes] or list(range(1, len(pts) - 1))
        if not libres:
            break
        i = min(libres, key=lambda j: ((temps[j] - temps[j - 1]).total_seconds(), j))
        del pts[i]
    return pts


def _maxi_points(publie, t) -> int:
    return POINTS_MAX_ANCIENS if (t - publie) > timedelta(days=AGE_ANCIEN_J) else POINTS_MAX


def _ajouter_reel(compte: dict, r: dict, t_iso: str, source: str):
    if not isinstance(r, dict):
        return
    code = _code(r.get("code"))
    publie = _instant(r.get("publie"))
    t = _instant(t_iso)
    if not code or publie is None or t is None or publie < t - timedelta(days=JOURS):
        return
    reels = compte.setdefault("reels", {})
    e = reels.get(code)
    if e is None:                                                       # le même Reel, vu par une autre source sous un autre code
        for x in reels.values():
            p = _instant(x.get("publie"))
            if p is not None and abs((p - publie).total_seconds()) <= MEME_REEL_S and source not in (x.get("sources") or []):
                e = x
                break
    if e is None:
        e = reels[code] = {"publie": _iso(publie), "type": str(r.get("type") or "Video"), "vues": []}
    srcs = e.setdefault("sources", [])
    if source not in srcs:
        srcs.append(source)
    v = _entier(r.get("vues")) if not isinstance(r.get("vues"), str) else None
    if v is None:
        return                                                          # vues absentes : aucun point (jamais 0)
    points = [p for p in (e.get("vues") or []) if isinstance(p, list) and len(p) == 2 and p[0] != t_iso]
    points.append([t_iso, v])
    points.sort(key=lambda p: str(p[0]))
    e["vues"] = _amincir(points, _instant(e.get("publie")) or publie, _maxi_points(publie, t))


def _fusionner(d: dict, ancienne: str, nouvelle: str) -> bool:
    """La série de `ancienne` rejoint celle de `nouvelle` (relevés et Reels réunis), `ancienne` devient un alias."""
    a, n = _cle(ancienne), _cle(nouvelle)
    if not a or not n or a == n:
        return False
    src = d["comptes"].pop(a, None)
    if src is not None:
        dst = d["comptes"].setdefault(n, {"id": "", "releves": [], "reels": {}})
        if not dst.get("id") and src.get("id"):
            dst["id"] = src["id"]
        cles = {(r.get("t"), r.get("source")) for r in dst.get("releves", [])}
        dst["releves"] = sorted(dst.get("releves", []) + [r for r in src.get("releves", []) if (r.get("t"), r.get("source")) not in cles],
                                key=lambda r: str(r.get("t") or ""))
        reels = dst.setdefault("reels", {})
        for code, x in (src.get("reels") or {}).items():
            if code not in reels:
                reels[code] = x
                continue
            y = reels[code]
            vus = {p[0] for p in y.get("vues", [])}
            pts = sorted(y.get("vues", []) + [p for p in x.get("vues", []) if p[0] not in vus], key=lambda p: str(p[0]))
            publie = _instant(y.get("publie")) or _instant(x.get("publie"))
            y["vues"] = _amincir(pts, publie, _maxi_points(publie, _instant(pts[-1][0]))) if pts and publie else pts
            y["sources"] = sorted(set(y.get("sources") or []) | set(x.get("sources") or []))
    d["alias"][a] = n
    for k, v in list(d["alias"].items()):
        if _cle(v) == a:
            d["alias"][k] = n
    d["alias"].pop(n, None)                                             # la nouvelle clé est vivante
    return src is not None


def _ajouter(d: dict, cle, releve, reels=(), ig_id="", source=None, couvre=None) -> bool:
    k = _cle(cle)
    if not k:
        return False
    rel = _releve_propre(releve, source, couvre)
    src = rel["source"]
    ig = str(ig_id or "").strip()
    cible = _resoudre(d, k)
    if cible != k:
        id_cible = str((d["comptes"].get(cible) or {}).get("id") or "")
        if src == "apify" and ig and id_cible and ig != id_cible:       # l'ancien @ est maintenant le compte de quelqu'un d'autre
            d["alias"].pop(k, None)
            cible = k
    if src == "apify" and ig:                                            # même id Instagram sous un autre @ : renommé, la série suit
        for autre, s in list(d["comptes"].items()):
            if autre != cible and str(s.get("id") or "") == ig and any(r.get("source") == "apify" for r in s.get("releves", [])):
                _fusionner(d, autre, cible)
                journal.info("Séries : un compte renommé sur Instagram, sa série suit le nouvel identifiant")
    compte = d["comptes"].setdefault(cible, {"id": "", "releves": [], "reels": {}})
    if ig and (src == "apify" or not compte.get("id")):
        compte["id"] = ig
    rels = [r for r in compte.get("releves", []) if not (r.get("t") == rel["t"] and r.get("source") == src)]
    rels.append(rel)
    rels.sort(key=lambda r: str(r.get("t") or ""))
    compte["releves"] = rels
    for r in reels or []:
        _ajouter_reel(compte, r, rel["t"], src)
    return True


def _purger(d: dict, jours: int = JOURS, maintenant=None) -> int:
    limite = _maintenant(maintenant) - timedelta(days=jours)
    n = 0
    for cle, s in list(d["comptes"].items()):
        avant = len(s.get("releves", [])) + len(s.get("reels", {}))
        s["releves"] = [r for r in s.get("releves", []) if (_instant(r.get("t")) or limite - timedelta(1)) >= limite]
        reels = {}
        for code, x in (s.get("reels") or {}).items():
            p = _instant(x.get("publie"))
            if p is None or p < limite:
                continue
            pts = x.get("vues") or []
            if pts and len(pts) > POINTS_MAX_ANCIENS:
                maxi = _maxi_points(p, _maintenant(maintenant))
                x["vues"] = _amincir(pts, p, maxi)
            reels[code] = x
        s["reels"] = reels
        n += avant - len(s["releves"]) - len(reels)
        if not s["releves"] and not s["reels"]:
            del d["comptes"][cle]
    for a in list(d["alias"]):
        if _resoudre(d, a) not in d["comptes"]:
            del d["alias"][a]
    return n


def ajouter_releve(cle, releve: dict, reels=(), ig_id="", source=None, couvre=None) -> bool:
    """Un relevé d'un compte LU (jamais pour un non-lu) et les Reels vus à ce relevé ([{code, publie, type, vues}]).
    `source` (facultatif) remplace releve["source"] ; `couvre` (facultatif) : voir l'en-tête du module."""
    if not actif():
        return False
    d = _charger()
    ok = _ajouter(d, cle, releve, reels, ig_id, source, couvre)
    if ok:
        _purger(d)
        _enregistrer(d)
    return ok


def ajouter_releves(entrees: list) -> int:
    """Plusieurs relevés en UNE lecture et UNE écriture (le scan : ~150 comptes par passage). entrees = [{cle, releve, reels,
    ig_id, source?, couvre?}]. Renvoie le nombre de relevés enregistrés."""
    if not actif() or not entrees:
        return 0
    d = _charger()
    n = 0
    for e in entrees:
        try:
            n += int(_ajouter(d, e.get("cle"), e.get("releve") or {}, e.get("reels") or [], e.get("ig_id") or "",
                              e.get("source"), e.get("couvre")))
        except Exception as erreur:                                     # noqa: BLE001 — un relevé abîmé n'empêche pas les autres
            journal.warning("Séries : un relevé ignoré (%s)", type(erreur).__name__)
    if n:
        _purger(d)
        _enregistrer(d)
    return n


def renommer(ancienne, nouvelle) -> bool:
    """@ renommé (onboarding.renommer_compte) : la série suit la nouvelle clé, l'ancienne devient un alias."""
    if not actif():
        return False
    a, n = _cle(ancienne), _cle(nouvelle)
    if not a or not n or a == n:
        return False
    d = _charger()
    vivante = _resoudre(d, a)
    if vivante == n or vivante not in d["comptes"]:
        return False                                                    # déjà fait, ou aucune série à faire suivre
    _fusionner(d, vivante, n)                                           # les alias vers l'ancienne clé suivent aussi
    _enregistrer(d)
    return True


def purger(jours: int = JOURS) -> int:
    """Retire les relevés et les Reels de plus de `jours` jours ; renvoie le nombre d'éléments retirés."""
    if not actif():
        return 0
    d = _charger()
    n = _purger(d, jours)
    _enregistrer(d)
    return n


# ------------------------------------------------------------------ lecture
def serie(cle) -> dict:
    """{"id", "releves", "reels"} du compte (alias suivis), copie ; {} si inconnu."""
    return copy.deepcopy(_serie_brute(cle))


def dernier_releve(cle, source=None):
    """Le dernier relevé du compte (d'une source donnée si `source`), copie ; None si aucun."""
    rels = [r for r in _serie_brute(cle).get("releves", []) if source is None or r.get("source") == source]
    return dict(rels[-1]) if rels else None


def _followers_a(s: dict, quand=None):
    q = _maintenant(quand)
    meilleur = None
    for r in s.get("releves", []):
        t, f = _instant(r.get("t")), r.get("followers")
        if t is None or t > q or isinstance(f, bool) or not isinstance(f, int):
            continue
        rang = (t, 1 if r.get("source") == "metricool" else 0)          # même heure : Metricool (source officielle) prime
        if meilleur is None or rang >= meilleur[0]:
            meilleur = (rang, f)
    return meilleur[1] if meilleur else None


def _delta_followers(s: dict, heures: float, maintenant=None):
    now = _maintenant(maintenant)
    tol = timedelta(hours=max(12.0, float(heures) * 0.25))
    rels = [r for r in s.get("releves", []) if isinstance(r.get("followers"), int) and not isinstance(r.get("followers"), bool)
            and _instant(r.get("t")) is not None]
    sources = ["metricool", "apify"] + sorted({str(r.get("source")) for r in rels} - {"metricool", "apify"})
    for src in sources:                                                 # une seule source aux deux bouts : jamais d'écart entre outils
        rs = sorted((r for r in rels if r.get("source") == src), key=lambda r: _instant(r["t"]))
        if not rs:
            continue
        dernier = rs[-1]
        t1 = _instant(dernier["t"])
        if t1 > now + timedelta(minutes=5) or now - t1 > timedelta(hours=PERIME_H):
            continue
        cible = t1 - timedelta(hours=float(heures))
        avant = [r for r in rs if _instant(r["t"]) <= cible]
        if avant and cible - _instant(avant[-1]["t"]) <= tol:
            return int(dernier["followers"]) - int(avant[-1]["followers"])
    return None


def _vues_age_fixe(s: dict, debut, fin, age_h: float = 48):
    d0, d1 = _instant(debut), _instant(fin)
    if d0 is None or d1 is None or d1 <= d0:
        return None
    vals = []
    for x in (s.get("reels") or {}).values():
        p = _instant(x.get("publie"))
        if p is None or not (d0 <= p < d1):
            continue
        but = p + timedelta(hours=float(age_h))
        meilleur = None
        for pt in x.get("vues") or []:
            if not isinstance(pt, list) or len(pt) != 2 or isinstance(pt[1], bool) or not isinstance(pt[1], (int, float)):
                continue
            t = _instant(pt[0])
            if t is None:
                continue
            ecart = abs((t - but).total_seconds())
            if ecart <= TOLERANCE_AGE_H * 3600 and (meilleur is None or ecart < meilleur[0]):
                meilleur = (ecart, int(pt[1]))
        if meilleur is not None:
            vals.append(meilleur[1])
    if not vals:
        return None
    return sum(vals), len(vals), int(statistics.median(vals) + 0.5)


def _lisible_reels(r: dict) -> bool:
    if r.get("restreint") or r.get("prive"):
        return False
    return bool(r.get("reels_lus", True))


def _intervalle(r: dict):
    """[début, fin] des publications que ce relevé voit toutes."""
    t = _instant(r.get("t"))
    if t is None:
        return None
    if "couvre" not in r:
        return (t - timedelta(hours=COUVERTURE_DEFAUT_H), t)
    if r.get("couvre") == "":
        return (_DEBUT_DES_TEMPS, t)
    c = _instant(r.get("couvre"))
    return (min(c, t), t) if c is not None else (t, t)


def _reels_publies(s: dict, debut, fin, maintenant=None):
    d0, d1 = _instant(debut), _instant(fin)
    if d0 is None or d1 is None or d1 <= d0:
        return None
    now = _maintenant(maintenant)
    ints = sorted(i for i in (_intervalle(r) for r in s.get("releves", []) if _lisible_reels(r)) if i)
    if not ints:
        return None
    dernier = max(b for _, b in ints)
    if dernier >= d1:
        borne = d1
    elif d1 >= now - timedelta(minutes=5) and now - dernier <= timedelta(hours=OUVERT_H):
        borne = dernier                                                 # période « jusqu'à maintenant » : l'état au dernier relevé
    else:
        return None                                                     # la fin de la période n'a pas été relue
    if borne <= d0:
        return None
    cur = d0
    for a, b in ints:
        if b < cur:
            continue
        if a > cur:
            return None                                                 # un trou : des Reels ont pu passer sans être vus
        cur = max(cur, b)
        if cur >= borne:
            break
    if cur < borne:
        return None
    return sum(1 for x in (s.get("reels") or {}).values() if (p := _instant(x.get("publie"))) is not None and d0 <= p < d1)


def _derniere_lecture(s: dict) -> str:
    ts = [str(r.get("t") or "") for r in s.get("releves", []) if r.get("t")]
    return max(ts, key=lambda t: _instant(t) or _DEBUT_DES_TEMPS) if ts else ""


def followers_a(cle, quand=None):
    """Followers du dernier relevé lu au plus tard à `quand` (maintenant par défaut) ; None si aucun."""
    return _followers_a(_serie_brute(cle), quand)


def delta_followers(cle, heures, maintenant=None):
    """Écart de followers sur `heures` heures, entre le dernier relevé lu et celui d'environ `heures` heures avant (même source,
    Metricool d'abord ; tolérance max(12 h, heures/4)) ; None si l'un manque ou si le dernier relevé a plus de 60 h."""
    return _delta_followers(_serie_brute(cle), heures, maintenant)


def vues_age_fixe(cle, debut, fin, age_h=48):
    """(somme, nombre de Reels, médiane) des vues des Reels publiés dans [debut, fin[, chacune relevée au point le plus proche
    de publication + age_h (à ±18 h, sinon le Reel est ignoré) ; None si aucun Reel n'est mesurable."""
    return _vues_age_fixe(_serie_brute(cle), debut, fin, age_h)


def reels_publies(cle, debut, fin, maintenant=None):
    """Nombre de Reels publiés dans [debut, fin[ ; None si la période n'est pas entièrement couverte par des relevés lisibles
    (compte restreint, privé, trou dans les relevés, fin de période pas encore relue)."""
    return _reels_publies(_serie_brute(cle), debut, fin, maintenant)


def derniere_lecture(cle) -> str:
    """L'heure (ISO) du dernier relevé du compte, toutes sources ; '' si jamais lu."""
    return _derniere_lecture(_serie_brute(cle))
