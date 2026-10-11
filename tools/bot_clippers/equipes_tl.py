"""Équipes de Team Leaders et managers (grille de Gaëtan du 10/10, lot L10 de la revue du recrutement).

La grille, telle que Gaëtan l'a écrite le 10/10 :

  - clipper et TL : 0,05 $ la visite payée, payés le 5 et le 20 (paie_clics, inchangé ici) ;
  - TL : en plus, TL_PRIME_VA_USD (10 $) par VA de son équipe à TL_SEUIL_VA (500) visites payées ou plus sur la période ;
  - manager : MANAGER_PRIME_USD (75 $) par équipe dont il a la charge, avec un TL, à MANAGER_SEUIL_EQUIPE (3 000) ou plus.

« Au-dessus de » se lit « ou plus ». Une visite payée = pays francophones, hors robots, sur la période de paie du 5 au 19 ou du
20 au 4 : ni les clics GAML bruts, ni 15 jours glissants.

Modèle (equipes.json, clé = uid Discord, jamais le prénom ; rien dans roster.json) :

  - fiche du TL : « chef » (la créatrice), « chef_depuis » (AAAA-MM-JJ), « chef_par » ; un mandat fini part dans « chef_passe » ;
  - fiche du manager : « manager_de » (créatrices), « manager_depuis », « manager_par » ; un mandat fini part dans « manager_passe ».

Un VA appartient à l'équipe de fiche['creatrice'] s'il est au clic, n'est TL d'aucune équipe, n'est pas exclu de la paie au clic
(CLICS_EXCLURE) et est au registre le dernier jour de la période. Toutes ses visites payées, tous liens confondus (clipper multi),
comptent pour son seuil et pour CETTE équipe seulement.

Garde-fous (revue du 10/10) :

  - le TL n'est le VA d'aucune équipe, et ne compte pas dans le total de la sienne (EQUIPE_COMPTE_TL=0) ;
  - un manager ne touche jamais les 75 $ d'une équipe dont il est TL, et ses propres visites ne comptent pas dans le total d'une
    équipe qu'il manage (MANAGER_COMPTE=0, revue L10 R2) ;
  - une prime n'est jamais refusée seule : TOUTE ligne payée est « à vérifier » (Gaëtan contrôle à la main 5 abonnés par VA
    primé, Infloww / MyPulse) ; « ⚠️ à vérifier : … » en plus si un jour n'est pas relevé, si moins de PRIME_PREUVE_REELS Reels
    sont vus, ou si la part de robots ou de visites non francophones est hors norme ;
  - rien n'est payé avant PRIMES_EQUIPES_DEPUIS (première période primée : 20/10 → 04/11, payée le 05/11), et rien n'est affiché
    comme dû sur une période non primée ;
  - nomination par les admins seulement (`!tl`, `!manager`), jamais par le rôle Manager ; le rôle « Team Leader » n'a aucune
    permission (jamais posé s'il en garde une), et un porteur du rôle Manager ne peut pas être nommé TL, même en MP ;
  - une variable Railway mal saisie (« 0,25 », « 3 000 ») ne bloque jamais le démarrage : lue à la française, sinon valeur par
    défaut et avertissement dans `!tl liste`.

Le module ne connaît ni bot_discord ni paie_clics : la mesure (`payees`, lot L11), la preuve de publication (`reels_vus`) et les
jours non relevés sont injectés, comme le régime et les exclus (`configurer`).
"""

import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

import discord

journal = logging.getLogger("equipes_tl")
AVERTISSEMENTS = []                                                     # variables Railway illisibles : montrées dans `!tl liste`


def _nombre(nom: str, defaut, type_=float, part: bool = False):
    """Une variable Railway numérique, lue à la française, sans JAMAIS lever d'exception à l'import (revue L10, R4 : une erreur
    ici arrêterait tout le bot) : « 0,25 », « 7,5 », « 3 000 », « 25 % » sont lus ; illisible ou négatif → la valeur par défaut,
    avec un avertissement au journal et dans `!tl liste`. `part` : une part (0 à 1), « 25 » se lit 25 %."""
    brut = str(os.environ.get(nom, "") or "")
    s = "".join(brut.split())                                           # espaces, insécables et fines insécables comprises
    if not s:
        return defaut
    try:
        pourcent = s.endswith("%")
        s = s.rstrip("%")
        if type_ is int and re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):  # « 3.000 » ou « 3,000 » : séparateur de milliers
            s = re.sub(r"[.,]", "", s)
        v = float(s.replace(",", "."))
        if pourcent or (part and v > 1):
            v /= 100
        if v != v or v in (float("inf"), float("-inf")) or v < 0 or (type_ is int and v != int(v)):
            raise ValueError(brut)
        return int(v) if type_ is int else v
    except (ValueError, OverflowError):
        texte = f"{nom} illisible (« {brut} ») : {defaut} gardé"
        journal.warning(texte)
        AVERTISSEMENTS.append(texte)
        return defaut


def _oui(nom: str, defaut: str = "0") -> bool:
    return str(os.environ.get(nom, defaut) or defaut).strip().lower() in ("1", "oui", "vrai", "true", "yes")


TL_PRIME_VA_USD = _nombre("TL_PRIME_VA_USD", 10.0)
TL_SEUIL_VA = _nombre("TL_SEUIL_VA", 500, int)
MANAGER_PRIME_USD = _nombre("MANAGER_PRIME_USD", 75.0)
MANAGER_SEUIL_EQUIPE = _nombre("MANAGER_SEUIL_EQUIPE", 3000, int)
EQUIPE_COMPTE_TL = _oui("EQUIPE_COMPTE_TL")                             # 0 : le TL hors du total de son équipe
# Revue L10 (R2) : un manager qui clippe lui-même sur une créatrice qu'il manage reste VA de cette équipe (le TL est primé sur
# lui), mais ses visites ne comptent pas dans le total qui le paie (sinon 2 050 à lui + 1 000 d'équipe = 75 $ sur sa production).
MANAGER_COMPTE = _oui("MANAGER_COMPTE")
PRIME_PREUVE_REELS = _nombre("PRIME_PREUVE_REELS", 10, int)             # Reels vus sur la période, sinon « à vérifier »
# Première période primée (son premier jour, AAAA-MM-JJ ou JJ/MM/AAAA) ; vide = rien de payé. 10/10 : la grille est annoncée en
# cours de période, donc la première prime porte sur le 20/10 → 04/11, payée le 05/11.
PRIMES_EQUIPES_DEPUIS = os.environ.get("PRIMES_EQUIPES_DEPUIS", "2026-10-20").strip()
PRIME_ECART_NORME = _nombre("PRIME_ECART_NORME", 0.25, part=True)       # écart à la norme (25 points) jugé anormal
PRIME_VOLUME_MIN = _nombre("PRIME_VOLUME_MIN", 100, int)                # en dessous, ni part ni Reels ne sont jugés
ROLE_TL_NOM = os.environ.get("ROLE_TL_NOM", "Team Leader").strip() or "Team Leader"
LIMITE_MESSAGE = 1900

