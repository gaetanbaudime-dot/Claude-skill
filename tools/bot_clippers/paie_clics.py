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
    `!paie-clics 5|20 [AAAA-MM]` : la liste adresse-montant de la paie du 5 (16 → fin du mois
    précédent) ou du 20 (1 → 15 du mois), avec le CSV. Le virement reste humain.

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

import aiohttp
import discord

import google_api

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
LIGNE_MATIN = os.environ.get("CLICS_LIGNE_MATIN", "0").strip() == "1"   # 05/10 : la ligne « Visites hier » du salon perso, éteinte
# 25/09 : les anciens clippers gardent leur fixe deux semaines, puis clic ou sortie. Le bilan part tout seul ce jour-là.
BILAN_FIXE_DATE = os.environ.get("BILAN_FIXE_DATE", "2026-10-05").strip()      # 28/09 (Gaëtan) : bascule le 05/10, plus le 09/10
BILAN_FIXE_JOURS = int(os.environ.get("BILAN_FIXE_JOURS", "14") or 14)
SEUIL_FIXE_100 = int(os.environ.get("SEUIL_FIXE_100", "32") or 32)            # visites payables/jour qui rentabilisent 100 €
SEUIL_FIXE_200 = int(os.environ.get("SEUIL_FIXE_200", "65") or 65)            # … et 200 € (0,30 $ de CA par visite, 35 % de marge)
CLICS_EXCLURE = {p.strip().lower() for p in os.environ.get("CLICS_EXCLURE", "rianah,gaetan,gaëtan,jonas,x,y").split(",") if p.strip()}
# 08/10 (Gaëtan) : tout le monde au clic sauf ces prénoms (Jonas = manager). Sans accents. 09/10 (Gaëtan : « Julien arrête tout, il va
# juste faire le monteur vidéo maintenant pour moi ») : « julien » retiré, l'ancien sort du clipping (`!monteur`) et le nouveau Julien
# clipper est au clic comme les autres.
PAIE_FIXE = {"".join(c for c in unicodedata.normalize("NFD", p.strip().lower()) if unicodedata.category(c) != "Mn")
             for p in os.environ.get("PAIE_FIXE", "caroline,lilian,josue,yves,rianah,jonas").split(",") if p.strip()}
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
    raise RuntimeError(f"GAML : trop de tentatives sur {chemin}")


async def liens_gaml() -> list:
    """08/10 (audit : 50 liens renvoyés pile, forfait à 49 actifs) : page 2, 3… tant qu'elles apportent des liens nouveaux.
    Une API qui ignore `page` renvoie la même liste (rien de neuf : on s'arrête) ; une page refusée arrête la lecture sans
    perdre la première."""
    def _lot(r):
        return r if isinstance(r, list) else ((r or {}).get("member") or (r or {}).get("links") or (r or {}).get("data") or [])
    tous = _lot(await _requete("GET", "/links"))
    vus = {l.get("id") for l in tous}
    for page in range(2, 11):
        try:
            neufs = [l for l in _lot(await _requete("GET", "/links", params={"page": page})) if l.get("id") not in vus]
        except RuntimeError as erreur:
            journal.info("Liens GAML : page %s refusée (%s), %s liens lus", page, erreur, len(tous))
            break
        if not neufs:
            break
        tous += neufs
        vus.update(l.get("id") for l in neufs)
    return tous


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


async def releve(link_id: str, jour: date) -> dict:
    """Relevé d'un lien pour un jour (heure de Paris) : brut (robots inclus), hors robots, payés. 09/10 (dashboard) : accepte
    l'enveloppe `{data}` et la clé `total_visits` (forme du MCP), et lève une erreur sur une réponse illisible (jamais un 0)."""
    base = {"link_id": link_id, "range": "custom", "date_from": jour.isoformat(), "date_to": jour.isoformat(),
            "timezone": FUSEAU}
    pays = _liste_reponse(await _requete("GET", "/analytics/countries", params=base), "/analytics/countries")
    hors_robots, payes = _comptes_pays(pays)
    avec = _liste_reponse(await _requete("GET", "/analytics/visitors", params={**base, "hide_bots": "false"}), "/analytics/visitors")
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


