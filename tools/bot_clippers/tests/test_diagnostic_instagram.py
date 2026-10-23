"""23/10 : le diagnostic tourne les pages avec ou sans id_acc et compte les Reels distincts."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import diagnostic_instagram as D  # noqa: E402
import instagram_rapidapi as I  # noqa: E402


def test_tourner_avec_et_sans_id_acc(monkeypatch):
    maintenant = datetime.now(timezone.utc)
    appels = []

    def page(debut):
        return [{"media": {"code": f"R{debut + k}", "taken_at": int((maintenant - timedelta(days=debut + k)).timestamp())}} for k in range(12)]

    async def appeler(session, chemin, params):
        appels.append(dict(params))
        if "max_id" not in params:
            return 200, {"items": page(0), "paging_info": {"max_id": "C1", "more_available": True}, "pagination": {"id_acc": 7}}
        if params.get("id_acc") == 7:                                   # le curseur ne marche qu'avec le même compte
            return 200, {"items": page(12), "paging_info": {"more_available": False}, "pagination": {"id_acc": 7}}
        return 200, {"items": page(0), "paging_info": {"more_available": False}, "pagination": {"id_acc": 9}}
    monkeypatch.setattr(I, "appeler", appeler)
    _, vus_a, _ = asyncio.run(D.tourner(None, "1", "reels", False, maintenant - timedelta(days=60)))
    _, vus_b, dans_b = asyncio.run(D.tourner(None, "1", "reels", True, maintenant - timedelta(days=60)))
    assert len(vus_a) == 12 and len(vus_b) == 24 and len(dans_b) == 24
    assert appels[-1] == {"id_user": "1", "max_id": "C1", "id_acc": 7}


def test_ecart_avec_metricool():
    depuis = datetime(2026, 9, 1, tzinfo=timezone.utc)
    v = D.lire_verite([["@", "Code", "Lien", "Publié le"], ["Sophie1", "A", "", "2026-09-15T08:00:00Z"],
                       ["sophie1", "B", "", "2026-09-14T08:00:00Z"], ["sophie1", "VIEUX", "", "2026-08-01T08:00:00Z"]], depuis)
    assert v == {"sophie1": {"A": "2026-09-15T08:00", "B": "2026-09-14T08:00"}}
    n = D.note_ecart({"A", "Z"}, v["sophie1"])
    assert n == " · Metricool : 2 · manquants : 1 (B (2026-09-14)) · en plus de Metricool : 1"
    assert D.note_ecart({"A"}, {}) == ""
