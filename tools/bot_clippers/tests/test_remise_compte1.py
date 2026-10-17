"""Modèle et remise manuelle avec accès strictement fictifs."""
from pathlib import Path
import sys
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
        self.salon = N(topic='clipper-uid:42 · Salon de Fictif.', fetch_message=AsyncMock(return_value=self.original),
                       permissions_for=lambda m:N(view_channel=m.id != 0))
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
                       _onb=lambda uid:{'gerant':'Fictif'}, _comptes_ordonnes=lambda *a:['compte_fictif'],
                       _retirer_pret=self.retrait),
                   patch.dict(r.parcours._deps, {'POSTS_FORMATION':{'1':55}}),
                   patch.object(r.onboarding, 'lire_comptes', self.lecture)]:
            pa.start(); self.addCleanup(pa.stop)
        self.guild.id = 77

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
