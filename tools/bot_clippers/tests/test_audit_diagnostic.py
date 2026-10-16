import sys
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_diagnostic as d

class DiagnosticTests(unittest.TestCase):
    def test_sortie_fermee_sans_texte_libre_avec_curseur(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.db'
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE meta(cle,valeur);INSERT INTO meta VALUES ('guild','1');CREATE TABLE messages(id,salon,contenu);")
                for i in range(1,4):
                    db.execute('INSERT INTO messages VALUES (?,?,?)',(str(i),'2',json.dumps(dict(uid='42',date='2026-10-16T00:00:00+00:00',texte='Drive bloqué EXEMPLE-SECRET-FICTIF',bot=False))))
            r=d.diagnostic(path,limite=2)
            self.assertTrue(r['reste']);self.assertEqual(2,r['curseur_suivant']);self.assertEqual(2,r['compteurs']['drive'])
            self.assertNotIn('EXEMPLE',json.dumps(r));self.assertNotIn('bloqué',json.dumps(r))
            suite=d.diagnostic(path,apres=2,limite=2)
            self.assertFalse(suite['reste']);self.assertEqual(1,len(suite['cas']))
            self.assertEqual('https://discord.com/channels/1/2/3',suite['cas'][0]['source'])
