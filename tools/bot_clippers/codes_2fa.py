"""OTP e-mail Meta/Facebook/Instagram : un bouton, une réponse privée par UID.

Le salon commun reste le point d'entrée. Le bouton affiche les derniers OTP e-mail
par compte/service/usage, de moins de deux minutes, puis guette cinq minutes.
Aucun code en salon ou sur disque ; aucune graine TOTP, récupération ou mutation
sensible. Les droits sont relus avant chaque envoi ; une nouvelle demande remplace
la précédente. Les tests utilisent exclusivement des données synthétiques.
"""

import asyncio
import email
import email.utils
import html
import hashlib
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
DOSSIER_TOUS = os.environ.get("CODES_IMAP_TOUS", "[Gmail]/All Mail").strip()
IMAP_TIMEOUT = int(os.environ.get("CODES_IMAP_TIMEOUT_SEC", "30") or 30)
ROLE_MANAGER_NOM = os.environ.get("ROLE_MANAGER_NOM", "Manager").strip()
# 10/10 : IDLE au plus SONDAGE_SEC secondes (le code arrive en quelques secondes), sinon une lecture toutes les SONDAGE_SEC.
SONDAGE_SEC = int(os.environ.get("CODES_SONDAGE_SEC", "20") or 20)
ATTENTE_SEC = int(os.environ.get("CODES_ATTENTE_SEC", "300") or 300)    # le guet après « 📩 Mon code » : 5 min
CODE_SALON_EFFACE_MIN = int(os.environ.get("CODES_SALON_EFFACE_MIN", "10") or 10)   # 18/10 : `!code` répond dans le salon
FRAIS_MIN = min(20, max(1, int(os.environ.get("CODES_FRAIS_MIN", "20") or 20)))  # 18/10 (Gaëtan) : les 20 dernières minutes
SALON_CODES_MINUTES = min(10, max(1, int(os.environ.get("CODES_SALON_MINUTES", "10") or 10)))
CACHE_MIN = SALON_CODES_MINUTES  # tout code récupérable doit dater de moins de dix minutes
JOURS_AMORCE = int(os.environ.get("BANS_JOURS", "3") or 3)              # premier passage : les mails Meta de 3 jours
AMORCE_MAX = int(os.environ.get("CODES_AMORCE_MAX", "120") or 120)
QUOTA_SEUIL = 0.9
# 10/10 (règle stricte de Gaëtan) : le code d'un appel après un ban est gardé ; CODES_APPEL=1 le donne au clipper.
CODES_APPEL = _oui("CODES_APPEL")
# L’ancien interrupteur CODES_SECURITES=0 ne peut plus supprimer les filtres.
SECURITES = True  # Le relais public ne doit jamais réactiver le mode sans filtre.
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
MOTS_EXPEDITEUR = ("instagram", "facebook", "meta.com", "meta_com", "metamail", "fb.com", "fb_com")
COMMANDES_RECUP = ("!recup", "!récup", "!recuperation", "!récupération", "!appel", "!unban", "!deban")
COMMANDES_APPEL = ("!appel", "!unban", "!deban")
COMMANDES_AIDE = ("!aide-ig", "!aide-instagram")
ID_BOUTON = "codes:mon-code"
# Version conservée : ce déploiement améliore les réponses à la demande, sans nouvelle annonce au salon.
VERSION_EXPLICATION = "12-point-entree-meta"   # 12/10 : v8, tout code Instagram, le plus récent

# ------------------------------------------------------------------ textes
TEXTE_CODE_BRUT = f"Dans #{SALON_CODES_NOM}, appuie sur 📩 Mon code : tes codes e-mail Meta, Facebook et Instagram s'affichent pour toi seul."
SUJET_SALON = "📩 Mon code : tes codes e-mail récents, dans une réponse visible par toi seul."
TEXTE_ATTENTE = ("⏳ Pas encore reçu.\n\nJe guette 5 minutes : ton code s'affiche ici tout seul dès que l'e-mail arrive. "
                 "Pas besoin de rappuyer.\n\nL'écran demande une application d'authentification ? "
                 "Ce code ne vient pas par e-mail : `!aide-ig authentificateur`.")
TEXTE_RIEN = ("😴 Toujours pas de code.\n\nVérifie que l'e-mail tapé dans l’application concernée est exactement celui de ton compte. "
              "Si l'écran propose l'envoi par e-mail, demande un renvoi puis rappuie sur 📩 Mon code. "
              "Respecte le délai affiché par l'application.\n\n"
              "Application d'authentification, SMS ou WhatsApp : `!aide-ig authentificateur`.")
TEXTE_PANNE = "⚠️ Je n'arrive pas à lire la boîte mail en ce moment.\n\nRéessaie dans 2 minutes. Si le blocage persiste, signale-le à ton manager sans code ni mot de passe."
# 10/10 (revue) : la panne se dit tout de suite, plus au bout des 5 minutes de guet.
TEXTE_PANNE_GUET = ("⚠️ Je n'arrive pas à lire la boîte mail en ce moment.\n\n"
                    "⏳ Je guette quand même 5 minutes : ton code s'affiche ici dès que la boîte répond.")
# 10/10 (revue, deux codes rapprochés) : le guet continue après un code ; un code plus récent remplace l'ancien tout seul.
TEXTE_REFUSE = ("-# Code refusé ? Appuie sur « Renvoyer le code » dans l’application concernée : le nouveau s'affiche ici tout "
                "seul, à la place de celui-ci.")
TEXTE_REFUSE_FIN = ("-# Code refusé ? Demande un renvoi dans l’application, respecte son délai affiché, puis "
                    "rappuie sur 📩 Mon code. Utilise le dernier code du bon compte et du bon usage.")
TEXTE_SUITE = "Cette demande a été remplacée par ta dernière demande."
TEXTE_PLUS_ADRESSE = ("🔒 Aucune adresse n'est plus rattachée à toi : je ne guette plus rien.\n\n"
                      "Une question ? Écris dans ton salon perso.")
TEXTE_GARDE = ("🔒 Le dernier e-mail reçu sur ton adresse n'est pas un code e-mail autorisé de connexion, de création ou de vérification : "
               "je ne le donne pas.\n\nBesoin d'aide ? `!aide-ig`.")
URL_AIDE_INSTAGRAM = "https://help.instagram.com/366993040048856"
URL_AIDE_META = "https://www.meta.com/account-recovery-support/"
TEXTE_APPEL_GARDE = (
    "Ouvre le compte concerné dans Instagram et lis la notification. Si « Contester » ou « Demander un examen » "
    "est proposé, suis ce parcours et le délai affiché. Si l'examen est en cours, consulte son statut.\n\n"
    "Le titulaire réalise lui-même toute vérification d'identité, selfie ou pièce demandée par Meta. "
    "Le bot ne soumet pas de recours et ne garantit pas le rétablissement.\n\n"
    f"[Aide officielle Instagram]({URL_AIDE_INSTAGRAM}) · [Centre d'aide Meta]({URL_AIDE_META})")
TEXTE_RECUP_REFUSE = ("🔒 Les codes de récupération, de recours et de changement de sécurité ne passent pas par le bot. "
                    "Pour un accès perdu : https://www.instagram.com/hacked/ . "
                    "Utilise ce parcours avec le titulaire.\n\n" + TEXTE_APPEL_GARDE)

TEXTE_MP = "📩 Je t'envoie ton code en message privé.\n\nPlus rapide : le bouton « 📩 Mon code »."
TEXTE_MP_FERMES = ("🔒 Tes messages privés sont fermés : je ne peux pas t'écrire.\n\n"
                   "Appuie sur le bouton : ton code s'affiche ici, pour toi seul.")
QUOI = {"creation": "création de compte", "connexion": "connexion", "appel": "appel après un ban",
        "verification": "vérification d’e-mail"}
# 14/10 (Gaëtan : « Il ne reçoit pas le code pour unban un compte, règle ça pour tous les clippeurs ») : « Pour confirmer votre
# identité sur Instagram, nous devons vérifier votre adresse e-mail » (code de confirmation d'adresse e-mail, envoyé à l'adresse
# DU compte quand Instagram le bloque) est donné. Le reste du mail passe toujours la liste noire : un mail qui parle aussi de mot
# de passe, d'ajout ou de changement d'adresse, de suppression… reste gardé. CODES_VERIFICATION=0 : gardé comme avant.
CODES_VERIFICATION = _oui("CODES_VERIFICATION", "1")


def explication_salon() -> str:
    return ("🔐 **Tes codes Meta · Facebook · Instagram**\n\n"
            "Appuie sur **📩 Mon code** : tes codes e-mail récents s'affichent ici, **pour toi seul**.\n"
            "Demande ton code dans l'application : je guette cinq minutes et le nouveau s'affiche automatiquement.\n\n"
            "Chaque code indique son service, son compte et son usage. Si un code est refusé, demande un renvoi.\n"
            "Les codes d'une application d'authentification ne viennent pas par e-mail. "
            "Les codes de récupération et les changements de sécurité restent dans le parcours du titulaire.")


def _explication_v7() -> str:
    """Compatibilité : les anciens appels suivent aussi les limites du parcours courant."""
    return explication_salon()


def aide_instagram(cas="") -> str:
    """Aide déterministe, sans lecture de compte ni de boîte, disponible même si le relais est indisponible."""
    aide = {
        "creation": ("🆕 **Créer le compte attribué**\n\n"
                     "1. Suis l'étape de ton compte et utilise les coordonnées autorisées pour son titulaire. "
                     "S'il existe déjà, choisis « Se connecter ».\n"
                     "2. Si Instagram demande un code envoyé par e-mail, " + texte_salon_codes() + "\n"
                     "3. Saisis le dernier code de création du bon compte. Une vérification personnelle demandée par Meta "
                     "revient au titulaire. Ne crée pas de compte pour éviter une suspension."),
        "connexion": ("🔑 **Se connecter**\n\n"
                      "1. Utilise les accès du compte déjà attribué.\n"
                      "2. Lis le moyen demandé par Instagram : e-mail, application d'authentification, SMS ou WhatsApp.\n"
                      "3. Pour l'e-mail, " + texte_salon_codes() + " Pour les autres moyens, "
                      "utilise celui déjà lié au compte avec son titulaire : `!aide-ig authentificateur`. "
                      "Ne remplace pas l'e-mail ou le numéro pour te connecter."),
        "renvoi": ("🔁 **Code absent ou refusé**\n\n"
                   "1. Vérifie le compte, son adresse et le moyen d'envoi affiché par l'application.\n"
                   "2. Demande « Renvoyer le code » si proposé et respecte le délai affiché. "
                   "La réponse privée ouverte se met à jour pendant cinq minutes.\n"
                   "3. Utilise le dernier code du bon service et du bon usage. Après la fin de l'attente, "
                   "rappuie sur 📩 Mon code. Si l'affectation de ton compte est bloquée, les renvois ne la corrigent pas."),
        "authentificateur": ("🔐 **Quel code est demandé ?**\n\n"
                            "**E-mail** : 📩 Mon code peut relayer les codes de création, connexion et vérification reconnus.\n\n"
                            "**Application d'authentification** : le bot ne génère pas ces codes. "
                            "Utilise l'application déjà liée au compte avec son titulaire.\n\n"
                            "**SMS ou WhatsApp** : le code arrive sur le moyen déjà lié au compte, pas dans cette boîte e-mail.\n\n"
                            "Si ce moyen n'est pas disponible, suis l'aide officielle proposée à l'écran avec le titulaire. "
                            "Ne publie aucun code, mot de passe, QR code ou code de secours dans Discord.\n"
                            f"[Aide officielle Meta]({URL_AIDE_META})"),
        "suspension": "🛟 **Compte suspendu ou désactivé**\n\n" + TEXTE_APPEL_GARDE +
                      "\n\nPrépare le motif et la date affichés, sans inventer de faits. "
                      "Aucun code de recours n'est transmis par ce bot. Ne publie pas de pièce d'identité dans Discord.",
    }
    cle = _cle(cas)
    cle = {"creer": "creation", "connecter": "connexion", "code": "renvoi", "2fa": "authentificateur",
           "totp": "authentificateur", "authenticator": "authentificateur", "ban": "suspension",
           "banni": "suspension", "recours": "suspension"}.get(cle, cle)
    if cle in aide:
        return aide[cle]
    return ("📱 **Aide Instagram**\n\n"
            "· Créer le compte attribué : `!aide-ig creation`\n"
            "· Se connecter : `!aide-ig connexion`\n"
            "· Code absent ou refusé : `!aide-ig renvoi`\n"
            "· Authentificateur, SMS ou WhatsApp : `!aide-ig authentificateur`\n"
            "· Compte suspendu : `!aide-ig suspension`\n\n" + texte_salon_codes() +
            "\n\nLe bot ne génère pas de codes d'authentificateur et ne soumet pas de recours.")


