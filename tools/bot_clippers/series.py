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
     "alias": {"<ancienne clé>": "<nouvelle clé>"},
     "renommes": {"<nouvelle clé>": {"de": "<ancienne clé>", "t": iso}}}      # 09/10 (revue 3), facultatif

Règles (jamais un faux 0) :
  - un relevé n'existe que pour un compte LU ; `followers: None` = illisible, jamais 0 par défaut ;
  - vues d'un Reel : `vues_post` — videoPlayCount si c'est un nombre, sinon videoViewCount, sinon absent (aucun point ajouté).
    La même règle partout (scan des comptes, cadence_reels) ;
  - Reels = vidéos non épinglées vues dans latestPosts, gardés 40 jours après publication, 20 points de vues au plus
    (6 au-delà de 15 jours), les points proches de 24 h / 48 h / 72 h / 7 j après la publication toujours gardés ;
  - un même Reel vu par deux sources sous deux codes (publié à 2 minutes près) n'est compté qu'une fois ; 09/10 (revue) : les
    codes vus d'un Reel sont gardés (« codes ») et cherchés d'abord, il reste un seul Reel aux passages suivants ;
  - `couvre` (facultatif) dit depuis quand le relevé voit TOUTES les publications du compte : "" = tout l'historique visible
    (moins de publications que latestPosts n'en montre), une date = la plus ancienne publication non épinglée vue (12 au plus),
    absent = les 48 h avant le relevé. `reels_publies` ne répond que si la période est entièrement couverte ;
  - un @ renommé (series.renommer, ou même id Instagram vu sous un autre @) : la série suit, l'ancienne clé devient un alias.
    09/10 (revue) : une série qui porte l'id Instagram d'un compte (relevés Apify) ne suit plus un renommage du classeur (c'était
    peut-être le compte d'un inconnu qui avait pris le @ prévu) ; si c'est le même compte, l'id la fait suivre au relevé suivant.
    Un relevé Apify d'un AUTRE id que celui de la série repart d'une série vide (le @ est maintenant à quelqu'un d'autre) ; 09/10
    (revue 3) : l'ancienne série est archivée sous « #<son id> », rendue à son compte au premier relevé qui porte cet id.
    09/10 (revue 3) : tout renommage passé par `renommer` est noté (« renommes » : {nouvelle clé: {de, t}}, 40 jours), fusion ou
    pas : `renomme_depuis(cle)` dit au scan que les cellules de la ligne viennent peut-être de l'ancien @.
  - `reels_vus(cle, debut, fin)` : les Reels vus publiés dans la période, sans exiger qu'elle soit couverte (un minimum).

Calculs purs, testés : followers_a, delta_followers, vues_age_fixe, reels_publies, derniere_lecture. Les dates acceptent un
`datetime` (sans fuseau = UTC), une chaîne ISO, ou une `date` (= minuit à Paris).
Les écritures sont synchrones (lecture, modification, écriture sans `await` au milieu) : deux boucles asyncio ne peuvent pas
s'écraser. La lecture est gardée en cache tant que le fichier ne change pas (le Dashboard relit souvent).
09/10 (revue, contrat C6c) : `ajouter_releves(entrees)` = UNE écriture par passage, et tout écrivain de séries passe par lui
(`ajouter_releve` aussi) ; le contenu reste en cache après l'écriture (plus relu ni re-purgé à chaque relevé : 0,7 s par
relevé, 22 s par passage Metricool, boucle du bot bloquée) ; le fichier est écrit par ce module en JSON compact, de façon
atomique (fichier temporaire puis os.replace, copie .bak gardée) ; la purge à 40 jours passe au plus une fois par heure."""
import copy
import json
import logging
import os
import re
import statistics
import time as _horloge
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

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
# 09/10 (revue) : 72 h ajouté — au-delà de 15 jours (6 points), le premier, le dernier, 24 h, 48 h, 72 h et 7 j restent
CIBLES_COURTES_H = (24, 48, 72, 168)
_DEBUT_DES_TEMPS = datetime(2000, 1, 1, tzinfo=timezone.utc)
PURGE_S = 3600                                # 09/10 (revue) : la purge à 40 jours au plus une fois par heure
ARCHIVE = "#"                                 # 09/10 (revue 3) : clé d'archive « #<id Instagram> » d'une série dont le @ a été repris

_deps = {}
_cache = {"d": None, "f": "", "sig": None, "purge": 0.0}
_PARIS = None


def configurer(deps: dict):
    global _deps
    _deps = dict(deps or {})
    _cache.update(d=None, f="", sig=None, purge=0.0)


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


def _ecrire_fichier(f, d: dict):
    """09/10 (revue) : l'écrivain du fichier des séries — JSON compact (deux fois plus petit et plus rapide que l'indenté du bot),
    écriture atomique : fichier temporaire, l'ancien gardé en .bak (relu par lire_json si le fichier est abîmé), puis os.replace."""
    p = Path(f)
    contenu = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(contenu, encoding="utf-8")
    if p.exists():
        try:
            os.replace(p, p.with_suffix(p.suffix + ".bak"))
        except OSError:
            pass
    os.replace(tmp, p)


