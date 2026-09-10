"""Suivi quotidien des INPUTS clippers (Reels publiés, vues, followers) via Apify.

POURQUOI CE MODULE (décidé le 30/07/2026) : les rapports GAML mesurent l'OUTPUT (clics).
Résultat : un clipper qui publie 12 Reels qui flopent et un clipper qui ne publie rien sont
identiques dans les données (0 clic) — impossible de piloter la discipline. Ce module mesure
ce que le clipper CONTRÔLE : le nombre de Reels publiés par jour. C'est la métrique qui
conditionne le fixe, et c'est celle qui sépare Yanil (205 visites/jour) de la médiane (12) —
il ne monte pas mieux, il publie plus.

SÉCURITÉ PLATEFORME — la règle absolue : le scraping passe par Apify, qui interroge des
profils PUBLICS depuis SA propre infrastructure et ses proxies résidentiels, **sans aucune
authentification**. Meta voit un visiteur anonyme, non attribuable à un compte de l'agence :
aucun risque de ban sur les comptes clippers. NE JAMAIS fournir de cookie de session, de
`sessionid` ni d'identifiants Instagram à un actor Apify — c'est la seule chose qui créerait
un vrai risque. Les actors utilisés ici n'en demandent pas.

SÉCURITÉ DONNÉES : la cartographie des comptes se lit dans les **descriptions (topics) des
salons Discord**, qui contiennent aussi des mots de passe. Ce module n'extrait QUE les
identifiants `@` et ne journalise jamais un topic brut.
"""

import asyncio
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
import discord

journal = __import__("logging").getLogger("bot_clippers")

# ------------------------------------------------------------------ configuration
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR_IG = os.environ.get("APIFY_ACTOR_IG", "apify~instagram-profile-scraper").strip()
ACTOR_FB = os.environ.get("APIFY_ACTOR_FB", "apify~facebook-posts-scraper").strip()
FB_POSTS_MAX = int(os.environ.get("FB_POSTS_MAX", "6"))   # posts lus par page (coût ~2 $/1 000)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
# Cadence exigée sur CHAQUE surface (compte IG de croissance, page FB) : 2 Reels/jour — grille du
# 07/09 (le défaut était resté à 3, contredisant la base de connaissances — audit 10/09).
CADENCE_MIN = int(os.environ.get("CADENCE_REELS_MIN", "2"))
# Montée en charge des nouveaux (grille 07/09) : semaine 1 = warm-up, 0 publication exigée ;
# semaine 2 = 1 Reel/jour/surface ; semaine 3+ = cadence pleine. NOUVEAU_JOURS = durée totale.
NOUVEAU_JOURS = int(os.environ.get("NOUVEAU_JOURS", "14"))
# Objectif de comptes Instagram VIVANTS par créatrice prioritaire (décision du 02/09 : la machine
# à surfaces neuves — en créer plus qu'il n'en meurt). Le rapport quotidien affiche l'écart.
OBJECTIF_COMPTES_IG = int(os.environ.get("OBJECTIF_COMPTES_IG", "20"))
TOP_CREATRICES = [c.strip() for c in
                  os.environ.get("TOP_CREATRICES", "Chloé,Sarah,Sophie,Maddie").split(",") if c.strip()]
# Prime discipline (grille du 07/09) : tout-ou-rien sur TOUTES les surfaces du clipper — chaque compte
# IG de croissance ET chaque page FB à CADENCE_MIN par jour, PRIME_JOURS_MIN jours dans le mois.
# La structure minimale (2 IG de croissance + 3 pages FB) conditionne aussi le fixe.
STRUCTURE_IG_MIN = int(os.environ.get("STRUCTURE_IG_MIN", "2"))
STRUCTURE_FB_MIN = int(os.environ.get("STRUCTURE_FB_MIN", "3"))
# Compte privé (« compte à lien ») exigé par la grille : 1. Mettre 0 pour ne pas l'exiger.
STRUCTURE_PRIVE_MIN = int(os.environ.get("STRUCTURE_PRIVE_MIN", "1"))
PRIME_JOURS_MIN = int(os.environ.get("PRIME_JOURS_MIN", "26"))
PRIME_CLIPPER_EUR = int(os.environ.get("PRIME_CLIPPER_EUR", "50"))
MANAGER_PAR_CLIPPER_EUR = int(os.environ.get("MANAGER_PAR_CLIPPER_EUR", "100"))
MANAGER_BONUS_EQUIPE_EUR = int(os.environ.get("MANAGER_BONUS_EQUIPE_EUR", "150"))
# Variable (grille 07/09) : 0,50 €/abonné vérifié pour le clipper, 0,30 € pour le manager, et
# paliers manager sur le total d'abonnés de son équipe (non cumulés) : >1 000 → 300 €,
# >2 500 → 800 €, >5 000 → 1 600 €. Les abonnés se saisissent avec `!subs` (stats OF).
COMMISSION_CLIPPER_EUR = float(os.environ.get("COMMISSION_CLIPPER_EUR", "0.5"))
COMMISSION_MANAGER_EUR = float(os.environ.get("COMMISSION_MANAGER_EUR", "0.3"))
PALIERS_MANAGER = ((5000, 1600), (2500, 800), (1000, 300))
MANAGER_PRENOM = os.environ.get("MANAGER_PRENOM", "Jonas").strip()
SUBS_MIN_PREMIER_MOIS = int(os.environ.get("SUBS_MIN_PREMIER_MOIS", "50"))
ACTIF_TAUX_MIN = float(os.environ.get("ACTIF_TAUX_MIN", "0.8"))   # clipper « actif » = ≥ 80 % de jours validés
# Heure UTC d'envoi du rapport quotidien (9 = 11h à Paris l'été, 13h à Dubaï).
HEURE_RAPPORT = int(os.environ.get("HEURE_RAPPORT_INPUTS", "9"))
# Salons à ignorer dans la cartographie : réserves de comptes non attribués.
SALONS_IGNORES = {s.strip().lower() for s in
                  os.environ.get("SALONS_RESERVE", "xxx,yyy,zzz,reserve,reserves,stock,libre").split(",")
                  if s.strip()}

FICHIER_INPUTS = None          # injecté par bot_discord.py (chemin sur le volume persistant)
# Source de vérité des comptes : le Google Sheet publié en CSV (prioritaire), sinon les topics
# Discord en repli. ⚠️ Ne JAMAIS publier l'onglet qui contient les mots de passe — voir README :
# on publie un onglet « Tracking » dédié, alimenté par formule, sans aucune colonne sensible.
SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "").strip()
# Archivage de l'historique dans le Sheet (Apps Script « historique_inputs.gs » déployé en Web App).
# Le JSON local reste la mémoire de travail ; le Sheet est l'archive consultable qui survit à tout.
SHEET_HISTORIQUE_URL = os.environ.get("SHEET_HISTORIQUE_URL", "").strip()
SHEET_HISTORIQUE_SECRET = os.environ.get("SHEET_HISTORIQUE_SECRET", "").strip()
# États du sheet qui excluent un compte du scraping (économie de crédits + moins de bruit).
# « à créer » compte AUTANT que « ban » : scraper un compte qui n'existe pas encore brûle des
# crédits et pollue les rapports avec de faux « injoignables ».
ETATS_MORTS = {_e.strip().lower() for _e in os.environ.get(
    "SHEET_ETATS_MORTS",
    "ban,banni,mort,supprime,ferme,a creer,acreer,a faire,attente,reserve").split(",") if _e.strip()}
# Onglet Facebook publié séparément (structure différente : « URL Page » + « Gérant »).
SHEET_CSV_FB_URL = os.environ.get("SHEET_CSV_FB_URL", "").strip()


