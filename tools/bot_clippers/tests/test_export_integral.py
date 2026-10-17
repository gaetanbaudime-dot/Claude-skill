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
            with patch.object(ei.audit_complet,'collecter',new=AsyncMock(return_value=rapport)) as collecte:
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
            with patch.object(ei,'segments',return_value=iter([(42,b'texte nettoye')])):
                with self.assertRaises(OSError): await ei.commande(msg,root,['livrer'])
            self.assertEqual(json.loads((root/'export-1.json').read_text())['apres'],0)
