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

11/10 (vérification du lot L3) :
- les membres déjà sur le serveur, quizz réussi, pas encore attribués (en_transit) passent avant un nouveau, comme ceux qui
  attendent une créatrice ;
- la promesse du quizz (places_livrables) dit ce que l'attribution donnera : le forfait GAML ne bloque l'attribution que si
  PLACES_GAML_ATTRIBUTION=1 (décision de Gaëtan, une variable). Sinon il limite `!annonce` et le digest, pas l'arrivée ;
- ligne_sans_lien : la ligne du digest « Compte privé sans lien GAML », chaque jour tant qu'il en reste (l'alerte en direct ne
  part qu'à l'ouverture du compte privé).
"""

import logging
import os
import unicodedata
from datetime import datetime, timedelta, timezone

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
# 11/10 (vérification du lot L3 : forfait plein, le quizz promettait « dès qu'une place se libère » à des candidats qui recevaient
# leur créatrice dans la minute) : 1 = le forfait GAML bloque aussi l'attribution (personne n'entre sans lien possible au compte 3) ;
# 0 (défaut, comme avant) = l'attribution suit les lignes seules, le forfait limite `!annonce` et le digest. Décision de Gaëtan.
GAML_BLOQUE_ATTRIBUTION = os.environ.get("PLACES_GAML_ATTRIBUTION", "0").strip() == "1"
TRANSIT_H = 24                                                          # 11/10 : un quizz réussi non attribué compte 24 h au plus
ETATS_TRANSIT = ("quiz_ok", "valide")


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
    try:                                                                # 24/10 : un sorti de l'équipe n'est plus en route
        f_eq = parcours._deps.get("FICHIER_EQUIPES")
        registre = parcours._deps["lire_json"](f_eq, {}) if f_eq and parcours._deps.get("lire_json") else None
    except Exception:                                                   # noqa: BLE001 — registre illisible : personne n'est écarté
        registre = None
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
        if isinstance(registre, dict) and registre and str(uid) not in registre:
            continue
        onb = clippers.get(str(uid)) or {}
        if onb.get("sorti"):
            continue
        creatrice = f.get("creatrice") or onb.get("creatrice") or ""
        np_ = parcours.n_prive(f)
        prive_ouvert = etape > np_ or bool((f.get("dates") or {}).get(str(np_)))
        a_un_lien = bool(onb.get("lien")) or str(uid) in avec_lien
        out.append({"uid": str(uid), "cle": _cle(creatrice),
                    "lignes_dues": max(0, int(onboarding.COMPTES_PAR_CLIPPER) - len([h for h in onb.get("comptes") or [] if h])),
                    # 24/10 (« ⛔ 0 place » : 15 liens promis, dont 11 clippers qui n'avaient pas créé leur compte 1 depuis 3 à
                    # 11 jours et 6 avertis pour une sortie) : le lien n'arrive qu'au compte 3, 96 h après le compte 1 au plus tôt.
                    # Il n'est promis qu'une fois le compte 1 créé ; l'alerte du forfait plein reste là si tous reprennent.
                    "lien_du": not prive_ouvert and not a_un_lien and bool((f.get("dates") or {}).get("1_fait"))})
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


def _instant(v):
    """Une date ISO du pipeline en datetime UTC, None si illisible."""
    try:
        t = datetime.fromisoformat(str(v or ""))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def en_transit(maintenant=None) -> int:
    """11/10 (vérification du lot L3 : après une `!annonce`, trois quizz réussis dans la même heure lisaient tous « ta créatrice et
    ton compte 1 t'y attendent » pour une seule place) : les membres déjà sur le serveur dont le quizz est réussi (pipeline
    « quiz_ok » ou « valide »), pas encore au registre avec une créatrice, quizz ou validation de moins de TRANSIT_H heures. Ni
    livrés ni en attente, ils prennent pourtant la prochaine place. Les candidats du site pas encore arrivés sur Discord sont
    déduits par la page du quizz elle-même (web_candidature, lot L2) : elle sait qui lit la page, alors qu'ici le lecteur, dont le
    quizz est écrit avant la lecture, se compterait lui-même. Lecture seule ; 0 si le pipeline ou le registre est illisible."""
    try:
        fichier, lire = attribution._fichier_pipeline(), attribution._deps.get("lire_json")
        if fichier is None or lire is None:
            return 0
        etats = (lire(fichier, {}) or {}).get("etats") or {}
        registre = (lire(attribution._deps["FICHIER_EQUIPES"], {}) or {}) if attribution._deps.get("FICHIER_EQUIPES") else {}
    except Exception as erreur:                                         # noqa: BLE001 — attribution non branchée : personne
        journal.info("Places, transit illisible : %s", type(erreur).__name__)
        return 0
    limite = (maintenant or datetime.now(timezone.utc)) - timedelta(hours=TRANSIT_H)
    n = 0
    for uid, info in etats.items():
        if not isinstance(info, dict) or info.get("etat") not in ETATS_TRANSIT:
            continue
        fiche = registre.get(str(uid))
        if isinstance(fiche, dict) and fiche.get("creatrice"):
            continue                                                    # attribué : ses lignes sont réservées (ou dues)
        dates = [t for t in (_instant(info.get(k)) for k in ("date_quiz", "validation")) if t is not None]
        if dates and max(dates) >= limite:
            n += 1
    return n


def calculer(comptes: list, noms=None, route=None, gaml=None, attente: int = 0, transit: int = 0) -> dict:
    """Le calcul, pur (aucune lecture) : comptes du classeur, créatrices retenues, clippers en route (en_route), forfait GAML
    (etat_gaml, None = pas de limite), membres en attente d'une créatrice, membres en transit (en_transit). Renvoie :
    {"k", "lignes": {créatrice: n}, "dues": {créatrice: n}, "par_creatrice": {créatrice: places}, "places_lignes",
     "gaml": None | {"forfait", "actifs", "promis", "reutilisables", "libres", "libres_forfait", "restes", "capacite"},
     "attente" (en attente + en transit), "attente_creatrice", "transit", "places" (avec le forfait GAML : `!annonce`, digest),
     "promesse" (ce que l'attribution donnera à un arrivant : sans le forfait, sauf PLACES_GAML_ATTRIBUTION=1)}."""
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
             "reutilisables": sum(reutil.values()), "libres": libres_forfait + sum(restes.values()), "libres_forfait": libres_forfait,
             "restes": restes, "capacite": capacite}
        brut = min(places_lignes, capacite)
    attente_c, transit = max(0, int(attente or 0)), max(0, int(transit or 0))
    devant = attente_c + transit                                        # 11/10 : ils passent tous avant un nouveau
    return {"k": k, "lignes": lignes, "dues": dues, "par_creatrice": par_creatrice, "places_lignes": places_lignes, "gaml": g,
            "attente": devant, "attente_creatrice": attente_c, "transit": transit, "places": max(0, brut - devant),
            "promesse": max(0, (brut if GAML_BLOQUE_ATTRIBUTION else places_lignes) - devant)}


def plafond_gaml(det: dict) -> dict:
    """11/10 (PLACES_GAML_ATTRIBUTION=1 seulement) : {créatrice: places} bornées par le forfait. Chaque créatrice garde ses liens
    libérés réutilisables, plus les liens libres du forfait ; forfait plein et rien à reprendre : 0. Une approximation par
    créatrice (le forfait est commun) : l'attribution relit le stock à chaque nouveau, et le lien promis au précédent (en_route)
    est déjà déduit."""
    g = det.get("gaml")
    if g is None:
        return dict(det["par_creatrice"])
    restes, libres = g.get("restes") or {}, int(g.get("libres_forfait") or 0)
    return {nom: min(n, restes.get(_cle(nom), 0) + libres) for nom, n in det["par_creatrice"].items()}


async def places_par_creatrice(comptes: list = None) -> dict:
    """{créatrice du classeur: places}, lignes dues aux clippers en route déduites : la dépendance « livrables » de l'attribution et de
    `!attribution` (remplace `_livrables_par_creatrice` d'on_ready, lot W). Sans le forfait GAML par défaut : l'attribution donne
    une créatrice dès qu'une ligne existe ; le forfait se voit à `!annonce`, au digest et au compte 3. PLACES_GAML_ATTRIBUTION=1 :
    bornées par le forfait (plafond_gaml), comme la promesse du quizz. Une panne du classeur remonte : l'attribution traite alors
    le stock comme inconnu et ne bloque personne (attribution.stock_livrable)."""
    if comptes is None:
        comptes = await onboarding.lire_comptes()
    if not GAML_BLOQUE_ATTRIBUTION:
        return calculer(comptes, noms_du_classeur(comptes), en_route())["par_creatrice"]
    return plafond_gaml(calculer(comptes, noms_du_classeur(comptes), en_route(), etat_gaml()))


async def detail(comptes: list = None) -> dict:
    """Le calcul complet pour un NOUVEAU (créatrices de l'ordre d'attribution, forfait GAML, membres en attente et en transit). Une
    panne du classeur remonte (RuntimeError) : à l'appelant de dire « places inconnues »."""
    if comptes is None:
        comptes = await onboarding.lire_comptes()
    return calculer(comptes, noms_ouverts(comptes), en_route(), etat_gaml(), attente_attribution(), en_transit())


async def places_livrables() -> int:
    """Les nouveaux qui auront leur créatrice et leur compte 1 en arrivant (dépendance `places` de web_candidature, lot W) : la
    « promesse » de detail, celle que l'attribution tiendra (11/10 : sans le forfait GAML, sauf PLACES_GAML_ATTRIBUTION=1). Lève
    l'erreur du classeur."""
    return int((await detail())["promesse"])


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
        if not GAML_BLOQUE_ATTRIBUTION and det.get("promesse", 0) > det["places"]:
            # 11/10 : l'attribution ne regarde pas le forfait (PLACES_GAML_ATTRIBUTION=0) — Gaëtan sait ce que vit un arrivant
            limites.append("Qui arrive quand même a sa créatrice et son compte 1 : son compte 3 attendra un lien.")
    if det["places_lignes"] <= 0:
        limites.append("Il manque des lignes : crée des comptes (Build capacity).")
    attente_c = det.get("attente_creatrice", det["attente"] - det.get("transit", 0))
    if attente_c:
        limites.append(f"{_pluriel(attente_c, 'membre attend', 'membres attendent')} déjà une créatrice : "
                       f"{'il passe' if attente_c == 1 else 'ils passent'} avant.")
    if det.get("transit"):                                              # 11/10 : quizz réussi, arrivés, pas encore attribués
        limites.append(f"{_pluriel(det['transit'], 'membre vient', 'membres viennent')} de réussir le quizz et "
                       f"{'arrive' if det['transit'] == 1 else 'arrivent'} : déjà compté{'s' if det['transit'] > 1 else ''}.")
    if det["places"] <= 0:
        return "\n\n".join(["⛔ **0 place : n'annonce pas encore.**", *limites, f"-# {stock} ({entre})"])
    tete = f"📦 **Places maintenant : {stock}** ({entre})."
    return "\n\n".join([tete, f"→ **{det['places']}** {'nouveau peut' if det['places'] == 1 else 'nouveaux peuvent'} entrer.",
                        *limites])


def texte_court(det: dict) -> str:
    """21/10 (Gaëtan : « simplifie, rends ça plus facile à lire ») : le bloc des places du point du matin en deux lignes — combien
    peuvent entrer, ce qui limite — puis les places par créatrice en petit. `texte` (détaillé) reste pour `!annonce`."""
    stock = " · ".join(f"{nom} {n}" for nom, n in det["par_creatrice"].items()) or "aucune créatrice"
    g = det.get("gaml")
    limite = ""
    if g is not None and g["capacite"] < det["places_lignes"]:
        limite = (f"Limite : les liens GAML ({g['actifs']}/{g['forfait']} actifs"
                  + (f", {g['promis']} promis aux clippers en route" if g.get("promis") else "")
                  + ") → libère un lien (`!liens`) ou monte le forfait.")
    elif det["places_lignes"] <= 0:
        limite = "Limite : plus de comptes prêts → crée des comptes (Build capacity)."
    attente_c = det.get("attente_creatrice", det["attente"] - det.get("transit", 0))
    if attente_c:
        limite += (" " if limite else "") + f"{_pluriel(attente_c, 'membre attend', 'membres attendent')} déjà une créatrice."
    if det["places"] <= 0:
        tete = "⛔ **0 place : n'annonce pas encore.**"
    else:
        tete = f"📦 **{det['places']} {'nouveau peut' if det['places'] == 1 else 'nouveaux peuvent'} entrer.**"
    return "\n".join(x for x in (tete, limite, f"-# Places par créatrice : {stock}") if x)


async def texte_annonce() -> str:
    """La ligne sous la réponse de `!annonce` (dépendance `places_texte` de web_candidature, lot W). Classeur illisible : une
    ligne qui le dit, jamais un faux 0."""
    try:
        return texte(await detail())
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Places livrables : %s", erreur)
        return f"⚠️ Places inconnues : classeur des logins illisible ({type(erreur).__name__})."


def sans_lien() -> list:
    """11/10 (vérification du lot L3 : l'alerte « Forfait GAML plein » ne part qu'à l'ouverture du compte privé ; la relance du lien
    toutes les 6 h, onboarding.boucle, se tait) : [(uid, prénom)] des clippers dont le lien est dû (parcours.lien_du : compte privé
    ouvert, ou lien, ou routine) sans aucun lien actif à eux (fiche d'onboarding, clics.json). Lecture seule ; [] si la paie au
    clic est éteinte (pas de lien à donner) ou les fichiers illisibles."""
    if not paie_clics.actif():
        return []
    try:
        fiches_p = parcours._lire() or {}
        clippers = onboarding._lire_etat().get("clippers", {}) or {}
        avec_lien = {str(i.get("uid") or "") for i in (paie_clics._lire().get("liens") or {}).values()
                     if isinstance(i, dict) and not i.get("supprime_gaml") and not i.get("desactive")}
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Comptes sans lien GAML illisibles : %s", type(erreur).__name__)
        return []
    # 11/10 (lot W, contre-vérification du lot L3 : la ligne listait pour toujours les prénoms exclus de la paie au clic et les
    # sortis dont la fiche reste au parcours) : les mêmes exclusions que parcours.livrer_app
    try:
        f_eq = parcours._deps.get("FICHIER_EQUIPES")
        registre = parcours._deps["lire_json"](f_eq, {}) if f_eq and parcours._deps.get("lire_json") else None
    except Exception as erreur:                                         # noqa: BLE001 — registre illisible : personne n'est écarté
        journal.info("Comptes sans lien GAML, registre illisible : %s", type(erreur).__name__)
        registre = None
    out = []
    for uid, f in fiches_p.items():
        if not isinstance(f, dict) or not parcours.lien_du(f):
            continue
        if (clippers.get(str(uid)) or {}).get("lien") or str(uid) in avec_lien:
            continue
        if parcours._norm(str(f.get("prenom") or "")) in paie_clics.CLICS_EXCLURE:
            continue                                                    # pas d'app ni de paie au clic (staff, Rianah)
        if isinstance(registre, dict) and str(uid) not in registre:
            continue                                                    # sorti de l'équipe : sa fiche reste au parcours
        out.append((str(uid), str(f.get("prenom") or uid)))
    return out


def ligne_sans_lien() -> str:
    """La ligne du digest de 9 h (lot L9b ou W) : « 🔗 Compte privé sans lien GAML : 2 (Eve, Rio). Libère un lien (`!liens`) ou
    monte le forfait. », chaque jour tant qu'il en reste ; "" s'il n'y en a aucun."""
    liste = sans_lien()
    if not liste:
        return ""
    noms = ", ".join(p for _, p in liste[:10]) + (f" et {len(liste) - 10} autres" if len(liste) > 10 else "")
    return f"🔗 Compte privé sans lien GAML : {len(liste)} ({noms}). Libère un lien (`!liens`) ou monte le forfait."
