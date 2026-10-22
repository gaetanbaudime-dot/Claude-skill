"""Suivi Instagram par RapidAPI « Instagram Looter » (22/10/2026, Gaëtan : « il faut vraiment que je sois capable de traquer les
followers, le nombre de Reels postés et les vues sur chacun des comptes des clippers et des créatrices… c'est ce qui permet de passer
du compte 1 au compte 2 : les clippers ne reçoivent jamais le compte 2 parce qu'on ne sait pas compter les Reels du compte 1 »).

Trois usages, une seule source (clé RAPIDAPI_KEY dans Railway, jamais écrite ailleurs) :

  1. PARCOURS (prioritaire, toutes les PRIORITE_MIN minutes) : pour chaque clipper qui attend son compte 2 ou 3, les Reels du compte
     d'avant sont relus par leur ID Instagram et versés comme preuves datées (code + date de publication, type « reel ») dans sa
     fiche parcours — exactement le format que `parcours.reels_pour` compte déjà. `programme_du_jour` (toutes les 10 minutes) ouvre
     alors le compte suivant dès 4 Reels publiés APRÈS la création du compte (règle inchangée : « 48 h et 4 Reels »).
  2. SUIVI DE TOUS LES COMPTES (PASSAGES_HEURES, heure de Paris : 3 fois par jour) : profil (ID, followers, publications, privé,
     introuvable) et première page de Reels (vues, likes, commentaires) de chaque compte vivant du LOG DASHBOARD IG, clippers et
     créatrices. Historique dans DONNEES/instagram.json.
  3. TOP REELS DES CRÉATRICES : les comptes « Compte de la créatrice » sont remontés une fois sur HISTORIQUE_CREATRICE_J jours
     (pagination), puis suivis comme les autres ; leurs 20 meilleurs Reels par vues partent dans l'onglet « IG · Top Reels ».

Backend (tableur « App clippers · usage », privé) : « IG · Comptes » (une ligne par compte : followers, écarts, Reels et vues sur
1/7/15/30/60 jours, dernier Reel, statut), « IG · Reels » (chaque Reel des 60 derniers jours) et « IG · Top Reels ». Le Cockpit les lit.

Jamais d'exception ; jamais de faux 0 : un compte non relu garde sa dernière mesure et sa date. Quota : au plus QUOTA_JOUR requêtes
par jour, et le suivi complet s'arrête quand le quota RapidAPI restant passe sous RESERVE (le parcours garde sa part).
Les réponses de l'API sont lues de façon tolérante (plusieurs noms de champs possibles) : le premier exemple de chaque route part
dans l'onglet « Test API Instagram » pour contrôle.
"""

import asyncio
import json
import logging
import os
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

journal = logging.getLogger("instagram_rapidapi")

CLE = os.environ.get("RAPIDAPI_KEY", "").strip()
HOTE = os.environ.get("RAPIDAPI_INSTAGRAM_HOTE", "instagram-looter2.p.rapidapi.com").strip()
QUOTA_JOUR = int(os.environ.get("RAPIDAPI_QUOTA_JOUR", "2400") or 2400)
RESERVE = int(os.environ.get("RAPIDAPI_RESERVE", "150") or 150)
PRIORITE_MIN = max(20, int(os.environ.get("RAPIDAPI_PRIORITE_MIN", "60") or 60))
PASSAGES_HEURES = [int(x) for x in os.environ.get("RAPIDAPI_PASSAGES", "7,14,21").split(",") if x.strip().isdigit()]
HISTORIQUE_CREATRICE_J = int(os.environ.get("RAPIDAPI_HISTORIQUE_J", "365") or 365)
PAGES_HISTORIQUE = int(os.environ.get("RAPIDAPI_PAGES_HISTORIQUE", "25") or 25)
GARDE_REELS_J = 90                                                      # Reels des clippers gardés en mémoire
PAUSE = float(os.environ.get("RAPIDAPI_PAUSE", "0.4") or 0.4)
ACTIF = os.environ.get("RAPIDAPI_SUIVI", "1").strip() != "0"
ONGLET_COMPTES, ONGLET_REELS, ONGLET_TOP = "IG · Comptes", "IG · Reels", "IG · Top Reels"
ENTETE_COMPTES = ["Créatrice", "Gérant", "Type", "@", "ID Instagram", "Statut", "Followers", "Δ 24 h", "Δ 7 j", "Publications",
                  "Reels 24 h", "Reels 7 j", "Reels 15 j", "Reels 30 j", "Reels 60 j", "Vues 7 j", "Vues 15 j", "Vues 30 j",
                  "Vues 60 j", "Dernier Reel", "Profil relu le", "Reels relus le"]
