"""Menus avec discord.py réel si installé, sans client, token ou connexion réseau."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock

HAS_DISCORD = importlib.util.find_spec("discord") is not None


@unittest.skipUnless(HAS_DISCORD, "discord.py requis pour le contrôle du menu réel")
class MenuTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        spec = importlib.util.spec_from_file_location("codes_ui_test", Path(__file__).resolve().parents[1] / "codes_2fa.py")
        self.c = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.c)
        self.c.actif = lambda: True
        self.c._adresses_membre = lambda _: {"one@example.invalid"}
        self.c._servir = AsyncMock(return_value="code")
        self.c._demander_scan = lambda *_: None

    def interaction(self, uid=100):
        return types.SimpleNamespace(user=types.SimpleNamespace(id=uid),
            response=types.SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            edit_original_response=AsyncMock(), followup=types.SimpleNamespace(send=AsyncMock()))

    async def test_bouton_persistant_et_options_serialisables_sans_code(self):
        vue = self.c.vue_choix_code(100, {"one@example.invalid", "two@example.invalid"})
        donnees = vue.to_components()
        self.assertEqual(len(donnees), 2)
        self.assertEqual(len(donnees[0]["components"][0]["options"]), 3)
        self.assertEqual(len(donnees[1]["components"][0]["options"]), 2)
        self.assertTrue(self.c.vue_mon_code().is_persistent())
        self.assertNotIn("111111", str(donnees))
        vue.stop()

    async def test_choix_compte_et_usage_lancent_demande_privee(self):
        vue = self.c.vue_choix_code(100, {"one@example.invalid"})
        usage, adresse = vue.children
        usage._values = ["connexion"]
        adresse._values = ["one@example.invalid"]
        premier, second = self.interaction(), self.interaction()
        await usage.callback(premier)
        self.c._servir.assert_not_awaited()
        await adresse.callback(second)
        second.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.assertEqual(self.c._servir.call_args.args[0], {"one@example.invalid"})
        self.assertEqual(self.c._servir.call_args.kwargs["usage"], "connexion")

    async def test_autre_uid_ne_peut_pas_utiliser_menu(self):
        vue = self.c.vue_choix_code(100, {"one@example.invalid"})
        vue.children[0]._values = ["connexion"]
        i = self.interaction(200)
        await vue.children[0].callback(i)
        self.c._servir.assert_not_awaited()
        self.assertTrue(i.response.send_message.call_args.kwargs["ephemeral"])
        vue.stop()
