import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export_integral as ei
from conversation_audit import sanitize_message, sanitize_in_channel


class TexteIntegral(unittest.TestCase):
    def test_texte_long_non_tronque_et_masquage(self):
        texte = '\n'.join(['Bonjour tout le monde. ' * 30] * 30)
        self.assertEqual(sanitize_message(texte, integral=True), texte)
        self.assertLessEqual(len(sanitize_message(texte)), 1200)
        self.assertNotIn('123456', sanitize_message('Code de connexion : 123456', integral=True))
        self.assertEqual(sanitize_in_channel(texte, SimpleNamespace(name='codes', parent=None, category=None), integral=True), '[SALON D’ACCÈS MASQUÉ]')

    def test_segments_et_reprise_sans_perte(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbpath=Path(tmp)/'archive.sqlite3'
            with sqlite3.connect(dbpath) as db:
                db.execute('CREATE TABLE messages(id TEXT, salon TEXT, contenu TEXT)')
                for i in range(7):
                    db.execute('INSERT INTO messages VALUES(?,?,?)',(str(i),'salon',json.dumps(dict(date='date',uid='auteur',texte=f'Texte numéro {i}',pieces_jointes=1,embeds_omis=0))))
            blocs=list(ei.segments(dbpath,maximum=300))
            self.assertGreater(len(blocs),1)
            self.assertEqual(b''.join(x[1] for x in blocs[1:]),b''.join(x[1] for x in ei.segments(dbpath,apres=blocs[0][0],maximum=300)))
            for i in range(7): self.assertEqual(b''.join(x[1] for x in blocs).count(f'Texte numéro {i}'.encode()),1)


class CommandeIntegral(unittest.IsolatedAsyncioTestCase):
    async def test_non_proprietaire_aucune_collecte(self):
        msg=SimpleNamespace(guild=SimpleNamespace(id=1,owner_id=2),author=SimpleNamespace(id=3,send=AsyncMock()))
        with patch.object(ei.audit_complet,'collecter',new=AsyncMock()) as collecte:
            await ei.commande(msg,Path('/inexistant'),['nouveau'])
            collecte.assert_not_awaited()
            msg.author.send.assert_not_awaited()

    async def test_archive_distincte_integrale_decouverte_partielle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ancienne=root/'1.sqlite3';ancienne.write_bytes(b'archive precedente')
            msg=SimpleNamespace(guild=SimpleNamespace(id=1,owner_id=2),author=SimpleNamespace(id=2,send=AsyncMock()))
            rapport=dict(avant='1500000000000000000',complet=False,salons=[{'statut':'complet'}],decouverte=[{'statut':'a_reprendre'}])
            with patch.object(ei.audit_complet,'collecter',new=AsyncMock(return_value=rapport)) as collecte, patch.object(ei,'livraison',return_value={'livraison_complete':False}):
                await ei.commande(msg,root,['nouveau'])
                self.assertTrue(collecte.call_args.kwargs['integral'])
                self.assertNotEqual(collecte.call_args.args[1],ancienne)
                self.assertEqual(ancienne.read_bytes(),b'archive precedente')
                self.assertTrue(any('PARTIEL' in str(c) for c in msg.author.send.call_args_list))
                self.assertFalse(any('discussions-00001' in str(c) for c in msg.author.send.call_args_list))

    async def test_echec_envoi_ne_saute_pas_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            etat=dict(fichier='export-test.sqlite3',proprietaire='2',debut='date',apres=0,partie=0,
                      rapport=dict(avant='1500000000000000000',complet=True))
            ei.sauver(root/'export-1.json',etat)
            async def envoi(*args,**kwargs):
                f=kwargs.get('file')
                if f and f.filename.startswith('discussions-'): raise OSError('envoi interrompu')
            msg=SimpleNamespace(guild=SimpleNamespace(id=1,owner_id=2),author=SimpleNamespace(id=2,send=AsyncMock(side_effect=envoi)))
            with patch.object(ei,'segments',return_value=iter([(42,b'texte nettoye')])), patch.object(ei,'livraison',return_value={'livraison_complete':False}):
                with self.assertRaises(OSError): await ei.commande(msg,root,['livrer'])
            self.assertEqual(json.loads((root/'export-1.json').read_text())['apres'],0)


class Budgets(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_full_rollback_conserve_curseur_et_reprise(self):
        from test_audit_complet import Channel
        from datetime import datetime, timezone
        class Grand(Channel):
            async def history(self, limit, before, oldest_first):
                for i in range(5, 0, -1):
                    yield SimpleNamespace(id=i,created_at=datetime.now(timezone.utc),author=SimpleNamespace(id=42,bot=False),content='bonjour ' * 8000,attachments=[],embeds=[])
        c=Grand()
        g=SimpleNamespace(id=9,me=SimpleNamespace(id=99),channels=[c],active_threads=AsyncMock(return_value=[]),get_channel_or_thread=lambda _:None)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'export.sqlite3'
            await ei.audit_complet.collecter(g,path,pages_max=0,integral=True)
            with sqlite3.connect(path) as db:
                avant=db.execute('SELECT curseur FROM salons').fetchone()
            with self.assertRaises(sqlite3.OperationalError):
                await ei.audit_complet.collecter(g,path,integral=True,volume_max=path.stat().st_size+4096)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT curseur FROM salons').fetchone(),avant)
                self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],0)
            r=await ei.audit_complet.collecter(g,path,integral=True,volume_max=1024*1024)
            self.assertTrue(r['complet'])
            self.assertEqual(r['salons'][0]['messages'],5)

    def test_budget_global_compte_autres_fichiers_et_journaux(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'ancienne.sqlite3').write_bytes(b'a'*20)
            (root/'export-un.sqlite3').write_bytes(b'b'*10)
            (root/'export-un.sqlite3-journal').write_bytes(b'j'*30)
            with patch.object(ei,'BUDGET_ARCHIVE',100),patch.object(ei,'BUDGET_GLOBAL',100):
                with self.assertRaises(ValueError): ei.verifier_budget(root,nouveau=True)
            self.assertEqual((root/'ancienne.sqlite3').read_bytes(),b'a'*20)

    async def test_plus_de_trois_segments_et_fin_verifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dbpath=root/'export-test.sqlite3'
            with sqlite3.connect(dbpath) as db:
                db.execute('CREATE TABLE messages(id TEXT,salon TEXT,contenu TEXT)')
                for i in range(7):
                    db.execute('INSERT INTO messages VALUES(?,?,?)',(str(i),'salon',json.dumps(dict(date='date',uid='auteur',texte='bonjour '*20,pieces_jointes=0,embeds_omis=0))))
            etat=dict(fichier=dbpath.name,proprietaire='2',debut='date',lot='lot-stable',apres=0,partie=0,rapport=dict(avant='1500000000000000000',complet=True))
            ei.sauver(root/'export-1.json',etat)
            msg=SimpleNamespace(guild=SimpleNamespace(id=1,owner_id=2),author=SimpleNamespace(id=2,send=AsyncMock()))
            original=ei.segments
            with patch.object(ei,'segments',side_effect=lambda p,a:original(p,a,maximum=300)):
                await ei.commande(msg,root,['livrer'])
                state=json.loads((root/'export-1.json').read_text())
                self.assertEqual(state['partie'],3)
                self.assertFalse(ei.livraison(dbpath,state['apres'],True)['livraison_complete'])
                await ei.commande(msg,root,['livrer'])
                await ei.commande(msg,root,['livrer'])
            state=json.loads((root/'export-1.json').read_text())
            fin=ei.livraison(dbpath,state['apres'],True)
            self.assertTrue(fin['livraison_complete'])
            self.assertEqual(fin['messages_livres'],7)
            self.assertEqual(fin['messages_restants'],0)
            noms=[c.kwargs['file'].filename for c in msg.author.send.call_args_list if 'file' in c.kwargs and c.kwargs['file'].filename.startswith('discussions-')]
            self.assertEqual(len(noms),len(set(noms)))
            self.assertTrue(all('lot-stable' in n for n in noms))

    def test_sauvegarde_synchronise_fichier_et_repertoire(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            observe=[]
            original=os.fsync
            def sync(fd):
                observe.append(stat.S_ISDIR(os.fstat(fd).st_mode))
                original(fd)
            with patch.object(os,'fsync',side_effect=sync): ei.sauver(Path(tmp)/'curseur.json',{'apres':12})
            self.assertEqual(observe,[False,True])
