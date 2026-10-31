"""Création des comptes jugée par Instagram seul, vue par RapidAPI (31/10/2026).

Gaëtan, 31/10 : « Ne juge que la création du compte Instagram par le scrapping RapidAPI. Quand tu sais que tu as délivré le compte
Instagram à un clipper, vérifie assez fréquemment s'il l'a créé ou pas… fais hyper attention à ce que la fiabilité du bot soit bonne
avec la clé RapidAPI » ; « Gère le problème entre le compte un et les comptes deux et trois, parce que c'est là que tous les clippers
lâchent. »

1. SUIVI (`passage`, à chaque tour léger du parcours, toutes les 10 minutes) : chaque @ remis à un clipper (message de son étape, ou
   remise de tous ses @) et pas encore créé est regardé sur Instagram (arobase_libre.examen : RapidAPI de Railway, relais du contrôle
   GitHub si la clé est refusée), d'autant plus souvent qu'il a été remis récemment (`intervalle_min`). Au plus PAR_TOUR examens par
   tour et QUOTA_JOUR par jour ; plus rien sous RESERVE requêtes RapidAPI restantes (annoncé par RapidAPI) : la clé garde de quoi
   vérifier les @ avant de les donner.
2. JUGEMENT (`juger`, pur) : le @ existe et (le bot l'a déjà vu libre, ou le profil est neuf, ou il prouve qu'il est à nous, ou le
   LOG le porte déjà créé : `log_dit_cree`) → créé ;
   il n'existe pas → pas encore ; il existe, installé, sans rien qui le relie à nous → le compte d'un inconnu (une ligne au salon
   admin, une fois : variante à donner) ; un doute (réponse muette, profil illisible jamais vu libre) → rien, nouvel essai.
3. CRÉÉ (`noter_cree`) : étape ouverte → elle se ferme comme au bouton (parcours.valider_etape, profil et suite) ; étape déjà passée
   (compte 2 parti à 48 h) → notée faite sans message ; étape pas encore ouverte (@ remis d'avance) → notée vue (« crees_ig »), LOG
   à GOOD, et l'étape se ferme d'elle-même dès qu'elle s'ouvre.
4. BOUTON (`confirmer`) : « ✅ Compte n créé » ne ferme plus rien sur la seule parole du clipper : le @ est regardé sur Instagram tout
   de suite ; pas vu → le clipper le sait, et le suivi le revérifie dans l'heure. CREATION_PAR_RAPIDAPI=0 rend l'ancien bouton.
5. RELANCES (`relances`) : compte 2 ou 3 toujours absent d'Instagram RELANCE_H heures après son heure → un message dans son salon,
   une fois ; TL_H heures → son TL est mentionné dans le salon, une fois. Le compte 1 a déjà sa règle (L6 : avertissement à 48 h).
6. FIABILITÉ DE LA CLÉ (`surveiller_cle`, chaque heure ; `ligne_digest`, chaque matin) : clé de Railway refusée (401/403) → une
   alerte au salon admin, au plus toutes les ALERTE_CLE_H heures, et une ligne quand elle revient ; quota RapidAPI restant sous
   ALERTE_QUOTA → une alerte par jour. Pendant une panne de NOTRE clé (refusée, absente, quota épuisé) sans réponse du contrôle
   GitHub, le bouton du clipper passe comme avant : un clipper n'est jamais bloqué par notre panne ; chaque appui accepté ainsi
   est compté et dit le matin. Le point du matin dit l'état de la clé, le quota restant et les regards de la veille.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

journal = logging.getLogger("suivi_creation")

ACTIF = os.environ.get("SUIVI_CREATION", "1").strip() != "0"
GARDE_BOUTON = os.environ.get("CREATION_PAR_RAPIDAPI", "1").strip() != "0"
PAR_TOUR = int(os.environ.get("SUIVI_CREATION_PAR_TOUR", "12") or 12)
QUOTA_JOUR = int(os.environ.get("SUIVI_CREATION_QUOTA_JOUR", "400") or 400)
RESERVE = int(os.environ.get("SUIVI_CREATION_RESERVE", "2000") or 2000)
RELANCE_H = int(os.environ.get("SUIVI_CREATION_RELANCE_H", "24") or 24)
TL_H = int(os.environ.get("SUIVI_CREATION_TL_H", "48") or 48)

ALERTE_CLE_H = int(os.environ.get("SUIVI_CREATION_ALERTE_CLE_H", "6") or 6)
ALERTE_QUOTA = int(os.environ.get("SUIVI_CREATION_ALERTE_QUOTA", "5000") or 5000)
FICHIER = Path(os.environ.get("DONNEES_DIR", Path(__file__).with_name("donnees"))) / "suivi_creation.json"
GARDE_JOURS = 14

CREE, PAS_CREE, INSTALLE, DOUTE = "créé", "pas créé", "compte d'un inconnu", "doute"
_jour = {"jour": "", "n": 0}
_deps: dict = {}
_alertes = {"cle": None, "quota": ""}


def configurer(deps: dict):
    """deps : canal_admin (coroutine → salon admin) ; tl_de(uid, creatrice) → id du TL ou '' (par défaut : la même résolution que
    la demande de groupe au TL, onboarding_preuves.tl_pour)."""
    _deps.update(deps)


def _tl_de(uid: str, creatrice: str) -> str:
    if _deps.get("tl_de"):
        return str(_deps["tl_de"](uid, creatrice) or "")
    import equipes_tl
    import onboarding_preuves
    return str(onboarding_preuves.tl_pour(uid, creatrice, equipes_tl.tl_par_va(), equipes_tl._fiches()) or "")


def _instant(v):
    try:
        d = datetime.fromisoformat(str(v))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def intervalle_min(age_h: float) -> int:
    """Pur : le temps entre deux regards sur Instagram pour un @ remis il y a `age_h` heures. Le jour de la remise, toutes les
    heures (le clipper crée d'habitude dans la journée) ; jusqu'à 3 jours, toutes les 3 h ; jusqu'à 10 jours, toutes les 8 h ;
    ensuite une fois par jour."""
    if age_h < 24:
        return 60
    if age_h < 72:
        return 180
    if age_h < 240:
        return 480
    return 1440


def juger(ex: dict, libre_vu: bool = False) -> str:
    """Pur : ce que dit Instagram d'un @ remis à un clipper (ex = arobase_libre.examen)."""
    import arobase_libre as a
    v = (ex or {}).get("verdict")
    if v == a.LIBRE:
        return PAS_CREE
    if v != a.PRIS:
        return DOUTE
    if libre_vu or ex.get("a_nous") or ex.get("neuf"):
        return CREE
    if ex.get("profil_lu") is False:
        return DOUTE                                                    # privé ou illisible, jamais vu libre : on ne conclut pas
    return INSTALLE


def remis(f: dict, n: int, h: str):
    """Pur : l'heure à laquelle le @ `h` du compte n a été remis au clipper (message de son étape, ou remise de tous ses @), et
    l'heure à partir de laquelle il doit le créer ; (None, None) s'il ne l'a pas encore reçu."""
    import onboarding
    dates = f.get("dates") or {}
    don = (f.get("donnes") or {}).get(str(n)) or {}
    moments, a_partir = [], []
    if dates.get(str(n)):
        moments.append(_instant(dates[str(n)]))
        a_partir.append(_instant(dates[str(n)]))
    if don and onboarding.normaliser_handle(don.get("handle")).lower() == onboarding.normaliser_handle(h).lower():
        moments.append(_instant(don.get("le")))
        a_partir.append(_instant(don.get("a_partir_de")) or _instant(don.get("le")))
    moments = [m for m in moments if m is not None]
    a_partir = [m for m in a_partir if m is not None]
    return (min(moments) if moments else None), (min(a_partir) if a_partir else None)


def a_verifier(d: dict, comptes_de, maintenant: datetime, sortis=frozenset()) -> list:
    """Pur : [(uid, n, @, âge en heures, déjà_vu)] des @ remis et pas encore créés dont le prochain regard est dû ; d'abord ceux
    déjà vus créés (aucun appel : leur étape vient de s'ouvrir), puis l'étape en cours, puis le plus récent. `comptes_de(uid, f)` :
    les @ du clipper dans l'ordre du parcours."""
    import onboarding
    import parcours
    out = []
    for uid, f in (d or {}).items():
        if not isinstance(f, dict) or str(uid) in sortis or f.get("sorti"):
            continue
        comptes = comptes_de(uid, f) or []
        for n in (1, 2, 3):
            if n > len(comptes) or not comptes[n - 1] or parcours._cree(f, n) or (f.get("profils") or {}).get(str(n)):
                continue                                                # créé, ou profil déjà parti (le privé attend « Profil fait »)
            h = onboarding.normaliser_handle(comptes[n - 1]).lower()
            vu = (f.get("crees_ig") or {}).get(str(n)) or {}
            if vu.get("h") == h:
                if int(f.get("etape", 0) or 0) == n and (f.get("dates") or {}).get(str(n)):
                    out.append((str(uid), n, h, 0.0, True))
                continue
            quand, _ = remis(f, n, h)
            if quand is None:
                continue
            age = max(0.0, (maintenant - quand).total_seconds() / 3600)
            dernier = (f.get("verif_ig") or {}).get(str(n)) or {}
            le = _instant(dernier.get("le")) if dernier.get("h") == h else None
            # compte d'un inconnu : dit une fois, puis regardé une fois par jour seulement (le LOG peut le dire créé entre-temps)
            attente = 1440 if (dernier.get("h") == h and dernier.get("installe")) else intervalle_min(age)
            if le is not None and maintenant - le < timedelta(minutes=attente):
                continue
            out.append((str(uid), n, h, age, False))
    ouverte = {u: int((d.get(u) or {}).get("etape", 0) or 0) for u, *_ in out}
    return sorted(out, key=lambda x: (not x[4], ouverte.get(x[0]) != x[1], x[3]))


def _budget_ok() -> bool:
    import instagram_rapidapi as ig
    j = datetime.now(timezone.utc).date().isoformat()
    if _jour["jour"] != j:
        _jour.update({"jour": j, "n": 0})
    if _jour["n"] >= QUOTA_JOUR:
        return False
    restant = ig._jour.get("restant")
    return restant is None or restant > RESERVE


def _jour_paris(maintenant: datetime):
    try:
        from zoneinfo import ZoneInfo
        return maintenant.astimezone(ZoneInfo("Europe/Paris")).date()
    except Exception:                                                   # noqa: BLE001 — sans base des fuseaux : UTC
        return maintenant.astimezone(timezone.utc).date()


def _lire_stats() -> dict:
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def compter(quoi: str, k: int = 1, maintenant: datetime = None) -> None:
    """Le compteur du jour (Paris) : examens, crees, relances, relances_tl, boutons_refuses, boutons_sans_verif. GARDE_JOURS jours
    gardés. Jamais d'exception (un compteur raté ne bloque rien)."""
    if k <= 0:
        return
    try:
        d = _lire_stats()
        jours = d.setdefault("jours", {})
        j = _jour_paris(maintenant or datetime.now(timezone.utc)).isoformat()
        jours.setdefault(j, {})
        jours[j][quoi] = int(jours[j].get(quoi, 0) or 0) + k
        for vieux in sorted(jours)[:-GARDE_JOURS]:
            jours.pop(vieux, None)
        FICHIER.parent.mkdir(parents=True, exist_ok=True)
        tmp = FICHIER.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FICHIER)
    except (OSError, ValueError, TypeError) as erreur:
        journal.info("Compteur du suivi des créations non écrit : %s", type(erreur).__name__)


