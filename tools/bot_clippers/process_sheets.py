"""Restitution des liens vérifiés : lecture par identité, aucune création GAML."""
from process_store import Bloque

CHAMPS = {'lien_gaml': 'lien', 'lien_mym': 'mym', 'lien_infloww': 'of'}


def verifier_job(registre, uid, creatrice, job):
    key = 'liens:' + str(uid) + ':' + creatrice.casefold()
    if (not job or job.get('phase') != 'pret' or job.get('archive')
            or str(job.get('uid')) != str(uid) or job.get('creatrice') != creatrice
            or registre.get('sortie:' + str(uid))):
        raise Bloque('liens_non_prets')
    if any(not str(job.get(k) or '').startswith('https://') for k in CHAMPS.values()):
        raise Bloque('destination_absente')
    if job['mym'] == job['of'] or any(registre.resource_owner(k, job[k]) != key for k in ('mym', 'of')):
        raise Bloque('reservation_divergente')


async def _synchroniser(registre, uid, creatrice, api):
    """Retourne les conflits sans URL ni secret. Chaque reprise relit les cellules.

    Google Sheets ne fournit pas de compare-and-swap sur ces valeurs : aucun tri ou
    éditeur concurrent sur ces cellules entre la relecture et l'écriture.
    """
    key = 'liens:' + str(uid) + ':' + creatrice.casefold()
    resultat = {'ecrits': 0, 'conflits': []}
    job = registre.get(key)
    verifier_job(registre, uid, creatrice, job)
    if not await api.verifier(job):
        raise Bloque('verification_gaml_echouee')
    lignes = await api.lignes()
    cibles = [r for r in lignes if api.appartient(r, uid, creatrice)]
    if not cibles:
        raise Bloque('aucune_ligne_attribuee_verifiee')
    for cible in cibles:
        identite = (cible.get('onglet'), cible.get('handle'))
        def conflit(raison):
            resultat['conflits'].append({'onglet': identite[0], 'handle': identite[1], 'raison': raison})
        # Relecture avant CHAQUE lot de cellules, jamais le numéro mémorisé.
        relues = await api.lignes()
        matches = [r for r in relues if (r.get('onglet'), r.get('handle')) == identite]
        if len(matches) != 1 or matches[0].get('doublons_ecartes'):
            conflit('identite_ambigue_ou_absente'); continue
        r = matches[0]
        actuel = registre.get(key)
        verifier_job(registre, uid, creatrice, actuel)
        if any(actuel.get(k) != job.get(k) for k in ('lid', 'lien', 'mym', 'of')):
            raise Bloque('allocation_modifiee')
        if (not api.appartient(r, uid, creatrice)
                or r.get('gerant') != cible.get('gerant')):
            conflit('attribution_modifiee'); continue
        if any(not api.colonne(k, r['onglet']) for k in CHAMPS):
            conflit('colonne_absente'); continue
        if any(k in (r.get('fusions') or {}) for k in CHAMPS):
            conflit('cellule_fusionnee'); continue
        if any(str(r.get(k) or '').strip() not in ('', job[v]) for k,v in CHAMPS.items()):
            conflit('destination_divergente'); continue
        changements = {k: job[v] for k,v in CHAMPS.items() if not str(r.get(k) or '').strip()}
        if changements:
            await api.ecrire(r, changements)
            apres = [x for x in await api.lignes() if (x.get('onglet'), x.get('handle')) == identite]
            if (len(apres) != 1 or not api.appartient(apres[0], uid, creatrice)
                    or any(str(apres[0].get(k) or '').strip() != job[v] for k,v in CHAMPS.items())):
                conflit('ecriture_non_confirmee'); continue
            resultat['ecrits'] += len(changements)
    return resultat


async def synchroniser(registre, uid, creatrice, api):
    with registre.lock('allocations-liens'):
        return await _synchroniser(registre, uid, creatrice, api)
