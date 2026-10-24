"""Paie au clic (machine horizontale v2, décision de Gaëtan des 22-23/09/2026).

Le clipper est payé TAUX_CLIC dollars (0,05 $ par défaut) par visite réelle sur son lien GetAllMyLinks :
visiteurs francophones (PAYS_PAYES : France, Belgique, Suisse, Canada, DOM-TOM… par défaut), robots exclus par GAML. Ce module :

  - lit chaque jour les relevés de tous les liens attribués (deux appels par lien et par jour :
    pays hors robots, total avec robots) et les range dans clics.json sur le volume ; 09/10 (dashboard, contrat C2) : de TOUS
    les liens GAML actifs (pages de créatrice, /ytb, /fb, libérés, hors clipping), la veille relue vers 6 h puis figée, et le
    jour en cours relu toutes les 15 minutes (`aujourdhui`) ; lecteurs : `clics_lien`, `clics_aujourdhui` (jamais un faux 0) ;
  - envoie chaque matin, dans le salon perso de chaque clipper, sa ligne de la veille ;
  - répond à `!mesclics` (le clipper ne voit que lui) et `!wallet` (son adresse de paiement) ;
  - donne aux managers `!clics`, `!liens`, `!lien @clipper …` (attribuer ou cloner un lien) et
    `!paie-clics 5|20 [AAAA-MM]` : la liste adresse-montant de la paie du 5 (20 → 4, règle du 09/10 ; la paie au clic a commencé le 05/10
    précédent) ou du 20 (1 → 15 du mois), avec le CSV. Le virement reste humain ;
  - 11/10 (lot L11, grille TL / manager de Gaëtan) : ajoute à cette liste les primes d'équipe d'equipes_tl (10 $ au TL par VA à 500
    visites payées ou plus, 75 $ au manager par équipe à 3 000 ou plus), mesurées par `payees` (la ligne de paie elle-même), figées
    dans clics.json['primes_equipes'] au premier calcul où elles sont définitives, sur la feuille « Paie du … » (colonnes « Au
    clic », « Parrainage », « Prime équipe »), dans le salon du TL et du manager, et dans l'onglet « Équipes » que lit l'app.
    Dépendances : `primes_equipes`, que l'on_ready du lot W branche déjà (la liste du 5 et du 20 porte alors les primes) ;
    `etat_equipes` (figement) et `calcul_equipes` (onglet « Équipes »), qu'on_ready peut passer aussi, sinon dérivées d'equipes_tl
    (_dep_equipes, mêmes mesures). Sans `primes_equipes`, rien ne change.

Le module ne connaît pas bot_discord : il reçoit ses dépendances dans `demarrer(client, deps)`.
Sans GAML_API_KEY, tout est inactif et les commandes le disent.
"""

import asyncio
import contextvars
import csv
import io
import copy
import json
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

import aiohttp
import discord

import google_api

journal = logging.getLogger("clics")

GAML_API_KEY = os.environ.get("GAML_API_KEY", "").strip()
TAUX_CLIC = float(os.environ.get("TAUX_CLIC", "0.05") or 0.05)
try:                                                                    # 23/10 : le forfait de liens GAML (même variable que places.py) = liens ACTIFS permis
    FORFAIT_LIENS_GAML = max(0, int(os.environ.get("GAML_FORFAIT_LIENS", "50") or 50))
except ValueError:
    FORFAIT_LIENS_GAML = 50
# 24/10 : la liste GAML contient AUSSI les liens désactivés, qui ne comptent pas dans le forfait (36 actifs + 14 désactivés = 50 lignes
# sous un forfait de 50 : l'inventaire se croyait « au plafond » et bloquait la création de lien). Plafond supposé d'UNE réponse du
# serveur : forfait + 50 lignes désactivées, au moins 100. Une liste qui l'atteint peut être coupée : elle reste incomplète.
try:
    LISTE_GAML_MAX = max(1, int(os.environ.get("GAML_LISTE_MAX", "") or max(100, FORFAIT_LIENS_GAML + 50)))
except ValueError:
    LISTE_GAML_MAX = max(100, FORFAIT_LIENS_GAML + 50)
# Visiteurs FRANCOPHONES (précision de Gaëtan, 23/09) : la zone qui paie sur OnlyFans/MYM. Noms tels que GAML les renvoie.
# Le Maghreb et l'Afrique francophone (pays des clippers eux-mêmes) restent exclus par défaut : PAYS_PAYES pour changer.
PAYS_PAYES_DEFAUT = ("France,Belgium,Switzerland,Canada,Luxembourg,Monaco,Réunion,Guadeloupe,Martinique,French Guiana,"
                     "Mayotte,New Caledonia,French Polynesia")
PAYS_PAYES = [p.strip() for p in os.environ.get("PAYS_PAYES", PAYS_PAYES_DEFAUT).split(",") if p.strip()]
PAYS_LIBELLE = os.environ.get("PAYS_LIBELLE", "francophones").strip() or "francophones"
CLICS_DEPUIS = os.environ.get("CLICS_DEPUIS", "2026-10-05").strip()          # 09/10 (Gaëtan) : la paie au clic a commencé le 05/10
CLICS_HEURE = int(os.environ.get("CLICS_HEURE", "7") or 7)                    # ligne du matin (heure de Paris)
LIGNE_MATIN = os.environ.get("CLICS_LIGNE_MATIN", "0").strip() == "1"   # 05/10 : la ligne « Visites hier » du salon perso, éteinte
# 25/09 : les anciens clippers gardent leur fixe deux semaines, puis clic ou sortie. Le bilan part tout seul ce jour-là.
BILAN_FIXE_DATE = os.environ.get("BILAN_FIXE_DATE", "2026-10-05").strip()      # 28/09 (Gaëtan) : bascule le 05/10, plus le 09/10
BILAN_FIXE_JOURS = int(os.environ.get("BILAN_FIXE_JOURS", "14") or 14)
SEUIL_FIXE_100 = int(os.environ.get("SEUIL_FIXE_100", "32") or 32)            # visites payables/jour qui rentabilisent 100 €
SEUIL_FIXE_200 = int(os.environ.get("SEUIL_FIXE_200", "65") or 65)            # … et 200 € (0,30 $ de CA par visite, 35 % de marge)
CLICS_EXCLURE = {p.strip().lower() for p in os.environ.get("CLICS_EXCLURE", "gaetan,gaëtan,jonas,x,y").split(",") if p.strip()}
# 13/10 (Gaëtan : « Caroline, Lilian, Josué, Yves au fixe + commission sur les subs ; tout le reste commission sur les clics ;
# tout le monde est payé le 20 et le 5 ») : Rianah sort du fixe et de CLICS_EXCLURE — son clipping est payé au clic (comme les
# autres anciens fixes, depuis BASCULE_CLIC), ses comptes Metricool restent au fixe (liens hors clipping, jamais payés au clic).
# 08/10 (Gaëtan) : tout le monde au clic sauf ces prénoms (Jonas = manager). Sans accents. 09/10 (Gaëtan : « Julien arrête tout, il va
# juste faire le monteur vidéo maintenant pour moi ») : « julien » retiré, l'ancien sort du clipping (`!monteur`) et le nouveau Julien
# clipper est au clic comme les autres.
PAIE_FIXE = {"".join(c for c in unicodedata.normalize("NFD", p.strip().lower()) if unicodedata.category(c) != "Mn")
             for p in os.environ.get("PAIE_FIXE", "caroline,lilian,josue,yves").split(",") if p.strip()}
PAIE_DECISION = "2026-10-08"
# 09/10 (Gaëtan : « tout le monde passe au clic depuis le 5 octobre, sauf Rianah, Caroline, Lilian, Josué et Yves qui restent au
# fixe ») : un ancien fixe est payé au clic sur ses visites à partir du 05/10 (la bascule prévue par le bilan des fixes).
BASCULE_CLIC = os.environ.get("BASCULE_CLIC", "2026-10-05").strip() or "2026-10-05"
# 08/10 (ménage GAML) : un lien libéré sous ce nombre de visiteurs (hors robots) sur 7 jours est désactivé, une fois par jour.
MENAGE_SEUIL = int(os.environ.get("CLICS_MENAGE_SEUIL", "15") or 15)
MENAGE_VERSION = 2                                                      # changée → le ménage repasse dès le déploiement
# 08/10 (Gaëtan : « branche le tableau d'adresses dans la paie du bot ») : l'app clippers enregistre l'adresse USDC de chaque
# clipper dans l'onglet « Adresses USDC » du tableur « App clippers · usage » (Drive agence). Le bot le lit à chaque paie, une fois
# par jour et sur `!adresses`, et complète ses `wallets` : la plus récente des deux adresses (app ou `!wallet`) gagne.
ADRESSES_TABLEUR = os.environ.get("ADRESSES_TABLEUR", "App clippers · usage").strip()
ADRESSES_ONGLET = os.environ.get("ADRESSES_ONGLET", "Adresses USDC").strip()
ADRESSES_CLASSEUR_ID = os.environ.get("ADRESSES_CLASSEUR_ID", "").strip()        # pour éviter la recherche par nom
API = "https://getallmylinks.com/api/v1"
FUSEAU = "Europe/Paris"
# 09/10 (dashboard : « tout voir, le plus souvent possible, pas de manquements ») : TOUS les liens GAML actifs sont relevés chaque
# jour (pages de créatrice, /ytb, /fb, libérés, hors clipping, en plus des liens payés), et le jour en cours est relu toutes les
# 15 minutes (`aujourdhui`). Une erreur GAML n'écrit jamais 0 : le jour reste absent, le lecteur affiche « non lu ».
RELEVE_RECUL = int(os.environ.get("CLICS_RELEVE_RECUL", "15") or 15)     # jours relus en arrière pour un lien sans clipper
RELEVE_ANCIENS_MAX = int(os.environ.get("CLICS_RELEVE_ANCIENS_MAX", "40") or 40)   # appels de rattrapage (jours anciens) par passage
RELEVE_PAUSE = float(os.environ.get("CLICS_RELEVE_PAUSE", "2") or 2)      # secondes entre deux relevés (2 appels) : ≈ 45 appels/min
RELECTURE_HEURE = int(os.environ.get("CLICS_RELECTURE_HEURE", "6") or 6)  # J-1 lu avant cette heure (Paris) : relu après, puis figé
DIRECT_MAX = int(os.environ.get("CLICS_DIRECT_MAX", "45") or 45)          # appels « aujourd'hui » au plus par passage de 15 min
DIRECT_PAUSE = float(os.environ.get("CLICS_DIRECT_PAUSE", "4") or 4)      # secondes entre deux appels « aujourd'hui »
DIRECT_RESERVE = int(os.environ.get("CLICS_DIRECT_RESERVE", "15") or 15)  # requêtes de la minute laissées à l'app : on s'arrête avant
DIRECT_SI_RATTRAPAGE = int(os.environ.get("CLICS_DIRECT_SI_RATTRAPAGE", "60") or 60)   # passage chargé (minuit, 6 h) : pas de direct
DIRECT_MALADES = int(os.environ.get("CLICS_DIRECT_MALADES", "3") or 3)    # 09/10 : essais réservés aux liens en échec récent, en fin de passage
# 10/10 (revue CLICS, 3e passe) : un jour de la période de paie pas encore relevé fait attendre la paie du 5 / du 20 jusqu'à cette
# heure (Paris) au plus ; ensuite elle part quand même, ces jours signalés (jamais comptés 0 en silence, jamais une paie oubliée)
PAIE_ATTENTE_HEURE = int(os.environ.get("CLICS_PAIE_ATTENTE_HEURE", "12") or 12)

_deps = {}
_client = None
_session = None
_verrou = asyncio.Lock()
# 08/10 (revue : un lien repris pendant la passe du ménage était désactivé, puis la reprise écrasée par la copie de la boucle) :
# toute décision sur un lien libéré (désactiver, rattraper, reprendre) relit clics.json et l'écrit sous ce verrou.
verrou_liens = asyncio.Lock()
_limite = {"restant": 60, "reset": 0.0}
# 09/10 (dashboard) : la boucle « aujourd'hui » s'arrête sur un 429 au lieu d'attendre (la minute appartient alors à l'app). Une
# variable de contexte : seule la tâche qui la pose est concernée, jamais une commande ou l'onboarding qui appellent GAML en même temps.
_arret_429 = contextvars.ContextVar("clics_arret_429", default=False)


class LimiteGAML(RuntimeError):
    """09/10 (dashboard) : 429 de GAML dans la boucle « aujourd'hui » (limite de 60 requêtes/min partagée avec l'app)."""


def actif() -> bool:
    return bool(GAML_API_KEY)


# ------------------------------------------------------------------ données
class _Etat(dict):
    """09/10 (revue : la boucle horaire lisait les liens en début de tour et les réécrivait minutes plus tard, effaçant une sortie,
    une reprise ou un `!monteur` faits entre-temps — l'ancien Julien redevenait payé) : l'état lu garde une copie de ce qu'il était
    à la lecture (`_base`), pour que `_ecrire` n'applique que ce que l'appelant a changé lui-même."""
    _base = None


_ABSENT = object()


def _fusion(base, mien, frais):
    """Fusion à trois voies : ce que j'ai changé depuis ma lecture (`base` → `mien`) appliqué sur le disque (`frais`). Un sous-dict
    changé des deux côtés est fusionné clé par clé ; une même valeur changée des deux côtés : celle du disque gagne (écrite par un
    autre, en connaissance de cause, pendant que je travaillais sur une copie)."""
    out = {}
    for k in list(frais) + [k for k in mien if k not in frais] + [k for k in base if k not in frais and k not in mien]:
        b, m, f = base.get(k, _ABSENT), mien.get(k, _ABSENT), frais.get(k, _ABSENT)
        if m == b:
            v = f
        elif f == b:
            v = m
        elif isinstance(m, dict) and isinstance(f, dict) and isinstance(b, dict):
            v = _fusion(b, m, f)
        else:
            v = f
        if v is not _ABSENT:
            out[k] = v
    return out


def _lire() -> dict:
    d = _Etat(_deps["lire_json"](_deps["FICHIER_CLICS"], {}))
    d.setdefault("liens", {}); d.setdefault("jours", {}); d.setdefault("wallets", {})
    d._base = copy.deepcopy(dict(d))
    return d


def _ecrire(d: dict):
    base = getattr(d, "_base", None)
    if base is not None:
        frais = _deps["lire_json"](_deps["FICHIER_CLICS"], {})
        frais.setdefault("liens", {}); frais.setdefault("jours", {}); frais.setdefault("wallets", {})
        if frais != base:                                              # quelqu'un a écrit depuis ma lecture : on fusionne
            fusion = _fusion(base, dict(d), frais)
            d.clear()
            d.update(fusion)
        d._base = copy.deepcopy(dict(d))
    _deps["ecrire_json"](_deps["FICHIER_CLICS"], dict(d))


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
    dernier = 0                                                         # le dernier statut rejoué (429 ou 5xx)
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
                if r.status == 429 and _arret_429.get():
                    raise LimiteGAML(f"GAML 429 sur {chemin} : limite de la minute atteinte")
                if r.status == 429 or r.status >= 500:
                    dernier = r.status
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
        except asyncio.TimeoutError as erreur:                           # 08/10 (revue) : pas un ClientError ; jamais rejoué
            raise RuntimeError(f"GAML : délai dépassé sur {chemin}") from erreur   # (un POST /clone rejoué ferait un doublon)
    # 09/10 (revue CLICS, R3 bis) : le 429 épuisé (limite de la minute : global) n'est plus confondu avec le 5xx épuisé (souvent propre
    # à un lien : une page /ytb que l'analytique ne sait pas lire) ; les relevés ne s'arrêtent que sur le premier
    if dernier == 429:
        raise RuntimeError(f"GAML : trop de tentatives (429) sur {chemin}")
    raise RuntimeError(f"GAML {dernier or '5xx'} répété : trop de tentatives (5xx) sur {chemin}")


class ListeGAML(list):
    """11/10 (contre-vérification CLICS, passe 3 : la page 2 de /links refusée au démarrage, verifier_trackings marquait
    `supprime_gaml` pour toujours les liens payés de la page 2 — plus relevés, comptés 0 dans la paie sans « provisoire ») : la liste
    de liens_gaml, avec `complete` = False quand une page a été refusée ou que la dernière page lue en apportait encore. Un lien
    absent d'une liste incomplète n'est jamais la preuve qu'il est effacé."""
    complete = True


async def liens_gaml() -> list:
    """Conserve les pages lues ; seule une page vide prouve la fin de pagination.
    Une page répétée ou malformée laisse l'inventaire incomplet : son absence ne
    prouve ni la suppression d'un lien ni la disponibilité d'une capacité.
    23/10 : un inventaire incomplet dit POURQUOI dans le journal (avertissement « Inventaire GAML incomplet : … »), car il bloque toute
    création de lien (compte 3, cohorte, lien déposé).
    """
    def _lot(r):
        lot = r if isinstance(r, list) else None
        if isinstance(r, dict):
            for cle in ("member", "hydra:member", "links", "data"):
                if cle in r:
                    lot = r[cle]
                    break
        if not isinstance(lot, list) or any(
            not isinstance(lien, dict)
            or not isinstance(lien.get("id"), (str, int))
            or isinstance(lien.get("id"), bool)
            or not str(lien["id"]).strip()
            for lien in lot
        ):
            raise RuntimeError("GAML : inventaire de liens malformé")
        return list(lot)
    tous = _lot(await _requete("GET", "/links"))
    vus = {l.get("id") for l in tous}
    complete = False
    raison = f"aucune page vide après {len(tous)} liens (page 1)"       # 23/10 : dit POURQUOI l'inventaire est incomplet (bloquait tous les liens)
    for page in range(2, 11):
        try:
            lot = _lot(await _requete("GET", "/links", params={"page": page}))
            neufs = [l for l in lot if l.get("id") not in vus]
        except RuntimeError as erreur:
            raison = f"page {page} refusée ({str(erreur)[:120]}), {len(tous)} liens lus"
            journal.info("Liens GAML : page %s refusée (%s), %s liens lus", page, erreur, len(tous))
            break
        if not lot:
            complete = True
            break
        if not neufs:
            # 23/10 : GAML ignore `page` et rend la même liste entière à chaque appel (49 liens lus, page 2 identique ; le MCP, sans
            # paramètre de page, rend les mêmes 49). Une page qui redonne EXACTEMENT les liens déjà lus, sous le forfait du compte, est la
            # liste entière : fin prouvée. Une page seulement en partie déjà lue, ou une liste au plafond supposé d'une réponse (peut-être
            # coupée), reste incomplète : fermé par défaut, comme avant. 24/10 : le plafond n'est plus le forfait (liens actifs) : la liste
            # compte aussi les liens désactivés.
            if {l.get("id") for l in lot} == vus and len(vus) < LISTE_GAML_MAX:
                complete = True
                journal.info("Inventaire GAML : page %s identique à la page 1 (%s liens, plafond supposé %s) : le serveur ignore la page, liste entière",
                             page, len(tous), LISTE_GAML_MAX)
                break
            raison = f"page {page} : {len(lot)} lien(s), tous déjà lus ({len(tous)} lus) : la page demandée est rendue identique"
            break
        tous += neufs
        vus.update(l.get("id") for l in neufs)
        raison = f"page {page} lue ({len(lot)} lien(s), {len(neufs)} nouveaux), pas de page vide avant la page 10"
    out = ListeGAML(tous)
    out.complete = complete
    if not complete:
        journal.warning("Inventaire GAML incomplet : %s", raison)
    return out


def _liste_reponse(r, chemin: str) -> list:
    """09/10 (dashboard) : les lignes d'une réponse d'analytique GAML : une liste, ou l'enveloppe `{member}` / `{hydra:member}` /
    `{data}` (celle du MCP). Toute autre forme lève une erreur : avant, une enveloppe inconnue donnait une liste vide, donc un
    relevé à 0 écrit pour toujours (« jamais un faux 0 »)."""
    if isinstance(r, list):
        return r
    if isinstance(r, dict):
        for cle in ("member", "hydra:member", "data"):
            if isinstance(r.get(cle), list):
                return r[cle]
    raise RuntimeError(f"GAML : réponse inattendue sur {chemin} ({type(r).__name__} {str(r)[:80]})")


def _nombre(x: dict, *cles) -> int:
    """La première clé présente parmi `cles` (« count », « totalVisits » ou « total_visits » selon l'API ou le MCP), en entier."""
    for cle in cles:
        if x.get(cle) is not None:
            return int(x.get(cle) or 0)
    return 0


def _comptes_pays(pays: list) -> tuple:
    """(hors robots, payés) d'une réponse `/analytics/countries` (robots déjà exclus par GAML)."""
    hors_robots = sum(_nombre(x, "count", "visits", "total_visits", "totalVisits") for x in pays)
    payes = sum(_nombre(x, "count", "visits", "total_visits", "totalVisits") for x in pays if str(x.get("country", "")) in PAYS_PAYES)
    return hors_robots, payes


async def releve(link_id: str, jour: date, sans_visitors: bool = False, erreurs: dict = None) -> dict:
    """Relevé d'un lien pour un jour (heure de Paris) : brut (robots inclus), hors robots, payés. 09/10 (dashboard) : accepte
    l'enveloppe `{data}` et la clé `total_visits` (forme du MCP), et lève une erreur sur une réponse illisible (jamais un 0).
    11/10 (contre-vérification CLICS, passe 3) : `sans_visitors` (rattraper, /analytics/visitors en panne pendant le passage) → brut
    None sans appeler visitors ; `erreurs` (dict) reçoit l'erreur visitors d'un lien (`erreurs["visitors"]`)."""
    base = {"link_id": link_id, "range": "custom", "date_from": jour.isoformat(), "date_to": jour.isoformat(),
            "timezone": FUSEAU}
    pays = _liste_reponse(await _requete("GET", "/analytics/countries", params=base), "/analytics/countries")
    hors_robots, payes = _comptes_pays(pays)
    if sans_visitors:
        return {"brut": None, "hors_robots": hors_robots, "payes": payes, "brut_non_lu": True}
    # 10/10 (revue CLICS, reprise de la 3e passe : le jour viral de Tom, /analytics/visitors en délai dépassé, countries répondait 71
    # fois et tout était jeté) : le chiffre payé vient de countries seul ; le total robots compris (visitors) ne sert qu'à afficher les
    # robots. Une erreur propre au lien sur visitors garde donc le jour : brut None (`brut_non_lu`, comme `aujourdhui`, contrat C2).
    # Une erreur globale (panne, limite) remonte : le jour entier est relu au passage suivant.
    try:
        avec = _liste_reponse(await _requete("GET", "/analytics/visitors", params={**base, "hide_bots": "false"}), "/analytics/visitors")
    except Exception as erreur:                                         # noqa: BLE001 — réponse illisible comprise
        if _erreur_globale(erreur):
            raise
        journal.warning("Relevé %s %s : total robots compris illisible (%s), visites payées gardées", link_id, jour, erreur)
        if erreurs is not None:
            erreurs["visitors"] = str(erreur)[:160]
        return {"brut": None, "hors_robots": hors_robots, "payes": payes, "brut_non_lu": True}
    brut = sum(_nombre(x, "totalVisits", "total_visits", "visits", "count") for x in avec)
    return {"brut": brut, "hors_robots": hors_robots, "payes": payes}


async def payes_periode(link_id: str, debut: date, fin: date) -> int:
    """Visites payables (pays de PAYS_PAYES, robots exclus) d'un lien sur une période, en un appel (30/09 : Clics last 7d. du
    classeur, bloc par bloc)."""
    pays = await _requete("GET", "/analytics/countries", params={"link_id": link_id, "range": "custom", "date_from": debut.isoformat(),
                                                                  "date_to": fin.isoformat(), "timezone": FUSEAU})
    return _comptes_pays(_liste_reponse(pays, "/analytics/countries"))[1]


async def visiteurs_periode(link_id: str, debut: date, fin: date) -> int:
    """Visites hors robots (tous pays) d'un lien sur une période, en un appel (08/10 : le ménage des liens libérés)."""
    pays = await _requete("GET", "/analytics/countries", params={"link_id": link_id, "range": "custom", "date_from": debut.isoformat(),
                                                                  "date_to": fin.isoformat(), "timezone": FUSEAU})
    return _comptes_pays(_liste_reponse(pays, "/analytics/countries"))[0]


async def cloner_lien(base_id: str, nom: str, note: str) -> dict:
    """Clone un lien GAML (même boutons, même design), le renomme, l'active. Renvoie {id, url}."""
    clone = await _requete("POST", f"/links/{base_id}/clone")
    nouveau_id = clone.get("id")
    if not nouveau_id:
        raise RuntimeError("clone GAML sans identifiant")
    try:
        maj = await _requete("PATCH", f"/links/{nouveau_id}", corps={"name": nom, "note": note, "enabled": True})
    except RuntimeError as erreur:
        # 03/10 : le clone réussit mais l'activation échoue (forfait GAML plein) → sans ça, chaque relance laissait un clone
        # désactivé de plus (22 « Clipping Andry » le 01/10). On efface le clone avant de remonter l'erreur.
        try:
            await _requete("DELETE", f"/links/{nouveau_id}")
        except RuntimeError:
            pass
        raise RuntimeError(f"{erreur} — clone effacé ; forfait GAML plein ?") from erreur
    return {"id": nouveau_id, "url": maj.get("url") or clone.get("url") or ""}


async def lien_detail(link_id: str) -> dict:
    return await _requete("GET", f"/links/{link_id}")


def _nom_plateforme(c):
    nom = str(c.get("name") or "").strip().lower()
    return any(m in nom for m in ("priv", "platform", "plateforme", "exclusi",
                                  "onlyfans", "only fans", "onlyfriends", "mym", "miam")) or nom in ("of", "0f")


def annexe_sure(c):
    """Liste fermée : texte brut, image non cliquable, profil Instagram direct.

    Aucun raccourcisseur, HTML, paramètre de redirection ou URL secondaire.
    Un nom de plateforme rend la carte ambiguë même si son type prétend être texte/image.
    """
    if _nom_plateforme(c):
        return False
    # Les destinations alternatives ne peuvent se cacher dans un champ annexe.
    for k, v in c.items():
        if v and k not in ("value", "image", "imageUrl") and any(
                x in k.lower() for x in ("url", "href", "link", "redirect", "target", "html")):
            return False
    valeur = str(c.get("value") or "").strip()
    typ = str(c.get("cardType") or "").lower()
    if typ == "text":
        return not re.search(r"[:/<>&]|www\.|(?:mym|onlyfans|instagram)\.", valeur, re.I)
    if typ == "image":
        image = c.get("imageUrl") or c.get("image")
        return not valeur and isinstance(image, str) and bool(re.fullmatch(
            r"https://[a-zA-Z0-9.-]+/[^?#<>]+\.(?:png|jpg|jpeg|gif|webp|avif)", image, re.I))
    if typ in ("simple", "social", "instagram", ""):
        match = re.fullmatch(r"https://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?", valeur)
        return bool(match and match[1].lower() not in
                    ("accounts", "redirect", "direct", "explore", "p", "reel", "reels", "stories", "about"))
    return False


def cartes_tracking(detail: dict):
    """Modèle livrable : une carte privée identifiable, zéro ou une MYM.

    Seules les annexes explicitement sûres sont ignorées ; aucune suppression.
    Les liens Infloww sont reconnus par le nom de la carte privée existante.
    """
    cartes = detail.get("contents") or []
    def domaine(c, attendu):
        try:
            h = (urlsplit(str(c.get("value") or "")).hostname or "").lower()
            return h == attendu or h.endswith("." + attendu)
        except ValueError:
            return False
    mym = [c for c in cartes if domaine(c, "mym.fans")]
    autres = [c for c in cartes if c not in mym and not annexe_sure(c)]
    if len(mym) > 1 or len(autres) != 1:
        raise ValueError("Cartes GAML ambiguës : vérification manuelle du modèle requise")
    privee = autres[0]
    nom = str(privee.get("name") or "").strip().lower()
    if not (domaine(privee, "onlyfans.com") or
            any(m in nom for m in ("priv", "platform", "plateforme", "exclusi", "onlyfans", "only fans", "onlyfriends")) or
            nom in ("of", "0f")):
        raise ValueError("Carte privée non identifiable : vérification manuelle requise")
    ids = [str(c.get("id") or "") for c in cartes]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("Identifiants de cartes GAML absents ou dupliqués")
    return (mym[0] if mym else None), privee


def _carte_privee(detail: dict):
    return cartes_tracking(detail)[1]


async def poser_tracking(link_id: str, url: str) -> str:
    """27/09 (Gaëtan) : « quand tu crées un lien de clipper, tu dupliques celui d'avant et tu modifies le lien dans Cards ».
    Met `url` (le lien de tracking OnlyFans du POD) dans la carte « Plateforme privée ». Renvoie 'ok', 'déjà' ou la raison."""
    if not url:
        return "sans tracking"
    try:
        carte = _carte_privee(await lien_detail(link_id))
    except ValueError as erreur:
        return str(erreur)
    if carte is None:
        return "pas de carte OnlyFans sur ce lien"
    if (carte.get("value") or "").strip() == url.strip():
        return "déjà"
    await _requete("PATCH", f"/contents/{carte['id']}", corps={"value": url.strip()})
    return "ok"


async def poser_mym(link_id: str, url: str, image: str = "") -> str:
    """05/10 (Gaëtan : MYM en premier, « Miam ») : le bouton MYM d'un lien reçoit `url` (tracking MyPulse). S'il manque, il est
    créé comme les autres (« Miam », effet pulsant, `image` si les cartes du lien sont illustrées) puis remonté au-dessus
    d'OnlyFriends. Repéré par sa destination (mym.fans), jamais la carte OnlyFans. Renvoie 'ok', 'déjà' ou la raison."""
    url = (url or "").strip()
    if not url.startswith("https://mym.fans/"):
        return "pas un lien MYM"
    detail = await lien_detail(link_id)
    cartes = detail.get("contents") or []
    try:
        mym, _ = cartes_tracking(detail)
    except ValueError as erreur:
        return str(erreur)
    if mym:
        if str(mym.get("value") or "").strip() == url and mym.get("name") == "Miam":
            return "déjà"
        await _requete("PATCH", f"/contents/{mym['id']}", corps={"value": url, "name": "Miam"})
        return "ok"
    attrs = {"name": "Miam", "value": url, "effect": "button-pulsing", "cardType": "simple", "is18Plus": True}
    if image and any(c.get("image") for c in cartes):                   # cartes illustrées (Chloé) : même image que ses autres Miam
        attrs["imageUrl"] = image
    nouveau = await _requete("POST", f"/links/{link_id}/contents", corps=attrs)
    nid = (nouveau or {}).get("id")
    if nid and cartes:
        ordre = [nid] + [c["id"] for c in sorted(cartes, key=lambda c: c.get("position") or 0)]
        for methode, chemin in (("PUT", f"/links/{link_id}/contents/reorder"), ("POST", f"/links/{link_id}/contents/reorder")):
            try:
                await _requete(methode, chemin, corps={"order": ordre})
                return "ok"
            except RuntimeError:
                continue
        return "ok (Miam ajouté sous OnlyFriends : à remonter dans GAML)"
    return "ok"


