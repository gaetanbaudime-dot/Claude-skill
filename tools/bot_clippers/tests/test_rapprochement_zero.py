import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_store import Store, Bloque
import rapprochement_zero as rz


class RapprochementZero(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for nom in rz.FICHIERS:
            (self.root/nom).write_text('[]' if nom == 'sortis.json' else '{}')
        self.store = Store(self.root/'process_clippeur.sqlite3')
        self.preuve = dict(uid='123', total=0, source='discord-message:456', par='789', date='2026-10-17T06:41:00+00:00')

    def run_zero(self):
        return rz.rapprocher(self.root, '123', self.preuve, {'123'})

    def test_snapshot_references_idempotence_reprise(self):
        self.store.reconcile('123', [], 'ancienne-reference')
        self.assertEqual(self.run_zero(), 'rapproche_reprise_requise')
        journal = self.store.get('rapprochement-zero:123')
        self.assertEqual(json.loads(journal['historique_apres'])['references_anterieures'], ['ancienne-reference'])
        with sqlite3.connect(self.root/journal['sauvegarde']/'process_clippeur.sqlite3') as db:
            self.assertEqual(db.execute('SELECT evidence FROM histories').fetchone(), ('ancienne-reference',))
        self.assertEqual(self.run_zero(), 'deja_rapproche')
        with self.assertRaises(Bloque): self.store.reserve('123', ['fictif'])
        with self.assertRaises(Bloque): self.store.reprise_zero('123')
        self.store.reprise_zero('123', dict(source='discord-message:457', par='789', date=self.preuve['date'], creatrice='Test'))
        self.store.reserve('123', ['fictif'])
        self.assertEqual(self.store.counts('123'), {'reserved': 1})

    def test_contradictions(self):
        for statut in ('created', 'reserved', 'unknown', 'cancelled'):
            with self.subTest(statut=statut):
                with self.store.transaction() as db:
                    db.execute('DELETE FROM accounts')
                    db.execute('INSERT INTO accounts VALUES(?,?,?,?)', ('a', '123', statut, 'ref'))
                with self.assertRaises(Bloque): self.run_zero()
        self.assertEqual(self.store.get('rapprochement-zero:123'), {})

    def test_livraison_blocks(self):
        (self.root/'onboarding.json').write_text(json.dumps({'clippers': {'123': {'comptes': ['fictif']}}}))
        with self.assertRaises(Bloque): self.run_zero()

    def test_files_heritees_isolees_bloquent_zero(self):
        for champ in ('a_dire', 'remise_securisee'):
            with self.subTest(champ=champ):
                (self.root/'onboarding.json').write_text(json.dumps({'clippers': {'123': {champ: ['ancien_fictif']}}}))
                with self.assertRaises(Bloque): self.run_zero()
                with self.store.transaction() as db:
                    self.assertIsNone(db.execute('SELECT * FROM histories').fetchone())
                    self.assertIsNone(db.execute('SELECT * FROM jobs').fetchone())

    def test_etape_avancee_isolee_bloque_zero(self):
        for etape in (2, 3, 10, '2', None):
            with self.subTest(etape=etape):
                (self.root/'parcours.json').write_text(json.dumps({'123': {'etape': etape}}))
                with self.assertRaises(Bloque): self.run_zero()
                with self.store.transaction() as db:
                    self.assertIsNone(db.execute('SELECT * FROM histories').fetchone())
                    self.assertIsNone(db.execute('SELECT * FROM jobs').fetchone())

    def test_backup_failure_no_write(self):
        with patch.object(rz, 'sauvegarder', side_effect=OSError('disque')):
            with self.assertRaises(OSError): self.run_zero()
        with self.store.transaction() as db:
            self.assertIsNone(db.execute('SELECT * FROM histories').fetchone())
            self.assertIsNone(db.execute('SELECT * FROM jobs').fetchone())

    def test_concurrent_allocation_blocked(self):
        started = threading.Event()
        outcomes = []
        backup = rz.sauvegarder
        def allocation():
            started.set()
            try: self.store.reserve('123', ['fictif'])
            except Bloque: outcomes.append('bloque')
        def snapshot(*args):
            self.thread = threading.Thread(target=allocation)
            self.thread.start()
            self.assertTrue(started.wait(2))
            return backup(*args)
        with patch.object(rz, 'sauvegarder', side_effect=snapshot): self.run_zero()
        self.thread.join(5)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(outcomes, ['bloque'])
        self.assertEqual(self.store.counts('123'), {})

    def test_relecture_sources(self):
        backup = rz.sauvegarder
        def snapshot(*args):
            result = backup(*args)
            (self.root/'parcours.json').write_text('{"123":{"comptes":["fictif"]}}')
            return result
        with patch.object(rz, 'sauvegarder', side_effect=snapshot):
            with self.assertRaises(Bloque): self.run_zero()
        self.assertEqual(self.store.get('rapprochement-zero:123'), {})

    def test_scope_owner_and_admin(self):
        for owner, admins in ((777, {'789'}), (789, set())):
            message = SimpleNamespace(guild=SimpleNamespace(owner_id=owner), author=SimpleNamespace(id=789, send=AsyncMock()))
            with patch.object(rz, 'rapprocher') as action:
                asyncio.run(rz.commande(message, '!rapprocher-zero 123 confirme-zero', self.root, admins, {'123'}))
                action.assert_not_called()
        with self.assertRaises(Bloque): rz.rapprocher(self.root, '123', self.preuve, set())

    def test_bad_provenance(self):
        for field, value in [('total', False), ('date', '2026-10-17'), ('source', 'sans-source')]:
            with self.subTest(field=field):
                proof = dict(self.preuve, **{field: value})
                with self.assertRaises(Bloque): rz.rapprocher(self.root, '123', proof, {'123'})
