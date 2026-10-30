"""Parcours Instagram : aide utilisable sans secrets ni compte réel.

Le routage est exécuté depuis l'AST de production, sans lancer le client Discord.
"""
import ast
import types
import unittest
from unittest.mock import AsyncMock, Mock

from test_codes_reliable import ROOT, load_codes


def extraire(fichier, nom, namespace):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    fonction = next(n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom)
    fonction.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])), fichier, "exec"), namespace)
    return namespace[nom]


class AideFunnelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.c = load_codes()
        self.c.actif = Mock(return_value=False)
        self.c.texte_salon_codes = lambda: self.c.TEXTE_CODE_BRUT
        self.c._lire = Mock(side_effect=AssertionError("Aucune lecture du registre pour cette aide"))
        self.c._adresses_membre = Mock(side_effect=AssertionError("Aucun compte à résoudre"))
        self.c._rafraichir_membre = AsyncMock(side_effect=AssertionError("Aucune mutation de liaison"))
        self.c._servir = AsyncMock(side_effect=AssertionError("Aucun code à délivrer"))
        self.c._demander_scan = Mock(side_effect=AssertionError("Aucune lecture de boîte"))
        self.c._commande_salon_commun = AsyncMock(side_effect=AssertionError("Aucune demande de code"))

    def message(self, texte, staff=False):
        return types.SimpleNamespace(content=texte, webhook_id=None,
            author=types.SimpleNamespace(id=42, bot=False, roles=[], staff=staff),
            channel=types.SimpleNamespace(id=123), guild=None, reply=AsyncMock())

    async def test_aide_disponible_relais_eteint_sans_consulter_les_comptes(self):
        for sujet in ("", "creation", "connexion", "renvoi", "authentificateur", "suspension"):
            with self.subTest(sujet=sujet):
                message = self.message("!aide-ig " + sujet)
                self.assertTrue(await self.c.commande(message, set()))
                reponse = message.reply.call_args.args[0]
                self.assertLess(len(reponse), 2000)
                self.assertFalse(message.reply.call_args.kwargs["mention_author"])
                self.assertEqual(reponse, self.c.aide_instagram(sujet))
        self.c.actif.assert_not_called()
        self.c._lire.assert_not_called()
        self.c._commande_salon_commun.assert_not_awaited()

    async def test_argument_inconnu_ou_sensible_jamais_recopie(self):
        for texte in ("!aide-ig synthetic-secret-918273", "!aide-instagram suspension synthetic-secret-918273"):
            message = self.message(texte)
            await self.c.commande(message, set())
            self.assertNotIn("synthetic-secret-918273", message.reply.call_args.args[0])

    async def test_demande_totp_explique_la_limite_sans_scanner(self):
        for terme in ("totp", "2fa", "authentificateur", "authenticator"):
            message = self.message("!code " + terme)
            await self.c.commande(message, set())
            texte = message.reply.call_args.args[0]
            self.assertIn("le bot ne génère pas ces codes", texte)
            self.assertIn("**SMS ou WhatsApp**", texte)
        self.c._servir.assert_not_awaited()
        self.c._demander_scan.assert_not_called()

    async def test_recours_et_recuperation_officiels_sans_distribution_de_code(self):
        for commande in ("!appel", "!unban", "!deban", "!recup"):
            message = self.message(commande)
            await self.c.commande(message, set())
            texte = message.reply.call_args.args[0]
            self.assertIn(self.c.URL_AIDE_META, texte)
            self.assertIn("Si « Contester »", texte)
            self.assertIn("« Voir la règle »", texte)               # 30/10 (Gaëtan) : la capture dit pourquoi
            self.assertIn("avec tes infos à toi", texte)
            self.assertIn("selfie vidéo de ton visage", texte)
            self.assertIn("ne soumet pas de recours", texte)
            self.assertNotIn("l'équipe le reçoit et te répond", texte)
        self.c._commande_salon_commun.assert_not_awaited()

    async def test_blocage_liaison_ne_promet_pas_une_alerte_non_envoyee(self):
        self.c._est_staff = lambda _: False
        self.c._comptes_a_son_mail = lambda _: False                  # un compte à l'e-mail de l'agence sans adresse rattachée
        self.c._alerter_sans_adresse = AsyncMock(return_value=False)
        dire = AsyncMock()
        await self.c._sans_adresse(self.message("").author, dire)
        self.assertIn("Signale ce blocage", dire.call_args.args[0])
        self.assertNotIn("est signalé", dire.call_args.args[0])
        self.c._alerter_sans_adresse.return_value = True
        await self.c._sans_adresse(self.message("").author, dire)
        self.assertIn("est signalé", dire.call_args.args[0])
        self.assertNotIn("te répond", dire.call_args.args[0])

    async def test_comptes_a_son_mail_pas_de_blocage_ni_d_alerte(self):
        """30/10 (règle C14) : ses comptes ont son e-mail à lui, ses codes arrivent dans sa boîte : rien à signaler."""
        self.c._est_staff = lambda _: False
        self.c._comptes_a_son_mail = lambda _: True
        self.c._alerter_sans_adresse = AsyncMock(return_value=True)
        dire = AsyncMock()
        await self.c._sans_adresse(self.message("").author, dire)
        self.assertEqual(self.c.TEXTE_CODE_SA_BOITE, dire.call_args.args[0])
        self.assertIn("arrivent dans ta boîte", dire.call_args.args[0])
        self.c._alerter_sans_adresse.assert_not_awaited()

    def test_comptes_a_son_mail_lit_la_fiche(self):
        import onboarding
        from unittest.mock import patch
        membre = types.SimpleNamespace(id=42)
        for acces, attendu in (([{"handle": "a.fictif"}], True), ([], True),
                               ([{"handle": "a.fictif", "mail": "x@agence.fictif"}], False)):
            etat = {"clippers": {"42": {"acces": acces}}}
            with patch.object(onboarding, "_lire_etat", return_value=etat):
                self.assertEqual(attendu, self.c._comptes_a_son_mail(membre), acces)
        with patch.object(onboarding, "_lire_etat", side_effect=OSError):
            self.assertFalse(self.c._comptes_a_son_mail(membre))

    def test_aide_renvoi_garde_le_compte_usage_et_delai(self):
        texte = self.c.aide_instagram("renvoi")
        self.assertIn("si proposé", texte)
        self.assertIn("délai affiché", texte)
        self.assertIn("bon service et du bon usage", texte)
        self.assertIn("cinq minutes", texte)
        self.assertIn("renvois ne la corrigent pas", texte)

    def test_ecrans_de_panne_ne_promettent_pas_une_notification_non_confirmee(self):
        for texte in (self.c.TEXTE_PANNE, self.c.TEXTE_PANNE_GUET, self.c.TEXTE_GARDE):
            self.assertNotIn("équipe est prévenue", texte)
            self.assertLess(len(texte), 2000)

    def test_parcours_ban_et_aide_clipper_utilisent_les_limites_courantes(self):
        ban = extraire("parcours.py", "texte_bloque", {"codes_2fa": self.c})(2)
        self.assertIn("Ton compte 2", ban)
        self.assertIn(self.c.aide_instagram("suspension"), ban)
        self.assertNotIn("équipe est prévenue", ban)
        aide = extraire("bot_discord.py", "texte_aide", {"codes_2fa": self.c,
            "est_manager": lambda _: False, "est_signe": lambda _: True})(None, False)
        self.assertIn("!aide-ig suspension", aide)
        self.assertNotIn("l'équipe le reçoit", aide)
        self.assertLess(len(aide), 2000)

    def test_modeles_creation_connexion_formatables_sans_changement_de_contact(self):
        arbre = ast.parse((ROOT / "parcours.py").read_text(encoding="utf-8"))
        noms = {"PSEUDO_PRIS", "CREATION", "CONNEXION"}
        noeuds = [n for n in arbre.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id in noms for t in n.targets)]
        ns = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=noeuds, type_ignores=[])), "modeles", "exec"), ns)
        for texte in ns["CREATION"] + ns["CONNEXION"]:
            rendu = texte.format(codes=self.c.TEXTE_CODE_BRUT)
            self.assertNotIn("{codes}", rendu)
            self.assertNotIn("Mets le tien", rendu)
            self.assertNotIn("Numéro demandé ? Le tien", rendu)
        self.assertIn("titulaire", ns["CREATION"][0])
        self.assertIn("Ne remplace pas", ns["CONNEXION"][0])

    async def test_routage_reel_de_aide_et_appel_de_presence(self):
        presence = types.SimpleNamespace(commande=AsyncMock(return_value=True), noter_activite=Mock())
        ns = {"codes_2fa": self.c, "appel": presence, "ANCIENS_WEBHOOKS": (), "ADMIN_IDS": set(),
              "nettoyer": lambda m: m.content, "normaliser_commande": lambda t: t,
              "en_prive": lambda _: False, "est_staff": lambda m: m.staff,
              "filtrer_spam": AsyncMock(return_value=False)}
        router = extraire("bot_discord.py", "on_message", ns)
        message = self.message("!aide-ig suspension")
        await router(message)
        self.assertEqual(message.reply.call_args.args[0], self.c.aide_instagram("suspension"))
        presence.commande.assert_not_awaited()
        appel_staff = self.message("!appel go", staff=True)
        await router(appel_staff)
        presence.commande.assert_awaited_once_with(appel_staff, "!appel go")
        appel_staff.reply.assert_not_awaited()
        self.assertEqual(self.c.demande_de_code("!aide-ig code"), "")


if __name__ == "__main__":
    unittest.main()