def panne_cle(ex: dict) -> bool:
    """Vrai quand la réponse ne vient ni de notre clé ni du contrôle GitHub parce que NOTRE clé est en panne (absente, refusée,
    quota sous la réserve d'arobase_libre) : le doute est le nôtre, pas celui d'Instagram."""
    import arobase_libre as a
    import instagram_rapidapi as ig
    if (ex or {}).get("source") == "github" or (ex or {}).get("verdict") != a.INCONNU:
        return False
    return not a.actif() or a.cle_refusee() or not ig._quota_ok(a.RESERVE_QUOTA)


def _noter_verif(uid: str, n: int, h: str, ex: dict, jugement: str) -> bool:
    """Retient le regard dans la fiche (lecture-écriture sans attente) ; renvoie libre_vu (le @ a déjà été vu libre)."""
    import arobase_libre as a
    import parcours
    d = parcours._lire()
    f = d.get(uid)
    if not isinstance(f, dict):
        return False
    avant = (f.get("verif_ig") or {}).get(str(n)) or {}
    meme = avant.get("h") == h
    libre_vu = bool((meme and avant.get("libre_vu")) or (ex or {}).get("verdict") == a.LIBRE)
    f.setdefault("verif_ig", {})[str(n)] = {"h": h, "le": parcours._maintenant(), "v": jugement, "libre_vu": libre_vu,
                                           "k": (int(avant.get("k") or 0) if meme else 0) + 1,
                                           **({"installe": True} if jugement == INSTALLE else {})}
    parcours._ecrire(d)
    return libre_vu