_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER_EQUIPES ; facultatifs : FICHIER_SORTIS, ADMIN_IDS, est_manager(membre),
    membre_par_id(uid), nom_de(uid), regime(uid) -> « clic » | « fixe », exclu(uid) -> bool ou exclus (prénoms normalisés),
    creatrices() -> noms, lire_clics() -> clics.json, payees(d, uid, debut, fin), reels_vus(uid, debut, fin),
    jours_manquants(d, uid, debut, fin), heure_paris()."""
    _deps.update(deps or {})


# ------------------------------------------------------------------ outils
def _n(t) -> str:
    """Minuscules, sans accents, sans espaces autour : « Chloé » et « chloe » sont la même créatrice."""
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _jour(x):
    """Une date depuis `date`, `datetime` ou « AAAA-MM-JJ… » ; None si illisible."""
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x or "")[:10])
    except ValueError:
        return None


def _aujourdhui() -> date:
    try:
        return _deps["heure_paris"]().date()
    except Exception:                                                   # noqa: BLE001
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo("Europe/Paris")).date()
        except Exception:                                               # noqa: BLE001
            return (datetime.now(timezone.utc) + timedelta(hours=2)).date()


def _entier(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def _usd(x) -> str:
    x = round(float(x or 0), 2)
    return f"{int(x)} $" if x == int(x) else f"{x:.2f} $".replace(".", ",")


def _fiches() -> dict:
    return _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) or {}


def _ecrire_fiches(fiches: dict):
    _deps["ecrire_json"](_deps["FICHIER_EQUIPES"], fiches)


def _sortis() -> list:
    if not _deps.get("FICHIER_SORTIS"):
        return []
    s = _deps["lire_json"](_deps["FICHIER_SORTIS"], []) or []
    return s if isinstance(s, list) else []


def _admins() -> set:
    return {str(i) for i in (_deps.get("ADMIN_IDS") or ())}


def est_admin(membre) -> bool:
    return membre is not None and str(getattr(membre, "id", "")) in _admins()


def _a_role_manager(membre) -> bool:
    """Le rôle Discord « Manager » (staff complet : codes, `!wallet`, `!lien forcer`), admins mis à part."""
    if membre is None or est_admin(membre):
        return False
    if _deps.get("est_manager"):
        try:
            return bool(_deps["est_manager"](membre))
        except Exception:                                               # noqa: BLE001
            pass
    return any(_n(getattr(r, "name", "")) in ("manager", "manageur") for r in getattr(membre, "roles", None) or [])


def _membre(uid):
    try:
        return _deps["membre_par_id"](str(uid)) if _deps.get("membre_par_id") else None
    except Exception:                                                   # noqa: BLE001
        return None


def nom_de(uid, fiche=None) -> str:
    """Le prénom affiché d'un uid : la dépendance `nom_de`, le pseudo du membre, la fiche, sinon « id …1234 »."""
    uid = str(uid)
    if _deps.get("nom_de"):
        try:
            nom = str(_deps["nom_de"](uid) or "").strip()
            if nom:
                return nom
        except Exception:                                               # noqa: BLE001
            pass
    m = _membre(uid)
    if m is not None and str(getattr(m, "display_name", "") or "").strip():
        return str(m.display_name).strip()
    fiche = fiche if fiche is not None else (_fiches().get(uid) or {})
    for cle in ("prenom_distinct", "prenom", "nom"):
        if str(fiche.get(cle) or "").strip():
            return str(fiche[cle]).strip()
    return f"id …{uid[-4:]}"


def _regime(uid) -> str:
    if not _deps.get("regime"):
        return "clic"
    try:
        return str(_deps["regime"](str(uid)) or "")
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Régime de %s illisible (%s) : hors équipe", uid, erreur)
        return ""                                                       # prudence : ni VA ni prime sur un régime inconnu


def _exclu(uid, fiche=None) -> bool:
    """Exclu de la paie au clic (CLICS_EXCLURE : Rianah, le staff…) : jamais VA d'une équipe."""
    if _deps.get("exclu"):
        try:
            return bool(_deps["exclu"](str(uid)))
        except Exception:                                               # noqa: BLE001
            return True
    exclus = {_n(p) for p in (_deps.get("exclus") or ())}
    if not exclus:
        return False
    mots = nom_de(uid, fiche).split()
    return bool(mots) and _n(mots[0]) in exclus


def _affiche(c: str) -> str:
    c = str(c or "").strip()
    return c if c != c.lower() else c[:1].upper() + c[1:]


def creatrices_connues(fiches=None) -> dict:
    """{nom normalisé : nom affiché} : les créatrices de la dépendance `creatrices` (le roster), puis celles du registre."""
    connues = {}
    source = _deps.get("creatrices")
    try:
        noms = source() if callable(source) else (source or ())
    except Exception:                                                   # noqa: BLE001
        noms = ()
    for c in list(noms) + [f.get("creatrice") for f in (fiches if fiches is not None else _fiches()).values()
                           if isinstance(f, dict)]:
        if str(c or "").strip():
            k = _n(c)
            if k not in connues or (connues[k] == connues[k].lower() and str(c) != str(c).lower()):
                connues[k] = _affiche(c)
    return connues


# ------------------------------------------------------------------ périodes (même règle que paie_clics.periode)
def periode(cle: str, mois: str = "", jour=None) -> tuple:
    """`20` : 5 → 19 de `mois` (paie du 20) ; `5` : 20 du mois précédent → 4 de `mois` (paie du 5)."""
    ref = _jour(jour) or _aujourdhui()
    annee, m = (int(mois[:4]), int(mois[5:7])) if mois else (ref.year, ref.month)
    if str(cle) == "20":
        return date(annee, m, 5), date(annee, m, 19)
    ap, mp = (annee - 1, 12) if m == 1 else (annee, m - 1)
    return date(ap, mp, 20), date(annee, m, 4)


def periode_de(jour=None) -> tuple:
    """La période de paie qui contient `jour` (aujourd'hui par défaut) : (debut, fin)."""
    ref = _jour(jour) or _aujourdhui()
    if ref.day <= 4:
        return periode("5", ref.strftime("%Y-%m"))
    if ref.day <= 19:
        return periode("20", ref.strftime("%Y-%m"))
    a, m = (ref.year + 1, 1) if ref.month == 12 else (ref.year, ref.month + 1)
    return periode("5", f"{a:04d}-{m:02d}")


def cle_de_periode(fin) -> str:
    """La clé de la période comme paie_clics.liste_paie la pose : le jour de paie, lendemain de la fin (« 2026-11-05 »)."""
    return (_jour(fin) + timedelta(days=1)).isoformat()


def _date_depuis(texte=None):
    """PRIMES_EQUIPES_DEPUIS lue : « 2026-10-20 » ou, à la française, « 20/10/2026 » (revue L10, R5) ; None si vide ou illisible."""
    s = str(PRIMES_EQUIPES_DEPUIS if texte is None else texte or "").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    return _jour(s) if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", s) else None


def periode_primee(debut) -> bool:
    """Vrai si la période qui commence le `debut` ouvre droit aux primes d'équipe (PRIMES_EQUIPES_DEPUIS ; vide = jamais)."""
    depuis, d0 = _date_depuis(), _jour(debut)
    return depuis is not None and d0 is not None and d0 >= depuis


def _texte_premiere_periode() -> str:
    depuis = _date_depuis()
    if not PRIMES_EQUIPES_DEPUIS.strip():
        return "Primes d'équipe : aucune période primée pour l'instant (PRIMES_EQUIPES_DEPUIS vide)."
    if depuis is None:
        return (f"⚠️ PRIMES_EQUIPES_DEPUIS illisible (« {PRIMES_EQUIPES_DEPUIS} ») : attendu AAAA-MM-JJ, par exemple 2026-10-20. "
                "Aucune prime d'équipe n'est calculée tant qu'elle l'est.")
    d0, f0 = periode_de(depuis)
    if d0 < depuis:                                                     # une date en milieu de période : la suivante
        d0, f0 = periode_de(f0 + timedelta(days=1))
    return (f"Primes d'équipe : à partir de la période du {d0.strftime('%d/%m')} → {f0.strftime('%d/%m')}, "
            f"payée le {(f0 + timedelta(days=1)).strftime('%d/%m')}.")


if PRIMES_EQUIPES_DEPUIS and _date_depuis() is None:                    # dit au chargement (jamais une exception), puis dans
    journal.warning("PRIMES_EQUIPES_DEPUIS illisible (« %s ») : attendu AAAA-MM-JJ, aucune prime calculée",   # `!tl liste` et
                    PRIMES_EQUIPES_DEPUIS)                                                                    # `!tl` (texte ci-dessus)


# ------------------------------------------------------------------ composition des équipes
def _mandat_tl(fiche: dict, fin_iso: str = "") -> str:
    """La créatrice dont la fiche est TL au jour `fin_iso` (aujourd'hui si vide) : le mandat en cours, ou un mandat fini qui
    couvrait ce jour (une liste retapée après un `!tl … aucun` retrouve le TL de la période)."""
    c = str(fiche.get("chef") or "").strip()
    if c and (not fin_iso or str(fiche.get("chef_depuis") or "")[:10] <= fin_iso):
        return c
    if fin_iso:
        for m in fiche.get("chef_passe") or []:
            if isinstance(m, dict) and str(m.get("depuis") or "")[:10] <= fin_iso < str(m.get("jusqu") or "")[:10]:
                return str(m.get("creatrice") or "").strip()
    return ""


