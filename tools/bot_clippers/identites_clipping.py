"""Identités de clipping d'un même membre Discord (24/10, Gaëtan, à propos de Rianah : « C'est comme si tu avais trois personnes :
Rianah Metricool, Rianah clipping Chloé, Rianah clipping Sarah, sauf que tu mets le même compte Discord. Elle a déjà créé un compte
pour Chloé et un pour Sarah : on lui rajoute juste deux comptes pour Chloé, deux comptes pour Sarah »).

Dépôt dans la variable Railway IDENTITES_CLIPPING_JSON (les @ des comptes ne vont jamais dans le dépôt Git), sinon dans
`identites_clipping.json` à côté de ce fichier. Appliqué UNE fois au démarrage (trace par id sur le volume), bilan au salon admin :

[{"id", "prenom",
  "salons": [créatrice principale, autres…],         # bot_discord.ouvrir_salons_clipping : un salon par créatrice
  "renommer": [[onglet, ancien, nouveau], …],         # onboarding.renommer_compte (classeur, fiche, journal), dans l'ordre
  "renommer_classeur": [[onglet, ancien, nouveau]],   # @ seul (classeur + fiche), quand le journal ne peut pas suivre
  "renommer_suite": [[onglet, ancien, nouveau]],      # comme « renommer », après « renommer_classeur »
  "comptes": {créatrice: [@1, @2, @privé]},           # le trio de CETTE identité, le privé en dernier
  "remis": {créatrice: n},                            # autre créatrice : comptes déjà sur son téléphone
  "ban": [@…],                                        # cramés : ETAT BAN, rendus (Gérant vidé)
  "lien": {créatrice: url},                           # autre créatrice : son lien déjà attribué
  "simple": true}]                                    # son parcours principal passe à la règle des 48 h

Le Gérant des lignes d'un trio devient « Prénom Clipping Créatrice ». Ses autres lignes « Prénom Clipping Créatrice » de l'onglet
sont rendues au stock (Gérant vidé). Une ligne « Metricool » n'entre jamais dans un trio et n'est jamais touchée.
Le journal des places (process_store) reçoit l'historique des trios (reconcile) : trois places à vie par identité.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import google_api
import onboarding
import parcours

journal = logging.getLogger("bot.identites_clipping")
FICHIER = Path(__file__).parent / "identites_clipping.json"
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, DONNEES, FICHIER_EQUIPES, membre_par_prenom, ouvrir_salons, notifier."""
    _deps.update(deps)


def _n(t) -> str:
    return onboarding._norm(str(t or ""))


def _h(t) -> str:
    return onboarding.normaliser_handle(str(t or "")).lower()


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _renommer_classeur(uid: str, onglet: str, ancien: str, nouveau: str) -> str:
    """Le @ d'une ligne de SON trio, dans le classeur et sa fiche (accès des deux créatrices, livraisons), sans le journal des places
    (un alias déjà rattaché à un autre de ses comptes y bloquerait). Renvoie la ligne de bilan."""
    tous = await onboarding.lire_comptes()
    if any(_h(c["handle"]) == _h(nouveau) for c in tous):
        return f"= `{nouveau}` déjà au classeur"
    lignes = [c for c in tous if _n(c.get("onglet")) == _n(onglet) and _h(c["handle"]) == _h(ancien)]
    if len(lignes) != 1:
        return f"⚠️ `{ancien}` absent ou en double dans l'onglet {onglet}"
    ligne = lignes[0]
    if "metricool" in _n(ligne.get("gerant")):
        return f"⚠️ `{ancien}` est une ligne Metricool : pas touché"
    await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, onboarding.cellule(ligne, "handle"), [[_h(nouveau)]])
    etat = onboarding._lire_etat()
    fiche = etat["clippers"].setdefault(uid, {})
    fiche["comptes"] = [_h(nouveau) if _h(h) == _h(ancien) else h for h in fiche.get("comptes") or []]
    for a in list(fiche.get("acces") or []) + [x for t in (fiche.get("telephones") or {}).values() if isinstance(t, dict)
                                               for x in t.get("acces") or []]:
        if isinstance(a, dict) and _h(a.get("handle")) == _h(ancien):
            a["handle"] = _h(nouveau)
    livres = etat.setdefault("livres", {})
    for cle in [k for k in livres if _h(k) == _h(ancien)]:
        livres[_h(nouveau)] = livres.pop(cle)
    onboarding._ecrire_etat(etat)
    return f"✏️ {onglet} : `{ancien}` → `{nouveau}`"


