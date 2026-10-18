"""Réparation propriétaire par UID : rôles, catégorie et TL existants uniquement.

Aucun import du parcours ou de l'allocation, aucune écriture des affectations.
Diagnostic sans écriture ; application journalisée avant chaque effet Discord.
"""
from contextlib import contextmanager
from copy import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unicodedata

import discord
import choix_creatrice
from onboarding_discord import role_clippeur, surcharge_acces_tl
from onboarding_preuves import salon_vide_verifie, tl_pour


class Retenue(RuntimeError):
    pass


def mots(texte):
    texte = unicodedata.normalize('NFKD', str(texte or '').casefold())
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    return re.findall(r'[a-z0-9]+', texte)


def sources(root, uid, mapping):
    """Ne projeter que le choix déjà enregistré ; jamais un handle ou un secret."""
    donnees = {}
    for nom in ('equipes', 'pipeline', 'parcours', 'onboarding', 'sortis'):
        fichier = Path(root) / (nom + '.json')
        if fichier.is_symlink() or not fichier.is_file() or fichier.stat().st_size > 32 * 1024 * 1024:
            raise Retenue('Sources d’affectation absentes ou illisibles.')
        try:
            valeur = json.loads(fichier.read_text())
        except (OSError, ValueError):
            raise Retenue('Sources d’affectation absentes ou illisibles.') from None
        if not isinstance(valeur, list if nom == 'sortis' else dict):
            raise Retenue('Structure des sources invalide.')
        donnees[nom] = valeur
    registre = donnees['equipes']
    fiche = registre.get(uid) or {}
    pipeline = (donnees['pipeline'].get('etats') or {}).get(uid) or {}
    parcours = donnees['parcours'].get(uid) or {}
    onboarding = (donnees['onboarding'].get('clippers') or {}).get(uid) or {}
    if not all(isinstance(x, dict) for x in (fiche, pipeline, parcours, onboarding)):
        raise Retenue('Dossier invalide.')
    creatrice = fiche.get('creatrice')
    if not isinstance(creatrice, str) or not mots(creatrice):
        raise Retenue('Aucune créatrice déjà affectée au registre.')
    if pipeline.get('etat') not in ('quiz_ok', 'valide', 'attente_attribution') or not pipeline.get('score_quiz'):
        raise Retenue('Validation du quiz non confirmée.')
    choix = [pipeline.get('creatrice_attendue'), (pipeline.get('decision_creatrice') or {}).get('creatrice'),
             parcours.get('creatrice'), onboarding.get('creatrice')]
    if any(c and mots(c) != mots(creatrice) for c in choix):
        raise Retenue('Affectations de créatrice contradictoires.')
    if any(not isinstance(s, dict) or str(s.get('uid')) == uid for s in donnees['sortis']):
        raise Retenue('Historique de sortie présent ou illisible : revue nécessaire.')
    sids = {str(f.get('salon_id')) for f in (fiche, parcours, onboarding) if f.get('salon_id')}
    if len(sids) > 1 or any(not s.isdigit() for s in sids):
        raise Retenue('Références de salon contradictoires.')
    correspondances = mapping()
    if not isinstance(correspondances, dict):
        raise Retenue('Affectation TL illisible.')
    tl = tl_pour(uid, creatrice, correspondances, registre)
    if not tl or not tl.isdigit() or tl == uid:
        raise Retenue('Team leader existant absent ou ambigu.')
    return {'uid': uid, 'creatrice': creatrice, 'tl': tl, 'salon': next(iter(sids), None),
            'source_tl': 'affectation_individuelle' if correspondances.get(uid) else 'mandat_creatrice'}


def empreinte_permissions(salon):
    return {str(cible.id): list(p.value for p in overwrite.pair())
            for cible, overwrite in salon.overwrites.items()}


def canal_avec_roles_frais(canal, roles):
    """permissions_for utilise le cache du serveur : isoler une vue relue, sans le modifier."""
    vue = copy(canal)
    vue.guild = copy(canal.guild)
    vue.guild._roles = {r.id: r for r in roles}
    return vue


