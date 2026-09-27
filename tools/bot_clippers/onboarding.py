"""Onboarding automatique d'un clipper (machine horizontale v2, 23/09/2026).

Quand un manager attribue une créatrice (`!creatrice @clipper Prénom`), ou quand un nom de clipper
apparaît dans la colonne Gérant du classeur des logins, le bot livre dans le salon perso du clipper :

  1. ses identités de comptes Instagram (COMPTES_PAR_CLIPPER, 3 par défaut) prises dans le classeur des
     logins (Utilisation = Clipper, Gérant libre, Créatrice = la sienne), et il écrit son prénom dans la
     colonne Gérant : le classeur reste la source de vérité, modifiable à la main ;
  2. son lien GAML (cloné depuis un lien « Clipping » de la créatrice si aucun ne lui est attribué) ;
  3. son dossier Drive personnel (photos et Reels de la créatrice), copié et partagé par le script de
     l'agence quand il est déployé (drive_agence.py), sinon rien.

Le classeur (27/09) : **un onglet par créatrice** (Chloé, Sarah, Sophie, Jade, Maddie, Clara…), découverts tout seuls ;
les onglets Gaetan, Tracking, Backup sont ignorés (ONGLETS_EXCLUS) et l'ancien onglet global « Instagram » n'est lu que
s'il n'y a aucun onglet créatrice. Colonnes reconnues par leur en-tête : ETAT · @ IG · MDP · Followers · Clics · Mail ·
Phone · Gérant · Utilisation · Numéro Mail · Créatrice · POD · Lien Infloww Tracking · Lien GAML associé. Une ligne
sans Créatrice prend le nom de son onglet ; chaque ligne garde son onglet, les écritures y retournent (`cellule`).
Variables : CLASSEUR_LOGINS_ID (obligatoire), ONGLET_LOGINS (vide = automatique, ou « Sarah, Sophie » pour forcer),
ONGLETS_EXCLUS, COMPTES_PAR_CLIPPER (3), DRIVE_SOURCES (JSON : {"Chloé": {"parent": id, "sources": [id, …]}}).
Le module ne connaît pas bot_discord : dépendances dans `demarrer(deps)`.
"""

import asyncio
import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import discord

import codes_2fa
import drive_agence
import google_api
import paie_clics
import roster

journal = logging.getLogger("onboarding")

CLASSEUR_LOGINS_ID = os.environ.get("CLASSEUR_LOGINS_ID", "").strip()
ONGLET_LOGINS = os.environ.get("ONGLET_LOGINS", "").strip()             # 27/09 : vide ou « auto » = un onglet par créatrice, découverts
ONGLETS_EXCLUS = os.environ.get("ONGLETS_EXCLUS", "Gaetan, Gaëtan, Tracking, Backup, Candidatures, Modèle, Template, Archive")
ONGLETS_HERITES = ("instagram", "logins", "comptes")                     # l'ancien onglet global : lu seulement sans onglet créatrice
CACHE_ONGLETS_SEC = 600                                                  # la liste des onglets est relue toutes les 10 minutes
_onglets_cache = {"quand": 0.0, "titres": []}
_colonnes_par_onglet = {}
_doublons_vus = set()
COMPTES_PAR_CLIPPER = int(os.environ.get("COMPTES_PAR_CLIPPER", "3") or 3)
GERANTS_LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
ETATS_DISPONIBLES = {"a creer", "à créer", "good", "warmup", "warm-up", "prive", "privé", "actif", "ok"}
COL_DEFAUT = {"etat": 0, "handle": 1, "mdp": 2, "followers": 3, "mail": 4, "phone": 5, "gerant": 6, "utilisation": 7, "numero": 8, "creatrice": 9}
# 26/09 : Gaëtan insère des colonnes (Clics GAML, Lien GAML associé) → les colonnes se trouvent par leur en-tête, jamais par position
MOTS_COLONNES = (("etat", ("etat", "statut")), ("handle", ("@", "ig", "compte", "pseudo")), ("mdp", ("mdp", "mot de passe", "password")),
                 ("followers", ("followers", "abonnes")), ("clics", ("clics", "gaml last", "visites")), ("numero", ("numero",)),
                 ("mail", ("mail", "email")), ("phone", ("phone", "tel")), ("gerant", ("gerant", "clipper")),
                 ("utilisation", ("utilisation", "usage")), ("creatrice", ("creatrice",)), ("pod", ("pod",)),
                 ("lien_gaml", ("lien gaml", "gaml associe")), ("lien_infloww", ("infloww",)))
_colonnes = dict(COL_DEFAUT)


def _colonnes_trouvees(en_tete: list) -> dict:
    trouve = {}
    pris = set()
    for champ, mots in MOTS_COLONNES:
        for i, h in enumerate(en_tete):
            hn = _norm(h)
            if i in pris or not hn:
                continue
            if champ == "mail" and "numero" in hn:
                continue                                                # « Numéro Mail » n'est pas la colonne Mail
            if any(m in hn for m in mots):
                trouve[champ] = i
                pris.add(i)
                break
    return trouve


def en_tete_reconnu(en_tete: list) -> bool:
    """Vrai si la ligne d'en-tête est celle d'un onglet de logins (ETAT, @ IG et Gérant repérés)."""
    return all(k in _colonnes_trouvees(en_tete) for k in ("etat", "handle", "gerant"))


def colonnes(en_tete: list) -> dict:
    """{champ: index de colonne} d'après la ligne d'en-tête (accents/casse ignorés, premier mot-clé gagnant, une colonne
    ne sert qu'une fois). Sans en-tête reconnu, l'ordre historique."""
    trouve = _colonnes_trouvees(en_tete)
    if not all(k in trouve for k in ("etat", "handle", "gerant")):
        return dict(COL_DEFAUT)
    return {**COL_DEFAUT, **trouve}


