"""Débrief du 23/10 (Gaëtan) : lien en story dès le compte 1 (cohorte d'essai), app au jour 3 avec le duplicateur de Reels, Gaëtan TL par
défaut, phrases qui contredisent la règle C10, compte banni. Cas fictifs, sans réseau ni Discord."""
import ast
import os
import re
import sys
import unicodedata
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codes_2fa  # noqa: E402
import equipes_tl  # noqa: E402
import parcours  # noqa: E402

VAR = "LIEN_STORY_COMPTE1_CREATRICES"
LIEN = "https://gaml.exemple/fictif"


def normaliser(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn").lower()


@contextmanager
def monde(fiches, onboarding=None, cohorte=None, depuis=None):
    """Un parcours et un onboarding en mémoire. `cohorte` : valeur de LIEN_STORY_COMPTE1_CREATRICES (None = variable absente)."""
    memoire = {"p": fiches, "o": {"clippers": onboarding if onboarding is not None else {}}}
    canal = N(send=AsyncMock())
    ancien = dict(parcours._deps)
    parcours._deps.update({"lire_json": lambda f, d: memoire.get(f, d), "ecrire_json": lambda f, d: memoire.__setitem__(f, d),
                           "FICHIER_PARCOURS": "p", "FICHIER_ONBOARDING": "o", "normaliser": normaliser,
                           "canal_admin": AsyncMock(return_value=canal)})
    parcours._deps.pop("attribuer_lien", None)
    env = {VAR: cohorte} if cohorte is not None else {}
    try:
        with patch.dict(os.environ, env):
            if cohorte is None:
                os.environ.pop(VAR, None)
            reglages = [patch.object(parcours, "APP_JOUR_DEPUIS", depuis)] if depuis else []
            for r in reglages:
                r.start()
            try:
                yield memoire, canal
            finally:
                for r in reglages:
                    r.stop()
    finally:
        parcours._deps.clear()
        parcours._deps.update(ancien)


def clipper(**plus):
    return {"prenom": "Nina", "creatrice": "Chloé", "etape": 1, "dates": {"1": "2026-10-24T09:00:00+00:00"},
            "bienvenue_ok": "2026-10-24T09:00:00+00:00", **plus}


def avec_lien(memoire, uid="1"):
    """Simule l'attribution du lien GAML : `liens_prets` et le lien lisible."""
    memoire["o"]["clippers"].setdefault(uid, {})["liens_prets"] = True


def liens_gaml(memoire, uid="1"):
    def f(_uid, _creatrice):
        if memoire["o"]["clippers"].get(uid, {}).get("liens_prets"):
            return LIEN, [LIEN]
        return "", []
    return f


class LienEnStoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.membre = N(mention="<@1>", display_name="Nina - Chloé")
        self.salon = N(send=AsyncMock(), guild=None)

    async def test_eteint_par_defaut(self):
        with monde({"1": clipper()}) as (m, canal):
            attribuer = AsyncMock()
            parcours._deps["attribuer_lien"] = attribuer
            etat = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
        self.assertEqual("hors_cohorte", etat)
        self.salon.send.assert_not_awaited()
        attribuer.assert_not_awaited()
        self.assertNotIn("cohorte_story_lien", m["p"]["1"])
        with monde({}):
            self.assertEqual(set(), parcours.creatrices_cohorte_story())

    async def test_variable_vide_ou_espaces_reste_eteinte(self):
        for valeur in ("", "  ", " , "):
            with monde({"1": clipper()}, cohorte=valeur):
                self.assertEqual(set(), parcours.creatrices_cohorte_story())

    async def test_entre_a_l_arrivee_cree_le_lien_et_l_envoie_une_fois(self):
        with monde({"1": clipper()}, cohorte="Chloé") as (m, canal):
            async def attribuer(membre, raison=""):
                avec_lien(m)
            attribuer_mock = AsyncMock(side_effect=attribuer)
            parcours._deps["attribuer_lien"] = attribuer_mock
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                premier = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
                second = await parcours.livrer_story_lien(self.salon, self.membre, "1")
            fiche = m["p"]["1"]
        self.assertEqual(("envoye", "deja"), (premier, second))
        self.salon.send.assert_awaited_once()
        texte = self.salon.send.await_args.args[0]
        self.assertIn(LIEN, texte)
        self.assertIn("tous les 2 jours", texte)
        self.assertIn("Ne le mets jamais à la une.", texte)
        self.assertIn("Ne le mets jamais dans ta bio.", texte)
        self.assertTrue(fiche["cohorte_story_lien"] and fiche["story_lien_envoye"])
        attribuer_mock.assert_awaited_once()
        self.assertIn("cohorte du lien en story", attribuer_mock.await_args.kwargs["raison"])

    async def test_lien_deja_pret_n_en_cree_pas_un_autre(self):
        with monde({"1": clipper()}, onboarding={"1": {"liens_prets": True}}, cohorte="chloe") as (m, canal):
            attribuer = AsyncMock()
            parcours._deps["attribuer_lien"] = attribuer
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                etat = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
            attribuer.assert_not_awaited()
        self.assertEqual("envoye", etat)

    async def test_autre_creatrice_reste_hors_cohorte(self):
        with monde({"1": clipper(creatrice="Sophie")}, cohorte="Chloé") as (m, canal):
            etat = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
        self.assertEqual("hors_cohorte", etat)
        self.salon.send.assert_not_awaited()

    async def test_un_ancien_clipper_n_entre_jamais_apres_coup(self):
        with monde({"1": clipper()}, cohorte="Chloé") as (m, canal):
            etat = await parcours.livrer_story_lien(self.salon, self.membre, "1")        # ni arrivée ni cohorte : rattrapage
            self.assertNotIn("cohorte_story_lien", m["p"]["1"])
        self.assertEqual("hors_cohorte", etat)
        self.salon.send.assert_not_awaited()

    async def test_sans_lien_une_seule_ligne_admin_et_un_seul_essai_par_jour(self):
        with monde({"1": clipper()}, cohorte="Chloé") as (m, canal):
            attribuer = AsyncMock()                                                        # forfait plein : rien n'est créé
            parcours._deps["attribuer_lien"] = attribuer
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                a = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
                b = await parcours.livrer_story_lien(self.salon, self.membre, "1")
                c = await parcours.livrer_story_lien(self.salon, self.membre, "1")
        self.assertEqual(["sans_lien"] * 3, [a, b, c])
        self.salon.send.assert_not_awaited()
        attribuer.assert_awaited_once()
        canal.send.assert_awaited_once()
        self.assertIn("Chloé", canal.send.await_args.args[0])
        self.assertIn("son parcours continue", canal.send.await_args.args[0])

    async def test_trop_tard_quand_le_compte_prive_est_ouvert(self):
        fiche = clipper(etape=6, cohorte_story_lien="2026-10-24T09:00:00+00:00")
        with monde({"1": fiche}, onboarding={"1": {"liens_prets": True}}, cohorte="Chloé") as (m, canal):
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                etat = await parcours.livrer_story_lien(self.salon, self.membre, "1")
        self.assertEqual("trop_tard", etat)
        self.salon.send.assert_not_awaited()

    async def test_clipper_sorti_ne_recoit_rien(self):
        with monde({"1": clipper()}, onboarding={"1": {"liens_prets": True, "sorti": True}}, cohorte="Chloé"):
            etat = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
        self.assertEqual("hors_cohorte", etat)

    async def test_envoi_refuse_par_discord_reessaie_plus_tard(self):
        import discord
        self.salon.send = AsyncMock(side_effect=discord.HTTPException(N(status=500, reason="x"), "x"))
        with monde({"1": clipper()}, onboarding={"1": {"liens_prets": True}}, cohorte="Chloé") as (m, canal):
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                etat = await parcours.livrer_story_lien(self.salon, self.membre, "1", premiere=True)
            self.assertNotIn("story_lien_envoye", m["p"]["1"])
        self.assertEqual("erreur", etat)

    async def test_rattrapage_horaire_envoie_des_que_le_lien_existe_puis_se_tait(self):
        client = N(get_channel=lambda _id: self.salon)
        with monde({"1": clipper(salon_id=5, cohorte_story_lien="2026-10-24T09:00:00+00:00")}, cohorte="Chloé") as (m, canal):
            parcours._deps["membre_par_id"] = lambda uid: self.membre
            parcours._deps["attribuer_lien"] = AsyncMock()
            with patch.object(parcours, "_liens_gaml", liens_gaml(m)):
                avant = await parcours.rattraper_story_lien(client)
                avec_lien(m)
                pendant = await parcours.rattraper_story_lien(client)
                apres = await parcours.rattraper_story_lien(client)
        self.assertEqual([("1", "sans_lien")], avant)
        self.assertEqual([("1", "envoye")], pendant)
        self.assertEqual([], apres)
        self.salon.send.assert_awaited_once()

    async def test_rattrapage_eteint_sans_variable(self):
        with monde({"1": clipper(salon_id=5, cohorte_story_lien="2026-10-24T09:00:00+00:00")}):
            self.assertEqual([], await parcours.rattraper_story_lien(N(get_channel=lambda _id: self.salon)))

    async def test_fin_des_stories_avec_le_lien_au_profil_du_prive_pour_la_cohorte_seulement(self):
        ctx = {"pointent_tes": "tes 2 comptes", "cprive": "prive_fictif", "pointent_court": "tes comptes"}
        for cohorte, attendu in ((True, True), (False, False)):
            salon = N(send=AsyncMock(), guild=None)
            fiche = clipper(etape=6)
            if cohorte:
                fiche["cohorte_story_lien"] = "2026-10-24T09:00:00+00:00"
            with monde({"1": fiche}, onboarding={"1": {"lien": LIEN}}) as (m, canal):
                with patch.object(parcours, "_contexte", AsyncMock(return_value=ctx)), \
                        patch.object(parcours, "envoyer_etape", AsyncMock()), patch.object(parcours, "_poser_story", lambda *a, **k: None):
                    await parcours._story_puis_app(salon, self.membre, "1")
            envoye = salon.send.await_args.args[0]
            self.assertEqual(attendu, parcours.STORY_LIEN_FIN in envoye)
            self.assertIn("@prive_fictif", envoye)
        self.assertEqual("Plus aucune story avec le lien. Seulement des stories qui mentionnent le compte privé.", parcours.STORY_LIEN_FIN)

    def test_message_en_francais_simple(self):
        """Phrases de 10 mots au plus, sans parenthèse ni tiret long : les textes ajoutés le 23/10 seulement."""
        ajoutes_app = [l for l in parcours.TEXTE_APP.split("\n") if "duplicateur" in l or "rush" in l]
        ajoutes_ligne = [l for l in parcours.LIGNE_APP.split("\n") if "duplicateur" in l]
        self.assertTrue(ajoutes_app and ajoutes_ligne)
        for texte in (parcours.STORY_LIEN_COMPTE1, parcours.STORY_LIEN_FIN, parcours.TEXTE_GROUPE_GAETAN, *ajoutes_app, *ajoutes_ligne):
            propre = re.sub(r"\{[^}]*\}", "", re.sub(r"```.*?```", "", texte, flags=re.S))
            self.assertNotIn("—", propre)
            self.assertNotIn("(", propre)
            for phrase in re.split(r"[.!?\n]+", re.sub(r"[`*]|\d\.", "", propre)):
                self.assertLessEqual(len([w for w in phrase.split() if re.search(r"\w", w)]), 10, phrase)


class EnvoyerEtapeCompte1Tests(unittest.IsolatedAsyncioTestCase):
    def test_le_lien_en_story_part_apres_le_compte_1_et_une_seule_fois(self):
        """Le message du compte 1 n'est pas modifié ; la consigne part seulement à la première livraison de l'étape 1."""
        source = (ROOT / "parcours.py").read_text(encoding="utf-8")
        self.assertIn('if n == 1 and pointer and not (fiche_avant.get("messages") or {}).get("1"):', source)
        self.assertIn("livrer_story_lien(salon, membre, uid, premiere=True)", source)


class AppJour3Tests(unittest.IsolatedAsyncioTestCase):
    ARRIVEE = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)

    def fiche(self, **plus):
        return clipper(bienvenue_ok=self.ARRIVEE.isoformat(), **plus)

    def test_jour_3_avec_lien_pret(self):
        with monde({}, onboarding={"1": {"liens_prets": True}}):
            f = self.fiche()
            self.assertFalse(parcours.jour_app_atteint(f, "1", self.ARRIVEE + timedelta(days=2, hours=23)))
            self.assertTrue(parcours.jour_app_atteint(f, "1", self.ARRIVEE + timedelta(days=3)))

    def test_sans_lien_pret_l_app_n_est_jamais_due_au_jour_3(self):
        with monde({}, onboarding={"1": {"liens_prets": False}}):
            self.assertFalse(parcours.jour_app_atteint(self.fiche(), "1", self.ARRIVEE + timedelta(days=30)))

    def test_les_clippers_deja_en_route_ne_sont_pas_touches(self):
        ancien = clipper(bienvenue_ok="2026-10-10T10:00:00+00:00")
        with monde({}, onboarding={"1": {"liens_prets": True}}):
            self.assertFalse(parcours.jour_app_atteint(ancien, "1", self.ARRIVEE + timedelta(days=30)))

    def test_app_jour_zero_rend_l_ancienne_regle(self):
        with monde({}, onboarding={"1": {"liens_prets": True}}), patch.object(parcours, "APP_JOUR", 0):
            self.assertFalse(parcours.jour_app_atteint(self.fiche(), "1", self.ARRIVEE + timedelta(days=30)))

    def test_date_illisible_ne_leve_rien(self):
        with monde({}, onboarding={"1": {"liens_prets": True}}):
            self.assertFalse(parcours.jour_app_atteint({"bienvenue_ok": "n'importe quoi"}, "1"))
            self.assertFalse(parcours.jour_app_atteint({}, "1"))

    def test_app_due_sans_uid_garde_l_ancienne_regle(self):
        with monde({}, onboarding={"1": {"liens_prets": True}}), patch.object(parcours, "APP_JOUR_DEPUIS", "2000-01-01T00:00:00+00:00"):
            vieux = clipper(bienvenue_ok=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat())
            self.assertFalse(parcours.app_due(vieux))                     # étape 1 : pas 3 comptes
            self.assertTrue(parcours.app_due(vieux, "1"))                 # jour 3 passé, lien prêt

    async def test_livrer_app_au_jour_3_une_seule_fois(self):
        depuis = "2000-01-01T00:00:00+00:00"
        vieux = clipper(bienvenue_ok=(datetime.now(timezone.utc) - timedelta(days=4)).isoformat(), salon_id=7)
        salon = N(send=AsyncMock(return_value=N(id=99)))
        membre = N(mention="<@1>", display_name="Nina - Chloé")
        with monde({"1": vieux}, onboarding={"1": {"liens_prets": True}}, depuis=depuis) as (m, canal), \
                patch.object(parcours, "_liens_gaml", lambda uid, c: (LIEN, [LIEN])), \
                patch.object(parcours.lien_app, "lien", AsyncMock(return_value="https://app.exemple/fictif")):
            premier = await parcours.livrer_app("1", salon=salon, membre=membre)
            second = await parcours.livrer_app("1", salon=salon, membre=membre)
        self.assertEqual(("envoye", "deja"), (premier, second))
        salon.send.assert_awaited_once()
        texte = salon.send.await_args.args[0]
        self.assertIn("duplicateur de Reels", texte)
        self.assertIn("rushes bruts", texte)

    async def test_livrer_app_avant_le_jour_3_reste_en_attente(self):
        recent = clipper(bienvenue_ok=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), salon_id=7)
        salon = N(send=AsyncMock())
        with monde({"1": recent}, onboarding={"1": {"liens_prets": True}}, depuis="2000-01-01T00:00:00+00:00"):
            etat = await parcours.livrer_app("1", salon=salon, membre=N(mention="<@1>", display_name="Nina"))
        self.assertEqual("pas_pret", etat)
        salon.send.assert_not_awaited()

    def test_textes_de_l_app_parlent_du_duplicateur_et_des_rushes_bruts(self):
        self.assertIn("duplicateur de Reels", parcours.TEXTE_APP)
        self.assertIn("rushes bruts", parcours.TEXTE_APP)
        self.assertIn("rushes bruts", parcours.LIGNE_APP)
        self.assertIn("duplicateur de Reels", parcours.LIGNE_APP)


class GaetanTlParDefautTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.membre = N(mention="<@1>", display_name="Nina - Clara")
        self.salon = N(send=AsyncMock())

    async def test_message_unique_avec_les_deux_boutons(self):
        with monde({"1": clipper(creatrice="Clara")}) as (m, canal):
            premier = await parcours.demander_groupe_gaetan(self.salon, self.membre, "1", "Nina", "Clara")
            second = await parcours.demander_groupe_gaetan(self.salon, self.membre, "1", "Nina", "Clara")
            fiche = m["p"]["1"]
        self.assertEqual((True, False), (premier, second))
        self.salon.send.assert_awaited_once()
        self.assertIn("écris à Gaëtan", self.salon.send.await_args.args[0])
        self.assertIn("J'ai écrit à Gaëtan", self.salon.send.await_args.args[0])
        self.assertTrue(fiche["groupe_gaetan_demande"])
        labels = [getattr(b, "label", "") or getattr(getattr(b, "item", None), "label", "") for b in self.salon.send.await_args.kwargs["view"].children]
        self.assertTrue(any("J'ai écrit à Gaëtan" in l for l in labels), labels)

    async def test_deja_ecrit_a_gaetan_rien_a_redemander(self):
        with monde({"1": clipper(creatrice="Clara", whatsapp="2026-10-24T11:00:00+00:00")}):
            self.assertFalse(await parcours.demander_groupe_gaetan(self.salon, self.membre, "1", "Nina", "Clara"))
        self.salon.send.assert_not_awaited()

    async def test_jamais_d_exception_sans_fiche(self):
        with monde({}):
            self.assertFalse(await parcours.demander_groupe_gaetan(self.salon, self.membre, "9", "Nina", "Clara"))
        self.salon.send.assert_not_awaited()

    def test_equipe_sans_tl_aucune_prime_tl(self):
        calcul = {"equipes": {"Clara": {"tl": None, "manager": "42", "vas": [], "total": 3200, "projete": 3200}}}
        lignes = equipes_tl.lignes_primes(calcul)
        self.assertEqual([("42", 0.0, lignes[0][2], False)], lignes)
        self.assertIn("pas de TL", lignes[0][2])
        self.assertNotIn("+ ", lignes[0][2].replace("0 $", ""))

    def test_l_arrivee_sans_tl_appelle_le_chemin_de_gaetan(self):
        source = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("pas de TL pour {creatrice_c} : Gaëtan est TL par défaut", source)
        self.assertIn("parcours.demander_groupe_gaetan(salon_c, m_, uid_m, prenom_c, creatrice_c)", source)


