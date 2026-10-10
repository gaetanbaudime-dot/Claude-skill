"""Comptes Instagram branchés à Metricool → séries par compte (09/10, dashboard — Gaëtan : « je dois comprendre quel compte est
en hausse ou en baisse de vues ; le plus précis possible, pas de trucs pas précis, pas de manquements »).

Contrat C4 de la spécification du dashboard :
    await releves() -> {"<clé IG>": {"followers": int | None, "reels": [{"code", "publie", "vues"}], "jour": "AAAA-MM-JJ"}}
pour les comptes Instagram branchés à Metricool. Metricool passe par l'API officielle d'Instagram : lisible même pour un compte
restreint, sans scraping (la voie propre au regard des CGU, contrairement à Apify). `boucle(client)` le relit deux fois par jour
(METRICOOL_HEURES, heures de Paris, défaut « 8,15 ») et écrit les comptes lus dans les séries en UNE écriture par passage
(series.ajouter_releves, contrats C1 et C6c, source « metricool »).
Contrat C6(b) : `etat()` = {"jour": J-1 des données du dernier passage RÉUSSI ou "", "dernier_ok": iso de ce passage ou "",
"jour_essai": J-1 du dernier essai, "erreur": erreur du dernier essai, "lus": comptes lus au dernier passage réussi}.

Routes REST : UNIQUEMENT celles déjà utilisées dans le dépôt, aucune inventée (base https://app.metricool.com/api, en-tête
X-Mc-Auth = METRICOOL_API_KEY, userId = METRICOOL_USER_ID s'il est posé) :
  - GET /admin/simpleProfiles (tools/mcp_metricool/metricool_mcp.py, rapport_quotidien.metricool) → les marques, l'@ Instagram
    branché (champ `instagram`) ;
  - GET /v2/analytics/brand-summary/posts?blogId=&from=AAAA-MM-JJT00:00:00&to=AAAA-MM-JJT23:59:59 (rapport_quotidien.metricool),
    un appel par marque et par JOUR comme le rapport → les publications de la marque, tous réseaux ; on ne garde que les Reels
    Instagram (réseau INSTAGRAM…, type REEL, lien instagram.com/reel/<shortcode>/).
    (/v2/analytics/posts/instagram, l'autre route connue, ne rend PAS les Reels : vérifié le 09/10 en lecture par le connecteur
    Metricool, Instagram Posts vide pour une marque qui publie 5 Reels par jour.)

Ce que le module NE sait PAS lire (laissé à None, jamais 0) :
  - followers : 09/10 (correctif) — la métrique existe chez Metricool (IGEV01 « Instagram Evolution > Followers », agrégation
    LAST, confirmée en lecture par le connecteur Metricool, getAnalyticsAvailableMetrics). Mais AUCUNE route REST du dépôt ne la
    lit : tools/mcp_metricool/metricool_mcp.py n'utilise que admin/simpleProfiles et v2/analytics/posts/<réseau>,
    rapport_quotidien que brand-summary/posts. La spec interdit d'inventer une route : `followers` reste None et Apify reste la
    source des followers, jusqu'à ce qu'une route REST des followers soit utilisée (et vérifiée) dans le dépôt ;
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
    Une valeur absente ou illisible = pas de point. 09/10 (correctif) : un 0 n'est « pas encore relevé » (pas de point) que pour
    un Reel publié moins de 24 h avant la fin de la fenêtre ; plus vieux, c'est un VRAI 0 de l'API officielle (Reel bloqué,
    compte shadowban), gardé comme le fait Apify (series.vues_post). 10/10 (revue) : seulement si la métrique est prouvée
    remplie, au moins un Reel du passage (tous comptes) avec des vues positives ; sinon (métrique cassée qui renvoie 0 partout)
    les 0 deviennent None (non mesuré) et l'alerte « vues » part ;
  - une seule source par Reel pour les vues (09/10, correctif) : Metricool n'ajoute pas de point à un Reel qu'Apify suit encore
    (un point Apify dans les 24 h qui précèdent la photo de Metricool) — les deux outils ne mesurent pas forcément la même chose
    (VIEWS contre videoPlayCount) et la photo de Metricool est datée à quelques heures près ; et le passage de 15 h ne remplace
    pas les vues déjà notées à 8 h pour la même veille (la lecture la plus proche de l'heure du relevé est gardée) ;
  - un compte n'est écrit avec sa couverture (ses Reels comptés) que s'il est lu ENTIER, sinon « non lu » (rien d'écrit, jamais
    un 0 ; seule exception, sans couverture : le compte « partiel » ci-dessous) :
      · un jour en erreur → non lu (aucune fenêtre à trous) ; un Reel sans lien ou sans date → format non compris ;
      · aucune publication Instagram sur la fenêtre → non lu (Instagram débranché de Metricool, ou compte à l'arrêt) ;
      · 09/10 (correctif) : les derniers jours de la fenêtre SANS REEL ne sont jamais revendiqués comme « 0 Reel » sur la seule
        foi de Metricool : veille pas encore synchronisée, compte en pause ou Instagram débranché (jeton expiré) se ressemblent.
        10/10 (revue) : l'horizon se lit sur les seuls Reels — une story (relevée à part, dans la journée) ou une photo publiée
        par le planificateur de Metricool ne prouve pas que les Reels de la veille sont synchronisés. Ces jours sont « 0 Reel »
        seulement si un relevé Apify lisible (ni restreint, ni privé, Reels lus) les couvre et n'y voit aucun Reel ;
      · 10/10 (revue) : sinon, le compte n'est pas jeté pour autant si sa synchro est prouvée VIVANTE — au moins un Reel dont les
        vues ont bougé depuis la lecture Metricool d'une veille plus tôt (gardée dans l'état, `photos`) ; un Instagram débranché
        fige les métriques. Il est écrit « partiel » : relevé SANS couverture (reels_lus=False, pas de `couvre` : aucun « 0 Reel »
        possible), ses Reels et leurs vues (un compte restreint, ou tous quand Apify est coupé, reste mesuré à 48 h). Synchro
        pas prouvée (vues figées, ou pas de lecture précédente) : non lu, rien d'écrit ;
      · « débranché ? » au salon admin (10/10, revue : au DERNIER passage du jour seulement, Apify a eu le temps de confirmer) :
        rien depuis 2 jours ou plus, non confirmé par Apify, vues figées ; et un compte que Metricool lisait (relevés metricool
        dans la série, ou lecture gardée) qui n'a plus AUCUNE publication sur la fenêtre, si Apify ne confirme pas la pause ;
      · 09/10 (correctif) : liste incomplète = au moins 2 Reels (et le quart des vérifiables) qu'Apify a vus VIVANTS après la photo
        de Metricool (un point de vues après la fin de la fenêtre) absents de la réponse. Un Reel supprimé par le clipper (pratique
        courante : on retire ceux qui floppent) n'est plus pris pour un manque : il n'a plus de point après sa suppression ;
  - un même @ porté par plusieurs marques : lu par la première marque (ordre des id) qui le lit entier ; si elle est en erreur
    ou le rend non lu, la suivante est essayée (09/10, correctif) ;
  - correspondance marque → @ Instagram → clé du classeur : la clé est celle du scan (etats_comptes._cle =
    onboarding.normaliser_handle en minuscules) ; un @ renommé est suivi par les alias de series.
Pannes jamais silencieuses (09/10, correctif) : une alerte au salon admin par jour et par motif (Metricool en panne, réponse non
comprise, aucun compte lu, aucune vue lisible — absentes ou toutes à 0, 10/10 —, comptes « débranchés ? »). Deux 429 de suite
arrêtent tout le passage (nouvel essai au tour suivant). Un passage qui lève une exception compte comme un essai raté (ESSAIS_MAX
par heure de passage), même si l'état ne peut pas être écrit sur le disque (compteurs gardés en mémoire).

Dépendances (`configurer`, toutes facultatives) : lire_json, ecrire_json, FICHIER (état : passages faits, essais, alertes, dernier
essai, dernier passage réussi, dernière lecture des vues par compte), FICHIER_SERIES (series n'est configuré ici que s'il ne
l'est pas déjà — c'est le scan qui le configure normalement), heure_paris, canal_admin, cle (fonction @ → clé), lire_comptes
(le classeur : les comptes Metricool dont l'@ n'est sur aucune ligne sont listés au bilan, `hors_classeur`).
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
PAUSE_429_S = 60                                 # « trop d'appels » : une minute, puis un seul nouvel essai ; deux 429 : passage arrêté
TIMEOUT_S = 60
DELAI_DEMARRAGE_S = 120
TOUR_S = 600                                     # la boucle regarde l'heure toutes les 10 min
ESSAIS_MAX = 3                                   # passage en panne : retenté au tour suivant, 3 fois au plus par heure de passage
TYPES_REEL = {"REEL", "REELS", "CLIPS", "VIDEO"}
MANQUANTS_MIN = 2                                # liste incomplète : au moins 2 Reels vus vivants par Apify absents…
MANQUANTS_PART = 0.25                            # … et au moins le quart des Reels vérifiables de la fenêtre
AGE_VRAI_ZERO_H = 24                             # 0 vue d'un Reel publié au moins 24 h avant la fin de la fenêtre : un vrai 0
SUIVI_APIFY_H = 24                               # un point Apify dans les 24 h avant la photo Metricool : Apify suit le Reel
MEME_REEL_S = 120                                # deux codes, publiés à 2 minutes près = le même Reel (comme series)
DEBRANCHE_J = 2                                  # rien depuis 2 jours ou plus, non confirmé : « débranché ? » au salon admin
VUES_ALERTE_MIN = 3                              # au moins 3 Reels de plus de 24 h lus sans aucune vue : alerte « vues illisibles »
PHOTOS_J = 12                                    # dernière lecture des vues d'un compte gardée 12 jours (synchro vivante ?)
# 10/10 (revue) : début des raisons qui comptent pour « veille pas synchronisée / pause / débranché » et « aucune publication »
PREFIXE_SYNC = "aucun Reel de Metricool"
PREFIXE_AUCUNE = "aucune publication Instagram"
# réseaux connus qui ne sont pas Instagram (un réseau inconnu avec un lien instagram.com est pris pour Instagram)
RESEAUX_AUTRES = {"facebook", "fb", "tiktok", "youtube", "yt", "twitter", "x", "linkedin", "pinterest", "threads", "bluesky",
                  "twitch", "gmb", "googlebusinessprofile", "google", "website", "smartlinks"}

_RE_CODE = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
_PARIS = None
_dernier_bilan: dict = {}
_format_journalise = {"fait": False}
# 09/10 (correctif) : compteurs gardés aussi en mémoire — un état illisible ou impossible à écrire (disque plein) ne doit pas
# faire repartir un passage complet toutes les 10 min, ni répéter une alerte à chaque passage
_memoire: dict = {"faits": {}, "essais": {}, "alertes": {}, "photos": {}}
# 10/10 (revue) : ce que le dernier releves() a lu en plus des comptes entiers (C4) — comptes « partiels » (synchro vivante, Reels
# non comptés) et lecture des vues de chaque compte (gardée dans l'état par executer, pour la comparer le lendemain)
_passage: dict = {"partiels": {}, "photos": {}, "fin": ""}


class ErreurMetricool(Exception):
    """Réponse HTTP autre que 200 (ou forme illisible) : la donnée n'est pas lue, jamais remplacée par 0."""

    def __init__(self, statut, chemin: str = ""):
        super().__init__(f"Metricool {statut} sur {chemin}")
        self.statut = statut


