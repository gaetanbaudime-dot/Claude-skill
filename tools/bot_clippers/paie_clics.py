"""Paie au clic (machine horizontale v2, décision de Gaëtan des 22-23/09/2026).

Le clipper est payé TAUX_CLIC dollars (0,05 $ par défaut) par visite réelle sur son lien GetAllMyLinks :
visiteurs francophones (PAYS_PAYES : France, Belgique, Suisse, Canada, DOM-TOM… par défaut), robots exclus par GAML. Ce module :

  - lit chaque jour les relevés de tous les liens attribués (deux appels par lien et par jour :
    pays hors robots, total avec robots) et les range dans clics.json sur le volume ;
  - envoie chaque matin, dans le salon perso de chaque clipper, sa ligne de la veille ;
  - répond à `!mesclics` (le clipper ne voit que lui) et `!wallet` (son adresse de paiement) ;
  - donne aux managers `!clics`, `!liens`, `!lien @clipper …` (attribuer ou cloner un lien) et
    `!paie-clics 5|20 [AAAA-MM]` : la liste adresse-montant de la paie du 5 (16 → fin du mois
    précédent) ou du 20 (1 → 15 du mois), avec le CSV. Le virement reste humain.

Le module ne connaît pas bot_discord : il reçoit ses dépendances dans `demarrer(client, deps)`.
Sans GAML_API_KEY, tout est inactif et les commandes le disent.
"""

import asyncio
import csv
import io
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

import aiohttp
import discord

journal = logging.getLogger("clics")

GAML_API_KEY = os.environ.get("GAML_API_KEY", "").strip()
TAUX_CLIC = float(os.environ.get("TAUX_CLIC", "0.05") or 0.05)
# Visiteurs FRANCOPHONES (précision de Gaëtan, 23/09) : la zone qui paie sur OnlyFans/MYM. Noms tels que GAML les renvoie.
# Le Maghreb et l'Afrique francophone (pays des clippers eux-mêmes) restent exclus par défaut : PAYS_PAYES pour changer.
PAYS_PAYES_DEFAUT = ("France,Belgium,Switzerland,Canada,Luxembourg,Monaco,Réunion,Guadeloupe,Martinique,French Guiana,"
                     "Mayotte,New Caledonia,French Polynesia")
PAYS_PAYES = [p.strip() for p in os.environ.get("PAYS_PAYES", PAYS_PAYES_DEFAUT).split(",") if p.strip()]
PAYS_LIBELLE = os.environ.get("PAYS_LIBELLE", "francophones").strip() or "francophones"
CLICS_DEPUIS = os.environ.get("CLICS_DEPUIS", "2026-09-16").strip()          # début du relevé rétroactif
CLICS_HEURE = int(os.environ.get("CLICS_HEURE", "7") or 7)                    # ligne du matin (heure de Paris)
# 25/09 : les anciens clippers gardent leur fixe deux semaines, puis clic ou sortie. Le bilan part tout seul ce jour-là.
BILAN_FIXE_DATE = os.environ.get("BILAN_FIXE_DATE", "2026-10-09").strip()
BILAN_FIXE_JOURS = int(os.environ.get("BILAN_FIXE_JOURS", "14") or 14)
SEUIL_FIXE_100 = int(os.environ.get("SEUIL_FIXE_100", "32") or 32)            # visites payables/jour qui rentabilisent 100 €
SEUIL_FIXE_200 = int(os.environ.get("SEUIL_FIXE_200", "65") or 65)            # … et 200 € (0,30 $ de CA par visite, 35 % de marge)
CLICS_EXCLURE = {p.strip().lower() for p in os.environ.get("CLICS_EXCLURE", "rianah,gaetan,gaëtan,jonas,x,y").split(",") if p.strip()}
API = "https://getallmylinks.com/api/v1"
FUSEAU = "Europe/Paris"

_deps = {}
_client = None
_session = None
_verrou = asyncio.Lock()
_limite = {"restant": 60, "reset": 0.0}


def actif() -> bool:
    return bool(GAML_API_KEY)