# ------------------------------------------------------------------ calculs
# 09/10 (Gaëtan : « la paie se fait le 5 et le 20 de chaque mois ; ils sont payés sur les périodes du 5 au 19 inclus et du 20 au 4
# inclus ») : `20` = 5 → 19 du mois (payé le 20) ; `5` = 20 du mois précédent → 4 du mois (payé le 5). « J'ai commencé la
# rémunération au clic le 5 octobre » : la première période au clic est le 5 → 19/10/2026 (CLICS_DEPUIS), aucune exception.


def _mois_prec(annee: int, m: int) -> tuple:
    return (annee - 1, 12) if m == 1 else (annee, m - 1)


def _mois_suiv(annee: int, m: int) -> tuple:
    return (annee + 1, 1) if m == 12 else (annee, m + 1)


def periode(cle: str, mois: str = "") -> tuple:
    """`20` : 5 → 19 de `mois` (paie du 20) ; `5` : 20 du mois précédent → 4 de `mois` (paie du 5)."""
    ref = _aujourdhui()
    annee, m = (int(mois[:4]), int(mois[5:7])) if mois else (ref.year, ref.month)
    if cle == "20":
        return date(annee, m, 5), date(annee, m, 19)
    ap, mp = _mois_prec(annee, m)
    return date(ap, mp, 20), date(annee, m, 4)


def prochaine_paie(ref: date) -> date:
    """Le prochain jour de paie : le 5 pour les jours 1 à 4 (fin de la période 20 → 4), le 20 pour les jours 5 à 19, le 5 du
    mois suivant à partir du 20."""
    if ref.day <= 4:
        return date(ref.year, ref.month, 5)
    if ref.day <= 19:
        return date(ref.year, ref.month, 20)
    a, m = _mois_suiv(ref.year, ref.month)
    return date(a, m, 5)


def periode_en_cours() -> tuple:
    ref = _aujourdhui()
    if ref.day <= 4:
        return periode("5", ref.strftime("%Y-%m"))
    if ref.day <= 19:
        return periode("20", ref.strftime("%Y-%m"))
    a, m = _mois_suiv(ref.year, ref.month)
    return periode("5", f"{a:04d}-{m:02d}")


def _ancien_regime(fiche: dict) -> str:
    """La règle d'avant le 08/10 : fixe pour les signés d'avant le 24/09, clic après, `!paie` par-dessus."""
    return fiche.get("paie") or ("clic" if str(fiche.get("date", ""))[:10] >= "2026-09-24" else "fixe")


def _prenom_uid(uid: str, fiche: dict) -> str:
    m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
    nom = str(getattr(m, "display_name", "") or fiche.get("prenom") or "")
    return _n_note(nom.split()[0]) if nom.split() else ""


def regime(uid: str) -> str:
    """« clic » ou « fixe ». 08/10 (Gaëtan : « tout le monde au variable sauf Caroline, Lilian, Josué, Yves et Rianah. Julien
    montage vidéo YTB et Jonas manageur ») : tout le monde au clic, sauf les prénoms de PAIE_FIXE signés avant la décision (un
    nouveau Julien signé après est au clic). Un `!paie @clipper clic|fixe` posé depuis le 08/10 passe par-dessus."""
    fiche = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(uid), {})
    if fiche.get("paie") and str(fiche.get("paie_le", ""))[:10] >= PAIE_DECISION:
        return fiche["paie"]
    if str(fiche.get("date", ""))[:10] > PAIE_DECISION:
        return "clic"
    return "fixe" if _prenom_uid(str(uid), fiche) in PAIE_FIXE else "clic"


def debut_clic(uid: str, d: dict = None) -> str:
    """08/10 : un clipper passé du fixe au clic par la décision du 08/10 est payé au clic à partir de BASCULE_CLIC (09/10 : le 05/10 ;
    ce qui précède reste au fixe : jamais payé deux fois). '' pour les autres. Revue du 08/10 : un `!paie clic` fige son propre plancher
    (`clic_depuis`, le jour de la bascule) ; une fiche absente du registre (sorti, ancien hors registre) se date par son premier
    lien, comme dans l'app."""
    fiche = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(uid))
    if fiche is None:
        try:
            d = d if d is not None else _lire()
            dates = sorted(str(i.get("depuis") or "") for i in d.get("liens", {}).values() if str(i.get("uid")) == str(uid))
        except Exception:                                               # noqa: BLE001
            dates = []
        fiche = {"date": dates[0] if dates else ""}
    if regime(uid) != "clic":
        return ""
    if fiche.get("clic_depuis"):
        dc = str(fiche["clic_depuis"])[:10]
        # 09/10 (revue) : un `!paie clic` redondant tapé entre le déploiement du 08/10 et celui du 09/10 a figé l'ancien plancher
        # (le 08/10) ; hors PAIE_FIXE, la décision du 09/10 paie au clic depuis le 05/10
        if dc == PAIE_DECISION and _prenom_uid(str(uid), fiche) not in PAIE_FIXE:
            return min(dc, BASCULE_CLIC)
        return dc
    if _ancien_regime(fiche) == "fixe" and not str(fiche.get("paie_le", ""))[:10] >= PAIE_DECISION:
        return BASCULE_CLIC
    return ""


def _debut_paie(uid: str, debut: date, d: dict = None) -> date:
    dc = debut_clic(uid, d)
    return max(debut, _jour(dc)) if dc else debut


def liens_de(d: dict, uid: str) -> list:
    return [lid for lid, info in d["liens"].items() if str(info.get("uid")) == str(uid) and not info.get("archive")]


def releve_seul(info: dict) -> bool:
    """09/10 (dashboard) : fiche créée seulement pour relever le lien (`releve`) : page de créatrice, /ytb, /fb, lien jamais
    attribué. Personne ne l'a jamais eu : pour l'attribution (associer_auto, orphelins, sortie par la note), c'est comme si le bot
    ne le connaissait pas."""
    info = info or {}
    return (bool(info.get("releve")) and info.get("par") == "releve"
            and not (str(info.get("uid") or "") or info.get("suivi") or info.get("libere") or info.get("hors_clipping")
                     or info.get("ancien") or info.get("ancien_uid")))


def a_relever(info: dict, jour_iso: str = "") -> bool:
    """09/10 (dashboard, contrat C2) : le lien est-il relevé chaque jour ? Tout lien actif connu du bot : attribué, suivi par le
    rapport, libéré, hors clipping (Metricool), ou marqué `releve` (pages de créatrice, /ytb, /fb, liens jamais attribués). Jamais
    un lien effacé dans GAML, ni un lien désactivé sans clipper (aucune visite possible), ni un lien introuvable aujourd'hui (404 :
    retenté demain, rien d'écrit)."""
    info = info or {}
    if info.get("supprime_gaml") or (jour_iso and str(info.get("introuvable") or "") == jour_iso):
        return False
    if str(info.get("uid") or "") or info.get("suivi"):
        return True                                                     # inchangé : les liens payés ou suivis
    if info.get("desactive"):
        return False
    return bool(info.get("libere") or info.get("hors_clipping") or info.get("releve") or info.get("ancien"))


def marquer_releves(d: dict, liens: list) -> int:
    """09/10 (dashboard, contrat C2) : chaque lien GAML actif de la liste est relevé. Un lien inconnu du bot reçoit une fiche
    `{"uid": "", "releve": true, "par": "releve", …}` (créatrice, nom, slug, URL et note quand la liste les porte) ; une fiche
    existante qui ne serait plus relevée (ancien lien retiré à la main) reçoit `releve`. Une fiche `releve` seule suit la liste
    (note, nom, URL, désactivation dans GAML) : personne d'autre ne l'écrit. 11/10 : une fiche `supprime_gaml` dont le lien est dans
    la liste perd ce marquage (le lien existe). Renvoie le nombre de fiches créées ou changées. L'appelant écrit `d`."""
    n = 0
    fiches = d.setdefault("liens", {})
    for l in liens or []:
        lid = l.get("id")
        if not lid:
            continue
        nom = str(l.get("name") or "")
        info = fiches.get(lid)
        if info is None:
            if l.get("enabled") is False:
                continue                                                # un lien éteint ne fait aucune visite
            info = {"uid": "", "releve": True, "par": "releve", "creatrice": nom.split()[0] if nom.split() else ""}
            for cle_l, cle_f in (("name", "nom"), ("slug", "slug"), ("url", "url"), ("note", "note")):
                if l.get(cle_l):
                    info[cle_f] = l.get(cle_l)
            fiches[lid] = info
            n += 1
            continue
        if info.get("supprime_gaml"):
            # 11/10 (contre-vérification CLICS, passe 3) : un lien présent dans /links existe : le marquage « effacé » (posé sur une
            # liste partielle, un 404 passager) est levé, le lien est de nouveau relevé (rattraper relit ses jours manquants)
            journal.info("Lien GAML %s de nouveau dans /links : marquage « effacé » du %s levé", lid, info.get("supprime_gaml"))
            info.pop("supprime_gaml", None)
            n += 1
        if releve_seul(info):
            avant = dict(info)
            for cle_l, cle_f in (("name", "nom"), ("slug", "slug"), ("url", "url"), ("note", "note")):
                if l.get(cle_l) is not None and (l.get(cle_l) or cle_f in info):
                    info[cle_f] = l.get(cle_l)
            if l.get("enabled") is False:
                info["desactive"] = info.get("desactive") or "gaml"
            elif info.get("desactive") == "gaml":
                info.pop("desactive", None)
            n += info != avant
            continue
        if l.get("enabled") is not False and not a_relever(info) and not (info.get("supprime_gaml") or info.get("desactive")):
            info["releve"] = True
            n += 1
    return n


def _n_note(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def liberer_liens(d: dict, uid: str, prenom: str = "", uids_connus=None) -> list:
    """28/09 (sortie automatique) : les liens d'un sortant restent à sa créatrice, sans clipper (uid vide), prêts pour le suivant.
    Par uid, ou (28/09 soir, Marias parti du serveur) par la note « Clipping Prénom » quand le lien n'a pas de clipper connu :
    uid vide, ou uid absent de `uids_connus` (les fiches encore au registre). Un lien déjà libre n'est pas retouché.
    Renvoie les identifiants libérés. L'appelant écrit `d`."""
    libres = []
    cible = _n_note(f"clipping {prenom}") if prenom else ""
    connus = {str(u) for u in uids_connus} if uids_connus is not None else None
    for lid, info in d.get("liens", {}).items():
        uid_l = str(info.get("uid") or "")
        if not uid_l and info.get("libere"):
            continue
        par_uid = bool(str(uid)) and uid_l == str(uid)
        inconnu = not uid_l or (connus is not None and uid_l not in connus)
        # 09/10 (dashboard) : une fiche seulement relevée (jamais attribuée) n'est pas libérée par la note : avant le relevé de tous
        # les liens, le bot ne la connaissait pas (un « Clipping Eddy » laissé sans clipper, faute de candidat unique, est peut-être
        # celui de l'autre Eddy)
        par_note = bool(cible) and inconnu and _n_note(info.get("note")) == cible and not releve_seul(info)
        if par_uid or par_note:
            info.update({"uid": "", "libere": _aujourdhui().isoformat(), "ancien": prenom or info.get("note", "")})
            libres.append(lid)
    return libres


def note_du_sortant(info: dict, note) -> bool:
    """09/10 : le lien est libéré et sa note GAML est encore « Clipping <le sortant> » (`ancien`) — pas encore renommée, pas
    réattribuée à la main à quelqu'un d'autre. Un tel lien n'est jamais rattaché par prénom (`associer_auto`, lien « existant »
    de l'onboarding) : un homonyme signé plus tard hériterait des Reels de l'ancien, et l'app additionnerait les deux."""
    if str((info or {}).get("uid") or "") or not (info or {}).get("libere") or info.get("hors_clipping"):
        return False
    p = _n_note(_prenom_note(note)).split()
    ancien = str(info.get("ancien") or "")
    a = _n_note(_prenom_note(ancien) or ancien).split()
    return bool(p) and bool(a) and p[0] != "libre" and p[0] == a[0]


def numero_metricool(liens, repreneur: str) -> int:
    """Le prochain numéro des liens « Rianah Metricool N » (« Rianah Metricool » seul = 1, « Rianah Metricool 3 (ex-Hasina) » = 3) :
    1 s'il n'y en a aucun. Lu dans les notes GAML (`liens`)."""
    cible = _n_note(repreneur).split()
    if not cible:
        return 1
    nums = []
    for l in liens or []:
        mots = re.sub(r"\(.*?\)", " ", _n_note(l.get("note"))).split()
        if mots[:len(cible) + 1] == cible + ["metricool"]:
            suite = mots[len(cible) + 1:]
            nums.append(int(suite[0]) if suite and suite[0].isdigit() else 1)
    return max(nums) + 1 if nums else 1


RENOMMER_MAX = int(os.environ.get("CLICS_RENOMMER_MAX", "10") or 10)     # notes GAML renommées au plus par passage


async def renommer_liberes(liens: list, seulement=None, maximum: int = None) -> list:
    """09/10 (homonymes : un deuxième Julien signé) : la note GAML d'un lien libéré passe de « Clipping Eddy » à « Clipping libre
    (ex-Eddy) ». Le lien reste dans le clipping (`lien_libre` le redonne au suivant, `reprendre_lien` pose « Clipping Prénom »),
    mais ni l'app ni `associer_auto` ne le donnent plus à un homonyme. Revue du 09/10 : candidats choisis sur la liste GAML de la
    passe, puis, lien par lien, la fiche relue et la note relue dans GAML juste avant le PATCH (une note changée à la main entre-temps
    n'est jamais écrasée) ; aucun verrou tenu pendant les appels réseau ; `maximum` tentatives par passage, arrêt au premier refus
    de GAML (le reste au passage suivant). Les liens « suivi » par le rapport du manager sont renommés comme les autres (seul un lien
    jamais attribué par le bot, créé par le rapport, est laissé). Renvoie les lignes pour l'admin."""
    maximum = RENOMMER_MAX if maximum is None else maximum
    par_id = {l.get("id"): l for l in liens or [] if l.get("id") and "note" in l}    # note absente de la réponse : on ne juge pas
    lignes, essais = [], 0
    for lid, info in list(_lire().get("liens", {}).items()):
        if essais >= maximum:
            break
        l = par_id.get(lid)
        if l is None or (seulement is not None and lid not in seulement) or info.get("supprime_gaml") \
                or (info.get("suivi") and info.get("par") == "rapport"):
            continue
        if not note_du_sortant(info, str(l.get("note") or "").strip()):
            continue
        essais += 1
        try:
            vivant = await lien_detail(lid)                             # la note de maintenant, pas celle du début de la passe
            note = str((vivant or {}).get("note") or "").strip()
            if not note_du_sortant((_lire().get("liens") or {}).get(lid) or {}, note):
                continue
            nouvelle = f"Clipping libre (ex-{_prenom_note(note)})"
            await _requete("PATCH", f"/links/{lid}", corps={"note": nouvelle})
        except RuntimeError as erreur:
            journal.warning("Lien libéré %s : note GAML non renommée (%s), le reste au passage suivant", lid, erreur)
            break
        async with verrou_liens:                                        # écrit sur une relecture, sans await entre lecture et écriture
            frais = _lire()
            g = frais.get("liens", {}).get(lid)
            if g is not None and not str(g.get("uid") or ""):
                g["note"] = nouvelle
                g.pop("suivi", None)
                _ecrire(frais)
        lignes.append(f"· {str(info.get('creatrice') or '?').title()} · « {note} » → « {nouvelle} »")
    return lignes


def lien_libre(d: dict, creatrice: str):
    """(id, fiche) d'un lien libéré de cette créatrice, ou None. 08/10 (ménage GAML) : jamais un lien effacé dans GAML ni un lien
    passé hors clipping (note GAML changée à la main, ex. Metricool) ; un lien encore actif d'abord (il ne prend pas de place
    de plus dans le forfait), un lien désactivé par le ménage ensuite (`reprendre_lien` le réactive). 09/10 (revue CLICS) : jamais un
    lien introuvable dans GAML (404 au relevé) aujourd'hui ou hier : il serait posé mort dans la bio du suivant."""
    cible = (creatrice or "").split()[0].lower() if creatrice else ""
    if not cible:
        return None
    recent = (_aujourdhui() - timedelta(days=1)).isoformat()
    libres = [(lid, info) for lid, info in d.get("liens", {}).items()
              if not str(info.get("uid") or "") and info.get("libere") and not info.get("supprime_gaml") and not info.get("hors_clipping") and not info.get("archive")
              and str(info.get("introuvable") or "")[:10] < recent
              and str(info.get("creatrice") or "").lower().startswith(cible)]
    libres.sort(key=lambda li: bool(li[1].get("desactive")))
    return libres[0] if libres else None


async def reprendre_lien(d: dict, lid: str, uid: str, prenom: str, creatrice: str) -> bool:
    """Le lien d'un sortant passe au suivant : uid, `depuis` = aujourd'hui (ses visites commencent là), note « Clipping Prénom »
    (aussi côté GAML, sans bloquer si l'API refuse). 08/10 : réactivé côté GAML s'il avait été désactivé par le ménage ; si
    GAML refuse la réactivation (forfait plein), rien n'est repris (jamais un lien mort dans une bio) et on renvoie False.
    L'appelant écrit `d`."""
    info = d["liens"][lid]
    if info.get("archive"):
        return False
    avant = dict(info)
    try:
        await _requete("PATCH", f"/links/{lid}", corps={"note": f"Clipping {prenom}", "enabled": True})
    except RuntimeError as erreur:
        if info.get("desactive"):
            journal.warning("Lien %s désactivé non repris pour %s : réactivation refusée (%s)", lid, prenom, erreur)
            info["reactivation_echouee"] = _aujourdhui().isoformat()
            return False
        journal.warning("Lien %s repris pour %s : note GAML non mise à jour (%s)", lid, prenom, erreur)
    info.update({"uid": str(uid), "depuis": _aujourdhui().isoformat(), "note": f"Clipping {prenom}", "creatrice": creatrice.split()[0],
                 "par": "reprise", "repris_de": avant.get("ancien", ""), "libere": ""})
    for cle in ("ancien", "desactive", "reactivation_echouee"):
        info.pop(cle, None)
    return True


async def menage_liens(d: dict, seuil: int = None, jours: int = 7) -> list:
    """08/10 (Gaëtan : « on fait le ménage avec les clippeurs qui partent ») : un lien libéré qui ne fait plus de visites est
    désactivé dans GAML (un lien désactivé ne compte pas dans le forfait). Jamais effacé : il reste à sa créatrice, avec son
    tracking, et `reprendre_lien` le réactive pour le suivant. Un lien libéré qui travaille encore (les Reels de l'ancien
    amènent des visites à la créatrice) reste actif jusqu'à ce qu'il tombe sous le seuil. Renvoie les lignes pour l'admin.
    L'appelant écrit `d`."""
    seuil = MENAGE_SEUIL if seuil is None else seuil
    fin = _aujourdhui() - timedelta(days=1)
    debut = fin - timedelta(days=jours - 1)
    lignes = []

    def _a_menager(i):
        return not (str(i.get("uid") or "") or not i.get("libere") or i.get("desactive") or i.get("supprime_gaml")
                    or i.get("hors_clipping") or i.get("suivi"))
    for lid, info in list(d.get("liens", {}).items()):
        if not _a_menager(info):
            continue
        try:
            n = await visiteurs_periode(lid, debut, fin)
        except RuntimeError as erreur:
            journal.warning("Ménage %s : visites illisibles (%s)", lid, erreur)
            continue
        if n >= seuil:
            continue
        async with verrou_liens:                                        # relu juste avant : repris entre-temps → on n'y touche pas
            frais = _lire()
            f = frais.get("liens", {}).get(lid)
            if f is None or not _a_menager(f):
                info.update(f or {})
                continue
            try:
                await _requete("PATCH", f"/links/{lid}", corps={"enabled": False})
            except RuntimeError as erreur:
                journal.warning("Ménage %s : désactivation refusée (%s)", lid, erreur)
                continue
            f["desactive"] = _aujourdhui().isoformat()
            _ecrire(frais)
            info.update(f)
        lignes.append(f"· {str(info.get('creatrice') or '?').title()} · ex-{info.get('ancien') or info.get('note') or '?'} · "
                      f"{n} visiteur(s) en {jours} jours → désactivé")
        journal.info("Ménage GAML : lien %s (%s) désactivé, %s visiteurs en %s jours", lid, info.get("ancien"), n, jours)
    return lignes


ORPHELINS_MAX = int(os.environ.get("CLICS_ORPHELINS_MAX", "8") or 8)       # liens rattrapés au plus par passage


async def rattraper_orphelins(d: dict, liens: list, seuil: int = None, jours: int = 7) -> list:
    """08/10 (premier ménage : 1 seul lien désactivé sur 12 liens morts) : des clippers sont partis sans que leur lien soit
    libéré (sortis avant la libération automatique, ou jamais rattachés au bot). Deux cas, rattrapés comme une sortie (`libere`),
    que le ménage désactive ensuite s'ils dorment :
    1. lien rattaché à un uid qui n'est plus au registre ET plus sur le serveur ;
    2. lien GAML « Clipping Prénom » inconnu du bot, dont le prénom n'est ni au registre, ni au roster, ni exclu.
    Garde-fous : jamais un lien qui ramène encore `seuil` visiteurs sur 7 jours (son clipper travaille), jamais avec un registre
    presque vide (lecture ratée), ORPHELINS_MAX au plus par passage. L'appelant écrit `d`. Renvoie les lignes pour l'admin."""
    seuil = MENAGE_SEUIL if seuil is None else seuil
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
    if len(registre) < 5:
        journal.warning("Orphelins GAML : registre presque vide (%s fiches), rien rattrapé", len(registre))
        return []
    membre_de = _deps.get("membre_par_id") or (lambda u: None)
    connus = set()
    for uid, fiche in registre.items():
        m = membre_de(uid)
        for nom in (getattr(m, "display_name", "") if m is not None else "", fiche.get("prenom") or ""):
            if str(nom).split():
                connus.add(_n_note(str(nom).split()[0]))
    try:
        import roster as _roster
        connus |= {_n_note(x) for x in _roster.noms_actifs()}
    except Exception:                                                   # noqa: BLE001
        pass
    fin = _aujourdhui() - timedelta(days=1)
    debut = fin - timedelta(days=jours - 1)
    candidats = []
    for lid, info in d.get("liens", {}).items():                        # 1. un uid parti
        uid = str(info.get("uid") or "")
        if uid and uid not in registre and membre_de(uid) is None and not info.get("suivi") and not info.get("hors_clipping"):
            candidats.append((lid, info.get("creatrice") or "", _prenom_note(info.get("note")) or info.get("note") or "?", info))
    for l in liens or []:                                               # 2. un lien « Clipping Prénom » inconnu du bot
        lid, prenom = l.get("id"), _prenom_note(l.get("note"))
        connu = lid in d.get("liens", {}) and not releve_seul(d["liens"][lid])   # 09/10 : une fiche de relevé seule = inconnu
        if (not lid or connu or not prenom or l.get("enabled") is False
                or _n_note(prenom) in connus or _n_note(prenom) in CLICS_EXCLURE):
            continue
        creatrice = str(l.get("name") or "").split()[0] if str(l.get("name") or "").split() else ""
        candidats.append((lid, creatrice, prenom, None, l))
    lignes = []
    for c in candidats[:ORPHELINS_MAX * 2]:
        if len(lignes) >= ORPHELINS_MAX:
            break
        lid, creatrice, prenom, info = c[0], c[1], c[2], c[3]
        try:
            n = await visiteurs_periode(lid, debut, fin)
        except RuntimeError as erreur:
            journal.warning("Orphelin %s : visites illisibles (%s)", lid, erreur)
            continue
        if n >= seuil:
            continue                                                    # il ramène du monde : quelqu'un s'en sert, on n'y touche pas
        async with verrou_liens:                                        # appliqué sur une relecture, jamais sur la copie de la boucle
            frais = _lire()
            liens_f = frais.setdefault("liens", {})
            if info is None:
                if lid in liens_f and not releve_seul(liens_f[lid]):
                    continue                                            # rattaché entre-temps (onboarding, associer_auto)
                l = c[4]
                liens_f[lid] = {"uid": "", "note": l.get("note"), "url": l.get("url") or "", "creatrice": creatrice,
                                "depuis": CLICS_DEPUIS, "par": "orphelin", "libere": _aujourdhui().isoformat(), "ancien": prenom}
            else:
                f = liens_f.get(lid)
                if f is None or str(f.get("uid") or "") != str(info.get("uid") or ""):
                    continue                                            # changé entre-temps
                f.update({"ancien_uid": str(f.get("uid") or ""), "uid": "", "libere": _aujourdhui().isoformat(), "ancien": prenom})
            _ecrire(frais)
            d.setdefault("liens", {})[lid] = dict(liens_f[lid])
        lignes.append(f"· {str(creatrice or '?').title()} · ex-{prenom} : {n} visiteur(s) en {jours} jours, clipper parti → libéré")
    return lignes


def synchroniser_notes(d: dict, liens: list) -> list:
    """08/10 (comptes d'Hasina passés sur Metricool, gérés par Rianah) : une note GAML changée à la main qui n'est plus
    « Clipping Prénom » sort le lien du clipping (jamais repris pour un nouveau clipper, jamais désactivé par le ménage).
    La note redevient « Clipping … » → le lien revient. Renvoie les lignes pour l'admin (seulement les changements)."""
    lignes = []
    par_id = {l.get("id"): l for l in liens or [] if l.get("id") and "note" in l}    # note absente de la réponse : on ne juge pas
    for lid, info in d.get("liens", {}).items():
        # revue CLICS du 09/10 : un lien passé chez le repreneur Metricool dont GAML a refusé la note (`note_attendue`) garde son
        # ancienne note « Clipping <sortant> » : il n'est pas « revenu au clipping » (poser_notes_attendues retente la note). Une
        # note changée à la main entre-temps (ni l'ancienne, ni l'attendue) gagne : l'attente est levée, la règle normale s'applique.
        l = par_id.get(lid)
        if l is None or not info.get("note_attendue"):
            continue
        note = str(l.get("note") or "").strip()
        if note == str(info["note_attendue"]).strip() or not _note_du_detenteur(info, note):
            info.pop("note_attendue", None)
    attente = {lid for lid, info in d.get("liens", {}).items() if info.get("note_attendue")}
    sortants = [lid for lid, info in d.get("liens", {}).items()
                if lid in par_id and (str(info.get("uid") or "") or info.get("libere")) and not info.get("hors_clipping")
                and not _prenom_note(str(par_id[lid].get("note") or ""))]
    if len(sortants) > 3:                                               # garde-fou : jamais une sortie en masse sur une réponse GAML bizarre
        journal.warning("Notes GAML : %s liens sortiraient du clipping d'un coup, rien appliqué", len(sortants))
        if d.get("alerte_notes") == _aujourdhui().isoformat():
            return []                                                   # l'alerte une fois par jour
        d["alerte_notes"] = _aujourdhui().isoformat()
        return [f"⚠️ {len(sortants)} liens de clippers n'ont plus de note « Clipping Prénom » dans GAML d'un coup : rien appliqué, "
                "à vérifier (une note changée à la main sort le lien du clipping, trois au plus par passage)."]
    for lid, info in d.get("liens", {}).items():
        l = par_id.get(lid)
        if info.get("archive") or l is None or lid in attente or not (str(info.get("uid") or "") or info.get("libere") or info.get("hors_clipping")):
            continue                                                    # liens de la créatrice / Metricool suivis par le rapport : pas du clipping
        note = str(l.get("note") or "").strip()
        hors = not _prenom_note(note)
        if hors and not info.get("hors_clipping"):
            # Détaché de son clipper comme à une sortie (uid vidé, plus de relevé ni de paie au clic dessus), jamais libéré.
            uid_av = str(info.get("uid") or "")
            info.update({"hors_clipping": note or "(note vide)", "hors_depuis": _aujourdhui().isoformat(), "uid": "", "libere": "",
                         "ancien": info.get("ancien") or _prenom_note(info.get("note")) or str(info.get("note") or ""),
                         "note": note})
            if uid_av:
                info["ancien_uid"] = uid_av
            lignes.append(f"· {str(info.get('creatrice') or '?').title()} · ex-{info['ancien'] or '?'} devenu « {note or '(vide)'} » : "
                          f"sorti du clipping, plus compté pour un clipper ni repris par le bot")
        elif hors and info.get("hors_clipping") and note and note != str(info.get("note") or ""):
            # 09/10 (« Rianah reprend ses liens Metricool ») : toujours hors clipping, la note change de main
            lignes.append(f"· {str(info.get('creatrice') or '?').title()} · « {info.get('note') or info.get('hors_clipping')} » devenu « {note} »")
            info.update({"hors_clipping": note, "note": note})
        elif not hors and info.get("hors_clipping"):
            info.pop("hors_clipping", None)
            info.pop("ancien", None)                                    # 09/10 (revue) : décision à la main, jamais renommé « libre »
            info["note"] = note                                         # `associer_auto` le rattache au membre de ce prénom
            if not str(info.get("uid") or ""):
                info["libere"] = _aujourdhui().isoformat()              # sinon il redevient libre pour le suivant
            lignes.append(f"· {str(info.get('creatrice') or '?').title()} · « {note} » : revenu au clipping")
        elif not hors and str(info.get("uid") or "") and _n_note(_prenom_note(note)).startswith("libre"):
            # 09/10 (revue) : la note dit « libre » mais le bot croit le lien encore attribué (écriture concurrente) → libéré
            m_ex = re.search(r"\(ex-([^)]*)\)", note)
            info.update({"ancien_uid": str(info.get("uid")), "uid": "", "libere": _aujourdhui().isoformat(), "note": note,
                         "ancien": (m_ex.group(1).strip() if m_ex else "") or str(info.get("ancien") or "")})
            lignes.append(f"· {str(info.get('creatrice') or '?').title()} · « {note} » : noté libre dans GAML, détaché de son clipper")
    return lignes


def _note_du_detenteur(info: dict, note) -> bool:
    """La note GAML `note` est-elle encore « Clipping <l'ancien détenteur> » (`ancien`) ?"""
    p = (_n_note(_prenom_note(note)).split() or [""])[0]
    ancien = str((info or {}).get("ancien") or "")
    a = (_n_note(_prenom_note(ancien) or ancien).split() or [""])[0]
    return bool(p) and p == a


def _membres_du_prenom(prenom: str, creatrice: str = "", sauf: str = "") -> tuple:
    """09/10 (revue CLICS, contrat C6(d)) : les membres SIGNÉS présents sur le serveur dont le premier mot du pseudo vaut `prenom`
    (la recherche d'associer_auto), sauf l'uid `sauf`. Renvoie (tous ces uid, ceux de la créatrice `creatrice`). 10/10 (revue CLICS,
    2e passe) : plus de repli « seul candidat » d'une autre créatrice (un Eddy signé chez Chloé recevait le lien de Sophie d'un
    sortant)."""
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
    membre_de = _deps.get("membre_par_id") or (lambda u: None)
    normaliser = _deps.get("normaliser") or _n_note
    cible = normaliser(str(prenom or "").strip())
    if not cible:
        return [], []
    candidats = []
    for u, fiche in (registre or {}).items():
        if str(u) == str(sauf or ""):
            continue
        m = membre_de(u)
        if m is None or not ((fiche or {}).get("equipe") or (fiche or {}).get("creatrice")):
            continue
        nom = str(getattr(m, "display_name", "") or "")
        if normaliser(nom.split()[0] if nom.split() else "") != cible:
            continue
        candidats.append((str(u), normaliser(fiche.get("creatrice") or "") == normaliser(creatrice or "")))
    return [u for u, _ in candidats], [u for u, meme in candidats if meme]


async def passer_liens_metricool(uid: str, prenom: str, repreneur: str, vivants: dict, dus: bool = False,
                                 notes_lues: bool = True) -> dict:
    """09/10 (Gaëtan : « Rianah reprend ses liens Metricool ainsi que ses liens de tracking OF MYM ») ; revue CLICS du 09/10 : la
    fonction commune de `!monteur` et de `!sortie` sans pool quand les comptes créés du membre partent sur Metricool (avant, `!sortie`
    libérait le lien : le clipper suivant de la créatrice le reprenait et était payé pour le trafic des comptes partis sur Metricool).
    Les liens du membre `uid` (par uid seulement : jamais ceux d'un homonyme) suivent ses comptes chez `repreneur` : note GAML
    « <repreneur> Metricool N (ex-Prénom) », détachés hors clipping comme une note changée à la main (uid vidé, `ancien_uid` ; jamais
    redonnés à un clipper, jamais ménagés) ; les cartes Miam et OnlyFriends (ses trackings) restent posées. Un lien déjà sorti du
    clipping à la main est seulement détaché. Sans repreneur, les liens sont libérés pour le suivant (« Clipping libre (ex-Prénom) »).
    GAML refuse la note : le lien est détaché quand même (`note_attendue`, retentée à chaque passe horaire par poser_notes_attendues ;
    jamais libéré ni « revenu au clipping » entre-temps). `dus` : ses visites au clic jusqu'à hier lui restent dues (garder_dus,
    `!sortie`). `vivants` = {id: lien de la liste GAML}, lue AVANT l'appel (notes_gaml_de). À appeler avant le retrait du registre.
    Revue CLICS du 09/10 (suite) :
    1. contrat C6(d) : « lien d'un autre clipper » décidé sur les identifiants, jamais sur le prénom du pseudo. Le lien est au membre
       quand la note GAML porte son prénom, ou la note posée par le bot pour lui (fiche `note` : « Clipping Eddy » d'un Eddy devenu
       « Eddie » ou « 🌸Eddy »), ou un prénom qu'aucun AUTRE membre signé ne porte. Il est à l'autre seulement quand la note désigne
       un autre membre signé (uid différent) : rattaché à lui s'il est seul (comme associer_auto), sinon détaché sans être libéré
       (jamais redonné au suivant, à trancher avec `!lien`). Avant : libéré dès que le prénom du pseudo différait, donc redonné au
       clipper suivant avec le trafic des comptes partis sur Metricool ;
    2. aucun appel réseau sous verrou_liens : le plan sur une lecture, les PATCH hors verrou, le résultat appliqué sur une relecture
       sans await entre la lecture et l'écriture ; un lien changé de main entre-temps n'est pas touché ;
    3. `dus` posés pour tous ses liens, ceux effacés de GAML compris (avant : sautés avant garder_dus, visites perdues) ;
    4. un lien introuvable dans GAML (`vivants[lid]["introuvable"]`, 404 lu par notes_gaml_de) est marqué `supprime_gaml` et détaché,
       jamais libéré (avant : vu « noté au prénom d'un autre », libéré, et redonné mort au suivant) ;
    5. `notes_lues=False` (GAML illisible pendant `!sortie`) : rien n'est bloqué, ses liens sont détachés vers le repreneur avec la note
       en attente (`note_attendue`, posée à la passe horaire si GAML dit encore « Clipping <lui> » ; une note changée à la main
       entre-temps gagne, comme pour un refus de GAML).
    10/10 (revue CLICS, 2e passe, C6(d)) : le lien n'est « à l'autre » que si la fiche porte une note (posée par le bot) que GAML
    contredit ET que le prénom de la note GAML est celui d'un membre signé de la MÊME créatrice que le lien ; sinon l'uid l'emporte
    (le lien suit le sortant, ligne admin « note GAML … inattendue, à vérifier »). Avant : une fiche sans note (`!lien` quand la liste
    GAML ne portait pas la note) et un pseudo changé suffisaient à rattacher le lien de Sophie au seul « Eddy » signé, chez Chloé.
    Renvoie {"repris": [lignes], "liberes": [ids], "refus": [lignes]}."""
    uid, repreneur = str(uid or ""), str(repreneur or "").strip()
    repris, refus, liberes = [], [], []
    if not uid:
        return {"repris": repris, "liberes": liberes, "refus": refus}
    vivants = vivants or {}
    p_sortant = (_n_note(prenom).split() or [""])[0]
    jour = _aujourdhui().isoformat()
    # 1. le plan, sur une lecture (aucun verrou : rien n'est écrit ici)
    d0 = _lire()
    numero = max(numero_metricool(vivants.values(), repreneur), numero_metricool(d0.get("liens", {}).values(), repreneur))
    plan = []
    for lid in liens_de(d0, uid):
        info = d0["liens"][lid]
        vivant = vivants.get(lid) or {}
        note_v = str(vivant.get("note") or "").strip()
        lue = notes_lues and "note" in vivant
        p = {"lid": lid, "note": note_v, "nouvelle": "", "autres": [], "surs": [], "inattendue": False}
        if info.get("supprime_gaml") or vivant.get("introuvable"):
            p["action"] = "efface"
        elif lue and not _prenom_note(note_v):
            p["action"] = "main"                                        # déjà sortie du clipping à la main
        else:
            if lue:
                p_note = _prenom_note(note_v)
                if (_n_note(p_note).split() or [""])[0] != p_sortant and _n_note(note_v) != _n_note(info.get("note")):
                    creatrice = (str(vivant.get("name") or "").split() or [str(info.get("creatrice") or "")])[0]
                    meme = _membres_du_prenom(p_note, creatrice, sauf=uid)[1]
                    if meme and str(info.get("note") or "").strip():
                        p["autres"] = p["surs"] = meme                  # note du bot contredite, membre de la même créatrice
                    else:
                        p["inattendue"] = True                          # 10/10 (C6(d)) : l'uid l'emporte, l'admin vérifie
            if p["autres"]:
                p["action"] = "autre"
            elif not repreneur:
                p["action"] = "libre"
            else:
                p["action"] = "patch" if lue else "attente"
                p["nouvelle"] = f"{repreneur} Metricool{f' {numero}' if numero > 1 else ''} (ex-{prenom})"
                numero += 1
        plan.append(p)
    # 2. les notes GAML, hors verrou
    erreurs = {}
    for p in plan:
        if p["action"] != "patch":
            continue
        try:
            await _requete("PATCH", f"/links/{p['lid']}", corps={"note": p["nouvelle"]})
        except Exception as erreur:                                     # noqa: BLE001
            erreurs[p["lid"]] = str(erreur)[:80] or type(erreur).__name__
    # 3. le résultat, sur une relecture, sans await entre la lecture et l'écriture
    async with verrou_liens:
        d_l = _lire()
        for p in plan:
            lid, note_v, nouvelle = p["lid"], p["note"], p["nouvelle"]
            info = d_l.get("liens", {}).get(lid)
            cr_l = str((info or {}).get("creatrice") or "?").title()
            if info is None or str(info.get("uid") or "") != uid:
                refus.append(f"lien {cr_l} changé de main pendant l'opération : non touché")
                continue
            if dus:
                garder_dus(info, uid, d_l, jour)                        # avant de vider l'uid, effacés de GAML compris
            # le prénom sous lequel GAML connaît le détenteur (note lue, sinon celle posée par le bot) : poser_notes_attendues et
            # renommer_liberes le comparent à la note GAML (un pseudo changé en « Eddie » ne les bloque plus)
            ancien_gaml = _prenom_note(note_v) or _prenom_note(info.get("note")) or prenom
            action = p["action"]
            if p.get("inattendue"):
                refus.append(f"lien {cr_l} : note GAML « {note_v} » inattendue, à vérifier (le lien suit {prenom} par son identifiant)")
            if action == "efface":
                if not info.get("supprime_gaml"):
                    info["supprime_gaml"] = jour
                    refus.append(f"lien {cr_l} introuvable dans GAML (404) : marqué effacé, jamais redonné")
                info.update({"uid": "", "ancien_uid": uid, "ancien": prenom})
            elif action == "main":
                synchroniser_notes(d_l, [{"id": lid, "note": note_v}])
                repris.append(f"{cr_l} « {note_v or '(note vide)'} » (déjà changée à la main)")
            elif action == "autre":
                if len(p["surs"]) == 1:
                    info.update({"uid": p["surs"][0], "note": note_v, "depuis": jour, "par": "auto", "ancien_uid": uid, "ancien": prenom,
                                 "libere": ""})
                    refus.append(f"lien {cr_l} noté « {note_v} » dans GAML : rattaché à <@{p['surs'][0]}> (ses visites comptent à "
                                 f"partir d'aujourd'hui), plus à {prenom}")
                else:
                    info.update({"uid": "", "note": note_v, "ancien_uid": uid, "ancien": prenom, "libere": ""})
                    refus.append(f"lien {cr_l} noté « {note_v} » dans GAML ({len(p['autres'])} membres de ce prénom) : détaché de "
                                 f"{prenom}, jamais redonné au suivant, à rattacher avec `!lien`")
            elif action == "libre":
                info.update({"uid": "", "libere": jour, "ancien": ancien_gaml, "ancien_uid": uid})
                liberes.append(lid)
            elif action == "patch" and lid not in erreurs:
                synchroniser_notes(d_l, [{"id": lid, "note": nouvelle}])
                repris.append(f"{cr_l} « {nouvelle} »")
            else:                                                       # refusée par GAML, ou GAML illisible : détaché quand même
                # `ancien` = le détenteur selon GAML : tant que GAML dit « Clipping <lui> », la note est retentée (poser_notes_attendues)
                info.update({"hors_clipping": nouvelle, "hors_depuis": jour, "uid": "", "libere": "", "ancien_uid": uid,
                             "ancien": ancien_gaml, "note": nouvelle, "note_attendue": nouvelle})
                if action == "patch":
                    refus.append(f"lien {cr_l} : note GAML pas changée ({erreurs[lid]}) — détaché quand même, « {nouvelle} » "
                                 "retentée à chaque passe horaire")
                else:
                    refus.append(f"lien {cr_l} : note GAML non lue (GAML illisible) — détaché quand même, « {nouvelle} » posée à la "
                                 "passe horaire")
                repris.append(f"{cr_l} « {nouvelle} » (note à poser)")
        vus = {p["lid"] for p in plan}
        for lid in liens_de(d_l, uid):
            if lid not in vus:                                          # attribué pendant l'opération : jamais touché sans plan
                refus.append(f"lien {str(d_l['liens'][lid].get('creatrice') or '?').title()} attribué pendant l'opération : "
                             "non touché, relance la commande")
        _ecrire(d_l)
    if liberes and notes_lues:
        try:                                                            # la note relue dans GAML avant chaque PATCH (renommer_liberes)
            await renommer_liberes([{"id": lid, "note": str((vivants.get(lid) or {}).get("note")
                                                            or (d_l["liens"].get(lid) or {}).get("note") or "")} for lid in liberes],
                                   seulement=set(liberes))
        except Exception as erreur:                                     # noqa: BLE001
            refus.append(f"notes des liens libérés ({type(erreur).__name__}) : renommées au prochain passage")
    return {"repris": repris, "liberes": liberes, "refus": refus}


async def poser_notes_attendues(liens: list) -> list:
    """Revue CLICS du 09/10 : la note « <repreneur> Metricool N (ex-Prénom) » refusée par GAML au passage chez le repreneur est retentée
    à chaque passe horaire, seulement si la note GAML est encore celle de l'ancien détenteur (une note changée à la main entre-temps
    n'est jamais écrasée : synchroniser_notes lève l'attente). Arrêt au premier refus. Écrit sur une relecture. Renvoie les lignes.
    09/10 (revue CLICS : une liste /links sans `note` laissait l'attente sans fin, et le lien à la merci d'un homonyme) : la note est
    lue dans le détail du lien (lien_detail) quand la liste ne la porte pas ; un lien introuvable (404) est marqué `supprime_gaml`
    (plus rien à poser) ; une autre erreur de lecture arrête la passe (le reste au passage suivant)."""
    par_id = {l.get("id"): l for l in liens or [] if l.get("id") and "note" in l}
    lignes = []
    for lid, info in list(_lire().get("liens", {}).items()):
        attendue = str(info.get("note_attendue") or "").strip()
        if not attendue:
            continue
        l = par_id.get(lid)
        if l is None:
            try:
                det = await lien_detail(lid)
            except RuntimeError as erreur:
                if "404" in str(erreur):
                    async with verrou_liens:                            # effacé de GAML : plus rien à poser
                        frais = _lire()
                        g = frais.get("liens", {}).get(lid)
                        if g is not None and str(g.get("note_attendue") or "").strip() == attendue:
                            g.pop("note_attendue", None)
                            g["supprime_gaml"] = g.get("supprime_gaml") or _aujourdhui().isoformat()
                            _ecrire(frais)
                    lignes.append(f"· {str(info.get('creatrice') or '?').title()} · « {attendue} » : lien introuvable dans GAML, "
                                  "marqué effacé")
                    continue
                journal.warning("Lien %s : note GAML illisible (%s), « %s » au passage suivant", lid, erreur, attendue)
                break
            if not isinstance(det, dict) or "note" not in det:
                continue                                                # note toujours inconnue : on ne juge pas
            l = {"id": lid, "note": det.get("note")}
        if not _note_du_detenteur(info, str(l.get("note") or "")):
            continue
        try:
            await _requete("PATCH", f"/links/{lid}", corps={"note": attendue})
        except RuntimeError as erreur:
            journal.warning("Lien %s : note « %s » toujours refusée par GAML (%s)", lid, attendue, erreur)
            break
        async with verrou_liens:
            frais = _lire()
            g = frais.get("liens", {}).get(lid)
            if g is not None and str(g.get("note_attendue") or "").strip() == attendue:
                g.pop("note_attendue", None)
                g["note"] = attendue
                _ecrire(frais)
        l["note"] = attendue                                            # la liste de la passe suit (synchroniser_notes juste après)
        lignes.append(f"· {str(info.get('creatrice') or '?').title()} · note posée : « {attendue} »")
    return lignes


def releve_valide(v):
    """Un zéro exige un relevé réussi et des compteurs numériques valides."""
    import math
    def compte(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0 and int(x) == x
    return (isinstance(v, dict) and not v.get('erreur')
            and compte(v.get('payes')) and compte(v.get('hors_robots'))
            and (v.get('brut') is None or compte(v.get('brut'))))


def somme(d: dict, link_ids, debut: date, fin: date) -> dict:
    """Visites des liens sur la période. 28/09 : un lien repris d'un sortant ne compte pour son nouveau clipper qu'à partir de
    `depuis` (les visites d'avant sont celles de l'ancien). 10/10 : un jour dont le total robots compris n'a pas pu être lu (`brut`
    None, releve) compte ses visites payées ; `brut_non_lu` = le nombre de ces jours (les robots ne sont alors pas affichés)."""
    tot = {"brut": 0, "hors_robots": 0, "payes": 0, "jours": 0, "brut_non_lu": 0}
    for lid in link_ids:
        dep = str((d.get("liens", {}).get(lid) or {}).get("depuis") or "")
        for j, v in (d.get("jours") or {}).get(lid, {}).items():
            if not releve_valide(v):
                continue
            if debut.isoformat() <= j <= fin.isoformat() and j >= dep:
                if v.get("brut") is None:
                    tot["brut_non_lu"] += 1
                tot["brut"] += v.get("brut") or 0; tot["hors_robots"] += v.get("hors_robots") or 0
                tot["payes"] += v.get("payes") or 0; tot["jours"] += 1
    return tot


def _en_date(x):
    """Une date depuis `date` ou « AAAA-MM-JJ » (ou ISO plus long) ; None si illisible."""
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x or "")[:10])
    except ValueError:
        return None


