"""23/10 (Gaëtan : « Mise à jour BOT Gaëtan et Assistant IA », logs du 18 au 22/10) : panne de la clé Google dite clairement,
rapport sans faux zéro, alertes « code pas reçu » groupées, tickets de support regroupés et nommés, relance d'attente, accusés
dans #assistant-ia, salutation et renvoi de fiche retirés, « !étape » compris, profil connu de l'assistant, lien de TL orphelin."""
import ast
import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace as N
import unicodedata
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def normaliser(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn").strip()


def extraire(noms, namespace, fichier="bot_discord.py"):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms)
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in noms for t in n.targets))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=corps, type_ignores=[])), fichier, "exec"), namespace)
    return namespace


BOT = extraire({"texte_panne_google", "MOTIFS_SUPPORT", "motif_probable", "MOTS_ACCUSE", "accuse_reel", "_RELANCE",
                "est_relance_attente", "_SALUTATION", "retirer_salutation", "_RENVOI_FICHE", "retirer_renvoi_fiche",
                "normaliser_commande", "texte_notification_support", "reponse_escalade_verifiee", "signaler_escalade"},
               {"re": re, "normaliser": normaliser, "unicodedata": unicodedata})


class PanneGoogleTests(unittest.TestCase):
    def test_etat_et_texte(self):
        import google_api
        ancien = dict(google_api._PANNE_AUTH)
        try:
            google_api._PANNE_AUTH.update(depuis=None, detail="")
            self.assertEqual(google_api.panne_auth(), {})
            self.assertEqual(google_api.raison_panne(), "")
            google_api._PANNE_AUTH.update(depuis=time.time() - 3 * 3600 - 120, detail="Invalid JWT Signature.")
            self.assertTrue(google_api.panne_auth())
            self.assertEqual(google_api.raison_panne(), "clé Google refusée")
            texte = BOT["texte_panne_google"](google_api.panne_auth(), time.time(), "bot@projet.iam.gserviceaccount.com")
        finally:
            google_api._PANNE_AUTH.clear()
            google_api._PANNE_AUTH.update(ancien)
        self.assertIn("depuis 3 h 02", texte)
        self.assertIn("GOOGLE_SERVICE_ACCOUNT_JSON", texte)
        self.assertIn("bot@projet.iam.gserviceaccount.com", texte)
        self.assertIn("comptes à remettre", texte)


class RapportTests(unittest.TestCase):
    def test_reels_non_lus_jamais_zero(self):
        import rapport_quotidien as r
        texte = r.composer(date(2026, 10, 21), {"erreur": "clé Google refusée"},
                           {"par": {"Sarah": {"hier": 309, "j7": 2000}}, "clippers": [("Yves", 282)]},
                           {"par": {}, "clippers": {}, "silencieux": [], "publie": 0, "erreur": "clé Google refusée"},
                           {}, 27, ["Sarah"])
        self.assertIn("Reels : classeur non lu (clé Google refusée)", texte)
        self.assertNotIn("0 Reels", texte)
        self.assertIn("Data G&M non lu (clé Google refusée)", texte)
        self.assertNotIn("DATA_GM_ID", texte)


