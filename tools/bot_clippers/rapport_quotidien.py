"""Rapport quotidien compact (29/09, Gaëtan : « simplifie le GAML Report Bot, le plus pertinent et compact possible »).

Remplace le rapport GitHub Actions (trois sources mortes sur cinq : clé GAML révoquée, onglet Tracking cassé, inputs Apify de
l'ancien système). Tout vient de ce que le bot tient déjà : Data G&M (subs et CA saisis par Rianah), les relevés GAML du bot
(visites payables), le scan quotidien du classeur (Reels, comptes), Metricool si la clé est posée. Huit lignes, la veille,
envoyées à RAPPORT_HEURE_PARIS (13 h, après la saisie de Rianah) sur Telegram et dans le salon admin ; `!rapport` l'envoie
tout de suite.

Dépendances (`configurer`) : lire_json, ecrire_json, FICHIER (état : dernier envoi), FICHIER_ETATS (historique du scan),
lire_comptes, clics_de(prénom, jours) -> int|None, groupes() -> {créatrice: [prénoms]}, exclus() -> [prénoms], canal_admin,
envoyer_telegram, heure_paris, normaliser, google_api, est_staff."""
import asyncio
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

import aiohttp

journal = logging.getLogger("bot.rapport")
_deps: dict = {}
ACTIF = os.environ.get("RAPPORT_QUOTIDIEN", "1").strip() != "0"
HEURE_PARIS = int(os.environ.get("RAPPORT_HEURE_PARIS", "13") or 13)
DATA_GM_ID = os.environ.get("DATA_GM_ID", "").strip()
METRICOOL_API_KEY = os.environ.get("METRICOOL_API_KEY", "").strip()
METRICOOL_USER_ID = os.environ.get("METRICOOL_USER_ID", "").strip()
TAUX_USD_EUR = float((os.environ.get("TAUX_USD_EUR", "0.92") or "0.92").replace(",", "."))
ONGLETS_IGNORES = ("synth", "notice", "param", "config", "dashboard")
JOURS_SILENCE = 3
MOIS_FR = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
           "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12}
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def configurer(deps: dict):
    _deps.update(deps)


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else str(t or "").strip().lower()


def _nb(x) -> int:
    return f"{int(round(x)):,}".replace(",", " ")


def _pct(a, b):
    """Variation en % de a par rapport à b, ou None."""
    return None if not b else round((a - b) / b * 100)


def _delta(d) -> str:
    return "" if d is None else (f" ({'+' if d > 0 else ''}{d} %)")


