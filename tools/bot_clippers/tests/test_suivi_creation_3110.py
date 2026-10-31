"""31/10, 9 h 38 (Gaëtan : « Ne juge que la création du compte Instagram par le scrapping RapidAPI. Quand tu sais que tu as délivré
le compte Instagram à un clipper, vérifie assez fréquemment s'il l'a créé ou pas » ; « Gère le problème entre le compte un et les
comptes deux et trois »). Cas fictifs, sans réseau, sans Discord, sans classeur."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arobase_libre as a
import parcours
import suivi_creation as sc

M = datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc)
LIBRE = {"verdict": "libre"}
NEUF = {"verdict": "pris", "profil_lu": True, "neuf": True, "a_nous": False, "abonnes": 2, "publications": 0}
INSTALLE = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": False, "abonnes": 900, "publications": 40}
GROS_A_NOUS = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": True, "abonnes": 900, "publications": 40}


_TMP = tempfile.TemporaryDirectory()
_FICHIER = patch.object(sc, "FICHIER", Path(_TMP.name) / "suivi_creation.json")


def setUpModule():
    _FICHIER.start()


def tearDownModule():
    _FICHIER.stop()
    _TMP.cleanup()


def iso(dt):
    return dt.isoformat(timespec="seconds")


def comptes(uid, f):
    return ["un.fictif", "deux.fictif", "trois.prive_fictif"]


class PursTests(unittest.TestCase):
    def test_intervalle(self):
        self.assertEqual([60, 180, 480, 1440], [sc.intervalle_min(h) for h in (2, 30, 100, 300)])

    def test_juger(self):
        self.assertEqual(sc.PAS_CREE, sc.juger(LIBRE))
        self.assertEqual(sc.CREE, sc.juger(NEUF))
        self.assertEqual(sc.CREE, sc.juger(GROS_A_NOUS))
        self.assertEqual(sc.CREE, sc.juger(INSTALLE, libre_vu=True))   # vu libre puis créé : c'est le sien, même grossi
        self.assertEqual(sc.INSTALLE, sc.juger(INSTALLE))
        self.assertEqual(sc.DOUTE, sc.juger({"verdict": "inconnu"}))
        self.assertEqual(sc.DOUTE, sc.juger({"verdict": "pris", "profil_lu": False}))
        self.assertEqual(sc.CREE, sc.juger({"verdict": "pris", "profil_lu": False}, libre_vu=True))

    def test_remis(self):
        f = {"dates": {"2": iso(M - timedelta(hours=5))},
             "donnes": {"3": {"handle": "trois.prive_fictif", "le": iso(M - timedelta(days=1)), "a_partir_de": iso(M + timedelta(days=1))}}}
        self.assertEqual((M - timedelta(hours=5), M - timedelta(hours=5)), sc.remis(f, 2, "deux.fictif"))
        self.assertEqual((M - timedelta(days=1), M + timedelta(days=1)), sc.remis(f, 3, "trois.prive_fictif"))
        self.assertEqual((None, None), sc.remis(f, 1, "un.fictif"))
        self.assertEqual((None, None), sc.remis(f, 3, "autre.fictif"))           # la remise d'un autre @ ne compte pas

    def test_a_verifier(self):
        d = {"1": {"etape": 2, "dates": {"1": iso(M - timedelta(days=4)), "1_fait": iso(M - timedelta(days=3)),
                                         "2": iso(M - timedelta(hours=2))},
                   "verif_ig": {"2": {"h": "deux.fictif", "le": iso(M - timedelta(minutes=30))}}},
             "2": {"etape": 2, "dates": {"1": iso(M - timedelta(days=4)), "1_fait": iso(M - timedelta(days=3)),
                                         "2": iso(M - timedelta(hours=2))}},
             "3": {"etape": 3, "dates": {"3": iso(M - timedelta(hours=1))}, "crees_ig": {"3": {"h": "trois.prive_fictif"}}},
             "4": {"etape": 1, "dates": {"1": iso(M - timedelta(days=20))},
                   "verif_ig": {"1": {"h": "un.fictif", "le": iso(M - timedelta(hours=2)), "installe": True}}},
             "5": {"etape": 3, "dates": {"3": iso(M - timedelta(hours=1))}, "profils": {"3": iso(M)}},
             "6": {"etape": 2, "dates": {"2": iso(M - timedelta(hours=2))}}}
        out = sc.a_verifier(d, comptes, M, sortis=frozenset({"6"}))
        self.assertEqual([("3", 3, "trois.prive_fictif", 0.0, True), ("2", 2, "deux.fictif", 2.0, False)], out)


class FauxRegistre:
    def __init__(self):
        self.crees = []

    def owner_for_handle(self, h):
        return None

    def reserve(self, uid, hs):
        pass

    def created(self, uid, h, preuve):
        self.crees.append((uid, h))


class PassageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.d = {"42": {"prenom": "Fictive", "creatrice": "Sophie", "salon_id": "7", "etape": 2,
                         "dates": {"1": iso(M - timedelta(days=3)), "1_fait": iso(M - timedelta(days=2)),
                                   "2": iso(M - timedelta(hours=3))},
                         "donnes": {"3": {"handle": "trois.prive_fictif", "le": iso(M - timedelta(days=1)),
                                          "a_partir_de": iso(M + timedelta(days=1))}}}}
        self.examens = {"deux.fictif": NEUF, "trois.prive_fictif": LIBRE}
        self.valider = AsyncMock(side_effect=self._valider)
        self.registre = FauxRegistre()
        self.marquer = AsyncMock()
        self.admin = N(send=AsyncMock())

        def ecrire(d):
            self.d = deepcopy(d)
        import onboarding
        for patcher in (patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.d)),
                        patch.object(parcours, "_ecrire", side_effect=ecrire),
                        patch.object(parcours, "_comptes_ordonnes", side_effect=lambda u, fiche_p=None, onb=None: comptes(u, fiche_p)),
                        patch.object(parcours, "valider_etape", self.valider),
                        patch.object(parcours, "_retirer_bouton", AsyncMock()),
                        patch.dict(parcours._deps, {"marquer_etat": self.marquer}),
                        patch.object(onboarding, "_lire_etat", return_value={"clippers": {}}),
                        patch.object(onboarding.process_adapters, "store", return_value=self.registre),
                        patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": self.examens[h])),
                        patch.object(a, "actif", return_value=True),
                        patch.object(a, "vu_libre", return_value=False),
                        patch.dict(sc._deps, {"canal_admin": AsyncMock(return_value=self.admin)}),
                        patch.dict(sc._jour, {"jour": "", "n": 0})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = N(get_channel=lambda i: "salon-fictif" if i == 7 else None)

    async def _valider(self, salon, uid, n, par="", creation=False):
        self.d[uid].setdefault("profils", {})[str(n)] = iso(M)
        self.d[uid]["dates"][f"{n}_fait"] = iso(M)
        return True

    async def test_le_compte_ouvert_vu_cree_se_ferme_seul_et_le_compte_d_avance_est_retenu(self):
        bilan = await sc.passage(self.client, M)
        self.valider.assert_awaited_once()
        self.assertEqual(("salon-fictif", "42", 2), self.valider.await_args.args)
        self.assertEqual("rapidapi", self.valider.await_args.kwargs["par"])
        self.assertIn("compte 2 @deux.fictif vu sur Instagram, étape fermée", bilan[0])
        v3 = self.d["42"]["verif_ig"]["3"]
        self.assertEqual((sc.PAS_CREE, True), (v3["v"], v3["libre_vu"]))  # pas encore créé, vu libre (retenu pour la suite)
        self.admin.send.assert_awaited_once()
        # un tour plus tard, le compte 3 remis d'avance existe : noté vu, LOG à GOOD, sans fermer une étape pas encore ouverte
        self.examens["trois.prive_fictif"] = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": False, "abonnes": 150}
        bilan = await sc.passage(self.client, M + timedelta(hours=9))
        self.assertEqual("trois.prive_fictif", self.d["42"]["crees_ig"]["3"]["h"])
        self.assertIn(("42", "trois.prive_fictif"), self.registre.crees)
        self.marquer.assert_awaited_with("trois.prive_fictif", "GOOD")
        self.assertIn("son étape se fermera dès qu'elle s'ouvre", bilan[0])
        self.assertEqual(1, self.valider.await_count)
        # l'étape 3 s'ouvre : fermée sans nouvel appel à Instagram
        self.d["42"].update({"etape": 3})
        self.d["42"]["dates"]["3"] = iso(M + timedelta(days=1))
        appels = a.examen.await_count
        await sc.passage(self.client, M + timedelta(days=1, minutes=10))
        self.assertEqual(appels, a.examen.await_count)
        self.assertEqual(3, self.valider.await_args.args[2])

    async def test_le_compte_d_un_inconnu_est_dit_une_fois_et_plus_regarde(self):
        self.examens["deux.fictif"] = INSTALLE
        bilan = await sc.passage(self.client, M)
        self.assertIn("compte d'un inconnu", bilan[0])
        self.valider.assert_not_awaited()
        self.assertEqual([], [x for x in sc.a_verifier(self.d, comptes, M + timedelta(days=3)) if x[1] == 2])

    async def test_budget_et_reserve(self):
        with patch.object(sc, "PAR_TOUR", 1):
            await sc.passage(self.client, M)
        self.assertEqual(1, a.examen.await_count)
        import instagram_rapidapi as ig
        with patch.dict(ig._jour, {"restant": sc.RESERVE - 1}):
            self.assertEqual([], await sc.passage(self.client, M + timedelta(hours=5)))
        self.assertEqual(1, a.examen.await_count)

    async def test_le_bouton_juge_par_instagram(self):
        ok, msg = await sc.confirmer("42", 2, "deux.fictif")
        self.assertEqual((True, ""), (ok, msg))
        self.examens["deux.fictif"] = LIBRE
        ok, msg = await sc.confirmer("42", 2, "deux.fictif")
        self.assertFalse(ok)
        self.assertIn("Je ne vois pas encore `@deux.fictif` sur Instagram", msg)
        self.assertEqual(sc.PAS_CREE, self.d["42"]["verif_ig"]["2"]["v"])
        self.examens["deux.fictif"] = {"verdict": "inconnu"}
        ok, msg = await sc.confirmer("42", 2, "deux.fictif")
        self.assertIn("Instagram ne me répond pas", msg)
        with patch.object(sc, "GARDE_BOUTON", False):
            self.assertEqual((True, ""), await sc.confirmer("42", 2, "deux.fictif"))

    async def test_notre_panne_de_cle_ne_bloque_jamais_le_clipper(self):
        self.examens["deux.fictif"] = {"verdict": "inconnu"}
        sc.FICHIER.unlink(missing_ok=True)
        with patch.object(a, "cle_refusee", return_value=True):
            self.assertEqual((True, ""), await sc.confirmer("42", 2, "deux.fictif"))
        jour = sc._jour_paris(datetime.now(timezone.utc)).isoformat()
        self.assertEqual(1, sc._lire_stats()["jours"][jour]["boutons_sans_verif"])
        # le contrôle GitHub a répondu (même un doute) : ce n'est plus notre panne, le bouton attend Instagram
        self.examens["deux.fictif"] = {"verdict": "inconnu", "source": "github"}
        with patch.object(a, "cle_refusee", return_value=True):
            ok, _ = await sc.confirmer("42", 2, "deux.fictif")
        self.assertFalse(ok)
        # Instagram répond « libre » pendant que la clé marche : refusé, quelle que soit la panne d'avant
        self.examens["deux.fictif"] = LIBRE
        self.assertFalse((await sc.confirmer("42", 2, "deux.fictif"))[0])

    def test_branche_dans_le_parcours(self):
        source = Path(parcours.__file__).read_text(encoding="utf-8")
        self.assertIn("await suivi_creation.passage(client)", source)
        self.assertIn("await suivi_creation.relances(client)", source)
        self.assertIn("ok, refus = await suivi_creation.confirmer(self.uid, self.n, saisi)", source)
        self.assertIn("await suivi_creation.surveiller_cle()", source)
        self.assertIn("suivi_creation.ligne_digest(maintenant)", Path(parcours.__file__).with_name("bot_discord.py").read_text(encoding="utf-8"))


class RelancesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        base = {"prenom": "Fictive", "creatrice": "Sophie", "salon_id": "7"}
        self.d = {"42": {**base, "etape": 2, "dates": {"1": iso(M - timedelta(days=5)), "1_fait": iso(M - timedelta(days=4)),
                                                       "2": iso(M - timedelta(hours=30))},
                         "verif_ig": {"2": {"h": "deux.fictif", "v": sc.PAS_CREE, "le": iso(M)}}},
                  "43": {**base, "etape": 1, "dates": {"1": iso(M - timedelta(hours=30))},
                         "verif_ig": {"1": {"h": "un.fictif", "v": sc.PAS_CREE, "le": iso(M)}}}}
        self.salon = N(send=AsyncMock())

        def ecrire(d):
            self.d = deepcopy(d)
        import onboarding
        for patcher in (patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.d)),
                        patch.object(parcours, "_ecrire", side_effect=ecrire),
                        patch.object(parcours, "_comptes_ordonnes", side_effect=lambda u, fiche_p=None, onb=None: comptes(u, fiche_p)),
                        patch.object(onboarding, "_lire_etat", return_value={"clippers": {}}),
                        patch.dict(sc._deps, {"tl_de": lambda uid, c: "99"})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = N(get_channel=lambda i: self.salon if i == 7 else None)

    def test_qui_et_quand(self):
        out = sc.a_relancer(self.d, comptes, M)
        self.assertEqual([("42", 2, "deux.fictif", "clipper", 30.0)], out)      # le compte 1 a déjà sa règle (L6) : pas de relance
        out = sc.a_relancer(self.d, comptes, M + timedelta(hours=20))
        self.assertIn(("43", 1, "un.fictif", "tl", 50.0), out)

    async def test_une_fois_chacune_clipper_puis_tl(self):
        await sc.relances(self.client, M)
        self.assertIn("Ton compte 2 `@deux.fictif` n'existe pas encore sur Instagram", self.salon.send.await_args.args[0])
        await sc.relances(self.client, M + timedelta(hours=1))
        self.assertEqual(1, self.salon.send.await_count)
        await sc.relances(self.client, M + timedelta(hours=20))
        textes = [c.args[0] for c in self.salon.send.await_args_list]
        self.assertTrue(any("Hello <@99> ! Fictive n'a pas encore créé son compte 2" in t for t in textes))
        self.assertTrue(any("son compte 1 (`@un.fictif`)" in t for t in textes))
        n = self.salon.send.await_count
        await sc.relances(self.client, M + timedelta(days=3))
        self.assertEqual(n, self.salon.send.await_count)

    async def test_jamais_pour_un_compte_vu_cree(self):
        self.d["42"]["crees_ig"] = {"2": {"h": "deux.fictif"}}
        self.d["43"]["dates"]["1_fait"] = iso(M)
        self.assertEqual([], sc.a_relancer(self.d, comptes, M + timedelta(days=2)))


class CleTests(unittest.IsolatedAsyncioTestCase):
    def test_alertes_cle_refusee_puis_revenue(self):
        etat = {}
        self.assertIn("Clé RapidAPI de Railway refusée", sc.alertes_dues(etat, True, None, M)[0])
        self.assertEqual([], sc.alertes_dues(etat, True, None, M + timedelta(hours=2)))          # pas de répétition sous 6 h
        self.assertEqual(1, len(sc.alertes_dues(etat, True, None, M + timedelta(hours=6))))
        revenue = sc.alertes_dues(etat, False, None, M + timedelta(hours=7))
        self.assertIn("de nouveau acceptée (refusée depuis 2026-10-31 06:00 UTC)", revenue[0])
        self.assertEqual([], sc.alertes_dues(etat, False, None, M + timedelta(hours=8)))

    def test_alerte_quota_une_fois_par_jour(self):
        etat = {}
        self.assertEqual([], sc.alertes_dues(etat, False, sc.ALERTE_QUOTA, M))
        self.assertIn("Quota RapidAPI bas** : 4200 requêtes", sc.alertes_dues(etat, False, 4200, M)[0])
        self.assertEqual([], sc.alertes_dues(etat, False, 4100, M + timedelta(hours=3)))
        self.assertEqual(1, len(sc.alertes_dues(etat, False, 3000, M + timedelta(days=1))))

    async def test_surveiller_poste_au_salon_admin(self):
        import instagram_rapidapi as ig
        admin = N(send=AsyncMock())
        with patch.dict(sc._deps, {"canal_admin": AsyncMock(return_value=admin)}), patch.dict(sc._alertes, {}, clear=True), \
                patch.object(ig, "CLE", "fictive"), patch.object(a, "cle_refusee", return_value=True):
            await sc.surveiller_cle(M)
            await sc.surveiller_cle(M + timedelta(minutes=60))
        admin.send.assert_awaited_once()

    def test_ligne_du_matin(self):
        import instagram_rapidapi as ig
        sc.FICHIER.unlink(missing_ok=True)
        hier = M - timedelta(days=1)
        sc.compter("examens", 41, hier)
        sc.compter("crees", 3, hier)
        sc.compter("relances", 2, hier)
        sc.compter("examens", 5, M)                                     # aujourd'hui : pas dans la ligne d'hier
        with patch.object(a, "actif", return_value=True), patch.object(a, "cle_refusee", return_value=False), \
                patch.dict(ig._jour, {"restant": 33412}):
            ligne = sc.ligne_digest(M)
        self.assertTrue(ligne.startswith("🔑 **RapidAPI** : clé OK · 33 412 requêtes restantes"))
        self.assertIn("Hier : 41 @ regardé(s) · 3 compte(s) vu(s) créé(s) · 2 relance(s) clipper, 0 TL", ligne)
        with patch.object(a, "actif", return_value=True), patch.object(a, "cle_refusee", return_value=True):
            self.assertIn("⛔ clé de Railway refusée", sc.ligne_digest(M))


if __name__ == "__main__":
    unittest.main()