def configurer(deps: dict):
    if "FICHIER" in (deps or {}) and str(deps.get("FICHIER")) != str(_deps.get("FICHIER")):
        _memoire.update(faits={}, essais={}, alertes={}, photos={})      # un autre fichier d'état : la mémoire repart de zéro
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


def _minuit(jour: date) -> datetime:
    return datetime.combine(jour, dtime(0), tzinfo=_paris_tz())


def _instant(v, tz=None):
    """Une date de publication Metricool → instant avec fuseau, ou None. Formes acceptées : {"dateTime", "timezone"} (forme des
    dates de Metricool), ISO avec ou sans fuseau (sans fuseau = fuseau de la marque), « AAAAMMJJHHMMSS », secondes ou
    millisecondes depuis 1970."""
    tz = tz or _paris_tz()
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=tz)
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
        t = v.strip().replace(" ", "").replace(" ", "")
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


def vues_metricool(post: dict, publie=None, fin=None):
    """La règle des vues d'un Reel Instagram lu dans brand-summary, une seule métrique : VIEWS, sinon IMPRESSIONS (le même chiffre
    pour un Reel Instagram dans ce résumé). Absent ou illisible → None (aucun point). 09/10 (correctif) : un 0 est un VRAI 0
    (gardé) quand le Reel a été publié au moins AGE_VRAI_ZERO_H heures avant `fin` (déjà passé par une synchro de nuit
    complète) ; sinon (Reel de la veille, ou âge inconnu) c'est un chiffre pas encore relevé → None. Un VIEWS à 0 avec des
    IMPRESSIONS positives : IMPRESSIONS (VIEWS pas rempli, jamais un faux 0)."""
    metriques = post.get("metrics") if isinstance(post.get("metrics"), dict) else {}
    lus = []
    for nom in ("VIEWS", "IMPRESSIONS"):
        v = _champ(metriques, nom)
        if v is None:
            v = _champ(post, nom)
        if v is not None:
            lus.append(_nombre(v))
    if not lus or lus[0] is None:
        return None
    if lus[0] > 0:
        return lus[0]
    if len(lus) > 1 and lus[1]:
        return lus[1]                                                    # VIEWS à 0 mais IMPRESSIONS lues : VIEWS pas rempli
    p, f = _instant(publie, timezone.utc), _instant(fin, timezone.utc)
    if p is not None and f is not None and f - p >= timedelta(hours=AGE_VRAI_ZERO_H):
        return 0
    return None


