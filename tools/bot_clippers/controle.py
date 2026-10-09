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
  C6  cellule « Lien GAML associé » ≠ lien attendu (libéré, hors clipping, supprimé, désactivé, autre clipper, page de la créatrice) ;
  C7  lien attribué sans ligne vivante (ou à un membre absent du registre) ;
  C8  lien libéré ou hors clipping avec des visites payables sur 7 j, porté par aucune ligne ;
  C9  note GAML ≠ attribution du bot ;
  C10 lien en bio Instagram (etats_comptes.json « bios ») ≠ lien attendu ;
  C11 @ en double (même onglet, ou deux onglets : la ligne écartée par onboarding._sans_doublons est invisible au bot) ;
  C12 compte non lu / restreint / illisible au dernier passage (etats « non_lus », « dernier_passage », historique, séries).

API :
  anomalies(comptes, clics, onboarding_etat, registre, membres, series_etat) -> [{"famille", "gravite", "texte", "cle"}]
      pure : les entrées optionnelles (etats, parcours, details_gaml, premiers_vus, maintenant) se passent en mots-clés ; laissées
      à None, elles sont LUES (lecture seule) dans les fichiers du bot quand le module est configuré, sinon ignorées.
  bouclage(clics, lignes_attribuees) -> dict : visites 7 j de tous les liens actifs = lignes + pages + libérés/hors clipping + écart.
  texte_admin(anomalies) -> str ; empreinte(anomalies) -> str ; compter(anomalies) -> {famille: n}.
  await passage(deps) : le tour de 15 min (calcul, mémoire des premiers signalements, salon admin seulement si l'empreinte change).

Aucun appel GAML, Apify ni Google en écriture : le classeur est relu (lire_comptes), tout le reste vient des fichiers du bot.
"""

import hashlib
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import onboarding

journal = logging.getLogger("controle")

FAMILLES = {
    "C1": "Compte créé sans Gérant",
    "C2": "Gérant fantôme",
    "C3": "Gérant ambigu (homonymes)",
    "C4": "Gérant ≠ fiche d'onboarding",
    "C5": "Lien dû manquant",
    "C6": "Cellule Lien GAML fausse",
    "C7": "Lien sans ligne vivante",
    "C8": "Visites sur lien libéré / hors clipping",
    "C9": "Note GAML ≠ attribution",
    "C10": "Lien en bio ≠ lien attendu",
    "C11": "@ en double",
    "C12": "Compte non lu / restreint / illisible",
}
GRAVITES = ("bloquant", "important", "info")
# 09/10 (dashboard) : les prénoms du staff (Gérant d'un compte de redirection, repreneur Metricool) ne sont jamais des fantômes
STAFF = {p for p in (onboarding._norm(x).strip() for x in os.environ.get("CONTROLE_STAFF", "gaetan,rianah,jonas").split(",")) if p}
BIO_JOURS = int(os.environ.get("CONTROLE_BIO_JOURS", "7") or 7)         # une bio relevée il y a plus longtemps n'est plus jugée
CLICS_DEPUIS = os.environ.get("CLICS_DEPUIS", "2026-09-16").strip()       # même début de relevé que paie_clics
LIMITE_TEXTE = 1950
_RE_COMPTE_DE = re.compile(r"\s*compte\s+de\s+@?\s*(\S+)")
_RE_CLIPPING = re.compile(r"\s*clipping\s+(.+)$", re.I)
_RE_INSTAGRAM = re.compile(r"(^|\.)(instagram\.com|instagr\.am|threads\.net)$")

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


def _paris(quand: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return quand.astimezone(ZoneInfo("Europe/Paris"))
    except Exception:                                                    # noqa: BLE001 — base de fuseaux absente
        return quand.astimezone(timezone(timedelta(hours=2)))


def _hier_paris(maintenant: datetime = None) -> date:
    return _paris(maintenant or datetime.now(timezone.utc)).date() - timedelta(days=1)


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


# ------------------------------------------------------------------ visites (relevé local de paie_clics, zéro appel)
def visites_7j(clics: dict, lid: str, fin: date, jours: int = 7):
    """Visites payables (`payes`) d'un lien sur les `jours` jours finissant `fin`, depuis clics.json « jours ». None si un jour
    manque ou porte une erreur (jamais un faux 0). Les jours d'avant le début du relevé du lien (`depuis`, sinon CLICS_DEPUIS)
    ne sont pas exigés."""
    serie = ((clics or {}).get("jours") or {}).get(str(lid)) or {}
    if not isinstance(serie, dict) or not serie:
        return None
    info = ((clics or {}).get("liens") or {}).get(str(lid)) or {}
    debut = fin - timedelta(days=jours - 1)
    bornes = [d for d in (_date(info.get("depuis")) or _date(CLICS_DEPUIS), min((d for d in map(_date, serie) if d), default=None)) if d]
    j = max(debut, min(bornes)) if bornes else debut
    if j > fin:
        return None
    total = 0
    while j <= fin:
        v = serie.get(j.isoformat())
        if not isinstance(v, dict) or v.get("erreur") or "payes" not in v:
            return None
        try:
            total += int(v.get("payes") or 0)
        except (TypeError, ValueError):
            return None
        j += timedelta(days=1)
    return total


def _categorie(info: dict) -> str:
    """attribue / libere / hors_clipping / page (créatrice, /ytb, /fb, Metricool jamais attribué) / desactive / supprime."""
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
    return "page"


# ------------------------------------------------------------------ le contexte d'un calcul
class _Ctx:
    def __init__(self, comptes, clics, onb, registre, membres_d, series_etat, etats, parcours, details, premiers_vus, maintenant):
        self.comptes = comptes
        self.clics = clics
        self.liens = {str(k): v for k, v in ((clics.get("liens") or {}) if isinstance(clics, dict) else {}).items() if isinstance(v, dict)}
        self.onb = onb
        self.registre = registre
        self.membres = membres_d
        self.series = series_etat
        self.etats = etats
        self.parcours = parcours
        self.premiers_vus = premiers_vus
        self.maintenant = maintenant
        self.fin = _hier_paris(maintenant)
        self.creatrices = onboarding.creatrices_connues(comptes)
        # la résolution par prénom n'a de sens qu'avec un registre et la liste des membres (sinon tout serait « fantôme »)
        self.resolution = bool(registre) and bool(membres_d)
        self.notes = {}
        self.par_url = {}
        for lid, info in self.liens.items():
            if info.get("note") is not None:
                self.notes[lid] = str(info.get("note") or "")
            if _url_cle(info.get("url")):
                self.par_url.setdefault(_url_cle(info.get("url")), lid)
        for d in details or []:                                          # la note vivante de GAML (cache du jour) gagne
            if not isinstance(d, dict) or not d.get("id"):
                continue
            lid = str(d["id"])
            if d.get("note") is not None and str(d.get("note")).strip():
                self.notes[lid] = str(d.get("note") or "")
            if _url_cle(d.get("url")) and lid in self.liens:
                self.par_url.setdefault(_url_cle(d.get("url")), lid)
        self.hotes_gaml = {_hote(u) for u in self.par_url} | {_hote(d.get("url")) for d in details or [] if isinstance(d, dict)}
        self.hotes_gaml.discard("")
        self._resolus = {}
        self.cellules = {}                                               # url → lignes qui portent ce lien dans leur cellule
        for c in comptes:
            u = _url_cle(c.get("lien_gaml"))
            if u and c.get("handle"):
                self.cellules.setdefault(u, []).append(c)
        self.prenoms_membres = {_premier(nom) for nom in membres_d.values()} - {""}
        self.prenoms_registre = {_premier(f.get("prenom")) for f in registre.values() if isinstance(f, dict)} - {""}
        self.repreneurs = set()                                          # « Rianah Metricool 3 (ex-…) » → rianah
        for note in self.notes.values():
            m = re.match(r"\s*(\S+)\s+metricool\b", _n(note))
            if m:
                self.repreneurs.add(m.group(1))
        self.proprietaires = {}                                          # handle → {uid} (fiches d'onboarding, livraisons)
        for uid, fiche in ((onb.get("clippers") or {}) if isinstance(onb, dict) else {}).items():
            if not isinstance(fiche, dict):
                continue
            hs = {_cle_compte(h) for h in fiche.get("comptes") or [] if isinstance(h, str)}
            hs |= {_cle_compte(a.get("handle")) for a in fiche.get("acces") or [] if isinstance(a, dict)}
            for h in hs - {""}:
                self.proprietaires.setdefault(h, set()).add(str(uid))
        for h, l in ((onb.get("livres") or {}) if isinstance(onb, dict) else {}).items():
            if isinstance(l, dict) and str(l.get("uid") or ""):
                self.proprietaires.setdefault(_cle_compte(h), set()).add(str(l["uid"]))
        self.ecartes = {_cle_compte(h): str((e or {}).get("uid") or "") for h, e in
                        ((onb.get("ecartes") or {}) if isinstance(onb, dict) else {}).items() if isinstance(e, dict)}

    # -- Gérant → membre
    def resoudre(self, gerant) -> tuple:
        """(genre, uid, candidats) : genre = libre | creatrice | metricool | staff | membre | ambigu | fantome | inconnu.
        Même règle que bot_discord.membre_par_prenom : membre SIGNÉ (registre) présent sur le serveur, dont le premier mot du
        pseudo (ou le pseudo entier) vaut le Gérant normalisé ; un seul, sinon personne."""
        g = _n(gerant)
        if g in self._resolus:
            return self._resolus[g]
        if g in onboarding.GERANTS_LIBRES:
            r = ("libre", "", [])
        elif onboarding.est_creatrice(gerant, self.creatrices):
            r = ("creatrice", "", [])
        elif "metricool" in g:
            r = ("metricool", "", [])
        elif _premier(g) in STAFF:
            r = ("staff", "", [])
        elif not self.resolution:
            r = ("inconnu", "", [])
        else:
            cands = sorted(uid for uid, nom in self.membres.items() if uid in self.registre and (_premier(nom) == g or _n(nom) == g))
            r = ("membre", cands[0], cands) if len(cands) == 1 else (("ambigu", "", cands) if cands else ("fantome", "", []))
        self._resolus[g] = r
        return r

    def _prenom_registre(self, uid) -> str:
        fiche = self.registre.get(str(uid or ""))
        return str(fiche.get("prenom") or "").strip() if isinstance(fiche, dict) else ""

    def nom(self, uid) -> str:
        """Le nom à afficher d'un membre : son pseudo (avant « - Créatrice »), sinon le prénom du registre."""
        uid = str(uid or "")
        if self.membres.get(uid):
            return self.membres[uid].split(" - ")[0].strip() or "?"
        p = self._prenom_registre(uid)
        return p.title() if p else "un membre parti"

    def prenom_de(self, uid) -> str:
        """Le prénom normalisé d'un membre (premier mot du pseudo, sinon du registre) ; '' si inconnu."""
        uid = str(uid or "")
        return _premier(self.membres.get(uid) or self._prenom_registre(uid))

    def compte_pour(self, c, uid) -> bool:
        genre, u, cands = self.resoudre(c.get("gerant"))
        return (genre == "membre" and u == uid) or (genre == "ambigu" and uid in cands)

    # -- liens
    def lid_url(self, u):
        return self.par_url.get(_url_cle(u))

    def cr_lien(self, info) -> str:
        return _premier(info.get("creatrice"))

    def liens_de(self, uid) -> list:
        return [(lid, i) for lid, i in self.liens.items()
                if str(i.get("uid") or "") == uid and not i.get("supprime_gaml") and not i.get("desactive")]

    def voulu(self, uid, cr):
        """(lid, info) du lien attendu d'un clipper pour une créatrice : comme onboarding.liens_classeur (le plus récent de la
        créatrice ; un lien unique sans créatrice connue vaut pour toutes)."""
        siens = self.liens_de(uid)
        cands = [x for x in siens if self.cr_lien(x[1]) == cr] or (siens if len(siens) == 1 and not self.cr_lien(siens[0][1]) else [])
        return max(cands, key=lambda x: (str(x[1].get("depuis") or ""), x[0])) if cands else None

    def prenom_lien(self, lid) -> str:
        info = self.liens.get(lid) or {}
        uid = str(info.get("uid") or "")
        if uid and self.prenom_de(uid):
            return self.prenom_de(uid)
        m = _RE_CLIPPING.match(self.notes.get(lid) or "")
        return _premier(m.group(1)) if m else ""

    def visites(self, lid):
        return visites_7j(self.clics, lid, self.fin)

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
        return any(_cree(c) and _cr_ligne(c) == cr and self.compte_pour(c, uid) for c in self.comptes)


def _a(famille, gravite, texte, cle) -> dict:
    return {"famille": famille, "gravite": gravite, "texte": texte, "cle": cle}


# ------------------------------------------------------------------ les familles
def _c1(x: _Ctx) -> list:
    out = []
    for c in x.comptes:
        if not c.get("handle") or x.resoudre(c.get("gerant"))[0] != "libre" or not _cree(c):
            continue
        cle = f"C1|{_n(c.get('onglet'))}|{_cle_compte(c['handle'])}"
        if _n(c.get("utilisation")).startswith("a mettre metricool"):
            vu = _date((x.premiers_vus or {}).get(cle))
            age = f" · signalé depuis le {vu.strftime('%d/%m')} ({(x.maintenant.date() - vu).days} j)" if vu else ""
            out.append(_a("C1", "important", f"{_ou(c)} · @{c['handle']} ({c.get('etat')}) : compte créé rendu, « à mettre Metricool »"
                                              f" — aucune ligne ne le suit{age}", cle))
        else:
            out.append(_a("C1", "info", f"{_ou(c)} · @{c['handle']} ({c.get('etat')}) : compte créé sans Gérant (au vivier, prêt pour le "
                                        "prochain clipper)", cle))
    return out


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
        quoi = ("repreneur Metricool inconnu (ni membre, ni staff, ni note GAML « … Metricool »)" if "metricool" in g else
                "aucun membre signé de ce prénom sur le serveur (parti, prénom écrit autrement ?)")
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
    if not x.resolution:
        return []
    out = []
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        if not h:
            continue
        genre, uid, _ = x.resoudre(c.get("gerant"))
        if genre in ("fantome", "ambigu", "inconnu"):
            continue                                                     # déjà C2 / C3 : pas de propriétaire attendu à comparer
        cle = f"C4|{_n(c.get('onglet'))}|{h}"
        proprios = x.proprietaires.get(h, set())
        presents = sorted(o for o in proprios if o != uid and o in x.membres)
        if genre == "membre":
            if x.ecartes.get(h) == uid:
                out.append(_a("C4", "important", f"{_ou(c)} · {_qui(c)} : écarté à la livraison (homonyme possible d'un ancien), jamais "
                                                 "livré — `!onboarding` si c'est bien le sien, sinon `!liberer`", cle))
            elif presents:
                out.append(_a("C4", "bloquant", f"{_ou(c)} · {_qui(c)} : encore dans la fiche de {', '.join(x.nom(o) for o in presents)} "
                                                "(accès et codes 2FA chez un autre)" + ("" if uid in proprios else " ; jamais livré au Gérant"), cle))
            elif uid not in proprios and _n(c.get("utilisation")) == "clipper":
                out.append(_a("C4", "important", f"{_ou(c)} · {_qui(c)} : au nom de {x.nom(uid)} mais absent de sa fiche d'onboarding "
                                                 "(jamais livré)", cle))
        elif presents:
            quoi = {"libre": "compte sans Gérant", "metricool": "compte Metricool", "staff": "compte du staff",
                    "creatrice": "compte de la créatrice"}[genre]
            out.append(_a("C4", "bloquant", f"{_ou(c)} · {_qui(c)} : {quoi} encore dans la fiche de "
                                            f"{', '.join(x.nom(o) for o in presents)} (accès et codes 2FA) — `!liberer`", cle))
    return out


def _c5(x: _Ctx) -> list:
    if not x.resolution:
        return []
    paires = {}
    for c in x.comptes:
        if not _vivante(c) or _n(c.get("utilisation")) not in ("clipper", ""):
            continue
        genre, uid, _ = x.resoudre(c.get("gerant"))
        if genre == "membre":
            paires.setdefault((uid, _cr_ligne(c)), []).append(c)
    out = []
    for (uid, cr), cs in sorted(paires.items()):
        if not cr or x.voulu(uid, cr) or not x.lien_du(uid, cr):
            continue
        out.append(_a("C5", "important", f"{cs[0].get('onglet') or cr.title()} · {x.nom(uid)} : lien GAML dû (compte privé ouvert ou "
                                         f"comptes créés) mais aucun lien {cr.title()} à son nom dans le bot", f"C5|{uid}|{cr}"))
    return out


def _c6(x: _Ctx) -> list:
    out = []
    for c in x.comptes:
        cellule = str(c.get("lien_gaml") or "").strip()
        if not c.get("handle") or not cellule:
            continue
        genre, uid, cands = x.resoudre(c.get("gerant"))
        cle = f"C6|{_n(c.get('onglet'))}|{_cle_compte(c['handle'])}"
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
        cat = _categorie(info)
        clipper = genre in ("membre", "ambigu", "fantome", "inconnu")
        probleme, grav = "", "bloquant"
        if cat in ("supprime", "desactive"):
            probleme = "lien effacé de GAML" if cat == "supprime" else "lien désactivé dans GAML (visites perdues)"
            grav = "important" if genre == "libre" else "bloquant"
        elif genre == "libre":
            probleme, grav = "ligne sans Gérant qui garde un lien (le regroupement lui redonnerait un Gérant)", "important"
        elif cat == "attribue":
            uid_l = str(info.get("uid"))
            if genre == "membre" and uid_l != uid:
                probleme = f"lien de {x.nom(uid_l)}, pas de {str(c.get('gerant')).strip()}"
            elif genre == "membre" and x.cr_lien(info) and x.cr_lien(info) != _cr_ligne(c):
                probleme = f"son lien {x.cr_lien(info).title()} sur une ligne {_cr_ligne(c).title()}"
            elif genre == "membre":
                v = x.voulu(uid, _cr_ligne(c))
                if v and v[0] != lid:
                    probleme, grav = f"pas son lien le plus récent (attendu « {_slug(v[1].get('url'))} »)", "important"
            elif genre == "ambigu":
                if uid_l not in cands:
                    probleme = f"lien de {x.nom(uid_l)}"
            elif genre == "fantome":
                if x.prenom_lien(lid) and x.prenom_lien(lid) != _premier(c.get("gerant")):
                    probleme = f"lien de {x.nom(uid_l)} sur une ligne au nom de « {str(c.get('gerant')).strip()} »"
            elif genre != "inconnu":
                probleme = (f"lien du clipper {x.nom(uid_l)} sur une ligne "
                            + {"metricool": "Metricool", "creatrice": "de la créatrice", "staff": "du staff"}.get(genre, genre))
        elif cat == "libere":
            ancien = str(info.get("ancien") or "?")
            probleme, grav = f"lien libéré (ex-{ancien}) : ses visites sont celles d'un autre", ("bloquant" if clipper else "important")
        elif cat == "hors_clipping":
            note = str(info.get("hors_clipping") or x.notes.get(lid) or "")
            if genre == "metricool":
                rep = re.split(r"[\s(]", _n(c.get("gerant")))[0]
                if rep and f"{rep} metricool" not in _n(note):
                    probleme, grav = f"lien hors clipping « {note} », pas un lien {rep.title()} Metricool", "important"
            elif clipper:
                probleme = f"lien hors clipping « {note} » sur une ligne de clipper"
            else:
                probleme, grav = f"lien hors clipping « {note} »", "important"
        else:                                                            # page de la créatrice, /ytb, /fb, lien jamais attribué
            if clipper:
                probleme = "page de la créatrice (lien jamais attribué) sur une ligne de clipper"
            elif genre == "creatrice":
                m = _RE_COMPTE_DE.match(_n(x.notes.get(lid)))
                if m and _compact(m.group(1)) != _compact(c.get("handle")):
                    probleme, grav = f"lien du compte @{m.group(1)} (note GAML) sur la ligne d'un autre compte de la créatrice", "important"
        if probleme:
            out.append(_a("C6", grav, f"{tete} = {probleme}", cle))
    return out


def _c7(x: _Ctx) -> list:
    if not x.resolution:
        return []
    out = []
    for lid, info in sorted(x.liens.items()):
        uid = str(info.get("uid") or "")
        if not uid or _categorie(info) != "attribue":
            continue
        cr = x.cr_lien(info)
        tete = f"{(cr or '?').title()} · lien « {_slug(info.get('url'))} »"
        if uid not in x.registre:
            out.append(_a("C7", "important", f"{tete} attribué à {x.nom(uid)}, absent du registre des signés (parti ?) : à libérer",
                          f"C7|{lid}"))
            continue
        lignes = [c for c in x.comptes if _vivante(c) and x.compte_pour(c, uid) and (not cr or _cr_ligne(c) == cr)]
        if not lignes:
            out.append(_a("C7", "important", f"{tete} de {x.nom(uid)} : aucune ligne vivante à son nom chez {(cr or '?').title()} "
                                             "(ses visites ne sont comptées sur aucun compte)", f"C7|{lid}"))
    return out


def _c8(x: _Ctx) -> list:
    out = []
    for lid, info in sorted(x.liens.items()):
        cat = _categorie(info)
        if cat not in ("libere", "hors_clipping") or x.cellules.get(_url_cle(info.get("url"))):
            continue
        v = x.visites(lid)
        if not v:
            continue                                                     # 0 ou non mesuré : rien à dire (jamais un faux 0)
        quoi = f"libéré (ex-{info.get('ancien') or '?'})" if cat == "libere" else f"hors clipping « {info.get('hors_clipping') or x.notes.get(lid) or ''} »"
        out.append(_a("C8", "info" if cat == "libere" else "important",
                      f"{(x.cr_lien(info) or '?').title()} · lien « {_slug(info.get('url'))} » {quoi} : {v} visite(s) payable(s) sur 7 j, "
                      "portées par aucune ligne", f"C8|{lid}"))
    return out


def _c9(x: _Ctx) -> list:
    out = []
    for lid, info in sorted(x.liens.items()):
        if lid not in x.notes or info.get("supprime_gaml"):
            continue
        note = str(x.notes.get(lid) or "").strip()
        if not note:
            continue
        m = _RE_CLIPPING.match(note)
        prenom_note = _premier(m.group(1)) if m else ""
        uid = str(info.get("uid") or "")
        tete = f"{(x.cr_lien(info) or '?').title()} · lien « {_slug(info.get('url'))} » note « {note} »"
        probleme = ""
        if uid:
            qui = x.nom(uid)
            attendu = x.prenom_de(uid)
            if not m:
                probleme = f"attribué à {qui} mais la note n'est plus « Clipping … » (sorti du clipping à la main ?)"
            elif prenom_note == "libre":
                probleme = f"attribué à {qui} mais noté libre dans GAML"
            elif attendu and prenom_note != attendu:
                probleme = f"attribué à {qui} : l'app et le rapport le donnent à « {m.group(1).strip()} »"
        elif info.get("libere") and not info.get("hors_clipping") and m and prenom_note != "libre":
            ancien = _premier(re.sub(r"^\s*clipping\s+", "", _n(info.get("ancien")))) if info.get("ancien") else ""
            if prenom_note != ancien:
                probleme = f"libéré dans le bot (ex-{info.get('ancien') or '?'}) mais la note le donne à « {m.group(1).strip()} »"
        elif _categorie(info) == "page" and m and prenom_note not in STAFF | {"libre"}:
            probleme = "« Clipping … » jamais attribué par le bot (homonymes ou prénom inconnu : `!lien`)"
        if probleme:
            out.append(_a("C9", "important", f"{tete} : {probleme}", f"C9|{lid}"))
    return out


def _c10(x: _Ctx) -> list:
    bios = ((x.etats or {}).get("bios") or {}) if isinstance(x.etats, dict) else {}
    if not bios:
        return []
    limite = x.maintenant.date() - timedelta(days=BIO_JOURS)
    out = []
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        bio = bios.get(h) if h else None
        if not isinstance(bio, dict) or (_date(bio.get("jour")) or date.min) < limite:
            continue
        genre, uid, cands = x.resoudre(c.get("gerant"))
        cr = _cr_ligne(c)
        urls = [str(u) for u in bio.get("liens") or [] if str(u or "").strip()]
        gaml = [(u, x.lid_url(u)) for u in urls if x.lid_url(u)]
        autres = [u for u in urls if not x.lid_url(u)]
        probs = []
        for u, lid in gaml:
            info = x.liens[lid]
            cat = _categorie(info)
            uid_l = str(info.get("uid") or "")
            if cat in ("supprime", "desactive"):
                probs.append(("info" if genre == "libre" else "bloquant", f"lien « {_slug(u)} » {'effacé' if cat == 'supprime' else 'désactivé'} "
                                                                           "dans GAML (visites perdues)"))
            elif cat == "attribue":
                if (genre == "membre" and uid_l == uid) or (genre == "ambigu" and uid_l in cands):
                    if x.cr_lien(info) and x.cr_lien(info) != cr:
                        probs.append(("important", f"son lien {x.cr_lien(info).title()} « {_slug(u)} » sur un compte {cr.title()}"))
                elif genre == "fantome" and x.prenom_lien(lid) == _premier(c.get("gerant")):
                    continue                                             # le lien du Gérant fantôme lui-même : C2 le dit déjà
                elif genre != "inconnu":
                    probs.append(("bloquant", f"lien de {x.nom(uid_l)} « {_slug(u)} » : ses visites lui sont payées depuis un compte qui "
                                              "n'est pas le sien"))
            elif cat == "libere":
                probs.append(("info" if genre == "libre" else "important",
                              f"lien libéré « {_slug(u)} » (ex-{info.get('ancien') or '?'}) : visites payées à personne"))
            elif cat == "hors_clipping":
                if genre in ("membre", "ambigu"):
                    probs.append(("important", f"lien hors clipping « {_slug(u)} » au lieu du sien"))
            elif genre in ("membre", "ambigu"):
                probs.append(("important", f"page de la créatrice « {_slug(u)} » au lieu de son lien (clics non attribuables)"))
        if genre == "membre" and not gaml:
            # un compte de croissance qui renvoie vers le compte privé (lien Instagram) est dans la règle : jamais signalé
            externes = [u for u in autres if not _RE_INSTAGRAM.search(_hote(u))]
            if onboarding._est_prive(c) and x.voulu(uid, cr) and x.lien_du(uid, cr):
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
        ecartes = [e for c in cs for e in c.get("doublons_ecartes") or []]
        if len(cs) < 2 and not ecartes:
            continue
        ou = [f"{c.get('onglet') or '?'} l. {c.get('ligne') or '?'} ({str(c.get('gerant') or '').strip() or 'sans Gérant'})" for c in cs]
        ou += [f"{e[0]} l. {e[1]} (écartée : invisible au bot)" if isinstance(e, (list, tuple)) and len(e) >= 2 else f"{e} (écartée)"
               for e in ecartes]
        out.append(_a("C11", "bloquant", f"@{cs[0]['handle']} sur {len(ou)} lignes : " + " · ".join(ou)
                      + " — une seule est lue, scannée et comptée", f"C11|{h}"))
    return out


def _c12(x: _Ctx) -> list:
    etats = x.etats if isinstance(x.etats, dict) else {}
    historique = etats.get("historique") or {}
    non_lus = etats.get("non_lus") or {}
    dp = etats.get("dernier_passage") or {}
    series = ((x.series or {}).get("comptes") or {}) if isinstance(x.series, dict) else {}
    alias = ((x.series or {}).get("alias") or {}) if isinstance(x.series, dict) else {}
    if not (historique or non_lus or dp or series):
        return []                                                        # aucune donnée de scan : rien à juger
    listes = {k: set(dp.get(k) or []) for k in ("non_lus", "restreints", "suspects", "reels_non_lus")}
    out, vus = [], set()
    for c in x.comptes:
        h = _cle_compte(c.get("handle"))
        if not h or (h, _n(c.get("onglet"))) in vus or _ban(c) or _perdu(c):
            continue
        vus.add((h, _n(c.get("onglet"))))
        if _a_creer(c) and x.resoudre(c.get("gerant"))[0] == "libre":
            continue                                                     # jamais scanné, par construction
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
            raisons.append(("important", "jamais lu par le scan (ligne ajoutée depuis le passage, onglet ou colonne non reconnus ?)"))
        if not raisons:
            continue
        grav = min((g for g, _ in raisons), key=GRAVITES.index)
        out.append(_a("C12", grav, f"{_ou(c)} · {_qui(c)} : " + " ; ".join(t for _, t in raisons), f"C12|{_n(c.get('onglet'))}|{h}"))
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
    """Les notes GAML vivantes que l'onboarding a déjà relues aujourd'hui (aucun appel GAML ici)."""
    cache = getattr(onboarding, "_details_gaml", None) or {}
    return list(cache.get("liens") or []) if cache.get("jour") == datetime.now(timezone.utc).strftime("%Y-%m-%d") else []


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
    notes GAML du jour, premiers signalements. Lecture seule ; une source absente vaut {}."""
    lj = _dep("lire_json")
    def _lu(cle, nom):
        v = _lire_fichier(cle, nom, {})
        return v if isinstance(v, dict) else {}
    clics = _lu("FICHIER_CLICS", "clics.json")
    onb = _lu("FICHIER_ONBOARDING", "onboarding.json")
    registre = _lu("FICHIER_EQUIPES", "equipes.json")
    return {"clics": clics, "onboarding_etat": onb, "registre": registre, "membres": _membres_connus(registre, onb, clics) if lj else {},
            "series_etat": _lu("FICHIER_SERIES", "series_comptes.json"), "etats": _lu("FICHIER_ETATS", "etats_comptes.json"),
            "parcours": _lu("FICHIER_PARCOURS", "parcours.json"), "details_gaml": _details_en_cache(),
            "premiers_vus": (_lu("FICHIER_CONTROLE", "controle.json").get("premiers_vus") or {})}


# ------------------------------------------------------------------ API du contrat C3
def anomalies(comptes, clics, onboarding_etat, registre, membres, series_etat, *, etats=None, parcours=None,
              details_gaml=None, premiers_vus=None, maintenant: datetime = None) -> list:
    """Les anomalies d'attribution, triées (bloquant, important, info ; puis famille), une par clé stable. Pure sur ses entrées.
    09/10 (dashboard) : `membres` = {uid: pseudo} (ou membres Discord, ou paires) des membres présents sur le serveur ; `etats`
    (etats_comptes.json : bios, non_lus, historique, dernier_passage), `parcours` (parcours.json), `details_gaml` ([{id, url, note}]
    du jour) et `premiers_vus` ({clé: iso}) sont lus dans les fichiers du bot quand ils ne sont pas passés et que le module est
    configuré ; sans eux, C10 et C12 se taisent, C5 juge tout clipper comme un ancien, C1 n'a pas de date."""
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
             premiers_vus if premiers_vus is not None else (_defaut("premiers_vus") or {}), maintenant)
    out, cles = [], set()
    for famille in (_c1, _c2_c3, _c4, _c5, _c6, _c7, _c8, _c9, _c10, _c11, _c12):
        try:
            trouvees = famille(x)
        except Exception as erreur:                                      # noqa: BLE001 — une famille cassée n'éteint pas les autres
            journal.warning("Contrôle %s : %s", famille.__name__, erreur)
            continue
        for a in trouvees:
            if a["cle"] not in cles:
                cles.add(a["cle"])
                out.append(a)
    out.sort(key=lambda a: (GRAVITES.index(a["gravite"]), int(a["famille"][1:]), a["texte"]))
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


