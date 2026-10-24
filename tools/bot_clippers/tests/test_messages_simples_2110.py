"""21/10 (Gaëtan : « c'est assez compliqué en termes de lisibilité ; simplifie, supprime des choses, rends ça plus agréable ») :
les messages du salon admin. Cas fictifs, sans réseau ni Discord."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bloques  # noqa: E402
import controle  # noqa: E402
import etats_comptes  # noqa: E402
import places  # noqa: E402


class BloquesTests(unittest.TestCase):
    def test_ranges_par_geste_un_par_ligne(self):
        b = [(13, "Lina", "Sophie", "compte 2 à créer depuis 13 j", "https://wa.me/1"),
             (8, "Hugo", "Sophie", "compte 1 à créer depuis 8 j", "https://wa.me/2"),
             (5, "Rémi", "Chloé", "aucun Reel depuis 5 j", "https://wa.me/3"),
             (4, "Inès", "Sophie", "compte 1 créé depuis 4 j, pas de WhatsApp (`!wa @Inès` quand c'est fait)", "https://wa.me/4"),
             (3, "Karim", "compte 1, Sarah", "scan pas passé sur ce compte depuis l'attente. `!etape @Karim 2` s'il publie.", ""),
             (2, "Noé", "Sophie", "compte 1 à créer depuis 2 j", "https://wa.me/5")]
        out = bloques.lignes(b)
        self.assertEqual(out[0], "🚧 **6 à relancer** · touche un prénom pour ouvrir son WhatsApp, relis, envoie.")
        texte = "\n".join(out)
        self.assertLess(texte.index("**Compte 1 pas créé**"), texte.index("**Compte 2 pas créé**"))
        self.assertLess(texte.index("**Compte 2 pas créé**"), texte.index("**Plus de Reel**"))
        self.assertIn("· [Hugo](https://wa.me/2) Sophie · 8 j\n· [Noé](https://wa.me/5) Sophie · 2 j", texte)
        self.assertIn("· Karim (pas de numéro) (compte 1, Sarah) : scan pas passé", texte)
        self.assertIn("-# Quand c'est fait : `!wa @Prénom`.", texte)
        self.assertTrue(all(ligne.count("](") <= 1 for ligne in out))          # jamais deux liens sur une ligne

    def test_personne(self):
        self.assertEqual(bloques.lignes([]), [])


class PlacesTests(unittest.TestCase):
    DET = {"k": 3, "par_creatrice": {"Sarah": 1, "Sophie": 2}, "places_lignes": 3, "places": 1, "attente": 0, "transit": 0,
           "gaml": {"libres": 1, "promis": 15, "capacite": 1, "actifs": 34, "forfait": 50}}

    def test_deux_lignes_et_les_places_en_petit(self):
        t = places.texte_court(self.DET)
        self.assertEqual(t.split("\n")[0], "📦 **1 nouveau peut entrer.**")
        self.assertIn("Limite : les liens GAML (34/50 actifs, 15 promis aux clippers en route)", t)
        self.assertIn("-# Places par créatrice : Sarah 1 · Sophie 2", t)

    def test_zero_place(self):
        det = dict(self.DET, places=0, places_lignes=0, gaml=None)
        self.assertTrue(places.texte_court(det).startswith("⛔ **0 place : n'annonce pas encore.**\nLimite : plus de comptes prêts"))


class EtatsTests(unittest.TestCase):
    def test_rien_de_change_rien_n_est_poste(self):
        self.assertEqual(etats_comptes.texte_bilan_court({"changements": [], "scannes": 100, "followers": 26, "restreints": ["x"]}), "")

    def test_seulement_les_changements(self):
        t = etats_comptes.texte_bilan_court({"changements": [("a1", "Alice Clipping", "GOOD", "BAN", 4),
                                                             ("b1", "Bruno", "BAN", "GOOD", 9)]})
        self.assertTrue(t.startswith("🗂️ **Comptes ce matin** : 1 BAN · 1 GOOD"))
        self.assertIn("→ BAN : `a1` (Alice)", t)
        self.assertIn("→ GOOD : `b1` (Bruno)", t)
        self.assertNotIn("Restreints", t)


class ControleTests(unittest.TestCase):
    def test_trois_lignes(self):
        an = [{"famille": "C4", "texte": "Chloé l. 10 · @x : compte encore dans la fiche de Y", "gravite": "bloquant"},
              {"famille": "C4", "texte": "Chloé l. 12 · @z : idem", "gravite": "bloquant"},
              {"famille": "C2", "texte": "Chloé · Gérant inconnu", "gravite": "important"},
              {"famille": "C1", "texte": "info", "gravite": "info"}]
        t = controle.texte_admin_court(an)
        lignes = t.split("\n")
        self.assertEqual(lignes[0], "🧭 **Contrôle du classeur** : 2 bloquant(s) · 1 important(s) · 1 info")
        self.assertEqual(len(lignes), 4)
        self.assertEqual(lignes[-1], "-# Le détail : `!controle`.")

    def test_rien(self):
        self.assertEqual(controle.texte_admin_court([]), "🧭 **Contrôle du classeur** : rien à corriger.")


class SupportTests(unittest.TestCase):
    def test_support_lisible(self):
        import bot_discord
        t = bot_discord.texte_notification_support(7, "42", "assistance IA · question 4b3927c17fcd9ae0", "https://discord.com/x")
        self.assertEqual(t, "🆘 **Support #7** · <@42> : l'assistant n'a pas su lui répondre.\n→ https://discord.com/x\n"
                            "-# Dossier : `!support 42`")
        t = bot_discord.texte_notification_support(8, "42", "demande de prise en charge par l’équipe", "Demande reçue en MP")
        self.assertIn("il demande l'équipe", t)
        self.assertIn("réponds-lui dans son salon", t)


if __name__ == "__main__":
    unittest.main()


class EnRoute2410Tests(unittest.TestCase):
    """24/10 (« ⛔ 0 place », 15 liens promis) : un lien n'est promis qu'une fois le compte 1 créé, et jamais à un sorti."""
    def test_lien_promis_apres_le_compte_1(self):
        from unittest.mock import patch
        import parcours
        fiches = {"1": {"etape": 1, "creatrice": "Sophie", "dates": {"1": "2026-10-18T10:00:00+00:00"}},
                  "2": {"etape": 2, "creatrice": "Sophie", "dates": {"1": "x", "1_fait": "2026-10-20T10:00:00+00:00", "2": "y"}},
                  "3": {"etape": 2, "creatrice": "Sophie", "dates": {"1_fait": "z"}}}
        registre = {"1": {}, "2": {}}
        ancien = dict(parcours._deps)
        parcours._deps.update(FICHIER_EQUIPES="equipes.json", lire_json=lambda f, d: registre)
        try:
            with patch.object(parcours, "_lire", return_value=fiches), \
                    patch.object(places.onboarding, "_lire_etat", return_value={"clippers": {}}), \
                    patch.object(places.paie_clics, "actif", return_value=False):
                route = {r["uid"]: r for r in places.en_route()}
        finally:
            parcours._deps.clear()
            parcours._deps.update(ancien)
        self.assertFalse(route["1"]["lien_du"])                              # compte 1 pas créé : pas de lien réservé
        self.assertTrue(route["2"]["lien_du"])
        self.assertNotIn("3", route)                                         # hors registre : sorti de l'équipe
