"""Visibilité Instagram de chaque compte, dans le LOG, et contrôle des comptes des clippers (23/10/2026).

Gaëtan : « savoir si le compte est privé ou pas, le mettre dans le Google Sheet pour avoir une meilleure visibilité sur l'ensemble
des comptes, et savoir pour chaque clipper : ses deux comptes Instagram de croissance et son compte privé ».

Source : le statut relevé par le suivi Instagram (instagram_rapidapi, profil FlashAPI : is_private), déjà dans le store du suivi.
Un compte privé ne montre ni ses Reels ni ses vues à l'API : seuls ses followers et son nombre de publications sont suivis.

1. LOG (classeur des logins), chaque onglet créatrice : une colonne « Visibilité Insta » (Public / Privé / Introuvable), posée
   dans la première colonne libre après le bloc principal (en-tête vide ET colonne vide jusqu'en bas ; sinon l'onglet est laissé
   tel quel). Aucune colonne insérée, rien décalé. Le nom évite les mots-clés des autres colonnes (« ig », « compte », « statut »).
2. Onglet « IG · Visibilité » (App clippers · usage) : une ligne par anomalie :
   - compte marqué « Croissance » dans Utilisation mais privé (il ne touche personne) ;
   - compte marqué « privé » dans Utilisation mais public ;
   - clipper sans aucun compte privé, ou avec plusieurs comptes privés (un compte de croissance passé en privé ?) ;
   - compte vivant dans le LOG mais introuvable sur Instagram (renommé, banni ou faute de frappe) ;
   - compte « en appel » dans le LOG mais de nouveau visible sur Instagram (l'appel a abouti : repasser GOOD).
"""

import logging
import unicodedata

journal = logging.getLogger("visibilite_ig")

ENTETE_LOG = "Visibilité Insta"
ONGLET = "IG · Visibilité"
ENTETE = ["Créatrice", "Gérant", "@", "Utilisation", "Visibilité", "Problème"]
LIBELLES = {"public": "Public", "privé": "Privé", "introuvable": "Introuvable"}


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def libelle(store: dict, handle: str) -> str:
    """Pur : Public / Privé / Introuvable d'après le dernier relevé du suivi ; vide si le compte n'a pas encore été relu."""
    e = (store.get("comptes") or {}).get(str(handle or "").strip().lstrip("@").lower()) or {}
    return LIBELLES.get(e.get("statut"), "")


def colonne_libre(entete: list, lignes: list):
    """Pur : index de la colonne « Visibilité Insta » si elle existe, sinon la première colonne sans en-tête après le bloc
    principal, à condition qu'elle soit vide sur toutes les lignes. None si aucune colonne ne convient."""
    for i, h in enumerate(entete or []):
        if _n(h) == _n(ENTETE_LOG):
            return i
    noms = [i for i, h in enumerate(entete or []) if str(h).strip()]
    if not noms:
        return None
    # fin du bloc principal : le premier trou après la colonne « Lien GAML » (ou après la dernière colonne si pas de trou)
    i = next((k for k in range(len(entete)) if not str(entete[k]).strip()), len(entete))
    if any(len(l) > i and str(l[i]).strip() for l in lignes or []):
        return None
    return i


def valeurs_colonne(lignes: list, i_handle: int, store: dict) -> list:
    """Pur : la colonne à écrire (lignes 2 à N), une valeur par ligne du LOG, vide pour une ligne sans @ ou pas encore relue."""
    out = []
    for l in lignes or []:
        h = l[i_handle] if len(l) > i_handle else ""
        out.append([libelle(store, h) if str(h).strip() else ""])
    return out


def _gerant_clipper(g: str) -> bool:
    gn = _n(g)
    return bool(gn) and not any(m in gn for m in ("metricool", "rianah", "a mettre", "stock", "libre"))