ENTETE_REELS = ["Créatrice", "Gérant", "Type", "@", "Code", "Lien", "Publié le", "Vues", "Likes", "Commentaires", "Relu le"]
ENTETE_TOP = ["Créatrice", "Rang", "@", "Lien", "Publié le", "Vues", "Likes", "Commentaires"]
ETATS_VIVANTS = ("good", "prive", "privé", "private")

_deps = {}
_jour = {"jour": "", "n": 0, "restant": None}
_echantillons_faits = set()
_verrou = None


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (DONNEES/instagram.json)."""
    _deps.update(deps)


# ------------------------------------------------------------------ lecture tolérante des réponses (pur, testé)
def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def chercher(obj, cles, profondeur=0):
    """La première valeur non vide d'une des `cles` (« a.b » = chemin), en largeur dans un JSON imbriqué."""
    if profondeur > 6 or obj is None:
        return None
    if isinstance(obj, dict):
        for cle in cles:
            v = obj
            for morceau in cle.split("."):
                v = v.get(morceau) if isinstance(v, dict) else None
            if v not in (None, "", [], {}):
                return v
        for v in obj.values():
            if isinstance(v, (dict, list)):
                r = chercher(v, cles, profondeur + 1)
                if r not in (None, "", [], {}):
                    return r
    elif isinstance(obj, list):
        for v in obj[:5]:
            r = chercher(v, cles, profondeur + 1)
            if r not in (None, "", [], {}):
                return r
    return None


def _entier(v):
    try:
        return int(float(v)) if v not in (None, "", True, False) else None
    except (TypeError, ValueError):
        return None


def introuvable(code: int, corps) -> bool:
    """La réponse dit que le compte n'existe pas (supprimé, banni, renommé)."""
    if code == 404:
        return True
    texte = _n(json.dumps(corps, ensure_ascii=False)[:600]) if corps is not None else ""
    return any(m in texte for m in ("user not found", "not found", "no user", "doesn't exist", "does not exist", "page not found",
                                    "user_not_found", "invalid username"))


def lire_profil(corps) -> dict:
    """Réponse de /profile ou /web-profile → {id, username, followers, suivis, publications, prive}. Champs absents : None."""
    u = chercher(corps, ["data.user", "user", "graphql.user"]) if isinstance(corps, dict) else None
    base = u if isinstance(u, dict) else corps
    return {"id": str(chercher(base, ["pk", "pk_id", "id", "user_id"]) or "") or None,
            "username": chercher(base, ["username"]),
            "followers": _entier(chercher(base, ["follower_count", "edge_followed_by.count", "followers", "followers_count"])),
            "suivis": _entier(chercher(base, ["following_count", "edge_follow.count", "following"])),
            "publications": _entier(chercher(base, ["media_count", "edge_owner_to_timeline_media.count", "posts_count"])),
            "prive": chercher(base, ["is_private"])}


def lire_id(corps):
    """Réponse de /id → l'ID Instagram (texte) ou None."""
    v = chercher(corps, ["user_id", "pk", "id", "data.user_id"]) if corps is not None else None
    return str(v) if v not in (None, "", False) and str(v).isdigit() else None


