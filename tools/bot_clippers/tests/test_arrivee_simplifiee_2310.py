"""23/10, 14 h 51 (Gaëtan : « un petit message à l'arrivée, le compte 1 avec ses étapes, le TL avec le numéro du clipper, puis on donne le
compte 1, on attend 48 h, le compte 2, 48 h, le compte 3 ») :
1. Le message d'arrivée tient en un seul message : bienvenue, créatrice, salon ℹ️, compte 1 avec 1️⃣ 2️⃣ 3️⃣, salon des codes cliquable.
2. Le TL reçoit la demande de groupe WhatsApp avec le numéro du clipper.
3. Les NOUVEAUX arrivants (fiche « simple ») ouvrent le compte 2 puis le compte 3 48 h après le précédent, sans condition de Reels ; les
   fiches d'avant gardent « 4 Reels ».
Cas fictifs, sans réseau ni Discord."""
import asyncio
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import codes_2fa  # noqa: E402
import dashboard  # noqa: E402
import parcours  # noqa: E402
import remise_compte1  # noqa: E402
from test_regles_2310 import clipper, monde  # noqa: E402

MAINTENANT = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def phrases(texte):
    """Les phrases d'un message, sans mise en forme : ≤ 10 mots chacune (règle des textes aux clippers)."""
    brut = re.sub(r"[`*]|<[^>]+>|https?://\S+", "", texte)
    return [p for bloc in brut.split("\n") for p in re.split(r"(?<=[.?!])\s+", bloc) if p.strip()]


# ------------------------------------------------------------------------------------------------ 1. le message d'arrivée
class MessageArriveeTests(unittest.TestCase):
    def modele(self, **kw):
        with patch.object(codes_2fa, "salon_codes_id", lambda: "555"):
            return remise_compte1.modele("<@42>", "compte_fictif", "fictif@example.invalid", "MDP_FICTIF", **kw)

    def test_etapes_numerotees_par_emoji_et_salon_des_codes_cliquable(self):
        texte = self.modele()
        for attendu in ("📱 **Ton compte 1**", "Identifiant :\n```\ncompte_fictif\n```", "E-mail :\n```\nfictif@example.invalid\n```",
                        "Mot de passe :\n```\nMDP_FICTIF\n```", "1️⃣ Instagram → Créer un compte → utilise cet e-mail.",
                        "2️⃣ Le code arrive dans <#555>. Appuie sur « 📩 Mon code ».", "3️⃣ "):
            self.assertIn(attendu, texte)
        self.assertLess(texte.index("1️⃣"), texte.index("2️⃣"))
        self.assertLess(texte.index("2️⃣"), texte.index("3️⃣"))

    def test_la_phrase_du_bouton_est_retiree(self):
        texte = self.modele()
        self.assertNotIn("Créé ? Appuie", texte)
        self.assertNotIn("Appuie sur le bouton", texte)

    def test_sans_id_de_salon_le_nom_est_dit(self):
        with patch.object(codes_2fa, "salon_codes_id", lambda: ""):
            texte = remise_compte1.modele("<@42>", "h", "m", "p")
        self.assertIn(f"#{codes_2fa.SALON_CODES_NOM}", texte)

    def test_ligne_des_delais_seulement_si_demandee(self):
        self.assertNotIn("48 h", self.modele())
        texte = self.modele(suite=parcours.LIGNE_48H)
        self.assertTrue(texte.endswith(parcours.LIGNE_48H))

    def test_bienvenue_courte_sans_creatrice_repetee(self):
        ctx = {"prenom": "Nina", "creatrice": "Sarah", "info": "<#777>"}
        for gabarit in (parcours.TEXTE_BIENVENUE, parcours.TEXTE_CREATRICE_LA):
            texte = parcours._rendre(gabarit, ctx)
            self.assertIn("<#777>", texte)
            self.assertIn("Google Drive", texte)
            self.assertEqual(1, texte.count("Sarah"), "la créatrice est dite une seule fois")
            self.assertNotIn("Garde ce message", texte)
            self.assertNotIn("!etape", texte)
        self.assertIn("Bienvenue dans l'agence, Nina", parcours._rendre(parcours.TEXTE_BIENVENUE, ctx))

    def test_message_complet_lisible_sur_telephone(self):
        ctx = {"prenom": "Nina", "creatrice": "Sarah", "info": "<#777>"}
        texte = "<@42> " + parcours._rendre(parcours.TEXTE_BIENVENUE, ctx) + "\n\n" + self.modele(suite=parcours.LIGNE_48H).removeprefix("<@42>").lstrip()
        self.assertLess(len(texte), 1990)
        self.assertNotIn("\n\n\n", texte)
        # 26/10 (Gaëtan) : trois blocs à copier, les deux délais sur deux lignes, rien après (les boutons suivent)
        self.assertEqual(3, texte.count(" :\n```\n"), "un bloc Copier par accès")
        self.assertTrue(texte.endswith("après la création du compte 1.\nLe compte 3, 48 h après le compte 2."))
        self.assertEqual(1, texte.count("<@42>"), "une seule mention, en tête")
        self.assertLess(texte.index("<#777>"), texte.index("Identifiant"), "les vidéos et le Drive sont tout en haut, avant le compte 1")
        for phrase in phrases(texte):
            self.assertLessEqual(len(phrase.split()), 14, phrase)
            self.assertNotIn("(", phrase)

    def test_le_complement_n_est_plus_envoye_quand_le_salon_est_deja_dans_le_message(self):
        """onboarding_discord.confirmer_accueil : le salon ℹ️ est déjà mentionné → aucun second message « Ta créatrice »."""
        import onboarding_discord
        message = N(content="<@42> bienvenue <#777> compte 1", author=N(id=9))
        salon = N(guild=N(me=N(id=9)), fetch_message=AsyncMock(return_value=message))
        envoyer = AsyncMock()
        with patch("process_livraison.envoyer_compte_1", envoyer):
            asyncio.run(onboarding_discord.confirmer_accueil(object(), salon, "42", "123", "Sarah", N(id=777)))
        envoyer.assert_not_awaited()


