"""24/10 (Gaëtan : « Rianah Metricool, Rianah clipping Chloé, Rianah clipping Sarah : comme trois personnes, le même compte
Discord ») : un salon de clipping par créatrice, ses comptes un par un toutes les 48 h dans CE salon, `!pseudo` qui vise ses
comptes de cette créatrice, trois places à vie par identité, et le dépôt qui range ses trios. Données fictives uniquement."""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import identites_clipping
import onboarding
import parcours
import process_store


def extraire(fichier, noms, namespace):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms)
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in noms for t in n.targets))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=corps, type_ignores=[])), fichier, "exec"), namespace)
    return namespace


class PlacesParIdentite(unittest.TestCase):
    def tearDown(self):
        process_store.identites_de = process_store._identites

    def test_trois_places_par_defaut_six_avec_un_salon_de_clipping(self):
        self.assertEqual(3, process_store.places_a_vie("1"))
        process_store.identites_de = lambda uid: 2
        self.assertEqual(6, process_store.places_a_vie("1"))
        process_store.identites_de = lambda uid: (_ for _ in ()).throw(ValueError())
        self.assertEqual(3, process_store.places_a_vie("1"))            # une erreur ne donne jamais plus de places

    def test_reserve_suit_les_places_de_l_identite(self):
        with tempfile.TemporaryDirectory() as d:
            store = process_store.Store(Path(d) / "s.sqlite3")
            store.reconcile("7", [{"aliases": [f"fictif{i}"], "status": "created"} for i in range(3)], "test")
            with self.assertRaises(process_store.Bloque):
                store.reserve("7", ["fictif-quatre"])
            process_store.identites_de = lambda uid: 2
            store.reserve("7", ["fictif-quatre", "fictif-cinq", "fictif-six"])
            with self.assertRaises(process_store.Bloque):
                store.reserve("7", ["fictif-sept"])


class SalonDedie(unittest.IsolatedAsyncioTestCase):
    def etat(self, donnes=1, dernier=None, cree=True):
        return {"clippers": {"42": {"comptes": ["compte-a"], "telephones": {"Fictive": {
            "acces": [{"handle": "fictif-un", "mdp": secrets.token_hex(8), "mail": "a@exemple.invalid", "cree": True},
                      {"handle": "fictif-deux", "mdp": secrets.token_hex(8), "mail": "b@exemple.invalid", "cree": cree},
                      {"handle": "fictif-prive", "mdp": secrets.token_hex(8), "mail": "c@exemple.invalid", "prive": True,
                       "cree": False}],
            "donnes": donnes, "dernier": dernier or "2020-01-01T00:00:00+00:00", "lien": "https://exemple.invalid/8"}}}},
            "livres": {}}

    async def passer(self, etat, salon_dedie, maintenant=None):
        def ecrire(d):
            etat.clear(); etat.update(deepcopy(d))
        principal = SimpleNamespace(send=AsyncMock())
        membre = SimpleNamespace(mention="<@42>", send=AsyncMock())
        with patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(etat)), \
             patch.object(onboarding, "_ecrire_etat", side_effect=ecrire), \
             patch.object(onboarding, "lien_autre_creatrice", AsyncMock(return_value="")), \
             patch.object(onboarding, "lien_drive_creatrice", AsyncMock(return_value="")), \
             patch.object(parcours, "_onb", side_effect=lambda uid: deepcopy(etat)["clippers"].get(str(uid), {})), \
             patch.dict(onboarding._deps, {"salon_perso": lambda uid: principal, "membre_par_id": lambda uid: membre,
                                           "salon_telephone": lambda uid, c: salon_dedie,
                                           "lire_json": lambda *_: {}, "FICHIER_ONBOARDING": Path("/tmp/x.json")}):
            n = await onboarding.donner_telephones("42", maintenant=maintenant)
        return n, principal

    async def test_compte_suivant_dans_son_salon_sans_secret(self):
        etat = self.etat()
        secrets_ = [a["mdp"] for a in etat["clippers"]["42"]["telephones"]["Fictive"]["acces"]]
        salon = SimpleNamespace(send=AsyncMock())
        n, principal = await self.passer(etat, salon)
        self.assertEqual(1, n)
        principal.send.assert_not_awaited()                             # rien dans le salon principal
        texte = salon.send.await_args.args[0]
        self.assertIn("Fictive · ton compte 2", texte)
        self.assertIn("ton téléphone Fictive", texte)
        self.assertNotIn("2e téléphone", texte)
        self.assertFalse(any(s in texte for s in secrets_ + ["a@exemple.invalid", "b@exemple.invalid"]))
        t = etat["clippers"]["42"]["telephones"]["Fictive"]
        self.assertEqual(2, t["donnes"])

    async def test_48_heures_entre_deux_comptes(self):
        maintenant = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        etat = self.etat(dernier=(maintenant - timedelta(hours=47)).isoformat())
        salon = SimpleNamespace(send=AsyncMock())
        n, _ = await self.passer(etat, salon, maintenant=maintenant)
        self.assertEqual(0, n)
        salon.send.assert_not_awaited()

    async def test_prive_a_creer_part_avec_son_lien(self):
        etat = self.etat(donnes=2)
        salon = SimpleNamespace(send=AsyncMock())
        n, _ = await self.passer(etat, salon)
        self.assertEqual(1, n)
        texte = salon.send.await_args.args[0]
        self.assertIn("le privé", texte)
        self.assertIn("https://exemple.invalid/8", texte)              # le lien déjà attribué de cette créatrice
        self.assertEqual(3, etat["clippers"]["42"]["telephones"]["Fictive"]["donnes"])

    async def test_sans_salon_dedie_la_file_heritee_reste_retenue(self):
        etat = self.etat()
        n, principal = await self.passer(etat, None)
        self.assertEqual(0, n)
        principal.send.assert_not_awaited()
        self.assertEqual("humaine_requise", etat["clippers"]["42"]["telephones"]["Fictive"]["remise_securisee"]["etat"])


