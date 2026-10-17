"""Attribution automatique des créatrices (27/09, décision de Gaëtan). Ordre final du 27/09 au soir, PONDÉRÉ :
« Chloé (3) > Sarah (3) > Sophie (3) > Jade (2) > Clara (1) > Maddie (1) » — trois nouveaux d'affilée chez Chloé, puis trois
chez Sarah, trois chez Sophie, deux chez Jade, un chez Clara, un chez Maddie, et on recommence. Dès qu'un clipper accepte
les règles, il reçoit la créatrice suivante de la séquence et tout ce que `!creatrice` faisait (salon perso, pseudo, rôles,
comptes du classeur, lien, alias 2FA, parcours). Au démarrage, les signés présents sans créatrice sont rattrapés un
par un, avec une pause entre deux.

09/10 (Gaëtan : « on va ouvrir les vannes ») : le quiz suffit pour entrer, le goulot devient le stock de comptes. Une créatrice sans
compte livrable est sautée ; si AUCUNE n'en a, le membre reçoit une fois le repli « Ta créatrice arrive ici dès qu'un compte est
prêt pour toi » (10/10 : plus de délai promis) et passe à l'état « attente_attribution » du pipeline. boucle_pipeline (bot_discord, toutes les 5 min) le reprend tout seul dès qu'un compte se
libère (`reprendre_attente`, la seule reprise, sous verrou), un par un, ATTRIBUTION_PAUSE_SEC entre deux, sans commande.

Ordre : ATTRIBUTION_ORDRE, « Créatrice:poids » séparés par des virgules (défaut « Sophie:5,Sarah:3,Clara:1,Jade:1,Maddie:1,Chloé:1 »
depuis le 14/10, appliqué une fois au déploiement par-dessus un ordre posé avant ; ATTRIBUTION_DECISION=0 l'empêche ; sans poids = 1). Une créatrice sans catégorie ni rôle sur le serveur est sautée (et dite au salon admin). Un
changement d'ordre remet le compteur au début. ATTRIBUTION_AUTO=0 éteint tout. État dans DONNEES/attribution.json."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import discord

journal = __import__("logging").getLogger("bot_clippers")

# 14/10 (Gaëtan, après la décision « Sophie d'abord ») : « Sophie 5, Sarah 3, Clara 1, Jade 1, Maddie 1, Chloé 1 ». Appliqué une fois au
# déploiement par-dessus tout ordre posé avant (`!attribution`, ATTRIBUTION_ORDRE) : voir DECISION_ORDRE dans configurer.
ORDRE_DECISION = "Sophie:5,Sarah:3,Clara:1,Jade:1,Maddie:1,Chloé:1"
DECISION_ORDRE = "2026-10-14"
ORDRE_TEXTE = os.environ.get("ATTRIBUTION_ORDRE", ORDRE_DECISION)
ORDRE, POIDS, SEQUENCE = [], {}, []


def definir_ordre(texte: str) -> list:
    """« Chloé:3,Sarah:3,Sophie:3,Jade:2,Clara:1,Maddie:1 » → ORDRE (noms uniques), POIDS, SEQUENCE (13 positions)."""
    global ORDRE_TEXTE
    ORDRE_TEXTE = texte
    ORDRE.clear(); POIDS.clear(); SEQUENCE.clear()
    for morceau in texte.split(","):
        nom, _, poids = morceau.strip().partition(":")
        nom = nom.strip()
        if not nom:
            continue
        try:
            n = max(0, int(poids.strip() or 1))                        # 30/09 : « Clara:0 » = exclue (avant, 0 valait 1)
        except ValueError:
            n = 1
        if n == 0:
            continue
        if nom not in ORDRE:
            ORDRE.append(nom)
        POIDS[nom] = POIDS.get(nom, 0) + n
    for nom in ORDRE:
        SEQUENCE.extend([nom] * POIDS[nom])
    return SEQUENCE


definir_ordre(ORDRE_TEXTE)


def ordre_texte() -> str:
    return " > ".join(f"{c} ×{POIDS[c]}" if POIDS[c] > 1 else c for c in ORDRE)
ACTIF = os.environ.get("ATTRIBUTION_AUTO", "1").strip() != "0"
PAUSE_SEC = int(os.environ.get("ATTRIBUTION_PAUSE_SEC", "90"))
_deps = {}


class _Par:
    display_name, id = "attribution automatique", "auto"


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, FICHIER_EQUIPES, categorie_de_creatrice, role_creatrice, onboarder_membre,
    canal_admin, membre_par_id, est_staff, prenom_de, roster, etats_classeur (async), normaliser, livrables (async, 30/09).
    09/10 : FICHIER_PIPELINE (sinon pipeline.json à côté du registre), texte_repli (bot_discord.texte_repli_attente),
    envoyer_mp (salon perso, sinon MP), valider_candidat (async, pour reprendre un candidat mis en attente par la migration).
    10/10 (vérification L10) : arrive_avant_vannes (membre → bool : le roster par prénom ne vaut que pour un membre arrivé avant
    le 09/10) et reserve_depot (membre → bool : son prénom est attendu par un dépôt salons_a_ouvrir.json « onboarding »).
    30/09 : un ordre posé par `!attribution` (clé « ordre_force » de l'état) prime sur ATTRIBUTION_ORDRE, redémarrages compris."""
    _deps.update(deps)
    e = _etat()
    force = (_etat().get("ordre_force") or "").strip()
    if force:
        definir_ordre(force)


