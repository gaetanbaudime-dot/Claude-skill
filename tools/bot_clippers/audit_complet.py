"""Collecte privée reprenable : SQLite ne reçoit que du contenu déjà masqué.

Pas de jeton, endpoint, permission nouvelle, pièce jointe ou embed exporté.
La couverture est celle du bot, pas une promesse d'accès à tout Discord.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import discord
from conversation_audit import sanitize_in_channel

_LOCKS = {}

async def collecter(guild, chemin, pages_max=100):
    """Chaque page est validée atomiquement avec son curseur ; reprise sans doublon."""
    async with _LOCKS.setdefault(str(guild.id), asyncio.Lock()):
        return await _collecter(guild, chemin, pages_max)

async def _collecter(guild, chemin, pages_max):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(chemin, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(chemin,0o600)
    db = sqlite3.connect(chemin)
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
        CREATE TABLE IF NOT EXISTS salons (id TEXT PRIMARY KEY, curseur TEXT, statut TEXT DEFAULT 'a_lire', erreur TEXT);
        CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, salon TEXT, contenu TEXT);
        CREATE TABLE IF NOT EXISTS decouverte (id TEXT PRIMARY KEY, statut TEXT);
        ''')
        db.execute("INSERT OR IGNORE INTO meta VALUES ('guild',?)",(str(guild.id),))
        if db.execute("SELECT valeur FROM meta WHERE cle='guild'").fetchone()[0] != str(guild.id):
            raise ValueError('Archive liée à un autre serveur.')
        db.execute("INSERT OR IGNORE INTO meta VALUES ('avant',?)",(str(discord.utils.time_snowflake(datetime.now(timezone.utc), high=False)),))
        avant = db.execute("SELECT valeur FROM meta WHERE cle='avant'").fetchone()[0]
        db.commit()
        channels = {str(c.id):c for c in guild.channels if hasattr(c,'history')}
        try:
            for c in await guild.active_threads():
                channels[str(c.id)] = c
            actifs='complet'
        except (discord.Forbidden,discord.HTTPException) as exc:
            actifs=type(exc).__name__
        db.execute('INSERT OR REPLACE INTO decouverte VALUES (?,?)',('fils_actifs',actifs))
        db.commit()
        # La bibliothèque pagine les fils archivés jusqu'à épuisement (limit=None).
        # Refaire la découverte à chaque reprise évite un inventaire partiel figé après erreur.
        for c in guild.channels:
            if not hasattr(c,'archived_threads'):
                continue
            modes = [{}]
            if isinstance(c,discord.TextChannel):
                modes += [{'private':True}, {'private':True,'joined':True}]
            for mode in modes:
                key = str(c.id)+':'+json.dumps(mode,sort_keys=True)
                try:
                    async for thread in c.archived_threads(limit=None,**mode):
                        channels[str(thread.id)] = thread
                    statut='complet'
                except (discord.Forbidden,discord.HTTPException) as exc:
                    statut=type(exc).__name__
                db.execute('INSERT OR REPLACE INTO decouverte VALUES (?,?)',(key,statut))
                db.commit()
        for cid in channels:
            db.execute('INSERT OR IGNORE INTO salons(id,curseur) VALUES (?,?)',(cid,avant))
        db.commit()
        pages=0
        for cid,channel in channels.items():
            cursor,status=db.execute('SELECT curseur,statut FROM salons WHERE id=?',(cid,)).fetchone()
            if status=='complet':
                continue
            while pages < pages_max:
                try:
                    batch=[m async for m in channel.history(limit=100,before=discord.Object(id=int(cursor)),oldest_first=False)]
                except (discord.Forbidden,discord.HTTPException) as exc:
                    db.execute('UPDATE salons SET statut=?,erreur=? WHERE id=?',('illisible',type(exc).__name__,cid))
                    db.commit()
                    break
                pages+=1
                with db:
                    for m in batch:
                        # Embeds, champs, composants, pièces jointes, mentions de nom et
                        # messages cités ne sont jamais copiés, même pour le nettoyeur.
                        safe = sanitize_in_channel(m.content, channel)
                        row=dict(date=m.created_at.isoformat(),uid=str(m.author.id),bot=bool(m.author.bot),texte=safe,
                                 pieces_jointes=len(m.attachments),embeds_omis=len(m.embeds))
                        db.execute('INSERT OR IGNORE INTO messages VALUES (?,?,?)',(str(m.id),cid,json.dumps(row,ensure_ascii=False)))
                    if batch:
                        cursor=str(min(m.id for m in batch))
                    status='complet' if len(batch)<100 else 'a_reprendre'
                    db.execute('UPDATE salons SET curseur=?,statut=?,erreur=NULL WHERE id=?',(cursor,status,cid))
                if status=='complet':
                    break
        salons=[dict(id=i,statut=s,erreur=e,messages=n) for i,s,e,n in db.execute('SELECT s.id,s.statut,s.erreur,count(m.id) FROM salons s LEFT JOIN messages m ON s.id=m.salon GROUP BY s.id')]
        discovery=[dict(source=i,statut=s) for i,s in db.execute('SELECT * FROM decouverte')]
        return dict(avant=avant,salons=salons,decouverte=discovery,pages=pages,
                    complet=all(s['statut']=='complet' for s in salons) and all(x['statut']=='complet' for x in discovery),
                    limites=['MP non inclus','Salons invisibles au bot non énumérables','Embeds, composants et pièces jointes omis','Masquage prudent : texte perdu possible ; pas de garantie sur un secret sans contexte'])
    finally:
        db.close()

async def commande(message, chemin):
    """Appelé exclusivement après le contrôle ADMIN_IDS existant. Aucun envoi public."""
    if message.guild is None:
        await message.author.send('Lance cette commande dans le serveur concerné.')
        return
    await message.author.send('Audit privé en lecture seule : collecte ou reprise, 100 pages maximum par invocation. Aucun contenu exporté automatiquement.')
    rapport=await collecter(message.guild,chemin)
    import io
    await message.author.send('Couverture uniquement. Relance `!audit-discussions complet` si des salons restent à reprendre. Le contenu nettoyé reste sur le volume privé du bot.',
                              file=discord.File(io.BytesIO(json.dumps(rapport,ensure_ascii=False,indent=2).encode()),filename='couverture-audit.json'))
