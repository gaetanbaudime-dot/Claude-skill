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
# 22/10 (comparatif des API de Gaëtan) : FlashAPI d'abord (98 % de disponibilité, 2,8 s, tests RapidAPI à 100 %), Instagram Looter
# en secours (75 k requêtes pour 27,90 $, mais 8 s et 85 % aux tests). Mêmes données : ID, profil par ID, Reels paginés.
FOURNISSEURS = {
    "flash": {"hote": "flashapi1.p.rapidapi.com",
              "id": ("/ig/user_id/", lambda h: {"user": h}),
              "profil": ("/ig/info/", lambda i: {"id_user": i}),
              "reels": ("/ig/reels_posts/", lambda i, cur, n: {"id_user": i, **({"max_id": cur} if cur else {})}),
              # 22/10 (Gaëtan : itschloe.douceur et itsvanlifesophie ont des dizaines de Reels, le relevé en voyait 12-16) : pour
              # certains comptes, /ig/reels_posts/ s'arrête sans page suivante. Route de secours : les publications du compte
              # (toutes, filtrées sur les vidéos). Le chemin exact est découvert une fois parmi ces candidats, puis mémorisé.
              # 22/10 : seul /ig/posts/ existe (les autres : « does not exist ») ; il a répondu « Temporary upstream error ».
              "posts_candidats": ["/ig/posts/", "/ig/user_posts/", "/ig/medias/", "/ig/feed/", "/ig/clips/"]},
    "looter": {"hote": "instagram-looter2.p.rapidapi.com",
               "id": ("/id", lambda h: {"username": h}),
               "profil": ("/profile", lambda i: {"id": i}),
               "reels": ("/reels", lambda i, cur, n: {"id": i, "count": n, **({"max_id": cur} if cur else {})})},
}
FOURNISSEUR = os.environ.get("RAPIDAPI_INSTAGRAM_FOURNISSEUR", "flash").strip().lower()
API = FOURNISSEURS.get(FOURNISSEUR, FOURNISSEURS["flash"])
HOTE = os.environ.get("RAPIDAPI_INSTAGRAM_HOTE", API["hote"]).strip()
QUOTA_JOUR = int(os.environ.get("RAPIDAPI_QUOTA_JOUR", "2400") or 2400)
RESERVE = int(os.environ.get("RAPIDAPI_RESERVE", "150") or 150)
PRIORITE_MIN = max(20, int(os.environ.get("RAPIDAPI_PRIORITE_MIN", "60") or 60))
PASSAGES_HEURES = [int(x) for x in os.environ.get("RAPIDAPI_PASSAGES", "7,14,21").split(",") if x.strip().isdigit()]
HISTORIQUE_CREATRICE_J = int(os.environ.get("RAPIDAPI_HISTORIQUE_J", "365") or 365)
PAGES_HISTORIQUE = int(os.environ.get("RAPIDAPI_PAGES_HISTORIQUE", "25") or 25)
FENETRE_RELUE_J = int(os.environ.get("RAPIDAPI_FENETRE_J", "15") or 15)   # chaque passage relit les Reels de 15 j (vues à jour)
PAGES_FENETRE = int(os.environ.get("RAPIDAPI_PAGES_FENETRE", "4") or 4)    # 12 Reels par page : 4 pages = 48 Reels au plus
# 22/10 (Gaëtan : « les vues d'un Reel montent pendant 45 jours ») : une fois par jour (1er passage, heure de Paris), la relecture
# remonte à 45 jours pour mettre à jour les vues des Reels plus anciens ; les deux autres passages restent à 15 jours.
FENETRE_LONGUE_J = int(os.environ.get("RAPIDAPI_FENETRE_LONGUE_J", "45") or 45)
PAGES_LONGUE = int(os.environ.get("RAPIDAPI_PAGES_LONGUE", "12") or 12)
GARDE_REELS_J = int(os.environ.get("RAPIDAPI_GARDE_J", "180") or 180)   # Reels des clippers gardés en mémoire (archive 180 j)
# 22/10 (Gaëtan : « un gros backup des 90, 180 derniers jours ») : rattrapage lancé une fois (workflow, champ « rattrapage_jours »),
# repris de passage en passage jusqu'à ce que chaque compte ait été relu sur RATTRAPAGE_J jours, puis le suivi léger reprend.
RATTRAPAGE_J = int(os.environ.get("RAPIDAPI_RATTRAPAGE_J", "0") or 0)
PAGES_RATTRAPAGE = int(os.environ.get("RAPIDAPI_PAGES_RATTRAPAGE", "60") or 60)   # 12 Reels par page : 720 Reels au plus
BUDGET_MIN = float(os.environ.get("SUIVI_BUDGET_MIN", "0") or 0)       # durée max d'un passage (0 : sans limite)
ESSAIS = 2                                                              # 1 nouvel essai sur 429, 5xx ou délai dépassé
PAUSE = float(os.environ.get("RAPIDAPI_PAUSE", "0.4") or 0.4)
ACTIF = os.environ.get("RAPIDAPI_SUIVI", "1").strip() != "0"
ONGLET_COMPTES, ONGLET_REELS, ONGLET_TOP = "IG · Comptes", "IG · Reels", "IG · Top Reels"
ONGLET_ARCHIVE, ONGLET_PASSAGES = "IG · Archive Reels", "IG · Passages"
ENTETE_PASSAGES = ["Début (UTC)", "Durée (min)", "Comptes", "Profils relus", "Reels relus", "Pages lues", "Pages en échec",
                   "Requêtes", "Quota restant", "Rattrapage", "Arrêt", "Fenêtre relue",
                   "Page pleine sans suite (pagination)", "Comptes relus par leurs publications",
                   "Metricool (Reels officiels)"]