def lettre(champ: str, onglet: str = "") -> str:
    """La lettre de colonne d'un champ (A, B, …, AA) d'après l'en-tête de cet onglet (27/09 : Gaëtan peut insérer une
    colonne dans un onglet et pas dans l'autre), sinon le dernier en-tête lu."""
    cols = _colonnes_par_onglet.get(onglet) or _colonnes
    i = cols.get(champ, COL_DEFAUT.get(champ, 0))
    return (chr(64 + i // 26) if i >= 26 else "") + chr(65 + i % 26)


def a_colonne(champ: str, onglet: str = "") -> bool:
    """L'onglet a-t-il cette colonne (clics, lien_gaml… ne sont écrits que si l'en-tête les porte) ?"""
    return champ in (_colonnes_par_onglet.get(onglet) or _colonnes)


def onglet_a1(titre: str) -> str:
    """Le nom d'onglet tel qu'il s'écrit dans une plage A1 : Instagram tel quel, « 'Chloé' » entre apostrophes dès
    qu'il y a un accent, un espace ou un signe (apostrophes internes doublées)."""
    if re.fullmatch(r"[A-Za-z0-9_]+", titre or ""):
        return titre
    return "'" + (titre or "").replace("'", "''") + "'"


def cellule(c: dict, champ: str) -> str:
    """La plage A1 d'une cellule d'une ligne lue par lire_comptes : « 'Sarah'!G12 ». L'écriture retourne toujours dans
    l'onglet d'où vient la ligne."""
    onglet = c.get("onglet") or _onglet_par_defaut()
    return f"{onglet_a1(onglet)}!{lettre(champ, onglet)}{c['ligne']}"


def _onglet_par_defaut() -> str:
    if ONGLET_LOGINS and _norm(ONGLET_LOGINS) not in ("auto", "*", "tous", "toutes"):
        return ONGLET_LOGINS.split(",")[0].strip()
    return (_onglets_cache["titres"] or ["Instagram"])[0]
RE_PRIVE = re.compile(r"priv|secret|onlyme|perso")                 # handle d'un compte privé (le 3e du trio)
JOURS_NOUVEAU = int(os.environ.get("ONBOARDING_JOURS_NOUVEAU", "45") or 45)   # un membre arrivé depuis moins longtemps est « nouveau »
A_CREER = ("a creer", "à créer")
MENTION_LIBERE = "à mettre Metricool"                              # Utilisation d'un compte créé rendu par un clipper parti

_deps = {}


def configurer(deps: dict):
    """À appeler dès le démarrage : `livrer` peut être déclenché par !creatrice avant le premier tour de boucle."""
    global _deps
    _deps = deps


def actif() -> bool:
    return bool(CLASSEUR_LOGINS_ID and google_api.actif())


def _norm(t: str) -> str:
    if _deps.get("normaliser"):
        return _deps["normaliser"](t or "")
    t = unicodedata.normalize("NFD", (t or "").strip().lower())            # même règle que bot_discord : sans accents, minuscules
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _exclus() -> set:
    return {_norm(t).strip() for t in ONGLETS_EXCLUS.split(",") if t.strip()}


def _sources() -> dict:
    try:
        return json.loads(os.environ.get("DRIVE_SOURCES", "") or "{}")
    except ValueError:
        journal.warning("DRIVE_SOURCES illisible (JSON attendu)")
        return {}


def _lire_etat() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {})
    d.setdefault("livres", {}); d.setdefault("clippers", {})
    return d


def _ecrire_etat(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_ONBOARDING"], d)


# ------------------------------------------------------------------ classeur
async def onglets_logins(forcer: bool = False) -> list:
    """Les onglets du classeur à lire, dans l'ordre du classeur (27/09 : Gaëtan a fait une feuille par créatrice).
    ONGLET_LOGINS explicite (« Sarah, Sophie ») gagne. Sinon : tous les onglets visibles dont l'en-tête est celui des
    logins, sauf ONGLETS_EXCLUS (Gaetan, Tracking, Backup…) et les onglets masqués ; l'ancien onglet global « Instagram »
    n'est lu que s'il n'y a aucun onglet créatrice. Liste gardée CACHE_ONGLETS_SEC secondes."""
    global _onglets_cache
    if ONGLET_LOGINS and _norm(ONGLET_LOGINS) not in ("auto", "*", "tous", "toutes"):
        return [t.strip() for t in ONGLET_LOGINS.split(",") if t.strip()]
    if not forcer and _onglets_cache["titres"] and time.time() - _onglets_cache["quand"] < CACHE_ONGLETS_SEC:
        return list(_onglets_cache["titres"])
    titres = [t for t in await google_api.sheets_onglets_visibles(CLASSEUR_LOGINS_ID) if _norm(t).strip() not in _exclus()]
    if not titres:
        return []
    en_tetes = await google_api.sheets_lire_plusieurs(CLASSEUR_LOGINS_ID, [f"{onglet_a1(t)}!A1:Z1" for t in titres])
    reconnus = [t for t, bloc in zip(titres, en_tetes) if bloc and en_tete_reconnu(bloc[0])]
    creatrices = [t for t in reconnus if _norm(t).strip() not in ONGLETS_HERITES]
    retenus = creatrices or [t for t in reconnus if _norm(t).strip() in ONGLETS_HERITES]
    if retenus != _onglets_cache["titres"]:
        journal.info("Classeur des logins : onglets lus → %s", ", ".join(retenus) or "aucun")
    _onglets_cache = {"quand": time.time(), "titres": list(retenus)}
    return list(retenus)


async def lire_comptes() -> list:
    """Toutes les lignes de tous les onglets créatrices (index de ligne 1-based et nom d'onglet inclus), colonnes reconnues
    par leur en-tête onglet par onglet, cellules manquantes complétées. Une ligne sans Créatrice prend le nom de son onglet."""
    global _colonnes
    titres = await onglets_logins()
    if not titres:
        return []
    if len(titres) == 1:
        blocs = [await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{onglet_a1(titres[0])}!A1:Z")]
    else:
        blocs = await google_api.sheets_lire_plusieurs(CLASSEUR_LOGINS_ID, [f"{onglet_a1(t)}!A1:Z" for t in titres])
    out = []
    for titre, lignes in zip(titres, blocs):
        if not lignes:
            continue
        cols = colonnes(lignes[0])
        _colonnes_par_onglet[titre] = cols
        if titre == titres[0]:
            _colonnes = cols
        herite = _norm(titre).strip() in ONGLETS_HERITES
        for i, l in enumerate(lignes[1:], start=2):
            l = (l + [""] * 26)[:26]
            def champ(nom):
                return l[cols[nom]].strip() if nom in cols else ""
            out.append({"onglet": titre, "ligne": i, "etat": champ("etat"), "handle": champ("handle").lstrip("@"), "mdp": champ("mdp"),
                        "followers": champ("followers"), "clics": champ("clics"), "mail": champ("mail"), "phone": champ("phone"),
                        "gerant": champ("gerant"), "utilisation": champ("utilisation"), "numero": champ("numero"),
                        "creatrice": champ("creatrice") or ("" if herite else titre), "lien_gaml": champ("lien_gaml"),
                        "pod": champ("pod"), "lien_infloww": champ("lien_infloww")})
    return _sans_doublons(out)


def _sans_doublons(lignes: list) -> list:
    """Un même handle présent sur deux onglets (copier-coller entre feuilles) : on garde les lignes de l'onglet de SA
    créatrice, sinon celles du premier onglet ; avertissement une fois. Les doublons à l'intérieur d'un onglet restent."""
    global _doublons_vus
    par_handle = {}
    for c in lignes:
        if c["handle"]:
            par_handle.setdefault(c["handle"].lower(), []).append(c)
    ecartes, doublons = set(), set()
    for h, cs in par_handle.items():
        onglets = {c["onglet"] for c in cs}
        if len(onglets) < 2:
            continue
        doublons.add(h)
        chez_elle = [c for c in cs if _norm(c["creatrice"]).split() and _norm(c["onglet"]).startswith(_norm(c["creatrice"]).split()[0])]
        garde = (chez_elle or cs)[0]["onglet"]
        ecartes.update(id(c) for c in cs if c["onglet"] != garde)
    if doublons and doublons != _doublons_vus:
        journal.warning("Classeur : %d compte(s) présent(s) sur plusieurs onglets, seule la ligne de l'onglet de la créatrice compte : %s",
                        len(doublons), ", ".join(sorted(doublons)[:10]))
    _doublons_vus = doublons
    return [c for c in lignes if id(c) not in ecartes]


def tracking_du_pod(tous: list, comptes: list) -> tuple:
    """(lien de tracking OnlyFans, POD) des comptes d'un clipper : Gaëtan pose le lien sur la première ligne du POD dans la
    colonne « Lien Infloww Tracking » (27/09). Sans POD : la première ligne du clipper qui en porte un."""
    pod = next((str(c.get("pod") or "").strip() for c in comptes if str(c.get("pod") or "").strip()), "")
    # Les numéros de POD se répètent d'une créatrice à l'autre (Sarah POD 2, Jade POD 2…) : on reste dans la créatrice des comptes.
    creatrice = next((_norm(c.get("creatrice") or "").split()[0] for c in comptes if _norm(c.get("creatrice") or "").split()), "")
    candidats = [c for c in tous if pod and str(c.get("pod") or "").strip() == pod
                 and (not creatrice or (_norm(c.get("creatrice") or "").split() or [""])[0] == creatrice)] or list(comptes)
    for c in candidats:
        url = str(c.get("lien_infloww") or "").strip()
        if url.startswith("http"):
            return url, pod
    return "", pod


def _pour_creatrice(c: dict, creatrice: str) -> bool:
    cible = _norm(creatrice).split()[0] if _norm(creatrice) else ""
    return bool(cible) and _norm(c["creatrice"]).startswith(cible)


def _est_prive(c: dict) -> bool:
    return _norm(c["etat"]) in ("prive", "privé") or RE_PRIVE.search(_norm(c["handle"] or "")) is not None


def _crees(lignes: list) -> list:
    return [c for c in lignes if _norm(c["etat"]) not in A_CREER]


def disponibles(comptes: list, creatrice: str, n: int) -> list:
    """Lignes libres pour cette créatrice : Utilisation = Clipper, Gérant libre, état utilisable, handle présent.
    Les comptes déjà créés (GOOD, WARMUP, PRIVÉ, ACTIF) passent avant ceux « à créer ». Le trio livré fait
    n-1 comptes de croissance + 1 compte privé quand le classeur en a un (24/09 : avant, le « privé » annoncé
    était juste le dernier de la liste)."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)
              and (c.get("mail") or _norm(c["etat"]) not in A_CREER)]        # 25/09 : un compte à créer sans e-mail est inutilisable
    # 26/09 (Gaëtan) : « un nouveau = 3 nouveaux comptes et mails, dans les nouveaux PODs ». Le POD le plus bas où la
    # créatrice a n lignes « à créer » libres avec e-mail gagne ; les comptes déjà créés (rendus par un ancien) passent en dernier.
    neufs = [c for c in libres if _norm(c["etat"]) in A_CREER and c.get("mail")]
    pods = {}
    for c in neufs:
        if str(c.get("pod") or "").strip():
            pods.setdefault(str(c["pod"]).strip(), []).append(c)
    for pod in sorted(pods, key=lambda p: (not p.isdigit(), int(p) if p.isdigit() else p)):
        if len(pods[pod]) >= n:
            return sorted(pods[pod], key=lambda c: c["ligne"])[:n]
    libres.sort(key=lambda c: (_norm(c["etat"]) not in A_CREER, not c.get("mail"), c["ligne"]))
    if n < 3:
        return libres[:n]
    choix = [c for c in libres if not _est_prive(c)][:n - 1] + [c for c in libres if _est_prive(c)][:1]
    if len(choix) < n:                                              # pas assez d'un côté : on complète avec le reste
        choix += [c for c in libres if c not in choix][:n - len(choix)]
    return choix


def pool(comptes: list, creatrice: str) -> dict:
    """État du vivier d'une créatrice : lignes « à créer » libres, dont celles avec e-mail (les seules livrables),
    et comptes déjà créés libres. 25/09 : Chloé avait 18 lignes à créer, zéro avec e-mail."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)]
    a_creer = [c for c in libres if _norm(c["etat"]) in A_CREER]
    return {"a_creer": len(a_creer), "avec_mail": sum(1 for c in a_creer if c.get("mail")),
            "crees": len(libres) - len(a_creer), "livrables": len(disponibles(comptes, creatrice, 999))}


async def marquer_etat(handle: str, etat: str) -> bool:
    """Colonne ETAT du classeur pour un compte (25/09 : le parcours passe une ligne à WARMUP quand le clipper valide
    la création, puis à GOOD après le warm-up). Une seule cellule, jamais la structure."""
    if not actif() or not handle:
        return False
    cible = _norm(handle).lstrip("@")
    for c in await lire_comptes():
        if _norm(c["handle"]).lstrip("@") == cible:
            if _norm(c["etat"]) == _norm(etat):
                return True
            try:
                await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "etat"), [[etat]])
                journal.info("Classeur : %s → %s (%s, ligne %s)", c["handle"], etat, c.get("onglet") or "?", c["ligne"])
                return True
            except Exception as erreur:
                journal.warning("Classeur : état de %s non écrit : %s", c["handle"], erreur)
                return False
    return False


def _nouveau(membre, etat: dict) -> bool:
    """Un clipper que le bot n'a jamais onboardé (aucune créatrice dans sa fiche) et arrivé sur le serveur depuis
    moins de JOURS_NOUVEAU jours. Un tel membre ne peut pas légitimement posséder des comptes déjà créés :
    si le classeur en porte à son prénom, c'est l'homonyme d'un ancien clipper (Eddy, 24/09)."""
    uid = str(membre.id)
    if etat["clippers"].get(uid, {}).get("creatrice"):
        return False
    if _deps.get("lire_json") and _deps.get("FICHIER_EQUIPES") and \
            _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {}).get("creatrice"):
        return False                                                # `!creatrice` déjà passé : clipper établi
    arrive = getattr(membre, "joined_at", None)
    if arrive is None:
        return True
    if arrive.tzinfo is None:
        arrive = arrive.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - arrive).days < JOURS_NOUVEAU


