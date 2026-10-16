"""Menus avec discord.py réel si installé, sans client, token ou connexion réseau."""
import importlib.util
from pathlib import Path
import re
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

    async def test_panneau_public_persistant_sans_code_ni_compte(self):
        vue = self.c.vue_mon_code()
        donnees = vue.to_components()
        self.assertEqual(len(donnees), 1)
        self.assertEqual(len(donnees[0]["components"]), 1)
        self.assertTrue(vue.is_persistent())
        self.assertNotIn("111111", str(donnees))
        self.assertNotIn("example.invalid", str(donnees))
        self.assertEqual([b["custom_id"] for b in donnees[0]["components"]],
                         ["codes:mon-code"])
        vue.stop()

    async def test_un_clic_repond_directement_si_compte_unique(self):
        vue = self.c.vue_mon_code()
        i = self.interaction()
        await vue.children[0].callback(i)
        i.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.assertEqual(self.c._servir.call_args.args[0], {"one@example.invalid"})
        self.assertEqual(self.c._servir.call_args.kwargs["usage"], "auto")
        vue.stop()

    async def test_plusieurs_comptes_menu_prive_puis_un_choix(self):
        self.c._adresses_membre = lambda _: {"one@example.invalid", "two@example.invalid"}
        i = self.interaction()
        await self.c.BoutonUsageCode("connexion").callback(i)
        i.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.c._servir.assert_not_awaited()
        vue = i.edit_original_response.call_args.kwargs["view"]
        self.assertEqual(len(vue.children), 1)
        self.assertEqual(len(vue.to_components()[0]["components"][0]["options"]), 2)
        vue.children[0]._values = ["two@example.invalid"]
        second = self.interaction()
        await vue.children[0].callback(second)
        second.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.assertEqual(self.c._servir.call_args.args[0], {"two@example.invalid"})
        self.assertEqual(self.c._servir.call_args.kwargs["usage"], "connexion")
        vue.stop()

    async def test_autre_uid_ne_peut_pas_utiliser_menu_de_compte(self):
        vue = self.c.vue_choix_code(100, {"one@example.invalid"}, usage="connexion")
        vue.children[0]._values = ["one@example.invalid"]
        i = self.interaction(200)
        await vue.children[0].callback(i)
        self.c._servir.assert_not_awaited()
        self.assertTrue(i.response.send_message.call_args.kwargs["ephemeral"])
        vue.stop()

    async def test_bouton_commun_resout_les_comptes_de_celui_qui_clique(self):
        self.c._adresses_membre = lambda m: {f"user{m.id}@example.invalid"}
        i = self.interaction(200)
        await self.c.BoutonUsageCode("creation").callback(i)
        self.assertEqual(self.c._servir.call_args.args[0], {"user200@example.invalid"})
        self.assertEqual(self.c._servir.call_args.args[2], "u|200")

    async def test_reconstruction_apres_redemarrage(self):
        match = re.fullmatch(r"codes:usage:(?P<usage>creation|connexion|verification)", "codes:usage:connexion")
        bouton = await self.c.BoutonUsageCode.from_custom_id(None, None, match)
        self.assertEqual(bouton.usage, "connexion")
        i = self.interaction()
        await bouton.callback(i)
        self.c._servir.assert_awaited_once()

    async def test_bouton_unique_plusieurs_comptes_sans_menu(self):
        self.c._adresses_membre = lambda _: {"one@example.invalid", "two@example.invalid"}
        i = self.interaction()
        await self.c.BoutonMonCode().callback(i)
        i.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.assertEqual(self.c._servir.call_args.args[0], {"one@example.invalid", "two@example.invalid"})
        self.assertEqual(self.c._servir.call_args.kwargs["usage"], "auto")
        i.edit_original_response.assert_not_awaited()  # La restitution vient du guet, pas d'un menu.

    async def test_expiration_apres_reutilisation_et_suppression_du_nouvel_accuse(self):
        import discord
        premier,second=self.interaction(),self.interaction()
        second.delete_original_response=AsyncMock()
        secours=types.SimpleNamespace(edit=AsyncMock())
        second.followup.send=AsyncMock(return_value=secours)
        await self.c.servir_interaction(premier)
        dire1=self.c._servir.call_args.args[1]
        await dire1('attente fictive')
        await self.c.servir_interaction(second)
        dire2=self.c._servir.call_args.args[1]
        await dire2('résultat fictif A')
        second.delete_original_response.assert_awaited_once()
        premier.edit_original_response.side_effect=discord.HTTPException(types.SimpleNamespace(status=401,reason='expiré'), 'expiré')
        second.edit_original_response.side_effect=discord.NotFound(types.SimpleNamespace(status=404,reason='supprimé'), 'supprimé')
        await dire2('résultat fictif B')
        second.followup.send.assert_awaited_once_with('résultat fictif B',ephemeral=True,wait=True)
        await dire2('résultat fictif C')
        secours.edit.assert_awaited_once_with(content='résultat fictif C',view=None)
        self.assertEqual(1,second.followup.send.await_count)
