"""Parcours guidé du clipper dans son salon perso, et mémoire par clipper (25/09/2026).

Dès `!creatrice`, une fois ses comptes livrés, le bot déroule dans le salon perso un parcours en étapes :
créer le compte 1, le compte 2, le compte privé, le warm-up (7 jours comptés chaque matin), le premier Reel,
le lien en bio, la routine. Chaque étape = un message court, des boutons-liens vers la bonne fiche du forum
formation et le salon d'infos de la créatrice, et un bouton « ✅ C'est fait » qui ouvre l'étape suivante.
Dans ce salon, l'assistant IA joue le manager : il reçoit la mémoire du clipper (étape, comptes, lien, clics,
notes du manager) avec chaque question.

État dans parcours.json : {uid: {"prenom", "creatrice", "salon_id", "etape", "dates": {n: iso}, "messages": {n: id},
"notes": [{"date", "par", "texte"}], "warmup_jour"}}. Commandes manager : `!etape @clipper [n]`, `!note @clipper texte`,
`!memoire @clipper`. Le module ne connaît pas bot_discord : tout passe par `configurer(deps)`.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import discord

import codes_2fa
import lien_app
import onboarding
import paie_clics

journal = logging.getLogger("parcours")
_deps = {}
WARMUP_JOURS = int(os.environ.get("WARMUP_JOURS", "1") or 1)
# 01/10 (Gaëtan : « la même règle pour tous, nouveaux et anciens, plus de période d'essai à part : le compte suivant s'ouvre
# tout seul, au plus tôt 48 h après la création du précédent, et seulement quand 2 Reels sont publiés dessus ») : remplace la
# période d'essai du 30/09 (5 Reels en 72 h, nouveaux seulement). Les Reels sont ceux que le scan du matin voit, cumulés
# compte par compte dans la fiche (_cumuler_reels) ; les fiches encore « en essai » passent sous la règle sans message
# (_migrer_essai). `!etape @clipper n` (staff) force toujours.
REELS_OUVERTURE = int(os.environ.get("PARCOURS_REELS_OUVERTURE", "4") or 4)   # 05/10 (Gaëtan) : « 48 h et 4 Reels »
# 30/09 (Gaëtan : « arrête de spammer les clippeurs : une information à la fois, au bon moment ; un compte par un compte, on
# distille l'information et on ne la donne que quand il en a réellement besoin ») : chaque compte se fait en trois temps,
# un message chacun — 1) identifiants et création, bouton « créé » ; 2) photo, nom et bio en UN message, bouton « profil
# fait » ; 3) une ligne de warm-up. Le compte suivant arrive tout seul 48 h plus tard (la règle des 48 h n'était qu'une
# phrase : le compte 2 tombait dès le bouton du compte 1), et « il peut publier » arrive 24 h plus tard, avec le Drive.
DISTILLE_DEPUIS = "2026-09-30T06:40:00+00:00"   # une étape envoyée avant : son profil est déjà parti (ancien déroulé), pas de doublon
ATTENTE_COMPTE_H = int(os.environ.get("PARCOURS_ATTENTE_COMPTE_H", "48") or 48)
WARMUP_H = int(os.environ.get("PARCOURS_WARMUP_H", "24") or 24)


def regle_comptes() -> str:
    """01/10 : le texte canonique de la règle des comptes, le même partout (salon, message de comptes, assistant)."""
    return (f"Un compte à la fois. Le suivant arrive tout seul ici, au plus tôt {ATTENTE_COMPTE_H} h après le précédent, "
            f"dès que {REELS_OUVERTURE} Reels sont publiés dessus.")


def texte_codes() -> str:
    """01/10 (Gaëtan : « les codes Instagram se demandent uniquement dans le salon code-instagram ») : la phrase canonique,
    avec le salon en lien cliquable quand son id est connu."""
    # 01/10 (fusion des lots) : une seule source, codes_2fa.texte_salon_codes() (lot B) ; même texte, même lien.
    try:
        return codes_2fa.texte_salon_codes()
    except Exception:                                                   # noqa: BLE001
        return "Un code Instagram ? Va dans #🔐-code-instagram et tape !code."


# 01/10 : plus de date ni de « compte 2 demain » ici, la règle canonique ; la date « au plus tôt » vit dans la ligne du matin
TEXTE_WARMUP = ("🔥 **Compte {n} : 24 h de warm-up.** Regarde des Reels, mets des likes, abonne-toi à 2 comptes. Pas de Reel.\n\n"
                "Je te dis ici quand il peut publier.\n\n"
                "{regle}")
TEXTE_PUBLIER = {1: ("✅ **Ton compte 1 peut publier.** {rythme}\n\n"
                     "Prends une vidéo dans ton Drive : {drive}\n\n"
                     "Modifie-la toujours avant : musique, texte, un début qui accroche (Fiche 3)."),
                 2: "✅ **Ton compte 2 peut publier.** 2 Reels par jour dessus aussi."}   # 26/09 (Gaëtan) : 24 h de warm-up par compte ; 01/10 : sans « comme sur le compte 1 » (BAN)
LIEN_REPORTING = os.environ.get("LIEN_REPORTING", "https://forms.gle/uhPewryox7R4jifv5").strip()   # formulaire du dimanche

ETAPES = {
    # 26/09 (Gaëtan) : textes courts, 24 h de warm-up sur chaque compte, puis les Reels.
    # 29/09 (Gaëtan) : « un compte tous les 48 h » — jamais plus vite, c'est ce qui limite les bans (7 comptes perdus le 28/09).
    # 08/10 (audit : dans le parcours automatique, la créatrice n'était jamais annoncée) : son nom et le bouton de son salon d'infos
    1: {"titre": "Étape 1 · Crée ton compte 1", "fiche": "1", "bouton": "✅ Compte 1 créé", "salons": ["info"],
        "texte": ("Ta créatrice : **{creatrice}**.\n\n"
                  "Identifiant :\n```\n{compte1}\n```\nE-mail :\n```\n{mail1}\n```\nMot de passe :\n```\n{mdp1}\n```\n"
                  "{creation1}\n\n"
                  "Créé ? Appuie sur le bouton.")},
    2: {"titre": "Étape 2 · Crée ton compte 2", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": [],
        "texte": ("Identifiant :\n```\n{compte2}\n```\nE-mail :\n```\n{mail2}\n```\nMot de passe :\n```\n{mdp2}\n```\n"
                  "{creation2}\n\n"
                  "Créé ? Appuie sur le bouton.")},
    # 05/10 (Gaëtan : « 2 comptes de croissance, story à la une qui mentionne le 3e compte privé avec le lien en bio ») : le
    # compte 3 est PRIVÉ, il ne publie pas ; son profil porte le lien dans la bio ; les comptes 1 et 2 pointent vers lui.
    3: {"titre": "Étape 3 · Crée ton compte 3, le privé", "fiche": "1", "bouton": "✅ Compte 3 créé", "salons": [],
        "texte": ("Identifiant :\n```\n{compte3}\n```\nE-mail :\n```\n{mail3}\n```\nMot de passe :\n```\n{mdp3}\n```\n"
                  "{creation3}\n\n"
                  "Ce compte est **privé** : il ne publie pas de Reel. C'est lui qui portera ton lien.\n\n"
                  "Créé ? Appuie sur le bouton.")},
    4: {"titre": "Étape 4 · 24 h de warm-up sur le compte 3 (Fiche 2)", "fiche": "2", "bouton": "✅ Warm-up fini", "salons": ["ressources"],
        "texte": ("**Compte 3, pendant 24 h** : pas de Reel. 10 min de Reels de créatrices françaises ({ressources}), "
                  "5 likes, 2 abonnements, 1 story sans lien.\n\n"
                  "**{autres}** : ils ont fini leur warm-up. 2 Reels par jour sur chacun, pris dans ton Drive, "   # 01/10 : sans les BAN
                  "et 1 story par jour (une photo du dossier Photos de ton Drive).\n\n"
                  "Dans 24 h, le compte 3 publie aussi.")},
    5: {"titre": "Étape 5 · Tes Reels sur les 3 comptes (Fiche 3)", "fiche": "3", "bouton": "✅ Premier Reel publié", "salons": ["ressources"],
        "texte": ("Tes vidéos : {drive}\n\n"
                  "1. Prends une vidéo dans ce dossier. Modifie-la toujours : musique, texte, un début qui accroche.\n"
                  "2. Publie-la sur {vivants}. Jamais la même vidéo sur deux comptes le même jour.\n\n"   # 01/10 : sans les comptes BAN
                  "Premier Reel en ligne ? Appuie sur le bouton.")},
    # 08/10 (audit) : les étapes 4 et 5 n'existent plus depuis le 05/10 ; le clipper voyait « Étape 3 » puis « Étape 6 ». Le numéro
    # interne reste 6 (fiches, boutons), seul le titre dit 4.
    6: {"titre": "Étape 4 · Ton lien et ta story à la une (Fiche 4)", "fiche": "4", "bouton": "✅ Lien mis", "salons": [],
        "texte": ("**Ton lien** : {lien}\n\n"
                  "1. Sur ton compte 3 (`{compte3}`, privé) : ce lien dans la **bio**. Nulle part ailleurs.\n"
                  "2. Sur ton compte 1 et ton compte 2 : une story (une photo ou une vidéo de ton Drive) avec le **widget de mention** "
                  "`@{compte3}`, puis cette story **à la une** (épinglée sur le profil). Une seule fois.\n"
                  "3. Jamais de lien sur les comptes 1 et 2 : ni en bio, ni en story, ni dans un Reel. Le lien ne vit que dans la bio du compte 3.\n"
                  "4. Chaque jour, une story sur les comptes 1 et 2 avec le widget vers ta story à la une.\n"
                  "5. `!mesclics` ici : ce lien compte tes visites, donc ta paie, tous les 15 jours.\n\n"
                  "Fini ? Appuie sur le bouton.")},
    7: {"titre": "🎉 Bravo, tu as fini · Ta routine de chaque jour", "fiche": "4", "bouton": "", "salons": [],
        "texte": ("Chaque jour, sur {croissance} : 2 Reels chacun, 1 story avec le widget vers ta story à la une, quelques commentaires. "
                  "Le compte 3 reste privé, avec ton lien en bio.\n\n"
                  "Chaque semaine, ajoute 1 Reel par jour sur chaque compte, jusqu'à 10. Le matin tu montes, tu mets en brouillon, tu publies dans la journée.\n\n"
                  "Tes visites : `!mesclics` ici, quand tu veux. Ta paie arrive ici les 5 et 20.\n\n"
                  "Tu connais quelqu'un de sérieux ? Tape `!parrain @lui` ici : 5 $ pour toi le jour de sa première paie.\n\n"
                  "Une question ? Écris ici.")},
}
# 28/09 : un compte rendu par un sortant existe déjà → on s'y connecte, pas d'inscription
# 01/10 (Gaëtan : « les codes Instagram se demandent uniquement dans #🔐-code-instagram ») : plus de « écris !code ici » ni
# de « il arrive ici tout seul », la phrase canonique {codes} ; « il a déjà chauffé » retiré (24 h de warm-up quand même).
# 08/10 (audit : l'identifiant déjà pris est le blocage le plus courant à la création ; Mohamed a créé une variante que le bot ne
# connaissait pas) : la consigne et la commande `!pseudo n identifiant`, qui met le classeur et la fiche à jour.
PSEUDO_PRIS = "Identifiant déjà pris ? Ajoute un chiffre à la fin. Puis tape ici : `!pseudo {n} ton_identifiant`."
CREATION = ("1. Instagram → Créer un compte → avec cet e-mail.\n"
            "2. {codes}\n"
            "3. Mets ce mot de passe. Numéro demandé ? Le tien. Date de naissance : la vraie.\n"
            "4. " + PSEUDO_PRIS.format(n=1),
            "Même chose que le compte 1, sur le même téléphone : tu ajoutes un compte, sans te déconnecter.\n"
            "⚠️ Instagram ne demande pas d'e-mail ? Arrête et écris-le ici.\n"
            "{codes}\n" + PSEUDO_PRIS.format(n=2),
            "Crée-le comme les autres, sur le même téléphone.\n"
            "{codes}\n" + PSEUDO_PRIS.format(n=3))
CONNEXION = ("Ce compte existe déjà.\n"
             "1. Instagram → Se connecter → cet identifiant et ce mot de passe.\n"
             "2. {codes}\n"
             "3. Numéro demandé ? Mets le tien. Ne change ni la photo ni la bio pour l'instant.",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter, sans te déconnecter du compte 1.\n{codes}",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter.\n{codes}")
RELANCE_JOURS = int(os.environ.get("PARCOURS_RELANCE_JOURS", "0") or 0)   # 05/10 (Gaëtan : « arrêter de polluer chaque salon privé ») : 0 = plus de relance ; 28/09 : 2
# 30/09 (Daniella) : « sur chaque compte… pas de Reel » contredisait l'étape 4 (comptes 1 et 2 publient déjà) — le warm-up du
# jour ne concerne que le compte 3.
# 01/10 (relecture) : « Comptes 1 et 2 » devient {autres}, les comptes vivants hors compte 3 (un compte BAN ne publie plus)
WARMUP_JOUR_TEXTE = ("🔥 **Warm-up du compte 3 : jour {j} sur {jours}.** Sur le compte 3 : 10 minutes de Reels, 5 likes, "
                     "2 abonnements, 1 story sans lien, pas de Reel. {autres} : 2 Reels et 1 story chacun, comme d'habitude.")


def configurer(deps: dict):
    global _deps
    _deps = deps


def _onb(uid) -> dict:
    """La fiche d'onboarding du clipper (comptes, accès, lien, Drive), {} sans elle."""
    try:
        return (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(str(uid), {}) or {})
    except Exception:                                                   # noqa: BLE001
        return {}


