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

Les modules des autres lots (series, controle, metricool_comptes, paie_clics.clics_lien / clics_aujourdhui) sont importés s'ils
sont là : s'il en manque un, sa section dit « source indisponible », ou les chiffres viennent des cellules du classeur (repli
marqué), et les clics d'un lien sont recalculés depuis clics.json « jours » selon la même règle que le contrat C2.
Dépendances (`configurer`) : lire_json, ecrire_json, FICHIER (état du Dashboard : empreinte, version, lignes écrites),
FICHIER_ETATS, FICHIER_CLICS, FICHIER_EQUIPES, FICHIER_ONBOARDING ; facultatifs membre_par_id, normaliser."""
import asyncio
import hashlib
import json
import logging
import os
import re
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
DASHBOARD_VERSION = 10                 # 09/10 (dashboard) : une ligne par compte, tendances, contrôle ; changée → règles reposées
ACTIF = os.environ.get("DASHBOARD_BOUCLE", "1").strip() != "0"
INTERVALLE_S = 900                     # la boucle regarde toutes les 15 minutes
ECART_MIN_S = 14 * 60                  # deux réécritures non forcées : au moins 14 minutes d'écart
DELAI_DEMARRAGE_S = 90                 # au démarrage, laisser les autres boucles se configurer
ANOMALIES_MAX = 15
TOP = 5
AGE_VUES_H = 48                        # vues d'un Reel relevées 48 h après sa publication (même âge pour comparer)
METRICOOL_RECENT_J = 4                 # un relevé Metricool plus vieux ne compte plus dans la Mesure

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

# Les catégories de lien qu'une ligne peut porter (sinon : « ⚠ » dans la colonne Lien, et le lien reste dans sa ligne de résumé)
AUTORISES = {"clipper": {"attribue", "suivi"}, "metricool": {"attribue", "suivi", "hors_clipping"}, "creatrice": {"page"},
             "libre": set()}
INACTIFS = ("desactive", "supprime")

_deps: dict = {}
_verrou = None
_PARIS = None


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
    desactive / supprime — même découpage que le contrôle (bouclage), « suivi » mis à part."""
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
        self.seriesok = series_dispo()
        # le prénom de chaque membre connu (pseudo Discord, sinon prénom du registre) : un lien attribué à un autre prénom que le
        # Gérant de la ligne est le lien d'un autre clipper (jamais compté sur cette ligne)
        self.prenoms = {}
        for uid, f in (e.get("registre") or {}).items():
            if isinstance(f, dict) and _premier(f.get("prenom")):
                self.prenoms[str(uid)] = _premier(f.get("prenom"))
        for uid, nom in (e.get("membres") or {}).items() if isinstance(e.get("membres"), dict) else ():
            if _premier(nom):
                self.prenoms[str(uid)] = _premier(nom)

    def cat(self, lid) -> str:
        return _categorie(self.liens.get(lid) or {})

    def a_un_autre(self, lid, gerant) -> bool:
        """Lien attribué à un membre dont le prénom connu n'est pas celui du Gérant de la ligne."""
        uid = str((self.liens.get(lid) or {}).get("uid") or "")
        p = self.prenoms.get(uid)
        return bool(uid and p and p != _premier(gerant))

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
             "c7p": _clics_lien(self.clics, lid, j0 - timedelta(days=14), j0 - timedelta(days=8))}
        dep = str((self.liens.get(lid) or {}).get("depuis") or "")[:10]
        if dep and dep > (j0 - timedelta(days=14)).isoformat():
            r["c7p"] = None
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
    return out


