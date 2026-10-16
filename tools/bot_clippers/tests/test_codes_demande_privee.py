"""Régressions synthétiques : contexte, fraîcheur, révocation et transports privés.
Aucun appel Gmail/Discord et aucune lecture de configuration ou de compte réel.
"""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock

from test_codes_reliable import load_codes
import test_codes_reliable as existing


class DemandeTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now
        self.state = {"codes": [], "n": 0}
        self.c._etat = lambda: self.state
        self.c._sauver = lambda: None
        self.c.actif = lambda: True
        self.c._demander_scan = lambda *args: None
        self.c._adresses_membre = lambda user: {"one@example.invalid"}
        self.c.discord.HTTPException = type("HTTPException", (Exception,), {})
        self.c.discord.Forbidden = type("Forbidden", (self.c.discord.HTTPException,), {})
        self.c.discord.NotFound = type("NotFound", (self.c.discord.HTTPException,), {})
        self.c.discord.InteractionResponded = type("InteractionResponded", (Exception,), {})
        self.c.vue_mon_code = lambda: "bouton"

    def entree(self, code="111111", alias="one@example.invalid", usage="connexion", age=0, mid=None):
        t = dict(code=code, alias=alias, type=usage, decision="donner", mid=mid or code,
                 date=(self.now - timedelta(minutes=age)).isoformat())
        self.state["codes"].append(t)
        return t

    def servir(self, usage="connexion", adresses=None, relire=None):
        messages = []
        async def dire(t): messages.append(t)
        result = asyncio.run(self.c._servir(adresses or {"one@example.invalid"}, dire, "u|100",
                                           duree=0, usage=usage, relire=relire))
        return result, "\n".join(messages)

    def test_connexion_ne_recoit_jamais_creation(self):
        self.entree(usage="creation")
        result, texte = self.servir()
        self.assertEqual(result, "rien")
        self.assertNotIn("111111", texte)

    def test_bon_compte_et_bon_usage_meme_si_autre_plus_recent(self):
        self.entree("111111", age=1)
        self.entree("222222", alias="other@example.invalid")
        self.entree("333333", usage="creation")
        result, texte = self.servir()
        self.assertEqual(result, "code")
        self.assertIn("111111", texte)
        self.assertNotIn("222222", texte)
        self.assertNotIn("333333", texte)

    def test_code_creation_de_huit_minutes_non_rejoue(self):
        self.entree(age=8, usage="creation")
        self.assertNotIn("111111", self.servir(usage="creation")[1])

    def test_date_future_ou_naive_ou_invalide_refusee(self):
        for date in ((self.now + timedelta(hours=1)).isoformat(), "2026-10-14T10:00:00", "absente"):
            self.state["codes"].clear()
            self.entree()["date"] = date
            self.assertNotIn("111111", self.servir()[1])

    def test_deux_comptes_ou_aucun_usage_demandent_un_choix(self):
        self.entree()
        self.assertEqual(self.servir(usage="")[0], "choix")
        self.assertEqual(self.servir(adresses={"one@example.invalid", "two@example.invalid"})[0], "choix")

    def test_retrait_droits_avant_premiere_livraison(self):
        self.entree()
        result, texte = self.servir(relire=lambda: set())
        self.assertEqual(result, "sortie")
        self.assertNotIn("111111", texte)

    def test_nouvelle_demande_ne_rejoue_pas_code_deja_presente(self):
        self.entree()
        self.assertIn("111111", self.servir()[1])
        self.assertNotIn("111111", self.servir()[1])

    def test_nouveau_code_remplace_precedent(self):
        self.entree(age=1)
        messages = []
        async def attendre(_):
            self.now += timedelta(minutes=1)
            self.entree("222222")
            self.c.time = types.SimpleNamespace(monotonic=lambda: 10)
        async def dire(t): messages.append(t)
        self.c.time = types.SimpleNamespace(monotonic=lambda: 0)
        self.c._attendre_nouveau = attendre
        result = asyncio.run(self.c._servir({"one@example.invalid"}, dire, "u|100", duree=1, usage="connexion"))
        self.assertEqual(result, "code")
        self.assertIn("111111", messages[0])
        self.assertIn("222222", messages[-1])
        self.assertNotIn("111111", messages[-1])

    def test_retrait_droits_efface_code_pendant_attente(self):
        self.entree()
        droits = {"one@example.invalid"}
        messages = []
        async def attendre(_): droits.clear()
        async def dire(t): messages.append(t)
        self.c._attendre_nouveau = attendre
        result = asyncio.run(self.c._servir(set(droits), dire, "u|100", duree=1,
                                           usage="connexion", relire=lambda: droits))
        self.assertEqual(result, "sortie")
        self.assertNotIn("111111", messages[-1])

    def test_deux_demandes_rapides_changent_vraiment_de_compte(self):
        self.entree()
        self.entree("222222", alias="two@example.invalid")
        ancien, nouveau = [], []
        async def test():
            async def dire1(t): ancien.append(t)
            async def dire2(t): nouveau.append(t)
            task = asyncio.create_task(self.c._servir({"one@example.invalid"}, dire1, "u|100", duree=1, usage="connexion"))
            await asyncio.sleep(0)
            result = await self.c._servir({"two@example.invalid"}, dire2, "u|100", duree=0, usage="connexion")
            await self.c._reveiller()
            self.assertEqual(await task, "remplace")
            return result
        self.assertEqual(asyncio.run(test()), "code")
        self.assertNotIn("111111", "\n".join(nouveau))
        self.assertIn("222222", nouveau[-1])
        self.assertNotIn(self.c.TEXTE_SUITE, ancien)

    def test_commande_conserve_son_contexte(self):
        self.assertEqual(self.c.demande_de_code("!code connexion"), "!code connexion")

    def interaction(self):
        return types.SimpleNamespace(user=types.SimpleNamespace(id=100),
            response=types.SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            edit_original_response=AsyncMock(), followup=types.SimpleNamespace(send=AsyncMock()))

    def test_interaction_code_uniquement_ephemere(self):
        self.entree()
        i = self.interaction()
        self.c.ATTENTE_SEC = 0
        result = asyncio.run(self.c.servir_interaction(i, "connexion", "one@example.invalid"))
        self.assertEqual(result, "code")
        i.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.assertIn("111111", i.edit_original_response.call_args.kwargs["content"])

    def test_echec_accuse_prive_ne_modifie_pas_message_public(self):
        i = self.interaction()
        i.response.defer.side_effect = self.c.discord.HTTPException("transport")
        result = asyncio.run(self.c.servir_interaction(i, "connexion", "one@example.invalid"))
        self.assertEqual(result, "indisponible")
        i.edit_original_response.assert_not_awaited()
        i.followup.send.assert_not_awaited()

    def test_compte_forge_refuse_par_callback(self):
        i = self.interaction()
        self.entree("222222", alias="other@example.invalid")
        self.assertEqual(asyncio.run(self.c.servir_interaction(i, "connexion", "other@example.invalid")), "refus")
        self.assertNotIn("222222", str(i.edit_original_response.call_args))

    def test_mp_fermes_pas_de_code_dans_salon(self):
        self.entree()
        m = types.SimpleNamespace(author=types.SimpleNamespace(id=100,
             send=AsyncMock(side_effect=self.c.discord.Forbidden("fermes"))), reply=AsyncMock())
        asyncio.run(self.c._commande_salon_commun(m, False, False, usage="connexion"))
        self.assertNotIn("111111", str(m.reply.call_args_list))
        self.assertIn("fermés", m.reply.call_args.args[0])

    def test_retrait_push_historique_vers_salon(self):
        self.c.classer_mail = lambda _: dict(mid="synthetique", alias="one@example.invalid", code="111111",
            type="connexion", decision="donner", compte="", date=self.now, libelle="connexion")
        self.c._proprietaire = lambda _: {"canal_id": "200", "par": "100"}
        salon = types.SimpleNamespace(send=AsyncMock())
        client = types.SimpleNamespace(get_channel=lambda _: salon)
        bilan = dict(donnes=0, orphelins=0, gardes=0, alertes=0)
        asyncio.run(self.c._traiter_un(client, {"msg": {}, "dossier": "INBOX"}, self.state, set(), "300", bilan))
        salon.send.assert_not_awaited()

    def test_logs_exception_sans_code_ni_secret_et_diagnostic_preserve(self):
        erreur = self.c.imaplib.IMAP4.error("AUTHENTICATIONFAILED secret-test 111111")
        self.assertNotIn("111111", self.c._err(erreur))
        self.assertNotIn("secret-test", self.c._err(erreur))
        self.assertEqual(self.c._genre_erreur(erreur), "mdp")

    def test_mail_sans_date_n_est_pas_frais_et_cle_sans_code(self):
        msg = EmailMessage()
        msg["From"] = "security@mail.instagram.com"
        msg["To"] = "one@example.invalid"
        msg["Subject"] = "111111 is your Instagram code"
        msg.set_content("Use this code to log in: 111111")
        info = self.c.classer_mail(msg)
        self.assertEqual(info["date"].year, 1970)
        self.assertNotIn("111111", info["mid"])

    def test_modification_apres_code_ou_dans_autre_partie_refusee(self):
        prefix = ("Someone tried to log in to your Instagram profile. "
                  "Use the following code to confirm your identity: 111111. ")
        for corps, parties in ((prefix + "Use it to change your password.", []),
                                (prefix, ["Use 111111 to reset your password."])):
            result = self.c.classer("security@mail.instagram.com", "Verify your profile", corps, parties)
            self.assertNotEqual(result["decision"], "donner")

    def test_securite_2fa_et_recuperation_non_livrables(self):
        for usage in ("2fa", "recuperation", "appel"):
            self.state["codes"].clear()
            self.entree(usage=usage)
            self.assertNotIn("111111", self.servir(usage=usage)[1])

    def test_destinataires_ambigus_refuses(self):
        msg = EmailMessage()
        msg["To"] = "one@example.invalid, other@example.invalid"
        self.assertEqual(self.c.alias_du_mail(msg), "")

    def test_codes_ne_sont_pas_ecrits_sur_disque(self):
        import json
        import tempfile
        self.entree()
        self.state.update(faits={}, sante={})
        # Retrouver la fonction réelle ; les tests de transport l'isolent par défaut.
        original = load_codes()
        original._etat = lambda: self.state
        original._maintenant = lambda: self.now
        with tempfile.TemporaryDirectory() as d:
            fichier = Path(d) / "etat.json"
            original._fichier_etat = lambda: fichier
            original._sauver()
            contenu = fichier.read_text()
            self.assertNotIn("111111", contenu)
            self.assertEqual(json.loads(contenu)["codes"], [])

    def test_type_2fa_dans_sujet_generique_reste_bloque(self):
        for texte in ("Use 111111 to turn off two-factor authentication.", "Your backup code is 111111."):
            result = self.c.classer("security@mail.instagram.com", "111111 is your Instagram code", texte)
            self.assertNotEqual(result["decision"], "donner")

    def test_tri_recherche_directe_deux_codes_meme_seconde(self):
        self.state["codes"].clear()
        self.c._scan_recent_sync = lambda *_: [
            dict(mid="nouveau", alias="one@example.invalid", code="222222", type="connexion", decision="donner", date=self.now.isoformat()),
            dict(mid="ancien", alias="one@example.invalid", code="111111", type="connexion", decision="donner", date=self.now.isoformat())]
        asyncio.run(self.c._scanner_sur_demande({"one@example.invalid"}, "u|100"))
        result, texte = self.servir()
        self.assertEqual(result, "code")
        self.assertIn("222222", texte)
        self.assertNotIn("111111", texte)


