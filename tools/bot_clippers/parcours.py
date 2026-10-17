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

09/10 (Gaëtan : « distribue connaissances et informations au compte-goutte… Chaque étape à la fois… Saute des lignes, aère ») :
bienvenue (créatrice, vidéos d'origine, WhatsApp, « ✅ C'est fait ») → compte 1 → 4 Reels → compte 2 → 4 Reels → compte 3 privé
(son lien dans le profil) → story à la une → la routine et l'app en UN message → 7 jours plus tard, la suite de la routine.

10/10 (Gaëtan : « simplifier et supprimer toutes les étapes inutiles… Ils peuvent directement créer le premier compte ») : bienvenue
(WhatsApp sans attente) → compte 1 juste derrière → « Compte n créé » ferme l'étape, profil + warm-up en un message (plus de « Profil
fait » sur les comptes qui publient) → compte 3 privé, « Profil fait » → story à la une et routine + app, sans étape 6 ni suite à J+7.
"""

import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import discord

import codes_2fa
import lien_app
import onboarding
import process_clippeur
import paie_clics

journal = logging.getLogger("parcours")
_deps = {}
WARMUP_JOURS = int(os.environ.get("WARMUP_JOURS", "1") or 1)
# 01/10 (Gaëtan : « la même règle pour tous, nouveaux et anciens, plus de période d'essai à part : le compte suivant s'ouvre
# tout seul, au plus tôt 48 h après la création du précédent, et seulement quand 2 Reels sont publiés dessus ») : remplace la
# période d'essai du 30/09 (5 Reels en 72 h, nouveaux seulement). Les Reels sont ceux que le scan du matin voit, cumulés
# compte par compte dans la fiche (_cumuler_reels) ; les fiches encore « en essai » passent sous la règle sans message
# (_migrer_essai). `!etape @clipper n` (staff) force toujours.
REELS_OUVERTURE = 4   # 05/10 (Gaëtan) : « 48 h et 4 Reels »
# 30/09 (Gaëtan : « arrête de spammer les clippeurs : une information à la fois, au bon moment ; un compte par un compte, on
# distille l'information et on ne la donne que quand il en a réellement besoin ») : chaque compte se fait en trois temps,
# un message chacun — 1) identifiants et création, bouton « créé » ; 2) photo, nom et bio en UN message, bouton « profil
# fait » ; 3) une ligne de warm-up. Le compte suivant arrive tout seul 48 h plus tard (la règle des 48 h n'était qu'une
# phrase : le compte 2 tombait dès le bouton du compte 1), et « il peut publier » arrive 24 h plus tard, avec le Drive.
DISTILLE_DEPUIS = "2026-09-30T06:40:00+00:00"   # une étape envoyée avant : son profil est déjà parti (ancien déroulé), pas de doublon
ATTENTE_COMPTE_H = 0
WARMUP_H = int(os.environ.get("PARCOURS_WARMUP_H", "24") or 24)
# 08/10 (Gaëtan, GO n° 1 du checkup : « le compte privé en 2e position ») : compte 1 croissance, compte 2 PRIVÉ (le lien dans sa
# bio), compte 3 croissance. Le lien existe à J+2 au lieu de J+5-6 : les Reels du compte 1 ont une destination dès leurs
# premières vues. Le compte privé ne publie pas : le compte 3 s'ouvre 48 h après lui, quand 4 Reels de plus sont publiés sur le
# compte 1. L'ordre est figé dans la fiche à l'ouverture de l'étape 2 ; une fiche dont l'étape 2 est déjà partie garde l'ordre du
# 05/10 (privé en 3). PARCOURS_PRIVE_EN_2=0 revient à l'ordre du 05/10 pour les nouvelles fiches.
# 09/10 (Gaëtan : « garde le compte privé en 3e position et fais-le créer uniquement si le clippeur publie bien sur les deux premiers
# comptes ») : retour au privé en 3 par défaut. Une fiche notée « prive2 » dont l'étape 2 n'est pas encore partie repasse en
# « prive3 » ; celles dont le privé (compte 2) est déjà ouvert le gardent (jamais un compte refait). Le privé (compte 3) s'ouvre
# 48 h après le compte 2, quand 4 Reels sont publiés sur le compte 2 ET 4 Reels de plus sur le compte 1 depuis la création du
# compte 2 (`sources_reels`, base retenue dans `base_reels["3"]`).
PRIVE_EN_2 = False


def ordre(fiche_p: dict) -> str:
    """« prive2 » (compte 2 privé) ou « prive3 » (l'ordre du 05/10). Figé dans `fiche_p["ordre"]` à l'ouverture de l'étape 2."""
    if not fiche_p:
        return "prive3"                                                 # pas de parcours (ancien, inconnu) : l'ordre du 05/10
    dates = fiche_p.get("dates") or {}
    # 09/10 (carte des comptes : un ancien repris d'après le classeur, jamais passé par l'étape 1, se retrouvait en « prive2 » et son
    # compte 2, qui publie, devenait « le privé ») : une fiche sans étape 1 est « prive3 » — sauf si un de ses comptes est déjà ouvert
    # dans l'ordre « prive2 » (ancien figé le 08/10, remplacement qui a vidé les dates) : on ne renumérote jamais un compte déjà donné.
    # 09/10 (revue : le plan dit « toujours prive3 ») : la bascule renumérotait le privé déjà donné et, à l'étape 3 en attente,
    # exigeait 4 Reels d'un compte 2 jamais créé (bloqué sans fin) ; ces fiches et celles dont le compte 2 publie sont signalées au
    # salon admin (verifier_prive2), Gaëtan tranche.
    if not any(dates.get(k) for k in ("1", "1_fait", "2", "2_fait", "3", "3_fait")):
        return "prive3"
    if fiche_p.get("ordre") == "prive2" and not PRIVE_EN_2 and not dates.get("2") and not dates.get("2_fait"):
        return "prive3"                                                 # 09/10 : retour au privé en 3, son compte 2 n'est pas ouvert
    if fiche_p.get("ordre") in ("prive2", "prive3"):
        return fiche_p["ordre"]
    # 08/10 (revue) : seulement un parcours commencé (étape 1 envoyée) ; une fiche créée par `!note` pour un ancien garde l'ordre du 05/10
    if PRIVE_EN_2 and dates.get("1") and not dates.get("2") and not dates.get("2_fait") and int(fiche_p.get("etape", 0) or 0) <= 2:
        return "prive2"
    return "prive3"


def prive2_douteux(uid, fiche_p: dict = None) -> bool:
    """09/10 : en ordre « prive2 », le compte 2 doit être réellement privé — son @ (priv, secret, perso) ou l'ETAT « PRIVE » du
    classeur (onboarding._est_prive). Douteux seulement si le classeur, au dernier scan, le dit WARMUP ou GOOD (il publie) ; un
    compte pas encore créé, BAN ou pas lu ne prouve rien. 09/10 (revue : entre sa création et son passage en privé, le scan peut le
    voir WARMUP) : seulement ATTENTE_COMPTE_H heures après la fermeture de son étape (« 2_fait »)."""
    fiche_p = (_lire().get(str(uid)) or {}) if fiche_p is None else fiche_p
    try:
        ferme = datetime.fromisoformat(str((fiche_p.get("dates") or {}).get("2_fait")))
        ferme = ferme if ferme.tzinfo else ferme.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False                                                    # compte 2 pas encore fermé : en cours de création
    if datetime.now(timezone.utc) - ferme < timedelta(hours=ATTENTE_COMPTE_H):
        return False
    o = _comptes_ordonnes_05(uid)
    if len(o) < 3:
        return False
    h = o[2]                                                            # le compte 2 de l'ordre « prive2 »
    etat = _derniers_etats.get(str(h).lower(), "")
    if onboarding._est_prive({"handle": h, "etat": etat}):
        return False
    return etat in ("warmup", "good")


def verifier_prive2(d: dict) -> list:
    """09/10 : les fiches « prive2 » à vérifier, pas encore signalées : [(uid, @ du compte 2, raison)] — son compte 2 publie
    (prive2_douteux), ou la fiche n'a pas d'étape 1 (ancien repris d'après le classeur et figé « prive2 » le 08/10, ou dates vidées
    par un remplacement : le plan les veut « prive3 »). 09/10 (revue : dans les deux ordres le privé est le MÊME @,
    _comptes_ordonnes_05()[2] ; repasser en « prive3 » ne changeait que son numéro, renumérotait un privé en cours de création, et
    bloquait sans fin un compte 3 en attente) : l'ordre n'est plus jamais changé ici. La fiche est notée (« prive2_alerte ») pour ne
    le dire qu'une fois ; reconcilier le dit au salon admin, Gaëtan tranche."""
    faits = []
    for uid, f in d.items():
        if not isinstance(f, dict) or f.get("ordre") != "prive2" or f.get("prive2_alerte") or ordre(f) != "prive2":
            continue
        dates = f.get("dates") or {}
        o = _comptes_ordonnes_05(uid)
        if len(o) < 3:
            continue
        if prive2_douteux(uid, f):
            raison = f" {_derniers_etats.get(str(o[2]).lower(), '').upper()} au classeur, il publie"
        elif not dates.get("1") and not dates.get("1_fait"):
            raison = ", parcours sans compte 1 (ancien repris ou remplacement)"
        else:
            continue
        f["prive2_alerte"] = _maintenant()
        faits.append((uid, o[2], raison))
    if faits:
        journal.warning("Ordre « prive2 » à vérifier (signalé, pas renuméroté) : %s", [u for u, _, _ in faits])
    return faits


def n_prive(fiche_p: dict) -> int:
    """Le numéro du compte privé (celui qui porte le lien) : 2, ou 3 pour les fiches d'avant le 08/10."""
    return 2 if ordre(fiche_p) == "prive2" else 3


def source_reels(fiche_p: dict, n: int) -> int:
    """Le compte dont les Reels ouvrent le compte n : le précédent, sauf s'il est privé (il ne publie pas) — alors celui d'avant
    (compte 3 en ordre « prive2 » : les Reels du compte 1)."""
    m = n - 1
    return m - 1 if m == n_prive(fiche_p) and m > 1 else m


def sources_reels(fiche_p: dict, n: int) -> list:
    """15/10 : quatre Reels vérifiés du compte précédent ; ancien privé en 2 à vérifier."""
    return [n - 1] if ordre(fiche_p) == "prive3" else []


def regle_comptes(fiche_p: dict = None) -> str:
    if fiche_p and ordre(fiche_p) == "prive2":
        return "Ancien ordre des comptes : vérification par le manager avant la suite."
    return ("Trois comptes créés au total, sans remplacement. Le compte 1 est disponible immédiatement. "
            "Les quatre premiers Reels publiés et vérifiés sur le compte 1 sont ton test opérationnel, après le quiz. "
            "Le compte 2 arrive dès que ces quatre Reels sont vérifiés. "
            "Le compte 3, privé, arrive après 4 Reels publiés et vérifiés sur le compte 2.")


def texte_codes() -> str:
    """01/10 (Gaëtan : « les codes Instagram se demandent uniquement dans le salon code-instagram ») : la phrase canonique,
    avec le salon en lien cliquable quand son id est connu."""
    # 01/10 (fusion des lots) : une seule source, codes_2fa.texte_salon_codes() (lot B) ; même texte, même lien.
    try:
        return codes_2fa.texte_salon_codes()
    except Exception:                                                   # noqa: BLE001
        return codes_2fa.TEXTE_CODE_BRUT                                # 11/10 (revue du lot W) : le bouton, plus « tape !code »


# 01/10 : plus de date ni de « compte 2 demain » ici, la règle canonique ; la date « au plus tôt » vit dans la ligne du matin
# 09/10 (Gaëtan : « Les clippeurs se font submerger d'informations sur leur salon privé. Améliore, simplifie, supprime, fluidifie,
# distribue connaissances et informations au compte-goutte afin d'éviter la surcharge… Chaque étape à la fois… Saute des lignes,
# aère ») : un message = une action, des paragraphes courts séparés par une ligne vide. La règle complète des comptes ({regle})
# n'est plus recollée au warm-up : elle arrive morceau par morceau, au moment où elle sert (« compte n peut publier »).
TEXTE_WARMUP = ("🔥 **Compte {n} : {h} h de warm-up.**\n\n"
                "Regarde des Reels, mets des likes, abonne-toi à 2 comptes. Pas de Reel.\n\n"
                "Je te dis ici quand il peut publier.")
# 10/10 (Gaëtan : « simplifier et supprimer toutes les étapes inutiles ») : un compte qui publie n'a plus de bouton « ✅ Profil fait » ;
# le warm-up est dit à la fin de son message de profil (profil.envoyer, `suite`), et l'étape se ferme au « ✅ Compte n créé ».
# TEXTE_WARMUP ne part plus que si ce profil n'a pas pu partir (compte repris d'un sortant, photo ou Discord en panne, fiche d'avant).
TEXTE_WARMUP_PROFIL = ("🔥 **Puis {h} h de warm-up.** Regarde des Reels, mets des likes, abonne-toi à 2 comptes. Pas de Reel.\n\n"
                       "Je te dis ici quand il peut publier.")
# 09/10 (Gaëtan : « Enlève le truc qui envoie un dossier Drive au clippeur, la qualité est pourrie ») : plus de Drive perso ; les
# vidéos d'ORIGINE de la créatrice ({videos} : onboarding.lien_drive_creatrice, sinon son salon ℹ️). Plus de demande WhatsApp ici :
# elle est faite au message de bienvenue.
TEXTE_PUBLIER = {1: ("✅ **Ton compte 1 peut publier : 2 Reels par jour.**\n\n"
                     "{videos}\n\n"
                     "Modifie chaque vidéo avant de la publier : musique, texte, un début qui accroche."),
                 2: "✅ **Ton compte 2 peut publier : 2 Reels par jour dessus aussi.**",   # 26/09 (Gaëtan) : 24 h de warm-up par compte
                 # 08/10 (privé en 2) : le compte 3 est le 2e compte de croissance ; il pointe vers le privé comme le compte 1
                 3: ("✅ **Ton compte 3 peut publier : 2 Reels par jour dessus aussi.**\n\n"
                     "Une fois : une story avec le widget de mention `@{cprive}`, puis mets-la à la une.\n\n"
                     "Pas de lien sur ce compte.")}
# 10/10 (revue du recrutement) : plus de « Un doute sur une vidéo ? Envoie-la ici avant » sous « compte 1 peut publier » (LIGNE_DOUTE
# retirée) : une action par message, et la relecture des Reels publiés reste (review_reels).
LIEN_REPORTING = os.environ.get("LIEN_REPORTING", "https://forms.gle/uhPewryox7R4jifv5").strip()   # formulaire du dimanche


def _identifiants(n: int) -> str:
    """Les secrets sont remis par le responsable, jamais dans le message automatique."""
    return f"Identifiant prévu : @{{compte{n}}}\n\nTon responsable te remet les accès personnellement."


ETAPES = {
    # 26/09 (Gaëtan) : textes courts, 24 h de warm-up sur chaque compte, puis les Reels.
    # 29/09 (Gaëtan) : « un compte tous les 48 h » — jamais plus vite, c'est ce qui limite les bans (7 comptes perdus le 28/09).
    # 09/10 (Gaëtan : « Chaque étape à la fois, on se complique pas la vie ») : la créatrice, ses vidéos et le WhatsApp sont donnés au
    # message de bienvenue ; l'étape 1 ne porte plus que le compte 1 (plus de ligne « Ta créatrice », plus de bouton ℹ️ ni WhatsApp).
    # {palier} : « 4 Reels vus… » quand c'est le palier qui ouvre le compte (rien si le staff le force) ; « icone » devant le titre.
    # 10/10 : plus de « Étape 1 · » dans le titre (aucune étape 2 ni 3 numérotée ne suit) : « 📱 Ton compte 1 »
    1: {"icone": "📱", "titre": "Croissance 1 · @{compte1}", "fiche": "1", "bouton": "✅ Compte 1 créé", "salons": [],
        "texte": _identifiants(1) + "\n\n{creation1}\n\nCréé ? Appuie sur ✅."},
    2: {"icone": "🎯", "titre": "{palier}Croissance 2 · @{compte2}", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": [],
        "texte": _identifiants(2) + "\n\n{creation2}\n\nCréé ? Appuie sur ✅."},
    # 05/10 (Gaëtan : « 2 comptes de croissance, story à la une qui mentionne le 3e compte privé avec le lien en bio ») : le
    # compte 3 est PRIVÉ, il ne publie pas ; son profil porte le lien ; les comptes 1 et 2 pointent vers lui.
    3: {"icone": "🔒", "titre": "{palier}Privé · @{compte3}", "fiche": "1", "bouton": "✅ Compte 3 créé", "salons": [],
        "texte": ("Il ne publie pas de Reel. Il porte ton lien personnel.\n\n" + _identifiants(3)
                  + "\n\n{creation3}\n\nCréé ? Appuie sur ✅.")},
    # 05/10 : étapes 4 et 5 supprimées du déroulé ; elles ne partent plus que par `!etape @x 4|5` du staff. 09/10 : sans Drive perso.
    4: {"titre": "Étape 4 · 24 h de warm-up sur le compte 3 (Fiche 2)", "fiche": "2", "bouton": "✅ Warm-up fini", "salons": ["ressources"],
        "texte": ("**Compte 3, pendant 24 h** : pas de Reel. 10 min de Reels, 5 likes, 2 abonnements, 1 story sans lien.\n\n"
                  "**{autres}** : 2 Reels par jour sur chacun, et 1 story par jour.\n\n"   # 01/10 : sans les BAN
                  "{videos}\n\n"
                  "Dans 24 h, le compte 3 publie aussi.")},
    5: {"titre": "Étape 5 · Tes Reels sur les 3 comptes (Fiche 3)", "fiche": "3", "bouton": "✅ Premier Reel publié", "salons": ["ressources"],
        "texte": ("{videos}\n\n"
                  "Modifie chaque vidéo avant de la publier : musique, texte, un début qui accroche.\n\n"
                  "Publie-la sur {vivants}. Jamais la même vidéo sur deux comptes le même jour.\n\n"   # 01/10 : sans les comptes BAN
                  "Premier Reel en ligne ? Appuie sur ✅.")},
    # 08/10 (audit) : les étapes 4 et 5 n'existent plus depuis le 05/10 ; le numéro interne reste 6 (fiches, boutons), le titre dit 4.
    # 09/10 : le lien est déjà dans le champ Liens du privé (message de profil) : l'étape se réduit à la story à la une, une fois.
    # {pointent_tes} et {pointent_court} : les comptes qui pointent vers le privé, selon l'ordre (« prive2 » : 1 et 3).
    # 09/10 (revue : un clipper repris à l'étape 6 d'après le classeur n'a jamais reçu le profil du privé, donc jamais son lien GAML) :
    # {ligne_lien} donne le lien quand le profil du privé n'est pas parti avec lui (LIGNE_LIEN, _contexte) ; vide sinon.
    # 10/10 : l'étape 6 n'est plus dans le déroulé (la story part sans bouton avec la routine, TEXTE_STORY) ; elle ne sert plus qu'à
    # `!etape @x 6`, au message du lien en ordre « prive2 » et aux fiches d'avant. Titre sans « Étape 4 · ».
    6: {"icone": "📌", "titre": "Ta story à la une", "fiche": "4", "bouton": "✅ Fait", "salons": [],
        "texte": ("{ligne_lien}"
                  "Sur {pointent_tes} : une story avec le widget de mention `@{cprive}`, puis mets-la à la une.\n\n"
                  "Une seule fois. Jamais de lien sur {pointent_court}.\n\n"
                  "Fait ? Appuie sur ✅.")},
    # 09/10 : la routine et l'app en UN message (livrer_app). {ligne_app} : vide si l'app ne peut pas partir avec (elle suit seule,
    # rattraper_app). 09/10 (Gaëtan) : la paie des clippers tombe les 5 et 20.
    # 10/10 : au « ✅ Profil fait » du privé, TEXTE_STORY part juste avant (valider_etape), sans bouton ; plus de suite à J+7.
    7: {"icone": "🎉", "titre": "Bravo, tes 3 comptes sont en place.", "fiche": "", "bouton": "", "salons": [],
        "texte": ("Chaque jour : 2 Reels sur {pointent_tes}, et 1 story avec le widget vers ta story à la une.\n\n"
                  "{ligne_app}"
                  "💸 Ta paie arrive ici les 5 et 20.\n\n"
                  "Une question ? Écris-la ici, je réponds.")},
}
LIGNE_APP = "📱 Ton app clipper te montre tes visites et tes gains, jour par jour. Garde-la en favori.\n\n"
LIGNE_LIEN = ("🔗 **Ton lien**, sur ton compte privé `{cprive}` : Modifier le profil → **Liens** → Ajouter un lien externe → colle :\n"
              "```\n{lien}\n```\n\n")
# 10/10 (revue du recrutement : « jusqu'à 10 Reels par jour » contredisait la règle 5 du formulaire, 2 Reels par jour, et le scan
# qui ne lit que les 12 derniers posts) : la suite de la routine à J+7 (TEXTE_ROUTINE2) est supprimée. 11/10 (lot W) : plus rien
# ne programme « routine2 » (ROUTINE2_JOURS et PARCOURS_ROUTINE2_JOURS retirés) ; programme_du_jour retire encore sans message les
# éléments « routine2 » des fiches d'avant le déploiement.
# 10/10 (Gaëtan : le 3e compte « avec le lien GAML + l'application de clippeur ») : au « ✅ Profil fait » du privé, la story à la une
# part sans bouton, juste avant la routine et l'app (étape 7). Plus d'étape 6 qui retenait l'app jusqu'à 24 h.
TEXTE_STORY = ("📌 **Une fois, maintenant : ta story à la une.**\n\n"
               "Sur {pointent_tes} : une story avec le widget de mention `@{cprive}`, puis mets-la à la une.\n\n"
               "Jamais de lien sur {pointent_court}.")
# 08/10 (privé en 2) : les étapes 2 et 3 de l'ordre « prive2 » — le compte 2 est le privé, le compte 3 le 2e compte de croissance.
ETAPES_PRIVE2 = {
    2: {"icone": "🔒", "titre": "{palier}Privé · @{compte2}", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": [],
        "texte": ("Il ne publie pas de Reel. Il porte ton lien personnel.\n\n" + _identifiants(2)
                  + "\n\n{creation2}\n\nTon compte 1 continue ses 2 Reels par jour.\n\nCréé ? Appuie sur ✅.")},
    3: {"icone": "🎯", "titre": "{palier}Croissance 2 · @{compte3}", "fiche": "1", "bouton": "✅ Compte 3 créé", "salons": [],
        "texte": (_identifiants(3) + "\n\n{creation3}\n\nIl publie, comme ton compte 1. Pas de lien dessus.\n\nCréé ? Appuie sur ✅.")},
}


def etape_def(fiche_p: dict, n: int) -> dict:
    """La définition de l'étape n pour CE clipper (titre, texte, bouton) selon l'ordre de ses comptes."""
    if ordre(fiche_p) == "prive2" and n in ETAPES_PRIVE2:
        return ETAPES_PRIVE2[n]
    return ETAPES[n]


def titre_etape(fiche_p: dict, n: int) -> str:
    """09/10 : le titre de l'étape n en clair (mémoire, assistant, `!etape`), sans le palier ni l'icône."""
    titre = re.sub(r" · @\{compte[123]\}", "", etape_def(fiche_p, n)["titre"])
    return titre.replace("{palier}", "").format_map(_Gabarit({"jours": WARMUP_JOURS}))


# Un compte déjà créé par le clipper se rejoint par connexion ; ce texte n'attribue aucun compte.
# 01/10 (Gaëtan : « les codes Instagram se demandent uniquement dans #🔐-code-instagram ») : plus de « écris !code ici » ni
# de « il arrive ici tout seul », la phrase canonique {codes} ; « il a déjà chauffé » retiré (24 h de warm-up quand même).
# 08/10 (audit : l'identifiant déjà pris est le blocage le plus courant à la création ; Mohamed a créé une variante que le bot ne
# connaissait pas) : la consigne et la commande `!pseudo n identifiant`, qui met le classeur et la fiche à jour.
# 09/10 : le bouton « Compte n créé » demande le @ exact (fenêtre ModalPseudo) ; `!pseudo` reste pour corriger après coup
PSEUDO_PRIS = "Identifiant déjà pris ? Ajoute un chiffre ou un point. Quand tu appuies sur ✅, je te demande ton @ exact."
# 09/10 (Gaëtan : « Saute des lignes, aère ») : une ligne vide entre chaque paragraphe ; la liste du compte 1 reste d'un bloc.
CREATION = ("1. Instagram → Créer un compte → avec cet e-mail.\n"
            "2. {codes}\n"
            "3. Utilise les accès prévus et l'identité réelle du titulaire. Un numéro demandé doit être autorisé pour ce compte.\n"
            "4. " + PSEUDO_PRIS.format(n=1),
            "Même chose que le compte 1, sur le même téléphone : tu ajoutes un compte, sans te déconnecter.\n\n"
            "⚠️ Instagram ne demande pas d'e-mail ? Arrête et écris-le ici.\n\n"
            "{codes}\n\n" + PSEUDO_PRIS.format(n=2),
            "Crée-le comme les autres, sur le même téléphone.\n\n"
            "{codes}\n\n" + PSEUDO_PRIS.format(n=3))
CONNEXION = ("Ce compte existe déjà.\n\n"
             "1. Instagram → Se connecter → cet identifiant et ce mot de passe.\n"
             "2. {codes}\n"
             "3. Utilise le moyen de vérification déjà lié au compte. Ne remplace pas son numéro ou son e-mail. "
             "Besoin d'aide ? `!aide-ig authentificateur`.",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter, sans te déconnecter du compte 1.\n\n{codes}",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter.\n\n{codes}")
RELANCE_JOURS = int(os.environ.get("PARCOURS_RELANCE_JOURS", "0") or 0)   # 05/10 (Gaëtan : « arrêter de polluer chaque salon privé ») : 0 = plus de relance ; 28/09 : 2
# 30/09 (Daniella) : « sur chaque compte… pas de Reel » contredisait l'étape 4 (comptes 1 et 2 publient déjà) — le warm-up du
# jour ne concerne que le compte 3.
# 01/10 (relecture) : « Comptes 1 et 2 » devient {autres}, les comptes vivants hors compte 3 (un compte BAN ne publie plus)
WARMUP_JOUR_TEXTE = ("🔥 **Warm-up du compte 3 : jour {j} sur {jours}.** Sur le compte 3 : 10 minutes de Reels, 5 likes, "
                     "2 abonnements, 1 story sans lien, pas de Reel. {autres} : 2 Reels et 1 story chacun, comme d'habitude.")


def configurer(deps: dict):
    global _deps
    _deps = deps
    # 09/10 (revue : on_ready n'enregistrait que BoutonEtape et BoutonWhatsApp ; discord.py n'enregistre un DynamicItem qu'à l'envoi
    # d'une vue, donc après chaque redémarrage le « ✅ C'est fait » d'une bienvenue déjà postée échouait) : les boutons persistants du
    # parcours, BoutonPret compris, sont enregistrés ici sur le client reçu (on_ready le passe déjà ; deux fois est sans effet)
    try:
        vues_persistantes(deps.get("client"))
    except Exception as erreur:                                         # noqa: BLE001 — sans client (tests, outils) : rien
        journal.info("Vues persistantes du parcours : %s", type(erreur).__name__)


def _onb(uid) -> dict:
    """La fiche d'onboarding du clipper (comptes, accès, lien, Drive), {} sans elle."""
    try:
        return (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(str(uid), {}) or {})
    except Exception:                                                   # noqa: BLE001
        return {}


def _comptes_ordonnes(uid, onb=None, fiche_p=None) -> list:
    """01/10 (bug de l'ordre : la boucle du classeur triait la liste, et chaque fonction relisait les comptes à sa façon —
    « ouvre ton compte 1 » avec l'identifiant du compte 2) : l'ordre unique compte 1, 2, 3, pour tout le module. L'ordre des
    accès livrés (fiche « acces ») fait foi, puis celui de la liste ; croissance d'abord, un identifiant de type privé en 3.
    08/10 (privé en 2) : en ordre « prive2 », le même privé passe en 2 et le 2e compte de croissance en 3."""
    if fiche_p is None:
        try:
            fiche_p = _lire().get(str(uid)) or {}
        except Exception:                                               # noqa: BLE001 — sans parcours : l'ordre du 05/10
            fiche_p = {}
    o = _comptes_ordonnes_05(uid, onb)
    if ordre(fiche_p) == "prive2" and len(o) >= 3:
        return [o[0], o[2], o[1]] + o[3:]
    return o


def _comptes_ordonnes_05(uid, onb=None) -> list:
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


def _reels_soir(fiche_p: dict, h: str) -> int:
    """08/10 (GO n° 2 du checkup) : les Reels vus par le scan du soir depuis celui du matin, valables le jour même seulement (le
    scan du lendemain matin les compte dans son passage, ils ne comptent jamais deux fois)."""
    e = (fiche_p.get("reels_soir") or {}).get(str(h).lower()) or {}
    return int(e.get("n") or 0) if e.get("jour") == datetime.now(timezone.utc).date().isoformat() else 0


def reels_vus(uid, fiche_p: dict, n: int) -> int:
    """Les Reels vus par le scan sur le compte n ; compte n BAN : sur tous ses comptes vivants déjà créés."""
    comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)
    suivis = fiche_p.get("reels") or {}
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    if h and not _est_ban(h, fiche_p):
        return int((suivis.get(h.lower()) or {}).get("vus", 0) or 0) + _reels_soir(fiche_p, h)
    return sum(int((suivis.get(x.lower()) or {}).get("vus", 0) or 0) for i, x in enumerate(comptes[:3], start=1)
               if _cree(fiche_p, i) and i != n_prive(fiche_p) and not _est_ban(x, fiche_p))   # 08/10 : jamais le privé


