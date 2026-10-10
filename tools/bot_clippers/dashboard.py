"""Dashboard des clippers (09/10, contrat C5 — Gaëtan : « je veux que ce dashboard se mette à jour constamment : statuts, Reels
postés, clics, followers. Je dois comprendre quel compte est en hausse ou en baisse de vues, ainsi que ses clics. Tout voir, le plus
souvent possible, le plus précis possible : pas de trucs pas précis, pas de manquements, pas de clippeurs ou de liens pas assignés
au compte »).

`await ecrire(force=False) -> dict` relit lui-même le classeur (onboarding.lire_comptes), les séries par compte (series.py, contrat
C1), l'état du scan (etats_comptes.json : historique, bios, non lus, dernier passage, budget Apify), les clics (clics.json, `jours`
et `aujourdhui`, contrat C2, lus par paie_clics.clics_lien / clics_aujourdhui) et le contrôle d'attribution (controle.py, contrat
C3), puis réécrit l'onglet « Dashboard » du classeur des logins (le bot seul y écrit). AUCUN appel Apify, GAML ni Metricool : des
lectures de fichiers du bot et une lecture du classeur. L'onglet n'est réécrit que si son contenu a changé (empreinte), au plus
toutes les 15 minutes (`boucle(client)`, démarrée par bot_discord.py) ; `force=True` (`!dashboard`, passage complet du matin via
etats_comptes.ecrire_dashboard) le réécrit tout de suite.

De haut en bas (deux colonnes figées, Gérant et @ : au téléphone le détail défile à droite, les libellés restent) :
  1. titre « Dashboard · mis à jour le JJ/MM à HHhMM (Paris) », fraîcheur de chaque source (« Instagram 14h05 · Clics 16h45 ·
     Metricool J-1 ») et budget Apify du mois ;
  2. CONTRÔLE : compteur par famille (C1…C12), les 15 premières anomalies, bouclage des visites 7 j (écart attendu : 0) ;
  3. TENDANCES : top 5 hausses et top 5 baisses — vues 7 j à âge fixe (48 h) contre les 7 jours d'avant, clics 7 j contre les 7
     jours d'avant, followers sur 7 jours — seulement pour ce qui est mesuré sur les deux périodes (classement par écart absolu) ;
  4. COMPTES, par créatrice : une ligne par compte (@), groupée par Gérant (sous-total dès deux comptes), puis « Pages de la
     créatrice » (principale, /fb, /ytb), « Libérés / hors clipping » et, s'il y en a, « Liens attribués sans ligne » : chaque lien
     GAML actif est compté une fois et une seule. Le trio d'un clipper partage un lien : ses clics sont sur la ligne qui le porte
     (le compte dont la bio a le lien, sinon le privé, sinon le premier), « (trio) » sur les autres. Un compte sans lien qui renvoie
     vers YouTube : « via YouTube, non attribuable ». Deux clippers du même prénom (homonymes) : un groupe par lien.
Jamais un faux 0 : une valeur non lue reste vide, ou garde sa dernière valeur relevée (followers) avec l'heure du relevé ; la
colonne Mesure dit pourquoi (lu, restreint, privé, non lu, introuvable, Metricool, à créer, classeur, jamais lu). Les écarts sont
écrits en texte, « ▲ 12 % » / « ▼ 8 % » ; leur couleur vient d'une mise en forme conditionnelle posée une fois par
DASHBOARD_VERSION. Aucune formule (le classeur est en locale française) : valeurs et nombres bruts, aucune interprétation.

Écriture en place, en un batchUpdate : les valeurs écrasent les anciennes et les lignes en trop sont vidées dans la même requête
(updateCells sur toute la grille), jamais d'onglet vidé d'abord. La mise en forme des onglets créatrices (classeur_forme) et
l'onglet Build capacity (capacite) ne suivent plus le Dashboard : passage complet du matin seulement.

09/10 (revue DASH) — ce qui a changé après la revue adversariale :
  - titre : budget Apify d'après `apify_budget` (contrat C6a) rapporté au budget de Gaëtan (25 $), « ⛔ Apify coupé jusqu'au
    JJ/MM » à 100 %, alerte dès que la trajectoire du budget est dépassée ; fraîcheur Metricool d'après le dernier passage RÉUSSI
    (C6b), « ⚠ Metricool en échec depuis JJ/MM » sinon ; alertes en lignes à part sous le titre (visibles au téléphone) ;
  - « lien d'un autre clipper » décidé sur les identifiants (C6d : onboarding.json → uid, uid du lien), jamais sur un prénom ;
  - une somme qui ne couvre qu'une partie des comptes ou des liens le dit dans la colonne Mesure (« k/n ») ; un followers d'un vieux
    relevé porte sa date ; un compte relu par le passage léger n'est plus « non lu » ; Reels du classeur repris seulement si le scan
    qui les a écrits a le même « hier » (heure de Paris) ; vues comparées seulement quand chaque Reel publié est mesuré à 48 h ;
  - bouclage : ✅ seulement si tout est mesuré, sans écart, et concordant avec le TOTAL Clics 7 j (C6e) ; les liens des Gérants
    masqués vont dans le seau « masqués » (jamais une fausse alerte) ;
  - l'onglet part en UN appel HTTP (plus de découpage par 400) ; l'empreinte porte aussi la fraîcheur des sources ;
  - la réécriture forcée du passage complet attend la fin du passage (ecrire_apres_passage).

10/10 (restants de la revue DASH) :
  - une somme de vues faite seulement de comptes partiels le dit (« partiel : vues 0/2 »), comme toute somme partielle ;
  - relectures légères sautées par la garde du budget (`leger_ok` faux) : dit au titre et en ligne d'alerte, même quand la dépense
    seule reste sous la trajectoire ;
  - un lien compté sur une ligne dont le Gérant ne porte pas le nom du membre du lien (fiche d'onboarding écartée, ou Gérant au
    nom d'un autre membre) est signalé « ⚠ lien de X d'après le nom, à vérifier », sans être refusé (C6d).

Les modules des autres lots (series, controle, metricool_comptes, paie_clics.clics_lien / clics_aujourdhui) sont importés s'ils
sont là : s'il en manque un, sa section dit « source indisponible », ou les chiffres viennent des cellules du classeur (repli
marqué), et les clics d'un lien sont recalculés depuis clics.json « jours » selon la même règle que le contrat C2.
Dépendances (`configurer`) : lire_json, ecrire_json, FICHIER (état du Dashboard : empreinte, version, lignes écrites),
FICHIER_ETATS, FICHIER_CLICS, FICHIER_EQUIPES, FICHIER_ONBOARDING ; facultatifs membre_par_id, normaliser."""
import asyncio
import calendar
import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime, time as dtime, timedelta, timezone

import google_api
import onboarding

try:                                                                    # contrat C1 (lot SCAN)
    import series
except ImportError:                                                     # pragma: no cover — section « source indisponible »
    series = None
try:                                                                    # contrat C2 (lot CLICS)
    import paie_clics
except ImportError:                                                     # pragma: no cover
    paie_clics = None
try:                                                                    # contrat C3 (lot CONTROLE)
    import controle
except ImportError:
    controle = None
try:                                                                    # contrat C4 (lot METRICOOL)
    import metricool_comptes
except ImportError:
    metricool_comptes = None

journal = logging.getLogger("dashboard")

ONGLET = os.environ.get("ONGLET_DASHBOARD", "Dashboard").strip() or "Dashboard"
DASHBOARD_VERSION = 11                 # 09/10 (dashboard) : une ligne par compte, tendances, contrôle ; changée → règles reposées
                                       # 11 (revue DASH) : lignes d'alerte « ⛔ » sous le titre, règle de couleur « ⛔ »
ACTIF = os.environ.get("DASHBOARD_BOUCLE", "1").strip() != "0"
INTERVALLE_S = 900                     # la boucle regarde toutes les 15 minutes
ECART_MIN_S = 14 * 60                  # deux réécritures non forcées : au moins 14 minutes d'écart
DELAI_DEMARRAGE_S = 90                 # au démarrage, laisser les autres boucles se configurer
ANOMALIES_MAX = 15
TOP = 5
AGE_VUES_H = 48                        # vues d'un Reel relevées 48 h après sa publication (même âge pour comparer)
METRICOOL_RECENT_J = 4                 # un relevé Metricool plus vieux ne compte plus dans la Mesure
# 09/10 (revue DASH) : budget Apify TOTAL du mois décidé par Gaëtan (« Dépasse pas 25 $ / mois »), le même que le lot SCAN
try:
    APIFY_BUDGET_MOIS = float(os.environ.get("APIFY_BUDGET_MOIS", "25") or 25)
except ValueError:
    APIFY_BUDGET_MOIS = 25.0
FOLLOWERS_PERIME_J = 7                 # followers illisibles depuis plus longtemps (compte relu entre-temps) : cellule vide
CLICS_VIEUX_MIN = 45                   # clics du jour relevés il y a plus longtemps : l'heure est écrite sur la ligne (la boucle des
                                       # clics relit chaque lien toutes les 15 à 30 min, plus le décalage de la boucle du Dashboard)
METRICOOL_VIEUX_J = 3                  # données Metricool plus vieilles (J-3 et au-delà) : « ⚠ » dans la fraîcheur
ATTENTE_PASSAGE_S = 1800               # réécriture différée : attendre au plus 30 min la fin du passage complet

COLONNES = ["Gérant", "@", "Utilisation", "ETAT", "Followers", "Δ 24 h", "Δ 7 j", "Reels hier", "Reels 7 j", "Δ Reels",
            "Vues 7 j (48 h)", "Δ vues", "Vue médiane", "Lien", "Clics auj.", "Clics hier", "Clics 7 j", "Δ clics", "Mesure", "Relevé"]
NB = len(COLONNES)
(C_GERANT, C_HANDLE, C_UTIL, C_ETAT, C_FOL, C_DF24, C_DF7, C_RH, C_R7, C_DR, C_V7, C_DV, C_VMED, C_LIEN, C_CA, C_CH, C_C7, C_DC,
 C_MES, C_REL) = range(NB)
LARGEURS = (92, 136, 86, 72, 76, 62, 62, 54, 54, 58, 74, 66, 64, 128, 56, 56, 60, 66, 120, 86)
COLS_NOMBRES = (C_FOL, C_RH, C_R7, C_V7, C_VMED, C_CA, C_CH, C_C7)
COLS_DELTAS = (C_DF24, C_DF7, C_DR, C_DV, C_DC)

FAMILLES = {"C1": "Compte créé sans Gérant", "C2": "Gérant fantôme", "C3": "Gérant ambigu (homonymes)",
            "C4": "Gérant ≠ fiche d'onboarding", "C5": "Lien dû manquant", "C6": "Cellule Lien GAML fausse",
            "C7": "Lien sans ligne vivante", "C8": "Visites sur lien libéré / hors clipping", "C9": "Note GAML ≠ attribution",
            "C10": "Lien en bio ≠ lien attendu", "C11": "@ en double", "C12": "Compte non lu / restreint / illisible"}
GRAVITES = {"bloquant": "⛔ bloquant", "important": "⚠️ important", "info": "ℹ️ info"}

# Palette par créatrice (bandeau, teinte des lignes), la même que l'ancien Dashboard et les onglets créatrices
PALETTE = {"chloe": ("#C2185B", "#FCE4EC"), "sarah": ("#1565C0", "#E3F2FD"), "sophie": ("#6A1B9A", "#F3E5F5"),
           "jade": ("#2E7D32", "#E8F5E9"), "maddie": ("#EF6C00", "#FFF3E0"), "clara": ("#00838F", "#E0F7FA")}
PALETTE_DEFAUT = ("#455A64", "#ECEFF1")
SOMBRE, SECTION, BLANC, GRIS_CLAIR, GRIS_TEXTE = "#263238", "#37474F", "#FFFFFF", "#ECEFF1", "#546E7A"

# Les catégories de lien qu'une ligne peut porter (sinon : « ⚠ » dans la colonne Lien, et le lien reste dans sa ligne de résumé).
# 09/10 (revue DASH) : « non_attribue » = la catégorie du contrôle (controle.categorie) pour un lien de clipping sans détenteur
# (note « Clipping X » jamais attribuée, lien suivi par le rapport) : porté par la ligne qui l'a en cellule, comme « suivi ».
AUTORISES = {"clipper": {"attribue", "suivi", "non_attribue"}, "metricool": {"attribue", "suivi", "non_attribue", "hors_clipping"},
             "creatrice": {"page"}, "libre": set()}
INACTIFS = ("desactive", "supprime")

_deps: dict = {}
_verrou = None
_PARIS = None
_differees: set = set()                # réécritures forcées qui attendent la fin du passage complet (ecrire_apres_passage)


def configurer(deps: dict):
    _deps.update(deps or {})


def actif() -> bool:
    return ACTIF and onboarding.actif()


# ------------------------------------------------------------------ outils
def _tz():
    global _PARIS
    if _PARIS is None:
        try:
            from zoneinfo import ZoneInfo
            _PARIS = ZoneInfo("Europe/Paris")
        except Exception:                                                # noqa: BLE001
            _PARIS = timezone(timedelta(hours=2))
    return _PARIS


def _paris(dt: datetime) -> datetime:
    return dt.astimezone(_tz())


def _minuit(j: date) -> datetime:
    """Minuit (heure de Paris) au début du jour `j`, avec fuseau."""
    return datetime.combine(j, dtime(0), tzinfo=_tz())


def _instant(x):
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(x).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _norm(t) -> str:
    return onboarding._norm(str(t or "")).strip()


def _premier(t) -> str:
    return (_norm(t).split() or [""])[0]


def _cle(handle) -> str:
    """La clé d'un compte, la même que le scan et les séries (etats_comptes._cle) : identifiant nettoyé, minuscules."""
    return onboarding.normaliser_handle(handle).lower()


