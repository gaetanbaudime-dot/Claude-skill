import asyncio
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_autonome as a
from audit_transport import TransportSheets,ENTETE_COUVERTURE,ENTETE_SIGNAUX

CONFIG=dict(actif=True,destinataires_verifies='preuve-fictive',lecture_cloud_prouvee='lecture-fictive',serveur='9')
def rapport(n=1,complet=False,avant='1000'):
 return dict(avant=avant,apres='0',complet=complet,salons=[dict(id='1',statut='complet' if complet else 'a_reprendre',messages=n)],
             decouverte=[dict(source='1',statut='complet' if complet else 'a_reprendre')],reprises=[])
class Sink:
 lignes=staticmethod(TransportSheets.lignes)
 def __init__(self):self.couverture=AsyncMock();self.signaux=AsyncMock()
def diagnostic(path,apres,limite):
 return dict(cas=[dict(jour='2026-10-16',categories=['drive'],source='https://discord.com/channels/9/1/123',bot=False)],
             curseur_suivant=123,reste=False)

class AutonomieTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=1800000000;self.sink=Sink()
 def tearDown(self):self.tmp.cleanup()
 async def tour(self,collect,config=None,diag=diagnostic):
  return await a.tour(N(id=9),self.root,CONFIG if config is None else config,self.sink,collecter=collect,diagnostiquer=diag,maintenant=lambda:self.now)
 async def test_inactif_sans_lecture_cloud_ne_collecte_pas(self):
  f=AsyncMock();r=await self.tour(f,{**CONFIG,'lecture_cloud_prouvee':''})
  self.assertEqual('inactif_ou_source_non_lue',r['statut']);f.assert_not_awaited()
 async def test_quatre_tranches_max_et_backoff(self):
  f=AsyncMock(side_effect=[rapport(i) for i in range(4)])
  r=await self.tour(f);self.assertEqual(4,f.await_count);self.assertEqual('collecte_partielle',r['statut'])
  self.assertEqual('backoff',(await self.tour(f))['statut']);self.assertEqual(4,f.await_count)
 async def test_arret_si_absence_de_progres(self):
  f=AsyncMock(return_value=rapport())
  await self.tour(f);self.assertEqual(2,f.await_count)
 async def test_timeout_preserve_checkpoint_et_differe(self):
  f=AsyncMock(side_effect=[rapport(),TimeoutError()])
  self.assertEqual('reprise_differee',(await self.tour(f))['statut'])
  self.assertEqual(1,a.lire(self.root/'9-producteur.json')['cycle']['rapport']['salons'][0]['messages'])
 async def test_nouvelle_fenetre_apres_fin_sans_recreer_snapshot(self):
  f=AsyncMock(return_value=rapport(complet=True))
  self.assertEqual('lot_publie',(await self.tour(f))['statut'])
  self.now+=1000
  g=AsyncMock(side_effect=TimeoutError())
  await self.tour(g)
  self.assertEqual(999,g.call_args.kwargs['apres'])  # inclure la borne précédente, jamais perdre le premier snowflake
  self.assertNotEqual('1000',g.call_args.kwargs['avant_fixe'])
  self.assertIn('delta-',str(g.call_args.args[1]))
 async def test_echec_transport_reprend_exactement_meme_plage(self):
  f=AsyncMock(return_value=rapport(complet=True))
  self.sink.signaux.side_effect=TimeoutError()
  with self.assertRaises(TimeoutError):await self.tour(f)
  premier=self.sink.signaux.call_args
  self.now+=1000;self.sink.signaux.side_effect=None
  await self.tour(f)
  self.assertEqual(premier,self.sink.signaux.call_args)
  self.assertEqual(1,f.await_count)  # snapshot fini : aucun second parcours Discord
 async def test_deux_passages_simultanes_ne_collectent_pas_deux_fois(self):
  f=AsyncMock(return_value=rapport(complet=True))
  await asyncio.gather(self.tour(f),self.tour(f))
  self.assertEqual(1,f.await_count)
 async def test_export_borne_a_quatre_pages(self):
  f=AsyncMock(return_value=rapport(complet=True))
  def diag(path,apres,limite):
   d=diagnostic(path,apres,limite);d.update(curseur_suivant=apres+1,reste=True);return d
  self.assertEqual('export_partiel',(await self.tour(f,diag=diag))['statut'])
  self.assertEqual(4,self.sink.signaux.await_count)

