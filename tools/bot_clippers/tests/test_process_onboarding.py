"""Tests des vraies fonctions d'orchestration, avec Discord/Drive simulés."""
import ast
import __future__
import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import discord
import onboarding_preuves
import process_adapters
from process_store import Store


def charger(nom, ns, fichier='bot_discord.py'):
    tree = ast.parse((ROOT/fichier).read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom)
    exec(compile(ast.Module(body=[node], type_ignores=[]), fichier, 'exec', flags=__future__.annotations.compiler_flag), ns)
    return ns[nom]


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'process.sqlite3')
        self.store.reconcile('42', [], 'revue-fictive')
        self.patch = patch.object(process_adapters, 'store', return_value=self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_salon_unique_apres_timeout_et_changement_de_pseudo(self):
        channels = []
        guild = SimpleNamespace(fetch_channels=AsyncMock(side_effect=lambda: list(channels)))
        membre = SimpleNamespace(id=42, display_name='Fictif')
        async def creer(*args):
            channels.append(SimpleNamespace(id=99, topic='clipper-uid:42 · Fictif'))
            raise TimeoutError('réponse Discord perdue')
        creation = AsyncMock(side_effect=creer)
        fn = charger('assurer_salon_perso', {'_assurer_salon_perso': creation})
        with self.assertRaises(TimeoutError): await fn(guild, membre, None, 'Fictive', 'test')
        membre.display_name = 'NouveauPseudo'
        salon, cree, erreur = await fn(guild, membre, None, 'Fictive', 'test')
        self.assertEqual(99, salon.id)
        self.assertFalse(cree)
        self.assertEqual(1, creation.await_count)

    async def test_salon_incertain_non_visible_ne_declenche_pas_un_second_post(self):
        guild = SimpleNamespace(fetch_channels=AsyncMock(return_value=[]))
        fn = charger('assurer_salon_perso', {'_assurer_salon_perso': AsyncMock(side_effect=TimeoutError())})
        membre = SimpleNamespace(id=42)
        with self.assertRaises(TimeoutError): await fn(guild, membre, None, 'Fictive', 'test')
        salon, _, erreur = await fn(guild, membre, None, 'Fictive', 'test')
        self.assertIsNone(salon)
        self.assertIn('incertaine', erreur)

    def contexte(self):
        registre = {'pipeline': {'etats': {'42': {'etat': 'valide', 'score_quiz': '10 / 10'}}}, 'equipes': {}}
        role = SimpleNamespace(name='Fictive')
        membre = SimpleNamespace(id=42, display_name='Fictif - Fictive', roles=[SimpleNamespace(name='Clippeur')],
                                 edit=AsyncMock(), add_roles=AsyncMock())
        salon = SimpleNamespace(id=99, set_permissions=AsyncMock(), permissions_for=lambda tl:SimpleNamespace(view_channel=True,read_message_history=True))
        onb = SimpleNamespace(lien_drive_creatrice=AsyncMock(return_value='https://example.invalid/drive'),
                              livrer=AsyncMock(return_value='1 compte(s)'))
        parcours = SimpleNamespace(demarrer_parcours=AsyncMock(), demarrer_selon_classeur=AsyncMock(), _lire=lambda:{"42":{"messages":{"1":"fictif"}}})
        ns = {'onboarding_preuves':onboarding_preuves,'FICHIER_ONBOARDING':'onboarding','FICHIER_PARCOURS':'parcours','FICHIER_SORTIS':'sortis','DONNEES':Path(self.tmp.name),'ancien_sans_salon': lambda m: False, 'parcours_a_demarrer': lambda uid: True,
              'equipes_tl': SimpleNamespace(tl_par_va=lambda: {'42': '90'}),
              'membre_par_id': lambda uid: SimpleNamespace(id=90), 'onboarding': onb,
              '_ONBOARDINGS_EN_COURS': set(), 'categorie_de_creatrice': lambda g, cr: None,
              'assurer_salon_perso': AsyncMock(return_value=(salon, False, '')),
              'prenom_distinct': lambda m, n: 'Fictif', 'normaliser': str.lower,
              'prenom_de': lambda m: 'Fictif', 'FICHIER_EQUIPES': 'equipes', 'FICHIER_PIPELINE': 'pipeline',
              'lire_json': lambda key, default: deepcopy(registre.get(key, default)),
              'ecrire_json': lambda key, val: registre.update({key: deepcopy(val)}),
              'datetime': datetime, 'timezone': timezone, 'attribution': SimpleNamespace(_sortir_d_attente=Mock(), conserver_attente=Mock()),
              'NOMS_RANGS': ['Clippeur'], 'role_creatrice': lambda g, cr: role,
              'roster': SimpleNamespace(ajouter=Mock()), 'discord': discord, 'parcours': parcours,
              'journal': logging.getLogger('test')}
        return ns, membre, salon, registre

    async def test_role_refuse_ne_livre_rien_puis_reprise(self):
        ns, membre, salon, registre = self.contexte()
        membre.add_roles.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='fictif'), 'refus fictif')
        fn = charger('onboarder_membre', ns)
        resultat = await fn(SimpleNamespace(), membre, 'Fictive', None, {}, [])
        self.assertIn('refusé', resultat)
        ns['onboarding'].livrer.assert_not_awaited()
        ns['parcours'].demarrer_parcours.assert_not_awaited()
        membre.add_roles.side_effect = None
        await fn(SimpleNamespace(), membre, 'Fictive', None, {}, [])
        ns['onboarding'].livrer.assert_awaited_once()
        ns['parcours'].demarrer_parcours.assert_awaited_once()
        self.assertEqual('99', registre['equipes']['42']['salon_id'])
        salon.set_permissions.assert_awaited()

    async def test_drive_tl_quiz_manquants_bloquent_avant_droits(self):
        for manque in ('drive', 'tl', 'quiz'):
            ns, membre, salon, registre = self.contexte()
            if manque == 'drive': ns['onboarding'].lien_drive_creatrice.return_value = ''
            if manque == 'tl': ns['equipes_tl'].tl_par_va = lambda: {}
            if manque == 'quiz': registre['pipeline']['etats']['42'].pop('score_quiz')
            fn = charger('onboarder_membre', ns)
            await fn(SimpleNamespace(), membre, 'Fictive', None, {}, [])
            ns['assurer_salon_perso'].assert_not_awaited()
            membre.add_roles.assert_not_awaited()
            ns['onboarding'].livrer.assert_not_awaited()

    def test_message_compte_sans_secret(self):
        fn = charger('_identifiants', {}, fichier='parcours.py')
        texte = fn(1)
        self.assertNotIn('mdp', texte)
        self.assertNotIn('mail', texte)
        self.assertIn('responsable', texte)

    async def test_historique_salon_non_partage_nouvre_pas_les_acces(self):
        ns,membre,salon,_=self.contexte()
        salon.permissions_for=lambda tl:SimpleNamespace(view_channel=False,read_message_history=False)
        fn=charger('onboarder_membre',ns)
        resultat=await fn(SimpleNamespace(),membre,'Fictive',None,{},[])
        self.assertIn('historique',resultat)
        salon.set_permissions.assert_not_awaited()
        ns['onboarding'].livrer.assert_not_awaited()

    async def test_double_evenement_ne_double_pas_la_livraison(self):
        ns,membre,salon,_=self.contexte()
        entre,sortie=asyncio.Event(),asyncio.Event()
        async def drive(*args):
            entre.set();await sortie.wait();return 'https://example.invalid/drive'
        ns['onboarding'].lien_drive_creatrice.side_effect=drive
        fn=charger('onboarder_membre',ns)
        un=asyncio.create_task(fn(SimpleNamespace(),membre,'Fictive',None,{},[]))
        await entre.wait()
        deux=await fn(SimpleNamespace(),membre,'Fictive',None,{},[])
        self.assertIn('déjà en cours',deux)
        sortie.set();await un
        ns['onboarding'].livrer.assert_awaited_once()

    async def test_absence_message_compte_garde_attente(self):
        ns,membre,salon,_=self.contexte()
        ns['parcours']._lire=lambda:{}
        fn=charger('onboarder_membre',ns)
        resultat=await fn(SimpleNamespace(),membre,'Fictive',None,{},[])
        self.assertIn('non livré',resultat)
        ns['attribution']._sortir_d_attente.assert_not_called()

    async def test_bouton_obsolete_retire_meme_pret_retire(self):
        msg=SimpleNamespace(author=SimpleNamespace(id=90),components=['ancien'],edit=AsyncMock())
        salon=SimpleNamespace(guild=SimpleNamespace(me=SimpleNamespace(id=90)),fetch_message=AsyncMock(return_value=msg))
        fn=charger('_retirer_pret',{'discord':discord,'journal':logging.getLogger('test')},'parcours.py')
        await fn(salon,'42',{'pret_retire':True,'messages':{'bienvenue':'99'}})
        msg.edit.assert_awaited_once_with(view=None)
        msg.edit.reset_mock();msg.author.id=91
        await fn(salon,'42',{'messages':{'bienvenue':'99'}})
        msg.edit.assert_not_awaited()


    async def test_erreur_livraison_garde_attente_meme_avec_ancien_message(self):
        ns,membre,salon,_=self.contexte()
        ns['onboarding'].livrer.side_effect=TimeoutError('fictif')
        fn=charger('onboarder_membre',ns)
        resultat=await fn(SimpleNamespace(),membre,'Fictive',None,{},[])
        self.assertIn('reprise conservée',resultat)
        ns['attribution']._sortir_d_attente.assert_not_called()
        ns['parcours'].demarrer_parcours.assert_not_awaited()


    async def test_arrivee_site_salon_vide_existant_tl_puis_compte1(self):
        import recrutement_suivi
        ns,membre,salon,registre=self.contexte()
        now=datetime.now(timezone.utc)
        registre['pipeline']={'candidatures_web':{'cand-fictif':{
            'date':(now-timedelta(minutes=5)).isoformat(),
            'quiz':{'reussi':True,'score':'9 / 10','date':(now-timedelta(minutes=1)).isoformat()}}}}
        registre.update(onboarding={},parcours={},sortis=[])
        registre[Path(self.tmp.name)/'parcours_oublis.json']={}
        channels=[]
        guild=SimpleNamespace(me=SimpleNamespace(id=91),fetch_channels=AsyncMock(side_effect=lambda:list(channels)))
        membre.guild=guild
        salon.guild=guild;salon.topic='clipper-uid:42'
        ouvert=False
        def permissions(m):
            return SimpleNamespace(view_channel=m.id==91 or ouvert,read_message_history=m.id==91 or ouvert)
        salon.permissions_for=permissions
        async def vide(**kw):
            if False:yield None
        salon.history=vide
        async def ouvrir(*args,**kw):
            nonlocal ouvert
            ouvert=True
        salon.set_permissions.side_effect=ouvrir
        async def creer(*args):
            channels.append(salon)
            return salon,True,''
        ns.update(_assurer_salon_perso=AsyncMock(side_effect=creer),SALON_ARRIVEE=True,ADMIN_IDS=set(),
                  est_manager=lambda m:False,sortie_d_un_ancien=lambda uid:None,ETATS_REMIS_A_ZERO=set(),
                  traiter_liaison=AsyncMock(),recrutement_suivi=recrutement_suivi,
                  canal_admin=AsyncMock(return_value=None),_MessageQuizWeb=lambda content,canal:SimpleNamespace(content=content))
        for nom in ('assurer_salon_perso','assurer_salon_arrivee','preparer_arrivee_site','suite_arrivee_site','onboarder_membre','accueillir_site'):
            charger(nom,ns)
        async def quiz(message):
            return await ns['onboarder_membre'](guild,membre,'Fictive',None,{},[])
        ns['traiter_quiz_webhook']=AsyncMock(side_effect=quiz)
        import parcours as reel
        ns['parcours']=reel
        membre.mention='<@42>'
        salon.send=AsyncMock(return_value=SimpleNamespace(id=123))
        etat_parcours={}
        def ecrire_parcours(d):
            etat_parcours.clear();etat_parcours.update(deepcopy(d))
        neuf=Store(Path(self.tmp.name)/'neuf.sqlite3')
        with patch.object(process_adapters,'store',return_value=neuf), \
             patch.object(reel.process_clippeur,'pseudo_disponible',return_value=True), \
             patch.dict(reel.onboarding._deps,{'FICHIER_ONBOARDING':Path(self.tmp.name)/'onboarding.json','lire_json':lambda *a:{}}), \
             patch.multiple(reel,_lire=lambda:deepcopy(etat_parcours),_ecrire=ecrire_parcours,
                 _deps={'membre_par_id':lambda uid:membre},_reprendre_trace=lambda *a:None,
                 _ligne_du_compte=AsyncMock(return_value=True),_comptes_ordonnes=lambda *a,**kw:['compte-fictif'],
                 _contexte=AsyncMock(return_value={'prenom':'Fictif','creatrice':'Fictive'}),
                 _rendre=lambda texte,ctx:texte,_vue=lambda *a:None,_retirer_pret=AsyncMock()):
            await ns['accueillir_site'](membre,'inv-fictive',{'cand':'cand-fictif','prenom':'Fictif'},None)
            self.assertTrue(ouvert)
            self.assertEqual(len(channels),1)
            ns['_assurer_salon_perso'].assert_awaited_once()
            salon.set_permissions.assert_awaited_once()
            ns['onboarding'].livrer.assert_awaited_once()
            self.assertEqual('123',etat_parcours['42']['messages']['1'])
            salon.send.assert_awaited_once()
            self.assertFalse(neuf.initialiser_nouveau('42',None))
            self.assertEqual(ns['assurer_salon_perso'].__name__,'assurer_salon_perso')

    async def test_reprise_apres_permission_tl_verifiee_hors_du_bot(self):
        ns,membre,salon,_=self.contexte()
        salon.permissions_for=lambda tl:SimpleNamespace(view_channel=False,read_message_history=False)
        fn=charger('onboarder_membre',ns)
        self.assertIn('historique',await fn(SimpleNamespace(),membre,'Fictive',None,{},[]))
        ns['onboarding'].livrer.assert_not_awaited()
        salon.permissions_for=lambda tl:SimpleNamespace(view_channel=True,read_message_history=True)
        await fn(SimpleNamespace(),membre,'Fictive',None,{},[])
        ns['onboarding'].livrer.assert_awaited_once()


class RepriseAttributionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reprises_selectionnees_sans_stock_et_blocage_individuel(self):
        etats = {u: {'etat':'attente_attribution', **({'creatrice_attendue':'Fictive'} if u != '30' else {})}
                 for u in ('10','20','30')}
        membres = {u:SimpleNamespace(id=int(u),guild=None) for u in etats}
        attribution = AsyncMock(side_effect=['', 'Fictive'])
        valider = AsyncMock()
        lock = asyncio.Lock()
        ns = {'actif':lambda:True,'_verrou':lambda cle:lock,'en_attente':lambda:list(etats.items()),
              '_deps':{'membre_par_id':membres.get,'est_staff':lambda m:False,
                       'lire_json':lambda fichier,defaut:{'etats':etats} if fichier == 'pipeline' else {},
                       'FICHIER_EQUIPES':'equipes','prenom_de':lambda m:str(m.id),'valider_candidat':valider},
              '_repris_possible':lambda u,i:membres[u], 'stock_livrable':AsyncMock(return_value={}),
              'ETAT_ATTENTE':'attente_attribution','ORDRE':['Fictive'],'_existe':lambda g,c:True,'_stock_de':lambda s,c:0,
              'creatrice_en_attente':lambda u:etats[u].get('creatrice_attendue'),
              '_fichier_pipeline':lambda:'pipeline','sans_creatrice':lambda m:False,
              '_noter_essai':Mock(),'attribuer':attribution,'asyncio':asyncio,'PAUSE_SEC':0,
              'journal':logging.getLogger('test')}
        fn = charger('reprendre_attente',ns,'attribution.py')
        self.assertEqual(await fn(), [('20','Fictive')])
        self.assertEqual([a.args[0].id for a in attribution.await_args_list], [10,20])
        valider.assert_not_awaited()
