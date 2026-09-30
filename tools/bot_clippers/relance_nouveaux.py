"""Relance simple, une fois par jour, des nouveaux qui n'ont pas encore rendu leur test de montage (30/09, Gaëtan : « fais une
relance simple tous les jours pour les nouveaux, afin qu'ils fassent le test de montage vidéo »).

Avant : deux relances seulement (24 h et 48 h après la liaison pour le quiz, 24 h après l'envoi pour le test), puis silence
jusqu'à la sortie à 7 jours (Joaoo : accueilli le 28/09, plus rien du bot ensuite). Maintenant, chaque jour à HEURE (Paris),
dans son salon, UNE ligne selon son étape :
  · quiz pas encore réussi → « ton test de montage arrive juste après le quiz », avec son lien de quiz ;
  · test envoyé, pas rendu → « ton test t'attend », le lien du dossier et les heures qui restent.
Jamais le jour de son arrivée (ni dans les 20 h qui suivent l'envoi du test), jamais deux fois le même jour, jamais après un
STOP, jamais pour un signé, un membre du staff ou quelqu'un qui a déjà rendu son test. La sortie à 7 jours sans quiz reste.
RELANCE_NOUVEAUX=0 éteint (les anciennes relances 24/48 h reviennent)."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord

journal = logging.getLogger("relance_nouveaux")
ACTIF = os.environ.get("RELANCE_NOUVEAUX", "1").strip() != "0"
HEURE = int(os.environ.get("RELANCE_NOUVEAUX_HEURE", "11") or 11)
DELAI_H = 20                                                            # pas de relance dans les 20 h qui suivent l'arrivée / le test
FINIS = ("quiz_ok", "test_rendu", "valide", "refuse", "test_expire", "sorti")
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PIPELINE, FICHIER_EQUIPES, client, heure_paris, salon_perso (uid),
    lien_quiz (uid), LIEN_TEST, est_staff (membre)."""
    _deps.update(deps)


def _date(iso):
    try:
        d = datetime.fromisoformat(str(iso))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def texte(etape: str, mention: str, lien: str = "", heures: int = 0) -> str:
    if etape == "test":
        return (f"🎬 {mention} Ton test de montage t'attend : {lien}\n\n"
                "Monte 1 vidéo du dossier en Reel vertical. Envoie-la ici avec le **+**."
                + (f"\n\n⏳ Il te reste {heures} h." if heures > 0 else ""))
    return (f"👋 {mention} Ton test de montage vidéo arrive juste après le quiz.\n\n"
            "Étape du jour : regarde la formation, puis fais le quiz."
            + (f"\n\n{lien}" if lien else ""))


def a_relancer(uid: str, pipe: dict, signes: dict, arrivee, maintenant) -> tuple:
    """(étape, heures restantes) si ce membre doit être relancé aujourd'hui, sinon None."""
    if uid in signes:
        return None
    info = (pipe.get("etats") or {}).get(uid) or {}
    stop = any(bool((d or {}).get("stop")) for d in (info.get("relances"), (pipe.get("liaisons") or {}).get(uid),
                                                        (pipe.get("arrivees") or {}).get(uid)))
    if stop or info.get("etat") in FINIS:
        return None
    if info.get("etat") == "test_envoye":
        envoi, echeance = _date(info.get("envoi")), _date(info.get("echeance"))
        if info.get("mp_ok") is False or envoi is None or maintenant - envoi < timedelta(hours=DELAI_H):
            return None
        reste = int((echeance - maintenant).total_seconds() // 3600) if echeance else 0
        return ("test", reste) if reste > 0 else None
    if arrivee is not None and maintenant - arrivee < timedelta(hours=DELAI_H):
        return None
    return ("quiz", 0)


async def passage(maintenant=None) -> list:
    """Un passage : relance chaque nouveau concerné. Renvoie [(uid, étape)]."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jour = _deps["heure_paris"]().strftime("%Y-%m-%d")
    etat = _deps["lire_json"](_deps["FICHIER"], {})
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
    signes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    faits = []
    for g in _deps["client"].guilds:
        for m in g.members:
            uid = str(m.id)
            if m.bot or etat.get(uid) == jour or _deps["est_staff"](m):
                continue
            arrivee = m.joined_at if m.joined_at is None or m.joined_at.tzinfo else m.joined_at.replace(tzinfo=timezone.utc)
            quoi = a_relancer(uid, pipe, signes, arrivee, maintenant)
            if quoi is None:
                continue
            salon = _deps["salon_perso"](uid)
            if salon is None:
                continue
            etape, reste = quoi
            lien = _deps["LIEN_TEST"] if etape == "test" else (_deps["lien_quiz"](uid) or "")
            try:
                await salon.send(texte(etape, m.mention, lien, reste)[:1990])
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.info("Relance du nouveau %s : %s", uid, erreur)
                continue
            etat[uid] = jour
            faits.append((uid, etape))
            await asyncio.sleep(1.2)
    if faits:
        _deps["ecrire_json"](_deps["FICHIER"], etat)
        journal.info("Relance des nouveaux : %d (%s)", len(faits), ", ".join(e for _, e in faits))
    return faits


async def boucle(client):
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if ACTIF and _deps["heure_paris"]().hour >= HEURE:
                await passage()
        except Exception as erreur:                                     # noqa: BLE001 — la boucle ne meurt jamais
            journal.warning("Relance des nouveaux : %s", erreur)
        await asyncio.sleep(1800)
