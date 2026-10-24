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


# 18/10 (Julien, Mavie : deux jours avec un compte 1 sans accès, personne prévenu) : la raison du dernier refus d'identifiants_surs,
# par uid, pour que le parcours prévienne le salon admin avec la commande qui répare. Jamais de secret dedans.
RAISONS = {}


def modele(mention, handle, mail, mdp, codes="", suite=""):
    """Valeurs existantes uniquement ; rendu destiné au seul salon du titulaire.
    23/10 (Gaëtan : « 1️⃣ Instagram, crée un compte, utilise cet e-mail. 2️⃣ Le code reçu dans le salon #code-instagram, comme ça il peut
    cliquer direct dessus ; on enlève « Créé ? Appuie sur le bouton » ») : étapes numérotées par emoji, le salon des codes en mention
    cliquable (`codes`, sinon parcours.mention_salon_codes), plus de phrase sur le bouton (son libellé le dit). `suite` : une ligne
    en plus à la fin (les délais du parcours simple)."""
    codes = codes or parcours.mention_salon_codes()
    texte = (f"{mention}\n\n📱 **Ton compte 1**\n\n"
             f"Identifiant : `{handle}`\n\nE-mail : `{mail}`\n\nMot de passe : `{mdp}`\n\n"
             "1️⃣ Instagram → Créer un compte → utilise cet e-mail.\n\n"
             f"2️⃣ Le code arrive dans {codes}. Appuie sur « 📩 Mon code ».\n\n"
             "3️⃣ Instagram demande ta date de naissance ou ton numéro ? Mets les vrais.")
    return texte + (f"\n\n{suite}" if suite else "")


def diagnostic_lecteurs(guild, salon, uid, creatrice, admin_ids, est_staff):
    """Même décision que la remise ; projection Discord sans contenu de message ni accès Instagram."""
    uid = str(uid)
    mapping = equipes_tl.tl_par_va()
    tl = onboarding_preuves.tl_pour(uid, creatrice, mapping, equipes_tl._fiches())
    autorises = {uid, str(guild.owner_id), str(guild.me.id), *map(str, admin_ids)}
    if tl:
        autorises.add(str(tl))
    lecteurs = []
    for membre in guild.members:
        if not salon.permissions_for(membre).view_channel:
            continue
        mid = str(membre.id)
        staff = not getattr(membre, 'bot', False) and est_staff(membre)
        # 18/10 (remise retenue « un lecteur non autorisé » sur tous les salons) : un administrateur du serveur voit TOUS les
        # salons, quoi qu'on fasse ; le compter comme intrus rendait toute remise impossible. L'intrus visé reste un autre clipper.
        admin_serveur = (not getattr(membre, 'bot', False)
                         and bool(getattr(getattr(membre, 'guild_permissions', None), 'administrator', False)))
        raison = ('titulaire' if mid == uid else 'proprietaire' if membre.id == guild.owner_id
                  else 'bot_service' if membre.id == guild.me.id else 'admin_configure' if mid in set(map(str, admin_ids))
                  else 'tl_effectif' if mid == str(tl) else 'staff' if staff
                  else 'administrateur_serveur' if admin_serveur else 'non_autorise')
        roles = []
        for role in getattr(membre, 'roles', []):
            surcharge = salon.overwrites_for(role)
            roles.append({'id': str(role.id), 'nom': role.name,
                          'administrateur': bool(role.permissions.administrator),
                          'voir_base': bool(role.permissions.view_channel),
                          'voir_salon': surcharge.view_channel})
        surcharge = salon.overwrites_for(membre) if hasattr(salon, 'overwrites_for') else None
        lecteurs.append({'uid': mid, 'nom': membre.display_name if hasattr(membre, 'display_name') else '',
                         'autorise': mid in autorises or bool(staff) or admin_serveur, 'raison': raison,
                         'voir_salon_individuel': getattr(surcharge, 'view_channel', None), 'roles': roles})
    complet = bool(guild.chunked)
    public = bool(salon.permissions_for(guild.default_role).view_channel)
    return {'inventaire_complet': complet, 'salon_public': public, 'tl_effectif': str(tl) if tl else None,
            'source_tl': 'affectation_individuelle' if mapping.get(uid) else 'mandat_creatrice',
            'lecteurs': lecteurs, 'remise_autorisee': complet and not public and all(x['autorise'] for x in lecteurs)}


def verifier_lecteurs(guild, salon, uid, creatrice, admin_ids, est_staff):
    diagnostic = diagnostic_lecteurs(guild, salon, uid, creatrice, admin_ids, est_staff)
    if not diagnostic['inventaire_complet']:
        raise Retenue('Liste complète des membres non disponible : remise retenue.')
    if diagnostic['salon_public']:
        raise Retenue('Salon accessible à tous : remise retenue.')
    if not diagnostic['remise_autorisee']:
        intrus = [x['nom'] or x['uid'] for x in diagnostic['lecteurs'] if not x['autorise']]
        raise Retenue('Un lecteur non autorisé peut accéder au salon : ' + ', '.join(intrus[:5]) + '. Remise retenue.')


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
    fiche.pop('acces_en_attente', None)                                 # 18/10 : les accès sont remis, l'alerte s'éteint
    parcours._ecrire(etat)


