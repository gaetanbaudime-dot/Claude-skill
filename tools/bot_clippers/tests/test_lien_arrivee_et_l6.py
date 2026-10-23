"""23/10 (Gaëtan : « je vais passer au forfait supérieur à 100 liens. Cohorte : Sarah. La règle L6, c'est très bien ») :
1. L6 des règles gelées : compte 1 non créé 48 h après la remise → avertissement ; sortie 48 h après l'avertissement, validée par le manager.
2. Le lien GAML créé à l'arrivée pour TOUS (app au jour 3), derrière LIEN_ARRIVEE_TOUS, éteint par défaut ; le clipper ne le voit pas avant son
   compte privé (`!mesclics`, contexte de l'assistant) ; `!app` répond dès le jour 3.
Cas fictifs, sans réseau ni Discord."""
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import paie_clics  # noqa: E402
import parcours  # noqa: E402
import sortie_auto  # noqa: E402
from test_regles_2310 import LIEN, avec_lien, clipper, monde  # noqa: E402

VAR_ARRIVEE = "LIEN_ARRIVEE_TOUS"
MAINTENANT = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def fiche_remise(heures, **plus):
    """Un clipper dont le compte 1 a été remis il y a `heures` heures, jamais créé."""
    return {"1": {"prenom": "Nina", "creatrice": "Chloé", "etape": 1, "dates": {"1": iso(MAINTENANT - timedelta(hours=heures))}, **plus}}