# ------------------------------------------------------------------ comptes
def _mesure(ctx: _Ctx, L: dict) -> str:
    c, cle, serie = L["c"], L["cle"], L["serie"]
    if _norm(c.get("etat")) in onboarding.A_CREER:
        return "à créer"
    rels = [r for r in (serie.get("releves") or []) if isinstance(r, dict)]
    apify = [r for r in rels if r.get("source") != "metricool"]
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
    if suivi is not None or cle in set(ctx.dp.get("non_lus") or []):
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
    f = _serie("followers_a", cle) if ctx.seriesok else None
    L["followers_source"] = "série" if f is not None else ""
    if f is None:
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
    # jour : critique du 09/10, « Reels hier » de l'avant-veille affiché sans le dire)
    hist = ctx.hist.get(cle) or []
    d_h = hist[-1] if hist and isinstance(hist[-1], dict) else {}
    lu_du_jour = (str(d_h.get("jour") or "")[:10] == ctx.maintenant.astimezone(timezone.utc).strftime("%Y-%m-%d")
                  and d_h.get("existe") and not d_h.get("restreint") and not d_h.get("prive") and not d_h.get("reels_non_lus"))
    L["r7_serie"] = r7 is not None                                      # Δ Reels : deux périodes de la même source
    if rh is None and lu_du_jour:
        rh = _entier(c.get("reels_hier"))
    if r7 is None and lu_du_jour:
        r7 = _entier(c.get("reels_7j"))
    L["rh"], L["r7"] = rh, r7
    vA = _serie("vues_age_fixe", cle, _minuit(j0 - timedelta(days=9)), _minuit(j0 - timedelta(days=2)), AGE_VUES_H) if ctx.seriesok else None
    vB = _serie("vues_age_fixe", cle, _minuit(j0 - timedelta(days=16)), _minuit(j0 - timedelta(days=9)), AGE_VUES_H) if ctx.seriesok else None
    L["vues"] = tuple(vA) if vA else None
    L["vues_p"] = tuple(vB) if vB else None
    L["mesure"] = _mesure(ctx, L)
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
            autre = L["typ"] == "clipper" and cat == "attribue" and ctx.a_un_autre(lid, L["c"].get("gerant"))
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
            autre = L["typ"] == "clipper" and cat == "attribue" and ctx.a_un_autre(lid, L["c"].get("gerant"))
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
                if uid and not ctx.a_un_autre(lid, L["c"].get("gerant")):   # le lien d'un autre ne fait pas un homonyme
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
    ordre_cr, comptes_l, hors = [], [], {}
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
        if _norm(c.get("gerant")) in masques:
            h["masques"] += 1
            continue
        nom_cr = (str(c.get("creatrice") or c.get("onglet") or "").split() or ["?"])[0]
        comptes_l.append({"c": c, "typ": typ, "cr": cr, "cr_nom": nom_cr, "cle": _cle(c["handle"]), "ordre": i})
    _grouper(comptes_l, ctx)
    porte_par = _resoudre_liens(ctx, comptes_l, creatrices)
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
    for L in comptes_l:
        L["lids"] = L["portes"] + L["attaches"]
        L["clics"] = _clics_de(ctx, L["lids"]) if L["lids"] else None

    # -------- liens restants, par créatrice : pages, libérés / hors clipping, attribués sans ligne
    restes = {}
    for lid in sorted(actifs - set(porte_par)):
        cr = ctx.cr_lien(lid, creatrices)
        cr = cr if cr in ordre_cr else ""
        cat = ctx.cat(lid)
        seau = "pages" if cat == "page" else ("liberes" if cat in ("libere", "hors_clipping", "suivi") else "sans_ligne")
        restes.setdefault(cr, {"pages": [], "liberes": [], "sans_ligne": []})[seau].append(lid)

    # -------- tendances
    tend = {"vues": [], "clics": [], "followers": []}
    for L in comptes_l:
        qui = (L["c"].get("gerant") or "sans Gérant").strip()
        if L["vues"] and L["vues_p"]:
            tend["vues"].append((L["vues"][0] - L["vues_p"][0], L["c"]["handle"], qui, L["cr_nom"], _delta_pct(L["vues"][0], L["vues_p"][0]),
                                 L["vues"][0], L["vues_p"][0]))
        if L["clics"] and L["clics"]["comparable"]:
            k = L["clics"]
            tend["clics"].append((k["c7"] - k["c7p"], " + ".join(_slug(ctx.liens[x], x) for x in L["lids"]), qui, L["cr_nom"], k["delta"],
                                  k["c7"], k["c7p"]))
        if L["df7"] is not None and L["followers"] is not None:
            tend["followers"].append((L["df7"], L["c"]["handle"], qui, L["cr_nom"], _delta_abs(L["df7"]), L["followers"],
                                      L["followers"] - L["df7"]))

    # -------- titre et fraîcheur
    p = ctx.p
    ajouter(["Dashboard · mis à jour le " + p.strftime("%d/%m à %Hh%M") + " (Paris)", "", _fraicheur(ctx, e, comptes_l)], "titre")
    ajouter(["", "", "Clics = visites payables GAML (pays francophones) · Vues = vues Instagram des Reels, relevées 48 h après la "
             "publication · cellule vide = pas mesuré (jamais 0 par défaut) · ▲ ▼ = contre les 7 jours d'avant · Mesure = d'où vient "
             "le chiffre"], "legende")
    ajouter([], "vide")

    # -------- CONTRÔLE
    lids_lignes = sorted(porte_par)
    n_anomalies = _section_controle(ajouter, ctx, e, comptes, lids_lignes)
    ajouter([], "vide")

    # -------- TENDANCES
    _section_tendances(ajouter, ctx, tend, len(comptes_l))
    ajouter([], "vide")

    # -------- COMPTES par créatrice
    tot = {"comptes": 0, "fol": [], "r7": [], "v7": [], "lids": []}
    for cr in ordre_cr + ([""] if restes.get("") else []):
        lignes_cr = [L for L in comptes_l if L["cr"] == cr] if cr else []
        r_cr = restes.get(cr, {"pages": [], "liberes": [], "sans_ligne": []})
        if cr and not lignes_cr and not any(r_cr.values()) and not any((hors.get(cr) or {}).values()):
            continue
        _bloc_creatrice(ajouter, ctx, cr, lignes_cr, r_cr, hors.get(cr) or {}, tot)
        ajouter([], "vide")
    tout = _clics_de(ctx, tot["lids"]) if tot["lids"] else {}
    r = _ligne_vide()
    r[C_GERANT], r[C_HANDLE] = "TOTAL", f"{tot['comptes']} comptes"
    r[C_FOL], r[C_R7], r[C_V7] = _v(_somme(tot["fol"])[0]), _v(_somme(tot["r7"])[0]), _v(_somme(tot["v7"])[0])
    if tout:
        r[C_CA], r[C_CH], r[C_C7] = _v(tout["auj"]), _v(tout["hier"]), _v(tout["c7"])
        r[C_DC] = tout["delta"]
        r[C_LIEN] = f"{len(set(tot['lids']))} liens actifs"
        r[C_MES] = _partiel_auj(tout).lstrip(" ·")
    ajouter(r, "total")

    contenu = json.dumps([DASHBOARD_VERSION] + rows[1:], ensure_ascii=False, default=str)
    return {"lignes": rows, "types": kinds, "empreinte": hashlib.sha1(contenu.encode("utf-8")).hexdigest()[:20],
            "comptes": len(comptes_l), "anomalies": n_anomalies, "lids_lignes": lids_lignes}


