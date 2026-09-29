"""Le tableau de bord d'une ligne, chaque lundi (27/09, décision de Gaëtan) :
candidats → validés → premier Reel → jour 7 tenu → premier paiement, sur les 7 derniers jours, avec la semaine d'avant
entre parenthèses. Posté dans le salon admin le lundi entre 8 h et 10 h (Paris), une fois par semaine ; `!tableau` à la
demande. La seule décision de recrutement se lit sur « validés → premier Reel », jamais sur le volume de candidatures.

Sources : classeur des candidatures (candidats), pipeline.json (validation), etats_comptes.json (27/09 : le premier jour où les
comptes d'un clipper portent au moins une publication, puis 7 jours dont 5 à 2 publications ou plus, comptées par le scan Apify
quotidien du classeur ; le module inputs_clippers a été retiré le 29/09), paiements.jsonl (`!paiement`) et clics.json
« paies » (listes `!paie-clics`) pour le premier paiement.

29/09 (Gaëtan, GO axe 4 et « on est à combien ? ») : deux lignes de plus. Le délai formulaire → premier Reel (médiane et 80 % en
jours, pour les clippers dont le premier Reel tombe dans la semaine ; formulaire retrouvé par le prénom). Et les trois
déclencheurs pour doubler le recrutement, sur 14 jours : formulaire → quiz réussi (≥ 30 %, le quiz se passe sur le site avant
Discord depuis le 29/09 ; formulaire → Discord affiché à côté), validés → premier Reel (≥ 50 %), clippers livrables par le
classeur ≥ 2 × les validés des 30 derniers jours."""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import discord

journal = __import__("logging").getLogger("bot_clippers")
_deps = {}
ETAPES = ("candidats", "valides", "premier_reel", "jour7", "premier_paiement")
LIBELLES = {"candidats": "Candidats", "valides": "Validés", "premier_reel": "Premier Reel", "jour7": "Jour 7 tenu",
            "premier_paiement": "Premier paiement"}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PIPELINE, inputs_lire (-> dict), JOURNAL_PAIEMENTS (Path),
    paie_lire (-> dict clics.json), lire_candidatures (async -> list), heure_paris, canal_admin, est_staff,
    disponibles (onboarding, 29/09), normaliser."""
    _deps.update(deps)


def _jour(iso) -> date | None:
    if not iso:
        return None
    try:
        if isinstance(iso, datetime):
            return iso.date()
        if isinstance(iso, date):
            return iso
        return datetime.fromisoformat(str(iso)[:19]).date()
    except (TypeError, ValueError):
        try:
            return date.fromisoformat(str(iso)[:10])
        except (TypeError, ValueError):
            return None


def fenetres(ref: date) -> tuple:
    """(début, fin) des 7 derniers jours pleins, puis des 7 d'avant."""
    fin = ref - timedelta(days=1)
    debut = fin - timedelta(days=6)
    return (debut, fin), (debut - timedelta(days=7), debut - timedelta(days=1))


def _compter(dates, fen) -> int:
    return sum(1 for d in dates if d is not None and fen[0] <= d <= fen[1])


def premiers_reels(historique: dict) -> dict:
    """{clipper: (jour du premier Reel, jour 7 tenu ou None)} depuis l'historique des inputs."""
    premiers = {}
    for jour in sorted(historique):
        for clipper, v in (historique.get(jour) or {}).items():
            if clipper not in premiers and (v.get("posts_24h") or 0) >= 1:
                premiers[clipper] = jour
    resultat = {}
    for clipper, j0 in premiers.items():
        d0 = _jour(j0)
        if d0 is None:
            continue
        bons = 0
        for k in range(7):
            v = (historique.get((d0 + timedelta(days=k)).isoformat()) or {}).get(clipper) or {}
            if (v.get("posts_24h") or 0) >= 2:
                bons += 1
        resultat[clipper] = (d0, d0 + timedelta(days=6) if bons >= 5 else None)
    return resultat


