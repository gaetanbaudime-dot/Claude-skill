"""31/10, 9 h 28 (Gaëtan : « OUI » — Romaric et Mathieu marqués comme terminés, sans leur envoyer de message). Leurs trois comptes
tournent, leur fiche attendait encore l'étape 3. Cas fictifs, sans réseau, sans Discord, sans classeur."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import corrections as co
import onboarding
import parcours

LOG = [{"handle": "un.fictif", "etat": "BAN", "gerant": "Ancien", "creatrice": "Sophie"},
       {"handle": "deux.fictif", "etat": "APPEL A FAIRE", "gerant": "Ancien", "creatrice": "Sophie"},
       {"handle": "trois.secret_fictif", "etat": "GOOD", "gerant": "Ancien", "creatrice": "Sophie"}]


class ClotureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.parc = {"42": {"prenom": "Ancien", "creatrice": "Sophie", "etape": 3, "salon_id": "7",
                            "dates": {"1": "2026-10-06T08:00:00+00:00", "1_fait": "2026-10-06T09:00:00+00:00",
                                      "2": "2026-10-12T08:00:00+00:00", "2_fait": "2026-10-12T09:00:00+00:00"},
                            "programme": [{"quand": "2026-10-31T04:41:43+00:00", "type": "etape", "n": 3, "ligne": True},
                                          {"quand": "2026-11-01T08:00:00+00:00", "type": "rappel", "n": 0}],
                            "retenue": {"n": 3, "raison": "Historique à vie non rapproché : allocation bloquée"},
                            "ligne_attendue": 3}}
        self.log = deepcopy(LOG)

        def ecrire(d):
            self.parc = deepcopy(d)
        for patcher in (patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.parc)),
                        patch.object(parcours, "_ecrire", side_effect=ecrire),
                        patch.object(parcours, "_comptes_ordonnes", return_value=["un.fictif", "deux.fictif", "trois.secret_fictif"]),
                        patch.object(onboarding, "lire_comptes", AsyncMock(side_effect=lambda: deepcopy(self.log)))):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_passe_en_routine_sans_message(self):
        ligne = await co._cloturer({"prenom": "Ancien", "creatrice": "Sophie"}, "42")
        f = self.parc["42"]
        self.assertEqual(7, f["etape"])
        for cle in ("3", "3_fait", "7"):
            self.assertIn(cle, f["dates"])
        self.assertEqual("2026-10-06T09:00:00+00:00", f["dates"]["1_fait"])      # l'histoire gardée
        self.assertEqual([{"quand": "2026-11-01T08:00:00+00:00", "type": "rappel", "n": 0}], f["programme"])
        for cle in ("retenue", "ligne_attendue", "story_due"):
            self.assertNotIn(cle, f)
        self.assertTrue(f["app"])                                       # il l'a déjà : rattraper_app saute une fiche à « app »
        self.assertTrue(parcours.trois_comptes(f))
        self.assertIn("passé en routine sans message", ligne)
        self.assertEqual([], parcours.retenues_longues(self.parc, parcours.datetime.now(parcours.timezone.utc)))

    async def test_jamais_sans_les_trois_comptes_crees_a_son_nom(self):
        for i, modif in ((2, {"etat": "à créer"}), (1, {"gerant": "Autre"})):
            self.log = deepcopy(LOG)
            self.log[i].update(modif)
            avant = deepcopy(self.parc)
            self.assertIn("rien changé", await co._cloturer({"prenom": "Ancien", "creatrice": "Sophie"}, "42"))
            self.assertEqual(avant, self.parc)

    async def test_jamais_hors_de_l_etape_3_attendue(self):
        self.parc["42"]["dates"].pop("2_fait")
        avant = deepcopy(self.parc)
        self.assertIn("pas l'étape 3 attendue", await co._cloturer({"prenom": "Ancien", "creatrice": "Sophie"}, "42"))
        self.assertEqual(avant, self.parc)

    async def test_branche_et_depot(self):
        import json
        with patch.object(co, "_cloturer", AsyncMock(return_value="🏁 fait")) as cl:
            bilan = await co.appliquer(N(guilds=[]), {"actions": [{"action": "cloturer", "prenom": "Ancien", "creatrice": "Sophie"}]})
        self.assertEqual(["🏁 fait"], bilan)
        self.assertEqual("42", cl.await_args.args[1])
        depot = json.loads(co.FICHIER.read_text(encoding="utf-8"))
        self.assertEqual({("Romaric", "Chloé"), ("Mathieu", "Sophie")},
                         {(x["prenom"], x["creatrice"]) for x in depot["actions"] if x["action"] == "cloturer"})


if __name__ == "__main__":
    unittest.main()
