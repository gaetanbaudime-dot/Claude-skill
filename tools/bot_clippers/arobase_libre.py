"""Un @ Instagram n'est donné que s'il est libre (30/10/2026).

Gaëtan (30/10) : « Fais en sorte qu'on arrive vraiment à déterminer si les arobas des comptes Instagram qu'on va donner sont
disponibles ou pas. Il ne faut jamais donner un arobas qui n'est pas disponible. Je compte sur toi par rapport à ça. Comme ça, on
est sûr d'avoir la bonne attribution des clippers. »

Le cas réel qui le justifie (onglet « IG · À trancher », 29/10) : un clipper a reçu `journaldesarah`, un compte qui existait déjà
chez une inconnue (141 abonnés, une bio) ; il a créé une variante, et le suivi a perdu son compte.

Avant d'envoyer le message d'un compte (parcours.envoyer_etape), le bot demande à RapidAPI l'ID Instagram de ce @ (la même route que
le suivi, `instagram_rapidapi.API["id"]`) :

- un ID revient : le @ est **pris**. Il n'est jamais donné ; la ligne du classeur passe en Utilisation « @ pris sur Instagram » et
  une autre ligne est réservée (onboarding.remplacer_arobase_pris) ;
- Instagram ne connaît pas ce @ (introuvable) : il est **libre**, le message part ;
- pas de réponse claire (quota, erreur, délai) : **inconnu**. Le compte n'est pas envoyé, le bot réessaie au tour suivant. Jamais
  de @ donné sur un doute.

Le verdict « pris » est gardé pour toujours (DONNEES/arobases_verifies.json) ; « libre » vaut LIBRE_VALIDE_H heures, puis le @ est
revu. `!arobase @x` (staff) vérifie un @ à la main ; `!arobase-ok @x` le déclare libre après un contrôle humain sur Instagram.

Limites connues :
- un @ d'un compte supprimé ou banni peut rester bloqué par Instagram un moment tout en répondant « introuvable » : le clipper le
  dit alors avec le bouton « ✅ Compte créé » ou `!pseudo`, comme avant ;
- la vérification passe par une API tierce qui lit Instagram : c'est la même dette CGU Meta que le suivi RapidAPI.
Sans RAPIDAPI_KEY, ou avec AROBASE_VERIF=0, rien n'est vérifié (journal au démarrage) : l'ancien comportement.

30/10, 9 h 36 (Gaëtan : « si jamais tu vois qu'il y a des Instagram qui sont pris, tu remplaces les points par des tirets du bas,
les tirets du bas par… des points, ou alors tu rajoutes XO à la fin de l'arobas, comme ça il sera disponible ») : un @ pris n'est
plus remplacé d'abord par une autre ligne du stock. Le bot cherche une variante proche et libre (variantes, variante_libre) et
l'écrit dans la cellule du LOG (parcours.renommer) ; une autre ligne seulement si aucune variante n'est libre.
examen() lit aussi le profil d'un @ pris : un compte du clipper (preuve dans la bio, le nom ou le lien, ou compte tout neuf) n'est
pas un @ « pris par un inconnu »."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

journal = logging.getLogger("arobase_libre")

LIBRE, PRIS, INCONNU = "libre", "pris", "inconnu"
ACTIVE = os.environ.get("AROBASE_VERIF", "1").strip() != "0"
LIBRE_VALIDE_H = int(os.environ.get("AROBASE_LIBRE_VALIDE_H", "6") or 6)
RESERVE_QUOTA = int(os.environ.get("AROBASE_RESERVE_QUOTA", "20") or 20)   # sous ce reste annoncé par RapidAPI : « inconnu »
DELAI_S = int(os.environ.get("AROBASE_DELAI_S", "25") or 25)
FICHIER = Path(os.environ.get("DONNEES_DIR", Path(__file__).with_name("donnees"))) / "arobases_verifies.json"


def norm(handle) -> str:
    return str(handle or "").strip().lower().lstrip("@")


def actif() -> bool:
    """Vrai quand le bot peut vérifier : interrupteur allumé et clé RapidAPI présente."""
    if not ACTIVE:
        return False
    try:
        import instagram_rapidapi as ig
        return bool(ig.CLE)
    except Exception:                                                   # noqa: BLE001
        return False


def _lire() -> dict:
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire(donnees: dict) -> None:
    try:
        FICHIER.parent.mkdir(parents=True, exist_ok=True)
        tmp = FICHIER.with_suffix(".tmp")
        tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FICHIER)
    except OSError as erreur:
        journal.warning("Vérifications des @ non écrites : %s", erreur)


def _noter(handle: str, etat: str, **extra) -> None:
    d = _lire()
    d[norm(handle)] = {"etat": etat, "le": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
    _ecrire(d)


def connu_pris(handle) -> bool:
    """Pur sur le fichier : ce @ a déjà été vu pris sur Instagram (sert à écarter la ligne des stocks, sans appel)."""
    return (_lire().get(norm(handle)) or {}).get("etat") == PRIS


def pris_connus() -> list:
    return sorted(h for h, e in _lire().items() if (e or {}).get("etat") == PRIS)


def forcer_libre(handle, par: str = "") -> None:
    """`!arobase-ok` : un humain a vérifié sur Instagram que le @ est libre (l'API se trompe, ou reste muette)."""
    _noter(handle, "force_libre", par=str(par))


import re as _re

RE_VALIDE = _re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")   # règles d'Instagram
VARIANTES_MAX = int(os.environ.get("AROBASE_VARIANTES_MAX", "6") or 6)
NEUF_ABONNES, NEUF_PUBLICATIONS = 100, 5                                # un compte tout neuf (créé il y a peu)


def variantes(handle) -> list:
    """Pur (30/10, Gaëtan) : les variantes proches d'un @ pris, dans l'ordre d'essai : points en tirets bas, tirets bas en points,
    puis « xo » à la fin (seul, après un tiret bas ou un point), puis les deux combinés. Deux points de suite (« .. ») sont refusés
    par Instagram : jamais proposés. Valides, sans doublon, jamais le @ lui-même."""
    b = norm(handle)
    if not b:
        return []
    cands = []
    if "." in b:
        cands.append(b.replace(".", "_"))
    if "_" in b:
        cands.append(b.replace("_", "."))
    base = b.rstrip("._")
    cands += [b + "xo", base + "_xo", base + ".xo"]
    if "." in b:
        cands.append(b.replace(".", "_") + "xo")
    if "_" in b:
        cands.append(b.replace("_", ".").strip(".") + "xo")
    cands += [b + "x", base + "_x"]
    out = []
    for c in cands:
        c = c[:30].rstrip(".")
        if c and c != b and c not in out and RE_VALIDE.match(c):
            out.append(c)
    return out


async def variante_libre(handle, exclus=()) -> str:
    """La première variante de `handle` vue LIBRE sur Instagram (jamais une variante déjà dans le LOG : `exclus`), sinon ''.
    Une variante douteuse (API muette) est sautée, jamais donnée. 30/10 : clé de Railway refusée → la variante trouvée libre par
    le dernier contrôle GitHub de ce @ (colonne « Variante libre »), s'il a moins de CI_VALIDE_H heures."""
    exclus = {norm(x) for x in exclus or ()}
    if actif() and not cle_refusee():
        for v in variantes(handle)[:VARIANTES_MAX]:
            if v in exclus:
                continue
            if await verdict(v) == LIBRE:
                return v
            if cle_refusee():
                break
        if not cle_refusee():
            return ""
    ci = await depuis_ci(handle)
    v = (ci or {}).get("variante") or ""
    return v if v and v not in exclus and v in variantes(handle) else ""


def vu_libre(handle) -> bool:
    """Pur sur le fichier : ce @ a déjà été vu libre par le bot (ou déclaré libre). S'il existe ensuite, c'est le clipper qui l'a créé."""
    return (_lire().get(norm(handle)) or {}).get("etat") in (LIBRE, "force_libre")


async def examen(handle, creatrice: str = "") -> dict:
    """Le @ sur Instagram, avec son profil quand il existe : {verdict, id, abonnes, publications, nom, bio, prive, a_nous, neuf}.
    a_nous : le profil prouve qu'il est à nous (instagram_rapidapi.preuve_a_nous : bio du bot, prénom de la créatrice, lien) ;
    neuf : au plus NEUF_ABONNES abonnés et NEUF_PUBLICATIONS publications. Jamais d'exception : un doute est INCONNU.
    30/10 : la clé de Railway refusée (401/403) ou une réponse douteuse → le dernier contrôle GitHub de ce @ (depuis_ci), s'il a
    moins de CI_VALIDE_H heures."""
    h = norm(handle)
    res = {"verdict": INCONNU, "handle": h}
    if not h:
        return res
    if not ACTIVE:
        return {**res, "verdict": LIBRE}
    direct = await _examen_direct(h, creatrice) if actif() and not cle_refusee() else None
    if direct and direct.get("verdict") != INCONNU:
        return direct
    ci = await depuis_ci(h)
    if ci:
        return ci
    if not actif() and not CI_SEUL:
        return {**res, "verdict": LIBRE}                                # sans clé ni contrôle : l'ancien comportement
    return direct or res


async def _examen_direct(h: str, creatrice: str) -> dict:
    res = {"verdict": INCONNU, "handle": h}
    try:
        import aiohttp
        import instagram_rapidapi as ig
        if not ig._quota_ok(RESERVE_QUOTA):
            return res
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DELAI_S)) as session:
            chemin, params = ig.API["id"]
            code, corps = await ig.appeler(session, chemin, params(h))
            v, i = lire_reponse(code, corps)
            if v != PRIS:
                if v == LIBRE:
                    _noter(h, LIBRE)
                else:
                    _noter_refus(code)
                return {**res, "verdict": v}
            res.update({"verdict": PRIS, "id": i})
            chemin, params = ig.API["profil"]
            code, corps = await ig.appeler(session, chemin, params(i))
        if code != 200 or not isinstance(corps, dict):
            return {**res, "profil_lu": False}
        p, b = ig.lire_profil(corps), ig.lire_bio(corps)
        r = {"bio": b.get("bio"), "nom": b.get("nom"), "liens": b.get("liens") or [], "prive": p.get("prive") is True}
        res.update({"profil_lu": True, "abonnes": p.get("followers"), "publications": p.get("publications"), "nom": b.get("nom") or "",
                    "bio": (b.get("bio") or "")[:120], "prive": p.get("prive") is True,
                    "a_nous": bool(creatrice) and ig.preuve_a_nous(r, creatrice),
                    "neuf": (p.get("followers") or 0) <= NEUF_ABONNES and (p.get("publications") or 0) <= NEUF_PUBLICATIONS})
        return res
    except Exception as erreur:                                         # noqa: BLE001 — un doute, jamais une conclusion
        journal.warning("Examen de @%s : %s", h, type(erreur).__name__)
        return res