# ------------------------------------------------------------------ données
def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_CLICS"], {})
    d.setdefault("liens", {}); d.setdefault("jours", {}); d.setdefault("wallets", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_CLICS"], d)


def _aujourdhui() -> date:
    return _deps["heure_paris"]().date()


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def _usd(x) -> str:
    return f"{x:,.2f} $".replace(",", " ").replace(".", ",")


def _jour(s: str) -> date:
    return date.fromisoformat(s)


# ------------------------------------------------------------------ API GAML
async def _requete(methode: str, chemin: str, params=None, corps=None):
    """Appel GAML avec respect de la limite (60/min) et une reprise sur 429 / 5xx."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))
    entetes = {"X-Api-Key": GAML_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}
    for essai in range(3):
        async with _verrou:
            if _limite["restant"] <= 2 and _limite["reset"] > time.time():
                await asyncio.sleep(min(70, _limite["reset"] - time.time() + 1))
        try:
            async with _session.request(methode, f"{API}{chemin}", params=params, json=corps, headers=entetes) as r:
                try:
                    _limite["restant"] = int(r.headers.get("X-RateLimit-Remaining", 60))
                    _limite["reset"] = float(r.headers.get("X-RateLimit-Reset", 0))
                except ValueError:
                    pass
                if r.status == 429 or r.status >= 500:
                    await asyncio.sleep(5 * (essai + 1) if r.status >= 500 else max(2.0, _limite["reset"] - time.time() + 1))
                    continue
                if r.status >= 400:
                    texte = await r.text()
                    raise RuntimeError(f"GAML {r.status} sur {chemin} : {texte[:200]}")
                return await r.json(content_type=None)
        except aiohttp.ClientError as erreur:
            if essai == 2:
                raise RuntimeError(f"GAML injoignable ({type(erreur).__name__})") from erreur
            await asyncio.sleep(3 * (essai + 1))
    raise RuntimeError(f"GAML : trop de tentatives sur {chemin}")


async def liens_gaml() -> list:
    return await _requete("GET", "/links")


async def releve(link_id: str, jour: date) -> dict:
    """Relevé d'un lien pour un jour (heure de Paris) : brut (robots inclus), hors robots, payés."""
    base = {"link_id": link_id, "range": "custom", "date_from": jour.isoformat(), "date_to": jour.isoformat(),
            "timezone": FUSEAU}
    pays = await _requete("GET", "/analytics/countries", params=base)
    pays = pays if isinstance(pays, list) else pays.get("member", [])
    hors_robots = sum(int(x.get("count", 0)) for x in pays)
    payes = sum(int(x.get("count", 0)) for x in pays if str(x.get("country", "")) in PAYS_PAYES)
    avec = await _requete("GET", "/analytics/visitors", params={**base, "hide_bots": "false"})
    avec = avec if isinstance(avec, list) else avec.get("member", [])
    brut = sum(int(x.get("totalVisits", 0)) for x in avec)
    return {"brut": brut, "hors_robots": hors_robots, "payes": payes}


async def cloner_lien(base_id: str, nom: str, note: str) -> dict:
    """Clone un lien GAML (même boutons, même design), le renomme, l'active. Renvoie {id, url}."""
    clone = await _requete("POST", f"/links/{base_id}/clone")
    nouveau_id = clone.get("id")
    if not nouveau_id:
        raise RuntimeError("clone GAML sans identifiant")
    maj = await _requete("PATCH", f"/links/{nouveau_id}", corps={"name": nom, "note": note, "enabled": True})
    return {"id": nouveau_id, "url": maj.get("url") or clone.get("url") or ""}


# ------------------------------------------------------------------ calculs
def periode(cle: str, mois: str = "") -> tuple:
    """`5` : 16 → fin du mois précédent (paie du 5 de `mois`) ; `20` : 1 → 15 de `mois`."""
    ref = _aujourdhui()
    if mois:
        annee, m = int(mois[:4]), int(mois[5:7])
    else:
        annee, m = ref.year, ref.month
    if cle == "20":
        return date(annee, m, 1), date(annee, m, 15)
    fin = date(annee, m, 1) - timedelta(days=1)
    return date(fin.year, fin.month, 16), fin


def periode_en_cours() -> tuple:
    ref = _aujourdhui()
    if ref.day <= 15:
        return date(ref.year, ref.month, 1), date(ref.year, ref.month, 15)
    fin = (date(ref.year, ref.month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return date(ref.year, ref.month, 16), fin


def regime(uid: str) -> str:
    """« clic » ou « fixe ». Décision du 23/09 : les clippers déjà signés gardent leur fixe, tout nouveau signé
    passe au clic (le handler J'ACCEPTE pose `paie: clic`). `!paie @clipper clic|fixe` pour changer à la main."""
    fiche = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(uid), {})
    return fiche.get("paie") or ("clic" if str(fiche.get("date", ""))[:10] >= "2026-09-24" else "fixe")


def liens_de(d: dict, uid: str) -> list:
    return [lid for lid, info in d["liens"].items() if str(info.get("uid")) == str(uid)]


def somme(d: dict, link_ids, debut: date, fin: date) -> dict:
    tot = {"brut": 0, "hors_robots": 0, "payes": 0, "jours": 0}
    for lid in link_ids:
        for j, v in d["jours"].get(lid, {}).items():
            if debut.isoformat() <= j <= fin.isoformat():
                tot["brut"] += v.get("brut", 0); tot["hors_robots"] += v.get("hors_robots", 0)
                tot["payes"] += v.get("payes", 0); tot["jours"] += 1
    return tot


def texte_bilan_fixe(d: dict, jours: int = BILAN_FIXE_JOURS) -> list:
    """Le verdict des clippers encore au fixe : visites payables sur `jours` jours, équivalent au clic, et ce que ça
    dit face au point mort. Décision du 25/09 : deux semaines à l'arrache, puis clic ou sortie, sans distinction
    France / Madagascar / Bénin."""
    hier = _aujourdhui() - timedelta(days=1)
    debut = hier - timedelta(days=jours - 1)
    par_uid = {}
    for lid, info in d["liens"].items():
        if info.get("uid"):
            par_uid.setdefault(str(info["uid"]), []).append(lid)
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None) or f"id {uid}")
    rangs = []
    for uid in registre:
        if regime(uid) != "fixe":
            continue
        s = somme(d, par_uid.get(uid, []), debut, hier)
        rangs.append((nom_de(uid), s, s["payes"] / jours, uid, bool(par_uid.get(uid))))
    rangs.sort(key=lambda r: -r[2])
    lignes = [f"⚖️ **Bilan des fixes** — {jours} jours ({debut.strftime('%d/%m')} → {hier.strftime('%d/%m')}), "
              f"équivalent au clic à {_usd(TAUX_CLIC)} la visite"]
    for nom, s, pj, uid, a_lien in rangs:
        if not a_lien:
            verdict = "⚠️ aucun lien GAML : rien à mesurer, `!lien @clipper nouveau`"
        elif pj >= SEUIL_FIXE_200:
            verdict = "✅ rentable, même à 200 €"
        elif pj >= SEUIL_FIXE_100:
            verdict = "🟡 rentable à 100 € seulement"
        else:
            verdict = "❌ sous le point mort : clic ou sortie"
        lignes.append(f"· {nom} — {_fmt(s['payes'])} visites payables ({_fmt(pj)}/j) = {_usd(s['payes'] * TAUX_CLIC)} au clic · {verdict}")
    if not rangs:
        lignes.append("· plus personne au fixe.")
    lignes.append(f"-# Point mort : ≈ {SEUIL_FIXE_100} visites payables/jour pour 100 €, ≈ {SEUIL_FIXE_200}/jour pour 200 €. "
                  "`!paie @clipper clic` pour basculer · `!sortie @clipper raison` pour sortir · `!bilan-fixe 30` pour un autre horizon.")
    return lignes


