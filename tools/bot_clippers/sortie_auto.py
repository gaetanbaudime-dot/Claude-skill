"""Sortie automatique (28/09, feu vert de Gaëtan : « code-le, et réattribue comptes et liens au suivant »).

30/09 (Gaëtan, GO : « un avertissement automatique à 3 jours, puis la sortie à 7 jours », règle 5 : 3 jours sans publier =
licenciement) : le compteur n'est plus « jamais publié depuis 14 jours » mais « jours depuis la DERNIÈRE publication » (ou depuis
la créatrice s'il n'a jamais publié). À AVERT_JOURS (3) : un message dans son salon perso, une fois par silence, avec la date de
sortie. À JOURS (7) : la sortie ci-dessous. Une publication = une hausse du nombre de publications d'un de ses comptes entre deux
scans (ou la première valeur d'un compte vu après son arrivée : un compte rendu garde les Reels du clipper d'avant). Il faut au
moins SCANS_MIN jours de scan où un de ses comptes existe pendant le silence : un compte banni ou un scan en panne ne fait sortir
personne. Personne n'est averti ni sorti pour un silence antérieur à REGLE_DEPUIS (30/09) : premières sorties possibles le 07/10.

Texte d'origine (14/09 → 29/09) :

Chaque jour à SORTIE_AUTO_HEURE_UTC (8 h, après le scan Apify du classeur) : un clipper signé avec une créatrice depuis au
moins SORTIE_AUTO_JOURS jours (14), dont les comptes ont été regardés au moins SCANS_MIN fois (7) et n'ont JAMAIS porté une
publication, est sorti comme par `!sortie` : rôles et accès retirés, registre tracé, roster à jour — mais ses comptes créés
restent dans le vivier (Gérant vidé, état GOOD/WARMUP gardé) et son lien GAML est libéré : le prochain clipper de la même
créatrice les reçoit, avec l'e-mail rattaché à son salon pour que le code de CONNEXION arrive chez lui.

Ne touche jamais : le staff, les anciens gérés par Jonas (`sans_salon` du roster), un clipper sans données de scan, un clipper
dont une note du manager contient « garde ». `SORTIE_AUTO=0` éteint. `!sortie-auto` (admin) : liste ce qui partirait ;
`!sortie-auto go` : l'applique maintenant. Le module ne connaît pas bot_discord : dépendances dans `configurer(deps)`.

10/10 (ménage L9a) : l'ancienne règle « 7 jours sans Reel » (executer_sans_reel, a_sortir, a_avertir, `!sortie-auto reels`) est
supprimée ; `silences` et `jours_sans_reel` restent pour les bloqués du matin. Le calcul des visites GAML vit ici (`visites`, avant
dans appel.py) : la règle du compte 1 ne dépend plus de l'appel de présence. `mesures` et `compte_lu` disent si le scan a LU les
comptes d'un clipper : sans relevé récent, il est « non mesuré », jamais inactif (l'appel de présence ne sort personne sur un scan
coupé, un compte restreint ou un passage raté).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("sortie_auto")

# 05/10 (Gaëtan, après l'audit du bot : « règle expulsion oui, juste 3 jours sans compte créé ») : UNE règle, à la place des trois
# horloges (réservation 48 h, 3 j sans Reel, 7 j sans Reel). Un clipper dont le compte 1 est ouvert dans son salon depuis
# SORTIE_JOURS_COMPTE1 jours sans être créé (étape 1 jamais fermée) : un avertissement la veille (J-1), puis la sortie : rôles et
# accès retirés, salon perso supprimé, parcours oublié, comptes et lien au vivier, et il est EXPULSÉ du serveur (SORTIE_KICK=1).
# Le compteur ne commence jamais avant SORTIE_COMPTE1_DEPUIS (la règle annoncée) : personne n'est sorti pour un retard antérieur.
# Un clipper qui a créé son compte 1 mais ne publie pas n'est plus sorti tout seul : il n'obtient simplement pas le compte 2, et
# la liste des bloqués du matin le montre à Gaëtan. Les anciens compteurs restent lisibles (jours_sans_reel) pour cette liste.
ACTIF = os.environ.get("SORTIE_AUTO", "1").strip() != "0"
# 08/10 (audit : « 3 jours » annoncé, purge à 48 h sans prévenir) : la règle suit la dernière consigne de Gaëtan (05/10, 15 h 30 :
# « donne-leur 48 h ») — avertissement à 24 h, sortie à 48 h, et le même chiffre dans tous les textes.
# 23/10 (règle L6 des règles gelées, confirmée par Gaëtan : « la règle L6, c'est très bien ») : compte 1 non créé 48 h après sa remise →
# UN avertissement ; sortie 48 h après l'AVERTISSEMENT (pas avant, jamais sans lui). La sortie reste validée par le manager
# (RETRAIT_AUTOMATIQUE éteint) : le bot signale, `!sortie` exécute. Les chiffres sont fixés ici, plus lus dans Railway (la variable
# SORTIE_JOURS_COMPTE1 n'a plus d'effet : une valeur oubliée là-bas aurait défait la règle gelée sans que personne le voie).
AVERTIR_APRES_H = 48                                                    # remise du compte 1 → avertissement
SORTIE_APRES_AVERTISSEMENT_H = 48                                       # avertissement → sortie (validée)
TOLERANCE_PASSE_H = 2                                                   # la passe quotidienne ne tombe pas à la minute : 46 h valent 48 h
JOURS_AVERTIR = AVERTIR_APRES_H // 24
JOURS_COMPTE1 = (AVERTIR_APRES_H + SORTIE_APRES_AVERTISSEMENT_H) // 24  # 4 jours au plus entre la remise et la sortie
KICK = os.environ.get("SORTIE_KICK", "1").strip() != "0"
# Scheduled first-account checks only alert managers; no automatic release or kick.
RETRAIT_AUTOMATIQUE = os.environ.get("SORTIE_AUTO_RETRAIT", "0").strip() == "1"
COMPTE1_DEPUIS = os.environ.get("SORTIE_COMPTE1_DEPUIS", "2026-10-05")
HEURE_UTC = int(os.environ.get("SORTIE_AUTO_HEURE_UTC", "8") or 8)
REGLE_DEPUIS = os.environ.get("SORTIE_AUTO_DEPUIS", "2026-09-30")
# 10/10 (L9a) : recopié d'appel.py (même variable) : au-dessous de ce seuil sur 48 h, ce sont nos propres clics de contrôle
VISITES_ACTIF = int(os.environ.get("APPEL_VISITES_ACTIF", "5") or 5)
# 10/10 (L9a) : un relevé du scan plus vieux que MESURE_JOURS jours ne mesure plus rien (budget Apify coupé, passage raté)
MESURE_JOURS = int(os.environ.get("APPEL_MESURE_JOURS", "1") or 1)
RAISON_COMPTE1 = f"compte 1 non créé {SORTIE_APRES_AVERTISSEMENT_H} h après l'avertissement (règle L6)"
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_EQUIPES, etats_lire (-> etats_comptes.json), comptes_lire (async ->
    lignes du classeur), notes (uid -> [textes]), sortir (async membre, raison, pool), membre_par_id, prenom_de, roster, canal_admin,
    normaliser, heure_paris, salon_perso (uid -> salon, 30/09 : l'avertissement)."""
    _deps.update(deps)


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _jour(iso) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(iso)[:19])
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def debut_de(fiche: dict, onboarding: dict, uid: str) -> datetime | None:
    """Le point de départ des 14 jours : le plus récent entre l'attribution de la créatrice et la livraison des comptes."""
    dates = [fiche.get("creatrice_date"), fiche.get("date"), (onboarding.get("clippers", {}).get(str(uid)) or {}).get("date")]
    dates = [d for d in (_jour(x) for x in dates) if d is not None]
    return max(dates) if dates else None


