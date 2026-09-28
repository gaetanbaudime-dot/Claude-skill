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
import re
from datetime import date, datetime, timedelta, timezone

import aiohttp

import google_api
import onboarding

journal = logging.getLogger("etats_comptes")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR_IG = os.environ.get("APIFY_ACTOR_IG", "apify~instagram-profile-scraper").strip()
ACTIF = (os.environ.get("ETATS_CLASSEUR", "1").strip() or "1") != "0"
GOOD_JOURS = int(os.environ.get("ETATS_GOOD_JOURS", "3") or 3)         # jours de publication de suite pour GOOD
BAN_JOURS = int(os.environ.get("ETATS_BAN_JOURS", "1") or 1)           # 28/09 (Gaëtan) : plus lisible = BAN par défaut, dès le premier scan
HEURE_UTC = int(os.environ.get("ETATS_HEURE_UTC", "7") or 7)           # après le rapport inputs du matin
JOURS_HISTORIQUE = 14
SUIVIS = ("a creer", "à créer", "warmup", "good", "prive", "privé", "ban")
VERSION = 4                       # 26/09 soir : passage forcé au déploiement pour recaler le parcours de Daniella (étape 2)
DASHBOARD_VERSION = 4             # 28/09 : structure de l'onglet Dashboard (12 colonnes, exclusions) ; changée → réécrit au démarrage, sans scan
EXCLUS_DEFAUT = [m.strip() for m in os.environ.get("DASHBOARD_EXCLUS", "Julien, Rianah").split(",") if m.strip()]


