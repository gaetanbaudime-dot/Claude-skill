"""Organisation et preuves Discord de l'accueil, sans remise d'identifiants."""
import re
import unicodedata

import discord


def surcharge_acces_tl(salon, tl):
    """Ouvrir les trois accès attendus sans effacer les autres permissions du TL."""
    overwrite = discord.PermissionOverwrite.from_pair(*salon.overwrites_for(tl).pair())
    overwrite.update(view_channel=True, send_messages=True, read_message_history=True)
    return overwrite


def role_clippeur(guild):
    """Le rôle Clippeur doit être unique ; un rang ou une équipe ne le remplace pas."""
    def nom_exact(role):
        nom = unicodedata.normalize('NFKD', role.name.casefold())
        nom = ''.join(c for c in nom if not unicodedata.combining(c))
        return re.findall(r'[^\W_]+', nom) == ['clippeur']
    candidats = [r for r in guild.roles if not getattr(r, 'managed', False)
                 and nom_exact(r)]
    return candidats[0] if len(candidats) == 1 else None


def salon_information(categorie):
    """Un seul salon d'information dans la catégorie ; aucun repli arbitraire."""
    candidats = []
    for salon in getattr(categorie, 'text_channels', ()):
        nom = unicodedata.normalize('NFKD', salon.name.casefold())
        nom = ''.join(c for c in nom if not unicodedata.combining(c))
        if 'ℹ' in salon.name or re.search(r'(?<!\w)(?:i|infos?|informations?)(?!\w)', nom):
            candidats.append(salon)
    return candidats[0] if len(candidats) == 1 else None


async def ranger_categorie(salon, categorie, raison):
    """Reprise par UID : déplacer le salon existant sans synchroniser ses accès."""
    if categorie is None or salon.category_id == categorie.id:
        return salon, ''
    try:
        salon = await salon.edit(category=categorie, sync_permissions=False, reason=raison)
        if salon is None or salon.category_id != categorie.id:
            return salon, 'catégorie non confirmée : reprise nécessaire'
        return salon, ''
    except (discord.HTTPException, TimeoutError, OSError):
        return salon, 'déplacement non confirmé : reprise nécessaire, aucun nouveau salon'


async def verifier_organisation(guild, membre, salon, categorie, tl, roles, info):
    """Relire rôles et accès après les écritures, avant toute réservation de compte."""
    membre = await guild.fetch_member(membre.id)
    tl = await guild.fetch_member(tl.id)
    salon = await guild.fetch_channel(salon.id)
    info = await guild.fetch_channel(info.id)
    if salon.category_id != categorie.id or info.category_id != categorie.id:
        raise RuntimeError('Catégorie de la créatrice non confirmée')
    if not {r.id for r in roles}.issubset({r.id for r in membre.roles}):
        raise RuntimeError('Rôles Clippeur et créatrice non confirmés')
    for personne in (membre, tl, guild.me):
        permissions = salon.permissions_for(personne)
        if not (permissions.view_channel and permissions.send_messages and permissions.read_message_history):
            raise RuntimeError('Accès au salon personnel non confirmés')
    droits_info = info.permissions_for(membre)
    if not (droits_info.view_channel and droits_info.read_message_history):
        raise RuntimeError('Salon informations illisible pour le clippeur')
    return membre, salon, info


async def confirmer_accueil(store, salon, uid, message_id, creatrice, info):
    """Vérifier le message réel ; compléter les informations à part, sans modifier la remise du compte."""
    import process_livraison

    async def lire(mid):
        if not str(mid).isdigit():
            raise RuntimeError('Identité du message du compte 1 non vérifiable')
        message = await salon.fetch_message(int(mid))
        if message.author.id != salon.guild.me.id:
            raise RuntimeError('Auteur du message du compte 1 non confirmé')
        return message

    message = await lire(message_id)
    mention = f'<#{info.id}>'
    if mention in message.content:
        return
    # Un complément séparé évite toute réécriture d'un message contenant des accès.
    # Le journal conserve aussi les envois incertains : aucun second POST à l'aveugle.
    texte = (f'Ta créatrice : **{creatrice}**.\n\n'
             f'Vidéos et Drive de ta créatrice : {mention}.')
    complement = await process_livraison.envoyer_compte_1(
        store, salon, uid, texte, None, cle='message-infos:' + str(uid),
        operation={'compte1': str(message_id), 'info': str(info.id)})
    confirme = await lire(complement.id)
    if mention not in confirme.content:
        raise RuntimeError('Complément informations non confirmé')
