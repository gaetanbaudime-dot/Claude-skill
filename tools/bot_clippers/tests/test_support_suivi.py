import asyncio
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import support_suivi as s

class SupportTests(unittest.IsolatedAsyncioTestCase):
    async def test_repetitions_concurrentes_et_reprise_conservent_preuves(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'support.db';notifier=AsyncMock(return_value=99)
            await asyncio.gather(*(s.signaler(path,'42','Drive inaccessible',1,2,i,1,notifier) for i in [3,4,3]))
            notifier.assert_awaited_once()
            self.assertEqual(1,len(s.lister(path,'42')))
            self.assertIn('2 message(s) source',s.contexte(path,'42'))
            self.assertIn('/1/2/4',s.rapport(path,'42'))
            self.assertNotIn('résolu.',s.contexte(path,'42').splitlines()[-1])
            self.assertFalse(s.clore(path,'autre',1));self.assertTrue(s.clore(path,'42',1))
            await s.signaler(path,'42','Drive inaccessible',1,2,5,0,notifier)
            self.assertEqual(2,notifier.await_count)
    async def test_absence_canal_reessayable_timeout_incertain_sans_doublon(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'support.db'
            r=await s.signaler(path,'42','Blocage',1,2,3,0,AsyncMock(return_value=None))
            self.assertEqual('a_envoyer',r['statut'])
            n=AsyncMock(side_effect=TimeoutError)
            r=await s.signaler(path,'42','Blocage',1,2,4,0,n)
            self.assertEqual('envoi_incertain',r['statut'])
            await s.signaler(path,'42','Blocage',1,2,5,0,n)
            n.assert_awaited_once()
            self.assertNotIn('transmis',s.contexte(path,'42'))

class RevueSupportTests(unittest.IsolatedAsyncioTestCase):
    async def test_refus_certain_puis_succes_et_reprise_incertaine_explicitement(self):
        from types import SimpleNamespace as N
        import discord
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'support.db'
            n=AsyncMock(side_effect=[discord.Forbidden(N(status=403,reason='fictif'),'refus fictif'),99])
            r=await s.signaler(path,'42','Blocage',1,2,3,0,n)
            self.assertEqual('a_envoyer',r['statut'])
            r=await s.signaler(path,'42','Blocage',1,2,4,0,n)
            self.assertEqual('transmis',r['statut']);self.assertEqual(2,n.await_count)
            r=await s.signaler(path,'43','Blocage',1,2,5,0,AsyncMock(side_effect=TimeoutError))
            suite=AsyncMock(return_value=100)
            self.assertIsNone(await s.reprendre(path,'43',r['id'],suite))
            self.assertIsNone(await s.reprendre(path,'autre',r['id'],suite,non_livre=True))
            repris=await s.reprendre(path,'43',r['id'],suite,non_livre=True)
            self.assertEqual('transmis',repris['statut'])
            self.assertIsNone(await s.reprendre(path,'43',r['id'],suite,non_livre=True))
            suite.assert_awaited_once()
    async def test_piece_de_suivi_sans_motif_conservee_sans_nouvelle_notification(self):
        import json
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'support.db';n=AsyncMock(return_value=99)
            await s.signaler(path,'42','Suspension',1,2,3,0,n)
            self.assertEqual([],s.ajouter_suivi(path,'autre',1,2,4,1))
            self.assertEqual([],s.ajouter_suivi(path,'42',1,99,4,1))
            self.assertEqual([1],s.ajouter_suivi(path,'42',1,2,4,1))
            s.ajouter_suivi(path,'42',1,2,4,1)
            preuves=json.loads(s.lister(path,'42')[0]['preuves'])
            self.assertEqual(2,len(preuves));self.assertEqual(1,preuves[-1]['pieces']);n.assert_awaited_once()
            self.assertIn('2 message(s) source',s.contexte(path,'42'))