def _comptes_ordonnes(uid, onb=None) -> list:
    """01/10 (bug de l'ordre : la boucle du classeur triait la liste, et chaque fonction relisait les comptes à sa façon —
    « ouvre ton compte 1 » avec l'identifiant du compte 2) : l'ordre unique compte 1, 2, 3, pour tout le module. L'ordre des
    accès livrés (fiche « acces ») fait foi, puis celui de la liste ; croissance d'abord, un identifiant de type privé en 3."""
    onb = _onb(uid) if onb is None else onb
    handles = [h for h in (onb.get("comptes") or []) if h]
    acces = [a.get("handle") for a in (onb.get("acces") or []) if isinstance(a, dict) and a.get("handle") in handles]
    base = list(dict.fromkeys(acces + handles))
    prives = [h for h in base if onboarding._est_prive({"handle": h, "etat": ""})]
    croissance = [h for h in base if h not in prives]
    ordonnes = croissance[:2] + prives[:1]
    if len(ordonnes) < 3:
        ordonnes += [h for h in base if h not in ordonnes][:3 - len(ordonnes)]
    return ordonnes + [h for h in base if h not in ordonnes]


def _est_ban(h: str, fiche_p: dict = None, bans=()) -> bool:
    """01/10 : BAN d'après le dernier scan, la fiche (retenu au scan, survit aux redémarrages) ou le classeur lu à l'instant."""
    cle = str(h or "").lower()
    return bool(cle) and (_derniers_etats.get(cle) == "ban" or cle in {str(x).lower() for x in (fiche_p or {}).get("bans") or []}
                          or cle in {str(x).lower() for x in bans})


def _vivants(uid, fiche_p: dict = None, comptes=None, bans=()) -> list:
    """01/10 (Daniella : son compte 2 banni restait listé à l'étape 5 et le matin) : les comptes du clipper sans les BAN."""
    fiche_p = _lire().get(str(uid), {}) if fiche_p is None else fiche_p
    comptes = _comptes_ordonnes(uid) if comptes is None else comptes
    return [h for h in comptes if not _est_ban(h, fiche_p, bans)]


def _liste(handles: list) -> str:
    """« `a`, `b` et `c` »."""
    h = [f"`{x}`" for x in handles]
    return " et ".join([", ".join(h[:-1]), h[-1]]) if len(h) > 1 else (h[0] if h else "tes comptes")


def _date_creation(fiche_p: dict, i: int):
    """01/10 : le compte i est créé au premier signal (bouton « créé » ou scan, qui envoie son profil), sinon à la fermeture
    de son étape. Le warm-up et les 48 h se comptent de là, plus de l'heure du second appui."""
    for valeur in ((fiche_p.get("profils") or {}).get(str(i)), (fiche_p.get("dates") or {}).get(f"{i}_fait")):
        try:
            d = datetime.fromisoformat(str(valeur))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


def _cree(fiche_p: dict, i: int) -> bool:
    """01/10 (l'assistant disait « 2 comptes créés, compte 2 en warm-up » quand le bot avait seulement envoyé l'étape 2) : un
    compte n'est créé que si son étape est fermée (dates « i_fait »). Seule exception, un parcours repris d'après le classeur
    à une étape plus loin (jamais passé par l'étape 1) : ses comptes d'avant existent déjà."""
    dates = fiche_p.get("dates") or {}
    if dates.get(f"{i}_fait"):
        return True
    ancien = not dates.get("1") and not dates.get("1_fait")
    return ancien and i < int(fiche_p.get("etape", 0) or 0)


def _cumuler_reels(suivi: dict, n72: int, jour: str) -> dict:
    """01/10 : les Reels d'un compte vus par le scan, cumulés. Le scan ne donne que les Reels de ses trois derniers passages
    (reels_72h) : chaque jour, on ajoute ce que ce total a gagné depuis la veille (jamais plus que ce qui a été publié). Rejoué
    le même jour, le chiffre du jour est remplacé, pas ajouté."""
    suivi = dict(suivi or {})
    if suivi.get("jour") != jour:
        suivi = {"avant": int(suivi.get("vus", 0) or 0), "base": int(suivi.get("dernier", 0) or 0), "jour": jour}
    suivi["dernier"] = int(n72 or 0)
    suivi["vus"] = int(suivi.get("avant", 0)) + max(0, suivi["dernier"] - int(suivi.get("base", 0)))
    return suivi


def reels_vus(uid, fiche_p: dict, n: int) -> int:
    """Les Reels vus par le scan sur le compte n ; compte n BAN : sur tous ses comptes vivants déjà créés."""
    comptes = _comptes_ordonnes(uid)
    suivis = fiche_p.get("reels") or {}
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    if h and not _est_ban(h, fiche_p):
        return int((suivis.get(h.lower()) or {}).get("vus", 0) or 0)
    return sum(int((suivis.get(x.lower()) or {}).get("vus", 0) or 0) for i, x in enumerate(comptes[:3], start=1)
               if _cree(fiche_p, i) and not _est_ban(x, fiche_p))


def _ou_publier(uid, fiche_p: dict, n: int) -> str:
    comptes = _comptes_ordonnes(uid)
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    return f"ton compte {n}" if (not h or not _est_ban(h, fiche_p)) else "tes autres comptes"


def _bloque_ban(uid, fiche_p: dict, n: int) -> bool:
    """01/10 (relecture : compte 1 BAN à l'étape 2, aucun autre compte créé — reels_vus restait à 0 pour toujours et la ligne
    du matin disait « tes autres comptes ») : le compte n est BAN et le clipper n'a aucun compte vivant déjà créé. Le parcours
    attend : c'est Gaëtan qui décide (`!etape` ou remplacement), aucune règle n'est inventée ici."""
    comptes = _comptes_ordonnes(uid)
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    if not h or not _est_ban(h, fiche_p):
        return False
    return not any(_cree(fiche_p, i) and not _est_ban(x, fiche_p) for i, x in enumerate(comptes[:3], start=1))


def texte_bloque(n: int) -> str:
    """La ligne donnée au clipper bloqué par le BAN de son compte n (_bloque_ban)."""
    return f"Ton compte {n} est bloqué : fais appel sur Instagram (« Contester la décision »).\n\nL'équipe est prévenue."


def _migrer_essai(d: dict) -> bool:
    """01/10 : une fiche encore « en essai » (compte 1 seul, ancienne règle des 5 Reels en 72 h) passe sous la règle unique :
    l'étape 2 est programmée 48 h après la création du compte 1 et part quand 2 Reels y sont vus. Aucun message."""
    change = False
    for fiche_p in d.values():
        essai = fiche_p.get("essai") if isinstance(fiche_p, dict) else None
        if not essai:
            continue
        fiche_p.pop("essai", None)
        change = True
        if (isinstance(essai, dict) and essai.get("fini")) or int(fiche_p.get("etape", 0) or 0) != 2 or (fiche_p.get("dates") or {}).get("2"):
            continue
        programme = fiche_p.setdefault("programme", [])
        if any(x.get("type") == "etape" for x in programme):
            continue
        base = _date_creation(fiche_p, 1) or datetime.now(timezone.utc)
        programme.append({"quand": (base + timedelta(hours=ATTENTE_COMPTE_H)).isoformat(timespec="seconds"), "type": "etape", "n": 2})
    return change


async def _suite(salon, texte: str):
    """Le message de suivi du salon : il remplace le précédent (matin.remplacer), sinon un envoi simple."""
    if _deps.get("remplacer_suite"):
        return await _deps["remplacer_suite"](salon, texte)
    return await salon.send(texte)


def _lire() -> dict:
    return _deps["lire_json"](_deps["FICHIER_PARCOURS"], {})


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_PARCOURS"], d)


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").lower()


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ liens et contexte
def _url(guild, cid) -> str:
    return f"https://discord.com/channels/{guild.id}/{cid}"


def _salon_nom(guild, *mots):
    """Premier salon texte dont le nom normalisé contient tous les mots."""
    for c in guild.text_channels:
        n = _norm(c.name)
        if all(m in n for m in mots):
            return c
    return None


def _salon_info(guild, creatrice: str):
    """Le salon d'infos de la créatrice (ℹ️-sophie / i-sophie), sinon le premier salon de sa catégorie."""
    cat = _deps["categorie_de_creatrice"](guild, creatrice) if _deps.get("categorie_de_creatrice") else None
    if cat is None:
        return None
    for c in cat.text_channels:
        n = _norm(c.name)
        if "ℹ" in c.name or n.startswith("i-") or "info" in n:
            return c
    return cat.text_channels[0] if cat.text_channels else None


async def _contexte(guild, uid: str, fiche_p: dict) -> dict:
    """Les valeurs des gabarits : comptes (handle + e-mail, croissance d'abord, privé en 3), lien, Drive, salons."""
    ctx = {"prenom": fiche_p.get("prenom", ""), "creatrice": fiche_p.get("creatrice", ""),
           "jours": WARMUP_JOURS, "jour_suivant": WARMUP_JOURS + 1}
    onb = _onb(uid)
    handles = list(onb.get("comptes", []))
    mails, mdps, bans = {}, {}, set()
    try:
        if onboarding.actif() and handles:
            for c in await onboarding.lire_comptes():
                if c["handle"] in handles:
                    mails[c["handle"]] = c.get("mail", "")
                    mdps[c["handle"]] = c.get("mdp", "")                # 01/10 (Simon) : repli du mot de passe sur le classeur
                    if _norm(c.get("etat", "")) == "ban":
                        bans.add(c["handle"].lower())
    except Exception as erreur:
        journal.info("Classeur indisponible pour le parcours : %s", erreur)
    ordonnes = _comptes_ordonnes(uid, onb)                              # 01/10 : le même ordre partout
    acces = {a.get("handle"): a for a in (onb.get("acces") or []) if isinstance(a, dict)}   # 27/09 : mot de passe et e-mail par compte
    for i in range(3):
        h = ordonnes[i] if i < len(ordonnes) else "?"
        ctx[f"compte{i + 1}"] = h
        ctx[f"mail{i + 1}"] = acces.get(h, {}).get("mail") or mails.get(h, "(dans ton message de comptes plus haut)")
        ctx[f"mdp{i + 1}"] = acces.get(h, {}).get("mdp") or mdps.get(h) or "(demande-le à Gaëtan sur WhatsApp)"
    vivants = _vivants(uid, fiche_p, ordonnes[:3], bans)
    ctx["vivants"] = _liste(vivants)                                    # 01/10 : étapes 5 et 7 sans les comptes BAN
    ctx["autres"] = _liste([h for h in vivants if h != ctx["compte3"]])  # 01/10 (relecture) : étape 4, sans les BAN
    ctx["croissance"] = ctx["autres"]                                   # 05/10 : les comptes qui publient (le compte 3 est privé)
    ctx["codes"] = texte_codes()
    ctx["lien"] = onb.get("lien") or "(il arrive ici dès que ton compte 3 est prêt)"   # 05/10 : le lien est créé avec le compte 3
    ctx["drive"] = onb.get("drive") or "(pas encore prêt, je te le donne ici dès qu'il l'est)"
    creatrice = ctx["creatrice"]
    info = _salon_info(guild, creatrice) if guild is not None else None
    ctx["info"] = f"<#{info.id}>" if info is not None else f"le salon d'infos de {creatrice}"
    res = _salon_nom(guild, "ressources") if guild is not None else None
    ctx["ressources"] = f"<#{res.id}>" if res is not None else "#ressources"
    for i in range(3):                                                  # 28/09 : création, ou connexion à un compte rendu par un sortant
        a = acces.get(ctx[f"compte{i + 1}"], {})
        ctx[f"creation{i + 1}"] = (CONNEXION[i] if a.get("cree") else CREATION[i]).format(info=ctx["info"], codes=ctx["codes"])
    rep = _salon_nom(guild, "reporting") if guild is not None else None
    ctx["reporting"] = f"<#{rep.id}>" if rep is not None else "#reporting"
    ctx["lien_reporting"] = LIEN_REPORTING
    ctx["_info_id"] = info.id if info is not None else None
    ctx["_res_id"] = res.id if res is not None else None
    ctx["_rep_id"] = rep.id if rep is not None else None
    return ctx


class _Gabarit(dict):
    def __missing__(self, cle):
        return "…"


def _rendre(texte: str, ctx: dict) -> str:
    return texte.format_map(_Gabarit(ctx))


