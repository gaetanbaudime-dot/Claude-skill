"""Tickets par UID/sujet, preuves référencées sans recopier de conversations."""
import asyncio
import json
import os
import sqlite3
import discord
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager

_LOCKS={}

@contextmanager
def ouvrir(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY, uid TEXT, sujet TEXT, statut TEXT,
        preuves TEXT, notification TEXT, cree TEXT, clos TEXT)''')
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ticket_ouvert ON tickets(uid,sujet) WHERE clos IS NULL")
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()

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
            except Exception as exc:
                # Un refus HTTP 4xx explicite ne livre pas le message. Un timeout,
                # 408 ou 5xx reste ambigu et exige un rapprochement humain.
                certain = isinstance(exc, discord.HTTPException) and 400 <= exc.status < 500 and exc.status != 408
                statut = 'a_envoyer' if certain else 'envoi_incertain'
                db.execute('UPDATE tickets SET statut=? WHERE id=?',(statut,ident));db.commit()
                return dict(id=ident,statut=statut,nouveau=False)
            if notification is None:
                db.execute("UPDATE tickets SET statut='a_envoyer' WHERE id=?",(ident,));db.commit()
                return dict(id=ident,statut='a_envoyer',nouveau=False)
            db.execute("UPDATE tickets SET statut='transmis',notification=? WHERE id=?",(str(notification),ident));db.commit()
            return dict(id=ident,statut='transmis',nouveau=True)

def ticket_recent(path,uid,prefixe,heures):
    """23/10 (Yves, 22/10 : quatre tickets « assistance IA » en douze heures pour le même compte 2 verrouillé, dont un vide pour
    une capture) : le sujet du ticket OUVERT de cet UID qui commence par `prefixe`, créé il y a moins de `heures`, sinon None.
    La demande suivante s'y ajoute comme preuve, sans nouvelle notification."""
    limite=datetime.now(timezone.utc).timestamp()-float(heures)*3600
    with ouvrir(path) as db:
        rows=db.execute('SELECT sujet,cree FROM tickets WHERE uid=? AND clos IS NULL ORDER BY id DESC',(str(uid),)).fetchall()
    for r in rows:
        try:
            cree=datetime.fromisoformat(str(r['cree'])).timestamp()
        except ValueError:
            continue
        if str(r['sujet']).startswith(prefixe) and cree>=limite:
            return r['sujet']
    return None

def ajouter_suivi(path,uid,guild,channel,message,pieces):
    """Rattachement contextuel aux tickets ouverts du même auteur et salon.

    Plusieurs tickets possibles : ce contexte n'affirme pas qu'une PJ prouve
    chacun des problèmes. Le manager vérifie les références, sans nouvelle copie.
    """
    preuve=dict(guild=str(guild),canal=str(channel),message=str(message),pieces=int(pieces),suivi_contextuel=True)
    attaches=[]
    with ouvrir(path) as db:
        for row in db.execute('SELECT id,preuves FROM tickets WHERE uid=? AND clos IS NULL',(str(uid),)).fetchall():
            preuves=json.loads(row['preuves'])
            if not any(p['guild']==str(guild) and p['canal']==str(channel) for p in preuves):continue
            existante=next((p for p in preuves if p['canal']==str(channel) and p['message']==str(message)),None)
            if existante is None:preuves.append(preuve)
            else:existante['pieces']=max(existante['pieces'],int(pieces))
            db.execute('UPDATE tickets SET preuves=? WHERE id=?',(json.dumps(preuves),row['id']))
            attaches.append(row['id'])
    return attaches


async def reprendre(path,uid,ticket,notifier,non_livre=False):
    if not non_livre:return None
    with ouvrir(path) as db:
        row=db.execute('SELECT * FROM tickets WHERE id=? AND uid=? AND clos IS NULL',(ticket,str(uid))).fetchone()
        if not row or row['statut'] not in ('envoi_incertain','a_envoyer'):return None
        db.execute("UPDATE tickets SET statut='a_envoyer' WHERE id=?",(ticket,))
        sujet=row['sujet'];p=json.loads(row['preuves'])[-1]
    return await signaler(path,uid,sujet,p['guild'],p['canal'],p['message'],p['pieces'],notifier)


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
            lignes.append(f"https://discord.com/channels/{p['guild']}/{p['canal']}/{p['message']} · {p['pieces']} pièce(s) jointe(s){'; suivi contextuel à vérifier' if p.get('suivi_contextuel') else ''}")
        if r['statut'] in ('envoi_incertain','a_envoyer'):
            lignes.append(f"Après vérification de la non-livraison : `!support-reprendre {uid} {r['id']} confirme-non-livre`")
        lignes.append(f"Résolu après vérification : `!support-resolu {uid} {r['id']}`")
    return '\n'.join(lignes)