def _mandat_manager(fiche: dict, fin_iso: str = "") -> list:
    cs = [str(c).strip() for c in fiche.get("manager_de") or [] if str(c or "").strip()]
    if cs and (not fin_iso or str(fiche.get("manager_depuis") or "")[:10] <= fin_iso):
        return cs
    if fin_iso:
        for m in fiche.get("manager_passe") or []:
            if isinstance(m, dict) and str(m.get("depuis") or "")[:10] <= fin_iso < str(m.get("jusqu") or "")[:10]:
                return [str(c).strip() for c in m.get("creatrices") or [] if str(c or "").strip()]
    return []


def _present(fiche: dict, fin_iso: str) -> bool:
    """Au registre le jour `fin_iso` : signé ce jour-là ou avant (une fiche sans date est ancienne)."""
    return not fin_iso or str(fiche.get("date") or "")[:10] <= fin_iso


def _sortis_a_la_fin(fiches: dict, registre: list, fin_iso: str) -> dict:
    """{uid : entrée de sortis.json} des membres sortis APRÈS `fin_iso` et signés avant : ils étaient au registre ce jour-là. Une
    fiche présente à la fin fait foi ; une fiche neuve d'après la fin (ancien re-onboardé, revue L10 R6) ne masque plus son
    entrée. Plusieurs entrées pour un uid : la première qui couvre la fin."""
    out = {}
    if not fin_iso:
        return out
    for s in registre or []:
        uid = str(s.get("uid") or "") if isinstance(s, dict) else ""
        if not uid or uid in out or (isinstance(fiches.get(uid), dict) and _present(fiches[uid], fin_iso)):
            continue
        if str(s.get("signe_le") or "")[:10] <= fin_iso < str(s.get("date") or "")[:10]:
            out[uid] = s
    return out


def composition(fiches=None, registre=None, fin=None) -> dict:
    """{créatrice : {"tl": uid | None, "vas": [uid…], "manager": uid | None}} telle qu'au jour `fin` (aujourd'hui si None).

    `fiches` : equipes.json (lu si None). `registre` : la trace des sorties (sortis.json, lue si None) : un membre sorti APRÈS
    `fin` était encore au registre ce jour-là, il compte pour sa période, même revenu depuis avec une fiche neuve ; son mandat de TL
    ou de manager est relu dans son entrée (« chef_passe », « manager_passe », recopiés par `fin_de_mandats` à la sortie). Un VA :
    fiche['creatrice'], au clic, TL d'aucune équipe, pas exclu, pas admin, signé au plus tard le jour `fin`."""
    fiches = _fiches() if fiches is None else (fiches or {})
    registre = _sortis() if registre is None else (registre or [])
    fin_d = _jour(fin)
    fin_iso = fin_d.isoformat() if fin_d else ""
    connues = creatrices_connues(fiches)
    equipes = {}
    sortis = _sortis_a_la_fin(fiches, registre, fin_iso)

    def equipe(c):
        k = _n(c)
        connues.setdefault(k, _affiche(c))
        return equipes.setdefault(k, {"tl": None, "vas": [], "manager": None})

    def presents():
        """(uid, fiche ou entrée de sortie) de tous ceux qui étaient au registre à la fin : les fiches d'abord."""
        for uid, f in fiches.items():
            if isinstance(f, dict) and _present(f, fin_iso):
                yield str(uid), f
        yield from sortis.items()

    tls = {}
    candidats = []
    for uid, f in presents():
        c = _mandat_tl(f, fin_iso)
        if c:
            candidats.append((str(f.get("chef_depuis") or ""), uid, c))
    for _, uid, c in sorted(candidats):                                 # deux TL sur une créatrice (fiche retouchée) : le plus ancien
        tls[uid] = _n(c)
        e = equipe(c)
        if e["tl"] is None:
            e["tl"] = uid
        else:
            journal.warning("Deux TL pour %s : %s gardé, %s ignoré", c, e["tl"], uid)
    admins = _admins()
    for uid, f in presents():
        if uid in tls or uid in admins:
            continue
        c = str(f.get("creatrice") or "").strip()
        if not c or _exclu(uid, f) or _regime(uid) != "clic":         # une entrée de sortie porte « nom » : lu par nom_de
            continue
        equipe(c)["vas"].append(uid)
    for uid, f in presents():
        for c in _mandat_manager(f, fin_iso):
            e = equipe(c)
            if e["manager"] is None:
                e["manager"] = uid
    return {connues[k]: equipes[k] for k in sorted(equipes, key=lambda k: connues[k])}


# ------------------------------------------------------------------ mesures (repli quand la paie n'est pas branchée)
def _liens_de(d: dict, uid: str) -> list:
    return [lid for lid, i in ((d or {}).get("liens") or {}).items() if str((i or {}).get("uid") or "") == str(uid)]


def _jours_valides(d: dict, lid: str, debut: date, fin: date):
    """(jour, relevé) des jours de [debut, fin] lus pour le lien, à partir de sa reprise (`depuis`)."""
    dep = _jour(((d or {}).get("liens", {}).get(lid) or {}).get("depuis"))
    a = max(debut, dep) if dep else debut
    for j, v in (((d or {}).get("jours") or {}).get(lid) or {}).items():
        if a.isoformat() <= str(j) <= fin.isoformat() and isinstance(v, dict) and not v.get("erreur") and v.get("payes") is not None:
            yield str(j), v


def _payees_local(d: dict, uid: str, debut, fin) -> int:
    """Repli seulement : les visites payées des liens du clipper sur la période. La mesure qui fait foi est paie_clics.payees
    (lot L11, injectée) : la ligne du VA sur la liste de paie, plancher du passage au clic et visites dues comprises."""
    debut, fin = _jour(debut), _jour(fin)
    return sum(_entier(v.get("payes")) for lid in _liens_de(d, uid) for _, v in _jours_valides(d, lid, debut, fin))


def _jours_manquants_local(d: dict, uid: str, debut, fin) -> int:
    """Jours de la période (jusqu'à hier) où au moins un lien du clipper n'a pas de relevé lisible (jamais un faux 0)."""
    debut, fin = _jour(debut), _jour(fin)
    borne = min(fin, _aujourdhui() - timedelta(days=1))
    manquants = set()
    for lid in _liens_de(d, uid):
        dep = _jour(((d or {}).get("liens", {}).get(lid) or {}).get("depuis"))
        lus = {j for j, _ in _jours_valides(d, lid, debut, borne)}
        j = max(debut, dep) if dep else debut
        while j <= borne:
            if j.isoformat() not in lus:
                manquants.add(j)
            j += timedelta(days=1)
    return len(manquants)


def _parts(d: dict, uid: str, debut: date, fin: date) -> dict:
    tot = {"brut": 0, "hors_robots": 0, "payes": 0}
    for lid in _liens_de(d, uid):
        for _, v in _jours_valides(d, lid, debut, fin):
            for k in tot:
                tot[k] += _entier(v.get(k))
    return tot


def _norme(d: dict, debut: date, fin: date):
    """Part de robots et part non francophone de tous les liens de clippers sur la période ; None si trop peu de volume."""
    tot = {"brut": 0, "hors_robots": 0, "payes": 0}
    for uid in {str((i or {}).get("uid") or "") for i in ((d or {}).get("liens") or {}).values()} - {""}:
        for k, v in _parts(d, uid, debut, fin).items():
            tot[k] += v
    if tot["brut"] < 10 * PRIME_VOLUME_MIN or not tot["hors_robots"]:
        return None
    return {"robots": 1 - tot["hors_robots"] / tot["brut"], "non_fr": 1 - tot["payes"] / tot["hors_robots"]}


def _anomalie(parts: dict, norme) -> str:
    """« robots 60 % (norme 20 %) » ou « francophones 98 % (norme 55 %) » quand la part s'écarte de la norme de la période de
    plus de PRIME_ECART_NORME ; '' sinon (ou trop peu de volume pour juger)."""
    if not norme or parts["brut"] < PRIME_VOLUME_MIN or not parts["hors_robots"]:
        return ""
    robots, non_fr = 1 - parts["hors_robots"] / parts["brut"], 1 - parts["payes"] / parts["hors_robots"]
    if robots > norme["robots"] + PRIME_ECART_NORME:
        return f"robots {robots:.0%} (norme {norme['robots']:.0%})".replace("%", " %")
    if abs(non_fr - norme["non_fr"]) > PRIME_ECART_NORME:
        return f"francophones {1 - non_fr:.0%} (norme {1 - norme['non_fr']:.0%})".replace("%", " %")
    return ""