def _txt_n(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def _hm(x, ref: date = None) -> str:
    """« 14h05 » si le relevé est du jour `ref` (Paris), sinon « 08/10 14h05 » ; '' si illisible."""
    t = _instant(x)
    if t is None:
        return ""
    p = _paris(t)
    return p.strftime("%Hh%M") if ref is not None and p.date() == ref else p.strftime("%d/%m %Hh%M")


def _entier(v):
    """Un nombre lu dans une cellule du classeur (« 12 345 », « 953 ») ; None si vide ou illisible (jamais 0 par défaut)."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    t = re.sub(r"[\s  ]", "", str(v))
    return int(t) if t.isdigit() else None


def _delta_pct(cur, prev) -> str:
    """« ▲ 12 % » / « ▼ 8 % » / « ► 0 % » ; '' si l'une des deux périodes n'est pas mesurée."""
    if cur is None or prev is None:
        return ""
    if prev == 0:
        return "▲ nouveau" if cur > 0 else "► 0 %"
    r = int(round((cur - prev) * 100 / prev))
    return f"▲ {_txt_n(r)} %" if r > 0 else (f"▼ {_txt_n(-r)} %" if r < 0 else "► 0 %")


def _delta_abs(d) -> str:
    """« ▲ 35 » / « ▼ 4 » / « ► 0 » ; '' si inconnu."""
    if d is None:
        return ""
    return f"▲ {_txt_n(d)}" if d > 0 else (f"▼ {_txt_n(-d)}" if d < 0 else "► 0")


def _url_cle(u) -> str:
    t = str(u or "").strip().lower()
    t = re.sub(r"^https?://", "", t)
    t = re.sub(r"^www\.", "", t)
    return t.split("?")[0].split("#")[0].rstrip("/")


_RE_URL = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s,;|]*)?", re.I)


def _urls(texte) -> list:
    return [_url_cle(m) for m in _RE_URL.findall(str(texte or "")) if _url_cle(m)]


def _categorie(info: dict) -> str:
    """attribue / suivi (rapport, sans clipper payé) / hors_clipping / libere / page (créatrice, /fb, /ytb, jamais attribué) /
    desactive / supprime — même découpage que le contrôle (bouclage), « suivi » mis à part.
    09/10 (revue DASH) : la règle du contrôle (controle.categorie : « page » définie positivement, « non_attribue » pour un lien de
    clipping sans détenteur) quand elle est là — les lignes « Pages » et « Libérés » du Dashboard et les seaux du bouclage disent
    la même chose ; ce découpage local n'est qu'un repli."""
    f = getattr(controle, "categorie", None) if controle is not None else None
    if callable(f):
        try:
            return str(f(info))
        except Exception as erreur:                                      # noqa: BLE001 — repli local
            journal.debug("Catégorie du contrôle : %s", erreur)
    if info.get("supprime_gaml"):
        return "supprime"
    if info.get("desactive"):
        return "desactive"
    if str(info.get("uid") or ""):
        return "attribue"
    if info.get("hors_clipping"):
        return "hors_clipping"
    if info.get("libere"):
        return "libere"
    if info.get("suivi"):
        return "suivi"
    return "page"


def _slug(info: dict, lid: str) -> str:
    """Le slug court d'un lien : le slug GAML, sinon le chemin de son URL, sinon son domaine (page principale)."""
    if str(info.get("slug") or "").strip():
        return str(info["slug"]).strip()
    u = _url_cle(info.get("url"))
    if "/" in u:
        return u.split("/", 1)[1][:28] or u.split("/", 1)[0]
    return u[:28] or str(lid)[:10]


def _est_prive(c: dict) -> bool:
    return _norm(c.get("etat")) in ("prive", "privé") or bool(onboarding.RE_PRIVE.search(_norm(c.get("handle"))))


def _mots_nom(t) -> set:
    """Les mots d'un pseudo avant « - Créatrice » (ou d'un Gérant), tirets et emoji ignorés : « 🌸 Jean-Marc - Sophie » → {jean,
    marc}. Même règle que onboarding (liens_classeur, contrat C6d) : sert seulement à écarter un détenteur périmé, jamais à décider
    qu'un lien est celui d'un autre."""
    return set(re.findall(r"[a-z0-9]+", _norm(str(t or "").split(" - ")[0]))) - {"metricool", "clipper", "compte"}


def _proprietaires(onb: dict) -> dict:
    """Contrat C6(d) : {clé du @ : {uid}} — qui détient chaque compte d'après onboarding.json : la livraison la plus récente
    (`livres`) prime, sinon les fiches (comptes, accès) qui portent ce @. {} si le fichier manque (rien n'est alors décidé)."""
    onb = onb if isinstance(onb, dict) else {}
    out = {}
    for uid, fiche in (onb.get("clippers") or {}).items() if isinstance(onb.get("clippers"), dict) else ():
        if not isinstance(fiche, dict):
            continue
        hs = {h for h in fiche.get("comptes") or [] if isinstance(h, str)}
        hs |= {a.get("handle") for a in fiche.get("acces") or [] if isinstance(a, dict) and isinstance(a.get("handle"), str)}
        for h in hs:
            if _cle(h):
                out.setdefault(_cle(h), set()).add(str(uid))
    for h, l in (onb.get("livres") or {}).items() if isinstance(onb.get("livres"), dict) else ():
        if isinstance(l, dict) and str(l.get("uid") or "") and _cle(h):
            out[_cle(h)] = {str(l["uid"])}
    return out


def _type_ligne(c: dict, creatrices: set) -> str:
    g, u = _norm(c.get("gerant")), _norm(c.get("utilisation"))
    if onboarding.est_ligne_creatrice(c, creatrices):
        return "creatrice"
    if g in onboarding.GERANTS_LIBRES:
        return "libre"
    if "metricool" in g or u == "metricool":
        return "metricool"
    return "clipper"


# ------------------------------------------------------------------ sources (avec repli si un lot manque)
def _serie(fn: str, *args):
    """Un calcul de series.py (contrat C1) ; None si le module ou la fonction manque, ou si le calcul échoue."""
    f = getattr(series, fn, None) if series is not None else None
    if not callable(f):
        return None
    try:
        return f(*args)
    except Exception as erreur:                                          # noqa: BLE001 — un compte abîmé n'éteint pas le reste
        journal.debug("Séries %s : %s", fn, erreur)
        return None


def series_dispo() -> bool:
    return series is not None and callable(getattr(series, "followers_a", None))


def _clics_lien_local(d: dict, lid: str, debut: date, fin: date):
    """Repli de paie_clics.clics_lien (contrat C2) si le lot CLICS n'est pas là : somme des `payes` du `debut` au `fin` inclus,
    None si un jour manque ou porte une erreur ; un lien repris ne compte qu'à partir de `depuis`."""
    dep = str((((d or {}).get("liens") or {}).get(str(lid)) or {}).get("depuis") or "")[:10]
    if dep:
        try:
            debut = max(debut, date.fromisoformat(dep))
        except ValueError:
            pass
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


def _clics_lien(d: dict, lid: str, debut: date, fin: date):
    f = getattr(paie_clics, "clics_lien", None) if paie_clics is not None else None
    try:
        return f(d, lid, debut, fin) if callable(f) else _clics_lien_local(d, lid, debut, fin)
    except Exception as erreur:                                          # noqa: BLE001
        journal.debug("Clics %s : %s", lid, erreur)
        return None


def _clics_aujourdhui(d: dict, lid: str, j0: date) -> tuple:
    """(visites payables du jour en cours à Paris, heure du relevé) ; (None, '') si le lien n'a pas été relu aujourd'hui."""
    f = getattr(paie_clics, "clics_aujourdhui", None) if paie_clics is not None else None
    try:
        if callable(f):
            try:                                                         # 09/10 (revue DASH) : le jour du Dashboard, pas l'horloge
                n, t = f(d, lid, jour=j0)
            except TypeError:                                            # signature du contrat sans `jour`
                n, t = f(d, lid)
        else:
            e = ((d or {}).get("aujourdhui") or {}).get(str(lid)) or {}
            n, t = (e.get("payes"), str(e.get("t") or "")) if str(e.get("jour") or "") == j0.isoformat() else (None, "")
    except Exception as erreur:                                          # noqa: BLE001
        journal.debug("Clics du jour %s : %s", lid, erreur)
        return None, ""
    ti = _instant(t)
    if n is None or isinstance(n, bool) or (ti is not None and _paris(ti).date() != j0):
        return None, ""
    return int(n), str(t or "")


# ------------------------------------------------------------------ contexte d'un calcul
class _Ctx:
    def __init__(self, e: dict, maintenant: datetime):
        self.maintenant = maintenant
        self.p = _paris(maintenant)
        self.j0 = self.p.date()
        self.hier = self.j0 - timedelta(days=1)
        self.etats = e.get("etats") if isinstance(e.get("etats"), dict) else {}
        self.clics = e.get("clics") if isinstance(e.get("clics"), dict) else {}
        self.hist = self.etats.get("historique") or {}
        self.dp = self.etats.get("dernier_passage") if isinstance(self.etats.get("dernier_passage"), dict) else {}
        self.non_lus = self.etats.get("non_lus") if isinstance(self.etats.get("non_lus"), dict) else {}
        self.bios = self.etats.get("bios") if isinstance(self.etats.get("bios"), dict) else {}
        self.liens = {str(k): v for k, v in (self.clics.get("liens") or {}).items() if isinstance(v, dict)}
        self.par_url = {}
        for lid, info in sorted(self.liens.items()):
            u = _url_cle(info.get("url"))
            if u:
                self.par_url.setdefault(u, lid)
        self._clics = {}
        self._cats = {}
        self.seriesok = series_dispo()
        # 09/10 (revue DASH, contrat C6d) : « lien d'un autre clipper » se décide sur les IDENTIFIANTS — qui détient chaque compte
        # d'après onboarding.json (uid), et l'uid du lien dans clics.json —, jamais sur le premier mot d'un pseudo ou du Gérant
        # (avant : « 🌸 Paul - Sophie » voyait son propre lien refusé sur sa ligne, ses clics partaient en « Sans ligne »).
        self.proprietaires = _proprietaires(e.get("onboarding"))
        registre = e.get("registre") if isinstance(e.get("registre"), dict) else {}
        membres = e.get("membres") if isinstance(e.get("membres"), dict) else {}
        self.registre, self.membres = registre, membres
        self.noms_uid = {}
        for uid in set(map(str, registre)) | set(map(str, membres)):
            f = registre.get(uid) if isinstance(registre.get(uid), dict) else {}
            self.noms_uid[uid] = _mots_nom(membres.get(uid)) | _mots_nom(f.get("prenom"))

    def cat(self, lid) -> str:
        if lid not in self._cats:
            self._cats[lid] = _categorie(self.liens.get(lid) or {})
        return self._cats[lid]

    def detenteurs(self, c: dict) -> set:
        """Contrat C6(d) : les uid qui détiennent la ligne d'après onboarding.json, gardés s'ils sont compatibles avec le Gérant écrit
        (un mot en commun avec le nom du membre, ou membre sans nom connu : onboarding.json fait foi) — même règle que
        onboarding.liens_classeur. Un Gérant changé à la main sans que le bot ait suivi n'hérite pas de l'ancien détenteur."""
        mots_g = _mots_nom(c.get("gerant"))
        out = set()
        for uid in self.proprietaires.get(_cle(c.get("handle")), set()):
            noms = self.noms_uid.get(str(uid)) or set()
            if not noms or (mots_g & noms):
                out.add(str(uid))
        return out

    def a_un_autre(self, lid, L: dict) -> bool:
        """Contrat C6(d) : le lien est attribué (uid dans clics.json) à un autre identifiant que le(s) détenteur(s) de la ligne
        (onboarding.json). Détenteur inconnu → non : rien ne prouve que ce n'est pas le sien (le contrôle signale)."""
        uid = str((self.liens.get(lid) or {}).get("uid") or "")
        if not uid:
            return False
        props = L.get("detenteurs")
        if props is None:
            props = L["detenteurs"] = self.detenteurs(L["c"])
        return bool(props) and uid not in props

    def nom_uid(self, uid) -> str:
        """Le nom à afficher d'un membre : son pseudo avant « - Créatrice », sinon le prénom du registre (règle du contrôle)."""
        uid = str(uid or "")
        nom = str(self.membres.get(uid) or "").split(" - ")[0].strip()
        if not nom:
            f = self.registre.get(uid) if isinstance(self.registre.get(uid), dict) else {}
            nom = str(f.get("prenom") or "").strip().title()
        return nom[:24]

    def lien_suspect(self, lid, L: dict) -> str:
        """10/10 (revue DASH, restant 3 : Gérant changé à la main sans que le bot suive — onboarding.json livre encore la ligne à
        Paul, la cellule garde le lien de Paul ; le détenteur écarté, rien ne prouvait sur les uid que le lien était à un autre, et la
        ligne de Lea affichait p1 et ses clics sans rien dire, alors que le CONTRÔLE signale C6). Contrat C6(d) : le lien n'est PAS
        refusé (dans le doute, il reste compté sur la ligne) ; il est seulement signalé « à vérifier » quand aucun détenteur
        confirmé ne tranche sur les uid, que le nom connu du membre du lien n'a aucun mot commun avec le Gérant, ET que le doute est
        fondé : la fiche d'onboarding de la ligne a été écartée (Gérant changé à la main), ou le Gérant porte le nom d'un autre
        membre (même cas que le contrôle, « vu sur le seul nom »). Renvoie le nom du membre du lien, '' sinon."""
        if L.get("typ") != "clipper" or self.cat(lid) != "attribue":
            return ""
        uid = str((self.liens.get(lid) or {}).get("uid") or "")
        noms = self.noms_uid.get(uid) or set()
        if not uid or not noms:                                          # membre sans nom connu : rien pour en douter
            return ""
        props = L.get("detenteurs")
        if props is None:
            props = L["detenteurs"] = self.detenteurs(L["c"])
        if props:                                                        # détenteur confirmé : a_un_autre a tranché sur les uid
            return ""
        mots_g = _mots_nom(L["c"].get("gerant"))
        if noms & mots_g:
            return ""
        ecartee = bool(self.proprietaires.get(_cle(L["c"].get("handle"))))   # fiche présente mais écartée (Gérant ≠ détenteur)
        autre = bool(mots_g) and any(u != uid and (n & mots_g) for u, n in self.noms_uid.items())
        return (self.nom_uid(uid) or "un autre membre") if (ecartee or autre) else ""

    def cr_lien(self, lid, creatrices: set) -> str:
        """La créatrice d'un lien (prénom normalisé) : sa fiche (créatrice, créatrice suivie, nom GAML), sinon son domaine."""
        info = self.liens.get(lid) or {}
        for x in (info.get("creatrice"), info.get("suivi_creatrice"), info.get("nom")):
            p = _premier(x)
            if p and p in creatrices:
                return p
        domaine = re.sub(r"[^a-z0-9]", "", _url_cle(info.get("url")).split("/")[0])
        for cr in sorted(creatrices, key=len, reverse=True):
            if cr and cr in domaine:
                return cr
        return _premier(info.get("creatrice"))

    def clics_lien(self, lid) -> dict:
        """Les clics d'un lien : aujourd'hui (jusqu'au dernier relevé), hier, 7 jours finissant hier, les 7 jours d'avant (None si
        un jour manque, ou si le lien a été repris pendant la période d'avant : comparaison faussée)."""
        if lid in self._clics:
            return self._clics[lid]
        j0 = self.j0
        auj, t = _clics_aujourdhui(self.clics, lid, j0)
        r = {"auj": auj, "t_auj": t, "hier": _clics_lien(self.clics, lid, self.hier, self.hier),
             "c7": _clics_lien(self.clics, lid, j0 - timedelta(days=7), self.hier),
             "c7p": _clics_lien(self.clics, lid, j0 - timedelta(days=14), j0 - timedelta(days=8)), "depuis": None}
        dep = str((self.liens.get(lid) or {}).get("depuis") or "")[:10]
        if dep and dep > (j0 - timedelta(days=14)).isoformat():
            r["c7p"] = None
        if dep and dep > (j0 - timedelta(days=7)).isoformat():          # 09/10 (revue DASH) : 7 j raccourcis par la reprise, dit
            try:
                r["depuis"] = date.fromisoformat(dep)
            except ValueError:
                pass
        self._clics[lid] = r
        return r

    def bio_urls(self, cle) -> list:
        b = self.bios.get(cle) if isinstance(self.bios.get(cle), dict) else {}
        return [_url_cle(u) for u in (b.get("liens") or []) if _url_cle(u)]


def _somme(valeurs) -> tuple:
    """(somme des valeurs mesurées ou None, nombre mesuré, nombre total)."""
    vals = list(valeurs)
    mes = [v for v in vals if v is not None]
    return (sum(mes) if mes else None), len(mes), len(vals)


def _clics_de(ctx: _Ctx, lids) -> dict:
    """Clics cumulés de plusieurs liens (chacun compté une fois). Une période n'est comparée que si tous les liens sont mesurés
    sur les deux."""
    lids = list(dict.fromkeys(lids))
    cs = [ctx.clics_lien(l) for l in lids]
    out = {}
    for k in ("auj", "hier", "c7", "c7p"):
        out[k], out[k + "_n"], out[k + "_tot"] = _somme(c[k] for c in cs)
    complet = lids and all(c["c7"] is not None and c["c7p"] is not None for c in cs)
    out["delta"] = _delta_pct(out["c7"], out["c7p"]) if complet else ""
    out["comparable"] = bool(complet)
    deps = [c["depuis"] for c in cs if c.get("depuis") and c["c7"] is not None]
    out["depuis"] = max(deps) if deps else None
    out["repris"], out["n_liens"] = len(deps), len(lids)
    ts = [_instant(c["t_auj"]) for c in cs if c["auj"] is not None and _instant(c["t_auj"])]
    out["t_auj_min"] = min(ts) if ts else None
    return out


def _notes_clics(ctx: _Ctx, k: dict, heure: bool = False) -> list:
    """09/10 (revue DASH : « sommes partielles affichées comme complètes ») : ce qu'une somme de clics ne couvre pas, pour la colonne
    Mesure — « clics 7 j : 1/2 liens relevés », « clics hier : 1/2 », « clics du jour : 3/9 liens relus », « clics depuis le 06/10
    (lien repris) » ; `heure` : l'heure du relevé du jour le plus ancien s'il a plus de CLICS_VIEUX_MIN minutes (« clics du jour
    à 09h00 »)."""
    if not k:
        return []
    notes = []
    for cle, nom, verbe in (("c7", "clics 7 j", "relevés"), ("hier", "clics hier", "relevés"), ("auj", "clics du jour", "relus")):
        n, tot = k.get(cle + "_n"), k.get(cle + "_tot")
        if tot and n and n < tot:                                        # 0 lien mesuré : la cellule est vide, elle le dit déjà
            notes.append(f"{nom} : {n}/{tot} lien{'s' if tot > 1 else ''} {verbe if tot > 1 else verbe[:-1]}")
    if k.get("depuis"):
        if k.get("n_liens", 1) <= 1:
            notes.append(f"clics depuis le {k['depuis'].strftime('%d/%m')} (lien repris)")
        else:                                                            # une somme : la reprise ne raccourcit qu'une partie
            notes.append(f"{k['repris']} lien{'s' if k['repris'] > 1 else ''} repris dans la semaine (7 j raccourcis)")
    t = k.get("t_auj_min")
    if heure and t is not None and ctx.maintenant - t > timedelta(minutes=CLICS_VIEUX_MIN):
        notes.append(f"clics du jour à {_hm(t, ctx.j0)}")
    return notes


def _vues_mesurees(L: dict):
    """La contribution d'un compte à une somme de vues : (vues, mesuré ?) — un compte sans Reel publié dans la période compte pour
    une mesure (rien à additionner), un compte dont un Reel publié n'est pas mesuré à 48 h, non."""
    if L.get("vues_etat") == "complet":
        return L["vues"][0], True
    if L.get("vues_etat") == "aucun":
        return None, True
    return (L["vues"][0] if L.get("vues") else None), False


def _notes_sommes(lignes: list) -> list:
    """09/10 (revue DASH) : ce que les sommes Followers, Reels 7 j et Vues d'un groupe ne couvrent pas (« followers 2/3 ») —
    restreints, privés, non lus et Metricool compris ; les comptes « à créer » ne comptent pas.
    10/10 (revue DASH, restant 1 : « somme des vues partielle affichée sans mention quand aucun compte n'est mesuré en entier ») :
    la somme des vues additionne aussi les comptes PARTIELS (_vues_mesurees) ; « vues 0/2 » est donc écrit dès qu'une valeur est
    additionnée sans qu'aucun compte soit mesuré en entier — seule une somme vraiment vide (cellule vide) se passe de note."""
    base = [L for L in lignes if L.get("mesure_base") != "à créer"]
    if not base:
        return []
    notes = []
    for nom, mesure, valeur in (("followers", lambda L: L.get("followers") is not None, lambda L: L.get("followers")),
                                ("Reels 7 j", lambda L: L.get("r7") is not None, lambda L: L.get("r7")),
                                ("vues", lambda L: _vues_mesurees(L)[1], lambda L: _vues_mesurees(L)[0])):
        n = sum(1 for L in base if mesure(L))
        somme_vide = all(valeur(L) is None for L in base)                # la cellule de la somme reste vide : elle le dit déjà
        if n < len(base) and (n > 0 or not somme_vide):
            notes.append(f"{nom} {n}/{len(base)}")
    return notes


def _texte_partiel(notes_comptes: list, notes_clics: list) -> str:
    out = []
    if notes_comptes:
        out.append("partiel : " + ", ".join(notes_comptes))
    out += notes_clics
    return " · ".join(out)


# ------------------------------------------------------------------ comptes
def _mesure(ctx: _Ctx, L: dict) -> str:
    c, cle, serie = L["c"], L["cle"], L["serie"]
    if _norm(c.get("etat")) in onboarding.A_CREER:
        return "à créer"
    rels = [r for r in (serie.get("releves") or []) if isinstance(r, dict)]
    apify = sorted((r for r in rels if r.get("source") != "metricool" and _instant(r.get("t"))), key=lambda r: _instant(r["t"]))
    metri = [r for r in rels if r.get("source") == "metricool"
             and (_instant(r.get("t")) or ctx.maintenant) >= ctx.maintenant - timedelta(days=METRICOOL_RECENT_J)]
    hist = ctx.hist.get(cle) or []
    dernier_h = hist[-1] if hist and isinstance(hist[-1], dict) else {}
    suivi = ctx.non_lus.get(cle) if isinstance(ctx.non_lus.get(cle), dict) else None
    # absent au dernier scan quotidien, et aucun relevé lu depuis ce scan (un passage léger plus tard le même jour l'a peut-être lu)
    jour_h = str(dernier_h.get("jour") or "")[:10]
    scan = _instant(ctx.etats.get("scan_iso")) if str(ctx.etats.get("scan_iso") or "")[:10] == jour_h else None
    t_h = (scan or _instant(jour_h + "T00:00:00+00:00")) if jour_h else None
    t_a = _instant(apify[-1].get("t")) if apify else None
    absent_h = bool(dernier_h) and not dernier_h.get("existe") and (t_a is None or t_h is None or t_a <= t_h)
    # 09/10 (revue DASH : un compte relu par le passage léger de 14 h restait « non lu » toute la journée — `non_lus` n'est vidé que
    # par le passage complet) : l'entrée `non_lus` ne compte plus dès qu'un relevé Apify est postérieur au passage complet qui l'a
    # posée ; « non lu » reste vrai si le DERNIER passage (complet ou léger) ne l'a pas lu
    t_complet = _instant(ctx.etats.get("scan_iso")) or (_instant(ctx.dp.get("t")) if ctx.dp.get("mode") == "complet" else None)
    relu_depuis = t_a is not None and t_complet is not None and t_a > t_complet
    if cle in set(ctx.dp.get("non_lus") or []) or (suivi is not None and not relu_depuis):
        n = int((suivi or {}).get("jours") or 0)
        base = f"non lu ({n} passages)" if n >= 2 else "non lu"
    elif cle in set(ctx.dp.get("introuvables") or []) or absent_h:
        base = "introuvable"
    elif apify:
        last = apify[-1]
        base = "restreint" if last.get("restreint") else ("privé" if last.get("prive") else "lu")
    elif dernier_h:
        base = ("restreint" if dernier_h.get("restreint") else ("privé" if dernier_h.get("prive") else "lu")) \
            if dernier_h.get("existe") else "introuvable"
    else:
        base = ""
    if metri:
        base = f"{base} + Metricool" if base else "Metricool"
    if not base:
        base = "classeur" if L["followers_source"] == "classeur" else "jamais lu"
    if cle in set(ctx.dp.get("suspects") or []):
        base += " · followers suspects"
    if cle in set(ctx.dp.get("reels_non_lus") or []):
        base += " · Reels non lus"
    return base


def _releve(ctx: _Ctx, L: dict) -> str:
    rels = [r for r in (L["serie"].get("releves") or []) if isinstance(r, dict) and _instant(r.get("t"))]
    if rels:
        last = max(rels, key=lambda r: _instant(r["t"]))
        if last.get("source") == "metricool":                             # photo de la nuit : la veille de son heure
            return "Metricool " + (_paris(_instant(last["t"])) - timedelta(minutes=1)).strftime("%d/%m")
        return _hm(last["t"], ctx.j0)
    der = _serie("derniere_lecture", L["cle"])
    if der:
        return _hm(der, ctx.j0)
    hist = ctx.hist.get(L["cle"]) or []
    if hist and isinstance(hist[-1], dict) and hist[-1].get("jour"):
        try:
            return "scan " + date.fromisoformat(str(hist[-1]["jour"])[:10]).strftime("%d/%m")
        except ValueError:
            return ""
    return ""


def _chiffres_compte(ctx: _Ctx, L: dict):
    """Followers, écarts, Reels, vues : la série d'abord (contrat C1), les cellules du classeur en repli (jamais 0 par défaut)."""
    c, cle = L["c"], L["cle"]
    j0 = ctx.j0
    L["serie"] = (_serie("serie", cle) or {}) if ctx.seriesok else {}
    notes = []
    f = _serie("followers_a", cle) if ctx.seriesok else None
    L["followers_source"] = "série" if f is not None else ""
    if f is not None:
        # 09/10 (revue DASH : un followers de 5 ou 15 jours affiché « lu » avec l'heure du jour) : l'heure du relevé qui a FOURNI les
        # followers (même choix que series.followers_a : le plus récent, Metricool d'abord à la même heure). Plus vieux que le
        # dernier relevé Apify du compte (relu, followers illisibles ou restreint) : la date est écrite dans la Mesure ; au-delà de
        # FOLLOWERS_PERIME_J jours, la cellule reste vide (« followers non lus depuis JJ/MM »), jamais un vieux chiffre pour frais.
        rels = [r for r in (L["serie"].get("releves") or []) if isinstance(r, dict) and _instant(r.get("t"))
                and _instant(r.get("t")) <= ctx.maintenant]
        avec = [r for r in rels if isinstance(r.get("followers"), int) and not isinstance(r.get("followers"), bool)]
        r_f = max(avec, key=lambda r: (_instant(r["t"]), r.get("source") == "metricool")) if avec else None
        t_f = _instant(r_f["t"]) if r_f else None
        t_apify = max((_instant(r["t"]) for r in rels if r.get("source") != "metricool"), default=None)
        if t_f is not None and t_apify is not None and t_f < t_apify:
            if ctx.maintenant - t_f > timedelta(days=FOLLOWERS_PERIME_J):
                f = None
                notes.append(f"followers non lus depuis le {_paris(t_f):%d/%m}")
            elif r_f.get("source") == "metricool":                      # photo de la nuit : le jour des données
                notes.append(f"followers Metricool {(_paris(t_f) - timedelta(minutes=1)):%d/%m}")
            else:
                notes.append(f"followers {_hm(t_f, j0)}")
    else:
        f = _entier(c.get("followers"))
        L["followers_source"] = "classeur" if f is not None else ""
    L["followers"] = f
    L["df24"] = _serie("delta_followers", cle, 24) if ctx.seriesok else None
    L["df7"] = _serie("delta_followers", cle, 168) if ctx.seriesok else None
    m0, m1, m7, m14 = _minuit(j0), _minuit(j0 - timedelta(days=1)), _minuit(j0 - timedelta(days=7)), _minuit(j0 - timedelta(days=14))
    rh = _serie("reels_publies", cle, m1, m0) if ctx.seriesok else None
    r7 = _serie("reels_publies", cle, m7, m0) if ctx.seriesok else None
    L["r7p"] = _serie("reels_publies", cle, m14, m7) if ctx.seriesok else None
    # repli : les cellules Reels du classeur, seulement si le scan du jour a lu ce compte en entier (sinon la cellule porte un autre
    # jour : critique du 09/10, « Reels hier » de l'avant-veille affiché sans le dire). 09/10 (revue DASH : entre 0 h et 2 h à Paris,
    # la date UTC est encore la veille, et la cellule du scan d'hier — qui compte l'avant-veille — passait pour « hier ») : la
    # cellule n'est reprise que si le passage complet qui l'a écrite (scan_iso) a le même « hier » que le Dashboard, en heure de
    # Paris, et si l'entrée d'historique est bien celle de ce passage.
    hist = ctx.hist.get(cle) or []
    d_h = hist[-1] if hist and isinstance(hist[-1], dict) else {}
    scan = _instant(ctx.etats.get("scan_iso")) or (_instant(ctx.dp.get("t")) if ctx.dp.get("mode") == "complet" else None)
    lu_du_jour = (scan is not None and _paris(scan).date() == j0
                  and str(d_h.get("jour") or "")[:10] == scan.astimezone(timezone.utc).strftime("%Y-%m-%d")
                  and d_h.get("existe") and not d_h.get("restreint") and not d_h.get("prive") and not d_h.get("reels_non_lus"))
    L["r7_serie"] = r7 is not None                                      # Δ Reels : deux périodes de la même source
    if rh is None and lu_du_jour:
        rh = _entier(c.get("reels_hier"))
    if r7 is None and lu_du_jour:
        r7 = _entier(c.get("reels_7j"))
    L["rh"], L["r7"] = rh, r7
    # vues à âge fixe : 09/10 (revue DASH : un seul passage manqué retirait un Reel de la somme, faux « ▼ 33 % » en tête des
    # baisses) — une période n'est « complète » que si chaque Reel publié (reels_publies) est mesuré à 48 h (2e valeur du C1) ;
    # Δ vues et tendance seulement entre deux périodes complètes, sinon la Mesure dit « vues 2/3 Reels ».
    a0, a1 = _minuit(j0 - timedelta(days=9)), _minuit(j0 - timedelta(days=2))
    b0, b1 = _minuit(j0 - timedelta(days=16)), _minuit(j0 - timedelta(days=9))
    vA = _serie("vues_age_fixe", cle, a0, a1, AGE_VUES_H) if ctx.seriesok else None
    vB = _serie("vues_age_fixe", cle, b0, b1, AGE_VUES_H) if ctx.seriesok else None
    pA = _serie("reels_publies", cle, a0, a1) if ctx.seriesok else None
    pB = _serie("reels_publies", cle, b0, b1) if ctx.seriesok else None
    L["vues"] = tuple(vA) if vA else None
    L["vues_p"] = tuple(vB) if vB else None

    def etat_vues(v, p):
        if v and isinstance(p, int) and v[1] >= p:
            return "complet"
        if not v and p == 0:
            return "aucun"
        return "partiel" if v else "non mesuré"
    L["vues_etat"], L["vues_p_etat"] = etat_vues(L["vues"], pA), etat_vues(L["vues_p"], pB)
    L["vues_comparable"] = L["vues_etat"] == "complet" and L["vues_p_etat"] == "complet"
    if L["vues_etat"] == "partiel":
        notes.append(f"vues {L['vues'][1]}/{pA if isinstance(pA, int) else '?'} Reels mesurés à 48 h")
    base = _mesure(ctx, L)
    L["mesure_base"] = base
    if base == "à créer":
        notes = []
    elif L["followers_source"] == "classeur" and base != "classeur":
        notes.insert(0, "followers : classeur")
    L["mesure_notes"] = notes
    L["mesure"] = " · ".join([base] + notes)
    L["releve"] = _releve(ctx, L)


def _resoudre_liens(ctx: _Ctx, lignes: list, creatrices: set):
    """Quel lien chaque ligne porte. Une ligne porte les liens de sa cellule « Lien GAML associé » qui lui reviennent (catégorie
    permise pour son type, même créatrice), sinon celui de sa bio ; un lien porté par plusieurs lignes d'un même Gérant (le trio)
    est compté sur une seule : la bio qui l'affiche, sinon le compte privé, sinon la première ligne. Renvoie {lid: ligne porteuse}."""
    candidats = {}
    for L in lignes:
        L.update({"ok": [], "ko": [], "inconnus": [], "trio": [], "ailleurs": [], "portes": [], "bio": False, "attaches": []})
        for u in _urls(L["c"].get("lien_gaml")):
            lid = ctx.par_url.get(u)
            if lid is None:
                L["inconnus"].append(u)
                continue
            cat = ctx.cat(lid)
            cr = ctx.cr_lien(lid, creatrices)
            autre = L["typ"] == "clipper" and cat == "attribue" and ctx.a_un_autre(lid, L)
            if cat in AUTORISES[L["typ"]] and (not cr or cr == L["cr"]) and not autre:
                if lid not in L["ok"]:
                    L["ok"].append(lid)
                    candidats.setdefault(lid, []).append(L)
            elif lid not in [x for x, _ in L["ko"]]:
                L["ko"].append((lid, "autre clipper" if autre else ("autre créatrice" if cat in AUTORISES[L["typ"]] else cat)))
    maison = {lid: cands[0]["groupe"] for lid, cands in candidats.items()}   # le groupe dont la cellule porte le lien
    for L in lignes:                                                     # pas de lien en cellule : celui de la bio
        if L["ok"] or L["typ"] == "libre":
            continue
        for u in ctx.bio_urls(L["cle"]):
            lid = ctx.par_url.get(u)
            if lid is None:
                continue
            cr = ctx.cr_lien(lid, creatrices)
            cat = ctx.cat(lid)
            autre = L["typ"] == "clipper" and cat == "attribue" and ctx.a_un_autre(lid, L)
            if cat in AUTORISES[L["typ"]] and (not cr or cr == L["cr"]) and not autre:
                L["ok"].append(lid)
                L["bio"] = lid not in maison                             # « (bio) » seulement quand aucune cellule ne le porte
                candidats.setdefault(lid, []).append(L)
            elif cat not in ("page",) or L["typ"] == "clipper":          # la bio affiche un lien qui n'est pas le sien : dit, jamais compté
                L.setdefault("bio_ko", []).append((lid, "autre clipper" if autre else ("autre créatrice" if cat in AUTORISES[L["typ"]] else cat)))
    porte_par = {}
    for lid, cands in candidats.items():
        u = _url_cle((ctx.liens.get(lid) or {}).get("url"))
        # le groupe dont la cellule porte le lien d'abord (une bio ailleurs ne lui prend jamais ses clics), puis la bio qui l'affiche,
        # puis le compte privé, puis l'ordre du classeur
        cands = sorted(cands, key=lambda L: (maison.get(lid, L["groupe"]) != L["groupe"], u not in ctx.bio_urls(L["cle"]),
                                             not _est_prive(L["c"]), L["ordre"]))
        porteur = cands[0]
        porte_par[lid] = porteur
        porteur["portes"].append(lid)
        for L in cands[1:]:
            (L["trio"] if L["groupe"] == porteur["groupe"] else L["ailleurs"]).append((lid, porteur))
    return porte_par


def _grouper(lignes: list, ctx: _Ctx):
    """Clé de groupe de chaque ligne : la créatrice ; « libre » ; « m|Gérant » (Metricool) ; « g|Gérant|uid » (clipper — deux
    clippers du même prénom, deux uid de liens : deux groupes, signalés homonymes)."""
    uids = {}
    for L in lignes:
        if L["typ"] == "clipper":
            for u in _urls(L["c"].get("lien_gaml")):
                lid = ctx.par_url.get(u)
                uid = str((ctx.liens.get(lid) or {}).get("uid") or "") if lid else ""
                if uid and not ctx.a_un_autre(lid, L):   # le lien d'un autre ne fait pas un homonyme
                    L.setdefault("uids", []).append(uid)
                    uids.setdefault((L["cr"], _norm(L["c"].get("gerant"))), set()).add(uid)
    for L in lignes:
        g = _norm(L["c"].get("gerant"))
        if L["typ"] == "creatrice":
            L["groupe"] = "crea"
        elif L["typ"] == "libre":
            L["groupe"] = "libre"
        elif L["typ"] == "metricool":
            L["groupe"] = f"m|{g}"
        else:
            tous = sorted(uids.get((L["cr"], g), set()))
            siens = L.get("uids") or []
            if len(tous) <= 1:
                L["groupe"] = f"g|{g}|{tous[0] if tous else ''}"
            else:
                L["groupe"] = f"g|{g}|{siens[0] if siens else '?'}"
                L["homonyme"] = True


# ------------------------------------------------------------------ construction des lignes
def _ligne_vide() -> list:
    return [""] * NB


def construire(e: dict, maintenant: datetime = None) -> dict:
    """Pur (lectures de séries comprises) : les lignes de l'onglet, le type de chaque ligne (pour la mise en forme), les fusions,
    l'empreinte du contenu (sans l'heure du titre). Entrées : comptes, etats, clics, registre, onboarding, membres, masques,
    metricool (état du lot METRICOOL, facultatif)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    ctx = _Ctx(e, maintenant)
    comptes = [c for c in (e.get("comptes") or []) if isinstance(c, dict)]
    creatrices = onboarding.creatrices_connues(comptes)
    masques = {_norm(x) for x in (e.get("masques") or []) if str(x).strip()}
    rows, kinds = [], []

    def ajouter(r, kind, **info):
        rows.append((list(r) + [""] * NB)[:NB] if r else [])
        kinds.append({"kind": kind, **info})

    # -------- les comptes montrés
    ordre_cr, comptes_l, masques_l, hors = [], [], [], {}
    for i, c in enumerate(comptes):
        if not c.get("handle"):
            continue
        typ = _type_ligne(c, creatrices)
        cr = _premier(c.get("creatrice") or c.get("onglet")) or "?"
        if cr not in ordre_cr:
            ordre_cr.append(cr)
        e_n = _norm(c.get("etat"))
        h = hors.setdefault(cr, {"vivier": 0, "ban": 0, "masques": 0})
        if typ == "libre" and e_n in onboarding.A_CREER:
            h["vivier"] += 1                                             # comptes d'avance : comptés au bandeau, pas montrés
            continue
        if typ == "libre" and e_n == "ban":
            h["ban"] += 1                                                # BAN rendus (sans Gérant) : comptés au bandeau
            continue
        nom_cr = (str(c.get("creatrice") or c.get("onglet") or "").split() or ["?"])[0]
        L = {"c": c, "typ": typ, "cr": cr, "cr_nom": nom_cr, "cle": _cle(c["handle"]), "ordre": i}
        if _norm(c.get("gerant")) in masques:
            # 09/10 (revue DASH : masquer un Gérant faisait passer ses liens en « ⚠ Sans ligne » et le bouclage en écart bloquant) :
            # ses lignes ne sont pas montrées, mais leurs liens sont résolus comme les autres et rangés dans le seau « masqués »
            h["masques"] += 1
            L["masque"] = True
            masques_l.append(L)
            continue
        comptes_l.append(L)
    tous_l = comptes_l + masques_l
    _grouper(tous_l, ctx)
    porte_par = _resoudre_liens(ctx, tous_l, creatrices)
    for L in comptes_l:
        _chiffres_compte(ctx, L)
    # liens attribués au même clipper (même uid, même créatrice) qu'aucune ligne ne porte : sur la ligne porteuse de son groupe
    actifs = {lid for lid in ctx.liens if ctx.cat(lid) not in INACTIFS}
    porteur_uid = {}
    for lid, L in porte_par.items():
        uid = str((ctx.liens.get(lid) or {}).get("uid") or "")
        if uid:
            porteur_uid.setdefault((uid, L["cr"]), L)
    for lid in sorted(actifs - set(porte_par)):
        uid = str((ctx.liens.get(lid) or {}).get("uid") or "")
        if ctx.cat(lid) != "attribue" or not uid:
            continue
        cr = ctx.cr_lien(lid, creatrices)
        if cr:
            L = porteur_uid.get((uid, cr))
        else:                                                            # créatrice inconnue : seulement si le clipper n'a qu'une ligne porteuse
            siens = [v for k, v in porteur_uid.items() if k[0] == uid]
            L = siens[0] if len(siens) == 1 else None
        if L is not None:
            L["attaches"].append(lid)
            porte_par[lid] = L
    for L in tous_l:
        L["lids"] = L["portes"] + L["attaches"]
        L["clics"] = _clics_de(ctx, L["lids"]) if L["lids"] and not L.get("masque") else None
    lids_lignes = sorted(lid for lid, L in porte_par.items() if not L.get("masque"))
    lids_masques = sorted(lid for lid, L in porte_par.items() if L.get("masque"))

    # -------- liens restants, par créatrice : pages, libérés / hors clipping, attribués sans ligne ; liens des Gérants masqués
    restes = {}
    vide_r = lambda: {"pages": [], "liberes": [], "sans_ligne": [], "masques": []}   # noqa: E731
    for lid in lids_masques:
        cr = porte_par[lid]["cr"]
        restes.setdefault(cr if cr in ordre_cr else "", vide_r())["masques"].append(lid)
    for lid in sorted(actifs - set(porte_par)):
        cr = ctx.cr_lien(lid, creatrices)
        cr = cr if cr in ordre_cr else ""
        cat = ctx.cat(lid)
        # 09/10 (revue DASH) : un lien « suivi » ou « non_attribue » (lien de clipping sans détenteur) qu'aucune ligne ne porte est
        # un lien de clipper perdu, comme pour le bouclage : « ⚠ Sans ligne », jamais rangé avec les pages ou les libérés
        seau = "pages" if cat == "page" else ("liberes" if cat in ("libere", "hors_clipping") else "sans_ligne")
        restes.setdefault(cr, vide_r())[seau].append(lid)
    tout = _clics_de(ctx, sorted(actifs)) if actifs else {}               # tous les liens actifs, chacun une fois (= le TOTAL)

    # -------- tendances
    tend = {"vues": [], "clics": [], "followers": []}
    for L in comptes_l:
        qui = (L["c"].get("gerant") or "sans Gérant").strip()
        if L["vues_comparable"]:                                         # chaque Reel publié mesuré à 48 h, sur les deux périodes
            tend["vues"].append((L["vues"][0] - L["vues_p"][0], L["c"]["handle"], qui, L["cr_nom"], _delta_pct(L["vues"][0], L["vues_p"][0]),
                                 L["vues"][0], L["vues_p"][0]))
        if L["clics"] and L["clics"]["comparable"]:
            k = L["clics"]
            tend["clics"].append((k["c7"] - k["c7p"], " + ".join(_slug(ctx.liens[x], x) for x in L["lids"]), qui, L["cr_nom"], k["delta"],
                                  k["c7"], k["c7p"]))
        if L["df7"] is not None and L["followers"] is not None:
            tend["followers"].append((L["df7"], L["c"]["handle"], qui, L["cr_nom"], _delta_abs(L["df7"]), L["followers"],
                                      L["followers"] - L["df7"]))

    # -------- titre, fraîcheur et alertes (09/10, revue DASH : une alerte budget Apify ou Metricool a sa propre ligne, « ⛔ » / « ⚠ »
    # en tête de cellule — la mise en forme conditionnelle la colore, lisible au téléphone sans faire défiler le titre)
    p = ctx.p
    fraicheur, alertes = _fraicheur(ctx, e, comptes_l)
    ajouter(["Dashboard · mis à jour le " + p.strftime("%d/%m à %Hh%M") + " (Paris)", "", fraicheur], "titre")
    for quoi, gravite, texte in alertes:
        ajouter([quoi, "", texte], "alerte", gravite=gravite)
    ajouter(["", "", "Clics = visites payables GAML (pays francophones) · Vues = vues Instagram des Reels, relevées 48 h après la "
             "publication · cellule vide = pas mesuré (jamais 0 par défaut) · ▲ ▼ = contre les 7 jours d'avant · Mesure = d'où vient "
             "le chiffre (« k/n » : somme qui ne couvre pas tout)"], "legende")
    ajouter([], "vide")

    # -------- CONTRÔLE
    n_anomalies = _section_controle(ajouter, ctx, e, comptes, lids_lignes, lids_masques, tout)
    ajouter([], "vide")

    # -------- TENDANCES
    _section_tendances(ajouter, ctx, tend, len(comptes_l))
    ajouter([], "vide")

    # -------- COMPTES par créatrice
    tot = {"comptes": 0, "lignes": [], "lids": []}
    for cr in ordre_cr + ([""] if restes.get("") else []):
        lignes_cr = [L for L in comptes_l if L["cr"] == cr] if cr else []
        r_cr = restes.get(cr, vide_r())
        if cr and not lignes_cr and not any(r_cr.values()) and not any((hors.get(cr) or {}).values()):
            continue
        _bloc_creatrice(ajouter, ctx, cr, lignes_cr, r_cr, hors.get(cr) or {}, tot)
        ajouter([], "vide")
    r = _ligne_vide()
    r[C_GERANT], r[C_HANDLE] = "TOTAL", f"{tot['comptes']} comptes"
    r[C_FOL] = _v(_somme(L["followers"] for L in tot["lignes"])[0])
    r[C_R7] = _v(_somme(L["r7"] for L in tot["lignes"])[0])
    r[C_V7] = _v(_somme(_vues_mesurees(L)[0] for L in tot["lignes"])[0])
    if tout:
        r[C_CA], r[C_CH], r[C_C7] = _v(tout["auj"]), _v(tout["hier"]), _v(tout["c7"])
        r[C_DC] = tout["delta"]
        r[C_LIEN] = f"{len(set(tot['lids']))} liens actifs"
    r[C_MES] = _texte_partiel(_notes_sommes(tot["lignes"]), _notes_clics(ctx, tout))
    ajouter(r, "total")

    # 09/10 (revue DASH : la fraîcheur du titre était hors empreinte — des clics relus sans changement laissaient au titre l'heure
    # de la réécriture d'avant) : l'empreinte porte tout sauf « mis à jour le … » (l'heure de l'écriture elle-même)
    contenu = json.dumps([DASHBOARD_VERSION, rows[0][1:]] + rows[1:], ensure_ascii=False, default=str)
    return {"lignes": rows, "types": kinds, "empreinte": hashlib.sha1(contenu.encode("utf-8")).hexdigest()[:20],
            "comptes": len(comptes_l), "anomalies": n_anomalies, "lids_lignes": lids_lignes, "lids_masques": lids_masques}


def _v(x):
    return "" if x is None else x


def _montant(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
        return None
    return float(v)


def _euros(x) -> str:
    """« 12,30 » ; un montant rond sans décimales (« 25 »)."""
    return (f"{x:.0f}" if abs(x - round(x)) < 0.005 else f"{x:.2f}").replace(".", ",")


def _mois_suivant(d: datetime) -> datetime:
    a, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=a, month=m, day=min(d.day, calendar.monthrange(a, m)[1]))


def budget_apify(b: dict, maintenant: datetime = None):
    """Contrat C6(a) lu par le Dashboard : {usage, budget, trajectoire, coupe, atteint, leger_ok, fin, t, source, cout_leger (facultatif :
    `cout_leger_usd` du lot SCAN, None s'il manque)} ; None si le budget
    n'a jamais été lu. Budget = `budget_usd` (APIFY_BUDGET_MOIS du lot SCAN, défaut 25 $) ; un état d'avant le C6 (sans
    budget_usd, trajectoire_usd ni coupe) est lu avec le même budget et la trajectoire linéaire calculée à l'heure du relevé."""
    b = b if isinstance(b, dict) else {}
    usage = _montant(b.get("usage_usd"))
    if usage is None:
        return None
    maintenant = maintenant or datetime.now(timezone.utc)
    budget = _montant(b.get("budget_usd")) or APIFY_BUDGET_MOIS
    t = _instant(b.get("t")) or maintenant
    d0, d1 = _instant(b.get("cycle_debut") or b.get("debut")), _instant(b.get("cycle_fin") or b.get("fin"))
    if not (d0 and d1 and d1 > d0):
        d0 = t.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        d1 = _mois_suivant(d0)
    traj = _montant(b.get("trajectoire_usd"))
    if traj is None:
        traj = budget * min(1.0, max(0.0, (t - d0).total_seconds() / (d1 - d0).total_seconds()))
    coupe = b.get("coupe") if isinstance(b.get("coupe"), bool) else None
    return {"usage": usage, "budget": budget, "trajectoire": traj, "coupe": coupe, "atteint": usage >= budget - 1e-9,
            "leger_ok": b.get("leger_ok", b.get("ok")), "fin": d1, "t": t, "source": str(b.get("source") or ""),
            "cout_leger": _montant(b.get("cout_leger_usd"))}                  # facultatif (lot SCAN) : coût d'une relecture légère


def _fraicheur_apify(ctx: _Ctx) -> tuple:
    """(texte du titre, alerte ou None). 09/10 (revue DASH, décision de Gaëtan « Dépasse pas 25 $ / mois ») : la dépense est
    rapportée au BUDGET de 25 $ (avant : à la limite du compte Apify, 25,20 $ dépensés sur 29 $ s'affichaient sans alerte) ;
    « ⛔ Apify coupé jusqu'au JJ/MM » à 100 % ; « ⚠ » dès que la dépense dépasse la trajectoire linéaire du budget, ou dès que la
    garde du lot SCAN saute les relectures légères (`leger_ok` faux : dépense + une relecture au-dessus de la trajectoire)."""
    st = budget_apify(ctx.etats.get("apify_budget"), ctx.maintenant)
    if st is None:
        return "Apify : budget pas encore lu", None
    u, bud = _euros(st["usage"]), _euros(st["budget"])
    local = " (compté par le bot)" if st["source"] == "local" else ""
    fin = _paris(st["fin"]).strftime("%d/%m")
    if st["coupe"] or (st["coupe"] is None and st["atteint"]):
        coupe = bool(st["coupe"])
        titre = f"⛔ Apify coupé jusqu'au {fin} ({u} $ / {bud} $)" if coupe else f"⛔ Apify {u} $ / {bud} $ : budget atteint"
        texte = (f"budget Apify du mois atteint : {u} $ dépensés sur {bud} $ (décision de Gaëtan){local}"
                 + (f" — plus aucun appel Apify jusqu'au {fin} : followers, Reels et vues restent à leur dernier relevé (colonne "
                    "Relevé)" if coupe else ""))
        return titre, ("⛔ Apify", "bloquant", texte)
    if st["atteint"]:                                                     # coupe=False malgré tout : dit quand même
        return f"⛔ Apify {u} $ / {bud} $ : budget atteint", ("⛔ Apify", "bloquant", f"budget Apify du mois atteint : {u} $ sur {bud} ${local}")
    saute = " : relectures légères sautées" if st["leger_ok"] is False else ""
    if st["usage"] > st["trajectoire"] + 1e-9:
        texte = (f"{u} $ dépensés sur {bud} $, au-dessus de la trajectoire du budget ({_euros(st['trajectoire'])} $ au "
                 f"{_paris(st['t']):%d/%m}){local}" + saute)
        return f"⚠ Apify {u} $ / {bud} ${saute}", ("⚠ Apify", "important", texte)
    if saute:
        # 10/10 (revue DASH, restant 2 : la garde du lot SCAN saute la relecture légère dès que la dépense PLUS une relecture
        # dépasserait la trajectoire — la dépense seule peut rester dessous, et le Dashboard ne disait plus rien) : dit au titre
        # et en ligne d'alerte, même sous la trajectoire
        cout = f" + {_euros(st['cout_leger'])} $ par relecture" if st.get("cout_leger") else " + une relecture"
        texte = (f"relectures légères sautées : {u} $ dépensés{cout} dépasseraient la trajectoire du budget de {bud} $ "
                 f"({_euros(st['trajectoire'])} $ au {_paris(st['t']):%d/%m}){local} — les comptes ne sont relus qu'au passage "
                 "complet du matin (colonne Relevé) tant que la trajectoire n'a pas rattrapé la dépense")
        return f"⚠ Apify {u} $ / {bud} ${saute}", ("⚠ Apify", "important", texte)
    return f"Apify {u} $ / {bud} ${local}", None


def _fraicheur_metricool(ctx: _Ctx, e: dict, comptes_l: list) -> tuple:
    """(texte du titre, alerte ou None). 09/10 (revue DASH, contrat C6b : avant, « Metricool J-1 » s'affichait d'après le jour du
    dernier passage TENTÉ, même raté) : l'âge vient du dernier passage RÉUSSI (`jour`, `dernier_ok`) ; un passage en erreur
    → « ⚠ Metricool en échec depuis JJ/MM » (JJ/MM : dernier passage réussi). Un état d'avant le C6 (sans `jour_essai`, où
    `jour` est celui du dernier essai) est lu d'après `dernier_ok`."""
    met = e.get("metricool") if isinstance(e.get("metricool"), dict) else {}
    erreur = str(met.get("erreur") or "").strip()
    ok = _instant(met.get("dernier_ok"))
    nouveau = "jour_essai" in met
    jour = str(met.get("jour") or "")[:10]
    lus_vides = isinstance(met.get("lus"), list) and not met.get("lus") and bool(met.get("t") or jour)
    echec = bool(erreur) or (not nouveau and lus_vides)
    if echec and not nouveau:                                            # ancien état : `jour` = veille du dernier ESSAI
        jour = (_paris(ok).date() - timedelta(days=1)).isoformat() if ok else ""
    if not jour and not echec and ctx.seriesok:                          # sans état : le dernier relevé Metricool des séries
        ts = [_instant(r.get("t")) for L in comptes_l for r in (L.get("serie") or {}).get("releves") or []
              if isinstance(r, dict) and r.get("source") == "metricool" and _instant(r.get("t"))]
        if ts:
            jour = (_paris(max(ts)) - timedelta(minutes=1)).date().isoformat()
    try:
        j = date.fromisoformat(jour) if jour else None
    except ValueError:
        j = None
    if echec:
        donnees = f" (données du {j:%d/%m})" if j else ""
        if ok is None:
            return f"⚠ Metricool en échec (aucun passage réussi){donnees}", \
                ("⚠ Metricool", "important", "en échec, aucun passage réussi" + (f" : {erreur[:140]}" if erreur else ""))
        depuis = _paris(ok).strftime("%d/%m")
        texte = (f"en échec depuis le {depuis} (dernier passage réussi à {_paris(ok):%Hh%M})" + (f" : {erreur[:140]}" if erreur else
                 " : aucun compte lu") + (f" — les comptes Metricool gardent les chiffres du {j:%d/%m}" if j else ""))
        return f"⚠ Metricool en échec depuis {depuis}{donnees}", ("⚠ Metricool", "important", texte)
    if j is not None:
        ecart = (ctx.j0 - j).days
        if ecart < 1:
            return "Metricool du jour", None
        txt = f"Metricool J-{ecart} ({j:%d/%m})"
        return ("⚠ " + txt) if ecart >= METRICOOL_VIEUX_J else txt, None
    if metricool_comptes is None and not met:
        return "Metricool : source indisponible", None
    return "Metricool : aucun relevé", None


def _fraicheur(ctx: _Ctx, e: dict, comptes_l: list) -> tuple:
    """(« Instagram 14h05 · Clics 16h45 · Metricool J-1 (08/10) · Apify 12,30 $ / 25 $ », [alertes (quoi, gravité, texte)]) : l'âge
    de chaque source, et ce qui mérite une ligne d'alerte sous le titre."""
    parts, alertes = [], []
    ts_ig = [t for t in (_instant(x) for x in ((ctx.dp or {}).get("t"), ctx.etats.get("leger_iso"), ctx.etats.get("scan_iso"))) if t]
    parts.append("Instagram " + (_hm(max(ts_ig), ctx.j0) if ts_ig else "jamais lu"))
    # 09/10 (revue DASH : « Clics 16h45 » quand un autre lien n'avait pas été relu depuis 09h00) : l'heure du relevé le plus ancien
    # des liens actifs relus aujourd'hui aussi, s'il a plus de CLICS_VIEUX_MIN minutes de retard sur le plus récent
    ts_cl = [t for t in (_instant(v.get("t")) for lid, v in (ctx.clics.get("aujourdhui") or {}).items()
                         if isinstance(v, dict) and str(v.get("jour") or "") == ctx.j0.isoformat()
                         and str(lid) in ctx.liens and ctx.cat(str(lid)) not in INACTIFS) if t]
    if ts_cl:
        t0, t1 = min(ts_cl), max(ts_cl)
        parts.append("Clics " + (_hm(t1, ctx.j0) if t1 - t0 <= timedelta(minutes=CLICS_VIEUX_MIN)
                                 else f"{_hm(t0, ctx.j0)} → {_hm(t1, ctx.j0)}"))
    else:
        jours = sorted(j for v in (ctx.clics.get("jours") or {}).values() if isinstance(v, dict) for j in v
                       if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(j)))
        parts.append("Clics jusqu'au " + date.fromisoformat(jours[-1]).strftime("%d/%m") if jours else "Clics : aucun relevé")
    txt, alerte = _fraicheur_metricool(ctx, e, comptes_l)
    parts.append(txt)
    if alerte:
        alertes.append(alerte)
    if not ctx.seriesok:
        parts.append("séries indisponibles (chiffres des cellules du classeur)")
    txt, alerte = _fraicheur_apify(ctx)
    parts.append(txt)
    if alerte:
        alertes.insert(0, alerte)
    return " · ".join(parts), alertes


def _appel_bouclage(ctx: _Ctx, lids_lignes: list, lids_masques: list):
    """controle.bouclage sur la fenêtre du Dashboard (`fin` = hier, heure de Paris : les deux totaux portent sur les mêmes jours)
    avec le seau « masqués » (09/10, revue DASH). Contrat plus ancien sans `masques` : les liens masqués comptent avec les lignes
    (jamais en écart) ; sans `fin` : la fenêtre du contrôle."""
    essais = ([{"fin": ctx.hier, "masques": list(lids_masques)}] if lids_masques else []) + [{"fin": ctx.hier}, {}]
    for i, kw in enumerate(essais):
        lignes = list(lids_lignes) + ([] if "masques" in kw else list(lids_masques))
        try:
            return controle.bouclage(ctx.clics, lignes, **kw)
        except TypeError:
            if i == len(essais) - 1:                                     # aucune signature ne passe : erreur dite, jamais tue
                raise
    return None


def _section_controle(ajouter, ctx: _Ctx, e: dict, comptes: list, lids_lignes: list, lids_masques: list = (), tout: dict = None):
    """CONTRÔLE (contrat C3) : compteur par famille, les 15 premières anomalies, bouclage des visites 7 j. Renvoie le nombre
    d'anomalies, None si la source manque. 09/10 (revue DASH) : une famille qui n'a pas pu juger (anomalie « non_mesure » du
    contrôle) est dite « non mesuré », jamais « sans anomalie » ni ✅ ; le bouclage n'a ✅ que si tous les liens sont mesurés, sans
    écart, ET si son total concorde avec le TOTAL Clics 7 j du Dashboard (contrat C6e : une seule règle des visites)."""
    if controle is None or not callable(getattr(controle, "anomalies", None)):
        ajouter(["CONTRÔLE", "", "source indisponible (module controle absent) : attribution non vérifiée"], "section")
        return None
    series_etat = {"v": 1, "comptes": {}, "alias": {}}
    if ctx.seriesok:
        for c in comptes:
            k = _cle(c.get("handle"))
            if k and k not in series_etat["comptes"]:
                s = _serie("serie", k)
                if s:
                    series_etat["comptes"][k] = s
    args = (comptes, ctx.clics, e.get("onboarding") or {}, e.get("registre") or {}, e.get("membres"), series_etat)
    try:
        try:
            toutes = controle.anomalies(*args, etats=ctx.etats, maintenant=ctx.maintenant)
        except TypeError:                                                # contrat strict : six arguments
            toutes = controle.anomalies(*args)
        toutes = [a for a in toutes or [] if isinstance(a, dict)]
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Dashboard : contrôle illisible (%s)", erreur)
        ajouter(["CONTRÔLE", "", f"source indisponible (erreur du contrôle : {type(erreur).__name__})"], "section")
        return None
    an = [a for a in toutes if not a.get("non_mesure")]
    nm_f = {}
    for a in toutes:
        if a.get("non_mesure"):
            nm_f.setdefault(str(a.get("famille") or "?"), re.sub(r"^non mesuré : ", "", str(a.get("texte") or "")))
    rang = lambda f: int(f[1:]) if f[1:].isdigit() else 99              # noqa: E731
    n = {g: sum(1 for a in an if a.get("gravite") == g) for g in GRAVITES}
    if an:
        tete = (f"{len(an)} anomalie(s) : {n['bloquant']} bloquante(s), {n['important']} importante(s), {n['info']} info"
                " · rien n'est corrigé tout seul : à trancher dans le classeur ou dans GAML")
        if nm_f:
            tete += " · non mesuré : " + ", ".join(sorted(nm_f, key=rang))
    elif nm_f:
        tete = "aucune anomalie trouvée, mais non mesuré : " + ", ".join(sorted(nm_f, key=rang)) + " (pas prouvé complet)"
    else:
        tete = "aucune anomalie : chaque compte et chaque lien est attribué ✅"
    ajouter(["CONTRÔLE", "", tete], "section")
    noms = dict(FAMILLES)
    noms.update(getattr(controle, "FAMILLES", None) or {})
    compte_f = {f: 0 for f in noms}
    for a in an:
        if a.get("famille") in compte_f:
            compte_f[a["famille"]] += 1
    ajouter(["Famille", "Nombre", "Libellé"], "sous_titre")
    for f, k in compte_f.items():
        if k:
            gr = min((a.get("gravite") for a in an if a.get("famille") == f), key=lambda g: list(GRAVITES).index(g) if g in GRAVITES else 9)
            ajouter([f, k, (noms.get(f, f) + (f" · en partie non mesuré : {nm_f[f]}" if f in nm_f else ""))[:300]], "famille", gravite=gr)
        elif f in nm_f:
            ajouter([f, "?", f"{noms.get(f, f)} · non mesuré : {nm_f[f]}"[:300]], "famille", gravite="important")
    zeros = [f for f, k in compte_f.items() if not k and f not in nm_f]
    if zeros:
        ajouter(["0", "", "sans anomalie : " + " · ".join(zeros)], "famille", gravite="ok")
    if an:
        ajouter(["Famille", "Gravité", "Détail (les " + str(min(len(an), ANOMALIES_MAX)) + " premières)"], "sous_titre")
        for a in an[:ANOMALIES_MAX]:
            ajouter([a.get("famille", "?"), GRAVITES.get(a.get("gravite"), a.get("gravite", "")), str(a.get("texte") or "")[:300]],
                    "anomalie", gravite=a.get("gravite"))
        if len(an) > ANOMALIES_MAX:
            ajouter(["", "", f"… et {len(an) - ANOMALIES_MAX} autre(s) : texte complet au salon admin (contrôle toutes les 15 min)"],
                    "anomalie", gravite="info")
    if callable(getattr(controle, "bouclage", None)):
        try:
            b = _appel_bouclage(ctx, lids_lignes, lids_masques)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : bouclage illisible (%s)", erreur)
            b = None
            ajouter(["Bouclage", "⚠", f"illisible (erreur du contrôle : {type(erreur).__name__}) : rien ne prouve que chaque visite est "
                     "portée"], "bouclage", gravite="important")
        if isinstance(b, dict):
            _ligne_bouclage(ajouter, ctx, b, tout)
    return len(an)


def _ligne_bouclage(ajouter, ctx: _Ctx, b: dict, tout: dict = None):
    """La ligne Bouclage. 09/10 (revue DASH) : « 0 = … ✅ » ne s'affiche plus quand aucun lien n'est mesuré (un jour de GAML en
    panne : sommes vides, « non mesurable ») ; un relevé incomplet → « ⚠ incomplet (k/n liens) », jamais ✅ ; le total du
    bouclage est comparé au TOTAL Clics 7 j de la même page (contrat C6e) — s'ils diffèrent, c'est dit, sans ✅."""
    ecart = int(b.get("ecart") or 0)
    try:
        periode = f"{date.fromisoformat(b['debut']).strftime('%d/%m')} → {date.fromisoformat(b['fin']).strftime('%d/%m')}"
    except (KeyError, ValueError, TypeError):
        periode = "7 j"
    non_mes = list(b.get("non_mesures") or [])
    n_liens = b.get("liens") if isinstance(b.get("liens"), int) and not isinstance(b.get("liens"), bool) else None
    mesures = b.get("mesures") if isinstance(b.get("mesures"), int) and not isinstance(b.get("mesures"), bool) else \
        (n_liens - len(non_mes) if n_liens is not None else None)
    if n_liens is None and mesures is not None:
        n_liens = mesures + len(non_mes)
    if non_mes and (mesures == 0 or (mesures is None and not b.get("total"))):
        ajouter(["Bouclage", "⚠", f"Visites 7 j ({periode}) : non mesurable, relevé incomplet ({len(non_mes)}"
                 + (f"/{n_liens}" if n_liens is not None else "") + " lien(s) sans 7 jours relevés) — sommes laissées vides, jamais un 0"],
                "bouclage", gravite="important")
        return
    total = int(b.get("total") or 0)
    masques = int(b.get("masques") or 0)
    txt = (f"Visites 7 j ({periode}) : {_txt_n(total)} = lignes {_txt_n(b.get('lignes') or 0)}"
           + (f" + masqués {_txt_n(masques)}" if masques or b.get("liens_masques") else "")
           + f" + pages {_txt_n(b.get('pages') or 0)} + libérés / hors clipping {_txt_n(b.get('liberes') or 0)} + écart {_txt_n(ecart)}"
           + (" ⚠" if ecart else ""))
    problemes = []
    if non_mes:
        problemes.append(f"⚠ incomplet : {len(non_mes)}" + (f"/{n_liens}" if n_liens is not None else "")
                         + " lien(s) sans 7 jours relevés, hors des sommes")
    # contrat C6e : le TOTAL Clics 7 j (paie_clics.clics_lien sur tous les liens actifs) et le bouclage doivent donner le même chiffre
    if tout and str(b.get("fin") or "")[:10] in ("", ctx.hier.isoformat()):
        t_dash = tout.get("c7") if tout.get("c7") is not None else 0
        if t_dash != total:
            problemes.append(f"⚠ ne concorde pas avec le TOTAL Clics 7 j ({_txt_n(t_dash)}) : deux règles de calcul des visites")
    if problemes:
        txt += " · " + " · ".join(problemes)
    elif not ecart:
        txt += " ✅"
    statut = ecart if ecart else ("⚠" if problemes else "✅")
    ajouter(["Bouclage", statut, txt], "bouclage", gravite="bloquant" if ecart else ("important" if problemes else "ok"))
    for x in (b.get("non_comptes") or [])[:10]:
        ajouter(["", x.get("visites", ""), f"⚠ lien {x.get('url') or x.get('lid')} ({x.get('creatrice') or '?'}"
                 + (f", note « {x.get('note')} »" if x.get("note") else "") + ") : visites portées par aucune ligne"],
                "anomalie", gravite="bloquant")


def _section_tendances(ajouter, ctx: _Ctx, tend: dict, n_comptes: int):
    j0 = ctx.j0
    a7, b7 = j0 - timedelta(days=7), j0 - timedelta(days=1)
    va, vb = j0 - timedelta(days=9), j0 - timedelta(days=3)
    ajouter(["TENDANCES", "", f"7 jours ({a7.strftime('%d/%m')} → {b7.strftime('%d/%m')}) contre les 7 jours d'avant · vues des Reels "
             f"publiés du {va.strftime('%d/%m')} au {vb.strftime('%d/%m')}, relevées 48 h après la publication · seulement ce qui est "
             "mesuré sur les deux périodes · classés par écart"], "section")
    ajouter(["Quoi", "Compte / lien", "Gérant", "Δ", "Actuel", "Avant", "Créatrice"], "sous_titre")
    noms = {"vues": ("Vues", "il faut que chaque Reel publié soit mesuré à 48 h, sur les deux périodes (16 jours de séries)"),
            "clics": ("Clics", "il faut 14 jours de relevés complets du lien (un jour manquant ou un lien repris : pas comparé)"),
            "followers": ("Followers", "il faut deux relevés à 7 jours d'écart (même source)")}
    for k, (nom, raison) in noms.items():
        items = tend[k]
        if not items:
            ajouter([nom, "", "pas encore calculable : " + raison], "tendance_vide")
            continue
        hausses = sorted((x for x in items if x[0] > 0), key=lambda x: (-x[0], str(x[1])))[:TOP]
        baisses = sorted((x for x in items if x[0] < 0), key=lambda x: (x[0], str(x[1])))[:TOP]
        for sens, liste in (("▲", hausses), ("▼", baisses)):
            for x in liste:
                ajouter([f"{sens} {nom}", x[1], x[2], x[4], x[5], x[6], x[3]], "tendance")
        if not hausses and not baisses:
            ajouter([nom, "", f"► stable : {len(items)} mesuré(s) sur les deux périodes, aucun écart"], "tendance_vide")
        else:
            ajouter(["", "", f"{len(items)} {'lien(s)' if k == 'clics' else 'compte(s)'} comparable(s) sur {n_comptes} compte(s) montrés"],
                    "tendance_vide")


def _lien_texte(ctx: _Ctx, L: dict) -> str:
    morceaux = []
    for lid in L["ok"]:
        # 10/10 (revue DASH, restant 3) : compté sur la ligne (C6d), mais signalé EN TÊTE de cellule — la règle « ⚠ » la colore
        nom = ctx.lien_suspect(lid, L)
        if nom:
            morceaux.append(f"⚠ {_slug(ctx.liens[lid], lid)} : lien de {nom} d'après le nom, à vérifier")
    if L["lids"]:
        morceaux.append(" + ".join(_slug(ctx.liens[x], x) for x in L["lids"]) + (" (bio)" if L["bio"] else ""))
    elif L["trio"]:
        morceaux.append(f"(trio) {_slug(ctx.liens[L['trio'][0][0]], L['trio'][0][0])}")
    for lid, porteur in L["ailleurs"]:
        chez = "un Gérant masqué" if porteur.get("masque") else (porteur["c"].get("gerant") or "?").strip()
        morceaux.append(f"⚠ {_slug(ctx.liens[lid], lid)} déjà compté chez {chez}")
    noms = {"libere": "libéré", "hors_clipping": "hors clipping", "page": "page de la créatrice", "desactive": "désactivé",
            "supprime": "supprimé", "attribue": "lien d'un clipper", "suivi": "lien suivi", "non_attribue": "jamais attribué"}
    for lid, raison in L["ko"]:
        morceaux.append(f"⚠ {_slug(ctx.liens[lid], lid)} ({noms.get(raison, raison)})")
    if not L["ok"]:
        for lid, raison in L.get("bio_ko") or []:
            morceaux.append(f"⚠ bio : {_slug(ctx.liens[lid], lid)} ({noms.get(raison, raison)})")
    for u in L["inconnus"]:
        morceaux.append(f"⚠ {u[:28]} (inconnu du bot)")
    if morceaux:
        return " · ".join(morceaux)
    if _youtube(ctx, L):
        return "via YouTube, non attribuable"
    e_n = _norm(L["c"].get("etat"))
    if L["typ"] == "clipper" and e_n not in onboarding.A_CREER and e_n != "ban":
        return "⚠ sans lien"
    return "—"


def _youtube(ctx: _Ctx, L: dict) -> bool:
    for u in ctx.bio_urls(L["cle"]):
        hote = u.split("/")[0]
        if hote.endswith("youtube.com") or hote.endswith("youtu.be"):
            return True
        lid = ctx.par_url.get(u)
        if lid and ctx.cat(lid) == "page" and re.search(r"(^|/)(ytb|youtube)\b", u.split("/", 1)[1] if "/" in u else ""):
            return True
    return False


def _ligne_compte(ctx: _Ctx, L: dict, gerant: str) -> list:
    c = L["c"]
    r = _ligne_vide()
    r[C_GERANT] = gerant
    r[C_HANDLE] = c["handle"]
    r[C_UTIL] = str(c.get("utilisation") or "").strip()
    etat = str(c.get("etat") or "").strip()
    r[C_ETAT] = etat if etat else ("—" if L["typ"] == "creatrice" else "⚠ vide")   # l'ETAT d'une créatrice n'est jamais décidé par le bot
    r[C_FOL] = _v(L["followers"])
    r[C_DF24] = _delta_abs(L["df24"])
    r[C_DF7] = _delta_abs(L["df7"])
    r[C_RH], r[C_R7] = _v(L["rh"]), _v(L["r7"])
    r[C_DR] = _delta_abs(L["r7"] - L["r7p"]) if L["r7"] is not None and L["r7p"] is not None and L["r7_serie"] else ""
    if L["vues"]:
        r[C_V7], r[C_VMED] = L["vues"][0], L["vues"][2]
        r[C_DV] = _delta_pct(L["vues"][0], L["vues_p"][0]) if L["vues_comparable"] else ""
    r[C_LIEN] = _lien_texte(ctx, L)
    notes = []
    if L["clics"]:
        k = L["clics"]
        r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
        notes = _notes_clics(ctx, k, heure=True)                         # 09/10 (revue DASH) : k/n liens, reprise, heure du jour
    r[C_MES] = " · ".join([L["mesure"]] + notes)
    r[C_REL] = L["releve"]
    return r


def _sous_total(ctx: _Ctx, groupe: list, nom: str) -> list:
    r = _ligne_vide()
    r[C_GERANT], r[C_HANDLE] = "Sous-total", nom
    r[C_FOL] = _v(_somme(L["followers"] for L in groupe)[0])
    both = [L for L in groupe if L["df24"] is not None]
    r[C_DF24] = _delta_abs(sum(L["df24"] for L in both)) if both else ""
    both = [L for L in groupe if L["df7"] is not None]
    r[C_DF7] = _delta_abs(sum(L["df7"] for L in both)) if both else ""
    r[C_RH] = _v(_somme(L["rh"] for L in groupe)[0])
    r[C_R7] = _v(_somme(L["r7"] for L in groupe)[0])
    comp = [L for L in groupe if L["r7"] is not None and L["r7p"] is not None and L["r7_serie"]]
    r[C_DR] = _delta_abs(sum(L["r7"] - L["r7p"] for L in comp)) if comp else ""
    r[C_V7] = _v(_somme(_vues_mesurees(L)[0] for L in groupe)[0])
    comp = [L for L in groupe if L["vues_comparable"]]
    r[C_DV] = _delta_pct(sum(L["vues"][0] for L in comp), sum(L["vues_p"][0] for L in comp)) if comp else ""
    lids = [x for L in groupe for x in L["lids"]]
    k = {}
    if lids:
        k = _clics_de(ctx, lids)
        r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
        r[C_LIEN] = f"{len(set(lids))} lien(s)"
    # 09/10 (revue DASH) : une somme partielle le dit, mesure par mesure (« partiel : followers 2/3, Reels 7 j 1/3 · clics 7 j : 1/2
    # liens relevés »)
    r[C_MES] = " · ".join(x for x in (f"{len(groupe)} comptes", _texte_partiel(_notes_sommes(groupe), _notes_clics(ctx, k))) if x)
    return r


def _ligne_liens(ctx: _Ctx, titre: str, sous: str, lids: list, kind: str) -> list:
    r = _ligne_vide()
    r[C_GERANT], r[C_HANDLE] = titre, sous
    if not lids:
        r[C_LIEN] = "aucun"
        return r
    noms = []
    for x in lids:
        info = ctx.liens.get(x) or {}
        s = _slug(info, x)
        if kind == "sans_ligne":
            note = str(info.get("note") or info.get("nom") or "").strip()
            s += f" ({note[:24]})" if note else ""
        elif ctx.cat(x) == "hors_clipping" and str(info.get("hors_clipping") or "").strip() not in ("", "True", "1"):
            s += f" ({str(info['hors_clipping'])[:20]})"
        noms.append(s)
    r[C_LIEN] = f"{len(lids)} lien(s)" if kind == "masques" else " · ".join(noms)   # masqués : pas de détail
    k = _clics_de(ctx, lids)
    r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
    r[C_MES] = " · ".join(["GAML"] + _notes_clics(ctx, k))
    return r


def _bloc_creatrice(ajouter, ctx: _Ctx, cr: str, lignes_cr: list, r_cr: dict, hors: dict, tot: dict):
    nom_cr = (lignes_cr[0]["cr_nom"] if lignes_cr else cr.capitalize()) if cr else "Autres liens"
    groupes = {}
    for L in sorted(lignes_cr, key=lambda L: L["ordre"]):
        groupes.setdefault(L["groupe"], []).append(L)

    def cle_tri(item):
        g, ls = item
        rang = 0 if g == "crea" else (3 if g == "libre" else (2 if g.startswith("m|") else 1))
        c7 = _somme((L["clics"] or {}).get("c7") for L in ls)[0]
        return (rang, -(c7 if c7 is not None else -1), -(_somme(L["followers"] for L in ls)[0] or 0), g)

    tous_lids = [x for L in lignes_cr for x in L["lids"]] + [x for seau in r_cr.values() for x in seau]
    k_cr = _clics_de(ctx, tous_lids) if tous_lids else {}
    bande = _ligne_vide()
    bande[C_GERANT], bande[C_HANDLE] = nom_cr.upper(), f"{len(lignes_cr)} comptes" if cr else ""
    bande[C_FOL] = _v(_somme(L["followers"] for L in lignes_cr)[0])
    bande[C_R7] = _v(_somme(L["r7"] for L in lignes_cr)[0])
    bande[C_V7] = _v(_somme(_vues_mesurees(L)[0] for L in lignes_cr)[0])
    if k_cr:
        bande[C_CA], bande[C_CH], bande[C_C7], bande[C_DC] = _v(k_cr["auj"]), _v(k_cr["hier"]), _v(k_cr["c7"]), k_cr["delta"]
        bande[C_LIEN] = f"{len(set(tous_lids))} liens actifs"
    extra = []
    if hors.get("vivier"):
        extra.append(f"+{hors['vivier']} à créer d'avance")
    if hors.get("ban"):
        extra.append(f"{hors['ban']} BAN rendus")
    if hors.get("masques"):
        n_m = len(r_cr.get("masques") or [])
        extra.append(f"{hors['masques']} masqué(s)" + (f", {n_m} lien(s) de Gérants masqués" if n_m else ""))
    extra.append(_texte_partiel(_notes_sommes(lignes_cr), _notes_clics(ctx, k_cr)))
    bande[C_MES] = " · ".join(x for x in extra if x)
    ajouter(bande, "creatrice", cr=cr)
    ajouter(COLONNES, "entete", cr=cr)
    zebre = 0
    for g, ls in sorted(groupes.items(), key=cle_tri):
        if g == "crea":
            nom = f"{nom_cr} (créatrice)"
        elif g == "libre":
            nom = "Sans Gérant"
        else:
            nom = (ls[0]["c"].get("gerant") or "?").strip()
            if any(L.get("homonyme") for L in ls):
                porte = next((x for L in ls for x in L["lids"]), None)
                nom += " ⚠ homonyme" + (f" ({_slug(ctx.liens[porte], porte)})" if porte else " (sans lien)")
        for L in ls:
            ajouter(_ligne_compte(ctx, L, nom), "compte", cr=cr, zebre=zebre % 2)
        if len(ls) >= 2:
            ajouter(_sous_total(ctx, ls, nom), "sous_total", cr=cr)
        zebre += 1
    ajouter(_ligne_liens(ctx, "Pages", "de la créatrice" if cr else "sans créatrice", r_cr["pages"], "pages"), "liens", cr=cr)
    ajouter(_ligne_liens(ctx, "Libérés", "hors clipping", r_cr["liberes"], "liberes"), "liens", cr=cr)
    if r_cr.get("masques"):                                              # 09/10 (revue DASH) : rien ne se perd, rien n'est montré
        ajouter(_ligne_liens(ctx, "Masqués", "Gérants masqués", r_cr["masques"], "masques"), "liens", cr=cr)
    if r_cr["sans_ligne"]:
        ajouter(_ligne_liens(ctx, "⚠ Sans ligne", "liens attribués", r_cr["sans_ligne"], "sans_ligne"), "sans_ligne", cr=cr)
    tot["comptes"] += len(lignes_cr)
    tot["lignes"] += lignes_cr
    tot["lids"] += tous_lids


# ------------------------------------------------------------------ mise en forme (batchUpdate)
def _rgb(hexa: str) -> dict:
    h = hexa.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def _melange(hexa: str, t: float) -> str:
    h = hexa.lstrip("#"); t = max(0.0, min(1.0, t))
    return "#" + "".join(f"{int(round(255 + (int(h[i:i + 2], 16) - 255) * t)):02X}" for i in (0, 2, 4))


def _plage(sid, r0, r1, c0, c1) -> dict:
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _style(sid, r0, r1, c0, c1, fond=None, texte=None, gras=None, italique=None, taille=None, aligne=None, nombre=None,
           coupe=None) -> dict:
    fmt, champs, tf = {}, [], {}
    if fond:
        fmt["backgroundColor"] = _rgb(fond); champs.append("backgroundColor")
    if texte:
        tf["foregroundColor"] = _rgb(texte)
    if gras is not None:
        tf["bold"] = gras
    if italique is not None:
        tf["italic"] = italique
    if taille:
        tf["fontSize"] = taille
    if tf:
        fmt["textFormat"] = tf; champs.append("textFormat")
    if aligne:
        fmt["horizontalAlignment"] = aligne; champs.append("horizontalAlignment")
    if nombre:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": nombre}; champs.append("numberFormat")
    if coupe:
        fmt["wrapStrategy"] = coupe; champs.append("wrapStrategy")
    fmt["verticalAlignment"] = "MIDDLE"; champs.append("verticalAlignment")
    return {"repeatCell": {"range": _plage(sid, r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt},
                           "fields": "userEnteredFormat(" + ",".join(champs) + ")"}}


def _hauteur(sid, r0, r1, px) -> dict:
    return {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r0, "endIndex": r1},
                                          "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def _valeur(v) -> dict:
    if v is None or v == "":
        return {}
    if isinstance(v, bool):
        return {"userEnteredValue": {"stringValue": "oui" if v else "non"}}
    if isinstance(v, (int, float)):
        return {"userEnteredValue": {"numberValue": v}}
    return {"userEnteredValue": {"stringValue": str(v)}}


def requetes(r: dict, sid: int, lignes_grille: int, colonnes_grille: int) -> list:
    """Le batchUpdate de l'onglet : valeurs écrites EN PLACE sur toute la grille (updateCells : ce qui n'est pas fourni est vidé,
    valeurs et formats, dans la même requête — jamais un onglet vidé d'abord), puis la mise en forme ligne par ligne."""
    lignes, types = r["lignes"], r["types"]
    n = len(lignes)
    req = []
    if lignes_grille < n + 20:                                           # la grille s'agrandit avant l'écriture
        req.append({"appendDimension": {"sheetId": sid, "dimension": "ROWS", "length": n + 50 - lignes_grille}})
        lignes_grille = n + 50
    if colonnes_grille < NB:
        req.append({"appendDimension": {"sheetId": sid, "dimension": "COLUMNS", "length": NB - colonnes_grille}})
        colonnes_grille = NB
    req.append({"unmergeCells": {"range": _plage(sid, 0, lignes_grille, 0, colonnes_grille)}})
    req.append({"updateCells": {"range": _plage(sid, 0, lignes_grille, 0, colonnes_grille),
                                "rows": [{"values": [_valeur(v) for v in ligne]} for ligne in lignes],
                                "fields": "userEnteredValue,userEnteredFormat"}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
        "hideGridlines": True, "frozenRowCount": 1, "frozenColumnCount": 2}},
        "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})
    for i, px in enumerate(LARGEURS):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                  "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    req.append(_hauteur(sid, 0, lignes_grille, 22))
    req.append(_style(sid, 0, max(n, 1), 0, NB, texte="#212121", taille=10, coupe="CLIP"))
    i = 0
    while i < n:
        t = types[i]
        k = t["kind"]
        bande, teinte = PALETTE.get(t.get("cr") or "", PALETTE_DEFAUT)
        if k == "titre":
            req += [_style(sid, i, i + 1, 0, NB, fond=SOMBRE, texte=BLANC, gras=True, taille=11),
                    _style(sid, i, i + 1, 0, 2, fond=SOMBRE, texte=BLANC, gras=True, taille=12, coupe="WRAP"),
                    {"mergeCells": {"range": _plage(sid, i, i + 1, 0, 2), "mergeType": "MERGE_ALL"}},
                    _style(sid, i, i + 1, 2, NB, fond=SOMBRE, texte="#CFD8DC", taille=10, coupe="OVERFLOW_CELL"), _hauteur(sid, i, i + 1, 44)]
        elif k == "alerte":                                              # 09/10 (revue DASH) : budget Apify, Metricool en échec
            fond = "#FFEBEE" if t.get("gravite") == "bloquant" else "#FFF8E1"
            req += [_style(sid, i, i + 1, 0, NB, fond=fond, texte="#212121", taille=10),
                    _style(sid, i, i + 1, 0, 2, fond=fond, texte="#B71C1C" if t.get("gravite") == "bloquant" else "#E65100", gras=True,
                           taille=11, aligne="LEFT"),
                    _style(sid, i, i + 1, 2, NB, fond=fond, texte="#212121", gras=True, taille=10, coupe="OVERFLOW_CELL"),
                    _hauteur(sid, i, i + 1, 28)]
        elif k == "legende":
            req.append(_style(sid, i, i + 1, 2, NB, texte=GRIS_TEXTE, italique=True, taille=9, coupe="OVERFLOW_CELL"))
        elif k == "vide":
            req.append(_hauteur(sid, i, i + 1, 12))
        elif k == "section":
            req += [_style(sid, i, i + 1, 0, NB, fond=SECTION, texte=BLANC, gras=True, taille=11),
                    {"mergeCells": {"range": _plage(sid, i, i + 1, 0, 2), "mergeType": "MERGE_ALL"}},
                    _style(sid, i, i + 1, 2, NB, fond=SECTION, texte="#ECEFF1", gras=False, taille=10, coupe="OVERFLOW_CELL"),
                    _hauteur(sid, i, i + 1, 30)]
        elif k == "sous_titre":
            req.append(_style(sid, i, i + 1, 0, NB, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9))
        elif k in ("famille", "anomalie", "bouclage"):
            fond = {"bloquant": "#FFEBEE", "important": "#FFF8E1"}.get(t.get("gravite"), None)
            req += [_style(sid, i, i + 1, 0, 2, fond=fond or BLANC, texte="#37474F", gras=True, taille=9, aligne="CENTER"),
                    _style(sid, i, i + 1, 2, NB, texte="#212121", taille=9, coupe="OVERFLOW_CELL")]
        elif k in ("tendance", "tendance_vide"):
            req += [_style(sid, i, i + 1, 0, 2, texte="#37474F", gras=k == "tendance", taille=9),
                    _style(sid, i, i + 1, 2, NB, texte="#212121" if k == "tendance" else GRIS_TEXTE, italique=k != "tendance", taille=9,
                           coupe="OVERFLOW_CELL" if k != "tendance" else "CLIP"),
                    _style(sid, i, i + 1, 3, 6, aligne="CENTER", nombre="#,##0")]
        elif k == "creatrice":
            req += [_style(sid, i, i + 1, 0, NB, fond=bande, texte=BLANC, gras=True, taille=11, aligne="CENTER", nombre="#,##0"),
                    _style(sid, i, i + 1, 0, 2, fond=bande, texte=BLANC, gras=True, taille=12, aligne="LEFT"),
                    _style(sid, i, i + 1, C_LIEN, C_LIEN + 1, fond=bande, texte=BLANC, gras=False, taille=9, aligne="LEFT"),
                    _style(sid, i, i + 1, C_MES, NB, fond=bande, texte=BLANC, gras=False, taille=9, aligne="LEFT", coupe="OVERFLOW_CELL"),
                    _hauteur(sid, i, i + 1, 30)]
        elif k == "entete":
            req += [_style(sid, i, i + 1, 0, NB, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9, aligne="CENTER", coupe="WRAP"),
                    _style(sid, i, i + 1, 0, 2, fond=GRIS_CLAIR, texte="#37474F", gras=True, taille=9, aligne="LEFT"),
                    _hauteur(sid, i, i + 1, 34)]
        elif k == "compte":
            j = i                                                        # les lignes d'un même groupe, d'une traite
            while j + 1 < n and types[j + 1]["kind"] == "compte" and types[j + 1].get("zebre") == t.get("zebre") \
                    and types[j + 1].get("cr") == t.get("cr"):
                j += 1
            fond = teinte if t.get("zebre") == 0 else BLANC
            req += [_style(sid, i, j + 1, 0, NB, fond=fond, texte="#212121", taille=10, aligne="CENTER", nombre="#,##0"),
                    _style(sid, i, j + 1, 0, 2, fond=fond, gras=True, aligne="LEFT"),
                    _style(sid, i, j + 1, C_UTIL, C_UTIL + 1, fond=fond, texte=GRIS_TEXTE, taille=9, aligne="LEFT"),
                    _style(sid, i, j + 1, C_LIEN, C_LIEN + 1, fond=fond, texte="#37474F", taille=9, aligne="LEFT"),
                    _style(sid, i, j + 1, C_MES, NB, fond=fond, texte=GRIS_TEXTE, taille=9, aligne="LEFT")]
            i = j + 1
            continue
        elif k == "sous_total":
            fond = _melange(bande, 0.18)
            req += [_style(sid, i, i + 1, 0, NB, fond=fond, texte="#212121", gras=True, taille=10, aligne="CENTER", nombre="#,##0"),
                    _style(sid, i, i + 1, 0, 2, fond=fond, gras=True, italique=True, aligne="LEFT"),
                    _style(sid, i, i + 1, C_LIEN, C_LIEN + 1, fond=fond, gras=False, taille=9, aligne="LEFT"),
                    _style(sid, i, i + 1, C_MES, NB, fond=fond, gras=False, texte=GRIS_TEXTE, taille=9, aligne="LEFT")]
        elif k in ("liens", "sans_ligne"):
            fond = "#FFF3E0" if k == "sans_ligne" else "#FAFAFA"
            req += [_style(sid, i, i + 1, 0, NB, fond=fond, texte="#455A64", italique=True, taille=10, aligne="CENTER", nombre="#,##0"),
                    _style(sid, i, i + 1, 0, 2, fond=fond, gras=True, aligne="LEFT"),
                    _style(sid, i, i + 1, C_UTIL, C_LIEN + 1, fond=fond, taille=9, aligne="LEFT", coupe="CLIP"),
                    _style(sid, i, i + 1, C_MES, NB, fond=fond, taille=9, aligne="LEFT")]
        elif k == "total":
            req += [_style(sid, i, i + 1, 0, NB, fond=SOMBRE, texte=BLANC, gras=True, taille=11, aligne="CENTER", nombre="#,##0"),
                    _style(sid, i, i + 1, 0, 2, fond=SOMBRE, texte=BLANC, gras=True, aligne="LEFT"), _hauteur(sid, i, i + 1, 30)]
        i += 1
    return req


def regles(sid: int) -> list:
    """La mise en forme conditionnelle (posée une fois par DASHBOARD_VERSION) : ▲ en vert, ▼ en rouge, « ⛔ » en rouge, « ⚠ » en
    orange, « non lu » en ambre, BAN en rouge — sur tout l'onglet, quelle que soit la ligne : le contenu bouge, les règles restent."""
    plage = [{"sheetId": sid, "startColumnIndex": 0, "endColumnIndex": NB}]

    def regle(type_, valeur, texte, fond, gras=True):
        return {"ranges": plage, "booleanRule": {"condition": {"type": type_, "values": [{"userEnteredValue": valeur}]},
                                                 "format": {"textFormat": {"foregroundColor": _rgb(texte), "bold": gras},
                                                            "backgroundColor": _rgb(fond)}}}
    return [regle("TEXT_STARTS_WITH", "▲", "#1B5E20", "#E8F5E9"),
            regle("TEXT_STARTS_WITH", "▼", "#B71C1C", "#FFEBEE"),
            regle("TEXT_STARTS_WITH", "⛔", "#B71C1C", "#FFCDD2"),           # 09/10 (revue DASH) : Apify coupé, budget atteint
            regle("TEXT_STARTS_WITH", "⚠", "#E65100", "#FFF3E0"),
            regle("TEXT_STARTS_WITH", "non lu", "#E65100", "#FFF8E1", gras=False),
            regle("TEXT_EQ", "BAN", "#B71C1C", "#FFCDD2")]


async def _nb_regles(cid: str, sid: int) -> int:
    r = await google_api._appel("GET", f"{google_api.SHEETS}/{cid}", params={"fields": "sheets(properties(sheetId),conditionalFormats)"})
    for s in (r or {}).get("sheets", []):
        if (s.get("properties") or {}).get("sheetId") == sid:
            return len(s.get("conditionalFormats") or [])
    return 0


async def _batch_unique(cid: str, req: list) -> None:
    """09/10 (revue DASH : google_api.sheets_batch_update découpe par paquets de 400 — à la taille réelle (~130 comptes, ~620
    requêtes) l'onglet partait en DEUX appels non atomiques, valeurs et formats vidés dans le 1er, mise en forme dans le 2e) :
    UN seul batchUpdate, sans découpage — Google applique tout ou rien (pas de limite de nombre de requêtes côté Google)."""
    await google_api._appel("POST", f"{google_api.SHEETS}/{cid}:batchUpdate", corps={"requests": list(req)})


async def _poser_regles(cid: str, sid: int) -> None:
    """Les règles conditionnelles de l'onglet remplacées par les nôtres (le bot seul écrit dans le Dashboard)."""
    n = await _nb_regles(cid, sid)
    req = [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}} for _ in range(n)]
    req += [{"addConditionalFormatRule": {"rule": rg, "index": i}} for i, rg in enumerate(regles(sid))]
    await _batch_unique(cid, req)


