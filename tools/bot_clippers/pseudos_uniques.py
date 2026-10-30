"""Pseudos uniques pour les comptes à créer (22/10/2026, Gaëtan : « des fois les noms d'utilisateur sont déjà pris : le clipper
crée une variante, le @ du classeur ne correspond plus, on scrape le compte de quelqu'un d'autre et on perd le suivi »).

Avant qu'un compte soit remis à un clipper, son @ prévu est vérifié sur Instagram (FlashAPI, /ig/user_id/ : 1 requête) :
- libre : rien à faire, revérifié tous les REVERIFIER_J jours (un nom libre peut être pris entre-temps) ;
- pris et en stock (à créer, sans gérant) : remplacé dans la cellule « @ IG » du LOG par une variante libre et unique
  (points, tirets bas, x ou 1 au début ou à la fin), elle-même vérifiée ; le clipper reçoit directement un @ qui marche ;
- pris mais déjà attribué à un clipper (à créer, avec gérant) : jamais réécrit (il a peut-être déjà le @ en main), signalé.

26/10 : chaque écriture retrouve sa ligne par son @ dans le LOG relu juste avant (jamais un numéro de ligne vieux de plusieurs
minutes : le tri du matin déplace les lignes) ; une ligne « à créer » dont le @ est libre sur Instagram perd ses followers et ses
Reels (des chiffres d'un autre compte : aucun compte ne porte ce nom).

27/10 : les @ attribués et les PROCHAINS premiers du stock de chaque créatrice sont revérifiés chaque jour (les autres chaque
semaine). Limite connue : Instagram refuse aussi des noms qu'aucun compte visible ne porte (comptes supprimés ou désactivés) ; ceux-là
passent pour libres. Le suivi retrouve alors le compte sous la suggestion d'Instagram (instagram_rapidapi.variantes_instagram).

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
    # 30/10 (Gaëtan : « tu remplaces les points par des tirets du bas, les tirets du bas par… des points, ou alors tu rajoutes XO à
    # la fin ») : ses variantes d'abord, les mêmes que le bot au moment de donner un @ (arobase_libre.variantes)
    try:
        import arobase_libre
        candidats = list(arobase_libre.variantes(b))
    except Exception:                                                   # noqa: BLE001
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


PROCHAINS = int(os.environ.get("PSEUDOS_PROCHAINS", "10") or 10)     # 27/10 : les 10 prochains @ à créer par créatrice…
REVERIFIER_PROCHAINS_H = int(os.environ.get("PSEUDOS_PROCHAINS_H", "20") or 20)   # … revérifiés chaque jour (20 h : 1 passage sur 3)


def prochains(comptes: list, n: int = PROCHAINS) -> set:
    """Pur (27/10, Gaëtan : « une fois par jour, vérifier que les @ à créer sont bien libres, au moins les 10 prochains par
    créatrice ; le clipper ne doit jamais changer de @, sinon on perd le suivi ») : les @ à créer attribués à un clipper (création
    imminente) et les n premiers du stock de chaque onglet, dans l'ordre du LOG (les prochains distribués)."""
    out, par_onglet = set(), {}
    for l in a_controler(comptes):
        if not l["stock"]:
            out.add(l["handle"])
        elif par_onglet.get(l["onglet"], 0) < n:
            par_onglet[l["onglet"]] = par_onglet.get(l["onglet"], 0) + 1
            out.add(l["handle"])
    return out


