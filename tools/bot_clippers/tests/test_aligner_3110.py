"""31/10, 7 h 04 (Gaëtan : « Résous le problème d'Espérance »). Son compte 3 retenu toutes les 30 min par « Trois places à vie »,
son compte 1 jamais confirmé : la fiche portait un @ mal tapé (absent du LOG) et deux essais de privé jamais faits, alors que le LOG
porte ses trois comptes créés. Cas fictifs, sans réseau, sans Discord, sans classeur."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arobase_libre as a
import corrections as co
import onboarding
import parcours
import process_adapters
from process_store import Bloque, Store

LIBRE = {"verdict": "libre"}
INCONNU_ANCIEN = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": False, "abonnes": 900, "publications": 40}
NEUF = {"verdict": "pris", "profil_lu": True, "neuf": True, "a_nous": False, "abonnes": 2, "publications": 0}
A_NOUS = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": True, "abonnes": 300, "publications": 9}


class RegistreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / "p.sqlite3")
        for uid in ("42", "43"):
            self.s.reconcile(uid, [], "revue-fictive")

    def test_une_place_jamais_creee_libere_le_compte_3(self):
        self.s.reserve("42", ["un_fictif", "deux.fictif", "essai.fictif"])
        self.s.created("42", "deux.fictif", "confirmation-fictive")
        with self.assertRaises(Bloque):
            self.s.reserve("42", ["trois.fictif"])                      # avant : « Trois places à vie »
        self.s.retirer_doublon("42", "@Essai.Fictif", "libre sur Instagram (fictif)")
        self.s.reserve("42", ["trois.fictif"])
        self.assertEqual("42", self.s.owner_for_handle("essai.fictif"))  # l'alias reste : jamais réattribué
        with self.assertRaises(Bloque):
            self.s.reserve("43", ["essai.fictif"])
        statuts = {tuple(al): st for _, st, al in self.s.comptes_de("42")}
        self.assertEqual("cancelled", statuts[("essai.fictif",)])
        self.assertEqual("created", statuts[("deux.fictif",)])

    def test_jamais_un_compte_cree_ni_celui_d_un_autre_ni_sans_preuve(self):
        self.s.reserve("42", ["a.fictif", "b.fictif"])
        self.s.created("42", "a.fictif", "confirmation-fictive")
        for uid, h, preuve in (("42", "a.fictif", "x"), ("43", "b.fictif", "x"), ("42", "b.fictif", ""), ("42", "inconnu", "x")):
            with self.assertRaises(Bloque, msg=(uid, h)):
                self.s.retirer_doublon(uid, h, preuve)


class JamaisALuiTests(unittest.TestCase):
    def test_seulement_sur_preuve(self):
        self.assertTrue(co.jamais_a_lui(LIBRE))
        self.assertTrue(co.jamais_a_lui(INCONNU_ANCIEN))
        for ex in (NEUF, A_NOUS, {"verdict": "inconnu"}, {**INCONNU_ANCIEN, "profil_lu": False}, {}, None):
            self.assertFalse(co.jamais_a_lui(ex), ex)


LOG = [{"handle": "un_c.fictif", "etat": "GOOD", "gerant": "Fictive", "creatrice": "Chloé"},
       {"handle": "deux.fictif", "etat": "GOOD", "gerant": "Fictive", "creatrice": "Chloé"},
       {"handle": "trois.prive_fictif", "etat": "GOOD", "gerant": "Fictive", "creatrice": "Chloé"},
       {"handle": "essai.secret_fictif_x", "etat": "à créer", "gerant": "", "creatrice": "Chloé"}]


class AlignerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registre = Store(Path(self.tmp.name) / "p.sqlite3")
        self.registre.reconcile("42", [], "revue-fictive")
        self.registre.reserve("42", ["un_.fictif", "deux.fictif", "essai.prv_fictif"])
        self.registre.created("42", "deux.fictif", "confirmation-fictive")
        self.onb = {"clippers": {"42": {"comptes": ["un_.fictif", "deux.fictif", "trois.prive_fictif", "essai.prv_fictif",
                                                    "essai.secret_fictif"], "acces": []}}}
        self.parc = {"42": {"prenom": "Fictive", "creatrice": "Chloé", "etape": 3, "salon_id": "7", "force_2": True,
                            "dates": {"1": "2026-10-17T08:00:00+00:00", "2": "2026-10-24T10:00:00+00:00",
                                      "2_fait": "2026-10-25T09:00:00+00:00"}, "messages": {"1": "111", "2": "222"}}}
        self.examens = {"un_.fictif": LIBRE, "essai.prv_fictif": LIBRE, "essai.secret_fictif": INCONNU_ANCIEN}
        self.bouton = AsyncMock()

        def renommer(uid, ancien, nouveau):
            f = self.onb["clippers"][uid]
            f["comptes"] = [nouveau if h == ancien else h for h in f["comptes"]]

        def ecrire_onb(e):
            self.onb = deepcopy(e)

        def ecrire_parc(d):
            self.parc = deepcopy(d)
        for patcher in (patch.object(onboarding, "lire_comptes", AsyncMock(side_effect=lambda: deepcopy(LOG))),
                        patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(self.onb)),
                        patch.object(onboarding, "_ecrire_etat", side_effect=ecrire_onb),
                        patch.object(onboarding, "_appliquer_nouveau_handle", side_effect=renommer),
                        patch.object(process_adapters, "store", return_value=self.registre),
                        patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": self.examens.get(h, {"verdict": "inconnu"}))),
                        patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.parc)),
                        patch.object(parcours, "_ecrire", side_effect=ecrire_parc),
                        patch.object(parcours, "_retirer_bouton", self.bouton)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = N(get_channel=lambda i: "salon-fictif" if i == 7 else None)
        self.action = {"action": "aligner", "prenom": "Fictive", "creatrice": "Chloé",
                       "comptes": ["un_c.fictif", "deux.fictif", "trois.prive_fictif"], "renommer": {"un_.fictif": "un_c.fictif"}}

    async def test_le_cas_esperance(self):
        bilan = await co._aligner(self.action, "42", self.client)
        texte = "\n".join(bilan)
        self.assertEqual(["un_c.fictif", "deux.fictif", "trois.prive_fictif"], self.onb["clippers"]["42"]["comptes"])
        self.assertEqual(["un_c.fictif", "deux.fictif", "trois.prive_fictif"], parcours._comptes_ordonnes("42", onb=self.onb["clippers"]["42"]))
        statuts = {h: st for _, st, al in self.registre.comptes_de("42") for h in al}
        self.assertEqual("created", statuts["un_c.fictif"])                # même place que @un_.fictif, renommée
        self.assertEqual("created", statuts["trois.prive_fictif"])         # la place du compte 3 existe enfin
        self.assertEqual("cancelled", statuts["essai.prv_fictif"])
        self.assertEqual({"created": 3, "cancelled": 1}, self.registre.counts("42"))
        dates = self.parc["42"]["dates"]
        self.assertIn("1_fait", dates)                                     # compte 1 noté créé, sans message
        self.assertNotIn("3_fait", dates)                                  # l'étape en cours suit son cours
        self.assertEqual(3, self.parc["42"]["etape"])
        self.bouton.assert_awaited_once_with("salon-fictif", "111")
        self.assertIn("aligné sur le LOG", bilan[0])
        self.assertIn("@essai.prv_fictif", texte)
        self.assertIn("compte 1 noté(s) créé(s), sans message", texte)
        self.assertNotIn("⚠️", texte)

    async def test_rejoue_ne_change_plus_rien(self):
        await co._aligner(self.action, "42", self.client)
        avant = (deepcopy(self.onb), deepcopy(self.parc), self.registre.counts("42"))
        bilan = await co._aligner(self.action, "42", self.client)
        self.assertEqual(avant, (self.onb, self.parc, self.registre.counts("42")))
        self.assertEqual(1, len(bilan))

    async def test_un_doute_sur_instagram_garde_le_compte(self):
        self.examens["essai.prv_fictif"] = NEUF                           # il a peut-être créé cet essai : jamais retiré
        bilan = "\n".join(await co._aligner(self.action, "42", self.client))
        self.assertIn("essai.prv_fictif", self.onb["clippers"]["42"]["comptes"])
        statuts = {h: st for _, st, al in self.registre.comptes_de("42") for h in al}
        self.assertEqual("reserved", statuts["essai.prv_fictif"])
        self.assertIn("à trancher", bilan)
        self.assertIn("trois.prive_fictif", bilan)                         # « Trois places à vie » : dit, pas contourné
        self.assertNotIn("trois.prive_fictif", statuts)

    async def test_retirer_sur_decision_jamais_un_compte_du_log(self):
        self.examens["essai.prv_fictif"] = NEUF                           # doute d'Instagram, tranché dans le dépôt
        action = {**self.action, "retirer": ["essai.prv_fictif", "deux.fictif", "trois.prive_fictif"]}
        bilan = "\n".join(await co._aligner(action, "42", self.client))
        self.assertEqual(["un_c.fictif", "deux.fictif", "trois.prive_fictif"], self.onb["clippers"]["42"]["comptes"])
        statuts = {h: st for _, st, al in self.registre.comptes_de("42") for h in al}
        self.assertEqual("cancelled", statuts["essai.prv_fictif"])
        self.assertEqual("created", statuts["deux.fictif"])               # un compte créé du LOG : jamais retiré
        self.assertEqual("created", statuts["trois.prive_fictif"])
        self.assertIn("sur décision (pas au LOG à son nom) : @essai.prv_fictif", bilan)
        self.assertNotIn("⚠️", bilan)

    async def test_rien_sans_les_trois_lignes_creees_a_son_nom(self):
        for comptes in (["un_c.fictif", "deux.fictif", "essai.secret_fictif_x"],     # « à créer » dans le LOG
                        ["un_c.fictif", "deux.fictif", "absent.fictif"],
                        ["un_c.fictif", "deux.fictif", "deux.fictif"]):
            avant = (deepcopy(self.onb), deepcopy(self.parc), self.registre.counts("42"))
            bilan = await co._aligner({**self.action, "comptes": comptes}, "42", self.client)
            self.assertIn("rien changé", bilan[0])
            self.assertEqual(avant, (self.onb, self.parc, self.registre.counts("42")))
        with patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[{**c, "gerant": "Autre"} for c in LOG])):
            self.assertIn("rien changé", (await co._aligner(self.action, "42", self.client))[0])

    async def test_branche_dans_appliquer(self):
        with patch.object(co, "_aligner", AsyncMock(return_value=["🧩 Fictive (Chloé) aligné sur le LOG", "✅ parcours"])) as al:
            bilan = await co.appliquer(N(guilds=[]), {"actions": [self.action]})
        self.assertEqual("42", al.await_args.args[1])
        self.assertEqual(["🧩 Fictive (Chloé) aligné sur le LOG", "✅ parcours"], bilan[:2])
        self.assertIn("registre :", bilan[2])                              # 31/10 : les places après l'alignement

    def test_le_depot_du_jour(self):
        import json
        depot = json.loads(co.FICHIER.read_text(encoding="utf-8"))
        self.assertTrue(depot["id"].startswith("3110-"))
        al = next(x for x in depot["actions"] if x["action"] == "aligner")
        self.assertEqual(("Esperance", "Chloé"), (al["prenom"], al["creatrice"]))
        self.assertEqual(3, len(al["comptes"]))

    async def test_registre_en_lecture_seule_et_bilan_au_journal(self):
        await co._aligner(self.action, "42", self.client)
        avant = (deepcopy(self.onb), deepcopy(self.parc), self.registre.comptes_de("42"))
        with patch.object(parcours, "_comptes_ordonnes", return_value=["un_c.fictif", "deux.fictif", "trois.prive_fictif"]):
            ligne = await co._registre({"prenom": "Fictive", "creatrice": "Chloé"}, "42")
        self.assertEqual(avant, (self.onb, self.parc, self.registre.comptes_de("42")))
        self.assertIn("registre : 3 place(s) prise(s) sur 3", ligne)
        self.assertIn("@essai.prv_fictif cancelled", ligne)
        self.assertIn("étape 3", ligne)
        self.assertIn('journal.info("Correction %s : %s"', Path(co.__file__).read_text(encoding="utf-8"))


class RetenuesTests(unittest.IsolatedAsyncioTestCase):
    """31/10 : le compte 3 d'Esperance retenu toutes les 30 min pendant plus de deux jours, sans que personne le voie."""

    def test_depuis_garde_le_premier_essai_de_la_meme_etape(self):
        f = {}
        with patch.object(parcours, "_maintenant", return_value="2026-10-29T07:00:00+00:00"):
            parcours._noter_retenue(f, 3, "Trois places à vie déjà créées, réservées ou incertaines")
        with patch.object(parcours, "_maintenant", return_value="2026-10-31T03:00:00+00:00"):
            parcours._noter_retenue(f, 3, "Trois places à vie déjà créées, réservées ou incertaines")
            self.assertEqual("2026-10-29T07:00:00+00:00", f["retenue"]["depuis"])
            parcours._noter_retenue(f, 2, "autre")                        # une autre étape repart de zéro
            self.assertEqual("2026-10-31T03:00:00+00:00", f["retenue"]["depuis"])

    def test_retenues_longues(self):
        from datetime import datetime, timezone
        m = datetime(2026, 10, 31, 3, 30, tzinfo=timezone.utc)
        d = {"1": {"prenom": "Fictive", "retenue": {"n": 3, "raison": "Trois places", "depuis": "2026-10-29T07:00:00+00:00",
                                                    "date": "2026-10-31T03:00:00+00:00"}},
             "2": {"prenom": "Recent", "retenue": {"n": 1, "raison": "x", "depuis": "2026-10-31T01:00:00+00:00",
                                                   "date": "2026-10-31T03:00:00+00:00"}},
             "3": {"prenom": "Debloque", "retenue": {"n": 2, "raison": "x", "depuis": "2026-10-20T01:00:00+00:00",
                                                     "date": "2026-10-21T03:00:00+00:00"}},
             "4": {"prenom": "Sorti", "sorti": True, "retenue": {"n": 2, "raison": "x", "depuis": "2026-10-20T01:00:00+00:00",
                                                                 "date": "2026-10-31T03:00:00+00:00"}}}
        self.assertEqual([("1", "Fictive", 3, "Trois places", 44)], parcours.retenues_longues(d, m))

    async def test_alerte_une_fois_par_jour(self):
        from datetime import datetime, timezone
        m = datetime(2026, 10, 31, 3, 30, tzinfo=timezone.utc)
        etat = {"1": {"prenom": "Fictive", "retenue": {"n": 3, "raison": "Trois places", "depuis": "2026-10-29T07:00:00+00:00",
                                                       "date": "2026-10-31T03:00:00+00:00"}}}
        canal = N(send=AsyncMock())

        def ecrire(d):
            etat.clear()
            etat.update(deepcopy(d))
        with patch.object(parcours, "_lire", side_effect=lambda: deepcopy(etat)), patch.object(parcours, "_ecrire", side_effect=ecrire), \
                patch.dict(parcours._deps, {"canal_admin": AsyncMock(return_value=canal)}):
            self.assertEqual(1, len(await parcours.alerter_retenues(m)))
            self.assertEqual([], await parcours.alerter_retenues(m))
        canal.send.assert_awaited_once()
        self.assertIn("compte 3 retenu depuis 44 h (Trois places)", canal.send.await_args.args[0])

    def test_branche_dans_la_boucle(self):
        self.assertIn("await alerter_retenues()", Path(parcours.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
