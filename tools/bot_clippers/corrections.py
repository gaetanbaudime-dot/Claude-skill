"""Corrections décidées par Gaëtan, déposées dans le dépôt (30/10/2026).

`corrections_a_appliquer.json` = {"id", "attendre_ci": [{"handle", "variante": bool}], "actions": [...]}, joué UNE fois par id,
CORRECTIONS_DELAI_S après le démarrage. Avant les actions, le bot attend (au plus ATTENTE_CI_MIN minutes) que le contrôle GitHub
des @ (onglet « IG · Contrôle des @ ») ait lu chaque @ de `attendre_ci` (avec une variante libre si demandé) : la clé RapidAPI de
Railway est refusée, c'est lui qui prouve qu'un @ est libre. Bilan au salon admin.

Actions (un clipper est désigné par son prénom ET sa créatrice : une seule fiche du parcours doit correspondre) :
- « log » {creatrice, ancien, nouveau, etat?} : la cellule « @ IG » de la ligne `ancien` (seule dans cet onglet) devient `nouveau`,
  et son état `etat` si donné. Le registre note la création si l'état n'est plus « à créer ».
- « fiche » {prenom, creatrice, ancien, nouveau} : côté bot seulement (fiche, livraisons, registre), `ancien` devient `nouveau` ;
  le LOG porte déjà `nouveau`.
- « attribuer » {prenom, creatrice, handle} : la ligne « à créer » du stock `handle` passe au nom du clipper (Gérant).
- « rendre » {prenom, creatrice, handles?, actifs_permis?} : ses lignes « à créer » repartent au stock (onboarding.rendre_lignes :
  @ vu libre exigé, jamais un compte créé).
- « variante » {prenom, creatrice, n} : son compte n prend la variante libre de son @ (parcours.renommer : LOG, fiche, registre).
- « remise » {clippers: [[prenom, creatrice], …]} : la remise de leurs @ restants (remise_arobases, envoi).
- « aligner » {prenom, creatrice, comptes: [@1, @2, @3], renommer?} (31/10, Esperance) : fiche, registre et parcours suivent ses
  trois comptes créés du LOG ; les @ en trop sortent seulement si Instagram prouve qu'il ne les a jamais créés (voir _aligner).
- « registre » {prenom, creatrice} (31/10) : lecture seule, fiche, ordre des comptes, parcours et places du registre du clipper.
Le bilan part au salon admin ET au journal (« Correction <id> : … »).
"""
import asyncio
import json
import logging
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

journal = logging.getLogger("corrections")

FICHIER = Path(__file__).with_name("corrections_a_appliquer.json")
DELAI_S = int(os.environ.get("CORRECTIONS_DELAI_S", "180") or 180)
ATTENTE_CI_MIN = int(os.environ.get("CORRECTIONS_ATTENTE_CI_MIN", "45") or 45)
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, DONNEES, FICHIER_EQUIPES, notifier (coroutine texte, guild)."""
    _deps.update(deps)


def _n(t) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def uid_de(fiches: dict, prenom: str, creatrice: str) -> str:
    """Pur : l'uid de LA fiche du parcours à ce prénom (premier mot) et cette créatrice ; '' si aucune ou plusieurs."""
    p, c = _n(prenom).split()[:1], _n(creatrice)
    trouves = [u for u, f in (fiches or {}).items() if isinstance(f, dict) and p
               and _n(f.get("prenom")).split()[:1] == p and (not c or _n(f.get("creatrice")) == c)]
    return trouves[0] if len(trouves) == 1 else ""


