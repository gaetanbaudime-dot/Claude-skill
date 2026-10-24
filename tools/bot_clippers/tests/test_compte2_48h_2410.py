"""24/10 (Gaëtan, 13 h 48) : le compte 2 part 48 h après l'envoi du compte 1 pour TOUS les clippers, sinon tout de suite ; les
comptes 2 et 3 portent leur e-mail et leur mot de passe (mêmes contrôles que le compte 1) ; Rianah reçoit les accès de ses comptes
2 et 3 dans chaque salon de clipping. Données fictives uniquement."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import identites_clipping
import onboarding
import parcours
import remise_compte1

MAINTENANT = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def il_y_a(h):
    return (MAINTENANT - timedelta(hours=h)).isoformat(timespec="seconds")


class ValeursCompte(unittest.TestCase):
    def ligne(self, **x):
        base = {"gerant": "Fictif", "creatrice": "Créa", "etat": "GOOD", "mail": "a@exemple.invalid", "mdp": secrets.token_hex(6)}
        base.update(x)
        return base

    def test_compte_existant_donne_ses_acces(self):
        ligne = self.ligne()
        self.assertEqual([ligne["mail"], ligne["mdp"]], remise_compte1.valeurs_compte(ligne, "fictif", "crea"))

    def test_refus_autre_gerant_autre_creatrice_ou_ban(self):
        for ligne, gerant in ((self.ligne(gerant="Autre"), "Fictif"), (self.ligne(creatrice="Autre"), "Fictif"),
                              (self.ligne(etat="BAN"), "Fictif"), (self.ligne(), ""), (self.ligne(mail="pas-un-mail"), "Fictif")):
            with self.assertRaises(remise_compte1.Retenue):
                remise_compte1.valeurs_compte(ligne, gerant, "Créa")


class AccesDansLEtape(unittest.IsolatedAsyncioTestCase):
    async def test_remplace_la_ligne_d_acces_quand_les_controles_passent(self):
        texte = f"Identifiant prévu : @fictif-deux\n\n{parcours.ACCES_A_CONFIRMER}\n\nCréé ? Appuie sur ✅."
        mdp = secrets.token_hex(6)
        with patch.object(parcours, "_comptes_ordonnes", return_value=["fictif-un", "fictif-deux"]), \
             patch.object(parcours, "_onb", return_value={"gerant": "Fictif"}), \
             patch.object(remise_compte1, "identifiants_compte", AsyncMock(return_value=("b@exemple.invalid", mdp))) as ident:
            sortie = await parcours._avec_acces(SimpleNamespace(guild=None), "42", 2, {"creatrice": "Créa"}, texte)
        self.assertIn(f"Mot de passe : `{mdp}`", sortie)
        self.assertNotIn(parcours.ACCES_A_CONFIRMER, sortie)
        self.assertEqual("fictif-deux", ident.await_args.args[3])
        self.assertEqual("inclus", parcours.ACCES_ETAPE[("42", 2)])

    async def test_garde_la_ligne_et_note_la_raison_sinon(self):
        texte = f"x\n\n{parcours.ACCES_A_CONFIRMER}"
        remise_compte1.RAISONS["43"] = "Un lecteur non autorisé peut accéder au salon"
        with patch.object(parcours, "_comptes_ordonnes", return_value=["fictif-un", "fictif-deux"]), \
             patch.object(parcours, "_onb", return_value={"gerant": "Fictif"}), \
             patch.object(remise_compte1, "identifiants_compte", AsyncMock(return_value=None)):
            sortie = await parcours._avec_acces(SimpleNamespace(guild=None), "43", 2, {}, texte)
        self.assertEqual(texte, sortie)
        self.assertIn("lecteur non autorisé", parcours.ACCES_ETAPE[("43", 2)])


class Compte2A48h(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        parcours._COMPTE1_LISTE["dite"] = False
        self.d = {
            "1": {"prenom": "Ancien", "etape": 1, "salon_id": "11", "dates": {"1": il_y_a(60)}, "messages": {"1": "5"}},
            "2": {"prenom": "Recent", "etape": 1, "salon_id": "12", "dates": {"1": il_y_a(10)}},
            "3": {"prenom": "Parti", "etape": 2, "salon_id": "13", "dates": {"1": il_y_a(90), "1_fait": il_y_a(80)}},
            "4": {"prenom": "Fait", "etape": 3, "salon_id": "14", "dates": {"1": il_y_a(99), "2": il_y_a(50)}},
            "5": {"prenom": "Confirme", "etape": 2, "salon_id": "15", "dates": {"1": il_y_a(49), "1_fait": il_y_a(47)},
                  "programme": [{"type": "etape", "n": 2, "quand": il_y_a(1)}]},
        }

    lignes = []

    async def passer(self, envoyer=True):
        d = self.d

        def ecrire(x):
            d.clear(); d.update(deepcopy(x))
        store = Mock()
        store.get.side_effect = lambda cle: {"motif": "fictif"} if cle == "sortie:3" else {}
        client = SimpleNamespace(get_channel=lambda i: SimpleNamespace(id=i, send=AsyncMock()))
        envoyer_etape = AsyncMock(return_value=envoyer)
        publier = AsyncMock()
        with patch.object(parcours, "_lire", side_effect=lambda: deepcopy(d)), \
             patch.object(parcours, "_ecrire", side_effect=ecrire), \
             patch.object(parcours, "envoyer_etape", envoyer_etape), \
             patch.object(parcours, "_envoyer_publier", publier), \
             patch.object(onboarding.process_adapters, "store", return_value=store), \
             patch.object(onboarding, "lire_comptes", AsyncMock(return_value=self.lignes)), \
             patch.object(parcours, "_comptes_ordonnes", side_effect=lambda uid, **_: [f"fictif-{uid}-1", f"fictif-{uid}-2"]), \
             patch.dict(parcours._deps, {"membre_par_id": lambda uid: SimpleNamespace(id=int(uid), mention=f"<@{uid}>"),
                                         "canal_admin": None}):
            faits = await parcours.forcer_comptes2(client, MAINTENANT)
        return faits, envoyer_etape, publier

    def test_au_compte_1_liste_du_plus_ancien_au_plus_recent(self):
        with patch.object(parcours, "SIMPLE_POUR_TOUS", False):         # la règle du 23/10 seule : « simple » lu sur la fiche
            liste = parcours.au_compte_1(self.d, MAINTENANT)
        self.assertEqual(["3", "1", "5", "2"], [u for u, *_ in liste])
        self.assertEqual((60.0, False, False), liste[1][2:])

    async def test_seuls_ceux_a_48h_et_plus_recoivent_leur_compte_2(self):
        faits, envoyer_etape, publier = await self.passer()
        self.assertEqual([("1", "etape", 2), ("5", "etape", 2)], faits)
        self.assertEqual(["1", "5"], [str(c.args[1].id) for c in envoyer_etape.await_args_list])
        self.assertTrue(all(c.args[2] == 2 for c in envoyer_etape.await_args_list))
        self.assertTrue(self.d["1"]["force_2"] and self.d["5"]["force_2"])
        self.assertNotIn("force_2", self.d["2"])                         # 10 h : il attend ses 48 h
        self.assertNotIn("force_2", self.d["3"])                         # départ enregistré
        # compte 1 jamais confirmé : « ton compte 1 peut publier » part d'abord, une fois ; le confirmé l'a déjà eu
        self.assertEqual([("1", 1)], [(str(c.args[1].id), c.args[3]) for c in publier.await_args_list])

    async def test_pas_de_second_essai_avant_30_minutes(self):
        await self.passer(envoyer=False)
        _, envoyer_etape, publier = await self.passer(envoyer=False)
        envoyer_etape.assert_not_awaited()
        publier.assert_not_awaited()

    @patch.object(parcours, "SIMPLE_POUR_TOUS", False)
    def test_sans_reels_vaut_pour_le_compte_2_force_seulement(self):
        self.assertTrue(parcours._sans_reels({"force_2": "x"}, 2))
        self.assertFalse(parcours._sans_reels({"force_2": "x"}, 3))
        self.assertTrue(parcours._sans_reels({"simple": "x"}, 3))
        self.assertFalse(parcours._sans_reels({}, 2))


class Compte1ConfirmeApres(unittest.IsolatedAsyncioTestCase):
    async def test_appui_tardif_sur_compte_1_cree_est_note(self):
        d = {"42": {"etape": 2, "force_2": "x", "dates": {"1": "a", "2": "b"}, "messages": {"1": "7"}}}

        def ecrire(x):
            d.clear(); d.update(deepcopy(x))
        with patch.object(parcours, "_lire", side_effect=lambda: deepcopy(d)), \
             patch.object(parcours, "_ecrire", side_effect=ecrire), \
             patch.object(parcours, "_retirer_bouton", AsyncMock()), \
             patch.object(parcours, "_classeur_etat", AsyncMock()) as classeur:
            self.assertTrue(await parcours.valider_etape(SimpleNamespace(), "42", 1, par="42", creation=True))
        self.assertTrue(d["42"]["dates"]["1_fait"])
        self.assertEqual(2, d["42"]["etape"])
        classeur.assert_awaited_once_with("42", 1)


class AccesDeRianah(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        remise_compte1.RAISONS.clear()
        pause = patch.object(identites_clipping, "PAUSE_CLASSEUR_S", 0)
        pause.start()
        self.addCleanup(pause.stop)
        self.mdp = {h: secrets.token_hex(6) for h in ("fictif-a1", "fictif-a2", "fictif-a3", "fictif-b1", "fictif-b2", "fictif-b3")}
        self.etat = {"clippers": {"42": {"lien_impose": "https://exemple.invalid/7", "telephones": {"Bêta": {
            "acces": [{"handle": "fictif-b1"}, {"handle": "fictif-b2"}, {"handle": "fictif-b3", "prive": True}],
            "donnes": 2, "dernier": "2020-01-01T00:00:00+00:00", "lien": "https://exemple.invalid/8", "remise_securisee": "x"}}}}}
        self.salons = {}

    async def remettre(self, creatrice, identifiants=True):
        etat = self.etat

        def ecrire(x):
            etat.clear(); etat.update(deepcopy(x))

        def salon(i):
            return self.salons.setdefault(int(i), SimpleNamespace(id=int(i), guild=guild, send=AsyncMock()))
        guild = SimpleNamespace(get_channel=salon)
        membre = SimpleNamespace(mention="<@42>", guild=guild)

        async def ident(g, s, uid, h, gerant, cre, *_):
            return (f"{h}@exemple.invalid", self.mdp[h]) if identifiants and gerant == f"Fictive Clipping {cre}" else None
        registre = {"42": {"salon_id": "100", "salons_clipping": {"Bêta": "200"}}}
        with patch.object(onboarding, "_lire_etat", side_effect=lambda: deepcopy(etat)), \
             patch.object(onboarding, "_ecrire_etat", side_effect=ecrire), \
             patch.object(parcours, "_lire", return_value={"42": {"salon_id": "100"}}), \
             patch.object(parcours, "_comptes_ordonnes", return_value=["fictif-a1", "fictif-a2", "fictif-a3"]), \
             patch.object(parcours, "mention_salon_codes", return_value="#codes"), \
             patch.object(remise_compte1, "identifiants_compte", side_effect=ident), \
             patch.dict(identites_clipping._deps, {"lire_json": lambda *_: registre, "FICHIER_EQUIPES": Path("/tmp/e.json")}):
            return await identites_clipping._remettre_acces("42", membre, "Fictive", creatrice, [2, 3], "Alpha")

    async def test_principale_dans_son_salon_le_prive_avec_son_lien(self):
        ligne = await self.remettre("Alpha")
        texte = self.salons[100].send.await_args.args[0]
        self.assertIn("**Compte 2 · @fictif-a2**", texte)
        self.assertIn(f"Mot de passe : `{self.mdp['fictif-a3']}`", texte)
        self.assertIn("Compte 3, le privé · @fictif-a3", texte)
        self.assertIn("Lien à mettre dans sa bio : https://exemple.invalid/7", texte)
        self.assertNotIn("fictif-a1", texte)
        self.assertNotIn(self.mdp["fictif-a2"], ligne)                   # jamais de secret au bilan
        self.assertIn("remis dans <#100>", ligne)

    async def test_autre_creatrice_dans_son_salon_de_clipping_comptes_notes_remis(self):
        ligne = await self.remettre("Bêta")
        texte = self.salons[200].send.await_args.args[0]
        self.assertIn("https://exemple.invalid/8", texte)
        t = self.etat["clippers"]["42"]["telephones"]["Bêta"]
        self.assertEqual(3, t["donnes"])
        self.assertNotIn("remise_securisee", t)
        self.assertIn("remis dans <#200>", ligne)

    async def test_controle_refuse_rien_n_est_envoye(self):
        ligne = await self.remettre("Bêta", identifiants=False)
        self.assertTrue(ligne.startswith("⚠️"))
        self.salons[200].send.assert_not_awaited()
        self.assertEqual(2, self.etat["clippers"]["42"]["telephones"]["Bêta"]["donnes"])


class LigneDAcces(unittest.TestCase):
    def test_le_texte_des_etapes_porte_la_ligne_remplacable(self):
        for n in (2, 3):
            self.assertIn(parcours.ACCES_A_CONFIRMER, parcours.ETAPES[n]["texte"])


class AccesDeRianahReprise(AccesDeRianah):
    test_principale_dans_son_salon_le_prive_avec_son_lien = None           # déjà joués par la classe mère
    test_autre_creatrice_dans_son_salon_de_clipping_comptes_notes_remis = None
    test_controle_refuse_rien_n_est_envoye = None

    async def test_deja_remis_ne_repart_pas(self):
        await self.remettre("Bêta")
        self.salons[200].send.reset_mock()
        ligne = await self.remettre("Bêta")
        self.assertTrue(ligne.startswith("= Bêta"))
        self.salons[200].send.assert_not_awaited()

    async def test_classeur_sature_le_depot_repart_au_demarrage_suivant(self):
        remise_compte1.RAISONS["42"] = "erreur technique (RuntimeError)"
        with self.assertRaises(identites_clipping.Passager):
            await self.remettre("Bêta", identifiants=False)
        self.assertNotIn("acces_remis", self.etat["clippers"]["42"])
        self.assertTrue(issubclass(identites_clipping.Passager, LookupError))   # demarrage ne le marque pas fait


class RelanceDesAcces(unittest.IsolatedAsyncioTestCase):
    async def passer(self, d, contenu=""):
        def ecrire(x):
            d.clear(); d.update(deepcopy(x))
        salon = SimpleNamespace(id=11, guild=None, send=AsyncMock(),
                                fetch_message=AsyncMock(return_value=SimpleNamespace(content=contenu)))
        client = SimpleNamespace(get_channel=lambda i: salon)
        mdp = secrets.token_hex(6)
        with patch.object(parcours, "_lire", side_effect=lambda: deepcopy(d)), \
             patch.object(parcours, "_ecrire", side_effect=ecrire), \
             patch.object(parcours, "_comptes_ordonnes", return_value=["fictif-un", "fictif-deux", "fictif-prive"]), \
             patch.object(parcours, "_onb", return_value={"gerant": "Fictif"}), \
             patch.object(parcours, "mention_salon_codes", return_value="#codes"), \
             patch.object(remise_compte1, "identifiants_compte", AsyncMock(return_value=("b@exemple.invalid", mdp))), \
             patch.dict(parcours._deps, {"membre_par_id": lambda uid: SimpleNamespace(mention=f"<@{uid}>")}):
            remis = await parcours.relancer_acces(client, MAINTENANT)
        return remis, salon, mdp

    async def test_compte_parti_sans_acces_les_recoit_ensuite(self):
        d = {"42": {"salon_id": "11", "dates": {"2": il_y_a(2)}, "messages": {"2": "9"}, "acces_etape": {"2": "a_remettre"}}}
        with patch.object(parcours, "ACCES_SUIVI_DEPUIS", il_y_a(24)):
            remis, salon, mdp = await self.passer(d)
        self.assertEqual([("42", 2)], remis)
        self.assertIn(f"Mot de passe : `{mdp}`", salon.send.await_args.args[0])
        self.assertIn("@fictif-deux", salon.send.await_args.args[0])
        self.assertEqual("remis", d["42"]["acces_etape"]["2"])

    async def test_envoi_d_avant_le_suivi_lu_une_fois_dans_discord(self):
        d = {"42": {"salon_id": "11", "dates": {"2": il_y_a(2)}, "messages": {"2": "9"}},
             "43": {"salon_id": "11", "dates": {"2": il_y_a(3)}, "messages": {"2": "8"}}}
        with patch.object(parcours, "ACCES_SUIVI_DEPUIS", il_y_a(24)):
            remis, salon, _ = await self.passer(d, contenu=f"x\n\n{parcours.ACCES_A_CONFIRMER}")
        self.assertEqual({("42", 2), ("43", 2)}, set(remis))
        with patch.object(parcours, "ACCES_SUIVI_DEPUIS", il_y_a(24)):
            remis, _, _ = await self.passer({"44": {"salon_id": "11", "dates": {"2": il_y_a(2)}, "messages": {"2": "7"}}},
                                            contenu="E-mail : `x`")
        self.assertEqual([], remis)

    async def test_envois_d_avant_le_24_ne_sont_pas_repris(self):
        d = {"42": {"salon_id": "11", "dates": {"2": il_y_a(100)}, "messages": {"2": "9"}, "acces_etape": {"2": "a_remettre"}}}
        with patch.object(parcours, "ACCES_SUIVI_DEPUIS", il_y_a(24)):
            remis, salon, _ = await self.passer(d)
        self.assertEqual([], remis)
        salon.send.assert_not_awaited()


class VeteransEtRetenus(Compte2A48h):
    test_au_compte_1_liste_du_plus_ancien_au_plus_recent = None
    test_seuls_ceux_a_48h_et_plus_recoivent_leur_compte_2 = None
    test_pas_de_second_essai_avant_30_minutes = None
    test_sans_reels_vaut_pour_le_compte_2_force_seulement = None

    async def test_compte_2_deja_en_service_depuis_longtemps_fiche_close(self):
        self.d["6"] = {"prenom": "Veteran", "etape": 2, "salon_id": "16", "dates": {"1": il_y_a(400)},
                       "programme": [{"type": "etape", "n": 2, "quand": il_y_a(1), "ligne": True}]}
        self.lignes = [{"handle": "fictif-6-2", "etat": "GOOD"}, {"handle": "fictif-1-2", "etat": "GOOD"}]
        faits, envoyer_etape, _ = await self.passer()
        self.assertNotIn("6", [str(c.args[1].id) for c in envoyer_etape.await_args_list])
        self.assertEqual("fictif-6-2", self.d["6"]["compte2_en_service"])
        self.assertEqual([], self.d["6"]["programme"])
        # 60 h : un compte existant confié à un nouveau part quand même (« Ce compte existe déjà »)
        self.assertIn("1", [str(c.args[1].id) for c in envoyer_etape.await_args_list])

    async def test_retenu_echu_repris_retenu_a_venir_laisse_au_programme(self):
        self.d["7"] = {"prenom": "Echu", "etape": 2, "salon_id": "17", "dates": {"1": il_y_a(200), "1_fait": "x"},
                       "programme": [{"type": "etape", "n": 2, "quand": il_y_a(5), "ligne": True}]}
        self.d["8"] = {"prenom": "AVenir", "etape": 2, "salon_id": "18", "dates": {"1": il_y_a(200), "1_fait": "x"},
                       "programme": [{"type": "etape", "n": 2, "quand": (MAINTENANT + timedelta(minutes=20)).isoformat(), "ligne": True}]}
        _, envoyer_etape, _ = await self.passer()
        partis = [str(c.args[1].id) for c in envoyer_etape.await_args_list]
        self.assertIn("7", partis)
        self.assertNotIn("8", partis)


class LigneProche(unittest.TestCase):
    TOUS = [{"handle": "fictif.un.deux", "gerant": "Fictif", "creatrice": "Créa"},
            {"handle": "journaldecrea_x", "gerant": "Fictif", "creatrice": "Créa"},
            {"handle": "fictifundeux", "gerant": "Autre", "creatrice": "Créa"},
            {"handle": "doublon1", "gerant": "Fictif", "creatrice": "Créa"},
            {"handle": "doublon2", "gerant": "Fictif", "creatrice": "Créa"}]

    def test_meme_squelette_puis_prefixe_parmi_ses_lignes_seulement(self):
        self.assertEqual(["fictif.un.deux"], [c["handle"] for c in remise_compte1.ligne_proche(self.TOUS, "fictifundeux", "Fictif", "Créa")])
        self.assertEqual(["journaldecrea_x"], [c["handle"] for c in remise_compte1.ligne_proche(self.TOUS, "journaldecrea", "Fictif", "Créa")])
        self.assertEqual(2, len(remise_compte1.ligne_proche(self.TOUS, "doublon", "Fictif", "Créa")))   # deux : rien n'est choisi
        self.assertEqual([], remise_compte1.ligne_proche(self.TOUS, "fictifundeux", "", "Créa"))


class IdentifiantsCompteRendLArobaseDuClasseur(unittest.IsolatedAsyncioTestCase):
    async def test_arobase_du_classeur_en_troisieme(self):
        mdp = secrets.token_hex(6)
        lignes = [{"handle": "fictif.un.deux", "gerant": "Fictif", "creatrice": "Créa", "etat": "à créer",
                   "mail": "x@exemple.invalid", "mdp": mdp}]
        with patch.object(remise_compte1, "verifier_lecteurs", Mock()), \
             patch.object(onboarding, "lire_comptes", AsyncMock(return_value=lignes)):
            acces = await remise_compte1.identifiants_compte(None, None, "42", "fictifundeux", "Fictif", "Créa", set(), None)
        self.assertEqual(("x@exemple.invalid", mdp, "fictif.un.deux"), acces)


class HistoriqueNonRapproche(Compte2A48h):
    test_au_compte_1_liste_du_plus_ancien_au_plus_recent = None
    test_seuls_ceux_a_48h_et_plus_recoivent_leur_compte_2 = None
    test_pas_de_second_essai_avant_30_minutes = None
    test_sans_reels_vaut_pour_le_compte_2_force_seulement = None

    def setUp(self):
        super().setUp()
        a_venir = (MAINTENANT + timedelta(minutes=25)).isoformat()
        retenue = {"n": 2, "raison": "Historique à vie non rapproché : allocation bloquée", "date": il_y_a(0)}
        self.d = {
            "9": {"prenom": "Nouveau", "etape": 2, "salon_id": "19", "dates": {"1": il_y_a(250), "1_fait": "x"}, "retenue": retenue,
                  "programme": [{"type": "etape", "n": 2, "quand": a_venir, "ligne": True}]},
            "10": {"prenom": "Ancien", "etape": 2, "salon_id": "20", "dates": {"1": il_y_a(400), "1_fait": "x"}, "retenue": retenue,
                   "programme": [{"type": "etape", "n": 2, "quand": a_venir, "ligne": True}]},
        }
        self.lignes = [{"handle": "fictif-9-2", "etat": "à créer"}, {"handle": "fictif-10-2", "etat": "GOOD"}]

    async def test_historique_repris_puis_compte_2_envoye_ancien_en_service_clos(self):
        with patch.object(parcours, "_reprendre_historique", return_value=True) as reprendre:
            _, envoyer_etape, _ = await self.passer()
        self.assertEqual(["9"], [str(c.args[1].id) for c in envoyer_etape.await_args_list])
        self.assertEqual(["9"], [c.args[0] for c in reprendre.call_args_list])
        self.assertEqual([], self.d["9"]["programme"])                  # l'essai part ici, plus au programme
        self.assertEqual("fictif-10-2", self.d["10"]["compte2_en_service"])

    async def test_historique_refuse_rien_ne_part(self):
        with patch.object(parcours, "_reprendre_historique", return_value=False):
            _, envoyer_etape, _ = await self.passer()
        envoyer_etape.assert_not_awaited()


class ReprendreHistorique(unittest.TestCase):
    def test_a_creer_compte_reserve_les_autres_incertains(self):
        import reprise_ancien
        with patch.object(reprise_ancien, "handles_connus", return_value=["fictif-a", "fictif-b"]), \
             patch.object(reprise_ancien, "reprendre", return_value={"comptes": 2}) as reprendre, \
             patch.object(onboarding, "_lire_etat", return_value={}), patch.object(parcours, "_lire", return_value={}), \
             patch.object(onboarding.process_adapters, "store", return_value=Mock()):
            ok = parcours._reprendre_historique("42", "Fictif", {"fictif-a": {"etat": "à créer"}, "fictif-b": {"etat": "GOOD"}})
        self.assertTrue(ok)
        self.assertEqual({"fictif-a"}, reprendre.call_args.args[4])
        self.assertEqual("bot (décision de Gaëtan, 24/10)", reprendre.call_args.args[3]["par"])
