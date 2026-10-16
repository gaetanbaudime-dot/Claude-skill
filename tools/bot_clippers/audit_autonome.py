"""Producteur borné, désactivé par défaut. Aucun message à l'équipe, aucune proposition appliquée."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import discord
import audit_complet
import audit_diagnostic

MAX_TRANCHES = 4
SECONDES_TRANCHE = 45
INTERVALLE = 900
MAX_VOLUME = 256 * 1024 * 1024
MAX_LIGNES = 100000
_LOCKS = {}


def sauver(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def lire(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())  # Un état corrompu bloque, jamais remise à zéro implicite.


def empreinte(r):
    donnees = {'messages':sum(s.get('messages',0) for s in r.get('salons',[])),
               'salons':[(s['id'],s['statut']) for s in r.get('salons',[])],
               'decouverte':[(s['source'],s['statut']) for s in r.get('decouverte',[])]}
    return hashlib.sha256(json.dumps(donnees,sort_keys=True).encode()).hexdigest()


def configuration():
    """Paramètres non secrets ; preuves à renseigner seulement après vérification réelle."""
    return dict(actif=os.environ.get('AUDIT_AUTONOME_ACTIF')=='1',
                destinataires_verifies=os.environ.get('AUDIT_DESTINATAIRES_VERIFIES_REF',''),
                lecture_cloud_prouvee=os.environ.get('AUDIT_LECTURE_CLOUD_REF',''),
                classeur_approuve=os.environ.get('AUDIT_CLASSEUR_APPROUVE',''),
                serveur=os.environ.get('AUDIT_SERVEUR_ID',''))


async def tour(guild, dossier, config, transport, *, amorcage=False,
               collecter=audit_complet.collecter, diagnostiquer=audit_diagnostic.diagnostic,
               maintenant=time.time):
    """Au plus quatre tranches et quatre pages exportées ; état durable avant tout effet externe."""
    if str(guild.id) != str(config.get('serveur') or ''):
        return {'statut':'serveur_non_approuve'}
    if not config.get('destinataires_verifies'):
        return {'statut':'destination_non_verifiee'}
    if not amorcage and not (config.get('actif') and config.get('lecture_cloud_prouvee')):
        return {'statut':'inactif_ou_source_non_lue'}
    async with _LOCKS.setdefault(str(guild.id),asyncio.Lock()):
        root=Path(dossier)
        state_path=root/f'{guild.id}-producteur.json'
        state=lire(state_path)
        if state.get('prochain',0)>maintenant():
            return {'statut':'backoff','prochain':state['prochain']}
        if sum(p.stat().st_size for p in root.glob('*.sqlite3'))>=MAX_VOLUME:
            return {'statut':'volume_atteint'}
        if not state.get('cycle'):
            # La photographie déjà en cours est reprise, pas remplacée.
            debut=state.get('dernier_avant',0)
            fin=str(discord.utils.time_snowflake(datetime.fromtimestamp(maintenant(),timezone.utc),high=False))
            if debut and int(fin)<=int(debut):
                return {'statut':'horloge_incoherente'}
            state['cycle']={'fichier':f'{guild.id}.sqlite3' if not debut else f'{guild.id}-delta-{fin}.sqlite3',
                            'apres':str(max(0,int(debut)-1)),'avant':None if not debut else fin,
                            'curseur_export':0,'lignes':0,'manifeste':state.get('manifestes',0)+2}
            sauver(state_path,state)
        cycle=state['cycle'];path=root/cycle['fichier']
        rapport=cycle.get('rapport')
        if not (rapport or {}).get('complet'):
            precedent=cycle.get('empreinte')
            for _ in range(MAX_TRANCHES):
                try:
                    rapport=await asyncio.wait_for(collecter(guild,path,pages_max=100,decouverte_max=10,
                        duree_max=SECONDES_TRANCHE,apres=int(cycle['apres']),avant_fixe=cycle['avant']),SECONDES_TRANCHE+1)
                except (TimeoutError,discord.HTTPException):
                    state['prochain']=maintenant()+INTERVALLE
                    sauver(state_path,state)
                    return {'statut':'reprise_differee','prochain':state['prochain']}
                cycle['rapport']=rapport;cycle['avant']=rapport['avant']
                actuel=empreinte(rapport);cycle['empreinte']=actuel
                sauver(state_path,state)
                if rapport['complet'] or actuel==precedent:
                    break
                precedent=actuel
            # Backoff minimal du producteur : aucun spin sur une source sans progrès.
            state['prochain']=maintenant()+INTERVALLE
            sauver(state_path,state)
        if rapport is None:
            return {'statut':'aucun_rapport'}
        lot=str(cycle['avant'])
        # Couverture partielle publiée sans texte libre ; un lot n'est prêt qu'après toutes ses lignes.
        await transport.couverture(cycle['manifeste'],lot,rapport,False)
        if not rapport['complet']:
            return {'statut':'collecte_partielle','rapport':rapport}
        for _ in range(MAX_TRANCHES):
            diag=diagnostiquer(path,apres=cycle['curseur_export'],limite=1000)
            rows=transport.lignes(lot,diag)
            offset=state.get('lignes_publiees',0)+cycle['lignes']
            if offset+len(rows)>MAX_LIGNES:
                return {'statut':'capacite_transport_atteinte'}
            # Même plage et mêmes valeurs après une réponse réseau incertaine.
            if rows:
                await transport.signaux(offset+2,rows)
            cycle['lignes']+=len(rows);cycle['curseur_export']=diag['curseur_suivant']
            sauver(state_path,state)
            if not diag['reste']:
                await transport.couverture(cycle['manifeste'],lot,rapport,True)
                state.update(dernier_avant=lot,lignes_publiees=offset+len(rows),
                             manifestes=state.get('manifestes',0)+1,prochain=maintenant()+INTERVALLE)
                state.pop('cycle');sauver(state_path,state)
                return {'statut':'lot_publie','lot':lot}
        return {'statut':'export_partiel','lot':lot}


async def boucle(client,dossier,transport_factory):
    """Une seule tâche, cadence technique de 15 min ; aucun calendrier de propositions ici."""
    await client.wait_until_ready()
    while not client.is_closed():
        config=configuration()
        if config.get('actif') and config.get('lecture_cloud_prouvee') and config.get('destinataires_verifies'):
            for guild in [g for g in client.guilds if str(g.id)==str(config.get('serveur'))]:
                try:
                    await tour(guild,dossier,config,transport_factory())
                except Exception:
                    # Pas de corps de réponse, identifiant d'accès ou texte de message dans les logs.
                    import logging
                    logging.getLogger(__name__).warning('Audit autonome : passage interrompu, checkpoint conservé')
        await asyncio.sleep(INTERVALLE)
