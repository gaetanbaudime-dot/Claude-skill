"""Attribution automatique des créatrices (27/09, décision de Gaëtan). Ordre final du 27/09 au soir, PONDÉRÉ :
« Chloé (3) > Sarah (3) > Sophie (3) > Jade (2) > Clara (1) > Maddie (1) » — trois nouveaux d'affilée chez Chloé, puis trois
chez Sarah, trois chez Sophie, deux chez Jade, un chez Clara, un chez Maddie, et on recommence. Dès qu'un clipper accepte
les règles, il reçoit la créatrice suivante de la séquence et tout ce que `!creatrice` faisait (salon perso, pseudo, rôles,
comptes du classeur, lien, Drive, alias 2FA, parcours). Au démarrage, les signés présents sans créatrice sont rattrapés un
par un, avec une pause entre deux.

Ordre : ATTRIBUTION_ORDRE, « Créatrice:poids » séparés par des virgules (défaut « Chloé:3,Sarah:3,Sophie:3,Jade:1 » depuis le 28/09 : Clara et
Maddie à 0 tant qu'aucun e-mail de compte n'arrive ; sans poids = 1). Une créatrice sans catégorie ni rôle sur le serveur est sautée (et dite au salon admin). Un
changement d'ordre remet le compteur au début. ATTRIBUTION_AUTO=0 éteint tout. État dans DONNEES/attribution.json."""

import asyncio
import os
from datetime import datetime, timezone

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
    try:                                                                    # 01/10 : l'onglet « Build capacity » suit les coefficients
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
    sans le préfixe « Prénom → Créatrice », et le Drive sans e-mail dit juste qu'il attend l'e-mail."""
    import re
    t = bilan.split(" · ", 1)[-1] if " → " in bilan.split(" · ", 1)[0] else bilan
    t = re.sub(r"\s*·\s*rôle Clippeur", "", t)
    t = re.sub(r"\s*·\s*\d+ alias 2FA rattaché\(s\)", "", t)
    t = t.replace("Drive ✅ (sans e-mail : rien partagé, `!onboarding` après son e-mail)", "Drive (attend son e-mail)")
    t = t.replace("lien GAML ✅", "lien ✅").replace("lien GAML absent", "lien ✗").replace("Drive non configuré", "Drive ✗")
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


def prochaine(guild) -> tuple:
    """La créatrice suivante de la séquence pondérée (et une note si des créatrices ont été sautées). Avance l'index ;
    un ordre changé (ATTRIBUTION_ORDRE) remet l'index au début."""
    e = _etat()
    if e.get("ordre") != ORDRE_TEXTE:
        e["ordre"], e["index"] = ORDRE_TEXTE, 0
    n = len(SEQUENCE)
    sautees = []
    for k in range(n):
        i = (int(e.get("index", 0)) + k) % n
        if _existe(guild, SEQUENCE[i]):
            e["index"] = (i + 1) % n
            _ecrire(e)
            uniques = list(dict.fromkeys(sautees))
            return SEQUENCE[i], (" · sautée(s), sans catégorie ni rôle sur le serveur : " + ", ".join(uniques)) if uniques else ""
        sautees.append(SEQUENCE[i])
    i = int(e.get("index", 0)) % n
    e["index"] = (i + 1) % n
    _ecrire(e)
    return SEQUENCE[i], " · ⚠️ aucune créatrice de l'ordre n'a de catégorie ni de rôle sur le serveur"


def sans_creatrice(membre) -> bool:
    fiche = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(str(membre.id)) or {}
    if fiche.get("creatrice"):
        return False
    roster = _deps.get("roster")
    prenom = _deps["prenom_de"](membre)
    return not (roster and (roster.creatrice_de(prenom) or roster.sans_salon(prenom)))


async def attribuer(membre, via: str) -> str:
    """Attribue la créatrice suivante à un membre signé sans créatrice ; renvoie son prénom, ou "" si rien à faire."""
    if not actif() or membre is None or getattr(membre, "bot", False) or not sans_creatrice(membre):
        return ""
    creatrice, note = prochaine(membre.guild)
    try:
        etats_cl = await _deps["etats_classeur"]()
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("États du classeur pour l'attribution : %s", erreur)
        etats_cl = {}
    try:
        bilan = await _deps["onboarder_membre"](membre.guild, membre, creatrice, _Par(), etats_cl, [], forcer_salon=True)
    except Exception as erreur:                                             # noqa: BLE001
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
