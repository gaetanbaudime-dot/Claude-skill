"""23/10 (Gaëtan : « envoie le lien à Esperance ») : un message déposé avec `lien_nouveau` fait créer le lien du clipper par le
circuit habituel, puis l'envoie dans son salon perso.
1. Le salon est vérifié AVANT : sans salon perso, aucun lien n'est créé.
2. Lien prêt : « {lien} » est remplacé par son adresse, le message part une fois, la trace est écrite.
3. Lien pas prêt (forfait plein, exception) : rien ne part, la raison va à l'admin, rien n'est tracé (retenté au démarrage suivant).
4. Une entrée sans `lien_nouveau` ne touche jamais au circuit des liens.
5. L'entrée du dépôt est bien formée.
Cas fictifs, sans réseau ni Discord."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import messages_deposes  # noqa: E402

URL = "https://chloe-callista.fr/21"


def salon(nom):
    return N(name=nom, id=hash(nom) % 10**6, mention=f"#{nom}", send=AsyncMock())


class Monde:
    """Un serveur fictif : un membre « Esperance », son salon perso (ou pas), un salon admin, un registre de traces en mémoire."""

    def __init__(self, avec_salon=True, lien=(URL, ""), exception=None):
        self.membre = N(id=42, display_name="Esperance - Chloé")
        self.perso = salon("esperance-chloe") if avec_salon else None
        self.admin = salon("admin")
        self.traces = {}
        self.lien_pour = AsyncMock(return_value=lien, side_effect=exception)
        self.client = N(wait_until_ready=AsyncMock(), user=N(), guilds=[])

    def deps(self):
        return {
            "lire_json": lambda chemin, defaut: self.traces,
            "ecrire_json": lambda chemin, valeur: self.traces.update(valeur),
            "FICHIER": "traces.json",
            "chercher_membre": lambda ref, exact=True: self.membre if ref == "Esperance" else None,
            "salon_perso": lambda uid: self.perso if uid == 42 else None,
            "canal_admin": AsyncMock(return_value=self.admin),
            "lien_pour": self.lien_pour,
        }

    def lancer(self, entrees):
        with tempfile.TemporaryDirectory() as tmp:
            dep = Path(tmp) / "messages_a_envoyer.json"
            dep.write_text(json.dumps(entrees, ensure_ascii=False), encoding="utf-8")
            with patch.object(messages_deposes, "FICHIER_REPO", dep), patch.dict(messages_deposes._deps, self.deps(), clear=True):
                return asyncio.run(messages_deposes.envoyer_au_demarrage(self.client))


def entree(**plus):
    base = {"id": "lien-test", "pour": "Esperance", "lien_nouveau": True, "texte": "Voici ton lien : {lien}\n\nMets-le en bio."}
    base.update(plus)
    return base


class LienNouveau(unittest.TestCase):
    def test_lien_pret_le_message_part_avec_l_adresse(self):
        m = Monde()
        faits = m.lancer([entree()])
        self.assertEqual(faits, ["lien-test"])
        m.lien_pour.assert_awaited_once_with(m.membre)
        envoye = m.perso.send.await_args.args[0]
        self.assertIn(URL, envoye)
        self.assertNotIn("{lien}", envoye)
        self.assertIn("lien-test", m.traces)

    def test_sans_salon_perso_aucun_lien_cree(self):
        m = Monde(avec_salon=False)
        self.assertEqual(m.lancer([entree()]), [])
        m.lien_pour.assert_not_awaited()
        self.assertEqual(m.traces, {})
        self.assertIn("non envoyé", m.admin.send.await_args.args[0])

    def test_lien_pas_pret_rien_ne_part_et_la_raison_va_a_l_admin(self):
        m = Monde(lien=("", "forfait GAML plein"))
        self.assertEqual(m.lancer([entree()]), [])
        m.perso.send.assert_not_awaited()
        self.assertEqual(m.traces, {})
        message_admin = m.admin.send.await_args.args[0]
        self.assertIn("forfait GAML plein", message_admin)
        self.assertIn("prochain démarrage", message_admin)

    def test_exception_du_circuit_meme_traitement(self):
        m = Monde(exception=RuntimeError("GAML en panne"))
        self.assertEqual(m.lancer([entree()]), [])
        m.perso.send.assert_not_awaited()
        self.assertEqual(m.traces, {})
        self.assertIn("GAML en panne", m.admin.send.await_args.args[0])

    def test_adresse_qui_n_est_pas_un_lien_refusee(self):
        m = Monde(lien=("pas un lien", ""))
        self.assertEqual(m.lancer([entree()]), [])
        m.perso.send.assert_not_awaited()

    def test_deja_envoye_jamais_deux_fois_ni_second_lien(self):
        m = Monde()
        m.traces["lien-test"] = {"date": "2026-10-23T10:00:00+00:00", "salon": "esperance-chloe"}
        self.assertEqual(m.lancer([entree()]), [])
        m.lien_pour.assert_not_awaited()
        m.perso.send.assert_not_awaited()

    def test_sans_option_le_circuit_des_liens_n_est_jamais_appele(self):
        m = Monde()
        faits = m.lancer([entree(lien_nouveau=False, texte="Un simple message.")])
        self.assertEqual(faits, ["lien-test"])
        m.lien_pour.assert_not_awaited()
        self.assertEqual(m.perso.send.await_args.args[0], "Un simple message.")


class EntreeDuDepot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        deposes = json.loads((ROOT / "messages_a_envoyer.json").read_text(encoding="utf-8"))
        cls.entrees = [e for e in deposes if e["id"] == "lien-esperance-2310"]

    def test_une_seule_entree_pour_esperance(self):
        self.assertEqual(len(self.entrees), 1)

    def test_forme(self):
        e = self.entrees[0]
        self.assertEqual(e["pour"], "Esperance")
        self.assertTrue(e["lien_nouveau"])
        self.assertEqual(e["texte"].count("{lien}"), 1)
        self.assertLessEqual(len(e["texte"]), 1900)

    def test_paragraphes_courts_separes_par_une_ligne_vide(self):
        texte = self.entrees[0]["texte"]
        self.assertNotIn("\n\n\n", texte)
        for bloc in texte.split("\n\n"):
            self.assertNotIn("\n", bloc)
            for phrase in bloc.replace(" ?", "?").replace(" !", "!").replace(" :", ":").split(". "):
                self.assertLessEqual(len(phrase.split()), 10, phrase)

    def test_ne_promet_rien_de_faux(self):
        texte = self.entrees[0]["texte"]
        for interdit in ("0,05", "$", "paie", "Sarah", "GAML"):
            self.assertNotIn(interdit, texte)


if __name__ == "__main__":
    unittest.main()


class EchecsRegroupes(unittest.TestCase):
    """24/10 (« lien-esperance-2310 » : neuf lignes « non envoyé » en 24 h) : une ligne admin par message et par 24 h."""
    def test_deux_redemarrages_une_seule_ligne_puis_succes_avec_le_compte(self):
        m = Monde(lien=("", "inventaire GAML incomplet"))
        echecs = {}
        base = m.deps

        def deps():
            d = base()
            lire = d["lire_json"]
            d["lire_json"] = lambda chemin, defaut: echecs if chemin == "echecs.json" else lire(chemin, defaut)
            d["ecrire_json"] = (lambda chemin, valeur: (echecs.clear(), echecs.update(valeur)) if chemin == "echecs.json"
                                else m.traces.update(valeur))
            d["FICHIER_ECHECS"] = "echecs.json"
            return d
        m.deps = deps
        m.lancer([entree()])
        m.lancer([entree()])
        self.assertEqual(1, m.admin.send.await_count)
        self.assertEqual(2, echecs["lien-test"]["n"])
        m.lien_pour = AsyncMock(return_value=(URL, ""))
        self.assertEqual(["lien-test"], m.lancer([entree()]))
        self.assertIn("après 3 essais", m.admin.send.await_args.args[0])
        self.assertNotIn("lien-test", echecs)
