"""Cadence de publication et vues Instagram par clipper (05/10).

Ce que fait le module : pour chaque clipper demandé (par défaut les équipes de Jonas et Julien), il prend ses comptes
Instagram dans le classeur des logins (colonne Gérant), demande à Apify les publications des N derniers jours de ces
comptes (acteur `apify~instagram-scraper`, type « posts »), puis calcule par clipper : nombre de Reels, Reels par jour,
jours avec au moins un Reel, jours avec au moins deux Reels, vues cumulées, vues médianes et meilleure vidéo.
Le résultat est posté dans le salon admin (ou le salon de la commande), enregistré dans `cadence_reels.json`, et résumé
dans le journal sans aucun identifiant de compte (une ligne par clipper).

Pourquoi : la fiche de poste de Jonas paie 100 € par clipper « actif » (cadence tenue 80 % des jours) et personne ne sait
qui a réellement publié ; les visiteurs GAML ne disent qu'une partie de l'histoire. Ici on lit les publications elles-mêmes.

Commande (staff) : `!cadence [jours] [prénom …]` — par défaut 30 jours, les équipes de Jonas et Julien.
Lancement automatique : une fois par déploiement si `CADENCE_AUTO=1`, 90 s après le démarrage, puis jamais
plus de une fois par jour. Coût : environ 2,3 $ pour 1 000 publications lues ; 40 comptes sur 30 jours ≈ 5 $.
09/10 (dashboard) : `CADENCE_AUTO` vaut 0 par défaut — relancée à chaque déploiement (presque tous les jours), c'était le
premier poste Apify (1 à 5 $ par passage) ; les vues par compte viennent maintenant des séries du scan (series.py), sans coût.
`!cadence` reste. Vues d'une publication : la même règle partout (series.vues_post : videoPlayCount, sinon videoViewCount).
09/10 (Gaëtan : « Dépasse pas 25 $ / mois ») : la cadence passe par la garde du budget Apify du mois (etats_comptes.garde_apify) :
refusée d'emblée si sa dépense maximale (comptes × LIMITE_PAR_COMPTE publications × APIFY_PRIX_1000) ferait dépasser le budget,
chaque lot revérifié, et la dépense notée (publications lues ; un lot raté compté au maximum, la course continue chez Apify).
09/10 (revue 3) : la dépense maximale de chaque lot est réservée dans le registre du budget dès que la garde l'accepte (un scan
lancé pendant la lecture la compte), puis remplacée par la dépense réelle.
"""
import asyncio
import logging
import os
import statistics
from datetime import datetime, timedelta, timezone

import aiohttp

journal = logging.getLogger("bot.cadence")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR_POSTS = os.environ.get("APIFY_ACTOR_POSTS", "apify~instagram-scraper").strip()
AUTO = os.environ.get("CADENCE_AUTO", "0").strip() == "1"              # 09/10 (dashboard) : éteinte par défaut, `!cadence` reste
JOURS_DEFAUT = 30
LIMITE_PAR_COMPTE = 70                                                  # 30 jours × 2 Reels par jour, avec de la marge
LOT = 8                                                                 # profils par appel Apify (la lecture des posts est lente)
DELAI_AUTO = 90
ETATS_IGNORES = ("ban", "banni", "bannie", "a creer", "à créer", "supprime", "supprimé", "ferme", "fermé")

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    return bool(APIFY_TOKEN) and bool(_deps.get("lire_comptes"))


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _lire() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {}) if _deps.get("lire_json") else {}


def _ecrire(d: dict):
    if _deps.get("ecrire_json"):
        _deps["ecrire_json"](_deps["FICHIER"], d)


def _aujourdhui():
    return (_deps["heure_paris"]() if _deps.get("heure_paris") else datetime.now(timezone.utc)).date()


