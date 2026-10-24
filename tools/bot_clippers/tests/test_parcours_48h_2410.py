"""24/10 (Gaëtan : « dans tous les cas, on leur donne un compte Instagram toutes les 48 heures. On arrête ce truc de quatre posts… c'est
quand même cool de s'assurer aussi que le clipper poste bien sur les comptes ») : tout parcours, ceux d'avant le 23/10 compris, ouvre
le compte suivant 48 h après la création du précédent, sans condition de Reels ; l'objectif de 4 Reels est dit, jamais exigé.
Cas fictifs, sans réseau ni Discord."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import parcours  # noqa: E402

MAINTENANT = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def ancienne(creation_1, quand=None, **plus):
    """Une fiche d'avant le 23/10 (sans marque « simple ») : son compte 2 programmé SANS délai, à la création du compte 1."""
    return {"etape": 2, "ordre": "prive3", "dates": {"1": iso(creation_1 - timedelta(minutes=30)), "1_fait": iso(creation_1)},
            "programme": [{"quand": iso(quand or creation_1), "type": "etape", "n": 2}], **plus}


class DelaiTests(unittest.TestCase):
    def test_ancienne_fiche_attend_48_h_apres_la_creation(self):
        f = ancienne(MAINTENANT - timedelta(hours=10))
        item = f["programme"][0]
        self.assertEqual(MAINTENANT + timedelta(hours=38), parcours.quand_etape(f, item))
        self.assertFalse(parcours._a_traiter(f, item, MAINTENANT), "programmé sans délai : jamais avant ses 48 h")
        self.assertEqual((2, MAINTENANT + timedelta(hours=38)), parcours.attente(f), "la date dite au clipper et au Dashboard")

    def test_ancienne_fiche_en_retard_part_tout_de_suite_sans_reel(self):
        f = ancienne(MAINTENANT - timedelta(days=5))
        self.assertTrue(parcours._a_traiter(f, f["programme"][0], MAINTENANT))
        self.assertEqual([], parcours.sources_reels(f, 2), "aucun Reel à compter")

    def test_compte_3_48_h_apres_le_compte_2(self):
        c2 = MAINTENANT - timedelta(hours=47)
        f = {"etape": 3, "ordre": "prive3", "dates": {"2_fait": iso(c2)}, "programme": [{"quand": iso(c2), "type": "etape", "n": 3}]}
        self.assertEqual(c2 + timedelta(hours=48), parcours.quand_etape(f, f["programme"][0]))
        self.assertFalse(parcours._a_traiter(f, f["programme"][0], MAINTENANT))
        self.assertTrue(parcours._a_traiter(f, f["programme"][0], MAINTENANT + timedelta(hours=1)))

    def test_heure_plus_tardive_gardee_et_ligne_sur_son_heure(self):
        f = ancienne(MAINTENANT - timedelta(days=5), quand=MAINTENANT + timedelta(hours=3))
        self.assertEqual(MAINTENANT + timedelta(hours=3), parcours.quand_etape(f, f["programme"][0]))
        ligne = {"quand": iso(MAINTENANT - timedelta(minutes=5)), "type": "etape", "n": 2, "ligne": True}
        f = ancienne(MAINTENANT - timedelta(hours=1))
        self.assertTrue(parcours._a_traiter(f, ligne, MAINTENANT), "retenu faute de ligne : son heure de nouvel essai")

    def test_sans_date_de_creation_l_heure_programmee(self):
        f = {"etape": 2, "programme": [{"quand": iso(MAINTENANT - timedelta(hours=1)), "type": "etape", "n": 2}]}
        self.assertTrue(parcours._a_traiter(f, f["programme"][0], MAINTENANT))

    def test_interrupteur_remet_la_regle_du_23_10(self):
        f = ancienne(MAINTENANT - timedelta(hours=10))
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):
            self.assertTrue(parcours._a_traiter(f, f["programme"][0], MAINTENANT), "l'ancienne règle : le palier de Reels décide")
            self.assertEqual([1], parcours.sources_reels(f, 2))

    def test_regle_dite_a_tous(self):
        texte = parcours.regle_comptes({"etape": 3, "dates": {"1": "2026-10-10T00:00:00+00:00"}, "ordre": "prive3"})
        self.assertIn("48 h après la création du compte 1", texte)
        self.assertIn("Aucune condition de Reels", texte)


