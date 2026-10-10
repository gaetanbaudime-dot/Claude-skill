"""Places livrables (10/10, revue du recrutement, lot L3) : les deux goulots du recrutement en un seul chiffre.

Gaëtan, 10/10 : « Fais en sorte que l'expérience soit le plus fluide et la plus rapide possible pour qu'un clipper arrive dans
l'agence, soit formé et commence à créer ses comptes Instagram. » Le débit est tenu par deux stocks que personne ne pilotait :

1. les lignes libres du classeur des logins (onboarding.disponibles). Un nouveau en réserve ATTRIBUTION_LIGNES_MIN à son arrivée :
   3 par défaut, son trio, comme avant. À 1, `livrer` ne réserve que le compte 1, et les comptes 2 et 3 sont réservés à
   l'ouverture de leur étape (parcours.envoyer_etape → onboarding.reserver_compte) ;
2. le forfait GAML (GAML_FORFAIT_LIENS liens actifs, 50) : sans lien, le compte 3 part sans app ni paie.

Une place = un nouveau qui peut entrer maintenant. Par créatrice : (lignes libres − lignes encore dues aux clippers en route)
÷ ATTRIBUTION_LIGNES_MIN. Au total : le plus petit de la somme et des liens GAML libres (après les liens promis aux clippers en
route, liens libérés de la créatrice réutilisables compris), moins les membres qui attendent déjà une créatrice.

Lecture seule partout : le classeur (onboarding.lire_comptes), clics.json (paie_clics._lire, jamais écrit ici), parcours.json,
onboarding.json et pipeline.json (attribution.en_attente). Le module ne connaît pas bot_discord : le lot W branche
places_par_creatrice (attribution, `!attribution`), places_livrables (page du quizz réussi) et texte_annonce (`!annonce`, digest).
"""

import logging
import os
import unicodedata

import attribution
import onboarding
import paie_clics
import parcours

journal = logging.getLogger("places")


def _entier(nom: str, defaut: int) -> int:
    try:
        return int(os.environ.get(nom, str(defaut)) or defaut)
    except ValueError:
        journal.warning("%s illisible : %s gardé", nom, defaut)
        return defaut


# 10/10 (décision : livré à 3, aucun changement ; Gaëtan peut passer à 1 une fois le forfait GAML tranché)
LIGNES_PAR_PLACE = max(1, _entier("ATTRIBUTION_LIGNES_MIN", 3))
GAML_FORFAIT_LIENS = max(0, _entier("GAML_FORFAIT_LIENS", 50))          # 08/10 : 49 liens actifs sur 50


def lignes_par_place() -> int:
    """Le diviseur des places : les lignes qu'un nouveau prend à son arrivée (ATTRIBUTION_LIGNES_MIN, 3 par défaut)."""
    return LIGNES_PAR_PLACE


def lignes_a_reserver() -> int:
    """Les lignes que `livrer` réserve à l'arrivée : min(COMPTES_PAR_CLIPPER, ATTRIBUTION_LIGNES_MIN). À 3 : le trio, inchangé."""
    return max(1, min(int(onboarding.COMPTES_PAR_CLIPPER), LIGNES_PAR_PLACE))


def _cle(t) -> str:
    """Une créatrice comparée sans accent ni casse, premier mot (« Chloé 💖 », « chloe » : la même)."""
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return (t.split() or [""])[0]


def noms_du_classeur(comptes: list) -> list:
    """Les créatrices du classeur (colonne Créatrice, sinon le nom de l'onglet), triées : celles de `_livrables_par_creatrice`."""
    return sorted({str(c.get("creatrice") or "").strip() for c in comptes if str(c.get("creatrice") or "").strip()})


def noms_ouverts(comptes: list) -> list:
    """Les créatrices qui reçoivent des nouveaux : l'ordre d'attribution s'il est actif, sinon toutes celles du classeur."""
    if attribution.actif() and attribution.ORDRE:
        return list(attribution.ORDRE)
    return noms_du_classeur(comptes)


def lignes_par_creatrice(comptes: list, noms=None) -> dict:
    """{créatrice: lignes libres livrables} (onboarding.disponibles, sans limite). `noms` : toutes celles du classeur par défaut."""
    noms = noms_du_classeur(comptes) if noms is None else list(noms)
    return {nom: len(onboarding.disponibles(comptes, nom, 999)) for nom in noms}


