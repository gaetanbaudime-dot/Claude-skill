"""Réserve de liens de tracking MYM par créatrice (05/10, Gaëtan : « Mets les numéros sur les bons numéros. Tu créeras les liens
gaml avec le bon numéro, ajoute au sheets pour faire de la réserve de lien de tracking MYM pour Sophie »).

Onglet « Réserve trackings MYM » du classeur des logins, une ligne par tracking créé dans MyPulse :
    Créatrice | N° du lien GAML | Nom MyPulse | Lien de tracking MYM | Posé sur | Le
La règle : le tracking « gaml-lienN » va UNIQUEMENT sur le lien GAML /N de la créatrice.

GAML numérote seul : un clone prend toujours le numéro suivant (Sophie : /16 après /15) et le slug ne se choisit pas
(« Slug must be at least 3 characters », test du 05/10). La réserve se prépare donc avec les numéros à venir.

- Au démarrage puis toutes les heures : une ligne libre dont le lien /N existe déjà → bouton « Miam » de ce lien = ce tracking
  (Sophie /13, /14, /15 dès que leurs lignes existent).
- À l'onboarding, juste après le clone (`pour_clone`) : la ligne du numéro que GAML vient de donner → bouton « Miam » du clone.
  Sans ligne pour ce numéro, le bilan le dit (« crée gaml-lienN dans MyPulse ») : jamais un tracking d'un autre numéro.
Une ligne posée garde l'adresse du lien et la date : elle n'est plus jamais reprise.
"""

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import google_api
import paie_clics

journal = logging.getLogger("reserve_mym")

ONGLET = "Réserve trackings MYM"
EN_TETE = ["Créatrice", "N° du lien GAML", "Nom MyPulse", "Lien de tracking MYM", "Posé sur", "Le"]
DEPART = Path(__file__).with_name("reserve_mym_depart.json")       # premières lignes, écrites une fois dans un onglet vide
_classeur = ""


def configurer(classeur_id: str):
    global _classeur
    _classeur = (classeur_id or "").strip()


def actif() -> bool:
    return bool(_classeur and google_api.actif() and paie_clics.actif())


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _premier(t) -> str:
    mots = _n(t).split()
    return mots[0] if mots else ""


def _plage(a1: str) -> str:
    return f"'{ONGLET}'!{a1}"


def numero_du_lien(lien: dict):
    """« sophievanfr:13 » ou « https://sophievan.fr/13 » → 13 ; None pour la page, /fb, /ytb."""
    m = re.search(r":(\d+)$", str(lien.get("slug") or "")) or re.search(r"/(\d+)/?$", str(lien.get("url") or ""))
    return int(m.group(1)) if m else None


def creatrice_du_lien(lien: dict) -> str:
    return _premier((lien.get("group") or {}).get("name") or lien.get("name") or "")


async def assurer_onglet() -> bool:
    """Crée l'onglet et son en-tête s'ils manquent. Vrai s'il vient d'être créé."""
    if not actif():
        return False
    cree = await google_api.sheets_creer_onglet(_classeur, ONGLET)
    tete = await google_api.sheets_lire(_classeur, _plage("A1:F1"))
    if not tete or not any(x.strip() for x in tete[0]):
        await google_api.sheets_ecrire(_classeur, _plage("A1:F1"), [EN_TETE])
    if cree:
        journal.info("Onglet « %s » créé dans le classeur des logins", ONGLET)
    corps = await google_api.sheets_lire(_classeur, _plage("A2:F500"))
    if not any(any(x.strip() for x in l) for l in corps) and DEPART.exists():
        try:
            depart = [list(l)[:4] + ["", ""] for l in json.loads(DEPART.read_text(encoding="utf-8")).get("lignes", [])]
        except (OSError, ValueError) as erreur:
            journal.warning("Réserve MYM, lignes de départ illisibles : %s", erreur)
            depart = []
        if depart:
            await google_api.sheets_ecrire(_classeur, _plage(f"A2:F{len(depart) + 1}"), depart)
            journal.info("Réserve MYM : %d ligne(s) de départ écrites", len(depart))
    return cree