def derniere_publication(handles: set, historique: dict, debut: datetime):
    """(jour de la dernière publication vue sur ses comptes ou None, jours de scan où un compte existe {date})."""
    derniere, jours_scan = None, set()
    for h in handles:
        prec = None
        for e in sorted(historique.get(h, []) or [], key=lambda x: str(x.get("jour", ""))):
            j = _jour(e.get("jour"))
            if j is None or not e.get("existe"):
                continue
            if e.get("restreint") and not e.get("posts"):               # 30/09 : compte restreint, Reels illisibles : ni scan ni silence
                continue
            if e.get("prive"):                                          # 07/10 : le compte 3 privé ne publie jamais, par règle (05/10)
                continue
            jours_scan.add(j.date())
            posts = int(e.get("posts") or 0)
            publie = (posts > prec) if prec is not None else (posts > 0 and j >= debut.replace(hour=0, minute=0, second=0, microsecond=0))
            if publie and (derniere is None or j > derniere):
                derniere = j
            prec = posts
    return derniere, jours_scan


def silences(fiches: dict, onboarding: dict, historique: dict, comptes: list, notes, prenom_de, maintenant=None,
             garder=(), depuis: str = None) -> list:
    """[(uid, prénom, jours sans publier, jours de scan pendant le silence, référence du silence)] pour chaque clipper signé
    avec une créatrice, hors note « garde » et prénoms protégés. La référence = dernière publication, sinon le début ; jamais
    avant `depuis` (REGLE_DEPUIS)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    borne = _jour((depuis or REGLE_DEPUIS) + "T00:00:00")
    proteges = {_n(p) for p in garder}
    par_prenom = {}
    for c in comptes:
        g = _n(c.get("gerant") or "")
        if g and c.get("handle"):
            par_prenom.setdefault(g, []).append(str(c["handle"]).lower())
    out = []
    for uid, fiche in fiches.items():
        if not fiche.get("creatrice"):
            continue
        prenom = prenom_de(uid) or ""
        if not prenom or _n(prenom) in proteges:
            continue
        debut = debut_de(fiche, onboarding, uid)
        if debut is None:
            continue
        if any("garde" in _n(t) for t in (notes(uid) if notes else [])):
            continue
        handles = set(par_prenom.get(_n(prenom), [])) | {str(h).lower() for h in (onboarding.get("clippers", {}).get(str(uid)) or {}).get("comptes", [])}
        # 07/10 (Caroline, Yves : trafic tous les jours, « aucun Reel depuis 5 j » dans le bilan) : un compte restreint cache ses
        # Reels au scan ; tant qu'un de ses comptes l'est, le clipper n'est pas mesurable → ni avertissement ni sortie sur les Reels.
        if any(((historique.get(h) or [{}])[-1] or {}).get("restreint") for h in handles):
            continue
        derniere, jours_scan = derniere_publication(handles, historique, debut)
        ref = max(d for d in (derniere, debut, borne) if d is not None)
        silence = (maintenant - ref).days
        scans = sum(1 for j in jours_scan if j > ref.date())
        out.append((str(uid), prenom, silence, scans, ref))
    return out


def _etat() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {"sorties": {}})


async def jours_sans_reel() -> dict:
    """{uid: jours sans Reel} de chaque clipper signé avec une créatrice (30/09 : la liste des bloqués du matin)."""
    fiches = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    onboarding = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}) if _deps.get("FICHIER_ONBOARDING") else {}
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    comptes = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []

    def prenom_de(uid):
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        return _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""
    return {uid: jours for uid, _, jours, _, _ in silences(fiches, onboarding, historique, comptes, _deps.get("notes"), prenom_de)}


# ------------------------------------------------------------------ mesuré ou non (10/10, L9a, amendement B)
def _cle_compte(h) -> str:
    """La clé d'un compte dans l'historique du scan (comme etats_comptes._cle) : identifiant nettoyé, en minuscules."""
    try:
        import onboarding as _onb_mod
        return _onb_mod.normaliser_handle(str(h or "")).lower()
    except Exception:                                                   # noqa: BLE001
        return str(h or "").strip().lstrip("@").lower()


def lu_recemment(handles, historique: dict, maintenant=None, jours: int = None, reels: bool = True) -> bool:
    """Le scan a-t-il lu au moins un de ces comptes depuis `jours` jours (MESURE_JOURS) ? reels=True : un relevé où ses Reels se
    lisent (compte existant, ni privé, ni restreint, Reels lus) ; reels=False : n'importe quel relevé, « introuvable » compris
    (un compte jamais créé se mesure aussi). Aucun relevé récent : rien n'est mesuré."""
    maintenant = maintenant or datetime.now(timezone.utc)
    borne = (maintenant - timedelta(days=MESURE_JOURS if jours is None else jours)).date()
    for h in handles or ():
        for e in (historique or {}).get(_cle_compte(h), []) or []:
            j = _jour(e.get("jour"))
            if j is None or j.date() < borne:
                continue
            if not reels:
                return True
            if e.get("existe") and not e.get("prive") and not e.get("restreint") and not e.get("reels_non_lus"):
                return True
    return False


