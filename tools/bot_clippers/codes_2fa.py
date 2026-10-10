"""Codes Instagram des clippers : liste blanche, réponse privée, un seul lecteur de la boîte (10/10/2026).

POURQUOI : chaque compte Instagram de l'agence est créé avec un alias iCloud « Masquer mon adresse » qui renvoie vers UNE
boîte Gmail. Le bot lit cette boîte et donne au clipper le code qu'Instagram vient de lui envoyer.

RÈGLE DE GAËTAN DU 10/10 (mot pour mot) : « Il faut qu'il n'y ait aucun problème de 2FA. Il faut que les 2FA et les codes
que tu renvoies dans le salon code Instagram soient uniquement les codes de connexion et de création de compte, pas de
modifications de données importantes, uniquement ces codes-là. »

CE QUE FAIT LE MODULE :
1. LISTE BLANCHE (classer) : un code ne part au clipper que si l'ADRESSE de l'expéditeur est Instagram (ou Meta pour un
   mail qui parle d'Instagram), réécriture iCloud comprise, jamais le seul nom affiché ; que le sujet ou le début du
   corps écrit un but de CONNEXION ou de CRÉATION de compte (FR, EN, DE, ES, PT, IT) ; et qu'aucun mot de la liste
   noire n'y figure (mot de passe, récupération, e-mail, numéro, 2FA, Espace Comptes, suppression, pseudo, sauvegarde,
   changement, appel…). Les phrases « si ce n'était pas vous… » sont retirées avant la lecture. Un mail HTML seul est
   d'abord converti en texte (CSS et scripts retirés).
2. Tout autre code est GARDÉ : jamais montré à un clipper, jamais stocké ; une ligne au salon admin, sans le code.
   Un changement déjà fait (mot de passe, e-mail, numéro, 2FA, Espace Comptes, pseudo, suppression) : une alerte admin
   « ⚠️ changement sur le compte @x : … », une fois par e-mail.
3. Code d'appel après un ban : gardé par défaut ; CODES_APPEL=1 le donne, seulement si l'e-mail ne parle que d'appel.
4. Le clipper reçoit son code en PRIVÉ : bouton persistant « 📩 Mon code » épinglé dans #🔐-code-instagram (réponse
   éphémère, visible par lui seul) ; `!code` tapé y répond en message privé. Plus jamais de code dans le salon commun.
   Le code n'est donné qu'au clipper dont le salon perso porte l'adresse dans alias_codes.json.
5. UN seul lecteur IMAP (Lecteur) : incrémental par UID, en-têtes d'abord, corps seulement pour les mails Meta, IDLE si
   le serveur le permet (sinon toutes les CODES_SONDAGE_SEC secondes). Le bouton, `!code`, la boucle des codes et
   bans_mail lisent tous ce flux : plus personne ne re-télécharge la boîte.
6. Santé : boîte illisible, mot de passe d'application refusé, boîte pleine, code reçu sur une adresse rattachée à
   personne → une ligne admin, une fois par heure au plus.

REVUE DU 10/10 (2e passe, 17 défauts corrigés) :
- filtre : une phrase « si ce n'était pas vous » qui porte le code ou le mot « code » est lue (et garde le code si c'est elle
  qui le porte) ; liste noire complétée (sécuriser, retrouver l'accès, restaurer, débloquer, « à nouveau », Facebook,
  Threads, déconnexion…) ; tirets Unicode et caractères invisibles neutralisés ; le pseudo ne compte jamais comme but ; un
  mail écrit dans aucune des 6 langues est gardé ; la liste noire lit TOUT le mail (texte, HTML, <title>, textes alternatifs) ;
  « confirm your identity », « restore » et « unlock » seuls ne suffisent plus ;
- lecteur : l'UID n'avance qu'au bout d'un passage réussi (une coupure ne perd plus rien), un mail illisible est rejoué
  puis sauté avec une ligne admin, IDLE robuste, réécriture iCloud tolérante et jamais d'écart en silence ;
- Discord : le guet continue après un code (le 2e code remplace le 1er tout seul), il relit les adresses du clipper, un salon
  lu par des clippers n'est jamais « privé », une ligne admin ne recopie jamais un code ;
- CODES_PREUVE_RELAIS : « observer » (défaut) ou « 1 » pour exiger la preuve Gmail qu'un mail iCloud vient bien de Meta.
"""

import asyncio
import email
import email.utils
import html
import imaplib
import json
import os
import re
import select
import socket
import ssl
import time
import unicodedata
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

import discord

journal = __import__("logging").getLogger("bot_clippers")


def _oui(nom: str, defaut: str = "0") -> bool:
    return os.environ.get(nom, defaut).strip().lower() not in ("", "0", "non", "false", "off", "no")


IMAP_HOST = os.environ.get("CODES_IMAP_HOST", "imap.gmail.com").strip()
IMAP_USER = os.environ.get("CODES_IMAP_USER", "").strip()
IMAP_PASSWORD = os.environ.get("CODES_IMAP_PASSWORD", "").strip()
# Dossier/libellé lu (Gmail : un libellé = un dossier IMAP), plus le Spam où Meta tombe souvent.
IMAP_DOSSIER = os.environ.get("CODES_IMAP_DOSSIER", "INBOX").strip() or "INBOX"
DOSSIER_SPAM = os.environ.get("CODES_IMAP_SPAM", "[Gmail]/Spam").strip()
IMAP_TIMEOUT = int(os.environ.get("CODES_IMAP_TIMEOUT_SEC", "30") or 30)
ROLE_MANAGER_NOM = os.environ.get("ROLE_MANAGER_NOM", "Manager").strip()
# 10/10 : IDLE au plus SONDAGE_SEC secondes (le code arrive en quelques secondes), sinon une lecture toutes les SONDAGE_SEC.
SONDAGE_SEC = int(os.environ.get("CODES_SONDAGE_SEC", "20") or 20)
ATTENTE_SEC = int(os.environ.get("CODES_ATTENTE_SEC", "300") or 300)    # le guet après « 📩 Mon code » : 5 min
FRAIS_MIN = int(os.environ.get("CODES_FRAIS_MIN", "5") or 5)            # au-delà, « ancien code » et le guet continue
SALON_CODES_MINUTES = int(os.environ.get("CODES_SALON_MINUTES", "60") or 60)
CACHE_MIN = max(SALON_CODES_MINUTES, 120)                               # 2 h pour `!code` d'un manager dans son salon
JOURS_AMORCE = int(os.environ.get("BANS_JOURS", "3") or 3)              # premier passage : les mails Meta de 3 jours
AMORCE_MAX = int(os.environ.get("CODES_AMORCE_MAX", "120") or 120)
QUOTA_SEUIL = 0.9
# 10/10 (règle stricte de Gaëtan) : le code d'un appel après un ban est gardé ; CODES_APPEL=1 le donne au clipper.
CODES_APPEL = _oui("CODES_APPEL")
# 10/10 (revue) : un mail relayé par iCloud porte une adresse @icloud.com ; une adresse iCloud ORDINAIRE à la forme d'une
# réécriture (« <x>_at_instagram_com_<n> » chez icloud.com) passerait pour Instagram. « observer » (défaut) : rien n'est bloqué, une
# ligne admin par jour quand Gmail n'atteste pas la signature Meta ; « 1 » : un tel mail est ignoré. Format réel à vérifier.
PREUVE_RELAIS = (os.environ.get("CODES_PREUVE_RELAIS", "observer").strip().lower() or "observer")
# 10/10 (revue) : un mail précis illisible (FETCH refusé, corps vide) est rejoué ; au bout de ECHECS_AVANT_SAUT passages, sauté.
ECHECS_AVANT_SAUT = int(os.environ.get("CODES_ECHECS_AVANT_SAUT", "3") or 3)
FICHIER_ALIAS = None            # injecté par bot_discord.py (volume persistant)
SALON_CODES_NOM = os.environ.get("CANAL_CODES_NOM", "🔐-code-instagram").strip() or "🔐-code-instagram"
# 29/09 (Gaëtan : « restreins le salon au rôle Clippeur ») : le salon commun est réservé à l'équipe.
ROLES_SALON_CODES = tuple(r.strip() for r in os.environ.get("CODES_SALON_ROLES", "Clippeur,Rookie,Confirmé,Elite").split(",") if r.strip())
# Sous-chaînes cherchées côté serveur au PREMIER passage seulement (IMAP FROM) : un pré-filtre, l'adresse décide ensuite.
MOTS_EXPEDITEUR = ("instagram", "facebook", "meta.com", "meta_com")
COMMANDES_RECUP = ("!recup", "!récup", "!recuperation", "!récupération", "!appel", "!unban", "!deban")
COMMANDES_APPEL = ("!appel", "!unban", "!deban")
ID_BOUTON = "codes:mon-code"
VERSION_EXPLICATION = "7a" if CODES_APPEL else "7"                    # 10/10 (revue) : v7, code refusé et langues lues

# ------------------------------------------------------------------ textes
TEXTE_CODE_BRUT = f"Un code Instagram ? Va dans #{SALON_CODES_NOM} et appuie sur « 📩 Mon code »."
SUJET_SALON = "📩 Mon code : ton code Instagram de connexion ou de création de compte, visible par toi seul."
TEXTE_ATTENTE = ("⏳ Pas encore reçu.\n\nJe guette 5 minutes : ton code s'affiche ici tout seul dès que l'e-mail arrive. "
                 "Pas besoin de rappuyer.")
TEXTE_RIEN = ("😴 Toujours pas de code.\n\nVérifie que l'e-mail tapé dans Instagram est exactement celui de ton compte. "
              "Appuie sur « Renvoyer le code », attends 30 secondes, puis rappuie sur 📩 Mon code.")
TEXTE_PANNE = "⚠️ Je n'arrive pas à lire la boîte mail en ce moment.\n\nRéessaie dans 2 minutes. L'équipe est prévenue."
# 10/10 (revue) : la panne se dit tout de suite, plus au bout des 5 minutes de guet.
TEXTE_PANNE_GUET = ("⚠️ Je n'arrive pas à lire la boîte mail en ce moment. L'équipe est prévenue.\n\n"
                    "⏳ Je guette quand même 5 minutes : ton code s'affiche ici dès que la boîte répond.")
# 10/10 (revue, deux codes rapprochés) : le guet continue après un code ; un code plus récent remplace l'ancien tout seul.
TEXTE_REFUSE = ("-# Refusé par Instagram ? Appuie sur « Renvoyer le code » dans Instagram : le nouveau s'affiche ici tout "
                "seul, à la place de celui-ci.")
TEXTE_REFUSE_FIN = ("-# Refusé par Instagram ? Appuie sur « Renvoyer le code » dans Instagram, attends 30 secondes, puis "
                    "redemande ton code (📩 Mon code).")
TEXTE_SUITE = "↪️ Tu as redemandé ton code : il s'affiche dans la nouvelle réponse, plus bas."
TEXTE_PLUS_ADRESSE = ("🔒 Aucune adresse n'est plus rattachée à toi : je ne guette plus rien.\n\n"
                      "Une question ? Écris dans ton salon perso.")
TEXTE_GARDE = ("🔒 Le dernier e-mail reçu sur ton adresse n'est pas un code de connexion ni de création de compte : "
               "je ne le donne pas.\n\nL'équipe est prévenue.")
TEXTE_APPEL_GARDE = ("Appel après un ban : tu le fais toi-même. Le code de l'appel ne passe pas par le bot : il arrive chez "
                     "l'équipe, qui te répond dans ton salon perso.")
TEXTE_RECUP_REFUSE = ("🔒 Ce code-là ne passe pas par le bot. « 📩 Mon code » donne seulement les codes de connexion et de "
                      "création de compte.\n\nMot de passe oublié : ne le fais jamais, écris à ton manager dans ton salon perso."
                      + ("" if CODES_APPEL else "\n\n" + TEXTE_APPEL_GARDE))
TEXTE_MP = "📩 Je t'envoie ton code en message privé.\n\nPlus rapide : le bouton « 📩 Mon code »."
TEXTE_MP_FERMES = ("🔒 Tes messages privés sont fermés : je ne peux pas t'écrire.\n\n"
                   "Appuie sur le bouton : ton code s'affiche ici, pour toi seul.")
QUOI = {"creation": "création de compte", "connexion": "connexion", "appel": "appel après un ban"}


def explication_salon() -> str:
    """Le mode d'emploi épinglé (v7, revue du 10/10) : le bouton, les deux usages, le code refusé, les langues lues."""
    usages = "1️⃣ Créer un compte\n2️⃣ Te connecter" + ("\n3️⃣ Faire appel après un ban" if CODES_APPEL else "")
    return ("🔐 **Ton code Instagram, c'est ici.**\n\n"
            "Appuie sur **📩 Mon code** : ton code s'affiche pour toi seul. Personne d'autre ne le voit.\n\n"
            f"Il sert à {'3' if CODES_APPEL else '2'} choses, rien d'autre :\n\n{usages}\n\n"
            "➡️ Tu fais ta demande sur Instagram. Instagram t'envoie un e-mail. Tu appuies sur 📩 Mon code : le code "
            "arrive tout seul dès que l'e-mail est là. ✅\n\n"
            "🔁 Code refusé ? Appuie sur « Renvoyer le code » dans Instagram, sans fermer ta réponse : le nouveau remplace "
            "l'ancien tout seul, pendant 5 minutes.\n\n"
            "😴 Pas de code après 5 minutes ? Vérifie l'e-mail tapé dans Instagram, appuie sur « Renvoyer le code », "
            "puis rappuie sur 📩 Mon code.\n\n"
            "🌍 Je lis les e-mails d'Instagram écrits en français, anglais, espagnol, portugais, italien ou allemand. "
            "Instagram dans une autre langue : remets-le en français, sinon je ne donne pas le code.\n\n"
            + ("" if CODES_APPEL else "🛟 " + TEXTE_APPEL_GARDE + "\n\n")
            + "⛔ Mot de passe oublié, changer l'e-mail, le numéro, le mot de passe ou le pseudo, double authentification : "
            "ces codes-là, je ne les donne jamais.")


def actif() -> bool:
    return bool(IMAP_USER and IMAP_PASSWORD)


def _err(erreur) -> str:
    """01/10 : str(TimeoutError()) vaut "" — le type d'abord."""
    return f"{type(erreur).__name__} {erreur}".strip()


def _masquer(alias: str) -> str:
    """« orbite_machin.8i@icloud.com » → « orb…8i@icloud.com »."""
    if not alias or "@" not in alias:
        return "adresse inconnue"
    local, domaine = alias.split("@", 1)
    return f"{local[:3]}…{local[-2:]}@{domaine}" if len(local) > 5 else f"{local[:1]}…@{domaine}"


_CHIFFRES = re.compile(r"(?:FB-?)?\d[\d \u00a0.\-]{2,12}\d|(?:FB-?)?\d{4,}")


