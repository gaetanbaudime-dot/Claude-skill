"""23/10 (Gaëtan : « refige toute la base de connaissances, comme ça l'assistant IA dans le Discord sera à jour et nos process aussi »).

La base de l'assistant (`connaissances.md`) doit rester alignée sur la page des règles gelées du 23/10 au 17/11/2026 : l'assistant
contredisait le bot (cas Romaric et Yves : « 48 h entre les comptes », « 4 Reels de plus sur le compte 1 », un bouton WhatsApp qui
n'existe plus). Ce test refuse les anciennes règles et vérifie que les règles du 23/10 sont écrites. Sans réseau ni Discord.

Après le 17/11/2026, quand les règles sont revues sur les chiffres des cohortes : mettre ce test à jour avec la page des règles,
jamais l'inverse."""
import os
import re
import sys
import unittest

DOSSIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER)

with open(os.path.join(DOSSIER, "connaissances.md"), encoding="utf-8") as _f:
    BASE = _f.read()
LIGNES = BASE.split("\n")


def _sources_bot() -> str:
    morceaux = []
    for nom in sorted(os.listdir(DOSSIER)):
        if nom.endswith(".py"):
            with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
                morceaux.append(f.read())
    return "\n".join(morceaux)


class EnTeteTests(unittest.TestCase):
    def test_version_et_gel_dans_la_premiere_ligne(self):
        premiere = LIGNES[0]
        version = re.search(r"\(v(\d+),", premiere)
        self.assertIsNotNone(version, "la première ligne doit porter la version (vNN, date)")
        self.assertGreaterEqual(int(version.group(1)), 21)
        self.assertIn("gelées du 23/10 au 17/11/2026", premiere)

    def test_le_gel_est_annonce_dans_l_entete(self):
        self.assertIn("Gel du 23/10 au 17/11/2026", "\n".join(LIGNES[:12]))


class AnciennesReglesRefuseesTests(unittest.TestCase):
    """Chaque motif est une règle qui n'existe plus. Une ligne qui la nie (« plus de délai de 48 h ») n'est pas visée."""

    INTERDITS = [
        (r"au plus tôt 48\s*h", "plus de délai de 48 h entre les comptes (C4, C5, 18/10)"),
        (r"4 (Reels )?de plus", "le compte 3 n'attend rien de plus sur le compte 1 (C5)"),
        (r"publies bien sur tes", "les comptes 2 et 3 arrivent dès 4 Reels lus, sans jugement de qualité en plus (C4, C5)"),
        (r"dans les 48\s*h après", "pas de durée annoncée pour le compte 1 : la règle L6 et le code ne disent pas la même chose"),
        (r"bouton WhatsApp", "plus de bouton WhatsApp dans la bienvenue : le TL crée le groupe (E8, E10)"),
        (r"reporting du dimanche", "le reporting du dimanche n'existe plus depuis le 5 octobre"),
        (r"sauf si ton manager le dit", "la cadence au-delà de 2 Reels est un choix du clipper (C7)"),
        (r"2 Reels par jour et pas plus", "la cadence peut monter, sur la base du volontariat (C7)"),
        (r"3 000 visites", "pas de chiffre d'agence dans la base (en-tête)"),
        (r"20 000 à 30 000", "pas de chiffre d'agence dans la base (en-tête)"),
        (r"ancien qui était au fixe", "un fixe ne touche pas aussi le clic (P3)"),
        (r"Madagascar, Bénin :", "plus de moyen de paiement par pays : USDC pour tous, quelques virements décidés avec Gaëtan (P4)"),
    ]

    def test_aucune_ancienne_regle(self):
        trouves = []
        for motif, raison in self.INTERDITS:
            for numero, ligne in enumerate(LIGNES, start=1):
                for m in re.finditer(motif, ligne, flags=re.IGNORECASE):
                    avant = ligne[max(0, m.start() - 20): m.start()]
                    if re.search(r"plus d(?:e|')\s*(?:le |la |l'|un |une )?$", avant, flags=re.IGNORECASE):
                        continue                                        # « Plus de bouton WhatsApp… » : la ligne nie l'ancienne règle
                    trouves.append(f"ligne {numero} : « {motif} » ({raison})")
        self.assertEqual(trouves, [], "\n".join(trouves))

    def test_drive_perso_seulement_pour_dire_qu_il_n_existe_plus(self):
        for numero, ligne in enumerate(LIGNES, start=1):
            if re.search(r"Drive perso", ligne):
                self.assertIn("Plus de Drive perso", ligne, f"ligne {numero}")

    def test_48_h_seulement_pour_le_nier_ou_pour_l_appel_de_presence(self):
        for numero, ligne in enumerate(LIGNES, start=1):
            for m in re.finditer(r"48\s*h", ligne):
                contexte = ligne[max(0, m.start() - 70): m.end() + 70]
                permis = ("aucun délai de 48 h" in contexte or "plus de délai de 48 h" in contexte
                          or "délai de 48 h est retiré" in contexte or "pour répondre" in contexte)
                self.assertTrue(permis, f"ligne {numero} : « {contexte} »")


