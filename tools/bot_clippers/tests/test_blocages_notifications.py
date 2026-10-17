"""Notifications fictives ; aucune mutation Discord."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import attribution as a


class Notifications(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.etat={}
        self.m=SimpleNamespace(id=3,mention='<@3>')
        self.admin=SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=7)))
        self.patches=[patch.object(a,'_etat',side_effect=lambda:deepcopy(self.etat)),patch.object(a,'_ecrire',side_effect=self.ecrire),patch.dict(a._deps,{'canal_admin':AsyncMock(return_value=self.admin)})]
        for p in self.patches: p.start();self.addCleanup(p.stop)

    def ecrire(self,e):
        self.etat=deepcopy(e)

    async def test_meme_blocage_une_fois_puis_resolution_et_recidive(self):
        for _ in range(18):
            await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu : onboarding en attente')
        self.assertEqual(1,self.admin.send.await_count)
        await a.signaler_blocage(self.m,'Fictive','✅ Compte 1 livré (message confirmé) · lignes déjà affectées ; la livraison effective est suivie séparément dans le parcours.')
        self.assertNotIn('3',self.etat['blocages_notifications'])
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu : onboarding en attente')
        self.assertEqual(2,self.admin.send.await_count)

    async def test_nouveau_blocage_et_creatrice_distincts(self):
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        await a.signaler_blocage(self.m,'Fictive','⚠️ Accès Drive non vérifié')
        await a.signaler_blocage(self.m,'Autre','⚠️ Accès Drive non vérifié')
        self.assertEqual(3,self.admin.send.await_count)

    async def test_timeout_ne_renvoie_pas_et_ne_change_pas_decision(self):
        self.etat={'decision_creatrice':{'creatrice':'Fictive'}}
        self.admin.send.side_effect=TimeoutError()
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.assertEqual(1,self.admin.send.await_count)
        self.assertEqual('envoi_incertain',self.etat['blocages_notifications']['3']['etat'])
        self.assertEqual({'creatrice':'Fictive'},self.etat['decision_creatrice'])

    async def test_modification_pendant_resolution_canal_conservee(self):
        async def canal():
            self.etat['ordre_force']='Fictive:2'
            return self.admin
        with patch.dict(a._deps,{'canal_admin':canal}):
            await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.assertEqual('Fictive:2',self.etat['ordre_force'])

    async def test_resolution_pendant_canal_annule_ancienne_alerte_pas_recidive(self):
        async def canal():
            a.resoudre_blocage('3')
            return self.admin
        with patch.dict(a._deps, {'canal_admin': canal}):
            await a.signaler_blocage(self.m, 'Fictive', '⚠️ Team leader absent ou ambigu')
        self.admin.send.assert_not_awaited()
        self.assertNotIn('3', self.etat['blocages_notifications'])
        # Un nouvel événement, même de même cause, utilise la génération actuelle.
        await a.signaler_blocage(self.m, 'Fictive', '⚠️ Team leader absent ou ambigu')
        self.admin.send.assert_awaited_once()
        self.assertEqual('envoye', self.etat['blocages_notifications']['3']['etat'])

    async def test_resolution_autre_membre_pendant_canal_ne_masque_pas_blocage(self):
        async def canal():
            a.resoudre_blocage('4')
            return self.admin
        with patch.dict(a._deps, {'canal_admin': canal}):
            await a.signaler_blocage(self.m, 'Fictive', '⚠️ Team leader absent ou ambigu')
        self.admin.send.assert_awaited_once()
        self.assertEqual('envoye', self.etat['blocages_notifications']['3']['etat'])

    async def test_forbidden_permet_reprise_et_redemarrage_conserve_incertain(self):
        import discord
        self.admin.send.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='fictif'),'refus fictif')
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.assertNotIn('3',self.etat['blocages_notifications'])
        self.admin.send.side_effect=TimeoutError()
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.etat=deepcopy(self.etat)  # même contenu persistant après relecture
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.assertEqual(2,self.admin.send.await_count)

    async def test_resolution_pendant_envoi_pas_ressuscitee(self):
        async def envoyer(*args):
            a.resoudre_blocage('3')
            return SimpleNamespace(id=9)
        self.admin.send.side_effect=envoyer
        await a.signaler_blocage(self.m,'Fictive','⚠️ Team leader absent ou ambigu')
        self.assertNotIn('3',self.etat['blocages_notifications'])

    def test_reservation_seule_reste_bloquee_livraison_confirmee_non(self):
        self.assertTrue(a.a_signaler('📦 lignes déjà affectées ; livraison suivie séparément'))
        self.assertFalse(a.a_signaler('✅ Compte 1 livré (message confirmé) · lignes déjà affectées ; livraison suivie séparément'))
