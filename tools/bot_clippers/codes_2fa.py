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
FICHIER_ALIAS = None            # injecté par bot_discord.py (volume persistant)
SALON_CODES_NOM = os.environ.get("CANAL_CODES_NOM", "🔐-code-instagram").strip() or "🔐-code-instagram"
# 29/09 (Gaëtan : « restreins le salon au rôle Clippeur ») : le salon commun est réservé à l'équipe.
ROLES_SALON_CODES = tuple(r.strip() for r in os.environ.get("CODES_SALON_ROLES", "Clippeur,Rookie,Confirmé,Elite").split(",") if r.strip())
# Sous-chaînes cherchées côté serveur au PREMIER passage seulement (IMAP FROM) : un pré-filtre, l'adresse décide ensuite.
MOTS_EXPEDITEUR = ("instagram", "facebook", "meta.com", "meta_com")
COMMANDES_RECUP = ("!recup", "!récup", "!recuperation", "!récupération", "!appel", "!unban", "!deban")
COMMANDES_APPEL = ("!appel", "!unban", "!deban")
ID_BOUTON = "codes:mon-code"
VERSION_EXPLICATION = "6a" if CODES_APPEL else "6"

# ------------------------------------------------------------------ textes
TEXTE_CODE_BRUT = f"Un code Instagram ? Va dans #{SALON_CODES_NOM} et appuie sur « 📩 Mon code »."
SUJET_SALON = "📩 Mon code : ton code Instagram de connexion ou de création de compte, visible par toi seul."
TEXTE_ATTENTE = ("⏳ Pas encore reçu.\n\nJe guette 5 minutes : ton code s'affiche ici tout seul dès que l'e-mail arrive. "
                 "Pas besoin de rappuyer.")
TEXTE_RIEN = ("😴 Toujours pas de code.\n\nVérifie que l'e-mail tapé dans Instagram est exactement celui de ton compte. "
              "Appuie sur « Renvoyer le code », attends 30 secondes, puis rappuie sur 📩 Mon code.")
TEXTE_PANNE = "⚠️ Je n'arrive pas à lire la boîte mail en ce moment.\n\nRéessaie dans 2 minutes. L'équipe est prévenue."
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
    """Le mode d'emploi épinglé (v6, 10/10) : le bouton, les deux usages, rien d'autre."""
    usages = "1️⃣ Créer un compte\n2️⃣ Te connecter" + ("\n3️⃣ Faire appel après un ban" if CODES_APPEL else "")
    return ("🔐 **Ton code Instagram, c'est ici.**\n\n"
            "Appuie sur **📩 Mon code** : ton code s'affiche pour toi seul. Personne d'autre ne le voit.\n\n"
            f"Il sert à {'3' if CODES_APPEL else '2'} choses, rien d'autre :\n\n{usages}\n\n"
            "➡️ Tu fais ta demande sur Instagram. Instagram t'envoie un e-mail. Tu appuies sur 📩 Mon code : le code "
            "arrive tout seul dès que l'e-mail est là. ✅\n\n"
            "😴 Pas de code après 5 minutes ? Vérifie l'e-mail tapé dans Instagram, appuie sur « Renvoyer le code », "
            "puis rappuie sur 📩 Mon code.\n\n"
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


def _sans_code(texte: str) -> str:
    """Un sujet recopié au salon admin, codes masqués (« 956472 is your… » → « •••••• is your… »)."""
    return re.sub(r"(?:FB-?)?\d{4,8}", "••••••", str(texte or ""))[:90]


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
def plat(t: str) -> str:
    """Minuscules, sans accents, apostrophes droites : « Réinitialisé » → « reinitialise »."""
    t = unicodedata.normalize("NFD", (t or "").lower().replace("’", "'").replace("ß", "ss"))
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
# La partie avant « _at_ » n'a pas de « _ » : « a_at_mail_instagram_com_at_outlook_com_zz9 » (un faux relayé) est refusé.
RE_ICLOUD_INSTAGRAM = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_)?instagram_com_[a-z0-9]+$")
RE_ICLOUD_META_CODES = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_)?meta_com_[a-z0-9]+$")
RE_ICLOUD_META = re.compile(r"^[a-z0-9.+-]+_at_(?:mail_|accountscenter_)?(?:instagram|facebookmail|facebook|meta)_com_[a-z0-9]+$")


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