async def _envoyer_canal(canal, lignes: list) -> None:
    bloc = ""
    for l in lignes:
        if len(bloc) + len(l) + 1 > 1900:
            await canal.send(bloc)
            bloc = ""
        bloc += l + "\n"
    if bloc.strip():
        await canal.send(bloc)


def texte_mesclics(d: dict, uid: str, nom: str) -> str:
    lids = liens_de(d, uid)
    if not lids:
        return "Tu n'as pas encore de lien. Ton manager te le donne. En attendant, rien n'est compté."
    hier = _aujourdhui() - timedelta(days=1)
    h = somme(d, lids, hier, hier)
    s7 = somme(d, lids, hier - timedelta(days=6), hier)
    debut, fin = periode_en_cours()
    q = somme(d, lids, debut, min(fin, hier))
    part = f" ({h['payes'] * 100 // h['hors_robots']} % de tes visiteurs)" if h["hors_robots"] else ""
    robots = h["brut"] - h["hors_robots"]
    au_clic = regime(uid) == "clic"
    return (f"📊 **Tes visites, {nom}**" + ("" if au_clic else " · tu es au fixe, ces montants sont juste pour info") + "\n\n"
            f"Hier, le {hier.strftime('%d/%m')} : **{_fmt(h['payes'])} visites qui comptent**{part}"
            + (f". {robots} robots enlevés" if robots > 0 else "") + ".\n\n"
            f"Sur 7 jours : **{_fmt(s7['payes'])}** visites qui comptent, sur {_fmt(s7['hors_robots'])} visiteurs.\n\n"
            f"Quinzaine du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')} : **{_fmt(q['payes'])} visites = "
            f"{_usd(q['payes'] * TAUX_CLIC)}**.\n"
            f"Une visite qui compte = {_usd(TAUX_CLIC)}. Elle vient de France ou d'un pays francophone. Ce n'est pas un robot.\n\n"
            + ("" if not au_clic or str(uid) in d["wallets"] else "⚠️ Je n'ai pas ton adresse de paiement. Écris `!wallet 0x…` pour l'USDC, ou `!wallet FR76…` pour un virement.\n\n")
            + "-# Ton lien : " + " · ".join(d["liens"][l].get("url", "") for l in lids))


def ligne_matin(d: dict, uid: str) -> str:
    lids = liens_de(d, uid)
    hier = _aujourdhui() - timedelta(days=1)
    h = somme(d, lids, hier, hier)
    if h["jours"] == 0:
        return ""
    debut, fin = periode_en_cours()
    q = somme(d, lids, debut, min(fin, hier))
    s7 = somme(d, lids, hier - timedelta(days=6), hier)
    au_clic = regime(uid) == "clic"
    montant = (f"= {_usd(q['payes'] * TAUX_CLIC)}" if au_clic else f", soit {_usd(q['payes'] * TAUX_CLIC)} au clic, juste pour info")
    return (f"☀️ **Hier, le {hier.strftime('%d/%m')}** : {_fmt(h['hors_robots'])} visiteurs, dont **{_fmt(h['payes'])} qui comptent**.\n\n"
            f"📆 Quinzaine du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')} : **{_fmt(q['payes'])} visites {montant}**. "
            f"Sur 7 jours : {_fmt(s7['payes'])}, soit {_fmt(s7['payes'] / 7)} par jour.\n\n"
            f"-# Écris `!mesclics` pour le détail" + ("" if not au_clic or str(uid) in d["wallets"] else " · `!wallet` pour ton adresse de paiement"))


