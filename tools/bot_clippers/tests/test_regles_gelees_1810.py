"""Règles gelées du 18/10 : paiement avant le compte privé (P4), grille manager (P6), 10 jours sans visite (L7), groupe TL (E8).
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


class PaiementAvantPriveTests(unittest.TestCase):
    def _paie(self, regime="clic", wallets=None, actif=True):
        return N(actif=lambda: actif, regime=lambda uid: regime, _lire=lambda: {"wallets": wallets or {}})

    def test_clic_sans_adresse_bloque(self):
        with patch.object(parcours, "paie_clics", self._paie()):
            self.assertFalse(parcours.moyen_paiement_ok("1"))

    def test_usdc_ou_iban_debloque(self):
        for adresse in ("0x" + "a" * 40, "FR7630006000011234567890189"):
            with patch.object(parcours, "paie_clics", self._paie(wallets={"1": {"adresse": adresse}})):
                self.assertTrue(parcours.moyen_paiement_ok("1"))

    def test_fixe_jamais_bloque(self):
        with patch.object(parcours, "paie_clics", self._paie(regime="fixe")):
            self.assertTrue(parcours.moyen_paiement_ok("1"))

    def test_panne_ne_bloque_pas(self):
        def casse():
            raise OSError("disque")
        with patch.object(parcours, "paie_clics", N(actif=lambda: True, regime=lambda uid: "clic", _lire=casse)):
            self.assertTrue(parcours.moyen_paiement_ok("1"))

    def test_regle_coupable(self):
        with patch.object(parcours, "paie_clics", self._paie()), patch.object(parcours, "PAIEMENT_AVANT_PRIVE", False):
            self.assertTrue(parcours.moyen_paiement_ok("1"))

    def test_texte_donne_les_deux_commandes(self):
        texte = parcours.TEXTE_PAIEMENT_AVANT_PRIVE.format(n=3)
        self.assertIn("`!wallet 0x…`", texte)
        self.assertIn("`!wallet FR76…`", texte)
        self.assertIn("compte 3", texte)


class GrilleManagerTests(unittest.TestCase):
    def test_defauts_du_18_10(self):
        self.assertEqual(equipes_tl.MANAGER_PRIME_USD, 50.0)
        self.assertEqual(equipes_tl.MANAGER_SEUIL_EQUIPE, 2500)
        self.assertEqual(equipes_tl.TL_PRIME_VA_USD, 10.0)
        self.assertEqual(equipes_tl.TL_SEUIL_VA, 500)


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


if __name__ == "__main__":
    unittest.main()