# ------------------------------------------------------------------ boutons
class BoutonEtape(discord.ui.DynamicItem[discord.ui.Button], template=r"parcours:(?P<uid>[0-9]+):(?P<etape>[0-9]+)"):
    """« ✅ C'est fait » : persistant (custom_id), donc il survit aux redémarrages du bot."""

    def __init__(self, uid: str, etape: int, label: str = "✅ C'est fait"):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.success,
                                           custom_id=f"parcours:{uid}:{etape}"))
        self.uid, self.etape = str(uid), int(etape)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["uid"], int(match["etape"]), item.label or "✅ C'est fait")

    async def callback(self, interaction: discord.Interaction):
        staff = _deps.get("est_staff")
        if str(interaction.user.id) != self.uid and not (staff and staff(interaction.user)):
            await interaction.response.send_message("Ce bouton est pour le clipper de ce salon 🙂", ephemeral=True)
            return
        await interaction.response.defer()
        if not await valider_etape(interaction.channel, self.uid, self.etape, par=str(interaction.user.id)):
            # 01/10 (Steeve : un vieux bouton du compte 2 a rouvert le compte 2 pendant l'attente) : refusé, et on le dit
            try:
                await interaction.followup.send("Ce bouton n'est plus valable. Suis le dernier message de ton salon 🙂", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass


def _vue(guild, uid: str, n: int, ctx: dict):
    vue = discord.ui.View(timeout=None)
    e = ETAPES[n]
    posts = _deps.get("POSTS_FORMATION") or {}
    if e.get("fiche") and posts.get(e["fiche"]) and guild is not None:
        vue.add_item(discord.ui.Button(label=f"📄 Fiche {e['fiche']}", style=discord.ButtonStyle.link,
                                       url=_url(guild, posts[e["fiche"]])))
    for s in e.get("salons", []):
        cid = ctx.get({"info": "_info_id", "ressources": "_res_id", "reporting": "_rep_id"}[s])
        if cid and guild is not None:
            libelle = {"info": f"ℹ️ Infos {ctx.get('creatrice', '')}", "ressources": "💡 Ressources", "reporting": "📊 Reporting"}[s]
            vue.add_item(discord.ui.Button(label=libelle[:80], style=discord.ButtonStyle.link, url=_url(guild, cid)))
    if e.get("bouton"):
        vue.add_item(BoutonEtape(uid, n, _rendre(e["bouton"], ctx)))
    if _deps.get("whatsapp"):                                            # 26/09 (Gaëtan) : « un bouton, envoyer un message à Gaëtan »
        vue.add_item(discord.ui.Button(label="💬 Écrire à Gaëtan (WhatsApp)", style=discord.ButtonStyle.link, url=_deps["whatsapp"]))
    return vue


# ------------------------------------------------------------------ déroulé
async def envoyer_etape(salon, membre, n: int) -> None:
    uid = str(membre.id)
    if n in (3, 6) and _deps.get("attribuer_lien"):
        # 05/10 (Gaëtan : « le lien que pour le troisième compte ») : le lien GAML n'existe pas avant le compte 3 ; il est créé
        # (ou repris) à l'ouverture de l'étape 3, pour être dans la bio du compte 3 dès son profil, puis donné à l'étape 6.
        try:
            await _deps["attribuer_lien"](membre)
        except Exception as erreur:                                     # noqa: BLE001 — sans lien, l'étape part quand même
            journal.warning("Lien GAML pour %s à l'étape %s : %s", uid, n, erreur)
    # 01/10 (relecture : deux programme_du_jour à 50 ms d'écart, le clipper 2 a reçu deux fois « Étape 2 ») : la fiche était
    # lue, puis réécrite après l'appel au classeur (_contexte) et l'envoi — elle écrasait ce qui avait été écrit entre-temps.
    # Le contexte d'abord ; la fiche relue après l'attente, posée et écrite sans attente ; relue encore pour l'id du message.
    ctx = await _contexte(getattr(salon, "guild", None), uid, _lire().get(uid) or {"prenom": _prenom(membre)})
    d = _lire()
    fiche_p = d.setdefault(uid, {"prenom": _prenom(membre),
                                 "creatrice": "", "salon_id": str(salon.id), "etape": n, "dates": {}, "notes": []})
    fiche_p["etape"] = n
    fiche_p["salon_id"] = str(salon.id)
    fiche_p.setdefault("dates", {})[str(n)] = _maintenant()
    _ecrire(d)
    e = ETAPES[n]
    texte = f"{membre.mention} **{_rendre(e['titre'], ctx)}**\n\n{_rendre(e['texte'], ctx)}"
    if n == 5:                                                          # 01/10 : il publie sur ses comptes, la relecture est proposée
        texte += _ligne_review(uid)
    try:
        msg = await salon.send(texte[:1990], view=_vue(getattr(salon, "guild", None), uid, n, ctx))
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Étape %s pour %s : %s", n, uid, erreur)
        return
    d = _lire()
    if uid in d:
        d[uid].setdefault("messages", {})[str(n)] = str(msg.id)
        _ecrire(d)


async def demarrer_parcours(salon, membre, creatrice: str) -> None:
    """Après la livraison des comptes : étape 1. Rejoué sur un clipper déjà en route : on ne repart pas de zéro."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.get(uid)
    if fiche_p and fiche_p.get("etape", 0) >= 1 and fiche_p.get("creatrice") == creatrice:
        return
    d[uid] = {"prenom": _prenom(membre),
              "creatrice": creatrice, "salon_id": str(salon.id), "etape": 0, "dates": {}, "notes": (fiche_p or {}).get("notes", [])}
    _ecrire(d)
    await envoyer_etape(salon, membre, 1)


def mal_partis(fiches: dict, valides: set) -> list:
    """30/09 (Steeve) : les nouveaux (test validé) partis à l'étape 2 ou 3 sans jamais avoir eu l'étape 1 — [uid]."""
    out = []
    for uid, f in fiches.items():
        dates = f.get("dates") or {}
        if uid in valides and int(f.get("etape", 0)) in (2, 3) and not dates.get("1") and not dates.get("1_fait"):
            out.append(uid)
    return out


async def reprendre_au_compte_1(salon, membre, creatrice: str) -> None:
    """Remet un nouveau parti trop loin à l'étape 1 (calendrier, profils et programme effacés, notes gardées), avec une ligne
    d'excuse, puis l'étape 1."""
    for mid in list(((_lire().get(str(membre.id)) or {}).get("messages") or {}).values()):
        await _retirer_bouton(salon, mid)                               # 01/10 (Steeve) : plus de bouton fantôme des étapes effacées
    d = _lire()
    f = d.get(str(membre.id)) or {}
    for cle in ("dates", "messages", "profils", "programme", "essai", "reconcilie", "corrige_4", "warmup_jour"):
        f.pop(cle, None)
    f["etape"] = 0
    d[str(membre.id)] = f
    _ecrire(d)
    try:
        await salon.send(f"{membre.mention} Petite erreur de ma part : on reprend dans l'ordre. Oublie le compte 2, commence par ton compte 1 👇")
    except (discord.Forbidden, discord.HTTPException):
        pass
    await forcer_etape(salon, membre, creatrice or f.get("creatrice", ""), 1)


async def demarrer_routine(salon, membre, creatrice: str) -> None:
    """Clipper déjà en place (comptes créés avant le bot) : le parcours démarre directement à la routine (étape 7),
    sans repasser par la création des comptes. Rejoué : rien."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.get(uid)
    if fiche_p and fiche_p.get("etape", 0) >= 7:
        return
    d[uid] = {"prenom": _prenom(membre),
              "creatrice": creatrice, "salon_id": str(salon.id), "etape": 7, "dates": {"7": _maintenant()},
              "notes": (fiche_p or {}).get("notes", [])}
    _ecrire(d)
    ctx = await _contexte(getattr(salon, "guild", None), uid, d[uid])
    e = ETAPES[7]
    try:
        await salon.send((f"{membre.mention} **{_rendre(e['titre'], ctx)}**\n\n{_rendre(e['texte'], ctx)}")[:1990],
                         view=_vue(getattr(salon, "guild", None), uid, 7, ctx))
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Routine pour %s : %s", uid, erreur)


async def valider_etape(salon, uid: str, n: int, par: str = "") -> bool:
    """Le bouton (ou le manager) ferme l'étape n et ouvre la suivante. Idempotent : un double clic ne saute rien."""
    d = _lire()
    fiche_p = d.get(str(uid))
    if not fiche_p or int(fiche_p.get("etape", 0)) != int(n):
        return False
    if not (fiche_p.get("dates") or {}).get(str(n)):
        # 01/10 (Steeve, Ricardo) : une étape pas encore ouverte (le compte suivant attend ses 48 h et ses Reels) ne se ferme
        # pas — ni par un vieux bouton, ni par le scan qui voit le compte (identifiant pris par un tiers, liste dans le désordre)
        return False
    # 30/09 : compte créé → d'abord son profil (photo, nom, bio en UN message, bouton « profil fait »), rien d'autre ; le
    # deuxième appui (ou le scan qui voit le compte) ferme l'étape. Un compte rendu par un sortant garde son profil.
    if n in (1, 2, 3) and not (fiche_p.get("profils") or {}).get(str(n)) and _deps.get("profil_envoyer") \
            and str((fiche_p.get("dates") or {}).get(str(n)) or "9") >= DISTILLE_DEPUIS:
        ctx = await _contexte(getattr(salon, "guild", None), str(uid), fiche_p)
        # 01/10 (relecture) : relue après l'appel au classeur — l'ancienne copie écrasait ce qui avait été écrit pendant
        # l'attente ; un double appui arrivé entre-temps a déjà envoyé le profil
        d = _lire()
        fiche_p = d.get(str(uid))
        if not fiche_p or int(fiche_p.get("etape", 0)) != int(n) or not (fiche_p.get("dates") or {}).get(str(n)):
            return False
        if (fiche_p.get("profils") or {}).get(str(n)):
            return True
        if not str(ctx.get(f"creation{n}", "")).startswith("Ce compte existe déjà"):
            fiche_p.setdefault("profils", {})[str(n)] = _maintenant()
            _ecrire(d)
            await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get(str(n)))
            vue = discord.ui.View(timeout=None)
            vue.add_item(BoutonEtape(uid, n, "✅ Profil fait"))
            try:
                msg = await _deps["profil_envoyer"](salon, uid, n, fiche_p.get("creatrice", ""), vue=vue,
                                                    **({"lien": _onb(uid).get("lien", "")} if n == 3 else {}))   # 05/10 : le lien dans la bio du compte 3
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Profil du compte %s pour %s : %s", n, uid, erreur)
                msg = None
            if msg is not None:
                d = _lire()
                d[str(uid)].setdefault("messages", {})[f"{n}p"] = str(getattr(msg, "id", ""))
                _ecrire(d)
                return True
            d = _lire()
            fiche_p = d.get(str(uid))                                   # profil impossible : on ferme l'étape quand même
            if not fiche_p or int(fiche_p.get("etape", 0)) != int(n):   # 01/10 (relecture) : fermée entre-temps
                return False
    fiche_p.setdefault("dates", {})[f"{n}_fait"] = _maintenant()
    fiche_p["etape"] = n + 1
    _ecrire(d)
    if _deps.get("activite") and par != "bot":                          # 05/10 : un bouton d'étape = une réponse à l'appel de présence
        # (08/10 : une étape fermée par le bot lui-même — warm-up fini, profil oublié — n'est pas une réponse du clipper)
        try:
            _deps["activite"](str(uid))
        except Exception:                                               # noqa: BLE001
            pass
    for cle in (str(n), f"{n}p"):
        await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get(cle))
    await _classeur_etat(uid, n)
    membre = _deps["membre_par_id"](uid)
    if membre is None:
        return True
    if _deps.get("effacer_suite"):                                      # 30/09 (GO n° 4) : l'ancien « prochaine étape » s'en va
        try:
            await _deps["effacer_suite"](salon)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Message de suivi de %s : %s", uid, erreur)
    maintenant = datetime.now(timezone.utc)
    if n in (1, 2):
        # 30/09 : règle des 48 h tenue par le bot ; 01/10 : la même pour tous, comptée depuis la création du compte (premier
        # signal), et l'étape suivante n'est envoyée qu'avec REELS_OUVERTURE Reels vus sur ce compte (programme_du_jour)
        base = min(_date_creation(fiche_p, n) or maintenant, maintenant)
        publier = {"quand": (base + timedelta(hours=WARMUP_H)).isoformat(timespec="seconds"), "type": "publier", "n": n}
        etape = {"quand": (base + timedelta(hours=ATTENTE_COMPTE_H)).isoformat(timespec="seconds"), "type": "etape", "n": n + 1}
        deja_chaud = _echu(publier, maintenant)                         # compte créé il y a plus de 24 h : il publie tout de suite
        d = _lire()
        d[str(uid)]["programme"] = [etape] if deja_chaud else [publier, etape]
        _ecrire(d)
        if deja_chaud:
            await _envoyer_publier(salon, membre, uid, n)
        else:
            await _suite(salon, f"{membre.mention} " + TEXTE_WARMUP.format(n=n, regle=regle_comptes()))
        return True
    if n == 3:                                                          # 05/10 : compte 3 privé → le lien, pas de warm-up ni d'étapes 4-5
        d = _lire()
        if str(uid) in d:
            d[str(uid)]["etape"] = 6
            _ecrire(d)
        await envoyer_etape(salon, membre, 6)
        try:                                                            # 08/10 : les 3 comptes sont créés → son app et son lien
            await livrer_app(str(uid), salon=salon, membre=membre)
        except Exception as erreur:                                     # noqa: BLE001 — la passe horaire réessaiera
            journal.warning("App clippers pour %s : %s", uid, erreur)
        return True
    if n + 1 in ETAPES:
        await envoyer_etape(salon, membre, n + 1)
    return True


async def _retirer_bouton(salon, mid) -> None:
    if not mid or not str(mid).isdigit():
        return
    try:
        ancien = await salon.fetch_message(int(mid))
        await ancien.edit(view=None)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        pass


def _etape_attendue(fiche_p: dict, item: dict) -> bool:
    """L'élément « etape n » vaut encore : le parcours attend bien ce compte (étape n, pas encore envoyée)."""
    n = int(item.get("n") or 0)
    return int(fiche_p.get("etape", 0) or 0) == n and not (fiche_p.get("dates") or {}).get(str(n))


