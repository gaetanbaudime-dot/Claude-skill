"""Comptes Instagram branchés à Metricool → séries par compte (09/10, dashboard — Gaëtan : « je dois comprendre quel compte est
en hausse ou en baisse de vues ; le plus précis possible, pas de trucs pas précis, pas de manquements »).

Contrat C4 de la spécification du dashboard :
    await releves() -> {"<clé IG>": {"followers": int | None, "reels": [{"code", "publie", "vues"}], "jour": "AAAA-MM-JJ"}}
pour les comptes Instagram branchés à Metricool. Metricool passe par l'API officielle d'Instagram : lisible même pour un compte
restreint, sans scraping (la voie propre au regard des CGU, contrairement à Apify). `boucle(client)` le relit deux fois par jour
(METRICOOL_HEURES, heures de Paris, défaut « 8,15 ») et écrit chaque compte lu dans les séries (series.ajouter_releve, contrat C1,
source « metricool »).

Routes REST : UNIQUEMENT celles déjà utilisées dans le dépôt, aucune inventée (base https://app.metricool.com/api, en-tête
X-Mc-Auth = METRICOOL_API_KEY, userId = METRICOOL_USER_ID s'il est posé) :
  - GET /admin/simpleProfiles (tools/mcp_metricool/metricool_mcp.py, rapport_quotidien.metricool) → les marques, l'@ Instagram
    branché (champ `instagram`) ;
  - GET /v2/analytics/brand-summary/posts?blogId=&from=AAAA-MM-JJT00:00:00&to=AAAA-MM-JJT23:59:59 (rapport_quotidien.metricool),
    un appel par marque et par JOUR comme le rapport → les publications de la marque, tous réseaux ; on ne garde que les Reels
    Instagram (réseau INSTAGRAM, type REEL, lien instagram.com/reel/<shortcode>/).
    (/v2/analytics/posts/instagram, l'autre route connue, ne rend PAS les Reels : vérifié le 09/10 en lecture par le connecteur
    Metricool, Instagram Posts vide pour une marque qui publie 5 Reels par jour.)

Ce que le module NE sait PAS lire (laissé à None, jamais 0) :
  - followers : aucune route REST du dépôt ne les lit. La donnée existe chez Metricool (Instagram Evolution > Followers, quotidienne,
    J-1, vérifiée en lecture le 09/10 par le connecteur) mais sa route REST n'est confirmée par aucun code du dépôt : à brancher
    quand elle le sera. En attendant `followers` vaut toujours None et Apify reste la source des followers ;
  - posts_total, id Instagram (simpleProfiles ne donne que l'@).

Règles (jamais un faux 0) :
  - Données à J-1 : Metricool synchronise Instagram dans la nuit. Le jour en cours est TOUJOURS exclu (vérifié le 09/10 à 10 h :
    les Reels du matin absents, et « Followers » du jour à 0 dans Metricool — le zéro d'un jour pas encore synchronisé). Un passage
    lit les JOURS jours qui finissent la veille (défaut 9 : 7 jours + 2 de marge pour la mesure des vues à 48 h) ;
  - relevé daté de la fin de la veille (minuit à Paris) : la photo de Metricool est celle de sa synchro de la nuit. Les deux passages
    d'un même jour écrivent donc le MÊME relevé (même heure) : le second remplace le premier, aucun doublon. `couvre` = début de la
    fenêtre (series : les Reels publiés depuis sont tous connus) ;
  - vues d'un Reel : UNE métrique, les vues Instagram du Reel (« Instagram Reels > Views »). Dans brand-summary elle s'appelle VIEWS,
    ou IMPRESSIONS (même chiffre pour un Reel Instagram : vérifié le 09/10 sur 10 Reels, impressions du résumé = views des Reels).
    Une valeur absente, illisible ou 0 = pas de point (un Reel de la veille à 0 vue est un chiffre pas encore relevé, pas un 0) ;
  - un compte n'est écrit que s'il est lu ENTIER : un jour en erreur → compte non lu ; aucune publication Instagram sur la fenêtre
    → non lu (Instagram débranché de Metricool ou compte à l'arrêt : on ne l'écrit pas comme « 0 Reel ») ; un Reel sans lien ou sans
    date → format non reconnu, non lu ; 0 Reel la veille alors que les deux jours d'avant en ont → veille pas encore synchronisée,
    non lu (le passage suivant le relira) ; au moins 2 Reels déjà connus de la série (Apify ou Metricool) absents de la réponse et
    au moins le quart des connus → liste incomplète, non lu ;
  - dédoublonnage par (réseau, compte) : deux marques qui portent le même @ Instagram ne sont lues qu'une fois (la marque d'id le
    plus petit) ;
  - correspondance marque → @ Instagram → clé du classeur : la clé est celle du scan (etats_comptes._cle =
    onboarding.normaliser_handle en minuscules) ; un @ renommé est suivi par les alias de series.

Dépendances (`configurer`, toutes facultatives) : lire_json, ecrire_json, FICHIER (état : passages faits, dernier bilan),
FICHIER_SERIES (series n'est configuré ici que s'il ne l'est pas déjà — c'est le scan qui le configure normalement), heure_paris,
canal_admin (une alerte par jour au plus si Metricool est en panne ou si sa réponse n'est plus comprise), cle (fonction @ → clé),
lire_comptes (le classeur : les comptes Metricool dont l'@ n'est sur aucune ligne sont listés au bilan, `hors_classeur`).
Variables : METRICOOL_API_KEY (sans elle : rien), METRICOOL_USER_ID, METRICOOL_COMPTES=0 pour éteindre, METRICOOL_HEURES,
METRICOOL_JOURS."""
import asyncio
import logging
import os
import re
from datetime import date, datetime, time as dtime, timedelta, timezone

