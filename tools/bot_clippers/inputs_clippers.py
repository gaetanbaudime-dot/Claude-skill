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
# Cadence exigée par compte de croissance (règle annoncée à l'équipe le 30/07).
CADENCE_MIN = int(os.environ.get("CADENCE_REELS_MIN", "3"))
# Objectif de comptes Instagram VIVANTS par créatrice prioritaire (décision du 02/09 : la machine
# à surfaces neuves — en créer plus qu'il n'en meurt). Le rapport quotidien affiche l'écart.
OBJECTIF_COMPTES_IG = int(os.environ.get("OBJECTIF_COMPTES_IG", "20"))
TOP_CREATRICES = [c.strip() for c in
                  os.environ.get("TOP_CREATRICES", "Chloé,Sarah,Sophie,Maddie").split(",") if c.strip()]
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
    if FICHIER_INPUTS:
        FICHIER_INPUTS.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")


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
    limite = datetime.now(timezone.utc) - timedelta(hours=24)
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
            if quand >= limite:
                posts_24h += 1
                vues_24h += int(post.get("videoViewCount") or post.get("videoPlayCount") or 0)
        resultats[handle] = {
            "followers": int(item.get("followersCount") or 0),
            "posts_24h": posts_24h,
            "vues_24h": vues_24h,
            "total_posts": int(item.get("postsCount") or 0),
        }
    return resultats


