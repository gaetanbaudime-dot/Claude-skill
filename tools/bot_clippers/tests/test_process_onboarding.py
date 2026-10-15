"""Tests des vraies fonctions d'orchestration, avec Discord/Drive simulés."""
import ast
import __future__
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
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
        salon = SimpleNamespace(id=99, set_permissions=AsyncMock())
        onb = SimpleNamespace(lien_drive_creatrice=AsyncMock(return_value='https://example.invalid/drive'),
                              livrer=AsyncMock(return_value='1 compte(s)'))
        parcours = SimpleNamespace(demarrer_parcours=AsyncMock(), demarrer_selon_classeur=AsyncMock())
        ns = {'ancien_sans_salon': lambda m: False, 'parcours_a_demarrer': lambda uid: True,
              'equipes_tl': SimpleNamespace(tl_par_va=lambda: {'42': '90'}),
              'membre_par_id': lambda uid: SimpleNamespace(id=90), 'onboarding': onb,
              '_ONBOARDINGS_EN_COURS': set(), 'categorie_de_creatrice': lambda g, cr: None,
              'assurer_salon_perso': AsyncMock(return_value=(salon, False, '')),
              'prenom_distinct': lambda m, n: 'Fictif', 'normaliser': str.lower,
              'prenom_de': lambda m: 'Fictif', 'FICHIER_EQUIPES': 'equipes', 'FICHIER_PIPELINE': 'pipeline',
              'lire_json': lambda key, default: deepcopy(registre.get(key, default)),
              'ecrire_json': lambda key, val: registre.update({key: deepcopy(val)}),
              'datetime': datetime, 'timezone': timezone, 'attribution': SimpleNamespace(_sortir_d_attente=Mock()),
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
