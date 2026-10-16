import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dashboard as d

class DashboardTests(unittest.TestCase):
 def test_schema_ajoute_deux_colonnes_sans_decaler_les_autres(self):
  self.assertEqual(['Type de compte','Qualité / vérification'],d.COLONNES_S[11:])
  self.assertEqual(2,d.S_ETAT);self.assertEqual(10,d.S_TL)
 def test_type_et_ambiguite_ne_deviennent_pas_des_etats(self):
  for ancien in ('PRIVE','WARMUP','inconnu',''):
   self.assertEqual('',d.etat_affiche(ancien));self.assertTrue(d.qualite_etat(ancien))
  self.assertEqual('GOOD',d.etat_affiche('GOOD'))
  self.assertEqual(['GOOD','Faire appel','Ban','À créer'],list(d.ETATS_COULEURS))
 def test_tri_vue_et_mesures_une_seule_fois_par_gerant(self):
  rows=[];kinds=[]
  for i,e in enumerate(('PRIVE','Ban','À créer','GOOD','Faire appel')):
   r=['']*d.NB_S;r[d.S_HANDLE]=str(i);r[d.S_ETAT]=d.etat_affiche(e);r[d.S_GERANT]='Fictif'
   if i==0:r[d.S_C7]=12
   rows.append(r);kinds.append(dict(kind='compte',groupe='uid-fictif',groupe_n=5))
  d.trier_comptes_simples(rows,kinds)
  self.assertEqual(['GOOD','Faire appel','Ban','À créer',''],[r[d.S_ETAT] for r in rows])
  self.assertEqual([12],[r[d.S_C7] for r in rows if r[d.S_C7]!=''])
  self.assertTrue(all(t['groupe_n']==1 for t in kinds))
