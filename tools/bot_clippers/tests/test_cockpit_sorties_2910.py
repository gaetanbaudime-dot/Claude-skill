"""29/10 (Gaëtan : « Sortie automatique » quand il passe quelqu'un en « Sorti » dans le Cockpit Clipping) : l'onglet « Équipe
clipping » du LOG DASHBOARD est lu, chaque « Sorti » qui désigne un clipper actif reçoit la sortie complète, une seule fois.
Cas fictifs, sans réseau ni Discord."""
import asyncio
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cockpit_sorties as cs  # noqa: E402

MAINTENANT = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)
ENTETE = ["Prénom", "Créatrice", "Team Leader", "Rôle", "Clippe pour", "France", "Note"]


def ligne(prenom, creatrice, role, note=""):
    return [prenom, creatrice, "sans TL", role, creatrice, "FALSE", note]


class PursTests(unittest.TestCase):
    def test_colonnes_par_entete(self):
        valeurs = [["Note", "Rôle", "Prénom", "Créatrice"], ["viré", "Sorti", "Démo", "Sophie"], ["", "", "", ""]]
        self.assertEqual([{"prenom": "Démo", "creatrice": "Sophie", "role": "Sorti", "note": "viré"}], cs.lignes_equipe(valeurs))
        self.assertEqual([], cs.lignes_equipe([["Nom", "Statut"], ["x", "Sorti"]]), "onglet changé : rien")

    def test_trace_premier_vu_close_et_oubli(self):
        lignes = cs.lignes_equipe([ENTETE, ligne("Démo", "Sophie", "Sorti"), ligne("Autre", "Sarah", "Clipper"),
                                   ligne("Vieux", "Chloé", "Sorti")])
        trace0 = {"vieux|chloe": {"premier": "2026-10-20T08:00:00+00:00", "fait": True},
                  "remis|sarah": {"premier": "2026-10-25T08:00:00+00:00", "fait": True}}
        trace, examen = cs.a_examiner(lignes, trace0, MAINTENANT)
        self.assertEqual(["demo|sophie"], [e["cle"] for e in examen], "la ligne close ne rejoue pas")
        self.assertEqual("2026-10-29T09:00:00+00:00", trace["demo|sophie"]["premier"])
        self.assertNotIn("remis|sarah", trace, "remis en Clipper : la décision est oubliée")
        self.assertTrue(trace["vieux|chloe"]["fait"])

    def test_signe_avant_le_lendemain(self):
        self.assertEqual("2026-10-30", cs.limite_signature("2026-10-29T09:00:00+00:00"))


class Membre:
    def __init__(self, uid):
        self.id = uid


