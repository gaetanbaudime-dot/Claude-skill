"""Consignes réellement transmises au modèle, avec fichiers et services fictifs."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def charger(fichier, noms, ns):
    arbre = ast.parse((ROOT / fichier).read_text(encoding="utf-8"))
    noeuds = [n for n in arbre.body if
              (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms)
              or (isinstance(n, ast.Assign) and any(
                  isinstance(t, ast.Name) and t.id in noms for t in n.targets))]
    exec(compile(ast.Module(body=noeuds, type_ignores=[]), fichier, "exec"), ns)
    return ns


class ConsignesModele(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        dossier = Path(self.tmp.name)
        self.base = dossier / "connaissances.md"
        self.base.write_text((ROOT / "connaissances.md").read_text(encoding="utf-8"), encoding="utf-8")
        self.ajouts, self.faq = dossier / "ajouts.md", dossier / "faq.md"
        regle = charger("parcours.py", {"regle_comptes"}, {})["regle_comptes"]()
        self.client = Mock()
        self.client.messages.create.return_value = N(usage=None)
        self.ns = charger("bot_discord.py", {
            "INSTRUCTIONS", "_connaissances", "connaissances", "bloc_systeme", "_appel_modele"}, {
            "NOM_BOT": "Assistant fictif", "MESSAGE_ESCALADE": "Demande au manager.",
            "REGLE_CODES": "Codes fictifs", "TEXTE_CODE": "Aide fictive",
            "TEXTE_COMPTES": regle, "WHATSAPP_GAETAN_URL": "",
            "FICHIER_CONNAISSANCES": self.base, "FICHIER_AJOUTS": self.ajouts,
            "FICHIER_FAQ_APPRISE": self.faq, "journal": logging.getLogger("test.consignes"),
            "regle_lien_assistant": lambda: "", "regle_liens_formation": lambda: "",
            "ligne_facturation": lambda: "", "retro": N(consignes_texte=lambda: ""),
            "MODELE": "modele-fictif", "MAX_TOKENS_REPONSE": 100,
            "MAX_TOKENS_ASSISTANT": 200, "EFFORT_ASSISTANT": "low",
            "claude": self.client, "compter_usage": Mock(),
        })

    def prompt_envoye(self, modele="modele-fictif", question="Quand arrive le compte suivant ?"):
        messages = [{"role": "user", "content": question}]
        self.ns["_appel_modele"](messages, modele)
        appel = self.client.messages.create.call_args.kwargs
        self.assertEqual(messages, appel["messages"])
        self.assertEqual(modele, appel["model"])
        self.assertEqual({"type": "ephemeral", "ttl": "1h"}, appel["system"][0]["cache_control"])
        return appel["system"][0]["text"]

    def test_regles_comptes_dans_les_deux_appels_modele(self):
        for modele in ("modele-fictif", "assistant-fictif"):
            with self.subTest(modele=modele):
                texte = self.prompt_envoye(modele)
                self.assertIn(self.base.read_text(encoding="utf-8"), texte)
                self.assertIn("4 Reels vérifiés sur le compte 1 ouvrent le compte 2", texte)
                self.assertIn("4 Reels vérifiés sur le compte 2 ouvrent le compte 3 privé", texte)
                self.assertIn("3 comptes créés maximum à vie, sans remplacement", texte)
                self.assertIn("Metricool ne remet pas le compteur à zéro", texte)
                self.assertIn("Un deuxième téléphone n'autorise aucun compte supplémentaire", texte)
                self.assertIn("Un compte supprimé, banni ou transféré sur Metricool reste compté", texte)
                self.assertNotRegex(texte, r"au plus tôt 48\s*h|48\s*h et (?:4 )?Reels|4 (?:Reels )?de plus")
                self.assertNotIn("On recrée alors des comptes neufs", texte)
                self.assertNotIn("3 comptes de plus", texte)

    def test_pseudo_identique_dans_instruction_et_base(self):
        texte = self.prompt_envoye()
        instruction = texte.split("# BASE DE CONNAISSANCES", 1)[0]
        base = texte.split("# BASE DE CONNAISSANCES", 1)[1]
        self.assertIn("pseudo du classeur Sheets reste strictement identique", instruction)
        self.assertIn("signaler le refus dans le salon perso, sans modifier le pseudo", instruction)
        self.assertIn("Le pseudo Sheets reste strictement identique", base)
        self.assertIn("signale le refus dans ton salon perso", base)
        self.assertNotIn("choisir une variante disponible", texte)
        self.assertNotIn("pseudo plus un chiffre ou un point", texte)
        self.assertNotIn("il met le classeur à jour tout seul", texte)

    def test_disponibilite_warmup_sortie_et_remuneration_preserves(self):
        texte = self.prompt_envoye()
        for consigne in (
            "Un palier atteint ne contourne aucune vérification de disponibilité",
            "24 h de warm-up", "Ton compte 1 doit être créé dans les 48 h",
            "48 h pour répondre", "0,05 $ par visite réelle, francophone",
        ):
            self.assertIn(consigne, texte)

    def test_accueil_sans_confirmation_whatsapp_dans_les_deux_modeles(self):
        for modele in ("modele-fictif", "assistant-fictif"):
            with self.subTest(modele=modele):
                texte = self.prompt_envoye(modele, "Dois-je écrire sur WhatsApp avant mon compte 1 ?")
                self.assertIn("Aucune confirmation WhatsApp n'est requise", texte)
                self.assertIn("Aucun bouton WhatsApp n'est obligatoire", texte)
                self.assertIn("Gaëtan", texte)
                self.assertIn("sur WhatsApp, pour un blocage : demande-moi le lien", texte)
                for ancien in (
                    "J'ai écrit à Gaëtan", "Appuie sur ✅ quand tu as écrit à Gaëtan",
                    "Écris à Gaëtan avec ce bouton", "le bouton WhatsApp de ton message de bienvenue",
                    "Le groupe WhatsApp dès ton arrivée", "Ton groupe WhatsApp (dès ton arrivée)",
                    "le lien de ses vidéos et le groupe WhatsApp, dans un seul message",
                ):
                    self.assertNotIn(ancien, texte)

    def test_comptes_neufs_et_reconnexion_a_son_propre_compte(self):
        for modele in ("modele-fictif", "assistant-fictif"):
            with self.subTest(modele=modele):
                texte = self.prompt_envoye(modele, "Est-ce le compte d'un ancien clippeur ?")
                self.assertIn("Seuls des comptes neufs sont attribués", texte)
                self.assertIn("Aucun compte ancien n'est réattribué", texte)
                self.assertIn("Si tu as déjà créé ton propre compte, reconnecte-toi", texte)
                self.assertIn("3 comptes créés maximum à vie, sans remplacement", texte)
                self.assertIn("Le pseudo Sheets reste strictement identique", texte)
                self.assertNotIn("rendu par un ancien clipper", texte)
                self.assertNotIn("Un compte « qui existe déjà » dans ton étape", texte)

    def test_compte_1_apres_attribution_et_roles_sans_presumer_la_remise(self):
        for modele in ("modele-fictif", "assistant-fictif"):
            with self.subTest(modele=modele):
                texte = self.prompt_envoye(modele, "Ma créatrice est attribuée. Ai-je déjà reçu mes accès ?")
                instruction, base = texte.split("# BASE DE CONNAISSANCES", 1)
                for partie in (instruction, base):
                    self.assertIn("après attribution et confirmation des rôles", partie)
                    self.assertIn("Une réservation Sheets ne prouve pas la remise", partie)
                    self.assertIn("Ne confirme jamais la remise sans preuve d'envoi réussi", partie)
                self.assertIn("Un palier atteint ne contourne aucune vérification de disponibilité", texte)
                for ancien in (
                    "Le compte 1 est disponible immédiatement",
                    "Le compte 1 arrive juste sous la bienvenue, sans attendre",
                    "ton compte 1 arrive tout de suite sous ton message de bienvenue",
                    "Tout de suite, juste en dessous de ton message de bienvenue",
                ):
                    self.assertNotIn(ancien, texte)

    def test_identifiants_sheets_remis_par_le_flux_autorise_sans_divulgation(self):
        for modele in ("modele-fictif", "assistant-fictif"):
            with self.subTest(modele=modele):
                texte = self.prompt_envoye(modele, "Qui me donne mes identifiants ?")
                self.assertIn("identifiants préparés dans Sheets", texte)
                self.assertIn("remis sans modification par le flux bot autorisé", texte)
                self.assertIn("L'assistant ne recopie jamais les mots de passe", texte)
                self.assertIn("Jamais d'identifiant, de mot de passe ni de lien perso dans #assistant", texte)
                self.assertIn("Ne transmettre aucun secret ni document d'identité dans la demande d'aide", texte)
                self.assertNotIn("Gaëtan n'envoie pas d'identifiants", texte)

    def test_ajouts_faq_et_consignes_staff_restent_injectes_dans_le_meme_ordre(self):
        self.ajouts.write_text("AJOUT_FICTIF_PRIORITAIRE", encoding="utf-8")
        self.faq.write_text("FAQ_FICTIVE_SECONDAIRE", encoding="utf-8")
        self.ns["retro"] = N(consignes_texte=lambda: "CONSIGNE_STAFF_FICTIVE")
        texte = self.prompt_envoye()
        self.assertLess(texte.index("CONSIGNE_STAFF_FICTIVE"), texte.index("# BASE DE CONNAISSANCES"))
        self.assertLess(texte.index("AJOUT_FICTIF_PRIORITAIRE"), texte.index("# Base de connaissances"))
        self.assertLess(texte.index("# Base de connaissances"), texte.index("FAQ_FICTIVE_SECONDAIRE"))
        self.assertIn("PRIMAIRES", texte)
        self.assertIn("SECONDAIRE", texte)
        self.assertIn("3 comptes créés maximum à vie", texte)

    def test_rechargement_effectif_de_la_base_avant_appel_suivant(self):
        premier = self.prompt_envoye()
        horodatage = self.base.stat().st_mtime
        self.base.write_text(self.base.read_text(encoding="utf-8") + "\nMAJ_FICTIVE\n", encoding="utf-8")
        os.utime(self.base, (horodatage + 2, horodatage + 2))
        second = self.prompt_envoye()
        self.assertNotIn("MAJ_FICTIVE", premier)
        self.assertIn("MAJ_FICTIVE", second)
        self.assertIn("3 comptes créés maximum à vie", second)


class MessagesComptes(unittest.IsolatedAsyncioTestCase):
    def test_trois_messages_de_creation_gardent_le_pseudo_sheets(self):
        ns = charger("parcours.py", {"PSEUDO_PRIS", "CREATION"}, {})
        self.assertEqual(3, len(ns["CREATION"]))
        for modele in ns["CREATION"]:
            texte = modele.format(codes="CODE_FICTIF")
            self.assertIn("Garde exactement le pseudo du classeur Sheets", texte)
            self.assertIn("signale le refus ici, sans modifier le pseudo", texte)
            self.assertNotIn("Ajoute un chiffre ou un point", texte)

    async def test_onboarding_force_annonce_les_reels_sans_ouvrir_etape(self):
        for n in (2, 3):
            with self.subTest(etape=n):
                etat = {"clippers": {"42": {}}, "livres": {}}
                parcours = N(_lire=lambda: {"42": {"etape": n, "dates": {}}},
                             lien_du=lambda _: False, envoyer_etape=AsyncMock(), ETAPES={2: {}, 3: {}})
                ns = charger("onboarding.py", {"livrer"}, {
                    "process_adapters": N(store=Mock()), "_lire_etat": lambda: deepcopy(etat),
                    "_ecrire_etat": lambda valeur: etat.update(deepcopy(valeur)),
                    "actif": lambda: False, "datetime": datetime, "timezone": timezone,
                    "attribuer_lien": AsyncMock(return_value={}), "codes_2fa": N(actif=lambda: False),
                    "_liens_classeur_en_fond": Mock(),
                })
                with patch.dict(sys.modules, {"parcours": parcours, "places": N(lignes_a_reserver=lambda: 1)}):
                    texte = await ns["livrer"](N(id=42, display_name="Fictif"), "Fictive", N(id=99), "!onboarding")
                self.assertIn(f"étape {n} pas encore ouverte (Reels requis à vérifier)", texte)
                self.assertNotIn("48 h", texte)
                self.assertIn(f"!etape @Fictif {n}", texte)
                parcours.envoyer_etape.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
