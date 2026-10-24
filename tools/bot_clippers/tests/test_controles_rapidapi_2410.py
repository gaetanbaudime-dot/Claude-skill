"""24/10 (Gaëtan : « essaie de développer la recherche d'un Instagram légèrement changé avec RapidAPI. Tout ce qui est contrôle,
fraîcheur et faux chiffres, développe-le avec RapidAPI plutôt que ce qu'on avait de base avec Apify ») :
1. le suivi RapidAPI relève nom, bio, lien en bio, légende, dimensions et couverture des Reels, et ne croit jamais une chute à 0 ;
2. un compte introuvable sans ID connu est cherché sous ses @ proches (« IG · Variantes ») ;
3. le bot lit tout ça : bio et lien du privé (C10), liens dans les légendes, compte retrouvé (bio du bot) ou renommé (même ID).
Cas fictifs, sans réseau."""
import asyncio
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import etats_comptes as etats  # noqa: E402
import instagram_rapidapi as I  # noqa: E402
import source_rapidapi as S  # noqa: E402
from test_source_rapidapi import ENTETE_R, compte, iso, reel  # noqa: E402

T = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
BIO_BOT = "Fan de Sophie 💛 Ses meilleurs moments, chaque jour"            # profil.BIOS[0] pour Sophie


# ------------------------------------------------------------------------------------------------ 1. le relevé RapidAPI
class ReleveTests(unittest.TestCase):
    def test_bio_nom_et_liens_du_profil(self):
        corps = {"user": {"pk": 9, "username": "demo", "full_name": "Sophie fan", "biography": "Coucou",
                          "external_url": "https://exemple.invalid/a", "bio_links": [{"url": "https://exemple.invalid/a"},
                                                                                     {"url": "https://exemple.invalid/b"}]}}
        b = I.lire_bio(corps)
        self.assertEqual((b["lu"], b["nom"], b["bio"]), (True, "Sophie fan", "Coucou"))
        self.assertEqual(b["liens"], ["https://exemple.invalid/a", "https://exemple.invalid/b"])
        self.assertEqual(I.lire_bio({"user": {"pk": 9, "biography": ""}})["lu"], True, "bio vide relue : vraiment vide")
        self.assertEqual(I.lire_bio({"user": {"pk": 9}})["lu"], False, "champ absent : rien conclu")

    def test_legende_dimensions_et_couverture_des_reels(self):
        corps = {"items": [{"media": {"code": "R1", "taken_at": 1761134400, "ig_play_count": 10, "caption": {"text": "go @quelquun"},
                                      "original_width": 1080, "original_height": 1920, "video_duration": 12.5,
                                      "image_versions2": {"candidates": [{"url": "https://cdn.invalid/c.jpg"}]}}},
                           {"media": {"code": "R2", "taken_at": 1761134400, "caption": None}}]}
        reels, _ = I.lire_reels(corps)
        r1, r2 = reels
        self.assertEqual((r1["legende"], r1["largeur"], r1["hauteur"], r1["duree"]), ("go @quelquun", 1080, 1920, 12.5))
        self.assertEqual(r1["image"], "https://cdn.invalid/c.jpg")
        self.assertIsNone(r2["legende"])
        d = I.fusionner_reels({"R1": {"publie": "p", "legende": "ancienne"}}, reels, T)
        self.assertEqual(d["R1"]["legende"], "go @quelquun")

    def test_jamais_un_faux_zero(self):
        self.assertTrue(I.suspect([["t", 1200, 40]], 0))
        self.assertFalse(I.suspect([["t", 12, 4]], 0), "petit compte : 0 est crédible")
        self.assertFalse(I.suspect([], 0))
        self.assertFalse(I.suspect([["t", 1200, 40]], 1150))
        store = {"comptes": {"demo": {"id": "9", "suivi": [["t", 1200, 40]]}}}

        async def appeler(session, chemin, params):
            return 200, {"user": {"pk": 9, "username": "demo", "follower_count": 0, "media_count": 0, "is_private": False,
                                  "biography": BIO_BOT}}
        with patch.object(I, "appeler", appeler):
            self.assertTrue(asyncio.run(I.relire_profil(None, store, "demo", T)))
        e = store["comptes"]["demo"]
        self.assertEqual(e["suivi"], [["t", 1200, 40]], "le relevé d'avant reste")
        self.assertIn("followers_suspect", e)
        self.assertEqual(e["bio"], BIO_BOT)

    def test_colonnes_ajoutees_aux_onglets(self):
        suivis = [{"handle": "demo", "creatrice": "Sophie", "gerant": "Thia", "type": "Clipper"},
                  {"handle": "neuf", "creatrice": "Sophie", "gerant": "Thia", "type": "Clipper"}]
        store = {"comptes": {"demo": {"id": "9", "statut": "public", "suivi": [[iso(T), 50, 3]], "profil_le": iso(T),
                                      "nom": "Fan", "bio": BIO_BOT, "liens": [], "bio_le": iso(T)},
                             "neuf": {"statut": "public", "profil_le": iso(T)}},
                 "reels": {"demo": {"R1": {"publie": iso(T - timedelta(days=1)), "vues": 5, "legende": "ok", "largeur": 1080,
                                           "hauteur": 1920, "duree": 9.0, "image": "https://cdn.invalid/c.jpg"},
                                    "R0": {"publie": iso(T - timedelta(days=10)), "vues": 5, "image": "https://cdn.invalid/v.jpg"}}}}
        lignes = {l[3]: l for l in I.lignes_comptes(suivis, store, T)}
        self.assertEqual(len(lignes["demo"]), len(I.ENTETE_COMPTES))
        self.assertEqual(lignes["demo"][23:], ["Fan", BIO_BOT, "aucun"])
        self.assertEqual(lignes["neuf"][23:], ["", "", ""], "bio jamais relue : vide")
        detail = {l[4]: l for l in I.lignes_reels(suivis, store, T, detail=True)}
        self.assertEqual(len(detail["R1"]), len(I.ENTETE_REELS_DETAIL))
        self.assertEqual(detail["R1"][11:], ["ok", "1080", "1920", "9.0", "https://cdn.invalid/c.jpg"])
        self.assertEqual(detail["R0"][15], "", "couverture des Reels récents seulement")
        self.assertEqual(len(I.lignes_reels(suivis, store, T)[0]), len(I.ENTETE_REELS), "l'archive reste légère")