async def _log(a: dict) -> str:
    import google_api
    import onboarding
    ancien, nouveau = onboarding.normaliser_handle(a["ancien"]).lower(), onboarding.normaliser_handle(a["nouveau"]).lower()
    comptes = await onboarding.lire_comptes()
    if any(onboarding.normaliser_handle(c.get("handle")).lower() == nouveau for c in comptes):
        return f"⚠️ LOG : @{nouveau} est déjà dans le classeur, rien changé"
    lignes = [c for c in comptes if onboarding.normaliser_handle(c.get("handle")).lower() == ancien
              and onboarding._pour_creatrice(c, a.get("creatrice", ""))]
    if len(lignes) != 1:
        return f"⚠️ LOG : ligne @{ancien} absente ou en double ({len(lignes)}), rien changé"
    c = lignes[0]
    ecr = [(onboarding.cellule(c, "handle"), [[nouveau]])]
    if a.get("etat"):
        ecr.append((onboarding.cellule(c, "etat"), [[a["etat"]]]))
    await google_api.sheets_ecrire_plusieurs(onboarding.CLASSEUR_LOGINS_ID, ecr)
    for uid, fiche in (onboarding._lire_etat().get("clippers") or {}).items():      # les fiches qui portaient l'ancien @ suivent
        if ancien in [onboarding.normaliser_handle(x).lower() for x in (fiche or {}).get("comptes") or []]:
            onboarding._appliquer_nouveau_handle(uid, ancien, nouveau)
    if a.get("etat") and onboarding._norm(a["etat"]) not in onboarding.A_CREER:
        registre = onboarding.process_adapters.store()
        owner = registre.owner_for_handle(nouveau) or registre.owner_for_handle(ancien)
        if owner:
            try:
                registre.created(owner, nouveau if registre.owner_for_handle(nouveau) else ancien,
                                 "correction LOG du 30/10 : compte vu sur Instagram (contrôle des @)")
            except Exception as erreur:                                 # noqa: BLE001 — le LOG fait foi
                journal.info("Registre, création de %s : %s", nouveau, erreur)
    return f"✏️ LOG : @{ancien} → @{nouveau}" + (f" ({a['etat']})" if a.get("etat") else "")


async def _fiche(a: dict, uid: str) -> str:
    import onboarding
    ancien, nouveau = onboarding.normaliser_handle(a["ancien"]).lower(), onboarding.normaliser_handle(a["nouveau"]).lower()
    registre = onboarding.process_adapters.store()
    try:
        registre.rename(uid, ancien, nouveau)
    except Exception as erreur:                                         # noqa: BLE001 — la fiche suit quand même le LOG
        journal.info("Registre, renommage %s → %s : %s", ancien, nouveau, erreur)
    onboarding._appliquer_nouveau_handle(uid, ancien, nouveau)
    return f"✏️ Fiche de {a['prenom']} : @{ancien} → @{nouveau} (comme le LOG)"


async def _attribuer(a: dict, uid: str) -> str:
    import google_api
    import onboarding
    h = onboarding.normaliser_handle(a["handle"]).lower()
    comptes = await onboarding.lire_comptes()
    lignes = [c for c in comptes if onboarding.normaliser_handle(c.get("handle")).lower() == h]
    if len(lignes) != 1 or onboarding._norm(lignes[0]["etat"]) not in onboarding.A_CREER:
        return f"⚠️ @{h} : ligne absente, en double ou déjà créée, rien attribué"
    c = lignes[0]
    if onboarding._norm(c["gerant"]) not in onboarding.GERANTS_LIBRES | {onboarding._norm(a["prenom"])}:
        return f"⚠️ @{h} : déjà au nom de {c['gerant']}, rien attribué"
    await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, onboarding.cellule(c, "gerant"), [[a["prenom"]]])
    etat = onboarding._lire_etat()
    fiche = etat["clippers"].setdefault(uid, {})
    if h not in [onboarding.normaliser_handle(x).lower() for x in fiche.get("comptes") or []]:
        fiche.setdefault("comptes", []).append(h)
        onboarding._ecrire_etat(etat)
    try:
        onboarding.process_adapters.store().reserve(uid, [h])
    except Exception as erreur:                                         # noqa: BLE001 — déjà à lui, ou places à vie : signalé
        journal.info("Registre, réservation de %s : %s", h, erreur)
    return f"📌 @{h} attribué à {a['prenom']} dans le LOG"


