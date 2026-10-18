"""Aide staff et pièges de saisie vérifiés sur le code de production, hors réseau."""
import ast
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aide_commandes import ADMIN, ADMIN_TOUT, MANAGER


def extraire(fichier, noms, namespace):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    noeuds = [n for n in arbre.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name in noms]
    for noeud in noeuds:
        noeud.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=noeuds, type_ignores=[])), fichier, "exec"), namespace)
    return namespace


class AideStaffTests(unittest.TestCase):
    def aide(self, admin=False, manager=False, signe=False, tout=False):
        ns = {"est_manager": lambda _: manager, "est_signe": lambda _: signe,
              "lire_json": lambda *_: {}, "FICHIER_PIPELINE": "inutilise",
              "ETATS_A_MIGRER": (), "seuil_quiz_texte": lambda: "80 %"}
        return extraire("bot_discord.py", {"texte_aide"}, ns)["texte_aide"](SimpleNamespace(id=42), admin, tout)

    def test_affichage_selon_role_et_limite_discord(self):
        for admin, manager, signe in [(True, False, False), (False, True, False),
                                      (False, False, True), (False, False, False)]:
            with self.subTest(admin=admin, manager=manager, signe=signe):
                texte = self.aide(admin, manager, signe)
                self.assertLessEqual(len(texte.encode("utf-16-le")) // 2, 1990)
                self.assertIn("\n\n", texte)
                # 18/10 (Gaëtan : « simplifie ») : l'aide admin tient en un écran ; les diagnostics sont dans `!aide tout`
                self.assertEqual("!sortie" in texte, admin)
                self.assertEqual("!remettre-compte1" in texte, admin)
                self.assertEqual("!aide tout" in texte, admin)
                self.assertNotIn("!diagnostic-dossier", texte)
        tout = self.aide(admin=True, tout=True)
        for commande in ("!diagnostic-dossier", "!audit-discussions", "!rapprocher-zero", "!organisation"):
            self.assertIn(commande, tout)
        self.assertIn("!aide-ig suspension", self.aide(signe=True))
        self.assertIn("!quiz", self.aide())

    def test_commandes_annoncees_existent_dans_le_code(self):
        # Les constantes de dispatch sont lues sans importer le client Discord.
        connues = set()
        for fichier in ROOT.glob("*.py"):
            if fichier.name == "aide_commandes.py":
                continue
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            arbre.body = [n for n in arbre.body if getattr(n, "name", "") != "texte_aide"]
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                    if re.fullmatch(r"![\w-]+", noeud.value):
                        connues.add(noeud.value)
        annoncees = set(re.findall(r"`(![\w-]+)", ADMIN + ADMIN_TOUT + MANAGER))
        self.assertFalse(annoncees - connues, annoncees - connues)

    def test_manager_ne_recoit_pas_de_commandes_admin(self):
        arbre = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
        valeur = next(n.value for n in arbre.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "COMMANDES_MANAGER" for t in n.targets))
        autorisees = set(ast.literal_eval(valeur)) | {"!code"}  # relais contrôlé avant le dispatch staff
        self.assertLessEqual(set(re.findall(r"`(![\w-]+)", MANAGER)), autorisees)
        for commande in ("!audit", "!secu", "!tl", "!pilotage"):
            self.assertNotIn(commande, MANAGER)

    def test_syntaxe_et_limites_expliquees(self):
        for texte in (ADMIN, MANAGER):
            self.assertIn("Une commande par message", texte)
            self.assertNotIn("!sécurité", texte)
        self.assertIn("sélectionne la personne", MANAGER)
        self.assertIn("Un prénom suffit quand un seul membre le porte", ADMIN)
        self.assertIn("`!dashboard scan` lance un scan payant", MANAGER)
        self.assertIn("`!dashboard scan` = scan payant", ADMIN_TOUT)
        self.assertIn('`!onboarding @membre`', ADMIN_TOUT)
        self.assertLessEqual(len(ADMIN), 1300)


