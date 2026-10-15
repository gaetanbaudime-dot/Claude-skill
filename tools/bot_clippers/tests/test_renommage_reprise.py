"""Renommages fictifs, Sheet et fichiers doublés ; aucun identifiant d'accès."""
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import AsyncMock,patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import onboarding as o
import parcours
import process_adapters
import series
from process_store import Store

class RenommageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'p.sqlite3')
        self.data={'clippers':{'42':{'comptes':['ancien'],'acces':[{'handle':'ancien'}]}},'livres':{'ancien':{'uid':'42'}}}
        self.rows=[{'handle':'ancien','onglet':'Fictive','ligne':2}]
        self.parcours={'42':{'reels':{'ancien':{'reels_verifies_v2':{'fictif':'2026-10-15T10:00:00Z'}}}}}
        def write(d):self.data=deepcopy(d)
        def write_p(d):self.parcours=deepcopy(d)
        self.patches=[patch.object(process_adapters,'store',return_value=self.store),patch.object(o,'actif',return_value=True),
            patch.object(o,'_lire_etat',side_effect=lambda:deepcopy(self.data)),patch.object(o,'_ecrire_etat',side_effect=write),
            patch.object(o,'lire_comptes',AsyncMock(side_effect=lambda:deepcopy(self.rows))),patch.object(o,'cellule',return_value='Fictive!A2'),
            patch.object(o,'_proprietaires',side_effect=lambda:{'ancien':{'42'}}),patch.object(series,'renommer'),
            patch.object(parcours,'_lire',side_effect=lambda:deepcopy(self.parcours)),patch.object(parcours,'_ecrire',side_effect=write_p)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    async def test_timeout_apres_sheet_reprend_sans_second_compte(self):
        calls=0
        async def sheet(*args):
            nonlocal calls
            calls+=1;self.rows[0]['handle']='nouveau'
            if calls==1:raise TimeoutError('réponse perdue')
        with patch.object(o.google_api,'sheets_ecrire',side_effect=sheet):
            with self.assertRaises(TimeoutError):await o.renommer_compte('42','ancien','nouveau')
            self.assertEqual('',await o.renommer_compte('42','ancien','nouveau'))
        self.assertEqual(['nouveau'],self.data['clippers']['42']['comptes'])
        self.assertEqual(1,sum(self.store.counts('42').values()))
        self.assertIn('nouveau',self.parcours['42']['reels'])

    async def test_fiche_ancienne_ne_renomme_pas_compte_autrui(self):
        with patch.object(o,'_proprietaires',return_value={'ancien':{'43'}}),patch.object(o.google_api,'sheets_ecrire',AsyncMock()) as write:
            raison=await o.renommer_compte('42','ancien','nouveau')
        self.assertTrue(raison);write.assert_not_awaited()

    async def test_reprise_refuse_une_autre_ligne_portant_le_nouveau_pseudo(self):
        async def sheet(*args):
            self.rows[0]['handle']='nouveau'
            raise TimeoutError('réponse perdue')
        with patch.object(o.google_api,'sheets_ecrire',side_effect=sheet):
            with self.assertRaises(TimeoutError):await o.renommer_compte('42','ancien','nouveau')
        self.rows[0]['ligne']=20
        with patch.object(o.google_api,'sheets_ecrire',AsyncMock()) as write:
            self.assertTrue(await o.renommer_compte('42','ancien','nouveau'))
            write.assert_not_awaited()
        self.assertEqual(['ancien'],self.data['clippers']['42']['comptes'])

    async def test_reprise_apres_ecriture_locale_interrompue_et_rejeu(self):
        async def sheet(*args):self.rows[0]['handle']='nouveau'
        with patch.object(o.google_api,'sheets_ecrire',side_effect=sheet) as write:
            with patch.object(o,'_ecrire_etat',side_effect=OSError('disque fictif')):
                with self.assertRaises(OSError):await o.renommer_compte('42','ancien','nouveau')
            self.assertEqual('',await o.renommer_compte('42','ancien','nouveau'))
            self.assertEqual('',await o.renommer_compte('42','ancien','nouveau'))
            self.assertEqual(1,write.call_count)
        self.assertEqual(1,len(self.data['clippers']['42']['renommes']))
        self.assertEqual(1,sum(self.store.counts('42').values()))
        self.assertEqual({'fictif':'2026-10-15T10:00:00Z'},self.parcours['42']['reels']['nouveau']['reels_verifies_v2'])