def valeurs_ligne(ligne, onb, fiche) -> list:
    """[mail, mdp] de la ligne du classeur, seulement si elle est bien celle du clipper (Gérant, créatrice, état à créer)."""
    if (not onb.get('gerant') or onboarding._norm(ligne.get('gerant', '')) != onboarding._norm(onb['gerant'])
            or onboarding._norm(ligne.get('creatrice', '')) != onboarding._norm(fiche.get('creatrice', ''))
            or onboarding._norm(ligne.get('etat', '')) not in onboarding.A_CREER):
        raise Retenue('Affectation ou état à créer du classeur non confirmé.')
    return _mail_mdp(ligne)


def _mail_mdp(ligne) -> list:
    valeurs = [ligne.get('mail'), ligne.get('mdp')]
    if any(not isinstance(v, str) or not v.strip() or any(c in v for c in ('`', '\n', '\r')) for v in valeurs):
        raise Retenue('Champs existants incomplets ou format incompatible.')
    # 18/10 (Esperance a reçu « E-mail : Muse2!Echo#98GlowAgency », un mot de passe collé dans la colonne Mail du classeur) :
    # une adresse qui n'a pas la forme d'un e-mail n'est jamais envoyée ; la ligne est à corriger dans le classeur.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", valeurs[0].strip()):
        raise Retenue("Colonne Mail du classeur invalide pour ce compte (pas une adresse e-mail) : corrige la ligne.")
    return [v.strip() for v in valeurs]


def valeurs_compte(ligne, gerant, creatrice) -> list:
    """24/10 : [mail, mdp] d'un compte 2 ou 3. La ligne est bien la sienne (Gérant, créatrice) et pas BAN ; un compte qui existe
    déjà (GOOD) donne aussi ses accès — c'est pour s'y connecter. Pas d'exigence « à créer », contrairement au compte 1."""
    if (not str(gerant or '').strip() or onboarding._norm(ligne.get('gerant', '')) != onboarding._norm(gerant)
            or (creatrice and onboarding._norm(ligne.get('creatrice', '')) != onboarding._norm(creatrice))):
        raise Retenue('Affectation du classeur non confirmée (Gérant ou créatrice).')
    if onboarding._norm(ligne.get('etat', '')).strip() == 'ban':
        raise Retenue('Compte BAN au classeur.')
    return _mail_mdp(ligne)


async def identifiants_surs(guild, salon, uid, handle, fiche, admin_ids, est_staff):
    """18/10 (règles gelées E7 et C10 : identifiants du compte 1 — e-mail, mot de passe, @ — dans le salon perso dès l'arrivée,
    sans attendre Gaëtan) : les mêmes contrôles que `!remettre-compte1`, faits AVANT le premier envoi, sans commande. Renvoie
    (mail, mdp) si le salon n'est lisible que par des personnes autorisées et que la ligne du classeur est bien la sienne ;
    sinon None (le message part sans secret et `!remettre-compte1 UID` reste possible). Jamais de secret au journal."""
    RAISONS.pop(str(uid), None)
    try:
        verifier_lecteurs(guild, salon, str(uid), (fiche or {}).get('creatrice', ''), admin_ids, est_staff)
        lignes = [c for c in await onboarding.lire_comptes() if c.get('handle', '').lower() == str(handle).lower()]
        if len(lignes) != 1:
            raise Retenue('Ligne unique du classeur non confirmée.')
        return tuple(valeurs_ligne(lignes[0], parcours._onb(str(uid)), fiche or {}))
    except Retenue as erreur:
        RAISONS[str(uid)] = str(erreur)
        parcours.journal.warning("Compte 1 de %s sans identifiants : %s", uid, erreur)
    except Exception as erreur:                                         # noqa: BLE001 — jamais de secret ni de blocage
        RAISONS[str(uid)] = f"erreur technique ({type(erreur).__name__})"
        parcours.journal.warning("Compte 1 de %s sans identifiants (%s)", uid, type(erreur).__name__)
    return None


async def identifiants_compte(guild, salon, uid, handle, gerant, creatrice, admin_ids, est_staff):
    """24/10 (Gaëtan : « le compte deux avec identifiant, username, mail et mot de passe ») : (mail, mdp) d'un compte 2 ou 3 pour son
    message d'étape, ou pour un salon de clipping (gerant « Prénom Clipping Créatrice »). Mêmes contrôles de lecteurs que le compte 1 ;
    la ligne du classeur doit être unique et à ce Gérant (valeurs_compte). Sinon None, la raison dans RAISONS. Jamais de secret au
    journal."""
    RAISONS.pop(str(uid), None)
    try:
        verifier_lecteurs(guild, salon, str(uid), creatrice or '', admin_ids, est_staff)
        lignes = [c for c in await onboarding.lire_comptes() if c.get('handle', '').lower().lstrip('@') == str(handle).lower().lstrip('@')]
        if len(lignes) != 1:
            raise Retenue('Ligne unique du classeur non confirmée.')
        return tuple(valeurs_compte(lignes[0], gerant, creatrice))
    except Retenue as erreur:
        RAISONS[str(uid)] = str(erreur)
        parcours.journal.warning("Accès de %s pour %s non remis : %s", handle, uid, erreur)
    except Exception as erreur:                                         # noqa: BLE001
        RAISONS[str(uid)] = f"erreur technique ({type(erreur).__name__})"
        parcours.journal.warning("Accès de %s pour %s non remis (%s)", handle, uid, type(erreur).__name__)
    return None


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
            valeurs = valeurs_ligne(lignes[0], onb, fiche)
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