def html_en_texte(source: str) -> str:
    """HTML → texte : commentaires, <head>, <style>, <script> retirés (un CSS de 2,5 Ko en tête cachait « reset your
    password »), fins de blocs en retours à la ligne, entités décodées."""
    h = re.sub(r"(?is)<!--.*?-->", " ", source or "")
    h = re.sub(r"(?is)<(head|style|script|title|noscript)\b.*?</\1\s*>", " ", h)
    h = re.sub(r"(?is)<(br|/p|/div|/tr|/td|/li|/h[1-6]|/table)\b[^>]*>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return html.unescape(h)


def texte_du_mail(msg) -> str:
    """Le texte du mail : la partie text/plain si elle existe, sinon le HTML converti. Retours à la ligne gardés (ils
    bornent les phrases)."""
    plain, pages = [], []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        genre = part.get_content_type()
        if genre not in ("text/plain", "text/html") or part.get_content_disposition() == "attachment":
            continue
        try:
            brut = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:                                               # noqa: BLE001
            continue
        (plain if genre == "text/plain" else pages).append(brut)
    texte = "\n".join(plain) if any(p.strip() for p in plain) else "\n".join(html_en_texte(p) for p in pages)
    texte = re.sub(r"[ \t\r\f\v ]+", " ", texte)
    return re.sub(r" *\n[\n ]*", "\n", texte).strip()


# Le pied de page Meta (« from Meta. © Instagram. Meta Platforms, Inc., Menlo Park, CA 94025 ») et les phrases de service.
PIED = re.compile(r"(from meta|de meta|da meta|von meta|di meta)?\W*©.*$|meta platforms.*$", re.I | re.S)
SERVICE = re.compile(r"(this (message|email) was sent to|ce message a ete envoye a|este (mensaje|correo) se envio a|esta mensagem "
                     r"foi enviada para|questo messaggio e stato inviato a|diese (nachricht|e-mail) wurde an|not your account|ce "
                     r"n'est pas votre compte|remove your email from this account|unsubscribe|se desabonner)[^.!?\n]*[.!?]?")
# Les phrases d'avertissement (« si ce n'était pas vous, changez votre mot de passe ») ne disent jamais à quoi sert le code.
AVERTISSEMENT = re.compile(
    r"(if (this|it) (wasn'?t|was not) you|if you didn'?t|if not,|si ce n'etait pas vous|si vous n'etes pas a l'origine|"
    r"si vous n'etes pas|sinon,|si no fuiste tu|si no has sido tu|si no lo hiciste|se nao foi voce|se voce nao|"
    r"se non sei stat[oa] tu|se non hai|wenn du das nicht warst|falls du das nicht warst)[^.!?\n]*[.!?]?")
# Le pseudo de la salutation (« Hi chloe.clips, ») est retiré de la lecture : un pseudo « x.phone » ne bloque rien.
SALUTATION = re.compile(r"\b(hi|hello|hey|bonjour|salut|hola|ola|ciao|hallo)\b\W{0,3}([a-z0-9][a-z0-9._]{1,40})\s*[,:!.]")
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
    ("numéro de téléphone", r"\b(phone|telephone|telefono|telefone|handynummer|sms)\b|\bnumero\b|phone number|mobile number"),
    ("double authentification", r"two[- ]?factor|\b2fa\b|deux facteurs|double authentification|dos factores|dois fatores|"
                                r"due fattori|zwei[- ]?faktor|authenticat\w*|authentifi\w*|autenticac\w*|autenticaz\w*|totp"),
    ("Espace Comptes", r"accounts? cent(er|re)|espace comptes|centre de comptes|centro de cuentas|central de contas|"
                       r"centro gestione|kontenubersicht|accountscenter"),
    ("suppression ou désactivation du compte", r"\bdelet\w*|supprim\w*|deactivat\w*|desactiv\w*|\beliminar\w*|\bexclu\w*|"
                                               r"\belimina\w*|losch\w*|deaktiv\w*|disabl\w*|disattiv\w*"),
    ("pseudo", r"\busername\b|nom d'utilisateur|\bpseudo\w*|nombre de usuario|nome de usuario|nome utente|benutzername"),
    ("codes de secours", r"backup|sauvegarde|respaldo|secours|codici di riserva"),
    ("changement d'une information du compte", r"\b(chang\w*|modif\w*|updat\w*|mettre a jour|mis a jour|cambi\w*|alter[ao]\w*|"
                                               r"geandert|anderung\w*|andern|actualiz\w*|atualiz\w*|aggiorn\w*)\b"),
)
NOIRE_RE = tuple((libelle, re.compile(motif)) for libelle, motif in NOIRE)
APPEL_RE = re.compile(r"\b(review\w*|appeal\w*|appel|appeler|contest\w*|examen|examin\w*|revision|revisar|revisao|revisione|"
                      r"einspruch|uberprufung)\b")
