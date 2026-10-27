"""27/10 : le @ réellement créé par un clipper suit partout (Mouhsinou : `x_y45` reçu, `x.y45` créé, invisible 4 jours).
Données fictives : aucun vrai @, e-mail, mot de passe ni identifiant Discord."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboarding as o  # noqa: E402
import parcours  # noqa: E402
import process_adapters  # noqa: E402
import rapprochement_mail as rm  # noqa: E402
import remise_compte1  # noqa: E402
import series  # noqa: E402
from process_store import Store  # noqa: E402

COMPTES = ["fictive_compte45", "deuxieme_vip", "troisieme_"]


# ------------------------------------------------------------------------------------------- 1. lire le @ écrit par le clipper
class PseudosEcritsTests(unittest.TestCase):
    def test_lien_instagram_avec_parametres(self):
        self.assertEqual([("fictive.compte45", "lien")],
                         parcours.pseudos_ecrits("https://www.instagram.com/fictive.compte45?vrfl=AbC==\nOui bien fait"))

    def test_mot_seul_sur_sa_ligne_et_arobase(self):
        self.assertEqual([("fictive.compte45", "mot")], parcours.pseudos_ecrits("C'est le même @ j'ai utilisé.\nfictive.compte45"))
        self.assertEqual([("fictive.compte45", "arobase")], parcours.pseudos_ecrits("mon compte est @fictive.compte45."))

    def test_e_mail_lien_drive_et_phrase_ignores(self):
        for texte in ("E-mail : alias_fictif.57@example.invalid", "https://drive.google.com/drive/folders/AbC_dEf",
                      "Mon code", "Compte 1 créé depuis 48h .", "<@123456789>"):
            self.assertEqual([], [h for h, _ in parcours.pseudos_ecrits(texte) if parcours.ecrase_pseudo(h) == "fictivecompte45"],
                             texte)

    def test_chemins_instagram_ne_sont_pas_des_comptes(self):
        self.assertEqual([], parcours.pseudos_ecrits("https://www.instagram.com/reel/AbC123/"))


class CorrespondancesTests(unittest.TestCase):
    def test_point_au_lieu_du_tiret_bas(self):
        self.assertEqual([(1, "fictive_compte45", "fictive.compte45", "lien")],
                         parcours.correspondances([("fictive.compte45", "lien")], COMPTES))

    def test_tiret_bas_final_retire(self):
        self.assertEqual([(3, "troisieme_", "troisi.eme", "mot")], parcours.correspondances([("troisi.eme", "mot")], COMPTES))

    def test_le_meme_at_ne_change_rien(self):
        self.assertEqual([], parcours.correspondances([("fictive_compte45", "mot")], COMPTES))

    def test_un_autre_compte_ou_un_at_sans_rapport_ne_change_rien(self):
        self.assertEqual([], parcours.correspondances([("autre.compte", "lien"), ("fictive_compte46", "lien")], COMPTES))

    def test_ambigu_entre_deux_comptes_ne_change_rien(self):
        self.assertEqual([], parcours.correspondances([("a.b", "lien")], ["a_b", "ab"]))

    def test_la_preuve_la_plus_forte_d_abord(self):
        ecrits = parcours.pseudos_ecrits("fictive_compte.45 et https://instagram.com/fictive.compte45")
        self.assertEqual((1, "fictive.compte45"), parcours.correspondances(ecrits, COMPTES)[0][:3:2])


# ------------------------------------------------------------------------------------------- 2. le salon perso corrige tout
class CapterPseudoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fiche = {"7": {"etape": 2, "salon_id": 99, "force_2": "2026-10-25T10:08:00+00:00",
                            "dates": {"1": "2026-10-23T10:07:00+00:00", "2": "2026-10-25T10:08:00+00:00"}}}
        self.patches = [patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.fiche)),
                        patch.object(parcours, "_ecrire", side_effect=lambda d: self.fiche.update(deepcopy(d))),
                        patch.object(parcours, "_comptes_ordonnes", side_effect=lambda uid, *a, **k: list(COMPTES))]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def message(self, texte):
        return N(author=N(id=7), channel=N(id=99), content=texte, reply=AsyncMock())

    async def test_lien_corrige_le_compte_1_et_le_note_cree_en_retard(self):
        msg = self.message("https://www.instagram.com/fictive.compte45?vrfl=x")
        with patch.object(parcours, "renommer", AsyncMock(return_value=("fictive_compte45", ""))) as ren, \
                patch.object(parcours, "valider_etape", AsyncMock(return_value=True)) as val:
            self.assertTrue(await parcours.capter_pseudo(msg, msg.content))
        ren.assert_awaited_once_with("7", 1, "fictive.compte45")
        val.assert_awaited_once()                                       # compte 1 dépassé (compte 2 parti à 48 h) : noté créé
        self.assertEqual(1, val.await_args.args[2])
        self.assertIn("ton compte 1 est `fictive.compte45`", msg.reply.await_args.args[0])

    async def test_mot_seul_sur_l_etape_en_cours_renomme_sans_valider(self):
        self.fiche["7"]["etape"] = 1
        msg = self.message("fictive.compte45")
        with patch.object(parcours, "renommer", AsyncMock(return_value=("fictive_compte45", ""))), \
                patch.object(parcours, "valider_etape", AsyncMock(return_value=True)) as val:
            self.assertTrue(await parcours.capter_pseudo(msg, msg.content))
        val.assert_not_awaited()                                        # le bouton reste à lui : un mot ne prouve pas la création

    async def test_rien_d_ecrit_ou_renommage_refuse_laisse_l_assistant_repondre(self):
        msg = self.message("Ok c'est compris.")
        self.assertFalse(await parcours.capter_pseudo(msg, msg.content))
        msg = self.message("fictive.compte45")
        with patch.object(parcours, "renommer", AsyncMock(return_value=("fictive_compte45", "cet identifiant est déjà dans le "
                                                                                              "classeur de l'agence"))):
            self.assertFalse(await parcours.capter_pseudo(msg, msg.content))
        msg.reply.assert_not_awaited()

    async def test_interrupteur(self):
        msg = self.message("fictive.compte45")
        with patch.dict("os.environ", {"CAPTER_PSEUDOS": "0"}), patch.object(parcours, "renommer", AsyncMock()) as ren:
            self.assertFalse(await parcours.capter_pseudo(msg, msg.content))
        ren.assert_not_awaited()

    async def test_rattrapage_lit_l_historique_une_seule_fois(self):
        anciens = [N(author=N(id=7), content="fictive.compte45"), N(author=N(id=8), content="troisi.eme"),
                   N(author=N(id=7), content="https://www.instagram.com/fictive.compte45?vrfl=x")]

        async def histoire(limit=None):
            for m in anciens:
                yield m
        salon = N(id=99, history=histoire)
        client = N(wait_until_ready=AsyncMock(), get_channel=lambda i: salon if i == 99 else None)
        with patch.object(parcours, "renommer", AsyncMock(return_value=("fictive_compte45", ""))) as ren, \
                patch.object(parcours, "valider_etape", AsyncMock(return_value=True)), \
                patch.object(parcours.asyncio, "sleep", AsyncMock()):
            faits = await parcours.rattraper_pseudos(client)
            self.assertEqual([("7", 1, "fictive_compte45", "fictive.compte45")], faits)
            ren.assert_awaited_once_with("7", 1, "fictive.compte45")   # l'autre membre (8) n'est jamais lu comme le clipper
            self.assertTrue(self.fiche["7"].get("pseudos_rattrapes"))
            self.assertEqual([], await parcours.rattraper_pseudos(client))
        self.assertEqual(1, ren.await_count)


class TextesTests(unittest.IsolatedAsyncioTestCase):
    def test_compte_1_dit_d_ecrire_le_at_exact(self):
        texte = remise_compte1.modele("<@42>", "compte_fictif", "fictif@example.invalid", "MDP_FICTIF", codes="<#555>",
                                      suite=parcours.LIGNE_48H)
        self.assertIn(remise_compte1.PSEUDO_CHANGE, texte)
        self.assertTrue(texte.endswith(parcours.LIGNE_48H))
        self.assertLess(texte.index("3️⃣"), texte.index("4️⃣"))

    def test_plus_d_invitation_a_changer_le_at_soi_meme(self):
        self.assertNotIn("Ajoute un chiffre", parcours.PSEUDO_PRIS)
        self.assertIn("Garde-le", parcours.PSEUDO_PRIS)

    async def test_fenetre_du_bouton_jamais_preremplie(self):
        with patch.object(parcours, "_prevu_pris", return_value=False):
            fenetre = parcours.ModalPseudo("7", 1, "fictive_compte45")
        self.assertIsNone(fenetre.champ.default)
        self.assertLessEqual(len(fenetre.champ.label), 45)


# ------------------------------------------------------------------------------------------- 3. fiche ↔ classeur par l'e-mail
def ligne(handle, mail, etat="GOOD", gerant="Fictif", onglet="Fictive", n=2):
    return {"handle": handle, "mail": mail, "etat": etat, "gerant": gerant, "onglet": onglet, "ligne": n}


def fiche(*acces, gerant="Fictif"):
    return {"gerant": gerant, "comptes": [a[0] for a in acces], "acces": [{"handle": h, "mail": m} for h, m in acces]}


class EcartsTests(unittest.TestCase):
    def test_meme_at_rien(self):
        self.assertEqual([], rm.ecarts({"1": fiche(("a_b", "a@x.invalid"))}, [ligne("a_b", "a@x.invalid")]))

    def test_ligne_qui_existe_sous_un_autre_at(self):
        e = rm.ecarts({"1": fiche(("prevu", "a@x.invalid"))}, [ligne("prevu_c", "A@X.invalid")])[0]
        self.assertEqual(("existe", 1, "prevu", "prevu_c"), (e["type"], e["n"], e["fiche"], e["classeur"]))
        self.assertTrue(rm.a_suivre(e))

    def test_ligne_a_creer_a_trancher(self):
        e = rm.ecarts({"1": fiche(("x", "z@x.invalid"), ("recu", "a@x.invalid"))},
                      [ligne("x", "z@x.invalid"), ligne("autre", "a@x.invalid", etat="à créer")])[0]
        self.assertEqual(("a_creer", 2), (e["type"], e["n"]))
        self.assertFalse(rm.a_suivre(e))

    def test_ligne_reattribuee_jamais_suivie(self):
        e = rm.ecarts({"1": fiche(("prevu", "a@x.invalid"))}, [ligne("prevu_c", "a@x.invalid", gerant="Quelquun")])[0]
        self.assertFalse(rm.a_suivre(e))

    def test_e_mail_en_double_tranche_par_le_gerant(self):
        lignes = [ligne("prevu", "a@x.invalid", gerant=""), ligne("vrai", "a@x.invalid", gerant="Fictif")]
        e = rm.ecarts({"1": fiche(("prevu", "a@x.invalid"))}, lignes)[0]
        self.assertEqual(("existe", "vrai"), (e["type"], e["classeur"]))

    def test_absente_ambigue_et_fiche_sortie(self):
        self.assertEqual("absente", rm.ecarts({"1": fiche(("p", "a@x.invalid"))}, [])[0]["type"])
        double = [ligne("u", "a@x.invalid", gerant="Fictif"), ligne("v", "a@x.invalid", gerant="Fictif")]
        self.assertEqual("ambigue", rm.ecarts({"1": fiche(("p", "a@x.invalid"))}, double)[0]["type"])
        sortie = dict(fiche(("p", "a@x.invalid")), sorti=True)
        self.assertEqual([], rm.ecarts({"1": sortie}, [ligne("q", "a@x.invalid")]))


class PasserTests(unittest.IsolatedAsyncioTestCase):
    async def test_aligne_signale_et_ne_repete_pas(self):
        fiches = {"1": fiche(("prevu", "a@x.invalid"), ("recu", "b@x.invalid"))}
        comptes = [ligne("prevu_c", "a@x.invalid"), ligne("autre", "b@x.invalid", etat="à créer")]
        onb = N(actif=lambda: True, lire_comptes=AsyncMock(return_value=comptes), _lire_etat=lambda: {"clippers": fiches},
                _cle_handle=lambda h: str(h or "").strip().lstrip("@").lower(), suivre_classeur=AsyncMock(return_value=""))
        admin, memo = AsyncMock(), {}
        args = dict(admin=admin, lire_json=lambda f, d: dict(memo), ecrire_json=lambda f, d: memo.update(d), fichier="memo")
        bilan = await rm.passer(onb, **args)
        self.assertEqual((2, 1, 1), (bilan["ecarts"], bilan["suivis"], bilan["a_trancher"]))
        onb.suivre_classeur.assert_awaited_once_with("1", "prevu", "prevu_c")
        texte = admin.await_args.args[0]
        self.assertIn("`prevu` → `prevu_c`", texte)
        self.assertIn("!pseudo @Fictif 2 <son @>", texte)
        onb.suivre_classeur.return_value = "c'est déjà cet identifiant"   # 2e passage : plus rien de neuf
        comptes[0]["handle"] = "prevu"
        await rm.passer(onb, **args)
        self.assertEqual(1, admin.await_count, "la même liste à trancher n'est pas reposée")

    async def test_interrupteur(self):
        onb = N(actif=lambda: True, lire_comptes=AsyncMock())
        with patch.object(rm, "ACTIF", False):
            await rm.passer(onb)
        onb.lire_comptes.assert_not_awaited()


class SuivreClasseurTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "p.sqlite3")
        self.data = {"clippers": {"42": {"comptes": ["ancien"], "acces": [{"handle": "ancien", "mail": "a@x.invalid"}]}},
                     "livres": {"ancien": {"uid": "42"}}}
        self.parcours = {"42": {"reels": {"ancien": {"n": 3}}}}

        def ecrire(d):
            self.data = deepcopy(d)

        def ecrire_p(d):
            self.parcours = deepcopy(d)
        for p in (patch.object(process_adapters, "store", return_value=self.store),
                  patch.object(o, "_lire_etat", side_effect=lambda: deepcopy(self.data)),
                  patch.object(o, "_ecrire_etat", side_effect=ecrire),
                  patch.object(o, "_proprietaires", side_effect=lambda: {"ancien": {"42"}}),
                  patch.object(series, "renommer"),
                  patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.parcours)),
                  patch.object(parcours, "_ecrire", side_effect=ecrire_p)):
            p.start()
            self.addCleanup(p.stop)

    async def test_la_fiche_suit_le_classeur_sans_ecrire_le_classeur(self):
        with patch.object(o.google_api, "sheets_ecrire", AsyncMock()) as ecrit:
            self.assertEqual("", await o.suivre_classeur("42", "ancien", "Nouveau_C"))
        ecrit.assert_not_awaited()
        f = self.data["clippers"]["42"]
        self.assertEqual(["nouveau_c"], f["comptes"])
        self.assertEqual("nouveau_c", f["acces"][0]["handle"])
        self.assertIn("nouveau_c", self.data["livres"])
        self.assertIn("nouveau_c", self.parcours["42"]["reels"])
        self.assertEqual("42", self.store.owner_for_handle("nouveau_c"))

    async def test_jamais_le_compte_d_un_autre(self):
        with patch.object(o, "_proprietaires", return_value={"ancien": {"42"}, "nouveau_c": {"43"}}):
            self.assertTrue(await o.suivre_classeur("42", "ancien", "nouveau_c"))
        self.assertEqual(["ancien"], self.data["clippers"]["42"]["comptes"])

    async def test_compte_hors_fiche_ou_dossier_sorti(self):
        self.assertTrue(await o.suivre_classeur("42", "inconnu", "nouveau_c"))
        self.data["clippers"]["42"]["sorti"] = True
        self.assertTrue(await o.suivre_classeur("42", "ancien", "nouveau_c"))


class PreuveMailEtapeDepasseeTests(unittest.TestCase):
    """27/10 : le mail d'Instagram qui salue un compte d'une étape déjà dépassée (compte 2 parti à 48 h) compte aussi."""
    def proprietaire(self, fiche_p):
        import ast
        src = (Path(__file__).resolve().parents[1] / "bot_discord.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "proprietaire_compte_alias")
        ns = {"destinataire_alias_code": lambda a: {"membre": N(id=7, display_name="Fictif")},
              "_adresses_codes_fiche": lambda uid, avec_comptes=False: {"a@x.invalid": "fictive_compte45"},
              "parcours": N(_lire=lambda: {"7": fiche_p}, _onb=lambda uid: {"acces": []}, _cree=parcours._cree,
                            _comptes_ordonnes=lambda uid, onb, f: list(COMPTES)),
              "onboarding": o}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), "bot_discord.py", "exec"), ns)
        return ns["proprietaire_compte_alias"]("a@x.invalid")

    def test_etape_depassee_pas_notee_creee(self):
        info = self.proprietaire({"etape": 2, "dates": {"1": "2026-10-23T10:07:00+00:00", "2": "2026-10-25T10:08:00+00:00"}})
        self.assertEqual((1, False), (info["n"], info["cree"]))

    def test_etape_depassee_deja_creee_ou_etape_future(self):
        self.assertIsNone(self.proprietaire({"etape": 2, "dates": {"1": "x", "1_fait": "y", "2": "z"}}))
        self.assertIsNone(self.proprietaire({"etape": 0, "dates": {}}))


class PreuveMailSilenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_etape_depassee_sans_changement_ne_reveille_pas_le_salon_admin(self):
        import preuve_mail
        from datetime import datetime, timezone
        quand = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
        for courant, attendu in ((False, 0), (True, 1)):
            admin, memo = AsyncMock(), {}
            info = {"uid": "7", "n": 1, "handle": "fictive_compte45", "ouverte": "2026-10-23T10:07:00+00:00", "cree": False,
                    "recycle": False, "courant": courant, "prenom": "Fictif"}
            preuve_mail.configurer({"lire_json": lambda f, d: dict(memo), "ecrire_json": lambda f, d: memo.update(d),
                                    "FICHIER": "memo", "proprietaire": lambda a: info, "renommer": AsyncMock(return_value=("", "")),
                                    "fermer": AsyncMock(return_value=False), "admin": admin})
            await preuve_mail.traiter("a@x.invalid", "fictive_compte45", quand)
            self.assertEqual(attendu, admin.await_count, f"courant={courant}")


if __name__ == "__main__":
    unittest.main()
