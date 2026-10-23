"""Reels des comptes branchés à Metricool, versés dans le suivi Instagram (22/10/2026).

Gaëtan : « itsvanlifesophie, c'est Rianah qui le gère sur Metricool, il y a une quantité de Reels astronomique : compare avec
Metricool ». Contrôle fait le 22/10 : sur 180 jours, Metricool voit 274 Reels sur ce compte, l'API RapidAPI (FlashAPI) 17 ;
lapetitesophievanlife 238 contre 50, iamjadetora 194 contre 55. Les vues concordent quand les deux voient le même Reel (4 750 /
4 926). Pour les comptes branchés à Metricool, Metricool (données officielles d'Instagram) devient donc la source des Reels.

Deux entrées, fusionnées dans le store du suivi (instagram_rapidapi) avant l'écriture des onglets IG · … :
1. l'onglet « IG · Reels Metricool » du tableur App clippers · usage : colonnes @, Code, Publié le, Vues, Likes, Commentaires.
   Il sert de sauvegarde visible et d'import (le 22/10, rempli depuis le connecteur Metricool) ; il est réécrit à chaque passage
   avec tous les Reels venus de Metricool.
2. l'API REST de Metricool, si METRICOOL_API_KEY (et METRICOOL_USER_ID) sont posés : les routes déjà utilisées par le dépôt
   (metricool_comptes : admin/simpleProfiles, v2/analytics/brand-summary/posts jour par jour). 180 jours la première fois pour
   un compte, puis 45 jours au premier passage du jour et 10 jours aux autres (les vues montent pendant des semaines).

Fusion : un Reel est ajouté s'il manque ; ses vues prennent la plus grande valeur lue (des vues ne baissent pas) ; jamais un 0
inventé. Jamais d'exception : une erreur est notée dans le bilan.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("metricool_reels")

ONGLET = "IG · Reels Metricool"
ENTETE = ["@", "Code", "Lien", "Publié le", "Vues", "Likes", "Commentaires", "Relu le"]
JOURS_PREMIER = int(os.environ.get("METRICOOL_REELS_PREMIER_J", "180") or 180)
JOURS_LONGUE = int(os.environ.get("METRICOOL_REELS_LONGUE_J", "45") or 45)
JOURS_COURTE = int(os.environ.get("METRICOOL_REELS_COURTE_J", "10") or 10)


def _entier(v):
    try:
        return None if v is None or v == "" or isinstance(v, bool) else int(float(str(v).replace(" ", "").replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _cle(h) -> str:
    return str(h or "").strip().lstrip("@").lower()


def lignes_import(valeurs: list) -> list:
    """Pur : les lignes de l'onglet (en-tête compris) → [{handle, code, publie, vues, likes, commentaires}] lisibles."""
    if not valeurs:
        return []
    tete = [str(x).strip() for x in valeurs[0]]
    def col(nom):
        return tete.index(nom) if nom in tete else None
    i_h, i_c, i_p, i_v, i_l, i_m = (col(n) for n in ("@", "Code", "Publié le", "Vues", "Likes", "Commentaires"))
    if None in (i_h, i_c, i_p):
        return []
    out = []
    for r in valeurs[1:]:
        r = list(r) + [""] * 10
        h, code, publie = _cle(r[i_h]), str(r[i_c]).strip(), str(r[i_p]).strip()
        if not h or not code or not publie:
            continue
        out.append({"handle": h, "code": code, "publie": publie, "vues": _entier(r[i_v]) if i_v is not None else None,
                    "likes": _entier(r[i_l]) if i_l is not None else None, "commentaires": _entier(r[i_m]) if i_m is not None else None})
    return out


def fusionner(store: dict, handle: str, reels: list, maintenant: datetime) -> int:
    """Pur (sur le store) : verse des Reels Metricool dans store['reels'][handle]. Renvoie le nombre de Reels ajoutés."""
    d = store.setdefault("reels", {}).setdefault(_cle(handle), {})
    ajoutes = 0
    for r in reels or []:
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        e = d.get(code)
        if e is None:
            e, ajoutes = {}, ajoutes + 1
        e["publie"] = e.get("publie") or r.get("publie")
        for k in ("vues", "likes", "commentaires"):
            v = r.get(k)
            if v is not None:
                e[k] = max(int(e.get(k) or 0), int(v)) if e.get(k) is not None else int(v)
        e["maj"] = maintenant.isoformat(timespec="seconds")
        e["metricool"] = True
        d[code] = e
    return ajoutes


