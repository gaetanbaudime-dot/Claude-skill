"""États des comptes du classeur (26/09, demande de Gaëtan : « mettre à jour constamment l'état des comptes sur le sheet »).

Chaque jour, le bot regarde Instagram (Apify) pour les comptes du classeur qui ont un Gérant, et met à jour la colonne
ETAT de l'onglet Instagram, une cellule à la fois, jamais la structure :
  à créer → WARMUP   dès que le compte existe sur Instagram
  WARMUP  → GOOD     quand il a publié GOOD_JOURS jours de suite (au moins une publication par jour)
  WARMUP  → PRIVE    quand le compte est passé en privé (le 3e compte du trio)
  WARMUP / GOOD / PRIVE → BAN   quand Instagram ne le trouve plus BAN_JOURS jours de suite (posé par le bot, annulé s'il revient)
  BAN posé par le bot → WARMUP  si le compte réapparaît
Les états posés à la main (PERDU LOGS, à vérifier, BIZARRE, ACTIF…) et les lignes sans Gérant ne sont jamais touchés :
un compte du vivier libre ne peut pas se créer tout seul. La colonne Followers est remplie pour TOUS les comptes créés du
classeur (26/09, « légendaire ») : clippers, créatrices sous Metricool, comptes libérés — pas les lignes « à créer » sans gérant.
Le module ne connaît pas bot_discord : dépendances dans `configurer(deps)` (lire_json, ecrire_json, FICHIER_ETATS,
normaliser, canal_admin, notifier, est_staff ; `scanner` optionnel pour les tests)."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp

import google_api
import onboarding

journal = logging.getLogger("etats_comptes")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR_IG = os.environ.get("APIFY_ACTOR_IG", "apify~instagram-profile-scraper").strip()
ACTIF = (os.environ.get("ETATS_CLASSEUR", "1").strip() or "1") != "0"
GOOD_JOURS = int(os.environ.get("ETATS_GOOD_JOURS", "3") or 3)         # jours de publication de suite pour GOOD
BAN_JOURS = int(os.environ.get("ETATS_BAN_JOURS", "2") or 2)           # jours d'absence de suite pour BAN
HEURE_UTC = int(os.environ.get("ETATS_HEURE_UTC", "7") or 7)           # après le rapport inputs du matin
JOURS_HISTORIQUE = 14
SUIVIS = ("a creer", "à créer", "warmup", "good", "prive", "privé", "ban")
VERSION = 2                                                            # changer = un passage de plus le jour du déploiement
LOT = 50                                                               # comptes par appel Apify

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    return ACTIF and bool(APIFY_TOKEN) and onboarding.actif()


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_ETATS"], {})
    d.setdefault("historique", {}); d.setdefault("bans_auto", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_ETATS"], d)


# ------------------------------------------------------------------ Instagram
async def scanner(handles: list) -> dict:
    """Un appel Apify pour tous les comptes → {handle: {existe, prive, restreint, followers, posts}} ; `posts` =
    publications des dernières 24 h. Un compte absent de la réponse, ou renvoyé avec une erreur, n'existe pas
    (banni, renommé, jamais créé). None si Apify est en panne : on ne conclut rien ce jour-là."""
    if _deps.get("scanner"):
        return await _deps["scanner"](handles)
    if not APIFY_TOKEN or not handles:
        return None
    url = f"https://api.apify.com/v2/acts/{ACTOR_IG}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    items = []
    for i in range(0, len(handles), LOT):                              # par lots : 130 comptes tiennent en deux ou trois appels
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=280)) as session:
                async with session.post(url, json={"usernames": handles[i:i + LOT]}) as reponse:
                    if reponse.status >= 400:
                        journal.error("Apify HTTP %s (états du classeur)", reponse.status)
                        return None
                    lot = await reponse.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
            journal.error("Apify injoignable (états du classeur) : %s", erreur)
            return None
        items += lot if isinstance(lot, list) else []
    limite = datetime.now(timezone.utc) - timedelta(hours=24)
    out = {h.lower(): {"existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0} for h in handles}
    for item in items:
        handle = (item.get("username") or item.get("inputUrl") or "").lower().rstrip("/").split("/")[-1].lstrip("@")
        if handle not in out:
            continue
        erreur = str(item.get("error") or "").lower()
        if erreur and "restricted" not in erreur and not item.get("isRestrictedProfile"):
            continue                                                    # not found, invalid… → n'existe pas
        fiche = out[handle]
        fiche["existe"] = True
        fiche["restreint"] = bool(item.get("isRestrictedProfile") or "restricted" in erreur)
        fiche["prive"] = bool(item.get("private"))
        fiche["followers"] = int(item.get("followersCount") or 0)
        for post in item.get("latestPosts") or []:
            try:
                quand = datetime.fromisoformat(str(post.get("timestamp") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if quand >= limite:
                fiche["posts"] += 1
    return out


# ------------------------------------------------------------------ règles
def _series(historique: list) -> tuple:
    """(jours d'absence de suite, jours de publication de suite) en partant du dernier jour."""
    absents = publie = 0
    for j in reversed(historique):
        if j.get("existe"):
            break
        absents += 1
    for j in reversed(historique):
        if not (j.get("existe") and j.get("posts", 0) >= 1):
            break
        publie += 1
    return absents, publie


def decider(etat: str, mesure: dict, historique: list, ban_auto: bool) -> str:
    """Le nouvel état d'une ligne, ou '' si rien ne change. `historique` inclut la mesure du jour."""
    e = _norm(etat)
    absents, publie = _series(historique)
    if e in ("a creer", "à créer"):
        return "WARMUP" if mesure["existe"] else ""
    if e == "warmup":
        if absents >= BAN_JOURS:
            return "BAN"
        if mesure["existe"] and mesure["prive"]:
            return "PRIVE"
        if publie >= GOOD_JOURS:
            return "GOOD"
        return ""
    if e in ("good", "prive", "privé"):
        return "BAN" if absents >= BAN_JOURS else ""
    if e == "ban" and ban_auto:
        return "WARMUP" if mesure["existe"] and not mesure["restreint"] else ""
    return ""


def candidats(comptes: list) -> list:
    """Les lignes dont l'ETAT peut bouger : Utilisation = Clipper, un Gérant, un identifiant, un état que le bot sait faire évoluer."""
    return [c for c in comptes if _norm(c["utilisation"]) == "clipper" and c["handle"]
            and _norm(c["gerant"]) not in ("", "x", "y", "z") and _norm(c["etat"]) in SUIVIS]


def a_scanner(comptes: list) -> list:
    """Les lignes regardées sur Instagram : tout compte créé (état autre que « à créer »), plus les « à créer » qui ont
    un Gérant. Le vivier « à créer » sans gérant n'existe pas encore sur Instagram, inutile de payer pour lui."""
    vus, out = set(), []
    for c in comptes:
        h = c["handle"].lower()
        if not h or h in vus:
            continue
        if _norm(c["etat"]) not in ("a creer", "à créer") or _norm(c["gerant"]) not in ("", "x", "y", "z"):
            vus.add(h)
            out.append(c)
    return out


# ------------------------------------------------------------------ cycle
async def executer(ecrire: bool = True) -> dict:
    """Un passage : lecture du classeur, scan Instagram, décisions, écriture des cellules. Renvoie le bilan
    {"changements": [(handle, gerant, avant, apres)], "scannes": n, "erreur": str}."""
    if not onboarding.actif():
        return {"changements": [], "scannes": 0, "erreur": "classeur non configuré"}
    comptes = await onboarding.lire_comptes()
    suivis = candidats(comptes)
    lignes = a_scanner(comptes)
    if not lignes:
        return {"changements": [], "scannes": 0, "erreur": ""}
    mesures = await scanner([c["handle"].lower() for c in lignes])
    if mesures is None:
        return {"changements": [], "scannes": 0, "erreur": "Instagram illisible aujourd'hui (Apify), rien changé"}
    d = _lire()
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changements, followers_maj = [], 0
    ids_suivis = {id(c) for c in suivis}
    for c in lignes:
        h = c["handle"].lower()
        m = mesures.get(h) or {"existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0}
        if ecrire and m["existe"] and not m["restreint"] and str(m["followers"]) != str(c.get("followers", "")).replace(" ", ""):
            try:
                await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, f"{onboarding.ONGLET_LOGINS}!D{c['ligne']}", [[m["followers"]]])
                followers_maj += 1
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Classeur : followers de %s non écrits : %s", c["handle"], erreur)
        if id(c) not in ids_suivis:
            continue
        hist = [x for x in d["historique"].get(h, []) if x.get("jour") != jour]
        hist.append({"jour": jour, "existe": m["existe"], "posts": m["posts"], "prive": m["prive"]})
        d["historique"][h] = hist[-JOURS_HISTORIQUE:]
        apres = decider(c["etat"], m, d["historique"][h], h in d["bans_auto"])
        if apres:
            changements.append((c["handle"], c["gerant"], c["etat"], apres, c["ligne"]))
            if ecrire:
                try:
                    await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, f"{onboarding.ONGLET_LOGINS}!A{c['ligne']}", [[apres]])
                except Exception as erreur:                              # noqa: BLE001
                    journal.warning("Classeur : état de %s non écrit : %s", c["handle"], erreur)
                    continue
                if apres == "BAN":
                    d["bans_auto"][h] = jour
                elif h in d["bans_auto"]:
                    d["bans_auto"].pop(h, None)
    if ecrire:
        d["dernier"] = jour
        d["version"] = VERSION
        _ecrire(d)
    journal.info("États du classeur : %d compte(s) scanné(s), %d changement(s), %d followers mis à jour", len(lignes), len(changements), followers_maj)
    return {"changements": changements, "scannes": len(lignes), "erreur": "", "followers": followers_maj}