async def lignes() -> list:
    """Les lignes exploitables : créatrice, numéro, lien mym.fans. Les autres sont ignorées (en-tête, notes, cases vides)."""
    brut = await google_api.sheets_lire(_classeur, _plage("A2:F500"))
    out = []
    for i, l in enumerate(brut, start=2):
        l = (list(l) + [""] * 6)[:6]
        m = re.search(r"(\d+)", l[1])
        url = l[3].strip()
        if not (l[0].strip() and m and url.startswith("https://mym.fans/")):
            continue
        out.append({"ligne": i, "creatrice": l[0].strip(), "numero": int(m.group(1)), "nom": l[2].strip(), "url": url,
                    "pose": l[4].strip()})
    return out


async def _marquer(ligne: int, url_lien: str):
    jour = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    await google_api.sheets_ecrire(_classeur, _plage(f"E{ligne}:F{ligne}"), [[url_lien or "posé", jour]])


async def _image_miam(liens: list, creatrice: str) -> str:
    """L'image d'une carte Miam déjà illustrée chez cette créatrice (Chloé), '' sinon. Deux ou trois lectures au plus."""
    for l in [x for x in liens if creatrice_du_lien(x) == _premier(creatrice)][:4]:
        try:
            detail = await paie_clics.lien_detail(l["id"])
        except RuntimeError:
            continue
        carte = next((c for c in detail.get("contents") or [] if "mym.fans" in str(c.get("value") or "") and c.get("image")), None)
        if carte:
            return str(carte["image"])
    return ""


async def poser_sur_existants() -> list:
    """Chaque ligne libre dont le lien /N de la créatrice existe : tracking posé dans son bouton Miam. Renvoie le bilan."""
    if not actif():
        return []
    libres = [r for r in await lignes() if not r["pose"]]
    if not libres:
        return []
    liens = await paie_clics.liens_gaml()
    bilan, images = [], {}
    for r in libres:
        cible = next((l for l in liens if creatrice_du_lien(l) == _premier(r["creatrice"]) and numero_du_lien(l) == r["numero"]), None)
        if cible is None:
            continue                                                    # numéro à venir : la ligne attend son clone
        cle = _premier(r["creatrice"])
        if cle not in images:
            images[cle] = await _image_miam(liens, r["creatrice"])
        try:
            etat = await paie_clics.poser_mym(cible["id"], r["url"], images[cle])
        except RuntimeError as erreur:
            etat = str(erreur)[:120]
        if etat.startswith("ok") or etat == "déjà":
            await _marquer(r["ligne"], cible.get("url") or "")
            bilan.append(f"🔗 Miam {r['nom'] or 'tracking'} → {cible.get('url')}" + ("" if etat in ("ok", "déjà") else f" ({etat})"))
        else:
            bilan.append(f"⚠️ {r['creatrice']} /{r['numero']} : {etat}")
    if bilan:
        journal.info("Réserve MYM : %s", bilan)
    return bilan


async def pour_clone(lien_id: str, creatrice: str) -> str:
    """Juste après un clone : le tracking réservé au numéro que GAML vient de donner part dans le bouton Miam. Ligne de bilan."""
    if not actif():
        return ""
    detail = await paie_clics.lien_detail(lien_id)
    n = numero_du_lien(detail)
    if n is None:
        return ""
    r = next((x for x in await lignes() if not x["pose"] and x["numero"] == n and _premier(x["creatrice"]) == _premier(creatrice)), None)
    if r is None:
        return f"⚠️ pas de tracking MYM en réserve pour /{n} : crée « gaml-lien{n} » dans MyPulse et ajoute-le à l'onglet « {ONGLET} »"
    image = await _image_miam(await paie_clics.liens_gaml(), creatrice) if any(c.get("image") for c in detail.get("contents") or []) else ""
    etat = await paie_clics.poser_mym(lien_id, r["url"], image)
    if etat.startswith("ok") or etat == "déjà":
        await _marquer(r["ligne"], detail.get("url") or "")
        return f"Miam /{n} ✅ ({r['nom'] or 'réserve'})"
    return f"⚠️ Miam /{n} : {etat}"