ENTETE_COMPTES = ["Créatrice", "Gérant", "Type", "@", "ID Instagram", "Statut", "Followers", "Δ 24 h", "Δ 7 j", "Publications",
                  "Reels 24 h", "Reels 7 j", "Reels 15 j", "Reels 30 j", "Reels 60 j", "Vues 7 j", "Vues 15 j", "Vues 30 j",
                  "Vues 60 j", "Dernier Reel", "Profil relu le", "Reels relus le", "Renommé en"]
ENTETE_REELS = ["Créatrice", "Gérant", "Type", "@", "Code", "Lien", "Publié le", "Vues", "Likes", "Commentaires", "Relu le"]
ENTETE_TOP = ["Créatrice", "Rang", "@", "Lien", "Publié le", "Vues", "Likes", "Commentaires"]
ETATS_VIVANTS = ("good", "prive", "privé", "private")

_deps = {}
_jour = {"jour": "", "n": 0, "restant": None}
_diag = {"pages": 0, "echecs": {}, "sans_suite": {}}                                      # pages de Reels lues et refusées (code → nombre) par passage
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
        return None if v is None or v == "" or isinstance(v, bool) else int(float(v))   # 0 reste 0 (0 == False en Python)
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


def est_video(m: dict) -> bool:
    """Un média du fil est un Reel (vidéo) : media_type 2, product_type clips, ou un compteur de lectures."""
    return (str(m.get("media_type")) == "2" or m.get("product_type") in ("clips", "igtv") or m.get("is_video") is True
            or any(m.get(k) not in (None, "") for k in ("play_count", "ig_play_count", "video_view_count", "view_count")))