def _instant(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        try:
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _medias(obj, profondeur=0) -> list:
    """Tous les objets média (ceux qui ont un code et une date de publication) d'une réponse, sans doublon."""
    out = []
    if profondeur > 6:
        return out
    if isinstance(obj, dict):
        code = obj.get("code") or obj.get("shortcode")
        quand = obj.get("taken_at") or obj.get("taken_at_timestamp") or obj.get("device_timestamp")
        if code and quand and isinstance(code, str):
            out.append(obj)
            return out
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out += _medias(v, profondeur + 1)
    elif isinstance(obj, list):
        for v in obj:
            out += _medias(v, profondeur + 1)
    return out


def lire_reels(corps) -> tuple:
    """Réponse de /reels → ([{code, publie (ISO), vues, likes, commentaires}], curseur suivant ou None)."""
    vus, reels = set(), []
    for m in _medias(corps):
        code = str(m.get("code") or m.get("shortcode"))
        quand = _instant(m.get("taken_at") or m.get("taken_at_timestamp") or m.get("device_timestamp"))
        if code in vus or quand is None:
            continue
        vus.add(code)
        reels.append({"code": code, "publie": quand.isoformat(timespec="seconds"),
                      "vues": _entier(m.get("play_count") or m.get("ig_play_count") or m.get("view_count")
                                      or m.get("video_view_count") or m.get("video_play_count")),
                      "likes": _entier(m.get("like_count") or (m.get("edge_liked_by") or {}).get("count")),
                      "commentaires": _entier(m.get("comment_count") or (m.get("edge_media_to_comment") or {}).get("count"))})
    plus = chercher(corps, ["paging_info.more_available", "more_available", "has_next_page", "page_info.has_next_page"])
    curseur = chercher(corps, ["paging_info.max_id", "next_max_id", "max_id", "end_cursor", "page_info.end_cursor"])
    return reels, (str(curseur) if curseur and plus is not False else None)


# ------------------------------------------------------------------ calculs (pur, testé)
def fenetres(reels: dict, maintenant: datetime) -> dict:
    """{code: {publie, vues}} → Reels et vues sur 1, 7, 15, 30, 60 jours, et le dernier Reel (ISO)."""
    out = {"dernier": ""}
    for j in (1, 7, 15, 30, 60):
        out[f"reels{j}"], out[f"vues{j}"] = 0, 0
    for r in (reels or {}).values():
        quand = _instant(r.get("publie"))
        if quand is None:
            continue
        out["dernier"] = max(out["dernier"], quand.isoformat(timespec="seconds"))
        age = maintenant - quand
        for j in (1, 7, 15, 30, 60):
            if timedelta(0) <= age <= timedelta(days=j):
                out[f"reels{j}"] += 1
                out[f"vues{j}"] += int(r.get("vues") or 0)
    return out


def ecart(suivi: list, heures: int, maintenant: datetime):
    """Écart de followers sur `heures` : dernière mesure moins la mesure la plus proche de maintenant − heures (± 30 %)."""
    points = [(_instant(t), f) for t, f, *_ in (suivi or []) if f is not None and _instant(t)]
    if len(points) < 2:
        return None
    dernier_t, dernier_f = points[-1]
    cible = maintenant - timedelta(hours=heures)
    proches = [(abs((t - cible).total_seconds()), f) for t, f in points[:-1] if abs((t - cible).total_seconds()) <= heures * 3600 * 0.3]
    return dernier_f - min(proches)[1] if proches else None


def preuves(reels: list, creation) -> list:
    """Reels relus → preuves au format du parcours (process_clippeur.cumuler_reels_verifies) : publiés après la création."""
    out = []
    for r in reels or []:
        quand = _instant(r.get("publie"))
        if quand is not None and (creation is None or quand >= creation):
            out.append({"code": r["code"], "publie": r["publie"], "type_verifie": "reel"})
    return out


def type_compte(c: dict, creatrices: set) -> str:
    u, g = _n(c.get("utilisation")), _n(c.get("gerant")).split()
    if "creatrice" in u or (g and g[0] in creatrices):
        return "Créatrice"
    if "metricool" in u or "metricool" in _n(c.get("gerant")):
        return "Metricool"
    return "Clipper"


def comptes_a_suivre(comptes: list) -> list:
    """Lignes du LOG → comptes vivants à suivre (GOOD / PRIVE), une fois chacun : [{handle, creatrice, gerant, type}]."""
    creatrices = {_n(c.get("onglet")).split()[0] for c in comptes or [] if _n(c.get("onglet"))}
    vus, out = set(), []
    for c in comptes or []:
        h = str(c.get("handle") or "").strip().lstrip("@").lower()
        if not h or h in vus or not any(_n(c.get("etat")).startswith(e) for e in ETATS_VIVANTS):
            continue
        vus.add(h)
        out.append({"handle": h, "creatrice": str(c.get("creatrice") or c.get("onglet") or "").strip(),
                    "gerant": str(c.get("gerant") or "").strip(), "type": type_compte(c, creatrices)})
    return out


def lignes_comptes(suivis: list, store: dict, maintenant: datetime) -> list:
    out = []
    for s in suivis:
        e = (store.get("comptes") or {}).get(s["handle"]) or {}
        f = fenetres((store.get("reels") or {}).get(s["handle"]) or {}, maintenant)
        suivi = e.get("suivi") or []
        dernier = suivi[-1] if suivi else [None, None, None]
        txt = lambda v: "" if v is None else str(v)                     # noqa: E731
        lu_reels = bool(e.get("reels_le"))
        out.append([s["creatrice"], s["gerant"], s["type"], s["handle"], txt(e.get("id")), e.get("statut") or "pas encore relu",
                    txt(dernier[1]), txt(ecart(suivi, 24, maintenant)), txt(ecart(suivi, 168, maintenant)), txt(dernier[2] if len(dernier) > 2 else None),
                    *[(str(f[f"reels{j}"]) if lu_reels else "") for j in (1, 7, 15, 30, 60)],
                    *[(str(f[f"vues{j}"]) if lu_reels else "") for j in (7, 15, 30, 60)],
                    f["dernier"], e.get("profil_le") or "", e.get("reels_le") or ""])
    return out


def lignes_reels(suivis: list, store: dict, maintenant: datetime, jours: int = 60) -> list:
    out = []
    infos = {s["handle"]: s for s in suivis}
    for h, reels in (store.get("reels") or {}).items():
        s = infos.get(h)
        if not s:
            continue
        for code, r in reels.items():
            quand = _instant(r.get("publie"))
            if quand is None or maintenant - quand > timedelta(days=jours):
                continue
            out.append([s["creatrice"], s["gerant"], s["type"], h, code, f"https://www.instagram.com/reel/{code}/", r["publie"],
                        "" if r.get("vues") is None else str(r["vues"]), "" if r.get("likes") is None else str(r["likes"]),
                        "" if r.get("commentaires") is None else str(r["commentaires"]), r.get("maj") or ""])
    out.sort(key=lambda x: x[6], reverse=True)
    return out


def lignes_top(suivis: list, store: dict, n: int = 20) -> list:
    """Les n meilleurs Reels (vues) des comptes de chaque créatrice, toutes dates gardées."""
    par_creatrice = {}
    for s in suivis:
        if s["type"] != "Créatrice":
            continue
        for code, r in ((store.get("reels") or {}).get(s["handle"]) or {}).items():
            if r.get("vues") is not None:
                par_creatrice.setdefault(s["creatrice"], []).append((int(r["vues"]), s["handle"], code, r))
    out = []
    for cr in sorted(par_creatrice):
        for rang, (vues, h, code, r) in enumerate(sorted(par_creatrice[cr], key=lambda x: -x[0])[:n], start=1):
            out.append([cr, str(rang), h, f"https://www.instagram.com/reel/{code}/", r.get("publie", ""), str(vues),
                        "" if r.get("likes") is None else str(r["likes"]),
                        "" if r.get("commentaires") is None else str(r["commentaires"])])
    return out


def fusionner_reels(ancien: dict, nouveaux: list, maintenant: datetime) -> dict:
    """Garde chaque Reel une fois ; ses vues, likes et commentaires prennent la dernière valeur relue."""
    d = dict(ancien or {})
    for r in nouveaux or []:
        e = dict(d.get(r["code"]) or {})
        e["publie"] = r["publie"]
        for k in ("vues", "likes", "commentaires"):
            if r.get(k) is not None:
                e[k] = r[k]
        e["maj"] = maintenant.isoformat(timespec="seconds")
        d[r["code"]] = e
    return d


# ------------------------------------------------------------------ appels
def _store() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {"comptes": {}, "reels": {}, "etat": {}})


