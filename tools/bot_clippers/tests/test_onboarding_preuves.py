import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timezone
from copy import deepcopy
import tempfile
import unittest
import onboarding_preuves as p
from process_store import Store,Bloque

class Preuves(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,17,tzinfo=timezone.utc)
        self.pipe={'arrivees':{'10':{'via':'site','date':'2026-10-16T02:00:00Z'}},
          'candidatures_web':{'c':{'date':'2026-10-16T00:00:00Z','discord_uids':['10'],
            'quiz':{'reussi':True,'date':'2026-10-16T01:00:00Z'}}}}
    def preuve(self,**kw):
        args=dict(uid='10',pipe=self.pipe,onboarding={},parcours={},sortis=[],oublis={},registre={},maintenant=self.now)
        return p.preuve_nouveau(**{**args,**kw})
    def test_nouveau_preuves_concordantes(self):
        self.assertEqual(self.preuve()['candidate_id'],'c')
    def test_revenant_ambigu_historique_non_lu(self):
        for kw in ({'onboarding':{'clippers':{'10':{'comptes':['ancien']}}}}, {'sortis':[{'uid':'10'}]},
                   {'oublis':{'10':{}}},{'registre':None},{'registre':{'10':{'date':'2025-01-01T00:00:00Z'}}},{'oublis':None},{'parcours':{'10':{'dates':{'1_fait':'ancienne'}}}}):
            self.assertIsNone(self.preuve(**kw))
        self.pipe['arrivees']['10']['retour']=True
        self.assertIsNone(self.preuve())
    def test_homonyme_non_lie_et_conflit(self):
        self.pipe['candidatures_web']['autre']={'prenom':'Même','discord_uids':['20']}
        self.assertIsNotNone(self.preuve())
        self.pipe['candidatures_web']['autre']['discord_uids']=['10','20']
        self.assertIsNone(self.preuve())
    def test_creation_atomique_replay_et_compteur_conserve(self):
        with tempfile.TemporaryDirectory() as d:
            st=Store(Path(d)/'test.sqlite3')
            self.assertTrue(st.initialiser_nouveau('10',self.preuve()))
            st.reserve('10',['a','b','c'])
            self.assertFalse(st.initialiser_nouveau('10',self.preuve()))
            with self.assertRaises(Bloque):st.reserve('10',['d'])
    def test_ancien_uid_non_initialisable(self):
        with tempfile.TemporaryDirectory() as d:
            st=Store(Path(d)/'test.sqlite3')
            st.observe_alias('10','ancien','preuve fictive')
            with self.assertRaises(Bloque):st.initialiser_nouveau('10',self.preuve())
            with self.assertRaises(Bloque):st.initialiser_nouveau('20',None)
    def test_tl_unique_absent_multiple(self):
        self.assertEqual(p.tl_pour('10','Fictive',{}, {'20':{'chef':'Fictive'}}),'20')
        self.assertIsNone(p.tl_pour('10','Fictive',{},{}))
        self.assertIsNone(p.tl_pour('10','Fictive',{}, {'20':{'chef':'Fictive'},'21':{'chef':'Fictive'}}))
