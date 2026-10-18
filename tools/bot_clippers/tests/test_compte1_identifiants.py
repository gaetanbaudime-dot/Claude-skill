"""18/10 : identifiants du compte 1 dans le salon perso dès l'envoi (règles gelées E7, C10), contrôles de !remettre-compte1."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onboarding  # noqa: E402
import remise_compte1  # noqa: E402

LIGNE = {"handle": "neuf_un", "gerant": "Mavie", "creatrice": "Sarah", "etat": next(iter(onboarding.A_CREER)),
         "mail": "x@exemple.test", "mdp": "Secret123"}


class IdentifiantsTests(unittest.TestCase):
    def _lancer(self, lignes, lecteurs_ok=True, gerant="Mavie"):
        async def lire():
            return lignes

        def lecteurs(*a, **k):
            if not lecteurs_ok:
                raise remise_compte1.Retenue("Un lecteur non autorisé")
        with patch.object(onboarding, "lire_comptes", lire), patch.object(remise_compte1, "verifier_lecteurs", lecteurs), \
                patch.object(remise_compte1.parcours, "_onb", lambda uid: {"gerant": gerant}):
            return asyncio.run(remise_compte1.identifiants_surs(N(), N(), "7", "neuf_un", {"creatrice": "Sarah"}, set(),
                                                                lambda m: False))

    def test_salon_sur_et_ligne_a_lui(self):
        self.assertEqual(self._lancer([LIGNE]), ("x@exemple.test", "Secret123"))

    def test_lecteur_non_autorise_pas_de_secret(self):
        self.assertIsNone(self._lancer([LIGNE], lecteurs_ok=False))

    def test_ligne_d_un_autre_pas_de_secret(self):
        self.assertIsNone(self._lancer([LIGNE], gerant="Thia"))
        self.assertIsNone(self._lancer([LIGNE, dict(LIGNE)]))

    def test_modele_complet(self):
        texte = remise_compte1.modele("<@7>", "neuf_un", "x@exemple.test", "Secret123")
        for morceau in ("`neuf_un`", "`x@exemple.test`", "`Secret123`", "!code"):
            self.assertIn(morceau, texte)


if __name__ == "__main__":
    unittest.main()


class LecteursTests(unittest.TestCase):
    """18/10 : un administrateur du serveur voit tous les salons ; il ne bloque plus la remise. Un autre clipper, si."""
    def _guild(self, lecteurs):
        moi = N(id=1, display_name="bot", bot=True, roles=[], guild_permissions=N(administrator=True))
        membres = [moi] + lecteurs
        salon = N(permissions_for=lambda m: N(view_channel=True), overwrites_for=lambda x: N(view_channel=None))
        guild = N(members=membres, owner_id=2, me=moi, chunked=True, default_role=N(id=0))
        salon.permissions_for = lambda m: N(view_channel=m is not guild.default_role)
        return guild, salon

    def _diag(self, lecteurs):
        guild, salon = self._guild(lecteurs)
        with patch.object(remise_compte1.equipes_tl, "tl_par_va", lambda: {}), \
                patch.object(remise_compte1.equipes_tl, "_fiches", lambda: {}), \
                patch.object(remise_compte1.onboarding_preuves, "tl_pour", lambda *a: None):
            return remise_compte1.diagnostic_lecteurs(guild, salon, "7", "Chloé", {"2"}, lambda m: False)

    def test_admin_du_serveur_autorise(self):
        d = self._diag([N(id=7, display_name="Titulaire", bot=False, roles=[], guild_permissions=N(administrator=False)),
                        N(id=8, display_name="Associé", bot=False, roles=[], guild_permissions=N(administrator=True))])
        self.assertTrue(d["remise_autorisee"])

    def test_autre_clipper_bloque_et_nomme(self):
        d = self._diag([N(id=7, display_name="Titulaire", bot=False, roles=[], guild_permissions=N(administrator=False)),
                        N(id=9, display_name="Autre clipper", bot=False, roles=[], guild_permissions=N(administrator=False))])
        self.assertFalse(d["remise_autorisee"])
        with patch.object(remise_compte1, "diagnostic_lecteurs", lambda *a: d):
            with self.assertRaises(remise_compte1.Retenue) as ctx:
                remise_compte1.verifier_lecteurs(None, None, "7", "Chloé", set(), lambda m: False)
        self.assertIn("Autre clipper", str(ctx.exception))
