"""Contrôles réseau doublés, destinations fictives exclusivement."""
import asyncio
from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paie_clics as p
from process_adapters import LiensAPI, DepartAPI
from process_store import Bloque

class Inventaire(list):
    complete = True

class AdaptersTests(unittest.TestCase):
    def test_unicite_distante_et_historique_obligatoire(self):
        job = dict(lid='new', lien='https://example.invalid/new', mym='https://example.invalid/m', of='https://example.invalid/o')
        async def detail(lid):
            return {'url': job['lien'], 'enabled': True, 'contents': [{'value': job['mym']}, {'value': job['of']}]} if lid == 'new' else {'contents': [{'value': job['mym']}]}
        with patch.object(p, 'lien_detail', side_effect=detail), patch.object(p, 'liens_gaml', AsyncMock(return_value=Inventaire([{'id':'new'}, {'id':'old'}]))), patch.object(p, '_lire', return_value={'liens': {}}):
            with self.assertRaisesRegex(Bloque, 'dupliqué'):
                asyncio.run(LiensAPI('42', []).verifier(job))
        with patch.object(p, 'lien_detail', side_effect=detail), patch.object(p, 'liens_gaml', AsyncMock(return_value=Inventaire([{'id':'new'}]))), patch.object(p, '_lire', return_value={'liens': {'old': {'mym': job['mym'], 'archive': True}}}):
            with self.assertRaisesRegex(Bloque, 'historique'):
                asyncio.run(LiensAPI('42', []).verifier(job))
        with patch.object(p, 'lien_detail', side_effect=detail), patch.object(p, 'liens_gaml', AsyncMock(return_value=Inventaire([{'id':'new'}]))), patch.object(p, '_lire', return_value={'liens': {}}):
            self.assertTrue(asyncio.run(LiensAPI('42', []).verifier(job)))

    def test_archivage_preserve_uid_et_dus_une_fois(self):
        data={'liens': {'old': {'uid': '42', 'depuis':'2026-10-01'}}}
        detail={'name':'X Fictive', 'note':'X Clipping UID:42'}
        def garder(info, uid, d):
            info['dus']=[{'uid':uid, 'depuis':'2026-10-01', 'avant':'2026-10-15'}]
        with patch.object(p, '_lire', return_value=data), patch.object(p, '_ecrire'), patch.object(p, 'lien_detail', AsyncMock(return_value=detail)), patch.object(p, '_requete', AsyncMock()) as request, patch.object(p, 'garder_dus', side_effect=garder) as dues, patch.object(p, '_aujourdhui', return_value=date(2026,10,15)):
            api=DepartAPI(None, 'fictif')
            asyncio.run(api.archiver_x('old'))
            asyncio.run(api.archiver_x('old'))
            dues.assert_called_once()
            request.assert_not_called()
        self.assertEqual('42', data['liens']['old']['uid'])
        self.assertEqual([], p.liens_de(data, '42'))
        self.assertTrue(data['liens']['old']['dus'])
        self.assertFalse(asyncio.run(p.reprendre_lien(data, 'old', '43', 'Fictif', 'Fictive')))