def _sans_code(texte: str) -> str:
    """Un sujet recopié au salon admin, codes masqués (« 956472 is your… » → « •••••• is your… »). 10/10 (revue) : un code
    écrit avec des espaces, des points ou des tirets (« 555 666 ») est masqué aussi, chiffres pleine chasse compris."""
    t = unicodedata.normalize("NFKC", str(texte or ""))
    return _CHIFFRES.sub(lambda m: "••••••" if len(re.sub(r"\D", "", m.group(0))) >= 4 else m.group(0), t)[:90]


def _cle(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation — pour comparer un nom de rôle à l'exact près."""
    t = unicodedata.normalize("NFD", (texte or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ registre des alias (alias_codes.json)
def _lire():
    if FICHIER_ALIAS and Path(FICHIER_ALIAS).exists():
        try:
            return json.loads(Path(FICHIER_ALIAS).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            journal.warning("alias_codes.json illisible, réinitialisé")
    return {}


def _ecrire(registre):
    if FICHIER_ALIAS:
        Path(FICHIER_ALIAS).write_text(json.dumps(registre, ensure_ascii=False, indent=2), encoding="utf-8")


_verrou_registre = (None, None)


def _verrou():
    """Un verrou asyncio (créé dans la boucle qui tourne) autour des lectures-écritures du registre."""
    global _verrou_registre
    boucle = asyncio.get_running_loop()
    if _verrou_registre[0] is not boucle:
        _verrou_registre = (boucle, asyncio.Lock())
    return _verrou_registre[1]


def salon_codes_id() -> str:
    """L'id du salon commun des codes, retenu dans le registre des alias (clé `_salon_codes`)."""
    try:
        return str((_lire().get("_salon_codes") or {}).get("id") or "")
    except Exception:                                                   # noqa: BLE001
        return ""


def texte_salon_codes() -> str:
    """La ligne canonique (10/10 : le bouton), avec le lien du salon quand son id est connu."""
    sid = salon_codes_id()
    return TEXTE_CODE_BRUT.replace(f"#{SALON_CODES_NOM}", f"<#{sid}>") if sid else TEXTE_CODE_BRUT


def adresses_de(salon_perso_id: str = "") -> set:
    """10/10 (règle : « le code n'est donné qu'au clipper dont l'alias est rattaché ») : les adresses rattachées à SON salon
    perso dans alias_codes.json, et rien d'autre. La fiche d'onboarding ne compte plus : une même adresse sur deux fiches
    donnait le code à deux clippers. Une adresse rattachée à personne déclenche une alerte admin (boucle_codes)."""
    adresses = set()
    if salon_perso_id:
        for alias, v in _lire().items():
            if "@" in alias and isinstance(v, dict) and str(v.get("canal_id")) == str(salon_perso_id):
                adresses.add(alias.strip().lower())
    return adresses


def rattacher(aliases, canal_id: str, par: str) -> int:
    """Rattache des adresses au salon qui recevra leurs codes (ce que fait `!alias ajouter`). Utilisé par l'onboarding :
    les e-mails des comptes du clipper → son salon perso. Renvoie le nombre d'alias posés."""
    registre = _lire()
    n = 0
    for alias in [str(a).strip().lower() for a in aliases if a and "@" in str(a)]:
        if registre.get(alias, {}).get("canal_id") == str(canal_id):
            continue
        registre[alias] = {"canal_id": str(canal_id), "par": str(par), "date": _maintenant().isoformat(timespec="seconds")}
        n += 1
    if n:
        _ecrire(registre)
    return n


def detacher(aliases) -> int:
    """Retire des adresses du registre (`!liberer` quand un clipper part). Renvoie le nombre d'alias retirés."""
    registre = _lire()
    n = 0
    for alias in [str(a).strip().lower() for a in aliases if a and "@" in str(a)]:
        if registre.pop(alias, None) is not None:
            n += 1
    if n:
        _ecrire(registre)
    return n


def _est_manager(membre, admin_ids) -> bool:
    """Admin, ou porteur du rôle Manager au nom EXACT (accents/casse/emoji ignorés)."""
    if str(getattr(membre, "id", "")) in admin_ids:
        return True
    cibles = {_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")} - {""}
    return any(_cle(r.name) in cibles for r in getattr(membre, "roles", None) or [])


# 01/10 (Ricardo « Code pour le compte 2 ») : une phrase courte autour du mot « code » vaut `!code`.
_MOT_SEUL = re.compile(r"!?\s*(codes?|r[ée]cup(?:[ée]ration)?)\s*[!?.]*", re.I)
_MOT_CODE = re.compile(r"(?<![\w-])codes?(?![\w-])", re.I)
_AUTRE_QUESTION = re.compile(r"(?<!\w)(comment|pourquoi|combien|quand)(?!\w)", re.I)
_MERCI = re.compile(r"(?<!\w)(merci|mrc|thanks?|thx)(?!\w)", re.I)
_CONFIRME = re.compile(r"(?<!\w)(bon|ok|okay|re[çc]u|marche|parfait|nickel|top|super|good)(?!\w)", re.I)
_NEGATION = re.compile(r"(?<!\w)(?:(?:pas|plus|toujours|jamais|rien|aucun|ne)(?!\w)|n['’])", re.I)


def demande_de_code(texte: str) -> str:
    """« !code » / « !recup » si le message est une demande de code (« Code », « code pour le compte 2 », « le code stp »,
    « j'ai pas reçu le code »), sinon "". Moins de 6 mots, le mot « code », sans autre question ni remerciement."""
    t = (texte or "").strip()
    m = _MOT_SEUL.fullmatch(t)
    if m:
        return "!code" if m.group(1).lower().startswith("code") else "!recup"
    if not t or "\n" in t or len(t) > 60 or len(t.split()) >= 6 or "http" in t.lower() or "@" in t:
        return ""
    if t.startswith("!") and not re.match(r"!\s*codes?(?![\w-])", t, re.I):
        return ""
    if not _MOT_CODE.search(t) or _AUTRE_QUESTION.search(t):
        return ""
    if _MERCI.search(t) or (_CONFIRME.search(t) and not _NEGATION.search(t)):
        return ""
    return "!code"


# ------------------------------------------------------------------ 1. la liste blanche
# 10/10 (revue) : « e‑mail » écrit avec un trait d'union insécable passait la liste noire ; un pré-en-tête de &zwnj;&#847;
# remplissait la fenêtre lue. Tirets Unicode ramenés à « - », caractères invisibles retirés partout.
TIRETS = re.compile("[\u2010-\u2015\u2212\u2e3a\u2e3b\ufe58\ufe63\uff0d]")
INVISIBLES = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f"
                        "\u3164\ufe00-\ufe0f\ufeff\uffa0]")


def plat(t: str) -> str:
    """Minuscules, sans accents, apostrophes droites, tirets simples, sans caractères invisibles, chiffres et lettres de
    compatibilité ramenés à l'ASCII (« Réinitialisé » → « reinitialise », « ５１７ » → « 517 »)."""
    t = TIRETS.sub("-", INVISIBLES.sub("", str(t or "")))
    t = unicodedata.normalize("NFKD", t).lower()
    t = t.replace("’", "'").replace("‘", "'").replace("ʼ", "'").replace("ß", "ss")
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def adresse_expediteur(from_header) -> str:
    """L'ADRESSE de l'expéditeur, jamais le nom affiché (« mail.instagram.com <faux@gmail.com> » → faux@gmail.com)."""
    try:
        valeur = str(make_header(decode_header(str(from_header or ""))))
    except Exception:                                                   # noqa: BLE001
        valeur = str(from_header or "")
    return email.utils.parseaddr(valeur)[1].strip().lower()


DOMAINES_INSTAGRAM = ("instagram.com", "mail.instagram.com")
DOMAINES_META_CODES = ("meta.com", "mail.meta.com")                    # Meta : seulement pour un mail qui parle d'Instagram
DOMAINES_META = DOMAINES_INSTAGRAM + DOMAINES_META_CODES + ("facebookmail.com", "facebook.com", "accountscenter.meta.com")
# iCloud « Masquer mon adresse » réécrit l'expéditeur : security@mail.instagram.com → security_at_mail_instagram_com_<id>@icloud.com.
# La partie avant « _at_ » n'a pas de « _ », le suffixe non plus : « a_at_mail_instagram_com_at_outlook_com_zz9 » (un faux relayé)
# et « …_instagram_com_exemple_invalid_x1 » (mail.instagram.com.exemple.invalid) sont refusés. 10/10 (revue) : le format exact
# n'est pas vérifié sur un vrai mail ; un tiret dans le suffixe, ou pas de suffixe, est accepté (ni l'un ni l'autre ne peut
# imiter un domaine, qui a toujours un point, donc un « _ »), et un expéditeur au nom de Meta à l'adresse non reconnue part au
# salon admin (Lecteur._expediteur_inconnu) : un écart de format ne fait plus taire les codes en silence.
RE_ICLOUD_INSTAGRAM = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_)?instagram_com(?:_[a-z0-9-]+)?$")
RE_ICLOUD_META_CODES = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_)?meta_com(?:_[a-z0-9-]+)?$")
RE_ICLOUD_META = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_|accountscenter_)?(?:instagram|facebookmail|facebook|meta)_com"
                            r"(?:_[a-z0-9-]+)?$")
MOTS_META = re.compile(r"(?<![a-z0-9])(instagram|facebook|facebookmail|meta)(?![a-z0-9])")


def _domaine_ok(from_header, domaines, motif) -> bool:
    adresse = adresse_expediteur(from_header)
    if "@" not in adresse:
        return False
    local, domaine = adresse.rsplit("@", 1)
    return domaine in domaines or (domaine == "icloud.com" and bool(motif.match(local)))


def expediteur_instagram(from_header) -> bool:
    return _domaine_ok(from_header, DOMAINES_INSTAGRAM, RE_ICLOUD_INSTAGRAM)


def expediteur_meta_codes(from_header) -> bool:
    return _domaine_ok(from_header, DOMAINES_META_CODES, RE_ICLOUD_META_CODES)


def expediteur_meta(from_header) -> bool:
    """Toute adresse Meta (Instagram, Facebook, Meta, Espace Comptes) : pour les ALERTES et pour bans_mail."""
    return _domaine_ok(from_header, DOMAINES_META, RE_ICLOUD_META)


_MOTS_CONNUS = {"security", "no", "reply", "noreply", "notification", "notifications", "at", "mail", "instagram", "facebook",
                "facebookmail", "meta", "com", "accountscenter", "posts", "recap", "icloud", "support", "help"}


def forme_adresse(adresse: str) -> str:
    """La FORME d'une adresse, sans rien d'identifiant : les mots connus gardés, tout le reste en « ••• »
    (« security_at_mail_instagram_com_<a>_<b> » chez icloud.com → « security_at_mail_instagram_com_•••_••• »)."""
    morceaux = re.split(r"([_.=+@-])", str(adresse or "").lower())
    return "".join(m if (not m or m in _MOTS_CONNUS or re.fullmatch(r"[_.=+@-]", m)) else "•••" for m in morceaux)


def nom_meta_sans_adresse_meta(from_header) -> bool:
    """Un expéditeur qui se dit Meta (nom affiché ou adresse) sans adresse Meta reconnue : imitation, ou format iCloud changé."""
    if expediteur_meta(from_header):
        return False
    try:
        valeur = str(make_header(decode_header(str(from_header or ""))))
    except Exception:                                                   # noqa: BLE001
        valeur = str(from_header or "")
    return bool(MOTS_META.search(plat(valeur)))


# 10/10 (revue) : la preuve du relais. Gmail écrit en TÊTE du mail son propre Authentication-Results (un expéditeur ne peut pas
# l'écrire à sa place : le sien arrive dessous) ; un mail relayé par iCloud devrait y porter « arc=pass (… dkdomain=
# mail.instagram.com …) » ou une signature Meta. Statut : spéculatif tant qu'un vrai mail relayé ne l'a pas confirmé.
PREUVE_META = re.compile(r"(?:arc=pass\s*\([^)]*dkdomain=|dkim=pass[^;]*?header\.(?:d=|i=@))(?:[a-z0-9-]+\.)*"
                         r"(?:instagram|facebookmail|facebook|meta)\.com\b")


def preuve_exigee() -> bool:
    return PREUVE_RELAIS in ("1", "oui", "exiger", "true", "on")


def preuve_relais(msg) -> str:
    """« directe » (adresse Meta en clair, protégée par DMARC), « ok » (Gmail atteste la signature Meta), « absente » (aucun
    Authentication-Results), « contraire » (Gmail a lu le mail sans aucune signature Meta)."""
    adresse = adresse_expediteur(msg.get("From"))
    if not adresse.endswith("@icloud.com"):
        return "directe"
    resultats = [str(v) for v in (msg.get_all("Authentication-Results") or [])]
    if not resultats:
        return "absente"
    return "ok" if PREUVE_META.search(plat(resultats[0])) else "contraire"


def relais_accepte(msg) -> bool:
    """Faux seulement si CODES_PREUVE_RELAIS=1 et qu'un mail relayé par iCloud n'a pas la preuve de Meta."""
    return not preuve_exigee() or preuve_relais(msg) in ("directe", "ok")


