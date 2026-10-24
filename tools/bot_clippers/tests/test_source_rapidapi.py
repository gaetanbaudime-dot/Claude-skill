"""24/10 : le bot lit Instagram par le suivi RapidAPI (« IG · Comptes », « IG · Reels »), plus par Apify. @ fictifs."""
import asyncio
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard  # noqa: E402
import etats_comptes as etats  # noqa: E402
import source_rapidapi as S  # noqa: E402

# 24/10 10 h UTC = 12 h à Paris ; minuit à Paris = 23/10 22 h UTC ; hier (Paris) = 23/10
T = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
ENTETE_C = ["Créatrice", "Gérant", "Type", "@", "ID Instagram", "Statut", "Followers", "Δ 24 h", "Δ 7 j", "Publications",
            "Reels 24 h", "Reels 7 j", "Reels 15 j", "Reels 30 j", "Reels 60 j", "Vues 7 j", "Vues 15 j", "Vues 30 j",
            "Vues 60 j", "Dernier Reel", "Profil relu le", "Reels relus le", "Renommé en"]
ENTETE_R = ["Créatrice", "Gérant", "Type", "@", "Code", "Lien", "Publié le", "Vues", "Likes", "Commentaires", "Relu le"]


def iso(dt):
    return dt.isoformat(timespec="seconds")


def compte(h, statut="public", followers="120", pubs="30", profil=T - timedelta(hours=4), reels=None, renomme="", ident="111"):
    reels = profil if reels is None else reels
    l = ["Sophie", "Demo", "Clipper", h, ident, statut, followers, "", "", pubs] + [""] * 10
    return l + [iso(profil) if profil else "", iso(reels) if reels else "", renomme]


def reel(h, code, publie, vues="1000"):
    return ["Sophie", "Demo", "Clipper", h, code, f"https://www.instagram.com/reel/{code}/", iso(publie), vues, "5", "", iso(T)]


hier_midi = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)          # 23/10 12 h à Paris
COMPTES = [ENTETE_C,
           compte("demo.public"),
           compte("demo.prive", statut="privé", followers="80", pubs="4"),
           compte("demo.mort", statut="introuvable", followers="", pubs=""),
           compte("demo.vieux", profil=T - timedelta(hours=40)),
           compte("demo.jamais", statut="pas encore relu", profil=None, reels=None),
           compte("demo.matin", reels=datetime(2026, 10, 23, 19, 0, tzinfo=timezone.utc)),   # Reels relus hier 21 h (Paris)
           compte("demo.ancien", renomme="demo.nouveau", ident="222")]
REELS = [ENTETE_R,
         reel("demo.public", "AAA", hier_midi),
         reel("demo.public", "AAA", hier_midi),                          # doublon : compté une fois
         reel("demo.public", "BBB", hier_midi - timedelta(hours=3)),
         reel("demo.public", "CCC", T - timedelta(days=4)),
         reel("demo.public", "DDD", T - timedelta(days=20)),
         reel("demo.public", "EEE", T - timedelta(hours=1)),             # aujourd'hui
         reel("demo.matin", "MMM", hier_midi),
         reel("demo.ancien", "NNN", hier_midi)]

CLES = ["demo.public", "demo.prive", "demo.mort", "demo.vieux", "demo.jamais", "demo.matin", "demo.ancien", "demo.nouveau",
        "demo.acreer"]


def lire():
    items, infos = S.fiches(CLES, COMPTES, REELS, T)
    return S.ajuster(etats._lire_items(items, CLES, T), infos)


