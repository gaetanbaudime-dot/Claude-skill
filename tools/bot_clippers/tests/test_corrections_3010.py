"""30/10, 10 h 59 (Gaëtan : « Tu libères Ben, Oumar et Alvaro… Si je les vire dans mon cockpit, tu les libères automatiquement.
Je ne veux pas avoir à le faire » ; Georgial, Amour, Andrianina : « tu appliques les recommandations »). Cas fictifs, sans réseau."""
from pathlib import Path
from types import SimpleNamespace as N
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arobase_libre as a
import cockpit_sorties as cs
import corrections as co
import onboarding
import process_adapters
from process_store import Bloque, Store


class RegistreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / "p.sqlite3")
        for uid in ("42", "43"):
            self.s.reconcile(uid, [], "revue-fictive")

    def test_une_reservation_jamais_creee_repart_au_stock_pour_un_autre(self):
        self.s.reserve("42", ["neuf.fictif", "cree.fictif"])
        self.s.created("42", "cree.fictif", "confirmation-fictive")
        with self.assertRaises(Bloque):
            self.s.reserve("43", ["neuf.fictif"])                       # avant : réattribution interdite
        self.s.rendre_au_stock("42", "@Neuf.Fictif", "ligne à créer, @ libre (fictif)")
        self.assertIsNone(self.s.owner_for_handle("neuf.fictif"))
        self.s.reserve("43", ["neuf.fictif"])
        self.assertEqual("43", self.s.owner_for_handle("neuf.fictif"))
        self.assertEqual({"created": 1, "cancelled": 1}, self.s.counts("42"))   # l'historique reste

    def test_jamais_un_compte_cree_ni_celui_d_un_autre_ni_sans_preuve(self):
        self.s.reserve("42", ["a.fictif", "b.fictif"])
        self.s.created("42", "a.fictif", "confirmation-fictive")
        for uid, h, preuve in (("42", "a.fictif", "x"), ("43", "b.fictif", "x"), ("42", "b.fictif", ""), ("42", "inconnu", "x")):
            with self.assertRaises(Bloque, msg=(uid, h)):
                self.s.rendre_au_stock(uid, h, preuve)


class FauxRegistre:
    def __init__(self, proprietaires):
        self.proprietaires, self.rendus = dict(proprietaires), []

    def owner_for_handle(self, h):
        return self.proprietaires.get(h)

    def rendre_au_stock(self, uid, h, preuve):
        self.rendus.append((uid, h))


LOG = [{"handle": "un.fictif", "etat": "à créer", "gerant": "Parti", "creatrice": "Sophie"},
       {"handle": "deux.fictif", "etat": "à créer", "gerant": "Parti", "creatrice": "Sophie"},
       {"handle": "cree.fictif", "etat": "GOOD", "gerant": "Parti", "creatrice": "Sophie"},
       {"handle": "autre.fictif", "etat": "à créer", "gerant": "Parti", "creatrice": "Sarah"},
       {"handle": "voisin.fictif", "etat": "à créer", "gerant": "Voisin", "creatrice": "Sophie"}]


class RendreLignesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registre = FauxRegistre({"un.fictif": "9", "deux.fictif": "9", "cree.fictif": "9"})
        self.liberer = AsyncMock(side_effect=lambda p, handles=(), pool=False: [f"· `{h}` → retour au pool" for h in handles])
        for patcher in (patch.object(process_adapters, "store", return_value=self.registre),
                        patch.object(onboarding, "_lire_etat", return_value={"clippers": {"9": {"comptes": []}}}),
                        patch.object(onboarding, "liberer", self.liberer)):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_seules_les_lignes_a_creer_libres_du_sorti_repartent(self):
        verdicts = {"un.fictif": a.LIBRE, "deux.fictif": a.INCONNU}
        with patch.object(a, "verdict", AsyncMock(side_effect=lambda h: verdicts.get(h, a.PRIS))):
            bilan = await onboarding.rendre_lignes("Parti", "Sophie", comptes=LOG, actifs=set())
        self.assertEqual(["un.fictif"], self.liberer.await_args.kwargs["handles"])   # deux : pas de preuve, cree : jamais
        self.assertEqual([("9", "un.fictif")], self.registre.rendus)
        self.assertEqual(1, len(bilan))

    async def test_un_clipper_encore_signe_garde_ses_lignes_sauf_decision(self):
        with patch.object(a, "verdict", AsyncMock(return_value=a.LIBRE)):
            self.assertEqual([], await onboarding.rendre_lignes("Parti", "Sophie", comptes=LOG, actifs={"9"}))
            self.liberer.assert_not_awaited()
            await onboarding.rendre_lignes("Parti", "Sophie", handles=["un.fictif"], comptes=LOG, actifs={"9"}, actifs_permis=True)
        self.assertEqual(["un.fictif"], self.liberer.await_args.kwargs["handles"])