def _enregistrer(d: dict):
    """Écrit le fichier et GARDE le contenu en cache (09/10, revue : avant, chaque relevé relisait tout le fichier). Si
    l'écriture échoue, le cache est vidé : la prochaine lecture repart du disque."""
    f = _deps["FICHIER_SERIES"]
    try:
        if isinstance(f, (str, os.PathLike)):
            _ecrire_fichier(f, d)
        else:                                                           # cible non fichier (bouchon) : l'écrivain configuré
            _deps["ecrire_json"](f, d)
    except Exception:
        _cache["d"] = None
        raise
    _cache.update(d=d, f=str(f), sig=_signature(f))


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
    if e is None:                                                       # 09/10 (revue) : un code déjà vu sous un autre nom
        e = next((x for x in reels.values() if code in (x.get("codes") or [])), None)
    if e is None:                                                       # le même Reel, vu par une autre source sous un autre code
        for k, x in reels.items():
            p = _instant(x.get("publie"))
            if p is not None and abs((p - publie).total_seconds()) <= MEME_REEL_S and source not in (x.get("sources") or []):
                e = x
                codes = x.setdefault("codes", [k])                      # les codes vus du Reel : retrouvé par le sien aux passages suivants
                if code not in codes:
                    codes.append(code)
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
            noms = {code} | set(x.get("codes") or [])
            y = reels.get(code) or next((z for k, z in reels.items() if noms & ({k} | set(z.get("codes") or []))), None)
            if y is None:
                reels[code] = x
                continue
            vus = {p[0] for p in y.get("vues", [])}
            pts = sorted(y.get("vues", []) + [p for p in x.get("vues", []) if p[0] not in vus], key=lambda p: str(p[0]))
            publie = _instant(y.get("publie")) or _instant(x.get("publie"))
            y["vues"] = _amincir(pts, publie, _maxi_points(publie, _instant(pts[-1][0]))) if pts and publie else pts
            y["sources"] = sorted(set(y.get("sources") or []) | set(x.get("sources") or []))
            if y.get("codes") or x.get("codes"):                       # 09/10 (revue) : les codes vus suivent aussi
                y["codes"] = sorted(set(y.get("codes") or []) | noms)
    d["alias"][a] = n
    for k, v in list(d["alias"].items()):
        if _cle(v) == a:
            d["alias"][k] = n
    d["alias"].pop(n, None)                                             # la nouvelle clé est vivante
    return src is not None


