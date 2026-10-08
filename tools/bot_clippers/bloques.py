"""Les bloqués du matin, avec leur relance WhatsApp en un appui (30/09, Gaëtan : « GO la liste des bloqués chaque matin »,
« GO relances WhatsApp en un appui » ; les clippers répondent plus vite sur WhatsApp que sur Discord).

Chaque matin à BLOQUES_HEURE (11 h Paris, après le scan Instagram), le salon admin reçoit la liste des clippers du roster qui
n'avancent pas, le plus bloqué d'abord :
- compte à créer depuis trop longtemps : étape 1 depuis plus de 2 jours, étape 2 ou 3 depuis plus de 4 jours (48 h
  d'attente normale entre deux comptes, plus 48 h) ;
- plus de Reel depuis BLOQUES_JOURS_SANS_REEL jours (3) une fois les comptes créés.
Pour chacun : prénom, créatrice, où il bloque, et un lien WhatsApp qui ouvre SA conversation avec le message déjà écrit.
Rien ne part tout seul : Gaëtan appuie, relit, envoie (les envois automatiques font bannir un numéro WhatsApp). BLOQUES_MAX
par jour (25). `!bloques` (staff) : la liste tout de suite. BLOQUES=0 éteint."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote

journal = logging.getLogger("bloques")
ACTIF = os.environ.get("BLOQUES", "1").strip() != "0"
HEURE = int(os.environ.get("BLOQUES_HEURE", "11") or 11)
MAX_JOUR = int(os.environ.get("BLOQUES_MAX", "25") or 25)
JOURS_SANS_REEL = int(os.environ.get("BLOQUES_JOURS_SANS_REEL", "3") or 3)
# jours au-delà desquels une étape de compte bloque. 08/10 (critique de l'audit) : étape 1 dès 1 jour, le jour de
# l'avertissement — à « plus de 2 jours », le clipper était déjà sorti par la règle des 48 h avant d'être jamais listé.
JOURS_ETAPE = {1: 0, 2: 4, 3: 4}
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PARCOURS, roster_groupes (-> {créatrice: [prénoms]}),
    membre_par_prenom, tel_de (uid -> numéro), jours_sans_reel (async -> {uid: jours}), canal_admin (async), heure_paris,
    est_staff, normaliser."""
    _deps.update(deps)


def lien_whatsapp(tel: str, texte: str) -> str:
    """wa.me/<numéro>?text=… : ouvre la conversation avec le message prêt, rien n'est envoyé sans appui."""
    chiffres = "".join(c for c in str(tel or "") if c.isdigit())
    if len(chiffres) < 8:
        return ""
    return f"https://wa.me/{chiffres}?text={quote(texte)}"


def message(prenom: str, cas: str, n: int, jours: int) -> str:
    """Le message WhatsApp, court, en mots simples."""
    if cas == "compte":
        return (f"Salut {prenom} ! Ton compte {n} t'attend dans ton salon Discord. "
                "Tu bloques où ? Réponds-moi ici, je t'aide 🙂")
    if cas == "whatsapp":                                                # 05/10 : compte 1 créé, il n'a pas encore écrit
        return (f"Salut {prenom} ! Ton compte 1 est créé, bravo. C'est ici qu'on se parle : "
                "réponds-moi un mot, j'ouvre ton groupe avec Jonas 🙂")
    return (f"Salut {prenom} ! Pas de Reel depuis {jours} jours sur tes comptes. "
            "Tout va bien ? Dis-moi ce qui bloque, on règle ça ensemble 💪")


def _jours_depuis(iso, maintenant) -> int:
    try:
        d = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return -1
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return (maintenant - d).days