def _lien(post: dict) -> str:
    return str(_champ(post, "link", "url", "permalink", "postUrl") or "").strip()


def _reseau(post: dict) -> str:
    return str(_champ(post, "network", "socialNetwork", "provider") or "").strip().lower()


def _est_instagram(post: dict) -> bool:
    """09/10 (correctif) : INSTAGRAM, INSTAGRAM_BUSINESS, IG… (le nom exact du champ n'est confirmé par aucun code du dépôt) ;
    réseau absent ou inconnu → un lien instagram.com décide."""
    r = _reseau(post)
    if r.startswith("instagram") or r == "ig" or r.startswith("ig_"):
        return True
    if r and re.split(r"[^a-z]", r)[0] in RESEAUX_AUTRES:
        return False
    return "instagram.com/" in _lien(post).lower()


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
    """simpleProfiles → ({clé: marque}, [textes des @ partagés]). Une marque = {"id", "nom", "ig", "cle", "tz", "autres"} ; seules
    les marques qui ont un Instagram branché ; une clé = un compte Instagram, lu par la marque d'id le plus petit, puis (si elle
    échoue ou le rend non lu) par les suivantes (`autres`, même forme, ordre des id)."""
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
        m = {"id": p.get("id"), "nom": nom, "ig": str(ig), "cle": cle, "tz": p.get("timezone") or ""}
        if cle not in out:
            out[cle] = {**m, "autres": []}
        else:
            out[cle]["autres"].append(m)
    textes = [f"@{c} partagé par {len(n)} marques ({', '.join(n)}) : lu une fois, par la première qui le lit entier"
              for c, n in partages.items() if len(n) > 1]
    return out, textes


def reels_de(publications: list, tz, debut: datetime, fin: datetime) -> tuple:
    """Les publications d'une marque → (reels, par_jour, ig_jours, illisibles). reels = [{"code", "publie", "vues"}] des Reels
    Instagram publiés dans [début, fin[, triés ; par_jour = {date de Paris: nombre de Reels} ; ig_jours = {date de Paris: nombre
    de publications Instagram, tous types} ; illisibles = Reels Instagram sans shortcode ou sans date (format non compris)."""
    par_code, par_jour, ig_jours, illisibles = {}, {}, {}, 0
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
        j = quand.astimezone(_paris_tz()).date()
        ig_jours[j] = ig_jours.get(j, 0) + 1
        if not reel:
            continue
        code = code_reel(_lien(p))
        if not code:
            illisibles += 1
            continue
        vues = vues_metricool(p, quand, fin)
        if code in par_code:                                             # le même Reel rendu deux fois : la plus grande valeur lue
            a = par_code[code]["vues"]
            par_code[code]["vues"] = max(x for x in (a, vues) if x is not None) if (a, vues) != (None, None) else None
            continue
        par_code[code] = {"code": code, "publie": _iso(quand), "vues": vues}
        par_jour[j] = par_jour.get(j, 0) + 1
    reels = sorted(par_code.values(), key=lambda r: (r["publie"], r["code"]))
    return reels, par_jour, ig_jours, illisibles


# ------------------------------------------------------------------ ce que la série sait déjà (Apify)
def _serie(cle: str) -> dict:
    """La série du compte (copie, alias suivis) ; {} sans series."""
    try:
        import series
        s = series.serie(cle)
    except Exception:                                                    # noqa: BLE001
        return {}
    return s if isinstance(s, dict) else {}


def _points(x: dict) -> list:
    """Les points de vues d'un Reel de la série : [(instant, vues)] lisibles."""
    out = []
    for pt in (x or {}).get("vues") or []:
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            t = _instant(pt[0], timezone.utc)
            if t is not None:
                out.append((t, pt[1]))
    return out


def _point_metricool(t: datetime) -> bool:
    """Un point posé par Metricool est daté de minuit pile à Paris (fin d'une veille) ; les relevés Apify, de l'heure du scan."""
    p = t.astimezone(_paris_tz())
    return (p.hour, p.minute, p.second, p.microsecond) == (0, 0, 0, 0)


def _lisible_apify(r: dict) -> bool:
    """Un relevé d'une autre source que Metricool qui voit les Reels du compte (ni restreint, ni privé, Reels lus)."""
    return isinstance(r, dict) and str(r.get("source") or "apify") != SOURCE and not r.get("restreint") \
        and not r.get("prive") and r.get("reels_lus", True) is not False


def _intervalle(r: dict):
    """[début, fin] des publications qu'un relevé voit toutes (contrat C1 : `couvre` absent = les 48 h avant le relevé, "" = tout
    l'historique, une date = depuis cette date)."""
    t = _instant(r.get("t"), timezone.utc)
    if t is None:
        return None
    if "couvre" not in r:
        return t - timedelta(hours=48), t
    if r.get("couvre") == "":
        return datetime(2000, 1, 1, tzinfo=timezone.utc), t
    c = _instant(r.get("couvre"), timezone.utc)
    return (min(c, t), t) if c is not None else (t, t)


def confirme_par_apify(serie: dict, debut: datetime, fin: datetime) -> str:
    """'' si des relevés Apify lisibles couvrent [début, fin] sans y voir aucun Reel (la période est bien vide) ; sinon pourquoi
    ce n'est pas confirmé. Les relevés Metricool ne comptent jamais (ils ne se confirmeraient qu'eux-mêmes)."""
    ints = sorted(i for i in (_intervalle(r) for r in (serie or {}).get("releves") or [] if _lisible_apify(r)) if i)
    cur = debut
    for a, b in ints:
        if b < cur:
            continue
        if a > cur:
            break
        cur = max(cur, b)
        if cur >= fin:
            break
    if cur < fin:
        return "Apify ne couvre pas ces jours"
    vus = [c for c, x in ((serie or {}).get("reels") or {}).items()
           if (p := _instant((x or {}).get("publie"), timezone.utc)) is not None and debut <= p < fin]
    if vus:
        return f"la série connaît {len(vus)} Reel(s) publié(s) ces jours-là, absent(s) de Metricool"
    return ""


def _meme(publie: datetime, autres: list) -> bool:
    return any(abs((publie - q).total_seconds()) <= MEME_REEL_S for q in autres)