async def _variante(a: dict, uid: str) -> str:
    import arobase_libre
    import onboarding
    import parcours
    n = int(a["n"])
    handles = parcours._comptes_ordonnes(uid)
    if len(handles) < n:
        return f"⚠️ {a['prenom']} : pas de compte {n}"
    h = handles[n - 1]
    dans_le_log = {onboarding.normaliser_handle(c.get("handle")).lower() for c in await onboarding.lire_comptes()}
    v = await arobase_libre.variante_libre(h, exclus=dans_le_log)
    if not v:
        return f"⚠️ {a['prenom']} : aucune variante libre vérifiée pour @{h}, rien changé"
    _, raison = await parcours.renommer(uid, n, v)
    return f"⚠️ {a['prenom']} : @{v} refusé ({raison})" if raison else f"🔁 {a['prenom']}, compte {n} : @{h} → @{v} (libre)"


def jamais_a_lui(ex: dict) -> bool:
    """Pur : Instagram prouve que ce @ n'est pas un compte créé par le clipper — libre, ou le compte ancien d'un inconnu (pas neuf,
    profil lu, rien qui le relie à nous). Un doute, un compte neuf ou un profil illisible : non (jamais retiré sur un doute)."""
    import arobase_libre
    v = (ex or {}).get("verdict")
    if v == arobase_libre.LIBRE:
        return True
    return (v == arobase_libre.PRIS and not ex.get("a_nous") and not ex.get("neuf") and ex.get("profil_lu") is not False)


