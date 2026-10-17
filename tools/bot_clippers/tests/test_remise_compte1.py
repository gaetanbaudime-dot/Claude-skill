"""Modèle et remise manuelle avec accès strictement fictifs."""
from pathlib import Path
import sys
import asyncio
import discord
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import remise_compte1 as r
from process_store import Store


class Remise(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'fictif.sqlite3')
        self.store.reconcile('42', [], 'fictif'); self.store.reserve('42', ['compte_fictif'])
        self.original = N(author=N(id=90), edit=AsyncMock())
        self.salon = N(id=99, topic='clipper-uid:42 · Salon de Fictif.', fetch_message=AsyncMock(return_value=self.original),
                       permissions_for=lambda m:N(view_channel=m.id != 0, read_message_history=True),
                       send=AsyncMock(return_value=N(id=123)))
        self.membre = N(id=42, mention='<@42>')
        self.guild = N(owner_id=1, me=N(id=90), default_role=N(id=0),
                       get_channel=lambda sid:self.salon, get_member=lambda uid:self.membre)
        self.message = N(author=N(id=1), guild=self.guild, reply=AsyncMock())
        self.fiche = {'salon_id':'99', 'creatrice':'Fictive', 'messages':{'1':'100','bienvenue':'98'}, 'dates':{'1':'fictif'}}
        self.ligne = {'handle':'compte_fictif', 'mail':'fictif@example.invalid', 'mdp':'MOT_DE_PASSE_FICTIF',
                      'gerant':'Fictif', 'creatrice':'Fictive', 'etat':'à créer'}
        self.lecture = AsyncMock(side_effect=lambda:[dict(self.ligne)])
        self.retrait = AsyncMock()
        for pa in [patch.object(r.process_adapters, 'store', return_value=self.store),
                   patch.multiple(r.parcours, _lire=lambda:{'42':self.fiche},
                       _ecrire=lambda data:setattr(self, 'fiche', data['42']),
                       _onb=lambda uid:{'gerant':'Fictif'}, _comptes_ordonnes=lambda *a:['compte_fictif'],
                       _retirer_pret=self.retrait),
                   patch.dict(r.parcours._deps, {'POSTS_FORMATION':{'1':55}}),
                   patch.object(r.onboarding, 'lire_comptes', self.lecture)]:
            pa.start(); self.addCleanup(pa.stop)
        self.guild.id = 77
        self.salon.guild = self.guild
        self.guild.chunked = True
        self.guild.members = [self.membre, self.guild.me, self.message.author]
        self.guild.fetch_channel = AsyncMock(return_value=self.salon)
        for pa in [patch.object(r.equipes_tl, 'tl_par_va', return_value={}),
                   patch.object(r.equipes_tl, '_fiches', return_value={})]:
            pa.start(); self.addCleanup(pa.stop)

    async def appeler(self):
        return await r.commande(self.message, '!remettre-compte1 42', {'1'})

    async def test_modele_court_edition_existante_boutons_et_aucun_secret_dans_retour(self):
        await self.appeler()
        self.original.edit.assert_awaited_once()
        kw = self.original.edit.call_args.kwargs
        attendu = ('<@42>\n\n**Étape 1 · Crée ton compte 1**\n\n'
                   'Identifiant : `compte_fictif`\n\nE-mail : `fictif@example.invalid`\n\n'
                   'Mot de passe : `MOT_DE_PASSE_FICTIF`\n\n')
        self.assertTrue(kw['content'].startswith(attendu))
        self.assertNotIn('proposé', kw['content'])
        self.assertNotIn('WhatsApp', kw['content'])
        labels = [getattr(x, 'label', getattr(getattr(x, 'item', None), 'label', '')) for x in kw['view'].children]
        self.assertIn('📄 Fiche 1', labels)
        self.assertIn('✅ Compte 1 créé', labels)
        self.assertEqual(2, len(labels))
        self.retrait.assert_awaited_once()
        self.assertNotIn('MOT_DE_PASSE_FICTIF', str(self.message.reply.call_args_list))
        self.assertNotIn('1_fait', self.fiche['dates'])

    async def test_non_proprietaire_aucune_lecture(self):
        self.message.author.id = 2
        await self.appeler()
        self.lecture.assert_not_awaited(); self.original.edit.assert_not_awaited()

    async def test_ligne_autre_titulaire_ou_non_neuve_refusee(self):
        for cle, valeur in [('gerant','Autre'), ('creatrice','Autre'), ('etat','GOOD')]:
            original = self.ligne[cle]; self.ligne[cle] = valeur
            await self.appeler(); self.original.edit.assert_not_awaited()
            self.ligne[cle] = original

    async def test_secret_manquant_aucun_repli(self):
        self.ligne['mdp'] = ''
        await self.appeler(); self.original.edit.assert_not_awaited()

    async def test_erreur_transport_ne_divulgue_pas_corps(self):
        self.original.edit.side_effect = RuntimeError('MOT_DE_PASSE_FICTIF')
        await self.appeler()
        self.assertNotIn('MOT_DE_PASSE_FICTIF', str(self.message.reply.call_args_list))

    async def test_accueil_fusionne_garde_boutons(self):
        self.fiche['messages']['bienvenue'] = '100'
        await self.appeler(); self.retrait.assert_not_awaited()
        self.original.edit.assert_awaited_once()

    async def test_compte_deja_cree_refuse(self):
        self.store.created('42', 'compte_fictif', 'preuve-fictive')
        await self.appeler(); self.lecture.assert_not_awaited()
        self.original.edit.assert_not_awaited()

    async def test_salon_public_message_etranger_et_ligne_double_refuses(self):
        permissions = self.salon.permissions_for
        self.salon.permissions_for = lambda m:N(view_channel=True)
        await self.appeler(); self.original.edit.assert_not_awaited()
        self.salon.permissions_for = permissions
        self.original.author.id = 91
        await self.appeler(); self.original.edit.assert_not_awaited()
        self.original.author.id = 90
        self.lecture.side_effect = lambda:[dict(self.ligne), dict(self.ligne)]
        await self.appeler(); self.original.edit.assert_not_awaited()

    async def test_rejeu_modifie_meme_message_sans_allocation(self):
        await self.appeler(); await self.appeler()
        self.assertEqual(2, self.original.edit.await_count)
        self.assertEqual(self.original.edit.call_args_list[0].kwargs['content'], self.original.edit.call_args_list[1].kwargs['content'])
        self.assertEqual({'reserved':1}, self.store.counts('42'))

    async def test_lecteur_via_role_clippeurs_refuse(self):
        autre = N(id=43, roles=['Clippeur'])
        self.guild.members.append(autre)
        self.salon.permissions_for = lambda m:N(view_channel=m.id in (1, 42, 90) or 'Clippeur' in getattr(m, 'roles', []))
        await self.appeler()
        self.lecture.assert_not_awaited(); self.original.edit.assert_not_awaited()

    async def test_membre_supplementaire_et_bot_refuses(self):
        self.guild.members.append(N(id=43, bot=True))
        await self.appeler()
        self.lecture.assert_not_awaited(); self.original.edit.assert_not_awaited()

    async def test_cache_incomplet_refuse(self):
        self.guild.chunked = False
        await self.appeler(); self.original.edit.assert_not_awaited()

    async def test_tl_configure_et_staff_autorises(self):
        self.guild.members.extend([N(id=43), N(id=44)])
        with patch.object(r.equipes_tl, 'tl_par_va', return_value={'42':'43'}):
            await r.commande(self.message, '!remettre-compte1 42', {'1'}, lambda m:m.id==44)
        self.original.edit.assert_awaited_once()

    async def mutation_durant_lecture(self, mutation):
        async def lecture():
            mutation()
            return [dict(self.ligne)]
        self.lecture.side_effect = lecture
        await self.appeler()
        self.original.edit.assert_not_awaited()
        self.assertNotIn('MOT_DE_PASSE_FICTIF', str(self.message.reply.call_args_list))

    async def test_creation_pendant_lecture_refusee(self):
        await self.mutation_durant_lecture(lambda:self.store.created('42', 'compte_fictif', 'preuve-fictive'))

    async def test_sortie_pendant_lecture_refusee(self):
        await self.mutation_durant_lecture(lambda:self.store.put('sortie:42', {'etat':'fictif'}))

    async def test_salon_change_pendant_lecture_refuse(self):
        await self.mutation_durant_lecture(lambda:self.fiche.update(salon_id='98'))

    async def test_message_change_pendant_lecture_refuse(self):
        await self.mutation_durant_lecture(lambda:self.fiche['messages'].update({'1':'101'}))

    async def test_pseudo_change_pendant_lecture_refuse(self):
        def changer():
            self.store.reserve('42', ['autre_fictif'])
            r.parcours._comptes_ordonnes = lambda *a:['autre_fictif']
        await self.mutation_durant_lecture(changer)

    async def test_lecteur_ajoute_pendant_lecture_refuse(self):
        await self.mutation_durant_lecture(lambda:self.guild.members.append(N(id=43)))

    async def test_permissions_fraiches_du_salon_refusees(self):
        frais = N(id=99, guild=self.guild, topic=self.salon.topic, permissions_for=lambda m:N(view_channel=True))
        self.guild.fetch_channel.return_value = frais
        await self.appeler(); self.original.edit.assert_not_awaited()

    def message_supprime(self):
        def lire(mid):
            if mid == 100:
                raise discord.NotFound(N(status=404, reason='fictif'), {'code':10008, 'message':'Unknown Message'})
            return self.original
        self.salon.fetch_message.side_effect = lire

    async def test_message_supprime_recree_une_fois_et_references_reparees(self):
        self.message_supprime()
        self.fiche['messages']['bienvenue'] = '100'
        await self.appeler(); await self.appeler()
        self.salon.send.assert_awaited_once()
        self.assertEqual('123', self.fiche['messages']['1'])
        self.assertEqual('123', self.fiche['messages']['bienvenue'])
        self.assertEqual('123', self.store.get('message-compte1:42')['message_id'])
        self.assertEqual(['100'], self.store.get('message-compte1:42')['messages_supprimes'])
        self.assertEqual({'reserved':1}, self.store.counts('42'))
        self.assertNotIn('1_fait', self.fiche['dates'])
        self.assertNotIn('MOT_DE_PASSE_FICTIF', str(self.message.reply.call_args_list))

    async def test_fetch_interdit_timeout_ou_salon_absent_ne_recree_pas(self):
        for erreur in [discord.Forbidden(N(status=403, reason='fictif'), 'refus'), TimeoutError(),
                       discord.NotFound(N(status=404, reason='fictif'), {'code':10003, 'message':'Unknown Channel'})]:
            self.salon.fetch_message.side_effect = erreur
            await self.appeler()
            self.salon.send.assert_not_awaited()
            self.lecture.assert_not_awaited()

    async def test_post_refuse_rejouable_sans_nouvelle_reservation(self):
        self.message_supprime()
        self.salon.send.side_effect = [discord.Forbidden(N(status=403, reason='fictif'), 'refus'), N(id=123)]
        await self.appeler()
        self.assertEqual('refuse', self.store.get('remise-compte1:42:100')['etat'])
        await self.appeler()
        self.assertEqual(2, self.salon.send.await_count)
        self.assertEqual('123', self.fiche['messages']['1'])
        self.assertEqual({'reserved':1}, self.store.counts('42'))

    async def test_post_incertain_retrouve_sans_second_envoi(self):
        self.message_supprime()
        recu = None
        async def envoyer(texte, **kwargs):
            nonlocal recu
            recu = N(id=123, content=texte, author=self.guild.me)
            raise TimeoutError()
        async def historique(**kwargs):
            yield recu
        self.salon.send.side_effect = envoyer
        self.salon.history = historique
        await self.appeler(); await self.appeler()
        self.salon.send.assert_awaited_once()
        self.assertEqual('123', self.fiche['messages']['1'])

    async def test_post_incertain_introuvable_ne_recree_pas(self):
        self.message_supprime()
        async def historique(**kwargs):
            if False: yield None
        self.salon.history = historique
        self.salon.send.side_effect = TimeoutError()
        await self.appeler(); await self.appeler()
        self.salon.send.assert_awaited_once()
        self.assertEqual('incertain', self.store.get('remise-compte1:42:100')['etat'])
        self.assertEqual('100', self.fiche['messages']['1'])

    async def test_reprise_apres_ecriture_json_partielle_sans_second_post(self):
        self.message_supprime()
        ecrire = r.parcours._ecrire
        with patch.object(r.parcours, '_ecrire', side_effect=OSError('fictif')):
            await self.appeler()
        self.assertEqual('123', self.store.get('message-compte1:42')['message_id'])
        # Simule un vrai JSON resté à l'ancien message, distinct du dict fourni à l'écriture.
        self.fiche['messages']['1'] = '100'
        await self.appeler()
        self.salon.send.assert_awaited_once()
        self.assertEqual('123', self.fiche['messages']['1'])

    async def test_deux_commandes_concurrentes_un_seul_post(self):
        self.message_supprime()
        await asyncio.gather(self.appeler(), self.appeler())
        self.salon.send.assert_awaited_once()

    async def test_suppression_confirmee_mais_sortie_pendant_sheets_aucun_post(self):
        self.message_supprime()
        await self.mutation_durant_lecture(lambda:self.store.put('sortie:42', {'etat':'fictif'}))
        self.salon.send.assert_not_awaited()