def bouclage(clics, lignes_attribuees, fin: date = None, jours: int = 7) -> dict:
    """09/10 (dashboard) : la preuve que rien ne se perd. Visites payables des `jours` derniers jours (jusqu'à hier, heure de
    Paris) de TOUS les liens actifs (ni désactivés, ni effacés) = attribuées aux lignes + pages de créatrice + libérés / hors
    clipping + écart. L'écart (attendu : 0) = les liens attribués à un clipper que portent aucune ligne, listés dans `non_comptes`.
    Un lien au relevé incomplet n'entre dans aucune somme : il est listé dans `non_mesures` (jamais un faux 0)."""
    clics = clics if isinstance(clics, dict) else {}
    fin = fin or _hier_paris()
    sur_lignes = _lids_de(lignes_attribuees, clics)
    out = {"debut": (fin - timedelta(days=jours - 1)).isoformat(), "fin": fin.isoformat(), "total": 0, "lignes": 0, "pages": 0,
           "liberes": 0, "ecart": 0, "non_comptes": [], "non_mesures": [], "liens": 0}
    for lid, info in sorted(((str(k), v) for k, v in (clics.get("liens") or {}).items() if isinstance(v, dict))):
        cat = _categorie(info)
        if cat in ("desactive", "supprime"):
            continue
        out["liens"] += 1
        v = visites_7j(clics, lid, fin, jours)
        if v is None:
            out["non_mesures"].append({"lid": lid, "url": _slug(info.get("url")), "categorie": cat})
            continue
        out["total"] += v
        if lid in sur_lignes:
            out["lignes"] += v
        elif cat == "page":
            out["pages"] += v
        elif cat in ("libere", "hors_clipping"):
            out["liberes"] += v
        else:
            out["ecart"] += v
            out["non_comptes"].append({"lid": lid, "url": _slug(info.get("url")), "visites": v, "creatrice": str(info.get("creatrice") or ""),
                                       "note": str(info.get("note") or "")})
    out["non_comptes"].sort(key=lambda d: -d["visites"])
    return out


