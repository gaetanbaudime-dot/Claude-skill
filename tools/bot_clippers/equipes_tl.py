"""Équipes de Team Leaders et managers (grille de Gaëtan du 10/10, lot L10 de la revue du recrutement).

La grille, telle que Gaëtan l'a écrite le 10/10 :

  - clipper et TL : 0,05 $ la visite payée, payés le 5 et le 20 (paie_clics, inchangé ici) ;
  - TL : en plus, TL_PRIME_VA_USD (10 $) par VA de son équipe à TL_SEUIL_VA (500) visites payées ou plus sur la période ;
  - manager : MANAGER_PRIME_USD (75 $) par équipe dont il a la charge, avec un TL, à MANAGER_SEUIL_EQUIPE (3 000) ou plus.

« Au-dessus de » se lit « ou plus ». Une visite payée = pays francophones, hors robots, sur la période de paie du 5 au 19 ou du
20 au 4 : ni les clics GAML bruts, ni 15 jours glissants.

Modèle (equipes.json, clé = uid Discord, jamais le prénom ; rien dans roster.json) :

  - fiche du TL : « chef » (la créatrice), « chef_depuis » (AAAA-MM-JJ), « chef_par » ; un mandat fini part dans « chef_passe » ;
  - fiche du manager : « manager_de » (créatrices), « manager_depuis », « manager_par » ; un mandat fini part dans « manager_passe » ;
  - mandats.json (à côté d'equipes.json) : le journal de chaque mandat {uid, rôle, créatrices, depuis, jusqu}, écrit par `!tl` et
    `!manager`. `!sortie`, la sortie automatique et le départ du serveur effacent la fiche sans recopier le mandat (sortir_membre,
    hors de ce lot) : `composition` relit ce journal pour un membre sorti après la fin d'une période (reprise 2 de la revue L10).

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
jours non relevés sont injectés, comme le régime et les exclus (`configurer`). Les adaptateurs `reels_vus_par_comptes` et
`jours_manquants_par_paie` donnent à on_ready (lot W) la forme attendue. Une mesure en erreur n'est jamais un 0 : le VA est dit
« non lu » et la prime part « à vérifier ».
"""

import inspect
import json
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
    """deps : lire_json, ecrire_json, FICHIER_EQUIPES ; facultatifs : FICHIER_SORTIS, FICHIER_MANDATS (défaut : mandats.json à
    côté d'equipes.json), ADMIN_IDS, est_manager(membre), membre_par_id(uid), nom_de(uid) ('' ou « id … » pour un inconnu : la
    fiche ou l'entrée de sortie prend le relais), regime(uid) -> « clic » | « fixe », exclu(uid) -> bool ou exclus (prénoms
    normalisés), creatrices() -> noms, lire_clics() -> clics.json, payees(d, uid, debut, fin), reels_vus(uid, debut, fin) (voir
    `reels_vus_par_comptes`), jours_manquants(d, uid, debut, fin) (voir `jours_manquants_par_paie`), heure_paris()."""
    _deps.update(deps or {})


class NonBranche(RuntimeError):
    """`configurer` n'a pas été appelé au démarrage (on_ready, lot W) : dit en clair, jamais un KeyError muet ni une liste de
    primes vide (revue L10, reprise 2)."""


_OBLIGATOIRES = ("lire_json", "ecrire_json", "FICHIER_EQUIPES")


def branche() -> bool:
    return all(k in _deps for k in _OBLIGATOIRES)


def _dep(cle: str):
    if cle not in _deps:
        raise NonBranche(f"equipes_tl non branché : « {cle} » absent de equipes_tl.configurer (on_ready, lot W)")
    return _deps[cle]


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


def _jour_paris(x) -> str:
    """« AAAA-MM-JJ » du jour À PARIS d'un horodatage ISO (sortie, signature) ; une chaîne sans heure garde ses 10 premiers
    caractères. 11/10 (lot W, contre-vérification du lot L10 : un TL sorti le 05/11 à 0 h 30 heure de Paris était daté du 04/11 en
    UTC, donc absent du registre à la fin de la période : sa prime et celle du manager disparaissaient)."""
    t = str(x or "").strip()
    if len(t) <= 10 or "T" not in t:
        return t[:10]
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return t[:10]
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("Europe/Paris")).date().isoformat()
    except Exception:                                                   # noqa: BLE001 — sans base des fuseaux : UTC + 1 h
        return (d.astimezone(timezone.utc) + timedelta(hours=1)).date().isoformat()


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
    return _dep("lire_json")(_dep("FICHIER_EQUIPES"), {}) or {}


def _ecrire_fiches(fiches: dict):
    _dep("ecrire_json")(_dep("FICHIER_EQUIPES"), fiches)


def _sortis() -> list:
    if not _deps.get("FICHIER_SORTIS"):
        return []
    s = _dep("lire_json")(_deps["FICHIER_SORTIS"], []) or []
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


_NOM_PAR_DEFAUT = re.compile(r"(id\s*…?\s*\d*|…?\d+)", re.IGNORECASE)


def nom_de(uid, fiche=None) -> str:
    """Le prénom affiché d'un uid : la dépendance `nom_de`, le pseudo du membre, la fiche (ou l'entrée de sortis.json, qui porte
    « nom »), sinon « id …1234 ». Un « id 1234 » rendu par la dépendance (celui de la paie pour un inconnu) ne court-circuite pas
    la fiche : Gaëtan a besoin du prénom d'un VA sorti pour contrôler ses abonnés (revue L10, reprise 2)."""
    uid = str(uid)
    if _deps.get("nom_de"):
        try:
            nom = str(_deps["nom_de"](uid) or "").strip()
            if nom and not _NOM_PAR_DEFAUT.fullmatch(nom) and nom != uid:
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


# ------------------------------------------------------------------ journal des mandats (mandats.json)
def _fichier_mandats():
    f = _deps.get("FICHIER_MANDATS")
    if f:
        return f
    base = _deps.get("FICHIER_EQUIPES")
    return Path(base).with_name("mandats.json") if base else None


def _lire_strict(f):
    """Le journal relu directement sur le disque (le fichier, sinon sa copie .bak) quand le fichier existe ; None s'il n'existe
    pas (la dépendance lire_json décide alors). Lève ValueError si le fichier et sa copie sont tous deux illisibles."""
    try:
        p = Path(f)
        if not p.exists():
            return None
    except (TypeError, OSError):
        return None
    derniere = None
    for c in (p, p.with_suffix(p.suffix + ".bak")):
        try:
            if c.exists():
                return json.loads(c.read_text(encoding="utf-8"))
        except (ValueError, OSError) as erreur:
            derniere = erreur
    raise derniere if derniere is not None else ValueError("mandats.json et sa copie .bak illisibles")


def _journal(strict: bool = False) -> list:
    """Les mandats notés par `!tl` et `!manager` : [{uid, role (« tl » | « manager »), creatrices, depuis, jusqu ('' = en
    cours), par, nom}]. Illisible : vide, dit au journal (la fiche reste la source pour un membre au registre) ; `strict` : lève,
    pour qu'une écriture ne remplace jamais un journal illisible par les seuls mandats en cours."""
    f = _fichier_mandats()
    if not f:
        return []
    try:
        # 11/10 (lot W, contre-vérification du lot L10 : le lire_json du bot ne lève jamais, il rend [] quand le fichier ET sa
        # copie .bak sont illisibles ; `!tl liste` réécrivait alors le journal avec les seuls mandats en cours, sans un mot) :
        # en écriture (`strict`), un fichier présent est relu ici, puis sa copie .bak ; les deux illisibles → erreur.
        j = _lire_strict(f) if strict else None
        if j is None:
            j = _dep("lire_json")(f, [])
        if j is not None and not isinstance(j, list):
            raise ValueError(f"mandats.json n'est pas une liste ({type(j).__name__})")
    except NonBranche:
        raise
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Journal des mandats illisible (%s)", erreur)
        if strict:
            raise
        return []
    return [m for m in j or [] if isinstance(m, dict)]