def _de_plus(fiche_p: dict, n: int, src: int = 1) -> str:
    return ""


def reels_detail(uid, fiche_p: dict, n: int) -> list:
    comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)
    suivis = fiche_p.get("reels") or {}
    return [(src, len(process_clippeur.cumuler_reels_verifies(
                suivis.get(comptes[src - 1].lower()) or {}, [], _date_creation(fiche_p, src), datetime.now(timezone.utc))))
            for src in sources_reels(fiche_p, n) if 0 < src <= len(comptes)]


def reels_pour(uid, fiche_p: dict, n: int) -> int:
    """Jamais de repli sur un autre compte ni sur des totaux glissants ambigus."""
    det = reels_detail(uid, fiche_p, n)
    return min((c for _, c in det), default=0)


def condition_texte(uid, fiche_p: dict, n: int, avec_compte: bool = True) -> str:
    """09/10 : la condition d'ouverture du compte n, dite au clipper : « 4 Reels sur ton compte 1 et 4 sur ton compte 2 (pour
    l'instant : 3 et 1) »."""
    det = reels_detail(uid, fiche_p, n) or [(source_reels(fiche_p, n), reels_pour(uid, fiche_p, n))]
    morceaux = [f"{REELS_OUVERTURE} Reels{_de_plus(fiche_p, n, src)} sur ton compte {src}" for src, _ in det]
    texte = " et ".join(morceaux)
    if avec_compte:
        texte += " (pour l'instant : " + " et ".join(f"{c} sur le compte {src}" for src, c in det) + ")"
    return texte


def _bloque_sources(uid, fiche_p: dict, n: int) -> int:
    """09/10 : le compte source BAN qui bloque l'ouverture du compte n (toutes ses sources BAN et aucun autre compte qui publie),
    0 sinon."""
    sources = sources_reels(fiche_p, n)
    if len(sources) > 1:
        # 09/10 (revue : un compte 2 BAN, même un faux BAN, ouvrait le privé sur les seuls Reels du compte 1) : le privé ne s'ouvre
        # que si les comptes 1 ET 2 publient ; l'un des deux BAN → bloqué, l'équipe prévenue (remplacement ou `!pseudo`)
        comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)
        for src in sources:
            h = comptes[src - 1] if 0 < src <= len(comptes) else ""
            if h and _est_ban(h, fiche_p):
                return src
        return 0
    if not all(_bloque_ban(uid, fiche_p, src) for src in sources):
        return 0
    return sources[0]


LIEN_BIO_H = int(os.environ.get("PARCOURS_LIEN_BIO_H", "24") or 24)   # délai laissé après la création du privé


def _cle_url(u) -> str:
    u = str(u or "").strip().lower().split("?")[0].split("#")[0]
    for prefixe in ("https://", "http://", "www."):
        u = u[len(prefixe):] if u.startswith(prefixe) else u
    return u.rstrip("/")


async def controler_liens_bio(client, bios: dict, maintenant=None) -> list:
    """08/10 (critique de complétude : « rien ne vérifie que le lien est dans la bio du compte privé », et le profil le faisait
    coller dans le texte de la bio, où il ne se clique pas) : après le scan du matin, pour chaque compte privé créé depuis
    LIEN_BIO_H heures et lu aujourd'hui par le scan (`bios` : {clé: {jour, liens, texte}}), le lien GAML du clipper est-il dans
    le champ « Liens » du profil ? Oui → noté (`lien_bio_ok`). Non → une ligne dans son salon (tous les 2 jours au plus) et une
    ligne au salon admin. Profil non lu (Apify) → rien conclu. Renvoie les lignes admin."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jour = maintenant.date().isoformat()
    d = _lire()
    a_dire, lignes = [], []
    for uid, f in d.items():
        if not isinstance(f, dict):
            continue
        np_ = n_prive(f)
        cree = _date_creation(f, np_)
        if cree is None and _cree(f, np_) and (f.get("dates") or {}).get("6"):
            # 09/10 (revue : un clipper repris à l'étape 6 d'après le classeur n'a pas de date de création du privé, il était sauté) :
            # son lien lui est donné à l'étape 6 ; on compte de là
            try:
                cree = datetime.fromisoformat(str(f["dates"]["6"]))
                cree = cree if cree.tzinfo else cree.replace(tzinfo=timezone.utc)
            except ValueError:
                cree = None
        if cree is None or maintenant - cree < timedelta(hours=LIEN_BIO_H):
            continue
        comptes = _comptes_ordonnes(uid, fiche_p=f)
        h = comptes[np_ - 1] if len(comptes) >= np_ else ""
        if not h or _est_ban(h, f):
            continue
        b = (bios or {}).get(onboarding.normaliser_handle(h).lower())
        if not b or b.get("jour") != jour:
            continue                                                    # pas lu aujourd'hui : on ne conclut rien
        lien, tous = _liens_gaml(uid, f.get("creatrice", ""))
        if not tous:
            continue
        cibles = {_cle_url(x) for x in tous}
        if any(_cle_url(x) in cibles for x in b.get("liens") or []):
            f["lien_bio_ok"] = jour
            f.pop("lien_bio_dit", None)
            continue
        dit = str(f.get("lien_bio_dit") or "")
        try:
            recent = bool(dit) and (maintenant.date() - datetime.fromisoformat(dit).date()).days < 2
        except ValueError:
            recent = False
        f.pop("lien_bio_ok", None)
        if recent:
            continue
        f["lien_bio_dit"] = jour
        a_dire.append((uid, f, h, lien, bool(b.get("texte")), bool(b.get("liens"))))
    _ecrire(d)                                                          # écrit AVANT les envois : jamais deux fois
    for uid, f, h, lien, texte, autre in a_dire:
        salon = client.get_channel(int(f.get("salon_id", 0) or 0)) if client is not None else None
        membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        pourquoi = ("Il est dans le texte de ta bio : là, il ne se clique pas." if texte else
                    "Le lien de ton profil n'est pas le tien." if autre else "Ton profil n'a pas encore de lien.")
        if salon is not None and membre is not None:
            try:
                await salon.send(f"🔗 {membre.mention} **Ton lien n'est pas sur ton compte privé** `{h}`. {pourquoi}\n\n"
                                 f"Modifier le profil → **Liens** → Ajouter un lien externe → colle :\n```\n{lien}\n```\n\n"   # 09/10 : aéré
                                 "Sans lui, tes Reels ne rapportent rien : c'est ce lien qui compte tes visites.")
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Lien en bio de %s : %s", uid, erreur)
        lignes.append(f"· {f.get('prenom') or uid} (<@{uid}>) : compte privé `{h}` sans son lien ({pourquoi.lower().rstrip('.')})")
    if lignes and _deps.get("canal_admin"):
        try:
            canal = await _deps["canal_admin"]()
            if canal is not None:
                await canal.send(("🔗 **Lien absent du compte privé** (scan du matin, prévenus dans leur salon)\n" + "\n".join(lignes))[:1900])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Liens en bio (admin) : %s", erreur)
    return lignes


def comptes_du_soir(maintenant=None) -> list:
    """08/10 (GO n° 2 du checkup : « un 2e scan Instagram à 19 h pour les seuls comptes en attente ») : les comptes dont les Reels
    ouvrent un compte en attente — ses 48 h passées ou finies avant le scan du lendemain matin — et qui n'ont pas encore leurs
    4 Reels. Quelques dizaines au plus : le seul coût du scan du soir."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for uid, f in _lire().items():
        a = attente(f) if isinstance(f, dict) else None
        if not a:
            continue
        quand = a[1] if a[1].tzinfo else a[1].replace(tzinfo=timezone.utc)
        if quand > maintenant + timedelta(hours=14) or reels_pour(uid, f, a[0]) >= REELS_OUVERTURE:
            continue
        comptes = _comptes_ordonnes(uid, fiche_p=f)
        for src in sources_reels(f, a[0]):                              # 09/10 : les comptes 1 et 2 pour le privé
            h = comptes[src - 1] if 0 < src <= len(comptes) else ""
            if h and not _est_ban(h, f) and h not in out:
                out.append(h)
    return out


def _apres(quand, depuis_iso: str) -> bool:
    try:
        q = datetime.fromisoformat(str(quand or "").replace("Z", "+00:00"))
        dep = datetime.fromisoformat(str(depuis_iso).replace("Z", "+00:00"))
    except ValueError:
        return False
    q = q if q.tzinfo else q.replace(tzinfo=timezone.utc)
    dep = dep if dep.tzinfo else dep.replace(tzinfo=timezone.utc)
    return q > dep


def noter_reels_soir(mesures: dict, depuis_iso: str, cle=None) -> int:
    """Retient dans chaque fiche en attente les Reels du compte source publiés après `depuis_iso` (le scan du matin), d'après le
    scan du soir (`mesures` : {clé: fiche du scanner}, avec la liste `reels` et leurs dates). Renvoie le nombre de fiches touchées."""
    cle = cle or (lambda h: onboarding.normaliser_handle(h).lower())
    jour = datetime.now(timezone.utc).date().isoformat()
    d = _lire()
    n = 0
    for uid, f in d.items():
        a = attente(f) if isinstance(f, dict) else None
        if not a:
            continue
        comptes = _comptes_ordonnes(uid, fiche_p=f)
        touche = False
        for src in sources_reels(f, a[0]):                              # 09/10 : toutes les sources (comptes 1 et 2 pour le privé)
            h = comptes[src - 1] if 0 < src <= len(comptes) else ""
            m = mesures.get(cle(h)) if h else None
            if not m or not m.get("lu", True) or not m.get("existe", True):
                continue
            nb = sum(1 for r in m.get("reels") or [] if _apres(r.get("quand"), depuis_iso))
            f.setdefault("reels_soir", {})[h.lower()] = {"jour": jour, "n": nb}
            touche = True
        n += int(touche)
    if n:
        _ecrire(d)
    return n


def _ou_publier(uid, fiche_p: dict, n: int) -> str:
    comptes = _comptes_ordonnes(uid)
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    return f"ton compte {n}" if (not h or not _est_ban(h, fiche_p)) else "tes autres comptes"


def _bloque_ban(uid, fiche_p: dict, n: int) -> bool:
    """01/10 (relecture : compte 1 BAN à l'étape 2, aucun autre compte créé — reels_vus restait à 0 pour toujours et la ligne
    du matin disait « tes autres comptes ») : le compte n est BAN et le clipper n'a aucun compte vivant déjà créé. Le parcours
    attend : c'est Gaëtan qui décide (`!etape` ou remplacement), aucune règle n'est inventée ici."""
    comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    if not h or not _est_ban(h, fiche_p):
        return False
    np_ = n_prive(fiche_p)                                              # 08/10 (revue) : le privé ne publie pas, il ne débloque rien
    return not any(_cree(fiche_p, i) and i != np_ and not _est_ban(x, fiche_p) for i, x in enumerate(comptes[:3], start=1))


def texte_bloque(n: int) -> str:
    """La ligne donnée au clipper bloqué par le BAN de son compte n (_bloque_ban)."""
    return f"Ton compte {n} est bloqué.\n\n" + codes_2fa.aide_instagram("suspension")


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