def texte_bilan(bilan: dict, test: bool = False) -> str:
    if bilan.get("erreur"):
        return f"⚠️ États du classeur : {bilan['erreur']}."
    ch = bilan["changements"]
    entete = (f"🗂️ **États du classeur** · {bilan['scannes']} compte(s) regardés sur Instagram · "
              f"{bilan.get('followers', 0)} compteur(s) de followers mis à jour")
    if not ch:
        return entete + " · aucun état à changer."
    par_etat = {}
    for handle, gerant, avant, apres, ligne in ch:
        par_etat.setdefault(apres, []).append(f"`{handle}` ({gerant}, était {avant})")
    lignes = [entete + (" · **test, rien n'est écrit**" if test else "")]
    for apres in ("WARMUP", "GOOD", "PRIVE", "BAN"):
        if apres in par_etat:
            lignes.append(f"→ **{apres}** : " + ", ".join(par_etat[apres]))
    if "BAN" in par_etat:
        lignes.append("-# BAN = introuvable sur Instagram 2 jours de suite. Le compte est à remplacer : `!liberer Prénom handle` puis un nouvel identifiant.")
    return "\n".join(lignes)


async def boucle(client) -> None:
    """Un passage par jour, à HEURE_UTC, après le rapport inputs. Trois tentatives espacées de 15 minutes."""
    if not actif():
        journal.info("États du classeur désactivés (APIFY_TOKEN / classeur absents ou ETATS_CLASSEUR=0)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = datetime.now(timezone.utc)
            jour = maintenant.strftime("%Y-%m-%d")
            d = _lire()
            if maintenant.hour >= HEURE_UTC and (d.get("dernier") != jour or d.get("version") != VERSION) \
                    and int(d.get("essais", {}).get(jour, 0)) < 3:
                bilan = await executer(ecrire=True)
                if bilan.get("erreur"):
                    d = _lire(); d.setdefault("essais", {})[jour] = int(d.get("essais", {}).get(jour, 0)) + 1; _ecrire(d)
                    journal.warning("États du classeur : %s", bilan["erreur"])
                else:
                    if (bilan["changements"] or bilan.get("followers")) and _deps.get("canal_admin"):
                        canal = await _deps["canal_admin"]()
                        if canal is not None:
                            await canal.send(texte_bilan(bilan)[:1990])
                    bans = [f"`{h}` ({g})" for h, g, _, a, _ in bilan["changements"] if a == "BAN"]
                    if bans and _deps.get("notifier"):
                        await _deps["notifier"]("🚫 **Comptes introuvables sur Instagram 2 jours de suite, passés en BAN** : "
                                                + ", ".join(bans) + ". À remplacer : `!liberer Prénom handle`, puis un nouvel identifiant.")
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.exception("Boucle états du classeur : %s", erreur)
        await asyncio.sleep(900)


async def commande_staff(message, texte: str) -> bool:
    """`!etats-comptes` : passage immédiat · `!etats-comptes test` : ce qui changerait, sans rien écrire."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!etats-comptes", "!états-comptes"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if not actif():
        await message.reply("États du classeur inactifs : il faut `APIFY_TOKEN`, `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
        return True
    test = len(mots) > 1 and mots[1].lower() == "test"
    await message.reply("⏳ Je regarde Instagram…")
    bilan = await executer(ecrire=not test)
    await message.reply(texte_bilan(bilan, test)[:1990])
    return True
