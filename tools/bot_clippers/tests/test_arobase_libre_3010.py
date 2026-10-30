"""30/10 (Gaëtan : « Il ne faut jamais donner un arobas qui n'est pas disponible. Je compte sur toi par rapport à ça. Comme ça, on
est sûr d'avoir la bonne attribution des clippers »).

Un @ est vérifié sur Instagram (RapidAPI, route « id ») avant le message de son compte : pris = jamais donné, la ligne sort du stock
et une autre est réservée ; doute = rien n'est donné, nouvel essai plus tard. Sans réseau ni Discord ni classeur."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arobase_libre as a
import instagram_rapidapi as ig
import onboarding
import parcours as p
import process_adapters


class LectureTests(unittest.TestCase):
    def test_un_id_veut_dire_pris_introuvable_veut_dire_libre_le_reste_un_doute(self):
        self.assertEqual((a.PRIS, "123"), a.lire_reponse(200, {"user_id": "123"}))
        self.assertEqual(a.LIBRE, a.lire_reponse(404, {"message": "User not found"})[0])
        self.assertEqual(a.LIBRE, a.lire_reponse(200, {"status": False})[0])
        for code, corps in ((500, "erreur"), (0, "TimeoutError"), (429, {"message": "Too many requests"}), (200, {})):
            self.assertEqual(a.INCONNU, a.lire_reponse(code, corps)[0], (code, corps))


class VerdictTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patcher in (patch.object(a, "FICHIER", Path(self.tmp.name) / "arobases.json"),
                        patch.object(a, "actif", return_value=True),
                        patch.object(ig, "_quota_ok", return_value=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_pris_garde_pour_toujours_sans_nouvel_appel(self):
        appel = AsyncMock(return_value=(200, {"user_id": "555"}))
        with patch.object(ig, "appeler", appel):
            self.assertEqual(a.PRIS, await a.verdict("@Journal.Fictif"))
            self.assertEqual(a.PRIS, await a.verdict("journal.fictif"))
        self.assertEqual(1, appel.await_count)
        self.assertTrue(a.connu_pris("JOURNAL.fictif"))
        self.assertEqual(["journal.fictif"], a.pris_connus())

    async def test_libre_reutilise_puis_revu(self):
        appel = AsyncMock(return_value=(404, "not found"))
        with patch.object(ig, "appeler", appel):
            self.assertEqual(a.LIBRE, await a.verdict("neuf.fictif"))
            self.assertEqual(a.LIBRE, await a.verdict("neuf.fictif"))
            self.assertEqual(1, appel.await_count)
            with patch.object(a, "LIBRE_VALIDE_H", 0):
                self.assertEqual(a.LIBRE, await a.verdict("neuf.fictif"))
        self.assertEqual(2, appel.await_count)

    async def test_un_doute_n_est_jamais_note_ni_donne(self):
        with patch.object(ig, "appeler", AsyncMock(return_value=(503, "indisponible"))):
            self.assertEqual(a.INCONNU, await a.verdict("doute.fictif"))
        self.assertEqual({}, a._lire())
        with patch.object(ig, "_quota_ok", return_value=False), patch.object(ig, "appeler", AsyncMock()) as appel:
            self.assertEqual(a.INCONNU, await a.verdict("quota.fictif"))
            appel.assert_not_awaited()

    async def test_declare_libre_par_un_humain(self):
        a.forcer_libre("@verifie.fictif", par="Staff")
        with patch.object(ig, "appeler", AsyncMock()) as appel:
            self.assertEqual(a.LIBRE, await a.verdict("verifie.fictif"))
            appel.assert_not_awaited()

    async def test_sans_verification_possible_l_ancien_comportement(self):
        with patch.object(a, "actif", return_value=False):
            self.assertEqual(a.LIBRE, await a.verdict("x.fictif"))


class RemiseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.etat = {"42": {"prenom": "Fictif", "creatrice": "Fictive", "ordre": "prive3", "messages": {}}}
        self.membre = N(id=42, mention="<@42>")

        def ecrire(d):
            self.etat = deepcopy(d)
        for patcher in (patch.object(p, "_lire", side_effect=lambda: deepcopy(self.etat)),
                        patch.object(p, "_ecrire", side_effect=ecrire),
                        patch.object(p, "_onb", return_value={"acces": []}),
                        patch.object(p, "_garder_au_programme", return_value=False),
                        patch.dict(p._deps, {"canal_admin": AsyncMock(return_value=N(send=AsyncMock()))}),
                        patch.object(a, "actif", return_value=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_un_arobase_pris_est_remplace_puis_le_nouveau_verifie(self):
        ordres = iter([["pris.fictif", "deux", "prive"], ["neuf.fictif", "deux", "prive"]])
        remplacer = AsyncMock(return_value={"handle": "neuf.fictif"})
        with patch.object(p, "_comptes_ordonnes", side_effect=lambda *x, **k: next(ordres)), \
                patch.object(a, "verdict", AsyncMock(side_effect=[a.PRIS, a.LIBRE])), \
                patch.object(onboarding, "remplacer_arobase_pris", remplacer):
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        remplacer.assert_awaited_once()
        self.assertEqual("pris.fictif", remplacer.await_args.args[2])
        self.assertFalse(remplacer.await_args.kwargs["prive"])

    async def test_un_doute_retient_le_compte(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["doute.fictif"]), \
                patch.object(a, "verdict", AsyncMock(return_value=a.INCONNU)), \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock()) as remplacer:
            self.assertFalse(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        remplacer.assert_not_awaited()
        self.assertEqual(1, self.etat["42"]["retenue"]["n"])

    async def test_plus_de_ligne_libre_retient_le_compte(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["pris.fictif", "deux", "prive"]), \
                patch.object(a, "verdict", AsyncMock(return_value=a.PRIS)), \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock(return_value=None)):
            self.assertFalse(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 2))
        self.assertIn("plus de ligne libre", self.etat["42"]["retenue"]["raison"])

    async def test_un_compte_qui_existe_deja_n_est_pas_verifie(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["sien.fictif"]), \
                patch.object(p, "_onb", return_value={"acces": [{"handle": "sien.fictif", "cree": True}]}), \
                patch.object(a, "verdict", AsyncMock()) as verdict:
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        verdict.assert_not_awaited()


class StockTests(unittest.IsolatedAsyncioTestCase):
    LIGNES = [{"utilisation": "Clipper", "gerant": "", "etat": "à créer", "handle": "pris.fictif", "mail": "", "mdp": "",
               "creatrice": "Fictive", "ligne": 2, "pod": "", "onglet": "Fictive"},
              {"utilisation": "Clipper", "gerant": "", "etat": "à créer", "handle": "libre.fictif", "mail": "", "mdp": "",
               "creatrice": "Fictive", "ligne": 3, "pod": "", "onglet": "Fictive"}]

    def setUp(self):
        for patcher in (patch.object(onboarding, "_proprietaires", return_value={}),
                        patch.object(process_adapters, "store", return_value=N(owner_for_handle=lambda h: None,
                                                                               cancel=lambda *x: None)),
                        patch.object(p, "pseudo_seul_uid", return_value=True),
                        patch.object(a, "connu_pris", side_effect=lambda h: a.norm(h) == "pris.fictif")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_un_arobase_deja_vu_pris_ne_se_reserve_plus(self):
        self.assertEqual(["libre.fictif"], [c["handle"] for c in onboarding.disponibles(deepcopy(self.LIGNES), "Fictive", 999, "42")])

    async def test_la_ligne_prise_sort_du_stock_et_une_autre_est_reservee(self):
        etat = {"clippers": {"42": {"comptes": ["pris.fictif", "deux.fictif"], "acces": [{"handle": "pris.fictif"}]}},
                "livres": {"pris.fictif": {"uid": "42"}}}
        ecrits = []

        async def ecrire_cellule(classeur, plage, valeurs):
            ecrits.append((plage, valeurs[0][0]))

        def ecrire_etat(d):
            etat.clear()
            etat.update(deepcopy(d))
        reserver = AsyncMock(return_value={"handle": "libre.fictif"})
        with patch.object(onboarding, "actif", return_value=True), \
                patch.object(onboarding, "lire_comptes", AsyncMock(return_value=deepcopy(self.LIGNES))), \
                patch.object(onboarding.google_api, "sheets_ecrire", side_effect=ecrire_cellule), \
                patch.object(onboarding, "cellule", side_effect=lambda c, champ: f"{champ}{c['ligne']}"), \
                patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(etat)), \
                patch.object(onboarding, "_ecrire_etat", side_effect=ecrire_etat), \
                patch.object(onboarding, "reserver_compte", reserver):
            nouvelle = await onboarding.remplacer_arobase_pris(N(id=42), "Fictive", "@Pris.Fictif", prive=False)
        self.assertEqual({"handle": "libre.fictif"}, nouvelle)
        self.assertIn(("utilisation2", onboarding.MENTION_AROBASE_PRIS), ecrits)
        self.assertIn(("gerant2", ""), ecrits)
        self.assertEqual(["deux.fictif"], etat["clippers"]["42"]["comptes"])
        self.assertEqual([], etat["clippers"]["42"]["acces"])
        self.assertNotIn("pris.fictif", etat["livres"])
        self.assertEqual(2, reserver.await_args.args[2])                # le compte suivant de sa fiche, du même type
        self.assertFalse(reserver.await_args.kwargs["prive"])


if __name__ == "__main__":
    unittest.main()
