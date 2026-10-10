"""Contrôle d'attribution (09/10, dashboard — Gaëtan : « pas de manquements, pas de clippeurs ou de liens pas assignés au compte »).

Le bot rapproche aujourd'hui un compte, un clipper, un lien GAML et une créatrice par un prénom tapé dans la colonne Gérant. Ce
module vérifie, toutes les 15 min (boucle de l'onboarding, juste après la colonne « Lien GAML associé ») et à chaque réécriture du
Dashboard, que tout est attribué une fois et une seule. Il SIGNALE, il ne corrige rien : c'est Gaëtan qui tranche.

Familles (contrat C3) :
  C1  compte créé (hors BAN) sans Gérant — la file « à mettre Metricool » avec sa date de premier signalement ;
  C2  Gérant fantôme (ni membre signé unique sur le serveur, ni créatrice, ni « X (Metricool) » connu) ;
  C3  Gérant ambigu (deux membres signés du même prénom) ;
  C4  Gérant ≠ propriétaire de la fiche d'onboarding (accès et codes 2FA encore chez un autre, compte jamais livré) ;
  C5  clipper dont le lien est dû (parcours.lien_du, ou ancien avec un compte créé) sans lien pour la créatrice de la ligne ;
  C6  cellule « Lien GAML associé » ≠ lien attendu (libéré, hors clipping, supprimé, désactivé, autre clipper, page de la créatrice,
      lien jamais attribué), ou VIDE alors que le clipper a son lien ;
  C7  lien attribué sans ligne vivante (ou à un membre absent du registre) ;
  C8  lien libéré, hors clipping ou jamais attribué avec des visites payables sur 7 j, porté par aucune ligne ;
  C9  note GAML ≠ attribution du bot ;
  C10 lien en bio Instagram (etats_comptes.json « bios ») ≠ lien attendu ;
  C11 @ en double (même onglet, ou deux onglets : la ligne écartée par onboarding._sans_doublons est invisible au bot) ;
  C12 compte non lu / restreint / illisible au dernier passage (etats « non_lus », « dernier_passage », historique, séries).

Règles communes (revue du 09/10) :
  - contrat C6(d) : « lien (ou compte) d'un autre clipper » se décide sur les IDENTIFIANTS — l'uid du lien (clics.json) contre le
    détenteur de la ligne d'après onboarding.json (livraison la plus récente, sinon fiches), compatible avec le Gérant écrit —, jamais
    sur le premier mot d'un pseudo ou d'un Gérant. Sans détenteur connu, un nom compatible (un mot en commun) laisse le bénéfice du
    doute, un nom incompatible n'est qu'« important » (jamais « bloquant » sans preuve par les identifiants) ;
  - contrat C6(e) : les visites d'un lien sur une période sont celles de paie_clics.clics_lien (plancher `depuis`, None si un jour
    manque) — partout : C8, visites_7j, bouclage (le TOTAL du Dashboard et le bouclage concordent) ;
  - « page de la créatrice » se définit positivement (note « Compte de @… », /ytb, /fb, page principale, note sans « Clipping ») ;
    un lien de clipping sans détenteur (« Clipping Nina » jamais attribué, suivi du rapport sans uid) est « non_attribue » : il
    compte dans l'écart du bouclage ;
  - une famille qui n'a pas pu juger le dit par une entrée « non mesuré » (gravité info, `"non_mesure": True`, clé
    « Cx|non_mesure ») : le contrôle n'écrit jamais « 0 anomalie » ni « chaque lien est attribué » quand une famille n'a rien pu voir.

API :
  anomalies(comptes, clics, onboarding_etat, registre, membres, series_etat) -> [{"famille", "gravite", "texte", "cle"}]
      pure : les entrées optionnelles (etats, parcours, details_gaml, premiers_vus, memoire, maintenant) se passent en mots-clés ;
      laissées à None, elles sont LUES (lecture seule) dans les fichiers du bot quand le module est configuré, sinon ignorées.
  bouclage(clics, lignes_attribuees, fin=None, jours=7, masques=None, notes=None) -> dict : visites 7 j de tous les liens actifs =
      lignes + masques + pages + libérés/hors clipping + écart (liens attribués ou de clipping portés par aucune ligne), et
      `categories` {lid: catégorie} (10/10).
  categorie(info, note) — sans `note`, celle que lit le bouclage (10/10 : le Dashboard et le bouclage rangent pareil) ;
  categorie_lien(clics, lid) ; clics_lien(clics, lid, debut, fin) ; visites_7j(clics, lid, fin) ; texte_admin(anomalies) ;
  empreinte(anomalies, precedentes=None) ; compter(anomalies) ; non_mesurees(anomalies) -> {famille: raison}.
  await passage(deps) : le tour de 15 min (calcul, mémoire des premiers signalements, des dernières mesures, des notes GAML
      vivantes et des clés du tour d'avant, salon admin seulement si l'empreinte change).

Aucun appel GAML, Apify ni Google en écriture : le classeur est relu (lire_comptes), tout le reste vient des fichiers du bot.
"""

import hashlib
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import onboarding

try:                                                                     # contrat C6(e) : la règle des visites d'un lien (clics_lien)
    import paie_clics
except Exception:                                                        # noqa: BLE001 — repli local identique plus bas
    paie_clics = None

journal = logging.getLogger("controle")

FAMILLES = {
    "C1": "Compte créé sans Gérant",
    "C2": "Gérant fantôme",
    "C3": "Gérant ambigu (homonymes)",
    "C4": "Gérant ≠ fiche d'onboarding",
    "C5": "Lien dû manquant",
    "C6": "Cellule Lien GAML fausse",
    "C7": "Lien sans ligne vivante",
    "C8": "Visites sur lien libéré / hors clipping / jamais attribué",
    "C9": "Note GAML ≠ attribution",
    "C10": "Lien en bio ≠ lien attendu",
    "C11": "@ en double",
    "C12": "Compte non lu / restreint / illisible",
}
GRAVITES = ("bloquant", "important", "info")
# 09/10 (dashboard) : les prénoms du staff (Gérant d'un compte de redirection, repreneur Metricool) ne sont jamais des fantômes.
# 09/10 (revue CONTROLE) : seulement quand AUCUN membre signé ne porte ce prénom (Rianah est aussi clippeuse signée depuis le 07/10).
STAFF = {p for p in (onboarding._norm(x).strip() for x in os.environ.get("CONTROLE_STAFF", "gaetan,rianah,jonas").split(",")) if p}
BIO_JOURS = int(os.environ.get("CONTROLE_BIO_JOURS", "7") or 7)         # une bio relevée il y a plus longtemps n'est plus jugée
# 10/10 (paie du 5 et du 20) : le début du relevé est celui de paie_clics (2026-10-05), jamais une date recopiée ici
CLICS_DEPUIS = str(getattr(paie_clics, "CLICS_DEPUIS", "") or os.environ.get("CLICS_DEPUIS", "2026-10-05")).strip()
MEMOIRE_JOURS = int(os.environ.get("CONTROLE_MEMOIRE_JOURS", "3") or 3)   # C8 : dernière mesure gardée au plus 3 jours
GRACE_H = int(os.environ.get("CONTROLE_GRACE_H", "24") or 24)            # C12 « jamais lu » : info pendant 24 h (ligne neuve)
LIMITE_TEXTE = 1950
JETON_LIBERER = "Rendu"     # Gérant provisoire du remède C4 : aucun membre ne s'appelle ainsi, rien ne lui est livré entre-temps
SEPARATEURS_PSEUDO = (" - ", " – ", " — ", " | ", " · ")                 # les mêmes que bot_discord.prenom_de
PAGES_CHEMINS = {"ytb", "fb", "yt", "youtube", "facebook"}
_RE_COMPTE_DE = re.compile(r"\s*compte\s+de\s+@?\s*(\S+)")
_RE_CLIPPING = re.compile(r"\s*clipping\s+(.+)$", re.I)
# 10/10 (vérification CONTROLE) : « Clipping » n'importe où dans la note (« Chloé - Clipping Nina », « Lien clipping Nina ») — un
# lien de clipping, jamais une page de la créatrice
_RE_CLIPPING_PARTOUT = re.compile(r"\bclipping\s+(\S.*)$", re.I)
_RE_MOT_CLIPPING = re.compile(r"\bclipping\b", re.I)
_RE_EX = re.compile(r"\(\s*ex\b[^)]*\)", re.I)                          # « (ex-Clipping Paul) » : l'ancien détenteur, pas la note
_RE_METRICOOL = re.compile(r"\s*(\S+)\s+metricool\b")
_RE_INSTAGRAM = re.compile(r"(^|\.)(instagram\.com|instagr\.am|threads\.net)$")


def _clipping_de(note):
    """10/10 (vérification CONTROLE) : le match « Clipping <nom> » d'une note, en tête (« Clipping Nina ») ou ailleurs (« Chloé -
    Clipping Nina »), sans compter une parenthèse « (ex-…) » ; None si la note ne dit pas « Clipping <nom> »."""
    note = str(note or "")
    return _RE_CLIPPING.match(note) or _RE_CLIPPING_PARTOUT.search(_RE_EX.sub(" ", note))


_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER_ONBOARDING (ou FICHIER_CONTROLE), FICHIER_CLICS, FICHIER_EQUIPES, canal_admin,
    membre_par_id, normaliser ; facultatifs FICHIER_ETATS, FICHIER_PARCOURS, FICHIER_SERIES (sinon à côté de FICHIER_ONBOARDING)."""
    _deps.update(deps or {})


def _dep(nom: str):
    """09/10 (dashboard) : la dépendance de ce module, sinon celle de l'onboarding (configuré dès le démarrage du bot)."""
    if nom in _deps:
        return _deps[nom]
    return (getattr(onboarding, "_deps", None) or {}).get(nom)


# ------------------------------------------------------------------ petites règles
def _n(t) -> str:
    return onboarding._norm(str(t or "")).strip()


def _premier(t) -> str:
    return (_n(t).split() or [""])[0]


def _compact(t) -> str:
    return re.sub(r"[^a-z0-9]", "", _n(t))


def _avant_separateur(t) -> str:
    """« Paul - Sophie » → « Paul » (pseudo « Prénom - Créatrice », mêmes séparateurs que bot_discord.prenom_de)."""
    t = str(t or "")
    for sep in SEPARATEURS_PSEUDO:
        if sep in t:
            return t.split(sep, 1)[0]
    return t


def _mots_nom(t) -> set:
    """09/10 (revue CONTROLE, contrat C6(d)) : les mots d'un pseudo (avant « - Créatrice ») ou d'un Gérant, tirets et signes traités
    comme des espaces : « Jean-Marc » → {jean, marc}, « 🌸 Paul - Sophie » → {paul}. Sert seulement à laisser le bénéfice du doute
    (un mot en commun), jamais à conclure seul qu'un lien est à un autre."""
    return set(re.findall(r"[a-z0-9]+", _n(_avant_separateur(t)))) - {"metricool", "clipper", "compte"}


def _cle_compte(h) -> str:
    return onboarding.normaliser_handle(h).lower()


def _url_cle(u) -> str:
    """« https://www.site.test/5/?utm_source=ig » → « site.test/5 » : la même adresse, écrite autrement, se retrouve."""
    t = str(u or "").strip().lower()
    t = re.sub(r"^[a-z][a-z0-9+.-]*://", "", t)
    t = re.sub(r"^www\.", "", t)
    t = re.split(r"[?#]", t)[0]
    return t.rstrip("/")


def _hote(u) -> str:
    return _url_cle(u).split("/")[0]


def _date(t):
    try:
        return date.fromisoformat(str(t or "")[:10])
    except ValueError:
        return None