import aiohttp

journal = logging.getLogger("bot.metricool")
_deps: dict = {}

API_BASE = "https://app.metricool.com/api"
ROUTE_MARQUES = "admin/simpleProfiles"
ROUTE_PUBLICATIONS = "v2/analytics/brand-summary/posts"
METRICOOL_API_KEY = os.environ.get("METRICOOL_API_KEY", "").strip()
METRICOOL_USER_ID = os.environ.get("METRICOOL_USER_ID", "").strip()
ACTIF = os.environ.get("METRICOOL_COMPTES", "1").strip() != "0"
HEURES = sorted({int(h) for h in re.findall(r"\d+", os.environ.get("METRICOOL_HEURES", "8,15") or "8,15") if 0 <= int(h) <= 23}) \
    or [8, 15]
JOURS = max(3, min(30, int((re.findall(r"\d+", os.environ.get("METRICOOL_JOURS", "") or "") or ["9"])[0])))
SOURCE = "metricool"
PAUSE_S = 0.5                                    # entre deux appels (comme le rapport) : Metricool ne publie pas sa limite
PAUSE_429_S = 60                                 # « trop d'appels » : une minute, puis un seul nouvel essai
TIMEOUT_S = 60
DELAI_DEMARRAGE_S = 120
TOUR_S = 600                                     # la boucle regarde l'heure toutes les 10 min
ESSAIS_MAX = 3                                   # passage en panne : retenté au tour suivant, 3 fois au plus par jour
TYPES_REEL = {"REEL", "REELS", "CLIPS", "VIDEO"}
MANQUANTS_MIN = 2                                # liste incomplète : au moins 2 Reels connus absents…
MANQUANTS_PART = 0.25                            # … et au moins le quart des Reels connus de la fenêtre

_RE_CODE = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
_PARIS = None
_dernier_bilan: dict = {}


class ErreurMetricool(Exception):
    """Réponse HTTP autre que 200 (ou forme illisible) : la donnée n'est pas lue, jamais remplacée par 0."""

    def __init__(self, statut, chemin: str = ""):
        super().__init__(f"Metricool {statut} sur {chemin}")
        self.statut = statut