def manquants(serie: dict, reels: list, debut: datetime, fin: datetime) -> tuple:
    """(manquants, vérifiables) : les Reels de la série publiés dans [début, fin[ qu'une autre source (Apify) a vus VIVANTS après
    la photo de Metricool (un point de vues après `fin`, jamais posé par Metricool), et, parmi eux, ceux que Metricool ne rend pas
    (ni sous le même code, ni publiés à 2 minutes près). Un Reel supprimé n'a plus de point après sa suppression : jamais compté."""
    codes = {r["code"] for r in reels}
    instants = [p for p in (_instant(r.get("publie"), timezone.utc) for r in reels) if p is not None]
    miss, verif = [], 0
    for code, x in ((serie or {}).get("reels") or {}).items():
        p = _instant((x or {}).get("publie"), timezone.utc)
        if p is None or not (debut <= p < fin):
            continue
        if not any(t > fin and not _point_metricool(t) for t, _ in _points(x)):
            continue
        verif += 1
        autres_codes = {str(c) for c in (x or {}).get("codes") or []}           # le même Reel vu sous plusieurs codes (series)
        if str(code) not in codes and not (autres_codes & codes) and not _meme(p, instants):
            miss.append(str(code))
    return miss, verif


def raison_incomplet(veille: date, reels: list, ig_jours: dict, illisibles: int, serie: dict = None,
                     debut: datetime = None, fin: datetime = None) -> str:
    """'' si la lecture d'un compte est entière ; sinon pourquoi elle ne l'est pas (le compte est alors « non lu », ou « partiel »
    si la raison commence par PREFIXE_SYNC et que sa synchro est vivante, voir _lire_compte).
    ig_jours = {jour de Paris: publications Instagram de tous types} (reels_de) ; serie = la série du compte (series.serie).
    10/10 (revue) : les jours sans Reel en fin de fenêtre se lisent sur les seuls REELS (`reels`), plus sur ig_jours : une story
    de la veille (relevée à part, dans la journée) ou une photo publiée par le planificateur ne prouve pas que les Reels de la
    veille sont synchronisés. Aucun Reel sur toute la fenêtre : toute la fenêtre doit être confirmée par Apify."""
    if debut is None or fin is None:
        debut, fin = fenetre(veille)
    if illisibles:
        return f"{illisibles} Reel(s) Instagram sans lien ou sans date : réponse de Metricool non comprise"
    if not ig_jours:
        return f"{PREFIXE_AUCUNE} en {JOURS} jours (Instagram débranché de Metricool, ou compte à l'arrêt)"
    jours_reels = {p.astimezone(_paris_tz()).date() for p in (_instant(r.get("publie"), timezone.utc) for r in reels or []
                                                               if isinstance(r, dict)) if p is not None}
    horizon = max(jours_reels) if jours_reels else None
    if horizon is None or horizon < veille:                              # jours sans Reel en fin de fenêtre
        depuis = _minuit(horizon + timedelta(days=1)) if horizon is not None else debut
        pourquoi = confirme_par_apify(serie or {}, depuis, fin)
        if pourquoi:
            quand = f"depuis le {horizon:%d/%m}" if horizon is not None else f"en {JOURS} jours"
            return (f"{PREFIXE_SYNC} {quand} (veille pas encore synchronisée, compte en pause, ou Instagram débranché de "
                    f"Metricool) et {pourquoi}")
    miss, verif = manquants(serie or {}, reels, debut, fin)
    if len(miss) >= MANQUANTS_MIN and len(miss) >= MANQUANTS_PART * verif:
        return f"{len(miss)} Reels vus vivants par Apify sur {verif} absents de Metricool : liste incomplète"
    return ""


# ------------------------------------------------------------------ synchro vivante (10/10, revue)
def vues_photo(reels: list) -> dict:
    """La lecture des vues d'un compte : {code: vues} des Reels dont les vues sont lues (None exclus)."""
    out = {}
    for r in reels or []:
        v = _nombre((r or {}).get("vues")) if isinstance(r, dict) else None
        if v is not None and r.get("code"):
            out[str(r["code"])] = v
    return out


def _precedente(photo, fin_iso: str):
    """La lecture gardée d'un compte faite pour une veille PLUS TÔT que la photo `fin_iso` : {"fin", "vues"} ou None. Les deux
    passages d'un même jour ont la même photo : le second compare à la lecture d'avant (`prec`), jamais au passage de 8 h."""
    if not isinstance(photo, dict):
        return None
    f, g = _instant(photo.get("fin"), timezone.utc), _instant(fin_iso, timezone.utc)
    if f is None or g is None:
        return None
    if f < g:
        return {"fin": str(photo.get("fin")), "vues": dict(photo.get("vues") or {})}
    if f == g and isinstance(photo.get("prec"), dict):
        return photo["prec"]
    return None


def sync_vivante(reels: list, fin: datetime, photo) -> "bool | None":
    """La synchro Instagram → Metricool du compte est-elle vivante ? True : au moins un Reel dont les vues ont BOUGÉ depuis la
    lecture d'une veille plus tôt (un Instagram débranché fige les métriques) ; False : rien n'a bougé ; None : aucune lecture
    précédente à comparer (on ne sait pas)."""
    prec = _precedente(photo, _iso(fin))
    if prec is None:
        return None
    avant = prec.get("vues") if isinstance(prec.get("vues"), dict) else {}
    for code, v in vues_photo(reels).items():
        a = _nombre(avant.get(code))
        if a is not None and a != v:
            return True
    return False


def photo_maj(ancienne, fin_iso: str, vues: dict) -> dict:
    """La lecture gardée d'un compte après un passage dont la photo est `fin_iso` : {"fin", "vues", "prec"} (prec = la lecture
    d'une veille plus tôt, une seule : la profondeur reste bornée). Une lecture gardée plus récente n'est jamais remplacée."""
    f = _instant(ancienne.get("fin"), timezone.utc) if isinstance(ancienne, dict) else None
    g = _instant(fin_iso, timezone.utc)
    if f is not None and g is not None and f > g:
        return ancienne
    return {"fin": fin_iso, "vues": dict(vues or {}), "prec": _precedente(ancienne, fin_iso)}


def _lu_avant(serie: dict, photo) -> bool:
    """Metricool lisait déjà ce compte : un relevé metricool dans la série, ou une lecture gardée."""
    return isinstance(photo, dict) or any(isinstance(r, dict) and r.get("source") == SOURCE
                                          for r in (serie or {}).get("releves") or [])


def _derniere_publication(serie: dict) -> str:
    """Le jour (Paris, AAAA-MM-JJ) du dernier Reel que Metricool a rendu pour ce compte d'après la série ; '' si inconnu."""
    ts = [p for x in ((serie or {}).get("reels") or {}).values() if isinstance(x, dict) and SOURCE in (x.get("sources") or [])
          for p in [_instant(x.get("publie"), timezone.utc)] if p is not None]
    return max(ts).astimezone(_paris_tz()).date().isoformat() if ts else ""


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