_log = {"le": None, "etats": {}}
LOG_CACHE_MIN = 30


async def log_dit_cree(h: str) -> bool:
    """Le LOG DASHBOARD IG (qui fait foi) porte ce @ dans un état créé (tout sauf « à créer ») : un compte grossi depuis sa création
    (plus « neuf », bio sans preuve) n'est jamais pris pour le compte d'un inconnu. LOG relu au plus toutes les LOG_CACHE_MIN
    minutes, seulement quand un @ en a besoin. Faux si le LOG est illisible (dans le doute, rien n'est conclu de lui)."""
    import onboarding
    maintenant = datetime.now(timezone.utc)
    if _log["le"] is None or maintenant - _log["le"] > timedelta(minutes=LOG_CACHE_MIN):
        try:
            lignes = await onboarding.lire_comptes()
            _log["etats"] = {onboarding.normaliser_handle(c.get("handle")).lower(): onboarding._norm(c.get("etat") or "")
                             for c in lignes or [] if c.get("handle")}
            _log["le"] = maintenant
        except Exception as erreur:                                     # noqa: BLE001
            journal.info("LOG illisible pour le suivi des créations : %s", type(erreur).__name__)
            return False
    e = _log["etats"].get(onboarding.normaliser_handle(h).lower(), "")
    return bool(e) and e not in ("a creer", "à créer")


