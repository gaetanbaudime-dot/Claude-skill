"""23/10 : l'annonce des règles gelées part dans #annonces au prochain démarrage du bot.
1. `_salon_par_nom` retrouve « 📢｜annonces » quand on demande « #annonces », sans jamais deviner entre deux salons.
2. L'entrée `annonce-regles-2310` est bien formée : un seul salon visé, texte court et lisible sur téléphone, sans promesse fausse.
Cas fictifs, sans réseau ni Discord."""
import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import messages_deposes  # noqa: E402


def client_avec(*noms):
    return N(guilds=[N(text_channels=[N(name=n) for n in noms])])


class SalonParNom(unittest.TestCase):
    def test_nom_exact(self):
        c = client_avec("general", "annonces")
        self.assertEqual(messages_deposes._salon_par_nom(c, "#annonces").name, "annonces")

    def test_casse_ignoree(self):
        c = client_avec("Annonces")
        self.assertEqual(messages_deposes._salon_par_nom(c, "#annonces").name, "Annonces")

    def test_emoji_et_separateur_ignores(self):
        for nom in ("📢｜annonces", "📢-annonces", "📢・annonces", "annonces📢"):
            with self.subTest(nom=nom):
                c = client_avec("general", nom, "ressources")
                self.assertEqual(messages_deposes._salon_par_nom(c, "#annonces").name, nom)

    def test_accents_ignores(self):
        c = client_avec("ℹ️-chloé")
        self.assertEqual(messages_deposes._salon_par_nom(c, "chloe").name, "ℹ️-chloé")

    def test_le_nom_exact_gagne_sur_le_proche(self):
        c = client_avec("📢｜annonces", "annonces")
        self.assertEqual(messages_deposes._salon_par_nom(c, "annonces").name, "annonces")

    def test_deux_proches_aucun_choisi(self):
        c = client_avec("📢｜annonces", "📣｜annonces")
        self.assertIsNone(messages_deposes._salon_par_nom(c, "#annonces"))

    def test_introuvable(self):
        self.assertIsNone(messages_deposes._salon_par_nom(client_avec("general"), "#annonces"))

    def test_nom_vide_ou_sans_caractere_utile(self):
        c = client_avec("📢｜", "general")
        self.assertIsNone(messages_deposes._salon_par_nom(c, "#"))
        self.assertIsNone(messages_deposes._salon_par_nom(c, "#📢"))


class EntreeAnnonce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        deposes = json.loads((ROOT / "messages_a_envoyer.json").read_text(encoding="utf-8"))
        ids = [str(e["id"]) for e in deposes]
        cls.ids = ids
        cls.entree = next((e for e in deposes if e["id"] == "annonce-regles-2310"), None)

    def test_presente_une_seule_fois(self):
        self.assertEqual(self.ids.count("annonce-regles-2310"), 1)

    def test_vise_annonces_seulement(self):
        self.assertEqual(self.entree["salon"], "#annonces")
        for cle in ("pour", "tous_clippers", "tous_arrivants", "effacer_bot"):
            self.assertFalse(self.entree.get(cle), cle)

    def test_texte_tient_dans_discord(self):
        self.assertLessEqual(len(self.entree["texte"]), 1900)

    def test_paragraphes_courts_separes_par_une_ligne_vide(self):
        texte = self.entree["texte"]
        self.assertNotIn("\n\n\n", texte)
        for bloc in texte.split("\n\n"):
            self.assertNotIn("\n", bloc, "une ligne vide entre chaque paragraphe")
            for phrase in re.split(r"(?<=[.?!:])\s+", bloc.replace("**", "")):
                self.assertLessEqual(len(phrase.split()), 15, phrase)

    def test_regles_annoncees_sont_celles_gelees(self):
        texte = self.entree["texte"]
        for attendu in ("jour 3", "rushes bruts", "48 h après sa remise", "48 h après l'avertissement",
                        "manager valide", "salon ℹ️", "#ressources"):
            self.assertIn(attendu, texte)
        for interdit in ("24 h", "Sarah", "GAML", "100 liens", "0,05"):
            self.assertNotIn(interdit, texte)

    def test_ids_uniques(self):
        self.assertEqual(len(self.ids), len(set(self.ids)))


if __name__ == "__main__":
    unittest.main()
