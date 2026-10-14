"""Envoi automatique et panneau public testés sans réseau ni fichier opérationnel."""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock, Mock
from test_codes_reliable import load_codes


class DiffusionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now
        self.state = {"codes": [], "faits": {}, "sante": {}, "n": 0}
        self.c._etat = lambda: self.state
        self.c._sauver = Mock()
        self.c.discord.HTTPException = type("HTTPException", (Exception,), {})
        self.c.discord.Forbidden = type("Forbidden", (self.c.discord.HTTPException,), {})
        self.membre = types.SimpleNamespace(id=100, send=AsyncMock())
        self.salon = types.SimpleNamespace(id=200, send=AsyncMock(),
            permissions_for=lambda _: types.SimpleNamespace(view_channel=True))
        self.c._deps = {"destinataire_alias": lambda _: {"membre": self.membre, "salon": self.salon}}
        self.c._adresses_membre = lambda _: {"one@example.invalid"}
        self.c.salon_codes_id = lambda: "300"
        self.c.vue_mon_code = lambda: "boutons-sans-code"
        self.info = dict(mid="synthetic-message", alias="one@example.invalid", code="111111", type="connexion",
                         decision="donner", date=self.now, compte="compte.synthetic", libelle="connexion")

    async def test_lecteur_met_en_cache_sans_dm_ni_publication(self):
        self.info["service"] = "facebook"
        self.c.classer_mail = lambda _: self.info
        self.c._proprietaire = lambda _: {"canal_id": "200"}
        bilan = dict(donnes=0, orphelins=0, gardes=0, alertes=0)
        await self.c._traiter_un(None, {"msg": {}, "dossier": "INBOX"}, self.state, set(), "300", bilan)
        self.membre.send.assert_not_awaited()
        self.salon.send.assert_not_awaited()
        self.assertEqual(self.state["codes"][0]["service"], "facebook")
        self.assertEqual(bilan["donnes"], 1)

    async def test_panneau_existant_sans_modifier_permissions_ni_historique(self):
        self.c.actif = lambda: True
        self.c._lire = lambda: {"_salon_codes": {"id": "300"}}
        self.c._ecrire = Mock()
        self.salon.id = 300
        self.salon.edit = AsyncMock()
        self.salon.history = Mock(side_effect=AssertionError("ne pas lire les messages"))
        message = types.SimpleNamespace(pin=AsyncMock())
        self.salon.send.return_value = message
        guild = types.SimpleNamespace(id=400, text_channels=[self.salon], create_text_channel=AsyncMock())
        client = types.SimpleNamespace(wait_until_ready=AsyncMock(), guilds=[guild], get_channel=lambda _: self.salon)
        await self.c.assurer_salon_codes(client)
        self.salon.edit.assert_not_awaited()
        self.salon.history.assert_not_called()
        guild.create_text_channel.assert_not_awaited()
        self.assertNotIn("111111", str(self.salon.send.call_args))
        self.c._ecrire.assert_called_once()

    async def test_echec_publication_panneau_ne_marque_pas_installe(self):
        self.c.actif = lambda: True
        self.c._lire = lambda: {"_salon_codes": {"id": "300"}}
        self.c._ecrire = Mock()
        self.salon.send.side_effect = self.c.discord.Forbidden("refus-synthetique")
        guild = types.SimpleNamespace(id=400)
        client = types.SimpleNamespace(wait_until_ready=AsyncMock(), guilds=[guild], get_channel=lambda _: self.salon)
        await self.c.assurer_salon_codes(client)
        self.c._ecrire.assert_not_called()

    async def test_salon_absent_ne_cree_pas_acces(self):
        self.c.actif = lambda: True
        self.c._lire = lambda: {}
        self.c._ecrire = Mock()
        guild = types.SimpleNamespace(id=400, text_channels=[], create_text_channel=AsyncMock())
        client = types.SimpleNamespace(wait_until_ready=AsyncMock(), guilds=[guild], get_channel=lambda _: None)
        await self.c.assurer_salon_codes(client)
        guild.create_text_channel.assert_not_awaited()
        self.c._ecrire.assert_not_called()


class DestinataireTests(unittest.TestCase):
    def resolveur(self, records):
        tree = ast.parse((Path(__file__).resolve().parents[1]/"bot_discord.py").read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ("_adresses_codes_fiche", "destinataire_alias_code")]
        ns = dict(lire_json=lambda *_: records, FICHIER_ONBOARDING="mock",
                  onboarding=types.SimpleNamespace(_cle_handle=lambda h: str(h).strip().lower()),
                  membre_par_id=lambda uid: types.SimpleNamespace(id=int(uid), display_name="Même prénom"),
                  salon_perso_de=lambda uid: types.SimpleNamespace(id=int(uid)+1000))
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), "owner-synthetic", "exec"), ns)
        return ns["destinataire_alias_code"]

    def fiche(self, handle, mail):
        return dict(comptes=[handle], acces=[dict(handle=handle, mail=mail)])

    def test_identite_uid_pas_prenom_ni_permissions_salon(self):
        resolver = self.resolveur({"clippers": {"100": self.fiche("one", "one@example.invalid"),
                                                "200": self.fiche("two", "two@example.invalid")}})
        self.assertEqual(resolver("one@example.invalid")["membre"].id, 100)
        self.assertEqual(resolver("two@example.invalid")["membre"].id, 200)
        self.assertIsNone(resolver("unknown@example.invalid"))

    def test_alias_commun_a_deux_uids_refuse(self):
        resolver = self.resolveur({"clippers": {uid: self.fiche(uid, "same@example.invalid") for uid in ("100", "200")}})
        self.assertIsNone(resolver("same@example.invalid"))

    def test_alias_commun_a_deux_comptes_meme_uid_refuse(self):
        resolver = self.resolveur({"clippers": {"100": dict(comptes=["one", "two"], acces=[
            dict(handle=h, mail="same@example.invalid") for h in ("one", "two")])}})
        self.assertIsNone(resolver("same@example.invalid"))

    def test_compte_avec_deux_alias_contradictoires_refuse(self):
        resolver = self.resolveur({"clippers": {"100": dict(comptes=["one"], acces=[
            dict(handle="one", mail=m) for m in ("one@example.invalid", "two@example.invalid")])}})
        self.assertIsNone(resolver("one@example.invalid"))
        self.assertIsNone(resolver("two@example.invalid"))

    def test_meme_compte_deux_uids_et_alias_distincts_refuse(self):
        resolver = self.resolveur({"clippers": {uid: self.fiche("same", uid+"@example.invalid") for uid in ("100", "200")}})
        self.assertIsNone(resolver("100@example.invalid"))
        self.assertIsNone(resolver("200@example.invalid"))

    def test_compte_revoque_ou_livre_a_un_autre_refuse(self):
        records = {"clippers": {"100": self.fiche("one", "one@example.invalid")}, "livres": {"one": {"uid": "200"}}}
        self.assertIsNone(self.resolveur(records)("one@example.invalid"))
        records["clippers"]["100"]["comptes"] = []
        self.assertIsNone(self.resolveur(records)("one@example.invalid"))