class PhrasesContradictoiresTests(unittest.TestCase):
    CONTRADICTION = "pour éviter une suspension"

    def test_aide_creation_ne_dit_plus_de_ne_pas_creer_son_compte(self):
        with patch.object(codes_2fa, "texte_salon_codes", lambda: "va dans le salon des codes."):
            texte = codes_2fa.aide_instagram("creation")
        self.assertNotIn(self.CONTRADICTION, texte)
        self.assertNotIn("Ne crée pas de compte", texte)
        self.assertIn("ne crée pas de compte de remplacement : fais appel (Fiche 6)", texte)
        self.assertIn("Les comptes de ton parcours se créent normalement", texte)

    def test_regle_23_de_l_assistant(self):
        source = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertNotIn("pas de création de remplacement pour éviter une suspension", source)
        self.assertIn("pas de compte de remplacement inventé après une suspension", source)
        self.assertIn("tu ne dis jamais « ne crée pas", source)


def extraire_bot(noms_fonctions, noms_valeurs):
    arbre = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
    corps = []
    for n in arbre.body:
        if isinstance(n, ast.FunctionDef) and n.name in noms_fonctions:
            corps.append(n)
        elif isinstance(n, ast.Assign) and any(getattr(t, "id", "") in noms_valeurs for t in n.targets):
            corps.append(n)
    ns = {"re": re, "normaliser": normaliser}
    exec(compile(ast.Module(body=corps, type_ignores=[]), "bot-fictif", "exec"), ns)
    return ns


