"""27/10 (Gaëtan : « envoie son application clippeur à Esperance ») : un message déposé `"app": true` envoie l'app du clipper dans
son salon perso par le chemin de `!app @clipper` (parcours.livrer_app forcé), sans que le lien personnel passe par le dépôt.
1. App envoyée : tracée une fois, ligne admin, jamais deux fois.
2. App pas envoyée (aucun lien, app inconnue, exception) : rien de tracé, la raison va à l'admin, retenté au démarrage suivant.
3. Sans salon perso : l'envoi d'app n'est jamais appelé.
4. L'entrée du dépôt est bien formée et ne contient aucun lien.
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


def salon(nom):
    return N(name=nom, id=hash(nom) % 10**6, mention=f"#{nom}", send=AsyncMock())


class Monde:
    def __init__(self, avec_salon=True, resultat=("envoye", "envoye"), exception=None):
        self.membre = N(id=42, display_name="Esperance - Chloé")
        self.perso = salon("esperance") if avec_salon else None
        self.admin = salon("admin")
        self.traces = {}
        self.app_pour = AsyncMock(return_value=resultat, side_effect=exception)
        self.client = N(wait_until_ready=AsyncMock(), user=N(), guilds=[])

    def lancer(self, entrees):
        deps = {"lire_json": lambda chemin, defaut: self.traces, "ecrire_json": lambda chemin, valeur: self.traces.update(valeur),
                "FICHIER": "traces.json", "chercher_membre": lambda ref, exact=True: self.membre if ref == "Esperance" else None,
                "salon_perso": lambda uid: self.perso if uid == 42 else None, "canal_admin": AsyncMock(return_value=self.admin),
                "app_pour": self.app_pour}
        with tempfile.TemporaryDirectory() as tmp:
            dep = Path(tmp) / "messages_a_envoyer.json"
            dep.write_text(json.dumps(entrees, ensure_ascii=False), encoding="utf-8")
            with patch.object(messages_deposes, "FICHIER_REPO", dep), patch.dict(messages_deposes._deps, deps, clear=True):
                return asyncio.run(messages_deposes.envoyer_au_demarrage(self.client))


ENTREE = {"id": "app-test", "pour": "Esperance", "app": True}


class AppDeposee(unittest.TestCase):
    def test_entree_sans_texte_acceptee(self):
        with tempfile.TemporaryDirectory() as tmp:
            dep = Path(tmp) / "m.json"
            dep.write_text(json.dumps([ENTREE, {"id": "vide", "app": True}]), encoding="utf-8")
            with patch.object(messages_deposes, "FICHIER_REPO", dep):
                self.assertEqual([e["id"] for e in messages_deposes.lire_deposes()], ["app-test"])   # « app » demande « pour »

    def test_app_envoyee_une_fois_et_tracee(self):
        m = Monde()
        self.assertEqual(m.lancer([ENTREE]), ["app-test"])
        m.app_pour.assert_awaited_once_with(m.membre, m.perso)
        self.assertTrue(m.traces["app-test"]["app"])
        self.assertIn("envoyée", m.admin.send.await_args.args[0])
        m.perso.send.assert_not_awaited()                     # le message part par livrer_app, pas par le dépôt
        m2 = Monde()
        m2.traces["app-test"] = {"date": "2026-10-27T04:00:00+00:00"}
        self.assertEqual(m2.lancer([ENTREE]), [])
        m2.app_pour.assert_not_awaited()

    def test_app_pas_envoyee_la_raison_va_a_l_admin(self):
        m = Monde(resultat=("sans_lien", "aucun lien GAML à son nom"))
        self.assertEqual(m.lancer([ENTREE]), [])
        self.assertEqual(m.traces, {})
        texte = m.admin.send.await_args.args[0]
        self.assertIn("aucun lien GAML à son nom", texte)
        self.assertIn("prochain démarrage", texte)

    def test_exception_meme_traitement(self):
        m = Monde(exception=RuntimeError("Discord en panne"))
        self.assertEqual(m.lancer([ENTREE]), [])
        self.assertEqual(m.traces, {})
        self.assertIn("Discord en panne", m.admin.send.await_args.args[0])

    def test_sans_salon_perso_rien_n_est_appele(self):
        m = Monde(avec_salon=False)
        self.assertEqual(m.lancer([ENTREE]), [])
        m.app_pour.assert_not_awaited()
        self.assertEqual(m.traces, {})


class EntreeDuDepot(unittest.TestCase):
    def test_entree_esperance(self):
        deposes = json.loads((ROOT / "messages_a_envoyer.json").read_text(encoding="utf-8"))
        e = [x for x in deposes if x["id"] == "app-esperance-2710"]
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["pour"], "Esperance")
        self.assertIs(e[0]["app"], True)
        self.assertNotIn("http", json.dumps(e[0]))               # jamais le lien personnel de l'app dans le dépôt
        self.assertNotIn("texte", e[0])


if __name__ == "__main__":
    unittest.main()
