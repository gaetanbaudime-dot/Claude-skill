"""Tickets par UID/sujet, preuves référencées sans recopier de conversations."""
import asyncio
import json
import os
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

_LOCKS={}

def ouvrir(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY, uid TEXT, sujet TEXT, statut TEXT,
        preuves TEXT, notification TEXT, cree TEXT, clos TEXT)''')
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ticket_ouvert ON tickets(uid,sujet) WHERE clos IS NULL")
    db.commit();return db

def lister(path,uid):
    with ouvrir(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM tickets WHERE uid=? AND clos IS NULL ORDER BY id',(str(uid),))]

def clore(path,uid,ticket):
    with ouvrir(path) as db:
        return db.execute('UPDATE tickets SET clos=? WHERE id=? AND uid=? AND clos IS NULL',
                          (datetime.now(timezone.utc).isoformat(),ticket,str(uid))).rowcount==1

async def signaler(path,uid,sujet,guild,channel,message,pieces,notifier):
    """Une notification par problème ouvert ; résultat incertain jamais renvoyé seul."""
    async with _LOCKS.setdefault(str(path),asyncio.Lock()):
        with ouvrir(path) as db:
            row=db.execute('SELECT * FROM tickets WHERE uid=? AND sujet=? AND clos IS NULL',(str(uid),sujet)).fetchone()
            preuve=dict(guild=str(guild),canal=str(channel),message=str(message),pieces=int(pieces))
            if row is None:
                cur=db.execute('INSERT INTO tickets(uid,sujet,statut,preuves,cree) VALUES (?,?,?,?,?)',
                               (str(uid),sujet,'a_envoyer',json.dumps([preuve]),datetime.now(timezone.utc).isoformat()))
                ident=cur.lastrowid;statut='a_envoyer'
            else:
                ident=row['id'];statut=row['statut'];preuves=json.loads(row['preuves'])
                if not any(p['message']==preuve['message'] and p['canal']==preuve['canal'] for p in preuves):
                    preuves.append(preuve)
                    db.execute('UPDATE tickets SET preuves=? WHERE id=?',(json.dumps(preuves),ident))
            db.commit()
            if statut != 'a_envoyer':
                return dict(id=ident,statut=statut,nouveau=False)
            db.execute("UPDATE tickets SET statut='envoi_incertain' WHERE id=?",(ident,));db.commit()
            try:
                notification=await notifier(ident)
            except Exception:
                # Un timeout peut suivre une livraison effective : pas de renvoi automatique.
                return dict(id=ident,statut='envoi_incertain',nouveau=False)
            if notification is None:
                db.execute("UPDATE tickets SET statut='a_envoyer' WHERE id=?",(ident,));db.commit()
                return dict(id=ident,statut='a_envoyer',nouveau=False)
            db.execute("UPDATE tickets SET statut='transmis',notification=? WHERE id=?",(str(notification),ident));db.commit()
            return dict(id=ident,statut='transmis',nouveau=True)

def contexte(path,uid):
    rows=lister(path,uid)
    if not rows:return ''
    lignes=['[Support existant : ne redemande pas les preuves déjà référencées. Ne prétends pas que le problème est résolu.]']
    for r in rows:
        lignes.append(f"Ticket {r['id']} : {r['sujet']} ; {r['statut']} ; {len(json.loads(r['preuves']))} message(s) source. Responsable : équipe. Aucun délai promis.")
    return '\n'.join(lignes)

def rapport(path,uid):
    rows=lister(path,uid)
    if not rows:return 'Aucun ticket ouvert pour cet UID.'
    lignes=[]
    for r in rows:
        lignes.append(f"Ticket {r['id']} — {r['sujet']} — {r['statut']}")
        for p in json.loads(r['preuves'])[-8:]:
            lignes.append(f"https://discord.com/channels/{p['guild']}/{p['canal']}/{p['message']} · {p['pieces']} pièce(s) jointe(s)")
        lignes.append(f"Résolu après vérification : `!support-resolu {uid} {r['id']}`")
    return '\n'.join(lignes)