class FichesTests(unittest.TestCase):
    def test_public_lu_avec_tous_ses_reels(self):
        f = lire()["demo.public"]
        self.assertTrue(f["lu"] and f["existe"] and f["reels_lus"])
        self.assertEqual((f["followers"], f["posts_total"], f["ig_id"]), (120, 30, "111"))
        self.assertEqual(f["reels_hier"], 2)                             # AAA (une fois) et BBB, la veille à Paris
        self.assertEqual(f["reels_7j"], 3)                               # + CCC ; EEE est d'aujourd'hui, DDD a 20 jours
        self.assertFalse(f["plafonne"])
        self.assertTrue(etats._couvre_depuis(f, T - timedelta(days=30)))  # 60 jours vus en entier
        self.assertEqual({p["type_verifie"] for p in f["publications_verifiees"]}, {"reel"})   # preuves du parcours
        self.assertEqual(f["collecte_iso"], iso(T - timedelta(hours=4)))  # daté du relevé RapidAPI, pas du passage du bot
        # la série reçoit chaque Reel des 60 jours avec ses vues (Apify n'en donnait que 12)
        self.assertEqual(sorted(r["code"] for r in f["serie_reels"]), ["AAA", "BBB", "CCC", "DDD", "EEE"])
        self.assertEqual({r["vues"] for r in f["serie_reels"]}, {1000})

    def test_prive_introuvable(self):
        out = lire()
        self.assertTrue(out["demo.prive"]["lu"] and out["demo.prive"]["prive"])
        self.assertEqual(out["demo.prive"]["followers"], 80)
        self.assertTrue(out["demo.mort"]["lu"])
        self.assertFalse(out["demo.mort"]["existe"])                     # « introuvable » explicite

    def test_rien_conclu_sans_releve_frais(self):
        out = lire()
        for h in ("demo.vieux", "demo.jamais"):
            self.assertFalse(out[h]["lu"], h)
            self.assertFalse(out[h].get("hors_suivi"), h)
        self.assertTrue(out["demo.vieux"]["vieux"])

    def test_hors_suivi_jamais_compte(self):
        f = lire()["demo.acreer"]
        self.assertEqual((f["lu"], f["budget"], f["hors_suivi"]), (False, True, True))

    def test_reels_relus_avant_minuit_pas_lus(self):
        f = lire()["demo.matin"]
        self.assertTrue(f["lu"] and f["existe"])
        self.assertFalse(f["reels_lus"])                                 # la veille vue jusqu'à 21 h seulement : cellules gardées
        self.assertEqual(etats._valeurs_reels("demo.matin", f, [], "2026-10-24", T), {})

    def test_renomme_suivi_sous_ses_deux_at(self):
        out = lire()
        self.assertEqual(out["demo.ancien"]["reels_hier"], 1)
        self.assertTrue(out["demo.nouveau"]["lu"])
        self.assertEqual(out["demo.nouveau"]["ig_id"], "222")

    def test_en_tete_absente_et_dernier_releve(self):
        items, _ = S.fiches(["demo.public"], COMPTES[1:], REELS[1:], T)
        self.assertEqual(items[0]["followersCount"], 120)
        self.assertEqual(S.dernier_releve(COMPTES, T), iso(T - timedelta(hours=4)))
        self.assertEqual(S.dernier_releve([ENTETE_C], T), "")


class ScannerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.fichier = Path(self.dossier.name) / "etats.json"
        lire_json = lambda f, d: json.loads(Path(f).read_text()) if Path(f).exists() else d          # noqa: E731
        ecrire_json = lambda f, d: Path(f).write_text(json.dumps(d))                                # noqa: E731
        self.deps = patch.object(etats, "_deps", {"lire_json": lire_json, "ecrire_json": ecrire_json, "FICHIER_ETATS": self.fichier})
        self.deps.start()

    async def asyncTearDown(self):
        self.deps.stop()
        self.dossier.cleanup()

    async def test_scanner_sans_apify_ni_budget(self):
        maintenant = datetime.now(timezone.utc)
        comptes = [ENTETE_C, compte("demo.public", profil=maintenant - timedelta(minutes=30))]
        with patch.object(etats, "SOURCE_IG", "rapidapi"), \
                patch.object(S, "lire_onglets", AsyncMock(return_value=(comptes, [ENTETE_R]))), \
                patch.object(etats, "garde_apify", AsyncMock(side_effect=AssertionError("budget Apify"))), \
                patch.object(etats, "_apify", AsyncMock(side_effect=AssertionError("appel Apify"))):
            out = await etats.scanner(["@demo.public", "demo.acreer"])
        self.assertTrue(out["demo.public"]["lu"])
        self.assertTrue(out["demo.acreer"]["hors_suivi"])
        noté = json.loads(self.fichier.read_text())["source_instagram"]
        self.assertEqual(noté, {"source": "rapidapi", "releve": iso(maintenant - timedelta(minutes=30))})

    async def test_onglets_illisibles_rien_conclu(self):
        with patch.object(etats, "SOURCE_IG", "rapidapi"), patch.object(S, "lire_onglets", AsyncMock(return_value=None)):
            self.assertIsNone(await etats.scanner(["demo.public"]))

    async def test_actif_sans_cle_apify(self):
        with patch.object(etats, "SOURCE_IG", "rapidapi"), patch.object(etats, "APIFY_TOKEN", ""), \
                patch.object(etats.onboarding, "actif", lambda: True):
            self.assertTrue(etats.actif())
        with patch.object(etats, "SOURCE_IG", "apify"), patch.object(etats, "APIFY_TOKEN", ""), \
                patch.object(etats.onboarding, "actif", lambda: True):
            self.assertFalse(etats.actif())

    async def test_releve_note_au_demarrage(self):
        self.fichier.write_text(json.dumps({"apify_budget": {"coupe": True}, "apify_local": {"entrees": [1]}}))
        with patch.object(etats, "SOURCE_IG", "rapidapi"), \
                patch.object(S, "lire_onglets", AsyncMock(return_value=(COMPTES, REELS))):
            self.assertEqual(await etats.noter_source_instagram(), iso(T - timedelta(hours=4)))
        d = json.loads(self.fichier.read_text())
        self.assertNotIn("apify_budget", d)                              # « budget atteint » ne reste pas affiché pour toujours
        self.assertEqual(d["apify_local"], {"entrees": [1]})
        self.assertEqual(d["source_instagram"]["source"], "rapidapi")


    async def test_matin_attend_le_releve_du_jour(self):
        matin = datetime(2026, 10, 24, 7, 0, tzinfo=timezone.utc)      # 9 h à Paris
        hier_soir = [ENTETE_C, compte("demo.public", profil=datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc))]
        ce_matin = [ENTETE_C, compte("demo.public", profil=datetime(2026, 10, 24, 6, 11, tzinfo=timezone.utc))]
        with patch.object(etats, "SOURCE_IG", "rapidapi"):
            with patch.object(S, "lire_onglets", AsyncMock(return_value=(hier_soir, [ENTETE_R]))):
                self.assertTrue(await etats._attendre_releve_du_matin(matin))
                self.assertFalse(await etats._attendre_releve_du_matin(matin.replace(hour=11)))   # 13 h à Paris : on n'attend plus
            with patch.object(S, "lire_onglets", AsyncMock(return_value=(ce_matin, [ENTETE_R]))):
                self.assertFalse(await etats._attendre_releve_du_matin(matin))
            with patch.object(S, "lire_onglets", AsyncMock(return_value=None)):
                self.assertFalse(await etats._attendre_releve_du_matin(matin))   # illisible : le passage le dira lui-même
        with patch.object(etats, "SOURCE_IG", "apify"):
            self.assertFalse(await etats._attendre_releve_du_matin(matin))


class DashboardTests(unittest.TestCase):
    def ctx(self, releve, maintenant=T):
        c = dashboard._Ctx({"etats": {"source_instagram": {"source": "rapidapi", "releve": iso(releve)},
                                      "leger_iso": iso(maintenant - timedelta(minutes=5)),
                                      "apify_budget": {"usage_usd": 12.3, "budget_usd": 25}}}, maintenant)
        return c

    def test_titre_dit_le_releve_rapidapi_pas_apify(self):
        c = self.ctx(T - timedelta(hours=4))
        with patch.object(etats, "SOURCE_IG", "rapidapi"):
            txt, alerte = dashboard._fraicheur_apify(c)
            self.assertNotIn("Apify", txt)
            self.assertIsNone(alerte)
            self.assertIn("prochain vers 14 h", txt)                     # cron 12 h UTC = 14 h à Paris (heure d'été)
            self.assertEqual(dashboard._dernier_instagram(c), T - timedelta(hours=4))   # l'heure du relevé, pas du passage

    def test_suivi_en_panne_alerte(self):
        c = self.ctx(T - timedelta(hours=20))
        with patch.object(etats, "SOURCE_IG", "rapidapi"):
            txt, alerte = dashboard._fraicheur_apify(c)
        self.assertIn("pas relu depuis le 23/10", txt)
        self.assertEqual(alerte[1], "important")

    def test_retour_apify(self):
        c = self.ctx(T - timedelta(hours=4))
        with patch.object(etats, "SOURCE_IG", "apify"):
            self.assertIsNone(dashboard._suivi_rapidapi(c))
            self.assertEqual(dashboard._dernier_instagram(c), T - timedelta(minutes=5))


if __name__ == "__main__":
    unittest.main()