def _id_apify(s: dict) -> bool:
    """La série porte un id Instagram posé par un relevé Apify (le seul qui en donne un)."""
    return bool(str((s or {}).get("id") or "")) and any(r.get("source") == "apify" for r in (s or {}).get("releves", []))


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
    if src == "apify" and ig:
        # 09/10 (revue) : la série de cette clé porte l'id d'un AUTRE compte Instagram (le @ a été repris par quelqu'un d'autre, ou un
        # renommage du classeur avait fait suivre la série d'un inconnu) : elle repart de zéro, jamais mélangée au compte lu.
        # 09/10 (revue 3 : l'historique du clipper était effacé) : l'ancienne série n'est plus jetée, elle est rangée sous la clé
        # d'archive « #<son id> » (sans alias) ; la boucle « même id sous un autre @ » ci-dessous la rend à son compte dès qu'un
        # relevé porte cet id, sinon la purge à 40 jours la retire
        actuel = d["comptes"].get(cible)
        if actuel and str(actuel.get("id") or "") not in ("", ig) and _id_apify(actuel):
            _fusionner(d, cible, ARCHIVE + str(actuel.get("id")))
            d["alias"].pop(cible, None)                                 # la clé reste celle du compte lu, pas un alias de l'archive
            d["comptes"][cible] = {"id": ig, "releves": [], "reels": {}}
            journal.info("Séries : la série d'une clé portait un autre compte Instagram, archivée, la clé repart de zéro")
        for autre, s in list(d["comptes"].items()):                     # même id Instagram sous un autre @ : renommé, la série suit
            if autre != cible and str(s.get("id") or "") == ig and _id_apify(s):
                _fusionner(d, autre, cible)
                if autre.startswith(ARCHIVE):
                    d["alias"].pop(autre, None)                         # une archive rendue à son compte n'est pas un @ : pas d'alias
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
    ren = d.get("renommes") if isinstance(d.get("renommes"), dict) else {}
    for k in list(ren):                                                 # 09/10 (revue 3) : renommages notés, 40 jours
        if not isinstance(ren[k], dict) or (_instant(ren[k].get("t")) or limite - timedelta(1)) < limite:
            del ren[k]
    return n


def ajouter_releve(cle, releve: dict, reels=(), ig_id="", source=None, couvre=None) -> bool:
    """Un relevé d'un compte LU (jamais pour un non-lu) et les Reels vus à ce relevé ([{code, publie, type, vues}]).
    `source` (facultatif) remplace releve["source"] ; `couvre` (facultatif) : voir l'en-tête du module. 09/10 (contrat C6c) :
    passe par ajouter_releves (une écriture) ; un écrivain de plusieurs comptes appelle ajouter_releves directement."""
    entree = {"cle": cle, "releve": releve, "reels": list(reels or []), "ig_id": ig_id, "source": source, "couvre": couvre}
    return ajouter_releves([entree]) == 1


def ajouter_releves(entrees: list) -> int:
    """Plusieurs relevés en UNE écriture (contrat C6c : un passage du scan, de Metricool… = un appel). entrees = [{cle, releve,
    reels, ig_id, source?, couvre?}]. Renvoie le nombre de relevés enregistrés. Le contenu est pris du cache (relu seulement si
    le fichier a changé), la purge passe au plus une fois par heure."""
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
        if _horloge.monotonic() - _cache["purge"] >= PURGE_S or not _cache["purge"]:
            _purger(d)
            _cache["purge"] = _horloge.monotonic()
        _enregistrer(d)
    return n


