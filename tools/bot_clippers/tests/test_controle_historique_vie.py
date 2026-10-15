"""Contrôles purs sur dossiers fictifs ; aucune écriture métier ni message."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import controle as c
from process_store import Store

NOW = datetime(2026, 10, 15, 15, tzinfo=timezone.utc)

def ligne(h, etat='GOOD', gerant='Clippeuse', onglet='Créatrice A', utilisation='Clipper'):
    return dict(handle=h, etat=etat, gerant=gerant, onglet=onglet, ligne=13, utilisation=utilisation)

def historique(n=0, reserve=0, inconnu=0, revu=True):
    comptes = [dict(id=str(i), uid='42', status='created', evidence='preuve-fictive', aliases=['fictif'+str(i)]) for i in range(n)]
    comptes += [dict(id='r'+str(i), uid='42', status='reserved', aliases=['reserve'+str(i)]) for i in range(reserve)]
    comptes += [dict(id='u'+str(i), uid='42', status='unknown', aliases=['inconnu'+str(i)]) for i in range(inconnu)]
    return dict(disponible=True, revus=['42'] if revu else [], comptes=comptes)

def contexte(lignes, hist=None, pv=None, onb=None, membres=None):
    return c._Ctx(lignes, {}, onb or {}, {'42': {'prenom': 'Clippeuse'}},
                  membres if membres is not None else {'42': 'Clippeuse'}, {}, {}, {}, [], pv or {}, NOW,
                  historique_vie=hist, exclus=[])

class ControleVieTests(unittest.TestCase):
    def test_c1_onze_good_six_incertains_ne_font_pas_dix_sept_utilisables(self):
        lignes = [ligne('fictif'+str(i), gerant='') for i in range(11)]
        lignes += [ligne('incertain'+str(i), e, '', utilisation='Créatrice' if i<2 else 'Clipper')
                   for i,e in enumerate(['PRIVE','BIZARRE','Marie à check','','PRIVE','BIZARRE'])]
        out=c._c1(contexte(lignes))
        self.assertEqual(17,len(out))
        self.assertEqual(6,sum(bool(a.get('non_mesure')) for a in out))
        self.assertEqual(2,sum(a['usage']=='creatrice' for a in out))
        self.assertNotIn('prêt pour le prochain',str(out))
        self.assertNotIn('compte créé',str(out))

    def test_caroline_quatre_good_app_trois_alerte_divergence_sans_preuve_quatre_creations(self):
        lignes=[ligne('fictif'+str(i)) for i in range(4)]
        onb={'clippers': {'42': {'comptes':['fictif0','fictif1','fictif2']}}}
        out=c._c16(contexte(lignes,historique(3),onb=onb))
        a=next(a for a in out if a['cle']=='C16|uid|42')
        self.assertIsNone(a['total_crees']);self.assertFalse(a['depassement_prouve'])
        self.assertEqual('important',a['gravite']);self.assertIn('divergence',a['texte'])

    def test_clarisse_deux_creations_deux_reservations_pas_quatre_creations(self):
        lignes=[ligne('fictif0'),ligne('fictif1'),ligne('reserve0','À créer'),ligne('reserve1','À créer')]
        a=c._c16(contexte(lignes,historique(2,reserve=2)))[0]
        self.assertEqual(2,a['total_crees']);self.assertEqual(2,a['reservations'])
        self.assertFalse(a['depassement_prouve']);self.assertIn('réservations à vérifier',a['texte'])

    def test_quatre_creations_ban_depart_changement_onglet_ne_remettent_pas_a_zero(self):
        lignes=[ligne('fictif0','BAN'),ligne('fictif1',onglet='Créatrice B')]
        a=c._c16(contexte(lignes,historique(4),membres={}))[0]
        self.assertEqual(4,a['total_crees']);self.assertTrue(a['depassement_prouve'])
        self.assertNotIn('liberer',a['texte'])

    def test_renommage_et_doublon_ne_comptent_pas_deux_creations(self):
        hist=historique(3);hist['comptes'][0]['aliases'].append('nouveau')
        lignes=[ligne('fictif0'),ligne('nouveau',onglet='Créatrice B')]
        self.assertEqual([],c._c16(contexte(lignes,hist)))

    def test_historique_absent_inconnu_jamais_total_zero(self):
        out=c._c16(contexte([ligne('fictif0','À créer')]))
        self.assertTrue(any(a.get('non_mesure') for a in out))
        self.assertIsNone(next(a for a in out if a['cle']=='C16|uid|42')['total_crees'])

    def test_identites_inconnues_restent_inconnues_meme_si_revu(self):
        a=c._c16(contexte([],historique(2,inconnu=1)))[0]
        self.assertIsNone(a['total_crees']);self.assertFalse(a['depassement_prouve'])

    def test_identite_non_resolue_pas_groupee_par_prenom(self):
        out=c._c16(contexte([ligne('x',gerant='Inconnu')],historique()))
        self.assertTrue(any(a.get('non_mesure') and 'identité stable' in a['texte'] for a in out))

    def test_date_future_ou_invalide_ne_produit_pas_age_negatif(self):
        for date in ['2026-10-20','pas-une-date']:
            out=c._c1(contexte([ligne('x',gerant='')],pv={'C1|creatrice a|x':date}))
            self.assertIn('incohérente',out[0]['texte'])

    def test_date_ancienne_conservee(self):
        out=c._c1(contexte([ligne('x',gerant='')],pv={'C1|creatrice a|x':'2026-10-12'}))
        self.assertIn('12/10/2026 (3 j)',out[0]['texte'])

    def test_controles_ne_mutent_pas_les_entrees(self):
        x=contexte([ligne('fictif0')],historique(4));avant=copy.deepcopy((x.comptes,x.historique_vie,x.onb))
        c._c1(x);c._c16(x)
        self.assertEqual(avant,(x.comptes,x.historique_vie,x.onb))

    def test_sqlite_lecture_seule_preserve_base_et_alias(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'process_clippeur.sqlite3';store=Store(p)
            store.reconcile('42',[dict(aliases=['ancien','nouveau'],status='created')],'preuve-fictive')
            avant=p.read_bytes()
            with patch.object(c,'_fichier',return_value=p):
                h=c._lire_historique_vie()
            self.assertTrue(h['disponible']);self.assertEqual(['42'],h['revus'])
            self.assertEqual(['ancien','nouveau'],h['comptes'][0]['aliases']);self.assertEqual(avant,p.read_bytes())

    def test_base_absente_ne_se_cree_pas(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'absente.sqlite3'
            with patch.object(c,'_fichier',return_value=p): self.assertFalse(c._lire_historique_vie()['disponible'])
            self.assertFalse(p.exists())

    def test_base_corrompue_inconnue(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'invalide.sqlite3';p.write_text('fictif')
            with patch.object(c,'_fichier',return_value=p): self.assertFalse(c._lire_historique_vie()['disponible'])

    def test_date_utc_convertie_en_jour_paris(self):
        x=contexte([ligne('x',gerant='')],pv={'C1|creatrice a|x':'2026-10-14T23:30:00Z'})
        self.assertIn('15/10/2026 (0 j)',c._c1(x)[0]['texte'])

    def test_date_future_meme_jour_est_incoherente(self):
        x=contexte([ligne('x',gerant='')],pv={'C1|creatrice a|x':'2026-10-15T16:00:00Z'})
        self.assertIn('incohérente',c._c1(x)[0]['texte'])

    def test_prive_est_usage_pas_preuve_sante(self):
        a=c._c16(contexte([ligne('inconnu0','PRIVE',utilisation='Privé')],historique(inconnu=1)))[0]
        self.assertIsNone(a['total_crees'])
        self.assertIn('0 pseudos avec santé déclarée',a['texte'])

    def test_depassement_historique_visible_meme_classeur_vide(self):
        out=c.anomalies([],{}, {},{}, {},{},historique_vie=historique(4),maintenant=NOW,sortis=[])
        self.assertTrue(any(a.get('depassement_prouve') for a in out))

    def test_c16_preserve_premier_signalement_ancienne_cle_par_onglet(self):
        x=contexte([ligne('fictif0')],historique(4),pv={'C16|creatrice a|clippeuse':'2026-10-12T10:00:00Z'})
        a=c._c16(x)[0]
        self.assertEqual('2026-10-12T10:00:00Z',a['premier_vu'])
        self.assertIn('12/10/2026 (3 j)',a['texte'])

    def test_c16_garde_plus_ancienne_date_lors_du_changement_de_cle(self):
        x=contexte([ligne('fictif0')],historique(4),pv={
            'C16|creatrice a|clippeuse':'2026-10-12T10:00:00Z','C16|uid|42':'2026-10-14T10:00:00Z'})
        self.assertIn('12/10/2026',c._c16(x)[0]['texte'])

    def test_nouveau_candidat_sans_rapprochement_reste_inconnu(self):
        a=c._c16(contexte([],dict(disponible=True,revus=[],comptes=[])))[0]
        self.assertIsNone(a['total_crees'])
        self.assertIn('absence de passé non démontrée',a['texte'])

    def test_nouveau_candidat_historique_vide_explicitement_revu(self):
        self.assertEqual([],c._c16(contexte([],historique())))

    def test_retour_ancien_compte_inconnu_pas_nouveau_zero(self):
        a=c._c16(contexte([],historique(inconnu=1,revu=False),onb={'clippers':{'42':{'sorti':True}}}))[0]
        self.assertIsNone(a['total_crees'])
        self.assertTrue(a['historique_inconnu'])

    def test_protection_allocation_nouveau_revu_vs_retour_inconnu(self):
        from process_store import Bloque
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'test.sqlite3')
            with self.assertRaises(Bloque): s.reserve('42',['fictif'])
            s.reconcile('42',[],'revue-fictive-absence-de-passe')
            s.reserve('42',['fictif'])
            self.assertEqual({'reserved':1},s.counts('42'))
            s.observe_alias('43','ancien','observation-fictive')
            with self.assertRaises(Bloque): s.reserve('43',['nouveau'])

    def test_c1_conserve_perimetre_hors_ban_et_logs_perdus(self):
        x=contexte([ligne('banni','BAN',gerant=''),ligne('perdu','logs perdus',gerant=''),
                    ligne('incertain','PRIVE',gerant='')])
        out=c._c1(x)
        self.assertEqual(1,len(out));self.assertTrue(out[0]['non_mesure'])
        self.assertIn('incertain',out[0]['texte'])