def _synchroniser_mandats(fiches: dict, jour: str, par: str = "") -> str:
    """Aligne mandats.json sur equipes.json après `!tl`, `!manager` ou `!tl liste` ; '' si fait, sinon la ligne d'avertissement.

    - un membre au registre : son mandat en cours (créatrices et date) a une entrée ouverte ; une entrée ouverte qui ne lui
      correspond plus est fermée le `jour` ;
    - un membre sorti (fiche effacée par sortir_membre) : son entrée ouverte n'est fermée que si quelqu'un d'autre tient
      maintenant une de ses créatrices (le reste est rouvert le `jour`, comme sur une fiche). Elle ne sert qu'aux périodes finies
      avant sa sortie (`composition`), donc une entrée restée ouverte après la sortie ne paie jamais rien de plus."""
    try:
        j = _journal(strict=True)
    except NonBranche:
        raise
    except Exception as erreur:                                         # noqa: BLE001
        return (f"⚠️ Journal des mandats (mandats.json) illisible ({type(erreur).__name__}) : non réécrit. Remets sa copie .bak, "
                "puis refais la commande.")
    actuels, tenus = {}, {}
    for uid, f in fiches.items():
        if not isinstance(f, dict):
            continue
        uid = str(uid)
        if str(f.get("chef") or "").strip():
            actuels[(uid, "tl")] = ([str(f["chef"]).strip()], str(f.get("chef_depuis") or jour)[:10])
        cs = [str(c).strip() for c in f.get("manager_de") or [] if str(c or "").strip()]
        if cs:
            actuels[(uid, "manager")] = (cs, str(f.get("manager_depuis") or jour)[:10])
    for (uid, role), (cs, _) in actuels.items():
        for c in cs:
            tenus[(role, _n(c))] = uid

    def meme(m, cs, depuis):
        return (sorted(_n(c) for c in m.get("creatrices") or []) == sorted(_n(c) for c in cs)
                and str(m.get("depuis") or "")[:10] == depuis)

    change, ajouts = False, []
    for m in list(j):
        if m.get("jusqu"):
            continue
        uid, role = str(m.get("uid") or ""), str(m.get("role") or "")
        if isinstance(fiches.get(uid), dict):
            a = actuels.get((uid, role))
            if a is None or not meme(m, *a):
                m["jusqu"], change = jour, True
            continue
        cs = [str(c) for c in m.get("creatrices") or []]
        pris = [c for c in cs if tenus.get((role, _n(c))) not in (None, uid)]
        if pris:
            m["jusqu"], change = jour, True
            reste = [c for c in cs if c not in pris]
            if reste:
                ajouts.append(dict(m, creatrices=reste, depuis=jour, jusqu=""))
    j.extend(ajouts)
    for (uid, role), (cs, depuis) in actuels.items():
        if not any(not m.get("jusqu") and str(m.get("uid") or "") == uid and m.get("role") == role and meme(m, cs, depuis)
                   for m in j):
            f = fiches[uid]
            j.append({"uid": uid, "role": role, "creatrices": cs, "depuis": depuis, "jusqu": "",
                      "par": str(f.get("chef_par" if role == "tl" else "manager_par") or par or ""), "nom": nom_de(uid, f)})
            change = True
    if not change:
        return ""
    j = [m for m in j if not m.get("jusqu") or str(m.get("depuis") or "")[:10] < str(m["jusqu"])[:10]]   # vides : rien couvert
    try:
        _dep("ecrire_json")(_fichier_mandats(), j[-2000:])
    except NonBranche:
        raise
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Journal des mandats non écrit (%s)", erreur)
        return (f"⚠️ Journal des mandats (mandats.json) non écrit ({type(erreur).__name__}) : si ce TL ou ce manager sort avant la "
                "liste de paie, sa prime de la période ne sera pas retrouvée. Refais la commande.")
    return ""


def _fermer_mandats(uid, jour: str):
    """Ferme les entrées ouvertes de `uid` le `jour` (fin_de_mandats) ; ne lève jamais."""
    try:
        j = _journal(strict=True)
        touche = False
        for m in j:
            if not m.get("jusqu") and str(m.get("uid") or "") == str(uid):
                m["jusqu"], touche = jour, True
        if touche:
            _dep("ecrire_json")(_fichier_mandats(), j)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Sortie de %s : journal des mandats non fermé (%s)", uid, erreur)


def _mandats_du_journal(jnl: list, uid: str, sortie_iso: str) -> dict:
    """Les mandats de `uid` notés au journal, sous la forme d'une entrée de sortis.json (« chef_passe », « manager_passe ») ; un
    mandat encore ouvert est fermé le jour de sa sortie (`sortie_iso`), comme `mandats_a_garder` l'aurait fait."""
    out = {"chef_passe": [], "manager_passe": []}
    for m in jnl:
        if str(m.get("uid") or "") != uid:
            continue
        cs = [str(c).strip() for c in m.get("creatrices") or [] if str(c or "").strip()]
        depuis, jusqu = str(m.get("depuis") or "")[:10], str(m.get("jusqu") or "")[:10] or sortie_iso
        if not cs or not depuis or not jusqu:
            continue
        if m.get("role") == "tl":
            out["chef_passe"].append({"creatrice": cs[0], "depuis": depuis, "jusqu": jusqu})
        elif m.get("role") == "manager":
            out["manager_passe"].append({"creatrices": cs, "depuis": depuis, "jusqu": jusqu})
    return out


def _present(fiche: dict, fin_iso: str) -> bool:
    """Au registre le jour `fin_iso` : signé ce jour-là ou avant (une fiche sans date est ancienne)."""
    return not fin_iso or _jour_paris(fiche.get("date")) <= fin_iso


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
        if _jour_paris(s.get("signe_le")) <= fin_iso < _jour_paris(s.get("date")):
            out[uid] = s
    return out


# ------------------------------------------------------------------ colonne « Team leader » du classeur (12/10)
# Gaëtan (12/10) : « J'ajouterai dans la colonne team leader du sheets à qui appartient chaque clippeur. » Une colonne « Team leader »
# dans les onglets créatrices du classeur : le prénom du TL sur les lignes de chaque clipper. Un VA nommé là appartient à l'équipe
# de CE TL (plusieurs TL par créatrice possibles) ; un TL nommé là est TL (jamais VA), même sans `!tl`. Colonne vide : la règle du
# 10/10 (l'équipe = la créatrice du TL nommé par `!tl`). Lue à chaque passage du Dashboard (maj_colonne), gardée dans
# tl_colonne.json à côté d'equipes.json ; les décisions se font sur les uid (le @ de la ligne → son détenteur, sinon le Gérant),
# jamais sur un prénom ambigu (deux membres du même prénom : la ligne est ignorée et listée dans « inconnus »).
_COLONNE = {"t": "", "va": None, "inconnus": [], "conflits": []}