async def _aligner(a: dict, uid: str, client) -> list:
    """31/10 (Esperance : son compte 3 retenu toutes les 30 min par « Trois places à vie », son compte 1 jamais confirmé : la
    fiche portait @lasoir_ quand elle avait créé @lasoir_c, plus deux essais de privé jamais faits). {prenom, creatrice,
    comptes: [@1, @2, @3], renommer?: {ancien: nouveau}, retirer?: [@…]} : la fiche et le registre s'alignent sur le LOG.
    1. Chaque @ de `comptes` doit être UNE ligne créée (pas « à créer ») de cette créatrice, au nom du clipper (Gérant) ; sinon rien.
    2. `renommer` : la fiche suit le LOG (_appliquer_nouveau_handle), le registre garde la même place sous le nouveau @.
    3. Les autres @ de la fiche sortent de la fiche, et leur place réservée ou incertaine est annulée au registre, seulement si
       Instagram prouve qu'il ne les a jamais créés (jamais_a_lui), ou s'ils sont dans `retirer` (tranchés, preuve dans la note
       du dépôt) ; un compte créé à son nom dans le LOG n'est jamais retiré.
    4. Les trois comptes sont notés créés au registre ; un compte d'une étape déjà passée (le compte 1 quand le 2 est parti à 48 h)
       est noté fait dans le parcours SANS message, son bouton retiré ; l'étape en cours repart d'elle-même au passage suivant."""
    import arobase_libre
    import onboarding
    import parcours
    from copy import deepcopy

    def norm(h):
        return onboarding.normaliser_handle(h).lower()
    prenom, creatrice = a["prenom"], a.get("creatrice", "")
    cibles = [norm(h) for h in a.get("comptes") or [] if norm(h)]
    if len(cibles) != 3 or len(set(cibles)) != 3:
        return [f"⚠️ {prenom} : trois @ distincts attendus, rien changé"]
    p1 = _n(prenom).split()[:1]

    def a_lui(c):
        return bool(p1) and _n(c.get("gerant")).split()[:1] == p1
    log = await onboarding.lire_comptes()
    for h in cibles:
        lignes = [c for c in log if norm(c.get("handle")) == h]
        if (len(lignes) != 1 or not onboarding._pour_creatrice(lignes[0], creatrice) or not a_lui(lignes[0])
                or onboarding._norm(lignes[0].get("etat")) in onboarding.A_CREER):
            return [f"⚠️ {prenom} : @{h} n'est pas UNE ligne créée à son nom dans le LOG ({creatrice}), rien changé"]
    siens = {norm(c.get("handle")) for c in log if a_lui(c) and onboarding._norm(c.get("etat")) not in onboarding.A_CREER}
    bilan = []
    for ancien, nouveau in ((norm(k), norm(v)) for k, v in (a.get("renommer") or {}).items()):
        dans = [norm(h) for h in (onboarding._lire_etat()["clippers"].get(uid) or {}).get("comptes") or []]
        if ancien in dans and nouveau not in dans:
            onboarding._appliquer_nouveau_handle(uid, ancien, nouveau)
            bilan.append(f"✏️ fiche : @{ancien} → @{nouveau} (comme le LOG)")
    etat = onboarding._lire_etat()
    fiche = etat["clippers"].setdefault(uid, {})
    extras = [h for h in fiche.get("comptes") or [] if norm(h) not in cibles and norm(h) not in siens]
    # « retirer » : @ tranchés par Gaëtan (ou en son nom, avec la preuve dans la note du dépôt) malgré un doute d'Instagram ;
    # jamais un des trois comptes ni un compte créé à son nom dans le LOG
    decides = {norm(h) for h in a.get("retirer") or []} - set(cibles) - siens
    retires, gardes = [], []
    for h in extras:
        if norm(h) in decides:
            retires.append(norm(h))
            continue
        ex = await arobase_libre.examen(norm(h), creatrice)
        (retires if jamais_a_lui(ex) else gardes).append(norm(h))
    nouvelle = deepcopy(fiche)
    nouvelle["comptes"] = [h for h in fiche.get("comptes") or [] if norm(h) not in retires]
    nouvelle["acces"] = [x for x in fiche.get("acces") or [] if not (isinstance(x, dict) and norm(x.get("handle")) in retires)]
    ordre = [norm(h) for h in parcours._comptes_ordonnes(uid, onb=nouvelle)[:3]]
    if ordre != cibles:
        return bilan + [f"⚠️ {prenom} : l'ordre des comptes serait {', '.join('@' + h for h in ordre)} au lieu de "
                        f"{', '.join('@' + h for h in cibles)} : fiche et registre laissés tels quels"]
    if retires:
        etat["clippers"][uid] = nouvelle
        onboarding._ecrire_etat(etat)
        vus = [h for h in retires if h not in decides]
        if vus:
            bilan.append("🧹 sortis de la fiche (jamais créés par lui, vu sur Instagram) : " + ", ".join("@" + h for h in vus))
        if set(retires) & decides:
            bilan.append("🧹 sortis de la fiche sur décision (pas au LOG à son nom) : "
                         + ", ".join("@" + h for h in retires if h in decides))
    if gardes:
        bilan.append("⚠️ gardés, à trancher (Instagram ne prouve pas qu'il ne les a pas créés) : "
                     + ", ".join("@" + h for h in gardes))
    registre = onboarding.process_adapters.store()
    for ancien, nouveau in ((norm(k), norm(v)) for k, v in (a.get("renommer") or {}).items()):
        try:
            registre.rename(uid, ancien, nouveau)
        except Exception as erreur:                                     # noqa: BLE001 — déjà fait, ou le nouveau a sa place
            journal.info("Registre, renommage %s → %s : %s", ancien, nouveau, erreur)
    preuve = f"correction du 31/10 : le LOG porte ses 3 comptes créés ({', '.join(cibles)})"
    annules, dans_fiche = [], {norm(h) for h in fiche.get("comptes") or []}
    for _, statut, alias in registre.comptes_de(uid):
        if statut == "cancelled" or not alias or set(alias) & (set(cibles) | siens):
            continue
        nom = "/".join("@" + x for x in alias)
        # 31/10 : un compte noté « créé » parce qu'il EXISTE sur Instagram (le compte d'un inconnu, vu par le scan) ne sort que
        # tranché dans le dépôt (`retirer`) ; jamais un « créé » sur la seule lecture d'Instagram
        faux_cree = statut == "created" and bool(set(alias) & decides)
        if (statut not in ("reserved", "unknown") and not faux_cree) or set(alias) & set(gardes):
            bilan.append(f"⚠️ registre : {nom} ({statut}) gardé, à trancher")
            continue
        prouve = bool(set(alias) & (set(retires) | decides))
        if not prouve and not set(alias) & dans_fiche:                  # place du registre seule : Instagram d'abord, chaque @
            prouve = all([jamais_a_lui(await arobase_libre.examen(x, creatrice)) for x in alias])
        if not prouve:
            bilan.append(f"⚠️ registre : {nom} ({statut}) gardé, à trancher")
            continue
        try:
            registre.retirer_doublon(uid, alias[0], preuve, cree_par_erreur=faux_cree)
            annules.append(nom + (" (noté créé à tort)" if faux_cree else ""))
        except Exception as erreur:                                     # noqa: BLE001
            bilan.append(f"⚠️ registre : {nom} pas retiré ({erreur})")
    if annules:
        bilan.append("♻️ registre : place(s) libérée(s) : " + ", ".join(annules))
    statuts = {h: s for _, s, al in registre.comptes_de(uid) for h in al}
    for h in cibles:
        proprio = registre.owner_for_handle(h)
        try:
            if proprio is None:
                registre.reserve(uid, [h])
            elif str(proprio) != uid:
                bilan.append(f"⚠️ registre : @{h} est au nom d'un autre clipper, pas touché")
                continue
            if statuts.get(h) != "created":
                registre.created(uid, h, preuve)
        except Exception as erreur:                                     # noqa: BLE001 — signalé, la suite passe
            bilan.append(f"⚠️ registre : @{h} pas noté créé ({type(erreur).__name__} {erreur})")
    d = parcours._lire()
    f = d.get(uid) or {}
    etape, fermes = int(f.get("etape", 0) or 0), []
    for n in (1, 2, 3):
        dates = f.get("dates") or {}
        if etape > n and dates.get(str(n)) and not dates.get(f"{n}_fait"):
            f["dates"][f"{n}_fait"] = parcours._maintenant()
            fermes.append(n)
    if fermes:
        parcours._ecrire(d)
        salon = client.get_channel(int(f.get("salon_id") or 0)) if client is not None and str(f.get("salon_id") or "").isdigit() else None
        for n in fermes:
            if salon is not None:
                await parcours._retirer_bouton(salon, (f.get("messages") or {}).get(str(n)))
        bilan.append("✅ parcours : " + ", ".join(f"compte {n}" for n in fermes) + " noté(s) créé(s), sans message")
    return [f"🧩 {prenom} ({creatrice}) aligné sur le LOG : " + ", ".join(f"{i} @{h}" for i, h in enumerate(cibles, 1))] + bilan


