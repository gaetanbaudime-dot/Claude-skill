"""Rapport quotidien GAML par manager (demande de Gaëtan, 24/09/2026) : #jonas-stats.

Chaque matin, une fois les relevés de la veille faits (paie_clics), le bot poste dans le salon du manager
les visiteurs GAML de la veille des clippers qu'il suit, groupés par créatrice : visiteurs hors robots,
dont francophones payables, cumul 7 jours. Les clippers sans lien GAML sont signalés.

Configuration : `rapport_jonas.json` à côté du bot :
  {"salon": "jonas-stats", "mis_a_jour": "<ISO UTC>", "groupes": {"Sophie": ["Thia", "Rianah"], "Chloé": [...], "Sarah": [...]}}
26/09 (liste de Gaëtan) : `groupes` est LE roster actif par créatrice, daté par `mis_a_jour`. Le roster vivant
(`groupes_actifs`) y ajoute les fiches du registre qui ont reçu une créatrice après cette date et en retire les
`!sortie` faites après cette date ; il sert au rapport ET au salon-compteur « 🎬 Clippers : N » (plus de comptage
par rôle Discord, cassé à chaque renommage de rôle).
Un lien GAML est rattaché à un clipper du rapport quand sa note contient le prénom et que son nom commence
par la créatrice (ex. note « Clipping Thia », nom « Sophie 🌸 » ; « Rianah Metricool » compte pour Rianah
sous Sophie). Ces liens sont relevés même sans membre Discord attribué (`suivi` dans clics.json).
"""

import json
import re
import os
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
    c.setdefault("salon", "jonas-stats"); c.setdefault("groupes", {}); c.setdefault("mis_a_jour", "")
    if _deps.get("roster"):                                             # 26/09 : le roster de Gaëtan remplace les groupes du fichier
        try:
            g = _deps["roster"]()
            if g:
                c["groupes"] = g
        except Exception:                                               # noqa: BLE001
            pass
    return c


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").lower().strip()


# ------------------------------------------------------------------ roster actif (26/09)
def _prenom(nom: str) -> str:
    """« Meiji - Chloé » → « Meiji » (convention des pseudos et des fiches de sortie)."""
    mots = str(nom or "").split()
    return mots[0] if mots else ""


def fusionner_actifs(groupes: dict, mis_a_jour: str, registre: dict, sortis: list, nom_par_uid, exclus=()) -> dict:
    """Le roster vivant, fonction pure (testée hors ligne) : la liste datée de Gaëtan + les fiches du registre
    qui ont reçu une créatrice APRÈS cette date − les sorties (!sortie) faites APRÈS cette date. Les dates sont
    des ISO UTC comparables comme des chaînes. `nom_par_uid(uid)` renvoie le prénom d'un membre ou None."""
    ref = str(mis_a_jour or "")
    exclus = {str(x) for x in (exclus or ())}
    actifs = {c: list(noms) for c, noms in (groupes or {}).items()}
    for uid, fiche in (registre or {}).items():
        cr = str(fiche.get("creatrice") or "").strip()
        if not cr or str(uid) in exclus or str(fiche.get("creatrice_date") or "") <= ref:
            continue
        nom = _prenom(nom_par_uid(uid) or "")
        if not nom:
            continue
        cle = next((c for c in actifs if _n(c) == _n(cr)), cr)
        liste = actifs.setdefault(cle, [])
        if _n(nom) not in {_n(x) for x in liste}:
            liste.append(nom)
    partis = {_n(_prenom(s.get("nom"))) for s in (sortis or [])
              if s.get("nom") and str(s.get("date") or "") > ref}
    if partis:
        actifs = {c: [n for n in noms if _n(n) not in partis] for c, noms in actifs.items()}
    return actifs


