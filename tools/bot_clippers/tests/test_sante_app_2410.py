"""24/10 (Gaëtan : « assure-toi que ça marche une bonne fois pour toutes ») : la clé Google de l'app des clippers (Vercel) a été
refusée du 22 au 24/10 sans alerte. Le bot interroge /api/sante de l'app et prévient le salon admin, comme pour sa propre clé."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extraire(noms, namespace):
    arbre = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms]
    exec(compile(ast.fix_missing_locations(ast.Module(body=corps, type_ignores=[])), "bot_discord.py", "exec"), namespace)
    return namespace


BOT = extraire({"texte_panne_app", "decider_alerte_app"}, {"GOOGLE_PANNE_MIN": 10, "GOOGLE_PANNE_RAPPEL_H": 12})


class SanteAppTests(unittest.TestCase):
    def test_alerte_apres_dix_minutes_puis_rappel_et_retour(self):
        decider, etat = BOT["decider_alerte_app"], {"depuis": None, "dite": None, "detail": ""}
        t0 = 1_000_000.0
        self.assertEqual("", decider(etat, False, t0, "Google OAuth 400 invalid_grant"))          # refus tout neuf : on attend
        self.assertEqual("", decider(etat, None, t0 + 300))                                          # app muette : rien à conclure
        self.assertEqual("alerte", decider(etat, False, t0 + 600, "Google OAuth 400 invalid_grant"))
        self.assertEqual("", decider(etat, False, t0 + 900))                                         # une seule alerte…
        self.assertEqual("alerte", decider(etat, False, t0 + 600 + 12 * 3600))                       # … puis un rappel à 12 h
        self.assertEqual("retour", decider(etat, True, t0 + 13 * 3600))
        self.assertEqual("", decider(etat, True, t0 + 14 * 3600))                                    # le retour n'est dit qu'une fois
        self.assertIsNone(etat["depuis"])

    def test_pas_de_retour_sans_alerte(self):
        etat = {"depuis": None, "dite": None, "detail": ""}
        self.assertEqual("", BOT["decider_alerte_app"](etat, False, 0.0))
        self.assertEqual("", BOT["decider_alerte_app"](etat, True, 60.0))

    def test_texte_dit_la_cause_et_le_remede(self):
        t = BOT["texte_panne_app"](0.0, 3 * 3600 + 120, "Google OAuth 400 invalid_grant: Invalid JWT Signature")
        self.assertIn("depuis 3 h 02", t)
        self.assertIn("Invalid JWT Signature", t)
        self.assertIn("GOOGLE_SERVICE_ACCOUNT_JSON", t)
        self.assertIn("Redeploy", t)
        self.assertIn("Les versements marchent toujours", t)


if __name__ == "__main__":
    unittest.main()
