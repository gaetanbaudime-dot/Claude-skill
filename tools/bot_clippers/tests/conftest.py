"""31/10 : les compteurs du suivi des créations (suivi_creation.compter) écrivent dans un dossier temporaire pendant les tests,
jamais dans donnees/ (les parcours de test passent par le bouton « Compte créé », qui compte ses vérifications)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _compteurs_du_suivi_en_temporaire(tmp_path, monkeypatch):
    import suivi_creation
    if not str(suivi_creation.FICHIER).startswith(str(Path(__file__).resolve().parent.parent / "donnees")):
        yield                                                           # déjà détourné par le test lui-même
        return
    monkeypatch.setattr(suivi_creation, "FICHIER", tmp_path / "suivi_creation.json")
    yield
