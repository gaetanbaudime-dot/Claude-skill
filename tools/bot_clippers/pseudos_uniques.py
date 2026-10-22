"""Pseudos uniques pour les comptes à créer (22/10/2026, Gaëtan : « des fois les noms d'utilisateur sont déjà pris : le clipper
crée une variante, le @ du classeur ne correspond plus, on scrape le compte de quelqu'un d'autre et on perd le suivi »).

Avant qu'un compte soit remis à un clipper, son @ prévu est vérifié sur Instagram (FlashAPI, /ig/user_id/ : 1 requête) :
- libre : rien à faire, revérifié tous les REVERIFIER_J jours (un nom libre peut être pris entre-temps) ;
- pris et en stock (à créer, sans gérant) : remplacé dans la cellule « @ IG » du LOG par une variante libre et unique
  (points, tirets bas, x ou 1 au début ou à la fin), elle-même vérifiée ; le clipper reçoit directement un @ qui marche ;
- pris mais déjà attribué à un clipper (à créer, avec gérant) : jamais réécrit (il a peut-être déjà le @ en main), signalé.

Tout est écrit dans l'onglet « IG · Pseudos » du tableur App clippers · usage. Une réponse douteuse de l'API (erreur, quota) ne
décide rien : le @ est revu au passage suivant. Le contrôle ne garantit pas qu'Instagram acceptera le nom (noms récemment
supprimés ou réservés), il évite seulement les noms déjà portés par un compte visible.
"""

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("pseudos_uniques")

ONGLET = "IG · Pseudos"
ENTETE = ["Créatrice", "Onglet", "Ligne", "@ prévu", "Statut", "Nouveau @", "Gérant", "Vérifié le"]
REVERIFIER_J = int(os.environ.get("PSEUDOS_REVERIFIER_J", "7") or 7)
PAR_PASSAGE = int(os.environ.get("PSEUDOS_PAR_PASSAGE", "200") or 200)   # requêtes au plus par passage (vérifs + variantes)
VARIANTES_MAX = 6                                                        # variantes essayées pour un @ pris
RE_VALIDE = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def valide(h: str) -> bool:
    """Règles d'Instagram : lettres, chiffres, point, tiret bas ; 30 caractères ; pas de point au début, à la fin ni doublé."""
    return bool(RE_VALIDE.match(h or ""))


def variantes(handle: str) -> list:
    """Pur : variantes du @ (proposées par Gaëtan : points, tirets bas, x ou 1 au début ou à la fin), valides, sans doublon,
    dans l'ordre d'essai. La dernière ajoute deux chiffres tirés du nom (stables d'un passage à l'autre)."""
    b = str(handle or "").strip().lstrip("@").lower()
    mots = [m for m in re.split(r"[._]+", b) if m]
    out = []
    candidats = []
    if len(mots) > 1:
        candidats += [".".join(mots), "_".join(mots)]
    candidats += [f"{b}_x", f"x_{b}", f"{b}.x", f"x.{b}", f"{b}1", f"1{b}", f"{b}_1", f"_{b}_", f"{b}__"]
    candidats.append(f"{b}{int(hashlib.sha1(b.encode()).hexdigest(), 16) % 90 + 10}")
    for c in candidats:
        c = c[:30].rstrip(".")
        if c != b and valide(c) and c not in out:
            out.append(c)
    return out


def a_controler(comptes: list) -> list:
    """Pur : les lignes « à créer » du LOG → [{onglet, ligne, handle, creatrice, gerant, stock}] (stock = sans gérant)."""
    out, vus = [], set()
    for c in comptes or []:
        if "creer" not in _n(c.get("etat")):
            continue
        h = str(c.get("handle") or "").strip().lstrip("@").lower()
        if not h or h in vus:
            continue
        vus.add(h)
        g = str(c.get("gerant") or "").strip()
        stock = not g or _n(g) in ("stock", "libre", "-")
        out.append({"onglet": c.get("onglet"), "ligne": c.get("ligne"), "handle": h, "creatrice": c.get("creatrice") or c.get("onglet"),
                    "gerant": "" if stock else g, "stock": stock})
    return out


def a_revoir(memo: dict, h: str, maintenant: datetime) -> bool:
    """Pur : jamais vérifié, ou vérifié libre il y a plus de REVERIFIER_J jours (un @ pris le reste : pas revérifié)."""
    m = (memo or {}).get(h)
    if not m:
        return True
    if m.get("statut") == "pris":
        return False
    try:
        return maintenant - datetime.fromisoformat(m["le"]) > timedelta(days=REVERIFIER_J)
    except (KeyError, ValueError, TypeError):
        return True


async def existe(session, handle: str):
    """True si un compte visible porte ce @, False s'il est libre, None si la réponse ne permet pas de trancher."""
    import instagram_rapidapi as I
    chemin, params = I.API["id"]
    code, corps = await I.appeler(session, chemin, params(handle))
    if code == 200 and I.lire_id(corps):
        return True
    if I.introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False):
        return False
    return None