def lignes_onglet(store: dict) -> list:
    """Pur : tous les Reels venus de Metricool, du plus récent au plus ancien."""
    out = []
    for h, reels in (store.get("reels") or {}).items():
        for code, r in reels.items():
            if not r.get("metricool"):
                continue
            txt = lambda v: "" if v is None else str(v)                     # noqa: E731
            out.append([h, code, f"https://www.instagram.com/reel/{code}/", r.get("publie") or "", txt(r.get("vues")),
                        txt(r.get("likes")), txt(r.get("commentaires")), r.get("maj") or ""])
    out.sort(key=lambda x: x[3], reverse=True)
    return out


async def _rest(store: dict, suivis: set, maintenant: datetime, longue: bool, bilan: dict):
    import metricool_comptes as M
    if not M.METRICOOL_API_KEY:
        bilan["rest"] = "sans clé (METRICOOL_API_KEY absente)"
        return
    try:
        marques, _ = M.marques_instagram(M._liste(await M._get(M.ROUTE_MARQUES, {})))
    except Exception as erreur:                                         # noqa: BLE001
        bilan["rest"] = f"marques illisibles ({str(erreur)[:120]})"
        return
    faits = store.setdefault("etat", {}).setdefault("metricool_reels", {})
    lus = []
    for cle, mq in marques.items():
        h = _cle(cle)
        if h not in suivis:
            continue
        jours = JOURS_PREMIER if not faits.get(h) else (JOURS_LONGUE if longue else JOURS_COURTE)
        debut = maintenant - timedelta(days=jours)
        try:
            pubs = await M._publications(mq, debut, maintenant)
            reels, *_ = M.reels_de(pubs, M._fuseau(mq.get("tz")), debut, maintenant)
        except Exception as erreur:                                     # noqa: BLE001 — ce compte au passage suivant
            bilan.setdefault("erreurs", []).append(f"{h} : {str(erreur)[:100]}")
            continue
        bilan["ajoutes"] = bilan.get("ajoutes", 0) + fusionner(store, h, reels, maintenant)
        faits[h] = maintenant.isoformat(timespec="seconds")
        lus.append(f"{h} ({len(reels)} Reels sur {jours} j)")
    bilan["rest"] = " ; ".join(lus) or "aucun compte suivi branché à Metricool"


async def passage(store: dict, comptes: list, maintenant: datetime = None, longue: bool = False) -> dict:
    """Import de l'onglet + relevé REST, fusion dans le store, onglet réécrit. Renvoie le bilan (jamais d'exception)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    suivis = {_cle(c.get("handle")) for c in comptes or []}
    bilan = {"importes": 0, "ajoutes": 0}
    classeur = None
    try:
        import google_api
        import paie_clics
        classeur = await paie_clics._classeur_usage() if google_api.actif() else None
        if classeur:
            try:
                valeurs = await google_api.sheets_lire(classeur, f"'{ONGLET}'!A1:H")
            except Exception:                                           # noqa: BLE001 — onglet absent : rien à importer
                valeurs = []
            for r in lignes_import(valeurs):
                if r["handle"] in suivis:
                    bilan["importes"] += 1
                    bilan["ajoutes"] += fusionner(store, r["handle"], [r], maintenant)
    except Exception as erreur:                                         # noqa: BLE001
        bilan["import"] = f"onglet illisible ({str(erreur)[:120]})"
    try:
        await _rest(store, suivis, maintenant, longue, bilan)
    except Exception as erreur:                                         # noqa: BLE001
        bilan["rest"] = f"erreur ({str(erreur)[:120]})"
    try:
        if classeur:
            import pilotage
            await pilotage._ecrire(classeur, ONGLET, ENTETE, lignes_onglet(store))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Onglet %s non écrit : %s", ONGLET, str(erreur)[:160])
    return bilan