class CockpitTests(unittest.IsolatedAsyncioTestCase):
    async def test_les_sortis_du_cockpit_rendent_leurs_lignes(self):
        rendre = AsyncMock(return_value=["· `un.fictif` (à créer) → retour au pool des clippers"])
        registre = {"1": {"prenom": "Voisin"}, "2": {"prenom": "Homonyme - Sarah"}}
        lignes = [{"prenom": "Parti", "creatrice": "Sophie", "role": "Sorti"}, {"prenom": "Homonyme", "creatrice": "Sarah",
                  "role": "Sorti"}, {"prenom": "Rien", "creatrice": "Jade", "role": "Sorti"},
                  {"prenom": "Voisin", "creatrice": "Sophie", "role": "Clipper"}]
        log = LOG + [{"handle": "h.fictif", "etat": "à créer", "gerant": "Homonyme", "creatrice": "Sarah"}]
        with patch.dict(cs._deps, {"rendre_lignes": rendre, "lire_json": lambda f, d: registre, "FICHIER_EQUIPES": "eq"}), \
                patch.object(onboarding, "lire_comptes", AsyncMock(return_value=log)):
            out = await cs.rendre_lignes_des_sortis(lignes)
        rendre.assert_awaited_once()                                    # ni l'homonyme signé, ni celui sans ligne
        self.assertEqual(("Parti", "Sophie"), rendre.await_args.args)
        self.assertEqual({"1", "2"}, rendre.await_args.kwargs["actifs"])
        self.assertIn("Parti (Cockpit : Sorti) : 1 ligne(s)", out[0])

    def test_branche_dans_le_passage_et_le_bot(self):
        source = (Path(cs.__file__)).read_text(encoding="utf-8")
        self.assertIn("bilan += await rendre_lignes_des_sortis(lignes)", source)
        bot = (Path(cs.__file__).with_name("bot_discord.py")).read_text(encoding="utf-8")
        self.assertIn('"rendre_lignes": onboarding.rendre_lignes', bot)
        self.assertIn("corrections.demarrage(client)", bot)


class CorrectionsTests(unittest.IsolatedAsyncioTestCase):
    FICHES = {"10": {"prenom": "Georgial", "creatrice": "Sarah"}, "11": {"prenom": "Amour", "creatrice": "Sophie"},
              "12": {"prenom": "Amour", "creatrice": "Jade"}}

    def test_uid_de(self):
        self.assertEqual("10", co.uid_de(self.FICHES, "georgial", "Sarah"))
        self.assertEqual("11", co.uid_de(self.FICHES, "Amour", "Sophie"))
        self.assertEqual("", co.uid_de(self.FICHES, "Amour", ""))       # deux fiches : jamais deviné
        self.assertEqual("", co.uid_de(self.FICHES, "Inconnu", "Sarah"))

    async def test_appliquer_dans_l_ordre_et_bilan(self):
        import parcours
        import remise_arobases
        depot = {"actions": [{"action": "rendre", "prenom": "Parti", "creatrice": "Sophie"},
                             {"action": "fiche", "prenom": "Georgial", "creatrice": "Sarah", "ancien": "a.fictif", "nouveau": "b.fictif"},
                             {"action": "variante", "prenom": "Fantome", "creatrice": "Sarah", "n": 3},
                             {"action": "remise", "clippers": [["Georgial", "Sarah"]]}]}
        rendre = AsyncMock(return_value=["· `un.fictif` → retour au pool"])
        remise = AsyncMock(return_value={"messages": 1, "bilan": ["• Georgial (Sarah) : compte 2 `b.fictif`"]})
        with patch.object(parcours, "_lire", return_value=self.FICHES), \
                patch.dict(co._deps, {"lire_json": lambda f, d: {}, "FICHIER_EQUIPES": "eq"}), \
                patch.object(onboarding, "rendre_lignes", rendre), \
                patch.object(co, "_fiche", AsyncMock(return_value="✏️ fiche")) as fiche, \
                patch.object(remise_arobases, "remise", remise):
            bilan = await co.appliquer(N(guilds=[]), depot)
        self.assertEqual(set(), rendre.await_args.kwargs["actifs"])       # le registre (vide ici) borne les lignes rendues
        fiche.assert_awaited_once()
        self.assertEqual("10", fiche.await_args.args[1])
        self.assertEqual({"10"}, remise.await_args.kwargs["seulement"])
        self.assertIn("♻️ Parti : 1 ligne(s)", bilan[0])
        self.assertIn("Fantome (Sarah) : fiche introuvable", bilan[2])
        self.assertIn("1 message(s) envoyé(s)", bilan[3])

    async def test_un_homonyme_signe_bloque_la_liberation(self):
        rendre = AsyncMock()
        with patch.dict(co._deps, {"lire_json": lambda f, d: {"1": {"prenom": "Benn"}}, "FICHIER_EQUIPES": "eq"}), \
                patch.object(onboarding, "rendre_lignes", rendre), patch("parcours._lire", return_value={}):
            bilan = await co.appliquer(N(guilds=[]), {"actions": [{"action": "rendre", "prenom": "Benn", "creatrice": "Sophie"}]})
        rendre.assert_not_awaited()
        self.assertIn("un clipper signé porte ce prénom", bilan[0])

    async def test_attendre_le_controle_github(self):
        lus = iter([None, {"verdict": a.PRIS}, {"verdict": a.PRIS, "variante": "x_fictif"}])
        with patch.object(a, "depuis_ci", AsyncMock(side_effect=lambda h: next(lus))), patch.object(co.asyncio, "sleep", AsyncMock()):
            self.assertEqual([], await co._attendre_ci([{"handle": "x.fictif", "variante": True}]))
        with patch.object(a, "depuis_ci", AsyncMock(return_value=None)), patch.object(co.asyncio, "sleep", AsyncMock()), \
                patch.object(co, "ATTENTE_CI_MIN", 2):
            self.assertEqual(1, len(await co._attendre_ci([{"handle": "y.fictif"}])))


if __name__ == "__main__":
    unittest.main()