def _journaliser_format(publications: list):
    """09/10 (correctif) : une fois par démarrage, les CLÉS (jamais les valeurs) d'une publication brute de brand-summary et de
    ses métriques, pour confirmer sur une vraie réponse les noms de champs que le code suppose."""
    if _format_journalise["fait"]:
        return
    pubs = [p for p in publications or [] if isinstance(p, dict)]
    for p in sorted(pubs, key=lambda p: not _est_instagram(p)):         # une publication Instagram d'abord, s'il y en a
        if isinstance(p, dict):
            m = p.get("metrics") if isinstance(p.get("metrics"), dict) else {}
            journal.info("Metricool : format de brand-summary — clés %s ; métriques %s ; réseau %r ; type %r",
                         sorted(map(str, p)), sorted(map(str, m)), _reseau(p), _type(p))
            _format_journalise["fait"] = True
            return


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
def _texte_erreur(erreur: Exception) -> str:
    return str(erreur)[:160] if isinstance(erreur, ErreurMetricool) else f"{type(erreur).__name__} {str(erreur)[:120]}"


async def _lire_compte(cle: str, m: dict, veille: date, debut: datetime, fin: datetime, b: dict, photos: dict = None):
    """Un compte Instagram : ses marques l'une après l'autre jusqu'à une lecture entière. Renvoie (reels, True) si lu entier,
    (reels, False) s'il est « partiel » (10/10, revue : jours sans Reel non confirmés mais synchro vivante — vues écrites, Reels
    non comptés), ou None (le bilan dit pourquoi : non_lus, echecs, debranches). Deux 429 de suite → ErreurMetricool(429)
    remonte : le passage s'arrête. `photos` = lectures gardées ({clé: {"fin", "vues", "prec"}}) ; la lecture de ce passage est
    notée dans _passage["photos"]."""
    marques = [m] + list(m.get("autres") or [])
    serie = _serie(cle)
    photo = (photos or {}).get(cle)
    raisons, erreurs, partiel, debranche = [], [], None, None
    for mq in marques:
        await asyncio.sleep(PAUSE_S)
        try:
            pubs = await _publications(mq, debut, fin)
            _journaliser_format(pubs)
            reels, _par_jour, ig_jours, illisibles = reels_de(pubs, _fuseau(mq.get("tz")), debut, fin)
            raison = raison_incomplet(veille, reels, ig_jours, illisibles, serie, debut, fin)
        except ErreurMetricool as erreur:
            if erreur.statut == 429:
                raise
            erreurs.append(_texte_erreur(erreur))
            journal.warning("Metricool : @%s (%s) non lu (%s)", cle, mq["nom"], erreurs[-1])
            continue
        except Exception as erreur:                                      # noqa: BLE001 — un compte en erreur n'arrête pas les autres
            erreurs.append(_texte_erreur(erreur))
            journal.warning("Metricool : @%s (%s) non lu (%s)", cle, mq["nom"], erreurs[-1])
            continue
        if reels and not illisibles and cle not in _passage["photos"]:
            _passage["photos"][cle] = vues_photo(reels)                 # la première lecture comprise (remplacée par la retenue)
        if not raison:
            if mq is not m:
                journal.info("Metricool : @%s lu par la marque %s (la première ne le lisait pas)", cle, mq["nom"])
            _passage["photos"][cle] = vues_photo(reels)
            b["debranches"].pop(cle, None)
            return reels, True
        raisons.append(raison)
        journal.warning("Metricool : @%s (%s) non lu : %s", cle, mq["nom"], raison)
        if raison.startswith(PREFIXE_SYNC):
            # 10/10 (revue) : jours sans Reel non confirmés. Vues qui bougent → synchro vivante : écrit sans couverture (partiel),
            # jamais « débranché ? ». Vues figées ou pas de lecture d'avant → non lu ; rien depuis 2 jours ou plus → listé
            if sync_vivante(reels, fin, photo):
                if partiel is None:
                    partiel = (reels, raison)
                    _passage["photos"][cle] = vues_photo(reels)
            elif debranche is None and (veille - max(ig_jours)).days >= DEBRANCHE_J:
                debranche = max(ig_jours).isoformat()
        elif raison.startswith(PREFIXE_AUCUNE) and debranche is None and _lu_avant(serie, photo) \
                and confirme_par_apify(serie, debut, fin):
            # 10/10 (revue) : plus AUCUNE publication sur la fenêtre, mais Metricool le lisait : un vrai débranchement ne sort
            # plus des alertes au bout de JOURS jours (sauf si Apify confirme la pause)
            debranche = _derniere_publication(serie)
    if partiel is not None:
        b["non_lus"][cle] = partiel[1] + " ; synchro vivante (vues qui bougent) : vues écrites, Reels non comptés"
        b["partiels"].append(cle)
        b["debranches"].pop(cle, None)
        return partiel[0], False
    if raisons:
        b["non_lus"][cle] = raisons[0] + (f" ({len(marques)} marques essayées)" if len(marques) > 1 else "")
        if debranche is not None and not erreurs:                        # une autre marque en erreur : on ne sait pas
            b["debranches"].setdefault(cle, debranche)
    else:
        b["echecs"][cle] = erreurs[0] if erreurs else "aucune marque lue"
    return None


async def releves(maintenant=None) -> dict:
    """{"<clé IG>": {"followers": None, "reels": [{"code", "publie", "vues"}], "jour": "AAAA-MM-JJ"}} des comptes Instagram
    branchés à Metricool et lus ENTIERS (données à J-1). Un compte non lu est absent (jamais un faux 0) ; {} sans clé ou en panne.
    Le détail (non lus et pourquoi, erreurs, débranchés ?, partiels) est dans `bilan()` ; les comptes « partiels » (synchro
    vivante, Reels non comptés, 10/10) dans `partiels()`, même forme que C4. 10/10 (revue) : aucun Reel du passage (tous comptes)
    avec des vues positives → la métrique n'est pas prouvée remplie, ses 0 deviennent None (bilan : `zeros_ignores`)."""
    global _dernier_bilan
    now = _maintenant_paris(maintenant)
    veille = now.date() - timedelta(days=1)
    debut, fin = fenetre(veille)
    b = {"t": _iso(now), "jour": veille.isoformat(), "marques_ig": 0, "lus": [], "non_lus": {}, "echecs": {}, "partages": [],
         "debranches": {}, "partiels": [], "zeros_ignores": 0, "erreur": ""}
    _dernier_bilan = b
    _passage.update(partiels={}, photos={}, fin=_iso(fin))
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
    photos = _photos()
    out = {}
    for cle, m in comptes.items():
        try:
            lu = await _lire_compte(cle, m, veille, debut, fin, b, photos)
        except ErreurMetricool as erreur:                                # deux 429 de suite : on s'arrête là (09/10, correctif)
            b["erreur"] = (f"trop d'appels (429 deux fois de suite) : passage arrêté à @{cle}, "
                           f"{len(comptes) - len(out) - len(b['non_lus']) - len(b['echecs'])} compte(s) pas relu(s), "
                           f"nouvel essai au tour suivant")
            journal.warning("Metricool : %s (%s)", b["erreur"], erreur)
            break
        if lu is None:
            continue
        reels, entier = lu
        if entier:
            out[cle] = {"followers": None, "reels": reels, "jour": veille.isoformat()}
            b["lus"].append(cle)
        else:
            _passage["partiels"][cle] = {"followers": None, "reels": reels, "jour": veille.isoformat()}
    # 10/10 (revue) : un 0 n'est un vrai 0 que si la métrique est prouvée remplie dans ce passage (au moins un Reel, tous comptes,
    # avec des vues positives) ; sinon (métrique dépréciée, 0 de remplissage) les 0 deviennent None — jamais un shadowban de masse
    tous = [x for lot in (out, _passage["partiels"]) for r in lot.values() for x in r["reels"]]
    if not any((_nombre(x.get("vues")) or 0) > 0 for x in tous):
        for x in tous:
            if x.get("vues") == 0:
                x["vues"] = None
                b["zeros_ignores"] += 1
        if b["zeros_ignores"]:
            journal.warning("Metricool : aucune vue positive dans le passage, %d vue(s) à 0 non écrite(s)", b["zeros_ignores"])
    if comptes and not out and not b["erreur"] and len(b["echecs"]) == len(comptes):
        b["erreur"] = "aucun compte lu (toutes les lectures en erreur)"
    for t in b["partages"]:
        journal.info("Metricool : %s", t)
    journal.info("Metricool (J-1 = %s) : %d compte(s) Instagram, %d lu(s), %d non lu(s) dont %d partiel(s), %d en erreur",
                 b["jour"], len(comptes), len(out), len(b["non_lus"]), len(b["partiels"]), len(b["echecs"]))
    return out


