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

class VolumeAtteint(RuntimeError):
    """Budget SQLite épuisé : transaction annulée, curseur antérieur conservé."""


def progression(salons, decouverte, pages, pages_max, pages_decouverte, decouverte_max, borne_atteinte):
    """Une borne temporelle non atteinte n'implique pas une découverte terminée."""
    reste_salons = sum(s['statut'] != 'complet' for s in salons)
    reste_decouverte = sum(d['statut'] != 'complet' for d in decouverte)
    raisons = []
    if borne_atteinte:
        raisons.append('borne_temps_ou_volume')
    if reste_salons and pages >= pages_max:
        raisons.append('budget_pages_messages')
    if reste_decouverte and pages_decouverte >= decouverte_max:
        raisons.append('budget_pages_decouverte')
    if (reste_salons or reste_decouverte) and not raisons:
        raisons.append('decouverte_ou_reprises_restantes')
    return dict(travail_restant={'salons': reste_salons, 'operations_decouverte': reste_decouverte},
                raisons_arret=raisons,
                instruction='Reprise nécessaire : la couverture reste incomplète.' if reste_salons or reste_decouverte
                else 'Tous les éléments identifiés sont terminés pour la borne avant indiquée.')


async def collecter(guild, chemin, pages_max=100, decouverte_max=10, duree_max=45, volume_max=64*1024*1024, apres=None, avant_fixe=None):
    """Chaque page est validée atomiquement avec son curseur ; reprise sans doublon."""
    async with _LOCKS.setdefault(str(guild.id), asyncio.Lock()):
        # Recalcul sous le verrou partagé avec les collectes manuelles.
        path=Path(chemin)
        total=sum(p.stat().st_size for p in path.parent.glob('*.sqlite3*'))
        taille=path.stat().st_size if path.exists() else 0
        volume_max=min(volume_max,taille+256*1024*1024-total-1024*1024)
        return await _collecter(guild, chemin, pages_max, decouverte_max, duree_max, volume_max, apres, avant_fixe)