def mesure(handles, historique: dict, maintenant=None, jours: int = None) -> bool:
    """Un clipper est « mesuré » si un de ses comptes publics a un relevé lisible récent et qu'aucun de ses comptes n'est restreint
    au dernier relevé (un restreint cache ses Reels, comme dans `silences`). Sinon : « non mesuré », jamais inactif.
    11/10 (lot W, contre-vérification du lot L9a : un vieux compte banni ou sorti du classeur, « restreint » à son dernier relevé
    d'il y a 20 jours, rendait le clipper « non mesuré » pour toujours, et l'appel ne le visait plus jamais) : seul un « restreint »
    relevé depuis moins de MESURE_JOURS jours (la même fenêtre que la mesure) compte."""
    maintenant_ = maintenant or datetime.now(timezone.utc)
    borne = (maintenant_ - timedelta(days=MESURE_JOURS if jours is None else jours)).date()
    for h in handles or ():
        dernier = ((historique or {}).get(_cle_compte(h)) or [{}])[-1] or {}
        if dernier.get("restreint"):
            j = _jour(dernier.get("jour"))
            if j is None or j.date() >= borne:                          # date illisible : prudence, non mesuré
                return False
    return lu_recemment(handles, historique, maintenant, jours, reels=True)


async def mesures(maintenant=None) -> dict:
    """{uid: True/False} pour chaque fiche du registre : son activité Instagram est-elle mesurée par le scan ? Ses comptes : ceux
    du classeur à son prénom (colonne Gérant) et ceux qui lui ont été livrés. Une erreur de lecture remonte à l'appelant (l'appel
    de présence n'appelle alors personne)."""
    fiches = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    onboarding = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}) if _deps.get("FICHIER_ONBOARDING") else {}
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    comptes = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []
    par_prenom = {}
    for c in comptes:
        g = _n(c.get("gerant") or "")
        if g and c.get("handle"):
            par_prenom.setdefault(g, []).append(str(c["handle"]))
    out = {}
    for uid in fiches:
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        prenom = _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""
        handles = (par_prenom.get(_n(prenom), []) if prenom else []) + list((onboarding.get("clippers", {}).get(str(uid)) or {}).get("comptes", []))
        out[str(uid)] = mesure(handles, historique, maintenant)
    return out


def compte_lu(handles, maintenant=None) -> bool:
    """Un de ces comptes a-t-il un relevé récent du scan (existant ou introuvable) ? La purge de l'appel ne sort personne sans."""
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    return lu_recemment(handles, historique, maintenant, reels=False)