class PasseTests(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        self.fichiers = {}
        self.sortis, self.notes, self.recherches = [], [], []
        self.membres = {("benn", "sophie"): Membre(1), ("meiji", ""): Membre(3)}
        self.registre = {"1": {"creatrice": "Sophie"}, "3": {}}
        self.valeurs = [ENTETE, ligne("Benn", "Sophie", "Sorti"), ligne("Meiji", "Chloé", "Sorti", "Viré le 20/10"),
                        ligne("Ancien", "Sarah", "Sorti"), ligne("Thia", "Sophie", "Clipper")]

        def lire_json(chemin, defaut):
            if str(chemin).endswith("equipes.json"):
                return self.registre
            return self.fichiers.get(str(chemin), defaut)

        def ecrire_json(chemin, valeur):
            self.fichiers[str(chemin)] = valeur

        def chercher(prenom, creatrice=None, signe_avant=None):
            self.recherches.append((prenom, creatrice, signe_avant))
            return self.membres.get((cs._n(prenom), cs._n(creatrice)))

        async def sortir(membre, raison, metricool=False):
            self.sortis.append((membre.id, raison, metricool))
            return {"expulse": True, "comptes": 3, "liens": 1}

        async def notifier(texte, guild):
            self.notes.append(texte)

        cs._deps.clear()
        cs.configurer({"DONNEES": self.dossier, "lire_json": lire_json, "ecrire_json": ecrire_json, "notifier": notifier,
                       "FICHIER_EQUIPES": "equipes.json", "chercher_prenom": chercher, "sortir_depose": sortir})

    def passer(self):
        async def sheets_lire(cid, plage):
            self.assertIn("Équipe clipping", plage)
            return self.valeurs
        faux_google = types.SimpleNamespace(actif=lambda: True, sheets_lire=sheets_lire)
        faux_onb = types.SimpleNamespace(CLASSEUR_LOGINS_ID="demo", onglet_a1=lambda o: f"'{o}'")
        client = types.SimpleNamespace(guilds=[])
        with patch.dict(sys.modules, {"google_api": faux_google, "onboarding": faux_onb}), \
                patch.object(cs, "datetime", wraps=datetime) as faux_dt:
            faux_dt.now.return_value = MAINTENANT
            return asyncio.run(cs.passe(client))

    def test_vires_sortis_une_seule_fois(self):
        bilan = self.passer()
        self.assertEqual([1, 3], sorted(x[0] for x in self.sortis), "Benn et Meiji (sans créatrice au registre)")
        self.assertTrue(all(not m for _, _, m in self.sortis), "comptes au vivier, pas Metricool")
        self.assertIn("Cockpit Clipping", self.sortis[0][1])
        self.assertEqual(2, len(bilan))
        self.assertTrue(self.notes and "Sorties du Cockpit" in self.notes[0])
        trace = self.fichiers[str(self.dossier / "cockpit_sorties.json")]
        self.assertTrue(trace["ancien|sarah"]["fait"], "aucun clipper actif : close sans rien toucher")
        self.assertEqual("2026-10-30", self.recherches[0][2], "jamais un signé après le jour où la ligne a été vue")
        self.sortis.clear()
        self.passer()
        self.assertEqual([], self.sortis, "une ligne close ne rejoue jamais")

    def test_meiji_avec_une_creatrice_au_registre_n_est_pas_pris_sans_elle(self):
        self.registre["3"] = {"creatrice": "Sarah"}
        self.passer()
        self.assertEqual([1], [x[0] for x in self.sortis])

    def test_trop_de_sorties_d_un_coup_rien_n_est_fait(self):
        self.valeurs = [ENTETE] + [ligne(f"Demo{i}", "Sophie", "Sorti") for i in range(cs.MAX_PAR_PASSE + 1)]
        self.membres = {(f"demo{i}", "sophie"): Membre(10 + i) for i in range(cs.MAX_PAR_PASSE + 1)}
        bilan = self.passer()
        self.assertEqual([], self.sortis)
        self.assertEqual(1, len(bilan))
        self.assertIn("d'un coup", bilan[0])
        self.assertEqual([], self.passer(), "l'alerte ne se répète pas pour la même liste")

    def test_sortie_annulee_retentee_puis_abandonnee(self):
        async def annule(membre, raison, metricool=False):
            return {"annule": "GAML illisible : rien n'a été fait"}
        cs._deps["sortir_depose"] = annule
        self.valeurs = [ENTETE, ligne("Benn", "Sophie", "Sorti")]
        for _ in range(cs.ESSAIS_MAX - 1):
            self.assertEqual([], self.passer())
        bilan = self.passer()
        self.assertIn("abandonnée", bilan[0])
        self.assertIn("!sortie @Benn", bilan[0])

    def test_eteint(self):
        with patch.object(cs, "ACTIF", False):
            self.assertEqual([], self.passer())
        self.assertEqual([], self.sortis)


class BrancheTests(unittest.TestCase):
    def test_boucle_branchee_et_sorties_deposees(self):
        import json
        texte = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("cockpit_sorties.boucle(client)", texte)
        self.assertIn('"chercher_prenom": chercher_sortant', texte.split("cockpit_sorties.configurer", 1)[1][:600])
        depots = {e["id"]: e for e in json.loads((ROOT / "sorties_a_appliquer.json").read_text(encoding="utf-8"))}
        for ident in ("benn-2910", "oumar-2910", "meiji-2910"):
            self.assertTrue(depots[ident]["expulser"])
            self.assertFalse(depots[ident].get("metricool"))
            self.assertEqual("2026-10-28", depots[ident]["signe_avant"])
        self.assertNotIn("creatrice", depots["meiji-2910"], "Meiji n'a pas de créatrice au registre")


if __name__ == "__main__":
    unittest.main()


class ChercherSortantTests(unittest.TestCase):
    """La recherche du sortant (bot_discord.chercher_sortant), extraite du fichier : le prénom de la fiche au registre compte
    aussi (Meiji, pseudo Discord sans son prénom), avec les mêmes garde-fous."""

    def charger(self, membres, registre):
        import ast
        import unicodedata
        texte = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        arbre = ast.parse(texte)
        fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "chercher_sortant")
        norm = lambda t: "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")  # noqa: E731
        ns = {"normaliser": norm, "roster": types.SimpleNamespace(resoudre_alias=lambda c: c),
              "_entree_sortie_deposee": lambda c: {}, "datetime": datetime, "timezone": timezone,
              "lire_json": lambda f, d: registre, "FICHIER_EQUIPES": "equipes.json",
              "client": types.SimpleNamespace(guilds=[types.SimpleNamespace(members=membres)]),
              "prenom_de": lambda m: m.display_name.split(" - ")[0],
              "_clipper_sortable": lambda m, reg: str(m.id) in reg, "role_creatrice": lambda g, c: False,
              "SEPARATEURS_PSEUDO": (" - ",)}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "bot_discord.py", "exec"), ns)
        return ns["chercher_sortant"]

    def membre(self, uid, pseudo):
        return types.SimpleNamespace(id=uid, name=pseudo.lower(), display_name=pseudo, global_name=None, roles=[])

    def test_prenom_de_la_fiche(self):
        m = self.membre(3, "Shadow99")
        chercher = self.charger([m, self.membre(4, "Autre")], {"3": {"prenom": "Meiji", "date": "2026-10-01"}, "4": {"prenom": "Autre"}})
        self.assertIs(m, chercher("Meiji", creatrice="", signe_avant="2026-10-28"))
        self.assertIsNone(chercher("Meiji", creatrice="", signe_avant="2026-09-30"), "signé après le dépôt : pas lui")

    def test_deux_fiches_du_meme_prenom_personne(self):
        chercher = self.charger([self.membre(3, "A1"), self.membre(5, "B2")],
                                {"3": {"prenom": "Meiji"}, "5": {"prenom": "Meiji"}})
        self.assertIsNone(chercher("Meiji", creatrice="", signe_avant="2026-10-28"))

    def test_sans_fiche_jamais(self):
        chercher = self.charger([self.membre(3, "Meiji")], {})
        self.assertIsNone(chercher("Meiji", creatrice="", signe_avant="2026-10-28"), "ni fiche ni rôle : pas un clipper")


class RefusEnCoursTests(PasseTests):
    def test_operation_deja_en_cours_reprise_sans_bilan(self):
        async def en_cours(membre, raison, metricool=False):
            return {"roles": 0, "comptes": 0, "liens": 0, "refus": ["Opération déjà en cours, réessayer"], "expulse": False}
        cs._deps["sortir_depose"] = en_cours
        self.valeurs = [ENTETE, ligne("Benn", "Sophie", "Sorti")]
        self.assertEqual([], self.passer(), "rien n'a été fait : pas de faux bilan au salon admin")
        trace = self.fichiers[str(self.dossier / "cockpit_sorties.json")]
        self.assertFalse(trace["benn|sophie"].get("fait"))
        self.assertEqual(1, trace["benn|sophie"]["essais"])
        self.membres = {}
        self.assertEqual([], self.passer())
        self.assertTrue(self.fichiers[str(self.dossier / "cockpit_sorties.json")]["benn|sophie"]["fait"], "parti : close sans bruit")
