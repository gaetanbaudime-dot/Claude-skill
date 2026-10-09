"""États des comptes du classeur (26/09, demande de Gaëtan : « mettre à jour constamment l'état des comptes sur le sheet »).

Chaque jour, le bot regarde Instagram (Apify) pour les comptes du classeur qui ont un Gérant, et met à jour la colonne
ETAT de l'onglet Instagram, une cellule à la fois, jamais la structure :
  à créer → WARMUP   dès que le compte existe sur Instagram
  WARMUP  → GOOD     quand il a publié GOOD_JOURS jours de suite (au moins une publication par jour)
  WARMUP  → PRIVE    quand le compte est passé en privé (le 3e compte du trio)
  WARMUP / GOOD / PRIVE → BAN   quand Instagram ne le trouve plus BAN_JOURS jours de suite (posé par le bot, annulé s'il revient)
  BAN → son état d'avant (sinon GOOD s'il a déjà publié, sinon WARMUP)  dès que le compte est vivant sur Instagram
       (30/09, Gaëtan : « tous les comptes GOOD, BAN et WARMUP, vérifie-les à chaque fois », BAN posé à la main compris)
  restreint (profil caché aux visiteurs non connectés) = vivant, jamais BAN
`!dashboard` lance ce passage complet avant de réécrire l'onglet (30/09) ; `!dashboard rapide` réécrit sans scan.
Les états posés à la main (PERDU LOGS, à vérifier, BIZARRE, ACTIF…) ne sont jamais touchés, ni une ligne « à créer » sans Gérant :
un compte du vivier libre ne peut pas se créer tout seul. La colonne Followers est remplie pour TOUS les comptes créés du
classeur (26/09, « légendaire ») : clippers, créatrices sous Metricool, comptes libérés — pas les lignes « à créer » sans gérant.
05/10 (Gaëtan : « pour CHAQUE ligne ayant un @, tous les états sauf à créer, le classeur tenu à jour chaque jour ») :
  - l'ETAT suit toute ligne créée (Gérant ou pas, Utilisation quelle qu'elle soit) ; un BAN sans Gérant n'est jamais ressuscité ;
  - Followers, « Reels Hier », « Reels 7 j » (Reels = vidéos, jour civil de Paris, tirés des latestPosts d'Apify — 12 publications
    au plus, complétés par l'historique du scan) sont écrits pour chaque compte lisible ; un restreint ou un privé cache ses Reels ;
  - un compte ABSENT de la réponse d'Apify (après la deuxième demande) ou renvoyé sans chiffres est « non lu » : rien n'est écrit,
    il garde son état et ses valeurs ; seul un « introuvable » explicite d'Apify compte comme absence (→ BAN). Au bout de
    NON_LU_JOURS passages non lus de suite, le compte est traité comme absent. Plus de la moitié non lue = Apify en panne, rien changé ;
  - les identifiants sont nettoyés (onboarding.normaliser_handle : @, URL, espaces, casse) avant d'être envoyés et comparés.
Le module ne connaît pas bot_discord : dépendances dans `configurer(deps)` (lire_json, ecrire_json, FICHIER_ETATS,
normaliser, canal_admin, notifier, est_staff ; `scanner` optionnel pour les tests)."""
import asyncio
import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

import aiohttp

import google_api
import onboarding

journal = logging.getLogger("etats_comptes")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR_IG = os.environ.get("APIFY_ACTOR_IG", "apify~instagram-profile-scraper").strip()
ACTIF = (os.environ.get("ETATS_CLASSEUR", "1").strip() or "1") != "0"
GOOD_JOURS = int(os.environ.get("ETATS_GOOD_JOURS", "3") or 3)         # jours de publication de suite pour GOOD
BAN_JOURS = int(os.environ.get("ETATS_BAN_JOURS", "1") or 1)           # 28/09 (Gaëtan) : plus lisible = BAN par défaut, dès le premier scan
HEURE_UTC = int(os.environ.get("ETATS_HEURE_UTC", "7") or 7)           # après le rapport inputs du matin
# 08/10 (GO n° 2 du checkup) : un 2e passage, le soir (heure de Paris), sur les seuls comptes dont les Reels ouvrent un compte en
# attente ; il n'écrit ni le classeur ni l'historique (un passage par jour), il donne au parcours les Reels publiés depuis le matin.
SOIR_HEURE = int(os.environ.get("ETATS_SOIR_HEURE", "19") or 19)                # -1 pour l'éteindre
JOURS_HISTORIQUE = 14
SUIVIS = ("a creer", "à créer", "warmup", "good", "prive", "privé", "ban")
VERSION = 6                       # 05/10 : passage forcé au déploiement pour remplir Reels 7 j / Clics hier et suivre toutes les lignes créées
NON_LU_JOURS = int(os.environ.get("ETATS_NON_LU_JOURS", "3") or 3)   # 05/10 : passages non lus de suite avant de traiter le compte comme absent
A_CREER = ("a creer", "à créer")
GERANTS_LIBRES = ("", "x", "y", "z")                                     # la ligne n'a pas de clipper
DASHBOARD_VERSION = 9             # 05/10 : ligne « Créatrice » en tête de bloc ; changée → réécrit au démarrage, sans scan (Clics relevés avant)
EXCLUS_DEFAUT = [m.strip() for m in os.environ.get("DASHBOARD_EXCLUS", "Rianah").split(",") if m.strip()]
# 09/10 (Gaëtan : « Julien arrête tout, il va juste faire le monteur vidéo maintenant pour moi ») : l'ancien Julien sort du clipping
# (`!monteur`, ses lignes « Julien » du classeur rendues) et un nouveau Julien clipper est signé. « Julien » n'est plus tenu hors de
# la vérification ni du rapport (sinon les comptes du nouveau n'y passeraient jamais), y compris dans la liste d'état d'avant le 30/09.
# Ses lignes « Julien (Metricool) » restent hors clipping : un Gérant « … (Metricool) » n'est jamais compté comme un clipper.
REINTEGRES = {"julien"}
# 30/09 (Gaëtan : « inclus Julien et Rianah dans le dashboard aussi ») : le Dashboard ne masque plus personne par défaut.
# La liste « hors clipping » ci-dessus ne sert plus qu'à la vérification du classeur et au rapport du jour (Rianah gère les
# comptes de tout le monde : sans elle, le plafond de trois comptes la signalerait chaque matin).
MASQUES_DEFAUT = [m.strip() for m in os.environ.get("DASHBOARD_MASQUES", "").split(",") if m.strip()]


def dashboard_exclus(d=None) -> list:
    """Les prénoms tenus hors du Dashboard (28/09, Gaëtan : « Julien et Rianah, on va les exclure totalement du clipping ») :
    la liste de l'état (ancienne clé, plus modifiée depuis le 30/09), sinon DASHBOARD_EXCLUS. Sert à la vérification du
    classeur et au rapport du jour, plus au Dashboard (voir dashboard_masques)."""
    d = d if d is not None else _lire()
    liste = list(d["dashboard_exclus"]) if isinstance(d.get("dashboard_exclus"), list) else list(EXCLUS_DEFAUT)
    return [x for x in liste if _norm(str(x)).strip() not in REINTEGRES]


def dashboard_masques(d=None) -> list:
    """Les Gérants masqués du seul onglet Dashboard : `!dashboard exclure Prénom` / `!dashboard inclure Prénom`, sinon
    DASHBOARD_MASQUES (vide)."""
    d = d if d is not None else _lire()
    return list(d["dashboard_masques"]) if isinstance(d.get("dashboard_masques"), list) else list(MASQUES_DEFAUT)
LOT = 50                                                               # comptes par appel Apify

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    return ACTIF and bool(APIFY_TOKEN) and onboarding.actif()


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _cle(handle: str) -> str:
    """05/10 : la clé d'un compte partout dans ce module (historique, mesures, Apify) : identifiant nettoyé (sans @, sans URL,
    sans espace) en minuscules. Avant, un « @ » ou une URL dans la cellule partait tel quel chez Apify : compte « introuvable »."""
    return onboarding.normaliser_handle(handle).lower()


_PARIS = None


def _paris(quand: datetime) -> datetime:
    """L'heure de Paris (repli UTC+2 si la base de fuseaux manque sur le conteneur, comme bot_discord.heure_paris)."""
    global _PARIS
    if _PARIS is None:
        try:
            from zoneinfo import ZoneInfo
            _PARIS = ZoneInfo("Europe/Paris")
        except Exception:                                                # noqa: BLE001
            _PARIS = timezone(timedelta(hours=2))
    return quand.astimezone(_PARIS)


def _est_reel(post: dict) -> bool:
    """Une publication est un Reel si Apify la dit vidéo (type Video, productType clips/reels/igtv) ; sans type, on compte."""
    t = str(post.get("type") or "").lower()
    pt = str(post.get("productType") or "").lower()
    return t == "video" or pt in ("clips", "reels", "igtv") or (not t and not pt)


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_ETATS"], {})
    d.setdefault("historique", {}); d.setdefault("bans_auto", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_ETATS"], d)


# ------------------------------------------------------------------ Instagram
async def scanner(handles: list) -> dict:
    """Un appel Apify pour tous les comptes → {clé: {lu, existe, prive, restreint, followers, posts, reels_hier, reels_7j, posts_lus…}} ;
    `posts` = publications des dernières 24 h (compatibilité : message du matin, parcours, sortie auto), `reels_hier` / `reels_7j` =
    Reels (vidéos) de la veille et des 7 derniers jours en jour civil de Paris. None si Apify est en panne : on ne conclut rien.
    05/10 : `lu` = Apify a répondu pour ce compte (fiche, ou erreur explicite « introuvable »). Un compte absent de la réponse après
    la deuxième demande, ou renvoyé sans aucun chiffre (mur de connexion, page incomplète), est `lu: False` : l'appelant n'en conclut
    rien et n'écrit rien. `existe: False` avec `lu: True` = Apify a bien dit que le compte n'existe pas (banni, renommé, jamais créé)."""
    if _deps.get("scanner"):
        return await _deps["scanner"](handles)
    if not APIFY_TOKEN or not handles:
        return None
    cles = []
    for h in handles:                                                    # 05/10 : identifiants nettoyés, sans doublon
        k = _cle(h)
        if k and k not in cles:
            cles.append(k)
    items = await _apify(cles)
    if items is None:
        return None
    # 30/09 : un compte absent de la réponse d'Apify n'est pas forcément mort (profil sauté par le robot) : les absents sont
    # redemandés une fois, à part, avant de conclure
    vus = {_handle_item(it) for it in items}
    manquants = [h for h in cles if h not in vus]
    if manquants:
        journal.info("Apify (états) : %d compte(s) sur %d absent(s) de la première réponse, redemandés à part", len(manquants), len(cles))
        encore = await _apify(manquants)
        items += encore or []
    out = _lire_items(items, cles)
    journal.info("Apify (états) : %d demandés, %d fiches reçues, %d lus, %d introuvables (réponse explicite), %d restreints, %d non lus",
                 len(cles), len(items), sum(1 for f in out.values() if f["lu"]), sum(1 for f in out.values() if f["lu"] and not f["existe"]),
                 sum(1 for f in out.values() if f["restreint"]), sum(1 for f in out.values() if not f["lu"]))
    return out


def _handle_item(item: dict) -> str:
    """La clé du compte d'une fiche Apify : `username`, sinon le dernier segment de `inputUrl` / `url` (fiches d'erreur)."""
    u = item.get("username")
    if not u:
        brut = str(item.get("inputUrl") or item.get("url") or "")
        u = brut.split("?")[0].split("#")[0].rstrip("/").split("/")[-1]
    return _cle(str(u))


async def _apify(handles: list):
    """Les fiches Apify brutes de `handles`, par lots ; None si Apify est en panne."""
    url = f"https://api.apify.com/v2/acts/{ACTOR_IG}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    items = []
    for i in range(0, len(handles), LOT):                              # par lots : 130 comptes tiennent en deux ou trois appels
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=280)) as session:
                async with session.post(url, json={"usernames": handles[i:i + LOT]}) as reponse:
                    if reponse.status >= 400:
                        journal.error("Apify HTTP %s (états du classeur)", reponse.status)
                        return None
                    lot = await reponse.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
            journal.error("Apify injoignable (états du classeur) : %s", erreur)
            return None
        items += lot if isinstance(lot, list) else []
    return items


