"""Cas fictifs : sorties claires et réutilisation de la réponse privée, sans réseau."""
import ast
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]


def extraire(fichier, noms, ns):
    arbre = ast.parse((ROOT / fichier).read_text())
    fonctions = [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms]
    exec(compile(ast.Module(body=fonctions, type_ignores=[]), fichier, 'exec'), ns)
    return ns


class DecisionsTests(unittest.TestCase):
    def test_video_sans_note_ni_correction_contradictoire(self):
        f = extraire('review_reels.py', ['texte_avant'], {'TEXTE_ECHEC':'indisponible', 'RISQUES':{'mineur':'mineur apparent'}})['texte_avant']
        self.assertEqual(f({'note':8,'verdict':'publie','a_corriger':['autre idée']}), '✅ **Prête à publier.**')
        self.assertIn('Point bloquant : cadrage', f({'note':5,'verdict':'corrige','a_corriger':['cadrage','son']}))
        self.assertNotIn('son', f({'note':5,'verdict':'corrige','a_corriger':['cadrage','son']}))
        self.assertIn('Ne publie pas', f({'verdict':'risque','risque':'mineur'}))
        self.assertEqual('indisponible', f({'verdict':'corrige','a_corriger':[]}))

    def test_attente_ne_reclame_pas_whatsapp_et_ne_promet_pas_une_date(self):
        f=extraire('parcours.py',['attente_compte_1'],{})['attente_compte_1']
        self.assertEqual(f({}), f({'whatsapp':'historique'}))
        self.assertNotIn('heure',f({}))
        self.assertNotIn('WhatsApp',f({}))


class ReponseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import discord
        self.discord=discord
        self.ns=extraire('codes_2fa.py',['reponse_privee_unique'],{'asyncio':asyncio,'discord':discord,
                    '_reponses_privees':{},'_verrous_reponses':{}})
        self.f=self.ns['reponse_privee_unique']

    async def test_deux_appuis_meme_uid_editent_meme_message(self):
        premier,second,fermer=AsyncMock(),AsyncMock(),AsyncMock()
        await self.f(('fictif','ephemere'),premier)('attente')
        await self.f(('fictif','ephemere'),second,fermer)('nouveau résultat fictif')
        self.assertEqual(2,premier.await_count)
        second.assert_not_awaited();fermer.assert_awaited_once()

    async def test_utilisateurs_et_surfaces_isoles(self):
        a,b,c=AsyncMock(),AsyncMock(),AsyncMock()
        await self.f(('a','ephemere'),a)('A')
        await self.f(('b','ephemere'),b)('B')
        await self.f(('a','mp'),c)('C')
        a.assert_awaited_once_with('A');b.assert_awaited_once_with('B');c.assert_awaited_once_with('C')

    async def test_expiration_recree_prive_mais_erreur_ambigue_ne_duplique_pas(self):
        for statut in (404,503):
            self.ns['_reponses_privees'].clear()
            ancien,nouveau=AsyncMock(),AsyncMock()
            await self.f(('a','ephemere'),ancien)('attente')
            ancien.side_effect=self.discord.HTTPException(N(status=statut,reason='fictif'), 'fictif')
            if statut==404:
                await self.f(('a','ephemere'),nouveau)('résultat')
                nouveau.assert_awaited_once_with('résultat')
            else:
                with self.assertRaises(self.discord.HTTPException):
                    await self.f(('a','ephemere'),nouveau)('résultat')
                nouveau.assert_not_awaited()

    async def test_ecritures_concurrentes_serialisees(self):
        actif=0
        maximum=0
        async def livraison(t):
            nonlocal actif,maximum
            actif+=1;maximum=max(maximum,actif)
            await asyncio.sleep(0)
            actif-=1
        a=self.f(('a','ephemere'),livraison)
        b=self.f(('a','ephemere'),AsyncMock())
        await asyncio.gather(a('a'),b('b'))
        self.assertEqual(1,maximum)

class AccueilTests(unittest.IsolatedAsyncioTestCase):
    async def test_arrivee_rejouee_ne_renvoie_pas_un_deuxieme_accueil(self):
        from datetime import datetime,timezone,timedelta
        from copy import deepcopy
        etat={}
        def ecrire(d):
            etat.clear();etat.update(deepcopy(d))
        async def livraison(*args,**kw):
            etat['100'].setdefault('messages',{})['1']='compte1-fictif'
        ouvrir=AsyncMock(side_effect=livraison)
        ns={'_lire':lambda:deepcopy(etat),'_ecrire':ecrire,'_prenom':lambda m:'Fictif',
            '_cle_creatrice':str.lower,'_reprendre_trace':lambda *a:None,'PRIVE_EN_2':False,
            'datetime':datetime,'timezone':timezone,'timedelta':timedelta,'BIENVENUE_H':1,
            'ouvrir_compte_1':ouvrir,'_marque_simple':lambda:{'simple':'2026-10-24T00:00:00+00:00'}}
        f=extraire('parcours.py',['demarrer_parcours'],ns)['demarrer_parcours']
        salon=N(id=200,send=AsyncMock());membre=N(id=100)
        await f(salon,membre,'Fictive')
        await f(salon,membre,'Fictive')
        ouvrir.assert_awaited_once_with(salon,'100',par='bot')
        salon.send.assert_not_awaited()  # La bienvenue part uniquement avec l'étape 1.
        self.assertTrue(etat['100']['accueil_unique'])
        self.assertEqual('prive3',etat['100']['ordre'])
        self.assertTrue(etat['100']['simple'])  # 23/10 : un nouvel arrivant est au parcours simple (48 h, sans Reels)

    async def test_ancienne_trace_et_historique_ne_sont_pas_reinitialises(self):
        from copy import deepcopy
        etat={}
        def ecrire(d):etat.update(deepcopy(d))
        ns={'_lire':lambda:deepcopy(etat),'_ecrire':ecrire,'_prenom':lambda m:'Fictif',
            '_cle_creatrice':str.lower,'_reprendre_trace':lambda *a:{'message':'300','whatsapp':'ancienne preuve'},
            'PRIVE_EN_2':False,'_maintenant':lambda:'date fictive','ouvrir_compte_1':AsyncMock(),'_marque_simple':lambda:{}}
        f=extraire('parcours.py',['demarrer_parcours'],ns)['demarrer_parcours']
        await f(N(id=200),N(id=100),'Fictive')
        self.assertEqual('300',etat['100']['messages']['bienvenue'])
        self.assertEqual('ancienne preuve',etat['100']['whatsapp'])
        self.assertNotIn('accueil_unique',etat['100'])
