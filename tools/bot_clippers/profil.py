"""Profil prêt à coller (28/09, Gaëtan : GO). Avec chaque compte (étapes 1 à 3 du parcours), le clipper reçoit dans son salon une
photo de profil prise dans le dossier « Photos » de sa créatrice (DRIVE_SOURCES) et une bio tirée d'une banque de vingt modèles,
sage, sans lien ni @, jamais la même deux fois de suite pour une créatrice. Plus rien à choisir ni à écrire.
État dans DONNEES/profil.json : {"photos": {créatrice: [ids récents]}, "bios": {créatrice: [indices récents]}}. PROFIL=0 éteint."""

import io
import logging
import os
import re

import discord

journal = logging.getLogger("profil")
ACTIF = os.environ.get("PROFIL", "1").strip() != "0"
PHOTO_MAX_OCTETS = 9_500_000                    # 30/09 : la limite d'envoi de Discord est 10 Mo par fichier
DOSSIER_MIME = "application/vnd.google-apps.folder"
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
    """deps : lire_json, ecrire_json, FICHIER, source_de (créatrice -> entrée DRIVE_SOURCES), drive_lister, drive_telecharger,
    et en option drive_vignette (id -> octets ; par défaut la vignette Drive lue par google_api)."""
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


async def _vignette_drive(fichier_id: str) -> bytes:
    """01/10 : la vignette Drive d'une image (agrandie à 1600 px), pour une photo trop lourde pour Discord."""
    import google_api                                                   # (import tardif : les tests de ce module s'en passent)
    r = await google_api._appel("GET", f"{google_api.DRIVE}/files/{fichier_id}",
                                params={"supportsAllDrives": "true", "fields": "thumbnailLink"})
    lien = str(r.get("thumbnailLink") or "")
    if not lien:
        raise RuntimeError("pas de vignette Drive")
    lien = re.sub(r"=s\d+$", "=s1600", lien)
    s_ = await google_api._session_http()
    async with s_.get(lien, headers={"Authorization": f"Bearer {await google_api.jeton()}"}) as rep:
        if rep.status >= 400:
            raise RuntimeError(f"vignette refusée ({rep.status})")
        return await rep.read()


def _image(f: dict):
    """Le fichier Drive vu comme une image {id, name, size}, raccourci compris (sa cible), ou None."""
    raccourci = f.get("shortcutDetails") or {}
    if str(f.get("mimeType", "")).startswith("image/") and f.get("id"):
        return f
    if str(raccourci.get("targetMimeType", "")).startswith("image/") and raccourci.get("targetId"):
        return {"id": raccourci["targetId"], "name": f.get("name"), "size": None}
    return None


def _sous_dossier(f: dict) -> str:
    raccourci = f.get("shortcutDetails") or {}
    if f.get("mimeType") == DOSSIER_MIME and f.get("id"):
        return f["id"]
    return raccourci.get("targetId", "") if raccourci.get("targetMimeType") == DOSSIER_MIME else ""


