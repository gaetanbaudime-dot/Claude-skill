"""Sorties décidées dans le Cockpit Clipping (29/10).

Gaëtan, 28/10 : « J'ai viré pas mal de monde ce matin dans le cockpit. » Le Cockpit écrivait seulement « Sorti » dans l'onglet
« Équipe clipping » du LOG DASHBOARD (classeur des logins) : le bot ne le lisait pas. Les virés restaient actifs pour lui :
encore dans l'app de leur Team Leader, un compte toutes les 48 h. Gaëtan, 29/10, à « quand tu passes quelqu'un en Sorti dans le
Cockpit, comment le bot doit réagir ? » : « Sortie automatique ».

Toutes les COCKPIT_SORTIES_SEC secondes, ce module lit l'onglet. Chaque ligne au Rôle « Sorti » qui désigne un clipper encore
signé et présent sur le serveur reçoit la sortie complète d'une sortie déposée (`sortir_depose` : MP, rôles retirés, salon
supprimé, expulsion, comptes rendus selon la règle de sortie, lien libéré, visites dues gardées sur la prochaine paie). Le bilan part au salon admin.

Garde-fous :
- le sortant est cherché comme pour une sortie déposée (`chercher_sortant`) : par prénom, de la créatrice de la ligne, signé
  avant le jour où le bot a vu la ligne « Sorti ». Un nouveau du même prénom, signé depuis, n'est jamais visé. Jamais le staff ;
- une ligne « Sorti » qui ne désigne aucun clipper actif (déjà parti, ancien viré) est close sans rien toucher ;
- une ligne close ne rejoue jamais. Si Gaëtan la remet en Clipper, la trace est oubliée : un nouveau « Sorti » est une nouvelle
  décision ;
- plus de COCKPIT_SORTIES_MAX sortants dans un même passage (une colonne écrasée par erreur, un tri raté) : rien n'est fait,
  une alerte au salon admin, une seule fois pour cette liste ;
- une sortie annulée par le bot (GAML illisible…) est retentée aux passages suivants, COCKPIT_SORTIES_ESSAIS fois au plus.

30/10 : à chaque passage, les lignes « à créer » encore au nom d'un « Sorti » du LOG repartent au stock (rendre_lignes_des_sortis),
même pour un sorti parti avant ce module. Jamais un compte créé, jamais un @ pas vu libre, jamais si un signé porte ce prénom.
"""
from __future__ import annotations

import asyncio
import logging
import os
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

journal = logging.getLogger("cockpit_sorties")

ONGLET = os.environ.get("COCKPIT_ONGLET_EQUIPE", "Équipe clipping").strip() or "Équipe clipping"
ACTIF = os.environ.get("COCKPIT_SORTIES", "1").strip() != "0"
PERIODE_S = max(120, int(os.environ.get("COCKPIT_SORTIES_SEC", "900") or 900))
MAX_PAR_PASSE = max(1, int(os.environ.get("COCKPIT_SORTIES_MAX", "5") or 5))
ESSAIS_MAX = max(1, int(os.environ.get("COCKPIT_SORTIES_ESSAIS", "5") or 5))

_deps: dict = {}


def configurer(deps: dict):
    _deps.update(deps)


def _n(t) -> str:
    """Sans accents, en minuscules, espaces réduits."""
    s = "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def cle(prenom: str, creatrice: str) -> str:
    return f"{_n(prenom)}|{_n(creatrice)}"


def lignes_equipe(valeurs: list) -> list:
    """Pur : les lignes de l'onglet « Équipe clipping » → [{"prenom", "creatrice", "role", "note"}]. Colonnes reconnues par leur
    en-tête (Prénom, Créatrice, Rôle, Note), jamais par position. Sans en-tête « Prénom » ni « Rôle » : [] (onglet changé)."""
    if not valeurs:
        return []
    entete = [_n(x) for x in valeurs[0]]

    def col(*noms):
        for nom in noms:
            if nom in entete:
                return entete.index(nom)
        return None
    i_p, i_c, i_r, i_note = col("prenom"), col("creatrice"), col("role"), col("note")
    if i_p is None or i_r is None:
        return []
    out = []
    for ligne in valeurs[1:]:
        lire = lambda i: (str(ligne[i]).strip() if i is not None and i < len(ligne) else "")   # noqa: E731
        if not lire(i_p):
            continue
        out.append({"prenom": lire(i_p), "creatrice": lire(i_c), "role": lire(i_r), "note": lire(i_note)})
    return out


