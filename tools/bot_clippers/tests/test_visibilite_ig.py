"""23/10 : colonne « Visibilité Insta » du LOG et anomalies des comptes des clippers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import onboarding  # noqa: E402
import visibilite_ig as V  # noqa: E402

STORE = {"comptes": {"pub1": {"statut": "public"}, "pub2": {"statut": "public"}, "priv1": {"statut": "privé"},
                     "priv2": {"statut": "privé"}, "mort": {"statut": "introuvable"}, "c1": {"statut": "public"}}}


def test_libelles_et_colonne():
    assert V.libelle(STORE, "@Priv1") == "Privé" and V.libelle(STORE, "mort") == "Introuvable" and V.libelle(STORE, "inconnu") == ""
    entete = ["ETAT", "@ IG ", "Gérant", "Lien GAML associé", "", "", "Mois", "Visiteurs"]
    assert V.colonne_libre(entete, [["GOOD", "pub1", "Léo", "x"]]) == 4
    assert V.colonne_libre(entete, [["GOOD", "pub1", "Léo", "x", "note"]]) is None          # colonne libre mais remplie : on n'y touche pas
    assert V.colonne_libre(["ETAT", "@ IG", "Visibilité Insta", "Gérant"], [["a", "b", "Public"]]) == 2   # déjà posée : réutilisée
    assert V.colonne_libre(["ETAT", "@ IG", "Gérant"], []) == 3                                # en-tête plein : juste après
    assert V.valeurs_colonne([["GOOD", "pub1"], ["à créer", ""], ["GOOD", "priv1"], []], 1, STORE) == [["Public"], [""], ["Privé"], [""]]


def test_le_nom_de_colonne_ne_capte_aucun_champ_du_log():
    entete = ["ETAT", "@ IG ", "MDP", "Mail ", "Phone", "Gérant", "Utilisation", "Lien GAML associé", V.ENTETE_LOG]
    assert len(entete) - 1 not in onboarding._colonnes_trouvees(entete).values()


def test_anomalies():
    def l(h, g, u="Clipper", etat="GOOD", cr="Chloé"):
        return {"handle": h, "gerant": g, "utilisation": u, "etat": etat, "creatrice": cr, "onglet": cr}
    comptes = [l("c1", "Chloé", "Compte de la créatrice"),
               l("pub1", "Léo"), l("pub2", "Léo"),                                   # aucun compte privé
               l("priv1", "Max", "Compte Croissance"), l("priv2", "Max"),             # croissance en privé + 2 privés
               l("pub1", "Rianah (Metricool)"),                                       # pas un clipper : ignoré
               l("mort", "Zoé"), l("pub2", "Zoé", etat="à créer"),
               l("x9", "Ana", "Compte privé avec lien")]                              # pas encore relu : rien
    a = V.anomalies(comptes, {**STORE, "comptes": {**STORE["comptes"]}}, {"chloe"})
    problemes = {(r[1], r[5].split(" :")[0].split(" (")[0]) for r in a}
    assert ("Léo", "aucun compte privé pour ce clipper") in problemes
    assert ("Max", "compte de croissance en privé") in problemes and ("Max", "2 comptes privés") in problemes
    assert ("Zoé", "introuvable sur Instagram") in problemes
    assert not any(r[1] in ("Chloé", "Rianah (Metricool)", "Ana") for r in a)
    pub_prive = V.anomalies([l("pub1", "Léo", "Compte privé avec lien")], STORE)
    assert pub_prive[0][5] == "compte privé resté public"


def test_compte_en_appel_revenu_signale():
    store = {"comptes": {"rev": {"statut": "public"}, "susp": {"statut": "introuvable"}}}
    a = V.anomalies([{"handle": "rev", "gerant": "Yves", "etat": "Faire appel", "creatrice": "Sarah"},
                     {"handle": "susp", "gerant": "Yves", "etat": "APPEL A FAIRE", "creatrice": "Sarah"}], store)
    assert len(a) == 1 and a[0][2] == "rev" and "l'appel a abouti" in a[0][5]


def test_compte_a_creer_cree_par_le_clipper():
    store = {"comptes": {"neuf": {"statut": "public"}, "inconnu": {"statut": "public"}},
             "pseudos": {"neuf": {"statut": "cree"}, "inconnu": {"statut": "pris", "attribue": True}}}
    lignes = [{"handle": "neuf", "gerant": "Mavie", "etat": "à créer", "creatrice": "Sarah"},
              {"handle": "inconnu", "gerant": "Mavie", "etat": "à créer", "creatrice": "Sarah"}]
    a = V.anomalies(lignes, store)
    assert [(r[2], r[5]) for r in a] == [("neuf", "compte créé sur Instagram : passer GOOD dans le LOG")]
    col = V.valeurs_colonne([["à créer", "neuf"], ["à créer", "inconnu"], ["GOOD", "inconnu"]], 1, store, 0)
    assert col == [["Public"], [""], ["Public"]]


def test_compte_cree_passe_good_seulement_si_prouve():
    store = {"comptes": {"neuf": {"statut": "public"}, "var": {"statut": "public", "renomme_en": "var_x"},
                         "inconnu": {"statut": "public"}, "pasencore": {"statut": "introuvable"}},
             "pseudos": {"neuf": {"statut": "cree"}, "var": {"statut": "cree", "cree_sous": "var_x"},
                         "inconnu": {"statut": "pris", "attribue": True}, "pasencore": {"statut": "libre"}}}
    lignes = [["à créer", "neuf"], ["À créer", "var"], ["à créer", "inconnu"], ["à créer", "pasencore"], ["GOOD", "neuf"], ["BAN", "neuf"]]
    assert V.a_passer_good(lignes, 1, 0, store) == [(2, "neuf")]          # ligne 2 du LOG ; jamais une autre valeur réécrite