def _sauver(d: dict):
    _deps["ecrire_json"](_deps["FICHIER"], d)


def _quota_ok(reserve: int = 0) -> bool:
    j = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _jour["jour"] != j:
        _jour.update({"jour": j, "n": 0})
    if _jour["n"] >= QUOTA_JOUR:
        return False
    return _jour["restant"] is None or _jour["restant"] > reserve


async def appeler(session, chemin: str, params: dict) -> tuple:
    """(code HTTP, corps JSON ou texte). Compte la requête et retient le quota restant annoncé par RapidAPI."""
    _jour["n"] += 1
    try:
        async with session.get(f"https://{HOTE}{chemin}", params=params,
                               headers={"X-RapidAPI-Key": CLE, "X-RapidAPI-Host": HOTE}) as r:
            texte = await r.text()
            restant = r.headers.get("x-ratelimit-requests-remaining")
            if restant and str(restant).isdigit():
                _jour["restant"] = int(restant)
            try:
                corps = json.loads(texte)
            except ValueError:
                corps = texte
            await _echantillon(chemin, params, r.status, texte)
            return r.status, corps
    finally:
        await asyncio.sleep(PAUSE)


async def _echantillon(chemin, params, code, texte):
    """Le premier exemple de chaque route dans l'onglet « Test API Instagram » (contrôle des champs), une fois par démarrage."""
    if chemin in _echantillons_faits:
        return
    _echantillons_faits.add(chemin)
    try:
        import google_api
        import paie_clics
        import relais_rapidapi
        classeur = await paie_clics._classeur_usage()
        if not classeur:
            return
        quand = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await google_api.sheets_ajouter(classeur, f"'{relais_rapidapi.ONGLET}'!A1",
                                        [["échantillon (suivi)", HOTE, chemin, "&".join(f"{k}={v}" for k, v in params.items()), "GET", "",
                                          str(code), "", "" if _jour["restant"] is None else str(_jour["restant"]),
                                          relais_rapidapi.reponse_texte(texte), quand]])
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Échantillon RapidAPI non écrit : %s", type(erreur).__name__)


