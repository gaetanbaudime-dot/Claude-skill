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
`!dashboard` lançait ce passage complet avant de réécrire l'onglet (30/09) ; depuis le 09/10, `!dashboard` réécrit sans scan et
`!dashboard scan` lance le passage complet (payant).
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
09/10 (dashboard — Gaëtan : « le dashboard se met à jour constamment, le plus précis possible, pas de trucs pas précis ») :
  - jamais un faux 0 : followersCount absent ou non numérique = followers non lus (rien écrit) ; 0 alors que le compte en avait
    plus de SUSPECT_FOLLOWERS = suspect (cellule gardée, listé au bilan) ; latestPosts vide alors que postsCount > 0 = Reels non
    lus (cellules gardées) ; une erreur Apify n'est « introuvable » que si elle le dit (not found, does not exist…), sinon non lu ;
  - publications épinglées (isPinned) hors du décompte des Reels et de `plafonne` ;
  - chaque compte lu ajoute un relevé à sa série (series.py, contrat C1 : followers, Reels, vues, id Instagram) ;
  - ETAT, Followers et Reels partent en UN lot à la fin du passage, après relecture du classeur : chaque ligne est retrouvée par
    son @ dans son onglet (jamais par un numéro de ligne lu au début), un ETAT n'est écrit que si la cellule n'a pas bougé entre-
    temps, un changement n'entre au bilan que si l'écriture a réussi, une ligne disparue ou déplacée est signalée ;
  - passages LÉGERS (`executer(leger=True)`, heures de Paris ETATS_HEURES_LEGERES, défaut 14 h et 20 h) : Followers, Reels et
    séries des comptes vivants, sans aucune décision, sous garde du budget Apify du mois (`apify_budget`) ;
  - `!dashboard` réécrit sans scan, `!dashboard scan` lance le passage complet payant ; `!etats-comptes leger` : un passage léger.
09/10 (Gaëtan, 7 h 40 UTC : « Dépasse pas 25 $ / mois pour le moment, fais comme tu peux ») : la dépense Apify TOTALE du cycle
(tous les acteurs : scan, relectures, recherches des @ changés, scan du soir, identifiants neufs, cadence) est plafonnée à
APIFY_BUDGET_MOIS (25 $). Dépense lue par l'API Apify (users/me/limits, au plus toutes les 30 min) plus les appels faits depuis,
à défaut comptée ici (profils demandés × APIFY_PRIX_1000, 2,30 $ les mille), gardée dans etats_comptes.json par cycle. Une
relecture légère ne part que si la dépense, elle comprise, reste sous la trajectoire linéaire du budget ; un appel qui ferait
dépasser le budget est refusé, et à 100 % plus aucun appel Apify jusqu'au cycle suivant (alerte admin une fois par jour, le
Dashboard le dit : clé « apify_budget », contrat C6a).
Le module ne connaît pas bot_discord : dépendances dans `configurer(deps)` (lire_json, ecrire_json, FICHIER_ETATS,
normaliser, canal_admin, notifier, est_staff ; `scanner` optionnel pour les tests ; `FICHIER_SERIES` facultatif, sinon
series_comptes.json à côté de FICHIER_ETATS)."""
import asyncio
import calendar
import logging
import os
import re
import time as _horloge
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import aiohttp

import google_api
import onboarding
import series

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
# 09/10 (dashboard) : Apify coupe un appel synchrone à 300 s (code 408) ; le bot attend un peu plus pour recevoir sa réponse
# au lieu d'abandonner le premier (avant : 280 s, la course continuait et était payée pour rien)
APIFY_TIMEOUT = 310
SUSPECT_FOLLOWERS = 20                 # 09/10 (dashboard) : 0 lu alors que le compte en avait plus = fiche suspecte, rien écrit


def _heures(brut: str) -> list:
    out = set()
    for x in str(brut or "").split(","):
        try:
            h = int(x.strip())
        except ValueError:
            continue
        if 0 <= h <= 23:
            out.add(h)
    return sorted(out)


def _flottant(brut, defaut: float) -> float:
    """Un nombre de l'environnement (« 2,30 » ou « 2.30 ») ; le défaut s'il est absent, illisible ou négatif."""
    try:
        v = float(str(brut).strip().replace(",", "."))
    except (TypeError, ValueError):
        return defaut
    return v if v == v and v >= 0 else defaut


# 09/10 (dashboard) : passages légers aux heures de Paris (Followers, Reels, séries ; aucune décision) ; vide = éteints
HEURES_LEGERES = _heures(os.environ.get("ETATS_HEURES_LEGERES", "14,20"))
LEGER_APRES_COMPLET_H = 2              # un passage léger juste après le passage complet ne relirait rien de neuf
# 09/10 (Gaëtan : « Dépasse pas 25 $ / mois pour le moment ») : budget Apify TOTAL du cycle, et prix compté localement quand l'API
# Apify ne répond pas (profils demandés ; publications lues pour la cadence)
APIFY_BUDGET_MOIS = _flottant(os.environ.get("APIFY_BUDGET_MOIS"), 25.0)
APIFY_PRIX_1000 = _flottant(os.environ.get("APIFY_PRIX_1000"), 2.30)
BUDGET_CACHE_MIN = 30                  # l'API Apify (dépense du cycle) relue au plus toutes les 30 min
RECOUVREMENT_API_MIN = 15              # un appel noté moins de 15 min avant la lecture de l'API compte encore (elle a du retard)
APIFY_LIMITES = "https://api.apify.com/v2/users/me/limits"

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps
    # 09/10 (dashboard) : les séries par compte (series.py) vivent à côté de l'état du scan, sauf FICHIER_SERIES explicite
    fichier = deps.get("FICHIER_SERIES") or (Path(str(deps["FICHIER_ETATS"])).with_name("series_comptes.json")
                                             if deps.get("FICHIER_ETATS") else None)
    if fichier and deps.get("lire_json") and deps.get("ecrire_json"):
        series.configurer({"lire_json": deps["lire_json"], "ecrire_json": deps["ecrire_json"], "FICHIER_SERIES": fichier})


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


# 09/10 (revue) : clés de etats_comptes.json écrites PENDANT un passage complet par d'autres que lui (garde et dépense du budget
# Apify, heures légères faites, alertes du jour, essais de la boucle) : le passage complet, qui réécrit à la fin l'état lu au
# début, les reprend du disque au lieu de les écraser (avant : la dépense des recherches de variantes et « legers » perdues)
CLES_EXTERNES = ("apify_budget", "apify_local", "legers", "leger_iso", "alertes_legeres", "essais", "soir", "dashboard_masques",
                 "dashboard_exclus")


def _ecrire_passage(d: dict):
    """Écrit l'état d'un passage complet en gardant les CLES_EXTERNES telles qu'elles sont sur le disque."""
    try:
        disque = _lire()
    except Exception:                                                   # noqa: BLE001
        disque = {}
    for k in CLES_EXTERNES:
        if k in disque:
            d[k] = disque[k]
    _ecrire(d)


def _maj_etat(cles: dict):
    """Quelques clés posées sur l'état relu à l'instant (lecture, modification, écriture sans `await` au milieu)."""
    d = _lire()
    d.update(cles)
    _ecrire(d)


def _etat_configure() -> bool:
    return bool(_deps.get("lire_json") and _deps.get("ecrire_json") and _deps.get("FICHIER_ETATS"))


# ------------------------------------------------------------------ Instagram
async def scanner(handles: list) -> dict:
    """Un appel Apify pour tous les comptes → {clé: {lu, existe, prive, restreint, followers, posts, reels_hier, reels_7j, posts_lus…}} ;
    `posts` = publications des dernières 24 h (compatibilité : message du matin, parcours, sortie auto), `reels_hier` / `reels_7j` =
    Reels (vidéos) de la veille et des 7 derniers jours en jour civil de Paris. None si Apify est en panne : on ne conclut rien.
    05/10 : `lu` = Apify a répondu pour ce compte (fiche, ou erreur explicite « introuvable »). Un compte absent de la réponse après
    la deuxième demande, ou renvoyé sans aucun chiffre (mur de connexion, page incomplète), est `lu: False` : l'appelant n'en conclut
    rien et n'écrit rien. `existe: False` avec `lu: True` = Apify a bien dit que le compte n'existe pas (banni, renommé, jamais créé).
    09/10 (budget de Gaëtan, 25 $ / mois) : rien n'est demandé si le scan ferait dépasser le budget Apify du mois (None, comme une
    panne : personne n'en conclut rien) ; un compte d'un lot refusé en route est rendu `lu: False, budget: True` (jamais compté
    comme un passage non lu, qui mène au BAN). Toute fonction du bot qui lit Instagram passe par ici (passages, recherche des @
    changés, scan du soir, identifiants neufs, followers de la cadence)."""
    cles = []
    for h in handles or []:                                              # 05/10 : identifiants nettoyés, sans doublon
        k = _cle(h)
        if k and k not in cles:
            cles.append(k)
    if not await garde_apify(len(cles) * APIFY_PRIX_1000 / 1000, "profils Instagram"):
        return None
    if _deps.get("scanner"):
        return await _deps["scanner"](handles)
    if not APIFY_TOKEN or not handles:
        return None
    refuses = set()                                                      # 09/10 : comptes de lots refusés par la garde du budget
    items = await _apify(cles, refuses)
    if items is None:
        return None
    # 30/09 : un compte absent de la réponse d'Apify n'est pas forcément mort (profil sauté par le robot) : les absents sont
    # redemandés une fois, à part, avant de conclure
    vus = {_handle_item(it) for it in items}
    manquants = [h for h in cles if h not in vus and h not in refuses]
    if manquants:
        journal.info("Apify (états) : %d compte(s) sur %d absent(s) de la première réponse, redemandés à part", len(manquants), len(cles))
        encore = await _apify(manquants, refuses)
        items += encore or []
    out = _lire_items(items, cles)
    for h in refuses:                                                    # 09/10 : lot refusé (budget) : non lu, sans compter de jour
        if h in out and not out[h]["lu"]:
            out[h]["budget"] = True
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


