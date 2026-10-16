import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_complet import progression

class ProgressionTests(unittest.TestCase):
 def test_salons_complets_ne_masquent_pas_decouverte_restante(self):
  r=progression([{'statut':'complet'}]*50,[{'statut':'complet'}]*21+[{'statut':'a_lire'}]*113,10,100,10,10,False)
  self.assertEqual({'salons':0,'operations_decouverte':113},r['travail_restant'])
  self.assertEqual(['budget_pages_decouverte'],r['raisons_arret'])
  self.assertIn('incomplète',r['instruction'])
 def test_erreur_ou_permissions_absentes_ne_sont_pas_du_travail_termine(self):
  r=progression([{'statut':'illisible'}],[{'statut':'permissions_absentes'}],1,100,1,10,False)
  self.assertEqual({'salons':1,'operations_decouverte':1},r['travail_restant'])
  self.assertIn('decouverte_ou_reprises_restantes',r['raisons_arret'])
 def test_fin_et_budgets_distincts(self):
  r=progression([{'statut':'complet'}],[{'statut':'complet'}],100,100,10,10,False)
  self.assertEqual([],r['raisons_arret'])
  r=progression([{'statut':'a_reprendre'}],[],100,100,0,10,True)
  self.assertEqual(['borne_temps_ou_volume','budget_pages_messages'],r['raisons_arret'])