def compte1_prouve(uid: str, ouverture, onboarding_d: dict, historique: dict) -> bool:
    """08/10 (Mohamed : averti « compte 1 pas créé, sortie demain » alors que ses comptes 1 et 2 existaient et qu'il publiait ; il
    n'avait jamais appuyé sur le bouton, et le pseudo prévu d'un compte était pris) : le scan Instagram vaut le bouton. Preuve :
    un Reel publié depuis l'ouverture de l'étape 1 sur un de ses comptes livrés (reels_hier d'un scan postérieur), ou son compte 1,
    livré « à créer », vu existant depuis. Un compte repris d'un sortant existait déjà : son existence seule ne prouve rien."""
    import onboarding as _onb_mod
    import parcours as _parcours
    onb = ((onboarding_d or {}).get("clippers", {}) or {}).get(str(uid)) or {}
    handles = [h for h in _parcours._comptes_ordonnes(uid, onb) if h]
    neufs = {str(a.get("handle") or "").lower() for a in onb.get("acces") or [] if isinstance(a, dict) and not a.get("cree")}
    jour0 = ouverture.date() if ouverture is not None else None
    for i, h in enumerate(handles):
        for e in (historique or {}).get(_onb_mod.normaliser_handle(h).lower(), []):
            try:
                j = datetime.fromisoformat(str(e.get("jour", ""))[:10]).date()
            except ValueError:
                continue
            if jour0 is None or j < jour0 or not e.get("existe"):
                continue
            if j > jour0 and int(e.get("reels_hier") or 0) > 0:
                return True
            if i == 0 and str(h).lower() in neufs:
                return True
    return False


def compte1_bloque(uid: str, onboarding_d: dict, etats_classeur) -> str:
    """08/10 (critique de l'audit) : le clipper ne PEUT pas créer son compte 1 → jamais « 48 h sans compte créé ». Renvoie la
    raison, '' sinon : aucun compte livré (vivier vide à la livraison, identifiant « ? ») ou compte 1 passé BAN au classeur
    (banni à la création, relevé des bans par mail). `etats_classeur` = {handle normalisé: état} ou None (classeur illisible)."""
    import onboarding as _onb_mod
    import parcours as _parcours
    onb = ((onboarding_d or {}).get("clippers", {}) or {}).get(str(uid)) or {}
    handles = [h for h in _parcours._comptes_ordonnes(uid, onb) if h and str(h).strip("@ ?")]
    if not handles:
        return "aucun compte livré (vivier vide ?)"
    if etats_classeur and _n(etats_classeur.get(_onb_mod.normaliser_handle(handles[0]).lower(), "")) == "ban":
        return "compte 1 BAN au classeur"
    return ""


def visites(uid: str, jours: int) -> int:
    """08/10 : visiteurs (hors robots) sur ses liens GAML les `jours` derniers jours, hier compris ; 0 sans paie au clic.
    10/10 (L9a) : déplacé d'appel.py, qui s'en sert encore. Lecture seule de paie_clics (actif, _lire, liens_de, somme)."""
    try:
        import paie_clics                                               # import tardif : la sortie ne dépend pas de la paie
        if not paie_clics.actif():
            return 0
        d = paie_clics._lire()
        lids = paie_clics.liens_de(d, str(uid))
        if not lids:
            return 0
        hier = datetime.now(timezone.utc).date() - timedelta(days=1)
        return int(paie_clics.somme(d, lids, hier - timedelta(days=max(int(jours), 1) - 1), hier).get("hors_robots", 0) or 0)
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Visites de %s illisibles : %s", uid, erreur)
        return 0


# 18/10 (Gaëtan, règles gelées L7 : « 0 visite payée pendant 10 jours d'affilée = sortie ») : la liste part chaque matin dans le
# digest, avec la commande à taper. Comme le compte 1 (SORTIE_AUTO_RETRAIT=0), aucune expulsion n'est automatique : un lien dont la
# carte a sauté ou un relevé GAML en panne ne doit jamais faire sortir quelqu'un sans un regard humain. Un lien attribué depuis moins
# de INACTIF_JOURS jours n'est pas jugé. SORTIE_INACTIF_JOURS=0 coupe la liste.
INACTIF_JOURS = int(os.environ.get("SORTIE_INACTIF_JOURS", "10") or 0)


def infos_lids(paie_clics, d, uid) -> list:
    return list(paie_clics.liens_de(d, uid))


def inactifs(maintenant=None) -> list:
    """[(uid, nom)] des clippers dont tous les liens GAML (attribués depuis au moins INACTIF_JOURS jours) n'ont ramené aucune visite
    payée (paie_clics.payees, la mesure de la paie) sur les INACTIF_JOURS derniers jours, hier compris. Lecture seule ; [] sans paie
    au clic ou en cas de panne."""
    if INACTIF_JOURS <= 0:
        return []
    try:
        import paie_clics                                               # import tardif : la sortie ne dépend pas de la paie
        if not paie_clics.actif():
            return []
        d = paie_clics._lire()
        maintenant = maintenant or datetime.now(timezone.utc)
        hier = maintenant.date() - timedelta(days=1)
        debut = hier - timedelta(days=INACTIF_JOURS - 1)
        out = []
        for uid in sorted({str(i.get("uid")) for i in d.get("liens", {}).values() if i.get("uid")}):
            infos = [d["liens"][lid] for lid in paie_clics.liens_de(d, uid)]
            if not infos or min(str(i.get("depuis") or "9999-12-31")[:10] for i in infos) > debut.isoformat():
                continue
            nom = next((str(i.get("note") or "")[len("Clipping "):].strip() for i in infos
                        if str(i.get("note") or "").startswith("Clipping ")), "") or uid
            if str(nom or "").strip().lower() in paie_clics.CLICS_EXCLURE:
                continue
            # 18/10 (Caroline, Josué, Lilian, Yves listés « 10 jours sans visite payée » : ils sont au FIXE, leurs visites payées
            # au clic valent 0 par construction, Caroline est la première productrice) : la règle lit les visites qui comptent de
            # leurs liens (francophones, hors robots), quel que soit le régime de paie.
            if paie_clics.payees(d, uid, debut, hier) > 0 or paie_clics.somme(d, infos_lids(paie_clics, d, uid), debut, hier)["payes"] > 0:
                continue
            out.append((uid, nom or uid))
        return out
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Inactifs %s j illisibles : %s", INACTIF_JOURS, erreur)
        return []


