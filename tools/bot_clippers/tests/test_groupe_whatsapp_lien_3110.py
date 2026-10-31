"""31/10 (Gaëtan : « au lieu qu'on crée un groupe avec le team leader, direct tu demandes au clippeur de rejoindre ce groupe à la
fin… Demande au clippeur de se présenter à son arrivée ») : la créatrice qui a un lien de groupe (variable WHATSAPP_GROUPES) le
donne au clipper en dernier message de l'arrivée, avec la consigne de se présenter ; plus de message au TL pour elle. Liens et
cas fictifs, sans réseau ni Discord."""
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import parcours  # noqa: E402
from test_regles_2310 import clipper, monde  # noqa: E402
import test_process_onboarding as orchestration  # noqa: E402
from test_process_onboarding import charger  # noqa: E402

LIEN_CHLOE = "https://chat.whatsapp.com/FictifChloe123"
LIEN_SOPHIE = "https://chat.whatsapp.com/FictifSophie456"
GROUPES = f"Chloé={LIEN_CHLOE}; Sophie = {LIEN_SOPHIE}\nJade=https://exemple.invalid/pas-whatsapp"


def boutons(salon):
    return [getattr(b, "url", "") or getattr(getattr(b, "item", None), "url", "")
            for b in salon.send.await_args.kwargs["view"].children]