class PseudoDansLeSalonDeClipping(unittest.IsolatedAsyncioTestCase):
    async def test_pseudo_vise_les_comptes_de_la_creatrice_du_salon(self):
        message = SimpleNamespace(author=SimpleNamespace(id=42), mentions=[], channel=SimpleNamespace(id=777), reply=AsyncMock())
        with patch.dict(parcours._deps, {"est_staff": lambda m: False, "creatrice_du_salon": lambda uid, sid: "Fictive"
                                         if sid == 777 else "", "salon_perso": lambda uid: SimpleNamespace(id=1)}), \
             patch.object(parcours, "renommer_telephone", AsyncMock(return_value=("fictif-un", ""))) as tel, \
             patch.object(parcours, "renommer", AsyncMock(return_value=("x", ""))) as principal:
            await parcours.commande_pseudo(message, "!pseudo 1 fictif.vrai")
        tel.assert_awaited_once_with("42", "Fictive", 1, "fictif.vrai")
        principal.assert_not_awaited()
        self.assertIn("ton compte 1 Fictive", message.reply.await_args.args[0])

    async def test_pseudo_dans_le_salon_principal_inchange(self):
        message = SimpleNamespace(author=SimpleNamespace(id=42), mentions=[], channel=SimpleNamespace(id=1), reply=AsyncMock())
        with patch.dict(parcours._deps, {"est_staff": lambda m: False, "creatrice_du_salon": lambda uid, sid: "",
                                         "salon_perso": lambda uid: SimpleNamespace(id=1)}), \
             patch.object(parcours, "renommer_telephone", AsyncMock()) as tel, \
             patch.object(parcours, "renommer", AsyncMock(return_value=("x", ""))) as principal:
            await parcours.commande_pseudo(message, "!pseudo 2 fictif.vrai")
        principal.assert_awaited_once_with("42", 2, "fictif.vrai")
        tel.assert_not_awaited()

    async def test_renommer_telephone_choisit_le_bon_compte(self):
        onb = {"telephones": {"Fictive": {"acces": [{"handle": "fictif-un"}, {"handle": "fictif-deux"}]},
                              "Autre": {"acces": [{"handle": "autre-un"}]}}}
        with patch.object(parcours, "_onb", return_value=onb), \
             patch.object(onboarding, "renommer_compte", AsyncMock(return_value="")) as ren, \
             patch.dict(parcours._deps, {"canal_admin": None}):
            ancien, raison = await parcours.renommer_telephone("42", "fictive", 2, "fictif.nouveau")
        self.assertEqual(("fictif-deux", ""), (ancien, raison))
        ren.assert_awaited_once_with("42", "fictif-deux", "fictif.nouveau")