def libre_vu(uid: str, n: int, h: str) -> bool:
    import arobase_libre as a
    import parcours
    v = ((parcours._lire().get(str(uid)) or {}).get("verif_ig") or {}).get(str(n)) or {}
    return bool((v.get("h") == h and v.get("libre_vu")) or a.vu_libre(h))


async def _marquer_log(uid: str, h: str) -> None:
    """Le compte vu créé : registre (place notée créée) et LOG à GOOD, chacun de son côté (l'un ne bloque jamais l'autre)."""
    import onboarding
    import parcours
    registre = onboarding.process_adapters.store()
    try:
        if registre.owner_for_handle(h) is None:
            registre.reserve(uid, [h])
        registre.created(uid, h, "vu-sur-instagram-rapidapi:" + parcours._maintenant())
    except Exception as erreur:                                         # noqa: BLE001 — le LOG suit quand même
        journal.info("Registre, création de %s : %s", h, erreur)
    marquer = parcours._deps.get("marquer_etat")
    if marquer is not None:
        try:
            await marquer(h, "GOOD")
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("LOG, %s à GOOD : %s", h, erreur)


async def noter_cree(client, uid: str, n: int, h: str) -> str:
    """Le compte n de ce clipper existe sur Instagram : la suite du parcours, sans attendre le bouton. Renvoie une ligne de bilan."""
    import parcours
    d = parcours._lire()
    f = d.get(uid)
    if not isinstance(f, dict) or parcours._cree(f, n):
        return ""
    dates = f.get("dates") or {}
    salon = client.get_channel(int(f.get("salon_id") or 0)) if client is not None and str(f.get("salon_id") or "").isdigit() else None
    prenom = f.get("prenom") or uid
    if int(f.get("etape", 0) or 0) == n and dates.get(str(n)):
        if salon is None:
            return ""
        await parcours.valider_etape(salon, uid, n, par="rapidapi", creation=True)
        apres = parcours._lire().get(uid) or {}
        if parcours._cree(apres, n) or (apres.get("profils") or {}).get(str(n)):
            return f"✅ {prenom} : compte {n} @{h} vu sur Instagram, étape fermée"
        return ""
    if dates.get(str(n)):                                               # étape passée (compte 2 parti à 48 h) : notée, sans message
        if n == 1 and salon is not None:
            await parcours.valider_etape(salon, uid, 1, par="rapidapi", creation=True)   # le « compte 1 en retard » du 24/10
            if parcours._cree(parcours._lire().get(uid) or {}, 1):
                return f"✅ {prenom} : compte 1 @{h} vu sur Instagram (en retard), noté"
        d = parcours._lire()
        f = d.get(uid) or {}
        if parcours._cree(f, n):
            return ""
        f.setdefault("dates", {})[f"{n}_fait"] = parcours._maintenant()
        parcours._ecrire(d)
        if salon is not None:
            await parcours._retirer_bouton(salon, (f.get("messages") or {}).get(str(n)))
        await _marquer_log(uid, h)
        return f"✅ {prenom} : compte {n} @{h} vu sur Instagram, noté sans message"
    f.setdefault("crees_ig", {})[str(n)] = {"h": h, "le": parcours._maintenant()}
    parcours._ecrire(d)
    await _marquer_log(uid, h)
    return f"✅ {prenom} : compte {n} @{h} déjà créé (vu sur Instagram), son étape se fermera dès qu'elle s'ouvre"


