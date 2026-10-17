"""Livraison initiale : refus rejouable, réponse incertaine rapprochée sans doublon."""
from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace

import discord
from process_store import Bloque


def empreinte(texte):
    return hashlib.sha256(texte.encode()).hexdigest()


async def envoyer_compte_1(store, salon, uid, texte, vue, *, cle=None, operation=None):
    cle = cle or 'message-compte1:' + str(uid)
    with store.lock(cle):
        job = store.get(cle)
        if job and job.get('salon') != str(salon.id):
            raise Bloque('Livraison dans un autre salon : rapprochement requis')
        if operation is not None and job and (
                job.get('operation') != operation or job.get('empreinte') != empreinte(texte)):
            raise Bloque('Opération de remise divergente : rapprochement requis')
        if job.get('message_id'):
            return SimpleNamespace(id=job['message_id'])
        if job.get('etat') == 'incertain':
            # Une absence dans cette fenêtre bornée ne permet jamais de renvoyer.
            permissions = salon.permissions_for(salon.guild.me)
            if not (permissions.view_channel and permissions.read_message_history):
                raise Bloque('Livraison incertaine : historique illisible, vérification humaine requise')
            apres = datetime.fromisoformat(job['debut'])
            async for message in salon.history(limit=100, after=apres, oldest_first=True):
                if message.author.id == salon.guild.me.id and empreinte(message.content) == job['empreinte']:
                    job['message_id'] = str(message.id)
                    job['etat'] = 'livre'
                    store.put(cle, job)
                    return message
            raise Bloque('Livraison incertaine : vérifier le salon avant tout renvoi')
        job = {'etat':'incertain', 'salon':str(salon.id), 'empreinte':empreinte(texte),
               'debut':datetime.now(timezone.utc).isoformat()}
        if operation is not None:
            job['operation'] = dict(operation)
        store.put(cle, job)  # durable avant le POST ; couvre aussi un arrêt du processus
        try:
            message = await salon.send(texte, view=vue, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as erreur:
            if erreur.status in (400, 401, 403, 404, 429):
                job['etat'] = 'refuse'  # refus explicite : aucun message accepté
                store.put(cle, job)
            raise
        job.update(etat='livre', message_id=str(message.id))
        store.put(cle, job)
        return message