def partiels() -> dict:
    """10/10 (revue) : les comptes « partiels » du dernier `releves()` (même forme que C4) — jours sans Reel non confirmés mais
    synchro vivante : leurs vues sont écrites, leurs Reels jamais comptés (relevé sans couverture)."""
    return {k: {**v, "reels": [dict(x) for x in v["reels"]]} for k, v in _passage["partiels"].items()}


def bilan() -> dict:
    """Le détail du dernier `releves()` : jour, marques Instagram, lus, non lus (raison), échecs, débranchés ? (candidats,
    signalés au dernier passage du jour), partiels (parmi les non lus, vues écrites sans couverture), zeros_ignores, @ partagés,
    erreur."""
    return dict(_dernier_bilan)


# ------------------------------------------------------------------ séries (contrats C1 et C6c)
def _reel_de_serie(serie: dict, code: str, publie):
    """L'entrée de la série pour un Reel de Metricool : même code, sinon publiée à 2 minutes près (comme series)."""
    reels = (serie or {}).get("reels") or {}
    if code in reels:
        return reels[code]
    for x in reels.values():                                             # code déjà rattaché à un Reel vu sous un autre code
        if code in ((x or {}).get("codes") or []):
            return x
    p = _instant(publie, timezone.utc)
    if p is None:
        return None
    for x in reels.values():
        q = _instant((x or {}).get("publie"), timezone.utc)
        if q is not None and abs((p - q).total_seconds()) <= MEME_REEL_S:
            return x
    return None


def _vues_a_ecrire(serie: dict, x: dict, fin: datetime):
    """Les vues Metricool d'un Reel à écrire dans la série, ou None (aucun point) : une seule source par Reel — pas de point si
    Apify le suit encore (un de ses points dans les SUIVI_APIFY_H heures avant la photo, ou après) ; et pas de remplacement des
    vues déjà notées pour cette même photo (passage de 8 h gardé au passage de 15 h : la lecture la plus proche de l'heure du
    relevé)."""
    v = x.get("vues")
    if v is None:
        return None
    e = _reel_de_serie(serie, x.get("code"), x.get("publie"))
    if e is None:
        return v
    pts = _points(e)
    if any(t == fin for t, _ in pts):
        return None
    if any(not _point_metricool(t) and t >= fin - timedelta(hours=SUIVI_APIFY_H) for t, _ in pts):
        return None
    return v


def _deja_entier(serie: dict, fin: datetime) -> bool:
    """La série a déjà, pour cette photo, un relevé Metricool ENTIER (avec couverture) : un partiel ne le remplace jamais."""
    return any(isinstance(r, dict) and r.get("source") == SOURCE and _instant(r.get("t"), timezone.utc) == fin
               and r.get("reels_lus", True) is not False for r in (serie or {}).get("releves") or [])


def ecrire_series(rels: dict, partiels_: dict = None) -> int:
    """Les comptes lus → un relevé « metricool » chacun, en UNE écriture (series.ajouter_releves, contrat C6c : tout écrivain
    de séries passe par lui, jamais un appel par compte) : daté de la fin de sa veille (minuit à Paris), couvrant la fenêtre
    lue ; ses Reels avec leurs vues (une seule source par Reel, voir _vues_a_ecrire). 10/10 (revue) : `partiels_` (même forme,
    `partiels()`) → relevé SANS couverture (reels_lus=False, pas de `couvre` : series.reels_publies ne s'en sert jamais, aucun
    « 0 Reel » possible), mêmes Reels et vues ; jamais à la place d'un relevé entier déjà écrit pour la même photo. Renvoie le
    nombre de relevés écrits (0 sans series.ajouter_releves : rien n'est écrit, et le passage n'est pas « réussi »)."""
    if not rels and not partiels_:
        return 0
    try:
        import series
    except ImportError:
        journal.warning("Metricool : series.py absent, %d relevé(s) non écrit(s)", len(rels or {}) + len(partiels_ or {}))
        return 0
    if not callable(getattr(series, "ajouter_releves", None)):
        journal.warning("Metricool : series.ajouter_releves absent (contrat C6c), %d relevé(s) non écrit(s)",
                        len(rels or {}) + len(partiels_ or {}))
        return 0
    entrees = []
    for entier, lot in ((True, rels or {}), (False, partiels_ or {})):
        for cle, r in lot.items():
            if not entier and cle in (rels or {}):
                continue
            try:
                veille = date.fromisoformat(str(r.get("jour")))
            except (TypeError, ValueError):
                continue
            debut, fin = fenetre(veille)
            serie = _serie(cle)
            if not entier and _deja_entier(serie, fin):
                continue                                                 # le passage de 8 h l'a lu entier : on le garde
            releve = {"t": _iso(fin), "source": SOURCE, "followers": r.get("followers"), "posts_total": None,
                      "restreint": False, "prive": False, "reels_lus": entier}
            if entier:
                releve["couvre"] = _iso(debut)
            reels = [{"code": x["code"], "publie": x["publie"], "type": "Video", "vues": _vues_a_ecrire(serie, x, fin)}
                     for x in r.get("reels") or [] if isinstance(x, dict) and x.get("code")]
            entrees.append({"cle": cle, "releve": releve, "reels": reels, "ig_id": "", "source": SOURCE,
                            "couvre": _iso(debut) if entier else None})
    if not entrees:
        return 0
    try:
        n = series.ajouter_releves(entrees)
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : séries non écrites (%s)", type(erreur).__name__)
        return 0
    return int(n) if isinstance(n, int) and not isinstance(n, bool) else 0


