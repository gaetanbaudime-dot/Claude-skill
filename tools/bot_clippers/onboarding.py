"""Onboarding automatique d'un clipper (machine horizontale v2, 23/09/2026).

Quand un manager attribue une créatrice (`!creatrice @clipper Prénom`), ou quand un nom de clipper
apparaît dans la colonne Gérant du classeur des logins, le bot livre dans le salon perso du clipper :

  1. ses identités de comptes Instagram (COMPTES_PAR_CLIPPER, 3 par défaut) prises dans l'onglet
     Instagram du classeur (Utilisation = Clipper, Gérant libre, Créatrice = la sienne), et il écrit son
     prénom dans la colonne Gérant : le classeur reste la source de vérité, modifiable à la main ;
  2. son lien GAML (cloné depuis un lien « Clipping » de la créatrice si aucun ne lui est attribué) ;
  3. son dossier Drive personnel (photos et Reels de la créatrice), copié et partagé par le script de
     l'agence quand il est déployé (drive_agence.py), sinon rien.

Colonnes de l'onglet Instagram : A ETAT · B @ IG · C MDP · D Followers · E Mail · F Phone · G Gérant ·
H Utilisation · I Numéro · J Créatrice. Variables : CLASSEUR_LOGINS_ID (obligatoire), ONGLET_LOGINS
(Instagram), COMPTES_PAR_CLIPPER (3), DRIVE_SOURCES (JSON : {"Chloé": {"parent": id, "sources": [id, …]}}).
Le module ne connaît pas bot_discord : dépendances dans `demarrer(deps)`.
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import discord

import drive_agence
import google_api
import paie_clics

journal = logging.getLogger("onboarding")

CLASSEUR_LOGINS_ID = os.environ.get("CLASSEUR_LOGINS_ID", "").strip()
ONGLET_LOGINS = os.environ.get("ONGLET_LOGINS", "Instagram").strip() or "Instagram"
COMPTES_PAR_CLIPPER = int(os.environ.get("COMPTES_PAR_CLIPPER", "3") or 3)
GERANTS_LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
ETATS_DISPONIBLES = {"a creer", "à créer", "good", "warmup", "warm-up", "prive", "privé", "actif", "ok"}
COL = {"etat": 0, "handle": 1, "mdp": 2, "followers": 3, "mail": 4, "phone": 5, "gerant": 6, "utilisation": 7, "numero": 8, "creatrice": 9}

_deps = {}


def configurer(deps: dict):
    """À appeler dès le démarrage : `livrer` peut être déclenché par !creatrice avant le premier tour de boucle."""
    global _deps
    _deps = deps


def actif() -> bool:
    return bool(CLASSEUR_LOGINS_ID and google_api.actif())


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _sources() -> dict:
    try:
        return json.loads(os.environ.get("DRIVE_SOURCES", "") or "{}")
    except ValueError:
        journal.warning("DRIVE_SOURCES illisible (JSON attendu)")
        return {}


def _lire_etat() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {})
    d.setdefault("livres", {}); d.setdefault("clippers", {})
    return d


def _ecrire_etat(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_ONBOARDING"], d)


# ------------------------------------------------------------------ classeur
async def lire_comptes() -> list:
    """Toutes les lignes de l'onglet (index de ligne 1-based inclus), cellules manquantes complétées."""
    lignes = await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!A1:J")
    out = []
    for i, l in enumerate(lignes[1:], start=2):
        l = (l + [""] * 10)[:10]
        out.append({"ligne": i, "etat": l[0].strip(), "handle": l[1].strip().lstrip("@"), "mdp": l[2].strip(),
                    "mail": l[4].strip(), "phone": l[5].strip(), "gerant": l[6].strip(), "utilisation": l[7].strip(),
                    "numero": l[8].strip(), "creatrice": l[9].strip()})
    return out


def _pour_creatrice(c: dict, creatrice: str) -> bool:
    cible = _norm(creatrice).split()[0] if _norm(creatrice) else ""
    return bool(cible) and _norm(c["creatrice"]).startswith(cible)


