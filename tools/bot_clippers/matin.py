"""Le message du matin, un seul par clipper (26/09, Gaëtan : « garde uniquement l'essentiel et la prochaine étape »).

Avant, trois modules écrivaient chacun dans le salon perso : le bilan des Reels (inputs), la ligne des visites
(paie au clic), le jour de warm-up (parcours). Ils déposent maintenant leur morceau ici, et le bot envoie UN
message : les chiffres d'hier, puis « 👉 Aujourd'hui : … », la prochaine étape du parcours. L'envoi part entre
MATIN_HEURE_MIN et MATIN_HEURE_MAX (UTC) : dès que le bilan des Reels est arrivé, ou à l'heure limite. Un morceau
déposé après l'envoi du jour part tout seul, comme avant. Dépendances dans `configurer(deps)` : lire_json,
ecrire_json, FICHIER_MATIN, heure_paris, prochaine_etape(salon_id), prenom_salon(salon_id), inputs_actifs()."""
import asyncio
import logging
import os
from datetime import datetime, timezone

import discord

journal = logging.getLogger("matin")

MATIN_HEURE_MIN = int(os.environ.get("MATIN_HEURE_MIN_UTC", "8") or 8)     # jamais avant (10 h Paris)
MATIN_HEURE_MAX = int(os.environ.get("MATIN_HEURE_MAX_UTC", "10") or 10)   # au plus tard, même sans bilan des Reels

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_MATIN"], {})
    d.setdefault("morceaux", {}); d.setdefault("envoyes", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_MATIN"], d)


def _jour() -> str:
    return _deps["heure_paris"]().strftime("%Y-%m-%d")


def deposer(salon_id, cle: str, texte: str) -> bool:
    """Garde un morceau pour le message du matin de ce salon. False = le message du jour est déjà parti (ou le module
    n'est pas configuré) : l'appelant envoie lui-même."""
    if not _deps or not salon_id or not texte:
        return False
    d = _lire()
    jour, sid = _jour(), str(salon_id)
    if d["envoyes"].get(sid) == jour:
        return False
    m = d["morceaux"].setdefault(sid, {})
    if m.get("jour") != jour:
        m.clear()
        m["jour"] = jour
    m[cle] = texte
    _ecrire(d)
    return True


def composer(salon_id, m: dict) -> str:
    prenom = (_deps["prenom_salon"](salon_id) if _deps.get("prenom_salon") else "") or ""
    lignes = [f"☀️ **Bonjour {prenom}**".rstrip() if prenom else "☀️ **Bonjour**"]
    for cle in ("inputs", "clics"):
        if m.get(cle):
            lignes.append(m[cle])
    if m.get("warmup"):
        lignes.append(m["warmup"])
    else:
        prochaine = (_deps["prochaine_etape"](salon_id) if _deps.get("prochaine_etape") else "") or ""
        if prochaine:
            lignes.append(f"👉 **Aujourd'hui** : {prochaine}")
    return "\n".join(lignes)


async def envoyer_prets(client, force: bool = False) -> int:
    """Envoie les messages du jour prêts : bilan des Reels reçu, ou heure limite passée, ou `force`."""
    d = _lire()
    jour = _jour()
    heure = datetime.now(timezone.utc).hour
    if not force and not (MATIN_HEURE_MIN <= heure <= MATIN_HEURE_MAX + 1):
        return 0                                                        # 26/09 : jamais de message du matin l'après-midi (Daniella, 17 h)
    attendre_inputs = _deps.get("inputs_actifs", lambda: False)() and heure < MATIN_HEURE_MAX and not force
    envoyes = 0
    for sid, m in list(d["morceaux"].items()):
        if m.get("jour") != jour or d["envoyes"].get(sid) == jour:
            continue
        if attendre_inputs and "inputs" not in m:
            continue
        salon = client.get_channel(int(sid))
        if salon is None:
            d["envoyes"][sid] = jour
            continue
        try:
            await salon.send(composer(sid, m)[:1990])
            envoyes += 1
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Message du matin %s : %s", sid, erreur)
        d["envoyes"][sid] = jour
    for sid in [s for s, j in d["envoyes"].items() if j < jour and s not in d["morceaux"]]:
        d["envoyes"].pop(sid, None)
    _ecrire(d)
    if envoyes:
        journal.info("Messages du matin envoyés : %d", envoyes)
    return envoyes


async def boucle(client) -> None:
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if MATIN_HEURE_MIN <= datetime.now(timezone.utc).hour <= MATIN_HEURE_MAX + 1:
                await envoyer_prets(client)
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.exception("Boucle du matin : %s", erreur)
        await asyncio.sleep(300)