def _visites_actives(uid: str) -> bool:
    """08/10 (audit : un ancien rouvert aux comptes restreints n'a aucun Reel lisible) : son lien GAML ramène du monde sur 48 h.
    10/10 (L9a) : calculé ici, plus d'import d'appel (un import raté renvoyait Faux sans bruit et faisait sortir à 48 h)."""
    return visites(uid, 2) >= VISITES_ACTIF


def sans_compte1(parcours: dict, maintenant=None, depuis: str = None, garder=(), prenom_de=None, notes=None, prouve=None,
                 reprises: dict = None) -> list:
    """05/10 : [(uid, prénom, jours depuis l'ouverture du compte 1, référence iso)] pour chaque fiche de parcours à l'étape 1
    (ouverte, jamais fermée). La référence = la date d'ouverture de l'étape 1, jamais avant `depuis` (la règle annoncée).
    Protégés : prénoms de `garder` (anciens de Jonas), note « garde » du manager ; 08/10 : ceux dont le scan prouve le compte
    (`prouve(uid, ouverture)`, compte1_prouve)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    borne = _jour((depuis or COMPTE1_DEPUIS) + "T00:00:00")
    proteges = {_n(p) for p in garder}
    out = []
    for uid, fiche_p in (parcours or {}).items():
        if not isinstance(fiche_p, dict) or int(fiche_p.get("etape", 0) or 0) != 1:
            continue
        dates = fiche_p.get("dates") or {}
        if dates.get("1_fait") or (fiche_p.get("profils") or {}).get("1"):   # un premier signal (profil envoyé) = compte créé
            continue
        ouverture = _jour(dates.get("1"))
        if ouverture is None:
            continue
        prenom = (prenom_de(uid) if prenom_de else "") or fiche_p.get("prenom") or ""
        if not prenom or _n(prenom) in proteges:
            continue
        if any("garde" in _n(t) for t in (notes(uid) if notes else [])):
            continue
        try:
            if prouve is not None and prouve(str(uid), ouverture):
                continue
        except Exception as erreur:                                         # noqa: BLE001 — dans le doute, personne ne sort
            journal.warning("Preuve du compte 1 de %s illisible : %s", uid, erreur)
            continue
        # 08/10 (revue) : un clipper débloqué (compte enfin livré, BAN remplacé) repart de 48 h pleines, avertissement compris
        ref = max(d for d in (ouverture, borne, _jour((reprises or {}).get(str(uid)))) if d is not None)
        out.append((str(uid), prenom, (maintenant - ref).days, ref.isoformat(timespec="seconds")))
    return out


def _instant(brut):
    """Un instant iso lu en UTC, None s'il est absent ou illisible."""
    try:
        v = datetime.fromisoformat(str(brut))
    except (TypeError, ValueError):
        return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def _heures_depuis(brut, maintenant) -> float:
    """Heures écoulées depuis l'instant `brut` ; 0 s'il est illisible (dans le doute, rien ne part)."""
    v = _instant(brut)
    return 0.0 if v is None else (maintenant - v).total_seconds() / 3600


def _averti(uid, ref, deja: dict, quand) -> bool:
    """Averti POUR CETTE RÉFÉRENCE et, depuis le 23/10, avec l'instant de l'avertissement : un avertissement d'avant (texte sans
    échéance, aucun instant gardé) ne compte pas, le clipper reçoit l'avertissement de L6 avant toute sortie."""
    if deja.get(uid) != ref:
        return False
    return quand is None or _instant(quand.get(uid)) is not None


