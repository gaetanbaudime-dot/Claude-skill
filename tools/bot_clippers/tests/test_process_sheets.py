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
  registre.get.side_effect=lambda k: {'uid':'fictif','gerant':'Homonyme','creatrice':'Fictive','preuve':'fictive'} if k.startswith('attribution-sheet:') else None
  r=dict(handle='compte.fictif',gerant='Homonyme',creatrice='Fictive',onglet='Fictive')
  with patch.object(o,'_lire_etat',return_value={'clippers':{'fictif':{'comptes':['compte.fictif']}}}),patch.object(o,'_proprietaires',return_value={'compte.fictif':{'fictif'}}):
   self.assertFalse(a.LiensSheetsAPI('fictif',registre).appartient(r,'fictif','Fictive'))
   registre.owner_for_handle.return_value='fictif'
   self.assertTrue(a.LiensSheetsAPI('fictif',registre).appartient(r,'fictif','Fictive'))

class ReviewRegressions(unittest.IsolatedAsyncioTestCase):
 async def test_attribution_courante_et_creatrice_exacte(self):
  from unittest.mock import patch,Mock
  import onboarding as o,process_adapters as a
  registry=Mock();registry.owner_for_handle.return_value='alice'
  binding={'uid':'alice','gerant':'Alice','creatrice':'Sarah','preuve':'validation-fictive'}
  registry.get.side_effect=lambda k: binding if k.startswith('attribution-sheet:') else None
  row=dict(handle='fictif',gerant='Bob',creatrice='Sarah',onglet='Sarah')
  with patch.object(o,'_lire_etat',return_value={'clippers':{'alice':{'comptes':['fictif']}}}),patch.object(o,'_proprietaires',return_value={'fictif':{'alice'}}):
   api=a.LiensSheetsAPI('alice',registry)
   self.assertFalse(api.appartient(row,'alice','Sarah'))
   row['gerant']='Alice';self.assertTrue(api.appartient(row,'alice','Sarah'))
   row['creatrice']='Sarah2';self.assertFalse(api.appartient(row,'alice','Sarah'))
   registry.get.side_effect=lambda k: binding if k.startswith('attribution-sheet:') else {'canonique':'Sarah','preuve':'alias-valide'}
   self.assertTrue(api.appartient(row,'alice','Sarah'))
   binding.pop('preuve');self.assertFalse(api.appartient(row,'alice','Sarah'))
 async def test_fusions_strictes_horizontales_verticales_et_panne(self):
  from unittest.mock import patch,AsyncMock
  import onboarding as o,process_adapters as a,google_api as g
  row=dict(onglet='Fictive',ligne=2,handle='fictif')
  with patch.object(o,'lire_comptes',AsyncMock(side_effect=lambda:[deepcopy(row)])),patch.object(o,'_colonnes_lues_par_onglet',{'Fictive':{'lien_mym':3}}):
   api=a.LiensSheetsAPI('alice',None)
   with patch.object(g,'sheets_fusions',AsyncMock(side_effect=TimeoutError)):
    with self.assertRaises(TimeoutError):await api.lignes()
   for fusion in [(1,2,2,5),(0,4,3,4)]:
    with patch.object(g,'sheets_fusions',AsyncMock(return_value={'Fictive':[fusion]})):
     self.assertIn('lien_mym',(await api.lignes())[0]['fusions'])
 async def test_historique_sans_job_necrit_ni_nefface(self):
  from unittest.mock import patch,AsyncMock
  import onboarding as o,process_adapters as a,google_api as g
  row=dict(handle='fictif',gerant='Alice',lien_gaml='https://example.invalid/ancien')
  with patch.object(o,'actif',return_value=True),patch.object(o.paie_clics,'actif',return_value=True),patch.object(a,'synchroniser_liens_sheets',AsyncMock(return_value={'ecrits':0,'proteges':set(),'conflits':[]})),patch.object(g,'sheets_ecrire',AsyncMock()) as write,patch.object(o.paie_clics,'liens_gaml',AsyncMock()) as scan:
   result=await o.liens_classeur([row]);self.assertEqual('historique_sans_job_verifie',result['conflits'][0]['raison'])
   write.assert_not_awaited();scan.assert_not_awaited();self.assertEqual('https://example.invalid/ancien',row['lien_gaml'])
 async def test_dashboard_gid_protege_meme_si_renomme(self):
  from unittest.mock import patch,AsyncMock
  import dashboard as d
  for sid in (1900160410,1900160402):
   with patch.object(d.onboarding,'CLASSEUR_LOGINS_ID',d.CLASSEUR_DASHBOARD_AUTORISE),patch.object(d.google_api,'sheets_proprietes',AsyncMock(return_value={d.ONGLET:{'id':sid}})),patch.object(d,'_batch_unique',AsyncMock()) as write:
    with self.assertRaises(RuntimeError):await d._ecrire_onglet({'simple':True})
    write.assert_not_awaited()

 async def test_destination_exacte_et_absence_de_creation(self):
  from unittest.mock import patch,AsyncMock
  import dashboard as d
  for classeur,gid,ok in [(d.CLASSEUR_DASHBOARD_AUTORISE,d.GID_DASHBOARD_AUTORISE,True),
                          ('classeur-fictif',d.GID_DASHBOARD_AUTORISE,False),
                          (d.CLASSEUR_DASHBOARD_AUTORISE,123,False),
                          (d.CLASSEUR_DASHBOARD_AUTORISE,None,False)]:
   with patch.object(d.onboarding,'CLASSEUR_LOGINS_ID',classeur),patch.object(d.google_api,'sheets_proprietes',AsyncMock(return_value={d.ONGLET:{'id':gid}})),patch.object(d.google_api,'sheets_creer_onglet',AsyncMock()) as create,patch.object(d,'requetes_simple',return_value=[]),patch.object(d,'_batch_unique',AsyncMock()) as write:
    if ok:
     self.assertEqual(d.GID_DASHBOARD_AUTORISE,await d._ecrire_onglet({'simple':True}));write.assert_awaited_once()
    else:
     with self.assertRaises(RuntimeError):await d._ecrire_onglet({'simple':True})
     write.assert_not_awaited()
    create.assert_not_awaited()
