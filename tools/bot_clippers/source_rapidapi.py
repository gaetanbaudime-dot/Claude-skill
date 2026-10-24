"""La source Instagram du bot : le suivi RapidAPI (24/10/2026, Gaëtan : « on n'utilise plus Apify, on utilise RapidAPI… pourquoi tu
me parles encore de Apify ? »).

Le suivi RapidAPI (instagram_rapidapi.py, lancé 3 fois par jour par GitHub Actions, .github/workflows/suivi-instagram.yml) relit
chaque compte vivant du LOG DASHBOARD IG par son ID Instagram et publie dans le tableur d'usage :
  « IG · Comptes » : une ligne par compte (statut public / privé / introuvable, followers, publications, Profil relu le…) ;
  « IG · Reels »   : chaque Reel des 60 derniers jours (@, code, lien, publié le, vues).
Jusqu'au 24/10, le scan des états (etats_comptes.py) relisait les mêmes comptes chez Apify, payant, pour écrire Followers,
Reels Hier et Reels 7 j dans le LOG DASHBOARD et nourrir Dashboard, séries, parcours et apps. Ce module relit les deux onglets et
rend, pour chaque @ demandé, une fiche au format Apify que etats_comptes._lire_items sait déjà lire : tout ce qui suit le scan
reste identique, plus aucun appel Apify.

Règles (pures, testées par tests/test_source_rapidapi.py) :
- un @ absent de « IG · Comptes » (à créer, BAN, état que le suivi ne relit pas) n'est pas suivi : `hors_suivi`, jamais compté
  comme un passage manqué ni comme une panne ;
- un profil jamais relu, ou relu il y a plus de FRAICHEUR_H heures (suivi en panne) : non lu, rien n'est conclu ni écrit ;
- « introuvable » : la réponse explicite de RapidAPI (compte supprimé, banni, @ changé sans ID connu) ;
- Reels : tous ceux de « IG · Reels » (60 jours, pas 12 comme chez Apify) ; ils ne sont « lus » que si le compte a été relu
  depuis minuit (Paris) — sinon « Reels Hier » serait compté sur une veille vue à moitié : les cellules sont alors gardées.
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("source_rapidapi")

ONGLET_COMPTES, ONGLET_REELS = "IG · Comptes", "IG · Reels"
FRAICHEUR_H = float(os.environ.get("SOURCE_IG_FRAICHEUR_H", "30") or 30)
FENETRE_REELS_J = 59                    # « IG · Reels » : les 60 derniers jours (instagram_rapidapi.lignes_reels)
CACHE_S = 120                           # le suivi publie 3 fois par jour : une lecture sert tous les appels d'un passage
# colonnes de « IG · Comptes » (instagram_rapidapi.ENTETE_COMPTES) et de « IG · Reels » (ENTETE_REELS)
C_HANDLE, C_ID, C_STATUT, C_FOLLOWERS, C_PUBLICATIONS, C_PROFIL_LE, C_REELS_LE, C_RENOMME = 3, 4, 5, 6, 9, 20, 21, 22
R_HANDLE, R_CODE, R_LIEN, R_PUBLIE, R_VUES = 3, 4, 5, 6, 7

_cache = {"t": 0.0, "lignes": None}


def _cle(h) -> str:
    return str(h or "").strip().lstrip("@").strip().lower()


def _instant(v):
    if v in (None, ""):
        return None
    t = str(v).strip()
    try:
        if t.isdigit():
            return datetime.fromtimestamp(int(t), tz=timezone.utc)
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _entier(v):
    t = str(v if v is not None else "").replace(" ", "").replace("\xa0", "").replace(" ", "").strip()
    if t == "":
        return None
    try:
        n = int(float(t.replace(",", ".")))
    except ValueError:
        return None
    return n if n >= 0 else None


def _cellule(ligne: list, i: int) -> str:
    return str(ligne[i]).strip() if i < len(ligne) and ligne[i] is not None else ""


def _minuit_paris(maintenant: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        p = maintenant.astimezone(ZoneInfo("Europe/Paris"))
    except Exception:                                                   # noqa: BLE001
        p = maintenant + timedelta(hours=2)
    return p.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _sans_entete(lignes: list, premiere: str) -> list:
    lignes = [l for l in (lignes or []) if isinstance(l, list)]
    if lignes and _cellule(lignes[0], 0).lower() == premiere.lower():
        return lignes[1:]
    return lignes


def comptes(lignes: list) -> dict:
    """« IG · Comptes » (en-tête compris ou non) → {@ : {id, statut, followers, publications, profil_le, reels_le, renomme_en}}.
    Un compte renommé (« Renommé en ») se trouve sous ses deux @ ; un @ en double garde sa première ligne."""
    out = {}
    for l in _sans_entete(lignes, "Créatrice"):
        h = _cle(_cellule(l, C_HANDLE))
        if not h:
            continue
        c = {"handle": h, "id": _cellule(l, C_ID), "statut": _cellule(l, C_STATUT).lower(),
             "followers": _entier(_cellule(l, C_FOLLOWERS)), "publications": _entier(_cellule(l, C_PUBLICATIONS)),
             "profil_le": _instant(_cellule(l, C_PROFIL_LE)), "reels_le": _instant(_cellule(l, C_REELS_LE)),
             "renomme_en": _cle(_cellule(l, C_RENOMME))}
        out.setdefault(h, c)
        if c["renomme_en"]:
            out.setdefault(c["renomme_en"], c)
    return out


def reels(lignes: list) -> dict:
    """« IG · Reels » → {@ : [{code, lien, publie (datetime), vues}]}, un Reel une fois (même code), le plus récent d'abord."""
    out, vus = {}, set()
    for l in _sans_entete(lignes, "Créatrice"):
        h, code = _cle(_cellule(l, R_HANDLE)), _cellule(l, R_CODE)
        quand = _instant(_cellule(l, R_PUBLIE))
        if not h or not code or quand is None or (h, code) in vus:
            continue
        vus.add((h, code))
        out.setdefault(h, []).append({"code": code, "lien": _cellule(l, R_LIEN) or f"https://www.instagram.com/reel/{code}/",
                                      "publie": quand, "vues": _entier(_cellule(l, R_VUES))})
    for liste in out.values():
        liste.sort(key=lambda r: r["publie"], reverse=True)
    return out