def liste_paie(d: dict, nom_de, debut: date, fin: date, jour_paie: str) -> tuple:
    """Lignes Discord + CSV de la paie : un clipper par ligne, visites payées, montant, adresse."""
    par_uid = {}
    for lid, info in d["liens"].items():
        uid = str(info.get("uid") or "")
        if uid:
            par_uid.setdefault(uid, []).append(lid)
    lignes, rangs, total, sans, fixes = [], [], 0.0, 0, []
    for uid, lids in par_uid.items():
        s = somme(d, lids, debut, fin)
        if regime(uid) != "clic":
            fixes.append((nom_de(uid), s["payes"]))
            continue
        if s["payes"] == 0:
            continue
        montant = round(s["payes"] * TAUX_CLIC, 2); total += montant
        w = d["wallets"].get(uid, {}).get("adresse", "")
        if not w:
            sans += 1
        rangs.append((nom_de(uid), uid, s["payes"], s["hors_robots"], montant, w))
    rangs.sort(key=lambda r: -r[4])
    for nom, uid, payes, hors, montant, w in rangs:
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else (w or "⚠️ adresse manquante")
        lignes.append(f"· {nom} — {_fmt(payes)} payées ({_fmt(hors)} visiteurs) → **{_usd(montant)}** → {adr}")
    tampon = io.StringIO(); ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["prenom", "discord_id", "visites_payees", "visiteurs_hors_robots", "montant_usd", "adresse"])
    for nom, uid, payes, hors, montant, w in rangs:
        ecrivain.writerow([nom, uid, payes, hors, f"{montant:.2f}".replace(".", ","), w])
    entete = (f"💸 **Paie au clic du {jour_paie}** — période {debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}, "
              f"{_usd(TAUX_CLIC)} la visite payée ({PAYS_LIBELLE}, hors robots)")
    pied = (f"**Total : {_usd(total)}** · {len(rangs)} clipper(s) au clic" + (f" · ⚠️ {sans} sans adresse" if sans else "")
            + "\n-# Le virement reste à faire à la main (Binance / banque). Le CSV est joint.")
    if fixes:
        fixes.sort(key=lambda f: -f[1])
        pied += ("\n\n🧾 **Au fixe, hors liste** (ce qu'ils auraient touché au clic) : "
                 + " · ".join(f"{n} {_fmt(v)} = {_usd(v * TAUX_CLIC)}" for n, v in fixes))
    return [entete] + (lignes or ["· (aucune visite payée sur la période)"]) + [pied], tampon.getvalue()


# ------------------------------------------------------------------ attribution automatique
def _prenom_note(note: str) -> str:
    m = re.match(r"\s*clipping\s+(.+)$", str(note or ""), re.I)
    return m.group(1).strip() if m else ""


async def associer_auto(d: dict, liens: list) -> list:
    """Les liens « Clipping Prénom » non attribués → le membre signé du même prénom (et de la même
    créatrice si possible). Un seul candidat, sinon on laisse `!lien`. Renvoie les lignes à journaliser."""
    normaliser = _deps["normaliser"]
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    deja = {lid for lid, info in d["liens"].items() if info.get("uid")}
    lignes = []
    for l in liens:
        lid, prenom = l.get("id"), _prenom_note(l.get("note"))
        if not lid or lid in deja or not prenom or normaliser(prenom) in CLICS_EXCLURE or len(prenom) < 3:
            continue
        creatrice = str(l.get("name", "")).split()[0] if l.get("name") else ""
        candidats = []
        for uid, fiche in registre.items():
            m = _deps["membre_par_id"](uid)
            if m is None or not (fiche.get("equipe") or fiche.get("creatrice")):
                continue
            if normaliser(m.display_name.split()[0] if m.display_name.split() else "") != normaliser(prenom):
                continue
            candidats.append((uid, normaliser(fiche.get("creatrice") or "") == normaliser(creatrice)))
        if not candidats:
            continue
        surs = [c for c in candidats if c[1]] or (candidats if len(candidats) == 1 else [])
        if len(surs) != 1:
            lignes.append(f"⚠️ {l.get('note')} ({creatrice}) : {len(candidats)} membres possibles, à trancher avec `!lien`.")
            journal.info("Lien GAML %s (%s) : %s candidats, non attribué", l.get("note"), creatrice, len(candidats))
            continue
        uid = surs[0][0]
        d["liens"][lid] = {"uid": uid, "note": l.get("note"), "url": l.get("url"), "creatrice": creatrice,
                           "depuis": max(CLICS_DEPUIS, str(l.get("createdAt", ""))[:10] or CLICS_DEPUIS), "par": "auto"}
        lignes.append(f"🔗 {l.get('note')} ({creatrice}) → <@{uid}>")
        journal.info("Lien GAML %s (%s) → membre %s", l.get("note"), creatrice, uid)
    return lignes