def premiers_reels_etats(historique: dict, comptes: list) -> dict:
    """{clipper: (jour du premier Reel, jour 7 tenu ou None)} depuis l'historique d'etats_comptes ({handle: [{jour, existe, posts}]})
    et le classeur (handle → Gérant). Publications d'un jour = somme des posts de ses comptes ; nouveau Reel = hausse d'un jour
    à l'autre (le premier jour compte pour ce qu'il porte)."""
    norm = _deps.get("normaliser") or (lambda t: (t or "").strip().lower())
    gerant = {}
    for c in comptes or []:
        g = str(c.get("gerant") or "").strip()
        if c.get("handle") and g and norm(g) not in ("x", "y", "z", "aaa", "?", "-", "libre", "dispo"):
            gerant[str(c["handle"]).lower()] = g.split()[0]
    totaux = {}
    for handle, entrees in (historique or {}).items():
        g = gerant.get(str(handle).lower())
        if not g:
            continue
        for e in entrees or []:
            if not e.get("existe") or not e.get("jour"):
                continue
            totaux.setdefault(g, {}).setdefault(e["jour"], 0)
            totaux[g][e["jour"]] += int(e.get("posts") or 0)
    resultat = {}
    for g, par_jour in totaux.items():
        j0 = next((j for j in sorted(par_jour) if par_jour[j] >= 1), None)
        d0 = _jour(j0)
        if d0 is None:
            continue
        bons, precedent = 0, None
        for k in range(7):
            j = (d0 + timedelta(days=k)).isoformat()
            if j not in par_jour:
                continue
            delta = par_jour[j] - (precedent if precedent is not None else 0)
            precedent = par_jour[j]
            if delta >= 2:
                bons += 1
        resultat[g] = (d0, d0 + timedelta(days=6) if bons >= 5 else None)
    return resultat


def premiers_paiements() -> dict:
    """{uid: premier jour payé} depuis paiements.jsonl et les listes `!paie-clics` mémorisées dans clics.json."""
    premiers = {}
    chemin = _deps.get("JOURNAL_PAIEMENTS")
    try:
        if chemin is not None and chemin.exists():
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                try:
                    o = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                uid, d = str(o.get("beneficiaire", "")), _jour(o.get("horodatage"))
                if uid and d and (uid not in premiers or d < premiers[uid]):
                    premiers[uid] = d
    except OSError:
        pass
    try:
        for jour, par_uid in ((_deps["paie_lire"]() or {}).get("paies") or {}).items():
            d = _jour(jour)
            for uid, montant in (par_uid or {}).items():
                if d and montant and (uid not in premiers or d < premiers[uid]):
                    premiers[uid] = d
    except Exception:                                                       # noqa: BLE001
        pass
    return premiers


APRES_QUIZ = ("quiz_ok", "test_envoye", "test_rendu", "valide", "refuse", "test_expire")
SEUIL_QUIZ_PCT, SEUIL_REEL_PCT, FACTEUR_COMPTES = 30, 50, 2


def _pct(a: int, b: int) -> int | None:
    return round(100 * a / b) if b else None


def delais_premier_reel(pr: dict, pipe: dict, fen: tuple, debut_scan: date | None) -> list:
    """Jours entre le formulaire et le premier Reel, pour les clippers dont le premier Reel tombe dans `fen`. Le formulaire est
    celui du même prénom le plus récent avant le premier Reel ; un formulaire antérieur au début du scan est écarté (son
    « premier Reel » serait le premier jour du scan, pas le vrai)."""
    norm = _deps.get("normaliser") or (lambda t: (t or "").strip().lower())
    par_prenom = {}
    for c in (pipe.get("candidatures") or {}).values():
        d, pn = _jour(c.get("date")), norm(str(c.get("prenom") or "").split(" ")[0])
        if d and pn:
            par_prenom.setdefault(pn, []).append(d)
    out = []
    for clipper, (d0, _) in pr.items():
        if not (fen[0] <= d0 <= fen[1]):
            continue
        avant = [d for d in par_prenom.get(norm(str(clipper).split(" ")[0]), []) if d <= d0]
        if not avant:
            continue
        df = max(avant)
        if debut_scan and df < debut_scan:
            continue
        out.append((d0 - df).days)
    return sorted(out)


def _quantile(valeurs: list, q: float):
    if not valeurs:
        return None
    k = min(len(valeurs) - 1, max(0, int(round(q * (len(valeurs) - 1)))))
    return valeurs[k]