def _carte_privee(detail: dict):
    """La carte OnlyFans d'un lien (celle qui porte le lien de tracking). 02/10 : les deux boutons s'appellent désormais
    « Plateforme exclusive » ; la carte se repère d'abord par sa destination (onlyfans.com), puis par son nom, et jamais une
    carte MYM : un lien sans carte OnlyFans renvoie None plutôt que d'écraser le lien MYM (cause des « Miam » → OnlyFans)."""
    cartes = detail.get("contents") or []
    if not cartes:
        return None
    def _nom(c):
        return str(c.get("name", "")).lower().strip()
    def _dest(c):
        return str(c.get("value") or "").lower()
    carte_of = next((c for c in cartes if "onlyfans.com" in _dest(c)), None)
    if carte_of:
        return carte_of
    hors_mym = [c for c in cartes if "mym.fans" not in _dest(c)]
    if not hors_mym:
        return None
    return next((c for c in hors_mym if any(m in _nom(c) for m in ("priv", "platform", "plateforme", "exclusi", "onlyfans", "only fans"))
                 or _nom(c) in ("of", "0f")), hors_mym[0])                  # 27/09 : la carte de Clara s'appelait « 0F »


async def poser_tracking(link_id: str, url: str) -> str:
    """27/09 (Gaëtan) : « quand tu crées un lien de clipper, tu dupliques celui d'avant et tu modifies le lien dans Cards ».
    Met `url` (le lien de tracking OnlyFans du POD) dans la carte « Plateforme privée ». Renvoie 'ok', 'déjà' ou la raison."""
    if not url:
        return "sans tracking"
    carte = _carte_privee(await lien_detail(link_id))
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
    mym = next((c for c in cartes if "mym.fans" in str(c.get("value") or "").lower()), None)
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


def prochaine_paie(ref: date) -> date:
    """Le prochain jour de paie : le 20 pour la quinzaine du 1 au 15, le 5 du mois suivant pour celle du 16 à la fin."""
    if ref.day <= 15:
        return date(ref.year, ref.month, 20)
    premier = (date(ref.year, ref.month, 1) + timedelta(days=32)).replace(day=1)
    return date(premier.year, premier.month, 5)


