"""Modèles et destinations fictifs ; aucun appel externe."""
import asyncio
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paie_clics as p
from process_adapters import LiensAPI
from process_store import Bloque

M = 'https://mym.fans/fictive?track=new'
O = 'https://onlyfans.com/fictive?ref=new'
def carte(ident, url, name='Plateforme exclusive'):
    return dict(id=ident, value=url, name=name)
class CartesTests(unittest.TestCase):
    def test_doublons_bloquent_avant_modification(self):
        for fonction, url, cartes in [
            (p.poser_mym, M, [carte('m1', M), carte('m2', M+'old'), carte('o', O)]),
            (p.poser_tracking, O, [carte('m', M), carte('o1', O), carte('o2', O+'old')])]:
            with self.subTest(fonction=fonction.__name__), patch.object(p, 'lien_detail', AsyncMock(return_value={'contents':cartes})), patch.object(p, '_requete', AsyncMock()) as req:
                resultat = asyncio.run(fonction('fake', url))
                self.assertFalse(resultat == 'déjà' or resultat.startswith('ok'))
                req.assert_not_called()
    def test_modele_ambigu_ne_se_clone_pas(self):
        for cartes in ([carte('m', M), carte('o', O), carte('old', O+'old')],
                       [carte('x', 'https://example.invalid/social', 'Instagram')]):
            with self.subTest(cartes=cartes), patch.object(p, 'lien_detail', AsyncMock(return_value={'contents':cartes})), patch.object(p, '_requete', AsyncMock()) as req:
                with self.assertRaises(Bloque):
                    asyncio.run(LiensAPI('42', []).preparer_clone('fake'))
                req.assert_not_called()
    def test_verification_refuse_toute_carte_supplementaire(self):
        job=dict(lid='fake', lien='https://example.invalid/new', mym=M, of=O)
        for extra in [carte('old', O+'old'), carte('dup', M), carte('blank', '')]:
            detail={'url':job['lien'], 'enabled':True, 'contents':[carte('m', M), carte('o', O), extra]}
            with self.subTest(extra=extra), patch.object(p, 'lien_detail', AsyncMock(return_value=detail)), patch.object(p, '_lire', return_value={'liens':{}}), patch.object(p, 'liens_gaml', AsyncMock()) as inventaire:
                self.assertFalse(asyncio.run(LiensAPI('42', []).verifier(job)))
                inventaire.assert_not_called()
    def test_modele_simple_et_reprise_idempotente(self):
        detail={'contents':[carte('m', M, 'Miam'), carte('o', O)]}
        with patch.object(p, 'lien_detail', AsyncMock(return_value=detail)), patch.object(p, '_requete', AsyncMock(return_value={'id':'clone'})) as req:
            self.assertEqual('déjà', asyncio.run(p.poser_mym('fake', M)))
            self.assertEqual('déjà', asyncio.run(p.poser_tracking('fake', O)))
            req.assert_not_called()
            self.assertEqual({'id':'clone'}, asyncio.run(LiensAPI('42', []).cloner('fake')))
    def test_mym_absent_peut_etre_ajoute_sur_modele_simple(self):
        detail={'contents':[carte('o', O, 'OnlyFriends')]}
        with patch.object(p, 'lien_detail', AsyncMock(return_value=detail)), patch.object(p, '_requete', AsyncMock(return_value={'id':'m'})) as req:
            self.assertEqual('ok', asyncio.run(p.poser_mym('fake', M)))
            self.assertEqual('POST', req.call_args_list[0].args[0])
    def test_clone_modifie_entre_les_etapes_reste_bloque(self):
        detail={'contents':[carte('m', M), carte('o', O), carte('old', O+'old')]}
        with patch.object(p, 'lien_detail', AsyncMock(return_value=detail)), patch.object(p, '_requete', AsyncMock()) as req:
            with self.assertRaises(Bloque):
                asyncio.run(LiensAPI('42', []).configurer('fake', '42'))
            req.assert_not_called()
    def test_annexes_explicitement_sures_conservees(self):
        class Inventaire(list): complete=True
        annexes=[dict(id='texte',cardType='text',name='Bienvenue',value='Découvre mes photos'),
                 dict(id='image',cardType='image',name='Portrait',value='',imageUrl='https://example.invalid/photo.jpg'),
                 dict(id='ig',cardType='simple',name='Instagram',value='https://www.instagram.com/fictive/')]
        detail={'url':'https://example.invalid/new','enabled':True,'contents':[carte('m',M),carte('o',O)]+annexes}
        job=dict(lid='fake',lien=detail['url'],mym=M,of=O)
        with patch.object(p,'lien_detail',AsyncMock(return_value=detail)), patch.object(p,'_requete',AsyncMock()) as req, patch.object(p,'_lire',return_value={'liens':{}}),patch.object(p,'liens_gaml',AsyncMock(return_value=Inventaire([{'id':'fake'}]))):
            self.assertEqual('ok',asyncio.run(p.poser_mym('fake',M)))
            self.assertTrue(asyncio.run(LiensAPI('42',[]).verifier(job)))
            self.assertEqual(annexes,detail['contents'][2:])
    def test_annexe_ambigue_ne_cache_pas_une_plateforme(self):
        for extra in [dict(id='x',cardType='simple',name='Instagram',value='https://example.invalid/redirect'),
                      dict(id='x',cardType='simple',name='Instagram',value='https://www.instagram.com/fictive/?url='+O),
                      dict(id='x',cardType='text',name='Note',value=O),
                      dict(id='x',cardType='image',name='Portrait',value='',imageUrl='https://example.invalid/i.jpg',href=O)]:
            detail={'contents':[carte('m',M),carte('o',O),extra]}
            with self.subTest(extra=extra),patch.object(p,'lien_detail',AsyncMock(return_value=detail)),patch.object(p,'_requete',AsyncMock()) as req:
                self.assertFalse(asyncio.run(p.poser_tracking('fake',O)) in ('ok','déjà'))
                req.assert_not_called()

class PreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_avant_post_reessayable(self):
        import tempfile
        from process_store import Store
        from process_liens import preparer
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'process.sqlite3')
            api=LiensAPI('42',[])
            api.capacite=AsyncMock(return_value=dict(modele='model',mym=M,of=O))
            api.configurer=AsyncMock();api.poser=AsyncMock();api.verifier=AsyncMock(return_value=True);api.marquer_capacite=AsyncMock()
            detail={'contents':[carte('m',M),carte('o',O)]}
            with patch.object(p,'lien_detail',AsyncMock(side_effect=[TimeoutError('GET fictif'),detail])),patch.object(p,'_requete',AsyncMock(return_value={'id':'clone'})) as req:
                with self.assertRaises(TimeoutError): await preparer(store,'42','Fictive',api)
                self.assertEqual('reserve',store.get('liens:42:fictive')['phase'])
                req.assert_not_called()
                await preparer(store,'42','Fictive',api)
                req.assert_awaited_once_with('POST','/links/model/clone')
    async def test_timeout_post_ne_reclone_jamais(self):
        import tempfile
        from process_store import Store
        from process_liens import preparer
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'process.sqlite3')
            api=LiensAPI('42',[])
            api.capacite=AsyncMock(return_value=dict(modele='model',mym=M,of=O))
            detail={'contents':[carte('m',M),carte('o',O)]}
            async def post(*args):
                self.assertEqual('clone_incertain',store.get('liens:42:fictive')['phase'])
                raise TimeoutError('POST fictif')
            with patch.object(p,'lien_detail',AsyncMock(return_value=detail)) as get,patch.object(p,'_requete',AsyncMock(side_effect=post)) as req:
                with self.assertRaises(TimeoutError): await preparer(store,'42','Fictive',api)
                with self.assertRaises(Bloque): await preparer(store,'42','Fictive',api)
                req.assert_awaited_once()
                get.assert_awaited_once()
    async def test_modele_ambigu_avant_post_reessayable(self):
        import tempfile
        from process_store import Store
        from process_liens import preparer
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'process.sqlite3')
            api=LiensAPI('42',[])
            api.capacite=AsyncMock(return_value=dict(modele='model',mym=M,of=O))
            api.configurer=AsyncMock();api.poser=AsyncMock();api.verifier=AsyncMock(return_value=True);api.marquer_capacite=AsyncMock()
            detail={'contents':[carte('m',M),carte('o',O)]}
            ambigu={'contents':detail['contents']+[carte('old',O+'old')]}
            with patch.object(p,'lien_detail',AsyncMock(side_effect=[ambigu,detail])),patch.object(p,'_requete',AsyncMock(return_value={'id':'clone'})) as req:
                with self.assertRaises(Bloque): await preparer(store,'42','Fictive',api)
                self.assertEqual('reserve',store.get('liens:42:fictive')['phase'])
                req.assert_not_called()
                await preparer(store,'42','Fictive',api)
                req.assert_awaited_once()