def html_en_texte(source: str, complet: bool = False) -> str:
    """HTML → texte : commentaires, <head>, <style>, <script> retirés (un CSS de 2,5 Ko en tête cachait « reset your
    password »), fins de blocs en retours à la ligne, entités décodées. `complet` (10/10, revue : pour la liste noire) :
    le <title> et les textes alternatifs des images sont lus aussi (« Reset your password » caché dans l'un ou l'autre)."""
    h = re.sub(r"(?is)<!--.*?-->", " ", source or "")
    titres = re.findall(r"(?is)<title\b[^>]*>(.*?)</title\s*>", h) if complet else []
    h = re.sub(r"(?is)<(head|style|script|title|noscript)\b.*?</\1\s*>", " ", h)
    if complet:
        h = re.sub(r"(?is)<img\b[^>]*?\balt\s*=\s*(?:\"([^\"]*)\"|'([^']*)')[^>]*>",
                   lambda m: " " + (m.group(1) or m.group(2) or "") + " ", h)
    h = re.sub(r"(?is)<(br|/p|/div|/tr|/td|/li|/h[1-6]|/table)\b[^>]*>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return html.unescape(("\n".join(titres) + "\n" if titres else "") + h)


def _parties(msg) -> list:
    """[(type, texte)] des parties texte et HTML du mail (pièces jointes exclues)."""
    sortie = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        genre = part.get_content_type()
        if genre not in ("text/plain", "text/html") or part.get_content_disposition() == "attachment":
            continue
        try:
            brut = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:                                               # noqa: BLE001
            continue
        sortie.append((genre, brut))
    return sortie


def _espaces(texte: str) -> str:
    texte = re.sub(r"[ \t\r\f\v\u00a0]+", " ", INVISIBLES.sub("", texte or ""))
    return re.sub(r" *\n[\n ]*", "\n", texte).strip()


def texte_du_mail(msg) -> str:
    """Le texte du mail : la partie text/plain si elle existe, sinon le HTML converti. Retours à la ligne gardés (ils
    bornent les phrases)."""
    parties = _parties(msg)
    plain = [t for g, t in parties if g == "text/plain"]
    pages = [t for g, t in parties if g == "text/html"]
    texte = "\n".join(plain) if any(p.strip() for p in plain) else "\n".join(html_en_texte(p) for p in pages)
    return _espaces(texte)


def textes_complets(msg) -> list:
    """10/10 (revue) : TOUT le mail pour la liste noire — chaque partie texte ET chaque partie HTML (avec <title> et textes
    alternatifs), sans limite de 600 caractères. Une partie texte bénigne ne cache plus une partie HTML de réinitialisation."""
    return [_espaces(t if g == "text/plain" else html_en_texte(t, complet=True)) for g, t in _parties(msg)]


# Le pied de page Meta (« This message was sent to … Not your account? Remove your email from this account. © Instagram.
# Meta Platforms, Inc. ») : 10/10 (revue) ce qui suit sa première marque APRÈS le code est ignoré (texte aplati) — la liste
# noire lit désormais tout l'e-mail, et « Supprimez votre adresse e-mail de ce compte » du pied ne doit garder aucun code.
PIED_DEBUT = re.compile(
    r"(?:(?:from|de|da|von|di) (?:meta|facebook)\W*)?(?:©|meta platforms|facebook,? inc|"
    r"this (?:message|e-?mail) was sent to|ce (?:message|courriel|e-?mail) a ete envoye a|cet e-?mail a ete envoye a|"
    r"este (?:mensaje|correo(?: electronico)?) se envio a|esta mensagem foi enviada para|este e-?mail foi enviado para|"
    r"questo messaggio e stato inviato a|questa e-?mail e stata inviata a|diese (?:nachricht|e-?mail) wurde an|"
    r"not your account|ce n'est pas votre compte|no es tu cuenta|nao e (?:a )?sua conta|non e il tuo account|"
    r"nicht dein konto|unsubscribe|se desabonner|se desinscrire|darse de baja|cancelar inscricao|annulla iscrizione|abbestellen)")
SERVICE = re.compile(r"(do not|don't|ne) (reply|repondez pas|pas repondre) (to )?(this|a cet|a ce) (e-?mail|message|courriel)"
                     r"[^.!?\n]*[.!?]?")
# 10/10 (revue) : « If you didn't request this code, you can ignore this email » porte le mot « code » (la phrase est donc
# lue) et le mot « email » (qui garderait un vrai code de connexion) : ces formules sans risque sont retirées avant.
IGNORER = re.compile(
    r"(?:you can )?(?:safely )?ignore this (?:e-?mail|message)|(?:do not|don't) (?:forward|share) this (?:e-?mail|message)|"
    r"(?:vous pouvez )?ignorer cet e-?mail|ignorez cet e-?mail|ignorez ce message|ne tenez pas compte de (?:cet e-?mail|ce message)|"
    r"ne transferez pas cet e-?mail|(?:puedes )?ignorar este (?:correo|mensaje)|(?:pode|podes) ignorar (?:este|esta) "
    r"(?:e-?mail|mensagem)|(?:puoi )?ignorare (?:questa|questo) (?:e-?mail|messaggio)|diese (?:e-?mail|nachricht) ignorieren")
URLS = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|me|io|fr)\b(?:/\S*)?", re.I)
# Les phrases d'avertissement (« si ce n'était pas vous, changez votre mot de passe ») ne disent pas à quoi sert le code…
AVERTISSEMENT = re.compile(
    r"(if (this|it) (wasn'?t|was not) you|if you didn'?t|if you did not|if not,|si ce n'etait pas vous|si vous n'etes pas a "
    r"l'origine|si vous n'etes pas|sinon,|si no fuiste tu|si no has sido tu|si no lo hiciste|se nao foi voce|se voce nao|"
    r"se non sei stat[oa] tu|se non hai|wenn du das nicht warst|falls du das nicht warst)[^.!?\n]*[.!?]?")
# … sauf (10/10, revue) quand elles portent le code ou le mot « code » : « Sinon, utilisez ce code pour réinitialiser votre mot
# de passe : 956472 » dit exactement à quoi il sert. Une telle phrase est lue ; si c'est elle qui porte le code, il est gardé.
MOT_CODE_PHRASE = re.compile(r"(?<!\w)(?:codes?|codigo|codice|kod\w*|kode)(?!\w)|(?<![\w.@-])\d{5,8}(?![\w@])")
# Le pseudo de la salutation (« Hi chloe.clips, ») est retiré de la lecture : un pseudo « x.phone » ne bloque rien.
SALUTATION = re.compile(r"\b(hi|hello|hey|bonjour|salut|hola|ola|ciao|hallo|merhaba|hai|hoi|czesc)\b\W{0,3}"
                        r"([a-z0-9][a-z0-9._]{1,40})\s*[,:!.]")
ADRESSES = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# La confirmation de l'e-mail à l'inscription : autorisée (le mot « e-mail » y est), mais ne suffit pas comme but.
CONFIRMER_EMAIL = re.compile(
    r"confirm your email( address)?|confirmez votre (adresse )?e-?mail|confirma tu (direccion de )?correo( electronico)?|"
    r"confirme (o )?seu (endereco de )?e-?mail|conferma il tuo indirizzo e-?mail|conferma la tua e-?mail|"
    r"bestatige deine e-?mail(-adresse)?")
# Liste noire (texte aplati). Chaque groupe porte le libellé dit au salon admin.
NOIRE = (
    ("code de récupération (mot de passe oublié)", r"recover\w*|\brecup\w*|\brecuper\w*|wiederherstell\w*|get back (in)?to|retrouv\w*"),
    ("réinitialisation du mot de passe", r"\breset\w*|reinitialis\w*|restablec\w*|redefin\w*|reimpost\w*|zurucksetz\w*"),
    ("mot de passe", r"password|mot de passe|contrasena|\bsenha|passwort|\bmdp\b"),
    ("mot de passe oublié", r"forgot\w*|\boubli\w*|olvid\w*|esquec\w*|dimentic\w*|vergessen"),
    ("e-mail ajouté ou changé", r"\b(add|added|adding|ajout\w*|nouvel\w*|new|agreg\w*|adicion\w*|aggiun\w*|hinzu\w*)\b\W+(\w+\W+){0,4}"
                                r"(adresse|address|endereco|indirizzo|direccion)"),
    ("e-mail ajouté ou changé", r"\be-?mails?\b|courriel|\bcorreo\b"),
    ("numéro de téléphone", r"\b(phone|telephone|telefono|telefone|handynummer|sms|celular|cellulare|portable)\b|\bnumero\b|"
                            r"phone number|mobile number|telefonnummer|mobilnummer|rufnummer"),
    ("double authentification", r"two[- ]?factor|\b2fa\b|deux facteurs|double authentification|dos factores|dois fatores|"
                                r"due fattori|zwei[- ]?faktor|authenticat\w*|authentifi\w*|autenticac\w*|autenticaz\w*|totp"),
    ("Espace Comptes", r"accounts? cent(er|re)|espace comptes|centre de comptes|centro de cuentas|central de contas|"
                       r"centro gestione|kontenubersicht|accountscenter"),
    ("suppression ou désactivation du compte", r"\bdelet\w*|supprim\w*|deactivat\w*|desactiv\w*|desativ\w*|\beliminar\w*|"
                                               r"\bexclu\w*|\belimina\w*|losch\w*|deaktiv\w*|disabl\w*|disattiv\w*|\bremov\w*"),
    ("pseudo", r"\busername\b|nom d'utilisateur|\bpseudo\w*|nombre de usuario|nome de usuario|nome utente|benutzername"),
    ("codes de secours", r"backup|sauvegarde|respaldo|secours|codici di riserva"),
    ("changement d'une information du compte", r"\b(chang\w*|modif\w*|updat\w*|mettre a jour|mis a jour|cambi\w*|alter[ao]\w*|"
                                               r"geandert|anderung\w*|andern|actualiz\w*|atualiz\w*|aggiorn\w*)\b"),
    # 10/10 (revue) : « Use this code to secure your account » passait comme connexion dès que le mail parlait de « login ».
    ("sécurisation ou reprise du compte", r"secure (your|the|this) account|secure it\b|\bsecuris\w*|\bproteg\w*|\bproteja\w*|"
                                          r"protect (your|the|this) account|konto (zu )?(sichern|schutzen)|schutze dein konto|"
                                          r"\bregain\w*|\brestor\w*|\brestaur\w*|\bunlock\w*|\bdebloq\w*|\bdesbloq\w*|\bsblocc\w*|"
                                          r"\bentsperr\w*|\bagain\b|de nuevo|otra vez|novamente|outra vez|di nuovo|a nouveau|"
                                          r"de nouveau|\berneut\b|\bwieder\b|volver a (entrar|acceder|iniciar)|"
                                          r"voltar a (entrar|acessar|fazer)|tornare a"),
    ("un autre service Meta (Facebook, Threads…)", r"\bfacebook\b|\bthreads\b|\bhorizon\b|whatsapp|\bmessenger\b|\boculus\b|"
                                                  r"meta account|compte meta|cuenta de meta|conta (da )?meta|account meta|meta-konto"),
    ("déconnexion ou sessions", r"\blog ?out\b|\blogged out\b|\bsign(ed)? out\b|\bsessions\b|\bdeconnect\w*|cerrar (la )?sesion|"
                                r"\bsair da conta\b|\bdisconnett\w*|\babmeld\w*"),
)
NOIRE_RE = tuple((libelle, re.compile(motif)) for libelle, motif in NOIRE)
APPEL_RE = re.compile(r"\b(review\w*|appeal\w*|appel|appeler|contest\w*|examen|examin\w*|revision|revisar|revisao|revisione|"
                      r"einspruch|uberprufung)\b")
# 10/10 (revue) : les mots blancs sont bornés (ni lettre, ni « . » collé) — « deniz.login » n'est jamais un but.
_G, _D = r"(?<!\w)(?<!\w\.)(?:", r")(?!\w)(?!\.\w)"
CREATION_RE = re.compile(_G + r"|".join((
    r"sign(?:ed|ing)? ?up", r"create (?:an|a new) account|creating (?:an|a new) account|finish setting up your account",
    r"creer un compte|cree un compte|creer votre compte|inscri\w*", r"registr\w*", r"cadastr\w*|criar (?:uma )?conta",
    r"crear (?:una )?cuenta", r"iscriv\w*|iscriz\w*|creare un account", r"konto (?:zu )?erstell\w*")) + _D)
# 10/10 (revue) : « confirm your identity » / « verify your account » seuls ne sont plus un but (connexion, ou
# ré-authentification avant un changement ? ambigu, donc gardé) ; le vrai mail de connexion dit « Someone tried to log in ».
CONNEXION_RE = re.compile(_G + r"|".join((
    r"log ?in|logging in|sign(?:ing)? in|unusual login", r"se connecter|tentative de connexion|connexion inhabituelle",
    r"iniciar sesion|inicio de sesion", r"fazer login|entrar na (?:sua )?conta", r"accedere|accesso", r"anmeld\w*|anzumelden")) + _D)
# 10/10 (revue) : un e-mail écrit dans aucune des 6 langues (turc, indonésien…) est gardé : ses mots de modification ne
# seraient pas lus. Il faut au moins deux mots-outils d'une même langue.
MOTS_OUTILS = {
    "fr": {"le", "la", "les", "une", "des", "du", "votre", "vous", "ce", "cette", "est", "et", "pour", "avec", "que", "qui",
           "sur", "dans", "nous", "quelqu'un", "utilisez", "saisissez"},
    "en": {"the", "your", "you", "this", "is", "and", "for", "with", "to", "of", "we", "if", "was", "it", "someone", "use",
           "enter", "please", "an", "account"},
    "es": {"el", "la", "los", "las", "tu", "su", "de", "que", "para", "con", "una", "un", "es", "este", "esta", "en", "si",
           "alguien", "usa", "cuenta"},
    "pt": {"seu", "sua", "de", "que", "para", "com", "uma", "um", "voce", "este", "esta", "na", "no", "em", "se", "alguem",
           "conta", "foi"},
    "it": {"il", "la", "tuo", "tua", "di", "che", "per", "con", "una", "un", "questo", "questa", "sei", "hai", "nel", "del",
           "qualcuno", "usa"},
    "de": {"der", "die", "das", "dein", "deine", "du", "und", "ist", "mit", "fur", "zu", "wir", "diesen", "dich", "dir",
           "jemand", "hat", "bei", "konto"},
}
CODE_SUJET = re.compile(r"(?<![\w.@-])((?:FB-?)?\d{5,8})(?![\w@])")
CODE_CORPS = re.compile(r"(?:code|codigo|codice|kod|confirmation)\D{0,60}?(?<![\w.@-])((?:FB-?)?\d{5,8})(?![\w@])", re.I)
# 10/10 (revue) : « enter 956472 to lock your account » (sans le mot « code ») n'était même pas vu comme un code : rien au
# salon admin. Un nombre seul de 6 à 8 chiffres dans un mail Meta compte désormais comme un code (lu, puis classé).
CODE_SEUL = re.compile(r"(?<![\w.@/:=-])(\d{6,8})(?![\w@/])")
# 10/10 (revue) : « 956 472 is your Instagram recovery code » (code écrit en deux blocs) passait pour un mail sans code :
# aucune ligne admin. Reconnu quand le mot « code » est là ; le code est rendu sans l'espace.
MOT_CODE = re.compile(r"(?<!\w)(?:codes?|codigo|codice|kod\w*|kode|confirmation)(?!\w)")
CODE_ESPACE = re.compile(r"(?<![\w.@-])(\d{3} \d{3})(?![\w@])")
CODE_CORPS_ESPACE = re.compile(r"(?:code|codigo|codice|kod|confirmation)\D{0,60}?(?<![\w.@-])(\d{3} \d{3})(?![\w@])")
ALERTES = (
    ("mot de passe oublié (lien de réinitialisation envoyé)",
     r"forgot your password|mot de passe oublie|get back on instagram|revenir sur instagram|reset your password|"
     r"reinitialiser votre mot de passe|olvidaste tu contrasena|esqueceu sua senha|password dimenticata|passwort vergessen"),
    ("mot de passe changé ou réinitialisé",
     r"(password|mot de passe|contrasena|senha|passwort)\W+(\w+\W+){0,5}(chang|reset|reinitialis|modif|cambi|alterad|redefin|"
     r"reimpost|geandert|zuruckgesetzt)"),
    ("double authentification", r"two[- ]?factor|\b2fa\b|deux facteurs|double authentification|dos factores|dois fatores|"
                                r"due fattori|zwei[- ]?faktor"),
    ("e-mail changé ou ajouté",
     r"(e-?mail|adresse|address|correo|endereco|indirizzo)\W+(\w+\W+){0,5}(chang|modif|ajout|added|cambi|alterad|aggiun|"
     r"geandert|hinzugefugt)|\b(new|nouvel\w*|nueva|novo|nuovo|neue)\b (e-?mail|adresse|correo|endereco|indirizzo)"),
    ("numéro de téléphone changé",
     r"(phone|telephone|numero|telefono|telefone|handynummer|telefonnummer)\W+(\w+\W+){0,5}(chang|modif|ajout|added|remov|"
     r"supprim|cambi|alterad|aggiun|geandert)"),
    ("compte relié à un Espace Comptes", r"accounts? cent(er|re)|espace comptes|centro de cuentas|central de contas|centro gestione"),
    ("pseudo changé", r"(username|nom d'utilisateur|nombre de usuario|nome de usuario|nome utente|benutzername|pseudo)\W+"
                      r"(\w+\W+){0,5}(chang|modif|cambi|alterad|geandert)"),
    ("suppression ou désactivation demandée", r"\bdelet\w*|supprim\w*|deactivat\w*|desactiv\w*|desativ\w*|\beliminar\w*|"
                                              r"\bexclu\w*|losch\w*|deaktiv\w*|disattiv\w*"),
)
ALERTES_RE = tuple((libelle, re.compile(motif)) for libelle, motif in ALERTES)
MOTIF_COMPTE = re.compile(r"\b(?:Hi|Hello|Hey|Bonjour|Salut|Hola|Olá|Ola|Ciao|Hallo|Merhaba|Hai|Hoi)\b\W{0,3}"
                          r"([A-Za-z0-9][A-Za-z0-9._]{1,40})\s*[,:!.]")


