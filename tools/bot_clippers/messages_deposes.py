"""Messages déposés (27/09) : un message écrit dans le dépôt (`messages_a_envoyer.json`, à côté de ce fichier) est posté
UNE fois par le bot à son démarrage — dans le salon perso d'un clipper (« pour » : son prénom), dans un salon nommé
(« salon » : « #nom ») ou, par défaut, dans le salon admin.

POURQUOI : depuis une session Claude Code on ne parle pas à Discord (le jeton du bot ne vit que dans Railway), mais le
dépôt, lui, se déploie. Gaëtan dit « envoie ça à Daniella dans son salon » : le message part avec le déploiement suivant.
Trace des envois dans DONNEES/messages_envoyes.json (id → date, salon) : jamais deux fois, même après dix redéploiements.
Un salon introuvable est signalé dans le salon admin et le message est retenté au démarrage suivant.

Format d'une entrée : {"id": "daniella-recup-2709", "pour": "Daniella", "texte": "…", "bouton_whatsapp": true}
                   ou {"id": "…", "salon": "#annonces", "texte": "…"}.
Options (28/09) : "effacer_bot": true efface d'abord les messages du bot dans ce salon (jusqu'à 20) ; "accueil_liaison": true
remplace le texte par le message d'arrivée du membre (parcours, formation, lien du quiz), calculé au moment de l'envoi ;
"creer_salon": true crée le salon perso du membre « pour » s'il n'en a pas ; "tous_arrivants": true applique l'entrée à chaque
salon de la catégorie Clippers dont le membre n'est ni staff ni signé avec une créatrice (« efface et renvoie ça à tous ceux
qu'on a onboardés cette nuit », 28/09).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import discord

journal = __import__("logging").getLogger("bot_clippers")

FICHIER_REPO = Path(__file__).with_name("messages_a_envoyer.json")
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (DONNEES/messages_envoyes.json), chercher_membre, salon_perso, canal_admin,
    vue_whatsapp, prenom_de."""
    _deps.update(deps)


def lire_deposes() -> list:
    try:
        if not FICHIER_REPO.exists():
            return []
        contenu = json.loads(FICHIER_REPO.read_text(encoding="utf-8"))
        return [m for m in (contenu if isinstance(contenu, list) else contenu.get("messages", []))
                if isinstance(m, dict) and m.get("id") and (m.get("texte") or m.get("accueil_liaison") or m.get("creer_salon"))]
    except (json.JSONDecodeError, OSError) as erreur:
        journal.warning("messages_a_envoyer.json illisible : %s", erreur)
        return []


def _salon_par_nom(client, nom: str):
    cible = nom.lstrip("#").strip().lower()
    for g in client.guilds:
        for s in getattr(g, "text_channels", []):
            if s.name.lower() == cible:
                return s
    return None


def _membre_du_salon(client, salon):
    """Le membre humain non staff d'un salon perso (celui qui a une permission nominative), ou None."""
    for cible in getattr(salon, "overwrites", {}) or {}:
        if isinstance(cible, discord.Member) and not cible.bot and not (_deps.get("est_staff") and _deps["est_staff"](cible)):
            return cible
    return None


def salons_arrivants(client) -> list:
    """[(salon, membre)] de la catégorie Clippers : membres ni staff ni signés avec une créatrice."""
    nom = str(_deps.get("categorie_nom") or "").strip().lower()
    out = []
    for g in client.guilds:
        for s in getattr(g, "text_channels", []):
            if not s.category or s.category.name.strip().lower() != nom:
                continue
            m = _membre_du_salon(client, s)
            if m is None or (_deps.get("signe_creatrice") and _deps["signe_creatrice"](m.id)):
                continue
            out.append((s, m))
    return out


