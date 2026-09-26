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

import codes_2fa
import drive_agence
import google_api
import paie_clics

journal = logging.getLogger("onboarding")

CLASSEUR_LOGINS_ID = os.environ.get("CLASSEUR_LOGINS_ID", "").strip()
ONGLET_LOGINS = os.environ.get("ONGLET_LOGINS", "Instagram").strip() or "Instagram"
COMPTES_PAR_CLIPPER = int(os.environ.get("COMPTES_PAR_CLIPPER", "3") or 3)
GERANTS_LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
ETATS_DISPONIBLES = {"a creer", "à créer", "good", "warmup", "warm-up", "prive", "privé", "actif", "ok"}
COL_DEFAUT = {"etat": 0, "handle": 1, "mdp": 2, "followers": 3, "mail": 4, "phone": 5, "gerant": 6, "utilisation": 7, "numero": 8, "creatrice": 9}
# 26/09 : Gaëtan insère des colonnes (Clics GAML, Lien GAML associé) → les colonnes se trouvent par leur en-tête, jamais par position
MOTS_COLONNES = (("etat", ("etat", "statut")), ("handle", ("@", "ig", "compte", "pseudo")), ("mdp", ("mdp", "mot de passe", "password")),
                 ("followers", ("followers", "abonnes")), ("clics", ("clics", "gaml last", "visites")), ("numero", ("numero",)),
                 ("mail", ("mail", "email")), ("phone", ("phone", "tel")), ("gerant", ("gerant", "clipper")),
                 ("utilisation", ("utilisation", "usage")), ("creatrice", ("creatrice",)), ("pod", ("pod",)),
                 ("lien_gaml", ("lien gaml", "gaml associe")), ("lien_infloww", ("infloww",)))
_colonnes = dict(COL_DEFAUT)


def colonnes(en_tete: list) -> dict:
    """{champ: index de colonne} d'après la ligne d'en-tête (accents/casse ignorés, premier mot-clé gagnant, une colonne
    ne sert qu'une fois). Sans en-tête reconnu, l'ordre historique."""
    trouve = {}
    pris = set()
    for champ, mots in MOTS_COLONNES:
        for i, h in enumerate(en_tete):
            hn = _norm(h)
            if i in pris or not hn:
                continue
            if champ == "mail" and "numero" in hn:
                continue                                                # « Numéro Mail » n'est pas la colonne Mail
            if any(m in hn for m in mots):
                trouve[champ] = i
                pris.add(i)
                break
    if not all(k in trouve for k in ("etat", "handle", "gerant")):
        return dict(COL_DEFAUT)
    return {**COL_DEFAUT, **trouve}


