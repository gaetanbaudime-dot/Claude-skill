"""Drive de l'agence : client du script Apps Script `apps_script/drive_agence.gs` (23/09/2026).

Le compte de service n'a pas d'espace de stockage (Google : « Service Accounts do not have storage
quota »), donc tout ce qui CRÉE des fichiers dans le Drive passe par le script déployé sous le compte
Google de l'agence : copie des photos et Reels d'une créatrice dans le dossier personnel d'un clipper,
partage en lecture, dépôt des Reels spoofés. Le compte de service (google_api.py) reste la voie de
LECTURE (Drive, Sheets) et d'écriture dans les classeurs.

Variables : DRIVE_AGENCE_URL (l'URL /exec du script), DRIVE_AGENCE_SECRET (la même phrase que SECRET).
"""

import asyncio
import base64
import logging
import os

import aiohttp

journal = logging.getLogger("drive_agence")

URL = os.environ.get("DRIVE_AGENCE_URL", "").strip()
SECRET = os.environ.get("DRIVE_AGENCE_SECRET", "").strip()

_session = None


def actif() -> bool:
    return bool(URL and SECRET)


async def appeler(action: str, **champs) -> dict:
    """POST JSON au script ; suit la redirection Apps Script ; renvoie le dict de réponse (clé `ok`)."""
    global _session
    if not actif():
        raise RuntimeError("Drive agence inactif : DRIVE_AGENCE_URL / DRIVE_AGENCE_SECRET absents")
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=340), trust_env=True)
    corps = {"secret": SECRET, "action": action, **champs}
    for essai in range(2):
        try:
            async with _session.post(URL, json=corps, allow_redirects=True) as r:
                texte = await r.text()
                if r.status >= 400:
                    raise RuntimeError(f"script Drive {r.status} : {texte[:160]}")
                try:
                    import json
                    rep = json.loads(texte)
                except ValueError:
                    raise RuntimeError("script Drive : réponse illisible (déploiement « Tout le monde » ?) : " + texte[:120])
                if not rep.get("ok"):
                    raise RuntimeError("script Drive : " + str(rep.get("erreur", "erreur inconnue"))[:200])
                return rep
        except aiohttp.ClientError as erreur:
            if essai == 1:
                raise RuntimeError(f"script Drive injoignable ({type(erreur).__name__})") from erreur
            await asyncio.sleep(3)
    raise RuntimeError("script Drive : trop de tentatives")


async def ping() -> str:
    return (await appeler("ping")).get("compte", "")


async def copier_dossier(source_id: str, parent_id: str, nom: str, types=("image", "video"), max_fichiers: int = 0,
                         sous: str = "") -> dict:
    """Copie `source_id` dans `parent_id/nom` (sous-dossiers compris), en plusieurs appels si le script
    rend la main avant sa limite de temps. Renvoie {id, url, copies, sautes}."""
    total = {"id": "", "url": "", "copies": 0, "sautes": 0}
    for _ in range(12):                                          # 12 × 4,5 min au plus
        rep = await appeler("copier", source=source_id, parent=parent_id, nom=nom, types=list(types),
                            max=int(max_fichiers or 0), sous=sous or "")
        total["id"], total["url"] = rep.get("id", total["id"]), rep.get("url", total["url"])
        total["copies"] += int(rep.get("copies", 0)); total["sautes"] += int(rep.get("sautes", 0))
        if not rep.get("reste"):
            return total
    journal.warning("Copie Drive incomplète pour %s (script toujours en reste)", nom)
    return total


async def partager(fichier_id: str, email: str, role: str = "reader") -> str:
    rep = await appeler("partager", id=fichier_id, email=email, role=role)
    return rep.get("url", "")


async def televerser(parent_id: str, nom: str, contenu: bytes, mime: str = "video/mp4") -> dict:
    if len(contenu) > 45 * 1024 * 1024:
        raise RuntimeError(f"fichier trop lourd pour le script ({len(contenu) // 1_000_000} Mo > 45 Mo)")
    return await appeler("televerser", parent=parent_id, nom=nom, mime=mime,
                         base64=base64.b64encode(contenu).decode("ascii"))


async def lister(dossier_id: str) -> list:
    return (await appeler("lister", id=dossier_id)).get("elements", [])


async def supprimer(fichier_id: str):
    await appeler("supprimer", id=fichier_id)