CREATION_RE = re.compile(r"|".join((
    r"\bsign(ed|ing)? ?up\b", r"create (an|a new) account|creating (an|a new) account|finish setting up your account",
    r"creer un compte|cree un compte|creer votre compte|\binscri\w*", r"\bregistr\w*", r"cadastr\w*|criar (uma )?conta",
    r"crear (una )?cuenta", r"\biscriv\w*|\biscriz\w*|creare un account", r"konto (zu )?erstell\w*")))
CONNEXION_RE = re.compile(r"|".join((
    r"\blog ?in\b|\blogging in\b|\bsign(ing)? in\b|unusual login", r"se connecter|tentative de connexion|connexion inhabituelle",
    r"iniciar sesion|inicio de sesion", r"fazer login|entrar na (sua )?conta", r"\baccedere\b|\baccesso\b", r"\banmeld\w*",
    r"confirm your identity|confirmer votre identite|confirma tu identidad|confirme sua identidade|conferma la tua identita|"
    r"bestatige deine identitat", r"verify your account|verifiez votre compte|verifica tu cuenta|verifique sua conta")))
CODE_SUJET = re.compile(r"(?<![\w.@-])((?:FB-?)?\d{5,8})(?![\w@])")
CODE_CORPS = re.compile(r"(?:code|codigo|codice|kod|confirmation)\D{0,60}?(?<![\w.@-])((?:FB-?)?\d{5,8})(?![\w@])", re.I)
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
     r"(phone|telephone|numero|telefono|telefone|handynummer)\W+(\w+\W+){0,5}(chang|modif|ajout|added|remov|supprim|cambi|"
     r"alterad|aggiun|geandert)"),
    ("compte relié à un Espace Comptes", r"accounts? cent(er|re)|espace comptes|centro de cuentas|central de contas|centro gestione"),
    ("pseudo changé", r"(username|nom d'utilisateur|nombre de usuario|nome de usuario|nome utente|benutzername|pseudo)\W+"
                      r"(\w+\W+){0,5}(chang|modif|cambi|alterad|geandert)"),
    ("suppression ou désactivation demandée", r"\bdelet\w*|supprim\w*|deactivat\w*|desactiv\w*|\beliminar\w*|\bexclu\w*|"
                                              r"losch\w*|deaktiv\w*|disattiv\w*"),
)
ALERTES_RE = tuple((libelle, re.compile(motif)) for libelle, motif in ALERTES)
MOTIF_COMPTE = re.compile(r"\b(?:Hi|Hello|Hey|Bonjour|Salut|Hola|Olá|Ola|Ciao|Hallo)\b\W{0,3}([A-Za-z0-9][A-Za-z0-9._]{1,40})\s*[,:!.]")


def _libelle_2fa(texte: str) -> str:
    if re.search(r"\boff\b|desactiv|disabl|deaktiv|disattiv|\bcoupe", texte):
        return "double authentification coupée"
    if re.search(r"\bon\b|activ|enabl|aktiviert|attiv", texte):
        return "double authentification activée"
    return "double authentification activée ou coupée"