def _appel(f, *args, defaut=None):
    try:
        return f(*args)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("%s en erreur (%s)", getattr(f, "__name__", "mesure"), erreur)
        return defaut


# ------------------------------------------------------------------ calcul des primes
def calculer(d: dict, debut, fin, payees=None, reels_vus=None, jours_manquants=None, fiches=None, registre=None) -> dict:
    """Les équipes de la période et leurs chiffres, sans rien écrire. `payees(d, uid, debut, fin)` -> visites payées (la ligne
    de paie) ; `reels_vus(uid, debut, fin)` -> Reels vus sur la période, bornes comprises (None : non mesurable) ;
    `jours_manquants(d, uid, debut, fin)` -> jours non relevés. Une mesure absente : repli local (payees, jours) ou « non
    mesuré » (Reels, donc « à vérifier »)."""
    debut, fin = _jour(debut), _jour(fin)
    mesure = payees or _payees_local
    manque = jours_manquants or _jours_manquants_local
    norme = _norme(d, debut, fin)
    n_jours = max(1, (min(fin, max(debut, _aujourdhui() - timedelta(days=1))) - debut).days + 1)
    primee = periode_primee(debut)
    out = {"debut": debut.isoformat(), "fin": fin.isoformat(), "equipes": {}, "norme": norme,
           "reels_branches": reels_vus is not None, "primee": primee}
    for c, e in composition(fiches, registre, fin).items():
        vas = []
        for uid in e["vas"]:
            p = _entier(_appel(mesure, d, uid, debut, fin, defaut=0))
            j = _entier(_appel(manque, d, uid, debut, fin, defaut=0))
            r = _appel(reels_vus, uid, debut, fin) if (reels_vus and p >= PRIME_VOLUME_MIN) else None
            # Revue L10 (R2) : le manager de l'équipe qui y clippe reste VA (le TL est primé sur lui), hors du total qui le paie
            hors_total = uid == e["manager"] and not MANAGER_COMPTE
            vas.append({"uid": uid, "nom": nom_de(uid), "payees": p, "manquants": j,
                        "projete": p + (p * j / max(1, n_jours - j) if j else 0),
                        "reels": None if r is None else _entier(r), "juge": p >= PRIME_VOLUME_MIN,
                        "anomalie": _anomalie(_parts(d, uid, debut, fin), norme), "prime": p >= TL_SEUIL_VA,
                        "hors_total": hors_total})
        vas.sort(key=lambda v: (-v["payees"], v["nom"]))
        tl_p, tl_j = None, 0
        if e["tl"]:
            tl_p = _entier(_appel(mesure, d, e["tl"], debut, fin, defaut=0))
            tl_j = _entier(_appel(manque, d, e["tl"], debut, fin, defaut=0)) if EQUIPE_COMPTE_TL else 0
        part_tl = (tl_p or 0) if EQUIPE_COMPTE_TL else 0                # EQUIPE_COMPTE_TL=0 : le TL hors du total
        comptes = [v for v in vas if not v["hors_total"]]
        total = sum(v["payees"] for v in comptes) + part_tl
        projete = sum(v["projete"] for v in comptes) + part_tl + (part_tl * tl_j / max(1, n_jours - tl_j) if tl_j else 0)
        out["equipes"][c] = {"tl": e["tl"], "tl_nom": nom_de(e["tl"]) if e["tl"] else "", "tl_payees": tl_p,
                             "tl_manquants": tl_j, "manager": e["manager"],
                             "manager_nom": nom_de(e["manager"]) if e["manager"] else "",
                             "vas": vas, "total": total, "projete": projete,
                             "va_primes": sum(1 for v in vas if v["prime"]), "primee": primee}
    return out


def _raisons(e: dict, juges: list, reels_branches: bool, pour_manager: bool = False) -> list:
    """Pourquoi une prime est « à vérifier » : jours non relevés dans l'équipe, preuve de publication ou part de visites hors norme
    chez les VA `juges`. `pour_manager` : le manager lui-même, hors du total qui le paie, n'est pas compté."""
    r = []
    manq = [v for v in e["vas"] if v["manquants"] and not (pour_manager and v.get("hors_total"))] + (
        [{"nom": e["tl_nom"] + " (TL)", "manquants": e["tl_manquants"]}] if EQUIPE_COMPTE_TL and e.get("tl_manquants") else [])
    if manq:
        r.append("jours non relevés : " + ", ".join(f"{v['nom']} ({v['manquants']} j)" for v in manq))
    for v in juges:
        if not reels_branches:
            r.append(f"Reels de {v['nom']} non mesurés (preuve non branchée)")
        elif v["reels"] is None:
            r.append(f"Reels de {v['nom']} non mesurés")
        elif v["reels"] < PRIME_PREUVE_REELS:
            r.append(f"{v['nom']} : {v['reels']} Reels vus (moins de {PRIME_PREUVE_REELS})")
        if v["anomalie"]:
            r.append(f"{v['nom']} : {v['anomalie']}")
    return r


CONTROLE_ABONNES_TL = "contrôle abonnés (Infloww / MyPulse) : 5 par VA primé"


def _controle_abonnes_manager() -> str:
    return f"contrôle abonnés (Infloww / MyPulse) : 5 par VA de l'équipe à {_fmt(PRIME_VOLUME_MIN)} visites ou plus"


def lignes_primes(calcul: dict) -> list:
    """[(uid, montant, détail, à_vérifier)] : une entrée par bénéficiaire (TL et manager fusionnés), montant décroissant.

    Amendement E (revue L10, R9) : TOUTE ligne avec un montant est « à vérifier » (à_vérifier vrai), car Gaëtan contrôle à la main
    5 abonnés par VA primé avant le virement. Le détail sépare le contrôle de routine (« contrôle abonnés … ») d'une anomalie
    (« ⚠️ à vérifier : … », jour non relevé, preuve, part hors norme). Montant 0 = une note « à vérifier » seulement (un VA ou une
    équipe que des jours non relevés pourraient faire passer le seuil) : rien à virer."""
    par_uid = {}

    def ajouter(uid, montant, detail, verif):
        x = par_uid.setdefault(uid, [0.0, [], False])
        x[0] += montant
        x[1].append(detail)
        x[2] = x[2] or verif or montant > 0

    reels_branches = calcul.get("reels_branches", True)
    for c, e in calcul["equipes"].items():
        if e["tl"]:
            primes = [v for v in e["vas"] if v["prime"]]
            raisons = _raisons(e, primes, reels_branches)
            montant = TL_PRIME_VA_USD * len(primes)
            if primes:
                detail = (f"+ {_usd(montant)} équipe {c} ({len(primes)} VA à {_fmt(TL_SEUIL_VA)} ou plus : "
                          + ", ".join(f"{v['nom']} {_fmt(v['payees'])}" for v in primes)
                          + ") · " + CONTROLE_ABONNES_TL)
            else:
                portee = [v for v in e["vas"] if v["manquants"] and v["projete"] >= TL_SEUIL_VA]
                detail = (f"0 $ équipe {c} pour l'instant : " + ", ".join(
                    f"{v['nom']} {_fmt(v['payees'])} / {_fmt(TL_SEUIL_VA)} avec {v['manquants']} j non relevé(s)" for v in portee)
                    if portee else "")
            if detail:
                if raisons:
                    detail += " · ⚠️ à vérifier : " + " ; ".join(raisons)
                ajouter(e["tl"], montant, detail, bool(raisons) or not montant)
        m = e["manager"]
        if not m:
            continue
        if not e["tl"] or e["tl"] == m:
            if e["total"] >= MANAGER_SEUIL_EQUIPE:                     # dit, pour qu'aucun 0 ne soit une surprise
                pourquoi = "pas de TL" if not e["tl"] else "il en est le TL"
                ajouter(m, 0.0, f"0 $ manager {c} ({_fmt(e['total'])} ; {pourquoi} : pas de prime manager)", False)
            continue
        juges = [v for v in e["vas"] if v["juge"] and not v.get("hors_total")]
        raisons = _raisons(e, juges, reels_branches, pour_manager=True)
        if e["total"] >= MANAGER_SEUIL_EQUIPE:
            lui = any(v.get("hors_total") for v in e["vas"])
            detail = (f"+ {_usd(MANAGER_PRIME_USD)} manager (équipe {c} à {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)}, "
                      f"TL {'compris' if EQUIPE_COMPTE_TL else 'non compris'}" + (", ses visites non comprises" if lui else "")
                      + ") · " + _controle_abonnes_manager())
            montant = MANAGER_PRIME_USD
        elif raisons and e["projete"] >= MANAGER_SEUIL_EQUIPE:
            detail = f"0 $ manager {c} pour l'instant : {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)} avec des jours non relevés"
            montant = 0.0
        else:
            continue
        if raisons:
            detail += " · ⚠️ à vérifier : " + " ; ".join(raisons)
        ajouter(m, montant, detail, bool(raisons) or not montant)
    out = [(uid, round(x[0], 2), " · ".join(x[1]), x[2]) for uid, x in par_uid.items()]
    return sorted(out, key=lambda t: (-t[1], t[0]))