# ------------------------------------------------------------------------------------------------ 2. le TL et le numéro
class GroupeTLNumeroTests(unittest.TestCase):
    def envoyer(self, liaisons, uid="7", tl=None):
        fiches = {uid: {"prenom": "Mavie"}}
        salon = N(send=AsyncMock())
        pipeline = {"liaisons": liaisons}
        with patch.object(parcours, "_lire", lambda: fiches), patch.object(parcours, "_ecrire", lambda d: None), \
                patch.dict(parcours._deps, {"lire_json": lambda f, d: pipeline, "FICHIER_PIPELINE": "pipe"}):
            asyncio.run(parcours.demander_groupe_tl(salon, uid, tl or N(mention="<@9>"), "Mavie", "Sophie"))
        return salon.send.await_args.args[0], salon.send.await_args.kwargs

    def test_le_numero_du_clipper_est_affiche_tel_quel_avec_un_lien_whatsapp(self):
        texte, kw = self.envoyer({"7": {"tel": "+33612345678"}})
        self.assertIn("<@9>", texte)
        self.assertIn("crée le groupe WhatsApp de Mavie pour Sophie", texte)
        self.assertIn("Gaëtan", texte)
        self.assertIn("`+33612345678`", texte)
        self.assertIn("<https://wa.me/33612345678>", texte)
        self.assertIsNotNone(kw.get("view"), "le bouton « Groupe créé » reste")

    def test_numero_d_un_autre_clipper_jamais_montre(self):
        texte, _ = self.envoyer({"8": {"tel": "+33699999999"}, "7": {"tel": "+33611111111"}})
        self.assertIn("+33611111111", texte)
        self.assertNotIn("+33699999999", texte)

    def test_numero_sans_indicatif_affiche_sans_lien(self):
        texte, _ = self.envoyer({"7": {"tel": "0612345678"}})
        self.assertIn("`0612345678`", texte)
        self.assertNotIn("wa.me", texte)

    def test_numero_absent_le_dit_au_tl(self):
        texte, _ = self.envoyer({})
        self.assertIn("n'est pas dans son dossier", texte)
        self.assertNotIn("wa.me", texte)

    def test_pipeline_illisible_ne_leve_pas(self):
        fiches = {"7": {"prenom": "Mavie"}}
        salon = N(send=AsyncMock())

        def casse(f, d):
            raise OSError("fictif")
        with patch.object(parcours, "_lire", lambda: fiches), patch.object(parcours, "_ecrire", lambda d: None), \
                patch.dict(parcours._deps, {"lire_json": casse, "FICHIER_PIPELINE": "pipe"}):
            self.assertTrue(asyncio.run(parcours.demander_groupe_tl(salon, "7", N(mention="<@9>"), "Mavie", "Sophie")))
        self.assertIn("n'est pas dans son dossier", salon.send.await_args.args[0])

    def test_texte_sans_parenthese_et_phrases_courtes(self):
        texte, _ = self.envoyer({"7": {"tel": "+33612345678"}})
        self.assertNotIn("(", texte)
        for phrase in phrases(texte):
            self.assertLessEqual(len(phrase.split()), 10, phrase)


