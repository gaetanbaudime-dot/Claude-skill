"""Rapport quotidien GAML par manager (demande de Gaëtan, 24/09/2026) : #jonas-stats.

Chaque matin, une fois les relevés de la veille faits (paie_clics), le bot poste dans le salon du manager
les visiteurs GAML de la veille des clippers qu'il suit, groupés par créatrice : visiteurs hors robots,
dont francophones payables, cumul 7 jours. Les clippers sans lien GAML sont signalés.

Configuration : `rapport_jonas.json` à côté du bot :
  {"salon": "jonas-stats", "groupes": {"Sophie": ["Thia", "Rianah"], "Chloé": [...], "Sarah": [...]}}
Un lien GAML est rattaché à un clipper du rapport quand sa note contient le prénom et que son nom commence
par la créatrice (ex. note « Clipping Thia », nom « Sophie 🌸 » ; « Rianah Metricool » compte pour Rianah
sous Sophie). Ces liens sont relevés même sans membre Discord attribué (`suivi` dans clics.json).
"""

import json
import logging
from datetime import timedelta
from pathlib import Path

import discord

import paie_clics

journal = logging.getLogger("rapport")
FICHIER_CONFIG = Path(__file__).parent / "rapport_jonas.json"

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def config() -> dict:
    try:
        c = json.loads(FICHIER_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"salon": "", "groupes": {}}
    c.setdefault("salon", "jonas-stats"); c.setdefault("groupes", {})
    return c


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").lower().strip()


# ------------------------------------------------------------------ liens suivis
def associer_suivi(d: dict, liens: list) -> int:
    """Marque dans clics.json les liens GAML des clippers du rapport (relevés même sans membre Discord).
    Renvoie le nombre de liens nouvellement suivis."""
    nouveaux = 0
    for creatrice, noms in config()["groupes"].items():
        for nom in noms:
            for l in liens:
                lid, note = l.get("id"), _n(l.get("note"))
                cr = _n(str(l.get("name", "")).split()[0] if l.get("name") else "")
                if not lid or _n(nom) not in note or cr != _n(creatrice):
                    continue
                info = d["liens"].setdefault(lid, {"uid": "", "note": l.get("note"), "url": l.get("url"),
                                                   "creatrice": creatrice, "depuis": paie_clics.CLICS_DEPUIS, "par": "rapport"})
                if not info.get("suivi"):
                    nouveaux += 1
                info.update({"suivi": True, "suivi_nom": nom, "suivi_creatrice": creatrice,
                             "note": l.get("note") or info.get("note"), "url": l.get("url") or info.get("url")})
    return nouveaux


def _liens_de(d: dict, creatrice: str, nom: str) -> list:
    return [lid for lid, i in d["liens"].items()
            if i.get("suivi") and _n(i.get("suivi_nom")) == _n(nom) and _n(i.get("suivi_creatrice")) == _n(creatrice)]


# ------------------------------------------------------------------ texte
def texte_rapport(d: dict, jour) -> str:
    c = config()
    lignes = [f"📊 **Visiteurs du {jour.strftime('%d/%m')}**, par clipper"]
    tot = {"hors_robots": 0, "payes": 0, "s7": 0}
    for creatrice, noms in c["groupes"].items():
        lignes.append(f"\n**{creatrice}**")
        for nom in noms:
            lids = _liens_de(d, creatrice, nom)
            if not lids:
                lignes.append(f"· {nom} : pas de lien")
                continue
            h = paie_clics.somme(d, lids, jour, jour)
            s7 = paie_clics.somme(d, lids, jour - timedelta(days=6), jour)
            if h["jours"] == 0:
                lignes.append(f"· {nom} : pas encore compté")
                continue
            tot["hors_robots"] += h["hors_robots"]; tot["payes"] += h["payes"]; tot["s7"] += s7["hors_robots"]
            lignes.append(f"· {nom} : **{paie_clics._fmt(h['hors_robots'])}**")
    # 26/09, demande de Gaëtan : un chiffre par clipper, deux totaux en conclusion, rien d'autre (Jonas s'y perdait)
    lignes.append(f"\nHier, tous les clippeurs réunis : **{paie_clics._fmt(tot['hors_robots'])} visiteurs**")
    lignes.append(f"Les 7 derniers jours, tous les clippeurs réunis : **{paie_clics._fmt(tot['s7'])} visiteurs**")
    return "\n".join(lignes)