class NomDuSalon(unittest.TestCase):
    def test_nom_fixe_au_registre(self):
        reg = {"42": {"salon_nom": "fictive-clipping-chloé"}}
        ns = extraire("bot_discord.py", {"nom_salon_cible", "_slug_salon"},
                      {"re": re, "lire_json": lambda *_: reg, "FICHIER_EQUIPES": "x"})
        self.assertEqual("fictive-clipping-chloé", ns["nom_salon_cible"](None, SimpleNamespace(id=42)))

    def test_creatrice_du_salon(self):
        reg = {"42": {"salons_clipping": {"Fictive": "777"}}}
        ns = extraire("bot_discord.py", {"_salons_clipping", "creatrice_du_salon_clipping"},
                      {"lire_json": lambda *_: reg, "FICHIER_EQUIPES": "x"})
        self.assertEqual("Fictive", ns["creatrice_du_salon_clipping"]("42", 777))
        self.assertEqual("", ns["creatrice_du_salon_clipping"]("42", 1))


class DepotTrios(unittest.IsolatedAsyncioTestCase):
    def lignes(self):
        def l(onglet, i, handle, gerant, etat="GOOD", utilisation="Clipper"):
            return {"onglet": onglet, "ligne": i, "handle": handle, "gerant": gerant, "etat": etat, "utilisation": utilisation,
                    "mdp": "x", "mail": f"{handle}@exemple.invalid"}
        return [l("Fictive", 2, "fictif-un", "Prenom Clipping Fictive"),
                l("Fictive", 3, "fictif-deux", "Prenom Clipping Fictive"),
                l("Fictive", 4, "fictif-crame", "Prenom Clipping Fictive"),
                l("Fictive", 5, "fictif-en-trop", "Prenom Clipping Fictive", etat="à créer"),
                l("Fictive", 6, "fictif-prive", "", etat="à créer"),
                l("Fictive", 7, "fictif-metricool", "Prenom Metricool")]

    async def test_trio_gerant_ban_et_stock(self):
        etat = {"clippers": {"42": {"telephones": {"Fictive": {"acces": [{"handle": "fictif-crame"}], "lien": "l"}}}},
                "livres": {"fictif-crame": {"uid": "42"}, "fictif-en-trop": {"uid": "42"}}}
        ecrit = []

        async def sheets_ecrire(_id, plage, valeurs):
            ecrit.append((plage, valeurs[0][0]))
            return 1

        def ecrire(d):
            etat.clear(); etat.update(deepcopy(d))
        with patch.object(onboarding, "lire_comptes", AsyncMock(return_value=self.lignes())), \
             patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(etat)), \
             patch.object(onboarding, "_ecrire_etat", side_effect=ecrire), \
             patch.object(onboarding, "cellule", side_effect=lambda c, champ: f"{champ}{c['ligne']}"), \
             patch.object(identites_clipping.google_api, "sheets_ecrire", side_effect=sheets_ecrire):
            bilan = await identites_clipping._trio("42", "Prenom", "Fictive", ["fictif-un", "fictif-deux", "fictif-prive"],
                                                   "Principale", {"remis": {"Fictive": 1}, "ban": ["fictif-crame"]})
        self.assertIn(("gerant6", "Prenom Clipping Fictive"), ecrit)
        self.assertIn(("gerant4", ""), ecrit)
        self.assertIn(("etat4", "BAN"), ecrit)
        self.assertIn(("gerant5", ""), ecrit)
        self.assertFalse(any(p.endswith("7") for p, _ in ecrit))         # la ligne Metricool n'est jamais touchée
        t = etat["clippers"]["42"]["telephones"]["Fictive"]
        self.assertEqual(["fictif-un", "fictif-deux", "fictif-prive"], [a["handle"] for a in t["acces"]])
        self.assertTrue(t["acces"][2]["prive"])
        self.assertEqual((1, "l"), (t["donnes"], t["lien"]))
        self.assertNotIn("fictif-crame", etat["livres"])
        self.assertEqual("42", etat["livres"]["fictif-prive"]["uid"])
        self.assertTrue(any("rendus au stock" in b for b in bilan))

    async def test_trio_refuse_un_compte_metricool(self):
        with patch.object(onboarding, "lire_comptes", AsyncMock(return_value=self.lignes())), \
             patch.object(identites_clipping.google_api, "sheets_ecrire", AsyncMock()) as ecrire:
            bilan = await identites_clipping._trio("42", "Prenom", "Fictive", ["fictif-un", "fictif-metricool", "fictif-prive"],
                                                   "Principale", {})
        ecrire.assert_not_awaited()
        self.assertIn("Metricool", bilan[0])