def primes_equipes(d: dict, debut, fin, cle_periode: str = "", payees=None, reels_vus=None, jours_manquants=None) -> list:
    """Contrat du lot L11 (dépendance `primes_equipes` de paie_clics.liste_paie) : [(uid, montant, détail, à_vérifier)].

    Une période figée (clics.json['primes_equipes'][cle_periode] avec « lignes », écrit par paie_clics.figer_primes_equipes avec
    `a_figer`) est relue telle quelle : une liste retapée donne le même montant. Rien avant PRIMES_EQUIPES_DEPUIS."""
    fige = (((d or {}).get("primes_equipes") or {}).get(str(cle_periode or "")) or {}) if cle_periode else {}
    if isinstance(fige, dict) and isinstance(fige.get("lignes"), list):
        return [(str(l[0]), float(l[1]), str(l[2]), bool(l[3])) for l in fige["lignes"] if isinstance(l, (list, tuple)) and len(l) >= 4]
    if not periode_primee(debut):
        return []
    return lignes_primes(calculer(d, debut, fin, payees, reels_vus, jours_manquants))


def a_figer(d: dict, debut, fin, cle_periode: str = "", payees=None, reels_vus=None, jours_manquants=None) -> dict:
    """Ce que paie_clics.figer_primes_equipes (lot L11) écrit dans clics.json['primes_equipes'][cle_periode] au premier calcul
    après la clôture : la composition, les chiffres et les lignes (vides avant PRIMES_EQUIPES_DEPUIS). Aucun prénom n'y est
    une clé : tout est indexé par uid."""
    calcul = calculer(d, debut, fin, payees, reels_vus, jours_manquants)
    lignes = lignes_primes(calcul) if periode_primee(debut) else []
    return {"calcule_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "debut": calcul["debut"], "fin": calcul["fin"],
            "cle": str(cle_periode or cle_de_periode(fin)),
            "composition": {c: {"tl": e["tl"], "manager": e["manager"], "vas": {v["uid"]: v["payees"] for v in e["vas"]},
                                "total": e["total"]} for c, e in calcul["equipes"].items()},
            "lignes": [list(l) for l in lignes]}


def resume_equipe(c: str, e: dict, primee=None) -> str:
    """Une ligne par équipe (`!tl liste`, section ÉQUIPES du Dashboard) : « Chloé · TL Ana · VA à 500 ou plus 2/6 · équipe
    2 340 / 3 000 · primes 20 $ · 1 jour non relevé ». Période non primée (avant PRIMES_EQUIPES_DEPUIS, revue L10 R1) : « pas de
    prime sur cette période » à la place du montant, jamais une somme qui ne sera pas payée. `primee` : sinon lu dans `e` (posé
    par `calculer`) ; absent des deux, la période est tenue pour non primée."""
    primee = bool(e.get("primee", False) if primee is None else primee)
    prime_tl = TL_PRIME_VA_USD * e["va_primes"] if e["tl"] else 0
    prime_m = MANAGER_PRIME_USD if (e["manager"] and e["tl"] and e["manager"] != e["tl"]
                                    and e["total"] >= MANAGER_SEUIL_EQUIPE) else 0
    manq = sum(v["manquants"] for v in e["vas"])
    return (f"{c} · TL {e['tl_nom'] or 'aucun'} · VA à {_fmt(TL_SEUIL_VA)} ou plus {e['va_primes']}/{len(e['vas'])} · "
            f"équipe {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)} · "
            + (f"primes {_usd(prime_tl + prime_m)}" if primee else "pas de prime sur cette période")
            + (f" · {manq} jour(s) non relevé(s)" if manq else ""))


# ------------------------------------------------------------------ rôle « Team Leader »
def _role_tl(guild):
    return next((r for r in getattr(guild, "roles", None) or [] if _n(getattr(r, "name", "")) == _n(ROLE_TL_NOM)), None)


def _permissions(role) -> int:
    return _entier(getattr(getattr(role, "permissions", None), "value", 0))


async def assurer_role_tl(guild):
    """Le rôle « Team Leader » : créé s'il manque, SANS AUCUNE permission (une étiquette) ; s'il existe avec des permissions,
    le bot les retire. None si le serveur est absent ou si le bot n'a pas le droit de créer le rôle. Le rôle rendu peut encore
    porter des permissions si Discord a refusé de les retirer : `_poser_role` ne le pose alors pas (revue L10, R3)."""
    if guild is None:
        return None
    role = _role_tl(guild)
    try:
        if role is None:
            role = await guild.create_role(name=ROLE_TL_NOM, permissions=discord.Permissions.none(), hoist=False,
                                           mentionable=False, reason="Rôle Team Leader : une étiquette, sans permission (10/10)")
        elif _permissions(role):
            vide = await role.edit(permissions=discord.Permissions.none(), reason="Un Team Leader n'a aucune permission (10/10)")
            if vide is not None:                                        # discord.py rend le rôle modifié, l'ancien objet ne bouge pas
                role = vide
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Rôle %s : %s", ROLE_TL_NOM, erreur)
    return role


async def _poser_role(membre, guild, poser: bool, raison: str) -> str:
    """Pose ou retire le rôle Team Leader ; '' si fait, sinon la ligne d'avertissement. Jamais posé s'il porte encore une
    permission (amendement E : un TL n'a aucune commande staff) ; sans serveur (commande en MP, membre introuvable), dit."""
    if membre is None:
        return ""
    if guild is None or not hasattr(membre, "add_roles"):              # un discord.User (MP) n'a ni serveur ni rôles
        nom = getattr(membre, "display_name", "")
        return (f"⚠️ Rôle {ROLE_TL_NOM} non posé (commande en MP) : refais la commande dans le serveur." if poser else
                f"⚠️ Rôle {ROLE_TL_NOM} non retiré à {nom} (commande en MP) : retire-le-lui à la main.")
    role = await assurer_role_tl(guild) if poser else _role_tl(guild)
    if role is None:
        return f"⚠️ Rôle {ROLE_TL_NOM} introuvable et non créé (droit « Gérer les rôles » du bot)." if poser else ""
    if poser and _permissions(role):
        return (f"⚠️ Rôle {ROLE_TL_NOM} encore porteur de permissions, non posé : vide-le à la main (Réglages du serveur → "
                f"Rôles → {ROLE_TL_NOM} → Permissions → tout décocher), puis refais la commande.")
    try:
        if poser and role not in (getattr(membre, "roles", None) or []):
            await membre.add_roles(role, reason=raison)
        elif not poser and role in (getattr(membre, "roles", None) or []):
            await membre.remove_roles(role, reason=raison)
    except Exception as erreur:                                         # noqa: BLE001
        return f"⚠️ Rôle {ROLE_TL_NOM} non {'posé' if poser else 'retiré'} ({type(erreur).__name__}) : à faire à la main."
    return ""


# ------------------------------------------------------------------ nominations (admins seulement)
def _fin_mandat(fiche: dict, cle: str, jour: str):
    """Range le mandat en cours (chef ou manager) dans son historique, fini le `jour` (exclu)."""
    if cle == "chef" and fiche.get("chef"):
        fiche.setdefault("chef_passe", []).append({"creatrice": fiche["chef"], "depuis": str(fiche.get("chef_depuis") or "")[:10],
                                                   "jusqu": jour})
    if cle == "manager" and fiche.get("manager_de"):
        fiche.setdefault("manager_passe", []).append({"creatrices": list(fiche["manager_de"]),
                                                      "depuis": str(fiche.get("manager_depuis") or "")[:10], "jusqu": jour})
    for k in ((("chef", "chef_depuis", "chef_par") if cle == "chef" else ("manager_de", "manager_depuis", "manager_par"))):
        fiche.pop(k, None)