def configurer(deps: dict):
    _deps.update(deps or {})
    if _deps.get("FICHIER_SERIES") and _deps.get("lire_json") and _deps.get("ecrire_json"):
        try:
            import series
            deja = series.actif() if callable(getattr(series, "actif", None)) else False
            if not deja:
                series.configurer({"lire_json": _deps["lire_json"], "ecrire_json": _deps["ecrire_json"],
                                   "FICHIER_SERIES": _deps["FICHIER_SERIES"]})
        except ImportError:
            journal.warning("Metricool : series.py absent, les relevés ne seront pas écrits")


def actif() -> bool:
    return ACTIF and bool(METRICOOL_API_KEY)


# ------------------------------------------------------------------ outils purs
def _paris_tz():
    global _PARIS
    if _PARIS is None:
        try:
            from zoneinfo import ZoneInfo
            _PARIS = ZoneInfo("Europe/Paris")
        except Exception:                                                # noqa: BLE001
            _PARIS = timezone(timedelta(hours=2))
    return _PARIS


def _fuseau(nom):
    """Le fuseau d'une marque (champ `timezone` de Metricool) ; Paris si absent ou inconnu."""
    if not nom:
        return _paris_tz()
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(str(nom))
    except Exception:                                                    # noqa: BLE001
        return _paris_tz()


def _maintenant_paris(maintenant=None) -> datetime:
    if maintenant is None:
        maintenant = _deps["heure_paris"]() if callable(_deps.get("heure_paris")) else datetime.now(timezone.utc)
    if maintenant.tzinfo is None:
        maintenant = maintenant.replace(tzinfo=timezone.utc)
    return maintenant.astimezone(_paris_tz())


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _cle(handle) -> str:
    """La clé d'un compte, la même que celle du scan (etats_comptes._cle) : @ nettoyé (URL, @, espaces) en minuscules."""
    if callable(_deps.get("cle")):
        return str(_deps["cle"](handle) or "")
    try:
        import onboarding
        return onboarding.normaliser_handle(handle).lower()
    except Exception:                                                    # noqa: BLE001 — repli : même nettoyage, en plus simple
        t = re.sub(r"^(?:https?://)?(?:www\.)?instagram\.com/", "", str(handle or "").strip(), flags=re.I)
        t = t.split("?")[0].split("#")[0].strip().strip("/").split("/")[0].strip().lstrip("@").strip()
        return ((t.split() or [""])[0]).rstrip(".,;:").lower()


def fenetre(veille: date) -> tuple:
    """[début, fin[ de la lecture d'un passage, en instants de Paris : les JOURS jours qui finissent `veille` (J-1) inclus.
    `fin` (minuit à Paris, fin de la veille) est l'heure du relevé ; `début` est sa couverture."""
    tz = _paris_tz()
    debut = datetime.combine(veille - timedelta(days=JOURS - 1), dtime(0), tzinfo=tz)
    fin = datetime.combine(veille + timedelta(days=1), dtime(0), tzinfo=tz)
    return debut, fin