class TransportTests(unittest.IsolatedAsyncioTestCase):
 def test_aucun_texte_libre_uid_ou_piece_jointe_exporte(self):
  d=diagnostic(None,0,1000);d['cas'][0].update(texte='SECRET-FICTIF',uid='999',piece_jointe='SECRET-FICTIF')
  rows=TransportSheets.lignes('1000',d)
  self.assertNotIn('SECRET',str(rows));self.assertNotIn('999',str(rows))
  d['cas'][0]['categories']=['=FORMULE-FICTIVE']
  with self.assertRaises(ValueError):TransportSheets.lignes('1000',d)
 def test_destination_precise_obligatoire(self):
  with self.assertRaises(ValueError):TransportSheets('existant',CONFIG)
 async def test_schema_et_relecture_obligatoires(self):
  rows=[['1000','2026-10-16','drive','https://discord.com/channels/9/1/123','non']]
  api=N(sheets_lire=AsyncMock(side_effect=[[ENTETE_COUVERTURE],[ENTETE_SIGNAUX],rows]),sheets_ecrire_brut=AsyncMock())
  t=TransportSheets('existant',{**CONFIG,'classeur_approuve':'existant'},api)
  await t.signaux(2,rows)
  self.assertEqual(3,api.sheets_lire.await_count);api.sheets_ecrire_brut.assert_awaited_once()
 async def test_schema_absent_aucune_ecriture(self):
  api=N(sheets_lire=AsyncMock(return_value=[]),sheets_ecrire_brut=AsyncMock())
  t=TransportSheets('existant',{**CONFIG,'classeur_approuve':'existant'},api)
  with self.assertRaises(ValueError):await t.signaux(2,[['1000','2026-10-16','drive','https://discord.com/channels/9/1/123','non']])
  api.sheets_ecrire_brut.assert_not_awaited()

class IncrementalTests(unittest.IsolatedAsyncioTestCase):
 async def test_cutoffs_figes_et_nouveaux_messages_sans_trou(self):
  import sqlite3
  from datetime import datetime,timezone
  import audit_complet
  class Channel:
   id=123;name='fictif'
   def permissions_for(self,me):return N(view_channel=True,read_message_history=True)
   async def history(self,limit,before,oldest_first,after=None):
    for ident in range(205,0,-1):
     if ident<before.id and (after is None or ident>after.id):
      if limit<=0:break
      limit-=1
      yield N(id=ident,created_at=datetime(2026,1,1,tzinfo=timezone.utc),author=N(id=42,bot=False),content='Drive fictif',attachments=[],embeds=[])
  async def actifs():return []
  channel=Channel();guild=N(id=9,me=N(id=99),channels=[channel],active_threads=actifs,get_channel_or_thread=lambda _:channel)
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'initial.sqlite3';q=Path(root)/'delta.sqlite3'
   await audit_complet.collecter(guild,p,avant_fixe=150,apres=0)
   await audit_complet.collecter(guild,q,avant_fixe=200,apres=149)
   with sqlite3.connect(p) as db:premiers={int(x[0]) for x in db.execute('SELECT id FROM messages')}
   with sqlite3.connect(q) as db:suivants={int(x[0]) for x in db.execute('SELECT id FROM messages')}
   self.assertEqual(set(range(1,200)),premiers|suivants);self.assertFalse(premiers&suivants)
   with self.assertRaises(ValueError):await audit_complet.collecter(guild,q,avant_fixe=201,apres=149)