def _normaliser(texte: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", (texte or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def _identifier_compte(valeur: str):
    """Devine la plateforme d'après l'écriture : une URL facebook.com ou un préfixe « fb: » désigne
    une page Facebook, tout le reste un compte Instagram. Retourne ("comptes"|"pages_fb", nom) ou
    ("comptes", "") si la valeur n'est pas exploitable. C'est ce qui permet de n'avoir QU'UNE
    colonne « Compte » dans le Sheet, donc un seul onglet à publier."""
    v = (valeur or "").strip()
    if not v:
        return "comptes", ""
    if re.search(r"facebook\.com|^fb:", v, re.I):
        page = re.sub(r"^(?:fb:|https?://)?(?:www\.|m\.|web\.)?(?:facebook\.com/)?", "", v,
                      flags=re.I).lstrip("@").lower()
        # « profile.php?id=… » : l'identifiant numérique EST le nom de la page, on le conserve.
        # Pour toute autre URL, on coupe le query string (paramètres de suivi, ?ref=…) AVANT le
        # slash final, sinon il reste collé au nom.
        if not page.startswith("profile.php"):
            page = page.split("?")[0]
        page = page.rstrip("/")
        return "pages_fb", (page if page and len(page) <= 60 else "")
    handle = v.lstrip("@").strip().lower()
    if not handle or " " in handle or len(handle) > 30 or "/" in handle:
        return "comptes", ""
    return "comptes", handle


def _etat_mort(etat: str) -> bool:
    """Un compte à exclure du scraping : banni, supprimé, ou pas encore créé. Comparaison souple
    (accents et ponctuation retirés) pour attraper « à créer », « A CRÉER », « a-creer »…"""
    e = re.sub(r"[^a-z0-9 ]", "", _normaliser(etat)).strip()
    return bool(e) and any(e == m or e.startswith(m) for m in ETATS_MORTS)


async def _telecharger_csv(url: str):
    """Télécharge un CSV publié et le renvoie en liste de lignes. [] si indisponible."""
    import csv as _csv
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            async with session.get(url) as reponse:
                if reponse.status >= 400:
                    journal.warning("Sheet CSV HTTP %s", reponse.status)
                    return []
                return list(_csv.reader(io.StringIO(await reponse.text())))
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Sheet CSV injoignable : %s", erreur)
        return []


def _index_colonnes(entetes):
    """Retourne une fonction qui trouve l'index d'une colonne par mots-clés (premier trouvé)."""
    normalises = [_normaliser(c) for c in entetes]
    def colonne(*mots):
        for i, e in enumerate(normalises):
            if any(m in e for m in mots):
                return i
        return -1
    return colonne, normalises


def _lire(defaut):
    if FICHIER_INPUTS and FICHIER_INPUTS.exists():
        try:
            return json.loads(FICHIER_INPUTS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            journal.warning("inputs_clippers.json illisible, réinitialisé")
    return defaut


def _ecrire(donnees):
    """Écriture atomique (temporaire puis remplacement) : un redéploiement au milieu d'une écriture
    laissait un historique vide, donc un mois de primes perdu."""
    if not FICHIER_INPUTS:
        return
    temporaire = FICHIER_INPUTS.with_suffix(".json.tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, FICHIER_INPUTS)


def heure_paris():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Paris"))
    except Exception:                                    # noqa: BLE001 — base de fuseaux absente
        return datetime.now(timezone.utc) + timedelta(hours=2)


def fenetre_veille():
    """La journée évaluée = HIER, de minuit à minuit heure de Paris (la grille parle de journées,
    pas de « 24 dernières heures » glissantes qui coupaient une soirée en deux — audit 10/09).
    Retourne (début UTC, fin UTC, 'AAAA-MM-JJ')."""
    maintenant = heure_paris()
    fin_locale = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    debut_locale = fin_locale - timedelta(days=1)
    return (debut_locale.astimezone(timezone.utc), fin_locale.astimezone(timezone.utc),
            debut_locale.strftime("%Y-%m-%d"))


# ------------------------------------------------------------------ 1. cartographie
# Un @ Instagram : 1-30 caractères, lettres/chiffres/points/underscores. On exclut les e-mails
# (un @ suivi d'un domaine) et les mots de passe (majuscules + caractères spéciaux).
MOTIF_HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9._]{2,30})(?![\w.]*\.(?:com|fr|net|org|io|es))")
# Une page Facebook se déclare par son URL complète, ou par « fb:nom-de-la-page ».
MOTIF_FB = re.compile(r"(?:facebook\.com/|(?<![\w])fb:)([A-Za-z0-9._-]{2,60})", re.I)
MOTS_INTERDITS = {"gmail", "icloud", "hotmail", "outlook", "yahoo", "everyone", "here",
                  "profile.php", "pages", "groups", "share", "reel", "watch"}


def extraire_handles(topic: str) -> dict:
    """Les comptes d'une description de salon : `@pseudo` → Instagram, `facebook.com/x` ou `fb:x`
    → Facebook. N'extrait QUE des identifiants : jamais de mot de passe, jamais d'e-mail.
    Retourne {"ig": [...], "fb": [...]}, dédoublonné, ordre conservé."""
    resultat = {"ig": [], "fb": []}
    for cle, motif in (("ig", MOTIF_HANDLE), ("fb", MOTIF_FB)):
        vus = set()
        for brut in motif.findall(topic or ""):
            h = brut.strip(".-").lower()
            if not h or h in vus or h in MOTS_INTERDITS or h.isdigit():
                continue
            vus.add(h)
            resultat[cle].append(h)
    return resultat


async def cartographier_depuis_sheet(guild) -> dict:
    """Source de vérité n°1 : le Google Sheet publié en CSV. Colonnes reconnues par mot-clé dans
    l'entête (ordre libre) : « @ » ou « compte » → identifiant Instagram · « gérant »/« clipper » →
    à qui il appartient · « état » → BAN et assimilés sont ignorés · « facebook »/« fb » → page FB.
    Le salon privé du clipper est retrouvé par son prénom sur le serveur. Retourne {} si le sheet
    n'est pas configuré ou illisible : l'appelant retombe alors sur les topics Discord."""
    if not SHEET_CSV_URL:
        return {}
    lignes = await _telecharger_csv(SHEET_CSV_URL)
    if len(lignes) < 2:
        return {}
    colonne, entetes = _index_colonnes(lignes[0])
    i_compte = colonne("@", "compte", "pseudo", "instagram")
    i_gerant = colonne("gerant", "clipper", "responsable")
    i_etat = colonne("etat", "statut")
    i_fb = colonne("facebook", "fb", "page")
    if i_compte < 0 or i_gerant < 0:
        journal.warning("Sheet CSV : colonnes « compte » et/ou « gérant » introuvables — entêtes : %s",
                        ", ".join(entetes[:10]))
        return {}

    # Index des salons du serveur par prénom normalisé, pour retrouver le salon privé de chacun.
    salons, creatrices = {}, {}
    for categorie in getattr(guild, "categories", []):
        for salon in categorie.text_channels:
            cle = re.sub(r"[^a-z0-9]", "", _normaliser(salon.name))
            if cle and cle not in SALONS_IGNORES:
                salons[cle] = salon.id
                creatrices[cle] = categorie.name.strip()

    carte, ignores = {}, 0
    for ligne in lignes[1:]:
        def champ(i):
            return ligne[i].strip() if 0 <= i < len(ligne) else ""
        brut_compte, gerant = champ(i_compte), champ(i_gerant)
        if not brut_compte or not gerant:
            continue
        if _etat_mort(champ(i_etat)):
            ignores += 1
            continue
        cle = re.sub(r"[^a-z0-9]", "", _normaliser(gerant))
        if cle in SALONS_IGNORES:
            continue
        fiche = carte.setdefault(gerant.strip().title(),
                                 {"creatrice": creatrices.get(cle, "—"), "canal_id": salons.get(cle),
                                  "comptes": [], "pages_fb": []})
        # Une seule colonne « Compte » suffit : le bot reconnaît une page Facebook à son écriture
        # (URL facebook.com ou préfixe « fb: ») et tout le reste comme un identifiant Instagram.
        # Ainsi un unique onglet Tracking couvre les deux plateformes, sans donnée sensible.
        for valeur in (brut_compte, champ(i_fb) if i_fb >= 0 else ""):
            cible, nom = _identifier_compte(valeur)
            if nom and nom not in fiche[cible]:
                fiche[cible].append(nom)
    journal.info("Sheet CSV : %d clipper(s), %d compte(s) · %d ignoré(s) (banni ou à créer)",
                 len(carte), sum(len(f["comptes"]) for f in carte.values()), ignores)
    await enrichir_pages_fb(carte, salons, creatrices)
    return carte


async def enrichir_pages_fb(carte: dict, salons: dict, creatrices: dict):
    """Ajoute les pages Facebook depuis l'onglet « FaceBook » publié séparément (colonnes « URL Page »
    et « Gérant »). Un gérant absent de la carte Instagram est ajouté : certaines pages sont tenues
    par des opérateurs internes qui n'ont pas de compte Instagram (Metricool)."""
    if not SHEET_CSV_FB_URL:
        return
    lignes = await _telecharger_csv(SHEET_CSV_FB_URL)
    if len(lignes) < 2:
        return
    colonne, _ = _index_colonnes(lignes[0])
    i_url = colonne("url")                       # « URL Page » avant « Nom Page »
    i_gerant = colonne("gerant", "clipper", "responsable")
    i_etat = colonne("etat", "statut")
    if i_url < 0 or i_gerant < 0:
        journal.warning("Onglet Facebook : colonnes « URL » et/ou « Gérant » introuvables")
        return
    ajoutees = 0
    for ligne in lignes[1:]:
        def champ(i):
            return ligne[i].strip() if 0 <= i < len(ligne) else ""
        url, gerant = champ(i_url), champ(i_gerant)
        if not url or not gerant or _etat_mort(champ(i_etat)):
            continue
        page = re.sub(r"^(?:fb:|https?://)?(?:www\.|m\.)?(?:facebook\.com/)?", "", url,
                      flags=re.I).rstrip("/").split("?")[0].lstrip("@").lower()
        if not page or len(page) > 60:
            continue
        clipper = gerant.strip().title()
        cle = re.sub(r"[^a-z0-9]", "", _normaliser(gerant))
        if cle in SALONS_IGNORES:
            continue
        fiche = carte.setdefault(clipper, {"creatrice": creatrices.get(cle, "—"),
                                           "canal_id": salons.get(cle), "comptes": [], "pages_fb": []})
        if page not in fiche["pages_fb"]:
            fiche["pages_fb"].append(page)
            ajoutees += 1
    journal.info("Onglet Facebook : %d page(s) rattachée(s)", ajoutees)


async def compter_comptes_creatrices() -> dict:
    """L'inventaire de surfaces par créatrice, depuis l'onglet Tracking publié : combien de comptes
    Instagram VIVANTS chaque créatrice possède, face à l'objectif OBJECTIF_COMPTES_IG. C'est le
    tableau de bord de la décision du 02/09 (créer plus de comptes qu'il n'en meurt). Retourne
    {créatrice: {"vivants": n, "en_attente": n}} ; {} si le sheet n'a pas de colonne créatrice."""
    if not SHEET_CSV_URL:
        return {}
    lignes = await _telecharger_csv(SHEET_CSV_URL)
    if len(lignes) < 2:
        return {}
    colonne, _ = _index_colonnes(lignes[0])
    i_compte = colonne("@", "compte", "pseudo", "instagram")
    i_etat = colonne("etat", "statut")
    i_crea = colonne("creatrice", "createur", "modele", "crea")
    if i_compte < 0 or i_crea < 0:
        return {}
    inventaire = {}
    for ligne in lignes[1:]:
        def champ(i):
            return ligne[i].strip() if 0 <= i < len(ligne) else ""
        crea = champ(i_crea)
        if not crea:
            continue
        cible, nom = _identifier_compte(champ(i_compte))
        if cible != "comptes" or not nom:
            continue                                   # pages FB : hors objectif « 20 IG »
        etat = champ(i_etat)
        fiche = inventaire.setdefault(crea.title(), {"vivants": 0, "en_attente": 0})
        if _etat_mort(etat):
            # « à créer » n'est pas un mort comme un ban : c'est la file d'attente de création.
            e = re.sub(r"[^a-z0-9 ]", "", _normaliser(etat)).strip()
            if e.startswith("a creer") or e.startswith("acreer") or e.startswith("a faire"):
                fiche["en_attente"] += 1
        else:
            fiche["vivants"] += 1
    return inventaire


def bloc_comptes(inventaire: dict) -> str:
    """La ligne « surfaces » du rapport : vivants/objectif par créatrice prioritaire, file d'attente
    incluse. Vide si l'inventaire n'est pas disponible (colonne créatrice absente du sheet)."""
    if not inventaire:
        return ""
    morceaux = []
    for crea in TOP_CREATRICES:
        fiche = next((f for n, f in inventaire.items() if _normaliser(n) == _normaliser(crea)), None)
        if fiche is None:
            morceaux.append(f"{crea} ?")
            continue
        manque = max(0, OBJECTIF_COMPTES_IG - fiche["vivants"])
        attente = fiche["en_attente"]
        morceaux.append(f"{crea} {fiche['vivants']}"
                        + (f" (manque {manque}"
                           + (f", {attente} préparé{'s' if attente > 1 else ''}" if attente else "")
                           + ")" if manque else " ✅"))
    return f"🏗️ IG vivants /{OBJECTIF_COMPTES_IG} : " + " · ".join(morceaux)


def cartographier_comptes(guild) -> dict:
    """Parcourt le serveur : catégorie = créatrice, salon = clipper, topic = ses comptes.
    Retourne {clipper: {"creatrice", "canal_id", "comptes": [...]}}.
    Les salons de réserve (xxx, yyy…) et les salons sans @ sont ignorés."""
    carte = {}
    for categorie in getattr(guild, "categories", []):
        creatrice = categorie.name.strip()
        for salon in categorie.text_channels:
            nom = salon.name.strip()
            # Les salons Discord portent souvent un emoji en préfixe (« 💬Xxx ») : on ne garde que
            # les lettres et chiffres avant de comparer, sinon les salons de réserve passent au travers.
            nom_n = re.sub(r"[^a-z0-9]", "", _normaliser(nom))
            if not nom_n or nom_n in SALONS_IGNORES or re.fullmatch(r"(.)\1{1,}", nom_n):
                continue
            comptes = extraire_handles(salon.topic)
            if not comptes["ig"] and not comptes["fb"]:
                continue
            clipper = re.sub(r"[^\w\s'-]", "", nom).replace("-", " ").replace("_", " ").strip().title()
            fiche = carte.setdefault(clipper, {"creatrice": creatrice, "canal_id": salon.id,
                                               "comptes": [], "pages_fb": []})
            for c in comptes["ig"]:
                if c not in fiche["comptes"]:
                    fiche["comptes"].append(c)
            for p in comptes["fb"]:
                if p not in fiche["pages_fb"]:
                    fiche["pages_fb"].append(p)
    return carte


# ------------------------------------------------------------------ 2. scraping Apify
async def scraper_apify(handles: list) -> dict:
    """Un seul appel Apify pour tous les comptes. Retourne {handle: {followers, posts_24h,
    vues_24h, total_posts}}. Un handle absent du résultat = compte injoignable (privé, banni
    ou renommé) — l'appelant le signale, c'est un signal de ban utile."""
    if not APIFY_TOKEN or not handles:
        return {}
    url = f"https://api.apify.com/v2/acts/{ACTOR_IG}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    debut_f, fin_f, _ = fenetre_veille()
    resultats = {}
    try:
        delai = aiohttp.ClientTimeout(total=280)
        async with aiohttp.ClientSession(timeout=delai) as session:
            async with session.post(url, json={"usernames": handles}) as reponse:
                if reponse.status >= 400:
                    journal.error("Apify HTTP %s (vérifie APIFY_TOKEN / crédits)", reponse.status)
                    return {}
                items = await reponse.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.error("Apify injoignable : %s", erreur)
        return {}

    for item in items if isinstance(items, list) else []:
        handle = (item.get("username") or "").lower()
        if not handle:
            continue
        # Profil marqué 18+ par Instagram : invisible aux visiteurs non connectés, donc illisible
        # ici — mais surtout catastrophique en portée organique. Découvert le 30/07 sur un compte
        # réel de l'agence : c'est un signal BUSINESS prioritaire, pas une erreur de scraping.
        if item.get("isRestrictedProfile") or "restricted" in str(item.get("error") or "").lower():
            resultats[handle] = {"restreint": True, "raison": str(item.get("restrictionReason") or "")[:120],
                                 "followers": 0, "posts_24h": 0, "vues_24h": 0, "total_posts": 0}
            continue
        # Compte en mode privé = le « compte à lien » du kit : sa bio et son lien restent visibles
        # de tous, seules les publications sont masquées. C'est VOULU (ça crée la curiosité) — donc
        # jamais une alerte : simplement un compte dont on ne peut pas compter les Reels.
        if item.get("private"):
            resultats[handle] = {"prive": True, "followers": int(item.get("followersCount") or 0),
                                 "posts_24h": 0, "vues_24h": 0, "total_posts": 0}
            continue
        posts_24h, vues_24h = 0, 0
        # latestPosts plafonne à ~12 publications : au-delà de 12 Reels/jour sur un même compte,
        # le comptage sature (sans effet à la cadence cible de 6/jour/compte).
        for post in item.get("latestPosts") or []:
            horodatage = post.get("timestamp") or ""
            try:
                quand = datetime.fromisoformat(horodatage.replace("Z", "+00:00"))
            except ValueError:
                continue
            if debut_f <= quand < fin_f:
                posts_24h += 1
                vues_24h += int(post.get("videoViewCount") or post.get("videoPlayCount") or 0)
        resultats[handle] = {
            "followers": int(item.get("followersCount") or 0),
            "posts_24h": posts_24h,
            "vues_24h": vues_24h,
            "total_posts": int(item.get("postsCount") or 0),
        }
    return resultats


async def scraper_facebook(pages: list):
    """Pages Facebook publiques → {page: {posts_24h, vues_24h}}, ou None si Apify est en PANNE.
    La distinction compte : une panne renvoyait des zéros, comptés comme mesurés → journée
    invalidée pour toute l'équipe, prime perdue sans faute (audit 10/09). Facebook fait partie de
    la grille du 07/09 (2 Reels/jour/page), ce n'est plus un « second regard »."""
    if not APIFY_TOKEN or not pages:
        return {}
    url = f"https://api.apify.com/v2/acts/{ACTOR_FB}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    debut_f, fin_f, _ = fenetre_veille()
    charge = {"startUrls": [{"url": f"https://www.facebook.com/{p}"} for p in pages],
              "resultsLimit": FB_POSTS_MAX}
    resultats = {p: {"posts_24h": 0, "vues_24h": 0} for p in pages}
    try:
        delai = aiohttp.ClientTimeout(total=280)
        async with aiohttp.ClientSession(timeout=delai) as session:
            async with session.post(url, json=charge) as reponse:
                if reponse.status >= 400:
                    journal.warning("Apify Facebook HTTP %s — journée FB non évaluée", reponse.status)
                    return None
                items = await reponse.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Apify Facebook injoignable : %s — journée FB non évaluée", erreur)
        return None
    if not isinstance(items, list):
        return None

    for post in items if isinstance(items, list) else []:
        source = (post.get("inputUrl") or "").rstrip("/").rsplit("/", 1)[-1].lower()
        if source not in resultats:
            continue
        try:
            quand = datetime.fromisoformat((post.get("time") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if debut_f <= quand < fin_f:
            resultats[source]["posts_24h"] += 1
            resultats[source]["vues_24h"] += int(post.get("viewsCount") or 0)
    return resultats


# ------------------------------------------------------------------ 3. calcul par clipper
def _cle(nom: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _normaliser(nom))


def cadence_du_jour(clipper: str, debuts: dict, jour: str) -> tuple:
    """(cadence exigée par surface, libellé de phase) pour ce clipper ce jour-là : semaine 1 = 0
    (warm-up), semaine 2 = 1, ensuite CADENCE_MIN. debuts = {prénom normalisé: 'AAAA-MM-JJ'}."""
    debut = (debuts or {}).get(_cle(clipper))
    if not debut:
        return CADENCE_MIN, ""
    try:
        age = (datetime.strptime(jour, "%Y-%m-%d") - datetime.strptime(debut[:10], "%Y-%m-%d")).days
    except ValueError:
        return CADENCE_MIN, ""
    if age < 0:
        return CADENCE_MIN, ""
    if age < NOUVEAU_JOURS // 2:
        return 0, "warm-up (semaine 1)"
    if age < NOUVEAU_JOURS:
        return min(1, CADENCE_MIN), "montée (semaine 2 : 1 Reel/jour/surface)"
    return CADENCE_MIN, ""


def agreger(carte: dict, brut: dict, veille: dict, brut_fb=None, debuts: dict = None, jour: str = "") -> dict:
    """Agrège par clipper. La journée est validée si la STRUCTURE est complète (IG de croissance,
    compte privé, pages FB) ET si CHAQUE surface tient sa cadence — pas la somme (audit 10/09 :
    4 Reels sur un compte et 0 sur l'autre passaient). brut_fb=None (panne Apify Facebook) →
    journée NON évaluée (journee_ok=None), jamais invalidée à tort."""
    fb_mesure = brut_fb is not None
    brut_fb = brut_fb or {}
    jour = jour or fenetre_veille()[2]
    bilan = {}
    for clipper, fiche in carte.items():
        posts = vues = followers = 0
        injoignables, restreints, prives, detail = [], [], [], []
        for handle in fiche["comptes"]:
            mesure = brut.get(handle)
            if mesure is None:
                injoignables.append(handle)
                continue
            if mesure.get("restreint"):
                restreints.append(handle)
                continue
            if mesure.get("prive"):
                prives.append(handle)
                continue
            posts += mesure["posts_24h"]
            vues += mesure["vues_24h"]
            followers += mesure["followers"]
            detail.append({"compte": handle, **mesure})
        pages = fiche.get("pages_fb", [])
        posts_fb = sum(brut_fb.get(p, {}).get("posts_24h", 0) for p in pages)
        vues_fb = sum(brut_fb.get(p, {}).get("vues_24h", 0) for p in pages)
        avant = (veille.get(clipper) or {}).get("followers")
        cadence, phase = cadence_du_jour(clipper, debuts, jour)
        ig_vivants = len(detail)
        # Surfaces en retard : chaque compte de croissance et chaque page doit tenir SA cadence.
        ig_en_retard = [d["compte"] for d in detail if d["posts_24h"] < cadence]
        fb_en_retard = [p for p in pages if brut_fb.get(p, {}).get("posts_24h", 0) < cadence] if fb_mesure else []
        manques = []
        if ig_vivants < STRUCTURE_IG_MIN:
            manques.append(f"{ig_vivants}/{STRUCTURE_IG_MIN} IG de croissance vivants")
        if len(prives) < STRUCTURE_PRIVE_MIN:
            manques.append(f"{len(prives)}/{STRUCTURE_PRIVE_MIN} compte privé (à lien)")
        if len(pages) < STRUCTURE_FB_MIN:
            manques.append(f"{len(pages)}/{STRUCTURE_FB_MIN} pages FB")
        structure_ok = not manques
        if fb_mesure or not pages:
            journee_ok = bool(structure_ok and not ig_en_retard and not fb_en_retard)
        else:
            journee_ok = None                          # Facebook non mesuré : on ne juge pas
        bilan[clipper] = {
            "creatrice": fiche["creatrice"],
            "canal_id": fiche["canal_id"],
            "comptes_suivis": len(fiche["comptes"]),
            "posts_24h": posts,
            "vues_24h": vues,
            "followers": followers,
            "delta_followers": (followers - avant) if isinstance(avant, int) else None,
            "pages_fb": len(pages),
            "posts_fb": posts_fb,
            "vues_fb": vues_fb,
            "fb_mesure": fb_mesure,
            "injoignables": injoignables,
            "restreints": restreints,
            "prives": prives,
            "detail": detail,
            "cadence": cadence,
            "phase": phase,
            "cadence_attendue": cadence * max(1, ig_vivants),
            "cadence_attendue_fb": cadence * len(pages),
            "ig_en_retard": ig_en_retard,
            "fb_en_retard": fb_en_retard,
            "manques_structure": manques,
            "structure_ok": structure_ok,
            "journee_ok": journee_ok,
        }
    return bilan


def jours_valides_mois(historique: dict, mois: str) -> dict:
    """{clipper: {"mesures": n, "valides": n, "creatrice": …}} pour un mois AAAA-MM. Seuls les jours
    où la journée a été évaluée (clé journee_ok présente) comptent comme mesurés."""
    compte = {}
    for jour, par_clipper in historique.items():
        if not jour.startswith(mois):
            continue
        for clipper, v in par_clipper.items():
            if "journee_ok" not in v:
                continue
            c = compte.setdefault(clipper, {"mesures": 0, "valides": 0, "creatrice": v.get("creatrice", "—")})
            c["mesures"] += 1
            c["valides"] += 1 if v["journee_ok"] else 0
    return compte


def message_primes(historique: dict, mois: str, subs: dict = None, debuts: dict = None) -> str:
    """La paie variable du mois, prête à virer — grille du 07/09 :
    · clipper : prime discipline 50 € (PRIME_JOURS_MIN journées validées) + 0,50 €/abonné (`!subs`) ;
    · manager : 100 € par clipper actif + 0,30 €/abonné de l'équipe + palier (300/800/1 600 €, non
      cumulés, sur le total d'abonnés) + 150 € UNE fois si tous ses clippers ont leur prime.
    Règle des 50 abonnés le premier mois de publication signalée. Les opérateurs Metricool sont exclus."""
    subs = {(_cle(n)): int(v) for n, v in (subs or {}).items()}
    compte = {n: c for n, c in jours_valides_mois(historique, mois).items()
              if not _normaliser(c["creatrice"]).startswith("metricool")}
    noms_subs = {n for n in (subs or {})}
    if not compte and not noms_subs:
        return (f"🏅 *PRIMES — {mois}* : aucune journée évaluée ni abonné saisi ce mois-ci "
                "(le suivi des inputs doit tourner · `!subs Prénom n` pour les abonnés).")
    equipes = {}
    for n, c in compte.items():
        equipes.setdefault(c["creatrice"], []).append((n, c))
    lignes = [f"🏅 *PRIMES — {mois}* (prime = {PRIME_JOURS_MIN} j validés · actif = ≥ {ACTIF_TAUX_MIN:.0%} des jours évalués)"]
    total_primes = total_commissions = 0.0
    actifs_total, total_subs, toutes_primes, alertes_50 = 0, 0, True, []
    vus = set()
    for crea, membres in sorted(equipes.items()):
        lignes.append(f"\n*Équipe {crea}*")
        for n, c in sorted(membres, key=lambda x: -x[1]["valides"]):
            vus.add(_cle(n))
            prime = c["valides"] >= PRIME_JOURS_MIN
            actif = c["mesures"] > 0 and c["valides"] / c["mesures"] >= ACTIF_TAUX_MIN
            actifs_total += 1 if actif else 0
            toutes_primes = toutes_primes and prime
            s = subs.get(_cle(n), 0)
            total_subs += s
            com = s * COMMISSION_CLIPPER_EUR
            total_primes += PRIME_CLIPPER_EUR if prime else 0
            total_commissions += com
            lignes.append(f"  {'🏅' if prime else ('✅' if actif else '🔴')} {n} — {c['valides']}/{c['mesures']} j validés"
                          + (f" → prime {PRIME_CLIPPER_EUR} €" if prime else "")
                          + (f" · {s} abo → {com:.0f} €" if s else " · abonnés non saisis")
                          + ("" if actif else " · non actif"))
            debut = (debuts or {}).get(_cle(n), "")
            premier_mois = bool(debut) and debut[:7] == mois
            if premier_mois and s < SUBS_MIN_PREMIER_MOIS:
                alertes_50.append(f"{n} ({s} abo)")
    restants = [n for n in (subs or {}) if _cle(n) not in vus]
    if restants:
        lignes.append("\n*Abonnés saisis sans journée évaluée* : "
                      + " · ".join(f"{n} {subs[_cle(n)]} abo → {subs[_cle(n)] * COMMISSION_CLIPPER_EUR:.0f} €" for n in restants))
        for n in restants:
            total_subs += subs[_cle(n)]
            total_commissions += subs[_cle(n)] * COMMISSION_CLIPPER_EUR
    fixe = MANAGER_PAR_CLIPPER_EUR * actifs_total
    com_manager = total_subs * COMMISSION_MANAGER_EUR
    palier = next((montant for seuil, montant in PALIERS_MANAGER if total_subs > seuil), 0)
    bonus = MANAGER_BONUS_EQUIPE_EUR if (toutes_primes and compte) else 0
    lignes.append(f"\n*Manager {MANAGER_PRENOM}* : {actifs_total} actif(s) × {MANAGER_PAR_CLIPPER_EUR} € = {fixe} € · "
                  f"{total_subs} abo × {COMMISSION_MANAGER_EUR:.2f} € = {com_manager:.0f} €"
                  + (f" · palier {palier} €" if palier else " · aucun palier (>1 000 abo → 300 €)")
                  + (f" · discipline équipe {bonus} €" if bonus else " · discipline équipe non atteinte")
                  + f" → *{fixe + com_manager + palier + bonus:.0f} €*")
    lignes.append(f"*Total clippers : primes {total_primes:.0f} € + commissions {total_commissions:.0f} €*")
    if alertes_50:
        lignes.append(f"⚠️ *Règle des {SUBS_MIN_PREMIER_MOIS} abonnés (premier mois)* : {', '.join(alertes_50)} → sortie à décider (`!sortie`).")
    lignes.append("_Abonnés = `!subs Prénom n` depuis les stats OF des liens de tracking. Téléphone cloud (60 €) hors calcul._")
    return "\n".join(lignes)


# ------------------------------------------------------------------ 4. messages
def message_clipper(prenom: str, b: dict) -> str:
    """Le bilan personnel envoyé dans le salon privé du clipper — factuel, jamais moralisateur."""
    posts, cible, cadence = b["posts_24h"], b["cadence_attendue"], b.get("cadence", CADENCE_MIN)
    if b.get("phase", "").startswith("warm-up"):
        entete = "🌱 **Semaine de warm-up** — aucune publication attendue, seulement la routine de la Fiche 2."
    elif not b.get("ig_en_retard") and b["detail"]:
        entete = f"✅ **{posts} Reels hier** — cadence tenue sur chaque compte ({cadence}/compte). Continue exactement comme ça."
    elif posts > 0:
        entete = (f"⚠️ **{posts} Reels hier** — en retard sur : "
                  + ", ".join("@" + c for c in b["ig_en_retard"]) + f" (objectif {cadence} par compte).")
    else:
        entete = (f"🔴 **0 Reel publié hier** (objectif {cadence} par compte). Si tu es bloqué sur quelque chose, "
                  f"dis-le ici maintenant à ton manager — on débloque en 5 minutes.")
    lignes = [f"📊 **Ton bilan d'hier — {prenom}**", "", entete, ""]
    if b.get("phase") and not b["phase"].startswith("warm-up"):
        lignes.append(f"📈 Phase : {b['phase']}")
    if b["vues_24h"]:
        lignes.append(f"👁️ **{b['vues_24h']:,}** vues sur tes Reels d'hier".replace(",", " "))
    lignes.append(f"👥 **{b['followers']:,}** abonnés cumulés".replace(",", " ")
                  + (f" ({b['delta_followers']:+d} depuis hier)" if b["delta_followers"] is not None else ""))
    if b["restreints"]:
        lignes.append(f"\n🔞 **URGENT — compte(s) marqué(s) 18+ par Instagram** : "
                      f"{', '.join('@' + c for c in b['restreints'])}.\n"
                      "Ton compte est **invisible pour toute personne non connectée** et sa portée est "
                      "massacrée. → Préviens ton manager aujourd'hui avec une capture : on le règle ensemble.")
    if b["prives"]:
        lignes.append(f"\n🔒 Compte à lien en privé : {', '.join('@' + c for c in b['prives'])} — "
                      "normal et voulu, je ne compte pas ses Reels.")
    if b["injoignables"]:
        lignes.append(f"\n🚫 **Compte(s) injoignable(s)** : {', '.join('@' + c for c in b['injoignables'])} — "
                      "banni ou renommé ? Préviens ton manager, on recrée (Fiche 1).")
    if b.get("pages_fb"):
        if b.get("fb_mesure", True):
            lignes.append(f"📘 Facebook : **{b['posts_fb']}/{b['cadence_attendue_fb']}** publication(s) hier"
                          + (f" · en retard : {', '.join(b['fb_en_retard'])}" if b.get("fb_en_retard") else "")
                          + (f" · {b['vues_fb']:,} vues".replace(",", " ") if b["vues_fb"] else ""))
        else:
            lignes.append("📘 Facebook : non mesuré hier (souci technique de notre côté) — ta journée n'est pas pénalisée.")
    else:
        lignes.append(f"📘 Facebook : **aucune page suivie** — il en faut {STRUCTURE_FB_MIN} pour la prime.")
    if b.get("journee_ok") is None:
        lignes.append(f"⏸️ Journée non évaluée pour la prime (mesure incomplète) — {b.get('jours_ok_mois', 0)}/{PRIME_JOURS_MIN} ce mois-ci.")
    elif b.get("journee_ok"):
        lignes.append(f"🏅 **Journée validée pour la prime discipline** ({b.get('jours_ok_mois', '?')}/{PRIME_JOURS_MIN} ce mois-ci).")
    else:
        manque = list(b.get("manques_structure") or [])
        if b.get("ig_en_retard"):
            manque.append("IG : " + ", ".join("@" + c for c in b["ig_en_retard"]))
        if b.get("fb_en_retard"):
            manque.append("FB : " + ", ".join(b["fb_en_retard"]))
        lignes.append(f"❌ Journée non validée pour la prime : {' · '.join(manque) or 'cadence'} "
                      f"({b.get('jours_ok_mois', 0)}/{PRIME_JOURS_MIN} ce mois-ci).")
    if b.get("deux_jours_rates"):
        lignes.append("\n🚨 **Deux journées ratées de suite.** La règle de l'équipe est claire : ton manager en est "
                      "informé, parle-lui aujourd'hui.")
    lignes.append("\n-# Rappel : ta commission de 0,50 €/abonné n'a aucun plafond. Plus tu publies, plus elle monte.")
    return "\n".join(lignes)


def _bloc_equipe(titre: str, membres: list) -> list:
    """Une section du récap : une ligne par personne, triée par production décroissante."""
    if not membres:
        return []
    total = sum(b["posts_24h"] for _, b in membres)
    lignes = [f"*{titre}* — {total} Reels", ""]
    for nom, b in sorted(membres, key=lambda x: -x[1]["posts_24h"]):
        etat = "✅" if b["posts_24h"] >= b["cadence_attendue"] else ("⚠️" if b["posts_24h"] else "🔴")
        delta = f" · {b['delta_followers']:+d} abo" if b["delta_followers"] is not None else ""
        fb = f" · FB {b['posts_fb']}" if b.get("pages_fb") else ""
        lignes.append(f"{etat} {nom} — {b['posts_24h']}/{b['cadence_attendue']} · "
                      f"{b['vues_24h']:,} vues{fb}{delta}".replace(",", " "))
        for etiquette, comptes in (("🔞 18+", b["restreints"]), ("🚫 mort", b["injoignables"])):
            if comptes:
                lignes.append(f"    {etiquette} : {', '.join(comptes)}")
    return lignes + [""]


def _analyse_et_actions(bilan: dict, veille: dict) -> list:
    """Analyse automatique + actionnables. Règles volontairement simples et vérifiables : on ne
    commente que ce que la donnée dit, jamais d'interprétation inventée."""
    total = sum(b["posts_24h"] for b in bilan.values())
    total_hier = sum(v.get("posts_24h", 0) for v in veille.values()) if veille else None
    actifs = [n for n, b in bilan.items() if b["posts_24h"] > 0]
    zeros = [n for n, b in bilan.items() if b["posts_24h"] == 0 and b["comptes_suivis"]
             and not b["restreints"] and not b["injoignables"]]
    restreints = {n: b["restreints"] for n, b in bilan.items() if b["restreints"]}
    morts = {n: b["injoignables"] for n, b in bilan.items() if b["injoignables"]}
    top = max(bilan.items(), key=lambda x: x[1]["posts_24h"], default=(None, None))

    analyse = ["🎯 *ANALYSE*", ""]
    if total_hier is not None:
        ecart = total - total_hier
        fleche = "🟢" if ecart > 0 else ("🔴" if ecart < 0 else "⚪")
        analyse.append(f"{fleche} {total} Reels aujourd'hui vs {total_hier} hier ({ecart:+d})")
    analyse.append(f"👥 {len(actifs)}/{len(bilan)} personnes ont publié")
    if top[0] and top[1]["posts_24h"]:
        part = top[1]["posts_24h"] / total * 100 if total else 0
        analyse.append(f"🥇 {top[0]} porte {part:.0f} % de la production du jour")
        if part >= 60:
            analyse.append("⚠️ Dépendance à une seule personne : si elle s'arrête, tout s'arrête.")

    actions = ["✅ *ACTIONNABLE*", ""]
    if restreints:
        actions.append(f"1. 🔞 Lever la restriction 18+ : "
                       + " · ".join(f"{n} ({', '.join(c)})" for n, c in list(restreints.items())[:3])
                       + " — trafic perdu à 100 %, gain immédiat sans publier un Reel de plus.")
    if morts:
        actions.append(f"{len(actions)-1}. 🚫 Recréer les comptes tombés : "
                       + " · ".join(f"{n} ({len(c)})" for n, c in list(morts.items())[:4]))
    if zeros:
        actions.append(f"{len(actions)-1}. 🔴 Relancer (0 Reel, comptes sains) : {', '.join(zeros[:8])}")
    if top[0] and top[1]["posts_24h"] >= top[1]["cadence_attendue"]:
        actions.append(f"{len(actions)-1}. 🙌 Féliciter {top[0]} publiquement dans #dopamine "
                       "— la reconnaissance publique est le seul levier gratuit.")
    if len(actions) == 2:
        actions.append("Rien d'urgent : tout le monde est à la cadence. Passe au chatting.")
    return analyse + [""] + actions


def message_recap_detail(bilan: dict, date_jour: str, veille: dict = None) -> str:
    """La version LONGUE du récapitulatif (une ligne par personne, analyse, actionnables) —
    disponible à la demande via `!inputs detail`. Le rapport quotidien, lui, utilise
    message_recap : la version courte (demande du 02/09 : « illisible »)."""
    if not bilan:
        return (f"📊 *INPUTS — {date_jour}*\n\nAucun compte cartographié "
                "(vérifie `SHEET_CSV_URL` ou les topics des salons).")
    metricool = [(n, b) for n, b in bilan.items() if _normaliser(b["creatrice"]).startswith("metricool")]
    clippers = [(n, b) for n, b in bilan.items() if (n, b) not in metricool]
    total = sum(b["posts_24h"] for b in bilan.values())
    total_vues = sum(b["vues_24h"] for b in bilan.values())

    lignes = [f"📊 *INPUTS — {date_jour}*",
              f"_{total} Reels · {total_vues:,} vues_".replace(",", " "), ""]
    lignes += _bloc_equipe("📱 CLIPPERS", clippers)
    lignes += _bloc_equipe("🎛️ METRICOOL (interne)", metricool)
    lignes += _analyse_et_actions(bilan, veille or {})
    return "\n".join(lignes)


def message_recap(bilan: dict, date_jour: str, veille: dict = None, comptes: dict = None) -> str:
    """Le rapport quotidien COURT (≤ 9 lignes) : total et tendance des CLIPPERS (Metricool à part),
    qui publie et qui est à zéro, journées validées, deux-jours-ratés, surfaces, incidents, UNE
    priorité. Tout le reste vit derrière `!inputs detail`."""
    if not bilan:
        return (f"📊 *MARKETING — {date_jour}*\n\nAucun compte cartographié "
                "(vérifie `SHEET_CSV_URL` ou les topics des salons).")
    clippers = {n: b for n, b in bilan.items() if not _normaliser(b["creatrice"]).startswith("metricool")}
    metricool = {n: b for n, b in bilan.items() if n not in clippers}
    veille = veille or {}
    total = sum(b["posts_24h"] for b in clippers.values())
    total_vues = sum(b["vues_24h"] for b in clippers.values())
    total_hier = (sum(v.get("posts_24h", 0) for n, v in veille.items()
                      if not _normaliser(v.get("creatrice", "")).startswith("metricool")) if veille else None)
    actifs = [n for n, b in clippers.items() if b["posts_24h"] > 0]
    zeros = [n for n, b in clippers.items() if b["posts_24h"] == 0 and b["comptes_suivis"]
             and not b["restreints"] and not b["injoignables"] and not b.get("phase", "").startswith("warm-up")]
    valides = [n for n, b in clippers.items() if b.get("journee_ok")]
    evalues = [n for n, b in clippers.items() if b.get("journee_ok") is not None]
    rates2 = [n for n, b in clippers.items() if b.get("deux_jours_rates")]
    restreints = sum(len(b["restreints"]) for b in clippers.values())
    morts = sum(len(b["injoignables"]) for b in clippers.values())
    fb_panne = any(not b.get("fb_mesure", True) and b.get("pages_fb") for b in clippers.values())
    top = max(clippers.items(), key=lambda x: x[1]["posts_24h"], default=(None, None))

    tendance = f" ({total - total_hier:+d} vs veille)" if total_hier is not None else ""
    feu = "🟢" if total_hier is None or total >= total_hier else "🔴"
    lignes = [f"📊 *MARKETING — {date_jour}*",
              f"{feu} *{total} Reels clippers*{tendance} · {total_vues:,} vues · "
              f"{len(actifs)}/{len(clippers)} ont publié · {len(valides)}/{len(evalues)} journées validées".replace(",", " ")]
    if metricool:
        lignes.append(f"🎛️ Metricool (interne) : {sum(b['posts_24h'] for b in metricool.values())} Reels")
    if top[0] and top[1]["posts_24h"]:
        ligne_top = f"🥇 {top[0]} ({top[1]['posts_24h']})"
        if zeros:
            ligne_top += f" — 🔴 zéro : {', '.join(zeros[:5])}" + (f" +{len(zeros)-5}" if len(zeros) > 5 else "")
        lignes.append(ligne_top)
    if rates2:
        lignes.append(f"🚨 *2 jours ratés de suite* (règle : sortie lundi) : {', '.join(rates2[:6])}")
    surfaces = bloc_comptes(comptes or {})
    if surfaces:
        lignes.append(surfaces)
    if restreints or morts or fb_panne:
        lignes.append("❗ " + " · ".join(filter(None, [
            f"{restreints} compte(s) 18+" if restreints else "",
            f"{morts} mort(s)/renommé(s)" if morts else "",
            "Facebook non mesuré (Apify) — journées non pénalisées" if fb_panne else ""])))
    # UNE priorité, la première qui s'applique — le reste attend le détail.
    if restreints:
        priorite = "lever les restrictions 18+ (trafic perdu à 100 %, gain sans publier plus)"
    elif rates2:
        priorite = f"trancher pour {', '.join(rates2[:3])} — 2 jours ratés, la règle dit sortie lundi"
    elif zeros:
        priorite = f"relancer les {len(zeros)} à zéro (comptes sains, aucune excuse technique)"
    elif morts:
        priorite = "recréer les comptes tombés (Fiche 1)"
    elif comptes and any(max(0, OBJECTIF_COMPTES_IG - f["vivants"]) > 0
                         for n, f in comptes.items()
                         if any(_normaliser(n) == _normaliser(c) for c in TOP_CREATRICES)):
        priorite = "créer des comptes — la file « à créer » du sheet attend les pods"
    else:
        priorite = f"rien d'urgent — féliciter {top[0]} dans #dopamine" if top[0] else "rien d'urgent"
    lignes.append(f"👉 *LA priorité : {priorite}*")
    lignes.append("_Détail par clipper : !inputs detail_")
    return "\n".join(lignes)


def message_lecture(historique: dict) -> str:
    """`!inputs` sans argument : le DERNIER bilan enregistré, sans relancer un cycle (qui re-postait
    les bilans aux clippers et réécrivait l'historique)."""
    if not historique:
        return "📊 Aucun bilan enregistré pour l'instant — `!inputs maintenant` lance le premier cycle."
    jour = sorted(historique)[-1]
    par_clipper = historique[jour]
    clippers = {n: v for n, v in par_clipper.items() if not _normaliser(v.get("creatrice", "")).startswith("metricool")}
    lignes = [f"📊 *Dernier bilan — journée du {jour}* ({len(clippers)} clipper(s))"]
    for n, v in sorted(clippers.items(), key=lambda x: -x[1].get("posts_24h", 0)):
        ok = v.get("journee_ok")
        etat = "🏅" if ok else ("⏸️" if ok is None else "❌")
        lignes.append(f"{etat} {n} — {v.get('posts_24h', 0)} Reels IG · FB {v.get('posts_fb', 0)} · "
                      f"{v.get('followers', 0):,} abo".replace(",", " ")
                      + (" · 🚨 2 j ratés" if v.get("deux_jours_rates") else ""))
    lignes.append("_Relancer le comptage : !inputs maintenant · détail : !inputs detail · paie : !primes_")
    return "\n".join(lignes)


async def archiver_dans_sheet(bilan: dict, brut: dict, date_jour: str):
    """Envoie une ligne par compte et par jour dans l'onglet « Historique » du Sheet. Silencieux si
    non configuré. Le détail par COMPTE (pas seulement par clipper) est volontaire : c'est ce qui
    permet de voir quel compte porte réellement un clipper, et de dater un ban au jour près."""
    if not (SHEET_HISTORIQUE_URL and SHEET_HISTORIQUE_SECRET):
        return
    lignes = []
    for clipper, b in bilan.items():
        for d in b["detail"]:
            lignes.append([date_jour, clipper, b["creatrice"], d["compte"], "Instagram",
                           d["posts_24h"], d["vues_24h"], d["followers"], "", "ok"])
        for compte, etat in ([(c, "restreint 18+") for c in b["restreints"]]
                             + [(c, "privé (compte à lien)") for c in b["prives"]]
                             + [(c, "injoignable") for c in b["injoignables"]]):
            lignes.append([date_jour, clipper, b["creatrice"], compte, "Instagram", 0, 0, 0, "", etat])
        if b.get("pages_fb"):
            lignes.append([date_jour, clipper, b["creatrice"], f"{b['pages_fb']} page(s)", "Facebook",
                           b["posts_fb"], b["vues_fb"], "", "", "ok"])
        if lignes and b.get("delta_followers") is not None:
            lignes[-1][8] = b["delta_followers"]
    if not lignes:
        return
    charge = {"secret": SHEET_HISTORIQUE_SECRET, "lignes": lignes}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(SHEET_HISTORIQUE_URL, json=charge) as reponse:
                corps = await reponse.text()
                if reponse.status >= 400 or '"ok":false' in corps.replace(" ", ""):
                    journal.warning("Archivage Sheet refusé (HTTP %s) : %s", reponse.status, corps[:150])
                else:
                    journal.info("Archivage Sheet : %d ligne(s) pour le %s", len(lignes), date_jour)
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Archivage Sheet injoignable : %s", erreur)


def _sans_markdown(texte: str) -> str:
    """Telegram en Markdown refusait tout message contenant un « _ » ou un « * » orphelin (pseudo
    Instagram avec underscore, par exemple) : le rapport n'arrivait pas. On envoie du texte brut."""
    texte = texte.replace("**", "").replace("*", "")
    return "\n".join(re.sub(r"^_(.+)_$", r"\1", ligne) for ligne in texte.split("\n"))


async def envoyer_telegram(texte: str):
    """Pousse le récap dans le rapport quotidien Telegram (texte brut). Silencieux si non configuré."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    charge = {"chat_id": TELEGRAM_CHAT_ID, "text": _sans_markdown(texte)[:4000]}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=charge) as reponse:
                if reponse.status >= 400:
                    journal.warning("Telegram HTTP %s", reponse.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Telegram injoignable : %s", erreur)


# ------------------------------------------------------------------ 5. exécution
async def executer(client, guild, canal_admin=None, silencieux=False, debuts=None, notifier=None):
    """Un cycle complet pour la journée d'HIER (Paris) : cartographie → Apify → agrégation →
    salons privés + Telegram + salon admin. Retourne (bilan, erreur) : erreur=None si le cycle a
    abouti, sinon la cause (la boucle ne marque la journée faite QUE sur succès).
    silencieux=True : ne poste rien (`!inputs test`/`detail`). notifier(texte) : alerte manager."""
    carte = await cartographier_depuis_sheet(guild)
    source = "Google Sheet"
    if not carte:
        carte, source = cartographier_comptes(guild), "topics Discord"
    if not carte:
        return {}, "aucun compte cartographié (SHEET_CSV_URL illisible et aucun @ dans les topics)"
    journal.info("Cartographie : %d clipper(s) depuis %s", len(carte), source)
    handles = sorted({h for f in carte.values() for h in f["comptes"]})
    pages_fb = sorted({p for f in carte.values() for p in f.get("pages_fb", [])})
    brut = await scraper_apify(handles)
    if not brut:
        return {}, "Apify n'a rien renvoyé (token absent, crédits épuisés ou actor en panne)"
    brut_fb = await scraper_facebook(pages_fb)

    _, _, jour = fenetre_veille()
    donnees = _lire({"historique": {}})
    historique = donnees.setdefault("historique", {})
    # La veille de la journée évaluée = le dernier jour évalué AVANT elle (un cycle rejoué le même
    # jour ne se compare plus à lui-même — audit 10/09).
    anterieurs = sorted(j for j in historique if j < jour)
    veille = historique[anterieurs[-1]] if anterieurs else {}
    bilan = agreger(carte, brut, veille, brut_fb, debuts, jour)
    for n, b in bilan.items():
        hier_b = veille.get(n) or {}
        b["deux_jours_rates"] = bool(b.get("journee_ok") is False and hier_b.get("journee_ok") is False
                                     and not b.get("phase"))
    if silencieux:
        return bilan, None

    historique[jour] = {}
    for n, b in bilan.items():
        ligne = {k: b[k] for k in ("posts_24h", "vues_24h", "followers", "creatrice", "posts_fb",
                                   "structure_ok", "deux_jours_rates")}
        if b.get("journee_ok") is not None:          # clé absente = journée non évaluée
            ligne["journee_ok"] = b["journee_ok"]
        historique[jour][n] = ligne
    compteur = jours_valides_mois(historique, jour[:7])
    for n, b in bilan.items():
        b["jours_ok_mois"] = compteur.get(n, {}).get("valides", 0)
    for vieux in sorted(historique)[:-90]:
        historique.pop(vieux, None)
    _ecrire(donnees)

    for prenom, b in bilan.items():
        salon = client.get_channel(b["canal_id"]) if b.get("canal_id") else None
        if salon is None:
            continue
        try:
            await salon.send(message_clipper(prenom, b))
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Bilan non envoyé à %s : %s", prenom, erreur)
        await asyncio.sleep(1)

    await archiver_dans_sheet(bilan, brut, jour)
    comptes = await compter_comptes_creatrices()
    date_aff = datetime.strptime(jour, "%Y-%m-%d").strftime("%d/%m")
    recap = message_recap(bilan, date_aff, veille, comptes)
    await envoyer_telegram(recap)
    if canal_admin is not None:
        try:
            await canal_admin.send(recap.replace("*", "**")[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass
    # Règle de sortie (grille 07/09) : cadence ratée deux jours de suite → le manager tranche
    # et prévient Gaëtan. L'alerte part au manager le jour même, pas au digest.
    rates2 = [n for n, b in bilan.items() if b.get("deux_jours_rates")
              and not _normaliser(b["creatrice"]).startswith("metricool")]
    sans_salon = [n for n, b in bilan.items() if not b.get("canal_id")]
    if notifier is not None and (rates2 or sans_salon):
        texte_m = ""
        if rates2:
            texte_m += (f"🚨 **Cadence ratée 2 jours de suite** ({date_aff}) : {', '.join(rates2)}\n"
                        "Règle de l'équipe : sortie le lundi suivant, Gaëtan prévenu. Décision : "
                        "`!sortie Prénom cadence ratée 2 jours de suite` — ou une raison valable, notée ici.\n")
        if sans_salon:
            texte_m += (f"ℹ️ Sans salon perso (bilan quotidien non envoyé) : {', '.join(sans_salon[:8])} — "
                        "`!creatrice @clipper Prénom` le crée.")
        try:
            await notifier(texte_m.strip())
        except Exception as erreur:                          # noqa: BLE001
            journal.warning("Alerte manager inputs : %s", erreur)
    journal.info("Inputs clippers (%s) : %d clippers, %d comptes scrapés", jour, len(bilan), len(brut))
    return bilan, None


async def boucle_inputs(client, canal_admin_async, fichier_etat, lire_json, ecrire_json,
                        debuts_fn=None, notifier=None):
    """Boucle quotidienne : une exécution par jour à HEURE_RAPPORT (UTC), 3 tentatives espacées de
    15 min, et la journée n'est marquée faite QUE si le cycle a abouti (un jour d'échec était marqué
    fait → trou d'un jour dans les primes, audit 10/09). Inerte sans APIFY_TOKEN."""
    if not APIFY_TOKEN:
        journal.info("Inputs clippers désactivés (APIFY_TOKEN absent)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = datetime.now(timezone.utc)
            aujourdhui = maintenant.strftime("%Y-%m-%d")
            etat = lire_json(fichier_etat, {})
            if maintenant.hour >= HEURE_RAPPORT and etat.get("inputs") != aujourdhui:
                tentatives = etat.get("inputs_tentatives", {})
                nb = int(tentatives.get(aujourdhui, 0))
                if nb < 3:
                    erreurs = []
                    for guild in client.guilds:
                        _, erreur = await executer(client, guild, await canal_admin_async(),
                                                   debuts=(debuts_fn() if debuts_fn else None), notifier=notifier)
                        if erreur:
                            erreurs.append(erreur)
                    etat = lire_json(fichier_etat, {})
                    if not erreurs:
                        etat["inputs"] = aujourdhui
                        etat.pop("inputs_tentatives", None)
                    else:
                        etat.setdefault("inputs_tentatives", {})[aujourdhui] = nb + 1
                        journal.warning("Inputs clippers : tentative %d/3 échouée — %s", nb + 1, " ; ".join(erreurs))
                        if nb + 1 >= 3:
                            canal = await canal_admin_async()
                            if canal is not None:
                                try:
                                    await canal.send("⚠️ **Inputs clippers : 3 échecs aujourd'hui** — "
                                                     + " ; ".join(erreurs)[:600]
                                                     + "\nLa journée n'est pas évaluée (pas de prime perdue). "
                                                       "`!inputs maintenant` pour réessayer à la main.")
                                except (discord.Forbidden, discord.HTTPException):
                                    pass
                    ecrire_json(fichier_etat, etat)
        except Exception as erreur:                     # une panne ici ne doit jamais tuer le bot
            journal.exception("Boucle inputs clippers : %s", erreur)
        await asyncio.sleep(900)
