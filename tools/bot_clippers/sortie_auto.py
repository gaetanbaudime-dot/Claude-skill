"""Sortie automatique à 14 jours (28/09, feu vert de Gaëtan : « code-le, et réattribue comptes et liens au suivant »).

Chaque jour à SORTIE_AUTO_HEURE_UTC (8 h, après le scan Apify du classeur) : un clipper signé avec une créatrice depuis au
moins SORTIE_AUTO_JOURS jours (14), dont les comptes ont été regardés au moins SCANS_MIN fois (7) et n'ont JAMAIS porté une
publication, est sorti comme par `!sortie` : rôles et accès retirés, registre tracé, roster à jour — mais ses comptes créés
restent dans le vivier (Gérant vidé, état GOOD/WARMUP gardé) et son lien GAML est libéré : le prochain clipper de la même
créatrice les reçoit, avec l'e-mail rattaché à son salon pour que le code de CONNEXION arrive chez lui.

Ne touche jamais : le staff, les anciens gérés par Jonas (`sans_salon` du roster), un clipper sans données de scan, un clipper
dont une note du manager contient « garde ». `SORTIE_AUTO=0` éteint. `!sortie-auto` (admin) : liste ce qui partirait ;
`!sortie-auto go` : l'applique maintenant. Le module ne connaît pas bot_discord : dépendances dans `configurer(deps)`.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("sortie_auto")

ACTIF = os.environ.get("SORTIE_AUTO", "1").strip() != "0"
JOURS = int(os.environ.get("SORTIE_AUTO_JOURS", "14") or 14)
SCANS_MIN = int(os.environ.get("SORTIE_AUTO_SCANS_MIN", "7") or 7)
HEURE_UTC = int(os.environ.get("SORTIE_AUTO_HEURE_UTC", "8") or 8)
RAISON = f"{JOURS} jours sans Reel (sortie automatique)"
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_EQUIPES, etats_lire (-> etats_comptes.json), comptes_lire (async ->
    lignes du classeur), notes (uid -> [textes]), sortir (async membre, raison, pool), membre_par_id, prenom_de, roster, canal_admin,
    normaliser, heure_paris."""
    _deps.update(deps)


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _jour(iso) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(iso)[:19])
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def debut_de(fiche: dict, onboarding: dict, uid: str) -> datetime | None:
    """Le point de départ des 14 jours : le plus récent entre l'attribution de la créatrice et la livraison des comptes."""
    dates = [fiche.get("creatrice_date"), fiche.get("date"), (onboarding.get("clippers", {}).get(str(uid)) or {}).get("date")]
    dates = [d for d in (_jour(x) for x in dates) if d is not None]
    return max(dates) if dates else None