# ------------------------------------------------------------------------------------------------ 3. 48 h puis 48 h
class MarqueSimpleTests(unittest.TestCase):
    def test_arrivee_apres_la_date_est_marquee(self):
        with patch.object(parcours, "ARRIVEE_SIMPLE_DEPUIS", "2020-01-01T00:00:00+00:00"):
            self.assertTrue(parcours._marque_simple().get("simple"))

    def test_arrivee_avant_la_date_n_est_pas_marquee(self):
        with patch.object(parcours, "ARRIVEE_SIMPLE_DEPUIS", "2999-01-01T00:00:00+00:00"):
            self.assertEqual({}, parcours._marque_simple())

    def test_date_illisible_garde_l_ancien_parcours(self):
        with patch.object(parcours, "ARRIVEE_SIMPLE_DEPUIS", "pas une date"):
            self.assertEqual({}, parcours._marque_simple())

    def test_simple_lit_la_marque(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):                 # la règle du 23/10 (PARCOURS_SIMPLE_TOUS=0)
            self.assertTrue(parcours.simple({"simple": "2026-10-24T00:00:00+00:00"}))
            self.assertFalse(parcours.simple({}))
            self.assertFalse(parcours.simple(None))

    def test_depuis_le_24_10_tout_parcours_est_simple(self):
        self.assertTrue(parcours.simple({}))
        self.assertTrue(parcours.simple({"etape": 2, "ordre": "prive3"}))
        self.assertFalse(parcours.simple(None))


class EcheanceTests(unittest.TestCase):
    futur = {"type": "etape", "n": 2, "quand": "2099-01-01T00:00:00+00:00"}
    passe = {"type": "etape", "n": 2, "quand": "2020-01-01T00:00:00+00:00"}

    def test_parcours_simple_attend_ses_48_h(self):
        f = {"simple": "2026-10-24T00:00:00+00:00"}
        self.assertFalse(parcours._a_traiter(f, self.futur, MAINTENANT))
        self.assertTrue(parcours._a_traiter(f, self.passe, MAINTENANT))
        self.assertFalse(parcours._a_traiter(f, {**self.futur, "n": 3}, MAINTENANT))

    def test_ancien_parcours_n_est_pas_touche(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):
            self.assertTrue(parcours._a_traiter({}, self.futur, MAINTENANT), "15/10 : les anciens délais ne retardent pas le palier")
            self.assertTrue(parcours._a_traiter({}, {**self.futur, "n": 3}, MAINTENANT))

    def test_pas_de_reels_a_compter_pour_un_parcours_simple(self):
        f = {"simple": "x", "ordre": "prive3"}
        self.assertEqual([], parcours.sources_reels(f, 2))
        self.assertEqual([], parcours.sources_reels(f, 3))
        self.assertEqual(0, parcours._bloque_sources("1", f, 2))
        self.assertEqual([], parcours.sources_reels({"ordre": "prive3"}, 2), "24/10 : un ancien non plus")
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):
            self.assertEqual([1], parcours.sources_reels({"ordre": "prive3"}, 2), "un ancien compte garde ses 4 Reels")
            self.assertEqual([2], parcours.sources_reels({"ordre": "prive3"}, 3))