def _fichier_colonne():
    return Path(str(_dep("FICHIER_EQUIPES"))).with_name("tl_colonne.json")


def uid_par_nom(nom, fiches=None) -> str:
    """L'uid du membre au registre dont le prénom affiché est `nom` (nom complet d'abord, sinon premier mot), '' s'il n'y en a
    aucun ou plusieurs."""
    cible = _n(nom)
    if not cible:
        return ""
    fiches = _fiches() if fiches is None else fiches
    noms = {str(uid): _n(nom_de(uid, f)) for uid, f in (fiches or {}).items() if isinstance(f, dict)}
    exacts = [u for u, n in noms.items() if n == cible]
    if len(exacts) == 1:
        return exacts[0]
    if exacts:
        return ""
    premier = cible.split()[0]
    par_prenom = [u for u, n in noms.items() if (n.split() or [""])[0] == premier]
    return par_prenom[0] if len(par_prenom) == 1 else ""


def lire_colonne(comptes: list, proprietaires=None, cle_handle=None, fiches=None) -> dict:
    """Pur : {"va": {uid VA : uid TL}, "inconnus": [noms non résolus], "conflits": [prénoms des VA à deux TL]} d'après les lignes du
    classeur (champ « tl »). Le VA d'une ligne : le détenteur de son @ (onboarding, un seul), sinon son Gérant ; le premier TL lu
    gagne pour un VA (les autres lignes en conflit sont listées)."""
    proprietaires = proprietaires or {}
    cle_handle = cle_handle or (lambda h: str(h or "").strip().lstrip("@").lower())
    fiches = _fiches() if fiches is None else fiches
    va, inconnus, conflits = {}, [], []
    for c in comptes or []:
        tl_nom = str((c or {}).get("tl") or "").strip()
        if not tl_nom:
            continue
        tl = uid_par_nom(tl_nom, fiches)
        detenteurs = proprietaires.get(cle_handle(c.get("handle"))) or set()
        v = next(iter(detenteurs)) if len(detenteurs) == 1 else uid_par_nom(c.get("gerant"), fiches)
        if not tl:
            if tl_nom not in inconnus:
                inconnus.append(tl_nom)
            continue
        if not v:
            g = str(c.get("gerant") or "").strip()
            if g and g not in inconnus:
                inconnus.append(g)
            continue
        if v == tl:
            continue                                                    # ses propres comptes : le TL n'est pas son propre VA
        if v in va and va[v] != tl:
            if nom_de(v) not in conflits:
                conflits.append(nom_de(v))
            continue
        va[str(v)] = str(tl)
    return {"va": va, "inconnus": inconnus, "conflits": conflits}


def maj_colonne(comptes: list, proprietaires=None, cle_handle=None) -> dict:
    """Relit la colonne « Team leader » (lire_colonne) et l'enregistre si elle a changé. Jamais d'exception."""
    try:
        lu = lire_colonne(comptes, proprietaires, cle_handle)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Colonne Team leader illisible : %s", erreur)
        return {}
    if lu["va"] != _colonne_va() or lu["inconnus"] != _COLONNE["inconnus"]:
        try:
            _dep("ecrire_json")(_fichier_colonne(), {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), **lu})
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("tl_colonne.json non écrit : %s", erreur)
        if lu["va"] != (_COLONNE["va"] or {}):
            journal.info("Colonne Team leader : %d VA rattaché(s) à %d TL", len(lu["va"]), len(set(lu["va"].values())))
    _COLONNE.update(va=dict(lu["va"]), inconnus=list(lu["inconnus"]), conflits=list(lu["conflits"]))
    return lu


# 13/10 (Gaëtan, organigramme du pool clipping) : les équipes de TL, par prénoms — « TL:VA,VA;TL:VA ». La colonne « Team leader » du
# classeur passe par-dessus pour un VA qu'elle nomme. Un prénom absent du registre, ou porté par deux membres, est ignoré et
# signalé dans `!tl liste`. TL_ORGANIGRAMME= (vide) : la colonne seule.
ORGANIGRAMME = os.environ.get("TL_ORGANIGRAMME", "mathieu:alvaro,thia;clarisse:romaric,ricardo;yves:mohamed,simon,moutakabirou")
_ORGA = {"inconnus": []}


def organigramme_va(texte: str = None, fiches=None) -> dict:
    """{uid VA : uid TL} de l'organigramme (TL_ORGANIGRAMME) ; les prénoms non résolus vont dans _ORGA["inconnus"]."""
    texte = ORGANIGRAMME if texte is None else texte
    va, inconnus = {}, []
    for bloc in str(texte or "").split(";"):
        if ":" not in bloc:
            continue
        tl_nom, vas = bloc.split(":", 1)
        tl = uid_par_nom(tl_nom.strip(), fiches) if tl_nom.strip() else ""
        if not tl:
            if tl_nom.strip():
                inconnus.append(tl_nom.strip().capitalize())
            continue
        for v_nom in vas.split(","):
            v = uid_par_nom(v_nom.strip(), fiches) if v_nom.strip() else ""
            if not v:
                if v_nom.strip():
                    inconnus.append(v_nom.strip().capitalize())
                continue
            if v != tl:
                va.setdefault(str(v), str(tl))
    _ORGA["inconnus"] = inconnus
    return va


def tl_par_va() -> dict:
    """{uid VA : uid TL} : l'organigramme (TL_ORGANIGRAMME), puis la colonne « Team leader » du classeur par-dessus."""
    try:
        base = organigramme_va()
    except Exception as erreur:                                         # noqa: BLE001 — jamais au prix des équipes
        journal.warning("Organigramme des TL illisible : %s", erreur)
        base = {}
    base.update(_colonne_va())
    return base


def _colonne_va() -> dict:
    """{uid VA : uid TL} de la colonne « Team leader » (mémoire, sinon tl_colonne.json) ; {} sans colonne."""
    if _COLONNE["va"] is None:
        try:
            d = _dep("lire_json")(_fichier_colonne(), {}) or {}
        except Exception:                                               # noqa: BLE001
            d = {}
        _COLONNE.update(va={str(k): str(v) for k, v in (d.get("va") or {}).items()}, inconnus=list(d.get("inconnus") or []),
                        conflits=list(d.get("conflits") or []))
    return dict(_COLONNE["va"] or {})


