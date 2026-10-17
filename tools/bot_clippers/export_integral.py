"""Export propriétaire privé, collecte séparée et livraison bornée reprenable."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
import discord
import audit_complet

_VERROUS = {}
BUDGET_ARCHIVE = 64 * 1024 * 1024
BUDGET_GLOBAL = 256 * 1024 * 1024


def verifier_budget(racine, nouveau=False):
    # Réserver pour chaque archive son plafond complet ET son journal de rollback.
    # Les autres archives/fichiers sont comptés à leur taille réelle, jamais effacés.
    fichiers = [p for p in Path(racine).rglob('*') if p.is_file()]
    archives = [p for p in fichiers if p.name.startswith('export-') and p.suffix == '.sqlite3']
    taille = sum(p.stat().st_size for p in fichiers)
    reserve = sum(max(0, 2 * BUDGET_ARCHIVE + 1024 * 1024 - p.stat().st_size) for p in archives)
    if taille + reserve + (2 * BUDGET_ARCHIVE + 1024 * 1024 if nouveau else 0) > BUDGET_GLOBAL:
        raise ValueError('Budget global réservé atteint : archives conservées, aucune collecte supplémentaire')


def livraison(chemin, apres, collecte_complete):
    with closing(sqlite3.connect(Path(chemin).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'").fetchone():
            return dict(collecte_complete=False, livraison_complete=False, messages_livres=0, messages_restants=0, borne_livraison=0, curseur_livre=apres)
        total, borne = db.execute('SELECT count(*),coalesce(max(rowid),0) FROM messages').fetchone()
        livres = db.execute('SELECT count(*) FROM messages WHERE rowid<=?', (apres,)).fetchone()[0]
    return dict(collecte_complete=collecte_complete, livraison_complete=bool(collecte_complete and livres == total),
                messages_livres=livres, messages_restants=total-livres, borne_livraison=borne, curseur_livre=apres)



def rapport_volume(chemin, debut):
    """Relire uniquement les transactions validées après SQLITE_FULL/rollback."""
    with closing(sqlite3.connect(Path(chemin).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        avant = db.execute("SELECT valeur FROM meta WHERE cle='avant'").fetchone() if 'meta' in tables else None
        salons = [dict(id=i, statut=s, erreur=e, messages=n) for i,s,e,n in db.execute(
            'SELECT s.id,s.statut,s.erreur,count(m.id) FROM salons s LEFT JOIN messages m ON s.id=m.salon GROUP BY s.id')
            ] if {'salons','messages'} <= tables else []
        decouverte = [dict(source=i, statut=s) for i,s in db.execute('SELECT id,statut FROM decouverte_v2')] if 'decouverte_v2' in tables else []
        total = db.execute('SELECT count(*) FROM messages').fetchone()[0] if 'messages' in tables else 0
        return dict(avant=avant[0] if avant else str(discord.utils.time_snowflake(datetime.fromisoformat(debut), high=False)),
                    salons=salons, decouverte=decouverte, messages_valides=total,
                    complet=False, borne_atteinte=True, arret='volume', plafond_octets=BUDGET_ARCHIVE,
                    limites=['Collecte interrompue au plafond SQLite ; seules les transactions validées sont disponibles',
                             'Découverte non garantie complète ; salons invisibles et MP exclus',
                             'Pièces jointes, embeds et composants omis ; masquage heuristique'])


def segments(chemin, apres=0, maximum=6_000_000):
    """Texte lisible, sans réinterpréter le Markdown ; pagination par rowid stable."""
    with closing(sqlite3.connect(Path(chemin).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'").fetchone():
            return
        contenu = bytearray()
        dernier = apres
        for numero, mid, salon, brut in db.execute('SELECT rowid,id,salon,contenu FROM messages WHERE rowid>? ORDER BY rowid', (apres,)):
            m = json.loads(brut)
            ligne = (f"\n--- Salon {salon} · message {mid} · {m['date']} · auteur {m['uid']} ---\n"
                     f"{m['texte']}\n[Pièces jointes omises : {m['pieces_jointes']} ; embeds omis : {m['embeds_omis']}]\n").encode()
            if contenu and len(contenu)+len(ligne)>maximum:
                yield dernier, bytes(contenu)
                contenu.clear()
            contenu.extend(ligne)
            dernier = numero
        if contenu:
            yield dernier, bytes(contenu)


def sauver(path, etat):
    temporaire = path.with_suffix('.tmp')
    with temporaire.open('w') as f:
        import os
        os.chmod(temporaire, 0o600)
        json.dump(etat, f)
        f.flush(); os.fsync(f.fileno())
    temporaire.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


async def commande(message, racine, args):
    """Le dispatch vérifie ADMIN_IDS ; le propriétaire est revérifié ici."""
    if message.guild is None or message.author.id != message.guild.owner_id:
        return
    if args not in ([], ['nouveau'], ['livrer']):
        await message.author.send('Usage : !audit-discussions export [nouveau|livrer]')
        return
    async with _VERROUS.setdefault(str(message.guild.id), asyncio.Lock()):
        racine = Path(racine)
        racine.mkdir(parents=True, exist_ok=True, mode=0o700)
        pointeur = racine / f'export-{message.guild.id}.json'
        await message.author.send('Export privé : vérification de la collecte et de sa couverture.')
        if args == ['livrer']:
            try:
                verifier_budget(racine)
            except ValueError:
                await message.author.send('Budget global dépassé : récupération de l’archive existante autorisée ; aucune nouvelle collecte.')
        else:
            verifier_budget(racine, nouveau=args == ['nouveau'])
        if args == ['nouveau']:
            ident = uuid4().hex
            etat = dict(fichier=f'export-{message.guild.id}-{ident}.sqlite3', proprietaire=str(message.author.id),
                        debut=datetime.now(timezone.utc).isoformat(), lot=ident, apres=0, partie=0)
            # Réserve immédiatement l'identité d'archive avant toute interruption.
            with (racine / etat['fichier']).open('xb') as f:
                import os
                os.chmod(f.name, 0o600)
            sauver(pointeur, etat)
        elif pointeur.is_file():
            etat = json.loads(pointeur.read_text())
        else:
            await message.author.send('Démarre une archive séparée : !audit-discussions export nouveau')
            return
        if etat['proprietaire'] != str(message.author.id) or Path(etat['fichier']).name != etat['fichier']:
            raise ValueError('Archive incompatible avec le propriétaire ou le serveur.')
        chemin = racine / etat['fichier']
        if args != ['livrer']:
            try:
                rapport = await audit_complet.collecter(message.guild, chemin, integral=True, volume_max=BUDGET_ARCHIVE)
            except sqlite3.OperationalError as erreur:
                if getattr(erreur, 'sqlite_errorcode', None) != sqlite3.SQLITE_FULL:
                    raise
                rapport = rapport_volume(chemin, etat['debut'])
            etat['rapport'] = rapport
            sauver(pointeur, etat)
        rapport = etat.get('rapport')
        if not rapport:
            await message.author.send('Collecte à reprendre : !audit-discussions export')
            return
        # Même une archive partielle reste livrable, explicitement qualifiée ;
        # elle ne devient complète que lorsque salons ET découverte sont terminés.
        manifeste = dict(debut=etat['debut'], coupure=discord.utils.snowflake_time(int(rapport['avant'])).isoformat(),
                         lot=etat.get('lot', etat['fichier']), livraison=livraison(chemin, etat['apres'], rapport['complet']), couverture=rapport,
                         format='Texte intégral après masquage ; pas de troncature volontaire.',
                         exclusions=['MP hors serveur', 'Salons invisibles au bot', 'Fichiers joints non téléchargés : compte uniquement',
                                     'Embeds et composants omis', 'URLs, coordonnées et contenus d’authentification masqués',
                                     'Secrets sans contexte : détection automatique non garantie'])
        await message.author.send('Manifeste : '+('complet' if rapport['complet'] else 'PARTIEL — collecte/découverte à reprendre ou accès manquant'),
            file=discord.File(io.BytesIO(json.dumps(manifeste, ensure_ascii=False, indent=2).encode()), filename='manifeste-export.json'))
        if args != ['livrer']:
            if rapport.get('arret') == 'volume':
                await message.author.send('Arrêt volume : pages validées conservées et livrables via `!audit-discussions export livrer`. Une revue du budget est nécessaire avant de poursuivre la collecte.')
            else:
                await message.author.send('Contenu disponible via `!audit-discussions export livrer`. Pour poursuivre la collecte : `!audit-discussions export`.')
            return
        nombre = 0
        for dernier, contenu in segments(chemin, etat['apres']):
            partie = etat['partie'] + 1
            await message.author.send(file=discord.File(io.BytesIO(contenu), filename=f"discussions-{etat.get('lot', etat['fichier'])}-{partie:05d}.txt"))
            etat.update(apres=dernier, partie=partie)
            sauver(pointeur, etat)
            nombre += 1
            if nombre == 3:
                break
        final = livraison(chemin, etat['apres'], rapport['complet'])
        await message.author.send(file=discord.File(io.BytesIO(json.dumps(dict(lot=etat.get('lot', etat['fichier']), **final), ensure_ascii=False, indent=2).encode()), filename='etat-livraison.json'))
        await message.author.send(f'{nombre} segment(s) envoyé(s). Répète `!audit-discussions export livrer` pour la suite. '
                                  'Après une coupure entre envoi et sauvegarde, le dernier segment peut être renvoyé.')