class OuvertureTests(unittest.IsolatedAsyncioTestCase):
    """Le programme ouvre le compte 2 ou 3 d'un parcours simple à l'heure dite, sans un seul Reel, et laisse un ancien attendre."""

    async def passer(self, fiche, maintenant):
        salon = N(id=5)
        membre = N(id=1, mention="<@1>")
        client = N(get_channel=lambda _id: salon)
        envoyer = AsyncMock(return_value=True)
        with monde({"1": fiche}) as (m, canal), patch.object(parcours, "envoyer_etape", envoyer), patch.object(parcours, "_suite", AsyncMock()), \
                patch.object(parcours, "_retirer_pret", AsyncMock()), patch.object(parcours, "_signaler_bloques", AsyncMock()), \
                patch.object(parcours, "_migrer_essai", lambda d: False), patch.dict(parcours._deps, {"membre_par_id": lambda uid: membre}):
            faits = await parcours._programme_du_jour(client, maintenant)
            return faits, envoyer, m["p"]["1"]

    def fiche(self, quand, **plus):
        # compte 1 créé le 24/10 à 8 h : ses 48 h sont faites le 26/10 à 8 h (MAINTENANT : 26/10, 9 h)
        return clipper(etape=2, salon_id="5", dates={"1": "2026-10-24T07:30:00+00:00", "1_fait": "2026-10-24T08:00:00+00:00"},
                       programme=[{"quand": quand, "type": "etape", "n": 2}], **plus)

    async def test_simple_apres_48_h_sans_reel_le_compte_2_part(self):
        faits, envoyer, f = await self.passer(self.fiche(iso(MAINTENANT - timedelta(minutes=1)), simple="x"), MAINTENANT)
        envoyer.assert_awaited_once()
        self.assertEqual(2, envoyer.await_args.args[2])
        self.assertEqual([("1", "etape", 2)], faits)
        self.assertEqual([], f["programme"])

    async def test_simple_avant_48_h_rien_ne_part_et_rien_n_est_dit(self):
        faits, envoyer, f = await self.passer(self.fiche(iso(MAINTENANT + timedelta(hours=5)), simple="x"), MAINTENANT)
        envoyer.assert_not_awaited()
        self.assertEqual([], faits)
        self.assertEqual(1, len(f["programme"]), "l'élément reste au programme")
        self.assertNotIn("attente_dite", f, "aucun « je vois N Reels » : il n'y a pas de Reels à attendre")

    async def test_ancien_parcours_part_aussi_48_h_apres_la_creation_sans_reel(self):
        # 24/10 (Gaëtan : « dans tous les cas, un compte toutes les 48 heures ») : un ancien, sans marque « simple », part aussi
        faits, envoyer, f = await self.passer(self.fiche(iso(MAINTENANT - timedelta(hours=60))), MAINTENANT)
        envoyer.assert_awaited_once()
        self.assertEqual([("1", "etape", 2)], faits)

    async def test_ancien_parcours_sous_l_ancienne_regle_attend_ses_reels(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):
            faits, envoyer, f = await self.passer(self.fiche(iso(MAINTENANT - timedelta(hours=60))), MAINTENANT)
        envoyer.assert_not_awaited()
        self.assertEqual([], faits)
        self.assertEqual(1, len(f["programme"]))


