"""30/10 (Gaëtan : « savoir d'où viennent les candidatures, pour double down sur ce qui marche ») : la question « Où as-tu vu
notre annonce ? » du formulaire, son canal (sources_annonce), sa colonne dans le classeur et le compte par source du digest.
Réponses calquées sur celles de l'onglet « Candidatures bot », pseudos et prénoms remplacés par des exemples fictifs. Hors réseau, sans Discord."""
import ast
import json
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sources_annonce as sa  # noqa: E402


def extraire(noms_fonctions, noms_variables, namespace):
    """Les fonctions et constantes nommées de bot_discord.py, exécutées seules (comme test_aide_staff)."""
    arbre = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
    garder = []
    for n in arbre.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms_fonctions:
            n.decorator_list = []
            garder.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in noms_variables for t in n.targets):
            garder.append(n)
    exec(compile(ast.fix_missing_locations(ast.Module(body=garder, type_ignores=[])), "bot_discord.py", "exec"), namespace)
    return namespace


def normaliser(texte):
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn").lower()


class CanalTests(unittest.TestCase):
    def test_reponses_reelles(self):
        cas = {
            "Telegram": "telegram", "telegram": "telegram", "Groupe jobs mada sur tg": "telegram", "t.me/jobsfr": "telegram",
            "Indeed": "indeed", "Discord (annonces)": "discord", "Discord": "discord",
            "Disboard (référencement)": "disboard", "Instagram": "instagram", "IG": "instagram", "insta": "instagram",
            "TikTok": "tiktok", "YouTube": "youtube", "Publicités": "pub", "Whatsapp": "whatsapp",
            "le site https://ofmjob.com/": "ofmjob", "OFM JOBS": "ofmjob", "Ofmjob": "ofmjob",
            "Un ami : demo_ami42": "parrainage", "Parrainage Paul": "parrainage", "mon cousin": "parrainage",
            "Un ami sur Telegram": "telegram",
        }
        for texte, attendu in cas.items():
            with self.subTest(texte=texte):
                self.assertEqual(attendu, sa.canal(texte))

    def test_vide_ou_inconnu_jamais_devine(self):
        for vide in ("", "  ", None, "Non", "-"):
            self.assertEqual("", sa.canal(vide))
        self.assertEqual("autre", sa.canal("Martin"), "un prénom seul : on ne devine pas")
        self.assertEqual("autre", sa.canal("je sais plus"))

    def test_le_lien_prime_sur_la_reponse(self):
        self.assertEqual("tg-jobs-mada", sa.source_candidature("tg-jobs-mada", "Indeed"))
        self.assertEqual("tg-bot", sa.source_candidature("tg-bot · détail", ""))
        self.assertEqual("indeed", sa.source_candidature("web", "Indeed"))
        self.assertEqual("discord", sa.source_candidature("form-principal", "Discord (annonces)"))
        self.assertEqual("web", sa.source_candidature("", ""))
        self.assertEqual("web", sa.source_candidature("web", "Non"))


class FormulaireTests(unittest.TestCase):
    def test_question_annonce_courte_obligatoire_apres_le_pays(self):
        cfg = json.loads((ROOT / "questions_candidature.json").read_text(encoding="utf-8"))
        ids = [q["id"] for q in cfg["questions"]]
        self.assertEqual(1, ids.count("annonce"))
        q = cfg["questions"][ids.index("annonce")]
        self.assertEqual("text", q["type"], "texte libre, une ligne")
        self.assertTrue(q["requis"])
        self.assertEqual("Toi", q["section"])
        self.assertEqual(ids.index("pays") + 1, ids.index("annonce"))


class ClasseurEtDigestTests(unittest.TestCase):
    def setUp(self):
        self.ns = extraire({"_colonnes_candidature", "sources_candidatures", "_chiffres_tel"}, {"MOTS_CANDIDATURE"},
                           {"normaliser": normaliser, "sources_annonce": sa, "re": __import__("re")})

    def test_colonne_historique_retrouvee(self):
        """La réponse va dans la colonne déjà présente « ou as tu vu annonce ? », jamais dans une colonne neuve,
        et l'ancienne question du Google Form reste reconnue."""
        cols = self.ns["_colonnes_candidature"]
        en_tete = ["Horodatage", "Source", "Quel est ton Prénom ?", "Est-ce que tu as bien lu la description de l'annonce ?",
                   "ou as tu vu annonce ?", "Si parrainage ou autre : précise"]
        self.assertEqual(4, cols(en_tete)["annonce"])
        self.assertEqual(1, cols(["Horodateur", "Sur quel réseau social as-tu vu notre annonce de recrutement ? "])["annonce"])

    def test_digest_compte_la_source_declaree(self):
        cands = [{"tel_chiffres": "33600000001"}, {"tel_chiffres": "33600000002"}, {"tel_chiffres": "33600000003"},
                 {"tel_chiffres": "33600000004"}]
        pipe = {"candidatures": {
            "+33600000001": {"source": "web", "reponses": {"annonce": "Telegram"}},
            "+33600000002": {"source": "tg-jobs-fr", "reponses": {"annonce": "Indeed"}},
            "+33600000003": {"source": "web", "reponses": {"annonce": ""}},
        }}
        lignes = [{"tel_chiffres": "33600000004", "src": "web", "annonce": "Discord (annonces)", "source": "site"}]
        self.assertEqual([("discord", 1), ("telegram", 1), ("tg-jobs-fr", 1), ("web", 1)],
                         self.ns["sources_candidatures"](cands, lignes, pipe))


if __name__ == "__main__":
    unittest.main()