# ---------------------------------------------------------------------------------------------------------------------- L6
class RegleL6Tests(unittest.TestCase):
    def ref(self, heures):
        return iso(MAINTENANT - timedelta(hours=heures))

    def test_les_chiffres_de_la_regle_gelee(self):
        self.assertEqual((48, 48), (sortie_auto.AVERTIR_APRES_H, sortie_auto.SORTIE_APRES_AVERTISSEMENT_H))
        self.assertEqual(4, sortie_auto.JOURS_COMPTE1)
        self.assertFalse(sortie_auto.RETRAIT_AUTOMATIQUE, "la sortie reste validée par le manager")

    def test_la_variable_railway_d_avant_n_a_plus_d_effet(self):
        with patch.dict(os.environ, {"SORTIE_JOURS_COMPTE1": "1"}):
            import importlib
            recharge = importlib.reload(sortie_auto)
            try:
                self.assertEqual(4, recharge.JOURS_COMPTE1)
            finally:
                importlib.reload(sortie_auto)

    def test_pas_d_avertissement_avant_48_h(self):
        self.assertEqual([], sortie_auto.a_avertir_compte1(fiche_remise(24), {}, MAINTENANT, quand={}))
        self.assertEqual([], sortie_auto.a_avertir_compte1(fiche_remise(40), {}, MAINTENANT, quand={}))

    def test_avertissement_a_48_h_et_la_tolerance_de_la_passe_quotidienne(self):
        for heures in (46, 48, 60, 200):
            a_dire = sortie_auto.a_avertir_compte1(fiche_remise(heures), {}, MAINTENANT, quand={})
            self.assertEqual(["1"], [u for u, *_ in a_dire], f"{heures} h")

    def test_un_seul_avertissement_par_remise(self):
        fiches = fiche_remise(60)
        ref = self.ref(60)
        self.assertEqual([], sortie_auto.a_avertir_compte1(fiches, {"1": ref}, MAINTENANT, quand={"1": iso(MAINTENANT)}))

    def test_un_avertissement_d_avant_le_23_10_sans_instant_est_refait(self):
        """L'ancien texte n'annonçait aucune échéance : sans instant gardé, le clipper reçoit celui de L6 avant toute sortie."""
        fiches = fiche_remise(60)
        self.assertEqual(["1"], [u for u, *_ in sortie_auto.a_avertir_compte1(fiches, {"1": self.ref(60)}, MAINTENANT, quand={})])

    def test_jamais_de_sortie_sans_avertissement(self):
        fiches = fiche_remise(500)
        self.assertEqual([], sortie_auto.a_sortir_compte1(fiches, MAINTENANT, deja={}, quand={}))
        self.assertEqual([], sortie_auto.a_sortir_compte1(fiches, MAINTENANT, deja={"1": self.ref(500)}, quand={}))

    def test_sortie_48_h_apres_l_avertissement_pas_avant(self):
        fiches = fiche_remise(200)
        ref = self.ref(200)
        for heures, attendu in ((0, []), (24, []), (40, []), (46, ["1"]), (48, ["1"]), (100, ["1"])):
            quand = {"1": iso(MAINTENANT - timedelta(hours=heures))}
            sortants = sortie_auto.a_sortir_compte1(fiches, MAINTENANT, deja={"1": ref}, quand=quand)
            self.assertEqual(attendu, [u for u, *_ in sortants], f"averti il y a {heures} h")

    def test_un_avertissement_pour_une_autre_remise_ne_compte_pas(self):
        fiches = fiche_remise(200)
        quand = {"1": iso(MAINTENANT - timedelta(hours=100))}
        self.assertEqual([], sortie_auto.a_sortir_compte1(fiches, MAINTENANT, deja={"1": "2026-01-01T00:00:00+00:00"}, quand=quand))

    def test_un_instant_illisible_ne_fait_sortir_personne(self):
        fiches = fiche_remise(200)
        self.assertEqual([], sortie_auto.a_sortir_compte1(fiches, MAINTENANT, deja={"1": self.ref(200)}, quand={"1": "n'importe quoi"}))

    def test_compte_cree_ou_protege_n_est_ni_averti_ni_sorti(self):
        crees = fiche_remise(200)
        crees["1"]["dates"]["1_fait"] = iso(MAINTENANT)
        self.assertEqual([], sortie_auto.a_avertir_compte1(crees, {}, MAINTENANT, quand={}))
        garde = fiche_remise(200)
        self.assertEqual([], sortie_auto.a_avertir_compte1(garde, {}, MAINTENANT, quand={}, notes=lambda uid: ["garde"]))

    def test_appel_d_avant_sans_deja_garde_le_seuil_de_4_jours(self):
        self.assertEqual([], sortie_auto.a_sortir_compte1(fiche_remise(80), MAINTENANT))
        self.assertEqual(["1"], [u for u, *_ in sortie_auto.a_sortir_compte1(fiche_remise(100), MAINTENANT)])

    def test_texte_de_l_avertissement_dit_l_echeance_le_recours_et_reste_simple(self):
        texte = sortie_auto.texte_avertissement_compte1("Nina", 2)
        for attendu in ("Nina", "48 h", "Gaëtan", "WhatsApp", "manager", "déjà créé"):
            self.assertIn(attendu, texte)
        self.assertNotIn("(", texte)
        self.assertNotIn("—", texte)
        self.assertNotIn("Aucune exclusion", texte)
        for phrase in re.split(r"[.!?:\n]+", re.sub(r"[`*]", "", texte)):
            self.assertLessEqual(len([w for w in phrase.split() if re.search(r"\w", w)]), 10, phrase)
        self.assertIn("\n\n", texte, "une ligne vide entre les paragraphes (lecture sur téléphone)")