def lettre(champ: str) -> str:
    """La lettre de colonne d'un champ (A, B, …, AA) d'après le dernier en-tête lu."""
    i = _colonnes.get(champ, COL_DEFAUT.get(champ, 0))
    return (chr(64 + i // 26) if i >= 26 else "") + chr(65 + i % 26)
RE_PRIVE = re.compile(r"priv|secret|onlyme|perso")                 # handle d'un compte privé (le 3e du trio)
JOURS_NOUVEAU = int(os.environ.get("ONBOARDING_JOURS_NOUVEAU", "45") or 45)   # un membre arrivé depuis moins longtemps est « nouveau »
A_CREER = ("a creer", "à créer")
MENTION_LIBERE = "à mettre Metricool"                              # Utilisation d'un compte créé rendu par un clipper parti

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
    """Toutes les lignes de l'onglet (index de ligne 1-based inclus), colonnes reconnues par leur en-tête, cellules
    manquantes complétées."""
    global _colonnes
    lignes = await google_api.sheets_lire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!A1:Z")
    if not lignes:
        return []
    _colonnes = colonnes(lignes[0])
    out = []
    for i, l in enumerate(lignes[1:], start=2):
        l = (l + [""] * 26)[:26]
        def champ(nom):
            return l[_colonnes[nom]].strip() if nom in _colonnes else ""
        out.append({"ligne": i, "etat": champ("etat"), "handle": champ("handle").lstrip("@"), "mdp": champ("mdp"),
                    "followers": champ("followers"), "clics": champ("clics"), "mail": champ("mail"), "phone": champ("phone"),
                    "gerant": champ("gerant"), "utilisation": champ("utilisation"), "numero": champ("numero"),
                    "creatrice": champ("creatrice"), "lien_gaml": champ("lien_gaml")})
    return out


def _pour_creatrice(c: dict, creatrice: str) -> bool:
    cible = _norm(creatrice).split()[0] if _norm(creatrice) else ""
    return bool(cible) and _norm(c["creatrice"]).startswith(cible)


def _est_prive(c: dict) -> bool:
    return _norm(c["etat"]) in ("prive", "privé") or RE_PRIVE.search(_norm(c["handle"] or "")) is not None


def _crees(lignes: list) -> list:
    return [c for c in lignes if _norm(c["etat"]) not in A_CREER]


def disponibles(comptes: list, creatrice: str, n: int) -> list:
    """Lignes libres pour cette créatrice : Utilisation = Clipper, Gérant libre, état utilisable, handle présent.
    Les comptes déjà créés (GOOD, WARMUP, PRIVÉ, ACTIF) passent avant ceux « à créer ». Le trio livré fait
    n-1 comptes de croissance + 1 compte privé quand le classeur en a un (24/09 : avant, le « privé » annoncé
    était juste le dernier de la liste)."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)
              and (c.get("mail") or _norm(c["etat"]) not in A_CREER)]        # 25/09 : un compte à créer sans e-mail est inutilisable
    libres.sort(key=lambda c: (_norm(c["etat"]) in A_CREER, c["ligne"]))
    if n < 3:
        return libres[:n]
    choix = [c for c in libres if not _est_prive(c)][:n - 1] + [c for c in libres if _est_prive(c)][:1]
    if len(choix) < n:                                              # pas assez d'un côté : on complète avec le reste
        choix += [c for c in libres if c not in choix][:n - len(choix)]
    return choix


def pool(comptes: list, creatrice: str) -> dict:
    """État du vivier d'une créatrice : lignes « à créer » libres, dont celles avec e-mail (les seules livrables),
    et comptes déjà créés libres. 25/09 : Chloé avait 18 lignes à créer, zéro avec e-mail."""
    libres = [c for c in comptes if _norm(c["utilisation"]) == "clipper" and _norm(c["gerant"]) in GERANTS_LIBRES
              and _norm(c["etat"]) in ETATS_DISPONIBLES and c["handle"] and _pour_creatrice(c, creatrice)]
    a_creer = [c for c in libres if _norm(c["etat"]) in A_CREER]
    return {"a_creer": len(a_creer), "avec_mail": sum(1 for c in a_creer if c.get("mail")),
            "crees": len(libres) - len(a_creer), "livrables": len(disponibles(comptes, creatrice, 999))}


async def marquer_etat(handle: str, etat: str) -> bool:
    """Colonne ETAT du classeur pour un compte (25/09 : le parcours passe une ligne à WARMUP quand le clipper valide
    la création, puis à GOOD après le warm-up). Une seule cellule, jamais la structure."""
    if not actif() or not handle:
        return False
    cible = _norm(handle).lstrip("@")
    for c in await lire_comptes():
        if _norm(c["handle"]).lstrip("@") == cible:
            if _norm(c["etat"]) == _norm(etat):
                return True
            try:
                await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!{lettre('etat')}{c['ligne']}", [[etat]])
                journal.info("Classeur : %s → %s (ligne %s)", c["handle"], etat, c["ligne"])
                return True
            except Exception as erreur:
                journal.warning("Classeur : état de %s non écrit : %s", c["handle"], erreur)
                return False
    return False


def _nouveau(membre, etat: dict) -> bool:
    """Un clipper que le bot n'a jamais onboardé (aucune créatrice dans sa fiche) et arrivé sur le serveur depuis
    moins de JOURS_NOUVEAU jours. Un tel membre ne peut pas légitimement posséder des comptes déjà créés :
    si le classeur en porte à son prénom, c'est l'homonyme d'un ancien clipper (Eddy, 24/09)."""
    uid = str(membre.id)
    if etat["clippers"].get(uid, {}).get("creatrice"):
        return False
    if _deps.get("lire_json") and _deps.get("FICHIER_EQUIPES") and \
            _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {}).get("creatrice"):
        return False                                                # `!creatrice` déjà passé : clipper établi
    arrive = getattr(membre, "joined_at", None)
    if arrive is None:
        return True
    if arrive.tzinfo is None:
        arrive = arrive.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - arrive).days < JOURS_NOUVEAU