def _fiche_vide() -> dict:
    return {"lu": False, "existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0, "fautes": 0,
            "reels_hier": 0, "reels_7j": 0, "posts_lus": 0, "bio_liens": [], "bio_lu": False, "lien_dans_texte": False,
            "nom": "", "bio": ""}


# 09/10 (Gaëtan : « les clippeurs peuvent changer le @ légèrement quand il n'est pas disponible ») : un compte marqué créé mais
# jamais vu vivant n'est plus passé BAN au premier passage. Le scan cherche les @ proches de celui prévu et reconnaît le compte
# du clipper au nom et à la bio que le bot lui a donnés (profil.py). Trouvé → renommé partout ; rien → le clipper est prévenu,
# BAN seulement après INTROUVABLE_JOURS passages sans le voir.
INTROUVABLE_JOURS = int(os.environ.get("ETATS_INTROUVABLE_JOURS", "3") or 3)
VARIANTES_MAX = int(os.environ.get("ETATS_VARIANTES_MAX", "12") or 12)   # comptes cherchés au plus par passage
# 09/10 (revue) : un BAN n'est cherché sous un @ proche que dans les jours qui suivent le BAN posé par le bot (un vrai BAN, vu
# vivant un jour, ne l'est jamais ; sans limite, les vieux BAN prenaient chaque jour toutes les places de la recherche).
BAN_RECHERCHE_JOURS = int(os.environ.get("ETATS_BAN_RECHERCHE_JOURS", "7") or 7)
CREES = ("warmup", "prive", "privé")                                    # créés, pas encore GOOD : le délai avant BAN les protège


def _absents_depuis(historique: list, depuis: str) -> int:
    """09/10 (revue : le délai comptait les jours où la ligne était encore « à créer ») : les passages absents de suite, en partant
    du dernier, seulement depuis le jour où la ligne a été vue créée (`depuis`, AAAA-MM-JJ)."""
    n = 0
    for j in reversed(historique or []):
        if str(j.get("jour", ""))[:10] < str(depuis or "")[:10]:
            break
        if j.get("existe") and j.get("restreint"):
            continue
        if j.get("existe"):
            break
        n += 1
    return n


def _ban_recent(d: dict, h: str, jour: str) -> bool:
    """Le BAN de ce compte a été posé par le bot il y a au plus BAN_RECHERCHE_JOURS jours."""
    pose = str((d.get("bans_auto") or {}).get(h) or "")[:10]
    try:
        return bool(pose) and (date.fromisoformat(jour) - date.fromisoformat(pose)).days <= BAN_RECHERCHE_JOURS
    except ValueError:
        return False


def variantes(h: str) -> list:
    """Les @ qu'un clipper prend quand celui prévu est pris : un chiffre, un point, un tiret bas, une lettre doublée…"""
    h = _cle(h)
    if not h:
        return []
    racine = h.rstrip("0123456789._") or h
    cands = [h + x for x in ("1", "2", "3", "_", "_1", "01", "x", "_off", ".off", "0")]
    cands += [h.replace("_", "."), h.replace(".", "_"), h.replace("_", ""), h.replace(".", ""), "_" + h, h + h[-1],
              racine + "_", racine + "1", racine + "2", racine + "_1"]
    out = []
    for v in cands:
        if v != h and v not in out and onboarding.RE_HANDLE_IG.match(v) and not v.endswith(".") and not v.startswith("."):
            out.append(v)
    return out[:16]


def _lettres(t: str) -> str:
    sans = "".join(ch for ch in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sans).strip()


def est_a_nous(m: dict, creatrice: str) -> bool:
    """Le profil trouvé est bien celui que le bot a fait préparer : jeune (peu d'abonnés) ET avec une bio de la banque de profil.py
    (lettres et chiffres comparés, emojis et ponctuation ignorés). 09/10 (revue) : le nom seul (« Sophie », « Chloé ») ne suffit
    plus — c'est le nom de milliers de comptes personnels, le scan aurait suivi le compte d'une inconnue."""
    prenom = (str(creatrice or "").split() or [""])[0]
    if not prenom or not m or not m.get("existe") or int(m.get("followers") or 0) > 3000 or not _lettres(m.get("bio")):
        return False
    try:
        import profil
        return any(_lettres(m.get("bio")) == _lettres(b.format(prenom=prenom)) for b in profil.BIOS)
    except Exception:                                                   # noqa: BLE001
        return False


async def chercher_variantes(lignes: list) -> tuple:
    """([(ligne, nouveau @)], [ligne]) : les comptes retrouvés sous un @ proche (un seul profil qui est à nous), et les introuvables."""
    cands = {id(c): variantes(c["handle"]) for c in lignes}
    tous = sorted({v for vs in cands.values() for v in vs})
    if not tous:
        return [], list(lignes)
    mesures = await scanner(tous)
    if mesures is None:
        return [], []                                                   # Apify en panne : on ne conclut rien
    trouves, perdus = [], []
    for c in lignes:
        bons = [v for v in cands[id(c)] if est_a_nous(mesures.get(v) or {}, c.get("creatrice") or "")]
        if len(bons) == 1:
            trouves.append((c, bons[0]))
        else:
            perdus.append(c)
    return trouves, perdus


RE_URL_TEXTE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(fr|com|app|link|me|io)/", re.I)


def _liens_profil(item: dict) -> tuple:
    """08/10 (critique : le lien en bio n'était jamais vérifié) : (liens cliquables du profil, champ lu, lien collé dans le texte de
    la bio). Le lien cliquable est le champ « Liens » (externalUrl / externalUrls), visible même sur un compte privé."""
    liens = [item.get("externalUrl")] + [u.get("url") for u in item.get("externalUrls") or [] if isinstance(u, dict)]
    lu = any(k in item for k in ("externalUrl", "externalUrls", "biography"))
    return [str(x) for x in liens if x], lu, bool(RE_URL_TEXTE.search(str(item.get("biography") or "")))


