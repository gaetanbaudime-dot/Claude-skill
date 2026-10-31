"""31/10 (Mathieu : « donner à Pierre et Amour le lien de l'application ») : Pierre avait /14 noté « Clipping Pierre » et /1 noté
« Clipping UID:<id> » : deux lignes « Régime paie », deux clés dans `_cles_app` (la dernière lue gagnait), deux apps. Une seule clé
par clipper : celle « uid:<id> » si un de ses liens la porte, sinon celle de la plupart de ses liens. Aucun appel externe."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paie_clics as p

PIERRE, THIA, J1, J2 = "1471000000000000001", "1488000000000000002", "1100000000000000003", "1200000000000000004"


def donnees():
    return {"liens": {
        "l14": {"uid": PIERRE, "note": "Clipping Pierre", "depuis": "2026-10-28"},
        "l1": {"uid": PIERRE, "note": f"Clipping UID:{PIERRE}", "depuis": "2026-10-26"},
        "l7": {"uid": THIA, "note": "Clipping Thia", "depuis": "2026-09-16"},
        "l8": {"uid": THIA, "note": "Clipping Thia", "depuis": ""},
        "lj1": {"uid": J1, "note": "Clipping Julien", "depuis": "2026-10-01"},
        "lj2": {"uid": J1, "note": "Clipping Julien", "depuis": "2026-10-02"},
        "lj3": {"uid": J2, "note": "Clipping Julien", "depuis": "2026-10-03"},
        "libre": {"uid": "", "note": "Clipping libre (ex-Eddy)", "depuis": ""},
    }}


class CleUnique(unittest.TestCase):
    def test_cle_uid_l_emporte(self):
        canon = p._cles_par_uid(donnees())
        self.assertEqual(canon[PIERRE], f"uid:{PIERRE}")
        self.assertEqual(canon[THIA], "thia")
        self.assertEqual(canon[J1], "julien")
        self.assertNotIn("", canon)

    def test_regimes_une_ligne_par_clipper(self):
        with patch.object(p, "regime", return_value="clic"), patch.object(p, "debut_clic", return_value=""):
            lignes = p.lignes_regimes(donnees())
        cles = [l[0] for l in lignes]
        self.assertEqual(cles, sorted(set(cles)))                                # une ligne par clé
        self.assertNotIn("pierre", cles)
        pierre = next(l for l in lignes if l[0] == f"uid:{PIERRE}")
        self.assertEqual(pierre[3], "l1:2026-10-26;l14:2026-10-28")              # ses deux liens sous sa seule clé
        thia = next(l for l in lignes if l[0] == "thia")
        self.assertEqual(thia[3], "l7:2026-09-16")                               # inchangé : un lien sans `depuis` n'est pas listé
        julien = next(l for l in lignes if l[0] == "julien")
        self.assertEqual(julien[3], "lj1:2026-10-01;lj2:2026-10-02")             # homonymes : celui qui a le plus de liens

    def test_cles_app_deterministe(self):
        cles = p._cles_app(donnees())
        self.assertEqual(cles[PIERRE], f"uid:{PIERRE}")
        self.assertEqual(cles[THIA], "thia")
        self.assertEqual(cles[J1], "julien")
        self.assertNotIn(J2, cles)



class EntreesDuDepot(unittest.TestCase):
    """Les envois d'app de Pierre et Amour (TL Mathieu, 31/10) : désignés par leur identifiant Discord, sans lien ni texte."""

    def test_pierre_et_amour(self):
        import json
        deposes = json.loads((Path(__file__).resolve().parents[1] / "messages_a_envoyer.json").read_text(encoding="utf-8"))
        for ident, uid in (("app-amour-3110", "1318861442216230945"), ("app-pierre-3110", "1471860235542073367")):
            e = [x for x in deposes if x["id"] == ident]
            self.assertEqual(len(e), 1)
            self.assertEqual(e[0]["pour"], uid)
            self.assertIs(e[0]["app"], True)
            self.assertNotIn("texte", e[0])
            self.assertNotIn("http", json.dumps(e[0]))
        import messages_deposes
        self.assertTrue({"app-amour-3110", "app-pierre-3110"} <= {m["id"] for m in messages_deposes.lire_deposes()})


if __name__ == "__main__":
    unittest.main()