async def examiner(guild, root, uid, mapping):
    affectation = sources(root, uid, mapping)
    canaux = await guild.fetch_channels()
    roles = await guild.fetch_roles()
    membre = await guild.fetch_member(int(uid))
    tl = await guild.fetch_member(int(affectation['tl']))
    possedes = {r.id for r in membre.roles}
    if (membre.bot or tl.bot or membre.id in (guild.owner_id, guild.me.id)
            or any(r.id in possedes and r.permissions.administrator for r in roles)):
        raise Retenue('Le dossier doit désigner un clippeur humain et son TL humain.')
    categories = [c for c in canaux if c.type == discord.ChannelType.category]
    cible = mots(affectation['creatrice'])
    cats = [c for c in categories if mots(c.name) == cible]
    roles_c = [r for r in roles if not r.managed and mots(r.name) == cible]
    clippeur = role_clippeur(SimpleNamespace(roles=roles))
    if len(cats) != 1 or len(roles_c) != 1 or clippeur is None:
        raise Retenue('Catégorie ou rôles attendus absents ou ambigus ; aucune supposition.')
    categorie, role_c = canal_avec_roles_frais(cats[0], roles), roles_c[0]
    noms_categories = {tuple(mots(c.name)) for c in categories}
    if any(r.id in possedes and r.id not in (role_c.id, clippeur.id) and tuple(mots(r.name)) in noms_categories
           for r in roles if r.id != guild.default_role.id):
        raise Retenue('Un autre rôle de créatrice est présent : revue nécessaire.')
    proprietaires = lambda c: re.findall(r'(?<![\w-])clipper-uid:(\d+)(?!\d)', str(getattr(c, 'topic', '') or ''))
    salons = [c for c in canaux if c.type == discord.ChannelType.text and uid in proprietaires(c)]
    if (len(salons) != 1 or set(proprietaires(salons[0])) != {uid}
            or affectation['salon'] not in (None, str(salons[0].id))):
        raise Retenue('Salon personnel unique non confirmé par UID ; aucune création.')
    salon = canal_avec_roles_frais(salons[0], roles)
    if salon.permissions_for(salon.guild.default_role).view_channel:
        raise Retenue('Salon public : aucune réparation automatique des accès.')
    droits_tl = salon.permissions_for(tl)
    acces_tl = droits_tl.view_channel and droits_tl.read_message_history
    if not acces_tl and not await salon_vide_verifie(salon):
        raise Retenue('Historique privé présent ou illisible : accès TL retenu.')
    manquants = [r for r in (clippeur, role_c) if r.id not in possedes]
    dangereux = ('administrator', 'manage_roles', 'manage_guild', 'manage_channels',
                 'manage_webhooks', 'ban_members', 'kick_members')
    if any(any(getattr(r.permissions, p) for p in dangereux) for r in manquants):
        raise Retenue('Un rôle attendu contient des permissions administratives : ajout retenu.')
    roles_bot = [r for r in roles if r.id in {r.id for r in guild.me.roles}]
    if manquants and (not guild.me.guild_permissions.manage_roles or not roles_bot
                      or max(r.position for r in roles_bot) <= max(r.position for r in manquants)):
        raise Retenue('Hiérarchie ou permission du bot insuffisante pour les rôles.')
    actions = [('role', r.id) for r in manquants]
    if salon.category_id != categorie.id:
        if not salon.permissions_for(guild.me).manage_channels or not categorie.permissions_for(guild.me).manage_channels:
            raise Retenue('Permission du bot insuffisante pour déplacer le salon.')
        actions.append(('categorie', categorie.id))
    if not (acces_tl and droits_tl.send_messages):
        if not salon.permissions_for(guild.me).manage_roles:
            raise Retenue('Permission du bot insuffisante pour l’accès TL.')
        actions.append(('tl', tl.id))
    droits_membre = salon.permissions_for(membre)
    if not actions and not (droits_membre.view_channel and droits_membre.send_messages
                            and droits_membre.read_message_history):
        raise Retenue('Lecture, écriture ou historique refusé au clippeur : restriction hors périmètre.')
    if sources(root, uid, mapping) != affectation:
        raise Retenue('Affectation modifiée pendant la lecture : relancer le diagnostic.')
    reference = {**affectation, 'salon': str(salon.id), 'categorie': str(categorie.id),
                 'roles': [str(clippeur.id), str(role_c.id)]}
    return {'reference': reference, 'actions': actions, 'permissions': empreinte_permissions(salon),
            'membre': membre, 'tl': tl, 'salon': salon, 'categorie': categorie, 'roles': roles}