# ------------------------------------------------------------------ relevés et ligne du matin
async def rattraper(d: dict, limite_appels: int = 110) -> int:
    """Complète les jours manquants (depuis `depuis`, jusqu'à hier) pour chaque lien attribué.
    Borné par appel pour respecter la limite GAML ; la boucle repasse un quart d'heure plus tard."""
    hier = _aujourdhui() - timedelta(days=1)
    appels = 0
    for lid, info in list(d["liens"].items()):
        if not (info.get("uid") or info.get("suivi")):
            continue
        debut = max(_jour(info.get("depuis") or CLICS_DEPUIS), hier - timedelta(days=45))
        jours = d["jours"].setdefault(lid, {})
        j = hier
        while j >= debut and appels < limite_appels:
            if j.isoformat() not in jours:
                try:
                    jours[j.isoformat()] = await releve(lid, j)
                except RuntimeError as erreur:
                    journal.warning("Relevé %s %s : %s", info.get("note"), j, erreur)
                    if "404" in str(erreur):
                        jours[j.isoformat()] = {"brut": 0, "hors_robots": 0, "payes": 0, "erreur": "404"}
                    else:
                        return appels
                appels += 2
                _ecrire(d)
            j -= timedelta(days=1)
        if appels >= limite_appels:
            break
    return appels


async def envoyer_lignes_matin(d: dict) -> int:
    envoyes = 0
    salon_de = _deps["salon_perso"]
    for uid in {str(info.get("uid")) for info in d["liens"].values() if info.get("uid")}:
        texte = ligne_matin(d, uid)
        salon = salon_de(uid) if texte else None
        if salon is None:
            journal.info("Ligne du matin %s : %s", uid, "pas de relevé d'hier" if not texte else "salon perso introuvable ou fermé au bot")
            continue
        try:
            await salon.send(texte)
            envoyes += 1
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Ligne du matin %s : %s", uid, erreur)
    return envoyes


async def annoncer_paie(client, d: dict, maintenant) -> None:
    """Jour de paie (5 : période 16 → fin du mois précédent ; 20 : 1 → 15) : la liste et le CSV au salon admin,
    et dans le salon perso de chaque clipper au clic sa ligne (visites payées, montant, adresse)."""
    cle = "5" if maintenant.day == 5 else "20"
    debut, fin = periode(cle, maintenant.strftime("%Y-%m"))
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None) or f"id {uid}")
    lignes, csv_texte = liste_paie(d, nom_de, debut, fin, maintenant.strftime("%d/%m"))
    canal = await _deps["canal_admin"]()
    if canal is not None:
        try:
            await canal.send("\n".join(lignes)[:1990], file=discord.File(io.BytesIO(csv_texte.encode("utf-8-sig")),
                                                                        filename=f"paie_clics_{debut.isoformat()}_{fin.isoformat()}.csv"))
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Annonce de paie (admin) : %s", erreur)
    envoyes = 0
    for uid in {str(i.get("uid")) for i in d["liens"].values() if i.get("uid")}:
        if regime(uid) != "clic":
            continue
        s = somme(d, liens_de(d, uid), debut, fin)
        salon = _deps["salon_perso"](uid)
        if salon is None:
            continue
        w = d["wallets"].get(uid, {}).get("adresse", "")
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else w
        texte = (f"💸 **Ta paie du {maintenant.strftime('%d/%m')}** (période {debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}) : "
                 f"**{_fmt(s['payes'])} visites payées = {_usd(s['payes'] * TAUX_CLIC)}**"
                 + (f" → virement vers {adr} dans la journée." if w else " → ⚠️ pas d'adresse enregistrée : `!wallet 0x…` ou `!wallet FR76…` maintenant, sinon la paie attend la prochaine."))
        try:
            await salon.send(texte)
            envoyes += 1
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Ligne de paie %s : %s", uid, erreur)
    journal.info("Paie du %s annoncée : liste au salon admin, %s ligne(s) en salon perso", maintenant.strftime("%d/%m"), envoyes)


