"""Attribution automatique des créatrices (27/09, décision de Gaëtan) : « dans l'ordre Sophie > Sarah > Chloé > Clara >
Jade, une par une ». Dès qu'un clipper accepte les règles, il reçoit la créatrice suivante de la rotation et tout ce que
`!creatrice` faisait (salon perso, pseudo, rôles, comptes du classeur, lien, Drive, alias 2FA, parcours). Au démarrage,
les signés présents sur le serveur sans créatrice sont rattrapés un par un, avec une pause entre deux.

Ordre : ATTRIBUTION_ORDRE (défaut « Sophie,Sarah,Chloé,Clara,Jade »). Une créatrice sans catégorie ni rôle sur le
serveur est sautée (et dite au salon admin). ATTRIBUTION_AUTO=0 éteint tout. État dans DONNEES/attribution.json."""

import asyncio
import os
from datetime import datetime, timezone

import discord

journal = __import__("logging").getLogger("bot_clippers")

ORDRE = [c.strip() for c in os.environ.get("ATTRIBUTION_ORDRE", "Sophie,Sarah,Chloé,Clara,Jade").split(",") if c.strip()]
ACTIF = os.environ.get("ATTRIBUTION_AUTO", "1").strip() != "0"
PAUSE_SEC = int(os.environ.get("ATTRIBUTION_PAUSE_SEC", "90"))
_deps = {}


class _Par:
    display_name, id = "attribution automatique", "auto"


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, FICHIER_EQUIPES, categorie_de_creatrice, role_creatrice, onboarder_membre,
    canal_admin, membre_par_id, est_staff, prenom_de, roster, etats_classeur (async), normaliser."""
    _deps.update(deps)


def actif() -> bool:
    return ACTIF and bool(ORDRE)


def _etat() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {"index": 0, "historique": []})


def _ecrire(e: dict):
    _deps["ecrire_json"](_deps["FICHIER"], e)


def _existe(guild, creatrice: str) -> bool:
    if guild is None:
        return True
    try:
        return _deps["categorie_de_creatrice"](guild, creatrice) is not None or _deps["role_creatrice"](guild, creatrice) is not None
    except Exception:                                                       # noqa: BLE001
        return False


def prochaine(guild) -> tuple:
    """La créatrice suivante de la rotation (et une note si des créatrices ont été sautées). Avance l'index."""
    e = _etat()
    n = len(ORDRE)
    sautees = []
    for k in range(n):
        i = (int(e.get("index", 0)) + k) % n
        if _existe(guild, ORDRE[i]):
            e["index"] = (i + 1) % n
            _ecrire(e)
            return ORDRE[i], (" · sautée(s), sans catégorie ni rôle sur le serveur : " + ", ".join(sautees)) if sautees else ""
        sautees.append(ORDRE[i])
    i = int(e.get("index", 0)) % n
    e["index"] = (i + 1) % n
    _ecrire(e)
    return ORDRE[i], " · ⚠️ aucune créatrice de l'ordre n'a de catégorie ni de rôle sur le serveur"


def sans_creatrice(membre) -> bool:
    fiche = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(membre.id)) or {}
    if fiche.get("creatrice"):
        return False
    roster = _deps.get("roster")
    prenom = _deps["prenom_de"](membre)
    return not (roster and (roster.creatrice_de(prenom) or roster.sans_salon(prenom)))


async def attribuer(membre, via: str) -> str:
    """Attribue la créatrice suivante à un membre signé sans créatrice ; renvoie son prénom, ou "" si rien à faire."""
    if not actif() or membre is None or getattr(membre, "bot", False) or not sans_creatrice(membre):
        return ""
    creatrice, note = prochaine(membre.guild)
    try:
        etats_cl = await _deps["etats_classeur"]()
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("États du classeur pour l'attribution : %s", erreur)
        etats_cl = {}
    try:
        bilan = await _deps["onboarder_membre"](membre.guild, membre, creatrice, _Par(), etats_cl, [], forcer_salon=True)
    except Exception as erreur:                                             # noqa: BLE001
        bilan = f"❌ {type(erreur).__name__} {str(erreur)[:120]}"
    e = _etat()
    e.setdefault("historique", []).append({"uid": str(membre.id), "prenom": _deps["prenom_de"](membre), "creatrice": creatrice,
                                           "via": via, "date": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    e["historique"] = e["historique"][-300:]
    _ecrire(e)
    journal.info("Attribution automatique : %s → %s (%s)", _deps["prenom_de"](membre), creatrice, via)
    admin = await _deps["canal_admin"]()
    if admin is not None:
        try:
            await admin.send((f"🎬 **Attribution automatique** : {membre.mention} → **{creatrice}** "
                              f"(ordre {' > '.join(ORDRE)}, {via}){note}\n{bilan}")[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass
    return creatrice


async def rattraper(client) -> list:
    """Au démarrage : chaque signé présent sur le serveur sans créatrice reçoit la suivante, un par un, PAUSE_SEC entre deux."""
    await client.wait_until_ready()
    if not actif() or not client.guilds:
        return []
    await asyncio.sleep(int(os.environ.get("ATTRIBUTION_DELAI_DEMARRAGE_SEC", "120")))   # après le roster et les boutons
    faits = []
    for uid, fiche in list(_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).items()):
        if fiche.get("creatrice"):
            continue
        membre = _deps["membre_par_id"](uid)
        if membre is None or getattr(membre, "bot", False) or _deps["est_staff"](membre):
            continue
        creatrice = await attribuer(membre, "rattrapage au démarrage")
        if creatrice:
            faits.append((_deps["prenom_de"](membre), creatrice))
            await asyncio.sleep(PAUSE_SEC)
    if faits:
        journal.info("Attribution automatique, rattrapage : %s", faits)
    return faits