class ProprieteTests(unittest.TestCase):
    def namespace(self, data):
        ns, code = existing.OwnershipTests()._functions()
        ns.update(lire_json=lambda *_: data, FICHIER_ONBOARDING="mock",
                  onboarding=types.SimpleNamespace(_cle_handle=lambda t: str(t).strip().lower()),
                  membre_par_id=lambda uid: types.SimpleNamespace(id=uid),
                  salon_perso_de=lambda uid: types.SimpleNamespace(id="200"),
                  _autres_occupants=lambda *_: [],
                  _revision_adresses_codes=lambda: "nouvelle-revision",
                  codes_2fa=types.SimpleNamespace(_salon_prive=lambda _: True,
                     adresses_de=lambda _: {"retired@example.invalid"}))
        exec(code, ns)
        return ns

    def test_compte_retire_ne_revient_pas_des_acces_ou_alias_historiques(self):
        data = {"clippers": {"100": {"comptes": [], "acces": [
            {"handle": "retired", "mail": "retired@example.invalid"}]}}, "livres": {}}
        self.assertEqual(self.namespace(data)["adresses_codes_de"]("100"), set())

    def test_mail_commun_a_deux_clippers_est_bloque(self):
        data = {"clippers": {uid: {"comptes": [uid], "acces": [
            {"handle": uid, "mail": "shared@example.invalid"}]} for uid in ("100", "200")}}
        ns = self.namespace(data)
        self.assertEqual(ns["adresses_codes_de"]("100"), set())
        self.assertEqual(ns["adresses_codes_de"]("200"), set())

    def test_cache_invalide_immediatement_apres_changement_propriete(self):
        ns = self.namespace({"clippers": {"100": {"comptes": [], "acces": []}}})
        ns["_OTP_UID_CACHE"]["100"] = {"mails": {"retired@example.invalid"}, "jusque": 999,
                                       "revision": "ancienne-revision"}
        self.assertEqual(ns["adresses_codes_de"]("100"), set())

    def test_second_telephone_ne_perd_pas_son_compte_deja_livre(self):
        data = {"clippers": {"100": {"comptes": [], "telephones": {"exemple": {
            "donnes": 1, "acces": [{"handle": "phone.one", "mail": "phone@example.invalid"},
                                    {"handle": "phone.future", "mail": "future@example.invalid"}]}}}}}
        self.assertEqual(self.namespace(data)["adresses_codes_de"]("100"), {"phone@example.invalid"})


if __name__ == "__main__":
    unittest.main()