async def _collecter(guild, chemin, pages_max, decouverte_max, duree_max, volume_max, apres=None, avant_fixe=None):
    fin = time.monotonic() + duree_max
    fin_decouverte = fin - duree_max * 2 / 3
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(chemin, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(chemin,0o600)
    db = sqlite3.connect(chemin)
    try:
        # Le moteur impose la limite à chaque allocation, y compris dans une page.
        # Pas de WAL ; journal en mémoire borné par la taille de la transaction.
        db.execute('PRAGMA journal_mode=MEMORY')
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        maximum = int(volume_max) // page_size
        if maximum < 16 or db.execute('PRAGMA page_count').fetchone()[0] > maximum:
            raise VolumeAtteint('volume_atteint')
        db.execute(f'PRAGMA max_page_count={maximum}')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
        CREATE TABLE IF NOT EXISTS salons (id TEXT PRIMARY KEY, curseur TEXT, statut TEXT DEFAULT 'a_lire', erreur TEXT);
        CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, salon TEXT, contenu TEXT);
        CREATE TABLE IF NOT EXISTS decouverte (id TEXT PRIMARY KEY, statut TEXT);
        ''')
        db.execute("INSERT OR IGNORE INTO meta VALUES ('guild',?)",(str(guild.id),))
        if db.execute("SELECT valeur FROM meta WHERE cle='guild'").fetchone()[0] != str(guild.id):
            raise ValueError('Archive liée à un autre serveur.')
        db.execute("INSERT OR IGNORE INTO meta VALUES ('avant',?)",(str(avant_fixe or discord.utils.time_snowflake(datetime.now(timezone.utc), high=False)),))
        db.execute("INSERT OR IGNORE INTO meta VALUES ('apres',?)",(str(apres or 0),))
        apres_stocke = db.execute("SELECT valeur FROM meta WHERE cle='apres'").fetchone()[0]
        if apres is not None and str(apres) != apres_stocke:
            raise ValueError('Borne incrémentale différente de cette collecte.')
        apres = int(apres_stocke)
        if avant_fixe is not None and str(avant_fixe) != db.execute("SELECT valeur FROM meta WHERE cle='avant'").fetchone()[0]:
            raise ValueError('Borne finale différente de cette collecte.')
        avant = db.execute("SELECT valeur FROM meta WHERE cle='avant'").fetchone()[0]
        db.commit()
        db.execute('CREATE TABLE IF NOT EXISTS decouverte_v2 (id TEXT PRIMARY KEY, statut TEXT, curseur TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS reprises (cle TEXT PRIMARY KEY, derniere REAL, apres REAL, echecs INTEGER)')
        def reprise(cle):
            return db.execute('SELECT derniere,apres,echecs FROM reprises WHERE cle=?',(cle,)).fetchone() or (0,0,0)
        def debut_tentative(cle):
            _,apres,echecs=reprise(cle)
            db.execute('INSERT OR REPLACE INTO reprises VALUES (?,?,?,?)',(cle,time.time(),apres,echecs));db.commit()
        def fin_tentative(cle,echec=False):
            derniere,_,echecs=reprise(cle)
            echecs=echecs+1 if echec else 0
            apres=time.time()+min(3600,60*(2**min(echecs-1,6))) if echec else 0
            db.execute('INSERT OR REPLACE INTO reprises VALUES (?,?,?,?)',(cle,derniere,apres,echecs));db.commit()
        def priorite(statut,cle):
            return (0 if statut in ('a_lire','a_reprendre') else 1,reprise(cle)[0])
        # Les statuts v1 ne prouvaient pas READ_MESSAGE_HISTORY : relecture bornée,
        # sans supprimer les messages déjà nettoyés (INSERT OR IGNORE).
        if not db.execute("SELECT 1 FROM meta WHERE cle='permissions_v2'").fetchone():
            db.execute("UPDATE salons SET statut='a_reprendre',curseur=?",(avant,))
            db.execute("INSERT INTO meta VALUES ('permissions_v2','1')")
        def borne():
            return (time.monotonic() >= fin or
                    db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0] >= volume_max)
        async def attendre(coro,deadline=None):
            return await asyncio.wait_for(coro,timeout=max(.001,min(10,(deadline or fin)-time.monotonic())))
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
        if not borne() and time.monotonic()<fin_decouverte and reprise('d:fils_actifs')[1]<=time.time() and (not actif or actif[0]!='complet'):
            debut_tentative('d:fils_actifs')
            try:
                for c in await attendre(guild.active_threads(),fin_decouverte):
                    inscrire(c.id)
                actifs='complet'
            except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                actifs=type(exc).__name__
            fin_tentative('d:fils_actifs',actifs!='complet')
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
        sources.sort(key=lambda item: priorite(db.execute('SELECT statut FROM decouverte_v2 WHERE id=?',(item[0],)).fetchone()[0],'d:'+item[0]))
        for key,c,mode in sources:
            statut,cursor=db.execute('SELECT statut,curseur FROM decouverte_v2 WHERE id=?',(key,)).fetchone()
            if statut=='complet' or reprise('d:'+key)[1]>time.time():continue
            if not permission(c):
                db.execute("UPDATE decouverte_v2 SET statut='permissions_absentes' WHERE id=?",(key,));db.commit();continue
            while pages_decouverte<decouverte_max and not borne() and time.monotonic()<fin_decouverte:
                debut_tentative('d:'+key)
                pages_decouverte+=1
                before=None if not cursor else (discord.Object(id=int(cursor)) if mode.get('joined') else datetime.fromisoformat(cursor))
                try:
                    batch=await attendre(page(c.archived_threads(limit=50,before=before,**mode)),fin_decouverte)
                    nouveau=(str(batch[-1].id) if mode.get('joined') else batch[-1].archive_timestamp.isoformat()) if batch else cursor
                    statut='complet' if len(batch)<50 else ('a_reprendre' if nouveau!=cursor else 'curseur_bloque')
                except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                    fin_tentative('d:'+key,True)
                    db.execute('UPDATE decouverte_v2 SET statut=? WHERE id=?',(type(exc).__name__,key));db.commit();break
                fin_tentative('d:'+key)
                with db:
                    for thread in batch:inscrire(thread.id)
                    db.execute('UPDATE decouverte_v2 SET statut=?,curseur=? WHERE id=?',(statut,nouveau,key))
                cursor=nouveau
                if statut!='a_reprendre':break
        pages=0
        # Les fils archivés sont résolus un par un : pas d'accumulation de leur
        # historique ni de tous leurs objets Discord en RAM.
        a_lire=db.execute('SELECT id,curseur,statut FROM salons').fetchall()
        a_lire.sort(key=lambda row: priorite(row[2],'s:'+row[0]))
        for cid,cursor,status in a_lire:
            # Complet = historique déjà lu avec droits vérifiés pour la borne figée.
            # Ne pas consommer le budget réseau sur ce préfixe à chaque reprise.
            if status=='complet' or reprise('s:'+cid)[1]>time.time():continue
            if pages>=pages_max or borne():break
            debut_tentative('s:'+cid)
            channel=channels.get(cid) or guild.get_channel_or_thread(int(cid))
            try:
                if channel is None:channel=await attendre(guild.fetch_channel(int(cid)))
            except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                fin_tentative('s:'+cid,True)
                db.execute("UPDATE salons SET statut='illisible',erreur=? WHERE id=?",(type(exc).__name__,cid));db.commit();continue
            if not permission(channel):
                db.execute("UPDATE salons SET statut='permissions_absentes',erreur='VIEW_CHANNEL/READ_MESSAGE_HISTORY' WHERE id=?",(cid,));db.commit();continue
            while pages<pages_max and not borne():
                try:
                    batch=await attendre(page(channel.history(limit=100,before=discord.Object(id=int(cursor)),oldest_first=False,
                        **({"after":discord.Object(id=apres)} if apres else {}))))
                except (discord.Forbidden,discord.HTTPException,TimeoutError) as exc:
                    fin_tentative('s:'+cid,True)
                    db.execute('UPDATE salons SET statut=?,erreur=? WHERE id=?',('illisible',type(exc).__name__,cid));db.commit();break
                fin_tentative('s:'+cid)
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
        reprises=[dict(source=c,apres=t) for c,t in db.execute('SELECT cle,apres FROM reprises WHERE apres>0')]
        borne_atteinte = borne()
        avancement = progression(salons, discovery, pages, pages_max, pages_decouverte, decouverte_max, borne_atteinte)
        return dict(**avancement, reprises=reprises,avant=avant,apres=str(apres),salons=salons,decouverte=discovery,pages=pages,pages_decouverte=pages_decouverte,borne_atteinte=borne_atteinte,
                    complet=not borne_atteinte and all(s['statut']=='complet' for s in salons) and all(x['statut']=='complet' for x in discovery),
                    limites=['MP non inclus','Salons invisibles au bot non énumérables','Embeds, composants et pièces jointes omis','Masquage prudent : texte perdu possible ; pas de garantie sur un secret sans contexte'])
    except sqlite3.OperationalError as exc:
        if getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_FULL:
            raise VolumeAtteint('volume_atteint') from exc
        raise
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
    reste = rapport['travail_restant']
    resume = (f"Couverture uniquement : {reste['salons']} salon(s) et {reste['operations_decouverte']} opération(s) de découverte restent. "
              + ("Relance `!audit-discussions complet` pour continuer, même si borne_atteinte vaut false. " if not rapport['complet'] else
                 "Cette photographie est terminée pour sa borne avant. ")
              + "Le contenu nettoyé reste sur le volume privé du bot.")
    await message.author.send(resume,
                              file=discord.File(io.BytesIO(json.dumps(rapport,ensure_ascii=False,indent=2).encode()),filename='couverture-audit.json'))