def _libelle_2fa(texte: str) -> str:
    if re.search(r"\boff\b|desactiv|disabl|deaktiv|disattiv|\bcoupe", texte):
        return "double authentification coupée"
    if re.search(r"\bon\b|activ|enabl|aktiviert|attiv", texte):
        return "double authentification activée"
    return "double authentification activée ou coupée"


def _sans_pied(texte_plat: str, code: str = None) -> str:
    """Le texte jusqu'au pied de page Meta. 10/10 (revue) : seule une marque APRÈS la dernière occurrence du code compte —
    un « © » glissé avant le code (un nom affiché, par exemple) ne coupe plus la phrase qui dit à quoi il sert."""
    debut = 0
    if code:
        i = texte_plat.rfind(plat(code))
        debut = i + len(plat(code)) if i >= 0 else 0
    m = PIED_DEBUT.search(texte_plat, debut)
    return texte_plat[:m.start()] if m else texte_plat


def _lisible(brut: str, compte: str = "", code: str = None) -> str:
    """Texte brut → texte aplati prêt à lire : liens et adresses masqués, pied de page coupé, phrases de service et formules
    sans risque retirées, salutation et pseudo du compte (s'il a un « . » ou un « _ ») retirés, « confirmez votre e-mail »
    neutralisé."""
    t = URLS.sub(" _lien_ ", ADRESSES.sub(" _x_ ", INVISIBLES.sub("", str(brut or ""))))
    t = IGNORER.sub(" ", SERVICE.sub(" ", _sans_pied(plat(t), code)))
    t = SALUTATION.sub(lambda m: f"{m.group(1)} _x_,", t)
    pseudo = plat(compte).rstrip(".")
    if pseudo and re.search(r"[._]", pseudo):
        t = re.sub(r"(?<![\w.])" + re.escape(pseudo) + r"(?!\w)", " _x_ ", t)
    return CONFIRMER_EMAIL.sub(" _confirmation_ ", t)


def _avertissements(texte: str, code: str = None) -> tuple:
    """(texte sans les avertissements qui ne parlent pas du code, phrases d'avertissement qui en parlent)."""
    gardees = []
    cible = plat(code) if code else ""

    def remplacer(m):
        phrase = m.group(0)
        if MOT_CODE_PHRASE.search(phrase) or (cible and cible in phrase):
            gardees.append(phrase)
            return phrase
        return " "
    return AVERTISSEMENT.sub(remplacer, texte), gardees


def _sans_pseudos(texte: str) -> str:
    """Tout jeton qui contient un « . » ou un « _ » entre deux lettres (un pseudo : « deniz.login », « lina_signup ») est retiré,
    au sujet comme au corps : un pseudo, choisi par le clipper, ne compte jamais comme but."""
    return re.sub(r"[\w.'-]+", lambda m: " " if re.search(r"\w[._]\w|^_|_$", m.group(0).strip(".'-")) else m.group(0), texte)


def _noire(texte: str):
    for libelle, motif in NOIRE_RE:
        if motif.search(texte):
            return libelle
    return None


def langue_lue(texte: str) -> bool:
    """Au moins deux mots-outils distincts d'une même langue parmi FR, EN, DE, ES, PT, IT."""
    mots = set(re.findall(r"[a-z']+", texte))
    return any(len(mots & outils) >= 2 for outils in MOTS_OUTILS.values())


def _code_du_mail(sujet: str, fenetre: str):
    """Le code : dans le sujet, sinon après le mot « code » au début du corps, sinon un nombre seul de 6 à 8 chiffres avant
    le pied de page (liens et adresses exclus). Toujours en chiffres ASCII (« ５１７ » → « 517 »)."""
    m = CODE_SUJET.search(unicodedata.normalize("NFKC", sujet))
    if m:
        return m.group(1).upper()
    s = plat(sujet)
    m = CODE_ESPACE.search(s) if MOT_CODE.search(s) else None
    if m:
        return re.sub(r"\D", "", m.group(1))
    propre = plat(URLS.sub(" ", ADRESSES.sub(" ", fenetre)))
    m = CODE_CORPS.search(propre)
    if m:
        return m.group(1).upper()
    m = CODE_CORPS_ESPACE.search(propre) or CODE_SEUL.search(_sans_pied(propre))
    return re.sub(r"\D", "", m.group(1)) if m else None


def classer(from_header, sujet: str, corps: str, complets=None) -> dict:
    """La décision sur un mail : {"decision": "donner"|"garder"|"alerte"|"rien", "type": "creation"|"connexion"|"appel"|"",
    "code": str|None, "libelle": str, "compte": str}. « donner » = le clipper peut l'avoir ; « garder » = un code qui ne
    sort jamais (une ligne admin sans le code) ; « alerte » = un changement déjà fait ; « rien » = le reste.
    `corps` : le texte préféré (son début dit le but) ; `complets` : toutes les parties du mail (la liste noire lit tout)."""
    sujet = INVISIBLES.sub("", str(sujet or ""))
    corps = INVISIBLES.sub("", str(corps or ""))
    m_compte = MOTIF_COMPTE.search(corps[:400])
    compte = m_compte.group(1).rstrip(".") if m_compte else ""
    fenetre = corps[:600]
    code = _code_du_mail(sujet, fenetre)
    texte = _lisible(f"{sujet} .\n{fenetre}", compte, code)
    sortie = {"decision": "rien", "type": "", "code": code, "libelle": "", "compte": compte}
    if code is None:
        if not expediteur_meta(from_header):
            return dict(sortie, libelle="expéditeur hors Meta")
        lu = AVERTISSEMENT.sub(" ", texte)
        for libelle, motif in ALERTES_RE:
            if motif.search(lu):
                if libelle == "double authentification":
                    libelle = _libelle_2fa(lu)
                return dict(sortie, decision="alerte", libelle=libelle)
        return sortie
    if not expediteur_meta(from_header):
        return dict(sortie, decision="rien", code=None, libelle="expéditeur hors Meta")   # jamais lu comme un code Meta
    texte, avert = _avertissements(texte, code)
    blanc = _sans_pseudos(texte)
    if not expediteur_instagram(from_header) and not (expediteur_meta_codes(from_header) and "instagram" in blanc):
        quoi = "Facebook" if "facebook" in adresse_expediteur(from_header) else "Meta ou Espace Comptes"
        return dict(sortie, decision="garder", libelle=f"code {quoi} (pas un mail Instagram)")
    libelle = _noire(texte)
    if libelle:
        return dict(sortie, decision="garder", libelle=libelle)
    if any(plat(code) in phrase for phrase in avert):
        return dict(sortie, decision="garder", libelle="code dans une phrase « si ce n'était pas vous »")
    for partie in complets or []:                                      # tout l'e-mail, pied de page exclu
        lu, avert_p = _avertissements(_lisible(partie, compte, code), code)
        libelle = _noire(lu)
        if libelle:
            return dict(sortie, decision="garder", libelle=f"{libelle} (plus bas dans l'e-mail)")
        if any(plat(code) in phrase for phrase in avert_p):
            return dict(sortie, decision="garder", libelle="code dans une phrase « si ce n'était pas vous » (plus bas)")
    if not langue_lue(blanc):
        return dict(sortie, decision="garder", libelle="langue non lue (ni FR, EN, DE, ES, PT, IT)")
    if APPEL_RE.search(blanc):
        if CODES_APPEL:
            return dict(sortie, decision="donner", type="appel", libelle="appel après un ban")
        return dict(sortie, decision="garder", type="appel", libelle="appel après un ban (CODES_APPEL=0)")
    if CREATION_RE.search(blanc):
        return dict(sortie, decision="donner", type="creation", libelle="création de compte")
    if CONNEXION_RE.search(blanc):
        return dict(sortie, decision="donner", type="connexion", libelle="connexion")
    return dict(sortie, decision="garder", libelle="code sans but reconnu (ni connexion ni création)")


def _entete(msg, nom: str) -> str:
    try:
        return str(make_header(decode_header(msg.get(nom) or "")))
    except Exception:                                                   # noqa: BLE001
        return str(msg.get(nom) or "")


def alias_du_mail(msg) -> str:
    """L'adresse du compte (l'alias iCloud) : To d'abord, puis X-Original-To, Delivered-To ; jamais la boîte lue."""
    for nom in ("To", "X-Original-To", "Delivered-To"):
        for _, adresse in email.utils.getaddresses([_entete(msg, nom)]):
            adresse = adresse.strip().lower()
            if "@" in adresse and adresse != IMAP_USER.lower():
                return adresse
    return ""


def cle_du_mail(msg) -> str:
    """Le Message-ID, sinon une empreinte stable (expéditeur, date, sujet) : un mail remonté du Spam garde sa clé."""
    mid = str(msg.get("Message-ID") or "").strip()
    return mid or f"{msg.get('From')}|{msg.get('Date')}|{_entete(msg, 'Subject')}"


def classer_mail(msg) -> dict:
    """classer() sur un message e-mail (tout le mail lu par la liste noire), plus l'alias, la date, la clé, l'expéditeur et
    la preuve du relais iCloud. CODES_PREUVE_RELAIS=1 : un mail relayé sans la preuve de Meta est ignoré (« rien »)."""
    sujet = _entete(msg, "Subject")
    preuve = preuve_relais(msg)
    if not relais_accepte(msg):
        info = {"decision": "rien", "type": "", "code": None, "libelle": "relais iCloud non prouvé (CODES_PREUVE_RELAIS=1)",
                "compte": ""}
    else:
        info = classer(msg.get("From"), sujet, texte_du_mail(msg), textes_complets(msg))
    try:
        date = email.utils.parsedate_to_datetime(msg.get("Date")).astimezone(timezone.utc)
    except Exception:                                                   # noqa: BLE001
        date = _maintenant()
    info.update(alias=alias_du_mail(msg), sujet=sujet, date=date, mid=cle_du_mail(msg),
                expediteur=adresse_expediteur(msg.get("From")), preuve=preuve)
    return info


# ------------------------------------------------------------------ 5. le lecteur unique
def _q(dossier: str) -> str:
    return dossier if dossier.startswith('"') else '"' + dossier.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _paires_fetch(data) -> list:
    """[(uid, octets)] d'une réponse UID FETCH (l'UID peut venir avant ou après le littéral)."""
    sortie = []
    for i, el in enumerate(data or []):
        if isinstance(el, tuple) and len(el) >= 2:
            m = re.search(rb"UID (\d+)", el[0] or b"")
            if not m and i + 1 < len(data) and isinstance(data[i + 1], bytes):
                m = re.search(rb"UID (\d+)", data[i + 1])
            if m:
                sortie.append((int(m.group(1)), el[1]))
    return sortie


def _tampon_pret(boite) -> bool:
    """10/10 (revue) : vrai si une ligne attend DÉJÀ dans le tampon de lecture d'imaplib (« + idling » et « * 12 EXISTS »
    arrivés dans le même paquet) — select() ne la voit pas. Coup d'œil sans attente : la socket passe un instant en non
    bloquant (BlockingIOError ou SSLWantReadError = rien en attente) ; le tampon et le délai de la socket restent intacts."""
    fichier, sock = getattr(boite, "file", None), getattr(boite, "sock", None)
    if fichier is None or sock is None or not hasattr(fichier, "peek"):
        return False
    try:
        ancien = sock.gettimeout()
    except (AttributeError, OSError):
        return False
    try:
        sock.settimeout(0.0)
        return bool(fichier.peek(1))
    except (BlockingIOError, InterruptedError, ssl.SSLWantReadError, ssl.SSLWantWriteError, socket.timeout):
        return False
    finally:
        try:
            sock.settimeout(ancien)
        except OSError:
            pass


def _pret_a_lire(boite, delai: float) -> bool:
    """Vrai si la connexion a quelque chose à lire avant `delai` secondes (IDLE) : le tampon d'imaplib d'abord, puis le
    tampon TLS, puis la socket."""
    sock = getattr(boite, "sock", None)
    if sock is None:
        return False
    if _tampon_pret(boite):
        return True
    if getattr(sock, "pending", None) and sock.pending():
        return True
    lisibles, _, _ = select.select([sock], [], [], max(0.0, delai))
    return bool(lisibles)


class MailIllisible(imaplib.IMAP4.error):
    """10/10 (revue) : UN mail précis ne se lit pas (corps refusé ou vide, en-têtes absents). Le passage échoue (rien n'avance)
    et il est rejoué vite, sans reconnexion ni alerte « boîte illisible » ; au bout de ECHECS_AVANT_SAUT essais, le mail est
    sauté avec une ligne admin, pour ne jamais bloquer les autres codes."""