@contextmanager
def verrou_fichier(root, uid):
    fd = os.open(Path(root) / f'organisation-{uid}.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Retenue('Réparation déjà en cours pour cet UID.') from None
        yield
    finally:
        os.close(fd)


def journaliser(root, uid, source, etat, **details):
    entree = {'date': datetime.now(timezone.utc).isoformat(), 'uid': uid, 'source': source,
              'etat': etat, **details}
    ligne = (json.dumps(entree, ensure_ascii=False, sort_keys=True) + '\n').encode()
    fd = os.open(Path(root) / f'organisation-{uid}.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'ab') as fichier:
        fichier.write(ligne)
        fichier.flush()
        os.fsync(fichier.fileno())


async def appliquer(guild, root, uid, mapping, source, diagnostic):
    reference = diagnostic['reference']
    journaliser(root, uid, source, 'debut', reference=reference, actions=diagnostic['actions'])
    for action in diagnostic['actions']:
        courant = await examiner(guild, root, uid, mapping)
        if courant['reference'] != reference:
            raise Retenue('Cible modifiée depuis le diagnostic : réparation interrompue.')
        if action not in courant['actions']:
            continue  # Une réponse perdue ne doit pas répéter une mutation déjà visible.
        genre, identifiant = action
        salon = courant['salon']
        attendues = dict(courant['permissions'])
        if genre == 'tl':
            overwrite = surcharge_acces_tl(salon, courant['tl'])
            attendues[str(identifiant)] = [p.value for p in overwrite.pair()]
        journaliser(root, uid, source, 'intention', action=action, permissions_avant=courant['permissions'])
        try:
            raison = 'Réparation organisation par le propriétaire, discord-message:' + source['message']
            if genre == 'role':
                role = next(r for r in courant['roles'] if r.id == identifiant)
                await courant['membre'].add_roles(role, reason=raison)
            elif genre == 'categorie':
                await salon.edit(category=courant['categorie'], sync_permissions=False, reason=raison)
            else:
                await salon.set_permissions(courant['tl'], overwrite=overwrite, reason=raison)
            apres = await examiner(guild, root, uid, mapping)
            if apres['reference'] != reference or action in apres['actions'] or apres['permissions'] != attendues:
                raise Retenue('État Discord ou permissions non confirmés après la mutation.')
        except Exception as erreur:
            journaliser(root, uid, source, 'non_confirme', action=action, erreur_type=type(erreur).__name__)
            raise
        journaliser(root, uid, source, 'confirme', action=action)
    final = await examiner(guild, root, uid, mapping)
    if final['reference'] != reference or final['actions']:
        raise Retenue('Organisation encore incomplète : reprise nécessaire.')
    journaliser(root, uid, source, 'termine', reference=reference)
    return final


async def commande(message, texte, root, admin_ids, mapping):
    if texte.split()[:1] != ['!organisation']:
        return False
    if (message.guild is None or message.author.id != message.guild.owner_id
            or str(message.author.id) not in admin_ids):
        return True
    args = texte.split()[1:]
    if not args or not re.fullmatch(r'[0-9]{1,22}', args[0]) or len(args) > 2 or (len(args) == 2 and args[1] not in ('diagnostic', 'appliquer')):
        await message.author.send('Usage : `!organisation UID` (diagnostic) ou `!organisation UID appliquer`.')
        return True
    uid = args[0]
    try:
        async with choix_creatrice.verrou(uid):
            diagnostic = await examiner(message.guild, root, uid, mapping)
            if len(args) == 2 and args[1] == 'appliquer':
                with verrou_fichier(root, uid):
                    source = {'message': str(message.id), 'par': str(message.author.id), 'serveur': str(message.guild.id)}
                    await appliquer(message.guild, root, uid, mapping, source, diagnostic)
                texte = '✅ Organisation vérifiée. Aucun compte réservé, aucun message de compte envoyé.'
            else:
                modeles = {'role': 'Ajouter le rôle <@&{}>', 'categorie': 'Déplacer dans <#{}>',
                           'tl': 'Rétablir l’accès du TL <@{}>'}
                actions = '\n'.join('• ' + modeles[genre].format(identifiant)
                                    for genre, identifiant in diagnostic['actions']) or 'Aucune.'
                reference = diagnostic['reference']
                texte = (f"**Diagnostic organisation · UID {uid}**\n\nCréatrice affectée : {reference['creatrice']}.\n\n"
                         f"Salon : <#{reference['salon']}>.\n\nTL affecté : <@{reference['tl']}>.\n\nActions prévues :\n\n{actions}\n\n"
                         f"Pour appliquer à cet UID uniquement : `!organisation {uid} appliquer`.")
    except Retenue as erreur:
        texte = '⚠️ Organisation retenue : ' + str(erreur)
    except Exception:
        texte = '⚠️ Résultat non confirmé. Relance le diagnostic ; aucune reprise du parcours de comptes.'
    await message.author.send(texte, allowed_mentions=discord.AllowedMentions.none())
    return True
