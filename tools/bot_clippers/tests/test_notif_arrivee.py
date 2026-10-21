"""21/10 : une ligne Telegram par nouveau clipper attribué."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import attribution  # noqa: E402


def test_texte_arrivee():
    assert attribution.texte_arrivee("Oumar", "Sophie", "acceptation (bouton)") == "🆕 Nouveau clipper : Oumar → Sophie (bouton)"
    assert attribution.texte_arrivee("Benn", "Sarah", "") == "🆕 Nouveau clipper : Benn → Sarah"
    assert attribution.texte_arrivee("Benn", "Sarah", "quiz", True) == "🆕 Nouveau clipper : Benn → Sarah (quiz) · en attente de comptes prêts"


def test_notifier_ne_casse_jamais(monkeypatch):
    import telegram

    async def panne(_texte):
        raise RuntimeError("réseau")
    monkeypatch.setattr(telegram, "envoyer_telegram", panne)
    asyncio.run(attribution.notifier_arrivee("Oumar", "Sophie", "quiz"))


def test_coupure(monkeypatch):
    import telegram
    envoyes = []

    async def note(texte):
        envoyes.append(texte)
    monkeypatch.setattr(telegram, "envoyer_telegram", note)
    monkeypatch.setattr(attribution, "TELEGRAM_ARRIVEES", False)
    asyncio.run(attribution.notifier_arrivee("Oumar", "Sophie", "quiz"))
    assert envoyes == []
    monkeypatch.setattr(attribution, "TELEGRAM_ARRIVEES", True)
    asyncio.run(attribution.notifier_arrivee("Oumar", "Sophie", "quiz"))
    assert envoyes == ["🆕 Nouveau clipper : Oumar → Sophie (quiz)"]