def etat_registre(uid: str) -> str:
    """31/10 (Esperance : « Trois places à vie » sans voir quelles places) : les places de ce clipper au registre, en une ligne."""
    import onboarding
    try:
        comptes = onboarding.process_adapters.store().comptes_de(uid)
    except Exception as erreur:                                         # noqa: BLE001
        return f"registre illisible ({type(erreur).__name__})"
    vivants = [c for c in comptes if c[1] != "cancelled"]
    return (f"registre : {len(vivants)} place(s) prise(s) sur 3 · "
            + " · ".join(f"{'/'.join('@' + a for a in al) or '(sans @)'} {st}" for _, st, al in comptes))


async def _registre(a: dict, uid: str) -> str:
    """31/10 : lecture seule — la fiche, l'ordre des comptes, le parcours et le registre d'un clipper (diagnostic d'une retenue)."""
    import onboarding
    import parcours
    fiche = (onboarding._lire_etat().get("clippers") or {}).get(uid) or {}
    f = parcours._lire().get(uid) or {}
    dates = f.get("dates") or {}
    return (f"🔎 {a['prenom']} ({a.get('creatrice', '')}) : fiche {', '.join('@' + str(h) for h in fiche.get('comptes') or []) or 'vide'}"
            f" · ordre {', '.join('@' + h for h in parcours._comptes_ordonnes(uid)[:3])}"
            f" · étape {f.get('etape')} · dates {', '.join(sorted(dates))}"
            f" · retenue {(f.get('retenue') or {}).get('raison', 'aucune')} · {etat_registre(uid)}")


async def _attendre_ci(attentes: list) -> list:
    """Les @ que le contrôle GitHub n'a toujours pas lus au bout d'ATTENTE_CI_MIN minutes ([] : tout est là)."""
    import arobase_libre
    manquent = list(attentes or [])
    for _ in range(max(1, ATTENTE_CI_MIN)):
        reste = []
        for x in manquent:
            ci = await arobase_libre.depuis_ci(x.get("handle"))
            if not ci or (x.get("variante") and not ci.get("variante")):
                reste.append(x)
        manquent = reste
        if not manquent:
            return []
        arobase_libre._cache_ci["le"] = 0.0                             # relu au tour suivant
        await asyncio.sleep(60)
    return manquent