# ------------------------------------------------------------------ état, lecture, écriture
def _lire_etat() -> dict:
    if not (_deps.get("lire_json") and _deps.get("FICHIER")):
        return {}
    d = _deps["lire_json"](_deps["FICHIER"], {})
    return d if isinstance(d, dict) else {}


def _ecrire_etat(d: dict):
    if _deps.get("ecrire_json") and _deps.get("FICHIER"):
        _deps["ecrire_json"](_deps["FICHIER"], d)


def _lire(cle: str, defaut):
    if not (_deps.get("lire_json") and _deps.get(cle)):
        return defaut
    try:
        v = _deps["lire_json"](_deps[cle], defaut)
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Dashboard : %s illisible (%s)", cle, erreur)
        return defaut
    return v if isinstance(v, type(defaut)) else defaut


def entrees(comptes: list) -> dict:
    """Tout ce que le Dashboard lit en plus du classeur : fichiers du bot (lecture seule), membres présents, état Metricool."""
    etats = _lire("FICHIER_ETATS", {})
    clics = _lire("FICHIER_CLICS", {})
    registre = _lire("FICHIER_EQUIPES", {})
    onb = _lire("FICHIER_ONBOARDING", {})
    if not onb:
        try:
            onb = onboarding._lire_etat()
        except Exception:                                                # noqa: BLE001
            onb = {}
    membres = None                                                       # None : le contrôle lit lui-même (sinon tout serait fantôme)
    mpi = _deps.get("membre_par_id")
    if callable(mpi):
        uids = set(registre) | {str((i or {}).get("uid") or "") for i in (clics.get("liens") or {}).values() if isinstance(i, dict)}
        membres = {}
        for uid in sorted(uids - {""}):
            try:
                m = mpi(uid)
            except Exception:                                            # noqa: BLE001
                m = None
            if m is not None:
                membres[str(uid)] = str(getattr(m, "display_name", "") or "")
    masques = etats.get("dashboard_masques") if isinstance(etats.get("dashboard_masques"), list) else \
        [m.strip() for m in os.environ.get("DASHBOARD_MASQUES", "").split(",") if m.strip()]
    met = None
    if metricool_comptes is not None and callable(getattr(metricool_comptes, "etat", None)):
        try:
            met = metricool_comptes.etat()
        except Exception as erreur:                                      # noqa: BLE001
            journal.debug("Metricool (état) : %s", erreur)
    return {"comptes": comptes, "etats": etats, "clics": clics, "registre": registre, "onboarding": onb, "membres": membres,
            "masques": masques, "metricool": met}


