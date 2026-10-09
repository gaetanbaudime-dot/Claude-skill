"""Relance Telegram en un appui (30/09, Gaëtan : « go idée 3 avec Telegram uniquement »).

Chaque matin à RELANCES_HEURE (10 h, Paris), le bot poste dans le salon admin la liste des candidats qui ont envoyé le
formulaire du site depuis plus de 24 h sans réussir le quizz et sans être arrivés sur Discord (ceux-là, le bot les relance
déjà dans leur salon). Pour chacun : prénom, pays, depuis quand, le lien qui ouvre sa conversation Telegram, et le message à
copier d'un appui, avec SON lien vers la page formation (il reprend là où il s'était arrêté, sans refaire le formulaire).
09/10 : un message groupé (un candidat par bloc, coupé entre deux candidats au-delà de 1 990 caractères). Plus rien à copier :
un seul lien par candidat, Telegram ou WhatsApp, qui ouvre sa conversation avec le message déjà écrit (paramètre « text » des
liens t.me, documenté par Telegram pour t.me/<pseudo> comme pour t.me/+<numéro>). Un appui, relire, envoyer.

Rien ne part tout seul : Gaëtan (ou Rianah) appuie sur le lien, relit, envoie. Deux relances au plus par candidat
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
# 01/10 (Gaëtan : « une ligne par personne ») : les numéros du staff (candidatures de test), séparés par des virgules, ne sont
# jamais relancés ni comptés dans les candidatures du jour (comparés sur leurs 8 derniers chiffres).
EXCLURE_TELS = {re.sub(r"\D", "", t)[-8:] for t in os.environ.get("RELANCES_EXCLURE_TELS", "").split(",")
                if len(re.sub(r"\D", "", t)) >= 8}
_deps = {}


def cle_tel(tel) -> str:
    """Une personne = un numéro : ses 8 derniers chiffres (comme candidature_de), sinon le numéro tel quel."""
    chiffres = re.sub(r"\D", "", str(tel or ""))
    return chiffres[-8:] if len(chiffres) >= 8 else str(tel or "").strip()


def tel_exclu(tel) -> bool:
    """Numéro du staff (RELANCES_EXCLURE_TELS) : jamais relancé, jamais compté."""
    chiffres = re.sub(r"\D", "", str(tel or ""))
    return len(chiffres) >= 8 and chiffres[-8:] in EXCLURE_TELS


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


def a_relancer(pipe: dict, etat: dict, maintenant=None) -> list:
    """[(cand_id, prénom, pays, heures depuis le formulaire, n° de relance, lien Telegram, étiquette)], les plus anciens
    d'abord, RELANCES_MAX au plus.
    01/10 (Gaëtan : « une ligne par personne ») : `candidatures_web` a une entrée par ENVOI du formulaire (Lucio, Enzo : deux
    lignes et deux liens chacun le 30/09). Les envois sont regroupés par numéro : on garde le dernier (son lien le plus récent),
    les relances déjà faites comptent tous ses envois, un quizz réussi avec n'importe lequel de ses liens le sort de la liste,
    et les numéros du staff (RELANCES_EXCLURE_TELS) n'y sont jamais."""
    maintenant = maintenant or datetime.now(timezone.utc)
    lies = {cle_tel(l.get("tel")) for l in (pipe.get("liaisons") or {}).values() if l.get("tel")}
    deja = etat.get("relances") or {}
    web = pipe.get("candidatures_web") or {}
    par_tel = {}
    for cid, fiche in web.items():
        par_tel.setdefault(cle_tel(fiche.get("tel")), []).append(cid)
    out = []
    for cle, cids in par_tel.items():
        if cle in lies or any(tel_exclu(web[c].get("tel")) for c in cids):
            continue
        if any((web[c].get("quiz") or {}).get("reussi") for c in cids):
            continue
        cid = max(cids, key=lambda c: str(web[c].get("date") or ""))
        fiche = web[cid]
        d = _jour(fiche.get("date"))
        if d is None:
            continue
        heures = (maintenant - d).total_seconds() / 3600
        if heures < DELAIS_H[0] or heures > FENETRE_JOURS * 24:
            continue
        # ses relances, tous envois confondus ; deux lignes du même matin (l'ancien doublon) comptent pour une relance
        par_jour = {}
        for x in (x for c in cids for x in (deja.get(c) or [])):
            par_jour[str(x)[:10]] = max(par_jour.get(str(x)[:10], x), x, key=lambda y: _jour(y) or maintenant)
        faites = sorted(par_jour.values(), key=lambda x: _jour(x) or maintenant)
        if len(faites) >= len(DELAIS_H) or heures < DELAIS_H[len(faites)]:
            continue
        if faites and (maintenant - (_jour(faites[-1]) or maintenant)).total_seconds() < 20 * 3600:
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