def composition(fiches=None, registre=None, fin=None, mandats=None) -> dict:
    """{créatrice : {"tl": uid | None, "vas": [uid…], "manager": uid | None, "noms": {uid : prénom}}} telle qu'au jour `fin`
    (aujourd'hui si None).

    `fiches` : equipes.json (lu si None). `registre` : la trace des sorties (sortis.json, lue si None) : un membre sorti APRÈS
    `fin` était encore au registre ce jour-là, il compte pour sa période, même revenu depuis avec une fiche neuve. Son mandat de
    TL ou de manager est relu dans son entrée (« chef_passe », « manager_passe », si `fin_de_mandats` les y a recopiés), sinon
    dans le journal `mandats` (mandats.json, lu si None) : sortir_membre efface la fiche sans rien recopier (revue L10, reprise
    2). Un VA : fiche['creatrice'], au clic, TL d'aucune équipe, pas exclu, pas admin, signé au plus tard le jour `fin`. « noms »
    est lu sur la fiche ou l'entrée de sortie : un VA sorti garde son prénom dans la ligne de prime."""
    fiches = _fiches() if fiches is None else (fiches or {})
    registre = _sortis() if registre is None else (registre or [])
    fin_d = _jour(fin)
    fin_iso = fin_d.isoformat() if fin_d else ""
    connues = creatrices_connues(fiches)
    equipes = {}
    sortis = _sortis_a_la_fin(fiches, registre, fin_iso)
    jnl = (_journal() if mandats is None else list(mandats or [])) if sortis else []
    for uid, s in list(sortis.items()):
        du_journal = _mandats_du_journal(jnl, uid, _jour_paris(s.get("date")))
        if du_journal["chef_passe"] or du_journal["manager_passe"]:     # l'entrée d'abord (fin_de_mandats), le journal ensuite
            sortis[uid] = dict(s, chef_passe=list(s.get("chef_passe") or []) + du_journal["chef_passe"],
                               manager_passe=list(s.get("manager_passe") or []) + du_journal["manager_passe"])

    def equipe(c):
        k = _n(c)
        connues.setdefault(k, _affiche(c))
        return equipes.setdefault(k, {"tl": None, "vas": [], "manager": None, "noms": {}})

    def presents():
        """(uid, fiche ou entrée de sortie) de tous ceux qui étaient au registre à la fin : les fiches d'abord."""
        for uid, f in fiches.items():
            if isinstance(f, dict) and _present(f, fin_iso):
                yield str(uid), f
        yield from sortis.items()

    def depuis_tl(f, c):
        """La date du mandat de TL qui couvre la fin (pour départager deux TL d'une même créatrice : le plus ancien)."""
        if _n(f.get("chef")) == _n(c) and str(f.get("chef_depuis") or "")[:10] <= (fin_iso or "9999"):
            return str(f.get("chef_depuis") or "")
        return next((str(m.get("depuis") or "") for m in f.get("chef_passe") or [] if isinstance(m, dict)
                     and _n(m.get("creatrice")) == _n(c) and str(m.get("depuis") or "")[:10] <= fin_iso < str(m.get("jusqu") or "")[:10]),
                    "")

    tls, fiche_de = {}, {}
    candidats = []
    for uid, f in presents():
        fiche_de.setdefault(uid, f)
        c = _mandat_tl(f, fin_iso)
        if c:
            candidats.append((depuis_tl(f, c), uid, c))
    cle_tl = {}                                                         # uid TL → la clé de son équipe
    for _, uid, c in sorted(candidats):                                 # deux TL sur une créatrice (fiche retouchée) : le plus ancien
        tls[uid] = _n(c)
        e = equipe(c)
        if e["tl"] is None:
            e["tl"] = uid
            cle_tl[uid] = c
        else:
            journal.warning("Deux TL pour %s : %s gardé, %s ignoré", c, e["tl"], uid)
    # 12/10 : la colonne « Team leader » du classeur — ses TL sont TL (une équipe à leur nom s'ils n'en ont pas déjà une) et ses VA
    # vont chez eux ; la règle par créatrice ne vaut plus que pour les VA que la colonne ne nomme pas
    colonne = {va: tl for va, tl in tl_par_va().items() if tl in fiche_de}
    for tl in sorted(set(colonne.values())):
        if tl in cle_tl:
            continue
        # le prénom seul : le pseudo Discord porte « Yves - Sarah - TL Sarah », illisible comme nom d'équipe
        prenom = str((fiche_de.get(tl) or {}).get("prenom") or "").strip() or nom_de(tl, fiche_de.get(tl)).split(" - ")[0].strip()
        cle = f"Équipe {prenom}"
        tls.setdefault(tl, _n(cle))
        e = equipe(cle)
        if e["tl"] is None:
            e["tl"] = tl
            cle_tl[tl] = cle
    admins = _admins()
    for uid, f in presents():
        if uid in tls or uid in admins:
            continue
        c = str(f.get("creatrice") or "").strip()
        if not c or _exclu(uid, f) or _regime(uid) != "clic":         # une entrée de sortie porte « nom » : lu par nom_de
            continue
        cible = cle_tl.get(colonne.get(uid, ""))
        equipe(cible or c)["vas"].append(uid)
    for uid, f in presents():
        for c in _mandat_manager(f, fin_iso):
            e = equipe(c)
            if e["manager"] is None:
                e["manager"] = uid
    for tl, cle in cle_tl.items():                                      # 12/10 : une équipe « Équipe X » : le manager de la créatrice du TL
        e = equipes.get(_n(cle))
        c_tl = _n((fiche_de.get(tl) or {}).get("creatrice"))
        if e is not None and e["manager"] is None and c_tl in equipes and c_tl != _n(cle):
            e["manager"] = equipes[c_tl]["manager"]
    for e in equipes.values():
        for uid in [e["tl"], e["manager"], *e["vas"]]:
            if uid and uid not in e["noms"]:
                e["noms"][uid] = nom_de(uid, fiche_de.get(uid))
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


def _mesure(f, *args):
    """Une mesure entière, ou None si elle lève ou ne rend rien de lisible : jamais un faux 0 (revue L10, reprise 2)."""
    v = _appel(f, *args)
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        journal.warning("%s illisible (%r)", getattr(f, "__name__", "mesure"), v)
        return None


# ------------------------------------------------------------------ adaptateurs à injecter (on_ready, lot W)
def reels_vus_par_comptes(comptes_de_uid, reels_vus_compte, derniere_lecture=None):
    """La dépendance `reels_vus(uid, debut, fin)` à partir de series (reprise 2) : series.reels_vus prend la clé d'UN compte et
    une fin EXCLUE ([debut, fin[, une date = minuit à Paris) ; injecté tel quel, il chercherait une série « 20 » et rendrait 0
    Reels sur chaque prime (fausse anomalie permanente, donc muette).

    `comptes_de_uid(uid)` -> les comptes du clipper (bot_discord.comptes_de_uid) ; `reels_vus_compte(cle, debut, fin_exclue)`
    (series.reels_vus) ; `derniere_lecture(cle)` -> '' si jamais lu (series.derniere_lecture, facultatif). Rend la somme sur ses
    comptes du `debut` au `fin` INCLUS (fin + 1 jour exclu), ou None si aucun de ses comptes n'a été lu : « Reels non mesurés »,
    jamais 0."""
    def reels_vus(uid, debut, fin):
        comptes = sorted({str(h) for h in (comptes_de_uid(str(uid)) or ()) if str(h or "").strip()})
        if derniere_lecture is not None:
            comptes = [h for h in comptes if derniere_lecture(h)]
        if not comptes:
            return None
        d0, d1 = _jour(debut), _jour(fin) + timedelta(days=1)
        return sum(_entier(reels_vus_compte(h, d0, d1)) for h in comptes)
    return reels_vus