def compter(anomalies_: list) -> dict:
    """{famille: nombre} pour les 12 familles (zéros compris), dans l'ordre C1 → C12."""
    out = {f: 0 for f in FAMILLES}
    for a in anomalies_ or []:
        if a.get("famille") in out:
            out[a["famille"]] += 1
    return out


def empreinte(anomalies_: list) -> str:
    """L'empreinte de ce qui mérite un message : les clés des anomalies bloquantes et importantes (pas leurs textes, qui portent
    des chiffres qui bougent ; pas les « info »)."""
    cles = sorted(a["cle"] for a in anomalies_ or [] if a.get("gravite") in ("bloquant", "important"))
    return hashlib.sha1("\n".join(cles).encode("utf-8")).hexdigest()[:16]


def texte_admin(anomalies_: list) -> str:
    """Le message du salon admin (lu sur téléphone : blocs courts, une ligne vide entre chaque bloc)."""
    an = list(anomalies_ or [])
    if not an:
        return "🧭 **Contrôle d'attribution** : 0 anomalie, chaque compte et chaque lien est attribué."
    n = {g: sum(1 for a in an if a["gravite"] == g) for g in GRAVITES}
    tete = (f"🧭 **Contrôle d'attribution** : {len(an)} anomalie(s) — {n['bloquant']} bloquante(s), {n['important']} importante(s), "
            f"{n['info']} info. Rien n'est corrigé : à trancher dans le classeur ou dans GAML.")
    blocs = [tete]
    reste = LIMITE_TEXTE - len(tete) - 200
    for g, titre in (("bloquant", "**⛔ Bloquant**"), ("important", "**⚠️ Important**")):
        lignes = [f"· {a['famille']} {a['texte']}" for a in an if a["gravite"] == g]
        if not lignes:
            continue
        gardees = []
        for l in lignes:
            l = l if len(l) <= 300 else l[:297] + "…"
            if reste - len(l) - 1 < 0:
                break
            gardees.append(l)
            reste -= len(l) + 1
        bloc = titre + "\n\n" + "\n".join(gardees)
        if len(gardees) < len(lignes):
            bloc += f"\n… et {len(lignes) - len(gardees)} autre(s) (Dashboard, section Contrôle)"
        blocs.append(bloc)
    infos = compter([a for a in an if a["gravite"] == "info"])
    if n["info"]:
        blocs.append("**ℹ️ Info** : " + " · ".join(f"{f} ×{k}" for f, k in infos.items() if k))
    return "\n\n".join(blocs)[:LIMITE_TEXTE]