def jour_paris() -> date:
    """La date du jour à Paris : `heure_paris` du bot si le module est branché, sinon l'horloge (lecteurs hors boucle, tests)."""
    try:
        return _deps["heure_paris"]().date()
    except Exception:                                                   # noqa: BLE001
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(FUSEAU)).date()
        except Exception:                                               # noqa: BLE001
            return (datetime.now(timezone.utc) + timedelta(hours=2)).date()


def clics_lien(d: dict, lid: str, debut, fin, depuis: bool = True):
    """Contrat C2 (09/10, dashboard) : visites payables du lien `lid` du `debut` au `fin` inclus, lues dans `jours` — aucun appel
    GAML. None si un jour de la période manque (pas encore relevé, erreur GAML, jour en cours) : jamais un faux 0. Un lien repris
    ne compte qu'à partir de sa reprise (`depuis`, comme la paie : les visites d'avant sont celles de l'ancien clipper) ; une période
    tout entière avant `depuis` → None (rien à mesurer pour le détenteur actuel, pas un zéro). `depuis=False` : le lien entier.
    Un vieux relevé marqué `erreur` (404 enregistré à 0 avant le 09/10) compte comme manquant."""
    debut, fin = _en_date(debut), _en_date(fin)
    if debut is None or fin is None or fin < debut:
        return None
    if depuis:
        dep = _en_date(((d or {}).get("liens", {}).get(str(lid)) or {}).get("depuis"))
        if dep is not None and dep > debut:
            debut = dep
        if debut > fin:
            return None
    jours = ((d or {}).get("jours") or {}).get(str(lid)) or {}
    total, j = 0, debut
    while j <= fin:
        v = jours.get(j.isoformat())
        if not isinstance(v, dict) or v.get("erreur") or v.get("payes") is None:
            return None
        total += int(v.get("payes") or 0)
        j += timedelta(days=1)
    return total


def clics_aujourdhui(d: dict, lid: str, jour=None) -> tuple:
    """Contrat C2 (09/10, dashboard) : (visites payables du jour en cours à Paris, heure ISO du relevé) d'après `aujourdhui`, rafraîchi
    toutes les 15 minutes par la boucle. (None, '') si le lien n'a pas été relu aujourd'hui (jamais un faux 0)."""
    e = ((d or {}).get("aujourdhui") or {}).get(str(lid)) or {}
    j = _en_date(jour) if jour is not None else jour_paris()
    if not e or str(e.get("jour") or "") != (j.isoformat() if j else "") or e.get("payes") is None:
        return None, ""
    return int(e["payes"]), str(e.get("t") or "")


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
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None)
                          or str((registre.get(uid) or {}).get("prenom") or "").title() or f"id {uid}")
    rangs = []
    for uid in registre:
        if regime(uid) != "fixe":
            continue
        if not par_uid.get(uid) and _deps["membre_par_id"](uid) is None:
            continue                    # 05/10 : parti du serveur et sans lien (les 20 lignes « id 1127… · aucun lien GAML »)
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


def _blocs(lignes: list, taille: int = 1900) -> list:
    """Les lignes regroupées en messages Discord de `taille` caractères au plus (une ligne trop longue est coupée)."""
    blocs, bloc = [], ""
    for l in lignes:
        l = str(l)[:taille - 1]
        if bloc and len(bloc) + len(l) + 1 > taille:
            blocs.append(bloc)
            bloc = ""
        bloc += l + "\n"
    if bloc.strip():
        blocs.append(bloc)
    return blocs


async def _envoyer_blocs(envoyer, lignes: list, fichier=None) -> None:
    """10/10 (revue CLICS, reprise de la 3e passe : la liste de paie coupée à 1990 caractères perdait l'alerte « Jours non relevés »,
    les marqueurs « provisoire » des derniers clippers et le Total dès 20 à 25 clippers) : la liste entière, en plusieurs messages ;
    `fichier` (le CSV) part avec le premier. `envoyer` = canal.send ou message.reply."""
    blocs = _blocs(lignes) or (["📎"] if fichier is not None else [])
    for i, bloc in enumerate(blocs):
        if i == 0 and fichier is not None:
            await envoyer(bloc, file=fichier)
        else:
            await envoyer(bloc)


async def _envoyer_canal(canal, lignes: list) -> None:
    await _envoyer_blocs(canal.send, lignes)


def non_releves(d: dict, lids, debut: date, fin: date, aujourdhui: date = None) -> list:
    """10/10 (revue CLICS, reprise de la 3e passe : `!mesclics` disait « Hier : 0 visites qui comptent » le jour du Reel viral de Tom,
    relevé en délai dépassé) : les (lid, « AAAA-MM-JJ ») de [debut, fin] (hier au plus) pas encore relevés pour ces liens, à partir de
    leur `depuis` (contrat C2/C6(e) : un jour manquant n'est jamais un zéro). Un lien effacé de GAML ou introuvable aujourd'hui (404)
    n'est pas attendu (même règle que jours_manquants_paie). `aujourdhui` : le jour de référence (11/10 : le rapport du manager)."""
    aujourdhui = aujourdhui or _aujourdhui()
    fin = min(fin, aujourdhui - timedelta(days=1))
    out = []
    for lid in lids:
        info = (d.get("liens") or {}).get(lid) or {}
        if info.get("supprime_gaml") or str(info.get("introuvable") or "") == aujourdhui.isoformat():
            continue
        jours, j = (d.get("jours") or {}).get(lid) or {}, max(debut, _en_date(info.get("depuis")) or debut)
        while j <= fin:
            if _manque(jours, j):
                out.append((lid, j.isoformat()))
            j += timedelta(days=1)
    return out


def _n_jours(paires) -> int:
    return len({j for _, j in paires or []})


def _jours_non_lus(n: int, court: bool = False) -> str:
    """« 2 jour(s) pas encore relevé(s) » (ou « 2 j. non relevé(s) ») ; '' pour 0."""
    return "" if not n else (f"{n} j. non relevé(s)" if court else f"{n} jour(s) pas encore relevé(s)")


def periode_mesclics(arguments: list, aujourd_hui: date = None):
    """Dates inclusives explicites ; ne jamais ignorer un argument."""
    if not arguments:
        return None
    aujourd_hui = aujourd_hui or _aujourdhui()
    try:
        if len(arguments) != 2:
            raise ValueError
        debut, fin = (date.fromisoformat(x) for x in arguments)
        if debut > fin or fin >= aujourd_hui:
            raise ValueError
        return debut, fin
    except ValueError:
        raise ValueError("Période non reconnue : utilise `!mesclics AAAA-MM-JJ AAAA-MM-JJ` (dates incluses, jusqu’à hier), ou `!mesclics` pour le résumé.") from None


def texte_clics_periode(d: dict, uid: str, periode: tuple) -> str:
    debut, fin = periode
    lids = liens_de(d, uid)
    if not lids:
        return "Aucun lien rattaché : les visites de cette période ne sont pas mesurables."
    q = somme(d, lids, debut, fin)
    manquants = non_releves(d, lids, debut, fin)
    couverture = all((_en_date(d['liens'][lid].get('depuis')) or date.max) <= debut for lid in lids)
    complet = not manquants and couverture and bool(q['jours'])
    valeur = _fmt(q['payes']) if complet else (f"{_fmt(q['payes'])} relevées — total incomplet" if q['jours'] else "non mesuré")
    return (f"📊 Visites du **{debut.isoformat()} au {fin.isoformat()} inclus** : **{valeur}**.\n"
            "Cette période décrit les visites ; elle ne recalcule pas une rémunération historique. "
            + ("Ton forfait fixe est distinct des visites." if regime(uid) != "clic" else "La paie au clic dépend de la période et du régime applicables."))


def _lien_masque(uid: str) -> bool:
    """23/10 : le lien GAML est créé à l'arrivée pour tous (parcours.lien_arrivee_actif) : `!mesclics` ne le montre pas avant que le
    parcours le remette (compte privé ouvert, ou consigne de la cohorte). Sans parcours configuré ou en cas d'erreur : visible, comme avant."""
    try:
        import parcours                                                 # import tardif : parcours importe paie_clics
        return not parcours.lien_remis(uid)
    except Exception:                                                   # noqa: BLE001
        return False


def texte_mesclics(d: dict, uid: str, nom: str) -> str:
    lids = liens_de(d, uid)
    if not lids:
        return "Aucun lien n’est rattaché à ton dossier. Ton équipe doit vérifier le rattachement ; tes visites ne sont pas mesurables ici."
    hier = _aujourdhui() - timedelta(days=1)
    h = somme(d, lids, hier, hier)
    s7 = somme(d, lids, hier - timedelta(days=6), hier)
    s30 = somme(d, lids, hier - timedelta(days=29), hier)               # 18/10 (action 28) : hier, 7 j et 30 j
    debut, fin = periode_en_cours()
    debut = _debut_paie(uid, debut, d)                                  # 08/10 : passé au clic ce jour-là
    q = somme(d, lids, debut, min(fin, hier))
    au_clic = regime(uid) == "clic"
    # 10/10 (revue CLICS, reprise de la 3e passe) : un jour pas encore relevé n'est jamais affiché 0 (« Hier : pas encore relevé »),
    # et la paie en cours dit combien de jours elle attend encore (les mêmes que la liste de paie : jours_manquants_paie)
    manque_h = non_releves(d, lids, hier, hier)
    n7 = _n_jours(non_releves(d, lids, hier - timedelta(days=6), hier))
    nq = (_n_jours(jours_manquants_paie(d, debut, min(fin, hier)).get(str(uid))) if au_clic
          else _n_jours(non_releves(d, lids, debut, min(fin, hier))))
    part = f" ({h['payes'] * 100 // h['hors_robots']} % de tes visiteurs)" if h["hors_robots"] else ""
    robots = h["brut"] - h["hors_robots"] if not h["brut_non_lu"] else 0
    if not h["jours"]:
        ligne_hier = f"Hier, le {hier.strftime('%d/%m')} : non mesuré, relevé en attente.\n\n"
    else:
        ligne_hier = (f"Hier, le {hier.strftime('%d/%m')} : **{_fmt(h['payes'])} visites qui comptent**{part}"
                      + (" pour l'instant (un de tes liens pas encore relevé)" if manque_h else "")
                      + (f". {robots} robots enlevés" if robots > 0 else "") + ".\n\n")
    reste_q = f", {_jours_non_lus(nq)} : montant provisoire" if nq else ""
    visites_7 = _fmt(s7["payes"]) if s7["jours"] else "non mesuré"
    visiteurs_7 = _fmt(s7["hors_robots"]) if s7["jours"] else "non mesuré"
    visites_q = _fmt(q["payes"]) if q["jours"] else "non mesuré"
    montant_q = _usd(q["payes"] * TAUX_CLIC) if q["jours"] else "non mesurée"
    return (f"📊 **Tes visites, {nom}**" + ("" if au_clic else " · rémunération au forfait fixe") + "\n\n"
            + ligne_hier +
            f"Sur 7 jours : **{visites_7}** visites qui comptent, sur {visiteurs_7} visiteurs"
            + (f" ({_jours_non_lus(n7)})" if n7 else "") + ".\n\n"
            + (f"Sur 30 jours : **{_fmt(s30['payes'])}** visites qui comptent.\n\n" if s30["jours"] else "")
            + ((f"💸 **Ta paie en cours : {montant_q}** ({visites_q} visites du {debut.strftime('%d/%m')} au "
                f"{min(fin, hier).strftime('%d/%m')}{reste_q}), date de paie prévue : {prochaine_paie(_aujourdhui()).strftime('%d/%m')}.\n") if au_clic else
               (f"Période du {debut.strftime('%d/%m')} au {min(fin, hier).strftime('%d/%m')} : **{visites_q} visites**"
                f"{f' ({_jours_non_lus(nq)})' if nq else ''}. Ton forfait fixe est distinct des visites.\n"))
            +
            (f"Une visite qui compte = {_usd(TAUX_CLIC)}. " if au_clic else "")
            + "Les visites qui comptent viennent de France ou d’un pays francophone, hors robots.\n\n"
            + ("" if not au_clic or str(uid) in d["wallets"] else "⚠️ Je n'ai pas ton adresse de paiement. Colle ton adresse USDC dans ton app (onglet Versements), ou écris `!wallet 0x…` ici (`!wallet FR76…` pour un virement).\n\n")
            + ("" if _lien_masque(uid) else "-# Ton lien : " + " · ".join(d["liens"][l].get("url", "") for l in lids))).rstrip()


def ligne_matin(d: dict, uid: str) -> str:
    lids = liens_de(d, uid)
    hier = _aujourdhui() - timedelta(days=1)
    h = somme(d, lids, hier, hier)
    if h["jours"] == 0:
        return ""
    debut, fin = periode_en_cours()
    q = somme(d, lids, _debut_paie(uid, debut, d), min(fin, hier))     # 08/10 (revue) : la même période que la paie
    if not h["payes"] and not q["payes"]:
        # 27/09 : « Visites hier : 0 · quinzaine : 0 = 0,00 $ » chez un clipper qui crée encore ses comptes, c'est du
        # bruit (Daniella). Rien à dire tant qu'il n'y a rien ; `!mesclics` reste là, et le bilan manager voit les zéros.
        return ""
    au_clic = regime(uid) == "clic"
    montant = f" = {_usd(q['payes'] * TAUX_CLIC)} · virée le {prochaine_paie(_aujourdhui()).strftime('%d/%m')}" if au_clic else ""   # 28/09 (GO n° 8)
    # 10/10 (revue CLICS, reprise de la 3e passe) : un lien pas encore relevé pour hier n'est pas compté 0 en silence
    incomplet = " (pas encore tout relevé)" if non_releves(d, lids, hier, hier) else ""
    dp = _debut_paie(uid, debut, d)
    nq = (_n_jours(jours_manquants_paie(d, dp, min(fin, hier)).get(str(uid))) if au_clic
          else _n_jours(non_releves(d, lids, dp, min(fin, hier))))
    # 26/09 : une ligne, dans le message du matin (les détails restent dans `!mesclics`)
    return (f"👀 Visites hier : **{_fmt(h['payes'])}**{incomplet} · période : **{_fmt(q['payes'])}{montant}**"
            + (f" ({_jours_non_lus(nq, court=True)})" if nq else "")
            + ("" if not au_clic or str(uid) in d["wallets"] else "\n⚠️ Adresse de paiement manquante : colle-la dans ton app (onglet Versements) ou `!wallet 0x…`"))


def garder_dus(info: dict, uid: str, d: dict = None, jour: str = "") -> bool:
    """09/10 (revue CLICS : `!lien @Nina <url> forcer` sur le lien d'Eddy, au clic et toujours dans l'équipe, effaçait de la paie ses
    80 visites du 01 au 08/10) : avant qu'un lien change de main (forcé, retiré, sortie, passage chez le repreneur Metricool), les
    visites de son détenteur AU CLIC lui restent dues : `dus` += {uid, depuis, avant}, que la liste de paie compte (jours `depuis` ≤ j <
    `avant` ; le jour du changement exclu, il revient au suivant). `depuis` = le plus tard du premier jour compté du lien (`depuis`) et
    du plancher du clic du détenteur (debut_clic) : jamais payé deux fois. Un détenteur au fixe n'a rien de dû au clic. À appeler
    AVANT le retrait du registre (régime et plancher lus sur sa fiche) et AVANT de vider l'uid. Renvoie True si une entrée est posée."""
    uid = str(uid or "")
    if not uid or info is None or regime(uid) != "clic":
        return False
    jour = jour or _aujourdhui().isoformat()
    dep = max(str(info.get("depuis") or CLICS_DEPUIS)[:10], str(debut_clic(uid, d) or "")[:10])
    if dep >= jour:
        return False
    dus = info.setdefault("dus", [])
    if any(str(e.get("uid") or "") == uid and str(e.get("avant") or "") == jour for e in dus if isinstance(e, dict)):
        return False                                                    # déjà posé aujourd'hui (commande relancée)
    dus.append({"uid": uid, "depuis": dep, "avant": jour})
    return True