def _ecarter(etat: dict, membre, lignes: list) -> list:
    """Les comptes déjà créés qu'on ne livre pas à un nouveau venu, mémorisés dans etat["ecartes"] pour que la
    boucle ne les représente pas toutes les 15 minutes. Levés par `!onboarding` (forçage) ou `!liberer`."""
    douteux = _crees(lignes)
    ecartes = etat.setdefault("ecartes", {})
    for c in douteux:
        ecartes[c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return douteux


def _ecarte_pour(etat: dict, c: dict, uid: str) -> bool:
    return etat.get("ecartes", {}).get(c["handle"].lower(), {}).get("uid") == str(uid)


async def reserver(comptes: list, prenom_clipper: str) -> int:
    """Écrit le prénom du clipper dans la colonne Gérant de chaque ligne. Renvoie le nombre de cellules écrites."""
    n = 0
    for c in comptes:
        n += await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "gerant"), [[prenom_clipper]])
    return n


def acces_ordonnes(comptes: list) -> list:
    """[{handle, mdp, mail}] dans l'ordre du parcours : les comptes de croissance d'abord, le privé en dernier."""
    ordonnes = sorted(comptes, key=_est_prive)
    return [{"handle": c.get("handle", ""), "mdp": c.get("mdp", ""), "mail": c.get("mail", ""), "prive": bool(_est_prive(c))}
            for c in ordonnes]


def message_comptes_court(prenom: str) -> str:
    """27/09 (Gaëtan : « donne les comptes 24 h par 24 h, pas un message énorme dès le début ») : une ligne. Chaque accès
    (identifiant, mot de passe, e-mail) arrive dans l'étape du jour du parcours, un par jour."""
    return (f"🔐 {prenom}, tes accès arrivent **un par jour**, dans l'étape du jour. "
            "Ils sont à l'agence : tu ne les donnes à personne.")