async def _envoyer_publier(salon, membre, uid: str, n: int) -> None:
    """« Ton compte n peut publier », avec le Drive ; 01/10 : et ce qui ouvre le compte suivant, s'il attend encore."""
    if n not in TEXTE_PUBLIER:
        return
    fiche_p = _lire().get(str(uid), {})
    ctx = await _contexte(getattr(salon, "guild", None), str(uid), fiche_p)
    texte = TEXTE_PUBLIER[n].format(rythme="2 Reels par jour dessus.", drive=ctx.get("drive", "ton Drive"))
    a = attente(fiche_p)
    # 01/10 (relecture) : les deux conditions de la règle, plus seulement les Reels ; compte n BAN : « sur tes autres
    # comptes » ; BAN sans aucun compte vivant : rien ici, l'équipe est prévenue (_signaler_bloques)
    if a and a[0] == n + 1 and reels_vus(uid, fiche_p, n) < REELS_OUVERTURE and not _bloque_ban(uid, fiche_p, n):
        ou = _ou_publier(uid, fiche_p, n)
        texte += (f"\n\nTon compte {n + 1} arrive tout seul ici, au plus tôt {ATTENTE_COMPTE_H} h après ton compte {n}, "
                  + (f"dès que {REELS_OUVERTURE} Reels sont publiés dessus." if ou == f"ton compte {n}" else
                     f"dès que {REELS_OUVERTURE} Reels sont publiés sur {ou}."))
    texte += _ligne_review(uid)
    vue = None
    if n == 1 and _deps.get("whatsapp"):
        # 05/10 (Gaëtan : « oblige les gens à me contacter sur WhatsApp une fois qu'il a créé le premier IG ») : pas bloquant,
        # mais demandé ici, une fois, avec le message déjà écrit ; `!wa @clipper` (staff) note que c'est fait.
        texte += (f"\n\n📲 **Maintenant, écris à Gaëtan sur WhatsApp** (bouton ci-dessous, {consigne_whatsapp(uid, fiche_p)}) : "
                  "il ouvre ton groupe avec Jonas. C'est là que tu poses tes questions.\n\nFait ? Appuie sur « ✅ J'ai écrit à Gaëtan ».")
        vue = discord.ui.View(timeout=None)
        vue.add_item(discord.ui.Button(label="📲 Écrire à Gaëtan sur WhatsApp", style=discord.ButtonStyle.link,
                                       url=lien_whatsapp_prerempli(uid, fiche_p)))
        vue.add_item(BoutonWhatsApp(uid))                              # 08/10 : il se déclare lui-même
    await salon.send(f"{membre.mention} " + texte, view=vue) if vue is not None else await salon.send(f"{membre.mention} " + texte)


# 08/10 (Mathieu : « ça me redirige vers WhatsApp mais il demande d'envoyer le message à un contact dans mon téléphone ») : le
# lien de Gaëtan est un lien court WhatsApp Business (wa.me/message/…), qui ne prend pas de texte ; le « ?text= » ajouté le
# cassait (WhatsApp ouvrait le choix d'un contact). Le texte n'est ajouté qu'à un lien wa.me/<numéro> — ou au numéro de
# WHATSAPP_GAETAN_NUMERO s'il est posé dans Railway (jamais dans le dépôt) ; sinon le lien court part tel quel et le message à
# envoyer est écrit dans Discord, à copier.
WHATSAPP_NUMERO = re.sub(r"\D", "", os.environ.get("WHATSAPP_GAETAN_NUMERO", ""))


def _message_wa(uid, fiche_p: dict = None) -> str:
    fiche_p = _lire().get(str(uid), {}) if fiche_p is None else fiche_p
    return f"Bonjour Gaëtan, je suis {fiche_p.get('prenom') or 'un clipper'}, clipper de {fiche_p.get('creatrice') or '?'}."


def whatsapp_prerempli() -> bool:
    """Le bouton WhatsApp peut-il porter le message déjà écrit ? Seulement vers un numéro (wa.me/<numéro>)."""
    base = str(_deps.get("whatsapp") or "").split("?")[0]
    return bool(WHATSAPP_NUMERO) or bool(re.search(r"wa\.me/\+?\d{6,}/?$", base))


def lien_whatsapp_prerempli(uid, fiche_p: dict = None) -> str:
    """05/10 : le wa.me de Gaëtan avec le message du clipper déjà écrit (prénom, créatrice) quand c'est possible ; sinon le lien
    court WhatsApp Business tel quel (08/10)."""
    from urllib.parse import quote
    brut = str(_deps.get("whatsapp") or "")
    base = f"https://wa.me/{WHATSAPP_NUMERO}" if WHATSAPP_NUMERO else brut.split("?")[0]
    if not base:
        return ""
    if not whatsapp_prerempli():
        return brut
    return f"{base.rstrip('/')}?text=" + quote(_message_wa(uid, fiche_p))


def consigne_whatsapp(uid, fiche_p: dict = None) -> str:
    """Ce qui accompagne le bouton : « le message est déjà écrit » seulement si c'est vrai, sinon le message à lui envoyer."""
    if whatsapp_prerempli():
        return "le message est déjà écrit"
    return f"envoie-lui : « {_message_wa(uid, fiche_p)} »"


def marquer_whatsapp(uid: str, par: str = "staff", annuler: bool = False) -> bool:
    """05/10 : `!wa @clipper` (staff) : le clipper a écrit sur WhatsApp, son groupe est ouvert. 08/10 : aussi le bouton du clipper
    (par="clipper", déclaratif) et `!wa @clipper non` (annuler). Renvoie False sans fiche."""
    d = _lire()
    if str(uid) not in d:
        return False
    if annuler:
        d[str(uid)].pop("whatsapp", None)
        d[str(uid)].pop("whatsapp_par", None)
    else:
        d[str(uid)]["whatsapp"] = _maintenant()
        d[str(uid)]["whatsapp_par"] = par
    _ecrire(d)
    return True


class BoutonWhatsApp(discord.ui.DynamicItem[discord.ui.Button], template=r"wa:(?P<uid>[0-9]+)"):
    """08/10 (audit : Simon répond « Déjà fait » et reste « pas de WhatsApp » ; chaque confirmation attendait un `!wa` de Gaëtan) :
    « ✅ J'ai écrit à Gaëtan », sous chaque demande de WhatsApp. Le clipper se déclare lui-même, Gaëtan est prévenu au salon admin
    et annule d'un `!wa @clipper non` si ce n'est pas vrai. Persistant (custom_id), comme les boutons d'étape."""

    def __init__(self, uid: str):
        super().__init__(discord.ui.Button(label="✅ J'ai écrit à Gaëtan", style=discord.ButtonStyle.success, custom_id=f"wa:{uid}"))
        self.uid = str(uid)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["uid"])

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("Ce bouton est pour le clipper de ce salon 🙂", ephemeral=True)
            return
        deja = (_lire().get(self.uid) or {}).get("whatsapp")
        if not marquer_whatsapp(self.uid, par="clipper"):
            await interaction.response.send_message("Ton parcours n'a pas encore commencé.", ephemeral=True)
            return
        await interaction.response.send_message("📲 Merci, c'est noté. Gaëtan te répond sur WhatsApp.", ephemeral=True)
        if _deps.get("activite"):
            try:
                _deps["activite"](self.uid)                             # un appui du clipper = une réponse à l'appel
            except Exception:                                           # noqa: BLE001
                pass
        if not deja:
            try:
                canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
                if canal is not None:
                    prenom = (_lire().get(self.uid) or {}).get("prenom") or self.uid
                    await canal.send(f"📲 {prenom} (<@{self.uid}>) dit avoir écrit sur WhatsApp. Pas vrai ? `!wa @{prenom} non`.")
            except Exception:                                           # noqa: BLE001
                pass


# ------------------------------------------------------------------ app clippers
# 08/10 (Gaëtan : « envoie automatiquement l'app dans le salon Discord privé du clippeur, une fois seulement qu'il a créé les
# 3 IG : l'app + son lien de tracking GAML ») : dès que l'étape du compte 3 est fermée (étape 6 ou plus : compte 3 créé, ou
# parcours repris plus loin par le staff), un message dans son salon perso avec le bouton de son app et son lien GAML. Une
# seule fois (« app » dans la fiche, écrite avant l'envoi) ; si l'app ne le connaît pas encore, la passe horaire réessaie et
# le salon admin est prévenu une fois par jour. Le lien de l'app vient de l'app elle-même (lien_app.py), jamais deviné.
TEXTE_APP = ("📱 {mention} **Ton app clipper est prête.**\n\n"
             "Dedans : tes vidéos à publier, tes visites, ta paie.\n\n"
             "1. Appuie sur « 📱 Ouvrir mon app ».\n"
             "2. Ouvre-la dans Safari (iPhone) ou Chrome (Android).\n"
             "3. Mets-la sur ton écran d'accueil. L'app te montre comment.\n\n"
             "Ton app : <{app}>\n\n"
             "🔗 **Ton lien** : {lien}\n"
             "Il va seulement dans la bio de ton compte 3.\n\n"
             "🔒 Ton app est à toi. Ne donne son lien à personne.")
APP_PAR_PASSE = 5                                                       # rattrapage : 5 messages au plus par passe horaire


def trois_comptes(fiche_p: dict) -> bool:
    """Ses 3 comptes sont créés : l'étape du compte 3 est fermée (étape 6, le lien, ou 7, la routine)."""
    return int((fiche_p or {}).get("etape", 0) or 0) >= 6


def _liens_gaml(uid: str, creatrice: str) -> tuple:
    """(le lien à lui donner, tous ses liens) : ses liens GAML de la paie au clic (adresse à jour, comme `!mesclics`), le plus
    récent de sa créatrice d'abord ; repli sur le lien de sa fiche d'onboarding."""
    infos = []
    try:
        d = paie_clics._lire()
        infos = [d["liens"][l] for l in paie_clics.liens_de(d, uid)
                 if d["liens"][l].get("url") and not d["liens"][l].get("supprime_gaml")]
    except Exception as erreur:                                         # noqa: BLE001
        journal.info("Liens GAML de %s illisibles : %s", uid, erreur)
    cle = (_norm(creatrice).split() or [""])[0]
    siens = sorted([i for i in infos if (_norm(i.get("creatrice") or "").split() or [""])[0] == cle],
                   key=lambda i: str(i.get("depuis") or ""), reverse=True)
    onb = str(_onb(uid).get("lien") or "")
    tous = [str(i["url"]) for i in siens + infos] + ([onb] if onb else [])
    return (tous[0] if tous else ""), list(dict.fromkeys(tous))


async def livrer_app(uid: str, salon=None, membre=None, client=None, forcer: bool = False) -> str:
    """Envoie dans son salon perso le bouton de son app et son lien GAML, une seule fois (forcer : staff ou `!app`, renvoyé
    même si déjà envoyé). Renvoie « envoye », « deja », « pas_pret », « exclu », « sans_lien », « sans_app » ou « erreur »."""
    uid = str(uid)
    fiche_p = _lire().get(uid) or {}
    if not forcer:
        if fiche_p.get("app"):
            return "deja"
        if not trois_comptes(fiche_p):
            return "pas_pret"
        if _deps.get("FICHIER_EQUIPES") and uid not in _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}):
            return "pas_pret"                                           # sorti de l'équipe (sa fiche reste au parcours)
    prenom = fiche_p.get("prenom") or (_prenom(membre) if membre is not None else "")
    if _norm(prenom) in paie_clics.CLICS_EXCLURE:                       # Rianah, le staff : pas d'app au clic
        return "exclu"
    if salon is None and client is not None:
        salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
    membre = membre if membre is not None else _deps["membre_par_id"](uid)
    if salon is None or membre is None:
        return "pas_pret"
    lien_gaml, tous = _liens_gaml(uid, fiche_p.get("creatrice", ""))
    if not lien_gaml:
        return "sans_lien"
    url = await lien_app.lien(tous)
    if not url:
        return "sans_app"
    d = _lire()                                                         # écrit AVANT l'envoi : jamais deux fois
    if uid in d:
        if d[uid].get("app") and not forcer:
            return "deja"
        d[uid]["app"] = _maintenant()
        d[uid].pop("app_alerte", None)
        _ecrire(d)
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="📱 Ouvrir mon app", style=discord.ButtonStyle.link, url=url))
    try:
        await salon.send(TEXTE_APP.format(mention=membre.mention, app=url, lien=lien_gaml)[:1990], view=vue)
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("App pour %s : %s", uid, erreur)
        if not forcer:
            d = _lire()
            if uid in d:
                d[uid].pop("app", None)
                _ecrire(d)
        return "erreur"
    journal.info("App clippers envoyée à %s", uid)
    return "envoye"


PROFIL_AUTO_H = int(os.environ.get("PARCOURS_PROFIL_AUTO_H", "6") or 6)