def liberer_sortant(d: dict, uid: str, prenom: str = "") -> list:
    """09/10 (dashboard : « pas de liens pas assignés ») : `!sortie` sans pool libère aussi les liens du sortant — par son uid
    seulement (jamais par la note : un homonyme garde les siens). Avant, le lien restait attribué à un membre parti de l'équipe :
    lien sans compte, jamais redonné ni ménagé. Les visites d'AVANT la sortie restent à lui (le MP de sortie promet « ce qui t'est
    dû est réglé au prochain décompte ») : chaque lien garde `dus` (garder_dus). Revue CLICS du 09/10 : réservé au sortant SANS
    compte créé ; celui dont les comptes créés partent sur Metricool passe ses liens chez le repreneur (passer_liens_metricool).
    À appeler AVANT le retrait du registre. Renvoie les identifiants libérés. L'appelant écrit `d`."""
    uid = str(uid or "")
    if not uid:
        return []
    jour = _aujourdhui().isoformat()
    for lid in liens_de(d, uid):                                        # avant liberer_liens : il vide l'uid
        garder_dus(d["liens"][lid], uid, d, jour)
    notes = {lid: _prenom_note(d["liens"][lid].get("note")) for lid in liens_de(d, uid)}
    libres = liberer_liens(d, uid, "")
    for lid in libres:
        info = d["liens"][lid]
        info["ancien_uid"] = uid
        # 09/10 (revue CLICS, C6(d)) : `ancien` = le prénom de la note posée pour lui (« Clipping Eddy » d'un Eddy devenu « Eddie ») :
        # renommer_liberes le compare à la note GAML (sinon jamais renommé « libre », donc donné à un homonyme par associer_auto)
        if notes.get(lid) or prenom:
            info["ancien"] = notes.get(lid) or prenom
    return libres


def dus_sortie(d: dict, debut: date, fin: date) -> dict:
    """{uid: {"payes", "hors_robots"}} : les visites dues aux sortants sur [debut, fin] (`dus` posés par liberer_sortant)."""
    out = {}
    for lid, info in (d.get("liens") or {}).items():
        for e in info.get("dus") or []:
            u = str(e.get("uid") or "")
            de, av = _en_date(e.get("depuis")), _en_date(e.get("avant"))
            if not u or de is None or av is None:
                continue
            a, b = max(debut, de), min(fin, av - timedelta(days=1))
            if a > b:
                continue
            tot = out.setdefault(u, {"payes": 0, "hors_robots": 0})
            for j, v in (d.get("jours") or {}).get(lid, {}).items():
                if a.isoformat() <= j <= b.isoformat() and isinstance(v, dict):
                    tot["payes"] += int(v.get("payes") or 0)
                    tot["hors_robots"] += int(v.get("hors_robots") or 0)
    return out


def jours_manquants_paie(d: dict, debut: date, fin: date, avec_provisoires: bool = False, garder_introuvables: bool = False) -> dict:
    """10/10 (revue CLICS, 3e passe : ce qui restait de R3 côté paie) : {uid: [(lid, "AAAA-MM-JJ"), …]}, les jours de la période
    [debut, fin] (hier au plus) qui manquent dans `jours` (jamais relevés, ou vieux 0 marqué `erreur`) pour ce que la liste de paie
    compte : chaque lien d'un clipper au clic, de son premier jour payé (`depuis` du lien, plancher du clic) à `fin`, et les visites
    dues à un sortant (`dus`). `somme` compte un jour absent pour 0 sans rien dire (avant : un jour viral jamais relevé — délai dépassé
    sur /analytics/visitors — disparaissait de la paie du 20 sans alerte ; contrat C6(e) : un jour manquant n'est jamais un zéro).
    Un lien effacé de GAML ou introuvable aujourd'hui (404) n'est pas attendu : rien à relire (même règle que `complets`).
    11/10 (contre-vérification CLICS, passe 3 : la relecture de 6 h des veilles en échec jusqu'à 7 h 30, la paie de 7 h partait avec Tom
    à 148 au lieu de 150, sans « provisoire » ni complément) : `avec_provisoires` (la paie, son complément, `!paie-clics`) → une veille
    lue avant RELECTURE_HEURE et pas encore relue (`provisoires`) manque aussi.
    11/10 (reprise L11, R3) : `garder_introuvables` (les primes d'équipe) → un lien introuvable aujourd'hui (404 passager) garde ses
    jours manquants : un VA à 480 dont le 04/11 manque n'est jamais tenu pour complet, ni sa prime figée à 0 sans un mot."""
    aujourdhui = _aujourdhui()
    fin = min(fin, aujourdhui - timedelta(days=1))
    out = {}
    prov = (d.get("provisoires") or {}) if avec_provisoires else {}

    def noter(uid: str, lid: str, a, b) -> None:
        info = (d.get("liens") or {}).get(lid) or {}
        if a is None or b is None or info.get("supprime_gaml") or (
                not garder_introuvables and str(info.get("introuvable") or "") == aujourdhui.isoformat()):
            return
        jours, j = (d.get("jours") or {}).get(lid) or {}, a
        while j <= b:
            if ((_manque(jours, j) or j.isoformat() in (prov.get(lid) or ()))
                    and (lid, j.isoformat()) not in out.get(uid, [])):
                out.setdefault(uid, []).append((lid, j.isoformat()))
            j += timedelta(days=1)
    for lid, info in (d.get("liens") or {}).items():
        uid = str(info.get("uid") or "")
        if uid and regime(uid) == "clic":
            noter(uid, lid, max(_debut_paie(uid, debut, d), _en_date(info.get("depuis")) or debut), fin)
        for e in info.get("dus") or []:                                 # les visites dues à un sortant (dus_sortie)
            if isinstance(e, dict) and str(e.get("uid") or "") and _en_date(e.get("avant")) is not None:
                noter(str(e["uid"]), lid, max(debut, _en_date(e.get("depuis")) or debut),
                      min(fin, _en_date(e.get("avant")) - timedelta(days=1)))
    for uid in out:
        out[uid].sort(key=lambda x: (x[1], x[0]))
    return out


def texte_manquants(manquants: dict, nom_de, maximum: int = 8) -> str:
    """10/10 : « Tom (12/10, 13/10) · Lia (19/10) » pour l'admin (`maximum` clippers, quatre jours chacun au plus)."""
    morceaux = []
    for uid, paires in sorted(manquants.items(), key=lambda x: -len(x[1]))[:maximum]:
        jours = sorted({j for _, j in paires})
        morceaux.append(f"{str(nom_de(uid)).split(' - ')[0]} ({', '.join(j[8:10] + '/' + j[5:7] for j in jours[:4])}"
                        + (f" et {len(jours) - 4} de plus" if len(jours) > 4 else "") + ")")
    reste = len(manquants) - len(morceaux)
    return " · ".join(morceaux) + (f" · et {reste} autre(s)" if reste > 0 else "")


def _cle_periode(jour_paie: str, fin: date) -> str:
    """« AAAA-MM-JJ » du jour de paie (« 20/10 » + fin de période → « 2026-10-20 ») : la clé de `paies` et de `paies_annoncees`."""
    return jour_paie if "-" in jour_paie else f"{fin.year}-{jour_paie[3:5]}-{jour_paie[:2]}"


def _jjmm(jours) -> str:
    return ", ".join(j[8:10] + "/" + j[5:7] for j in sorted(set(jours or [])))


def _deja_verse(annonce: dict, uid: str) -> tuple:
    """(annoncé, compléments postés, total versé) d'un clipper pour une paie annoncée ; `annonce` = {uid: {montant, complement}}
    (_versements)."""
    a = (annonce or {}).get(str(uid)) or {}
    a_m, c_m = round(float(a.get("montant") or 0), 2), round(float(a.get("complement") or 0), 2)
    return a_m, c_m, round(a_m + c_m, 2)


def _versements(d: dict, cle: str):
    """10/10 (reprise CLICS, 4e tour) : ce qui a déjà été versé pour la paie `cle` — {uid: {montant (annoncé), complement (compléments
    postés, cumulés)}} d'après `paies_annoncees` et `paies_complements` ; None si cette paie n'a jamais été annoncée."""
    annonce = (d.get("paies_annoncees") or {}).get(cle)
    if not annonce:
        return None
    out = {str(uid): {"montant": float((c or {}).get("montant") or 0), "complement": 0.0}
           for uid, c in (annonce.get("clippers") or {}).items()}
    for uid, c in (((d.get("paies_complements") or {}).get(cle) or {}).get("clippers") or {}).items():
        out.setdefault(str(uid), {"montant": 0.0, "complement": 0.0})["complement"] = float((c or {}).get("montant") or 0)
    return out


def _payees_detail(d: dict, uid: str, debut: date, fin: date, lids: list = None, du: dict = None, clic: bool = None) -> dict:
    """{"payes", "hors_robots"} : LA mesure de la ligne d'un clipper sur la liste de paie (lot L11, revue du 10/10). Ses liens au clic,
    de son premier jour payé (_debut_paie : plancher du passage au clic) à `fin`, plus les visites qui lui sont dues après un
    changement de main (`dus`, dus_sortie). Un lien au fixe ne compte pas (ses `dus` au clic, si). `lids`, `du`, `clic` : déjà
    calculés par l'appelant (liste_paie), sinon lus ici."""
    uid = str(uid)
    lids = liens_de(d, uid) if lids is None else lids
    if du is None:
        du = dus_sortie(d, debut, fin).get(uid) or {"payes": 0, "hors_robots": 0}
    if clic is None:
        clic = not lids or regime(uid) == "clic"
    if lids and not clic:
        s = {"payes": 0, "hors_robots": 0}
    else:
        s = somme(d, lids, _debut_paie(uid, debut, d), fin) if lids else {"payes": 0, "hors_robots": 0}   # 08/10 : passé au clic ce jour-là
    return {"payes": s["payes"] + du["payes"], "hors_robots": s["hors_robots"] + du["hors_robots"]}


def payees(d: dict, uid: str, debut, fin) -> int:
    """Lot L11 (revue du 10/10) : les visites payées d'un clipper sur [debut, fin], EXACTEMENT celles de sa ligne sur la liste de
    paie du 5 et du 20 (liste_paie utilise la même mesure, _payees_detail). C'est elle que equipes_tl reçoit pour les seuils des
    primes d'équipe (500 par VA, 3 000 par équipe) : une seule mesure partout (liste, primes, app, Dashboard). 0 pour un clipper sans
    lien ni visite, jamais None ; des dates illisibles lèvent ValueError (equipes_tl en fait alors une « mesure en erreur »)."""
    a, b = _en_date(debut), _en_date(fin)
    if a is None or b is None:
        raise ValueError(f"période illisible ({debut!r} → {fin!r})")
    return int(_payees_detail(d, str(uid), a, b)["payes"])


class RangsPaie(list):
    """Les rangs de liste_paie, (nom, uid, payées, visiteurs, montant, adresse) comme avant (aucun appelant ne change), plus ce que la
    feuille, l'annonce et le complément doivent savoir des primes (lot L11) : `primes_equipe` {uid : (montant, détail, à_vérifier)}
    pour les clippers de la liste, `parrainage` {uid : total des primes de parrainage}, `notes_equipe` [(uid, nom, détail)] : les
    notes à 0 $ d'un bénéficiaire absent de la liste (rien à virer, jamais une ligne de virement)."""
    primes_equipe = None
    parrainage = None
    notes_equipe = None


def _rangs_paie(rangs, primes_equipe=None, parrainage=None, notes_equipe=None) -> RangsPaie:
    r = RangsPaie(rangs)
    r.primes_equipe, r.parrainage, r.notes_equipe = dict(primes_equipe or {}), dict(parrainage or {}), list(notes_equipe or [])
    return r


def _cle_iso(jour_paie: str, fin: date) -> str:
    """La clé « AAAA-MM-JJ » du jour de paie, d'un « 05/11 », d'une clé ISO ou de rien (le lendemain de la fin)."""
    jp = str(jour_paie or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", jp[:10]) and len(jp) >= 10:
        return jp[:10]
    if re.fullmatch(r"\d{2}/\d{2}(/\d{4})?", jp):
        return f"{jp[6:10] if len(jp) == 10 else fin.year}-{jp[3:5]}-{jp[:2]}"
    return (fin + timedelta(days=1)).isoformat()


def _equipes_tl():
    """Le module equipes_tl (lot L10), ou None s'il manque."""
    try:
        import equipes_tl
        return equipes_tl
    except Exception:                                                   # noqa: BLE001
        return None


def _dep_equipes(nom: str):
    """Reprise L11 (R6) : la dépendance `etat_equipes` ou `calcul_equipes` passée par on_ready ; à défaut, quand `primes_equipes` est
    branchée (l'on_ready du lot W ne passe qu'elle), la même fonction dérivée d'equipes_tl déjà configuré, avec les mêmes mesures que
    `primes_equipes` (paie_clics.payees, et les reels_vus / jours_manquants donnés à equipes_tl.configurer). Avant : la liste du 05/11
    portait les primes, mais rien n'était jamais figé (double prime au recompte) et l'onglet « Équipes » de l'app restait vide.
    None sans `primes_equipes` : rien ne change."""
    f = _deps.get(nom)
    if f is not None or not _deps.get("primes_equipes") or nom not in ("etat_equipes", "calcul_equipes"):
        return f
    et = _equipes_tl()
    if et is None or not et.branche():
        return None

    def mesures() -> tuple:
        return payees, et._deps.get("reels_vus"), et._deps.get("jours_manquants")
    if nom == "etat_equipes":
        return lambda d, debut, fin, cle="": et.a_figer(d, debut, fin, cle, *mesures())
    return lambda d, debut, fin: et.calculer(d, debut, fin, *mesures())


def _uids_equipes(etat: dict) -> set:
    """Les uid des VA d'un état d'équipes (equipes_tl.a_figer) : ceux dont un jour non relevé peut changer une prime. Le TL aussi, mais
    seulement quand ses visites comptent dans son équipe (EQUIPE_COMPTE_TL=1) ; à 0 (la grille de Gaëtan), un jour non relevé du TL ne
    change aucune prime et ne retarde plus le figement (reprise L11, R4).
    11/10 (clôture de la vague 2 : le lien en 404 d'un VA de Sarah, sans TL ni manager, retenait le complément au clic de TOUS les
    clippers jusqu'à J+3 7 h) : seulement les équipes qui ont un TL ou un manager, les seules où un jour peut changer une prime."""
    et = _equipes_tl()
    tl_compte = bool(getattr(et, "EQUIPE_COMPTE_TL", False))
    out = set()
    for e in ((etat or {}).get("composition") or {}).values():
        if isinstance(e, dict) and (e.get("tl") or e.get("manager")):
            out.update(str(u) for u in (e.get("vas") or {}))
            if e.get("tl") and tl_compte:
                out.add(str(e["tl"]))
    return out


def manquants_equipes(d: dict, debut: date, fin: date, cle: str) -> dict:
    """Reprise L11 (R3) : {uid: [(lien, jour)]} des VA d'équipe dont un jour de la période manque, lien introuvable aujourd'hui (404)
    compris, tant que les primes de la période ne sont pas figées (seule la composition l'est). L'annonce les attend comme les autres
    jours manquants : quand ils arrivent, le complément porte la prime juste (et le clic du VA) ; sinon la période est figée au délai,
    « jours non relevés », et le complément suivant le dit. {} si les primes sont figées ou s'il n'y a pas d'équipe."""
    fige = (d.get("primes_equipes") or {}).get(cle)
    if not isinstance(fige, dict) or isinstance(fige.get("lignes"), list):
        return {}
    uids = _uids_equipes(fige)
    if not uids:
        return {}
    tous = jours_manquants_paie(d, debut, fin, avec_provisoires=True, garder_introuvables=True)
    return {u: p for u, p in tous.items() if u in uids and p}


def _unir_manquants(*sources) -> dict:
    """{uid: [(lien, jour)]} : l'union de plusieurs jours_manquants_paie, sans doublon, triée comme eux."""
    out = {}
    for s in sources:
        for uid, paires in (s or {}).items():
            deja = out.setdefault(str(uid), [])
            deja.extend(p for p in paires if tuple(p) not in {tuple(x) for x in deja})
    return {uid: sorted(ps, key=lambda x: (x[1], x[0])) for uid, ps in out.items() if ps}


def _a_proteger(etat: dict) -> bool:
    """Une période dont la composition mérite d'être figée : primée, avec au moins un TL ou un manager."""
    return bool(etat.get("primee", bool(etat.get("lignes")))) and any(
        isinstance(e, dict) and (e.get("tl") or e.get("manager")) for e in (etat.get("composition") or {}).values())


def figer_primes_equipes(d: dict, debut: date, fin: date, jour_paie: str = "", manquants: dict = None, aujourdhui: date = None,
                         maintenant=None) -> bool:
    """Lot L11 : fige les primes d'équipe d'une période close dans clics.json['primes_equipes'][« AAAA-MM-JJ » du jour de paie]
    (equipes_tl.a_figer : composition, chiffres, lignes), au premier calcul où elles sont définitives. Ensuite, une liste retapée
    (`!paie-clics`, complément), une sortie, une nomination ou une correction de relevé ne changent plus rien : equipes_tl relit le
    figé. Renvoie True si la période est figée maintenant. Écrit `d`.

    Pas figée (le calcul suivant réessaie, les montants restent ceux du jour) :
      - période pas close (aujourd'hui ≤ `fin`), ou déjà figée, ou `etat_equipes` ni passée ni dérivable (_dep_equipes) ;
      - une mesure en erreur (a_figer « complet » faux, contrat L10 : jamais un faux 0 figé) ;
      - aucune prime ni note (rien à protéger ; un PRIMES_EQUIPES_DEPUIS avancé après coup peut encore primer la période) ;
      - un VA d'une équipe (le TL aussi si EQUIPE_COMPTE_TL=1) a un jour non relevé (`manquants`, et jours_manquants_paie avec les
        veilles provisoires et les liens introuvables aujourd'hui), tant que le délai du complément court (jour de paie +
        COMPLEMENT_JOURS, à CLICS_HEURE comme le complément) : le complément porte alors la prime juste (jamais un faux 0 figé quand
        le jour manquant ferait passer 500 ou 3 000). Le délai passé, la période est figée telle quelle, « à vérifier ».

    Reprise L11 (R1) : la COMPOSITION (TL, manager, VA de chaque équipe) est figée dès le premier calcul après la clôture, même
    quand les montants ne le sont pas encore (`composition` sans `lignes`) : jusqu'au figement des primes, seuls les chiffres de
    cette composition bougent. Un VA passé chez une autre créatrice entre l'annonce et le figement ne prime plus deux TL."""
    etat_f = _dep_equipes("etat_equipes")
    if not etat_f:
        return False
    if maintenant is None and aujourdhui is None:
        maintenant = _deps["heure_paris"]()
    aujourdhui = aujourdhui or maintenant.date()
    cle = _cle_iso(jour_paie, fin)
    deja = (d.get("primes_equipes") or {}).get(cle)
    if aujourdhui <= fin or (isinstance(deja, dict) and isinstance(deja.get("lignes"), list)):
        return False
    etat = etat_f(d, debut, fin, cle)
    if not isinstance(etat, dict):
        return False
    cle = str(etat.get("cle") or cle)
    deja = (d.get("primes_equipes") or {}).get(cle)
    if not (isinstance(deja, dict) and isinstance(deja.get("composition"), dict)) and _a_proteger(etat):
        deja = {"cle": cle, "debut": etat.get("debut"), "fin": etat.get("fin"), "composition": etat.get("composition") or {},
                "noms": etat.get("noms") or {}, "composition_le": aujourdhui.isoformat()}
        d.setdefault("primes_equipes", {})[cle] = deja
        if _deps.get("ecrire_json"):
            _ecrire(d)
        journal.info("Équipes figées pour la paie %s (composition, primes pas encore)", cle)
    if not etat.get("complet", True) or not etat.get("lignes"):
        return False
    tous = jours_manquants_paie(d, debut, fin, avec_provisoires=True, garder_introuvables=True)
    en_attente = _uids_equipes(etat) & {str(u) for u, paires in [*(manquants or {}).items(), *tous.items()] if paires}
    limite = _en_date(cle) + timedelta(days=COMPLEMENT_JOURS)
    if en_attente and (aujourdhui < limite or (aujourdhui == limite and maintenant is not None and maintenant.hour < CLICS_HEURE)):
        return False
    etat = dict(deja if isinstance(deja, dict) else {}, **etat)
    etat.update(cle=cle, fige_le=aujourdhui.isoformat(), **({"jours_non_releves": sorted(en_attente)} if en_attente else {}))
    d.setdefault("primes_equipes", {})[etat["cle"]] = etat
    if _deps.get("ecrire_json"):
        _ecrire(d)
    journal.info("Primes d'équipe figées pour la paie %s : %s ligne(s)", etat["cle"], len(etat.get("lignes") or []))
    return True


_RESUME_TL = re.compile(r"\((\d+) VA à ([\d\s  ]+?) ou plus")
_RESUME_MANAGER = re.compile(r"\$ manager \(équipe .+? à [\d\s  ]+? / ([\d\s  ]+?),")


def resume_prime(detail: str) -> str:
    """« 2 VA à 500 ou plus » et/ou « 1 équipe à 3 000 ou plus », lus dans le détail d'une ligne de prime (equipes_tl.lignes_primes) :
    ce que le TL ou le manager lit dans son salon. '' si rien n'est reconnu."""
    morceaux = []
    m = _RESUME_TL.search(str(detail or ""))
    if m:
        morceaux.append(f"{m.group(1)} VA à {m.group(2).strip()} ou plus")
    managers = _RESUME_MANAGER.findall(str(detail or ""))
    if managers:
        morceaux.append(f"{len(managers)} équipe{'s' if len(managers) > 1 else ''} à {managers[0].strip()} ou plus")
    return ", ".join(morceaux)


def _primes_equipes_liste(d: dict, debut: date, fin: date, jour_paie: str, manquants: dict, lignes: list) -> dict:
    """{uid : (montant, détail, à_vérifier)} des primes d'équipe de la période (dépendance `primes_equipes`, contrat L10), après
    une tentative de figement (figer_primes_equipes). Une erreur n'arrête jamais la paie au clic : la ligne « ⚠️ primes d'équipe non
    calculées » est ajoutée à `lignes` et la liste part sans elles."""
    if not _deps.get("primes_equipes"):
        return {}
    try:
        figer_primes_equipes(d, debut, fin, jour_paie, manquants)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Primes d'équipe non figées : %s", erreur)
        lignes.append(f"⚠️ primes d'équipe non figées ({type(erreur).__name__}) : recalculées à chaque liste, à vérifier")
    try:
        brutes = _deps["primes_equipes"](d, debut, fin, _cle_iso(jour_paie, fin)) or []
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Primes d'équipe non calculées : %s", erreur)
        lignes.append(f"⚠️ primes d'équipe non calculées ({type(erreur).__name__}) : la liste part sans elles, à vérifier")
        return {}
    out = {}
    for x in brutes:
        try:
            uid, montant, detail, verif = str(x[0]), round(float(x[1] or 0), 2), str(x[2] or ""), bool(x[3])
        except (TypeError, ValueError, IndexError):
            journal.warning("Prime d'équipe illisible : %r", x)
            continue
        if not uid or montant < 0:
            continue
        m0, d0, v0 = out.get(uid, (0.0, "", False))
        out[uid] = (round(m0 + montant, 2), " · ".join(p for p in (d0, detail) if p), v0 or verif)
    return out


def liste_paie(d: dict, nom_de, debut: date, fin: date, jour_paie: str, manquants: dict = None, annonce: dict = None) -> tuple:
    """Lignes Discord + CSV de la paie : un clipper par ligne, visites payées, montant, adresse. 10/10 (revue CLICS, 3e passe) :
    `manquants` (jours_manquants_paie) → la ligne d'un clipper dont des jours ne sont pas encore relevés est marquée « provisoire ».
    10/10 (reprise de la 3e passe) : `annonce` ({uid: {"montant", "complement"}}, ce qui a déjà été versé pour cette paie, _versements)
    → chaque ligne dit ce qui a été annoncé, les compléments déjà postés, et le reste (recompte − annoncé − compléments) ; le CSV
    porte « deja_verse_usd » et « reste_usd ».
    Lot L11 (revue du 10/10) : les primes d'équipe (dépendance `primes_equipes`, equipes_tl) s'ajoutent comme le parrainage — sur la
    ligne du TL ou du manager (« 👥 + 20 $ équipe Chloé (2 VA à 500 ou plus : …) »), ou sur une ligne neuve s'il n'a aucune visite
    payée (manager sans lien, TL au fixe) ; une prime à 0 $ est une note « à vérifier », jamais une ligne de virement. Le CSV prend
    alors les colonnes prime_equipe_usd et detail_prime. Sans prime d'équipe, tout est identique à avant. Les rangs rendus sont une
    RangsPaie (mêmes tuples, plus les primes pour la feuille, l'annonce et le complément)."""
    manquants = manquants or {}
    par_uid = {}
    for lid, info in d["liens"].items():
        uid = str(info.get("uid") or "")
        if uid:
            par_uid.setdefault(uid, []).append(lid)
    dus = dus_sortie(d, debut, fin)                                     # 09/10 : visites d'avant un `!sortie` manuel
    lignes, rangs, total, sans, fixes = [], [], 0.0, 0, []
    for uid in list(par_uid) + [u for u in dus if u not in par_uid]:
        lids = par_uid.get(uid, [])
        du = dus.get(uid, {"payes": 0, "hors_robots": 0})
        clic = not lids or regime(uid) == "clic"
        if not clic:
            fixes.append((nom_de(uid), somme(d, lids, debut, fin)["payes"]))
            if not du["payes"]:
                continue
        s = _payees_detail(d, uid, debut, fin, lids, du, clic)          # lot L11 : la même mesure que payees (seuils d'équipe)
        if s["payes"] == 0:
            continue
        montant = round(s["payes"] * TAUX_CLIC, 2); total += montant
        w = d["wallets"].get(uid, {}).get("adresse", "")
        if not w:
            sans += 1
        rangs.append((nom_de(uid), uid, s["payes"], s["hors_robots"], montant, w))
    rangs.sort(key=lambda r: -r[4])
    cle_periode = _cle_periode(jour_paie, fin)
    # 27/09 : la liste est mémorisée (jour de paie → uid → montant) pour le tableau de bord du lundi (« premier paiement »)
    if rangs and _deps.get("ecrire_json"):
        d.setdefault("paies", {})[cle_periode] = {uid: montant for _, uid, _, _, montant, _ in rangs}
        _ecrire(d)
    # 28/09 : la prime de parrainage (5 $) s'ajoute à la ligne du parrain le jour de la première paie du filleul
    primes = {}
    if _deps.get("primes_parrainage"):
        try:
            for uid_p, uid_f, prime in _deps["primes_parrainage"]({uid: montant for _, uid, _, _, montant, _ in rangs}, cle_periode):
                primes.setdefault(uid_p, []).append((nom_de(uid_f), prime))
        except Exception as erreur:                                     # noqa: BLE001
            lignes.append(f"⚠️ primes de parrainage non calculées ({type(erreur).__name__})")
    if primes:
        presents = {uid for _, uid, _, _, _, _ in rangs}
        rangs = [(nom, uid, payes, hors, montant + sum(pr for _, pr in primes.get(uid, [])), w) for nom, uid, payes, hors, montant, w in rangs]
        for uid_p, lst in primes.items():
            if uid_p not in presents:
                rangs.append((nom_de(uid_p), uid_p, 0, 0, sum(pr for _, pr in lst), d["wallets"].get(uid_p, {}).get("adresse", "")))
        rangs.sort(key=lambda r: -r[4])
        total = sum(r[4] for r in rangs)
        sans = sum(1 for r in rangs if not r[5])
    # Lot L11 (revue du 10/10) : les primes d'équipe (10 $ au TL par VA à 500 visites payées ou plus, 75 $ au manager par équipe à
    # 3 000 ou plus), sur le modèle du parrainage. Figées au premier calcul où elles sont définitives (figer_primes_equipes).
    p_eq = _primes_equipes_liste(d, debut, fin, jour_paie, manquants, lignes)
    notes_eq = []
    if p_eq:
        presents = {uid for _, uid, _, _, _, _ in rangs}
        rangs = [(nom, uid, payes, hors, round(montant + (p_eq[uid][0] if uid in p_eq else 0), 2), w)
                 for nom, uid, payes, hors, montant, w in rangs]
        for uid_b, (m_b, det_b, _) in p_eq.items():
            if uid_b in presents:
                continue
            if m_b >= 0.01:                                             # manager sans lien, TL au fixe : une ligne neuve
                rangs.append((nom_de(uid_b), uid_b, 0, 0, m_b, d["wallets"].get(uid_b, {}).get("adresse", "")))
            else:                                                       # 0 $ : une note « à vérifier », rien à virer
                notes_eq.append((uid_b, nom_de(uid_b), det_b))
        rangs.sort(key=lambda r: -r[4])
        total = sum(r[4] for r in rangs)
        sans = sum(1 for r in rangs if not r[5])
    p_eq_rangs = {uid: p_eq[uid] for _, uid, _, _, _, _ in rangs if uid in p_eq}
    for nom, uid, payes, hors, montant, w in rangs:
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else (w or "⚠️ adresse manquante")
        bonus = "".join(f" · 🎁 +{_usd(pr)} parrainage de {f}" for f, pr in primes.get(uid, []))
        if uid in p_eq_rangs:
            bonus += f" · 👥 {p_eq_rangs[uid][1]}"
        n_manq = len({j for _, j in manquants.get(uid, [])})
        prov = f" · ⚠️ provisoire : {n_manq} jour(s) non relevé(s)" if n_manq else ""
        if annonce is not None:
            # 10/10 (reprise CLICS, 4e tour) : le recompte se compare à ce qui a déjà été versé (annonce + compléments postés),
            # jamais à l'annonce seule (avant : un complément déjà posté revenait en « complément **+0,50 $** », à virer deux fois)
            a_m, c_m, verse = _deja_verse(annonce, uid)
            ecart = round(montant - verse, 2)
            deja = f"annoncé {_usd(a_m)}" + (f" + complément {_usd(c_m)}" if c_m >= 0.01 else "")
            if ecart >= 0.01:
                prov += f" · {deja} → reste **+{_usd(ecart)}**"
            elif ecart <= -0.01:
                prov += f" · {deja} : recompte plus bas ({_usd(ecart)}), rien à reprendre, à vérifier"
            elif c_m >= 0.01:
                prov += f" · {deja} : rien de plus"
        lignes.append(f"· {nom} — {_fmt(payes)} payées ({_fmt(hors)} visiteurs) → **{_usd(montant)}** → {adr}{bonus}{prov}")
    if annonce is not None:
        presents = {uid for _, uid, _, _, _, _ in rangs}
        for uid in annonce:
            verse = _deja_verse(annonce, uid)[2]
            if uid not in presents and verse >= 0.01:
                lignes.append(f"· {nom_de(uid)} — déjà versé {_usd(verse)}, plus rien au recompte : rien à reprendre, à vérifier")
    if notes_eq:
        lignes.append("📝 **Primes d'équipe à 0 $, à vérifier** (rien à virer) :")
        lignes.extend(f"· {nom} — 👥 {det}" for _, nom, det in notes_eq)
    tampon = io.StringIO(); ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["prenom", "discord_id", "visites_payees", "visiteurs_hors_robots", "montant_usd", "adresse"]
                      + (["prime_equipe_usd", "detail_prime"] if p_eq_rangs else [])
                      + (["deja_verse_usd", "reste_usd"] if annonce is not None else []))
    for nom, uid, payes, hors, montant, w in rangs:
        en_plus = []
        if p_eq_rangs:
            m_e, det_e, _ = p_eq_rangs.get(uid, (0.0, "", False))
            en_plus = [f"{m_e:.2f}".replace(".", ","), det_e]
        if annonce is not None:
            verse = _deja_verse(annonce, uid)[2]
            en_plus += [f"{verse:.2f}".replace(".", ","), f"{round(montant - verse, 2):.2f}".replace(".", ",")]
        ecrivain.writerow([nom, uid, payes, hors, f"{montant:.2f}".replace(".", ","), w] + en_plus)
    entete = (f"💸 **Paie au clic du {jour_paie}** — période {debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}, "
              f"{_usd(TAUX_CLIC)} la visite payée ({PAYS_LIBELLE}, hors robots)")
    pied = (f"**Total : {_usd(total)}** · {len(rangs)} clipper(s) au clic" + (f" · ⚠️ {sans} sans adresse" if sans else "")
            + ("\n-# Le virement reste à faire à la main (Binance / banque). Le CSV est joint." if annonce is None else
               "\n-# Recompte d'une paie déjà virée : seul le **reste** de chaque ligne est dû (colonne reste_usd du CSV joint)."))
    t_eq = round(sum(m for m, _, _ in p_eq_rangs.values()), 2)
    if t_eq >= 0.01:
        n_eq = sum(1 for m, _, _ in p_eq_rangs.values() if m >= 0.01)
        pied += (f"\n\n👥 **Primes d'équipe : {_usd(t_eq)}** ({n_eq} ligne(s), comprises dans le total). Avant le virement : "
                 "5 abonnés par VA primé à contrôler sur Infloww ou MyPulse, et chaque « ⚠️ à vérifier ».")
    if fixes:
        fixes.sort(key=lambda f: -f[1])
        pied += ("\n\n🧾 **Au fixe, hors liste** (ce qu'ils auraient touché au clic) : "
                 + " · ".join(f"{n} {_fmt(v)} = {_usd(v * TAUX_CLIC)}" for n, v in fixes))
    parr = {uid: round(sum(pr for _, pr in lst), 2) for uid, lst in primes.items()}
    return ([entete] + (lignes or ["· (aucune visite payée sur la période)"]) + [pied], tampon.getvalue(),
            _rangs_paie(rangs, p_eq_rangs, parr, notes_eq))


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
        if not lid or (d["liens"].get(lid) or {}).get("archive") or lid in deja or not prenom or normaliser(prenom) in CLICS_EXCLURE or len(prenom) < 3:
            continue
        if note_du_sortant(d["liens"].get(lid) or {}, l.get("note")):  # 09/10 : le lien d'un sortant, jamais à son homonyme
            continue
        if (d["liens"].get(lid) or {}).get("note_attendue"):           # revue CLICS : passé chez le repreneur Metricool, note pas
            continue                                                    # encore posée dans GAML (« Clipping <sortant> » : jamais à l'homonyme)
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
            jour = _aujourdhui().isoformat()                               # 03/10 (Gaëtan) : l'alerte une fois par jour et par lien, pas à chaque passage
            if d.setdefault("avertis", {}).get(lid) != jour:
                d["avertis"][lid] = jour
                lignes.append(f"⚠️ {l.get('note')} ({creatrice}) : {len(candidats)} membres possibles, à trancher avec `!lien`.")
            journal.info("Lien GAML %s (%s) : %s candidats, non attribué", l.get("note"), creatrice, len(candidats))
            continue
        uid = surs[0][0]
        # 08/10 (revue) : libéré, repris, revenu au clipping → ses visites partent d'aujourd'hui. 09/10 (dashboard) : une fiche
        # seulement relevée n'a jamais eu de clipper (lien neuf « Clipping Prénom ») : tout son historique est à lui
        connu = lid in d["liens"] and not releve_seul(d["liens"][lid])
        dus_av = (d["liens"].get(lid) or {}).get("dus")
        d["liens"][lid] = {"uid": uid, "note": l.get("note"), "url": l.get("url"), "creatrice": creatrice,
                           "depuis": _aujourdhui().isoformat() if connu else max(CLICS_DEPUIS, str(l.get("createdAt", ""))[:10] or CLICS_DEPUIS),
                           "par": "auto"}
        if dus_av:
            d["liens"][lid]["dus"] = dus_av                             # 09/10 : les visites dues à un sortant restent à lui
        lignes.append(f"🔗 {l.get('note')} ({creatrice}) → <@{uid}>")
        journal.info("Lien GAML %s (%s) → membre %s", l.get("note"), creatrice, uid)
    return lignes