def dashboard_exclus(d=None) -> list:
    """Les prénoms tenus hors du Dashboard (28/09, Gaëtan : « Julien et Rianah, on va les exclure totalement du clipping ») :
    la liste de l'état, tenue par `!dashboard exclure Prénom` / `!dashboard inclure Prénom`, sinon DASHBOARD_EXCLUS."""
    d = d if d is not None else _lire()
    return list(d["dashboard_exclus"]) if isinstance(d.get("dashboard_exclus"), list) else list(EXCLUS_DEFAUT)
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
    out = {h.lower(): {"existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0, "fautes": 0} for h in handles}
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
                if RE_FAUTE.search(str(post.get("caption") or "")):    # 28/09 : lien ou @ dans la légende → ❌
                    fiche["fautes"] += 1
    return out


# ------------------------------------------------------------------ règles
def _series(historique: list) -> tuple:
    """(jours d'absence de suite, jours de publication de suite) en partant du dernier jour."""
    absents = publie = 0
    for j in reversed(historique):
        if j.get("existe") and not j.get("restreint"):                  # 28/09 : un compte restreint (followers illisibles) compte absent
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
    changements, followers_maj, clics_maj, liens_maj = [], 0, 0, 0
    ids_suivis = {id(c) for c in suivis}
    async def _cellule(c, champ, valeur):                                # 27/09 : la cellule retourne dans l'onglet de la ligne
        await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, onboarding.cellule(c, champ), [[valeur]])
    for c in lignes:
        h = c["handle"].lower()
        m = mesures.get(h) or {"existe": False, "prive": False, "restreint": False, "followers": 0, "posts": 0}
        if ecrire and m["existe"] and not m["restreint"] and str(m["followers"]) != str(c.get("followers", "")).replace(" ", ""):
            try:
                await _cellule(c, "followers", m["followers"])
                followers_maj += 1
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Classeur : followers de %s non écrits : %s", c["handle"], erreur)
        if id(c) not in ids_suivis:
            continue
        hist = [x for x in d["historique"].get(h, []) if x.get("jour") != jour]
        hist.append({"jour": jour, "existe": m["existe"], "posts": m["posts"], "prive": m["prive"], "fautes": m.get("fautes", 0),
                     "restreint": bool(m.get("restreint")), "followers": m.get("followers", 0)})
        d["historique"][h] = hist[-JOURS_HISTORIQUE:]
        apres = decider(c["etat"], m, d["historique"][h], h in d["bans_auto"])
        if apres:
            changements.append((c["handle"], c["gerant"], c["etat"], apres, c["ligne"]))
            if ecrire:
                try:
                    await _cellule(c, "etat", apres)
                except Exception as erreur:                              # noqa: BLE001
                    journal.warning("Classeur : état de %s non écrit : %s", c["handle"], erreur)
                    continue
                if apres == "BAN":
                    d["bans_auto"][h] = jour
                elif h in d["bans_auto"]:
                    d["bans_auto"].pop(h, None)
    # 26/09 : tableau de bord — pour chaque ligne qui a un Gérant, ses visites payables des 7 derniers jours
    # (le lien GAML de la ligne est tenu par onboarding.liens_classeur depuis le 27/09 : un lien par créatrice)
    if ecrire and _deps.get("clics_7j"):
        cache = {}
        for c in comptes:
            g = _norm(c["gerant"])
            if not c["handle"] or g in ("", "x", "y", "z"):
                continue
            if g not in cache:
                try:
                    cache[g] = _deps["clics_7j"](c["gerant"])
                except Exception as erreur:                              # noqa: BLE001
                    journal.warning("Clics de %s : %s", c["gerant"], erreur)
                    cache[g] = None
            clics = cache[g]
            try:
                if clics is not None and onboarding.a_colonne("clics", c.get("onglet", "")) and str(clics) != str(c.get("clics", "")).replace(" ", ""):
                    await _cellule(c, "clics", clics)
                    clics_maj += 1
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Classeur : clics de %s non écrits : %s", c["handle"], erreur)
    if ecrire:
        try:
            liens_maj = (await onboarding.liens_classeur(comptes)).get("ecrits", 0)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Colonne Lien GAML (états) : %s", erreur)
    if ecrire and _deps.get("reconcilier"):
        try:
            etats_h = {c["handle"].lower(): c["etat"] for c in comptes if c["handle"]}
            for handle, _, _, apres, _ in changements:
                etats_h[handle.lower()] = apres
            # 28/09 : les comptes qui ont publié au moins une fois (le premier Reel valide l'étape 5 tout seul)
            publies = {h for h, hist in d["historique"].items() if any(e.get("existe") and int(e.get("posts") or 0) > 0 for e in hist)}
            await _deps["reconcilier"](etats_h, publies)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réconciliation des parcours : %s", erreur)
    if ecrire and _deps.get("reservations_expirees"):                             # 28/09 : la réservation qui expire
        try:
            await _deps["reservations_expirees"](d["historique"])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réservations expirées : %s", erreur)
    fautifs = sorted({f"{c['gerant'].split()[0]} (@{c['handle']})" for c in lignes
                      if c.get("gerant") and (mesures.get(c["handle"].lower()) or {}).get("fautes")})
    if ecrire and fautifs and _deps.get("canal_admin"):                           # 28/09 : contrôle par Reel, une ligne à l'admin
        try:
            canal_f = await _deps["canal_admin"]()
            if canal_f is not None:
                await canal_f.send("⚠️ Lien ou @ dans une légende de Reel hier : " + ", ".join(fautifs)[:1800])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Alerte légendes : %s", erreur)
    if ecrire and _deps.get("deposer") and _deps.get("salon_de_prenom"):        # 27/09 : « Reels d'hier » du message du matin
        for prenom, texte_r in lignes_reels(comptes, d["historique"], jour).items():
            try:
                sid = _deps["salon_de_prenom"](prenom)
                if sid:
                    _deps["deposer"](sid, "reels", texte_r)
            except Exception as erreur:                                      # noqa: BLE001
                journal.warning("Reels du matin pour %s : %s", prenom, erreur)
    if ecrire:
        try:                                                                        # 28/09 : l'onglet Dashboard, une ligne par clipper
            await ecrire_dashboard(comptes, d["historique"], _deps.get("clics_7j"), jour)
            d["dashboard_version"] = DASHBOARD_VERSION
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : %s", erreur)
    if ecrire:
        d["dernier"] = jour
        d["version"] = VERSION
        _ecrire(d)
    journal.info("États du classeur : %d compte(s) scanné(s), %d changement(s), %d followers, %d clics, %d liens mis à jour",
                 len(lignes), len(changements), followers_maj, clics_maj, liens_maj)
    return {"changements": changements, "scannes": len(lignes), "erreur": "", "followers": followers_maj, "clics": clics_maj, "liens": liens_maj}


ONGLET_DASHBOARD = os.environ.get("ONGLET_DASHBOARD", "Dashboard").strip() or "Dashboard"
ENTETE_DASHBOARD = ["Clipper", "Comptes", "Créés", "À créer", "BAN", "Followers cumulés", "Visites 7 j", "Visites hier", "Reels 7 j", "Reels hier",
                    "Dernier Reel", "Détail des comptes"]
NB_COLONNES = len(ENTETE_DASHBOARD)


def _fenetre(jour: str, jours: int) -> str:
    """Le premier jour (ISO) d'une fenêtre de `jours` jours qui finit à `jour` ; '' si la date est illisible."""
    try:
        return (date.fromisoformat(str(jour)[:10]) - timedelta(days=jours - 1)).isoformat()
    except ValueError:
        return ""


def _entier(v) -> int:
    try:
        return int(re.sub(r"[^\d-]", "", str(v or "")) or 0)
    except ValueError:
        return 0


def lignes_dashboard(comptes: list, historique: dict, clics_de, jour: str, exclus=None) -> list:
    """28/09 (Gaëtan : « un dashboard par clipper, au même endroit ») : par créatrice, une ligne par clipper — comptes, créés,
    à créer, BAN, followers cumulés des comptes vivants, visites payables des 7 derniers jours (le chiffre de la colonne Clics,
    une seule fois), Reels vus par le scan sur 7 jours, dernier Reel, et le détail compte par compte. Triée par visites."""
    exclus_n = {_norm(str(x).split()[0]) for x in (exclus or []) if str(x).strip()}
    par = {}
    for c in comptes:
        g = (c.get("gerant") or "").strip()
        if not g or _norm(g) in ("x", "y", "z", "aaa", "?", "-", "libre", "dispo") or not c.get("handle"):
            continue
        if _norm(g.split()[0]) in exclus_n:                                 # hors clipping (Julien, Rianah…)
            continue
        crea = ((c.get("creatrice") or c.get("onglet") or "?").split() or ["?"])[0]
        par.setdefault(crea, {}).setdefault(g.split()[0], []).append(c)
    lignes = [[f"Dashboard clippers — mis à jour le {jour} · visites payables (GAML) sur 7 jours et hier, followers des comptes en gestion, Reels vus par le scan"
               + (f" · hors clipping : {', '.join(str(x) for x in exclus)}" if exclus else "")], []]
    tot_f = tot_v = tot_vh = tot_r = tot_rh = tot_c = 0
    for crea, clippers in par.items():
        rows = []
        for g, cs in clippers.items():
            etats = [_norm(c.get("etat") or "") for c in cs]
            ban = sum(1 for e in etats if e == "ban")
            a_creer = sum(1 for e in etats if e in ("a creer", "à créer", ""))
            crees = len(cs) - ban - a_creer
            # 28/09 (Gaëtan : « la somme des followers des 3 comptes que le clipper a en gestion ») : les comptes dont
            # l'Utilisation est Clipper (ou vide), sauf les BAN (morts), quel que soit l'état ; un compte passé Metricool
            # ou « à mettre Metricool » n'est plus en gestion, il reste dans le détail.
            en_gestion = [c for c, e in zip(cs, etats) if e != "ban" and _norm(c.get("utilisation") or "clipper") in ("clipper", "")]
            followers = sum(_entier(c.get("followers")) for c in en_gestion)
            # Visites : d'abord la colonne « Clics last 7d. » du classeur (écrite par le scan, propre à la créatrice de la
            # ligne : Lilian sous Chloé et Lilian sous Sophie sont deux liens), sinon le total du clipper via clics_de.
            en_colonne = [_entier(c.get("clics")) for c in cs if str(c.get("clics") or "").strip() != ""]
            if en_colonne:
                visites = max(en_colonne)
            else:
                try:
                    visites = clics_de(g) if clics_de else None
                except Exception:                                       # noqa: BLE001
                    visites = None
            try:                                                        # visites d'hier (dépendance à deux arguments, 28/09)
                visites_hier = clics_de(g, 1) if clics_de else None
            except Exception:                                           # noqa: BLE001
                visites_hier = None
            depuis = _fenetre(jour, 7)
            reels7, reels_hier, dernier = 0, 0, ""
            for c in cs:
                hist = historique.get(c["handle"].lower()) or []
                for e in (hist if depuis else hist[-7:]):
                    j_e = str(e.get("jour", ""))[:10]
                    if not e.get("existe") or (depuis and not (depuis <= j_e <= str(jour)[:10])):
                        continue
                    reels7 += int(e.get("posts") or 0)
                    if j_e == str(jour)[:10]:                             # le scan de `jour` compte ce qui est sorti depuis la veille
                        reels_hier += int(e.get("posts") or 0)
                for e in hist:
                    if e.get("existe") and int(e.get("posts") or 0) > 0 and str(e.get("jour", "")) > dernier:
                        dernier = str(e.get("jour", ""))
            detail = " · ".join(f"{c['handle']} ({(c.get('etat') or '?').strip()}, {_entier(c.get('followers'))}"
                                + ("" if _norm(c.get("utilisation") or "clipper") == "clipper" else f", {str(c.get('utilisation')).strip()}") + ")"
                                for c in cs)
            rows.append([g, len(cs), crees, a_creer, ban, followers, visites if visites is not None else "",
                         visites_hier if visites_hier is not None else "", reels7, reels_hier, dernier, detail])
        rows.sort(key=lambda r: (-(r[6] if isinstance(r[6], int) else -1), -r[5]))
        somme = lambda i: sum(r[i] for r in rows if isinstance(r[i], int))  # noqa: E731
        f_c, v_c, vh_c, r_c, rh_c = somme(5), somme(6), somme(7), somme(8), somme(9)
        tot_f += f_c; tot_v += v_c; tot_vh += vh_c; tot_r += r_c; tot_rh += rh_c; tot_c += len(rows)
        lignes.append([crea.upper(), f"{len(rows)} clipper(s)", "", "", "", f_c, v_c, vh_c, r_c, rh_c, "", ""])
        lignes.append(list(ENTETE_DASHBOARD))
        lignes.extend(rows)
        lignes.append([])
    lignes.append(["TOTAL", f"{tot_c} clipper(s)", "", "", "", tot_f, tot_v, tot_vh, tot_r, tot_rh, "", ""])
    return lignes


async def ecrire_dashboard(comptes: list, historique: dict, clics_de, jour: str, exclus=None) -> int:
    """Écrit l'onglet Dashboard du classeur des logins (créé s'il manque, vidé puis réécrit). Renvoie le nombre de lignes."""
    if exclus is None:
        try:
            exclus = dashboard_exclus()
        except Exception:                                                   # noqa: BLE001 — sans état (tests), la liste par défaut
            exclus = list(EXCLUS_DEFAUT)
    lignes = lignes_dashboard(comptes, historique, clics_de, jour, exclus)
    cid = onboarding.CLASSEUR_LOGINS_ID
    try:
        await google_api.sheets_creer_onglet(cid, ONGLET_DASHBOARD)
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Onglet %s : %s", ONGLET_DASHBOARD, erreur)
    await google_api.sheets_effacer(cid, f"'{ONGLET_DASHBOARD}'!A1:N500")
    await google_api.sheets_ecrire(cid, f"'{ONGLET_DASHBOARD}'!A1", lignes)
    try:                                                                # 28/09 (Gaëtan : « des couleurs, des groupes, des cards »)
        props = await google_api.sheets_proprietes(cid)
        sid = props.get(ONGLET_DASHBOARD, {}).get("id")
        if sid is not None:
            await google_api.sheets_batch_update(cid, requetes_mise_en_forme(lignes, sid))
    except Exception as erreur:                                         # noqa: BLE001 — la mise en forme ne bloque jamais le scan
        journal.warning("Dashboard : mise en forme impossible (%s)", erreur)
    return len(lignes)


# Palette par créatrice : (bandeau, teinte des lignes). Lisible sur téléphone, une couleur par bloc.
PALETTE_DASHBOARD = {"chloe": ("#C2185B", "#FCE4EC"), "sarah": ("#1565C0", "#E3F2FD"), "sophie": ("#6A1B9A", "#F3E5F5"),
                     "jade": ("#2E7D32", "#E8F5E9"), "maddie": ("#EF6C00", "#FFF3E0"), "clara": ("#00838F", "#E0F7FA")}
PALETTE_DEFAUT = ("#455A64", "#ECEFF1")
SOMBRE, BLANC, GRIS_CLAIR, GRIS_TEXTE = "#263238", "#FFFFFF", "#ECEFF1", "#546E7A"
LARGEURS_DASHBOARD = (120, 78, 64, 70, 58, 118, 96, 96, 80, 80, 96, 560)


def _rgb(hexa: str) -> dict:
    h = hexa.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def _melange(hexa: str, t: float) -> str:
    """Blanc → couleur, t entre 0 et 1 (dégradé des visites)."""
    h = hexa.lstrip("#"); t = max(0.0, min(1.0, t))
    return "#" + "".join(f"{int(round(255 + (int(h[i:i + 2], 16) - 255) * t)):02X}" for i in (0, 2, 4))


def _plage(sid: int, r0: int, r1: int, c0: int = 0, c1: int = NB_COLONNES) -> dict:
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _cellules(sid, r0, r1, c0, c1, fond=None, texte=None, gras=None, taille=None, aligne=None, format_nombre=None, coupe=None,
              format_date=None) -> dict:
    fmt, champs = {}, []
    if fond:
        fmt["backgroundColor"] = _rgb(fond); champs.append("backgroundColor")
    tf = {}
    if texte: tf["foregroundColor"] = _rgb(texte)
    if gras is not None: tf["bold"] = gras
    if taille: tf["fontSize"] = taille
    if tf:
        fmt["textFormat"] = tf; champs.append("textFormat")
    if aligne:
        fmt["horizontalAlignment"] = aligne; champs.append("horizontalAlignment")
    if format_nombre:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": format_nombre}; champs.append("numberFormat")
    if format_date:                                                         # 28/09 : « Dernier Reel » affichait 46 293 (série)
        fmt["numberFormat"] = {"type": "DATE", "pattern": format_date}; champs.append("numberFormat")
    if coupe:
        fmt["wrapStrategy"] = coupe; champs.append("wrapStrategy")
    fmt["verticalAlignment"] = "MIDDLE"; champs.append("verticalAlignment")
    return {"repeatCell": {"range": _plage(sid, r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt},
                           "fields": "userEnteredFormat(" + ",".join(champs) + ")"}}


def requetes_mise_en_forme(lignes: list, sid: int) -> list:
    """La mise en forme de l'onglet Dashboard, recalculée sur les lignes réellement écrites : titre en bandeau sombre, un bloc
    (« card ») par créatrice avec son bandeau de couleur, en-têtes gris, lignes en zébrure, BAN en rouge, à créer en orange,
    visites en dégradé vert, cadre autour de chaque bloc, quadrillage masqué, titre et colonne des prénoms figés."""
    n = len(lignes)
    req = [{"unmergeCells": {"range": _plage(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2)}},
           _cellules(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2, fond=BLANC, texte="#212121", gras=False, taille=10, aligne="LEFT", coupe="CLIP"),
           {"updateBorders": {"range": _plage(sid, 0, max(n, 1) + 100, 0, NB_COLONNES + 2), "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
                              "left": {"style": "NONE"}, "right": {"style": "NONE"}, "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}}},
           {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": 1, "frozenColumnCount": 1}},
                                      "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}]
    for i, largeur in enumerate(LARGEURS_DASHBOARD):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                  "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": max(n, 1) + 100},
                                              "properties": {"pixelSize": 24}, "fields": "pixelSize"}})
    if not lignes:
        return req
    # Titre
    req += [_cellules(sid, 0, 1, 0, NB_COLONNES, fond=SOMBRE, texte=BLANC, gras=True, taille=12, aligne="LEFT", coupe="OVERFLOW_CELL"),   # pas de fusion : la colonne A est figée
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}}]
    max_v = max((r[6] for r in lignes if len(r) >= 7 and isinstance(r[6], int) and r[0] not in ("TOTAL",) and r != ENTETE_DASHBOARD
                 and not (len(r) >= 2 and str(r[1]).endswith("clipper(s)"))), default=0)
    i = 1
    while i < n:
        r = lignes[i]
        if len(r) >= 2 and r[0] == "TOTAL":
            req += [_cellules(sid, i, i + 1, 0, NB_COLONNES, fond=SOMBRE, texte=BLANC, gras=True, taille=11),
                    _cellules(sid, i, i + 1, 5, 10, fond=SOMBRE, texte=BLANC, gras=True, taille=11, aligne="CENTER", format_nombre="#,##0"),
                    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 30}, "fields": "pixelSize"}}]
            i += 1
            continue
        if len(r) >= 2 and str(r[1]).endswith("clipper(s)") and i + 1 < n and lignes[i + 1] == ENTETE_DASHBOARD:
            bande, teinte = PALETTE_DASHBOARD.get(_norm(str(r[0])).split()[0] if str(r[0]).strip() else "", PALETTE_DEFAUT)
            debut = i
            fin = i + 2
            while fin < n and lignes[fin] and lignes[fin] != ENTETE_DASHBOARD and lignes[fin][0] != "TOTAL":
                fin += 1
            # bandeau créatrice + en-têtes
            req += [_cellules(sid, i, i + 1, 0, NB_COLONNES, fond=bande, texte=BLANC, gras=True, taille=12, coupe="OVERFLOW_CELL"),
                    _cellules(sid, i, i + 1, 5, 10, fond=bande, texte=BLANC, gras=True, taille=12, aligne="CENTER", format_nombre="#,##0"),
                    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 32}, "fields": "pixelSize"}},
                    _cellules(sid, i + 1, i + 2, 0, NB_COLONNES, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9),
                    _cellules(sid, i + 1, i + 2, 1, NB_COLONNES - 1, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9, aligne="CENTER")]
            for k, ligne in enumerate(lignes[i + 2:fin]):
                j = i + 2 + k
                fond = teinte if k % 2 == 0 else BLANC
                req += [_cellules(sid, j, j + 1, 0, NB_COLONNES, fond=fond, texte="#212121", gras=False, taille=10),
                        _cellules(sid, j, j + 1, 0, 1, fond=fond, texte="#212121", gras=True, taille=10),
                        _cellules(sid, j, j + 1, 1, 10, fond=fond, texte="#37474F", gras=False, taille=10, aligne="CENTER", format_nombre="#,##0"),
                        _cellules(sid, j, j + 1, 10, 11, fond=fond, texte="#37474F", gras=False, taille=10, aligne="CENTER", format_date="dd/MM"),
                        _cellules(sid, j, j + 1, 11, 12, fond=fond, texte=GRIS_TEXTE, gras=False, taille=9, coupe="CLIP")]
                comptes, crees, a_creer, ban = (_entier(ligne[1]), _entier(ligne[2]), _entier(ligne[3]), _entier(ligne[4])) if len(ligne) >= 5 else (0, 0, 0, 0)
                if crees and crees == comptes:
                    req.append(_cellules(sid, j, j + 1, 2, 3, fond=fond, texte="#2E7D32", gras=True, taille=10, aligne="CENTER"))
                if a_creer > 0:
                    req.append(_cellules(sid, j, j + 1, 3, 4, fond="#FFE0B2", texte="#E65100", gras=True, taille=10, aligne="CENTER"))
                if ban > 0:
                    req.append(_cellules(sid, j, j + 1, 4, 5, fond="#FFCDD2", texte="#B71C1C", gras=True, taille=10, aligne="CENTER"))
                v = ligne[6] if len(ligne) >= 7 and isinstance(ligne[6], int) else None
                if v is not None and v > 0 and max_v:
                    req.append(_cellules(sid, j, j + 1, 6, 7, fond=_melange("#43A047", 0.15 + 0.85 * (v / max_v) ** 0.5), texte="#1B5E20", gras=True, taille=10, aligne="CENTER", format_nombre="#,##0"))
                for col in (7, 9):                                          # visites d'hier, Reels d'hier : en vert quand il y en a
                    x = ligne[col] if len(ligne) > col and isinstance(ligne[col], int) else 0
                    if x > 0:
                        req.append(_cellules(sid, j, j + 1, col, col + 1, fond=fond, texte="#1B5E20", gras=True, taille=10, aligne="CENTER", format_nombre="#,##0"))
            # cadre du bloc
            req.append({"updateBorders": {"range": _plage(sid, debut, fin, 0, NB_COLONNES),
                                          "top": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}, "bottom": {"style": "SOLID_MEDIUM", "color": _rgb(bande)},
                                          "left": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}, "right": {"style": "SOLID_MEDIUM", "color": _rgb(bande)}}})
            i = fin
            continue
        if not r:
            req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": 14}, "fields": "pixelSize"}})
        i += 1
    return req


