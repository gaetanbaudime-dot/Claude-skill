"""Dossiers et preuves fictifs ; aucun service réel ni écriture des historiques."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recrutement as r

NOW=datetime(2026,10,16,2,0,tzinfo=timezone.utc)
def preuve(): return dict(verifie=True,reference='preuve-fictive',source='registre-fictif',date=NOW.isoformat())
def compte(n=1, reels=0):
    return dict(id=f'identite-fictive-{n}',rang=n,statut='created',etat='Good',
                cree_le=(NOW-timedelta(days=10)).isoformat(),preuve_creation='creation-fictive',
                publications=[dict(code=f'reel-fictif-{n}-{i}',publie=(NOW-timedelta(days=5-i)).isoformat(),type_verifie='reel') for i in range(reels)])
def dossier():
    return dict(uid='clippeur-fictif',tl_uid='tl-fictif',quiz_reussi=preuve(),admis=True,
                historique_vie=dict(reference='rapprochement-fictif',complet=True,comptes=[compte()]))
class ProjectionTests(unittest.TestCase):
    def test_identite_retour_et_changement_pseudo(self):
        fs=[dict(candidature_id='c-fictif',pseudo='avant'),dict(uid='u-fictif',candidature_id='c-fictif',pseudo='apres'),
            dict(uid='u-fictif',candidature_id='retour-fictif',pseudo='retour')]
        res=r.fiches_uniques(fs)
        self.assertEqual(1,len(res));self.assertEqual(['avant','apres','retour'],res[0]['pseudos'])
        self.assertEqual(['c-fictif','retour-fictif'],res[0]['candidatures'])
    def test_homonymes_non_fusionnes_et_liaison_ambigue_bloquee(self):
        res=r.fiches_uniques([dict(uid='a-fictif',candidature_id='c-fictif',pseudo='idem'),dict(uid='b-fictif',candidature_id='c-fictif',pseudo='idem')])
        self.assertEqual(2,len(res));self.assertTrue(all(f['conflit'] for f in res))
    def test_quatre_reels_test_sans_nouveau_seuil(self):
        d=dossier();d['historique_vie']['comptes']=[compte(1,4),compte(2)]
        avant=copy.deepcopy(d);v=r.projection(d,NOW)
        self.assertEqual('valide',v['test_operationnel']['statut'])
        self.assertIn('compte 2',v['prochaine_action']['texte']);self.assertEqual('clippeur-fictif',v['prochaine_action']['responsable'])
        self.assertEqual(avant,d)
    def test_doublon_photo_et_date_future_pas_des_reels(self):
        d=dossier();c=d['historique_vie']['comptes'][0]
        c['publications']=[dict(code='un-fictif',publie=NOW.isoformat(),type_verifie='reel')]*4
        c['publications'] += [dict(code='photo-fictive',publie=NOW.isoformat(),type_verifie='photo'),dict(code='futur-fictif',publie=(NOW+timedelta(days=1)).isoformat(),type_verifie='reel')]
        v=r.projection(d,NOW);self.assertEqual(1,v['test_operationnel']['publies_verifies'])
        self.assertIn('3 Reels',v['prochaine_action']['texte'])
    def test_pas_de_quatrieme_compte_ni_replacement_apres_ban(self):
        d=dossier();d['historique_vie']['comptes']=[compte(1,4),compte(2,4),compte(3)]
        d['historique_vie']['comptes'][0]['etat']='Ban'
        v=r.projection(d,NOW);self.assertEqual('verification',v['prochaine_action']['code'])
        self.assertEqual('tl-fictif',v['blocages'][0]['responsable'])
        d['historique_vie']['comptes'].append(compte(4))
        self.assertIn('limite_vie',[b['code'] for b in r.projection(d,NOW)['blocages']])
    def test_historique_inconnu_et_sortie_ne_reinitialisent_rien(self):
        for champ in ('sorti','ordre_ancien','conflit_identite'):
            d=dossier();d[champ]=True
            self.assertTrue(r.projection(d,NOW)['blocages'])
        d=dossier();d['historique_vie']['complet']=False
        self.assertEqual('resoudre_blocage',r.projection(d,NOW)['prochaine_action']['code'])
    def test_quiz_avant_discord_sans_nouvelle_etape(self):
        self.assertEqual('quiz',r.projection({},NOW)['prochaine_action']['code'])
        self.assertEqual('discord',r.projection({'quiz_reussi':preuve()},NOW)['prochaine_action']['code'])
    def test_type_prive_ne_vaut_pas_etat_sain(self):
        d=dossier();d['historique_vie']['comptes'][0]['etat']='PRIVE'
        self.assertEqual('sante_inconnue',r.projection(d,NOW)['blocages'][0]['code'])
    def test_creation_deja_enregistree_sans_date_ne_se_refait_pas(self):
        for date in ('', (NOW+timedelta(days=1)).isoformat()):
            d=dossier();d['historique_vie']['comptes'][0]['cree_le']=date
            v=r.projection(d,NOW)
            self.assertEqual('verification',v['prochaine_action']['code'])
            self.assertEqual('preuve_creation',v['blocages'][0]['code'])
    def test_quiz_reste_obligatoire(self):
        d=dossier();d['quiz_reussi']={}
        self.assertEqual('quiz',r.projection(d,NOW)['prochaine_action']['code'])
    def test_capacite_manquante_avec_responsables_et_preuves(self):
        d=dossier();d['admis']=False
        v=r.projection(d,NOW)
        self.assertFalse(v['admission_prete'])
        self.assertTrue(all(b['responsable'] and b['preuve_manquante'] for b in v['blocages']))
    def test_capacite_preparee_mais_ne_declenche_rien(self):
        d=dossier();d['admis']=False
        d['capacite']={k:dict(uid=d['uid'],valeur='reserve-fictive',preuve=preuve()) for k in ('creatrice','tl','tracking')}
        d['capacite']['tracking'].update(gaml_id='gaml-fictif',mym='https://example.invalid/m',of='https://example.invalid/o')
        d['capacite']['handle']=dict(uid=d['uid'],valeur='pseudo-fictif',preuve=dict(source='instagram_formulaire',date=NOW.isoformat(),disponible=True,reference='preuve-fictive',verifie_par='operateur-fictif'))
        self.assertTrue(r.projection(d,NOW)['admission_prete'])
        d['capacite']['handle']['preuve']['source']='scan_public'
        self.assertFalse(r.projection(d,NOW)['admission_prete'])
    def test_compte_prive_apres_quatre_sur_g2_seulement(self):
        d=dossier();d['historique_vie']['comptes']=[compte(1,4),compte(2,4),{**compte(3),'statut':'reserved'}]
        v=r.projection(d,NOW)
        self.assertEqual('creer_compte',v['prochaine_action']['code']);self.assertIn('3',v['prochaine_action']['texte'])

class MesuresTests(unittest.TestCase):
    def test_absence_source_pas_zero(self):
        m=r.metriques_hebdomadaires([],NOW,{})
        self.assertEqual(5,len(m));self.assertTrue(all(v['valeur'] is None for v in m.values()))
    def test_dedoublonnage_premiere_reussite_et_bornes(self):
        e=dict(type='quiz_reussi',identite='fictif',reference='preuve-fictive',verifie=True,date=NOW.isoformat())
        m=r.metriques_hebdomadaires([e,e,{**e,'identite':'apres-fictif','date':(NOW+timedelta(days=7)).isoformat()}],NOW,{'quiz_reussis':True})
        self.assertEqual(1,m['quiz_reussis']['valeur'])
        self.assertEqual(0,r.metriques_hebdomadaires([e,{**e,'date':(NOW-timedelta(days=1)).isoformat()}],NOW,{'quiz_reussis':True})['quiz_reussis']['valeur'])
    def test_premier_lot_date_quatrieme_publication_pas_scan(self):
        c=compte(1,4);e=r.evenement_premier_lot('fictif',c,NOW)
        self.assertEqual((NOW-timedelta(days=2)).isoformat(),e['date'])
        self.assertIsNone(r.evenement_premier_lot('fictif',compte(1,3),NOW))
    def test_j30_definition_explicite_et_cohorte_mature(self):
        e=[dict(type='admission',identite='fictif',reference='preuve-fictive',verifie=True,date=(NOW-timedelta(days=30)).isoformat()),
           dict(type='reel',identite='fictif',reference='reel-fictif',verifie=True,date=NOW.isoformat())]
        self.assertIsNone(r.metriques_hebdomadaires(e,NOW,{'actifs_j30':True})['actifs_j30']['valeur'])
        m=r.metriques_hebdomadaires(e,NOW,{'actifs_j30':True},fenetre_j30=1)
        self.assertEqual(1,m['actifs_j30']['valeur']);self.assertEqual(1,m['actifs_j30']['cohorte'])
    def test_marge_apres_remuneration_et_outils_sans_conversion_implicite(self):
        f=dict(debut=NOW.isoformat(),fin=(NOW+timedelta(days=7)).isoformat(),reference='journal-fictif',devise='EUR',revenu_attribuable='100.10',remuneration='20.05',outils='10')
        self.assertEqual('70.05',r.metriques_hebdomadaires([],NOW,{'marge':True},f)['marge']['valeur'])
        del f['outils']
        self.assertIsNone(r.metriques_hebdomadaires([],NOW,{'marge':True},f)['marge']['valeur'])

    def test_preuve_invalide_ne_devient_pas_zero_meme_si_couverture_annoncee(self):
        e=dict(type='quiz_reussi',identite='fictif',reference='preuve-fictive',verifie=True,date='illisible')
        self.assertIsNone(r.metriques_hebdomadaires([e],NOW,{'quiz_reussis':True})['quiz_reussis']['valeur'])

class SourcesTests(unittest.TestCase):
    def test_alias_garde_preuves_pas_totaux_ambigus_ni_secrets(self):
        e=dict(historique_vie=dict(disponible=True,revus=['fictif'],comptes=[dict(uid='fictif',id='stable-fictif',status='created',evidence='preuve-fictive',aliases=['avant-fictif','apres-fictif'])]),
               parcours={'fictif':dict(ordre='prive3',dates={'1_fait':(NOW-timedelta(days=10)).isoformat()},reels={'avant-fictif':dict(vus=99,reels_verifies_v2={'reel-fictif':NOW.isoformat()})})},
               registre={'fictif':dict(creatrice='Fictive',password='NE-PAS-EXPORTER'),'tl-fictif':dict(chef='Fictive')})
        pipe={'etats':{'fictif':dict(valide_par='quiz',validation=NOW.isoformat(),score_quiz='1 / 1')}}
        avant=copy.deepcopy(e)
        d=r.dossier_depuis_sources('fictif',e,pipe,['apres-fictif'],{'apres-fictif':'Good'})
        self.assertEqual('stable-fictif',d['historique_vie']['comptes'][0]['id'])
        self.assertEqual('tl-fictif',d['tl_uid'])
        self.assertEqual(1,r.projection(d,NOW)['test_operationnel']['publies_verifies'])
        self.assertNotIn('NE-PAS-EXPORTER',str(d));self.assertEqual(avant,e)
    def test_sources_manquantes_ne_deviennent_pas_historique_complet(self):
        d=r.dossier_depuis_sources('fictif',{}, {}, [], {})
        self.assertFalse(d['historique_vie']['complet']);self.assertIsNone(d['historique_vie']['reference'])
    def test_quiz_succes_et_conflit_issus_des_liaisons_explicites(self):
        pipe=dict(candidatures_web={'c-fictif':dict(quiz=dict(reussi=True,date=NOW.isoformat()))},
                  invitations={'i-fictif':dict(cand='c-fictif',membre='fictif')})
        self.assertTrue(r.dossier_depuis_sources('fictif',{},pipe,[],{})['quiz_reussi'])
        pipe['web_attendus']={'autre-fictif':dict(cand='c-fictif')}
        d=r.dossier_depuis_sources('fictif',{},pipe,[],{})
        self.assertTrue(d['conflit_identite']);self.assertFalse(d['quiz_reussi'])