def entonnoir_site(pipe: dict, debut: date, fin: date) -> dict:
    """Formulaires du site envoyés entre `debut` et `fin` : combien sont arrivés sur Discord (numéro relié), combien ont
    réussi le quiz (sur le site avant Discord, ou sur Discord)."""
    uid_de_tel = {str(l.get("tel")): uid for uid, l in (pipe.get("liaisons") or {}).items() if l.get("tel")}
    etats = pipe.get("etats") or {}
    n = arrives = quiz = 0
    for c in (pipe.get("candidatures_web") or {}).values():
        d = _jour(c.get("date"))
        if not d or not (debut <= d <= fin):
            continue
        n += 1
        uid = uid_de_tel.get(str(c.get("tel")))
        arrives += 1 if uid else 0
        if (c.get("quiz") or {}).get("reussi") or (uid and (etats.get(uid) or {}).get("etat") in APRES_QUIZ):
            quiz += 1
    return {"formulaires": n, "discord": arrives, "quiz": quiz}


def clippers_livrables(comptes: list) -> int:
    """Clippers qu'on peut servir aujourd'hui : par créatrice, les lignes livrables (comptes rendus + à créer avec e-mail) ÷ 3."""
    dispo = _deps.get("disponibles")
    if not dispo or not comptes:
        return 0
    creatrices = sorted({str(c.get("creatrice") or "").strip() for c in comptes if str(c.get("creatrice") or "").strip()})
    return sum(len(dispo(comptes, cr, 999)) // 3 for cr in creatrices)


async def calculer(ref: date = None) -> dict:
    ref = ref or _deps["heure_paris"]().date()
    actuel, precedent = fenetres(ref)
    try:
        cands = await _deps["lire_candidatures"]()
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Tableau de bord, candidatures : %s", erreur)
        cands = []
    dates_c = [_jour(c.get("date")) for c in cands]
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {"liaisons": {}, "etats": {}})
    dates_v = [_jour(i.get("validation")) for i in pipe.get("etats", {}).values() if i.get("validation")]
    hist = (_deps["inputs_lire"]() or {}).get("historique", {}) if _deps.get("inputs_lire") else {}
    pr = premiers_reels(hist)
    etats, comptes = {}, []
    try:                                                                    # 27/09 : le scan Apify du classeur remplace les inputs
        etats = (_deps["etats_lire"]() if _deps.get("etats_lire") else {}) or {}
        comptes = await _deps["comptes_lire"]() if _deps.get("comptes_lire") else []
        for clipper, val in premiers_reels_etats(etats.get("historique", {}), comptes).items():
            if clipper not in pr or val[0] < pr[clipper][0]:
                pr[clipper] = val
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Tableau de bord, premiers Reels depuis le classeur : %s", erreur)
    dates_r = [d0 for d0, _ in pr.values()]
    dates_7 = [j7 for _, j7 in pr.values() if j7]
    dates_p = list(premiers_paiements().values())
    series = {"candidats": dates_c, "valides": dates_v, "premier_reel": dates_r, "jour7": dates_7, "premier_paiement": dates_p}
    # 29/09 (GO axe 4) : le délai formulaire → premier Reel, et les trois déclencheurs pour doubler le recrutement
    jours_scan = [_jour(e.get("jour")) for ent in (etats.get("historique") or {}).values() for e in (ent or []) if e.get("jour")]
    debut_scan = min((j for j in jours_scan if j), default=None)
    delais = delais_premier_reel(pr, pipe, actuel, debut_scan)
    quinze = (precedent[0], actuel[1])
    try:
        livrables = clippers_livrables(comptes)
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Tableau de bord, comptes livrables : %s", erreur)
        livrables = None
    trente = (actuel[1] - timedelta(days=29), actuel[1])
    return {"actuel": {k: _compter(v, actuel) for k, v in series.items()},
            "precedent": {k: _compter(v, precedent) for k, v in series.items()},
            "fenetre": actuel, "fenetre_precedente": precedent,
            "delais": delais, "entonnoir": entonnoir_site(pipe, *quinze),
            "reel_14": (_compter(dates_r, quinze), _compter(dates_v, quinze)),
            "livrables": livrables, "valides_30": _compter(dates_v, trente)}