def _instant(v, tz=None):
    """Une date de publication Metricool → instant avec fuseau, ou None. Formes acceptées : {"dateTime", "timezone"} (forme des
    dates de Metricool), ISO avec ou sans fuseau (sans fuseau = fuseau de la marque), « AAAAMMJJHHMMSS », secondes ou
    millisecondes depuis 1970."""
    tz = tz or _paris_tz()
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, dict):
        brut = v.get("dateTime") or v.get("date") or v.get("value")
        return None if isinstance(brut, dict) else _instant(brut, _fuseau(v.get("timezone")) if v.get("timezone") else tz)
    if isinstance(v, (int, float)):
        x = float(v)
        if x != x or x <= 0:
            return None
        if x > 1e11:
            x /= 1000.0
        try:
            return datetime.fromtimestamp(x, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    t = str(v).strip()
    try:
        if re.fullmatch(r"\d{14}", t):
            dt = datetime.strptime(t, "%Y%m%d%H%M%S")
        elif re.fullmatch(r"\d{12}", t):
            dt = datetime.strptime(t, "%Y%m%d%H%M")
        elif re.fullmatch(r"\d{10}(?:\d{3})?(?:\.\d+)?", t):
            return _instant(float(t), tz)
        else:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def _nombre(v):
    """Un compte lu (int, float, « 161.0 ») → int ; None, booléen, texte, négatif, NaN → None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str):
        t = v.strip().replace(" ", "").replace(" ", "")
        if not re.fullmatch(r"\d+(?:\.\d+)?", t):
            return None
        v = float(t)
    if isinstance(v, (int, float)) and v == v and 0 <= v != float("inf"):
        return int(v)
    return None


def _champ(d: dict, *noms):
    """La première valeur présente (non None) parmi `noms`, en tolérant la casse (VIEWS / views)."""
    if not isinstance(d, dict):
        return None
    bas = {str(k).lower(): v for k, v in d.items()}
    for n in noms:
        v = d.get(n)
        if v is None:
            v = bas.get(n.lower())
        if v is not None:
            return v
    return None


def vues_metricool(post: dict):
    """La règle des vues d'un Reel Instagram lu dans brand-summary, une seule métrique : VIEWS, sinon IMPRESSIONS (le même chiffre
    pour un Reel Instagram dans ce résumé). Absent, illisible ou 0 → None : aucun point, jamais un faux 0."""
    metriques = post.get("metrics") if isinstance(post.get("metrics"), dict) else {}
    for nom in ("VIEWS", "IMPRESSIONS"):
        v = _champ(metriques, nom)
        if v is None:
            v = _champ(post, nom)
        if v is not None:
            n = _nombre(v)
            return n if n else None
    return None


def _lien(post: dict) -> str:
    return str(_champ(post, "link", "url", "permalink", "postUrl") or "").strip()


def _est_instagram(post: dict) -> bool:
    reseau = str(_champ(post, "network", "socialNetwork", "provider") or "").strip().lower()
    return reseau in ("instagram", "ig") or (not reseau and "instagram.com/" in _lien(post).lower())


def _type(post: dict) -> str:
    return str(_champ(post, "postType", "type", "mediaType", "mediaProductType") or "").strip().upper()


def _est_reel(post: dict) -> bool:
    """Un Reel (vidéo) Instagram : type REEL / VIDEO / CLIPS ; sans type, un lien /reel/. Photos, carrousels et stories exclus."""
    ty = _type(post)
    if ty:
        return ty in TYPES_REEL
    return "/reel/" in _lien(post).lower() or "/reels/" in _lien(post).lower()


def code_reel(lien: str) -> str:
    """Le shortcode d'un lien Instagram (…/reel/<code>/ ou …/p/<code>/) — le même que celui d'Apify."""
    m = _RE_CODE.search(str(lien or ""))
    return m.group(1) if m else ""


def _liste(corps) -> list:
    """Le corps d'une réponse : une liste, ou une enveloppe {"data": [...]}. Toute autre forme est illisible (jamais vide par défaut)."""
    if isinstance(corps, list):
        return corps
    if isinstance(corps, dict) and isinstance(corps.get("data"), list):
        return corps["data"]
    raise ErreurMetricool("forme inattendue", "réponse")


def marques_instagram(profils: list) -> tuple:
    """simpleProfiles → ({clé: marque}, [textes des @ partagés]). Une marque = {"id", "nom", "ig", "cle", "tz"} ; seules les
    marques qui ont un Instagram branché ; dédoublonnage par (instagram, compte) : la marque d'id le plus petit lit le compte."""
    out, partages = {}, {}
    def _id(p):
        n = _nombre(p.get("id"))
        return (0, n) if n is not None else (1, str(p.get("id")))
    for p in sorted((p for p in profils or [] if isinstance(p, dict)), key=_id):
        ig = p.get("instagram")
        if not ig and isinstance(p.get("networksData"), dict):
            ig = p["networksData"].get("instagramData")
        if isinstance(ig, dict):
            ig = ig.get("username") or ig.get("name") or ""
        cle = _cle(ig) if ig else ""
        if not cle or p.get("id") in (None, ""):
            continue
        nom = str(p.get("label") or p.get("name") or p.get("id"))
        partages.setdefault(cle, []).append(nom)
        if cle not in out:
            out[cle] = {"id": p.get("id"), "nom": nom, "ig": str(ig), "cle": cle, "tz": p.get("timezone") or ""}
    textes = [f"@{c} partagé par {len(n)} marques ({', '.join(n)}) : lu une fois" for c, n in partages.items() if len(n) > 1]
    return out, textes