async def passage(session, store: dict, comptes: list, maintenant: datetime = None) -> dict:
    """Vérifie les @ à créer, remplace dans le LOG ceux du stock qui sont pris. Renvoie le bilan ; écrit l'onglet IG · Pseudos."""
    import instagram_rapidapi as I
    import google_api
    import onboarding
    maintenant = maintenant or datetime.now(timezone.utc)
    memo = store.setdefault("pseudos", {})
    pris_ailleurs = {str(c.get("handle") or "").strip().lstrip("@").lower() for c in comptes or []}
    bilan = {"verifies": 0, "libres": 0, "pris": 0, "remplaces": 0, "signales": 0, "doute": 0, "requetes": 0}
    n0 = I._jour["n"]
    for ligne in a_controler(comptes):
        if I._jour["n"] - n0 >= PAR_PASSAGE or not I._quota_ok(I.RESERVE):
            break
        h = ligne["handle"]
        if not a_revoir(memo, h, maintenant):
            continue
        r = await existe(session, h)
        bilan["verifies"] += 1
        if r is None:
            bilan["doute"] += 1
            continue
        if r is False:
            bilan["libres"] += 1
            memo[h] = {"statut": "libre", "le": maintenant.isoformat(timespec="seconds")}
            continue
        bilan["pris"] += 1
        if not ligne["stock"]:
            bilan["signales"] += 1
            memo[h] = {"statut": "pris", "attribue": True, "le": maintenant.isoformat(timespec="seconds")}
            continue
        nouveau = None
        for v in variantes(h)[:VARIANTES_MAX]:
            if v in pris_ailleurs or I._jour["n"] - n0 >= PAR_PASSAGE:
                continue
            rv = await existe(session, v)
            if rv is False:
                nouveau = v
                break
        if not nouveau:
            memo[h] = {"statut": "pris", "le": maintenant.isoformat(timespec="seconds"), "sans_variante": True}
            continue
        col = (onboarding._colonnes_lues_par_onglet.get(ligne["onglet"]) or {}).get("handle")
        if col is None:
            memo[h] = {"statut": "pris", "le": maintenant.isoformat(timespec="seconds"), "sans_variante": True}
            continue
        lettre = chr(ord("A") + col)
        try:
            await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, f"{onboarding.onglet_a1(ligne['onglet'])}!{lettre}{ligne['ligne']}", [[nouveau]])
        except Exception as erreur:                                     # noqa: BLE001 — revu au passage suivant
            journal.warning("Pseudo %s non remplacé : %s", h, str(erreur)[:160])
            continue
        pris_ailleurs.add(nouveau)
        bilan["remplaces"] += 1
        memo[h] = {"statut": "pris", "remplace_par": nouveau, "le": maintenant.isoformat(timespec="seconds")}
        memo[nouveau] = {"statut": "libre", "le": maintenant.isoformat(timespec="seconds"), "variante_de": h}
        journal.info("Pseudo pris : %s → %s (%s, ligne %s)", h, nouveau, ligne["onglet"], ligne["ligne"])
    bilan["requetes"] = I._jour["n"] - n0
    try:
        import paie_clics
        import pilotage
        classeur = await paie_clics._classeur_usage()
        if classeur:
            await pilotage._ecrire(classeur, ONGLET, ENTETE, lignes_onglet(comptes, memo))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Onglet %s non écrit : %s", ONGLET, str(erreur)[:160])
    return bilan


def lignes_onglet(comptes: list, memo: dict) -> list:
    """Pur : une ligne par @ à créer vérifié, les problèmes en haut (pris attribué, pris sans variante), puis les remplacés."""
    libelle = {"libre": "libre"}
    out = []
    for l in a_controler(comptes):
        m = (memo or {}).get(l["handle"])
        if not m:
            statut = "pas encore vérifié"
        elif m.get("statut") == "libre":
            statut = libelle["libre"] + (f" (remplace {m['variante_de']}, pris)" if m.get("variante_de") else "")
        elif m.get("attribue"):
            statut = "pris, déjà attribué : donner un autre @ au clipper"
        elif m.get("remplace_par"):
            statut = "pris, remplacé dans le LOG"
        else:
            statut = "pris, aucune variante libre trouvée"
        out.append([str(l["creatrice"] or ""), str(l["onglet"] or ""), str(l["ligne"] or ""), l["handle"], statut,
                    (m or {}).get("remplace_par", ""), l["gerant"], (m or {}).get("le", "")])
    ordre = {"pris, déjà attribué : donner un autre @ au clipper": 0, "pris, aucune variante libre trouvée": 1, "pris, remplacé dans le LOG": 2,
             "pas encore vérifié": 3, "libre": 4}
    out.sort(key=lambda r: (ordre.get(r[4].split(" (")[0], 5), r[0], r[3]))
    return out
