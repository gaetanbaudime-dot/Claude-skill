"""Résolution unique par UID ; aucune allocation, aucun rôle utilisé comme décision."""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import weakref
from datetime import datetime, timezone


class Divergence(RuntimeError):
    pass


# Une boucle par processus du bot ; réentrée uniquement pour la même tâche.
_verrous = weakref.WeakKeyDictionary()


@asynccontextmanager
async def verrou(uid):
    boucle = asyncio.get_running_loop()
    entrees = _verrous.setdefault(boucle, {})
    entree = entrees.setdefault(str(uid), {'lock': asyncio.Lock(), 'owner': None})
    tache = asyncio.current_task()
    if entree['owner'] is tache:
        yield
        return
    async with entree['lock']:
        entree['owner'] = tache
        try:
            yield
        finally:
            entree['owner'] = None


def resoudre(uid, fiche, info, proposition='', decision=None):
    """Une proposition n'est utilisable que si aucun choix durable ne la précède."""
    decision = decision if decision is not None else info.get('decision_creatrice')
    if decision:
        if not all(str(decision.get(k) or '').strip() for k in ('creatrice', 'source', 'par', 'date')):
            raise Divergence('Décision de créatrice sans provenance complète')
        return decision['creatrice']
    registre = str(fiche.get('creatrice') or '').strip()
    attente = str(info.get('creatrice_attendue') or '').strip()
    if registre and attente and registre.casefold() != attente.casefold():
        raise Divergence('Registre et attente divergent : décision sourcée requise')
    return registre or attente or proposition


def preparer(uid, proposition, lire, ecrire, fichier_pipeline, fichier_equipes,
             fichier_onboarding, decision=None, comptes_connus=None):
    """À appeler sous verrou(uid), avant tout effet externe. Écrit uniquement le choix et son attente."""
    uid = str(uid)
    pipe = lire(fichier_pipeline, None)
    registre = lire(fichier_equipes, None)
    onb = lire(fichier_onboarding, None)
    if not all(isinstance(d, dict) for d in (pipe, registre, onb)):
        raise Divergence('Sources du choix absentes ou illisibles')
    info = pipe.setdefault('etats', {}).setdefault(uid, {})
    fiche = registre.get(uid) or {}
    choix = resoudre(uid, fiche, info, proposition, decision)
    if not choix:
        raise Divergence('Créatrice non déterminée')
    ancienne = (onb.get('clippers') or {}).get(uid) or {}
    precedents = [fiche.get('creatrice'), info.get('creatrice_attendue'), ancienne.get('creatrice')]
    changement = any(c and str(c).casefold() != choix.casefold() for c in precedents)
    if changement and (comptes_connus is None or any(comptes_connus.values())):
        raise Divergence('Comptes historiques conservés : rapprochement requis avant changement')
    if ancienne.get('comptes') and str(ancienne.get('creatrice') or '').casefold() != choix.casefold():
        raise Divergence('Réservation ancienne conservée : rapprochement nécessaire')
    avant = deepcopy(pipe)
    if decision is not None:
        info['decision_creatrice'] = deepcopy(decision)
    info.update(etat='attente_attribution', creatrice_attendue=choix)
    info.setdefault('attente_depuis', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    if pipe != avant:
        ecrire(fichier_pipeline, pipe)
        if lire(fichier_pipeline, None) != pipe:
            raise Divergence('Écriture du choix non confirmée')
    # Une décision durable permet de reprendre une écriture partielle sans nouveau tirage.
    if fiche.get('creatrice') and fiche['creatrice'] != choix:
        fiche['creatrice'] = choix
        registre[uid] = fiche
        ecrire(fichier_equipes, registre)
        if lire(fichier_equipes, None) != registre:
            raise Divergence('Écriture du registre non confirmée')
    return choix