class CompteBanniTests(unittest.TestCase):
    CONFIRMATION = "Ta demande est signalée à l’équipe."

    def ns(self):
        return extraire_bot({"avec_procedure_compte_banni"}, {"MOTIF_COMPTE_BANNI", "PROCEDURE_COMPTE_BANNI"})

    def test_cas_yves_la_procedure_passe_avant_l_escalade(self):
        f = self.ns()["avec_procedure_compte_banni"]
        for question in ("mon compte 2 est ban", "Mon compte a été banni", "ma page est suspendue", "mon compte est bloqué",
                         "Instagram a désactivé mon compte", "j’ai reçu « nous examinons votre compte »"):
            texte = f(question, self.CONFIRMATION)
            self.assertTrue(texte.endswith(self.CONFIRMATION), question)
            avant = texte[:texte.index(self.CONFIRMATION)]
            for morceau in ("Contester la décision", "capture", "salon perso", "Gaëtan décide", "Ne réutilise rien"):
                self.assertIn(morceau, avant, question)
            self.assertLess(texte.index("Contester la décision"), texte.index("signalée"))

    def test_autres_questions_gardent_la_confirmation_seule(self):
        f = self.ns()["avec_procedure_compte_banni"]
        for question in ("comment je poste un Reel ?", "je suis bloqué à l'étape 2", "je ne trouve pas mon lien", "banque de vidéos ?", ""):
            self.assertEqual(self.CONFIRMATION, f(question, self.CONFIRMATION), question)
        self.assertEqual(self.CONFIRMATION, f(None, self.CONFIRMATION))

    def test_procedure_courte_sans_promesse_ni_piege(self):
        procedure = self.ns()["PROCEDURE_COMPTE_BANNI"]
        self.assertNotIn("—", procedure)
        self.assertNotIn("garanti", procedure.lower())
        self.assertIn("Jamais ceux d'un autre", procedure)
        self.assertIn("Ne les envoie jamais dans Discord", procedure)
        for phrase in re.split(r"[.!?\n]+", re.sub(r"[«»]|\d\.", "", procedure)):
            self.assertLessEqual(len(phrase.split()), 10, phrase)

    def test_le_point_d_appel_envoie_la_procedure_apres_la_verification(self):
        source = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("avec_procedure_compte_banni(texte, await reponse_escalade_verifiee(message, texte))", source)
        self.assertIn("la marche à suivre de la Fiche 6 AVANT la confirmation de l'équipe", source)


if __name__ == "__main__":
    unittest.main()