async def fermer_profils_oublies(client, maintenant=None) -> list:
    """08/10 (audit : « oublier Profil fait fige le parcours sans un mot ») : le compte est créé (premier appui ou scan, profil
    envoyé) mais « ✅ Profil fait » n'a jamais été pressé. Au bout de PROFIL_AUTO_H heures, l'étape se ferme comme si le clipper
    avait appuyé : rien n'est retardé, le warm-up et les 48 h comptent déjà depuis la création. Renvoie [(uid, n)] fermés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    faits = []
    for uid, fiche_p in list(_lire().items()):
        if not isinstance(fiche_p, dict):
            continue
        n = int(fiche_p.get("etape", 0) or 0)
        dates = fiche_p.get("dates") or {}
        if n not in (1, 2, 3) or dates.get(f"{n}_fait") or not dates.get(str(n)):
            continue
        try:
            quand = datetime.fromisoformat(str((fiche_p.get("profils") or {}).get(str(n))))
        except (TypeError, ValueError):
            continue                                                    # pas encore créé : rien à fermer
        quand = quand if quand.tzinfo else quand.replace(tzinfo=timezone.utc)
        if maintenant - quand < timedelta(hours=PROFIL_AUTO_H):
            continue
        salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0)) if client is not None else None
        if salon is None:
            continue
        try:
            if await valider_etape(salon, uid, n, par="bot"):
                faits.append((uid, n))
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Profil oublié de %s (compte %s) : %s", uid, n, erreur)
    return faits


async def rattraper_app(client) -> list:
    """Passe horaire : chaque clipper aux 3 comptes créés qui n'a pas encore son app la reçoit (APP_PAR_PASSE au plus). Ceux que
    l'app ne connaît pas encore : une ligne au salon admin, une fois par jour et par clipper. Renvoie les lignes de bilan."""
    if not lien_app.actif():
        return []
    envoyes, manquants = 0, []
    jour = datetime.now(timezone.utc).date().isoformat()
    for uid, fiche_p in list(_lire().items()):
        if envoyes >= APP_PAR_PASSE:
            break
        if not isinstance(fiche_p, dict) or fiche_p.get("app") or not trois_comptes(fiche_p):
            continue
        etat = await livrer_app(uid, client=client)
        if etat == "envoye":
            envoyes += 1
        elif (etat == "sans_lien" or (etat == "sans_app" and lien_app.onglet_rempli())) and fiche_p.get("app_alerte") != jour:
            d = _lire()
            if uid in d:
                d[uid]["app_alerte"] = jour
                _ecrire(d)
            manquants.append(f"{fiche_p.get('prenom') or uid}" + (" (aucun lien GAML)" if etat == "sans_lien" else ""))
    bilan = []
    if manquants:
        bilan.append("📱 App clippers pas encore envoyée, l'app ne connaît pas leur lien GAML (note « Clipping Prénom » ?) : "
                     + ", ".join(manquants))
    if envoyes:
        bilan.append(f"📱 App clippers envoyée à {envoyes} clipper(s) aux 3 comptes créés")
    return bilan


def _ligne_review(uid) -> str:
    """01/10 (Gaëtan, review des Reels) : « Avant de publier, envoie-moi ta vidéo ici… », pour ses 5 premiers Reels
    (review_reels.ligne_proposition, branchée par bot_discord). Sans elle, rien."""
    try:
        ligne = _deps["ligne_review"](uid) if _deps.get("ligne_review") else ""
    except Exception as erreur:                                         # noqa: BLE001 — une ligne en moins, jamais une étape en moins
        journal.warning("Ligne de review : %s", type(erreur).__name__)
        ligne = ""
    return f"\n\n{ligne}" if ligne else ""


async def programme_du_jour(client, maintenant=None) -> list:
    """30/09 : les messages programmés qui arrivent à échéance — « ton compte n peut publier » (24 h après sa création) et
    l'étape du compte suivant (48 h après). 01/10 : l'étape du compte suivant ne part qu'avec REELS_OUVERTURE Reels vus par le
    scan sur le compte d'avant ; sinon elle reste au programme, sans message, et part au passage (heure ou scan) qui la voit
    remplie. Chaque élément qui part est retiré de la fiche AVANT l'envoi (jamais deux fois) ; un salon ou un membre
    introuvable le garde pour le passage suivant. Renvoie [(uid, type, n)] envoyés.
    01/10 (relecture) : un seul passage à la fois (la boucle horaire et la fin du scan se chevauchaient), et le clipper
    bloqué par un BAN sans aucun compte vivant (_bloque_ban) est signalé une fois au salon admin."""
    async with _verrou_programme():
        return await _programme_du_jour(client, maintenant)


_verrou_prog = (None, None)


def _verrou_programme():
    """Le verrou de programme_du_jour, créé dans la boucle asyncio qui tourne (même modèle que codes_2fa._verrou)."""
    global _verrou_prog
    boucle_a = asyncio.get_running_loop()
    if _verrou_prog[0] is not boucle_a:
        _verrou_prog = (boucle_a, asyncio.Lock())
    return _verrou_prog[1]


async def _signaler_bloques(d0: dict) -> None:
    """01/10 (relecture) : le compte qui ouvre le suivant est BAN et aucun compte vivant n'est créé — le parcours attend
    sans fin. Une ligne au salon admin, une fois par compte banni (clé « alerte_ban » de la fiche). Gaëtan décide."""
    for uid, fiche_p in list(d0.items()):
        a = attente(fiche_p) if isinstance(fiche_p, dict) else None
        if not a or not _bloque_ban(uid, fiche_p, a[0] - 1):
            continue
        cle = str(a[0] - 1)
        if fiche_p.get("alerte_ban") == cle:
            continue
        d = _lire()                                                     # écrit AVANT l'envoi : jamais deux alertes
        if uid not in d:
            continue
        d[uid]["alerte_ban"] = cle
        _ecrire(d)
        canal = None
        try:
            canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
            if canal is not None:
                await canal.send(f"⛔ **{fiche_p.get('prenom') or uid}** (<@{uid}>) bloqué : compte {a[0] - 1} BAN, aucun compte "
                                 f"vivant, parcours en attente. Tu décides : `!etape @{fiche_p.get('prenom') or uid} {a[0]}` pour "
                                 "ouvrir le suivant, ou un remplacement.")
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Alerte BAN de %s : %s", uid, erreur)
        if canal is None:                                               # pas prévenu : on retentera au passage suivant
            d = _lire()
            if uid in d and d[uid].get("alerte_ban") == cle:
                d[uid].pop("alerte_ban", None)
                _ecrire(d)


async def _programme_du_jour(client, maintenant=None) -> list:
    maintenant = maintenant or datetime.now(timezone.utc)
    faits = []
    d0 = _lire()
    if _migrer_essai(d0):                                               # 01/10 : fin de la période d'essai, sans message
        _ecrire(d0)
    try:
        await _signaler_bloques(d0)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Clippers bloqués par un BAN : %s", erreur)
    for uid, fiche_p in list(d0.items()):
        if not any(_echu(x, maintenant) for x in fiche_p.get("programme") or []):
            continue
        salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
        membre = _deps["membre_par_id"](uid)
        if salon is None or membre is None:
            continue
        d = _lire()                                                     # relu et réécrit sans attente entre les deux : le passage
        fiche_p = d.get(uid) or {}                                      # de l'heure et celui du scan n'envoient jamais deux fois
        programme = fiche_p.get("programme") or []
        partants, gardes, dites = [], [], []
        for x in programme:
            if not _echu(x, maintenant):
                gardes.append(x)
            elif x.get("type") != "etape":
                partants.append(x)
            elif not _etape_attendue(fiche_p, x):
                continue                                                # déjà envoyée (`!etape` du staff) : retirée, sans message
            elif reels_vus(uid, fiche_p, int(x.get("n") or 0) - 1) >= REELS_OUVERTURE:
                partants.append(x)
            else:
                gardes.append(x)                                        # 48 h passées, Reels pas encore là : on attend
                n_x = int(x.get("n") or 0)
                if fiche_p.get("attente_dite") != n_x:                   # 08/10 (audit) : une fois, il sait ce qui manque
                    fiche_p["attente_dite"] = n_x
                    dites.append((n_x, reels_vus(uid, fiche_p, n_x - 1)))
        if gardes == programme and not dites:
            continue
        fiche_p["programme"] = gardes
        _ecrire(d)
        for n_x, vus in dites:                                          # 08/10 : « je vois N Reels », une fois par compte attendu
            try:
                await _suite(salon, f"{membre.mention} Ton compte {n_x} arrive dès que je vois {REELS_OUVERTURE} Reels sur ton "
                                    f"compte {n_x - 1}. Pour l'instant, j'en vois {vus}.\n\nTu publies sous un autre identifiant ? "
                                    f"Tape `!pseudo {n_x - 1} ton_identifiant`.")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Attente du compte %s de %s : %s", n_x, uid, erreur)
        for item in partants:
            n = int(item.get("n") or 0)
            try:
                if item.get("type") == "publier" and n in TEXTE_PUBLIER:
                    await _envoyer_publier(salon, membre, uid, n)
                    faits.append((uid, "publier", n))
                elif item.get("type") == "etape":
                    await envoyer_etape(salon, membre, n)
                    faits.append((uid, "etape", n))
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Programme de %s (%s %s) : %s", uid, item.get("type"), n, erreur)
    return faits


def _echu(item: dict, maintenant) -> bool:
    try:
        return datetime.fromisoformat(str(item.get("quand"))) <= maintenant
    except ValueError:
        return True                                                     # date illisible : on ne la garde pas indéfiniment


def attente(fiche_p: dict):
    """(n, date au plus tôt) du compte qui attend ses 48 h et ses Reels, sinon None."""
    for item in fiche_p.get("programme") or []:
        if item.get("type") == "etape" and int(fiche_p.get("etape", 0)) == int(item.get("n") or 0) \
                and not (fiche_p.get("dates") or {}).get(str(item.get("n"))):
            try:
                return int(item["n"]), datetime.fromisoformat(str(item["quand"]))
            except (KeyError, ValueError):
                return None
    return None


async def _classeur_etat(uid: str, n: int) -> None:
    """25/09 : le classeur des logins suit le parcours — compte 1/2/3 validé → sa ligne passe à WARMUP, warm-up
    fini (étape 4) → les trois lignes passent à GOOD. Sans le classeur (ou sans la dépendance), rien."""
    marquer = _deps.get("marquer_etat")
    if marquer is None or n not in (1, 2, 3):
        return
    comptes = _comptes_ordonnes(uid)                                    # 01/10 : le même ordre que l'étape envoyée
    for h in comptes[n - 1:n]:
        try:
            await marquer(h, "PRIVE" if n == 3 else "WARMUP")           # 05/10 : le compte 3 est privé, il ne chauffe pas
        except Exception as erreur:
            journal.warning("Classeur étape %s de %s : %s", n, uid, erreur)