def message_comptes(comptes: list, prenom: str, creatrice: str) -> str:
    """26/09 (Gaëtan : « hyper long, trop d'informations ») : les 3 comptes et une ligne de règle, rien d'autre.
    Depuis le 27/09, ne sert plus qu'à `!onboarding` forcé (COMPTES_UN_PAR_JOUR=0 pour le rétablir partout)."""
    if not comptes:
        return (f"⚠️ Il n'y a pas encore de compte prêt pour {creatrice}. Ton manager en prépare. "
                "Je te les envoie ici dès qu'ils sont prêts.")
    blocs = []
    ordonnes = sorted(comptes, key=_est_prive)                      # le privé en dernier
    a_un_prive = any(_est_prive(c) for c in comptes)
    for i, c in enumerate(ordonnes, start=1):
        prive = _est_prive(c) if a_un_prive else (i == len(ordonnes) and len(ordonnes) >= 3)
        role = "privé, ton compte secret" if prive else "il publie"
        deja = "" if _norm(c["etat"]) in A_CREER else " · déjà créé"
        blocs.append(f"**Compte {i} · `{c['handle']}`** · {role}{deja}\n"
                     f"Mot de passe `{c['mdp'] or 'demande-le à ton manager'}`"
                     + (f" · e-mail `{c['mail']}`" if c["mail"] else "")
                     + (f" · tél `{c['phone']}`" if c["phone"] else ""))
    return (f"🔐 **Tes comptes Instagram, {prenom}** · créatrice : {creatrice}\n\n" + "\n\n".join(blocs) + "\n\n"
            "Un compte par jour, sur ton téléphone seulement. Ces accès sont à l'agence : tu ne les donnes à personne.")


# ------------------------------------------------------------------ Drive
async def _partager(fichier_id: str, email: str) -> bool:
    """Partage en lecture : par le compte de service d'abord, par le script de l'agence sinon."""
    try:
        await google_api.drive_partager(fichier_id, email, "reader")
        return True
    except RuntimeError as erreur:
        journal.info("Partage par le compte de service refusé (%s), essai par le script", str(erreur)[:80])
    if drive_agence.actif():
        try:
            await drive_agence.partager(fichier_id, email, "reader")
            return True
        except RuntimeError as erreur:
            journal.warning("Partage Drive %s : %s", fichier_id[:8], erreur)
    return False


UN_PAR_JOUR = os.environ.get("COMPTES_UN_PAR_JOUR", "1").strip() != "0"   # 27/09 : un accès par jour, dans l'étape du jour
NOM_TOP20 = "TOP 20 Reels"                     # le sous-dossier des Reels uniques du clipper (27/09, avant : « Reels uniques »)


async def restructurer_drives(client, prenoms_par_creatrice: dict, email_de) -> list:
    """Au démarrage, une fois (marqueur dans l'état) : chaque clipper du roster retrouve la structure Photos / Reels / Stories /
    TOP 20 Reels dans son dossier Drive. `email_de(prenom)` renvoie l'adresse connue ou ''. Renvoie les prénoms traités."""
    if not google_api.actif():
        return []
    etat = _lire_etat()
    if etat.get("drive_structure") == 3:
        return []
    faits = []
    for creatrice, prenoms in (prenoms_par_creatrice or {}).items():
        for prenom in prenoms:
            try:
                if await dossier_drive(prenom, creatrice, email_de(prenom) or ""):
                    faits.append(prenom)
            except Exception as erreur:                                     # noqa: BLE001
                journal.warning("Structure Drive de %s (%s) : %s", prenom, creatrice, erreur)
    etat["drive_structure"] = 3
    _ecrire_etat(etat)
    journal.info("Structure Drive v2 posée pour %d clipper(s)", len(faits))
    return faits


async def dossier_drive(prenom: str, creatrice: str, email: str) -> str:
    """Dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice : un raccourci vers CHAQUE source (Reels,
    photos : tout le contenu, rien de copié, aucun espace consommé), les sources partagées en lecture à son e-mail.
    Décision du 24/09 : plus de copies limitées ; 25/09 : plus de sous-dossier « Reels spoofés » (spoofer abandonné).
    '' si le Drive n'est pas configuré."""
    if not google_api.actif():
        return ""
    cfg = _sources().get(creatrice) or _sources().get(creatrice.split()[0]) or {}
    parent, sources = cfg.get("parent", ""), cfg.get("sources", [])
    if not parent or not sources:
        journal.info("DRIVE_SOURCES sans entrée pour %s", creatrice)
        return ""
    dossier = await google_api.drive_trouver_dossier(prenom, parent) or await google_api.drive_creer_dossier(prenom, parent)
    # 27/09 (Gaëtan) : « pour chaque clipper, un dossier avec dedans : Photos, Reels, TOP 20 Reels ». Les raccourcis portent
    # le nom de la source tel quel (« Photos », « Reels », « Stories »), les anciens « Photos — Chloé » sont renommés, et le
    # sous-dossier « TOP 20 Reels » (ses Reels uniques) existe dès le départ, même vide.
    existants = await google_api.drive_lister(dossier)
    vus = {}
    for src in sources:
        if not isinstance(src, dict):
            src = {"id": src}
        libelle = src.get("sous") or "Contenu"
        vus[libelle] = vus.get(libelle, 0) + 1
        nom = f"{libelle} {vus[libelle]}" if vus[libelle] > 1 else libelle
        if email:
            await _partager(src["id"], email)
        try:
            ancien = next((f for f in existants if f.get("shortcutDetails", {}).get("targetId") == src["id"]), None)
            if ancien is not None and ancien.get("name") != nom:
                await google_api.drive_renommer(ancien["id"], nom)
            elif ancien is None:
                await google_api.drive_raccourci(nom, src["id"], dossier)
        except RuntimeError as erreur:
            journal.warning("Raccourci %s pour %s : %s", nom, prenom, erreur)
    # 27/09 : un ancien raccourci « Photos — Chloé » qui pointe vers un dossier qui n'est plus dans les sources (ids refaits le
    # 26/09) reste à côté du nouveau « Photos » : on le retire (le compte de service l'avait créé).
    cibles = {(src["id"] if isinstance(src, dict) else src) for src in sources}
    for f in existants:
        t = (f.get("shortcutDetails") or {}).get("targetId")
        if t and t not in cibles and " — " in (f.get("name") or ""):
            try:
                await google_api.drive_supprimer(f["id"])
            except RuntimeError as erreur:
                journal.warning("Ancien raccourci %s de %s : %s", f.get("name"), prenom, erreur)
    try:
        ancien_top = next((f for f in existants if f.get("mimeType") == google_api.DOSSIER_MIME
                           and f.get("name", "").strip().lower() == "reels uniques"), None)
        if ancien_top is not None:
            await google_api.drive_renommer(ancien_top["id"], NOM_TOP20)
        elif not await google_api.drive_trouver_dossier(NOM_TOP20, dossier):
            await google_api.drive_creer_dossier(NOM_TOP20, dossier)
    except RuntimeError as erreur:
        journal.warning("Dossier « %s » pour %s : %s", NOM_TOP20, prenom, erreur)
    if email:
        await _partager(dossier, email)
    journal.info("Drive de %s (%s) prêt : %s sources, e-mail %s", prenom, creatrice, len(sources), "oui" if email else "non")
    return google_api.drive_lien(dossier)


