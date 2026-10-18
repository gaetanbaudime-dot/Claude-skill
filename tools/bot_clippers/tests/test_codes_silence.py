"""18/10 (action 26) : aucun code Instagram reçu depuis 3 h, de jour à Paris → une ligne au salon admin. Cas fictifs."""
import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import codes_2fa as c  # noqa: E402

MAINTENANT = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


class SilenceTests(unittest.TestCase):
    def test_seuil_et_plage_de_jour(self):
        iso = (MAINTENANT - timedelta(minutes=200)).isoformat()
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 14, 180, (9, 23)), 200)
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 3, 180, (9, 23)), 0)       # la nuit : normal
        recent = (MAINTENANT - timedelta(minutes=30)).isoformat()
        self.assertEqual(c.silence_a_signaler(recent, MAINTENANT, 14, 180, (9, 23)), 0)
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 14, 0, (9, 23)), 0)        # coupée

    def test_une_fois_puis_retour(self):
        etat = {"dernier_code": (MAINTENANT - timedelta(hours=4)).isoformat()}
        dits = []

        async def admin(t):
            dits.append(t)
            return True
        with patch.object(c, "_etat", lambda: etat), patch.object(c, "_sauver", lambda: None), \
                patch.object(c, "_admin", admin), patch.object(c, "_maintenant", lambda: MAINTENANT), \
                patch.object(c, "SILENCE_MIN", 180), patch.object(c, "SILENCE_HEURES", (0, 24)):
            asyncio.run(c.surveiller_silence())
            asyncio.run(c.surveiller_silence())                         # pas deux fois
            etat["dernier_code"] = MAINTENANT.isoformat()                # un code arrive
            asyncio.run(c.surveiller_silence())
        self.assertEqual(len(dits), 2)
        self.assertIn("Aucun code Instagram reçu depuis 4 h 00", dits[0])
        self.assertIn("arrivent de nouveau", dits[1])


if __name__ == "__main__":
    unittest.main()


class CodeAbsentEtGardienTests(unittest.IsolatedAsyncioTestCase):
    def test_seuil_une_heure_par_defaut(self):
        import importlib, os
        import codes_2fa
        if "CODES_SILENCE_MIN" not in os.environ:
            self.assertEqual(codes_2fa.SILENCE_MIN, 60)

    def test_texte_sans_adresse_en_clair(self):
        import codes_2fa
        t = codes_2fa.texte_code_absent("123", {"jean.dupont42@icloud.com"}, "creation", False)
        self.assertIn("<@123>", t)
        self.assertIn("Code Instagram pas reçu", t)
        self.assertNotIn("jean.dupont42", t)

    async def test_alerte_une_fois_par_clipper(self):
        import codes_2fa
        envoyes = []

        async def faux_admin(texte):
            envoyes.append(texte)
            return True
        ancien_admin, ancien_etat = codes_2fa._admin, codes_2fa._etat
        etat = {"faits": {}, "sante": {}, "codes": []}
        codes_2fa._admin, codes_2fa._etat = faux_admin, lambda: etat
        try:
            codes_2fa._signaler_code_absent("u|123", {"a@icloud.com"}, "creation")
            codes_2fa._signaler_code_absent("u|123", {"a@icloud.com"}, "creation")
            import asyncio
            await asyncio.sleep(0)
        finally:
            codes_2fa._admin, codes_2fa._etat = ancien_admin, ancien_etat
        self.assertEqual(len(envoyes), 1)

    def test_lecteur_bloque(self):
        import codes_2fa
        ancien = dict(codes_2fa._SANTE)
        try:
            codes_2fa._SANTE["ok_t"] = 1000.0
            self.assertEqual(codes_2fa.lecteur_bloque(1000.0 + 5 * 60), 0)
            self.assertEqual(codes_2fa.lecteur_bloque(1000.0 + 12 * 60), 12)
        finally:
            codes_2fa._SANTE.clear()
            codes_2fa._SANTE.update(ancien)


class FausseAlerteTests(unittest.TestCase):
    def test_pas_d_alerte_si_un_code_a_ete_montre(self):
        import codes_2fa
        maintenant = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)
        ancien_m, ancien_t = dict(codes_2fa._MONTRES), codes_2fa._maintenant
        codes_2fa._maintenant = lambda: maintenant
        try:
            codes_2fa._MONTRES["u|7"] = {"mid1": codes_2fa._iso(maintenant - timedelta(minutes=5))}
            self.assertTrue(codes_2fa.code_montre_recemment("u|7"))
            self.assertFalse(codes_2fa.code_montre_recemment("u|8"))
            codes_2fa._MONTRES["u|9"] = {"mid2": codes_2fa._iso(maintenant - timedelta(minutes=40))}
            self.assertFalse(codes_2fa.code_montre_recemment("u|9"))
        finally:
            codes_2fa._MONTRES.clear()
            codes_2fa._MONTRES.update(ancien_m)
            codes_2fa._maintenant = ancien_t