def groupes_actifs() -> dict:
    """Le roster vivant quand le bot est branché (registre + sorties), sinon la liste du fichier telle quelle."""
    c = config()
    if _deps.get("roster"):                                             # 26/09 : roster.py (roster.json + !roster) est la source unique
        return c["groupes"]
    if not (_deps.get("lire_json") and _deps.get("nom_par_uid")):
        return c["groupes"]
    return fusionner_actifs(c["groupes"], c.get("mis_a_jour", ""),
                            _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}),
                            _deps["lire_json"](_deps["FICHIER_SORTIS"], []),
                            _deps["nom_par_uid"], _deps.get("ADMIN_IDS", ()))


def total_actifs(groupes: dict = None) -> int:
    """Le chiffre du salon-compteur : prénoms distincts, toutes créatrices confondues."""
    g = groupes if groupes is not None else groupes_actifs()
    return len({_n(n) for noms in g.values() for n in noms})


def texte_actifs() -> str:
    g = groupes_actifs()
    date = str(config().get("mis_a_jour") or "")[:10] or "?"
    lignes = [f"👥 **Clippers actifs : {total_actifs(g)}** (liste du {date} + arrivées `!creatrice` − sorties `!sortie`)"]
    for cr, noms in g.items():
        lignes.append(f"**{cr}** ({len(noms)}) : {', '.join(noms) if noms else '—'}")
    return "\n".join(lignes)


# ------------------------------------------------------------------ liens suivis
def _mots(t: str) -> list:
    """Les mots d'un texte, sans accents ni casse ni ponctuation (« Clipping Anaïs » → ["clipping", "anais"])."""
    return re.findall(r"[a-z0-9]+", paie_clics._n_note(t))


def associer_suivi(d: dict, liens: list) -> int:
    """Marque dans clics.json les liens GAML des clippers du rapport (relevés même sans membre Discord).
    Renvoie le nombre de liens nouvellement suivis. 09/10 (dashboard) : le prénom est cherché comme MOT ENTIER de la note (tous
    ses mots, dans l'ordre de la note ou non) : « Ana » ne prend plus « Clipping Anaïs », « Rianah » prend toujours « Rianah
    Metricool ». Un suivi déjà posé dont la note GAML actuelle ne contient plus le prénom suivi en mot entier (posé par l'ancienne
    règle, « Ana » sur « Clipping Anaïs ») est retiré, puis rattaché au bon prénom s'il y en a un ; le lien reste relevé
    (paie_clics.marquer_releves). Renvoie le nombre de liens nouvellement suivis ou retirés (l'appelant écrit si > 0)."""
    nouveaux = 0
    notes = {l.get("id"): str(l.get("note") or "") for l in liens if l.get("id") and "note" in l}
    for lid, info in d.get("liens", {}).items():
        if not info.get("suivi") or lid not in notes:
            continue
        mots_note = set(_mots(re.sub(r"\(\s*ex[^)]*\)", " ", notes[lid], flags=re.I)))
        if set(_mots(info.get("suivi_nom"))) and set(_mots(info.get("suivi_nom"))) <= mots_note:
            continue
        for cle in ("suivi", "suivi_nom", "suivi_creatrice"):
            info.pop(cle, None)
        nouveaux += 1
    for creatrice, noms in groupes_actifs().items():
        for nom in noms:
            mots_nom = set(_mots(nom))
            for l in liens:
                # 09/10 (revue) : « (ex-Julien) » dit l'ancien propriétaire, jamais le clipper suivi ; un lien « Clipping libre » n'est à personne
                lid, note = l.get("id"), _n(re.sub(r"\(\s*ex[^)]*\)", " ", str(l.get("note") or ""), flags=re.I))
                cr = _n(str(l.get("name", "")).split()[0] if l.get("name") else "")
                if (not lid or not mots_nom or not mots_nom <= set(_mots(note)) or cr != _n(creatrice)
                        or note.strip().startswith("clipping libre")):
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
def texte_rapport(d: dict, jour, seulement=None, titre: str = "par clipper") -> str:
    """Le rapport d'un jour. `seulement` : prénoms à garder (28/09 : Jonas ne voit que ses anciens, l'admin voit tout)."""
    garder = {_n(x) for x in seulement} if seulement is not None else None
    lignes = [f"📊 **Visiteurs du {jour.strftime('%d/%m')}**, {titre}"]
    tot = {"hors_robots": 0, "payes": 0, "s7": 0}
    for creatrice, noms in groupes_actifs().items():
        noms = [n for n in noms if garder is None or _n(n) in garder]
        if not noms:
            continue
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