# ------------------------------------------------------------------ livraison
async def livrer(membre, creatrice: str, salon=None, declencheur: str = "!creatrice") -> str:
    """Tout l'onboarding d'un clipper. Renvoie la ligne à poster à l'admin / au manager."""
    prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
    etat = _lire_etat()
    fiche = etat["clippers"].setdefault(str(membre.id), {})
    resultat = []
    # 26/09 : `!salons-equipe` relancé = le même message de comptes deux fois dans chaque salon. Une livraison déjà faite
    # dans les 24 h n'est pas rejouée, sauf forçage explicite (`!onboarding @clipper`).
    if not declencheur.startswith("!onboarding") and fiche.get("comptes") and fiche.get("date"):
        try:
            depuis = datetime.now(timezone.utc) - datetime.fromisoformat(fiche["date"])
        except ValueError:
            depuis = timedelta(days=9)
        if depuis < timedelta(hours=24):
            return f"📦 Onboarding de {membre.display_name} ({fiche.get('creatrice') or creatrice}) : déjà livré il y a {int(depuis.total_seconds() // 3600)} h, rien renvoyé (`!onboarding @{prenom}` pour forcer)"
    # 1. comptes depuis le classeur
    comptes, tous = [], []
    if actif():
        try:
            tous = await lire_comptes()
            deja = [c for c in tous if _norm(c["gerant"]) == _norm(prenom) and _norm(c["utilisation"]) == "clipper"
                    and _pour_creatrice(c, creatrice)]
            if declencheur.startswith("!onboarding"):                # forçage explicite : on lève les écartés
                for c in deja:
                    etat.get("ecartes", {}).pop(c["handle"].lower(), None)
            elif _nouveau(membre, etat):                             # 24/09 : nouvel Eddy ≠ ancien Eddy viré
                douteux = _ecarter(etat, membre, deja)
                if douteux:
                    deja = [c for c in deja if c not in douteux]
                    resultat.append(f"⚠️ {len(douteux)} compte(s) déjà créé(s) au nom de {prenom} dans le classeur, NON livrés "
                                    f"(homonyme d'un ancien clipper ?) : {', '.join(c['handle'] for c in douteux)} — "
                                    f"`!liberer {prenom} <handles>` pour les rendre, `!onboarding @{prenom}` si ce sont bien les siens")
            comptes = deja[:COMPTES_PAR_CLIPPER]
            if len(comptes) < COMPTES_PAR_CLIPPER:
                nouveaux = disponibles(tous, creatrice, COMPTES_PAR_CLIPPER - len(comptes))
                if nouveaux:
                    await reserver(nouveaux, prenom)
                comptes += nouveaux
            resultat.append(f"{len(comptes)} compte(s)" + (" (aucun libre dans le classeur !)" if not comptes else ""))
        except RuntimeError as erreur:
            resultat.append(f"classeur : {erreur}")
    else:
        resultat.append("classeur non branché")
    # 2. lien GAML — cloné depuis le DERNIER lien de clipper de la créatrice (27/09 : « tu dupliques celui d'avant »), puis la carte
    # « Plateforme privée » reçoit le lien de tracking OnlyFans du POD du clipper (colonne « Lien Infloww Tracking » du classeur).
    lien, lid = "", ""
    try:
        d = paie_clics._lire() if paie_clics.actif() else {"liens": {}}
        lids = paie_clics.liens_de(d, str(membre.id))
        if lids:
            lid = lids[0]
            lien = d["liens"][lid].get("url", "")
        elif paie_clics.actif():
            liens = await paie_clics.liens_gaml()
            de_la_creatrice = [l for l in liens if _norm(str(l.get("name", "")).split()[0] if l.get("name") else "") == _norm(creatrice.split()[0])]
            modeles = [l for l in de_la_creatrice if paie_clics._prenom_note(l.get("note"))]
            modeles.sort(key=lambda l: str(l.get("createdAt") or ""), reverse=True)        # le plus récent d'abord
            if not modeles:                                              # 27/09 : première créatrice sans lien de clipper (Jade, Clara, Maddie) →
                modeles = [l for l in de_la_creatrice if "/fb" not in str(l.get("url", "")) and "/ytb" not in str(l.get("url", ""))]   # on part de son lien principal
            if modeles:
                nouveau = await paie_clics.cloner_lien(modeles[0]["id"], modeles[0].get("name", creatrice), f"Clipping {prenom}")
                d["liens"][nouveau["id"]] = {"uid": str(membre.id), "note": f"Clipping {prenom}", "url": nouveau["url"],
                                             "creatrice": creatrice.split()[0], "depuis": _deps["heure_paris"]().date().isoformat(),
                                             "par": "onboarding"}
                paie_clics._ecrire(d)
                lien, lid = nouveau["url"], nouveau["id"]
        resultat.append("lien GAML " + ("✅" if lien else "absent"))
        if lid and comptes:
            tracking, pod = tracking_du_pod(tous, comptes)
            if tracking:
                etat_tr = await paie_clics.poser_tracking(lid, tracking)
                d = paie_clics._lire()
                if lid in d.get("liens", {}):
                    d["liens"][lid]["tracking"] = tracking
                    paie_clics._ecrire(d)
                resultat.append("tracking OF " + ("✅" if etat_tr in ("ok", "déjà") else f"⚠️ {etat_tr}") + f" ({tracking.rsplit('/', 1)[-1]})")
            else:
                resultat.append(f"⚠️ pas de lien de tracking OnlyFans dans le classeur pour {'le POD ' + pod if pod else 'ses comptes'}")
    except RuntimeError as erreur:
        resultat.append(f"GAML : {erreur}")
    # 3. Drive
    drive, email = "", ""
    try:
        email = (_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("liaisons", {}).get(str(membre.id), {}).get("email", "")
                 or fiche.get("email", ""))
        drive = await dossier_drive(prenom, creatrice, email)
        resultat.append("Drive " + ("✅" + ("" if email else " (sans e-mail : rien partagé, `!onboarding` après son e-mail)") if drive
                                    else "non configuré"))
    except RuntimeError as erreur:
        resultat.append(f"Drive : {erreur}")
    # 4. message
    texte = (message_comptes_court(prenom) if (UN_PAR_JOUR and comptes and not declencheur.startswith("!onboarding"))
             else message_comptes(comptes, prenom, creatrice))
    if lien:
        texte += f"\n\n🔗 **Ton lien** : {lien} · tes visites : `!mesclics`"
    if drive:
        texte += (f"\n📁 **Ton Drive** (photos et vidéos de {creatrice.split()[0]}) : <{drive}>"
                  + ("" if email else " · envoie-moi ici **ton adresse Gmail** pour l'ouvrir"))
    if salon is not None and codes_2fa.actif():
        try:
            n_alias = codes_2fa.rattacher([c["mail"] for c in comptes if c.get("mail")], str(salon.id), "onboarding")
            if n_alias:
                resultat.append(f"{n_alias} alias 2FA rattaché(s)")                # 26/09 : plus de ligne dans le message, l'étape 1 dit `!code`
        except Exception as erreur:                                     # jamais bloquer la livraison
            journal.warning("Alias 2FA %s : %s", prenom, erreur)
    cible = salon if salon is not None else membre
    try:
        await cible.send(texte[:1990])
        if len(texte) > 1990:
            await cible.send(texte[1990:3980])
    except (discord.Forbidden, discord.HTTPException) as erreur:
        resultat.append(f"envoi impossible ({type(erreur).__name__})")
    for c in comptes:
        etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    fiche["acces"] = acces_ordonnes(comptes)                              # 27/09 : chaque étape du parcours donne l'accès du jour
    fiche.update({"creatrice": creatrice, "comptes": [c["handle"] for c in comptes], "lien": lien, "drive": drive, "email": email,
                  "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "par": declencheur})
    _ecrire_etat(etat)
    try:
        await liens_classeur()                                          # 27/09 : la colonne « Lien GAML associé » suit tout de suite
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Colonne Lien GAML après livraison : %s", erreur)
    return f"📦 Onboarding de {membre.display_name} ({creatrice}) : " + " · ".join(resultat)


RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


async def message_clipper(message) -> bool:
    """Un clipper qui poste son adresse e-mail dans son salon perso (ou en MP) alors que son Drive n'a pas encore
    été partagé : l'adresse va dans sa fiche et le partage part tout de suite (25/09 : Daniella, « sans e-mail :
    rien partagé », un bilan que seul l'admin voyait)."""
    if not actif() or getattr(message.author, "bot", False):
        return False
    m = RE_EMAIL.search(message.content or "")
    if not m:
        return False
    uid = str(message.author.id)
    etat = _lire_etat()
    fiche = etat["clippers"].get(uid)
    if not fiche or not fiche.get("creatrice"):
        return False
    if message.guild is not None:
        salon = _deps["salon_perso"](uid)
        if salon is None or salon.id != message.channel.id:
            return False
    email = m.group(0).strip().lower()
    if fiche.get("email") == email and fiche.get("drive"):
        return False
    fiche["email"] = email
    _ecrire_etat(etat)
    prenom = message.author.display_name.split()[0] if message.author.display_name.split() else message.author.display_name
    try:
        drive = await dossier_drive(prenom, fiche["creatrice"], email)
    except RuntimeError as erreur:
        await message.reply(f"J'ai noté ton adresse : {email}. Mais le partage du Drive n'a pas marché. Ton manager va le refaire.")
        return True
    if drive:
        fiche["drive"] = drive
        _ecrire_etat(etat)
        await message.reply(f"📁 C'est fait, le Drive est partagé avec {email} : {drive}\nOuvre-le avec ce compte Google. Tu reçois aussi un e-mail.")
    else:
        await message.reply(f"J'ai noté ton adresse : {email}. Le Drive de {fiche['creatrice']} n'est pas encore prêt. Ton manager s'en occupe.")
    return True


# ------------------------------------------------------------------ liens GAML dans le classeur
def _creatrice_du_lien(nom_lien: str, info: dict, url: str, creatrices) -> str:
    """La créatrice d'un lien GAML, en prénom normalisé : le premier mot de son nom GAML (« Chloé - Clipping Julien »), sinon
    celle mémorisée à l'attribution, sinon celle dont le prénom est dans le domaine (chloe-callista.fr, sophievan.fr, jadetora.fr)."""
    cands = {(_norm(x).split() or [""])[0] for x in creatrices if x} - {""}
    premier = (_norm(nom_lien or "").split() or [""])[0]
    if premier in cands:
        return premier
    memo = (_norm(str((info or {}).get("creatrice") or "")).split() or [""])[0]
    if memo in cands:
        return memo
    domaine = re.sub(r"[^a-z0-9]", "", _norm(re.sub(r"^https?://", "", url or "").split("/")[0]))
    for cr in sorted(cands, key=len, reverse=True):
        if cr in domaine:
            return cr
    return "" if cands else (premier or memo)


def _prenom_du_lien(info: dict) -> str:
    uid = str((info or {}).get("uid") or "")
    m = _deps["membre_par_id"](uid) if (uid and _deps.get("membre_par_id")) else None
    if m is not None and m.display_name.split():
        return m.display_name.split()[0]
    return paie_clics._prenom_note((info or {}).get("note"))


def _clipper_compte(prenom: str) -> bool:
    """27/09 (« on s'en fout de ceux qui sont virés ») : les vérifications ne parlent que des clippers du roster actif."""
    try:
        return (not roster.actif()) or roster.est_actif(prenom)
    except Exception:                                                   # noqa: BLE001
        return True


async def liens_classeur(comptes: list = None) -> dict:
    """27/09 (« c'est le bazar ») : la colonne « Lien GAML associé » de chaque ligne = LE lien du gérant pour la créatrice de la
    ligne (Julien : son lien Sophie sur ses lignes Sophie, son lien Chloé sur ses lignes Chloé, rien sur ses lignes Maddie) ;
    deux liens pour la même créatrice → le plus récent ; une cellule vidée quand aucun lien ne correspond. Écrit seulement ce
    qui change. Renvoie {"ecrits": n, "groupes": {(gérant, créatrice, lien): n}}."""
    vide = {"ecrits": 0, "groupes": {}}
    if not (actif() and paie_clics.actif()):
        return vide
    if comptes is None:
        comptes = await lire_comptes()
    d = paie_clics._lire()
    try:
        noms = {l["id"]: str(l.get("name") or "") for l in await paie_clics.liens_gaml() if l.get("id")}
    except RuntimeError as erreur:
        journal.warning("Liens GAML illisibles pour le classeur : %s", erreur)
        noms = {}
    creatrices = {c["creatrice"] for c in comptes if c.get("creatrice")}
    par_prenom = {}
    for lid, info in d.get("liens", {}).items():
        url = str(info.get("url") or "").strip()
        prenom = _prenom_du_lien(info)
        if not url or not prenom:
            continue
        cr = _creatrice_du_lien(noms.get(lid, ""), info, url, creatrices)
        par_prenom.setdefault(_norm(prenom), []).append((cr, url, str(info.get("depuis") or ""), str(lid)))
    ecrits, groupes = 0, {}
    for c in comptes:
        g = _norm(c["gerant"])
        if not c["handle"] or g in GERANTS_LIBRES or not a_colonne("lien_gaml", c.get("onglet", "")):
            continue
        cr = (_norm(c["creatrice"]).split() or [""])[0]
        liens = par_prenom.get(g, [])
        cands = [x for x in liens if x[0] == cr] or ([x for x in liens] if len(liens) == 1 and not liens[0][0] else [])
        voulu = max(cands, key=lambda x: (x[2], x[3]))[1] if cands else ""
        if voulu == str(c.get("lien_gaml") or "").strip():
            continue
        try:
            await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "lien_gaml"), [[voulu]])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Classeur : lien GAML de %s non écrit : %s", c["handle"], erreur)
            continue
        ecrits += 1
        cle = (c["gerant"], (c["creatrice"] or c.get("onglet") or "").split()[0] if (c["creatrice"] or c.get("onglet")) else "?", voulu)
        groupes[cle] = groupes.get(cle, 0) + 1
    if ecrits:
        journal.info("Classeur, colonne Lien GAML associé : %d cellule(s) corrigée(s)", ecrits)
    return {"ecrits": ecrits, "groupes": groupes}