# ------------------------------------------------------------------ passage, état, boucle
def _lire() -> dict:
    if not (_deps.get("lire_json") and _deps.get("FICHIER")):
        return {}
    try:
        d = _deps["lire_json"](_deps["FICHIER"], {})
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : état illisible (%s)", type(erreur).__name__)
        return {}
    return d if isinstance(d, dict) else {}


def _ecrire(d: dict) -> bool:
    """09/10 (correctif) : une écriture impossible (disque plein, volume en lecture seule) est journalisée, jamais levée : le
    passage n'est pas perdu pour autant (les séries sont écrites à part) et les compteurs restent en mémoire."""
    if not (_deps.get("ecrire_json") and _deps.get("FICHIER")):
        return False
    try:
        _deps["ecrire_json"](_deps["FICHIER"], d)
        return True
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : état non écrit (%s)", type(erreur).__name__)
        return False


def _photos(d: dict = None) -> dict:
    """10/10 (revue) : les dernières lectures des vues par compte ({clé: {"fin", "vues", "prec"}}) — l'état, complété par la
    mémoire (état illisible ou pas écrit) ; à photo égale, la mémoire (la plus récente) l'emporte."""
    d = _lire() if d is None else d
    out = {k: v for k, v in (d.get("photos") or {}).items() if isinstance(v, dict)} if isinstance(d.get("photos"), dict) else {}
    for k, v in (_memoire.get("photos") or {}).items():
        f_m, f_d = _instant(v.get("fin"), timezone.utc), _instant((out.get(k) or {}).get("fin"), timezone.utc)
        if f_m is not None and (f_d is None or f_m >= f_d):
            out[k] = v
    return out


def _photos_maj(d: dict) -> dict:
    """Les lectures gardées après ce passage (_passage["photos"]), lectures de plus de PHOTOS_J jours retirées."""
    fin = _passage.get("fin") or ""
    photos = _photos(d)
    for cle, vues in (_passage.get("photos") or {}).items():
        photos[cle] = photo_maj(photos.get(cle), fin, vues)
    g = _instant(fin, timezone.utc)
    if g is not None:
        photos = {k: v for k, v in photos.items()
                  if (_instant(v.get("fin"), timezone.utc) or g) >= g - timedelta(days=PHOTOS_J)}
    _memoire["photos"] = photos
    return photos


def _jour_de(t: str) -> str:
    """La veille (Paris) d'un passage fait à l'instant `t` : le jour des données qu'il a lues."""
    i = _instant(t, timezone.utc)
    return (i.astimezone(_paris_tz()).date() - timedelta(days=1)).isoformat() if i is not None else ""


def etat() -> dict:
    """Contrat C6(b) à la lettre, pour le Dashboard (fraîcheur « Metricool J-1 ») : {"jour": J-1 des données du dernier passage
    RÉUSSI (au moins un compte lu, aucune erreur, séries écrites) ou "", "dernier_ok": iso de ce passage ou "", "jour_essai":
    J-1 du dernier essai, "erreur": erreur du dernier essai ("" s'il a réussi), "lus": comptes lus au dernier passage réussi}.
    Un essai raté ne change ni `jour`, ni `dernier_ok`, ni `lus` (jamais une fraîcheur annoncée à tort). Le détail du dernier
    essai (non lus, échecs, débranchés ?, @ partagés, hors classeur, écrits) : `dernier_essai()`."""
    d = _lire()
    dern = d.get("dernier") if isinstance(d.get("dernier"), dict) else {}
    ok = d.get("ok") if isinstance(d.get("ok"), dict) else {}
    dernier_ok = str(ok.get("t") or d.get("dernier_ok") or "")
    jour = str(ok.get("jour") or "") or (_jour_de(dernier_ok) if dernier_ok else "")
    if "lus" in ok:
        lus = list(ok.get("lus") or [])
    else:                                                                # état d'avant le correctif
        lus = list(dern.get("lus") or []) if dernier_ok and dern.get("t") == dernier_ok else []
    return {"jour": jour, "dernier_ok": dernier_ok, "jour_essai": str(dern.get("jour") or ""),
            "erreur": str(dern.get("erreur") or ""), "lus": lus}


def dernier_essai() -> dict:
    """Le bilan complet du dernier essai, gardé dans l'état (survit à un redémarrage, contrairement à `bilan()`)."""
    d = _lire()
    return dict(d["dernier"]) if isinstance(d.get("dernier"), dict) else {}


async def _alerter(lignes: list, jour: str):
    """Une alerte au salon admin par jour et par motif au plus : lignes = [(motif, texte)] ; les motifs déjà signalés aujourd'hui
    (état ou mémoire) sont retirés, le reste part en UN message."""
    d = _lire()
    faites = dict(d.get("alertes") or {}) if isinstance(d.get("alertes"), dict) else {}
    faites.update({k: v for k, v in _memoire["alertes"].items() if v == jour})
    a_dire = [(k, t) for k, t in lignes if faites.get(k) != jour]
    if not a_dire or not callable(_deps.get("canal_admin")):
        return
    try:
        canal = await _deps["canal_admin"]()
        if canal is None:
            return
        await canal.send(("⚠️ **Metricool**\n\n" + "\n\n".join(t for _, t in a_dire))[:1990])
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Metricool : alerte admin non envoyée (%s)", type(erreur).__name__)
        return
    for k, _ in a_dire:
        _memoire["alertes"][k] = jour
        faites[k] = jour
    d = _lire()
    d["alertes"] = {k: v for k, v in faites.items() if v >= (date.fromisoformat(jour) - timedelta(days=3)).isoformat()}
    _ecrire(d)


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


def _texte_debranche(c: str, j: str) -> str:
    try:
        return f"@{c} (dernière publication le {date.fromisoformat(str(j)):%d/%m})"
    except ValueError:
        return f"@{c} (aucune publication depuis plus de {JOURS} jours)"