async def boucle(client) -> None:
    """Chaque heure : le compte des jours de warm-up dans le salon (le matin), et l'ouverture automatique des Reels
    au jour WARMUP_JOURS + 1."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            try:
                await programme_du_jour(client)                         # 30/09 : « il peut publier », compte suivant à 48 h
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Programme du parcours : %s", erreur)
            try:                                                        # 08/10 : « Profil fait » oublié → l'étape se ferme seule
                fermes = await fermer_profils_oublies(client)
                if fermes:
                    journal.info("Étapes fermées après un profil oublié : %s", fermes)
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Profils oubliés : %s", erreur)
            try:                                                        # 08/10 : l'app de ceux qui ont leurs 3 comptes
                bilan_app = await rattraper_app(client)
                canal = await _deps["canal_admin"]() if (bilan_app and _deps.get("canal_admin")) else None
                if canal is not None:
                    await canal.send("\n".join(bilan_app)[:1990])
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("App clippers (rattrapage) : %s", erreur)
            maintenant = _deps["heure_paris"]()
            if maintenant.hour >= paie_clics.CLICS_HEURE and RELANCE_JOURS > 0:
                # 05/10 : les étapes 4 et 5 ne s'ouvrent plus (compte 3 privé → lien → routine) ; les fiches encore à 4 ou 5
                # sont migrées au démarrage (migrer_etapes_45). La ligne de warm-up quotidienne ne sert donc plus.
                d = _lire()
                for uid, fiche_p in list(d.items()):
                    if int(fiche_p.get("etape", 0)) != 4 or not fiche_p.get("dates", {}).get("4"):
                        continue
                    debut = datetime.fromisoformat(fiche_p["dates"]["4"]).date()
                    j = (maintenant.date() - debut).days + 1
                    if j == fiche_p.get("warmup_jour"):
                        continue
                    salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
                    if salon is None:
                        continue
                    fiche_p["warmup_jour"] = j
                    _ecrire(d)
                    if j > WARMUP_JOURS:
                        await salon.send(f"🎉 <@{uid}> ton warm-up est fini. Tu peux publier tes Reels !")   # 01/10 : plus de « tes 1 jours »
                        await valider_etape(salon, uid, 4, par="bot")
                    else:
                        comptes_w = _comptes_ordonnes(uid)              # 01/10 (relecture) : les autres comptes, sans les BAN
                        autres_w = [h for h in _vivants(uid, fiche_p, comptes_w[:3]) if h not in comptes_w[2:3]]
                        texte_w = WARMUP_JOUR_TEXTE.format(j=j, jours=WARMUP_JOURS, autres=_liste(autres_w))
                        if not (_deps.get("deposer") and _deps["deposer"](salon.id, "warmup", texte_w)):
                            await _suite(salon, f"<@{uid}> " + texte_w)
                # 28/09 : relance courte — une étape (1 à 3, 5, 6) qui traîne depuis RELANCE_JOURS jours → une ligne, tous les RELANCE_JOURS jours
                # 05/10 : éteinte par défaut (RELANCE_JOURS = 0) — « des relances simples » faisaient un message du matin vide chaque jour
                d = _lire()                                             # 01/10 : relu, valider_etape a pu écrire au-dessus
                for uid, fiche_p in list(d.items()):
                    n = int(fiche_p.get("etape", 0))
                    if RELANCE_JOURS <= 0 or n not in (1, 2, 3, 5, 6) or not fiche_p.get("dates", {}).get(str(n)):
                        continue
                    try:
                        depuis = (maintenant.date() - datetime.fromisoformat(fiche_p["dates"][str(n)]).date()).days
                    except ValueError:
                        continue
                    jour_s = maintenant.date().isoformat()
                    derniere = fiche_p.get("relance", "")
                    if depuis < RELANCE_JOURS or derniere == jour_s or (derniere and (maintenant.date() - datetime.fromisoformat(derniere).date()).days < RELANCE_JOURS):
                        continue
                    salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
                    if salon is None:
                        continue
                    fiche_p["relance"] = jour_s
                    _ecrire(d)
                    suite = prochaine_etape(salon.id)
                    texte_r = f"👉 <@{uid}> {suite}\n\nBloqué ? Écris ici." if suite else f"👉 <@{uid}> Étape {n} toujours en cours : `!etape` pour la revoir.\n\nBloqué ? Écris ici."
                    if not (_deps.get("deposer") and _deps["deposer"](salon.id, "relance", texte_r)):
                        await _suite(salon, texte_r)                    # 30/09 (GO n° 4) : remplace, n'empile pas
        except Exception as erreur:                                 # la boucle ne meurt jamais
            journal.warning("Boucle parcours : %s", erreur)
        await asyncio.sleep(3600)


# ------------------------------------------------------------------ mémoire
def memoire(uid: str) -> str:
    """Tout ce que le bot sait du clipper, en texte : pour le manager (`!memoire`) et pour l'assistant IA."""
    uid = str(uid)
    fiche_p = _lire().get(uid, {})
    equipes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {})
    onb = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(uid, {})
    membre = _deps["membre_par_id"](uid)
    nom = _prenom(membre) if membre else fiche_p.get("prenom", f"id {uid}")
    creatrice = fiche_p.get("creatrice") or equipes.get("creatrice") or onb.get("creatrice") or "aucune"
    n = int(fiche_p.get("etape", 0))
    titre = ETAPES[n]["titre"].format(jours=WARMUP_JOURS) if n in ETAPES else ("parcours non commencé" if n == 0 else "parcours terminé")
    if attente(fiche_p):                                                # 01/10 : l'étape n'est pas encore ouverte, rien à créer
        titre = f"attente du compte {n}, pas encore ouvert : rien à créer pour l'instant"
    date_etape = (fiche_p.get("dates") or {}).get(str(n), "")[:10]
    try:
        regime = paie_clics.regime(uid)
    except Exception:
        regime = "?"
    # 27/09 : l'assistant disait « continue sur tes deux autres comptes » à Daniella qui n'en avait qu'un. 01/10 : le nombre
    # de comptes CRÉÉS ne se déduit plus de l'étape (l'étape 2 attend souvent son compte) : seulement les étapes fermées.
    crees = sum(1 for i in (1, 2, 3) if _cree(fiche_p, i))
    lignes = [f"Clipper : {nom} (Discord {uid}) · créatrice : {creatrice} · signé le {str(equipes.get('date', ''))[:10] or '?'} "
              f"· paie : {regime}",
              f"Étape en cours : {titre}" + (f" (depuis le {date_etape})" if date_etape else "")
              + (f" · warm-up jour {fiche_p['warmup_jour']}/{WARMUP_JOURS}" if fiche_p.get("warmup_jour") else ""),
              f"Comptes créés : {crees} sur 3" + (" — les autres n'existent pas encore, n'en parle pas" if crees < 3 else "")]
    try:
        lignes.append(etat_des_comptes(uid))
    except Exception as erreur:                                     # noqa: BLE001
        journal.warning("État des comptes de %s : %s", uid, erreur)
    vivants = _vivants(uid, fiche_p)                                    # 01/10 : un compte BAN ne sert plus, on n'en parle plus
    if vivants:
        lignes.append("Comptes Instagram : " + ", ".join(vivants) + " (mots de passe déjà dans le salon, ne jamais les redonner)")
    if onb.get("lien"):
        lignes.append(f"Lien (dans la bio du compte 3 privé seulement ; comptes 1 et 2 : story à la une avec le widget de mention du compte 3) : {onb['lien']}")
    lignes.append("Drive : " + (onb["drive"] if onb.get("drive") else "pas encore prêt"))
    try:
        if paie_clics.actif():
            d = paie_clics._lire()
            lids = paie_clics.liens_de(d, uid)
            if lids:
                hier = paie_clics._aujourdhui() - timedelta(days=1)
                s7 = paie_clics.somme(d, lids, hier - timedelta(days=6), hier)
                lignes.append(f"Visites payables : {s7['payes']} sur 7 jours ({s7['payes'] / 7:.0f}/jour)")
    except Exception:
        pass
    for note in (fiche_p.get("notes") or [])[-5:]:
        lignes.append(f"Note du manager ({str(note.get('date', ''))[:10]}) : {note.get('texte', '')}")
    return "\n".join(lignes)


_derniers_etats = {}                                        # handle (minuscules) → état normalisé du classeur au dernier scan


def etat_des_comptes(uid: str, maintenant=None) -> str:
    """30/09 (Daniella, trois réponses contraires en une soirée : « publie demain », « ton compte 1 finit son warm-up demain
    aussi », « pas de story ni de publication ») : l'état de chaque compte, calculé, que l'assistant recopie au lieu de le
    déduire. 01/10 : compte i créé seulement si son étape est fermée (_cree), warm-up compté depuis sa création
    (_date_creation) ; BAN d'après le dernier scan du classeur ; le compte qui attend dit ce qui l'ouvre."""
    maintenant = maintenant or datetime.now(timezone.utc)
    fiche_p = _lire().get(str(uid), {})
    comptes = _comptes_ordonnes(uid)                                    # 01/10 : le même ordre que les étapes
    a = attente(fiche_p)
    parts = []
    for i in (1, 2, 3):
        h = comptes[i - 1] if i - 1 < len(comptes) else ""
        nom = f"compte {i}" + (f" `{h}`" if h else "")
        if _est_ban(h, fiche_p):
            # 01/10 (relecture) : le salon des codes nommé, plus « `!code` » seul (l'assistant disait « tape !code » au salon perso)
            parts.append(f"{nom} : BAN, il fait appel lui-même (Contester la décision, code dans #{codes_2fa.SALON_CODES_NOM} avec !code, "
                         "selfie, son numéro ou sa pièce d'identité si demandés)")
            continue
        if not _cree(fiche_p, i):
            if a and a[0] == i:                                         # 01/10 : la règle unique, sans date promise
                parts.append(f"{nom} : pas encore ouvert, il arrive tout seul au plus tôt {ATTENTE_COMPTE_H} h après le compte {i - 1}, "
                             f"dès que {REELS_OUVERTURE} Reels sont publiés dessus ({reels_vus(uid, fiche_p, i - 1)} vu(s) par le scan)")
            else:
                parts.append(f"{nom} : pas encore créé")
            continue
        d = _date_creation(fiche_p, i)
        if d is None:                                                   # parcours repris d'après le classeur : début de l'étape d'après
            try:
                d = datetime.fromisoformat(str((fiche_p.get("dates") or {}).get(str(i + 1))))
                d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                d = None
        fin = d + timedelta(days=WARMUP_JOURS) if d else None
        if fin and maintenant < fin:
            parts.append(f"{nom} : WARM-UP jusqu'au {_date_fr(fin)}, pas de Reel, 1 story sans lien par jour")
        else:
            parts.append(f"{nom} : PUBLIE, 2 Reels et 1 story par jour")
    return "État de chaque compte (fait foi) : " + " ; ".join(parts)


def _date_fr(d) -> str:
    from zoneinfo import ZoneInfo
    d = d.astimezone(ZoneInfo("Europe/Paris"))
    # 01/10 : les clippers sont à Dubaï, Madagascar, au Bénin — « 10 h 12 » sans fuseau trompait tout le monde
    return d.strftime("%d/%m à ") + f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "") + " (heure de Paris)"


def _prenom(membre) -> str:
    """Prénom d'un membre au pseudo « Prénom - Créatrice » (25/09) : avant le séparateur, puis premier mot."""
    nom = (getattr(membre, "display_name", "") or "").strip()
    for sep in (" - ", " – ", " — ", " | ", " · "):
        if sep in nom:
            nom = nom.split(sep, 1)[0].strip()
            break
    return nom.split()[0] if nom.split() else nom


PROCHAINES = {1: "ouvre ton compte 1, `{compte1}` (création ou connexion, c'est dans l'étape). Clique ✅ quand c'est fait.",
              2: "crée ton compte 2, `{compte2}`. Clique ✅ quand c'est fait.",
              3: "crée ton compte 3, `{compte3}`, le privé. Clique ✅ quand c'est fait.",
              4: "compte 3 en warm-up (Reels, likes, 1 story, pas de Reel) ; {autres} : 2 Reels et 1 story chacun.",
              5: "publie un Reel de ton Drive sur {vivants}. Clique ✅ quand c'est fait.",
              6: "mets ton lien dans la bio du compte 3, et sur les comptes 1 et 2 une story à la une avec le widget de mention du compte 3. Clique ✅ quand c'est fait.",
              7: "2 Reels sur chacun de ces comptes : {autres}. 1 story avec le widget vers ta story à la une."}


def prochaine_etape(salon_id, maintenant=None) -> str:
    """La ligne « 👉 Aujourd'hui » du message du matin, d'après l'étape du clipper dont c'est le salon."""
    maintenant = maintenant or datetime.now(timezone.utc)
    for uid, fiche_p in _lire().items():
        if str(fiche_p.get("salon_id")) != str(salon_id):
            continue
        n = int(fiche_p.get("etape", 0))
        if n not in PROCHAINES:
            return "" if n else "attends ta créatrice, ton manager te l'attribue."
        comptes = _comptes_ordonnes(uid)                                # 01/10 : le même ordre que les étapes (plus la liste brute)
        c = {f"compte{i + 1}": (comptes[i] if i < len(comptes) else "…") for i in range(3)}
        vivants = _vivants(uid, fiche_p, comptes[:3])                   # 01/10 : sans les comptes BAN
        c["vivants"] = _liste(vivants)
        c["autres"] = _liste([h for h in vivants if h != c["compte3"]])
        for item in fiche_p.get("programme") or []:
            # 01/10 (Mathias, Steeve : « publie tes Reels » le matin, « pas de Reel » une heure avant) : un compte encore en
            # warm-up le dit, et rien d'autre
            if item.get("type") == "publier" and not _echu(item, maintenant):
                k = int(item.get("n") or 0)
                quand = datetime.fromisoformat(str(item["quand"]))
                return (f"compte {k} en warm-up jusqu'au {_date_fr(quand)} : pas de Reel dessus. Je te dis ici quand il peut publier."
                        + (" Tes autres comptes : 2 Reels par jour." if k > 1 else ""))
        a = attente(fiche_p)
        if a:                                                           # 01/10 : le compte suivant attend ses 48 h ET ses Reels
            m = a[0] - 1
            if _bloque_ban(uid, fiche_p, m):                            # 01/10 (relecture) : plus de « tes autres comptes » fantôme
                return texte_bloque(m)[0].lower() + texte_bloque(m)[1:]
            ou = _ou_publier(uid, fiche_p, m)
            if reels_vus(uid, fiche_p, m) >= REELS_OUVERTURE:
                return f"ton compte {a[0]} arrive ici le {_date_fr(a[1])}. D'ici là : 2 Reels par jour sur {ou}."
            if maintenant < a[1]:
                return (f"2 Reels par jour sur {ou}. Ton compte {a[0]} arrive ici au plus tôt le {_date_fr(a[1])}, "
                        f"dès que {REELS_OUVERTURE} Reels sont publiés sur {ou}.")
            # 01/10 (relecture, règle 30) : plus de « Prends-les dans ton Drive », qui laissait publier sans modifier
            return (f"ton compte {a[0]} arrive dès que {REELS_OUVERTURE} Reels sont publiés sur {ou}.\n\n"
                    "Prends une vidéo dans ton Drive et modifie-la avant de la publier.")
        return PROCHAINES[n].format(**c)
    return ""


def _etats_comptes(uid, etats_par_handle: dict) -> list:
    """[(handle, état normalisé du classeur)] des comptes livrés au clipper, dans l'ordre compte 1, 2, 3 (_comptes_ordonnes)."""
    return [(h, _norm(etats_par_handle.get(h.lower(), "") or "")) for h in _comptes_ordonnes(uid)]


def etape_selon_classeur(etats: list) -> int:
    """26/09 : l'étape est celle du prochain compte à créer. 0 compte créé → 1, 1 → 2, 2 → 3 ; les trois créés → 4 (warm-up) ;
    les deux comptes de croissance GOOD → 7 (routine). Daniella (26/09, soir) : un seul compte créé la mettait au warm-up."""
    if not etats:
        return 7
    e = [x for _, x in etats]
    crees = [x for x in e if x not in ("a creer", "à créer", "")]
    if len(crees) < min(3, len(e)):
        return 1 + len(crees)
    if len(e) >= 2 and all(x == "good" for x in e[:2]):
        return 7
    return 6                                                            # 08/10 : plus l'étape 4 (supprimée le 05/10) : le lien


def migrer_etapes_45(d: dict) -> list:
    """05/10 : les étapes 4 (warm-up du compte 3) et 5 (Reels sur 3 comptes) n'existent plus. Une fiche encore à 4 ou 5 passe à 6
    (le lien), sans message ici : l'appelant envoie l'étape 6. Renvoie les uid migrés."""
    migres = []
    for uid, fiche_p in d.items():
        if isinstance(fiche_p, dict) and int(fiche_p.get("etape", 0) or 0) in (4, 5):
            fiche_p["etape"] = 6
            fiche_p.pop("warmup_jour", None)
            migres.append(uid)
    return migres