def texte_liens(bilan: dict) -> str:
    """Une ligne pour le salon admin : « 🔗 Lien GAML associé : 12 cellules · Julien / Maddie vidé ×1 · Mie02 / Chloé → chloe-callista.fr/15 ×3 »."""
    if not bilan.get("ecrits"):
        return ""
    morceaux = []
    for (gerant, cr, lien), n in sorted(bilan["groupes"].items(), key=lambda kv: (-kv[1], kv[0])):
        cible = lien.split("//")[-1].rstrip("/") if lien else "vidé"
        morceaux.append(f"{gerant} / {cr} → {cible} ×{n}")
    return f"🔗 Lien GAML associé : {bilan['ecrits']} cellule(s) · " + " · ".join(morceaux[:8]) + (" · …" if len(morceaux) > 8 else "")


def bilan_a_poster(lignes: list, cle: str) -> bool:
    """Vrai s'il faut poster ce bilan au salon admin : il contient une action (🔧 ❌ 🔗) ou ses avertissements ont changé depuis
    le dernier bilan posté (27/09 : cinq bilans identiques dans l'après-midi, à chaque redémarrage)."""
    if not lignes:
        return False
    signature = "|".join(sorted(l for l in lignes if l.startswith("⚠️")))
    etat = _lire_etat()
    avant = etat.setdefault("bilans", {}).get(cle)
    action = any(l.startswith(("🔧", "❌", "🔗")) for l in lignes)
    if signature != avant:
        etat["bilans"][cle] = signature
        _ecrire_etat(etat)
    return action or signature != avant