RE_FAUTE = re.compile(r"https?://|www\.|getallmylinks|gaml\.|\.fr/|\.app/|(?<![\w.])@[A-Za-z0-9_.]{3,}")


def lignes_reels(comptes: list, historique: dict, jour: str) -> dict:
    """{prénom du gérant: ligne du matin} — les publications apparues sur ses comptes (Utilisation = Clipper) entre le scan
    précédent et celui de `jour` (27/09 : les Inputs clippers sont éteints, la ligne « Reels d'hier » vient d'ici)."""
    par = {}
    for c in comptes:
        g = str(c.get("gerant") or "").strip()
        h = str(c.get("handle") or "").lower()
        if not h or not g or _norm(g) in ("", "x", "y", "z") or _norm(c.get("utilisation") or "") != "clipper":
            continue
        entrees = [e for e in historique.get(h, []) if e.get("existe")]
        auj = next((e for e in entrees if e.get("jour") == jour), None)
        if auj is None:
            continue
        avant = [e for e in entrees if str(e.get("jour") or "") < jour]
        prev = int((avant[-1].get("posts") if avant else 0) or 0)
        delta = max(0, int(auj.get("posts") or 0) - prev)
        p = par.setdefault(g.split()[0], {"n": 0, "comptes": 0, "fautes": 0})
        p["n"] += delta
        p["comptes"] += 1
        p["fautes"] += int(auj.get("fautes") or 0)
    return {prenom: f"🎬 Hier : {p['n']} publication(s) sur tes comptes." + (" ✅" if p["n"] >= 2 and not p["fautes"] else "")
            + ("\n❌ Un lien ou un @ dans la légende d'un Reel d'hier : enlève-le. Le lien va seulement en story à la une."
               if p["fautes"] else "")
            for prenom, p in par.items()}