def en_route() -> list:
    """[{uid, cle, lignes_dues, lien_du}] des clippers dont le parcours n'a pas encore donné tous ses comptes (étapes 1 à 3, bienvenue
    comprise). `lignes_dues` : les comptes pas encore dans sa fiche d'onboarding (0 quand `livrer` a réservé le trio). `lien_du` : son
    compte privé n'est pas encore ouvert et aucun lien GAML n'est à lui (le lien sera créé à son ouverture). Lecture seule."""
    try:
        fiches_p = parcours._lire() or {}
    except Exception as erreur:                                         # noqa: BLE001 — parcours non branché : personne en route
        journal.info("Places, parcours illisible : %s", type(erreur).__name__)
        return []
    try:
        clippers = onboarding._lire_etat().get("clippers", {}) or {}
    except Exception:                                                   # noqa: BLE001
        clippers = {}
    avec_lien = set()
    try:
        if paie_clics.actif():
            avec_lien = {str(i.get("uid") or "") for i in (paie_clics._lire().get("liens") or {}).values() if isinstance(i, dict)}
    except Exception:                                                   # noqa: BLE001 — sans clics.json : la fiche d'onboarding seule
        avec_lien = set()
    out = []
    for uid, f in fiches_p.items():
        if not isinstance(f, dict):
            continue
        try:
            etape = int(f.get("etape", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not 1 <= etape <= 3:
            continue
        onb = clippers.get(str(uid)) or {}
        creatrice = f.get("creatrice") or onb.get("creatrice") or ""
        np_ = parcours.n_prive(f)
        prive_ouvert = etape > np_ or bool((f.get("dates") or {}).get(str(np_)))
        a_un_lien = bool(onb.get("lien")) or str(uid) in avec_lien
        out.append({"uid": str(uid), "cle": _cle(creatrice),
                    "lignes_dues": max(0, int(onboarding.COMPTES_PAR_CLIPPER) - len([h for h in onb.get("comptes") or [] if h])),
                    "lien_du": not prive_ouvert and not a_un_lien})
    return out


def etat_gaml() -> dict:
    """Le forfait GAML lu dans clics.json (paie_clics._lire, LECTURE SEULE) : {"forfait", "actifs", "reutilisables": {créatrice: n}}.
    Actif = ni effacé dans GAML (`supprime_gaml`) ni désactivé (`desactive`) : depuis le 09/10, chaque lien actif de GAML a sa fiche
    (marquer_releves, toutes les heures), pages des créatrices comprises. Réutilisable = libéré par un sortant, encore actif, pas
    passé hors clipping : le suivant de la même créatrice le reprend sans place de plus (paie_clics.lien_libre). Un lien effacé à la
    main sans être vu au relevé compte encore : l'erreur va vers moins de places, jamais plus. None : paie au clic éteinte ou
    clics.json illisible (le forfait ne limite alors rien)."""
    if not paie_clics.actif():
        return None
    try:
        liens = paie_clics._lire().get("liens") or {}
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Places, clics.json illisible : %s", type(erreur).__name__)
        return None
    actifs, reutilisables = 0, {}
    for info in liens.values():
        if not isinstance(info, dict) or info.get("supprime_gaml") or info.get("desactive"):
            continue
        actifs += 1
        if not str(info.get("uid") or "") and info.get("libere") and not info.get("hors_clipping"):
            cle = _cle(info.get("creatrice"))
            if cle:
                reutilisables[cle] = reutilisables.get(cle, 0) + 1
    return {"forfait": GAML_FORFAIT_LIENS, "actifs": actifs, "reutilisables": reutilisables}


def attente_attribution() -> int:
    """Les membres qui attendent déjà une créatrice faute de compte (attribution.en_attente) : ils passent avant un nouveau. Ceux du
    filet du roster (attente d'une décision du staff, pas d'un compte) ne comptent pas."""
    try:
        return sum(1 for _, i in attribution.en_attente() if (i or {}).get("attente_par") != attribution.ATTENTE_ROSTER)
    except Exception as erreur:                                         # noqa: BLE001 — attribution non branchée : personne
        journal.info("Places, attente illisible : %s", type(erreur).__name__)
        return 0


def calculer(comptes: list, noms=None, route=None, gaml=None, attente: int = 0) -> dict:
    """Le calcul, pur (aucune lecture) : comptes du classeur, créatrices retenues, clippers en route (en_route), forfait GAML
    (etat_gaml, None = pas de limite), membres en attente. Renvoie :
    {"k", "lignes": {créatrice: n}, "dues": {créatrice: n}, "par_creatrice": {créatrice: places}, "places_lignes",
     "gaml": None | {"forfait", "actifs", "promis", "reutilisables", "libres", "capacite"}, "attente", "places"}."""
    noms = noms_du_classeur(comptes) if noms is None else list(noms)
    route = route or []
    k = LIGNES_PAR_PLACE
    lignes = lignes_par_creatrice(comptes, noms)
    dues_cle, promis_cle = {}, {}
    for r in route:
        dues_cle[r["cle"]] = dues_cle.get(r["cle"], 0) + int(r.get("lignes_dues") or 0)
        if r.get("lien_du"):
            promis_cle[r["cle"]] = promis_cle.get(r["cle"], 0) + 1
    dues = {nom: dues_cle.get(_cle(nom), 0) for nom in noms}
    par_creatrice = {nom: max(0, lignes[nom] - dues[nom]) // k for nom in noms}
    places_lignes = sum(par_creatrice.values())
    g = None
    brut = places_lignes
    if gaml is not None:
        reutil = gaml.get("reutilisables") or {}
        restes, debordes = {}, 0                                        # liens réutilisables laissés aux nouveaux, promis sans lien libéré
        for cle in set(reutil) | set(promis_cle):
            restes[cle] = max(0, reutil.get(cle, 0) - promis_cle.get(cle, 0))
            debordes += max(0, promis_cle.get(cle, 0) - reutil.get(cle, 0))
        libres_forfait = max(0, int(gaml.get("forfait") or 0) - int(gaml.get("actifs") or 0) - debordes)
        capacite = libres_forfait + sum(min(par_creatrice[nom], restes.get(_cle(nom), 0)) for nom in noms)
        g = {"forfait": int(gaml.get("forfait") or 0), "actifs": int(gaml.get("actifs") or 0), "promis": sum(promis_cle.values()),
             "reutilisables": sum(reutil.values()), "libres": libres_forfait + sum(restes.values()), "capacite": capacite}
        brut = min(places_lignes, capacite)
    return {"k": k, "lignes": lignes, "dues": dues, "par_creatrice": par_creatrice, "places_lignes": places_lignes, "gaml": g,
            "attente": max(0, int(attente or 0)), "places": max(0, brut - max(0, int(attente or 0)))}


async def places_par_creatrice(comptes: list = None) -> dict:
    """{créatrice du classeur: places}, lignes dues aux clippers en route déduites : la dépendance « livrables » de l'attribution et de
    `!attribution` (remplace `_livrables_par_creatrice` d'on_ready, lot W). Sans le forfait GAML : l'attribution donne une créatrice
    dès qu'une ligne existe ; le forfait se voit à `!annonce`, au quizz et au compte 3. Une panne du classeur remonte : l'attribution
    traite alors le stock comme inconnu et ne bloque personne (attribution.stock_livrable)."""
    if comptes is None:
        comptes = await onboarding.lire_comptes()
    return calculer(comptes, noms_du_classeur(comptes), en_route())["par_creatrice"]


async def detail(comptes: list = None) -> dict:
    """Le calcul complet pour un NOUVEAU (créatrices de l'ordre d'attribution, forfait GAML, membres en attente). Une panne du
    classeur remonte (RuntimeError) : à l'appelant de dire « places inconnues »."""
    if comptes is None:
        comptes = await onboarding.lire_comptes()
    return calculer(comptes, noms_ouverts(comptes), en_route(), etat_gaml(), attente_attribution())


async def places_livrables() -> int:
    """Les nouveaux qui peuvent entrer maintenant (dépendance `places` de web_candidature, lot W). Lève l'erreur du classeur."""
    return int((await detail())["places"])


def _pluriel(n: int, un: str, plusieurs: str) -> str:
    return f"{n} {un if n <= 1 else plusieurs}"


def texte(det: dict) -> str:
    """Pour Gaëtan seul (`!annonce`, digest) : « Places maintenant : Chloé 2, Sarah 1 (lignes ÷ 3 ; liens GAML libres : 4) », ou
    « 0 place : n'annonce pas encore » avec ce qui manque. Paragraphes courts, une ligne vide entre deux."""
    k = det["k"]
    stock = ", ".join(f"{nom} {n}" for nom, n in det["par_creatrice"].items()) or "aucune créatrice"
    g = det.get("gaml")
    if g is None:
        gaml_t = "liens GAML libres : inconnus"
    else:
        gaml_t = f"liens GAML libres : {g['libres']}"
        if g["promis"]:
            gaml_t += f", après {g['promis']} promis aux clippers en route"
    entre = f"lignes ÷ {k} ; {gaml_t}"
    dues = sum(det.get("dues", {}).values())
    if dues:
        entre += f" ; {_pluriel(dues, 'ligne due', 'lignes dues')} aux clippers en route"
    limites = []
    if g is not None and g["capacite"] < det["places_lignes"]:
        limites.append(f"Le forfait GAML limite ({g['actifs']}/{g['forfait']} liens actifs) : libère un lien (`!liens`) ou monte "
                       "le forfait.")
    if det["places_lignes"] <= 0:
        limites.append("Il manque des lignes : crée des comptes (Build capacity).")
    if det["attente"]:
        limites.append(f"{_pluriel(det['attente'], 'membre attend', 'membres attendent')} déjà une créatrice : "
                       f"{'il passe' if det['attente'] == 1 else 'ils passent'} avant.")
    if det["places"] <= 0:
        return "\n\n".join(["⛔ **0 place : n'annonce pas encore.**", *limites, f"-# {stock} ({entre})"])
    tete = f"📦 **Places maintenant : {stock}** ({entre})."
    return "\n\n".join([tete, f"→ **{det['places']}** {'nouveau peut' if det['places'] == 1 else 'nouveaux peuvent'} entrer.",
                        *limites])


async def texte_annonce() -> str:
    """La ligne sous la réponse de `!annonce` (dépendance `places_texte` de web_candidature, lot W). Classeur illisible : une
    ligne qui le dit, jamais un faux 0."""
    try:
        return texte(await detail())
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Places livrables : %s", erreur)
        return f"⚠️ Places inconnues : classeur des logins illisible ({type(erreur).__name__})."