# ------------------------------------------------------------------------------------------------ 2. les @ proches
class VariantesTests(unittest.TestCase):
    def passer(self, store, suivis, existants):
        appels = []

        async def appeler(session, chemin, params):
            appels.append((chemin, dict(params)))
            if chemin == I.API["id"][0]:
                nom = params.get("user") or params.get("username")
                return (200, {"status": True, "user_id": existants[nom]["id"]}) if nom in existants else (404, {"message": "User not found"})
            i = params.get("id_user") or params.get("id")
            p = next(v for v in existants.values() if v["id"] == i)
            return 200, {"user": {"pk": i, "username": "x", "follower_count": p.get("followers", 3), "is_private": False,
                                  "full_name": "Fan", "biography": p.get("bio", "")}}
        I._jour.update({"jour": "", "n": 0, "restant": None})
        with patch.object(I, "appeler", appeler):
            bilan = asyncio.run(I.chercher_variantes(None, store, suivis, T))
        return bilan, appels

    def suivis(self, *h):
        return [{"handle": x, "creatrice": "Sophie", "gerant": "Thia", "type": "Clipper"} for x in h]

    def test_compte_introuvable_cherche_sous_ses_variantes(self):
        store = {"comptes": {"demo.fan": {"statut": "introuvable"}, "autre": {"statut": "public", "id": "55"}}}
        bilan, appels = self.passer(store, self.suivis("demo.fan", "autre"), {"demo.fan1": {"id": "77", "bio": BIO_BOT},
                                                                              "demo_fan": {"id": "55"}})
        res = store["variantes"]["demo.fan"]["resultats"]
        self.assertEqual(res["demo.fan1"]["statut"], "existe")
        self.assertEqual(res["demo.fan1"]["bio"], BIO_BOT)
        self.assertEqual(res["demo_fan"]["statut"], "déjà suivi", "même ID qu'un compte suivi : jamais une variante")
        self.assertEqual(res["demo.fan2"]["statut"], "introuvable")
        self.assertTrue(store["variantes"]["demo.fan"]["complet"])
        self.assertEqual(bilan["comptes"], 1)
        lignes = I.lignes_variantes(self.suivis("demo.fan"), store)
        self.assertEqual(len(lignes[0]), len(I.ENTETE_VARIANTES))
        # une fois par jour : le passage suivant du même jour ne redemande rien
        n = len(appels)
        _, appels2 = self.passer(store, self.suivis("demo.fan", "autre"), {})
        self.assertEqual(appels2, [])
        self.assertGreater(n, 0)

    def test_compte_deja_vu_vivant_ou_suivi_jamais_cherche(self):
        store = {"comptes": {"vu": {"statut": "introuvable", "id": "12"}, "ok": {"statut": "public"}}}
        _, appels = self.passer(store, self.suivis("vu", "ok"), {})
        self.assertEqual(appels, [])

    def test_variantes_oubliees_quand_le_compte_reapparait(self):
        store = {"comptes": {"demo.fan": {"statut": "public", "id": "9"}}, "variantes": {"demo.fan": {"jour": "x"}}}
        self.passer(store, self.suivis("demo.fan"), {})
        self.assertEqual(store["variantes"], {})