def mandats_a_garder(fiche: dict, jour) -> dict:
    """Les mandats d'une fiche qui sort, fermés le `jour` (exclu) : {"chef_passe": […], "manager_passe": […]}, à recopier dans
    son entrée de sortis.json. `composition` les y relit : un TL sorti après la fin d'une période reste le TL de cette période
    (revue L10, R6), au lieu de devenir le VA de sa propre créatrice. La fiche donnée n'est pas modifiée."""
    f = {k: (list(v) if isinstance(v, list) else v) for k, v in (fiche or {}).items()
         if k in ("chef", "chef_depuis", "chef_passe", "manager_de", "manager_depuis", "manager_passe")}
    jour = (_jour(jour) or _aujourdhui()).isoformat()
    _fin_mandat(f, "chef", jour)
    _fin_mandat(f, "manager", jour)
    return {k: f[k] for k in ("chef_passe", "manager_passe") if f.get(k)}


async def fin_de_mandats(uid, guild=None, fiche=None, jour=None) -> dict:
    """À appeler par `!sortie` (sortir_membre), le départ du serveur (on_member_remove) et le passage hors clipping AVANT
    d'effacer la fiche d'equipes.json (lot ultérieur, revue L10 R6 et R11) : retire le rôle Team Leader et rend les mandats
    fermés à recopier dans l'entrée de sortis.json (`sortis.append({…, **await equipes_tl.fin_de_mandats(uid, g, fiche)})`).
    Ne lève jamais : une erreur Discord est journalisée."""
    uid = str(uid)
    fiche = fiche if fiche is not None else (_fiches().get(uid) or {})
    garde = mandats_a_garder(fiche, jour)
    try:
        m = _membre(uid)
        if m is not None:
            avert = await _poser_role(m, guild if guild is not None else getattr(m, "guild", None), False, "Sortie de l'équipe")
            if avert:
                journal.warning("Sortie de %s : %s", uid, avert)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Sortie de %s : rôle %s non retiré (%s)", uid, ROLE_TL_NOM, erreur)
    return garde


def _resoudre(membre):
    """Le membre du SERVEUR derrière une mention (revue L10, R8) : en MP, discord.py met un discord.User dans message.mentions,
    sans rôles ni serveur ; le refus « rôle Manager » et la pose du rôle Team Leader ont besoin du membre."""
    if membre is None:
        return None
    return _membre(getattr(membre, "id", "")) or membre


def _refus_personne(membre, fiches: dict, role: str) -> str:
    if membre is None:
        return "❌ Mentionne la personne : `!tl Chloé @X`." if role == "tl" else "❌ Mentionne la personne : `!manager @X Chloé Sarah`."
    if getattr(membre, "bot", False):
        return "❌ Un bot ne peut pas être nommé."
    if est_admin(membre):
        return "❌ Un admin n'est ni TL ni manager : d'ici là, le manager, c'est toi, et ça coûte 0 $."
    if str(membre.id) not in fiches:
        return (f"❌ {getattr(membre, 'display_name', 'Cette personne')} n'est pas au registre des signés : "
                "un TL ou un manager doit être un clipper signé.")
    return ""


async def nommer_tl(membre, creatrice: str, par: str = "", guild=None) -> list:
    """`!tl Chloé @X` : X devient TL de Chloé (le TL précédent de Chloé et l'ancienne équipe de X sont rangés dans l'historique).
    Refusé si X porte le rôle Manager : un TL n'a jamais de commande staff. Déjà TL de cette créatrice : rien ne change, mais le
    rôle est reposé s'il manque (après une commande en MP ou un rôle vidé à la main). Renvoie les lignes de la réponse."""
    membre = _resoudre(membre)
    fiches = _fiches()
    refus = _refus_personne(membre, fiches, "tl")
    if refus:
        return [refus]
    if _a_role_manager(membre):
        return [f"❌ {membre.display_name} a le rôle Manager : c'est un rôle staff (tous les codes, `!wallet`, `!lien forcer`). "
                "Un TL ne l'a jamais. Retire-lui ce rôle, puis refais `!tl`."]
    connues = creatrices_connues(fiches)
    canon = connues.get(_n(creatrice))
    if not canon:
        return [f"❌ Créatrice inconnue : « {creatrice} ». Connues : {', '.join(sorted(connues.values())) or 'aucune'}."]
    uid, jour = str(membre.id), _aujourdhui().isoformat()
    fiche = fiches[uid]
    guild = guild if guild is not None else getattr(membre, "guild", None)
    if _n(fiche.get("chef")) == _n(canon):
        depuis = _jour(fiche.get("chef_depuis"))
        lignes = [f"ℹ️ {membre.display_name} est déjà TL de {canon} depuis le {depuis.strftime('%d/%m') if depuis else '?'}."]
        manquait = guild is not None and _role_tl(guild) not in (getattr(membre, "roles", None) or [])
        avert = await _poser_role(membre, guild, True, f"TL de {canon}")
        if avert:
            lignes.append(avert)
        elif manquait:
            lignes.append(f"Rôle {ROLE_TL_NOM} reposé.")
        return lignes
    lignes, anciens = [], []
    if fiche.get("chef"):
        lignes.append(f"{membre.display_name} quitte l'équipe de {fiche['chef']} (un TL n'a qu'une équipe).")
        _fin_mandat(fiche, "chef", jour)
    for autre, f in fiches.items():
        if autre != uid and isinstance(f, dict) and _n(f.get("chef")) == _n(canon):
            lignes.append(f"{nom_de(autre, f)} n'est plus TL de {canon}.")
            _fin_mandat(f, "chef", jour)
            anciens.append(autre)
    fiche.update({"chef": canon, "chef_depuis": jour, "chef_par": str(par or "")})
    _ecrire_fiches(fiches)                                              # lu et écrit sans attente : rien ne s'intercale
    for autre in anciens:
        avert = await _poser_role(_membre(autre), guild, False, f"Plus TL de {canon}")
        if avert:
            lignes.append(avert)
    avert = await _poser_role(membre, guild, True, f"TL de {canon}")
    entete = (f"✅ {membre.display_name} est TL de {canon} depuis le {_jour(jour).strftime('%d/%m')}.\n\n"
              f"Ses visites restent payées comme celles d'un clipper. Il ne compte ni dans les {_fmt(TL_SEUIL_VA)} ni dans les "
              f"{_fmt(MANAGER_SEUIL_EQUIPE)} de son équipe" + (" (EQUIPE_COMPTE_TL=1 : il compte dans le total)" if EQUIPE_COMPTE_TL else "")
              + f". Prime : {_usd(TL_PRIME_VA_USD)} par VA à {_fmt(TL_SEUIL_VA)} visites payées ou plus.\n\n"
              f"Rôle {ROLE_TL_NOM} : aucune commande staff. Ne lui donne jamais le rôle Manager.")
    if _regime(uid) == "fixe":
        lignes.append(f"{membre.display_name} est au fixe : sa prime d'équipe passe sur une ligne à part. "
                      f"`!paie @{membre.display_name} clic` le jour où son fixe s'arrête.")
    if not periode_primee(periode_de()[0]):
        lignes.append(_texte_premiere_periode())
    if avert:
        lignes.append(avert)
    return [entete] + lignes


async def retirer_tl(creatrice: str, par: str = "", guild=None) -> list:
    """`!tl Chloé aucun` : Chloé n'a plus de TL (le mandat reste dans l'historique de la fiche, pour les périodes passées)."""
    if not _n(creatrice):
        return ["Usage : `!tl Chloé aucun`."]
    fiches = _fiches()
    canon = creatrices_connues(fiches).get(_n(creatrice)) or _affiche(creatrice)
    jour = _aujourdhui().isoformat()
    partis = [uid for uid, f in fiches.items() if isinstance(f, dict) and f.get("chef") and _n(f.get("chef")) == _n(canon)]
    if not partis:
        return [f"ℹ️ {canon} n'a pas de TL."]
    for uid in partis:
        _fin_mandat(fiches[uid], "chef", jour)
    _ecrire_fiches(fiches)
    lignes = [f"✅ {', '.join(nom_de(u, fiches[u]) for u in partis)} n'est plus TL de {canon} (depuis le "
              f"{_jour(jour).strftime('%d/%m')}). La période en cours n'a plus de prime TL pour {canon}."]
    for uid in partis:
        m = _membre(uid)
        avert = await _poser_role(m, guild if guild is not None else getattr(m, "guild", None), False, f"Plus TL de {canon}")
        if avert:
            lignes.append(avert)
    return lignes