async def _renommer_journal(uid: str, renommages: list) -> list:
    """[[onglet, ancien, nouveau]] par onboarding.renommer_compte (classeur, fiche, journal des places) ; si le journal refuse, le @
    seul (classeur et fiche)."""
    lignes = []
    for onglet, ancien, nouveau in renommages:
        fiche = onboarding._lire_etat()["clippers"].get(uid) or {}
        propres = {_h(h) for h in list(fiche.get("comptes") or []) + onboarding.handles_telephones(fiche)}
        if _h(nouveau) in propres and _h(ancien) not in propres:
            lignes.append(f"= `{ancien}` → `{nouveau}` déjà fait")
            continue
        try:
            raison = await onboarding.renommer_compte(uid, ancien, nouveau)
        except RuntimeError as erreur:
            raison = str(erreur)[:120]
        if raison:
            lignes.append(f"⚠️ `{ancien}` → `{nouveau}` par le journal : {raison} ; repli sur le classeur")
            lignes.append(await _renommer_classeur(uid, onglet, ancien, nouveau))
        else:
            lignes.append(f"✏️ {onglet} : `{ancien}` → `{nouveau}`")
    return lignes


async def _trio(uid: str, prenom: str, creatrice: str, handles: list, principale: str, entree: dict) -> list:
    """Le trio d'une identité : Gérant au classeur, fiche (parcours principal ou « telephones »), lignes en trop rendues."""
    gerant = f"{prenom} Clipping {creatrice}"
    tous = await onboarding.lire_comptes()
    onglet = [c for c in tous if _n(c.get("onglet")) == _n(creatrice)]
    trio = []
    for h in handles:
        lignes = [c for c in onglet if _h(c["handle"]) == _h(h)]
        if len(lignes) != 1:
            return [f"⚠️ {creatrice} : `{h}` absent ou en double dans l'onglet, trio non appliqué"]
        trio.append(lignes[0])
    if any("metricool" in _n(c.get("gerant")) or "metricool" in _n(c.get("utilisation")) for c in trio):
        return [f"⚠️ {creatrice} : un compte Metricool dans le trio, non appliqué"]
    proprietaires = onboarding._proprietaires()
    a_autrui = [c["handle"] for c in trio if (proprietaires.get(onboarding._cle_handle(c["handle"])) or {uid}) != {uid}]
    if a_autrui:
        return [f"⚠️ {creatrice} : {', '.join(a_autrui)} déjà à un autre clipper, trio non appliqué"]
    cles_trio = {_h(c["handle"]) for c in trio}
    bans = {_h(x) for x in entree.get("ban") or []}
    ecritures, rendus = [], []
    for c in trio:
        if (c.get("gerant") or "").strip() != gerant:
            ecritures.append((onboarding.cellule(c, "gerant"), gerant))
    for c in onglet:
        if _h(c["handle"]) in cles_trio or "metricool" in _n(c.get("gerant")):
            continue
        if _n(c.get("gerant")) == _n(gerant) or (_h(c["handle"]) in bans and _n(prenom) in _n(c.get("gerant"))):
            ecritures.append((onboarding.cellule(c, "gerant"), ""))
            if _h(c["handle"]) in bans:
                ecritures.append((onboarding.cellule(c, "etat"), "BAN"))
            rendus.append(c["handle"])
    for plage, valeur in ecritures:
        await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, plage, [[valeur]])
    roles = [dict(c, role_confirme="prive" if i == len(trio) - 1 else "croissance") for i, c in enumerate(trio)]
    acces = onboarding.acces_ordonnes(roles)
    maintenant = _maintenant()
    etat = onboarding._lire_etat()
    fiche = etat["clippers"].setdefault(uid, {})
    livres = etat.setdefault("livres", {})
    if _n(creatrice) == _n(principale):
        retires = [h for h in fiche.get("comptes") or [] if _h(h) not in cles_trio]
        fiche["comptes"] = [c["handle"] for c in trio]
        fiche["acces"] = acces
        fiche["gerant"] = gerant
    else:
        tel = fiche.setdefault("telephones", {})
        cle = next((k for k in tel if _n(k) == _n(creatrice)), creatrice)
        avant = tel.get(cle) if isinstance(tel.get(cle), dict) else {}
        retires = [h for h in onboarding.handles_telephones(fiche, creatrice) if _h(h) not in cles_trio]
        remis = min(int((entree.get("remis") or {}).get(creatrice, 0) or 0), len(acces))
        ancien_dernier = (datetime.now(timezone.utc) - timedelta(hours=onboarding.TELEPHONE2_ATTENTE_H + 1)).isoformat(timespec="seconds")
        tel[cle] = {"acces": acces, "donnes": remis, "dernier": ancien_dernier if remis else "",
                    "lien": (entree.get("lien") or {}).get(creatrice) or avant.get("lien", "")}
    for c in trio:
        livres[_h(c["handle"])] = {"uid": uid, "date": maintenant}
    for h in rendus:
        if str((livres.get(_h(h)) or {}).get("uid") or "") == uid:
            livres.pop(_h(h), None)
    onboarding._ecrire_etat(etat)
    bilan = [f"🎬 {gerant} : " + " · ".join(f"`{c['handle']}`" for c in trio)]
    if retires:
        bilan.append(f"   sortis de cette identité : {', '.join(retires)}")
    if rendus:
        bilan.append(f"   rendus au stock : {', '.join(rendus)}" + (" (BAN noté)" if bans & {_h(x) for x in rendus} else ""))
    return bilan