async def _apify(handles: list, refuses: set = None):
    """Les fiches Apify brutes de `handles`, par lots ; None si Apify est en panne (aucun lot lu).
    09/10 (dashboard) : un lot en échec ne fait plus tout jeter — les lots réussis sont gardés, les comptes du lot raté manquent
    à la réponse (redemandés une fois par `scanner`, puis « non lus »).
    09/10 (budget) : chaque lot passe la garde du budget du mois (refusé s'il le ferait dépasser : ses comptes vont dans
    `refuses` et `_derniers_refuses`) et sa dépense est notée (profils demandés × APIFY_PRIX_1000 ; un lot raté en route est compté aussi, la
    course continue chez Apify ; un refus HTTP 4xx ne l'est pas, rien n'a tourné)."""
    _derniers_refuses.clear()
    url = f"https://api.apify.com/v2/acts/{ACTOR_IG}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    items, reussis, rates = [], 0, 0
    for i in range(0, len(handles), LOT):                              # par lots : 130 comptes tiennent en deux ou trois appels
        lot_h = handles[i:i + LOT]
        cout = len(lot_h) * APIFY_PRIX_1000 / 1000
        if not await garde_apify(cout, "profils Instagram"):
            _derniers_refuses.update(lot_h)
            if refuses is not None:
                refuses.update(lot_h)
            continue
        paye = True
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=APIFY_TIMEOUT)) as session:
                async with session.post(url, json={"usernames": lot_h}) as reponse:
                    if reponse.status >= 400:
                        journal.error("Apify HTTP %s (états du classeur, lot %d)", reponse.status, i // LOT + 1)
                        paye = reponse.status >= 500 or reponse.status == 408       # 408 : la course a tourné 300 s, elle est payée
                        rates += 1
                        continue
                    lot = await reponse.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as erreur:
            journal.error("Apify injoignable (états du classeur, lot %d) : %s", i // LOT + 1, type(erreur).__name__)
            rates += 1
            continue
        finally:
            if paye:
                noter_depense(cout, len(lot_h), "profils Instagram")
        reussis += 1
        items += lot if isinstance(lot, list) else []
    if rates and reussis:
        journal.warning("Apify (états) : %d lot(s) raté(s) sur %d, les lots lus sont gardés", rates, rates + reussis)
    if _derniers_refuses:
        journal.warning("Apify (états) : %d compte(s) non demandé(s), le lot ferait dépasser le budget du mois", len(_derniers_refuses))
    return items if reussis else None


_derniers_refuses = set()                                               # 09/10 : comptes du dernier _apify refusés par la garde du budget


def _fiche_vide() -> dict:
    return {"lu": False, "existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0, "fautes": 0,
            "reels_hier": 0, "reels_7j": 0, "posts_lus": 0, "bio_liens": [], "bio_lu": False, "lien_dans_texte": False,
            "nom": "", "bio": ""}


# 09/10 (dashboard) : seule une erreur qui DIT que le compte n'existe pas vaut « introuvable » (→ BAN possible) ; toute autre
# erreur d'Apify (limite, page indisponible, délai…) laisse le compte « non lu » : rien n'est conclu ni écrit
RE_INTROUVABLE = re.compile(r"not[\s_-]?found|does\s?n[o'’]?t\s+exist|does\s+not\s+exist|no\s+such\s+(user|profile|account)"
                            r"|introuvable|n['’]existe\s+pas|page\s+(isn['’]t|is\s+not)\s+available", re.I)


def _nombre(v):
    """Un compteur Apify lisible (entier ou flottant, pas un booléen) → int ; sinon None (« 1,2k », None, texte : non lu)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
        return None
    return int(v)


def _quand_post(post: dict):
    try:
        quand = datetime.fromisoformat(str(post.get("timestamp") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return quand if quand.tzinfo else quand.replace(tzinfo=timezone.utc)


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
    """([(ligne, nouveau @)], [ligne]) : les comptes retrouvés sous un @ proche (un seul profil qui est à nous), et les introuvables.
    09/10 (revue) : une ligne dont au moins une variante est revenue NON LUE (lot Apify raté ou refusé par le budget, fiche
    illisible) n'est ni trouvée ni perdue — ni renommée, ni « introuvable » pour le clipper : elle est recherchée au passage
    suivant. Seule une ligne dont TOUTES les variantes ont été lues peut être déclarée perdue."""
    cands = {id(c): variantes(c["handle"]) for c in lignes}
    tous = sorted({v for vs in cands.values() for v in vs})
    if not tous:
        return [], list(lignes)
    mesures = await scanner(tous)
    if mesures is None:
        return [], []                                                   # Apify en panne : on ne conclut rien
    trouves, perdus = [], []
    for c in lignes:
        if any(isinstance(mesures.get(v), dict) and mesures[v].get("lu", True) is False for v in cands[id(c)]):
            continue                                                    # une variante non lue : on ne conclut rien pour cette ligne
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
        erreur = " ".join(str(item.get(k) or "") for k in ("error", "errorDescription")).strip().lower()
        restreint = bool(item.get("isRestrictedProfile") or "restricted" in erreur)
        if erreur and not restreint:
            if RE_INTROUVABLE.search(erreur):
                fiche["lu"] = True                                       # Apify DIT que le compte n'existe pas (banni, renommé…)
            else:
                fiche["erreur"] = erreur[:120]                           # 09/10 (dashboard) : toute autre erreur = non lu, rien conclu
            continue
        followers = _nombre(item.get("followersCount"))
        posts_total = _nombre(item.get("postsCount"))
        posts = [p for p in (item.get("latestPosts") or []) if isinstance(p, dict)]
        if not restreint and followers is None and not posts and item.get("private") is None and posts_total is None:
            # 05/10 : une fiche sans aucun chiffre (mur de connexion, page incomplète) n'est pas « 0 followers, 0 Reel » :
            # elle est illisible, le compte reste non lu et garde ses valeurs dans le classeur
            fiche["illisible"] = True
            continue
        prive = bool(item.get("private"))
        # 09/10 (dashboard) : followersCount absent ou non numérique → followers None (« non lu » : rien écrit, null dans la série),
        # jamais 0 ; un restreint cache ses chiffres (None aussi)
        fiche.update({"lu": True, "existe": True, "restreint": restreint, "prive": prive,
                      "followers": None if restreint else followers, "posts_total": posts_total,
                      "nom": str(item.get("fullName") or ""), "bio": str(item.get("biography") or ""),
                      "ig_id": str(item.get("id") or "").strip()})
        fiche["bio_liens"], fiche["bio_lu"], fiche["lien_dans_texte"] = _liens_profil(item)
        fiche["posts_lus"] = len(posts)
        # 09/10 (dashboard) : Reels lisibles = compte ni privé ni restreint, et au moins une publication non épinglée vue (ou latestPosts
        # montre tout le compte, 0 publication comprise) ; latestPosts vide (ou rien que des épinglées) alors que postsCount en
        # annonce d'autres, ou postsCount inconnu = Reels NON LUS → cellules gardées, jamais 0
        n_libres = sum(1 for p in posts if not p.get("isPinned"))
        fiche["reels_lus"] = not prive and not restreint and (n_libres > 0 or (posts_total is not None and posts_total <= len(posts)))
        serie_reels, plus_ancien = [], None
        for post in posts:
            quand = _quand_post(post)
            if quand is None:
                continue
            jour_paris = _paris(quand).date()
            epingle = bool(post.get("isPinned"))                         # 09/10 (dashboard) : une épinglée (souvent vieille) ne compte pas
            if not epingle:
                plus_ancien = quand if plus_ancien is None or quand < plus_ancien else plus_ancien
            if _est_reel(post) and not epingle:
                if jour_paris == hier:
                    fiche["reels_hier"] += 1
                if debut_7j <= jour_paris <= hier:
                    fiche["reels_7j"] += 1
                code = series.code_post(post)
                if code:                                                 # la série du compte (contrat C1) : vues = series.vues_post
                    serie_reels.append({"code": code, "publie": quand.astimezone(timezone.utc).isoformat(timespec="seconds"),
                                        "type": str(post.get("type") or "Video"), "vues": series.vues_post(post)})
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
        # décompte est un minimum (complété par l'historique du scan dans reels_7j_estime). 09/10 (dashboard) : la plus ancienne
        # NON épinglée (une épinglée de l'an dernier faisait conclure « non plafonné »), et seulement si latestPosts ne montre pas
        # tout le compte (moins de publications vues que postsCount ; sans postsCount, les 12 places prises)
        incomplet = len(posts) < posts_total if posts_total is not None else len(posts) >= 12
        fiche["plafonne"] = bool(plus_ancien is not None and incomplet and _paris(plus_ancien).date() >= debut_7j)
        # 09/10 (dashboard) : depuis quand ce relevé voit TOUTES les publications ("" = tout le compte est visible)
        if posts_total is not None and not incomplet:
            fiche["couvre"] = ""
        else:
            fiche["couvre"] = (plus_ancien or maintenant).astimezone(timezone.utc).isoformat(timespec="seconds")
        fiche["serie_reels"] = serie_reels
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
        if j.get("existe") and (j.get("restreint") or j.get("reels_non_lus")) and not j.get("posts"):
            continue                                                    # 09/10 (dashboard) : Reels non lus ce jour-là = sauté, pas « 0 »
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
_verrou = (None, None)


def _verrou_passages() -> asyncio.Lock:
    """Le verrou des passages (complet, léger), créé dans la boucle asyncio qui tourne (même modèle que parcours._verrou_programme)."""
    global _verrou
    boucle_a = asyncio.get_running_loop()
    if _verrou[0] is not boucle_a:
        _verrou = (boucle_a, asyncio.Lock())
    return _verrou[1]


async def executer(ecrire: bool = True, leger: bool = False) -> dict:
    """Un seul passage à la fois (30/09 : `!dashboard` scanne aussi ; deux scans en même temps écriraient deux fois).
    09/10 (dashboard) : `leger=True` = passage léger (Followers, Reels et séries des comptes vivants, aucune décision)."""
    async with _verrou_passages():
        return await (_executer_leger(ecrire) if leger else _executer(ecrire))


# ------------------------------------------------------------------ 09/10 (dashboard) : chiffres justes, écritures fiables
def _instant(x):
    """Un instant ISO (sans fuseau = UTC) ; None si illisible."""
    if not x:
        return None
    try:
        dt = datetime.fromisoformat(str(x).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _propre(v) -> str:
    """Une cellule comparable : sans espace (« 1 234 » = « 1234 »)."""
    return re.sub(r"[\s  ]", "", str(v if v is not None else ""))


def _chiffre(v):
    """Le nombre d'une cellule ; None si vide ou illisible."""
    t = _propre(v)
    return int(t) if t.isdigit() else None


def _debut_jour_paris(maintenant: datetime, jours_avant: int = 0) -> datetime:
    """Minuit (heure de Paris) du jour de `maintenant` moins `jours_avant` jours."""
    p = _paris(maintenant)
    j = p.date() - timedelta(days=jours_avant)
    return datetime(j.year, j.month, j.day, tzinfo=p.tzinfo)


def _preuves(h: str, m: dict, hist: list) -> tuple:
    """09/10 (revue : le compte neuf d'un clipper, retrouvé sous un @ proche, restait « suspect » pour toujours à cause des abonnés
    de l'inconnu qui avait pris le @ prévu) : (historique utilisable, clé de la série de CE compte, cellule utilisable). Avec l'id
    Instagram de la fiche, la série est celle qui porte cet id (sous quelque @ que ce soit) ; si la série de cette clé porte un
    AUTRE id, l'historique et la cellule sont ceux de l'autre compte. Une cellule ne sert de preuve que pour un compte déjà suivi
    (historique sous cette clé, ou série de ce compte) : celle d'un @ jamais scanné vient d'ailleurs (ancien @ de la ligne)."""
    ig = str(m.get("ig_id") or "").strip()
    cle_s, autre = h, False
    if ig:
        try:
            sid, cle_s = series.id_instagram(h), series.cle_du_compte(ig)
        except Exception:                                               # noqa: BLE001
            sid, cle_s = "", h
        autre = bool(sid) and sid != ig
        if not cle_s and not autre:
            cle_s = h                                                   # série sans id (relevés d'avant, Metricool) : la sienne
    hist_ok = [] if autre else list(hist or [])
    try:
        suivi = bool(cle_s) and bool(series.derniere_lecture(cle_s))
    except Exception:                                                   # noqa: BLE001
        suivi = False
    return hist_ok, cle_s, (not autre and (bool(hist_ok) or suivi))


def _suspect(h: str, m: dict, hist: list, cellule) -> bool:
    """0 follower lu alors que le compte en avait plus de SUSPECT_FOLLOWERS (historique du scan, série, cellule du classeur) :
    fiche suspecte (un compte vivant ne perd pas tous ses abonnés d'un coup). Un compte neuf à 0 reste écrit à 0. 09/10 (revue) :
    jamais d'après les chiffres d'un autre compte (voir _preuves)."""
    f = m.get("followers")
    if not m.get("existe") or m.get("restreint") or isinstance(f, bool) or f != 0:
        return False
    hist_ok, cle_s, cellule_ok = _preuves(h, m, hist)
    try:
        dans_serie = series.followers_a(cle_s) if cle_s else None
    except Exception:                                                   # noqa: BLE001
        dans_serie = None
    avant = [e.get("followers") for e in hist_ok] + [dans_serie] + ([_chiffre(cellule)] if cellule_ok else [])
    return any(isinstance(x, int) and not isinstance(x, bool) and x > SUSPECT_FOLLOWERS for x in avant)


def _publie_d_habitude(h: str, m: dict, hist: list) -> bool:
    """09/10 (revue) : le compte publie (une publication vue par un passage des 14 derniers jours, ou postsCount > 0 dans un relevé
    Apify de moins de 14 jours de la série de ce compte) — une fiche qui annonce 0 publication est alors dégradée."""
    hist_ok, cle_s, _ = _preuves(h, m, hist)
    if any(int(e.get("posts_lus") or 0) > 0 or int(e.get("posts") or 0) > 0 for e in hist_ok if e.get("existe")):
        return True
    if not cle_s:
        return False
    try:
        r = series.dernier_releve(cle_s, source="apify")
    except Exception:                                                   # noqa: BLE001
        return False
    t = _instant((r or {}).get("t"))
    n = (r or {}).get("posts_total")
    return isinstance(n, int) and not isinstance(n, bool) and n > 0 and t is not None \
        and datetime.now(timezone.utc) - t <= timedelta(days=JOURS_HISTORIQUE)


def _controler(lignes: list, mesures: dict, ids_non_lus: set, d: dict) -> tuple:
    """Les fiches lues passées au crible des faux 0 : ([lignes à followers suspects], [lignes à Reels non lus]). Un suspect perd
    ses followers (None : rien écrit, null dans la série).
    09/10 (revue : fiche « tout à zéro » — followersCount 0, postsCount 0, latestPosts vide — jugée suspecte pour les followers mais
    crue pour les Reels, « Reels Hier » passait à 0) : une fiche suspecte sans aucune publication vue, ou qui annonce 0 publication
    alors que le compte publie, a aussi ses Reels NON LUS — cellules gardées, jour sauté dans l'historique, relevé de série qui ne
    couvre rien et ne certifie aucun 0. Une fiche suspecte qui montre des publications garde ses Reels (elles sont bien là)."""
    suspects, reels_nl, vus = [], [], set()
    for c in lignes:
        h = _cle(c["handle"])
        m = mesures.get(h)
        if id(c) in ids_non_lus or h in vus or not isinstance(m, dict) or not m.get("lu", True) or not m.get("existe"):
            continue
        vus.add(h)
        hist = (d.get("historique") or {}).get(h, [])
        suspect = _suspect(h, m, hist, c.get("followers"))
        if suspect:
            m["followers"] = None
            m["followers_suspect"] = True
            suspects.append(c)
        lisible = not m.get("restreint") and not m.get("prive")
        sans_publication = not int(m.get("posts_lus") or 0)
        if lisible and m.get("reels_lus", True) and sans_publication \
                and (suspect or (m.get("posts_total") == 0 and _publie_d_habitude(h, m, hist))):
            m["reels_lus"] = False                                      # la fiche ne prouve pas « 0 Reel »
            m["reels_suspects"] = True
            m.pop("couvre", None)
            if m.get("posts_total") == 0:
                m["posts_total"] = None                                 # « 0 publication » d'une fiche dégradée : non lu
        if not m.get("reels_lus", True) and lisible:
            reels_nl.append(c)
    return suspects, reels_nl


def _alimenter_series(lignes: list, mesures: dict, ids_non_lus: set, t_iso: str) -> int:
    """Un relevé par compte LU et vivant (jamais pour un non-lu ni un introuvable) dans series_comptes.json (contrat C1), en une
    seule écriture. La série ne bloque jamais le passage."""
    entrees, vus = [], set()
    for c in lignes:
        h = _cle(c["handle"])
        m = mesures.get(h)
        if id(c) in ids_non_lus or h in vus or not isinstance(m, dict) or not m.get("lu", True) or not m.get("existe") \
                or m.get("force_absent"):
            continue
        vus.add(h)
        lisible = not m.get("restreint") and not m.get("prive")
        f = m.get("followers")
        rel = {"t": t_iso, "source": "apify", "followers": None if m.get("restreint") or isinstance(f, bool) else f,
               "posts_total": m.get("posts_total"), "restreint": bool(m.get("restreint")), "prive": bool(m.get("prive")),
               "reels_lus": bool(lisible and m.get("reels_lus", True))}
        if "couvre" in m:
            rel["couvre"] = m["couvre"]
        entrees.append({"cle": h, "releve": rel, "reels": m.get("serie_reels") or [], "ig_id": m.get("ig_id") or ""})
    try:
        return series.ajouter_releves(entrees)
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Séries : relevés non enregistrés (%s)", type(erreur).__name__)
        return 0


def _followers_metricool(h: str):
    """Metricool prime sur Apify pour les followers des comptes branchés (source officielle, lisible même restreint) : son relevé
    de moins de 48 h dans la série, sinon None."""
    try:
        r = series.dernier_releve(h, source="metricool")
    except Exception:                                                   # noqa: BLE001
        return None
    f = (r or {}).get("followers")
    t = _instant((r or {}).get("t"))
    if isinstance(f, bool) or not isinstance(f, int) or t is None:
        return None
    return f if datetime.now(timezone.utc) - t <= timedelta(hours=48) else None


def _couvre_depuis(m: dict, depuis: datetime) -> bool:
    """09/10 (revue) : la fiche voit-elle TOUTES les publications depuis `depuis` ? `couvre` "" = tout le compte, une date = la plus
    ancienne publication non épinglée vue ; sans `couvre` (fiche d'avant le 09/10), on la croit comme avant."""
    if "couvre" not in m or m.get("couvre") == "":
        return True
    c = _instant(m.get("couvre"))
    return c is not None and c <= depuis


def _historique_complet(hist_prec: list, jour: str) -> bool:
    """Les 6 jours qui précèdent `jour` ont chacun un passage complet qui a lu les Reels de sa veille (reels_7j_estime est alors
    un compte exact, pas un minorant)."""
    jours = {str(e.get("jour", ""))[:10] for e in hist_prec or []
             if e.get("existe") and "reels_hier" in e and not e.get("reels_non_lus") and not e.get("reels_hier_incomplet")
             and not e.get("restreint") and not e.get("prive")}
    try:
        j0 = date.fromisoformat(str(jour)[:10])
    except ValueError:
        return False
    return all((j0 - timedelta(days=k)).isoformat() in jours for k in range(1, 7))


def _reels_hier_sur(h: str, m: dict, maintenant: datetime):
    """Les Reels de la veille (Paris) d'une fiche lue, s'ils sont SÛRS : comptés par la fiche si elle voit toute la veille, sinon par
    la série (si elle couvre la veille) ; None si personne n'a vu toute la veille (12 publications d'aujourd'hui remplissent
    latestPosts, par exemple) — jamais un 0 par défaut."""
    n_hier = int(m.get("reels_hier") or 0)
    try:
        s_hier = series.reels_publies(h, _debut_jour_paris(maintenant, 1), _debut_jour_paris(maintenant), maintenant)
    except Exception:                                                   # noqa: BLE001
        s_hier = None
    if _couvre_depuis(m, _debut_jour_paris(maintenant, 1)):
        return max(n_hier, s_hier) if s_hier is not None else n_hier
    return max(n_hier, s_hier) if s_hier is not None else None


def _valeurs_reels(h: str, m: dict, hist_prec: list, jour: str, maintenant: datetime, cellule_7j=None) -> dict:
    """Les cellules Reels Hier / Reels 7 j d'une fiche lue : '' si le compte cache ses Reels (restreint, privé) ou n'existe plus ;
    rien (cellules gardées) si les Reels n'ont pas été lus ; sinon le meilleur des minorants — latestPosts du passage, historique
    du scan, série des passages précédents (même définition : vidéos non épinglées, jour civil de Paris).
    09/10 (revue : « Reels Hier » écrit à 0 alors que latestPosts ne voyait pas la veille) : une période que ni la fiche (`couvre`)
    ni la série ne voient en entier n'est pas écrite — « Reels Hier » est gardé ; « Reels 7 j » n'est écrit que si la fiche ou la
    série couvrent les 7 jours, ou si l'historique du scan les a tous comptés, sinon seulement s'il ne baisse pas la cellule."""
    if not m.get("existe") or m.get("restreint") or m.get("prive"):
        return {"reels_hier": "", "reels_7j": ""}
    if not m.get("reels_lus", True):
        return {}
    out = {}
    n_hier = _reels_hier_sur(h, m, maintenant)
    if n_hier is not None:
        out["reels_hier"] = str(n_hier)
    n_7j = reels_7j_estime(m, hist_prec, jour)
    try:
        s_7j = series.reels_publies(h, _debut_jour_paris(maintenant, 7), _debut_jour_paris(maintenant), maintenant)
    except Exception:                                                   # noqa: BLE001
        s_7j = None
    sur_7j = _couvre_depuis(m, _debut_jour_paris(maintenant, 7)) or s_7j is not None \
        or (n_hier is not None and _historique_complet(hist_prec, jour))
    n_7j = max(n_7j, s_7j) if s_7j is not None else n_7j
    n_7j = max(n_7j, n_hier or 0)
    cellule = _chiffre(cellule_7j)
    if sur_7j or (n_7j > 0 and (cellule is None or n_7j >= cellule)):      # un minimum de 0 ne prouve rien : jamais écrit
        out["reels_7j"] = str(n_7j)
    return out


def _ecritures_mesure(c: dict, m, hist_prec: list, jour: str, maintenant: datetime) -> list:
    """Les cellules Followers / Reels à écrire pour une ligne (seulement celles qui changent). `m` None = compte non lu par
    Apify : seuls des followers Metricool peuvent alors être écrits."""
    h, onglet, out = _cle(c["handle"]), c.get("onglet", ""), []
    f = _followers_metricool(h)
    if f is None and m and m.get("existe") and not m.get("restreint") and isinstance(m.get("followers"), int) \
            and not isinstance(m.get("followers"), bool):
        f = m["followers"]
    if f is not None and onboarding.a_colonne("followers", onglet) and _propre(f) != _propre(c.get("followers")):
        out.append({"c": c, "champ": "followers", "valeur": f})
    for champ, valeur in (_valeurs_reels(h, m, hist_prec, jour, maintenant, c.get("reels_7j")) if m else {}).items():
        if onboarding.a_colonne(champ, onglet) and _propre(valeur) != _propre(c.get(champ)):
            out.append({"c": c, "champ": champ, "valeur": valeur})
    return out


async def _envoyer_lot(ecr: list) -> set:
    """Les plages écrites. Un seul appel pour tout (une seule cellule : un appel simple, même coût) ; si Google refuse le lot
    (plage invalide, onglet renommé…), un nouvel essai onglet par onglet pour ne pas perdre les autres."""
    if not ecr:
        return set()
    cid = onboarding.CLASSEUR_LOGINS_ID

    async def _un(lot):
        if len(lot) == 1:
            await google_api.sheets_ecrire(cid, lot[0][0], lot[0][1])
        else:
            await google_api.sheets_ecrire_plusieurs(cid, lot)
    try:
        await _un(ecr)
        return {p for p, _ in ecr}
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Classeur : lot de %d cellule(s) refusé (%s)", len(ecr), type(erreur).__name__)
    par_onglet = {}
    for p, v in ecr:
        par_onglet.setdefault(p.rsplit("!", 1)[0], []).append((p, v))
    ok = set()
    if len(par_onglet) < 2:
        return ok
    for lot in par_onglet.values():
        try:
            await _un(lot)
            ok |= {p for p, _ in lot}
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Classeur : %d cellule(s) d'un onglet non écrites (%s)", len(lot), type(erreur).__name__)
    return ok


async def _ecrire_lot(ecritures: list) -> tuple:
    """(faites, perdues [(écriture, raison)], relus) : le classeur est relu juste avant d'écrire, chaque écriture va sur la ligne
    retrouvée par son @ dans SON onglet (toutes les lignes de ce @ dans l'onglet, doublons compris), jamais sur un numéro de ligne
    lu au début du passage ; un ETAT n'est écrit que si la cellule vaut encore ce que le passage a lu (un changement à la main
    pendant le passage gagne). Une ligne disparue ou passée dans un autre onglet : rien écrit, signalé. Tout part en un appel."""
    if not ecritures:
        return [], [], None
    try:
        relus = await onboarding.lire_comptes()
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Classeur : relecture impossible avant d'écrire (%s), rien écrit", type(erreur).__name__)
        return [], [(e, "classeur illisible au moment d'écrire") for e in ecritures], None
    index = {}
    for r in relus:
        k = _cle(r.get("handle") or "")
        if k:
            index.setdefault(k, []).append(r)
    plages, prevues, perdues = {}, [], []
    for e in ecritures:
        c = e["c"]
        k, onglet = _cle(c["handle"]), c.get("onglet", "")
        toutes = index.get(k) or []
        ici = [r for r in toutes if r.get("onglet", "") == onglet]
        if not ici:
            perdues.append((e, "ligne passée dans un autre onglet" if toutes else "ligne disparue du classeur"))
            continue
        # 09/10 (revue) : l'en-tête RELU porte-t-il encore la colonne ? (« Reels 7 j » retouché pendant le passage : la lettre
        # retombait sur la colonne A et le nombre de Reels écrasait l'ETAT de la ligne)
        if e["champ"] != "etat" and not onboarding.a_colonne(e["champ"], onglet):
            perdues.append((e, "colonne introuvable dans l'en-tête"))
            continue
        if e["champ"] == "etat":
            ici = [r for r in ici if _norm(r.get("etat") or "") == _norm(e.get("attendu") or "")]
            if not ici:
                perdues.append((e, "ETAT changé dans le classeur pendant le passage"))
                continue
        else:
            ici = [r for r in ici if _propre(r.get(e["champ"])) != _propre(e["valeur"])]
            if not ici:
                continue                                                # la cellule a déjà la bonne valeur
        e["plages"] = []
        for r in ici:
            p = onboarding.cellule(r, e["champ"])
            if p in plages and _propre(plages[p]) != _propre(e["valeur"]):
                continue                                                # deux valeurs pour une cellule : la première gagne
            plages[p] = e["valeur"]
            e["plages"].append((p, r))
        if e["plages"]:
            prevues.append(e)
        else:
            perdues.append((e, "deux valeurs pour la même cellule"))
    ok = await _envoyer_lot([(p, [[v]]) for p, v in plages.items()])
    faites = []
    for e in prevues:
        bonnes = [(p, r) for p, r in e["plages"] if p in ok]
        if not bonnes:
            perdues.append((e, "écriture refusée par Google"))
            continue
        faites.append(e)
        for _, r in bonnes:
            r[e["champ"]] = str(e["valeur"])                            # la relecture porte la valeur écrite (suite du passage)
    return faites, perdues, relus


def _txt_ligne(c: dict) -> str:
    return f"`{c['handle']}` ({c.get('gerant') or 'sans gérant'})"


def _txt_perdue(e: dict, raison: str) -> str:
    noms = {"etat": "ETAT", "followers": "Followers", "reels_hier": "Reels Hier", "reels_7j": "Reels 7 j"}
    return f"`{e['c']['handle']}` ({e['c'].get('onglet', '')}, {noms.get(e['champ'], e['champ'])}) : {raison}"


def _resume_passage(mode: str, maintenant: datetime, lignes: list, mesures: dict, non_lus: list, suspects: list,
                    reels_nl: list, perdues: list) -> dict:
    """09/10 (dashboard) : ce que le dernier passage a lu, gardé dans etats_comptes.json (« dernier_passage ») pour le Dashboard
    et le contrôle : clés de compte seulement."""
    cles = {_cle(c["handle"]) for c in lignes}
    return {"t": maintenant.isoformat(timespec="seconds"), "mode": mode, "demandes": len(cles),
            "non_lus": sorted({_cle(c["handle"]) for c in non_lus}),
            "restreints": sorted(h for h in cles if isinstance(mesures.get(h), dict) and mesures[h].get("restreint")),
            "introuvables": sorted(h for h in cles if isinstance(mesures.get(h), dict) and mesures[h].get("lu", True)
                                   and not mesures[h].get("existe") and h not in {_cle(c["handle"]) for c in non_lus}),
            "suspects": sorted({_cle(c["handle"]) for c in suspects}), "reels_non_lus": sorted({_cle(c["handle"]) for c in reels_nl}),
            "perdues": len(perdues)}


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
    t_refus = _horloge.monotonic()
    mesures = await scanner([_cle(c["handle"]) for c in lignes])
    if mesures is None:
        return {"changements": [], "scannes": 0, "erreur": _erreur_budget(t_refus) or "Instagram illisible aujourd'hui (Apify), rien changé"}
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
        if m is not None and m.get("budget"):                           # 09/10 : pas demandé (budget du mois) : non lu, sans compter
            non_lus.append(c)
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
    maintenant = datetime.now(timezone.utc)
    # 09/10 (dashboard) : les faux 0 écartés avant toute décision ou écriture, puis un relevé par compte lu dans sa série
    suspects, reels_nl = _controler(lignes, mesures, ids_non_lus, d)
    if ecrire:
        _alimenter_series(lignes, mesures, ids_non_lus, maintenant.isoformat(timespec="seconds"))
    changements, followers_maj, clics_maj, liens_maj, reels_maj = [], 0, 0, 0, 0
    restreints_n = absents_n = forces_n = 0
    ecritures = []                                                       # 09/10 (dashboard) : ETAT, Followers et Reels, un lot à la fin
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

    def _appliquer(c, apres):
        # 09/10 (dashboard) : l'ETAT part dans le lot de la fin (ligne retrouvée par son @, ETAT inchangé entre-temps) ; il n'entre
        # au bilan, et BAN / avant_ban ne sont notés, qu'une fois l'écriture faite
        if not ecrire:
            changements.append((c["handle"], c["gerant"], c["etat"], apres, c["ligne"]))
            return
        ecritures.append({"c": c, "champ": "etat", "valeur": apres, "attendu": c["etat"], "changement": True})
    for c in lignes:
        if id(c) in ids_non_lus:
            if ecrire:                                                   # 09/10 (dashboard) : seuls des followers Metricool peuvent s'écrire
                ecritures += _ecritures_mesure(c, None, [], jour, maintenant)
            continue                                                     # 05/10 : non lu → rien d'écrit, rien de conclu, pas d'historique
        h = _cle(c["handle"])
        m = {**_fiche_vide(), **(mesures.get(h) or {})}
        restreints_n += 1 if m["restreint"] else 0
        absents_n += 0 if m["existe"] else 1
        forces_n += 1 if m.get("force_absent") else 0
        hist_prec = [x for x in d["historique"].get(h, []) if x.get("jour") != jour]
        # Followers : pour tout compte lisible (vivant, pas restreint) dont l'onglet a la colonne ; un restreint ou un introuvable
        # garde sa dernière valeur (05/10 : jamais vidé, jamais mis à 0 ; 09/10 : followers illisibles ou suspects non plus,
        # Metricool d'abord pour un compte branché).
        # 30/09 (Gaëtan : « une colonne Reels Hier, combien de Reels a posté chaque compte IG hier ») ; 05/10 : pour CHAQUE compte
        # scanné (plus seulement les lignes suivies), la veille en jour civil de Paris et les 7 derniers jours (colonne « Reels 7 j »),
        # seulement les cellules qui changent. Restreint ou privé : Reels illisibles → cellule vide, pas 0 ; introuvable (réponse
        # explicite d'Apify) : vide ; 09/10 : Reels non lus (latestPosts vide alors que le compte publie) → cellules gardées.
        if ecrire:
            ecritures += _ecritures_mesure(c, m, hist_prec, jour, maintenant)
        if m.get("reels") and c.get("gerant") and _en_gestion(c):
            a_relire += [{**r, "handle": h, "gerant": c["gerant"]} for r in m["reels"][:10]]   # 01/10 : review des Reels
        hist = list(hist_prec)
        entree = {"jour": jour, "existe": m["existe"], "posts": m["posts"], "prive": m["prive"], "fautes": m.get("fautes", 0),
                  "restreint": bool(m.get("restreint")), "followers": m.get("followers"),      # 09/10 : None = non lu, jamais 0
                  "reels_hier": int(m.get("reels_hier") or 0), "reels_7j": int(m.get("reels_7j") or 0),   # 05/10
                  "posts_lus": int(m.get("posts_lus") or 0)}
        if m["existe"] and not m["restreint"] and not m["prive"] and not m.get("reels_lus", True):
            entree["reels_non_lus"] = True                               # 09/10 (dashboard) : jour sauté, pas « 0 Reel »
        elif m["existe"] and not m["restreint"] and not m["prive"]:
            # 09/10 (revue) : la veille vue en entier ? Sinon « reels_hier » n'est qu'un minimum (latestPosts rempli par le jour même) :
            # noté, pour que « Reels 7 j » ne le prenne jamais pour un compte exact
            sur = _reels_hier_sur(h, m, maintenant)
            if sur is None:
                entree["reels_hier_incomplet"] = True
            else:
                entree["reels_hier"] = max(entree["reels_hier"], sur)
        hist.append(entree)
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
            _appliquer(c, apres)
    renommes_passe = {}                                                 # 09/10 (dashboard) : @ renommés pendant ce passage
    if ecrire and a_chercher:                                           # 09/10 : les @ légèrement changés
        # 09/10 (revue) : les comptes créés d'abord (WARMUP, PRIVE), les BAN récents ensuite ; une fois par jour et par compte
        # (`!dashboard` relance le scan), noté seulement pour ceux vraiment cherchés ; le reste attend le passage suivant
        a_chercher.sort(key=lambda x: x[0])
        lot = [c for _, c in a_chercher if d.setdefault("cherches", {}).get(_cle(c["handle"])) != jour]
        if len(lot) > VARIANTES_MAX:
            journal.info("Recherche des @ changés : %s comptes, %s cherchés ce passage", len(lot), VARIANTES_MAX)
        lot = lot[:VARIANTES_MAX]
        avant_cherches = {_cle(c["handle"]): d["cherches"].get(_cle(c["handle"])) for c in lot}
        for c in lot:
            d["cherches"][_cle(c["handle"])] = jour
        try:
            trouves, perdus = await chercher_variantes(lot) if lot else ([], [])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Recherche des @ changés : %s", erreur)
            trouves, perdus = [], []
        # 09/10 (revue) : une ligne ni trouvée ni perdue (une variante non lue : lot raté, budget, Apify en panne) n'a pas vraiment été
        # cherchée — pas notée « cherchée aujourd'hui » (elle repart au passage suivant) et pas de BAN différé conclu sans elle
        conclus = {id(c) for c, _ in trouves} | {id(c) for c in perdus}
        for c in lot:
            if id(c) not in conclus:
                h_i = _cle(c["handle"])
                if avant_cherches.get(h_i):
                    d["cherches"][h_i] = avant_cherches[h_i]
                else:
                    d["cherches"].pop(h_i, None)
                differes.pop(id(c), None)
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
            renommes_passe[h_c] = _cle(nouveau)                         # la ligne porte maintenant le nouvel @ (cellule réécrite)
            if _norm(c["etat"]) == "ban":                               # faux BAN : le compte vit sous son vrai @, état d'avant rendu
                retour = d.get("avant_ban", {}).get(h_c) or "WARMUP"
                ecritures.append({"c": c, "champ": "etat", "valeur": retour, "attendu": c["etat"], "retour": True})
            changements.append((c["handle"], c["gerant"], c["etat"], f"retrouvé sous {nouveau}", c["ligne"]))
        for c in perdus:
            if _norm(c["etat"]) in CREES and _deps.get("compte_introuvable"):
                try:
                    await _deps["compte_introuvable"](c["handle"])
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Compte introuvable %s : %s", c["handle"], erreur)
    for c, apres in list(differes.values()):                            # 09/10 (revue) : pas retrouvé → le BAN différé est écrit
        _appliquer(c, apres)
    # 09/10 (dashboard) : ETAT, Followers et Reels en UN lot, après relecture du classeur (voir _ecrire_lot). Une ligne renommée
    # pendant le passage est retrouvée sous son nouvel @ ; ses chiffres, mesurés sous l'ancien @ (introuvable), ne sont pas écrits.
    perdues = []
    if ecrire and ecritures:
        for e in ecritures:
            ancien = _cle(e["c"]["handle"])
            if ancien in renommes_passe:
                e["c"], e["cle"] = {**e["c"], "handle": renommes_passe[ancien]}, ancien
        ecritures = [e for e in ecritures if e["champ"] == "etat" or _cle(e["c"]["handle"]) not in renommes_passe.values()]
        faites, perdues, relus = await _ecrire_lot(ecritures)
        for e in faites:
            c, h_a = e["c"], e.get("cle") or _cle(e["c"]["handle"])     # bans_auto / avant_ban restent sous la clé du scan
            if e["champ"] == "followers":
                followers_maj += 1
            elif e["champ"] in ("reels_hier", "reels_7j"):
                reels_maj += 1
            elif e.get("changement"):
                changements.append((c["handle"], c["gerant"], c["etat"], e["valeur"], c["ligne"]))
                if e["valeur"] == "BAN":
                    d["bans_auto"][h_a] = jour
                    d.setdefault("avant_ban", {})[h_a] = str(c["etat"]).strip().upper().replace("É", "E")
                elif h_a in d["bans_auto"]:
                    d["bans_auto"].pop(h_a, None)
                    d.setdefault("avant_ban", {}).pop(h_a, None)
            elif e.get("retour"):
                d["bans_auto"].pop(h_a, None)
                d.setdefault("avant_ban", {}).pop(h_a, None)
        if perdues:
            journal.warning("Classeur : %d écriture(s) non faite(s) (ligne disparue ou déplacée, ETAT changé à la main, refus de Google)",
                            len(perdues))
        if relus is not None:
            comptes = relus                                             # la suite du passage part du classeur relu (valeurs écrites)
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
    if ecrire and _deps.get("verifier_classeur"):                                 # 29/09 : le classeur se vérifie seul, rien corrigé
        try:
            await _deps["verifier_classeur"](comptes, d["historique"])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Vérification du classeur : %s", erreur)
    if ecrire:
        d["dernier"] = jour
        d["version"] = VERSION
        d["dernier_passage"] = _resume_passage("complet", maintenant, lignes, mesures, non_lus, suspects, reels_nl, perdues)
        _ecrire_passage(d)
        # 09/10 (revue) : le Dashboard APRÈS l'enregistrement de l'état du passage (il relit etats_comptes.json : avant, il montrait
        # l'historique, les non lus et le dernier passage de la veille — un compte lu ce matin affiché « non lu »)
        try:                                                                        # 28/09 : l'onglet Dashboard
            await ecrire_dashboard(comptes, d["historique"], _deps.get("clics_7j"), jour, forme=True)   # 09/10 : + onglets, capacité
            _maj_etat({"dashboard_version": DASHBOARD_VERSION})
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : %s", erreur)
    # 05/10 : les compteurs du passage dans le journal (jamais d'identifiant de compte) — c'est ici qu'on lit, dans Railway, pourquoi
    # une cellule n'a pas bougé : non lu (Apify muet), restreint (chiffres cachés), introuvable (réponse explicite)
    journal.info("États du classeur : %d compte(s) scanné(s), %d non lu(s) laissés tels quels, %d restreint(s), %d introuvable(s) "
                 "(dont %d après %d passages non lus), %d changement(s), %d followers, %d cellules Reels, %d clics, %d liens mis à jour, "
                 "%d followers suspects, %d Reels non lus, %d écriture(s) perdue(s)",
                 len(lignes), len(non_lus), restreints_n, absents_n, forces_n, NON_LU_JOURS, len(changements), followers_maj, reels_maj,
                 clics_maj, liens_maj, len(suspects), len(reels_nl), len(perdues))
    avance = onboarding.comptes_d_avance(comptes)                        # 30/09 : comptes à créer sans Gérant, par créatrice
    restreints = sorted(f"`{c['handle']}` ({c['gerant']})" for c in lignes if c.get("gerant")
                        and (mesures.get(_cle(c["handle"])) or {}).get("restreint"))
    non_lus_txt = sorted(f"`{c['handle']}` ({c.get('gerant') or 'sans gérant'})" for c in non_lus)
    return {"changements": changements, "scannes": len(lignes), "erreur": "", "followers": followers_maj, "clics": clics_maj, "liens": liens_maj,
            "reels": reels_maj, "avance": avance, "restreints": restreints, "non_lus": non_lus_txt, "mode": "complet",
            "suspects": sorted(_txt_ligne(c) for c in suspects), "reels_non_lus": sorted(_txt_ligne(c) for c in reels_nl),
            "perdues": [_txt_perdue(e, r) for e, r in perdues]}


def _vivant(c: dict) -> bool:
    """09/10 (dashboard) : les lignes relues par le passage léger — un @, ni BAN, ni « à créer », ni Gérant libre."""
    e = _norm(c.get("etat") or "")
    g = _norm(c.get("gerant") or "").strip()
    return bool(c.get("handle")) and e not in A_CREER and e != "ban" and g not in GERANTS_LIBRES and g not in onboarding.GERANTS_LIBRES


async def _executer_leger(ecrire: bool = True) -> dict:
    """09/10 (dashboard) : passage LÉGER — Apify sur les seuls comptes vivants, puis Followers, Reels Hier, Reels 7 j et séries.
    Il ne décide AUCUN état, ne regroupe pas, ne met pas en forme, ne touche ni à la capacité, ni aux messages, ni à la recherche
    des @ changés, ni aux parcours, et n'écrit pas l'entrée du jour de l'historique (seul le passage complet du matin le fait).
    Un compte introuvable n'y est ni conclu ni vidé. Pas de bilan au salon (la boucle ne poste que les erreurs)."""
    vide = {"changements": [], "scannes": 0, "erreur": "", "mode": "leger", "followers": 0, "reels": 0, "clics": 0, "liens": 0}
    if not onboarding.actif():
        return {**vide, "erreur": "classeur non configuré"}
    comptes = await onboarding.lire_comptes()
    lignes = [c for c in a_scanner(comptes) if _vivant(c)]
    if not lignes:
        return vide
    t_refus = _horloge.monotonic()
    mesures = await scanner([_cle(c["handle"]) for c in lignes])
    if mesures is None:
        return {**vide, "scannes": len(lignes),
                "erreur": _erreur_budget(t_refus) or "Instagram illisible (Apify), passage léger sans effet"}
    non_lus = [c for c in lignes if not (isinstance(mesures.get(_cle(c["handle"])), dict) and mesures[_cle(c["handle"])].get("lu", True))]
    if non_lus and len(non_lus) * 2 > len(lignes):
        return {**vide, "scannes": len(lignes),
                "erreur": f"Apify n'a lu que {len(lignes) - len(non_lus)} compte(s) sur {len(lignes)}, passage léger sans effet"}
    ids_non_lus = {id(c) for c in non_lus}
    d = _lire()                                                         # lecture seule : historique (Reels 7 j, garde des faux 0)
    maintenant = datetime.now(timezone.utc)
    jour = maintenant.strftime("%Y-%m-%d")
    suspects, reels_nl = _controler(lignes, mesures, ids_non_lus, d)
    ecritures = []
    if ecrire:
        _alimenter_series(lignes, mesures, ids_non_lus, maintenant.isoformat(timespec="seconds"))
        for c in lignes:
            h = _cle(c["handle"])
            if id(c) in ids_non_lus:
                ecritures += _ecritures_mesure(c, None, [], jour, maintenant)
                continue
            m = {**_fiche_vide(), **(mesures.get(h) or {})}
            if not m["existe"]:
                continue                                                # introuvable : le passage complet du matin décide
            hist_prec = [x for x in (d.get("historique") or {}).get(h, []) if x.get("jour") != jour]
            ecritures += _ecritures_mesure(c, m, hist_prec, jour, maintenant)
    faites, perdues, _ = await _ecrire_lot(ecritures) if ecritures else ([], [], None)
    followers_maj = sum(1 for e in faites if e["champ"] == "followers")
    reels_maj = sum(1 for e in faites if e["champ"] in ("reels_hier", "reels_7j"))
    if ecrire:
        d2 = _lire()                                                    # relu juste avant : seules ces clés changent
        d2["leger_iso"] = maintenant.isoformat(timespec="seconds")
        d2["dernier_passage"] = _resume_passage("leger", maintenant, lignes, mesures, non_lus, suspects, reels_nl, perdues)
        # 09/10 (revue) : un compte non lu au passage du matin et LU (vivant) par ce passage n'est plus « non lu » (le Dashboard et le
        # contrôle l'affichaient « non lu » toute la journée) ; le compteur ne grandit jamais ici (seul le complet compte les jours)
        if isinstance(d2.get("non_lus"), dict):
            for c in lignes:
                h = _cle(c["handle"])
                m = mesures.get(h)
                if id(c) not in ids_non_lus and isinstance(m, dict) and m.get("lu", True) and m.get("existe"):
                    d2["non_lus"].pop(h, None)
        loc = d2.get("apify_local") if isinstance(d2.get("apify_local"), dict) else {}
        loc["cout_leger_usd"] = round(len({_cle(c["handle"]) for c in lignes}) * APIFY_PRIX_1000 / 1000, 4)   # le prochain, estimé
        d2["apify_local"] = loc
        _ecrire(d2)
    journal.info("Passage léger : %d compte(s) vivant(s) demandé(s), %d non lu(s), %d followers et %d cellules Reels mis à jour, "
                 "%d followers suspects, %d Reels non lus, %d écriture(s) perdue(s)", len(lignes), len(non_lus), followers_maj,
                 reels_maj, len(suspects), len(reels_nl), len(perdues))
    return {**vide, "scannes": len(lignes), "followers": followers_maj, "reels": reels_maj,
            "non_lus": sorted(_txt_ligne(c) for c in non_lus), "suspects": sorted(_txt_ligne(c) for c in suspects),
            "reels_non_lus": sorted(_txt_ligne(c) for c in reels_nl), "perdues": [_txt_perdue(e, r) for e, r in perdues],
            "restreints": sorted(_txt_ligne(c) for c in lignes if (mesures.get(_cle(c["handle"])) or {}).get("restreint"))}


# ------------------------------------------------------------------ 09/10 : budget Apify du mois (25 $, décision de Gaëtan) et passages légers
def _montant(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
        return None
    return float(v)


def _iso(dt) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds") if dt else ""


def _plus_un_mois(dt: datetime) -> datetime:
    a, m = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
    return dt.replace(year=a, month=m, day=min(dt.day, calendar.monthrange(a, m)[1]))


def _cycle(maintenant: datetime, api: dict = None) -> tuple:
    """(début, fin) du cycle de facturation Apify en cours : celui que l'API a donné (avancé d'un mois tant qu'il est fini), sinon
    le mois civil (UTC)."""
    api = api if isinstance(api, dict) else {}
    d0, d1 = _instant(api.get("cycle_debut")), _instant(api.get("cycle_fin"))
    if d0 is not None and d1 is not None and d1 > d0:
        n = 0
        while maintenant >= d1 and n < 36:
            d0, d1, n = d1, _plus_un_mois(d1), n + 1
        if d0 <= maintenant < d1:
            return d0, d1
    d0 = maintenant.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return d0, _plus_un_mois(d0)


def _lire_api(brut, maintenant: datetime):
    """La réponse de GET /v2/users/me/limits → {t, usage_usd, limite_usd, cycle_debut, cycle_fin} ; None si illisible."""
    data = brut.get("data", brut) if isinstance(brut, dict) else None
    if not isinstance(data, dict):
        return None
    usage = _montant((data.get("current") or {}).get("monthlyUsageUsd"))
    if usage is None:
        return None
    limite = _montant((data.get("limits") or {}).get("maxMonthlyUsageUsd")) or None
    cycle = data.get("monthlyUsageCycle") or {}
    d0, d1 = _instant(cycle.get("startAt")), _instant(cycle.get("endAt"))
    return {"t": _iso(maintenant), "usage_usd": round(usage, 4), "limite_usd": round(limite, 2) if limite else None,
            "cycle_debut": _iso(d0), "cycle_fin": _iso(d1)}


def _registre(d: dict) -> dict:
    """Le registre local du budget dans l'état (« apify_local ») : {api (dernière lecture de l'API), api_essai, entrees
    [[iso, usd, unités, quoi]] du cycle, cout_leger_usd}."""
    loc = d.get("apify_local") if isinstance(d.get("apify_local"), dict) else {}
    if not isinstance(loc.get("entrees"), list):
        loc["entrees"] = []
    d["apify_local"] = loc
    return loc


def _cout_leger(d: dict) -> float:
    """Ce que coûtera la prochaine relecture légère : celle d'avant (comptes vivants × prix), sinon les comptes du dernier passage."""
    loc = d.get("apify_local") if isinstance(d.get("apify_local"), dict) else {}
    c = _montant(loc.get("cout_leger_usd"))
    if c is not None:
        return c
    n = (d.get("dernier_passage") or {}).get("demandes") if isinstance(d.get("dernier_passage"), dict) else None
    return int(n) * APIFY_PRIX_1000 / 1000 if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0.0


def etat_budget(d: dict = None, maintenant: datetime = None) -> dict:
    """Le budget Apify du cycle (contrat C6a), calcul pur sur l'état (« apify_local ») :
    {t, source (« apify » : dernière lecture de l'API + appels notés depuis ; « local » : appels notés seulement), usage_usd,
     limite_usd (limite du compte Apify, si lue), budget_usd (APIFY_BUDGET_MOIS), trajectoire_usd (budget × part du cycle écoulée),
     part (usage ÷ budget), coupe (usage ≥ budget : plus aucun appel Apify), leger_ok (pas coupé, et la dépense, relecture légère
     comprise, reste sous la trajectoire), cycle_debut, cycle_fin}
    et, en plus : projete_usd (usage ÷ part écoulée, au moins 10 %), cout_leger_usd, api_t (heure de la dernière lecture de
    l'API), ok (= leger_ok, pour les lecteurs d'avant le 09/10)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if d is None:
        d = _lire() if _etat_configure() else {}
    loc = d.get("apify_local") if isinstance(d.get("apify_local"), dict) else {}
    api = loc.get("api") if isinstance(loc.get("api"), dict) else {}
    d0, d1 = _cycle(maintenant, api)
    entrees = []
    for e in loc.get("entrees") or []:
        t = _instant(e[0]) if isinstance(e, list) and e else None
        usd = _montant(e[1]) if isinstance(e, list) and len(e) > 1 else None
        if t is not None and usd is not None and d0 <= t <= maintenant + timedelta(minutes=5):
            entrees.append((t, usd))
    t_api, u_api = _instant(api.get("t")), _montant(api.get("usage_usd"))
    if t_api is not None and u_api is not None and d0 <= t_api <= maintenant + timedelta(minutes=5):
        # l'API compte avec quelques minutes de retard : un appel noté juste avant sa lecture compte encore (au pire compté deux
        # fois une demi-heure — prudent pour un plafond)
        usage, source = u_api + sum(u for t, u in entrees if t > t_api - timedelta(minutes=RECOUVREMENT_API_MIN)), "apify"
    else:
        usage, source = sum(u for _, u in entrees), "local"
    budget = APIFY_BUDGET_MOIS
    duree = (d1 - d0).total_seconds()
    ecoule = min(1.0, max(0.0, (maintenant - d0).total_seconds() / duree)) if duree > 0 else 1.0
    trajectoire = budget * ecoule
    cout_leger = _cout_leger(d)
    coupe = usage >= budget
    leger_ok = not coupe and usage + cout_leger <= trajectoire + 1e-9
    return {"t": _iso(maintenant), "source": source, "usage_usd": round(usage, 4), "limite_usd": _montant(api.get("limite_usd")) or None,
            "budget_usd": round(budget, 2), "trajectoire_usd": round(trajectoire, 2),
            "part": round(usage / budget, 3) if budget > 0 else None, "coupe": coupe, "leger_ok": leger_ok,
            "cycle_debut": _iso(d0), "cycle_fin": _iso(d1),
            "projete_usd": round(usage / max(0.1, ecoule), 2), "cout_leger_usd": round(cout_leger, 2), "api_t": str(api.get("t") or ""),
            "ok": leger_ok}


def projection_budget(brut, maintenant: datetime = None):
    """La réponse de GET /v2/users/me/limits seule → le budget du cycle (etat_budget, source « apify », sans les appels notés
    depuis) ; None si la réponse est illisible."""
    maintenant = maintenant or datetime.now(timezone.utc)
    api = _lire_api(brut, maintenant)
    if api is None:
        return None
    return etat_budget({"apify_local": {"api": api, "entrees": []}}, maintenant)


def budget_apify_connu() -> dict:
    """Le dernier budget Apify publié (etats_comptes.json, « apify_budget ») — pour le Dashboard, sans aucun appel ; {} si inconnu."""
    try:
        return dict(_lire().get("apify_budget") or {})
    except Exception:                                                   # noqa: BLE001
        return {}


async def _lire_limites():
    """GET https://api.apify.com/v2/users/me/limits?token=… (lecture seule, gratuite) ; None si illisible."""
    if _deps.get("apify_limites"):
        return await _deps["apify_limites"]()
    if not APIFY_TOKEN:
        return None
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(APIFY_LIMITES, params={"token": APIFY_TOKEN}) as reponse:
            if reponse.status >= 400:
                journal.warning("Apify : dépense du mois illisible (HTTP %s), comptée localement", reponse.status)
                return None
            return await reponse.json()


_CLES_DECISION = ("source", "usage_usd", "limite_usd", "budget_usd", "coupe", "leger_ok", "cycle_debut", "cycle_fin", "cout_leger_usd")


async def apify_budget(forcer: bool = False, publier: bool = False, maintenant: datetime = None) -> dict:
    """Le budget Apify du cycle (contrat C6a, voir etat_budget), publié dans etats_comptes.json (« apify_budget ») pour le Dashboard.
    L'API Apify (users/me/limits) est relue au plus toutes les BUDGET_CACHE_MIN minutes (`forcer` : tout de suite), une panne de
    l'API n'est réessayée qu'après le même délai ; à défaut, la dépense comptée localement. `publier` : écrit même si rien de décisif
    n'a changé (heure et trajectoire fraîches, boucle de 15 min)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if not _etat_configure():
        return etat_budget({}, maintenant)
    d = _lire()
    loc = d.get("apify_local") if isinstance(d.get("apify_local"), dict) else {}
    t_api = _instant((loc.get("api") or {}).get("t")) if isinstance(loc.get("api"), dict) else None
    essai = _instant(loc.get("api_essai"))
    recent = lambda t: t is not None and timedelta(0) <= maintenant - t < timedelta(minutes=BUDGET_CACHE_MIN)   # noqa: E731
    lu = essaye = False
    if forcer or not (recent(t_api) or recent(essai)):
        essaye = True
        try:
            brut = await _lire_limites()
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Apify : dépense du mois illisible (%s), comptée localement", type(erreur).__name__)
            brut = None
        api = _lire_api(brut, maintenant) if brut is not None else None
        d = _lire()                                                     # relu après l'appel : rien d'écrit pendant n'est perdu
        loc = _registre(d)
        loc["api_essai"] = _iso(maintenant)
        if api is not None:
            loc["api"] = api
            lu = True
    st = etat_budget(d, maintenant)
    ancien = d.get("apify_budget") if isinstance(d.get("apify_budget"), dict) else {}
    if publier or essaye or any(st.get(k) != ancien.get(k) for k in _CLES_DECISION):
        d["apify_budget"] = st
        _ecrire(d)
    if lu:
        journal.info("Apify : %s $ dépensés ce cycle (budget %s $, trajectoire %s $)", _euros(st["usage_usd"]), _euros(st["budget_usd"]),
                     _euros(st["trajectoire_usd"]))
    return st


def noter_depense(usd: float, unites: int = 0, quoi: str = "") -> None:
    """Une dépense Apify faite par le bot (profils demandés, publications lues), notée dans le registre du cycle : elle compte
    jusqu'à ce que l'API Apify, relue après elle, l'inclue (ou toute seule si l'API ne répond pas)."""
    if not _etat_configure() or not usd or usd <= 0:
        return
    maintenant = datetime.now(timezone.utc)
    try:
        d = _lire()
        loc = _registre(d)
        d0, _ = _cycle(maintenant, loc.get("api"))
        garde = [e for e in loc["entrees"] if isinstance(e, list) and e and (_instant(e[0]) or d0 - timedelta(1)) >= d0]
        loc["entrees"] = garde[-1999:] + [[_iso(maintenant), round(float(usd), 4), int(unites or 0), str(quoi or "")[:40]]]
        d["apify_budget"] = etat_budget(d, maintenant)
        _ecrire(d)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Apify : dépense non notée (%s)", type(erreur).__name__)


_refus = {"t": 0.0}                                                     # dernier appel refusé par la garde (horloge monotone)


async def garde_apify(cout_usd: float, quoi: str = "") -> bool:
    """09/10 (Gaëtan : « Dépasse pas 25 $ / mois ») : un appel Apify de `cout_usd` est-il permis ? Refusé si le budget du cycle est
    atteint (coupe) ou si cet appel le ferait dépasser ; alerte admin une fois par jour. Sans état configuré (tests d'un autre
    module) : permis ; si le budget ne peut pas être calculé : refusé (jamais de dépense à l'aveugle)."""
    if not _etat_configure():
        return True
    try:
        st = await apify_budget()
    except Exception as erreur:                                         # noqa: BLE001
        journal.error("Apify : budget du mois incalculable (%s), appel refusé par prudence", type(erreur).__name__)
        _refus["t"] = _horloge.monotonic()
        return False
    usage, budget = float(st.get("usage_usd") or 0), float(st.get("budget_usd") or 0)
    if st.get("coupe") or usage + max(0.0, float(cout_usd or 0)) > budget + 1e-9:
        _refus["t"] = _horloge.monotonic()
        journal.warning("Apify : appel refusé (%s, %s $) — %s $ dépensés ce cycle pour un budget de %s $", quoi or "?",
                        _euros(cout_usd), _euros(usage), _euros(budget))
        await _alerter_coupe(st, quoi, cout_usd)
        return False
    return True


def _jusqu_au(st: dict) -> str:
    fin = _instant(st.get("cycle_fin"))
    return _paris(fin).strftime("%d/%m") if fin else "la fin du cycle"


def _erreur_budget(depuis: float) -> str:
    """Le texte d'erreur d'un passage qui n'a rien lu parce que la garde du budget a refusé (depuis l'instant `depuis`) ; '' sinon."""
    if _refus["t"] < depuis:
        return ""
    st = budget_apify_connu() or etat_budget()
    return (f"budget Apify du mois atteint ({_euros(st.get('usage_usd'))} $ sur {_euros(st.get('budget_usd'))} $) : aucun appel "
            f"Apify jusqu'au {_jusqu_au(st)}, rien changé")


async def _alerter_coupe(st: dict, quoi: str, cout_usd) -> None:
    jour_p = _paris(datetime.now(timezone.utc)).date().isoformat()
    if st.get("coupe"):
        texte = (f"⛔ Budget Apify du mois atteint : {_euros(st.get('usage_usd'))} $ dépensés sur {_euros(st.get('budget_usd'))} $ "
                 f"(décision de Gaëtan). Plus aucun appel Apify (scan du matin, relectures, recherche des @ changés, scan du soir, "
                 f"identifiants neufs, cadence) jusqu'au {_jusqu_au(st)}. Le Dashboard le dit.")
        await _alerter_une_fois("coupe", jour_p, texte)
    else:
        texte = (f"⚠️ Budget Apify presque atteint : {_euros(st.get('usage_usd'))} $ dépensés sur {_euros(st.get('budget_usd'))} $. "
                 f"Un appel de {_euros(cout_usd)} $ ({quoi or 'Apify'}) le dépasserait : refusé.")
        await _alerter_une_fois("budget_refus", jour_p, texte)


def _euros(x) -> str:
    return f"{x:.2f}".replace(".", ",") if isinstance(x, (int, float)) and not isinstance(x, bool) else "?"


async def _alerter_une_fois(quoi: str, jour_p: str, texte: str) -> bool:
    """Une alerte au salon admin, une seule fois par jour (de Paris) et par sujet."""
    d = _lire()
    alertes = d.setdefault("alertes_legeres", {})
    if alertes.get(quoi) == jour_p:
        return False
    alertes[quoi] = jour_p
    _ecrire(d)
    if _deps.get("canal_admin"):
        try:
            canal = await _deps["canal_admin"]()
            if canal is not None:
                await canal.send(texte[:1990])
                return True
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Alerte du passage léger : %s", type(erreur).__name__)
    return False


def _complet_recent(d: dict, maintenant: datetime) -> bool:
    """Le passage complet a relu Instagram il y a moins de LEGER_APRES_COMPLET_H heures. 09/10 (revue) : un passage complet APRÈS
    `maintenant` (heure prise avant lui par la boucle, ou complet manuel fini pendant l'attente du verrou) compte aussi comme récent
    (avant : écart négatif, garde contournée, relecture payante juste derrière le complet)."""
    complet = _instant(d.get("scan_iso"))
    if complet is None:
        return False
    ecart = maintenant - complet
    return -timedelta(days=1) < ecart < timedelta(hours=LEGER_APRES_COMPLET_H)


def _texte_trajectoire(h: int, st: dict, cout: float) -> str:
    return (f"⏭️ Relecture légère de {h} h sautée : {_euros(st.get('usage_usd'))} $ dépensés sur Apify ce mois, la trajectoire du "
            f"budget en permet {_euros(st.get('trajectoire_usd'))} $ à cette date (budget {_euros(st.get('budget_usd'))} $, décision "
            f"de Gaëtan ; relecture estimée à {_euros(cout)} $). Le passage complet du matin continue.")


async def passage_leger_si_du(maintenant: datetime = None) -> str:
    """Lance le passage léger d'une heure de ETATS_HEURES_LEGERES (Paris) pas encore faite aujourd'hui. Renvoie : '' (rien de dû),
    'attente' (le passage complet du jour passe d'abord), 'recent' (le complet vient de relire Instagram : heure notée faite),
    'budget' (budget Apify du mois atteint, ou la relecture ferait passer la dépense au-dessus de la trajectoire linéaire du
    budget : sautée), 'erreur', 'fait'. 09/10 (revue) : « récent » et budget revérifiés une fois le verrou des passages pris (un
    passage complet manuel en cours finit d'abord : il a relu Instagram et dépensé)."""
    if not HEURES_LEGERES:
        return ""
    maintenant = maintenant or datetime.now(timezone.utc)
    p = _paris(maintenant)
    jour_p, jour = p.date().isoformat(), maintenant.strftime("%Y-%m-%d")
    d = _lire()
    dus = [h for h in HEURES_LEGERES if p.hour >= h]
    faits = [h for h in ((d.get("legers") or {}).get(jour_p) or []) if isinstance(h, int)]
    if not [h for h in dus if h not in faits]:
        return ""
    if maintenant.hour >= HEURE_UTC and (d.get("dernier") != jour or d.get("version") != VERSION) \
            and int((d.get("essais") or {}).get(jour, 0)) < 3:
        return "attente"
    d["legers"] = {jour_p: sorted(set(faits) | set(dus))}               # une heure ratée n'est pas rejouée en boucle
    _ecrire(d)
    if _complet_recent(d, maintenant):
        journal.info("Passage léger de %d h sauté : le passage complet a relu Instagram il y a moins de %d h", dus[-1], LEGER_APRES_COMPLET_H)
        return "recent"

    async def _budget_permet(st: dict, d_: dict) -> bool:
        cout = _cout_leger(d_)
        if st.get("coupe"):
            journal.warning("Passage léger de %d h sauté : budget Apify du mois atteint", dus[-1])
            await _alerter_coupe(st, "relecture légère", cout)
            return False
        if float(st.get("usage_usd") or 0) + cout > float(st.get("trajectoire_usd") or 0) + 1e-9:
            journal.warning("Passage léger de %d h sauté : dépense Apify au-dessus de la trajectoire du budget", dus[-1])
            await _alerter_une_fois("budget", jour_p, _texte_trajectoire(dus[-1], st, cout))
            return False
        return True

    if not await _budget_permet(await apify_budget(maintenant=maintenant), d):
        return "budget"
    async with _verrou_passages():
        d = _lire()
        if _complet_recent(d, maintenant):
            journal.info("Passage léger de %d h sauté : un passage complet vient de finir", dus[-1])
            return "recent"
        if not await _budget_permet(etat_budget(d, maintenant), d):     # la dépense du passage qui vient de finir comptée
            return "budget"
        bilan = await _executer_leger(True)
    if bilan.get("erreur"):
        journal.warning("Passage léger : %s", bilan["erreur"])
        await _alerter_une_fois("leger", jour_p, f"⚠️ Passage léger de {dus[-1]} h : {bilan['erreur']}.")
        return "erreur"
    return "fait"


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
        if auj is None or ((auj.get("restreint") or auj.get("reels_non_lus")) and not auj.get("posts")):   # 30/09 : restreint = illisible,
            continue                                                    # pas « 0 Reel » ; 09/10 (dashboard) : Reels non lus non plus
        avant = [e for e in entrees if str(e.get("jour") or "") < jour
                 and not ((e.get("restreint") or e.get("reels_non_lus")) and not e.get("posts"))]
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
    if bilan.get("suspects"):                                           # 09/10 (dashboard) : faux 0 écartés
        entete += (f"\n⚠️ **Followers suspects** ({len(bilan['suspects'])}, 0 lu alors que le compte en avait plus de "
                   f"{SUSPECT_FOLLOWERS} : cellule gardée) : {', '.join(bilan['suspects'][:25])}")
    if bilan.get("reels_non_lus"):
        entete += (f"\n⚠️ **Reels non lus** ({len(bilan['reels_non_lus'])}, Apify n'a rendu aucune publication alors que le compte "
                   f"en a : cellules gardées) : {', '.join(bilan['reels_non_lus'][:25])}")
    if bilan.get("perdues"):                                            # 09/10 (dashboard) : jamais une écriture perdue en silence
        entete += (f"\n❌ **Cellules non écrites** ({len(bilan['perdues'])}) : " + " · ".join(bilan["perdues"][:15]))
    if bilan.get("mode") == "leger":
        entete = entete.replace("**États du classeur**", "**États du classeur (passage léger : followers et Reels, aucun état)**", 1)
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
    """Un passage par jour, à HEURE_UTC, après le rapport inputs. Trois tentatives espacées de 15 minutes. 09/10 (dashboard) :
    puis les passages légers aux heures de Paris ETATS_HEURES_LEGERES (passage_leger_si_du), sous garde du budget Apify ; le
    budget du mois (« apify_budget ») est republié à chaque tour (15 min) pour le Dashboard."""
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
                    if (bilan["changements"] or bilan.get("followers") or bilan.get("clics") or bilan.get("non_lus")
                            or bilan.get("suspects") or bilan.get("perdues")) and _deps.get("canal_admin"):
                        canal = await _deps["canal_admin"]()
                        if canal is not None:
                            await canal.send(texte_bilan(bilan)[:1990])
                    bans = [f"`{h}` ({g})" for h, g, _, a, _ in bilan["changements"] if a == "BAN"]
                    if bans and _deps.get("notifier"):
                        await _deps["notifier"]("🚫 **Comptes introuvables sur Instagram, passés en BAN** : "
                                                + ", ".join(bans) + ". À remplacer : `!liberer Prénom handle`, puis un nouvel identifiant.")
            try:                                                        # 09/10 : le budget du mois (contrat C6a), frais pour le Dashboard
                await apify_budget(publier=True)
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Budget Apify : %s", type(erreur).__name__)
            try:                                                        # 09/10 (dashboard) : passages légers (14 h, 20 h de Paris)
                # 09/10 (revue) : l'heure d'APRÈS le passage complet de cette itération (celle de la tête de boucle le précédait :
                # la garde « complet de moins de 2 h » ne jouait pas et une relecture payante repartait juste derrière)
                await passage_leger_si_du(datetime.now(timezone.utc))
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Passage léger : %s", erreur)
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
    """`!etats-comptes` : passage immédiat · `!etats-comptes test` : ce qui changerait, sans rien écrire · `!etats-comptes leger` :
    un passage léger (09/10) · `!dashboard` : l'onglet réécrit sans scan · `!dashboard scan` : passage complet puis l'onglet."""
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
        # le passage complet (Instagram, états, followers, Reels hier, clics, regroupement) avant l'onglet. 09/10 (dashboard) : le
        # Dashboard se tient à jour seul (passages légers, séries) ; `!dashboard` réécrit l'onglet SANS scan (gratuit), et
        # `!dashboard scan` lance d'abord le passage complet payant. « rapide » / « vite » restent acceptés (sans scan).
        st = etat_budget() if actif() and len(mots) > 1 and mots[1].lower() == "scan" else {}
        if st.get("coupe"):                                             # 09/10 (budget de Gaëtan) : plus aucun appel Apify ce mois
            await message.reply(f"⛔ Budget Apify du mois atteint ({_euros(st.get('usage_usd'))} $ sur {_euros(st.get('budget_usd'))} $) : "
                                f"pas de scan jusqu'au {_jusqu_au(st)}. Je réécris le Dashboard sans relire Instagram.")
        elif actif() and len(mots) > 1 and mots[1].lower() == "scan":
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
            scan = len(mots) > 1 and mots[1].lower() == "scan"
            await message.reply(f"✅ Onglet « {ONGLET_DASHBOARD} » du classeur des logins réécrit ({n} lignes) : une ligne par clipper, par créatrice."
                                + ("" if scan else "\nSans relire Instagram : `!dashboard scan` lance d'abord le passage complet (payant).")
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
    leger = len(mots) > 1 and _norm(mots[1]) == "leger"                 # 09/10 (dashboard) : `!etats-comptes leger`
    await message.reply("⏳ Je regarde Instagram…" + (" (passage léger : comptes vivants, followers et Reels, aucun état changé)"
                                                       if leger else ""))
    bilan = await executer(ecrire=not test, leger=leger)
    await message.reply(texte_bilan(bilan, test)[:1990])
    return True