def renommer(ancienne, nouvelle) -> bool:
    """@ renommé (onboarding.renommer_compte) : la série suit la nouvelle clé, l'ancienne devient un alias.
    09/10 (revue) : sauf si la série porte l'id Instagram d'un compte (relevés Apify) — c'était peut-être le compte d'un INCONNU
    lu sous le @ prévu (@ pris, retrouvé sous un @ proche, `!pseudo`) : elle reste où elle est, rien n'est mélangé. Si c'est bien
    le même compte (renommé sur Instagram), le premier relevé sous le nouvel @ porte le même id et la série suit alors."""
    if not actif():
        return False
    a, n = _cle(ancienne), _cle(nouvelle)
    if not a or not n or a == n:
        return False
    d = _charger()
    # 09/10 (revue 3) : le renommage est noté dans tous les cas (fusion ou pas) : les cellules Followers / Reels de la ligne viennent
    # peut-être de l'ancien @ (le compte d'un inconnu qui l'avait pris) — le scan ne s'en sert alors jamais comme preuve (renomme_depuis)
    if not isinstance(d.get("renommes"), dict):
        d["renommes"] = {}
    d["renommes"][n] = {"de": a, "t": _iso(datetime.now(timezone.utc))}
    vivante = _resoudre(d, a)
    fusion = vivante != n and vivante in d["comptes"] and not _id_apify(d["comptes"][vivante])
    if vivante != n and vivante in d["comptes"] and not fusion:
        journal.info("Séries : renommage sans fusion (la série porte un id Instagram ; elle suivra si le nouvel @ a le même)")
    if fusion:
        _fusionner(d, vivante, n)                                       # les alias vers l'ancienne clé suivent aussi
    _enregistrer(d)
    return fusion


def purger(jours: int = JOURS) -> int:
    """Retire les relevés et les Reels de plus de `jours` jours ; renvoie le nombre d'éléments retirés."""
    if not actif():
        return 0
    d = _charger()
    n = _purger(d, jours)
    _cache["purge"] = _horloge.monotonic()
    _enregistrer(d)
    return n


# ------------------------------------------------------------------ lecture
def serie(cle) -> dict:
    """{"id", "releves", "reels"} du compte (alias suivis), copie ; {} si inconnu."""
    return copy.deepcopy(_serie_brute(cle))


def id_instagram(cle) -> str:
    """09/10 (revue) : l'id Instagram que les relevés Apify ont posé sur la série du compte ('' si aucun) — sans copie de la série.
    Le scan s'en sert pour ne jamais juger un compte sur les chiffres d'un autre (même @, autre compte)."""
    s = _serie_brute(cle)
    return str(s.get("id") or "") if _id_apify(s) else ""


def cle_du_compte(ig_id) -> str:
    """09/10 (revue) : la clé de la série qui porte cet id Instagram (posé par Apify), sous quelque @ que ce soit ; '' si aucune."""
    ig = str(ig_id or "").strip()
    if not ig or not actif():
        return ""
    for k, s in _charger()["comptes"].items():
        if str(s.get("id") or "") == ig and _id_apify(s):
            return k
    return ""


def renomme_depuis(cle) -> str:
    """09/10 (revue 3) : l'ancienne clé si ce @ est le nouveau nom d'un compte renommé (noté par `renommer`, fusion ou pas, ou un
    alias vers lui) ; '' sinon. Le scan ne prend alors jamais les cellules de la ligne pour une preuve : elles viennent peut-être
    de l'ancien @."""
    k = _cle(cle)
    if not k or not actif():
        return ""
    d = _charger()
    r = (d.get("renommes") or {}).get(k) if isinstance(d.get("renommes"), dict) else None
    if isinstance(r, dict) and r.get("de"):
        return str(r["de"])
    return next((a for a, v in (d.get("alias") or {}).items() if _cle(v) == k), "")


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


def reels_vus(cle, debut, fin) -> int:
    """09/10 (revue 3) : le nombre de Reels VUS (par un relevé quelconque, toutes sources) publiés dans [debut, fin[ — un minimum,
    sans exiger que la période soit couverte (reels_publies, lui, est exact ou None). 0 si aucun."""
    d0, d1 = _instant(debut), _instant(fin)
    if d0 is None or d1 is None or d1 <= d0:
        return 0
    return sum(1 for x in (_serie_brute(cle).get("reels") or {}).values()
               if (p := _instant(x.get("publie"))) is not None and d0 <= p < d1)


def derniere_lecture(cle) -> str:
    """L'heure (ISO) du dernier relevé du compte, toutes sources ; '' si jamais lu."""
    return _derniere_lecture(_serie_brute(cle))