class Lecteur:
    """Le SEUL lecteur de la boîte (10/10). Bloquant : appelé par boucle_codes via asyncio.to_thread, jamais deux à la fois.
    État : {dossier: {"validite": UIDVALIDITY, "dernier": dernier UID lu}} — persistant, donc un redémarrage ne relit rien
    de déjà vu. Un premier passage (ou un UIDVALIDITY changé) lit seulement les mails Meta des JOURS_AMORCE derniers jours.
    10/10 (revue) : l'état (UID, Message-ID vus) n'avance qu'EN FIN de passage réussi ; une coupure au milieu, un FETCH refusé
    ou un corps vide font échouer le passage, et le suivant relit les mêmes mails (l'ancien code relisait les 15 derniers
    mails à chaque tour et se rattrapait seul ; le lecteur incrémental ne le fait plus, il ne doit donc rien sauter)."""

    def __init__(self):
        self.boite = None
        self.idle = False
        self.selection = None
        self.validite = None                                           # UIDVALIDITY du dossier ouvert
        self.etat = {}
        self.vus = OrderedDict()
        self.trieur = None                                             # bans_mail : (dossier, sujet, expediteur) → dossier cible
        self.quota_t = None                                            # monotonic() peut valoir moins de 3600 au démarrage
        self.echecs_uid = {}                                           # (dossier, uid) → passages ratés sur ce mail
        self._prevu = {}                                               # le passage en cours : {dossier: état à poser à la fin}
        self._vus_passage = []                                         # le passage en cours : Message-ID lus (dossier en cours)
        self._vus_cycle = set()                                        # le passage en cours : Message-ID lus (tous dossiers)
        self._signal = []                                              # le passage en cours : remarques pour le salon admin

    def dossiers(self) -> list:
        return [IMAP_DOSSIER] + ([DOSSIER_SPAM] if DOSSIER_SPAM and DOSSIER_SPAM != IMAP_DOSSIER else [])

    def fermer(self):
        boite, self.boite, self.selection, self.validite = self.boite, None, None, None
        if boite is not None:
            try:
                boite.logout()
            except Exception:                                           # noqa: BLE001
                pass

    def _connecter(self):
        boite = imaplib.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT)
        boite.login(IMAP_USER, IMAP_PASSWORD)
        self.boite, self.selection = boite, None
        self.idle = "IDLE" in tuple(str(c).upper() for c in (getattr(boite, "capabilities", ()) or ()))

    def _selectionner(self, dossier: str):
        ecrire = self.trieur is not None
        if self.selection == (dossier, ecrire):
            return
        ok, _ = self.boite.select(_q(dossier), readonly=not ecrire)
        if ok != "OK":
            self.selection = None
            raise imaplib.IMAP4.error(f"dossier {dossier} illisible")
        self.selection = (dossier, ecrire)
        try:                                                           # « * OK [UIDVALIDITY n] » de la réponse au SELECT
            _, valeur = self.boite.response("UIDVALIDITY")
            self.validite = int(valeur[0]) if valeur and valeur[0] else None
        except Exception:                                               # noqa: BLE001
            self.validite = None

    def cycle(self, attendre: float = 0.0) -> dict:
        """Un passage : IDLE au plus `attendre` secondes, puis les seuls mails nouveaux de chaque dossier.
        Renvoie {"mails": [{"uid", "dossier", "mid", "msg", "amorce"}], "quota": (utilisé, limite) | None, "signal": [...]}.
        Rien n'avance (UID, Message-ID vus) tant que le passage n'est pas allé au bout ; un Spam illisible n'empêche pas la
        boîte de réception d'avancer (le Spam est relu au passage suivant)."""
        if self.boite is None:
            self._connecter()
        if attendre > 0 and self.idle:
            self._idle(attendre)
        mails, prevu, vus, signal = [], {}, [], []
        self._vus_cycle = set()
        for dossier in self.dossiers():
            self._prevu, self._vus_passage, self._signal = {}, [], []
            try:
                lus = self._nouveaux(dossier)
            except imaplib.IMAP4.abort:
                raise                                                  # la connexion est cassée : le passage échoue
            except imaplib.IMAP4.error as erreur:
                if dossier == IMAP_DOSSIER:
                    raise
                journal.warning("Codes : dossier %s ignoré ce passage : %s", dossier, erreur)   # un Spam absent ne bloque rien
                self.selection = None
                signal += [s for s in self._signal if s[0] == "saute"]
                continue
            mails += lus
            prevu.update(self._prevu)
            vus += self._vus_passage
            signal += self._signal
        quota = None
        if self.quota_t is None or time.monotonic() - self.quota_t > 3600:   # la boîte pleine, vérifiée une fois par heure
            quota = self._quota()
            self.quota_t = time.monotonic()
        # 10/10 (revue) : l'UID n'avance qu'ici, au bout d'un passage réussi.
        for dossier, st in prevu.items():
            self.etat[dossier] = st
            for cle in [k for k in self.echecs_uid if k[0] == dossier and k[1] <= int(st.get("dernier", 0))]:
                self.echecs_uid.pop(cle, None)
        for mid in vus:
            self.vus[mid] = True
        while len(self.vus) > 3000:
            self.vus.popitem(last=False)
        return {"mails": mails, "quota": quota, "signal": signal}

    def _idle(self, secondes: float) -> bool:
        """IDLE sur le dossier principal : rend la main dès qu'un mail arrive (EXISTS), au plus `secondes` secondes.
        10/10 (revue) : une réponse non étiquetée AVANT « + » (RFC 2177 le permet) est lue et notée, plus prise pour un refus ;
        une ligne déjà dans le tampon d'imaplib réveille tout de suite (_pret_a_lire)."""
        boite = self.boite
        self._selectionner(IMAP_DOSSIER)
        tag = boite._new_tag()
        boite.send(tag + b" IDLE\r\n")
        nouveau = False
        while True:
            ligne = boite.readline()
            if not ligne:
                raise imaplib.IMAP4.abort("connexion fermée au début d'IDLE")
            if ligne.startswith(b"+"):
                break
            if ligne.startswith(tag):                                   # NO / BAD : le serveur refuse IDLE
                boite.tagged_commands.pop(tag, None)
                self.idle = False                                      # sondage simple désormais
                return False
            if re.search(rb"\b(EXISTS|RECENT)\b", ligne):
                nouveau = True
        fin = time.monotonic() + secondes
        try:
            while not nouveau:
                reste = fin - time.monotonic()
                if reste <= 0 or not _pret_a_lire(boite, reste):
                    break
                ligne = boite.readline()
                if not ligne:
                    raise imaplib.IMAP4.abort("connexion fermée pendant IDLE")
                if re.search(rb"\b(EXISTS|RECENT)\b", ligne):
                    nouveau = True
        finally:
            boite.send(b"DONE\r\n")
            while True:
                ligne = boite.readline()
                if not ligne:
                    raise imaplib.IMAP4.abort("connexion fermée après IDLE")
                if ligne.startswith(tag):
                    break
                if re.search(rb"\b(EXISTS|RECENT)\b", ligne):
                    nouveau = True
            boite.tagged_commands.pop(tag, None)
        return nouveau

    def _quota(self):
        if "QUOTA" not in tuple(str(c).upper() for c in (getattr(self.boite, "capabilities", ()) or ())):
            return None
        try:
            ok, data = self.boite.getquotaroot(_q("INBOX"))
        except imaplib.IMAP4.abort:
            raise
        except imaplib.IMAP4.error:
            return None
        plats = []
        for el in data or []:
            plats += el if isinstance(el, list) else [el]
        m = re.search(rb"STORAGE (\d+) (\d+)", b" ".join(x if isinstance(x, bytes) else str(x).encode() for x in plats))
        return (int(m.group(1)), int(m.group(2))) if m else None

    def _existe(self, uid: int) -> bool:
        """Le mail est-il toujours dans le dossier ouvert ? (déplacé ou effacé entre la recherche et la lecture : non)"""
        ok, ids = self.boite.uid("SEARCH", None, f"UID {uid}")
        if ok != "OK":
            raise imaplib.IMAP4.error(f"recherche de l'UID {uid} refusée")
        return str(uid).encode() in (ids[0].split() if ids and ids[0] else [])

    def _sauter(self, dossier: str, uid: int, quoi: str) -> bool:
        """Un mail qui échoue ECHECS_AVANT_SAUT passages de suite est sauté (une ligne admin) ; avant, le passage échoue."""
        cle = (dossier, int(uid))
        self.echecs_uid[cle] = self.echecs_uid.get(cle, 0) + 1
        if self.echecs_uid[cle] < ECHECS_AVANT_SAUT:
            return False
        self._signal.append(("saute", dossier, int(uid), quoi))
        journal.warning("Codes : mail UID %s (%s) sauté après %d passages : %s illisible", uid, dossier, ECHECS_AVANT_SAUT, quoi)
        return True

    def _incrementer(self, dossier: str, st: dict, uidnext: int = 0) -> list:
        """Les UID au-delà du dernier lu (« UID n:* » rend au moins le dernier mail : filtré). L'état est PRÉVU, pas posé."""
        dernier = int(st.get("dernier", 0))
        ok, ids = self.boite.uid("SEARCH", None, f"UID {dernier + 1}:*")
        if ok != "OK":
            raise imaplib.IMAP4.error(f"recherche des nouveaux mails refusée ({dossier})")
        uids = sorted(int(u) for u in (ids[0].split() if ids and ids[0] else []) if int(u) > dernier)
        lus = self._lire(dossier, uids, False)
        self._prevu[dossier] = dict(st, dernier=max([dernier, uidnext - 1] + uids))
        return lus

    def _nouveaux(self, dossier: str) -> list:
        st = self.etat.get(dossier)
        if self.selection is not None and self.selection[0] == dossier and st is not None \
                and self.validite is not None and int(st.get("validite", -1)) == self.validite:
            # Le dossier ouvert (celui d'IDLE) : jamais de STATUS sur lui (RFC 3501, la réponse peut être périmée) ;
            # une recherche UID suffit, et ne rend que l'UID du dernier mail quand rien n'est arrivé.
            return self._incrementer(dossier, st)
        ok, data = self.boite.status(_q(dossier), "(UIDNEXT UIDVALIDITY)")
        if ok != "OK":
            raise imaplib.IMAP4.error(f"dossier {dossier} illisible (STATUS)")
        brut = b" ".join(x for x in data if isinstance(x, bytes))
        m_next, m_val = re.search(rb"UIDNEXT (\d+)", brut), re.search(rb"UIDVALIDITY (\d+)", brut)
        if not (m_next and m_val):
            raise imaplib.IMAP4.error(f"dossier {dossier} : STATUS sans UIDNEXT ni UIDVALIDITY")
        uidnext, validite = int(m_next.group(1)), int(m_val.group(1))
        amorce = st is None or int(st.get("validite", -1)) != validite
        if amorce:
            self._selectionner(dossier)
            depuis = (_maintenant() - timedelta(days=JOURS_AMORCE)).strftime("%d-%b-%Y")
            uids = set()
            for mot in MOTS_EXPEDITEUR:
                ok, ids = self.boite.uid("SEARCH", None, f'(SINCE {depuis} FROM "{mot}")')
                if ok != "OK":
                    raise imaplib.IMAP4.error(f"recherche du premier passage refusée ({dossier})")
                if ids and ids[0]:
                    uids.update(int(u) for u in ids[0].split())
            uids = sorted(uids)[-AMORCE_MAX:]
            lus = self._lire(dossier, uids, True)
            self._prevu[dossier] = {"validite": validite, "dernier": max([uidnext - 1] + uids)}
            return lus
        if uidnext - 1 <= int(st.get("dernier", 0)):
            return []
        self._selectionner(dossier)
        return self._incrementer(dossier, st, uidnext)

    def _expediteur_inconnu(self, from_header):
        """10/10 (revue) : un mail au nom de Meta (nom ou adresse) dont l'adresse n'est pas reconnue n'est plus écarté en
        silence — si le vrai format de la réécriture iCloud diffère, plus aucun code ne sortirait sans que personne le sache."""
        if nom_meta_sans_adresse_meta(from_header):
            self._signal.append(("inconnu", forme_adresse(adresse_expediteur(from_header))))

    def _lire(self, dossier: str, uids: list, amorce: bool) -> list:
        """En-têtes de tous les nouveaux mails, corps seulement pour les expéditeurs Meta (par l'ADRESSE). 10/10 (revue) : un
        FETCH refusé, des en-têtes absents ou un corps vide font échouer le passage (relu au suivant), sauf pour un mail qui
        n'est plus là (déplacé, effacé) ; plus aucun `continue` silencieux qui perdait le mail pour toujours."""
        sortie, deplacer = [], []
        champs = "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])"
        for i in range(0, len(uids), 50):
            lot = uids[i:i + 50]
            ok, data = self.boite.uid("FETCH", ",".join(str(u) for u in lot), champs)
            if ok != "OK":
                raise imaplib.IMAP4.error(f"en-têtes illisibles ({dossier})")
            paires = _paires_fetch(data)
            recus = {u for u, _ in paires}
            for u in lot:
                if u not in recus and self._existe(u) and not self._sauter(dossier, u, "en-têtes"):
                    raise MailIllisible(f"en-têtes du mail UID {u} absents ({dossier})")
            for uid, entetes in paires:
                tete = email.message_from_bytes(entetes or b"")
                if not expediteur_meta(tete.get("From")):
                    self._expediteur_inconnu(tete.get("From"))
                    continue
                mid = cle_du_mail(tete)
                if mid in self.vus or mid in self._vus_cycle:            # déjà lu (remonté du Spam, relu après un UIDVALIDITY)
                    continue
                ok, corps = self.boite.uid("FETCH", str(uid), "(BODY.PEEK[]<0.60000>)")
                paires_c = _paires_fetch(corps) if ok == "OK" else []
                if not paires_c or not (paires_c[0][1] or b"").strip():
                    if not self._existe(uid):
                        continue                                       # plus là : déplacé (relu dans l'autre dossier) ou effacé
                    if self._sauter(dossier, uid, "corps"):
                        continue
                    raise MailIllisible(f"corps du mail UID {uid} {'refusé' if ok != 'OK' else 'vide'} ({dossier})")
                self._vus_cycle.add(mid)
                self._vus_passage.append(mid)
                msg = email.message_from_bytes(paires_c[0][1] or b"")
                sortie.append({"uid": uid, "dossier": dossier, "mid": mid, "msg": msg, "amorce": amorce})
                if self.trieur is not None:
                    try:
                        cible = self.trieur(dossier, _entete(msg, "Subject"), adresse_expediteur(msg.get("From")))
                    except Exception as erreur:                         # noqa: BLE001
                        journal.warning("Tri des mails Meta : %s", _err(erreur))
                        cible = None
                    if cible and cible != dossier:
                        deplacer.append((uid, cible))
        for uid, cible in deplacer:                                    # bans_mail : pub → Spam, important du Spam → boîte
            try:
                self.boite.uid("MOVE", str(uid), _q(cible))
            except imaplib.IMAP4.abort:
                raise
            except imaplib.IMAP4.error as erreur:
                journal.warning("Codes : déplacement depuis %s : %s", dossier, erreur)
                break
        return sortie


LECTEUR = Lecteur()
_ABONNES = []                                                          # bans_mail : fonction(msg, dossier), sur chaque mail Meta