def actif() -> bool:
    return bool(IMAP_USER and IMAP_PASSWORD)


def _err(erreur) -> str:
    """01/10 : str(TimeoutError()) vaut "" — le type d'abord."""
    return type(erreur).__name__  # Les exceptions de transport peuvent contenir le mail ou la réponse Discord.


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
    if re.match(r"^!code(?:\s|$)", t, re.I):
        return t  # Conserver le choix explicite de l’usage et du compte.
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
DOMAINES_META_CODES = ("meta.com", "metamail.com")
DOMAINES_META = DOMAINES_INSTAGRAM + DOMAINES_META_CODES + ("facebookmail.com", "facebook.com", "fb.com")
# iCloud « Masquer mon adresse » réécrit l'expéditeur : security@mail.instagram.com → security_at_mail_instagram_com_<id>@icloud.com.
# La partie avant « _at_ » n'a pas de « _ », le suffixe non plus : « a_at_mail_instagram_com_at_outlook_com_zz9 » (un faux relayé)
# et « …_instagram_com_exemple_invalid_x1 » (mail.instagram.com.exemple.invalid) sont refusés. 10/10 (revue) : le format exact
# n'est pas vérifié sur un vrai mail ; un tiret dans le suffixe, ou pas de suffixe, est accepté (ni l'un ni l'autre ne peut
# imiter un domaine, qui a toujours un point, donc un « _ »), et un expéditeur au nom de Meta à l'adresse non reconnue part au
# salon admin (Lecteur._expediteur_inconnu) : un écart de format ne fait plus taire les codes en silence.
# 12/10 (vrai mail vu par Gaëtan, codes jamais donnés depuis le 10/10) : la réécriture réelle porte DEUX morceaux après « _com »
# (« no-reply_at_mail_instagram_com_<a>_<b> ») et des sous-domaines variés (support_facebook_com) : tous acceptés désormais.
# Seul garde-fou gardé : pas de second « _at_ » (une adresse relayée d'un autre domaine).
_SANS_2E_AT = r"(?!(?:.*_at_){2})"
RE_ICLOUD_INSTAGRAM = re.compile(_SANS_2E_AT + r"^[a-z0-9.+-]+_at_(?:[a-z0-9-]+_)*instagram_com(?:_[a-z0-9-]+){0,2}$")
RE_ICLOUD_META_CODES = re.compile(_SANS_2E_AT + r"^[a-z0-9.+-]+_at_(?:[a-z0-9-]+_)*(?:meta|metamail)_com(?:_[a-z0-9-]+){0,2}$")
RE_ICLOUD_META = re.compile(_SANS_2E_AT + r"^[a-z0-9.+-]+_at_(?:[a-z0-9-]+_)*(?:instagram|facebookmail|facebook|fb|meta|metamail)_com"
                            r"(?:_[a-z0-9-]+){0,2}$")
MOTS_META = re.compile(r"(?<![a-z0-9])(instagram|facebook|facebookmail|meta)(?![a-z0-9])")


def _domaine_ok(from_header, domaines, motif) -> bool:
    adresse = adresse_expediteur(from_header)
    if "@" not in adresse:
        return False
    local, domaine = adresse.rsplit("@", 1)
    return any(domaine == d or domaine.endswith("." + d) for d in domaines) or (domaine == "icloud.com" and bool(motif.fullmatch(local)))


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
                         r"(?:instagram|facebookmail|facebook|fb|meta|metamail)\.com(?=[\s;)]|$)")


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


def preuve_confirmation_instagram(msg) -> bool:
    """Lire uniquement le résultat du MX Gmail de réception, jamais From seul.

    Aucun résultat inférieur ne remplace le premier. Plusieurs résultats du MX
    attendu sont ambigus et refusés. Aucun nouvel hôte de confiance configurable.
    """
    resultats = [str(v).strip().lower() for v in msg.get_all("Authentication-Results") or []]
    def fiable(valeur):
        return bool(re.match(r"^mx\.google\.com\s*;", valeur))
    if not resultats or not fiable(resultats[0]) or sum(fiable(r) for r in resultats) != 1:
        return False
    resultat = resultats[0]
    def domaine_instagram(domaine):
        return domaine in DOMAINES_INSTAGRAM
    # Les commentaires ne peuvent pas inventer un résultat DKIM/DMARC.
    sans_commentaires = re.sub(r"\([^()]*\)", " ", resultat)
    for section in sans_commentaires.split(";")[1:]:
        section = section.strip()
        if re.match(r"^dkim=pass(?:\s|$)", section):
            domaines = re.findall(r"(?:^|\s)header\.d=([^\s;]+)", section)
            if len(domaines) == 1 and domaine_instagram(domaines[0]):
                return True
        if re.match(r"^dmarc=pass(?:\s|$)", section):
            domaines = re.findall(r"(?:^|\s)header\.from=([^\s;]+)", section)
            if len(domaines) == 1 and domaine_instagram(domaines[0]):
                return True
    # ARC : seule l'attestation explicite DKIM Instagram du MX est utilisable.
    for section in resultat.split(";")[1:]:
        m = re.fullmatch(r"\s*arc=pass\s*\(([^()]*)\)\s*", section)
        if m and re.search(r"(?:^|\s)dkim=pass(?:\s|$)", m[1]):
            domaines = re.findall(r"(?:^|\s)dkdomain=([^\s]+)", m[1])
            if len(domaines) == 1 and domaine_instagram(domaines[0]):
                return True
    return False


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
# 14/10 : la vérification d'identité (déblocage d'un compte) : neutralisée avant la liste noire, puis reconnue comme but.
VERIFIER_IDENTITE = re.compile(
    r"(?:votre )?code de confirmation d'adresse e-?mail|confirmer votre identite|(?:nous devons )?verifier votre adresse e-?mail|"
    r"verifiez votre adresse e-?mail|confirm your identity|verify your identity|(?:we need to )?verify your email(?: address)?|"
    r"(?:your )?email(?: address)? confirmation code|confirmar tu identidad|verificar tu (?:direccion de )?correo(?: electronico)?|"
    r"confirmar (?:a )?sua identidade|verificar (?:o )?seu (?:endereco de )?e-?mail|confermare la tua identita|"
    r"verificare il tuo indirizzo e-?mail|deine identitat (?:zu )?bestatigen|deine e-?mail-adresse (?:zu )?(?:bestatigen|verifizieren)")
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
    r"log ?in|logging in|sign(?:ing)? in|unusual login", r"se connecter|tentative de connexion|connexion inhabituelle|code de connexion",
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


SERVICES_EMAIL = {"instagram": "Instagram", "facebook": "Facebook", "meta": "Meta"}


def service_du_mail(from_header, sujet, corps):
    if expediteur_instagram(from_header):
        return "instagram"
    if expediteur_meta_codes(from_header):
        entete = plat(str(sujet)) + " " + _sans_pied(plat(str(corps)))[:400]
        if re.search(r"\binstagram\b", entete):
            return "instagram"
        if re.search(r"\bfacebook\b", entete):
            return "facebook"
        return "meta"
    return "facebook" if expediteur_meta(from_header) else ""


_FACTEUR_EMAIL = re.compile(r"two[- ]?factor(?: authentication)?|\b2fa\b|deux facteurs|double authentification|"
                             r"authentication code|code d'authentification", re.I)


def _sans_service_otp(texte, service, connexion):
    # Le nom du service n'est pas une modification de compte. La 2FA n'est
    # neutralisée que pour un OTP de connexion envoyé par e-mail, jamais une graine.
    marque = {"facebook": r"\bfacebook\b", "meta": r"\bmeta(?: account)?\b|compte meta",
              "instagram": r"\binstagram\b"}.get(service, r"(?!)")
    texte = re.sub(marque, " _service_ ", texte)
    if connexion:
        texte = re.sub(r"accounts? cent(?:er|re)|espace comptes|centre de comptes", " _centre_ ", texte)
    return _FACTEUR_EMAIL.sub(" _facteur_email_ ", texte) if connexion else texte


def _code_service_email(service, sujet, corps, complets, code, compte):
    """Nouveaux modèles FB/Meta : but explicite, contrôle de toutes les parties MIME."""
    principal = _sans_pied(plat(sujet + " . " + corps), code)
    if re.search(r"\binstagram\b", principal) and service != "instagram":
        return None
    connexion = bool(CONNEXION_RE.search(_sans_pseudos(principal)))
    creation = bool(CREATION_RE.search(_sans_pseudos(principal)))
    verification = bool(CODES_VERIFICATION and (CONFIRMER_EMAIL.search(principal) or VERIFIER_IDENTITE.search(principal)))
    if not (connexion or creation or verification):
        return None
    for partie in [sujet, corps] + list(complets or []):
        lu, avert = _avertissements(_lisible(partie, compte, code), code)
        lu = _sans_service_otp(lu, service, connexion)
        if _noire(lu) or APPEL_RE.search(lu) or any(plat(code) in phrase for phrase in avert):
            return None
    if not langue_lue(principal):
        return None
    return "creation" if creation else "connexion" if connexion else "verification"


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
    t = VERIFIER_IDENTITE.sub(" _verification_ ", t) if CODES_VERIFICATION else t
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


AJOUT_ADRESSE = "e-mail ajouté ou changé"


def _seulement_adresse(*textes) -> bool:
    """18/10 (Pierre : trois codes de création gardés, « e-mail ajouté ou changé ») : vrai si, dans ces textes, la SEULE famille
    de la liste noire touchée est celle de l'adresse e-mail (ni mot de passe, ni récupération, ni téléphone, ni 2FA…)."""
    familles = {libelle for t in textes for libelle, motif in NOIRE_RE if motif.search(t or "")}
    return familles == {AJOUT_ADRESSE}


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


# Mail standard Instagram issu du parcours d'inscription / connexion.
# Il est souvent suivi d'un pied de page Meta contenant "Facebook", "e-mail",
# "password" ou "authentication". Ce pied ne doit pas changer le but du code.
# La décision ne se fonde JAMAIS sur le nom affiché de l'expéditeur.
_SUJET_CODE_INSTAGRAM = re.compile(
    r"^\s*[0-9]{5,8}\s+(?:is your instagram code|est votre code instagram)\s*[.!]?\s*$", re.I)
_MUTATION_CODE = re.compile(
    r"(?:reset|change|changing|changed|update|updating|updated|remove|removing|add|adding|added|"
    r"recover|recovery|forgot|forgotten|restore|appeal|disable|enable|turn off|turn on|delete|deleting|"
    r"link|unlink|set up|setup|configure|configur\w*|associer|lier|dissocier|"
    r"reinitialis\w*|reinitializ\w*|modifi\w*|chang\w*|ajout\w*|supprim\w*|"
    r"recup\w*|oubli\w*|desactiv\w*|activ\w*|deban\w*|appel)\b.{0,65}?"
    r"(?:password|mot de passe|email|e-mail|adresse|phone|telephone|numero|username|"
    r"pseudo|authent(?:icat|ifi)\w*|securit\w*|security|account|compte|2fa|two.factor)"
    r"|(?:password|mot de passe|email|e-mail|adresse|phone|telephone|numero|username|"
    r"pseudo|2fa|two.factor)\b.{0,65}?(?:reset|chang\w*|modifi\w*|updat\w*|"
    r"remov\w*|ajout\w*|add(?:ing|ed)?\b|desactiv\w*|activ\w*)",
    re.I,
)