async def _ecrire_onglet(r: dict) -> int:
    cid = onboarding.CLASSEUR_LOGINS_ID
    props = await google_api.sheets_proprietes(cid)
    if ONGLET not in props:
        await google_api.sheets_creer_onglet(cid, ONGLET)
        props = await google_api.sheets_proprietes(cid)
    p = props.get(ONGLET) or {}
    sid = p.get("id")
    if sid is None:
        raise RuntimeError(f"onglet « {ONGLET} » introuvable")
    await _batch_unique(cid, requetes(r, sid, int(p.get("lignes") or 0), int(p.get("colonnes") or 0)))
    return sid


async def ecrire(force: bool = False, *, maintenant: datetime = None) -> dict:
    """Contrat C5 : relit tout, réécrit l'onglet si son contenu a changé (ou `force`), au plus toutes les 14 minutes hors `force`.
    Renvoie {ecrit, lignes, comptes, anomalies, empreinte, raison, erreur}. Aucun appel Apify, GAML ni Metricool."""
    global _verrou
    _verrou = _verrou or asyncio.Lock()
    bilan = {"ecrit": False, "lignes": 0, "comptes": 0, "anomalies": None, "empreinte": "", "raison": "", "erreur": ""}
    async with _verrou:
        if not onboarding.actif() or not google_api.actif():
            bilan["erreur"] = "classeur non configuré (CLASSEUR_LOGINS_ID, compte de service Google)"
            return bilan
        if not _deps.get("lire_json"):
            bilan["erreur"] = "Dashboard non configuré (dashboard.configurer)"
            return bilan
        maintenant = maintenant or datetime.now(timezone.utc)
        etat = _lire_etat()
        dernier = _instant(etat.get("t"))
        if not force and dernier is not None and timedelta(0) <= maintenant - dernier < timedelta(seconds=ECART_MIN_S) \
                and etat.get("version") == DASHBOARD_VERSION:
            bilan["raison"] = "trop tôt"
            return bilan
        comptes = await onboarding.lire_comptes()
        if not comptes:
            bilan["erreur"] = "classeur vide ou illisible : Dashboard gardé tel quel"
            return bilan
        r = construire(entrees(comptes), maintenant)
        bilan.update(lignes=len(r["lignes"]), comptes=r["comptes"], anomalies=r["anomalies"], empreinte=r["empreinte"])
        if not force and etat.get("empreinte") == r["empreinte"] and etat.get("version") == DASHBOARD_VERSION:
            bilan["raison"] = "inchangé"
            return bilan
        try:
            sid = await _ecrire_onglet(r)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : écriture impossible (%s)", erreur)
            bilan["erreur"] = f"écriture impossible : {type(erreur).__name__} {str(erreur)[:150]}"
            return bilan
        bilan["ecrit"] = True
        etat.update({"t": maintenant.isoformat(timespec="seconds"), "empreinte": r["empreinte"], "lignes": len(r["lignes"]),
                     "version": DASHBOARD_VERSION, "sid": sid})
        if etat.get("regles") != DASHBOARD_VERSION:                     # la mise en forme conditionnelle, une fois par version
            try:
                await _poser_regles(onboarding.CLASSEUR_LOGINS_ID, sid)
                etat["regles"] = DASHBOARD_VERSION
            except Exception as erreur:                                  # noqa: BLE001 — retentée à la prochaine écriture
                journal.warning("Dashboard : couleurs ▲ ▼ non posées (%s)", erreur)
        _ecrire_etat(etat)
        journal.info("Dashboard réécrit : %d lignes, %d compte(s), %s anomalie(s)", len(r["lignes"]), r["comptes"],
                     "?" if r["anomalies"] is None else r["anomalies"])
        return bilan