def reels_de(publications: list, tz, debut: datetime, fin: datetime) -> tuple:
    """Les publications d'une marque → (reels, par_jour, nb_instagram, illisibles). reels = [{"code", "publie", "vues"}] des Reels
    Instagram publiés dans [début, fin[, triés ; par_jour = {date de Paris: nombre de Reels} ; nb_instagram = publications
    Instagram de la fenêtre (Reels ou non) ; illisibles = Reels Instagram sans shortcode ou sans date (format non compris)."""
    par_code, par_jour, nb_ig, illisibles = {}, {}, 0, 0
    for p in publications or []:
        if not isinstance(p, dict) or not _est_instagram(p):
            continue
        quand = _instant(_champ(p, "publicationDate", "date", "created", "timestamp", "publishedAt"), tz)
        reel = _est_reel(p)
        if quand is None:
            illisibles += int(reel)
            continue
        if not (debut <= quand < fin):
            continue
        nb_ig += 1
        if not reel:
            continue
        code = code_reel(_lien(p))
        if not code:
            illisibles += 1
            continue
        vues = vues_metricool(p)
        if code in par_code:                                             # le même Reel rendu deux fois : la plus grande valeur lue
            a = par_code[code]["vues"]
            par_code[code]["vues"] = max(x for x in (a, vues) if x is not None) if (a, vues) != (None, None) else None
            continue
        par_code[code] = {"code": code, "publie": _iso(quand), "vues": vues}
        j = quand.astimezone(_paris_tz()).date()
        par_jour[j] = par_jour.get(j, 0) + 1
    reels = sorted(par_code.values(), key=lambda r: (r["publie"], r["code"]))
    return reels, par_jour, nb_ig, illisibles


def _connus(cle: str, debut: datetime, fin: datetime) -> set:
    """Les shortcodes des Reels déjà dans la série du compte (toutes sources), publiés dans [début, fin[ ; vide sans series."""
    try:
        import series
        s = series.serie(cle) or {}
    except Exception:                                                    # noqa: BLE001
        return set()
    out = set()
    for code, x in (s.get("reels") or {}).items():
        p = _instant((x or {}).get("publie"), timezone.utc)
        if p is not None and debut <= p < fin:
            out.add(str(code))
    return out


def raison_incomplet(veille: date, reels: list, par_jour: dict, nb_ig: int, illisibles: int, connus: set) -> str:
    """'' si la lecture d'un compte est entière ; sinon pourquoi elle ne l'est pas (le compte est alors « non lu »)."""
    if illisibles:
        return f"{illisibles} Reel(s) Instagram sans lien ou sans date : réponse de Metricool non comprise"
    if not nb_ig:
        return f"aucune publication Instagram en {JOURS} jours (Instagram débranché de Metricool, ou compte à l'arrêt)"
    j1, j2, j3 = veille, veille - timedelta(days=1), veille - timedelta(days=2)
    if not par_jour.get(j1) and par_jour.get(j2) and par_jour.get(j3):
        return "0 Reel la veille alors que les deux jours d'avant en ont : veille pas encore synchronisée"
    manquants = connus - {r["code"] for r in reels}
    if len(manquants) >= MANQUANTS_MIN and len(manquants) >= MANQUANTS_PART * len(connus):
        return f"{len(manquants)} Reels déjà connus sur {len(connus)} absents de Metricool : liste incomplète"
    return ""