def classer(from_header, sujet: str, corps: str) -> dict:
    """La décision sur un mail : {"decision": "donner"|"garder"|"alerte"|"rien", "type": "creation"|"connexion"|"appel"|"",
    "code": str|None, "libelle": str, "compte": str}. « donner » = le clipper peut l'avoir ; « garder » = un code qui ne
    sort jamais (une ligne admin sans le code) ; « alerte » = un changement déjà fait ; « rien » = le reste."""
    sujet = str(sujet or "")
    corps = SERVICE.sub(" ", PIED.sub(" ", str(corps or "")))
    m_compte = MOTIF_COMPTE.search(corps[:400])
    compte = m_compte.group(1).rstrip(".") if m_compte else ""
    fenetre = corps[:600]
    texte = plat(f"{sujet} .\n{fenetre}")
    texte = ADRESSES.sub(" _x_ ", texte)
    texte = SALUTATION.sub(lambda m: f"{m.group(1)} _x_,", texte)
    texte = AVERTISSEMENT.sub(" ", texte)
    texte = CONFIRMER_EMAIL.sub(" _confirmation_ ", texte)
    m = CODE_SUJET.search(sujet) or CODE_CORPS.search(plat(ADRESSES.sub(" ", fenetre)))
    code = m.group(1) if m else None
    sortie = {"decision": "rien", "type": "", "code": code, "libelle": "", "compte": compte}
    if code is None:
        if not expediteur_meta(from_header):
            return dict(sortie, libelle="expéditeur hors Meta")
        for libelle, motif in ALERTES_RE:
            if motif.search(texte):
                if libelle == "double authentification":
                    libelle = _libelle_2fa(texte)
                return dict(sortie, decision="alerte", libelle=libelle)
        return sortie
    if not expediteur_meta(from_header):
        return dict(sortie, decision="rien", code=None, libelle="expéditeur hors Meta")   # jamais lu comme un code Meta
    if not expediteur_instagram(from_header) and not (expediteur_meta_codes(from_header) and "instagram" in texte):
        quoi = "Facebook" if "facebook" in adresse_expediteur(from_header) else "Meta ou Espace Comptes"
        return dict(sortie, decision="garder", libelle=f"code {quoi} (pas un mail Instagram)")
    for libelle, motif in NOIRE_RE:
        if motif.search(texte):
            return dict(sortie, decision="garder", libelle=libelle)
    if APPEL_RE.search(texte):
        if CODES_APPEL:
            return dict(sortie, decision="donner", type="appel", libelle="appel après un ban")
        return dict(sortie, decision="garder", type="appel", libelle="appel après un ban (CODES_APPEL=0)")
    if CREATION_RE.search(texte):
        return dict(sortie, decision="donner", type="creation", libelle="création de compte")
    if CONNEXION_RE.search(texte):
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
    """classer() sur un message e-mail, plus l'alias, la date, la clé et l'expéditeur."""
    sujet = _entete(msg, "Subject")
    info = classer(msg.get("From"), sujet, texte_du_mail(msg))
    try:
        date = email.utils.parsedate_to_datetime(msg.get("Date")).astimezone(timezone.utc)
    except Exception:                                                   # noqa: BLE001
        date = _maintenant()
    info.update(alias=alias_du_mail(msg), sujet=sujet, date=date, mid=cle_du_mail(msg),
                expediteur=adresse_expediteur(msg.get("From")))
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


def _pret_a_lire(boite, delai: float) -> bool:
    """Vrai si la connexion a quelque chose à lire avant `delai` secondes (IDLE)."""
    sock = getattr(boite, "sock", None)
    if sock is None:
        return False
    if getattr(sock, "pending", None) and sock.pending():
        return True
    lisibles, _, _ = select.select([sock], [], [], max(0.0, delai))
    return bool(lisibles)


