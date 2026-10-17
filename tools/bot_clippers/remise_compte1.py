"""Remise explicite par le propriétaire : édition du compte 1 existant uniquement.

Aucun appel depuis les reprises automatiques. Aucun secret dans les retours ou logs.
"""
import re

import discord
import choix_creatrice
import onboarding
import onboarding_preuves
import equipes_tl
import parcours
import process_adapters
import process_livraison


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


def verifier_lecteurs(guild, salon, uid, creatrice, admin_ids, est_staff):
    # Sans inventaire complet, un lecteur par rôle pourrait manquer au contrôle.
    if not guild.chunked:
        raise Retenue('Liste complète des membres non disponible : remise retenue.')
    tl = onboarding_preuves.tl_pour(uid, creatrice, equipes_tl.tl_par_va(), equipes_tl._fiches())
    autorises = {uid, str(guild.owner_id), str(guild.me.id), *map(str, admin_ids)}
    if tl:
        autorises.add(str(tl))
    if salon.permissions_for(guild.default_role).view_channel:
        raise Retenue('Salon accessible à tous : remise retenue.')
    for membre in guild.members:
        if (salon.permissions_for(membre).view_channel and str(membre.id) not in autorises
                and not (not getattr(membre, 'bot', False) and est_staff(membre))):
            raise Retenue('Un lecteur non autorisé peut accéder au salon : remise retenue.')


def verifier_etat(message, uid, admin_ids, est_staff, salon_frais=None):
    guild = message.guild
    if message.author.id != guild.owner_id or str(message.author.id) not in admin_ids:
        raise Retenue('Autorisation propriétaire non confirmée.')
    fiche = parcours._lire().get(uid) or {}
    onb = parcours._onb(uid)
    handles = parcours._comptes_ordonnes(uid, onb, fiche)
    mid, sid = (fiche.get('messages') or {}).get('1'), fiche.get('salon_id')
    if not handles or not str(mid or '').isdigit() or not str(sid or '').isdigit() or parcours._cree(fiche, 1):
        raise Retenue('Compte 1 déjà créé ou message initial non identifié.')
    handle = handles[0]
    with process_adapters.store().transaction() as db:
        row = db.execute('SELECT a.id,a.uid,a.status FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?',
                         (handle.lower().lstrip('@'),)).fetchone()
        sortie = db.execute('SELECT 1 FROM jobs WHERE key=?', ('sortie:' + uid,)).fetchone()
    if not row or row[1:] != (uid, 'reserved') or sortie:
        raise Retenue('Réservation nominative non confirmée.')
    salon = salon_frais if salon_frais is not None else guild.get_channel(int(sid))
    membre = guild.get_member(int(uid))
    if (salon is None or membre is None or salon.id != int(sid) or salon.guild.id != guild.id
            or f'clipper-uid:{uid}' not in str(getattr(salon, 'topic', '')).split(' · ')):
        raise Retenue('Salon personnel non confirmé.')
    if not salon.permissions_for(membre).view_channel:
        raise Retenue('Destinataire sans accès au salon.')
    verifier_lecteurs(guild, salon, uid, fiche.get('creatrice', ''), admin_ids, est_staff)
    identite = (row[0], handle, str(mid), str(sid), fiche.get('creatrice'), onb.get('gerant'))
    return fiche, onb, handle, str(mid), salon, membre, identite


def enregistrer_reprise(uid, ancien_mid, nouveau_mid, salon_id, operation):
    """Répare les références après POST confirmé ; rejouable après écriture partielle."""
    store = process_adapters.store()
    reprise = store.get(f'remise-compte1:{uid}:{ancien_mid}')
    if reprise.get('operation') != operation or str(reprise.get('message_id')) != nouveau_mid:
        raise Retenue('Opération de reprise divergente : rapprochement requis.')
    cle = 'message-compte1:' + uid
    journal = store.get(cle)
    if str(journal.get('message_id') or '') not in ('', ancien_mid, nouveau_mid):
        raise Retenue('Référence de livraison divergente : rapprochement requis.')
    anciens = list(journal.get('messages_supprimes') or [])
    if ancien_mid not in anciens:
        anciens.append(ancien_mid)
    journal.update(etat='livre', message_id=nouveau_mid, salon=salon_id, messages_supprimes=anciens)
    store.put(cle, journal)
    etat = parcours._lire()
    fiche = etat.get(uid) or {}
    messages = fiche.get('messages') or {}
    if str(messages.get('1') or '') not in (ancien_mid, nouveau_mid) or str(fiche.get('salon_id')) != salon_id:
        raise Retenue('Référence du parcours divergente : rapprochement requis.')
    messages['1'] = nouveau_mid
    if str(messages.get('bienvenue')) == ancien_mid:
        messages['bienvenue'] = nouveau_mid
    fiche['messages'] = messages
    parcours._ecrire(etat)


async def commande(message, texte, admin_ids, est_staff=lambda membre:False):
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
            fiche, onb, handle, mid, salon, membre, identite = verifier_etat(message, uid, admin_ids, est_staff)
            try:
                original = await salon.fetch_message(int(mid))
            except discord.NotFound as erreur:
                if erreur.code != 10008:  # Unknown Message ; un salon absent n'est pas une suppression prouvée.
                    raise
                original = None
            if original is not None and original.author.id != message.guild.me.id:
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
            # Dernière attente avant validation : relire les permissions du salon depuis Discord.
            salon_frais = await message.guild.fetch_channel(salon.id)
            fiche_finale, _, _, _, _, _, identite_finale = verifier_etat(
                message, uid, admin_ids, est_staff, salon_frais)
            if identite_finale != identite:
                raise Retenue('Dossier modifié pendant la lecture : remise retenue.')
            # Aucun await entre cette revalidation locale et le POST/PATCH Discord.
            vue = parcours._vue(message.guild, uid, 1, {}, fiche_finale)
            if original is None:
                # Journal distinct pour chaque suppression confirmée. Ne jamais vider l'ancien journal.
                operation = dict(zip(('account_id', 'handle', 'ancien_message', 'salon', 'creatrice', 'gerant'), identite))
                operation['uid'] = uid
                nouveau = await process_livraison.envoyer_compte_1(
                    process_adapters.store(), salon_frais, uid, contenu, vue,
                    cle=f'remise-compte1:{uid}:{mid}', operation=operation)
                _, _, _, _, _, _, apres_envoi = verifier_etat(message, uid, admin_ids, est_staff, salon_frais)
                if apres_envoi != identite:
                    raise Retenue('Dossier modifié pendant la remise ; résultat conservé au journal pour rapprochement.')
                enregistrer_reprise(uid, mid, str(nouveau.id), str(salon.id), operation)
            else:
                await original.edit(content=contenu, view=vue, allowed_mentions=discord.AllowedMentions.none())
        await message.reply('✅ Message du compte 1 mis à jour dans le salon personnel. Aucun compte créé ni réattribué.')
    except Retenue as erreur:
        await message.reply('⚠️ Remise retenue : ' + str(erreur))
    except Exception:
        # Une réponse HTTP peut contenir le corps envoyé : jamais la sérialiser.
        await message.reply('⚠️ Résultat de remise non confirmé. Vérifie le message existant ; aucun nouvel envoi automatique.')
    return True