class ReglesDu2310EcritesTests(unittest.TestCase):
    ATTENDUS = [
        ("4 Reels sont publiés sur le compte 1", "C4 : compte 2 dès 4 Reels sur le compte 1"),
        ("4 Reels sont publiés sur le compte 2", "C5 : compte 3 dès 4 Reels sur le compte 2"),
        ("Aucun délai en plus", "C4 : aucun délai en plus"),
        ("au jour 3", "C11 : l'app au jour 3"),
        ("duplicateur de Reels", "C11 : le duplicateur est dans l'app"),
        ("rushes bruts", "C11 : rushes bruts seulement"),
        ("Gaëtan est ton TL", "E10 : Gaëtan est TL par défaut"),
        ("J'ai écrit à Gaëtan", "E10 : le bouton du clipper sans TL"),
        ("ton TL le crée", "E8 : le TL crée le groupe WhatsApp"),
        ("salon ℹ️ de ta créatrice", "E11 : vidéos, Drive et photos dans le salon ℹ️"),
        ("photos de profil", "E11 : les photos de profil"),
        ("top 50", "E11 : le Google Sheet du top 50"),
        ("#ressources", "E11 : #ressources"),
        ("Ton lien est prêt", "L9 : le message de la cohorte"),
        ("Une story tous les 2 jours", "L9 : une story tous les 2 jours"),
        ("sticker « Lien »", "L9 : le sticker lien"),
        ("Jamais à la une. Jamais dans ta bio. Jamais dans un Reel.", "L9 : jamais à la une, en bio, dans un Reel"),
        ("0,05 $", "P1 : 0,05 $ par visite"),
        ("le 5 et le 20", "P2 : paie le 5 et le 20"),
        ("USDC", "P4 : USDC"),
        ("reportée à la période suivante", "P4 : sans adresse, report"),
        ("10 jours d'affilée", "L7 : sortie après 10 jours à 0 visite payée"),
        ("30 jours est désactivé, jamais effacé", "L5 : lien à 0 clic sur 30 jours désactivé"),
        ("1 Reel par jour et par compte de croissance chaque semaine", "C7 : +1 par semaine, volontaire"),
        ("Un fixe ne touche pas aussi le clic", "P3 : aucun fixe ne touche aussi le clic"),
    ]

    def test_chaque_regle_est_ecrite(self):
        manquantes = [f"« {texte} » ({raison})" for texte, raison in self.ATTENDUS if texte not in BASE]
        self.assertEqual(manquantes, [], "\n".join(manquantes))

    def test_les_trois_motifs_whatsapp_gaetan(self):
        ligne = next(l for l in LIGNES if l.startswith("- **Gaëtan**, sur WhatsApp"))
        for motif in ("banni", "numéro refusé", "paiement"):
            self.assertIn(motif, ligne)


class SecuriteDeLaBaseTests(unittest.TestCase):
    def test_pas_d_identite_ni_de_donnee_de_paie(self):
        noms = ("Sophie", "Sarah", "Chloé", "Clara", "Jade", "Maddie", "Clarisse", "Yves", "Mathieu",
                "Caroline", "Lilian", "Josué", "Lucas", "Rianah", "Romaric")
        presents = [n for n in noms if re.search(rf"\b{n}\b", BASE)]
        self.assertEqual(presents, [], "identités interdites dans la base (en-tête du fichier)")
        self.assertIsNone(re.search(r"0x[0-9a-fA-F]{20,}", BASE), "adresse de portefeuille")
        self.assertIsNone(re.search(r"\b(FR\d{2}\s?\d{4}|IBAN\s*:)", BASE), "coordonnées bancaires")
        self.assertIsNone(re.search(r"\d+\s?\$ par (TL|clipper de son équipe)", BASE), "montant de paie du manager ou du TL")


class CommandesCiteesTests(unittest.TestCase):
    def test_chaque_commande_citee_existe_dans_le_bot(self):
        source = _sources_bot()
        inconnues = []
        for cmd in sorted(set(re.findall(r"`(![a-zé-]+)", BASE))):
            if cmd not in source:
                inconnues.append(cmd)
        self.assertEqual(inconnues, [], "commandes citées dans la base mais absentes du code")


if __name__ == "__main__":
    unittest.main()
