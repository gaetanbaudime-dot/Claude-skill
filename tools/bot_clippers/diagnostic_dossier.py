"""Diagnostic borné, sans secrets ni mutation, réservé au propriétaire administrateur."""
import io
import json
from pathlib import Path
import re
import sqlite3

import discord

_NON_FOURNI = object()


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


def affectations(onb, parcours):
    """Projection bornée des seuls champs d'affectation, jamais les accès."""
    onb, parcours = onb or {}, parcours or {}
    valid = lambda h: isinstance(h, str) and re.fullmatch(r'(?!\.)(?!.*\.$)[a-z0-9._]{1,30}', h)
    comptes = onb.get('comptes') if isinstance(onb.get('comptes'), list) else []
    acces = onb.get('acces') if isinstance(onb.get('acces'), list) else []
    return {'comptes': [h for h in comptes[:10] if valid(h)], 'tronque': len(comptes) > 10 or len(acces) > 10,
            'acces_roles': [{'handle': a['handle'],
                            'role_confirme': a.get('role_confirme') if a.get('role_confirme') in {'croissance', 'prive'} else None,
                            'prive_metadata': a.get('prive') if isinstance(a.get('prive'), bool) else None}
                           for a in acces[:10] if isinstance(a, dict) and valid(a.get('handle'))],
            'ordre': parcours.get('ordre') if parcours.get('ordre') in {'prive2', 'prive3'} else None,
            'ordre_confirme': (parcours.get('ordre_confirme') or {}).get('valeur')
            if isinstance(parcours.get('ordre_confirme'), dict)
            and parcours['ordre_confirme'].get('valeur') in {'prive2', 'prive3'} else None,
            'sante_et_visibilite': 'Non évaluées par ce diagnostic ; aucun rôle déduit du suffixe.'}


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


def rapport(root, uid, attendue, tl_attendu, *, parcours_source=_NON_FOURNI):
    root = Path(root)
    pipe = fiche(lire(root / 'pipeline.json'), 'etats', uid)
    onb = fiche(lire(root / 'onboarding.json'), 'clippers', uid)
    parcours = parcours_source if parcours_source is not _NON_FOURNI else fiche(lire(root / 'parcours.json'), uid)
    choix = fiche(pipe, 'decision_creatrice')
    attentes = (pipe or {}).get('creatrice_attendue')
    tl = fiche(lire(root / 'tl_colonne.json'), 'va')
    messages = fiche(parcours, 'messages') or {}
    return {'uid': uid, 'attendu': {'creatrice': attendue, 'tl_id': tl_attendu},
            'registre_equipes': resume(fiche(lire(root / 'equipes.json'), uid), attendue),
            'onboarding': resume(onb, attendue), 'parcours': resume(parcours, attendue),
            'affectations': affectations(onb, parcours),
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


async def commande(message, texte, root, admin_ids, est_staff=lambda membre:False):
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
    # Même source que verifier_etat : jamais la créatrice attendue de la commande.
    parcours_reel = fiche(lire(Path(root) / 'parcours.json'), args[0])
    creatrice_reelle = (parcours_reel or {}).get('creatrice', '')
    data = rapport(root, *args, parcours_source=parcours_reel)
    sid = data['parcours'].get('salon_id') or data['registre_equipes'].get('salon_id')
    data['lecteurs_discord'] = {'lecture': 'salon_non_identifie'}
    if sid:
        try:
            import remise_compte1
            salon = await message.guild.fetch_channel(int(sid))
            if salon.guild.id != message.guild.id:
                raise ValueError('Salon hors serveur')
            data['lecteurs_discord'] = {'lecture': 'reussie', 'salon_id': sid,
                'source_creatrice': 'parcours', 'creatrice_attendue': args[1],
                'creatrice_divergente': str(creatrice_reelle).casefold() != args[1].casefold() if creatrice_reelle else None,
                **remise_compte1.diagnostic_lecteurs(message.guild, salon, args[0], creatrice_reelle, admin_ids, est_staff)}
        except Exception as erreur:
            data['lecteurs_discord'] = {'lecture': 'indisponible', 'erreur_type': type(erreur).__name__}
    fichier = discord.File(io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode()), filename='diagnostic-dossier.json')
    await message.author.send(file=fichier)
    return True