def abonner(fonction, trieur=None):
    """bans_mail s'abonne au flux du lecteur unique (10/10 : plus de connexion IMAP à lui)."""
    if fonction is not None and fonction not in _ABONNES:
        _ABONNES.append(fonction)
    if trieur is not None:
        LECTEUR.trieur = trieur


# ------------------------------------------------------------------ état persistant (codes_lecteur.json)
_ETAT = {}


def _fichier_etat():
    return Path(FICHIER_ALIAS).with_name("codes_lecteur.json") if FICHIER_ALIAS else None


def _etat() -> dict:
    """{"uid": {...}, "codes": [...], "faits": {cle: iso}, "sante": {cle: iso}, "panne_signalee": bool, "n": int}. Les codes
    gardés n'y sont jamais écrits : seulement leur type, leur adresse et leur date. « n » numérote les arrivées (10/10, revue :
    deux codes à la même seconde, le dernier arrivé passe devant)."""
    if not _ETAT:
        f = _fichier_etat()
        try:
            _ETAT.update(json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {})
        except (OSError, ValueError):
            journal.warning("codes_lecteur.json illisible, réinitialisé")
        for cle, defaut in (("uid", {}), ("codes", []), ("faits", {}), ("sante", {}), ("n", 0)):
            _ETAT.setdefault(cle, defaut)
    return _ETAT


def _sauver():
    f = _fichier_etat()
    if f is None:
        return
    e = _etat()
    limite = (_maintenant() - timedelta(minutes=CACHE_MIN)).isoformat()
    e["codes"] = [t for t in e["codes"] if str(t.get("date", "")) >= limite]
    vieux = (_maintenant() - timedelta(days=7)).isoformat()
    e["faits"] = {k: v for k, v in e["faits"].items() if str(v) >= vieux}
    e["sante"] = {k: v for k, v in e["sante"].items() if str(v) >= vieux}
    try:
        f.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as erreur:
        journal.warning("codes_lecteur.json non écrit : %s", erreur)


def _iso(date) -> str:
    return date.astimezone(timezone.utc).isoformat(timespec="seconds") if isinstance(date, datetime) else str(date or "")