def a_avertir_compte1(parcours: dict, deja: dict, maintenant=None, quand: dict = None, **kw) -> list:
    """L6 : ceux dont le compte 1 n'est pas créé 48 h après sa remise (AVERTIR_APRES_H, à TOLERANCE_PASSE_H près), pas encore avertis
    pour cette référence. « Ou plus » : un clipper déjà au-delà est averti d'abord, il ne sort jamais sans avertissement.
    `quand` = les instants d'avertissement (`avertis_compte1_le`) ; sans lui, seule la référence compte (appels d'avant le 23/10)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    return [(u, p, j, ref) for u, p, j, ref in sans_compte1(parcours, maintenant, **kw)
            if _heures_depuis(ref, maintenant) >= AVERTIR_APRES_H - TOLERANCE_PASSE_H and not _averti(u, ref, deja, quand)]


def a_sortir_compte1(parcours: dict, maintenant=None, deja: dict = None, quand: dict = None, **kw) -> list:
    """L6 : ceux avertis pour cette référence il y a SORTIE_APRES_AVERTISSEMENT_H heures ou plus (à TOLERANCE_PASSE_H près), et
    toujours sans compte 1. `deja` + `quand` = les avertis et leurs instants lus AVANT la passe : un clipper averti dans cette
    passe ne sort pas dans la même. Sans `deja` (appel d'avant le 23/10) : JOURS_COMPTE1 jours depuis la remise suffisent."""
    maintenant = maintenant or datetime.now(timezone.utc)
    sortants = []
    for u, p, j, ref in sans_compte1(parcours, maintenant, **kw):
        if deja is None:
            if j >= JOURS_COMPTE1:
                sortants.append((u, p, j, ref))
            continue
        if not _averti(u, ref, deja, quand):
            continue
        if quand is not None and _heures_depuis(quand.get(u), maintenant) < SORTIE_APRES_AVERTISSEMENT_H - TOLERANCE_PASSE_H:
            continue
        sortants.append((u, p, j, ref))
    return sortants


def texte_avertissement_compte1(prenom: str, jours: int) -> str:
    """L6, en phrases courtes : l'échéance est dite, le recours aussi (compte déjà créé, blocage)."""
    return (f"⚠️ {prenom}, ton compte 1 n'est toujours pas créé.\n\n"
            f"Il t'a été remis il y a {jours} jours.\n\n"
            f"Crée-le dans les {SORTIE_APRES_AVERTISSEMENT_H} h, puis valide ton étape.\n\n"
            "Tu l'as déjà créé ? Écris-le ici, je mets ton suivi à jour.\n\n"
            "Bloqué ? Écris à Gaëtan sur WhatsApp.\n\n"
            f"Pas de compte 1 dans {SORTIE_APRES_AVERTISSEMENT_H} h ? Ton manager valide ta sortie du serveur.")


async def executer(client, appliquer: bool = True) -> list:
    """Un passage. 05/10 : la règle unique du compte 1 (avertissement à J-1, sortie + expulsion à J). Renvoie les lignes du bilan."""
    if not ACTIF and appliquer:
        return []
    roster = _deps.get("roster")
    garder = list(roster.lire().get("sans_salon", [])) if roster is not None else []
    parcours = _deps["parcours_lire"]() if _deps.get("parcours_lire") else {}

    def prenom_de(uid):
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        return _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""

    bilan = []
    d = _etat()
    onboarding_d = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}) if _deps.get("FICHIER_ONBOARDING") else {}
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    try:
        import onboarding as _onb_mod
        lignes_c = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []
        etats_classeur = {_onb_mod.normaliser_handle(c.get("handle") or "").lower(): str(c.get("etat") or "") for c in lignes_c if c.get("handle")}
    except Exception as erreur:                                         # noqa: BLE001 — sans classeur, seule la livraison est vérifiée
        journal.warning("Sortie compte 1 : classeur illisible (%s), BAN non vérifiés", erreur)
        etats_classeur = None
    bloques = {}
    instant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    deja_bloques = dict(d.get("bloques_compte1") or {})
    reprises = dict(d.get("reprise_compte1") or {})
    reprises_avant = dict(reprises)

    def _bloque(u):
        raison = compte1_bloque(u, onboarding_d, etats_classeur)
        if raison:
            bloques[str(u)] = raison
            reprises.pop(str(u), None)                                  # rebloqué : la prochaine reprise repartira de zéro
        elif str(u) in deja_bloques and str(u) not in reprises:
            reprises[str(u)] = instant                                  # débloqué : les 48 h partent d'ici
        return bool(raison)
    kw = {"garder": garder, "prenom_de": prenom_de, "notes": _deps.get("notes"), "reprises": reprises,
          "prouve": lambda u, ouv: _bloque(u) or compte1_prouve(u, ouv, onboarding_d, historique) or _visites_actives(u)}   # 08/10 : scan ou visites
    avertis_avant = dict(d.get("avertis_compte1", {}))                  # 08/10 : la sortie exige un avertissement d'une passe précédente
    avertis_le = dict(d.get("avertis_compte1_le", {}))                  # 23/10 (L6) : ... d'au moins 48 h
    for uid, prenom, nb_jours, ref in a_avertir_compte1(parcours, avertis_avant, quand=avertis_le, **kw):
        if not appliquer:
            bilan.append(f"· {prenom} : compte 1 pas créé depuis {nb_jours} j → avertissement L6 à envoyer (sortie {SORTIE_APRES_AVERTISSEMENT_H} h après)")
            continue
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        if salon is None:
            continue
        try:
            await salon.send(texte_avertissement_compte1(prenom, nb_jours))
            d = _etat()
            d.setdefault("avertis_compte1", {})[uid] = ref
            d.setdefault("avertis_compte1_le", {})[uid] = instant        # l'échéance de la sortie part de CET instant
            _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"⚠️ {prenom} : averti, sortie à valider dans {SORTIE_APRES_AVERTISSEMENT_H} h s'il n'a toujours pas créé son compte 1 ({nb_jours} j)")
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Avertissement compte 1 de %s : %s", prenom, erreur)
    for uid, prenom, nb_jours, ref in a_sortir_compte1(parcours, deja=avertis_avant, quand=avertis_le, **kw):
        if not appliquer:
            bilan.append(f"· {prenom} : compte 1 pas créé depuis {nb_jours} j → " + ("sortie possible" if RETRAIT_AUTOMATIQUE else "à vérifier par le manager (aucune sortie automatique)") + (" et expulsé" if (KICK and RETRAIT_AUTOMATIQUE) else ""))
            continue
        if not RETRAIT_AUTOMATIQUE:
            # A false negative in Instagram/Apify must not revoke a working clipper.
            d_revue = _etat()
            deja_signale = (d_revue.get("signalements_compte1") or {}).get(uid) == ref
            if not deja_signale:
                d_revue.setdefault("signalements_compte1", {})[uid] = ref
                _deps["ecrire_json"](_deps["FICHIER"], d_revue)
                bilan.append(f"👀 {prenom} : compte 1 pas créé depuis {nb_jours} j, validation manager requise (le bot ne sort "
                             "personne seul)")
            continue
        m = _deps["membre_par_id"](uid)
        if m is None:
            continue
        try:
            res = await _deps["sortir"](m, RAISON_COMPTE1, pool=True, expulser=KICK)
            d = _etat()
            d.setdefault("sorties", {})[uid] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "prenom": prenom,
                                                 "jours": nb_jours, "regle": "compte1", "expulse": bool(res.get("expulse"))}
            _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"🚪 {prenom} : sorti ({nb_jours} j sans compte 1)" + (" · expulsé" if res.get("expulse") else " · ⚠️ pas expulsé")
                         + f" · comptes rendus : {res.get('comptes', 0)} · lien libéré : {res.get('liens', 0)}"
                         + (f" · refus : {', '.join(res.get('refus') or [])}" if res.get("refus") else ""))
            journal.info("Sortie automatique (compte 1) : %s (%s) après %d jours", prenom, uid, nb_jours)
        except Exception as erreur:                                         # noqa: BLE001
            bilan.append(f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}")
            journal.warning("Sortie automatique de %s : %s", prenom, erreur)
    jour = datetime.now(timezone.utc).date().isoformat()
    d = _etat()
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else None
    for uid, raison in bloques.items():                                 # 08/10 : on ne sort pas, on dit au staff quoi débloquer
        if registre is not None and str(uid) not in registre:
            continue                                                    # sorti (sa fiche de parcours traîne) : rien à débloquer
        if (d.get("bloques_compte1") or {}).get(uid) == jour:
            continue
        bilan.append(f"🧱 {prenom_de(uid) or uid} (<@{uid}>) : {raison} → pas de sortie ; à débloquer (`!onboarding @…` ou un compte neuf)")
        if appliquer:
            d.setdefault("bloques_compte1", {})[uid] = jour
    if appliquer and (bloques or reprises != reprises_avant):
        d["reprise_compte1"] = reprises
        _deps["ecrire_json"](_deps["FICHIER"], d)
    return bilan