async def commande(message, texte: str) -> bool:
    """30/09 (Gaëtan : « redonne-moi les coefficients, on va ajuster ») — staff :
    `!attribution` : l'ordre, la séquence et les clippers livrables par créatrice ;
    `!attribution Chloé:4,Sophie:3,Sarah:2,Jade:1` : nouvel ordre (0 = exclue), gardé aux redémarrages, compteur remis au début ;
    `!attribution défaut` : retour à ATTRIBUTION_ORDRE (Railway)."""
    if not texte.lower().startswith("!attribution"):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    arg = texte[len("!attribution"):].strip()
    e = _etat()
    if arg.lower() in ("défaut", "defaut", "reset"):
        e.pop("ordre_force", None); _ecrire(e)
        definir_ordre(os.environ.get("ATTRIBUTION_ORDRE", ORDRE_DECISION))
        arg = ""
        entete = "↩️ Ordre remis à celui de Railway."
    elif arg:
        ancien = ORDRE_TEXTE
        definir_ordre(arg)
        if not SEQUENCE:
            definir_ordre(ancien)
            await message.reply("❌ Ordre vide. Exemple : `!attribution Chloé:4,Sophie:3,Sarah:2,Jade:1` (0 = exclue).")
            return True
        e["ordre_force"] = ORDRE_TEXTE; _ecrire(e)
        entete = "✅ Nouvel ordre enregistré, le compteur repart au début."
    else:
        entete = "🎬 **Attribution des nouveaux clippers**"
    livr = {}
    if _deps.get("livrables"):
        try:
            livr = await _deps["livrables"]()
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("!attribution, livrables : %s", erreur)
    lignes = [entete, f"Ordre : **{ordre_texte()}** · sur {len(SEQUENCE)} nouveaux clippers : "
              + ", ".join(f"{c} {POIDS[c]}" for c in ORDRE)]
    if livr:
        lignes.append("Clippers livrables (comptes prêts ÷ 3) : " + " · ".join(f"{c} {n}" for c, n in sorted(livr.items(), key=lambda x: -x[1])))
        vides = [c for c in ORDRE if livr.get(c, 0) == 0]
        if vides:
            lignes.append("⚠️ Dans l'ordre mais sans compte livrable : " + ", ".join(vides) + " — ses nouveaux attendront des comptes.")
    try:                                                                    # 30/09 : l'onglet « Build capacity » suit les coefficients
        import capacite
        lignes.append(capacite.texte_resume(await capacite.ecrire()))
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("!attribution, Build capacity : %s", erreur)
    lignes.append("-# Changer : `!attribution Chloé:4,Sophie:3,Sarah:2,Jade:1` (0 = exclue) · `!attribution défaut`")
    await message.reply("\n".join(lignes)[:1990])
    return True


def actif() -> bool:
    return ACTIF and bool(ORDRE)


def bilan_court(bilan: str) -> str:
    """Le bilan d'onboarding en une ligne lisible sur téléphone (27/09) : sans les évidences (rôle posé, alias rattachés),
    sans le préfixe « Prénom → Créatrice ». 09/10 : plus de « Drive ✅/✗ » (le dossier perso n'existe plus)."""
    import re
    t = bilan.split(" · ", 1)[-1] if " → " in bilan.split(" · ", 1)[0] else bilan
    t = re.sub(r"\s*·\s*rôle Clippeur", "", t)
    t = re.sub(r"\s*·\s*\d+ alias 2FA rattaché\(s\)", "", t)
    t = t.replace("lien GAML ✅", "lien ✅").replace("lien GAML absent", "lien ✗")
    t = re.sub(r"(\d+) compte\(s\)", r"\1 comptes", t)
    return t.strip(" ·")


def _etat() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {"index": 0, "historique": []})


def _ecrire(e: dict):
    _deps["ecrire_json"](_deps["FICHIER"], e)


def _existe(guild, creatrice: str) -> bool:
    if guild is None:
        return True
    try:
        return _deps["categorie_de_creatrice"](guild, creatrice) is not None or _deps["role_creatrice"](guild, creatrice) is not None
    except Exception:                                                       # noqa: BLE001
        return False


def _premier(t) -> str:
    """Le premier mot d'un nom de créatrice, sans accent ni casse (« Chloé 💖 » → « chloe »)."""
    mots = str(t or "").split()
    if not mots:
        return ""
    norm = _deps.get("normaliser") or (lambda x: str(x or "").strip().lower())
    return norm(mots[0])


def _stock_de(stock: dict, creatrice: str) -> int:
    """09/10 : les clippers encore livrables (comptes prêts ÷ 3) d'une créatrice, d'après `livrables` (noms du classeur)."""
    cle = _premier(creatrice)
    return sum(int(n or 0) for c, n in (stock or {}).items() if cle and _premier(c) == cle)