async def boucle(client, deps: dict):
    global _client, _deps
    _client, _deps = client, deps
    await client.wait_until_ready()
    if not actif():
        journal.info("Paie au clic inactive (GAML_API_KEY absente)")
        return
    journal.info("Paie au clic active : %s $ la visite (%s), relevés depuis %s", TAUX_CLIC, "/".join(PAYS_PAYES), CLICS_DEPUIS)
    derniere_assoc = 0.0
    while not client.is_closed():
        try:
            d = _lire()
            if time.time() - derniere_assoc > 3600:
                liens_tous = await liens_gaml()
                lignes = await associer_auto(d, liens_tous)
                if _deps.get("associer_suivi") and _deps["associer_suivi"](d, liens_tous):
                    _ecrire(d)
                derniere_assoc = time.time()
                if lignes:
                    _ecrire(d)
                    canal = await _deps["canal_admin"]()
                    if canal:
                        await canal.send("🔗 **Liens GAML attribués automatiquement**\n" + "\n".join(lignes)[:1800])
            appels = await rattraper(d)
            if appels:
                journal.info("Relevés GAML : %s appels ce passage", appels)
            maintenant = _deps["heure_paris"]()
            aujourdhui = maintenant.date().isoformat()
            hier_iso = (maintenant.date() - timedelta(days=1)).isoformat()
            complets = all(hier_iso in d["jours"].get(lid, {}) for lid, i in d["liens"].items() if i.get("uid"))
            if maintenant.hour >= CLICS_HEURE and d.get("matin") != aujourdhui and complets:
                n = await envoyer_lignes_matin(d)
                d["matin"] = aujourdhui
                _ecrire(d)
                journal.info("Lignes du matin envoyées : %s", n)
            if maintenant.day in (5, 20) and maintenant.hour >= CLICS_HEURE and d.get("paie_annoncee") != aujourdhui and complets:
                await annoncer_paie(client, d, maintenant)
                d["paie_annoncee"] = aujourdhui
                _ecrire(d)
            if (BILAN_FIXE_DATE and aujourdhui >= BILAN_FIXE_DATE and d.get("bilan_fixe") != BILAN_FIXE_DATE
                    and maintenant.hour >= CLICS_HEURE and complets):        # 25/09 : le verdict des deux semaines, une fois
                canal = await _deps["canal_admin"]()
                if canal:
                    await _envoyer_canal(canal, ["📅 **Les deux semaines sont passées** (décision du 25/09) : le verdict des "
                                                 "fixes, à trancher aujourd'hui."] + texte_bilan_fixe(d))
                d["bilan_fixe"] = BILAN_FIXE_DATE
                _ecrire(d)
            if _deps.get("apres_releves"):
                await _deps["apres_releves"](client, d)
            journal.info("État clics : %s liens attribués, %s suivis, relevés d'hier %s, matin %s, rapport %s",
                         sum(1 for i in d["liens"].values() if i.get("uid")), sum(1 for i in d["liens"].values() if i.get("suivi")),
                         "complets" if complets else "en cours", d.get("matin", "-"), d.get("rapport_jonas", "-"))
        except Exception as erreur:                                  # la boucle ne meurt jamais
            journal.warning("Boucle clics : %s", erreur)
        await asyncio.sleep(900)


# ------------------------------------------------------------------ commandes
_ADRESSE_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")
_IBAN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def _adresse_valide(brut: str) -> str:
    a = brut.strip().replace(" ", "")
    if _ADRESSE_EVM.match(a):
        return a
    if _IBAN.match(a.upper()):
        return a.upper()
    return ""