def _historique(uid: str, entree: dict) -> str:
    """Les trios au journal des places (process_store.reconcile) : historique rapproché, comptes déjà créés ou réservés."""
    registre = onboarding.process_adapters.store()
    comptes = []
    for creatrice, handles in (entree.get("comptes") or {}).items():
        for i, h in enumerate(handles):
            deja = parcours.compte_deja_cree(uid, h)
            comptes.append({"aliases": [_h(h)], "status": "created" if deja else "reserved",
                            "evidence": f"identites-clipping:{entree.get('id')}:{creatrice}:{i + 1}"})
    registre.reconcile(uid, comptes, f"identites-clipping:{entree.get('id')}:decision-gaetan-24/10")
    import process_store
    return f"📒 Journal des places : {registre.counts(uid)} (max {process_store.places_a_vie(uid)})"


def _parcours_simple(uid: str) -> str:
    """Son parcours principal passe à la règle des 48 h ; le compte 2 est programmé s'il n'est pas encore parti."""
    d = parcours._lire()
    f = d.get(uid)
    if not isinstance(f, dict):
        return "⚠️ parcours principal introuvable"
    f["simple"] = f.get("simple") or _maintenant()
    dates = f.get("dates") or {}
    programme = f.setdefault("programme", [])
    if not dates.get("2") and not any(x.get("type") == "etape" for x in programme):
        programme.append({"quand": _maintenant(), "type": "etape", "n": 2})
    parcours._ecrire(d)
    return f"⏱️ Parcours principal : règle des 48 h (étape {f.get('etape', '?')})"


async def appliquer(entree: dict) -> list:
    prenom = str(entree.get("prenom") or "").strip()
    membre = _deps["membre_par_prenom"](_n(prenom)) if _deps.get("membre_par_prenom") else None
    if membre is None:
        raise LookupError(f"{prenom} introuvable ou plusieurs membres de ce prénom")
    uid = str(membre.id)
    principale = str((_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid) or {}).get("creatrice") or "")
    lignes = [f"**{prenom}** · créatrice principale : {principale or '?'}"]
    lignes += await _renommer_journal(uid, entree.get("renommer") or [])
    for onglet, ancien, nouveau in entree.get("renommer_classeur") or []:
        lignes.append(await _renommer_classeur(uid, onglet, ancien, nouveau))
    lignes += await _renommer_journal(uid, entree.get("renommer_suite") or [])
    for creatrice, handles in (entree.get("comptes") or {}).items():
        lignes += await _trio(uid, prenom, creatrice, handles, principale, entree)
    try:
        lignes.append(_historique(uid, entree))
    except RuntimeError as erreur:
        lignes.append(f"⚠️ Journal des places : {str(erreur)[:120]}")
    if entree.get("simple"):
        lignes.append(_parcours_simple(uid))
    if entree.get("salons") and _deps.get("ouvrir_salons"):
        lignes += await _deps["ouvrir_salons"](membre, list(entree["salons"]), "depot")
    return lignes


async def demarrage(client) -> list:
    await client.wait_until_ready()
    brut = os.environ.get("IDENTITES_CLIPPING_JSON", "").strip()
    if not brut and FICHIER.exists():
        brut = FICHIER.read_text(encoding="utf-8")
    if not brut or not _deps.get("DONNEES") or not onboarding.actif():
        return []
    try:
        entrees = json.loads(brut)
    except ValueError as erreur:
        journal.warning("Dépôt des identités de clipping illisible : %s", erreur)
        return []
    trace = _deps["DONNEES"] / "identites_clipping_faites.json"
    faits = _deps["lire_json"](trace, {})
    lignes = []
    for e in entrees if isinstance(entrees, list) else []:
        ident = str(e.get("id") or "")
        if not ident or ident in faits:
            continue
        try:
            bilan = await appliquer(e)
        except LookupError as erreur:
            lignes.append(f"⚠️ {e.get('prenom')} : {erreur}, réessayé au prochain démarrage")
            continue
        except Exception as erreur:                                     # noqa: BLE001 — jamais tuer le bot
            journal.exception("Identités de clipping de %s", e.get("prenom"))
            bilan = [f"⚠️ {e.get('prenom')} : {type(erreur).__name__} {str(erreur)[:160]}"]
        faits[ident] = {"date": _maintenant(), "bilan": bilan}
        _deps["ecrire_json"](trace, faits)
        journal.info("Identités de clipping %s : %s", ident, " | ".join(bilan))
        lignes += bilan
    if lignes and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Identités de clipping appliquées**\n" + "\n".join(lignes),
                                    client.guilds[0] if client.guilds else None)
        except Exception:                                               # noqa: BLE001
            pass
    return lignes