# ------------------------------------------------------------------ 30/10 : le contrôle des @ lancé par GitHub
# La clé RapidAPI de Railway répond 403 (pas d'abonnement FlashAPI), celle de GitHub marche. Le workflow « Contrôle des @ »
# (controle_arobases_ci.py) examine toutes les quelques heures les @ à créer attribués et les prochains du stock, et écrit
# l'onglet ONGLET_CI du tableur App clippers · usage. Le bot le lit quand sa propre clé est refusée ou muette : un @ vu libre par
# GitHub il y a moins de CI_VALIDE_H heures est libre ; plus vieux ou absent : doute, rien n'est donné.
ONGLET_CI = "IG · Contrôle des @"
ENTETE_CI = ["@", "Créatrice", "Onglet", "Ligne", "Gérant", "Instagram", "Abonnés", "Publications", "Nom", "Bio", "À nous", "Neuf",
             "Vérifié le", "Variante libre"]
CI_VALIDE_H = int(os.environ.get("AROBASE_CI_VALIDE_H", "12") or 12)
CI_PROCHAINS = int(os.environ.get("AROBASE_CI_PROCHAINS", "4") or 4)     # prochains @ du stock contrôlés par créatrice
CI_SEUL = os.environ.get("AROBASE_CI_SEUL", "1").strip() != "0"            # sans clé : le contrôle GitHub, jamais « libre » d'office
REFUS_PAUSE_S = 3600
_refus = {"jusqua": 0.0}
_cache_ci = {"le": 0.0, "par_handle": {}}