def jours_manquants_par_paie(jours_manquants_paie, avec_provisoires: bool = True):
    """La dépendance `jours_manquants(d, uid, debut, fin)` à partir de paie_clics.jours_manquants_paie(d, debut, fin,
    avec_provisoires) -> {uid: [(lien, « AAAA-MM-JJ »), …]} (reprise 2) : le nombre de JOURS distincts qui manquent au clipper,
    la même règle que la liste de paie (veilles provisoires comprises, comme la paie), à un détail près : un lien introuvable
    aujourd'hui (404) garde ses jours manquants (`garder_introuvables`, reprise L11). Le calcul de tous les clippers est gardé
    une minute pour un même `d` et une même période (une liste interroge chaque VA)."""
    try:
        params = inspect.signature(jours_manquants_paie).parameters
    except (TypeError, ValueError):
        params = {}
    kw = {k: v for k, v in (("avec_provisoires", avec_provisoires), ("garder_introuvables", True)) if k in params}
    memo = {}

    def jours_manquants(d, uid, debut, fin):
        d0, d1 = _jour(debut), _jour(fin)
        cle = (id(d), d0, d1)
        m = memo.get("dernier")
        if not m or m[0] != cle or m[1] is not d or time.monotonic() - m[2] > 60:
            # 11/10 (reprise L11, R3) : un lien introuvable aujourd'hui (404 passager) garde ses jours manquants pour les primes
            # d'équipe — sinon le VA à 480 avec un jour manquant passait pour complet, et un faux 0 était figé sans un mot
            res = jours_manquants_paie(d, d0, d1, **kw)
            memo["dernier"] = m = (cle, d, time.monotonic(), res if isinstance(res, dict) else {})
        return len({str(j)[:10] for _, j in (m[3].get(str(uid)) or [])})
    return jours_manquants


# ------------------------------------------------------------------ calcul des primes
def calculer(d: dict, debut, fin, payees=None, reels_vus=None, jours_manquants=None, fiches=None, registre=None,
             compo=None) -> dict:
    """Les équipes de la période et leurs chiffres, sans rien écrire. `payees(d, uid, debut, fin)` -> visites payées (la ligne
    de paie) ; `reels_vus(uid, debut, fin)` -> Reels vus sur la période, bornes comprises (None : non mesurable) ;
    `jours_manquants(d, uid, debut, fin)` -> jours non relevés. Une mesure absente : repli local (payees, jours) ou « non
    mesuré » (Reels, donc « à vérifier »). Une mesure en erreur (exception, None) : le VA est « non lu » (`erreur`), compté 0
    dans les montants, et la prime de son TL et de son manager part « à vérifier » (revue L10, reprise 2).
    `compo` (reprise L11) : la composition figée de la période (composition_figee), utilisée telle quelle à la place du
    registre du jour : un VA passé chez une autre créatrice après la clôture ne compte que dans l'équipe où il était."""
    debut, fin = _jour(debut), _jour(fin)
    mesure = payees or _payees_local
    manque = jours_manquants or _jours_manquants_local
    norme = _norme(d, debut, fin)
    n_jours = max(1, (min(fin, max(debut, _aujourdhui() - timedelta(days=1))) - debut).days + 1)
    primee = periode_primee(debut)
    out = {"debut": debut.isoformat(), "fin": fin.isoformat(), "equipes": {}, "norme": norme,
           "reels_branches": reels_vus is not None, "primee": primee}
    for c, e in (composition(fiches, registre, fin) if compo is None else compo).items():
        noms = e.get("noms") or {}
        vas = []
        for uid in e["vas"]:
            p_lu = _mesure(mesure, d, uid, debut, fin)
            j_lu = _mesure(manque, d, uid, debut, fin)
            erreur = ([] if p_lu is not None else ["visites"]) + ([] if j_lu is not None else ["jours"])
            p, j = p_lu or 0, j_lu or 0
            r = _appel(reels_vus, uid, debut, fin) if (reels_vus and p >= PRIME_VOLUME_MIN) else None
            # Revue L10 (R2) : le manager de l'équipe qui y clippe reste VA (le TL est primé sur lui), hors du total qui le paie
            hors_total = uid == e["manager"] and not MANAGER_COMPTE
            vas.append({"uid": uid, "nom": noms.get(uid) or nom_de(uid), "payees": p, "manquants": j,
                        "projete": p + (p * j / max(1, n_jours - j) if j else 0),
                        "reels": None if r is None else _entier(r), "juge": p >= PRIME_VOLUME_MIN,
                        "anomalie": _anomalie(_parts(d, uid, debut, fin), norme), "prime": p >= TL_SEUIL_VA,
                        "hors_total": hors_total, "erreur": erreur})
        vas.sort(key=lambda v: (-v["payees"], v["nom"]))
        tl_p, tl_j, tl_erreur = None, 0, []
        if e["tl"]:
            tl_p = _mesure(mesure, d, e["tl"], debut, fin)
            if tl_p is None:
                tl_erreur.append("visites")
            if EQUIPE_COMPTE_TL:
                tl_j = _mesure(manque, d, e["tl"], debut, fin)
                if tl_j is None:
                    tl_erreur.append("jours")
                tl_j = tl_j or 0
        part_tl = (tl_p or 0) if EQUIPE_COMPTE_TL else 0                # EQUIPE_COMPTE_TL=0 : le TL hors du total
        comptes = [v for v in vas if not v["hors_total"]]
        total = sum(v["payees"] for v in comptes) + part_tl
        projete = sum(v["projete"] for v in comptes) + part_tl + (part_tl * tl_j / max(1, n_jours - tl_j) if tl_j else 0)
        out["equipes"][c] = {"tl": e["tl"], "tl_nom": (noms.get(e["tl"]) or nom_de(e["tl"])) if e["tl"] else "",
                             "tl_payees": tl_p, "tl_manquants": tl_j, "tl_erreur": tl_erreur if EQUIPE_COMPTE_TL else [],
                             "manager": e["manager"],
                             "manager_nom": (noms.get(e["manager"]) or nom_de(e["manager"])) if e["manager"] else "",
                             "vas": vas, "total": total, "projete": projete,
                             "va_primes": sum(1 for v in vas if v["prime"]), "primee": primee}
    return out


def _texte_erreur(nom: str, erreur: list) -> str:
    """« Bea : mesure en erreur (visites non lues, comptées 0) » ou « (jours non relevés inconnus) »."""
    morceaux = (["visites non lues, comptées 0"] if "visites" in erreur else []) + (
        ["jours non relevés inconnus"] if "jours" in erreur else [])
    return f"{nom} : mesure en erreur ({', '.join(morceaux)})"