class CodeAbsentTests(unittest.IsolatedAsyncioTestCase):
    async def test_serie_comptee_puis_rappel(self):
        import codes_2fa
        envoyes = []

        async def faux_admin(texte):
            envoyes.append(texte)
            return True
        etat = {"faits": {}, "sante": {}, "codes": []}
        anciens = codes_2fa._admin, codes_2fa._etat, dict(codes_2fa._ABSENTS)
        codes_2fa._admin, codes_2fa._etat = faux_admin, lambda: etat
        codes_2fa._ABSENTS.clear()
        try:
            for _ in range(4):
                codes_2fa._signaler_code_absent("u|55", {"a@icloud.com"}, "auto")
            await asyncio.sleep(0)
            self.assertEqual(len(envoyes), 1)                       # quatre demandes, une seule alerte
            vieux = datetime.now(timezone.utc) - timedelta(minutes=codes_2fa.ABSENT_RAPPEL_MIN + 1)
            etat["sante"]["absent|55"] = codes_2fa._iso(vieux)
            codes_2fa._signaler_code_absent("u|55", {"a@icloud.com"}, "auto")
            await asyncio.sleep(0)
            self.assertEqual(len(envoyes), 2)
            self.assertIn("5ᵉ demande sans code", envoyes[1])
            codes_2fa._noter_montre("u|55", [{"mid": "x"}])            # un code montré efface la série
            self.assertNotIn("55", codes_2fa._ABSENTS)
        finally:
            codes_2fa._admin, codes_2fa._etat = anciens[0], anciens[1]
            codes_2fa._ABSENTS.clear()
            codes_2fa._ABSENTS.update(anciens[2])

    def test_cause_cle_google(self):
        import codes_2fa
        t = codes_2fa.texte_code_absent("1", {"x@icloud.com"}, "auto", False, cle_google=True)
        self.assertIn("clé Google est refusée", t)
        self.assertIn("1 adresse rattachée", t)


class SupportTests(unittest.IsolatedAsyncioTestCase):
    def test_ticket_recent(self):
        import support_suivi
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "support.sqlite"

            async def notifier(_ticket):
                return 1
            asyncio.run(support_suivi.signaler(chemin, "7", "assistance IA · compte verrouillé ou mot de passe · abc", 1, 2, 3, 0, notifier))
            self.assertEqual(support_suivi.ticket_recent(chemin, "7", "assistance IA", 6),
                             "assistance IA · compte verrouillé ou mot de passe · abc")
            self.assertIsNone(support_suivi.ticket_recent(chemin, "8", "assistance IA", 6))
            self.assertIsNone(support_suivi.ticket_recent(chemin, "7", "demande", 6))

    def test_motifs(self):
        f = BOT["motif_probable"]
        self.assertEqual(f("Mon compte 2 est verrouillé et je dois changer de mot de passe"), "compte verrouillé ou mot de passe")
        self.assertEqual(f("Mon compte 2 est ban"), "compte banni ou suspendu")
        self.assertEqual(f("J'ai déjà posté 5 reels sur mon compte № 1 Mais j'ai pas encore les coordonnées du compte № 2"),
                         "compte suivant ou identifiants")
        self.assertEqual(f(""), "capture")
        self.assertEqual(f("Je sais pas quoi faire"), "question")

    def test_notification_dit_le_motif(self):
        t = BOT["texte_notification_support"](9, "1", "assistance IA · compte verrouillé ou mot de passe · abc", "https://x")
        self.assertIn("(compte verrouillé ou mot de passe)", t)
        ancien = BOT["texte_notification_support"](9, "1", "assistance IA · question 4c1e03624c5a62b0", "https://x")
        self.assertNotIn("(", ancien.split(".")[0].split(":", 1)[1])

    async def test_demande_suivante_regroupee(self):
        signal = AsyncMock(return_value={"statut": "transmis", "nouveau": False})
        ns = dict(BOT, signaler_support=signal, ticket_ia_recent=lambda uid: "assistance IA · code Instagram · abc")
        exec("pass", ns)
        f = extraire({"signaler_escalade"}, ns)["signaler_escalade"]
        self.assertEqual(await f(N(author=N(id=1), id=2), ""), "groupe")
        self.assertEqual(signal.call_args.args[1], "assistance IA · code Instagram · abc")
        g = extraire({"reponse_escalade_verifiee"}, {"signaler_escalade": AsyncMock(return_value="groupe")})["reponse_escalade_verifiee"]
        texte = await g(N(), "")
        self.assertIn("ajouté à ta demande en cours", texte)
        self.assertIn("est signalée", texte)


