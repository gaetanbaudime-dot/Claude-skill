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
JOURS_COMPTE1 = int(os.environ.get("SORTIE_JOURS_COMPTE1", "3") or 3)
KICK = os.environ.get("SORTIE_KICK", "1").strip() != "0"
COMPTE1_DEPUIS = os.environ.get("SORTIE_COMPTE1_DEPUIS", "2026-10-05")
JOURS = int(os.environ.get("SORTIE_AUTO_JOURS", "7") or 7)                 # 30/09 : 14 → 7
AVERT_JOURS = int(os.environ.get("SORTIE_AUTO_AVERT_JOURS", "3") or 3)     # 30/09 : l'avertissement
SCANS_MIN = int(os.environ.get("SORTIE_AUTO_SCANS_MIN", "5") or 5)         # jours de scan pendant le silence (7 → 5 sur 7 jours)
HEURE_UTC = int(os.environ.get("SORTIE_AUTO_HEURE_UTC", "8") or 8)
REGLE_DEPUIS = os.environ.get("SORTIE_AUTO_DEPUIS", "2026-09-30")
RAISON = f"{JOURS} jours sans Reel (sortie automatique)"                     # ancienne règle (30/09), plus appliquée
RAISON_COMPTE1 = f"{JOURS_COMPTE1} jours sans créer ton compte 1 (règle de l'équipe)"
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


def a_sortir(fiches: dict, onboarding: dict, historique: dict, comptes: list, notes, prenom_de, maintenant=None,
             jours: int = JOURS, scans_min: int = SCANS_MIN, garder=(), depuis: str = None) -> list:
    """[(uid, prénom, jours sans publier, scans)] : silence ≥ `jours`, avec au moins `scans_min` jours de scan pendant le silence."""
    return [(u, p, j, s) for u, p, j, s, _ in silences(fiches, onboarding, historique, comptes, notes, prenom_de, maintenant,
                                                         garder, depuis) if j >= jours and s >= scans_min]


def a_avertir(fiches: dict, onboarding: dict, historique: dict, comptes: list, notes, prenom_de, deja: dict, maintenant=None,
              garder=(), depuis: str = None) -> list:
    """[(uid, prénom, jours sans publier, référence iso)] : silence entre AVERT_JOURS et JOURS - 1, au moins deux jours de
    scan pendant le silence, pas déjà averti pour ce même silence (`deja` : {uid: référence iso})."""
    out = []
    for u, p, j, s, ref in silences(fiches, onboarding, historique, comptes, notes, prenom_de, maintenant, garder, depuis):
        cle = ref.isoformat(timespec="seconds")
        if AVERT_JOURS <= j < JOURS and s >= 2 and deja.get(u) != cle:
            out.append((u, p, j, cle))
    return out


def texte_avertissement(prenom: str, jours: int, date_sortie: str) -> str:
    return (f"⚠️ {prenom}, **{jours} jours sans Reel** sur tes comptes.\n\n"
            "La règle de l'équipe : sans publication, tu sors. "
            f"Sans nouveau Reel d'ici là, **tu sors le {date_sortie}**, et tes comptes vont au suivant.\n\n"
            "Publie aujourd'hui : le compteur repart à zéro. Un souci (compte bloqué, téléphone) ? Écris-le ici.")


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


def sans_compte1(parcours: dict, maintenant=None, depuis: str = None, garder=(), prenom_de=None, notes=None, prouve=None) -> list:
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
        ref = max(d for d in (ouverture, borne) if d is not None)
        out.append((str(uid), prenom, (maintenant - ref).days, ref.isoformat(timespec="seconds")))
    return out


def a_avertir_compte1(parcours: dict, deja: dict, maintenant=None, **kw) -> list:
    """Ceux à J-1 (JOURS_COMPTE1 - 1 jours), pas encore avertis pour cette référence."""
    return [(u, p, j, ref) for u, p, j, ref in sans_compte1(parcours, maintenant, **kw)
            if JOURS_COMPTE1 - 1 <= j < JOURS_COMPTE1 and deja.get(u) != ref]


def a_sortir_compte1(parcours: dict, maintenant=None, **kw) -> list:
    """Ceux à JOURS_COMPTE1 jours ou plus."""
    return [(u, p, j, ref) for u, p, j, ref in sans_compte1(parcours, maintenant, **kw) if j >= JOURS_COMPTE1]


def texte_avertissement_compte1(prenom: str, jours: int) -> str:
    return (f"⚠️ {prenom}, **ton compte 1 n'est toujours pas créé** ({jours} jours).\n\n"
            f"La règle de l'équipe : {JOURS_COMPTE1} jours sans compte créé, tu sors du serveur et ta place va au suivant.\n\n"
            "Crée-le aujourd'hui, puis appuie sur le bouton ✅ de ton étape. Un souci ? Écris à Gaëtan sur WhatsApp.")


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
    kw = {"garder": garder, "prenom_de": prenom_de, "notes": _deps.get("notes"),
          "prouve": lambda u, ouv: compte1_prouve(u, ouv, onboarding_d, historique)}       # 08/10 : le scan vaut le bouton
    for uid, prenom, nb_jours, ref in a_avertir_compte1(parcours, d.get("avertis_compte1", {}), **kw):
        if not appliquer:
            bilan.append(f"· {prenom} : compte 1 pas créé depuis {nb_jours} j → averti (sortie demain)")
            continue
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        if salon is None:
            continue
        try:
            await salon.send(texte_avertissement_compte1(prenom, nb_jours))
            d = _etat(); d.setdefault("avertis_compte1", {})[uid] = ref; _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"⚠️ {prenom} : averti (compte 1 pas créé depuis {nb_jours} j, sortie demain)")
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Avertissement compte 1 de %s : %s", prenom, erreur)
    for uid, prenom, nb_jours, ref in a_sortir_compte1(parcours, **kw):
        if not appliquer:
            bilan.append(f"· {prenom} : compte 1 pas créé depuis {nb_jours} j → sortirait" + (" et expulsé" if KICK else ""))
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
    return bilan