def fiches(cles: list, lignes_comptes: list, lignes_reels: list, maintenant: datetime = None) -> tuple:
    """(items au format Apify, infos par clé). `items` va tel quel à etats_comptes._lire_items ; `infos[clé]` dit ce que la
    fiche ne peut pas dire elle-même : {"suivi": False} (hors suivi), {"frais": False} (profil trop vieux ou jamais relu), et pour
    un compte lu {"reels_lus", "couvre", "releve_le", "reels_le"}."""
    maintenant = maintenant or datetime.now(timezone.utc)
    par_compte, par_reels = comptes(lignes_comptes), reels(lignes_reels)
    limite = maintenant - timedelta(hours=FRAICHEUR_H)
    minuit = _minuit_paris(maintenant)
    items, infos = [], {}
    for k in dict.fromkeys(_cle(h) for h in cles or []):
        if not k:
            continue
        c = par_compte.get(k)
        if c is None:
            infos[k] = {"suivi": False}
            continue
        if c["profil_le"] is None or c["profil_le"] < limite or c["profil_le"] > maintenant + timedelta(minutes=5):
            infos[k] = {"suivi": True, "frais": False}
            continue
        info = {"suivi": True, "frais": True, "releve_le": c["profil_le"].isoformat(timespec="seconds"),
                "reels_le": c["reels_le"].isoformat(timespec="seconds") if c["reels_le"] else ""}
        infos[k] = info
        if c["statut"] == "introuvable":
            items.append({"username": k, "error": "not_found", "errorDescription": "introuvable (suivi RapidAPI)"})
            continue
        prive = c["statut"] in ("privé", "prive", "private")
        liste = [] if prive else par_reels.get(k) or par_reels.get(c["handle"]) or []
        if c["renomme_en"] and not liste:
            liste = par_reels.get(c["renomme_en"]) or []
        posts = [{"shortCode": r["code"], "url": r["lien"], "timestamp": r["publie"].isoformat(timespec="seconds"),
                  "type": "Video", "productType": "clips", "videoPlayCount": r["vues"], "isPinned": False, "_rapidapi": True}
                 for r in liste]
        items.append({"username": k, "id": c["id"], "followersCount": c["followers"], "postsCount": c["publications"],
                      "private": prive, "latestPosts": posts})
        lus = (not prive) and c["reels_le"] is not None and c["reels_le"] >= minuit
        info["reels_lus"] = lus
        info["couvre"] = ((c["reels_le"] - timedelta(days=FENETRE_REELS_J)) if lus else maintenant).isoformat(timespec="seconds")
    return items, infos