def _code_standard_connexion(sujet: str, corps: str, code: str) -> str:
    """Recognize only Meta's exact 6-digit subject; reject explicit account mutations."""
    sujet = unicodedata.normalize("NFKC", str(sujet or ""))
    if not _SUJET_CODE_INSTAGRAM.fullmatch(sujet):
        return ""
    # Only the meaningful text, excluding the boilerplate footer. If the core
    # requests a sensitive change, refuse even when the subject is generic.
    pertinent = _sans_pied(plat(str(corps or "")[:1000]), code)
    sans_avertissement, _ = _avertissements(pertinent, code)
    if _MUTATION_CODE.search(sans_avertissement):
        return ""
    if APPEL_RE.search(_sans_pseudos(sans_avertissement)):
        return ""
    return "creation" if CREATION_RE.search(_sans_pseudos(sans_avertissement)) else "connexion"


def _verification_profil_connexion(sujet: str, corps: str, code: str) -> bool:
    """Recognize a normal 'Verify your profile' login, not an account change."""
    if str(sujet).strip().lower() != "verify your profile" or not code:
        return False
    debut = plat(corps).split(plat(code), 1)[0]
    return (bool(re.search(r"someone tried to log in to your instagram profile", debut))
            and bool(re.search(r"following code to confirm your identity", debut))
            and not _MUTATION_CODE.search(debut))


_EMAIL_IDENTITY_SUBJECT = re.compile(
    r"^votre code de confirmation d[’']adresse e-?mail\s*$", re.I)
_EMAIL_IDENTITY_CONTEXT = re.compile(
    r"pour confirmer votre identite sur instagram.{0,140}"
    r"nous devons verifier votre adresse e-?mail", re.I)


def _verification_identite_existante(sujet: str, corps: str, code: str) -> bool:
    """Instagram identity challenge to the account's EXISTING mailbox.

    Must not turn an address-change or account-recovery OTP into a login code.
    Only trust the exact template and meaningful context around the OTP.
    """
    if not CODES_VERIFICATION or not code:
        return False
    if not _EMAIL_IDENTITY_SUBJECT.fullmatch(plat(sujet)):
        return False
    texte = plat(corps)
    indice = texte.find(plat(code))
    if indice < 0:
        return False
    avant = texte[:indice]
    if not _EMAIL_IDENTITY_CONTEXT.search(avant):
        return False
    if _MUTATION_CODE.search(avant) or APPEL_RE.search(_sans_pseudos(avant)):
        return False
    # No explicit request to change the account's recovery address/password.
    if re.search(r"(?:changer|modifier|ajouter|supprimer|reinitialiser|recuperer)"
                 r".{0,55}(?:adresse|e-?mail|mot de passe|numero|compte)", avant):
        return False
    return True


_INSCRIPTION = re.compile(r"(?:someone )?tried to sign up for (?:an )?instagram(?: account)?|"
                          r"(?:une personne )?a tente de creer un compte (?:an )?instagram")
_PAS_INSCRIPTION = re.compile(r"password|mot de passe|reset|reinitialis|recover|recup|forgot|oubli|settings|parametres|reglages|"
                              r"\bchang\w*|\bmodif\w*|\bupdat\w*|backup|secours|two.factor|deux facteurs|authenticator|authentificat")


def _inscription_instagram(sujet, corps) -> bool:
    """18/10 : vrai pour le seul modèle d'inscription d'Instagram (« tried to sign up » / « a tenté de créer un compte »), sans
    aucun mot de changement, de mot de passe, de réglages ou de double authentification dans le début du mail."""
    debut = plat(f"{sujet} . {corps}")[:700]
    return bool(_INSCRIPTION.search(debut)) and not _PAS_INSCRIPTION.search(debut)


def confirmation_email_fr(sujet):
    return bool(re.fullmatch(r"confirmer l'adresse e-?mail[.!]?", plat(sujet).strip()))


def _confirmation_email_fr(sujet, corps, compte):
    """Modèle distinct de la connexion : code isolé, compte explicite et but borné."""
    if not CODES_VERIFICATION or not confirmation_email_fr(sujet) or not compte:
        return None
    texte = plat(corps)
    codes = re.findall(r"(?m)^\s*([0-9]{6})\s*$", texte)
    if len(set(codes)) != 1:
        return None
    if not re.search(r"(?:confirmer|confirmez|verifier|verifiez).{0,40}(?:adresse e-?mail|e-?mail)", texte):
        return None
    return codes[0]


# 18/10, 13 h 52 (Gaëtan : « Donne tous les codes SAUF changer les informations, mots de passe et mail ») : ce qui fait d'un code
# Meta un code de CHANGEMENT, jamais donné. Lu dans tout le mail (sujet, corps, toutes les parties).
CHANGEMENT_RE = re.compile(
    r"password|mot de passe|contrasena|senha|passwort|\bmdp\b|reset\w*|reinitialis\w*|recover\w*|recup\w*|forgot\w*|oubli\w*|"
    r"backup codes?|codes? de secours|secret key|cle secrete|totp|authenticator app|settings|parametres|reglages|"
    r"\b(?:chang\w*|modif\w*|updat\w*|mettre a jour|mis a jour|remplac\w*|replac\w*|supprim\w*|delet\w*|remov\w*|"
    r"ajout\w*|add(?:ed|ing)?|new email|nouvelle adresse|e-?mail address change|email change)\b")


REGLAGES_RE = re.compile(r"modif\w* (?:the |your )?(?:settings|parametres|reglages)|tried to modify|tente de modifier|"
                         r"(?:change|update|modifier|changer) (?:your |votre |the |l.)?(?:email|e-mail|adresse|password|mot de passe)|"
                         r"reset (?:your )?password|reinitialiser (?:votre )?mot de passe")


def classer(from_header, sujet: str, corps: str, complets=None) -> dict:
    """La décision de _classer_base ; pour un code gardé d'un mail Meta ou Instagram, garde aussi le code (code_brut, jamais
    affiché ni stocké tant qu'il n'est pas donné) et dit s'il parle d'un changement (promouvoir_creation décide)."""
    info = _classer_base(from_header, sujet, corps, complets)
    if info.get("decision") == "donner" and info.get("code"):
        # 18/10 (Diamondra : « Authenticate your profile — Someone tried to modify settings ») : un code dont la phrase d'avant
        # dit qu'on MODIFIE les réglages, le mot de passe ou l'e-mail n'est jamais donné, même au format d'un code de connexion.
        avant = plat(INVISIBLES.sub("", str(corps or ""))).split(plat(str(info["code"])), 1)[0][-400:]
        if REGLAGES_RE.search(avant):
            return dict(info, decision="garder", code=None, libelle="changement des réglages, du mot de passe ou de l'e-mail")
        return info
    if info.get("decision") != "garder" or not expediteur_meta(from_header):
        return info
    s_, c_ = INVISIBLES.sub("", str(sujet or "")), INVISIBLES.sub("", str(corps or ""))
    code = info.get("code") or _code_du_mail(s_, c_[:600])
    if not code:
        return info
    tout = " ".join(plat(x) for x in [s_, c_] + list(complets or []))
    return dict(info, code_brut=code, changement=bool(CHANGEMENT_RE.search(tout)))


def _classer_base(from_header, sujet: str, corps: str, complets=None) -> dict:
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
    sortie = {"decision": "rien", "type": "", "code": code, "libelle": "", "compte": compte,
              "service": service_du_mail(from_header, sujet, corps)}
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
    if not SECURITES:
        # 12/10 (Gaëtan : « Enlève les sécurités sur le 2FA… il faut que le 2FA marche à tous les coups ») : tout code d'un
        # mail Meta est donné ; le type ne sert qu'au libellé.
        typ = "creation" if CREATION_RE.search(blanc) else ("appel" if APPEL_RE.search(blanc) else "connexion")
        return dict(sortie, decision="donner", type=typ, libelle=QUOI.get(typ, "connexion"))
    for partie in [sujet, corps] + list(complets or []):
        pertinent, _ = _avertissements(_sans_pied(plat(partie), code), code)
        if (_MUTATION_CODE.search(pertinent) or re.search(
                r"\btotp\b|authenticator|authentificateur|backup codes?|codes? de secours|"
                r"secret key|cle secrete|recovery (?:key|codes?)|graine|\botpauth\b", pertinent)):
            return dict(sortie, decision="garder", code=None, libelle="récupération ou sécurité du compte")
    if confirmation_email_fr(sujet):
        confirme = _confirmation_email_fr(sujet, corps, compte)
        if expediteur_instagram(from_header) and confirme:
            return dict(sortie, decision="donner", code=confirme, type="verification",
                        libelle=QUOI["verification"], confirmation_adresse=True)
        return dict(sortie, decision="garder", code=None, libelle="confirmation e-mail non vérifiable")
    service = sortie["service"]
    reconnu = _code_service_email(service, sujet, corps, complets, code, compte)
    if reconnu:
        return dict(sortie, decision="donner", type=reconnu, libelle=QUOI[reconnu])
    if not expediteur_instagram(from_header):
        # 18/10 (Diamondra : « Authenticate your profile » de Meta, gardé trois fois pendant la création de son compte 1) : le
        # nouveau parcours d'inscription Instagram passe par un compte Meta. Un code Meta sans aucune famille sensible (ou la
        # seule adresse e-mail) reste gardé ici, mais peut devenir un code de création si le compte de l'adresse n'est pas créé.
        profil = re.compile(r"authenticate your profile|authentifie[rz] votre profil|authentification de (?:votre )?profil")
        familles = {libelle for t in [texte] + [_lisible(x, compte, code) for x in complets or []]
                    for libelle, motif in NOIRE_RE if motif.search(profil.sub(" ", t or ""))}
        return dict(sortie, decision="garder", libelle="OTP e-mail sans but sûr reconnu",
                    ajout_adresse=expediteur_meta(from_header) and familles <= {AJOUT_ADRESSE})
    # Les anciens modèles Instagram restent compatibles ; une mention 2FA ambiguë
    # sans but de connexion explicite ne doit pas emprunter leur raccourci.
    if any(_FACTEUR_EMAIL.search(_sans_pied(plat(t), code)) for t in [sujet, corps] + list(complets or [])):
        return dict(sortie, decision="garder", code=None, libelle="double authentification sans connexion explicite")
    if expediteur_instagram(from_header):
        standard = _code_standard_connexion(sujet, corps, code)
        if standard or _verification_profil_connexion(sujet, corps, code):
            return dict(sortie, decision="donner", type=standard or "connexion", libelle=QUOI[standard or "connexion"])
        # The identity confirmation template is not a change-of-email request;
        # classify it before scanning boilerplate mentions of other Meta services.
        if _verification_identite_existante(sujet, corps, code):
            return dict(sortie, decision="donner", type="verification", libelle=QUOI["verification"])
    # Confirmation d'identité sur l'adresse déjà associée à un compte IG.
    # Décider sur l'intention AVANT le code et ignorer les mentions Meta en pied.
    # Ne jamais autoriser une modification d'e-mail ou de mot de passe.
    if expediteur_instagram(from_header) and CODES_VERIFICATION:
        # Vérification d'identité sur l'adresse de compte déjà enregistrée :
        # les mentions génériques de Meta situées sous le code ne font pas
        # de cet e-mail une modification des paramètres du compte.
        debut = plat(corps).split(plat(code), 1)[0]
        sujet_lu = plat(sujet)
        confirmation = bool(re.search(r"confirmation|verifiez votre adresse|verify your email", sujet_lu))
        verification = bool(re.search(r"confirmer votre identite sur instagram|confirm your identity on instagram", debut))
        adresse = bool(re.search(r"verifier votre adresse e.mail|verify your email address", debut))
        action = bool(re.search(r"\b(?:chang\w*|modifi\w*|ajout\w*|supprim\w*|reinitialis\w*|reset|remov\w*|add(?:ing|ed)?)\b", debut))
        if confirmation and verification and adresse and not action:
            return dict(sortie, decision="donner", type="verification", libelle=QUOI["verification"])
    # 18/10 (Gaëtan : « Ceux-là tu peux renvoyer sans même ouvrir le mail ») : le modèle d'INSCRIPTION d'Instagram, en anglais
    # (« Someone tried to sign up for Instagram with <adresse> ») et en français (« Une personne a tenté de créer un compte
    # Instagram en utilisant l'adresse courriel suivante »). Il ne sert qu'à créer un compte neuf avec cette adresse : code de
    # création, même si le texte cite l'« adresse courriel ». Jamais s'il parle aussi de mot de passe, de réglages ou de changement.
    if expediteur_instagram(from_header) and _inscription_instagram(sujet, corps):
        return dict(sortie, decision="donner", type="creation", libelle=QUOI["creation"])
    libelle = _noire(texte)
    if libelle:
        return dict(sortie, decision="garder", libelle=libelle,
                    ajout_adresse=libelle == AJOUT_ADRESSE and expediteur_instagram(from_header)
                    and _seulement_adresse(texte, *[_lisible(x, compte, code) for x in complets or []]))
    if any(plat(code) in phrase for phrase in avert):
        return dict(sortie, decision="garder", libelle="code dans une phrase « si ce n'était pas vous »")
    for partie in complets or []:                                      # tout l'e-mail, pied de page exclu
        lu, avert_p = _avertissements(_lisible(partie, compte, code), code)
        libelle = _noire(lu)
        if libelle:
            return dict(sortie, decision="garder", libelle=f"{libelle} (plus bas dans l'e-mail)",
                        ajout_adresse=libelle == AJOUT_ADRESSE and expediteur_instagram(from_header)
                        and _seulement_adresse(texte, *[_lisible(x, compte, code) for x in complets or []]))
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
    """Refuser les destinataires ambigus plutôt que choisir le premier compte au hasard."""
    adresses = set()
    for nom in ("To", "X-Original-To", "Delivered-To"):
        for valeur in msg.get_all(nom) or []:
            for _, adresse in email.utils.getaddresses([str(valeur)]):
                adresse = adresse.strip().lower()
                if "@" in adresse and adresse != IMAP_USER.lower():
                    adresses.add(adresse)
    return next(iter(adresses)) if len(adresses) == 1 else ""