async def stock_livrable():
    """09/10 : {créatrice: clippers livrables} lu dans le classeur, ou None si on ne sait pas (classeur injoignable ou pas branché :
    l'attribution ne bloque alors personne, comme avant)."""
    if not _deps.get("livrables"):
        return None
    try:
        stock = await _deps["livrables"]()
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Stock de comptes livrables : %s", erreur)
        return None
    return stock if isinstance(stock, dict) else None


def prochaine(guild, stock: dict = None) -> tuple:
    """La créatrice suivante de la séquence pondérée (et une note si des créatrices ont été sautées). Avance l'index ;
    un ordre changé (ATTRIBUTION_ORDRE) remet l'index au début. 09/10 : `stock` connu ({créatrice: clippers livrables}) → une
    créatrice sans compte livrable est sautée ; si aucune n'en a, ("", note) et le compteur ne bouge pas."""
    e = _etat()
    if e.get("ordre") != ORDRE_TEXTE:
        e["ordre"], e["index"] = ORDRE_TEXTE, 0
    n = len(SEQUENCE)
    sautees, vides = [], []
    for k in range(n):
        i = (int(e.get("index", 0)) + k) % n
        if not _existe(guild, SEQUENCE[i]):
            sautees.append(SEQUENCE[i])
            continue
        if stock is not None and _stock_de(stock, SEQUENCE[i]) <= 0:
            vides.append(SEQUENCE[i])
            continue
        e["index"] = (i + 1) % n
        _ecrire(e)
        uniques, sans_compte = list(dict.fromkeys(sautees)), list(dict.fromkeys(vides))
        return SEQUENCE[i], ((" · sautée(s), sans catégorie ni rôle sur le serveur : " + ", ".join(uniques)) if uniques else "") \
            + ((" · sautée(s), sans compte livrable : " + ", ".join(sans_compte)) if sans_compte else "")
    if stock is not None and vides:
        return "", " · aucune créatrice de l'ordre n'a de compte livrable"
    i = int(e.get("index", 0)) % n
    e["index"] = (i + 1) % n
    _ecrire(e)
    return SEQUENCE[i], " · ⚠️ aucune créatrice de l'ordre n'a de catégorie ni de rôle sur le serveur"


def sans_creatrice(membre) -> bool:
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    fiche = registre.get(str(membre.id)) or {}
    if fiche.get("creatrice"):
        return False
    roster = _deps.get("roster")
    prenom = _deps["prenom_de"](membre)
    if not (roster and (roster.creatrice_de(prenom) or roster.sans_salon(prenom))):
        return True
    # 10/10 (vérification L10 : un NOUVEAU « Timeo », quizz réussi, validé, n'avait jamais de créatrice ni aucun message, parce que
    # le roster porte un ancien Timeo absent du serveur) : le roster par prénom ne vaut que pour un membre arrivé AVANT l'ouverture
    # des vannes (la même garde que bot_discord.est_signe). Un arrivant d'après n'est jamais l'ancien du roster.
    avant = _deps.get("arrive_avant_vannes")
    if callable(avant):
        try:
            if not avant(membre):
                return True
        except Exception as erreur:                                         # noqa: BLE001 — dans le doute, le filet prévient l'admin
            journal.info("arrive_avant_vannes(%s) : %s", getattr(membre, "id", "?"), erreur)
    # 08/10 (audit) : le roster parle par prénom. S'il désigne un AUTRE signé du même prénom, qui a déjà sa créatrice au registre,
    # ce membre-ci n'est pas l'ancien du roster : avant, il était sauté en silence et n'avait jamais de créatrice.
    norm = _deps.get("normaliser") or (lambda t: str(t or "").strip().lower())
    cle = norm(prenom)
    for uid, f in registre.items():
        if str(uid) == str(membre.id) or not (f or {}).get("creatrice"):
            continue
        autre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        if autre is not None and norm(_deps["prenom_de"](autre)) == cle:
            return True
    return False


# ------------------------------------------------------------------ 09/10 : attente d'un compte livrable
ETAT_ATTENTE = "attente_attribution"
ATTENTE_ROSTER = "prénom au roster"                                      # 10/10 : « attente_par » du filet du roster
_verrous = {}


def _verrou(nom: str) -> asyncio.Lock:
    """Un verrou par usage, créé dans la boucle qui tourne : « attribution » (deux validations simultanées ne prennent jamais
    le même dernier compte), « reprise » (une seule reprise des attentes à la fois)."""
    if nom not in _verrous:
        _verrous[nom] = asyncio.Lock()
    return _verrous[nom]


def _fichier_pipeline():
    if _deps.get("FICHIER_PIPELINE"):
        return _deps["FICHIER_PIPELINE"]
    return Path(_deps["FICHIER_EQUIPES"]).parent / "pipeline.json" if _deps.get("FICHIER_EQUIPES") else None


def _texte_repli(prenom: str) -> str:
    """Le repli de l'étape 5 du funnel (le même que bot_discord.texte_repli_attente, branché par `texte_repli`)."""
    if _deps.get("texte_repli"):
        try:
            return _deps["texte_repli"](prenom)
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Texte de repli : %s", erreur)
    return f"🎉 **Bienvenue dans l'agence, {prenom} !**\n\nTa créatrice arrive ici dès qu'un compte est prêt pour toi.\n\nRien à faire d'ici là."


