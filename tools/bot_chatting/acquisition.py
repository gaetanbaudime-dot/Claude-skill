"""Acquisition du jour (30/09/2026, Gaëtan : « envoie un message hyper simple avec les visiteurs sur les plateformes MYM + OF
combinés des créatrices », dans le salon acquisition du serveur chatting).

Chaque matin à ACQUISITION_HEURE (heure de Paris), un message dans le salon ACQUISITION_SALON_ID :

    Hier (30 septembre)

    Chloé 595
    Sophie 9876
    …

Le chiffre d'une créatrice = les clics de la veille sur les boutons OnlyFans (onlyfans.com) et MYM (mym.fans) de TOUS ses liens
GetAllMyLinks — c'est-à-dire les gens réellement envoyés sur les deux plateformes. Les liens sont rangés par groupe GAML (un
groupe par créatrice). Les robots sont exclus par GAML.

Sous les créatrices, des lignes par PERSONNE (30/09, Gaëtan : « rajoute Rianah (Metricool), Julien (Metricool) ; à l'avenir
Rianah clipping, juste Rianah avec les comptes de tout le monde ») : la somme des liens dont la NOTE GAML contient tous les mots
donnés, toutes créatrices confondues (« Rianah Metricool », « Rianah Metricool 2 »…). Réglage ACQUISITION_LIGNES :
« Libellé=mots;Libellé=mots » — vide par défaut depuis le 30/09 (Gaëtan : « juste le total de la veille de chaque créatrice »).
Pour remettre une ligne plus tard : « Rianah=rianah ».

Lecture seule : le bot ne modifie rien dans GAML. Variables : GAML_API_KEY (obligatoire, sinon rien ne part),
ACQUISITION_SALON_ID (défaut : le salon acquisition), ACQUISITION_HEURE (défaut 9), ACQUISITION_CREATRICES (l'ordre
d'affichage ; les groupes GAML absents de la liste suivent). `!acquisition` (admin) : le message tout de suite, pour hier ;
`!acquisition 2026-09-28` pour un autre jour."""

import asyncio
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

log = logging.getLogger("chatting.acquisition")

GAML_API_KEY = os.environ.get("GAML_API_KEY", "").strip()
_cle_memoire = {"cle": ""}                             # 30/09 : clé donnée par `!cle-gaml` (volume), si la variable Railway manque


def definir_cle(cle: str) -> None:
    _cle_memoire["cle"] = (cle or "").strip()


def cle() -> str:
    return GAML_API_KEY or _cle_memoire["cle"]
API = "https://getallmylinks.com/api/v1"
FUSEAU = "Europe/Paris"
SALON_ID = int(os.environ.get("ACQUISITION_SALON_ID", "1548671205890990240") or 0)
HEURE = int(os.environ.get("ACQUISITION_HEURE", "9") or 9)
ORDRE = [c.strip() for c in os.environ.get("ACQUISITION_CREATRICES", "Chloé,Sophie,Sarah,Jade,Clara,Maddie").split(",") if c.strip()]
PLATEFORMES = ("onlyfans.com", "mym.fans")


def _lignes_personnes(texte: str) -> list:
    """[(libellé, [mots normalisés])] depuis « Rianah (Metricool)=rianah metricool;Julien (Metricool)=julien »."""
    out = []
    for morceau in (texte or "").split(";"):
        if "=" not in morceau:
            continue
        libelle, mots = morceau.split("=", 1)
        mots = [_norm(m) for m in mots.split() if _norm(m)]
        if libelle.strip() and mots:
            out.append((libelle.strip(), mots))
    return out


LIGNES_DEFAUT = ""                                       # 30/09 (Gaëtan : « mets pas le Metricool, juste le total de chaque créatrice »)
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def actif() -> bool:
    return bool(cle() and SALON_ID)