def texte_relance(prenom: str, lien: str) -> str:
    """09/10 (revue du lot L3 : 10 messages pour 30 candidats, deux copies par candidat côté Telegram) : le message pré-rempli,
    court parce qu'il voyage encodé dans le lien. Bonjour, une action, son lien."""
    return f"Salut {prenom} 👋\n\nTa formation t'attend :\n\n{lien}"


def ligne(cid, prenom, pays, heures, n, lien, etiquette, tel) -> str:
    """Un candidat : prénom, pays, depuis quand, n° de relance ; dessous, UN lien qui ouvre sa conversation, message déjà écrit.
    Telegram s'il a un @ lisible (le funnel part de Telegram, t.me/<pseudo> s'ouvre toujours), sinon WhatsApp par son numéro,
    sinon Telegram par numéro (il ne s'ouvre que si le candidat l'autorise : signalé)."""
    texte = quote(texte_relance(prenom, _deps["lien_formation"](cid)), safe=":/")
    # 30/09 (Gaëtan, GO n° 2 : « relances WhatsApp en un appui ») : le lien WhatsApp ouvre sa conversation, message déjà écrit.
    # 09/10 (revue du lot L3) : le lien Telegram aussi (t.me/…?text=), et un seul lien par candidat : deux liens pré-remplis
    # doublaient la longueur (10 messages pour 30 candidats).
    chiffres = re.sub(r"\D", "", tel or "")
    if lien and etiquette != "par numéro":
        appui = f"[Telegram {etiquette}](<{lien}?text={texte}>)"
    elif len(chiffres) >= 8:
        appui = f"[WhatsApp](<https://wa.me/{chiffres}?text={texte}>)"
    else:
        appui = f"[Telegram par numéro](<{lien}?text={texte}>)" if lien else ""
    return f"**{prenom}**{' · ' + pays if pays else ''} · {heures} h · {'1re' if n == 1 else '2e'} relance\n{appui}"


def blocs(liste: list, apercu: bool = False) -> list:
    """09/10 (revue du funnel : « Relances admin : 1 + N messages par jour ») : un message groupé, coupé à 1990 caractères.
    L'en-tête (ce qu'il y a à faire, une fois), puis un candidat par bloc, une ligne vide entre deux. Une liste trop longue pour un
    message continue dans le suivant, coupée entre deux candidats, jamais au milieu d'un candidat."""
    entete = (f"📨 **Relances du jour : {len(liste)}**" + (" _(aperçu : rien n'est compté)_" if apercu else "") + "\n\n"
              "Formulaire envoyé, quizz pas réussi, pas encore sur Discord.\n\n"
              "Appuie sur son lien : son message est déjà écrit. Relis, envoie.")
    morceaux, courant = [], entete
    for x in liste:
        l_ = ligne(*x)[:1900]
        if len(courant) + 2 + len(l_) > 1990:
            morceaux.append(courant)
            courant = l_
        else:
            courant += "\n\n" + l_
    morceaux.append(courant)
    return morceaux


async def envoyer(canal, compter: bool = True, muet_si_vide: bool = False) -> int:
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
    etat = _deps["lire_json"](_deps["FICHIER"], {"relances": {}})
    liste = a_relancer(pipe, etat)
    if not liste:
        if not muet_si_vide:                                            # le matin, rien quand il n'y a personne
            await canal.send("📨 Relances Telegram : personne à relancer aujourd'hui.")
        return 0
    for b in blocs(liste, apercu=not compter):
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
