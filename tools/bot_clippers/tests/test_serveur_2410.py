"""24/10 (Gaëtan, « MAJ serveur, bot, assistant ») : TL sans accès au salon de son VA repéré par !audit, parti du serveur sur sa
propre ligne du digest avec `!lien <id> retirer`, règle 45 de l'assistant. Données fictives uniquement."""
import logging
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sortie_auto  # noqa: E402
from test_assistant_simplifie_1810 import extraire, normaliser  # noqa: E402


def salon(nom, voient):
    return SimpleNamespace(name=nom, permissions_for=lambda m: SimpleNamespace(view_channel=m.id in voient))


class AccesTlTests(unittest.TestCase):
    def test_salon_sans_son_tl_repere(self):
        membres = {i: SimpleNamespace(id=i, bot=False) for i in (1, 2, 3, 9)}
        salons = {"1": salon("va-un", {1, 9}), "2": salon("va-deux", {2}), "3": salon("salaire", {3})}
        ns = extraire("bot_discord.py", {"acces_tl_manquants"},
                      {"equipes_tl": SimpleNamespace(tl_par_va=lambda: {"1": "9", "2": "9", "9": "9", "3": "9"},
                                                     _exclu=lambda u: u == "3", _regime=lambda u: "clic"),
                       "salon_perso_de": lambda uid: salons.get(str(uid)), "journal": logging.getLogger("test"),
                       "ADMIN_IDS": set()})
        g = SimpleNamespace(get_member=lambda i: membres.get(i))
        manques = ns["acces_tl_manquants"](g)
        self.assertEqual([("va-deux", 9, 2)], [(s.name, tl.id, va.id) for s, tl, va in manques])

    def test_commande_et_audit_branches(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn('texte.startswith("!acces-tl")', src)
        self.assertLess(src.index('texte.startswith("!acces-tl")'), src.index('    if texte.startswith("!acces") or'))
        self.assertIn("TL sans accès au salon de son VA", src)


class DigestPartisTests(unittest.TestCase):
    def test_parti_sur_sa_ligne_avec_la_commande_qui_marche(self):
        ancien = dict(sortie_auto._deps)
        sortie_auto._deps.update(FICHIER="sortie_auto.json", lire_json=lambda f, d: {},
                                 membre_par_id=lambda uid: None if uid == "222" else SimpleNamespace(id=int(uid)))
        try:
            with patch.object(sortie_auto, "inactifs", return_value=[("111", "Présent"), ("222", "Parti")]), \
                    patch.object(sortie_auto, "_etat", return_value={}):
                lignes, _ = sortie_auto.bilan_pour_digest()
        finally:
            sortie_auto._deps.clear()
            sortie_auto._deps.update(ancien)
        texte = "\n".join(lignes)
        self.assertIn("<@111>", texte)
        self.assertNotIn("<@222>", texte)
        self.assertIn("Partis du serveur", texte)
        self.assertIn("`!lien 222 retirer`", texte)


class AssistantTests(unittest.TestCase):
    def test_regle_45_bouton_compte_cree(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("45. « J'ai créé mon compte N »", src)
        self.assertIn("Appuie sur ✅ Compte N créé", src)


if __name__ == "__main__":
    unittest.main()
