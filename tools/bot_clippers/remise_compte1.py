"""Remise explicite par le propriétaire : édition du compte 1 existant uniquement.

Aucun appel depuis les reprises automatiques. Aucun secret dans les retours ou logs.
"""
import re

import discord
import choix_creatrice
import onboarding
import parcours
import process_adapters


class Retenue(Exception):
    pass


def modele(mention, handle, mail, mdp):
    """Valeurs existantes uniquement ; rendu destiné au seul salon du titulaire."""
    return (f"{mention}\n\n**Étape 1 · Crée ton compte 1**\n\n"
            f"Identifiant : `{handle}`\n\nE-mail : `{mail}`\n\nMot de passe : `{mdp}`\n\n"
            "1. Instagram → Créer un compte → utilise cet e-mail.\n\n"
            "2. Pour le code reçu par e-mail, utilise `!code` dans le salon 🔐-code-instagram.\n\n"
            "3. Si Instagram demande ton numéro ou ta date de naissance, utilise les vrais.\n\n"
            "Créé ? Appuie sur le bouton.")


async def commande(message, texte, admin_ids):
    if texte.split()[:1] != ['!remettre-compte1']:
        return False
    if (message.guild is None or message.author.id != message.guild.owner_id
            or str(message.author.id) not in admin_ids):
        return True
    args = texte.split()[1:]
    if len(args) != 1 or not re.fullmatch(r'[0-9]{1,22}', args[0]):
        await message.reply('Usage propriétaire : !remettre-compte1 UID')
        return True
    uid = args[0]
    try:
        async with choix_creatrice.verrou(uid):
            fiche = parcours._lire().get(uid) or {}
            onb = parcours._onb(uid)
            handles = parcours._comptes_ordonnes(uid, onb, fiche)
            mid = (fiche.get('messages') or {}).get('1')
            sid = fiche.get('salon_id')
            if not handles or not str(mid or '').isdigit() or not str(sid or '').isdigit() or parcours._cree(fiche, 1):
                raise Retenue('Compte 1 déjà créé ou message initial non identifié.')
            handle = handles[0]
            store = process_adapters.store()
            with store.transaction() as db:
                row = db.execute('SELECT a.uid,a.status FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?',
                                 (handle.lower().lstrip('@'),)).fetchone()
                sortie = db.execute('SELECT 1 FROM jobs WHERE key=?', ('sortie:' + uid,)).fetchone()
            if row != (uid, 'reserved') or sortie:
                raise Retenue('Réservation nominative non confirmée.')
            salon = message.guild.get_channel(int(sid))
            membre = message.guild.get_member(int(uid))
            if salon is None or membre is None or f'clipper-uid:{uid}' not in str(getattr(salon, 'topic', '')).split(' · '):
                raise Retenue('Salon personnel non confirmé.')
            if not salon.permissions_for(membre).view_channel or salon.permissions_for(message.guild.default_role).view_channel:
                raise Retenue('Confidentialité du salon non confirmée.')
            original = await salon.fetch_message(int(mid))
            if original.author.id != message.guild.me.id:
                raise Retenue('Message initial du bot non confirmé.')
            # Lecture serveur uniquement après commande du propriétaire ; pas de repli ni allocation.
            lignes = [c for c in await onboarding.lire_comptes() if c.get('handle', '').lower() == handle.lower()]
            if len(lignes) != 1:
                raise Retenue('Ligne unique du classeur non confirmée.')
            ligne = lignes[0]
            if (not onb.get('gerant') or onboarding._norm(ligne.get('gerant', '')) != onboarding._norm(onb['gerant'])
                    or onboarding._norm(ligne.get('creatrice', '')) != onboarding._norm(fiche.get('creatrice', ''))
                    or onboarding._norm(ligne.get('etat', '')) not in onboarding.A_CREER):
                raise Retenue('Affectation ou état à créer du classeur non confirmé.')
            valeurs = [ligne.get('mail'), ligne.get('mdp')]
            if any(not isinstance(v, str) or not v.strip() or any(c in v for c in ('`', '\n', '\r')) for v in valeurs):
                raise Retenue('Champs existants incomplets ou format incompatible.')
            contenu = modele(membre.mention, handle, *valeurs)
            if len(contenu) > 1990:
                raise Retenue('Message trop long : aucune modification.')
            # Ne pas utiliser _retirer_pret sur un accueil fusionné : il retirerait la confirmation.
            if str((fiche.get('messages') or {}).get('bienvenue')) != str(mid):
                await parcours._retirer_pret(salon, uid, fiche)
            await original.edit(content=contenu, view=parcours._vue(message.guild, uid, 1, {}, fiche),
                                allowed_mentions=discord.AllowedMentions.none())
        await message.reply('✅ Message du compte 1 mis à jour dans le salon personnel. Aucun compte créé ni réattribué.')
    except Retenue as erreur:
        await message.reply('⚠️ Remise retenue : ' + str(erreur))
    except Exception:
        # Une réponse HTTP peut contenir le corps envoyé : jamais la sérialiser.
        await message.reply('⚠️ Résultat de remise non confirmé. Vérifie le message existant ; aucun nouvel envoi automatique.')
    return True