def texte_bilan(bilan: dict, test: bool = False) -> str:
    if bilan.get("erreur"):
        return f"⚠️ États du classeur : {bilan['erreur']}."
    ch = bilan["changements"]
    entete = (f"🗂️ **États du classeur** · {bilan['scannes']} compte(s) regardés sur Instagram · "
              f"{bilan.get('followers', 0)} followers, {bilan.get('clics', 0)} clics 7 j, {bilan.get('liens', 0)} liens GAML mis à jour")
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
            if d.get("historique") and d.get("dashboard_version") != DASHBOARD_VERSION:     # 28/09 : nouvelle structure → réécrit
                await ecrire_dashboard(await onboarding.lire_comptes(), d.get("historique", {}), _deps.get("clics_7j"), jour)
                d = _lire(); d["dashboard_version"] = DASHBOARD_VERSION; _ecrire(d)
                journal.info("Dashboard réécrit (structure v%s)", DASHBOARD_VERSION)
            if maintenant.hour >= HEURE_UTC and (d.get("dernier") != jour or d.get("version") != VERSION) \
                    and int(d.get("essais", {}).get(jour, 0)) < 3:
                bilan = await executer(ecrire=True)
                if bilan.get("erreur"):
                    d = _lire(); d.setdefault("essais", {})[jour] = int(d.get("essais", {}).get(jour, 0)) + 1; _ecrire(d)
                    journal.warning("États du classeur : %s", bilan["erreur"])
                else:
                    if (bilan["changements"] or bilan.get("followers") or bilan.get("clics")) and _deps.get("canal_admin"):
                        canal = await _deps["canal_admin"]()
                        if canal is not None:
                            await canal.send(texte_bilan(bilan)[:1990])
                    bans = [f"`{h}` ({g})" for h, g, _, a, _ in bilan["changements"] if a == "BAN"]
                    if bans and _deps.get("notifier"):
                        await _deps["notifier"]("🚫 **Comptes introuvables ou illisibles sur Instagram, passés en BAN** : "
                                                + ", ".join(bans) + ". À remplacer : `!liberer Prénom handle`, puis un nouvel identifiant.")
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.exception("Boucle états du classeur : %s", erreur)
        await asyncio.sleep(900)