# ------------------------------------------------------------------ comptes du classeur
def comptes_par_clipper(comptes: list, prenoms: list) -> dict:
    """{prénom demandé: [handles]} à partir des lignes du classeur (colonne Gérant, comptes vivants seulement).
    Un prénom demandé qui n'a aucun compte reste dans le résultat avec une liste vide : on le dit, on ne l'oublie pas."""
    voulu = {_norm(p): p for p in prenoms}
    out = {p: [] for p in prenoms}
    for c in comptes:
        gerant = _norm(str(c.get("gerant") or "").split()[0] if str(c.get("gerant") or "").split() else "")
        if gerant not in voulu or "metricool" in _norm(c.get("gerant")):    # 09/10 : « Julien (Metricool) » n'est pas le clipper Julien
            continue
        if any(e in _norm(c.get("etat")) for e in ETATS_IGNORES):
            continue
        # 05/10 : même nettoyage d'identifiant que le scan du classeur (onboarding.normaliser_handle quand bot_discord le passe) :
        # @, URL, espaces invisibles, premier mot — sinon le profil part tel quel chez Apify et compte « non lu »
        if _deps.get("normaliser_handle"):
            handle = _deps["normaliser_handle"](c.get("handle"))
        else:
            handle = str(c.get("handle") or "").strip().lstrip("@").rstrip("/").split("/")[-1]
        if handle and handle.lower() not in {h.lower() for h in out[voulu[gerant]]}:
            out[voulu[gerant]].append(handle)
    return out


def prenoms_par_defaut() -> list:
    """Les équipes de Jonas (groupes du rapport) ; sans groupes connus, personne (la commande dit alors quoi faire). 09/10 : plus
    « Julien » en dur (l'ancien est passé monteur vidéo, le nouveau Julien clipper est dans les groupes)."""
    groupes = _deps["groupes"]() if callable(_deps.get("groupes")) else (_deps.get("groupes") or {})
    prenoms = []
    for membres in (groupes or {}).values():
        for p in membres or []:
            if p not in prenoms:
                prenoms.append(p)
    return prenoms


# ------------------------------------------------------------------ Apify
def _cout_max(n_comptes: int) -> float:
    """09/10 : la dépense Apify au plus d'une lecture de `n_comptes` comptes (LIMITE_PAR_COMPTE publications chacun)."""
    import etats_comptes
    return n_comptes * LIMITE_PAR_COMPTE * etats_comptes.APIFY_PRIX_1000 / 1000


async def _apify_posts(handles: list, depuis: datetime) -> list:
    """Les publications des comptes depuis `depuis`, par lots ; None si Apify est en panne, ou si un lot ferait dépasser le
    budget Apify du mois (09/10)."""
    if _deps.get("apify_posts"):
        return await _deps["apify_posts"](handles, depuis)
    import etats_comptes                                                # la garde et le registre du budget du mois
    url = f"https://api.apify.com/v2/acts/{ACTOR_POSTS}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    items = []
    for i in range(0, len(handles), LOT):
        lot = handles[i:i + LOT]
        maxi = _cout_max(len(lot))
        # 09/10 (revue 3) : la dépense maximale du lot est RÉSERVÉE dès que la garde accepte (un scan lancé pendant la lecture la
        # voit), puis remplacée par la dépense réelle, ou retirée sur un refus 4xx (rien n'a tourné)
        jeton = await etats_comptes.garde_apify(maxi, "cadence (publications)", reserver=True)
        if not jeton:
            return None
        charge = {"directUrls": [f"https://www.instagram.com/{h}/" for h in lot], "resultsType": "posts",
                  "resultsLimit": LIMITE_PAR_COMPTE, "onlyPostsNewerThan": depuis.strftime("%Y-%m-%d"), "addParentData": False}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                async with session.post(url, json=charge) as reponse:
                    if reponse.status >= 400:
                        journal.error("Apify HTTP %s (cadence)", reponse.status)
                        if reponse.status >= 500 or reponse.status == 408:     # la course a tourné : payée
                            etats_comptes.noter_depense(maxi, len(lot), "cadence (raté)", reservation=jeton)
                        else:
                            etats_comptes.liberer_reservation(jeton)
                        return None
                    brut = await reponse.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
            journal.error("Apify injoignable (cadence) : %s", erreur)
            etats_comptes.noter_depense(maxi, len(lot), "cadence (raté)", reservation=jeton)
            return None
        lus = brut if isinstance(brut, list) else []
        etats_comptes.noter_depense(len(lus) * etats_comptes.APIFY_PRIX_1000 / 1000, len(lus), "cadence (publications)",
                                    reservation=jeton)
        items += lus
    return items