def cle_refusee() -> bool:
    import time
    return time.time() < _refus["jusqua"]


def _noter_refus(code) -> None:
    """Une réponse 401/403 : la clé n'a pas accès à l'API. Plus d'appel direct pendant REFUS_PAUSE_S (le contrôle GitHub prend le
    relais) ; une ligne de journal par pause."""
    import time
    if code in (401, 403) and not cle_refusee():
        _refus["jusqua"] = time.time() + REFUS_PAUSE_S
        journal.warning("Clé RapidAPI de Railway refusée (%s) : le contrôle GitHub des @ prend le relais pendant %s min",
                        code, REFUS_PAUSE_S // 60)


def _stock(gerant) -> bool:
    g = str(gerant or "").strip().lower()
    return not g or g in ("stock", "libre", "-", "x", "?", "dispo")


def cibles_ci(comptes: list, prochains: int = None) -> list:
    """Pur : les lignes « à créer » à contrôler, une fois chacune : attribuées à un clipper (remise imminente), puis les
    `prochains` premières du stock de chaque onglet, dans l'ordre du LOG. [{handle, creatrice, onglet, ligne, gerant}]."""
    prochains = CI_PROCHAINS if prochains is None else prochains
    attribuees, stock, vus, par_onglet = [], [], set(), {}
    for c in comptes or []:
        e = str(c.get("etat") or "").strip().lower()
        h = norm(c.get("handle"))
        if not h or h in vus or not ("créer" in e or "creer" in e):
            continue
        vus.add(h)
        x = {"handle": h, "creatrice": str(c.get("creatrice") or c.get("onglet") or ""), "onglet": str(c.get("onglet") or ""),
             "ligne": str(c.get("ligne") or ""), "gerant": str(c.get("gerant") or "").strip()}
        if not _stock(x["gerant"]):
            attribuees.append(x)
        elif par_onglet.get(x["onglet"], 0) < prochains:
            par_onglet[x["onglet"]] = par_onglet.get(x["onglet"], 0) + 1
            stock.append(x)
    return attribuees + stock


def ligne_ci(c: dict, ex: dict, maintenant: datetime, variante: str = "") -> list:
    """Pur : la ligne de l'onglet ONGLET_CI pour un @ examiné (`variante` : la première variante vue libre d'un @ pris par un
    inconnu)."""
    ex = ex or {}
    ig = {LIBRE: "libre", PRIS: "existe"}.get(ex.get("verdict"), "pas lu")
    if ex.get("verdict") == PRIS and ex.get("profil_lu") is False:
        ig = "existe, profil illisible"

    def n(v):
        return "" if v is None else str(v)
    return [c.get("handle", ""), c.get("creatrice", ""), c.get("onglet", ""), c.get("ligne", ""), c.get("gerant", ""), ig,
            n(ex.get("abonnes")), n(ex.get("publications")), str(ex.get("nom") or "")[:80], str(ex.get("bio") or "")[:120],
            "oui" if ex.get("a_nous") else "", "oui" if ex.get("neuf") else "", maintenant.isoformat(timespec="seconds"),
            variante or ""]


def lire_ligne_ci(ligne: list, maintenant: datetime = None, valide_h: int = None):
    """Pur : une ligne de l'onglet ONGLET_CI → le même dictionnaire qu'examen(), ou None (pas lu, illisible ou trop vieux)."""
    valide_h = CI_VALIDE_H if valide_h is None else valide_h
    ligne = list(ligne or []) + [""] * (len(ENTETE_CI) - len(ligne or []))
    ig, le = str(ligne[5]).strip(), str(ligne[12]).strip()
    try:
        quand = datetime.fromisoformat(le)
        quand = quand if quand.tzinfo else quand.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if (maintenant or datetime.now(timezone.utc)) - quand > timedelta(hours=valide_h):
        return None

    def entier(v):
        try:
            return int(float(str(v).replace(",", ".")))
        except ValueError:
            return None
    if ig == "libre":
        return {"verdict": LIBRE, "handle": norm(ligne[0]), "source": "github", "le": le}
    if ig == "existe":
        return {"verdict": PRIS, "handle": norm(ligne[0]), "profil_lu": True, "abonnes": entier(ligne[6]),
                "publications": entier(ligne[7]), "nom": ligne[8], "bio": ligne[9], "a_nous": ligne[10] == "oui",
                "neuf": ligne[11] == "oui", "variante": norm(ligne[13]), "source": "github", "le": le}
    if ig.startswith("existe"):
        return {"verdict": PRIS, "handle": norm(ligne[0]), "profil_lu": False, "source": "github", "le": le}
    return None


def plage_ci() -> str:
    """Pur : toutes les colonnes de l'onglet du contrôle (A jusqu'à la dernière de ENTETE_CI), sans l'en-tête."""
    return f"'{ONGLET_CI}'!A2:{chr(ord('A') + len(ENTETE_CI) - 1)}"


async def depuis_ci(handle):
    """Le dernier contrôle GitHub de ce @ (onglet ONGLET_CI, relu au plus toutes les 5 minutes), ou None. Jamais d'exception."""
    import time
    h = norm(handle)
    if not h:
        return None
    if time.time() - _cache_ci["le"] > 300:
        try:
            import google_api
            if not google_api.actif():                                  # sans compte de service : pas d'onglet à lire
                _cache_ci["le"] = time.time()
                return None
            import paie_clics
            classeur = await paie_clics._classeur_usage()
            lignes = await google_api.sheets_lire(classeur, plage_ci()) if classeur else []
            _cache_ci.update({"le": time.time(), "par_handle": {norm(l[0]): l for l in lignes if l and norm(l[0])}})
        except Exception as erreur:                                     # noqa: BLE001 — sans l'onglet : doute
            journal.info("Contrôle GitHub des @ illisible : %s", type(erreur).__name__)
            _cache_ci["le"] = time.time()
    return lire_ligne_ci(_cache_ci["par_handle"].get(h))


def lire_reponse(code: int, corps) -> tuple:
    """Pur : (verdict, id) d'une réponse de la route « id » de RapidAPI. Un ID = pris ; introuvable = libre ; le reste = inconnu."""
    import instagram_rapidapi as ig
    i = ig.lire_id(corps) if code == 200 else None
    if i:
        return PRIS, i
    if ig.introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False):
        return LIBRE, None
    return INCONNU, None


