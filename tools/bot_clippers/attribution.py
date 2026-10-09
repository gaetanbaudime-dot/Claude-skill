"""Attribution automatique des créatrices (27/09, décision de Gaëtan). Ordre final du 27/09 au soir, PONDÉRÉ :
« Chloé (3) > Sarah (3) > Sophie (3) > Jade (2) > Clara (1) > Maddie (1) » — trois nouveaux d'affilée chez Chloé, puis trois
chez Sarah, trois chez Sophie, deux chez Jade, un chez Clara, un chez Maddie, et on recommence. Dès qu'un clipper accepte
les règles, il reçoit la créatrice suivante de la séquence et tout ce que `!creatrice` faisait (salon perso, pseudo, rôles,
comptes du classeur, lien, alias 2FA, parcours). Au démarrage, les signés présents sans créatrice sont rattrapés un
par un, avec une pause entre deux.

09/10 (Gaëtan : « on va ouvrir les vannes ») : le goulot passe du test de montage au stock de comptes. Une créatrice sans compte
livrable est sautée ; si AUCUNE n'en a, le membre reçoit une fois le repli « Ta créatrice arrive ici sous 48 h » et passe à l'état
« attente_attribution » du pipeline. La boucle de l'onboarding le reprend tout seul dès qu'un compte se libère (`reprendre_attente`),
un par un, ATTRIBUTION_PAUSE_SEC entre deux, sans commande.

Ordre : ATTRIBUTION_ORDRE, « Créatrice:poids » séparés par des virgules (défaut « Chloé:3,Sarah:3,Sophie:3,Jade:1 » depuis le 28/09 : Clara et
Maddie à 0 tant qu'aucun e-mail de compte n'arrive ; sans poids = 1). Une créatrice sans catégorie ni rôle sur le serveur est sautée (et dite au salon admin). Un
changement d'ordre remet le compteur au début. ATTRIBUTION_AUTO=0 éteint tout. État dans DONNEES/attribution.json."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import discord

journal = __import__("logging").getLogger("bot_clippers")

ORDRE_TEXTE = os.environ.get("ATTRIBUTION_ORDRE", "Chloé:3,Sarah:3,Sophie:3,Jade:1")   # 28/09 (Gaëtan) : Jade 1, Clara 0, Maddie 0 tant qu'aucun e-mail n'arrive
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
    30/09 : un ordre posé par `!attribution` (clé « ordre_force » de l'état) prime sur ATTRIBUTION_ORDRE, redémarrages compris."""
    _deps.update(deps)
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
        definir_ordre(os.environ.get("ATTRIBUTION_ORDRE", "Chloé:3,Sarah:3,Sophie:3,Jade:1"))
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
    return f"🎉 **Bienvenue dans l'agence, {prenom} !**\n\nTa créatrice arrive ici sous 48 h.\n\nRien à faire d'ici là."


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
    l'attente, repli envoyé) : l'admin n'a une ligne qu'à l'entrée dans l'attente, jamais à chaque démarrage ou passage."""
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


def _sortir_d_attente(uid: str) -> None:
    """09/10 : un membre qui reçoit sa créatrice quitte l'attente AVANT l'onboarding : l'état redevient « valide » (onboarder_membre
    démarre alors le parcours à l'étape 1)."""
    fichier = _fichier_pipeline()
    if fichier is None:
        return
    pipe = _deps["lire_json"](fichier, {"liaisons": {}, "etats": {}})
    info = (pipe.get("etats") or {}).get(str(uid))
    if not info or info.get("etat") != ETAT_ATTENTE:
        return
    info["etat"] = "valide"
    info["attente_fin"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for cle in ("attente_depuis", "attente_par", "repli_attente"):
        info.pop(cle, None)
    _deps["ecrire_json"](fichier, pipe)


def en_attente() -> list:
    """[(uid, info)] des membres « attente_attribution », les plus anciens d'abord."""
    fichier = _fichier_pipeline()
    if fichier is None or not _deps.get("lire_json"):
        return []
    etats = (_deps["lire_json"](fichier, {}) or {}).get("etats") or {}
    attente = [(str(u), i) for u, i in etats.items() if isinstance(i, dict) and i.get("etat") == ETAT_ATTENTE]
    return sorted(attente, key=lambda x: str(x[1].get("attente_depuis") or ""))


def attente_a_reprendre() -> bool:
    """Lecture seule, sans réseau : y a-t-il quelqu'un à reprendre (et une reprise n'est pas déjà en cours) ?"""
    return actif() and bool(_deps) and not _verrou("reprise").locked() and bool(en_attente())


async def attribuer(membre, via: str) -> str:
    """Attribue la créatrice suivante à un membre signé sans créatrice ; renvoie son prénom, ou "" si rien à faire.
    09/10 : une seule attribution à la fois ; aucune créatrice avec un compte livrable → repli une fois, « attente_attribution »."""
    if not actif() or membre is None or getattr(membre, "bot", False) or not sans_creatrice(membre):
        return ""
    async with _verrou("attribution"):
        if not sans_creatrice(membre):                                      # attribué pendant l'attente du verrou
            return ""
        stock = await stock_livrable()
        creatrice, note = prochaine(membre.guild, stock)
        if not creatrice:
            nouveau, prevenu = await _mettre_en_attente(membre, via)
            journal.info("Attribution impossible pour %s (%s) : aucun compte livrable, en attente", _deps["prenom_de"](membre), via)
            admin = await _deps["canal_admin"]() if nouveau else None
            if admin is not None:
                try:
                    await admin.send((f"⏳ {membre.mention} en attente d'une créatrice : aucun compte livrable ({via})."
                                      + (" Repli « sous 48 h » envoyé." if prevenu else "")
                                      + " Repris tout seul dès qu'un compte se libère.")[:1990])
                except (discord.Forbidden, discord.HTTPException):
                    pass
            return ""
        _sortir_d_attente(str(membre.id))
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
    journal.info("Attribution automatique : %s → %s (%s)", _deps["prenom_de"](membre), creatrice, via)
    admin = await _deps["canal_admin"]()
    if admin is not None:
        try:
            await admin.send((f"🎬 {membre.mention} → **{creatrice}** (auto, {ordre_texte()}) · {bilan_court(bilan)}{note}")[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass
    return creatrice


async def reprendre_attente() -> list:
    """09/10 (Gaëtan : « on va ouvrir les vannes » ; décision : reprise automatique, sans commande) : appelée par la boucle de
    l'onboarding (15 min). Les membres « attente_attribution » présents passent, les plus anciens d'abord, dans la limite du stock
    de comptes livrables, ATTRIBUTION_PAUSE_SEC entre deux : un signé reçoit sa créatrice (attribuer), un candidat mis en attente
    par la migration est validé (valider_candidat, qui mène à la même attribution). Stock inconnu ou nul : personne ne bouge.
    Renvoie [(prénom, résultat)]."""
    if not actif() or _verrou("reprise").locked():
        return []
    faits = []
    async with _verrou("reprise"):
        attente = en_attente()
        if not attente:
            return []
        presents = [m for m in (_deps["membre_par_id"](u) if _deps.get("membre_par_id") else None for u, _i in attente) if m is not None]
        if not presents:
            return []
        stock = await stock_livrable()
        guild = getattr(presents[0], "guild", None)                         # seules les créatrices ouvertes sur le serveur comptent
        places = sum(_stock_de(stock, c) for c in ORDRE if _existe(guild, c)) if stock is not None else 0
        if places <= 0:
            return []
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
        for uid, info in attente:
            if len(faits) >= places:
                break
            membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            if membre is None or getattr(membre, "bot", False) or (_deps.get("est_staff") and _deps["est_staff"](membre)):
                continue                                                    # parti du serveur : il garde son état, rien à faire
            prenom = _deps["prenom_de"](membre)
            if uid in registre:
                if not sans_creatrice(membre):                              # créatrice reçue autrement (`!creatrice`, roster)
                    _sortir_d_attente(uid)
                    continue
                creatrice = await attribuer(membre, "reprise : compte libéré")
                if not creatrice:
                    break                                                   # plus de compte en vrai : on s'arrête là
                faits.append((prenom, creatrice))
            elif _deps.get("valider_candidat"):
                try:
                    retour = await _deps["valider_candidat"](membre, str(info.get("score_quiz") or ""), "reprise")
                except Exception as erreur:                                 # noqa: BLE001
                    journal.warning("Reprise de %s : %s", uid, erreur)
                    continue
                faits.append((prenom, "validé" if retour != "deja" else "déjà dans l'agence"))
                if retour == "deja":
                    continue                                                # aucune place prise, pas de pause
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