def _v(x):
    return "" if x is None else x


def _partiel_auj(k: dict) -> str:
    """« · clics du jour : 3/9 liens relus » quand la somme du jour ne couvre pas tous les liens (jamais une somme qui se fait
    passer pour complète)."""
    if k and k.get("auj_tot") and k.get("auj_n") is not None and k["auj_n"] < k["auj_tot"]:
        return f" · clics du jour : {k['auj_n']}/{k['auj_tot']} liens relus"
    return ""


def _fraicheur(ctx: _Ctx, e: dict, comptes_l: list) -> str:
    """« Instagram 14h05 · Clics 16h45 · Metricool J-1 (08/10) · Apify 12,30 $ sur 29 $ ce mois » : l'âge de chaque source."""
    parts = []
    ts_ig = [t for t in (_instant(x) for x in ((ctx.dp or {}).get("t"), ctx.etats.get("leger_iso"), ctx.etats.get("scan_iso"))) if t]
    parts.append("Instagram " + (_hm(max(ts_ig), ctx.j0) if ts_ig else "jamais lu"))
    ts_cl = [t for t in (_instant(v.get("t")) for v in (ctx.clics.get("aujourdhui") or {}).values()
                         if isinstance(v, dict) and str(v.get("jour") or "") == ctx.j0.isoformat()) if t]
    if ts_cl:
        parts.append("Clics " + _hm(max(ts_cl), ctx.j0))
    else:
        jours = sorted(j for v in (ctx.clics.get("jours") or {}).values() if isinstance(v, dict) for j in v
                       if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(j)))
        parts.append("Clics jusqu'au " + date.fromisoformat(jours[-1]).strftime("%d/%m") if jours else "Clics : aucun relevé")
    met = e.get("metricool") if isinstance(e.get("metricool"), dict) else {}
    jour_m = str(met.get("jour") or "")[:10]
    if not jour_m and ctx.seriesok:                                      # sinon : le dernier relevé Metricool des séries
        ts = [_instant(r.get("t")) for L in comptes_l for r in (L.get("serie") or {}).get("releves") or []
              if isinstance(r, dict) and r.get("source") == "metricool" and _instant(r.get("t"))]
        if ts:
            jour_m = (_paris(max(ts)) - timedelta(minutes=1)).date().isoformat()
    if jour_m:
        try:
            ecart = (ctx.j0 - date.fromisoformat(jour_m)).days
            parts.append(f"Metricool J-{ecart} ({date.fromisoformat(jour_m).strftime('%d/%m')})" if ecart >= 1 else "Metricool du jour")
        except ValueError:
            pass
    elif metricool_comptes is None:
        parts.append("Metricool : source indisponible")
    else:
        parts.append("Metricool : aucun relevé")
    if not ctx.seriesok:
        parts.append("séries indisponibles (chiffres des cellules du classeur)")
    b = ctx.etats.get("apify_budget") if isinstance(ctx.etats.get("apify_budget"), dict) else {}
    if b.get("usage_usd") is not None:
        txt = f"Apify {b['usage_usd']:.2f} $".replace(".", ",")
        if b.get("limite_usd"):
            txt += f" sur {b['limite_usd']:.0f} $ ce mois"
        if b.get("projete_usd") is not None:
            txt += f" (projeté {b['projete_usd']:.0f} $" + (f", {int(round(b['part'] * 100))} %" if b.get("part") is not None else "") + ")"
        if b.get("ok") is False:
            txt = "⚠ " + txt + " : passages légers sautés"
        parts.append(txt)
    else:
        parts.append("Apify : budget pas encore lu")
    return " · ".join(parts)