class Lecteur:
    """Le SEUL lecteur de la boîte (10/10). Bloquant : appelé par boucle_codes via asyncio.to_thread, jamais deux à la fois.
    État : {dossier: {"validite": UIDVALIDITY, "dernier": dernier UID lu}} — persistant, donc un redémarrage ne relit rien
    de déjà vu. Un premier passage (ou un UIDVALIDITY changé) lit seulement les mails Meta des JOURS_AMORCE derniers jours."""

    def __init__(self):
        self.boite = None
        self.idle = False
        self.selection = None
        self.validite = None                                           # UIDVALIDITY du dossier ouvert
        self.etat = {}
        self.vus = OrderedDict()
        self.trieur = None                                             # bans_mail : (dossier, sujet, expediteur) → dossier cible
        self.quota_t = None                                            # monotonic() peut valoir moins de 3600 au démarrage

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
        Renvoie {"mails": [{"uid", "dossier", "mid", "msg", "amorce"}], "quota": (utilisé, limite) | None}."""
        if self.boite is None:
            self._connecter()
        if attendre > 0 and self.idle:
            self._idle(attendre)
        mails = []
        for dossier in self.dossiers():
            try:
                mails += self._nouveaux(dossier)
            except imaplib.IMAP4.abort:
                raise                                                  # la connexion est cassée : le passage échoue
            except imaplib.IMAP4.error as erreur:
                if dossier == IMAP_DOSSIER:
                    raise
                journal.warning("Codes : dossier %s ignoré : %s", dossier, erreur)   # un Spam absent ne bloque rien
                self.selection = None
        quota = None
        if self.quota_t is None or time.monotonic() - self.quota_t > 3600:   # la boîte pleine, vérifiée une fois par heure
            self.quota_t = time.monotonic()
            quota = self._quota()
        return {"mails": mails, "quota": quota}

    def _idle(self, secondes: float) -> bool:
        """IDLE sur le dossier principal : rend la main dès qu'un mail arrive (EXISTS), au plus `secondes` secondes."""
        boite = self.boite
        self._selectionner(IMAP_DOSSIER)
        tag = boite._new_tag()
        boite.send(tag + b" IDLE\r\n")
        ligne = boite.readline()
        if not ligne.startswith(b"+"):
            while ligne and not ligne.startswith(tag):
                ligne = boite.readline()
            boite.tagged_commands.pop(tag, None)
            self.idle = False                                          # le serveur refuse : sondage simple désormais
            return False
        nouveau = False
        fin = time.monotonic() + secondes
        try:
            while True:
                reste = fin - time.monotonic()
                if reste <= 0 or not _pret_a_lire(boite, reste):
                    break
                ligne = boite.readline()
                if not ligne:
                    raise imaplib.IMAP4.abort("connexion fermée pendant IDLE")
                if re.search(rb"\b(EXISTS|RECENT)\b", ligne):
                    nouveau = True
                    break
        finally:
            boite.send(b"DONE\r\n")
            while True:
                ligne = boite.readline()
                if not ligne:
                    raise imaplib.IMAP4.abort("connexion fermée après IDLE")
                if ligne.startswith(tag):
                    break
            boite.tagged_commands.pop(tag, None)
        return nouveau

    def _quota(self):
        if "QUOTA" not in tuple(str(c).upper() for c in (getattr(self.boite, "capabilities", ()) or ())):
            return None
        try:
            ok, data = self.boite.getquotaroot(_q("INBOX"))
        except imaplib.IMAP4.error:
            return None
        plats = []
        for el in data or []:
            plats += el if isinstance(el, list) else [el]
        m = re.search(rb"STORAGE (\d+) (\d+)", b" ".join(x if isinstance(x, bytes) else str(x).encode() for x in plats))
        return (int(m.group(1)), int(m.group(2))) if m else None

    def _incrementer(self, dossier: str, st: dict, uidnext: int = 0) -> list:
        """Les UID au-delà du dernier lu (« UID n:* » rend au moins le dernier mail : filtré)."""
        dernier = int(st.get("dernier", 0))
        ok, ids = self.boite.uid("SEARCH", None, f"UID {dernier + 1}:*")
        uids = sorted(int(u) for u in (ids[0].split() if ok == "OK" and ids and ids[0] else []) if int(u) > dernier)
        st["dernier"] = max([dernier, uidnext - 1] + uids)
        return self._lire(dossier, uids, False)

    def _nouveaux(self, dossier: str) -> list:
        st = self.etat.get(dossier)
        if self.selection is not None and self.selection[0] == dossier and st is not None \
                and self.validite is not None and int(st.get("validite", -1)) == self.validite:
            # Le dossier ouvert (celui d'IDLE) : jamais de STATUS sur lui (RFC 3501, la réponse peut être périmée) ;
            # une recherche UID suffit, et ne rend que l'UID du dernier mail quand rien n'est arrivé.
            return self._incrementer(dossier, st)
        ok, data = self.boite.status(_q(dossier), "(UIDNEXT UIDVALIDITY)")
        if ok != "OK":
            journal.warning("Codes : dossier %s illisible (STATUS)", dossier)
            return []
        brut = b" ".join(x for x in data if isinstance(x, bytes))
        m_next, m_val = re.search(rb"UIDNEXT (\d+)", brut), re.search(rb"UIDVALIDITY (\d+)", brut)
        if not (m_next and m_val):
            return []
        uidnext, validite = int(m_next.group(1)), int(m_val.group(1))
        amorce = st is None or int(st.get("validite", -1)) != validite
        if amorce:
            self._selectionner(dossier)
            depuis = (_maintenant() - timedelta(days=JOURS_AMORCE)).strftime("%d-%b-%Y")
            uids = set()
            for mot in MOTS_EXPEDITEUR:
                ok, ids = self.boite.uid("SEARCH", None, f'(SINCE {depuis} FROM "{mot}")')
                if ok == "OK" and ids and ids[0]:
                    uids.update(int(u) for u in ids[0].split())
            uids = sorted(uids)[-AMORCE_MAX:]
            self.etat[dossier] = {"validite": validite, "dernier": max([uidnext - 1] + uids)}
            return self._lire(dossier, uids, True)
        if uidnext - 1 <= int(st.get("dernier", 0)):
            return []
        self._selectionner(dossier)
        return self._incrementer(dossier, st, uidnext)

    def _lire(self, dossier: str, uids: list, amorce: bool) -> list:
        """En-têtes de tous les nouveaux mails, corps seulement pour les expéditeurs Meta (par l'ADRESSE)."""
        sortie, deplacer = [], []
        champs = "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])"
        for i in range(0, len(uids), 50):
            lot = uids[i:i + 50]
            ok, data = self.boite.uid("FETCH", ",".join(str(u) for u in lot), champs)
            if ok != "OK":
                continue
            for uid, entetes in _paires_fetch(data):
                tete = email.message_from_bytes(entetes or b"")
                if not expediteur_meta(tete.get("From")):
                    continue
                mid = cle_du_mail(tete)
                if mid in self.vus:                                    # déjà lu (remonté du Spam, relu après un UIDVALIDITY)
                    continue
                ok, corps = self.boite.uid("FETCH", str(uid), "(BODY.PEEK[]<0.60000>)")
                paires = _paires_fetch(corps) if ok == "OK" else []
                if not paires:
                    continue
                self.vus[mid] = True
                while len(self.vus) > 3000:
                    self.vus.popitem(last=False)
                msg = email.message_from_bytes(paires[0][1] or b"")
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
    """{"uid": {...}, "codes": [...], "faits": {cle: iso}, "sante": {cle: iso}, "panne_signalee": bool}. Les codes gardés n'y
    sont jamais écrits : seulement leur type, leur adresse et leur date."""
    if not _ETAT:
        f = _fichier_etat()
        try:
            _ETAT.update(json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {})
        except (OSError, ValueError):
            journal.warning("codes_lecteur.json illisible, réinitialisé")
        for cle, defaut in (("uid", {}), ("codes", []), ("faits", {}), ("sante", {})):
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


