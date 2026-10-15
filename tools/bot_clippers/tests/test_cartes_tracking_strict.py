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
                    asyncio.run(LiensAPI('42', []).cloner('fake'))
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