async def passage(client, maintenant=None) -> list:
    """Un tour du suivi : les @ dus, regardés sur Instagram, les créés notés. Jamais d'exception. Renvoie les lignes de bilan."""
    if not ACTIF:
        return []
    import arobase_libre as a
    import onboarding
    import parcours
    maintenant = maintenant or datetime.now(timezone.utc)
    try:
        sortis = {u for u, x in (onboarding._lire_etat().get("clippers") or {}).items() if (x or {}).get("sorti")}
    except Exception:                                                   # noqa: BLE001
        sortis = set()
    bilan, examines = [], 0
    for uid, n, h, age, deja_vu in a_verifier(parcours._lire(), lambda u, f: parcours._comptes_ordonnes(u, fiche_p=f),
                                              maintenant, frozenset(sortis)):
        try:
            if deja_vu:
                ligne = await noter_cree(client, uid, n, h)
                if ligne:
                    bilan.append(ligne)
                continue
            if examines >= PAR_TOUR or not _budget_ok():
                break
            if not a.actif() and not a.CI_SEUL:
                break
            f = parcours._lire().get(uid) or {}
            ex = await a.examen(h, f.get("creatrice") or "")
            examines += 1
            _jour["n"] += 1
            vu = libre_vu(uid, n, h)
            avant = (f.get("verif_ig") or {}).get(str(n)) or {}
            deja_dit = avant.get("h") == h and bool(avant.get("installe"))
            jugement = juger(ex, vu)
            if jugement == INSTALLE and await log_dit_cree(h):
                jugement = CREE                                         # grossi depuis sa création : le LOG fait foi
            _noter_verif(uid, n, h, ex, jugement)
            if jugement == CREE:
                ligne = await noter_cree(client, uid, n, h)
                if ligne:
                    bilan.append(ligne)
                    compter("crees")
            elif jugement == INSTALLE and not deja_dit:
                bilan.append(f"⚠️ {f.get('prenom') or uid} : son compte {n} @{h} est le compte d'un inconnu "
                             f"({ex.get('abonnes', '?')} abonnés, {ex.get('publications', '?')} publications) : variante à donner "
                             "(`!remise-arobases`)")
        except Exception as erreur:                                     # noqa: BLE001 — le @ suivant passe quand même
            journal.warning("Suivi des créations, %s compte %s : %s", uid, n, type(erreur).__name__)
    compter("examens", examines)
    if bilan:
        journal.info("Suivi des créations (%s examen(s), %s aujourd'hui) : %s", examines, _jour["n"], " · ".join(bilan))
        await _dire_admin("🔎 **Comptes vus sur Instagram**\n" + "\n".join(bilan))
    return bilan


async def _dire_admin(texte: str) -> None:
    if not _deps.get("canal_admin"):
        return
    try:
        canal = await _deps["canal_admin"]()
        if canal is not None:
            await canal.send(texte[:1990])
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Salon admin : %s", type(erreur).__name__)