async def scraper_facebook(pages: list) -> dict:
    """Pages Facebook publiques → {page: {posts_24h, vues_24h}}. Facultatif : ne tourne que si des
    pages sont déclarées dans les topics (`facebook.com/x` ou `fb:x`). Facebook n'est PAS la
    métrique de discipline (les Reels y sont republiés depuis Instagram) — c'est un second regard.
    resultsLimit reste bas : au-delà, la facture grimpe pour une information qu'on a déjà."""
    if not APIFY_TOKEN or not pages:
        return {}
    url = f"https://api.apify.com/v2/acts/{ACTOR_FB}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    limite = datetime.now(timezone.utc) - timedelta(hours=24)
    charge = {"startUrls": [{"url": f"https://www.facebook.com/{p}"} for p in pages],
              "resultsLimit": FB_POSTS_MAX}
    resultats = {p: {"posts_24h": 0, "vues_24h": 0} for p in pages}
    try:
        delai = aiohttp.ClientTimeout(total=280)
        async with aiohttp.ClientSession(timeout=delai) as session:
            async with session.post(url, json=charge) as reponse:
                if reponse.status >= 400:
                    journal.warning("Apify Facebook HTTP %s", reponse.status)
                    return resultats
                items = await reponse.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Apify Facebook injoignable : %s", erreur)
        return resultats

    for post in items if isinstance(items, list) else []:
        source = (post.get("inputUrl") or "").rstrip("/").rsplit("/", 1)[-1].lower()
        if source not in resultats:
            continue
        try:
            quand = datetime.fromisoformat((post.get("time") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if quand >= limite:
            resultats[source]["posts_24h"] += 1
            resultats[source]["vues_24h"] += int(post.get("viewsCount") or 0)
    return resultats


# ------------------------------------------------------------------ 3. calcul par clipper
def agreger(carte: dict, brut: dict, veille: dict, brut_fb: dict = None) -> dict:
    """Agrège par clipper et calcule les deltas de followers vs la veille."""
    brut_fb = brut_fb or {}
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
        posts_fb = sum(brut_fb.get(p, {}).get("posts_24h", 0) for p in fiche.get("pages_fb", []))
        vues_fb = sum(brut_fb.get(p, {}).get("vues_24h", 0) for p in fiche.get("pages_fb", []))
        avant = (veille.get(clipper) or {}).get("followers")
        hors_service = len(injoignables) + len(restreints) + len(prives)
        bilan[clipper] = {
            "creatrice": fiche["creatrice"],
            "canal_id": fiche["canal_id"],
            "comptes_suivis": len(fiche["comptes"]),
            "posts_24h": posts,
            "vues_24h": vues,
            "followers": followers,
            "delta_followers": (followers - avant) if isinstance(avant, int) else None,
            "pages_fb": len(fiche.get("pages_fb", [])),
            "posts_fb": posts_fb,
            "vues_fb": vues_fb,
            "injoignables": injoignables,
            "restreints": restreints,
            "prives": prives,
            "detail": detail,
            # Cadence attendue : CADENCE_MIN par compte réellement mesurable — on n'exige pas
            # une cadence sur un compte banni, restreint ou passé en privé.
            "cadence_attendue": CADENCE_MIN * max(1, len(fiche["comptes"]) - hors_service),
        }
    return bilan


# ------------------------------------------------------------------ 4. messages
def message_clipper(prenom: str, b: dict) -> str:
    """Le bilan personnel envoyé dans le salon privé du clipper — factuel, jamais moralisateur."""
    posts, cible = b["posts_24h"], b["cadence_attendue"]
    if posts >= cible:
        entete = f"✅ **{posts} Reels hier** — cadence tenue (objectif {cible}). Continue exactement comme ça."
    elif posts > 0:
        entete = (f"⚠️ **{posts} Reels hier** — objectif {cible}. Il t'en manque **{cible - posts}** "
                  f"pour valider ta journée.")
    else:
        entete = (f"🔴 **0 Reel publié hier** (objectif {cible}). Si tu es bloqué sur quelque chose, "
                  f"dis-le ici maintenant — on débloque en 5 minutes.")
    lignes = [f"📊 **Ton bilan d'hier — {prenom}**", "", entete, ""]
    if b["vues_24h"]:
        lignes.append(f"👁️ **{b['vues_24h']:,}** vues sur tes Reels d'hier".replace(",", " "))
    lignes.append(f"👥 **{b['followers']:,}** abonnés cumulés".replace(",", " ")
                  + (f" ({b['delta_followers']:+d} depuis hier)" if b["delta_followers"] is not None else ""))
    if b["restreints"]:
        lignes.append(f"\n🔞 **URGENT — compte(s) marqué(s) 18+ par Instagram** : "
                      f"{', '.join('@' + c for c in b['restreints'])}.\n"
                      "Ton compte est **invisible pour toute personne non connectée** et sa portée est "
                      "massacrée : tu peux publier 20 Reels par jour, ils ne sortiront quasiment pas.\n"
                      "→ Instagram : Paramètres → **Confidentialité du compte / Public visé** et demande "
                      "la levée de la restriction. Envoie-moi une capture ici, on le règle aujourd'hui.")
    if b["prives"]:
        lignes.append(f"\n🔒 **Compte(s) à lien en privé** : {', '.join('@' + c for c in b['prives'])} — "
                      "c'est **normal et voulu** (le lien reste visible de tous, seules les publications "
                      "sont masquées). Je ne peux simplement pas compter leurs Reels : ta cadence n'est "
                      "calculée que sur tes comptes de croissance.")
    if b["injoignables"]:
        lignes.append(f"\n🚫 **Compte(s) injoignable(s)** : {', '.join('@' + c for c in b['injoignables'])} — "
                      "compte banni ou renommé ? Préviens-moi, on recrée (Fiche 1).")
    if b.get("pages_fb"):
        lignes.append(f"📘 Facebook : **{b['posts_fb']}** publication(s) hier"
                      + (f" · {b['vues_fb']:,} vues".replace(",", " ") if b["vues_fb"] else ""))
    lignes.append("\n-# Rappel : ta commission de 0,50 €/abonné n'a aucun plafond. "
                  "Plus tu publies, plus elle monte. "
                  + ("" if b.get("pages_fb") else
                     "Et Facebook reste obligatoire même s'il n'est pas compté ici."))
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
    """Le rapport quotidien COURT (≤ 8 lignes) : le total et sa tendance, qui publie et qui est à
    zéro, l'inventaire de surfaces face à l'objectif, les incidents, et UNE priorité. Tout le
    reste vit derrière `!inputs detail` — un rapport qu'on ne lit plus ne pilote rien."""
    if not bilan:
        return (f"📊 *MARKETING — {date_jour}*\n\nAucun compte cartographié "
                "(vérifie `SHEET_CSV_URL` ou les topics des salons).")
    total = sum(b["posts_24h"] for b in bilan.values())
    total_vues = sum(b["vues_24h"] for b in bilan.values())
    total_hier = sum(v.get("posts_24h", 0) for v in veille.values()) if veille else None
    actifs = [n for n, b in bilan.items() if b["posts_24h"] > 0]
    zeros = [n for n, b in bilan.items() if b["posts_24h"] == 0 and b["comptes_suivis"]
             and not b["restreints"] and not b["injoignables"]]
    restreints = sum(len(b["restreints"]) for b in bilan.values())
    morts = sum(len(b["injoignables"]) for b in bilan.values())
    top = max(bilan.items(), key=lambda x: x[1]["posts_24h"], default=(None, None))

    tendance = f" ({total - total_hier:+d} vs hier)" if total_hier is not None else ""
    feu = "🟢" if total_hier is None or total >= total_hier else "🔴"
    lignes = [f"📊 *MARKETING — {date_jour}*",
              f"{feu} *{total} Reels*{tendance} · {total_vues:,} vues · "
              f"{len(actifs)}/{len(bilan)} ont publié".replace(",", " ")]
    if top[0] and top[1]["posts_24h"]:
        ligne_top = f"🥇 {top[0]} ({top[1]['posts_24h']})"
        if zeros:
            ligne_top += f" — 🔴 zéro : {', '.join(zeros[:5])}" + (f" +{len(zeros)-5}" if len(zeros) > 5 else "")
        lignes.append(ligne_top)
    surfaces = bloc_comptes(comptes or {})
    if surfaces:
        lignes.append(surfaces)
    if restreints or morts:
        lignes.append("❗ " + " · ".join(filter(None, [
            f"{restreints} compte(s) 18+" if restreints else "",
            f"{morts} mort(s)/renommé(s)" if morts else ""])))
    # UNE priorité, la première qui s'applique — le reste attend le détail.
    if restreints:
        priorite = "lever les restrictions 18+ (trafic perdu à 100 %, gain sans publier plus)"
    elif comptes and any(max(0, OBJECTIF_COMPTES_IG - f["vivants"]) > 0
                         for n, f in comptes.items()
                         if any(_normaliser(n) == _normaliser(c) for c in TOP_CREATRICES)):
        priorite = "créer des comptes — la file « à créer » du sheet attend les pods"
    elif zeros:
        priorite = f"relancer les {len(zeros)} à zéro (comptes sains, aucune excuse technique)"
    elif morts:
        priorite = "recréer les comptes tombés (Fiche 1)"
    else:
        priorite = f"rien d'urgent — féliciter {top[0]} dans #dopamine" if top[0] else "rien d'urgent"
    lignes.append(f"👉 *LA priorité : {priorite}*")
    lignes.append("_Détail par clipper : !inputs detail_")
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


async def envoyer_telegram(texte: str):
    """Pousse le récap dans le rapport quotidien Telegram. Silencieux si non configuré."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    charge = {"chat_id": TELEGRAM_CHAT_ID, "text": texte[:4000], "parse_mode": "Markdown"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=charge) as reponse:
                if reponse.status >= 400:
                    journal.warning("Telegram HTTP %s", reponse.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Telegram injoignable : %s", erreur)


# ------------------------------------------------------------------ 5. exécution
async def executer(client, guild, canal_admin=None, silencieux=False) -> dict:
    """Un cycle complet : cartographie → Apify → agrégation → salons privés + Telegram.
    Retourne le bilan (vide si rien à faire). silencieux=True : ne poste rien, sert à `!inputs test`."""
    # Le Google Sheet fait foi ; les topics Discord ne servent que s'il n'est pas configuré
    # (ou illisible) — ainsi une panne du sheet n'arrête jamais le suivi.
    carte = await cartographier_depuis_sheet(guild)
    source = "Google Sheet"
    if not carte:
        carte, source = cartographier_comptes(guild), "topics Discord"
    if not carte:
        return {}
    journal.info("Cartographie : %d clipper(s) depuis %s", len(carte), source)
    handles = sorted({h for f in carte.values() for h in f["comptes"]})
    pages_fb = sorted({p for f in carte.values() for p in f.get("pages_fb", [])})
    brut = await scraper_apify(handles)
    brut_fb = await scraper_facebook(pages_fb)
    if not brut:
        if canal_admin is not None and not silencieux:
            await canal_admin.send("⚠️ **Inputs clippers** : Apify n'a rien renvoyé "
                                   "(token absent, crédits épuisés ou actor en panne).")
        return {}

    donnees = _lire({"historique": {}})
    hier = sorted(donnees.get("historique", {}))
    veille = donnees["historique"][hier[-1]] if hier else {}
    bilan = agreger(carte, brut, veille, brut_fb)
    if silencieux:
        return bilan

    aujourdhui = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    donnees.setdefault("historique", {})[aujourdhui] = {
        n: {k: b[k] for k in ("posts_24h", "vues_24h", "followers", "creatrice")} for n, b in bilan.items()}
    # On ne garde que 90 jours : le volume Railway n'est pas une base de données.
    for vieux in sorted(donnees["historique"])[:-90]:
        donnees["historique"].pop(vieux, None)
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

    await archiver_dans_sheet(bilan, brut, aujourdhui)
    comptes = await compter_comptes_creatrices()
    recap = message_recap(bilan, datetime.now(timezone.utc).strftime("%d/%m"), veille, comptes)
    await envoyer_telegram(recap)
    if canal_admin is not None:
        try:
            await canal_admin.send(recap.replace("*", "**")[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass
    journal.info("Inputs clippers : %d clippers, %d comptes scrapés", len(bilan), len(brut))
    return bilan


async def boucle_inputs(client, canal_admin_async, fichier_etat, lire_json, ecrire_json):
    """Boucle quotidienne : une exécution par jour à HEURE_RAPPORT (UTC). Ne démarre que si
    APIFY_TOKEN est configuré — sans lui, le module reste totalement inerte."""
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
                for guild in client.guilds:
                    await executer(client, guild, await canal_admin_async())
                etat["inputs"] = aujourdhui
                ecrire_json(fichier_etat, etat)
        except Exception as erreur:                     # une panne ici ne doit jamais tuer le bot
            journal.exception("Boucle inputs clippers : %s", erreur)
        await asyncio.sleep(900)