def liste(parcours: dict, groupes: dict, uid_de, tel_de, sans_reel: dict, maintenant=None) -> list:
    """[(jours, prénom, créatrice, où il bloque, lien WhatsApp)], le plus bloqué d'abord, MAX_JOUR au plus."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for creatrice, prenoms in (groupes or {}).items():
        for prenom in prenoms or []:
            uid = uid_de(prenom)
            if not uid:
                continue
            fiche = parcours.get(str(uid)) or {}
            n = int(fiche.get("etape", 0) or 0)
            jours = _jours_depuis((fiche.get("dates") or {}).get(str(n)), maintenant) if n in JOURS_ETAPE else -1
            fait1 = (fiche.get("dates") or {}).get("1_fait")
            if n in JOURS_ETAPE and jours > JOURS_ETAPE[n]:
                ou, texte = f"compte {n} à créer depuis {jours} j", message(prenom, "compte", n, jours)
            elif fait1 and not fiche.get("whatsapp") and _jours_depuis(fait1, maintenant) >= 1:
                # 05/10 (Gaëtan : WhatsApp demandé après le compte 1, pas bloquant) : il n'a pas écrit, Gaëtan le relance d'un appui
                jours = _jours_depuis(fait1, maintenant)
                ou, texte = f"compte 1 créé depuis {jours} j, pas de WhatsApp (`!wa @{prenom}` quand c'est fait)", message(prenom, "whatsapp", 1, jours)
            elif n == 1:
                continue
            else:
                # 01/10 (Antoinr, étape 2 depuis 4 jours sans un Reel, jamais listé) : aux étapes 2 et 3, un clipper sans Reel est
                # signalé même si l'étape est jeune — et c'est ce qui bloque l'ouverture de son compte suivant (règle du 01/10)
                jours = int(sans_reel.get(str(uid), -1))
                if jours < JOURS_SANS_REEL:
                    continue
                ou, texte = f"aucun Reel depuis {jours} j", message(prenom, "reel", n, jours)
            out.append((jours, prenom, creatrice, ou, lien_whatsapp(tel_de(uid), texte)))
    out.sort(key=lambda x: -x[0])
    return out[:MAX_JOUR]


def lignes(bloques: list) -> list:
    if not bloques:
        return ["🚧 Bloqués ce matin : personne 🎉"]
    out = [f"🚧 **Bloqués ce matin ({len(bloques)})** — appuie sur WhatsApp, relis, envoie."]
    for _, prenom, creatrice, ou, lien in bloques:
        out.append(f"· **{prenom}** ({creatrice}) · {ou} · " + (f"[WhatsApp]({lien})" if lien else "pas de numéro"))
    return out


async def envoyer(canal) -> int:
    parcours = _deps["lire_json"](_deps["FICHIER_PARCOURS"], {})
    try:
        sans_reel = await _deps["jours_sans_reel"]()
    except Exception as erreur:                                          # noqa: BLE001 — sans le classeur, les comptes seulement
        journal.warning("Bloqués : jours sans Reel illisibles (%s)", erreur)
        sans_reel = {}

    def uid_de(prenom):
        m = _deps["membre_par_prenom"](_deps["normaliser"](str(prenom).split()[0]))
        return str(m.id) if m is not None else ""
    bloques = liste(parcours, _deps["roster_groupes"](), uid_de, _deps["tel_de"], sans_reel)
    morceau = ""
    for ligne in lignes(bloques):                                       # plusieurs messages si la liste dépasse 2 000 caractères
        if len(morceau) + len(ligne) + 1 > 1900:
            await canal.send(morceau, suppress_embeds=True)
            morceau = ""
        morceau += ("\n" if morceau else "") + ligne
    if morceau:
        await canal.send(morceau, suppress_embeds=True)
    journal.info("Bloqués du matin : %d", len(bloques))
    return len(bloques)


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith(("!bloques", "!bloqués")):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    await envoyer(message.channel)
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Liste des bloqués éteinte (BLOQUES=0)")
        return
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            etat = _deps["lire_json"](_deps["FICHIER"], {})
            if maintenant.hour >= HEURE and etat.get("dernier") != jour:
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await envoyer(canal)
                    etat["dernier"] = jour
                    _deps["ecrire_json"](_deps["FICHIER"], etat)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Boucle des bloqués : %s", erreur)
        await asyncio.sleep(1200)