# ------------------------------------------------------------------ relevés et ligne du matin
def _manque(jours: dict, j: date) -> bool:
    """Le jour `j` est-il à (re)lire ? Absent, ou un vieux 404 enregistré à 0 avant le 09/10 (`erreur`)."""
    v = (jours or {}).get(j.isoformat())
    return not releve_valide(v)


ECHEC_REESSAI = int(os.environ.get("CLICS_ECHEC_REESSAI", "1800") or 1800)   # revue CLICS : un lien en erreur retenté 30 min après
ECHEC_MALADE = int(os.environ.get("CLICS_ECHEC_MALADE", "86400") or 86400)   # 09/10 : un lien en échec depuis moins de 24 h = « malade »
SUITE_MAX = int(os.environ.get("CLICS_SUITE_MAX", "5") or 5)                   # garde-fou : erreurs de suite qui arrêtent un passage
_ERREURS_GLOBALES = ("injoignable", "trop de tentatives (429)")


def _erreur_globale(erreur) -> bool:
    """Revue CLICS du 09/10 (un seul lien /ytb qui répondait « GAML 400 » arrêtait le direct de tous les liens et la relecture de
    6 h) : une erreur GLOBALE (limite de la minute, GAML injoignable, 429 répété jusqu'à « trop de tentatives (429) ») arrête le
    passage ; toute autre erreur (400, 403, 5xx répété, délai dépassé sur une analytique lourde…) est propre au lien : on passe au
    suivant. 09/10 (R3 bis) : le 5xx répété n'est plus global (un lien /ytb en 500 permanent arrêtait encore tout) ; une vraie panne
    se voit à deux liens sains en erreur de suite (_Suite)."""
    return isinstance(erreur, LimiteGAML) or any(m in str(erreur) for m in _ERREURS_GLOBALES)


def _erreur_du_lien(erreur) -> bool:
    """09/10 (revue CLICS, R3 bis : toutes les pages /ytb en « GAML 400 unsupported link type ») : un 4xx définitif (400, 403, 405,
    410, 422…) est propre au lien par nature — GAML a répondu, tout de suite, sans rejeu : jamais le signe d'une panne. Il ne compte
    donc pas dans les erreurs de suite qui arrêtent un passage. 401 (clé refusée) et 408 (délai) restent des signes de panne."""
    m = re.match(r"\s*GAML (4\d\d) sur ", str(erreur or ""))
    return bool(m) and m.group(1) not in ("401", "408", "429")


def _malade(info: dict, maintenant, cle: str) -> bool:
    """09/10 (revue CLICS, R3 bis) : le lien a-t-il échoué depuis moins de ECHEC_MALADE secondes sur CE canal (`cle` : « echec » pour
    le relevé, « echec_direct » pour le direct) ? Un tel lien passe APRÈS les liens sains et son erreur ne compte pas comme un signe
    de panne (un succès du même canal efface l'échec). 10/10 (revue CLICS, 2e passe) : chaque canal ne juge que ses propres échecs.
    Le direct (/analytics/countries sur la journée en cours, encore partielle) et le relevé (countries puis /analytics/visitors sur
    une journée entière, plus lourd) n'échouent pas pour les mêmes raisons : un succès de l'un ne prouve rien pour l'autre (avant :
    le direct effaçait l'`echec` du relevé, deux pages en « délai dépassé » sur visitors redevenaient « saines » à chaque passage
    et arrêtaient rattraper à l'étape 1, relecture de 6 h et jours anciens jamais faits)."""
    e = (info or {}).get(cle) or {}
    try:
        return bool(e) and maintenant.timestamp() - float(e.get("ts") or 0) < ECHEC_MALADE
    except (TypeError, ValueError):
        return False


def _sain(d: dict, lid: str, maintenant, cle: str) -> bool:
    """09/10 (revue CLICS, R3 bis) : le lien a-t-il été lu avec succès récemment sur ce canal, sans échec depuis ? Seule l'erreur d'un
    tel lien est un signe de panne de GAML : une page jamais lisible (/ytb « unsupported link type », 5xx permanent) ne l'est pas.
    10/10 (revue CLICS, 2e passe) : pour le relevé (`cle` = « echec »), seul son propre historique compte (un jour relevé dans les
    trois derniers jours, pas d'`echec` récent) : un direct réussi ne rend pas « sain » un lien dont le relevé échoue. Pour le direct
    (« echec_direct »), un direct du jour ou de la veille compte aussi."""
    if _malade((d.get("liens") or {}).get(lid), maintenant, cle):
        return False
    if cle == "echec_direct":
        veille = (maintenant.date() - timedelta(days=1)).isoformat()
        if str(((d.get("aujourdhui") or {}).get(lid) or {}).get("jour") or "") >= veille:
            return True
    depuis = (maintenant.date() - timedelta(days=3)).isoformat()
    return any(j >= depuis for j in ((d.get("jours") or {}).get(lid) or {}))


class _Suite:
    """09/10 (revue CLICS, R3 bis : 4 pages /ytb en erreur persistante, toujours en tête, arrêtaient chaque passage sur « deux liens
    différents de suite ») : quand arrêter un passage de relevés sur des erreurs de suite. Arrêt sur deux erreurs de suite de deux
    liens SAINS différents (lus avec succès récemment, sans échec depuis : GAML probablement en panne), ou sur SUITE_MAX erreurs de
    suite en tout (garde-fou : liens tous malades ou jamais lus pendant une panne). Un 4xx définitif (_erreur_du_lien) ne compte
    jamais ; un succès remet tout à zéro."""

    def __init__(self):
        self.saines, self.toutes = [], 0

    def succes(self) -> None:
        self.saines.clear()
        self.toutes = 0

    def erreur(self, lid: str, erreur, sain: bool) -> bool:
        """Note l'erreur du lien `lid` (`sain` : jugé AVANT cet essai, _sain). True = arrêter le passage."""
        if _erreur_du_lien(erreur):
            return False
        self.toutes += 1
        if sain:
            self.saines.append(lid)
        return len(set(self.saines[-2:])) == 2 or self.toutes >= SUITE_MAX


def _horodatage(maintenant=None) -> str:
    """L'heure ISO UTC (à la seconde) de `maintenant` (heure_paris du bot, lue maintenant par défaut) ; l'horloge si elle est naïve."""
    m = maintenant if maintenant is not None else _deps["heure_paris"]()
    return (m.astimezone(timezone.utc) if m.tzinfo else datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _echec(info: dict, cle: str, erreur, maintenant, jour_iso: str = "") -> None:
    """Pose `info[cle]` = {jour, t (ISO UTC), ts (horloge du bot, pour le délai de reprise), erreur} : le lien n'est retenté
    qu'ECHEC_REESSAI secondes plus tard, les autres passent."""
    info[cle] = {"jour": jour_iso, "t": _horodatage(maintenant), "ts": round(maintenant.timestamp(), 1), "erreur": str(erreur)[:160]}


def _en_echec(info: dict, cle: str, maintenant) -> bool:
    e = (info or {}).get(cle) or {}
    try:
        return bool(e) and maintenant.timestamp() - float(e.get("ts") or 0) < ECHEC_REESSAI
    except (TypeError, ValueError):
        return False


def _depuis_moins_de(ts, maintenant, secondes: int) -> bool:
    try:
        return maintenant.timestamp() - float(ts) < secondes
    except (TypeError, ValueError):
        return False


def _noter_echec_releve(info: dict, jour_iso: str, erreur, maintenant) -> None:
    """10/10 (revue CLICS, reprise de la 3e passe : chez Tom, le 12/10, jour viral trop lourd pour GAML, échouait toujours et bloquait la
    relecture des 05 → 11/10, pourtant lisibles) : l'échec du relevé est noté pour le JOUR. `echec` = le dernier échec (_malade, _sain),
    avec `jours` = les jours différents en échec depuis le dernier succès du lien ; `echecs_jours` = {jour: ts} (gardés ECHEC_MALADE
    secondes, même après le succès d'un autre jour) : ce jour seul n'est retenté qu'ECHEC_REESSAI secondes plus tard, et après les jours
    jamais en échec."""
    precedents = [j for j in ((info.get("echec") or {}).get("jours") or []) if j != jour_iso]
    _echec(info, "echec", erreur, maintenant, jour_iso)
    info["echec"]["jours"] = (precedents + [jour_iso])[-6:]
    ej = {j: ts for j, ts in (info.get("echecs_jours") or {}).items() if _depuis_moins_de(ts, maintenant, ECHEC_MALADE)}
    ej[jour_iso] = round(maintenant.timestamp(), 1)
    info["echecs_jours"] = ej


def _lien_bloque(info: dict, maintenant) -> bool:
    """10/10 : le relevé du LIEN entier est-il en pause (ECHEC_REESSAI secondes après son dernier échec) ? Seulement quand l'échec
    n'est pas propre à un jour : deux jours différents en échec sans un succès entre deux (page morte, 5xx permanent), ou un 4xx
    définitif (/ytb « unsupported link type »). Un seul jour en échec (jour viral trop lourd) ne bloque que lui (_jour_en_echec)."""
    if not _en_echec(info, "echec", maintenant):
        return False
    e = (info or {}).get("echec") or {}
    if "jours" not in e:                                                # échec noté avant le 10/10 : son jour seulement (`jour`)
        return not e.get("jour")
    return len(set(e.get("jours") or [])) >= 2 or _erreur_du_lien(e.get("erreur"))


def _jour_en_echec(info: dict, jour_iso: str, maintenant) -> bool:
    """10/10 : le relevé de CE jour du lien a-t-il échoué il y a moins d'ECHEC_REESSAI secondes ?"""
    ts = ((info or {}).get("echecs_jours") or {}).get(jour_iso)
    if ts is not None:
        return _depuis_moins_de(ts, maintenant, ECHEC_REESSAI)
    e = (info or {}).get("echec") or {}
    return "jours" not in e and str(e.get("jour") or "") == jour_iso and _en_echec(info, "echec", maintenant)


def _releve_en_pause(info: dict, jour_iso: str, maintenant) -> bool:
    return _lien_bloque(info, maintenant) or _jour_en_echec(info, jour_iso, maintenant)


def _dus_recents(info: dict, hier: date, recul: int = 45) -> list:
    """Les `dus` du lien (visites dues à un ancien détenteur) dont un jour tombe dans les `recul` jours avant `hier`."""
    limite = hier - timedelta(days=recul)
    out = []
    for e in (info or {}).get("dus") or []:
        de, av = (_en_date(e.get("depuis")), _en_date(e.get("avant"))) if isinstance(e, dict) else (None, None)
        if de is not None and av is not None and av - timedelta(days=1) >= limite and de < av:
            out.append((de, av))
    return out


def _plancher_releve(info: dict, hier: date):
    """10/10 (revue CLICS, reprise de la 3e passe : `!lien @Tom <e1> forcer` tapé à 0 h, avant la relecture de la veille, ou pendant
    que le relevé du 15/10 de e1 échouait : `depuis` passait au 16/10 et le 15/10, dû à Eddy, n'était plus jamais relu ; la paie de
    toute l'équipe attendait midi, puis Eddy était payé « provisoire » pour toujours) : le premier jour à relever d'un lien = le plus
    ancien de son `depuis` et des `dus[].depuis` encore dans la fenêtre de 45 jours (relus comme un lien payé). None sans l'un ni l'autre."""
    dates = [x for x in [_en_date((info or {}).get("depuis"))] + [de for de, _ in _dus_recents(info, hier)] if x is not None]
    return min(dates) if dates else None


async def relever_jour(d: dict, lid: str, j: date, maintenant=None, visiteurs: dict = None) -> str:
    """Le relevé d'un jour (heure de Paris) d'un lien, rangé dans `d["jours"]` puis écrit sur le disque. Renvoie 'ok', '404' (lien
    introuvable : `introuvable` posé, rien d'écrit, retenté demain), 'erreur' (propre à ce lien : `echec` posé, retenté
    ECHEC_REESSAI secondes plus tard) ou 'global' (GAML en panne ou limite atteinte : l'appelant s'arrête). Jamais un 0 sur une
    erreur. Une veille lue avant RELECTURE_HEURE (Paris) est provisoire : relue une fois après, puis figée. Partagé par `rattraper`
    et le secours de onboarding.clics_classeur (contrat C6(e) : le classeur lit les mêmes jours que le Dashboard).
    11/10 (contre-vérification CLICS, passe 3) : `visiteurs` (rattraper : {"ko": [liens], "coupe": bool}, un par passage) — après deux
    liens différents de suite en erreur sur /analytics/visitors (hors 4xx définitif), visitors n'est plus appelé de tout le passage
    (avant : 55 erreurs de 30 à 45 s, un passage de 28 à 41 min, le direct sauté) ; et un total robots compris déjà rangé pour ce
    jour n'est jamais remplacé par None (la relecture de 6 h pendant une panne de visitors le perdait pour toujours)."""
    maintenant = maintenant if maintenant is not None else _deps["heure_paris"]()
    jour_iso = maintenant.date().isoformat()
    hier = maintenant.date() - timedelta(days=1)
    info = d.setdefault("liens", {}).setdefault(lid, {"uid": "", "releve": True, "par": "releve"})   # (appelants : lien connu)
    provisoires = d.setdefault("provisoires", {})
    erreurs = {}                                                        # 11/10 : l'erreur de /analytics/visitors (releve)
    try:
        v = await (releve(lid, j) if visiteurs is None else releve(lid, j, sans_visitors=bool(visiteurs.get("coupe")), erreurs=erreurs))
    except Exception as erreur:                                         # noqa: BLE001 — une réponse illisible (JSON, valeur) aussi :
        journal.warning("Relevé %s %s : %s", info.get("note") or lid, j, erreur)   # propre à ce lien, jamais tout le passage
        if "404" in str(erreur):
            info["introuvable"] = jour_iso                              # rien d'écrit : ni 0 ni trou comblé, retenté demain
            _ecrire(d)
            return "404"
        if _erreur_globale(erreur):
            return "global"
        _noter_echec_releve(info, j.isoformat(), erreur, maintenant)     # 10/10 : l'échec du JOUR (les autres jours restent lus)
        _ecrire(d)
        return "erreur"
    js = j.isoformat()
    v = dict(v)
    err_v = erreurs.get("visitors")
    if visiteurs is not None and not visiteurs.get("coupe") and not _erreur_du_lien(err_v):
        if err_v is None:
            visiteurs["ko"] = []                                        # visitors a répondu : la suite repart de zéro
        else:
            visiteurs.setdefault("ko", []).append(lid)
            if len(set(visiteurs["ko"][-2:])) == 2:
                visiteurs["coupe"] = True
                journal.warning("Relevés GAML : /analytics/visitors en erreur sur deux liens de suite, plus appelé de ce passage "
                                "(visites payées gardées, total robots non lu)")
    ancien = ((d.get("jours") or {}).get(lid) or {}).get(js)
    if v.get("brut") is None and isinstance(ancien, dict) and ancien.get("brut") is not None and not ancien.get("erreur"):
        v["brut"] = ancien["brut"]                                      # 11/10 : le total robots déjà lu est gardé
        v.pop("brut_non_lu", None)
    d.setdefault("jours", {}).setdefault(lid, {})[js] = v
    info.pop("echec", None)                                             # 10/10 : seulement l'échec du relevé (`echec_direct` : le direct, _malade)
    ej = {k: ts for k, ts in (info.get("echecs_jours") or {}).items() if k != js and _depuis_moins_de(ts, maintenant, ECHEC_MALADE)}
    if ej:
        info["echecs_jours"] = ej                                       # les autres jours en échec gardent leur délai
    else:
        info.pop("echecs_jours", None)
    if j == hier and maintenant.hour < RELECTURE_HEURE:
        if js not in provisoires.setdefault(lid, []):
            provisoires[lid].append(js)
    else:                                                               # relu après RELECTURE_HEURE : figé
        if js in provisoires.get(lid, []):
            provisoires[lid].remove(js)
        if lid in provisoires and not provisoires[lid]:
            provisoires.pop(lid, None)
    _ecrire(d)
    return "ok"


async def rattraper(d: dict, limite_appels: int = 110) -> int:
    """Complète les jours manquants (depuis `depuis`, jusqu'à hier) de chaque lien relevé (`a_relever`). Borné par appel pour
    respecter la limite GAML ; la boucle repasse un quart d'heure plus tard.
    09/10 (dashboard, contrat C2) : 1. tous les liens actifs, pas seulement les payés (pages de créatrice, /ytb, /fb, libérés, hors
    clipping : RELEVE_RECUL jours en arrière pour eux) ; 2. la veille d'abord pour tous (paie, ligne du matin, rapport), les liens
    payés en tête, puis les jours anciens (RELEVE_ANCIENS_MAX appels par passage : le rattrapage d'un lien neuf ne prend jamais
    toute la minute de l'app) ; 3. une erreur GAML n'écrit JAMAIS de 0 : le jour reste absent (relever_jour) ; 4. une veille lue avant
    RELECTURE_HEURE (Paris) est provisoire : relue une fois après, puis figée (dernières visites de la soirée, robots reclassés).
    Revue CLICS du 09/10 : une erreur propre à UN lien (400, 403, délai dépassé…) ne bloque plus les autres : le lien est noté
    `echec` et sauté ECHEC_REESSAI secondes ; le passage s'arrête seulement sur une erreur globale (limite, GAML injoignable, 429
    répété) ou sur deux échecs de suite de deux liens différents (GAML probablement en panne).
    09/10 (R3 bis : toutes les pages /ytb en erreur persistante arrêtaient encore chaque passage) : un lien « malade » (en échec depuis
    moins de 24 h) passe après les liens sains à chaque étape (sa veille après les relectures de l'étape 2) et son erreur ne compte
    pas comme un signe de panne, pas plus qu'un 4xx définitif ou l'erreur d'un lien jamais lu (_Suite, _sain)."""
    maintenant = _deps["heure_paris"]()
    aujourdhui = maintenant.date()
    hier = aujourdhui - timedelta(days=1)
    jour_iso = aujourdhui.isoformat()
    provisoires = d.setdefault("provisoires", {})
    appels, anciens = 0, 0
    suite = _Suite()                                                    # erreurs de suite (remises à zéro par un succès)
    visiteurs = {"ko": [], "coupe": False}                              # 11/10 : le disjoncteur de /analytics/visitors (relever_jour)

    async def lire(lid: str, j: date) -> str:
        """'ok', '404', 'erreur' (ce lien seulement) ou 'stop' (fin du passage)."""
        nonlocal appels
        if appels and RELEVE_PAUSE > 0:
            await asyncio.sleep(RELEVE_PAUSE)                           # minuit : ~55 liens d'un coup, la minute reste partagée avec l'app
        # jugé AVANT l'essai (relever_jour pose le nouvel échec) ; 10/10 : un jour qui a déjà échoué (jour trop lourd pour GAML) et
        # qu'on retente n'est jamais un signe de panne
        sain = (_sain(d, lid, maintenant, "echec")
                and j.isoformat() not in (((d.get("liens") or {}).get(lid) or {}).get("echecs_jours") or {}))
        sans_v = visiteurs["coupe"]
        r = await relever_jour(d, lid, j, maintenant, visiteurs)
        appels += (1 if sans_v else 2) if r == "ok" else 1             # 11/10 : visitors coupé → un seul appel (countries)
        if r == "global":
            return "stop"
        if r == "erreur":
            if suite.erreur(lid, ((d["liens"].get(lid) or {}).get("echec") or {}).get("erreur"), sain):
                journal.warning("Relevés GAML : liens en erreur de suite, la suite au prochain passage")
                return "stop"
            return "erreur"
        suite.succes()
        return r

    def payant(info):
        # 10/10 : un lien qui porte des visites dues à un ancien détenteur (`dus`) est relu comme un lien payé
        return bool(str(info.get("uid") or "") or info.get("suivi") or _dus_recents(info, hier))
    cibles = [(lid, info) for lid, info in list(d["liens"].items()) if a_relever(info, jour_iso)]
    # tri stable (l'ordre du fichier sinon) : les liens malades en dernier, puis les liens payés en tête
    cibles.sort(key=lambda li: (_malade(li[1], maintenant, "echec"), 0 if payant(li[1]) else 1))
    malades = {lid for lid, info in cibles if _malade(info, maintenant, "echec")}

    def fiche(lid: str, info: dict) -> dict:
        return d["liens"].get(lid) or info                              # relue : _ecrire peut avoir fusionné une écriture concurrente

    async def veilles(liste) -> bool:
        """La veille de chaque lien de `liste` ; True = fin du passage (budget ou arrêt)."""
        for lid, info in liste:
            if appels >= limite_appels:
                return True
            info = fiche(lid, info)
            # 10/10 : le plancher compte les jours dus à l'ancien détenteur (`dus`), et seul l'échec de la veille elle-même (ou du
            # lien entier) la fait attendre
            debut = _plancher_releve(info, hier) or _jour(CLICS_DEPUIS)
            if (hier < debut or not _manque(d["jours"].get(lid, {}), hier) or str(info.get("introuvable") or "") == jour_iso
                    or _releve_en_pause(info, hier.isoformat(), maintenant)):
                continue
            if await lire(lid, hier) == "stop":
                return True
        return False
    # 1. la veille de chaque lien sain (09/10 : ceux des liens malades après les relectures de l'étape 2, qu'ils ne retardent jamais)
    if await veilles([li for li in cibles if li[0] not in malades]):
        return appels
    # 2. la relecture des veilles provisoires, une fois passé RELECTURE_HEURE (ou un jour plus tard) ; les liens malades en dernier
    for lid in sorted(provisoires, key=lambda l_: l_ in malades):
        info = d["liens"].get(lid)
        if info is None or not a_relever(info, jour_iso):
            provisoires.pop(lid, None)
            continue
        for js in sorted(provisoires.get(lid, [])):
            j = _en_date(js)
            if j is None or j >= aujourdhui:
                if js in provisoires.get(lid, []):
                    provisoires[lid].remove(js)
                if lid in provisoires and not provisoires[lid]:
                    provisoires.pop(lid, None)
                continue
            if (j == hier and maintenant.hour < RELECTURE_HEURE) or _releve_en_pause(fiche(lid, info), js, maintenant):
                continue
            if appels >= limite_appels:
                return appels
            r = await lire(lid, j)
            if r == "stop":
                return appels
            if r in ("404", "erreur"):
                break
    # 2 bis. la veille des liens malades
    if await veilles([li for li in cibles if li[0] in malades]):
        return appels
    # 3. les jours plus anciens (les liens malades en dernier). 10/10 (revue CLICS, reprise de la 3e passe : chez Tom, le 12/10 en
    # échec permanent — jour viral trop lourd pour GAML — arrêtait la descente à chaque passage, les 05 → 11/10 n'étaient jamais
    # relus) : un jour en échec ne fait attendre que lui ; la descente continue vers les jours plus anciens, les jours jamais en échec
    # d'abord (les plus récents en tête), puis ceux dont l'échec a passé ECHEC_REESSAI. Le lien entier n'attend que si deux jours
    # différents échouent sans un succès entre deux, ou sur un 4xx définitif (_lien_bloque) ; `_Suite` arrête toujours le passage
    # sur une vraie panne. Le plancher compte les jours dus à un ancien détenteur (`dus`).
    for lid, info in cibles:
        info = fiche(lid, info)
        recul = 45 if payant(info) else RELEVE_RECUL - 1
        debut = max(_plancher_releve(info, hier) or _jour(CLICS_DEPUIS), hier - timedelta(days=recul))
        if str(info.get("introuvable") or "") == jour_iso or _lien_bloque(info, maintenant):
            continue
        jours, a_lire, j = d["jours"].get(lid, {}), [], hier - timedelta(days=1)
        while j >= debut:
            if _manque(jours, j) and not _jour_en_echec(info, j.isoformat(), maintenant):
                a_lire.append(j)
            j -= timedelta(days=1)
        deja = info.get("echecs_jours") or {}
        a_lire.sort(key=lambda x: x.isoformat() in deja)                # tri stable : du plus récent au plus ancien dans chaque groupe
        for j in a_lire:
            info = fiche(lid, info)
            if str(info.get("introuvable") or "") == jour_iso or _lien_bloque(info, maintenant):
                break
            if not _manque(d["jours"].get(lid, {}), j):
                continue
            if appels >= limite_appels or anciens >= RELEVE_ANCIENS_MAX:
                return appels
            avant = appels
            r = await lire(lid, j)
            anciens += appels - avant
            if r == "stop":
                return appels
    return appels


async def completer(lid: str, debut, fin, maximum: int = 14) -> tuple:
    """Contrat C6(e) (09/10, revue CLICS) : le secours GAML de onboarding.clics_classeur. Les jours manquants du lien sur [debut,
    fin] (fin ≤ hier ; le plancher `depuis` du lien appliqué) sont relevés et RANGÉS dans clics.json (relever_jour, `maximum` appels au
    plus), puis l'appelant relit la période avec clics_lien : le classeur, le Dashboard, le contrôle et le bouclage comptent les mêmes
    jours avec la même règle (avant : une somme GAML de toute la période, que ni clics.json ni le Dashboard ne connaissaient).
    10/10 (revue CLICS, reprise de la 3e passe) : un jour en échec ne fait attendre que lui (les autres jours sont relevés ; arrêt sur le
    lien entier en échec, _lien_bloque, sur un 404 ou une panne) ; le plancher compte les jours dus à un ancien détenteur (`dus`), relevés
    APRÈS ceux du détenteur actuel (du plus récent au plus ancien : le budget `maximum` sert d'abord ce que l'appelant relit).
    Renvoie (état relu de clics.json, appels GAML faits)."""
    maintenant = _deps["heure_paris"]()
    hier = maintenant.date() - timedelta(days=1)
    debut, fin = _en_date(debut), min(_en_date(fin) or hier, hier)
    d = _lire()
    info = (d.get("liens") or {}).get(str(lid))
    if info is None:
        return d, 0                                                     # lien inconnu du bot : la passe horaire le marquera `releve`
    dep = _plancher_releve(info, hier)
    if debut is None or (dep is not None and dep > debut):
        debut = dep
    if debut is None or debut > fin or _lien_bloque(info, maintenant) or str(info.get("introuvable") or "") == maintenant.date().isoformat():
        return d, 0
    appels, j = 0, fin
    while j >= debut and appels < maximum:
        info = (d.get("liens") or {}).get(str(lid)) or info
        if _lien_bloque(info, maintenant):
            break
        if _manque((d.get("jours") or {}).get(str(lid), {}), j) and not _jour_en_echec(info, j.isoformat(), maintenant):
            if appels and RELEVE_PAUSE > 0:
                await asyncio.sleep(RELEVE_PAUSE)
            r = await relever_jour(d, str(lid), j, maintenant)
            appels += 2 if r == "ok" else 1
            if r in ("404", "global"):
                break
        j -= timedelta(days=1)
    return d, appels


async def rafraichir_aujourdhui(d: dict, maximum: int = None) -> int:
    """Contrat C2 (09/10, dashboard : « tout voir, le plus souvent possible ») : `aujourdhui[lid]` = {jour (Paris), t (ISO UTC), brut,
    hors_robots, payes} de la journée de Paris en cours, un appel `/analytics/countries` par lien relevé (`a_relever`). `brut` reste
    None : le total robots compris demande un second appel par lien, hors budget toutes les 15 minutes (jamais un faux 0). Budget
    GAML (60 requêtes/min partagées avec l'app) : `maximum` appels au plus (DIRECT_MAX), DIRECT_PAUSE secondes entre deux, arrêt
    sur un 429 ou quand il reste moins de DIRECT_RESERVE requêtes dans la minute ; les liens jamais lus aujourd'hui passent d'abord,
    puis les plus anciens (tous relus en deux passages au pire). Une erreur n'écrit rien : la valeur précédente reste, avec son
    heure. Renvoie le nombre d'appels faits. Écrit `d`.
    Revue CLICS du 09/10 : 1. une erreur propre à UN lien (400, 403, délai dépassé…) ne coupe plus le direct des autres : le lien
    est noté `echec_direct` et sauté ECHEC_REESSAI secondes (avant : jamais lu, il revenait en tête à chaque passage et arrêtait
    tout) ; arrêt seulement sur une erreur globale ou deux échecs de suite de deux liens différents ; 2. chaque relevé porte l'heure
    de SA réponse (avant : l'heure du début du passage, jusqu'à 3 min d'avance). 09/10 (R3 bis : 4 pages /ytb en erreur persistante,
    jamais lues donc toujours en tête, arrêtaient chaque passage) : les liens malades (en échec depuis moins de 24 h) passent après
    les liens sains, et ni leur erreur, ni celle d'un lien jamais lu, ni un 4xx définitif ne comptent comme un signe de panne
    (_Suite, _sain) ; DIRECT_MALADES essais leur
    restent réservés en fin de passage (plus de liens sains que le budget : un lien en échec passager est quand même retenté).
    10/10 (revue CLICS, 2e passe) : 1. les liens du passage sont choisis par ancienneté, malades compris (avant : les malades
    n'avaient que les essais restants, 3 au moins ; après une panne de GAML de deux heures, une vingtaine de liens devenus
    « malades » n'étaient relus que 3 par passage, plus d'une heure de « Clics aujourd'hui » périmé) ; les malades choisis passent
    toujours en fin de passage ; 2. le direct n'efface que son propre échec (`echec_direct`), jamais celui du relevé (_malade)."""
    maximum = DIRECT_MAX if maximum is None else maximum
    maintenant = _deps["heure_paris"]()
    jour = maintenant.date()
    jour_iso, veille = jour.isoformat(), (jour - timedelta(days=1)).isoformat()
    auj = d.setdefault("aujourdhui", {})
    for lid in list(auj):                                               # ménage : un lien disparu, un relevé d'avant-hier
        if lid not in d.get("liens", {}) or str((auj.get(lid) or {}).get("jour") or "") < veille:
            auj.pop(lid, None)
    cibles = [lid for lid, info in d.get("liens", {}).items()
              if a_relever(info, jour_iso) and not _en_echec(info, "echec_direct", maintenant)]
    malades = {lid for lid in cibles if _malade(d["liens"].get(lid), maintenant, "echec_direct")}
    cibles.sort(key=lambda lid: ((auj.get(lid) or {}).get("jour") == jour_iso, str((auj.get(lid) or {}).get("t") or "")))
    budget = max(0, maximum)
    mal = [l for l in cibles if l in malades]
    choisis = set(mal[:min(len(mal), DIRECT_MALADES, budget)])          # quelques essais réservés aux malades
    for lid in cibles:                                                  # puis les plus anciens, malades compris
        if len(choisis) >= budget:
            break
        choisis.add(lid)
    cibles = ([l for l in cibles if l in choisis and l not in malades]
              + [l for l in cibles if l in choisis and l in malades])   # les malades en fin de passage
    appels, suite = 0, _Suite()
    jeton = _arret_429.set(True)
    try:
        for lid in cibles:
            if appels and DIRECT_PAUSE > 0:
                await asyncio.sleep(DIRECT_PAUSE)
            if _limite["restant"] <= DIRECT_RESERVE and _limite["reset"] > time.time():
                journal.info("Clics du jour : %s requêtes GAML restantes dans la minute, la suite au prochain passage", _limite["restant"])
                break
            info = d["liens"].get(lid) or {}
            sain = _sain(d, lid, maintenant, "echec_direct")            # jugé AVANT l'essai
            try:
                rep = await _requete("GET", "/analytics/countries", params={"link_id": lid, "range": "custom", "date_from": jour_iso,
                                                                             "date_to": jour_iso, "timezone": FUSEAU})
                hors_robots, payes = _comptes_pays(_liste_reponse(rep, "/analytics/countries"))
            except LimiteGAML as erreur:
                journal.info("Clics du jour : %s — arrêt du passage", erreur)
                break
            except Exception as erreur:                                 # noqa: BLE001 — réponse illisible comprise
                appels += 1
                journal.warning("Clics du jour %s : %s", lid, erreur)
                if "404" in str(erreur):
                    continue                                            # ce lien seulement ; le relevé quotidien le marquera
                if _erreur_globale(erreur):
                    break                                               # GAML en panne : on n'insiste pas
                _echec(info, "echec_direct", erreur, _deps["heure_paris"](), jour_iso)
                if suite.erreur(lid, erreur, sain):
                    journal.warning("Clics du jour : liens en erreur de suite, la suite au prochain passage")
                    break
                continue
            appels += 1
            suite.succes()
            info.pop("echec_direct", None)                              # 10/10 : jamais `echec` (le relevé échoue peut-être encore)
            auj[lid] = {"jour": jour_iso, "t": _horodatage(), "brut": None, "hors_robots": hors_robots, "payes": payes}
    finally:
        _arret_429.reset(jeton)
    _ecrire(d)
    return appels


def top_uids(d: dict, hier: date, n: int = 5) -> list:
    """Les uid des n premiers en visites payées sur les sept jours finissant `hier` (même calcul que le classement)."""
    debut = hier - timedelta(days=6)
    par_uid = {}
    for lid, info in d["liens"].items():
        if info.get("uid"):
            par_uid.setdefault(str(info["uid"]), []).append(lid)
    rangs = [(uid, somme(d, lids, debut, hier)["payes"]) for uid, lids in par_uid.items()]
    return [uid for uid, v in sorted((r for r in rangs if r[1] > 0), key=lambda r: -r[1])[:n]]


def texte_classement(d: dict, nom_de, hier: date, n: int = 5, equipe_de=None) -> str:
    """28/09 (GO n° 7) : le lundi, dans #dopamine, les cinq premiers en visites payées sur les sept derniers jours. '' si personne.
    18/10 (action 28 du plan : « classement par équipe TL ») : `equipe_de(uid)` → nom de l'équipe (prénom du TL) ou None ; les
    équipes sont classées dessous, avec le seuil de prime d'équipe."""
    debut = hier - timedelta(days=6)
    par_uid = {}
    for lid, info in d["liens"].items():
        if info.get("uid"):
            par_uid.setdefault(str(info["uid"]), []).append(lid)
    rangs = []
    for uid, lids in par_uid.items():
        s = somme(d, lids, debut, hier)
        if s["payes"] > 0:
            rangs.append((nom_de(uid), s["payes"]))
    if not rangs:
        return ""
    rangs.sort(key=lambda r: -r[1])
    lignes = [f"{i}. **{nom}** · {_fmt(v)} visites = {_usd(v * TAUX_CLIC)}" for i, (nom, v) in enumerate(rangs[:n], 1)]
    texte = (f"🏆 **Top {min(n, len(rangs))} de la semaine** ({debut.strftime('%d/%m')} → {hier.strftime('%d/%m')})\n" + "\n".join(lignes)
             + f"\n-# {len(rangs)} clipper(s) ont fait des visites cette semaine. Une visite = {_usd(TAUX_CLIC)}.")
    if equipe_de is not None:
        equipes = {}
        for uid, lids in par_uid.items():
            try:
                nom_e = equipe_de(uid)
            except Exception:                                           # noqa: BLE001
                nom_e = None
            if nom_e:
                e = equipes.setdefault(nom_e, [0, 0])
                e[0] += somme(d, lids, debut, hier)["payes"]
                e[1] += 1
        if equipes:
            ordre = sorted(equipes.items(), key=lambda x: -x[1][0])
            texte += ("\n\n👥 **Équipes de la semaine**\n" + "\n".join(
                f"{i}. **Équipe {nom}** · {_fmt(v)} visites · {k} clipper(s)" for i, (nom, (v, k)) in enumerate(ordre, 1)))
    return texte


async def envoyer_lignes_matin(d: dict) -> int:
    envoyes = 0
    salon_de = _deps["salon_perso"]
    for uid in {str(info.get("uid")) for info in d["liens"].values() if info.get("uid")}:
        texte = ligne_matin(d, uid)
        salon = salon_de(uid) if texte else None
        if salon is None:
            journal.info("Ligne du matin %s : %s", uid, "pas de relevé d'hier" if not texte else "salon perso introuvable ou fermé au bot")
            continue
        deposer = _deps.get("deposer")
        if deposer and deposer(salon.id, "clics", texte):              # 26/09 : dans le message du matin unique
            envoyes += 1
            continue
        try:
            await salon.send(texte)
            envoyes += 1
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Ligne du matin %s : %s", uid, erreur)
    return envoyes


async def annoncer_paie(client, d: dict, maintenant, manquants: dict = None) -> None:
    """Jour de paie (5 : période 20 → 4 ; 20 : période 5 → 19) : la liste et le CSV au salon admin, la feuille dans le tableur,
    et dans le salon perso de chaque clipper au clic sa ligne (visites payées, montant, adresse).
    10/10 (revue CLICS, 3e passe) : `manquants` (jours_manquants_paie, recalculé si absent) — les jours de la période pas encore
    relevés sont dits en tête de la liste admin (montants provisoires, sous-estimés) et sur la ligne du clipper concerné ; avant,
    `somme` les comptait 0 sans un mot."""
    cle = "5" if maintenant.day == 5 else "20"
    debut, fin = periode(cle, maintenant.strftime("%Y-%m"))
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None)          # noqa: E731
                          or str((registre.get(uid) or {}).get("prenom") or "").title() or f"id {uid}")
    reprises = await synchroniser_adresses(d)                           # 08/10 : les adresses collées dans l'app, avant la liste
    if reprises:
        _ecrire(d)
    if manquants is None:
        manquants = jours_manquants_paie(d, debut, fin, avec_provisoires=True)
    jour_paie = maintenant.strftime("%d/%m")
    lignes, csv_texte, rangs = liste_paie(d, nom_de, debut, fin, jour_paie, manquants=manquants)
    # 10/10 (revue CLICS, reprise de la 3e passe) : l'annonce est mémorisée une fois (`paies_annoncees`, jamais réécrite par
    # `!paie-clics`) ; ses jours manquants relevés, le complément part tout seul (completer_paies)
    # reprise L11 (R3) : les jours manquants des VA d'équipe (404 du jour compris) sont attendus aussi, tant que les primes ne sont
    # pas figées : le complément les porte quand ils arrivent
    eq_attendus = manquants_equipes(d, debut, fin, _cle_periode(jour_paie, fin))
    memoriser_annonce(d, _cle_periode(jour_paie, fin), rangs, _unir_manquants(manquants, eq_attendus) if eq_attendus else manquants,
                      debut, fin, jour_paie, maintenant)
    if manquants:
        limite = maintenant.date() + timedelta(days=COMPLEMENT_JOURS)
        lignes.insert(1, f"⚠️ **Jours pas encore relevés dans GAML** : montants provisoires, sous-estimés — {texte_manquants(manquants, nom_de)}. "
                         f"Dès qu'ils sont relevés (au plus tard le {limite.strftime('%d/%m')}), le **complément** est posté ici tout seul, "
                         f"avec l'onglet « {ONGLET_COMPLEMENT_PREFIXE}{_date_paie(jour_paie, fin)} ».")
    titre = await ecrire_feuille_paie(d, rangs, debut, fin, jour_paie, manquants=manquants)
    if titre:
        lignes.append(f"📗 Feuille « {titre} » écrite dans le tableur « {ADRESSES_TABLEUR} » (prénom, adresse USDC, montant"
                      + (", « provisoire » en note" if manquants else "") + ").")
    if reprises:
        lignes.append(f"📒 {len(reprises)} adresse(s) reprise(s) de l'app : " + ", ".join(reprises)[:600])
    canal = await _deps["canal_admin"]()
    if canal is not None:
        try:                                                            # 10/10 : la liste entière, en plusieurs messages
            await _envoyer_blocs(canal.send, lignes, discord.File(io.BytesIO(csv_texte.encode("utf-8-sig")),
                                                                  filename=f"paie_clics_{debut.isoformat()}_{fin.isoformat()}.csv"))
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Annonce de paie (admin) : %s", erreur)
    envoyes = 0
    # Lot L11 : le TL et le manager reçoivent leur montant (clic + prime d'équipe), même sans visite à eux (manager sans lien, TL au
    # fixe). Une prime à 0 $ (note « à vérifier ») ne leur écrit rien.
    p_eq = {uid: x for uid, x in (getattr(rangs, "primes_equipe", None) or {}).items() if x[0] >= 0.01}
    for uid in {str(i.get("uid")) for i in d["liens"].values() if i.get("uid")} | set(p_eq):
        prime, det_p, verif_p = p_eq.get(uid, (0.0, "", False))
        au_clic = regime(uid) == "clic"
        if not au_clic and not prime:
            continue
        dp = _debut_paie(uid, debut, d) if au_clic else debut
        s = somme(d, liens_de(d, uid), dp, fin) if au_clic else {"payes": 0}
        if not s["payes"] and not prime:
            continue                                                    # 08/10 (audit) : plus de « 0,00 $, !wallet maintenant » à un nouveau
        salon = _deps["salon_perso"](uid)
        if salon is None:
            continue
        w = d["wallets"].get(uid, {}).get("adresse", "")
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else w
        if prime:
            clic = round(s["payes"] * TAUX_CLIC, 2)
            pourquoi = resume_prime(det_p)
            equipe = f"{_usd(prime)} d'équipe" + (f" ({pourquoi})" if pourquoi else "")
            corps = (f"**{_usd(clic)} au clic + {equipe} = {_usd(round(clic + prime, 2))}**" if s["payes"] else f"**{equipe}**")
            texte = (f"💸 **Ta paie du {maintenant.strftime('%d/%m')}** (période {dp.strftime('%d/%m')} → {fin.strftime('%d/%m')}) : "
                     + corps + (f" ({_fmt(s['payes'])} visites payées)" if s["payes"] else ""))
        else:
            texte = (f"💸 **Ta paie du {maintenant.strftime('%d/%m')}** (période {dp.strftime('%d/%m')} → {fin.strftime('%d/%m')}) : "
                     f"**{_fmt(s['payes'])} visites payées = {_usd(s['payes'] * TAUX_CLIC)}**")
        texte += (f" → virement vers {adr} dans la journée." if w else " → ⚠️ pas d'adresse enregistrée : colle-la dans ton app (onglet Versements) ou `!wallet 0x…` maintenant, sinon la paie attend la prochaine.")
        if prime and verif_p:
            texte += ("\n\n-# Prime d'équipe à vérifier par Gaëtan avant le virement : il contrôle 5 abonnés par VA primé. "
                      "S'il trouve un problème, il te le dit ici.")
        jours_m = sorted({j for _, j in manquants.get(uid, [])})
        if jours_m:                                                     # 10/10 : jamais un montant sous-estimé sans le dire
            texte += ("\n\n-# Montant provisoire : " + ", ".join(j[8:10] + "/" + j[5:7] for j in jours_m[:6])
                      + (" et d'autres jours" if len(jours_m) > 6 else "") + " pas encore relevé(s) dans GAML. Gaëtan est prévenu : "
                      "le complément te sera versé dès qu'ils sont relevés.")
        try:
            await salon.send(texte)
            envoyes += 1
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Ligne de paie %s : %s", uid, erreur)
    journal.info("Paie du %s annoncée : liste au salon admin, %s ligne(s) en salon perso", maintenant.strftime("%d/%m"), envoyes)


