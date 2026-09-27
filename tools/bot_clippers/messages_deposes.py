"""Messages déposés (27/09) : un message écrit dans le dépôt (`messages_a_envoyer.json`, à côté de ce fichier) est posté
UNE fois par le bot à son démarrage — dans le salon perso d'un clipper (« pour » : son prénom), dans un salon nommé
(« salon » : « #nom ») ou, par défaut, dans le salon admin.

POURQUOI : depuis une session Claude Code on ne parle pas à Discord (le jeton du bot ne vit que dans Railway), mais le
dépôt, lui, se déploie. Gaëtan dit « envoie ça à Daniella dans son salon » : le message part avec le déploiement suivant.
Trace des envois dans DONNEES/messages_envoyes.json (id → date, salon) : jamais deux fois, même après dix redéploiements.
Un salon introuvable est signalé dans le salon admin et le message est retenté au démarrage suivant.

Format d'une entrée : {"id": "daniella-recup-2709", "pour": "Daniella", "texte": "…", "bouton_whatsapp": true}
                   ou {"id": "…", "salon": "#annonces", "texte": "…"}.
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
                if isinstance(m, dict) and m.get("id") and m.get("texte")]
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


def resoudre(client, entree: dict):
    """Le salon visé par une entrée, ou (None, raison)."""
    if entree.get("pour"):
        membre = _deps["chercher_membre"](str(entree["pour"]), exact=True)
        if membre is None:
            return None, f"membre « {entree['pour']} » introuvable sur le serveur"
        salon = _deps["salon_perso"](membre.id)
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
        salon, raison = resoudre(client, entree)
        admin = await _deps["canal_admin"]()
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
        vue = _deps["vue_whatsapp"]() if entree.get("bouton_whatsapp") and _deps.get("vue_whatsapp") else None
        try:
            await salon.send(str(entree["texte"])[:1900], view=vue)
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Message déposé « %s » refusé par Discord : %s", ident, erreur)
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
