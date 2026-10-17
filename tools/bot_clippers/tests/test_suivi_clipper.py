"""Fiches et boutons avec données fictives ; aucun Discord, Sheets ou accord réel."""
import ast
import asyncio
import copy
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import recrutement
import suivi_clipper as s
import support_suivi

MAINTENANT = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)


def donnees():
    compte = dict(id='compte-fictif', rang=1, statut='created', etat='Good',
                  cree_le='2026-10-15T08:00:00Z', preuve_creation='preuve-fictive',
                  publications=[dict(code='reel-fictif', publie='2026-10-16T08:00:00Z', type_verifie='reel')],
                  publications_observees=True)
    dossier = dict(uid='42', admis=True, tl_uid='73', quiz_reussi=dict(verifie=True, source='quiz_site',
                   reference='quiz-fictif', date='2026-10-14T08:00:00Z'),
                   historique_vie=dict(complet=True, reference='registre-fictif', comptes=[compte]))
    entrees = {'registre': {'42': {'creatrice': 'Créatrice exemple'}, '420': {'creatrice': 'AUTRE-UID'}},
               'parcours': {'42': {'creatrice': 'Créatrice exemple', 'dates': {'1': '2026-10-15'}}},
               'onboarding_etat': {'clippers': {'42': {'comptes': ['handle-fictif'], 'mail': 'SECRET-FICTIF', 'mdp': 'SECRET-FICTIF'}}},
               'clics': {'liens': {'propre': {'uid': '42', 'url': 'https://example.com/lien-fictif'},
                                   'autre': {'uid': '420', 'url': 'https://example.com/AUTRE-UID'},
                                   'ferme': {'uid': '42', 'url': 'https://example.com/ferme', 'archive': True},
                                   'secret': {'uid': '42', 'url': 'https://example.com/app?token=SECRET-FICTIF'}}}}
    return entrees, dossier