def _ecarter(etat: dict, membre, lignes: list) -> list:
    """Les comptes déjà créés qu'on ne livre pas à un nouveau venu, mémorisés dans etat["ecartes"] pour que la
    boucle ne les représente pas toutes les 15 minutes. Levés par `!onboarding` (forçage) ou `!liberer`."""
    douteux = _crees(lignes)
    ecartes = etat.setdefault("ecartes", {})
    for c in douteux:
        ecartes[c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return douteux


def _ecarte_pour(etat: dict, c: dict, uid: str) -> bool:
    return etat.get("ecartes", {}).get(c["handle"].lower(), {}).get("uid") == str(uid)


async def reserver(comptes: list, prenom_clipper: str) -> int:
    """Écrit le prénom du clipper dans la colonne Gérant de chaque ligne. Renvoie le nombre de cellules écrites."""
    n = 0
    for c in comptes:
        n += await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!{lettre('gerant')}{c['ligne']}", [[prenom_clipper]])
    return n


def message_comptes(comptes: list, prenom: str, creatrice: str) -> str:
    if not comptes:
        return (f"⚠️ Il n'y a pas encore de compte prêt pour {creatrice}. Ton manager en prépare. "
                "Je te les envoie ici dès qu'ils sont prêts.")
    blocs = []
    ordonnes = sorted(comptes, key=_est_prive)                      # le privé en dernier
    a_un_prive = any(_est_prive(c) for c in comptes)
    for i, c in enumerate(ordonnes, start=1):
        prive = _est_prive(c) if a_un_prive else (i == len(ordonnes) and len(ordonnes) >= 3)
        role = "privé, ton compte secret" if prive else "il publie"
        etat = "à créer, sur ton téléphone" if _norm(c["etat"]) in A_CREER else "déjà créé"
        blocs.append(f"**Compte {i} · {role}** — {etat}\n"
                     f"Identifiant : `{c['handle']}`\n"
                     f"Mot de passe : `{c['mdp'] or 'demande-le à ton manager'}`\n"
                     + (f"E-mail : `{c['mail']}`\n" if c["mail"] else "")
                     + (f"Téléphone : `{c['phone']}`\n" if c["phone"] else ""))
    return (f"🔐 **Tes comptes Instagram, {prenom}** · créatrice : {creatrice}\n\n" + "\n".join(blocs) + "\n"
            "Les règles :\n"
            "• Tu crées et tu te connectes **seulement sur ton téléphone**. Jamais sur un ordinateur.\n"
            "• Un compte par jour.\n"
            "• Le code d'Instagram arrive ici. Écris `!code`.\n"
            "• La première semaine, tu chauffes les comptes. Tu ne publies rien. Après, 2 Reels par jour sur chaque compte qui publie.\n"
            "• Ne donne jamais ces accès à quelqu'un. Ils sont à l'agence.")


# ------------------------------------------------------------------ Drive
async def _partager(fichier_id: str, email: str) -> bool:
    """Partage en lecture : par le compte de service d'abord, par le script de l'agence sinon."""
    try:
        await google_api.drive_partager(fichier_id, email, "reader")
        return True
    except RuntimeError as erreur:
        journal.info("Partage par le compte de service refusé (%s), essai par le script", str(erreur)[:80])
    if drive_agence.actif():
        try:
            await drive_agence.partager(fichier_id, email, "reader")
            return True
        except RuntimeError as erreur:
            journal.warning("Partage Drive %s : %s", fichier_id[:8], erreur)
    return False


async def dossier_drive(prenom: str, creatrice: str, email: str) -> str:
    """Dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice : un raccourci vers CHAQUE source (Reels,
    photos : tout le contenu, rien de copié, aucun espace consommé), les sources partagées en lecture à son e-mail.
    Décision du 24/09 : plus de copies limitées ; 25/09 : plus de sous-dossier « Reels spoofés » (spoofer abandonné).
    '' si le Drive n'est pas configuré."""
    if not google_api.actif():
        return ""
    cfg = _sources().get(creatrice) or _sources().get(creatrice.split()[0]) or {}
    parent, sources = cfg.get("parent", ""), cfg.get("sources", [])
    if not parent or not sources:
        journal.info("DRIVE_SOURCES sans entrée pour %s", creatrice)
        return ""
    dossier = await google_api.drive_trouver_dossier(prenom, parent) or await google_api.drive_creer_dossier(prenom, parent)
    vus = {}
    for src in sources:
        if not isinstance(src, dict):
            src = {"id": src}
        libelle = src.get("sous") or "Contenu"
        vus[libelle] = vus.get(libelle, 0) + 1
        nom = f"{libelle} {vus[libelle]} — {creatrice.split()[0]}" if vus[libelle] > 1 else f"{libelle} — {creatrice.split()[0]}"
        if email:
            await _partager(src["id"], email)
        try:
            await google_api.drive_raccourci(nom, src["id"], dossier)
        except RuntimeError as erreur:
            journal.warning("Raccourci %s pour %s : %s", nom, prenom, erreur)
    if email:
        await _partager(dossier, email)
    journal.info("Drive de %s (%s) prêt : %s sources, e-mail %s", prenom, creatrice, len(sources), "oui" if email else "non")
    return google_api.drive_lien(dossier)


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
            if declencheur.startswith("!onboarding"):                # forçage explicite : on lève les écartés
                for c in deja:
                    etat.get("ecartes", {}).pop(c["handle"].lower(), None)
            elif _nouveau(membre, etat):                             # 24/09 : nouvel Eddy ≠ ancien Eddy viré
                douteux = _ecarter(etat, membre, deja)
                if douteux:
                    deja = [c for c in deja if c not in douteux]
                    resultat.append(f"⚠️ {len(douteux)} compte(s) déjà créé(s) au nom de {prenom} dans le classeur, NON livrés "
                                    f"(homonyme d'un ancien clipper ?) : {', '.join(c['handle'] for c in douteux)} — "
                                    f"`!liberer {prenom} <handles>` pour les rendre, `!onboarding @{prenom}` si ce sont bien les siens")
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
    drive, email = "", ""
    try:
        email = (_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("liaisons", {}).get(str(membre.id), {}).get("email", "")
                 or fiche.get("email", ""))
        drive = await dossier_drive(prenom, creatrice, email)
        resultat.append("Drive " + ("✅" + ("" if email else " (sans e-mail : rien partagé, `!onboarding` après son e-mail)") if drive
                                    else "non configuré"))
    except RuntimeError as erreur:
        resultat.append(f"Drive : {erreur}")
    # 4. message
    texte = message_comptes(comptes, prenom, creatrice)
    if lien:
        texte += f"\n\n🔗 **Ton lien** : {lien}\nCe lien compte tes visites. Écris `!mesclics` pour les voir."
    if drive:
        texte += (f"\n\n📁 **Ton Drive**, avec les photos et les vidéos de {creatrice.split()[0]} : {drive}\nTu regardes et tu télécharges. Tu ne modifies rien."
                  + ("" if email else "\nPour l'ouvrir, envoie-moi ici **ton adresse Gmail**, celle de ton téléphone. Je te le partage tout de suite."))
    if salon is not None and codes_2fa.actif():
        try:
            n_alias = codes_2fa.rattacher([c["mail"] for c in comptes if c.get("mail")], str(salon.id), "onboarding")
            if n_alias:
                texte += f"\n\n📨 Les codes Instagram de {'ces adresses' if n_alias > 1 else 'cette adresse'} arrivent ici tout seuls."
                resultat.append(f"{n_alias} alias 2FA rattaché(s)")
        except Exception as erreur:                                     # jamais bloquer la livraison
            journal.warning("Alias 2FA %s : %s", prenom, erreur)
    cible = salon if salon is not None else membre
    try:
        await cible.send(texte[:1990])
        if len(texte) > 1990:
            await cible.send(texte[1990:3980])
    except (discord.Forbidden, discord.HTTPException) as erreur:
        resultat.append(f"envoi impossible ({type(erreur).__name__})")
    for c in comptes:
        etat["livres"][c["handle"].lower()] = {"uid": str(membre.id), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    fiche.update({"creatrice": creatrice, "comptes": [c["handle"] for c in comptes], "lien": lien, "drive": drive, "email": email,
                  "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "par": declencheur})
    _ecrire_etat(etat)
    return f"📦 Onboarding de {membre.display_name} ({creatrice}) : " + " · ".join(resultat)


RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


async def message_clipper(message) -> bool:
    """Un clipper qui poste son adresse e-mail dans son salon perso (ou en MP) alors que son Drive n'a pas encore
    été partagé : l'adresse va dans sa fiche et le partage part tout de suite (25/09 : Daniella, « sans e-mail :
    rien partagé », un bilan que seul l'admin voyait)."""
    if not actif() or getattr(message.author, "bot", False):
        return False
    m = RE_EMAIL.search(message.content or "")
    if not m:
        return False
    uid = str(message.author.id)
    etat = _lire_etat()
    fiche = etat["clippers"].get(uid)
    if not fiche or not fiche.get("creatrice"):
        return False
    if message.guild is not None:
        salon = _deps["salon_perso"](uid)
        if salon is None or salon.id != message.channel.id:
            return False
    email = m.group(0).strip().lower()
    if fiche.get("email") == email and fiche.get("drive"):
        return False
    fiche["email"] = email
    _ecrire_etat(etat)
    prenom = message.author.display_name.split()[0] if message.author.display_name.split() else message.author.display_name
    try:
        drive = await dossier_drive(prenom, fiche["creatrice"], email)
    except RuntimeError as erreur:
        await message.reply(f"J'ai noté ton adresse : {email}. Mais le partage du Drive n'a pas marché. Ton manager va le refaire.")
        return True
    if drive:
        fiche["drive"] = drive
        _ecrire_etat(etat)
        await message.reply(f"📁 C'est fait, le Drive est partagé avec {email} : {drive}\nOuvre-le avec ce compte Google. Tu reçois aussi un e-mail.")
    else:
        await message.reply(f"J'ai noté ton adresse : {email}. Le Drive de {fiche['creatrice']} n'est pas encore prêt. Ton manager s'en occupe.")
    return True


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
                nouveaux = [c for c in lignes if etat["livres"].get(c["handle"].lower(), {}).get("uid") != str(membre.id)
                            and not _ecarte_pour(etat, c, membre.id)]
                if not nouveaux:
                    continue
                prenom = membre.display_name.split()[0] if membre.display_name.split() else membre.display_name
                creatrice = nouveaux[0]["creatrice"] or etat["clippers"].get(str(membre.id), {}).get("creatrice", "")
                if _nouveau(membre, etat):                          # 24/09 : un nouveau venu n'a pas de comptes déjà créés
                    douteux = _ecarter(etat, membre, nouveaux)
                    if douteux:
                        nouveaux = [c for c in nouveaux if c not in douteux]
                        _ecrire_etat(etat)
                        canal = await deps["canal_admin"]()
                        if canal:
                            handles = " ".join(c["handle"] for c in douteux)
                            await canal.send(
                                f"⚠️ **Homonyme possible** : le classeur porte « {prenom} » sur {len(douteux)} compte(s) déjà créé(s) "
                                f"({handles}) alors que {membre.mention} vient d'arriver et n'a encore reçu aucune créatrice. "
                                f"Ancien clipper du même prénom ? Rien livré. Si ce sont bien les siens : `!onboarding @{prenom} {creatrice}`. "
                                f"Sinon : `!liberer {prenom} {handles}` puis `!creatrice @{prenom} {creatrice}`."[:1990])
                    if not nouveaux:
                        continue
                salon = deps["salon_perso"](str(membre.id))
                cible = salon if salon is not None else membre
                try:
                    await cible.send(("🔐 **Compte(s) attribué(s) depuis le classeur**\n\n" +
                                      message_comptes(nouveaux, prenom, creatrice or "?"))[:1990])
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
async def liberer(prenom: str, handles=(), pool: bool = False) -> list:
    """Rend les comptes d'un clipper parti : colonne Gérant vidée sur ses lignes (toutes, ou seulement `handles`) ;
    les comptes déjà créés passent en Utilisation « à mettre Metricool » (ils sortent du pool des clippers), sauf
    `pool=True` ; ceux « à créer » restent au pool. Nettoie l'état du bot (livrés, écartés, fiches) et détache les
    alias 2FA. Renvoie une ligne de bilan par compte (sans mot de passe). C'est l'étape qui manquait quand un
    clipper est viré : sans elle, le prochain homonyme hérite de ses comptes (Eddy, 24/09)."""
    cibles = {_norm(h).lstrip("@") for h in handles if _norm(h)}
    comptes = await lire_comptes()
    lignes = [c for c in comptes if _norm(c["gerant"]) == _norm(prenom) and (not cibles or _norm(c["handle"]) in cibles)]
    if not lignes:
        return []
    etat = _lire_etat()
    bilan = []
    for c in lignes:
        await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!{lettre('gerant')}{c['ligne']}", [[""]])
        metricool = _norm(c["etat"]) not in A_CREER and not pool
        if metricool:
            await google_api.sheets_ecrire(CLASSEUR_LOGINS_ID, f"{ONGLET_LOGINS}!{lettre('utilisation')}{c['ligne']}", [[MENTION_LIBERE]])
        h = c["handle"].lower()
        etat["livres"].pop(h, None)
        etat.get("ecartes", {}).pop(h, None)
        for fiche in etat["clippers"].values():
            if c["handle"] in fiche.get("comptes", []):
                fiche["comptes"] = [x for x in fiche["comptes"] if x != c["handle"]]
        bilan.append(f"· `{c['handle']}` ({c['etat'] or 'état ?'}) → " + (MENTION_LIBERE if metricool else "retour au pool des clippers"))
    _ecrire_etat(etat)
    if codes_2fa.actif():
        n_alias = codes_2fa.detacher([c["mail"] for c in lignes if c.get("mail")])
        if n_alias:
            bilan.append(f"-# {n_alias} alias 2FA détaché(s).")
    return bilan


async def commande_staff(message, texte: str) -> bool:
    """`!comptes-libres [Créatrice]` : ce que le classeur a de disponible ; `!onboarding @clipper` : rejouer la livraison ;
    `!liberer Prénom [handle …] [pool]` : rendre les comptes d'un clipper parti."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!comptes-libres", "!onboarding", "!liberer", "!libérer"):
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
            crees = sum(1 for c in lst if _norm(c["etat"]) not in A_CREER)
            a_creer = [c for c in lst if _norm(c["etat"]) in A_CREER]
            avec_mail = sum(1 for c in a_creer if c.get("mail"))
            livrables = crees + avec_mail
            lignes.append(f"· {cr} — {len(lst)} libre(s) : {crees} créé(s), {len(a_creer)} à créer dont **{avec_mail} avec e-mail** "
                          f"→ {livrables} livrable(s) = {livrables // 3} clipper(s)"
                          + (" ⚠️ ajoute des e-mails (iCloud « Masquer mon adresse ») avant le prochain clipper" if livrables < 3 else ""))
        lignes.append("-# Un compte est « libre » quand Utilisation = Clipper, Gérant vide ou x/y/z, état à créer / GOOD / WARMUP / PRIVÉ / ACTIF. "
                      "Un compte à créer sans e-mail n'est pas livré (25/09) : impossible à créer sur Instagram ni à relayer en 2FA.")
        await message.reply("\n".join(lignes)[:1990])
        return True
    if mots[0].lower() in ("!liberer", "!libérer"):
        args = [m for m in mots[1:] if m.lower() != "pool"]
        if not args:
            await message.reply("Format : `!liberer Prénom [handle …] [pool]` — vide la colonne Gérant des comptes de ce clipper "
                                "(tous, ou seulement les handles cités). Les comptes déjà créés passent en « à mettre Metricool » ; "
                                "avec `pool`, ils restent disponibles pour le prochain clipper.")
            return True
        prenom = args[0].lstrip("@")
        try:
            bilan = await liberer(prenom, args[1:], pool=any(m.lower() == "pool" for m in mots[1:]))
        except RuntimeError as erreur:
            await message.reply(f"❌ {erreur}")
            return True
        if not bilan:
            await message.reply(f"Aucune ligne du classeur avec Gérant « {prenom} »" + (" pour ces handles." if args[1:] else "."))
            return True
        n = sum(1 for b in bilan if b.startswith("·"))
        await message.reply((f"🔓 **{n} compte(s) libéré(s)** — Gérant « {prenom} » effacé dans le classeur\n" + "\n".join(bilan)
                             + "\n-# Lien GAML, salon perso et rôles non touchés (`!sortie` pour ça).")[:1990])
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
