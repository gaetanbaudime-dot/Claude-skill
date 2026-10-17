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
        await a.signaler_blocage(self.m,'Fictive','✅ 1 compte(s)')
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
