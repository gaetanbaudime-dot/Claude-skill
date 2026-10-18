"""18/10 (Gaëtan : « Assistant IA, BOT Gaëtan : améliore, simplifie, vérifie ») : réponses sans fausse promesse ni « prochaine
étape » collée, !sortie par prénom, suggestion de commande, compte 1 sans accès signalé."""
import ast
import asyncio
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def extraire(fichier, noms, namespace):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms)
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in noms for t in n.targets))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=corps, type_ignores=[])), fichier, "exec"), namespace)
    return namespace


def normaliser(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn").strip()


class ReponsesTests(unittest.TestCase):
    ns = extraire("bot_discord.py", {"_DEMANDE_SUITE", "retirer_prochaine_etape", "_FAUSSE_PROMESSE", "retirer_fausse_promesse",
                                     "COMMANDES_ADMIN", "suggestion_admin", "membre_par_nom_tape"},
                  {"re": re, "normaliser": normaliser})

    def test_prochaine_etape_retiree_sauf_si_demandee(self):
        r = "Attends 10 minutes.\n\n👉 Prochaine étape : ouvre la Fiche 1 - Création des Comptes"
        self.assertEqual(self.ns["retirer_prochaine_etape"](r, "le code n'arrive pas"), "Attends 10 minutes.")
        self.assertEqual(self.ns["retirer_prochaine_etape"](r, "je fais quoi ensuite ?"), r)

    def test_fausse_promesse_retiree(self):
        f = self.ns["retirer_fausse_promesse"]
        self.assertEqual(f("Toujours 0 ? Mets une capture dans ton salon perso : ton manager regarde."),
                         "Toujours 0 ? Mets une capture dans ton salon perso.")
        self.assertEqual(f("Toujours bloqué ? Mets une nouvelle capture ici, ton manager la voit."),
                         "Toujours bloqué ? Mets une nouvelle capture ici.")
        self.assertEqual(f("Ton manager, c'est Gaëtan. Il lit ton salon perso."), "Ton manager, c'est Gaëtan. Il lit ton salon perso.")

    def test_suggestion_admin(self):
        self.assertIn("`!roster`", self.ns["suggestion_admin"]("!toster"))
        self.assertIn("inconnue", self.ns["suggestion_admin"]("!zzzz"))

    def test_membre_par_prenom_tape(self):
        andry = SimpleNamespace(display_name="Andry - Sarah", bot=False)
        g = SimpleNamespace(members=[andry, SimpleNamespace(display_name="Julien - Sarah", bot=False)])
        f = self.ns["membre_par_nom_tape"]
        self.assertEqual(f(g, "Andry pas publier".split()), (andry, "pas publier", []))
        self.assertEqual(f(g, "@Andry - Sarah inactif".split())[0], andry)
        doublon = SimpleNamespace(members=[andry, SimpleNamespace(display_name="Andry - Chloé", bot=False)])
        membre, _, homonymes = f(doublon, ["Andry"])
        self.assertIsNone(membre)
        self.assertEqual(len(homonymes), 2)


class PromptTests(unittest.TestCase):
    def test_regles_ajoutees(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        for morceau in ("36. Aucune fausse promesse", "38. Tu as déjà donné la même consigne deux fois",
                        "40. Le lien WhatsApp de Gaëtan", "Tu ne cites JAMAIS un détail dont tu n'es pas"):
            self.assertIn(morceau, src)


class AccesEnAttenteTests(unittest.IsolatedAsyncioTestCase):
    async def test_alerte_admin_avec_commande(self):
        import parcours
        canal = SimpleNamespace(send=AsyncMock())
        ancien = dict(parcours._deps)
        parcours._deps["canal_admin"] = AsyncMock(return_value=canal)
        try:
            ok = await parcours.alerter_acces_en_attente(SimpleNamespace(display_name="Julien - Sarah"), "123",
                                                         "Ligne unique du classeur non confirmée.")
        finally:
            parcours._deps.clear()
            parcours._deps.update(ancien)
        self.assertTrue(ok)
        texte = canal.send.await_args.args[0]
        self.assertIn("`!remettre-compte1 123`", texte)
        self.assertIn("Julien - Sarah", texte)


if __name__ == "__main__":
    unittest.main()


class BotGaetanSimpleTests(unittest.TestCase):
    """18/10 après-midi (Gaëtan : « BOT Gaëtan : simplifier les commandes ») ."""
    def ns(self, parcours_lire=lambda: {}):
        return extraire("bot_discord.py", {"membre_par_nom_tape", "uid_depuis_nom"},
                        {"re": re, "normaliser": normaliser, "parcours": SimpleNamespace(_lire=parcours_lire)})

    def test_prenom_au_lieu_de_l_uid(self):
        g = SimpleNamespace(members=[SimpleNamespace(display_name="Antonio - Chloé", bot=False, id=1504090569427779725)])
        f = self.ns()["uid_depuis_nom"]
        self.assertEqual(f("!remettre-compte1 Antonio", g), ("!remettre-compte1 1504090569427779725", ""))
        self.assertEqual(f("!remettre-compte1 1504090569427779725", g)[1], "")
        self.assertIn("Personne", f("!organisation Zorro", g)[1])

    def test_fin_de_reponse_creatrice(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("compte 1 envoyé sans e-mail ni mot de passe : `!remettre-compte1 {prenom_c}`", src)
        self.assertNotIn('+ " · Message du compte 1 vérifié ; remise des accès non attestée.")', src)


class BloquesProducteursTests(unittest.TestCase):
    def test_un_clipper_qui_produit_n_est_pas_bloque(self):
        import bloques
        from datetime import datetime, timezone
        parcours = {"1": {"etape": 1, "dates": {"1": "2026-10-01T08:00:00+00:00"}},
                    "2": {"etape": 1, "dates": {"1": "2026-10-01T08:00:00+00:00"}}}
        l = bloques.liste(parcours, {"Chloé": ["Lucas", "Thia"]}, lambda p: {"Lucas": "1", "Thia": "2"}[p], lambda u: "",
                          {}, maintenant=datetime(2026, 10, 18, tzinfo=timezone.utc), produit=lambda uid: uid == "1")
        self.assertEqual([x[1] for x in l], ["Thia"])


class IdentiteClippingTests(unittest.TestCase):
    def test_rianah_clipping_chloe_appartient_a_rianah(self):
        rianah = SimpleNamespace(display_name="Rianah - Chloé", id=5)
        ns = extraire("bot_discord.py", {"membre_par_prenom"},
                      {"re": re, "normaliser": normaliser, "lire_json": lambda *_: {"5": {}}, "FICHIER_EQUIPES": "x",
                       "membre_par_id": lambda uid: rianah})
        for g in ("rianah clipping chloe", "rianah clipping sarah", "rianah"):
            self.assertIs(ns["membre_par_prenom"](g), rianah, g)
        self.assertIsNone(ns["membre_par_prenom"]("rianah metricool"))