def codes_recents(adresses, minutes: int = None, decision: str = "donner") -> list:
    """Les entrées du cache (« donner » ou « garder ») des `adresses`, plus récentes d'abord, dans la fenêtre."""
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    adresses = {str(a).strip().lower() for a in adresses or []}
    limite = _maintenant() - timedelta(minutes=minutes)
    trouves = [t for t in _etat()["codes"] if t.get("alias") in adresses and t.get("decision") == decision
               and _date(t) >= limite]
    return sorted(trouves, key=_date, reverse=True)


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


async def _servir(adresses: set, dire, cle_guet: str, duree: int = None, minutes: int = None) -> str:
    """Le cœur du bouton et de `!code` : `dire(texte)` poste ou remplace la réponse PRIVÉE. Renvoie l'issue (« code »,
    « ancien », « rien », « panne », « deja ») pour le journal et les tests. Un code gardé n'est jamais dit."""
    duree = ATTENTE_SEC if duree is None else duree
    minutes = SALON_CODES_MINUTES if minutes is None else minutes
    donnes = codes_recents(adresses, minutes)
    dernier = donnes[0] if donnes else None
    gardes = codes_recents(adresses, minutes, decision="garder")
    garde = gardes[0] if gardes and (dernier is None or _date(gardes[0]) >= _date(dernier)) else None
    if dernier is not None and _age_min(dernier) < FRAIS_MIN:
        frais = [t for t in donnes if _age_min(t) < FRAIS_MIN]
        await dire(_texte_codes(frais) + ("\n\n-# Un e-mail plus récent sur ton adresse n'est pas un code de connexion ni "
                                          "de création : je ne le donne pas." if garde else ""))
        return "code"
    if cle_guet in _guets:                                             # il rappuie : la réponse la plus récente suit le guet
        _guets[cle_guet]["dire"] = dire
        await dire(TEXTE_ATTENTE)
        return "deja"
    entete = _texte_ancien(dernier) if dernier is not None else TEXTE_ATTENTE
    if garde is not None:
        entete = TEXTE_GARDE + "\n\n" + (entete if dernier is not None else "⏳ Je guette quand même 5 minutes un code de "
                                         "connexion ou de création : il s'affiche ici tout seul.")
    _guets[cle_guet] = {"dire": dire}
    await dire(entete)
    vu_garde = garde
    try:
        fin = time.monotonic() + duree
        while time.monotonic() < fin:
            await _attendre_nouveau(min(5.0, fin - time.monotonic()))
            nouveaux = [t for t in codes_recents(adresses, minutes) if dernier is None or _date(t) > _date(dernier)]
            if nouveaux:
                await _guets[cle_guet]["dire"](_texte_codes(nouveaux))
                return "code"
            gardes = codes_recents(adresses, minutes, decision="garder")
            if gardes and gardes[0] is not vu_garde and (vu_garde is None or _date(gardes[0]) > _date(vu_garde)) \
                    and (dernier is None or _date(gardes[0]) > _date(dernier)):
                vu_garde = gardes[0]
                await _guets[cle_guet]["dire"](TEXTE_GARDE + "\n\n⏳ Je guette encore un code de connexion ou de création.")
        if lecteur_en_panne():
            await _guets[cle_guet]["dire"](TEXTE_PANNE)
            return "panne"
        await _guets[cle_guet]["dire"]((_texte_ancien(dernier) + "\n\n" if dernier is not None else "") + TEXTE_RIEN)
        return "ancien" if dernier is not None else "rien"
    finally:
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
    return await _servir(adresses, dire, f"u|{getattr(membre, 'id', '')}")


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
    if adresse:
        adresses = {adresse.strip().lower()}
    elif adresses_de_membre is not None:
        try:
            adresses = {str(a).strip().lower() for a in adresses_de_membre() or [] if a and "@" in str(a)}
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Adresses du clipper (salon commun) : %s", _err(erreur))
            adresses = set()
    else:
        adresses = _adresses_membre(message.author)
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

    await _servir(adresses, dire, f"u|{getattr(message.author, 'id', '')}")
    return True