def _proprietaire(item: dict) -> str:
    u = item.get("ownerUsername") or item.get("username") or ""
    if not u:
        u = str(item.get("inputUrl") or "").rstrip("/").split("/")[-1]
    return str(u).lower().lstrip("@")


def _est_reel(item: dict) -> bool:
    t = str(item.get("type") or "").lower()
    pt = str(item.get("productType") or "").lower()
    return t == "video" or pt in ("clips", "reels", "igtv")


def _vues(item: dict) -> int:
    """09/10 (dashboard) : la même règle de vues partout (series.vues_post : videoPlayCount si c'est un nombre, sinon
    videoViewCount) ; avant, le premier champ non nul de quatre, différent d'une publication à l'autre. Absent = 0 ici (somme)."""
    import series
    v = series.vues_post(item)
    return v if v is not None else 0


def _jour(item: dict) -> str:
    t = str(item.get("timestamp") or item.get("takenAt") or "")
    return t[:10]


# ------------------------------------------------------------------ calcul
def agreger(items: list, par_clipper: dict, jours: int, fin) -> dict:
    """{prénom: {comptes, comptes_vus, reels, par_jour, jours_1, jours_2, vues, vues_mediane, meilleure, jours_fenetre}}."""
    debut = fin - timedelta(days=jours - 1)
    fenetre = {(debut + timedelta(d)).isoformat() for d in range(jours)}
    handle_vers = {h.lower(): p for p, hs in par_clipper.items() for h in hs}
    brut = {p: {"reels": [], "vus": set(), "par_jour": {}} for p in par_clipper}
    for it in items or []:
        p = handle_vers.get(_proprietaire(it))
        if not p:
            continue
        brut[p]["vus"].add(_proprietaire(it))
        j = _jour(it)
        if j not in fenetre or not _est_reel(it):
            continue
        brut[p]["reels"].append(_vues(it))
        brut[p]["par_jour"][j] = brut[p]["par_jour"].get(j, 0) + 1
    out = {}
    for p, hs in par_clipper.items():
        b = brut[p]
        vues = [v for v in b["reels"]]
        out[p] = {
            "comptes": len(hs), "comptes_vus": len(b["vus"]), "reels": len(b["reels"]),
            "par_jour": round(len(b["reels"]) / jours, 2),
            "jours_1": sum(1 for n in b["par_jour"].values() if n >= 1),
            "jours_2": sum(1 for n in b["par_jour"].values() if n >= 2),
            "vues": sum(vues), "vues_mediane": int(statistics.median(vues)) if vues else 0,
            "meilleure": max(vues) if vues else 0, "jours_fenetre": jours,
        }
    return out


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def texte(resultat: dict, equipes: dict, jours: int, fin) -> list:
    """Lignes Discord, une par clipper, triées par Reels publiés ; `equipes` = {prénom: créatrice}."""
    debut = fin - timedelta(days=jours - 1)
    lignes = [f"**Cadence et vues Instagram** · du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')} ({jours} jours, publications lues sur les comptes du classeur)"]
    for p, r in sorted(resultat.items(), key=lambda x: (-x[1]["reels"], x[0])):
        cre = equipes.get(p, "")
        if r["comptes"] == 0:
            lignes.append(f"• **{p}**{f' ({cre})' if cre else ''} · aucun compte vivant à son nom dans le classeur")
            continue
        if r["comptes_vus"] == 0:
            lignes.append(f"• **{p}**{f' ({cre})' if cre else ''} · {r['comptes']} compte(s), aucun lisible (privés, bannis ou renommés)")
            continue
        fol = f" · {_fmt(r['followers'])} followers" if r.get("followers") is not None else ""
        lignes.append(
            f"• **{p}**{f' ({cre})' if cre else ''} · {r['comptes_vus']}/{r['comptes']} comptes lus{fol} · **{r['reels']} Reels** ({r['par_jour']} par jour) · "
            f"jours avec un Reel : {r['jours_1']}/{jours}, avec deux : {r['jours_2']} · vues : **{_fmt(r['vues'])}** (médiane {_fmt(r['vues_mediane'])}, meilleure {_fmt(r['meilleure'])})"
        )
    lignes.append("Un jour « tenu » au sens de la fiche de Jonas = deux Reels par jour sur chaque compte de croissance ; ici on compte les Reels réellement visibles, les comptes bannis ou privés ne remontent pas.")
    return lignes


