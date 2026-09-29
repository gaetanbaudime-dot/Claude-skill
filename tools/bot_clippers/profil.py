"""Profil prêt à coller (28/09, Gaëtan : GO). Avec chaque compte (étapes 1 à 3 du parcours), le clipper reçoit dans son salon une
photo de profil prise dans le dossier « Photos » de sa créatrice (DRIVE_SOURCES) et une bio tirée d'une banque de vingt modèles,
sage, sans lien ni @, jamais la même deux fois de suite pour une créatrice. Plus rien à choisir ni à écrire.
État dans DONNEES/profil.json : {"photos": {créatrice: [ids récents]}, "bios": {créatrice: [indices récents]}}. PROFIL=0 éteint."""

import io
import logging
import os

import discord

journal = logging.getLogger("profil")
ACTIF = os.environ.get("PROFIL", "1").strip() != "0"
PHOTO_MAX_OCTETS = 9_500_000                    # 30/09 : la limite d'envoi de Discord est 10 Mo par fichier
_deps = {}

BIOS = (
    "Fan de {prenom} 💛 Ses meilleurs moments, chaque jour",
    "Le meilleur de {prenom}, en Reels 🎬",
    "Ici on aime {prenom} 💕 Compte de fans",
    "{prenom} · fan page · nouveaux Reels tous les jours",
    "Les plus beaux moments de {prenom} ✨",
    "Compte fan de {prenom} 🌸 Bonne humeur garantie",
    "{prenom} au quotidien 📸 Par ses fans",
    "Tout {prenom}, rien que {prenom} 💫",
    "Fan club de {prenom} 🎀 Reels chaque jour",
    "Un peu de {prenom} chaque jour ☀️",
    "{prenom} 🎬 Ses Reels préférés, réunis ici",
    "On adore {prenom} 💛 Toi aussi ? Abonne-toi",
    "Page de fans · {prenom} · avec amour 💕",
    "Le sourire de {prenom}, tous les jours 😊",
    "{prenom} · moments choisis · fan page ✨",
    "Fans de {prenom} réunis ici 🌟",
    "Les Reels de {prenom} qu'on regarde en boucle 🔁",
    "{prenom} 💫 Compte de fans, nouveaux Reels chaque jour",
    "Pour ceux qui aiment {prenom} 💛",
    "Ta dose de {prenom} 🎀 Chaque jour un Reel",
)


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, source_de (créatrice -> entrée DRIVE_SOURCES), drive_lister, drive_telecharger."""
    _deps.update(deps)


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER"], {"photos": {}, "bios": {}})
    d.setdefault("photos", {}); d.setdefault("bios", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER"], d)


def _cle(creatrice: str) -> str:
    return (creatrice or "").split()[0].strip().lower() if (creatrice or "").split() else ""


def bio_pour(creatrice: str) -> str:
    """Une bio de la banque, en tournant : les indices déjà servis sont mémorisés, la banque repart quand elle est épuisée."""
    prenom = (creatrice or "").split()[0] if (creatrice or "").split() else creatrice
    d = _lire()
    servis = d["bios"].setdefault(_cle(creatrice), [])
    libres = [i for i in range(len(BIOS)) if i not in servis]
    if not libres:
        servis.clear()
        libres = list(range(len(BIOS)))
    i = libres[0]
    servis.append(i)
    _ecrire(d)
    return BIOS[i].format(prenom=prenom)


async def photo_pour(creatrice: str):
    """(nom de fichier, octets) d'une photo du dossier « Photos » de la créatrice, en tournant ; None sans source ou sans image."""
    source_de = _deps.get("source_de")
    if source_de is None or not _deps.get("drive_lister") or not _deps.get("drive_telecharger"):
        return None
    sources = (source_de(creatrice) or {}).get("sources") or []
    dossiers = [s.get("id") if isinstance(s, dict) else s for s in sources
                if isinstance(s, dict) and str(s.get("sous", "")).strip().lower().startswith("photo")]
    if not dossiers:
        return None
    images = []
    for did in dossiers:
        try:
            for f in await _deps["drive_lister"](did):
                if str(f.get("mimeType", "")).startswith("image/") and f.get("id"):
                    images.append(f)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Photos de %s : %s", creatrice, erreur)
    if not images:
        return None
    images.sort(key=lambda f: str(f.get("name", "")))
    d = _lire()
    servis = d["photos"].setdefault(_cle(creatrice), [])
    choix = next((f for f in images if f["id"] not in servis), None)
    if choix is None:
        servis.clear()
        choix = images[0]
    try:
        octets = await _deps["drive_telecharger"](choix["id"], PHOTO_MAX_OCTETS)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Photo %s de %s : %s", choix.get("name"), creatrice, erreur)
        return None
    servis.append(choix["id"])
    d["photos"][_cle(creatrice)] = servis[-60:]
    _ecrire(d)
    nom = str(choix.get("name") or "photo.jpg")
    return nom, octets


def texte_bio(n: int, bio: str, nom: str = "") -> str:
    """30/09 (Ricardo demandait quoi mettre dans « Ajoutez votre nom », Gaëtan : « mets Chloé, t'embêtes pas ») : le nom du
    profil arrive avec la bio, prêt à coller — le prénom de la créatrice, rien d'autre."""
    tete = f"✏️ Nom du profil, à coller tel quel :\n```\n{nom}\n```\n" if nom else ""
    return tete + f"✏️ Bio du compte {n}, à coller telle quelle :\n```\n{bio}\n```"


async def envoyer(salon, uid: str, n: int, creatrice: str) -> bool:
    """Après l'étape n (1 à 3) : la photo en pièce jointe, puis la bio dans un bloc copiable. Jamais bloquant."""
    if not ACTIF or salon is None or not creatrice:
        return False
    photo = await photo_pour(creatrice)
    envoyee = False
    if photo is not None:
        try:
            nom_fichier, octets = photo
            await salon.send(f"📷 Photo de profil du compte {n} : télécharge-la, mets-la sur le compte.",
                             file=discord.File(io.BytesIO(octets), filename=nom_fichier))
            envoyee = True
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Photo du compte %s pour %s : %s", n, uid, erreur)
    try:
        if not envoyee:                                                 # 30/09 (Ricardo) : jamais une photo promise qui n'arrive pas
            journal.warning("Pas de photo de profil envoyée à %s (%s, compte %s)", uid, creatrice, n)
            await salon.send(f"📷 Photo de profil du compte {n} : prends-en une dans le dossier **Photos** de ton Drive.")
        prenom = (creatrice or "").split()[0] if (creatrice or "").split() else creatrice
        await salon.send(texte_bio(n, bio_pour(creatrice), prenom))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Profil du compte %s pour %s : %s", n, uid, erreur)
        return False
    return True