def _cle_creatrice(creatrice) -> str:
    """09/10 : la créatrice comparée sans accent ni casse, premier mot (« Chloé », « chloe », « Chloe ✨ » : la même)."""
    t = unicodedata.normalize("NFD", str(creatrice or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return (t.split() or [""])[0]


async def _lien_drive(creatrice: str) -> str:
    """09/10 (Gaëtan : « la qualité est pourrie ») : le lien des vidéos d'ORIGINE de la créatrice (onboarding.lien_drive_creatrice,
    lot L6 : le Drive de son salon ℹ️, sinon son dossier « 📁 Reels » d'origine) ; '' sans lien, ou avant la fusion de L6."""
    trouver = getattr(onboarding, "lien_drive_creatrice", None)
    if trouver is None or not creatrice:
        return ""
    try:
        return str(await asyncio.wait_for(trouver(creatrice), timeout=30) or "")
    except Exception as erreur:                                         # noqa: BLE001 — le texte renvoie alors au salon ℹ️
        journal.info("Vidéos d'origine de %s : %s", creatrice, type(erreur).__name__)
        return ""


async def _contexte(guild, uid: str, fiche_p: dict, drive: bool = False) -> dict:
    """Les valeurs des gabarits : comptes (handle + e-mail, croissance d'abord, privé en 3), lien, salons. 09/10 : `drive` : les
    vidéos d'origine de la créatrice ({drive}, {videos}, {videos_bienvenue}), cherchées seulement pour les messages qui les donnent."""
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
    ordonnes = _comptes_ordonnes(uid, onb, fiche_p)                     # 01/10 : le même ordre partout
    acces = {a.get("handle"): a for a in (onb.get("acces") or []) if isinstance(a, dict)}   # 27/09 : mot de passe et e-mail par compte
    for i in range(3):
        h = ordonnes[i] if i < len(ordonnes) else "?"
        ctx[f"compte{i + 1}"] = h
        # 09/10 (carte des comptes : « dans ton message de comptes plus haut » renvoyait à un message qui n'existe plus)
        ctx[f"mail{i + 1}"] = acces.get(h, {}).get("mail") or mails.get(h) or "(Gaëtan te le donne sur WhatsApp)"
        ctx[f"mdp{i + 1}"] = acces.get(h, {}).get("mdp") or mdps.get(h) or "(demande-le à Gaëtan sur WhatsApp)"
    vivants = _vivants(uid, fiche_p, ordonnes[:3], bans)
    np_ = n_prive(fiche_p)                                              # 08/10 : le compte privé, 2 (nouveaux) ou 3
    ctx["nprive"], ctx["cprive"] = np_, ctx[f"compte{np_}"]
    ctx["vivants"] = _liste(vivants)                                    # 01/10 : étapes 5 et 7 sans les comptes BAN
    ctx["autres"] = _liste([h for h in vivants if h != ctx["cprive"]])  # 01/10 (relecture) : étape 4, sans les BAN
    ctx["croissance"] = ctx["autres"]                                   # 05/10 : les comptes qui publient (pas le privé)
    if np_ == 2 and (_cree(fiche_p, 3) or int(fiche_p.get("etape", 0) or 0) >= 7):   # 09/10 : la routine, compte 3 créé
        ctx["pointent"], ctx["pointent_tes"], ctx["pointent_court"] = "ton compte 1 et ton compte 3", "tes comptes 1 et 3", "les comptes 1 et 3"
    elif np_ == 2:                                                      # le compte 3 n'existe pas encore quand le lien arrive
        ctx["pointent"] = "ton compte 1 (et ton compte 3 quand il arrive)"
        ctx["pointent_tes"] = ctx["pointent"]
        ctx["pointent_court"] = "les comptes 1 et 3"
    else:
        ctx["pointent"], ctx["pointent_court"] = "ton compte 1 et ton compte 2", "les comptes 1 et 2"
        ctx["pointent_tes"] = "tes comptes 1 et 2"                      # 09/10 : « Sur tes comptes 1 et 2 : une story… »
    ctx["codes"] = texte_codes()
    ctx["lien"] = onb.get("lien") or f"(il arrive ici dès que ton compte {np_} est prêt)"   # 05/10 : créé avec le compte privé
    ctx["ligne_lien"] = _rendre(LIGNE_LIEN, ctx) if onb.get("lien") and not lien_dans_profil(fiche_p) else ""   # 09/10 (revue)
    creatrice = ctx["creatrice"]
    info = _salon_info(guild, creatrice) if guild is not None else None
    ctx["info"] = f"<#{info.id}>" if info is not None else f"le salon d'infos de {creatrice}"
    # 09/10 (Gaëtan : « Enlève le truc qui envoie un dossier Drive au clippeur ») : plus de Drive perso (fiche « drive ») ; les vidéos
    # d'ORIGINE de la créatrice, sinon son salon ℹ️ (A1 : « Ses vidéos : dans le salon ℹ️ de {creatrice} »)
    ctx["drive"] = await _lien_drive(creatrice) if drive else ""
    salon_i = f"Ses vidéos : dans le salon ℹ️ de {creatrice}." + (f"\n<#{info.id}>" if info is not None else "")
    ctx["videos"] = f"Les vidéos de {creatrice} :\n<{ctx['drive']}>" if ctx["drive"] else salon_i
    ctx["videos_bienvenue"] = f"Ses vidéos, en qualité d'origine :\n<{ctx['drive']}>" if ctx["drive"] else salon_i
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


LIEN_PROFIL_DEPUIS = "2026-10-05T00:00:00+00:00"   # 05/10 : depuis ce jour, le profil du privé porte le lien (créé à l'ouverture de son étape)


def lien_dans_profil(fiche_p: dict) -> bool:
    """09/10 (revue) : le lien GAML est-il parti avec le profil du compte privé ? Non si le bot n'a jamais envoyé ce profil (parcours
    repris d'après le classeur, migré des étapes 4/5), s'il l'a envoyé sans lien (« lien_profil » vide, noté par valider_etape) ou
    avant le 05/10 (le profil ne portait pas encore le lien)."""
    f = fiche_p or {}
    envoye = (f.get("profils") or {}).get(str(n_prive(f)))
    if not envoye or str(envoye) < LIEN_PROFIL_DEPUIS:
        return False
    return not ("lien_profil" in f and not f.get("lien_profil"))


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

    def appui_creation(self, interaction) -> bool:
        """10/10 (vérification L10 : le même custom_id sert à « ✅ Compte n créé » et à « ✅ Profil fait ») : vrai si l'appui vient du
        bouton de création du compte n (étapes 1 à 3) et non du message de profil. Le message de profil se reconnaît à son id
        (messages["<n>p"] de la fiche), sinon au libellé « Profil »."""
        if self.etape not in (1, 2, 3):
            return False
        fiche_p = _lire().get(self.uid) or {}
        mid_profil = str((fiche_p.get("messages") or {}).get(f"{self.etape}p") or "")
        mid = str(getattr(getattr(interaction, "message", None), "id", "") or "")
        if mid and mid_profil and mid == mid_profil:
            return False
        return "profil" not in str(getattr(self.item, "label", "") or "").lower()

    async def callback(self, interaction: discord.Interaction):
        staff = _deps.get("est_staff")
        if str(interaction.user.id) != self.uid and not (staff and staff(interaction.user)):
            await interaction.response.send_message("Ce bouton est pour le clipper de ce salon 🙂", ephemeral=True)
            return
        # 09/10 (Gaëtan : « les clippeurs peuvent changer le @ légèrement quand il n'est pas disponible ») : au premier appui
        # « Compte n créé » du clipper, une fenêtre lui demande son @ exact, prérempli avec celui prévu.
        prevu = handle_a_confirmer(self.uid, self.etape) if str(interaction.user.id) == self.uid else ""
        if prevu:
            await interaction.response.send_modal(ModalPseudo(self.uid, self.etape, prevu))
            return
        await interaction.response.defer()
        if not await valider_etape(interaction.channel, self.uid, self.etape, par=str(interaction.user.id),
                                   creation=self.appui_creation(interaction)):
            # 01/10 (Steeve : un vieux bouton du compte 2 a rouvert le compte 2 pendant l'attente) : refusé, et on le dit
            try:
                await interaction.followup.send("Ce bouton n'est plus valable. Suis le dernier message de ton salon 🙂", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass


def handle_a_confirmer(uid: str, n: int) -> str:
    """09/10 : l'identifiant prévu du compte n si l'appui est celui de la création (étape n ouverte, profil pas encore envoyé) d'un
    compte à créer (pas un compte repris d'un sortant, qui existe déjà) ; '' sinon."""
    if n not in (1, 2, 3):
        return ""
    f = _lire().get(str(uid)) or {}
    if int(f.get("etape", 0) or 0) != n or not (f.get("dates") or {}).get(str(n)) or (f.get("profils") or {}).get(str(n)):
        return ""
    comptes = _comptes_ordonnes(uid, fiche_p=f)
    h = comptes[n - 1] if 0 < n <= len(comptes) else ""
    acces = {str(a.get("handle") or "").lower(): a for a in (_onb(uid).get("acces") or []) if isinstance(a, dict)}
    if not h or (acces.get(h.lower()) or {}).get("cree"):
        return ""
    return h


# 09/10 (Gaëtan a vu `!pseudo 1 ton_identifiant` accepté : le clipper recopiait l'exemple du bot, son compte 1 devenait introuvable
# puis BAN) : les mots d'exemple sont refusés, et les textes montrent un exemple réaliste, lui-même refusé s'il est recopié.
EXEMPLE_PSEUDO = "sarah.clips22"
_MOTS_EXEMPLE = {"ton_identifiant", "identifiant", "nouvel_identifiant", "mon_identifiant", "ton_", "ton", "pseudo", "handle",
                 "exemple", "nouveau", "username", EXEMPLE_PSEUDO}
RAISON_EXEMPLE = "écris le vrai @ de ton compte"


def est_exemple(handle: str) -> bool:
    """09/10 : un @ recopié d'un texte d'exemple (ton_identifiant, ton_@, pseudo, sarah.clips22…), jamais un vrai compte."""
    h = re.sub(r"[<>@\s`]", "", str(handle or "").lower())
    return h in _MOTS_EXEMPLE or h.startswith(("ton_", "nouvel_")) or "identifiant" in h


async def renommer(uid: str, n: int, nouveau: str) -> tuple:
    """09/10 : le compte n du clipper passe à `nouveau` (classeur, fiche d'onboarding, Reels suivis). Renvoie (ancien, raison) :
    raison '' si c'est fait. Commun à `!pseudo`, à la fenêtre de création et au scan qui retrouve un compte."""
    comptes = _comptes_ordonnes(uid)
    if n < 1 or n > len(comptes) or not comptes[n - 1]:
        return "", f"pas de compte {n} pour toi"
    ancien = comptes[n - 1]
    if est_exemple(nouveau):
        return ancien, RAISON_EXEMPLE
    nouveau = onboarding.normaliser_handle(nouveau).lower()
    # 09/10 (le même @ pour les comptes 1 et 2 d'un clipper) : jamais le @ d'un AUTRE de ses comptes, contrôle local et immédiat
    for k, h in enumerate(comptes, start=1):
        if k != n and h and onboarding.normaliser_handle(h).lower() == nouveau:
            return ancien, f"c'est déjà ton compte {k}"
    if n != n_prive(_lire().get(str(uid)) or {}) and onboarding.RE_PRIVE.search(nouveau):
        return ancien, "ce nom ressemble à un compte privé (priv, secret, perso) : choisis-en un autre"
    try:
        raison = await onboarding.renommer_compte(uid, ancien, nouveau)
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Renommage du compte %s de %s : %s", n, uid, erreur)
        raison = "le classeur ne répond pas, réessaie dans une minute"
    if raison:
        return ancien, raison
    d = _lire()                                                         # les Reels déjà vus suivent le compte
    f = d.get(str(uid)) or {}
    for cle in ("reels", "reels_soir"):
        suivis = f.get(cle) or {}
        if ancien.lower() in suivis:
            suivis[nouveau] = suivis.pop(ancien.lower())
    if str(uid) in d:
        _ecrire(d)
    try:
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal is not None:
            await canal.send(f"✏️ {f.get('prenom') or uid} : compte {n} `{ancien}` → `{nouveau}` (identifiant prévu pris, classeur mis à jour)")
    except Exception:                                                   # noqa: BLE001
        pass
    return ancien, ""


def proprietaire(handle: str) -> tuple:
    """09/10 : (uid, n) du clipper à qui ce compte est livré (fiche d'onboarding), n = son numéro de compte ; ('', 0) sinon."""
    cle = onboarding.normaliser_handle(handle).lower()
    try:
        clippers = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {})
    except Exception:                                                   # noqa: BLE001
        return "", 0
    for uid, onb in clippers.items():
        comptes = [onboarding.normaliser_handle(h).lower() for h in _comptes_ordonnes(uid, onb)]
        if cle in comptes:
            return str(uid), comptes.index(cle) + 1
    return "", 0


async def _dire_au_clipper(client, uid: str, texte: str) -> bool:
    f = _lire().get(str(uid)) or {}
    salon = client.get_channel(int(f.get("salon_id", 0) or 0)) if (client is not None and f.get("salon_id")) else None
    if salon is None and _deps.get("salon_perso"):
        salon = _deps["salon_perso"](str(uid))
    if salon is None:
        return False
    try:
        await salon.send(f"<@{uid}> {texte}")
        return True
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Message @ changé pour %s : %s", uid, erreur)
        return False


RAISONS_PASSAGERES = ("le classeur est indisponible", "le classeur ne répond pas", "je ne trouve pas ce compte dans le classeur")


async def compte_retrouve(client, ancien: str, nouveau: str):
    """09/10 : le scan a retrouvé le compte sous un @ proche (nom et bio du bot) → renommé partout, le clipper est prévenu.
    10/10 (dashboard, lot SCAN passe 3, M1 : un refus définitif était retenté à chaque passage, Apify payé à chaque fois, la ligne
    jamais BAN) : True si renommé ; False si refusé pour de bon (compte hors fiche, @ d'un autre compte, @ refusé) ; None si le
    classeur n'a pas répondu (RAISONS_PASSAGERES : à retenter au passage suivant). None et False restent faux pour un `bool()`."""
    uid, n = proprietaire(ancien)
    if not uid:
        return False
    deja, k = proprietaire(nouveau)
    if deja:
        # 09/10 (le même @ pour les comptes 1 et 2 : le scan retrouvait le compte 2 sous le @ du compte 1, nom et bio étant les mêmes
        # pour tous les comptes d'une créatrice) : un @ déjà dans une fiche n'est jamais proposé
        journal.warning("Compte retrouvé %s → %s pour %s ignoré : %s est déjà le compte %s de %s", ancien, nouveau, uid, nouveau, k, deja)
        return False
    _, raison = await renommer(uid, n, nouveau)
    if raison:
        journal.warning("Compte retrouvé %s → %s pour %s non renommé : %s", ancien, nouveau, uid, raison)
        return None if any(str(raison).startswith(r) for r in RAISONS_PASSAGERES) else False
    await _dire_au_clipper(client, uid, f"🔎 J'ai trouvé ton compte {n} sous `{nouveau}`. Le @ prévu, `{ancien}`, était pris.\n\n"
                                        f"Ce n'est pas le tien ? Tape `!pseudo {n}` puis ton vrai @.")
    return True


def _introuvable_jours() -> int:
    try:
        import etats_comptes
        return int(etats_comptes.INTROUVABLE_JOURS)
    except Exception:                                                   # noqa: BLE001
        return 3


async def compte_introuvable(client, handle: str) -> bool:
    """09/10 : un compte marqué créé que le scan ne voit pas, ni sous un @ proche → le clipper donne son @ (une fois par compte)."""
    uid, n = proprietaire(handle)
    if not uid:
        return False
    d = _lire()
    f = d.get(uid)
    cle = onboarding.normaliser_handle(handle).lower()
    if f is not None:
        if (f.get("introuvables") or {}).get(cle):
            return False
        f.setdefault("introuvables", {})[cle] = _maintenant()
        _ecrire(d)
    # 09/10 : plus de « ton_@ » à recopier, plus de renvoi vers #assistant (le clipper écrit dans son salon)
    ok = await _dire_au_clipper(client, uid, f"🔎 Je ne trouve pas ton compte {n} `{handle}` sur Instagram.\n\n"
                                             f"Tu as pris un autre @ ? Tape `!pseudo {n}` puis ton vrai @.\n\n"
                                             "Il est bloqué ? Écris-le ici.")
    try:
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal is not None:
            await canal.send(f"🔎 {(f or {}).get('prenom') or uid} (<@{uid}>) : compte {n} `{handle}` introuvable, ni sous un @ proche "
                             f"({'prévenu' if ok else 'pas prévenu'}) ; BAN après {_introuvable_jours()} passages sans le voir depuis sa création.")
    except Exception:                                                   # noqa: BLE001
        pass
    return ok


def _prevu_pris(handle: str) -> bool:
    """09/10 (revue) : le scan a vu ce @ exister sur Instagram avant que le clipper le crée (`pris_signales`)."""
    try:
        import etats_comptes
        return onboarding.normaliser_handle(handle).lower() in (etats_comptes._lire().get("pris_signales") or {})
    except Exception:                                                   # noqa: BLE001
        return False


class ModalPseudo(discord.ui.Modal):
    """09/10 : « Ton compte n est créé ? Ton @ exact » — prérempli avec l'identifiant prévu ; un @ légèrement changé (pris sur
    Instagram) met à jour le classeur et la fiche avant de fermer l'étape."""

    def __init__(self, uid: str, n: int, prevu: str):
        super().__init__(title=f"Ton compte {n} est créé ?", timeout=600)
        self.uid, self.n, self.prevu = str(uid), int(n), prevu
        # 09/10 (revue) : le @ prévu existait déjà sur Instagram avant sa création (compte d'un inconnu ?) → pas prérempli, sinon le
        # clipper confirme sans lire et le scan suit le compte de l'inconnu
        pris = _prevu_pris(prevu)
        self.champ = discord.ui.TextInput(label="Ton @ exact. Le @ prévu semble déjà pris." if pris else "Ton @ Instagram exact (sans le @)",
                                          default=None if pris else prevu, min_length=1, max_length=30,
                                          placeholder="Le @ que tu as créé" if pris else "Si le @ prévu était pris, celui que tu as choisi")
        self.add_item(self.champ)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        brut = str(self.champ.value or "").strip()
        saisi = onboarding.normaliser_handle(brut).lower()
        if not saisi or len(brut.split()) > 1 or not onboarding.RE_HANDLE_IG.match(saisi):
            try:                                                        # une phrase ou des signes : on ne devine jamais un @
                await interaction.followup.send("❌ Écris seulement ton @ (lettres, chiffres, point, tiret bas), puis réappuie sur le "
                                                "bouton.", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass
            return
        if saisi != self.prevu.lower():
            _, raison = await renommer(self.uid, self.n, saisi)
            if raison:
                try:                                                    # 09/10 : « ❌ Écris le vrai @… », « ❌ C'est déjà ton compte 1 »
                    await interaction.followup.send(f"❌ {raison[:1].upper()}{raison[1:]}. Réappuie sur ✅ avec ton @ exact.",
                                                    ephemeral=True)
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return
            try:
                await interaction.followup.send(f"✅ Noté : ton compte {self.n} est `{saisi}`. Je le suis sous ce nom.", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass
        if not await valider_etape(interaction.channel, self.uid, self.n, par=self.uid, creation=True):
            try:
                await interaction.followup.send("Ce bouton n'est plus valable. Suis le dernier message de ton salon 🙂", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass


def _vue(guild, uid: str, n: int, ctx: dict, fiche_p: dict = None):
    vue = discord.ui.View(timeout=None)
    e = etape_def(fiche_p if fiche_p is not None else (_lire().get(str(uid)) or {}), n)
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
    # 09/10 (Gaëtan : « simplifie, supprime ») : plus de bouton WhatsApp sous chaque étape ; il est au message de bienvenue, une fois
    return vue


# 10/10 (revue du recrutement, lot L3 : le stock de lignes est le goulot) : le compte 2 ou 3 dont la fiche n'a pas encore la ligne
# (ATTRIBUTION_LIGNES_MIN sous 3, ou classeur à court à l'arrivée) la réserve à l'ouverture de son étape. Sans ligne libre : rien
# au compte suivant, un message au clipper et une ligne à l'admin, une fois, et un nouvel essai au tour suivant du programme.
# 11/10 (vérification : « Rien à faire d'ici là » contredisait les 2 Reels par jour sur ses comptes déjà ouverts)
TEXTE_COMPTE_ATTENDU = "⏳ Ton compte {n} arrive dès qu'il est prêt.\n\nD'ici là, continue tes 2 Reels par jour."
# 11/10 (revue du lot W : stock vide ou classeur en panne pendant livrer, le compte 1 partait avec l'identifiant « ? ») : le compte 1
# passe aussi par _ligne_du_compte ; il n'a encore aucun compte qui publie, donc pas de « 2 Reels par jour ».
TEXTE_COMPTE_1_ATTENDU = "⏳ Ton compte 1 arrive ici dès qu'il est prêt.\n\nRien à faire d'ici là : je te préviens ici."
# 11/10 (lot W) : ce que l'assistant et `!memoire` disent du même compte (etat_des_comptes, contexte_court)
TEXTE_ATTENTE_LIGNE = ("pas encore ouvert : il attend une ligne libre du classeur et arrive tout seul dès qu'il est prêt ; rien à "
                       "faire d'ici là, sauf 2 Reels par jour sur ses comptes qui publient")


TEXTE_ATTENTE_LIGNE_1 = ("pas encore ouvert : il attend une ligne libre du classeur et arrive tout seul dans son salon dès qu'il est "
                         "prêt ; rien à faire d'ici là, pas de compte à créer")


def _compte_1_retenu(fiche_p: dict) -> bool:
    """11/10 (revue du lot W) : le compte 1 n'est pas parti faute de ligne libre (envoyer_etape l'a retenu)."""
    f = fiche_p or {}
    return (int(f.get("etape", 0) or 0) == 1 and int(f.get("ligne_attendue") or 0) == 1
            and not (f.get("dates") or {}).get("1"))


async def _ligne_du_compte(salon, membre, uid: str, n: int) -> bool:
    """Vrai : la fiche d'onboarding a la ligne du compte n, ou elle vient d'être réservée (onboarding.reserver_compte : Gérant, fiche,
    alias 2FA) — l'étape peut partir. Faux : l'étape n'est pas envoyée et reste au programme (nouvel essai au tour suivant) ; sans
    ligne libre, le clipper (TEXTE_COMPTE_ATTENDU) et l'admin (« Plus de ligne libre chez Y ») sont prévenus UNE fois par compte
    attendu (clé « ligne_attendue » de la fiche, écrite avant l'envoi) ; classeur illisible : rien de dit, nouvel essai. Classeur
    éteint : vrai, comme avant (l'étape part avec ce que la fiche a)."""
    if not onboarding.actif():
        return True
    tient = len([h for h in _onb(uid).get("comptes") or [] if h])
    fiche_p = _lire().get(uid) or {}
    manque = False
    if tient < n:
        creatrice = fiche_p.get("creatrice") or _onb(uid).get("creatrice") or ""
        try:
            for i in range(tient + 1, n + 1):                           # le compte n (et un compte d'avant resté sans ligne)
                if await onboarding.reserver_compte(membre, creatrice, i, salon=salon, prive=i == n_prive(fiche_p)) is None:
                    manque = True
                    break
        except Exception as erreur:                                     # noqa: BLE001 — classeur illisible : on réessaie
            journal.warning("Ligne du compte %s de %s : %s, nouvel essai au tour suivant", n, uid, erreur)
            _garder_au_programme(uid, n)
            return False
    if not manque:
        d = _lire()
        if uid in d and d[uid].pop("ligne_attendue", None) is not None:
            _ecrire(d)
        return True
    dire = _garder_au_programme(uid, n, noter=True)
    if not dire:
        return False
    prenom = fiche_p.get("prenom") or _prenom(membre)
    creatrice = fiche_p.get("creatrice") or "sa créatrice"
    try:
        await _suite(salon, f"{membre.mention} " + (TEXTE_COMPTE_1_ATTENDU if n == 1 else TEXTE_COMPTE_ATTENDU.format(n=n)))
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Compte %s attendu de %s : %s", n, uid, erreur)
    try:
        canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
        if canal is not None:
            await canal.send(f"📦 Plus de ligne libre chez {creatrice} : {prenom} (<@{uid}>) attend son compte {n}. "
                             "Crée une ligne (Build capacity).")
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Ligne admin du compte %s attendu de %s : %s", n, uid, erreur)
    return False


# 11/10 (lot W, contre-vérifications des lots L1 et L3 : l'élément « ligne » remis échu tout de suite était retenté à chaque tour
# léger de 10 min, soit 6 lectures du classeur des logins par heure et par clipper en attente) : sans ligne libre, le nouvel essai
# a lieu LIGNE_REESSAI_MIN minutes plus tard. Le compte part au plus 40 min après qu'une ligne se libère : 30 min, plus un tour léger
# de 10 min (PARCOURS_TICK_MIN) ; `!etape @x n` : tout de suite (revue du lot W : « au plus 30 min » était faux). Classeur illisible : nouvel essai au tour suivant, comme avant.
LIGNE_REESSAI_MIN = max(1, int(os.environ.get("PARCOURS_LIGNE_REESSAI_MIN", "30") or 30))


def _garder_au_programme(uid: str, n: int, noter: bool = False) -> bool:
    """L'étape n n'est pas partie : elle redevient l'étape attendue (pas de date « n », l'étape pointée sur n) et reste au programme,
    échue tout de suite si le classeur était illisible (le tour suivant la retente), LIGNE_REESSAI_MIN minutes plus tard s'il n'y
    avait pas de ligne libre (`noter`). `noter` : pose « ligne_attendue » = n ; vrai seulement si elle n'y était pas
    (le message et la ligne admin partent alors, une seule fois).
    11/10 (vérification : `!etape @x 3` forcé sans ligne retombait derrière les 4 Reels que le staff voulait sauter) : l'élément
    remis au programme est marqué « ligne » — il avait passé la règle des Reels, ou le staff l'a forcé ; _programme_du_jour le fait
    partir sans la retester, dès que la ligne existe. Un élément « etape n » encore en attente (48 h, Reels) est remplacé par lui."""
    d = _lire()
    f = d.get(uid)
    if f is None:
        return False
    f.setdefault("dates", {}).pop(str(n), None)                         # forcer_etape l'avait datée : rien n'est parti
    f["etape"] = n
    f["programme"] = [x for x in f.get("programme") or [] if not (x.get("type") == "etape" and int(x.get("n") or 0) == n)]
    quand = _maintenant() if not noter else \
        (datetime.now(timezone.utc) + timedelta(minutes=LIGNE_REESSAI_MIN)).isoformat(timespec="seconds")
    f["programme"].append({"quand": quand, "type": "etape", "n": n, "ligne": True})
    nouveau = noter and f.get("ligne_attendue") != n
    if nouveau:
        f["ligne_attendue"] = n
    _ecrire(d)
    return nouveau


# ------------------------------------------------------------------ déroulé
async def envoyer_etape(salon, membre, n: int, pointer: bool = True) -> bool:
    """Envoie l'étape n et en fait l'étape en cours (`pointer=False` : 08/10, le message du lien envoyé à côté du parcours, en
    ordre « prive2 », pendant que le compte 3 attend). 10/10 (lot L3) : les comptes 2 et 3 réservent leur ligne ici si la fiche ne
    l'a pas (_ligne_du_compte) ; sans ligne libre, rien n'est envoyé et l'étape reste au programme.
    11/10 (vérification du lot L3 : un compte 3 retenu faute de ligne était compté « ouvert » par _programme_du_jour, puis annoncé
    chaque soir au salon admin par le scan) : renvoie True quand l'étape est partie, False quand elle est retenue (pas de ligne,
    classeur illisible) ou que le salon refuse le message."""
    uid = str(membre.id)
    fiche_avant = _lire().get(uid) or {}
    if n == 1 and pointer and (fiche_avant.get("messages") or {}).get("1"):
        return True
    if n in (2, 3) and not (fiche_avant.get("messages") or {}).get(str(n)) and reels_pour(uid, fiche_avant, n) < REELS_OUVERTURE:
        return False
    if n >= 2:                                                          # 08/10 : l'ordre des comptes est figé ici, pour de bon (revue : dès 2)
        d = _lire()
        if uid in d:
            # 09/10 (revue) : plus de bascule ici sur un compte 2 qui publie (même @ privé, autre numéro) : verifier_prive2 le signale
            o_ = ordre(d[uid])
            if d[uid].get("ordre") != o_:                               # 09/10 : un « prive2 » pas encore ouvert repasse en « prive3 »
                d[uid]["ordre"] = o_
                _ecrire(d)
    # 10/10 (revue du recrutement, lot L3) : la ligne du compte 2 ou 3 d'abord (réservée ici si la fiche ne l'a pas) ; sans ligne libre,
    # rien au compte suivant (ni lien GAML pris sur le forfait) : l'étape reste au programme, le clipper et l'admin sont prévenus une fois
    # 11/10 (revue du lot W) : le compte 1 aussi — sans ligne (stock vide, `!creatrice` sur une créatrice sans place, classeur en
    # panne pendant livrer), il partait avec l'identifiant « ? » et « demande-le à Gaëtan sur WhatsApp », sans nouvel essai.
    if n in (1, 2, 3) and pointer and not await _ligne_du_compte(salon, membre, uid, n):
        return False
    if n in (1, 2, 3) and not (fiche_avant.get("messages") or {}).get(str(n)):
        handles = _comptes_ordonnes(uid, fiche_p=fiche_avant)
        if len(handles) < n:
            return False
        handle = handles[n - 1]
        try:
            onboarding.process_adapters.store().reserve(uid, [handle])
            preuves = onboarding._deps["lire_json"](
                onboarding._deps["FICHIER_ONBOARDING"].parent / "process_pseudos.json", {})
            if not process_clippeur.pseudo_disponible(preuves.get(handle.lower()) or {}, datetime.now(timezone.utc)):
                _garder_au_programme(uid, n, noter=True)
                journal.warning("Compte retenu : disponibilité Instagram non prouvée")
                return False
        except RuntimeError:
            _garder_au_programme(uid, n, noter=True)
            return False
    if (n == 6 or n == n_prive(_lire().get(uid) or {})) and _deps.get("attribuer_lien"):
        # 05/10 (Gaëtan : « le lien que pour le troisième compte ») : le lien GAML n'existe pas avant le compte privé ; il est créé
        # (ou repris) à l'ouverture de son étape, pour être dans sa bio dès son profil, puis donné à l'étape 6. 08/10 : le compte
        # privé est le 2 pour les nouveaux parcours.
        try:
            await _deps["attribuer_lien"](membre)
        except Exception as erreur:                                     # noqa: BLE001 — sans lien, l'étape part quand même
            journal.warning("Lien GAML pour %s à l'étape %s : %s", uid, n, erreur)
            return False
    if n in (n_prive(_lire().get(uid) or {}), 6, 7) and not _onb(uid).get("liens_prets"):
        return False  # Ne pas livrer le privé ou l’app sans lien préparé.
    # 01/10 (relecture : deux programme_du_jour à 50 ms d'écart, le clipper 2 a reçu deux fois « Étape 2 ») : la fiche était
    # lue, puis réécrite après l'appel au classeur (_contexte) et l'envoi — elle écrasait ce qui avait été écrit entre-temps.
    # Le contexte d'abord ; la fiche relue après l'attente, posée et écrite sans attente ; relue encore pour l'id du message.
    ctx = await _contexte(getattr(salon, "guild", None), uid, _lire().get(uid) or {"prenom": _prenom(membre)}, drive=n in (1, 4, 5))
    d = _lire()
    fiche_p = d.setdefault(uid, {"prenom": _prenom(membre),
                                 "creatrice": "", "salon_id": str(salon.id), "etape": n, "dates": {}, "notes": []})
    if pointer:
        fiche_p["etape"] = n
    fiche_p["salon_id"] = str(salon.id)
    fiche_p.setdefault("dates", {})[str(n)] = _maintenant()
    if n == 1:
        # 09/10 : le compte 1 est donné (clic sur ✅, programme de 3 h ou `!etape` du staff) : la bienvenue est close, une seule fois
        fiche_p["bienvenue_ok"] = fiche_p.get("bienvenue_ok") or _maintenant()
        fiche_p["programme"] = [x for x in fiche_p.get("programme") or [] if not (x.get("type") == "etape" and int(x.get("n") or 0) == 1)]
    # 10/10 (revue du recrutement : la routine J+7, « jusqu'à 10 Reels par jour », contredit la règle des 2 Reels par jour) : plus de
    # « routine2 » programmée ici (ni dans demarrer_routine depuis le 11/10)
    _ecrire(d)
    if n == 1:
        await _retirer_pret(salon, uid, fiche_p)
    if n == 7:                                                          # 09/10 : la routine et l'app, en UN message
        await _envoyer_routine(salon, membre, uid, ctx)
        return True
    e = etape_def(fiche_p, n)
    ctx["palier"] = ""
    if n in (2, 3):
        # 09/10 : « 🎯 4 Reels vus sur ton compte 1. Voici ton compte 2. » — seulement quand ce sont bien les Reels qui l'ouvrent
        try:
            if reels_pour(uid, fiche_p, n) >= REELS_OUVERTURE:
                ctx["palier"] = f"{REELS_OUVERTURE} Reels vus" + (" sur ton compte 1" if n == 2 else "") + ". "
        except Exception as erreur:                                     # noqa: BLE001 — le titre sans le palier
            journal.info("Palier du compte %s de %s : %s", n, uid, erreur)
    icone = f"{e['icone']} " if e.get("icone") else ""
    texte = f"{membre.mention} {icone}**{_rendre(e['titre'], ctx)}**\n\n{_rendre(e['texte'], ctx)}"
    if n == 1 and fiche_p.get("accueil_unique") and not (fiche_p.get("messages") or {}).get("bienvenue"):
        ctx["prenom"] = _prenom_affiche(ctx.get("prenom", ""))
        gabarit = TEXTE_CREATRICE_LA if _a_attendu(uid) else TEXTE_BIENVENUE
        texte = f"{membre.mention} " + _rendre(gabarit, ctx) + "\n\n" + texte.removeprefix(f"{membre.mention} ")
    if n == 5:                                                          # 01/10 : il publie sur ses comptes, la relecture est proposée
        texte += _ligne_review(uid)
    try:
        vue = _vue(getattr(salon, "guild", None), uid, n, ctx, fiche_p)
        if n == 1 and not (fiche_avant.get("messages") or {}).get("1"):
            import process_livraison
            msg = await process_livraison.envoyer_compte_1(onboarding.process_adapters.store(), salon, uid, texte[:1990], vue)
        else:
            msg = await salon.send(texte[:1990], view=vue)
    except (discord.HTTPException, TimeoutError, OSError, RuntimeError) as erreur:
        journal.warning("Étape %s pour %s retenue : %s", n, uid, type(erreur).__name__)
        reprise = _lire()
        if uid in reprise and not (fiche_avant.get("dates") or {}).get(str(n)):
            reprise[uid].setdefault("dates", {}).pop(str(n), None)
            _ecrire(reprise)
        if n == 1:
            _garder_au_programme(uid, 1, noter=True)
        return False
    d = _lire()
    if uid in d:
        d[uid].setdefault("messages", {})[str(n)] = str(msg.id)
        if n == 1 and d[uid].get("accueil_unique"):
            d[uid]["messages"].setdefault("bienvenue", str(msg.id))
        _ecrire(d)
    return True


# 16/10 : un seul accueil, fusionné avec Croissance 1 ; aucune confirmation WhatsApp requise.
# Le programme reste un filet de reprise lorsque le membre ou le stock est indisponible.
BIENVENUE_H = int(os.environ.get("PARCOURS_BIENVENUE_H", "1") or 1)
TEXTE_BIENVENUE = ("🎉 **Bienvenue, {prenom} !**\n\n"
                   "Ta créatrice : **{creatrice}**.\n\n"
                   "{videos_bienvenue}\n\n"
                   "Une question ? Réponds ici, dans ton salon personnel.")
# 10/10 (vérification L10 : deux « 🎉 Bienvenue dans l'agence » à la suite) : un clipper qui a déjà reçu le repli d'attente (« Ta
# créatrice arrive ici dès qu'un compte est prêt pour toi ») lit « Ta créatrice est là », pas une seconde bienvenue.
TEXTE_CREATRICE_LA = TEXTE_BIENVENUE.replace("🎉 **Bienvenue, {prenom} !**", "🎉 **Ta créatrice est là, {prenom} !**", 1)


def _a_attendu(uid) -> bool:
    """10/10 : vrai si le membre est passé par l'attente d'une créatrice (repli reçu, attente datée), d'après le pipeline."""
    if not (_deps.get("lire_json") and _deps.get("FICHIER_PIPELINE")):
        return False
    try:
        info = ((_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}) or {}).get("etats") or {}).get(str(uid)) or {}
    except Exception:                                                   # noqa: BLE001
        return False
    return bool(info.get("attente_fin") or info.get("repli_attente") or info.get("attente_depuis"))


def _prenom_affiche(prenom: str) -> str:
    """10/10 : « Andry2 » (pseudo distinct d'un homonyme, bot_discord.prenom_distinct) s'affiche « Andry » dans la bienvenue."""
    p = str(prenom or "")
    court = re.sub(r"(?<=[^\W\d_])\d+$", "", p)
    return court or p


def lien_whatsapp_groupe(uid, fiche_p: dict = None) -> str:
    """09/10 (A6) : le bouton WhatsApp du message de bienvenue. Aucun lien d'invitation de groupe par créatrice n'est connu du code
    (ni variable WHATSAPP_*, ni lien chat.whatsapp.com) : c'est le message déjà écrit à Gaëtan, « pour qu'il t'ajoute au groupe »."""
    return lien_whatsapp_prerempli(uid, fiche_p, groupe=True)


def _vue_bienvenue(uid: str, fiche_p: dict = None, avec_pret: bool = False):
    """Les anciennes confirmations restent lisibles, sans nouvelle demande d'arrivée."""
    return None


async def _retirer_pret(salon, uid: str, fiche_p: dict) -> None:
    """Retire seulement les composants de la bienvenue identifiée du bot.

    pret_retire est un ancien marqueur, pas une preuve d'absence du bouton WhatsApp.
    Le contenu du message et les autres messages restent inchangés.
    """
    mid = (fiche_p.get("messages") or {}).get("bienvenue")
    if not mid or not str(mid).isdigit() or salon is None:
        return
    try:
        msg = await salon.fetch_message(int(mid))
        if getattr(msg.author, "id", None) != getattr(salon.guild.me, "id", None):
            return
        if msg.components:
            await msg.edit(view=None)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        pass
    except Exception as erreur:                                         # noqa: BLE001 — un bouton en trop, jamais une étape en moins
        journal.info("Bouton de bienvenue de %s : %s", uid, erreur)


async def demarrer_parcours(salon, membre, creatrice: str, bienvenue: bool = True) -> None:
    """Après la livraison des comptes : le message de bienvenue (09/10), puis l'étape 1. Rejoué sur un clipper déjà en route : on ne
    repart pas de zéro (09/10 : créatrice comparée sans accent ni casse, « Chloé » = « chloe »).
    09/10 (revue : « 🔄 Je reprends » après une réservation expirée renvoyait une 2e bienvenue et une 2e demande WhatsApp au lieu du
    compte 1 promis) : `bienvenue=False`, ou une bienvenue déjà postée dans CE salon pour la même créatrice (trace gardée par
    `oublier`) → pas de second message de bienvenue : le compte 1 tout de suite, le WhatsApp déjà déclaré gardé."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.get(uid)
    if fiche_p and int(fiche_p.get("etape", 0) or 0) >= 1 and _cle_creatrice(fiche_p.get("creatrice")) == _cle_creatrice(creatrice):
        if int(fiche_p.get("etape", 0) or 0) == 1 and not (fiche_p.get("messages") or {}).get("1"):
            await ouvrir_compte_1(salon, uid, par="bot")
        return
    nouveau = {"prenom": _prenom(membre), "creatrice": creatrice}
    trace = _reprendre_trace(uid, salon, creatrice)
    if not bienvenue or trace:
        reprise = {**nouveau, "salon_id": str(salon.id), "etape": 1, "dates": {}, "notes": (fiche_p or {}).get("notes", []),
                   "ordre": "prive2" if PRIVE_EN_2 else "prive3",
                   "programme": [{"quand": _maintenant(), "type": "etape", "n": 1}]}   # filet : membre introuvable à l'instant
        for cle in ("bienvenue", "whatsapp", "whatsapp_par"):         # la bienvenue reste au-dessus, le WhatsApp déjà déclaré aussi
            if (trace or {}).get(cle):
                reprise[cle] = trace[cle]
        if (trace or {}).get("message"):
            reprise["messages"] = {"bienvenue": str(trace["message"])}
        d[uid] = reprise
        _ecrire(d)
        await ouvrir_compte_1(salon, uid, par="bot")
        return
    maintenant = datetime.now(timezone.utc)
    # 09/10 : étape 1 « en attente » (pas de dates["1"]) le temps de la bienvenue. 10/10 : le compte 1 part juste après elle ; le
    # programme à BIENVENUE_H h n'est qu'un filet (membre introuvable à l'instant). « pret_retire » : pas de « ✅ C'est fait » à retirer.
    d[uid] = {**nouveau, "salon_id": str(salon.id), "etape": 1, "dates": {}, "notes": (fiche_p or {}).get("notes", []),
              "ordre": "prive2" if PRIVE_EN_2 else "prive3",                # 08/10 : le privé en 2 pour tout nouveau parcours
              "bienvenue": maintenant.isoformat(timespec="seconds"), "pret_retire": True, "accueil_unique": True,
              "programme": [{"quand": (maintenant + timedelta(hours=BIENVENUE_H)).isoformat(timespec="seconds"), "type": "etape", "n": 1}]}
    _ecrire(d)
    # L'accueil est livré avec Croissance 1, par la même voie de reprise que cette étape.
    await ouvrir_compte_1(salon, uid, par="bot")


async def ouvrir_compte_1(salon, uid: str, par: str = "bot") -> str:
    """09/10 : après la bienvenue, l'étape 1 (le compte 1), une seule fois : au clic sur ✅ (par="clipper" : il a écrit à Gaëtan ;
    "staff" : un manager appuie pour lui) ou par le programme (par="bot", BIENVENUE_H h plus tard). Renvoie « envoye », « deja »
    (déjà donné, ou plus à l'étape 1), « absent » (plus sur le serveur) ou « attente » (11/10 : pas encore de ligne libre au
    classeur, ou classeur illisible ; le compte 1 reste au programme et part tout seul dès que sa ligne existe)."""
    uid = str(uid)
    membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
    if membre is None:
        return "absent"
    d = _lire()
    f = d.get(uid)
    if not f or (f.get("messages") or {}).get("1") or int(f.get("etape", 0) or 0) != 1:
        return "deja"
    f["bienvenue_ok"] = _maintenant()                                   # écrit AVANT l'envoi : jamais deux fois (clic + programme)
    f["programme"] = [x for x in f.get("programme") or [] if not (x.get("type") == "etape" and int(x.get("n") or 0) == 1)]
    _ecrire(d)
    # 11/10 (revue du lot W) : sans ligne libre, le compte 1 reste au programme (élément « ligne », envoyer_etape direct) : « attente »
    return "envoye" if await envoyer_etape(salon, membre, 1) else "attente"


class BoutonPret(discord.ui.DynamicItem[discord.ui.Button], template=r"pret:(?P<uid>[0-9]+)"):
    """09/10 : « ✅ C'est fait » du message de bienvenue — le clipper a écrit à Gaëtan sur WhatsApp, son compte 1 arrive. Persistant
    (custom_id « pret:<uid> », enregistré par vues_persistantes), comme les boutons d'étape."""

    def __init__(self, uid: str, label: str = "✅ C'est fait"):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.success, custom_id=f"pret:{uid}"))
        self.uid = str(uid)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["uid"], item.label or "✅ C'est fait")

    async def callback(self, interaction: discord.Interaction):
        staff = _deps.get("est_staff")
        lui = str(interaction.user.id) == self.uid
        if not lui and not (staff and staff(interaction.user)):
            await interaction.response.send_message("Ce bouton est pour le clipper de ce salon 🙂", ephemeral=True)
            return
        await interaction.response.defer()
        etat = await ouvrir_compte_1(interaction.channel, self.uid, par="clipper" if lui else "staff")
        if etat == "envoye" and lui and _deps.get("activite"):
            try:
                _deps["activite"](self.uid)                             # un appui du clipper = une réponse à l'appel
            except Exception:                                           # noqa: BLE001
                pass
        elif etat != "envoye":
            try:
                await interaction.followup.send("Ton compte 1 est déjà là, juste en dessous 🙂" if etat == "deja"
                                                else "⏳ Ton compte 1 arrive ici dès qu'il est prêt." if etat == "attente"
                                                else "Je ne te retrouve pas sur le serveur. Écris à Gaëtan.", ephemeral=True)
            except (discord.Forbidden, discord.HTTPException):
                pass