class ProjectionTests(unittest.TestCase):
    def construire(self, entrees=None, dossier=None, **kwargs):
        e, d = donnees()
        e = e if entrees is None else entrees
        d = d if dossier is None else dossier
        return s.construire('42', e, d, recrutement.projection(d, MAINTENANT), maintenant=MAINTENANT, **kwargs)

    def test_sources_six_faits_aucun_secret_et_aucune_mutation(self):
        e, d = donnees()
        avant = copy.deepcopy((e, d))
        fiche = self.construire(e, d, role=True, tl_uid='73', paie={'regime': 'clic', 'taux': '0.07', 'pays': 'France'})
        self.assertEqual(6, len(fiche['etapes']))
        texte = fiche['texte'] + fiche['consignes']
        for interdit in ('SECRET-FICTIF', 'AUTRE-UID', '/ferme', 'code reçu'):
            self.assertNotIn(interdit, texte)
        self.assertIn('0.07 USD', texte)
        self.assertIn('https://example.com/lien-fictif', texte)
        self.assertIn('16/10/2026', texte)
        self.assertIn('source :', texte)
        self.assertEqual(avant, (e, d))
        for t in (fiche['texte'], fiche['consignes']):
            self.assertEqual(t, s._borne(t))

    def test_uid_incoherent_refuse_meme_si_prenom_identique(self):
        e, d = donnees()
        d['uid'] = '420'
        with self.assertRaises(ValueError):
            self.construire(e, d)

    def test_reservation_date_etape_et_ancien_compteur_ne_prouvent_rien(self):
        e, d = donnees()
        compte = d['historique_vie']['comptes'][0]
        compte.update(statut='reserved', publications=[], vus=12)
        e['parcours']['42']['reels'] = {'handle-fictif': {'vus': 12}}
        fiche = self.construire(e, d)
        self.assertIn('Compte remis** — non confirmée', fiche['texte'])
        self.assertIn('Premier Reel** — non établi', fiche['texte'])

    def test_envoi_incertain_ou_refuse_ne_devient_pas_livre_au_rejeu(self):
        e, d = donnees()
        e['parcours']['42'].update(messages={'1': '123'}, salon_id='10')
        for etat in ('incertain', 'refuse'):
            livraison = {'livraison': etat, 'salon_compte1_id': '10'}
            a = self.construire(e, d, livraison=livraison, salon_id='10')
            b = self.construire(e, d, livraison=livraison, salon_id='10')
            self.assertEqual(a, b)
            self.assertNotIn('message du compte 1 enregistré', a['texte'])
        livre = self.construire(e, d, livraison={'livraison': 'livre', 'message_compte1_id': '123', 'salon_compte1_id': '10'}, salon_id='10')
        self.assertIn('envoi du compte 1 enregistré', livre['texte'])
        mauvais = self.construire(livraison={'livraison': 'livre', 'message_compte1_id': '123', 'salon_compte1_id': '99'}, salon_id='10')
        self.assertNotIn('envoi du compte 1 enregistré', mauvais['texte'])

    def test_reel_non_type_futur_ou_avant_creation_non_valide(self):
        for date, type_reel in [('2026-10-14T00:00:00Z', 'reel'), ('2026-10-18T00:00:00Z', 'reel'),
                                ('2026-10-16T00:00:00Z', 'image')]:
            e, d = donnees()
            d['historique_vie']['comptes'][0]['publications'] = [dict(code='fictif', publie=date, type_verifie=type_reel)]
            self.assertIn('Premier Reel** — non établi', self.construire(e, d)['texte'])

    def test_role_absent_conflit_et_source_indisponible_restent_visibles(self):
        e, d = donnees()
        e['parcours']['42']['creatrice'] = 'Autre créatrice'
        fiche = self.construire(e, d, role=False, lecture_etats=False)
        self.assertIn('Rôle Discord** — absent', fiche['texte'])
        self.assertIn('sources en désaccord', fiche['texte'])
        self.assertIn('État des comptes non lu', fiche['texte'])
        self.assertNotIn('Publie les', fiche['texte'])

    def test_blocage_exact_et_action_existante_sans_nouveau_gate(self):
        e, d = donnees()
        d['historique_vie']['complet'] = False
        vue = recrutement.projection(d, MAINTENANT)
        fiche = self.construire(e, d)
        self.assertIn('historique : Historique complet rapproché', fiche['texte'])
        self.assertIn(recrutement.texte_prochaine_action(vue), fiche['texte'])

    def test_accord_fixe_ou_absent_ne_devient_pas_un_taux_par_defaut(self):
        e, d = donnees()
        fixe = self.construire(e, d, paie={'regime': 'fixe', 'taux': '0.07'})['consignes']
        self.assertIn('Montant non chiffré', fixe)
        self.assertNotIn('0.07', fixe)
        del e['registre']['42']
        inconnu = self.construire(e, d, paie={'regime': 'clic', 'taux': '0.07'})['consignes']
        self.assertIn('Régime individuel non confirmé', inconnu)
        self.assertNotIn('0.07', inconnu)


class BoutonsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.collecter = AsyncMock(return_value={'uid': '42', 'texte': 'Avancement fictif', 'consignes': 'Consignes fictives'})
        self.signaler = AsyncMock(return_value={'id': 1, 'statut': 'transmis'})
        self.deps = {'collecter': self.collecter, 'signaler_support': self.signaler,
                     'est_staff': lambda u: u.staff,
                     'en_prive': lambda m: m.guild is None or m.channel.id == 10}
        s.configurer(self.deps)

    def interaction(self, uid=42, canal=10, staff=False):
        return N(user=N(id=uid, staff=staff), guild=N(id=1), channel=N(id=canal),
                 message=N(id=22, jump_url='https://discord.com/channels/1/10/22'),
                 response=N(send_message=AsyncMock(), defer=AsyncMock()), followup=N(send=AsyncMock()))

    async def test_uid_salon_et_roles_verifies_avant_lecture_ou_ticket(self):
        for action in ('consignes', 'bloque'):
            for uid, canal, staff in [(420, 10, False), (42, 11, False), (42, 10, True)]:
                interaction = self.interaction(uid, canal, staff)
                await s.BoutonSuivi('42', action).callback(interaction)
                interaction.response.send_message.assert_awaited_once()
        self.collecter.assert_not_awaited()
        self.signaler.assert_not_awaited()

    async def test_relecture_et_bouton_restaure_apres_redemarrage(self):
        client = Mock()
        s.configurer(self.deps, client)
        client.add_dynamic_items.assert_called_once_with(s.BoutonSuivi)
        match = re.fullmatch(r'suivi:(?P<uid>[0-9]+):(?P<action>consignes|bloque)', 'suivi:42:consignes')
        bouton = await s.BoutonSuivi.from_custom_id(None, None, match)
        self.collecter.side_effect = [{'uid': '42', 'consignes': 'état précédent'}, {'uid': '42', 'consignes': 'état relu'}]
        for attendu in ('état précédent', 'état relu'):
            interaction = self.interaction()
            await bouton.callback(interaction)
            self.assertEqual(attendu, interaction.followup.send.await_args.args[0])
            self.assertTrue(interaction.followup.send.await_args.kwargs['ephemeral'])
        self.signaler.assert_not_awaited()

    async def test_ticket_persistant_clics_repetes_et_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'support.db'
            notifier = AsyncMock(return_value=99)
            async def signaler(message, sujet):
                return await support_suivi.signaler(path, str(message.author.id), sujet,
                    message.guild.id, message.channel.id, message.id, 0, notifier)
            self.deps['signaler_support'] = signaler
            s.configurer(self.deps)
            bouton = s.BoutonSuivi('42', 'bloque')
            await bouton.callback(self.interaction())
            await bouton.callback(self.interaction())
            notifier.assert_awaited_once()
            self.assertEqual(1, len(support_suivi.lister(path, '42')))
            support_suivi.clore(path, '42', 1)
            notifier.side_effect = asyncio.CancelledError()
            with self.assertRaises(asyncio.CancelledError):
                await bouton.callback(self.interaction())
            self.assertEqual('envoi_incertain', support_suivi.lister(path, '42')[0]['statut'])
            notifier.reset_mock()
            s.configurer(self.deps)  # nouvelle session, même stockage durable
            interaction = self.interaction()
            await s.BoutonSuivi('42', 'bloque').callback(interaction)
            notifier.assert_not_awaited()
            self.assertIn('transmission incertaine', interaction.followup.send.await_args.args[0])
            self.assertNotIn('transmis à', interaction.followup.send.await_args.args[0])

    async def test_aucune_promesse_si_lecture_ou_notification_echoue(self):
        self.collecter.side_effect = TimeoutError()
        self.signaler.return_value = {'id': 1, 'statut': 'a_envoyer'}
        for action in ('consignes', 'bloque'):
            interaction = self.interaction()
            await s.BoutonSuivi('42', action).callback(interaction)
            texte = interaction.followup.send.await_args.args[0]
            self.assertNotIn('transmis à', texte)
            self.assertNotIn('résolu', texte)

    async def test_commande_ne_renvoie_pas_dossier_autre_uid(self):
        self.collecter.return_value = {'uid': '420', 'texte': 'AUTRE-UID'}
        message = N(author=N(id=42, staff=False), guild=N(id=1), channel=N(id=10), reply=AsyncMock())
        self.assertTrue(await s.commande(message))
        self.assertNotIn('AUTRE-UID', message.reply.await_args.args[0])
        self.signaler.assert_not_awaited()


