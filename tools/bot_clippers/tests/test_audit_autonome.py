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
  r=await self.tour(f);self.assertEqual(4,f.await_count);self.assertEqual('lot_partiel_publie',r['statut'])
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
  api=N(sheets_lire=AsyncMock(side_effect=[[ENTETE_COUVERTURE],[ENTETE_SIGNAUX],rows]),sheets_ecrire_brut=AsyncMock(),sheets_proprietes=AsyncMock(return_value={'Audit-processus — signaux':{'lignes':1000,'colonnes':5}}))
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

class ReviewTests(unittest.IsolatedAsyncioTestCase):
 async def test_historique_inaccessible_ne_bloque_pas_fenetre_recente(self):
  with tempfile.TemporaryDirectory() as tmp:
   sink=Sink();root=Path(tmp);now=1800000000
   collect=AsyncMock(return_value=rapport(complet=False))
   await a.tour(N(id=9),root,CONFIG,sink,collecter=collect,diagnostiquer=diagnostic,maintenant=lambda:now)
   state=a.lire(root/'9-producteur.json')
   self.assertEqual(1,len(state['reprises']));self.assertEqual('1000',state['dernier_avant'])
   now+=1000
   collect=AsyncMock(side_effect=TimeoutError())
   await a.tour(N(id=9),root,CONFIG,sink,collecter=collect,diagnostiquer=diagnostic,maintenant=lambda:now)
   self.assertEqual(999,collect.call_args.kwargs['apres'])
   self.assertIn('delta-',str(collect.call_args.args[1]))
 async def test_capacite_grille_et_colonnes_bloquent_avant_write(self):
  from audit_transport import CapaciteAtteinte,SIGNAUX
  for lignes,colonnes in [(1000,5),(2000,4)]:
   api=N(sheets_lire=AsyncMock(side_effect=[[ENTETE_COUVERTURE],[ENTETE_SIGNAUX]]),sheets_ecrire_brut=AsyncMock(),
         sheets_proprietes=AsyncMock(return_value={SIGNAUX:{'lignes':lignes,'colonnes':colonnes}}))
   t=TransportSheets('existant',{**CONFIG,'classeur_approuve':'existant'},api)
   with self.assertRaises(CapaciteAtteinte):await t.signaux(2,[['x']*5 for _ in range(1000)])
   api.sheets_ecrire_brut.assert_not_awaited()
 async def test_arret_capacite_persiste_et_couverture_indique_arret(self):
  from audit_transport import CapaciteAtteinte
  with tempfile.TemporaryDirectory() as tmp:
   sink=Sink();sink.signaux.side_effect=CapaciteAtteinte()
   r=await a.tour(N(id=9),tmp,CONFIG,sink,collecter=AsyncMock(return_value=rapport(complet=True)),diagnostiquer=diagnostic,maintenant=lambda:1800000000)
   self.assertEqual('capacite_transport_atteinte',r['statut'])
   state=a.lire(Path(tmp)/'9-producteur.json');self.assertEqual(r['statut'],state['arret'])
   self.assertEqual(r['statut'],sink.couverture.call_args.args[2]['arret'])
 async def test_budget_sqlite_en_transaction_preserve_curseur(self):
  import sqlite3
  import audit_complet
  from datetime import datetime,timezone
  class Channel:
   id=123;name='fictif'
   def permissions_for(self,me):return N(view_channel=True,read_message_history=True)
   async def history(self,**kwargs):
    for i in range(99,0,-1):
     yield N(id=i,created_at=datetime(2026,1,1,tzinfo=timezone.utc),author=N(id=42,bot=False),content=('contenu fictif '*40+'\n')*3,attachments=[],embeds=[])
  c=Channel();guild=N(id=9,me=N(id=1),channels=[c],active_threads=AsyncMock(return_value=[]))
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'9.sqlite3'
   with self.assertRaises(audit_complet.VolumeAtteint):await audit_complet.collecter(guild,p,volume_max=128*1024,avant_fixe=100)
   self.assertLessEqual(p.stat().st_size,128*1024)
   with sqlite3.connect(p) as db:
    self.assertEqual(0,db.execute('SELECT count(*) FROM messages').fetchone()[0])
    self.assertEqual('100',db.execute('SELECT curseur FROM salons').fetchone()[0])
 async def test_255_mib_bloque_collecte_avec_marge(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'historique.sqlite3'
   with p.open('wb') as f:f.truncate(255*1024*1024)
   collect=AsyncMock()
   r=await a.tour(N(id=9),tmp,CONFIG,Sink(),collecter=collect,maintenant=lambda:1800000000)
   self.assertEqual('volume_atteint',r['statut']);collect.assert_not_awaited()
 async def test_reliquats_alternent_sans_reculer_borne_recente(self):
  with tempfile.TemporaryDirectory() as tmp:
   now=1800000000;paths=[]
   async def collect(g,p,**kw):
    paths.append(p.name)
    r=rapport(avant=str(kw['avant_fixe'] or 1000))
    r['salons'][0]['statut']='permissions_absentes'
    return r
   for _ in range(4):
    await a.tour(N(id=9),tmp,CONFIG,Sink(),collecter=collect,diagnostiquer=diagnostic,maintenant=lambda:now)
    now+=1000
   # Deux tranches identiques au premier passage, une lors de la reprise historique.
   self.assertEqual('9.sqlite3',paths[0]);self.assertIn('delta-',paths[2])
   self.assertEqual('9.sqlite3',paths[4]);self.assertIn('delta-',paths[5])
   state=a.lire(Path(tmp)/'9-producteur.json')
   self.assertGreater(int(state['dernier_avant']),1000);self.assertTrue(state['reprises'])

class DurabiliteTests(unittest.IsolatedAsyncioTestCase):
 async def test_reprise_sans_message_ne_consomme_aucune_ligne(self):
  import sqlite3,json
  import audit_diagnostic
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'9.sqlite3'
   with sqlite3.connect(p) as db:
    db.executescript('CREATE TABLE meta(cle TEXT PRIMARY KEY,valeur TEXT); CREATE TABLE messages(id TEXT PRIMARY KEY,salon TEXT,contenu TEXT);')
    db.execute('INSERT INTO meta VALUES (?,?)',('guild','9'))
    db.execute('INSERT INTO messages VALUES (?,?,?)',('900','1',json.dumps(dict(date='2026-10-16',uid='42',texte='drive'))))
   sink=Sink();now=1800000000
   collect=AsyncMock(return_value=rapport())
   await a.tour(N(id=9),root,CONFIG,sink,collecter=collect,maintenant=lambda:now)
   self.assertEqual(1,sink.signaux.await_count)
   state=a.lire(root/'9-producteur.json');state['reprendre_historique']=True;a.sauver(root/'9-producteur.json',state)
   now+=1000
   await a.tour(N(id=9),root,CONFIG,sink,collecter=collect,maintenant=lambda:now)
   self.assertEqual(1,sink.signaux.await_count)
   state=a.lire(root/'9-producteur.json');self.assertEqual(1,state['lignes_publiees']);self.assertEqual(1,state['manifestes'])
   # Snowflake plus ancien, inséré plus tard : le curseur d'insertion le voit.
   with sqlite3.connect(p) as db:
    db.execute('INSERT INTO messages VALUES (?,?,?)',('100','1',json.dumps(dict(date='2026-10-15',uid='42',texte='drive'))))
   state['reprendre_historique']=True;a.sauver(root/'9-producteur.json',state);now+=1000
   await a.tour(N(id=9),root,CONFIG,sink,collecter=collect,maintenant=lambda:now)
   self.assertEqual(2,sink.signaux.await_count)
   rows=sink.signaux.call_args.args[1];self.assertEqual(1,len(rows));self.assertTrue(rows[0][3].endswith('/100'))
 async def test_journal_durable_reprise_apres_arret_processus(self):
  import sqlite3,subprocess
  import audit_complet
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'9.sqlite3';guild=N(id=9,channels=[],active_threads=AsyncMock(return_value=[]))
   await audit_complet.collecter(guild,p,avant_fixe=100)
   with sqlite3.connect(p) as db:
    self.assertEqual('delete',db.execute('PRAGMA journal_mode').fetchone()[0])
    self.assertEqual(2,db.execute('PRAGMA synchronous').fetchone()[0])
    db.execute('CREATE TABLE fictif(id INTEGER PRIMARY KEY, contenu TEXT)')
    db.executemany('INSERT INTO fictif VALUES (?,?)',[(i,'avant'*1000) for i in range(100)])
   script="""import sqlite3,sys,os
p=sys.argv[1]
db=sqlite3.connect(p)
db.execute('PRAGMA journal_mode=DELETE')
db.execute('PRAGMA synchronous=FULL')
db.execute('PRAGMA cache_size=5')
db.execute('BEGIN IMMEDIATE')
db.execute("UPDATE fictif SET contenu='apres'")
os._exit(17)
"""
   result=subprocess.run([sys.executable,'-c',script,str(p)],capture_output=True)
   self.assertEqual(17,result.returncode)
   with sqlite3.connect(p) as db:
    self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])
    self.assertEqual(100,db.execute("SELECT count(*) FROM fictif WHERE contenu=?",('avant'*1000,)).fetchone()[0])