def _lignes_alerte(b: dict, rels: dict, now: datetime, partiels_: dict = None) -> list:
    """Les motifs d'alerte d'un passage (09/10, correctif : plus de panne silencieuse)."""
    lignes = []
    if b.get("erreur"):
        lignes.append(("panne", f"{b['erreur']}. Les Reels et vues des comptes Instagram branchés ne sont pas à jour (rien "
                                f"n'est écrit à 0)."))
        return lignes
    dernier = now.hour >= HEURES[-1]                                     # dernier passage du jour : Apify a pu confirmer
    format_ko = [c for c, r in b["non_lus"].items() if "non comprise" in r]
    if format_ko:
        lignes.append(("format", f"réponse non comprise pour {len(format_ko)} compte(s) Instagram — format de brand-summary à "
                                 f"vérifier. Rien n'est écrit pour eux."))
    if b.get("marques_ig") and not b["lus"]:
        sync = all(r.startswith(PREFIXE_SYNC) for r in b["non_lus"].values()) and not b["echecs"]
        if not sync or dernier:                                          # pas encore synchronisé à 8 h : 15 h relira
            raisons = {}
            for r in list(b["non_lus"].values()) + [f"erreur : {e}" for e in b["echecs"].values()]:
                k = r.split(" (")[0].split(" et ")[0][:70]
                raisons[k] = raisons.get(k, 0) + 1
            part = len(b.get("partiels") or [])
            lignes.append(("aucun", f"aucun compte Instagram lu sur {b['marques_ig']} branché(s) — "
                                    + " ; ".join(f"{n} × {k}" for k, n in sorted(raisons.items(), key=lambda x: -x[1]))
                                    + (f" ({part} avec des vues qui bougent : vues écrites, Reels non comptés)" if part else "")
                                    + ". Rien n'est écrit à 0."))
    lus = dict(partiels_ or {})
    lus.update(rels or {})
    if lus:
        # 10/10 (revue) : vues absentes OU toutes à 0 (métrique cassée qui renvoie 0) : même alerte
        _, fin = fenetre(date.fromisoformat(b["jour"]))
        agees = [x for r in lus.values() for x in r.get("reels") or []
                 if (p := _instant(x.get("publie"), timezone.utc)) is not None and fin - p >= timedelta(hours=AGE_VRAI_ZERO_H)]
        if len(agees) >= VUES_ALERTE_MIN and not any((_nombre(x.get("vues")) or 0) > 0 for x in agees):
            zeros = int(b.get("zeros_ignores") or 0) or sum(1 for x in agees if x.get("vues") == 0)
            lignes.append(("vues", f"aucune vue lisible sur {len(agees)} Reels de plus de 24 h ({len(lus)} compte(s) lus"
                                   + (f", {zeros} vue(s) à 0" if zeros else "") + ") — métrique VIEWS / IMPRESSIONS "
                                   "introuvable ou vide dans brand-summary, à vérifier."
                                   + (" Ces 0 ne sont pas écrits (non mesuré, jamais un shadowban de masse)."
                                      if b.get("zeros_ignores") else "")))
    if b.get("debranches") and dernier:                                  # 10/10 (revue) : jamais au passage de 8 h
        lignes.append(("debranche", "rien de Metricool depuis 2 jours ou plus (aucun Reel, vues figées), et Apify ne confirme "
                                    "pas ces jours sans publication : compte en pause, ou Instagram débranché de Metricool "
                                    "(jeton expiré) ? "
                       + ", ".join(_texte_debranche(c, j) for c, j in sorted(b["debranches"].items()))
                       + ". Ces comptes sont non lus, rien n'est écrit à 0."))
    return lignes


async def executer(maintenant=None, ecrire: bool = True) -> dict:
    """Un passage : releves() puis, si `ecrire`, les séries (une écriture). Renvoie le bilan (avec `ecrits`) et le garde dans
    l'état ; le passage est RÉUSSI (etat()["jour"], "dernier_ok", "lus") s'il a lu au moins un compte, sans erreur, et écrit les
    séries. 10/10 (revue) : les comptes « partiels » (partiels()) sont écrits dans la même écriture, sans couverture ; la lecture
    des vues de chaque compte est gardée dans l'état (`photos`) pour juger demain si sa synchro est vivante."""
    now = _maintenant_paris(maintenant)
    rels = await releves(now)
    parts = partiels()
    b = bilan()
    b["ecrits"] = ecrire_series(rels, parts) if ecrire else 0
    if ecrire and rels and not b["ecrits"] and not b["erreur"]:
        b["erreur"] = f"séries non écrites ({len(rels)} compte(s) lus)"
    b["hors_classeur"] = await _hors_classeur(set(b.get("lus") or []) | set(b.get("non_lus") or {}) | set(b.get("echecs") or {}))
    d = _lire()
    d["dernier"] = b
    if b["lus"] and not b["erreur"] and ecrire:
        d["ok"] = {"t": b["t"], "jour": b["jour"], "lus": list(b["lus"])}
        d["dernier_ok"] = b["t"]
    if ecrire and _passage.get("photos"):
        d["photos"] = _photos_maj(d)
    _ecrire(d)
    if actif():
        lignes = _lignes_alerte(b, rels, now, parts)
        if lignes:
            await _alerter(lignes, now.date().isoformat())
    return b


def _faits(d: dict, jour: str) -> set:
    f = d.get("faits") if isinstance(d.get("faits"), dict) else {}
    return set(f.get(jour) or []) | set(_memoire["faits"].get(jour) or [])


def _essais(d: dict, jour: str, cran: int) -> int:
    e = d.get("essais") if isinstance(d.get("essais"), dict) else {}
    n = int(e.get("n") or 0) if e.get("jour") == jour and e.get("cran", cran) == cran else 0
    m = _memoire["essais"]
    if m.get("jour") == jour and m.get("cran") == cran:
        n = max(n, int(m.get("n") or 0))
    return n


async def tour(maintenant=None):
    """Un tour de boucle : un passage si une heure de METRICOOL_HEURES (Paris) est passée et pas encore faite aujourd'hui (après un
    redémarrage, les heures manquées se rattrapent en UN passage). Passage en panne (erreur ou exception) : retenté au tour
    suivant, ESSAIS_MAX fois par heure de passage ; l'essai est compté AVANT le passage (09/10, correctif)."""
    now = _maintenant_paris(maintenant)
    jour = now.date().isoformat()
    d = _lire()
    faits = _faits(d, jour)
    dues = [h for h in HEURES if now.hour >= h and h not in faits]
    if not dues:
        return None
    cran = max(dues)
    n = _essais(d, jour, cran) + 1
    _memoire["essais"] = {"jour": jour, "cran": cran, "n": n}
    d["essais"] = dict(_memoire["essais"])
    _ecrire(d)
    try:
        b = await executer(now)
    except Exception as erreur:                                          # noqa: BLE001 — compté comme un essai raté
        journal.exception("Metricool (comptes) : passage interrompu : %s", erreur)
        b = {"t": _iso(now), "jour": (now.date() - timedelta(days=1)).isoformat(), "lus": [], "non_lus": {}, "echecs": {},
             "erreur": f"passage interrompu ({type(erreur).__name__})"}
        d = _lire()
        d["dernier"] = b                                                 # etat() (C6b) : l'essai raté se voit, `jour` ne bouge pas
        _ecrire(d)
    if b.get("erreur") and n < ESSAIS_MAX:
        return b
    faits_j = sorted(faits | set(dues))
    _memoire["faits"] = {k: v for k, v in _memoire["faits"].items() if k >= (now.date() - timedelta(days=3)).isoformat()}
    _memoire["faits"][jour] = faits_j
    d = _lire()
    d["faits"] = {k: v for k, v in (d.get("faits") or {}).items() if k >= (now.date() - timedelta(days=3)).isoformat()} \
        if isinstance(d.get("faits"), dict) else {}
    d["faits"][jour] = faits_j
    d["essais"] = {"jour": jour, "cran": cran, "n": 0}
    _memoire["essais"] = dict(d["essais"])
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
