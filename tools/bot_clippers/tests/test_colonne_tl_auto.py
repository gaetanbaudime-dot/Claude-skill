"""24/10 (Jamel) : le TL du clipper est écrit dans la colonne « Team Leader » du classeur, avec les mêmes garde-fous que la lecture."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard  # noqa: E402
import equipes_tl as E  # noqa: E402

FICHES = {
    "1": {"prenom": "Mathieu", "creatrice": "Sophie", "chef": "Sophie"},
    "2": {"prenom": "Jamel", "creatrice": "Sophie"},
    "3": {"prenom": "Pierre", "creatrice": "Sophie"},
    "4": {"prenom": "Clarisse", "creatrice": "Chloé", "chef": "Chloé"},
    "5": {"prenom": "Esperance", "creatrice": "Chloé"},
    "6": {"prenom": "Maddie", "creatrice": "Maddie"},
    "7": {"prenom": "Karim", "creatrice": "Sarah"},
    "8": {"prenom": "Yves", "creatrice": "Sarah", "chef": "Sarah"},
    "9": {"prenom": "Yan", "creatrice": "Sarah", "chef": "Sarah"},
    "10": {"prenom": "Marc", "creatrice": "Sophie", "manager_de": ["Sophie"]},
    "11": {"prenom": "Rianah", "creatrice": "Chloé"},
}


def ligne(gerant, creatrice, n, tl="", **kw):
    return dict({"onglet": creatrice, "ligne": n, "gerant": gerant, "creatrice": creatrice, "tl": tl}, **kw)


class ColonneACompleter(unittest.TestCase):
    def test_les_trois_lignes_de_jamel_recoivent_le_tl_de_sophie(self):
        comptes = [ligne("Jamel", "Sophie", n) for n in (29, 30, 31)]
        r = E.colonne_a_completer(comptes, FICHES)
        self.assertEqual([(29, "Mathieu"), (30, "Mathieu"), (31, "Mathieu")], [(c["ligne"], nom) for c, nom in r])

    def test_une_cellule_remplie_nest_jamais_ecrasee(self):
        comptes = [ligne("Pierre", "Sophie", 26, tl="Autre")]
        self.assertEqual([], E.colonne_a_completer(comptes, FICHES))

    def test_le_tl_de_chloe_est_celui_de_chloe(self):
        r = E.colonne_a_completer([ligne("Esperance", "Chloé", 28)], FICHES)
        self.assertEqual([("Clarisse")], [nom for c, nom in r])

    def test_creatrice_sans_tl_rien_ecrit(self):
        self.assertEqual([], E.colonne_a_completer([ligne("Maddie", "Maddie", 5)], FICHES))

    def test_creatrice_avec_deux_tl_rien_ecrit(self):
        self.assertEqual([], E.colonne_a_completer([ligne("Karim", "Sarah", 5)], FICHES))

    def test_un_tl_ou_un_manager_na_pas_de_tl(self):
        comptes = [ligne("Mathieu", "Sophie", 10), ligne("Marc", "Sophie", 11)]
        self.assertEqual([], E.colonne_a_completer(comptes, FICHES))

    def test_gerant_inconnu_ou_hors_equipe_rien_ecrit(self):
        comptes = [ligne("Rianah (Clipping)", "Sophie", 34), ligne("à mettre Metricool", "Sophie", 5), ligne("", "Sophie", 6),
                   ligne("Jamel", "Chloé", 7)]                          # Jamel est de Sophie : pas sur une ligne de Chloé
        self.assertEqual([], E.colonne_a_completer(comptes, FICHES))

    def test_cellule_fusionnee_ou_exclue_ignoree(self):
        comptes = [ligne("Jamel", "Sophie", 29, fusions={"tl": (29, 31)}), ligne("Jamel", "Sophie", 30)]
        r = E.colonne_a_completer(comptes, FICHES, exclure=lambda c: c["ligne"] == 30)
        self.assertEqual([], r)

    def test_rianah_exclue_de_la_paie_au_clic_na_pas_de_tl(self):
        # 24/10 : « Rianah (Metricool) → Clarisse » écrit à tort sur 6 lignes de Chloé : ses comptes sont ceux de l'agence
        comptes = [ligne("Rianah (Metricool)", "Chloé", 23), ligne("Rianah Clipping Chloé", "Chloé", 7), ligne("Rianah Metricool", "Chloé", 9)]
        with patch.dict(E._deps, {"exclus": ["Rianah"]}):
            self.assertEqual([], E.colonne_a_completer(comptes, FICHES))
        self.assertEqual(3, len(E.colonne_a_completer(comptes, FICHES)))        # sans l'exclusion, rien ne l'arrêtait : le test garde le piège

    def test_regime_fixe_na_pas_de_tl(self):
        with patch.dict(E._deps, {"regime": lambda uid: "fixe" if str(uid) == "2" else "clic"}):
            self.assertEqual([], E.colonne_a_completer([ligne("Jamel", "Sophie", 29)], FICHES))
            self.assertEqual(1, len(E.colonne_a_completer([ligne("Pierre", "Sophie", 26)], FICHES)))

    def test_plafond_par_passage(self):
        comptes = [ligne("Jamel", "Sophie", n) for n in range(2, 60)]
        self.assertEqual(30, len(E.colonne_a_completer(comptes, FICHES)))
        self.assertEqual(5, len(E.colonne_a_completer(comptes, FICHES, plafond=5)))

    def test_le_prenom_ecrit_est_relu_comme_le_meme_tl_par_la_colonne(self):
        comptes = [ligne("Jamel", "Sophie", 29, handle="x")]
        (c, nom), = E.colonne_a_completer(comptes, FICHES)
        c["tl"] = nom
        lu = E.lire_colonne(comptes, {}, None, FICHES)
        self.assertEqual({"2": "1"}, lu["va"])


class EcritureDashboard(unittest.IsolatedAsyncioTestCase):
    async def test_ecrit_une_fois_et_remplit_les_lignes_lues(self):
        comptes = [ligne("Jamel", "Sophie", n, handle=f"j{n}") for n in (29, 30, 31)] + [ligne("Sophie", "Sophie", 2, utilisation="Compte de la créatrice")]
        faux = AsyncMock(return_value=3)
        with patch.object(dashboard.google_api, "sheets_ecrire_plusieurs", faux), \
             patch.object(dashboard.onboarding, "a_colonne", return_value=True), \
             patch.object(E, "_fiches", return_value=FICHES):
            n = await dashboard._completer_colonne_tl(E, comptes)
        self.assertEqual(3, n)
        ecritures = faux.await_args.args[1]
        self.assertEqual(3, len(ecritures))
        self.assertTrue(all(v == [["Mathieu"]] for _, v in ecritures))
        self.assertEqual(["Mathieu"] * 3, [c["tl"] for c in comptes[:3]])
        self.assertEqual("", comptes[3]["tl"])

    async def test_interrupteur_tl_colonne_auto(self):
        faux = AsyncMock()
        with patch.dict(os.environ, {"TL_COLONNE_AUTO": "0"}), patch.object(dashboard.google_api, "sheets_ecrire_plusieurs", faux):
            n = await dashboard._completer_colonne_tl(E, [ligne("Jamel", "Sophie", 29)])
        self.assertEqual(0, n)
        faux.assert_not_awaited()

    async def test_colonne_absente_de_longlet_rien_ecrit(self):
        faux = AsyncMock()
        with patch.object(dashboard.google_api, "sheets_ecrire_plusieurs", faux), \
             patch.object(dashboard.onboarding, "a_colonne", return_value=False), \
             patch.object(E, "_fiches", return_value=FICHES):
            n = await dashboard._completer_colonne_tl(E, [ligne("Jamel", "Sophie", 29)])
        self.assertEqual(0, n)
        faux.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
