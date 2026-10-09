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
import reserve_mym
import roster

journal = logging.getLogger("onboarding")

CLASSEUR_LOGINS_ID = os.environ.get("CLASSEUR_LOGINS_ID", "").strip()
ONGLET_LOGINS = os.environ.get("ONGLET_LOGINS", "").strip()             # 27/09 : vide ou « auto » = un onglet par créatrice, découverts
ONGLETS_EXCLUS = os.environ.get("ONGLETS_EXCLUS", "Gaetan, Gaëtan, Tracking, Backup, Candidatures, Modèle, Template, Archive, Dashboard, Build capacity")
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
                 ("followers", ("followers", "abonnes")), ("reels_hier", ("reels hier", "reels d'hier")),   # 30/09
                 ("reels_7j", ("reels 7",)),                                                      # 05/10 : « Reels 7 j »
                 ("clics_hier", ("clics hier", "clics d'hier", "visites hier")),   # 05/10 : AVANT « clics » (plus précis, sinon « clics » la prendrait)
                 ("clics", ("clics", "gaml last", "visites")), ("numero", ("numero",)),
                 ("mail", ("mail", "email")), ("phone", ("phone", "tel")), ("gerant", ("gerant", "clipper")),
                 ("utilisation", ("utilisation", "usage")), ("creatrice", ("creatrice",)), ("pod", ("pod",)),
                 ("lien_gaml", ("lien gaml", "gaml associe")), ("lien_infloww", ("infloww", "lien onlyfans", "onlyfans track")),
                 ("lien_mym", ("lien mym", "mym track")))                       # 29/09 : jamais « Clics vers MYM » (tableau du mois)
_colonnes = dict(COL_DEFAUT)
_colonnes_lues_par_onglet = {}      # 05/10 : les colonnes RÉELLEMENT présentes dans l'en-tête de chaque onglet (sans position par défaut)
_colonnes_journalisees = {}


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
    """L'onglet a-t-il cette colonne (clics, lien_gaml… ne sont écrits que si l'en-tête les porte) ? 05/10 : d'après l'en-tête
    RÉEL de l'onglet (une colonne absente de l'en-tête n'existe pas, même si COL_DEFAUT lui donne une position : Followers écrit
    en colonne D d'un onglet sans Followers, c'était possible avant)."""
    lues = _colonnes_lues_par_onglet.get(onglet)
    if lues is not None:
        return champ in lues
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


_RE_URL_IG = re.compile(r"^(?:https?://)?(?:www\.)?(?:instagram\.com|instagr\.am)/", re.I)
_INVISIBLES = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00a0"), None)


def normaliser_handle(brut) -> str:
    """05/10 : l'identifiant Instagram tel qu'Apify le comprend, à partir de ce qui est écrit dans la cellule « @ IG » : sans
    espace invisible ni espace autour, sans URL (https://www.instagram.com/x/ → x), sans « @ », sans « / » ni paramètre, premier
    mot seulement (« x (perso) » → x), sans ponctuation finale. La casse est gardée (Instagram l'ignore ; les clés du scan passent
    en minuscules). Avant, un « @ » restait retiré mais une URL ou un espace interne partait tel quel chez Apify : « introuvable »."""
    t = str(brut or "").translate(_INVISIBLES).strip()
    if not t:
        return ""
    t = _RE_URL_IG.sub("", t)
    t = t.split("?")[0].split("#")[0].strip().strip("/")
    t = t.split("/")[0] if t else t
    t = t.strip().lstrip("@").strip()
    t = (t.split() or [""])[0]
    return t.rstrip(".,;:")


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
        # 05/10 : on LIT seulement les colonnes présentes dans l'en-tête. Avant, un champ absent de l'en-tête (Utilisation,
        # Créatrice, Numéro) était lu à sa position historique de COL_DEFAUT : depuis l'insertion de « Reels Hier » le 30/09, cette
        # position pointe sur une autre colonne (7 = Gérant), et « Caroline » lu comme Utilisation sortait la ligne du scan.
        trouve = _colonnes_trouvees(lignes[0])
        lues = trouve if all(k in trouve for k in ("etat", "handle", "gerant")) else cols
        _colonnes_lues_par_onglet[titre] = lues
        if _colonnes_journalisees.get(titre) != sorted(lues):               # une ligne de journal par onglet quand l'en-tête change
            _colonnes_journalisees[titre] = sorted(lues)
            journal.info("Classeur %s : colonnes reconnues → %s", titre, ", ".join(sorted(lues)))
        if titre == titres[0]:
            _colonnes = cols
        herite = _norm(titre).strip() in ONGLETS_HERITES
        for i, l in enumerate(lignes[1:], start=2):
            l = (l + [""] * 26)[:26]
            def champ(nom):
                return l[lues[nom]].strip() if nom in lues and lues[nom] < len(l) else ""
            brut = champ("handle")
            out.append({"onglet": titre, "ligne": i, "etat": champ("etat"), "handle": normaliser_handle(brut), "handle_brut": brut, "mdp": champ("mdp"),
                        "followers": champ("followers"), "clics": champ("clics"), "mail": champ("mail"), "phone": champ("phone"),
                        "gerant": champ("gerant"), "utilisation": champ("utilisation"), "numero": champ("numero"),
                        "creatrice": champ("creatrice") or ("" if herite else titre), "lien_gaml": champ("lien_gaml"),
                        "pod": champ("pod"), "lien_infloww": champ("lien_infloww"), "lien_mym": champ("lien_mym"),
                        "reels_hier": champ("reels_hier"), "reels_7j": champ("reels_7j"), "clics_hier": champ("clics_hier")})   # 05/10
    await _remplir_fusions(out, titres)
    return _sans_doublons(out)


CHAMPS_FUSIONNES = ("gerant", "clics", "clics_hier", "lien_gaml", "lien_infloww", "lien_mym", "pod")   # 05/10 : + Clics hier


def creatrices_connues(comptes: list) -> set:
    """05/10 : les prénoms (normalisés, premier mot) des créatrices du classeur : titres des onglets et colonne Créatrice."""
    noms = set()
    for c in comptes or []:
        for x in (c.get("onglet"), c.get("creatrice")):
            mots = _norm(x or "").split()
            if mots and mots[0] not in ONGLETS_HERITES:
                noms.add(mots[0])
    return noms


def est_creatrice(gerant: str, creatrices: set) -> bool:
    """05/10 (Gaëtan : « le lien GAML de la ligne de la créatrice est effacé à chaque passage ») : la ligne dont le Gérant est une
    créatrice (son compte principal, Gérant = « Chloé ») n'est pas celle d'un clipper : le bot ne touche jamais à ses liens."""
    return (_norm(gerant or "").split() or [""])[0] in (creatrices or set())


def est_ligne_creatrice(c: dict, creatrices: set) -> bool:
    """05/10 (Gaëtan : « scrape les infos des comptes des créas, leurs Reels, leurs clics ») : la ligne du compte principal d'une
    créatrice = Gérant à son prénom (Chloé, Jade) ou Utilisation « Compte de la créatrice ». Pas « Compte redirection créatrice »
    (le compte privé de redirection, Gérant Gaëtan : un compte géré comme les autres)."""
    u = _norm(c.get("utilisation") or "").strip()
    return est_creatrice(c.get("gerant"), creatrices) or u == "creatrice" or u.startswith("compte de la creatrice")


def _compact(t) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(str(t or "")))


def lignes_creatrice(comptes: list, c: dict, creatrices: set = None) -> int:
    """09/10 (dashboard) : le nombre de lignes de compte de la créatrice de `c` (Gérant à son prénom ou « Compte de la créatrice »)."""
    creatrices = creatrices if creatrices is not None else creatrices_connues(comptes)
    cle = (_norm(c.get("creatrice") or c.get("onglet") or "").split() or [""])[0]
    return sum(1 for x in comptes or [] if x.get("handle") and est_ligne_creatrice(x, creatrices)
               and (_norm(x.get("creatrice") or x.get("onglet") or "").split() or [""])[0] == cle)


def lien_gaml_creatrice(c: dict, details: list, seule: bool = True):
    """05/10 : le lien GAML du compte principal d'une créatrice = celui dont la note GAML dit « Compte de @<identifiant> ».
    L'identifiant de la note et celui du classeur ne s'écrivent pas toujours pareil (« prenom_nom » dans la note, « prenom.nom__ » dans le classeur) : comparés
    sans ponctuation. À défaut, l'unique note « Compte de @… » qui commence par le prénom de la créatrice. Rien de sûr → None.
    09/10 (dashboard) : ce repli seulement si la créatrice n'a qu'UNE ligne de compte (`seule`) : son deuxième compte recevait le
    lien du compte principal (la seule note qui commence par son prénom), et ses clics passaient pour ceux du principal."""
    handle = _compact(normaliser_handle(c.get("handle")))
    prenom = _compact((_norm(c.get("creatrice") or c.get("onglet") or "").split() or [""])[0])
    notes = []
    for d in details or []:
        m = re.match(r"\s*compte\s+de\s+@?\s*(\S+)", _norm(str(d.get("note") or "")))
        if m and str(d.get("url") or "").strip():
            notes.append((_compact(m.group(1)), d))
    exact = [d for h, d in notes if handle and h == handle]
    if exact:
        return exact[0]
    par_prenom = [d for h, d in notes if prenom and h.startswith(prenom)]
    return par_prenom[0] if len(par_prenom) == 1 and seule else None


async def _remplir_fusions(lignes: list, titres: list) -> None:
    """30/09 (Gaëtan : Gérant, Clics et liens fusionnés par clipper) : dans une fusion l'API ne rend la valeur que dans la
    première cellule ; chaque ligne du bloc la reçoit, et note l'étendue du bloc (« fusions » : {champ: (1re ligne, dernière)})
    pour que les écritures visent la bonne cellule. Sans l'API des fusions, rien ne change."""
    try:
        fusions = await google_api.sheets_fusions(CLASSEUR_LOGINS_ID)
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Fusions du classeur illisibles : %s", erreur)
        return
    par_cle = {(c["onglet"], c["ligne"]): c for c in lignes}
    for titre in titres:
        cols = _colonnes_par_onglet.get(titre) or {}
        champ_de = {i: ch for ch, i in cols.items() if ch in CHAMPS_FUSIONNES}
        for r0, r1, c0, c1 in fusions.get(titre, []):
            if c1 - c0 != 1 or r1 - r0 < 2 or c0 not in champ_de or r0 < 1:
                continue
            champ = champ_de[c0]
            haut = par_cle.get((titre, r0 + 1))
            if haut is None:
                continue
            for ligne in range(r0 + 1, r1 + 1):
                c = par_cle.get((titre, ligne))
                if c is None:
                    continue
                if ligne > r0 + 1 and not str(c.get(champ) or "").strip():
                    c[champ] = haut.get(champ, "")
                c.setdefault("fusions", {})[champ] = (r0 + 1, r1)


STRUCTURE_LOGINS = 2                                                # 05/10 : + « Reels 7 j » après Reels Hier, « Clics hier » après Clics