CLIPPERS_JONAS = [n.strip() for n in os.environ.get(
    "CLIPPERS_JONAS", "Thia, Rianah, Lilian, Romaric, Lucas, Caroline, Ckycia, Hasina, Josué, Tara, Clarisse, Yves").split(",") if n.strip()]


def clippers_de_jonas() -> list:
    """28/09 (Gaëtan : « garde ceux que je t'ai dits, pas plus ») : la liste est en dur (CLIPPERS_JONAS), jamais lue dans le roster —
    la liste `sans_salon` du roster vivant était vide et le rapport retombait sur tout le monde."""
    return list(CLIPPERS_JONAS)


async def envoyer(client, d: dict, jour) -> bool:
    """Le rapport du jour : tous les clippers dans le salon admin, seulement ceux de Jonas dans son salon (28/09)."""
    ok = False
    anciens = clippers_de_jonas()
    s = await salon(client)
    if s is not None:
        try:
            await s.send(texte_rapport(d, jour, seulement=anciens, titre="tes clippers")[:1990])
            ok = True
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Envoi rapport Jonas : %s", erreur)
    admin = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
    if admin is not None and admin is not s:
        try:
            await admin.send(texte_rapport(d, jour, titre="tous les clippers de l'agence")[:1990])
            ok = True
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Envoi rapport admin : %s", erreur)
    return ok


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
    aujourdhui = maintenant.date().isoformat()
    if maintenant.hour < paie_clics.CLICS_HEURE or d.get("rapport_jonas") == aujourdhui:
        return
    # revue CLICS du 09/10 : la veille n'est attendue que des suivis relevés aujourd'hui (paie_clics.a_relever : pas un lien introuvable
    # aujourd'hui, 404, ni effacé dans GAML) et comptés à partir d'hier au plus tard — comme `complets` dans paie_clics. Avant, un
    # suivi introuvable (plus jamais écrit à 0) retardait le rapport de 7 h à 10 h chaque jour.
    suivis = [lid for lid, i in d["liens"].items() if i.get("suivi") and paie_clics.a_relever(i, aujourdhui)
              and str(i.get("depuis") or "")[:10] <= hier.isoformat()]
    complets = all(not paie_clics._manque(d["jours"].get(lid, {}), hier) for lid in suivis)
    if suivis and not complets and maintenant.hour < paie_clics.CLICS_HEURE + 3:
        return                                     # on attend les relevés, mais jamais au-delà de 3 h
    if await envoyer(client, d, hier):
        d["rapport_jonas"] = maintenant.date().isoformat()
        paie_clics._ecrire(d)
        journal.info("Rapport manager du %s posté (%s liens suivis, relevés %s)", hier, len(suivis), "complets" if complets else "partiels")


async def commande_staff(message, texte: str) -> bool:
    """`!stats-jonas [AAAA-MM-JJ]` : poster le rapport (hier par défaut) dans le salon. `!actifs` : le roster compté."""
    mots = texte.split()
    if mots and mots[0].lower() in ("!actifs", "!equipe-active"):      # 26/09 : le roster que compte le salon « Clippers »
        await message.reply(texte_actifs()[:1990])
        return True
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
    anciens = clippers_de_jonas()                                       # 28/09 : Jonas ne voit que ses anciens, l'admin voit tout
    texte_j = texte_rapport(d, jour, seulement=anciens, titre="tes clippers")
    texte_a = texte_rapport(d, jour, titre="tous les clippers de l'agence")
    if s is not None and s.id == message.channel.id:                   # tapé dans #jonas-stats : sa version, rien d'autre
        await message.channel.send(texte_j[:1990])
        return True
    if s is not None:
        try:
            await s.send(texte_j[:1990])
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Rapport Jonas : %s", erreur)
    await message.channel.send(texte_a[:1990])                          # ici (salon admin) : tout le monde
    return True
