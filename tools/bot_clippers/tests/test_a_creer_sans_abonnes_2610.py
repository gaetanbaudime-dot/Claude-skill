"""26/10 (Gaëtan : « ces comptes ne sont pas créés sur Instagram et n'ont pas de followers… je pense qu'on a un problème
d'attribution ») : une ligne « à créer » ne porte jamais les chiffres d'un autre compte, et les écritures du contrôle des @
retrouvent leur ligne par son @ dans le LOG relu. Cas fictifs, sans réseau."""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import etats_comptes as E  # noqa: E402
import onboarding  # noqa: E402
import pseudos_uniques as P  # noqa: E402

T = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
RECENT = (T - timedelta(days=2)).isoformat()
VIEUX = (T - timedelta(days=12)).isoformat()
COLS = {"Lea": {"etat": 0, "handle": 1, "followers": 3, "reels_hier": 4, "reels_7j": 5, "gerant": 8}}


def ligne(n, etat, handle, gerant="", followers="", rh="", r7=""):
    return {"onglet": "Lea", "ligne": n, "etat": etat, "handle": handle, "gerant": gerant, "followers": followers,
            "reels_hier": rh, "reels_7j": r7}


def test_a_vider_seulement_les_a_creer_libres_avec_des_chiffres():
    comptes = [ligne(10, "à créer", "lea.libre", "Nino", followers="142"),        # libre, des abonnés : à vider
               ligne(11, "à créer", "lea.zero", "", followers="0", rh="0", r7="0"),  # libre, des zéros : à vider aussi
               ligne(12, "à créer", "lea.prise", "Nino", followers="7"),          # pris : peut-être le compte du clipper
               ligne(13, "à créer", "lea.vieux", "", followers="5"),              # libre il y a 12 jours : à revérifier d'abord
               ligne(14, "GOOD", "lea.vivant", "Nino", followers="300"),          # créé : jamais touché
               ligne(15, "à créer", "lea.vide", "Nino")]                          # rien à vider
    memo = {"lea.libre": {"statut": "libre", "le": RECENT}, "lea.zero": {"statut": "libre", "le": RECENT},
            "lea.prise": {"statut": "pris", "attribue": True, "le": RECENT}, "lea.vieux": {"statut": "libre", "le": VIEUX},
            "lea.vivant": {"statut": "libre", "le": RECENT}, "lea.vide": {"statut": "libre", "le": RECENT}}
    assert P.a_vider(comptes, memo, T) == [{"onglet": "Lea", "handle": "lea.libre"}, {"onglet": "Lea", "handle": "lea.zero"}]


def test_ecriture_sur_la_ligne_relue_jamais_sur_l_ancien_numero():
    # le @ « lea.stock » était ligne 20 au début du passage ; le tri du matin l'a descendu ligne 31 entre-temps
    relus = [ligne(20, "GOOD", "lea.vivant", "Nino", followers="300"), ligne(31, "à créer", "lea.stock", "", followers="94", r7="0")]
    ecr, remplaces, vides = P.plan_ecritures(relus, [{"onglet": "Lea", "handle": "lea.stock", "nouveau": "lea.stock_x", "ligne": 20}],
                                             [], COLS)
    assert ecr == [("Lea!B31", [["lea.stock_x"]]), ("Lea!D31", [[""]]), ("Lea!F31", [[""]])]   # les chiffres de l'autre compte partent
    assert remplaces == {("Lea", "lea.stock")} and vides == 0
    assert not any(p.endswith("20") for p, _ in ecr)                      # le compte vivant de la ligne 20 n'est jamais touché


def test_remplacement_abandonne_si_la_ligne_a_change():
    rempl = [{"onglet": "Lea", "handle": "lea.stock", "nouveau": "lea.stock_x", "ligne": 20}]
    for relus in ([ligne(20, "à créer", "lea.stock", "Nino")],            # attribuée entre-temps : le clipper a peut-être le @
                  [ligne(20, "GOOD", "lea.stock", "")],                    # créée entre-temps
                  [ligne(20, "à créer", "lea.autre", "")],                 # @ changé à la main
                  [ligne(20, "à créer", "lea.stock"), ligne(40, "à créer", "lea.stock")]):   # en double : on ne devine pas
        assert P.plan_ecritures(relus, rempl, [], COLS) == ([], set(), 0)


def test_vider_les_chiffres_d_une_ligne_relue():
    relus = [ligne(12, "à créer", "lea.libre", "Nino", followers="142", rh="", r7="3"), ligne(13, "GOOD", "lea.libre2", "", followers="8")]
    ecr, remplaces, vides = P.plan_ecritures(relus, [], [{"onglet": "Lea", "handle": "lea.libre"},
                                                         {"onglet": "Lea", "handle": "lea.libre2"}], COLS)
    assert ecr == [("Lea!D12", [[""]]), ("Lea!F12", [[""]])] and vides == 1   # une ligne passée en GOOD garde ses chiffres


def test_scan_n_ecrit_rien_sur_une_ligne_a_creer():
    m = {**E._fiche_vide(), "existe": True, "followers": 142, "lu": True}
    with patch.object(E, "_followers_metricool", lambda h: None), patch.object(onboarding, "a_colonne", lambda champ, onglet="": True), \
            patch.object(E, "_valeurs_reels", lambda *a, **k: {"reels_hier": 0, "reels_7j": 0}):
        a_creer = E._ecritures_mesure({"handle": "lea.prise", "onglet": "Lea", "etat": "à créer", "followers": ""}, m, [], "2026-10-26", T)
        vivant = E._ecritures_mesure({"handle": "lea.vivant", "onglet": "Lea", "etat": "GOOD", "followers": ""}, m, [], "2026-10-26", T)
    assert a_creer == []                                                  # le compte d'un inconnu qui porte déjà ce nom
    assert [e["champ"] for e in vivant] == ["followers", "reels_hier", "reels_7j"]


def test_metricool_reste_ecrit_sur_une_ligne_a_creer():
    with patch.object(E, "_followers_metricool", lambda h: 37), patch.object(onboarding, "a_colonne", lambda champ, onglet="": True):
        out = E._ecritures_mesure({"handle": "lea.branche", "onglet": "Lea", "etat": "à créer", "followers": ""}, None, [], "2026-10-26", T)
    assert [(e["champ"], e["valeur"]) for e in out] == [("followers", 37)]   # branché à Metricool : c'est le nôtre