async def commande(message, texte: str) -> bool:
    """`!sortie-auto` : les comptes 1 à vérifier ; `!sortie-auto go` : appliquer les rappels."""
    if not texte.lower().startswith("!sortie-auto"):
        return False
    mots = texte.lower().split()[1:2]
    go = mots == ["go"]                                                 # 10/10 (L9a) : plus de `!sortie-auto reels` (ancienne règle)
    bilan = await executer(message.client if hasattr(message, "client") else None, appliquer=go)
    if not bilan:
        await message.reply(f"✅ Aucun compte 1 à relancer : aucun retard détecté depuis {AVERTIR_APRES_H} h."
                            + ("" if ACTIF else " Sortie automatique éteinte (`SORTIE_AUTO=0`)."))
        return True
    await message.reply((("🛡️ **Rappels et vérifications du compte 1**\n" if go else "🔎 **Comptes 1 à vérifier** (`!sortie-auto go` pour envoyer les rappels)\n")
                         + "\n".join(bilan))[:1990])
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Sortie automatique éteinte (SORTIE_AUTO=0)")
        return
    journal.info("Suivi compte 1 actif (L6) : avertissement à %d h après la remise, %s %d h après l'avertissement, à %d h UTC ; "
                 "référence à partir du %s",
                 AVERTIR_APRES_H, "sortie automatisée" if RETRAIT_AUTOMATIQUE else "revue humaine SANS sortie",
                 SORTIE_APRES_AVERTISSEMENT_H, HEURE_UTC, COMPTE1_DEPUIS)
    while not client.is_closed():
        maintenant = datetime.now(timezone.utc)
        d = _etat()
        jour = maintenant.strftime("%Y-%m-%d")
        if maintenant.hour >= HEURE_UTC and d.get("dernier") != jour:
            try:
                premiere = not d.get("dernier_compte1")                        # la première passe de la règle ne sort personne : liste seulement
                bilan = await executer(client, appliquer=not premiere)
                d = _etat(); d["dernier_compte1"] = jour; _deps["ecrire_json"](_deps["FICHIER"], d)
                d = _etat()
                d["dernier"] = jour
                if bilan and DIGEST:
                    # 10/10 (lot L9b, « un seul digest admin ») : le bilan attend le digest du matin (bilan_pour_digest), qui part
                    # juste après cette passe ; plus de message à part
                    d["a_dire"] = (list(d.get("a_dire") or []) + [{"jour": jour, "premiere": premiere, "lignes": bilan}])[-7:]
                _deps["ecrire_json"](_deps["FICHIER"], d)
                if bilan and not DIGEST and _deps.get("canal_admin"):
                    canal = await _deps["canal_admin"]()
                    if canal is not None:
                        entete = ("🔎 **Première liste : comptes 1 à vérifier** — revue humaine, aucune suppression d'accès.\n"
                                  if premiere else "🛡️ **Rappels et vérifications du compte 1**\n")
                        await canal.send((entete + "\n".join(bilan))[:1990])
            except Exception as erreur:                                     # noqa: BLE001
                journal.warning("Boucle de sortie automatique : %s", erreur)
        await asyncio.sleep(1800)