def _equipes(prenoms: list) -> dict:
    groupes = _deps["groupes"]() if callable(_deps.get("groupes")) else (_deps.get("groupes") or {})
    out = {}
    for cre, membres in (groupes or {}).items():
        for p in membres or []:
            out[p] = cre
    return {p: out.get(p, "") for p in prenoms}


async def _followers(par_clipper: dict) -> dict:
    """{prénom: followers cumulés de ses comptes} via le relevé de profils du module des états (acteur léger) ; {} si indisponible."""
    scanner = _deps.get("scanner_profils")
    handles = [h for hs in par_clipper.values() for h in hs]
    if not scanner or not handles:
        return {}
    try:
        fiches = await scanner(handles)
    except Exception as erreur:                                        # jamais bloquant
        journal.warning("Relevé des followers en échec : %s", erreur)
        return {}
    if not fiches:
        return {}
    out = {}
    for p, hs in par_clipper.items():
        # 05/10 : une fiche non lue (Apify muet) ou restreinte (chiffres cachés) ne vaut pas 0 : on le dit dans le journal, par
        # clipper et en nombre de comptes, jamais par identifiant
        non_lus = sum(1 for h in hs if not (fiches.get(h.lower()) or {}).get("lu", True))
        restreints = sum(1 for h in hs if (fiches.get(h.lower()) or {}).get("restreint"))
        if non_lus or restreints:
            journal.info("Cadence followers %s : %d compte(s) non lu(s), %d restreint(s) sur %d — followers incomplets", p, non_lus, restreints, len(hs))
        out[p] = sum(int((fiches.get(h.lower()) or {}).get("followers") or 0) for h in hs)
    return out


async def completer_followers() -> dict:
    """Ajoute les followers au résultat du jour déjà calculé (sans relire les publications) ; renvoie {prénom: followers}."""
    d = _lire()
    dernier = d.get("dernier") or {}
    resultat = dernier.get("resultat") or {}
    if not resultat or not _deps.get("lire_comptes"):
        return {}
    comptes = await _deps["lire_comptes"]()
    par_clipper = comptes_par_clipper(comptes, list(resultat.keys()))
    fol = await _followers(par_clipper)
    for p, n in fol.items():
        resultat[p]["followers"] = n
        journal.info("Cadence followers %s : %s (sur %s comptes)", p, n, len(par_clipper.get(p, [])))
    if fol:
        d["dernier"]["resultat"] = resultat
        _ecrire(d)
    return fol