# ------------------------------------------------------------------------------------------------ 3. ce que le bot en fait
ENTETE_C = ["Créatrice", "Gérant", "Type", "@", "ID Instagram", "Statut", "Followers", "Δ 24 h", "Δ 7 j", "Publications",
            "Reels 24 h", "Reels 7 j", "Reels 15 j", "Reels 30 j", "Reels 60 j", "Vues 7 j", "Vues 15 j", "Vues 30 j",
            "Vues 60 j", "Dernier Reel", "Profil relu le", "Reels relus le", "Renommé en", "Nom", "Bio", "Lien en bio"]
ENTETE_RD = ENTETE_R + ["Légende", "Largeur", "Hauteur", "Durée (s)", "Couverture"]


def compte_bio(h, nom="", bio="", liens="aucun", **kw):
    return compte(h, **kw) + [nom, bio, liens]


class BotTests(unittest.TestCase):
    def test_bio_et_lien_du_prive_relus(self):
        comptes = [ENTETE_C, compte_bio("demo.prv", statut="privé", liens="https://lien.invalid/13", bio=BIO_BOT),
                   compte_bio("demo.vide"), compte("demo.ancien")]
        cles = ["demo.prv", "demo.vide", "demo.ancien"]
        items, infos = S.fiches(cles, comptes, [ENTETE_RD], T)
        out = S.ajuster(etats._lire_items(items, cles, T), infos)
        self.assertEqual((out["demo.prv"]["bio_lu"], out["demo.prv"]["bio_liens"]), (True, ["https://lien.invalid/13"]))
        self.assertEqual(out["demo.prv"]["bio"], BIO_BOT)
        self.assertEqual((out["demo.vide"]["bio_lu"], out["demo.vide"]["bio_liens"]), (True, []), "relue, sans lien")
        self.assertFalse(out["demo.ancien"]["bio_lu"], "onglet sans les colonnes : bio pas relue, rien conclu")

    def test_lien_dans_une_legende_et_format_du_reel(self):
        comptes = [ENTETE_C, compte_bio("demo.pub")]
        l = reel("demo.pub", "R1", T - timedelta(hours=3)) + ["mon lien www.exemple.invalid", "1080", "1920", "11.0", "https://cdn.invalid/c.jpg"]
        items, infos = S.fiches(["demo.pub"], comptes, [ENTETE_RD, l], T)
        f = S.ajuster(etats._lire_items(items, ["demo.pub"], T), infos)["demo.pub"]
        self.assertEqual(f["fautes"], 1, "lien dans la légende d'un Reel des dernières 24 h")
        r = f["reels"][0]
        self.assertEqual((r["legende"], r["largeur"], r["hauteur"], r["duree"], r["image"]),
                         ("mon lien www.exemple.invalid", 1080, 1920, 11.0, "https://cdn.invalid/c.jpg"))
        self.assertEqual(f["dernier"]["image"], "https://cdn.invalid/c.jpg", "la couverture du premier Reel fêté")

    def test_renomme_sur_instagram_dans_la_fiche(self):
        comptes = [ENTETE_C, compte_bio("demo.ancien", renomme="demo.neuf")]
        items, infos = S.fiches(["demo.ancien", "demo.neuf"], comptes, [ENTETE_RD], T)
        out = S.ajuster(etats._lire_items(items, ["demo.ancien", "demo.neuf"], T), infos)
        self.assertEqual(out["demo.ancien"]["renomme_en"], "demo.neuf")
        self.assertNotIn("renomme_en", out["demo.neuf"])

    def test_variantes_lues_au_format_du_scan(self):
        entete = I.ENTETE_VARIANTES
        lignes = [entete, ["demo.fan", "Sophie", "Thia", "demo.fan1", "existe", "77", "3", "Fan", BIO_BOT, iso(T)],
                  ["demo.fan", "Sophie", "Thia", "demo.fan2", "introuvable", "", "", "", "", iso(T)],
                  ["demo.fan", "Sophie", "Thia", "demo_fan", "déjà suivi", "55", "", "", "", iso(T)],
                  ["demo.fan", "Sophie", "Thia", "demo.fann", "existe", "88", "3", "", BIO_BOT, iso(T - timedelta(hours=40))]]
        m = S.variantes(lignes, ["demo.fan1", "demo.fan2", "demo_fan", "demo.fann", "demo.fan_"], T)
        self.assertTrue(etats.est_a_nous(m["demo.fan1"], "Sophie"))
        self.assertEqual((m["demo.fan2"]["lu"], m["demo.fan2"]["existe"]), (True, False))
        self.assertFalse(etats.est_a_nous(m["demo_fan"], "Sophie"), "un compte déjà suivi n'est jamais « à nous » pour une autre ligne")
        self.assertFalse(m["demo.fann"]["lu"], "cherché il y a trop longtemps : non lu")
        self.assertFalse(m["demo.fan_"]["lu"], "pas encore cherché : non lu")
        self.assertEqual(S.variantes([], ["x"], T), {"x": {"lu": False}})

    def test_chercher_variantes_du_bot_par_rapidapi(self):
        lignes = [I.ENTETE_VARIANTES] + [["demo.fan", "Sophie", "Thia", v, st, "77" if st == "existe" else "", "3", "Fan",
                                           BIO_BOT if st == "existe" else "", iso(datetime.now(timezone.utc))]
                                          for v, st in (("demo.fan1", "existe"), ("demo_fan", "introuvable"), ("demo.fann", "introuvable"),
                                                        ("demo.fan2", "introuvable"), ("demo.fan_", "introuvable"))]
        ligne = {"handle": "demo.fan", "creatrice": "Sophie", "gerant": "Thia"}
        with patch.object(etats, "SOURCE_IG", "rapidapi"), patch.object(etats, "_deps", {}), \
                patch.object(S, "lire_onglets", AsyncMock(return_value=([ENTETE_C], [ENTETE_RD], lignes))), \
                patch.object(etats, "scanner", AsyncMock(side_effect=AssertionError("aucun scan Apify"))):
            trouves, perdus = asyncio.run(etats.chercher_variantes([ligne]))
        self.assertEqual([(c["handle"], v) for c, v in trouves], [("demo.fan", "demo.fan1")])
        self.assertEqual(perdus, [])
        # aucune variante à nous, toutes cherchées : la ligne est introuvable (le clipper est prévenu)
        lignes_perdu = [l if l[3] != "demo.fan1" else l[:4] + ["introuvable", "", "", "", "", l[9]] for l in lignes]
        with patch.object(etats, "SOURCE_IG", "rapidapi"), patch.object(etats, "_deps", {}), \
                patch.object(S, "lire_onglets", AsyncMock(return_value=([ENTETE_C], [ENTETE_RD], lignes_perdu))):
            trouves, perdus = asyncio.run(etats.chercher_variantes([ligne]))
        self.assertEqual((trouves, [c["handle"] for c in perdus]), ([], ["demo.fan"]))
        # une variante pas encore cherchée : rien conclu
        with patch.object(etats, "SOURCE_IG", "rapidapi"), patch.object(etats, "_deps", {}), \
                patch.object(S, "lire_onglets", AsyncMock(return_value=([ENTETE_C], [ENTETE_RD], lignes_perdu[:-1]))):
            self.assertEqual(asyncio.run(etats.chercher_variantes([ligne])), ([], []))


class RenommageTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_au_clipper_quand_il_a_renomme(self):
        import parcours
        dit = AsyncMock(return_value=True)
        with patch.object(parcours, "proprietaire", lambda h: ("42", 1) if h == "demo.ancien" else ("", 0)), \
                patch.object(parcours, "renommer", AsyncMock(return_value=(True, ""))), patch.object(parcours, "_dire_au_clipper", dit):
            self.assertTrue(await parcours.compte_retrouve(None, "demo.ancien", "demo.neuf", renomme=True))
        texte = dit.await_args.args[2]
        self.assertIn("s'appelle maintenant `demo.neuf`", texte)
        self.assertNotIn("était pris", texte)


if __name__ == "__main__":
    unittest.main()