# ------------------------------------------------------------------ le classeur comme télécommande
async def verifier_trackings() -> list:
    """27/09 : chaque clipper qui a un lien GAML et dont le POD porte un lien de tracking OnlyFans doit avoir CE lien dans la carte
    « Plateforme privée » de son lien. Corrige les écarts, signale les POD sans tracking et les liens sans carte. Renvoie les
    lignes du bilan (vide si tout est juste)."""
    if not (actif() and paie_clics.actif()):
        return []
    tous = await lire_comptes()
    d = paie_clics._lire()
    # Groupes (gérant, créatrice) : un clipper passé d'une créatrice à l'autre (Julien : lignes Chloé anciennes, lignes Sophie
    # neuves) a un lien par créatrice, chacun avec le tracking de SA créatrice.
    par_gerant = {}
    for c in tous:
        g = _norm(c.get("gerant") or "")
        cr = (_norm(c.get("creatrice") or "").split() or [""])[0]
        if g and _norm(c.get("utilisation") or "").startswith("clipper"):
            par_gerant.setdefault((g, cr), []).append(c)
    try:
        noms_liens = {l["id"]: str(l.get("name") or "") for l in await paie_clics.liens_gaml() if l.get("id")}
    except RuntimeError as erreur:
        journal.warning("Liens GAML illisibles pour la vérification : %s", erreur)
        noms_liens = {}
    creatrices = {c["creatrice"] for c in tous if c.get("creatrice")}
    liens_de_prenom = {}
    for lid, info in d.get("liens", {}).items():
        nom = _prenom_du_lien(info)
        if not nom:
            continue
        cr = _creatrice_du_lien(noms_liens.get(lid, ""), info, str(info.get("url") or ""), creatrices)
        liens_de_prenom.setdefault(_norm(nom), []).append((lid, cr))
    bilan, corriges = [], 0
    for (prenom_n, cr), comptes in par_gerant.items():
        if not _clipper_compte(comptes[0].get("gerant") or prenom_n):
            continue                                                    # parti ou staff : on n'en parle plus (27/09)
        candidats = liens_de_prenom.get(prenom_n) or []
        lids = [lid for lid, c_ in candidats if not cr or not c_ or c_ == cr] or []
        if candidats and not lids:
            continue                                                    # ses liens sont ceux d'une autre créatrice : rien à toucher ici
        tracking, pod = tracking_du_pod(tous, comptes)
        nom = comptes[0].get("gerant") or prenom_n
        if not lids:
            continue                                                    # pas de lien GAML connu : l'onboarding s'en charge
        if not tracking:
            bilan.append(f"⚠️ {nom} : pas de lien de tracking OnlyFans dans le classeur ({'POD ' + pod if pod else 'ses lignes'})")
            continue
        for lid in lids[:1]:
            try:
                etat_tr = await paie_clics.poser_tracking(lid, tracking)
            except RuntimeError as erreur:
                bilan.append(f"❌ {nom} : {erreur}")
                continue
            if etat_tr == "ok":
                corriges += 1
                bilan.append(f"🔧 {nom} : carte du lien → {tracking.rsplit('/', 1)[-1]}" + (f" (POD {pod})" if pod else ""))
            elif etat_tr != "déjà":
                bilan.append(f"⚠️ {nom} : {etat_tr}")
            if d.get("liens", {}).get(lid, {}).get("tracking") != tracking:
                d["liens"][lid]["tracking"] = tracking
                paie_clics._ecrire(d)
    journal.info("Trackings OnlyFans vérifiés : %d clipper(s), %d corrigé(s)", len(par_gerant), corriges)
    return bilan


async def boucle(client, deps: dict):
    """Toutes les 15 minutes : un compte dont la colonne Gérant porte le prénom d'un membre, et qui ne lui a
    pas encore été livré, part dans son salon perso. Attribuer ou changer un compte se fait donc dans le
    classeur, sans commande."""
    global _deps
    _deps = deps
    await client.wait_until_ready()
    if not actif():
        journal.info("Onboarding par classeur inactif (CLASSEUR_LOGINS_ID / compte de service absents)")
        return
    try:
        onglets = ", ".join(await onglets_logins()) or "aucun onglet reconnu"
    except Exception as erreur:                                     # noqa: BLE001
        onglets = f"onglets illisibles : {erreur}"
    journal.info("Onboarding par classeur actif (%s ; %s comptes par clipper)", onglets, COMPTES_PAR_CLIPPER)
    while not client.is_closed():
        try:
            etat = _lire_etat()
            comptes = await lire_comptes()
            # 27/09 : un clipper livré sans lien GAML (créatrice sans lien à cloner à ce moment-là, GAML injoignable) le reçoit
            # au tour suivant, sans `!onboarding` — trois par passage au plus.
            if paie_clics.actif():
                relances = 0
                for uid_r, fiche_r in list(etat.get("clippers", {}).items()):
                    if relances >= 3 or fiche_r.get("lien") or not fiche_r.get("creatrice") or not fiche_r.get("comptes"):
                        continue
                    m_r = _deps["membre_par_id"](uid_r) if _deps.get("membre_par_id") else None
                    if m_r is None:
                        continue
                    try:
                        bilan_l = await livrer(m_r, fiche_r["creatrice"], _deps["salon_perso"](uid_r) if _deps.get("salon_perso") else None,
                                               declencheur="!onboarding lien manquant")
                        relances += 1
                        journal.info("Lien GAML retenté pour %s : %s", uid_r, bilan_l[-160:])
                    except Exception as erreur:                             # noqa: BLE001
                        journal.warning("Lien GAML retenté pour %s : %s", uid_r, erreur)
                etat = _lire_etat()
            par_prenom = {}
            for c in comptes:
                g = _norm(c["gerant"])
                if g in GERANTS_LIBRES or _norm(c["utilisation"]) != "clipper" or not c["handle"]:
                    continue
                par_prenom.setdefault(g, []).append(c)
            for g, lignes in par_prenom.items():
                membre = deps["membre_par_prenom"](g)
                if membre is None:
                    continue
                nouveaux = [c for c in lignes if etat["livres"].get(c["handle"].lower(), {}).get("uid") != str(membre.id)
                            and not _ecarte_pour(etat, c, membre.id)]
                if not nouveaux:
                    continue
                prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
                creatrice = nouveaux[0]["creatrice"] or etat["clippers"].get(str(membre.id), {}).get("creatrice", "")
                if _nouveau(membre, etat):                          # 24/09 : un nouveau venu n'a pas de comptes déjà créés
                    douteux = _ecarter(etat, membre, nouveaux)
                    if douteux:
                        nouveaux = [c for c in nouveaux if c not in douteux]
                        _ecrire_etat(etat)
                        canal = await deps["canal_admin"]()
                        if canal:
                            handles = " ".join(c["handle"] for c in douteux)
                            await canal.send(
                                f"⚠️ **Homonyme possible** : le classeur porte « {prenom} » sur {len(douteux)} compte(s) déjà créé(s) "
                                f"({handles}) alors que {membre.mention} vient d'arriver et n'a encore reçu aucune créatrice. "
                                f"Ancien clipper du même prénom ? Rien livré. Si ce sont bien les siens : `!onboarding @{prenom} {creatrice}`. "
                                f"Sinon : `!liberer {prenom} {handles}` puis `!creatrice @{prenom} {creatrice}`."[:1990])
                    if not nouveaux:
                        continue
                salon = deps["salon_perso"](str(membre.id))
                cible = salon if salon is not None else membre
                try:
                    await cible.send(("🔐 **Compte(s) attribué(s) depuis le classeur**\n\n" +
                                      message_comptes(nouveaux, prenom, creatrice or "?"))[:1990])
                except (discord.Forbidden, discord.HTTPException) as erreur:
                    journal.warning("Livraison classeur %s : %s", membre.display_name, erreur)
                    continue
                for c in nouveaux:
                    etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                fiche = etat["clippers"].setdefault(str(membre.id), {})
                fiche["comptes"] = sorted(set(fiche.get("comptes", [])) | {c["handle"] for c in nouveaux})
                _ecrire_etat(etat)
                if creatrice and roster.actif() and not roster.est_actif(prenom):   # 27/09 : Georgial servi par le classeur, absent du roster
                    try:
                        roster.ajouter(creatrice.split()[0], prenom)
                    except Exception as erreur:                         # noqa: BLE001
                        journal.warning("Roster (télécommande) : %s", erreur)
                canal = await deps["canal_admin"]()
                if canal:
                    await canal.send(f"🔐 {len(nouveaux)} compte(s) du classeur livré(s) à {membre.mention} (colonne Gérant).")
        except Exception as erreur:                                 # la boucle ne meurt jamais
            journal.warning("Boucle onboarding : %s", erreur)
        try:
            await liens_classeur()                                      # 27/09 : Gérant changé à la main → lien GAML de la ligne à jour
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Colonne Lien GAML (boucle) : %s", erreur)
        await asyncio.sleep(900)


