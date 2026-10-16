"""Aucun accès Discord : pagination et secrets exclusivement synthétiques."""
import json
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace as N
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_complet as a
from conversation_audit import sanitize_message

class Channel:
    id=123
    name='discussion-fictive'
    def __init__(self): self.calls=[]
    async def history(self,limit,before,oldest_first):
        self.calls.append(before.id)
        for i in range(205,0,-1):
            if i<before.id:
                if limit<=0: break
                limit-=1
                yield N(id=i,created_at=datetime(2026,1,1,tzinfo=timezone.utc),author=N(id=42,bot=False),
                        content='Identifiants\nEXEMPLE-SECRET-INVENTE',attachments=[],embeds=[N(description='EXEMPLE-EMBED-INVENTE')])
class AuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_reprise_pagination_sans_doublon_et_masquage_avant_sqlite(self):
        c=Channel()
        async def active(): return []
        guild=N(id=9,channels=[c],active_threads=active)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.sqlite3'
            r=await a.collecter(guild,path,pages_max=1)
            self.assertFalse(r['complet']);self.assertEqual(100,r['salons'][0]['messages'])
            r=await a.collecter(guild,path,pages_max=3)
            self.assertTrue(r['complet']);self.assertEqual(205,r['salons'][0]['messages'])
            old=len(c.calls);await a.collecter(guild,path);self.assertEqual(old,len(c.calls))
            raw=path.read_bytes();self.assertNotIn(b'EXEMPLE-SECRET',raw);self.assertNotIn(b'EXEMPLE-EMBED',raw)
            self.assertEqual(0o600,path.stat().st_mode & 0o777)
    def test_blocs_multilignes_et_code_integralement_omis(self):
        for text in ['Mot de passe\nEXEMPLE-VALEUR-INVENTEE','**Identifiants**\nlogin\nEXEMPLE-VALEUR-INVENTEE','```\nEXEMPLE-VALEUR-INVENTEE\n```','Accès Instagram\nEXEMPLE-VALEUR-INVENTEE','https://exemple.invalid/?token=EXEMPLE-VALEUR-INVENTEE\nsuite']:
            s=sanitize_message(text)
            self.assertNotIn('EXEMPLE',s);self.assertIn('MASQU',s)

class RevueMasquageTests(unittest.TestCase):
    def test_codes_contextuels_multilignes_supprimes_en_entier(self):
        for text in ['OTP\n123 456','Code Instagram\n123 456','Code de vérification\nA1B2C3','Ｃｏｄｅ\nA1B2C3','co\u200bde\nA1B2C3','Code-de-vérification\nA1B2C3']:
            with self.subTest(format=text.splitlines()[0]):
                self.assertEqual('[MESSAGE D’ACCÈS MASQUÉ INTÉGRALEMENT]',sanitize_message(text))
    def test_salons_normalises_et_threads_masquent_meme_valeur_seule(self):
        from conversation_audit import sanitize_in_channel
        for nom in ['🔐-code-instagram','CÓDE—INSTAGRAM','code_instagram','🔒 accès','OTP','co\u200bde-instagram']:
            self.assertEqual('[SALON D’ACCÈS MASQUÉ]',sanitize_in_channel('A1B2C3',N(name=nom)))
            self.assertEqual('[SALON D’ACCÈS MASQUÉ]',sanitize_in_channel('A1B2C3',N(name='fil',parent=N(name=nom))))
    def test_chiffres_separes_sans_entete_masques(self):
        for code in ['123 456','12-34-56','1 2 3 4 5 6']:
            self.assertIn('MASQUÉ',sanitize_message(code))