def a_examiner(lignes: list, trace: dict, maintenant: datetime) -> tuple:
    """Pur : (nouvelle trace, lignes « Sorti » à examiner). Une ligne qui n'est plus « Sorti » perd sa trace ; une ligne close
    (« fait ») est ignorée ; une ligne vue pour la première fois prend la date du jour comme « premier »."""
    trace = {k: dict(v) for k, v in (trace or {}).items() if isinstance(v, dict)}
    sortis = {}
    for l in lignes:
        if _n(l.get("role")) == "sorti":
            sortis.setdefault(cle(l["prenom"], l.get("creatrice", "")), l)
    for k in [k for k in trace if k not in sortis]:
        trace.pop(k)                                                    # remis en Clipper (ou ligne effacée) : décision oubliée
    examen = []
    for k, l in sortis.items():
        t = trace.setdefault(k, {"premier": maintenant.isoformat(timespec="seconds")})
        if t.get("fait"):
            continue
        examen.append({"cle": k, "prenom": l["prenom"], "creatrice": l.get("creatrice", ""), "premier": t["premier"]})
    return trace, examen


def limite_signature(premier: str) -> str:
    """Le sortant a signé AVANT le lendemain du jour où le bot a vu la ligne « Sorti » (jamais un nouveau du même prénom)."""
    try:
        j = datetime.fromisoformat(str(premier)[:10]).date()
    except ValueError:
        j = datetime.now(timezone.utc).date()
    return (j + timedelta(days=1)).isoformat()


def _fichier():
    return (_deps["DONNEES"] / "cockpit_sorties.json") if _deps.get("DONNEES") else None


def bilan_ligne(prenom: str, res: dict) -> str:
    """Pur : la ligne du salon admin pour une sortie faite."""
    morceaux = [f"🚪 {prenom} : sorti(e)" + (" et expulsé(e)" if res.get("expulse") else " (⚠️ pas expulsé(e) : à la main)"),
                f"{res.get('comptes', 0)} compte(s) rendu(s)"]
    if res.get("liens"):
        morceaux.append(f"{res['liens']} lien(s) libéré(s)")
    if res.get("refus"):
        morceaux.append("⚠️ " + ", ".join(str(r) for r in res["refus"])[:300])
    return " · ".join(morceaux)


async def passe(client) -> list:
    """Un passage. Renvoie les lignes de bilan (aussi envoyées au salon admin quand il y en a)."""
    if not ACTIF or client is None:
        return []
    fichier = _fichier()
    chercher, sortir = _deps.get("chercher_prenom"), _deps.get("sortir_depose")
    if fichier is None or chercher is None or sortir is None or not _deps.get("lire_json"):
        return []
    import google_api
    import onboarding
    cid = onboarding.CLASSEUR_LOGINS_ID
    if not (cid and google_api.actif()):
        return []
    try:
        valeurs = await google_api.sheets_lire(cid, f"{onboarding.onglet_a1(ONGLET)}!A1:H400")
    except Exception as erreur:                                         # noqa: BLE001 — onglet absent ou Google indisponible
        journal.info("Cockpit, sorties : « %s » illisible (%s)", ONGLET, type(erreur).__name__)
        return []
    lignes = lignes_equipe(valeurs)
    if not lignes:
        return []
    maintenant = datetime.now(timezone.utc)
    ancienne = _deps["lire_json"](fichier, {}) or {}
    alerte_vue = ancienne.pop("_alerte", None)
    trace, examen = a_examiner(lignes, ancienne, maintenant)
    actifs = []
    for e in examen:
        try:
            membre = chercher(e["prenom"], creatrice=e["creatrice"], signe_avant=limite_signature(e["premier"]))
        except Exception as erreur:                                     # noqa: BLE001 — recherche impossible : retenté plus tard
            journal.warning("Cockpit, sorties : recherche de %s impossible (%s)", e["prenom"], type(erreur).__name__)
            continue
        if membre is None and e["creatrice"]:
            # un signé sans créatrice au registre (pas encore placé) : cherché sans elle, retenu seulement si sa fiche n'en a pas
            try:
                autre = chercher(e["prenom"], creatrice="", signe_avant=limite_signature(e["premier"]))
            except Exception:                                           # noqa: BLE001
                autre = None
            registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
            if autre is not None and not str((registre.get(str(getattr(autre, "id", ""))) or {}).get("creatrice") or "").strip():
                membre = autre
        if membre is None:
            trace[e["cle"]].update({"fait": True, "date": maintenant.isoformat(timespec="seconds"),
                                    "bilan": "aucun clipper actif à ce nom : rien à faire"})
            continue
        actifs.append((e, membre))
    bilan = []
    if len(actifs) > MAX_PAR_PASSE:
        noms = sorted(e["prenom"] for e, _ in actifs)
        if alerte_vue != noms:
            bilan.append(f"⚠️ Cockpit : {len(actifs)} clippers passés en « Sorti » d'un coup ({', '.join(noms)}). "
                         f"Au-delà de {MAX_PAR_PASSE}, je ne fais rien : vérifie l'onglet « {ONGLET} ». "
                         "S'ils sont bien virés, remets-les en « Sorti » par petits groupes, ou monte COCKPIT_SORTIES_MAX.")
        trace["_alerte"] = noms
        actifs = []
    for e, membre in actifs:
        quand = maintenant.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m")
        raison = f"viré(e) dans le Cockpit Clipping ({quand}, Gaëtan) : expulsé(e), comptes rendus, lien libéré, visites dues gardées"
        t = trace[e["cle"]]
        try:
            res = await sortir(membre, raison, metricool=False)
        except Exception as erreur:                                     # noqa: BLE001
            res = {"annule": f"{type(erreur).__name__} {str(erreur)[:100]}"}
        res = res if isinstance(res, dict) else {}
        if not res.get("annule") and not res.get("expulse") and res.get("refus"):
            # 29/10 (premier passage : Benn et Oumar sortis au même instant par leur sortie déposée, « Opération déjà en cours ») :
            # rien n'a été fait ici, on reprend au passage suivant (le membre parti, la ligne se ferme sans bruit)
            res = {"annule": str(res["refus"][0])}
        if res.get("annule"):
            t["essais"] = int(t.get("essais", 0) or 0) + 1
            motif = str(res["annule"]).split(" : ")[0]
            if t["essais"] >= ESSAIS_MAX:
                t.update({"fait": True, "abandon": True, "date": maintenant.isoformat(timespec="seconds")})
                bilan.append(f"❌ {e['prenom']} (Cockpit : Sorti) : sortie abandonnée après {t['essais']} essais ({motif}). "
                             f"À faire à la main : `!sortie @{e['prenom']} viré`.")
            else:
                journal.info("Cockpit, sorties : %s pas sorti(e) (%s), essai %s/%s", e["prenom"], motif, t["essais"], ESSAIS_MAX)
            continue
        ligne = bilan_ligne(e["prenom"], res)
        t.update({"fait": True, "date": maintenant.isoformat(timespec="seconds"), "bilan": ligne})
        bilan.append(ligne)
        journal.info("Cockpit, sorties : %s", ligne)
    _deps["ecrire_json"](fichier, trace)
    bilan += await rendre_lignes_des_sortis(lignes)
    if bilan and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Sorties du Cockpit appliquées**\n" + "\n".join(bilan),
                                    client.guilds[0] if getattr(client, "guilds", None) else None)
        except Exception:                                               # noqa: BLE001
            pass
    return bilan