async def nommer_manager(membre, creatrices: list, par: str = "") -> list:
    """`!manager @X Chloé Sarah` : X a la charge de CES équipes, et de celles-là seulement (la liste REMPLACE la précédente : une
    équipe qu'il avait et qui n'y est plus est dite, revue L10 R7) ; 75 $ par équipe à 3 000 ou plus, sauf celle dont il est TL.
    `!manager @X aucun` : plus aucune. Une équipe n'a qu'un manager : elle quitte l'ancien. Aucun rôle Discord n'est donné."""
    membre = _resoudre(membre)
    fiches = _fiches()
    refus = _refus_personne(membre, fiches, "manager")
    if refus:
        return [refus]
    uid, jour = str(membre.id), _aujourdhui().isoformat()
    fiche = fiches[uid]
    if [_n(c) for c in creatrices] in ([], ["aucun"], ["aucune"]):
        if not fiche.get("manager_de"):
            return [f"ℹ️ {membre.display_name} n'est manager d'aucune équipe."]
        _fin_mandat(fiche, "manager", jour)
        _ecrire_fiches(fiches)
        return [f"✅ {membre.display_name} n'est plus manager (depuis le {_jour(jour).strftime('%d/%m')})."]
    connues = creatrices_connues(fiches)
    inconnues = [c for c in creatrices if _n(c) not in connues]
    if inconnues:
        return [f"❌ Créatrice(s) inconnue(s) : {', '.join(inconnues)}. Connues : {', '.join(sorted(connues.values())) or 'aucune'}."]
    canons = list(dict.fromkeys(connues[_n(c)] for c in creatrices))
    if sorted(_n(c) for c in fiche.get("manager_de") or []) == sorted(_n(c) for c in canons):
        return [f"ℹ️ {membre.display_name} est déjà manager de {', '.join(canons)}."]
    perdues = [c for c in fiche.get("manager_de") or [] if _n(c) not in {_n(x) for x in canons}]
    lignes = []
    if perdues:
        lignes.append(f"{membre.display_name} n'est plus manager de {', '.join(perdues)} : la liste remplace l'ancienne. Pour les "
                      f"garder, tape `!manager @{membre.display_name} {' '.join(list(canons) + perdues)}`.")
    for autre, f in fiches.items():
        if autre == uid or not isinstance(f, dict) or not f.get("manager_de"):
            continue
        prises = [c for c in f["manager_de"] if _n(c) in {_n(x) for x in canons}]
        if prises:
            reste = [c for c in f["manager_de"] if _n(c) not in {_n(x) for x in canons}]
            _fin_mandat(f, "manager", jour)
            if reste:
                f.update({"manager_de": reste, "manager_depuis": jour, "manager_par": str(par or "")})
            lignes.append(f"{nom_de(autre, f)} n'est plus manager de {', '.join(prises)}.")
    if fiche.get("manager_de"):
        _fin_mandat(fiche, "manager", jour)
    fiche.update({"manager_de": canons, "manager_depuis": jour, "manager_par": str(par or "")})
    _ecrire_fiches(fiches)
    entete = (f"✅ {membre.display_name} est manager de {', '.join(canons)} depuis le {_jour(jour).strftime('%d/%m')}.\n\n"
              f"Prime : {_usd(MANAGER_PRIME_USD)} par équipe avec un TL à {_fmt(MANAGER_SEUIL_EQUIPE)} visites payées ou plus "
              f"(TL {'compris' if EQUIPE_COMPTE_TL else 'non compris'}). Aucun rôle Discord n'est donné.")
    tl_de = _n(fiche.get("chef"))
    if tl_de and tl_de in {_n(c) for c in canons}:
        lignes.append(f"{membre.display_name} est TL de {fiche['chef']} : il ne touchera pas les {_usd(MANAGER_PRIME_USD)} de cette équipe.")
    sa_c = _n(fiche.get("creatrice"))
    if not tl_de and sa_c and sa_c in {_n(c) for c in canons}:
        c_aff = next(c for c in canons if _n(c) == sa_c)
        lignes.append(f"{membre.display_name} clippe sur {c_aff} : ses visites "
                      + (f"comptent dans les {_fmt(MANAGER_SEUIL_EQUIPE)} de {c_aff} (MANAGER_COMPTE=1)." if MANAGER_COMPTE else
                         f"ne comptent pas dans les {_fmt(MANAGER_SEUIL_EQUIPE)} de {c_aff}, pour qu'il ne soit pas primé sur sa "
                         f"propre production. Elles restent payées au clic."))
    if _a_role_manager(membre):
        lignes.append(f"⚠️ {membre.display_name} a le rôle Manager (staff : `!lien forcer`, `!wallet`, tous les codes). Payé sur le "
                      "total de ses équipes, il pourrait y déplacer des liens : retire-lui ce rôle.")
    if not periode_primee(periode_de()[0]):
        lignes.append(_texte_premiere_periode())
    return [entete] + lignes


# ------------------------------------------------------------------ `!tl liste`
def texte_liste(calcul: dict, en_cours: bool) -> list:
    """Les paragraphes de `!tl liste` : l'arbre des équipes et les chiffres de la période."""
    debut, fin = _jour(calcul["debut"]), _jour(calcul["fin"])
    primee = periode_primee(debut)
    blocs = [f"👥 **Équipes** · période {debut.strftime('%d/%m')} → {fin.strftime('%d/%m')} (paie du "
             f"{(fin + timedelta(days=1)).strftime('%d/%m')})" + (" · en cours" if en_cours else " · close"),
             f"{_fmt(TL_SEUIL_VA)} = {_fmt(TL_SEUIL_VA)} visites payées (pays francophones, hors robots) sur la période. "
             f"TL : {_usd(TL_PRIME_VA_USD)} par VA à {_fmt(TL_SEUIL_VA)} ou plus. Manager : {_usd(MANAGER_PRIME_USD)} par équipe "
             f"à {_fmt(MANAGER_SEUIL_EQUIPE)} ou plus. TL {'compris dans' if EQUIPE_COMPTE_TL else 'hors de'} son équipe."]
    if not primee:
        blocs.append("Pas de prime d'équipe sur cette période. " + _texte_premiere_periode())
    if not calcul["equipes"]:
        blocs.append("Aucune équipe : personne n'a de créatrice au registre.")
    sans_prime = " (pas de prime sur cette période)"                    # revue L10 (R1) : jamais un montant qui ne sera pas payé
    for c, e in calcul["equipes"].items():
        tete = f"**{c}** · TL : {e['tl_nom'] or 'aucun (`!tl ' + c + ' @X`)'} · manager : {e['manager_nom'] or 'aucun'}"
        b = [tete]
        if e["tl"]:
            b.append(f"{e['va_primes']}/{len(e['vas'])} VA à {_fmt(TL_SEUIL_VA)} ou plus"
                     + (f" → {_usd(TL_PRIME_VA_USD * e['va_primes'])} au TL" if primee else sans_prime)
                     + (f" ; ses visites : {_fmt(e['tl_payees'] or 0)}" if e["tl_payees"] is not None else ""))
        else:
            b.append(f"{len(e['vas'])} VA, pas de TL : pas de prime TL")
        if e["manager"] and e["tl"] and e["manager"] != e["tl"]:
            gagne = e["total"] >= MANAGER_SEUIL_EQUIPE
            b.append(f"Équipe : {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)}"
                     + (f" → {_usd(MANAGER_PRIME_USD if gagne else 0)} au manager" if primee else sans_prime))
        else:
            b.append(f"Équipe : {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)}"
                     + (" (le manager en est le TL : pas de prime manager)" if e["manager"] and e["manager"] == e["tl"] else ""))
        if e["vas"]:
            b.append("VA : " + " · ".join(f"{v['nom']} {_fmt(v['payees'])}" + (" ✓" if v["prime"] else "")
                                          + (f" (manager : hors des {_fmt(MANAGER_SEUIL_EQUIPE)})" if v.get("hors_total") else "")
                                          for v in e["vas"]))
        manq = [v for v in e["vas"] if v["manquants"]]
        if manq:
            b.append("⚠️ Jours non relevés : " + ", ".join(f"{v['nom']} ({v['manquants']} j)" for v in manq))
        tl_m = _membre(e["tl"]) if e["tl"] else None
        if tl_m is not None and _a_role_manager(tl_m):
            b.append(f"⛔ {e['tl_nom']} (TL) porte le rôle Manager : retire-le, un TL n'a aucune commande staff.")
        blocs.append("\n".join(b))
    if primee:
        lignes = lignes_primes(calcul)
        total = sum(l[1] for l in lignes)
        anomalies = sum(1 for l in lignes if "⚠️" in l[2])
        blocs.append(f"Primes d'équipe de la période : **{_usd(total)}**, toutes à vérifier avant le virement : 5 abonnés par VA "
                     "primé, sur Infloww ou MyPulse."
                     + (f" ⚠️ {anomalies} ligne(s) avec une anomalie (jour non relevé, Reels, part de visites)." if anomalies else "")
                     + (" Les chiffres bougent jusqu'à la clôture." if en_cours else ""))
    return blocs