class PublicationTests(unittest.TestCase):
    def fiche(self, n_reels_1=0, n_reels_2=0):
        creation = "2026-10-20T08:00:00+00:00"
        preuves = lambda n: {f"code{i}": "2026-10-21T12:00:00+00:00" for i in range(n)}  # noqa: E731
        return {"ordre": "prive3", "profils": {"1": creation, "2": creation},
                "reels": {"demo.un": {"reels_verifies_v2": preuves(n_reels_1)}, "demo.deux": {"reels_verifies_v2": preuves(n_reels_2)}}}

    def ligne(self, f, n):
        with patch.object(parcours, "_comptes_ordonnes", lambda *a, **k: ["demo.un", "demo.deux", "demo.prive"]):
            return parcours.ligne_publication("1", f, n)

    def test_compte_2_ouvert_avec_peu_de_reels_sur_le_compte_1(self):
        texte = self.ligne(self.fiche(n_reels_1=2), 2)
        self.assertIn("📌 Compte 1 : 2 Reels vus pour l'instant.", texte)
        self.assertIn("L'objectif reste 4 Reels par compte.", texte)
        self.assertIn("Continue de publier sur chaque compte.", texte)
        self.assertIn("aucun Reel vu", self.ligne(self.fiche(), 2))
        self.assertIn("1 Reel vu pour", self.ligne(self.fiche(n_reels_1=1), 2))

    def test_objectif_tenu_rien_a_dire(self):
        self.assertEqual("", self.ligne(self.fiche(n_reels_1=4), 2))

    def test_compte_3_regarde_le_compte_2(self):
        self.assertIn("Compte 2 : 3 Reels vus", self.ligne(self.fiche(n_reels_1=9, n_reels_2=3), 3))

    def test_le_compte_d_avant_prive_ne_publie_pas(self):
        f = {**self.fiche(), "ordre": "prive2", "dates": {"1_fait": "2026-10-20T08:00:00+00:00", "2_fait": "2026-10-20T08:00:00+00:00"}}
        self.assertEqual("", self.ligne(f, 3), "ordre « prive2 » : le compte 2 est le privé")

    def test_phrases_courtes_sans_parenthese(self):
        texte = self.ligne(self.fiche(n_reels_1=2), 2)
        self.assertNotIn("(", texte)
        for phrase in [p for p in texte.replace("📌", "").split("\n") if p.strip()]:
            self.assertLessEqual(len(phrase.split()), 10, phrase)


class AnnonceTests(unittest.TestCase):
    """L'annonce du 24/10 dans #annonces (règles gelées, geste 4) : une fois, lisible sur téléphone, la règle et l'objectif."""

    def test_annonce_unique_et_lisible(self):
        import json
        import re
        deposes = json.loads((ROOT / "messages_a_envoyer.json").read_text(encoding="utf-8"))
        entrees = [e for e in deposes if e["id"] == "annonce-48h-tous-2410"]
        self.assertEqual(1, len(entrees))
        e = entrees[0]
        self.assertEqual("#annonces", e["salon"])
        for cle in ("pour", "tous_clippers", "tous_arrivants", "effacer_bot", "lien_nouveau"):
            self.assertFalse(e.get(cle), cle)
        texte = e["texte"]
        for attendu in ("tout le monde", "48 h après la création du compte 1", "48 h après la création du compte 2",
                        "Aucun Reel à compter", "L'objectif reste 4 Reels par compte"):
            self.assertIn(attendu, texte)
        self.assertLessEqual(len(texte), 1900)
        for bloc in texte.split("\n\n"):
            self.assertNotIn("\n", bloc, "une ligne vide entre chaque paragraphe")
            self.assertNotIn("(", bloc)
            for phrase in re.split(r"(?<=[.?!:])\s+", bloc.replace("**", "")):
                self.assertLessEqual(len(phrase.split()), 10, phrase)


if __name__ == "__main__":
    unittest.main()