# ------------------------------------------------------------------ HTTP (bouchonné dans les tests)
async def _requete(chemin: str, params: dict) -> tuple:
    """(statut HTTP, corps JSON ou None). Seul point de contact avec Metricool ; lecture seule."""
    p = {k: str(v) for k, v in (params or {}).items()}
    if METRICOOL_USER_ID:
        p.setdefault("userId", METRICOOL_USER_ID)
    entetes = {"X-Mc-Auth": METRICOOL_API_KEY, "Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT_S)) as s:
        async with s.get(f"{API_BASE}/{chemin.lstrip('/')}", params=p, headers=entetes) as r:
            corps = await r.json(content_type=None) if r.status == 200 else None
            return r.status, corps


async def _get(chemin: str, params: dict):
    statut, corps = None, None
    for essai in range(2):
        statut, corps = await _requete(chemin, params)
        if statut == 429 and essai == 0:
            journal.warning("Metricool : trop d'appels (429), pause %s s", PAUSE_429_S)
            await asyncio.sleep(PAUSE_429_S)
            continue
        break
    if statut != 200:
        raise ErreurMetricool(statut, chemin)
    return corps


async def _publications(marque: dict, debut: datetime, fin: datetime) -> list:
    """Toutes les publications de la marque sur la fenêtre, un appel par jour (dans le fuseau de la marque, comme le rapport).
    Une seule erreur → exception : le compte n'est pas lu (jamais une fenêtre à trous)."""
    tz = _fuseau(marque.get("tz"))
    d, dern = debut.astimezone(tz).date(), (fin - timedelta(seconds=1)).astimezone(tz).date()
    out = []
    while d <= dern:
        params = {"blogId": str(marque["id"]), "from": f"{d.isoformat()}T00:00:00", "to": f"{d.isoformat()}T23:59:59"}
        out.extend(_liste(await _get(ROUTE_PUBLICATIONS, params)))
        d += timedelta(days=1)
        await asyncio.sleep(PAUSE_S)
    return out


# ------------------------------------------------------------------ contrat C4
async def releves(maintenant=None) -> dict:
    """{"<clé IG>": {"followers": None, "reels": [{"code", "publie", "vues"}], "jour": "AAAA-MM-JJ"}} des comptes Instagram
    branchés à Metricool et lus ENTIERS (données à J-1). Un compte non lu est absent (jamais un faux 0) ; {} sans clé ou en panne.
    Le détail (non lus et pourquoi, erreurs) est dans `bilan()`."""
    global _dernier_bilan
    now = _maintenant_paris(maintenant)
    veille = now.date() - timedelta(days=1)
    debut, fin = fenetre(veille)
    b = {"t": _iso(now), "jour": veille.isoformat(), "marques_ig": 0, "lus": [], "non_lus": {}, "echecs": {}, "partages": [],
         "erreur": ""}
    _dernier_bilan = b
    if not actif():
        b["erreur"] = "inactif (METRICOOL_API_KEY absente ou METRICOOL_COMPTES=0)"
        return {}
    try:
        comptes, b["partages"] = marques_instagram(_liste(await _get(ROUTE_MARQUES, {})))
    except Exception as erreur:                                          # noqa: BLE001
        b["erreur"] = f"marques illisibles ({erreur})"[:200]
        journal.warning("Metricool : %s", b["erreur"])
        return {}
    b["marques_ig"] = len(comptes)
    out = {}
    for cle, m in comptes.items():
        await asyncio.sleep(PAUSE_S)
        try:
            pubs = await _publications(m, debut, fin)
            reels, par_jour, nb_ig, illisibles = reels_de(pubs, _fuseau(m.get("tz")), debut, fin)
            raison = raison_incomplet(veille, reels, par_jour, nb_ig, illisibles, _connus(cle, debut, fin))
        except Exception as erreur:                                      # noqa: BLE001 — un compte en erreur n'arrête pas les autres
            b["echecs"][cle] = str(erreur)[:160] if isinstance(erreur, ErreurMetricool) else \
                f"{type(erreur).__name__} {str(erreur)[:120]}"
            journal.warning("Metricool : @%s (%s) non lu (%s)", cle, m["nom"], b["echecs"][cle])
            continue
        if raison:
            b["non_lus"][cle] = raison
            journal.warning("Metricool : @%s (%s) non lu : %s", cle, m["nom"], raison)
            continue
        out[cle] = {"followers": None, "reels": reels, "jour": veille.isoformat()}
        b["lus"].append(cle)
    if comptes and not out and len(b["echecs"]) == len(comptes):
        b["erreur"] = "aucun compte lu (toutes les lectures en erreur)"
    for t in b["partages"]:
        journal.info("Metricool : %s", t)
    journal.info("Metricool (J-1 = %s) : %d compte(s) Instagram, %d lu(s), %d non lu(s), %d en erreur", b["jour"], len(comptes),
                 len(out), len(b["non_lus"]), len(b["echecs"]))
    return out


def bilan() -> dict:
    """Le détail du dernier `releves()` : jour, marques Instagram, lus, non lus (raison), échecs, @ partagés, erreur."""
    return dict(_dernier_bilan)


# ------------------------------------------------------------------ séries (contrat C1)
def ecrire_series(rels: dict) -> int:
    """Chaque compte lu → un relevé « metricool » dans sa série (series.ajouter_releve), daté de la fin de sa veille (minuit à Paris),
    couvrant la fenêtre lue ; ses Reels avec leurs vues. Renvoie le nombre de relevés écrits."""
    if not rels:
        return 0
    try:
        import series
    except ImportError:
        journal.warning("Metricool : series.py absent, %d relevé(s) non écrit(s)", len(rels))
        return 0
    n = 0
    for cle, r in rels.items():
        try:
            veille = date.fromisoformat(str(r.get("jour")))
        except (TypeError, ValueError):
            continue
        debut, fin = fenetre(veille)
        releve = {"t": _iso(fin), "source": SOURCE, "followers": r.get("followers"), "posts_total": None,
                  "restreint": False, "prive": False, "reels_lus": True, "couvre": _iso(debut)}
        reels = [{"code": x["code"], "publie": x["publie"], "type": "Video", "vues": x.get("vues")} for x in r.get("reels") or []]
        try:
            if series.ajouter_releve(cle, releve, reels, ig_id="") is not False:
                n += 1
        except Exception as erreur:                                      # noqa: BLE001 — un compte abîmé n'empêche pas les autres
            journal.warning("Metricool : série de @%s non écrite (%s)", cle, type(erreur).__name__)
    return n


# ------------------------------------------------------------------ passage, état, boucle
def _lire() -> dict:
    if not (_deps.get("lire_json") and _deps.get("FICHIER")):
        return {}
    d = _deps["lire_json"](_deps["FICHIER"], {})
    return d if isinstance(d, dict) else {}


def _ecrire(d: dict):
    if _deps.get("ecrire_json") and _deps.get("FICHIER"):
        _deps["ecrire_json"](_deps["FICHIER"], d)


def etat() -> dict:
    """Pour le Dashboard (fraîcheur « Metricool J-1 ») : le dernier passage {t, jour, marques_ig, lus, non_lus, echecs, partages,
    hors_classeur, ecrits, erreur} et l'heure du dernier passage réussi (`dernier_ok`)."""
    d = _lire()
    return {**(d.get("dernier") or {}), "dernier_ok": d.get("dernier_ok", "")}


async def _alerter(texte: str, jour: str):
    """Une alerte au salon admin par jour au plus (Metricool en panne, réponse plus comprise)."""
    d = _lire()
    if d.get("alerte") == jour or not callable(_deps.get("canal_admin")):
        return
    try:
        canal = await _deps["canal_admin"]()
        if canal is not None:
            await canal.send(texte[:1990])
            d["alerte"] = jour
            _ecrire(d)
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : alerte admin non envoyée (%s)", type(erreur).__name__)


async def _hors_classeur(cles_ig: set) -> list:
    """Les comptes Instagram branchés à Metricool dont l'@ n'est sur aucune ligne du classeur (dep `lire_comptes`) : leurs séries
    sont écrites, mais aucune ligne du Dashboard ne les montre. [] si le classeur est illisible (jamais une fausse alerte)."""
    if not cles_ig or not callable(_deps.get("lire_comptes")):
        return []
    try:
        cles = {_cle(c.get("handle")) for c in (await _deps["lire_comptes"]() or []) if isinstance(c, dict) and c.get("handle")}
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : classeur illisible pour la correspondance des @ (%s)", type(erreur).__name__)
        return []
    cles.discard("")
    hors = sorted(k for k in cles_ig if cles and k not in cles)
    if hors:
        journal.warning("Metricool : %d compte(s) Instagram branché(s) absent(s) du classeur : %s", len(hors),
                        ", ".join("@" + k for k in hors))
    return hors


async def executer(maintenant=None, ecrire: bool = True) -> dict:
    """Un passage : releves() puis, si `ecrire`, les séries. Renvoie le bilan (avec `ecrits`) et le garde dans l'état."""
    rels = await releves(maintenant)
    b = bilan()
    b["ecrits"] = ecrire_series(rels) if ecrire else 0
    b["hors_classeur"] = await _hors_classeur(set(b.get("lus") or []) | set(b.get("non_lus") or {}) | set(b.get("echecs") or {}))
    d = _lire()
    d["dernier"] = b
    if b["lus"] and not b["erreur"]:
        d["dernier_ok"] = b["t"]
    _ecrire(d)
    format_ko = [c for c, r in b["non_lus"].items() if "non comprise" in r]
    if b["erreur"] and actif():
        await _alerter(f"⚠️ **Metricool** : {b['erreur']}. Les Reels et vues des comptes Instagram branchés ne sont pas relus "
                       f"(rien n'est écrit à 0).", _maintenant_paris(maintenant).date().isoformat())
    elif format_ko:
        await _alerter(f"⚠️ **Metricool** : réponse non comprise pour {len(format_ko)} compte(s) Instagram — format de "
                       f"brand-summary à vérifier. Rien n'est écrit pour eux.", _maintenant_paris(maintenant).date().isoformat())
    return b


async def tour(maintenant=None):
    """Un tour de boucle : un passage si une heure de METRICOOL_HEURES (Paris) est passée et pas encore faite aujourd'hui (après un
    redémarrage, les heures manquées se rattrapent en UN passage). Passage en panne : retenté au tour suivant, ESSAIS_MAX fois."""
    now = _maintenant_paris(maintenant)
    jour = now.date().isoformat()
    d = _lire()
    faits = list((d.get("faits") or {}).get(jour) or [])
    dues = [h for h in HEURES if now.hour >= h and h not in faits]
    if not dues:
        return None
    b = await executer(now)
    d = _lire()                                                          # relu : executer() a écrit le bilan
    essais = d.get("essais") if isinstance(d.get("essais"), dict) and d["essais"].get("jour") == jour else {"jour": jour, "n": 0}
    if b.get("erreur") and essais["n"] + 1 < ESSAIS_MAX:
        essais["n"] += 1
        d["essais"] = essais
        _ecrire(d)
        return b
    faits_j = sorted(set(faits) | set(dues))
    d["faits"] = {k: v for k, v in (d.get("faits") or {}).items() if k >= (now.date() - timedelta(days=3)).isoformat()}
    d["faits"][jour] = faits_j
    d["essais"] = {"jour": jour, "n": 0}
    _ecrire(d)
    return b


async def boucle(client):
    """Deux passages par jour (METRICOOL_HEURES, Paris) : Metricool est à J-1, relu le matin puis l'après-midi pour capter sa synchro."""
    if not actif():
        journal.info("Metricool (comptes) : inactif (METRICOOL_API_KEY absente ou METRICOOL_COMPTES=0)")
        return
    await client.wait_until_ready()
    await asyncio.sleep(DELAI_DEMARRAGE_S)
    while not client.is_closed():
        try:
            await tour()
        except Exception as erreur:                                      # noqa: BLE001
            journal.exception("Metricool (comptes) : %s", erreur)
        await asyncio.sleep(TOUR_S)
