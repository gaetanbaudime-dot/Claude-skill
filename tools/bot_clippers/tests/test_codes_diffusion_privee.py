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

    async def test_dm_automatique_bon_compte_et_notification_sans_code_ni_alias(self):
        self.assertEqual(await self.c._diffuser_code_prive(self.info), "mp")
        texte = self.membre.send.call_args.args[0]
        self.assertIn("111111", texte)
        self.assertIn("connexion", texte)
        self.assertIn("one@example.invalid", texte)
        self.salon.send.assert_awaited_once()
        public = str(self.salon.send.call_args)
        for secret in ("111111", "one@example.invalid", "compte.synthetic"):
            self.assertNotIn(secret, public)
        self.assertEqual(self.salon.send.call_args.kwargs["view"], "boutons-sans-code")

    async def test_pas_de_notification_dans_salon_commun_meme_si_mal_associe(self):
        self.salon.id = 300
        await self.c._diffuser_code_prive(self.info)
        self.membre.send.assert_awaited_once()
        self.salon.send.assert_not_awaited()

    async def test_dm_fermes_notification_et_bouton_prive_sans_code(self):
        self.membre.send.side_effect = self.c.discord.Forbidden("111111 secret-synthetique")
        self.assertEqual(await self.c._diffuser_code_prive(self.info), "mp_fermes")
        self.assertNotIn("111111", str(self.salon.send.call_args))
        self.assertEqual(self.salon.send.call_args.kwargs["view"], "boutons-sans-code")
        self.assertNotIn("dm|100|synthetic-message", self.state["faits"])

    async def test_dm_et_notification_non_dupliques(self):
        await self.c._diffuser_code_prive(self.info)
        self.assertEqual(await self.c._diffuser_code_prive(self.info), "deja")
        self.membre.send.assert_awaited_once()
        self.salon.send.assert_awaited_once()
        self.assertNotIn("111111", str(self.state["faits"]))

    async def test_ancien_futur_naif_et_date_invalide_refuses(self):
        for date in (self.now-timedelta(minutes=3), self.now+timedelta(minutes=3),
                     self.now.replace(tzinfo=None), "date-invalide", None):
            self.assertEqual(await self.c._diffuser_code_prive(dict(self.info, date=date)), "ancien")
        self.membre.send.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    async def test_secrets_2fa_recuperation_et_mutations_non_diffuses(self):
        for usage in ("2fa", "recuperation", "appel", "changement", "sms", "totp"):
            self.assertEqual(await self.c._diffuser_code_prive(dict(self.info, type=usage)), "ignore")
        self.assertEqual(await self.c._diffuser_code_prive(dict(self.info, decision="garder")), "ignore")
        self.membre.send.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    async def test_destinataire_ambigu_absent_aucun_envoi(self):
        self.c._deps["destinataire_alias"] = lambda _: None
        self.assertEqual(await self.c._diffuser_code_prive(self.info), "sans_destinataire")
        self.membre.send.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    async def test_droits_retires_avant_dm_aucun_envoi(self):
        self.c._adresses_membre = lambda _: set()
        self.assertEqual(await self.c._diffuser_code_prive(self.info), "droits_retires")
        self.membre.send.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    async def test_reaffectation_pendant_dm_aucune_notification_ancien_salon(self):
        # La fonction résolue garde la même référence, mais son résultat change.
        cible = {"membre": self.membre, "salon": self.salon}
        self.c._deps["destinataire_alias"] = lambda _: cible or None
        async def retirer(*_, **kwargs): cible.clear()
        self.membre.send.side_effect = retirer
        await self.c._diffuser_code_prive(self.info)
        self.salon.send.assert_not_awaited()

    async def test_salon_inaccessible_au_clipper_pas_de_notification(self):
        self.salon.permissions_for = lambda _: types.SimpleNamespace(view_channel=False)
        await self.c._diffuser_code_prive(self.info)
        self.membre.send.assert_awaited_once()
        self.salon.send.assert_not_awaited()

    async def test_lecteur_alimente_envoi_automatique(self):
        self.c.classer_mail = lambda _: self.info
        self.c._proprietaire = lambda _: {"canal_id": "200"}
        bilan = dict(donnes=0, orphelins=0, gardes=0, alertes=0)
        await self.c._traiter_un(None, {"msg": {}, "dossier": "INBOX"}, self.state, set(), "300", bilan)
        self.membre.send.assert_awaited_once()
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