def _raisons(e: dict, juges: list, reels_branches: bool, pour_manager: bool = False) -> list:
    """Pourquoi une prime est « à vérifier » : mesure en erreur ou jours non relevés dans l'équipe, preuve de publication ou part
    de visites hors norme chez les VA `juges`. `pour_manager` : le manager lui-même, hors du total qui le paie, n'est pas compté."""
    r = []
    dans = [v for v in e["vas"] if not (pour_manager and v.get("hors_total"))]
    erreurs = [_texte_erreur(v["nom"], v["erreur"]) for v in dans if v.get("erreur")]
    if e.get("tl_erreur"):
        erreurs.append(_texte_erreur(f"{e['tl_nom']} (TL)", e["tl_erreur"]))
    r.extend(erreurs)
    manq = [v for v in dans if v["manquants"]] + (
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


def _a_portee(v: dict) -> bool:
    """Un VA sous le seuil que ses jours non relevés pourraient y faire passer (projeté à TL_SEUIL_VA ou plus)."""
    return not v["prime"] and bool(v["manquants"]) and v["projete"] >= TL_SEUIL_VA


def _texte_portee(v: dict) -> str:
    return f"{v['nom']} {_fmt(v['payees'])} / {_fmt(TL_SEUIL_VA)} avec {v['manquants']} j non relevé(s)"


def lignes_primes(calcul: dict) -> list:
    """[(uid, montant, détail, à_vérifier)] : une entrée par bénéficiaire (TL et manager fusionnés), montant décroissant.

    Amendement E (revue L10, R9) : TOUTE ligne avec un montant est « à vérifier » (à_vérifier vrai), car Gaëtan contrôle à la main
    5 abonnés par VA primé avant le virement. Le détail sépare le contrôle de routine (« contrôle abonnés … ») d'une anomalie
    (« ⚠️ à vérifier : … », jour non relevé, mesure en erreur, preuve, part hors norme). Montant 0 = une note « à vérifier »
    seulement, rien à virer : un VA que des jours non relevés pourraient faire passer le seuil (dit aussi quand un autre VA est
    déjà primé), une équipe que ces jours ou une mesure en erreur pourraient faire passer les 3 000, un VA « non lu »."""
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
            portee = [v for v in e["vas"] if _a_portee(v)]
            en_erreur = [v for v in e["vas"] if v.get("erreur")]
            montant = TL_PRIME_VA_USD * len(primes)
            if primes:
                detail = (f"+ {_usd(montant)} équipe {c} ({len(primes)} VA à {_fmt(TL_SEUIL_VA)} ou plus : "
                          + ", ".join(f"{v['nom']} {_fmt(v['payees'])}" for v in primes)
                          + ") · " + CONTROLE_ABONNES_TL)
                # reprise 2 : un VA qui peut encore passer le seuil est dit même quand un autre est déjà primé (+10 $ possibles)
                raisons += [f"{_texte_portee(v)} (+ {_usd(TL_PRIME_VA_USD)} possible)" for v in portee]
            elif portee or en_erreur:
                detail = (f"0 $ équipe {c} pour l'instant"
                          + (" : " + ", ".join(_texte_portee(v) for v in portee) if portee else ""))
            else:
                detail = ""
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
        non_lus = [v for v in e["vas"] if v.get("erreur") and not v.get("hors_total")] or e.get("tl_erreur")
        if e["total"] >= MANAGER_SEUIL_EQUIPE:
            lui = any(v.get("hors_total") for v in e["vas"])
            detail = (f"+ {_usd(MANAGER_PRIME_USD)} manager (équipe {c} à {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)}, "
                      f"TL {'compris' if EQUIPE_COMPTE_TL else 'non compris'}" + (", ses visites non comprises" if lui else "")
                      + ") · " + _controle_abonnes_manager())
            montant = MANAGER_PRIME_USD
        elif (raisons and e["projete"] >= MANAGER_SEUIL_EQUIPE) or non_lus:
            pourquoi = (["des jours non relevés"] if e["projete"] >= MANAGER_SEUIL_EQUIPE and any(
                        v["manquants"] for v in e["vas"] if not v.get("hors_total")) else []) + (
                        ["des mesures en erreur"] if non_lus else [])
            detail = (f"0 $ manager {c} pour l'instant : {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)}"
                      + (" avec " + " et ".join(pourquoi) if pourquoi else ""))
            montant = 0.0
        else:
            continue
        if raisons:
            detail += " · ⚠️ à vérifier : " + " ; ".join(raisons)
        ajouter(m, montant, detail, bool(raisons) or not montant)
    out = [(uid, round(x[0], 2), " · ".join(x[1]), x[2]) for uid, x in par_uid.items()]
    return sorted(out, key=lambda t: (-t[1], t[0]))


def _cle(cle_periode, fin) -> str:
    """La clé de la période figée : « AAAA-MM-JJ » telle quelle ; sinon (« 05/11 » de liste_paie, vide) le jour de paie déduit de
    `fin`, comme paie_clics._cle_periode (revue L10, reprise 2 : contrat L11)."""
    c = str(cle_periode or "").strip()
    return c if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c) else cle_de_periode(fin)


def composition_figee(d: dict, cle_periode, fin):
    """Reprise L11 (R1) : la composition (TL, manager, VA de chaque équipe) figée au premier calcul après la clôture
    (clics.json['primes_equipes'][clé]["composition"], écrit par paie_clics.figer_primes_equipes même quand des jours manquent),
    au format de `composition` ; None si rien n'est figé (on lit alors le registre du jour). Un `!creatrice` tapé entre l'annonce
    et le figement définitif ne déplace donc plus un VA d'une équipe à l'autre : jamais deux primes pour un même VA."""
    fige = ((d or {}).get("primes_equipes") or {}).get(_cle(cle_periode, fin)) if isinstance(d, dict) else None
    compo = fige.get("composition") if isinstance(fige, dict) else None
    if not isinstance(compo, dict):
        return None
    noms = {str(u): str(n) for u, n in (fige.get("noms") or {}).items()} if isinstance(fige.get("noms"), dict) else {}
    out = {}
    for c, e in compo.items():
        if not isinstance(e, dict):
            continue
        tl, m = e.get("tl"), e.get("manager")
        out[str(c)] = {"tl": str(tl) if tl else None, "manager": str(m) if m else None,
                       "vas": [str(u) for u in (e.get("vas") or {})],
                       "noms": {u: noms[u] for u in [str(tl or ""), str(m or ""), *map(str, e.get("vas") or {})] if u in noms}}
    return out


def primes_equipes(d: dict, debut, fin, cle_periode: str = "", payees=None, reels_vus=None, jours_manquants=None) -> list:
    """Contrat du lot L11 (dépendance `primes_equipes` de paie_clics.liste_paie) : [(uid, montant, détail, à_vérifier)].

    Une période figée (clics.json['primes_equipes'][clé] avec « lignes », écrit par paie_clics.figer_primes_equipes avec
    `a_figer`) est relue telle quelle : une liste retapée donne le même montant. La clé est le jour de paie « AAAA-MM-JJ » ;
    `cle_periode` peut être le « 05/11 » de liste_paie ou vide : elle est alors déduite de `fin` (reprise 2). Rien avant
    PRIMES_EQUIPES_DEPUIS. Lève NonBranche si `configurer` n'a pas été appelé (jamais une liste vide en silence)."""
    fige = ((d or {}).get("primes_equipes") or {}).get(_cle(cle_periode, fin)) or {}
    if isinstance(fige, dict) and isinstance(fige.get("lignes"), list):
        return [(str(l[0]), float(l[1]), str(l[2]), bool(l[3])) for l in fige["lignes"] if isinstance(l, (list, tuple)) and len(l) >= 4]
    if not periode_primee(debut):
        return []
    return lignes_primes(calculer(d, debut, fin, payees, reels_vus, jours_manquants,
                                  compo=composition_figee(d, cle_periode, fin)))