def a_revoir(memo: dict, h: str, maintenant: datetime, heures: int = None) -> bool:
    """Pur : jamais vérifié, ou vérifié libre il y a plus de REVERIFIER_J jours (`heures` : délai plus court pour les prochains).
    Un @ pris ou déjà créé le reste : pas revérifié."""
    m = (memo or {}).get(h)
    if not m:
        return True
    if m.get("statut") in ("pris", "cree"):
        return False
    try:
        delai = timedelta(hours=heures) if heures else timedelta(days=REVERIFIER_J)
        return maintenant - datetime.fromisoformat(m["le"]) > delai
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
    import onboarding
    maintenant = maintenant or datetime.now(timezone.utc)
    memo = store.setdefault("pseudos", {})
    pris_ailleurs = {str(c.get("handle") or "").strip().lstrip("@").lower() for c in comptes or []}
    bilan = {"verifies": 0, "libres": 0, "pris": 0, "remplaces": 0, "signales": 0, "doute": 0, "requetes": 0, "chiffres_effaces": 0}
    remplacements = []
    n0 = I._jour["n"]
    proch = prochains(comptes)
    for ligne in sorted(a_controler(comptes), key=lambda l: l["handle"] not in proch):    # les prochains d'abord
        if I._jour["n"] - n0 >= PAR_PASSAGE or not I._quota_ok(I.RESERVE):
            break
        h = ligne["handle"]
        if not a_revoir(memo, h, maintenant, REVERIFIER_PROCHAINS_H if h in proch else None):
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
        if not ligne["stock"] and (memo.get(h) or {}).get("statut") == "libre":
            # 27/10 : vu libre, attribué, maintenant pris : c'est le clipper qui l'a créé (le suivi Instagram le relit)
            memo[h] = {**memo[h], "statut": "cree", "vu_cree_le": maintenant.isoformat(timespec="seconds")}
            continue
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
        if (onboarding._colonnes_lues_par_onglet.get(ligne["onglet"]) or {}).get("handle") is None:
            memo[h] = {"statut": "pris", "le": maintenant.isoformat(timespec="seconds"), "sans_variante": True}
            continue
        pris_ailleurs.add(nouveau)
        remplacements.append({"onglet": ligne["onglet"], "handle": h, "nouveau": nouveau, "ligne": ligne["ligne"]})
    # 26/10 (Gaëtan : « ces comptes ne sont pas créés sur Instagram et n'ont pas de followers… je pense qu'on a un problème
    # d'attribution ») : les écritures dans le LOG retrouvent leur ligne par son @ dans un classeur relu juste avant (plus jamais le
    # numéro de ligne lu au début du passage : le tri du matin peut déplacer les lignes pendant les minutes de vérification), et les
    # chiffres d'un compte qui n'existe pas sont effacés.
    faits = await _ecrire_log(remplacements, a_vider(comptes, memo, maintenant))
    for r in remplacements:
        if (r["onglet"], r["handle"]) not in faits["remplaces"]:
            continue                                                     # ligne déplacée, attribuée ou modifiée : revue au passage suivant
        bilan["remplaces"] += 1
        memo[r["handle"]] = {"statut": "pris", "remplace_par": r["nouveau"], "le": maintenant.isoformat(timespec="seconds")}
        memo[r["nouveau"]] = {"statut": "libre", "le": maintenant.isoformat(timespec="seconds"), "variante_de": r["handle"]}
        journal.info("Pseudo pris : %s → %s (%s)", r["handle"], r["nouveau"], r["onglet"])
    bilan["chiffres_effaces"] = faits["vides"]
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


CHIFFRES = ("followers", "reels_hier", "reels_7j")                     # colonnes remplies par le bot : Followers, Reels Hier, Reels 7 j


def _a_creer(c: dict) -> bool:
    return "creer" in _n(c.get("etat"))


def _stock(c: dict) -> bool:
    g = str(c.get("gerant") or "").strip()
    return not g or _n(g) in ("stock", "libre", "-")


def a_vider(comptes: list, memo: dict, maintenant: datetime) -> list:
    """Pur (26/10) : les lignes « à créer » dont le @ a été vu LIBRE sur Instagram il y a moins de REVERIFIER_J jours (aucun compte
    ne porte ce nom) et qui portent pourtant des followers ou des Reels : des chiffres d'un autre compte, restés quand le @ a été
    changé (l'ancien scan Apify lisait aussi les @ à créer et écrivait les followers du compte qu'il trouvait, souvent celui d'un
    inconnu qui portait déjà ce nom). [{onglet, handle}]. Un @ pris n'y est jamais : ce peut être le compte du clipper."""
    out, vus = [], set()
    for c in comptes or []:
        h = str(c.get("handle") or "").strip().lstrip("@").lower()
        if not h or not _a_creer(c) or (c.get("onglet"), h) in vus:
            continue
        m = (memo or {}).get(h) or {}
        if m.get("statut") != "libre" or a_revoir(memo, h, maintenant):
            continue
        if any(str(c.get(k) or "").strip() for k in CHIFFRES):
            vus.add((c.get("onglet"), h))
            out.append({"onglet": c.get("onglet"), "handle": h})
    return out


