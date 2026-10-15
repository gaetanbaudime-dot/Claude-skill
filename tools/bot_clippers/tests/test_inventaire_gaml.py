"""Inventaire complet uniquement si une fin de pagination est établie."""
from pathlib import Path
import sys,unittest
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import paie_clics as p

class InventaireTests(unittest.IsolatedAsyncioTestCase):
    async def test_enveloppe_inconnue_ne_devient_pas_un_inventaire_vide(self):
        with patch.object(p,'_requete',AsyncMock(return_value={'unexpected':[{'id':'fictif'}]})):
            with self.assertRaises(RuntimeError): await p.liens_gaml()
    async def test_page_repetee_nest_pas_une_fin_prouvee(self):
        with patch.object(p,'_requete',AsyncMock(return_value=[{'id':'fictif'}])):
            r=await p.liens_gaml()
        self.assertFalse(r.complete);self.assertEqual(1,len(r))
    async def test_hydra_et_page_vide_valident_linvenaire(self):
        with patch.object(p,'_requete',AsyncMock(side_effect=[{'hydra:member':[{'id':'a'}]},{'hydra:member':[{'id':'b'}]},{'hydra:member':[]}])):
            r=await p.liens_gaml()
        self.assertTrue(r.complete);self.assertEqual(['a','b'],[x['id'] for x in r])
    async def test_page_invalide_preserve_les_resultats_sans_completude(self):
        with patch.object(p,'_requete',AsyncMock(side_effect=[[{'id':'a'}],{'unknown':[]}])):
            r=await p.liens_gaml()
        self.assertFalse(r.complete);self.assertEqual(['a'],[x['id'] for x in r])
    async def test_identifiant_absent_bloque_linventaire(self):
        with patch.object(p,'_requete',AsyncMock(return_value=[{'name':'fictif'}])):
            with self.assertRaises(RuntimeError): await p.liens_gaml()
