"""21/10 : onglet « Pilotage créations » (Cockpit Clipping : vitesse de création de comptes). Cas fictifs."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard  # noqa: E402


def _ctx(parcours=None, cree_vu=None, comptes=None, onb=None):
    e = {"etats": {"cree_vu": cree_vu or {}}, "parcours": parcours or {}, "comptes": comptes or [], "onboarding": onb or {}}
    return dashboard._Ctx(e, datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc))


def test_scan_sans_le_jour_d_amorcage_et_classeur_pour_creatrice_et_gerant():
    ctx = _ctx(cree_vu={"vieux1": "2026-10-09", "vieux2": "2026-10-09", "neuf": "2026-10-15", "ailleurs": "2026-10-20"},
               comptes=[{"handle": "neuf", "onglet": "Sarah", "creatrice": "Sarah", "gerant": "Yves"}])
    assert dashboard.lignes_creations(ctx) == [["2026-10-15", "Sarah", "Yves", "neuf", "scan"],
                                               ["2026-10-20", "", "", "ailleurs", "scan"]]


def test_parcours_prime_sur_le_scan_heure_de_paris():
    parcours = {"42": {"creatrice": "Sophie", "profils": {"1": "2026-10-19T22:30:00+00:00"}, "dates": {"2_fait": "2026-10-20T08:00:00+00:00"}}}
    onb = {"clippers": {"42": {"comptes": ["sophie.un", "sophie.deux", "sophie.prive"]}}}
    ctx = _ctx(parcours=parcours, onb=onb, cree_vu={"amorce": "2026-10-09", "sophie.un": "2026-10-21"},
               comptes=[{"handle": "sophie.un", "onglet": "Sophie", "creatrice": "Sophie", "gerant": "Paul"}])
    assert dashboard.lignes_creations(ctx) == [["2026-10-20", "Sophie", "", "sophie.deux", "parcours"],
                                               ["2026-10-20", "Sophie", "Paul", "sophie.un", "parcours"]]


def test_fenetre():
    ctx = _ctx(cree_vu={"amorce": "2026-01-01", "trop_vieux": "2026-08-01", "dedans": "2026-10-01"})
    assert [r[3] for r in dashboard.lignes_creations(ctx, jours=30)] == ["dedans"]