def _section_controle(ajouter, ctx: _Ctx, e: dict, comptes: list, lids_lignes: list):
    """CONTRÔLE (contrat C3) : compteur par famille, les 15 premières anomalies, bouclage des visites 7 j. Renvoie le nombre
    d'anomalies, None si la source manque."""
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
            an = controle.anomalies(*args, etats=ctx.etats, maintenant=ctx.maintenant)
        except TypeError:                                                # contrat strict : six arguments
            an = controle.anomalies(*args)
        an = [a for a in an or [] if isinstance(a, dict)]
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Dashboard : contrôle illisible (%s)", erreur)
        ajouter(["CONTRÔLE", "", f"source indisponible (erreur du contrôle : {type(erreur).__name__})"], "section")
        return None
    n = {g: sum(1 for a in an if a.get("gravite") == g) for g in GRAVITES}
    ajouter(["CONTRÔLE", "", (f"{len(an)} anomalie(s) : {n['bloquant']} bloquante(s), {n['important']} importante(s), {n['info']} info"
                              " · rien n'est corrigé tout seul : à trancher dans le classeur ou dans GAML") if an
             else "aucune anomalie : chaque compte et chaque lien est attribué ✅"], "section")
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
            ajouter([f, k, noms.get(f, f)], "famille", gravite=gr)
    zeros = [f for f, k in compte_f.items() if not k]
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
            b = controle.bouclage(ctx.clics, lids_lignes)
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Dashboard : bouclage illisible (%s)", erreur)
            b = None
        if isinstance(b, dict):
            ecart = int(b.get("ecart") or 0)
            try:
                periode = f"{date.fromisoformat(b['debut']).strftime('%d/%m')} → {date.fromisoformat(b['fin']).strftime('%d/%m')}"
            except (KeyError, ValueError, TypeError):
                periode = "7 j"
            txt = (f"Visites 7 j ({periode}) : {_txt_n(b.get('total') or 0)} = lignes {_txt_n(b.get('lignes') or 0)} + pages "
                   f"{_txt_n(b.get('pages') or 0)} + libérés / hors clipping {_txt_n(b.get('liberes') or 0)} + écart {_txt_n(ecart)}"
                   + (" ✅" if not ecart else " ⚠"))
            if b.get("non_mesures"):
                txt += f" · {len(b['non_mesures'])} lien(s) non mesuré(s) (relevé incomplet), hors des sommes"
            ajouter(["Bouclage", ecart if ecart else "✅", txt], "bouclage", gravite="bloquant" if ecart else "ok")
            for x in (b.get("non_comptes") or [])[:10]:
                ajouter(["", x.get("visites", ""), f"⚠ lien {x.get('url') or x.get('lid')} ({x.get('creatrice') or '?'}"
                         + (f", note « {x.get('note')} »" if x.get("note") else "") + ") : visites portées par aucune ligne"],
                        "anomalie", gravite="bloquant")
    return len(an)