async def _inserer_colonne(sid: int, titre: str, index: int, nom: str) -> list:
    """Insère une colonne vide à `index` (format hérité de la colonne de gauche), écrit son en-tête, renvoie l'en-tête relu.
    Les cellules fusionnées et les tableaux Google suivent le décalage tout seuls (Sheets déplace, n'efface rien)."""
    await google_api.sheets_batch_update(CLASSEUR_LOGINS_ID, [{"insertDimension": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": index, "endIndex": index + 1}, "inheritFromBefore": True}}])
    await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{onglet_a1(titre)}!{google_api.colonne(index)}1", [[nom]])
    return ((await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{onglet_a1(titre)}!A1:Z1")) or [[]])[0]


async def structurer_onglets() -> list:
    """30/09 (Gaëtan, onglet Sarah en exemple : « ajoute une colonne Reels Hier ; déplace Clics last 7d à droite de son gérant,
    on a un lien par clipper ») : dans chaque onglet de logins, une colonne « Reels Hier » juste après Followers (remplie par
    le scan du matin), et « Clics last 7d. » juste à droite de Gérant. 05/10 (Gaëtan : « Reels 7 derniers jours, Clics hier ») :
    « Reels 7 j » juste après Reels Hier, « Clics hier » juste après Clics last 7d. Une fois par version (état « structure_logins »),
    et sans rien toucher à un onglet déjà rangé. Les colonnes se retrouvent par leur en-tête : le reste du bot suit."""
    if not actif():
        return []
    etat = _lire_etat()
    if etat.get("structure_logins") == STRUCTURE_LOGINS:
        return []
    props = await google_api.sheets_proprietes(CLASSEUR_LOGINS_ID)
    faits = []
    for titre in await onglets_logins(forcer=True):
        sid = (props.get(titre) or {}).get("id")
        if sid is None:
            continue
        try:
            entete = ((await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{onglet_a1(titre)}!A1:Z1")) or [[]])[0]
            cols = _colonnes_trouvees(entete)
            if "reels_hier" not in cols and "followers" in cols:
                entete = await _inserer_colonne(sid, titre, cols["followers"] + 1, "Reels Hier")
                cols = _colonnes_trouvees(entete)
                faits.append(f"{titre} : Reels Hier ajoutée")
            if "reels_7j" not in cols and "reels_hier" in cols:          # 05/10
                entete = await _inserer_colonne(sid, titre, cols["reels_hier"] + 1, "Reels 7 j")
                cols = _colonnes_trouvees(entete)
                faits.append(f"{titre} : Reels 7 j ajoutée")
            if "clics" in cols and "gerant" in cols and cols["clics"] != cols["gerant"] + 1:
                await google_api.sheets_batch_update(CLASSEUR_LOGINS_ID, [{"moveDimension": {
                    "source": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": cols["clics"], "endIndex": cols["clics"] + 1},
                    "destinationIndex": cols["gerant"] + 1}}])
                faits.append(f"{titre} : Clics à droite du Gérant")
                entete = ((await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{onglet_a1(titre)}!A1:Z1")) or [[]])[0]
                cols = _colonnes_trouvees(entete)
            if "clics_hier" not in cols and "clics" in cols:             # 05/10
                entete = await _inserer_colonne(sid, titre, cols["clics"] + 1, "Clics hier")
                cols = _colonnes_trouvees(entete)
                faits.append(f"{titre} : Clics hier ajoutée")
        except Exception as erreur:                                     # noqa: BLE001 — un onglet raté n'arrête pas les autres
            journal.warning("Structure de l'onglet %s : %s", titre, erreur)
            faits.append(f"{titre} : ⚠️ {erreur}")
    etat = _lire_etat()
    etat["structure_logins"] = STRUCTURE_LOGINS
    _ecrire_etat(etat)
    _onglets_cache["quand"] = 0                                         # relire les en-têtes au prochain passage
    journal.info("Structure des logins : %s", " · ".join(faits) or "déjà en place")
    return faits


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
        for c in cs:                                                    # 09/10 (dashboard) : la ligne gardée dit où étaient les
            if c["onglet"] == garde:                                    # autres, pour que le contrôle (C11) le signale
                c["doublons_ecartes"] = sorted([x["onglet"], x["ligne"]] for x in cs if x["onglet"] != garde)
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


def _cles_infos(c: dict) -> dict:
    """Les infos d'un compte qu'Instagram relie entre elles : identifiant, mot de passe, e-mail, téléphone (normalisés)."""
    tel = re.sub(r"\D", "", str(c.get("phone") or ""))
    mdp = str(c.get("mdp") or "").strip()
    return {"identifiant": str(c.get("handle") or "").strip().lower().lstrip("@"),
            "mot de passe": mdp if len(mdp) >= 4 else "",
            "e-mail": str(c.get("mail") or "").strip().lower(),
            "téléphone": tel[-9:] if len(tel) >= 6 else ""}                  # +33 6… et 06… : les 9 derniers chiffres


def infos_brulees(comptes: list) -> dict:
    """30/09 (Gaëtan : « ON NE RÉUTILISE JAMAIS LES INFOS D'UN COMPTE BAN, on change mdp, username, mail, téléphone ») :
    {info: {valeurs}} de toutes les lignes BAN, tous onglets confondus."""
    out = {}
    for c in comptes:
        if _norm(c.get("etat") or "") == "ban":
            for k, v in _cles_infos(c).items():
                if v:
                    out.setdefault(k, set()).add(v)
    return out


def infos_d_un_ban(c: dict, brulees: dict) -> list:
    """Les infos de cette ligne (non BAN) déjà portées par un compte BAN : [] si elle est propre."""
    if _norm(c.get("etat") or "") == "ban":
        return []
    return [k for k, v in _cles_infos(c).items() if v and v in brulees.get(k, ())]


def disponibles(comptes: list, creatrice: str, n: int) -> list:
    """Lignes libres pour cette créatrice : Utilisation = Clipper, Gérant libre, état utilisable, handle présent.
    Les comptes déjà créés (GOOD, WARMUP, PRIVÉ, ACTIF) passent avant ceux « à créer ». Le trio livré fait
    n-1 comptes de croissance + 1 compte privé quand le classeur en a un (24/09 : avant, le « privé » annoncé
    était juste le dernier de la liste)."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)
              and (c.get("mail") or _norm(c["etat"]) not in A_CREER)]        # 25/09 : un compte à créer sans e-mail est inutilisable
    brulees = infos_brulees(comptes)                                    # 30/09 : jamais un compte qui partage une info d'un BAN
    libres = [c for c in libres if not infos_d_un_ban(c, brulees)]
    # 28/09 (Gaëtan, sortie automatique) : « réattribue comptes et liens au suivant » — les comptes déjà créés et rendus
    # (chauffés, Gérant vidé) partent en premier ; le clipper s'y CONNECTE, le code de connexion arrive dans son salon.
    rendus = sorted([c for c in libres if _norm(c["etat"]) not in A_CREER], key=lambda c: c["ligne"])
    if rendus:
        choix = rendus[:n]
        if len(choix) < n:
            choix += disponibles([c for c in comptes if c not in rendus], creatrice, n - len(choix))
        return choix
    # 26/09 (Gaëtan) : « un nouveau = 3 nouveaux comptes et mails, dans les nouveaux PODs ». Le POD le plus bas où la
    # créatrice a n lignes « à créer » libres avec e-mail gagne.
    neufs = [c for c in libres if _norm(c["etat"]) in A_CREER and c.get("mail")]
    pods = {}
    for c in neufs:
        if str(c.get("pod") or "").strip():
            pods.setdefault(str(c["pod"]).strip(), []).append(c)
    for pod in sorted(pods, key=lambda p: (not p.isdigit(), int(p) if p.isdigit() else p)):
        if len(pods[pod]) >= n:
            return sorted(pods[pod], key=lambda c: c["ligne"])[:n]
    libres.sort(key=lambda c: (_norm(c["etat"]) not in A_CREER, not c.get("mail"), c["ligne"]))
    return libres[:n]                                               # 28/09 (Gaëtan) : 3 comptes de croissance, plus de compte privé


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


RE_HANDLE_IG = re.compile(r"^[a-z0-9._]{1,30}$")


async def renommer_compte(uid: str, ancien: str, nouveau: str) -> str:
    """08/10 (Mohamed : « le nom d'utilisateur que vous m'avez proposé est indisponible » ; l'audit : le blocage le plus courant à la
    création) : l'identifiant prévu était pris, le clipper a créé une variante. La cellule « @ IG » de la ligne du classeur, sa fiche
    d'onboarding (comptes, accès) et l'état des livraisons passent au nouvel identifiant : le scan, le parcours et l'app le suivent.
    Le compte doit être à lui (dans sa fiche). Renvoie '' si c'est fait, sinon la raison, en mots simples."""
    nouveau_n = normaliser_handle(nouveau).lower()
    ancien_n = normaliser_handle(ancien).lower()
    if not RE_HANDLE_IG.match(nouveau_n):
        return "cet identifiant n'est pas valable : lettres, chiffres, point et tiret bas, 30 caractères au plus"
    if nouveau_n == ancien_n:
        return "c'est déjà cet identifiant"
    if not actif():
        return "le classeur est indisponible"
    fiche = (_lire_etat()["clippers"].get(str(uid)) or {})
    if ancien_n not in {normaliser_handle(h).lower() for h in fiche.get("comptes", [])}:
        return "ce compte n'est pas dans tes comptes"
    tous = await lire_comptes()
    if any(normaliser_handle(c["handle"]).lower() == nouveau_n for c in tous):
        return "cet identifiant est déjà dans le classeur de l'agence"
    ligne = next((c for c in tous if normaliser_handle(c["handle"]).lower() == ancien_n), None)
    if ligne is None:
        return "je ne trouve pas ce compte dans le classeur"
    await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(ligne, "handle"), [[nouveau_n]])
    etat = _lire_etat()
    fiche = etat["clippers"].setdefault(str(uid), {})
    fiche["comptes"] = [nouveau_n if normaliser_handle(h).lower() == ancien_n else h for h in fiche.get("comptes", [])]
    for a in fiche.get("acces") or []:
        if isinstance(a, dict) and normaliser_handle(a.get("handle")).lower() == ancien_n:
            a["handle"] = nouveau_n
    livres = etat.setdefault("livres", {})
    for cle in [k for k in livres if normaliser_handle(k).lower() == ancien_n]:
        livres[nouveau_n] = livres.pop(cle)
    fiche.setdefault("renommes", []).append({"ancien": ancien_n, "nouveau": nouveau_n,
                                             "date": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    _ecrire_etat(etat)
    try:                                                                # 09/10 (dashboard) : la série du compte (followers, Reels, vues) suit
        import series
        series.renommer(ancien_n, nouveau_n)
    except Exception as erreur:                                         # noqa: BLE001 — le renommage reste fait
        journal.warning("Séries : renommage non suivi (%s)", type(erreur).__name__)
    journal.info("Compte renommé pour %s : %s → %s (%s, ligne %s)", uid, ancien_n, nouveau_n, ligne.get("onglet"), ligne.get("ligne"))
    return ""


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
    return [{"handle": c.get("handle", ""), "mdp": c.get("mdp", ""), "mail": c.get("mail", ""), "prive": bool(_est_prive(c)),
             "cree": _norm(c.get("etat", "")) not in A_CREER}                # 28/09 : compte rendu par un sortant → connexion, pas inscription
            for c in ordonnes]


def message_comptes_court(prenom: str) -> str:
    """27/09 (Gaëtan : « donne les comptes 24 h par 24 h, pas un message énorme dès le début ») : une ligne. Chaque accès
    (identifiant, mot de passe, e-mail) arrive dans l'étape du parcours qui le sert."""
    import parcours                                                     # 01/10 : la règle canonique, une seule source (import tardif : parcours importe onboarding)
    return (f"🔐 {prenom}, tes accès arrivent ici, dans l'étape du parcours.\n\n{parcours.regle_comptes()}\n\n"
            "Tes accès sont à l'agence : tu ne les donnes à personne.")      # 01/10 (relecture) : « Ils » n'avait plus de référent


def message_comptes(comptes: list, prenom: str, creatrice: str, debut: int = 1) -> str:
    """26/09 (Gaëtan : « hyper long, trop d'informations ») : les 3 comptes et une ligne de règle, rien d'autre.
    Depuis le 27/09, ne sert plus qu'à `!onboarding` forcé (COMPTES_UN_PAR_JOUR=0 pour le rétablir partout). 01/10 : `debut`
    = le numéro du premier compte (sa place dans la fiche : un compte ajouté après les deux premiers est le compte 3)."""
    if not comptes:
        return (f"⚠️ Il n'y a pas encore de compte prêt pour {creatrice}. Ton manager en prépare. "
                "Je te les envoie ici dès qu'ils sont prêts.")
    blocs = []
    for i, c in enumerate(comptes, start=debut):                    # 28/09 : trois comptes qui publient, plus de compte privé
        deja = "" if _norm(c["etat"]) in A_CREER else " · déjà créé, connecte-toi"
        # 28/09 (Gaëtan, Simon perdu) : identifiant, mot de passe, e-mail chacun dans son bloc, copiable d'un geste sur le téléphone
        # 08/10 (audit de l'assistant : « Compte 3 · il publie » pour le compte privé des anciens) : le privé est dit privé
        role = "privé, il ne publie pas, ton lien va dans sa bio" if _est_prive(c) else "il publie"
        blocs.append(f"**Compte {i}** · {role}{deja}\nIdentifiant :\n```\n{c['handle']}\n```\n"
                     f"Mot de passe :\n```\n{c['mdp'] or 'demande-le à ton manager'}\n```"
                     + (f"\nE-mail :\n```\n{c['mail']}\n```" if c["mail"] else "")
                     + (f"\nTéléphone : `{c['phone']}`" if c["phone"] else ""))
    # 01/10 (relecture) : ce message livre déjà les comptes — « le suivant arrive tout seul ici » y était faux (plusieurs
    # comptes sous les yeux, ou un remplaçant livré à l'étape 7 qui n'aura pas de suivant). Plus de règle recollée ici.
    import parcours                                                     # 01/10 : les deux conditions de la règle (import tardif)
    consigne = (f"Crée-les un par un : le suivant au plus tôt {parcours.ATTENTE_COMPTE_H} h après le précédent, et seulement "
                f"quand {parcours.REELS_OUVERTURE} Reels sont publiés sur ton dernier compte qui publie.\n\nSur ton téléphone seulement."
                if len(comptes) > 1 else "Sur ton téléphone seulement.")
    return (f"🔐 **Tes comptes Instagram, {prenom}** · créatrice : {creatrice} · chaque bloc se copie d'un geste.\n\n" + "\n\n".join(blocs) + "\n\n"
            f"{consigne}\n\n"
            "Ces accès sont à l'agence : tu ne les donnes à personne.")


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


_sources_publiques = set()


async def ouvrir_sources_par_lien() -> int:
    """30/09 (Ricardo : « pour télécharger la photo il faut une autorisation ») : depuis le 28/09 le dossier du clipper se lit
    par le lien, sans e-mail — mais Photos et Reels y sont des RACCOURCIS vers les dossiers sources de la créatrice, qui
    n'étaient partagés qu'à l'e-mail du clipper. Sans e-mail : le TOP 20 (vrai sous-dossier) s'ouvrait, Photos et Reels
    répondaient « Vous devez disposer d'une autorisation ». Chaque source passe en lecture par le lien, une fois par
    démarrage (puis à chaque nouveau Drive). Renvoie le nombre de sources ouvertes."""
    if not google_api.actif():
        return 0
    n = 0
    for cfg in _sources().values():
        for src in (cfg or {}).get("sources", []):
            sid = src.get("id") if isinstance(src, dict) else src
            if sid and sid not in _sources_publiques and await google_api.drive_partager_public(sid):
                _sources_publiques.add(sid)
                n += 1
    journal.info("Sources Drive ouvertes par le lien : %d", n)
    return n


def _source_de(creatrice: str) -> dict:
    """L'entrée DRIVE_SOURCES d'une créatrice, sans casse ni accent (28/09 : « sarah » dans la fiche de Simon ne trouvait pas « Sarah »)."""
    cible = _norm((creatrice or "").split()[0] if (creatrice or "").split() else "")
    if not cible:
        return {}
    for nom, cfg in _sources().items():
        if _norm(str(nom).split()[0] if str(nom).split() else "") == cible:
            return cfg or {}
    return {}


def texte_drive(prenom: str, creatrice: str, drive: str) -> str:
    """Le message du Drive, seul (rattrapage) : 28/09 (Gaëtan, Simon) « envoie-lui le lien de son Drive ».
    01/10 (Daniella a cru qu'on publiait sans monter, l'ancien titre parlant de Reels « à publier ») : « Tes vidéos à monter »,
    règle du 30/09 : chaque vidéo se modifie avant d'être publiée, TOP 20 compris."""
    return (f"📁 **Tes vidéos à monter, {prenom}** (TOP 20 de {creatrice.split()[0] if creatrice.split() else creatrice}) : <{drive}>\n\n"
            "Modifie chaque vidéo avant de la publier.\n\n"
            "Il s'ouvre depuis ton téléphone, sans compte Google.")


async def drives_manquants(client=None, maxi: int = 3) -> list:
    """28/09 (Gaëtan, Simon : « veille à ce que les clippeurs l'aient avec leur premier compte ») : un clipper livré sans Drive
    (créatrice écrite en minuscules, source absente ou Drive en panne à ce moment-là) le reçoit au passage suivant de la boucle,
    dans son salon perso, et ses TOP 20 se déclinent dans la foulée. Renvoie les prénoms servis (au plus `maxi` par passage)."""
    if not google_api.actif():
        return []
    etat = _lire_etat()
    faits = []
    for uid, fiche in list(etat.get("clippers", {}).items()):
        if len(faits) >= maxi or fiche.get("drive") or not fiche.get("creatrice") or not fiche.get("comptes"):
            continue
        if not _source_de(fiche["creatrice"]):
            continue                                                    # rien à créer tant que la créatrice n'a pas de source
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        if m is None:
            continue
        prenom = m.display_name.split()[0] if m.display_name.split() else m.display_name
        try:
            drive = await dossier_drive(prenom, fiche["creatrice"], fiche.get("email", ""))
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Drive rattrapé pour %s : %s", prenom, erreur)
            continue
        if not drive:
            continue
        etat = _lire_etat()
        etat.setdefault("clippers", {}).setdefault(uid, {})["drive"] = drive
        _ecrire_etat(etat)
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        cible = salon if salon is not None else m
        try:
            await cible.send(texte_drive(prenom, fiche["creatrice"], drive))
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Drive de %s : envoi impossible (%s)", prenom, erreur)
        if _deps.get("reels_pour_nouveau") and client is not None:
            try:
                client.loop.create_task(_deps["reels_pour_nouveau"](prenom, fiche["creatrice"]))
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("TOP 20 après le Drive de %s : %s", prenom, erreur)
        faits.append(prenom)
        journal.info("Drive rattrapé pour %s (%s)", prenom, fiche["creatrice"])
    return faits


async def dossier_drive(prenom: str, creatrice: str, email: str) -> str:
    """Dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice : un raccourci vers CHAQUE source (Reels,
    photos : tout le contenu, rien de copié, aucun espace consommé), les sources partagées en lecture à son e-mail.
    Décision du 24/09 : plus de copies limitées ; 25/09 : plus de sous-dossier « Reels spoofés » (spoofer abandonné).
    '' si le Drive n'est pas configuré."""
    if not google_api.actif():
        return ""
    cfg = _source_de(creatrice)
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
        if src["id"] not in _sources_publiques and await google_api.drive_partager_public(src["id"]):
            _sources_publiques.add(src["id"])                           # 30/09 : le raccourci s'ouvre sans e-mail (Ricardo)
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
    top20 = ""
    try:
        ancien_top = next((f for f in existants if f.get("mimeType") == google_api.DOSSIER_MIME
                           and f.get("name", "").strip().lower() == "reels uniques"), None)
        if ancien_top is not None:
            await google_api.drive_renommer(ancien_top["id"], NOM_TOP20)
            top20 = ancien_top["id"]
        else:
            top20 = (await google_api.drive_trouver_dossier(NOM_TOP20, dossier)
                     or await google_api.drive_creer_dossier(NOM_TOP20, dossier))
    except RuntimeError as erreur:
        journal.warning("Dossier « %s » pour %s : %s", NOM_TOP20, prenom, erreur)
    if email:
        await _partager(dossier, email)
    try:
        await google_api.drive_partager_public(dossier)                 # 28/09 (Gaëtan) : lecture par le lien, plus besoin d'e-mail
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Partage par lien du Drive de %s : %s", prenom, erreur)
    journal.info("Drive de %s (%s) prêt : %s sources, lecture par le lien", prenom, creatrice, len(sources))
    # 30/09 (Gaëtan : « ajoute le TOP 20 Reels dans le Drive directement ») : le lien donné au clipper ouvre son dossier
    # « TOP 20 Reels », ses vidéos prêtes à publier (le partage par lien du dossier parent vaut pour lui).
    return google_api.drive_lien(top20 or dossier)


RESERVATION_JOURS = int(os.environ.get("RESERVATION_JOURS", "2") or 2)   # 28/09 (Gaëtan : GO) : la réservation qui expire ; 29/09 : 48 h au lieu de 5 jours


RESERVATION_ACTIVE = os.environ.get("RESERVATION_EXPIRE", "0").strip() == "1"   # 05/10 : éteinte, la règle unique de sortie_auto la remplace


async def reservations_expirees(historique: dict, maintenant=None) -> list:
    """Un clipper livré depuis RESERVATION_JOURS jours ou plus dont AUCUN compte n'existe (toutes ses lignes encore « à créer »,
    au moins trois scans sans le voir) : ses lignes retournent au vivier (Gérant vidé), ses alias 2FA sont détachés, sa fiche est
    vidée ; l'appelant remet son parcours à zéro et lui propose de reprendre. Renvoie [(uid, prénom, créatrice, nb de lignes)].
    05/10 (Gaëtan : « juste 3 jours sans compte créé ») : ÉTEINTE (RESERVATION_EXPIRE=1 pour la rallumer) — trois horloges
    se contredisaient ; la sortie à 3 jours (sortie_auto) rend les comptes au vivier elle-même."""
    if not actif() or not RESERVATION_ACTIVE:
        return []
    maintenant = maintenant or datetime.now(timezone.utc)
    etat = _lire_etat()
    comptes = await lire_comptes()
    par_handle = {c["handle"].lower(): c for c in comptes if c.get("handle")}
    faits = []
    for uid, fiche in list(etat.get("clippers", {}).items()):
        handles = [str(h).lower() for h in (fiche.get("comptes") or [])]
        if not handles or not fiche.get("date"):
            continue
        try:
            livre = datetime.fromisoformat(str(fiche["date"])[:19])
        except ValueError:
            continue
        if livre.tzinfo is None:
            livre = livre.replace(tzinfo=timezone.utc)
        if maintenant - livre < timedelta(days=RESERVATION_JOURS):
            continue
        lignes = [par_handle[h] for h in handles if h in par_handle]
        if not lignes or any(_norm(c["etat"]) not in A_CREER for c in lignes):
            continue                                                    # un compte créé au moins : la sortie à 14 jours jugera
        scans = [e for h in handles for e in (historique.get(h) or [])]
        if len(scans) < min(3, RESERVATION_JOURS) or any(e.get("existe") for e in scans):   # 29/09 : 2 scans suffisent à 48 h
            continue
        for c in lignes:
            await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "gerant"), [[""]])
            etat["livres"].pop(c["handle"].lower(), None)
        if codes_2fa.actif():
            try:
                codes_2fa.detacher([c["mail"] for c in lignes if c.get("mail")])
            except Exception:                                           # noqa: BLE001
                pass
        prenom = str(lignes[0].get("gerant") or "").split()[0] if str(lignes[0].get("gerant") or "").split() else "?"
        fiche["comptes"], fiche["acces"] = [], []
        fiche["expire"] = maintenant.isoformat(timespec="seconds")
        faits.append((uid, prenom, fiche.get("creatrice", ""), len(lignes)))
        journal.info("Réservation expirée : %s (%s), %d ligne(s) rendue(s) au vivier", prenom, fiche.get("creatrice", ""), len(lignes))
    if faits:
        _ecrire_etat(etat)
    return faits


# ------------------------------------------------------------------ livraison
async def attribuer_lien(membre, creatrice: str, tous: list = None, comptes: list = None, creer: bool = True) -> dict:
    """Le lien GAML du clipper : celui déjà à lui (paie_clics), sinon — seulement si `creer` — le lien libéré d'un sortant de la
    même créatrice, sinon un lien « Clipping Prénom » déjà dans GAML, sinon un clone du modèle de la créatrice (27/09 : « tu
    dupliques celui d'avant ») ; puis la carte « Plateforme privée » reçoit le tracking OnlyFans du POD (si `comptes`).
    05/10 (Gaëtan : « le lien que pour le troisième compte ») : appelée avec creer=True par le parcours à l'ouverture de
    l'étape 3, et avec creer=False par `livrer` (rappel d'un lien existant seulement). Écrit `fiche["lien"]` dans onboarding.json.
    Renvoie {"lien", "lid", "lignes"} (lignes = bilan pour l'admin)."""
    prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
    if tous is None and actif():
        try:
            tous = await lire_comptes()
        except RuntimeError:
            tous = []
    tous = tous or []
    if comptes is None:
        handles = {str(h).lower() for h in (_lire_etat()["clippers"].get(str(membre.id)) or {}).get("comptes", [])}
        comptes = [c for c in tous if c.get("handle") and c["handle"].lower() in handles]
    lien, lid = "", ""
    resultat = []
    try:
        d = paie_clics._lire() if paie_clics.actif() else {"liens": {}}
        lids = paie_clics.liens_de(d, str(membre.id))
        # 07/10 (Rianah sur Chloé et Sarah, avec ses liens Sophie) : le lien de CETTE créatrice ; un lien sans créatrice notée garde
        # l'ancien comportement ; si tous ses liens sont à d'autres créatrices, on passe à la reprise ou au clone.
        cr_n = (_norm(creatrice).split() or [""])[0]
        lids_c = [l for l in lids if (_norm(str((d["liens"].get(l) or {}).get("creatrice") or "")).split() or [""])[0] == cr_n]
        fiche_eq = (_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(membre.id)) or {}) if _deps.get("FICHIER_EQUIPES") else {}
        multi = bool(fiche_eq.get("creatrices_en_plus"))                    # plusieurs créatrices : jamais le lien d'une autre
        lids = lids_c or ([] if multi else [l for l in lids if not (d["liens"].get(l) or {}).get("creatrice")])
        repris = False
        if not lids and creer and paie_clics.actif():
            async with paie_clics.verrou_liens:                          # 08/10 (revue) : jamais pendant que le ménage le désactive
                d = paie_clics._lire()
                libre = paie_clics.lien_libre(d, creatrice)
                # 28/09 : le lien d'un sortant va au suivant ; 08/10 : réactivé s'il avait été désactivé par le ménage, sinon on clone
                if libre and await paie_clics.reprendre_lien(d, libre[0], str(membre.id), prenom, creatrice):
                    lid, lien, repris = libre[0], libre[1].get("url", ""), True
                elif libre:
                    resultat.append("⚠️ lien libéré désactivé, réactivation refusée par GAML (forfait plein ?) : clone tenté")
                if libre:
                    paie_clics._ecrire(d)
        if lids:
            lid = lids[0]
            lien = d["liens"][lid].get("url", "")
        elif not creer:
            return {"lien": "", "lid": "", "lignes": []}                    # 05/10 : pas encore le moment (compte 3 pas ouvert)
        elif repris:
            pass
        elif paie_clics.actif():
            liens = await paie_clics.liens_gaml()
            de_la_creatrice = [l for l in liens if _norm(str(l.get("name", "")).split()[0] if l.get("name") else "") == _norm(creatrice.split()[0])]
            modeles = [l for l in de_la_creatrice if paie_clics._prenom_note(l.get("note"))]
            # 28/09 (Gaëtan, Clara) : le lien posé dans la colonne « Lien GAML associé » d'une ligne libre de la créatrice est LE modèle à dupliquer
            urls_modele = {str(c.get("lien_gaml") or "").strip().rstrip("/") for c in tous
                           if _pour_creatrice(c, creatrice) and _norm(c.get("gerant") or "") in GERANTS_LIBRES and str(c.get("lien_gaml") or "").startswith("http")}
            poses = [l for l in de_la_creatrice if str(l.get("url") or "").rstrip("/") in urls_modele]
            if poses:
                modeles = poses
            modeles.sort(key=lambda l: str(l.get("createdAt") or ""), reverse=True)        # le plus récent d'abord
            if not modeles:                                              # 27/09 : première créatrice sans lien de clipper (Jade, Clara, Maddie) →
                modeles = [l for l in de_la_creatrice if "/fb" not in str(l.get("url", "")) and "/ytb" not in str(l.get("url", ""))]   # on part de son lien principal
            # 03/10 : un lien « Clipping Prénom » de la créatrice existe déjà (relance après une activation ratée : 22 clones
            # « Clipping Andry » le 01/10, GAML plein) → on le reprend, jamais un clone de plus.
            # 09/10 : jamais le lien libéré d'un homonyme parti (note encore « Clipping Julien ») : ses visites sont celles de l'ancien
            existants = [l for l in de_la_creatrice if _norm(paie_clics._prenom_note(l.get("note"))) == _norm(prenom) and l.get("enabled", True)
                         and str((d["liens"].get(l.get("id")) or {}).get("uid") or "") in ("", str(membre.id))
                         and not paie_clics.note_du_sortant(d["liens"].get(l.get("id")) or {}, l.get("note"))]
            existants.sort(key=lambda l: str(l.get("createdAt") or ""), reverse=True)
            nouveau = None
            if existants:
                nouveau = {"id": existants[0]["id"], "url": existants[0].get("url", "")}
                journal.info("Lien GAML de %s repris (%s), pas de clone", prenom, nouveau["url"])
            elif modeles:
                nouveau = await paie_clics.cloner_lien(modeles[0]["id"], modeles[0].get("name", creatrice), f"Clipping {prenom}")
                # 05/10 : le clone reçoit le tracking MYM réservé à SON numéro (onglet « Réserve trackings MYM »), jamais celui du modèle
                try:
                    ligne_mym = await reserve_mym.pour_clone(nouveau["id"], creatrice)
                except Exception as erreur:                         # noqa: BLE001
                    ligne_mym = f"⚠️ réserve MYM : {type(erreur).__name__} {str(erreur)[:80]}"
                if ligne_mym:
                    resultat.append(ligne_mym)
            if nouveau:
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
    if lien:
        etat = _lire_etat()
        fiche = etat["clippers"].setdefault(str(membre.id), {})
        if fiche.get("lien") != lien:
            fiche["lien"] = lien
            fiche.setdefault("creatrice", creatrice)
            _ecrire_etat(etat)
    return {"lien": lien, "lid": lid, "lignes": resultat}


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
                    and _pour_creatrice(c, creatrice)
                    and _norm(c.get("etat") or "") != "ban"]                # 06/10 : un compte banni n'est jamais livré (Clarisse : 3 BAN)
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
    # 2. lien GAML — 05/10 (Gaëtan : « le lien que pour le troisième compte ») : plus créé ici. Un lien déjà attribué à ce clipper
    # est simplement rappelé ; sinon le parcours le crée à l'ouverture de l'étape 3 (attribuer_lien, creer=True).
    lien, lid = "", ""
    try:
        bilan_lien = await attribuer_lien(membre, creatrice, tous, comptes, creer=declencheur.startswith("!onboarding"))
        lien, lid = bilan_lien.get("lien", ""), bilan_lien.get("lid", "")
        resultat += bilan_lien.get("lignes", [])
    except RuntimeError as erreur:
        resultat.append(f"GAML : {erreur}")
    # 3. Drive
    drive, email = "", ""
    try:
        email = (_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("liaisons", {}).get(str(membre.id), {}).get("email", "")
                 or fiche.get("email", ""))
        drive = await dossier_drive(prenom, creatrice, email)
        resultat.append("Drive " + ("✅" if drive else "non configuré"))
    except RuntimeError as erreur:
        resultat.append(f"Drive : {erreur}")
    # 4. message
    # 30/09 (Gaëtan, salon de Mathias : « simplifie encore ») : en un-par-48 h, plus de ligne « tes accès arrivent… » — l'étape 1
    # suit tout de suite avec le compte 1. Le message long (`!onboarding` forcé) reste.
    texte = ("" if (UN_PAR_JOUR and comptes and not declencheur.startswith("!onboarding"))
             else message_comptes(comptes, prenom, creatrice))
    # 30/09 (Gaëtan : « ne spam pas le clippeur avec trop d'informations ») : le message court reste une ligne ; le Drive
    # arrive dans l'étape 1, le lien dans l'étape 6, là où ils servent. Le message long (`!onboarding` forcé) les garde.
    if not (UN_PAR_JOUR and comptes and not declencheur.startswith("!onboarding")):
        if lien:
            texte += f"\n\n🔗 **Ton lien** : {lien} · tes visites : `!mesclics`"
        if drive:
            # 01/10 : « Tes vidéos à monter », jamais « à publier » (chaque vidéo se modifie avant d'être publiée)
            texte += (f"\n\n📁 **Tes vidéos à monter** (TOP 20 de {creatrice.split()[0]}) : <{drive}>"
                      "\n\nModifie chaque vidéo avant de la publier.")
    if salon is not None and codes_2fa.actif():
        try:
            n_alias = codes_2fa.rattacher([c["mail"] for c in comptes if c.get("mail")], str(salon.id), "onboarding")
            if n_alias:
                resultat.append(f"{n_alias} alias 2FA rattaché(s)")                # 26/09 : plus de ligne dans le message, l'étape 1 dit `!code`
        except Exception as erreur:                                     # jamais bloquer la livraison
            journal.warning("Alias 2FA %s : %s", prenom, erreur)
    cible = salon if salon is not None else membre
    try:
        if texte:
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


async def message_clipper(message) -> bool:
    """25/09 : un clipper qui postait une adresse e-mail dans son salon perso (ou en MP) recevait le Drive partagé à cette
    adresse. 01/10 : éteint, le message n'est plus jamais intercepté (renvoie toujours False). Depuis le 28/09 le Drive s'ouvre
    par son lien, sans compte Google (texte_drive) ; or toute adresse était captée, y compris l'e-mail d'un compte Instagram
    donné par l'agence : la fiche était écrasée, le Drive partagé avec cette adresse, « Ouvre-le avec ce compte Google » répondu,
    et la question du clipper n'arrivait jamais à l'assistant. Le message suit maintenant son chemin normal."""
    return False


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


def _premier(t) -> str:
    return (_norm(t or "").split() or [""])[0]


def _lien_rangeable(info: dict) -> bool:
    """09/10 (dashboard) : un lien que liens_classeur peut ranger sous un prénom = un lien qui a un détenteur dans le bot (uid, ou
    clipper suivi par le rapport). Jamais un lien libéré (sa note dit encore « Clipping Eddy » jusqu'au renommage : le nouvel
    homonyme l'aurait reçu), hors clipping (Metricool), effacé ou désactivé, ni une fiche seulement relevée (page de créatrice,
    lien neuf pas encore attribué)."""
    info = info or {}
    if info.get("supprime_gaml") or info.get("desactive") or info.get("hors_clipping"):
        return False
    if str(info.get("uid") or ""):
        return True
    return bool(info.get("suivi")) and not info.get("libere")


def ligne_metricool(gerant: str) -> bool:
    """« Rianah (Metricool) » : une ligne passée sur Metricool, gérée par son repreneur."""
    return "metricool" in _mots(gerant)


def _lien_du_repreneur(info: dict, gerant: str) -> bool:
    """09/10 (dashboard) : le lien (fiche clics.json) est-il un lien Metricool du repreneur de cette ligne (« Rianah Metricool N
    (ex-…) » pour « Rianah (Metricool) ») ?"""
    rep = [m for m in re.findall(r"[a-z0-9]+", _norm(gerant or "")) if m != "metricool"]
    note = re.findall(r"[a-z0-9]+", _norm(re.sub(r"\(\s*ex[^)]*\)", " ", str((info or {}).get("note") or ""), flags=re.I)))
    return bool(rep) and note[:len(rep) + 1] == rep + ["metricool"]


def _lien_d_un_autre(info: dict, gerant: str, note_vive: str = None, proprietaires=None) -> bool:
    """09/10 (dashboard : « pas de liens pas assignés au compte ») : le lien d'une cellule (sa fiche clics.json) est-il, à coup
    sûr, à quelqu'un d'autre que le détenteur de la ligne, ou à personne ? Effacé ou désactivé, libéré, hors clipping (sauf le lien
    Metricool du repreneur d'une ligne « X (Metricool) ») → à personne : oui. Contrat C6(d) (revue CLICS du 09/10 : un Gérant
    « Jean-Marc » au pseudo « Jean Marc - Sophie » voyait son PROPRE lien effacé, comparé au premier mot du pseudo) : « lien d'un
    autre clipper » se décide sur les IDENTIFIANTS — l'uid du lien (clics.json) n'est pas parmi `proprietaires`, les uid qui
    détiennent la ligne d'après onboarding.json (_proprietaires) —, jamais sur un prénom. Ligne sans propriétaire connu, lien suivi
    par le rapport (sans uid), inconnu du bot ou seulement relevé → non : rien ne prouve qu'il n'est pas le sien (le contrôle
    signale). Une ligne « X (Metricool) » n'a pas de clipper : un lien attribué à un clipper n'y est jamais le sien ; `note_vive`
    (la note GAML de maintenant) qui en fait un lien Metricool du repreneur → non (renommage pas encore suivi par la passe horaire)."""
    if not info:
        return False
    if info.get("supprime_gaml") or info.get("desactive"):
        return True
    if info.get("libere") and not str(info.get("uid") or "") and not info.get("hors_clipping"):
        return True
    metricool = ligne_metricool(gerant)
    if metricool and note_vive is not None and _lien_du_repreneur({"note": note_vive}, gerant):
        return False
    if info.get("hors_clipping"):
        return not (metricool and _lien_du_repreneur(info, gerant))
    uid = str(info.get("uid") or "")
    if uid:
        if metricool:
            return True
        props = {str(u) for u in (proprietaires or ()) if str(u)}
        return bool(props) and uid not in props
    if info.get("libere"):
        return True
    return False


def _cle_handle(h) -> str:
    return normaliser_handle(h).lower()


def _proprietaires() -> dict:
    """Contrat C6(d) (revue CLICS du 09/10) : {@ normalisé : {uid}} — qui détient chaque ligne d'après onboarding.json : la livraison
    la plus récente (`livres`, posée quand le Gérant change dans le classeur) prime, sinon les fiches (comptes, accès) qui portent ce
    @ (`liberer` les nettoie). {} si le fichier est illisible ou absent (rien n'est alors décidé sur les identifiants)."""
    try:
        etat = _lire_etat()
    except Exception:                                                   # noqa: BLE001
        return {}
    out = {}
    for uid, fiche in (etat.get("clippers") or {}).items():
        if not isinstance(fiche, dict):
            continue
        hs = {h for h in fiche.get("comptes") or [] if isinstance(h, str)}
        hs |= {a.get("handle") for a in fiche.get("acces") or [] if isinstance(a, dict) and isinstance(a.get("handle"), str)}
        for h in hs:
            if _cle_handle(h):
                out.setdefault(_cle_handle(h), set()).add(str(uid))
    for h, l in (etat.get("livres") or {}).items():
        if isinstance(l, dict) and str(l.get("uid") or "") and _cle_handle(h):
            out[_cle_handle(h)] = {str(l["uid"])}
    return out


def _mots_nom(t) -> set:
    """Les mots d'un pseudo avant « - Créatrice » (ou d'un Gérant), tirets traités comme des espaces : « Jean-Marc » → {jean, marc}."""
    return set(re.findall(r"[a-z0-9]+", _norm(str(t or "").split(" - ")[0]))) - {"metricool", "clipper", "compte"}


def _detenteurs(gerant: str, uids, cache: dict = None) -> set:
    """Les uid de `uids` (propriétaires d'une ligne selon onboarding.json) compatibles avec le Gérant écrit dans le classeur : un mot
    en commun entre le Gérant et le nom du membre (pseudo, sinon prénom du registre), ou membre introuvable (onboarding.json fait
    foi). Un Gérant changé à la main pour quelqu'un d'autre sans que le bot ait pu le suivre (homonymes) ne garde pas l'ancien
    propriétaire : la ligne est alors traitée comme sans propriétaire connu (rien n'y est décidé sur un identifiant périmé)."""
    cache = {} if cache is None else cache
    mots_g = _mots_nom(gerant)
    out = set()
    for uid in uids or ():
        uid = str(uid)
        if uid not in cache:
            noms = []
            m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            if m is not None:
                noms.append(getattr(m, "display_name", "") or "")
            try:
                fiche = (_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) or {}).get(uid) or {} if _deps.get("FICHIER_EQUIPES") else {}
            except Exception:                                           # noqa: BLE001
                fiche = {}
            noms.append(str((fiche or {}).get("prenom") or ""))
            cache[uid] = set().union(*(_mots_nom(n) for n in noms))
        if not cache[uid] or (mots_g & cache[uid]):
            out.add(uid)
    return out


def _jour_paris():
    """La date du jour à Paris (heure_paris du bot), repli sur l'horloge."""
    try:
        return _deps["heure_paris"]().date()
    except Exception:                                                   # noqa: BLE001
        return paie_clics.jour_paris()


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
    notes_vives = {}                                                    # 09/10 : la note GAML de maintenant, quand la liste la porte
    try:
        liste = [l for l in await paie_clics.liens_gaml() if l.get("id")]
        noms = {l["id"]: str(l.get("name") or "") for l in liste}
        notes_vives = {l["id"]: str(l.get("note") or "") for l in liste if "note" in l and l.get("note") is not None}
    except RuntimeError as erreur:
        journal.warning("Liens GAML illisibles pour le classeur : %s", erreur)
        noms = {}
    creatrices = {c["creatrice"] for c in comptes if c.get("creatrice")}
    par_prenom, par_uid, par_url = {}, {}, {}
    for lid, info in d.get("liens", {}).items():
        url = str(info.get("url") or "").strip()
        if url:
            par_url[_url_cle(url)] = (info, notes_vives.get(lid))
        # 09/10 (dashboard) : jamais un lien libéré, hors clipping, effacé ou désactivé rangé par prénom (le lien libéré d'un sortant,
        # encore noté « Clipping Eddy », était écrit sur les lignes du nouvel Eddy) ; seulement les liens qui ont un détenteur
        if not url or not _lien_rangeable(info):
            continue
        entree = (_creatrice_du_lien(noms.get(lid, ""), info, url, creatrices), url, str(info.get("depuis") or ""), str(lid))
        uid_l = str(info.get("uid") or "")
        if uid_l:
            par_uid.setdefault(uid_l, []).append(entree)
        prenom = _prenom_du_lien(info)
        if prenom:
            par_prenom.setdefault(_norm(prenom), []).append((entree, uid_l or "suivi:" + _norm(info.get("suivi_nom") or prenom)))
    # contrat C6(d) (revue CLICS du 09/10) : la ligne est rattachée à son détenteur par les IDENTIFIANTS (onboarding.json → uid →
    # liens de clics.json) ; le prénom ne sert plus qu'aux anciennes lignes mises à la main (inconnues d'onboarding.json), et
    # seulement s'il ne désigne qu'UN détenteur (deux Eddy : la cellule n'est jamais touchée par le prénom)
    proprietaires, noms_uid = _proprietaires(), {}
    ecrits, groupes = 0, {}
    creatrices = creatrices_connues(comptes)
    for c in comptes:
        g = _norm(c["gerant"])
        if not c["handle"] or g in GERANTS_LIBRES or not a_colonne("lien_gaml", c.get("onglet", "")):
            continue
        actuel = str(c.get("lien_gaml") or "").strip()
        # 05/10 (Gaëtan : « sur la ligne du compte principal de la créatrice, le lien GAML est effacé à chaque passage ») : la
        # cause était ici — Gérant « Chloé » n'a aucun lien dans paie_clics (ce n'est pas un clipper), donc `voulu` valait "" et
        # la cellule était vidée, puis revidée à chaque scan. Une ligne dont le Gérant est une créatrice n'est jamais vidée.
        if est_ligne_creatrice(c, creatrices):
            # 05/10 (Gaëtan : « scrape les clics des comptes des créas ») : la ligne de la créatrice reçoit SON lien GAML, celui dont
            # la note dit « Compte de @<son identifiant> » (lien_gaml_creatrice), seulement si la cellule est vide ; jamais écrasée,
            # jamais vidée. 09/10 (dashboard) : le repli « unique note qui commence par son prénom » seulement si elle n'a qu'une
            # ligne de compte (son deuxième compte recevait le lien du principal).
            if actuel:
                continue
            try:
                details = await _liens_gaml_details()
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Liens GAML (créatrices) illisibles : %s", erreur)
                continue
            voulu = str((lien_gaml_creatrice(c, details, seule=lignes_creatrice(comptes, c, creatrices) <= 1) or {}).get("url") or "").strip()
            if not voulu:
                continue
            try:
                await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "lien_gaml"), [[voulu]])
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Classeur : lien GAML de la créatrice %s non écrit : %s", c.get("creatrice") or c.get("onglet"), erreur)
                continue
            c["lien_gaml"] = voulu                                      # la lecture en mémoire suit (même passage)
            ecrits += 1
            groupes[(c["gerant"], c.get("creatrice") or c.get("onglet") or "?", voulu)] = 1
            continue
        cr = (_norm(c["creatrice"]).split() or [""])[0]
        detenteurs = set()
        if ligne_metricool(c["gerant"]):
            liens = []
        else:
            detenteurs = _detenteurs(c["gerant"], proprietaires.get(_cle_handle(c["handle"]), set()), noms_uid)
            if len(detenteurs) > 1:
                continue                                                # fiches contradictoires : on ne tranche pas (le contrôle signale)
            if detenteurs:
                liens = par_uid.get(next(iter(detenteurs)), [])          # les liens de SON identifiant
            else:
                ents = par_prenom.get(g, [])
                ids = {i for _, i in ents if not i.startswith("suivi:")} or {i for _, i in ents}
                if len(ids) > 1:
                    continue                                            # deux détenteurs de ce prénom (homonymes) : jamais par le prénom
                liens = [e for e, i in ents if i in ids]
        if liens:
            cands = [x for x in liens if x[0] == cr] or ([x for x in liens] if len(liens) == 1 and not liens[0][0] else [])
            voulu = max(cands, key=lambda x: (x[2], x[3]))[1] if cands else ""
        else:
            # 09/10 (dashboard) : le Gérant n'a encore aucun lien (nouveau clipper sur une ligne redonnée, ligne « X (Metricool) »,
            # prénom inconnu du bot). Avant : cellule gardée, donc le lien de l'ancien clipper restait et ses clics comptaient pour
            # le nouveau. Maintenant : vidée quand elle porte à coup sûr le lien de personne (libéré, hors clipping, effacé,
            # désactivé) ou d'un autre clipper — décidé sur les identifiants (C6(d) : l'uid du lien n'est pas le détenteur de la
            # ligne selon onboarding.json) ; une ligne « X (Metricool) » ne garde que les liens Metricool de SON repreneur ; un lien
            # inconnu du bot (collé à la main avant son attribution) ou une ligne sans détenteur connu : la cellule reste.
            info_c, note_c = par_url.get(_url_cle(actuel)) or (None, None)
            if not actuel or not _lien_d_un_autre(info_c, c["gerant"], note_c, detenteurs):
                continue
            voulu = ""
        if voulu == actuel:
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


_details_gaml = {"jour": "", "liens": []}
SECOURS_MAX = int(os.environ.get("CLICS_SECOURS_MAX", "40") or 40)         # revue CLICS : appels GAML de secours par passage de clics_classeur
DETAILS_LISTE_TTL = int(os.environ.get("GAML_DETAILS_TTL", "3600") or 3600)   # 09/10 : la liste GAML relue au plus toutes les heures
DETAILS_REESSAI = int(os.environ.get("GAML_DETAILS_REESSAI", "900") or 900)    # 09/10 : un détail illisible retenté 15 min après


def _fiches_clics() -> dict:
    """Les fiches de liens de clics.json (URL et note connues du bot), {} si illisibles."""
    try:
        return paie_clics._lire().get("liens", {}) or {}
    except Exception:                                                   # noqa: BLE001
        return {}


async def _liens_gaml_details(avec_desactives: bool = False) -> list:
    """[{id, url, note, groupe, actif}] des liens GAML actifs (la liste ne porte ni l'URL ni la note : un détail par lien).
    09/10 (dashboard) : 1. jamais une liste partielle gardée toute la journée : un détail illisible est retenté DETAILS_REESSAI
    secondes plus tard, et en attendant le lien garde l'URL et la note connues de clics.json (sinon il manque, et
    `_details_gaml["partiel"]` le dit aux appelants) ; 2. la liste est relue toutes les heures (un lien créé ou renommé dans la
    journée apparaît le jour même, une note portée par la liste remplace celle du cache) ; chaque détail reste en cache le reste du
    jour UTC ; 3. les liens désactivés sont lus aussi (la cellule qui en porte un garde ses visites), rendus seulement avec
    `avec_desactives` ; 4. liste illisible : le cache du jour s'il existe, sinon l'erreur remonte (rien d'écrit à 0 par l'appelant)."""
    c = _details_gaml
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    maintenant = time.time()
    if c.get("jour") != jour:
        c.update({"jour": jour, "liens": [], "par_id": {}, "echecs": {}, "liste": [], "liste_t": 0.0, "partiel": False})
    par_id, echecs = c.setdefault("par_id", {}), c.setdefault("echecs", {})
    if not c.get("liste") or maintenant - float(c.get("liste_t") or 0.0) >= DETAILS_LISTE_TTL:
        try:
            c["liste"] = [l for l in await paie_clics.liens_gaml() if l.get("id")]
            c["liste_t"] = maintenant
        except RuntimeError as erreur:
            if not c.get("liste"):
                raise
            journal.warning("Liens GAML : liste illisible (%s), celle de %s gardée", erreur,
                            datetime.fromtimestamp(float(c.get("liste_t") or 0), timezone.utc).strftime("%H:%M"))
    for l in c["liste"]:
        lid = l["id"]
        if lid in par_id or maintenant - float(echecs.get(lid) or 0.0) < DETAILS_REESSAI:
            continue
        try:
            det = await paie_clics.lien_detail(lid)
        except RuntimeError as erreur:
            echecs[lid] = maintenant
            journal.warning("Lien GAML %s : détail illisible (%s), retenté dans %s min", lid, erreur, DETAILS_REESSAI // 60)
            continue
        echecs.pop(lid, None)
        par_id[lid] = {"id": lid, "url": str(det.get("url") or ""), "note": str(det.get("note") or ""),
                       "groupe": str(((det.get("group") or l.get("group") or {}).get("name")) or "")}
    out, manquants, fiches = [], 0, None
    for l in c["liste"]:
        lid = l["id"]
        det = par_id.get(lid)
        if det is None:                                                 # détail illisible : l'URL et la note de clics.json
            fiches = _fiches_clics() if fiches is None else fiches
            info = fiches.get(lid) or {}
            if not str(info.get("url") or "").strip():
                manquants += 1
                continue
            det = {"id": lid, "url": str(info.get("url") or ""), "note": str(info.get("note") or ""),
                   "groupe": str(((l.get("group") or {}).get("name")) or "")}
        e = dict(det)
        if l.get("note") is not None and "note" in l:
            e["note"] = str(l.get("note") or "")                       # la liste de l'heure est plus fraîche que le détail du matin
        e["actif"] = l.get("enabled") is not False
        out.append(e)
    c["partiel"] = manquants > 0
    c["liens"] = [e for e in out if e["actif"]]
    return out if avec_desactives else list(c["liens"])


def _url_cle(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", str(url or "").strip().lower()).rstrip("/")


def _mots(texte: str) -> set:
    return set(re.findall(r"[a-z0-9]+", _norm(texte or "")))


def liens_du_bloc(gerant: str, creatrice: str, liens_cellule: set, details: list) -> list:
    """Les liens GAML d'un bloc de clipper : ceux de sa colonne « Lien GAML associé » PLUS ceux de la créatrice dont la note GAML
    contient tous les mots du Gérant (30/09 : Lilian a deux liens « Clipping Lilian », /4 et /5 ; le classeur ne portait que /5, le
    trafic était sur /4). Metricool et Clipping ne se mélangent pas : « Rianah (Metricool) » → notes « Rianah Metricool »,
    « Rianah » → « Clipping Rianah » seulement."""
    par_url = {_url_cle(d["url"]): d for d in details if d.get("url")}
    trouves = {par_url[_url_cle(u)]["id"]: par_url[_url_cle(u)] for u in liens_cellule if _url_cle(u) in par_url}
    mots = _mots(gerant) - {"clipper", "compte"}
    cr = (_norm(creatrice).split() or [""])[0]
    if mots:
        metricool = "metricool" in mots
        for d in details:
            if d.get("actif") is False:
                continue                                                # 09/10 : un lien désactivé n'est rattaché que par sa cellule
            # 09/10 : « (ex-Julien) » dit l'ancien propriétaire, jamais l'actuel (« Rianah Metricool 5 (ex-Julien) » est à Rianah,
            # « Clipping libre (ex-Julien) » n'est à personne) : ces mots ne comptent pas
            mn = _mots(re.sub(r"\(\s*ex[^)]*\)", " ", str(d.get("note") or ""), flags=re.I))
            if mots <= mn and ("metricool" in mn) == metricool and (_norm(d.get("groupe")).split() or [""])[0] == cr:
                trouves[d["id"]] = d
    return list(trouves.values())


def _payes_hier_connu(store: dict, lid: str, hier) -> int | None:
    """Les visites payables d'hier d'un lien si paie_clics les a déjà relevées (aucun appel GAML), sinon None."""
    v = ((store or {}).get("jours") or {}).get(str(lid), {}).get(hier.isoformat())
    return int(v.get("payes") or 0) if isinstance(v, dict) and "payes" in v and not v.get("erreur") else None


async def clics_classeur(comptes: list, clics_de=None) -> dict:
    """30/09 (Gaëtan : « associe automatiquement les Clics last 7d avec les clippeurs, comme les liens de tracking à droite ») :
    un chiffre par clipper et par onglet = les visites payables des 7 derniers jours de TOUS ses liens GAML (liens_du_bloc),
    écrit UNE fois, sur la ligne du milieu de chaque bloc (lignes qui se suivent avec le même Gérant), les autres lignes du bloc
    vidées — comme la colonne des liens. Les onglets sont des tableaux Google : pas de cellules fusionnées possibles. Sans lien
    GAML trouvé : cellule vide (l'ancien calcul par prénom additionnait les liens de toutes les créatrices).
    05/10 (Gaëtan : « Clics hier ») : même chose dans la colonne « Clics hier » (la veille, heure de Paris), prise dans le relevé
    quotidien de paie_clics quand il l'a (zéro appel GAML), sinon un appel par lien. La ligne d'une créatrice (Gérant = son prénom)
    ne compte que le lien écrit dans sa cellule, jamais les liens « Clipping » de ses clippers. Renvoie {"ecrits": n}.
    09/10 (dashboard) : 1. calcul depuis le relevé de clics.json (`paie_clics.clics_lien` : 0 appel GAML quand le relevé est complet,
    l'API seulement en secours) ; 2. un lien repris ne compte qu'à partir de sa reprise (`depuis`, comme la paie : avant, les visites
    de l'ancien clipper étaient créditées au nouveau pendant 7 jours) ; 3. « hier » = la veille à Paris (avant : en UTC, J-2 entre 0 h
    et 2 h) ; 4. jamais 0 sur une erreur : un lien illisible (relevé et API) → les cellules du bloc sont GARDÉES telles quelles, et un
    bloc sans lien trouvé alors que la liste GAML est partielle aussi ; 5. un lien qui est à coup sûr celui d'un autre ou de personne
    (libéré, hors clipping, attribué à un autre identifiant — point 8 —, effacé, désactivé) n'est plus compté (double compte : le
    contrôle le signale) ; 6. le repli de la ligne de créatrice seulement si elle n'a qu'une ligne de compte.
    Revue CLICS du 09/10 : 7. contrat C6(e) — la valeur d'un lien sur une période est celle de paie_clics.clics_lien (plancher
    `depuis`, None si un jour manque), la même que le Dashboard, le contrôle et le bouclage : le secours GAML relève les jours
    manquants DANS clics.json (paie_clics.completer, SECOURS_MAX appels par passage) au lieu d'une somme GAML de toute la période ;
    une période tout entière avant la reprise du lien n'est plus écrite « 0 » (rien à mesurer : cellule vide) ; 8. contrat C6(d) — un
    lien n'est « d'un autre clipper » que sur les identifiants (uid du lien ≠ détenteurs du bloc selon onboarding.json), qu'il soit
    trouvé par la cellule ou par la note ; sans détenteur connu, deux détenteurs différents parmi les liens du bloc → cellules gardées.
    Renvoie {"ecrits": n, "gardes": blocs gardés faute de chiffre sûr}."""
    if not (actif() and paie_clics.actif()) or not comptes:
        return {"ecrits": 0, "gardes": 0}
    tous_details = await _liens_gaml_details(avec_desactives=True)
    details = [x for x in tous_details if x.get("actif") is not False]
    partiel = bool(_details_gaml.get("partiel"))
    fin = _jour_paris() - timedelta(days=1)
    debut = fin - timedelta(days=6)
    etat_s = {"store": {}, "secours": 0}
    try:
        etat_s["store"] = paie_clics._lire()
    except Exception:                                                   # noqa: BLE001 — sans relevé local, rien n'est sûr : cellules gardées
        etat_s["store"] = {}

    async def payes(lid: str, d0, d1):
        """Visites payables du lien pour son détenteur selon clics_lien (C6(e)) ; 'rien' si la période est tout entière avant la
        reprise du lien (`depuis`) ; None si illisible, même après le secours (jamais 0)."""
        store = etat_s["store"]
        dep = paie_clics._en_date((((store or {}).get("liens") or {}).get(lid) or {}).get("depuis"))
        if dep is not None and dep > d1:
            return "rien"
        v = paie_clics.clics_lien(store, lid, d0, d1)
        reste = SECOURS_MAX - etat_s["secours"]
        if v is None and reste > 0 and lid in ((store or {}).get("liens") or {}):
            try:
                etat_s["store"], n = await paie_clics.completer(lid, d0, d1, maximum=min(14, reste))
                etat_s["secours"] += n
                v = paie_clics.clics_lien(etat_s["store"], lid, d0, d1)
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Clics du lien %s (%s → %s) : secours GAML impossible (%s)", lid, d0, d1, erreur)
        if v is None:
            journal.warning("Clics du lien %s (%s → %s) : jour(s) non relevé(s) — cellule gardée", lid, d0, d1)
        return v
    creatrices = creatrices_connues(comptes)
    proprietaires, noms_uid = _proprietaires(), {}
    par_onglet = {}
    for c in comptes:
        if c.get("handle") and (a_colonne("clics", c.get("onglet", "")) or a_colonne("clics_hier", c.get("onglet", ""))):
            par_onglet.setdefault(c["onglet"], []).append(c)
    visites, visites_hier, valeurs, ecritures, gardes = {}, {}, {}, [], 0
    for onglet, lignes in par_onglet.items():
        champs = [ch for ch in ("clics", "clics_hier") if a_colonne(ch, onglet)]
        lignes.sort(key=lambda c: c["ligne"])
        blocs, courant = [], []
        for c in lignes:                                                 # blocs = lignes qui se suivent avec le même Gérant
            g = _norm(c.get("gerant"))
            if courant and (g != _norm(courant[-1].get("gerant")) or c["ligne"] != courant[-1]["ligne"] + 1):
                blocs.append(courant); courant = []
            courant.append(c)
        if courant:
            blocs.append(courant)
        for bloc in blocs:
            g = _norm(bloc[0].get("gerant"))
            if g in GERANTS_LIBRES:                                      # 30/09 : ligne rendue au vivier (réservation expirée,
                for c in bloc:                                           # !liberer) → son ancien chiffre part avec le Gérant
                    for ch in champs:
                        if str(c.get(ch) or "").strip():
                            ecritures.append((cellule(c, ch), [[""]]))
                continue
            cle = (onglet, g)
            if cle not in valeurs:
                tous = [c for c in lignes if _norm(c.get("gerant")) == g]
                dans_cellules = {str(c.get("lien_gaml") or "").strip() for c in tous} - {""}
                if est_ligne_creatrice(bloc[0], creatrices):            # 05/10 : la créatrice : son lien, pas ceux de ses clippers
                    par_url = {_url_cle(d["url"]): d for d in tous_details if d.get("url")}
                    liens = list({par_url[_url_cle(u)]["id"]: par_url[_url_cle(u)] for u in dans_cellules if _url_cle(u) in par_url}.values())
                    if not liens:                                        # cellule encore vide : la note GAML « Compte de @… »
                        trouve = lien_gaml_creatrice(bloc[0], details, seule=lignes_creatrice(comptes, bloc[0], creatrices) <= 1)
                        liens = [trouve] if trouve else []
                else:
                    gerant = bloc[0]["gerant"]
                    liens = liens_du_bloc(gerant, bloc[0].get("creatrice") or onglet, dans_cellules, tous_details)
                    fiches = (etat_s["store"] or {}).get("liens") or {}
                    # C6(d) : les détenteurs des lignes de ce Gérant d'après onboarding.json (uid), jamais son prénom
                    detenteurs = set() if ligne_metricool(gerant) else set().union(
                        *(_detenteurs(gerant, proprietaires.get(_cle_handle(c.get("handle")), set()), noms_uid) for c in tous))
                    if len(detenteurs) > 1:                              # deux homonymes sous le même Gérant dans l'onglet :
                        journal.info("Clics %s / %s : lignes de %d clippers différents sous ce Gérant — cellules gardées",
                                     gerant, onglet, len(detenteurs))
                        valeurs[cle] = None                              # jamais additionnés (un chiffre par Gérant et par onglet)
                        gardes += 1
                        continue
                    autres = [x for x in liens if _lien_d_un_autre(fiches.get(x["id"]), gerant, x.get("note"), detenteurs)]
                    if autres:                                           # 09/10 : le lien d'un autre ou de personne : pas compté
                        journal.info("Clics %s / %s : lien(s) d'un autre ou de personne, pas comptés : %s", gerant, onglet,
                                     ", ".join(str(x.get("url") or x["id"]) for x in autres))
                        liens = [x for x in liens if x not in autres]
                    if not detenteurs and not ligne_metricool(gerant):
                        # lignes sans détenteur connu (anciennes lignes mises à la main) : rien n'est décidé sur un prénom. Liens de
                        # plusieurs clippers (homonymes), ou lien d'un clipper trouvé par la seule cellule et dont le nom ne recoupe
                        # pas le Gérant → pas de chiffre sûr : cellules gardées (ni compté pour lui, ni effacé)
                        par_note = {x["id"] for x in liens_du_bloc(gerant, bloc[0].get("creatrice") or onglet, set(), tous_details)}
                        uid_de = lambda x: str((fiches.get(x["id"]) or {}).get("uid") or "")   # noqa: E731
                        uids_l = {uid_de(x) for x in liens} - {""}
                        douteux = [x for x in liens if uid_de(x) and x["id"] not in par_note
                                   and not _detenteurs(gerant, {uid_de(x)}, noms_uid)]
                        if len(uids_l) > 1 or douteux:
                            journal.info("Clics %s / %s : ligne sans détenteur connu, %s — cellules gardées", gerant, onglet,
                                         f"liens de {len(uids_l)} clippers" if len(uids_l) > 1 else "lien d'un autre nom dans la cellule")
                            valeurs[cle] = None
                            gardes += 1
                            liens = None
                if liens is None:
                    pass
                else:
                    total = total_hier = 0
                    mesure = mesure_hier = illisible = False
                    for d in liens:
                        if d["id"] not in visites:
                            visites[d["id"]] = await payes(d["id"], debut, fin)
                        if "clics_hier" in champs and d["id"] not in visites_hier:
                            visites_hier[d["id"]] = await payes(d["id"], fin, fin)
                        v, vh = visites[d["id"]], visites_hier.get(d["id"], "rien")
                        if v is None or ("clics_hier" in champs and vh is None):
                            illisible = True
                            continue
                        if v != "rien":
                            total, mesure = total + v, True
                        if vh != "rien":
                            total_hier, mesure_hier = total_hier + vh, True
                    if illisible or (not liens and partiel):
                        valeurs[cle] = None                              # 09/10 : pas de chiffre sûr → cellules gardées
                        gardes += 1
                    else:                                                # rien à mesurer (repris aujourd'hui) : vide, jamais « 0 »
                        valeurs[cle] = {"clics": str(total) if mesure else "", "clics_hier": str(total_hier) if mesure_hier else ""}
            if valeurs[cle] is None:
                continue
            milieu = bloc[(len(bloc) - 1) // 2]
            for c in bloc:
                for ch in champs:
                    voulu = valeurs[cle][ch] if c is milieu else ""
                    if voulu != str(c.get(ch) or "").replace(" ", "").strip():
                        ecritures.append((cellule(c, ch), [[voulu]]))
                        c[ch] = voulu                                    # 05/10 : la lecture en mémoire suit (Dashboard du même passage)
    if ecritures:
        await google_api.sheets_ecrire_plusieurs(CLASSEUR_LOGINS_ID, ecritures)
        journal.info("Classeur, Clics last 7d. / Clics hier : %d cellule(s)", len(ecritures))
    if gardes:
        journal.warning("Classeur, Clics : %d bloc(s) gardé(s) tels quels (jour non relevé, liste GAML partielle ou détenteur "
                        "incertain : jamais un faux 0)", gardes)
    return {"ecrits": len(ecritures), "gardes": gardes}


def plan_regroupement(lignes: list) -> tuple:
    """30/09 (Gaëtan : « regroupe les comptes des clippeurs ») : pour un onglet, ([(ligne, gérant à écrire)], [(position source,
    position cible)]). 1) Une ligne sans Gérant dont le « Lien GAML associé » est celui d'UN seul Gérant de l'onglet reçoit son
    nom (Ricado, Stéphane : des lignes de leur bloc restaient sans nom). 2) Toutes les lignes d'un Gérant se rangent ensemble, à la
    place de sa première ligne ; les autres gardent leur ordre. Les positions sont comptées depuis la première ligne de données."""
    lignes = sorted(lignes, key=lambda c: c["ligne"])
    cle = {}
    par_lien = {}
    for c in lignes:
        g = _norm(c.get("gerant"))
        if g not in GERANTS_LIBRES and str(c.get("lien_gaml") or "").strip():
            par_lien.setdefault(_url_cle(c["lien_gaml"]), set()).add(c["gerant"].strip())
    noms = []
    for c in lignes:
        g = _norm(c.get("gerant"))
        if g in GERANTS_LIBRES and str(c.get("lien_gaml") or "").strip():
            cands = par_lien.get(_url_cle(c["lien_gaml"]), set())
            if len({_norm(x) for x in cands}) == 1:
                nom = sorted(cands)[0]
                noms.append((c["ligne"], nom))
                g = _norm(nom)
        cle[c["ligne"]] = None if g in GERANTS_LIBRES else g
    ordre = [c["ligne"] for c in lignes]
    # 30/09 (Gaëtan : « mets toujours les comptes sans gérant à créer en bas de la feuille, pour voir combien j'ai de comptes d'avance
    # en capacité d'onboarding ») : ceux-là passent en bas, dans leur ordre (les POD restent groupés)
    etat_de = {c["ligne"]: _norm(c.get("etat")) for c in lignes}
    libres = [r for r in ordre if cle[r] is None and etat_de[r] in A_CREER]
    cible, vus = [], set(libres)
    for r in ordre:
        if r in vus:
            continue
        if cle[r] is None:
            cible.append(r); vus.add(r)
            continue
        for r2 in ordre:
            if r2 not in vus and cle[r2] == cle[r]:
                cible.append(r2); vus.add(r2)
    cible += libres
    courant, deplacements = list(ordre), []
    for t, r in enumerate(cible):
        p = courant.index(r)
        if p != t:
            deplacements.append((p, t))
            courant.insert(t, courant.pop(p))
    return noms, deplacements


def comptes_d_avance(comptes: list) -> dict:
    """{créatrice (onglet): comptes à créer sans Gérant} — la capacité d'onboarding (30/09)."""
    out = {}
    for c in comptes:
        if c.get("handle") and _norm(c.get("gerant")) in GERANTS_LIBRES and _norm(c.get("etat")) in A_CREER:
            out[c["onglet"]] = out.get(c["onglet"], 0) + 1
    return out


async def regrouper_comptes(comptes: list) -> int:
    """Applique plan_regroupement à chaque onglet (écriture des noms manquants, puis déplacements de lignes entières : chaque ligne
    garde son état, ses liens, ses followers). Renvoie le nombre de lignes touchées ; 0 = rien à faire."""
    if not actif() or not comptes:
        return 0
    par_onglet = {}
    for c in comptes:
        par_onglet.setdefault(c["onglet"], []).append(c)
    props = await google_api.sheets_proprietes(CLASSEUR_LOGINS_ID)
    total = 0
    for onglet, lignes in par_onglet.items():
        sid = (props.get(onglet) or {}).get("id")
        if sid is None or not a_colonne("gerant", onglet):
            continue
        noms, deplacements = plan_regroupement(lignes)
        numeros = sorted(c["ligne"] for c in lignes)
        if deplacements and numeros[-1] - numeros[0] + 1 != len(numeros):
            journal.warning("Logins %s : lignes non continues (doublon écarté ?), regroupement laissé de côté", onglet)
            deplacements = []
        if noms:
            await google_api.sheets_ecrire_plusieurs(CLASSEUR_LOGINS_ID, [(f"{onglet_a1(onglet)}!{lettre('gerant', onglet)}{r}", [[n]])
                                                                          for r, n in noms])
        if deplacements:
            debut = min(c["ligne"] for c in lignes) - 1                      # index 0 de la première ligne de données
            await google_api.sheets_batch_update(CLASSEUR_LOGINS_ID, [{"moveDimension": {
                "source": {"sheetId": sid, "dimension": "ROWS", "startIndex": debut + p, "endIndex": debut + p + 1},
                "destinationIndex": debut + t}} for p, t in deplacements])
        if noms or deplacements:
            journal.info("Logins %s : %d nom(s) de Gérant complété(s), %d ligne(s) déplacée(s)", onglet, len(noms), len(deplacements))
        total += len(noms) + len(deplacements)
    return total


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
    # 05/10 : une erreur ❌ qui revient à l'identique (« Rianah : GAML 404 », quatre fois le 03/10) n'est plus une action :
    # elle compte dans la signature comme un avertissement, donc postée une fois puis seulement si elle change.
    signature = "|".join(sorted(l for l in lignes if l.startswith(("⚠️", "❌"))))
    etat = _lire_etat()
    avant = etat.setdefault("bilans", {}).get(cle)
    action = any(l.startswith(("🔧", "🔗", "🎭")) for l in lignes)
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
        if paie_clics.releve_seul(info):
            continue                                                    # 09/10 : fiche de relevé seule, à personne : rien à poser
        nom = _prenom_du_lien(info)
        if not nom:
            continue
        if noms_liens and lid not in noms_liens:
            # 05/10 : lien effacé dans GAML (404 « Link not found » de Rianah à chaque passage) : plus rien à poser dessus.
            # Ses relevés passés restent dans clics.json ; on le marque une fois et on n'en parle plus.
            if not info.get("supprime_gaml"):
                info["supprime_gaml"] = datetime.now(timezone.utc).date().isoformat()
                paie_clics._ecrire(d)
                journal.info("Lien GAML %s (%s) absent de GAML : marqué supprimé", lid, nom)
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
    try:                                                                # 01/10 : avant la boucle, qui écrit la même fiche
        await rattraper_acces(client)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Rattrapage des accès : %s", erreur)
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
                    # 08/10 (régression du 05/10, vue par l'audit : Mohamed a reçu deux fois ses 3 comptes) : depuis le 05/10, le lien
                    # n'existe qu'avec le compte 3. Ce rattrapage appelait livrer(), qui renvoyait tout le pavé (les 3 comptes, le
                    # compte 3 « il publie », le lien sans dire où le mettre) à tout nouveau 15 min après son étape 1. Il ne fait plus
                    # que créer le lien, sans message, quand le parcours en est au lien (étape 6 ou plus) ou n'a pas commencé ;
                    # pendant la création des comptes (étapes 1 à 5), c'est l'étape 3 qui crée le lien.
                    try:
                        import parcours                                     # import tardif : parcours importe onboarding
                        fiche_pr = parcours._lire().get(str(uid_r)) or {}
                        etape_r = int(fiche_pr.get("etape", 0) or 0)
                        du_r, dire_r = parcours.lien_du(fiche_pr), parcours.lien_a_dire(fiche_pr)
                    except Exception:                                       # noqa: BLE001
                        etape_r, du_r, dire_r = 0, False, False
                    if etape_r >= 1 and not du_r:                           # 08/10 : dû dès le compte privé (le 2 pour les nouveaux)
                        continue
                    essai = str(fiche_r.get("lien_essai") or "")
                    if essai and essai > (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(timespec="seconds"):
                        continue                                            # un essai toutes les 6 h au plus (clone refusé : forfait plein)
                    etat_e = _lire_etat()
                    if uid_r in etat_e.get("clippers", {}):
                        etat_e["clippers"][uid_r]["lien_essai"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        _ecrire_etat(etat_e)
                    try:
                        # créer un clone seulement quand le lien est dû (étape 6 ou plus) : le forfait GAML est presque plein
                        res_r = await attribuer_lien(m_r, fiche_r["creatrice"], comptes, None, creer=du_r)
                        relances += 1
                        journal.info("Lien GAML retenté pour %s : %s", uid_r, (res_r.get("lien") or "aucun")[:120])
                        salon_r = _deps["salon_perso"](uid_r) if (res_r.get("lien") and dire_r and _deps.get("salon_perso")) else None
                        if salon_r is not None:
                            await salon_r.send(f"🔗 {m_r.mention} **Ton lien est prêt** : {res_r['lien']}\n\n"
                                               "Il va seulement dans la bio de ton compte privé.")
                    except Exception as erreur:                             # noqa: BLE001
                        journal.warning("Lien GAML retenté pour %s : %s", uid_r, erreur)
                etat = _lire_etat()
            try:
                if await drives_manquants(client):                      # 28/09 : le Drive manquant arrive au passage suivant
                    etat = _lire_etat()
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Drives manquants : %s", erreur)
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
                # 01/10 (Ricado, Ricardo, Clarisse : accès déjà livrés renvoyés, futur compte 3 présenté « Compte 1 », 3 accès
                # d'un coup) : seuls les identifiants absents de sa fiche sont nouveaux ; ils s'ajoutent DANS L'ORDRE (plus de
                # tri : le parcours lit compte 1, 2, 3 dans cet ordre) avec leurs accès ; un clipper en plein parcours
                # (étapes 1 à 6) ne reçoit rien ici, le parcours les lui donne un par un, l'admin a une ligne.
                fiche = etat["clippers"].setdefault(str(membre.id), {})
                # 05/10 (doublons « mêmes identifiants » vus dans les salons) : la fiche peut porter « @x » ou une URL d'avant la
                # normalisation ; comparés normalisés des deux côtés, et un accès déjà livré n'est jamais renvoyé
                deja = {normaliser_handle(h).lower() for h in fiche.get("comptes", [])} | \
                       {normaliser_handle(a.get("handle")).lower() for a in fiche.get("acces") or [] if isinstance(a, dict)}
                a_livrer = sorted([c for c in nouveaux if normaliser_handle(c["handle"]).lower() not in deja], key=_est_prive)
                try:
                    import parcours                                     # import tardif : parcours importe onboarding
                    etape_p = int((parcours._lire().get(str(membre.id)) or {}).get("etape", 0) or 0)
                except Exception:                                       # noqa: BLE001
                    etape_p = 0
                en_parcours = 1 <= etape_p <= 6
                if a_livrer and not en_parcours:
                    salon = deps["salon_perso"](str(membre.id))
                    cible = salon if salon is not None else membre
                    try:
                        await cible.send(("🔐 **Compte(s) attribué(s) depuis le classeur**\n\n" +
                                          message_comptes(a_livrer, prenom, creatrice or "?", debut=len(deja) + 1))[:1990])
                    except (discord.Forbidden, discord.HTTPException) as erreur:
                        journal.warning("Livraison classeur %s : %s", membre.display_name, erreur)
                        continue
                for c in nouveaux:                                      # déjà dans sa fiche : seulement noté livré, sans message
                    etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                fiche["comptes"] = list(fiche.get("comptes", [])) + [c["handle"] for c in a_livrer]
                connus = {str(a.get("handle", "")).lower() for a in fiche.get("acces") or [] if isinstance(a, dict)}
                fiche["acces"] = list(fiche.get("acces") or []) + [a for a in acces_ordonnes(a_livrer) if a["handle"].lower() not in connus]
                _ecrire_etat(etat)
                if not a_livrer:
                    continue
                if creatrice and roster.actif() and not roster.est_actif(prenom):   # 27/09 : Georgial servi par le classeur, absent du roster
                    try:
                        roster.ajouter(creatrice.split()[0], prenom)
                    except Exception as erreur:                         # noqa: BLE001
                        journal.warning("Roster (télécommande) : %s", erreur)
                canal = await deps["canal_admin"]()
                if canal:
                    if en_parcours:
                        await canal.send(f"🔐 {len(a_livrer)} compte(s) du classeur ajouté(s) à la fiche de {membre.mention} (colonne Gérant) : "
                                         f"rien posté, son parcours est à l'étape {etape_p} et donne chaque accès à son tour.")
                    else:
                        await canal.send(f"🔐 {len(a_livrer)} compte(s) du classeur livré(s) à {membre.mention} (colonne Gérant).")
        except Exception as erreur:                                 # la boucle ne meurt jamais
            journal.warning("Boucle onboarding : %s", erreur)
        try:
            await liens_classeur()                                      # 27/09 : Gérant changé à la main → lien GAML de la ligne à jour
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Colonne Lien GAML (boucle) : %s", erreur)
        try:                                                            # 09/10 (dashboard) : contrôle d'attribution, après les liens ;
            import controle                                             # salon admin seulement si l'empreinte change (import tardif :
            await controle.passage(deps)                                # controle importe onboarding)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Contrôle d'attribution (boucle) : %s", erreur)
        await asyncio.sleep(900)


async def rattraper_acces(client) -> int:
    """01/10 (relecture : les comptes livrés depuis le classeur avant la fusion n'ont ni accès dans la fiche ni alias au
    registre — avec CODES_PUSH_SALON_PERSO=0, `!code` au salon commun ne trouvait jamais leurs codes) : au démarrage, une
    passe, un seul appel au classeur. Chaque compte de « comptes » absent de « acces » y est ajouté (dans l'ordre de la
    fiche, donc sans changer la numérotation), et son adresse est rattachée au salon perso si personne ne l'a déjà.
    `cree` reste faux, comme avant le rattrapage : l'étape garde son texte et le scan peut toujours la fermer.
    Renvoie le nombre d'accès ajoutés."""
    await client.wait_until_ready()
    if not actif():
        return 0
    try:
        lignes = await lire_comptes()
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Rattrapage des accès : classeur illisible (%s)", erreur)
        return 0
    par_handle = {str(c.get("handle") or "").lower(): c for c in lignes if c.get("handle")}
    etat = _lire_etat()                                                 # lu APRÈS l'appel au classeur, écrit sans attente
    ajoutes, a_rattacher = 0, []
    for uid, fiche in etat["clippers"].items():
        if not isinstance(fiche, dict):
            continue
        connus = {str(a.get("handle", "")).lower() for a in fiche.get("acces") or [] if isinstance(a, dict)}
        manquants = [par_handle[str(h).lower()] for h in fiche.get("comptes") or []
                     if h and str(h).lower() not in connus and str(h).lower() in par_handle]
        if not manquants:
            continue
        fiche["acces"] = list(fiche.get("acces") or []) + [dict(acces_ordonnes([c])[0], cree=False) for c in manquants]
        ajoutes += len(manquants)
        a_rattacher.append((uid, [c["mail"] for c in manquants if c.get("mail")]))
    if not ajoutes:
        return 0
    _ecrire_etat(etat)
    if codes_2fa.actif():
        registre = codes_2fa._lire()
        for uid, mails in a_rattacher:
            salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
            libres = [m for m in mails if str(m).strip().lower() not in registre]
            if salon is not None and libres:
                try:
                    codes_2fa.rattacher(libres, str(salon.id), "onboarding")
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Rattrapage des alias de %s : %s", uid, erreur)
    journal.info("Rattrapage des accès : %d compte(s) ajouté(s) à %d fiche(s)", ajoutes, len(a_rattacher))
    return ajoutes


# ------------------------------------------------------------------ commande
async def changer_gerant(ancien: str, nouveau: str) -> list:
    """09/10 (Gaëtan : « Rianah reprend ses liens Metricool ») : les lignes dont le Gérant est exactement `ancien` (« Julien
    (Metricool) ») passent à `nouveau` (« Rianah (Metricool) »), tous onglets. L'Utilisation ne bouge pas. Renvoie une ligne de
    bilan par compte (sans mot de passe)."""
    if not _norm(ancien) or _norm(ancien) == _norm(nouveau):
        return []
    lignes = [c for c in await lire_comptes() if _norm(c["gerant"]) == _norm(ancien)]
    for c in lignes:
        await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, cellule(c, "gerant"), [[nouveau]])
    return [f"· `{c['handle']}` ({c['etat'] or 'état ?'}) → Gérant {nouveau}" for c in lignes]


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
            # 01/10 (relecture : l'accès restait dans « acces », et `!code` au salon commun donnait encore les codes de ce
            # compte à l'ancien clipper) : l'accès part avec le compte
            if any(isinstance(a, dict) and str(a.get("handle", "")).lower() == h for a in fiche.get("acces") or []):
                fiche["acces"] = [a for a in fiche["acces"] if not (isinstance(a, dict) and str(a.get("handle", "")).lower() == h)]
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
