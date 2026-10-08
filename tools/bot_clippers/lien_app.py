"""08/10 (Gaëtan : « envoie automatiquement l'app dans le salon Discord privé du clippeur, une fois seulement qu'il a créé les
3 IG : l'app + son lien de tracking GAML ») : le lien personnel de l'app clippers (tools/app_clippers) de chaque clipper.

L'app calcule le jeton de chaque clipper avec un secret qui ne quitte pas Vercel. Le bot n'a donc rien à configurer : sur demande
(POST /api/liens, la réponse ne contient aucun lien), l'app écrit « clipper → lien de l'app » dans l'onglet « Liens app » du
tableur « App clippers · usage », et le bot lit cet onglet avec le compte de service, comme il lit déjà l'onglet « Adresses USDC »
(paie_clics.synchroniser_adresses).

Recherche par le lien GAML du clipper (colonne « Liens GAML »), jamais par le prénom seul : l'app regroupe les clippers par
prénom, deux homonymes partagent une ligne, et envoyer l'app d'un autre ouvrirait sa paie et son adresse USDC. Une adresse qui
n'est pas exactement APP_CLIPPERS_URL/k/<jeton de 24 caractères> est refusée.
"""

import logging
import os
import re
import time

import aiohttp

import google_api
import paie_clics

journal = logging.getLogger("lien_app")

APP_URL = os.environ.get("APP_CLIPPERS_URL", "https://app-clippers.vercel.app").strip().rstrip("/")
ONGLET = os.environ.get("APP_LIENS_ONGLET", "Liens app").strip()
SYNCHRO_S = 600                                                         # au plus une demande d'écriture à l'app toutes les 10 min
_synchro = {"dernier": 0.0}
_classeur = {"id": "", "expire": 0.0}
_lu = {"lignes": 0}                                                     # lignes lues la dernière fois : 0 = l'app n'a encore rien écrit


def onglet_rempli() -> bool:
    """L'onglet avait des lignes à la dernière lecture : un clipper absent est alors vraiment inconnu de l'app (et non une app
    pas encore déployée ou injoignable). Sert à ne prévenir le salon admin qu'à bon escient."""
    return _lu["lignes"] > 0


def actif() -> bool:
    return bool(APP_URL) and google_api.actif()


def _sans_schema(u) -> str:
    return re.sub(r"^https?://", "", str(u or "").strip().lower()).rstrip("/")


def _valide(url) -> str:
    url = str(url or "").strip()
    return url if re.fullmatch(re.escape(APP_URL) + r"/k/[A-Za-z0-9_-]{24}", url) else ""


def chercher(lignes: list, liens_gaml) -> str:
    """Le lien de l'app du clipper : la seule ligne de l'onglet qui porte un de ses liens GAML. '' sinon."""
    cibles = {_sans_schema(x) for x in liens_gaml or [] if x}
    if not cibles:
        return ""
    propres = [(list(l) + [""] * 6)[:6] for l in lignes or []]
    lignes_du_clipper = [l for l in propres if cibles & {_sans_schema(x) for x in str(l[3]).split()}]
    return _valide(lignes_du_clipper[0][2]) if len(lignes_du_clipper) == 1 else ""


async def _id_classeur() -> str:
    if _classeur["id"] and _classeur["expire"] > time.time():
        return _classeur["id"]
    cid = paie_clics.ADRESSES_CLASSEUR_ID or await google_api.drive_chercher(paie_clics.ADRESSES_TABLEUR,
                                                                            "application/vnd.google-apps.spreadsheet")
    if cid:
        _classeur.update({"id": cid, "expire": time.time() + 6 * 3600})
    return cid or ""


async def _lignes() -> list:
    """Les lignes de l'onglet ; [] s'il n'existe pas encore (l'app le crée à sa première écriture) ou si Google ne répond pas."""
    try:
        cid = await _id_classeur()
        lignes = await google_api.sheets_lire(cid, f"'{ONGLET}'!A2:F") if cid else []
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Onglet « %s » illisible : %s", ONGLET, str(erreur)[:160])
        lignes = []
    _lu["lignes"] = len([l for l in lignes if any(str(x).strip() for x in l)])
    return lignes


async def _synchroniser() -> bool:
    """Demande à l'app d'écrire l'onglet, au plus toutes les SYNCHRO_S secondes. Vrai si l'app a répondu ok."""
    if time.time() - _synchro["dernier"] < SYNCHRO_S:
        return False
    _synchro["dernier"] = time.time()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            async with session.post(f"{APP_URL}/api/liens") as r:
                statut = r.status
                corps = await r.json(content_type=None) if statut == 200 else {}
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("App clippers injoignable : %s", str(erreur)[:160])
        return False
    if statut != 200 or not (corps or {}).get("ok"):
        journal.warning("App clippers : onglet « %s » pas écrit (HTTP %s)", ONGLET, statut)
        return False
    return True


async def lien(liens_gaml) -> str:
    """Le lien de l'app du clipper dont voici les liens GAML ; '' si l'app ne le connaît pas (encore) : note GAML qui n'est pas
    « Clipping Prénom », prénom exclu par l'app (Rianah, Jonas…), onglet pas encore écrit. Une demande d'écriture au plus."""
    if not actif():
        return ""
    trouve = chercher(await _lignes(), liens_gaml)
    if trouve or not await _synchroniser():
        return trouve
    return chercher(await _lignes(), liens_gaml)