def _lire_items(items: list, handles: list, maintenant: datetime = None) -> dict:
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(hours=24)
    hier = _paris(maintenant).date() - timedelta(days=1)                  # 05/10 : la veille en jour civil de Paris
    debut_7j = hier - timedelta(days=6)
    out = {_cle(h): _fiche_vide() for h in handles if _cle(h)}
    for item in items:
        if not isinstance(item, dict):
            continue
        handle = _handle_item(item)
        if handle not in out or (out[handle]["lu"] and out[handle]["existe"] and not out[handle]["restreint"]):   # déjà lu en entier
            continue
        fiche = out[handle]
        erreur = str(item.get("error") or "").lower()
        restreint = bool(item.get("isRestrictedProfile") or "restricted" in erreur)
        if erreur and not restreint:
            fiche["lu"] = True                                           # not found, invalid… : Apify dit que le compte n'existe pas
            continue
        followers_brut = item.get("followersCount")
        if not restreint and not isinstance(followers_brut, (int, float)) and not item.get("latestPosts") \
                and item.get("private") is None and item.get("postsCount") is None:
            # 05/10 : une fiche sans aucun chiffre (mur de connexion, page incomplète) n'est pas « 0 followers, 0 Reel » :
            # elle est illisible, le compte reste non lu et garde ses valeurs dans le classeur
            fiche["illisible"] = True
            continue
        fiche.update({"lu": True, "existe": True, "restreint": restreint, "prive": bool(item.get("private")),
                      "followers": int(followers_brut or 0), "nom": str(item.get("fullName") or ""),
                      "bio": str(item.get("biography") or "")})
        fiche["bio_liens"], fiche["bio_lu"], fiche["lien_dans_texte"] = _liens_profil(item)
        posts = item.get("latestPosts") or []
        fiche["posts_lus"] = len(posts)
        for post in posts:
            try:
                quand = datetime.fromisoformat(str(post.get("timestamp") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if quand.tzinfo is None:
                quand = quand.replace(tzinfo=timezone.utc)
            jour_paris = _paris(quand).date()
            if _est_reel(post):
                if jour_paris == hier:
                    fiche["reels_hier"] += 1
                if debut_7j <= jour_paris <= hier:
                    fiche["reels_7j"] += 1
            if quand >= limite:
                fiche["posts"] += 1
                if not fiche.get("dernier") or str(post.get("timestamp")) > fiche["dernier"].get("quand", ""):
                    fiche["dernier"] = {"image": post.get("displayUrl") or "", "url": post.get("url") or "",   # 30/09 : premier Reel fêté
                                        "quand": str(post.get("timestamp") or "")}
                if RE_FAUTE.search(str(post.get("caption") or "")):    # 28/09 : lien ou @ dans la légende → ❌
                    fiche["fautes"] += 1
                # 01/10 (review des Reels) : ce que le scan sait déjà de chaque Reel des 24 h — URL, couverture, légende,
                # dimensions, date — gardé pour une relecture légère, sans autre appel Apify (review_reels)
                if str(post.get("type") or "Video") == "Video" or str(post.get("productType") or "") == "clips":
                    fiche.setdefault("reels", []).append({
                        "url": post.get("url") or "", "image": post.get("displayUrl") or "",
                        "legende": str(post.get("caption") or "")[:400], "quand": str(post.get("timestamp") or ""),
                        "largeur": post.get("dimensionsWidth") or 0, "hauteur": post.get("dimensionsHeight") or 0,
                        "duree": post.get("videoDuration") or 0})
        # 05/10 : 12 publications au plus dans latestPosts ; si la plus ancienne est encore dans la fenêtre des 7 jours, le
        # décompte est un minimum (complété par l'historique du scan dans reels_7j_estime)
        plus_ancien = min((str(p.get("timestamp") or "") for p in posts if p.get("timestamp")), default="")
        fiche["plafonne"] = bool(plus_ancien and plus_ancien[:10] >= debut_7j.isoformat())
    return out


def reels_7j_estime(mesure: dict, historique: list, jour: str) -> int:
    """Reels des 7 derniers jours d'un compte : le décompte des latestPosts du jour (12 publications au plus) ou, s'il est plus
    grand, la somme des « Reels hier » des 7 derniers passages du scan (chacun couvre la veille ; `historique` sans le jour même).
    Deux minorants : on garde le meilleur. Exact dès que le scan tourne chaque jour et qu'un compte publie moins de 12 fois par jour."""
    depuis = _fenetre(jour, 7)
    somme = int(mesure.get("reels_hier") or 0)                           # le passage du jour couvre la veille
    for e in historique:
        j = str(e.get("jour", ""))[:10]
        if depuis and depuis <= j < str(jour)[:10] and e.get("existe") and "reels_hier" in e:
            somme += int(e.get("reels_hier") or 0)
    return max(int(mesure.get("reels_7j") or 0), somme)


# ------------------------------------------------------------------ règles
def _series(historique: list) -> tuple:
    """(jours d'absence de suite, jours de publication de suite) en partant du dernier jour."""
    # 30/09 (Gaëtan : « pourquoi ce compte est BAN alors que Caroline publie dessus et que c'est lui qui ramène le trafic ? ») :
    # le 28/09, un compte « restreint » comptait absent, donc BAN au premier scan. Faux : restreint = Instagram cache le profil
    # aux visiteurs non connectés (contenu jugé sensible, 18+), le compte est bien vivant, seuls ses chiffres sont illisibles
    # pour le scan. Un jour restreint ne compte plus ni comme absence ni comme jour sans Reel : il est sauté.
    absents = publie = 0
    for j in reversed(historique):
        if j.get("existe") and j.get("restreint"):
            continue
        if j.get("existe"):
            break
        absents += 1
    for j in reversed(historique):
        if j.get("existe") and j.get("restreint") and not j.get("posts"):
            continue
        if not (j.get("existe") and j.get("posts", 0) >= 1):
            break
        publie += 1
    return absents, publie


def decider(etat: str, mesure: dict, historique: list, ban_auto: bool, avant_ban: str = "") -> str:
    """Le nouvel état d'une ligne, ou '' si rien ne change. `historique` inclut la mesure du jour."""
    e = _norm(etat)
    absents, publie = _series(historique)
    if e in ("a creer", "à créer"):
        # 01/10 (Andry, Clarisse, Ricado, Michel : identifiants « WARMUP » avant même d'avoir été envoyés, comptes privés de
        # 305 abonnés) : présent sur Instagram ne veut pas dire créé par NOTRE clipper. WARMUP seulement si un scan d'avant l'a
        # vu absent (absent, puis présent). Présent dès le premier regard : identifiant peut-être pris par un tiers, la ligne
        # reste « à créer » (alerte admin dans _executer) ; le bouton « créé » du parcours la passe à WARMUP s'il est bien à lui.
        if not mesure["existe"]:
            return ""
        return "WARMUP" if any(not j.get("existe") for j in historique[:-1]) else ""
    if e == "warmup":
        if absents >= BAN_JOURS:
            return "BAN"
        if mesure["existe"] and mesure["prive"]:
            return "PRIVE"
        if publie >= GOOD_JOURS:
            return "GOOD"
        return ""
    if e in ("good", "prive", "privé"):
        return "BAN" if absents >= BAN_JOURS else ""
    if e == "ban":                                                      # 30/09 : tout BAN vivant sur Instagram revient (à la main compris)
        if not mesure["existe"]:
            return ""
        if avant_ban in ("WARMUP", "GOOD", "PRIVE"):
            return avant_ban
        # 30/09 : état d'avant inconnu. Un compte restreint cache ses Reels au scan : « jamais vu publier » ne prouve rien,
        # et un compte restreint en WARMUP n'en sortirait jamais tout seul → GOOD (le chiffre de Clics dit la vérité)
        return "GOOD" if publie_deja(historique) or mesure.get("restreint") else "WARMUP"
    return ""


def publie_deja(historique: list) -> bool:
    """Au moins un Reel vu par le scan dans l'historique (14 jours)."""
    return any(j.get("existe") and int(j.get("posts") or 0) > 0 for j in historique)


def _en_gestion(c: dict) -> bool:
    """Utilisation Clipper ou vide. 05/10 : le scan exigeait « Clipper » écrit ; 13 lignes du classeur ont la cellule vide et
    n'avaient donc ni ETAT suivi ni Reels Hier — même règle désormais que le Dashboard, classeur_forme et classeur_verif."""
    return _norm(c.get("utilisation") or "") in ("clipper", "")


def candidats(comptes: list) -> list:
    """Les lignes dont l'ETAT peut bouger. 05/10 (Gaëtan : « pour CHAQUE ligne ayant un @, tous les états sauf à créer ») : toute
    ligne créée (WARMUP, GOOD, PRIVE, BAN) dans un état que le bot sait faire évoluer, Gérant ou pas, Utilisation quelle qu'elle
    soit (Metricool, Geelark, comptes libérés compris) ; une ligne « à créer » seulement si un clipper la gère (Utilisation Clipper
    ou vide) : un compte du vivier libre ne peut pas se créer tout seul ; un BAN sans Gérant n'est jamais ressuscité (30/09 :
    retirer le Gérant d'un BAN, c'est le garder hors jeu)."""
    out = []
    creatrices = onboarding.creatrices_connues(comptes)
    for c in comptes:
        e = _norm(c["etat"])
        if not c["handle"] or e not in SUIVIS:
            continue
        # 05/10 (Gaëtan : « scrape les infos des comptes des créas ») : le compte principal d'une créatrice (Gérant = Chloé,
        # Utilisation « Compte de la créatrice ») est scanné pour ses followers et ses Reels, mais son ETAT n'est jamais décidé par
        # le bot : un gros compte restreint ou mal lu ne doit pas finir « BAN » sur la ligne de la créatrice.
        if onboarding.est_ligne_creatrice(c, creatrices):
            continue
        libre = _norm(c["gerant"]) in GERANTS_LIBRES
        if e in A_CREER and (libre or not _en_gestion(c)):
            continue
        if e == "ban" and libre:
            continue
        out.append(c)
    return out


def a_scanner(comptes: list) -> list:
    """Les lignes regardées sur Instagram : tout compte créé (état autre que « à créer »), plus les « à créer » qui ont
    un Gérant. Le vivier « à créer » sans gérant n'existe pas encore sur Instagram, inutile de payer pour lui."""
    vus, out = set(), []
    for c in comptes:
        h = _cle(c["handle"])
        if not h or h in vus:
            continue
        if _norm(c["etat"]) not in A_CREER or _norm(c["gerant"]) not in GERANTS_LIBRES:
            vus.add(h)
            out.append(c)
    return out


# ------------------------------------------------------------------ cycle
_verrou = None


async def executer(ecrire: bool = True) -> dict:
    """Un seul passage à la fois (30/09 : `!dashboard` scanne aussi ; deux scans en même temps écriraient deux fois)."""
    global _verrou
    _verrou = _verrou or asyncio.Lock()
    async with _verrou:
        return await _executer(ecrire)


async def _executer(ecrire: bool = True) -> dict:
    """Un passage : lecture du classeur, scan Instagram, décisions, écriture des cellules. Renvoie le bilan
    {"changements": [(handle, gerant, avant, apres)], "scannes": n, "erreur": str}."""
    if not onboarding.actif():
        return {"changements": [], "scannes": 0, "erreur": "classeur non configuré"}
    comptes = await onboarding.lire_comptes()
    suivis = candidats(comptes)
    lignes = a_scanner(comptes)
    if not lignes:
        return {"changements": [], "scannes": 0, "erreur": ""}
    debut_scan = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mesures = await scanner([_cle(c["handle"]) for c in lignes])
    if mesures is None:
        return {"changements": [], "scannes": 0, "erreur": "Instagram illisible aujourd'hui (Apify), rien changé"}
    d = _lire()
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if ecrire:
        d["scan_iso"] = debut_scan                                      # 08/10 : le scan du soir compte les Reels publiés après
    # 05/10 (Gaëtan : « le scan ne doit jamais conclure BAN à cause d'un simple raté d'Apify ») : un compte absent de la réponse
    # (après la deuxième demande) ou renvoyé sans chiffres est « non lu » : rien n'est écrit pour lui, il garde son état et ses
    # valeurs. Au bout de NON_LU_JOURS passages non lus de suite, il est traité comme absent (sinon un compte vraiment mort ne
    # passerait jamais BAN). Plus de la moitié du classeur non lue = Apify en panne : rien n'est touché, la boucle réessaie.
    non_lus_d = d.setdefault("non_lus", {})
    non_lus = []
    for c in lignes:
        h = _cle(c["handle"])
        m = mesures.get(h)
        if m is not None and m.get("lu", True):                           # (un faux scanner de test sans clé `lu` = lu)
            non_lus_d.pop(h, None)
            continue
        suivi = non_lus_d.get(h) or {}
        n = int(suivi.get("jours") or 0) + (0 if suivi.get("dernier") == jour else 1)
        non_lus_d[h] = {"jours": n, "dernier": jour}
        if n >= NON_LU_JOURS:
            mesures[h] = {**_fiche_vide(), "lu": True, "force_absent": True}   # non lu depuis NON_LU_JOURS passages : absent
        else:
            non_lus.append(c)
    if non_lus and len(non_lus) * 2 > len(lignes):
        return {"changements": [], "scannes": len(lignes), "non_lus": [],
                "erreur": f"Apify n'a lu que {len(lignes) - len(non_lus)} compte(s) sur {len(lignes)}, rien changé (nouvel essai plus tard)"}
    ids_non_lus = {id(c) for c in non_lus}
    changements, followers_maj, clics_maj, liens_maj, reels_maj = [], 0, 0, 0, 0
    restreints_n = absents_n = forces_n = 0
    reels_ecritures = []
    a_relire = []                                                        # 01/10 : Reels des 24 h des clippers, pour la review
    pris = []                                                          # 01/10 : identifiants « à créer » déjà présents sur Instagram
    a_chercher = []                                                    # 09/10 : créés mais jamais vus vivants (@ changé ?) : (priorité, ligne)
    differes = {}                                                      # 09/10 (revue) : BAN écrits après la recherche du jour
    try:                                                               # 09/10 (revue) : @ changés par le clipper → jamais « pris »
        renommes = {str(r.get("nouveau") or "").lower() for f in (onboarding._lire_etat().get("clippers") or {}).values()
                    for r in (f.get("renommes") or []) if isinstance(r, dict)}
    except Exception:                                                  # noqa: BLE001
        renommes = set()
    ids_suivis = {id(c) for c in suivis}
    async def _cellule(c, champ, valeur):                                # 27/09 : la cellule retourne dans l'onglet de la ligne
        await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, onboarding.cellule(c, champ), [[valeur]])

    async def _appliquer(c, apres):
        h_a = _cle(c["handle"])
        changements.append((c["handle"], c["gerant"], c["etat"], apres, c["ligne"]))
        if not ecrire:
            return
        try:
            await _cellule(c, "etat", apres)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Classeur : état non écrit (%s ligne %s) : %s", c.get("onglet", ""), c.get("ligne"), type(erreur).__name__)
            return
        if apres == "BAN":
            d["bans_auto"][h_a] = jour
            d["avant_ban"][h_a] = str(c["etat"]).strip().upper().replace("É", "E")
        elif h_a in d["bans_auto"]:
            d["bans_auto"].pop(h_a, None)
            d["avant_ban"].pop(h_a, None)
    for c in lignes:
        if id(c) in ids_non_lus:
            continue                                                     # 05/10 : non lu → rien d'écrit, rien de conclu, pas d'historique
        h = _cle(c["handle"])
        m = {**_fiche_vide(), **(mesures.get(h) or {})}
        onglet = c.get("onglet", "")
        restreints_n += 1 if m["restreint"] else 0
        absents_n += 0 if m["existe"] else 1
        forces_n += 1 if m.get("force_absent") else 0
        # Followers : pour tout compte lisible (vivant, pas restreint) dont l'onglet a la colonne ; un restreint ou un introuvable
        # garde sa dernière valeur (05/10 : jamais vidé, jamais mis à 0)
        if ecrire and m["existe"] and not m["restreint"] and onboarding.a_colonne("followers", onglet) \
                and str(m["followers"]) != str(c.get("followers", "")).replace(" ", "").replace("\u202f", "").replace("\u00a0", ""):
            try:
                await _cellule(c, "followers", m["followers"])
                followers_maj += 1
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Classeur : followers non écrits (%s ligne %s) : %s", onglet, c.get("ligne"), type(erreur).__name__)
        # 30/09 (Gaëtan : « une colonne Reels Hier, combien de Reels a posté chaque compte IG hier ») ; 05/10 : pour CHAQUE compte
        # scanné (plus seulement les lignes suivies), la veille en jour civil de Paris et les 7 derniers jours (colonne « Reels 7 j »),
        # écrits en un seul appel à la fin, seulement les cellules qui changent. Restreint ou privé : Reels illisibles → cellule
        # vide, pas 0 ; introuvable (réponse explicite d'Apify) : vide.
        if ecrire:
            hist_prec = [x for x in d["historique"].get(h, []) if x.get("jour") != jour]
            lisible = m["existe"] and not m["restreint"] and not m["prive"]
            valeurs = {"reels_hier": str(m["reels_hier"]) if lisible else "",
                       "reels_7j": str(reels_7j_estime(m, hist_prec, jour)) if lisible else ""}
            for champ, valeur in valeurs.items():
                if onboarding.a_colonne(champ, onglet) and valeur != str(c.get(champ) or "").strip():
                    reels_ecritures.append((onboarding.cellule(c, champ), [[valeur]]))
        if m.get("reels") and c.get("gerant") and _en_gestion(c):
            a_relire += [{**r, "handle": h, "gerant": c["gerant"]} for r in m["reels"][:10]]   # 01/10 : review des Reels
        hist = [x for x in d["historique"].get(h, []) if x.get("jour") != jour]
        hist.append({"jour": jour, "existe": m["existe"], "posts": m["posts"], "prive": m["prive"], "fautes": m.get("fautes", 0),
                     "restreint": bool(m.get("restreint")), "followers": m.get("followers", 0),
                     "reels_hier": int(m.get("reels_hier") or 0), "reels_7j": int(m.get("reels_7j") or 0),   # 05/10
                     "posts_lus": int(m.get("posts_lus") or 0)})
        d["historique"][h] = hist[-JOURS_HISTORIQUE:]
        if ecrire and m["existe"] and m.get("bio_lu"):                  # 08/10 : le lien du profil, pour vérifier celui du privé
            d.setdefault("bios", {})[h] = {"jour": jour, "liens": list(m.get("bio_liens") or [])[:5],
                                           "texte": bool(m.get("lien_dans_texte"))}
        if id(c) not in ids_suivis:
            continue
        e_c = _norm(c["etat"])
        if m["existe"]:
            d.setdefault("vivants_vus", {}).setdefault(h, jour)         # 09/10 (revue) : vu vivant un jour, au-delà des 14 jours
        if e_c in CREES + ("good",):
            d.setdefault("cree_vu", {}).setdefault(h, jour)             # 09/10 (revue) : premier passage où la ligne est créée
        apres = decider(c["etat"], m, d["historique"][h], h in d["bans_auto"], d.setdefault("avant_ban", {}).get(h, ""))
        jamais_vu = h not in d.get("vivants_vus", {}) and not any(e.get("existe") for e in d["historique"][h])
        gere = bool(c.get("gerant")) and _en_gestion(c)
        if gere and e_c in CREES and jamais_vu and not m["existe"]:
            a_chercher.append((0, c))                                   # 09/10 : peut-être un @ légèrement changé
            if apres == "BAN":
                if _absents_depuis(d["historique"][h], d["cree_vu"].get(h, jour)) < INTROUVABLE_JOURS:
                    apres = ""                                          # pas BAN tant qu'on le cherche (jours comptés depuis sa création)
                else:
                    differes[id(c)] = (c, apres)                        # BAN écrit après la recherche du jour : retrouvé → jamais BAN
                    continue
        elif gere and e_c == "ban" and jamais_vu and not m["existe"] and _ban_recent(d, h, jour):
            a_chercher.append((1, c))                                   # un BAN récent jamais vu vivant (faux BAN ?)
        elif gere and e_c in CREES and m["existe"] and h in d.get("pris_signales", {}) \
                and not est_a_nous(m, c.get("creatrice") or c.get("onglet") or ""):
            a_chercher.append((0, c))                                   # 09/10 (revue) : @ prévu pris par un inconnu, le sien est à côté ?
        if ecrire and not apres and m["existe"] and _norm(c["etat"]) in A_CREER \
                and h not in d.setdefault("pris_signales", {}) and h not in renommes:
            pris.append(f"{c['handle']} ({str(c.get('gerant') or '?').split()[0]})")   # 01/10 : vu présent sans avoir été vu absent
            d["pris_signales"][h] = jour
        if apres:
            await _appliquer(c, apres)
    if ecrire and a_chercher:                                           # 09/10 : les @ légèrement changés
        # 09/10 (revue) : les comptes créés d'abord (WARMUP, PRIVE), les BAN récents ensuite ; une fois par jour et par compte
        # (`!dashboard` relance le scan), noté seulement pour ceux vraiment cherchés ; le reste attend le passage suivant
        a_chercher.sort(key=lambda x: x[0])
        lot = [c for _, c in a_chercher if d.setdefault("cherches", {}).get(_cle(c["handle"])) != jour]
        if len(lot) > VARIANTES_MAX:
            journal.info("Recherche des @ changés : %s comptes, %s cherchés ce passage", len(lot), VARIANTES_MAX)
        lot = lot[:VARIANTES_MAX]
        for c in lot:
            d["cherches"][_cle(c["handle"])] = jour
        try:
            trouves, perdus = await chercher_variantes(lot) if lot else ([], [])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Recherche des @ changés : %s", erreur)
            trouves, perdus = [], []
        for c, nouveau in trouves:
            h_c = _cle(c["handle"])
            try:
                ok = bool(await _deps["compte_retrouve"](c["handle"], nouveau)) if _deps.get("compte_retrouve") else False
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Compte retrouvé %s → %s : %s", c["handle"], nouveau, erreur)
                ok = False
            if not ok:                                                  # 09/10 (revue) : jamais WARMUP sous un @ qui n'existe pas
                changements.append((c["handle"], c["gerant"], c["etat"], f"vu sous {nouveau}, pas renommé (`!pseudo`)", c["ligne"]))
                continue
            differes.pop(id(c), None)                                   # retrouvé : jamais BAN
            if _norm(c["etat"]) == "ban":                               # faux BAN : le compte vit sous son vrai @, état d'avant rendu
                retour = d.get("avant_ban", {}).get(h_c) or "WARMUP"
                try:
                    await _cellule(c, "etat", retour)
                    d["bans_auto"].pop(h_c, None)
                    d["avant_ban"].pop(h_c, None)
                except Exception:                                       # noqa: BLE001
                    pass
            changements.append((c["handle"], c["gerant"], c["etat"], f"retrouvé sous {nouveau}", c["ligne"]))
        for c in perdus:
            if _norm(c["etat"]) in CREES and _deps.get("compte_introuvable"):
                try:
                    await _deps["compte_introuvable"](c["handle"])
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Compte introuvable %s : %s", c["handle"], erreur)
    for c, apres in list(differes.values()):                            # 09/10 (revue) : pas retrouvé → le BAN différé est écrit
        await _appliquer(c, apres)
    if reels_ecritures:
        try:
            await google_api.sheets_ecrire_plusieurs(onboarding.CLASSEUR_LOGINS_ID, reels_ecritures)
            reels_maj = len(reels_ecritures)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Classeur : colonnes Reels Hier / Reels 7 j non écrites : %s", erreur)
    if ecrire and a_relire and _deps.get("reels_publies"):                  # 01/10 : relus ensuite, à part (review_reels.boucle)
        try:
            _deps["reels_publies"](jour, a_relire)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Reels à relire : %s", type(erreur).__name__)
    # 30/09 (Gaëtan : « Bravo @clippeur pour ton premier Reel, avec le screenshot du Reel, dans #dopamine ») : le premier
    # Reel vu par le scan pour un Gérant part dans #dopamine, une seule fois. Au premier passage, ceux qui ont déjà publié
    # sont notés sans message.
    fetes = d.setdefault("premiers_reels", {})
    premier_passage = not d.get("premiers_reels_init")
    for c in lignes:
        g = _norm(c.get("gerant") or "").split(" ")[0] if c.get("gerant") else ""
        if not g or g in ("x", "y", "z", "aaa", "?", "-", "libre", "dispo") or g in fetes:
            continue
        h = _cle(c["handle"])
        m = mesures.get(h) or {}
        if id(c) in ids_non_lus:
            continue
        deja = any(int(e.get("posts") or 0) > 0 for e in d["historique"].get(h, []) if e.get("jour") != jour)
        if premier_passage and (deja or m.get("posts")):
            fetes[g] = jour
            continue
        if m.get("existe") and m.get("posts") and not deja:
            fetes[g] = jour
            if ecrire and _deps.get("premier_reel"):
                try:
                    await _deps["premier_reel"](c["gerant"], c["handle"], m.get("dernier") or {})
                except Exception as erreur:                              # noqa: BLE001
                    journal.warning("Premier Reel de %s : %s", c["gerant"], erreur)
    if premier_passage:
        d["premiers_reels_init"] = jour
    # 26/09 : tableau de bord — pour chaque ligne qui a un Gérant, ses visites payables des 7 derniers jours ; 30/09 (Gaëtan :
    # « associe automatiquement les Clics last 7d avec les clippeurs ») : un chiffre par bloc de clipper, tiré de SES liens GAML
    # (colonne « Lien GAML associé », sinon la note GAML), écrit une fois et fusionné comme le Gérant (onboarding.clics_classeur)
    if ecrire:
        try:                                                             # 30/09 : les comptes d'un clipper rangés ensemble d'abord
            if await onboarding.regrouper_comptes(comptes):
                comptes = await onboarding.lire_comptes()
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Classeur : regroupement des comptes impossible : %s", erreur)
        try:
            clics_maj = (await onboarding.clics_classeur(comptes, _deps.get("clics_7j"))).get("ecrits", 0)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Classeur : Clics last 7d. non écrits : %s", erreur)
    if ecrire:
        try:
            liens_maj = (await onboarding.liens_classeur(comptes)).get("ecrits", 0)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Colonne Lien GAML (états) : %s", erreur)
    if ecrire and _deps.get("reconcilier"):
        try:
            etats_h = {c["handle"].lower(): c["etat"] for c in comptes if c["handle"]}
            for handle, _, _, apres, _ in changements:
                etats_h[handle.lower()] = apres
            # 28/09 : les comptes qui ont publié au moins une fois (le premier Reel valide l'étape 5 tout seul)
            publies = {h for h, hist in d["historique"].items() if any(e.get("existe") and int(e.get("posts") or 0) > 0 for e in hist)}
            # 30/09 (période d'essai) : les Reels de chaque compte sur 72 h = ses trois derniers passages (chacun compte 24 h)
            depuis_3j = _fenetre(jour, 3)
            reels_72h = {h: sum(int(e.get("posts") or 0) for e in hist if e.get("existe") and str(e.get("jour", ""))[:10] >= depuis_3j)
                         for h, hist in d["historique"].items()}
            await _deps["reconcilier"](etats_h, publies, reels_72h, d["historique"])   # 08/10 : l'historique, pour compter les Reels
            if _deps.get("controler_bios"):                             # 08/10 : le lien est-il vraiment sur le compte privé ?
                await _deps["controler_bios"](d.get("bios") or {})
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réconciliation des parcours : %s", erreur)
    if ecrire and _deps.get("reservations_expirees"):                             # 28/09 : la réservation qui expire
        try:
            await _deps["reservations_expirees"](d["historique"])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réservations expirées : %s", erreur)
    fautifs = sorted({f"{c['gerant'].split()[0]} (@{c['handle']})" for c in lignes
                      if c.get("gerant") and (mesures.get(_cle(c["handle"])) or {}).get("fautes")})
    if ecrire and fautifs and _deps.get("canal_admin"):                           # 28/09 : contrôle par Reel, une ligne à l'admin
        try:
            canal_f = await _deps["canal_admin"]()
            if canal_f is not None:
                await canal_f.send("⚠️ Lien ou @ dans une légende de Reel hier : " + ", ".join(fautifs)[:1800])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Alerte légendes : %s", erreur)
    if ecrire and pris and _deps.get("canal_admin"):                              # 01/10 : une fois par identifiant
        try:
            canal_p = await _deps["canal_admin"]()
            if canal_p is not None:
                await canal_p.send("⚠️ Identifiant déjà pris sur Instagram ? Ces lignes « à créer » existent sans avoir jamais été vues "
                                   "absentes, elles restent « à créer » : " + ", ".join(pris)[:1700]
                                   + "\n\nSi le clipper l'a bien créé, son bouton « créé » la passe en WARMUP.")
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Alerte identifiants pris : %s", erreur)
    if ecrire and _deps.get("deposer") and _deps.get("salon_de_prenom"):        # 27/09 : « Reels d'hier » du message du matin
        for prenom, texte_r in lignes_reels(comptes, d["historique"], jour).items():
            try:
                sid = _deps["salon_de_prenom"](prenom)
                if sid:
                    _deps["deposer"](sid, "reels", texte_r)
            except Exception as erreur:                                      # noqa: BLE001
                journal.warning("Reels du matin pour %s : %s", prenom, erreur)
    if ecrire:
        try:                                                                        # 28/09 : l'onglet Dashboard, une ligne par clipper
            await ecrire_dashboard(comptes, d["historique"], _deps.get("clics_7j"), jour, forme=True)   # 09/10 : + onglets, capacité
            d["dashboard_version"] = DASHBOARD_VERSION
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : %s", erreur)
    if ecrire and _deps.get("verifier_classeur"):                                 # 29/09 : le classeur se vérifie seul, rien corrigé
        try:
            await _deps["verifier_classeur"](comptes, d["historique"])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Vérification du classeur : %s", erreur)
    if ecrire:
        d["dernier"] = jour
        d["version"] = VERSION
        _ecrire(d)
    # 05/10 : les compteurs du passage dans le journal (jamais d'identifiant de compte) — c'est ici qu'on lit, dans Railway, pourquoi
    # une cellule n'a pas bougé : non lu (Apify muet), restreint (chiffres cachés), introuvable (réponse explicite)
    journal.info("États du classeur : %d compte(s) scanné(s), %d non lu(s) laissés tels quels, %d restreint(s), %d introuvable(s) "
                 "(dont %d après %d passages non lus), %d changement(s), %d followers, %d cellules Reels, %d clics, %d liens mis à jour",
                 len(lignes), len(non_lus), restreints_n, absents_n, forces_n, NON_LU_JOURS, len(changements), followers_maj, reels_maj,
                 clics_maj, liens_maj)
    avance = onboarding.comptes_d_avance(comptes)                        # 30/09 : comptes à créer sans Gérant, par créatrice
    restreints = sorted(f"`{c['handle']}` ({c['gerant']})" for c in lignes if c.get("gerant")
                        and (mesures.get(_cle(c["handle"])) or {}).get("restreint"))
    non_lus_txt = sorted(f"`{c['handle']}` ({c.get('gerant') or 'sans gérant'})" for c in non_lus)
    return {"changements": changements, "scannes": len(lignes), "erreur": "", "followers": followers_maj, "clics": clics_maj, "liens": liens_maj,
            "reels": reels_maj, "avance": avance, "restreints": restreints, "non_lus": non_lus_txt}


ONGLET_DASHBOARD = os.environ.get("ONGLET_DASHBOARD", "Dashboard").strip() or "Dashboard"
ENTETE_DASHBOARD = ["Clipper", "Comptes", "Créés", "À créer", "BAN", "Followers cumulés", "Visites 7 j", "Visites hier", "Reels 7 j", "Reels hier",
                    "Dernier Reel", "Détail des comptes"]
NB_COLONNES = len(ENTETE_DASHBOARD)


def _fenetre(jour: str, jours: int) -> str:
    """Le premier jour (ISO) d'une fenêtre de `jours` jours qui finit à `jour` ; '' si la date est illisible."""
    try:
        return (date.fromisoformat(str(jour)[:10]) - timedelta(days=jours - 1)).isoformat()
    except ValueError:
        return ""


def _entier(v) -> int:
    try:
        return int(re.sub(r"[^\d-]", "", str(v or "")) or 0)
    except ValueError:
        return 0


def lignes_dashboard(comptes: list, historique: dict, clics_de, jour: str, exclus=None) -> list:
    """28/09 (Gaëtan : « un dashboard par clipper, au même endroit ») : par créatrice, une ligne par clipper — comptes, créés,
    à créer, BAN, followers cumulés des comptes vivants, visites payables des 7 derniers jours (le chiffre de la colonne Clics,
    une seule fois), Reels vus par le scan sur 7 jours, dernier Reel, et le détail compte par compte. Triée par visites."""
    # 30/09 (Gaëtan : « considère Rianah (Metricool) et Julien (Metricool) comme des clippeurs, ajoute-les au dashboard ») : le Gérant
    # compte en entier — « Rianah (Metricool) » a sa ligne ; un masque (`!dashboard exclure`) ne vise que le Gérant écrit exactement ainsi
    exclus_n = {_norm(str(x)).strip() for x in (exclus or []) if str(x).strip()}
    creatrices = onboarding.creatrices_connues(comptes)
    CLE_CREA = "\u0000creatrice"                                         # 05/10 : les comptes de la créatrice elle-même, en tête de son bloc
    par = {}
    for c in comptes:
        g = (c.get("gerant") or "").strip()
        if not g or _norm(g) in ("x", "y", "z", "aaa", "?", "-", "libre", "dispo") or not c.get("handle"):
            continue
        if _norm(g).strip() in exclus_n:                                    # masqué (`!dashboard exclure Prénom`, Gérant écrit exactement ainsi)
            continue
        crea = ((c.get("creatrice") or c.get("onglet") or "?").split() or ["?"])[0]
        # 05/10 (Gaëtan : « scrape les infos des comptes des créas, leurs Reels, leurs clics, ajoute-les au Dashboard ») : les lignes
        # dont le Gérant est une créatrice (ou l'Utilisation « Compte de la créatrice ») font une ligne à part, la première du bloc
        if onboarding.est_ligne_creatrice(c, creatrices):
            par.setdefault(crea, {}).setdefault(CLE_CREA, []).append(c)
            continue
        par.setdefault(crea, {}).setdefault(g, []).append(c)
    lignes = [[f"Dashboard clippers — mis à jour le {jour} · visites payables (GAML) sur 7 jours et hier, followers des comptes en gestion, Reels vus par le scan"
               + (f" · masqués : {', '.join(str(x) for x in exclus)}" if exclus else "")], []]
    tot_f = tot_v = tot_vh = tot_r = tot_rh = tot_c = 0
    for crea, clippers in par.items():
        rows, rows_crea = [], []
        for g, cs in clippers.items():
            est_crea = g == CLE_CREA
            etats = [_norm(c.get("etat") or "") for c in cs]
            ban = sum(1 for e in etats if e == "ban")
            a_creer = sum(1 for e in etats if e in ("a creer", "à créer", ""))
            crees = len(cs) - ban - a_creer
            # 28/09 (Gaëtan : « la somme des followers des 3 comptes que le clipper a en gestion ») : les comptes dont
            # l'Utilisation est Clipper (ou vide), sauf les BAN (morts), quel que soit l'état ; un compte passé Metricool
            # ou « à mettre Metricool » n'est plus en gestion, il reste dans le détail. 05/10 : pour la créatrice, tous ses comptes vivants.
            en_gestion = [c for c, e in zip(cs, etats)
                          if e != "ban" and (est_crea or _norm(c.get("utilisation") or "clipper") in ("clipper", "", "metricool"))]
            followers = sum(_entier(c.get("followers")) for c in en_gestion)
            # Visites : d'abord la colonne « Clics last 7d. » du classeur (écrite par le scan, propre à la créatrice de la
            # ligne : Lilian sous Chloé et Lilian sous Sophie sont deux liens), sinon le total du clipper via clics_de.
            en_colonne = [_entier(c.get("clics")) for c in cs if str(c.get("clics") or "").strip() != ""]
            if en_colonne:
                visites = max(en_colonne)
            elif est_crea:
                visites = None
            else:
                try:
                    visites = clics_de(g) if clics_de else None
                except Exception:                                       # noqa: BLE001
                    visites = None
            if est_crea:                                                # 05/10 : la créatrice n'a pas de paie au clic, ses clics d'hier sont dans sa colonne
                hier_col = [_entier(c.get("clics_hier")) for c in cs if str(c.get("clics_hier") or "").strip() != ""]
                visites_hier = max(hier_col) if hier_col else None
            else:
                try:                                                    # visites d'hier (dépendance à deux arguments, 28/09)
                    visites_hier = clics_de(g, 1) if clics_de else None
                except Exception:                                       # noqa: BLE001
                    visites_hier = None
            depuis = _fenetre(jour, 7)
            reels7, reels_hier, dernier = 0, 0, ""
            # 30/09 (Gaëtan : « la colonne Reels hier ne marche pas », 0 partout) : elle ne lisait que le scan daté du jour de
            # l'écriture ; un Dashboard réécrit le matin AVANT le scan du jour (redémarrage, `!dashboard`) mettait donc 0 à tout
            # le monde. Elle lit maintenant le scan le plus récent (celui du jour, sinon celui de la veille) : les 24 h qu'il couvre.
            veille = _fenetre(jour, 2) or ""
            for c in cs:
                hist = historique.get(c["handle"].lower()) or []
                for e in (hist if depuis else hist[-7:]):
                    j_e = str(e.get("jour", ""))[:10]
                    if not e.get("existe") or (depuis and not (depuis <= j_e <= str(jour)[:10])):
                        continue
                    reels7 += int(e.get("posts") or 0)
                recents = [e for e in hist if veille <= str(e.get("jour", ""))[:10] <= str(jour)[:10]]
                if recents:
                    e = max(recents, key=lambda x: str(x.get("jour", "")))
                    reels_hier += int(e.get("reels_hier", e.get("posts")) or 0) if e.get("existe") else 0   # 05/10 : veille civile
                for e in hist:
                    if e.get("existe") and int(e.get("posts") or 0) > 0 and str(e.get("jour", "")) > dernier:
                        dernier = str(e.get("jour", ""))
            def _restreint(c):                                          # 05/10 : profil restreint au dernier scan = chiffres cachés par Instagram
                hist_c = historique.get(c["handle"].lower()) or []
                return bool(hist_c and hist_c[-1].get("restreint"))
            detail = " · ".join(f"{c['handle']} ({(c.get('etat') or '?').strip()}, {_entier(c.get('followers'))}"
                                + ("" if _norm(c.get("utilisation") or "clipper") == "clipper" else f", {str(c.get('utilisation')).strip()}")
                                + (", restreint : chiffres cachés" if _restreint(c) else "") + ")"
                                for c in cs)
            ligne = [f"{crea} (créatrice)" if est_crea else g, len(cs), crees, a_creer, ban, followers, visites if visites is not None else "",
                     visites_hier if visites_hier is not None else "", reels7, reels_hier, dernier, detail]
            (rows_crea if est_crea else rows).append(ligne)
        rows.sort(key=lambda r: (-(r[6] if isinstance(r[6], int) else -1), -r[5]))
        somme = lambda i: sum(r[i] for r in rows if isinstance(r[i], int))  # noqa: E731
        f_c, v_c, vh_c, r_c, rh_c = somme(5), somme(6), somme(7), somme(8), somme(9)
        tot_f += f_c; tot_v += v_c; tot_vh += vh_c; tot_r += r_c; tot_rh += rh_c; tot_c += len(rows)
        lignes.append([crea.upper(), f"{len(rows)} clipper(s)", "", "", "", f_c, v_c, vh_c, r_c, rh_c, "", ""])
        lignes.append(list(ENTETE_DASHBOARD))
        lignes.extend(rows_crea + rows)                                 # 05/10 : la créatrice d'abord, hors des totaux des clippers
        lignes.append([])
    lignes.append(["TOTAL", f"{tot_c} clipper(s)", "", "", "", tot_f, tot_v, tot_vh, tot_r, tot_rh, "", ""])
    return lignes


async def ecrire_dashboard(comptes: list, historique: dict, clics_de, jour: str, exclus=None, forme: bool = False) -> int:
    """Écrit l'onglet Dashboard du classeur des logins. Renvoie le nombre de lignes.
    09/10 (dashboard, contrat C5) : délègue à dashboard.ecrire(force=True), qui relit lui-même le classeur, les séries, les états,
    les clics et le contrôle, et réécrit l'onglet en place (plus vidé d'abord) ; les arguments restent pour les appelants. La mise
    en forme des onglets créatrices et l'onglet Build capacity ne suivent plus chaque réécriture (un Dashboard réécrit toutes les
    15 min déplacerait des lignes pendant que Gaëtan édite et pourrait payer Apify) : `forme=True`, passé par le seul passage
    complet, les lance ensuite (mettre_en_forme_classeur)."""
    import dashboard                                                    # import tardif : dashboard lit l'état de ce module
    try:
        bilan = await dashboard.ecrire(force=True)
    finally:
        if forme:
            await mettre_en_forme_classeur(comptes)
    if bilan.get("erreur"):
        raise RuntimeError(bilan["erreur"])
    return int(bilan.get("lignes") or 0)


async def mettre_en_forme_classeur(comptes: list) -> None:
    """09/10 (dashboard) : la mise en forme des onglets créatrices (classeur_forme, qui peut déplacer des lignes) et l'onglet Build
    capacity (capacite, qui peut lancer Apify), sortis du chemin du Dashboard : passage complet du matin seulement."""
    if not (onboarding.actif() and google_api.actif()):
        return
    cid = onboarding.CLASSEUR_LOGINS_ID
    try:                                                                # 29/09 : les onglets créatrices, un bloc par clipper
        import classeur_forme
        classeur_forme.configurer({"google_api": google_api, "classeur_id": cid, "colonnes_par_onglet": onboarding._colonnes_par_onglet,
                                   "palette": PALETTE_DASHBOARD, "palette_defaut": PALETTE_DEFAUT, "melange": _melange, "rgb": _rgb,
                                   "normaliser": _norm, "onglet_a1": onboarding.onglet_a1, "colonne_lettre": google_api.colonne_lettre,
                                   "creatrices": onboarding.creatrices_connues(comptes)})   # 05/10 : la ligne d'une créatrice n'est jamais réécrite
        await classeur_forme.formater(comptes)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Classeur : mise en forme des onglets impossible (%s)", erreur)
    global CAPACITE
    try:                                                                # 30/09 : l'onglet « Build capacity » (09/10 : passage complet seulement)
        import capacite
        CAPACITE = await capacite.ecrire(comptes)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Build capacity : %s", erreur)


CAPACITE = {}                                                           # dernier résumé de l'onglet Build capacity


# Palette par créatrice : (bandeau, teinte des lignes). Lisible sur téléphone, une couleur par bloc.
PALETTE_DASHBOARD = {"chloe": ("#C2185B", "#FCE4EC"), "sarah": ("#1565C0", "#E3F2FD"), "sophie": ("#6A1B9A", "#F3E5F5"),
                     "jade": ("#2E7D32", "#E8F5E9"), "maddie": ("#EF6C00", "#FFF3E0"), "clara": ("#00838F", "#E0F7FA")}
PALETTE_DEFAUT = ("#455A64", "#ECEFF1")
SOMBRE, BLANC, GRIS_CLAIR, GRIS_TEXTE = "#263238", "#FFFFFF", "#ECEFF1", "#546E7A"
LARGEURS_DASHBOARD = (120, 78, 64, 70, 58, 118, 96, 96, 80, 80, 96, 560)


def _rgb(hexa: str) -> dict:
    h = hexa.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def _melange(hexa: str, t: float) -> str:
    """Blanc → couleur, t entre 0 et 1 (dégradé des visites)."""
    h = hexa.lstrip("#"); t = max(0.0, min(1.0, t))
    return "#" + "".join(f"{int(round(255 + (int(h[i:i + 2], 16) - 255) * t)):02X}" for i in (0, 2, 4))


def _plage(sid: int, r0: int, r1: int, c0: int = 0, c1: int = NB_COLONNES) -> dict:
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _cellules(sid, r0, r1, c0, c1, fond=None, texte=None, gras=None, taille=None, aligne=None, format_nombre=None, coupe=None,
              format_date=None) -> dict:
    fmt, champs = {}, []
    if fond:
        fmt["backgroundColor"] = _rgb(fond); champs.append("backgroundColor")
    tf = {}
    if texte: tf["foregroundColor"] = _rgb(texte)
    if gras is not None: tf["bold"] = gras
    if taille: tf["fontSize"] = taille
    if tf:
        fmt["textFormat"] = tf; champs.append("textFormat")
    if aligne:
        fmt["horizontalAlignment"] = aligne; champs.append("horizontalAlignment")
    if format_nombre:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": format_nombre}; champs.append("numberFormat")
    if format_date:                                                         # 28/09 : « Dernier Reel » affichait 46 293 (série)
        fmt["numberFormat"] = {"type": "DATE", "pattern": format_date}; champs.append("numberFormat")
    if coupe:
        fmt["wrapStrategy"] = coupe; champs.append("wrapStrategy")
    fmt["verticalAlignment"] = "MIDDLE"; champs.append("verticalAlignment")
    return {"repeatCell": {"range": _plage(sid, r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt},
                           "fields": "userEnteredFormat(" + ",".join(champs) + ")"}}


def requetes_mise_en_forme(lignes: list, sid: int) -> list:
    """La mise en forme de l'onglet Dashboard, recalculée sur les lignes réellement écrites : titre en bandeau sombre, un bloc
    (« card ») par créatrice avec son bandeau de couleur, en-têtes gris, lignes en zébrure, BAN en rouge, à créer en orange,
    visites en dégradé vert, cadre autour de chaque bloc, quadrillage masqué, titre et colonne des prénoms figés."""
    n = len(lignes)
    req = [{"unmergeCells": {"range": _plage(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2)}},
           _cellules(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2, fond=BLANC, texte="#212121", gras=False, taille=10, aligne="LEFT", coupe="CLIP"),
           {"updateBorders": {"range": _plage(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2), "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
                              "left": {"style": "NONE"}, "right": {"style": "NONE"}, "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}}},
           {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": 1, "frozenColumnCount": 1}},
                                      "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}]
    for i, largeur in enumerate(LARGEURS_DASHBOARD):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                  "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": max(n, 1) + 100},
                                              "properties": {"pixelSize": 24}, "fields": "pixelSize"}})
    if not lignes:
        return req
    # Titre
    req += [_cellules(sid, 0, 1, 0, NB_COLONNES, fond=SOMBRE, texte=BLANC, gras=True, taille=12, aligne="LEFT", coupe="OVERFLOW_CELL"),   # pas de fusion : la colonne A est figée
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}}]
    max_v = max((r[6] for r in lignes if len(r) >= 7 and isinstance(r[6], int) and r[0] not in ("TOTAL",) and r != ENTETE_DASHBOARD
                 and not (len(r) >= 2 and str(r[1]).endswith("clipper(s)"))), default=0)
    i = 1
    while i < n:
        r = lignes[i]
        if len(r) >= 2 and r[0] == "TOTAL":
            req += [_cellules(sid, i, i + 1, 0, NB_COLONNES, fond=SOMBRE, texte=BLANC, gras=True, taille=11),
                    _cellules(sid, i, i + 1, 5, 10, fond=SOMBRE, texte=BLANC, gras=True, taille=11, aligne="CENTER", format_nombre="#,##0"),
                    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 30}, "fields": "pixelSize"}}]
            i += 1
            continue
        if len(r) >= 2 and str(r[1]).endswith("clipper(s)") and i + 1 < n and lignes[i + 1] == ENTETE_DASHBOARD:
            bande, teinte = PALETTE_DASHBOARD.get(_norm(str(r[0])).split()[0] if str(r[0]).strip() else "", PALETTE_DEFAUT)
            debut = i
            fin = i + 2
            while fin < n and lignes[fin] and lignes[fin] != ENTETE_DASHBOARD and lignes[fin][0] != "TOTAL":
                fin += 1
            # bandeau créatrice + en-têtes
            req += [_cellules(sid, i, i + 1, 0, NB_COLONNES, fond=bande, texte=BLANC, gras=True, taille=12, coupe="OVERFLOW_CELL"),
                    _cellules(sid, i, i + 1, 5, 10, fond=bande, texte=BLANC, gras=True, taille=12, aligne="CENTER", format_nombre="#,##0"),
                    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 32}, "fields": "pixelSize"}},
                    _cellules(sid, i + 1, i + 2, 0, NB_COLONNES, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9),
                    _cellules(sid, i + 1, i + 2, 1, NB_COLONNES - 1, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9, aligne="CENTER")]
            for k, ligne in enumerate(lignes[i + 2:fin]):
                j = i + 2 + k
                fond = teinte if k % 2 == 0 else BLANC
                req += [_cellules(sid, j, j + 1, 0, NB_COLONNES, fond=fond, texte="#212121", gras=False, taille=10),
                        _cellules(sid, j, j + 1, 0, 1, fond=fond, texte="#212121", gras=True, taille=10),
                        _cellules(sid, j, j + 1, 1, 10, fond=fond, texte="#37474F", gras=False, taille=10, aligne="CENTER", format_nombre="#,##0"),
                        _cellules(sid, j, j + 1, 10, 11, fond=fond, texte="#37474F", gras=False, taille=10, aligne="CENTER", format_date="dd/MM"),
                        _cellules(sid, j, j + 1, 11, 12, fond=fond, texte=GRIS_TEXTE, gras=False, taille=9, coupe="CLIP")]
                comptes, crees, a_creer, ban = (_entier(ligne[1]), _entier(ligne[2]), _entier(ligne[3]), _entier(ligne[4])) if len(ligne) >= 5 else (0, 0, 0, 0)
                if crees and crees == comptes:
                    req.append(_cellules(sid, j, j + 1, 2, 3, fond=fond, texte="#2E7D32", gras=True, taille=10, aligne="CENTER"))
                if a_creer > 0:
                    req.append(_cellules(sid, j, j + 1, 3, 4, fond="#FFE0B2", texte="#E65100", gras=True, taille=10, aligne="CENTER"))
                if ban > 0:
                    req.append(_cellules(sid, j, j + 1, 4, 5, fond="#FFCDD2", texte="#B71C1C", gras=True, taille=10, aligne="CENTER"))
                v = ligne[6] if len(ligne) >= 7 and isinstance(ligne[6], int) else None
                if v is not None and v > 0 and max_v:
                    req.append(_cellules(sid, j, j + 1, 6, 7, fond=_melange("#43A047", 0.15 + 0.85 * (v / max_v) ** 0.5), texte="#1B5E20", gras=True, taille=10, aligne="CENTER", format_nombre="#,##0"))
                for col in (7, 9):                                          # visites d'hier, Reels d'hier : en vert quand il y en a
                    x = ligne[col] if len(ligne) > col and isinstance(ligne[col], int) else 0
                    if x > 0:
                        req.append(_cellules(sid, j, j + 1, col, col + 1, fond=fond, texte="#1B5E20", gras=True, taille=10, aligne="CENTER", format_nombre="#,##0"))
            # cadre du bloc
            req.append({"updateBorders": {"range": _plage(sid, debut, fin, 0, NB_COLONNES),
                                          "top": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}, "bottom": {"style": "SOLID_MEDIUM", "color": _rgb(bande)},
                                          "left": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}, "right": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}}})
            i = fin
            continue
        if not r:
            req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 14}, "fields": "pixelSize"}})
        i += 1
    return req