def a_sortir(fiches: dict, onboarding: dict, historique: dict, comptes: list, notes, prenom_de, maintenant=None,
             jours: int = JOURS, scans_min: int = SCANS_MIN, garder=()) -> list:
    """[(uid, prénom, jours depuis le début, scans)] des clippers à sortir : créatrice attribuée depuis ≥ `jours`, au moins
    `scans_min` scans de leurs comptes, aucune publication vue, pas de note « garde », pas dans `garder` (prénoms protégés)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    proteges = {_n(p) for p in garder}
    par_prenom = {}
    for c in comptes:
        g = _n(c.get("gerant") or "")
        if g and c.get("handle"):
            par_prenom.setdefault(g, []).append(str(c["handle"]).lower())
    out = []
    for uid, fiche in fiches.items():
        if not fiche.get("creatrice"):
            continue
        prenom = prenom_de(uid) or ""
        if not prenom or _n(prenom) in proteges:
            continue
        debut = debut_de(fiche, onboarding, uid)
        if debut is None or (maintenant - debut).days < jours:
            continue
        if any("garde" in _n(t) for t in (notes(uid) if notes else [])):
            continue
        handles = set(par_prenom.get(_n(prenom), [])) | {str(h).lower() for h in (onboarding.get("clippers", {}).get(str(uid)) or {}).get("comptes", [])}
        scans, publications = 0, 0
        for h in handles:
            for e in historique.get(h, []) or []:
                if e.get("existe"):
                    scans += 1
                    publications += int(e.get("posts") or 0)
        if scans < scans_min or publications > 0:
            continue
        out.append((str(uid), prenom, (maintenant - debut).days, scans))
    return out


def _etat() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {"sorties": {}})


async def executer(client, appliquer: bool = True) -> list:
    """Un passage. Renvoie les lignes du bilan (vide si personne)."""
    if not ACTIF and appliquer:
        return []
    fiches = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    onboarding = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}) if _deps.get("FICHIER_ONBOARDING") else {}
    historique = ((_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}).get("historique", {})
    try:
        comptes = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Sortie automatique : classeur illisible (%s), passage annulé", erreur)
        return []
    roster = _deps.get("roster")
    garder = list(roster.lire().get("sans_salon", [])) if roster is not None else []

    def prenom_de(uid):
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        return _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""

    cibles = a_sortir(fiches, onboarding, historique, comptes, _deps.get("notes"), prenom_de, garder=garder)
    if not cibles:
        return []
    bilan = []
    for uid, prenom, nb_jours, scans in cibles:
        if not appliquer:
            bilan.append(f"· {prenom} : {nb_jours} jours depuis sa créatrice, {scans} scans, 0 publication → sortirait")
            continue
        m = _deps["membre_par_id"](uid)
        if m is None:
            continue
        try:
            res = await _deps["sortir"](m, RAISON, pool=True)
            d = _etat()
            d.setdefault("sorties", {})[uid] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "prenom": prenom,
                                                 "jours": nb_jours, "scans": scans}
            _deps["ecrire_json"](_deps["FICHIER"], d)
            bilan.append(f"🚪 {prenom} : sorti ({nb_jours} jours, 0 publication) · comptes rendus au vivier : {res.get('comptes', 0)} · "
                         f"lien libéré : {res.get('liens', 0)}")
            journal.info("Sortie automatique : %s (%s) après %d jours, %d scans", prenom, uid, nb_jours, scans)
        except Exception as erreur:                                         # noqa: BLE001
            bilan.append(f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}")
            journal.warning("Sortie automatique de %s : %s", prenom, erreur)
    return bilan


async def commande(message, texte: str) -> bool:
    """`!sortie-auto` : qui partirait aujourd'hui ; `!sortie-auto go` : sortir maintenant."""
    if not texte.lower().startswith("!sortie-auto"):
        return False
    go = texte.lower().split()[1:2] == ["go"]
    bilan = await executer(message.client if hasattr(message, "client") else None, appliquer=go)
    if not bilan:
        await message.reply(f"✅ Personne à sortir : aucun clipper à {JOURS} jours ou plus sans publication (avec {SCANS_MIN} scans au moins)."
                            + ("" if ACTIF else " Sortie automatique éteinte (`SORTIE_AUTO=0`)."))
        return True
    await message.reply((("🚪 **Sorties automatiques**\n" if go else f"🔎 **Sortiraient aujourd'hui** (`!sortie-auto go` pour le faire)\n")
                         + "\n".join(bilan))[:1990])
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Sortie automatique éteinte (SORTIE_AUTO=0)")
        return
    journal.info("Sortie automatique active : %d jours sans publication, %d scans au moins, à %d h UTC", JOURS, SCANS_MIN, HEURE_UTC)
    while not client.is_closed():
        maintenant = datetime.now(timezone.utc)
        d = _etat()
        jour = maintenant.strftime("%Y-%m-%d")
        if maintenant.hour >= HEURE_UTC and d.get("dernier") != jour:
            try:
                premiere = not d.get("dernier")                                # la toute première passe ne sort personne : liste seulement
                bilan = await executer(client, appliquer=not premiere)
                d = _etat()
                d["dernier"] = jour
                _deps["ecrire_json"](_deps["FICHIER"], d)
                if bilan and _deps.get("canal_admin"):
                    canal = await _deps["canal_admin"]()
                    if canal is not None:
                        entete = ("🔎 **Sortie automatique, première liste** — rien n'est fait aujourd'hui. Demain à la même heure, ces "
                                  "clippers sortent tout seuls (`!sortie-auto go` pour le faire maintenant, `!note @x garde` pour en protéger un).\n"
                                  if premiere else "🚪 **Sorties automatiques du jour**\n")
                        await canal.send((entete + "\n".join(bilan))[:1990])
            except Exception as erreur:                                     # noqa: BLE001
                journal.warning("Boucle de sortie automatique : %s", erreur)
        await asyncio.sleep(1800)