class CollecteTests(unittest.IsolatedAsyncioTestCase):
    async def test_adaptateur_reel_lit_le_bon_uid_et_ne_confond_pas_un_nom_de_role(self):
        import diagnostic_dossier
        e, _ = donnees()
        e['historique_vie'] = {'disponible': True, 'revus': ['42'], 'comptes': [
            {'uid': '42', 'id': 'identite-fictive', 'status': 'reserved', 'aliases': ['handle-fictif']},
            {'uid': '420', 'id': 'autre-identite', 'status': 'created', 'aliases': ['autre-handle']}]}
        e['parcours']['42']['ordre'] = 'prive3'
        pipeline = {'etats': {'42': {'valide_par': 'quiz', 'validation': '2026-10-14T08:00:00Z', 'score_quiz': 8}}}
        regime = Mock(return_value='fixe')
        etats = AsyncMock(return_value=[{'handle': 'handle-fictif', 'etat': 'à créer'}])
        serveur = N(id=42, roles=[N(name='Faux Clipper')])
        ns = {'controle': N(lire_entrees=lambda: copy.deepcopy(e)), 'lire_json': lambda *_: pipeline,
              'FICHIER_PIPELINE': Path('/inutilise'), 'DONNEES': Path('/inutilise'),
              'parcours': N(_comptes_ordonnes=lambda uid, **kw: kw['onb']['comptes'], ordre=lambda _: 'prive3'),
              'onboarding': N(lire_comptes=etats), 'est_signe': lambda _: True,
              'membre_par_id': lambda uid: serveur, 'normaliser': str.lower,
              'ROLES_EQUIPE_ACCEPTES': ['Clipper'], 'NOMS_RANGS': [], 'ROLE_CLIPPER_NOM': 'Clipper',
              'ROLE_TEAM_FR_NOM': 'Team FR', 'ROLE_TEAM_MG_NOM': 'Team MG',
              'equipes_tl': N(composition=lambda **_: {'propre': {'tl': '73', 'vas': ['42']},
                                                     'autre': {'tl': '74', 'vas': ['420']}}),
              'paie_clics': N(regime=regime, TAUX_CLIC=.07, PAYS_LIBELLE='France'),
              'salon_perso_de': lambda uid: N(id=10), 'suivi_clipper': s}
        tree = ast.parse((ROOT / 'bot_discord.py').read_text())
        fn = next(n for n in tree.body if getattr(n, 'name', '') == 'lire_fiche_suivi')
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'collecte-fictive', 'exec'), ns)
        with patch.object(diagnostic_dossier, 'registre', return_value={}) as registre:
            fiche = await ns['lire_fiche_suivi'](N(id=42, guild=None))
            registre.assert_called_once_with(Path('/inutilise/process_clippeur.sqlite3'), '42')
        regime.assert_called_once_with('42')
        self.assertIn('Rôle Discord** — absent', fiche['texte'])
        self.assertIn('<@73>', fiche['texte'])
        self.assertNotIn('<@74>', fiche['texte'])
        self.assertIn('Forfait fixe', fiche['consignes'])
        self.assertNotIn('AUTRE-UID', fiche['consignes'])
        serveur.roles = [N(name='Clipper')]
        with patch.object(diagnostic_dossier, 'registre', return_value={}):
            fiche = await ns['lire_fiche_suivi'](N(id=42, guild=None))
        self.assertIn('Rôle Discord** — présent', fiche['texte'])
        etats.side_effect = OSError('ERREUR-FICTIVE-NE-PAS-REPRENDRE')
        with patch.object(diagnostic_dossier, 'registre', return_value={}):
            fiche = await ns['lire_fiche_suivi'](N(id=42, guild=None))
        self.assertIn('État des comptes non lu', fiche['texte'])
        self.assertNotIn('ERREUR-FICTIVE', fiche['texte'])

    def test_remise_courte_ne_promet_pas_un_acces_deja_livre(self):
        arbre = ast.parse((ROOT / 'parcours.py').read_text())
        fonction = next(n for n in arbre.body if getattr(n, 'name', '') == '_identifiants')
        ns = {}
        exec(compile(ast.Module(body=[fonction], type_ignores=[]), 'remise-fictive', 'exec'), ns)
        texte = ns['_identifiants'](1)
        self.assertLess(len(texte), 130)
        self.assertIn('à confirmer', texte)
        self.assertNotIn('mot de passe', texte)


if __name__ == '__main__':
    unittest.main()