RE_FAUTE = re.compile(r"https?://|www\.|getallmylinks|gaml\.|\.fr/|\.app/|(?<![\w.])@[A-Za-z0-9_.]{3,}")


def lignes_reels(comptes: list, historique: dict, jour: str) -> dict:
    """{prénom du gérant: ligne du matin} — les publications apparues sur ses comptes (Utilisation = Clipper) entre le scan
    précédent et celui de `jour` (27/09 : les Inputs clippers sont éteints, la ligne « Reels d'hier » vient d'ici)."""
    par = {}
    for c in comptes:
        g = str(c.get("gerant") or "").strip()
        h = str(c.get("handle") or "").lower()
        if not h or not g or _norm(g) in GERANTS_LIBRES or not _en_gestion(c):   # 05/10 : Utilisation vide = Clipper
            continue
        entrees = [e for e in historique.get(h, []) if e.get("existe")]
        auj = next((e for e in entrees if e.get("jour") == jour), None)
        if auj is None or (auj.get("restreint") and not auj.get("posts")):   # 30/09 : restreint = illisible, pas « 0 Reel »
            continue
        avant = [e for e in entrees if str(e.get("jour") or "") < jour and not (e.get("restreint") and not e.get("posts"))]
        prev = int((avant[-1].get("posts") if avant else 0) or 0)
        delta = max(0, int(auj.get("posts") or 0) - prev)
        p = par.setdefault(g.split()[0], {"n": 0, "comptes": 0, "fautes": 0})
        p["n"] += delta
        p["comptes"] += 1
        p["fautes"] += int(auj.get("fautes") or 0)
    return {prenom: f"🎬 Hier : {p['n']} publication(s) sur tes comptes." + (" ✅" if p["n"] >= 2 and not p["fautes"] else "")
            + ("\n❌ Un lien ou un @ dans la légende d'un Reel d'hier : enlève-le. Le lien va seulement dans la bio de ton compte privé."
               if p["fautes"] else "")
            for prenom, p in par.items()}


