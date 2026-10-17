"""Diagnostic borné, sans secrets ni mutation, réservé au propriétaire administrateur."""
import io
import json
from pathlib import Path
import re
import sqlite3

import discord


def identifiant(value):
    value = str(value or '')
    return value if re.fullmatch(r'[0-9]{1,22}', value) else None


def lire(path):
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            return None
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def fiche(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data if isinstance(data, dict) else None


def resume(data, attendue):
    if data is None:
        return {'lecture': 'absente_ou_illisible'}
    creatrice = data.get('creatrice')
    return {'lecture': 'presente', 'choix_present': bool(creatrice),
            'choix_conforme': str(creatrice or '').casefold() == attendue.casefold() if creatrice else None,
            'salon_id': identifiant(data.get('salon_id'))}


def registre(path, uid):
    inconnu = {'lecture': 'absente_ou_illisible', 'historique_rapproche': None, 'comptes_observes': None}
    if path.is_symlink() or not path.is_file():
        return inconnu
    db = None
    try:
        # Ne pas instancier Store : son constructeur crée le schéma et ouvre une transaction d’écriture.
        db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        preuve = db.execute('SELECT evidence FROM histories WHERE uid=?', (uid,)).fetchone()
        comptes = db.execute('SELECT status,COUNT(*) FROM accounts WHERE uid=? GROUP BY status', (uid,)).fetchall()
        counts = {s: n for s, n in comptes if s in {'created', 'reserved', 'unknown', 'cancelled'}}
        row = db.execute('SELECT data FROM jobs WHERE key=?', ('message-compte1:' + uid,)).fetchone()
        job = json.loads(row[0]) if row else {}
        if not isinstance(job, dict):
            job = {}
        return {'lecture': 'presente', 'historique_rapproche': bool(preuve and preuve[0]),
                'comptes_observes': counts, 'total_crees_a_vie': counts.get('created', 0) if preuve and preuve[0] and not counts.get('unknown') and all(s in counts for s, _ in comptes) else None,
                'statuts_non_reconnus': any(s not in counts for s, _ in comptes),
                'message_compte1_id': identifiant(job.get('message_id')),
                'salon_compte1_id': identifiant(job.get('salon')),
                'livraison': job.get('etat') if job.get('etat') in {'incertain', 'refuse', 'livre'} else None}
    except (sqlite3.Error, ValueError, OSError):
        return inconnu
    finally:
        if db is not None:
            db.close()


def rapport(root, uid, attendue, tl_attendu):
    root = Path(root)
    pipe = fiche(lire(root / 'pipeline.json'), 'etats', uid)
    onb = fiche(lire(root / 'onboarding.json'), 'clippers', uid)
    parcours = fiche(lire(root / 'parcours.json'), uid)
    choix = fiche(pipe, 'decision_creatrice')
    attentes = (pipe or {}).get('creatrice_attendue')
    tl = fiche(lire(root / 'tl_colonne.json'), 'va')
    messages = fiche(parcours, 'messages') or {}
    return {'uid': uid, 'attendu': {'creatrice': attendue, 'tl_id': tl_attendu},
            'registre_equipes': resume(fiche(lire(root / 'equipes.json'), uid), attendue),
            'onboarding': resume(onb, attendue), 'parcours': resume(parcours, attendue),
            'reservation_onboarding_nombre': len(onb['comptes']) if onb and isinstance(onb.get('comptes'), list) else None,
            'attente_pipeline_conforme': str(attentes).casefold() == attendue.casefold() if attentes else None,
            'decision': {**resume(choix, attendue), 'provenance_complete': bool(choix and all(choix.get(k) for k in ('source', 'par', 'date')))},
            'tl_colonne_id': identifiant((tl or {}).get(uid)),
            'tl_colonne_conforme': identifiant(tl[uid]) == tl_attendu if tl and uid in tl else None,
            'messages_parcours': {k: identifiant(messages[k]) for k in ('1', '1p', '2', '2p', '3', '3p', '4', '5') if k in messages},
            'processus': registre(root / 'process_clippeur.sqlite3', uid),
            'limites': ['Instantanés JSON non atomiques entre fichiers.',
                        'TL : cache de colonne seulement, ni organigramme effectif ni permissions Discord.',
                        'Aucun rapprochement ou correction effectué ; absence ne vaut jamais zéro historique.',
                        'Comptes observés et réservations ne prouvent pas la publication de Reels.']}


async def commande(message, texte, root, admin_ids):
    if texte.split()[:1] != ['!diagnostic-dossier']:
        return False
    # Aucun retour public, aucune lecture avant les deux contrôles existants.
    if (message.guild is None or str(message.author.id) not in admin_ids
            or message.author.id != message.guild.owner_id):
        return True
    args = texte.split()[1:]
    if len(args) != 3 or not identifiant(args[0]) or args[1] not in {'Sarah', 'Chloé'} or not identifiant(args[2]):
        await message.author.send('Usage : !diagnostic-dossier UID Sarah|Chloé UID_TL')
        return True
    data = rapport(root, *args)
    fichier = discord.File(io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode()), filename='diagnostic-dossier.json')
    await message.author.send(file=fichier)
    return True