# ------------------------------------------------------------------ 10/10 : le bilan va au digest du matin
# Revue du recrutement (lot L9b, « un seul digest admin ») : la passe du jour garde son heure (HEURE_UTC, après le scan Instagram)
# mais ne poste plus rien ; son bilan (avertis, sortis, 🧱 à débloquer) attend dans sortie_auto.json (« a_dire ») et part dans le
# digest du matin (bot_discord.boucle_rappels), qui attend cette passe. DIGEST=0 : le message à part revient (retour arrière).
DIGEST = os.environ.get("DIGEST", "1").strip() != "0"


def passe_du_jour_faite(maintenant=None) -> bool:
    """La passe du jour (date UTC, comme la boucle) est faite, ou il n'y en aura pas (SORTIE_AUTO=0, module non configuré) : le
    digest n'a pas à l'attendre."""
    if not ACTIF or not _deps.get("FICHIER") or not _deps.get("lire_json"):
        return True
    maintenant = maintenant or datetime.now(timezone.utc)
    return _etat().get("dernier") == maintenant.astimezone(timezone.utc).strftime("%Y-%m-%d")


def bilan_pour_digest() -> tuple:
    """Le bloc « sortie automatique » du digest : ([lignes], [jours des passes dites]) ; ([], []) si aucune passe n'a rien à dire.
    Lecture seule : oublier_bilan_dit(jours) une fois le digest posté (un digest raté ne perd rien, une passe arrivée entre-temps
    non plus)."""
    if not _deps.get("FICHIER") or not _deps.get("lire_json"):
        return [], []
    a_dire = [x for x in (_etat().get("a_dire") or []) if isinstance(x, dict) and x.get("lignes")]
    dormants = inactifs()
    # 24/10 (« !sortie bab raison » refusé : Bab n'était plus sur le serveur) : un parti n'a pas de sortie à faire, seulement son
    # lien à libérer ; il a sa propre ligne, avec la commande qui marche pour lui.
    membre_de = _deps.get("membre_par_id")
    partis = [(uid, nom) for uid, nom in dormants if membre_de and membre_de(uid) is None]
    presents = [x for x in dormants if x not in partis]
    bloc_inactifs = ([f"😴 **0 visite payée depuis {INACTIF_JOURS} j** : "
                      + ", ".join(f"<@{uid}>" for uid, nom in presents[:25])
                      + ("…" if len(presents) > 25 else "")
                      + "\n-# `!sortie @x raison` pour le sortir, `!note @x garde` pour le garder."] if presents else [])
    if partis:
        bloc_inactifs.append("🧹 **Partis du serveur, lien encore à leur nom** : "
                             + " · ".join(f"{nom} `!lien {uid} retirer`" for uid, nom in partis[:10]))
    if not a_dire:
        return bloc_inactifs, []
    out = [f"🚪 **Sorties** (compte 1 : avertis à {AVERTIR_APRES_H} h, sortie {SORTIE_APRES_AVERTISSEMENT_H} h après)"]
    for x in a_dire:
        jour = str(x.get("jour") or "")
        if len(a_dire) > 1 and len(jour) == 10:
            out.append(f"-# Passe du {jour[8:10]}/{jour[5:7]}")
        if x.get("premiere"):
            out.append("🔎 Première liste : rien n'est fait aujourd'hui. Demain à la même heure, ces clippers sortent tout seuls "
                       "(`!sortie-auto go` pour le faire maintenant, `!note @x garde` pour en protéger un).")
        out.extend(str(ligne) for ligne in x["lignes"])
    return out + bloc_inactifs, [str(x.get("jour") or "") for x in a_dire]


def oublier_bilan_dit(jours) -> None:
    """Le digest est parti : les bilans des passes `jours` qu'il portait sont oubliés (les autres restent)."""
    if not _deps.get("FICHIER") or not _deps.get("lire_json") or not jours:
        return
    d = _etat()
    restent = [x for x in (d.get("a_dire") or []) if not (isinstance(x, dict) and str(x.get("jour") or "") in set(jours))]
    if restent:
        d["a_dire"] = restent
    else:
        d.pop("a_dire", None)
    _deps["ecrire_json"](_deps["FICHIER"], d)