class PasseL6Tests(unittest.IsolatedAsyncioTestCase):
    """La passe quotidienne, de bout en bout : avertissement, silence le même jour, puis une ligne « validation manager »."""

    def deps(self, memoire, salon, sortir):
        return {"lire_json": lambda f, d: memoire.get(f, d), "ecrire_json": lambda f, d: memoire.__setitem__(f, d), "FICHIER": "etat",
                "parcours_lire": lambda: memoire["parcours"], "salon_perso": lambda uid: salon, "sortir": sortir,
                "membre_par_id": lambda uid: N(id=int(uid)), "prenom_de": lambda m: "Nina"}

    async def passe(self, memoire, salon, sortir=None, appliquer=True):
        sortir = sortir or AsyncMock()
        with patch.object(sortie_auto, "_deps", self.deps(memoire, salon, sortir)), \
                patch.object(sortie_auto, "compte1_bloque", lambda *a, **k: ""), \
                patch.object(sortie_auto, "compte1_prouve", lambda *a, **k: False), \
                patch.object(sortie_auto, "_visites_actives", lambda uid: False), \
                patch.object(sortie_auto, "ACTIF", True):
            bilan = await sortie_auto.executer(None, appliquer=appliquer)
        return bilan, sortir

    async def test_avertir_puis_attendre_48_h_puis_demander_la_validation_sans_jamais_sortir_seul(self):
        maintenant = datetime.now(timezone.utc)
        memoire = {"parcours": {"1": {"prenom": "Nina", "creatrice": "Chloé", "etape": 1,
                                      "dates": {"1": iso(maintenant - timedelta(hours=100))}}}, "etat": {"sorties": {}}}
        salon = N(send=AsyncMock())
        bilan, sortir = await self.passe(memoire, salon)
        salon.send.assert_awaited_once()
        self.assertIn("48 h", salon.send.await_args.args[0])
        self.assertTrue(any("averti" in ligne for ligne in bilan), bilan)
        self.assertEqual({"1"}, set(memoire["etat"]["avertis_compte1_le"]))
        self.assertFalse(any("validation manager" in ligne for ligne in bilan), "averti dans cette passe : pas de sortie dans la même")

        bilan, _ = await self.passe(memoire, salon)                       # une heure plus tard : rien
        salon.send.assert_awaited_once()
        self.assertEqual([], [l for l in bilan if "Nina" in l and "validation" in l])

        memoire["etat"]["avertis_compte1_le"]["1"] = iso(datetime.now(timezone.utc) - timedelta(hours=49))
        bilan, sortir = await self.passe(memoire, salon)                  # 49 h après l'avertissement
        self.assertTrue(any("validation manager requise" in ligne for ligne in bilan), bilan)
        sortir.assert_not_awaited()
        salon.send.assert_awaited_once()                                  # pas un second avertissement

    async def test_a_blanc_ne_ecrit_rien_et_n_envoie_rien(self):
        maintenant = datetime.now(timezone.utc)
        memoire = {"parcours": {"1": {"prenom": "Nina", "creatrice": "Chloé", "etape": 1,
                                      "dates": {"1": iso(maintenant - timedelta(hours=100))}}}, "etat": {"sorties": {}}}
        salon = N(send=AsyncMock())
        bilan, sortir = await self.passe(memoire, salon, appliquer=False)
        salon.send.assert_not_awaited()
        sortir.assert_not_awaited()
        self.assertNotIn("avertis_compte1_le", memoire["etat"])
        self.assertTrue(any("avertissement L6" in ligne for ligne in bilan), bilan)

    def test_la_garde_du_manager_reste_avant_toute_sortie(self):
        source = (ROOT / "sortie_auto.py").read_text(encoding="utf-8")
        self.assertLess(source.index("if not RETRAIT_AUTOMATIQUE:"), source.index('await _deps["sortir"]'))


