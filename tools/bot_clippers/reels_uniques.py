"""TOP 20 Reels d'origine des créatrices (26/09, déclinaison par clipper RETIRÉE le 09/10).

09/10 (Gaëtan : « Enlève le truc qui envoie un dossier Drive au clippeur, la qualité est pourrie apparemment ») : chaque TOP 20
était ré-encodé pour chaque clipper (zoom, couleurs, x264 veryfast, crf 24 à 27, 1,4 à 2 Mbit/s), puis une seconde fois par
Instagram. La déclinaison, son dépôt dans le Drive du clipper et le passage OpusClip sont supprimés. Le clipper reçoit le lien
des vidéos d'ORIGINE de sa créatrice (onboarding.lien_drive_creatrice).

Ce qui reste : trouver le dossier d'origine. `dossier_reels` (le « 📁 Reels » de l'Instagram Drive de la créatrice, au-dessus de
« 🎬 Clippers » de DRIVE_SOURCES), `dossier_top20` et `videos_top20` (review_reels compare la vidéo d'un clipper au TOP 20
d'origine). `boucle`, `demarrage`, `pour_nouveau` et `commande_staff` ne font plus rien, en attendant que leurs appels
disparaissent de bot_discord. DONNEES/reels_uniques.json reste en place, sans effet.

Dépendances (`configurer`) : google_api, sources (DRIVE_SOURCES parsé), normaliser."""
import logging
import os

journal = logging.getLogger("bot.reels_uniques")
_deps: dict = {}
MAX_VIDEOS = int(os.environ.get("REELS_UNIQUES_MAX", "20") or 20)


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    """09/10 : plus aucune déclinaison, donc jamais actif (un appel oublié ne lance plus rien)."""
    return False


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


# ------------------------------------------------------------------ Drive : la source
async def dossier_reels(creatrice: str):
    """09/10 : (id du dossier « 📁 Reels » d'origine de la créatrice, nom) ou (None, raison). C'est le parent du TOP 20 : ses
    vidéos telles que Gaëtan les a déposées, sans ré-encodage."""
    g = _deps.get("google_api")
    if g is None or not _deps.get("sources"):
        return None, "Drive non configuré"
    premier = (creatrice or "").split()[0] if (creatrice or "").split() else ""
    cfg = _deps["sources"]().get(creatrice) or _deps["sources"]().get(premier) or {}
    parent = cfg.get("parent")
    if not parent:
        return None, f"DRIVE_SOURCES sans entrée pour {creatrice}"
    infos = await g.drive_infos(parent)
    instagram = (infos.get("parents") or [None])[0]
    if not instagram:
        return None, "dossier Instagram introuvable au-dessus de « 🎬 Clippers »"
    reels = next((f for f in await g.drive_lister(instagram) if "reels" in _n(f.get("name")) and "folder" in f.get("mimeType", "")), None)
    if not reels:
        return None, "pas de dossier « 📁 Reels » dans l'Instagram de la créatrice"
    return reels["id"], reels["name"].strip()


async def dossier_top20(creatrice: str):
    """(id du dossier TOP 20, nom) ou (None, raison)."""
    reels_id, nom = await dossier_reels(creatrice)
    if not reels_id:
        return None, nom
    g = _deps["google_api"]
    top = next((f for f in await g.drive_lister(reels_id) if "top" in _n(f.get("name")) and "folder" in f.get("mimeType", "")), None)
    if not top:
        return None, "pas de dossier « TOP 20 Reels » dans « 📁 Reels »"
    return top["id"], top["name"].strip()


async def videos_top20(top_id: str) -> list:
    g = _deps["google_api"]
    vids = [f for f in await g.drive_lister(top_id) if (f.get("mimeType") or "").startswith("video/")]
    vids.sort(key=lambda f: f.get("name", ""))
    return vids[:MAX_VIDEOS]


# ------------------------------------------------------------------ retiré le 09/10
async def commande_staff(message, texte: str) -> bool:
    """09/10 : `!reels-uniques` retiré (la déclinaison n'existe plus). Répond une ligne si quelqu'un la tape encore."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!reels-uniques", "!reels-unique"):
        return False
    await message.reply("`!reels-uniques` est retiré depuis le 09/10 : les clippers reçoivent les vidéos d'origine de leur créatrice.")
    return True


async def boucle(client):
    """09/10 : retiré, ne fait plus rien."""
    journal.info("Reels uniques : déclinaison retirée le 09/10, boucle sans effet")


async def demarrage(client) -> list:
    """09/10 : retiré, ne fait plus rien."""
    journal.info("Reels uniques : déclinaison retirée le 09/10, rien à refaire au démarrage")
    return []


async def pour_nouveau(prenom: str, creatrice: str) -> None:
    """09/10 : retiré, ne fait plus rien."""
    journal.info("Reels uniques : déclinaison retirée le 09/10, rien pour %s (%s)", prenom, creatrice)
