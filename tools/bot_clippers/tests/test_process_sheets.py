"""Classeur et GAML fictifs, aucune requête réseau."""
import asyncio
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from process_store import Store,Bloque
import process_sheets as p

class API:
 def __init__(self):
  self.rows=[dict(onglet='Fictive',ligne=2,handle='compte.fictif',gerant='Homonyme',uid='fictif',lien_gaml='',lien_mym='',lien_infloww='')]
  self.writes=[];self.calls=0;self.mutate=None;self.partial=False;self.missing=False
 async def verifier(self,job):return True
 async def lignes(self):
  self.calls+=1
  if self.mutate:self.mutate(self)
  return deepcopy(self.rows)
 def appartient(self,r,uid,creatrice):return r.get('uid')==uid and r['onglet']==creatrice
 def colonne(self,k,onglet):return not self.missing
 async def ecrire(self,r,changes):
  self.writes.append((r['ligne'],deepcopy(changes)))
  for k,v in changes.items():
   self.rows[0][k]=v
   if self.partial:
    self.partial=False
    raise TimeoutError('fictif')

class SheetsTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'etat.sqlite3');self.api=API()
  self.job=dict(uid='fictif',creatrice='Fictive',phase='pret',lid='clone-fictif',lien='https://example.invalid/gaml',mym='https://example.invalid/mym',of='https://example.invalid/of')
  self.s.claim_job('liens:fictif:fictive',self.job)
 def tearDown(self):self.tmp.cleanup()
 async def sync(self):return await p.synchroniser(self.s,'fictif','Fictive',self.api)
 async def test_trois_destinations_et_reprise_sans_nouvelle_ecriture(self):
  self.assertEqual(3,(await self.sync())['ecrits'])
  self.assertEqual(0,(await self.sync())['ecrits']);self.assertEqual(1,len(self.api.writes))
 async def test_ligne_deplacee_retrouvee_par_identite(self):
  self.api.mutate=lambda a:a.rows[0].update(ligne=19) if a.calls==2 else None
  await self.sync();self.assertEqual(19,self.api.writes[0][0])
 async def test_homonyme_autre_uid_ne_recoit_aucun_lien(self):
  self.api.rows[0]['uid']='autre'
  with self.assertRaises(Bloque):await self.sync()
  self.assertFalse(self.api.writes)
 async def test_attribution_changee_apres_lecture(self):
  self.api.mutate=lambda a:a.rows[0].update(uid='autre') if a.calls==2 else None
  r=await self.sync();self.assertEqual('attribution_modifiee',r['conflits'][0]['raison']);self.assertFalse(self.api.writes)
 async def test_valeur_divergente_necrase_rien(self):
  self.api.rows[0]['lien_mym']='https://example.invalid/ancien'
  self.assertEqual('destination_divergente',(await self.sync())['conflits'][0]['raison']);self.assertFalse(self.api.writes)
 async def test_colonne_absente_ou_fusionnee_bloque(self):
  self.api.missing=True
  self.assertEqual('colonne_absente',(await self.sync())['conflits'][0]['raison'])
  self.api.missing=False;self.api.rows[0]['fusions']={'lien_mym':(2,4)}
  self.assertEqual('cellule_fusionnee',(await self.sync())['conflits'][0]['raison']);self.assertFalse(self.api.writes)
 async def test_reprise_apres_ecriture_partielle_sans_clone(self):
  self.api.partial=True
  with self.assertRaises(TimeoutError):await self.sync()
  self.assertEqual(2,(await self.sync())['ecrits']);self.assertEqual(2,len(self.api.writes[-1][1]))
 async def test_depart_entre_lectures_bloque(self):
  self.api.mutate=lambda a:self.s.put('sortie:fictif',{'phase':'prepare'}) if a.calls==2 else None
  with self.assertRaises(Bloque):await self.sync()
  self.assertFalse(self.api.writes)
 async def test_double_identite_refusee(self):
  self.api.rows.append(deepcopy(self.api.rows[0]))
  r=await self.sync();self.assertTrue(r['conflits']);self.assertFalse(self.api.writes)
 async def test_verrou_interdit_deux_synchronisations_simultanees(self):
  with self.s.lock('allocations-liens'):
   with self.assertRaises(Bloque):await self.sync()
  self.assertFalse(self.api.writes)

class AdapterTests(unittest.IsolatedAsyncioTestCase):
 async def test_verification_lit_uniquement_clone_sans_ecriture_gaml(self):
  from unittest.mock import patch,AsyncMock
  import process_adapters as a
  import paie_clics as p
  job=dict(lid='fictif',lien='https://example.invalid/gaml',mym='https://example.invalid/mym',of='https://example.invalid/of')
  detail=dict(url=job['lien'],enabled=True,contents=[{'value':job['mym']},{'value':job['of']}])
  with patch.object(p,'lien_detail',AsyncMock(return_value=detail)) as read,patch.object(p,'liens_gaml',AsyncMock()) as scan,patch.object(p,'_requete',AsyncMock()) as write:
   self.assertTrue(await a.LiensSheetsAPI('fictif',None).verifier(job))
   read.assert_awaited_once_with('fictif');scan.assert_not_awaited();write.assert_not_awaited()
 async def test_proprietaire_stable_requis_meme_si_prenom_identique(self):
  from unittest.mock import patch,Mock
  import onboarding as o
  import process_adapters as a
  registre=Mock();registre.owner_for_handle.return_value='autre-uid'
  r=dict(handle='compte.fictif',gerant='Homonyme',creatrice='Fictive',onglet='Fictive')
  with patch.object(o,'_lire_etat',return_value={'clippers':{'fictif':{'comptes':['compte.fictif']}}}),patch.object(o,'_proprietaires',return_value={'compte.fictif':{'fictif'}}):
   self.assertFalse(a.LiensSheetsAPI('fictif',registre).appartient(r,'fictif','Fictive'))
   registre.owner_for_handle.return_value='fictif'
   self.assertTrue(a.LiensSheetsAPI('fictif',registre).appartient(r,'fictif','Fictive'))
