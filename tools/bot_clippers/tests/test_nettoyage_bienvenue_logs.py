"""Résultats du vrai nettoyage avec messages et erreurs Discord fictifs uniquement."""
import ast
import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, Mock

import discord


class NettoyageLogsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'parcours.py').read_text())
        names = {'_noter_nettoyage_bienvenue', '_retirer_pret'}
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        self.ns = {'discord': discord, 'asyncio': asyncio, 'journal': Mock(), '_NETTOYAGE_BIENVENUE_LOGS': {}}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'parcours.py', 'exec'), self.ns)
        self.nettoyer = self.ns['_retirer_pret']
        self.message = N(author=N(id=90), content='Bienvenue fictive', components=[], edit=AsyncMock())
        self.salon = N(id=10, guild=N(me=N(id=90)), fetch_message=AsyncMock(return_value=self.message))
        self.fiche = {'salon_id': '10', 'messages': {'bienvenue': '99'}}

    def resultats(self):
        return [c.args[3] for c in self.ns['journal'].info.call_args_list]

    def lignes(self):
        return [c.args[0] % c.args[1:] for c in self.ns['journal'].info.call_args_list]

    async def test_edition_confirmee_puis_conforme_sans_repetitions_ni_contenu(self):
        prefixe = 'Bienvenue SECRET-FICTIF https://example.invalid/private'
        self.message.content = prefixe + '\n\n👇 Ton compte 1 arrive juste en dessous.'
        self.message.components = ['ancien']
        avant = deepcopy(self.fiche)
        async def editer(**kwargs):
            self.assertEqual([], self.resultats())  # Aucun succès avant le retour de Discord.
            self.message.content = kwargs['content']
            self.message.components = []
        self.message.edit.side_effect = editer
        for _ in range(3):
            await self.nettoyer(self.salon, 'UID-SECRET', self.fiche)
        self.assertEqual(['nettoye', 'deja_conforme'], self.resultats())
        self.message.edit.assert_awaited_once_with(content=prefixe, view=None)
        self.assertEqual(3, self.salon.fetch_message.await_count)  # Pas de suppression des lectures existantes.
        self.assertIn('modification=texte_et_composants', self.lignes()[0])
        self.assertIn('salon=10 message=99', self.lignes()[0])
        self.assertEqual(avant, self.fiche)
        for secret in ('SECRET-FICTIF', 'UID-SECRET', 'https://'):
            self.assertNotIn(secret, '\n'.join(self.lignes()))

    async def test_retrait_composants_seuls_et_chaque_edition_confirmee_tracee(self):
        self.message.components = ['ancien']
        await self.nettoyer(self.salon, '42', self.fiche)
        await self.nettoyer(self.salon, '42', self.fiche)
        self.assertEqual(['nettoye', 'nettoye'], self.resultats())
        self.assertTrue(all('modification=composants' in ligne for ligne in self.lignes()))
        self.assertEqual(2, self.message.edit.await_count)

    async def test_refus_absence_erreurs_temporaires_et_http_permanent_distincts(self):
        reponse = lambda status: N(status=status, reason='DETAIL-SECRET')
        cas = [
            (discord.Forbidden(reponse(403), 'DETAIL-SECRET'), 'acces_refuse'),
            (discord.NotFound(reponse(404), {'code':10008, 'message':'DETAIL-SECRET'}), 'message_absent'),
            (discord.HTTPException(reponse(503), 'DETAIL-SECRET'), 'erreur_temporaire'),
            (discord.HTTPException(reponse(429), 'DETAIL-SECRET'), 'erreur_temporaire'),
            (TimeoutError('DETAIL-SECRET'), 'erreur_temporaire'),
            (OSError('DETAIL-SECRET'), 'erreur_temporaire'),
            (discord.HTTPException(reponse(400), 'DETAIL-SECRET'), 'erreur_http'),
            (ValueError('DETAIL-SECRET'), 'erreur_inattendue'),
        ]
        for i, (erreur, attendu) in enumerate(cas):
            with self.subTest(attendu=attendu, type=type(erreur).__name__):
                self.ns['journal'].reset_mock()
                self.fiche['messages']['bienvenue'] = str(100 + i)
                self.salon.fetch_message.side_effect = erreur
                await self.nettoyer(self.salon, '42', self.fiche)
                await self.nettoyer(self.salon, '42', self.fiche)
                self.assertEqual([attendu], self.resultats())
                self.assertIn('phase=lecture modification=aucune', self.lignes()[0])
                self.assertNotIn('DETAIL-SECRET', self.lignes()[0])
        self.message.edit.assert_not_awaited()

    async def test_echec_edition_ne_devient_pas_nettoyage_confirme_puis_reprise(self):
        self.message.content += '\n\n👇 Ton compte 1 arrive juste en dessous.'
        self.message.edit.side_effect = discord.HTTPException(N(status=503, reason='SECRET'), 'SECRET')
        for _ in range(2):
            await self.nettoyer(self.salon, '42', self.fiche)
        self.assertEqual(['erreur_temporaire'], self.resultats())
        self.assertIn('phase=edition modification=non_confirmee', self.lignes()[0])
        self.message.edit.side_effect = None
        await self.nettoyer(self.salon, '42', self.fiche)
        self.assertEqual(['erreur_temporaire', 'nettoye'], self.resultats())

    async def test_absence_ou_refus_durant_edition_jamais_presentes_comme_succes(self):
        self.message.content += '\n\n👇 Ton compte 1 arrive juste en dessous.'
        cas = [(discord.Forbidden, 403, 0, 'acces_refuse'), (discord.NotFound, 404, 10008, 'message_absent'),
               (discord.HTTPException, 400, 0, 'erreur_http')]
        for i, (type_erreur, status, code, attendu) in enumerate(cas):
            with self.subTest(status=status):
                self.ns['journal'].reset_mock()
                self.fiche['messages']['bienvenue'] = str(200 + i)
                self.message.edit.side_effect = type_erreur(N(status=status, reason='SECRET'), {'code':code, 'message':'SECRET'})
                await self.nettoyer(self.salon, '42', self.fiche)
                self.assertEqual([attendu], self.resultats())
                self.assertIn('phase=edition modification=non_confirmee', self.lignes()[0])
                self.assertNotIn('SECRET', self.lignes()[0])

    async def test_404_message_salon_et_ressource_inconnue_distincts_en_lecture_et_edition(self):
        cas = [(10008, 'message_absent'), (10003, 'salon_introuvable'),
               (10004, 'ressource_introuvable'), (None, 'ressource_introuvable'),
               ('10008', 'ressource_introuvable')]
        for p, phase in enumerate(('lecture', 'edition')):
            for i, (code, attendu) in enumerate(cas):
                with self.subTest(phase=phase, code=code):
                    self.ns['journal'].reset_mock()
                    self.salon.fetch_message.reset_mock(side_effect=True)
                    self.message.edit.reset_mock(side_effect=True)
                    self.fiche['messages']['bienvenue'] = str(300 + p * 100 + i)
                    self.message.content = 'Bienvenue\n\n👇 Ton compte 1 arrive juste en dessous.'
                    reponse = 'DETAIL-SECRET' if code is None else {'code':code, 'message':'DETAIL-SECRET'}
                    operation = self.salon.fetch_message if phase == 'lecture' else self.message.edit
                    operation.side_effect = discord.NotFound(N(status=404, reason='SECRET'), reponse)
                    for _ in range(2):
                        await self.nettoyer(self.salon, '42', self.fiche)
                    self.assertEqual([attendu], self.resultats())
                    self.assertIn('phase=' + phase, self.lignes()[0])
                    self.assertNotIn('SECRET', self.lignes()[0])
                    if phase == 'lecture':
                        self.message.edit.assert_not_awaited()

    async def annuler_pendant(self, operation, effet=None):
        entre = asyncio.Event()
        async def suspendre(*args, **kwargs):
            if effet:
                effet(*args, **kwargs)
            entre.set()
            await asyncio.Event().wait()
        operation.side_effect = suspendre
        tache = asyncio.create_task(self.nettoyer(self.salon, '42', self.fiche))
        try:
            await asyncio.wait_for(entre.wait(), 1)
        finally:
            tache.cancel('ANNULATION-SECRET')
        with self.assertRaises(asyncio.CancelledError):
            await tache
        self.assertTrue(tache.cancelled())
        self.assertEqual(['interrompu'], self.resultats())
        self.assertNotIn('SECRET', '\n'.join(self.lignes()))

    async def test_annulation_lecture_propagee_sans_edition_ni_faux_succes(self):
        avant = deepcopy(self.fiche)
        await self.annuler_pendant(self.salon.fetch_message)
        self.salon.fetch_message.assert_awaited_once_with(99)
        self.message.edit.assert_not_awaited()
        self.assertIn('phase=lecture modification=aucune', self.lignes()[0])
        self.assertEqual(avant, self.fiche)

    async def test_annulation_edition_issue_inconnue_sans_relance(self):
        self.message.content += '\n\n👇 Ton compte 1 arrive juste en dessous.'
        avant = deepcopy(self.fiche)
        await self.annuler_pendant(self.message.edit)
        self.salon.fetch_message.assert_awaited_once_with(99)
        self.message.edit.assert_awaited_once_with(content='Bienvenue fictive', view=None)
        self.assertIn('phase=edition modification=inconnue', self.lignes()[0])
        self.assertEqual(avant, self.fiche)

    async def test_edition_appliquee_avant_annulation_reprise_relit_sans_seconde_edition(self):
        self.message.content += '\n\n👇 Ton compte 1 arrive juste en dessous.'
        distant = {}
        def appliquer(**kwargs):
            distant['contenu'] = kwargs['content']  # Serveur changé, réponse encore attendue.
        await self.annuler_pendant(self.message.edit, appliquer)
        self.assertIn('phase=edition modification=inconnue', self.lignes()[0])
        self.message.edit.assert_awaited_once()
        self.salon.fetch_message.assert_awaited_once_with(99)
        # Une invocation ultérieure utilise une nouvelle lecture, jamais l'ancien
        # objet conservé par le client après l'annulation.
        frais = N(author=N(id=90), content=distant['contenu'], components=[], edit=AsyncMock())
        self.salon.fetch_message.return_value = frais
        await self.nettoyer(self.salon, '42', self.fiche)
        self.assertEqual(2, self.salon.fetch_message.await_count)
        self.assertEqual(['interrompu', 'deja_conforme'], self.resultats())
        self.message.edit.assert_awaited_once()
        frais.edit.assert_not_awaited()

    async def test_humain_absence_id_et_salon_indisponible_nelargissent_pas_le_perimetre(self):
        for fiche in ({}, {'messages': {'bienvenue': 'invalide'}}):
            await self.nettoyer(self.salon, '42', fiche)
        self.salon.fetch_message.assert_not_awaited()
        self.assertEqual([], self.resultats())
        self.message.author.id = 91
        for _ in range(2):
            await self.nettoyer(self.salon, '42', self.fiche)
        self.assertEqual(['auteur_hors_perimetre'], self.resultats())
        self.message.edit.assert_not_awaited()
        for _ in range(2):
            await self.nettoyer(None, '42', self.fiche)
        self.assertEqual(['auteur_hors_perimetre', 'salon_indisponible'], self.resultats())

    def test_memoire_bornee_et_identifiants_non_numeriques_non_journalises(self):
        noter = self.ns['_noter_nettoyage_bienvenue']
        noter('SALON-SECRET', 'MESSAGE-SECRET', 'salon_indisponible', 'lecture', code_http='SECRET')
        self.assertIn('salon=inconnu message=inconnu', self.lignes()[0])
        self.assertNotIn('SECRET', self.lignes()[0])
        for i in range(2050):
            noter(10, i + 1, 'deja_conforme', 'lecture')
        self.assertEqual(2048, len(self.ns['_NETTOYAGE_BIENVENUE_LOGS']))