# ------------------------------------------------------------------ 2. et 6. la boucle : flux, alertes, santé
def _salon_prive(salon) -> bool:
    """Vrai si @everyone ne voit pas ce salon : un code ne s'écrit jamais dans un salon public, ni dans le salon commun."""
    try:
        if str(getattr(salon, "id", "")) == salon_codes_id():
            return False
        return not salon.permissions_for(salon.guild.default_role).view_channel
    except Exception:                                                   # noqa: BLE001 — inconnu : pas privé
        return False


def _proprietaire(alias: str) -> dict:
    v = _lire().get(alias)
    return v if isinstance(v, dict) else {}


async def _traiter_lus(client, resultat: dict) -> dict:
    """Les mails nouveaux du lecteur : cache des codes donnables, lignes admin (codes gardés, changements, adresses
    rattachées à personne), push dans le salon d'un manager (`!alias`), abonnés (bans_mail). Renvoie un bilan."""
    bilan = {"donnes": 0, "gardes": 0, "alertes": 0, "orphelins": 0}
    e = _etat()
    connus = {t.get("mid") for t in e["codes"]}
    commun = salon_codes_id()
    for lu in resultat.get("mails") or []:
        msg, dossier = lu["msg"], lu["dossier"]
        for abonne in list(_ABONNES):
            try:
                abonne(msg, dossier)
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Abonné du lecteur des codes : %s", _err(erreur))
        info = classer_mail(msg)
        mid, alias = info["mid"], info["alias"]
        recent = not lu.get("amorce") or _maintenant() - info["date"] < timedelta(minutes=60)
        journal.info("Codes : %s (%s) sur %s → %s", info["libelle"] or "mail Meta", dossier, _masquer(alias), info["decision"])
        if info["decision"] == "donner":
            if mid not in connus:
                e["codes"].append({"mid": mid, "alias": alias, "code": info["code"], "type": info["type"],
                                   "decision": "donner", "compte": info["compte"], "date": _iso(info["date"])})
                connus.add(mid)
                bilan["donnes"] += 1
            proprio = _proprietaire(alias)
            if not proprio.get("canal_id"):
                if alias and recent and _une_fois(f"orphelin|{alias}", minutes=60):
                    bilan["orphelins"] += 1
                    await _admin(f"🔐 Code de {QUOI.get(info['type'], 'connexion')} reçu sur `{alias}`, une adresse rattachée "
                                 "à personne : je ne le donne à personne.\n\n"
                                 f"Si c'est l'adresse d'un clipper : `!alias ajouter {alias}` dans son salon perso.")
            elif proprio.get("par") != "onboarding" and str(proprio["canal_id"]) != str(commun) \
                    and _age_min({"date": _iso(info["date"])}) < FRAIS_MIN and _une_fois(f"push|{mid}"):
                salon = client.get_channel(int(proprio["canal_id"])) if str(proprio["canal_id"]).isdigit() else None
                if salon is not None and not _salon_prive(salon):
                    journal.warning("Code non poussé : le salon %s est lisible par tous", getattr(salon, "name", "?"))
                elif salon is not None:
                    try:
                        await salon.send(ligne_code(dict(info, date=_iso(info["date"]))))
                    except (discord.Forbidden, discord.HTTPException) as erreur:
                        journal.warning("Code non posté dans le salon du manager : %s", _err(erreur))
        elif info["decision"] == "garder":
            if mid not in connus:                                       # jamais le code : le type, l'adresse, la date
                e["codes"].append({"mid": mid, "alias": alias, "type": info["type"], "decision": "garder",
                                   "compte": info["compte"], "libelle": info["libelle"], "date": _iso(info["date"])})
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
    quota = resultat.get("quota")
    if quota and quota[1] and quota[0] / quota[1] >= QUOTA_SEUIL and _une_fois("sante|pleine", minutes=60):
        await _admin(f"⚠️ **Boîte des codes presque pleine** : {round(100 * quota[0] / quota[1])} % utilisés.\n\n"
                     "Libère de la place (vieux mails Meta, Drive, Photos). Une boîte pleine ne reçoit plus aucun code, "
                     "sans aucune erreur.")
    if resultat.get("mails") or quota:
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
    _traiter_lus. Jamais tuée par un mail ou une panne."""
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
    """Au démarrage : le salon commun existe (créé sinon), réservé à l'équipe ; le mode d'emploi v6 est épinglé avec le
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