# ------------------------------------------------------------------ salon
async def salon(client, creer: bool = True):
    """Le salon du rapport (nom dans la config), créé au besoin : privé, visible du rôle Manager et des admins."""
    nom = config()["salon"]
    if not nom or not client.guilds:
        return None
    guild = client.guilds[0]
    cible = _n(nom).replace(" ", "-")
    for s in guild.text_channels:
        if _n(s.name) == cible:
            return s
    if not creer:
        return None
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
                  guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
    rm = _deps["role_manager"](guild) if _deps.get("role_manager") else None
    if rm is not None:
        overwrites[rm] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    for uid in _deps.get("ADMIN_IDS", ()):
        m = guild.get_member(int(uid)) if str(uid).isdigit() else None
        if m is not None:
            overwrites[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    categorie = None
    canal_admin = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
    if canal_admin is not None and getattr(canal_admin, "category", None) is not None:
        categorie = canal_admin.category
    try:
        s = await guild.create_text_channel(nom, category=categorie, overwrites=overwrites,
                                            topic="Stats GAML de la veille des clippers suivis, chaque matin (bot).",
                                            reason="Rapport quotidien manager (24/09)")
        journal.info("Salon %s créé", nom)
        return s
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Salon %s : %s", nom, erreur)
        return None


async def envoyer(client, d: dict, jour) -> bool:
    s = await salon(client)
    if s is None:
        return False
    try:
        await s.send(texte_rapport(d, jour)[:1990])
        return True
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Envoi rapport : %s", erreur)
        return False


async def demarrer(client):
    """Au démarrage : le salon existe (créé sinon), avec un mot d'accueil s'il vient d'être créé."""
    await client.wait_until_ready()
    if not config()["groupes"]:
        return
    existait = await salon(client, creer=False)
    s = await salon(client)
    journal.info("Salon du rapport : %s", "créé" if (s is not None and existait is None) else ("présent" if s else "impossible"))
    if s is not None and existait is None:
        try:
            await s.send("📊 Salon créé par le bot. Chaque matin après 7 h : les stats GAML de la veille des clippers suivis, "
                         "par créatrice. `!stats-jonas` pour un rapport tout de suite, `!stats-jonas 2026-09-22` pour un autre jour.")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def apres_releves(client, d: dict):
    """Appelé par la boucle des clics après chaque passage : poste le rapport de la veille une fois par jour,
    dès que tous les liens suivis ont leur relevé d'hier. La liste des liens suivis est rafraîchie par
    paie_clics (associer_suivi) à chaque tour d'association."""
    if not config()["groupes"]:
        return
    maintenant = _deps["heure_paris"]()
    hier = maintenant.date() - timedelta(days=1)
    if maintenant.hour < paie_clics.CLICS_HEURE or d.get("rapport_jonas") == maintenant.date().isoformat():
        return
    suivis = [lid for lid, i in d["liens"].items() if i.get("suivi")]
    complets = all(hier.isoformat() in d["jours"].get(lid, {}) for lid in suivis)
    if suivis and not complets and maintenant.hour < paie_clics.CLICS_HEURE + 3:
        return                                     # on attend les relevés, mais jamais au-delà de 3 h
    if await envoyer(client, d, hier):
        d["rapport_jonas"] = maintenant.date().isoformat()
        paie_clics._ecrire(d)
        journal.info("Rapport manager du %s posté (%s liens suivis, relevés %s)", hier, len(suivis), "complets" if complets else "partiels")


async def commande_staff(message, texte: str) -> bool:
    """`!stats-jonas [AAAA-MM-JJ]` : poster le rapport (hier par défaut) dans le salon."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!stats-jonas", "!stats-manager"):
        return False
    if not paie_clics.actif():
        await message.reply("Paie au clic inactive (clé GAML absente) : pas de relevés.")
        return True
    from datetime import date
    jour = _deps["heure_paris"]().date() - timedelta(days=1)
    for m in mots[1:]:
        try:
            jour = date.fromisoformat(m)
        except ValueError:
            pass
    d = paie_clics._lire()
    try:
        n = associer_suivi(d, await paie_clics.liens_gaml())
        if n:
            paie_clics._ecrire(d)
    except RuntimeError as erreur:
        await message.reply(f"❌ GAML : {erreur}")
        return True
    s = await salon(message.client if hasattr(message, "client") else _deps["client"])
    texte_r = texte_rapport(d, jour)
    if s is not None and s.id != message.channel.id:
        await s.send(texte_r[:1990])
        await message.reply(f"✅ Rapport du {jour.strftime('%d/%m')} posté dans <#{s.id}>.")
    else:
        await message.reply(texte_r[:1990])
    return True
