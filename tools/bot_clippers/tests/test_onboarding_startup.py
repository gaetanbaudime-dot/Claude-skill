"""Course de démarrage reproduite avec le dispatch réel et un SQLite temporaire."""
import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import choix_creatrice
import onboarding
import process_adapters
from process_store import Bloque


def fonctions(namespace):
    noms = {'brancher_onboarding', 'setup_hook', 'on_ready', 'on_message', 'commande_creatrice', 'onboarder_membre'}
    arbre = ast.parse((ROOT / 'bot_discord.py').read_text())
    corps = [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms]
    for n in corps:
        n.decorator_list = []
    exec(compile(ast.Module(body=corps, type_ignores=[]), 'demarrage-reel', 'exec'), namespace)
    return namespace


class DemarrageTests(unittest.IsolatedAsyncioTestCase):
    def environnement(self, root):
        membre = N(id=42, display_name='Membre fictif', bot=False)
        auteur = N(id=99, display_name='Admin fictif', bot=False)
        guild = N(id=1)
        message = N(id=12, content='!creatrice <@42> Sarah', webhook_id=None,
                    author=auteur, guild=guild, channel=N(id=10), reply=AsyncMock())
        pipe = root / 'pipeline.json'
        equipes = root / 'equipes.json'
        def lire(path, defaut):
            if path == pipe:
                return {'etats': {'42': {'score_quiz': 8, 'etat': 'quiz_ok'}}}
            if path == equipes:
                return {'42': {'creatrice': 'Sarah'}}
            return defaut
        deps = dict(onboarding=onboarding, lire_json=Mock(side_effect=lire), ecrire_json=Mock(),
            FICHIER_ONBOARDING=root / 'onboarding.json', FICHIER_EQUIPES=equipes,
            FICHIER_PIPELINE=pipe, FICHIER_CLICS=root / 'clics.json', normaliser=str.lower,
            heure_paris=Mock(), canal_admin=AsyncMock(), salon_perso_de=Mock(), membre_par_prenom=Mock(),
            membre_par_id=Mock(), envoyer_long=AsyncMock(), brancher_codes=Mock(),
            client=N(user='bot fictif'), MODELE='fictif', ADMIN_IDS={'99'}, CANAL_BOT_ID='', ACTIVER_V2=True,
            journal=Mock(), _taches_demarrees=False, _ONBOARDINGS_EN_COURS=set(),
            filtrer_spam=AsyncMock(return_value=False), nettoyer=lambda m: m.content,
            normaliser_commande=lambda t: t, appel=N(noter_activite=Mock()), en_prive=lambda _: False,
            est_staff=lambda m: m.id == 99, est_manager=lambda m: m.id == 99,
            codes_2fa=N(COMMANDES_RECUP=(), COMMANDES_AIDE=(), demande_de_code=lambda _: ''),
            categorie_de_creatrice=lambda *_: None, role_creatrice=lambda *_: None,
            roster=N(groupes=lambda: {'Sarah': []}), attribution=N(ORDRE=['Sarah']),
            chercher_membre=lambda mot, **_: membre if mot == '<@42>' else None,
            datetime=datetime, timezone=timezone)
        return fonctions(deps), message

    async def test_configuration_avant_passerelle_sans_lecture_ni_ecriture(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(onboarding, '_deps', {}):
            root = Path(tmp)
            ns, _ = self.environnement(root)
            await ns['setup_hook']()
            self.assertEqual(root / 'onboarding.json', onboarding._deps['FICHIER_ONBOARDING'])
            ns['lire_json'].assert_not_called()
            ns['ecrire_json'].assert_not_called()
            self.assertEqual([], list(root.iterdir()))

    async def test_creatrice_durant_premier_await_on_ready_atteint_counts_sans_keyerror(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(onboarding, '_deps', {}):
            root = Path(tmp)
            ns, message = self.environnement(root)
            entre, attente = asyncio.Event(), asyncio.Event()
            async def premier_await():
                entre.set()
                await attente.wait()
            ns['verifier_canaux_configures'] = premier_await
            await ns['setup_hook']()
            lancement = asyncio.create_task(ns['on_ready']())
            try:
                await asyncio.wait_for(entre.wait(), 1)
                # Coupe le test APRÈS l'accès counts fautif en production, avant toute attribution.
                with patch.object(choix_creatrice, 'preparer', side_effect=choix_creatrice.Divergence('fin de test')) as preparer:
                    await ns['on_message'](message)
                preparer.assert_called_once()
                self.assertEqual('42', preparer.call_args.args[0])
                self.assertIsInstance(preparer.call_args.kwargs['comptes_connus'], dict)
                self.assertTrue((root / 'process_clippeur.sqlite3').is_file())
                self.assertIn('Choix retenu : fin de test', message.reply.await_args.args[0])
                ns['ecrire_json'].assert_not_called()
            finally:
                lancement.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await lancement

    async def test_sans_configuration_refus_explicite_et_aucun_store_cree(self):
        with patch.object(onboarding, '_deps', {}), patch.object(process_adapters, 'Store') as store:
            with self.assertRaisesRegex(Bloque, 'Onboarding non initialisé'):
                process_adapters.store()
            store.assert_not_called()

    async def test_dispatch_sans_droit_ne_touche_pas_au_stockage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(onboarding, '_deps', {}):
            ns, message = self.environnement(Path(tmp))
            message.author.id = 88
            await ns['setup_hook']()
            with patch.object(process_adapters, 'store') as store:
                await ns['on_message'](message)
                store.assert_not_called()
            self.assertIn('réservée aux managers', message.reply.await_args.args[0])
            self.assertEqual([], list(Path(tmp).iterdir()))


if __name__ == '__main__':
    unittest.main()
