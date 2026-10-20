"""20/10 : coefficients d'attribution réglés depuis le Cockpit Clipping (onglet « Réglages attribution »)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import attribution  # noqa: E402

CONNUES = ["Sophie", "Sarah", "Chloé", "Jade", "Clara", "Maddie"]


def test_demande_normalisee():
    assert attribution.lire_demande(" sophie : 5 ; Sarah:3, chloe:1,Clara:0", CONNUES) == ("Sophie:5,Sarah:3,Chloé:1,Clara:0", "")


def test_demandes_refusees():
    assert attribution.lire_demande("", CONNUES)[0] is None
    assert attribution.lire_demande("Sophie", CONNUES)[1].startswith("« Sophie »")
    assert attribution.lire_demande("Sophie:deux", CONNUES)[0] is None
    assert attribution.lire_demande("Sophie:99", CONNUES)[0] is None
    assert attribution.lire_demande("Sophie:1,sophie:2", CONNUES)[1] == "sophie apparaît deux fois"
    assert attribution.lire_demande("Sophie:0,Sarah:0", CONNUES)[0] is None


def test_etat_publie():
    ancien = attribution.ORDRE_TEXTE
    try:
        attribution.definir_ordre("Sophie:2,Sarah:1")
        lignes = attribution.etat_reglages(4, {"Sophie": 3, "Sarah 💖": 0})
        assert lignes[0][:2] == ["Ordre appliqué", "Sophie:2,Sarah:1"]
        assert lignes[1][1] == "1"                                   # 4 modulo 3 places
        assert lignes[2][1] == "Sophie,Sophie,Sarah"
        assert lignes[3][1] == "Sophie:3,Sarah:0"
        assert attribution.etat_reglages(0, None)[3][1] == ""        # stock inconnu : vide, jamais un faux 0
    finally:
        attribution.definir_ordre(ancien)