async def _dire(membre, texte: str) -> bool:
    """Au membre : dans son salon perso (envoyer_mp de bot_discord), sinon en MP."""
    try:
        if _deps.get("envoyer_mp"):
            return bool(await _deps["envoyer_mp"](membre, texte))
        salon = _deps["salon_perso"](str(membre.id)) if _deps.get("salon_perso") else None
        await (salon if salon is not None else membre).send(texte)
        return True
    except (discord.Forbidden, discord.HTTPException, AttributeError) as erreur:
        journal.info("Repli d'attente non envoyé à %s : %s", getattr(membre, "id", "?"), type(erreur).__name__)
        return False


async def _mettre_en_attente(membre, via: str) -> tuple:
    """Le membre passe à « attente_attribution » (pipeline). Le repli part UNE fois : pas à quelqu'un qui attendait déjà (repris
    par la boucle, remis en attente faute de compte) ni à un candidat que la migration a déjà prévenu. Renvoie (nouveau dans
    l'attente, repli envoyé) : l'admin n'a une ligne qu'à l'entrée dans l'attente, jamais à chaque démarrage ou passage (10/10 :
    et seulement si l'attribution est éteinte ; sinon le digest du matin le dit)."""
    fichier, uid = _fichier_pipeline(), str(membre.id)
    deja_prevenu, nouveau = False, True
    if fichier is not None:
        pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
        info = pipe.setdefault("etats", {}).setdefault(uid, {})
        deja_prevenu = bool(info.get("attente_depuis") or info.get("repli_attente"))
        nouveau = info.get("etat") != ETAT_ATTENTE
        info["etat"] = ETAT_ATTENTE
        info.setdefault("attente_depuis", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        info.setdefault("attente_par", via)
        _deps["ecrire_json"](fichier, pipe)
    if deja_prevenu:
        return nouveau, False
    envoye = await _dire(membre, _texte_repli(_deps["prenom_de"](membre)))
    if envoye and fichier is not None:
        pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
        pipe.setdefault("etats", {}).setdefault(uid, {})["repli_attente"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _deps["ecrire_json"](fichier, pipe)
    return nouveau, envoye


def creatrice_en_attente(uid):
    pipe = _deps["lire_json"](_fichier_pipeline(), {})
    info = (pipe.get("etats") or {}).get(str(uid)) or {}
    return info.get("creatrice_attendue", "") if info.get("etat") == ETAT_ATTENTE else ""


def _sortir_d_attente(uid: str) -> bool:
    """09/10 : un membre qui termine son onboarding quitte l'attente après la livraison vérifiée : l'état redevient « valide » et « attente_fin »
    est daté. bot_discord.parcours_a_demarrer compte cette date comme une validation : un nouveau qui a attendu plus de 7 jours
    démarre quand même à l'étape 1 (bienvenue, compte 1), jamais en routine. Renvoie vrai si le membre était en attente."""
    fichier = _fichier_pipeline()
    if fichier is None:
        return False
    pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
    info = (pipe.get("etats") or {}).get(str(uid))
    if not info or info.get("etat") != ETAT_ATTENTE:
        return False
    info["etat"] = "valide"
    info["attente_fin"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for cle in ("attente_depuis", "attente_par", "repli_attente", "reprise_essai", "creatrice_attendue"):
        info.pop(cle, None)
    _deps["ecrire_json"](fichier, pipe)
    return True


def en_attente() -> list:
    """[(uid, info)] des membres « attente_attribution », les plus anciens d'abord."""
    fichier = _fichier_pipeline()
    if fichier is None or not _deps.get("lire_json"):
        return []
    etats = (_deps["lire_json"](fichier, {}) or {}).get("etats") or {}
    attente = [(str(u), i) for u, i in etats.items() if isinstance(i, dict) and i.get("etat") == ETAT_ATTENTE]
    return sorted(attente, key=lambda x: str(x[1].get("attente_depuis") or ""))


# 09/10 (revue du lot L6 : deux reprises lancées l'une après l'autre validaient deux fois le même candidat) : un même membre est
# repris au plus une fois par REPRISE_ESSAI_H heure ; la trace « reprise_essai » est écrite dans le pipeline AVANT l'appel.
REPRISE_ESSAI_H = float(os.environ.get("ATTRIBUTION_REPRISE_H", "1") or 1)


def _essai_recent(info: dict, maintenant=None) -> bool:
    try:
        essai = datetime.fromisoformat(str((info or {}).get("reprise_essai") or ""))
    except ValueError:
        return False
    if essai.tzinfo is None:
        essai = essai.replace(tzinfo=timezone.utc)
    return ((maintenant or datetime.now(timezone.utc)) - essai).total_seconds() < REPRISE_ESSAI_H * 3600


def _noter_essai(uid: str) -> None:
    fichier = _fichier_pipeline()
    if fichier is None:
        return
    pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
    info = (pipe.get("etats") or {}).get(str(uid))
    if isinstance(info, dict):
        info["reprise_essai"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _deps["ecrire_json"](fichier, pipe)


def _attend_le_staff(uid: str, info: dict) -> bool:
    """10/10 : un membre mis en attente par le filet du roster (ATTENTE_ROSTER) attend une décision du staff, pas un compte : la
    reprise ne le prend pas (elle ne relit pas le stock pour lui) tant que sa fiche n'a pas de créatrice."""
    if (info or {}).get("attente_par") != ATTENTE_ROSTER:
        return False
    try:
        fiche = (_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) or {}).get(str(uid)) or {}
    except Exception:                                                       # noqa: BLE001
        fiche = {}
    return not fiche.get("creatrice")


def _repris_possible(uid: str, info: dict):
    """Le membre si la reprise peut le prendre maintenant (présent, ni bot ni staff, pas essayé dans l'heure, pas en attente d'une
    décision du staff), sinon None."""
    membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
    if membre is None or getattr(membre, "bot", False) or (_deps.get("est_staff") and _deps["est_staff"](membre)):
        return None
    if _attend_le_staff(uid, info):
        return None
    return None if _essai_recent(info) else membre


def attente_a_reprendre() -> bool:
    """Lecture seule, sans réseau : y a-t-il quelqu'un à reprendre (et une reprise n'est pas déjà en cours) ? 09/10 (revue) : seuls
    comptent les membres présents, ni bots ni staff, pas essayés dans l'heure : un absent garde son état sans faire relire le stock
    toutes les 15 minutes."""
    if not (actif() and bool(_deps) and not _verrou("reprise").locked()):
        return False
    return any(_repris_possible(u, i) is not None for u, i in en_attente())


def _fiche_registre(membre):
    """La fiche du registre du membre, None s'il n'y est pas."""
    try:
        return (_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) or {}).get(str(membre.id))
    except Exception:                                                       # noqa: BLE001
        return None


def _marquer_une_fois(uid: str, cle: str) -> bool:
    """Pose la date `cle` dans l'état du pipeline du membre ; faux si elle y était déjà (la ligne à l'admin part une fois)."""
    fichier = _fichier_pipeline()
    if fichier is None:
        return True
    pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
    info = pipe.setdefault("etats", {}).setdefault(str(uid), {})
    if info.get(cle):
        return False
    info[cle] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _deps["ecrire_json"](fichier, pipe)
    return True


async def _ligne_admin(texte: str) -> None:
    admin = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
    if admin is not None:
        try:
            await admin.send(texte[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass


def _reserve_au_depot(membre) -> bool:
    """10/10 (vérification L10, D3) : son prénom est attendu par un dépôt salons_a_ouvrir.json « onboarding » pas encore servi
    (« Ajoute Andry Sarah ») : sa créatrice vient du dépôt, jamais de la séquence (sinon le dépôt « nouveau » ne le trouve plus)."""
    reserve = _deps.get("reserve_depot")
    if not callable(reserve):
        return False
    try:
        return bool(reserve(membre))
    except Exception as erreur:                                             # noqa: BLE001
        journal.info("reserve_depot(%s) : %s", getattr(membre, "id", "?"), erreur)
        return False


def _valide_au_funnel(uid) -> bool:
    """10/10 : validé par le funnel du 09/10 (quizz, migration, reprise, `!quiz-ok`, dépôt : clé « sans_test » du pipeline), donc un
    NOUVEAU clipper. Un ancien du roster resté au registre sans créatrice n'en a pas : le filet ne lui parle jamais."""
    fichier = _fichier_pipeline()
    if fichier is None:
        return False
    info = ((_deps["lire_json"](fichier, {}) or {}).get("etats") or {}).get(str(uid)) or {}
    return bool(info.get("sans_test")) and info.get("etat") in ("valide", ETAT_ATTENTE)


async def _filet_roster(membre, via: str) -> None:
    """10/10 (vérification L10 : un validé dont le prénom est au roster ne recevait RIEN, ni créatrice, ni repli, ni ligne admin) :
    le roster le prend pour l'ancien clipper de ce prénom, l'attribution ne peut pas trancher. Une seule fois : une ligne à l'admin
    avec la commande, le repli au membre, l'état « attente_attribution » (attente_par = ATTENTE_ROSTER : la reprise des attentes
    ne le prend pas, c'est au staff de décider)."""
    uid = str(membre.id)
    if not _marquer_une_fois(uid, "roster_signale"):
        return
    prenom = _deps["prenom_de"](membre)
    roster = _deps.get("roster")
    creatrice_r = ""
    try:
        creatrice_r = (roster.creatrice_de(prenom) if roster else "") or ""
    except Exception:                                                       # noqa: BLE001
        pass
    _, envoye = await _mettre_en_attente(membre, ATTENTE_ROSTER)
    journal.info("Attribution de %s (%s) : prénom au roster, décision du staff attendue", prenom, via)
    await _ligne_admin(f"⚠️ {membre.mention} validé, sans créatrice : son prénom « {prenom} » est au roster"
                       + (f" ({creatrice_r})" if creatrice_r else " (anciens sans salon)") + ", je ne sais pas si c'est l'ancien.\n\n"
                       f"Nouveau clipper : `!creatrice @{prenom} <créatrice>`."
                       + (f" C'est bien l'ancien : `!creatrice @{prenom} {creatrice_r}`." if creatrice_r else "")
                       + ("" if envoye else " (repli non envoyé : salon et MP fermés)"))


async def attribuer(membre, via: str) -> str:
    """Attribue la créatrice suivante à un membre signé sans créatrice ; renvoie son prénom, ou "" si rien à faire.
    09/10 : une seule attribution à la fois ; aucune créatrice avec un compte livrable → repli une fois, « attente_attribution ».
    10/10 (vérification L10) : un prénom attendu par un dépôt « onboarding » attend le dépôt (une ligne à l'admin, une fois) ; un
    nouveau validé (_valide_au_funnel) que le roster prend pour l'ancien de son prénom passe par le filet (_filet_roster), jamais
    plus le silence."""
    if not actif() or membre is None or getattr(membre, "bot", False):
        return ""
    import choix_creatrice
    import process_adapters
    async with _verrou("attribution"):
        async with choix_creatrice.verrou(str(membre.id)):
            fiche = _fiche_registre(membre)
            reprise = creatrice_en_attente(membre.id)
            if (fiche or {}).get("creatrice") and not reprise:
                return ""
            if _reserve_au_depot(membre):
                if _marquer_une_fois(str(membre.id), "depot_attendu"):
                    journal.info("Attribution de %s (%s) : prénom attendu par un dépôt, rien attribué", _deps["prenom_de"](membre), via)
                    await _ligne_admin(f"⏸️ {membre.mention} validé : son prénom est attendu par un dépôt `salons_a_ouvrir.json` "
                                       "(« onboarding »). Sa créatrice vient du dépôt, au prochain démarrage.\n\n"
                                       f"Pas lui ? `!creatrice @{_deps['prenom_de'](membre)} <créatrice>`.")
                return ""
            if not sans_creatrice(membre) and not reprise:
                est_staff = _deps.get("est_staff")
                if fiche is not None and not (est_staff and est_staff(membre)) and _valide_au_funnel(membre.id):
                    await _filet_roster(membre, via)
                return ""
            pipe = _deps['lire_json'](_fichier_pipeline(), None)
            if not isinstance(pipe, dict):
                return ""
            info = (pipe.get('etats') or {}).get(str(membre.id)) or {}
            try:
                reprise = choix_creatrice.resoudre(membre.id, _fiche_registre(membre) or {}, info)
            except choix_creatrice.Divergence:
                journal.warning("Choix de créatrice divergent : attribution retenue")
                return ""
            if not sans_creatrice(membre) and not reprise:  # attribué pendant l'attente du verrou
                return ""
            if reprise:
                creatrice, note = reprise, ""
            else:
                stock = await stock_livrable()
                creatrice, note = prochaine(membre.guild, stock)
            if not creatrice:
                nouveau, prevenu = await _mettre_en_attente(membre, via)
                journal.info("Attribution impossible pour %s (%s) : aucun compte livrable, en attente%s", _deps["prenom_de"](membre), via,
                             " (repli envoyé)" if prevenu else "")
                # 10/10 (vérification du lot L9b) : plus de ligne « ⏳ … repris tout seul » au salon admin, sans geste à faire et en double
                # avec le bloc « En attente d'une créatrice » et les places du digest. Seule exception : l'attribution est éteinte au
                # moment de la mise en attente (actif() faux, ordre vidé pendant l'attente du verrou) : la reprise ne le prendra pas, le
                # geste est `!creatrice`.
                admin = await _deps["canal_admin"]() if nouveau and not actif() else None
                if admin is not None:
                    try:
                        await admin.send((f"⏳ {membre.mention} attend une créatrice et l'attribution est éteinte : personne ne le reprendra.\n\n"
                                          f"`!creatrice @{_deps['prenom_de'](membre)} <créatrice>`.")[:1990])
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                return ""
            try:
                creatrice = choix_creatrice.preparer(membre.id, creatrice, _deps['lire_json'], _deps['ecrire_json'],
                    _fichier_pipeline(), _deps['FICHIER_EQUIPES'], _deps['FICHIER_ONBOARDING'],
                    comptes_connus=process_adapters.store().counts(membre.id),
                    verification_roles=lambda choix: choix_creatrice.verifier_roles(membre,
                        _deps['role_creatrice'](membre.guild, choix), _deps['roles_creatrices'](membre.guild)
                        + [r for nom in set(ORDRE) | set(_deps['roster'].groupes())
                           if (r := _deps['role_creatrice'](membre.guild, nom)) is not None]))
            except (choix_creatrice.Divergence, OSError):
                journal.warning("Choix non persisté ou réservation à rapprocher : attribution retenue")
                return ""
            try:
                etats_cl = await _deps["etats_classeur"]()
            except Exception as erreur:                                         # noqa: BLE001
                journal.warning("États du classeur pour l'attribution : %s", erreur)
                etats_cl = {}
            try:
                bilan = await _deps["onboarder_membre"](membre.guild, membre, creatrice, _Par(), etats_cl, [], forcer_salon=True)
            except Exception as erreur:                                         # noqa: BLE001
                bilan = f"❌ {type(erreur).__name__} {str(erreur)[:120]}"
            e = _etat()
            e.setdefault("historique", []).append({"uid": str(membre.id), "prenom": _deps["prenom_de"](membre), "creatrice": creatrice,
                                                   "via": via, "date": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            e["historique"] = e["historique"][-300:]
            _ecrire(e)
            journal.info("Attribution automatique : %s → %s (%s) · %s%s", _deps["prenom_de"](membre), creatrice, via, bilan_court(bilan), note)
            # 10/10 (revue du recrutement, lot L9b : « un seul digest admin ») : une attribution qui s'est bien passée n'est plus une ligne
            # au salon admin ; elle compte dans « attribué(s) » du digest du matin (registre, creatrice_date). Seule une attribution qui
            # demande un geste (onboarding en échec, rôle ou pseudo refusé, comptes non livrés, créatrice sans catégorie ni rôle) part
            # encore tout de suite.
            await signaler_blocage(membre, creatrice, bilan, note)
            return "" if creatrice_en_attente(membre.id) else creatrice


async def signaler_blocage(membre, creatrice, bilan, note=""):
    """Sous le verrou d'attribution : une notification par blocage actif, reprise inchangée.

    Intention persistée avant l'envoi : une réponse Discord perdue ne provoque pas
    de doublon. Une interdiction explicite peut être retentée après correction.
    """
    import hashlib
    uid = str(membre.id)
    e = _etat()
    blocages = e.setdefault("blocages_notifications", {})
    if not a_signaler(bilan, note):
        if uid in blocages:
            blocages.pop(uid)
            _ecrire(e)
        return
    raison = "team_leader_absent_ou_ambigu" if "team leader absent ou ambigu" in str(bilan).lower() else " ".join((bilan_court(bilan) + note).split())
    signature = hashlib.sha256((str(creatrice).casefold() + ":" + raison).encode()).hexdigest()
    precedent = blocages.get(uid) or {}
    if precedent.get("signature") == signature:
        return
    admin = await _deps["canal_admin"]()
    if admin is None:
        return
    entree = {"signature": signature, "depuis": datetime.now(timezone.utc).isoformat(), "etat": "envoi_incertain"}
    blocages[uid] = entree
    _ecrire(e)
    try:
        message = await admin.send((f"🎬 {membre.mention} → **{creatrice}** · {bilan_court(bilan)}{note}")[:1990])
    except discord.Forbidden:
        e = _etat()
        if (e.get("blocages_notifications", {}).get(uid) or {}).get("signature") == signature:
            e["blocages_notifications"].pop(uid, None)
            _ecrire(e)
        return
    except Exception:
        journal.warning("Notification de blocage %s : envoi incertain, pas de renvoi automatique", uid)
        return
    e = _etat()
    e.setdefault("blocages_notifications", {})[uid] = {**entree, "etat": "envoye", "message_id": str(message.id)}
    _ecrire(e)


# 10/10 (lot L9b) : ce qui, dans le bilan d'onboarding ou la note de l'ordre, demande un geste du staff (onboarder_membre et
# onboarding.livrer : échec, rôle ou pseudo refusé, aucun rôle d'équipe, comptes non livrés, classeur ou GAML en panne, parcours
# pas lancé ; prochaine : créatrice sans catégorie ni rôle sur le serveur)
MARQUES_A_SIGNALER = ("❌", "⚠️", "refusé", "impossible", "aucun libre", "classeur :", "classeur non branché", "gaml :",
                      "onboarding :", "non livrés", "sans catégorie ni rôle", "aucun rôle posé", "parcours pas commencé",
                      "non renvoyée")
# 10/10 (vérification du lot L9b : onboarding.livrer qui lève donnait « onboarding : KeyError … », coupé au premier « : » par
# onboarder_membre, donc sans marque, et la ligne admin ne partait plus alors qu'aucun compte n'était réservé) : le succès se lit
# en liste blanche. Une livraison réussie écrit « N compte(s) » (bilan_court : « N comptes »), N ≥ 1 ; sans elle, on signale.
_RE_COMPTES_LIVRES = __import__("re").compile(r"(?<![\d.,])[1-9]\d* compte(?:\(s\)|s)?(?![a-zà-ÿ(])")


def a_signaler(bilan: str, note: str = "") -> bool:
    """10/10 (lot L9b) : vrai si l'attribution demande un geste. Une des MARQUES_A_SIGNALER dans le bilan ou la note, OU aucun
    « N compte(s) » (N ≥ 1) dans le bilan : l'onboarding n'a rien réservé (exception de livrer, quelle qu'elle soit), sauf « déjà
    livré … rien renvoyé » (livraison de moins de 24 h, ses comptes sont à lui). Une créatrice sautée faute de compte livrable
    n'est pas un geste : les places du digest le disent."""
    t = f"{bilan or ''} {note or ''}".lower()
    if any(m.lower() in t for m in MARQUES_A_SIGNALER):
        return True
    b = str(bilan or "").lower()
    if "déjà livré" in b and "rien renvoyé" in b:
        return False
    return _RE_COMPTES_LIVRES.search(b) is None


async def reprendre_attente() -> list:
    """09/10 (Gaëtan : « on va ouvrir les vannes » ; décision : reprise automatique, sans commande) : lancée par
    boucle_pipeline (bot_discord.reprendre_attente_attribution, 5 min ; lot L10 : plus par la boucle de l'onboarding). Les membres « attente_attribution » présents passent, les plus anciens d'abord, dans la limite du stock
    de comptes livrables, ATTRIBUTION_PAUSE_SEC entre deux : un signé reçoit sa créatrice (attribuer), un candidat mis en attente
    par la migration est validé (valider_candidat, qui mène à la même attribution). Stock inconnu ou nul : seules les attributions déjà choisies sont reprises ; la réservation reste contrôlée par le store.
    09/10 (revue du lot L6) : un staff en attente en sort ; un « deja » (rôle d'équipe sans être au registre) en sort aussi, avec une
    ligne à l'admin, et ne prend pas de place ; un même membre au plus une fois par REPRISE_ESSAI_H heure (trace écrite avant l'appel :
    deux reprises lancées coup sur coup ne valident jamais deux fois). Renvoie [(prénom, résultat)]."""
    if not actif() or _verrou("reprise").locked():
        return []
    faits, pris = [], 0
    async with _verrou("reprise"):
        attente = en_attente()
        for uid, _info in attente:                                          # un staff n'attend jamais de créatrice
            m_s = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            if m_s is not None and _deps.get("est_staff") and _deps["est_staff"](m_s) and _sortir_d_attente(uid):
                journal.info("Reprise des attentes : %s est du staff, sorti de l'attente", uid)
        attente = [(u, i) for u, i in en_attente() if _repris_possible(u, i) is not None]
        if not attente:
            return []
        presents = [_repris_possible(u, i) for u, i in attente]
        stock = await stock_livrable()
        guild = getattr(presents[0], "guild", None)                         # seules les créatrices ouvertes sur le serveur comptent
        places = sum(_stock_de(stock, c) for c in ORDRE if _existe(guild, c)) if stock is not None else 0
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        for uid, info in attente:
            reprise = creatrice_en_attente(uid)
            if pris >= places and not reprise:
                continue
            membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            info_f = dict(((_deps["lire_json"](_fichier_pipeline(), {}) or {}).get("etats") or {}).get(uid) or {})
            if membre is None or info_f.get("etat") != ETAT_ATTENTE or _repris_possible(uid, info_f) is None:
                continue                                                    # parti, déjà repris ailleurs, ou essayé dans l'heure
            prenom = _deps["prenom_de"](membre)
            if uid in registre or reprise:
                if not sans_creatrice(membre) and not creatrice_en_attente(uid):  # créatrice reçue autrement (`!creatrice`, roster)
                    _sortir_d_attente(uid)
                    continue
                _noter_essai(uid)
                creatrice = await attribuer(membre, "reprise : compte libéré")
                if not creatrice:
                    continue  # un blocage individuel ne bloque pas les autres reprises
                pris += 1
                faits.append((prenom, creatrice))
            elif _deps.get("valider_candidat"):
                _noter_essai(uid)
                try:
                    retour = await _deps["valider_candidat"](membre, str(info.get("score_quiz") or ""), "reprise")
                except Exception as erreur:                                 # noqa: BLE001
                    journal.warning("Reprise de %s : %s", uid, erreur)
                    continue
                if retour == "deja":                                        # aucune place prise, pas de pause
                    faits.append((prenom, "déjà dans l'agence"))
                    if _sortir_d_attente(uid):                              # (une validation en cours ailleurs a déjà changé l'état)
                        admin = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
                        if admin is not None:
                            try:
                                await admin.send(f"⚠️ {membre.mention} attendait une créatrice mais porte déjà un rôle de l'équipe sans "
                                                 f"être au registre : sorti de l'attente. Clipper ? `!creatrice @{prenom} <créatrice>`.")
                            except (discord.Forbidden, discord.HTTPException):
                                pass
                    continue
                pris += 1
                faits.append((prenom, "validé"))
            else:
                journal.warning("Reprise des attentes : valider_candidat non branché, %s attend", uid)
                continue
            await asyncio.sleep(PAUSE_SEC)
    if faits:
        journal.info("Reprise des attentes d'attribution : %s", faits)
    return faits


async def rattraper(client) -> list:
    """Au démarrage : chaque signé présent sur le serveur sans créatrice reçoit la suivante, un par un, PAUSE_SEC entre deux."""
    await client.wait_until_ready()
    if not actif() or not client.guilds:
        return []
    await asyncio.sleep(int(os.environ.get("ATTRIBUTION_DELAI_DEMARRAGE_SEC", "120")))   # après le roster et les boutons
    faits = []
    for uid, fiche in list(_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).items()):
        if fiche.get("creatrice"):
            continue
        membre = _deps["membre_par_id"](uid)
        if membre is None or getattr(membre, "bot", False) or _deps["est_staff"](membre):
            continue
        creatrice = await attribuer(membre, "rattrapage au démarrage")
        if creatrice:
            faits.append((_deps["prenom_de"](membre), creatrice))
            await asyncio.sleep(PAUSE_SEC)
    if faits:
        journal.info("Attribution automatique, rattrapage : %s", faits)
    return faits