# --------------------------------------------------------------------------------------------- le bouton « ✅ Compte n créé »
TEXTE_PAS_VU = ("🔎 Je ne vois pas encore `@{h}` sur Instagram.\n\n"
                "Vérifie que ton compte {n} porte exactement ce @. Instagram l'a changé ? Écris ici ton @ exact.\n\n"
                "Je revérifie tout seul dans l'heure : la suite part dès que je le vois.")
TEXTE_MUET = ("⏳ Instagram ne me répond pas pour l'instant.\n\n"
              "Je revérifie `@{h}` tout seul dans l'heure : rien à refaire de ton côté.")
TEXTE_INCONNU = ("⚠️ `@{h}` est un compte qui existait déjà (pas le tien).\n\n"
                 "Écris ici le @ exact du compte que tu as créé, ou dis-le à ton TL.")


async def confirmer(uid: str, n: int, h: str) -> tuple:
    """(True, '') si Instagram montre le compte créé ; (False, message pour le clipper) sinon. Sans garde (CREATION_PAR_RAPIDAPI=0)
    ou sans aucun moyen de vérifier (ni clé ni relais GitHub) : (True, '') — l'ancien bouton."""
    import arobase_libre as a
    import onboarding
    import parcours
    h = onboarding.normaliser_handle(h).lower()
    if not GARDE_BOUTON or not a.ACTIVE or (not a.actif() and not a.CI_SEUL):
        return True, ""
    f = parcours._lire().get(str(uid)) or {}
    ex = await a.examen(h, f.get("creatrice") or "")
    _jour["n"] += 1
    compter("examens")
    jugement = juger(ex, libre_vu(uid, n, h))
    if jugement == INSTALLE and await log_dit_cree(h):
        jugement = CREE
    _noter_verif(str(uid), n, h, ex, jugement if jugement != INSTALLE else DOUTE)
    if jugement == CREE:
        compter("crees")
        return True, ""
    if jugement == DOUTE and panne_cle(ex):
        # notre clé est en panne et le contrôle GitHub ne connaît pas ce @ : jamais un clipper bloqué par notre panne
        compter("boutons_sans_verif")
        journal.warning("Bouton du compte %s de %s accepté sans vérification : clé RapidAPI indisponible", n, uid)
        return True, ""
    compter("boutons_refuses")
    if jugement == PAS_CREE:
        _revoir_vite(str(uid), n)
        return False, TEXTE_PAS_VU.format(h=h, n=n)
    if jugement == INSTALLE:
        return False, TEXTE_INCONNU.format(h=h)
    _revoir_vite(str(uid), n)
    return False, TEXTE_MUET.format(h=h)


def _revoir_vite(uid: str, n: int) -> None:
    """Le prochain regard dans 15 minutes environ, quel que soit l'âge du @ (le clipper dit l'avoir créé)."""
    import parcours
    d = parcours._lire()
    v = ((d.get(uid) or {}).get("verif_ig") or {}).get(str(n))
    if isinstance(v, dict):
        v["le"] = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(timespec="seconds")
        parcours._ecrire(d)


# --------------------------------------------------------------------------------------------- relances : clipper, puis TL
TEXTE_RELANCE = ("⏰ <@{uid}> Ton compte {n} `@{h}` n'existe pas encore sur Instagram.\n\n"
                 "Crée-le aujourd'hui, avec ton e-mail et ton mot de passe.\n\n"
                 "Identifiant pas disponible ? Change le point en tiret du bas ou ajoute xo à la fin. Puis écris ici ton @ exact.")
TEXTE_RELANCE_TL = ("👥 Hello <@{tl}> ! {prenom} n'a pas encore créé son compte {n} (`@{h}`), à faire depuis {jours}.\n\n"
                    "Un message de toi sur WhatsApp ?")