def periode_en_cours() -> tuple:
    ref = _aujourdhui()
    if ref.day <= 15:
        return date(ref.year, ref.month, 1), date(ref.year, ref.month, 15)
    fin = (date(ref.year, ref.month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return date(ref.year, ref.month, 16), fin


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
    return [lid for lid, info in d["liens"].items() if str(info.get("uid")) == str(uid)]


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
    (note, nom, URL, désactivation dans GAML) : personne d'autre ne l'écrit. Renvoie le nombre de fiches créées ou changées.
    L'appelant écrit `d`."""
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
    de plus dans le forfait), un lien désactivé par le ménage ensuite (`reprendre_lien` le réactive)."""
    cible = (creatrice or "").split()[0].lower() if creatrice else ""
    if not cible:
        return None
    libres = [(lid, info) for lid, info in d.get("liens", {}).items()
              if not str(info.get("uid") or "") and info.get("libere") and not info.get("supprime_gaml") and not info.get("hors_clipping")
              and str(info.get("creatrice") or "").lower().startswith(cible)]
    libres.sort(key=lambda li: bool(li[1].get("desactive")))
    return libres[0] if libres else None


async def reprendre_lien(d: dict, lid: str, uid: str, prenom: str, creatrice: str) -> bool:
    """Le lien d'un sortant passe au suivant : uid, `depuis` = aujourd'hui (ses visites commencent là), note « Clipping Prénom »
    (aussi côté GAML, sans bloquer si l'API refuse). 08/10 : réactivé côté GAML s'il avait été désactivé par le ménage ; si
    GAML refuse la réactivation (forfait plein), rien n'est repris (jamais un lien mort dans une bio) et on renvoie False.
    L'appelant écrit `d`."""
    info = d["liens"][lid]
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
        if l is None or not (str(info.get("uid") or "") or info.get("libere") or info.get("hors_clipping")):
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


def somme(d: dict, link_ids, debut: date, fin: date) -> dict:
    """Visites des liens sur la période. 28/09 : un lien repris d'un sortant ne compte pour son nouveau clipper qu'à partir de
    `depuis` (les visites d'avant sont celles de l'ancien)."""
    tot = {"brut": 0, "hors_robots": 0, "payes": 0, "jours": 0}
    for lid in link_ids:
        dep = str((d.get("liens", {}).get(lid) or {}).get("depuis") or "")
        for j, v in d["jours"].get(lid, {}).items():
            if debut.isoformat() <= j <= fin.isoformat() and j >= dep:
                tot["brut"] += v.get("brut", 0); tot["hors_robots"] += v.get("hors_robots", 0)
                tot["payes"] += v.get("payes", 0); tot["jours"] += 1
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
    debut = _debut_paie(uid, debut, d)                                  # 08/10 : passé au clic ce jour-là
    q = somme(d, lids, debut, min(fin, hier))
    part = f" ({h['payes'] * 100 // h['hors_robots']} % de tes visiteurs)" if h["hors_robots"] else ""
    robots = h["brut"] - h["hors_robots"]
    au_clic = regime(uid) == "clic"
    return (f"📊 **Tes visites, {nom}**" + ("" if au_clic else " · tu es au fixe, ces montants sont juste pour info") + "\n\n"
            f"Hier, le {hier.strftime('%d/%m')} : **{_fmt(h['payes'])} visites qui comptent**{part}"
            + (f". {robots} robots enlevés" if robots > 0 else "") + ".\n\n"
            f"Sur 7 jours : **{_fmt(s7['payes'])}** visites qui comptent, sur {_fmt(s7['hors_robots'])} visiteurs.\n\n"
            + ((f"💸 **Ta paie en cours : {_usd(q['payes'] * TAUX_CLIC)}** ({_fmt(q['payes'])} visites du {debut.strftime('%d/%m')} au "
                f"{fin.strftime('%d/%m')}), virée le {prochaine_paie(_aujourdhui()).strftime('%d/%m')}.\n") if au_clic else
               (f"Quinzaine du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')} : **{_fmt(q['payes'])} visites = "
                f"{_usd(q['payes'] * TAUX_CLIC)}**.\n"))
            +
            f"Une visite qui compte = {_usd(TAUX_CLIC)}. Elle vient de France ou d'un pays francophone. Ce n'est pas un robot.\n\n"
            + ("" if not au_clic or str(uid) in d["wallets"] else "⚠️ Je n'ai pas ton adresse de paiement. Colle ton adresse USDC dans ton app (onglet Versements), ou écris `!wallet 0x…` ici (`!wallet FR76…` pour un virement).\n\n")
            + "-# Ton lien : " + " · ".join(d["liens"][l].get("url", "") for l in lids))


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
    s7 = somme(d, lids, hier - timedelta(days=6), hier)
    au_clic = regime(uid) == "clic"
    montant = f" = {_usd(q['payes'] * TAUX_CLIC)} · virée le {prochaine_paie(_aujourdhui()).strftime('%d/%m')}" if au_clic else ""   # 28/09 (GO n° 8)
    # 26/09 : une ligne, dans le message du matin (les détails restent dans `!mesclics`)
    return (f"👀 Visites hier : **{_fmt(h['payes'])}** · quinzaine : **{_fmt(q['payes'])}{montant}**"
            + ("" if not au_clic or str(uid) in d["wallets"] else "\n⚠️ Adresse de paiement manquante : colle-la dans ton app (onglet Versements) ou `!wallet 0x…`"))


def liberer_sortant(d: dict, uid: str, prenom: str = "") -> list:
    """09/10 (dashboard : « pas de liens pas assignés ») : `!sortie` sans pool libère aussi les liens du sortant — par son uid
    seulement (jamais par la note : un homonyme garde les siens). Avant, le lien restait attribué à un membre parti de l'équipe :
    lien sans compte, jamais redonné ni ménagé. Les visites d'AVANT la sortie restent à lui (le MP de sortie promet « ce qui t'est
    dû est réglé au prochain décompte ») : chaque lien garde `dus` = [{uid, depuis, avant}], que la liste de paie compte (jours
    `depuis` ≤ j < `avant`, le jour de la sortie exclu : il revient au suivant si le lien est repris le jour même). À appeler AVANT
    le retrait du registre (régime et plancher du clic lus sur sa fiche) ; un sortant au fixe n'a rien de dû au clic. Renvoie les
    identifiants libérés. L'appelant écrit `d`."""
    uid = str(uid or "")
    if not uid:
        return []
    au_clic = regime(uid) == "clic"
    plancher = debut_clic(uid, d) if au_clic else ""
    jour = _aujourdhui().isoformat()
    libres = liberer_liens(d, uid, "")
    for lid in libres:
        info = d["liens"][lid]
        info["ancien_uid"] = uid
        if prenom:
            info["ancien"] = prenom
        if au_clic:
            dep = max(str(info.get("depuis") or CLICS_DEPUIS)[:10], str(plancher or "")[:10])
            if dep < jour:
                info.setdefault("dus", []).append({"uid": uid, "depuis": dep, "avant": jour})
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


def liste_paie(d: dict, nom_de, debut: date, fin: date, jour_paie: str) -> tuple:
    """Lignes Discord + CSV de la paie : un clipper par ligne, visites payées, montant, adresse."""
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
        if lids and regime(uid) != "clic":
            fixes.append((nom_de(uid), somme(d, lids, debut, fin)["payes"]))
            if not du["payes"]:
                continue
            s = {"payes": 0, "hors_robots": 0}
        else:
            s = somme(d, lids, _debut_paie(uid, debut, d), fin) if lids else {"payes": 0, "hors_robots": 0}   # 08/10 : passé au clic ce jour-là
        s = {"payes": s["payes"] + du["payes"], "hors_robots": s["hors_robots"] + du["hors_robots"]}
        if s["payes"] == 0:
            continue
        montant = round(s["payes"] * TAUX_CLIC, 2); total += montant
        w = d["wallets"].get(uid, {}).get("adresse", "")
        if not w:
            sans += 1
        rangs.append((nom_de(uid), uid, s["payes"], s["hors_robots"], montant, w))
    rangs.sort(key=lambda r: -r[4])
    cle_periode = jour_paie if "-" in jour_paie else f"{fin.year}-{jour_paie[3:5]}-{jour_paie[:2]}"
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
    for nom, uid, payes, hors, montant, w in rangs:
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else (w or "⚠️ adresse manquante")
        bonus = "".join(f" · 🎁 +{_usd(pr)} parrainage de {f}" for f, pr in primes.get(uid, []))
        lignes.append(f"· {nom} — {_fmt(payes)} payées ({_fmt(hors)} visiteurs) → **{_usd(montant)}** → {adr}{bonus}")
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
        if note_du_sortant(d["liens"].get(lid) or {}, l.get("note")):  # 09/10 : le lien d'un sortant, jamais à son homonyme
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
    return not isinstance(v, dict) or bool(v.get("erreur"))


async def rattraper(d: dict, limite_appels: int = 110) -> int:
    """Complète les jours manquants (depuis `depuis`, jusqu'à hier) de chaque lien relevé (`a_relever`). Borné par appel pour
    respecter la limite GAML ; la boucle repasse un quart d'heure plus tard.
    09/10 (dashboard, contrat C2) : 1. tous les liens actifs, pas seulement les payés (pages de créatrice, /ytb, /fb, libérés, hors
    clipping : RELEVE_RECUL jours en arrière pour eux) ; 2. la veille d'abord pour tous (paie, ligne du matin, rapport), les liens
    payés en tête, puis les jours anciens (RELEVE_ANCIENS_MAX appels par passage : le rattrapage d'un lien neuf ne prend jamais
    toute la minute de l'app) ; 3. une erreur GAML n'écrit JAMAIS de 0 : le jour reste absent (404 : lien introuvable, rien écrit,
    retenté demain ; autre erreur : on s'arrête, la boucle repasse) ; 4. une veille lue avant RELECTURE_HEURE (Paris) est provisoire :
    relue une fois après, puis figée (dernières visites de la soirée, robots reclassés par GAML)."""
    maintenant = _deps["heure_paris"]()
    aujourdhui = maintenant.date()
    hier = aujourdhui - timedelta(days=1)
    jour_iso = aujourdhui.isoformat()
    provisoires = d.setdefault("provisoires", {})
    appels, anciens = 0, 0

    def retirer_provisoire(lid: str, js: str) -> None:
        if js in provisoires.get(lid, []):
            provisoires[lid].remove(js)
        if lid in provisoires and not provisoires[lid]:
            provisoires.pop(lid, None)

    async def lire(lid: str, info: dict, j: date) -> str:
        """'ok', '404' ou 'stop' (erreur GAML : fin du passage). Écrit seulement un relevé réussi."""
        nonlocal appels
        if appels and RELEVE_PAUSE > 0:
            await asyncio.sleep(RELEVE_PAUSE)                           # minuit : ~55 liens d'un coup, la minute reste partagée avec l'app
        try:
            v = await releve(lid, j)
        except RuntimeError as erreur:
            journal.warning("Relevé %s %s : %s", info.get("note") or lid, j, erreur)
            appels += 1
            if "404" in str(erreur):
                info["introuvable"] = jour_iso                          # rien d'écrit : ni 0 ni trou comblé, retenté demain
                return "404"
            return "stop"
        appels += 2
        d["jours"].setdefault(lid, {})[j.isoformat()] = v
        if j == hier and maintenant.hour < RELECTURE_HEURE:
            if j.isoformat() not in provisoires.setdefault(lid, []):
                provisoires[lid].append(j.isoformat())
        else:
            retirer_provisoire(lid, j.isoformat())                      # relu après RELECTURE_HEURE : figé
        _ecrire(d)
        return "ok"

    def payant(info):
        return bool(str(info.get("uid") or "") or info.get("suivi"))
    cibles = [(lid, info) for lid, info in list(d["liens"].items()) if a_relever(info, jour_iso)]
    cibles.sort(key=lambda li: 0 if payant(li[1]) else 1)              # tri stable : l'ordre du fichier sinon
    # 1. la veille de chaque lien
    for lid, info in cibles:
        if appels >= limite_appels:
            return appels
        debut = _en_date(info.get("depuis")) or _jour(CLICS_DEPUIS)
        if hier < debut or not _manque(d["jours"].get(lid, {}), hier) or str(info.get("introuvable") or "") == jour_iso:
            continue
        if await lire(lid, info, hier) == "stop":
            return appels
    # 2. la relecture des veilles provisoires, une fois passé RELECTURE_HEURE (ou un jour plus tard)
    for lid in list(provisoires):
        info = d["liens"].get(lid)
        if info is None or not a_relever(info, jour_iso):
            provisoires.pop(lid, None)
            continue
        for js in sorted(provisoires.get(lid, [])):
            j = _en_date(js)
            if j is None or j >= aujourdhui:
                retirer_provisoire(lid, js)
                continue
            if j == hier and maintenant.hour < RELECTURE_HEURE:
                continue
            if appels >= limite_appels:
                return appels
            r = await lire(lid, info, j)
            if r == "stop":
                return appels
            if r == "404":
                break
    # 3. les jours plus anciens
    for lid, info in cibles:
        recul = 45 if payant(info) else RELEVE_RECUL - 1
        debut = max(_en_date(info.get("depuis")) or _jour(CLICS_DEPUIS), hier - timedelta(days=recul))
        jours = d["jours"].get(lid, {})
        j = hier - timedelta(days=1)
        while j >= debut:
            if str(info.get("introuvable") or "") == jour_iso:
                break
            if _manque(jours, j):
                if appels >= limite_appels or anciens >= RELEVE_ANCIENS_MAX:
                    return appels
                avant = appels
                r = await lire(lid, info, j)
                anciens += appels - avant
                if r == "stop":
                    return appels
                jours = d["jours"].get(lid, {})
            j -= timedelta(days=1)
    return appels


async def rafraichir_aujourdhui(d: dict, maximum: int = None) -> int:
    """Contrat C2 (09/10, dashboard : « tout voir, le plus souvent possible ») : `aujourdhui[lid]` = {jour (Paris), t (ISO UTC), brut,
    hors_robots, payes} de la journée de Paris en cours, un appel `/analytics/countries` par lien relevé (`a_relever`). `brut` reste
    None : le total robots compris demande un second appel par lien, hors budget toutes les 15 minutes (jamais un faux 0). Budget
    GAML (60 requêtes/min partagées avec l'app) : `maximum` appels au plus (DIRECT_MAX), DIRECT_PAUSE secondes entre deux, arrêt
    sur un 429 ou quand il reste moins de DIRECT_RESERVE requêtes dans la minute ; les liens jamais lus aujourd'hui passent d'abord,
    puis les plus anciens (tous relus en deux passages au pire). Une erreur n'écrit rien : la valeur précédente reste, avec son
    heure. Renvoie le nombre d'appels faits. Écrit `d`."""
    maximum = DIRECT_MAX if maximum is None else maximum
    maintenant = _deps["heure_paris"]()
    jour = maintenant.date()
    jour_iso, veille = jour.isoformat(), (jour - timedelta(days=1)).isoformat()
    auj = d.setdefault("aujourdhui", {})
    for lid in list(auj):                                               # ménage : un lien disparu, un relevé d'avant-hier
        if lid not in d.get("liens", {}) or str((auj.get(lid) or {}).get("jour") or "") < veille:
            auj.pop(lid, None)
    cibles = [lid for lid, info in d.get("liens", {}).items() if a_relever(info, jour_iso)]
    cibles.sort(key=lambda lid: ((auj.get(lid) or {}).get("jour") == jour_iso, str((auj.get(lid) or {}).get("t") or "")))
    appels = 0
    jeton = _arret_429.set(True)
    try:
        for lid in cibles[:max(0, maximum)]:
            if appels and DIRECT_PAUSE > 0:
                await asyncio.sleep(DIRECT_PAUSE)
            if _limite["restant"] <= DIRECT_RESERVE and _limite["reset"] > time.time():
                journal.info("Clics du jour : %s requêtes GAML restantes dans la minute, la suite au prochain passage", _limite["restant"])
                break
            try:
                rep = await _requete("GET", "/analytics/countries", params={"link_id": lid, "range": "custom", "date_from": jour_iso,
                                                                             "date_to": jour_iso, "timezone": FUSEAU})
                hors_robots, payes = _comptes_pays(_liste_reponse(rep, "/analytics/countries"))
            except LimiteGAML as erreur:
                journal.info("Clics du jour : %s — arrêt du passage", erreur)
                break
            except RuntimeError as erreur:
                appels += 1
                journal.warning("Clics du jour %s : %s", lid, erreur)
                if "404" in str(erreur):
                    continue                                            # ce lien seulement ; le relevé quotidien le marquera
                break                                                   # GAML en panne : on n'insiste pas
            appels += 1
            t = (maintenant.astimezone(timezone.utc) if maintenant.tzinfo else datetime.now(timezone.utc)).isoformat(timespec="seconds")
            auj[lid] = {"jour": jour_iso, "t": t, "brut": None, "hors_robots": hors_robots, "payes": payes}
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


def texte_classement(d: dict, nom_de, hier: date, n: int = 5) -> str:
    """28/09 (GO n° 7) : le lundi, dans #dopamine, les cinq premiers en visites payées sur les sept derniers jours. '' si personne."""
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
    return (f"🏆 **Top {min(n, len(rangs))} de la semaine** ({debut.strftime('%d/%m')} → {hier.strftime('%d/%m')})\n" + "\n".join(lignes)
            + f"\n-# {len(rangs)} clipper(s) ont fait des visites cette semaine. Une visite = {_usd(TAUX_CLIC)}.")


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


async def annoncer_paie(client, d: dict, maintenant) -> None:
    """Jour de paie (5 : période 16 → fin du mois précédent ; 20 : 1 → 15) : la liste et le CSV au salon admin,
    et dans le salon perso de chaque clipper au clic sa ligne (visites payées, montant, adresse)."""
    cle = "5" if maintenant.day == 5 else "20"
    debut, fin = periode(cle, maintenant.strftime("%Y-%m"))
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    nom_de = lambda uid: (getattr(_deps["membre_par_id"](uid), "display_name", None)          # noqa: E731
                          or str((registre.get(uid) or {}).get("prenom") or "").title() or f"id {uid}")
    reprises = await synchroniser_adresses(d)                           # 08/10 : les adresses collées dans l'app, avant la liste
    if reprises:
        _ecrire(d)
    lignes, csv_texte = liste_paie(d, nom_de, debut, fin, maintenant.strftime("%d/%m"))
    if reprises:
        lignes.append(f"📒 {len(reprises)} adresse(s) reprise(s) de l'app : " + ", ".join(reprises)[:600])
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
        dp = _debut_paie(uid, debut, d)
        s = somme(d, liens_de(d, uid), dp, fin)
        if not s["payes"]:
            continue                                                    # 08/10 (audit) : plus de « 0,00 $, !wallet maintenant » à un nouveau
        salon = _deps["salon_perso"](uid)
        if salon is None:
            continue
        w = d["wallets"].get(uid, {}).get("adresse", "")
        adr = (w[:6] + "…" + w[-4:]) if len(w) > 12 else w
        texte = (f"💸 **Ta paie du {maintenant.strftime('%d/%m')}** (période {dp.strftime('%d/%m')} → {fin.strftime('%d/%m')}) : "
                 f"**{_fmt(s['payes'])} visites payées = {_usd(s['payes'] * TAUX_CLIC)}**"
                 + (f" → virement vers {adr} dans la journée." if w else " → ⚠️ pas d'adresse enregistrée : colle-la dans ton app (onglet Versements) ou `!wallet 0x…` maintenant, sinon la paie attend la prochaine."))
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
                if marquer_releves(d, liens_tous):                     # 09/10 (dashboard) : tous les liens actifs relevés
                    _ecrire(d)
                await publier_regimes(d)                                 # 08/10 (revue) : l'app lit le régime du bot
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
                    texte_c = texte_classement(d, prenom_c, maintenant.date() - timedelta(days=1))
                    if canal_c is not None and texte_c:
                        await canal_c.send(texte_c[:1990])
                    if texte_c and _deps.get("apres_classement"):       # 29/09 (GO axe 8) : le lien de parrainage aux cinq premiers
                        await _deps["apres_classement"](top_uids(d, maintenant.date() - timedelta(days=1)))
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Classement du lundi : %s", erreur)
                d["classement"] = aujourdhui
                _ecrire(d)
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
            ref = _aujourdhui()
            cle = "5" if ref.day <= 12 or ref.day >= 28 else "20"      # la prochaine paie
            if ref.day >= 28:
                suivant = (ref.replace(day=1) + timedelta(days=32))
                mois = mois or suivant.strftime("%Y-%m")
        debut, fin = periode(cle, mois)
        jour_paie = f"{cle.rjust(2, '0')}/{(mois or (fin + timedelta(days=1)).strftime('%Y-%m'))[5:7]}"
        reprises = await synchroniser_adresses(d)
        if reprises:
            _ecrire(d)
        lignes, csv_texte = liste_paie(d, nom_de, debut, fin, jour_paie)
        if reprises:
            lignes.append(f"📒 {len(reprises)} adresse(s) reprise(s) de l'app : " + ", ".join(reprises)[:600])
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
            q = somme(d, lids, _debut_paie(uid, debut, d), min(fin, hier))   # 08/10 (revue) : la même période que la paie
            rangs.append((nom_de(uid), h, s7, q, uid))
        rangs.sort(key=lambda r: -r[2]["payes"])
        for nom, h, s7, q, uid in rangs:
            part = f"{s7['payes'] * 100 // s7['hors_robots']} %" if s7["hors_robots"] else "–"
            reg = regime(uid)
            lignes.append(f"· {nom} [{reg}] — hier {_fmt(h['payes'])} · 7 j {_fmt(s7['payes'])} ({part} payables, "
                          f"{_fmt(s7['payes'] / 7)}/j) · quinzaine {_fmt(q['payes'])} = {_usd(q['payes'] * TAUX_CLIC)}"
                          + ("" if reg != "clic" or uid in d["wallets"] else " · ⚠️ sans adresse"))
        lignes.append("-# [fixe] = Rianah, Caroline, Lilian, Josué, Yves (et Jonas, manager), décision du 09/10 ; "
                      "[clic] = tous les autres, payés sur la liste du 5 et du 20 (au clic depuis le 05/10 pour les anciens fixes). "
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
            qui = (f"→ {nom_de(info['uid'])}" if info.get("uid") else
                   "→ **hors clipping**" if info.get("hors_clipping") else
                   "→ **libre** (désactivé, réactivé à l'attribution)" if (l.get("enabled") is False or info.get("desactive")) else
                   "→ **libre**")
            lignes.append(f"· {str(l.get('name', '')).split()[0]} · {l.get('note')} · <{l.get('url')}> {qui}"
                          + (f" · hier {_fmt(h['payes'])} payées" if info.get("uid") else ""))
        lignes.append("-# `!lien @clipper <url ou slug>` pour attribuer (`forcer` si le lien est déjà à quelqu'un) · "
                      "`!lien @clipper nouveau` pour cloner un lien de sa créatrice · `!lien @clipper retirer` (libéré pour le suivant)")
        await _deps["envoyer_long"](message, lignes)
        return True

    # !lien @clipper [url | slug | nouveau [Créatrice] | retirer]
    if not message.mentions:
        await message.reply("Format : `!lien @clipper <url ou slug GAML>` (`forcer` à la fin pour un lien déjà à quelqu'un) · "
                            "`!lien @clipper nouveau [Créatrice]` · `!lien @clipper retirer` (le lien est libéré) · `!lien @clipper` pour voir.")
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
        # repart au suivant de la créatrice, et le ménage le désactive s'il ne fait plus de visites. Ses visites passées restent
        # dans le relevé ; elles ne sont plus payées à ce membre (un retrait corrige une attribution).
        prenom_r = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
        libres = liberer_liens(d, uid, "")
        for lid in libres:
            d["liens"][lid].update({"ancien": prenom_r, "ancien_uid": uid})
        _ecrire(d)
        await message.reply(f"✅ {len(libres)} lien(s) de {membre.display_name} retiré(s) et libéré(s) pour le suivant de la créatrice "
                            "(l'historique des visites reste)." if libres else f"{membre.display_name} n'a aucun lien attribué.")
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
    if uid_av:
        fiche_n["ancien_uid"] = uid_av
    if info_av.get("dus"):
        fiche_n["dus"] = info_av["dus"]                                 # les visites dues à un sortant restent à lui
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
                        + (f" (repris de {proprio}, visites comptées à partir d'aujourd'hui)" if proprio else "")
                        + ". Relevé rétroactif en cours, `!mesclics` pour lui d'ici un quart d'heure." + avert)
    return True