COMPLEMENT_JOURS = int(os.environ.get("CLICS_COMPLEMENT_JOURS", "3") or 3)   # complément d'une paie provisoire au plus tard à J+3


def memoriser_annonce(d: dict, cle: str, rangs: list, manquants: dict, debut: date, fin: date, jour_paie: str, maintenant) -> bool:
    """10/10 (revue CLICS, reprise de la 3e passe : `!paie-clics`, que le message de paie demandait de lancer, réécrivait la feuille
    « Paie du … » et `paies` avec le recompte : le montant viré n'était plus écrit nulle part, le complément était à calculer à la main)
    : `paies_annoncees[cle]` = ce que la paie automatique a annoncé (et que Gaëtan a viré), posé UNE fois, jamais réécrit : {jour_paie,
    debut, fin, t, total, clippers: {uid: {montant, payes, manquants, attendus}}} (`total` et `montant` primes de parrainage comprises,
    comme la liste). 11/10 (contre-vérification CLICS, passe 3) : `attendus` = les [lien, jour] manquants (`manquants` : les jours seuls,
    pour lire) — le complément juge chaque jour attendu sur SON lien. Renvoie True si posé maintenant. Écrit `d`."""
    annonces = d.setdefault("paies_annoncees", {})
    if cle in annonces:
        return False

    def fiche(paires) -> dict:
        return {"manquants": sorted({j for _, j in paires}), "attendus": sorted({(str(l), j) for l, j in paires})}
    p_eq = getattr(rangs, "primes_equipe", None) or {}                  # lot L11 : la prime d'équipe annoncée, à part (complément)
    clippers = {uid: {"montant": round(float(montant), 2), "payes": int(payes), **fiche((manquants or {}).get(uid, [])),
                      **({"prime_equipe": round(float(p_eq[uid][0]), 2)} if uid in p_eq and p_eq[uid][0] >= 0.01 else {})}
                for _, uid, payes, _, montant, _ in rangs}
    for uid, paires in (manquants or {}).items():                       # un clipper à 0 sur la liste, dont tous les jours manquent
        clippers.setdefault(str(uid), {"montant": 0.0, "payes": 0, **fiche(paires)})
    annonces[cle] = {"jour_paie": jour_paie, "debut": debut.isoformat(), "fin": fin.isoformat(), "t": _horodatage(maintenant),
                     "total": round(sum(float(r[4]) for r in rangs), 2), "clippers": clippers}
    if _deps.get("ecrire_json"):
        _ecrire(d)
    return True


COMPLEMENT_RECUL = 46   # un jour de plus de 46 jours n'est plus relu par rattraper (45 jours de recul d'un lien payé, depuis la veille)


def _paire(x) -> tuple:
    """(lien, « AAAA-MM-JJ ») d'un jour attendu ; un jour seul (forme d'avant le 11/10) → ("", jour)."""
    if isinstance(x, (list, tuple)) and len(x) == 2:
        return str(x[0] or ""), str(x[1])
    return "", str(x)


def _attendus(d: dict, cle: str, a: dict) -> dict:
    """{uid: [(lien, « AAAA-MM-JJ »)]} encore attendus pour la paie `cle` : avant le premier complément, les jours manquants à
    l'annonce ; après, ceux qui manquaient encore au dernier complément (`paies_complements[cle]["restants"]`). 11/10 (contre-
    vérification CLICS, passe 3 : avec deux liens dont un seul relevé, ou un 404 passager, le complément jugeait au grain (clipper,
    jour) et partait faux ou jamais) : au grain (lien, jour)."""
    fait = (d.get("paies_complements") or {}).get(cle)
    if fait is None:
        src = {str(uid): (c.get("attendus") or c.get("manquants")) for uid, c in (((a or {}).get("clippers")) or {}).items()
               if isinstance(c, dict)}
    else:
        src = fait.get("restants") or {}
    out = {}
    for uid, xs in src.items():
        paires = sorted({_paire(x) for x in xs or []})
        if paires:
            out[str(uid)] = paires
    return out


def _attendu_lu(d: dict, lid: str, jour_iso: str, manquants_uid=()) -> bool:
    """11/10 : un jour attendu est-il relevé ? Présent dans les jours de SON lien, et pas une veille encore provisoire (pas relue
    après RELECTURE_HEURE). Un lien introuvable ou effacé n'a rien relevé. Forme d'avant le 11/10 (sans lien) : le jour n'est plus
    dans les jours manquants du clipper (`manquants_uid`)."""
    if not lid:
        return jour_iso not in manquants_uid
    j = _en_date(jour_iso)
    return (j is not None and not _manque((d.get("jours") or {}).get(lid) or {}, j)
            and jour_iso not in ((d.get("provisoires") or {}).get(lid) or ()))


def _peut_arriver(d: dict, lid: str) -> bool:
    """11/10 : un jour attendu de ce lien peut-il encore être relevé ? Seulement sur un lien que rattraper relève (a_relever) : jamais
    sur un lien effacé de GAML (`supprime_gaml`, tant qu'il ne revient pas dans /links), éteint sans clipper, ou inconnu du bot. Un
    lien introuvable aujourd'hui (404) est retenté demain : il peut encore arriver."""
    if not lid:
        return True
    info = (d.get("liens") or {}).get(lid)
    return info is not None and a_relever(info)


def complement_en_attente(d: dict, cle: str, a: dict = None, aujourdhui: date = None) -> bool:
    """10/10 (reprise CLICS, 4e tour) : un complément de la paie `cle` est-il encore à poster tout seul ? Le premier, tant qu'il n'est
    pas parti (au plus tard à J+COMPLEMENT_JOURS) ; les suivants, tant qu'un jour encore attendu peut être relu (COMPLEMENT_RECUL jours :
    au-delà, rattraper ne le relit plus ; 11/10 : jamais sur un lien effacé de GAML, _peut_arriver)."""
    a = a if a is not None else (d.get("paies_annoncees") or {}).get(cle)
    attendus = _attendus(d, cle, a)
    if not attendus:
        return False
    if cle not in (d.get("paies_complements") or {}):
        return True
    limite = (aujourdhui or _aujourdhui()) - timedelta(days=COMPLEMENT_RECUL)
    return any((_en_date(j) or date.min) >= limite and _peut_arriver(d, lid) for paires in attendus.values() for lid, j in paires)