async def identifiant(session, store: dict, handle: str):
    """L'ID Instagram du compte (mémorisé) ; None si introuvable ou si l'API ne répond pas."""
    e = (store.setdefault("comptes", {})).setdefault(handle, {})
    if e.get("id"):
        return e["id"]
    code, corps = await appeler(session, "/id", {"username": handle})
    i = lire_id(corps) if code == 200 else None
    if i:
        e["id"] = i
    elif introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False):
        e["statut"] = "introuvable"
    return i


async def relire_profil(session, store: dict, handle: str, maintenant: datetime) -> bool:
    e = store.setdefault("comptes", {}).setdefault(handle, {})
    params = {"id": e["id"]} if e.get("id") else {"username": handle}
    code, corps = await appeler(session, "/profile", params)
    if code != 200 or introuvable(code, corps):
        if introuvable(code, corps):
            e["statut"] = "introuvable"
            e["profil_le"] = maintenant.isoformat(timespec="seconds")
        return False
    p = lire_profil(corps)
    if p["id"]:
        e["id"] = p["id"]
    if p["username"] and _n(p["username"]) != _n(handle):
        e["renomme_en"] = p["username"]
    e["statut"] = "privé" if p["prive"] is True else "public"
    if p["followers"] is not None:
        e.setdefault("suivi", []).append([maintenant.isoformat(timespec="seconds"), p["followers"], p["publications"]])
        e["suivi"] = e["suivi"][-200:]
    e["profil_le"] = maintenant.isoformat(timespec="seconds")
    return True