def vues_persistantes(client=None) -> list:
    """09/10 : les boutons persistants du parcours (custom_id fixes, ils survivent aux redémarrages) : « ✅ » des étapes
    (BoutonEtape), « ✅ J'ai écrit à Gaëtan » (BoutonWhatsApp) et « ✅ C'est fait » de la bienvenue (BoutonPret, « pret:<uid> »).
    Enregistrés sur `client` (sinon le client de configurer) ; la liste est renvoyée dans tous les cas."""
    classes = [BoutonEtape, BoutonWhatsApp, BoutonPret]
    client = client if client is not None else _deps.get("client")
    if client is not None and hasattr(client, "add_dynamic_items"):
        client.add_dynamic_items(*classes)
    return classes


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
    for cle in ("dates", "messages", "profils", "programme", "essai", "reconcilie", "corrige_4", "warmup_jour", "base_reels", "reels_soir"):
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
    # 11/10 (lot W) : plus de « routine2 » programmée (la suite à J+7, « jusqu'à 10 Reels par jour », est supprimée depuis le
    # 10/10 : elle contredisait la règle des 2 Reels par jour). Une trace « routine2 » déjà reçue reste sur la fiche.
    d[uid] = {"prenom": _prenom(membre),
              "creatrice": creatrice, "salon_id": str(salon.id), "etape": 7, "dates": {"7": _maintenant()},
              "notes": (fiche_p or {}).get("notes", []), "programme": []}
    if (fiche_p or {}).get("routine2"):
        d[uid]["routine2"] = fiche_p["routine2"]
    _ecrire(d)
    await _envoyer_routine(salon, membre, uid)                          # 09/10 : la routine et son app, en UN message