async def executer(jours: int = JOURS_DEFAUT, prenoms=None) -> tuple:
    """(lignes, resultat) ; lignes explique aussi les cas sans Apify ou sans comptes."""
    if not actif():
        return (["Cadence inactive : `APIFY_TOKEN` et le classeur des logins sont nécessaires dans Railway."], {})
    prenoms = list(prenoms or prenoms_par_defaut())
    if not prenoms:
        return (["Cadence : aucun prénom demandé et aucune équipe connue. Exemple : `!cadence 30 Caroline Josué`."], {})
    comptes = await _deps["lire_comptes"]()
    par_clipper = comptes_par_clipper(comptes, prenoms)
    handles = [h for hs in par_clipper.values() for h in hs]
    fin = _aujourdhui() - timedelta(days=1)
    depuis = datetime.combine(fin - timedelta(days=jours - 1), datetime.min.time())
    if handles:                                                         # 09/10 : budget Apify du mois (décision de Gaëtan, 25 $)
        import etats_comptes
        maxi = _cout_max(len(handles))
        if not await etats_comptes.garde_apify(maxi, "cadence (publications)"):
            st = etats_comptes.budget_apify_connu() or etats_comptes.etat_budget()
            return ([f"Cadence : budget Apify du mois insuffisant ({etats_comptes._euros(st.get('usage_usd'))} $ dépensés sur "
                     f"{etats_comptes._euros(st.get('budget_usd'))} $ ; cette lecture peut coûter jusqu'à {etats_comptes._euros(maxi)} $). "
                     "Rien n'a été lu. Avec moins de prénoms, la lecture coûte moins : `!cadence 30 Prénom`."], {})
    items = await _apify_posts(handles, depuis) if handles else []
    if items is None:
        return (["Cadence : Apify ne répond pas (ou le budget du mois est atteint), rien n'a été lu. Relance plus tard avec `!cadence`."], {})
    resultat = agreger(items, par_clipper, jours, fin)
    for p, n in (await _followers(par_clipper)).items():
        resultat[p]["followers"] = n
    for p, r in resultat.items():
        journal.info("Cadence %s : comptes=%s lus=%s reels=%s par_jour=%s jours1=%s jours2=%s vues=%s mediane=%s meilleure=%s followers=%s",
                     p, r["comptes"], r["comptes_vus"], r["reels"], r["par_jour"], r["jours_1"], r["jours_2"], r["vues"], r["vues_mediane"], r["meilleure"], r.get("followers", "?"))
    d = _lire()
    d["dernier"] = {"jour": fin.isoformat(), "jours": jours, "resultat": resultat, "calcule_le": datetime.now(timezone.utc).isoformat()}
    _ecrire(d)
    return (texte(resultat, _equipes(prenoms), jours, fin), resultat)


async def _envoyer(canal, lignes: list):
    bloc = ""
    for l in lignes:
        if len(bloc) + len(l) + 1 > 1900:
            await canal.send(bloc)
            bloc = ""
        bloc += l + "\n"
    if bloc:
        await canal.send(bloc)


# ------------------------------------------------------------------ lancement automatique et commande
async def boucle(client) -> None:
    """Une lecture automatique par déploiement (au plus une par jour), postée dans le salon admin."""
    if not AUTO or not actif():
        journal.info("Cadence automatique désactivée (CADENCE_AUTO=0 ou APIFY_TOKEN absent)")
        return
    await client.wait_until_ready()
    await asyncio.sleep(DELAI_AUTO)
    d = _lire()
    try:
        if d.get("dernier_auto") == _aujourdhui().isoformat():
            dernier = (d.get("dernier") or {}).get("resultat") or {}
            if dernier and not any("followers" in r for r in dernier.values()):   # résultat du jour sans followers : on les ajoute seulement
                fol = await completer_followers()
                canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
                if canal and fol:
                    await _envoyer(canal, ["**Followers Instagram par clipper** (comptes du classeur, relevé de ce matin)"] +
                                   [f"• **{p}** : {_fmt(n)}" for p, n in sorted(fol.items(), key=lambda x: -x[1])])
            return
        d["dernier_auto"] = _aujourdhui().isoformat()
        _ecrire(d)
        lignes, _ = await executer()
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal:
            await _envoyer(canal, lignes)
    except Exception as erreur:                                        # jamais de plantage du bot pour un rapport
        journal.exception("Cadence automatique en échec : %s", erreur)


async def commande(message, texte_msg: str) -> bool:
    """`!cadence [jours] [prénom …]` (staff)."""
    t = (texte_msg or "").strip()
    if not t.lower().startswith("!cadence"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    morceaux = t.split()[1:]
    jours = JOURS_DEFAUT
    if morceaux and morceaux[0].isdigit():
        jours = max(1, min(90, int(morceaux[0])))
        morceaux = morceaux[1:]
    prenoms = morceaux or None
    await message.reply(f"Lecture des publications en cours ({jours} jours, {'équipes par défaut' if not prenoms else ', '.join(prenoms)}) : une à trois minutes.")
    lignes, _ = await executer(jours, prenoms)
    await _envoyer(message.channel, lignes)
    return True