async def commande_clipper(message, texte: str) -> bool:
    """`!mesclics` et `!wallet <adresse>` : pour le clipper lui-même (MP ou salon)."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!mesclics", "!wallet"):
        return False
    if not actif():
        await message.reply("La paie au clic n'est pas encore branchée (clé GAML absente).")
        return True
    d = _lire(); uid = str(message.author.id)
    if mots[0].lower() == "!mesclics":
        await message.reply(texte_mesclics(d, uid, message.author.display_name)[:1990])
        return True
    if len(mots) < 2:
        actuelle = d["wallets"].get(uid, {}).get("adresse", "")
        await message.reply(("Adresse enregistrée : `" + actuelle + "`\n\n" if actuelle else "Aucune adresse enregistrée.\n\n")
                            + "Pour la poser ou la changer : `!wallet 0x…` (USDC sur Ethereum / ERC20) ou `!wallet FR76…` (IBAN).")
        return True
    adresse = _adresse_valide(" ".join(mots[1:]))
    if not adresse:
        await message.reply("Adresse non reconnue. USDC ERC20 = `0x` suivi de 40 caractères ; IBAN = `FR76…` sans fautes.")
        return True
    d["wallets"][uid] = {"adresse": adresse, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "type": "usdc" if adresse.startswith("0x") else "iban"}
    _ecrire(d)
    await message.reply(f"✅ Adresse enregistrée : `{adresse}`. C'est elle qui sera sur la liste de paie du 5 et du 20.")
    return True


async def commande_staff(message, texte: str) -> bool:
    """Managers et admins : `!clics`, `!liens`, `!lien @clipper …`, `!wallet @clipper adresse`, `!paie-clics`."""
    mots = texte.split()
    if not mots:
        return False
    cmd = mots[0].lower()
    if cmd not in ("!clics", "!liens", "!lien", "!paie-clics", "!wallet", "!paie", "!bilan-fixe"):
        return False
    if cmd == "!paie":
        if not message.mentions or not mots[-1].lower() in ("clic", "fixe"):
            await message.reply("Format : `!paie @clipper clic` (payé sur la liste du 5 et du 20) ou `!paie @clipper fixe` (ancien modèle).")
            return True
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        fiche = registre.setdefault(str(message.mentions[0].id), {})
        fiche["paie"] = mots[-1].lower(); fiche["paie_par"] = str(message.author.id)
        _deps["ecrire_json"](_deps["FICHIER_EQUIPES"], registre)
        await message.reply(f"✅ {message.mentions[0].display_name} → paie **{fiche['paie']}**.")
        return True
    if cmd == "!wallet" and not message.mentions:
        return False                                              # `!wallet 0x…` sans mention = la sienne
    if not actif():
        await message.reply("Paie au clic inactive : pose `GAML_API_KEY` dans Railway.")
        return True
    d = _lire()
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None) or f"id {uid}")

    if cmd == "!wallet":
        membre = message.mentions[0]
        adresse = _adresse_valide(" ".join(m for m in mots[1:] if not m.startswith("<@")))
        if not adresse:
            await message.reply("Format : `!wallet @clipper 0x…` ou `!wallet @clipper FR76…`.")
            return True
        d["wallets"][str(membre.id)] = {"adresse": adresse, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                        "type": "usdc" if adresse.startswith("0x") else "iban", "par": str(message.author.id)}
        _ecrire(d)
        await message.reply(f"✅ Adresse de {membre.display_name} enregistrée : `{adresse}`.")
        return True

    if cmd == "!paie-clics":
        args = [m for m in mots[1:]]
        cle = next((a for a in args if a in ("5", "20")), "")
        mois = next((a for a in args if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", a)), "")
        if not cle:
            ref = _aujourdhui()
            cle = "5" if ref.day <= 12 or ref.day >= 28 else "20"      # la prochaine paie
            if ref.day >= 28:
                suivant = (ref.replace(day=1) + timedelta(days=32))
                mois = mois or suivant.strftime("%Y-%m")
        debut, fin = periode(cle, mois)
        jour_paie = f"{cle.rjust(2, '0')}/{(mois or (fin + timedelta(days=1)).strftime('%Y-%m'))[5:7]}"
        lignes, csv_texte = liste_paie(d, nom_de, debut, fin, jour_paie)
        manquants = [lid for lid, i in d["liens"].items() if i.get("uid")
                     and any(j.isoformat() not in d["jours"].get(lid, {}) for j in
                             (debut + timedelta(days=k) for k in range((min(fin, _aujourdhui() - timedelta(days=1)) - debut).days + 1)))]
        if manquants:
            lignes.append(f"⚠️ {len(manquants)} lien(s) avec des jours non relevés sur la période (relevé en cours, relance dans 15 min).")
        fichier = discord.File(io.BytesIO(csv_texte.encode("utf-8-sig")), filename=f"paie_clics_{debut.isoformat()}_{fin.isoformat()}.csv")
        await message.reply("\n".join(lignes)[:1990], file=fichier)
        return True

    if cmd == "!bilan-fixe":
        jours = next((int(m) for m in mots[1:] if m.isdigit() and 1 <= int(m) <= 90), BILAN_FIXE_JOURS)
        await _deps["envoyer_long"](message, texte_bilan_fixe(d, jours))
        return True

    if cmd == "!clics":
        hier = _aujourdhui() - timedelta(days=1)
        debut, fin = periode_en_cours()
        lignes = [f"📊 **Clics par clipper** — hier {hier.strftime('%d/%m')} · 7 jours · quinzaine "
                  f"({debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}) à {_usd(TAUX_CLIC)}"]
        par_uid = {}
        for lid, info in d["liens"].items():
            if info.get("uid"):
                par_uid.setdefault(str(info["uid"]), []).append(lid)
        rangs = []
        for uid, lids in par_uid.items():
            h = somme(d, lids, hier, hier); s7 = somme(d, lids, hier - timedelta(days=6), hier)
            q = somme(d, lids, debut, min(fin, hier))
            rangs.append((nom_de(uid), h, s7, q, uid))
        rangs.sort(key=lambda r: -r[2]["payes"])
        for nom, h, s7, q, uid in rangs:
            part = f"{s7['payes'] * 100 // s7['hors_robots']} %" if s7["hors_robots"] else "–"
            reg = regime(uid)
            lignes.append(f"· {nom} [{reg}] — hier {_fmt(h['payes'])} · 7 j {_fmt(s7['payes'])} ({part} payables, "
                          f"{_fmt(s7['payes'] / 7)}/j) · quinzaine {_fmt(q['payes'])} = {_usd(q['payes'] * TAUX_CLIC)}"
                          + ("" if reg != "clic" or uid in d["wallets"] else " · ⚠️ sans adresse"))
        lignes.append("-# [fixe] = ancien modèle (grille + 0,50 €/abonné), [clic] = payé sur la liste du 5 et du 20. "
                      "`!paie @clipper clic|fixe` pour changer. Repère de rentabilité d'un fixe : ≈ 65 visites payables/jour "
                      "pour 200 €, ≈ 32/jour pour 100 € (0,30 $ de CA par visite, 35 % de marge).")
        if not rangs:
            lignes.append("· aucun lien attribué — `!liens` puis `!lien @clipper …`.")
        await _deps["envoyer_long"](message, lignes)
        return True

    if cmd == "!liens":
        try:
            liens = await liens_gaml()
        except RuntimeError as erreur:
            await message.reply(f"❌ {erreur}")
            return True
        hier = _aujourdhui() - timedelta(days=1)
        lignes = ["🔗 **Liens GAML « Clipping »**"]
        for l in sorted(liens, key=lambda x: (str(x.get("name")), str(x.get("note")))):
            if not _prenom_note(l.get("note")):
                continue
            info = d["liens"].get(l.get("id"), {})
            h = somme(d, [l.get("id")], hier, hier)
            qui = f"→ {nom_de(info['uid'])}" if info.get("uid") else "→ **libre**"
            lignes.append(f"· {str(l.get('name', '')).split()[0]} · {l.get('note')} · <{l.get('url')}> {qui}"
                          + (f" · hier {_fmt(h['payes'])} payées" if info.get("uid") else ""))
        lignes.append("-# `!lien @clipper <url ou slug>` pour attribuer · `!lien @clipper nouveau` pour cloner un lien de sa créatrice · "
                      "`!lien @clipper retirer`")
        await _deps["envoyer_long"](message, lignes)
        return True

    # !lien @clipper [url | slug | nouveau [Créatrice] | retirer]
    if not message.mentions:
        await message.reply("Format : `!lien @clipper <url ou slug GAML>` · `!lien @clipper nouveau [Créatrice]` · "
                            "`!lien @clipper retirer` · `!lien @clipper` pour voir.")
        return True
    membre = message.mentions[0]; uid = str(membre.id)
    reste = [m for m in mots[1:] if not m.startswith("<@")]
    if not reste:
        lids = liens_de(d, uid)
        await message.reply(f"{membre.display_name} → " + (" · ".join(f"<{d['liens'][l].get('url')}>" for l in lids) if lids else "aucun lien")
                            + ("" if uid in d["wallets"] else " · ⚠️ pas d'adresse de paiement"))
        return True
    if reste[0].lower() == "retirer":
        for lid in liens_de(d, uid):
            d["liens"][lid]["uid"] = ""
        _ecrire(d)
        await message.reply(f"✅ Liens de {membre.display_name} détachés (l'historique reste).")
        return True
    try:
        liens = await liens_gaml()
    except RuntimeError as erreur:
        await message.reply(f"❌ {erreur}")
        return True
    prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
    if reste[0].lower() == "nouveau":
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        creatrice = " ".join(reste[1:]).strip() or (registre.get(uid, {}).get("creatrice") or "")
        if not creatrice:
            await message.reply("Pas de créatrice connue pour ce clipper : `!lien @clipper nouveau Chloé`.")
            return True
        normaliser = _deps["normaliser"]
        modeles = [l for l in liens if normaliser(str(l.get("name", "")).split()[0] if l.get("name") else "") == normaliser(creatrice)
                   and _prenom_note(l.get("note"))]
        if not modeles:
            await message.reply(f"Aucun lien « Clipping » de {creatrice} à cloner dans GAML.")
            return True
        base = modeles[0]
        try:
            nouveau = await cloner_lien(base["id"], base.get("name", creatrice), f"Clipping {prenom}")
        except RuntimeError as erreur:
            await message.reply(f"❌ Clonage impossible : {erreur}")
            return True
        d["liens"][nouveau["id"]] = {"uid": uid, "note": f"Clipping {prenom}", "url": nouveau["url"], "creatrice": creatrice,
                                     "depuis": _aujourdhui().isoformat(), "par": str(message.author.id)}
        _ecrire(d)
        await message.reply(f"✅ Lien cloné depuis « {base.get('note')} » et attribué à {membre.display_name} : {nouveau['url']}\n"
                            f"-# Le bouton OnlyFans pointe encore sur la destination du modèle : à changer vers son lien Infloww "
                            f"quand la clé Infloww sera posée.")
        return True
    cible = reste[0].strip().rstrip("/")
    trouve = next((l for l in liens if l.get("id") == cible or str(l.get("url", "")).rstrip("/") == cible
                   or str(l.get("url", "")).rstrip("/").endswith("/" + cible.split("/")[-1])), None)
    if trouve is None:
        await message.reply(f"Lien « {cible} » introuvable dans GAML (`!liens` pour la liste).")
        return True
    d["liens"][trouve["id"]] = {"uid": uid, "note": trouve.get("note"), "url": trouve.get("url"),
                                "creatrice": str(trouve.get("name", "")).split()[0] if trouve.get("name") else "",
                                "depuis": max(CLICS_DEPUIS, str(trouve.get("createdAt", ""))[:10] or CLICS_DEPUIS),
                                "par": str(message.author.id)}
    _ecrire(d)
    await message.reply(f"✅ {trouve.get('url')} ({trouve.get('note')}) → {membre.display_name}. Relevé rétroactif en cours, "
                        f"`!mesclics` pour lui d'ici un quart d'heure.")
    return True