async def completer_paies(d: dict, maintenant) -> int:
    """10/10 (revue CLICS, reprise de la 3e passe : une paie partie « provisoire » à midi ne se refermait jamais — rien ne prévenait
    quand le jour manquant arrivait, le complément de Tom restait à calculer à la main ou était oublié) : pour chaque paie annoncée
    avec des jours manquants (`paies_annoncees`), dès que la période n'a plus de jour manquant (jours_manquants_paie), ou au plus tard
    COMPLEMENT_JOURS jours après la paie avec ce qui reste : UN message au salon admin « Complément de la paie du 20/10 : Tom +10
    visites = +0,50 $ → 0x… » (ou « rien à compléter »), l'onglet « Complément du JJ/MM/AAAA » (les différences seulement) et la ligne
    du clipper dans son salon perso. Mémorisé dans `paies_complements` (`paies_annoncees` n'est pas touché).
    10/10 (reprise CLICS, 4e tour : le 12/10 de Tom relevé APRÈS le complément de J+3 — « rien à compléter » — n'était plus jamais
    posté, et `!paie-clics` disait « complément déjà posté » pour 0,50 $ jamais versés) : les jours encore manquants au complément
    restent attendus (`restants`) ; dès que l'un d'eux est relevé (tant qu'il peut l'être : COMPLEMENT_RECUL jours), un complément
    suivant (« Complément n° 2 … », onglet « Complément 2 du … ») porte la différence avec tout ce qui a déjà été versé (annonce +
    compléments postés, cumulés dans `paies_complements[cle]["clippers"]`). Un complément suivant sans rien à verser ne dit rien.
    11/10 (contre-vérification CLICS, passe 3) : les jours attendus et `restants` sont gardés au grain (lien, jour) ; un jour attendu
    n'est « relevé » que présent dans les jours de son lien et relu après RELECTURE_HEURE (_attendu_lu), jamais parce qu'il sort de
    jours_manquants_paie (lien en 404). Renvoie le nombre de compléments postés. Écrit `d`."""
    annonces = d.get("paies_annoncees") or {}
    faits = d.setdefault("paies_complements", {})
    aujourdhui = maintenant.date()
    postes = 0
    for cle, a in sorted(annonces.items()):
        if not complement_en_attente(d, cle, a, aujourdhui):
            continue
        clippers = (a or {}).get("clippers") or {}
        debut, fin, jour_p = _en_date(a.get("debut")), _en_date(a.get("fin")), _en_date(cle)
        if debut is None or fin is None or jour_p is None:
            continue
        fait = faits.get(cle)
        attendus = _attendus(d, cle, a)
        restants = jours_manquants_paie(d, debut, fin, avec_provisoires=True)
        # 11/10 (contre-vérification CLICS, passe 3) : chaque jour attendu est jugé sur SON lien (_attendu_lu) — avant, un jour sorti
        # de jours_manquants_paie passait pour relevé (lien en 404 passager : « Tom (12/10) relevé, rien à compléter », puis le vrai
        # relevé jamais posté) et un jour relevé sur un lien sur deux ne déclenchait rien. `reste` = les attendus pas encore relevés
        # et les jours manquants de la période, au grain (lien, jour).
        releves, reste = {}, {}
        for uid, paires in attendus.items():
            manq_uid = {j for _, j in restants.get(uid, [])}
            for lid, j in paires:
                if _attendu_lu(d, lid, j, manq_uid):
                    releves.setdefault(uid, []).append(j)
                else:
                    reste.setdefault(uid, set()).add((lid, j))
        for uid, paires in restants.items():
            deja = reste.setdefault(uid, set())
            deja.update(p for p in paires if ("", p[1]) not in deja)    # (un jour d'avant le 11/10, sans lien, déjà compté)
        reste = {uid: sorted(ps, key=lambda p: (p[1], p[0])) for uid, ps in reste.items() if ps}
        if fait is None:
            limite = jour_p + timedelta(days=COMPLEMENT_JOURS)
            if reste and (aujourdhui < limite or (aujourdhui == limite and maintenant.hour < CLICS_HEURE)):
                continue                                                # on attend encore les jours manquants
        elif not releves:
            continue                                                    # aucun jour attendu relevé depuis le dernier complément
        n = int((fait or {}).get("n") or (1 if fait else 0)) + 1
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None)        # noqa: E731
                              or str((registre.get(uid) or {}).get("prenom") or "").title() or f"id {uid}")
        jour_paie = str(a.get("jour_paie") or jour_p.strftime("%d/%m"))
        _, _, rangs = liste_paie(d, nom_de, debut, fin, jour_paie, manquants=restants)
        recompte = {uid: (payes, montant, w, nom) for nom, uid, payes, _, montant, w in rangs}
        # Lot L11 : une prime d'équipe provisoire à l'annonce (jour non relevé chez un VA) est figée juste au recompte : l'écart de
        # prime part dans le complément, dit à part (« +10 $ de prime d'équipe »), et cumulé dans `prime_equipe`
        p_now = {str(u): float(x[0]) for u, x in (getattr(rangs, "primes_equipe", None) or {}).items()}
        eq_plus = {}
        verses = _versements(d, cle) or {}
        cumul = {str(u): dict(c) for u, c in ((fait or {}).get("clippers") or {}).items() if isinstance(c, dict)}
        plus, moins = [], []
        for uid in sorted(set(verses) | set(recompte), key=lambda u: -(recompte.get(u, (0, 0.0))[1])):
            p1, m1, w, nom = recompte.get(uid, (0, 0.0, d["wallets"].get(uid, {}).get("adresse", ""), nom_de(uid)))
            verse = _deja_verse(verses, uid)[2]
            payes_verses = int((clippers.get(uid) or {}).get("payes") or 0) + int((cumul.get(uid) or {}).get("payes") or 0)
            ecart, ecart_p = round(m1 - verse, 2), int(p1) - payes_verses
            prime_versee = float((clippers.get(uid) or {}).get("prime_equipe") or 0) + float((cumul.get(uid) or {}).get("prime_equipe") or 0)
            ecart_eq = round(p_now.get(uid, 0.0) - prime_versee, 2)
            if ecart >= 0.01:
                plus.append((nom, uid, ecart_p, ecart, w, [j for _, j in attendus.get(uid) or []]))
                if abs(ecart_eq) >= 0.01:
                    eq_plus[uid] = ecart_eq
            elif ecart <= -0.01:
                moins.append((nom, ecart))
        for _, uid, ecart_p, ecart, _, _ in plus:
            c = cumul.get(uid) or {}
            cumul[uid] = {"montant": round(float(c.get("montant") or 0) + ecart, 2), "payes": int(c.get("payes") or 0) + ecart_p}
            if uid in eq_plus or c.get("prime_equipe"):
                cumul[uid]["prime_equipe"] = round(float(c.get("prime_equipe") or 0) + eq_plus.get(uid, 0.0), 2)
        restants_iso = {uid: [[lid, j] for lid, j in paires] for uid, paires in reste.items()}   # 11/10 : au grain (lien, jour)
        envoi = {"t": _horodatage(maintenant), "n": n, "clippers": {uid: {"montant": ecart, "payes": ecart_p,
                                                                          **({"prime_equipe": eq_plus[uid]} if uid in eq_plus else {})}
                                                                    for _, uid, ecart_p, ecart, _, _ in plus}}
        if n > 1 and not plus and not moins:
            # un complément suivant sans rien à verser (le jour relevé n'a aucune visite payée) : l'état suit, sans message
            faits[cle] = {**fait, "restants": restants_iso}
            _ecrire(d)
            continue
        quand = "l'annonce" if n == 1 else f"le complément du {(_en_date((fait or {}).get('t')) or jour_p).strftime('%d/%m')}"
        lignes = [f"🧾 **Complément{'' if n == 1 else f' n° {n}'} de la paie du {jour_p.strftime('%d/%m')}** (période "
                  f"{debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}) — jours relevés depuis {quand} : "
                  + (" · ".join(f"{str(nom_de(u)).split(' - ')[0]} ({_jjmm(js)})" for u, js in releves.items()) or "aucun")]
        for nom, uid, ecart_p, ecart, w, _ in plus:
            adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else (w or "⚠️ adresse manquante")
            eq = (f", {'+' if eq_plus[uid] > 0 else ''}{_usd(eq_plus[uid])} de prime d'équipe" if uid in eq_plus else "")
            lignes.append(f"· {nom} — +{_fmt(ecart_p)} visites{eq} → **+{_usd(ecart)}** → {adr}")
        if plus:
            lignes.append(f"**Total du complément : {_usd(sum(p[3] for p in plus))}** · {len(plus)} clipper(s) — à virer à la main, en "
                          f"plus de la liste du {jour_p.strftime('%d/%m')}" + (" (déjà virée)." if n == 1 else " et des compléments déjà postés."))
        else:
            lignes.append("✅ Rien à compléter : les jours relevés n'ajoutent aucune visite payée.")
        if moins:
            lignes.append("⚠️ Recompte plus bas que ce qui a été versé (rien à reprendre, à vérifier) : "
                          + " · ".join(f"{str(nm).split(' - ')[0]} {_usd(e)}" for nm, e in moins))
        # lot L11 : des primes d'équipe figées au délai avec des jours non relevés ne bougent plus ; un de ces jours arrive → dit
        fige_eq = (d.get("primes_equipes") or {}).get(cle) or {}
        tard = sorted(set(map(str, fige_eq.get("jours_non_releves") or [])) & set(releves)) if isinstance(fige_eq, dict) else []
        if tard:
            lignes.append(f"⚠️ Primes d'équipe figées le {(_en_date(fige_eq.get('fige_le')) or jour_p).strftime('%d/%m')} avec des jours "
                          f"non relevés, relevés depuis : {', '.join(str(nom_de(u)).split(' - ')[0] for u in tard)}. Elles ne changent "
                          f"plus toutes seules : compare avec `!tl liste {jour_p.day} {jour_p.strftime('%Y-%m')}` et ajuste à la main.")
        if reste:
            jusqu = max((_en_date(j) or fin for ps in reste.values() for _, j in ps), default=fin) + timedelta(days=COMPLEMENT_RECUL)
            # 11/10 : un jour attendu sur un lien introuvable (404 aujourd'hui), effacé de GAML ou plus relevé n'est jamais dit « relevé »
            sans_lien = {lid for ps in reste.values() for lid, _ in ps
                         if lid and (not _peut_arriver(d, lid) or str(((d.get("liens") or {}).get(lid) or {}).get("introuvable") or "")
                                     == aujourdhui.isoformat())}
            # une veille lue la nuit et pas encore relue (`provisoires`) compte sa lecture de la nuit, pas 0
            nuit = any(not _manque((d.get("jours") or {}).get(lid) or {}, _en_date(j) or fin) for ps in reste.values() for lid, j in ps if lid)
            lignes.append("⚠️ Toujours pas relevés" + (f" {COMPLEMENT_JOURS} jours après la paie" if n == 1 else "")
                          + (", comptés 0 (ou à leur lecture de la nuit, pas encore relue)" if nuit else ", comptés 0")
                          + f" : {texte_manquants(reste, nom_de)} — relevés retentés toutes les 30 min"
                          + (f" (dont {len(sans_lien)} lien(s) introuvable(s) dans GAML ou plus relevé(s) : relu(s) seulement s'il(s) revien(nen)t)"
                             if sans_lien else "")
                          + f" ; s'ils arrivent (jusqu'au {jusqu.strftime('%d/%m')}), le complément suivant est posté ici tout seul.")
        if plus:
            titre = await ecrire_feuille_complement(d, plus, debut, fin, jour_paie, n, primes=eq_plus)
            if titre:
                lignes.append(f"📗 Onglet « {titre} » écrit dans le tableur « {ADRESSES_TABLEUR} » (les compléments seulement). "
                              f"La feuille « {ONGLET_PAIE_PREFIXE}{_date_paie(jour_paie, fin)} » reste celle du virement.")
        # mémorisé AVANT d'envoyer : jamais deux messages pour le même complément ; `clippers` = les compléments postés, cumulés
        faits[cle] = {"t": envoi["t"], "n": n, "clippers": cumul, "restants": restants_iso,
                      "envois": list((fait or {}).get("envois") or []) + [envoi]}
        _ecrire(d)
        canal = await _deps["canal_admin"]()
        if canal is not None:
            try:
                await _envoyer_blocs(canal.send, lignes)
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Complément de paie (admin) : %s", erreur)
        for nom, uid, ecart_p, ecart, w, _ in plus:
            avec_eq = eq_plus.get(uid, 0.0) >= 0.01                     # lot L11 : un TL au fixe ou un manager reçoit sa prime aussi
            salon = (_deps["salon_perso"](uid) if (regime(uid) == "clic" or avec_eq) and _deps.get("salon_perso") else None)
            if salon is None:
                continue
            adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else w
            corps = (f"**+{_fmt(ecart_p)} visites = +{_usd(ecart)}**" if not avec_eq else
                     f"**+{_usd(ecart)}**, dont +{_usd(eq_plus[uid])} de prime d'équipe" + (f" et +{_fmt(ecart_p)} visites" if ecart_p > 0 else ""))
            try:
                await salon.send(f"💸 **Complément de ta paie du {jour_p.strftime('%d/%m')}** : les jours qui manquaient sont relevés, "
                                 + corps
                                 + (f" → virement vers {adr}." if w else " → ⚠️ pas d'adresse enregistrée : colle-la dans ton app ou `!wallet 0x…`."))
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Complément de paie %s : %s", uid, erreur)
        postes += 1
        journal.info("Complément n° %s de la paie %s : %s clipper(s), %s", n, cle, len(plus), _usd(sum(p[3] for p in plus)))
    return postes


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
                if marquer_releves(d, liens_tous):                     # 09/10 (dashboard) : tous les liens actifs relevés
                    _ecrire(d)
                await publier_regimes(d)                                 # 08/10 (revue) : l'app lit le régime du bot
                await publier_equipes(d)                                 # lot L11 : l'équipe et la prime en cours du TL, pour l'app
                try:                                                    # revue CLICS : notes Metricool refusées par GAML, retentées
                    posees = await poser_notes_attendues(liens_tous)
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Notes Metricool en attente : %s", erreur)
                    posees = []
                if posees:
                    _ecrire(d)                                          # ce qui précède (associer_auto…) d'abord, puis la relecture
                    d = _lire()                                         # (poser_notes_attendues a écrit sur une relecture)
                    lignes += ["🏷️ **Notes Metricool posées dans GAML**"] + posees
                notes = synchroniser_notes(d, liens_tous)              # 08/10 : une note changée à la main (Metricool) sort le lien
                if notes:
                    _ecrire(d)
                    lignes += ["🏷️ **Note GAML changée à la main**"] + notes
                derniere_assoc = time.time()
                if lignes:
                    _ecrire(d)
                try:                                                    # 09/10 : liens libérés renommés « Clipping libre (ex-…) »
                    renommes = await renommer_liberes(liens_tous)
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Renommage des liens libérés : %s", erreur)
                    renommes = []
                if renommes:
                    d = _lire()                                         # écrit sur une relecture (d déjà écrit juste au-dessus)
                    lignes += ["🏷️ **Liens libérés renommés** (plus jamais donnés à un homonyme)"] + renommes
                if lignes:
                    canal = await _deps["canal_admin"]()
                    if canal:
                        await canal.send("🔗 **Liens GAML attribués automatiquement**\n" + "\n".join(lignes)[:1800])
            appels = await rattraper(d)
            if appels:
                journal.info("Relevés GAML : %s appels ce passage", appels)
            maintenant = _deps["heure_paris"]()
            aujourdhui = maintenant.date().isoformat()
            hier_iso = (maintenant.date() - timedelta(days=1)).isoformat()
            # 09/10 (dashboard) : une erreur n'écrit plus de 0, donc un lien introuvable aujourd'hui (404) ou attribué aujourd'hui
            # (rien à relever pour hier) ne bloque plus la ligne du matin, le classement ni l'annonce de paie
            complets = all(not _manque(d["jours"].get(lid, {}), maintenant.date() - timedelta(days=1))
                           for lid, i in d["liens"].items()
                           if i.get("uid") and a_relever(i, aujourdhui) and str(i.get("depuis") or "")[:10] <= hier_iso)
            if maintenant.hour >= CLICS_HEURE and d.get("adresses_sync") != aujourdhui:   # 08/10 : les adresses de l'app, chaque matin
                reprises = await synchroniser_adresses(d)
                d["adresses_sync"] = aujourdhui
                _ecrire(d)
                if reprises:
                    canal_a = await _deps["canal_admin"]()
                    if canal_a is not None:
                        try:
                            await canal_a.send(("📒 **Adresses USDC reprises de l'app**\n" + "\n".join(reprises))[:1900])
                        except (discord.Forbidden, discord.HTTPException) as erreur:
                            journal.warning("Adresses USDC (admin) : %s", erreur)
            if maintenant.hour >= CLICS_HEURE and (d.get("menage") != aujourdhui or d.get("menage_v") != MENAGE_VERSION):
                d["menage"], d["menage_v"] = aujourdhui, MENAGE_VERSION     # 08/10 : les liens libérés sans visites (v2 : + orphelins)
                _ecrire(d)                                              # une fois par jour, même si GAML échoue en route
                try:
                    orphelins = await rattraper_orphelins(d, await liens_gaml())
                except RuntimeError as erreur:
                    journal.warning("Orphelins GAML : %s", erreur)
                    orphelins = []
                faits = await menage_liens(d)
                d = _lire()                                             # 08/10 (revue) : les deux ont écrit sur une relecture
                if orphelins:
                    faits = ["**Liens de clippers partis, rattrapés**"] + orphelins + (["**Désactivés**"] + faits if faits else [])
                if faits:
                    canal_m = await _deps["canal_admin"]()
                    if canal_m is not None:
                        try:
                            await canal_m.send(("🧹 **Ménage GAML** (liens de clippers partis, moins de "
                                                f"{MENAGE_SEUIL} visiteurs en 7 jours ; réactivés tout seuls pour le suivant)\n"
                                                + "\n".join(faits))[:1900])
                        except (discord.Forbidden, discord.HTTPException) as erreur:
                            journal.warning("Ménage GAML (admin) : %s", erreur)
            if maintenant.hour >= CLICS_HEURE and d.get("matin") != aujourdhui and complets:
                # 05/10 (Gaëtan : « arrêter de polluer chaque salon privé ») : plus de ligne de visites quotidienne dans les
                # salons persos (CLICS_LIGNE_MATIN=1 pour la rallumer) ; `!mesclics` et la paie des 5 et 20 restent.
                n = await envoyer_lignes_matin(d) if LIGNE_MATIN else 0
                d["matin"] = aujourdhui
                _ecrire(d)
                journal.info("Lignes du matin : %s", n if LIGNE_MATIN else "éteintes (CLICS_LIGNE_MATIN=0)")
            if (maintenant.weekday() == 0 and maintenant.hour >= CLICS_HEURE and d.get("classement") != aujourdhui and complets
                    and _deps.get("canal_dopamine")):                   # 28/09 (GO n° 7) : le classement du lundi dans #dopamine
                try:
                    canal_c = await _deps["canal_dopamine"]()
                    prenom_c = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None) or f"id {uid}").split(" - ")[0]   # noqa: E731
                    try:                                        # 18/10 (action 28) : le classement par équipe TL
                        import equipes_tl
                        va_tl = equipes_tl.tl_par_va()
                    except Exception:                           # noqa: BLE001
                        va_tl = {}
                    texte_c = texte_classement(d, prenom_c, maintenant.date() - timedelta(days=1),
                                               equipe_de=(lambda uid: prenom_c(va_tl[uid]) if uid in va_tl else None) if va_tl else None)
                    if canal_c is not None and texte_c:
                        await canal_c.send(texte_c[:1990])
                    if texte_c and _deps.get("apres_classement"):       # 29/09 (GO axe 8) : le lien de parrainage aux cinq premiers
                        await _deps["apres_classement"](top_uids(d, maintenant.date() - timedelta(days=1)))
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Classement du lundi : %s", erreur)
                d["classement"] = aujourdhui
                _ecrire(d)
            if maintenant.day in (5, 20) and maintenant.hour >= CLICS_HEURE and d.get("paie_annoncee") != aujourdhui:
                # 10/10 (revue CLICS, 3e passe : ce qui restait de R3 côté paie) : la paie attend TOUS les jours de la période de
                # chaque clipper au clic, pas seulement la veille (avant : un jour ancien jamais relevé comptait 0 sans un mot), et
                # jamais au-delà de PAIE_ATTENTE_HEURE (avant : une veille jamais relevée — /analytics/visitors en délai dépassé sur
                # un lien payé — bloquait la paie toute la journée, et le lendemain n'était plus un jour de paie : pas de paie du
                # tout, sans un mot). Passé l'heure, elle part avec ces jours signalés (annoncer_paie).
                debut_p, fin_p = periode("5" if maintenant.day == 5 else "20", maintenant.strftime("%Y-%m"))
                manquants = jours_manquants_paie(d, debut_p, fin_p, avec_provisoires=True)   # 11/10 : une veille pas encore relue aussi
                if not manquants or maintenant.hour >= PAIE_ATTENTE_HEURE:
                    await annoncer_paie(client, d, maintenant, manquants)
                    d["paie_annoncee"] = aujourdhui
                    _ecrire(d)
                elif d.get("paie_attente") != aujourdhui:
                    d["paie_attente"] = aujourdhui                      # l'attente dite une fois par jour de paie
                    _ecrire(d)
                    registre_p = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
                    nom_p = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None)   # noqa: E731
                                         or str((registre_p.get(uid) or {}).get("prenom") or "").title() or f"id {uid}")
                    canal_p = await _deps["canal_admin"]()
                    if canal_p is not None:
                        try:
                            await canal_p.send((f"⏳ **Paie du {maintenant.strftime('%d/%m')} en attente** : des jours de la période ne "
                                                f"sont pas encore relevés dans GAML — {texte_manquants(manquants, nom_p)}. Relevés "
                                                f"retentés toutes les 30 min ; la paie part à {PAIE_ATTENTE_HEURE} h au plus tard, "
                                                "ces jours signalés.")[:1900])
                        except (discord.Forbidden, discord.HTTPException) as erreur:
                            journal.warning("Paie en attente (admin) : %s", erreur)
            # 10/10 (revue CLICS, reprise de la 3e passe) : une paie partie « provisoire » se referme toute seule — complément posté
            # dès que ses jours manquants sont relevés (au plus tard COMPLEMENT_JOURS jours après) ; 4e tour : un jour relevé après ce
            # complément en déclenche un suivant (tant qu'il peut l'être, COMPLEMENT_RECUL jours)
            if any(complement_en_attente(d, cle, a, maintenant.date()) for cle, a in (d.get("paies_annoncees") or {}).items()):
                try:
                    await completer_paies(d, maintenant)
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Complément de paie : %s", erreur)
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
            journal.info("État clics : %s liens attribués, %s suivis, %s relevés en tout, relevés d'hier %s, matin %s, rapport %s",
                         sum(1 for i in d["liens"].values() if i.get("uid")), sum(1 for i in d["liens"].values() if i.get("suivi")),
                         sum(1 for i in d["liens"].values() if a_relever(i, aujourdhui)),
                         "complets" if complets else "en cours", d.get("matin", "-"), d.get("rapport_jonas", "-"))
            # 09/10 (dashboard, contrat C2) : les clics de la journée en cours, toutes les 15 minutes, en fin de passage (jamais
            # avant la paie ni le rapport) ; sautés quand le rattrapage vient de prendre la minute (minuit, relecture de 6 h)
            if appels < DIRECT_SI_RATTRAPAGE:
                try:
                    n_direct = await rafraichir_aujourdhui(d)
                    if n_direct:
                        journal.info("Clics du jour : %s lien(s) relu(s)", n_direct)
                except Exception as erreur:                         # noqa: BLE001
                    journal.warning("Clics du jour : %s", erreur)
        except Exception as erreur:                                  # la boucle ne meurt jamais
            journal.warning("Boucle clics : %s", erreur)
        await asyncio.sleep(900)


# ------------------------------------------------------------------ commandes
_adresses_classeur = {"id": "", "expire": 0.0}