async def relire_reels(session, store: dict, handle: str, maintenant: datetime, jusqu_a=None, pages: int = 1) -> list:
    """Reels du compte (pages successives jusqu'à la date `jusqu_a` ou `pages` pages) ; [] si rien n'a pu être lu."""
    i = await identifiant(session, store, handle)
    if not i:
        return []
    tous, curseur, lu = [], None, False
    for _ in range(max(1, pages)):
        params = {"id": i, "count": 12 if pages == 1 else 50}
        if curseur:
            params["max_id"] = curseur
        code, corps = await appeler(session, "/reels", params)
        if code != 200:
            break
        lu = True
        reels, curseur = lire_reels(corps)
        tous += reels
        if not curseur or not reels or (jusqu_a and min(_instant(r["publie"]) for r in reels) < jusqu_a) or not _quota_ok(RESERVE):
            break
    e = store.setdefault("comptes", {}).setdefault(handle, {})
    if lu:
        store.setdefault("reels", {})[handle] = fusionner_reels(store.get("reels", {}).get(handle), tous, maintenant)
        e["reels_le"] = maintenant.isoformat(timespec="seconds")
    return tous


# ------------------------------------------------------------------ 1. parcours : ouvrir le compte suivant
def attentes_parcours() -> list:
    """Clippers qui attendent leur compte 2 ou 3 : [(uid, handle source, création du compte source)]."""
    import parcours
    out = []
    for uid, f in (parcours._lire() or {}).items():
        if not isinstance(f, dict):
            continue
        a = parcours.attente(f)
        if not a:
            continue
        comptes = parcours._comptes_ordonnes(uid, fiche_p=f)
        for src in parcours.sources_reels(f, a[0]):
            if 0 < src <= len(comptes) and comptes[src - 1] and parcours._cree(f, src):
                out.append((uid, comptes[src - 1].strip().lstrip("@").lower(), parcours._date_creation(f, src)))
    return out


def verser_preuves(uid: str, handle: str, reels: list, creation) -> int:
    """Ajoute les Reels relus (publiés après la création) aux preuves du compte dans la fiche parcours. Renvoie le total vérifié.
    Lecture-écriture sans attente entre les deux : jamais d'écrasement d'une écriture concurrente du parcours."""
    import parcours
    import process_clippeur
    d = parcours._lire()
    f = d.get(uid)
    if not isinstance(f, dict):
        return 0
    suivi = dict((f.get("reels") or {}).get(handle) or {})
    p = preuves(reels, creation)
    maintenant = datetime.now(timezone.utc)
    suivi["reels_verifies_v2"] = process_clippeur.cumuler_reels_verifies(suivi, p, creation, maintenant)
    suivi["publications_verifiees"] = process_clippeur.cumuler_publications(suivi, p, creation, maintenant)
    suivi["source_rapidapi"] = maintenant.isoformat(timespec="seconds")
    if suivi != (f.get("reels") or {}).get(handle):
        f.setdefault("reels", {})[handle] = suivi
        parcours._ecrire(d)
    return len(suivi["reels_verifies_v2"])


async def passage_parcours(session) -> list:
    faits = []
    store = _store()
    maintenant = datetime.now(timezone.utc)
    for uid, handle, creation in attentes_parcours():
        if not _quota_ok():
            break
        reels = await relire_reels(session, store, handle, maintenant)
        if reels:
            n = verser_preuves(uid, handle, reels, creation)
            faits.append((uid, handle, n))
    _sauver(store)
    return faits


