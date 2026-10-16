"""Collecte privée reprenable : SQLite ne reçoit que du contenu déjà masqué.

Pas de jeton, endpoint, permission nouvelle, pièce jointe ou embed exporté.
La couverture est celle du bot, pas une promesse d'accès à tout Discord.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import time
from datetime import datetime, timezone
import discord
from conversation_audit import sanitize_in_channel

_LOCKS = {}

async def collecter(guild, chemin, pages_max=100, decouverte_max=10, duree_max=45, volume_max=64*1024*1024):
    """Chaque page est validée atomiquement avec son curseur ; reprise sans doublon."""
    async with _LOCKS.setdefault(str(guild.id), asyncio.Lock()):
        return await _collecter(guild, chemin, pages_max, decouverte_max, duree_max, volume_max)

async def _collecter(guild, chemin, pages_max, decouverte_max, duree_max, volume_max):
    fin = time.monotonic() + duree_max
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
        db.execute('CREATE TABLE IF NOT EXISTS decouverte_v2 (id TEXT PRIMARY KEY, statut TEXT, curseur TEXT)')
        # Les statuts v1 ne prouvaient pas READ_MESSAGE_HISTORY : relecture bornée,
        # sans supprimer les messages déjà nettoyés (INSERT OR IGNORE).
        if not db.execute("SELECT 1 FROM meta WHERE cle='permissions_v2'").fetchone():
            db.execute("UPDATE salons SET statut='a_reprendre',curseur=?",(avant,))
            db.execute("INSERT INTO meta VALUES ('permissions_v2','1')")
        def borne():
            return (time.monotonic() >= fin or
                    db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0] >= volume_max)
        async def attendre(coro):
            return await asyncio.wait_for(coro,timeout=max(.001,min(10,fin-time.monotonic())))
        async def page(iterator):
            return [x async for x in iterator]
        def inscrire(cid):
            db.execute('INSERT OR IGNORE INTO salons(id,curseur) VALUES (?,?)',(str(cid),avant))
        def permission(c):
            try:
                droits=c.permissions_for(guild.me)
                return bool(droits.view_channel and droits.read_message_history)
            except (AttributeError, TypeError):
                return False
        channels = {str(c.id):c for c in guild.channels if hasattr(c,'history')}
        for cid in channels: inscrire(cid)
        actif=db.execute("SELECT statut FROM decouverte_v2 WHERE id='fils_actifs'").fetchone()
        if not borne() and (not actif or actif[0]!='complet'):
            try:
                for c in await attendre(guild.active_threads()):
                    inscrire(c.id)
                actifs='complet'
            except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                actifs=type(exc).__name__
            db.execute('INSERT OR REPLACE INTO decouverte_v2 VALUES (?,?,NULL)',('fils_actifs',actifs))
        db.commit()
        # Inventorier les sources avant de consommer le budget pour ne pas afficher
        # « complet » lorsque des sources n'ont même pas commencé.
        sources=[]
        for c in guild.channels:
            if not hasattr(c,'archived_threads'):continue
            modes=[{}]
            if isinstance(c,discord.TextChannel):modes += [{'private':True},{'private':True,'joined':True}]
            for mode in modes:
                key=str(c.id)+':'+json.dumps(mode,sort_keys=True)
                sources.append((key,c,mode))
                db.execute('INSERT OR IGNORE INTO decouverte_v2 VALUES (?, ?, NULL)',(key,'a_lire'))
        db.commit()
        pages_decouverte=0
        for key,c,mode in sources:
            statut,cursor=db.execute('SELECT statut,curseur FROM decouverte_v2 WHERE id=?',(key,)).fetchone()
            if statut=='complet':continue
            if not permission(c):
                db.execute("UPDATE decouverte_v2 SET statut='permissions_absentes' WHERE id=?",(key,));db.commit();continue
            while pages_decouverte<decouverte_max and not borne():
                before=None if not cursor else (discord.Object(id=int(cursor)) if mode.get('joined') else datetime.fromisoformat(cursor))
                try:
                    batch=await attendre(page(c.archived_threads(limit=50,before=before,**mode)))
                    nouveau=(str(batch[-1].id) if mode.get('joined') else batch[-1].archive_timestamp.isoformat()) if batch else cursor
                    statut='complet' if len(batch)<50 else ('a_reprendre' if nouveau!=cursor else 'curseur_bloque')
                except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                    db.execute('UPDATE decouverte_v2 SET statut=? WHERE id=?',(type(exc).__name__,key));db.commit();break
                pages_decouverte+=1
                with db:
                    for thread in batch:inscrire(thread.id)
                    db.execute('UPDATE decouverte_v2 SET statut=?,curseur=? WHERE id=?',(statut,nouveau,key))
                cursor=nouveau
                if statut!='a_reprendre':break
        pages=0
        # Les fils archivés sont résolus un par un : pas d'accumulation de leur
        # historique ni de tous leurs objets Discord en RAM.
        for cid,cursor,status in db.execute('SELECT id,curseur,statut FROM salons').fetchall():
            if pages>=pages_max or borne():break
            channel=channels.get(cid) or guild.get_channel_or_thread(int(cid))
            try:
                if channel is None:channel=await attendre(guild.fetch_channel(int(cid)))
            except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                db.execute("UPDATE salons SET statut='illisible',erreur=? WHERE id=?",(type(exc).__name__,cid));db.commit();continue
            if not permission(channel):
                db.execute("UPDATE salons SET statut='permissions_absentes',erreur='VIEW_CHANNEL/READ_MESSAGE_HISTORY' WHERE id=?",(cid,));db.commit();continue
            if status=='complet':continue
            while pages<pages_max and not borne():
                try:
                    batch=await attendre(page(channel.history(limit=100,before=discord.Object(id=int(cursor)),oldest_first=False)))
                except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                    db.execute('UPDATE salons SET statut=?,erreur=? WHERE id=?',('illisible',type(exc).__name__,cid));db.commit();break
                pages+=1
                with db:
                    for m in batch:
                        safe=sanitize_in_channel(m.content,channel)
                        row=dict(date=m.created_at.isoformat(),uid=str(m.author.id),bot=bool(m.author.bot),texte=safe,
                                 pieces_jointes=len(m.attachments),embeds_omis=len(m.embeds))
                        db.execute('INSERT OR IGNORE INTO messages VALUES (?,?,?)',(str(m.id),cid,json.dumps(row,ensure_ascii=False)))
                    if batch:cursor=str(min(m.id for m in batch))
                    status='complet' if len(batch)<100 else 'a_reprendre'
                    db.execute('UPDATE salons SET curseur=?,statut=?,erreur=NULL WHERE id=?',(cursor,status,cid))
                if status=='complet':break
        salons=[dict(id=i,statut=s,erreur=e,messages=n) for i,s,e,n in db.execute('SELECT s.id,s.statut,s.erreur,count(m.id) FROM salons s LEFT JOIN messages m ON s.id=m.salon GROUP BY s.id')]
        discovery=[dict(source=i,statut=s) for i,s in db.execute('SELECT id,statut FROM decouverte_v2')]
        return dict(avant=avant,salons=salons,decouverte=discovery,pages=pages,pages_decouverte=pages_decouverte,borne_atteinte=borne(),
                    complet=not borne() and all(s['statut']=='complet' for s in salons) and all(x['statut']=='complet' for x in discovery),
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