def _encore_libre(e: dict) -> bool:
    try:
        le = datetime.fromisoformat(str(e.get("le")))
        le = le if le.tzinfo else le.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) - le < timedelta(hours=LIBRE_VALIDE_H)


async def verdict(handle) -> str:
    """LIBRE, PRIS ou INCONNU pour ce @, avant de le donner. Jamais d'exception. Sans vérification possible (actif() faux) : LIBRE,
    l'ancien comportement."""
    h = norm(handle)
    if not h:
        return INCONNU
    if not ACTIVE:
        return LIBRE
    e = _lire().get(h) or {}
    if e.get("etat") == PRIS:
        return PRIS
    if e.get("etat") == "force_libre" or (e.get("etat") == LIBRE and _encore_libre(e)):
        return LIBRE
    if not actif() or cle_refusee():
        ci = await depuis_ci(h)                                         # 30/10 : la clé de Railway est refusée, GitHub vérifie
        return ci["verdict"] if ci else (LIBRE if not actif() and not CI_SEUL else INCONNU)
    try:
        import aiohttp
        import instagram_rapidapi as ig
        if not ig._quota_ok(RESERVE_QUOTA):
            journal.warning("@%s non vérifié : quota RapidAPI trop bas", h)
            return INCONNU
        chemin, params = ig.API["id"]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DELAI_S)) as session:
            code, corps = await ig.appeler(session, chemin, params(h))
        resultat, i = lire_reponse(code, corps)
    except Exception as erreur:                                         # noqa: BLE001 — un doute, jamais un @ donné
        journal.warning("@%s non vérifié : %s", h, type(erreur).__name__)
        return INCONNU
    if resultat == INCONNU:
        _noter_refus(code)
        ci = await depuis_ci(h)
        if ci:
            journal.info("@%s : réponse RapidAPI %s, contrôle GitHub du %s : %s", h, code, ci.get("le"), ci["verdict"])
            return ci["verdict"]
        journal.warning("@%s non vérifié : réponse RapidAPI %s", h, code)
        return INCONNU
    _noter(h, resultat, **({"id": i} if i else {}))
    journal.info("@%s vérifié sur Instagram : %s", h, resultat)
    return resultat