# ------------------------------------------------------------------ commande
async def liberer(prenom: str, handles=(), pool: bool = False) -> list:
    """Rend les comptes d'un clipper parti : colonne Gérant vidée sur ses lignes (toutes, ou seulement `handles`) ;
    les comptes déjà créés passent en Utilisation « à mettre Metricool » (ils sortent du pool des clippers), sauf
    `pool=True` ; ceux « à créer » restent au pool. Nettoie l'état du bot (livrés, écartés, fiches) et détache les
    alias 2FA. Renvoie une ligne de bilan par compte (sans mot de passe). C'est l'étape qui manquait quand un
    clipper est viré : sans elle, le prochain homonyme hérite de ses comptes (Eddy, 24/09)."""
    cibles = {_norm(h).lstrip("@") for h in handles if _norm(h)}
    comptes = await lire_comptes()
    lignes = [c for c in comptes if _norm(c["gerant"]) == _norm(prenom) and (not cibles or _norm(c["handle"]) in cibles)]
    if not lignes:
        return []
    etat = _lire_etat()
    bilan = []
    for c in lignes:
        await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "gerant"), [[""]])
        metricool = _norm(c["etat"]) not in A_CREER and not pool
        if metricool:
            await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "utilisation"), [[MENTION_LIBERE]])
        h = c["handle"].lower()
        etat["livres"].pop(h, None)
        etat.get("ecartes", {}).pop(h, None)
        for fiche in etat["clippers"].values():
            if c["handle"] in fiche.get("comptes", []):
                fiche["comptes"] = [x for x in fiche["comptes"] if x != c["handle"]]
        bilan.append(f"· `{c['handle']}` ({c['etat'] or 'état ?'}) → " + (MENTION_LIBERE if metricool else "retour au pool des clippers"))
    _ecrire_etat(etat)
    if codes_2fa.actif():
        n_alias = codes_2fa.detacher([c["mail"] for c in lignes if c.get("mail")])
        if n_alias:
            bilan.append(f"-# {n_alias} alias 2FA détaché(s).")
    return bilan


async def commande_staff(message, texte: str) -> bool:
    """`!comptes-libres [Créatrice]` : ce que le classeur a de disponible ; `!onboarding @clipper` : rejouer la livraison ;
    `!liberer Prénom [handle …] [pool]` : rendre les comptes d'un clipper parti."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!comptes-libres", "!onboarding", "!liberer", "!libérer"):
        return False
    if not actif():
        await message.reply("Onboarding par classeur inactif : `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
        return True
    if mots[0].lower() == "!comptes-libres":
        try:
            comptes = await lire_comptes()
        except RuntimeError as erreur:
            await message.reply(f"❌ {erreur}")
            return True
        cible = " ".join(mots[1:]).strip()
        libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
                  and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and (not cible or _pour_creatrice(c, cible))]
        par_c = {}
        for c in libres:
            par_c.setdefault(c["creatrice"] or "?", []).append(c)
        lignes = [f"🗂️ **Comptes libres dans le classeur** ({len(libres)})"]
        for cr, lst in sorted(par_c.items()):
            crees = sum(1 for c in lst if _norm(c["etat"]) not in A_CREER)
            a_creer = [c for c in lst if _norm(c["etat"]) in A_CREER]
            avec_mail = sum(1 for c in a_creer if c.get("mail"))
            livrables = crees + avec_mail
            lignes.append(f"· {cr} — {len(lst)} libre(s) : {crees} créé(s), {len(a_creer)} à créer dont **{avec_mail} avec e-mail** "
                          f"→ {livrables} livrable(s) = {livrables // 3} clipper(s)"
                          + (" ⚠️ ajoute des e-mails (iCloud « Masquer mon adresse ») avant le prochain clipper" if livrables < 3 else ""))
        lignes.append("-# Un compte est « libre » quand Utilisation = Clipper, Gérant vide ou x/y/z, état à créer / GOOD / WARMUP / PRIVÉ / ACTIF. "
                      "Un compte à créer sans e-mail n'est pas livré (25/09) : impossible à créer sur Instagram ni à relayer en 2FA.")
        lignes.append(f"-# Onglets lus : {', '.join(await onglets_logins()) or 'aucun'}.")
        await message.reply("\n".join(lignes)[:1990])
        return True
    if mots[0].lower() in ("!liberer", "!libérer"):
        args = [m for m in mots[1:] if m.lower() != "pool"]
        if not args:
            await message.reply("Format : `!liberer Prénom [handle …] [pool]` — vide la colonne Gérant des comptes de ce clipper "
                                "(tous, ou seulement les handles cités). Les comptes déjà créés passent en « à mettre Metricool » ; "
                                "avec `pool`, ils restent disponibles pour le prochain clipper.")
            return True
        prenom = args[0].lstrip("@")
        try:
            bilan = await liberer(prenom, args[1:], pool=any(m.lower() == "pool" for m in mots[1:]))
        except RuntimeError as erreur:
            await message.reply(f"❌ {erreur}")
            return True
        if not bilan:
            await message.reply(f"Aucune ligne du classeur avec Gérant « {prenom} »" + (" pour ces handles." if args[1:] else "."))
            return True
        n = sum(1 for b in bilan if b.startswith("·"))
        await message.reply((f"🔓 **{n} compte(s) libéré(s)** — Gérant « {prenom} » effacé dans le classeur\n" + "\n".join(bilan)
                             + "\n-# Lien GAML, salon perso et rôles non touchés (`!sortie` pour ça).")[:1990])
        return True
    if not message.mentions:
        await message.reply("Format : `!onboarding @clipper` — renvoie ses comptes, son lien et son Drive dans son salon perso.")
        return True
    membre = message.mentions[0]
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    creatrice = " ".join(m for m in mots[1:] if not m.startswith("<@")).strip() or registre.get(str(membre.id), {}).get("creatrice", "")
    if not creatrice:
        await message.reply("Pas de créatrice connue : `!onboarding @clipper Chloé` ou d'abord `!creatrice @clipper Chloé`.")
        return True
    bilan = await livrer(membre, creatrice, _deps["salon_perso"](str(membre.id)), declencheur=f"!onboarding par {message.author.id}")
    await message.reply(bilan[:1990])
    return True