DOUBLE_APPUI_MIN = 10                                                   # 11/10 : un 2e appui dans les 10 min ne dit rien


def _ferme_il_y_a_peu(fiche_p: dict, n: int, maintenant=None) -> bool:
    """L'étape n de cette fiche a été fermée (« n_fait ») il y a moins de DOUBLE_APPUI_MIN minutes."""
    try:
        quand = datetime.fromisoformat(str((fiche_p.get("dates") or {}).get(f"{int(n)}_fait") or ""))
    except ValueError:
        return False
    if quand.tzinfo is None:
        quand = quand.replace(tzinfo=timezone.utc)
    return (maintenant or datetime.now(timezone.utc)) - quand < timedelta(minutes=DOUBLE_APPUI_MIN)


async def valider_etape(salon, uid: str, n: int, par: str = "", creation: bool = False) -> bool:
    """Le bouton (ou le manager) ferme l'étape n et ouvre la suivante. Idempotent : un double clic ne saute rien.
    10/10 (vérification L10 : deux appuis rapides sur « ✅ Compte 1 créé », la 2e fenêtre arrivait après le profil et fermait l'étape,
    warm-up envoyé, profil sauté) : `creation` = l'appui vient du bouton « Compte n créé » (ou de sa fenêtre). Si le profil du
    compte n est déjà parti, il ne ferme rien (renvoie vrai) : seul « ✅ Profil fait » du message de profil, ou le scan, ferme l'étape.
    10/10 (Gaëtan : « simplifier et supprimer toutes les étapes inutiles ») : un compte qui publie (pas le privé) n'a plus de « ✅ Profil
    fait ». Au « ✅ Compte n créé » (ou au scan qui voit le compte), l'étape se ferme ET son profil part, sans bouton, avec le warm-up à
    la fin (profil.envoyer, `suite`) : un message au lieu de deux, un bouton de moins. Le privé garde son « ✅ Profil fait » (le lien,
    le passage en privé) ; à cet appui partent la story à la une (TEXTE_STORY, sans bouton) puis la routine et l'app (étape 7)."""
    d = _lire()
    fiche_p = d.get(str(uid))
    if (fiche_p and int(n) == 6 and ordre(fiche_p) == "prive2" and int(fiche_p.get("etape", 0)) != 6
            and (fiche_p.get("dates") or {}).get("6")):
        # 08/10 (privé en 2) : le message du lien part à côté du parcours (le compte 3 attend) ; son bouton note que c'est fait
        if (fiche_p.get("dates") or {}).get("6_fait"):
            return True
        fiche_p["dates"]["6_fait"] = _maintenant()
        _ecrire(d)
        await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get("6"))
        if _deps.get("activite") and par != "bot":
            try:
                _deps["activite"](str(uid))
            except Exception:                                           # noqa: BLE001
                pass
        return True
    if (creation and fiche_p and int(n) in (1, 2, 3) and int(fiche_p.get("etape", 0) or 0) != int(n)
            and (fiche_p.get("dates") or {}).get(f"{int(n)}_fait")):
        return True                                                     # 10/10 : 2e appui de création, l'étape est déjà fermée
    if (not creation and par == str(uid) and fiche_p and int(n) in (1, 2, 3) and int(fiche_p.get("etape", 0) or 0) != int(n)
            and _ferme_il_y_a_peu(fiche_p, n)):
        # 11/10 (lot W, contre-vérification du lot L1 : double appui sur « ✅ Profil fait » du privé) : le 1er appui a fermé
        # l'étape et envoyé la story ; le 2e ne dit plus « Ce bouton n'est plus valable » juste sous la story. Seulement le
        # clipper lui-même et une fermeture de moins de DOUBLE_APPUI_MIN minutes : un vieux bouton garde son refus.
        return True
    if not fiche_p or int(fiche_p.get("etape", 0)) != int(n):
        return False
    if not (fiche_p.get("dates") or {}).get(str(n)):
        # 01/10 (Steeve, Ricardo) : une étape pas encore ouverte (le compte suivant attend ses 48 h et ses Reels) ne se ferme
        # pas — ni par un vieux bouton, ni par le scan qui voit le compte (identifiant pris par un tiers, liste dans le désordre)
        return False
    if creation and int(n) in (1, 2, 3) and (fiche_p.get("profils") or {}).get(str(n)):
        return True                                                     # 10/10 : 2e appui de création, le profil est déjà parti
    # 30/09 : compte créé → d'abord son profil (photo, nom, bio en UN message, bouton « profil fait »), rien d'autre ; le
    # deuxième appui (ou le scan qui voit le compte) ferme l'étape. Un compte rendu par un sortant garde son profil.
    # 10/10 : seulement le privé ; le profil d'un compte qui publie part à la fermeture ci-dessous (`profil_suite`), sans bouton.
    profil_suite = False
    if n in (1, 2, 3) and not (fiche_p.get("profils") or {}).get(str(n)) and _deps.get("profil_envoyer") \
            and str((fiche_p.get("dates") or {}).get(str(n)) or "9") >= DISTILLE_DEPUIS:
        fait_avant = (fiche_p.get("dates") or {}).get(f"{n}_fait")      # 11/10 : lu avant l'attente (double appui, plus bas)
        ctx = await _contexte(getattr(salon, "guild", None), str(uid), fiche_p)
        # 01/10 (relecture) : relue après l'appel au classeur — l'ancienne copie écrasait ce qui avait été écrit pendant
        # l'attente ; un double appui arrivé entre-temps a déjà envoyé le profil
        d = _lire()
        fiche_p = d.get(str(uid))
        fait_apres = ((fiche_p or {}).get("dates") or {}).get(f"{n}_fait")
        if creation and fait_apres and fait_apres != fait_avant:
            # 11/10 (vérification L1 : deux « Compte n créé » coup sur coup, ou le scan pendant l'appui) : l'autre appel a fermé
            # l'étape pendant l'attente du classeur ; ce 2e appui ne dit rien (pas de « Ce bouton n'est plus valable »).
            # Seulement une fermeture faite PENDANT l'attente : l'étape rouverte par le staff avec un vieux « n_fait » (rien ne
            # l'efface) envoie toujours son profil et se ferme à l'appui
            return True
        if not fiche_p or int(fiche_p.get("etape", 0)) != int(n) or not (fiche_p.get("dates") or {}).get(str(n)):
            return False
        if (fiche_p.get("profils") or {}).get(str(n)):
            return True
        existe = str(ctx.get(f"creation{n}", "")).startswith("Ce compte existe déjà")
        if not existe and n != n_prive(fiche_p):
            # 10/10 : un compte qui publie. Sa date de création (le warm-up et les 48 h en partent) est posée dans la MÊME écriture
            # que la fermeture, sans attente entre les deux : un 2e appui ou le scan pendant l'envoi ne ferme jamais deux fois
            fiche_p.setdefault("profils", {})[str(n)] = _maintenant()
            profil_suite = True
        elif not existe:
            lien_p = str(_onb(uid).get("lien", "") or "")               # 05/10 : le lien dans la bio du compte privé (08/10 : le 2)
            fiche_p.setdefault("profils", {})[str(n)] = _maintenant()
            fiche_p["lien_profil"] = lien_p                             # 09/10 (revue) : vide → la story redonne le lien (lien_dans_profil)
            _ecrire(d)
            await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get(str(n)))
            vue = discord.ui.View(timeout=None)
            vue.add_item(BoutonEtape(uid, n, "✅ Profil fait"))
            try:
                msg = await _deps["profil_envoyer"](salon, uid, n, fiche_p.get("creatrice", ""), vue=vue, lien=lien_p, prive=True)
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
    prive2 = ordre(fiche_p) == "prive2"
    # 08/10 : en « prive2 », le compte 3 est le dernier. 10/10 : en « prive3 » aussi (le privé), plus d'étape 6 après lui
    fiche_p["etape"] = 7 if n == 3 else n + 1
    story = n == 3 and not prive2 and n == n_prive(fiche_p)
    if story:
        # 11/10 (revue du lot W : un arrêt du bot entre cette écriture et la story perdait story et routine) : la marque est posée
        # dans la même écriture que 3_fait ; story_puis_app la retire à la fin, fermer_profils_oublies relance ce qui reste.
        # 11/10 (clôture de la vague 2 : le tour horaire tombait pendant les attentes ci-dessous, avant que story_puis_app ne
        # s'inscrive, et lançait sa propre story : story et routine en double) : l'uid est inscrit dans _STORY_EN_COURS AVANT
        # l'écriture de la marque, et n'en sort qu'à la fin de cette fermeture
        fiche_p["story_due"] = _maintenant()
        _STORY_EN_COURS.add(str(uid))
        try:
            _ecrire(d)
            return await _apres_fermeture(salon, uid, n, par, fiche_p, prive2, profil_suite)
        finally:
            _STORY_EN_COURS.discard(str(uid))
    _ecrire(d)
    return await _apres_fermeture(salon, uid, n, par, fiche_p, prive2, profil_suite)


async def _apres_fermeture(salon, uid: str, n: int, par: str, fiche_p: dict, prive2: bool, profil_suite: bool) -> bool:
    """Suite de valider_etape une fois l'étape n fermée et écrite : activité, boutons retirés, classeur, puis la suite du parcours
    (warm-up, étape suivante, ou story à la une et routine du privé)."""
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
    if prive2 and n == 2:
        # 08/10 (privé en 2) : le compte 2 privé est créé → le lien et la story à la une tout de suite (message à côté du
        # parcours), et le compte 3 dans 48 h, quand 4 Reels DE PLUS sont publiés sur le compte 1 (base retenue ici)
        base = min(_date_creation(fiche_p, n) or maintenant, maintenant)
        d = _lire()
        f2 = d[str(uid)]
        f2["programme"] = [{"quand": (base + timedelta(hours=ATTENTE_COMPTE_H)).isoformat(timespec="seconds"), "type": "etape", "n": 3}]
        f2.setdefault("base_reels", {}).setdefault("3", reels_vus(uid, f2, 1))   # (revue) réouverture par `!etape @x 2` : base gardée
        lien_deja = bool((f2.get("dates") or {}).get("6"))
        _ecrire(d)
        if not lien_deja:                                               # le lien est déjà parti : pas de second message
            await envoyer_etape(salon, membre, 6, pointer=False)
        return True
    if n in (1, 2, 3):
        # 30/09 : règle des 48 h tenue par le bot ; 01/10 : la même pour tous, comptée depuis la création du compte (premier
        # signal), et l'étape suivante n'est envoyée qu'avec REELS_OUVERTURE Reels vus sur ce compte (programme_du_jour).
        # 08/10 (privé en 2) : le compte 3, dernier compte de croissance → warm-up, « il peut publier », la routine, et l'app.
        dernier = prive2 and n == 3
        if n != n_prive(fiche_p) or dernier:
            base = min(_date_creation(fiche_p, n) or maintenant, maintenant)
            publier = {"quand": (base + timedelta(hours=WARMUP_H)).isoformat(timespec="seconds"), "type": "publier", "n": n}
            suite_n = 7 if dernier else n + 1
            etape = {"quand": (base + timedelta(hours=WARMUP_H if dernier else ATTENTE_COMPTE_H)).isoformat(timespec="seconds"),
                     "type": "etape", "n": suite_n}
            deja_chaud = _echu(publier, maintenant)                     # compte créé il y a plus de 24 h : il publie tout de suite
            d = _lire()
            d[str(uid)]["programme"] = [etape] if deja_chaud else [publier, etape]
            if n == 2 and not prive2:                                   # 09/10 : le privé exige 4 Reels DE PLUS sur le compte 1
                d[str(uid)].setdefault("base_reels", {}).setdefault("3", reels_vus(uid, d[str(uid)], 1))
            _ecrire(d)
            profil_parti = False
            if profil_suite:
                # 10/10 : le profil sans bouton, le warm-up à la fin ; s'il ne part pas, le warm-up seul, comme avant
                try:
                    profil_parti = await _deps["profil_envoyer"](salon, uid, n, fiche_p.get("creatrice", ""), vue=None, prive=False,
                                                                 suite=TEXTE_WARMUP_PROFIL.format(h=WARMUP_H)) is not None
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("Profil du compte %s pour %s : %s", n, uid, erreur)
            if deja_chaud:
                await _envoyer_publier(salon, membre, uid, n)
            elif not profil_parti:
                # 09/10 (Gaëtan : « au compte-goutte ») : le warm-up seul, sans la règle complète des comptes
                await _suite(salon, f"{membre.mention} " + TEXTE_WARMUP.format(n=n, h=WARMUP_H))
            # 09/10 : plus d'app ici (ordre « prive2 », compte 3) : elle part avec la routine, l'étape 7 programmée ci-dessus
            return True
    if n == 3:
        # 05/10 : compte 3 privé, pas de warm-up. 10/10 (Gaëtan : le 3e compte « avec le lien GAML + l'application de clippeur ») :
        # plus d'étape 6 à bouton qui retenait l'app jusqu'à 24 h. La story à la une part sans bouton, puis la routine et l'app
        # (étape 7, déjà posée ci-dessus). Le lien, si le profil du privé est parti sans lui, part avant, à part.
        # 11/10 (vérification L1 : forfait GAML plein à l'ouverture du compte 3, lien libéré ensuite ; l'ancienne étape 6 refaisait
        # un essai, la routine partait ici sans lien ni app, jusqu'à 6 h d'attente) : un nouvel essai, un seul, s'il manque encore.
        await story_puis_app(salon, membre, str(uid), fiche_p)
        return True
    if n + 1 in ETAPES:
        await envoyer_etape(salon, membre, n + 1)                      # 09/10 : n = 6 → l'étape 7, la routine avec l'app
    return True


async def story_puis_app(salon, membre, uid: str, fiche_p: dict = None) -> None:
    """10/10 : après le profil du privé, sans bouton : le lien s'il manque (un nouvel essai GAML, un seul), la story à la une
    (TEXTE_STORY), puis la routine et l'app (étape 7). 11/10 (lot W) : sortie de valider_etape pour servir aussi à l'ancien repris
    d'après le classeur avec ses 3 comptes créés (demarrer_selon_classeur), qui n'attend plus d'étape 6 à bouton."""
    uid = str(uid)
    _STORY_EN_COURS.add(uid)
    try:
        await _story_puis_app(salon, membre, uid, fiche_p)
    finally:
        _STORY_EN_COURS.discard(uid)


# 11/10 (revue du lot W) : les story_puis_app en cours dans CE processus. Une marque « story_due » sans entrée ici = un arrêt du bot
# (déploiement Railway) au mauvais moment : fermer_profils_oublies la relance (au démarrage, puis toutes les heures).
_STORY_EN_COURS = set()


def _poser_story(uid: str, cle: str, retirer: bool = False) -> None:
    d = _lire()
    if uid not in d:
        return
    if retirer:
        d[uid].pop("story_due", None)
        d[uid].pop("story_faite", None)
    else:
        d[uid][cle] = _maintenant()
    _ecrire(d)


