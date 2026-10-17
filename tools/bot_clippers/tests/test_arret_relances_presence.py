"""Arrêt ciblé des relances ; données fictives, aucun appel Discord réel."""
import ast
import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import appel


class ArretRelances(unittest.IsolatedAsyncioTestCase):
    def test_desactive_par_defaut(self):
        arbre = ast.parse(Path(appel.__file__).read_text())
        valeur = next(n.value for n in arbre.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'RELANCES_ACTIVES' for t in n.targets))
        for environnement in ({}, {'APPEL': '1'}, {'APPEL_RELANCES': '0'}):
            import os
            with patch.dict(os.environ, environnement, clear=True):
                self.assertFalse(eval(compile(ast.Expression(valeur), '<test>', 'eval'), {'os': os}))

    async def test_aucun_appel_ni_bouton_ni_ecriture(self):
        salon = SimpleNamespace(send=AsyncMock())
        deps = {'lire_json': Mock(), 'ecrire_json': Mock(), 'salons_clippers': AsyncMock(),
                'lien_whatsapp': Mock(), 'bouton_wa': Mock()}
        with patch.object(appel, 'RELANCES_ACTIVES', False), patch.object(appel, '_deps', deps):
            self.assertEqual([], await appel.lancer_appel([(salon, object())], 'test'))
            self.assertEqual([], await appel.appel_general(None))
            self.assertIsNone(appel._vue('fictif'))
            for valeur in deps.values():
                valeur.assert_not_called()
        salon.send.assert_not_awaited()

    async def test_reponse_conservee_sans_relance_wa(self):
        now = datetime.now(timezone.utc)
        ancien = (now - timedelta(days=4)).isoformat()
        etat = {'appels': {'fictif': {'date': ancien, 'repondu': ancien, 'prenom': 'Test'}},
                'activite': {}, 'general': {}}
        avant = copy.deepcopy(etat)
        deps = {'lire_json': Mock(return_value=etat), 'FICHIER': 'fictif', 'ecrire_json': Mock(),
                'salons_clippers': AsyncMock()}
        client = SimpleNamespace(get_channel=Mock())
        with patch.object(appel, 'RELANCES_ACTIVES', False), patch.object(appel, '_deps', deps):
            self.assertEqual([], appel.a_relancer_wa(etat, {}, now))
            self.assertEqual([], await appel.executer(client, maintenant=now))
        self.assertEqual(avant, etat)
        deps['ecrire_json'].assert_not_called()
        deps['salons_clippers'].assert_not_awaited()
        client.get_channel.assert_not_called()

    async def test_demarrage_sans_annonce_conserve_boucle_existante(self):
        client = SimpleNamespace(wait_until_ready=AsyncMock(), is_closed=Mock(side_effect=[False, True]))
        canal = SimpleNamespace(send=AsyncMock())
        with patch.object(appel, 'RELANCES_ACTIVES', False), patch.object(appel, 'ACTIF', True), \
             patch.object(appel, 'GENERAL', True), patch.object(appel, 'PURGE', True), \
             patch.object(appel, '_deps', {'canal_admin': AsyncMock(return_value=canal)}), \
             patch.object(appel, 'appel_general', AsyncMock()) as general, \
             patch.object(appel, 'purger', AsyncMock(return_value=[])) as purge, \
             patch.object(appel, 'executer', AsyncMock(return_value=[])) as passage, \
             patch.object(appel.asyncio, 'sleep', AsyncMock()):
            await appel.boucle(client)
        general.assert_not_awaited()
        purge.assert_awaited_once_with(client, appliquer=True)
        passage.assert_awaited_once_with(client, appliquer=True)
        canal.send.assert_not_awaited()