class AssistantTests(unittest.TestCase):
    def test_relance_attente(self):
        f = BOT["est_relance_attente"]
        for t in ("Rien jusqu'à présent", "toujours rien", "J'attends ?", "des nouvelles ?", "Rien"):
            self.assertTrue(f(t), t)
        for t in ("Rien ne marche quand je crée le compte 2", "J'ai déjà posté 5 reels", ""):
            self.assertFalse(f(t), t)

    def test_accuse_dans_assistant(self):
        self.assertTrue(BOT["accuse_reel"]("D'accord"))
        self.assertTrue(BOT["accuse_reel"]("ok merci"))
        self.assertFalse(BOT["accuse_reel"]("Bonjour"))

    def test_salutation_retiree(self):
        f = BOT["retirer_salutation"]
        self.assertEqual(f("Salut Jamel ! 👋\n\nTu veux dire par où commencer ?"), "Tu veux dire par où commencer ?")
        self.assertEqual(f("Salut Jamel tu dois créer ton compte"), "Salut Jamel tu dois créer ton compte")
        self.assertEqual(f("Salut !"), "Salut !")

    def test_renvoi_fiche_retire(self):
        f = BOT["retirer_renvoi_fiche"]
        r = "Choisis celle qui te plaît.\n\nLes détails sont dans Fiche 1 (⁠🎓formation)"
        self.assertEqual(f(r, "une bio pour Sophie"), "Choisis celle qui te plaît.")
        self.assertEqual(f(r, "où est la fiche du compte ?"), r)

    def test_commande_accentuee(self):
        f = BOT["normaliser_commande"]
        self.assertEqual(f("!Étape 2"), "!etape 2")
        self.assertEqual(f("! pseudo 1 Sarah.Clic"), "!pseudo 1 Sarah.Clic")

    def test_regles_du_prompt(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        for morceau in ("41. Tu réponds ICI", "42. Pas de « Salut <prénom> ! 👋 »", "43. La bio", "44. Après une transmission"):
            self.assertIn(morceau, src)


class ProfilTests(unittest.TestCase):
    def test_ligne_profil(self):
        import parcours
        ouverte = "2026-10-20T08:00:00+00:00"
        self.assertIn("PAS ENCORE PARTI", parcours.ligne_profil({"etape": 1, "dates": {"1": ouverte}}))
        self.assertIn("✅ Compte 1 créé", parcours.ligne_profil({"etape": 1, "dates": {"1": ouverte}}))
        self.assertIn("PARTI, dans le message « Ton profil du compte 2 »",
                      parcours.ligne_profil({"etape": 2, "dates": {"2": ouverte}, "profils": {"2": ouverte}}))
        self.assertEqual(parcours.ligne_profil({"etape": 1, "dates": {"1": "2026-09-01T08:00:00+00:00"}}), "")
        self.assertEqual(parcours.ligne_profil({"etape": 0}), "")


class LienOrphelinTests(unittest.TestCase):
    def test_lien_du_tl_rattache_ailleurs(self):
        import equipes_tl
        d = {"liens": {"L1": {"uid": "999", "note": "Clipping Yves", "slug": "creatricefr:1"},
                       "L2": {"uid": "42", "note": "Clipping Yves"},
                       "L3": {"uid": "", "note": "Clipping Josué"}},
             "jours": {"L1": {"2026-10-20": {"payes": 499}, "2026-10-21": {"payes": 282}},
                       "L2": {"2026-10-20": {"payes": 5}}}}
        out = equipes_tl.liens_orphelins(d, "42", "Yves - Sarah - TL Sarah", date(2026, 10, 20), date(2026, 11, 4))
        self.assertEqual(out, [("creatricefr:1", 781)])
        self.assertEqual(equipes_tl.liens_orphelins(d, "77", "Josué", date(2026, 10, 20), date(2026, 11, 4)), [])   # sans visites
        self.assertEqual(equipes_tl.liens_orphelins(d, "42", "id …0042", date(2026, 10, 20), date(2026, 11, 4)), [])


if __name__ == "__main__":
    unittest.main()