class SaisieEtRafaleTests(unittest.IsolatedAsyncioTestCase):
    def message(self, mentions=()):
        return SimpleNamespace(author=SimpleNamespace(id=42), mentions=list(mentions), reply=AsyncMock())

    async def test_mentions_rafale_filtrees_par_ligne(self):
        ns = extraire("bot_discord.py", {"_MessageRafale"}, {})
        membre = SimpleNamespace(id=73)
        autre = SimpleNamespace(id=74)
        msg = self.message([membre, autre])
        for ligne, attendus in [("!onboarding <@73> Chloé", [membre]),
                                ("!onboarding <@!74> Chloé", [autre]),
                                ("!onboarding @Prénom Chloé", [])]:
            self.assertEqual(ns["_MessageRafale"](msg, ligne).mentions, attendus)

    async def test_onboarding_refuse_un_prenom_ou_une_fausse_mention(self):
        livraison = AsyncMock()
        ns = extraire("onboarding.py", {"commande_staff"}, {"actif": lambda: True, "livrer": livraison})
        for texte in ("!onboarding Prénom", "!onboarding @Prénom", "!onboarding 73 Chloé"):
            msg = self.message()
            self.assertTrue(await ns["commande_staff"](msg, texte))
            self.assertIn("Format", msg.reply.call_args.args[0])
        livraison.assert_not_awaited()

    async def test_onboarding_mention_reelle_selectionne_le_membre(self):
        membre = SimpleNamespace(id=73)
        livraison = AsyncMock(return_value="Résultat fictif")
        ns = extraire("onboarding.py", {"commande_staff"}, {
            "actif": lambda: True, "livrer": livraison,
            "_deps": {"lire_json": lambda *_: {}, "FICHIER_EQUIPES": "inutilise", "salon_perso": lambda _: "salon-fictif"}})
        self.assertTrue(await ns["commande_staff"](self.message([membre]), "!onboarding <@73> Chloé"))
        self.assertEqual(livraison.await_args.args, (membre, "Chloé", "salon-fictif"))

    async def test_onboarding_sans_creatrice_utilise_affectation_existante(self):
        membre = SimpleNamespace(id=73)
        livraison = AsyncMock(return_value='Résultat fictif')
        registre = {'73': {'creatrice': 'Sarah'}}
        ns = extraire('onboarding.py', {'commande_staff'}, {
            'actif': lambda: True, 'livrer': livraison,
            '_deps': {'lire_json': lambda *_: registre, 'FICHIER_EQUIPES': 'inutilise', 'salon_perso': lambda _: 'salon-fictif'}})
        await ns['commande_staff'](self.message([membre]), '!onboarding <@73>')
        self.assertEqual(livraison.await_args.args, (membre, 'Sarah', 'salon-fictif'))
        registre.clear()
        message = self.message([membre])
        await ns['commande_staff'](message, '!onboarding <@73>')
        self.assertIn("d'abord", message.reply.call_args.args[0])
        self.assertIn('`!creatrice @clipper Chloé`', message.reply.call_args.args[0])
        self.assertEqual(1, livraison.await_count)

    async def test_rafale_continue_apres_echec_et_ne_route_pas_dashboard(self):
        commandes = AsyncMock(side_effect=[RuntimeError("échec fictif"), False, True])
        envoi = AsyncMock()
        ns = extraire("bot_discord.py", {"_MessageRafale", "executer_rafale"}, {
            "commande_admin": commandes, "envoyer_long": envoi, "journal": Mock()})
        msg = self.message()
        await ns["executer_rafale"](msg, ["!audit", "!dashboard", "!pipeline"])
        self.assertEqual([a.args[1] for a in commandes.await_args_list], ["!audit", "!dashboard", "!pipeline"])
        rapport = "\n".join(envoi.await_args.args[1])
        self.assertIn("échec fictif", rapport)
        self.assertIn("`!dashboard` : commande inconnue", rapport)

    async def test_dashboard_reconnu_seul_et_refuse_aux_non_staff(self):
        actif = Mock(return_value=False)
        ns = extraire("etats_comptes.py", {"commande_staff"}, {
            "_deps": {"est_staff": lambda _: True}, "onboarding": SimpleNamespace(actif=actif)})
        msg = self.message()
        self.assertTrue(await ns["commande_staff"](msg, "!dashboard"))
        self.assertIn("Classeur inactif", msg.reply.call_args.args[0])
        actif.reset_mock()
        ns["_deps"]["est_staff"] = lambda _: False
        self.assertTrue(await ns["commande_staff"](msg, "!dashboard scan"))
        self.assertIn("Réservé", msg.reply.call_args.args[0])
        actif.assert_not_called()


if __name__ == "__main__":
    unittest.main()
