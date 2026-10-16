import sys
from pathlib import Path
from datetime import date
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import paie_clics as p
import tableau_bord as t

class PeriodesTests(unittest.TestCase):
    def test_dates_inclusives_et_arguments_invalides(self):
        self.assertEqual((date(2026,10,1),date(2026,10,7)),p.periode_mesclics(['2026-10-01','2026-10-07'],date(2026,10,16)))
        for args in [['hier'],['2026-10-07','2026-10-01'],['2026-10-01','2026-10-16']]:
            with self.assertRaises(ValueError): p.periode_mesclics(args,date(2026,10,16))
    def test_intervalle_exact_fixe_sans_equivalent_argent(self):
        d={'liens':{'a':{'depuis':'2026-09-01'}}}
        bounds=(date(2026,10,1),date(2026,10,7))
        with patch.object(p,'liens_de',return_value=['a']),patch.object(p,'somme',return_value={'payes':7,'jours':7}) as somme,patch.object(p,'non_releves',return_value=[]),patch.object(p,'regime',return_value='fixe'):
            s=p.texte_clics_periode(d,'fictif',bounds)
        somme.assert_called_once_with(d,['a'],*bounds)
        self.assertIn('7',s);self.assertIn('forfait fixe',s);self.assertNotIn('$',s)
    def test_absence_releve_non_zero(self):
        with patch.object(p,'liens_de',return_value=['a']),patch.object(p,'somme',return_value={'payes':0,'jours':0}),patch.object(p,'non_releves',return_value=[('a','2026-10-01')]),patch.object(p,'regime',return_value='clic'):
            s=p.texte_clics_periode({'liens':{'a':{}}},'fictif',(date(2026,10,1),date(2026,10,7)))
        self.assertIn('non mesuré',s);self.assertNotIn('**0**',s)
    def test_flux_non_cohortes_jamais_conversion(self):
        for r in [3,15]:
            s=t.texte_declencheurs({'entonnoir':{'quiz':10,'discord':10,'formulaires':10},'reel_14':(r,6),'livrables':100,'valides_30':6})
            self.assertIn('non comparable',s);self.assertNotIn('250 %',s);self.assertNotIn('trois sont au vert',s)

class CommandeTests(unittest.IsolatedAsyncioTestCase):
    async def test_commande_ne_perd_pas_les_arguments(self):
        from types import SimpleNamespace as N
        from unittest.mock import AsyncMock
        m=N(author=N(id=42,display_name='Fictif'),reply=AsyncMock())
        with patch.object(p,'_aujourdhui',return_value=date(2026,10,16)),patch.object(p,'actif',return_value=True),patch.object(p,'_lire',return_value={}),patch.object(p,'texte_clics_periode',return_value='intervalle exact') as rendu:
            await p.commande_clipper(m,'!mesclics 2020-01-01 2020-01-07')
        self.assertEqual((date(2020,1,1),date(2020,1,7)),rendu.call_args.args[2])
        m.reply.assert_awaited_once_with('intervalle exact')

class ResumeTests(unittest.TestCase):
    def test_resume_fixe_sans_releves_ne_promet_ni_zero_ni_paie_variable(self):
        q=dict(payes=0,jours=0,hors_robots=0,brut=0,brut_non_lu=0)
        d={'liens':{'a':{'url':'lien-fictif'}},'wallets':{}}
        with patch.object(p,'liens_de',return_value=['a']),patch.object(p,'_aujourdhui',return_value=date(2026,10,16)),patch.object(p,'somme',return_value=q),patch.object(p,'periode_en_cours',return_value=(date(2026,10,1),date(2026,10,15))),patch.object(p,'_debut_paie',return_value=date(2026,10,1)),patch.object(p,'regime',return_value='fixe'),patch.object(p,'non_releves',return_value=[('a','2026-10-01')]):
            s=p.texte_mesclics(d,'fictif','Fictif')
        self.assertNotIn('$',s);self.assertNotIn('**0**',s);self.assertIn('non mesuré',s);self.assertNotIn('dans la journée',s)