async def commande_staff(message, texte: str) -> bool:
    """`!etats-comptes` : passage immédiat · `!etats-comptes test` : ce qui changerait, sans rien écrire."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!etats-comptes", "!états-comptes", "!dashboard"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if mots[0].lower() == "!dashboard":                                # 28/09 : l'onglet Dashboard réécrit tout de suite, sans scan
        if not onboarding.actif():
            await message.reply("Classeur inactif : `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
            return True
        d = _lire()
        exclus = dashboard_exclus(d)
        if len(mots) >= 3 and mots[1].lower() in ("exclure", "inclure"):     # `!dashboard exclure Julien` · `!dashboard inclure Rianah`
            prenom = " ".join(mots[2:]).strip()
            deja = [x for x in exclus if _norm(x) == _norm(prenom)]
            if mots[1].lower() == "exclure" and not deja:
                exclus.append(prenom)
            elif mots[1].lower() == "inclure":
                exclus = [x for x in exclus if _norm(x) != _norm(prenom)]
            d["dashboard_exclus"] = exclus
            _ecrire(d)
        try:
            n = await ecrire_dashboard(await onboarding.lire_comptes(), d.get("historique", {}), _deps.get("clics_7j"),
                                       datetime.now(timezone.utc).strftime("%Y-%m-%d"), exclus)
            await message.reply(f"✅ Onglet « {ONGLET_DASHBOARD} » du classeur des logins réécrit ({n} lignes) : une ligne par clipper, par créatrice."
                                + (f"\nHors clipping : {', '.join(exclus)} (`!dashboard inclure Prénom` pour remettre quelqu'un)." if exclus
                                   else "\nPersonne n'est exclu (`!dashboard exclure Prénom`)."))
        except Exception as erreur:                                     # noqa: BLE001
            await message.reply(f"❌ Dashboard : {type(erreur).__name__} {str(erreur)[:150]}")
        return True
    if not actif():
        await message.reply("États du classeur inactifs : il faut `APIFY_TOKEN`, `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
        return True
    test = len(mots) > 1 and mots[1].lower() == "test"
    await message.reply("⏳ Je regarde Instagram…")
    bilan = await executer(ecrire=not test)
    await message.reply(texte_bilan(bilan, test)[:1990])
    return True
