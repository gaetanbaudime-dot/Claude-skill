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
    def __init__(self): self.calls=[]; self.allowed=True
    def permissions_for(self,me): return N(view_channel=True,read_message_history=self.allowed)
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
        guild=N(id=9,me=N(id=99),channels=[c],active_threads=active,get_channel_or_thread=lambda _:None)
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

class CouvertureTests(unittest.IsolatedAsyncioTestCase):
    async def test_sans_droit_historique_jamais_complet_puis_reprise(self):
        c=Channel();c.allowed=False
        async def active():return []
        g=N(id=9,me=N(id=99),channels=[c],active_threads=active,get_channel_or_thread=lambda _:None)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.db'
            r=await a.collecter(g,path)
            self.assertFalse(r['complet']);self.assertEqual('permissions_absentes',r['salons'][0]['statut']);self.assertEqual([],c.calls)
            c.allowed=True
            r=await a.collecter(g,path)
            self.assertTrue(r['complet']);self.assertEqual(205,r['salons'][0]['messages'])
    async def test_decouverte_bornee_curseur_persistant_pas_de_rescan(self):
        from datetime import timedelta
        class Forum:
            id=777;name='forum-fictif'
            def __init__(self):self.calls=[]
            def permissions_for(self,me):return N(view_channel=True,read_message_history=True)
            async def archived_threads(self,limit,before=None):
                self.calls.append((limit,before));self.assert_limit=limit
                n=0
                for i in range(120,0,-1):
                    date=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)
                    if before is None or date<before:
                        yield N(id=i,archive_timestamp=date)
                        n+=1
                        if n>=limit:break
        c=Forum()
        async def active():return []
        g=N(id=9,me=N(id=99),channels=[c],active_threads=active,get_channel_or_thread=lambda _:None)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.db'
            r=await a.collecter(g,path,pages_max=0,decouverte_max=1)
            self.assertFalse(r['complet']);self.assertEqual(50,len(r['salons']));self.assertEqual(1,len(c.calls))
            r=await a.collecter(g,path,pages_max=0,decouverte_max=1)
            self.assertEqual(100,len(r['salons']));self.assertIsNotNone(c.calls[-1][1])
            r=await a.collecter(g,path,pages_max=0,decouverte_max=1)
            self.assertEqual(120,len(r['salons']))
            await a.collecter(g,path,pages_max=0,decouverte_max=1)
            self.assertEqual(3,len(c.calls));self.assertTrue(all(limit==50 for limit,_ in c.calls))
    async def test_borne_duree_et_volume_ne_marquent_pas_complet(self):
        c=Channel()
        async def active():return []
        g=N(id=9,me=N(id=99),channels=[c],active_threads=active,get_channel_or_thread=lambda _:None)
        for limites in [dict(duree_max=0),dict(volume_max=1)]:
            with tempfile.TemporaryDirectory() as root:
                if 'volume_max' in limites:
                    with self.assertRaises(a.VolumeAtteint):await a.collecter(g,Path(root)/'audit.db',**limites)
                else:
                    r=await a.collecter(g,Path(root)/'audit.db',**limites)
                    self.assertFalse(r['complet']);self.assertTrue(r['borne_atteinte'])
                self.assertEqual([],c.calls)

class RepriseSansPrefactoringTests(unittest.IsolatedAsyncioTestCase):
    async def test_fils_complets_hors_cache_ne_sont_jamais_refetches(self):
        from unittest.mock import AsyncMock
        c=Channel()
        async def active():return []
        fetch=AsyncMock(side_effect=AssertionError('Un fil complet ne doit pas être récupéré'))
        g=N(id=9,me=N(id=99),channels=[c],active_threads=active,get_channel_or_thread=lambda _:None,fetch_channel=fetch)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.db'
            await a.collecter(g,path,pages_max=0)
            with sqlite3.connect(path) as db:
                db.execute("DELETE FROM salons WHERE id='123'")
                for i in range(1000,1100):
                    db.execute("INSERT INTO salons VALUES (?,?,'complet',NULL)",(str(i),'1'))
                db.execute("INSERT INTO salons VALUES ('123','999999999999999999','a_reprendre',NULL)")
            r=await a.collecter(g,path,pages_max=3)
            fetch.assert_not_awaited()
            self.assertTrue(r['complet'])
            self.assertEqual(205,next(x['messages'] for x in r['salons'] if x['id']=='123'))

class EquiteReprisesTests(unittest.IsolatedAsyncioTestCase):
    async def test_erreurs_lentes_ne_privant_pas_un_salon_a_reprendre(self):
        from unittest.mock import patch
        c=Channel();c.id=6
        horloge=[0.0];appels=[]
        async def active():return []
        async def fetch(cid):
            appels.append(cid);horloge[0]+=9
            if cid==6:return c
            raise a.discord.Forbidden(N(status=403,reason='fictif'),'interdit fictif')
        g=N(id=9,me=N(id=99),channels=[],active_threads=active,get_channel_or_thread=lambda _:None,fetch_channel=fetch)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'audit.db'
            await a.collecter(g,path,pages_max=0)
            with sqlite3.connect(path) as db:
                for i in range(1,6):db.execute("INSERT INTO salons VALUES (?,?,'illisible','Forbidden')",(str(i),'999999999999999999'))
                db.execute("INSERT INTO salons VALUES ('6','999999999999999999','a_reprendre',NULL)")
            with patch.object(a,'time',N(monotonic=lambda:horloge[0],time=lambda:1000.0)):
                r=await a.collecter(g,path,duree_max=45)
                self.assertEqual(6,appels[0]);self.assertEqual(205,next(s['messages'] for s in r['salons'] if s['id']=='6'))
                avant=list(appels)
                await a.collecter(g,path,duree_max=45)
                nouveaux=appels[len(avant):]
                self.assertFalse(set(nouveaux)&set(avant))
                self.assertTrue(r['reprises'])
    async def test_decouverte_en_erreur_garde_budget_pour_lecture(self):
        from unittest.mock import patch
        horloge=[0.0];appels=[]
        class Forum:
            def __init__(self,i):self.id=i
            def permissions_for(self,me):return N(view_channel=True,read_message_history=True)
            async def archived_threads(self,**kwargs):
                appels.append(self.id);horloge[0]+=9
                raise a.discord.Forbidden(N(status=403,reason='fictif'),'interdit fictif')
                yield
        c=Channel()
        async def active():return []
        g=N(id=9,me=N(id=99),channels=[*(Forum(i) for i in range(5)),c],active_threads=active,get_channel_or_thread=lambda _:None)
        with tempfile.TemporaryDirectory() as root, patch.object(a,'time',N(monotonic=lambda:horloge[0],time=lambda:1000.0)):
            path=Path(root)/'audit.db'
            r=await a.collecter(g,path,duree_max=45)
            self.assertEqual(205,r['salons'][0]['messages']);self.assertLess(len(appels),5)
            avant=set(appels)
            await a.collecter(g,path,duree_max=45)
            self.assertFalse(avant & set(appels[len(avant):]))