class FermetureTests(unittest.IsolatedAsyncioTestCase):
    """valider_etape ferme le compte n : le compte n+1 est programmé 48 h après la CRÉATION du compte n."""

    async def fermer(self, n, fiche):
        creation = datetime.now(timezone.utc) - timedelta(hours=1)
        membre = N(id=1, mention="<@1>")
        with monde({"1": fiche}) as (m, canal), patch.object(parcours, "_retirer_bouton", AsyncMock()), \
                patch.object(parcours, "_classeur_etat", AsyncMock()), patch.object(parcours, "_envoyer_publier", AsyncMock()), \
                patch.object(parcours, "_suite", AsyncMock()), patch.object(parcours, "_date_creation", lambda f, k: creation), \
                patch.dict(parcours._deps, {"membre_par_id": lambda uid: membre}):
            await parcours._apres_fermeture(N(id=5), "1", n, "bot", m["p"]["1"], False, False)
            return m["p"]["1"], creation

    def etape(self, f):
        return next(x for x in f["programme"] if x["type"] == "etape")

    async def test_compte_2_programme_48_h_apres_la_creation_du_compte_1(self):
        f, creation = await self.fermer(1, clipper(simple="x", etape=2, ordre="prive3"))
        quand = datetime.fromisoformat(self.etape(f)["quand"])
        self.assertEqual(2, self.etape(f)["n"])
        self.assertEqual(timedelta(hours=48), quand - creation.replace(microsecond=0))

    async def test_compte_3_programme_48_h_apres_la_creation_du_compte_2(self):
        f, creation = await self.fermer(2, clipper(simple="x", etape=3, ordre="prive3"))
        quand = datetime.fromisoformat(self.etape(f)["quand"])
        self.assertEqual(3, self.etape(f)["n"])
        self.assertEqual(timedelta(hours=48), quand - creation.replace(microsecond=0))

    async def test_ancien_parcours_garde_son_programme_sans_delai(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):                 # la règle du 23/10 pour une fiche d'avant
            f, creation = await self.fermer(1, clipper(etape=2, ordre="prive3"))
        self.assertEqual(creation.replace(microsecond=0), datetime.fromisoformat(self.etape(f)["quand"]))

    async def test_depuis_le_24_10_un_ancien_aussi_attend_48_h(self):
        f, creation = await self.fermer(1, clipper(etape=2, ordre="prive3"))
        self.assertEqual(timedelta(hours=48), datetime.fromisoformat(self.etape(f)["quand"]) - creation.replace(microsecond=0))


# ------------------------------------------------------------------------------------------------ les mots dits au clipper
class TextesDesDelaisTests(unittest.TestCase):
    def test_regle_des_comptes_sans_fiche_ou_simple_dit_48_h_sans_reels(self):
        for fiche in (None, {}, {"simple": "x"}):
            texte = parcours.regle_comptes(fiche)
            self.assertIn("48 h après la création du compte 1", texte, fiche)
            self.assertIn("48 h après la création du compte 2", texte, fiche)
            self.assertIn("Aucune condition de Reels", texte, fiche)

    def test_regle_des_comptes_d_un_ancien_garde_les_4_reels(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):                 # 24/10 : seulement sous PARCOURS_SIMPLE_TOUS=0
            texte = parcours.regle_comptes({"etape": 3, "dates": {"1": "2026-10-10T00:00:00+00:00"}, "ordre": "prive3"})
        self.assertIn("quatre Reels", texte)
        self.assertNotIn("48 h", texte)

    def test_ligne_du_matin_d_un_parcours_simple_donne_une_date(self):
        quand = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
        fiche = clipper(etape=2, salon_id="5", simple="x", ordre="prive3", dates={"1": "2026-10-26T09:00:00+00:00"},
                        programme=[{"quand": iso(quand), "type": "etape", "n": 2}])
        with monde({"1": fiche}), patch.object(parcours, "_comptes_ordonnes", lambda *a, **k: ["a", "b", "c"]), \
                patch.object(parcours, "_vivants", lambda *a, **k: ["a", "b", "c"]):
            ligne = parcours.prochaine_etape("5", MAINTENANT)
        self.assertIn("arrive ici le", ligne)
        self.assertIn("48 h après la création du compte 1", ligne)
        self.assertNotIn("Reels vus", ligne)
        self.assertNotIn("dès que je vois", ligne)

    def test_tableau_de_bord_dit_la_date_et_pas_zero_sur_quatre_reels(self):
        quand = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
        fiche = clipper(etape=2, simple="x", ordre="prive3", programme=[{"quand": iso(quand), "type": "etape", "n": 2}])
        ctx = N(parcours={"1": fiche}, maintenant=MAINTENANT)
        with patch.object(dashboard, "_module", lambda nom: parcours):
            texte = dashboard._etape_parcours(ctx, "1")
        self.assertEqual("compte 2 le 28/10", texte)


if __name__ == "__main__":
    unittest.main()