def lire_reels(corps, videos_seules: bool = False) -> tuple:
    """Réponse de /reels (ou des publications, `videos_seules`) → ([{code, publie (ISO), vues, likes, commentaires}], curseur)."""
    vus, reels = set(), []
    for m in _medias(corps):
        if videos_seules and not est_video(m):
            continue
        code = str(m.get("code") or m.get("shortcode"))
        quand = _instant(m.get("taken_at") or m.get("taken_at_timestamp") or m.get("device_timestamp"))
        if code in vus or quand is None:
            continue
        vus.add(code)
        # ig_play_count d'abord : play_count additionne les lectures Facebook quand le Reel y est repartagé (relevé du 22/10 :
        # 2 038 380 en play_count pour 96 062 lectures Instagram). Seules les vues Instagram amènent au lien en bio.
        vues = m.get("ig_play_count")
        if vues in (None, ""):
            vues = m.get("play_count") or m.get("view_count") or m.get("video_view_count") or m.get("video_play_count")
        reels.append({"code": code, "publie": quand.isoformat(timespec="seconds"), "vues": _entier(vues),
                      "epingle": bool(m.get("clips_tab_pinned_user_ids") or m.get("timeline_pinned_user_ids")),
                      "likes": _entier(m.get("like_count") or (m.get("edge_liked_by") or {}).get("count")),
                      "commentaires": _entier(m.get("comment_count") or (m.get("edge_media_to_comment") or {}).get("count"))})
    plus = chercher(corps, ["paging_info.more_available", "more_available", "has_next_page", "page_info.has_next_page"])
    curseur = chercher(corps, ["paging_info.max_id", "next_max_id", "max_id", "end_cursor", "page_info.end_cursor"])
    return reels, (str(curseur) if curseur and plus is not False else None)


# ------------------------------------------------------------------ calculs (pur, testé)
def plus_ancien(reels: list):
    """Date du Reel le plus ancien d'une page, Reels épinglés exclus (ils sont en tête, souvent vieux de plusieurs mois :
    les compter arrêterait la reprise d'historique dès la première page). Page faite d'épinglés seulement : on continue."""
    dates = [_instant(r["publie"]) for r in reels or [] if not r.get("epingle") and _instant(r.get("publie"))]
    return min(dates) if dates else datetime.max.replace(tzinfo=timezone.utc)


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
                    f["dernier"], e.get("profil_le") or "", e.get("reels_le") or "", e.get("renomme_en") or ""])
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


def lignes_top(suivis: list, store: dict, n: int = 20, maintenant: datetime = None, jours: int = 365) -> list:
    """Les n meilleurs Reels (vues Instagram) des comptes de chaque créatrice publiés sur les `jours` derniers jours
    (sans `maintenant` : toutes dates gardées). Un vieux Reel épinglé n'entre donc pas dans le top de l'année."""
    par_creatrice = {}
    for s in suivis:
        if s["type"] != "Créatrice":
            continue
        for code, r in ((store.get("reels") or {}).get(s["handle"]) or {}).items():
            quand = _instant(r.get("publie"))
            if maintenant is not None and (quand is None or maintenant - quand > timedelta(days=jours)):
                continue
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
        if r.get("epingle"):
            e["epingle"] = True
        else:
            e.pop("epingle", None)
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
    """(code HTTP, corps JSON ou texte). Compte la requête et retient le quota restant annoncé par RapidAPI.
    Un 429, un 5xx ou un délai dépassé est retenté une fois ; une erreur réseau rend (0, message), jamais d'exception."""
    code, corps = 0, None
    for essai in range(ESSAIS):
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
                code = r.status
                await _echantillon(chemin, params, r.status, texte)
        except Exception as erreur:                                     # noqa: BLE001 — délai, coupure réseau
            code, corps = 0, f"{type(erreur).__name__}: {str(erreur)[:200]}"
        finally:
            await asyncio.sleep(PAUSE)
        if code not in (0, 429, 500, 502, 503, 504):
            break
        await asyncio.sleep(3 * (essai + 1))
    return code, corps


def _debut_et_fin(texte: str, taille: int = 45000) -> str:
    """Pur : le corps compacté, tronqué au milieu (début + 6 000 derniers caractères) pour que le curseur de pagination,
    en fin de réponse, reste visible dans la cellule."""
    try:
        texte = json.dumps(json.loads(texte), ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        texte = str(texte or "")
    if len(texte) <= taille:
        return texte
    return texte[:taille - 6100] + f" … [{len(texte)} caractères, milieu coupé] … " + texte[-6000:]


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
                                          _debut_et_fin(texte), quand]])
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Échantillon RapidAPI non écrit : %s", type(erreur).__name__)


