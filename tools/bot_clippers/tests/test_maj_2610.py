"""26/10 (Gaëtan : « update, améliore, simplifie », logs du 24 au 26/10) : parrainage à 500 visites, sortie tenue au registre et
au roster, sortie déposée d'un parti faite à distance, organigramme sans les sortis, audit aligné sur `!acces`. Données fictives."""
import asyncio
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equipes_tl  # noqa: E402
import parrainage  # noqa: E402
from test_assistant_simplifie_1810 import extraire, normaliser  # noqa: E402


class ParrainageTests(unittest.TestCase):
    def setUp(self):
        self.d = {"filleuls": {"f1": {"parrain": "p1", "date": "2026-10-20T10:00:00+00:00", "periode": ""}}}
        parrainage._deps.clear()
        parrainage.configurer({"lire_json": lambda f, d: self.d, "ecrire_json": lambda f, d: self.d.update(d),
                               "FICHIER": "p.json", "prenom_de": lambda m: getattr(m, "display_name", "X").split(" - ")[0],
                               "est_staff": lambda m: getattr(m, "staff", False),
                               "est_staff_ou_tl": lambda m: getattr(m, "staff", False) or getattr(m, "tl", False)})
        parrainage.SEUIL_VISITES, parrainage.PRIME_USD, parrainage.ACTIF = 500, 10.0, True

    def test_prime_a_500_visites_pas_avant(self):
        self.assertEqual([], parrainage.primes_dues({"f1": 12.0}, "2026-11-05", {"f1": 240}))
        self.assertEqual("", self.d["filleuls"]["f1"]["periode"])
        self.assertEqual([("p1", "f1", 10.0)], parrainage.primes_dues({"f1": 25.0}, "2026-11-05", {"f1": 500}))
        self.assertEqual("2026-11-05", self.d["filleuls"]["f1"]["periode"])
        self.assertEqual([], parrainage.primes_dues({"f1": 30.0}, "2026-11-20", {"f1": 600}))   # une seule fois

    def test_tl_enregistre_les_deux(self):
        from datetime import datetime, timezone
        ancien = SimpleNamespace(id=1, display_name="Ancien - Sarah", bot=False, joined_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
        nouveau = SimpleNamespace(id=2, display_name="Nouveau - Sarah", bot=False, joined_at=datetime(2026, 10, 25, tzinfo=timezone.utc))
        tl = SimpleNamespace(id=3, display_name="Yves - Sarah - TL Sarah", tl=True, bot=False)
        message = SimpleNamespace(author=tl, mentions=[nouveau, ancien], reply=AsyncMock())
        asyncio.run(parrainage.commande(message, "!parrain @Nouveau @Ancien"))
        self.assertEqual("1", self.d["filleuls"]["2"]["parrain"])
        self.assertIn("500 visites payées", message.reply.await_args.args[0])
        self.assertIn("10 $", message.reply.await_args.args[0])


class SortieTests(unittest.TestCase):
    def test_sortir_membre_tient_le_registre_des_sortis_et_le_roster(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        corps = src[src.index("async def sortir_membre("):src.index("\ndef ", src.index("async def sortir_membre(") + 10)]
        self.assertIn("ecrire_json(FICHIER_SORTIS", corps)
        self.assertIn("roster.retirer(prenom)", corps)
        self.assertIn("roster.marquer_traite(prenom)", corps)

    def test_uid_parti_un_seul_candidat_hors_serveur(self):
        registre = {"10": {"prenom": "Stéphane", "creatrice": "Maddie", "date": "2026-09-20"},
                    "11": {"prenom": "Lucas", "creatrice": "Chloé", "date": "2026-10-01"}}
        clics = {"liens": {"l1": {"uid": "10", "note": "Clipping Stéphane", "creatrice": "Maddie"}}}
        ns = extraire("bot_discord.py", {"uid_parti"}, {
            "normaliser": normaliser, "roster": SimpleNamespace(resoudre_alias=lambda x: x),
            "client": SimpleNamespace(guilds=[SimpleNamespace(members=[SimpleNamespace(id=11)])]),
            "lire_json": lambda f, d: registre if f == "equipes" else {"clippers": {}},
            "FICHIER_EQUIPES": "equipes", "FICHIER_ONBOARDING": "onb",
            "paie_clics": SimpleNamespace(actif=lambda: True, _lire=lambda: clics,
                                          _prenom_note=lambda n: re.sub(r"^Clipping ", "", str(n or "")))})
        self.assertEqual("10", ns["uid_parti"]("stephane", "Maddie", "2026-10-24"))
        self.assertEqual("", ns["uid_parti"]("lucas", None, None))              # encore sur le serveur
        self.assertEqual("", ns["uid_parti"]("stephane", "Chloé", None))         # pas sa créatrice

    def test_depot_d_un_parti_clos_au_premier_passage(self):
        import roster
        ancien = dict(roster._deps)
        roster._deps.update(sortir_depose=AsyncMock(), chercher_prenom=lambda *a, **k: None,
                            sortir_parti=AsyncMock(return_value=["🚪 Stéphane : déjà parti(e) du serveur, sortie faite à distance · 1 lien(s) GAML libéré(s)"]),
                            FICHIER_SORTIS="s.json", lire_json=lambda f, d: [])
        try:
            lignes, faite = asyncio.run(roster._expulser_depose({"expulser": True, "creatrice": "Maddie"}, "Stéphane", "viré",
                                                                 client=SimpleNamespace(guilds=[]), premier="2026-10-24"))
        finally:
            roster._deps.clear()
            roster._deps.update(ancien)
        self.assertTrue(faite)
        self.assertIn("déjà parti(e)", lignes[0])


class OrganigrammeTests(unittest.TestCase):
    def test_sorti_passe_sans_bruit(self):
        ancien = dict(equipes_tl._deps)
        fiches = {"1": {"prenom": "Mathieu"}, "2": {"prenom": "Thia"}}
        sortis = [{"uid": "9", "nom": "Alvaro - Sophie"}]
        equipes_tl._deps.update(lire_json=lambda f, d: sortis if f == "sortis" else fiches, FICHIER_EQUIPES="eq", FICHIER_SORTIS="sortis")
        try:
            va = equipes_tl.organigramme_va("mathieu:alvaro,thia,inconnu", fiches)
        finally:
            equipes_tl._deps.clear()
            equipes_tl._deps.update(ancien)
        self.assertEqual({"2": "1"}, va)
        self.assertEqual(["Alvaro"], equipes_tl._ORGA["sortis"])
        self.assertEqual(["Inconnu"], equipes_tl._ORGA["inconnus"])


class AuditTests(unittest.TestCase):
    def test_reporting_public_quand_le_serveur_est_ferme(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn('noms_reserves = tuple(n for n in NOMS_RESERVES if n != "reporting") if serveur_ferme() else NOMS_RESERVES', src)
        self.assertIn("any(m in n for m in noms_reserves)", src)


class ConnaissancesTests(unittest.TestCase):
    def test_primes_annoncees(self):
        kb = (ROOT / "connaissances.md").read_text(encoding="utf-8")
        for morceau in ("La prime volume, c'est quoi ?", "+10 $", "+20 $", "+30 $", "500 visites payées", "10 $ pour le parrain",
                        "Discord me demande une vérification", "L'app est en maintenance ?"):
            self.assertIn(morceau, kb)
        self.assertNotIn("5 $ pour toi le jour de sa première paie", kb)


if __name__ == "__main__":
    unittest.main()


class AcquiescementTests(unittest.TestCase):
    def test_c_est_bon_et_ca_y_est_sans_reponse(self):
        ns = extraire("bot_discord.py", {"ACQUIESCEMENTS", "est_acquiescement"}, {"re": re, "normaliser": normaliser})
        for t in ("C'est bon", "ça y est", "c'est fait 👍", "ok merci"):
            self.assertTrue(ns["est_acquiescement"](t), t)
        for t in ("c'est bon ?", "Mon compte 2 est ban", "Compte 2"):
            self.assertFalse(ns["est_acquiescement"](t), t)


class SalonsSortisTests(unittest.TestCase):
    def test_commandes_et_audit_branches(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn('texte.startswith("!archiver-sortis")', src)
        self.assertLess(src.index('texte.startswith("!archiver-sortis")'), src.index('    if texte.startswith("!archiver"):'))
        self.assertIn("Salons de sortis encore sous leur créatrice", src)
        self.assertIn("rangé dans 🗄️ Archives (historique gardé)", src)
