"""Relais de test RapidAPI (21/10/2026, Gaëtan : « trouve-moi l'API Instagram la plus performante » ; la clé RAPIDAPI_KEY est dans
Railway, où elle reste : personne ne la recopie).

L'onglet « Test API Instagram » du tableur « App clippers · usage » sert de file : une ligne « à faire » (hôte *.p.rapidapi.com,
chemin, paramètres, méthode, corps JSON) est appelée par le bot avec la clé, et la réponse (code HTTP, durée, quota restant, corps
tronqué) est écrite sur la même ligne. On compare ainsi les API sans jamais exposer la clé.

Garde-fous : seuls les hôtes *.p.rapidapi.com sont appelés ; au plus RELAIS_PAR_PASSAGE appels par passage et RELAIS_PAR_JOUR par
jour (les offres gratuites n'ont que 150 requêtes par mois) ; la clé n'est jamais écrite nulle part ; sans RAPIDAPI_KEY, rien ne
tourne. Jamais d'exception : une erreur est écrite sur la ligne, ou retentée au passage suivant.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl

journal = logging.getLogger("relais_rapidapi")

CLE = os.environ.get("RAPIDAPI_KEY", "").strip()
ONGLET = os.environ.get("RELAIS_RAPIDAPI_ONGLET", "Test API Instagram").strip() or "Test API Instagram"
PAUSE_SEC = max(30, int(os.environ.get("RELAIS_RAPIDAPI_PAUSE", "60") or 60))
PAR_PASSAGE = max(1, int(os.environ.get("RELAIS_PAR_PASSAGE", "6") or 6))
PAR_JOUR = max(1, int(os.environ.get("RELAIS_PAR_JOUR", "80") or 80))
TAILLE_MAX = 45000                                                     # une cellule Google Sheets tient 50 000 caractères
ENTETE = ["Statut", "Hôte", "Chemin", "Paramètres", "Méthode", "Corps JSON", "Code HTTP", "Durée (ms)", "Quota restant",
          "Réponse (tronquée)", "Fait le"]
_compteur = {"jour": "", "n": 0}


def hote_autorise(hote: str) -> bool:
    h = str(hote or "").strip().lower()
    return h.endswith(".p.rapidapi.com") and "/" not in h and " " not in h


def demandes(lignes: list) -> list:
    """Pur : les lignes « à faire » de l'onglet → [(numéro de ligne, hôte, chemin, paramètres dict, méthode, corps)]."""
    out = []
    for i, r in enumerate(lignes or [], start=2):
        r = list(r) + [""] * (6 - len(r))
        if str(r[0]).strip().lower() not in ("à faire", "a faire"):
            continue
        hote, chemin = str(r[1]).strip(), "/" + str(r[2]).strip().lstrip("/")
        params = dict(parse_qsl(str(r[3]).strip().lstrip("?"), keep_blank_values=True))
        methode = (str(r[4]).strip().upper() or "GET")
        corps = str(r[5]).strip()
        out.append((i, hote, chemin, params, methode if methode in ("GET", "POST") else "GET", corps))
    return out


def reponse_texte(texte: str) -> str:
    """Pur : le corps reformaté (JSON compact si possible), tronqué pour tenir dans une cellule."""
    try:
        texte = json.dumps(json.loads(texte), ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        pass
    texte = str(texte or "")
    return texte if len(texte) <= TAILLE_MAX else texte[:TAILLE_MAX] + f"… [tronqué, {len(texte)} caractères]"


async def _appeler(session, hote: str, chemin: str, params: dict, methode: str, corps: str) -> list:
    t0 = time.monotonic()
    entetes = {"X-RapidAPI-Key": CLE, "X-RapidAPI-Host": hote}
    data = None
    if methode == "POST" and corps:
        try:
            data = json.loads(corps)
        except ValueError:
            return ["corps JSON illisible", "", "", "", datetime.now(timezone.utc).isoformat(timespec="seconds")]
    async with session.request(methode, f"https://{hote}{chemin}", params=params, json=data, headers=entetes) as r:
        texte = await r.text()
        quota = r.headers.get("x-ratelimit-requests-remaining", "")
        return [str(r.status), str(int((time.monotonic() - t0) * 1000)), quota, reponse_texte(texte),
                datetime.now(timezone.utc).isoformat(timespec="seconds")]


async def passage() -> int:
    """Un passage : traite au plus PAR_PASSAGE lignes « à faire ». Renvoie le nombre d'appels faits."""
    import aiohttp
    import google_api
    import paie_clics
    if not CLE or not google_api.actif():
        return 0
    classeur = await paie_clics._classeur_usage()
    if not classeur:
        return 0
    o = f"'{ONGLET}'"
    try:
        lignes = await google_api.sheets_lire(classeur, f"{o}!A2:F200")
    except Exception:                                                   # noqa: BLE001 — onglet absent : on le crée, vide
        await google_api.sheets_creer_onglet(classeur, ONGLET)
        await google_api.sheets_ecrire(classeur, f"{o}!A1", [ENTETE])
        return 0
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _compteur["jour"] != jour:
        _compteur.update({"jour": jour, "n": 0})
    faits = 0
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
        for ligne, hote, chemin, params, methode, corps in demandes(lignes)[:PAR_PASSAGE]:
            if not hote_autorise(hote):
                await google_api.sheets_ecrire(classeur, f"{o}!A{ligne}", [["refusé : hôte hors *.p.rapidapi.com"]])
                continue
            if _compteur["n"] >= PAR_JOUR:
                break
            _compteur["n"] += 1
            try:
                res = await _appeler(session, hote, chemin, params, methode, corps)
            except Exception as erreur:                                 # noqa: BLE001
                res = [f"erreur : {type(erreur).__name__}", "", "", str(erreur)[:500],
                       datetime.now(timezone.utc).isoformat(timespec="seconds")]
            await google_api.sheets_ecrire(classeur, f"{o}!G{ligne}:K{ligne}", [res], brut=True)
            await google_api.sheets_ecrire(classeur, f"{o}!A{ligne}", [["fait"]])
            faits += 1
            await asyncio.sleep(1)
    return faits


async def boucle():
    if not CLE:
        journal.info("Relais RapidAPI éteint (pas de RAPIDAPI_KEY)")
        return
    await asyncio.sleep(45)
    while True:
        try:
            n = await passage()
            if n:
                journal.info("Relais RapidAPI : %d appel(s)", n)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Relais RapidAPI : %s", str(erreur)[:200])
        await asyncio.sleep(PAUSE_SEC)