def a_figer(d: dict, debut, fin, cle_periode: str = "", payees=None, reels_vus=None, jours_manquants=None) -> dict:
    """Ce que paie_clics.figer_primes_equipes (lot L11) écrit dans clics.json['primes_equipes'][a_figer(…)["cle"]] au premier
    calcul après la clôture : la composition, les chiffres et les lignes (vides avant PRIMES_EQUIPES_DEPUIS). Aucun prénom n'y
    est une clé : tout est indexé par uid. « cle » est toujours « AAAA-MM-JJ » (« 05/11 » ou vide : déduite de `fin`).
    « complet » est faux si une mesure était en erreur (VA « non lu », listé dans « non_lus » de son équipe) : L11 ne fige pas
    une telle période, il réessaie au calcul suivant (reprise 2 : jamais un faux 0 figé).
    Reprise L11 : une composition déjà figée (composition_figee) est reprise telle quelle ; « noms » (uid → prénom) et « primee »
    (à côté de la composition, pas dedans) sont rendus pour que la composition se fige seule, avant les montants."""
    calcul = calculer(d, debut, fin, payees, reels_vus, jours_manquants, compo=composition_figee(d, cle_periode, fin))
    lignes = lignes_primes(calcul) if periode_primee(debut) else []
    non_lus = {c: [v["uid"] for v in e["vas"] if v.get("erreur")] + ([e["tl"]] if e.get("tl_erreur") else [])
               for c, e in calcul["equipes"].items()}
    return {"calcule_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "debut": calcul["debut"], "fin": calcul["fin"],
            "cle": _cle(cle_periode, fin), "complet": not any(non_lus.values()), "primee": bool(calcul.get("primee")),
            "composition": {c: {"tl": e["tl"], "manager": e["manager"], "vas": {v["uid"]: v["payees"] for v in e["vas"]},
                                "total": e["total"], **({"non_lus": non_lus[c]} if non_lus[c] else {})}
                            for c, e in calcul["equipes"].items()},
            "noms": {u: n for e in calcul["equipes"].values()
                     for u, n in [*((v["uid"], v["nom"]) for v in e["vas"]), (e["tl"], e["tl_nom"]), (e["manager"], e["manager_nom"])]
                     if u and n},
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
    non_lus = sum(1 for v in e["vas"] if v.get("erreur"))
    return (f"{c} · TL {e['tl_nom'] or 'aucun'} · VA à {_fmt(TL_SEUIL_VA)} ou plus {e['va_primes']}/{len(e['vas'])} · "
            f"équipe {_fmt(e['total'])} / {_fmt(MANAGER_SEUIL_EQUIPE)} · "
            + (f"primes {_usd(prime_tl + prime_m)}" if primee else "pas de prime sur cette période")
            + (f" · {manq} jour(s) non relevé(s)" if manq else "")
            + (f" · {non_lus} VA non lu(s) (mesure en erreur)" if non_lus else ""))


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
    Ses mandats ouverts dans mandats.json sont fermés le même jour. Facultatif depuis la reprise 2 : sans cet appel, `composition`
    retrouve le mandat dans mandats.json. Ne lève jamais : une erreur Discord est journalisée."""
    uid = str(uid)
    fiche = fiche if fiche is not None else (_fiches().get(uid) or {})
    garde = mandats_a_garder(fiche, jour)
    _fermer_mandats(uid, (_jour(jour) or _aujourdhui()).isoformat())
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
        avert_j = _synchroniser_mandats(fiches, jour, par)               # rattrape un mandat absent du journal
        return lignes + ([avert_j] if avert_j else [])
    lignes, anciens = [], []
    d0, f0 = periode_de()
    en_cours = f"la période en cours ({d0.strftime('%d/%m')} → {f0.strftime('%d/%m')})"
    if fiche.get("chef"):
        lignes.append(f"{membre.display_name} quitte l'équipe de {fiche['chef']} (un TL n'a qu'une équipe) : "
                      f"{en_cours} n'a plus de TL pour {fiche['chef']}, donc pas de prime TL, sauf si un autre y est nommé "
                      f"d'ici le {f0.strftime('%d/%m')}.")
        _fin_mandat(fiche, "chef", jour)
    for autre, f in fiches.items():
        if autre != uid and isinstance(f, dict) and _n(f.get("chef")) == _n(canon):
            lignes.append(f"{nom_de(autre, f)} n'est plus TL de {canon}.")
            _fin_mandat(f, "chef", jour)
            anciens.append(autre)
    fiche.update({"chef": canon, "chef_depuis": jour, "chef_par": str(par or "")})
    _ecrire_fiches(fiches)                                              # lu et écrit sans attente : rien ne s'intercale
    avert_j = _synchroniser_mandats(fiches, jour, par)
    if anciens:                                                         # reprise 2 : le TL d'une période est celui de son dernier jour
        noms_a = ", ".join(nom_de(a, fiches[a]) for a in anciens)
        lignes.append(f"Le TL d'une période est celui de son dernier jour : {en_cours} revient entière à {membre.display_name}, "
                      f"plus à {noms_a}.")
        for a in anciens:
            if _n(fiches[a].get("creatrice")) == _n(canon) and _regime(a) == "clic" and not _exclu(a, fiches[a]):
                lignes.append(f"{nom_de(a, fiches[a])} clippe sur {canon} : il y compte désormais comme VA.")
    for autre in anciens:
        avert = await _poser_role(_membre(autre), guild, False, f"Plus TL de {canon}")
        if avert:
            lignes.append(avert)
    avert = await _poser_role(membre, guild, True, f"TL de {canon}")
    compte = (f"Il ne compte ni dans les {_fmt(TL_SEUIL_VA)} ni dans les {_fmt(MANAGER_SEUIL_EQUIPE)} de son équipe"
              if not EQUIPE_COMPTE_TL else
              f"Il ne compte pas dans les {_fmt(TL_SEUIL_VA)} ; il compte dans les {_fmt(MANAGER_SEUIL_EQUIPE)} de son équipe "
              "(EQUIPE_COMPTE_TL=1)")
    entete = (f"✅ {membre.display_name} est TL de {canon} depuis le {_jour(jour).strftime('%d/%m')}.\n\n"
              f"Ses visites restent payées comme celles d'un clipper. {compte}. "
              f"Prime : {_usd(TL_PRIME_VA_USD)} par VA à {_fmt(TL_SEUIL_VA)} visites payées ou plus.\n\n"
              f"Rôle {ROLE_TL_NOM} : aucune commande staff. Ne lui donne jamais le rôle Manager.")
    if _regime(uid) == "fixe":
        lignes.append(f"{membre.display_name} est au fixe : sa prime d'équipe passe sur une ligne à part. "
                      f"`!paie @{membre.display_name} clic` le jour où son fixe s'arrête.")
    if not periode_primee(d0):
        lignes.append(_texte_premiere_periode())
    for a in (avert, avert_j):
        if a:
            lignes.append(a)
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
    avert_j = _synchroniser_mandats(fiches, jour, par)
    lignes = [f"✅ {', '.join(nom_de(u, fiches[u]) for u in partis)} n'est plus TL de {canon} (depuis le "
              f"{_jour(jour).strftime('%d/%m')}). La période en cours n'a plus de prime TL pour {canon}."]
    if avert_j:
        lignes.append(avert_j)
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
        avert_j = _synchroniser_mandats(fiches, jour, par)
        return [f"✅ {membre.display_name} n'est plus manager (depuis le {_jour(jour).strftime('%d/%m')})."] + ([avert_j] if avert_j else [])
    connues = creatrices_connues(fiches)
    inconnues = [c for c in creatrices if _n(c) not in connues]
    if inconnues:
        return [f"❌ Créatrice(s) inconnue(s) : {', '.join(inconnues)}. Connues : {', '.join(sorted(connues.values())) or 'aucune'}."]
    canons = list(dict.fromkeys(connues[_n(c)] for c in creatrices))
    if sorted(_n(c) for c in fiche.get("manager_de") or []) == sorted(_n(c) for c in canons):
        avert_j = _synchroniser_mandats(fiches, jour, par)               # rattrape un mandat absent du journal
        return [f"ℹ️ {membre.display_name} est déjà manager de {', '.join(canons)}."] + ([avert_j] if avert_j else [])
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
    avert_j = _synchroniser_mandats(fiches, jour, par)
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
    if avert_j:
        lignes.append(avert_j)
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
    col = tl_par_va()                                                   # 12/10 : colonne « Team leader » ; 13/10 : + organigramme
    if col or _COLONNE["inconnus"] or _COLONNE["conflits"] or _ORGA["inconnus"]:
        ligne = f"Organigramme et colonne « Team leader » : {len(col)} clipper(s) rattaché(s) à {len(set(col.values()))} TL."
        if _ORGA["inconnus"]:
            ligne += " ⚠️ Organigramme, prénoms pas encore au registre (ou en double) : " + ", ".join(_ORGA["inconnus"][:8]) + "."
        if _COLONNE["inconnus"]:
            ligne += " ⚠️ Prénoms non reconnus (aucun membre, ou deux du même prénom) : " + ", ".join(_COLONNE["inconnus"][:8]) + "."
        if _COLONNE["conflits"]:
            ligne += " ⚠️ Deux TL différents pour : " + ", ".join(_COLONNE["conflits"][:8]) + " (le premier lu gagne)."
        blocs.append(ligne)
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
            b.append("VA : " + " · ".join((f"{v['nom']} non lu" if "visites" in (v.get("erreur") or []) else
                                           f"{v['nom']} {_fmt(v['payees'])}") + (" ✓" if v["prime"] else "")
                                          + (f" (manager : hors des {_fmt(MANAGER_SEUIL_EQUIPE)})" if v.get("hors_total") else "")
                                          for v in e["vas"]))
        manq = [v for v in e["vas"] if v["manquants"]]
        if manq:
            b.append("⚠️ Jours non relevés : " + ", ".join(f"{v['nom']} ({v['manquants']} j)" for v in manq))
        non_lus = [_texte_erreur(v["nom"], v["erreur"]) for v in e["vas"] if v.get("erreur")]
        if non_lus:
            b.append("⚠️ " + " ; ".join(non_lus) + ". Les primes de l'équipe partent « à vérifier ».")
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
            "Sortie d'un TL ou d'un manager : rien de spécial. Son mandat est gardé (mandats.json) pour la période close ; "
            "nomme le suivant avec `!tl Chloé @Y`.")


def _cible(message, texte: str):
    """(membre, refus) : la personne écrite dans la commande (« <@123> » ou « <@!123> »), résolue en membre du serveur ; la
    première mention seulement s'il n'y en a aucune dans le texte. Reprise 2 : une commande tapée EN RÉPONSE à un message met
    aussi l'auteur du message cité dans `mentions` (souvent en premier) : il n'est jamais pris à la place de la personne écrite.
    Deux personnes écrites : refus."""
    mentions = list(getattr(message, "mentions", None) or [])
    ids = list(dict.fromkeys(re.findall(r"<@!?(\d+)>", texte or "")))
    if len(ids) > 1:
        return None, ("❌ Une seule personne par commande : le message en mentionne " + str(len(ids))
                      + ". Refais la commande avec la seule personne à nommer.")
    if ids:
        m = _membre(ids[0]) or next((x for x in mentions if str(getattr(x, "id", "")) == ids[0]), None)
        if m is None:
            return None, f"❌ Personne introuvable : <@{ids[0]}> n'est ni sur le serveur ni dans les mentions du message."
        return m, ""
    return _resoudre(mentions[0] if mentions else None), ""


async def commande(message, texte: str) -> bool:
    """`!tl …` et `!manager …`, réservées aux ADMIN_IDS (jamais au rôle Manager). True si la commande est traitée. Tapée en MP,
    la mention est résolue en membre du serveur, et le serveur est celui de ce membre (revue L10, R8). La personne est celle
    ÉCRITE dans la commande, jamais l'auteur d'un message cité (reprise 2)."""
    mots = (texte or "").split()
    if not mots or mots[0].lower() not in ("!tl", "!manager"):
        return False
    if not branche():
        journal.error("%s tapé, mais equipes_tl.configurer n'a pas été appelé au démarrage (on_ready, lot W)", mots[0])
        await message.reply(f"❌ `{mots[0]}` n'est pas branché au démarrage (equipes_tl.configurer manque dans on_ready). "
                            "Rien n'a été changé.")
        return True
    if not est_admin(message.author):
        await message.reply("Réservé aux admins.")
        return True
    args = [m for m in mots[1:] if not (m.startswith("<@") and m.endswith(">"))]
    cible, refus_cible = _cible(message, texte)
    par = str(getattr(message.author, "id", ""))
    guild = (getattr(message, "guild", None) or getattr(cible, "guild", None)
             or getattr(_membre(getattr(message.author, "id", "")), "guild", None))
    try:
        if mots[0].lower() == "!manager":
            if refus_cible:
                await message.reply(refus_cible)
                return True
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
        if refus_cible:
            await message.reply(refus_cible)
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
    usage = ("Usage : `!tl liste` (période en cours) ou `!tl liste 5 2026-11` (paie du 5 novembre), "
             "`!tl liste 20 2026-10` (paie du 20 octobre).")
    if args and args[0] in ("5", "20"):
        if len(args) > 2 or (len(args) == 2 and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args[1])):
            return [f"❌ Mois illisible : « {' '.join(args[1:])} ». " + usage]       # reprise 2 : plus de « a échoué (ValueError) »
        debut, fin = periode(args[0], args[1] if len(args) == 2 else "")
    elif args:
        return [f"❌ Période illisible : « {' '.join(args)} ». " + usage]
    else:
        debut, fin = periode_de()
    try:                                                                # rattrape un mandat noté à la main dans equipes.json
        avert_j = _synchroniser_mandats(_fiches(), _aujourdhui().isoformat())
    except NonBranche:
        raise
    except Exception as erreur:                                         # noqa: BLE001
        avert_j = f"⚠️ Journal des mandats non mis à jour ({type(erreur).__name__})."
    d = {}
    if _deps.get("lire_clics"):
        d = _appel(_deps["lire_clics"], defaut={}) or {}
    compo = composition_figee(d, "", fin)
    calcul = calculer(d, debut, fin, _deps.get("payees"), _deps.get("reels_vus"), _deps.get("jours_manquants"), compo=compo)
    fige = ((d.get("primes_equipes") or {}).get(cle_de_periode(fin)) or {}) if isinstance(d, dict) else {}
    blocs = texte_liste(calcul, en_cours=fin >= _aujourdhui())
    if isinstance(fige, dict) and fige.get("lignes") is not None:
        blocs.append(f"🔒 Période figée le {str(fige.get('calcule_le') or '')[:10]} : la liste de paie relit "
                     f"{_usd(sum(float(l[1]) for l in fige['lignes']))} de primes, quoi qu'affichent les chiffres du jour.")
    elif compo is not None:                                             # reprise L11 : équipes figées, chiffres pas encore
        blocs.append(f"🔒 Équipes figées le {str(fige.get('composition_le') or '')[:10]} (qui est TL, manager, VA de quelle "
                     f"équipe) : un changement de créatrice depuis ne compte pas pour cette période. Les visites, elles, "
                     f"bougent encore jusqu'au figement des primes.")
    try:
        roles = controle_roles(guild)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Contrôle du rôle %s : %s", ROLE_TL_NOM, erreur)
        roles = []
    if roles:
        blocs.append("\n".join(roles))
    if AVERTISSEMENTS:
        blocs.append("⚠️ Railway : " + " ; ".join(AVERTISSEMENTS) + ".")
    if avert_j:
        blocs.append(avert_j)
    if not _deps.get("payees"):
        blocs.append("-# Mesure approchée : paie_clics.payees n'est pas branchée ici.")
    return blocs
