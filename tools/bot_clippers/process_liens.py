"""Préparation reprenable GAML/MYM/OF. Les adaptateurs réseau sont injectés."""
from process_store import Bloque


async def preparer(store, uid, creatrice, api):
    key = 'liens:' + str(uid) + ':' + creatrice.casefold()
    with store.lock('allocations-liens'):
        if store.get('sortie:' + str(uid)):
            raise Bloque('Départ enregistré : nouvelle allocation de liens bloquée')
        job = store.get(key)
        if job.get('archive'):
            raise Bloque('Lien archivé : jamais réattribué')
        if not job:
            # Inventaire lu AVANT de réserver : toutes les destinations actives/archivées.
            choix = await api.capacite(creatrice)
            if not all(choix.get(k) for k in ('mym', 'of', 'modele')):
                raise Bloque('Capacité MYM/OF ou modèle GAML manquante')
            job = store.claim_job(key, {**choix, 'phase': 'reserve', 'uid': str(uid), 'creatrice': creatrice})
        if not job.get('lid'):
            if job['phase'] == 'clone_incertain':
                # POST non idempotent : absence de réponse ≠ absence de clone.
                raise Bloque('Résultat du clone inconnu : rapprochement GAML requis, aucun nouveau clone')
            # GET/validation sans effet : reste réessayable si ce contrôle échoue.
            await api.preparer_clone(job['modele'])
            job['phase'] = 'clone_incertain'
            store.put(key, job)
            clone = await api.cloner(job['modele'])
            if not clone.get('id'):
                raise Bloque('Réponse du clone incomplète : rapprochement requis')
            job.update(lid=clone['id'], lien=clone.get('url', ''), phase='clone')
            store.put(key, job)  # sauvegardé avant activation, note ou cartes
        await api.configurer(job['lid'], str(uid))
        for kind in ('mym', 'of'):
            # Relecture distante avant chaque reprise : PATCH seulement si nécessaire.
            await api.poser(job['lid'], kind, job[kind])
            job[kind + '_pose'] = True
            store.put(key, job)
        if not await api.verifier(job):
            raise Bloque('Destinations GAML non vérifiées : livraison bloquée')
        await api.marquer_capacite(job)
        job['phase'] = 'pret'
        store.put(key, job)
        return job


async def depart(store, uid, api):
    """Archiver X → préparer Metricool → exclusion. Aucun effacement d'historique."""
    key = 'sortie:' + str(uid)
    with store.lock('allocations-liens'), store.lock(key):
        job = store.get(key)
        if job.get('phase') == 'termine':
            return job
        if not job:
            job = {'phase': 'inventaire'}
            store.put(key, job)  # interdit les allocations avant le premier appel externe
        if 'liens' not in job:
            job.update(liens=await api.liens(str(uid)), phase='prepare')
            store.put(key, job)
        for lid in job['liens']:
            # PATCH idempotent, relu même si succès local : aucune confiance dans un timeout.
            await api.archiver_x(lid)
        job['phase'] = 'archive'
        store.put(key, job)
        await api.preparer_metricool(str(uid), job['liens'])
        job['phase'] = 'metricool'
        store.put(key, job)
        if not job.get('exclu'):
            await api.exclure(str(uid))  # membre déjà absent = succès de l'adaptateur
            job.update(exclu=True, phase='termine')
            store.put(key, job)
        return job