async def appliquer(client, depot: dict) -> list:
    import onboarding
    import parcours
    import remise_arobases
    bilan = []
    manquent = await _attendre_ci(depot.get("attendre_ci") or [])
    if manquent:
        bilan.append("⚠️ Contrôle GitHub pas encore lu pour : " + ", ".join("@" + str(x.get("handle")) for x in manquent)
                     + " (ce qui en dépend est sauté)")
    fiches = parcours._lire() or {}
    for a in depot.get("actions") or []:
        quoi = a.get("action")
        try:
            if quoi == "log":
                bilan.append(await _log(a))
                continue
            if quoi == "remise":
                uids = {uid_de(fiches, p, c) for p, c in a.get("clippers") or []} - {""}
                res = await remise_arobases.remise(client, envoyer=True, seulement=uids)
                bilan.append(f"📋 Remise : {res['messages']} message(s) envoyé(s)" + ("".join("\n" + b for b in res["bilan"])))
                continue
            uid = uid_de(fiches, a.get("prenom", ""), a.get("creatrice", ""))
            if quoi == "rendre":
                import cockpit_sorties
                registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
                if not a.get("actifs_permis") and _n(a["prenom"]).split()[0] in cockpit_sorties.prenoms_signes(registre):
                    bilan.append(f"⚠️ {a['prenom']} : un clipper signé porte ce prénom, aucune ligne rendue")
                    continue
                rendus = await onboarding.rendre_lignes(a["prenom"], a.get("creatrice", ""), handles=a.get("handles") or (),
                                                        actifs=set(registre), actifs_permis=bool(a.get("actifs_permis")))
                bilan.append(f"♻️ {a['prenom']} : {len([x for x in rendus if x.startswith('·')])} ligne(s) « à créer » rendue(s) au stock")
                continue
            if not uid:
                bilan.append(f"⚠️ {a.get('prenom')} ({a.get('creatrice')}) : fiche introuvable ou en double, « {quoi} » sauté")
                continue
            if quoi == "fiche":
                bilan.append(await _fiche(a, uid))
            elif quoi == "attribuer":
                bilan.append(await _attribuer(a, uid))
            elif quoi == "variante":
                bilan.append(await _variante(a, uid))
            elif quoi == "aligner":
                bilan.extend(await _aligner(a, uid, client))
                bilan.append(f"   {etat_registre(uid)}")
            elif quoi == "registre":
                bilan.append(await _registre(a, uid))
            else:
                bilan.append(f"⚠️ action inconnue : {quoi}")
        except Exception as erreur:                                     # noqa: BLE001 — l'action suivante passe quand même
            journal.exception("Correction %s", quoi)
            bilan.append(f"❌ {quoi} ({a.get('prenom') or a.get('ancien') or ''}) : {type(erreur).__name__} {str(erreur)[:120]}")
    return bilan


async def demarrage(client) -> None:
    await client.wait_until_ready()
    if not FICHIER.exists() or not _deps.get("DONNEES"):
        return
    try:
        depot = json.loads(FICHIER.read_text(encoding="utf-8"))
    except ValueError as erreur:
        journal.warning("corrections_a_appliquer.json illisible : %s", erreur)
        return
    ident = str((depot or {}).get("id") or "") if isinstance(depot, dict) else ""
    trace = _deps["DONNEES"] / "corrections_faites.json"
    faits = _deps["lire_json"](trace, {})
    if not ident or ident in faits:
        return
    await asyncio.sleep(DELAI_S)
    bilan = await appliquer(client, depot)
    for ligne in bilan:                                                 # 31/10 : le bilan aussi au journal (vérifiable sans Discord)
        journal.info("Correction %s : %s", ident, str(ligne).replace("\n", " | ")[:900])
    faits[ident] = {"le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bilan": bilan}
    _deps["ecrire_json"](trace, faits)
    if _deps.get("notifier"):
        texte = f"🛠️ **Corrections appliquées ({ident})**\n" + "\n".join(bilan)
        for i in range(0, len(texte), 1900):
            try:
                await _deps["notifier"](texte[i:i + 1900], client.guilds[0] if client.guilds else None)
            except Exception:                                           # noqa: BLE001
                break
