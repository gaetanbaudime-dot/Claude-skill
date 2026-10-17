"""Fiche personnelle en lecture seule ; le bouton réutilise les tickets existants.

Une réservation, une date d'étape ou un compteur ancien ne prouvent ni une remise
ni un Reel. Aucun accès Instagram, code, portefeuille ou lien d'app dans la fiche.
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from types import SimpleNamespace

import discord
import recrutement
from process_clippeur import cumuler_reels_verifies

_deps = {}

# Domaines publics attestés dans onboarding.py et visites_telegram.py ; les
# pages de clipping numérotées sont reconnues par reserve_mym.numero_du_lien.
# Tout nouveau domaine/format demande une vérification avant ajout à cette liste.
_LIEN_GAML_PUBLIC = re.compile(
    r'https://(?:chloe-callista\.fr|sarah-ivanova\.fr|sophievan\.fr|jadetora\.fr)/[0-9]+/?',
    re.IGNORECASE | re.ASCII,
)


def configurer(deps, client=None):
    _deps.clear()
    _deps.update(deps)
    if client is not None:
        client.add_dynamic_items(BoutonSuivi)


def _fiche(data, *cles):
    for cle in cles:
        if not isinstance(data, dict):
            return {}
        data = data.get(cle)
    return data if isinstance(data, dict) else {}


def _texte(valeur, limite=100):
    texte = ' '.join(str(valeur or '').split())[:limite]
    return discord.utils.escape_markdown(discord.utils.escape_mentions(texte))


def _date(valeur):
    date = recrutement.instant(valeur)
    return date.astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if date else 'date non vérifiable'


def _url_publique(valeur):
    # HTTPS seul ne prouve pas qu'un lien est public : un jeton peut se trouver
    # dans /app/<jeton>. Le format exact exclut aussi ports, sous-domaines,
    # identifiants, paramètres, fragments, encodages et chemins supplémentaires.
    return valeur if (isinstance(valeur, str) and len(valeur) <= 220
                      and _LIEN_GAML_PUBLIC.fullmatch(valeur)) else ''


def construire(uid, entrees, dossier, vue, *, role=None, tl_uid='', livraison=None,
               salon_id='', paie=None, maintenant=None, lecture_etats=True):
    """Projection bornée des sources du seul UID ; aucune recherche par prénom."""
    uid = str(uid)
    if not re.fullmatch(r'[0-9]{1,22}', uid) or str(dossier.get('uid')) != uid or str(vue.get('uid')) != uid:
        raise ValueError('UID incohérent')
    maintenant = maintenant or datetime.now(timezone.utc)
    registre = _fiche(entrees, 'registre', uid)
    onb = _fiche(entrees, 'onboarding_etat', 'clippers', uid)
    route = _fiche(entrees, 'parcours', uid)
    choix = {str(f.get('creatrice')).strip() for f in (registre, onb, route) if f.get('creatrice')}
    creatrice = _texte(next(iter(choix)), 40) if len(choix) == 1 else ''
    quiz = dossier.get('quiz_reussi') or {}
    quiz_ok = recrutement.preuve_valide(quiz, maintenant) and not dossier.get('conflit_identite')
    etapes = [
        ('Quiz', 'réussi le ' + _date(quiz.get('date')) if quiz_ok else 'preuve à vérifier',
         'quiz du site' if quiz.get('source') == 'quiz_site' else 'dossier du quiz'),
        ('Rôle Discord', {True: 'présent', False: 'absent', None: 'non vérifiable'}.get(role, 'non vérifiable'), 'membre Discord'),
        ('Créatrice', creatrice or ('sources en désaccord' if len(choix) > 1 else 'non confirmée'), 'affectations enregistrées'),
        ('Team leader', f'<@{tl_uid}>' if re.fullmatch(r'[0-9]{1,22}', str(tl_uid)) else 'non confirmé', 'organigramme effectif'),
    ]
    livraison = livraison or {}
    meme_salon = bool(salon_id and str(livraison.get('salon_compte1_id')) == str(salon_id))
    remise = 'non confirmée'
    if livraison.get('livraison') == 'livre' and livraison.get('message_compte1_id') and meme_salon:
        remise = 'envoi du compte 1 enregistré'
    elif livraison.get('livraison') == 'incertain':
        remise = 'envoi incertain : vérifier le salon avant tout renvoi'
    elif livraison.get('livraison') == 'refuse':
        remise = 'envoi refusé, remise non confirmée'
    elif (route.get('messages') or {}).get('1') and str(route.get('salon_id')) == str(salon_id) and salon_id:
        remise = 'message du compte 1 enregistré (trace du parcours)'
    etapes.append(('Compte remis', remise, 'journal de livraison / parcours'))
    publies = []
    for compte in (dossier.get('historique_vie') or {}).get('comptes') or []:
        creation = recrutement.instant(compte.get('cree_le'))
        if compte.get('statut') == 'created' and compte.get('preuve_creation') and creation and creation <= maintenant:
            reels = cumuler_reels_verifies({}, compte.get('publications'), creation, maintenant)
            publies.extend(recrutement.instant(t) for t in reels.values() if recrutement.instant(t))
    etapes.append(('Premier Reel', 'vérifié le ' + _date(min(publies).isoformat()) if publies else 'non établi par les preuves lues',
                   'Reels typés et datés du compte'))
    blocages = [f"{_texte(b.get('code'), 45)} : {_texte(b.get('preuve_manquante'), 160)}"
                for b in vue.get('blocages') or []][:3]
    if not lecture_etats:
        blocages.insert(0, 'État des comptes non lu : vérification nécessaire, aucune nouvelle création conseillée.')
    prochaine = recrutement.texte_prochaine_action(vue) if lecture_etats else 'Ton équipe doit vérifier les sources de ton étape.'
    lignes = [f"🧭 **Ton avancement · {_date(maintenant.isoformat())}**", '']
    lignes += [f'• **{nom}** — {etat} · source : {source}.' for nom, etat, source in etapes]
    lignes += ['', prochaine]
    if blocages:
        lignes += ['', '**Blocage du diagnostic**', *('• ' + b for b in blocages)]
    if dossier.get('sorti'):
        lignes += ['', 'Départ enregistré : toute reprise demande une vérification par ton équipe.']
    lignes += ['', 'Les boutons sont facultatifs ; ils ne valident aucune étape.']
    action = vue.get('prochaine_action') or {}
    motif = ((vue.get('blocages') or [{}])[0].get('code') or action.get('code')) if lecture_etats else 'source_indisponible'
    motif = motif if re.fullmatch(r'[a-z_]{1,45}', str(motif)) else 'verification'
    diagnostic = prochaine + ('\n\nÀ vérifier : ' + blocages[0] if blocages else '')
    return {'uid': uid, 'texte': '\n'.join(lignes), 'diagnostic': diagnostic,
            'escalade': not lecture_etats or str(action.get('responsable')) != uid,
            'motif_support': 'blocage du parcours : ' + motif,
            'consignes': consignes(uid, entrees, creatrice, paie, maintenant),
            'etapes': etapes, 'blocages': blocages}


def consignes(uid, entrees, creatrice, paie, maintenant):
    lignes = [f"📌 **Tes consignes · état lu le {_date(maintenant.isoformat())}**", '',
              'Créatrice : ' + (creatrice or 'à vérifier dans ton dossier') + '.',
              'Suis ton message d’étape existant. `!etape` relit ton avancement sans relancer la livraison.',
              'Pour les accès, consulte ton responsable. Ne partage aucun code ni mot de passe.', '']
    liens = []
    for info in _fiche(entrees, 'clics', 'liens').values():
        if not isinstance(info, dict) or str(info.get('uid')) != uid:
            continue
        if any(info.get(k) for k in ('archive', 'libere', 'hors_clipping', 'supprime_gaml', 'desactive')):
            continue
        url = _url_publique(info.get('url'))
        if url and url not in liens:
            liens.append(url)
    lignes.append('**Liens rattachés à ton UID dans le registre**')
    lignes += [f'<{lien}>' for lien in liens[:3]] or ['Aucun lien publiable confirmé ici : fais vérifier ton dossier.']
    lignes += ['Utilise seulement le lien prévu par ton étape ; cette fiche ne vérifie pas son ouverture.', '',
               '**Statistiques** — `!mesclics` dans ton salon ou en MP. Un relevé absent est non mesuré, pas zéro.', '',
               '**Rémunération appliquée par le bot**']
    paie = paie or {}
    if not _fiche(entrees, 'registre', uid):
        lignes.append('Régime individuel non confirmé : ton équipe doit consulter ton accord.')
    elif paie.get('regime') == 'fixe':
        lignes.append('Forfait fixe. Montant non chiffré dans cette source ; ton accord individuel fait référence.')
    elif paie.get('regime') == 'clic':
        try:
            taux = Decimal(str(paie.get('taux')))
            if not taux.is_finite() or taux < 0 or taux > 1000:
                raise ValueError('Taux non vérifiable')
            lignes.append(f'Au clic : {taux.normalize():f} USD par visite payable ({_texte(paie.get("pays"), 100)}, hors robots).')
        except (InvalidOperation, ValueError):
            lignes.append('Au clic ; taux non vérifiable dans la configuration lue.')
    else:
        lignes.append('Régime individuel non vérifiable : fais confirmer ton accord par ton équipe.')
    lignes += ['Source : moteur de paie existant pour ton UID ; cette lecture ne modifie aucun accord.']
    return '\n'.join(lignes)


def _autorise(user, guild, channel, uid):
    if str(getattr(user, 'id', '')) != str(uid):
        return False
    if not _deps.get('en_prive') or not _deps.get('est_staff'):
        return False
    return (not _deps['est_staff'](user)
            and _deps['en_prive'](SimpleNamespace(author=user, guild=guild, channel=channel)))


def _borne(texte):
    # Pas de coupure silencieuse d'une preuve ou d'un blocage.
    if len(texte.encode('utf-16-le')) // 2 > 1990:
        return 'La fiche dépasse la taille affichable. Ton équipe doit consulter le diagnostic ; aucune étape validée ici.'
    return texte


def vue(uid):
    resultat = discord.ui.View(timeout=None)
    resultat.add_item(BoutonSuivi(uid, 'consignes'))
    resultat.add_item(BoutonSuivi(uid, 'bloque'))
    return resultat


async def commande(message):
    uid = str(message.author.id)
    if not _autorise(message.author, message.guild, message.channel, uid):
        return False
    try:
        fiche = await asyncio.wait_for(_deps['collecter'](message.author), timeout=20)
        texte = fiche['texte'] if fiche.get('uid') == uid else 'Dossier non vérifiable pour ton UID.'
    except Exception:
        texte = 'Ton avancement n’est pas vérifiable pour le moment. Aucune livraison relancée ; ton équipe doit vérifier ton dossier.'
    await message.reply(_borne(texte), view=vue(uid), allowed_mentions=discord.AllowedMentions.none())
    return True


class BoutonSuivi(discord.ui.DynamicItem[discord.ui.Button], template=r'suivi:(?P<uid>[0-9]{1,22}):(?P<action>consignes|bloque)'):
    def __init__(self, uid, action):
        self.uid, self.action = str(uid), action
        super().__init__(discord.ui.Button(label='Mes consignes' if action == 'consignes' else 'Je suis bloqué',
            style=discord.ButtonStyle.secondary, custom_id=f'suivi:{uid}:{action}'))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['uid'], match['action'])

    async def callback(self, interaction):
        if not _autorise(interaction.user, interaction.guild, interaction.channel, self.uid):
            await interaction.response.send_message('Ce bouton concerne uniquement ton propre dossier, en MP ou dans ton salon personnel.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            fiche = await asyncio.wait_for(_deps['collecter'](interaction.user), timeout=20)
            if fiche.get('uid') != self.uid:
                texte = 'Dossier non vérifiable pour ton UID.'
            elif self.action == 'consignes':
                texte = fiche['consignes']
            elif not fiche.get('escalade'):
                texte = fiche['diagnostic'] + '\n\nDécris précisément ce qui t’empêche de faire cette action dans ton salon, avec une capture sans code ni mot de passe. Aucun ticket transmis par ce bouton.'
            else:
                # Le message du bot est une référence de contexte, pas une preuve du problème.
                source = interaction.message
                demande = SimpleNamespace(author=interaction.user, guild=interaction.guild, channel=interaction.channel,
                    id=source.id, jump_url=source.jump_url, attachments=[])
                retour = await _deps['signaler_support'](demande, fiche['motif_support'])
                ident = int(retour['id'])
                texte = {'transmis': f'Ticket #{ident} transmis à l’équipe. Aucun délai confirmé.',
                         'envoi_incertain': f'Ticket #{ident} enregistré ; transmission incertaine, à vérifier avant tout renvoi.',
                         'a_envoyer': f'Ticket #{ident} enregistré ; transmission non confirmée.'}.get(
                             retour.get('statut'), 'Transmission non confirmée. Ton équipe doit vérifier le ticket.')
                texte = fiche['diagnostic'] + '\n\n' + texte
                texte += ' Décris le blocage et ajoute ta capture dans ton salon ; ne partage aucun code ni mot de passe.'
        except Exception:
            texte = 'Résultat non vérifiable. Ne suppose pas que ton équipe a reçu le signalement ; fais vérifier le dossier.'
        await interaction.followup.send(_borne(texte), ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