class LiensDesGroupesTests(unittest.TestCase):
    def test_lecture_de_la_variable(self):
        with patch.dict(os.environ, {"WHATSAPP_GROUPES": GROUPES}):
            liens = parcours.liens_groupes_whatsapp()
            self.assertEqual({"chloe": LIEN_CHLOE, "sophie": LIEN_SOPHIE}, liens)      # le lien qui n'est pas WhatsApp est ignoré
            self.assertEqual(LIEN_CHLOE, parcours.lien_groupe_creatrice("chloe"))
            self.assertEqual(LIEN_SOPHIE, parcours.lien_groupe_creatrice("Sophie ✨"))
            self.assertEqual("", parcours.lien_groupe_creatrice("Jade"))
            self.assertEqual("", parcours.lien_groupe_creatrice("Clara"))
            self.assertEqual("", parcours.lien_groupe_creatrice(""))

    def test_variable_absente_aucun_lien(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WHATSAPP_GROUPES", None)
            self.assertEqual({}, parcours.liens_groupes_whatsapp())

    def test_aucun_lien_d_invitation_dans_le_code(self):
        """Le dépôt est public : un lien d'invitation fait entrer n'importe qui dans le groupe."""
        for nom in ("parcours.py", "bot_discord.py", "connaissances.md"):
            texte = (ROOT / nom).read_text(encoding="utf-8")
            self.assertEqual([], [l for l in re.findall(r"chat\.whatsapp\.com/[A-Za-z0-9]{6,}", texte)], nom)

    def test_message_en_francais_simple(self):
        propre = re.sub(r"\{[^}]*\}", "", parcours.TEXTE_GROUPE_LIEN)
        self.assertNotIn("—", propre)
        self.assertNotIn("(", propre)
        for phrase in re.split(r"[.!?\n]+", propre):
            self.assertLessEqual(len([w for w in phrase.split() if re.search(r"\w", w)]), 10, phrase)
        self.assertIn("présente-toi", parcours.TEXTE_GROUPE_LIEN)


class InviterGroupeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.membre = N(mention="<@1>", display_name="Nina - Chloé")
        self.salon = N(send=AsyncMock())

    async def test_un_seul_message_avec_le_bouton_et_la_presentation(self):
        with patch.dict(os.environ, {"WHATSAPP_GROUPES": GROUPES}), monde({"1": clipper()}) as (m, canal):
            premier = await parcours.inviter_groupe_creatrice(self.salon, self.membre, "1", "Chloé")
            second = await parcours.inviter_groupe_creatrice(self.salon, self.membre, "1", "Chloé")
            fiche = m["p"]["1"]
        self.assertEqual(("envoyé", ""), (premier, second))
        self.salon.send.assert_awaited_once()
        texte = self.salon.send.await_args.args[0]
        self.assertIn("<@1>", texte)
        self.assertIn("groupe WhatsApp Team Chloé", texte)
        self.assertIn("présente-toi", texte)
        self.assertNotIn(LIEN_CHLOE, texte)                                     # le lien est sur le bouton
        self.assertEqual([LIEN_CHLOE], boutons(self.salon))
        self.assertTrue(fiche["groupe_lien_envoye"])
        self.assertEqual("lien-groupe", fiche["whatsapp_par"])                  # ni relance ni « pas de WhatsApp » ensuite

    async def test_sans_lien_pour_la_creatrice_rien(self):
        with patch.dict(os.environ, {"WHATSAPP_GROUPES": GROUPES}), monde({"1": clipper(creatrice="Clara")}) as (m, _):
            self.assertEqual("", await parcours.inviter_groupe_creatrice(self.salon, self.membre, "1", "Clara"))
            self.assertNotIn("groupe_lien_envoye", m["p"]["1"])
        self.salon.send.assert_not_awaited()

    async def test_envoi_rate_la_reprise_le_renvoie(self):
        self.salon.send.side_effect = [RuntimeError("Discord fictif"), None]
        with patch.dict(os.environ, {"WHATSAPP_GROUPES": GROUPES}), monde({"1": clipper()}) as (m, _):
            self.assertEqual("échec", await parcours.inviter_groupe_creatrice(self.salon, self.membre, "1", "Chloé"))
            self.assertNotIn("groupe_lien_envoye", m["p"]["1"])
            self.assertNotIn("whatsapp", m["p"]["1"])
            self.assertEqual("envoyé", await parcours.inviter_groupe_creatrice(self.salon, self.membre, "1", "Chloé"))

    async def test_jamais_d_exception_sans_fiche(self):
        with patch.dict(os.environ, {"WHATSAPP_GROUPES": GROUPES}), monde({}):
            self.assertEqual("", await parcours.inviter_groupe_creatrice(self.salon, self.membre, "9", "Chloé"))
        self.salon.send.assert_not_awaited()


class ArriveeTests(unittest.IsolatedAsyncioTestCase):
    setUp = orchestration.OnboardingTests.setUp
    tearDown = orchestration.OnboardingTests.tearDown if hasattr(orchestration.OnboardingTests, "tearDown") else None
    contexte = orchestration.OnboardingTests.contexte

    async def test_lien_de_groupe_remplace_la_demande_au_tl_en_dernier(self):
        ns, membre, salon, _ = self.contexte()
        ordre = []
        ns['parcours'].lien_groupe_creatrice = lambda creatrice: LIEN_CHLOE
        ns['parcours'].inviter_groupe_creatrice = AsyncMock(side_effect=lambda *a: ordre.append('groupe') or "envoyé")
        ns['parcours'].demander_groupe_tl = AsyncMock()
        ns['parcours'].demander_groupe_gaetan = AsyncMock()
        ns['attribution']._sortir_d_attente.side_effect = lambda *a: ordre.append('cloture')
        resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
        ns['parcours'].inviter_groupe_creatrice.assert_awaited_once_with(salon, membre, '42', 'Fictive')
        ns['parcours'].demander_groupe_tl.assert_not_awaited()
        ns['parcours'].demander_groupe_gaetan.assert_not_awaited()
        self.assertEqual(['groupe', 'cloture'], ordre)
        self.assertIn('lien du groupe WhatsApp Team Fictive donné', resultat)

    async def test_sans_lien_le_tl_reste_sollicite(self):
        ns, membre, salon, _ = self.contexte()
        ns['parcours'].lien_groupe_creatrice = lambda creatrice: ""
        ns['parcours'].inviter_groupe_creatrice = AsyncMock()
        ns['parcours'].demander_groupe_tl = AsyncMock(return_value=True)
        await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
        ns['parcours'].inviter_groupe_creatrice.assert_not_awaited()
        ns['parcours'].demander_groupe_tl.assert_awaited_once()

    async def test_echec_du_lien_dit_dans_le_bilan(self):
        ns, membre, salon, _ = self.contexte()
        ns['parcours'].lien_groupe_creatrice = lambda creatrice: LIEN_CHLOE
        ns['parcours'].inviter_groupe_creatrice = AsyncMock(return_value="échec")
        resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
        self.assertIn("⚠️ lien du groupe WhatsApp Team Fictive pas envoyé : `!creatrice Fictif Fictive`", resultat)


if __name__ == "__main__":
    unittest.main()
