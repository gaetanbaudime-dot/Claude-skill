"""Règles gelées du 18/10 : rien ne bloque le compte privé (P4), grille manager (P6), 10 jours sans visite (L7), groupe TL (E8).
Cas fictifs, sans réseau ni Discord."""
import asyncio
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import equipes_tl  # noqa: E402
import parcours  # noqa: E402
import sortie_auto  # noqa: E402


class GrilleManagerTests(unittest.TestCase):
    def test_defauts_du_18_10(self):
        self.assertEqual(equipes_tl.MANAGER_PRIME_USD, 50.0)
        self.assertEqual(equipes_tl.MANAGER_SEUIL_EQUIPE, 2500)
        self.assertEqual(equipes_tl.TL_PRIME_VA_USD, 10.0)
        self.assertEqual(equipes_tl.TL_SEUIL_VA, 500)

    def test_ancienne_grille_railway_ignoree(self):
        import importlib
        with patch.dict("os.environ", {"MANAGER_PRIME_USD": "75", "MANAGER_SEUIL_EQUIPE": "3 000"}):
            module = importlib.reload(equipes_tl)
            grille = (module.MANAGER_PRIME_USD, module.MANAGER_SEUIL_EQUIPE)
            averti = any("ancienne grille" in a for a in module.AVERTISSEMENTS)
        importlib.reload(equipes_tl)
        self.assertEqual(grille, (50.0, 2500))
        self.assertTrue(averti)

    def test_paiement_ne_bloque_plus_le_prive(self):
        self.assertFalse(hasattr(parcours, "moyen_paiement_ok"))
        self.assertFalse(hasattr(parcours, "TEXTE_PAIEMENT_AVANT_PRIVE"))


class InactifsTests(unittest.TestCase):
    def _paie(self, liens, payees):
        return N(actif=lambda: True, _lire=lambda: {"liens": liens}, CLICS_EXCLURE={"gaetan"},
                 liens_de=lambda d, uid: [l for l, i in d["liens"].items() if str(i.get("uid")) == str(uid)],
                 payees=lambda d, uid, a, b: payees.get(uid, 0))

    def test_liste_seulement_les_liens_anciens_a_zero(self):
        liens = {"a": {"uid": "1", "depuis": "2026-09-20", "note": "Clipping Thia"},
                 "b": {"uid": "2", "depuis": "2026-09-20", "note": "Clipping Caroline"},
                 "c": {"uid": "3", "depuis": "2026-10-15", "note": "Clipping Mavie"}}
        maintenant = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
        with patch.dict(sys.modules, {"paie_clics": self._paie(liens, {"2": 1352})}):
            self.assertEqual(sortie_auto.inactifs(maintenant), [("1", "Thia")])

    def test_coupure(self):
        with patch.object(sortie_auto, "INACTIF_JOURS", 0):
            self.assertEqual(sortie_auto.inactifs(), [])


class GroupeTLTests(unittest.TestCase):
    def test_bouton_persistant(self):
        self.assertIn(parcours.BoutonGroupeTL, parcours.vues_persistantes(None))

    def test_demande_une_seule_fois(self):
        fiches = {"7": {"prenom": "Mavie"}}
        salon = N(send=AsyncMock())
        tl = N(mention="<@9>")
        with patch.object(parcours, "_lire", lambda: fiches), patch.object(parcours, "_ecrire", lambda d: None):
            premier = asyncio.run(parcours.demander_groupe_tl(salon, "7", tl, "Mavie", "Sophie"))
            second = asyncio.run(parcours.demander_groupe_tl(salon, "7", tl, "Mavie", "Sophie"))
        self.assertTrue(premier)
        self.assertFalse(second)
        self.assertEqual(salon.send.await_count, 1)
        self.assertIn("Gaëtan", salon.send.await_args.args[0])


class TLParPrenomTests(unittest.TestCase):
    """18/10 : `!tl Sophie Mathieu` sans mention (un @ recopié n'est pas une mention)."""
    def _guild(self, *noms):
        return N(members=[N(id=i + 1, display_name=n, bot=False) for i, n in enumerate(noms)])

    def test_prenom_seul(self):
        g = self._guild("Mathieu - Sophie - LT Sophie", "Thia")
        m, c, refus = equipes_tl._par_prenom(g, ["Sophie", "Mathieu"])
        self.assertEqual((m.display_name, c, refus), ("Mathieu - Sophie - LT Sophie", "Sophie", ""))

    def test_pseudo_entier_recopie(self):
        g = self._guild("Mathieu - Sophie - LT Sophie")
        m, c, _ = equipes_tl._par_prenom(g, ["Sophie", "@Mathieu", "-", "Sophie", "-", "LT", "Sophie"])
        self.assertEqual((m.display_name, c), ("Mathieu - Sophie - LT Sophie", "Sophie"))

    def test_homonymes_refuses(self):
        g = self._guild("Mathieu - Sophie", "Mathieu - Chloé")
        m, _, refus = equipes_tl._par_prenom(g, ["Sophie", "Mathieu"])
        self.assertIsNone(m)
        self.assertIn("2 membres", refus)

    def test_inconnu(self):
        m, c, refus = equipes_tl._par_prenom(self._guild("Thia"), ["Sophie", "Mathieu"])
        self.assertEqual((m, refus), (None, ""))


if __name__ == "__main__":
    unittest.main()
