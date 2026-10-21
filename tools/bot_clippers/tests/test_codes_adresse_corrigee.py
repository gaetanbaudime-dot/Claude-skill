"""19/10 (Esperance) : l'e-mail du compte 1 corrigé dans le classeur doit servir même si la fiche garde d'anciennes adresses."""
import types
import unittest
from unittest.mock import AsyncMock

from test_codes_reliable import load_codes


class AdresseCorrigeeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.c = load_codes()
        self.membre = types.SimpleNamespace(id=42, display_name="Esperance - Chloé", roles=[])

    async def test_classeur_ajoute_a_la_fiche_non_vide(self):
        rafraichir = AsyncMock(return_value={"ancienne@icloud.com", "corrigee@icloud.com"})
        self.c._deps["rafraichir_adresses_membre"] = rafraichir
        adresses = await self.c._adresses_a_jour(self.membre, {"ancienne@icloud.com", "autre@icloud.com"})
        self.assertEqual(adresses, {"ancienne@icloud.com", "autre@icloud.com", "corrigee@icloud.com"})
        rafraichir.assert_awaited_once()

    async def test_classeur_indisponible_garde_la_fiche(self):
        self.c._deps["rafraichir_adresses_membre"] = AsyncMock(side_effect=RuntimeError("Sheets"))
        adresses = await self.c._adresses_a_jour(self.membre, {"ancienne@icloud.com"})
        self.assertEqual(adresses, {"ancienne@icloud.com"})

    async def test_rien_nulle_part(self):
        self.c._deps["rafraichir_adresses_membre"] = AsyncMock(return_value=set())
        self.assertEqual(await self.c._adresses_a_jour(self.membre, set()), set())


class CacheClasseurTests(unittest.TestCase):
    """L'adresse vérifiée dans le classeur survit à une réécriture de la fiche pendant l'attente du code."""

    def ns(self, data):
        from test_codes_demande_privee import ProprieteTests
        return ProprieteTests().namespace(data)

    def test_fiche_active_garde_l_adresse_du_classeur(self):
        data = {"clippers": {"100": {"comptes": ["vieux"], "acces": [{"handle": "vieux", "mail": "vieux@example.invalid"}]}},
                "livres": {}}
        ns = self.ns(data)
        ns["_OTP_UID_CACHE"]["100"] = {"mails": {"corrigee@example.invalid"}, "jusque": 1e12, "revision": "ancienne"}
        self.assertEqual(ns["adresses_codes_de"]("100"), {"vieux@example.invalid", "corrigee@example.invalid"})

    def test_adresse_passee_a_un_autre_clipper_est_retiree(self):
        data = {"clippers": {
            "100": {"comptes": ["vieux"], "acces": [{"handle": "vieux", "mail": "vieux@example.invalid"}]},
            "200": {"comptes": ["neuf"], "acces": [{"handle": "neuf", "mail": "corrigee@example.invalid"}]}}, "livres": {}}
        ns = self.ns(data)
        ns["_OTP_UID_CACHE"]["100"] = {"mails": {"corrigee@example.invalid"}, "jusque": 1e12, "revision": "ancienne"}
        self.assertEqual(ns["adresses_codes_de"]("100"), {"vieux@example.invalid"})


if __name__ == "__main__":
    unittest.main()