async def _story_puis_app(salon, membre, uid: str, fiche_p: dict = None) -> None:
    if not (_lire().get(uid) or {}).get("story_faite"):                 # 11/10 : relancée après un arrêt, la story déjà partie ne
        if not str(_onb(uid).get("lien") or "") and _deps.get("attribuer_lien"):   # repart pas : seulement la routine
            try:
                await _deps["attribuer_lien"](membre)
            except Exception as erreur:                                 # noqa: BLE001 — sans lien, la story et la routine partent
                journal.warning("Lien GAML pour %s au profil du privé : %s", uid, erreur)
        try:
            ctx = await _contexte(getattr(salon, "guild", None), uid, _lire().get(uid) or fiche_p or {"prenom": _prenom(membre)})
            if ctx.get("ligne_lien"):
                await salon.send((f"{membre.mention} " + ctx["ligne_lien"].strip())[:1990])
            await salon.send((f"{membre.mention} " + _rendre(TEXTE_STORY, ctx))[:1990])
        except (discord.Forbidden, discord.HTTPException) as erreur:  # la routine et l'app partent quand même
            journal.warning("Story à la une de %s : %s", uid, erreur)
        if (_lire().get(uid) or {}).get("story_due"):
            _poser_story(uid, "story_faite")
    await envoyer_etape(salon, membre, 7)
    _poser_story(uid, "", retirer=True)


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


def phrase_suivant(uid, fiche_p: dict, n: int) -> str:
    """09/10 : sous « ton compte n peut publier », ce qui ouvre le compte suivant, en une phrase : « Ton compte 2 arrive ici dès que je
    vois 4 Reels sur ce compte. » ; pour le privé : « … 4 Reels sur ce compte et 4 de plus sur ton compte 1. »."""
    k = n + 1
    morceaux = []
    for src in sorted(sources_reels(fiche_p, k), key=lambda s: s != n):
        if src == n:
            morceaux.append(f"{REELS_OUVERTURE} Reels sur ce compte")
        elif _de_plus(fiche_p, k, src):
            morceaux.append(f"{REELS_OUVERTURE} de plus sur ton compte {src}")
        else:
            morceaux.append(f"{REELS_OUVERTURE} Reels sur ton compte {src}")
    return f"Ton compte {k} arrive ici dès que je vois " + " et ".join(morceaux) + "."


async def _envoyer_publier(salon, membre, uid: str, n: int) -> None:
    """« Ton compte n peut publier » ; 01/10 : et ce qui ouvre le compte suivant, s'il attend encore. 09/10 : les vidéos d'origine de
    la créatrice (plus de Drive perso), une ligne vide entre chaque paragraphe. 10/10 : sous le compte 1, le rappel WhatsApp pour qui
    ne l'a pas déclaré (le compte 1 ne l'attend plus) ; plus de ligne « Un doute sur une vidéo »."""
    if n not in TEXTE_PUBLIER:
        return
    fiche_p = _lire().get(str(uid), {})
    ctx = await _contexte(getattr(salon, "guild", None), str(uid), fiche_p, drive=n == 1)
    texte = _rendre(TEXTE_PUBLIER[n], ctx)
    a = attente(fiche_p)
    # 01/10 (relecture) : la condition seulement si le compte suivant attend encore ; BAN sans aucun compte vivant : rien ici,
    # l'équipe est prévenue (_signaler_bloques)
    if a and a[0] == n + 1 and reels_pour(uid, fiche_p, n + 1) < REELS_OUVERTURE and not _bloque_sources(uid, fiche_p, n + 1):
        texte += "\n\n" + phrase_suivant(uid, fiche_p, n)
    # 10/10 : plus de « Un doute sur une vidéo ? Envoie-la ici avant » ici (LIGNE_DOUTE retirée)
    vue = None
    await salon.send((f"{membre.mention} " + texte)[:1990], **({"view": vue} if vue is not None else {}))


# 08/10 (Mathieu : « ça me redirige vers WhatsApp mais il demande d'envoyer le message à un contact dans mon téléphone ») : le
# lien de Gaëtan est un lien court WhatsApp Business (wa.me/message/…), qui ne prend pas de texte ; le « ?text= » ajouté le
# cassait (WhatsApp ouvrait le choix d'un contact). Le texte n'est ajouté qu'à un lien wa.me/<numéro> — ou au numéro de
# WHATSAPP_GAETAN_NUMERO s'il est posé dans Railway (jamais dans le dépôt) ; sinon le lien court part tel quel et le message à
# envoyer est écrit dans Discord, à copier.
WHATSAPP_NUMERO = re.sub(r"\D", "", os.environ.get("WHATSAPP_GAETAN_NUMERO", ""))


def _message_wa(uid, fiche_p: dict = None, groupe: bool = False) -> str:
    fiche_p = _lire().get(str(uid), {}) if fiche_p is None else fiche_p
    return (f"Bonjour Gaëtan, je suis {fiche_p.get('prenom') or 'un clipper'}, clipper de {fiche_p.get('creatrice') or '?'}."
            + (" Tu peux m'ajouter au groupe ?" if groupe else ""))           # 09/10 : la demande du groupe, à la bienvenue


def whatsapp_prerempli() -> bool:
    """Le bouton WhatsApp peut-il porter le message déjà écrit ? Seulement vers un numéro (wa.me/<numéro>)."""
    base = str(_deps.get("whatsapp") or "").split("?")[0]
    return bool(WHATSAPP_NUMERO) or bool(re.search(r"wa\.me/\+?\d{6,}/?$", base))


def lien_whatsapp_prerempli(uid, fiche_p: dict = None, groupe: bool = False) -> str:
    """05/10 : le wa.me de Gaëtan avec le message du clipper déjà écrit (prénom, créatrice) quand c'est possible ; sinon le lien
    court WhatsApp Business tel quel (08/10). 09/10 : `groupe` ajoute « Tu peux m'ajouter au groupe ? » (message de bienvenue)."""
    from urllib.parse import quote
    brut = str(_deps.get("whatsapp") or "")
    base = f"https://wa.me/{WHATSAPP_NUMERO}" if WHATSAPP_NUMERO else brut.split("?")[0]
    if not base:
        return ""
    if not whatsapp_prerempli():
        return brut
    return f"{base.rstrip('/')}?text=" + quote(_message_wa(uid, fiche_p, groupe=groupe))


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
                    # 10/10 : c'est désormais le ✅ de la bienvenue : la créatrice et le geste à faire, comme l'ancien « C'est fait »
                    f_wa = _lire().get(self.uid) or {}
                    prenom = f_wa.get("prenom") or self.uid
                    await canal.send(f"📲 {prenom} (<@{self.uid}>, {f_wa.get('creatrice') or '?'}) dit avoir écrit sur WhatsApp : "
                                     f"ajoute-le au groupe. Pas vrai ? `!wa @{prenom} non`.")
            except Exception:                                           # noqa: BLE001
                pass


# ------------------------------------------------------------------ app clippers
# 08/10 (Gaëtan : « envoie automatiquement l'app dans le salon Discord privé du clippeur, une fois seulement qu'il a créé les
# 3 IG : l'app + son lien de tracking GAML ») : dès que l'étape du compte 3 est fermée (étape 6 ou plus : compte 3 créé, ou
# parcours repris plus loin par le staff), un message dans son salon perso avec le bouton de son app et son lien GAML. Une
# seule fois (« app » dans la fiche, écrite avant l'envoi) ; si l'app ne le connaît pas encore, la passe horaire réessaie et
# le salon admin est prévenu une fois par jour. Le lien de l'app vient de l'app elle-même (lien_app.py), jamais deviné.
# 09/10 (Gaëtan : « Application de clippeur pour suivre ses revenus » ; « simplifie, supprime ») : l'app part avec la routine, en UN
# message (_envoyer_routine) ; ce texte ne sert plus qu'à `!app` et au rattrapage. Le lien GAML n'y est plus recollé : il est dans
# le champ Liens du privé depuis son profil (livrer_app en a toujours besoin pour retrouver l'app, pas pour l'afficher). Plus de
# « tes vidéos à publier » : l'app montre les visites et les gains.
TEXTE_APP = ("📱 {mention} **Ton app clipper**\n\n"
             "Tes visites et tes gains, jour par jour.\n\n"
             "Ouvre-la dans Safari (iPhone) ou Chrome (Android), puis mets-la sur ton écran d'accueil.\n\n"
             "🔒 Elle est à toi : ne donne son lien à personne.")
APP_PAR_PASSE = 5                                                       # rattrapage : 5 messages au plus par passe horaire
STORY_AUTO_H = int(os.environ.get("PARCOURS_STORY_AUTO_H", "24") or 24)   # 09/10 : « ✅ Fait » de la story oublié → fermée seule
# 09/10 (plan : « les clippers déjà en route, on ne les touche pas ») : une étape 6 ouverte avant ce jour (ancien message « Ton lien
# et ta story », app déjà envoyée avec lui) garde l'ancien déroulé : ni fermeture automatique, ni app retenue
STORY_AUTO_DEPUIS = "2026-10-09T00:00:00+00:00"


def lien_du(fiche_p: dict) -> bool:
    """08/10 : le lien GAML est dû — son compte privé est ouvert (étape 2 envoyée en ordre « prive2 », étape 3 sinon) ou le
    parcours en est au lien (6) ou à la routine (7)."""
    fiche_p = fiche_p or {}
    n = int(fiche_p.get("etape", 0) or 0)
    dates = fiche_p.get("dates") or {}
    np_ = n_prive(fiche_p)
    return n >= 6 or n > np_ or (n == np_ and bool(dates.get(str(np_))))


def lien_a_dire(fiche_p: dict) -> bool:
    """Le lien peut être annoncé (« Ton lien est prêt ») : son compte privé est créé, ou le parcours en est au lien."""
    fiche_p = fiche_p or {}
    np_ = str(n_prive(fiche_p))
    return (int(fiche_p.get("etape", 0) or 0) >= 6 or bool((fiche_p.get("dates") or {}).get(f"{np_}_fait"))
            or bool((fiche_p.get("profils") or {}).get(np_)))         # (revue) le profil du privé a promis « ton lien arrive ici »


def trois_comptes(fiche_p: dict) -> bool:
    """Ses 3 comptes sont créés : l'étape du compte 3 est fermée (étape 6, le lien, ou 7, la routine). 08/10 (revue) : en ordre
    « prive2 », l'étape 6 peut être en cours avant le compte 3 ; il faut le compte 3 fermé ou la routine."""
    n = int((fiche_p or {}).get("etape", 0) or 0)
    if ordre(fiche_p) == "prive2":
        return n >= 7 or (n >= 6 and bool(((fiche_p or {}).get("dates") or {}).get("3_fait")))
    return n >= 6


def app_due(fiche_p: dict) -> bool:
    """09/10 : l'app part AVEC la routine (étape 7, un seul message). Le rattrapage seul ne vaut que si la routine est déjà partie
    (l'app n'était pas prête), ou pour une fiche ancienne à l'étape 6 sans date ; jamais pendant la story à la une (étape 6 ouverte)
    ni pendant les 24 h qui précèdent la routine (ordre « prive2 »)."""
    if not trois_comptes(fiche_p):
        return False
    f = fiche_p or {}
    if int(f.get("etape", 0) or 0) >= 7:
        return not any(x.get("type") == "etape" and int(x.get("n") or 0) == 7 for x in f.get("programme") or [])
    d6 = (f.get("dates") or {}).get("6")
    return not d6 or str(d6) < STORY_AUTO_DEPUIS                        # étape 6 de l'ancien déroulé : l'app comme avant


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


async def livrer_app(uid: str, salon=None, membre=None, client=None, forcer: bool = False, texte: str = "") -> str:
    """Envoie dans son salon perso le bouton de son app, une seule fois (forcer : staff ou `!app`, renvoyé même si déjà envoyé).
    09/10 : `texte` (le message déjà écrit, mention comprise : la routine) part avec le bouton à la place de TEXTE_APP, en UN message.
    Renvoie « envoye », « deja », « pas_pret », « exclu », « sans_lien », « sans_app » ou « erreur »."""
    uid = str(uid)
    fiche_p = _lire().get(uid) or {}
    if _onb(uid).get("sorti"):
        return "sans_lien"
    if fiche_p.get("app") and not forcer:
        return "deja"  # l'app historique continue ; aucune nouvelle livraison
    if not fiche_p.get("app") and not _onb(uid).get("liens_prets"):
        return "sans_lien"
    if not forcer:
        if fiche_p.get("app"):
            return "deja"
        if not app_due(fiche_p):                                        # 09/10 : avec la routine, pas avant
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
        msg = await salon.send((texte or TEXTE_APP.format(mention=membre.mention, app=url))[:1990], view=vue)
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("App pour %s : %s", uid, erreur)
        if not forcer:
            d = _lire()
            if uid in d:
                d[uid].pop("app", None)
                _ecrire(d)
        return "erreur"
    if texte and getattr(msg, "id", None) is not None:                  # 09/10 : la routine, retrouvée par `!etape`
        d = _lire()
        if uid in d:
            d[uid].setdefault("messages", {})["7"] = str(msg.id)
            _ecrire(d)
    journal.info("App clippers envoyée à %s", uid)
    return "envoye"


async def _envoyer_routine(salon, membre, uid: str, ctx: dict = None) -> str:
    """09/10 (plan du funnel, étape 13) : « 🎉 Bravo, tes 3 comptes sont en place » — la routine ET le bouton de l'app, en UN message
    (livrer_app). L'app pas prête (aucun lien GAML, app injoignable), déjà envoyée ou exclue : la routine part seule, sans la ligne de
    l'app (le rattrapage horaire l'envoie dès qu'elle est prête). Renvoie l'état de livrer_app."""
    uid = str(uid)
    if ctx is None:
        ctx = await _contexte(getattr(salon, "guild", None), uid, _lire().get(uid) or {})
    e = ETAPES[7]

    def message(avec_app: bool) -> str:
        c = {**ctx, "ligne_app": LIGNE_APP if avec_app else ""}
        return f"{membre.mention} {e['icone']} **{_rendre(e['titre'], c)}**\n\n{_rendre(e['texte'], c)}"

    try:
        etat = await livrer_app(uid, salon=salon, membre=membre, texte=message(True))
    except Exception as erreur:                                         # noqa: BLE001 — la routine part quand même
        journal.warning("App clippers pour %s : %s", uid, erreur)
        etat = "erreur"
    if etat == "envoye":
        return etat
    try:
        msg = await salon.send(message(False)[:1990])
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Routine pour %s : %s", uid, erreur)
        return etat
    d = _lire()
    if uid in d and getattr(msg, "id", None) is not None:
        d[uid].setdefault("messages", {})["7"] = str(msg.id)
        _ecrire(d)
    return etat


PROFIL_AUTO_H = int(os.environ.get("PARCOURS_PROFIL_AUTO_H", "6") or 6)


async def fermer_profils_oublies(client, maintenant=None) -> list:
    """08/10 (audit : « oublier Profil fait fige le parcours sans un mot ») : le compte est créé (premier appui ou scan, profil
    envoyé) mais « ✅ Profil fait » n'a jamais été pressé. Au bout de PROFIL_AUTO_H heures, l'étape se ferme comme si le clipper
    avait appuyé : rien n'est retardé, le warm-up et les 48 h comptent déjà depuis la création. Renvoie [(uid, n)] fermés.
    10/10 : seulement le profil du privé (les comptes qui publient n'ont plus ce bouton), sauf un profil d'avant parti avec lui."""
    maintenant = maintenant or datetime.now(timezone.utc)
    faits = []
    for uid, fiche_p in list(_lire().items()):
        if not isinstance(fiche_p, dict):
            continue
        n = int(fiche_p.get("etape", 0) or 0)
        dates = fiche_p.get("dates") or {}
        if n == 7 and fiche_p.get("story_due") and uid not in _STORY_EN_COURS:
            # 11/10 (revue du lot W) : la story et la routine du privé n'ont pas fini de partir (arrêt du bot) : relancées
            if dates.get("7"):
                _poser_story(uid, "", retirer=True)                     # la routine est partie : la marque seule restait
                continue
            salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0)) if client is not None else None
            membre = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            if salon is None or membre is None:
                continue
            try:
                await story_puis_app(salon, membre, uid)
                faits.append((uid, 7))
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Story du privé de %s, relancée : %s", uid, erreur)
            continue
        if n not in (1, 2, 3, 6) or dates.get(f"{n}_fait") or not dates.get(str(n)):
            continue
        if n == 6 and str(dates.get("6")) < STORY_AUTO_DEPUIS:
            continue                                                    # étape 6 de l'ancien déroulé : on n'y touche pas
        if n in (1, 2, 3) and n != n_prive(fiche_p) and not (fiche_p.get("messages") or {}).get(f"{n}p"):
            # 10/10 : un compte qui publie n'a plus de « ✅ Profil fait » (son étape se ferme à sa création) : seul le privé se ferme
            # ici, et un profil d'avant le 10/10 parti avec son bouton (messages « <n>p »), pour ne laisser personne en plan
            continue
        # 09/10 : la story à la une (étape 6) oubliée se ferme aussi, STORY_AUTO_H heures après son envoi : la routine et l'app (qui
        # partent à son « ✅ Fait ») n'attendent jamais un bouton (carte de fin de funnel : « l'étape du lien ne se ferme jamais seule »)
        try:
            quand = datetime.fromisoformat(str(dates.get("6") if n == 6 else (fiche_p.get("profils") or {}).get(str(n))))
        except (TypeError, ValueError):
            continue                                                    # pas encore créé : rien à fermer
        quand = quand if quand.tzinfo else quand.replace(tzinfo=timezone.utc)
        if maintenant - quand < timedelta(hours=STORY_AUTO_H if n == 6 else PROFIL_AUTO_H):
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
        if not isinstance(fiche_p, dict) or fiche_p.get("app") or not app_due(fiche_p):   # 09/10 : avec la routine, pas avant
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
        if not a or not _bloque_sources(uid, fiche_p, a[0]):
            continue
        cle = str(_bloque_sources(uid, fiche_p, a[0]))
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
                pourquoi = ("le privé ne s'ouvre que si les comptes 1 et 2 publient (`!pseudo` si c'est un @ changé)"
                            if len(sources_reels(fiche_p, a[0])) > 1 else "aucun compte qui publie")   # 09/10 (revue)
                await canal.send(f"⛔ **{fiche_p.get('prenom') or uid}** (<@{uid}>) bloqué : compte {cle} BAN, {pourquoi}, "
                                 f"parcours en attente. Tu décides : `!etape @{fiche_p.get('prenom') or uid} {a[0]}` pour "
                                 "ouvrir le suivant, aucun compte de remplacement n’est autorisé.")
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
        salon_nettoyage = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
        await _retirer_pret(salon_nettoyage, uid, fiche_p)
        if not any(_a_traiter(fiche_p, x, maintenant) for x in fiche_p.get("programme") or []):
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
            if not _a_traiter(fiche_p, x, maintenant):
                gardes.append(x)
            elif x.get("type") == "routine2":
                continue                                                # 10/10 : la suite à J+7 n'existe plus, retirée sans message
            elif x.get("type") != "etape":
                partants.append(x)
            elif not _etape_attendue(fiche_p, x):
                continue                                                # déjà envoyée (`!etape` du staff) : retirée, sans message
            elif int(x.get("n") or 0) not in (2, 3) or reels_pour(uid, fiche_p, int(x.get("n") or 0)) >= REELS_OUVERTURE:
                partants.append(x)                                      # 08/10 : la routine (7), 11/10 : « ligne », sans Reels
            else:
                gardes.append(x)                                        # 48 h passées, Reels pas encore là : on attend
                n_x = int(x.get("n") or 0)
                if fiche_p.get("attente_dite") != n_x:                   # 08/10 (audit) : une fois, il sait ce qui manque
                    fiche_p["attente_dite"] = n_x
                    # 09/10 (revue) : `!pseudo` du compte qui manque de Reels, pas toujours du compte 1 ; un compte BAN : bloqué
                    manque = [src for src, c in reels_detail(uid, fiche_p, n_x) if c < REELS_OUVERTURE] or sources_reels(fiche_p, n_x)
                    dites.append((n_x, condition_texte(uid, fiche_p, n_x), manque, _bloque_sources(uid, fiche_p, n_x)))
        if gardes == programme and not dites:
            continue
        fiche_p["programme"] = gardes
        _ecrire(d)
        for n_x, cond, srcs, bloque in dites:                           # 08/10 : « je vois N Reels », une fois par compte attendu
            try:
                if bloque:
                    await _suite(salon, f"{membre.mention} {texte_bloque(bloque)}")
                    continue
                # 09/10 (Gaëtan a vu `!pseudo 1 ton_identifiant` recopié tel quel) : plus de mot d'exemple à recopier
                await _suite(salon, f"{membre.mention} Ton compte {n_x} arrive dès que je vois {cond}.\n\n"
                                    f"Tu publies sous un autre @ ? Tape `!pseudo {srcs[0]}` puis ton vrai @.")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Attente du compte %s de %s : %s", n_x, uid, erreur)
        for item in partants:
            n = int(item.get("n") or 0)
            try:
                if item.get("type") == "publier" and n in TEXTE_PUBLIER:
                    await _envoyer_publier(salon, membre, uid, n)
                    faits.append((uid, "publier", n))
                elif item.get("type") == "etape" and n == 1 and item.get("ligne"):
                    # 11/10 (revue du lot W) : compte 1 retenu faute de ligne. ouvrir_compte_1 répondrait « deja » (bienvenue_ok posé) :
                    # l'étape part directement, dès que la ligne existe (sinon elle reste au programme, nouvel essai 30 min plus tard)
                    if await envoyer_etape(salon, membre, 1):
                        faits.append((uid, "etape", 1))
                elif item.get("type") == "etape" and n == 1:
                    # 09/10 : pas de « ✅ C'est fait » sous la bienvenue en BIENVENUE_H h → le compte 1 part quand même, une fois.
                    # 10/10 : le filet seulement (le compte 1 part déjà juste après la bienvenue)
                    if await ouvrir_compte_1(salon, uid, par="bot") == "envoye":
                        faits.append((uid, "etape", 1))
                elif item.get("type") == "etape" and n in (2, 3):
                    if await envoyer_etape(salon, membre, n):           # 11/10 (L3) : retenue faute de ligne = pas « ouverte »
                        faits.append((uid, "etape", n))
                    else:
                        reprise = _lire()
                        programme = reprise.setdefault(uid, {}).setdefault("programme", [])
                        if not any(x.get("type") == "etape" and x.get("n") == n for x in programme):
                            programme.append(item)
                            _ecrire(reprise)
                elif item.get("type") == "etape":
                    await envoyer_etape(salon, membre, n)
                    faits.append((uid, "etape", n))
                # 10/10 : plus de « routine2 » (la suite de la routine à J+7, « jusqu'à 10 Reels par jour ») : retirée plus haut
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Programme de %s (%s %s) : %s", uid, item.get("type"), n, erreur)
    return faits