# ------------------------------------------------------------------ Data G&M (subs et CA saisis par Rianah)
def _date(cellule, annee: int):
    t = str(cellule or "").strip().lower()
    if not t:
        return None
    m = re.fullmatch(r"(\d{1,2})\s+([a-zéû]+)\.?(?:\s+(\d{4}))?", t)
    if m and m.group(2) in MOIS_FR:
        try:
            return date(int(m.group(3) or annee), MOIS_FR[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    for motif in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m"):
        try:
            d = datetime.strptime(t, motif).date()
            return d.replace(year=annee) if motif == "%d/%m" else d
        except ValueError:
            continue
    return None


def _nombre(x) -> float:
    t = re.sub(r"[^\d,.\-]", "", str(x or "")).replace(",", ".")
    try:
        return float(t) if t not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


def lignes_data_gm(onglet: str, valeurs: list, aujourdhui: date) -> list:
    """Un onglet créatrice → [{date, of_subs, of_usd, mym_subs, mym_eur, saisi}] (saisi = au moins une case non vide)."""
    out, en_tete_vu = [], False
    for l in valeurs:
        l = (list(l) + [""] * 6)[:6]
        if not en_tete_vu:
            if str(l[0]).strip().lower() == "date":
                en_tete_vu = True
            continue
        d = _date(l[0], aujourdhui.year)
        if d is None:
            continue
        if d > aujourdhui + timedelta(days=1):
            d = d.replace(year=d.year - 1)
        out.append({"date": d, "of_subs": _nombre(l[1]), "of_usd": _nombre(l[2]), "mym_subs": _nombre(l[4]), "mym_eur": _nombre(l[5]),
                    "saisi": any(str(x).strip() for x in (l[1], l[2], l[4], l[5]))})
    return out


async def data_gm(aujourdhui: date) -> dict:
    """{créatrice: lignes} depuis le classeur Data G&M (compte de service), {} si non configuré."""
    g = _deps.get("google_api")
    if not (DATA_GM_ID and g and g.actif()):
        return {}
    props = await g.sheets_proprietes(DATA_GM_ID)
    titres = [t for t in props if not any(_n(t).startswith(p) for p in ONGLETS_IGNORES) and not props[t].get("masque")]
    blocs = await g.sheets_lire_plusieurs(DATA_GM_ID, [f"'{t}'!A1:F400" for t in titres]) if titres else []
    return {t: lignes_data_gm(t, b, aujourdhui) for t, b in zip(titres, blocs) if b}


def bloc_subs(donnees: dict, hier: date) -> dict:
    """Subs et CA (€) d'hier par créatrice, 7 jours et 7 jours d'avant, créatrices non saisies hier."""
    par, tot = {}, {"subs": 0, "of_usd": 0.0, "mym_eur": 0.0, "subs7": 0, "eur7": 0.0, "subs7_avant": 0, "eur7_avant": 0.0}
    non_saisis = []
    for crea, lignes in donnees.items():
        j = next((l for l in lignes if l["date"] == hier), None)
        if j is None or not j["saisi"]:
            non_saisis.append(crea)
        subs = int((j or {}).get("of_subs", 0) + (j or {}).get("mym_subs", 0))
        of_usd, mym_eur = (j or {}).get("of_usd", 0.0), (j or {}).get("mym_eur", 0.0)
        s7 = [l for l in lignes if hier - timedelta(days=6) <= l["date"] <= hier]
        s7a = [l for l in lignes if hier - timedelta(days=13) <= l["date"] <= hier - timedelta(days=7)]
        subs7 = int(sum(l["of_subs"] + l["mym_subs"] for l in s7)); eur7 = sum(l["of_usd"] * TAUX_USD_EUR + l["mym_eur"] for l in s7)
        subs7a = int(sum(l["of_subs"] + l["mym_subs"] for l in s7a)); eur7a = sum(l["of_usd"] * TAUX_USD_EUR + l["mym_eur"] for l in s7a)
        par[crea] = {"subs": subs, "of_usd": of_usd, "mym_eur": mym_eur, "subs7": subs7, "eur7": eur7}
        tot["subs"] += subs; tot["of_usd"] += of_usd; tot["mym_eur"] += mym_eur
        tot["subs7"] += subs7; tot["eur7"] += eur7; tot["subs7_avant"] += subs7a; tot["eur7_avant"] += eur7a
    return {"par": par, "tot": tot, "non_saisis": non_saisis}


# ------------------------------------------------------------------ visites payables (relevés GAML du bot)
def visites(groupes: dict, exclus: list, clics_de) -> dict:
    """Par créatrice {hier, j7} et par clipper [(prénom, hier)], hors clipping exclu."""
    ex = {_n(x) for x in exclus}
    par_crea, par_clipper = {}, []
    for crea, noms in groupes.items():
        h = s = 0
        for prenom in noms:
            if _n(prenom) in ex:
                continue
            try:
                v1, v7 = clics_de(prenom, 1), clics_de(prenom, 7)
            except Exception:                                               # noqa: BLE001
                v1, v7 = None, None
            h += int(v1 or 0); s += int(v7 or 0)
            par_clipper.append((prenom, int(v1 or 0)))
        par_crea[crea] = {"hier": h, "j7": s}
    par_clipper.sort(key=lambda x: -x[1])
    return {"par": par_crea, "clippers": par_clipper}


# ------------------------------------------------------------------ Reels (scan quotidien du classeur)
def reels(comptes: list, historique: dict, jour_scan: str, groupes: dict, exclus: list) -> dict:
    """Reels d'hier (le scan de `jour_scan`) et sur 7 jours par créatrice ; clippers qui ont publié ; clippers silencieux
    (au moins un compte créé, aucun Reel depuis JOURS_SILENCE jours)."""
    ex = {_n(x) for x in exclus}
    crea_de = {}
    for crea, noms in groupes.items():
        for p in noms:
            crea_de.setdefault(_n(p), crea)
    depuis7 = (date.fromisoformat(jour_scan) - timedelta(days=6)).isoformat()
    depuis_s = (date.fromisoformat(jour_scan) - timedelta(days=JOURS_SILENCE - 1)).isoformat()
    # 01/10 (Mathias listé « sans Reel » le jour de son warm-up, Ricado et Michel pour un ancien compte privé) : seuls comptent
    # les comptes qui publient (GOOD, WARMUP, ACTIF — plus PRIVE) vus vivants par le scan depuis au moins JOURS_SILENCE + 1 jours
    # (24 h de warm-up, puis JOURS_SILENCE jours pour publier)
    limite = (date.fromisoformat(jour_scan) - timedelta(days=JOURS_SILENCE + 1)).isoformat()
    par_crea, par_clipper, recents, crees = {}, {}, set(), set()
    for c in comptes:
        g = _n(str(c.get("gerant") or "").split()[0] if str(c.get("gerant") or "").strip() else "")
        if not g or g in ex or g not in crea_de:
            continue
        crea = crea_de[g]
        if _n(c.get("etat") or "") in ("good", "warmup", "actif"):
            vus = sorted(str(e.get("jour", ""))[:10] for e in historique.get(str(c.get("handle") or "").lower()) or [] if e.get("existe"))
            if vus and vus[0] <= limite:
                crees.add(g)
        for e in historique.get(str(c.get("handle") or "").lower()) or []:
            j = str(e.get("jour", ""))[:10]
            p = int(e.get("posts") or 0) if e.get("existe") else 0
            if not p:
                continue
            if j == jour_scan:
                par_crea.setdefault(crea, {"hier": 0, "j7": 0})["hier"] += p
                par_clipper[g] = par_clipper.get(g, 0) + p
            if depuis7 <= j <= jour_scan:
                par_crea.setdefault(crea, {"hier": 0, "j7": 0})["j7"] += p
            if depuis_s <= j <= jour_scan:
                recents.add(g)
    for crea in groupes:
        par_crea.setdefault(crea, {"hier": 0, "j7": 0})
    silencieux = sorted(g for g in crees if g not in recents)
    return {"par": par_crea, "clippers": par_clipper, "silencieux": silencieux, "publie": len(par_clipper)}


# ------------------------------------------------------------------ Metricool (optionnel)
async def metricool(hier: date) -> dict:
    """{créatrice: {posts, vues}} pour hier, ou {} sans clé / en panne."""
    if not (METRICOOL_API_KEY and METRICOOL_USER_ID):
        return {}
    base, entetes = "https://app.metricool.com/api", {"X-Mc-Auth": METRICOOL_API_KEY, "Accept": "application/json"}
    out = {}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
            async with s.get(f"{base}/admin/simpleProfiles", params={"userId": METRICOOL_USER_ID}, headers=entetes) as r:
                if r.status != 200:
                    journal.warning("Metricool %s sur simpleProfiles", r.status); return {}
                marques = await r.json(content_type=None)
            for m in marques or []:
                crea = str(m.get("label") or "").split()[0] if str(m.get("label") or "").strip() else "?"
                params = {"userId": METRICOOL_USER_ID, "blogId": str(m.get("id")), "from": f"{hier.isoformat()}T00:00:00", "to": f"{hier.isoformat()}T23:59:59"}
                await asyncio.sleep(0.5)
                async with s.get(f"{base}/v2/analytics/brand-summary/posts", params=params, headers=entetes) as r:
                    if r.status != 200:
                        continue
                    rep = await r.json(content_type=None)
                posts = rep if isinstance(rep, list) else (rep.get("data") or [])
                agg = out.setdefault(crea, {"posts": 0, "vues": 0})
                agg["posts"] += len(posts)
                agg["vues"] += sum(int((p.get("metrics") or {}).get("VIEWS") or (p.get("metrics") or {}).get("IMPRESSIONS") or 0) for p in posts)
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Metricool : %s", erreur)
    return out


# ------------------------------------------------------------------ le texte
def _k(n: int) -> str:
    return f"{n / 1000:.1f} k".replace(".0 k", " k").replace(".", ",") if n >= 10_000 else _nb(n)


def composer(hier: date, subs: dict, vis: dict, rl: dict, mc: dict, effectif: int, creatrices: list) -> str:
    """Huit lignes, la veille. Les créatrices dans l'ordre du roster ; chiffres à zéro affichés (un zéro dit quelque chose)."""
    t = subs.get("tot") or {}
    lignes = [f"📊 **{JOURS[hier.weekday()]} {hier.strftime('%d/%m')}** — la veille en 8 lignes"]
    non_saisis = list(subs.get("non_saisis") or [])
    if subs.get("par"):
        par_sub = (t["eur7"] / t["subs7"]) if t["subs7"] else 0
        sept = f"7 j : {_nb(t['subs7'])} subs{_delta(_pct(t['subs7'], t['subs7_avant']))}, {_nb(t['eur7'])} €, {par_sub:.1f} €/sub".replace(".", ",")
        saisis = [(c, v) for c, v in sorted(subs["par"].items(), key=lambda kv: -kv[1]["subs"]) if c not in non_saisis]
        if not saisis:                                                      # rien de saisi pour hier : on le dit, sans zéros trompeurs
            lignes.append(f"💰 **Hier pas encore saisi** · {sept}")
        else:
            ca = t["of_usd"] * TAUX_USD_EUR + t["mym_eur"]
            lignes.append(f"💰 **{_nb(t['subs'])} subs · {_nb(t['of_usd'])} $ OF · {_nb(t['mym_eur'])} € MYM** ({_nb(ca)} €) · {sept}")
            lignes.append("   " + " · ".join(f"{c} {_nb(v['subs'])}" for c, v in saisis))
    else:
        lignes.append("💰 Subs et CA : classeur Data G&M non lu (DATA_GM_ID).")
    vp, vt = vis["par"], sum(v["hier"] for v in vis["par"].values())
    v7 = sum(v["j7"] for v in vis["par"].values())
    lignes.append(f"🔗 **{_nb(vt)} visites payables** (7 j : {_nb(v7)}) · "
                  + " · ".join(f"{c} {_nb(vp[c]['hier'])}" for c in creatrices if c in vp))
    rp, rt = rl["par"], sum(v["hier"] for v in rl["par"].values())
    r7 = sum(v["j7"] for v in rl["par"].values())
    lignes.append(f"🎬 **{_nb(rt)} Reels** (7 j : {_nb(r7)}) · {rl['publie']} clipper(s) sur {effectif} ont publié · "
                  + " · ".join(f"{c} {_nb(rp[c]['hier'])}" for c in creatrices if c in rp))
    top = [(p, v) for p, v in vis["clippers"] if v > 0][:5]
    if top:
        lignes.append("🏆 " + " · ".join(f"{p} {_nb(v)}" for p, v in top))
    if rl["silencieux"]:
        noms = [s.capitalize() for s in rl["silencieux"]]
        lignes.append(f"😴 Sans Reel depuis {JOURS_SILENCE} j : " + ", ".join(noms[:8]) + (f" +{len(noms) - 8}" if len(noms) > 8 else ""))
    if mc:
        posts, vues = sum(v["posts"] for v in mc.values()), sum(v["vues"] for v in mc.values())
        ordre = sorted(((c, v) for c, v in mc.items() if v["posts"] or v["vues"]), key=lambda kv: -kv[1]["vues"])
        absentes = [c for c in creatrices if c not in mc]
        lignes.append(f"📱 Metricool : {_nb(posts)} posts · {_k(vues)} vues · " + " · ".join(f"{c} {_k(v['vues'])}" for c, v in ordre[:4])
                      + (f" · absente : {', '.join(absentes)}" if absentes else ""))
    if non_saisis and subs.get("par"):
        if len(non_saisis) >= len(subs["par"]):
            lignes.append("⚠️ Saisie d'hier manquante pour toutes les créatrices (Rianah)")
        else:
            lignes.append("⚠️ Non saisi hier : " + ", ".join(non_saisis) + " (Rianah)")
    return "\n".join(lignes)


async def executer(maintenant=None) -> str:
    """Compose le rapport de la veille ; les sources qui manquent ne bloquent pas les autres."""
    maintenant = maintenant or _deps["heure_paris"]()
    hier = (maintenant.date() if hasattr(maintenant, "date") else maintenant) - timedelta(days=1)
    groupes = _deps["groupes"]() if _deps.get("groupes") else {}
    exclus = _deps["exclus"]() if _deps.get("exclus") else []
    creatrices = list(groupes)
    ex = {_n(x) for x in exclus}
    effectif = sum(1 for noms in groupes.values() for p in noms if _n(p) not in ex)
    try:
        subs = bloc_subs(await data_gm(hier + timedelta(days=1)), hier)
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Rapport : Data G&M (%s)", erreur); subs = {}
    vis = visites(groupes, exclus, _deps.get("clics_de"))
    try:
        comptes = await _deps["lire_comptes"]() if _deps.get("lire_comptes") else []
        etat = _deps["lire_json"](_deps["FICHIER_ETATS"], {}) if _deps.get("FICHIER_ETATS") else {}
        jour_scan = str(etat.get("dernier") or (hier + timedelta(days=1)).isoformat())[:10]
        rl = reels(comptes, etat.get("historique") or {}, jour_scan, groupes, exclus)
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Rapport : Reels (%s)", erreur); rl = {"par": {}, "clippers": {}, "silencieux": [], "publie": 0}
    mc = await metricool(hier)
    return composer(hier, subs, vis, rl, mc, effectif, creatrices)


async def envoyer(texte: str):
    canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
    if canal is not None:
        await canal.send(texte[:1990])
    if _deps.get("envoyer_telegram"):
        try:
            await _deps["envoyer_telegram"](texte)
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Rapport : Telegram (%s)", erreur)


async def boucle(client):
    """Chaque jour à HEURE_PARIS (13 h : Rianah a saisi la veille), une fois."""
    if not ACTIF:
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            d = _deps["lire_json"](_deps["FICHIER"], {})
            if maintenant.hour >= HEURE_PARIS and d.get("dernier") != jour:
                texte = await executer(maintenant)
                await envoyer(texte)
                d["dernier"] = jour; _deps["ecrire_json"](_deps["FICHIER"], d)
                journal.info("Rapport quotidien envoyé (%s)", jour)
        except Exception as erreur:                                         # noqa: BLE001
            journal.exception("Rapport quotidien : %s", erreur)
        await asyncio.sleep(600)


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith("!rapport"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    try:
        rapport = await executer()
        await message.channel.send(rapport[:1990])
        if "telegram" in texte.lower() and _deps.get("envoyer_telegram"):
            await _deps["envoyer_telegram"](rapport)
            await message.reply("📨 Envoyé sur Telegram aussi.")
    except Exception as erreur:                                             # noqa: BLE001
        journal.exception("!rapport : %s", erreur)
        await message.reply(f"❌ Rapport : {type(erreur).__name__} {str(erreur)[:120]}")
    return True