def anomalies(comptes: list, store: dict, creatrices: set = None) -> list:
    """Pur : lignes du LOG (onboarding.lire_comptes) → anomalies [Créatrice, Gérant, @, Utilisation, Visibilité, Problème]."""
    creatrices = creatrices or set()
    out, par_clipper = [], {}
    for c in comptes or []:
        h = str(c.get("handle") or "").strip().lstrip("@").lower()
        etat = _n(c.get("etat"))
        appel = "appel" in etat
        if not h or not (etat.startswith("good") or etat.startswith("priv") or appel):
            continue
        v = libelle(store, h)
        u = str(c.get("utilisation") or "").strip()
        un = _n(u)
        cr = str(c.get("creatrice") or c.get("onglet") or "").strip()
        g = str(c.get("gerant") or "").strip()
        ligne = [cr, g, h, u, v or "pas encore relu"]
        if appel:
            # 26/10 : compte en appel de nouveau visible : l'appel a abouti, le LOG dit encore « appel »
            if v in ("Public", "Privé"):
                out.append(ligne + [f"compte en appel (« {c.get('etat')} ») mais visible sur Instagram : l'appel a abouti ? repasser GOOD dans le LOG"])
            continue
        if v == "Introuvable":
            out.append(ligne + ["introuvable sur Instagram : @ changé, compte banni ou faute de frappe dans le LOG"])
            continue
        if "croissance" in un and v == "Privé":
            out.append(ligne + ["compte de croissance en privé : ses Reels ne touchent personne"])
        if "priv" in un and v == "Public":
            out.append(ligne + ["compte privé resté public"])
        if v and _gerant_clipper(g) and _n(g).split()[0] not in creatrices and "creatrice" not in un:
            par_clipper.setdefault((cr, g), []).append((h, v))
    for (cr, g), lst in sorted(par_clipper.items()):
        prives = [h for h, v in lst if v == "Privé"]
        publics = [h for h, v in lst if v == "Public"]
        if not prives and len(publics) >= 2:
            out.append([cr, g, ", ".join(publics), "", "Public", "aucun compte privé pour ce clipper"])
        elif len(prives) >= 2:
            out.append([cr, g, ", ".join(prives), "", "Privé", f"{len(prives)} comptes privés : un compte de croissance est passé en privé ?"])
    return out


async def passage(store: dict) -> dict:
    """Écrit la colonne « Visibilité Insta » dans chaque onglet du LOG et l'onglet des anomalies. Jamais d'exception."""
    import google_api
    import onboarding
    bilan = {"onglets": [], "ignores": [], "anomalies": 0}
    if not google_api.actif():
        return bilan
    try:
        comptes = await onboarding.lire_comptes()
        for titre in await onboarding.onglets_logins():
            lignes = await google_api.sheets_lire(onboarding.CLASSEUR_LOGINS_ID, f"{onboarding.onglet_a1(titre)}!A1:AF")
            if not lignes:
                continue
            entete, corps = lignes[0], lignes[1:]
            cols = onboarding._colonnes_trouvees(entete)
            if "handle" not in cols:
                continue
            i = colonne_libre(entete, corps)
            if i is None:
                bilan["ignores"].append(titre)
                journal.warning("Visibilité Insta : pas de colonne libre dans l'onglet %s, rien écrit", titre)
                continue
            lettre = google_api.colonne(i)
            ecritures = [(f"{onboarding.onglet_a1(titre)}!{lettre}1", [[ENTETE_LOG]])]
            if corps:
                ecritures.append((f"{onboarding.onglet_a1(titre)}!{lettre}2:{lettre}{len(corps) + 1}", valeurs_colonne(corps, cols["handle"], store)))
            await google_api.sheets_ecrire_plusieurs(onboarding.CLASSEUR_LOGINS_ID, ecritures)
            bilan["onglets"].append(f"{titre} ({lettre})")
        lignes_anomalies = anomalies(comptes, store, onboarding.creatrices_connues(comptes))
        bilan["anomalies"] = len(lignes_anomalies)
        import paie_clics
        import pilotage
        classeur = await paie_clics._classeur_usage()
        if classeur:
            await pilotage._ecrire(classeur, ONGLET, ENTETE, lignes_anomalies)
    except Exception as erreur:                                         # noqa: BLE001 — le suivi est déjà écrit
        bilan["erreur"] = f"{type(erreur).__name__} : {str(erreur)[:160]}"
        journal.warning("Visibilité Insta : %s", bilan["erreur"])
    return bilan