def _echu(item: dict, maintenant) -> bool:
    try:
        return datetime.fromisoformat(str(item.get("quand"))) <= maintenant
    except ValueError:
        return True                                                     # date illisible : on ne la garde pas indéfiniment


def _a_traiter(fiche_p: dict, item: dict, maintenant) -> bool:
    """10/10 : l'élément du programme est à traiter maintenant. Échu (_echu), ou :
    - « routine2 » : plus programmée depuis le 11/10 ; reste retirée sans message sur les fiches d'avant le déploiement ;
    - le compte 1 : jamais plus de BIENVENUE_H h après la bienvenue (celles d'avant le 10/10 l'avaient programmé à 3 h)."""
    if item.get("type") == "etape" and int(item.get("n") or 0) in (2, 3) and not item.get("ligne"):
        return True  # 15/10 : les anciens délais ne retardent plus les paliers.
    if item.get("type") == "routine2":
        return True
    # 11/10 (revue du lot W) : un compte 1 retenu faute de ligne (« ligne ») suit son heure de nouvel essai, pas la bienvenue
    if item.get("type") == "etape" and int(item.get("n") or 0) == 1 and (fiche_p or {}).get("bienvenue") and not item.get("ligne"):
        try:
            depart = datetime.fromisoformat(str(fiche_p["bienvenue"]))
            depart = depart if depart.tzinfo else depart.replace(tzinfo=timezone.utc)
            if depart + timedelta(hours=BIENVENUE_H) <= maintenant:
                return True
        except (TypeError, ValueError):
            pass
    return _echu(item, maintenant)


def attente(fiche_p: dict):
    """(n, date au plus tôt) du compte qui attend ses 48 h et ses Reels, sinon None."""
    for item in fiche_p.get("programme") or []:
        if item.get("type") == "etape" and int(item.get("n") or 0) in (2, 3) and int(fiche_p.get("etape", 0)) == int(item.get("n") or 0) \
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
    prive_n = n == n_prive(_lire().get(str(uid)) or {})
    for h in comptes[n - 1:n]:
        try:
            # 05/10 : le compte privé ne chauffe pas (08/10 : le 2) ; 12/10 : plus de WARMUP au classeur (ETAT_WARMUP=1 : l'ancien)
            onboarding.process_adapters.store().created(uid, h, "confirmation-parcours:" + _maintenant())
            await marquer(h, "GOOD")  # privé est le type du compte, pas sa santé
        except Exception as erreur:
            journal.warning("Classeur étape %s de %s : %s", n, uid, erreur)


TICK_MIN = max(1, int(os.environ.get("PARCOURS_TICK_MIN", "10") or 10))


async def boucle(client) -> None:
    """Chaque heure : le compte des jours de warm-up dans le salon (le matin), et l'ouverture automatique des Reels
    au jour WARMUP_JOURS + 1.
    10/10 (revue du recrutement : la boucle horaire ajoutait jusqu'à 1 h à chaque échéance) : un tour léger toutes les TICK_MIN
    minutes (PARCOURS_TICK_MIN, 10 par défaut) ne fait QUE programme_du_jour — lecture de parcours.json, aucun appel Apify ni GAML
    tant que rien n'est échu. Le reste (profils oubliés, rattrapage de l'app, warm-up, relances) garde son rythme horaire : un tour
    sur 60 / TICK_MIN, le premier compris."""
    await client.wait_until_ready()
    tours, par_heure = 0, max(1, round(60 / TICK_MIN))
    while not client.is_closed():
        horaire = tours % par_heure == 0
        tours += 1
        try:
            try:
                await programme_du_jour(client)                         # 30/09 : « il peut publier », compte suivant à 48 h
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Programme du parcours : %s", erreur)
            if not horaire:                                             # 10/10 : tour léger, rien d'autre
                await asyncio.sleep(TICK_MIN * 60)
                continue
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
        await asyncio.sleep(TICK_MIN * 60)                              # 10/10 : 10 min (le reste ne tourne qu'un tour sur six)


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
    titre = titre_etape(fiche_p, n) if n in ETAPES else ("parcours non commencé" if n == 0 else "parcours terminé")
    if attente(fiche_p):                                                # 01/10 : l'étape n'est pas encore ouverte, rien à créer
        titre = f"attente du compte {n}, pas encore ouvert : rien à créer pour l'instant"
    if en_bienvenue(fiche_p):                                           # 09/10 ; 11/10 : plus de ✅ qui retient le compte 1
        titre = attente_compte_1(fiche_p)
    if n == 1 and _compte_1_retenu(fiche_p):                            # 11/10 (revue du lot W) : pas de ligne pour le compte 1
        titre = f"compte 1 {TEXTE_ATTENTE_LIGNE_1}"
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
        np_ = n_prive(fiche_p)
        lignes.append(f"Lien (dans la bio du compte {np_} privé seulement ; les autres comptes : story à la une avec le widget de "
                      f"mention du compte {np_}) : {onb['lien']}")
    # 09/10 : plus de Drive perso ; les vidéos d'origine de sa créatrice (lien dans sa bienvenue et dans « compte 1 peut publier »)
    if creatrice != "aucune":
        lignes.append(f"Vidéos à monter : celles de {creatrice}, en qualité d'origine (lien dans son message de bienvenue et dans "
                      "« ton compte 1 peut publier », sinon le salon ℹ️ de sa créatrice). Plus de dossier Drive perso.")
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
    comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)                   # 01/10 : le même ordre que les étapes
    a = attente(fiche_p)
    np_ = n_prive(fiche_p)
    parts = []
    for i in (1, 2, 3):
        h = comptes[i - 1] if i - 1 < len(comptes) else ""
        nom = f"compte {i}" + (f" `{h}`" if h else "")
        if _est_ban(h, fiche_p):
            # 01/10 (relecture) : le salon des codes nommé, plus « `!code` » seul (l'assistant disait « tape !code » au salon perso)
            # 11/10 (lot W, règle des codes du 10/10) : le code de l'appel est gardé par défaut (CODES_APPEL=0) ; plus de « !code »
            code_appel = (f"code dans #{codes_2fa.SALON_CODES_NOM} avec le bouton « 📩 Mon code »" if codes_2fa.CODES_APPEL else
                          "le code de l'appel ne passe pas par le bot : il arrive chez l'équipe, qui lui répond dans son salon perso")
            parts.append(f"{nom} : BAN, il fait appel lui-même (Contester la décision ; {code_appel} ; "
                         "selfie, son numéro ou sa pièce d'identité si demandés)")
            continue
        if not _cree(fiche_p, i):
            if i == 1 and _compte_1_retenu(fiche_p):                       # 11/10 (revue du lot W) : pas de ligne pour le compte 1
                parts.append(f"{nom} : {TEXTE_ATTENTE_LIGNE_1}")
            elif a and a[0] == i and fiche_p.get("ligne_attendue") == i:
                # 11/10 (lot W, contre-vérification du lot L3 : l'assistant parlait des 48 h et des Reels à un clipper qui les avait,
                # alors que le bot lui avait écrit « Ton compte n arrive dès qu'il est prêt »)
                parts.append(f"{nom} : {TEXTE_ATTENTE_LIGNE}" + (" — il est PRIVÉ, il portera le lien" if i == np_ else ""))
            elif a and a[0] == i:                                       # 01/10 : la règle unique, sans date promise
                parts.append(f"{nom} : pas encore ouvert, il arrive automatiquement "
                             f"dès que le scan voit {condition_texte(uid, fiche_p, i)}"
                             + (" — il est PRIVÉ, il portera le lien" if i == np_ else ""))
            else:
                parts.append(f"{nom} : pas encore créé")
            continue
        if i == np_:                                                    # 08/10 : le privé ne chauffe pas et ne publie jamais
            parts.append(f"{nom} : PRIVÉ, ne publie jamais de Reel, porte le lien dans sa bio")
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


PROCHAINES = {1: "ouvre ton compte 1, `{compte1}` (création ou connexion, c'est dans l'étape). Appuie sur ✅ quand c'est fait.",
              2: "crée ton compte 2, `{compte2}`{prive2}. Appuie sur ✅ quand c'est fait.",
              3: "crée ton compte 3, `{compte3}`{prive3}. Appuie sur ✅ quand c'est fait.",
              4: "compte 3 en warm-up (Reels, likes, 1 story, pas de Reel) ; {autres} : 2 Reels et 1 story chacun.",
              # 09/10 : plus de Drive perso, les vidéos de la créatrice ; l'étape 6 n'est plus que la story à la une
              5: "publie une vidéo de {creatrice}, modifiée avant, sur {vivants}. Appuie sur ✅ quand c'est fait.",
              6: "sur {pointent_court}, une story avec le widget de mention du compte {nprive}, puis mets-la à la une. Appuie sur ✅ quand c'est fait.",
              7: "2 Reels sur chacun de ces comptes : {autres}. 1 story avec le widget vers ta story à la une."}


def en_bienvenue(fiche_p: dict) -> bool:
    """09/10 : la bienvenue est partie et le compte 1 pas encore (étape 1 sans date, en attente du « ✅ C'est fait » ou des 3 h).
    09/10 (revue : un remplacement des comptes BAN vide les dates d'un nouveau encore à l'étape 1 ; la fiche redevenait « en
    bienvenue » et forcer_etape ne lui envoyait jamais son nouveau compte 1) : une bienvenue close (« bienvenue_ok », compte 1 déjà
    donné une fois) ne compte plus jamais."""
    f = fiche_p or {}
    return (int(f.get("etape", 0) or 0) == 1 and bool(f.get("bienvenue")) and not f.get("bienvenue_ok")
            and not (f.get("dates") or {}).get("1"))


def attente_compte_1(fiche_p: dict, majuscule: bool = False, sep: str = " ") -> str:
    """11/10 (vérification L1 : « écris à Gaëtan… puis appuie sur ✅. Ton compte 1 arrive juste après » restait dans le message du
    matin, `!etape` et l'assistant, alors que ce ✅ ne fait plus que prévenir Gaëtan) : la bienvenue qui attend encore son compte 1
    (filet : membre introuvable à l'instant de la bienvenue). Le compte 1 arrive par le programme, au plus tard BIENVENUE_H h après ;
    le WhatsApp n'est redemandé qu'à qui ne l'a pas déclaré. Une ligne par paragraphe, une seule action."""
    return f"{'T' if majuscule else 't'}on compte Croissance 1 arrive ici dès que sa préparation est vérifiée."



def prochaine_etape(salon_id, maintenant=None) -> str:
    """La ligne « 👉 Aujourd'hui » du message du matin, d'après l'étape du clipper dont c'est le salon."""
    maintenant = maintenant or datetime.now(timezone.utc)
    for uid, fiche_p in _lire().items():
        if str(fiche_p.get("salon_id")) != str(salon_id):
            continue
        n = int(fiche_p.get("etape", 0))
        if n not in PROCHAINES:
            return "" if n else "attends ta créatrice, ton manager te l'attribue."
        if en_bienvenue(fiche_p):                                       # 09/10 ; 11/10 : le compte 1 arrive seul, sans ✅
            return attente_compte_1(fiche_p)
        comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)               # 01/10 : le même ordre que les étapes (plus la liste brute)
        c = {f"compte{i + 1}": (comptes[i] if i < len(comptes) else "…") for i in range(3)}
        vivants = _vivants(uid, fiche_p, comptes[:3])                   # 01/10 : sans les comptes BAN
        np_ = n_prive(fiche_p)                                          # 08/10 : le privé en 2 pour les nouveaux
        c["vivants"] = _liste(vivants)
        c["autres"] = _liste([h for h in vivants if h != c[f"compte{np_}"]])
        c.update({"nprive": np_, "prive2": ", le privé" if np_ == 2 else "", "prive3": ", le privé" if np_ == 3 else "",
                  "pointent_court": "les comptes 1 et 3" if np_ == 2 else "les comptes 1 et 2",
                  "creatrice": fiche_p.get("creatrice") or "ta créatrice"})
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
            m = _bloque_sources(uid, fiche_p, a[0])                     # 09/10 : toutes ses sources BAN
            if m:                                                       # 01/10 (relecture) : plus de « tes autres comptes » fantôme
                return texte_bloque(m)[0].lower() + texte_bloque(m)[1:]
            srcs = [src for src, _ in reels_detail(uid, fiche_p, a[0])] or [source_reels(fiche_p, a[0])]
            ou = " et ".join(f"ton compte {x}" for x in srcs)
            if fiche_p.get("ligne_attendue") == a[0]:                  # 11/10 (lot W) : le texte de son message d'attente
                return f"ton compte {a[0]} arrive dès qu'il est prêt. D'ici là : 2 Reels par jour sur {ou}."
            if reels_pour(uid, fiche_p, a[0]) >= REELS_OUVERTURE:
                return f"ton compte {a[0]} arrive ici le {_date_fr(a[1])}. D'ici là : 2 Reels par jour sur {ou}."
            if maintenant < a[1]:
                return (f"2 Reels par jour sur {ou}. Ton compte {a[0]} arrive ici au plus tôt le {_date_fr(a[1])}, "
                        f"dès que je vois {condition_texte(uid, fiche_p, a[0])}.")
            # 01/10 (relecture, règle 30) : plus de « Prends-les dans ton Drive », qui laissait publier sans modifier
            # 09/10 : plus de Drive perso : les vidéos de sa créatrice
            return (f"ton compte {a[0]} arrive dès que je vois {condition_texte(uid, fiche_p, a[0])}.\n\n"
                    f"Prends une vidéo de {fiche_p.get('creatrice') or 'ta créatrice'} et modifie-la avant de la publier.")
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
    if not morceaux and not fiche:
        try:                                                            # 08/10 : un ancien du roster de Jonas, absent du registre
            import roster as _roster
            m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
            n_ = _deps.get("normaliser") or (lambda t: (t or "").strip().lower())
            role_equipe = m is not None and any(n_(r.name) in {"clippeur", "rookie"} for r in getattr(m, "roles", []) or [])
            prenom = (m.display_name.split() or [""])[0] if m is not None else ""
            if role_equipe and prenom and _roster.actif() and _roster.est_actif(prenom):   # (revue : jamais un homonyme sans rôle)
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
                    "Règle du lien : seulement dans la bio de son compte privé (le 3e chez les anciens) ; ses comptes qui publient : "
                    "une story à la une avec le widget de mention du compte privé")
    if n == 0:
        etape = "parcours pas encore commencé (il attend sa créatrice et son compte 1)"
    elif n == 1 and _compte_1_retenu(fiche_p):                          # 11/10 (revue du lot W) : pas de ligne pour le compte 1
        etape = f"compte 1 {TEXTE_ATTENTE_LIGNE_1}"
    elif en_bienvenue(fiche_p):                                         # 09/10 ; 11/10 : plus de ✅ qui retient le compte 1
        etape = attente_compte_1(fiche_p)
    elif n in ETAPES:
        etape = titre_etape(fiche_p, n)
        a = attente(fiche_p)
        if a and a[0] == n and fiche_p.get("ligne_attendue") == n:     # 11/10 (lot W) : il attend une ligne, pas ses Reels
            etape = f"attente du compte {n}, {TEXTE_ATTENTE_LIGNE}"
        elif a and a[0] == n:
            etape = (f"attente du compte {n} : il arrive dès que "
                     f"le scan voit {condition_texte(uid, fiche_p, n)}")
    else:
        etape = "parcours terminé (routine)"
    np_ = n_prive(fiche_p)
    autres_c = "comptes 1 et 3" if np_ == 2 else "comptes 1 et 2"
    return (f"étape : {etape} · comptes créés : {crees} sur 3 · "
            f"compte privé : le compte {np_} · règle du lien : seulement dans la bio du compte {np_} privé ; {autres_c} : une story "
            f"à la une avec le widget de mention du compte {np_}")


OUBLI_JOURS = 14                                                        # 09/10 : durée de la trace gardée par `oublier`


def _fichier_oublis():
    from pathlib import Path
    return Path(str(_deps["FICHIER_PARCOURS"])).with_name("parcours_oublis.json")


def _reprendre_trace(uid: str, salon, creatrice: str):
    """09/10 (revue, « 🔄 Je reprends ») : la trace laissée par `oublier`, consommée ici. Renvoyée seulement si le parcours repart dans
    le MÊME salon, pour la même créatrice, depuis moins de OUBLI_JOURS jours (sa bienvenue est encore au-dessus) ; None sinon."""
    try:
        traces = _deps["lire_json"](_fichier_oublis(), {})
        t = traces.pop(str(uid), None)
        if t is None:
            return None
        _deps["ecrire_json"](_fichier_oublis(), traces)
        quand = datetime.fromisoformat(str(t.get("quand")))
        quand = quand if quand.tzinfo else quand.replace(tzinfo=timezone.utc)
    except Exception as erreur:                                         # noqa: BLE001 — sans trace : la bienvenue, comme avant
        journal.info("Trace du parcours de %s : %s", uid, type(erreur).__name__)
        return None
    if (str(t.get("salon_id")) != str(getattr(salon, "id", "")) or _cle_creatrice(t.get("creatrice")) != _cle_creatrice(creatrice)
            or datetime.now(timezone.utc) - quand > timedelta(days=OUBLI_JOURS)):
        return None
    return t


def oublier(uid: str) -> bool:
    """Retire la fiche de parcours d'un clipper (salon perso supprimé le 26/09) : plus de warm-up ni d'étape postés nulle part.
    09/10 (revue : la réservation expirée efface la fiche, puis « 🔄 Je reprends » renvoyait une 2e bienvenue) : une trace courte
    (salon, créatrice, bienvenue, WhatsApp) est gardée OUBLI_JOURS jours à part, pour que demarrer_parcours ne la repose pas."""
    d = _lire()
    if str(uid) not in d:
        return False
    f = d.pop(str(uid), None) or {}
    _ecrire(d)
    if isinstance(f, dict) and int(f.get("etape", 0) or 0) >= 1 and f.get("salon_id"):
        try:
            limite = (datetime.now(timezone.utc) - timedelta(days=OUBLI_JOURS)).isoformat(timespec="seconds")
            traces = {u: t for u, t in _deps["lire_json"](_fichier_oublis(), {}).items()
                      if isinstance(t, dict) and str(t.get("quand") or "") >= limite}
            traces[str(uid)] = {"quand": _maintenant(), "salon_id": str(f.get("salon_id")), "creatrice": f.get("creatrice", ""),
                                "bienvenue": f.get("bienvenue", ""), "message": (f.get("messages") or {}).get("bienvenue", ""),
                                "whatsapp": f.get("whatsapp", ""), "whatsapp_par": f.get("whatsapp_par", "")}
            _deps["ecrire_json"](_fichier_oublis(), traces)
        except Exception as erreur:                                     # noqa: BLE001 — la fiche est oubliée quand même
            journal.info("Trace du parcours de %s : %s", uid, type(erreur).__name__)
    return True