def a_relancer(d: dict, comptes_de, maintenant: datetime, sortis=frozenset()) -> list:
    """Pur : [(uid, n, @, quoi, heures)] : « clipper » (comptes 2 et 3, RELANCE_H h après leur heure) puis « tl » (TL_H h, tous les
    comptes), une fois chacun par @, jamais pour un @ vu créé ni pour le compte d'un inconnu, jamais avant que le suivi ait
    regardé le @ au moins une fois sans le voir."""
    import onboarding
    import parcours
    out = []
    for uid, f in (d or {}).items():
        if not isinstance(f, dict) or str(uid) in sortis or f.get("sorti"):
            continue
        comptes = comptes_de(uid, f) or []
        for n in (1, 2, 3):
            if n > len(comptes) or not comptes[n - 1] or parcours._cree(f, n):
                continue
            h = onboarding.normaliser_handle(comptes[n - 1]).lower()
            v = (f.get("verif_ig") or {}).get(str(n)) or {}
            if v.get("h") != h or v.get("v") != PAS_CREE or ((f.get("crees_ig") or {}).get(str(n)) or {}).get("h") == h:
                continue
            _, depuis = remis(f, n, h)
            if depuis is None:
                continue
            heures = (maintenant - depuis).total_seconds() / 3600
            faits = (f.get("relances_ig") or {}).get(str(n)) or {}
            if faits.get("h") not in (None, h):
                faits = {}
            if n in (2, 3) and heures >= RELANCE_H and not faits.get("clipper"):
                out.append((str(uid), n, h, "clipper", heures))
            elif heures >= TL_H and not faits.get("tl"):
                out.append((str(uid), n, h, "tl", heures))
    return out


async def relances(client, maintenant=None) -> list:
    """Passe horaire : les relances dues, envoyées dans le salon perso, notées avant l'envoi (jamais deux fois). Renvoie le bilan."""
    if not ACTIF:
        return []
    import onboarding
    import parcours
    maintenant = maintenant or datetime.now(timezone.utc)
    try:
        sortis = {u for u, x in (onboarding._lire_etat().get("clippers") or {}).items() if (x or {}).get("sorti")}
    except Exception:                                                   # noqa: BLE001
        sortis = set()
    faits = []
    for uid, n, h, quoi, heures in a_relancer(parcours._lire(), lambda u, f: parcours._comptes_ordonnes(u, fiche_p=f),
                                              maintenant, frozenset(sortis)):
        d = parcours._lire()
        f = d.get(uid) or {}
        salon = client.get_channel(int(f.get("salon_id") or 0)) if client is not None and str(f.get("salon_id") or "").isdigit() else None
        if salon is None:
            continue
        tl = ""
        if quoi == "tl":
            try:
                tl = _tl_de(uid, f.get("creatrice") or "")
            except Exception:                                           # noqa: BLE001
                tl = ""
        r = f.setdefault("relances_ig", {}).setdefault(str(n), {})
        if r.get("h") != h:
            r.clear()
            r["h"] = h
        r[quoi] = parcours._maintenant()
        parcours._ecrire(d)
        if quoi == "tl" and not tl:
            continue                                                    # sans TL : le digest du matin (bloqués) le liste déjà
        jours = f"{int(heures // 24)} jour{'s' if heures >= 48 else ''}" if heures >= 24 else f"{int(heures)} h"
        texte = (TEXTE_RELANCE.format(uid=uid, n=n, h=h) if quoi == "clipper"
                 else TEXTE_RELANCE_TL.format(tl=tl, prenom=parcours._prenom_affiche(f.get("prenom") or "Ton clipper"), n=n, h=h,
                                              jours=jours))
        try:
            await salon.send(texte[:1990])
            faits.append((uid, n, quoi))
            compter("relances" if quoi == "clipper" else "relances_tl")
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Relance %s du compte %s de %s : %s", quoi, n, uid, type(erreur).__name__)
    if faits:
        journal.info("Relances des comptes à créer : %s", ", ".join(f"{u} compte {n} ({q})" for u, n, q in faits))
    return faits


