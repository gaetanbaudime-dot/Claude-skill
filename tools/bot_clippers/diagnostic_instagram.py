"""Diagnostic de la pagination FlashAPI (23/10/2026, Gaëtan : « une seule API hyper bien setup : trouve pourquoi RapidAPI n'arrive
pas à tracker ces comptes »).

Constat du 22/10 : sur itsvanlifesophie, Metricool voit 279 Reels sur 180 jours, FlashAPI (/ig/reels_posts/) 17 : la liste
s'arrête après une page, sans page suivante. Hypothèse principale : le curseur d'Instagram (max_id) est lié à la session du compte
qui a servi la page ; FlashAPI fait tourner ses comptes et renvoie dans chaque réponse « pagination.id_acc » (le compte utilisé).
Un curseur rejoué sur un autre compte de FlashAPI peut ne rien donner. On teste donc, sur des comptes dont on connaît la vérité
(Metricool) et sur des témoins, plusieurs façons de tourner les pages :

  A. reels, max_id seul (ce que fait le suivi)
  B. reels, max_id + id_acc de la page précédente
  C. publications (/ig/posts/), max_id seul
  D. publications, max_id + id_acc

Chaque page est notée dans l'onglet « IG · Diagnostic » (code HTTP, Reels de la page, nouveaux, cumul, dates, more_available,
curseur, id_acc, clés de la réponse), puis une ligne de synthèse par compte et par façon, à côté du nombre de Reels vu par
Metricool sur la même fenêtre. Aucune donnée du suivi n'est modifiée. Environ 400 requêtes au plus.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

import instagram_rapidapi as I  # noqa: E402

ONGLET = "IG · Diagnostic"
COMPTES = [h.strip().lower() for h in (os.environ.get("DIAG_COMPTES") or "itsvanlifesophie,lapetitesophievanlife,iamjadetora,"
           "itschloe.douceur,xosarahiva,cloudychloe.journal,sophiechoeur").split(",") if h.strip()]
PAGES = int(os.environ.get("DIAG_PAGES", "15") or 15)
JOURS = int(os.environ.get("DIAG_JOURS", "60") or 60)
FICHIER = Path(os.environ.get("SUIVI_FICHIER", "donnees_ci/instagram.json"))
VARIANTES = [("A reels max_id", "reels", False), ("B reels max_id+id_acc", "reels", True),
             ("C posts max_id", "posts", False), ("D posts max_id+id_acc", "posts", True)]
ENTETE = ["Compte", "Façon", "Page", "Code HTTP", "Reels page", "Nouveaux", "Cumul", "Plus ancien", "Plus récent",
          "more_available", "Curseur (début)", "id_acc", "Clés de la réponse", "Note"]


def _date(r):
    return (r.get("publie") or "")[:16]


async def tourner(session, i: str, route: str, avec_acc: bool, depuis: datetime) -> tuple:
    """Pages successives d'une façon ; renvoie (lignes de détail, codes distincts vus, codes dans la fenêtre)."""
    chemin = I.API["reels"][0] if route == "reels" else "/ig/posts/"
    lignes, vus, dans, curseur, acc, vides = [], {}, set(), None, None, 0
    for p in range(1, PAGES + 1):
        params = {"id_user": i}
        if curseur:
            params["max_id"] = curseur
            if avec_acc and acc is not None:
                params["id_acc"] = acc
        code, corps = await I.appeler(session, chemin, params)
        if code != 200 or not isinstance(corps, dict):
            lignes.append([str(code), "", "", "", "", "", "", "", "", "", str(corps)[:200]])
            break
        reels, cur = I.lire_reels(corps, videos_seules=(route == "posts"))
        nouveaux = [r for r in reels if r["code"] not in vus]
        for r in reels:
            vus[r["code"]] = r
            q = I._instant(r.get("publie"))
            if q and q >= depuis:
                dans.add(r["code"])
        pi = corps.get("paging_info") if isinstance(corps.get("paging_info"), dict) else {}
        pag = corps.get("pagination") if isinstance(corps.get("pagination"), dict) else {}
        acc = pag.get("id_acc", acc)
        dates = sorted(_date(r) for r in reels if _date(r))
        lignes.append([str(code), str(len(reels)), str(len(nouveaux)), str(len(vus)), dates[0] if dates else "", dates[-1] if dates else "",
                       str(pi.get("more_available", corps.get("more_available", ""))), str(cur or "")[:14], str(pag.get("id_acc", "")),
                       ",".join(sorted(corps.keys()))[:120], ""])
        vides = vides + 1 if not nouveaux else 0
        plus_vieux = I.plus_ancien(nouveaux) if nouveaux else None
        if not cur or vides >= 2 or (plus_vieux and plus_vieux < depuis - timedelta(days=5)):
            break
        curseur = cur
    return lignes, vus, dans


async def verite_metricool(classeur) -> dict:
    """Nombre de Reels par compte dans l'onglet IG · Reels Metricool, sur la fenêtre."""
    import google_api
    try:
        valeurs = await google_api.sheets_lire(classeur, "'IG · Reels Metricool'!A1:H")
    except Exception:                                                   # noqa: BLE001
        return {}
    if not valeurs:
        return {}
    tete = [str(x).strip() for x in valeurs[0]]
    ih, ip = tete.index("@"), tete.index("Publié le")
    depuis = datetime.now(timezone.utc) - timedelta(days=JOURS)
    out = {}
    for r in valeurs[1:]:
        r = list(r) + [""] * 8
        q = I._instant(r[ip])
        if q and q >= depuis:
            out[str(r[ih]).strip().lower()] = out.get(str(r[ih]).strip().lower(), 0) + 1
    return out


async def main() -> int:
    import aiohttp
    import google_api
    import paie_clics
    import pilotage
    if not I.CLE:
        print("RAPIDAPI_KEY manquant")
        return 1
    try:
        store = json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        store = {"comptes": {}}
    I.configurer({"lire_json": lambda f, d: store, "ecrire_json": lambda f, d: None, "FICHIER": FICHIER})
    classeur = await paie_clics._classeur_usage() if google_api.actif() else None
    verite = await verite_metricool(classeur) if classeur else {}
    depuis = datetime.now(timezone.utc) - timedelta(days=JOURS)
    detail, synthese = [], []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        for h in COMPTES:
            i = (store.get("comptes", {}).get(h) or {}).get("id") or await I.identifiant(session, store, h)
            if not i:
                synthese.append([h, "—", "", "", "", "", "", "", "", "", "", "", "", "ID introuvable"])
                continue
            for nom, route, avec_acc in VARIANTES:
                lignes, vus, dans = await tourner(session, str(i), route, avec_acc, depuis)
                for k, l in enumerate(lignes, start=1):
                    detail.append([h, nom, str(k)] + l)
                dates = sorted(_date(r) for r in vus.values() if _date(r))
                synthese.append([h, nom, "SYNTHÈSE", "", "", "", str(len(vus)), dates[0] if dates else "", dates[-1] if dates else "",
                                 "", "", "", "", f"{len(dans)} Reels sur {JOURS} j" + (f" · Metricool : {verite[h]}" if h in verite else "")])
                print(h, nom, len(vus), "Reels vus,", len(dans), f"sur {JOURS} j", "· Metricool", verite.get(h, "—"))
    if classeur:
        await pilotage._ecrire(classeur, ONGLET, ENTETE, synthese + [[""] * len(ENTETE)] + detail)
    print("Requêtes :", I._jour["n"], "· quota restant :", I._jour["restant"])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