def ajuster(out: dict, infos: dict) -> dict:
    """Après etats_comptes._lire_items : ce que dit le suivi et que la fiche Apify ne disait pas. Un compte hors suivi ou pas
    relu à temps est non lu (`budget` : jamais compté comme un passage manqué s'il est hors suivi) ; un compte lu voit tous ses
    Reels sur 60 jours (`plafonne` faux, `couvre` = début de la fenêtre), lus seulement s'il a été relu depuis minuit."""
    for k, info in (infos or {}).items():
        f = out.get(k)
        if not isinstance(f, dict):
            continue
        f["source"] = "rapidapi"
        if not info.get("suivi"):
            f.update({"lu": False, "budget": True, "hors_suivi": True})
            continue
        if not info.get("frais"):
            f.update({"lu": False, "vieux": True})
            continue
        f["releve_le"] = info.get("releve_le") or ""
        # l'heure du relevé RapidAPI, pas celle du passage du bot : la série (etats_comptes._alimenter_series) date le relevé de
        # ce qui a été vu, et deux passages qui relisent le même relevé n'en font qu'un (même instant, même source)
        f["collecte_iso"] = f["releve_le"]
        if f.get("lu") and f.get("existe") and not f.get("prive") and not f.get("restreint"):
            f["reels_lus"] = bool(info.get("reels_lus"))
            f["plafonne"] = False
            f["couvre"] = info.get("couvre") or ""
    return out


def dernier_releve(lignes_comptes: list, maintenant: datetime = None) -> str:
    """L'heure (ISO UTC) du relevé de profil le plus récent de « IG · Comptes » — celle du dernier passage du suivi —, '' si aucun.
    Une date dans le futur (horloge fausse) est ignorée."""
    maintenant = maintenant or datetime.now(timezone.utc)
    ts = [c["profil_le"] for c in comptes(lignes_comptes).values()
          if c["profil_le"] is not None and c["profil_le"] <= maintenant + timedelta(minutes=5)]
    return max(ts).isoformat(timespec="seconds") if ts else ""


async def lire_onglets(forcer: bool = False):
    """(lignes de « IG · Comptes », lignes de « IG · Reels ») du tableur d'usage, en un appel, gardées CACHE_S secondes ; None si
    le tableur est introuvable ou Google ne répond pas (l'appelant ne conclut rien)."""
    if not forcer and _cache["lignes"] is not None and time.monotonic() - _cache["t"] < CACHE_S:
        return _cache["lignes"]
    try:
        import google_api
        import paie_clics
        classeur = await paie_clics._classeur_usage()
        if not classeur:
            journal.warning("Suivi RapidAPI : tableur d'usage introuvable, Instagram non relu")
            return None
        blocs = await google_api.sheets_lire_plusieurs(classeur, [f"'{ONGLET_COMPTES}'!A1:W", f"'{ONGLET_REELS}'!A1:K"])
    except Exception as erreur:                                         # noqa: BLE001 — jamais d'exception vers le scan
        journal.warning("Suivi RapidAPI : onglets illisibles (%s)", type(erreur).__name__)
        return None
    if len(blocs) < 2 or not blocs[0]:
        journal.warning("Suivi RapidAPI : « %s » vide, Instagram non relu", ONGLET_COMPTES)
        return None
    _cache.update({"t": time.monotonic(), "lignes": (blocs[0], blocs[1])})
    return _cache["lignes"]