async def executer_sans_reel(client, appliquer: bool = True) -> list:
    """L'ancienne règle du 30/09 (3 j sans Reel → avertissement, 7 j → sortie). Plus appelée depuis le 05/10 ; gardée pour
    `!sortie-auto reels` (liste seulement)."""
    if not ACTIF and appliquer:
        return []
    fiches = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    onboarding = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}) if _deps.get("FICHIER_ONBOARDING") else {}
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    try:
        comptes = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Sortie automatique : classeur illisible (%s), passage annulé", erreur)
        return []
    roster = _deps.get("roster")
    garder = list(roster.lire().get("sans_salon", [])) if roster is not None else []

    def prenom_de(uid):
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        return _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""

    bilan = []
    d = _etat()
    avertir = a_avertir(fiches, onboarding, historique, comptes, _deps.get("notes"), prenom_de, d.get("avertis", {}), garder=garder)
    for uid, prenom, nb_jours, cle in avertir:
        date_sortie = (_jour(cle) + timedelta(days=JOURS)).strftime("%d/%m")
        if not appliquer:
            bilan.append(f"· {prenom} : {nb_jours} jours sans Reel → averti (sortie le {date_sortie} sans Reel)")
            continue
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        if salon is None:
            continue
        try:
            await salon.send(texte_avertissement(prenom, nb_jours, date_sortie))
            d = _etat(); d.setdefault("avertis", {})[uid] = cle; _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"⚠️ {prenom} : averti ({nb_jours} jours sans Reel, sortie le {date_sortie} sans Reel)")
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Avertissement de %s : %s", prenom, erreur)
    cibles = a_sortir(fiches, onboarding, historique, comptes, _deps.get("notes"), prenom_de, garder=garder)
    if not cibles:
        return bilan
    for uid, prenom, nb_jours, scans in cibles:
        if not appliquer:
            bilan.append(f"· {prenom} : {nb_jours} jours sans Reel ({scans} jours de scan) → sortirait")
            continue
        m = _deps["membre_par_id"](uid)
        if m is None:
            continue
        try:
            res = await _deps["sortir"](m, RAISON, pool=True)
            d = _etat()
            d.setdefault("sorties", {})[uid] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "prenom": prenom,
                                                 "jours": nb_jours, "scans": scans}
            _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"🚪 {prenom} : sorti ({nb_jours} jours sans Reel) · comptes rendus au vivier : {res.get('comptes', 0)} · "
                         f"lien libéré : {res.get('liens', 0)}")
            journal.info("Sortie automatique : %s (%s) après %d jours, %d scans", prenom, uid, nb_jours, scans)
        except Exception as erreur:                                         # noqa: BLE001
            bilan.append(f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}")
            journal.warning("Sortie automatique de %s : %s", prenom, erreur)
    return bilan


async def commande(message, texte: str) -> bool:
    """`!sortie-auto` : qui partirait aujourd'hui ; `!sortie-auto go` : sortir maintenant."""
    if not texte.lower().startswith("!sortie-auto"):
        return False
    mots = texte.lower().split()[1:2]
    go = mots == ["go"]
    if mots == ["reels"]:                                                # 05/10 : l'ancienne lecture « sans Reel », liste seulement
        bilan = await executer_sans_reel(None, appliquer=False)
        await message.reply(("🔎 **Silences (ancienne règle, pour information)**\n" + "\n".join(bilan))[:1990] if bilan
                            else "✅ Aucun silence de 3 jours ou plus sans Reel.")
        return True
    bilan = await executer(message.client if hasattr(message, "client") else None, appliquer=go)
    if not bilan:
        await message.reply(f"✅ Personne à avertir ni à sortir : aucun compte 1 ouvert depuis {JOURS_COMPTE1 - 1} jours sans être créé."
                            + ("" if ACTIF else " Sortie automatique éteinte (`SORTIE_AUTO=0`)."))
        return True
    await message.reply((("🚪 **Avertissements et sorties automatiques**\n" if go else "🔎 **Aujourd'hui** (`!sortie-auto go` pour le faire)\n")
                         + "\n".join(bilan))[:1990])
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Sortie automatique éteinte (SORTIE_AUTO=0)")
        return
    journal.info("Sortie automatique active (règle du 05/10) : compte 1 pas créé → averti à J-1, sorti%s à %d jours, à %d h UTC, "
                 "jamais pour un retard antérieur au %s", " et expulsé" if KICK else "", JOURS_COMPTE1, HEURE_UTC, COMPTE1_DEPUIS)
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
                _deps["ecrire_json"](_deps["FICHIER"], d)
                if bilan and _deps.get("canal_admin"):
                    canal = await _deps["canal_admin"]()
                    if canal is not None:
                        entete = ("🔎 **Sortie automatique, première liste** — rien n'est fait aujourd'hui. Demain à la même heure, ces "
                                  "clippers sortent tout seuls (`!sortie-auto go` pour le faire maintenant, `!note @x garde` pour en protéger un).\n"
                                  if premiere else "🚪 **Avertissements et sorties automatiques du jour**\n")
                        await canal.send((entete + "\n".join(bilan))[:1990])
            except Exception as erreur:                                     # noqa: BLE001
                journal.warning("Boucle de sortie automatique : %s", erreur)
        await asyncio.sleep(1800)