def _instant(t):
    """Un instant ISO (« Z » accepté), sans fuseau = UTC ; None si illisible."""
    s = str(t or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _paris(quand: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return quand.astimezone(ZoneInfo("Europe/Paris"))
    except Exception:                                                    # noqa: BLE001 — base de fuseaux absente
        return quand.astimezone(timezone(timedelta(hours=2)))


def _hier_paris(maintenant: datetime = None) -> date:
    return _paris(maintenant or datetime.now(timezone.utc)).date() - timedelta(days=1)


def _usd(x) -> str:
    try:
        return f"{float(x):.2f}".replace(".", ",") + " $"
    except (TypeError, ValueError):
        return "? $"


def _etat_n(c) -> str:
    return _n(c.get("etat"))


def _a_creer(c) -> bool:
    return _etat_n(c) in onboarding.A_CREER


def _ban(c) -> bool:
    return _etat_n(c) == "ban"


def _perdu(c) -> bool:
    return "perdu" in _etat_n(c)


def _cree(c) -> bool:
    """Compte créé et utilisable : ni « à créer », ni BAN, ni perdu, ni ETAT vide (inconnu)."""
    e = _etat_n(c)
    return bool(e) and not _a_creer(c) and not _ban(c) and not _perdu(c)


def _vivante(c) -> bool:
    return bool(c.get("handle")) and not _ban(c) and not _perdu(c)


def _cr_ligne(c) -> str:
    return _premier(c.get("creatrice") or c.get("onglet"))


def _ou(c) -> str:
    return f"{c.get('onglet') or '?'} l. {c.get('ligne') or '?'}"


def _qui(c) -> str:
    return f"@{c.get('handle')} ({str(c.get('gerant') or '').strip() or 'sans Gérant'})"


def _slug(u) -> str:
    return _url_cle(u) or "?"


def _sans_colonne_lien(onglet) -> bool:
    """09/10 (revue CONTROLE) : l'onglet a été lu (lire_comptes) et son en-tête n'a pas de colonne « Lien GAML associé » : le bot
    n'y écrit aucun lien (onboarding.liens_classeur). Inconnu (onglet jamais lu, données de test) → False."""
    lues = (getattr(onboarding, "_colonnes_lues_par_onglet", None) or {}).get(onglet)
    return lues is not None and "lien_gaml" not in lues


def _membres(membres) -> dict:
    """{uid: pseudo Discord} quelle que soit la forme reçue : dict uid → pseudo ou membre, liste de membres (id, display_name),
    liste de paires (uid, pseudo). Le contrat ne fixe pas la forme : on accepte toutes celles du bot."""
    if not membres or callable(membres):
        return {}
    out = {}
    paires = membres.items() if isinstance(membres, dict) else membres
    for x in paires:
        if isinstance(membres, dict) or (isinstance(x, (tuple, list)) and len(x) >= 2):
            uid, v = x[0], x[1]
        else:
            uid, v = getattr(x, "id", None), x
        if uid is None or v is None or isinstance(v, bool):
            continue
        if isinstance(v, str):
            nom = v
        elif isinstance(v, dict):
            nom = v.get("display_name") or v.get("nom") or v.get("name") or ""
        else:
            nom = getattr(v, "display_name", "") or getattr(v, "name", "") or ""
        out[str(uid)] = str(nom or "")
    return out


def _non_mesure(famille: str, raison: str, portee: list = None) -> dict:
    """09/10 (revue CONTROLE) : une famille qui n'a pas pu juger le dit (jamais « 0 anomalie » à sa place). `portee` = ce qui n'a
    pas été jugé : des clés exactes (« C8|L3 ») ou un préfixe de famille (« C2| », par défaut la famille entière). Le tour de 15 min
    garde dans son empreinte les anciennes clés couvertes (pas de message parasite quand une source manque le temps d'un tour)."""
    return {"famille": famille, "gravite": "info", "texte": f"non mesuré : {raison}", "cle": f"{famille}|non_mesure",
            "non_mesure": True, "portee": list(portee) if portee is not None else [f"{famille}|"]}


def _couverte(cle: str, portees) -> bool:
    return any(cle == p or (p.endswith("|") and cle.startswith(p)) for p in portees or ())


# ------------------------------------------------------------------ visites (relevé local de paie_clics, zéro appel)
def _clics_lien_local(clics: dict, lid: str, debut: date, fin: date):
    """Repli IDENTIQUE à paie_clics.clics_lien (contrat C2), seulement si ce module manque : somme des `payes` du `debut` au `fin`
    inclus ; un lien repris ne compte qu'à partir de `depuis` (période tout entière avant → None) ; None si un jour manque, porte une
    erreur ou n'a pas de `payes` (jamais un faux 0)."""
    if debut is None or fin is None or fin < debut:
        return None
    dep = _date((((clics or {}).get("liens") or {}).get(str(lid)) or {}).get("depuis"))
    if dep is not None and dep > debut:
        debut = dep
    if debut > fin:
        return None
    jours = ((clics or {}).get("jours") or {}).get(str(lid)) or {}
    total, j = 0, debut
    while j <= fin:
        v = jours.get(j.isoformat()) if isinstance(jours, dict) else None
        if not isinstance(v, dict) or v.get("erreur") or v.get("payes") is None:
            return None
        try:
            total += int(v.get("payes") or 0)
        except (TypeError, ValueError):
            return None
        j += timedelta(days=1)
    return total


def clics_lien(clics: dict, lid: str, debut: date, fin: date):
    """Contrat C6(e) : les visites payables du lien sur la période, exactement par paie_clics.clics_lien (le Dashboard, le classeur et
    la paie lisent la même règle) ; repli local identique si le module manque. None = non mesuré."""
    f = getattr(paie_clics, "clics_lien", None) if paie_clics is not None else None
    try:
        return f(clics or {}, str(lid), debut, fin) if callable(f) else _clics_lien_local(clics, str(lid), debut, fin)
    except Exception as erreur:                                          # noqa: BLE001 — un relevé abîmé = non mesuré, jamais 0
        journal.debug("Contrôle : visites de %s illisibles (%s)", lid, erreur)
        return None


def visites_7j(clics: dict, lid: str, fin: date, jours: int = 7):
    """Visites payables (`payes`) d'un lien sur les `jours` jours finissant `fin` (inclus). 09/10 (revue CONTROLE, contrat C6(e)) :
    paie_clics.clics_lien — un lien repris ne compte qu'à partir de `depuis`, None si un jour de la période manque ou porte une erreur
    (avant : les jours d'avant la reprise étaient comptés, le bouclage ne concordait pas avec le TOTAL du Dashboard)."""
    return clics_lien(clics, lid, fin - timedelta(days=jours - 1), fin)


def _visites_recentes(clics: dict, lid: str, fin: date, mesures: dict = None, jours: int = 7) -> tuple:
    """(visites, début, fin, source) des 7 derniers jours COMPLETS du lien. 09/10 (revue CONTROLE : C8 clignotait chaque nuit entre
    minuit et le relevé de J-1) : la fenêtre qui finit hier ; si un jour y manque, celle qui finit la veille (J-1 pas encore relevé) ;
    sinon la dernière mesure gardée par le contrôle (controle.json, au plus MEMOIRE_JOURS) ; sinon (None, None, None, "")."""
    for recul in (0, 1):
        f = fin - timedelta(days=recul)
        v = visites_7j(clics, lid, f, jours)
        if v is not None:
            return v, f - timedelta(days=jours - 1), f, "releve"
    m = (mesures or {}).get(str(lid)) if isinstance(mesures, dict) else None
    if isinstance(m, dict) and isinstance(m.get("v"), int) and _date(m.get("fin")) and (fin - _date(m["fin"])).days <= MEMOIRE_JOURS:
        return m["v"], _date(m.get("debut")), _date(m["fin"]), "memoire"
    return None, None, None, ""


# ------------------------------------------------------------------ catégories et notes des liens
def _chemin(info: dict):
    """Le chemin de l'URL d'un lien (« » pour la page principale), None si l'URL est inconnue."""
    u = _url_cle((info or {}).get("url"))
    if not u:
        return None
    return u.split("/", 1)[1] if "/" in u else ""


_NOTE_PAR_DEFAUT = object()                                              # categorie(info) sans note : la note du bouclage


def categorie(info: dict, note: str = _NOTE_PAR_DEFAUT) -> str:
    """attribue / libere / hors_clipping / page / non_attribue / desactive / supprime. 09/10 (revue CONTROLE) : « page » est
    définie POSITIVEMENT — note « Compte de @… », lien /ytb ou /fb, page principale (domaine seul), note qui ne parle pas de
    clipping ; un lien de clipping sans détenteur (note « Clipping Nina » jamais attribuée, lien suivi par le rapport sans uid, lien
    sans note sur un chemin) est « non_attribue » (avant : rangé en page, l'écart du bouclage restait à 0). `note` = la note GAML
    vivante si on l'a ; None = celle de clics.json.
    10/10 (vérification CONTROLE) : 1. « Clipping » n'importe où dans la note (« Chloé - Clipping Nina ») = un lien de clipping
    (« non_attribue », « libere » pour « … Clipping libre »), jamais une page ; 2. appelée SANS note (le Dashboard), la note est
    celle que le bouclage lit (_notes_par_defaut : note vivante du cache de l'onboarding, mémoire du contrôle, copie de clics.json),
    retrouvée par l'URL du lien : les lignes « Pages » et « Libérés » du Dashboard et les seaux du bouclage disent la même chose."""
    info = info if isinstance(info, dict) else {}
    if note is _NOTE_PAR_DEFAUT:
        note = _note_par_defaut(info)
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
    note = str(info.get("note") or "") if note is None else str(note or "")
    n = _n(note)
    if _RE_COMPTE_DE.match(n):
        return "page"
    if re.search(r"\bmetricool\b", n):
        return "hors_clipping"                                           # « Rianah Metricool 3 » sans le drapeau du bot
    m = _RE_CLIPPING.match(note)
    if m:
        return "libere" if _premier(m.group(1)) == "libre" else "non_attribue"
    if re.match(r"\s*clipping\b", n):
        return "non_attribue"                                            # « Clipping » sans prénom : un lien de clipping
    if info.get("suivi"):
        return "non_attribue"
    sans_ex = _RE_EX.sub(" ", n)                                         # 10/10 : « Chloé - Clipping Nina », « Lien clipping Nina »
    m = _RE_CLIPPING_PARTOUT.search(sans_ex)
    if m or _RE_MOT_CLIPPING.search(sans_ex):
        return "libere" if m and _premier(m.group(1)) == "libre" else "non_attribue"
    chemin = _chemin(info)
    dernier = (chemin or "").strip("/").split("/")[-1] if chemin else ""
    if chemin == "" or _n(dernier) in PAGES_CHEMINS or _n(str(info.get("slug") or "").strip("/")) in PAGES_CHEMINS:
        return "page"
    if n:
        return "page"                                                    # une note qui ne parle pas de clipping
    return "non_attribue"


_categorie = categorie                                                   # ancien nom (lot CONTROLE du 09/10)


def _notes(clics: dict, details=None, memo=None) -> tuple:
    """({lid: note GAML}, {lid: {note, copie}} à mémoriser). 09/10 (revue CONTROLE : C9 clignotait à 0 h et 7 h UTC) : la note
    vivante relue par l'onboarding (cache, même de la veille) ; sinon la dernière note vivante gardée par le contrôle (controle.json)
    tant que le bot n'a pas changé sa copie depuis ; sinon la copie de clics.json. Un cache plus vieux qu'un changement fait par le
    bot (synchroniser_notes : la copie a bougé, pas le cache) ne gagne pas sur la copie."""
    liens = {str(k): v for k, v in (((clics or {}).get("liens") or {}) if isinstance(clics, dict) else {}).items() if isinstance(v, dict)}
    memo = {str(k): v for k, v in memo.items()} if isinstance(memo, dict) else {}
    vives = {}
    for d in details or []:
        if isinstance(d, dict) and d.get("id") and d.get("note") is not None and str(d.get("note")).strip():
            vives[str(d["id"])] = str(d.get("note") or "")              # le dernier détail d'un id l'emporte
    notes, vus = {}, {}
    for lid in list(liens) + [l for l in vives if l not in liens]:
        note, vu = _note_lien(liens.get(lid), vives.get(lid), memo.get(lid) if lid in liens else None)
        if note is not None:
            notes[lid] = note
        if vu is not None:
            vus[lid] = vu
    return notes, vus


def _note_lien(info, vive=None, m=None) -> tuple:
    """(note, vu) d'UN lien — la règle de _notes, écrite une seule fois (10/10, vérification CONTROLE : le Dashboard et le bouclage
    lisent la même note). `info` = sa fiche de clics.json (None si inconnue), `vive` = la note du cache de l'onboarding, `m` = la
    mémoire du contrôle. La mémoire sert tant que le bot n'a pas changé sa copie depuis ; la note vive gagne, sauf si elle date
    d'avant un changement fait par le bot (synchroniser_notes : la copie a bougé, pas le cache). `vu` = ce qu'il faut mémoriser."""
    copie_brute = info.get("note") if isinstance(info, dict) else None
    copie = str(copie_brute or "")
    note = None if copie_brute is None else copie
    m = m if isinstance(m, dict) else None
    if info is not None and m is not None and m.get("note") is not None and str(m.get("copie") or "") == copie:
        note = str(m["note"])
    if vive is None or not str(vive).strip():
        return note, None
    vive = str(vive)
    if info is not None and m and str(m.get("note") or "") == vive and str(m.get("copie") or "") != copie:
        return note, None                                                # cache d'avant un changement du bot : la copie fait foi
    return vive, {"note": vive, "copie": copie}


_index_defaut = {"cle": None, "par_url": {}}                               # cache de _note_par_defaut (une lecture par état)


def _index_notes_defaut() -> dict:
    """{url : [(lid, note vive ou None, mémoire ou None)]} des liens dont le contrôle connaît une note autre que la copie : le cache
    de l'onboarding (id, url, note) et la mémoire du contrôle (controle.json « notes », l'URL y est gardée depuis le 10/10). Mêmes
    sources que _notes_par_defaut ; reconstruit seulement quand le cache ou controle.json changent (le Dashboard l'appelle par lien)."""
    cache = getattr(onboarding, "_details_gaml", None) or {}
    liste = cache.get("liens") if isinstance(cache, dict) else None
    f = _fichier("FICHIER_CONTROLE", "controle.json") if (_dep("lire_json") and _dossier() is not None) else None
    try:
        st = f.stat() if f is not None else None
        sig_f = (str(f), st.st_mtime_ns, st.st_size) if st is not None else (str(f), None, None)
    except OSError:
        sig_f = (str(f), None, None)
    cle = (id(liste), len(liste or ()), str(cache.get("jour") or ""), cache.get("liste_t"), sig_f)
    if _index_defaut["cle"] == cle:
        return _index_defaut["par_url"]
    memo = (_lire_etat().get("notes") or {}) if f is not None else {}
    memo = {str(k): v for k, v in memo.items() if isinstance(v, dict)} if isinstance(memo, dict) else {}
    par_url, vives = {}, {}
    for d in _details_en_cache():
        if d.get("note") is not None and str(d.get("note")).strip():
            vives[str(d["id"])] = (str(d.get("note") or ""), _url_cle(d.get("url")))
    for lid, (vive, u) in vives.items():
        if u:
            par_url.setdefault(u, []).append((lid, vive, memo.get(lid)))
    for lid, m in memo.items():
        u = _url_cle(m.get("url"))
        if u and lid not in vives:
            par_url.setdefault(u, []).append((lid, None, m))
    _index_defaut.update({"cle": cle, "par_url": par_url})
    return par_url


def _note_par_defaut(info: dict):
    """La note que le bouclage lirait pour ce lien (contrat C6(e), 10/10) : retrouvé par son URL dans le cache de l'onboarding ou
    la mémoire du contrôle, la règle de _note_lien ; None (= la copie de clics.json) quand rien d'autre n'est connu ou que deux
    liens de même URL ne disent pas la même chose."""
    u = _url_cle((info or {}).get("url"))
    if not u:
        return None
    try:
        cands = _index_notes_defaut().get(u) or []
    except Exception as erreur:                                          # noqa: BLE001 — jamais bloquer une catégorie
        journal.debug("Contrôle : notes par défaut illisibles (%s)", erreur)
        return None
    notes = {_note_lien(info, vive, m)[0] for _, vive, m in cands}
    return notes.pop() if len(notes) == 1 else None


# ------------------------------------------------------------------ le contexte d'un calcul
class _Ctx:
    def __init__(self, comptes, clics, onb, registre, membres_d, series_etat, etats, parcours, details, premiers_vus, maintenant,
                 memoire=None):
        self.comptes = comptes
        self.clics = clics
        self.liens = {str(k): v for k, v in ((clics.get("liens") or {}) if isinstance(clics, dict) else {}).items() if isinstance(v, dict)}
        self.onb = onb
        self.registre = registre
        self.membres = membres_d
        self.series = series_etat
        self.etats = etats
        self.parcours = parcours
        self.premiers_vus = premiers_vus if isinstance(premiers_vus, dict) else {}
        self.maintenant = maintenant
        self.fin = _hier_paris(maintenant)
        self.memoire = memoire if isinstance(memoire, dict) else {}
        self.mesures = self.memoire.get("mesures") if isinstance(self.memoire.get("mesures"), dict) else {}
        self.creatrices = onboarding.creatrices_connues(comptes)
        # 09/10 (revue CONTROLE) : la créatrice d'un lien se calcule comme dans liens_classeur (nom GAML, mémo, domaine), avec les
        # créatrices de la colonne Créatrice du classeur
        self.creatrices_brutes = {c["creatrice"] for c in comptes if c.get("creatrice")}
        # la résolution par prénom n'a de sens qu'avec un registre et la liste des membres (sinon tout serait « fantôme »)
        self.resolution = bool(registre) and bool(membres_d)
        self.signes = {uid for uid in membres_d if uid in registre}       # signés ET présents sur le serveur
        details = [d for d in details or [] if isinstance(d, dict) and d.get("id")]
        self.notes, _ = _notes(clics, details, self.memoire.get("notes"))
        self.noms_gaml = {str(d["id"]): str(d.get("nom") or d.get("name") or "") for d in details}
        self.groupes_gaml = {str(d["id"]): str(d.get("groupe") or "") for d in details}
        self.par_url = {}
        for lid, info in sorted(self.liens.items()):
            if _url_cle(info.get("url")):
                self.par_url.setdefault(_url_cle(info.get("url")), lid)
        for d in details:
            lid = str(d["id"])
            if _url_cle(d.get("url")) and lid in self.liens:
                self.par_url.setdefault(_url_cle(d.get("url")), lid)
        self.hotes_gaml = {_hote(u) for u in self.par_url} | {_hote(d.get("url")) for d in details}
        self.hotes_gaml.discard("")
        self.cats = {lid: categorie(info, self.notes.get(lid)) for lid, info in self.liens.items()}
        # 10/10 (vérification CONTROLE) : les liens suivis par le rapport (sans uid, ni libérés, ni hors clipping) — « le sien » sur
        # une ligne dont le Gérant porte le nom suivi (suivis_siens)
        self.suivis = sorted((lid, i) for lid, i in self.liens.items() if i.get("suivi") and not str(i.get("uid") or "")
                             and self.cats.get(lid) == "non_attribue")
        self.suivis_ids = {lid for lid, _ in self.suivis}
        self._resolus, self._cr, self._mots = {}, {}, {}
        self.cellules = {}                                               # url → lignes qui portent ce lien dans leur cellule
        for c in comptes:
            u = _url_cle(c.get("lien_gaml"))
            if u and c.get("handle"):
                self.cellules.setdefault(u, []).append(c)
        self.prenoms_membres = {_premier(nom) for nom in membres_d.values()} - {""}
        self.prenoms_registre = {_premier(f.get("prenom")) for f in registre.values() if isinstance(f, dict)} - {""}
        # un prénom du staff n'est « staff » que si aucun membre signé présent ne le porte (règle de membre_par_prenom)
        self.staff_purs = {p for p in STAFF if not any(_premier(self.membres[u]) == p for u in self.signes)}
        self.repreneurs = set()                                          # « Rianah Metricool 3 (ex-…) » → rianah
        for note in self.notes.values():
            m = _RE_METRICOOL.match(_n(note))
            if m:
                self.repreneurs.add(m.group(1))
        # 09/10 (revue CONTROLE, contrat C6(d)) : qui détient chaque @ d'après onboarding.json. `proprietaires` = toutes les fiches
        # (accès et codes 2FA : C4) ; `detenteurs_bruts` = la livraison la plus récente prime, sinon les fiches (comme
        # onboarding._proprietaires du lot CLICS) — c'est sur ces identifiants que se décide « le lien / le compte d'un autre ».
        self.proprietaires, fiches = {}, {}
        for uid, fiche in ((onb.get("clippers") or {}) if isinstance(onb, dict) else {}).items():
            if not isinstance(fiche, dict):
                continue
            hs = {_cle_compte(h) for h in fiche.get("comptes") or [] if isinstance(h, str)}
            hs |= {_cle_compte(a.get("handle")) for a in fiche.get("acces") or [] if isinstance(a, dict)}
            for h in hs - {""}:
                self.proprietaires.setdefault(h, set()).add(str(uid))
                fiches.setdefault(h, set()).add(str(uid))
        self.detenteurs_bruts = {h: set(u) for h, u in fiches.items()}
        for h, l in ((onb.get("livres") or {}) if isinstance(onb, dict) else {}).items():
            if isinstance(l, dict) and str(l.get("uid") or "") and _cle_compte(h):
                self.proprietaires.setdefault(_cle_compte(h), set()).add(str(l["uid"]))
                self.detenteurs_bruts[_cle_compte(h)] = {str(l["uid"])}
        self.ecartes = {_cle_compte(h): str((e or {}).get("uid") or "") for h, e in
                        ((onb.get("ecartes") or {}) if isinstance(onb, dict) else {}).items() if isinstance(e, dict)}

    # -- Gérant → membre
    def resoudre(self, gerant) -> tuple:
        """(genre, uid, candidats) : genre = libre | creatrice | metricool | staff | membre | ambigu | fantome | inconnu.
        Même règle que bot_discord.membre_par_prenom : membre SIGNÉ (registre) présent sur le serveur, dont le premier mot du
        pseudo (ou le pseudo entier) vaut le Gérant normalisé ; un seul, sinon personne. 09/10 (revue CONTROLE : Rianah, clippeuse
        signée, prise pour le staff — 7 faux bloquants et le conseil `!liberer`) : les membres d'abord ; le staff seulement quand
        aucun membre signé ne porte ce prénom (pour ne pas en faire un fantôme)."""
        g = _n(gerant)
        if g in self._resolus:
            return self._resolus[g]
        if g in onboarding.GERANTS_LIBRES:
            r = ("libre", "", [])
        elif onboarding.est_creatrice(gerant, self.creatrices):
            r = ("creatrice", "", [])
        elif "metricool" in g:
            r = ("metricool", "", [])
        else:
            cands = sorted(uid for uid in self.signes if _premier(self.membres[uid]) == g or _n(self.membres[uid]) == g) \
                if self.resolution else []
            if len(cands) == 1:
                r = ("membre", cands[0], cands)
            elif cands:
                r = ("ambigu", "", cands)
            elif _premier(g) in STAFF:
                r = ("staff", "", [])
            elif not self.resolution:
                r = ("inconnu", "", [])
            else:
                r = ("fantome", "", [])
        self._resolus[g] = r
        return r

    def _prenom_registre(self, uid) -> str:
        fiche = self.registre.get(str(uid or ""))
        return str(fiche.get("prenom") or "").strip() if isinstance(fiche, dict) else ""

    def nom(self, uid) -> str:
        """Le nom à afficher d'un membre : son pseudo (avant « - Créatrice »), sinon le prénom du registre."""
        uid = str(uid or "")
        if self.membres.get(uid):
            return _avant_separateur(self.membres[uid]).strip() or "?"
        p = self._prenom_registre(uid)
        return p.title() if p else "un membre parti"

    def mots_uid(self, uid) -> set:
        """Les mots du nom d'un membre (pseudo avant « - Créatrice », prénom du registre)."""
        uid = str(uid or "")
        if uid not in self._mots:
            self._mots[uid] = _mots_nom(self.membres.get(uid)) | _mots_nom(self._prenom_registre(uid))
        return self._mots[uid]

    def compatible(self, uid, gerant, strict: bool = False) -> bool:
        """Le membre `uid` peut-il être ce Gérant (un mot en commun) ? Nom inconnu : oui, sauf `strict`."""
        mots = self.mots_uid(uid)
        if not mots:
            return not strict
        return bool(mots & _mots_nom(gerant))

    def parti(self, uid) -> bool:
        """10/10 (vérification CONTROLE) : membre parti = ni sur le serveur, ni au registre des signés (le départ retire sa fiche du
        registre). Sans registre ou sans liste des membres, personne n'est dit parti (rien n'est décidé)."""
        uid = str(uid or "")
        return self.resolution and bool(uid) and uid not in self.membres and uid not in self.registre

    def detenteurs(self, c) -> set:
        """Contrat C6(d) : les uid qui détiennent la ligne d'après onboarding.json, compatibles avec le Gérant écrit (un Gérant changé
        à la main pour quelqu'un d'autre ne garde pas l'ancien détenteur) — même règle que onboarding._detenteurs du lot CLICS.
        10/10 (vérification CONTROLE : un compte encore livré à Paul, parti du serveur et du registre, puis donné à Lea à la main,
        faisait sortir « lien de Lea, pas de Lea » en bloquant et un C5 « un membre parti ») : un membre parti n'est plus détenteur
        de rien — son nom est inconnu, il passait pour compatible avec n'importe quel Gérant ; C4 dit que la fiche est à refaire."""
        h = _cle_compte(c.get("handle"))
        return {u for u in self.detenteurs_bruts.get(h, ()) if not self.parti(u) and self.compatible(u, c.get("gerant"))}

    def suivis_siens(self, c, cr: str = None) -> list:
        """10/10 (vérification CONTROLE : le lien « suivi » du rapport, que liens_classeur pose lui-même sur les lignes de son clipper,
        sortait en C6 / C9 / C10 importants avec le conseil `!lien`, qui l'aurait fait passer au clic) : les liens suivis par le rapport
        (sans uid, non libérés, ni effacés, ni désactivés, ni hors clipping) dont le nom suivi a un mot en commun avec le Gérant de la
        ligne ou avec le nom de son détenteur — même règle que onboarding._lien_d_un_autre (un lien suivi n'y est jamais « d'un
        autre ») ; `cr` : seulement ceux de cette créatrice (ou de créatrice inconnue)."""
        mots = _mots_nom(c.get("gerant"))
        for u in self.detenteurs(c):
            mots |= self.mots_uid(u)
        out = []
        for lid, i in self.suivis:
            if (mots & _mots_nom(i.get("suivi_nom") or "")) and (cr is None or self.cr_lien(lid) in ("", cr)):
                out.append((lid, i))
        return out

    def suivi_sien(self, c, lid) -> bool:
        return any(l == str(lid) for l, _ in self.suivis_siens(c))

    def proprio(self, c) -> str:
        """Le clipper de la ligne : son détenteur unique (onboarding.json), sinon le membre résolu par le prénom (règle du bot) ;
        '' pour une ligne sans Gérant, de créatrice, Metricool, ou dont les fiches se contredisent."""
        genre, uid, _ = self.resoudre(c.get("gerant"))
        if genre in ("libre", "creatrice", "metricool"):
            return ""
        dets = self.detenteurs(c)
        if len(dets) == 1:
            return next(iter(dets))
        if dets:
            return ""
        return uid if genre == "membre" else ""

    def lien_de(self, c, uid_l) -> tuple:
        """(verdict, gravité, raison) pour un lien attribué au membre `uid_l` posé sur la ligne `c` : « sien », « autre » ou
        « doute ». Contrat C6(d) : « autre » en bloquant seulement quand les identifiants le prouvent (détenteur de la ligne dans
        onboarding.json, ou ligne sans clipper : sans Gérant, Metricool, créatrice, staff) ; sans détenteur connu, un nom
        compatible laisse le bénéfice du doute et un nom incompatible n'est qu'important."""
        genre, uid, cands = self.resoudre(c.get("gerant"))
        uid_l = str(uid_l or "")
        if genre == "libre":
            return "autre", "bloquant", "ligne sans Gérant"
        if genre == "metricool":
            return "autre", "bloquant", "ligne Metricool"
        if genre == "creatrice":
            return "autre", "bloquant", "ligne de la créatrice"
        dets = self.detenteurs(c)
        if dets:
            if uid_l in dets:
                return "sien", "", ""
            return "autre", "bloquant", "fiche d'onboarding : " + ", ".join(self.nom(u) for u in sorted(dets))
        if (genre == "membre" and uid_l == uid) or (genre == "ambigu" and uid_l in cands) or genre == "inconnu":
            return "sien", "", ""
        if self.compatible(uid_l, c.get("gerant"), strict=True):
            if genre == "membre":
                return "doute", "info", (f"même prénom que le Gérant, que le bot rattache à {self.nom(uid)} ; aucune fiche "
                                         "d'onboarding pour départager")
            return "sien", "", ""
        if genre == "staff":
            return "autre", "bloquant", "ligne du staff"
        if not self.mots_uid(uid_l):
            return "doute", "info", "aucune fiche d'onboarding ni nom connu pour vérifier"
        return "autre", "important", "aucune fiche d'onboarding ne rattache ce compte : vu sur le seul nom"

    # -- liens
    def lid_url(self, u):
        return self.par_url.get(_url_cle(u))

    def cr_lien(self, lid) -> str:
        """La créatrice d'un lien (prénom normalisé), avec la règle de liens_classeur (onboarding._creatrice_du_lien) : premier mot
        du nom GAML, sinon la créatrice mémorisée à l'attribution, sinon le domaine. 09/10 (revue CONTROLE : « Clipping Marc »
        rangé chez « Clipping », lien que le bot pose lui-même sur les lignes Chloé déclaré faux) ; '' si inconnue."""
        lid = str(lid)
        if lid not in self._cr:
            info = self.liens.get(lid) or {}
            url = str(info.get("url") or "")
            cr = onboarding._creatrice_du_lien(self.noms_gaml.get(lid) or str(info.get("nom") or ""), info, url, self.creatrices_brutes)
            if not cr and self.groupes_gaml.get(lid):
                cr = onboarding._creatrice_du_lien(self.groupes_gaml[lid], info, url, self.creatrices_brutes)
            self._cr[lid] = cr or ""
        return self._cr[lid]

    def liens_de(self, uid) -> list:
        """Les liens d'un clipper que liens_classeur peut ranger (ni effacés, ni désactivés, ni hors clipping)."""
        return [(lid, i) for lid, i in self.liens.items() if str(i.get("uid") or "") == str(uid or "") and str(uid or "")
                and not i.get("supprime_gaml") and not i.get("desactive") and not i.get("hors_clipping")]

    def voulu(self, uid, cr):
        """(lid, info) du lien attendu d'un clipper pour une créatrice : comme onboarding.liens_classeur (le plus récent de la
        créatrice ; un lien unique sans créatrice connue vaut pour toutes)."""
        if not uid:
            return None
        siens = self.liens_de(uid)
        cands = [x for x in siens if self.cr_lien(x[0]) == cr] or (siens if len(siens) == 1 and not self.cr_lien(siens[0][0]) else [])
        return max(cands, key=lambda x: (str(x[1].get("depuis") or ""), x[0])) if cands else None

    def lien_du(self, uid, cr) -> bool:
        """Le lien est dû : parcours.lien_du pour la créatrice de son parcours ; sinon (ancien, autre créatrice) dès qu'il a un
        compte créé chez elle."""
        fiche = (self.parcours or {}).get(str(uid)) if isinstance(self.parcours, dict) else None
        if isinstance(fiche, dict) and int(fiche.get("etape", 0) or 0) >= 1 and _premier(fiche.get("creatrice")) in ("", cr):
            try:
                import parcours as _parcours                             # import tardif : parcours importe onboarding
                return bool(_parcours.lien_du(fiche))
            except Exception:                                            # noqa: BLE001
                pass
        return any(_cree(c) and _cr_ligne(c) == cr and self.proprio(c) == str(uid) for c in self.comptes)

    def porte(self, c, uid) -> bool:
        """La ligne est-elle au clipper `uid` (C7) : son détenteur, le membre résolu, un des homonymes, ou — sans détenteur connu —
        un Gérant au nom compatible (pseudo qui ne commence pas par le prénom : jamais « sans ligne » pour ça)."""
        uid = str(uid)
        if self.proprio(c) == uid:
            return True
        genre, u, cands = self.resoudre(c.get("gerant"))
        if genre in ("libre", "creatrice", "metricool"):
            return False
        if genre == "ambigu" and uid in cands:
            return True
        return not self.detenteurs(c) and genre in ("fantome", "staff", "inconnu") and self.compatible(uid, c.get("gerant"), strict=True)

    def visites(self, lid):
        return _visites_recentes(self.clics, lid, self.fin, self.mesures)


def _a(famille, gravite, texte, cle) -> dict:
    return {"famille": famille, "gravite": gravite, "texte": texte, "cle": cle}


def _remede_liberer(x: _Ctx, c: dict, genre: str, uid: str = "") -> str:
    """09/10 (revue CONTROLE : `!liberer` ne prend que les lignes dont le Gérant EST le prénom donné — conseillé sur une ligne sans
    Gérant, il ne faisait rien et le bloquant restait à vie) : le remède qui marche. Un Gérant provisoire neutre (JETON_LIBERER,
    personne ne s'appelle ainsi : rien n'est livré entre-temps), `!liberer … pool` (retire le compte de TOUTES les fiches et ses
    alias 2FA, revide le Gérant, garde l'Utilisation), puis le Gérant d'origine remis.
    10/10 (vérification CONTROLE : avec `pool`, le compte d'une clippeuse passait au vivier le temps de remettre son Gérant, et
    onboarding.disponibles l'offrait en PREMIER au prochain clipper — mot de passe et codes 2FA compris) : `pool` seulement pour un
    compte déjà sans Gérant (il est déjà au vivier, rien ne change). Sinon `!liberer` SANS `pool` (Utilisation « à mettre
    Metricool » : hors de disponibles() ; pour un compte « à créer », que `!liberer` ne change pas, l'écrire d'abord à la main),
    puis le Gérant d'origine remis AVANT l'Utilisation d'origine (jamais une fenêtre Gérant vide + Utilisation Clipper), puis
    `!onboarding @membre <Créatrice de la ligne>` (sans créatrice, celle du registre : la ligne d'un autre onglet n'était pas livrée)."""
    h, g = c.get("handle"), str(c.get("gerant") or "").strip()
    if not g:
        return (f"remède : écrire « {JETON_LIBERER} » dans sa colonne Gérant, puis `!liberer {JETON_LIBERER} {h} pool` (le Gérant "
                "redevient vide, l'Utilisation est gardée)")
    u = str(c.get("utilisation") or "").strip()
    gele = str(getattr(onboarding, "MENTION_LIBERE", "") or "à mettre Metricool")
    deja_gele = _n(u) == _n(gele)
    texte = "remède : " + ("" if deja_gele or not _a_creer(c) else f"écrire « {gele} » dans Utilisation, ")
    texte += f"écrire « {JETON_LIBERER} » dans sa colonne Gérant, puis `!liberer {JETON_LIBERER} {h}` (sans pool), puis remettre « {g} » dans Gérant"
    if not deja_gele:
        texte += f" puis « {u} » dans Utilisation" if u else " puis vider Utilisation"
    # la livraison n'est jamais automatique (commandes `!onboarding`, `!creatrice`, reprise) : la commande est donnée
    if genre == "membre" and uid and _n(u) == "clipper":
        texte += ", et " + _remede_onboarding(x, c, uid)
    return texte


def _remede_onboarding(x: _Ctx, c: dict, uid: str) -> str:
    """10/10 (vérification CONTROLE) : `!onboarding @membre <Créatrice de la ligne>` — onboarding.livrer prend les lignes dont le Gérant
    est son prénom chez CETTE créatrice, et complète jusqu'à COMPTES_PAR_CLIPPER avec des comptes libres : dit quand ça arrivera."""
    cr = (str(c.get("creatrice") or "").split() or [""])[0]
    nom = x.nom(uid)
    if not cr:
        return f"`!onboarding @{nom} <Créatrice>` (colonne Créatrice vide : la remplir d'abord)"
    k = int(getattr(onboarding, "COMPTES_PAR_CLIPPER", 3) or 3)
    n = sum(1 for c2 in x.comptes if _n(c2.get("gerant")) == _n(c.get("gerant")) and _n(c2.get("utilisation")) == "clipper"
            and _n(c2.get("creatrice")).startswith(_n(cr)) and not _ban(c2))
    return f"`!onboarding @{nom} {cr}`" + (f" (lui réserve aussi {k - n} compte(s) libre(s))" if n < k else "")


# ------------------------------------------------------------------ les familles
def _c1(x: _Ctx) -> list:
    out = []
    for c in x.comptes:
        if not c.get("handle") or x.resoudre(c.get("gerant"))[0] != "libre" or not _cree(c):
            continue
        cle = f"C1|{_n(c.get('onglet'))}|{_cle_compte(c['handle'])}"
        if _n(c.get("utilisation")).startswith("a mettre metricool"):
            vu = _date(x.premiers_vus.get(cle))
            age = f" · signalé depuis le {vu.strftime('%d/%m')} ({(x.maintenant.date() - vu).days} j)" if vu else ""
            out.append(_a("C1", "important", f"{_ou(c)} · @{c['handle']} ({c.get('etat')}) : compte créé rendu, « à mettre Metricool »"
                                              f" — aucune ligne ne le suit{age}", cle))
        else:
            out.append(_a("C1", "info", f"{_ou(c)} · @{c['handle']} ({c.get('etat')}) : compte créé sans Gérant (au vivier, prêt pour le "
                                        "prochain clipper)", cle))
    return out


def _nm_resolution(x: _Ctx) -> list:
    """Sans registre des signés ou sans liste des membres du serveur, C2, C3, C4, C5 et C7 ne peuvent rien juger : elles le disent."""
    if x.resolution:
        return []
    manque = "registre des signés" if not x.registre else "liste des membres du serveur"
    return [_non_mesure(f, f"{manque} indisponible, {FAMILLES[f].lower()} non vérifié") for f in ("C2", "C3", "C4", "C5", "C7")]


def _c2_c3(x: _Ctx) -> list:
    if not x.resolution:
        return []
    fantomes, ambigus = {}, {}
    for c in x.comptes:
        if not c.get("handle"):
            continue
        genre, _, cands = x.resoudre(c.get("gerant"))
        if genre == "fantome":
            fantomes.setdefault((c.get("onglet") or "?", _n(c.get("gerant"))), []).append(c)
        elif genre == "ambigu":
            ambigus.setdefault(_n(c.get("gerant")), []).append((c, cands))
        elif genre == "metricool":
            rep = re.split(r"[\s(]", _n(c.get("gerant")))[0]
            if rep and rep != "metricool" and rep not in STAFF | x.prenoms_membres | x.prenoms_registre | x.repreneurs:
                fantomes.setdefault((c.get("onglet") or "?", _n(c.get("gerant"))), []).append(c)
    out = []
    for (onglet, g), cs in sorted(fantomes.items()):
        brut = str(cs[0].get("gerant") or "").strip()
        if "metricool" in g:
            quoi = "repreneur Metricool inconnu (ni membre, ni staff, ni note GAML « … Metricool »)"
        else:
            # 09/10 (revue CONTROLE) : un membre signé au nom compatible existe (pseudo « 🌸 Paul - Sophie », « Jean Marc ») : le bot
            # ne le retrouve pas par le prénom, ce qui bloque les livraisons et les liens par prénom — le dire tel quel
            proches = [u for u in sorted(x.signes) if x.compatible(u, brut, strict=True)]
            quoi = ((f"le bot ne retrouve pas « {brut} » par le prénom : le pseudo " + ", ".join(f"« {x.membres[u]} »" for u in proches[:3])
                     + " ne commence pas par ce prénom (renommer le pseudo « Prénom - Créatrice » ou écrire le Gérant comme le pseudo)")
                    if proches else "aucun membre signé de ce prénom sur le serveur (parti, prénom écrit autrement ?)")
        out.append(_a("C2", "important", f"{onglet} · Gérant « {brut} » ({len(cs)} ligne(s) : " + ", ".join(f"@{c['handle']}" for c in cs[:4])
                      + (" …" if len(cs) > 4 else "") + f") : {quoi}", f"C2|{_n(onglet)}|{g}"))
    for g, paires in sorted(ambigus.items()):
        cands = paires[0][1]
        onglets = sorted({c.get("onglet") or "?" for c, _ in paires})
        out.append(_a("C3", "bloquant", f"Gérant « {str(paires[0][0].get('gerant') or '').strip()} » : {len(cands)} membres signés de ce "
                                        f"prénom ({', '.join(x.membres.get(u, '?') for u in cands)}) — {len(paires)} ligne(s) "
                                        f"({', '.join(onglets)}) attribuables à personne (livraisons, liens et clics mêlés)", f"C3|{g}"))
    return out


def _c4(x: _Ctx) -> list:
    """09/10 (revue CONTROLE, contrat C6(d)) : « encore chez un autre » se décide sur les uid des fiches d'onboarding : un détenteur
    présent dont le nom n'a aucun mot en commun avec le Gérant (bloquant, avec un remède qui marche) ; un détenteur au nom compatible
    autre que le membre résolu = homonymes à départager (important, sans commande) ; jamais `!liberer` conseillé sur la ligne d'un
    membre résolu."""
    if not x.resolution:
        return []
    if not isinstance((x.onb or {}).get("clippers") if isinstance(x.onb, dict) else None, dict):
        return [_non_mesure("C4", "fiches d'onboarding (onboarding.json) illisibles : propriétaires des comptes non vérifiés")]
    out = []
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        if not h:
            continue
        genre, uid, _ = x.resoudre(c.get("gerant"))
        if genre in ("fantome", "ambigu", "inconnu"):
            continue                                                     # déjà C2 / C3 : pas de propriétaire attendu à comparer
        cle = f"C4|{_n(c.get('onglet'))}|{h}"
        g = str(c.get("gerant") or "").strip()
        proprios = x.proprietaires.get(h, set())
        presents = sorted(o for o in proprios if o != uid and o in x.membres)
        etrangers = [o for o in presents if not x.compatible(o, g, strict=True)]
        homonymes = [o for o in presents if o not in etrangers]
        if genre == "membre":
            if x.ecartes.get(h) == uid:
                out.append(_a("C4", "important", f"{_ou(c)} · {_qui(c)} : écarté à la livraison (homonyme possible d'un ancien), jamais "
                                                 f"livré — {_remede_onboarding(x, c, uid)} si c'est bien le sien, sinon vider sa colonne "
                                                 "Gérant", cle))
            elif etrangers:
                # 10/10 : texte court — le remède (la partie utile) tient dans les 300 caractères du salon admin et du Dashboard
                out.append(_a("C4", "bloquant", f"{_ou(c)} · {_qui(c)} : accès et codes 2FA encore dans la fiche de "
                                                f"{', '.join(x.nom(o) for o in etrangers)}" + ("" if uid in proprios else ", jamais livré au Gérant")
                              + " — " + _remede_liberer(x, c, genre, uid), cle))
            elif homonymes:
                out.append(_a("C4", "important", f"{_ou(c)} · {_qui(c)} : dans la fiche de {', '.join(x.nom(o) for o in homonymes)} (même "
                                                 f"prénom que le Gérant) alors que le bot rattache « {g} » à {x.nom(uid)} : homonymes à "
                                                 "départager (pseudo ou Gérant écrit en entier)", cle))
            elif uid not in proprios and _n(c.get("utilisation")) == "clipper":
                # 10/10 (vérification CONTROLE) : un compte encore livré à un membre parti (serveur et registre) le dit, avec la commande
                partis = any(x.parti(o) for o in proprios)
                out.append(_a("C4", "important", f"{_ou(c)} · {_qui(c)} : au nom de {x.nom(uid)} mais absent de sa fiche d'onboarding "
                                                 "(jamais livré" + (" ; encore livré à un membre parti (onboarding.json)" if partis else "")
                                                 + ") — " + _remede_onboarding(x, c, uid), cle))
        elif etrangers:
            quoi = {"libre": "compte sans Gérant", "metricool": "compte Metricool", "staff": "compte du staff",
                    "creatrice": "compte de la créatrice"}[genre]
            out.append(_a("C4", "bloquant", f"{_ou(c)} · {_qui(c)} : {quoi} encore dans la fiche de "
                                            f"{', '.join(x.nom(o) for o in etrangers)} (accès et codes 2FA) — " + _remede_liberer(x, c, genre),
                          cle))
    return out


def _c5(x: _Ctx) -> list:
    if not x.resolution:
        return []
    paires = {}
    for c in x.comptes:
        if not _vivante(c) or _n(c.get("utilisation")) not in ("clipper", ""):
            continue
        uid = x.proprio(c)                                               # contrat C6(d) : le détenteur d'abord, sinon le prénom
        if uid and uid in x.signes:                                      # 10/10 : jamais un membre parti ou sorti du registre
            paires.setdefault((uid, _cr_ligne(c)), []).append(c)
    out = []
    for (uid, cr), cs in sorted(paires.items()):
        if not cr or x.voulu(uid, cr) or not x.lien_du(uid, cr):
            continue
        if any(x.suivis_siens(c, cr) for c in cs):
            continue                                                     # 10/10 : son lien suivi par le rapport (payé par le rapport)
        out.append(_a("C5", "important", f"{cs[0].get('onglet') or cr.title()} · {x.nom(uid)} : lien GAML dû (compte privé ouvert ou "
                                         f"comptes créés) mais aucun lien {cr.title()} à son nom dans le bot", f"C5|{uid}|{cr}"))
    return out


def _c6(x: _Ctx) -> list:
    out, sans_colonne = [], {}
    for c in x.comptes:
        if not c.get("handle"):
            continue
        cellule = str(c.get("lien_gaml") or "").strip()
        genre, uid, cands = x.resoudre(c.get("gerant"))
        cle = f"C6|{_n(c.get('onglet'))}|{_cle_compte(c['handle'])}"
        if not cellule:
            # 09/10 (revue CONTROLE : « lien pas assigné au compte » passé sous silence) : une ligne créée d'un clipper qui a son lien
            # pour cette créatrice, cellule vide — ses clics ne sont comptés sur aucun compte. Onglet sans la colonne : une fois.
            if genre in ("libre", "creatrice", "metricool") or not _cree(c):
                continue
            proprio = x.proprio(c)
            if x.resolution and proprio not in x.signes:
                proprio = ""                                             # 10/10 : jamais le lien d'un membre parti ou sorti
            v = x.voulu(proprio, _cr_ligne(c)) if proprio else None
            if not v:
                continue
            if _sans_colonne_lien(c.get("onglet")):
                sans_colonne.setdefault(c.get("onglet") or "?", []).append(c)
                continue
            out.append(_a("C6", "important", f"{_ou(c)} · {_qui(c)} : cellule vide alors que son lien « {_slug(v[1].get('url'))} » existe "
                                             "(ses clics ne sont comptés sur aucun compte)", cle))
            continue
        tete = f"{_ou(c)} · {_qui(c)} : cellule « {_slug(cellule)} »"
        lid = x.lid_url(cellule)
        if not lid:
            if _hote(cellule) in x.hotes_gaml:
                out.append(_a("C6", "info", f"{tete} = lien GAML inconnu du bot (jamais relevé)", cle))
            else:
                grav = "important" if genre in ("membre", "ambigu", "fantome", "libre") else "info"
                out.append(_a("C6", grav, f"{tete} n'est pas un lien GAML (clics non mesurés)", cle))
            continue
        info = x.liens[lid]
        cat = x.cats[lid]
        clipper = genre in ("membre", "ambigu", "fantome", "inconnu")
        probleme, grav = "", "bloquant"
        if cat in ("supprime", "desactive"):
            probleme = "lien effacé de GAML" if cat == "supprime" else "lien désactivé dans GAML (visites perdues)"
            grav = "important" if genre == "libre" else "bloquant"
        elif genre == "libre":
            probleme, grav = "ligne sans Gérant qui garde un lien (le regroupement lui redonnerait un Gérant)", "important"
        elif cat == "attribue":
            uid_l = str(info.get("uid"))
            verdict, g_v, raison = x.lien_de(c, uid_l)
            if verdict == "autre":
                if genre in ("metricool", "creatrice", "staff") and not x.detenteurs(c):
                    probleme = f"lien du clipper {x.nom(uid_l)} sur une {raison}"
                else:
                    probleme = f"lien de {x.nom(uid_l)}, pas de {str(c.get('gerant')).strip()} ({raison})"
                grav = g_v
            elif verdict == "doute":
                probleme, grav = f"lien de {x.nom(uid_l)} ({raison})", "info"
            elif x.cr_lien(lid) and _cr_ligne(c) and x.cr_lien(lid) != _cr_ligne(c):
                probleme = f"son lien {x.cr_lien(lid).title()} sur une ligne {_cr_ligne(c).title()}"
            else:
                v = x.voulu(uid_l, _cr_ligne(c))
                if v and v[0] != lid:
                    probleme, grav = f"pas son lien le plus récent (attendu « {_slug(v[1].get('url'))} »)", "important"
        elif cat == "libere":
            ancien = str(info.get("ancien") or "?")
            probleme, grav = f"lien libéré (ex-{ancien}) : ses visites sont celles d'un autre", ("bloquant" if clipper else "important")
        elif cat == "hors_clipping":
            note = str(info.get("hors_clipping") or x.notes.get(lid) or "")
            if genre == "metricool":
                rep = re.split(r"[\s(]", _n(c.get("gerant")))[0]
                if rep and f"{rep} metricool" not in _n(x.notes.get(lid) or note):
                    probleme, grav = f"lien hors clipping « {note} », pas un lien {rep.title()} Metricool", "important"
            elif clipper:
                probleme = f"lien hors clipping « {note} » sur une ligne de clipper"
            else:
                probleme, grav = f"lien hors clipping « {note} »", "important"
        elif cat == "non_attribue" and lid in x.suivis_ids:
            # 10/10 (vérification CONTROLE) : un lien suivi par le rapport, que liens_classeur pose lui-même sur les lignes de son
            # clipper, est « le sien » quand le nom suivi est celui du Gérant (même règle que onboarding._lien_d_un_autre) ; jamais
            # le conseil `!lien` (il le ferait passer au clic). Sur la ligne d'un autre nom : important, vu sur le seul nom (C6(d)).
            nom_s = str(info.get("suivi_nom") or "?").strip()
            if genre not in ("metricool", "creatrice") and x.suivi_sien(c, lid):
                if x.cr_lien(lid) and _cr_ligne(c) and x.cr_lien(lid) != _cr_ligne(c):
                    probleme, grav = f"son lien {x.cr_lien(lid).title()} (suivi par le rapport) sur une ligne {_cr_ligne(c).title()}", "important"
            elif clipper or genre == "staff":
                probleme, grav = (f"lien suivi par le rapport pour « {nom_s} », pas pour « {str(c.get('gerant')).strip()} » (vu sur le seul "
                                  "nom, aucun uid)"), "important"
            else:
                probleme, grav = f"lien suivi par le rapport pour « {nom_s} » sur une ligne " + {
                    "creatrice": "de la créatrice", "metricool": "Metricool"}.get(genre, genre), "important"
        elif cat == "non_attribue":
            # 09/10 (revue CONTROLE) : un lien de clipping sans détenteur dans le bot (jamais attribué, suivi du rapport) n'est pas une
            # page de la créatrice ; aucun uid : rien à décider sur « un autre clipper » (contrat C6(d)), ses visites ne sont à personne
            note = str(x.notes.get(lid) or "").strip()
            quoi = f"lien jamais attribué dans le bot{f' (note « {note} »)' if note else ''} : ses visites ne sont payées à personne"
            probleme, grav = (quoi + " — `!lien @clipper <url>`" if clipper else quoi + " (ligne " + {
                "creatrice": "de la créatrice", "metricool": "Metricool", "staff": "du staff"}.get(genre, genre) + ")"), "important"
        else:                                                            # page de la créatrice : note « Compte de @… », /ytb, /fb
            if clipper:
                probleme = "page de la créatrice sur une ligne de clipper (les visites de la créatrice comptées pour le clipper)"
            elif genre == "creatrice":
                m = _RE_COMPTE_DE.match(_n(x.notes.get(lid)))
                if m and _compact(m.group(1)) != _compact(c.get("handle")):
                    probleme, grav = f"lien du compte @{m.group(1)} (note GAML) sur la ligne d'un autre compte de la créatrice", "important"
        if probleme:
            out.append(_a("C6", grav, f"{tete} = {probleme}", cle))
    for onglet, cs in sorted(sans_colonne.items()):
        out.append(_a("C6", "important", f"{onglet} : onglet sans colonne « Lien GAML associé » — {len(cs)} ligne(s) de clippers qui ont "
                                         "un lien n'en affichent aucun (" + ", ".join(f"@{c['handle']}" for c in cs[:4])
                      + (" …" if len(cs) > 4 else "") + ")", f"C6|{_n(onglet)}|sans_colonne"))
    return out


def _c7(x: _Ctx) -> list:
    if not x.resolution:
        return []
    out = []
    for lid, info in sorted(x.liens.items()):
        uid = str(info.get("uid") or "")
        if not uid or x.cats[lid] != "attribue":
            continue
        cr = x.cr_lien(lid)
        tete = f"{(cr or '?').title()} · lien « {_slug(info.get('url'))} »"
        if uid not in x.registre:
            out.append(_a("C7", "important", f"{tete} attribué à {x.nom(uid)}, absent du registre des signés (parti ?) : à libérer",
                          f"C7|{lid}"))
            continue
        # contrat C6(d) : la ligne est au clipper par son uid (détenteur), le prénom résolu ou un nom compatible — jamais « aucune
        # ligne » parce que son pseudo ne commence pas par son prénom
        lignes = [c for c in x.comptes if _vivante(c) and (not cr or _cr_ligne(c) == cr) and x.porte(c, uid)]
        if not lignes:
            out.append(_a("C7", "important", f"{tete} de {x.nom(uid)} : aucune ligne vivante à son nom chez {(cr or '?').title()} "
                                             "(ses visites ne sont comptées sur aucun compte)", f"C7|{lid}"))
    return out


def _c8(x: _Ctx) -> list:
    """09/10 (revue CONTROLE : l'anomalie disparaissait chaque nuit entre minuit et le relevé de J-1, un faux « 0 anomalie » partait,
    puis elle revenait) : les 7 derniers jours COMPLETS du lien (fenêtre reculée d'un jour si J-1 n'est pas encore relevé), sinon la
    dernière mesure gardée ; un lien qu'on ne peut pas mesurer est dit « non mesuré », jamais tu. 09/10 (revue CONTROLE) : aussi les
    liens de clipping jamais attribués (« non_attribue ») portés par aucune ligne — ce sont eux qui font l'écart du bouclage ; sans
    ça, le salon admin pouvait écrire « chaque lien est attribué » à côté d'un écart."""
    out, inconnus = [], []
    for lid, info in sorted(x.liens.items()):
        cat = x.cats[lid]
        if cat not in ("libere", "hors_clipping", "non_attribue") or x.cellules.get(_url_cle(info.get("url"))):
            continue
        v, debut, fin, source = x.visites(lid)
        if v is None:
            inconnus.append(lid)
            continue
        if not v:
            continue                                                     # 0 mesuré : rien à dire
        periode = f"du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')}" if debut and fin else "sur 7 j"
        if source == "memoire":
            periode += " (dernière mesure, relevé incomplet depuis)"
        if cat == "libere":
            quoi, suite = f"libéré (ex-{info.get('ancien') or '?'})", ""
        elif cat == "hors_clipping":
            quoi, suite = f"hors clipping « {info.get('hors_clipping') or x.notes.get(lid) or ''} »", ""
        elif lid in x.suivis_ids:
            # 10/10 (vérification CONTROLE) : un lien suivi par le rapport sans ligne au nom suivi — jamais `!lien` (il passerait au clic)
            quoi = f"suivi par le rapport pour « {str(info.get('suivi_nom') or '?').strip()} »"
            suite = " : aucune ligne à ce nom (Gérant écrit autrement ?)"
        else:
            note = str(x.notes.get(lid) or "").strip()
            quoi = "jamais attribué dans le bot" + (f" (note « {note} »)" if note else " (sans note)")
            suite = (" : payées à personne — `!lien @clipper <url>` si c'est le lien d'un clipper, note « Compte de @… » si c'est une "
                     "page de la créatrice")
        out.append(_a("C8", "info" if cat == "libere" else "important",
                      f"{(x.cr_lien(lid) or '?').title()} · lien « {_slug(info.get('url'))} » {quoi} : {v} visite(s) payable(s) {periode}, "
                      "portées par aucune ligne" + suite, f"C8|{lid}"))
    if inconnus:
        out.append(_non_mesure("C8", f"{len(inconnus)} lien(s) libéré(s), hors clipping ou jamais attribué(s) sans 7 jours complets de "
                                     "relevé (" + ", ".join(_slug(x.liens[l].get("url")) for l in inconnus[:3])
                                     + (" …" if len(inconnus) > 3 else "") + ") : leurs visites ne sont pas connues",
                               [f"C8|{lid}" for lid in inconnus]))
    return out


def _c9(x: _Ctx) -> list:
    out = []
    for lid, info in sorted(x.liens.items()):
        if lid not in x.notes or info.get("supprime_gaml"):
            continue
        note = str(x.notes.get(lid) or "").strip()
        if not note:
            continue
        m = _clipping_de(note)                                           # 10/10 : « Chloé - Clipping Nina » aussi
        prenom_note = _premier(m.group(1)) if m else ""
        uid = str(info.get("uid") or "")
        tete = f"{(x.cr_lien(lid) or '?').title()} · lien « {_slug(info.get('url'))} » note « {note} »"
        probleme = ""
        if uid:
            qui = x.nom(uid)
            mots = x.mots_uid(uid)
            # le nom porté par la note, sans sa parenthèse « (ex-Paul) » : un ancien détenteur cité n'est pas un accord
            nom_note = re.split(r"[(\[]", m.group(1))[0].strip() if m else ""
            if not m:
                probleme = f"attribué à {qui} mais la note n'est plus « Clipping … » (sorti du clipping à la main ?)"
            elif prenom_note == "libre":
                probleme = f"attribué à {qui} mais noté libre dans GAML"
            elif mots and not (_mots_nom(nom_note) & mots):
                # contrat C6(d) : comparé à TOUS les mots du nom du membre (pseudo « 🌸 Paul - Sophie », « Jean-Marc »), pas au
                # premier mot de son pseudo
                probleme = f"attribué à {qui} : l'app et le rapport le donnent à « {nom_note or m.group(1).strip()} »"
        elif info.get("libere") and not info.get("hors_clipping") and m and prenom_note != "libre":
            ancien = _premier(re.sub(r"^\s*clipping\s+", "", _n(info.get("ancien")))) if info.get("ancien") else ""
            if prenom_note != ancien:
                probleme = f"libéré dans le bot (ex-{info.get('ancien') or '?'}) mais la note le donne à « {m.group(1).strip()} »"
        elif lid in x.suivis_ids:
            # 10/10 (vérification CONTROLE) : un lien suivi par le rapport est attribué au nom suivi (jamais `!lien`, il passerait
            # au clic) ; seul un désaccord entre la note et ce nom est signalé
            nom_s = str(info.get("suivi_nom") or "").strip()
            nom_note = re.split(r"[(\[]", m.group(1))[0].strip() if m else ""
            if m and _mots_nom(nom_s) and not (_mots_nom(nom_note) & _mots_nom(nom_s)):
                probleme = f"suivi par le rapport pour « {nom_s} » mais la note le donne à « {nom_note or m.group(1).strip()} »"
        elif x.cats[lid] == "non_attribue" and m and prenom_note not in x.staff_purs | {"libre"}:
            probleme = "« Clipping … » jamais attribué par le bot (homonymes ou prénom inconnu : `!lien @clipper <url>`)"
        if probleme:
            out.append(_a("C9", "important", f"{tete} : {probleme}", f"C9|{lid}"))
    return out


def _c10(x: _Ctx) -> list:
    if not isinstance(x.etats, dict):
        return [_non_mesure("C10", "états du scan illisibles (etats_comptes.json) : liens en bio non vérifiés")]
    bios = x.etats.get("bios") or {}
    limite = x.maintenant.date() - timedelta(days=BIO_JOURS)
    if not any(isinstance(b, dict) and (_date(b.get("jour")) or date.min) >= limite for b in bios.values()):
        return [_non_mesure("C10", f"aucune bio Instagram relevée depuis {BIO_JOURS} jours : liens en bio non vérifiés")]
    out = []
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        bio = bios.get(h) if h else None
        if not isinstance(bio, dict) or (_date(bio.get("jour")) or date.min) < limite:
            continue
        genre, uid, cands = x.resoudre(c.get("gerant"))
        cr = _cr_ligne(c)
        proprio = x.proprio(c)
        urls = [str(u) for u in bio.get("liens") or [] if str(u or "").strip()]
        gaml = [(u, x.lid_url(u)) for u in urls if x.lid_url(u)]
        autres = [u for u in urls if not x.lid_url(u)]
        probs = []
        for u, lid in gaml:
            info = x.liens[lid]
            cat = x.cats[lid]
            uid_l = str(info.get("uid") or "")
            if cat in ("supprime", "desactive"):
                probs.append(("info" if genre == "libre" else "bloquant", f"lien « {_slug(u)} » {'effacé' if cat == 'supprime' else 'désactivé'} "
                                                                           "dans GAML (visites perdues)"))
            elif cat == "attribue":
                verdict, g_v, raison = x.lien_de(c, uid_l)
                if verdict == "sien":
                    if x.cr_lien(lid) and cr and x.cr_lien(lid) != cr:
                        probs.append(("important", f"son lien {x.cr_lien(lid).title()} « {_slug(u)} » sur un compte {cr.title()}"))
                elif verdict == "autre":
                    probs.append((g_v, f"lien de {x.nom(uid_l)} « {_slug(u)} » : ses visites lui sont payées depuis un compte qui "
                                       f"n'est pas le sien ({raison})"))
                else:
                    probs.append(("info", f"lien de {x.nom(uid_l)} « {_slug(u)} » ({raison})"))
            elif cat == "libere":
                probs.append(("info" if genre == "libre" else "important",
                              f"lien libéré « {_slug(u)} » (ex-{info.get('ancien') or '?'}) : visites payées à personne"))
            elif cat == "hors_clipping":
                if genre in ("membre", "ambigu") or proprio:
                    probs.append(("important", f"lien hors clipping « {_slug(u)} » au lieu du sien"))
            elif cat == "non_attribue" and lid in x.suivis_ids:
                # 10/10 (vérification CONTROLE) : le lien suivi par le rapport au nom du Gérant est le sien
                if genre not in ("metricool", "creatrice") and x.suivi_sien(c, lid):
                    if x.cr_lien(lid) and cr and x.cr_lien(lid) != cr:
                        probs.append(("important", f"son lien {x.cr_lien(lid).title()} « {_slug(u)} » (suivi par le rapport) sur un compte "
                                                   f"{cr.title()}"))
                elif genre in ("membre", "ambigu", "fantome", "staff") or proprio:
                    probs.append(("important", f"lien suivi par le rapport pour « {str(x.liens[lid].get('suivi_nom') or '?').strip()} » "
                                               f"« {_slug(u)} » au lieu du sien (vu sur le seul nom)"))
            elif cat == "non_attribue":
                if genre in ("membre", "ambigu", "fantome") or proprio:
                    probs.append(("important", f"lien jamais attribué « {_slug(u)} » au lieu du sien (visites payées à personne)"))
            elif genre in ("membre", "ambigu") or proprio:
                probs.append(("important", f"page de la créatrice « {_slug(u)} » au lieu de son lien (clics non attribuables)"))
        if proprio and not gaml:
            # un compte de croissance qui renvoie vers le compte privé (lien Instagram) est dans la règle : jamais signalé
            externes = [u for u in autres if not _RE_INSTAGRAM.search(_hote(u))]
            if onboarding._est_prive(c) and x.voulu(proprio, cr) and x.lien_du(proprio, cr):
                probs.append(("important", "compte privé sans lien GAML dans le champ Liens de la bio"
                                           + (" (lien collé dans le texte, pas cliquable)" if bio.get("texte") else "")
                                           + (f" (renvoie vers « {_hote(externes[0])} »)" if externes else "")))
            elif externes:
                probs.append(("important", f"bio vers « {_hote(externes[0])} » au lieu de son lien GAML (clics non mesurés)"))
        if not probs:
            continue
        grav = min((g for g, _ in probs), key=GRAVITES.index)
        out.append(_a("C10", grav, f"{_ou(c)} · {_qui(c)} · bio du {(_date(bio.get('jour')) or x.maintenant.date()).strftime('%d/%m')} : "
                                   + " ; ".join(t for _, t in probs), f"C10|{_n(c.get('onglet'))}|{h}"))
    return out


def _c11(x: _Ctx) -> list:
    par_handle = {}
    for c in x.comptes:
        if c.get("handle"):
            par_handle.setdefault(_cle_compte(c["handle"]), []).append(c)
    out = []
    for h, cs in sorted(par_handle.items()):
        # 09/10 (revue CONTROLE) : le marqueur d'onboarding._sans_doublons est posé sur CHAQUE ligne gardée : une ligne écartée se
        # compte une fois (avant : « sur 4 lignes » pour 3, la ligne écartée citée deux fois)
        ecartes = sorted({(str(e[0]), str(e[1])) for c in cs for e in c.get("doublons_ecartes") or []
                          if isinstance(e, (list, tuple)) and len(e) >= 2})
        if len(cs) < 2 and not ecartes:
            continue
        ou = [f"{c.get('onglet') or '?'} l. {c.get('ligne') or '?'} ({str(c.get('gerant') or '').strip() or 'sans Gérant'})" for c in cs]
        ou += [f"{o} l. {l} (écartée : invisible au bot)" for o, l in ecartes]
        par_onglet = {}
        for c in cs:
            par_onglet[c.get("onglet") or "?"] = par_onglet.get(c.get("onglet") or "?", 0) + 1
        suites = [f"{k} fois dans l'onglet {o} : une seule ligne doit rester" for o, k in sorted(par_onglet.items()) if k >= 2]
        if ecartes:
            suites.append("la ligne écartée n'est ni lue, ni scannée, ni comptée" if len(ecartes) == 1 else
                          "les lignes écartées ne sont ni lues, ni scannées, ni comptées")
        out.append(_a("C11", "bloquant", f"@{cs[0]['handle']} sur {len(ou)} lignes : " + " · ".join(ou) + " — " + " ; ".join(suites),
                      f"C11|{h}"))
    return out


def _c12(x: _Ctx) -> list:
    etats = x.etats if isinstance(x.etats, dict) else {}
    historique = etats.get("historique") or {}
    non_lus = etats.get("non_lus") or {}
    dp = etats.get("dernier_passage") or {}
    series = ((x.series or {}).get("comptes") or {}) if isinstance(x.series, dict) else {}
    alias = ((x.series or {}).get("alias") or {}) if isinstance(x.series, dict) else {}
    budget = etats.get("apify_budget") if isinstance(etats.get("apify_budget"), dict) else {}
    coupe = bool(budget.get("coupe"))
    out = []
    if coupe:
        # contrat C6(a) (budget Apify plafonné à APIFY_BUDGET_MOIS, décision de Gaëtan du 09/10) : plus aucun scan, le contrôle le dit
        fin_c = _date(budget.get("cycle_fin"))
        out.append(_non_mesure("C12", f"budget Apify du mois atteint ({_usd(budget.get('usage_usd'))} / {_usd(budget.get('budget_usd') or 25)}) : "
                                      "plus aucun scan Instagram" + (f" jusqu'au {fin_c.strftime('%d/%m')}" if fin_c else "")
                                      + ", comptes non relus", []))                     # C12 juge encore sur le dernier relevé
    if not (historique or non_lus or dp or series):
        return out + [_non_mesure("C12", "aucune donnée de scan (états, séries) : lectures des comptes non vérifiées")]
    listes = {k: set(dp.get(k) or []) for k in ("non_lus", "restreints", "suspects", "reels_non_lus")}
    scan = _instant(etats.get("scan_iso"))
    vus = set()
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        if not h or (h, _n(c.get("onglet"))) in vus or _ban(c) or _perdu(c):
            continue
        vus.add((h, _n(c.get("onglet"))))
        if _a_creer(c) and x.resoudre(c.get("gerant"))[0] == "libre":
            continue                                                     # jamais scanné, par construction
        cle = f"C12|{_n(c.get('onglet'))}|{h}"
        raisons = []
        hist = historique.get(h) or []
        dernier = hist[-1] if hist and isinstance(hist[-1], dict) else {}
        s = series.get(alias.get(h, h)) or {}
        rel = (s.get("releves") or [])[-1] if isinstance(s, dict) and s.get("releves") else {}
        # 09/10 (dashboard) : un seul passage non lu = « info » (Apify rate un compte de temps en temps : sans ça, le salon admin
        # recevrait un message à chaque passage) ; non lu deux passages de suite ou plus = « important »
        suivi = non_lus.get(h) if isinstance(non_lus.get(h), dict) else None
        n_non_lu = int((suivi or {}).get("jours") or 0)
        if suivi is not None:
            raisons.append(("important" if n_non_lu >= 2 else "info",
                            f"non lu depuis {n_non_lu or '?'} passage(s) (dernier le "
                            f"{(_date(suivi.get('dernier')) or x.maintenant.date()).strftime('%d/%m')})"))
        elif h in listes["non_lus"]:
            raisons.append(("info", f"non lu au dernier passage ({str(dp.get('t') or '')[:16].replace('T', ' ')})"))
        if h in listes["suspects"]:
            raisons.append(("important", "followers suspects (0 lu alors que le compte en avait) : cellule gardée"))
        if h in listes["reels_non_lus"]:
            raisons.append(("info", "Reels non lus (publications illisibles) : cellules gardées"))
        if isinstance(rel, dict) and rel and not rel.get("restreint") and rel.get("followers") is None and h not in listes["suspects"]:
            raisons.append(("info", f"followers illisibles au dernier relevé ({rel.get('source') or '?'})"))
        mesure_metricool = isinstance(rel, dict) and rel.get("source") == "metricool" and rel.get("followers") is not None
        if not mesure_metricool and (h in listes["restreints"] or dernier.get("restreint") or (isinstance(rel, dict) and rel.get("restreint"))):
            raisons.append(("info", "restreint (chiffres cachés au scan non connecté)"))   # lu par Metricool : la mesure est bonne
        if not raisons and _cree(c) and historique and not hist and not s and h not in non_lus:
            # 09/10 (revue CONTROLE : une ligne ajoutée à midi devenait « important » au tour suivant, un message, puis un autre le
            # lendemain). 10/10 (vérification CONTROLE : le code appliquait l'inverse — important dès 24 h même sans aucun passage
            # complet, par exemple refusé par le budget, avec une cause fausse et un message par ligne neuve) : la règle demandée,
            # « info tant que la ligne a moins de GRACE_H OU tant qu'aucun passage complet n'a eu lieu depuis son apparition » ;
            # important seulement quand un passage complet (scan_iso, posé au début du passage) a suivi son apparition ET qu'elle a
            # plus de GRACE_H. Scan coupé (budget) : info.
            vu = _instant(x.premiers_vus.get(cle))
            age_ok = vu is not None and (x.maintenant - vu) >= timedelta(hours=GRACE_H)
            passe = vu is not None and scan is not None and scan > vu
            mur = age_ok and passe
            le_scan = f"du {_paris(scan).strftime('%d/%m à %Hh%M')}" if scan is not None else ""
            if coupe:
                pourquoi = "scan coupé : budget Apify du mois atteint"
            elif mur:
                pourquoi = f"pas lu par le passage complet {le_scan} : onglet ou colonne non reconnus ?"
            elif passe:
                pourquoi = f"pas lu par le passage complet {le_scan}, important s'il ne l'est toujours pas après {GRACE_H} h"
            elif age_ok and budget.get("leger_ok") is False:
                # leger_ok faux : la dépense dépasse la trajectoire du mois — le refus du passage complet est probable, pas prouvé
                pourquoi = "aucun passage complet depuis son apparition : budget Apify serré, passage complet sans doute refusé"
            elif age_ok:
                pourquoi = "aucun passage complet depuis son apparition" + (f" (dernier {le_scan})" if le_scan else "") + ", lue au prochain"
            else:
                pourquoi = "ligne ajoutée depuis le dernier passage, lue au prochain"
            raisons.append(("important" if mur and not coupe else "info", f"jamais lu par le scan ({pourquoi})"))
        if not raisons:
            continue
        grav = min((g for g, _ in raisons), key=GRAVITES.index)
        out.append(_a("C12", grav, f"{_ou(c)} · {_qui(c)} : " + " ; ".join(t for _, t in raisons), cle))
    return out


# ------------------------------------------------------------------ entrées facultatives (lecture seule)
def _dossier():
    for cle in ("FICHIER_CONTROLE", "FICHIER_ONBOARDING", "FICHIER_CLICS", "FICHIER_EQUIPES"):
        f = _dep(cle)
        if f:
            return Path(f).parent
    return None


def _fichier(cle: str, nom: str):
    f = _dep(cle)
    if f:
        return Path(f)
    d = _dossier()
    return d / nom if d is not None else None


def _lire_fichier(cle: str, nom: str, defaut):
    lj, f = _dep("lire_json"), _fichier(cle, nom)
    if not lj or f is None:
        return None
    try:
        return lj(f, defaut)
    except Exception as erreur:                                          # noqa: BLE001
        journal.info("Contrôle : %s illisible (%s)", nom, erreur)
        return None


def _details_en_cache() -> list:
    """Les notes GAML vivantes que l'onboarding a déjà relues (aucun appel GAML ici). 09/10 (revue CONTROLE : le cache était ignoré
    dès minuit UTC, C9 retombait sur la copie du bot jusqu'au passage du matin et clignotait) : le cache de la veille sert encore,
    jusqu'à sa relecture ; le nom GAML de la liste y est joint (créatrice du lien, même règle que liens_classeur)."""
    cache = getattr(onboarding, "_details_gaml", None) or {}
    noms = {str(l.get("id")): str(l.get("name") or "") for l in cache.get("liste") or [] if isinstance(l, dict) and l.get("id")}
    out = []
    for d in cache.get("liens") or []:
        if isinstance(d, dict) and d.get("id"):
            e = dict(d)
            e.setdefault("nom", noms.get(str(d["id"]), ""))
            e.setdefault("jour", str(cache.get("jour") or ""))
            out.append(e)
    return out


def _membres_connus(registre: dict, onb: dict, clics: dict, membre_par_id=None) -> dict:
    """{uid: pseudo} des membres encore sur le serveur parmi ceux que le contrôle peut croiser (registre, fiches, liens), par
    `membre_par_id` (celle du bot par défaut)."""
    membre_par_id = membre_par_id or _dep("membre_par_id")
    if not membre_par_id:
        return {}
    uids = set(registre or {})
    uids |= set(((onb or {}).get("clippers") or {}))
    uids |= {str((l or {}).get("uid") or "") for l in ((onb or {}).get("livres") or {}).values() if isinstance(l, dict)}
    uids |= {str((e or {}).get("uid") or "") for e in ((onb or {}).get("ecartes") or {}).values() if isinstance(e, dict)}
    uids |= {str((i or {}).get("uid") or "") for i in ((clics or {}).get("liens") or {}).values() if isinstance(i, dict)}
    out = {}
    for uid in sorted(uids - {""}):
        try:
            m = membre_par_id(uid)
        except Exception:                                                # noqa: BLE001
            m = None
        if m is not None:
            out[str(uid)] = str(getattr(m, "display_name", "") or "")
    return out


def lire_entrees() -> dict:
    """Tout ce que le contrôle lit, hors classeur : clics.json, onboarding.json, registre, membres, séries, états, parcours,
    notes GAML vivantes, premiers signalements et mémoire du contrôle (controle.json). Lecture seule ; une source absente vaut {}."""
    lj = _dep("lire_json")
    def _lu(cle, nom):
        v = _lire_fichier(cle, nom, {})
        return v if isinstance(v, dict) else {}
    clics = _lu("FICHIER_CLICS", "clics.json")
    onb = _lu("FICHIER_ONBOARDING", "onboarding.json")
    registre = _lu("FICHIER_EQUIPES", "equipes.json")
    ctrl = _lu("FICHIER_CONTROLE", "controle.json")
    return {"clics": clics, "onboarding_etat": onb, "registre": registre, "membres": _membres_connus(registre, onb, clics) if lj else {},
            "series_etat": _lu("FICHIER_SERIES", "series_comptes.json"), "etats": _lu("FICHIER_ETATS", "etats_comptes.json"),
            "parcours": _lu("FICHIER_PARCOURS", "parcours.json"), "details_gaml": _details_en_cache(),
            "premiers_vus": (ctrl.get("premiers_vus") or {}),
            "memoire": {"mesures": ctrl.get("mesures") or {}, "notes": ctrl.get("notes") or {}}}


# ------------------------------------------------------------------ API du contrat C3
def anomalies(comptes, clics, onboarding_etat, registre, membres, series_etat, *, etats=None, parcours=None,
              details_gaml=None, premiers_vus=None, memoire=None, maintenant: datetime = None) -> list:
    """Les anomalies d'attribution, triées (bloquant, important, info ; puis famille), une par clé stable. Pure sur ses entrées.
    09/10 (dashboard) : `membres` = {uid: pseudo} (ou membres Discord, ou paires) des membres présents sur le serveur ; `etats`
    (etats_comptes.json : bios, non_lus, historique, dernier_passage, apify_budget, scan_iso), `parcours` (parcours.json),
    `details_gaml` ([{id, url, note, nom}] relus par l'onboarding), `premiers_vus` ({clé: iso}) et `memoire` (controle.json :
    dernières mesures de C8, dernières notes vivantes) sont lus dans les fichiers du bot quand ils ne sont pas passés et que le module
    est configuré. 09/10 (revue CONTROLE) : une famille qui n'a pas pu juger renvoie une entrée « non mesuré » (gravité info,
    `non_mesure: True`) au lieu de se taire."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if maintenant.tzinfo is None:
        maintenant = maintenant.replace(tzinfo=timezone.utc)
    entrees = None

    def _defaut(nom):
        nonlocal entrees
        if entrees is None:
            entrees = lire_entrees() if (_dep("lire_json") and _dossier() is not None) else {}
        return entrees.get(nom)

    comptes = [c for c in (comptes or []) if isinstance(c, dict)]
    clics = clics if clics is not None else _defaut("clics")                # None = lu (le contrat les passe toujours)
    onboarding_etat = onboarding_etat if onboarding_etat is not None else _defaut("onboarding_etat")
    registre = registre if registre is not None else _defaut("registre")
    clics, onboarding_etat, registre = (v if isinstance(v, dict) else {} for v in (clics, onboarding_etat, registre))
    if callable(membres):                                                 # membre_par_id du bot : interrogé pour chaque uid connu
        membres_d = _membres_connus(registre, onboarding_etat, clics, membres)
    else:
        membres_d = _membres(membres) if membres is not None else _membres(_defaut("membres"))
    x = _Ctx(comptes, clics, onboarding_etat, registre, membres_d,
             series_etat if series_etat is not None else _defaut("series_etat"),
             etats if etats is not None else _defaut("etats"),
             parcours if parcours is not None else _defaut("parcours"),
             details_gaml if details_gaml is not None else (_defaut("details_gaml") or []),
             premiers_vus if premiers_vus is not None else (_defaut("premiers_vus") or {}), maintenant,
             memoire if memoire is not None else (_defaut("memoire") or {}))
    if not x.comptes:
        # 09/10 (revue CONTROLE) : classeur vide ou illisible → rien n'a été vérifié (jamais « 0 anomalie » à la place). 10/10
        # (vérification CONTROLE : une seule entrée C1 couvrait les 12 familles par sa portée, un lecteur qui lit `famille` affichait
        # C2 à C12 « sans anomalie ») : une entrée « non mesuré » PAR famille, même raison
        return [_non_mesure(f, "classeur des logins vide ou illisible : rien n'a pu être vérifié") for f in FAMILLES]
    sans_liens = not x.liens                                             # clics.json vide ou illisible
    out, cles = [], set()
    for famille, noms in ((_c1, ("C1",)), (_nm_resolution, ()), (_c2_c3, ("C2", "C3")), (_c4, ("C4",)), (_c5, ("C5",)),
                          (_c6, ("C6",)), (_c7, ("C7",)), (_c8, ("C8",)), (_c9, ("C9",)), (_c10, ("C10",)), (_c11, ("C11",)),
                          (_c12, ("C12",))):
        if sans_liens and set(noms) & {"C5", "C6", "C7", "C8", "C9", "C10"}:
            # sans le relevé des liens, chaque cellule passerait pour « pas un lien GAML » et chaque clipper pour « sans lien »
            # (une famille déjà « non mesuré » faute de registre garde sa première raison : même clé)
            trouvees = [_non_mesure(f, "relevé des liens GAML (clics.json) vide ou illisible : liens non vérifiés") for f in noms]
        else:
            try:
                trouvees = famille(x)
            except Exception as erreur:                                  # noqa: BLE001 — une famille cassée n'éteint pas les autres
                journal.warning("Contrôle %s : %s", famille.__name__, erreur)
                trouvees = [_non_mesure(f, f"erreur du contrôle ({type(erreur).__name__}) : rien vérifié") for f in noms]
        for a in trouvees:
            if a["cle"] not in cles:
                cles.add(a["cle"])
                out.append(a)
    out.sort(key=lambda a: (GRAVITES.index(a["gravite"]), bool(a.get("non_mesure")), int(a["famille"][1:]), a["texte"]))
    return out


def _lids_de(lignes_attribuees, clics: dict) -> set:
    """Les identifiants de liens portés par les lignes, quelle que soit la forme : ids, URL, dict {lid: …}, lignes {lid|lien_id|
    id|liens|lien|lien_gaml}."""
    par_url = {_url_cle((i or {}).get("url")): str(lid) for lid, i in ((clics or {}).get("liens") or {}).items()
               if isinstance(i, dict) and _url_cle(i.get("url"))}
    connus = {str(lid) for lid in ((clics or {}).get("liens") or {})}
    out = set()

    def _un(v):
        if v is None or isinstance(v, bool):
            return
        if isinstance(v, (list, tuple, set)):
            for w in v:
                _un(w)
            return
        if isinstance(v, dict):
            for k in ("lid", "lien_id", "id", "liens", "lien", "lien_gaml", "url"):
                if v.get(k):
                    _un(v[k])
            return
        s = str(v).strip()
        if s in connus:
            out.add(s)
        elif _url_cle(s) in par_url:
            out.add(par_url[_url_cle(s)])
        elif s:
            out.add(s)
    if isinstance(lignes_attribuees, dict):
        _un(list(lignes_attribuees.keys()))
    else:
        _un(list(lignes_attribuees or []))
    return out


def _notes_par_defaut(clics: dict) -> dict:
    """Les notes GAML les plus fraîches connues sans appel : cache de l'onboarding, mémoire du contrôle, copie de clics.json."""
    memo = {}
    if _dep("lire_json") and _dossier() is not None:
        memo = (_lire_etat().get("notes") or {})
    return _notes(clics, _details_en_cache(), memo)[0]


def categorie_lien(clics: dict, lid, notes: dict = None) -> str:
    """10/10 (vérification CONTROLE) : la catégorie d'un lien de clics.json avec les notes du bouclage (`notes`, sinon
    _notes_par_defaut) — ce que le bouclage range dans ses seaux, pour un lecteur qui connaît l'id du lien."""
    info = (((clics or {}).get("liens") or {}) if isinstance(clics, dict) else {}).get(str(lid))
    notes = notes if isinstance(notes, dict) else _notes_par_defaut(clics if isinstance(clics, dict) else {})
    return categorie(info if isinstance(info, dict) else {}, notes.get(str(lid)))


def bouclage(clics, lignes_attribuees, fin: date = None, jours: int = 7, masques=None, notes: dict = None) -> dict:
    """09/10 (dashboard) : la preuve que rien ne se perd. Visites payables des `jours` derniers jours (jusqu'à hier, heure de
    Paris) de TOUS les liens actifs (ni désactivés, ni effacés) = portées par les lignes + lignes masquées du Dashboard + pages de
    créatrice + libérés / hors clipping + écart. 09/10 (revue CONTROLE) :
      - visites = paie_clics.clics_lien (contrat C6(e) : plancher `depuis`, None si un jour manque) — le TOTAL du Dashboard et le
        bouclage donnent le même chiffre ;
      - « pages » définies positivement (categorie) ; un lien de clipping sans détenteur (« non_attribue ») porté par aucune ligne
        va dans l'écart avec les liens attribués non portés, listés dans `non_comptes` (avec leur catégorie) ;
      - `masques` (mêmes formes que les lignes : ids, URL, lignes) : les liens des Gérants masqués du Dashboard (`!dashboard
        exclure`) comptent dans le seau « masques », jamais en écart.
    Un lien au relevé incomplet n'entre dans aucune somme : il est listé dans `non_mesures` (jamais un faux 0) et `complet` est faux.
    10/10 (vérification CONTROLE) : `categories` = {lid: catégorie} de chaque lien, avec les notes du bouclage (un lecteur range ses
    lignes Pages / Libérés avec les MÊMES catégories ; controle.categorie(info) sans note les retrouve aussi)."""
    clics = clics if isinstance(clics, dict) else {}
    fin = fin or _hier_paris()
    sur_lignes = _lids_de(lignes_attribuees, clics)
    sur_masques = (_lids_de(masques, clics) - sur_lignes) if masques else set()
    notes = notes if isinstance(notes, dict) else _notes_par_defaut(clics)
    out = {"debut": (fin - timedelta(days=jours - 1)).isoformat(), "fin": fin.isoformat(), "total": 0, "lignes": 0, "masques": 0,
           "pages": 0, "liberes": 0, "ecart": 0, "non_comptes": [], "non_mesures": [], "liens_masques": [], "liens": 0, "mesures": 0,
           "complet": True, "categories": {}}
    for lid, info in sorted(((str(k), v) for k, v in (clics.get("liens") or {}).items() if isinstance(v, dict))):
        cat = categorie(info, notes.get(lid))
        out["categories"][lid] = cat
        if cat in ("desactive", "supprime"):
            continue
        out["liens"] += 1
        v = visites_7j(clics, lid, fin, jours)
        if v is None:
            out["non_mesures"].append({"lid": lid, "url": _slug(info.get("url")), "categorie": cat})
            continue
        out["mesures"] += 1
        out["total"] += v
        if lid in sur_lignes:
            out["lignes"] += v
        elif lid in sur_masques:
            out["masques"] += v
            out["liens_masques"].append(lid)
        elif cat == "page":
            out["pages"] += v
        elif cat in ("libere", "hors_clipping"):
            out["liberes"] += v
        else:                                                            # attribué ou non attribué, porté par aucune ligne
            out["ecart"] += v
            out["non_comptes"].append({"lid": lid, "url": _slug(info.get("url")), "visites": v, "creatrice": str(info.get("creatrice") or ""),
                                       "note": str(notes.get(lid) or info.get("note") or ""), "categorie": cat})
    out["non_comptes"].sort(key=lambda d: -d["visites"])
    out["complet"] = not out["non_mesures"]
    return out


def compter(anomalies_: list) -> dict:
    """{famille: nombre} pour les 12 familles (zéros compris), dans l'ordre C1 → C12."""
    out = {f: 0 for f in FAMILLES}
    for a in anomalies_ or []:
        if a.get("famille") in out:
            out[a["famille"]] += 1
    return out


def non_mesurees(anomalies_: list) -> dict:
    """{famille: raison} des familles (ou parties de famille) qui n'ont pas pu juger : à afficher « non mesuré », jamais « 0 ».
    10/10 (vérification CONTROLE : la portée était ignorée, une entrée qui couvrait C1 à C12 ne rendait que C1) : chaque famille dont
    le préfixe « Cx| » est dans la `portee` d'une entrée compte aussi (avec la raison de cette entrée), dans l'ordre C1 → C12."""
    nm = [a for a in anomalies_ or [] if isinstance(a, dict) and a.get("non_mesure")]
    raison = lambda a: re.sub(r"^non mesuré : ", "", str(a.get("texte") or ""))        # noqa: E731
    trouve = {}
    for a in nm:
        trouve.setdefault(str(a.get("famille") or ""), raison(a))
    for a in nm:
        for p in a.get("portee") or []:
            f = str(p)[:-1] if str(p).endswith("|") else ""
            if f in FAMILLES:
                trouve.setdefault(f, raison(a))
    return {f: trouve[f] for f in list(FAMILLES) + sorted(k for k in trouve if k not in FAMILLES) if f in trouve}


def _portees(anomalies_: list) -> list:
    return [p for a in anomalies_ or [] if isinstance(a, dict) and a.get("non_mesure") for p in (a.get("portee") or [])]


def _cles_empreinte(anomalies_: list, precedentes=None) -> list:
    """Les clés qui méritent un message : celles des anomalies bloquantes et importantes ; plus, quand une famille n'a pas pu juger
    (« non mesuré »), les clés `precedentes` qu'elle couvre — la situation n'est pas connue, donc pas changée."""
    cles = {a["cle"] for a in anomalies_ or [] if isinstance(a, dict) and a.get("gravite") in ("bloquant", "important")
            and not a.get("non_mesure")}
    portees = _portees(anomalies_)
    cles |= {str(k) for k in precedentes or () if _couverte(str(k), portees)}
    return sorted(cles)


def empreinte(anomalies_: list, precedentes=None) -> str:
    """L'empreinte de ce qui mérite un message : les clés des anomalies bloquantes et importantes (pas leurs textes, qui portent
    des chiffres qui bougent ; pas les « info », ni les « non mesuré »). 09/10 (revue CONTROLE) : `precedentes` = les clés du tour
    d'avant ; celles d'une famille « non mesuré » ce tour-ci sont gardées (registre illisible le temps d'un tour : pas de message
    parasite, ni à la panne, ni au retour)."""
    cles = _cles_empreinte(anomalies_, precedentes)
    return hashlib.sha1("\n".join(cles).encode("utf-8")).hexdigest()[:16]


def _suite(k: int) -> str:
    return f"… et {k} autre(s) (Dashboard, section Contrôle)"


LIGNE_MAX = 300                                                          # une ligne du salon admin (le Dashboard coupe aussi à 300)
REMEDE_MAX = 400                                                         # la partie « — remède / commande » gardée entière jusque-là


def _couper_ligne(l: str) -> str:
    """Une ligne d'anomalie de LIGNE_MAX caractères au plus. 10/10 (vérification CONTROLE : le remède C4, avec un @ long, passait
    les 300 caractères et sa fin — la commande `!onboarding` — était coupée) : quand la ligne a une suite « — … » qui porte une
    commande (`…`), c'est la description d'avant qui est raccourcie, jamais la commande (la ligne peut alors faire un peu plus)."""
    if len(l) <= LIGNE_MAX:
        return l
    tete, sep, suite = l.partition(" — ")
    if sep and "`" in suite and len(suite) <= REMEDE_MAX:
        place = max(60, LIGNE_MAX - len(sep) - len(suite))
        return (tete if len(tete) <= place else tete[:place - 1] + "…") + sep + suite
    return l[:LIGNE_MAX - 3] + "…"


def texte_admin(anomalies_: list) -> str:
    """Le message du salon admin (lu sur téléphone : blocs courts, une ligne vide entre chaque bloc). 09/10 (revue CONTROLE) :
    1. la place des listes se calcule d'après les lignes fixes RÉELLES (tête, Info, Non mesuré, titres, « … et N autre(s) ») : les
    listes sont coupées, jamais la ligne Info ; les importants gardent au moins un tiers de la place ; 2. jamais « 0 anomalie » ni
    « chaque lien est attribué » quand une famille n'a pas pu juger : la ligne « Non mesuré » le dit."""
    toutes = [a for a in anomalies_ or [] if isinstance(a, dict)]
    nm = [a for a in toutes if a.get("non_mesure")]
    an = [a for a in toutes if not a.get("non_mesure")]
    bloc_nm = ""
    if nm:
        # 10/10 (vérification CONTROLE) : une même raison pour plusieurs familles est écrite une fois (« C1, C2, … C12 classeur … »)
        par_raison = {}
        for a in nm:
            par_raison.setdefault(re.sub(r"^non mesuré : ", "", str(a.get("texte") or "")), []).append(str(a.get("famille") or "?"))
        raisons = [f"{', '.join(dict.fromkeys(fs))} {r}" for r, fs in par_raison.items()]
        bloc_nm = "**❔ Non mesuré** : " + " · ".join(r if len(r) <= 160 else r[:157] + "…" for r in raisons)
        bloc_nm = bloc_nm if len(bloc_nm) <= 700 else bloc_nm[:699] + "…"
    if not an:
        if not nm:
            return "🧭 **Contrôle d'attribution** : 0 anomalie, chaque compte et chaque lien est attribué."
        if set(_portees(nm)) >= {f"{f}|" for f in FAMILLES}:                # toutes les familles, en une entrée ou en douze
            return ("🧭 **Contrôle d'attribution** : rien n'a pu être vérifié ce tour-ci.\n\n" + bloc_nm)[:LIMITE_TEXTE]
        return ("🧭 **Contrôle d'attribution** : rien trouvé dans ce qui a pu être vérifié, mais une partie n'a pas pu l'être : "
                "l'attribution n'est pas prouvée complète.\n\n" + bloc_nm)[:LIMITE_TEXTE]
    n = {g: sum(1 for a in an if a["gravite"] == g) for g in GRAVITES}
    tete = (f"🧭 **Contrôle d'attribution** : {len(an)} anomalie(s) — {n['bloquant']} bloquante(s), {n['important']} importante(s), "
            f"{n['info']} info. Rien n'est corrigé : à trancher dans le classeur ou dans GAML.")
    infos = compter([a for a in an if a["gravite"] == "info"])
    bloc_info = ("**ℹ️ Info** : " + " · ".join(f"{f} ×{k}" for f, k in infos.items() if k)) if n["info"] else ""
    groupes = []
    for g, titre in (("bloquant", "**⛔ Bloquant**"), ("important", "**⚠️ Important**")):
        lignes = [f"· {a['famille']} {a['texte']}" for a in an if a["gravite"] == g]
        if lignes:
            groupes.append((titre, [_couper_ligne(l) for l in lignes]))
    fixes = [b for b in (bloc_info, bloc_nm) if b]
    # place fixe : tête, blocs Info / Non mesuré, titres, séparateurs « \n\n », et la ligne « … et N autre(s) » de chaque groupe
    fixe = len(tete) + sum(len(b) for b in fixes) + 2 * (len(fixes) + len(groupes))
    fixe += sum(len(titre) + 2 + 1 + len(_suite(len(lignes))) for titre, lignes in groupes)
    place = max(0, LIMITE_TEXTE - fixe)
    besoins = [sum(len(l) + 1 for l in lignes) for _, lignes in groupes]
    if sum(besoins) <= place:
        parts = besoins
    elif len(groupes) == 2:
        mini_imp = min(besoins[1], place // 3)
        p0 = min(besoins[0], place - mini_imp)
        parts = [p0, place - p0]
    else:
        parts = [place]
    blocs = [tete]
    for (titre, lignes), part in zip(groupes, parts):
        gardees, reste = [], part
        for l in lignes:
            if len(l) + 1 > reste:
                break
            gardees.append(l)
            reste -= len(l) + 1
        if len(gardees) < len(lignes):
            gardees.append(_suite(len(lignes) - len(gardees)))
        blocs.append(titre + "\n\n" + "\n".join(gardees))
    texte = "\n\n".join(blocs + fixes)
    while len(texte) > LIMITE_TEXTE and len(blocs) > 1:                   # garde-fou : on retire des lignes de liste, jamais Info
        i = len(blocs) - 1
        lignes_b = blocs[i].split("\n")
        if len(lignes_b) <= 3:
            blocs.pop(i)
        else:
            lignes_b.pop(-2)
            blocs[i] = "\n".join(lignes_b)
        texte = "\n\n".join(blocs + fixes)
    return texte[:LIMITE_TEXTE]


# ------------------------------------------------------------------ le tour de 15 min
def _lire_etat() -> dict:
    v = _lire_fichier("FICHIER_CONTROLE", "controle.json", {})
    return v if isinstance(v, dict) else {}


def _ecrire_etat(d: dict):
    ej, f = _dep("ecrire_json"), _fichier("FICHIER_CONTROLE", "controle.json")
    if ej and f is not None:
        ej(f, d)


def _memo_mesures(clics: dict, fin: date, ancien: dict) -> dict:
    """La dernière mesure complète des visites 7 j de chaque lien actif (C8 : reprise quand le relevé redevient incomplet)."""
    ancien = ancien if isinstance(ancien, dict) else {}
    out = {}
    for lid, info in ((clics or {}).get("liens") or {}).items():
        if not isinstance(info, dict) or info.get("supprime_gaml") or info.get("desactive"):
            continue
        v, d, f, source = _visites_recentes(clics, str(lid), fin, None)
        if v is not None and source == "releve":
            out[str(lid)] = {"v": v, "debut": d.isoformat(), "fin": f.isoformat()}
        elif isinstance(ancien.get(str(lid)), dict) and _date(ancien[str(lid)].get("fin")) and \
                (fin - _date(ancien[str(lid)]["fin"])).days <= MEMOIRE_JOURS:
            out[str(lid)] = ancien[str(lid)]
    return out


def _memo_notes(clics: dict, details: list, ancien: dict, t_iso: str) -> dict:
    """La dernière note GAML vivante vue pour chaque lien, avec la copie de clics.json de ce moment-là (C9 : sert après un
    redémarrage ou quand le cache de l'onboarding est vide ; abandonnée dès que le bot change sa copie). 10/10 (vérification
    CONTROLE) : avec l'URL du lien, pour que controle.categorie(info) appelée sans note (le Dashboard) retrouve la même note."""
    ancien = ancien if isinstance(ancien, dict) else {}
    liens = {str(k): v for k, v in ((clics or {}).get("liens") or {}).items() if isinstance(v, dict)}
    out = {str(lid): m for lid, m in ancien.items() if str(lid) in liens and isinstance(m, dict)}
    for lid, m in _notes(clics, details, ancien)[1].items():
        if lid in liens:
            out[lid] = dict(m, t=t_iso)
    for lid, m in out.items():
        if str(liens[lid].get("url") or "").strip():
            out[lid] = dict(m, url=str(liens[lid].get("url")))
    return out


async def passage(deps: dict = None, force: bool = False, comptes: list = None):
    """09/10 (dashboard) : appelé par la boucle de l'onboarding toutes les 15 min, après la colonne « Lien GAML associé ». Relit
    le classeur et les fichiers du bot, calcule les anomalies, garde la date du premier signalement de chacune (controle.json),
    et poste le texte au salon admin seulement si l'empreinte a changé (ou `force`). Renvoie le texte posté, sinon None.
    09/10 (revue CONTROLE) : garde aussi la dernière mesure 7 j de chaque lien et la dernière note GAML vivante (C8 et C9 ne
    clignotent plus la nuit ni au redémarrage)."""
    if deps and not _deps:
        configurer(deps)
    if comptes is None:
        if not onboarding.actif():
            return None
        comptes = await onboarding.lire_comptes()
    maintenant = datetime.now(timezone.utc)
    e = lire_entrees()
    an = anomalies(comptes, e["clics"], e["onboarding_etat"], e["registre"], e["membres"], e["series_etat"], etats=e["etats"],
                   parcours=e["parcours"], details_gaml=e["details_gaml"], premiers_vus=e["premiers_vus"], memoire=e["memoire"],
                   maintenant=maintenant)
    reelles = [a for a in an if not a.get("non_mesure")]
    etat = _lire_etat()
    avant = etat.get("empreinte")
    cles = _cles_empreinte(an, etat.get("cles"))                         # les clés d'une famille non mesurée sont gardées
    emp = hashlib.sha1("\n".join(cles).encode("utf-8")).hexdigest()[:16]
    t_iso = maintenant.isoformat(timespec="minutes")
    pv = etat.get("premiers_vus") or {}
    portees = _portees(an)
    garde_pv = {k: v for k, v in pv.items() if _couverte(str(k), portees)}   # date de premier signalement jamais remise à zéro
    etat.update({"t": t_iso, "n": compter(reelles), "non_mesure": sorted({a["famille"] for a in an if a.get("non_mesure")}),
                 "cles": cles,
                 "premiers_vus": dict(garde_pv, **{a["cle"]: pv.get(a["cle"]) or t_iso for a in reelles}),
                 "mesures": _memo_mesures(e["clics"], _hier_paris(maintenant), etat.get("mesures")),
                 "notes": _memo_notes(e["clics"], e["details_gaml"], etat.get("notes"), t_iso)})
    a_poster = force or (emp != avant and (avant is not None or any(a["gravite"] != "info" for a in an)))
    texte = texte_admin(an) if a_poster else None
    envoye = False
    if texte and _dep("canal_admin"):
        try:
            canal = await _dep("canal_admin")()
            if canal is not None:
                await canal.send(texte)
                envoye = True
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Contrôle d'attribution : salon admin : %s", erreur)
    if envoye or not a_poster:
        etat["empreinte"] = emp                                          # un envoi raté est retenté au tour suivant
    _ecrire_etat(etat)
    journal.info("Contrôle d'attribution : %d anomalie(s) (%s)%s%s", len(reelles),
                 ", ".join(f"{f} {k}" for f, k in compter(reelles).items() if k) or "aucune",
                 f" ; non mesuré : {', '.join(etat['non_mesure'])}" if etat["non_mesure"] else "", " — postée" if envoye else "")
    return texte if envoye else None