async def migrer_au_demarrage(client) -> int:
    """05/10 : au démarrage, les fiches aux étapes 4 et 5 reçoivent l'étape 6 (lien et story à la une) dans leur salon."""
    d = _lire()
    migres = migrer_etapes_45(d)
    if not migres:
        return 0
    _ecrire(d)
    n = 0
    for uid in migres:
        fiche_p = _lire().get(uid) or {}
        salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0)) if client is not None else None
        membre = _deps["membre_par_id"](uid)
        if salon is None or membre is None:
            continue
        try:
            await envoyer_etape(salon, membre, 6)
            n += 1
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Migration de l'étape de %s : %s", uid, erreur)
    journal.info("Parcours : %d fiche(s) migrée(s) des étapes 4/5 à l'étape 6, %d étape(s) envoyée(s)", len(migres), n)
    return n


def _en_place(uid: str) -> str:
    """08/10 : '' pour un inconnu ; sinon ce que le registre et la paie au clic disent d'un clipper sans fiche de parcours (ancien) :
    sa créatrice, ses visites payées sur 7 jours, son salon perso. Jamais d'identifiant ni de lien (salon commun)."""
    morceaux = []
    try:
        fiche = (_deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}).get(uid) or {}
    except Exception:                                                   # noqa: BLE001
        fiche = {}
    if fiche.get("creatrice"):
        morceaux.append(f"créatrice {fiche['creatrice']}")
    try:
        d = paie_clics._lire()
        lids = paie_clics.liens_de(d, uid)
        if lids:
            hier = datetime.now(timezone.utc).date() - timedelta(days=1)
            s7 = paie_clics.somme(d, lids, hier - timedelta(days=6), hier)
            morceaux.append(f"{s7.get('payes', 0)} visites payées sur 7 jours, il a donc son lien et publie")
    except Exception:                                                   # noqa: BLE001
        pass
    if not morceaux:
        try:                                                            # 08/10 : un ancien du roster de Jonas, absent du registre
            import roster as _roster
            m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            prenom = (m.display_name.split() or [""])[0] if m is not None else ""
            if prenom and _roster.actif() and _roster.est_actif(prenom):
                morceaux.append("clipper du roster de Jonas (ancien, déjà en place)")
        except Exception:                                               # noqa: BLE001
            pass
    if not morceaux:
        return ""
    salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
    morceaux.append("salon perso : " + ("oui" if salon is not None else "PAS ENCORE"))
    return ", ".join(morceaux)


def contexte_court(uid: str) -> str:
    """05/10 : ce que l'assistant du salon #assistant sait du clipper — l'étape et le nombre de comptes créés, jamais un
    identifiant, un mot de passe ni un lien (le salon est commun : rien ne doit passer d'un clipper à l'autre)."""
    fiche_p = _lire().get(str(uid), {})
    n = int(fiche_p.get("etape", 0) or 0)
    crees = sum(1 for i in (1, 2, 3) if _cree(fiche_p, i))
    if n == 0 and not fiche_p:
        # 08/10 (Yves, ancien à 50 visites par jour, sans salon à cause d'une panne : l'assistant lui a dit d'attendre son compte 1,
        # puis de taper J'ACCEPTE et de faire la formation) : sans fiche de parcours, les faits du registre et de la paie au clic.
        en_place = _en_place(str(uid))
        if en_place:
            return (f"clipper DÉJÀ EN PLACE, sans parcours guidé : {en_place}. Ne lui parle ni de compte 1 à attendre, ni de formation, "
                    "ni de quiz, ni de J'ACCEPTE. Sans salon perso : l'équipe le lui ouvre, il mentionne @Gaëtan ici. "
                    "Règle du lien : seulement dans la bio du compte 3 privé ; comptes 1 et 2 : une story à la une avec le widget de mention du compte 3")
    if n == 0:
        etape = "parcours pas encore commencé (il attend sa créatrice et son compte 1)"
    elif n in ETAPES:
        etape = ETAPES[n]["titre"]
        a = attente(fiche_p)
        if a and a[0] == n:
            etape = f"attente du compte {n} : il arrive tout seul au plus tôt {ATTENTE_COMPTE_H} h après le compte {n - 1}, dès que {REELS_OUVERTURE} Reels sont publiés dessus"
    else:
        etape = "parcours terminé (routine)"
    return (f"étape : {etape} · comptes créés : {crees} sur 3 · WhatsApp fait : {'oui' if fiche_p.get('whatsapp') else 'non'} · "
            "règle du lien : seulement dans la bio du compte 3 privé ; comptes 1 et 2 : une story à la une avec le widget de mention du compte 3")


def oublier(uid: str) -> bool:
    """Retire la fiche de parcours d'un clipper (salon perso supprimé le 26/09) : plus de warm-up ni d'étape postés nulle part."""
    d = _lire()
    if str(uid) not in d:
        return False
    d.pop(str(uid), None)
    _ecrire(d)
    return True


async def forcer_etape(salon, membre, creatrice: str, n: int) -> None:
    """Pose l'étape n (date du jour, utile au compte des jours de warm-up) et l'envoie dans le salon."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.setdefault(uid, {"prenom": _prenom(membre), "creatrice": creatrice, "salon_id": str(salon.id), "etape": 0,
                                 "dates": {}, "notes": []})
    fiche_p.update({"etape": n, "salon_id": str(salon.id), "creatrice": creatrice or fiche_p.get("creatrice", "")})
    fiche_p.setdefault("dates", {})[str(n)] = _maintenant()
    fiche_p.pop("warmup_jour", None)
    _ecrire(d)
    await envoyer_etape(salon, membre, n)


async def demarrer_selon_classeur(salon, membre, creatrice: str, etats_par_handle: dict) -> int:
    """Pour un clipper déjà en place : l'étape de départ dépend de l'état réel de ses comptes dans le classeur."""
    n = etape_selon_classeur(_etats_comptes(membre.id, etats_par_handle))
    if n == 1:
        await demarrer_parcours(salon, membre, creatrice)
    elif n == 7:
        await demarrer_routine(salon, membre, creatrice)
    else:
        await forcer_etape(salon, membre, creatrice, n)
    return n


def reels_depuis(historique: list, depuis) -> int:
    """08/10 (audit : avec 1 Reel par jour, le cumul par différence d'une fenêtre glissante de 3 jours plafonnait à 3, et le
    compte suivant, qui en demande 4, ne s'ouvrait jamais) : la somme des publications de chaque passage du scan (chaque passage
    couvre ses 24 h, un passage par jour) depuis la création du compte."""
    jour0 = depuis.date().isoformat() if depuis is not None else ""
    return sum(int(e.get("posts") or 0) for e in historique or []
               if e.get("existe") and str(e.get("jour", ""))[:10] >= jour0)


async def reconcilier(client, etats_par_handle: dict, publies=None, reels_72h=None, historique=None) -> list:
    """Après chaque scan du classeur : un compte créé sur Instagram valide tout seul l'étape 1, 2 ou 3 ; un clipper mis
    en routine par erreur alors que ses comptes sont à créer ou en warm-up est remis à la bonne étape (une seule fois)."""
    faits = []
    _derniers_etats.clear()
    _derniers_etats.update({str(h).lower(): _norm(e or "") for h, e in (etats_par_handle or {}).items()})
    # 01/10 : d'abord, retenus dans chaque fiche (sans attente ni envoi entre la lecture et l'écriture) : les comptes BAN, et
    # les Reels vus sur chaque compte créé — c'est ce qui ouvre le compte suivant (règle unique, programme_du_jour)
    jour = datetime.now(timezone.utc).date().isoformat()
    d = _lire()
    change = _migrer_essai(d)
    for uid, fiche_p in d.items():
        comptes = _comptes_ordonnes(uid)
        if not comptes or not isinstance(fiche_p, dict):
            continue
        bans = sorted(h.lower() for h in comptes if _derniers_etats.get(h.lower()) == "ban")
        if bans != sorted(fiche_p.get("bans") or []):
            fiche_p["bans"] = bans
            change = True
        if reels_72h is None:
            continue
        for i, h in enumerate(comptes[:3], start=1):
            if not _cree(fiche_p, i) or _derniers_etats.get(h.lower(), "") in ("", "a creer", "à créer"):
                continue
            avant = (fiche_p.get("reels") or {}).get(h.lower())
            apres = _cumuler_reels(avant, int((reels_72h or {}).get(h.lower(), 0) or 0), jour)
            if historique is not None:                                  # 08/10 : le vrai cumul, jamais en baisse
                somme = reels_depuis(historique.get(onboarding.normaliser_handle(h).lower(), []), _date_creation(fiche_p, i))
                apres["vus"] = max(int(apres.get("vus", 0) or 0), somme)
            if apres != avant:
                fiche_p.setdefault("reels", {})[h.lower()] = apres
                change = True
    if change:
        _ecrire(d)
    for uid, fiche_p in list(_lire().items()):
        n = int(fiche_p.get("etape", 0))
        salon = client.get_channel(int(fiche_p.get("salon_id") or 0)) if fiche_p.get("salon_id") else None
        membre = _deps["membre_par_id"](uid)
        if salon is None or membre is None:
            continue
        etats = _etats_comptes(uid, etats_par_handle)
        if not etats:
            continue
        try:
            if n == 7 and not fiche_p.get("dates", {}).get("1_fait") and not fiche_p.get("reconcilie"):
                cible = etape_selon_classeur(etats)
                d = _lire()
                d[uid]["reconcilie"] = _maintenant()
                _ecrire(d)
                if cible != 7:
                    await forcer_etape(salon, membre, fiche_p.get("creatrice", ""), cible)
                    faits.append((_prenom(membre), 7, cible))
            elif n in (1, 2, 3) and n - 1 < len(etats):
                h, e = etats[n - 1]
                # 01/10 (Steeve) : un compte rendu par un sortant existe avant même que le clipper s'y connecte → jamais validé
                # sur sa seule existence, il faut le bouton
                recycle = any(isinstance(a, dict) and a.get("handle") == h and a.get("cree") for a in (_onb(uid).get("acces") or []))
                if e and e not in ("a creer", "à créer") and not recycle and await valider_etape(salon, uid, n, par="classeur"):
                    faits.append((_prenom(membre), n, n + 1))
            elif n == 5 and publies and any(str(h).lower() in publies for h, _ in etats):
                # 28/09 (GO n° 4) : le premier Reel vu par le scan ferme l'étape 5 tout seul
                if await valider_etape(salon, uid, 5, par="scan"):
                    faits.append((_prenom(membre), 5, 6))
            elif n == 4 and not fiche_p.get("corrige_4"):
                # 26/09 (Daniella) : mise au warm-up avec un seul compte créé → retour à l'étape du prochain compte, une seule fois
                cible = etape_selon_classeur(etats)
                if cible < 4:
                    d = _lire()
                    d[uid]["corrige_4"] = _maintenant()
                    _ecrire(d)
                    await forcer_etape(salon, membre, fiche_p.get("creatrice", ""), cible)
                    faits.append((_prenom(membre), 4, cible))
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réconciliation du parcours de %s : %s", uid, erreur)
    try:                                                                # 01/10 : les Reels du scan ouvrent le compte suivant tout de suite
        faits += [(u, t, k) for u, t, k in await programme_du_jour(client) if t == "etape"]
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Programme après le scan : %s", erreur)
    if faits:
        journal.info("Parcours réconciliés avec le classeur : %s", faits)
    return faits


def contexte_llm(uid: str) -> str:
    """Le bloc de contexte ajouté à chaque question posée dans le salon perso : le bot y est le manager."""
    return ("[Salon perso : ici tu es l'ASSISTANT du clipper au quotidien (pas son manager). Tu parles comme à un élève de collège : phrases de "
            "10 mots maximum, mots simples, une action par ligne, jamais de parenthèses. Réponds court, une action à la fois, tutoie, "
            # 01/10 (relecture) : plus de `!code` seul, qui faisait dire « tape !code » dans le salon perso
            "guide-le selon son étape en cours, renvoie aux fiches du forum et à `!mesclics` (ses visites) ; pour un code, "
            "la phrase canonique ci-dessous. Les comptes se créent ici, guidés par le parcours : plus de créneau "
            "lundi/mercredi/vendredi, plus de contrat, plus de distinction France/International. Ne redonne jamais un mot "
            "de passe. Paie : 0,05 $ par visite francophone réelle sur son lien, tous les 15 jours, USDC ou virement. "
            # 01/10 (Gaëtan) : une seule règle des comptes, pour tous, mot pour mot ; une seule phrase pour les codes
            f"Règle des comptes (01/10), la même pour tous, nouveaux et anciens, à redire mot pour mot : « {regle_comptes()} » "
            "Jamais « un compte par jour », jamais « demain », jamais un autre nombre de Reels, jamais de période d'essai ; tu ne "
            "promets jamais de date pour le compte suivant et tu ne pousses jamais à créer un compte que le bot n'a pas encore "
            "ouvert. 24 h de warm-up sur chaque compte après sa création (Reels, likes, abonnements, 1 story sans lien, zéro Reel), "
            "puis CE compte publie 2 Reels et 1 story par jour, sans attendre les autres — ne dis jamais « une semaine de warm-up » "
            f"ni « dans 7 jours ». Les codes Instagram, une seule phrase : « {texte_codes()} » Jamais « écris !code ici », jamais "
            "« le code arrive ici tout seul ». La ligne « État de chaque "
            "compte » de la mémoire FAIT FOI : tu ne la contredis jamais, ni le message d'étape posté dans le salon. "
            "La story du jour se prend dans le dossier Photos de son Drive (une photo, ou une courte vidéo du dossier Reels) ; "
            "si le clipper voit un dossier, il existe : tu ne le nies jamais ; s'il est vide, il prend sa story dans Photos et "
            "l'équipe est prévenue. Il demande OÙ prendre "
            "la story : tu réponds au où, pas au widget. Un compte BAN ne change rien pour les autres : ils continuent. "
            "On ne réutilise jamais une info d'un compte BAN (identifiant, e-mail, mot de passe) pour un autre compte. "
            f"Un compte banni (30/09) : il fait appel lui-même, tout de suite (« Contester la décision », le code dans "
            f"#{codes_2fa.SALON_CODES_NOM} avec !code, selfie vidéo, son "
            "numéro ou sa pièce d'identité si Instagram les demande, jamais ceux d'un autre, jamais sa pièce d'identité dans Discord) ; "
            "tu ne promets jamais un compte neuf "
            "ni une date (« demain ») : si l'appel échoue, Gaëtan décide. "   # 01/10 (relecture) : une seule version du ban
            "Le lien (05/10) : il n'existe qu'avec le compte 3, le compte PRIVÉ, dans sa bio, et nulle part ailleurs ; les comptes 1 et 2 "
            "(croissance) ne portent jamais de lien : une story (photo ou vidéo) avec le widget de mention du compte 3, mise à la une, une "
            "seule fois ; chaque jour une story avec le widget vers cette story à la une. Deux comptes de croissance qui font 24 h de "
            "warm-up après leur création puis publient, et un compte 3 privé qui ne publie pas. Un compte « qui existe déjà » (rendu par un ancien) : on s'y "
            "connecte, et le code se demande comme les autres. Le Drive s'ouvre par son lien, jamais besoin d'une adresse e-mail. "
            "Quand il dit qu'une étape est faite, dis-lui de cliquer le bouton ✅ sous le message de l'étape, ou d'écrire "
            "`!etape` pour la revoir. Appelle-le par son prénom (celui de la mémoire), jamais par celui de la créatrice. "
            "Trois lignes maximum. La ligne « 👉 Prochaine étape : … » seulement si elle dit autre chose que l'étape déjà "
            "affichée dans le salon avec son bouton. Aucune question inutile (modèle de téléphone, « dis-moi quand c'est "
            "fait »). Tu ne parles que des comptes CRÉÉS d'après la mémoire : jamais « tes deux autres comptes » s'ils "
            "n'existent pas encore. Tu ne donnes jamais la cause d'un blocage, seulement la marche à suivre ; « déconnecté, "
            f"mot de passe modifié » = se reconnecter avec le mot de passe de son étape, puis le code dans "
            f"#{codes_2fa.SALON_CODES_NOM} avec !code ; s'il ne marche plus, "
            "WhatsApp Gaëtan, jamais « Mot de passe oublié ». `!code` ne donne QUE les codes reçus par e-mail (création, "
            "connexion, appel), jamais ceux qui changent l'e-mail, le mot de passe ou le numéro. Instagram demande un NUMÉRO de téléphone : il met LE SIEN et reçoit le SMS (décision du 26/09), ce numéro ne "
            "sert qu'à ses 3 comptes. Instagram demande un SELFIE VIDÉO : il le fait lui-même, avec son visage, c'est normal. "
            "Jamais de « compte prêt à l'emploi », jamais « ton manager a une autre solution » : si tu ne sais pas, renvoie vers "
            "Gaëtan sur WhatsApp (le lien est dans tes règles). Ne recopie jamais la ligne [Contexte : …].]\n"
            "[Mémoire du clipper]\n" + memoire(uid))


# ------------------------------------------------------------------ commandes manager
TEXTES_APP = {"exclu": "pas d'app au clic pour lui (prénom exclu de la paie au clic)",
              "sans_lien": "aucun lien GAML à son nom",
              "sans_app": "l'app ne connaît pas son lien GAML (note « Clipping Prénom » ? onglet « Liens app » pas encore écrit ?)",
              "pas_pret": "pas de salon perso ou plus sur le serveur",
              "erreur": "message refusé par Discord"}


async def commande_app(message) -> bool:
    """08/10 : `!app` tapé par le clipper : dans son salon perso, le bouton de son app et son lien, une fois ses 3 comptes créés.
    Jamais ailleurs : le lien de l'app ouvre sa paie et son adresse USDC."""
    uid = str(message.author.id)
    salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
    if salon is None or getattr(message.channel, "id", None) != salon.id:
        await message.reply("Tape `!app` dans ton salon perso. Ton lien d'app est à toi seul.")
        return True
    if not trois_comptes(_lire().get(uid) or {}):
        await message.reply("Ton app arrive ici dès que ton compte 3 est créé.")
        return True
    etat = await livrer_app(uid, salon=salon, membre=message.author, forcer=True)
    if etat != "envoye":
        await message.reply({"exclu": "Ta paie ne passe pas par les visites : pas d'app pour toi.",
                             "sans_lien": "Tu n'as pas encore de lien. Ton manager s'en occupe."}.get(
                                 etat, "Je n'arrive pas à trouver ton app. Réessaie dans une heure."))
    return True