# ------------------------------------------------------------------ 2 et 3. suivi complet et top Reels
async def passage_complet(session) -> dict:
    import onboarding
    import pilotage
    comptes = comptes_a_suivre(await onboarding.lire_comptes())
    store = _store()
    maintenant = datetime.now(timezone.utc)
    bilan = {"comptes": len(comptes), "profils": 0, "reels": 0, "arret_quota": False}
    for k, s in enumerate(comptes, start=1):
        if not _quota_ok(RESERVE):
            bilan["arret_quota"] = True
            break
        h = s["handle"]
        if await relire_profil(session, store, h, maintenant):
            bilan["profils"] += 1
        e = store["comptes"].get(h) or {}
        if e.get("statut") == "introuvable":
            continue
        historique = s["type"] == "Créatrice" and not e.get("historique_fait")
        jusqu_a = maintenant - timedelta(days=HISTORIQUE_CREATRICE_J) if historique else None
        reels = await relire_reels(session, store, h, maintenant, jusqu_a=jusqu_a, pages=PAGES_HISTORIQUE if historique else 1)
        if reels:
            bilan["reels"] += 1
            if historique:
                e["historique_fait"] = maintenant.isoformat(timespec="seconds")
        if s["type"] != "Créatrice":                                     # mémoire bornée pour les clippers
            limite = maintenant - timedelta(days=GARDE_REELS_J)
            store["reels"][h] = {c: r for c, r in (store["reels"].get(h) or {}).items() if (_instant(r.get("publie")) or maintenant) >= limite}
        if k % 25 == 0:
            _sauver(store)
    _sauver(store)
    try:
        import paie_clics
        classeur = await paie_clics._classeur_usage()
        if classeur:
            await pilotage._ecrire(classeur, ONGLET_COMPTES, ENTETE_COMPTES, lignes_comptes(comptes, store, maintenant))
            await pilotage._ecrire(classeur, ONGLET_REELS, ENTETE_REELS, lignes_reels(comptes, store, maintenant))
            await pilotage._ecrire(classeur, ONGLET_TOP, ENTETE_TOP, lignes_top(comptes, store))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Suivi Instagram : onglets non écrits (%s)", str(erreur)[:200])
    return bilan


def _paris(maintenant: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return maintenant.astimezone(ZoneInfo("Europe/Paris"))
    except Exception:                                                   # noqa: BLE001
        return maintenant + timedelta(hours=2)


def passage_du(etat: dict, maintenant: datetime) -> str:
    """Pur : la clé « AAAA-MM-JJ-HH » du passage complet à faire maintenant, ou '' (chaque heure de PASSAGES_HEURES, une fois)."""
    p = _paris(maintenant)
    dus = [h for h in PASSAGES_HEURES if p.hour >= h]
    if not dus:
        return ""
    cle = f"{p.date().isoformat()}-{max(dus):02d}"
    return "" if etat.get("dernier_passage") == cle else cle


async def boucle():
    """Toutes les 5 minutes : parcours toutes les PRIORITE_MIN minutes, suivi complet aux heures prévues. Jamais d'exception."""
    import aiohttp
    if not (CLE and ACTIF):
        journal.info("Suivi Instagram RapidAPI éteint (%s)", "pas de RAPIDAPI_KEY" if not CLE else "RAPIDAPI_SUIVI=0")
        return
    await asyncio.sleep(90)
    derniere_priorite = 0.0
    while True:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                if time.monotonic() - derniere_priorite >= PRIORITE_MIN * 60:
                    derniere_priorite = time.monotonic()
                    faits = await passage_parcours(session)
                    if faits:
                        journal.info("Suivi Instagram, parcours : %s", ", ".join(f"{h} {n} Reels" for _, h, n in faits))
                store = _store()
                cle = passage_du(store.get("etat") or {}, datetime.now(timezone.utc))
                if cle:
                    bilan = await passage_complet(session)
                    store = _store()
                    store.setdefault("etat", {})["dernier_passage"] = cle
                    store["etat"]["dernier_bilan"] = bilan
                    _sauver(store)
                    journal.info("Suivi Instagram, passage %s : %s (requêtes du jour %d, quota restant %s)", cle, bilan, _jour["n"], _jour["restant"])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Suivi Instagram : %s", str(erreur)[:200])
        await asyncio.sleep(300)
