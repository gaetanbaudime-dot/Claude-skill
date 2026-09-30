"""Relance Telegram en un appui (30/09, Gaëtan : « go idée 3 avec Telegram uniquement »).

Chaque matin à RELANCES_HEURE (10 h, Paris), le bot poste dans le salon admin la liste des candidats qui ont envoyé le
formulaire du site depuis plus de 24 h sans réussir le quizz et sans être arrivés sur Discord (ceux-là, le bot les relance
déjà dans leur salon). Pour chacun : prénom, pays, depuis quand, le lien qui ouvre sa conversation Telegram, et le message à
copier d'un appui, avec SON lien vers la page formation (il reprend là où il s'était arrêté, sans refaire le formulaire).

Rien ne part tout seul : Gaëtan (ou Rianah) ouvre la conversation, colle, envoie. Deux relances au plus par candidat
(à 24 h puis à 72 h), RELANCES_MAX par jour (30 : le rythme qui ne fait pas restreindre un compte Telegram), candidatures
des 7 derniers jours seulement. Sans @ Telegram lisible, le lien par numéro (t.me/+numéro) ne marche que si le candidat
l'autorise dans ses réglages : il est signalé comme tel.

`!relances` (staff) : la liste tout de suite (comptée comme envoyée) ; `!relances voir` : l'aperçu, rien de compté.
État dans DONNEES/relances.json : {"dernier": jour, "relances": {cand_id: [dates iso]}}. RELANCES=0 éteint."""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

journal = logging.getLogger("relances")
ACTIF = os.environ.get("RELANCES", "1").strip() != "0"
HEURE = int(os.environ.get("RELANCES_HEURE", "10") or 10)
MAX_JOUR = int(os.environ.get("RELANCES_MAX", "30") or 30)
DELAIS_H = (24, 72)                                                        # 1re relance à 24 h, 2e à 72 h
FENETRE_JOURS = 7
APRES_QUIZ = ("quiz_ok", "test_envoye", "test_rendu", "valide", "refuse", "test_expire")
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PIPELINE, heure_paris, canal_admin (async), est_staff,
    lien_formation (cand_id -> url)."""
    _deps.update(deps)


def _jour(iso):
    try:
        d = datetime.fromisoformat(str(iso)[:25])
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def lien_telegram(pseudo: str, tel: str = "") -> tuple:
    """(lien, étiquette) : t.me/pseudo si un @ ou un lien t.me est lisible, sinon t.me/+numéro (étiquette « par numéro »),
    sinon ("", "")."""
    p = (pseudo or "").strip()
    m = re.search(r"(?:t\.me|telegram\.me|telegram\.dog)/@?([A-Za-z][A-Za-z0-9_]{4,31})", p) \
        or re.fullmatch(r"@?\s*([A-Za-z][A-Za-z0-9_]{4,31})", p)
    if m:
        return f"https://t.me/{m.group(1)}", f"@{m.group(1)}"
    chiffres = re.sub(r"\D", "", p) if len(re.sub(r"\D", "", p)) >= 8 else re.sub(r"\D", "", tel or "")
    if len(chiffres) >= 8:
        return f"https://t.me/+{chiffres}", "par numéro"
    return "", ""


def texte_message(prenom: str, lien: str) -> str:
    return (f"Salut {prenom} ! Ta candidature est bien reçue ✅\n\n"
            f"Il te reste la formation (15 min) et le quizz, ici : {lien}\n\n"
            "Dès que c'est fait, tu rejoins le Discord.")


def a_relancer(pipe: dict, etat: dict, maintenant=None) -> list:
    """[(cand_id, prénom, pays, heures depuis le formulaire, n° de relance, lien Telegram, étiquette)], les plus anciens
    d'abord, RELANCES_MAX au plus."""
    maintenant = maintenant or datetime.now(timezone.utc)
    lies = {str(l.get("tel")) for l in (pipe.get("liaisons") or {}).values() if l.get("tel")}
    deja = etat.get("relances") or {}
    out = []
    for cid, fiche in (pipe.get("candidatures_web") or {}).items():
        d = _jour(fiche.get("date"))
        if d is None:
            continue
        heures = (maintenant - d).total_seconds() / 3600
        if heures < DELAIS_H[0] or heures > FENETRE_JOURS * 24:
            continue
        if (fiche.get("quiz") or {}).get("reussi") or str(fiche.get("tel")) in lies:
            continue
        faites = deja.get(cid) or []
        if len(faites) >= len(DELAIS_H) or heures < DELAIS_H[len(faites)]:
            continue
        if faites and (maintenant - _jour(faites[-1])).total_seconds() < 20 * 3600:
            continue
        cand = (pipe.get("candidatures") or {}).get(str(fiche.get("tel"))) or {}
        prenom = str(cand.get("prenom") or "").strip() or "toi"
        if prenom.lower().startswith("test"):
            continue
        lien, etiquette = lien_telegram(cand.get("pseudo", ""), str(fiche.get("tel") or ""))
        tel = str(fiche.get("tel") or "")
        if not lien and len(re.sub(r"\D", "", tel)) < 8:
            continue
        out.append((cid, prenom, cand.get("pays", ""), int(heures), len(faites) + 1, lien, etiquette, tel))
    out.sort(key=lambda x: -x[3])
    return out[:MAX_JOUR]