def disponibles(comptes: list, creatrice: str, n: int) -> list:
    """Lignes libres pour cette créatrice : Utilisation = Clipper, Gérant libre, état utilisable, handle présent.
    Les comptes déjà créés (GOOD, WARMUP, PRIVÉ, ACTIF) passent avant ceux « à créer »."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)]
    libres.sort(key=lambda c: (_norm(c["etat"]) in ("a creer", "à créer"), c["ligne"]))
    return libres[:n]


async def reserver(comptes: list, prenom_clipper: str) -> int:
    """Écrit le prénom du clipper dans la colonne Gérant de chaque ligne. Renvoie le nombre de cellules écrites."""
    n = 0
    for c in comptes:
        n += await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!G{c['ligne']}", [[prenom_clipper]])
    return n


def message_comptes(comptes: list, prenom: str, creatrice: str) -> str:
    if not comptes:
        return (f"⚠️ Aucun compte libre pour {creatrice} dans le classeur : ton manager en prépare et le bot te les "
                "enverra ici automatiquement.")
    blocs = []
    for i, c in enumerate(comptes, start=1):
        role = "privé (ton compte perso de la mission)" if i == len(comptes) and len(comptes) >= 3 else "croissance"
        etat = "à créer sur ton téléphone" if _norm(c["etat"]) in ("a creer", "à créer") else f"déjà créé ({c['etat']})"
        blocs.append(f"**Compte {i} · {role}** — {etat}\n"
                     f"Identifiant : `{c['handle']}`\n"
                     f"Mot de passe : `{c['mdp'] or '— (demande à ton manager)'}`\n"
                     + (f"E-mail : `{c['mail']}`\n" if c["mail"] else "")
                     + (f"Téléphone : `{c['phone']}`\n" if c["phone"] else ""))
    return (f"🔐 **Tes comptes Instagram, {prenom}** (créatrice : {creatrice})\n\n" + "\n".join(blocs) + "\n"
            "Règles : création et connexion **uniquement depuis ton téléphone**, jamais depuis un navigateur ; "
            "un compte à la fois ; le code de vérification arrive ici via le bot (`!code`) ; "
            "warm-up de la Fiche 2 toute la première semaine, puis 2 Reels par jour sur chaque compte de croissance. "
            "Ne partage jamais ces accès : ils appartiennent à l'agence.")


# ------------------------------------------------------------------ Drive
async def dossier_drive(prenom: str, creatrice: str, email: str) -> str:
    """Dossier personnel du clipper (copie des sources de la créatrice), partagé en lecture. '' si impossible."""
    if not drive_agence.actif():
        return ""
    cfg = _sources().get(creatrice) or _sources().get(creatrice.split()[0]) or {}
    parent, sources = cfg.get("parent", ""), cfg.get("sources", [])
    if not parent or not sources:
        journal.info("DRIVE_SOURCES sans entrée pour %s", creatrice)
        return ""
    dossier_id, url = "", ""
    for src in sources:
        if not isinstance(src, dict):
            src = {"id": src}
        bilan = await drive_agence.copier_dossier(src["id"], parent, prenom, types=src.get("types") or ("image", "video"),
                                                  max_fichiers=int(src.get("max", 0)), sous=src.get("sous", ""))
        dossier_id, url = bilan.get("id") or dossier_id, bilan.get("url") or url
    if dossier_id and email:
        try:
            await drive_agence.partager(dossier_id, email, "reader")
        except RuntimeError as erreur:
            journal.warning("Partage Drive %s : %s", prenom, erreur)
    return url or (google_api.drive_lien(dossier_id) if dossier_id else "")


# ------------------------------------------------------------------ livraison
async def livrer(membre, creatrice: str, salon=None, declencheur: str = "!creatrice") -> str:
    """Tout l'onboarding d'un clipper. Renvoie la ligne à poster à l'admin / au manager."""
    prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
    etat = _lire_etat()
    fiche = etat["clippers"].setdefault(str(membre.id), {})
    resultat = []
    # 1. comptes depuis le classeur
    comptes = []
    if actif():
        try:
            tous = await lire_comptes()
            deja = [c for c in tous if _norm(c["gerant"]) == _norm(prenom) and _norm(c["utilisation"]) == "clipper"
                    and _pour_creatrice(c, creatrice)]
            comptes = deja[:COMPTES_PAR_CLIPPER]
            if len(comptes) < COMPTES_PAR_CLIPPER:
                nouveaux = disponibles(tous, creatrice, COMPTES_PAR_CLIPPER - len(comptes))
                if nouveaux:
                    await reserver(nouveaux, prenom)
                comptes += nouveaux
            resultat.append(f"{len(comptes)} compte(s)" + (" (aucun libre dans le classeur !)" if not comptes else ""))
        except RuntimeError as erreur:
            resultat.append(f"classeur : {erreur}")
    else:
        resultat.append("classeur non branché")
    # 2. lien GAML
    lien = ""
    try:
        d = paie_clics._lire() if paie_clics.actif() else {"liens": {}}
        lids = paie_clics.liens_de(d, str(membre.id))
        if lids:
            lien = d["liens"][lids[0]].get("url", "")
        elif paie_clics.actif():
            liens = await paie_clics.liens_gaml()
            modeles = [l for l in liens if _norm(str(l.get("name", "")).split()[0] if l.get("name") else "") == _norm(creatrice.split()[0])
                       and paie_clics._prenom_note(l.get("note"))]
            if modeles:
                nouveau = await paie_clics.cloner_lien(modeles[0]["id"], modeles[0].get("name", creatrice), f"Clipping {prenom}")
                d["liens"][nouveau["id"]] = {"uid": str(membre.id), "note": f"Clipping {prenom}", "url": nouveau["url"],
                                             "creatrice": creatrice.split()[0], "depuis": _deps["heure_paris"]().date().isoformat(),
                                             "par": "onboarding"}
                paie_clics._ecrire(d)
                lien = nouveau["url"]
        resultat.append("lien GAML " + ("✅" if lien else "absent"))
    except RuntimeError as erreur:
        resultat.append(f"GAML : {erreur}")
    # 3. Drive
    drive = ""
    try:
        email = (_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("liaisons", {}).get(str(membre.id), {}).get("email", "")
                 or fiche.get("email", ""))
        drive = await dossier_drive(prenom, creatrice, email)
        resultat.append("Drive " + ("✅" if drive else ("sans e-mail du clipper" if drive_agence.actif() and not email else "non branché")))
    except RuntimeError as erreur:
        resultat.append(f"Drive : {erreur}")
    # 4. message
    texte = message_comptes(comptes, prenom, creatrice)
    if lien:
        texte += f"\n\n🔗 **Ton lien en bio** (le même sur tous tes comptes) : {lien}\nC'est lui qui compte tes visites : `!mesclics`."
    if drive:
        texte += f"\n\n📁 **Ton Drive** (photos et Reels de {creatrice.split()[0]}, lecture seule) : {drive}"
    cible = salon if salon is not None else membre
    try:
        await cible.send(texte[:1990])
        if len(texte) > 1990:
            await cible.send(texte[1990:3980])
    except (discord.Forbidden, discord.HTTPException) as erreur:
        resultat.append(f"envoi impossible ({type(erreur).__name__})")
    for c in comptes:
        etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    fiche.update({"creatrice": creatrice, "comptes": [c["handle"] for c in comptes], "lien": lien, "drive": drive,
                  "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "par": declencheur})
    _ecrire_etat(etat)
    return f"📦 Onboarding de {membre.display_name} ({creatrice}) : " + " · ".join(resultat)


# ------------------------------------------------------------------ le classeur comme télécommande
async def boucle(client, deps: dict):
    """Toutes les 15 minutes : un compte dont la colonne Gérant porte le prénom d'un membre, et qui ne lui a
    pas encore été livré, part dans son salon perso. Attribuer ou changer un compte se fait donc dans le
    classeur, sans commande."""
    global _deps
    _deps = deps
    await client.wait_until_ready()
    if not actif():
        journal.info("Onboarding par classeur inactif (CLASSEUR_LOGINS_ID / compte de service absents)")
        return
    journal.info("Onboarding par classeur actif (%s, %s comptes par clipper)", ONGLET_LOGINS, COMPTES_PAR_CLIPPER)
    while not client.is_closed():
        try:
            etat = _lire_etat()
            comptes = await lire_comptes()
            par_prenom = {}
            for c in comptes:
                g = _norm(c["gerant"])
                if g in GERANTS_LIBRES or _norm(c["utilisation"]) != "clipper" or not c["handle"]:
                    continue
                par_prenom.setdefault(g, []).append(c)
            for g, lignes in par_prenom.items():
                membre = deps["membre_par_prenom"](g)
                if membre is None:
                    continue
                nouveaux = [c for c in lignes if etat["livres"].get(c["handle"].lower(), {}).get("uid") != str(membre.id)]
                if not nouveaux:
                    continue
                salon = deps["salon_perso"](str(membre.id))
                cible = salon if salon is not None else membre
                creatrice = nouveaux[0]["creatrice"] or etat["clippers"].get(str(membre.id), {}).get("creatrice", "")
                try:
                    await cible.send(("🔐 **Compte(s) attribué(s) depuis le classeur**\n\n" +
                                      message_comptes(nouveaux, membre.display_name.split()[0], creatrice or "?"))[:1990])
                except (discord.Forbidden, discord.HTTPException) as erreur:
                    journal.warning("Livraison classeur %s : %s", membre.display_name, erreur)
                    continue
                for c in nouveaux:
                    etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                fiche = etat["clippers"].setdefault(str(membre.id), {})
                fiche["comptes"] = sorted(set(fiche.get("comptes", [])) | {c["handle"] for c in nouveaux})
                _ecrire_etat(etat)
                canal = await deps["canal_admin"]()
                if canal:
                    await canal.send(f"🔐 {len(nouveaux)} compte(s) du classeur livré(s) à {membre.mention} (colonne Gérant).")
        except Exception as erreur:                                 # la boucle ne meurt jamais
            journal.warning("Boucle onboarding : %s", erreur)
        await asyncio.sleep(900)


# ------------------------------------------------------------------ commande
async def commande_staff(message, texte: str) -> bool:
    """`!comptes-libres [Créatrice]` : ce que le classeur a de disponible ; `!onboarding @clipper` : rejouer la livraison."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!comptes-libres", "!onboarding"):
        return False
    if not actif():
        await message.reply("Onboarding par classeur inactif : `CLASSEUR_LOGINS_ID` et le compte de service dans Railway.")
        return True
    if mots[0].lower() == "!comptes-libres":
        try:
            comptes = await lire_comptes()
        except RuntimeError as erreur:
            await message.reply(f"❌ {erreur}")
            return True
        cible = " ".join(mots[1:]).strip()
        libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
                  and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and (not cible or _pour_creatrice(c, cible))]
        par_c = {}
        for c in libres:
            par_c.setdefault(c["creatrice"] or "?", []).append(c)
        lignes = [f"🗂️ **Comptes libres dans le classeur** ({len(libres)})"]
        for cr, lst in sorted(par_c.items()):
            crees = sum(1 for c in lst if _norm(c["etat"]) not in ("a creer", "à créer"))
            lignes.append(f"· {cr} — {len(lst)} libre(s) : {crees} créé(s), {len(lst) - crees} à créer")
        lignes.append("-# Un compte est « libre » quand Utilisation = Clipper, Gérant vide ou x/y/z, état à créer / GOOD / WARMUP / PRIVÉ / ACTIF.")
        await message.reply("\n".join(lignes)[:1990])
        return True
    if not message.mentions:
        await message.reply("Format : `!onboarding @clipper` — renvoie ses comptes, son lien et son Drive dans son salon perso.")
        return True
    membre = message.mentions[0]
    registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {})
    creatrice = " ".join(m for m in mots[1:] if not m.startswith("<@")).strip() or registre.get(str(membre.id), {}).get("creatrice", "")
    if not creatrice:
        await message.reply("Pas de créatrice connue : `!onboarding @clipper Chloé` ou d'abord `!creatrice @clipper Chloé`.")
        return True
    bilan = await livrer(membre, creatrice, _deps["salon_perso"](str(membre.id)), declencheur=f"!onboarding par {message.author.id}")
    await message.reply(bilan[:1990])
    return True