async def _envoyer_dans(client, salon, membre, entree: dict, ident: str) -> bool:
    """Efface (option), calcule le texte (option), envoie. Vrai si un message est parti."""
    vue = _deps["vue_whatsapp"]() if entree.get("bouton_whatsapp") and _deps.get("vue_whatsapp") else None
    texte = str(entree.get("texte") or "")
    if entree.get("accueil_liaison") and membre is not None and _deps.get("accueil_liaison"):
        texte = _deps["accueil_liaison"](membre)
    if entree.get("effacer_bot"):                                        # 28/09 : on remplace les messages du bot dans ce salon
        try:
            async for ancien in salon.history(limit=20):
                if ancien.author == client.user:
                    await ancien.delete()
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Message déposé « %s » : effacement impossible dans #%s (%s)", ident, getattr(salon, "name", "?"), erreur)
    if not texte:
        return False
    try:
        await salon.send(texte[:1900], view=vue)
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Message déposé « %s » refusé par Discord dans #%s : %s", ident, getattr(salon, "name", "?"), erreur)
        return False
    return True


async def resoudre(client, entree: dict):
    """Le salon visé par une entrée, ou (None, raison)."""
    if entree.get("pour"):
        membre = _deps["chercher_membre"](str(entree["pour"]), exact=True)
        if membre is None:
            return None, f"membre « {entree['pour']} » introuvable sur le serveur"
        salon = _deps["salon_perso"](membre.id)
        if salon is None and entree.get("creer_salon") and _deps.get("assurer_salon_arrivee"):
            salon = await _deps["assurer_salon_arrivee"](membre, accueil=False)
        if salon is None:
            return None, f"pas de salon perso ouvert pour {entree['pour']}"
        return salon, ""
    if entree.get("salon"):
        salon = _salon_par_nom(client, str(entree["salon"]))
        return (salon, "") if salon is not None else (None, f"salon « {entree['salon']} » introuvable")
    return None, "admin"


async def envoyer_au_demarrage(client) -> list:
    """Poste chaque message déposé pas encore envoyé. Renvoie les identifiants envoyés."""
    deposes = lire_deposes()
    if not deposes:
        return []
    await client.wait_until_ready()
    envoyes = _deps["lire_json"](_deps["FICHIER"], {})
    faits = []
    for entree in deposes:
        ident = str(entree["id"])
        if ident in envoyes:
            continue
        admin = await _deps["canal_admin"]()
        if entree.get("tous_arrivants"):                                     # 28/09 : un envoi par salon de la catégorie Clippers
            faits_ici = []
            for salon_a, membre_a in salons_arrivants(client):
                if await _envoyer_dans(client, salon_a, membre_a, entree, ident):
                    faits_ici.append(getattr(salon_a, "name", "?"))
            envoyes[ident] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "salons": faits_ici}
            _deps["ecrire_json"](_deps["FICHIER"], envoyes)
            faits.append(ident)
            journal.info("Message déposé « %s » envoyé dans %d salon(s) : %s", ident, len(faits_ici), ", ".join(faits_ici))
            if admin is not None:
                try:
                    await admin.send(f"📨 Message déposé « {ident} » envoyé dans {len(faits_ici)} salon(s) : {', '.join('#' + n for n in faits_ici) or 'aucun'}.")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            continue
        salon, raison = await resoudre(client, entree)
        if salon is None and raison == "admin":
            salon = admin
        if salon is None:
            journal.warning("Message déposé « %s » non envoyé : %s", ident, raison)
            if admin is not None:
                try:
                    await admin.send(f"📨 Message déposé « {ident} » non envoyé : {raison}. Je réessaie au prochain démarrage.")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            continue
        membre = _deps["chercher_membre"](str(entree["pour"]), exact=True) if entree.get("pour") else None
        if not await _envoyer_dans(client, salon, membre, entree, ident):
            continue
        envoyes[ident] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "salon": getattr(salon, "name", str(salon.id))}
        _deps["ecrire_json"](_deps["FICHIER"], envoyes)
        faits.append(ident)
        journal.info("Message déposé « %s » envoyé dans #%s", ident, getattr(salon, "name", salon.id))
        if admin is not None and admin is not salon:
            try:
                await admin.send(f"📨 Message déposé « {ident} » envoyé dans {getattr(salon, 'mention', '#' + getattr(salon, 'name', '?'))}.")
            except (discord.Forbidden, discord.HTTPException):
                pass
    return faits
