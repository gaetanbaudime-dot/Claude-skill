"""Régressions reproduites après déploiement, données fictives exclusivement."""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_store import Store, Bloque
from process_liens import preparer
import process_adapters
from test_process_onboarding import charger


class AuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'process.sqlite3')
        self.patch=patch.object(process_adapters,'store',return_value=self.store)
        self.patch.start();self.addCleanup(self.patch.stop)

    async def test_uid_prefixe_ne_recupere_pas_salon_autrui(self):
        autre=SimpleNamespace(id=99,topic='clipper-uid:420 · Autre')
        propre=SimpleNamespace(id=100,topic='clipper-uid:42 · Fictif')
        creation=AsyncMock(return_value=(propre,True,''))
        fn=charger('assurer_salon_perso',{'_assurer_salon_perso':creation})
        resultat=await fn(SimpleNamespace(fetch_channels=AsyncMock(return_value=[autre])),SimpleNamespace(id=42),None,'Fictive','test')
        self.assertEqual(100,resultat[0].id)

    async def test_salon_persistant_renomme_ne_se_recree_pas(self):
        self.store.put('salon:42',{'salon_id':'99'})
        salon=SimpleNamespace(id=99,topic='Sujet modifié manuellement')
        creation=AsyncMock(side_effect=AssertionError('second salon interdit'))
        fn=charger('assurer_salon_perso',{'_assurer_salon_perso':creation})
        resultat=await fn(SimpleNamespace(fetch_channels=AsyncMock(return_value=[salon])),SimpleNamespace(id=42),None,'Fictive','test')
        self.assertEqual(99,resultat[0].id);creation.assert_not_awaited()

    async def test_salon_persistant_absent_bloque_recreation(self):
        self.store.put('salon:42',{'salon_id':'99'})
        creation=AsyncMock(side_effect=AssertionError('second salon interdit'))
        fn=charger('assurer_salon_perso',{'_assurer_salon_perso':creation})
        resultat=await fn(SimpleNamespace(fetch_channels=AsyncMock(return_value=[])),SimpleNamespace(id=42),None,'Fictive','test')
        self.assertIsNone(resultat[0]);creation.assert_not_awaited()

    async def test_depart_survenu_avant_verrou_interdit_clone(self):
        self.store.put('sortie:42',{'phase':'termine'})
        api=SimpleNamespace(capacite=AsyncMock(side_effect=AssertionError('aucun appel externe après départ')))
        with self.assertRaises(Bloque): await preparer(self.store,'42','Fictive',api)
        api.capacite.assert_not_awaited()

    def test_fiche_sortie_conservee_ne_donne_plus_dadresses(self):
        data={'clippers':{'42':{'sorti':True,'comptes':['fictif'], 'acces':[{'handle':'fictif','mail':'fictif@example.invalid'}]}}}
        ns={'lire_json':lambda *a:data,'FICHIER_ONBOARDING':'fictif',
            'onboarding':SimpleNamespace(_cle_handle=lambda h:str(h).lower())}
        fn=charger('_adresses_codes_fiche',ns)
        self.assertEqual(set(),fn('42'))

    def test_cache_sortant_ne_ressuscite_pas_ses_codes(self):
        data={'clippers':{'42':{'sorti':True}}}
        ns={'lire_json':lambda *a:data,'FICHIER_ONBOARDING':'fictif',
            'membre_par_id':lambda uid:SimpleNamespace(id=42), '_adresses_codes_fiche':lambda uid:set(),
            '_OTP_UID_CACHE':{'42':{'mails':{'fictif@example.invalid'},'revision':1,'jusque':999}},
            'time':SimpleNamespace(monotonic=lambda:0),'_revision_adresses_codes':lambda:1}
        fn=charger('adresses_codes_de',ns)
        self.assertEqual(set(),fn('42'))

    async def test_refresh_sortant_ne_lit_pas_le_classeur(self):
        data={'clippers':{'42':{'sorti':True}}}
        read=AsyncMock(side_effect=AssertionError('lecture inutile'))
        ns={'lire_json':lambda *a:data,'FICHIER_ONBOARDING':'fictif','_OTP_UID_CACHE':{},
            'onboarding':SimpleNamespace(lire_comptes=read)}
        fn=charger('_actualiser_adresses_codes',ns)
        self.assertEqual(set(),await fn('42'));read.assert_not_awaited()

    def test_persistance_interprocessus_et_quatrieme_creation(self):
        import subprocess
        root=Path(__file__).resolve().parents[1]
        self.store.reconcile('42',[], 'fictif')
        script="""from process_store import Store, Bloque
import sys
s=Store(sys.argv[1])
try:
 s.reserve('42',[sys.argv[2]])
 s.created('42',sys.argv[2],'preuve-fictive')
 print('ok')
except Bloque:
 print('bloque')
"""
        env=__import__('os').environ.copy();env['PYTHONPATH']=str(root)
        workers=[subprocess.Popen([sys.executable,'-c',script,str(self.store.path),h],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for h in ('a','b','c','d')]
        resultats=[p.communicate(timeout=20) for p in workers]
        self.assertTrue(all(p.returncode==0 for p in workers),resultats)
        self.assertEqual(3,sum(out.strip()=='ok' for out,err in resultats))
        self.assertEqual({'created':3},Store(self.store.path).counts('42'))
        with self.assertRaises(Bloque):Store(self.store.path).reserve('42',['cinquieme'])

    def test_diagnostic_codes_sans_secret_ni_fausse_sante(self):
        from test_codes_reliable import load_codes
        c=load_codes();c.actif=lambda:True;c.time=SimpleNamespace(monotonic=lambda:1000)
        c._SANTE={'ok_t':None,'echecs':0,'erreur':'secret-fictif'}
        self.assertEqual('inconnu',c.sante_publique()['etat'])
        c._SANTE['ok_t']=995
        self.assertEqual('ok',c.sante_publique()['etat'])
        c._SANTE['echecs']=1
        self.assertEqual('degrade',c.sante_publique()['etat'])
        self.assertNotIn('secret-fictif',str(c.sante_publique()))
        c._SANTE.update(ok_t=1,echecs=0)
        self.assertEqual('degrade',c.sante_publique()['etat'])
