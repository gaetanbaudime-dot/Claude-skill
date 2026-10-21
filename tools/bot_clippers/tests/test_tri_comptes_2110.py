"""Tri des onglets créatrices du 21/10 (Gaëtan : « les GOOD d'abord, puis les appels à faire, puis les BAN, puis les à créer, sans
casser les pods par clipper »). Cas fictifs, sans réseau."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import classeur_forme  # noqa: E402
import onboarding  # noqa: E402


def ligne(n, etat, handle, gerant="", lien=""):
    return {"ligne": n, "etat": etat, "handle": handle, "gerant": gerant, "lien_gaml": lien, "mail": f"{handle}@x" if handle else "",
            "mdp": "m" if handle else ""}


# Un onglet « Lea » en désordre : le compte de la créatrice, un clipper avec GOOD + BAN + appel + à créer mêlés, un clipper qui n'a
# que des appels, un nouveau (tout à créer), un BAN sans Gérant au milieu, une ligne vide, le stock, un GOOD sans Gérant.
ONGLET = [
    ligne(2, "GOOD", "lea_officiel", "Lea"),
    ligne(3, "à créer", "stock1"),
    ligne(4, "GOOD", "a1", "Alice"),
    ligne(5, "BAN", "a2", "Alice"),
    ligne(6, "à créer", "a3", "Alice"),
    ligne(7, "APPEL A FAIRE", "a4", "Alice"),
    ligne(8, "Faire appel", "b1", "Bruno"),
    ligne(9, "BAN", "vieux_ban"),
    ligne(10, "", ""),
    ligne(11, "à créer", "n1", "Nadia"),
    ligne(12, "à créer", "n2", "Nadia"),
    ligne(13, "GOOD", "orphelin"),
    ligne(14, "GOOD", "c1", "Chris"),
    ligne(15, "à créer", "stock2"),
]


def appliquer(lignes, deplacements):
    courant = [c["ligne"] for c in sorted(lignes, key=lambda c: c["ligne"])]
    for p, t in deplacements:
        courant.insert(t, courant.pop(p))
    return courant


class OrdreCibleTests(unittest.TestCase):
    def test_sections_dans_l_ordre(self):
        cible = onboarding.ordre_cible(ONGLET, "Lea")
        # créatrice, pods avec GOOD (Alice puis Chris, ordre actuel ; dans le pod : GOOD, appel, à créer), le GOOD sans Gérant,
        # le pod en appel (Bruno), le nouveau (Nadia), tous les BAN, le stock, la ligne vide
        self.assertEqual(cible, [2, 4, 7, 6, 14, 13, 8, 11, 12, 5, 9, 3, 15, 10])

    def test_plan_rejoue_donne_l_ordre_cible(self):
        noms, deplacements = onboarding.plan_regroupement(ONGLET, "Lea")
        self.assertEqual(noms, [])
        self.assertEqual(appliquer(ONGLET, deplacements), onboarding.ordre_cible(ONGLET, "Lea"))

    def test_deja_trie_ne_bouge_plus(self):
        noms, deplacements = onboarding.plan_regroupement(ONGLET, "Lea")
        ordre = appliquer(ONGLET, deplacements)
        relu = [dict(next(c for c in ONGLET if c["ligne"] == r), ligne=i + 2) for i, r in enumerate(ordre)]
        self.assertEqual(onboarding.plan_regroupement(relu, "Lea"), ([], []))

    def test_un_ban_ne_recoit_jamais_de_gerant_par_son_lien(self):
        lignes = [ligne(2, "GOOD", "a1", "Alice", "https://x.fr/5"), ligne(3, "BAN", "a2", "", "https://x.fr/5"),
                  ligne(4, "GOOD", "a3", "", "https://x.fr/5")]
        noms, _ = onboarding.plan_regroupement(lignes, "Lea")
        self.assertEqual(noms, [(4, "Alice")])

    def test_ancien_regroupement_si_tri_coupe(self):
        ancien = onboarding.TRI_COMPTES
        onboarding.TRI_COMPTES = False
        try:
            _, deplacements = onboarding.plan_regroupement(ONGLET, "Lea")
            ordre = appliquer(ONGLET, deplacements)
        finally:
            onboarding.TRI_COMPTES = ancien
        self.assertEqual(ordre[-2:], [3, 15])                           # 30/09 : seul le stock descend
        self.assertEqual(ordre.index(5), ordre.index(4) + 1)            # le BAN d'Alice reste dans son pod


class BlocsTests(unittest.TestCase):
    def test_un_ban_sort_du_bloc_de_son_ancien_gerant(self):
        lignes = [ligne(2, "GOOD", "a1", "Alice"), ligne(3, "à créer", "a3", "Alice"), ligne(4, "BAN", "a2", "Alice")]
        self.assertEqual([(g, [c["ligne"] for c in ls]) for g, ls in classeur_forme.blocs(lignes)], [("alice", [2, 3])])

    def test_cle_bloc(self):
        self.assertEqual(onboarding.cle_bloc({"gerant": "Alice", "etat": "BAN"}), "")
        self.assertEqual(onboarding.cle_bloc({"gerant": "Alice", "etat": "GOOD"}), "alice")
        self.assertEqual(onboarding.cle_bloc({"gerant": "x", "etat": "GOOD"}), "")


if __name__ == "__main__":
    unittest.main()