def prenoms_signes(registre: dict) -> set:
    """Pur : le premier mot (normalisé) du prénom de chaque clipper encore signé au registre."""
    out = set()
    for f in (registre or {}).values():
        if isinstance(f, dict):
            p = _n(str(f.get("prenom") or f.get("prenom_distinct") or "").split(" - ")[0])
            if p:
                out.add(p.split()[0])
    return out


async def rendre_lignes_des_sortis(lignes: list) -> list:
    """30/10 (Gaëtan : « Si je les vire dans mon cockpit, tu les libères automatiquement. Je ne veux pas avoir à le faire ») :
    pour chaque ligne « Sorti » du Cockpit, les lignes « à créer » encore au nom du sorti dans le LOG repartent au stock
    (onboarding.rendre_lignes : jamais un compte créé, jamais sans @ vu libre). Garde-fou : si un clipper encore signé porte ce
    prénom (le sorti pas encore sorti, ou un homonyme), rien n'est touché. Le LOG est lu une fois par passage."""
    rendre = _deps.get("rendre_lignes")
    sortis = [l for l in lignes or [] if _n(l.get("role")) == "sorti"]
    if not rendre or not sortis:
        return []
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") and _deps.get("lire_json") else {}
    signes = prenoms_signes(registre)
    try:
        import onboarding
        comptes = await onboarding.lire_comptes()
    except Exception as erreur:                                         # noqa: BLE001 — revu au passage suivant
        journal.info("Cockpit : LOG illisible pour rendre les lignes des sortis (%s)", type(erreur).__name__)
        return []
    gerants = {_n(c.get("gerant")) for c in comptes if "creer" in _n(c.get("etat"))}
    out = []
    for l in sortis:
        p = _n(l["prenom"])
        if not p or p.split()[0] in signes or p not in gerants:
            continue
        try:
            rendus = await rendre(l["prenom"], l.get("creatrice", ""), comptes=comptes, actifs=set(registre))
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Cockpit : lignes de %s pas rendues (%s)", l["prenom"], type(erreur).__name__)
            continue
        if rendus:
            out.append(f"♻️ {l['prenom']} (Cockpit : Sorti) : {len([x for x in rendus if x.startswith('·')])} ligne(s) « à créer » "
                       "rendue(s) au stock")
    return out


async def boucle(client):
    """Un passage toutes les PERIODE_S secondes, le premier deux minutes après le démarrage (les sorties déposées d'abord)."""
    if not ACTIF:
        journal.info("Cockpit, sorties : éteint (COCKPIT_SORTIES=0)")
        return
    await asyncio.sleep(120)
    try:                                                                # 29/10 : jamais en même temps que les sorties déposées
        import roster
        await roster.attendre_demarrage()
    except Exception:                                                   # noqa: BLE001
        pass
    while True:
        try:
            await passe(client)
        except Exception as erreur:                                     # noqa: BLE001 — la boucle ne meurt jamais
            journal.warning("Cockpit, sorties : passage en échec (%s)", erreur)
        await asyncio.sleep(PERIODE_S)