def controle_roles(guild, fiches=None) -> list:
    """Écarts entre le rôle « Team Leader » et le registre, dits dans `!tl liste` (revue L10, R10 : une réécriture concurrente
    d'equipes.json peut effacer une nomination en laissant le rôle) : porteur du rôle sans mandat, TL sans le rôle, rôle avec
    des permissions."""
    role = _role_tl(guild) if guild is not None else None
    if role is None:
        return []
    fiches = _fiches() if fiches is None else fiches
    tls = {str(uid): f.get("chef") for uid, f in fiches.items() if isinstance(f, dict) and f.get("chef")}
    porteurs = {str(getattr(m, "id", "")): m for m in getattr(role, "members", None) or []}
    lignes = []
    if _permissions(role):
        lignes.append(f"⛔ Le rôle {ROLE_TL_NOM} a des permissions : vide-le (Réglages du serveur → Rôles). Un TL n'a aucune "
                      "commande staff.")
    for uid, m in porteurs.items():
        if uid not in tls:
            lignes.append(f"⚠️ {getattr(m, 'display_name', uid)} porte le rôle {ROLE_TL_NOM} sans être TL au registre : "
                          f"`!tl Créatrice @{getattr(m, 'display_name', '')}` pour le nommer, sinon retire-lui le rôle.")
    for uid, c in tls.items():
        m = _membre(uid)                                                # ses rôles à lui : jamais d'alerte sur un cache incomplet
        if m is not None and getattr(m, "roles", None) is not None and role not in m.roles:
            lignes.append(f"⚠️ {nom_de(uid, fiches.get(uid))} est TL de {c} sans le rôle {ROLE_TL_NOM} : "
                          f"`!tl {c} @{getattr(m, 'display_name', '')}` le lui repose.")
    return lignes


async def _repondre(message, blocs: list):
    """Paragraphes séparés par une ligne vide, découpés sous la limite de Discord."""
    morceaux, courant = [], ""
    for b in blocs:
        for part in [b[i:i + LIMITE_MESSAGE] for i in range(0, len(b), LIMITE_MESSAGE)] or [""]:
            if courant and len(courant) + len(part) + 2 > LIMITE_MESSAGE:
                morceaux.append(courant)
                courant = ""
            courant = f"{courant}\n\n{part}" if courant else part
    if courant:
        morceaux.append(courant)
    for i, m in enumerate(morceaux):
        if i == 0:
            await message.reply(m)
        else:
            await message.channel.send(m)


def _aide() -> str:
    return ("👥 **Team Leaders et managers** (admins seulement)\n\n"
            "`!tl Chloé @X` : X devient TL de Chloé.\n"
            "`!tl Chloé aucun` : Chloé n'a plus de TL.\n"
            "`!manager @X Chloé Sarah` : X est manager de ces équipes, et de celles-là seulement (la liste remplace la "
            "précédente). `!manager @X aucun` : plus aucune.\n"
            "`!tl liste [5|20 AAAA-MM]` : les équipes et les chiffres de la période.\n\n"
            f"Grille : {_usd(TL_PRIME_VA_USD)} au TL par VA à {_fmt(TL_SEUIL_VA)} visites payées ou plus, "
            f"{_usd(MANAGER_PRIME_USD)} au manager par équipe à {_fmt(MANAGER_SEUIL_EQUIPE)} ou plus. "
            f"Le TL {'compte' if EQUIPE_COMPTE_TL else 'ne compte pas'} dans son équipe.\n\n"
            "Sortie d'un TL : la liste de paie de la période close d'abord (`!paie-clics 5|20`), puis `!tl Chloé aucun`, "
            "puis `!sortie`.")


async def commande(message, texte: str) -> bool:
    """`!tl …` et `!manager …`, réservées aux ADMIN_IDS (jamais au rôle Manager). True si la commande est traitée. Tapée en MP,
    la mention est résolue en membre du serveur, et le serveur est celui de ce membre (revue L10, R8)."""
    mots = (texte or "").split()
    if not mots or mots[0].lower() not in ("!tl", "!manager"):
        return False
    if not est_admin(message.author):
        await message.reply("Réservé aux admins.")
        return True
    args = [m for m in mots[1:] if not (m.startswith("<@") and m.endswith(">"))]
    cible = _resoudre((getattr(message, "mentions", None) or [None])[0])
    par = str(getattr(message.author, "id", ""))
    guild = (getattr(message, "guild", None) or getattr(cible, "guild", None)
             or getattr(_membre(getattr(message.author, "id", "")), "guild", None))
    try:
        if mots[0].lower() == "!manager":
            if cible is None or not args:
                await message.reply("Usage : `!manager @X Chloé Sarah` (ou `!manager @X aucun`).")
                return True
            await _repondre(message, await nommer_manager(cible, [a.strip(",;") for a in args if a.strip(",;")], par))
            return True
        if not args or _n(args[0]) in ("aide", "help"):
            await message.reply(_aide())
            return True
        if _n(args[0]) == "liste":
            await _repondre(message, _liste(args[1:], guild))
            return True
        creatrice = " ".join(a for a in args if _n(a) not in ("aucun", "aucune"))
        if any(_n(a) in ("aucun", "aucune") for a in args):
            await _repondre(message, await retirer_tl(creatrice, par, guild))
            return True
        if cible is None:
            await message.reply("Usage : `!tl Chloé @X`, `!tl Chloé aucun` ou `!tl liste`.")
            return True
        await _repondre(message, await nommer_tl(cible, creatrice, par, guild))
    except Exception as erreur:                                         # noqa: BLE001
        journal.exception("Commande %s en erreur", mots[0])
        await message.reply(f"❌ `{mots[0]}` a échoué ({type(erreur).__name__}). Rien n'a été payé ni changé dans la paie.")
    return True


def _liste(args: list, guild=None) -> list:
    """`!tl liste [5|20 AAAA-MM]` : la période en cours, ou celle de la paie du 5 ou du 20 du mois donné. Avec le serveur : les
    écarts entre le rôle Team Leader et le registre ; toujours : les variables Railway illisibles."""
    if args and args[0] in ("5", "20"):
        mois = args[1] if len(args) > 1 and len(args[1]) == 7 and args[1][4] == "-" else ""
        debut, fin = periode(args[0], mois)
    else:
        debut, fin = periode_de()
    d = {}
    if _deps.get("lire_clics"):
        d = _appel(_deps["lire_clics"], defaut={}) or {}
    calcul = calculer(d, debut, fin, _deps.get("payees"), _deps.get("reels_vus"), _deps.get("jours_manquants"))
    fige = ((d.get("primes_equipes") or {}).get(cle_de_periode(fin)) or {}) if isinstance(d, dict) else {}
    blocs = texte_liste(calcul, en_cours=fin >= _aujourdhui())
    if isinstance(fige, dict) and fige.get("lignes") is not None:
        blocs.append(f"🔒 Période figée le {str(fige.get('calcule_le') or '')[:10]} : la liste de paie relit "
                     f"{_usd(sum(float(l[1]) for l in fige['lignes']))} de primes, quoi qu'affichent les chiffres du jour.")
    try:
        roles = controle_roles(guild)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Contrôle du rôle %s : %s", ROLE_TL_NOM, erreur)
        roles = []
    if roles:
        blocs.append("\n".join(roles))
    if AVERTISSEMENTS:
        blocs.append("⚠️ Railway : " + " ; ".join(AVERTISSEMENTS) + ".")
    if not _deps.get("payees"):
        blocs.append("-# Mesure approchée : paie_clics.payees n'est pas branchée ici.")
    return blocs
