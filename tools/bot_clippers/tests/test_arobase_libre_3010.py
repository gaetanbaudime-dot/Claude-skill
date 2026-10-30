"""30/10 (Gaëtan : « Il ne faut jamais donner un arobas qui n'est pas disponible. Je compte sur toi par rapport à ça. Comme ça, on
est sûr d'avoir la bonne attribution des clippers »).

Un @ est vérifié sur Instagram (RapidAPI, route « id ») avant le message de son compte : pris = jamais donné, la ligne sort du stock
et une autre est réservée ; doute = rien n'est donné, nouvel essai plus tard. Sans réseau ni Discord ni classeur."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
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

    async def test_sans_verification_possible(self):
        with patch.object(a, "ACTIVE", False):                          # AROBASE_VERIF=0 : l'ancien comportement
            self.assertEqual(a.LIBRE, await a.verdict("x.fictif"))
        with patch.object(a, "actif", return_value=False), patch.object(a, "depuis_ci", AsyncMock(return_value=None)):
            self.assertEqual(a.INCONNU, await a.verdict("x.fictif"))   # 30/10 : sans clé ni contrôle GitHub, jamais « libre »
        with patch.object(a, "actif", return_value=False), \
                patch.object(a, "depuis_ci", AsyncMock(return_value={"verdict": a.LIBRE})):
            self.assertEqual(a.LIBRE, await a.verdict("x.fictif"))

    async def test_cle_refusee_le_controle_github_prend_le_relais(self):
        a._refus["jusqua"] = 0
        self.addCleanup(a._refus.update, {"jusqua": 0})
        appel = AsyncMock(return_value=(403, {"message": "You are not subscribed to this API."}))
        with patch.object(ig, "appeler", appel), \
                patch.object(a, "depuis_ci", AsyncMock(side_effect=lambda h: {"verdict": a.LIBRE} if h == "vu.fictif" else None)):
            self.assertEqual(a.LIBRE, await a.verdict("vu.fictif"))
            self.assertTrue(a.cle_refusee())
            self.assertEqual(a.INCONNU, await a.verdict("jamais.fictif"))   # pas dans le contrôle : doute
            self.assertEqual(a.LIBRE, (await a.examen("vu.fictif"))["verdict"])
        self.assertEqual(1, appel.await_count)                          # une seule tentative : la clé est en pause


class RemiseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.etat = {"42": {"prenom": "Fictif", "creatrice": "Fictive", "ordre": "prive3", "messages": {}}}
        self.membre = N(id=42, mention="<@42>")
        patcher = patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[]))
        patcher.start()
        self.addCleanup(patcher.stop)

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

    INCONNU_INSTALLE = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": False, "abonnes": 141, "publications": 1}

    def _sans_variante(self):
        return (patch.object(a, "examen", AsyncMock(return_value=dict(self.INCONNU_INSTALLE))),
                patch.object(a, "variante_libre", AsyncMock(return_value="")),
                patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[])))

    async def test_un_arobase_pris_sans_variante_libre_prend_une_autre_ligne(self):
        ordres = iter([["pris.fictif", "deux", "prive"], ["neuf.fictif", "deux", "prive"]])
        remplacer = AsyncMock(return_value={"handle": "neuf.fictif"})
        e, v, l = self._sans_variante()
        with patch.object(p, "_comptes_ordonnes", side_effect=lambda *x, **k: next(ordres)), \
                patch.object(a, "verdict", AsyncMock(side_effect=[a.PRIS, a.LIBRE])), e, v, l, \
                patch.object(onboarding, "remplacer_arobase_pris", remplacer):
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        remplacer.assert_awaited_once()
        self.assertEqual("pris.fictif", remplacer.await_args.args[2])
        self.assertFalse(remplacer.await_args.kwargs["prive"])

    async def test_un_arobase_pris_devient_une_variante_dans_la_meme_ligne(self):
        """30/10, 9 h 36 (Gaëtan : « tu remplaces les points par des tirets du bas… ou tu rajoutes XO à la fin »)."""
        ordres = iter([["pris.fictif", "deux", "prive"], ["pris_fictif", "deux", "prive"]])
        renommer = AsyncMock(return_value=("pris.fictif", ""))
        with patch.object(p, "_comptes_ordonnes", side_effect=lambda *x, **k: next(ordres)), \
                patch.object(a, "verdict", AsyncMock(side_effect=[a.PRIS, a.LIBRE])), \
                patch.object(a, "examen", AsyncMock(return_value=dict(self.INCONNU_INSTALLE))), \
                patch.object(a, "variante_libre", AsyncMock(return_value="pris_fictif")) as variante, \
                patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[{"handle": "deux"}])), \
                patch.object(p, "renommer", renommer), \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock()) as remplacer:
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        renommer.assert_awaited_once_with("42", 1, "pris_fictif")
        self.assertIn("deux", variante.await_args.kwargs["exclus"])     # jamais une variante déjà dans le LOG
        remplacer.assert_not_awaited()

    async def test_un_compte_neuf_ou_a_nous_n_est_jamais_remplace(self):
        for examen in ({"verdict": "pris", "profil_lu": True, "neuf": True, "a_nous": False},
                       {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": True}):
            with patch.object(p, "_comptes_ordonnes", return_value=["sien.fictif", "deux", "prive"]), \
                    patch.object(a, "verdict", AsyncMock(return_value=a.PRIS)), \
                    patch.object(a, "examen", AsyncMock(return_value=examen)), \
                    patch.object(p, "renommer", AsyncMock()) as renommer, \
                    patch.object(onboarding, "remplacer_arobase_pris", AsyncMock()) as remplacer:
                self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
            renommer.assert_not_awaited()
            remplacer.assert_not_awaited()

    async def test_un_profil_illisible_retient_sans_rien_remplacer(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["pris.fictif"]), \
                patch.object(a, "verdict", AsyncMock(return_value=a.PRIS)), \
                patch.object(a, "examen", AsyncMock(return_value={"verdict": "pris", "profil_lu": False})), \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock()) as remplacer:
            self.assertFalse(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        remplacer.assert_not_awaited()
        self.assertIn("profil à relire", self.etat["42"]["retenue"]["raison"])

    async def test_un_arobase_deja_donne_n_est_plus_verifie(self):
        self.etat["42"]["donnes"] = {"2": {"handle": "Deux.Fictif"}}
        with patch.object(p, "_comptes_ordonnes", return_value=["un", "deux.fictif", "prive"]), \
                patch.object(a, "verdict", AsyncMock()) as verdict:
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 2))
        verdict.assert_not_awaited()

    async def test_un_compte_que_le_log_dit_cree_n_est_jamais_verifie(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["vivant.fictif"]), \
                patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[{"handle": "Vivant.Fictif", "etat": "GOOD"}])), \
                patch.object(a, "verdict", AsyncMock()) as verdict:
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        verdict.assert_not_awaited()

    async def test_un_doute_retient_le_compte(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["doute.fictif"]), \
                patch.object(a, "verdict", AsyncMock(return_value=a.INCONNU)), \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock()) as remplacer:
            self.assertFalse(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        remplacer.assert_not_awaited()
        self.assertEqual(1, self.etat["42"]["retenue"]["n"])

    async def test_plus_de_ligne_libre_retient_le_compte(self):
        e, v, l = self._sans_variante()
        with patch.object(p, "_comptes_ordonnes", return_value=["pris.fictif", "deux", "prive"]), \
                patch.object(a, "verdict", AsyncMock(return_value=a.PRIS)), e, v, l, \
                patch.object(onboarding, "remplacer_arobase_pris", AsyncMock(return_value=None)):
            self.assertFalse(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 2))
        self.assertIn("plus de ligne libre", self.etat["42"]["retenue"]["raison"])

    async def test_un_compte_qui_existe_deja_n_est_pas_verifie(self):
        with patch.object(p, "_comptes_ordonnes", return_value=["sien.fictif"]), \
                patch.object(p, "_onb", return_value={"acces": [{"handle": "sien.fictif", "cree": True}]}), \
                patch.object(a, "verdict", AsyncMock()) as verdict:
            self.assertTrue(await p._arobase_libre_ou_remplace(N(), self.membre, "42", 1))
        verdict.assert_not_awaited()


class VariantesTests(unittest.TestCase):
    def test_les_variantes_de_gaetan_d_abord(self):
        v = a.variantes("@Sarah.Secret")
        self.assertEqual(["sarah_secret", "sarah.secretxo", "sarah.secret_xo", "sarah.secret.xo"], v[:4])
        self.assertEqual(["jade_prv_x", "jade.prv.x"], a.variantes("jade.prv_x")[:2])
        self.assertIn("journaldesarahxo", a.variantes("journaldesarah"))

    def test_jamais_un_at_refuse_par_instagram(self):
        for h in ("sarah.secret", "roomsarah_", "a.b_c", "x" * 30, "chloe..vip", "_x_"):
            for v in a.variantes(h):
                self.assertRegex(v, r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$", (h, v))
                self.assertNotEqual(a.norm(h), v)


class ControleGithubTests(unittest.IsolatedAsyncioTestCase):
    MAINTENANT = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)

    def test_cibles_attribuees_puis_prochains_du_stock(self):
        comptes = [{"etat": "à créer", "handle": "@Un.Fictif", "gerant": "Fictif", "onglet": "Jade", "ligne": 4},
                   {"etat": "GOOD", "handle": "vivant", "gerant": "Fictif", "onglet": "Jade", "ligne": 5},
                   {"etat": "à créer", "handle": "s1", "gerant": "", "onglet": "Jade", "ligne": 6},
                   {"etat": "à créer", "handle": "s2", "gerant": "", "onglet": "Jade", "ligne": 7},
                   {"etat": "A CREER", "handle": "s3", "gerant": "-", "onglet": "Jade", "ligne": 8},
                   {"etat": "à créer", "handle": "un.fictif", "gerant": "Autre", "onglet": "Jade", "ligne": 9}]
        self.assertEqual(["un.fictif", "s1", "s2"], [c["handle"] for c in a.cibles_ci(comptes, prochains=2)])

    def test_aller_retour_de_l_onglet(self):
        c = {"handle": "pris.fictif", "creatrice": "Jade", "onglet": "Jade", "ligne": "4", "gerant": "Fictif"}
        ex = {"verdict": a.PRIS, "profil_lu": True, "abonnes": 141, "publications": 1, "nom": "X", "bio": "Y", "a_nous": False,
              "neuf": False}
        lu = a.lire_ligne_ci(a.ligne_ci(c, ex, self.MAINTENANT, "pris_fictif"), self.MAINTENANT + timedelta(hours=2))
        self.assertEqual((a.PRIS, 141, 1, False, False, "pris_fictif"),
                         (lu["verdict"], lu["abonnes"], lu["publications"], lu["a_nous"], lu["neuf"], lu["variante"]))
        libre = a.ligne_ci({**c, "handle": "libre.fictif"}, {"verdict": a.LIBRE}, self.MAINTENANT)
        self.assertEqual(a.LIBRE, a.lire_ligne_ci(libre, self.MAINTENANT)["verdict"])
        self.assertIsNone(a.lire_ligne_ci(libre, self.MAINTENANT + timedelta(hours=a.CI_VALIDE_H + 1)))   # trop vieux : doute
        self.assertIsNone(a.lire_ligne_ci(a.ligne_ci(c, {"verdict": a.INCONNU}, self.MAINTENANT), self.MAINTENANT))
        illisible = a.ligne_ci(c, {"verdict": a.PRIS, "profil_lu": False}, self.MAINTENANT)
        self.assertFalse(a.lire_ligne_ci(illisible, self.MAINTENANT)["profil_lu"])

    def test_la_lecture_couvre_la_colonne_variante(self):
        self.assertEqual("'IG · Contrôle des @'!A2:N", a.plage_ci())          # 30/10 : A2:M perdait « Variante libre »
        self.assertEqual(len(a.ENTETE_CI), ord(a.plage_ci()[-1]) - ord("A") + 1)

    async def test_variante_du_controle_quand_la_cle_est_refusee(self):
        with patch.object(a, "actif", return_value=True), patch.object(a, "cle_refusee", return_value=True):
            with patch.object(a, "depuis_ci", AsyncMock(return_value={"verdict": a.PRIS, "variante": "pris_fictif"})):
                self.assertEqual("pris_fictif", await a.variante_libre("pris.fictif"))
                self.assertEqual("", await a.variante_libre("pris.fictif", exclus={"pris_fictif"}))
            with patch.object(a, "depuis_ci", AsyncMock(return_value={"verdict": a.PRIS, "variante": "autre.chose"})):
                self.assertEqual("", await a.variante_libre("pris.fictif"))   # jamais un @ qui n'est pas une de ses variantes


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