def cle_du_mail(msg) -> str:
    """Le Message-ID, sinon une empreinte stable (expéditeur, date, sujet) : un mail remonté du Spam garde sa clé."""
    mid = str(msg.get("Message-ID") or "").strip()
    empreinte = "|".join(str(msg.get(k) or "") for k in ("From", "To", "Date", "Subject"))
    return mid or "sha256:" + hashlib.sha256(empreinte.encode("utf-8")).hexdigest()


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
        date = email.utils.parsedate_to_datetime(msg.get("Date"))
        if date.tzinfo is None:
            raise ValueError("date sans fuseau")
        date = date.astimezone(timezone.utc)
    except Exception:                                                   # noqa: BLE001
        date = datetime(1970, 1, 1, tzinfo=timezone.utc)
    alias = alias_du_mail(msg)
    if confirmation_email_fr(sujet):
        # Le nouveau modèle exige une authentification attestée, même en envoi direct.
        corps_alias = {a.lower() for a in ADRESSES.findall(texte_du_mail(msg))
                       if a.lower() != IMAP_USER.lower()}
        candidat = next(iter(corps_alias)) if len(corps_alias) == 1 else ""
        # Plusieurs destinataires explicites ne sont jamais remplacés par un alias du corps.
        entetes = set()
        for nom in ("To", "X-Original-To", "Delivered-To"):
            entetes.update(a.lower() for _, a in email.utils.getaddresses(msg.get_all(nom) or [])
                           if "@" in a and a.lower() != IMAP_USER.lower())
        if (not info.get("confirmation_adresse") or not preuve_confirmation_instagram(msg)
                or len(entetes) > 1 or len(corps_alias) > 1 or (alias and candidat and alias != candidat)
                or not (alias or candidat)):
            info.update(decision="garder", code=None, libelle="confirmation e-mail : provenance ou alias non vérifiable")
        else:
            alias = alias or candidat
    info.update(alias=alias, sujet=sujet, date=date, mid=cle_du_mail(msg),
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


def _dossiers_speciaux(lignes) -> dict:
    r"""Discover RFC 6154 \All / \Junk folder names (Gmail can localize them)."""
    found = {}
    for item in lignes or []:
        raw = item.decode("utf-8", "replace") if isinstance(item, bytes) else str(item or "")
        match = re.match(r'^\(([^)]*)\)\s+\S+\s+(.+)$', raw)
        if not match:
            continue
        flags, mailbox = match.groups()
        mailbox = mailbox.strip().strip('"')
        if re.search(r"\\All\b", flags, re.I):
            found["all"] = mailbox
        if re.search(r"\\(?:Junk|Spam)\b", flags, re.I):
            found["spam"] = mailbox
    return found


class Lecteur:
    """Le SEUL lecteur de la boîte (10/10). Bloquant : appelé par boucle_codes via asyncio.to_thread, jamais deux à la fois.
    État : {dossier: {"validite": UIDVALIDITY, "dernier": dernier UID lu}} — persistant, donc un redémarrage ne relit rien
    de déjà vu. Un premier passage (ou un UIDVALIDITY changé) lit seulement les mails Meta des JOURS_AMORCE derniers jours.
    10/10 (revue) : l'état (UID, Message-ID vus) n'avance qu'EN FIN de passage réussi ; une coupure au milieu, un FETCH refusé
    ou un corps vide font échouer le passage, et le suivant relit les mêmes mails (l'ancien code relisait les 15 derniers
    mails à chaque tour et se rattrapait seul ; le lecteur incrémental ne le fait plus, il ne doit donc rien sauter)."""

    def __init__(self):
        self.boite = None
        self.speciales = None
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
        # INBOX covers categories; All Mail may be localized by the IMAP server.
        if self.speciales is None:
            noms = (IMAP_DOSSIER, DOSSIER_TOUS, DOSSIER_SPAM)
        else:
            tous = self.speciales.get("all") or (DOSSIER_TOUS if os.environ.get("CODES_IMAP_TOUS") else "")
            noms = (IMAP_DOSSIER, tous, self.speciales.get("spam") or DOSSIER_SPAM)
        return list(dict.fromkeys(nom for nom in noms if nom))

    def fermer(self):
        boite, self.boite, self.selection, self.validite = self.boite, None, None, None
        if boite is not None:
            try:
                boite.logout()
            except Exception:                                           # noqa: BLE001
                try:
                    boite.shutdown()
                except Exception:
                    pass

    def _connecter(self):
        boite = imaplib.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT)
        self.boite = boite  # reste fermable même si LOGIN échoue
        boite.login(IMAP_USER, IMAP_PASSWORD)
        self.boite, self.selection = boite, None
        self.speciales = None
        self.idle = "IDLE" in tuple(str(c).upper() for c in (getattr(boite, "capabilities", ()) or ()))
        try:
            ok, lignes = boite.list()
            if ok == "OK":
                self.speciales = _dossiers_speciaux(lignes)
                journal.info("Codes : dossiers IMAP détectés : Tous=%s, Spam=%s",
                             bool(self.speciales.get("all")), bool(self.speciales.get("spam")))
        except Exception as erreur:
            # A LIST error cannot prevent the primary inbox from being scanned.
            journal.warning("Codes : LIST IMAP indisponible : %s", _err(erreur))

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
                journal.warning("Codes : dossier %s ignoré ce passage : %s", dossier, _err(erreur))   # un Spam absent ne bloque rien
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
        controle = getattr(self, "controle_recherche", None)
        filtre = getattr(self, "filtre_recherche", None)
        for i in range(0, len(uids), 50):
            if controle:
                controle()
            lot = uids[i:i + 50]
            ok, data = self.boite.uid("FETCH", ",".join(str(u) for u in lot), champs)
            if ok != "OK":
                raise imaplib.IMAP4.error(f"en-têtes illisibles ({dossier})")
            paires = _paires_fetch(data)
            recus = {u for u, _ in paires}
            for u in lot:
                if controle:
                    controle()
                if u not in recus and self._existe(u) and not self._sauter(dossier, u, "en-têtes"):
                    raise MailIllisible(f"en-têtes du mail UID {u} absents ({dossier})")
            for uid, entetes in paires:
                if controle:
                    controle()
                tete = email.message_from_bytes(entetes or b"")
                if filtre and not filtre(tete):
                    continue
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
                journal.warning("Codes : déplacement depuis %s : %s", dossier, _err(erreur))
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
        # Ne jamais restituer des codes mis en cache sous l'ancien mode non filtré :
        # certains pouvaient venir d'une modification de compte Instagram.
        mode = "strict_context_v3_services"
        if _ETAT.get("mode_codes") != mode:
            _ETAT["codes"] = []
            _ETAT["mode_codes"] = mode
            journal.info("Codes : cache invalidé suite à un changement de mode")
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
        f.write_text(json.dumps(dict(e, codes=[]), ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as erreur:
        journal.warning("codes_lecteur.json non écrit : %s", _err(erreur))


def _iso(date) -> str:
    return date.astimezone(timezone.utc).isoformat(timespec="seconds") if isinstance(date, datetime) else str(date or "")


def _date(t) -> datetime:
    try:
        date = datetime.fromisoformat(str(t.get("date")))
        return date.astimezone(timezone.utc) if date.tzinfo is not None else datetime(1970, 1, 1, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _age_min(t) -> int:
    return max(0, int((_maintenant() - _date(t)).total_seconds() // 60))


def _cle_tri(t) -> tuple:
    """La date de l'e-mail, puis l'ordre d'arrivée (10/10, revue : à la seconde près, le tri montrait le plus ancien)."""
    return (_date(t), int(t.get("n") or 0))


def _numeroter(entree: dict) -> dict:
    e = _etat()
    e["dernier_code"] = _maintenant().isoformat(timespec="seconds")   # 18/10 : la surveillance du silence (action 26)
    e["n"] = int(e.get("n") or 0) + 1
    entree["n"] = e["n"]
    return entree


def codes_recents(adresses, minutes: int = None, decision: str = "donner") -> list:
    """Les entrées du cache (« donner » ou « garder ») des `adresses`, plus récentes d'abord, dans la fenêtre."""
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    adresses = {str(a).strip().lower() for a in adresses or []}
    limite = _maintenant() - timedelta(minutes=minutes)
    trouves = [t for t in _etat()["codes"] if t.get("alias") in adresses and t.get("decision") == decision
               and limite <= _date(t) <= _maintenant() + timedelta(minutes=2)]
    return sorted(trouves, key=_cle_tri, reverse=True)


ORPHELIN_MIN = int(os.environ.get("CODES_ORPHELIN_MIN", "10") or 10)


def codes_pour(adresses, minutes: int = None, tout: bool = False) -> list:
    """12/10 (Gaëtan : « ça lui sort le 2FA le plus récent… il faut que le 2FA marche à tous les coups ») : les codes donnables
    pour celui qui demande, plus récents d'abord : ceux de ses adresses ; plus les codes reçus depuis ORPHELIN_MIN minutes sur une
    adresse que personne d'autre n'a (alias tapé autrement, adresse jamais rattachée) ; `tout` (staff) : tous les codes."""
    if SECURITES:
        # Seul ADMIN_IDS peut demander le dernier code admissible de la boîte entière.
        # Pas de repli "orphelin" pour les clippers : un alias doit appartenir à leur UID.
        if tout:
            limite = _maintenant() - timedelta(minutes=SALON_CODES_MINUTES if minutes is None else minutes)
            return sorted((t for t in _etat()["codes"] if t.get("decision") == "donner"
                           and t.get("code") and limite <= _date(t) <= _maintenant() + timedelta(minutes=2)),
                          key=_cle_tri, reverse=True)
        return codes_recents(adresses, minutes)
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    adresses = {str(a).strip().lower() for a in adresses or []}
    maintenant = _maintenant()
    limite, limite_o = maintenant - timedelta(minutes=minutes), maintenant - timedelta(minutes=ORPHELIN_MIN)
    registre = _lire()

    def a_un_autre(alias: str) -> bool:
        v = registre.get(alias)
        return isinstance(v, dict) and bool(v.get("canal_id"))
    trouves = []
    for t in _etat()["codes"]:
        if t.get("decision") != "donner" or not t.get("code"):
            continue
        d = _date(t)
        if d < limite:
            continue
        alias = str(t.get("alias") or "")
        if tout or alias in adresses or (d >= limite_o and not a_un_autre(alias)):
            trouves.append(t)
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
# Références privées en mémoire uniquement : aucun jeton d'interaction persisté.
_reponses_privees = {}
_verrous_reponses = {}
_presentations = {}
_verrous_guets = {}


def reponse_privee_unique(cle, nouveau, fermer=None):
    """Réédite la même réponse pour cet UID et cette surface privée.

    Une réponse Discord supprimée/expirée nécessite une nouvelle réponse privée.
    Un échec ambigu ne déclenche jamais une seconde livraison.
    """
    boucle = asyncio.get_running_loop()
    entree = _verrous_reponses.get(cle)
    if entree is None or entree[0] is not boucle:
        entree = (boucle, asyncio.Lock())
        _verrous_reponses[cle] = entree
    ferme = False

    async def dire(texte):
        nonlocal ferme
        async with entree[1]:
            cible = _reponses_privees.get(cle, nouveau)
            try:
                await cible(texte)
            except discord.HTTPException as erreur:
                if cible is nouveau or getattr(erreur, "status", None) not in (401, 404):
                    raise
                await nouveau(texte)
                cible = nouveau
            _reponses_privees[cle] = cible
            if cible is not nouveau and fermer is not None and not ferme:
                try:
                    await fermer()
                except discord.HTTPException:
                    pass  # Aucun code dans l'accusé provisoire.
                ferme = True
    dire.surface_privee = cle[1]
    dire.cle_privee = cle
    return dire


def verrou_guet(cle):
    boucle = asyncio.get_running_loop()
    entree = _verrous_guets.get(cle)
    if entree is None or entree[0] is not boucle:
        entree = (boucle, asyncio.Lock())
        _verrous_guets[cle] = entree
    return entree[1]


_SANTE = {"ok_t": None, "echecs": 0, "erreur": ""}
_deps = {}


def configurer(deps: dict):
    """deps : canal_admin (coroutine → salon admin), adresses_de_membre (uid → set), est_staff (membre → bool),
    admin_ids (ensemble d'identifiants), destinataire_alias (alias → propriétaire UID unique)."""
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


def sante_publique() -> dict:
    """Diagnostic agrégé : aucune adresse, contenu, erreur brute ou valeur d'accès."""
    actif_ = actif()
    dernier = _SANTE.get("ok_t")
    age = max(0, int(time.monotonic() - dernier)) if dernier is not None else None
    return {"actif": actif_, "dernier_succes_s": age,
            "echecs_consecutifs": int(_SANTE.get("echecs") or 0),
            "echecs_traitement": int(_SANTE.get("traitement_echecs") or 0),
            "etat": "eteint" if not actif_ else "inconnu" if age is None else
                    "degrade" if _SANTE.get("echecs") or _SANTE.get("traitement_echecs") or age > max(120, SONDAGE_SEC * 3) else "ok"}


def lecteur_en_panne() -> bool:
    return _SANTE["echecs"] > 0 and (_SANTE["ok_t"] is None or time.monotonic() - _SANTE["ok_t"] > 120)


# ------------------------------------------------------------------ 4. la réponse privée
def _ligne_privee(t: dict) -> str:
    compte = f" · compte `@{t['compte']}`" if t.get("compte") else ""
    age = _age_min(t)
    quand = "reçu à l'instant" if age < 1 else f"reçu il y a {age} min"
    service = SERVICES_EMAIL.get(t.get("service", "instagram"), "Meta")
    return (f"🔐 **Code {service} · {QUOI.get(t.get('type'), 'connexion')}**{compte}\n\n"
            f"Adresse `{t.get('alias', '')}` · {quand} :\n```\n{t['code']}\n```")


def _texte_codes(codes: list) -> str:
    """Afficher uniquement le code de connexion/inscription le plus récent du destinataire autorisé."""
    return _ligne_privee(max(codes, key=_cle_tri)) if codes else ""


def _texte_ancien(t: dict) -> str:
    return "🕰️ Le précédent code a expiré. Demande un nouveau code dans Instagram."


_MONTRES = {}                                                          # cle_guet → {Message-ID: date ISO où le code a été montré}


def _deja_montre(cle_guet: str, t: dict):
    """La date où ce code a déjà été montré à ce clipper, ou None (10/10, revue : « déjà donné il y a 2 min »)."""
    quand = (_MONTRES.get(cle_guet) or {}).get(t.get("mid"))
    return {"date": quand} if quand else None


def _noter_montre(cle_guet: str, codes: list):
    limite = _iso(_maintenant() - timedelta(minutes=CACHE_MIN))
    vus = {k: v for k, v in (_MONTRES.get(cle_guet) or {}).items() if v >= limite}
    for t in codes[:1]:
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
        note = (f"-# Déjà donné {quand}. S'il est refusé, appuie sur « Renvoyer le code » dans l’application concernée : je guette le "
                "suivant, il s'affiche ici tout seul.")
    else:
        note = TEXTE_REFUSE
    return _texte_codes(codes) + "\n\n" + note


USAGES_EMAIL = {"creation": "Créer un compte", "connexion": "Me connecter",
                "verification": "Vérifier mon e-mail"}
TEXTE_CHOIX = ("📩 Choisis le compte et ce qu’Instagram te demande.\n\n"
               "Un code d’application d’authentification, SMS ou WhatsApp ne vient pas de cette boîte e-mail. "
               "Les codes de récupération et les changements de sécurité restent réservés au titulaire.")


def _codes_demande(adresses, usage, depuis):
    """Le bon compte, un usage étiqueté et une date sûre ; aucun mélange entre contextes."""
    if not adresses or (usage != "auto" and (len(adresses) != 1 or usage not in USAGES_EMAIL)):
        return []
    limite = depuis                                                     # 18/10 : le recul de 20 minutes, aussi en « Mon code »
    candidats = [t for t in codes_recents(adresses, FRAIS_MIN)
                 if t.get("type") in USAGES_EMAIL and (usage == "auto" or t.get("type") == usage)
                 and t.get("code") and _date(t) >= limite
                 and t.get("service", "instagram") in SERVICES_EMAIL]
    vus, derniers = set(), []
    for t in candidats:
        contexte = (t.get("alias"), t.get("service", "instagram"), t.get("type"))
        if contexte not in vus:
            vus.add(contexte)
            derniers.append(t)
    # 18/10 (Gaëtan : « juste renvoie le dernier code envoyé les 20 dernières minutes ») : le dernier code de chaque compte et de
    # chaque service (Instagram, Facebook, Meta), jamais un ancien du même contexte.
    return derniers


def _texte_codes_auto(codes):
    blocs = []
    for t in codes:
        bloc = _ligne_privee(t)
        if len("\n\n".join(blocs + [bloc])) > 1500:
            break
        blocs.append(bloc)
    if len(blocs) < len(codes):
        blocs.append("D'autres codes récents sont disponibles : utilise !code connexion adresse pour cibler un compte.")
    return "\n\n".join(blocs)


async def _servir(adresses: set, dire, cle_guet: str, duree: int = None, minutes: int = None, relire=None,
                  tout: bool = False, usage: str = "") -> str:
    """Une demande explicite, privée, pour un seul compte. Toute nouvelle demande remplace le guet précédent.

    Deux minutes de recul à l'appui, puis cinq minutes d'attente ; jamais de retour à un code ancien
    ou d'un autre usage. `tout` est conservé pour compatibilité, sans élargir l'accès à la boîte.
    """
    if not adresses or (usage != "auto" and (len(adresses) != 1 or usage not in USAGES_EMAIL)):
        await dire(TEXTE_CHOIX)
        return "choix"
    duree = ATTENTE_SEC if duree is None else duree
    depuis = _maintenant() - timedelta(minutes=FRAIS_MIN)              # 18/10 (Gaëtan) : le dernier code des 20 dernières minutes
    guet = {"dire": dire, "texte": TEXTE_ATTENTE}
    verrou = verrou_guet(cle_guet)
    async with verrou:
        ancienne = _presentations.get(cle_guet)
        _guets[cle_guet] = guet
        if ancienne and getattr(ancienne, "surface_privee", "") != getattr(dire, "surface_privee", ""):
            # Invalide aussi une présentation dont le guet est déjà terminé.
            # L'invalidation ne transporte aucun code vers l'autre surface.
            try:
                await ancienne(TEXTE_SUITE)
            except Exception as erreur:
                if isinstance(erreur, discord.HTTPException) and getattr(erreur, "status", None) in (401, 404):
                    # Référence expirée ou supprimée : elle ne peut plus être actualisée.
                    # La retirer ne recrée rien sur l'ancien auditoire.
                    _presentations.pop(cle_guet, None)
                    _reponses_privees.pop(getattr(ancienne, "cle_privee", None), None)
                else:
                    if _guets.get(cle_guet) is guet:
                        _guets.pop(cle_guet, None)
                    await dire("L’ancienne réponse privée n’a pas pu être invalidée. Réessaie lorsque Discord est disponible.")
                    return "indisponible"
        _presentations[cle_guet] = dire
    vus = set((_MONTRES.get(cle_guet) or {}).keys())
    montre = None
    fin = time.monotonic() + duree
    try:
        while True:
            if _guets.get(cle_guet) is not guet:
                return "remplace"
            if relire is not None:
                try:
                    permis = {str(a).strip().lower() for a in relire() or ()}
                except Exception as erreur:
                    journal.warning("Codes : droits indisponibles : %s", _err(erreur))
                    permis = set()
                if not adresses.issubset(permis):
                    await dire(TEXTE_PLUS_ADRESSE)
                    return "sortie"
            admissibles = _codes_demande(adresses, usage, depuis)
            bloques_confirmation = False
            valides = []
            for entree in admissibles:
                if entree.get("confirmation_adresse"):
                    verifier = _deps.get("compte_alias_uid")
                    try:
                        attendu = verifier(cle_guet.removeprefix("u|"), entree.get("alias")) if verifier else ""
                    except Exception:
                        attendu = ""
                    if not attendu or str(attendu).lower().lstrip("@") != str(entree.get("compte") or "").lower().lstrip("@"):
                        bloques_confirmation = True
                        continue
                valides.append(entree)
            admissibles = valides
            candidats = [t for t in admissibles if usage == "auto" or t.get("mid") not in vus]
            if candidats:
                montre = candidats[0]
            elif montre and not any(t.get("mid") == montre.get("mid") for t in admissibles):
                montre = None
            fini = time.monotonic() >= fin
            rendu = _texte_codes_auto(admissibles) if usage == "auto" else _texte_codes([montre]) if montre else ""
            texte = (rendu + "\n\n" + (TEXTE_REFUSE_FIN if fini else TEXTE_REFUSE)) if montre else (
                TEXTE_PANNE if lecteur_en_panne() and fini else
                TEXTE_PANNE_GUET if lecteur_en_panne() else TEXTE_RIEN if fini else TEXTE_ATTENTE)
            if not montre and any(t.get("confirmation_adresse") and t.get("alias") in adresses
                                  and _date(t) < depuis for t in _etat()["codes"]):
                texte = "Le précédent e-mail de confirmation est trop ancien pour cette demande. Demande un renvoi dans Instagram ; aucun ancien code livré."
            gardes_confirmation = [t for t in codes_recents(adresses, min(FRAIS_MIN, 10), decision="garder")
                                    if str(t.get("libelle") or "").startswith("confirmation e-mail") and _date(t) >= depuis]
            if not montre and gardes_confirmation:
                texte = "Un e-mail de confirmation a été reçu, mais sa provenance ou son alias n’est pas vérifiable. Aucun code livré ; fais vérifier le rattachement par l’équipe."
            if not montre and bloques_confirmation:
                texte = "Confirmation e-mail reçue, mais le compte exact n’est pas vérifiable pour ton UID. Fais vérifier son affectation ; aucun code livré."
            if texte != guet["texte"] or "envoye" not in guet:
                guet["texte"] = texte
                async with verrou:
                    if _guets.get(cle_guet) is not guet:
                        return "remplace"
                    await dire(texte)
                uid = cle_guet.removeprefix("u|")
                if uid.isdigit():
                    journal.info("OTP_REPONSE %s", json.dumps({"uid": uid, "adresses": len(adresses),
                        "contextes_frais": len(admissibles), "avec_code": bool(montre)}, separators=(",", ":")))
                guet["envoye"] = True
                if montre:
                    _noter_montre(cle_guet, admissibles if usage == "auto" else [montre])
            if fini:
                if not montre and not code_montre_recemment(cle_guet):
                    _signaler_code_absent(cle_guet, adresses, usage)
                return "code" if montre else "panne" if lecteur_en_panne() else "rien"
            await _attendre_nouveau(min(5.0, fin - time.monotonic()))
    finally:
        if _guets.get(cle_guet) is guet:
            _guets.pop(cle_guet, None)


ABSENT_RAPPEL_MIN = int(os.environ.get("CODES_ABSENT_RAPPEL_MIN", "20") or 20)


def texte_code_absent(uid: str, adresses: set, usage: str, panne: bool) -> str:
    """18/10 : la ligne admin quand un clipper a attendu son code pour rien (sans l'adresse en clair, sans code)."""
    formes = ", ".join(f"`{forme_adresse(a)}`" for a in sorted(adresses)[:3])
    cause = ("La boîte des codes est illisible en ce moment : c'est elle qu'il faut réparer."
             if panne else "La boîte des codes est lisible : le mail n'est pas arrivé jusqu'à elle (transfert iCloud ou Gmail "
                           "de cette adresse), ou Instagram ne l'a pas encore envoyé.")
    return (f"🚨 **Code Instagram pas reçu** : <@{uid}> a appuyé sur « 📩 Mon code » et rien n'est arrivé en "
            f"{ATTENTE_SEC // 60} minutes ({usage or 'auto'}, adresse {formes or 'inconnue'}).\n\n{cause}")


def code_montre_recemment(cle_guet: str, minutes: int = None) -> bool:
    """18/10 (Pierre et Georgial : alerte « pas reçu » à 13 h 57 alors qu'un code leur avait été montré à 13 h 52) : vrai si un code
    a été montré à ce clipper pendant la fenêtre (le guet qui finit, ou un appui précédent). Pas d'alerte dans ce cas."""
    minutes = FRAIS_MIN if minutes is None else minutes
    limite = _iso(_maintenant() - timedelta(minutes=minutes))
    return any(v >= limite for v in (_MONTRES.get(cle_guet) or {}).values())


def _signaler_code_absent(cle_guet: str, adresses: set, usage: str):
    """18/10 (Gaëtan : « je dois voir hyper vite si le clippeur n'a pas reçu son 2FA. Il faut jamais que ça plante ») : la fin
    d'un guet de 5 minutes sans code part au salon admin tout de suite, une fois par clipper toutes les ABSENT_RAPPEL_MIN minutes.
    Jamais bloquant : une tâche à part, et une erreur ici n'empêche jamais la réponse au clipper."""
    try:
        uid = str(cle_guet).removeprefix("u|")
        if not uid.isdigit() or not _une_fois(f"absent|{uid}", minutes=ABSENT_RAPPEL_MIN):
            return
        asyncio.get_running_loop().create_task(_admin(texte_code_absent(uid, adresses, usage, lecteur_en_panne())))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Codes : alerte « code pas reçu » : %s", _err(erreur))


GARDE_SEC = 120
GARDE_BLOCAGE_MIN = int(os.environ.get("CODES_BLOCAGE_MIN", "10") or 10)


def lecteur_bloque(maintenant_mono: float = None) -> int:
    """Les minutes depuis le dernier passage réussi du lecteur si elles dépassent GARDE_BLOCAGE_MIN, sinon 0."""
    ok = _SANTE.get("ok_t")
    if ok is None:
        return 0
    minutes = int(((time.monotonic() if maintenant_mono is None else maintenant_mono) - ok) // 60)
    return minutes if minutes >= GARDE_BLOCAGE_MIN else 0


async def garde_codes(client, canal_admin_async, admin_ids):
    """18/10 (« il faut jamais que ça plante ») : le gardien du lecteur. Toutes les 2 minutes : la tâche du lecteur est-elle
    morte ? elle est relancée et l'admin le sait. Le lecteur ne passe plus depuis GARDE_BLOCAGE_MIN minutes (IMAP figé) ? une
    ligne admin, une fois par blocage, et sa connexion est fermée pour qu'il reparte."""
    if not actif():
        return
    await client.wait_until_ready()
    tache = asyncio.get_running_loop().create_task(boucle_codes(client, canal_admin_async, admin_ids))
    bloque_signale = False
    while not client.is_closed():
        await asyncio.sleep(GARDE_SEC)
        try:
            if tache.done():
                cause = "arrêtée" if tache.cancelled() else _err(tache.exception()) if tache.exception() else "terminée"
                journal.warning("Codes : lecteur %s, relancé par le gardien", cause)
                await _admin(f"⚠️ **Le lecteur des codes s'était arrêté** ({cause}) : relancé tout seul.")
                tache = asyncio.get_running_loop().create_task(boucle_codes(client, canal_admin_async, admin_ids))
                continue
            minutes = lecteur_bloque()
            if minutes and not bloque_signale:
                bloque_signale = await _admin(f"⚠️ **Le lecteur des codes ne passe plus depuis {minutes} min** : connexion à la "
                                              "boîte fermée pour la relancer. Si ça revient, regarde les journaux Railway.")
                try:                                                    # jamais sur la boucle : un socket figé la bloquerait
                    await asyncio.wait_for(asyncio.to_thread(LECTEUR.fermer), timeout=15)
                except Exception:                                       # noqa: BLE001
                    pass
            elif not minutes and bloque_signale:
                bloque_signale = False
                await _admin("✅ Le lecteur des codes passe de nouveau.")
        except Exception as erreur:                                     # noqa: BLE001 — le gardien ne meurt jamais
            journal.warning("Codes : gardien : %s", _err(erreur))


# ------------------------------------------------------------------ 4b. on-demand read-through (independent of IMAP IDLE)
# Dedicated connection: never move the background reader's UID cursor, IDLE state or
# persistent mailbox state. Do not echo OTPs or full aliases to Railway logs.
_SCAN_SEMAPHORE = (None, None)
_SCAN_LAST = {}  # opaque request key -> monotonic; rate-limit manual refresh
_SCAN_EN_COURS = set()  # (boucle, demande), jusqu'à la fin réelle du thread
_SCAN_TRAVAUX = set()  # références fortes des tâches protégées après timeout


class RechercheInterrompue(TimeoutError):
    """Arrêt coopératif d'une recherche directe ; jamais un état du lecteur principal."""


def _entete_recente(tete, limite, maintenant):
    """Écarter les corps déjà hors fenêtre. Le classement complet reste obligatoire."""
    try:
        instant = email.utils.parsedate_to_datetime(tete.get("Date"))
        if instant.tzinfo is None:
            return True
    except (TypeError, ValueError, AttributeError):
        return True
    return limite <= instant <= maintenant + timedelta(minutes=2)


def _scan_recent_sync(adresses: set, minutes: int = 10, arret=None) -> list:
    """Check the latest Meta/Facebook/Instagram emails independently, even if IDLE is stale.

    Only code entries from the caller's owned aliases and within the 10-minute
    window are returned; a dedicated reader is closed after every request.
    """
    aliases = {str(a).strip().lower() for a in adresses or () if "@" in str(a)}
    if not aliases:
        return []
    reader = Lecteur()
    found = {}
    limite = _maintenant() - timedelta(minutes=min(10, max(1, minutes)))
    since = (_maintenant() - timedelta(days=1)).strftime("%d-%b-%Y")
    def controle():
        if arret is not None and arret.is_set():
            raise RechercheInterrompue()
    reader.controle_recherche = controle
    reader.filtre_recherche = lambda tete: _entete_recente(tete, limite, _maintenant())
    try:
        controle()
        reader._connecter()
        for folder in reader.dossiers():
            controle()
            try:
                reader._selectionner(folder)
                controle()
                # Filter by originating platform first; this also matches iCloud relay
                # addresses such as "no-reply_at_mail_instagram_com_...@icloud.com".
                criteres = [f'FROM "{marque}"' for marque in MOTS_EXPEDITEUR]
                filtre = criteres[-1]
                for critere in reversed(criteres[:-1]):
                    filtre = f'OR {critere} ({filtre})'
                ok, results = reader.boite.uid("SEARCH", None, f'(SINCE {since} ({filtre}))')
                if ok != "OK":
                    continue
                uids = {int(uid) for uid in ((results or [b""])[0] or b"").split() if uid.isdigit()}
                # Bound the work even with a high-volume inbox; newest first per folder.
                controle()
                for message in reader._lire(folder, sorted(uids, reverse=True)[:100], False):
                    info = classer_mail(message["msg"])
                    if (info.get("decision") != "donner" or info.get("alias") not in aliases
                            or not info.get("code") or info.get("date") is None
                            or not limite <= info["date"] <= _maintenant() + timedelta(minutes=2)):
                        continue
                    mid = str(info.get("mid") or message.get("mid") or "")
                    if not mid or mid in found:
                        continue
                    found[mid] = {
                        "n": len(found),  # Ordre UID dans le premier dossier, sans doublons All Mail/Spam.
                        "mid": mid, "alias": info["alias"], "code": info["code"],
                        "type": info["type"], "service": info.get("service", "instagram"), "decision": "donner",
                        "compte": info.get("compte") or "", "date": _iso(info["date"]),
                        "confirmation_adresse": bool(info.get("confirmation_adresse")),
                    }
            except (imaplib.IMAP4.error, MailIllisible) as erreur:
                journal.warning("Codes : recherche directe, dossier indisponible : %s", type(erreur).__name__)
                reader.selection = None
                continue
    finally:
        if arret is not None and arret.is_set():
            # Fermer le socket sans attendre un LOGOUT réseau après annulation.
            try:
                reader.boite.shutdown()
            except Exception:  # la fermeture normale reste tentée ensuite
                pass
        reader.fermer()
    return sorted(found.values(), key=_cle_tri, reverse=True)


async def _scanner_sur_demande(adresses: set, cle: str) -> None:
    """Deux threads au plus, y compris après timeout ; aucune demande en double."""
    if not adresses or not actif():
        return
    boucle = asyncio.get_running_loop()
    demande = (boucle, cle)
    now = time.monotonic()
    if demande in _SCAN_EN_COURS or now - _SCAN_LAST.get(cle, -100) < 12:
        return
    _SCAN_LAST[cle] = now
    _SCAN_EN_COURS.add(demande)
    global _SCAN_SEMAPHORE
    if _SCAN_SEMAPHORE[0] is not boucle:
        _SCAN_SEMAPHORE = (boucle, asyncio.Semaphore(2))
    semaphore = _SCAN_SEMAPHORE[1]
    import threading
    arret = threading.Event()
    travail = None
    place = False
    debut = None
    try:
        await semaphore.acquire()
        place = True
        debut = time.monotonic()
        travail = asyncio.create_task(asyncio.to_thread(_scan_recent_sync, set(adresses), SALON_CODES_MINUTES, arret))
        _SCAN_TRAVAUX.add(travail)
        def fini(tache):
            _SCAN_TRAVAUX.discard(tache)
            semaphore.release()
            _SCAN_EN_COURS.discard(demande)
            # Après un timeout, le résultat tardif n'est jamais livré ni mis en cache.
            if not tache.cancelled():
                tache.exception()
        travail.add_done_callback(fini)
        recents = await asyncio.wait_for(asyncio.shield(travail), timeout=35)
        deja = {x.get("mid") for x in _etat()["codes"]}
        nouveaux = 0
        for entry in reversed(recents):
            if entry["mid"] not in deja:
                _etat()["codes"].append(_numeroter(entry))
                deja.add(entry["mid"])
                nouveaux += 1
        if nouveaux:
            _sauver()
            await _reveiller()
        journal.info("Codes : demande directe terminée, %d nouveau(x) code(s) admissible(s)", nouveaux)
    except asyncio.CancelledError:
        arret.set()
        raise
    except Exception as erreur:
        arret.set()
        phase = "delai_global" if isinstance(erreur, TimeoutError) and travail is not None and not travail.done() else "lecteur"
        journal.warning("Codes : recherche directe indisponible : %s (phase=%s, duree=%.1fs)",
                        type(erreur).__name__, phase, time.monotonic() - debut if debut is not None else 0.0)
    finally:
        if travail is None:
            if place:
                semaphore.release()
            _SCAN_EN_COURS.discard(demande)


def _demander_scan(adresses: set, cle: str) -> None:
    """Start a bounded scan without delaying the first Discord response."""
    # Also check for a newly re-sent code when a previous code is still cached.
    # Keep the first reply instant; the reader updates it asynchronously.
    if adresses:
        asyncio.create_task(_scanner_sur_demande(set(adresses), cle))


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


async def _rafraichir_membre(membre) -> set:
    """On-demand fallback : Sheets uniquement en cas de liaison UID manquante.

    Pour le bouton, reste dans la réponse éphémère; ne jamais publier d'OTP.
    """
    callback = _deps.get("rafraichir_adresses_membre")
    if not callable(callback):
        return set()
    try:
        mails = await asyncio.wait_for(callback(getattr(membre, "id", "")), timeout=22)
        return {str(a).strip().lower() for a in mails or () if "@" in str(a)}
    except Exception as erreur:
        journal.warning("Codes : rafraîchissement UID impossible : %s", _err(erreur))
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
                      "Vérifie l'affectation de ses comptes et adresses à son UID dans le registre des comptes, "
                      "y compris les doublons. Corrige uniquement les correspondances prouvées.")
    if not ok:
        _etat()["sante"].pop(cle, None)                                # pas prévenu : on le redira au prochain appui
    _sauver()
    return ok


async def _sans_adresse(membre, dire) -> None:
    if _est_staff(membre):
        await dire("Ici, chacun ses codes : aucune adresse de compte n'est validée pour ton UID.\n\n"
                   "Pour aider un clipper, vérifie l'affectation de ses propres comptes dans le registre.")
        return
    if await _alerter_sans_adresse(membre):
        await dire("L'affectation de tes comptes doit être vérifiée avant de recevoir leurs codes.\n\n"
                   "Le blocage est signalé à l'équipe. Un renvoi de code ne corrige pas ce rattachement.")
    else:
        await dire("L'affectation de tes comptes doit être vérifiée avant de recevoir leurs codes.\n\n"
                   "Signale ce blocage à ton manager, sans code ni mot de passe. Un renvoi de code ne le corrige pas.")


def vue_choix_code(uid, adresses, usage=""):
    """Un clic pour l'usage ; sélection du compte seulement si plusieurs comptes sont liés."""
    if not usage or usage == "auto":
        return vue_mon_code()
    vue = discord.ui.View(timeout=300)
    comptes = discord.ui.Select(placeholder="Choisis le compte", options=[
        discord.SelectOption(label=alias[:100], value=alias) for alias in sorted(adresses)[:25]])

    async def compte_choisi(interaction):
        if str(interaction.user.id) != str(uid):
            await interaction.response.send_message("Ce choix appartient à une autre personne.", ephemeral=True)
            return
        vue.stop()
        await servir_interaction(interaction, usage, comptes.values[0])

    comptes.callback = compte_choisi
    vue.add_item(comptes)
    return vue


async def servir_interaction(interaction, usage="", adresse="") -> str:
    """Menu et livraison uniquement éphémères ; droits relus à chaque sélection et pendant l'attente."""
    if not actif():
        await interaction.response.send_message("Relais des codes éteint pour l'instant. Dis-le à ton manager.", ephemeral=True)
        return "eteint"
    # Si l'accusé privé échoue, ne jamais éditer un message potentiellement public.
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
    except (discord.HTTPException, discord.InteractionResponded):
        return "indisponible"

    secours = {"message": None}

    async def nouveau(texte):
        try:
            if secours["message"] is not None:
                await secours["message"].edit(content=texte, view=None)
            else:
                await interaction.edit_original_response(content=texte, view=None)
        except discord.HTTPException as erreur:
            if getattr(erreur, "status", None) != 404:
                raise
            # La réponse provisoire peut avoir été supprimée après réutilisation.
            # Discord confirme son absence : recréer uniquement en éphémère,
            # puis conserver le message retourné pour les éditions suivantes.
            secours["message"] = await interaction.followup.send(texte, ephemeral=True, wait=True)

    membre = interaction.user
    dire = reponse_privee_unique((str(membre.id), "ephemere"), nouveau,
                                 getattr(interaction, "delete_original_response", None))
    adresses = _adresses_membre(membre)
    if not adresses:
        adresses = await _rafraichir_membre(membre)
    if not adresses:
        await _sans_adresse(membre, dire)
        return "sans_adresse"
    usage = usage or "auto"
    if usage == "auto" and not adresse:
        cle = f"u|{membre.id}"
        _demander_scan(adresses, cle)
        return await _servir(adresses, dire, cle, usage="auto", relire=lambda: _adresses_membre(membre))
    if usage in USAGES_EMAIL and not adresse and len(adresses) == 1:
        adresse = next(iter(adresses))
    if not usage or not adresse:
        if len(adresses) > 25:
            await dire("Plus de 25 adresses : utilise `!code connexion adresse` ou `!code creation adresse`.")
            return "choix"
        await interaction.edit_original_response(content=TEXTE_CHOIX, view=vue_choix_code(membre.id, adresses, usage))
        return "choix"
    if usage not in (*USAGES_EMAIL, "auto") or adresse not in adresses:
        await dire("🔒 Ce compte n’est plus rattaché à toi ou ce type de code n’est pas disponible.")
        return "refus"
    cibles = {adresse}
    cle = f"u|{membre.id}"
    _demander_scan(cibles, cle)
    return await _servir(cibles, dire, cle, usage=usage, relire=lambda: _adresses_membre(membre))


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


class BoutonUsageCode(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"codes:usage:(?P<usage>creation|connexion|verification)"):
    """Bouton persistant sans compte ni code : l'UID de celui qui clique décide des droits."""
    def __init__(self, usage="connexion"):
        self.usage = usage
        super().__init__(discord.ui.Button(label=USAGES_EMAIL[usage], style=discord.ButtonStyle.primary,
                                           custom_id=f"codes:usage:{usage}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["usage"])

    async def callback(self, interaction):
        await servir_interaction(interaction, usage=self.usage)


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
    """`!code [usage] [alias]` : réponse privée liée à l'UID dans tous les salons.
    `!alias` reste réservé aux managers ; récupération et recours ne livrent aucun code.
    Renvoie True si traité. `alerter` est conservé pour compatibilité."""
    texte = message.content.strip()
    mots = texte.split()
    if not mots:
        return False
    premier = mots[0].lower()
    if premier in COMMANDES_AIDE:
        await message.reply(aide_instagram(mots[1] if len(mots) > 1 else ""), mention_author=False)
        return True
    if not texte.lower().startswith(("!alias", "!code") + COMMANDES_RECUP):
        return False
    if premier.startswith("!code"):
        premier = "!code"
    if premier in COMMANDES_APPEL:
        await message.reply(aide_instagram("suspension"), mention_author=False)
        return True
    if premier in COMMANDES_RECUP:
        await message.reply(TEXTE_RECUP_REFUSE)
        return True
    canal_id = str(message.channel.id) if message.guild is not None else ""
    manager = message.guild is not None and _est_manager(message.author, admin_ids)
    if premier == "!code":
        if len(mots) == 2 and _cle(mots[1]) in ("2fa", "totp", "authentificateur", "authenticator"):
            await message.reply(aide_instagram("authentificateur"), mention_author=False)
            return True
        usage = next((m.lower() for m in mots[1:] if m.lower() in USAGES_EMAIL), "")
        adresse = next((m.lower() for m in mots[1:] if "@" in m), "")
        if any(m.lower() not in USAGES_EMAIL and "@" not in m for m in mots[1:]):
            await message.reply(texte_salon_codes() + "\n\nBesoin d'aide ? `!aide-ig`.")
            return True
        admin = str(getattr(message.author, "id", "")) in admin_ids
        return await _commande_salon_commun(message, manager, admin, adresses_de_membre, adresse, usage)
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


async def _commande_salon_commun(message, manager: bool, admin: bool, adresses_de_membre=None,
                                  adresse: str = "", usage: str = "") -> bool:
    """Même règle pour tous les salons : compte lié à l'UID, MP seulement, aucun repli sur la boîte entière."""
    if not actif():
        await message.reply("Relais des codes éteint pour l'instant. Dis-le à ton manager.")
        return True
    source = adresses_de_membre or (lambda: _adresses_membre(message.author))
    try:
        adresses = {str(a).strip().lower() for a in source() or ()}
    except Exception:
        adresses = set()
    if not adresses:
        adresses = await _rafraichir_membre(message.author)
    if not adresses:
        await _sans_adresse(message.author, message.reply)
        return True
    if adresse and adresse not in adresses:
        await message.reply("🔒 Cette adresse n’est pas rattachée à ton compte Discord.")
        return True
    usage = usage or "auto"
    if not adresse and len(adresses) == 1:
        adresse = next(iter(adresses))
    try:
        if usage != "auto" and not adresse:
            if len(adresses) > 25:
                await message.author.send("Plus de 25 adresses : utilise `!code connexion adresse` ou `!code creation adresse`.")
                return True
            await message.author.send(TEXTE_CHOIX, view=vue_choix_code(message.author.id, adresses, usage))
            await message.reply(TEXTE_MP, view=vue_mon_code(), delete_after=120)
            return True
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        await message.reply(TEXTE_MP_FERMES, view=vue_mon_code())
        return True
    # 18/10 (Gaëtan : « je veux juste que ce putain de code 2FA marche et soit renvoyé en clair dans le salon code-instagram ») :
    # `!code` répond DANS le salon où il a été tapé, en réponse au clipper, code en clair ; le message s'efface tout seul au bout de
    # CODE_SALON_EFFACE_MIN minutes (un code ne sert qu'une fois et expire). Avant : « je t'envoie ton code en message privé ».
    courant = {"msg": None}

    async def nouveau(t):
        if courant["msg"] is None:
            courant["msg"] = await message.reply(t, mention_author=True, delete_after=CODE_SALON_EFFACE_MIN * 60)
        else:
            await courant["msg"].edit(content=t)

    dire = reponse_privee_unique((str(message.author.id), "mp"), nouveau)

    cle = f"u|{getattr(message.author, 'id', '')}"
    cibles = {adresse} if adresse else adresses
    _demander_scan(cibles, cle)
    try:
        await _servir(cibles, dire, cle, usage=usage, relire=source)
    except discord.Forbidden:
        await message.reply(TEXTE_MP_FERMES, view=vue_mon_code())
    except discord.HTTPException:
        await message.reply("La réponse privée n’a pas pu être actualisée. Réessaie avec 📩 Mon code.", view=vue_mon_code())
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


def promouvoir_creation(info: dict) -> dict:
    """18/10 (Gaëtan : « Pierre ne reçoit pas le code » ; « il faut jamais que ça plante ») : à l'inscription avec un e-mail,
    Instagram envoie « Votre code Instagram est le … » en parlant d'AJOUTER cette adresse au compte. La liste noire le gardait
    (« e-mail ajouté ou changé »). Il devient un code de création, donné au seul clipper de cette adresse, quand :
      - le mail vient d'Instagram, porte un code, et l'adresse e-mail est la seule famille sensible touchée (ajout_adresse) ;
      - l'adresse a UN propriétaire, et le compte qui lui est attaché n'est PAS encore créé (dep « compte_a_creer »).
    Un compte déjà créé garde la règle : un changement d'adresse sur un compte vivant n'est jamais donné.

    18/10, 13 h 52 (Gaëtan : « Donne tous les codes SAUF changer les informations, mots de passe et mail… On est parfaitement
    protégé si on donne les codes login et sign up ») : tout code gardé d'un mail Meta ou Instagram (code_brut) est donné au
    clipper de l'adresse s'il ne parle d'aucun changement (changement=False : ni mot de passe, ni e-mail, ni réglages, ni
    récupération). Le type : vérification (« Authenticate », identité), sinon connexion."""
    if info.get("decision") != "garder" or not info.get("alias"):
        return info
    if info.get("code_brut") and not info.get("changement"):
        sujet = plat(str(info.get("sujet") or ""))
        typ = "verification" if re.search(r"authenticat|identit|confirmation d.adresse|verif", sujet) else "connexion"
        journal.info("Codes : code Meta sans changement (%s) → donné (%s)", info.get("libelle"), typ)
        return dict(info, decision="donner", code=info["code_brut"], type=typ, libelle=QUOI.get(typ, "connexion"))
    if not info.get("ajout_adresse") or not info.get("code"):
        return info
    verifier = _deps.get("compte_a_creer")
    try:
        a_creer = bool(verifier(info["alias"])) if verifier else False
    except Exception as erreur:                                         # noqa: BLE001 — dans le doute, la règle garde
        journal.warning("Codes : compte à créer illisible : %s", _err(erreur))
        a_creer = False
    if not a_creer:
        return info
    journal.info("Codes : ajout d'adresse sur un compte à créer → code de création donné")
    return dict(info, decision="donner", type="creation", libelle="création de compte (confirmation de l'adresse)")


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
    info = promouvoir_creation(info)
    recent = not lu.get("amorce") or _maintenant() - info["date"] < timedelta(minutes=60)
    journal.info("Codes : %s (%s) sur %s → %s", info["libelle"] or "mail Meta", dossier, _masquer(alias), info["decision"])
    if info.get("preuve") == "contraire" and info["decision"] != "rien" and _une_fois("preuve|observer", minutes=24 * 60):
        # 18/10 (Gaëtan : « simplifie ») : rien n'est bloqué en mode « observer » : journal seulement, plus de ligne admin
        journal.info("Codes : relais iCloud sans signature Meta attestée (%s), mode observer", forme_adresse(info.get("expediteur")))
    if info["decision"] == "donner":
        if mid not in connus:
            e["codes"].append(_numeroter({"mid": mid, "alias": alias, "code": info["code"], "type": info["type"], "service": info.get("service", "instagram"),
                                          "decision": "donner", "compte": info["compte"], "date": _iso(info["date"]),
                                          "confirmation_adresse": bool(info.get("confirmation_adresse"))}))
            connus.add(mid)
            bilan["donnes"] += 1
        proprio = _proprietaire(alias)
        if not proprio.get("canal_id"):
            if alias and recent and _une_fois(f"orphelin|{alias}", minutes=60):
                bilan["orphelins"] += 1
                await _admin(f"🔐 Code de {QUOI.get(info['type'], 'connexion')} reçu sur `{alias}`, une adresse rattachée "
                             "à personne : je ne le donne à personne.\n\n"
                             f"Si c'est l'adresse d'un clipper : `!alias ajouter {alias}` dans son salon perso.")
        # Les réponses privées déjà ouvertes sont réveillées par _traiter_lus.
        # Ne publier aucun code ou notification dans un autre salon/DM.
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
            appel = "\n\n" + TEXTE_APPEL_GARDE if info["type"] == "appel" else ""
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
    echecs = 0
    for lu in resultat.get("mails") or []:
        try:
            await _traiter_un(client, lu, e, connus, commun, bilan)
        except Exception as erreur:                                     # noqa: BLE001 — jamais tout le lot pour un mail
            echecs += 1
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
    if echecs:
        raise RuntimeError("Traitement du lot incomplet : curseurs non validés")
    return bilan


def _genre_erreur(erreur) -> str:
    t = str(erreur).lower()  # Classification en mémoire seulement ; jamais journalisée.
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


# 18/10 (action 26 du plan : « zéro code pendant deux jours en octobre, personne ne l'a vu ») : la boîte peut être lisible et ne
# plus rien recevoir (transfert coupé, adresse changée). Aucun e-mail Meta arrivé depuis CODES_SILENCE_MIN minutes, de jour à
# Paris (CODES_SILENCE_HEURES, défaut 9 h → 23 h : la nuit, le silence est normal) : une ligne au salon admin, une fois par
# silence ; une seconde quand les codes reviennent. CODES_SILENCE_MIN=0 coupe la surveillance. 18/10 : 60 min par défaut (Gaëtan : « je dois voir hyper vite si le clippeur n'a pas reçu son 2FA »).
SILENCE_MIN = int(os.environ.get("CODES_SILENCE_MIN", "60") or 0)   # 18/10 (Gaëtan : « fais à 1 h ») 
SILENCE_HEURES = tuple(int(x) for x in (os.environ.get("CODES_SILENCE_HEURES", "9-23") or "9-23").split("-")[:2])


def silence_a_signaler(dernier_iso: str, maintenant: datetime, heure_paris: int, seuil_min: int = None,
                       heures: tuple = None) -> int:
    """Les minutes de silence à signaler (0 = rien à dire) : seuil dépassé et heure de Paris dans la plage de jour."""
    seuil = SILENCE_MIN if seuil_min is None else seuil_min
    debut, fin = heures or SILENCE_HEURES
    if not seuil or not dernier_iso or not (debut <= heure_paris < fin):
        return 0
    try:
        dernier = datetime.fromisoformat(str(dernier_iso))
    except ValueError:
        return 0
    if dernier.tzinfo is None:
        dernier = dernier.replace(tzinfo=timezone.utc)
    minutes = int((maintenant - dernier).total_seconds() // 60)
    return minutes if minutes >= seuil else 0


async def surveiller_silence():
    """Un passage de la surveillance (appelé à chaque tour du lecteur)."""
    e = _etat()
    maintenant = _maintenant()
    if not e.get("dernier_code"):                                       # premier démarrage : le silence part de maintenant
        e["dernier_code"] = maintenant.isoformat(timespec="seconds")  # écrit avec le prochain état sauvé
        return
    try:
        from zoneinfo import ZoneInfo
        heure = maintenant.astimezone(ZoneInfo("Europe/Paris")).hour
    except Exception:                                                   # noqa: BLE001 — base de fuseaux absente
        heure = (maintenant + timedelta(hours=2)).hour
    minutes = silence_a_signaler(e["dernier_code"], maintenant, heure)
    if minutes and not e.get("silence_signale"):
        h, m = divmod(minutes, 60)
        if await _admin(f"⚠️ **Aucun code Instagram reçu depuis {h} h {m:02d}** alors que la boîte des codes est lisible.\n\n"
                        "Vérifie le transfert des e-mails des comptes vers la boîte des codes (adresses iCloud, règle Gmail). "
                        "D'ici là, un clipper qui crée un compte ne reçoit pas son code."):
            e["silence_signale"] = e["dernier_code"]
            _sauver()
    elif e.get("silence_signale") and e.get("silence_signale") != e.get("dernier_code"):
        e.pop("silence_signale", None)
        _sauver()
        await _admin("✅ Les codes Instagram arrivent de nouveau dans la boîte des codes.")


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
        # Cycle déplace son curseur en mémoire avant le traitement ; seul le succès
        # du lot valide ce point de reprise et ses Message-ID dédupliqués.
        avant_uid = {k: dict(v) for k, v in LECTEUR.etat.items()}
        avant_vus = LECTEUR.vus.copy()
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
        try:
            await _traiter_lus(client, resultat)
        except Exception as erreur:                                     # noqa: BLE001
            LECTEUR.etat, LECTEUR.vus = avant_uid, avant_vus
            _SANTE["traitement_echecs"] = _SANTE.get("traitement_echecs", 0) + 1
            journal.warning("Codes : traitement des mails : %s (lot à reprendre)", _err(erreur))
            attendre = 0.0
            await asyncio.sleep(min(5, SONDAGE_SEC))
            continue
        _SANTE["traitement_echecs"] = 0
        await _sante_ok()
        try:
            await surveiller_silence()
        except Exception as erreur:                                     # noqa: BLE001 — jamais tuer le lecteur
            journal.warning("Codes : surveillance du silence : %s", _err(erreur))
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


def audit_salon_codes(salon):
    """Lecture seule des droits effectifs du cache Discord et des compteurs UID.

    Aucun historique, e-mail, OTP, secret ou modification de permission. La complétude
    du cache de membres est explicitement indiquée, jamais supposée.
    """
    guild = salon.guild
    membres = list(guild.members)
    visibles = [m for m in membres if salon.permissions_for(m).view_channel]
    role_ids = {r.id for r in guild.roles}
    roles = []
    for role in guild.roles:
        permissions = salon.permissions_for(role)
        if permissions.view_channel or role.id == guild.default_role.id or role in salon.overwrites:
            roles.append({"id": str(role.id), "nom": str(role.name).replace("\n", " ")[:80],
                          "voir": bool(permissions.view_channel), "admin": bool(permissions.administrator)})
    exceptions = [{"id": str(cible.id), "type": "role" if cible.id in role_ids else "membre",
                   "voir": droits.view_channel, "ecrire": droits.send_messages}
                  for cible, droits in salon.overwrites.items()]
    permissions_bot = salon.permissions_for(guild.me)
    rapport = {"salon_id": str(salon.id), "membres_cache": len(membres), "membres_serveur": guild.member_count,
               "cache_complet": bool(guild.chunked), "visibles": len(visibles),
               "humains_visibles": sum(not m.bot for m in visibles), "roles": roles, "exceptions": exceptions,
               "bot_voit": bool(permissions_bot.view_channel), "bot_ecrit": bool(permissions_bot.send_messages)}
    journal.info("OTP_AUDIT_SALON %s", json.dumps(rapport, ensure_ascii=False, separators=(",", ":")))
    callback = _deps.get("audit_liaisons")
    for ligne in callback(guild) if callback else []:
        uid = str(ligne.get("uid") or "")
        if not uid.isdigit():
            continue
        # Seule cette projection peut sortir dans les journaux, jamais la fiche source.
        resume = {"uid": uid, "comptes_declares": int(ligne.get("comptes_declares", 0)),
                  "adresses_autorisees": int(ligne.get("adresses_autorisees", 0)),
                  "salon_perso": bool(ligne.get("salon_perso")),
                  "voit_codes": bool(ligne.get("voit_codes")),
                  "dans_serveur": bool(ligne.get("dans_serveur"))}
        diagnostic = ligne.get("diagnostic") or {}
        resume["diagnostic"] = {k: int(diagnostic.get(k, 0)) for k in
            ("compte_autorise", "acces_absent", "adresse_absente", "livraison_autre_uid", "alias_ambigu", "compte_ambigu")}
        journal.info("OTP_AUDIT_LIAISON %s", json.dumps(resume, separators=(",", ":")))
    return rapport


async def assurer_salon_codes(client):
    """Poser le panneau privé dans le salon existant, sans modifier ses permissions ni son historique."""
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
        if salon is None:
            journal.warning("Salon des codes absent : création et permissions à valider par l’administrateur")
            return
        if info.get("version") != VERSION_EXPLICATION or str(info.get("id")) != str(salon.id):
            try:
                m = await salon.send(explication_salon(), view=vue_mon_code())
                try:
                    await m.pin()
                except (discord.Forbidden, discord.HTTPException, AttributeError):
                    pass
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : mode d'emploi non posté (%s)", _err(erreur))
                return
        registre = _lire()
        registre["_salon_codes"] = {"id": str(salon.id), "guild": str(guild.id), "explique": True,
                                    "version": VERSION_EXPLICATION, "date": _maintenant().isoformat(timespec="seconds")}
        _ecrire(registre)
        journal.info("Salon des codes : bouton privé prêt ; permissions existantes conservées")
        try:
            audit_salon_codes(salon)
        except Exception as erreur:
            journal.warning("OTP_AUDIT_INDISPONIBLE %s", _err(erreur))
        return