def migrer_par_id(store: dict, handle: str, i: str) -> str:
    """Pur (sur le store) : 22/10 (Gaëtan : « quand ils changent le @, on perd le suivi ») : le compte est suivi par son ID
    Instagram. Quand le @ du LOG change et que le nouveau @ porte l'ID d'un compte déjà suivi, son historique (followers, Reels,
    reprises faites) passe au nouveau @. Renvoie l'ancien @ repris, ou ''."""
    comptes = store.setdefault("comptes", {})
    for ancien, e in list(comptes.items()):
        if ancien == handle or str(e.get("id") or "") != str(i):
            continue
        neuf = comptes.setdefault(handle, {})
        for k, v in e.items():
            if k == "suivi":
                neuf["suivi"] = sorted((v or []) + (neuf.get("suivi") or []), key=lambda x: x[0])[-200:]
            elif k not in neuf or k in ("historique_v2", "rattrapage_j"):
                neuf.setdefault(k, v)
        neuf.pop("renomme_en", None)
        reels = store.setdefault("reels", {})
        if ancien in reels:
            reels[handle] = {**reels.pop(ancien), **(reels.get(handle) or {})}
        comptes.pop(ancien, None)
        return ancien
    return ""


async def identifiant(session, store: dict, handle: str):
    """L'ID Instagram du compte (mémorisé) ; None si introuvable ou si l'API ne répond pas."""
    e = (store.setdefault("comptes", {})).setdefault(handle, {})
    if e.get("id"):
        return e["id"]
    chemin, params = API["id"]
    code, corps = await appeler(session, chemin, params(handle))
    i = lire_id(corps) if code == 200 else None
    if i:
        e["id"] = i
        migrer_par_id(store, handle, i)
    elif introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False):
        e["statut"] = "introuvable"
    return i


async def relire_profil(session, store: dict, handle: str, maintenant: datetime) -> bool:
    e = store.setdefault("comptes", {}).setdefault(handle, {})
    i = await identifiant(session, store, handle)
    if not i:
        if e.get("statut") == "introuvable":
            e["profil_le"] = maintenant.isoformat(timespec="seconds")
        return False
    chemin, params = API["profil"]
    code, corps = await appeler(session, chemin, params(i))
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


async def relire_reels(session, store: dict, handle: str, maintenant: datetime, jusqu_a=None, pages: int = 1, route: str = "reels") -> list:
    """Reels du compte (pages successives jusqu'à la date `jusqu_a` ou `pages` pages) ; [] si rien n'a pu être lu.
    route « posts » : les publications du compte (route découverte, voir decouvrir_route_posts), vidéos seulement."""
    i = await identifiant(session, store, handle)
    if not i:
        return []
    rp = (store.get("etat") or {}).get("route_posts") or {}
    if route == "posts" and not rp.get("chemin"):
        return []
    tous, curseur, lu, fin_api = [], None, False, False
    for _ in range(max(1, pages)):
        if route == "posts":
            chemin = rp["chemin"]
            forme = rp.get("forme") or "id_user"
            params = {forme: i if forme == "id_user" else handle, **({rp.get("param") or "max_id": curseur} if curseur else {})}
        else:
            chemin, fabrique = API["reels"]
            params = fabrique(i, curseur, 12 if pages == 1 else 50)
        code, corps = await appeler(session, chemin, params)
        if code != 200:
            cle = str(code or "réseau")
            _diag["echecs"][cle] = _diag["echecs"].get(cle, 0) + 1
            journal.info("Reels de %s : page refusée (%s) %s", handle, cle, str(corps)[:160])
            break
        lu = True
        _diag["pages"] += 1
        reels, curseur = lire_reels(corps, videos_seules=(route == "posts"))
        if not curseur and len(reels) >= 12 and isinstance(corps, dict):
            # 22/10 : des comptes très actifs s'arrêtaient à 12 Reels sans page refusée : l'API ne donne pas de page suivante.
            _diag["sans_suite"][handle] = {"route": route, "cles": sorted(corps.keys())[:12], "paging": corps.get("paging_info"),
                                           "plus": corps.get("more_available"), "suivant": corps.get("next_max_id")}
        tous += reels
        if not curseur:
            fin_api = True
            store.setdefault("comptes", {}).setdefault(handle, {})["fin_pleine"] = len(reels) >= 12
        if not curseur or (not reels and route == "reels") or (jusqu_a and reels and plus_ancien(reels) < jusqu_a) or not _quota_ok(RESERVE):
            break
    store.setdefault("comptes", {}).setdefault(handle, {})["fin_api"] = fin_api
    e = store.setdefault("comptes", {}).setdefault(handle, {})
    if lu:
        store.setdefault("reels", {})[handle] = fusionner_reels(store.get("reels", {}).get(handle), tous, maintenant)
        e["reels_le"] = maintenant.isoformat(timespec="seconds")
    return tous


