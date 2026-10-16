"""Retries HTTP et redémarrages simulés, sans client Discord ni réseau."""
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_candidature as w

QUIZ={'titre':'Fictif', 'seuil':1, 'questions':[{'id':'fictive','q':'Choix ?', 'choix':['A','B'], 'bonne':0}]}
class QuizTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data={'candidatures_web':{'cand':{'tel':'fake'}}, 'etats':{}}
        def lire(*a): return copy.deepcopy(self.data)
        def ecrire(f, d): self.data=copy.deepcopy(d)
        async def traiter(uid, score, ok, details, **kw):
            self.data['etats'][uid]={'essais_quiz':self.data['etats'].get(uid,{}).get('essais_quiz',0)+1}
            return 'applied'
        self.callback=AsyncMock(side_effect=traiter)
        self.patches=[patch.object(w,'_deps',{'lire_json':lire,'ecrire_json':ecrire,'FICHIER_PIPELINE':'fake',
            'essais_quiz':lambda uid:self.data['etats'].get(uid,{}).get('essais_quiz',0),
            'traiter_quiz_web':self.callback}), patch.object(w,'_quiz',return_value=QUIZ),
            patch.object(w,'quiz_seuil_total',return_value=(1,1)),patch.object(w,'noter',return_value=(0,1,[])),
            patch.object(w,'jeton',side_effect=lambda x:x),patch.object(w,'verifier_jeton',side_effect=lambda x:x),
            patch.object(w,'_prechauffer_places')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    def formulaire(self, champ='c', owner='cand'):
        rep=w._formulaire_quiz(QUIZ,champ,owner,1)
        found=re.search("name='tentative' value='([^']+)'",rep.text)
        return found.group(1) if found else 'avant-correction'
    async def post_discord(self, token):
        return await w.post_quiz(SimpleNamespace(post=AsyncMock(return_value={'t':'42','tentative':token,'q-fictive':'1'})))
    async def test_retry_candidat_compte_une_seule_fois(self):
        token=self.formulaire()
        await w.post_quiz_cand({'tentative':token,'q-fictive':'1'},'cand')
        await w.post_quiz_cand({'tentative':token,'q-fictive':'1'},'cand')
        self.assertEqual(1,self.data['candidatures_web']['cand']['quiz']['essais'])
    async def test_retry_discord_compte_une_seule_fois(self):
        token=self.formulaire('t','42')
        await self.post_discord(token)
        await self.post_discord(token)
        self.assertEqual(1,self.callback.await_count)
        self.assertEqual(1,self.data['etats']['42']['essais_quiz'])
    async def test_nouvel_essai_et_vieux_replay_ne_comptent_pas_trois(self):
        t1=self.formulaire()
        await w.post_quiz_cand({'tentative':t1},'cand')
        t2=self.formulaire()
        self.assertNotEqual(t1,t2)
        await w.post_quiz_cand({'tentative':t1},'cand')
        self.assertEqual(1,self.data['candidatures_web']['cand']['quiz']['essais'])
        await w.post_quiz_cand({'tentative':t2},'cand')
        self.assertEqual(2,self.data['candidatures_web']['cand']['quiz']['essais'])
    async def test_token_manquant_forge_ou_autre_candidat_ne_compte_pas(self):
        token=self.formulaire()
        self.data['candidatures_web']['autre']={}
        for data in ({},{'tentative':'invente'},{'tentative':token}):
            await w.post_quiz_cand(data,'autre')
        self.assertNotIn('quiz',self.data['candidatures_web']['autre'])
    async def test_deux_onglets_partagent_la_tentative(self):
        self.assertEqual(self.formulaire(),self.formulaire())
    async def test_retry_concurrent_discord(self):
        token=self.formulaire('t','42')
        originale=self.callback.side_effect
        async def lent(*a, **kw):
            await asyncio.sleep(0)
            return await originale(*a,**kw)
        self.callback.side_effect=lent
        await asyncio.gather(self.post_discord(token),self.post_discord(token))
        self.assertEqual(1,self.callback.await_count)
    async def test_reprise_apres_redemarrage_ne_recorrige_pas(self):
        token=self.formulaire('t','42')
        self.callback.side_effect=RuntimeError('interruption fictive avant effet')
        with self.assertRaises(RuntimeError): await self.post_discord(token)
        w._quiz_verrous.clear()  # aucune donnée d'idempotence en mémoire
        self.assertEqual(token,self.formulaire('t','42'))
        self.callback.side_effect=None
        self.callback.return_value='applied'
        with patch.object(w,'noter',side_effect=AssertionError('résultat déjà figé')):
            await self.post_discord(token)
        self.assertTrue(self.data['quiz_tentatives_web']['t:42']['terminee'])
        self.assertEqual(token,self.callback.call_args.kwargs['tentative_id'])
    async def test_revision_changee_exige_un_nouveau_formulaire(self):
        token=self.formulaire()
        with patch.object(w,'_revision_quiz',return_value='autre-revision'):
            await w.post_quiz_cand({'tentative':token},'cand')
        self.assertNotIn('quiz',self.data['candidatures_web']['cand'])
    async def test_retry_ne_redonne_pas_un_essai_apres_24h(self):
        token=self.formulaire()
        await w.post_quiz_cand({'tentative':token},'cand')
        token2=self.formulaire()
        await w.post_quiz_cand({'tentative':token2},'cand')
        self.data['candidatures_web']['cand']['quiz']['date']='2020-01-01T00:00:00+00:00'
        await w.post_quiz_cand({'tentative':token2},'cand')
        self.assertEqual(2,self.data['candidatures_web']['cand']['quiz']['essais'])
        token3=self.formulaire()
        await w.post_quiz_cand({'tentative':token3},'cand')
        self.assertEqual(1,self.data['candidatures_web']['cand']['quiz']['essais'])
    async def test_succes_rejoue_une_seule_fois(self):
        token=self.formulaire('t','42')
        with patch.object(w,'noter',return_value=(1,1,[])), patch.object(w,'_places_livrables',AsyncMock(return_value=0)):
            a=await self.post_discord(token)
            b=await self.post_discord(token)
        self.assertEqual(a.text,b.text)
        self.assertEqual(1,self.callback.await_count)

class BotTentativeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import ast
        import logging
        import time
        self.data={}
        self.uid='123456789012345678'
        membre=SimpleNamespace(id=int(self.uid))
        def lire(f,d): return copy.deepcopy(self.data) if f=='pipe' else {}
        def ecrire(f,d): self.data=copy.deepcopy(d)
        self.ns=dict(time=time,re=re,datetime=datetime,timezone=timezone,
            lire_json=lire,ecrire_json=ecrire,FICHIER_PIPELINE='pipe',FICHIER_EQUIPES='equipes',
            canal_admin=AsyncMock(return_value=None),membre_par_id=lambda uid:membre,
            prenom_de=lambda m:'Fictif',ligne_quiz_bot=AsyncMock(),
            essais_quiz=lambda uid:self.data.get('etats',{}).get(uid,{}).get('essais_quiz',0),
            essais_quiz_cycle=lambda q:q.get('essais_quiz',0),normaliser=lambda x:x,
            client=SimpleNamespace(guilds=[SimpleNamespace(get_member=lambda uid:membre)]),
            journal=logging.getLogger('test-quiz'),SEUIL_QUIZ=30)
        arbre=ast.parse((Path(w.__file__).parent/'bot_discord.py').read_text())
        noms={'_MessageQuizWeb','traiter_quiz_web','traiter_quiz_webhook'}
        exec(compile(ast.Module(body=[n for n in arbre.body if getattr(n,'name',None) in noms],type_ignores=[]),'bot_quiz','exec'),self.ns)
    async def test_compteur_et_marque_persistes_ensemble(self):
        await self.ns['traiter_quiz_web'](self.uid,'0 / 1',False,tentative_id='fictive')
        snapshot=copy.deepcopy(self.data)
        # Simule l'éviction de l'ancienne liste bornée et la perte de réponse HTTP.
        self.data['quiz_traites']=[]
        await self.ns['traiter_quiz_web'](self.uid,'0 / 1',False,tentative_id='fictive')
        self.assertEqual(1,self.data['etats'][self.uid]['essais_quiz'])
        self.assertIn(f'web:{self.uid}:fictive',snapshot['quiz_web_traites'])
        self.ns['ligne_quiz_bot'].assert_awaited_once()
    async def test_interruption_avant_ecriture_ne_marque_pas_traite(self):
        ecrire=self.ns['ecrire_json']
        self.ns['ecrire_json']=lambda *a: (_ for _ in ()).throw(RuntimeError('disque fictif'))
        with self.assertRaises(RuntimeError):
            await self.ns['traiter_quiz_web'](self.uid,'0 / 1',False,tentative_id='fictive')
        self.assertFalse(self.data)
        self.ns['ecrire_json']=ecrire
        await self.ns['traiter_quiz_web'](self.uid,'0 / 1',False,tentative_id='fictive')
        self.assertEqual(1,self.data['etats'][self.uid]['essais_quiz'])
    async def test_nouvelle_tentative_compte_bien(self):
        for token in ('fictive1','fictive2'):
            await self.ns['traiter_quiz_web'](self.uid,'0 / 1',False,tentative_id=token)
        self.assertEqual(2,self.data['etats'][self.uid]['essais_quiz'])
    async def test_membre_absent_puis_present_meme_tentative(self):
        membre=SimpleNamespace(id=int(self.uid))
        guild=SimpleNamespace(get_member=lambda uid:None,members=[])
        self.ns['client']=SimpleNamespace(guilds=[guild])
        self.ns['valider_candidat']=AsyncMock(return_value='ok fictif')
        self.ns['_VALIDATIONS_EN_COURS']=set()
        premier=await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive')
        self.assertEqual('retryable',premier)
        self.assertNotIn(f'web:{self.uid}:fictive',self.data.get('quiz_web_traites',{}))
        self.ns['ligne_quiz_bot'].assert_not_awaited()
        guild.get_member=lambda uid:membre
        deuxieme=await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive')
        self.assertEqual('applied',deuxieme)
        self.assertEqual('already_done',await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive'))
        self.ns['valider_candidat'].assert_awaited_once()
    async def test_http_absent_puis_present_validation_une_fois(self):
        membre=SimpleNamespace(id=int(self.uid))
        guild=SimpleNamespace(get_member=lambda uid:None,members=[])
        self.ns['client']=SimpleNamespace(guilds=[guild])
        self.ns['valider_candidat']=AsyncMock(return_value='ok fictif')
        self.ns['_VALIDATIONS_EN_COURS']=set()
        deps=dict(lire_json=self.ns['lire_json'],ecrire_json=self.ns['ecrire_json'],FICHIER_PIPELINE='pipe',
                  essais_quiz=lambda uid:0,traiter_quiz_web=self.ns['traiter_quiz_web'])
        with patch.object(w,'_deps',deps),patch.object(w,'_quiz',return_value=QUIZ),patch.object(w,'quiz_seuil_total',return_value=(1,1)),patch.object(w,'jeton',side_effect=lambda x:x),patch.object(w,'verifier_jeton',side_effect=lambda x:x),patch.object(w,'noter',return_value=(1,1,[])) as noter,patch.object(w,'_places_livrables',AsyncMock(return_value=0)):
            form=w._formulaire_quiz(QUIZ,'t',self.uid,1)
            token=re.search("name='tentative' value='([^']+)'",form.text).group(1)
            request=SimpleNamespace(post=AsyncMock(return_value={'t':self.uid,'tentative':token}))
            a=await w.post_quiz(request)
            self.assertEqual(503,a.status)
            self.assertNotIn('Quizz réussi',a.text)
            self.assertFalse(self.data['quiz_tentatives_web']['t:'+self.uid].get('terminee'))
            self.assertNotIn(f'web:{self.uid}:{token}',self.data.get('quiz_web_traites',{}))
            guild.get_member=lambda uid:membre
            self.assertEqual(200,(await w.post_quiz(request)).status)
            self.assertEqual(200,(await w.post_quiz(request)).status)
            self.ns['valider_candidat'].assert_awaited_once()
            noter.assert_called_once()
    async def test_validation_partielle_reste_reessayable(self):
        self.ns['_VALIDATIONS_EN_COURS']=set()
        self.ns['valider_candidat']=AsyncMock(side_effect=['⚠️ panne fictive','ok fictif'])
        self.assertEqual('retryable',await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive'))
        self.assertNotIn(f'web:{self.uid}:fictive',self.data.get('quiz_web_traites',{}))
        self.assertEqual('applied',await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive'))
    async def test_validation_en_cours_ne_vaut_pas_deja_applique(self):
        self.ns['_VALIDATIONS_EN_COURS']={self.uid}
        self.ns['valider_candidat']=AsyncMock(return_value='deja')
        self.assertEqual('retryable',await self.ns['traiter_quiz_web'](self.uid,'1 / 1',True,tentative_id='fictive'))
        self.ns['valider_candidat'].assert_not_awaited()
        self.assertNotIn(f'web:{self.uid}:fictive',self.data.get('quiz_web_traites',{}))