# --------------------------------------------------------------------------------------------- fiabilité de la clé RapidAPI
def alertes_dues(etat: dict, refusee: bool, restant, maintenant: datetime) -> list:
    """Pur sur `etat` (modifié en place) : les alertes à poster maintenant. Clé refusée : une alerte, répétée au plus toutes les
    ALERTE_CLE_H heures tant que ça dure, puis une ligne quand elle revient ; quota restant sous ALERTE_QUOTA : une alerte par jour."""
    out = []
    if refusee:
        dernier = _instant(etat.get("cle"))
        if dernier is None or maintenant - dernier >= timedelta(hours=ALERTE_CLE_H):
            etat["cle"] = maintenant.isoformat(timespec="seconds")
            etat.setdefault("cle_depuis", etat["cle"])
            out.append("⛔ **Clé RapidAPI de Railway refusée** (401/403).\n"
                       "Le suivi des créations et le contrôle des @ passent par le contrôle GitHub (toutes les ~4 h). "
                       "Les boutons « Compte créé » passent sans vérification tant que ça dure.\n"
                       "→ Vérifier l'abonnement FlashAPI de la clé `RAPIDAPI_KEY` (Railway), puis `!verifier`.")
    elif etat.get("cle_depuis"):
        out.append(f"✅ Clé RapidAPI de Railway de nouveau acceptée (refusée depuis {str(etat['cle_depuis'])[:16].replace('T', ' ')} UTC).")
        etat.pop("cle_depuis", None)
        etat.pop("cle", None)
    jour = maintenant.date().isoformat()
    if isinstance(restant, int) and restant < ALERTE_QUOTA and etat.get("quota") != jour:
        etat["quota"] = jour
        out.append(f"⚠️ **Quota RapidAPI bas** : {restant} requêtes restantes.\n"
                   f"Sous {RESERVE}, le suivi des créations s'arrête (le contrôle des @ avant remise garde sa part).\n"
                   "→ Monter le forfait FlashAPI ou attendre la remise à zéro du mois.")
    return out


async def surveiller_cle(maintenant: datetime = None) -> list:
    """Passe horaire : les alertes de la clé au salon admin. Jamais d'exception. Renvoie les alertes postées."""
    try:
        import arobase_libre as a
        import instagram_rapidapi as ig
        maintenant = maintenant or datetime.now(timezone.utc)
        refusee = a.ACTIVE and bool(ig.CLE) and a.cle_refusee()
        lignes = alertes_dues(_alertes, refusee, ig._jour.get("restant"), maintenant)
        for texte in lignes:
            journal.warning("Clé RapidAPI : %s", texte.splitlines()[0])
            await _dire_admin(texte)
        return lignes
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Surveillance de la clé RapidAPI : %s", type(erreur).__name__)
        return []


def ligne_digest(maintenant: datetime = None) -> str:
    """La ligne du point du matin : l'état de la clé, le quota restant, les regards et créations vus hier. '' si éteint."""
    if not ACTIF:
        return ""
    try:
        import arobase_libre as a
        import instagram_rapidapi as ig
        maintenant = maintenant or datetime.now(timezone.utc)
        if not a.ACTIVE:
            cle = "contrôle des @ éteint (AROBASE_VERIF=0)"
        elif not a.actif():
            cle = "⛔ pas de clé sur Railway (contrôle GitHub seul)"
        elif a.cle_refusee():
            cle = "⛔ clé de Railway refusée (contrôle GitHub en relais)"
        else:
            cle = "clé OK"
        restant = ig._jour.get("restant")
        quota = f" · {restant:,} requêtes restantes".replace(",", " ") if isinstance(restant, int) else ""
        hier = (_jour_paris(maintenant) - timedelta(days=1)).isoformat()
        s = (_lire_stats().get("jours") or {}).get(hier) or {}
        morceaux = [f"{int(s.get('examens', 0) or 0)} @ regardé(s)", f"{int(s.get('crees', 0) or 0)} compte(s) vu(s) créé(s)"]
        if s.get("relances") or s.get("relances_tl"):
            morceaux.append(f"{int(s.get('relances', 0) or 0)} relance(s) clipper, {int(s.get('relances_tl', 0) or 0)} TL")
        if s.get("boutons_refuses"):
            morceaux.append(f"{int(s['boutons_refuses'])} bouton(s) « créé » refusé(s) (pas vu sur Instagram)")
        if s.get("boutons_sans_verif"):
            morceaux.append(f"⚠️ {int(s['boutons_sans_verif'])} bouton(s) accepté(s) sans vérification (clé en panne)")
        return f"🔑 **RapidAPI** : {cle}{quota}\n-# Hier : " + " · ".join(morceaux)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Ligne RapidAPI du matin : %s", type(erreur).__name__)
        return ""
