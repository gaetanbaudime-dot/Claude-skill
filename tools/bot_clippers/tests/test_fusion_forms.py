"""18/10 : réponses des anciens Google Forms remontées en haut de « Candidatures bot ». Cas fictifs, sans réseau."""
import asyncio
import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fusion_forms  # noqa: E402

MOTS = (("date", ("horodat",)), ("prenom", ("prenom",)), ("tel", ("whatsapp", "numero")), ("telegram", ("telegram",)),
        ("pays", ("pays",)), ("age", ("quel age", "ton age")))


def normaliser(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")


def colonnes(en_tete):
    trouve, pris = {}, set()
    for champ, mots in MOTS:
        for i, h in enumerate(en_tete):
            hn = normaliser(h)
            if i not in pris and hn and any(m in hn for m in mots):
                trouve[champ] = i
                pris.add(i)
                break
    return trouve


BOT = ["Horodatage", "Source", "Quel est ton Prénom ?", "Whatsapp ?", "Pays ?", "Ton âge", "ou as tu vu annonce ?"]
FORM = [["Horodateur", "Quel est ton Prénom ?", "Quel est ton numéro Whatsapp ?", "Dans quel pays résides-tu ? ",
         "Tu as quel âge ?", "Sur quel réseau social as-tu vu notre annonce de recrutement ? ", "Es-tu OK avec le modèle fixe ?"],
        ["04/07/2026 11:46:11", "Orlando", "+261 33 00 000 01", "Madagascar", "21", "Telegram", "Oui"],
        ["05/07/2026 10:00:00", "", "", "Bénin", "", "", ""]]
EXISTANTE = ["18/10/2026 08:00", "tg-groupe", "Mavie", "+33600000002", "France", "24", "Telegram"]


class PlanTests(unittest.TestCase):
    def test_en_haut_sous_la_bonne_question(self):
        tete, lignes, compte = fusion_forms.plan(BOT, [EXISTANTE], [("form-malgaches", FORM)], normaliser, colonnes)
        self.assertEqual(compte, {"form-malgaches": 2})
        self.assertEqual(tete[-1], "Es-tu OK avec le modèle fixe ?")          # question sans équivalent : colonne au bout
        orlando = lignes[0]
        self.assertEqual(orlando[:7], ["04/07/2026 11:46:11", "form-malgaches", "Orlando", "+261 33 00 000 01", "Madagascar",
                                       "21", "Telegram"])
        self.assertEqual(orlando[-1], "Oui")
        self.assertEqual(lignes[2][:3], EXISTANTE[:3])                         # les candidatures du site restent dessous

    def test_jamais_deux_fois(self):
        _, lignes, _ = fusion_forms.plan(BOT, [EXISTANTE], [("form-malgaches", FORM)], normaliser, colonnes)
        _, lignes2, compte = fusion_forms.plan(BOT + ["Es-tu OK avec le modèle fixe ?"], lignes, [("form-malgaches", FORM)],
                                               normaliser, colonnes)
        self.assertEqual(compte, {"form-malgaches": 0})
        self.assertEqual(len(lignes2), 3)


class FakeGoogle:
    def __init__(self, partage=True):
        self.partage, self.ecrit = partage, {}

    def email_compte(self):
        return "bot@exemple.iam"

    async def sheets_onglets(self, ident):
        if not self.partage:
            raise RuntimeError("403")
        return ["Réponses au formulaire 1"]

    async def sheets_lire(self, ident, plage):
        return FORM

    async def sheets_assurer_colonnes(self, *a):
        return 0

    async def sheets_proprietes(self, classeur):
        return {"Candidatures bot": {"id": 1, "lignes": 1000}}

    async def sheets_batch_update(self, *a):
        pass

    async def sheets_ecrire(self, classeur, plage, valeurs):
        self.ecrit[plage] = valeurs


class ExecuterTests(unittest.TestCase):
    def _lancer(self, g, fichier):
        async def lire(onglet):
            return [BOT, EXISTANTE] if onglet == "Candidatures bot" else [FORM[0]]
        return asyncio.run(fusion_forms.executer(g, "X", "Candidatures bot", "Réponses au formulaire 1", fichier, normaliser,
                                                 colonnes, lire))

    def test_une_fois_et_principal_plus_lu(self):
        with tempfile.TemporaryDirectory() as d:
            fichier = Path(d) / "fusion.json"
            fusion_forms.FORMS_ARCHIVES = "form-malgaches=ID1"
            g = FakeGoogle()
            bilan = self._lancer(g, fichier)
            self.assertIn("form-malgaches : 2", bilan)
            self.assertEqual(g.ecrit["Candidatures bot!A2"][0][0], "04/07/2026 11:46:11")
            self.assertEqual(g.ecrit["Candidatures bot!A2"][0][3], "'+261 33 00 000 01")   # reste du texte
            self.assertTrue(fusion_forms.principal_fusionne(fichier))
            self.assertEqual(self._lancer(FakeGoogle(), fichier), "")                # deuxième démarrage : rien

    def test_classeur_non_partage_dit_le_compte(self):
        with tempfile.TemporaryDirectory() as d:
            fusion_forms.FORMS_ARCHIVES = "form-malgaches=ID1"
            bilan = self._lancer(FakeGoogle(partage=False), Path(d) / "f.json")
            self.assertIn("bot@exemple.iam", bilan)
            self.assertNotIn("form-malgaches", json.loads((Path(d) / "f.json").read_text()))


if __name__ == "__main__":
    unittest.main()