if __name__ == "__main__":
    unittest.main()


class ReserveUnique(unittest.IsolatedAsyncioTestCase):
    def test_lecture_de_l_onglet_unique(self):
        import reserve_mym
        brut = [["Fictive", "MYM", "CLIP-FICTIVE-MYM-001", "https://mym.fans/app/t/fictif1"],
                ["Fictive", "OF", "CLIP-FICTIVE-OF-001", "https://onlyfans.com/fictive/c1", "https://exemple.invalid/3", "Prenom", "24/10/2026"],
                ["Fictive", "", "", "https://onlyfans.com/fictive/c2"],      # plateforme déduite de l'adresse
                ["Fictive", "MYM", "", "https://onlyfans.com/fictive/c9"],   # mauvaise plateforme : ignorée
                ["", "MYM", "", "https://mym.fans/app/t/sans-creatrice"]]
        lignes = reserve_mym.lignes_reserve_depuis(brut)
        self.assertEqual([(2, "mym", ""), (3, "of", "https://exemple.invalid/3"), (4, "of", "")],
                         [(l["ligne"], l["kind"], l["pose"]) for l in lignes])

    async def test_capacite_prend_la_premiere_ligne_libre_de_la_creatrice(self):
        import paie_clics
        import process_adapters
        import reserve_mym
        liste = type("Liste", (list,), {"complete": True})([{"id": "m1", "name": "Fictive"}])
        u = [{"ligne": 2, "creatrice": "Autre", "kind": "mym", "url": "https://mym.fans/app/t/autre", "pose": ""},
             {"ligne": 3, "creatrice": "Fictive", "kind": "mym", "url": "https://mym.fans/app/t/pris", "pose": "https://x/1"},
             {"ligne": 4, "creatrice": "fictive", "kind": "mym", "url": "https://mym.fans/app/t/libre", "pose": ""},
             {"ligne": 5, "creatrice": "Fictive", "kind": "of", "url": "https://onlyfans.com/fictive/c5", "pose": ""}]
        store = SimpleNamespace(resource_owner=lambda kind, url: None)
        with patch.object(paie_clics, "liens_de", return_value=[]), patch.object(paie_clics, "_lire", return_value={}), \
             patch.object(paie_clics, "liens_gaml", AsyncMock(return_value=liste)), \
             patch.object(paie_clics, "lien_detail", AsyncMock(return_value={"contents": []})), \
             patch.object(process_adapters.LiensAPI, "_verifier_modele", staticmethod(lambda d: None)), \
             patch.object(process_adapters, "store", return_value=store), \
             patch.object(reserve_mym, "lignes_reserve", AsyncMock(return_value=u)), \
             patch.object(reserve_mym, "lignes", AsyncMock(return_value=[])):
            choix = await process_adapters.LiensAPI("42", []).capacite("Fictive")
        self.assertEqual(("https://mym.fans/app/t/libre", 4, "https://onlyfans.com/fictive/c5", 5, None),
                         (choix["mym"], choix["mym_ligne_u"], choix["of"], choix["of_ligne_u"], choix["mym_ligne"]))


class LienImpose(unittest.IsolatedAsyncioTestCase):
    async def test_lien_impose_sans_reserve(self):
        etat = {"clippers": {"42": {"creatrice": "Fictive", "lien_impose": "https://exemple.invalid/7"}}}
        with patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(etat)), \
             patch.object(onboarding, "_ecrire_etat", side_effect=lambda d: etat.update(deepcopy(d))), \
             patch.object(onboarding.process_adapters, "attribuer", AsyncMock()) as attribuer:
            bilan = await onboarding.attribuer_lien(SimpleNamespace(id=42), "Fictive", creer=True)
            self.assertEqual("https://exemple.invalid/7", bilan["lien"])
            attribuer.assert_not_awaited()
            self.assertTrue(etat["clippers"]["42"]["liens_prets"])
            await onboarding.attribuer_lien(SimpleNamespace(id=42), "Autre", creer=True)
            attribuer.assert_awaited_once()                              # une autre créatrice garde le chemin normal