def sous_compte(e: dict, reels_compte: dict, maintenant: datetime = None) -> bool:
    """Pur : la route Reels s'est arrêtée d'elle-même (sans page suivante) et le relevé a l'air incomplet : on passe ce compte
    sur la route des publications. Trois signes (un seul suffit) : nettement moins de Reels que de publications ; une page pleine
    sans suite ; un compte très actif (10 Reels ou plus) dont aucun Reel n'a plus de 3 semaines (le nombre de publications
    annoncé par l'API est parfois faux : 1 pour un compte qui a 14 Reels)."""
    if not e.get("fin_api") or e.get("statut") == "privé":
        return False
    maintenant = maintenant or datetime.now(timezone.utc)
    suivi = e.get("suivi") or []
    pubs = suivi[-1][2] if suivi and len(suivi[-1]) > 2 and suivi[-1][2] is not None else None
    n = len(reels_compte or {})
    if pubs is not None and pubs >= 20 and n < pubs * 0.5:
        return True
    if e.get("fin_pleine"):
        return True
    dates = [d for d in (_instant(r.get("publie")) for r in (reels_compte or {}).values()) if d]
    return n >= 10 and bool(dates) and min(dates) > maintenant - timedelta(days=21)


async def _essai_route(session, chemin: str, params: dict, essais: int = 3) -> tuple:
    """(code, corps) d'un chemin candidat ; une erreur passagère (5xx, « Temporary upstream error ») est réessayée."""
    code, corps = 0, None
    for k in range(essais):
        code, corps = await appeler(session, chemin, params)
        if code not in (0, 429, 500, 502, 503, 504):
            break
        await asyncio.sleep(5 * (k + 1))
    return code, corps