def texte_bilan(bilan: dict, test: bool = False) -> str:
    if bilan.get("erreur"):
        return f"⚠️ États du classeur : {bilan['erreur']}."
    ch = bilan["changements"]
    entete = (f"🗂️ **États du classeur** · {bilan['scannes']} compte(s) regardés sur Instagram · "
              f"{bilan.get('followers', 0)} followers, {bilan.get('reels', 0)} cellules Reels (hier / 7 j), {bilan.get('clics', 0)} clics, "
              f"{bilan.get('liens', 0)} liens GAML mis à jour")
    avance = bilan.get("avance") or {}
    if avance:                                                          # 30/09 (Gaëtan) : la capacité d'onboarding en un coup d'œil
        entete += (f"\n📦 **Comptes d'avance** (à créer, sans Gérant) : {sum(avance.values())} · "
                   + " · ".join(f"{k} {v}" for k, v in sorted(avance.items(), key=lambda kv: -kv[1])))
    if bilan.get("restreints"):                                         # 30/09 : vivants, jamais BAN, chiffres illisibles
        entete += (f"\n🔒 **Restreints** (vivants, cachés aux visiteurs non connectés : followers et Reels illisibles pour le scan, "
                   f"jamais passés BAN) : {', '.join(bilan['restreints'])}")
    if bilan.get("non_lus"):                                            # 05/10 : Apify muet sur ces comptes, rien conclu
        entete += (f"\n⚠️ **Non lus par Apify** ({len(bilan['non_lus'])}, laissés tels quels, ni BAN ni 0 ; absents s'ils restent "
                   f"non lus {NON_LU_JOURS} passages de suite) : {', '.join(bilan['non_lus'][:25])}")
    if not ch:
        return entete + "\n· aucun état à changer."
    par_etat = {}
    for handle, gerant, avant, apres, ligne in ch:
        par_etat.setdefault(apres, []).append(f"`{handle}` ({gerant}, était {avant})")
    lignes = [entete + (" · **test, rien n'est écrit**" if test else "")]
    for apres in ("WARMUP", "GOOD", "PRIVE", "BAN"):
        if apres in par_etat:
            lignes.append(f"→ **{apres}** : " + ", ".join(par_etat[apres]))
    for apres, quoi in par_etat.items():                                # 09/10 (revue) : comptes retrouvés sous un @ proche
        if apres not in ("WARMUP", "GOOD", "PRIVE", "BAN"):
            lignes.append(f"🔎 {', '.join(quoi)} → {apres}")
    if "BAN" in par_etat:
        lignes.append(f"-# BAN = introuvable sur Instagram (redemandé une fois avant de conclure ; un compte restreint n'est jamais BAN){' au premier scan' if BAN_JOURS <= 1 else f' {BAN_JOURS} jours de suite'} "
                      "(et, en plus, tout mail « Action requise / compte suspendu » lu dans ta boîte toutes les 3 min). "
                      "Le compte est à remplacer : `!liberer Prénom handle` puis un nouvel identifiant.")
    return "\n".join(lignes)