async def forcer_etape(salon, membre, creatrice: str, n: int) -> None:
    """Pose l'étape n (date du jour, utile au compte des jours de warm-up) et l'envoie dans le salon. 09/10 (identifiants reçus
    jusqu'à 4 fois : `!salons-equipe`, salon d'ancien rouvert, roster au démarrage) : l'étape déjà envoyée (étape en cours n, datée)
    n'est jamais renvoyée. `!etape @x n` du staff, lui, renvoie toujours (envoyer_etape)."""
    d = _lire()
    uid = str(membre.id)
    deja = d.get(uid) or {}
    if int(deja.get("etape", 0) or 0) == int(n) and (deja.get("dates") or {}).get(str(n)):
        journal.info("Étape %s de %s déjà envoyée : pas de renvoi", n, uid)
        return
    a = attente(deja)
    if (a and a[0] == int(n)) or (int(n) == 1 and en_bienvenue(deja)):
        # 09/10 : ce compte attend déjà son tour (48 h et 4 Reels, ou le ✅ de la bienvenue) : la règle n'est jamais sautée ici
        if int(n) == 1 and en_bienvenue(deja) and not any(x.get("type") == "etape" and int(x.get("n") or 0) == 1
                                                          for x in deja.get("programme") or []):
            # 09/10 (revue : un remplacement vide le programme) : le compte 1 garde son filet des BIENVENUE_H heures, jamais sans
            try:
                depart = datetime.fromisoformat(str(deja.get("bienvenue")))
                depart = depart if depart.tzinfo else depart.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                depart = datetime.now(timezone.utc)
            deja.setdefault("programme", []).append({"quand": (depart + timedelta(hours=BIENVENUE_H)).isoformat(timespec="seconds"),
                                                     "type": "etape", "n": 1})
            _ecrire(d)
        journal.info("Étape %s de %s déjà programmée : pas d'envoi forcé", n, uid)
        return
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
    elif n == 6:
        # 11/10 (lot W, contre-vérification du lot L1 : l'ancien repris avec ses 3 comptes créés recevait encore la story à bouton
        # et attendait son app jusqu'à 24 h) : comme un nouveau au « Profil fait » du privé, la story sans bouton, puis la routine
        # et l'app. Déjà à l'étape 6 ou au-delà (envoyée) : rien n'est renvoyé, comme forcer_etape.
        uid = str(membre.id)
        d = _lire()
        deja = d.get(uid) or {}
        e = int(deja.get("etape", 0) or 0)
        if e >= 6 and (deja.get("dates") or {}).get(str(e)):
            journal.info("Étape %s de %s déjà envoyée : pas de story renvoyée", e, uid)
            return n
        dates_d = deja.get("dates") or {}
        if 1 <= e <= 3 and dates_d.get(str(e)):
            # 11/10 (revue du lot W : `!salons-equipe` relancé sur un clipper au profil de son privé, « Profil fait » pas appuyé :
            # la fiche passait à l'étape 7 sans « 3_fait », et le bouton restait, mort) : le privé dont le profil est parti se
            # ferme comme à l'appui (3_fait, bouton retiré, story puis routine) ; toute autre étape 1 à 3 en cours suit son cours.
            if e == n_prive(deja) and (deja.get("profils") or {}).get(str(e)) and not dates_d.get(f"{e}_fait"):
                await valider_etape(salon, uid, e, par="bot")
            else:
                journal.info("Étape %s de %s en cours : le parcours suit son cours", e, uid)
            return n
        fiche_p = d.setdefault(uid, {"prenom": _prenom(membre), "creatrice": creatrice, "salon_id": str(salon.id), "etape": 0,
                                     "dates": {}, "notes": []})
        fiche_p.update({"etape": 7, "salon_id": str(salon.id), "creatrice": creatrice or fiche_p.get("creatrice", "")})
        fiche_p.setdefault("dates", {})["6"] = _maintenant()            # le lien donné : controler_liens_bio compte de là
        fiche_p.pop("warmup_jour", None)
        fiche_p["story_due"] = _maintenant()                            # 11/10 (revue du lot W) : rattrapée si le bot s'arrête
        _ecrire(d)
        await story_puis_app(salon, membre, uid, fiche_p)
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


def reels_apres(historique: list, quand) -> int:
    """09/10 (revue) : les publications vues par les passages du scan des jours qui suivent `quand` (le passage du jour même couvre
    surtout la veille : il ne compte pas, jamais un Reel d'avant la création du compte 2 dans les « 4 de plus »)."""
    jour0 = quand.date().isoformat() if quand is not None else ""
    return sum(int(e.get("posts") or 0) for e in historique or [] if e.get("existe") and str(e.get("jour", ""))[:10] > jour0)


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
    douteux = verifier_prive2(d)                                        # 09/10 (revue) : signalé une fois, jamais renuméroté
    change = bool(douteux) or change
    for uid, fiche_p in d.items():
        comptes = _comptes_ordonnes(uid, fiche_p=fiche_p)
        if not comptes or not isinstance(fiche_p, dict):
            continue
        bans = sorted(h.lower() for h in comptes if _derniers_etats.get(h.lower()) == "ban")
        if bans != sorted(fiche_p.get("bans") or []):
            fiche_p["bans"] = bans
            change = True
        if reels_72h is None:
            continue
        if fiche_p.pop("reels_soir", None) is not None:                # 08/10 (revue) : le passage complet les compte déjà
            change = True
        for i, h in enumerate(comptes[:3], start=1):
            if not _cree(fiche_p, i) or _derniers_etats.get(h.lower(), "") in ("", "a creer", "à créer"):
                continue
            avant = (fiche_p.get("reels") or {}).get(h.lower())
            apres = _cumuler_reels(avant, int((reels_72h or {}).get(h.lower(), 0) or 0), jour)
            if historique is not None:                                  # 08/10 : le vrai cumul, jamais en baisse
                hist_h = historique.get(onboarding.normaliser_handle(h).lower(), [])
                somme = reels_depuis(hist_h, _date_creation(fiche_p, i))
                apres["vus"] = max(int(apres.get("vus", 0) or 0), somme)
                t2 = _date_creation(fiche_p, 2)
                if i == 1 and (fiche_p.get("base_reels") or {}).get("3") is not None and t2 is not None:
                    # 09/10 (revue) : les Reels du compte 1 publiés après la création du compte 2, jamais en baisse
                    apres["apres_base"] = max(int((avant or {}).get("apres_base", 0) or 0), reels_apres(hist_h, t2))
            preuves = [p for e in (historique or {}).get(onboarding.normaliser_handle(h).lower(), [])
                       for p in e.get("publications_verifiees") or []]
            apres["reels_verifies_v2"] = process_clippeur.cumuler_reels_verifies(
                avant, preuves, _date_creation(fiche_p, i), datetime.now(timezone.utc))
            apres["publications_verifiees"] = process_clippeur.cumuler_publications(
                avant, preuves, _date_creation(fiche_p, i), datetime.now(timezone.utc))
            if apres != avant:
                fiche_p.setdefault("reels", {})[h.lower()] = apres
                change = True
    if change:
        _ecrire(d)
    if douteux:
        dit = False
        try:
            canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
            if canal is not None:
                lignes = [f"· {(d.get(u) or {}).get('prenom') or u} (<@{u}>) : compte 2 `{h}`{r}" for u, h, r in douteux]
                await canal.send(("🔒 **Compte privé à vérifier** (fiches du 08/10, privé en 2). Le bot traite leur compte 2 comme le "
                                  "privé : le lien et la story à la une. Vérifie avec eux lequel est leur compte privé :\n"
                                  + "\n".join(lignes))[:1900])
                dit = True
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Alerte « prive2 » : %s", erreur)
        if not dit:                                                     # pas prévenu : on retentera au scan suivant
            d = _lire()
            for u, _, _ in douteux:
                (d.get(u) or {}).pop("prive2_alerte", None)
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


def _code_appel_llm() -> str:
    """11/10 (revue du lot W) : le code de l'appel d'un compte banni, pour l'assistant, dit comme la règle 23 des INSTRUCTIONS et
    etat_des_comptes : par le bouton si CODES_APPEL=1, sinon il ne passe pas par le bot (règle des codes du 10/10)."""
    if codes_2fa.CODES_APPEL:
        return f"le code dans #{codes_2fa.SALON_CODES_NOM} avec le bouton « 📩 Mon code »"
    return "le code de l'appel ne passe pas par le bot : il arrive chez l'équipe, qui lui répond dans son salon perso"


def contexte_llm(uid: str) -> str:
    """Le bloc de contexte ajouté à chaque question posée dans le salon perso : le bot y est le manager."""
    return ("[Salon perso : ici tu es l'ASSISTANT du clipper au quotidien (pas son manager). Tu parles comme à un élève de collège : phrases de "
            "10 mots maximum, mots simples, une action par ligne, jamais de parenthèses. Réponds court, une action à la fois, tutoie, "
            # 01/10 (relecture) : plus de `!code` seul, qui faisait dire « tape !code » dans le salon perso
            "guide-le selon son étape en cours, renvoie aux fiches du forum et à `!mesclics` (ses visites) ; pour un code, "
            "la phrase canonique ci-dessous. Les comptes se créent ici, guidés par le parcours : plus de créneau "
            "lundi/mercredi/vendredi, plus de contrat, plus de distinction France/International. Ne redonne jamais un mot "
            # 09/10 (Gaëtan) : la paie des clippers tombe les 5 et 20
            "de passe. Paie : vérifie le régime individuel ; un forfait fixe n’est jamais une paie au clic. Les visites et la rémunération sont distinctes. "
            # 01/10 (Gaëtan) : une seule règle des comptes, pour tous, mot pour mot ; une seule phrase pour les codes
            f"Règle des comptes (01/10), à redire mot pour mot : « {regle_comptes(_lire().get(str(uid)))} » "
            "Jamais « un compte par jour », jamais « demain », jamais un autre nombre de Reels, jamais de période d'essai ; tu ne "
            "promets jamais de date pour le compte suivant et tu ne pousses jamais à créer un compte que le bot n'a pas encore "
            "ouvert. Aucun délai supplémentaire pour débloquer le compte suivant : seules les quatre publications vérifiées du compte précédent comptent. "
            "puis CE compte publie 2 Reels et 1 story par jour, sans attendre les autres — ne dis jamais « une semaine de warm-up » "
            f"ni « dans 7 jours ». Les codes Instagram, une seule phrase : « {texte_codes()} » Jamais de commande à taper pour un code, "
            "jamais « le code arrive ici tout seul ». La ligne « État de chaque "
            "compte » de la mémoire FAIT FOI : tu ne la contredis jamais, ni le message d'étape posté dans le salon. "
            # 09/10 (Gaëtan : « Enlève le truc qui envoie un dossier Drive au clippeur ») : plus de Drive perso ni de TOP 20 à lui
            "Ses vidéos sont celles de sa créatrice, en qualité d'origine : le lien est dans son message de bienvenue et dans « ton "
            "compte 1 peut publier », sinon dans le salon ℹ️ de sa créatrice. Il n'a plus de dossier Drive à lui : tu n'en parles "
            "jamais. Il modifie chaque vidéo avant de la publier. La story du jour : une photo ou une courte vidéo de sa créatrice. "
            "Il demande OÙ prendre "
            "la story : tu réponds au où, pas au widget. Un compte BAN ne change rien pour les autres : ils continuent. "
            "On ne réutilise jamais une info d'un compte BAN (identifiant, e-mail, mot de passe) pour un autre compte. "
            # 11/10 (revue du lot W, règle des codes du 10/10) : même formule que la règle 23 et etat_des_comptes ; plus de « !code »
            f"Un compte banni (30/09) : il fait appel lui-même, tout de suite (« Contester la décision », {_code_appel_llm()}, "
            "selfie vidéo, son "
            "numéro ou sa pièce d'identité si Instagram les demande, jamais ceux d'un autre, jamais sa pièce d'identité dans Discord) ; "
            "tu ne promets jamais un compte neuf "
            "ni une date (« demain ») : si l'appel échoue, Gaëtan décide. "   # 01/10 (relecture) : une seule version du ban
            f"Le lien (05/10) : il n'existe qu'avec le compte PRIVÉ — pour CE clipper le compte {n_prive(_lire().get(str(uid)) or {})} "
            "(le 3 dans le nouveau parcours ; tout ancien ordre ambigu demande une vérification) — dans le champ « Liens » de son profil (Modifier le profil → Liens), jamais dans le texte de la bio, et nulle part ailleurs ; "
            "les comptes de croissance ne portent jamais de lien : une story (photo ou vidéo) avec le widget de mention du compte privé, "
            "mise à la une, une seule fois ; chaque jour une story avec le widget vers cette story à la une. Deux comptes de croissance "
            "qui publient, et un compte privé qui ne publie pas. Aucun compte ancien n’est réattribué. On se "
            "connecte uniquement à son propre compte déjà créé ; un compte réservé neuf doit être créé. Le Drive s'ouvre par son lien, jamais besoin d'une adresse e-mail. "
            "Ne redemande jamais une preuve déjà présente dans la mémoire ou le fil. Une absence de mesure ne vaut ni zéro publication ni ban. Quand il dit qu'une étape est faite, dis-lui de cliquer le bouton ✅ sous le message de l'étape, ou d'écrire "
            "`!etape` pour la revoir. Appelle-le par son prénom (celui de la mémoire), jamais par celui de la créatrice. "
            "Trois lignes maximum. La ligne « 👉 Prochaine étape : … » seulement si elle dit autre chose que l'étape déjà "
            "affichée dans le salon avec son bouton. Aucune question inutile (modèle de téléphone, « dis-moi quand c'est "
            "fait »). Tu ne parles que des comptes CRÉÉS d'après la mémoire : jamais « tes deux autres comptes » s'ils "
            "n'existent pas encore. Tu ne donnes jamais la cause d'un blocage, seulement la marche à suivre ; « déconnecté, "
            f"mot de passe modifié » = se reconnecter avec le mot de passe de son étape, puis le code de connexion avec le "
            f"bouton « 📩 Mon code » dans #{codes_2fa.SALON_CODES_NOM} ; s'il ne marche plus, "
            "signale le problème à son équipe dans ce salon personnel, sans recopier de secret. "
            + (f"Le bouton « 📩 Mon code » ne donne QUE les codes reçus par e-mail "
               f"({'création, connexion, appel' if codes_2fa.CODES_APPEL else 'création et connexion'}), jamais ceux qui changent "
               "l'e-mail, le mot de passe ou le numéro. " if codes_2fa.SECURITES else
               "Le bouton « 📩 Mon code » donne le dernier code Instagram reçu par e-mail, quel qu'il soit (12/10). ")
            + "Instagram demande un NUMÉRO de téléphone : il met LE SIEN et reçoit le SMS (décision du 26/09), ce numéro ne "
            "sert qu'à ses 3 comptes. Instagram demande un SELFIE VIDÉO : il le fait lui-même, avec son visage, c'est normal. "
            "Jamais de « compte prêt à l'emploi », jamais « ton manager a une autre solution » : si tu ne sais pas, renvoie vers "
            "son équipe ici, dans son salon personnel. Aucune confirmation WhatsApp ne conditionne son arrivée. "
            "Ne recopie jamais la ligne [Contexte : …].]\n"
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
    # 09/10 : « ! pseudo » (espace du clavier) et « !Pseudo » (majuscule) valent `!pseudo`
    mots = re.sub(r"^!\s+", "!", (texte or "").strip()).split()
    reste = [m for m in mots[1:] if not m.startswith("<@")] if mots and mots[0].lower() == "!pseudo" else []
    if len(reste) != 2 or not reste[0].isdigit() or int(reste[0]) not in (1, 2, 3):
        # 09/10 : un exemple réaliste (lui-même refusé s'il est recopié), plus « ton_identifiant »
        await message.reply(f"Écris `!pseudo`, le numéro du compte (1, 2 ou 3) et ton vrai @. Par exemple : `!pseudo 1 {EXEMPLE_PSEUDO}`")
        return True
    uid, n = str(membre.id), int(reste[0])
    if not staff:
        salon = _deps["salon_perso"](uid) if _deps.get("salon_perso") else None
        if salon is None or getattr(message.channel, "id", None) != salon.id:
            await message.reply("Tape `!pseudo` dans ton salon perso.")
            return True
    nouveau = onboarding.normaliser_handle(reste[1]).lower()
    _, raison = await renommer(uid, n, nouveau)                         # 09/10 : la même fonction que la fenêtre de création
    if raison == RAISON_EXEMPLE:                                        # 09/10 : `!pseudo 1 ton_identifiant` recopié
        await message.reply(f"❌ Écris le vrai @ de ton compte, par exemple : `!pseudo {n} {EXEMPLE_PSEUDO}`")
        return True
    if raison:
        await message.reply(f"❌ Pas changé : {raison}.")
        return True
    await message.reply(f"✅ C'est noté : ton compte {n} est maintenant `{nouveau}`. Je le suis sous ce nom.")
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
        if en_bienvenue(fiche_p):                                       # 09/10 ; 11/10 : le compte 1 arrive seul, sans ✅
            await message.reply(attente_compte_1(fiche_p, majuscule=True, sep="\n\n"))
            return True
        # 05/10 : plus de renvoi de l'étape entière (identifiants compris) : le titre et le lien vers le message d'origine
        mid = (fiche_p.get("messages") or {}).get(str(n))
        guild = getattr(message, "guild", None)
        lien_m = f"https://discord.com/channels/{guild.id}/{message.channel.id}/{mid}" if (mid and guild is not None) else ""
        if fiche_p.get("ligne_attendue") == n:                          # 11/10 (L3) : son compte attend une ligne, pas ses Reels
            await message.reply(TEXTE_COMPTE_ATTENDU.format(n=n))
            return True
        a = attente(fiche_p)
        if a and a[0] == n:
            await message.reply(f"Ton compte {n} arrive automatiquement ici, "
                                f"dès que je vois {condition_texte(uid, fiche_p, n)}.")
            return True
        await message.reply(f"📍 **{titre_etape(fiche_p, n)}**" + (f"\n\nTon message d'étape est là : {lien_m}" if lien_m else "")
                            + ("" if n == 7 else "\n\nFait ? Appuie sur son bouton ✅."))
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
    # 08/10 (revue) : en ordre « prive2 », l'étape 6 (le lien) part À CÔTÉ du parcours tant que les comptes 2 et 3 sont en cours ;
    # en faire l'étape en cours perdait le compte 3 en silence (programme retiré, routine, app). Sauter le compte 3 : `!etape @x 7`.
    f_n = _lire().get(uid) or {}
    a_cote = n == 6 and ordre(f_n) == "prive2" and int(f_n.get("etape", 0) or 0) in (2, 3)
    if a_cote:
        d = _lire()
        if uid in d:
            (d[uid].get("dates") or {}).pop("6_fait", None)
            _ecrire(d)
    if not await envoyer_etape(salon, membre, n, pointer=not a_cote):
        # 11/10 (vérification du lot L3 : « 📍 Étape 3 envoyée » répondu alors que rien n'était parti, faute de ligne)
        f_r = _lire().get(uid) or {}
        if f_r.get("ligne_attendue") == n:
            await message.reply(f"⏳ Pas de ligne libre chez {f_r.get('creatrice') or 'sa créatrice'} : le compte {n} de "
                                f"{membre.display_name} part tout seul dès qu'une ligne existe.")
        elif any(x.get("ligne") and int(x.get("n") or 0) == n for x in f_r.get("programme") or []):
            await message.reply(f"⏳ Étape {n} de {membre.display_name} pas encore partie (classeur des logins illisible) : "
                                "nouvel essai au prochain tour du programme.")
        else:
            await message.reply(f"⚠️ Étape {n} pas envoyée à {membre.display_name} : <#{salon.id}> refuse le message.")
        return True
    await message.reply(f"📍 Étape {n} envoyée à {membre.display_name} dans <#{salon.id}>"
                        + (" (à côté du parcours : son compte 3 attend toujours)." if a_cote else "."))
    return True