def plan_ecritures(relus: list, remplacements: list, vider: list, colonnes: dict) -> tuple:
    """Pur (26/10) : les cellules à écrire, d'après le LOG RELU. Chaque écriture va sur la ligne qui porte ENCORE ce @ dans son
    onglet et qui est encore « à créer » (un remplacement : encore en stock) ; une ligne qui a changé entre-temps n'est pas touchée.
    Un @ remplacé perd aussi ses followers et ses Reels (ceux du compte qui portait déjà le nom). `colonnes` = {onglet: {champ:
    index}} (en-têtes réels). Renvoie ([(plage, [[valeur]])], {(onglet, @) remplacés}, nombre de lignes vidées)."""
    import google_api
    import onboarding
    index = {}
    for r in relus or []:
        h = str(r.get("handle") or "").strip().lstrip("@").lower()
        if h:
            index.setdefault((r.get("onglet"), h), []).append(r)
    ecr, remplaces, vides = [], set(), 0

    def cellule(r, champ):
        i = (colonnes.get(r.get("onglet")) or {}).get(champ)
        return None if i is None else f"{onboarding.onglet_a1(r['onglet'])}!{google_api.colonne(i)}{r['ligne']}"

    def vider_chiffres(r):
        n = 0
        for champ in CHIFFRES:
            p = cellule(r, champ)
            if p and str(r.get(champ) or "").strip():
                ecr.append((p, [[""]]))
                n += 1
        return n
    deja = set()
    for x in remplacements or []:
        lignes = [r for r in index.get((x["onglet"], x["handle"]), []) if _a_creer(r) and _stock(r)]
        if len(lignes) != 1 or not cellule(lignes[0], "handle"):
            continue                                                     # disparue, attribuée, passée en GOOD, ou en double
        ecr.append((cellule(lignes[0], "handle"), [[x["nouveau"]]]))
        vider_chiffres(lignes[0])
        remplaces.add((x["onglet"], x["handle"]))
        deja.add((x["onglet"], x["handle"]))
    for x in vider or []:
        if (x["onglet"], x["handle"]) in deja:
            continue
        lignes = [r for r in index.get((x["onglet"], x["handle"]), []) if _a_creer(r)]
        if len(lignes) == 1 and vider_chiffres(lignes[0]):
            vides += 1
    return ecr, remplaces, vides


async def _ecrire_log(remplacements: list, vider: list) -> dict:
    """Relit le LOG, puis écrit en un appel ce que plan_ecritures garde. Jamais d'exception : rien d'écrit = revu au passage suivant."""
    import google_api
    import onboarding
    if not remplacements and not vider:
        return {"remplaces": set(), "vides": 0}
    try:
        relus = await onboarding.lire_comptes()
        ecr, remplaces, vides = plan_ecritures(relus, remplacements, vider, dict(onboarding._colonnes_lues_par_onglet))
        if ecr:
            await google_api.sheets_ecrire_plusieurs(onboarding.CLASSEUR_LOGINS_ID, ecr)
        if vides:
            journal.info("Pseudos : followers / Reels effacés sur %d ligne(s) « à créer » dont le @ n'existe pas sur Instagram", vides)
        return {"remplaces": remplaces, "vides": vides}
    except Exception as erreur:                                         # noqa: BLE001 — revu au passage suivant
        journal.warning("Pseudos : LOG non écrit (%s)", str(erreur)[:160])
        return {"remplaces": set(), "vides": 0}


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
        elif m.get("statut") == "cree":
            statut = "créé sur Instagram : passer GOOD dans le LOG"
        elif m.get("attribue"):
            statut = "pris, déjà attribué : donner un autre @ au clipper"
        elif m.get("remplace_par"):
            statut = "pris, remplacé dans le LOG"
        else:
            statut = "pris, aucune variante libre trouvée"
        out.append([str(l["creatrice"] or ""), str(l["onglet"] or ""), str(l["ligne"] or ""), l["handle"], statut,
                    (m or {}).get("remplace_par", ""), l["gerant"], (m or {}).get("le", "")])
    ordre = {"créé sur Instagram : passer GOOD dans le LOG": 0, "pris, déjà attribué : donner un autre @ au clipper": 0, "pris, aucune variante libre trouvée": 1, "pris, remplacé dans le LOG": 2,
             "pas encore vérifié": 3, "libre": 4}
    out.sort(key=lambda r: (ordre.get(r[4].split(" (")[0], 5), r[0], r[3]))
    return out