def _date(t) -> datetime:
    try:
        return datetime.fromisoformat(str(t.get("date")))
    except (TypeError, ValueError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _age_min(t) -> int:
    return max(0, int((_maintenant() - _date(t)).total_seconds() // 60))


def _cle_tri(t) -> tuple:
    """La date de l'e-mail, puis l'ordre d'arrivée (10/10, revue : à la seconde près, le tri montrait le plus ancien)."""
    return (_date(t), int(t.get("n") or 0))


def _numeroter(entree: dict) -> dict:
    e = _etat()
    e["n"] = int(e.get("n") or 0) + 1
    entree["n"] = e["n"]
    return entree


def codes_recents(adresses, minutes: int = None, decision: str = "donner") -> list:
    """Les entrées du cache (« donner » ou « garder ») des `adresses`, plus récentes d'abord, dans la fenêtre."""
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    adresses = {str(a).strip().lower() for a in adresses or []}
    limite = _maintenant() - timedelta(minutes=minutes)
    trouves = [t for t in _etat()["codes"] if t.get("alias") in adresses and t.get("decision") == decision
               and _date(t) >= limite]
    return sorted(trouves, key=_cle_tri, reverse=True)


def _une_fois(cle: str, minutes: int = None) -> bool:
    """Vrai la première fois (puis plus pendant `minutes`, ou jamais pour une clé « par e-mail »)."""
    e = _etat()
    if minutes is None:
        if cle in e["faits"]:
            return False
        e["faits"][cle] = _iso(_maintenant())
        return True
    avant = e["sante"].get(cle)
    try:
        if avant and _maintenant() - datetime.fromisoformat(avant) < timedelta(minutes=minutes):
            return False
    except ValueError:
        pass
    e["sante"][cle] = _iso(_maintenant())
    return True


# ------------------------------------------------------------------ réveil des guets
_cond = (None, None)
_guets = {}                                                            # cle → {"dire": coroutine} (le dernier appui gagne)
_SANTE = {"ok_t": None, "echecs": 0, "erreur": ""}
_deps = {}


def configurer(deps: dict):
    """deps : canal_admin (coroutine → salon admin), adresses_de_membre (uid → set), est_staff (membre → bool),
    admin_ids (ensemble d'identifiants)."""
    _deps.update(deps)


def _condition():
    global _cond
    boucle = asyncio.get_running_loop()
    if _cond[0] is not boucle:
        _cond = (boucle, asyncio.Condition())
    return _cond[1]


async def _attendre_nouveau(delai: float) -> bool:
    c = _condition()
    async with c:
        try:
            await asyncio.wait_for(c.wait(), timeout=max(0.01, delai))
            return True
        except asyncio.TimeoutError:
            return False


async def _reveiller():
    c = _condition()
    async with c:
        c.notify_all()


def lecteur_en_panne() -> bool:
    return _SANTE["echecs"] > 0 and (_SANTE["ok_t"] is None or time.monotonic() - _SANTE["ok_t"] > 120)


# ------------------------------------------------------------------ 4. la réponse privée
def _ligne_privee(t: dict) -> str:
    compte = f" · compte `@{t['compte']}`" if t.get("compte") else ""
    age = _age_min(t)
    quand = "reçu à l'instant" if age < 1 else f"reçu il y a {age} min"
    return (f"🔐 **Ton code Instagram ({QUOI.get(t.get('type'), 'connexion')})**{compte}\n\n"
            f"Adresse `{t.get('alias', '')}` · {quand} :\n```\n{t['code']}\n```")


def _texte_codes(codes: list) -> str:
    """Le plus récent par adresse (3 au plus)."""
    vus, lignes = set(), []
    for t in codes:
        if t.get("alias") in vus:
            continue
        vus.add(t.get("alias"))
        lignes.append(_ligne_privee(t))
    return "\n\n".join(lignes[:3])


def _texte_ancien(t: dict) -> str:
    return (f"🕰️ **Ancien code** ({QUOI.get(t.get('type'), 'connexion')}, reçu il y a {_age_min(t)} min) :\n```\n{t['code']}\n```\n\n"
            "Il est peut-être périmé. S'il est refusé, appuie sur « Renvoyer le code » dans Instagram : je guette le "
            "nouveau 5 minutes, il remplace celui-ci ici.")


_MONTRES = {}                                                          # cle_guet → {Message-ID: date ISO où le code a été montré}


def _deja_montre(cle_guet: str, t: dict):
    """La date où ce code a déjà été montré à ce clipper, ou None (10/10, revue : « déjà donné il y a 2 min »)."""
    quand = (_MONTRES.get(cle_guet) or {}).get(t.get("mid"))
    return {"date": quand} if quand else None


def _noter_montre(cle_guet: str, codes: list):
    limite = _iso(_maintenant() - timedelta(minutes=CACHE_MIN))
    vus = {k: v for k, v in (_MONTRES.get(cle_guet) or {}).items() if v >= limite}
    for t in codes[:3]:
        vus.setdefault(t.get("mid"), _iso(_maintenant()))
    _MONTRES[cle_guet] = vus
    for cle in [k for k, v in _MONTRES.items() if not v]:
        _MONTRES.pop(cle, None)


NOTE_GARDE = ("-# Un e-mail plus récent sur ton adresse n'est pas un code de connexion ni de création : je ne le donne "
              "pas.")


def _note_garde(adresses, minutes: int, montre: dict) -> str:
    """La note quand le dernier e-mail reçu (plus récent que le code montré) est un code gardé, sinon ""."""
    gardes = codes_recents(adresses, minutes, decision="garder")
    return "\n\n" + NOTE_GARDE if gardes and montre is not None and _cle_tri(gardes[0]) >= _cle_tri(montre) else ""


def _texte_frais(codes: list, cle_guet: str) -> str:
    """Le(s) code(s) frais, et la ligne qui dit quoi faire s'il est refusé (le guet continue : le nouveau s'affiche seul).
    Déjà montré à ce clipper : on le lui dit, avec l'heure."""
    deja = _deja_montre(cle_guet, codes[0]) if codes else None
    if deja is not None:
        age = _age_min(deja)
        quand = "il y a moins d'une minute" if age < 1 else f"il y a {age} min"
        note = (f"-# Déjà donné {quand}. S'il est refusé, appuie sur « Renvoyer le code » dans Instagram : je guette le "
                "suivant, il s'affiche ici tout seul.")
    else:
        note = TEXTE_REFUSE
    return _texte_codes(codes) + "\n\n" + note


async def _servir(adresses: set, dire, cle_guet: str, duree: int = None, minutes: int = None, relire=None) -> str:
    """Le cœur du bouton et de `!code` : `dire(texte)` poste ou remplace la réponse PRIVÉE. Renvoie l'issue (« code »,
    « ancien », « rien », « panne », « deja », « sortie ») pour le journal et les tests. Un code gardé n'est jamais dit.
    10/10 (revue) :
    - après un code, le guet CONTINUE jusqu'au bout des 5 minutes : un code plus récent (création puis connexion, ou
      « Renvoyer le code ») remplace l'ancien tout seul, et la réponse dit quoi faire s'il est refusé ;
    - `relire()` redonne les adresses du clipper à chaque réveil : un clipper sorti pendant son guet ne voit plus rien ;
    - un 2e appui pendant un guet : la nouvelle réponse prend la suite, l'ancienne renvoie à la nouvelle ;
    - boîte en panne au moment de l'appui : dit tout de suite ;
    - deux codes à la même seconde : le dernier arrivé passe devant."""
    duree = ATTENTE_SEC if duree is None else duree
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    if cle_guet in _guets:                                             # il rappuie : la nouvelle réponse suit le guet
        guet = _guets[cle_guet]
        ancien, guet["dire"] = guet["dire"], dire
        try:
            await ancien(TEXTE_SUITE)
        except Exception as erreur:                                     # noqa: BLE001 — l'ancienne réponse a pu expirer
            journal.info("Codes : ancienne réponse non éditée : %s", _err(erreur))
        await dire(guet["texte"])
        return "deja"
    donnes = codes_recents(adresses, minutes)
    dernier = donnes[0] if donnes else None
    gardes = codes_recents(adresses, minutes, decision="garder")
    garde = gardes[0] if gardes and (dernier is None or _cle_tri(gardes[0]) >= _cle_tri(dernier)) else None
    montre, codes_montres = None, []
    if dernier is not None and _age_min(dernier) < FRAIS_MIN:
        frais = [t for t in donnes if _age_min(t) < FRAIS_MIN]
        texte = _texte_frais(frais, cle_guet) + ("\n\n" + NOTE_GARDE if garde else "")
        montre, codes_montres = dernier, frais
    elif lecteur_en_panne():                                           # dit tout de suite, plus au bout des 5 minutes
        texte = (TEXTE_PANNE_GUET + ("\n\n" + TEXTE_GARDE if garde is not None else "")
                 + ("\n\n" + _texte_ancien(dernier) if dernier is not None else ""))
    else:
        texte = _texte_ancien(dernier) if dernier is not None else TEXTE_ATTENTE
        if garde is not None:
            texte = TEXTE_GARDE + "\n\n" + (texte if dernier is not None else "⏳ Je guette quand même 5 minutes un code de "
                                            "connexion ou de création : il s'affiche ici tout seul.")
    guet = {"dire": dire, "texte": texte}
    _guets[cle_guet] = guet
    reference, vu_garde = dernier, garde
    try:
        await dire(texte)
        if montre is not None:
            _noter_montre(cle_guet, codes_montres)
        fin = time.monotonic() + duree
        while time.monotonic() < fin:
            await _attendre_nouveau(min(5.0, fin - time.monotonic()))
            if relire is not None:
                try:
                    adresses = {str(a).strip().lower() for a in (relire() or ()) if a and "@" in str(a)}
                except Exception as erreur:                             # noqa: BLE001 — dans le doute, plus rien
                    journal.warning("Codes : adresses relues pendant le guet : %s", _err(erreur))
                    adresses = set()
                if not adresses:                                       # sorti, ou adresse retirée : plus rien à guetter
                    guet["texte"] = TEXTE_PLUS_ADRESSE
                    await guet["dire"](TEXTE_PLUS_ADRESSE)
                    return "sortie"
                if montre is not None and any(t.get("alias") not in adresses for t in codes_montres):
                    codes_montres = [t for t in codes_montres if t.get("alias") in adresses]   # une adresse retirée : effacé
                    if not codes_montres:
                        montre = None
                    guet["texte"] = (_texte_codes(codes_montres) + "\n\n" + TEXTE_REFUSE) if codes_montres else TEXTE_ATTENTE
                    await guet["dire"](guet["texte"])
            nouveaux = [t for t in codes_recents(adresses, minutes) if reference is None or _cle_tri(t) > _cle_tri(reference)]
            if nouveaux:
                montre = reference = nouveaux[0]
                codes_montres = nouveaux
                guet["texte"] = _texte_codes(nouveaux) + "\n\n" + TEXTE_REFUSE
                await guet["dire"](guet["texte"])
                _noter_montre(cle_guet, nouveaux)
                continue
            if montre is not None:
                continue
            gardes = codes_recents(adresses, minutes, decision="garder")
            if gardes and gardes[0] is not vu_garde and (vu_garde is None or _cle_tri(gardes[0]) > _cle_tri(vu_garde)) \
                    and (dernier is None or _cle_tri(gardes[0]) > _cle_tri(dernier)):
                vu_garde = gardes[0]
                guet["texte"] = TEXTE_GARDE + "\n\n⏳ Je guette encore un code de connexion ou de création."
                await guet["dire"](guet["texte"])
        if montre is not None:                                         # le guet s'arrête : le code reste, la consigne change
            guet["texte"] = _texte_codes(codes_montres) + "\n\n" + TEXTE_REFUSE_FIN + _note_garde(adresses, minutes, montre)
            await guet["dire"](guet["texte"])
            return "code"
        if lecteur_en_panne():
            await guet["dire"](TEXTE_PANNE)
            return "panne"
        await guet["dire"]((_texte_ancien(dernier) + "\n\n" if dernier is not None else "") + TEXTE_RIEN)
        return "ancien" if dernier is not None else "rien"
    finally:
        if _guets.get(cle_guet) is guet:
            _guets.pop(cle_guet, None)


def _est_staff(membre) -> bool:
    if _deps.get("est_staff"):
        try:
            return bool(_deps["est_staff"](membre))
        except Exception:                                               # noqa: BLE001
            return False
    return _est_manager(membre, set(_deps.get("admin_ids") or ()))


def _adresses_membre(membre) -> set:
    fonction = _deps.get("adresses_de_membre")
    if fonction is None:
        return set()
    try:
        return {str(a).strip().lower() for a in fonction(getattr(membre, "id", "")) or [] if a and "@" in str(a)}
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Adresses du clipper (codes) : %s", _err(erreur))
        return set()


async def _admin(texte: str) -> bool:
    fonction = _deps.get("canal_admin")
    if fonction is None:
        return False
    try:
        salon = await fonction()
        if salon is None:
            return False
        await salon.send(texte[:1990])
        return True
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Codes : salon admin : %s", _err(erreur))
        return False


async def _alerter_sans_adresse(membre) -> bool:
    """Un clipper sans adresse rattachée demande son code → une ligne au salon admin, une fois par clipper et par jour."""
    uid = str(getattr(membre, "id", ""))
    cle = f"sans_adresse|{uid}"
    if not _une_fois(cle, minutes=24 * 60):
        return True
    prenom = getattr(membre, "display_name", "") or f"<@{uid}>"
    ok = await _admin(f"🔐 « 📩 Mon code » : aucune adresse rattachée pour **{prenom}** (<@{uid}>).\n\n"
                      "Rattache ses adresses dans son salon perso (`!alias ajouter adresse`), puis réponds-lui là-bas.")
    if not ok:
        _etat()["sante"].pop(cle, None)                                # pas prévenu : on le redira au prochain appui
    _sauver()
    return ok


async def _sans_adresse(membre, dire) -> None:
    if _est_staff(membre):
        await dire("Ici, chacun ses codes : aucune adresse n'est rattachée à ton salon.\n\n"
                   "Pour l'adresse d'un clipper : `!alias ajouter adresse` dans son salon perso.")
        return
    if await _alerter_sans_adresse(membre):
        await dire("Je ne trouve pas ton adresse.\n\nL'équipe est prévenue : elle te répond dans ton salon perso.")
    else:
        await dire("Je ne trouve pas ton adresse.\n\nDis-le à ton manager dans ton salon perso.")


async def servir_interaction(interaction) -> str:
    """Le bouton « 📩 Mon code » : une réponse ÉPHÉMÈRE (visible par celui qui appuie, et lui seul), mise à jour pendant
    le guet (le jeton d'interaction vaut 15 min, le guet 5)."""
    if not actif():
        await interaction.response.send_message("Relais des codes éteint pour l'instant. Dis-le à ton manager.", ephemeral=True)
        return "eteint"
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
    except (discord.HTTPException, discord.InteractionResponded):
        pass

    async def dire(texte):
        try:
            await interaction.edit_original_response(content=texte)
        except (discord.HTTPException, discord.NotFound):
            await interaction.followup.send(texte, ephemeral=True)

    membre = interaction.user
    adresses = _adresses_membre(membre)
    if not adresses:
        await _sans_adresse(membre, dire)
        return "sans_adresse"
    return await _servir(adresses, dire, f"u|{getattr(membre, 'id', '')}", relire=lambda: _adresses_membre(membre))


class BoutonMonCode(discord.ui.DynamicItem[discord.ui.Button], template=r"codes:mon-code"):
    """« 📩 Mon code » : persistant (custom_id fixe), il survit aux redémarrages. Le même bouton pour tout le monde : la
    réponse dépend de celui qui appuie."""

    def __init__(self):
        super().__init__(discord.ui.Button(label="📩 Mon code", style=discord.ButtonStyle.primary, custom_id=ID_BOUTON))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction):
        await servir_interaction(interaction)


def vue_mon_code():
    vue = discord.ui.View(timeout=None)
    vue.add_item(BoutonMonCode())
    return vue


# ------------------------------------------------------------------ commandes
def ligne_code(t: dict) -> str:
    """La ligne d'un code dans le salon d'un MANAGER (`!alias`) : seulement un code donnable, jamais le corps du mail."""
    compte = f" · compte `@{t['compte']}`" if t.get("compte") else ""
    age = _age_min(t)
    quand = " (à l'instant)" if age < 1 else f" (reçu il y a {age} min)"
    return (f"🔐 **Code Instagram, {QUOI.get(t.get('type'), 'connexion')}** pour `{t.get('alias', '')}`{compte}{quand}. "
            f"Copie-le d'un geste :\n```\n{t['code']}\n```")


async def commande(message, admin_ids, adresses_de_membre=None, alerter=None) -> bool:
    """`!code` (au salon commun : réponse en message privé ; ailleurs : le lien du salon) · `!alias ajouter|retirer|liste`
    et `!code [alias]` d'un manager dans son salon · `!recup`, `!appel`, `!unban` (refusés, sauf l'appel si CODES_APPEL=1).
    Renvoie True si traité. `alerter` n'est plus utilisé (gardé pour l'appelant) : l'alerte passe par configurer."""
    texte = message.content.strip()
    if not texte.lower().startswith(("!alias", "!code") + COMMANDES_RECUP):
        return False
    mots = texte.split()
    premier = mots[0].lower()
    if premier.startswith("!code"):
        premier = "!code"
    if premier in COMMANDES_RECUP:
        if CODES_APPEL and premier in COMMANDES_APPEL:
            premier = "!code"
        else:
            await message.reply(TEXTE_RECUP_REFUSE)
            return True
    canal_id = str(message.channel.id) if message.guild is not None else ""
    manager = message.guild is not None and _est_manager(message.author, admin_ids)
    if canal_id and canal_id == salon_codes_id() and premier == "!code":
        adresse = mots[1].lower() if len(mots) >= 2 and "@" in mots[1] else ""
        admin = str(getattr(message.author, "id", "")) in admin_ids
        return await _commande_salon_commun(message, manager, admin, adresses_de_membre, adresse)
    if not manager and premier == "!code":
        await message.reply(texte_salon_codes())
        return True
    if not manager:
        await message.reply("Réservé aux managers (rôle « Manager ») et aux admins.")
        return True
    if not actif():
        await message.reply("Relais des codes éteint : `CODES_IMAP_USER` / `CODES_IMAP_PASSWORD` absents.")
        return True
    registre = _lire()
    if premier == "!alias":
        action = mots[1].lower() if len(mots) > 1 else "liste"
        if action in ("ajouter", "add") and (canal_id == salon_codes_id() or not _salon_prive(message.channel)):
            await message.reply("Pas ici : un code ne s'écrit jamais dans un salon que d'autres lisent. Tape `!alias ajouter` "
                                "dans le salon perso du clipper, ou dans ton salon privé.")
            return True
        if action in ("ajouter", "add") and len(mots) > 2:
            for alias in [a.lower() for a in mots[2:] if "@" in a]:
                registre[alias] = {"canal_id": canal_id, "par": str(message.author.id),
                                   "date": _maintenant().isoformat(timespec="seconds")}
            _ecrire(registre)
            await message.reply(f"✅ Adresse(s) rattachée(s) à ce salon : {', '.join(a for a in mots[2:] if '@' in a)}.\n\n"
                                "Seuls les codes de connexion et de création de compte en sortent, jamais les autres.")
        elif action in ("retirer", "remove") and len(mots) > 2:
            for alias in [a.lower() for a in mots[2:]]:
                registre.pop(alias, None)
            _ecrire(registre)
            await message.reply("🗑️ Retiré.")
        else:
            miens = [a for a, v in registre.items() if isinstance(v, dict) and v.get("canal_id") == canal_id]
            await message.reply(("📮 Adresses de ce salon : " + ", ".join(miens)) if miens else
                                "Aucune adresse ici. `!alias ajouter prenom.xxx@icloud.com` pour en rattacher une.")
        return True
    # !code [alias] d'un manager dans son salon : seulement les codes donnables des adresses rattachées à CE salon.
    miens = [a for a, v in registre.items() if canal_id and isinstance(v, dict) and v.get("canal_id") == canal_id]
    if len(mots) >= 2 and "@" in mots[1]:
        alias = mots[1].lower()
        if (registre.get(alias) or {}).get("canal_id") != canal_id and str(message.author.id) not in admin_ids:
            await message.reply("Cette adresse n'est pas rattachée à ce salon : `!alias ajouter` d'abord.")
            return True
        cibles = {alias}
    elif miens:
        cibles = set(miens)
    else:
        await message.reply("Format : `!code adresse@icloud.com`. Dans un salon avec des adresses rattachées, `!code` tout "
                            "court suffit. Seuls les codes de connexion et de création sortent.")
        return True
    # Le code ne s'écrit dans le salon que s'il est privé et que TOUTES ces adresses y sont rattachées ; sinon, en MP.
    ici = all((registre.get(a) or {}).get("canal_id") == canal_id for a in cibles) and _salon_prive(message.channel)
    reponse = {"msg": None}

    async def dire(t):
        if reponse["msg"] is not None:
            try:
                await reponse["msg"].edit(content=t)
                return
            except Exception:                                           # noqa: BLE001
                pass
        reponse["msg"] = await (message.reply(t) if ici else message.author.send(t))

    if not ici:
        try:
            await dire("📩 Je regarde la boîte…")
        except (discord.Forbidden, discord.HTTPException):
            await message.reply("🔒 Tes messages privés sont fermés : je ne donne pas ce code dans ce salon.")
            return True
        await message.reply("📩 Réponse en message privé.")
    await _servir(cibles, dire, f"salon|{canal_id}|{getattr(message.author, 'id', '')}", minutes=CACHE_MIN)
    return True


async def _commande_salon_commun(message, manager: bool, admin: bool, adresses_de_membre=None, adresse: str = "") -> bool:
    """`!code` tapé au salon commun : la réponse part en MESSAGE PRIVÉ (10/10), jamais dans le salon. MP fermés : le
    bouton, dont la réponse est éphémère. `!code adresse` : Gaëtan seulement (ADMIN_IDS)."""
    if not actif():
        await message.reply("Relais des codes éteint pour l'instant. Dis-le à ton manager.")
        return True
    if adresse and not admin:
        await message.reply("Ici, chacun ses codes : `!code adresse` est réservé à Gaëtan.")
        return True
    relire = None
    if adresse:
        adresses = {adresse.strip().lower()}
    else:
        source = adresses_de_membre if adresses_de_membre is not None else (lambda: _adresses_membre(message.author))

        def _relire():                                                 # 10/10 (revue) : relu à chaque réveil du guet
            return {str(a).strip().lower() for a in source() or [] if a and "@" in str(a)}
        relire = _relire
        try:
            adresses = relire()
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Adresses du clipper (salon commun) : %s", _err(erreur))
            adresses = set()
    if not adresses:
        await _sans_adresse(message.author, message.reply)
        return True
    try:
        mp = await message.author.send("📩 Je regarde la boîte…")
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        await message.reply(TEXTE_MP_FERMES, view=vue_mon_code())
        return True
    try:
        await message.reply(TEXTE_MP, view=vue_mon_code(), delete_after=120)
    except (discord.Forbidden, discord.HTTPException):
        pass
    courant = {"msg": mp}

    async def dire(t):
        try:
            await courant["msg"].edit(content=t)
        except Exception:                                               # noqa: BLE001
            courant["msg"] = await message.author.send(t)

    await _servir(adresses, dire, f"u|{getattr(message.author, 'id', '')}", relire=relire)   # 10/10 (revue) : sortie pendant le guet
    return True


# ------------------------------------------------------------------ 2. et 6. la boucle : flux, alertes, santé
def _role_staff(role) -> bool:
    """Un rôle d'équipe qui voit tout : administrateur, rôle d'un bot, ou le rôle Manager (nom exact)."""
    perms = getattr(role, "permissions", None)
    if perms is not None and getattr(perms, "administrator", False):
        return True
    try:
        if role.is_bot_managed():
            return True
    except Exception:                                                   # noqa: BLE001
        pass
    return _cle(getattr(role, "name", "")) in ({_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")} - {""})


def _salon_prive(salon) -> bool:
    """Vrai si seul UN humain hors de l'équipe peut lire ce salon : un code ne s'écrit jamais ailleurs.
    10/10 (revue, #equipe-clippers fermé à @everyone mais ouvert au rôle Clippeur) : faux si @everyone ou un rôle hors équipe
    (Clippeur, Rookie, Confirmé, Elite, …) voit le salon, ou si plus d'un membre hors équipe y a un droit direct (salon perso
    ouvert à deux clippers) ; faux aussi pour le salon commun, et dans le doute."""
    try:
        if str(getattr(salon, "id", "")) == salon_codes_id():
            return False
        guild = salon.guild
        if salon.permissions_for(guild.default_role).view_channel:
            return False
        for role in getattr(guild, "roles", None) or []:
            if role is guild.default_role or _role_staff(role):
                continue
            if salon.permissions_for(role).view_channel:
                return False
        roles = list(getattr(guild, "roles", None) or [])
        moi = getattr(guild, "me", None)
        lecteurs = 0
        for cible, droit in (getattr(salon, "overwrites", None) or {}).items():
            if cible is moi or getattr(cible, "bot", False) or isinstance(cible, discord.Role) or cible in roles:
                continue
            if getattr(droit, "view_channel", None) and not _est_staff(cible):
                lecteurs += 1
        return lecteurs <= 1
    except Exception:                                                   # noqa: BLE001 — inconnu : pas privé
        return False


def _proprietaire(alias: str) -> dict:
    v = _lire().get(alias)
    return v if isinstance(v, dict) else {}


def signaler(cle: str, texte: str, minutes: int = 24 * 60) -> bool:
    """Une ligne au salon admin, une fois par `minutes` pour cette clé, appelable hors d'une coroutine (10/10, revue : salon
    perso partagé vu par adresses_codes_de). Vrai si la ligne part."""
    if not _une_fois(f"signal|{cle}", minutes=minutes):
        return False
    try:
        asyncio.get_running_loop().create_task(_admin(texte))
    except RuntimeError:                                               # pas de boucle : seulement le journal
        journal.warning("Codes (signal sans boucle) : %s", texte[:200])
    _sauver()
    return True


async def _signaux(resultat: dict):
    """Les remarques du lecteur : un mail sauté (illisible), un expéditeur au nom de Meta à l'adresse non reconnue."""
    for s in resultat.get("signal") or []:
        if s[0] == "saute" and _une_fois(f"saute|{s[1]}|{s[2]}"):
            await _admin(f"⚠️ **Boîte des codes : un mail reste illisible** ({s[1]}, {s[3]}) après {ECHECS_AVANT_SAUT} "
                         "essais : je le saute pour ne pas bloquer les autres codes.\n\n"
                         "Si c'était un code, lis-le dans la boîte : il n'est donné à personne.")
        elif s[0] == "inconnu" and _une_fois(f"inconnu|{s[1]}", minutes=24 * 60):
            await _admin(f"📮 **Mail au nom de Meta, adresse non reconnue** (`{s[1]}`) : écarté, aucun code lu.\n\n"
                         "Si c'est un vrai mail Instagram relayé par iCloud, le format de la réécriture a changé : à corriger "
                         "dans codes_2fa (RE_ICLOUD_*), sinon plus aucun code ne sort. Sinon, c'est une imitation : rien à "
                         "faire. Une ligne par forme d'adresse et par jour.")


async def _traiter_un(client, lu: dict, e: dict, connus: set, commun: str, bilan: dict):
    """Un mail nouveau du lecteur : abonnés, puis la décision (cache, lignes admin, push)."""
    msg, dossier = lu["msg"], lu["dossier"]
    for abonne in list(_ABONNES):
        try:
            abonne(msg, dossier)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Abonné du lecteur des codes : %s", _err(erreur))
    info = classer_mail(msg)
    mid, alias = info["mid"], info["alias"]
    recent = not lu.get("amorce") or _maintenant() - info["date"] < timedelta(minutes=60)
    journal.info("Codes : %s (%s) sur %s → %s", info["libelle"] or "mail Meta", dossier, _masquer(alias), info["decision"])
    if info.get("preuve") == "contraire" and info["decision"] != "rien" and _une_fois("preuve|observer", minutes=24 * 60):
        await _admin("📮 **Relais iCloud sans preuve Meta** : un mail au nom d'Instagram (adresse "
                     f"`{forme_adresse(info.get('expediteur'))}`) n'a pas la signature Meta attestée par Gmail.\n\n"
                     "Soit c'est une imitation, soit le format réel diffère : ouvre un vrai mail Instagram relayé dans la "
                     "boîte (Afficher l'original), regarde la 1re ligne Authentication-Results, et ne passe "
                     "CODES_PREUVE_RELAIS=1 qu'une fois ce format vérifié. Une ligne par jour au plus.")
    if info["decision"] == "donner":
        if mid not in connus:
            e["codes"].append(_numeroter({"mid": mid, "alias": alias, "code": info["code"], "type": info["type"],
                                          "decision": "donner", "compte": info["compte"], "date": _iso(info["date"])}))
            connus.add(mid)
            bilan["donnes"] += 1
        proprio = _proprietaire(alias)
        if not proprio.get("canal_id"):
            if alias and recent and _une_fois(f"orphelin|{alias}", minutes=60):
                bilan["orphelins"] += 1
                await _admin(f"🔐 Code de {QUOI.get(info['type'], 'connexion')} reçu sur `{alias}`, une adresse rattachée "
                             "à personne : je ne le donne à personne.\n\n"
                             f"Si c'est l'adresse d'un clipper : `!alias ajouter {alias}` dans son salon perso.")
        elif proprio.get("par") not in ("onboarding", "migration") and str(proprio["canal_id"]) != str(commun) \
                and _age_min({"date": _iso(info["date"])}) < FRAIS_MIN and _une_fois(f"push|{mid}"):
            salon = client.get_channel(int(proprio["canal_id"])) if str(proprio["canal_id"]).isdigit() else None
            if salon is not None and not _salon_prive(salon):
                # 10/10 (revue) : un salon d'équipe lu par des clippers ne reçoit jamais un code en clair.
                journal.warning("Code non poussé : le salon %s est lu par d'autres", getattr(salon, "name", "?"))
                await _admin(f"🔐 Code de {QUOI.get(info['type'], 'connexion')} pour `{_masquer(alias)}` **non posté** dans "
                             f"<#{proprio['canal_id']}> : ce salon est lu par d'autres que toi (un rôle de clippers, ou "
                             "plusieurs clippers).\n\n"
                             "Tape `!code` dans ton salon privé (réponse en MP), ou rattache l'adresse à un salon privé.")
            elif salon is not None:
                try:
                    await salon.send(ligne_code(dict(info, date=_iso(info["date"]))))
                except (discord.Forbidden, discord.HTTPException) as erreur:
                    journal.warning("Code non posté dans le salon du manager : %s", _err(erreur))
    elif info["decision"] == "garder":
        if mid not in connus:                                           # jamais le code : le type, l'adresse, la date
            e["codes"].append(_numeroter({"mid": mid, "alias": alias, "type": info["type"], "decision": "garder",
                                          "compte": info["compte"], "libelle": info["libelle"], "date": _iso(info["date"])}))
            connus.add(mid)
        if recent and _une_fois(f"garde|{mid}"):
            bilan["gardes"] += 1
            proprio = _proprietaire(alias)
            salon = f" · salon <#{proprio['canal_id']}>" if proprio.get("canal_id") else " · adresse rattachée à personne"
            compte = f"compte `@{info['compte']}` · " if info["compte"] else ""
            appel = ("\n\nC'est le code d'un appel après un ban : si le clipper fait appel, donne-le-lui dans son salon "
                     "perso (ou CODES_APPEL=1 sur Railway pour que le bouton le donne)." if info["type"] == "appel" else "")
            await _admin(f"🔒 **Code gardé, pas pour un clipper** : {info['libelle']}.\n\n"
                         f"{compte}adresse `{_masquer(alias)}`{salon} · e-mail « {_sans_code(info['sujet'])} ».\n\n"
                         "Le code n'est pas recopié ici : lis-le dans la boîte si tu en as besoin." + appel)
    elif info["decision"] == "alerte":
        if recent and _une_fois(f"alerte|{mid}"):
            bilan["alertes"] += 1
            qui = f"@{info['compte']}" if info["compte"] else _masquer(alias)
            proprio = _proprietaire(alias)
            salon = f" · salon <#{proprio['canal_id']}>" if proprio.get("canal_id") else ""
            await _admin(f"⚠️ changement sur le compte {qui} : {info['libelle']}.\n\n"
                         f"Adresse `{_masquer(alias)}`{salon} · e-mail « {_sans_code(info['sujet'])} ».\n\n"
                         "Si ce n'est pas l'équipe : ouvre le mail dans la boîte et utilise son lien « Ce n'était pas "
                         "moi » ou « Sécuriser le compte ».")


async def _traiter_lus(client, resultat: dict) -> dict:
    """Les mails nouveaux du lecteur : cache des codes donnables, lignes admin (codes gardés, changements, adresses
    rattachées à personne, mails sautés, expéditeurs non reconnus), push dans le salon PRIVÉ d'un manager (`!alias`),
    abonnés (bans_mail). Un mail qui fait planter son traitement n'empêche pas les suivants. Renvoie un bilan."""
    bilan = {"donnes": 0, "gardes": 0, "alertes": 0, "orphelins": 0}
    e = _etat()
    connus = {t.get("mid") for t in e["codes"]}
    commun = salon_codes_id()
    for lu in resultat.get("mails") or []:
        try:
            await _traiter_un(client, lu, e, connus, commun, bilan)
        except Exception as erreur:                                     # noqa: BLE001 — jamais tout le lot pour un mail
            journal.warning("Codes : traitement d'un mail : %s", _err(erreur))
    await _signaux(resultat)
    quota = resultat.get("quota")
    if quota and quota[1] and quota[0] / quota[1] >= QUOTA_SEUIL and _une_fois("sante|pleine", minutes=60):
        await _admin(f"⚠️ **Boîte des codes presque pleine** : {round(100 * quota[0] / quota[1])} % utilisés.\n\n"
                     "Libère de la place (vieux mails Meta, Drive, Photos). Une boîte pleine ne reçoit plus aucun code, "
                     "sans aucune erreur.")
    if resultat.get("mails") or quota or resultat.get("signal"):
        _sauver()
    if bilan["donnes"]:
        await _reveiller()
    return bilan


def _genre_erreur(erreur) -> str:
    t = _err(erreur).lower()
    if any(m in t for m in ("overquota", "over quota", "quota", "bandwidth")):
        return "pleine"
    if isinstance(erreur, imaplib.IMAP4.error) and any(m in t for m in (
            "authenticationfailed", "invalid credentials", "authentication failed", "application-specific",
            "web login required", "login failed", "auth")):
        return "mdp"
    return "illisible"


async def _sante_erreur(erreur) -> bool:
    """Une lecture échouée. Mot de passe refusé ou boîte pleine : une ligne tout de suite ; le reste après 3 échecs de
    suite. Une fois par heure au plus. Vrai si une ligne est partie."""
    _SANTE["echecs"] += 1
    _SANTE["erreur"] = _err(erreur)
    genre = _genre_erreur(erreur)
    if genre == "illisible" and _SANTE["echecs"] < 3:
        return False
    if not _une_fois(f"sante|{genre}", minutes=60):
        return False
    detail = _err(erreur)[:160]
    textes = {
        "mdp": (f"⚠️ **Boîte des codes : Gmail refuse le mot de passe d'application** ({detail}).\n\n"
                "Génère un nouveau mot de passe d'application pour la boîte des codes, puis remplace CODES_IMAP_PASSWORD sur "
                "Railway. D'ici là, aucun clipper ne reçoit de code."),
        "pleine": (f"⚠️ **Boîte des codes pleine, ou quota Gmail dépassé** ({detail}).\n\n"
                   "Libère de la place (vieux mails Meta, Drive, Photos). D'ici là, les codes n'arrivent plus."),
        "illisible": (f"⚠️ **Boîte des codes illisible** ({_SANTE['echecs']} essais de suite) : {detail}.\n\n"
                      "Vérifie CODES_IMAP_USER, le mot de passe d'application et l'IMAP activé dans Gmail. D'ici là, aucun "
                      "clipper ne reçoit de code."),
    }
    ok = await _admin(textes[genre])
    if ok:
        _etat()["panne_signalee"] = True
    _sauver()
    return ok


async def _sante_ok():
    _SANTE["echecs"], _SANTE["erreur"], _SANTE["ok_t"] = 0, "", time.monotonic()
    if _etat().get("panne_signalee"):
        _etat()["panne_signalee"] = False
        _sauver()
        await _admin("✅ Boîte des codes de nouveau lisible.")


async def boucle_codes(client, canal_admin_async, admin_ids):
    """Le lecteur unique (10/10) : IDLE ou sondage toutes les SONDAGE_SEC secondes, les seuls mails nouveaux, puis
    _traiter_lus. Jamais tuée par un mail ou une panne. 10/10 (revue) : un passage coupé n'avance rien (le Lecteur ne pose
    l'UID qu'au bout) ; l'état UID n'est écrit sur le disque qu'APRÈS _traiter_lus (un arrêt entre les deux relit le mail,
    les lignes admin déjà parties ne repartent pas : _une_fois)."""
    if not actif():
        journal.info("Relais codes 2FA désactivé (CODES_IMAP_USER absent)")
        return
    _deps.setdefault("canal_admin", canal_admin_async)
    _deps.setdefault("admin_ids", set(admin_ids or ()))
    await client.wait_until_ready()
    registre = _lire()
    if "_relayes" in registre or "_panne" in registre:                 # 10/10 : plus de codes en clair dans le registre
        registre.pop("_relayes", None)
        registre.pop("_panne", None)
        _ecrire(registre)
    LECTEUR.etat = {k: dict(v) for k, v in (_etat().get("uid") or {}).items() if isinstance(v, dict)}
    attendre = 0.0
    while not client.is_closed():
        try:
            resultat = await asyncio.to_thread(LECTEUR.cycle, attendre)
        except MailIllisible as erreur:                                 # 10/10 (revue) : un mail précis, pas la boîte
            journal.warning("Lecteur des codes : %s (passage rejoué, rien n'avance)", _err(erreur))
            await asyncio.sleep(min(5, SONDAGE_SEC))
            attendre = 0.0
            continue
        except Exception as erreur:                                     # noqa: BLE001
            LECTEUR.fermer()
            journal.warning("Lecteur des codes (%d de suite) : %s", _SANTE["echecs"] + 1, _err(erreur))
            await _sante_erreur(erreur)
            await asyncio.sleep(min(300, SONDAGE_SEC * _SANTE["echecs"]))
            attendre = 0.0
            continue
        await _sante_ok()
        try:
            await _traiter_lus(client, resultat)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Codes : traitement des mails : %s", _err(erreur))
        uid = {k: dict(v) for k, v in LECTEUR.etat.items()}
        if uid != _etat().get("uid"):                                  # écrit seulement quand un mail est arrivé
            _etat()["uid"] = uid
            _sauver()
        if LECTEUR.idle:
            attendre = float(SONDAGE_SEC)
        else:
            attendre = 0.0
            await asyncio.sleep(SONDAGE_SEC)


# ------------------------------------------------------------------ le salon commun
def _droits_salon_codes(guild) -> tuple:
    """(overwrites, noms des rôles admis) : fermé à @everyone, ouvert aux rôles de l'équipe et aux managers."""
    voir = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
                  guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True,
                                                        manage_messages=True)}
    cibles = {_cle(n) for n in ROLES_SALON_CODES} | {_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")}
    admis = []
    for role in guild.roles:
        if _cle(role.name) in cibles:
            overwrites[role] = voir
            admis.append(role.name)
    return overwrites, admis


async def assurer_salon_codes(client):
    """Au démarrage : le salon commun existe (créé sinon), réservé à l'équipe ; le mode d'emploi v7 est épinglé avec le
    bouton « 📩 Mon code ». À chaque nouvelle version : l'ancien mode d'emploi et les anciens messages du bot qui portaient
    un code en clair sont effacés."""
    await client.wait_until_ready()
    if not actif():
        return
    registre = _lire()
    info = registre.get("_salon_codes") or {}
    for guild in client.guilds:
        salon = client.get_channel(int(info["id"])) if str(info.get("id") or "").isdigit() else None
        if salon is None:
            cible = _cle(SALON_CODES_NOM)
            salon = next((c for c in guild.text_channels if _cle(c.name) == cible), None)
        overwrites, admis = _droits_salon_codes(guild)
        if salon is None:
            try:
                salon = await guild.create_text_channel(SALON_CODES_NOM, overwrites=overwrites, topic=SUJET_SALON,
                                                        reason="Salon commun des codes Instagram")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : création refusée (%s)", erreur)
                return
        else:
            try:
                await salon.edit(overwrites=overwrites, topic=SUJET_SALON, reason="Salon des codes : réservé à l'équipe")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : droits non posés (%s)", erreur)
        if info.get("version") != VERSION_EXPLICATION or str(info.get("id")) != str(salon.id):
            try:
                async for ancien in salon.history(limit=300):
                    if ancien.author == guild.me and ("```" in (ancien.content or "") or getattr(ancien, "pinned", False)):
                        try:
                            await ancien.delete()
                        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                            pass
            except (discord.Forbidden, discord.HTTPException, AttributeError) as erreur:
                journal.warning("Salon des codes : ménage des anciens messages (%s)", erreur)
            try:
                for ancien in await salon.pins():
                    if ancien.author == guild.me:
                        try:
                            await ancien.delete()
                        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                            pass
            except (discord.Forbidden, discord.HTTPException, AttributeError):
                pass
            try:
                m = await salon.send(explication_salon(), view=vue_mon_code())
                try:
                    await m.pin()
                except (discord.Forbidden, discord.HTTPException, AttributeError):
                    pass
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : mode d'emploi non posté (%s)", erreur)
        registre = _lire()
        registre["_salon_codes"] = {"id": str(salon.id), "guild": str(guild.id), "explique": True,
                                    "version": VERSION_EXPLICATION, "date": _maintenant().isoformat(timespec="seconds")}
        _ecrire(registre)
        journal.info("Salon des codes : #%s prêt, réservé à %s", salon.name, ", ".join(admis) or "personne (rôles introuvables !)")
        return