def ecrire_apres_passage(verrou, attente_max_s: float = ATTENTE_PASSAGE_S):
    """09/10 (revue DASH : la réécriture forcée qui suit le passage complet relisait etats_comptes.json AVANT son enregistrement —
    historique sans le jour, non lus et dernier passage de la veille : un compte lu le matin s'affichait « non lu ») : planifie
    `ecrire(force=True)` pour le moment où le passage en cours rend son verrou (`verrou`, celui de etats_comptes.executer), donc
    après l'enregistrement de son état. Attente plafonnée à `attente_max_s`. Renvoie la tâche (gardée dans `_differees`)."""
    async def _tache():
        debut = time.monotonic()
        while verrou is not None and verrou.locked() and time.monotonic() - debut < attente_max_s:
            await asyncio.sleep(0.5)
        try:
            b = await ecrire(force=True)
            if b.get("erreur"):
                journal.warning("Dashboard (après le passage complet) : %s", b["erreur"])
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.warning("Dashboard (après le passage complet) : %s", erreur)
    tache = asyncio.get_running_loop().create_task(_tache())
    _differees.add(tache)
    tache.add_done_callback(_differees.discard)
    return tache


async def boucle(client) -> None:
    """Toutes les 15 minutes : réécrit l'onglet si son contenu a changé (nouvelle version → réécrit et couleurs reposées)."""
    if not actif():
        journal.info("Dashboard : boucle éteinte (DASHBOARD_BOUCLE=0 ou classeur non configuré)")
        return
    await client.wait_until_ready()
    await asyncio.sleep(DELAI_DEMARRAGE_S)
    while not client.is_closed():
        try:
            b = await ecrire(force=_lire_etat().get("version") != DASHBOARD_VERSION)
            if b.get("erreur"):
                journal.warning("Dashboard : %s", b["erreur"])
        except Exception as erreur:                                      # noqa: BLE001 — jamais tuer le bot
            journal.exception("Boucle du Dashboard : %s", erreur)
        await asyncio.sleep(INTERVALLE_S)