async def boucle(client) -> None:
    """Un passage par jour, à HEURE_UTC, après le rapport inputs. Trois tentatives espacées de 15 minutes."""
    if not actif():
        journal.info("États du classeur désactivés (APIFY_TOKEN / classeur absents ou ETATS_CLASSEUR=0)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = datetime.now(timezone.utc)
            jour = maintenant.strftime("%Y-%m-%d")
            d = _lire()
            if d.get("historique") and d.get("dashboard_version") != DASHBOARD_VERSION:     # 28/09 : nouvelle structure → réécrit
                comptes_d = await onboarding.lire_comptes()
                try:                                                    # 05/10 : les Clics des blocs (créatrices comprises) d'abord, sans scan Apify
                    await onboarding.clics_classeur(comptes_d, _deps.get("clics_7j"))
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Dashboard : Clics non relevés avant la réécriture (%s)", erreur)
                await ecrire_dashboard(comptes_d, d.get("historique", {}), _deps.get("clics_7j"), jour)
                d = _lire(); d["dashboard_version"] = DASHBOARD_VERSION; _ecrire(d)
                journal.info("Dashboard réécrit (structure v%s)", DASHBOARD_VERSION)
            if maintenant.hour >= HEURE_UTC and (d.get("dernier") != jour or d.get("version") != VERSION) \
                    and int(d.get("essais", {}).get(jour, 0)) < 3:
                bilan = await executer(ecrire=True)
                if bilan.get("erreur"):
                    d = _lire(); d.setdefault("essais", {})[jour] = int(d.get("essais", {}).get(jour, 0)) + 1; _ecrire(d)
                    journal.warning("États du classeur : %s", bilan["erreur"])
                else:
                    if (bilan["changements"] or bilan.get("followers") or bilan.get("clics") or bilan.get("non_lus")) and _deps.get("canal_admin"):
                        canal = await _deps["canal_admin"]()
                        if canal is not None:
                            await canal.send(texte_bilan(bilan)[:1990])
                    bans = [f"`{h}` ({g})" for h, g, _, a, _ in bilan["changements"] if a == "BAN"]
                    if bans and _deps.get("notifier"):
                        await _deps["notifier"]("🚫 **Comptes introuvables sur Instagram, passés en BAN** : "
                                                + ", ".join(bans) + ". À remplacer : `!liberer Prénom handle`, puis un nouvel identifiant.")
            if SOIR_HEURE >= 0 and _paris(maintenant).hour >= SOIR_HEURE and d.get("dernier") == jour and d.get("soir") != jour:
                d = _lire(); d["soir"] = jour; _ecrire(d)               # une fois par jour, même si Apify échoue
                await scan_du_soir(client, d.get("scan_iso") or f"{jour}T{HEURE_UTC:02d}:00:00+00:00")
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.exception("Boucle états du classeur : %s", erreur)
        await asyncio.sleep(900)


async def scan_du_soir(client, depuis_iso: str) -> list:
    """08/10 (GO n° 2) : les comptes dont les Reels ouvrent un compte en attente, relus le soir ; le parcours ouvre aussitôt ceux
    qui ont leurs Reels (un jour gagné par compte). Renvoie [(uid, type, n)] des étapes envoyées."""
    import parcours                                                     # import tardif : parcours importe onboarding
    handles = parcours.comptes_du_soir()
    if not handles:
        journal.info("Scan du soir : aucun compte en attente de Reels")
        return []
    mesures = await scanner([_cle(h) for h in handles])
    if mesures is None:
        journal.warning("Scan du soir : Apify illisible, rien conclu")
        return []
    n = parcours.noter_reels_soir(mesures, depuis_iso, cle=_cle)
    faits = await parcours.programme_du_jour(client)
    ouverts = [f for f in faits if f[1] == "etape"]
    journal.info("Scan du soir : %d compte(s) relu(s), %d fiche(s) mise(s) à jour, %d compte(s) ouvert(s)", len(handles), n, len(ouverts))
    if ouverts and _deps.get("canal_admin"):
        canal = await _deps["canal_admin"]()
        if canal is not None:
            try:
                await canal.send(f"🌙 Scan du soir : {len(ouverts)} compte(s) ouvert(s) un jour plus tôt (" +
                                 ", ".join(f"<@{u}> compte {k}" for u, _, k in ouverts)[:1500] + ")")
            except Exception:                                           # noqa: BLE001
                pass
    return faits


async def commande_staff(message, texte: str) -> bool:
    """`!etats-comptes` : passage immédiat · `!etats-comptes test` : ce qui changerait, sans rien écrire."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!etats-comptes", "!états-comptes", "!dashboard", "!capacite", "!capacité", "!build-capacity"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if mots[0].lower() in ("!capacite", "!capacité", "!build-capacity"):  # 30/09 : l'onglet Build capacity seul, sans scan
        import capacite
        try:
            if len(mots) > 1 and mots[1].lower() in ("ajouter", "ajoute"):   # 30/09 : la réserve part dans les onglets
                await message.reply("⏳ J'ajoute les identifiants de la réserve dans chaque onglet et j'étends les tableaux.")
                await message.reply("\n".join(await capacite.ajouter_aux_onglets())[:1990])
                await message.reply(capacite.texte_resume(await capacite.ecrire())[:1990])
                return True
            neufs = len(mots) > 1 and mots[1].lower() in ("neufs", "nouveaux", "regenerer", "régénérer")
            if neufs:
                await message.reply("⏳ Nouveaux identifiants pour toutes les créatrices, vérifiés sur Instagram. Quelques minutes.")
            await message.reply(capacite.texte_resume(await capacite.ecrire(neufs=neufs))[:1990])
        except Exception as erreur:                                     # noqa: BLE001
            await message.reply(f"❌ Build capacity : {type(erreur).__name__} {str(erreur)[:150]}")
        return True
    if mots[0].lower() == "!dashboard":                                # 28/09 : l'onglet Dashboard réécrit tout de suite, sans scan
        if not onboarding.actif():
            await message.reply("Classeur inactif : `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
            return True
        d = _lire()
        exclus = dashboard_masques(d)
        if len(mots) >= 3 and mots[1].lower() in ("exclure", "inclure"):     # `!dashboard exclure Julien` · `!dashboard inclure Rianah`
            prenom = " ".join(mots[2:]).strip()
            deja = [x for x in exclus if _norm(x) == _norm(prenom)]
            if mots[1].lower() == "exclure" and not deja:
                exclus.append(prenom)
            elif mots[1].lower() == "inclure":
                exclus = [x for x in exclus if _norm(x) != _norm(prenom)]
            d["dashboard_masques"] = exclus
            _ecrire(d)
        # 30/09 (Gaëtan : « tous les comptes GOOD, BAN et WARMUP, fais des vérifications à chaque fois que je fais !dashboard ») :
        # le passage complet (Instagram, états, followers, Reels hier, clics, regroupement) avant l'onglet ; `!dashboard rapide`
        # réécrit l'onglet seul, sans payer de scan
        if actif() and not (len(mots) > 1 and mots[1].lower() in ("rapide", "vite")):
            await message.reply("⏳ Je vérifie tous les comptes sur Instagram (GOOD, WARMUP, PRIVE, BAN, à créer réservés), puis je réécris le Dashboard. Quelques minutes.")
            bilan = await executer(ecrire=True)
            await message.reply(texte_bilan(bilan)[:1990])
            if bilan.get("erreur"):
                return True
            d = _lire()
        try:
            n = await ecrire_dashboard(await onboarding.lire_comptes(), d.get("historique", {}), _deps.get("clics_7j"),
                                       datetime.now(timezone.utc).strftime("%Y-%m-%d"), exclus)
            import capacite
            await message.reply(f"✅ Onglet « {ONGLET_DASHBOARD} » du classeur des logins réécrit ({n} lignes) : une ligne par clipper, par créatrice."
                                + (f"\n{capacite.texte_resume(CAPACITE)}" if CAPACITE else "")
                                + (f"\nMasqués : {', '.join(exclus)} (`!dashboard inclure Prénom` pour remettre quelqu'un)." if exclus
                                   else "\nPersonne n'est masqué, Julien et Rianah compris (`!dashboard exclure Prénom` pour masquer)."))
        except Exception as erreur:                                     # noqa: BLE001
            await message.reply(f"❌ Dashboard : {type(erreur).__name__} {str(erreur)[:150]}")
        return True
    if not actif():
        await message.reply("États du classeur inactifs : il faut `APIFY_TOKEN`, `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
        return True
    test = len(mots) > 1 and mots[1].lower() == "test"
    await message.reply("⏳ Je regarde Instagram…")
    bilan = await executer(ecrire=not test)
    await message.reply(texte_bilan(bilan, test)[:1990])
    return True
