"""Relance des arrivés sur Discord qui n'ont pas encore réussi le quizz (30/09, refondue le 09/10).

30/09 (Gaëtan : « fais une relance simple tous les jours pour les nouveaux ») : une ligne par jour, dans le salon du nouveau.

09/10 (Gaëtan : « on va ouvrir les vannes » et « Chaque étape à la fois, on se complique pas la vie ») : le test vidéo
d'entrée n'existe plus et le quizz se fait sur le site, AVANT Discord. Presque personne n'arrive donc
sans quizz : le module est ÉTEINT par défaut (RELANCE_NOUVEAUX=1 pour le rallumer). Rallumé, il n'envoie qu'un texte, son lien
de quizz, au plus MAX_ENVOIS fois et jamais deux fois le même jour. Jamais le jour de l'arrivée (DELAI_H), jamais après un STOP,
jamais pour un signé (registre, rôle d'équipe, roster : est_signe), un membre du staff ou quelqu'un qui a déjà réussi le quizz.
La sortie à 2 jours sans quizz reste (boucle_pipeline ⑥).

État dans DONNEES/relance_nouveaux.json : {uid: {"jour": "AAAA-MM-JJ", "n": envois}} (l'ancienne forme {uid: jour} vaut 1 envoi)."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord

journal = logging.getLogger("relance_nouveaux")
ACTIF = os.environ.get("RELANCE_NOUVEAUX", "0").strip() != "0"         # 09/10 : éteint par défaut
HEURE = int(os.environ.get("RELANCE_NOUVEAUX_HEURE", "11") or 11)
DELAI_H = 20                                                            # pas de relance dans les 20 h qui suivent l'arrivée
MAX_ENVOIS = 2                                                          # 09/10 : deux relances au plus, puis silence
# 09/10 : un membre dans l'un de ces états a passé le quizz (ou est sorti). Un ancien état « test_* » d'avant la migration vaut
# aussi « quizz réussi » (voir a_relancer).
FINIS = ("quiz_ok", "valide", "attente_attribution", "refuse", "sorti")
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PIPELINE, FICHIER_EQUIPES, client, heure_paris, salon_perso (uid),
    lien_quiz (uid), est_staff (membre) ; est_signe (membre), facultatif. 09/10 : l'ancien lien du dossier de test n'est plus
    lu (une clé en trop dans deps est ignorée)."""
    _deps.update(deps)


def _date(iso):
    try:
        d = datetime.fromisoformat(str(iso))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def texte(mention: str, lien: str) -> str:
    """09/10 (Gaëtan : « Saute des lignes, aère ») : une seule action, son lien de quizz."""
    return (f"👋 {mention}\n\n"
            f"Ton quizz t'attend : {lien}\n\n"
            "Réussi = ta créatrice et ton compte 1 arrivent ici.")


def suivi(valeur) -> dict:
    """L'état d'un membre : {"jour", "n"}. L'ancienne forme (le jour seul) compte pour un envoi."""
    if isinstance(valeur, dict):
        return {"jour": str(valeur.get("jour") or ""), "n": int(valeur.get("n") or 0)}
    return {"jour": str(valeur or ""), "n": 1 if valeur else 0}


def a_relancer(uid: str, pipe: dict, signes: dict, arrivee, maintenant, signe: bool = False, envois: int = 0) -> tuple:
    """("quiz", 0) si ce membre doit être relancé aujourd'hui, sinon None. 09/10 : plus de branche « test » ; jamais un signé
    (`signes` = le registre, `signe` = est_signe du membre), jamais au-delà de MAX_ENVOIS."""
    if uid in signes or signe or envois >= MAX_ENVOIS:
        return None
    info = (pipe.get("etats") or {}).get(uid) or {}
    stop = any(bool((d or {}).get("stop")) for d in (info.get("relances"), (pipe.get("liaisons") or {}).get(uid),
                                                        (pipe.get("arrivees") or {}).get(uid)))
    etat = str(info.get("etat") or "")
    if stop or etat in FINIS or etat.startswith("test_"):
        return None
    if arrivee is not None and maintenant - arrivee < timedelta(hours=DELAI_H):
        return None
    return ("quiz", 0)


async def passage(maintenant=None) -> list:
    """Un passage : relance chaque nouveau concerné. Renvoie [(uid, "quiz")]."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jour = _deps["heure_paris"]().strftime("%Y-%m-%d")
    etat = _deps["lire_json"](_deps["FICHIER"], {})
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
    signes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    est_signe = _deps.get("est_signe")
    faits = []
    for g in _deps["client"].guilds:
        for m in g.members:
            uid = str(m.id)
            s = suivi(etat.get(uid))
            if m.bot or s["jour"] == jour or _deps["est_staff"](m):
                continue
            arrivee = m.joined_at if m.joined_at is None or m.joined_at.tzinfo else m.joined_at.replace(tzinfo=timezone.utc)
            try:
                signe = bool(est_signe(m)) if est_signe else False
            except Exception as erreur:                                 # noqa: BLE001 — dans le doute, on ne relance pas
                journal.info("est_signe(%s) : %s", uid, erreur)
                continue
            quoi = a_relancer(uid, pipe, signes, arrivee, maintenant, signe=signe, envois=s["n"])
            if quoi is None:
                continue
            lien = _deps["lien_quiz"](uid) or ""
            salon = _deps["salon_perso"](uid)
            if salon is None or not lien:
                continue
            try:
                await salon.send(texte(m.mention, lien)[:1990])
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.info("Relance du nouveau %s : %s", uid, erreur)
                continue
            etat[uid] = {"jour": jour, "n": s["n"] + 1}
            faits.append((uid, quoi[0]))
            await asyncio.sleep(1.2)
    if faits:
        _deps["ecrire_json"](_deps["FICHIER"], etat)
        journal.info("Relance des nouveaux : %d", len(faits))
    return faits


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Relance des nouveaux éteinte (RELANCE_NOUVEAUX=0, défaut depuis le 09/10)")
        return
    while not client.is_closed():
        try:
            if _deps["heure_paris"]().hour >= HEURE:
                await passage()
        except Exception as erreur:                                     # noqa: BLE001 — la boucle ne meurt jamais
            journal.warning("Relance des nouveaux : %s", erreur)
        await asyncio.sleep(1800)
