"""30/10, 9 h 36 (Gaëtan : « Pour tous ceux qui n'ont pas encore terminé la création de leur compte, vérifie à la main s'ils ont bien
créé leur compte ou pas… ceux qui ne l'ont pas créé, envoie-leur leur arobase dans leur salon privé… l'arobas qui est bien
disponible »). Sans réseau, sans Discord, sans classeur."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arobase_libre as a
import onboarding
import parcours as p
import remise_arobases as r

MAINTENANT = datetime(2026, 10, 30, 6, 0, tzinfo=timezone.utc)
LIBRE = {"verdict": "libre"}
INSTALLE = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": False, "abonnes": 141, "publications": 1}
NEUF = {"verdict": "pris", "profil_lu": True, "neuf": True, "a_nous": False, "abonnes": 3, "publications": 0}
A_NOUS = {"verdict": "pris", "profil_lu": True, "neuf": False, "a_nous": True, "abonnes": 400, "publications": 12}


class DeciderTests(unittest.TestCase):
    def test_les_cas(self):
        cas = [((True, {}, False, False), (r.CREE, r.RIEN)),
               ((False, LIBRE, False, False), (r.PAS_CREE, r.DONNER)),
               ((False, LIBRE, True, False), (r.PAS_CREE, r.DONNER)),                 # déjà donné, toujours libre : redonné
               ((False, {"verdict": "inconnu"}, False, False), (r.DOUTE, r.RIEN)),     # jamais rien sur un doute
               ((False, A_NOUS, False, False), (r.CREE, r.RIEN)),
               ((False, NEUF, True, False), (r.CREE, r.RIEN)),                        # donné puis existant et neuf : le sien
               ((False, INSTALLE, True, True), (r.CREE, r.RIEN)),                     # vu libre par le bot, puis existant
               ((False, INSTALLE, True, False), (r.A_TRANCHER, r.RIEN)),              # déjà dans ses mains : jamais changé d'office
               ((False, NEUF, False, False), (r.A_TRANCHER, r.RIEN)),
               ((False, {"verdict": "pris", "profil_lu": False}, False, False), (r.A_TRANCHER, r.RIEN)),
               ((False, INSTALLE, False, False), (r.PRIS_INCONNU, r.VARIANTE))]
        for args, attendu in cas:
            self.assertEqual(attendu, r.decider(*args), args)

    def test_etat_du_log(self):
        for etat, cree in (("GOOD", True), ("BAN", True), ("Faire appel", True), ("à créer", False), ("A créer", False), ("", False)):
            self.assertEqual(cree, r.cree_selon_log(etat), etat)


class EcheancesTests(unittest.TestCase):
    def test_un_compte_toutes_les_48_h_apres_le_dernier_cree(self):
        hier = MAINTENANT - timedelta(hours=24)
        self.assertEqual([hier + timedelta(hours=48), hier + timedelta(hours=96)], r.echeances(hier, 2, MAINTENANT))
        self.assertEqual([MAINTENANT, MAINTENANT + timedelta(hours=48), MAINTENANT + timedelta(hours=96)],
                         r.echeances(None, 3, MAINTENANT))
        vieux = MAINTENANT - timedelta(days=9)
        self.assertEqual(MAINTENANT, r.echeances(vieux, 1, MAINTENANT)[0])


class MessageTests(unittest.TestCase):
    def test_message_lisible_et_complet(self):
        items = [(2, "deux.fictif", MAINTENANT, False), (3, "trois.prv_fictif", MAINTENANT + timedelta(hours=48), True)]
        t = r.message("<@42>", items, MAINTENANT)
        self.assertLess(len(t), 1990)
        self.assertIn("```\ndeux.fictif\n```", t)
        self.assertIn("```\ntrois.prv_fictif\n```", t)
        self.assertIn("Compte 2 · croissance** · aujourd'hui", t)
        self.assertIn("Compte 3 · privé** · à partir du 01/11 à 7 h (heure de Paris)", t)
        self.assertIn("Un compte toutes les 48 h", t)
        self.assertIn("ton e-mail et ton mot de passe", t)
        self.assertIn("passe-le en privé", t)
        self.assertNotIn("\n\n\n", t)


def fiche(**extra):
    return {"prenom": "Fictif", "creatrice": "Fictive", "salon_id": "7", "etape": 2, "ordre": "prive3",
            "dates": {"1": "2026-10-28T10:00:00+00:00", "1_fait": "2026-10-29T06:00:00+00:00"}, "messages": {"1": 1}, **extra}


class SuggestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_une_seule_suggestion_neuve_avec_preuve(self):
        import instagram_rapidapi as ig
        examens = {"deu.xfictif": dict(NEUF, a_nous=True)}
        with patch.object(ig, "variantes_instagram", return_value=["deu.xfictif", "deux_fictif", "deux.fictif1"]), \
                patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens.get(h, LIBRE))):
            self.assertEqual("deu.xfictif", await r._suggestion_creee("deux.fictif", "Fictive"))
        examens["deux_fictif"] = NEUF                                    # deux comptes neufs : on ne devine pas
        with patch.object(ig, "variantes_instagram", return_value=["deu.xfictif", "deux_fictif"]), \
                patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens.get(h, LIBRE))):
            self.assertEqual("", await r._suggestion_creee("deux.fictif", "Fictive"))
        with patch.object(ig, "variantes_instagram", return_value=["deu.xfictif"]), \
                patch.object(a, "examen", AsyncMock(return_value=NEUF)):        # neuf sans preuve : rien
            self.assertEqual("", await r._suggestion_creee("deux.fictif", "Fictive"))


class RemiseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.etat = {"42": fiche()}
        self.salon = N(send=AsyncMock())
        self.membre = N(id=42, mention="<@42>", bot=False, display_name="Fictif - Fictive")
        guild = N(get_member=lambda i: self.membre if i == 42 else None, get_channel=lambda i: self.salon if i == 7 else None)
        self.client = N(guilds=[guild])
        self.log = [{"handle": "un.fictif", "etat": "GOOD"}, {"handle": "deux.fictif", "etat": "à créer"},
                    {"handle": "trois.prv_fictif", "etat": "à créer"}]

        def ecrire(d):
            self.etat = deepcopy(d)
        for patcher in (patch.object(p, "_lire", side_effect=lambda: deepcopy(self.etat)),
                        patch.object(p, "_ecrire", side_effect=ecrire),
                        patch.object(p, "_onb", return_value={"acces": []}),
                        patch.object(p, "_comptes_ordonnes", return_value=["un.fictif", "deux.fictif", "trois.prv_fictif"]),
                        patch.dict(p._deps, {"est_staff": lambda m: False}),
                        patch.object(onboarding, "lire_comptes", AsyncMock(side_effect=lambda: deepcopy(self.log))),
                        patch.object(onboarding, "_lire_etat", return_value={"clippers": {}}),
                        patch.object(a, "vu_libre", return_value=False),
                        patch.object(r, "_suggestion_creee", AsyncMock(return_value="")),
                        patch.object(r, "_rapport", AsyncMock())):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_apercu_rien_envoye_rien_ecrit(self):
        with patch.object(a, "examen", AsyncMock(return_value=LIBRE)), \
                patch.object(r, "_suggestion_creee", AsyncMock(return_value="")):
            res = await r.remise(self.client, envoyer=False)
        self.salon.send.assert_not_awaited()
        self.assertNotIn("donnes", self.etat["42"])
        self.assertEqual(1, res["clippers"])
        self.assertEqual(["créé", "pas créé", "pas créé"], [l[10] for l in res["lignes"]])
        self.assertIn("compte 2 `deux.fictif`, compte 3 `trois.prv_fictif`", res["bilan"][0])

    async def test_envoi_un_message_avec_tous_ses_at_notes_dans_la_fiche(self):
        with patch.object(a, "examen", AsyncMock(return_value=LIBRE)), \
                patch.object(r, "_suggestion_creee", AsyncMock(return_value="")), \
                patch.object(r, "datetime", wraps=datetime) as dt:
            dt.now.return_value = MAINTENANT
            res = await r.remise(self.client, envoyer=True)
        self.salon.send.assert_awaited_once()
        texte = self.salon.send.await_args.args[0]
        self.assertIn("deux.fictif", texte)
        self.assertIn("trois.prv_fictif", texte)
        self.assertIn("Compte 2 · croissance** · à partir du 31/10", texte)        # 48 h après la création du compte 1
        self.assertEqual({"2", "3"}, set(self.etat["42"]["donnes"]))
        self.assertEqual("deux.fictif", self.etat["42"]["donnes"]["2"]["handle"])
        self.assertEqual(1, res["messages"])

    async def test_pris_par_un_inconnu_variante_ecrite_puis_donnee(self):
        examens = {"deux.fictif": INSTALLE, "trois.prv_fictif": LIBRE}
        renommer = AsyncMock(return_value=("deux.fictif", ""))
        with patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens[h])), \
                patch.object(a, "variante_libre", AsyncMock(return_value="deux_fictif")) as variante, \
                patch.object(p, "renommer", renommer):
            res = await r.remise(self.client, envoyer=True)
        renommer.assert_awaited_once_with("42", 2, "deux_fictif")
        self.assertIn("un.fictif", variante.await_args.kwargs["exclus"])
        texte = self.salon.send.await_args.args[0]
        self.assertIn("```\ndeux_fictif\n```", texte)
        self.assertNotIn("```\ndeux.fictif\n```", texte)
        self.assertEqual("deux_fictif", self.etat["42"]["donnes"]["2"]["handle"])
        self.assertEqual(r.PRIS_INCONNU, res["lignes"][1][10])

    async def test_en_apercu_la_variante_est_proposee_sans_renommer(self):
        examens = {"deux.fictif": INSTALLE, "trois.prv_fictif": LIBRE}
        with patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens[h])), \
                patch.object(a, "variante_libre", AsyncMock(return_value="deux_fictif")), \
                patch.object(p, "renommer", AsyncMock()) as renommer:
            res = await r.remise(self.client, envoyer=False)
        renommer.assert_not_awaited()
        self.assertEqual("deux_fictif", res["lignes"][1][12])

    async def test_un_compte_deja_cree_en_avance_n_est_pas_redonne(self):
        self.etat["42"]["messages"]["2"] = 1
        examens = {"deux.fictif": NEUF, "trois.prv_fictif": LIBRE}
        with patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens[h])):
            res = await r.remise(self.client, envoyer=True)
        texte = self.salon.send.await_args.args[0]
        self.assertNotIn("deux.fictif", texte)
        self.assertIn("trois.prv_fictif", texte)
        self.assertEqual(r.CREE, res["lignes"][1][10])

    async def test_cree_sous_une_suggestion_d_instagram(self):
        self.etat["42"]["messages"]["2"] = 1
        examens = {"deux.fictif": LIBRE, "trois.prv_fictif": LIBRE}
        with patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens[h])), \
                patch.object(r, "_suggestion_creee", AsyncMock(side_effect=lambda h, c: "deu.xfictif" if h == "deux.fictif" else "")):
            res = await r.remise(self.client, envoyer=True)
        self.assertNotIn("deux.fictif", self.salon.send.await_args.args[0])
        self.assertIn("deu.xfictif", res["lignes"][1][10])

    async def test_doute_rien_envoye_pour_ce_compte(self):
        examens = {"deux.fictif": {"verdict": "inconnu"}, "trois.prv_fictif": {"verdict": "inconnu"}}
        with patch.object(a, "examen", AsyncMock(side_effect=lambda h, c="": examens[h])):
            res = await r.remise(self.client, envoyer=True)
        self.salon.send.assert_not_awaited()
        self.assertEqual(0, res["clippers"])

    async def test_staff_sortis_et_absents_ignores(self):
        with patch.dict(p._deps, {"est_staff": lambda m: True}), patch.object(a, "examen", AsyncMock()) as examen:
            res = await r.remise(self.client, envoyer=True)
        examen.assert_not_awaited()
        self.assertEqual([], res["lignes"])
        with patch.object(onboarding, "_lire_etat", return_value={"clippers": {"42": {"sorti": True}}}), \
                patch.object(a, "examen", AsyncMock()) as examen:
            await r.remise(self.client, envoyer=True)
        examen.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    async def test_trois_comptes_crees_rien(self):
        self.etat["42"]["dates"].update({"2_fait": "x", "3_fait": "y"})
        with patch.object(a, "examen", AsyncMock()) as examen:
            res = await r.remise(self.client, envoyer=True)
        examen.assert_not_awaited()
        self.assertEqual([], res["lignes"])

    def test_resume(self):
        t = r.resume({"mode": "aperçu", "clippers": 1, "messages": 0, "bilan": ["• Fictif (Fictive) : compte 2 `x`"],
                      "lignes": [["F", "C", "2", "x", "", "", "", "", "", "", "pas créé", "donner", "x", "aperçu", ""]]})
        self.assertIn("rien envoyé", t)
        self.assertIn("pas créé : 1", t)
        self.assertIn("Remise des @", t)


class EtatDesComptesTests(unittest.TestCase):
    def test_l_assistant_sait_que_l_at_est_donne(self):
        f = fiche(donnes={"2": {"handle": "deux.fictif", "a_partir_de": "2026-10-31T06:00:00+00:00"}})
        with patch.object(p, "_lire", return_value={"42": f}), \
                patch.object(p, "_comptes_ordonnes", return_value=["un.fictif", "deux.fictif", "trois.prv_fictif"]), \
                patch.object(p, "_onb", return_value={"acces": []}):
            t = p.etat_des_comptes("42", maintenant=MAINTENANT)
            self.assertIn("son @ `deux.fictif` lui a été donné dans son salon perso", t)
            self.assertIn("à partir du 31/10 à 7 h (heure de Paris)", t)
            t2 = p.etat_des_comptes("42", maintenant=MAINTENANT + timedelta(days=2))
            self.assertIn("il le crée lui-même dès maintenant", t2)


if __name__ == "__main__":
    unittest.main()