async def decouvrir_route_posts(session, store: dict, i: str, handle: str = "", temoin: tuple = None) -> dict:
    """Trouve la route des publications : chemins candidats × formes de paramètre (ID ou @), sur le compte visé puis, s'il ne
    répond pas, sur un compte témoin qui marche (`temoin` = (ID, @)). Garde le premier qui renvoie des médias et le nom du
    paramètre de page suivante. Mémorisé dans store['etat']['route_posts'] ; {'aucune': date} seulement si tous les chemins
    répondent « n'existe pas » (réessai à 7 jours) ; une erreur passagère est retentée au passage suivant."""
    etat = store.setdefault("etat", {})
    rp = etat.get("route_posts") or {}
    if rp.get("chemin"):
        return rp
    if rp.get("aucune2"):
        try:
            if datetime.now(timezone.utc) - datetime.fromisoformat(rp["aucune2"]) < timedelta(days=7):
                return rp
        except (ValueError, TypeError):
            pass
    cibles = [(i, handle)] + ([temoin] if temoin and temoin[0] and str(temoin[0]) != str(i) else [])
    passager = False
    for chemin in API.get("posts_candidats") or []:
        for (ci, ch) in cibles:
            for forme in ("id_user", "user"):
                if not _quota_ok(RESERVE):
                    return rp
                valeur = ci if forme == "id_user" else ch
                if not valeur:
                    continue
                code, corps = await _essai_route(session, chemin, {forme: valeur})
                if code == 404 and introuvable(code, corps) and "does not exist" in str(corps):
                    break                                                    # le chemin n'existe pas : candidat suivant
                if code != 200:
                    passager = passager or code in (0, 429, 500, 502, 503, 504)
                    continue
                p1, cur = lire_reels(corps)
                if not p1 and not _medias(corps):
                    continue
                trouve = {"chemin": chemin, "forme": forme, "param": None, "trouve_le": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                if cur:
                    codes1 = {r["code"] for r in p1}
                    for param in ("max_id", "end_cursor", "next_max_id", "cursor"):
                        c2, corps2 = await _essai_route(session, chemin, {forme: valeur, param: cur})
                        p2, _ = lire_reels(corps2) if c2 == 200 else ([], None)
                        if p2 and not {r["code"] for r in p2} <= codes1:
                            trouve["param"] = param
                            break
                etat["route_posts"] = trouve
                journal.info("Route des publications trouvée : %s ?%s= (page suivante : %s)", chemin, forme, trouve["param"])
                return trouve
            else:
                continue
            break
    if passager:
        etat["route_posts"] = {"passager": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        journal.warning("Route des publications : erreurs passagères, réessai au passage suivant")
    else:
        etat["route_posts"] = {"aucune2": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        journal.warning("Aucune route des publications ne répond parmi %s", API.get("posts_candidats"))
    return etat["route_posts"]


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
def a_rattraper(e: dict, jours: int) -> bool:
    """Pur : le compte n'a pas encore été relu sur `jours` jours (rattrapage en cours)."""
    return bool(jours) and int(e.get("rattrapage_j") or 0) < jours


def metricool_texte(b) -> str:
    """Pur : le bilan Metricool en une phrase pour le journal des passages."""
    if not isinstance(b, dict):
        return ""
    if b.get("erreur"):
        return "erreur : " + b["erreur"]
    morceaux = [f"{b.get('ajoutes', 0)} Reel(s) ajouté(s)", f"{b.get('importes', 0)} lu(s) dans l'onglet"]
    if b.get("rest"):
        morceaux.append("API : " + b["rest"])
    if b.get("erreurs"):
        morceaux.append("erreurs : " + " ; ".join(b["erreurs"])[:300])
    return " · ".join(morceaux)


def route_posts_texte(store: dict, comptes: list) -> str:
    """Pur : l'état de la route de secours (publications) pour le journal des passages."""
    rp = (store.get("etat") or {}).get("route_posts") or {}
    if rp.get("aucune2"):
        return "aucune route des publications ne répond (réessai dans 7 jours)"
    if rp.get("passager"):
        return "route des publications : erreur passagère de l'API, réessai au passage suivant"
    if not rp.get("chemin"):
        return ""
    hs = sorted(c["handle"] for c in comptes if ((store.get("comptes") or {}).get(c["handle"]) or {}).get("route") == "posts")
    return f"{rp['chemin']} (page suivante : {rp.get('param') or 'aucune'}) : {len(hs)} compte(s) : " + ", ".join(hs)


def lignes_passages(passages: list) -> list:
    """Pur : historique des passages (le plus récent en haut)."""
    out = []
    for b in reversed(passages or []):
        ech = b.get("echecs") or {}
        out.append([b.get("debut", ""), str(b.get("duree_min", "")), str(b.get("comptes", "")), str(b.get("profils", "")),
                    str(b.get("reels", "")), str(b.get("pages", "")), " · ".join(f"{k} : {v}" for k, v in sorted(ech.items())) or "0",
                    str(b.get("requetes", "")), "" if b.get("quota_restant") is None else str(b["quota_restant"]),
                    b.get("rattrapage", ""), b.get("arret", ""), b.get("fenetre", ""),
                    " ; ".join(f"{h} {json.dumps(v, ensure_ascii=False)[:160]}" for h, v in (b.get("sans_suite") or {}).items())[:4000],
                    b.get("route_posts", ""), b.get("metricool", "")])
    return out


async def passage_complet(session) -> dict:
    import onboarding
    import pilotage
    t0 = time.monotonic()
    comptes = comptes_a_suivre(await onboarding.lire_comptes())
    store = _store()
    maintenant = datetime.now(timezone.utc)
    etat = store.setdefault("etat", {})
    if RATTRAPAGE_J and int((etat.get("rattrapage") or {}).get("jours") or 0) != RATTRAPAGE_J:
        etat["rattrapage"] = {"jours": RATTRAPAGE_J, "depuis": maintenant.isoformat(timespec="seconds")}
    jours_r = int((etat.get("rattrapage") or {}).get("jours") or 0)
    jour_paris = _paris(maintenant).date().isoformat()
    longue = bool(FENETRE_LONGUE_J) and etat.get("fenetre_longue_le") != jour_paris
    fenetre_j, fenetre_p = (FENETRE_LONGUE_J, PAGES_LONGUE) if longue else (FENETRE_RELUE_J, PAGES_FENETRE)
    _diag.update({"pages": 0, "echecs": {}, "sans_suite": {}})
    n0 = _jour["n"]
    # comptes déjà rattrapés d'abord (suivi léger garanti), le rattrapage remplit le temps qui reste
    comptes_ordre = sorted(comptes, key=lambda c: a_rattraper((store.get("comptes") or {}).get(c["handle"]) or {}, jours_r))
    bilan = {"comptes": len(comptes), "profils": 0, "reels": 0, "arret_quota": False, "arret_temps": False}
    for k, s in enumerate(comptes_ordre, start=1):
        if not _quota_ok(RESERVE):
            bilan["arret_quota"] = True
            break
        if BUDGET_MIN and time.monotonic() - t0 > BUDGET_MIN * 60:
            bilan["arret_temps"] = True
            break
        h = s["handle"]
        if await relire_profil(session, store, h, maintenant):
            bilan["profils"] += 1
        e = store["comptes"].get(h) or {}
        if e.get("statut") == "introuvable":
            continue
        rattrapage = a_rattraper(e, jours_r)
        # historique_v2 : le 1er passage (22/10) s'arrêtait page 1 sur les Reels épinglés ; la reprise est refaite une fois.
        historique = s["type"] == "Créatrice" and not e.get("historique_v2")
        if historique or rattrapage:
            jours = max(HISTORIQUE_CREATRICE_J if historique else 0, jours_r if rattrapage else 0)
            pages = max(PAGES_HISTORIQUE if historique else 0, PAGES_RATTRAPAGE if rattrapage else 0)
        else:
            jours, pages = fenetre_j, fenetre_p
        depuis = maintenant - timedelta(days=jours)
        route = "posts" if e.get("route") == "posts" and ((etat.get("route_posts") or {}).get("chemin")) else "reels"
        reels = await relire_reels(session, store, h, maintenant, jusqu_a=depuis, pages=pages, route=route)
        if route == "posts" and e.get("reels_le") != maintenant.isoformat(timespec="seconds"):
            # la route des publications n'a pas répondu pour ce compte : la route Reels, même incomplète, garde les nouveautés
            reels = await relire_reels(session, store, h, maintenant, jusqu_a=depuis, pages=pages, route="reels")
        if route == "reels" and sous_compte(e, (store.get("reels") or {}).get(h), maintenant) and _quota_ok(RESERVE):
            temoin = next(((x.get("id"), hx) for hx, x in (store.get("comptes") or {}).items()
                           if x.get("id") and not x.get("fin_api") and x.get("statut") == "public" and hx != h), None)
            rp = await decouvrir_route_posts(session, store, e.get("id"), h, temoin)
            if rp.get("chemin"):
                plus = await relire_reels(session, store, h, maintenant, jusqu_a=maintenant - timedelta(days=max(jours, GARDE_REELS_J)),
                                          pages=max(pages, PAGES_RATTRAPAGE), route="posts")
                if plus:
                    e["route"] = "posts"                                   # ce compte passe sur les publications, pour de bon
                    bilan["routes_posts"] = bilan.get("routes_posts", 0) + 1
                    reels = reels + plus
        if reels:
            bilan["reels"] += 1
            if historique:
                e["historique_v2"] = maintenant.isoformat(timespec="seconds")
            if rattrapage and _quota_ok(RESERVE):
                e["rattrapage_j"] = jours_r
        elif rattrapage and e.get("reels_le") == maintenant.isoformat(timespec="seconds"):
            e["rattrapage_j"] = jours_r                                    # compte lu mais sans aucun Reel : rien à rattraper
        if s["type"] != "Créatrice":                                     # mémoire bornée pour les clippers
            limite = maintenant - timedelta(days=max(GARDE_REELS_J, jours_r))
            store["reels"][h] = {c: r for c, r in (store["reels"].get(h) or {}).items() if (_instant(r.get("publie")) or maintenant) >= limite}
        if k % 10 == 0:
            _sauver(store)
    # 22/10 : Reels des comptes branchés à Metricool (source officielle ; l'API RapidAPI en voit une partie seulement)
    try:
        import metricool_reels
        bilan["metricool"] = await metricool_reels.passage(store, comptes, maintenant, longue)
    except Exception as erreur:                                         # noqa: BLE001
        bilan["metricool"] = {"erreur": str(erreur)[:160]}
    restants = sum(1 for c in comptes if a_rattraper((store.get("comptes") or {}).get(c["handle"]) or {}, jours_r)
                   and ((store.get("comptes") or {}).get(c["handle"]) or {}).get("statut") != "introuvable")
    if longue and not (bilan["arret_quota"] or bilan["arret_temps"]):
        etat["fenetre_longue_le"] = jour_paris
    if jours_r and not restants:
        etat["dernier_rattrapage"] = {**etat.pop("rattrapage", {}), "fini": maintenant.isoformat(timespec="seconds")}
    bilan.update({"pages": _diag["pages"], "echecs": dict(_diag["echecs"]), "requetes": _jour["n"] - n0, "quota_restant": _jour["restant"],
                  "rattrapage_restants": restants if jours_r else 0})
    etat.setdefault("passages", []).append({
        "debut": maintenant.isoformat(timespec="minutes"), "duree_min": round((time.monotonic() - t0) / 60, 1), "comptes": len(comptes),
        "profils": bilan["profils"], "reels": bilan["reels"], "pages": _diag["pages"], "echecs": dict(_diag["echecs"]),
        "requetes": bilan["requetes"], "quota_restant": _jour["restant"],
        "rattrapage": (f"{jours_r} j : {restants} compte(s) restant(s)" if restants else f"{jours_r} j : fini") if jours_r else "",
        "arret": "quota" if bilan["arret_quota"] else "temps" if bilan["arret_temps"] else "", "fenetre": f"{fenetre_j} j", "sans_suite": dict(_diag["sans_suite"]),
        "route_posts": route_posts_texte(store, comptes), "metricool": metricool_texte(bilan.get("metricool"))})
    etat["passages"] = etat["passages"][-90:]
    _sauver(store)
    try:
        import paie_clics
        classeur = await paie_clics._classeur_usage()
        if classeur:
            await pilotage._ecrire(classeur, ONGLET_COMPTES, ENTETE_COMPTES, lignes_comptes(comptes, store, maintenant))
            await pilotage._ecrire(classeur, ONGLET_REELS, ENTETE_REELS, lignes_reels(comptes, store, maintenant))
            await pilotage._ecrire(classeur, ONGLET_TOP, ENTETE_TOP, lignes_top(comptes, store, maintenant=maintenant))
            await pilotage._ecrire(classeur, ONGLET_ARCHIVE, ENTETE_REELS, lignes_reels(comptes, store, maintenant, jours=max(GARDE_REELS_J, jours_r)))
            await pilotage._ecrire(classeur, ONGLET_PASSAGES, ENTETE_PASSAGES, lignes_passages(etat["passages"]))
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
