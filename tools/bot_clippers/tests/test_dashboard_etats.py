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
 def test_pods_contigus_meilleur_etat_et_clics_non_dupliques(self):
  rows=[];kinds=[]
  pods=[('D',['À créer']*3,4),('B',['Ban','Faire appel','Ban'],2),('C',['Ban']*3,3),('A',['Ban','GOOD','Faire appel'],1)]
  for uid,etats,clics in pods:
   for i,e in enumerate(etats):
    r=['']*d.NB_S;r[d.S_HANDLE]=uid+str(i);r[d.S_ETAT]=e;r[d.S_FOL]=i+10;r[d.S_R7]=i
    if i==0:r[d.S_C7]=clics
    rows.append(r);kinds.append(dict(kind='compte',groupe=uid,groupe_n=3))
  original={r[d.S_HANDLE]:(r[d.S_FOL],r[d.S_R7]) for r in rows}
  d.trier_comptes_simples(rows,kinds)
  self.assertEqual(list('AAABBBCCCDDD'),[k['groupe'] for k in kinds])
  self.assertEqual(['GOOD','Faire appel','Ban'],[r[d.S_ETAT] for r in rows[:3]])
  self.assertEqual(10,sum(r[d.S_C7] for r in rows if isinstance(r[d.S_C7],int)))
  for uid,_,clics in pods:
   self.assertEqual([clics],[r[d.S_C7] for r,k in zip(rows,kinds) if k['groupe']==uid and r[d.S_C7]!=''])
  self.assertEqual(original,{r[d.S_HANDLE]:(r[d.S_FOL],r[d.S_R7]) for r in rows})
 def test_anomalies_nombre_types_et_liens_conservees(self):
  from copy import deepcopy
  cs=[dict(type_compte=t,lien_gaml='g',lien_mym='m',lien_infloww='o') for t in ('croissance 1','croissance 2','privé')]
  self.assertEqual('',d.qualite_pod(cs))
  cs.append(dict(type_compte='inconnu',lien_gaml='autre'));before=deepcopy(cs)
  result=d.qualite_pod(cs)
  self.assertIn('4 IG',result);self.assertIn('GAML absent ou multiple',result)
  self.assertEqual(before,cs)
  self.assertEqual('Non relevé',d.mesure_pod(None));self.assertEqual(0,d.mesure_pod(0))
 def test_lien_gaml_partage_sur_trois_lignes_compte_une_fois(self):
  from unittest.mock import Mock
  ctx=Mock();ctx.clics_lien.return_value=dict(auj=1,hier=2,c7=30,c7p=20,paie=10,paie_manque=set(),t_auj=None)
  k=d._clics_de(ctx,['gaml-fictif']*3)
  self.assertEqual(30,k['c7']);ctx.clics_lien.assert_called_once_with('gaml-fictif')