def _norm(texte: str) -> str:
    t = unicodedata.normalize("NFD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


LIGNES = _lignes_personnes(os.environ.get("ACQUISITION_LIGNES", LIGNES_DEFAUT))


def personne_du_lien(note: str, lignes=None) -> list:
    """Les libellés de personne dont tous les mots sont dans la note du lien."""
    mots_note = set(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFD", str(note or "")).encode("ascii", "ignore").decode().lower()))
    return [lib for lib, mots in (LIGNES if lignes is None else lignes) if all(m in mots_note for m in mots)]


def aujourdhui() -> date:
    return datetime.now(ZoneInfo(FUSEAU)).date()


def _liste(reponse) -> list:
    if isinstance(reponse, list):
        return reponse
    if isinstance(reponse, dict):
        for cle in ("data", "member", "links", "items"):
            if isinstance(reponse.get(cle), list):
                return reponse[cle]
    return []


async def _requete(session, chemin: str, params=None):
    """GET GAML, avec une reprise sur 429 / 5xx (limite : 60 appels par minute)."""
    for essai in range(4):
        async with session.get(f"{API}{chemin}", params=params,
                               headers={"X-Api-Key": cle(), "Accept": "application/json"}) as r:
            if r.status == 429 or r.status >= 500:
                await asyncio.sleep(5 * (essai + 1))
                continue
            if r.status >= 400:
                raise RuntimeError(f"GAML {r.status} sur {chemin} : {(await r.text())[:150]}")
            return await r.json(content_type=None)
    raise RuntimeError(f"GAML : trop de tentatives sur {chemin}")


def clics_plateformes(lignes: list, jour: date) -> int:
    """Clics d'un lien vers OnlyFans ou MYM pour ce jour (une ligne par bouton et par jour)."""
    total = 0
    for x in lignes:
        if not isinstance(x, dict):
            continue
        url = str(x.get("url") or x.get("value") or "").lower()
        quand = str(x.get("date") or "")[:10]
        # 30/09 : sur un seul jour, GAML découpe par HEURE (« date » : « 00:00 », « 01:00 »…) — une heure compte, une autre date non
        if any(p in url for p in PLATEFORMES) and (not quand or "-" not in quand or quand == jour.isoformat()):
            total += int(x.get("clicks") or x.get("count") or 0)
    return total


async def par_creatrice(jour: date, requete=None) -> tuple:
    """({créatrice (nom du groupe GAML): clics OF + MYM du jour}, {personne: clics})."""
    async def _faire(session):
        liens = _liste(await (requete or _requete)(session, "/links"))
        totaux, personnes = {}, {lib: 0 for lib, _ in LIGNES}
        for lien in liens:
            groupe = ((lien.get("group") or {}).get("name") or "").strip()
            if not groupe or lien.get("enabled") is False:
                continue
            params = {"link_id": lien["id"], "range": "custom", "date_from": jour.isoformat(),
                      "date_to": jour.isoformat(), "timezone": FUSEAU}
            try:
                lignes = _liste(await (requete or _requete)(session, "/analytics/clicks", params))
            except RuntimeError as erreur:
                log.warning("Acquisition : lien %s (%s) : %s", lien.get("slug"), groupe, erreur)
                continue
            n = clics_plateformes(lignes, jour)
            totaux[groupe] = totaux.get(groupe, 0) + n
            if LIGNES:
                note = lien.get("note")
                if note is None:                                            # la liste ne porte pas toujours la note
                    try:
                        note = (await (requete or _requete)(session, f"/links/{lien['id']}")).get("note") or ""
                    except (RuntimeError, AttributeError):
                        note = ""
                for lib in personne_du_lien(note):
                    personnes[lib] += n
            if requete is None:
                await asyncio.sleep(2.1)                                    # 2 appels par lien, sous les 60 par minute
        return totaux, personnes
    if requete is not None:
        return await _faire(None)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
        return await _faire(session)


def texte(jour: date, totaux: dict, personnes: dict = None) -> str:
    """Le message, hyper simple : le jour, une créatrice par ligne dans l'ordre choisi, puis les personnes."""
    rang = {_norm(c): i for i, c in enumerate(ORDRE)}
    noms = sorted(totaux, key=lambda n: (rang.get(_norm(n), len(ORDRE)), n))
    titre = "Hier" if jour == aujourdhui() - timedelta(days=1) else "Le"
    lignes = [f"{titre} ({jour.day}{'er' if jour.day == 1 else ''} {MOIS[jour.month - 1]})", ""]
    lignes += [f"{n} {totaux[n]}" for n in noms]
    if personnes:
        lignes += [""] + [f"{lib} {v}" for lib, v in personnes.items()]
    return "\n".join(lignes)


async def envoyer(client, jour: date = None, salon=None) -> str:
    jour = jour or aujourdhui() - timedelta(days=1)
    salon = salon or client.get_channel(SALON_ID) or await client.fetch_channel(SALON_ID)
    totaux, personnes = await par_creatrice(jour)
    message = texte(jour, totaux, personnes)
    await salon.send(message)
    log.info("Acquisition du %s envoyée", jour.isoformat())
    return message


async def boucle(client, lire, ecrire, fichier) -> None:
    """Une fois par jour, à HEURE (Paris). L'état (dernier jour envoyé) survit aux redémarrages."""
    await client.wait_until_ready()
    if not actif():
        log.info("Acquisition éteinte : GAML_API_KEY absente")
        return
    while not client.is_closed():
        try:
            maintenant = datetime.now(ZoneInfo(FUSEAU))
            etat = lire(fichier, {})
            if maintenant.hour >= HEURE and etat.get("dernier") != maintenant.date().isoformat():
                await envoyer(client)
                etat["dernier"] = maintenant.date().isoformat()
                ecrire(fichier, etat)
        except Exception as erreur:                                         # la boucle ne meurt jamais
            log.warning("Acquisition : %s", erreur)
        await asyncio.sleep(600)
