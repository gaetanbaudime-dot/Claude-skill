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
    faits[ident] = {"le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bilan": bilan}
    _deps["ecrire_json"](trace, faits)
    if _deps.get("notifier"):
        texte = f"🛠️ **Corrections appliquées ({ident})**\n" + "\n".join(bilan)
        for i in range(0, len(texte), 1900):
            try:
                await _deps["notifier"](texte[i:i + 1900], client.guilds[0] if client.guilds else None)
            except Exception:                                           # noqa: BLE001
                break
