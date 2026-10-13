"""Clics sur les boutons OnlyFans et MYM des pages GAML (13/10, Gaëtan : « récupère le maximum de data partout pour mon app de
pilotage »). Le maillon qui manquait entre les visites d'une page et les subs : combien de visiteurs touchent le bouton OF ou MYM.

GAML les donne par lien et par jour (`/analytics/clicks` : une ligne par jour et par bouton, avec son URL). Le bot les relève au
plus toutes les BOUTONS_INTERVALLE_H heures (3 par défaut), un appel par lien actif, lentement (la limite GAML de 60 appels par
minute est partagée avec le relevé des visites) : 62 jours au premier relevé d'un lien, les 3 derniers jours ensuite. Les
chiffres vont dans boutons.json ({lien : {jour : {"of", "mym", "autre"}}}), que le Dashboard range comme les visites (créatrice,
axe, source, personne) dans l'onglet « Pilotage boutons » du tableur de l'app. Aucun coût : l'API GAML est comprise dans l'abonnement.
Jamais d'exception : un échec garde les chiffres d'avant et réessaie au relevé suivant."""
import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

journal = logging.getLogger("boutons")

ACTIF = os.environ.get("BOUTONS_RELEVE", "1").strip() != "0"
try:
    INTERVALLE_H = max(1.0, float(os.environ.get("BOUTONS_INTERVALLE_H", "3") or 3))
except ValueError:
    INTERVALLE_H = 3.0
JOURS_PREMIER = 62                     # premier relevé d'un lien : la fenêtre du pilotage
JOURS_SUIVANTS = 3                     # ensuite : les 3 derniers jours (aujourd'hui compris, encore partiel)
PAUSE_S = 1.5                          # entre deux appels : la limite GAML est partagée avec le relevé des visites
_etat = {"t": 0.0, "en_cours": False}


def _fichier() -> Path:
    return Path(os.environ.get("DONNEES_DIR", Path(__file__).parent / "donnees")) / "boutons.json"


def lire() -> dict:
    try:
        d = json.loads(_fichier().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ecrire(d: dict) -> None:
    f = _fichier()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(f)
    except OSError as erreur:
        journal.warning("boutons.json non écrit : %s", erreur)


def plateforme(url: str, nom: str = "") -> str:
    """« of », « mym » ou « autre », d'après l'URL du bouton (le nom en repli : « OnlyFriends », « Miam »)."""
    u, n = str(url or "").lower(), str(nom or "").lower()
    if "onlyfans." in u or "onlyfriends" in n or n.startswith("of"):
        return "of"
    if "mym." in u or "miam" in n or "mym" in n:
        return "mym"
    return "autre"


def par_jour(lignes: list) -> dict:
    """Pur : {jour : {"of", "mym", "autre"}} d'une réponse `/analytics/clicks` (une ligne par jour et par bouton)."""
    out = {}
    for x in lignes or []:
        if not isinstance(x, dict):
            continue
        j = str(x.get("date") or "")[:10]
        try:
            date.fromisoformat(j)
            n = int(x.get("clicks") or 0)
        except (ValueError, TypeError):
            continue
        e = out.setdefault(j, {"of": 0, "mym": 0, "autre": 0})
        e[plateforme(x.get("url"), x.get("name"))] += n
    return out


async def maj(lids: list, aujourdhui: date, forcer: bool = False) -> int:
    """Relève les liens `lids` si le dernier relevé a plus de INTERVALLE_H heures. Renvoie le nombre de liens relevés."""
    if not ACTIF or _etat["en_cours"] or not lids:
        return 0
    if not forcer and time.monotonic() - _etat["t"] < INTERVALLE_H * 3600 and _etat["t"]:
        return 0
    try:
        import paie_clics
    except Exception:                                                   # noqa: BLE001
        return 0
    if not paie_clics.actif():
        return 0
    _etat["en_cours"] = True
    n = 0
    try:
        d = lire()
        for lid in lids:
            deja = isinstance(d.get(lid), dict) and d[lid]
            debut = aujourdhui - timedelta(days=(JOURS_SUIVANTS if deja else JOURS_PREMIER) - 1)
            try:
                rep = await paie_clics._requete("GET", "/analytics/clicks", params={
                    "link_id": lid, "range": "custom", "date_from": debut.isoformat(), "date_to": aujourdhui.isoformat(),
                    "timezone": paie_clics.FUSEAU, "hide_bots": "true"})
                jours = par_jour(paie_clics._liste_reponse(rep, "/analytics/clicks"))
            except Exception as erreur:                                 # noqa: BLE001 — ce lien au prochain relevé
                journal.warning("Boutons %s : %s", lid, str(erreur)[:160])
                if isinstance(erreur, getattr(paie_clics, "LimiteGAML", ())):
                    break                                               # la limite de la minute : le reste au relevé suivant
                await asyncio.sleep(PAUSE_S)
                continue
            e = d.setdefault(lid, {})
            j = debut
            while j <= aujourdhui:                                      # un jour relevé sans clic : 0 (GAML a répondu)
                e[j.isoformat()] = jours.get(j.isoformat(), {"of": 0, "mym": 0, "autre": 0})
                j += timedelta(days=1)
            limite = (aujourdhui - timedelta(days=JOURS_PREMIER + 7)).isoformat()
            for k in [k for k in e if k < limite]:
                e.pop(k, None)
            n += 1
            await asyncio.sleep(PAUSE_S)
        d["_t"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _ecrire(d)
        _etat["t"] = time.monotonic()
        if n:
            journal.info("Boutons OF / MYM relevés sur %d lien(s)", n)
    finally:
        _etat["en_cours"] = False
    return n
