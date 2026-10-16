"""Rapport exploitable en MP : catégories fermées et références, jamais de texte libre."""
import io
import json
from pathlib import Path
import re
import sqlite3
from datetime import datetime
import discord

CATEGORIES = (
    ('acces_masque',r'masqu[eé]|accès'),
    ('signalement_suspension',r'ban|suspend|désactiv|desactiv|appel'),
    ('drive',r'drive|dossier|autorisation'),
    ('publication',r'reels?|publi|vidéo|video'),
    ('remuneration',r'paie|paiement|visite|clic|forfait'),
    ('demande_humaine',r'manager|ga[eëé]tan|aide|bloqu'),
)

def diagnostic(chemin,apres=0,limite=1000):
    """Lecture locale bornée ; aucun champ textuel fourni par un message n'est exporté."""
    path=Path(chemin)
    if not path.is_file():raise ValueError('Aucune collecte locale disponible.')
    if not isinstance(apres,int) or apres<0:raise ValueError('Curseur numérique attendu.')
    limite=min(1000,max(1,int(limite)))
    db=sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)
    try:
        guild=db.execute("SELECT valeur FROM meta WHERE cle='guild'").fetchone()[0]
        if not str(guild).isdigit():raise ValueError('Identité de serveur invalide.')
        rows=db.execute('SELECT id,salon,contenu FROM messages WHERE CAST(id AS INTEGER)>? ORDER BY CAST(id AS INTEGER) LIMIT ?',
                        (apres,limite+1)).fetchall()
        cas=[];comptes={};suivant=apres
        for ident,salon,contenu in rows[:limite]:
            if not str(ident).isdigit() or not str(salon).isdigit():continue
            suivant=int(ident)
            try:r=json.loads(contenu);jour=datetime.fromisoformat(r['date']).date().isoformat()
            except (ValueError,TypeError,KeyError):continue
            uid=str(r.get('uid') or '')
            if not uid.isdigit():uid='inconnu'
            texte=str(r.get('texte') or '').casefold()
            categories=[c for c,motif in CATEGORIES if re.search(motif,texte)] or ['autre']
            for c in categories:comptes[c]=comptes.get(c,0)+1
            cas.append(dict(uid=uid,jour=jour,bot=r.get('bot') is True,categories=categories,
                            source=f'https://discord.com/channels/{guild}/{salon}/{ident}'))
        return dict(version=1,compteurs=comptes,cas=cas,apres=apres,curseur_suivant=suivant,reste=len(rows)>limite,
                    limites=['Catégories automatiques, pas des diagnostics confirmés','Aucun contenu de message, nom, embed, pièce jointe ou secret exporté','Consulter les références Discord avec ses droits existants pour vérifier le contexte'])
    except sqlite3.Error:
        raise ValueError('Collecte locale indisponible ou incomplète.') from None
    finally:db.close()

async def envoyer(message,chemin,apres=0):
    rapport=diagnostic(chemin,apres)
    data=json.dumps(rapport,ensure_ascii=False,indent=2).encode()
    suite=f" Suite : `!audit-discussions diagnostic {rapport['curseur_suivant']}`." if rapport['reste'] else ''
    await message.author.send('Diagnostic privé : catégories et références des messages, sans contenu libre. Tu peux joindre ce JSON à la conversation d’analyse.'+suite,
        file=discord.File(io.BytesIO(data),filename=f'audit-diagnostic-{apres}.json'))