def _section_tendances(ajouter, ctx: _Ctx, tend: dict, n_comptes: int):
    j0 = ctx.j0
    a7, b7 = j0 - timedelta(days=7), j0 - timedelta(days=1)
    va, vb = j0 - timedelta(days=9), j0 - timedelta(days=3)
    ajouter(["TENDANCES", "", f"7 jours ({a7.strftime('%d/%m')} → {b7.strftime('%d/%m')}) contre les 7 jours d'avant · vues des Reels "
             f"publiés du {va.strftime('%d/%m')} au {vb.strftime('%d/%m')}, relevées 48 h après la publication · seulement ce qui est "
             "mesuré sur les deux périodes · classés par écart"], "section")
    ajouter(["Quoi", "Compte / lien", "Gérant", "Δ", "Actuel", "Avant", "Créatrice"], "sous_titre")
    noms = {"vues": ("Vues", "il faut des Reels mesurés à 48 h sur les deux périodes (16 jours de séries)"),
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
    if L["lids"]:
        morceaux.append(" + ".join(_slug(ctx.liens[x], x) for x in L["lids"]) + (" (bio)" if L["bio"] else ""))
    elif L["trio"]:
        morceaux.append(f"(trio) {_slug(ctx.liens[L['trio'][0][0]], L['trio'][0][0])}")
    for lid, porteur in L["ailleurs"]:
        morceaux.append(f"⚠ {_slug(ctx.liens[lid], lid)} déjà compté chez {(porteur['c'].get('gerant') or '?').strip()}")
    noms = {"libere": "libéré", "hors_clipping": "hors clipping", "page": "page de la créatrice", "desactive": "désactivé",
            "supprime": "supprimé", "attribue": "lien d'un clipper", "suivi": "lien suivi"}
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
        r[C_DV] = _delta_pct(L["vues"][0], L["vues_p"][0]) if L["vues_p"] else ""
    r[C_LIEN] = _lien_texte(ctx, L)
    if L["clics"]:
        k = L["clics"]
        r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
    r[C_MES] = L["mesure"]
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
    r[C_V7] = _v(_somme(L["vues"][0] if L["vues"] else None for L in groupe)[0])
    comp = [L for L in groupe if L["vues"] and L["vues_p"]]
    r[C_DV] = _delta_pct(sum(L["vues"][0] for L in comp), sum(L["vues_p"][0] for L in comp)) if comp else ""
    lids = [x for L in groupe for x in L["lids"]]
    if lids:
        k = _clics_de(ctx, lids)
        r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
        r[C_LIEN] = f"{len(set(lids))} lien(s)"
    manques = sum(1 for L in groupe if L["mesure"].startswith(("non lu", "jamais lu", "introuvable")))
    r[C_MES] = f"{len(groupe)} comptes" + (f" · {manques} non mesuré(s) : somme partielle" if manques else "")
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
    r[C_LIEN] = " · ".join(noms)
    k = _clics_de(ctx, lids)
    r[C_CA], r[C_CH], r[C_C7], r[C_DC] = _v(k["auj"]), _v(k["hier"]), _v(k["c7"]), k["delta"]
    manque = k["c7_tot"] - k["c7_n"]
    r[C_MES] = "GAML" + (f" · {manque} lien(s) non relevé(s) sur 7 j" if manque else "") + _partiel_auj(k)
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
    bande[C_V7] = _v(_somme(L["vues"][0] if L["vues"] else None for L in lignes_cr)[0])
    if k_cr:
        bande[C_CA], bande[C_CH], bande[C_C7], bande[C_DC] = _v(k_cr["auj"]), _v(k_cr["hier"]), _v(k_cr["c7"]), k_cr["delta"]
        bande[C_LIEN] = f"{len(set(tous_lids))} liens actifs"
    extra = []
    if hors.get("vivier"):
        extra.append(f"+{hors['vivier']} à créer d'avance")
    if hors.get("ban"):
        extra.append(f"{hors['ban']} BAN rendus")
    if hors.get("masques"):
        extra.append(f"{hors['masques']} masqué(s)")
    bande[C_MES] = " · ".join(extra) + (_partiel_auj(k_cr) if k_cr else "")
    bande[C_MES] = bande[C_MES].lstrip(" ·")
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
    if r_cr["sans_ligne"]:
        ajouter(_ligne_liens(ctx, "⚠ Sans ligne", "liens attribués", r_cr["sans_ligne"], "sans_ligne"), "sans_ligne", cr=cr)
    tot["comptes"] += len(lignes_cr)
    tot["fol"] += [L["followers"] for L in lignes_cr]
    tot["r7"] += [L["r7"] for L in lignes_cr]
    tot["v7"] += [L["vues"][0] if L["vues"] else None for L in lignes_cr]
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
    """La mise en forme conditionnelle (posée une fois par DASHBOARD_VERSION) : ▲ en vert, ▼ en rouge, « ⚠ » en orange, « non lu »
    en ambre, BAN en rouge — sur tout l'onglet, quelle que soit la ligne : le contenu bouge, les règles restent."""
    plage = [{"sheetId": sid, "startColumnIndex": 0, "endColumnIndex": NB}]

    def regle(type_, valeur, texte, fond, gras=True):
        return {"ranges": plage, "booleanRule": {"condition": {"type": type_, "values": [{"userEnteredValue": valeur}]},
                                                 "format": {"textFormat": {"foregroundColor": _rgb(texte), "bold": gras},
                                                            "backgroundColor": _rgb(fond)}}}
    return [regle("TEXT_STARTS_WITH", "▲", "#1B5E20", "#E8F5E9"),
            regle("TEXT_STARTS_WITH", "▼", "#B71C1C", "#FFEBEE"),
            regle("TEXT_STARTS_WITH", "⚠", "#E65100", "#FFF3E0"),
            regle("TEXT_STARTS_WITH", "non lu", "#E65100", "#FFF8E1", gras=False),
            regle("TEXT_EQ", "BAN", "#B71C1C", "#FFCDD2")]


async def _nb_regles(cid: str, sid: int) -> int:
    r = await google_api._appel("GET", f"{google_api.SHEETS}/{cid}", params={"fields": "sheets(properties(sheetId),conditionalFormats)"})
    for s in (r or {}).get("sheets", []):
        if (s.get("properties") or {}).get("sheetId") == sid:
            return len(s.get("conditionalFormats") or [])
    return 0


async def _poser_regles(cid: str, sid: int) -> None:
    """Les règles conditionnelles de l'onglet remplacées par les nôtres (le bot seul écrit dans le Dashboard)."""
    n = await _nb_regles(cid, sid)
    req = [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}} for _ in range(n)]
    req += [{"addConditionalFormatRule": {"rule": rg, "index": i}} for i, rg in enumerate(regles(sid))]
    await google_api.sheets_batch_update(cid, req)


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
    await google_api.sheets_batch_update(cid, requetes(r, sid, int(p.get("lignes") or 0), int(p.get("colonnes") or 0)))
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
