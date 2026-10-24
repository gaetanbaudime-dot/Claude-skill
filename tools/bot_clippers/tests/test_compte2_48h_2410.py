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
