"""Déclaration propriétaire : rapprochement zéro sans allocation, preuves conservées."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timezone

from contextlib import closing
from process_store import Bloque

# Périmètre fourni à la commande par l'appelant ; aucune identité réelle dans ce module.
FICHIERS = ('pipeline.json', 'equipes.json', 'onboarding.json', 'parcours.json',
            'sortis.json', 'parcours_oublis.json')


def sources(root, uid):
    bruts, donnees = {}, {}
    for nom in FICHIERS:
        p = root / nom
        if p.is_symlink() or not p.is_file():
            raise Bloque('Source absente : rapprochement retenu')
        try:
            bruts[nom] = p.read_bytes()
            donnees[nom] = json.loads(bruts[nom])
        except (OSError, ValueError):
            raise Bloque('Source illisible : rapprochement retenu') from None
        attendu = list if nom == 'sortis.json' else dict
        if not isinstance(donnees[nom], attendu):
            raise Bloque('Source invalide : rapprochement retenu')
    onb = donnees['onboarding.json']
    if not isinstance(onb.get('clippers', {}), dict) or not isinstance(onb.get('livres', {}), dict):
        raise Bloque('Structure onboarding invalide')
    fiche = onb.get('clippers', {}).get(uid) or {}
    parcours = donnees['parcours.json'].get(uid) or {}
    if not isinstance(fiche, dict) or not isinstance(parcours, dict):
        raise Bloque('Dossier invalide')
    if any(fiche.get(k) for k in ('comptes', 'acces', 'telephones', 'lien', 'liens_prets', 'sorti', 'a_dire', 'remise_securisee')):
        raise Bloque('Trace de compte ou livraison : rapprochement zéro refusé')
    if any(not isinstance(v, dict) for v in onb.get('livres', {}).values()):
        raise Bloque('Historique de livraisons invalide')
    if any(str(v.get('uid')) == uid for v in (onb.get('livres') or {}).values() if isinstance(v, dict)):
        raise Bloque('Livraison historique : rapprochement zéro refusé')
    if (any(parcours.get(k) for k in ('comptes', 'profils', 'reels', 'reels_soir', 'dates'))
            or any(k != 'bienvenue' for k in (parcours.get('messages') or {}))):
        raise Bloque('Parcours de compte existant : rapprochement zéro refusé')
    if any(not isinstance(x, dict) for x in donnees['sortis.json']):
        raise Bloque('Historique de sorties invalide')
    if uid in donnees['parcours_oublis.json'] or any(str(x.get('uid')) == uid for x in donnees['sortis.json'] if isinstance(x, dict)):
        raise Bloque('Départ ou historique oublié : rapprochement zéro refusé')
    return bruts


def sauvegarder(root, database, bruts):
    """Snapshot privé, durable et relu ; toute erreur interdit la mutation."""
    dossier = Path(tempfile.mkdtemp(prefix='rapprochement-zero-', dir=root))
    os.chmod(dossier, 0o700)
    for nom, contenu in bruts.items():
        cible = dossier / nom
        with cible.open('xb') as f:
            os.chmod(cible, 0o600)
            f.write(contenu); f.flush(); os.fsync(f.fileno())
        if cible.read_bytes() != contenu:
            raise Bloque('Sauvegarde non confirmée')
    cible_db = dossier / database.name
    fd_db = os.open(cible_db, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd_db)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as origine:
        with closing(sqlite3.connect(cible_db)) as copie:
            origine.backup(copie)
            if copie.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise Bloque('Sauvegarde SQLite non confirmée')
    os.chmod(cible_db, 0o600)
    with cible_db.open('rb') as f:
        os.fsync(f.fileno())
    fd = os.open(dossier, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return dossier.name


def rapprocher(root, uid, preuve, cibles):
    """À appeler sous le verrou UID du bot. Verrou SQLite contre toute allocation concurrente."""
    root, uid = Path(root), str(uid)
    if uid not in cibles or type(preuve.get('total')) is not int or preuve.get('total') != 0 or preuve.get('uid') != uid:
        raise Bloque('Dossier hors périmètre ou déclaration zéro absente')
    if not all(isinstance(preuve.get(k), str) and preuve[k].strip() for k in ('source', 'par', 'date')):
        raise Bloque('Provenance propriétaire incomplète')
    try:
        date = datetime.fromisoformat(preuve['date'])
        if date.tzinfo is None or not preuve['source'].startswith('discord-message:') or not preuve['par'].isdigit():
            raise ValueError()
    except ValueError:
        raise Bloque('Provenance propriétaire invalide') from None
    database = root / 'process_clippeur.sqlite3'
    if database.is_symlink() or not database.is_file():
        raise Bloque('Registre absent : aucune initialisation implicite')
    bruts = sources(root, uid)
    db = sqlite3.connect(database, timeout=5, isolation_level=None)
    cle = 'rapprochement-zero:' + uid
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM accounts WHERE uid=? LIMIT 1', (uid,)).fetchone():
            raise Bloque('Compte ou réservation existante : zéro refusé')
        if db.execute('SELECT 1 FROM resources WHERE owner=? LIMIT 1', (uid,)).fetchone():
            raise Bloque('Ressource réservée : zéro refusé')
        for key, data in db.execute('SELECT key,data FROM jobs'):
            if key == cle:
                continue
            if uid in str(key) or uid in str(data):
                raise Bloque('Opération historique existante : zéro refusé')
        ancien = db.execute('SELECT evidence FROM histories WHERE uid=?', (uid,)).fetchone()
        journal = db.execute('SELECT data FROM jobs WHERE key=?', (cle,)).fetchone()
        if journal:
            enregistre = json.loads(journal[0])
            if enregistre.get('preuve') == preuve and ancien and ancien[0] == enregistre.get('historique_apres'):
                db.rollback()
                return 'deja_rapproche'
            raise Bloque('Rapprochement existant différent : revue requise')
        if sources(root, uid) != bruts:
            raise Bloque('Sources modifiées pendant la lecture')
        snapshot = sauvegarder(root, database, bruts)
        if sources(root, uid) != bruts:
            raise Bloque('Sources modifiées pendant la sauvegarde')
        historique = json.dumps({'type':'declaration_proprietaire_zero', 'preuve':preuve,
                                 'references_anterieures':[ancien[0]] if ancien else []}, ensure_ascii=False, sort_keys=True)
        entree = {'preuve':preuve, 'historique_apres':historique, 'sauvegarde':snapshot,
                  'etat':'attente_reprise_explicite'}
        db.execute('INSERT OR REPLACE INTO histories VALUES(?,?)', (uid, historique))
        db.execute('INSERT INTO jobs VALUES(?,?)', (cle, json.dumps(entree, ensure_ascii=False)))
        if db.execute('SELECT evidence FROM histories WHERE uid=?',(uid,)).fetchone() != (historique,):
            raise Bloque('Relecture du rapprochement non confirmée')
        db.commit()
        if db.execute('SELECT evidence FROM histories WHERE uid=?', (uid,)).fetchone() != (historique,):
            raise Bloque('Relecture après commit non confirmée')
        return 'rapproche_reprise_requise'
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


async def commande(message, texte, root, admin_ids, cibles):
    if texte.split()[:1] != ['!rapprocher-zero']:
        return False
    if message.guild is None or message.author.id != message.guild.owner_id or str(message.author.id) not in admin_ids:
        return True
    args = texte.split()[1:]
    if len(args) != 2 or args[0] not in cibles or args[1] != 'confirme-zero':
        await message.author.send('Usage limité aux dossiers autorisés : !rapprocher-zero UID confirme-zero')
        return True
    uid = args[0]
    import choix_creatrice
    preuve = {'uid':uid, 'total':0, 'source':f'discord-message:{message.id}', 'par':str(message.author.id),
              'date':message.created_at.astimezone(timezone.utc).isoformat()}
    try:
        async with choix_creatrice.verrou(uid):
            resultat = rapprocher(root, uid, preuve, cibles)
        await message.author.send('Rapprochement : '+resultat+'. Aucun compte alloué ; reprise !creatrice explicite nécessaire.')
    except (Bloque, OSError, sqlite3.Error, ValueError, TypeError):
        await message.author.send('Rapprochement retenu : source contradictoire/illisible, sauvegarde ou validation impossible. Aucun compte alloué ; revue nécessaire.')
    return True
