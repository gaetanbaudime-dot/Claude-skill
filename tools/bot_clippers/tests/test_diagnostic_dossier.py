"""Diagnostic sans données réelles, sans réseau et sans initialisation implicite."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diagnostic_dossier as d


class Diagnostic(unittest.IsolatedAsyncioTestCase):
    async def test_refus_avant_lecture_et_sans_message(self):
        for author, owner, admins, guild in [(2, 1, {'2'}, True), (1, 1, set(), True), (1, 1, {'1'}, False)]:
            msg = SimpleNamespace(author=SimpleNamespace(id=author, send=AsyncMock()),
                                  guild=SimpleNamespace(owner_id=owner) if guild else None)
            with patch.object(d, 'rapport') as lecture:
                self.assertTrue(await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', '/absent', admins))
                lecture.assert_not_called()
                msg.author.send.assert_not_awaited()

    def test_absence_ne_cree_rien_et_ne_vaut_pas_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            rapport = d.rapport(tmp, '3', 'Sarah', '4')
            self.assertIsNone(rapport['processus']['comptes_observes'])
            self.assertIsNone(rapport['reservation_onboarding_nombre'])
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_projection_sans_secrets_et_sans_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            poison = 'SECRET-FICTIF-NE-PAS-EXPORTER'
            (root / 'onboarding.json').write_text(json.dumps({'clippers': {'3': {
                'creatrice': poison, 'comptes': [poison], 'mail': poison, 'mdp': poison, 'tel': poison, 'token': poison}}}))
            (root / 'parcours.json').write_text(json.dumps({'3': {'messages': {'1': '123', '2': poison}, 'notes': poison}}))
            dbpath = root / 'process_clippeur.sqlite3'
            with sqlite3.connect(dbpath) as db:
                db.executescript('CREATE TABLE histories(uid TEXT,evidence TEXT); CREATE TABLE accounts(id TEXT,uid TEXT,status TEXT,evidence TEXT); CREATE TABLE jobs(key TEXT,data TEXT);')
                db.execute('INSERT INTO accounts VALUES(?,?,?,?)', ('fictif', '3', 'unknown', poison))
                db.execute('INSERT INTO jobs VALUES(?,?)', ('message-compte1:3', json.dumps({'message_id':'456', 'salon':'789', 'token':poison, 'etat':'incertain'})))
            avant = {p.name:p.read_bytes() for p in root.iterdir()}
            rapport = d.rapport(root, '3', 'Sarah', '4')
            self.assertNotIn(poison, json.dumps(rapport))
            self.assertEqual({'unknown':1}, rapport['processus']['comptes_observes'])
            self.assertIsNone(rapport['processus']['total_crees_a_vie'])
            self.assertEqual('456', rapport['processus']['message_compte1_id'])
            self.assertFalse(rapport['onboarding']['choix_conforme'])
            self.assertEqual(avant, {p.name:p.read_bytes() for p in root.iterdir()})

    async def test_proprietaire_recoit_seulement_fichier_prive(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg = SimpleNamespace(author=SimpleNamespace(id=1, send=AsyncMock()), guild=SimpleNamespace(owner_id=1))
            await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', tmp, {'1'})
            msg.author.send.assert_awaited_once()
            self.assertEqual({'file'}, set(msg.author.send.call_args.kwargs))

    def test_corruption_et_symlink_restent_inconnus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'cible').write_text('invalide')
            (root / 'process_clippeur.sqlite3').symlink_to(root / 'cible')
            self.assertIsNone(d.registre(root / 'process_clippeur.sqlite3', '3')['comptes_observes'])
            self.assertIsNone(d.lire(root / 'cible'))

    def test_historique_avec_compte_inconnu_ne_prouve_pas_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'process_clippeur.sqlite3'
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE histories(uid TEXT,evidence TEXT); CREATE TABLE accounts(uid TEXT,status TEXT); CREATE TABLE jobs(key TEXT,data TEXT); INSERT INTO histories VALUES('3','preuve-fictive'); INSERT INTO accounts VALUES('3','unknown');")
            self.assertIsNone(d.registre(path, '3')['total_crees_a_vie'])
