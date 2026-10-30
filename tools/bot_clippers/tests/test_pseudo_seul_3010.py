"""30/10 (Gaëtan : « On va juste donner les arobas dans le bot pour tous les nouveaux clippers » ; Loom du 30/10 : « Le bot va te
donner un arobase Instagram… tu mets ton mail, tu mets mot de passe, tes informations à toi personnelles »).

Un clipper arrivé depuis REMISE_PSEUDO_SEUL_DEPUIS reçoit ses comptes avec l'@ seul : ni e-mail ni mot de passe de l'agence, ni
salon des codes. Une ligne « à créer » sans e-mail lui est livrable. Les clippers déjà en route gardent les accès de l'agence.
Sans réseau ni Discord."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboarding
import parcours as p
import process_adapters
import remise_compte1
from process_store import Store

DOSSIER = Path(__file__).resolve().parents[1]


class MarqueTests(unittest.TestCase):
    def test_regle_du_moment(self):
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", "2026-10-30T00:00:00+00:00"):
            self.assertTrue(p.pseudo_seul_actif())                      # la date du jour est passée
            self.assertTrue(p._marque_pseudo().get("pseudo_seul"))
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", "2999-01-01T00:00:00+00:00"):
            self.assertFalse(p.pseudo_seul_actif())
            self.assertEqual({}, p._marque_pseudo())
        for vide in ("", "pas une date"):
            with patch.object(p, "PSEUDO_SEUL_DEPUIS", vide):
                self.assertFalse(p.pseudo_seul_actif())

    def test_un_clipper_deja_en_route_garde_sa_regle(self):
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", "2026-10-30T00:00:00+00:00"):
            self.assertEqual({}, p._marque_pseudo_pour({"messages": {"1": "123"}}))       # compte 1 parti avec les accès
            self.assertEqual({"pseudo_seul": "x"}, p._marque_pseudo_pour({"pseudo_seul": "x", "messages": {"1": "1"}}))
            self.assertTrue(p._marque_pseudo_pour({"prenom": "Nouveau"}).get("pseudo_seul"))  # fiche d'attente, rien de remis
            self.assertTrue(p._marque_pseudo_pour(None).get("pseudo_seul"))
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", ""):
            self.assertEqual({}, p._marque_pseudo_pour(None))

    def test_un_compte_qui_existe_deja_garde_ses_acces(self):
        fiche = {"pseudo_seul": "x"}
        self.assertTrue(p._remise_par_pseudo(fiche, {"creation2": p.CREATION_PSEUDO[1]}, 2))
        self.assertFalse(p._remise_par_pseudo(fiche, {"creation2": p.CONNEXION[1]}, 2))
        with patch.object(p, "PSEUDO_SEUL_TOUS", False):
            self.assertFalse(p._remise_par_pseudo({}, {"creation2": p.CREATION[1]}, 2))

    def test_anciens_clippers_aussi_a_l_arobase_seul(self):
        """30/10, 7 h 54 : les comptes pas encore donnés d'un clipper déjà en route partent aussi avec l'@ seul."""
        ancien = {"messages": {"1": "123"}}
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", "2026-10-30T00:00:00+00:00"), patch.object(p, "PSEUDO_SEUL_TOUS", True):
            self.assertTrue(p.pseudo_seul(ancien))
            with patch.object(p, "_lire", return_value={"7": ancien}):
                self.assertTrue(p.pseudo_seul_uid("7"))
        with patch.object(p, "PSEUDO_SEUL_DEPUIS", ""), patch.object(p, "PSEUDO_SEUL_TOUS", True):
            self.assertFalse(p.pseudo_seul(ancien))                     # interrupteur général éteint


class TextesTests(unittest.TestCase):
    def test_compte_1_sans_acces_de_l_agence(self):
        texte = remise_compte1.modele_pseudo("<@1>", "reels.fictif", suite=p.LIGNE_48H)
        self.assertIn("```\nreels.fictif\n```", texte)
        self.assertEqual(2, texte.count("```"))                         # un seul bloc à copier : l'identifiant
        for absent in ("E-mail :", "Mot de passe :", "Mon code", "code-instagram"):
            self.assertNotIn(absent, texte)
        self.assertIn("ton e-mail et ton mot de passe à toi", texte)
        self.assertLess(texte.index("1️⃣"), texte.index("4️⃣"))
        self.assertTrue(texte.endswith(p.LIGNE_48H))

    def test_creation_des_comptes_2_et_3(self):
        for gabarit in p.CREATION_PSEUDO:
            self.assertNotIn("{codes}", gabarit)
            self.assertNotIn("cet e-mail", gabarit)
            self.assertIn("mot de passe", gabarit)
        self.assertNotIn("responsable", p.ACCES_PSEUDO)


class CompteUnTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "fictif.sqlite3")
        self.store.reconcile("42", [], "historique-fictif")
        self.etat = {"42": {"creatrice": "Fictive", "dates": {}, "messages": {}, "pseudo_seul": "2026-10-30T08:00:00+00:00"}}
        self.membre = N(id=42, mention="<@42>")
        self.salon = N(id=99, guild=None, send=AsyncMock(return_value=N(id=123)))
        self.surs = AsyncMock(side_effect=AssertionError("aucun accès de l'agence à lire"))
        self.alerte = AsyncMock()

        def ecrire(d):
            self.etat = deepcopy(d)
        patches = [
            patch.object(process_adapters, "store", return_value=self.store),
            patch.object(remise_compte1, "identifiants_surs", self.surs),
            patch.multiple(p, _lire=lambda: deepcopy(self.etat), _ecrire=ecrire, _deps={},
                           _ligne_du_compte=AsyncMock(return_value=True),
                           _comptes_ordonnes=lambda *a, **kw: ["pseudo_fictif", "autre_fictif"],
                           _contexte=AsyncMock(return_value={"compte1": "pseudo_fictif"}),
                           _vue=lambda *a: None, _retirer_pret=AsyncMock(), alerter_acces_en_attente=self.alerte),
            patch.dict(p.onboarding._deps, {"FICHIER_ONBOARDING": Path(self.tmp.name) / "onboarding.json",
                                            "lire_json": lambda *a: {}}),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_l_arobase_seul_sans_alerte_ni_acces_en_attente(self):
        self.assertTrue(await p.envoyer_etape(self.salon, self.membre, 1))
        texte = self.salon.send.call_args.args[0]
        self.assertIn("```\npseudo_fictif\n```", texte)
        self.assertIn("ton e-mail et ton mot de passe à toi", texte)
        for absent in ("E-mail :", "Mot de passe :", "Mon code", "remis ici par le propriétaire"):
            self.assertNotIn(absent, texte)
        self.surs.assert_not_awaited()
        self.alerte.assert_not_awaited()
        self.assertNotIn("acces_en_attente", self.etat["42"])


class CompteDeuxTests(unittest.IsolatedAsyncioTestCase):
    async def test_l_arobase_seul_sans_lecture_du_classeur(self):
        etat = {"42": {"creatrice": "Fictive", "pseudo_seul": "x", "ordre": "prive3", "etape": 1,
                       "dates": {"1": "2026-10-30T08:00:00+00:00", "1_fait": "2026-10-30T09:00:00+00:00"},
                       "messages": {"1": "111"}}}
        salon = N(id=99, guild=None, send=AsyncMock(return_value=N(id=222)))
        avec_acces = AsyncMock(side_effect=AssertionError("aucun accès de l'agence à lire"))

        def ecrire(d):
            etat.clear()
            etat.update(deepcopy(d))
        ctx = {"compte1": "un_fictif", "compte2": "deux_fictif", "creation2": p.CREATION_PSEUDO[1]}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "fictif.sqlite3")
        store.reconcile("42", [], "historique-fictif")
        with patch.object(process_adapters, "store", return_value=store), \
                patch.multiple(p, _lire=lambda: deepcopy(etat), _ecrire=ecrire, _deps={},
                            _comptes_ordonnes=lambda *a, **kw: ["un_fictif", "deux_fictif", "trois_fictif"],
                            _ligne_du_compte=AsyncMock(return_value=True), _contexte=AsyncMock(return_value=ctx),
                            _vue=lambda *a: None, _avec_acces=avec_acces, ligne_publication=lambda *a: ""):
            self.assertTrue(await p.envoyer_etape(salon, N(id=42, mention="<@42>"), 2))
        texte = salon.send.call_args.args[0]
        self.assertIn(p.ACCES_PSEUDO, texte)
        self.assertNotIn(p.ACCES_A_CONFIRMER, texte)
        self.assertIn("@deux_fictif", texte)
        avec_acces.assert_not_awaited()
        self.assertEqual("inclus", etat["42"]["acces_etape"]["2"])     # relancer_acces n'a rien à remettre


class LignesLivrablesTests(unittest.TestCase):
    LIGNES = [{"utilisation": "Clipper", "gerant": "", "etat": "à créer", "handle": "sans_mail", "mail": "", "mdp": "",
               "creatrice": "Fictive", "ligne": 2, "pod": ""},
              {"utilisation": "Clipper", "gerant": "", "etat": "à créer", "handle": "avec_mail", "mail": "a@exemple.invalid",
               "mdp": "x", "creatrice": "Fictive", "ligne": 3, "pod": ""}]

    def setUp(self):
        for patcher in (patch.object(onboarding, "_proprietaires", return_value={}),
                        patch.object(process_adapters, "store", return_value=N(owner_for_handle=lambda h: None))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _handles(self, pseudo: bool) -> list:
        with patch.object(p, "pseudo_seul_uid", return_value=pseudo):
            return [c["handle"] for c in onboarding.disponibles(deepcopy(self.LIGNES), "Fictive", 999, "42")]

    def test_ligne_sans_e_mail_livrable_au_nouveau_seulement(self):
        self.assertEqual(["avec_mail"], self._handles(False))
        self.assertEqual({"avec_mail", "sans_mail"}, set(self._handles(True)))


class QuizTests(unittest.TestCase):
    def test_quiz_du_loom_du_30_10(self):
        quiz = json.loads((DOSSIER / "quiz.json").read_text(encoding="utf-8"))
        self.assertEqual(8, quiz["seuil"])
        ids = [q["id"] for q in quiz["questions"]]
        self.assertEqual(["mot1", "mot2", "mot3", "mot4", "mot5", "arobase", "modifier", "trop_sexy", "comptes_separes", "tunnel"], ids)
        mots = [q["reponses"][0] for q in quiz["questions"] if q.get("reponses")]
        self.assertEqual(["régularité", "volume", "variation", "sécurité", "conversion"], mots)
        for q in quiz["questions"]:
            if "choix" in q:
                self.assertEqual(3, len(q["choix"]))
                self.assertIn(q["bonne"], range(3))
        arobase = next(q for q in quiz["questions"] if q["id"] == "arobase")
        self.assertIn("mon e-mail, mon mot de passe", arobase["choix"][arobase["bonne"]])


if __name__ == "__main__":
    unittest.main()