def blocs(liste: list) -> list:
    """Un message Discord par candidat : la ligne d'info, puis le message à copier dans un bloc de code."""
    out = []
    for cid, prenom, pays, heures, n, lien, etiquette, tel in liste:
        texte = texte_message(prenom, _deps["lien_formation"](cid))
        # 30/09 (Gaëtan, GO n° 2 : « relances WhatsApp en un appui ») : le lien WhatsApp ouvre sa conversation, message déjà écrit
        chiffres = re.sub(r"\D", "", tel or "")
        wa = f"[WhatsApp](https://wa.me/{chiffres}?text={quote(texte)})" if len(chiffres) >= 8 else ""
        tg = f"Telegram {etiquette} : <{lien}>" if lien else ""
        info = (f"**{prenom}**{' · ' + pays if pays else ''} · formulaire il y a {heures} h · "
                f"{'1re' if n == 1 else '2e'} relance · " + " · ".join(x for x in (wa, tg) if x))
        out.append(info + "\n```\n" + texte + "\n```")
    return out


async def envoyer(canal, compter: bool = True, muet_si_vide: bool = False) -> int:
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
    etat = _deps["lire_json"](_deps["FICHIER"], {"relances": {}})
    liste = a_relancer(pipe, etat)
    if not liste:
        if not muet_si_vide:                                            # le matin, rien quand il n'y a personne
            await canal.send("📨 Relances Telegram : personne à relancer aujourd'hui.")
        return 0
    await canal.send(f"📨 **Relances du jour ({len(liste)})** — formulaire envoyé, quizz pas réussi, pas encore sur Discord. "
                     "WhatsApp : appuie, relis, envoie. Telegram : ouvre, colle, envoie."
                     + ("" if compter else " _(aperçu : rien n'est compté)_"))
    for b in blocs(liste):
        await canal.send(b[:1990], suppress_embeds=True)
    if compter:
        etat = _deps["lire_json"](_deps["FICHIER"], {"relances": {}})
        maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for cid, *_ in liste:
            etat.setdefault("relances", {}).setdefault(cid, []).append(maintenant)
        _deps["ecrire_json"](_deps["FICHIER"], etat)
    journal.info("Relances Telegram : %d candidat(s) listé(s)%s", len(liste), "" if compter else " (aperçu)")
    return len(liste)


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith("!relances"):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    await envoyer(message.channel, compter=not texte.lower().rstrip().endswith("voir"))
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Relances Telegram éteintes (RELANCES=0)")
        return
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            etat = _deps["lire_json"](_deps["FICHIER"], {"relances": {}})
            if maintenant.hour >= HEURE and etat.get("dernier") != jour:
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await envoyer(canal, muet_si_vide=True)
                    etat = _deps["lire_json"](_deps["FICHIER"], {"relances": {}})
                    etat["dernier"] = jour
                    _deps["ecrire_json"](_deps["FICHIER"], etat)
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Boucle des relances Telegram : %s", erreur)
        await asyncio.sleep(1200)