async def photo_pour(creatrice: str):
    """(nom de fichier, octets) d'une photo du dossier « Photos » de la créatrice, en tournant ; None sans source ou sans image.
    01/10 (Ricardo, deux fois le texte de secours le 30/09, sans raison au journal) : la raison de chaque échec va au journal,
    les sous-dossiers du dossier Photos sont parcourus (un niveau), et quand toutes les images dépassent la limite de Discord,
    ou que le téléchargement échoue, c'est la vignette Drive qui part (résolution réduite, suffisante pour un profil)."""
    source_de = _deps.get("source_de")
    if source_de is None or not _deps.get("drive_lister") or not _deps.get("drive_telecharger"):
        journal.warning("Photo de profil de %s : module non configuré", creatrice)
        return None
    sources = (source_de(creatrice) or {}).get("sources") or []
    dossiers = [s.get("id") if isinstance(s, dict) else s for s in sources
                if isinstance(s, dict) and str(s.get("sous", "")).strip().lower().startswith("photo")]
    if not dossiers:
        journal.warning("Photo de profil de %s : pas de dossier Photos dans DRIVE_SOURCES", creatrice)
        return None
    images, lourdes, vus = [], [], 0
    a_voir = [(did, 0) for did in dossiers if did]
    while a_voir:
        did, niveau = a_voir.pop(0)
        try:
            fichiers = await _deps["drive_lister"](did)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Photos de %s : dossier %s illisible (%s)", creatrice, str(did)[:8], erreur)
            continue
        for f in fichiers:
            vus += 1
            sous = _sous_dossier(f)
            if sous:
                if niveau < 1:
                    a_voir.append((sous, niveau + 1))
                continue
            img = _image(f)
            if img is None:
                continue
            # 30/09 (Mathias, pas de photo reçue) : une photo au-dessus de la limite Discord faisait tout échouer — on ne
            # garde que celles qui passent (taille connue par le Drive) ; les autres servent par leur vignette
            (lourdes if int(img.get("size") or 0) > PHOTO_MAX_OCTETS else images).append(img)
    vignette = not images
    if vignette:
        if not lourdes:
            journal.warning("Photo de profil de %s : aucune image dans le dossier Photos (%d élément(s) vu(s))", creatrice, vus)
            return None
        journal.info("Photo de profil de %s : %d image(s), toutes au-dessus de %d Mo → vignette Drive", creatrice,
                     len(lourdes), PHOTO_MAX_OCTETS // 1_000_000)
        images = lourdes
    images.sort(key=lambda f: str(f.get("name", "")))
    d = _lire()
    servis = d["photos"].setdefault(_cle(creatrice), [])
    choix = next((f for f in images if f["id"] not in servis), None)
    if choix is None:
        servis.clear()
        choix = images[0]
    octets = None
    if not vignette:
        try:
            octets = await _deps["drive_telecharger"](choix["id"], PHOTO_MAX_OCTETS)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Photo %s de %s : téléchargement impossible (%s) → vignette Drive", choix.get("name"), creatrice, erreur)
    if octets is None:
        try:
            octets = await (_deps.get("drive_vignette") or _vignette_drive)(choix["id"])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Photo %s de %s : vignette impossible (%s)", choix.get("name"), creatrice, erreur)
            return None
        if len(octets) > PHOTO_MAX_OCTETS:
            journal.warning("Photo %s de %s : vignette encore trop lourde (%d Mo)", choix.get("name"), creatrice, len(octets) // 1_000_000)
            return None
    servis.append(choix["id"])
    d["photos"][_cle(creatrice)] = servis[-60:]
    _ecrire(d)
    nom = str(choix.get("name") or "photo.jpg")
    return nom, octets


def lien_photos(creatrice: str) -> str:
    """Le lien direct du dossier Photos de la créatrice (ouvert par le lien depuis le 30/09) : le Drive donné à l'étape 1
    ouvre le TOP 20, pas les photos."""
    source_de = _deps.get("source_de")
    for s in ((source_de(creatrice) or {}).get("sources") or []) if source_de else []:
        if isinstance(s, dict) and str(s.get("sous", "")).strip().lower().startswith("photo") and s.get("id"):
            return f"https://drive.google.com/drive/folders/{s['id']}"
    return ""


def texte_bio(n: int, bio: str, nom: str = "") -> str:
    """30/09 (Ricardo demandait quoi mettre dans « Ajoutez votre nom », Gaëtan : « mets Chloé, t'embêtes pas ») : le nom du
    profil arrive avec la bio, prêt à coller — le prénom de la créatrice, rien d'autre."""
    tete = f"✏️ Nom :\n```\n{nom}\n```\n" if nom else ""
    return tete + f"✏️ Bio :\n```\n{bio}\n```"


async def envoyer(salon, uid: str, n: int, creatrice: str, vue=None, lien: str = "", prive=None):
    """30/09 (Gaëtan : « arrête de spammer les clippeurs ») : le profil du compte n en UN message — la photo en pièce jointe
    (ou le lien du dossier Photos), le nom et la bio prêts à coller, et le bouton `vue`. Renvoie le message envoyé, None sinon.
    05/10 : le compte 3 est privé et porte le lien dans sa bio (`lien`) ; les comptes 1 et 2 n'ont ni lien ni @.
    08/10 (privé en 2) : `prive` dit si CE compte est le privé (le 2 pour les nouveaux parcours) ; sans lien encore prêt, il passe
    en privé quand même et le lien arrive dans le salon."""
    if not ACTIF or salon is None or not creatrice:
        return None
    photo = await photo_pour(creatrice)
    prenom = (creatrice or "").split()[0] if (creatrice or "").split() else creatrice
    if photo is None:                                                   # 30/09 (Ricardo) : jamais une photo promise qui n'arrive pas
        journal.warning("Pas de photo de profil envoyée à %s (%s, compte %s)", uid, creatrice, n)
        lien = lien_photos(creatrice)
        tete = (f"📷 Photo : choisis-en une ici : <{lien}>" if lien else "📷 Photo : prends-en une dans le dossier **Photos** de ton Drive.")
    else:
        tete = "📷 Photo : celle-ci, télécharge-la."
    bio = bio_pour(creatrice)
    prive = (n == 3) if prive is None else bool(prive)
    if prive:
        # 08/10 (checkup) : le lien était collé DANS le texte de la bio, où Instagram ne le rend pas cliquable ; il va dans le
        # champ « Liens » du profil (le seul lien cliquable d'un profil, visible même sur un compte privé)
        fin = ("Ce compte est **privé** : Réglages → Confidentialité du compte → Compte privé.\n\n"
               + (f"🔗 **Ton lien** : Modifier le profil → **Liens** → Ajouter un lien externe → colle :\n```\n{lien}\n```\n"
                  "Pas dans le texte de la bio : là, il ne se clique pas.\n\n" if lien else
                  "🔗 Ton lien arrive ici dans quelques minutes : tu le mettras dans Modifier le profil → **Liens**, pas dans le texte de la bio.\n\n")
               + "Fait ? Appuie sur le bouton.")
    else:
        fin = "Pas de lien, pas d'@. Fait ? Appuie sur le bouton."
    texte = f"**Ton profil du compte {n}**\n\n{tete}\n\n{texte_bio(n, bio, prenom)}\n\n{fin}"
    kwargs = {"view": vue} if vue is not None else {}
    try:
        if photo is not None:
            nom_fichier, octets = photo
            return await salon.send(texte[:1990], file=discord.File(io.BytesIO(octets), filename=nom_fichier), **kwargs)
        return await salon.send(texte[:1990], **kwargs)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Profil du compte %s pour %s : %s", n, uid, erreur)
        return None
