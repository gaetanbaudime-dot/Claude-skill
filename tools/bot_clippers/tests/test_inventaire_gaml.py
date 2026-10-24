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
    async def test_page_repetee_identique_sous_le_forfait_est_la_liste_entiere(self):
        # 23/10 : GAML ignore `page` et rend la liste entière à chaque appel (49 liens, page 2 identique) : c'est la fin.
        liste=[{'id':str(i)} for i in range(49)]
        with patch.object(p,'_requete',AsyncMock(return_value=liste)),patch.object(p,'LISTE_GAML_MAX',100):
            r=await p.liens_gaml()
        self.assertTrue(r.complete);self.assertEqual(49,len(r))
    async def test_page_repetee_au_plafond_suppose_reste_incomplete(self):
        liste=[{'id':str(i)} for i in range(100)]
        with patch.object(p,'_requete',AsyncMock(return_value=liste)),patch.object(p,'LISTE_GAML_MAX',100):
            r=await p.liens_gaml()
        self.assertFalse(r.complete);self.assertEqual(100,len(r))
    async def test_cinquante_lignes_sous_un_forfait_de_cinquante_actifs_sont_la_liste_entiere(self):
        # 24/10 : 36 liens actifs + 14 désactivés = 50 lignes ; le forfait (50) ne limite que les ACTIFS : la liste n'était pas coupée
        liste=[{'id':str(i),'enabled':i>=14} for i in range(50)]
        with patch.object(p,'_requete',AsyncMock(return_value=liste)),patch.object(p,'FORFAIT_LIENS_GAML',50),patch.object(p,'LISTE_GAML_MAX',100):
            r=await p.liens_gaml()
        self.assertTrue(r.complete);self.assertEqual(50,len(r))
    def test_plafond_par_defaut_depasse_le_forfait_de_liens_actifs(self):
        self.assertGreater(p.LISTE_GAML_MAX,p.FORFAIT_LIENS_GAML)
        self.assertGreaterEqual(p.LISTE_GAML_MAX,100)
    async def test_page_en_partie_deja_lue_nest_pas_une_fin_prouvee(self):
        with patch.object(p,'_requete',AsyncMock(side_effect=[[{'id':'a'},{'id':'b'}],[{'id':'a'}]])),patch.object(p,'LISTE_GAML_MAX',100):
            r=await p.liens_gaml()
        self.assertFalse(r.complete);self.assertEqual(['a','b'],[x['id'] for x in r])
    async def test_page_neuve_puis_repetee_nest_pas_une_fin_prouvee(self):
        # page 2 neuve (pagination réelle), page 3 qui ne redonne que la page 2 : pas la liste entière
        with patch.object(p,'_requete',AsyncMock(side_effect=[[{'id':'a'}],[{'id':'b'}],[{'id':'b'}]])),patch.object(p,'LISTE_GAML_MAX',100):
            r=await p.liens_gaml()
        self.assertFalse(r.complete);self.assertEqual(['a','b'],[x['id'] for x in r])
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