def texte(res: dict) -> str:
    a, p = res["actuel"], res["precedent"]
    deb, fin = res["fenetre"]
    ligne = " → ".join(f"{LIBELLES[k]} **{a[k]}**" for k in ETAPES)
    avant = " → ".join(str(p[k]) for k in ETAPES)
    conv = f"{a['premier_reel']}/{a['valides']}" if a["valides"] else "—"
    return (f"📊 **Tableau de bord — semaine du {deb.strftime('%d/%m')} au {fin.strftime('%d/%m')}**\n"
            f"{ligne}\n"
            f"-# Semaine d'avant : {avant} · validés → premier Reel : {conv} · `!tableau` pour le revoir."
            + texte_vitesse(res) + texte_declencheurs(res))


def texte_vitesse(res: dict) -> str:
    d = res.get("delais")
    if d is None:
        return ""
    if not d:
        return "\n⏱️ Délai formulaire → premier Reel : pas encore mesurable cette semaine (aucun premier Reel relié à un formulaire)."
    return (f"\n⏱️ Délai formulaire → premier Reel : médiane **{_quantile(d, 0.5)} j** · 80 % en {_quantile(d, 0.8)} j ou moins "
            f"({len(d)} clipper{'s' if len(d) > 1 else ''}) · objectif : médiane ≤ 3 j")


def texte_declencheurs(res: dict) -> str:
    e = res.get("entonnoir")
    if not e:
        return ""
    def feu(ok):
        return "⚪" if ok is None else ("✅" if ok else "❌")
    p_quiz, p_disc = _pct(e["quiz"], e["formulaires"]), _pct(e["discord"], e["formulaires"])
    r, v = res.get("reel_14", (0, 0))
    p_reel = _pct(r, v)
    liv, v30 = res.get("livrables"), res.get("valides_30", 0)
    ok_liv = None if liv is None else liv >= FACTEUR_COMPTES * max(v30, 1)
    ok_quiz = None if p_quiz is None else p_quiz >= SEUIL_QUIZ_PCT
    ok_reel = None if p_reel is None else p_reel >= SEUIL_REEL_PCT
    tous = all(x is True for x in (ok_quiz, ok_reel, ok_liv))
    return ("\n🚦 **Doubler le recrutement ?** " + ("**oui, les trois sont au vert**" if tous else "pas encore") + " (14 derniers jours)\n"
            f"{feu(ok_quiz)} Formulaire → quiz réussi : {e['quiz']}/{e['formulaires']}"
            + (f" ({p_quiz} %)" if p_quiz is not None else "") + f" · cible {SEUIL_QUIZ_PCT} % · arrivés sur Discord : {e['discord']}"
            + (f" ({p_disc} %)" if p_disc is not None else "") + "\n"
            f"{feu(ok_reel)} Validés → premier Reel : {r}/{v}" + (f" ({p_reel} %)" if p_reel is not None else "")
            + f" · cible {SEUIL_REEL_PCT} %\n"
            f"{feu(ok_liv)} Clippers livrables : {liv if liv is not None else '?'} pour {v30} validés sur 30 j · cible ≥ {FACTEUR_COMPTES} ×")


async def envoyer(canal) -> bool:
    try:
        res = await calculer()
        await canal.send(texte(res))
        return True
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Tableau de bord : %s", erreur)
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Tableau de bord (calcul) : %s", erreur)
    return False


async def commande(message, texte_cmd: str) -> bool:
    if not texte_cmd.lower().startswith("!tableau"):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Réservé aux admins et aux managers.")
        return True
    await envoyer(message.channel)
    return True


async def boucle(client):
    """Le lundi entre 8 h et 10 h (Paris), une fois par semaine ISO."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            semaine = maintenant.strftime("%G-W%V")
            etat = _deps["lire_json"](_deps["FICHIER"], {})
            if maintenant.weekday() == 0 and 8 <= maintenant.hour < 10 and etat.get("semaine") != semaine:
                canal = await _deps["canal_admin"]()
                if canal is not None and await envoyer(canal):
                    etat["semaine"] = semaine
                    _deps["ecrire_json"](_deps["FICHIER"], etat)
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Boucle du tableau de bord : %s", erreur)
        await asyncio.sleep(1200)
