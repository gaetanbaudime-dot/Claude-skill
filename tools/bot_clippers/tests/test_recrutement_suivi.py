"""Données fictives, aucun transport ni identité réelle."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recrutement_suivi as r
import web_candidature as w

NOW=datetime(2026, 10, 16, tzinfo=timezone.utc)
def dossier(uid='10', jours=15, **kw):
    return dict(uid=uid, validation=(NOW-timedelta(days=jours)).isoformat(), preuve_validation='fictive', **kw)
def reel(jours, code='r1', uid='10'):
    return dict(uid=uid, code=code, date=(NOW-timedelta(days=jours)).isoformat(), verifie=True, attribution='liee')

class Mesures(unittest.TestCase):
    def test_j7_j14_et_cadence_distincts(self):
        v=r.mesurer([dossier()], [reel(12),reel(3,'r2')],NOW,True)
        self.assertEqual(v['cohortes']['j7']['actifs'],1)
        self.assertEqual(v['cohortes']['j14']['actifs'],1)
        self.assertEqual(v['dossiers'][0]['cadence_7j'],1/7)
    def test_immature_et_inconnue_hors_denominateur(self):
        v=r.mesurer([dossier(jours=6),dict(uid='11')],[],NOW,True)
        self.assertEqual(v['cohortes']['j7'],dict(denominateur=0,actifs=0,exclus_immatures=1,exclus_non_mesures=0,dates_inconnues=1,blocages_techniques=0))
    def test_absence_collecte_ne_vaut_pas_zero(self):
        v=r.mesurer([dossier()],[],NOW)
        self.assertIsNone(v['dossiers'][0]['actif_recent'])
        self.assertEqual(v['cohortes']['j14']['denominateur'],0)
    def test_doublons_alias_compte_une_fois(self):
        v=r.mesurer([dossier(),dossier()], [reel(3),reel(3)],NOW,True)
        self.assertEqual(len(v['dossiers']),1)
        self.assertEqual(v['dossiers'][0]['j14']['reels'],1)
    def test_date_contradictoire_non_mesuree(self):
        v=r.mesurer([dossier()],[reel(3),reel(4)],NOW,True)
        self.assertEqual(v['cohortes']['j14']['denominateur'],0)
    def test_validation_future_naive_absente(self):
        for date in ['2026-11-01T00:00:00+00:00','2026-10-01T00:00:00',None]:
            v=r.mesurer([dict(uid='10',validation=date,preuve_validation='p')],[],NOW,True)
            self.assertIsNone(v['dossiers'][0]['validation'])
    def test_blocage_pas_echec_ni_exclusion(self):
        v=r.mesurer([dossier(blocage_technique=True,tl_uid='20')],[],NOW,True)['dossiers'][0]
        self.assertEqual(v['objectif_48h'],'blocage_technique')
        self.assertEqual(v['responsable'],'20')
    def test_bornes_anniversaire(self):
        # Publication à J7 exclue de [J0,J7[, incluse dans [J7,J14[.
        v=r.mesurer([dossier(jours=14)],[reel(7)],NOW,True)
        self.assertEqual(v['cohortes']['j7']['actifs'],0)
        self.assertEqual(v['cohortes']['j14']['actifs'],1)
    def test_historique_ancien_non_recupere_par_nouvelle_admission(self):
        v=r.mesurer([dossier(jours=3)],[reel(4)],NOW,True)['dossiers'][0]
        self.assertIsNone(v['premier_reel'])
    def test_retours_dates_contradictoires(self):
        v=r.mesurer([dossier(),dossier(jours=20)],[],NOW,True)
        self.assertEqual(v['cohortes']['j7']['dates_inconnues'],1)
    def test_seuils_explicites_seulement(self):
        self.assertEqual(r.decision_volume({}, {})['statut'],'a_valider')
        s=dict(preuve_approbation='fictive',activation_j7=.5,retention_j14=.5,effectif_min=10)
        m=dict(aide_disponible=10,aide_requise=9,activation_j7=.8,retention_j14=.8,effectif=20)
        self.assertEqual(r.decision_volume(m,s)['statut'],'revue_montee_possible')
        self.assertFalse(r.decision_volume(m,s)['automatique'])
        for k in m:
            self.assertEqual(r.decision_volume({**m,k:None},s)['statut'],'maintenir')
        self.assertEqual(r.decision_volume({**m,'aide_requise':11},s)['statut'],'maintenir')

class Identite(unittest.TestCase):
    def test_homonymes_telephone_ne_lient_pas(self):
        p=dict(candidatures_web={'a':dict(tel='fictif'),'b':dict(tel='fictif')})
        self.assertTrue(r.lier_discord(p,'a','10'))
        self.assertEqual(r.liaisons(p),{'a':{'10'}})
        self.assertFalse(r.lier_discord(p,'a','11'))
        self.assertEqual(r.liaisons(p),{'a':{'10','11'}})
    def test_snapshot_pas_ecrase_par_contact_reutilise(self):
        p=dict(candidatures_web={'a':dict(tel='fictif',dossier=dict(prenom='Premier'))},candidatures={'fictif':dict(id='b',prenom='Autre')})
        self.assertEqual(r.dossier_candidature(p,'a')['prenom'],'Premier')
        del p['candidatures_web']['a']['dossier']
        self.assertEqual(r.dossier_candidature(p,'a'),{})
    def test_publications_identite_stable_renommages_conflits(self):
        p=dict(candidatures_web={'a':dict(discord_uids=['10'])})
        parcours={'10':dict(reels={'ancien':dict(reels_verifies_v2={'r':'2026-10-01T00:00:00Z'}),'nouveau':dict(reels_verifies_v2={'r':'2026-10-01T00:00:00Z'})})}
        v=r.publications_attribuees(p,parcours)
        self.assertEqual(len(v),1)
        self.assertEqual(v[0]['candidatures'],['a'])
        r.lier_discord(p,'a','11')
        self.assertEqual(r.publications_attribuees(p,parcours)[0]['attribution'],'conflit')

class Formulaire(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pipe={}
        def lire(*a):return copy.deepcopy(self.pipe)
        def ecrire(f,d):self.pipe=copy.deepcopy(d)
        cfg={'questions':[dict(id='prenom',label='Prénom',type='text',requis=True),dict(id='age',label='Âge',type='number',requis=True)]}
        self.patches=[patch.object(w,'_deps',dict(lire_json=lire,ecrire_json=ecrire,FICHIER_PIPELINE='fictif',tel_selon_pays=lambda *a:'fictif')),
                      patch.object(w,'_questions',return_value=cfg),patch.object(w,'_jeton_formulaire_ok',return_value=True),
                      patch.object(w,'_rafale',return_value=False),patch.object(w.numeros,'verifier',return_value=('fictif','fictif','','')),
                      patch.object(w,'DISCORD_CLIENT_ID',''),patch.object(w,'DISCORD_CLIENT_SECRET','')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    async def poster(self,token,**kw):
        data=dict(prenom='Fictif',age='25',candidature=token,src='tg-fictif',campagne='vague-a',**kw)
        try:return await w.post_candidature(SimpleNamespace(post=AsyncMock(return_value=data),headers={},remote='fake'))
        except w.web.HTTPSeeOther as e:return e
    async def test_rejeu_et_concurrence_memes_dossier(self):
        import asyncio
        token=w.jeton('candidature:fictif')
        await asyncio.gather(self.poster(token),self.poster(token))
        self.assertEqual(list(self.pipe['candidatures_web']),['fictif'])
        self.assertEqual(self.pipe['candidatures_web']['fictif']['campagne'],'vague-a')
        await self.poster(w.jeton('candidature:autre'))
        self.assertEqual(len(self.pipe['candidatures_web']),2)
        self.assertEqual(self.pipe['candidatures_web']['fictif']['dossier']['id'],'fictif')
    async def test_formulaire_garde_campagne_et_nonce_sur_erreur(self):
        with patch.object(w,'_jeton_formulaire_ok',return_value=False):
            token=w.jeton('candidature:fictif')
            rep=await self.poster(token)
        self.assertIn(token,rep.text)
        self.assertIn("name='campagne' value='vague-a'",rep.text)
        self.assertEqual(self.pipe,{})
    def test_lien_canal_campagne(self):
        with patch.object(w,'WEB_ACTIVER','1'),patch.object(w,'WEB_URL_PUBLIQUE','https://example.invalid'):
            self.assertEqual(w.lien_candidature('Discord','Octobre A'),'https://example.invalid/candidature?src=discord&campagne=octobre-a')

class CouvertureEtSchema(unittest.TestCase):
    def test_deux_candidats_avant_discord(self):
        dossiers=r.dossiers_depuis_sources({'candidatures_web':{'a':{},'b':{}}},{},{},[])
        v=r.mesurer(dossiers,[],NOW,True)
        self.assertEqual(len(v['dossiers']),2)
        self.assertEqual({d['uid'] for d in v['dossiers']},{'candidature:a','candidature:b'})
    def test_reservation_pas_creation_ni_pret(self):
        p={'candidatures_web':{'a':{'discord_uids':['10']}}}
        d=r.dossiers_depuis_sources(p,{'10':{'creatrice':'Fictive','date':'2026-10-01'}},{},[{'uid':'10','status':'reserved'}])[0]
        self.assertEqual(d['comptes_reserves'],1)
        self.assertEqual(d['comptes_crees_prouves'],0)
        self.assertIsNone(d['pret_le'])
        self.assertIsNone(d['validation'])
    def test_ancien_quiz_sans_note_reste_inconnu(self):
        for q in [{'reussi':True,'date':'2026-10-11'}, {'reussi':True,'date':'2026-10-13T00:00:00Z','score':'8 / 8'}]:
            p={'candidatures_web':{'a':{'quiz':q}}}
            d=r.dossiers_depuis_sources(p,{},{},[])[0]
            self.assertEqual(d['score_quiz'],q.get('score'))
            self.assertIsNone(d['validation'])
    def test_dst_duree_utc(self):
        # Passage heure d'hiver Europe/Paris : sept jours = 168 heures UTC.
        date='2026-10-20T02:30:00+02:00'
        fin=datetime(2026,10,27,0,30,tzinfo=timezone.utc)
        d=dict(uid='10',validation=date,preuve_validation='fictive',blocage_technique=True)
        a=r.mesurer([d],[],fin-timedelta(seconds=1),True)
        b=r.mesurer([d],[],fin,True)
        self.assertEqual(a['cohortes']['j7']['denominateur'],0)
        self.assertEqual(b['cohortes']['j7']['denominateur'],1)
        self.assertEqual(b['cohortes']['j7']['blocages_techniques'],1)
    def test_contact_ne_prouve_pas_discord(self):
        p={'candidatures_web':{'a':{'tel':'0000000000'}},'liaisons':{'10':{'tel':'0000000000'}}}
        self.assertEqual(w._uids_de(p,'a'),[])
    def test_url_reel_dedoublonnee(self):
        a=reel(3,'abc')
        b=reel(3,'https://www.instagram.com/reel/abc/?igsh=fictif')
        v=r.mesurer([dossier()],[a,b],NOW,True)
        self.assertEqual(v['dossiers'][0]['j14']['reels'],1)
    def test_premiere_reussite_retakes(self):
        p={'candidatures_web':{'a':{'quiz_historique':{
            '1':dict(reussi=False,date='2026-10-01T00:00:00Z'),
            '2':dict(reussi=True,date='2026-10-02T00:00:00Z'),
            '3':dict(reussi=True,date='2026-10-03T00:00:00Z')
        }},'b':{'quiz':{'reussi':True}}}}
        self.assertEqual(r.premieres_reussites(p),{'a':'2026-10-02T00:00:00+00:00'})

class LiaisonBot(unittest.IsolatedAsyncioTestCase):
    async def test_contact_partage_lit_snapshot_et_pas_derniere_personne(self):
        import ast
        import logging
        pipe={'candidatures_web':{'a':dict(discord_uids=['10'],tel='fictif',dossier=dict(prenom='Premier',pays='Fictif'))},
              'candidatures':{'fictif':dict(id='b',prenom='Autre')},
              'liaisons':{'20':dict(tel='fictif')},'etats':{}}
        mp=AsyncMock()
        def lire(*a):return copy.deepcopy(pipe)
        def ecrire(f,d):pipe.clear();pipe.update(d)
        ns=dict(recrutement_suivi=r,interpretations_tel=lambda b:['fictif'],lire_json=lire,ecrire_json=ecrire,
                FICHIER_PIPELINE='fictif',envoyer_mp=mp,datetime=datetime,timezone=timezone,
                journal=logging.getLogger('fictif'),membre_par_id=lambda uid:None,texte_accueil_liaison=lambda *a:'')
        arbre=ast.parse((Path(w.__file__).parent/'bot_discord.py').read_text())
        exec(compile(ast.Module(body=[n for n in arbre.body if getattr(n,'name',None)=='traiter_liaison'],type_ignores=[]),'fictif','exec'),ns)
        auteur=SimpleNamespace(id=10)
        await ns['traiter_liaison'](auteur,'fictif',cand_id='a')
        self.assertEqual(pipe['liaisons']['10']['prenom'],'Premier')
        self.assertEqual(pipe['liaisons']['10']['candidature_id'],'a')
        avant=copy.deepcopy(pipe)
        await ns['traiter_liaison'](auteur,'fictif',cand_id='b')
        self.assertEqual(avant,pipe)

class RapportLocal(unittest.TestCase):
    def test_source_absente_ou_schema_invalide_non_mesure(self):
        from outils.mesurer_recrutement import rapport
        self.assertEqual(rapport({},NOW)['statut'],'non_mesure')
        self.assertEqual(rapport(dict(pipeline=[],equipes={},parcours={},comptes=[]),NOW)['statut'],'non_mesure')
    def test_rapport_incomplet_ne_devient_pas_zero(self):
        from outils.mesurer_recrutement import rapport
        p={'candidatures_web':{'a':{'discord_uids':['10']}},'etats':{'10':{'validation':'2026-10-01T00:00:00Z','valide_par':'quiz'}}}
        v=rapport(dict(pipeline=p,equipes={},parcours={},comptes=[]),NOW)
        self.assertEqual(v['cohortes']['j7']['denominateur'],0)
        self.assertEqual(v['cohortes']['j7']['exclus_non_mesures'],1)
        self.assertEqual(v['volume']['statut'],'a_valider')

class ConflitsRevue(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pipe={'candidatures_web':{'a':{'discord_uids':['10','11'],'tel':'partage'}},
                   'etats':{'10':dict(validation='2026-10-01T00:00:00Z',valide_par='quiz')}}
        def lire(*a):return copy.deepcopy(self.pipe)
        def ecrire(f,d):self.pipe=copy.deepcopy(d)
        self.traiter=AsyncMock()
        self.inviter=AsyncMock()
        self.patches=[patch.object(w,'_deps',dict(lire_json=lire,ecrire_json=ecrire,FICHIER_PIPELINE='fake',
            traiter_quiz_web=self.traiter,invitation_site=self.inviter,membre_par_id=lambda uid:SimpleNamespace(id=uid))),
            patch.object(w,'_prechauffer_places')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    async def test_quiz_reussi_conflit_et_replay_aucune_livraison(self):
        quiz={'questions':[{'id':'f','q':'Fictif','choix':['A','B'],'bonne':0}],'seuil':1}
        with patch.object(w,'_quiz',return_value=quiz),patch.object(w,'quiz_seuil_total',return_value=(1,1)),patch.object(w,'noter',return_value=(1,1,[])):
            nonce=w._ouvrir_tentative(quiz,'c','a')
            for _ in range(2):
                rep=await w.post_quiz_cand({'tentative':nonce,'q-f':'0'},'a')
                self.assertIn('vérifie la liaison',rep.text)
        self.assertTrue(self.pipe['candidatures_web']['a']['quiz']['reussi'])
        self.assertEqual(len(self.pipe['candidatures_web']['a']['quiz_historique']),1)
        self.assertEqual(w._uids_de(self.pipe,'a'),[])
        self.assertEqual(w._membre_present(self.pipe,'a'),'')
        self.traiter.assert_not_called();self.inviter.assert_not_called()
    async def test_invitation_oauth_et_cache_refuses(self):
        self.pipe['candidatures_web']['a']['quiz']={'reussi':True}
        request=SimpleNamespace(query={'t':w.jeton('a'),'state':w.jeton('a'),'code':'fictif'})
        with patch.object(w,'_cand_depuis',return_value='a'),patch.object(w,'_retours',{'a':(w.time.time(),'Fictif',1)}):
            for appel in (w.get_invitation,w.get_connexion,w.get_callback):
                rep=await appel(request)
                self.assertIn('vérifie la liaison',rep.text)
            self.assertEqual(await w._invitation_prete('a'),'')
        self.inviter.assert_not_called()
    def test_cas_exact_pas_de_reintroduction_historique(self):
        equipes={'10':dict(creatrice='Fictive')}
        parcours={'10':dict(reels={'alias':dict(reels_verifies_v2={'code':'2026-10-02T00:00:00Z'})})}
        dossiers=r.dossiers_depuis_sources(self.pipe,equipes,parcours,[])
        self.assertEqual(len(dossiers),1)
        self.assertIsNone(dossiers[0]['uid'])
        preuves=r.publications_attribuees(self.pipe,parcours)
        self.assertEqual(preuves[0]['attribution'],'conflit')
        v=r.mesurer(dossiers,preuves,NOW,True)
        self.assertEqual(v['cohortes']['j7']['actifs'],0)
        self.assertEqual(v['cohortes']['j7']['denominateur'],0)
    def test_mesurer_refuse_attribution_inconnue_ou_conflit(self):
        for valeur in ('conflit','inconnue',None):
            v=r.mesurer([dossier()],[{**reel(12),'attribution':valeur}],NOW,True)
            self.assertEqual(v['cohortes']['j7']['actifs'],0)
            self.assertEqual(v['cohortes']['j7']['denominateur'],0)
            self.assertIsNone(v['dossiers'][0]['premier_reel'])
    async def test_contact_partage_ne_fusionne_pas_capacite(self):
        self.pipe={'candidatures_web':{
            'a':dict(tel='partage',quiz=dict(reussi=True,date=(NOW-timedelta(minutes=2)).isoformat())),
            'b':dict(tel='partage',quiz=dict(reussi=True,date=(NOW-timedelta(minutes=1)).isoformat()))}}
        self.assertEqual(w._reussites_en_route(self.pipe,'b',NOW.timestamp(),NOW.timestamp()),1)
        self.assertEqual(w._reussites_en_route(self.pipe,'',NOW.timestamp(),NOW.timestamp()),2)
        self.pipe['candidatures_web']['a']['discord_uids']=['10','11']
        self.assertEqual(await w._places_livrables('b'),0)
    async def test_conflit_survenu_pendant_lecture_places(self):
        self.pipe['candidatures_web']['a']['discord_uids']=['10']
        quiz={'questions':[{'id':'f','q':'Fictif','choix':['A','B'],'bonne':0}],'seuil':1}
        async def places(*a,**kw):
            self.pipe['candidatures_web']['a']['discord_uids']=['10','11']
            return 1
        with patch.object(w,'_quiz',return_value=quiz),patch.object(w,'quiz_seuil_total',return_value=(1,1)),patch.object(w,'noter',return_value=(1,1,[])),patch.object(w,'_places_livrables',side_effect=places):
            nonce=w._ouvrir_tentative(quiz,'c','a')
            rep=await w.post_quiz_cand({'tentative':nonce,'q-f':'0'},'a')
            self.assertIn('vérifie la liaison',rep.text)
        self.traiter.assert_not_called()
    def test_conflit_explicite_non_efface_par_reliaison(self):
        self.pipe['candidatures_web']['a'].update(discord_uids=['10'],conflit_identite=True)
        self.assertFalse(r.lier_discord(self.pipe,'a','10'))
        self.assertEqual(w._uids_de(self.pipe,'a'),[])