# ------------------------------------------------------------------------------------------------ lien créé à l'arrivée
class InterrupteurTests(unittest.TestCase):
    def test_eteint_par_defaut_allume_par_1_seulement(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(VAR_ARRIVEE, None)
            self.assertFalse(parcours.lien_arrivee_actif())
        for valeur, attendu in (("1", True), (" 1 ", True), ("0", False), ("", False), ("oui", False), ("true", False)):
            with patch.dict(os.environ, {VAR_ARRIVEE: valeur}):
                self.assertEqual(attendu, parcours.lien_arrivee_actif(), repr(valeur))


class PreparerLienArriveeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.membre = N(id=1, mention="<@1>", display_name="Nina")

    def crée(self, memoire, appels):
        async def attribuer(membre, raison=""):
            appels.append(raison)
            avec_lien(memoire)
        return AsyncMock(side_effect=attribuer)

    async def test_eteint_rien_n_est_cree(self):
        with monde({"1": clipper()}) as (m, canal):
            os.environ.pop(VAR_ARRIVEE, None)
            parcours._deps["attribuer_lien"] = AsyncMock()
            etat = await parcours.preparer_lien_arrivee(self.membre, "1")
            parcours._deps["attribuer_lien"].assert_not_awaited()
        self.assertEqual("eteint", etat)

    async def test_allume_cree_le_lien_une_fois_et_le_marque(self):
        appels = []
        with monde({"1": clipper()}) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            parcours._deps["attribuer_lien"] = self.crée(m, appels)
            premier = await parcours.preparer_lien_arrivee(self.membre, "1")
            second = await parcours.preparer_lien_arrivee(self.membre, "1")
            fiche = m["p"]["1"]
        self.assertEqual(("cree", "deja"), (premier, second))
        self.assertEqual(1, len(appels))
        self.assertIn("lien créé à l'arrivée", appels[0])
        self.assertTrue(fiche.get("lien_arrivee"))

    async def test_forfait_plein_un_essai_par_jour_ecrit_avant_l_appel(self):
        attribuer = AsyncMock()                                           # ne crée rien : forfait plein
        with monde({"1": clipper()}) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            parcours._deps["attribuer_lien"] = attribuer
            premier = await parcours.preparer_lien_arrivee(self.membre, "1")
            second = await parcours.preparer_lien_arrivee(self.membre, "1")
            fiche = m["p"]["1"]
        self.assertEqual(("sans_lien", "essai_du_jour"), (premier, second))
        attribuer.assert_awaited_once()
        self.assertTrue(fiche.get("lien_arrivee_essai"))
        self.assertFalse(fiche.get("lien_arrivee"), "pas de lien, pas de marque")

    async def test_une_erreur_ne_leve_jamais(self):
        with monde({"1": clipper()}) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            parcours._deps["attribuer_lien"] = AsyncMock(side_effect=RuntimeError("GAML en panne"))
            self.assertEqual("sans_lien", await parcours.preparer_lien_arrivee(self.membre, "1"))

    async def test_sans_fiche_ou_sorti_rien(self):
        with monde({"1": clipper()}, onboarding={"2": {"sorti": True}}) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            parcours._deps["attribuer_lien"] = AsyncMock()
            self.assertEqual("sans_fiche", await parcours.preparer_lien_arrivee(self.membre, "9"))
            m["p"]["2"] = clipper()
            self.assertEqual("sans_fiche", await parcours.preparer_lien_arrivee(self.membre, "2"))
            parcours._deps["attribuer_lien"].assert_not_awaited()

    async def test_le_lien_de_la_cohorte_n_est_pas_recree(self):
        """Sarah (cohorte) : le lien est créé par la consigne en story ; l'arrivée pour tous le trouve prêt et n'y touche pas."""
        with monde({"1": clipper()}, onboarding={"1": {"liens_prets": True}}) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            parcours._deps["attribuer_lien"] = AsyncMock()
            self.assertEqual("deja", await parcours.preparer_lien_arrivee(self.membre, "1"))
            parcours._deps["attribuer_lien"].assert_not_awaited()


class RattrapageHoraireTests(unittest.IsolatedAsyncioTestCase):
    DEPUIS = "2026-10-23T00:00:00+00:00"

    def installer(self, m, appels):
        async def attribuer(membre, raison=""):
            uid = str(membre.id)
            appels.append(uid)
            m["o"]["clippers"].setdefault(uid, {})["liens_prets"] = True
        parcours._deps["attribuer_lien"] = AsyncMock(side_effect=attribuer)
        parcours._deps["membre_par_id"] = lambda uid: N(id=int(uid), mention=f"<@{uid}>", display_name=f"N{uid}")

    def fiches(self, n, **plus):
        return {str(i): clipper(bienvenue_ok="2026-10-25T10:00:00+00:00", **plus) for i in range(1, n + 1)}

    async def test_eteint_rien(self):
        with monde(self.fiches(2), depuis=self.DEPUIS) as (m, canal):
            os.environ.pop(VAR_ARRIVEE, None)
            appels = []
            self.installer(m, appels)
            self.assertEqual([], await parcours.rattraper_liens_arrivee(None))
        self.assertEqual([], appels)

    async def test_cinq_au_plus_par_passe_puis_le_reste_a_la_suivante_puis_silence(self):
        appels = []
        with monde(self.fiches(7), depuis=self.DEPUIS) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            self.installer(m, appels)
            premiere = await parcours.rattraper_liens_arrivee(None)
            seconde = await parcours.rattraper_liens_arrivee(None)
            troisieme = await parcours.rattraper_liens_arrivee(None)
        self.assertEqual((5, 2, 0), (len(premiere), len(seconde), len(troisieme)))
        self.assertEqual(7, len(set(appels)))

    async def test_ceux_d_avant_la_regle_ceux_qui_ont_l_app_et_les_sortis_sont_laisses(self):
        fiches = {"1": clipper(bienvenue_ok="2026-10-10T10:00:00+00:00"),                   # arrivé avant la règle
                  "2": clipper(bienvenue_ok="2026-10-25T10:00:00+00:00", app="2026-10-28"),   # a déjà son app
                  "3": clipper(bienvenue_ok="2026-10-25T10:00:00+00:00"),                   # sorti
                  "4": clipper(bienvenue_ok="n'importe quoi"),                              # date illisible
                  "5": clipper(bienvenue_ok="2026-10-25T10:00:00+00:00")}                   # le seul à traiter
        appels = []
        with monde(fiches, onboarding={"3": {"sorti": True}}, depuis=self.DEPUIS) as (m, canal), \
                patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            self.installer(m, appels)
            faits = await parcours.rattraper_liens_arrivee(None)
        self.assertEqual(["5"], [u for u, _ in faits])
        self.assertEqual(["5"], appels)

    async def test_un_clipper_sorti_de_l_equipe_est_laisse(self):
        appels = []
        with monde(self.fiches(2), depuis=self.DEPUIS) as (m, canal), patch.dict(os.environ, {VAR_ARRIVEE: "1"}):
            self.installer(m, appels)
            parcours._deps["FICHIER_EQUIPES"] = "e"
            m["e"] = {"1": {"creatrice": "Chloé"}}                        # « 2 » n'est plus dans le registre des équipes
            faits = await parcours.rattraper_liens_arrivee(None)
        self.assertEqual(["1"], [u for u, _ in faits])

    def test_la_passe_horaire_et_l_arrivee_sont_branchees(self):
        source = (ROOT / "parcours.py").read_text(encoding="utf-8")
        self.assertIn("await rattraper_liens_arrivee(client)", source)
        i_cohorte = source.index("livrer_story_lien(salon, membre, uid, premiere=True)")
        i_arrivee = source.index("await preparer_lien_arrivee(membre, uid)")
        self.assertLess(i_cohorte, i_arrivee, "la cohorte d'abord : sa consigne crée et dit son lien")


# --------------------------------------------------------------------------------- le lien ne sort pas avant sa remise
class LienRemisTests(unittest.TestCase):
    def test_un_lien_cree_a_l_arrivee_est_cache_jusqu_au_compte_prive(self):
        f = clipper(lien_arrivee="2026-10-25T10:00:00+00:00")
        with monde({"1": f}):
            self.assertFalse(parcours.lien_remis("1"))
            f["etape"] = 2
            self.assertFalse(parcours.lien_remis("1"), "compte 2 : le privé est le compte 3 (ou 2 en ordre prive2, voir ci-dessous)")

    def test_remis_quand_le_compte_prive_est_ouvert(self):
        np_ = parcours.n_prive({})
        f = clipper(lien_arrivee="2026-10-25T10:00:00+00:00", etape=np_, dates={"1": "2026-10-25T10:00:00+00:00", str(np_): "2026-10-27T10:00:00+00:00"})
        with monde({"1": f}):
            self.assertTrue(parcours.lien_remis("1"))
        f2 = clipper(lien_arrivee="2026-10-25T10:00:00+00:00", etape=7)
        with monde({"1": f2}):
            self.assertTrue(parcours.lien_remis("1"))

    def test_remis_quand_la_cohorte_a_recu_sa_consigne(self):
        with monde({"1": clipper(lien_arrivee="2026-10-25T10:00:00+00:00", story_lien_envoye="2026-10-25T11:00:00+00:00")}):
            self.assertTrue(parcours.lien_remis("1"))

    def test_les_anciens_et_les_autres_gardent_le_comportement_d_avant(self):
        with monde({"1": clipper(), "2": clipper(etape=1)}):
            self.assertTrue(parcours.lien_remis("1"))
            self.assertTrue(parcours.lien_remis("inconnu"))

    def test_parcours_non_configure_visible_comme_avant(self):
        ancien = dict(parcours._deps)
        parcours._deps.clear()
        try:
            self.assertTrue(parcours.lien_remis("1"))
        finally:
            parcours._deps.update(ancien)


class MesClicsMasqueTests(unittest.TestCase):
    Q = dict(payes=0, jours=0, hors_robots=0, brut=0, brut_non_lu=0)

    def texte(self):
        d = {"liens": {"a": {"url": LIEN}}, "wallets": {}}
        with patch.object(paie_clics, "liens_de", return_value=["a"]), patch.object(paie_clics, "_aujourdhui", return_value=date(2026, 10, 26)), \
                patch.object(paie_clics, "somme", return_value=self.Q), \
                patch.object(paie_clics, "periode_en_cours", return_value=(date(2026, 10, 20), date(2026, 11, 4))), \
                patch.object(paie_clics, "_debut_paie", return_value=date(2026, 10, 20)), patch.object(paie_clics, "regime", return_value="clic"), \
                patch.object(paie_clics, "non_releves", return_value=[]):
            return paie_clics.texte_mesclics(d, "1", "Nina")

    def test_lien_cree_a_l_arrivee_pas_de_ligne_ton_lien(self):
        with monde({"1": clipper(lien_arrivee="2026-10-25T10:00:00+00:00")}):
            texte = self.texte()
        self.assertNotIn(LIEN, texte)
        self.assertNotIn("Ton lien", texte)
        self.assertIn("Tes visites", texte)
        self.assertEqual(texte, texte.rstrip())

    def test_lien_remis_la_ligne_est_la(self):
        with monde({"1": clipper(lien_arrivee="2026-10-25T10:00:00+00:00", etape=7)}):
            self.assertIn(f"-# Ton lien : {LIEN}", self.texte())

    def test_les_autres_clippers_gardent_la_ligne(self):
        with monde({"1": clipper()}):
            self.assertIn(f"-# Ton lien : {LIEN}", self.texte())

    def test_sans_parcours_configure_la_ligne_reste(self):
        ancien = dict(parcours._deps)
        parcours._deps.clear()
        try:
            self.assertIn(f"-# Ton lien : {LIEN}", self.texte())
        finally:
            parcours._deps.update(ancien)


class ContexteAssistantTests(unittest.TestCase):
    def test_le_contexte_de_l_assistant_ne_dit_pas_un_lien_pas_encore_remis(self):
        source = (ROOT / "parcours.py").read_text(encoding="utf-8")
        self.assertIn('if onb.get("lien") and lien_remis(uid):', source)


# ------------------------------------------------------------------------------------------------------- !app au jour 3
class CommandeAppJour3Tests(unittest.IsolatedAsyncioTestCase):
    def message(self):
        salon = N(id=7)
        return N(author=N(id=1, display_name="Nina"), channel=salon, reply=AsyncMock()), salon

    async def lancer(self, fiche, onboarding, livrer=None):
        message, salon = self.message()
        livrer = livrer or AsyncMock(return_value="envoye")
        with monde({"1": fiche}, onboarding=onboarding, depuis="2000-01-01T00:00:00+00:00"), patch.object(parcours, "livrer_app", livrer):
            parcours._deps["salon_perso"] = lambda uid: salon
            await parcours.commande_app(message)
        return message, livrer

    async def test_jour_3_avec_lien_pret_l_app_part_sans_les_3_comptes(self):
        arrivee = iso(datetime.now(timezone.utc) - timedelta(days=4))
        message, livrer = await self.lancer(clipper(bienvenue_ok=arrivee), {"1": {"liens_prets": True}})
        livrer.assert_awaited_once()
        message.reply.assert_not_awaited()

    async def test_avant_le_jour_3_message_court_et_pas_d_app(self):
        arrivee = iso(datetime.now(timezone.utc) - timedelta(days=1))
        message, livrer = await self.lancer(clipper(bienvenue_ok=arrivee), {"1": {"liens_prets": True}})
        livrer.assert_not_awaited()
        texte = message.reply.await_args.args[0]
        self.assertIn("jour 3", texte)
        self.assertIn("ton lien est prêt", texte)

    async def test_jour_3_sans_lien_pret_l_app_attend(self):
        arrivee = iso(datetime.now(timezone.utc) - timedelta(days=5))
        message, livrer = await self.lancer(clipper(bienvenue_ok=arrivee), {"1": {"liens_prets": False}})
        livrer.assert_not_awaited()

    def test_texte_d_attente_en_francais_simple(self):
        source = (ROOT / "parcours.py").read_text(encoding="utf-8")
        ligne = re.search(r'await message\.reply\("(Ton app arrive à partir du jour 3[^"]*)"\)', source).group(1).replace("\\n", "\n")
        self.assertNotIn("(", ligne)
        self.assertNotIn("—", ligne)
        for phrase in re.split(r"[.!?\n]+", ligne):
            self.assertLessEqual(len([w for w in phrase.split() if re.search(r"\w", w)]), 10, phrase)


if __name__ == "__main__":
    unittest.main()