async def commande_pseudo(message, texte: str) -> bool:
    """08/10 : `!pseudo 1 nouvel_identifiant` (le clipper, dans son salon perso) ou `!pseudo @clipper 1 nouvel_identifiant` (staff) :
    l'identifiant prévu du compte n était pris sur Instagram, le clipper en a créé un autre. Le classeur, sa fiche, les Reels suivis
    et le scan passent au nouveau nom (onboarding.renommer_compte) ; une ligne au salon admin."""
    staff = bool(_deps.get("est_staff") and _deps["est_staff"](message.author))
    membre = message.mentions[0] if (staff and message.mentions) else message.author
    reste = [m for m in texte.split()[1:] if not m.startswith("<@")]
    if len(reste) != 2 or not reste[0].isdigit() or int(reste[0]) not in (1, 2, 3):
        await message.reply("Écris : `!pseudo 1 ton_identifiant` (1, 2 ou 3 : le numéro du compte).")
        return True
    uid, n = str(membre.id), int(reste[0])
    if not staff:
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        if salon is None or getattr(message.channel, "id", None) != salon.id:
            await message.reply("Tape `!pseudo` dans ton salon perso.")
            return True
    comptes = _comptes_ordonnes(uid)
    if n > len(comptes) or not comptes[n - 1]:
        await message.reply(f"Je n'ai pas de compte {n} pour toi.")
        return True
    ancien = comptes[n - 1]
    nouveau = onboarding.normaliser_handle(reste[1]).lower()
    if n in (1, 2) and onboarding.RE_PRIVE.search(nouveau):
        await message.reply("❌ Pas changé : ce nom ressemble à un compte privé (priv, secret, perso). Choisis-en un autre.")
        return True
    try:
        raison = await onboarding.renommer_compte(uid, ancien, nouveau)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("!pseudo de %s : %s", uid, erreur)
        raison = "le classeur ne répond pas, réessaie dans une minute"
    if raison:
        await message.reply(f"❌ Pas changé : {raison}.")
        return True
    d = _lire()                                                         # les Reels déjà vus suivent le compte
    suivis = (d.get(uid) or {}).get("reels") or {}
    if ancien.lower() in suivis:
        suivis[nouveau] = suivis.pop(ancien.lower())
        _ecrire(d)
    await message.reply(f"✅ C'est noté : ton compte {n} est maintenant `{nouveau}`. Je le suis sous ce nom.")
    try:
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal is not None:
            await canal.send(f"✏️ {membre.display_name} : compte {n} `{ancien}` → `{nouveau}` (identifiant prévu pris, classeur mis à jour)")
    except Exception:                                                   # noqa: BLE001
        pass
    return True


async def commande_staff(message, texte: str) -> bool:
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!etape", "!note", "!memoire", "!mémoire", "!wa", "!app", "!pseudo"):
        return False
    if mots[0].lower() == "!pseudo":
        return await commande_pseudo(message, texte)
    est_staff = _deps.get("est_staff")
    if len(mots) == 1 and mots[0].lower() == "!etape" and est_staff is not None and not est_staff(message.author):
        # 25/09 (Daniella) : le clipper tape `!etape` seul dans son salon → je lui renvoie son étape en cours
        uid = str(message.author.id)
        fiche_p = _lire().get(uid, {})
        n = int(fiche_p.get("etape", 0))
        if n not in ETAPES:
            await message.reply("Ton parcours n'a pas encore commencé. Ton manager le lance." if n == 0
                                else "Ton parcours est fini. Écris `!mesclics` pour voir tes visites.")
            return True
        # 05/10 : plus de renvoi de l'étape entière (identifiants compris) : le titre et le lien vers le message d'origine
        mid = (fiche_p.get("messages") or {}).get(str(n))
        guild = getattr(message, "guild", None)
        lien_m = f"https://discord.com/channels/{guild.id}/{message.channel.id}/{mid}" if (mid and guild is not None) else ""
        a = attente(fiche_p)
        if a and a[0] == n:
            await message.reply(f"Ton compte {n} arrive tout seul ici, au plus tôt {ATTENTE_COMPTE_H} h après le compte {n - 1}, "
                                f"dès que {REELS_OUVERTURE} Reels sont publiés dessus ({reels_vus(uid, fiche_p, n - 1)} vu(s) par le scan).")
            return True
        await message.reply(f"📍 **{ETAPES[n]['titre']}**" + (f" — ton message d'étape est là : {lien_m}" if lien_m else "")
                            + "\n\nFait ? Appuie sur son bouton ✅.")
        return True
    membre = message.mentions[0] if message.mentions else None
    reste = [m for m in mots[1:] if not m.startswith("<@")]
    if membre is None and reste and _deps.get("chercher_membre"):    # « !etape Gaëtan 1 » sans vraie mention Discord
        membre = _deps["chercher_membre"](reste[0].lstrip("@"))
        if membre is not None:
            reste = reste[1:]
    if membre is None:
        await message.reply("Format : `!etape @clipper [n]` (renvoyer ou forcer une étape) · `!note @clipper texte` "
                            "(mémoire du bot sur lui) · `!memoire @clipper` (ce que le bot sait) · `!wa @clipper` (il a écrit sur "
                            "WhatsApp) · `!app @clipper` (renvoyer son app et son lien dans son salon). Le @ doit être une vraie "
                            "mention, ou tape le prénom tel quel.")
        return True
    uid = str(membre.id)
    if mots[0].lower() == "!app":                                         # 08/10 : renvoyer son app et son lien, même avant le compte 3
        salon_a = _deps["salon_perso"](uid)
        if salon_a is None:
            await message.reply(f"{membre.display_name} n'a pas de salon perso.")
            return True
        etat = await livrer_app(uid, salon=salon_a, membre=membre, forcer=True)
        await message.reply(f"📱 App envoyée à {membre.display_name} dans <#{salon_a.id}>." if etat == "envoye"
                            else f"📱 Pas d'app envoyée à {membre.display_name} : {TEXTES_APP.get(etat, etat)}.")
        return True
    if mots[0].lower() == "!wa":                                          # 05/10 : le clipper a écrit sur WhatsApp, son groupe est ouvert
        if reste and reste[0].lower() in ("non", "annuler", "pas"):         # 08/10 : il s'est déclaré à tort
            await message.reply(f"📲 Annulé : {membre.display_name} redevient « pas de WhatsApp »." if marquer_whatsapp(uid, annuler=True)
                                else f"{membre.display_name} n'a pas de fiche de parcours.")
            return True
        if marquer_whatsapp(uid):
            if _deps.get("activite"):                                   # 08/10 (audit) : le `!wa` du staff vaut réponse à l'appel
                try:
                    _deps["activite"](uid)
                except Exception:                                       # noqa: BLE001
                    pass
            await message.reply(f"📲 Noté : {membre.display_name} a écrit sur WhatsApp. Il ne sera plus listé dans les bloqués pour ça.")
        else:
            await message.reply(f"{membre.display_name} n'a pas de fiche de parcours (pas encore de créatrice ?).")
        return True
    if mots[0].lower() in ("!memoire", "!mémoire"):
        await _deps["envoyer_long"](message, [f"🧠 **Mémoire de {membre.display_name}**"] + memoire(uid).split("\n"))
        return True
    if mots[0].lower() == "!note":
        if not reste:
            await message.reply("Format : `!note @clipper texte` — ex. `!note @Eddy préfère Edits, a un iPhone 11, absent le 3/10`.")
            return True
        d = _lire()
        fiche_p = d.setdefault(uid, {"prenom": _prenom(membre), "creatrice": "", "salon_id": "", "etape": 0, "dates": {}, "notes": []})
        fiche_p.setdefault("notes", []).append({"date": _maintenant(), "par": str(message.author.id), "texte": " ".join(reste)[:400]})
        fiche_p["notes"] = fiche_p["notes"][-30:]
        _ecrire(d)
        await message.reply(f"🧠 Noté pour {membre.display_name} ({len(fiche_p['notes'])} note(s)). Le bot s'en sert dans son salon.")
        return True
    # !etape @clipper [n]
    salon = _deps["salon_perso"](uid)
    if salon is None:
        await message.reply(f"{membre.display_name} n'a pas de salon perso : `!creatrice @{membre.display_name} Prénom` d'abord.")
        return True
    d = _lire()
    fiche_p = d.get(uid) or {}
    n = next((int(m) for m in reste if m.isdigit() and int(m) in ETAPES), int(fiche_p.get("etape", 0)) or 1)
    if not fiche_p:
        equipes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {})
        d[uid] = {"prenom": _prenom(membre), "creatrice": equipes.get("creatrice", ""), "salon_id": str(salon.id),
                  "etape": 0, "dates": {}, "notes": []}
        _ecrire(d)
    await envoyer_etape(salon, membre, n)
    await message.reply(f"📍 Étape {n} envoyée à {membre.display_name} dans <#{salon.id}>.")
    return True