def _cle_prenom(t: str) -> str:
    """La clé de l'app : prénom sans accents, en minuscules (même règle que `normaliser` côté Next)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if not unicodedata.combining(c)).lower().strip()


def _date_app_vers_utc(brut: str) -> str:
    """« 2026-10-08 14:03:21 » (heure de Paris) → ISO UTC ; '' si illisible."""
    try:
        from zoneinfo import ZoneInfo
        d = datetime.strptime(str(brut).strip()[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(FUSEAU))
        return d.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        return ""


ONGLET_REGIMES = os.environ.get("REGIMES_ONGLET", "Régime paie").strip() or "Régime paie"
_regimes = {"onglet": "", "sig": ""}


async def _classeur_usage() -> str:
    """L'id du tableur « App clippers · usage » (cache 6 h), '' s'il est introuvable."""
    if _adresses_classeur["id"] and _adresses_classeur["expire"] > time.time():
        return _adresses_classeur["id"]
    classeur = ADRESSES_CLASSEUR_ID or await google_api.drive_chercher(ADRESSES_TABLEUR, "application/vnd.google-apps.spreadsheet")
    if classeur:
        _adresses_classeur.update({"id": classeur, "expire": time.time() + 6 * 3600})
    return classeur or ""


def lignes_regimes(d: dict) -> list:
    """08/10 (revue : l'app devinait « fixe » et « ancien » autrement que le bot, et affichait des montants que le bot ne paierait
    pas) : une ligne par clé de clipper (prénom de la note « Clipping Prénom », la clé de l'app) — régime, premier jour payé au
    clic (debut_clic), et le premier jour compté de chaque lien (`depuis` : un lien repris compte pour lui à partir de la reprise)."""
    par_cle = {}
    for lid, info in d.get("liens", {}).items():
        uid = str(info.get("uid") or "")
        cle = _cle_prenom(_prenom_note(info.get("note")))
        if not uid or not cle:
            continue
        par_cle.setdefault(cle, {}).setdefault(uid, []).append((lid, str(info.get("depuis") or "")[:10]))
    out = []
    for cle, par_uid in sorted(par_cle.items()):
        uid, liens = max(par_uid.items(), key=lambda x: len(x[1]))       # deux homonymes : celui qui a le plus de liens
        out.append([cle, regime(uid), debut_clic(uid, d), ";".join(f"{lid}:{dep}" for lid, dep in sorted(liens) if dep)])
    return out


async def publier_regimes(d: dict) -> int:
    """Écrit l'onglet « Régime paie » du tableur de l'app, seulement s'il a changé. Renvoie le nombre de lignes écrites (0 sinon).
    Jamais d'exception : l'app retombe sur sa règle de repli si l'onglet manque."""
    if not google_api.actif():
        return 0
    try:
        lignes = lignes_regimes(d)
        sig = json.dumps(lignes, ensure_ascii=False)
        if sig == _regimes["sig"]:
            return 0
        classeur = await _classeur_usage()
        if not classeur:
            return 0
        if _regimes["onglet"] != classeur:
            await google_api.sheets_creer_onglet(classeur, ONGLET_REGIMES)
            _regimes["onglet"] = classeur
        await google_api.sheets_effacer(classeur, f"{ONGLET_REGIMES}!A1:E")
        await google_api.sheets_ecrire(classeur, f"{ONGLET_REGIMES}!A1:D{len(lignes) + 1}",
                                       [["Clé", "Régime", "Clic depuis", "Liens (id:premier jour)"]] + lignes)
        _regimes["sig"] = sig
        journal.info("Régime paie publié pour l'app : %d clipper(s)", len(lignes))
        return len(lignes)
    except Exception as erreur:                                        # noqa: BLE001
        journal.warning("Régime paie (app) : %s", str(erreur)[:160])
        return 0


ONGLET_EQUIPES = os.environ.get("EQUIPES_ONGLET", "Équipes").strip() or "Équipes"
_equipes_pub = {"onglet": "", "sig": ""}
ENTETE_EQUIPES = ["Discord", "Clé app", "Ligne", "Créatrice", "Début", "Fin", "Prénom", "Visites payées", "Seuil", "Atteint",
                  "Prime en cours ($)", "Primée", "Jours non relevés"]


def _cles_app(d: dict) -> dict:
    """{uid : clé de l'app} (le prénom de la note « Clipping Prénom », la clé de lignes_regimes et de l'app), pour le seul uid qui la
    porte dans l'app : deux homonymes, celui qui a le plus de liens (même règle que lignes_regimes)."""
    par_cle = {}
    for info in (d.get("liens") or {}).values():
        uid = str(info.get("uid") or "")
        cle = _cle_prenom(_prenom_note(info.get("note")))
        if uid and cle:
            par_cle.setdefault(cle, {}).setdefault(uid, 0)
            par_cle[cle][uid] += 1
    return {max(par_uid.items(), key=lambda x: x[1])[0]: cle for cle, par_uid in par_cle.items()}


def _seuils_equipes() -> tuple:
    """(seuil VA, seuil équipe) de la grille (equipes_tl, variables Railway) ; (500, 3000) si le module manque."""
    try:
        import equipes_tl
        return int(equipes_tl.TL_SEUIL_VA), int(equipes_tl.MANAGER_SEUIL_EQUIPE)
    except Exception:                                                   # noqa: BLE001
        return 500, 3000


def _texte(x) -> str:
    """Une valeur gardée telle quelle par le tableur (écrit en USER_ENTERED) : un uid Discord de 18 ou 19 chiffres n'y devient jamais
    un nombre arrondi (« 1,23E+18 »), ni « 2/6 » une date, ni « 2026-10-20 » un jour reformaté. L'apostrophe n'est pas relue."""
    s = str(x if x is not None else "")
    return "'" + s if s else ""


def _sans_formule(x) -> str:
    """Un prénom qui commence par « = », « + », « - » ou « @ » n'est jamais lu comme une formule (même règle que les candidatures)."""
    s = str(x or "")
    return "'" + s if s[:1] in ("+", "=", "-", "@") else s


def lignes_equipes(d: dict, debut: date, fin: date) -> list:
    """Lot L11 : l'onglet « Équipes » du tableur de l'app, pour la période en cours. Une ligne par TL (total d'équipe, VA au seuil
    « 2/6 »), une par VA de son équipe (visites payées, ✓ à 500), une par équipe managée (total, ✓ à 3 000), et une « Prime » par
    bénéficiaire (la prime en cours, TL et manager réunis, telle que la liste de paie la porterait aujourd'hui). Indexé par l'uid
    Discord du TL ou du manager, avec sa clé de l'app (vide sans lien : il n'a pas d'app). Jamais d'adresse USDC ni de jeton.
    Les chiffres viennent de `calcul_equipes` (equipes_tl.calculer, avec paie_clics.payees) : la même mesure que la paie.
    Reprise L11 (R5) : la colonne « Jours non relevés » (vide à 0) dit au TL qu'une somme est partielle (VA : ses jours ; TL et
    Manager : ceux de l'équipe), comme la liste de paie et `!tl liste`."""
    calcul = _dep_equipes("calcul_equipes")(d, debut, fin)
    primes = {}
    if _deps.get("primes_equipes"):
        for x in _deps["primes_equipes"](d, debut, fin, _cle_iso("", fin)) or []:
            primes[str(x[0])] = round(primes.get(str(x[0]), 0.0) + float(x[1] or 0), 2)
    cles = _cles_app(d)
    s_va, s_eq = _seuils_equipes()
    primee = "oui" if (calcul or {}).get("primee") else "non"
    a, b = _texte(debut.isoformat()), _texte(fin.isoformat())
    out, beneficiaires = [], {}
    tl_compte = bool(getattr(_equipes_tl(), "EQUIPE_COMPTE_TL", False))
    jours = lambda n: int(n) if int(n or 0) > 0 else ""                 # noqa: E731 — vide à 0 : rien à signaler
    for c, e in sorted(((calcul or {}).get("equipes") or {}).items()):
        tl, m = str(e.get("tl") or ""), str(e.get("manager") or "")
        vas = e.get("vas") or []
        manq_eq = sum(int(v.get("manquants") or 0) for v in vas if not v.get("hors_total")) + (
            int(e.get("tl_manquants") or 0) if tl_compte else 0)
        if tl:
            beneficiaires.setdefault(tl, e.get("tl_nom") or "")
            out.append([_texte(tl), cles.get(tl, ""), "TL", c, a, b, _sans_formule(e.get("tl_nom")), int(e.get("total") or 0), s_va,
                        _texte(f"{int(e.get('va_primes') or 0)}/{len(vas)}"), "", primee, jours(manq_eq)])
            for v in vas:
                out.append([_texte(tl), cles.get(tl, ""), "VA", c, a, b, _sans_formule(v.get("nom")),
                            "" if v.get("erreur") else int(v.get("payees") or 0), s_va, "✓" if v.get("prime") else "", "", primee,
                            jours(v.get("manquants"))])
        if m and tl and m != tl:
            beneficiaires.setdefault(m, e.get("manager_nom") or "")
            out.append([_texte(m), cles.get(m, ""), "Manager", c, a, b, _sans_formule(e.get("manager_nom")), int(e.get("total") or 0),
                        s_eq, "✓" if int(e.get("total") or 0) >= s_eq else "", "", primee, jours(manq_eq)])
    for uid, nom in sorted(beneficiaires.items()):
        out.append([_texte(uid), cles.get(uid, ""), "Prime", "", a, b, _sans_formule(nom), "", "", "", round(primes.get(uid, 0.0), 2),
                    primee, ""])
    return out


async def publier_equipes(d: dict) -> int:
    """Lot L11 : écrit l'onglet « Équipes » du tableur « App clippers · usage » (lignes_equipes, période en cours), seulement s'il a
    changé ; l'app le lit pour montrer au TL son équipe et sa prime en cours. Renvoie le nombre de lignes écrites (0 sinon). Jamais
    d'exception ; inerte sans `calcul_equipes` (passée ou dérivée d'equipes_tl, _dep_equipes) ou sans Google."""
    if not google_api.actif() or not _dep_equipes("calcul_equipes"):
        return 0
    try:
        debut, fin = periode_en_cours()
        lignes = lignes_equipes(d, debut, fin)
        sig = json.dumps(lignes, ensure_ascii=False)
        if sig == _equipes_pub["sig"]:
            return 0
        classeur = await _classeur_usage()
        if not classeur:
            return 0
        if _equipes_pub["onglet"] != classeur:
            await google_api.sheets_creer_onglet(classeur, ONGLET_EQUIPES)
            _equipes_pub["onglet"] = classeur
        await google_api.sheets_effacer(classeur, f"{ONGLET_EQUIPES}!A1:M")
        await google_api.sheets_ecrire(classeur, f"{ONGLET_EQUIPES}!A1:M{len(lignes) + 1}", [ENTETE_EQUIPES] + lignes)
        _equipes_pub["sig"] = sig
        journal.info("Équipes publiées pour l'app : %d ligne(s)", len(lignes))
        return len(lignes)
    except Exception as erreur:                                        # noqa: BLE001
        journal.warning("Équipes (app) : %s", str(erreur)[:160])
        return 0


ONGLET_PAIE_PREFIXE = "Paie du "
ONGLET_RECOMPTE_PREFIXE = "Recompte du "                                # 10/10 : `!paie-clics` sur une paie déjà annoncée
ONGLET_COMPLEMENT_PREFIXE = "Complément du "                            # 10/10 : les jours relevés après une paie provisoire


def _date_paie(jour_paie: str, fin: date) -> str:
    """« 20/10 » (ou « 2026-10-20 ») → « 20/10/2026 » : le jour de paie dans le titre des onglets."""
    if "-" in jour_paie:
        return date.fromisoformat(jour_paie[:10]).strftime("%d/%m/%Y")
    return jour_paie if jour_paie.count("/") == 2 else f"{jour_paie}/{fin.year if fin.month != 12 or jour_paie[3:5] != '01' else fin.year + 1}"


def _creatrices_par_uid(d: dict) -> dict:
    crea_de = {}
    for info in d.get("liens", {}).values():
        uid = str(info.get("uid") or "")
        if uid and info.get("creatrice") and uid not in crea_de:
            crea_de[uid] = str(info["creatrice"]).split()[0].title()
    return crea_de


async def _ecrire_onglet(titre: str, lignes: list, jusqua: str = "") -> str:
    """Écrit `lignes` dans l'onglet `titre` du tableur « App clippers · usage » (créé au besoin, vidé d'abord). Renvoie le titre, ''
    si rien n'a pu être écrit. Jamais d'exception. `jusqua` (lot L11) : la colonne la plus large que cet onglet a pu avoir (les
    colonnes des primes d'équipe), vidée aussi quand la version écrite est plus étroite."""
    if not google_api.actif() or not lignes:
        return ""
    try:
        classeur = await _classeur_usage()
        if not classeur:
            return ""
        col = chr(ord("A") + max(len(l) for l in lignes) - 1)
        await google_api.sheets_creer_onglet(classeur, titre)
        await google_api.sheets_effacer(classeur, f"{titre}!A1:{max(col, 'J')}")   # 11/10 : « Recompte » va jusqu'à K
        if jusqua and max(col, "J") < jusqua:
            await google_api.sheets_effacer(classeur, f"{titre}!{chr(ord(max(col, 'J')) + 1)}1:{jusqua}")
        await google_api.sheets_ecrire(classeur, f"{titre}!A1:{col}{len(lignes)}", lignes)
        return titre
    except Exception as erreur:                                        # noqa: BLE001
        journal.warning("Feuille « %s » : %s", titre, str(erreur)[:160])
        return ""


async def ecrire_feuille_paie(d: dict, rangs: list, debut: date, fin: date, jour_paie: str, manquants: dict = None,
                              annonce: dict = None) -> str:
    """09/10 (Gaëtan : « prépare-moi un sheet avec les adresses USDC ERC20 et le montant des clippers à payer, avec leur prénom ») :
    un onglet « Paie du JJ/MM/AAAA » dans le tableur « App clippers · usage » (Drive agence), réécrit à chaque liste (annonce du 5 et
    du 20, `!paie-clics`) : prénom, créatrice, adresse, visites payées, montant, période, date, note (adresse manquante ou IBAN).
    10/10 (revue CLICS, reprise de la 3e passe) : `manquants` (jours_manquants_paie) → la note dit « provisoire : 12/10 non relevé(s) »
    (la feuille est le support du virement : avant, Tom y était à 7,00 $ sans un mot) ; `annonce` ({uid: {montant, complement}}, ce
    qui a déjà été versé pour cette paie, _versements) → l'onglet « Recompte du JJ/MM/AAAA » avec les colonnes « Annoncé », « Complément
    posté » et « Reste à verser » (4e tour : avant, « Complément » = recompte − annonce, un complément déjà posté y revenait), et la
    feuille « Paie du … » (celle du virement) n'est jamais réécrite. Renvoie le titre de l'onglet, '' si rien n'a pu être écrit.
    Jamais d'exception."""
    if not google_api.actif() or not rangs:
        return ""
    try:
        paie = _date_paie(jour_paie, fin)
        titre = f"{ONGLET_RECOMPTE_PREFIXE if annonce is not None else ONGLET_PAIE_PREFIXE}{paie}"
        crea_de = _creatrices_par_uid(d)
        # Lot L11 : avec des primes d'équipe, « Montant » = « Au clic » + « Parrainage » + « Prime équipe », le total à virer ; le
        # détail de la prime va dans « Note ». Sans prime d'équipe, la feuille est celle d'avant (mêmes colonnes, mêmes places).
        p_eq = getattr(rangs, "primes_equipe", None) or {}
        parr = getattr(rangs, "parrainage", None) or {}
        entete = (["Prénom", "Créatrice", "Adresse USDC (ERC-20)", "Visites payées"]
                  + (["Au clic ($)", "Parrainage ($)", "Prime équipe ($)"] if p_eq else []) + ["Montant ($)", "Période", "Payé le", "Note"])
        lignes = [entete + (["Annoncé ($)", "Complément posté ($)", "Reste à verser ($)"] if annonce is not None else [])]
        total, total_a, total_c, total_reste = 0.0, 0.0, 0.0, 0.0
        t_clic, t_parr, t_eq = 0.0, 0.0, 0.0
        for nom, uid, payes, hors, montant, w in rangs:
            total += montant
            note = "⚠️ adresse manquante" if not w else ("IBAN, pas USDC" if not str(w).startswith("0x") else "")
            jours_m = sorted({j for _, j in (manquants or {}).get(uid, [])})
            if jours_m:
                note = " · ".join(x for x in (note, f"provisoire : {_jjmm(jours_m)} non relevé(s)") if x)
            parts = []
            if p_eq:
                m_e, det_e, verif_e = p_eq.get(uid, (0.0, "", False))
                m_p = round(float(parr.get(uid) or 0), 2)
                m_c = round(float(montant) - m_p - m_e, 2)                # = visites × taux (+ visites dues), arrondi comme la liste
                t_clic += m_c; t_parr += m_p; t_eq += m_e
                parts = [m_c, m_p, round(float(m_e), 2)]
                if det_e:
                    note = " · ".join(x for x in (note, f"équipe : {det_e}") if x)
            ligne = ([str(nom).split(" - ")[0].strip(), crea_de.get(uid, ""), w or "", int(payes)] + parts
                     + [round(float(montant), 2), f"{debut.strftime('%d/%m')} → {fin.strftime('%d/%m/%Y')}", paie, note])
            if annonce is not None:
                a, c, verse = _deja_verse(annonce, uid)
                total_a += a; total_c += c
                ligne += [a, c, round(float(montant) - verse, 2)]
                total_reste += max(0.0, ligne[-1])                      # 11/10 : seuls les restes positifs sont dus
            lignes.append(ligne)
        if annonce is not None:                                         # versé, plus rien au recompte
            presents = {r[1] for r in rangs}
            for uid in annonce:
                a, c, verse = _deja_verse(annonce, uid)
                if uid not in presents and verse:
                    total_a += a; total_c += c
                    membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
                    lignes.append([str(getattr(membre, "display_name", "") or f"id {uid}").split(" - ")[0], crea_de.get(uid, ""), "", 0]
                                  + ([0.0, 0.0, 0.0] if p_eq else []) + [0.0,
                                   f"{debut.strftime('%d/%m')} → {fin.strftime('%d/%m/%Y')}", paie, "plus rien au recompte : à vérifier",
                                   a, c, -verse])
        pied = (["Total", "", "", sum(int(r[2]) for r in rangs)]
                + ([round(t_clic, 2), round(t_parr, 2), round(t_eq, 2)] if p_eq else [])
                + [round(total, 2), "", "", f"{len(rangs)} clipper(s)"])
        if annonce is not None:
            # 11/10 (contre-vérification CLICS, passe 3) : « Reste à verser » du Total = la somme des restes positifs (avant : le net,
            # un recompte plus bas chez l'un effaçait le reste dû à l'autre)
            pied += [round(total_a, 2), round(total_c, 2), round(total_reste, 2)]
        lignes.append(pied)
        titre = await _ecrire_onglet(titre, lignes, jusqua="N")        # lot L11 : jusqu'à N avec les primes d'équipe (recompte)
        if titre:
            journal.info("Feuille de paie écrite : %s (%d clipper(s))", titre, len(rangs))
        return titre
    except Exception as erreur:                                        # noqa: BLE001
        journal.warning("Feuille de paie : %s", str(erreur)[:160])
        return ""


async def ecrire_feuille_complement(d: dict, plus: list, debut: date, fin: date, jour_paie: str, n: int = 1, primes: dict = None) -> str:
    """10/10 (revue CLICS, reprise de la 3e passe) : l'onglet « Complément du JJ/MM/AAAA » — seulement les clippers dont le recompte
    dépasse ce qui a déjà été versé : prénom, créatrice, adresse, visites en plus, complément, période, paie, jours attendus. `plus` =
    [(nom, uid, visites en plus, complément, adresse, jours attendus)]. 10/10 (4e tour) : le complément n° `n` ≥ 2 va dans son propre
    onglet « Complément n du … » (le premier n'est jamais réécrit). Renvoie le titre, '' si rien n'a pu être écrit. Lot L11 :
    `primes` {uid : écart de prime d'équipe} → « dont +10 $ de prime d'équipe » dans la note."""
    if not plus:
        return ""
    paie = _date_paie(jour_paie, fin)
    crea_de = _creatrices_par_uid(d)
    lignes = [["Prénom", "Créatrice", "Adresse USDC (ERC-20)", "Visites en plus", "Complément ($)", "Période", "Paie du", "Note"]]
    for nom, uid, ecart_p, ecart, w, jours_m in plus:
        note = "⚠️ adresse manquante" if not w else ("IBAN, pas USDC" if not str(w).startswith("0x") else "")
        note = " · ".join(x for x in (note, f"jours attendus : {_jjmm(jours_m)}" if jours_m else "") if x)
        if (primes or {}).get(uid):
            note = " · ".join(x for x in (note, f"dont {'+' if primes[uid] > 0 else ''}{_usd(primes[uid])} de prime d'équipe") if x)
        lignes.append([str(nom).split(" - ")[0].strip(), crea_de.get(uid, ""), w or "", int(ecart_p), round(float(ecart), 2),
                       f"{debut.strftime('%d/%m')} → {fin.strftime('%d/%m/%Y')}", paie, note])
    lignes.append(["Total", "", "", sum(int(p[2]) for p in plus), round(sum(float(p[3]) for p in plus), 2), "", "",
                   f"{len(plus)} clipper(s), en plus de la feuille « {ONGLET_PAIE_PREFIXE}{paie} »"
                   + ("" if n <= 1 else " et des compléments précédents")])
    return await _ecrire_onglet(f"{ONGLET_COMPLEMENT_PREFIXE}{paie}" if n <= 1 else f"Complément {n} du {paie}", lignes)


async def synchroniser_adresses(d: dict) -> list:
    """Lit l'onglet « Adresses USDC » du tableur de l'app et complète `d["wallets"]`. Renvoie une ligne par adresse reprise
    (« Prénom → 0x1234…abcd »), vide si rien de neuf. Jamais d'exception : la paie ne doit pas dépendre du tableur."""
    if not google_api.actif():
        return []
    try:
        if _adresses_classeur["id"] and _adresses_classeur["expire"] > time.time():
            classeur = _adresses_classeur["id"]
        else:
            classeur = ADRESSES_CLASSEUR_ID or await google_api.drive_chercher(ADRESSES_TABLEUR, "application/vnd.google-apps.spreadsheet")
            if not classeur:
                journal.info("Adresses USDC : tableur « %s » introuvable", ADRESSES_TABLEUR)
                return []
            _adresses_classeur.update({"id": classeur, "expire": time.time() + 6 * 3600})
        lignes = await google_api.sheets_lire(classeur, f"{ADRESSES_ONGLET}!A2:E")
    except Exception as erreur:                                        # noqa: BLE001
        journal.warning("Adresses USDC : lecture impossible (%s)", str(erreur)[:160])
        return []
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    par_cle = {}
    for uid, fiche in registre.items():
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        nom = getattr(m, "display_name", "") or str((fiche or {}).get("prenom") or "")
        cle = _cle_prenom(nom.split()[0] if nom.split() else "")
        if cle:
            par_cle.setdefault(cle, []).append(str(uid))
    reprises = []
    for l in lignes:
        l = list(l) + [""] * (5 - len(l))
        cle = _cle_prenom(l[4] or l[0])
        adresse = _adresse_valide(l[2])
        if not cle or not adresse or not adresse.startswith("0x"):
            continue
        uids = par_cle.get(cle, [])
        if len(uids) != 1:
            if uids:
                journal.info("Adresses USDC : « %s » correspond à %d membres, non reprise", l[0], len(uids))
            continue
        uid = uids[0]
        # 09/10 (revue : deux Julien) : l'app range les adresses par prénom ; une adresse saisie avant la signature de ce membre est
        # celle d'un homonyme parti, jamais la sienne. Sans date et avec un homonyme sorti : on ne devine pas.
        date_brute = _date_app_vers_utc(l[3])
        signe = str((registre.get(uid) or {}).get("date") or "")[:10]
        if date_brute and signe and date_brute[:10] < signe:
            journal.info("Adresses USDC : « %s » saisie le %s, avant la signature du membre (%s) : non reprise", l[0], date_brute[:10], signe)
            continue
        if not date_brute and any(_cle_prenom(str(s.get("nom") or "").split(" - ")[0]) == cle
                                  for s in (_deps["lire_json"](_deps["FICHIER_SORTIS"], []) if _deps.get("FICHIER_SORTIS") else [])):
            continue
        date_app = date_brute or datetime.now(timezone.utc).isoformat(timespec="seconds")
        w = d["wallets"].get(uid) or {}
        if w.get("adresse") == adresse:
            continue
        if w.get("adresse") and w.get("source") != "app" and str(w.get("date", "")) >= date_app:
            continue                                                    # `!wallet` plus récent que l'app : on le garde
        d["wallets"][uid] = {"adresse": adresse, "date": date_app, "type": "usdc", "source": "app"}
        reprises.append(f"{l[0] or cle} → `{adresse[:6]}…{adresse[-4:]}`")
    if reprises:
        journal.info("Adresses USDC reprises de l'app : %d", len(reprises))
    return reprises


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
        try:
            periode = periode_mesclics(mots[1:])
            reponse = texte_clics_periode(d, uid, periode) if periode else texte_mesclics(d, uid, message.author.display_name)
        except ValueError as erreur:
            reponse = str(erreur)
        await message.reply(reponse[:1990])
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
    """Managers et admins : `!clics`, `!liens`, `!lien @clipper …`, `!wallet @clipper adresse`, `!paie-clics`, `!paie @clipper
    clic|fixe`, `!bilan-fixe [jours]`, `!adresses`. 11/10 (lot L12) : aucune commande morte ici (toutes servent la paie du 5 et du
    20 ou les fixes encore en place) ; seul le pied de `!clics` change (plus de Jonas)."""
    mots = texte.split()
    if not mots:
        return False
    cmd = mots[0].lower()
    if cmd not in ("!clics", "!liens", "!lien", "!paie-clics", "!wallet", "!paie", "!bilan-fixe", "!adresses"):
        return False
    if cmd == "!adresses":                                              # 08/10 : relire le tableur de l'app maintenant
        d = _lire()
        reprises = await synchroniser_adresses(d)
        if reprises:
            _ecrire(d)
        avec = sum(1 for i in d["liens"].values() if i.get("uid") and d["wallets"].get(str(i["uid"]), {}).get("adresse"))
        total = len({str(i.get("uid")) for i in d["liens"].values() if i.get("uid")})
        await message.reply((f"📒 {len(reprises)} adresse(s) reprise(s) de l'app" + (" : " + ", ".join(reprises)[:1200] if reprises else "")
                             + f"\n{avec} clipper(s) avec adresse sur {total} avec un lien.")[:1990])
        return True
    if cmd == "!paie":
        if not message.mentions or not mots[-1].lower() in ("clic", "fixe"):
            await message.reply("Format : `!paie @clipper clic` (payé sur la liste du 5 et du 20) ou `!paie @clipper fixe` (ancien modèle).")
            return True
        uid_c = str(message.mentions[0].id)
        avant, dc_avant = regime(uid_c), debut_clic(uid_c)              # 08/10 (revue) : AVANT de toucher la fiche
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        fiche = registre.setdefault(uid_c, {})
        fiche["paie"] = mots[-1].lower(); fiche["paie_par"] = str(message.author.id)
        fiche["paie_le"] = _aujourdhui().isoformat()                    # 08/10 : passe par-dessus la règle du 08/10
        if fiche["paie"] == "clic" and avant == "fixe":
            fiche["clic_depuis"] = fiche["paie_le"]                     # au fixe jusqu'à hier : le clic part d'aujourd'hui
        elif fiche["paie"] == "clic" and dc_avant:
            fiche["clic_depuis"] = dc_avant                             # déjà au clic par la règle : son plancher reste
        elif fiche["paie"] == "fixe":
            fiche.pop("clic_depuis", None)
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
            ref = _aujourdhui()                                         # 09/10 : la prochaine paie, 5 → 19 payé le 20, 20 → 4 payé le 5
            cle = "5" if ref.day <= 4 or ref.day >= 20 else "20"
            if ref.day >= 20:
                suivant = (ref.replace(day=1) + timedelta(days=32))
                mois = mois or suivant.strftime("%Y-%m")
        debut, fin = periode(cle, mois)
        jour_paie = f"{cle.rjust(2, '0')}/{(mois or (fin + timedelta(days=1)).strftime('%Y-%m'))[5:7]}"
        reprises = await synchroniser_adresses(d)
        if reprises:
            _ecrire(d)
        # 10/10 (revue CLICS, 3e passe) : les jours manquants comptés comme la paie automatique (jours_manquants_paie : `depuis` du
        # lien, plancher du clic, visites dues aux sortants), et la ligne de chaque clipper concerné marquée « provisoire »
        manquants = jours_manquants_paie(d, debut, fin, avec_provisoires=True)
        # 10/10 (revue CLICS, reprise de la 3e passe) : une paie déjà annoncée (et virée) n'est jamais réécrite par un recompte — ni la
        # feuille « Paie du … », ni `paies_annoncees` : le recompte va dans « Recompte du … », avec ce qui avait été annoncé et le
        # complément ; l'alerte des jours manquants en ligne 2, et la liste entière en plusieurs messages (avant : coupée à 1990
        # caractères, l'alerte et le Total disparaissaient dès 20 clippers)
        cle_p = _cle_periode(jour_paie, fin)
        annonce = (d.get("paies_annoncees") or {}).get(cle_p)
        # 10/10 (reprise CLICS, 4e tour) : le recompte se compare à TOUT ce qui a été versé (annonce + compléments postés) ; avant,
        # « Écart avec l'annonce : +0,50 $ — complément déjà posté » s'affichait aussi quand le complément de J+3 n'avait rien versé
        # (12/10 relevé après) : 0,50 $ jamais virés, ou virés deux fois quand le complément était bien parti
        verses = _versements(d, cle_p) if annonce else None
        lignes, csv_texte, rangs = liste_paie(d, nom_de, debut, fin, jour_paie, manquants=manquants, annonce=verses)
        en_tete = []
        if annonce:
            t_a = _en_date(annonce.get("t"))
            tot_a = round(float(annonce.get("total") or 0), 2)
            tot_c = round(sum(float((c or {}).get("complement") or 0) for c in verses.values()), 2)
            # 11/10 (contre-vérification CLICS, passe 3 : Tom +0,10 $ et Lia −0,10 $ donnaient « Rien de plus à verser. » — le net
            # effaçait un montant dû) : le reste à verser = la somme des restes POSITIFS par clipper ; les recomptes plus bas à part
            ecarts = {str(r[1]): round(float(r[4]) - _deja_verse(verses, r[1])[2], 2) for r in rangs}
            for uid_v in verses:
                ecarts.setdefault(str(uid_v), round(-_deja_verse(verses, uid_v)[2], 2))
            reste = round(sum(e for e in ecarts.values() if e >= 0.01), 2)
            bas = [e for e in ecarts.values() if e <= -0.01]
            auto = complement_en_attente(d, cle_p, annonce)
            if reste >= 0.01:
                suite = (f"**Reste à verser : +{_usd(reste)}** — "
                         + ("posté tout seul au salon admin dès que les jours attendus sont relevés (ne pas le virer avant)." if auto
                            else f"aucun complément automatique ne le portera : à virer à la main (onglet « {ONGLET_RECOMPTE_PREFIXE}"
                                 f"{_date_paie(jour_paie, fin)} », colonne « Reste à verser »).")
                         + (f" Recompte plus bas pour {len(bas)} clipper(s) ({_usd(round(sum(bas), 2))}) : rien à reprendre, à vérifier."
                            if bas else ""))
            elif bas:
                suite = f"Recompte plus bas que ce qui a été versé ({_usd(round(sum(bas), 2))}) : rien à reprendre, à vérifier."
            else:
                suite = "Rien de plus à verser" + (" pour l'instant : le complément suivant part tout seul si des jours attendus arrivent."
                                                   if auto else ".")
            en_tete.append(f"ℹ️ **Paie du {jour_paie} déjà annoncée** ({t_a.strftime('%d/%m') if t_a else '?'}, total {_usd(tot_a)}"
                           + (f", compléments postés : +{_usd(tot_c)}" if tot_c >= 0.01 else "")
                           + f") : ceci est un **recompte**. La feuille « {ONGLET_PAIE_PREFIXE}{_date_paie(jour_paie, fin)} » (celle du "
                           f"virement) n'est pas touchée. {suite}")
        if manquants:
            en_tete.append(f"⚠️ **Jours non relevés sur la période** (montants provisoires, relevés retentés toutes les 30 min) : "
                           f"{texte_manquants(manquants, nom_de)}.")
        lignes[1:1] = en_tete
        titre = await ecrire_feuille_paie(d, rangs, debut, fin, jour_paie, manquants=manquants, annonce=verses)
        if titre:
            lignes.append(f"📗 Feuille « {titre} » écrite dans le tableur « {ADRESSES_TABLEUR} » (prénom, adresse USDC, montant"
                          + (", annoncé, complément posté et reste à verser" if annonce else "") + ").")
        if reprises:
            lignes.append(f"📒 {len(reprises)} adresse(s) reprise(s) de l'app : " + ", ".join(reprises)[:600])
        fichier = discord.File(io.BytesIO(csv_texte.encode("utf-8-sig")),
                               filename=f"{'recompte' if annonce else 'paie'}_clics_{debut.isoformat()}_{fin.isoformat()}.csv")
        await _envoyer_blocs(message.reply, lignes, fichier)
        return True

    if cmd == "!bilan-fixe":
        jours = next((int(m) for m in mots[1:] if m.isdigit() and 1 <= int(m) <= 90), BILAN_FIXE_JOURS)
        await _deps["envoyer_long"](message, texte_bilan_fixe(d, jours))
        return True

    if cmd == "!clics":
        hier = _aujourdhui() - timedelta(days=1)
        debut, fin = periode_en_cours()
        lignes = [f"📊 **Clics par clipper** — hier {hier.strftime('%d/%m')} · 7 jours · période "
                  f"({debut.strftime('%d/%m')} → {fin.strftime('%d/%m')}) à {_usd(TAUX_CLIC)}"]
        par_uid = {}
        for lid, info in d["liens"].items():
            if info.get("uid"):
                par_uid.setdefault(str(info["uid"]), []).append(lid)
        rangs = []
        # 10/10 (revue CLICS, reprise de la 3e passe) : un jour pas encore relevé n'est plus affiché 0 (« hier non relevé ») et la
        # période dit combien de jours elle attend (les mêmes que la liste de paie : jours_manquants_paie)
        manq_p = jours_manquants_paie(d, debut, min(fin, hier))
        for uid, lids in par_uid.items():
            h = somme(d, lids, hier, hier); s7 = somme(d, lids, hier - timedelta(days=6), hier)
            q = somme(d, lids, _debut_paie(uid, debut, d), min(fin, hier))   # 08/10 (revue) : la même période que la paie
            rangs.append((nom_de(uid), h, s7, q, uid))
        rangs.sort(key=lambda r: -r[2]["payes"])
        fixes = []                                                      # 11/10 (lot L12) : le pied les nomme d'après regime()
        for nom, h, s7, q, uid in rangs:
            part = f"{s7['payes'] * 100 // s7['hors_robots']} %" if s7["hors_robots"] else "–"
            reg = regime(uid)
            if reg == "fixe":
                fixes.append(str(nom).split(" - ")[0].strip() or str(nom))   # « Caroline - Sophie » → « Caroline »
            lids = par_uid[uid]
            manque_h = non_releves(d, lids, hier, hier)
            txt_h = ("non relevé" if manque_h and not h["jours"] else
                     f"{_fmt(h['payes'])}" + (" (incomplet)" if manque_h else ""))
            n7 = _n_jours(non_releves(d, lids, hier - timedelta(days=6), hier))
            nq = (_n_jours(manq_p.get(uid)) if reg == "clic"
                  else _n_jours(non_releves(d, lids, _debut_paie(uid, debut, d), min(fin, hier))))
            lignes.append(f"· {nom} [{reg}] — hier {txt_h} · 7 j {_fmt(s7['payes'])} ({part} payables, {_fmt(s7['payes'] / 7)}/j"
                          + (f" ; {_jours_non_lus(n7, True)}" if n7 else "")
                          + f") · période {_fmt(q['payes'])} = {_usd(q['payes'] * TAUX_CLIC)}"
                          + (f" ({_jours_non_lus(nq, True)})" if nq else "")
                          + ("" if reg != "clic" or uid in d["wallets"] else " · ⚠️ sans adresse"))
        # 11/10 (revue du recrutement, lot L12) : plus « et Jonas, manager » (parti le 09/10) ; les fixes sont ceux de la liste
        # ci-dessus d'après regime() (la liste écrite en dur mentait dès qu'un fixe passait au clic), et les primes d'équipe des TL et
        # managers (grille du 10/10) se lisent dans `!tl liste`
        lignes.append(f"-# [fixe] = {', '.join(fixes) if fixes else 'personne dans cette liste'} (décision du 09/10) ; "
                      f"[clic] = tous les autres, {_usd(TAUX_CLIC)} la visite payée, sur la liste du 5 et du 20 (au clic depuis le "
                      "05/10 pour les anciens fixes). `!paie @clipper clic|fixe` pour changer. Primes d'équipe des TL et managers : "
                      "`!tl liste` (admin). Repère de rentabilité d'un fixe : ≈ 65 visites payables/jour pour 200 €, ≈ 32/jour "
                      "pour 100 € (0,30 $ de CA par visite, 35 % de marge).")
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
            qui = (f"→ {nom_de(info['uid'])}" if info.get("uid") else
                   "→ **hors clipping**" if info.get("hors_clipping") else
                   "→ **libre** (désactivé, réactivé à l'attribution)" if (l.get("enabled") is False or info.get("desactive")) else
                   "→ **libre**")
            hier_txt = ("hier non relevé" if non_releves(d, [l.get("id")], hier, hier)       # 10/10 : jamais un faux 0
                        else f"hier {_fmt(h['payes'])} payées")
            lignes.append(f"· {str(l.get('name', '')).split()[0]} · {l.get('note')} · <{l.get('url')}> {qui}"
                          + (f" · {hier_txt}" if info.get("uid") else ""))
        lignes.append("-# `!lien @clipper <url ou slug>` pour attribuer (`forcer` si le lien est déjà à quelqu'un) · "
                      "`!lien @clipper nouveau` pour cloner un lien de sa créatrice · `!lien @clipper retirer` (libéré pour le suivant, ses visites "
                      "jusqu'à hier restent sur sa paie ; `retirer erreur` si ce lien n'a jamais été le sien)")
        await _deps["envoyer_long"](message, lignes)
        return True

    # !lien @clipper [url | slug | nouveau [Créatrice] | retirer]
    if not message.mentions:
        await message.reply("Format : `!lien @clipper <url ou slug GAML>` (`forcer` à la fin pour un lien déjà à quelqu'un) · "
                            "`!lien @clipper nouveau [Créatrice]` · `!lien @clipper retirer [erreur]` (le lien est libéré) · `!lien @clipper` pour voir.")
        return True
    membre = message.mentions[0]; uid = str(membre.id)
    reste = [m for m in mots[1:] if not m.startswith("<@")]
    if not reste:
        lids = liens_de(d, uid)
        await message.reply(f"{membre.display_name} → " + (" · ".join(f"<{d['liens'][l].get('url')}>" for l in lids) if lids else "aucun lien")
                            + ("" if uid in d["wallets"] else " · ⚠️ pas d'adresse de paiement"))
        return True
    if reste[0].lower() == "retirer":
        # 09/10 (dashboard) : le lien retiré est LIBÉRÉ (`libere`, `ancien`) : avant, seul l'uid était vidé et `associer_auto` le
        # rendait au même membre dans l'heure (note « Clipping Prénom » inchangée), ou le lien restait dans les limbes (ni libre, ni
        # ménagé, ni relevé). Libéré, il n'est plus rendu par la note (renommé « Clipping libre (ex-…) » à la passe horaire), il
        # repart au suivant de la créatrice, et le ménage le désactive s'il ne fait plus de visites. Revue CLICS du 09/10 : ses
        # visites jusqu'à hier lui restent payées s'il est au clic (`dus`, comme une sortie) ; `!lien @x retirer erreur` quand le lien
        # n'a jamais été le sien (attribution à corriger) : rien ne lui reste dû.
        prenom_r = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
        erreur_attr = any(m.lower() == "erreur" for m in reste[1:])
        dus_poses = 0
        if not erreur_attr:
            dus_poses = sum(garder_dus(d["liens"][lid], uid, d) for lid in liens_de(d, uid))
        libres = liberer_liens(d, uid, "")
        for lid in libres:
            d["liens"][lid].update({"ancien": prenom_r, "ancien_uid": uid})
        _ecrire(d)
        if not libres:
            await message.reply(f"{membre.display_name} n'a aucun lien attribué.")
            return True
        await message.reply(f"✅ {len(libres)} lien(s) de {membre.display_name} retiré(s) et libéré(s) pour le suivant de la créatrice "
                            "(l'historique des visites reste). "
                            + ("Attribution corrigée : rien ne lui reste dû sur ce lien." if erreur_attr else
                               "Ses visites jusqu'à hier restent sur sa paie (au clic). `!lien @x retirer erreur` si ce lien n'a jamais "
                               "été le sien." if dus_poses else ""))
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
    forcer = any(m.lower() == "forcer" for m in reste[1:])               # 09/10 : `!lien @x <url> forcer`
    trouve = next((l for l in liens if l.get("id") == cible or str(l.get("url", "")).rstrip("/") == cible
                   or str(l.get("url", "")).rstrip("/").endswith("/" + cible.split("/")[-1])), None)
    if trouve is None:
        await message.reply(f"Lien « {cible} » introuvable dans GAML (`!liens` pour la liste).")
        return True
    info_av = d["liens"].get(trouve["id"]) or {}
    eteint = trouve.get("enabled") is False
    # 09/10 (dashboard : « pas de liens pas assignés ») : un lien déjà à quelqu'un — un autre clipper, une ligne Metricool (hors
    # clipping), un clipper suivi par le rapport sous un autre prénom — n'est plus réattribué en silence : refusé sans `forcer`. Avant,
    # il changeait de main avec `depuis` = sa date de création : tout son historique, quinzaine en cours comprise, passait au nouveau.
    uid_av = str(info_av.get("uid") or "")
    if uid_av == uid:
        await message.reply(f"{trouve.get('url')} est déjà le lien de {membre.display_name} : rien changé.")
        return True
    prenom_n = _n_note(prenom).split()[:1]
    suivi_autre = bool(info_av.get("suivi")) and not info_av.get("libere") and _n_note(info_av.get("suivi_nom")).split()[:1] != prenom_n
    proprio = (f"<@{uid_av}>" if uid_av else f"la ligne « {info_av.get('hors_clipping')} »" if info_av.get("hors_clipping")
               else f"{info_av.get('suivi_nom')} (suivi par le rapport)" if suivi_autre else "")
    if proprio and not forcer:
        await message.reply(f"⛔ {trouve.get('url')} ({trouve.get('note') or info_av.get('note') or '?'}) est déjà à {proprio} : rien changé. "
                            f"Pour le donner quand même à {membre.display_name} (ses visites comptent alors à partir d'aujourd'hui) : "
                            f"`!lien @{prenom} {cible} forcer`.")
        return True
    if not str(info_av.get("uid") or "") and (info_av.get("libere") or info_av.get("desactive") or eteint):
        # 08/10 (revue) : un lien libéré ou désactivé passe par la reprise — réactivé, visites comptées à partir d'aujourd'hui
        cr = (str(trouve.get("name") or "").split() or [str(info_av.get("creatrice") or "?")])[0]
        fiche_l = d["liens"].setdefault(trouve["id"], {"uid": "", "url": trouve.get("url"), "note": trouve.get("note"), "creatrice": cr})
        if eteint:
            fiche_l["desactive"] = fiche_l.get("desactive") or "gaml"   # reprendre_lien refuse si la réactivation échoue
        fiche_l.pop("hors_clipping", None)
        if not await reprendre_lien(d, trouve["id"], uid, prenom, cr):
            _ecrire(d)
            await message.reply("❌ Lien désactivé dans GAML et réactivation refusée (forfait plein ?) : rien attribué.")
            return True
        _ecrire(d)
        await message.reply(f"✅ {trouve.get('url')} repris (réactivé, note « Clipping {prenom} », visites comptées à partir "
                            f"d'aujourd'hui) → {membre.display_name}.")
        return True
    # 09/10 (dashboard) : un lien qui a déjà eu un détenteur (forcé, retiré avant le 09/10, rendu par un orphelin…) compte pour le
    # nouveau à partir d'aujourd'hui ; un lien neuf ou seulement relevé, à partir de sa création (son historique est à lui)
    deja_eu = bool(proprio) or (bool(info_av) and not releve_seul(info_av) and info_av.get("par") != "rapport")
    fiche_n = {"uid": uid, "note": trouve.get("note"), "url": trouve.get("url"),
               "creatrice": str(trouve.get("name", "")).split()[0] if trouve.get("name") else "",
               "depuis": _aujourdhui().isoformat() if deja_eu else max(CLICS_DEPUIS, str(trouve.get("createdAt", ""))[:10] or CLICS_DEPUIS),
               "par": str(message.author.id)}
    if info_av.get("dus"):
        fiche_n["dus"] = list(info_av["dus"])                           # les visites dues à un sortant restent à lui
    du_ancien = False
    if uid_av:
        fiche_n["ancien_uid"] = uid_av
        # revue CLICS du 09/10 : l'ancien détenteur au clic (toujours dans l'équipe, ou parti) garde ses visites jusqu'à hier ; avant,
        # `forcer` les effaçait de la paie (ni à lui, ni au nouveau, compté à partir d'aujourd'hui)
        calcul = {"depuis": info_av.get("depuis"), "dus": list(fiche_n.get("dus") or [])}
        du_ancien = garder_dus(calcul, uid_av, d)
        if du_ancien:
            fiche_n["dus"] = calcul["dus"]
    avert = ""
    p_note = _n_note(_prenom_note(trouve.get("note"))).split()[:1]
    if proprio or (p_note and p_note != prenom_n):
        # forcé, ou note « Clipping <un autre prénom> » : la note GAML suit le nouveau détenteur (sinon l'app la montre à l'ancien,
        # et une note « Metricool » laissée ferait ressortir le lien du clipping à la passe horaire)
        try:
            await _requete("PATCH", f"/links/{trouve['id']}", corps={"note": f"Clipping {prenom}"})
            fiche_n["note"] = f"Clipping {prenom}"
        except RuntimeError as erreur:
            avert = f"\n⚠️ Note GAML non changée ({erreur}) : mets « Clipping {prenom} » à la main dans GAML."
    d["liens"][trouve["id"]] = fiche_n
    _ecrire(d)
    await message.reply(f"✅ {trouve.get('url')} ({trouve.get('note')}) → {membre.display_name}"
                        + (f" (repris de {proprio}, visites comptées à partir d'aujourd'hui"
                           + (f" ; celles d'avant restent sur la paie de {proprio}" if du_ancien else "") + ")" if proprio else "")
                        + ". Relevé rétroactif en cours, `!mesclics` pour lui d'ici un quart d'heure." + avert)
    return True