# ------------------------------------------------------------------ le tour de 15 min
def _lire_etat() -> dict:
    v = _lire_fichier("FICHIER_CONTROLE", "controle.json", {})
    return v if isinstance(v, dict) else {}


def _ecrire_etat(d: dict):
    ej, f = _dep("ecrire_json"), _fichier("FICHIER_CONTROLE", "controle.json")
    if ej and f is not None:
        ej(f, d)


async def passage(deps: dict = None, force: bool = False, comptes: list = None):
    """09/10 (dashboard) : appelé par la boucle de l'onboarding toutes les 15 min, après la colonne « Lien GAML associé ». Relit
    le classeur et les fichiers du bot, calcule les anomalies, garde la date du premier signalement de chacune (controle.json),
    et poste le texte au salon admin seulement si l'empreinte a changé (ou `force`). Renvoie le texte posté, sinon None."""
    if deps and not _deps:
        configurer(deps)
    if comptes is None:
        if not onboarding.actif():
            return None
        comptes = await onboarding.lire_comptes()
    maintenant = datetime.now(timezone.utc)
    e = lire_entrees()
    an = anomalies(comptes, e["clics"], e["onboarding_etat"], e["registre"], e["membres"], e["series_etat"], etats=e["etats"],
                   parcours=e["parcours"], details_gaml=e["details_gaml"], premiers_vus=e["premiers_vus"], maintenant=maintenant)
    etat = _lire_etat()
    avant = etat.get("empreinte")
    emp = empreinte(an)
    t_iso = maintenant.isoformat(timespec="minutes")
    pv = etat.get("premiers_vus") or {}
    etat.update({"t": t_iso, "n": compter(an), "premiers_vus": {a["cle"]: pv.get(a["cle"]) or t_iso for a in an}})
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
    journal.info("Contrôle d'attribution : %d anomalie(s) (%s)%s", len(an),
                 ", ".join(f"{f} {k}" for f, k in compter(an).items() if k) or "aucune", " — postée" if envoye else "")
    return texte if envoye else None
