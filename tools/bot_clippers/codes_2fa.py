"""Relais des codes de vérification Instagram/Facebook vers les managers (07/09/2026).

POURQUOI : chaque compte Instagram de l'agence est créé avec un alias « Masquer mon adresse »
iCloud qui renvoie vers UNE boîte Gmail — celle de Gaëtan. Résultat : chaque création de compte
et chaque 2FA passe par lui. Ce module lit une boîte mail DÉDIÉE aux codes (jamais la boîte
personnelle) et pousse le code dans le salon Discord du manager qui possède l'alias :
Jonas crée ses comptes sans Gaëtan.

SÉCURITÉ :
- La boîte lue doit être une boîte dédiée (ex. une adresse Gmail créée pour ça, cible du
  renvoi « Masquer mon adresse »). Le mot de passe d'application ne vit que dans l'environnement.
- Seuls les mails des expéditeurs Meta (instagram.com, facebookmail.com…) sont lus ; on n'en
  extrait QUE le code ; jamais le corps du mail n'est relayé.
- Un code n'est posté que dans le salon auquel l'alias est rattaché (registre !alias) ; un alias
  inconnu remonte au salon admin pour que rien ne se perde.

27/09 — CODES DE RÉCUPÉRATION : Instagram envoie « 956472 is your Instagram recovery code » quand on
fait « mot de passe oublié » ou quand on fait appel pour un compte banni. Même boîte, même alias,
même salon : le mail est reconnu comme code de RÉCUPÉRATION (sujet), posté avec ce libellé et le
pseudo du compte concerné, et `!recup` (alias `!appel`, `!unban`) le redonne à la demande (6 h).
"""

import asyncio
import email
import imaplib
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

import discord

journal = __import__("logging").getLogger("bot_clippers")

IMAP_HOST = os.environ.get("CODES_IMAP_HOST", "imap.gmail.com").strip()
IMAP_USER = os.environ.get("CODES_IMAP_USER", "").strip()
IMAP_PASSWORD = os.environ.get("CODES_IMAP_PASSWORD", "").strip()
# Dossier/libellé lu (Gmail : un libellé = un dossier IMAP). Avec un filtre Gmail « expéditeurs Meta →
# libellé Codes », le bot ne parcourt JAMAIS le reste de la boîte, même sur une adresse personnelle.
IMAP_DOSSIER = os.environ.get("CODES_IMAP_DOSSIER", "INBOX").strip() or "INBOX"
ROLE_MANAGER_NOM = os.environ.get("ROLE_MANAGER_NOM", "Manager").strip()
INTERVALLE = int(os.environ.get("CODES_INTERVALLE_SEC", "45"))
_guets = set()                                                  # salons où un !code guette déjà (30/09 : pas de doublon)
# 27/09 (Daniella, 22:13) : « Code » tapé juste après « Envoyer le code » → « pas de code depuis 2 heures », puis le code
# posté une seconde plus tard par la boucle. `!code` attend maintenant jusqu'à ATTENTE_SEC que le mail arrive.
ATTENTE_SEC = int(os.environ.get("CODES_ATTENTE_SEC", "300"))   # 30/09 (Ricardo a tapé « code » 3 fois) : 5 min de guet, plus 1
ATTENTE_PAS = int(os.environ.get("CODES_ATTENTE_PAS_SEC", "15"))
IMAP_TIMEOUT = int(os.environ.get("CODES_IMAP_TIMEOUT_SEC", "30"))
# Mots attendus dans le SUJET d'un mail de code (Meta en envoie aussi sur les connexions, les
# nouveautés, la sécurité…) : un mail sans l'un d'eux ne relaie jamais un nombre pris au hasard.
MOTS_SUJET = tuple(m.strip().lower() for m in os.environ.get(
    "CODES_MOTS_SUJET", "code,confirm,vérif,verif,connexion,login,sécurité,security,verify").split(",") if m.strip())
EXPEDITEURS = tuple(e.strip().lower() for e in os.environ.get(
    "CODES_EXPEDITEURS", "instagram.com,facebookmail.com,facebook.com,meta.com").split(",") if e.strip())

FICHIER_ALIAS = None            # injecté par bot_discord.py (volume persistant)
# 29/09 (Gaëtan) : « un salon "code Instagram" pour tout le monde, les anciens de Jonas aussi : le clipper tape !code et ça sort
# le code 2FA des dernières minutes, sans e-mail ni mot de passe ». Un salon commun, ouvert à tous, `!code` y répond à tout le
# monde avec les codes des CODES_SALON_MINUTES dernières minutes, adresse masquée (3 premières lettres, 2 dernières).
# 01/10 : un clipper n'y reçoit plus que les codes de SES adresses (adresses_de) ; le staff voit toujours tout.
SALON_CODES_NOM = os.environ.get("CANAL_CODES_NOM", "🔐-code-instagram").strip() or "🔐-code-instagram"
# 30/09 : une fenêtre pour tout (création, connexion, appel). 15 → 60 min le même jour : Tara a tapé `!code` 21 min après le
# mail de son appel (on demande le code sur Instagram, on arrive sur Discord bien après), Gaëtan a dû le lui donner à la main.
SALON_CODES_MINUTES = int(os.environ.get("CODES_SALON_MINUTES", "60") or 60)
SALON_RECUP_MINUTES = int(os.environ.get("CODES_SALON_RECUP_MINUTES", "30") or 30)
DOSSIER_SPAM = os.environ.get("CODES_IMAP_SPAM", "[Gmail]/Spam").strip()
# 29/09 (Gaëtan) : « restreins le salon au rôle Clippeur ; simplifie, rajoute des émojis, mets en forme, langage niveau collège »
ROLES_SALON_CODES = tuple(r.strip() for r in os.environ.get("CODES_SALON_ROLES", "Clippeur,Rookie,Confirmé,Elite").split(",") if r.strip())
# 01/10 (Gaëtan : « les codes Instagram se demandent UNIQUEMENT dans le salon #🔐-code-instagram ») : un clipper n'y voit
# que les codes de SES adresses, le message qui porte un code s'efface seul après CODES_EFFACER_MIN minutes, et la boucle
# ne pousse plus rien dans les salons perso des clippers (CODES_PUSH_SALON_PERSO=1 remet l'ancien comportement).
EFFACER_MIN = int(os.environ.get("CODES_EFFACER_MIN", "10") or 10)
PUSH_SALON_PERSO = os.environ.get("CODES_PUSH_SALON_PERSO", "0").strip().lower() not in ("", "0", "non", "false", "off")
VERSION_EXPLICATION = 5
# 30/09 (Gaëtan : « la même commande pour faire appel, créer un compte ou se connecter ; jamais le code pour modifier les
# informations sensibles ; supprime la ligne de l'adresse à moitié cachée »)
# 01/10 : chacun ne voit plus que ses codes, et le message s'efface seul (version 5).
EXPLICATION_SALON = ("🔐 **Ton code Instagram, c'est ici.**\n\n"
                     "Une seule commande pour tout : `!code`\n\n"
                     "1️⃣ Créer un compte\n"
                     "2️⃣ Te connecter\n"
                     "3️⃣ Faire appel après un ban\n\n"
                     "➡️ Tu fais ta demande sur Instagram. Instagram t'envoie un code par e-mail. Tu écris `!code` ici. "
                     "Je te donne le code de tes adresses reçu dans les {minutes} dernières minutes. ✅\n\n"
                     f"🧹 Le message avec ton code s'efface tout seul après {EFFACER_MIN} minutes.\n\n"
                     "😴 Pas de code ? Dans Instagram, appuie sur « Renvoyer le code », attends 30 secondes, puis retape `!code`.\n\n"
                     "⛔ Changer l'e-mail, le mot de passe ou le numéro d'un compte : jamais. Ces codes-là, je ne les donne pas.")

# Sous-chaînes cherchées côté serveur dans l'en-tête From (IMAP FROM) : courtes pour attraper les expéditeurs
# réécrits par iCloud, sans « meta » seul qui ramènerait Metricool.
MOTS_EXPEDITEUR = ("instagram", "facebook", "meta.com", "meta_com")
# 01/10 (faux code « 94025 » donné deux fois à Steeve le 30/09) : le premier nombre du corps était le code postal du pied
# de page de Meta (« Menlo Park, CA 94025 ») sur des mails sans code (« Vérifiez votre compte », « confirm your email »).
# Le nombre doit maintenant être isolé (pas collé à un pseudo comme « prenom.vip12345 »), le pied de page est retiré, et
# dans le corps on ne prend qu'un nombre qui suit « code » ou « confirmation » de près. Le sujet reste lu tel quel.
MOTIF_CODE = re.compile(r"(?<![\w.@-])(?:FB-?)?(\d{5,8})(?![\w@])")
MOTIF_CODE_CORPS = re.compile(r"(?:code|confirmation)\D{0,60}?(?<![\w.@-])((?:FB-?)?\d{5,8})(?![\w@])", re.I)
PIED_META = re.compile(r"Menlo Park,?\s*CA\s*\d{5}(?:-\d{4})?", re.I)
# 01/10 (mail « Votre mot de passe Instagram a été changé » du 30/09, ignoré sans alerte) : un mot de passe ou une adresse
# e-mail DÉJÀ changés, c'est sensible même sans code — une ligne au salon admin, une fois (règle « jamais changer le mot de
# passe »). Lu sur le sujet sans accents, avant le filtre MOTS_SUJET.
MOTIFS_CHANGEMENT = tuple(re.compile(m) for m in (
    r"\b(mot de passe|password)\W+(\w+\W+){0,5}(change|changee|changed|modifie|modifiee|modified)\b",
    r"\b(e-?mail|adresse)\W+(\w+\W+){0,5}(change|changee|changed|modifie|modifiee|modified)\b"))
MOTIF_ALIAS = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
# 27/09 : les codes de RÉCUPÉRATION (« 956472 is your Instagram recovery code » : mot de passe oublié, appel après
# un ban) arrivent par le même chemin que les codes 2FA — même alias, même boîte, même salon. On les distingue pour
# que le clipper, ou le manager qui fait appel, sache quel code Instagram attend, et pour que `!recup` ne renvoie
# jamais un code de connexion à la place. Le sujet décide ; le corps ne compte que pour quelques tournures sûres.
MOTS_RECUP_SUJET = ("recovery", "récupér", "recuper", "retrouver", "get back", "appel", "appeal", "review", "examen")
# 30/09 (Gaëtan : « jamais renvoyer le code pour modifier les informations sensibles ») : un mail dont le SUJET ou le
# DÉBUT (les 500 premiers caractères, là où Meta dit à quoi sert le code) parle de changer l'e-mail, le mot de passe, le
# numéro, la double authentification, ou de désactiver / supprimer le compte : le code n'est donné à personne, ni ici, ni
# dans un salon perso, ni au staff ; une ligne part au salon admin. Le bas du mail n'est pas lu : les codes de connexion y
# disent souvent « si ce n'était pas vous, changez votre mot de passe ».
MOTIFS_SENSIBLES = tuple(re.compile(m) for m in (
    r"(reset|reinitialis|change|chang|modif|update|mettre a jour|nouve(au|l|lle)|new|add|ajout)\w*\W+(\w+\W+){0,4}"
    r"(password|mot de passe|e-?mail|adresse|phone|telephone|numero|mobile)",
    r"(password|mot de passe)\W+(\w+\W+){0,2}(reset|reinitialis|change|oubli)",
    r"(e-?mail|adresse)\W+(\w+\W+){0,2}(change|modifi)",
    r"two[- ]factor|2fa|deux facteurs|double authentification|authentification a deux",
    r"deactivat|desactiv|delete your account|supprimer (votre|ton) compte|suppression (de|du) (votre |ton )?compte"))
MOTS_RECUP_CORPS = ("recovery code", "code de récupération", "code de recuperation", "get back into", "without password",
                    "sans mot de passe", "retrouver l'accès", "retrouver votre compte")
MOTIF_COMPTE = re.compile(r"\b(?:Hi|Hello|Bonjour|Salut)\s+([A-Za-z0-9][A-Za-z0-9._]{1,40}?)\s*[,!]")
TYPE_RECUP, TYPE_CONNEXION, TYPE_SENSIBLE = "récupération", "connexion", "sensible"


def _sans_accents(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def est_sensible(sujet: str, corps: str) -> bool:
    """Vrai si le code sert à changer une information sensible du compte. On lit le sujet et le mail jusqu'à la fin de la
    phrase qui porte le code (500 caractères au plus) : ce qui suit (« si ce n'était pas vous, changez votre mot de passe »)
    ne compte pas."""
    debut = corps[:500]
    m = MOTIF_CODE.search(debut)
    if m:
        fin = re.search(r"[.!?](\s|$)|\n", debut[m.end():])
        debut = debut[:m.end() + (fin.end() if fin else len(debut))]
    texte = _sans_accents(f"{sujet} {debut}")
    return any(r.search(texte) for r in MOTIFS_SENSIBLES)
COMMANDES_RECUP = ("!recup", "!récup", "!recuperation", "!récupération", "!appel", "!unban", "!deban")


def actif() -> bool:
    return bool(IMAP_USER and IMAP_PASSWORD)


def _masquer(alias: str) -> str:
    """« orbite_machin.8i@icloud.com » → « orb…8i@icloud.com » : reconnaissable par son propriétaire, illisible pour les autres."""
    if not alias or "@" not in alias:
        return "adresse inconnue"
    local, domaine = alias.split("@", 1)
    return f"{local[:3]}…{local[-2:]}@{domaine}" if len(local) > 5 else f"{local[:1]}…@{domaine}"


def salon_codes_id() -> str:
    """L'id du salon commun des codes, retenu dans le registre des alias (clé `_salon_codes`)."""
    try:
        return str((_lire().get("_salon_codes") or {}).get("id") or "")
    except Exception:                                                   # noqa: BLE001
        return ""


def texte_salon_codes() -> str:
    """01/10 (Gaëtan : « les codes Instagram se demandent UNIQUEMENT dans #🔐-code-instagram ») : la ligne canonique, avec
    le lien du salon quand son id est connu."""
    sid = salon_codes_id()
    return f"Un code Instagram ? Va dans {f'<#{sid}>' if sid else '#' + SALON_CODES_NOM} et tape !code."


def adresses_de(salon_perso_id: str = "", fiche: dict = None) -> set:
    """01/10 : les adresses d'un clipper — les alias rattachés à son salon perso dans le registre, plus les e-mails de ses
    comptes dans sa fiche d'onboarding (« acces »). Le classeur n'est pas relu ici (appel réseau à chaque !code)."""
    adresses = set()
    if salon_perso_id:
        for alias, v in _lire().items():
            if "@" in alias and isinstance(v, dict) and str(v.get("canal_id")) == str(salon_perso_id):
                adresses.add(alias.strip().lower())
    # 01/10 (relecture : `!liberer Prénom h2` retire h2 de « comptes » mais pas de « acces » — le clipper gardait les codes
    # d'un compte qui n'est plus à lui) : seulement les accès des comptes encore dans sa fiche.
    fiche = fiche or {}
    siens = {str(h).strip().lower() for h in fiche.get("comptes") or []} if "comptes" in fiche else None
    for acces in fiche.get("acces") or []:
        if not isinstance(acces, dict):
            continue
        if siens is not None and str(acces.get("handle") or "").strip().lower() not in siens:
            continue
        mail = str(acces.get("mail") or "").strip().lower()
        if "@" in mail:
            adresses.add(mail)
    return adresses


# 01/10 (Ricardo « Code pour le compte 2 », parti à l'assistant IA) : une phrase courte autour du mot « code » vaut `!code`.
_MOT_SEUL = re.compile(r"!?\s*(codes?|r[ée]cup(?:[ée]ration)?)\s*[!?.]*", re.I)
_MOT_CODE = re.compile(r"(?<![\w-])codes?(?![\w-])", re.I)
_AUTRE_QUESTION = re.compile(r"(?<!\w)(comment|pourquoi|combien|quand)(?!\w)", re.I)
# 01/10 (relecture : « merci pour le code », « code bon » relançaient un guet de 5 min et reposaient le code) : un
# remerciement n'est jamais une demande ; une confirmation non plus, sauf niée (« j'ai pas reçu le code » reste une demande).
_MERCI = re.compile(r"(?<!\w)(merci|mrc|thanks?|thx)(?!\w)", re.I)
_CONFIRME = re.compile(r"(?<!\w)(bon|ok|okay|re[çc]u|marche|parfait|nickel|top|super|good)(?!\w)", re.I)
_NEGATION = re.compile(r"(?<!\w)(?:(?:pas|plus|toujours|jamais|rien|aucun|ne)(?!\w)|n['’])", re.I)


def demande_de_code(texte: str) -> str:
    """« !code » / « !recup » si le message est une demande de code (« Code », « ! code », « code pour le compte 2 »,
    « le code stp », « j'ai pas reçu le code »), sinon "". Moins de 6 mots, le mot « code », sans autre question."""
    t = (texte or "").strip()
    m = _MOT_SEUL.fullmatch(t)
    if m:
        return "!code" if m.group(1).lower().startswith("code") else "!recup"
    if not t or "\n" in t or len(t) > 60 or len(t.split()) >= 6 or "http" in t.lower() or "@" in t:
        return ""
    if t.startswith("!") and not re.match(r"!\s*codes?(?![\w-])", t, re.I):
        return ""                                                       # une autre commande
    if not _MOT_CODE.search(t) or _AUTRE_QUESTION.search(t):
        return ""
    if _MERCI.search(t) or (_CONFIRME.search(t) and not _NEGATION.search(t)):
        return ""                                                       # 01/10 : « merci pour le code », « code bon »
    return "!code"


def _err(erreur) -> str:
    """01/10 : str(TimeoutError()) vaut "" — le journal et le digest affichaient « IMAP : » vide. Le type d'abord."""
    return f"{type(erreur).__name__} {erreur}".strip()


# 01/10 : une seule connexion IMAP du bot à la fois (la boucle, chaque !code qui guette et le salon commun ouvraient chacun
# la leur sur la même boîte Gmail), et un verrou autour de « lire _relayes, poster, écrire _relayes » (le même code posté
# deux fois dans #ricardo le 30/09 : la boucle et !code l'avaient vu ensemble). Créés dans la boucle asyncio qui tourne.
_sem_imap = (None, None)
_verrou_relayes = (None, None)


def _verrou():
    global _verrou_relayes
    boucle = asyncio.get_running_loop()
    if _verrou_relayes[0] is not boucle:
        _verrou_relayes = (boucle, asyncio.Lock())
    return _verrou_relayes[1]


async def _imap(fonction, *args, delai=None):
    """Lance `fonction` (bloquante, IMAP) dans un fil, une seule à la fois. Le jeton n'est rendu qu'à la vraie fin du fil :
    un délai dépassé n'ouvre pas une deuxième connexion à côté de celle qui traîne encore."""
    global _sem_imap
    delai = delai or IMAP_TIMEOUT * 3
    boucle = asyncio.get_running_loop()
    if _sem_imap[0] is not boucle:
        _sem_imap = (boucle, asyncio.Semaphore(1))
    sem = _sem_imap[1]
    await asyncio.wait_for(sem.acquire(), timeout=delai)
    tache = asyncio.ensure_future(asyncio.to_thread(fonction, *args))

    def _fin(f):
        sem.release()
        if not f.cancelled():
            f.exception()                                               # lue : pas d'« exception never retrieved »
    tache.add_done_callback(_fin)
    return await asyncio.wait_for(asyncio.shield(tache), timeout=delai)


def _recent(quand, minutes: int = 10) -> bool:
    """Vrai si la date ISO `quand` (registre _relayes) date de moins de `minutes`."""
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(str(quand)) < timedelta(minutes=minutes)
    except (TypeError, ValueError):
        return False


def ligne_code_masquee(t: dict) -> str:
    """La ligne du salon commun : le code, l'adresse masquée, le pseudo si le mail le donne, l'âge — jamais l'e-mail entier."""
    compte = f" · compte `@{t['compte']}`" if t.get("compte") else ""
    age = t.get("age_min")
    quand = "" if age is None else (" · à l'instant" if age < 1 else f" · reçu il y a {age} min")
    genre = "Code de récupération" if t.get("type") == TYPE_RECUP else "Code"
    return (f"🔐 **{genre} {t.get('plateforme', 'Instagram')}** · adresse `{_masquer(t.get('alias', ''))}`{compte}{quand} :"
            f"\n```\n{t['code']}\n```")


def _droits_salon_codes(guild) -> tuple:
    """(overwrites, noms des rôles admis) : fermé à @everyone, ouvert aux rôles de l'équipe (CODES_SALON_ROLES) et aux managers."""
    voir = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
                  guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)}
    cibles = {_cle(n) for n in ROLES_SALON_CODES} | {_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")}
    admis = []
    for role in guild.roles:
        if _cle(role.name) in cibles:
            overwrites[role] = voir
            admis.append(role.name)
    return overwrites, admis


async def assurer_salon_codes(client):
    """Au démarrage : le salon commun existe (créé sinon), réservé aux rôles de l'équipe et aux managers, son id est retenu,
    son mode d'emploi épinglé (remplacé quand le texte change : VERSION_EXPLICATION)."""
    await client.wait_until_ready()
    if not actif():
        return
    registre = _lire()
    info = registre.get("_salon_codes") or {}
    sujet = "Écris !code : ton code Instagram ou Facebook pour créer un compte, te connecter ou faire appel."
    for guild in client.guilds:
        salon = client.get_channel(int(info["id"])) if info.get("id") else None
        if salon is None:
            cible = _cle(SALON_CODES_NOM)
            salon = next((c for c in guild.text_channels if _cle(c.name) == cible), None)
        overwrites, admis = _droits_salon_codes(guild)
        if salon is None:
            try:
                salon = await guild.create_text_channel(SALON_CODES_NOM, overwrites=overwrites, topic=sujet, reason="Salon commun des codes 2FA (29/09)")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : création refusée (%s)", erreur)
                return
        else:
            try:
                await salon.edit(overwrites=overwrites, topic=sujet, reason="Salon des codes : réservé à l'équipe (29/09)")
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : droits non posés (%s)", erreur)
        if info.get("version") != VERSION_EXPLICATION or str(info.get("id")) != str(salon.id):
            try:
                for ancien in await salon.pins():                        # l'ancien mode d'emploi du bot s'efface
                    if ancien.author == guild.me:
                        try:
                            await ancien.delete()
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                m = await salon.send(EXPLICATION_SALON.format(minutes=SALON_CODES_MINUTES, recup=SALON_RECUP_MINUTES))
                try:
                    await m.pin()
                except (discord.Forbidden, discord.HTTPException):
                    pass
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Salon des codes : mode d'emploi non posté (%s)", erreur)
        registre = _lire()
        registre["_salon_codes"] = {"id": str(salon.id), "guild": str(guild.id), "explique": True, "version": VERSION_EXPLICATION,
                                    "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _ecrire(registre)
        journal.info("Salon des codes : #%s prêt, réservé à %s", salon.name, ", ".join(admis) or "personne (rôles introuvables !)")
        return


def _cle(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation — pour comparer un nom de rôle à l'exact près."""
    t = unicodedata.normalize("NFD", (texte or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


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


def _texte(valeur) -> str:
    try:
        return str(make_header(decode_header(valeur or "")))
    except Exception:
        return str(valeur or "")


def _corps(msg) -> str:
    """Le texte brut du mail (text/plain d'abord, sinon HTML débarrassé des balises)."""
    parties = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                brut = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            if part.get_content_type() == "text/html":
                brut = re.sub(r"<[^>]+>", " ", brut)
            parties.append(brut)
    return re.sub(r"\s+", " ", " ".join(parties))


def extraire(msg) -> dict:
    """{expediteur, alias, code, sujet} depuis un message ; code=None si rien d'exploitable."""
    expediteur = _texte(msg.get("From")).lower()
    # 25/09 : iCloud « Masquer mon adresse » réécrit l'expéditeur en no-reply_at_mail_instagram_com_xxx@icloud.com
    # (points → tirets bas) : « instagram.com » n'y était plus, chaque code passait à la trappe.
    if not any(d in expediteur or d in expediteur.replace("_", ".") for d in EXPEDITEURS):
        return {}
    destinataires = " ".join(_texte(msg.get(h)) for h in ("To", "Delivered-To", "X-Original-To") if msg.get(h))
    alias = next((a.lower() for a in MOTIF_ALIAS.findall(destinataires)), "")
    sujet = _texte(msg.get("Subject"))
    plateforme = "Facebook" if "facebook" in expediteur else "Instagram"
    sujet_sa = _sans_accents(sujet)
    if any(r.search(sujet_sa) for r in MOTIFS_CHANGEMENT):   # 01/10 : mot de passe / e-mail déjà changés → alerte admin
        return {"expediteur": expediteur, "alias": alias, "code": None, "sujet": sujet, "plateforme": plateforme,
                "type": TYPE_SENSIBLE, "changement": True}
    if MOTS_SUJET and not any(m in sujet.lower() for m in MOTS_SUJET):
        return {"expediteur": expediteur, "alias": alias, "code": None, "sujet": sujet, "plateforme": plateforme}
    code = None
    corps = PIED_META.sub(" ", _corps(msg)[:3000])             # 01/10 : jamais le code postal de Meta (94025)
    if est_sensible(sujet, corps):                             # 30/09 : jamais relayé, à personne
        return {"expediteur": expediteur, "alias": alias, "code": None, "sujet": sujet, "plateforme": plateforme,
                "type": TYPE_SENSIBLE}
    m = MOTIF_CODE.search(sujet)                               # Meta met le code dans le sujet (« 483972 is your Instagram code »)
    if m:
        code = m.group(0) if m.group(0).upper().startswith("FB") else m.group(1)
    else:                                                      # dans le corps : seulement un nombre qui suit « code » / « confirmation »
        m = MOTIF_CODE_CORPS.search(corps)
        code = m.group(1) if m else None
    genre = TYPE_RECUP if (any(m in sujet.lower() for m in MOTS_RECUP_SUJET)
                           or any(m in corps[:1500].lower() for m in MOTS_RECUP_CORPS)) else TYPE_CONNEXION
    m_compte = MOTIF_COMPTE.search(corps[:400])                # « Hi chloe.xxx, » : le pseudo du compte concerné
    compte = m_compte.group(1).rstrip(".") if m_compte else ""
    return {"expediteur": expediteur, "alias": alias, "code": code, "sujet": sujet, "plateforme": plateforme,
            "type": genre, "compte": compte}


def _lire_boite(uniquement_non_lus=True, alias=None, minutes=30, dossiers=None) -> list:
    """Bloquant (à appeler via to_thread) : les codes des mails Meta récents. Un mail n'est PLUS
    marqué lu ici : c'est le relais réussi qui le marque (_marquer_lus), sinon un code lu puis
    jamais posté (Discord en panne) était perdu — audit 10/09. `dossiers` (29/09) : le salon commun lit aussi le
    Spam ; hors du dossier principal, `num` vaut None (jamais marqué lu là-bas)."""
    resultats = []
    with imaplib.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT) as boite:
        boite.login(IMAP_USER, IMAP_PASSWORD)
        for dossier in (dossiers or [IMAP_DOSSIER]):
            resultats += _lire_dossier(boite, dossier, uniquement_non_lus, alias, minutes)
    return resultats


def _lire_dossier(boite, dossier, uniquement_non_lus, alias, minutes) -> list:
    resultats = []
    principal = dossier == IMAP_DOSSIER
    try:
        ok, _ = boite.select(dossier, readonly=not principal)
    except imaplib.IMAP4.error:
        ok = "NO"
    if ok != "OK":
        journal.warning("Relais 2FA : dossier %s illisible", dossier)
        return []
    if True:
        # SINCE = la veille : à 00 h 05 UTC, « aujourd'hui » excluait un code reçu deux minutes avant.
        depuis = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")
        base = f'UNSEEN SINCE {depuis}' if uniquement_non_lus else f'SINCE {depuis}'
        # 25/09 : recherche PAR EXPÉDITEUR. Sur une boîte perso à 12 000 non-lus, « UNSEEN SINCE hier » renvoyait
        # des centaines d'ids et le bot téléchargeait 40 newsletters entières par passage : délai dépassé à chaque
        # tour (TimeoutError sans message dans le journal), zéro code relayé. FROM est une sous-chaîne : elle
        # attrape aussi l'expéditeur réécrit par iCloud (no-reply_at_mail_instagram_com_…@icloud.com).
        nums = set()
        for mot in MOTS_EXPEDITEUR:
            ok, ids = boite.search(None, f'({base} FROM "{mot}")')
            if ok == "OK" and ids and ids[0]:
                nums.update(ids[0].split())
        if not nums:
            return []
        for num in sorted(nums, key=int)[-15:]:
            ok, brut = boite.fetch(num, "(BODY.PEEK[]<0.40000>)")      # en-têtes + 40 Ko : le code est dans le sujet
            if ok != "OK" or not brut or not brut[0]:
                continue
            msg = email.message_from_bytes(brut[0][1])
            info = extraire(msg)
            if not info:
                continue
            try:
                date_msg = email.utils.parsedate_to_datetime(msg.get("Date"))
                age = (datetime.now(timezone.utc) - date_msg.astimezone(timezone.utc)).total_seconds() / 60
            except Exception:
                age = 0
            if age > minutes:
                continue
            if alias and info["alias"] != alias.lower():
                continue
            info["num"] = num if principal else None
            info["age_min"] = max(0, int(age))
            resultats.append(info)
    return resultats


def _marquer_lus(nums: list):
    """Bloquant : marque lus les mails dont le code a été relayé avec succès."""
    if not nums:
        return
    with imaplib.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT) as boite:
        boite.login(IMAP_USER, IMAP_PASSWORD)
        boite.select(IMAP_DOSSIER)
        for num in nums:
            if num:                                                     # 29/09 : un mail lu dans le Spam (salon commun) n'a pas de num ici
                boite.store(num, "+FLAGS", "\\Seen")


def rattacher(aliases, canal_id: str, par: str) -> int:
    """Rattache des adresses (alias) au salon qui recevra leurs codes — ce que fait `!alias ajouter`, sans commande.
    Utilisé par l'onboarding : les e-mails des comptes du clipper → son salon perso. Renvoie le nombre d'alias posés."""
    registre = _lire()
    n = 0
    for alias in [str(a).strip().lower() for a in aliases if a and "@" in str(a)]:
        if registre.get(alias, {}).get("canal_id") == str(canal_id):
            continue
        registre[alias] = {"canal_id": str(canal_id), "par": str(par), "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        n += 1
    if n:
        _ecrire(registre)
    return n


def detacher(aliases) -> int:
    """Retire des adresses du registre (les codes de ces boîtes ne sont plus routés nulle part). Utilisé par
    `!liberer` quand un clipper part. Renvoie le nombre d'alias retirés."""
    registre = _lire()
    n = 0
    for alias in [str(a).strip().lower() for a in aliases if a and "@" in str(a)]:
        if registre.pop(alias, None) is not None:
            n += 1
    if n:
        _ecrire(registre)
    return n


def ligne_code(t: dict) -> str:
    """La ligne postée dans Discord pour un code trouvé : jamais le corps du mail, seulement le code, l'adresse,
    le pseudo du compte si le mail le donne, l'âge du mail. Un code de récupération est nommé comme tel : c'est
    celui qu'Instagram attend pour « mot de passe oublié » ou pour faire appel après un ban (27/09)."""
    alias = t.get("alias") or "adresse inconnue"
    compte = f" · compte `@{t['compte']}`" if t.get("compte") else ""
    age = t.get("age_min")
    quand = "" if age is None else (" (à l'instant)" if age < 1 else f" (reçu il y a {age} min)")
    if t.get("type") == TYPE_RECUP:
        return (f"🛟 **Code de récupération {t.get('plateforme', 'Instagram')}** pour `{alias}`{compte}{quand}. "
                "C'est le code pour retrouver le compte ou faire appel. Copie-le d'un geste :\n```\n" + str(t['code']) + "\n```")
    # 28/09 (Gaëtan, Simon) : le code seul dans un bloc, il se copie d'un geste sur le téléphone
    return f"🔐 **Code {t.get('plateforme', 'Instagram')}** pour `{alias}`{compte}{quand}. Copie-le d'un geste :\n```\n{t['code']}\n```"


def _est_manager(membre, admin_ids) -> bool:
    """Admin, ou porteur du rôle Manager au nom EXACT (accents/casse/emoji ignorés). La sous-chaîne
    d'avant faisait d'un rôle « Community manager » ou « bot-manager » un manager."""
    if str(membre.id) in admin_ids:
        return True
    cibles = {_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")} - {""}   # 25/09 : le serveur dit « Manageur »
    return any(_cle(r.name) in cibles for r in getattr(membre, "roles", []))


async def commande(message, admin_ids, adresses_de_membre=None, alerter=None) -> bool:
    """`!alias ajouter <alias>` (dans le salon qui recevra les codes) · `!alias retirer <alias>` ·
    `!alias liste` · `!code <alias>` (recherche à la demande, 30 dernières minutes).
    Réservé aux admins et aux membres portant le rôle manager. Renvoie True si traité.
    `adresses_de_membre` (01/10) : fonction sans argument qui donne les adresses de l'auteur (salon commun).
    `alerter` (01/10) : coroutine qui poste une ligne au salon admin (clipper sans adresse connue au salon commun)."""
    texte = message.content.strip()
    if not texte.lower().startswith(("!alias", "!code") + COMMANDES_RECUP):
        return False
    registre = _lire()
    mots = texte.split()
    # 30/09 (Gaëtan : « la même commande pour faire appel, créer un compte ou se connecter ») : `!recup` et ses variantes
    # font exactement `!code` — tous les codes utiles, jamais ceux qui changent une information sensible.
    recup = False
    if mots[0].lower() in COMMANDES_RECUP:
        mots[0] = "!code"
    canal_id = str(message.channel.id) if message.guild is not None else ""
    manager = message.guild is not None and _est_manager(message.author, admin_ids)
    if canal_id and canal_id == salon_codes_id() and mots[0].lower() == "!code":
        # 29/09 : le salon commun. 01/10 (relecture) : le staff aussi y passe, `!code adresse` compris — plus jamais la liste
        # des codes de tout le monde ni un code en clair sans effacement dans un salon que tous les clippers lisent.
        adresse = mots[1].lower() if manager and len(mots) >= 2 and "@" in mots[1] else ""
        return await _commande_salon_commun(message, recup, manager, adresses_de_membre, adresse=adresse, alerter=alerter)
    # 01/10 (Gaëtan : « les codes Instagram se demandent UNIQUEMENT dans #🔐-code-instagram ») : ailleurs, un clipper qui
    # demande un code reçoit une seule ligne, le salon où le demander. Le staff garde `!code` partout.
    if not manager and mots[0].lower() == "!code":
        await message.reply(texte_salon_codes())
        return True
    miens = [a for a, v in registre.items() if canal_id and isinstance(v, dict) and v.get("canal_id") == canal_id]
    if not manager:
        await message.reply("Réservé aux managers (rôle « Manager ») et aux admins.")
        return True
    if not actif():
        await message.reply("Relais des codes éteint : `CODES_IMAP_USER` / `CODES_IMAP_PASSWORD` absents.")
        return True

    if mots[0].lower() == "!alias":
        action = mots[1].lower() if len(mots) > 1 else "liste"
        if action in ("ajouter", "add") and len(mots) > 2:
            for alias in [a.lower() for a in mots[2:] if "@" in a]:
                registre[alias] = {"canal_id": canal_id, "par": str(message.author.id),
                                   "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            _ecrire(registre)
            await message.reply(f"✅ Alias rattaché(s) à ce salon : {', '.join(a for a in mots[2:] if '@' in a)}. "
                                "Les codes Instagram/Facebook reçus sur ces adresses arriveront ici.")
        elif action in ("retirer", "remove") and len(mots) > 2:
            for alias in [a.lower() for a in mots[2:]]:
                registre.pop(alias, None)
            _ecrire(registre)
            await message.reply("🗑️ Retiré.")
        else:
            miens = [a for a, v in registre.items() if v.get("canal_id") == canal_id]
            await message.reply(("📮 Alias de ce salon : " + ", ".join(miens)) if miens else
                                "Aucun alias ici. `!alias ajouter prenom.xxx@icloud.com` pour en rattacher un.")
        return True

    # !code [alias] : sans alias, toutes les adresses rattachées à ce salon
    if len(mots) >= 2 and "@" in mots[1]:
        alias = mots[1].lower()
        proprietaire = registre.get(alias, {}).get("canal_id")
        if proprietaire != canal_id and str(message.author.id) not in admin_ids:
            await message.reply("Cet alias n'est pas rattaché à ce salon — `!alias ajouter` d'abord.")
            return True
        cibles = [alias]
    elif miens:
        cibles = miens
    else:
        nom = "!recup" if recup else "!code"
        await message.reply(f"Format : `{nom} alias@icloud.com` — je cherche le dernier code reçu "
                            f"({'6 h' if recup else '2 h'}). Dans un salon perso avec des adresses rattachées, `{nom}` tout court suffit.")
        return True
    fenetre = 120                                              # 30/09 : création, connexion et appel, 2 h

    def _filtrer(trouves):
        return [t for t in trouves if t["code"] and t["alias"] in cibles and (not recup or t.get("type") == TYPE_RECUP)]

    try:
        codes = _filtrer(await _imap(_lire_boite, False, None, fenetre))
    except Exception as erreur:
        journal.warning("IMAP : %s", _err(erreur))
        await message.reply("⚠️ Je n'arrive pas à lire la boîte mail. Réessaie dans 2 minutes. Si ça continue, dis-le à ton manager.")
        return True
    attente = None
    lecture_ok = True                                          # 01/10 : la DERNIÈRE lecture a-t-elle marché ?
    if not codes and ATTENTE_SEC > 0 and canal_id in _guets:
        await message.reply("⏳ Je guette déjà ton code : il s'affiche ici dès qu'il arrive. Pas besoin de retaper.")
        return True
    if not codes and ATTENTE_SEC > 0:                          # le mail met 10 s à 3 min : on guette avant de dire non
        _guets.add(canal_id)
        attente = await message.reply(f"⏳ Pas encore reçu. Je guette {max(1, ATTENTE_SEC // 60)} minute{'s' if ATTENTE_SEC >= 120 else ''} et je le mets ici "
                                      "tout seul. Pas besoin de retaper.")
        debut = time.monotonic()
        try:
            while time.monotonic() - debut < ATTENTE_SEC:
                await asyncio.sleep(ATTENTE_PAS)
                try:
                    codes = _filtrer(await _imap(_lire_boite, False, None, fenetre))
                    lecture_ok = True
                except Exception as erreur:
                    journal.warning("IMAP (attente) : %s", _err(erreur))
                    codes, lecture_ok = [], False
                if codes:
                    break
        finally:
            _guets.discard(canal_id)

    async def _dire(texte):
        if attente is not None and hasattr(attente, "edit"):
            try:
                await attente.edit(content=texte)
                return
            except Exception:                                  # noqa: BLE001 — message supprimé, on renvoie
                pass
        await message.reply(texte)

    if not codes and not lecture_ok:                           # 01/10 (Simon) : boîte illisible ≠ pas de code
        await _dire("⚠️ Je n'arrive pas à lire la boîte mail. Réessaie dans 2 minutes. Si ça continue, dis-le à ton manager.")
        return True
    if not codes:
        pour = f" pour `{cibles[0]}`" if len(cibles) == 1 and len(mots) >= 2 else " pour tes adresses"
        if recup:
            await _dire(f"Pas de code de récupération depuis 6 h{pour}. Sur Instagram : « Mot de passe oublié » "
                        "ou « Faire appel », choisis l'e-mail, puis retape `!recup`.")
        else:
            await _dire(f"Toujours pas de code{pour}. Sur Instagram, vérifie l'adresse e-mail, appuie sur « Renvoyer le code », "
                        "puis retape `!code`.")
        return True
    derniers = {}
    for t in codes:                                            # le plus récent par adresse ET par type (connexion / récupération)
        derniers[(t["alias"], t.get("type", TYPE_CONNEXION))] = t
    # La boucle poste aussi les codes non lus : un code donné ici est noté comme relayé et marqué lu, sinon il
    # arrivait deux fois (la commande, puis la boucle 45 s plus tard).
    # 01/10 (#ricardo, 30/09 : le même code posté deux fois « à l'instant ») : le contrôle ne jouait qu'après une attente, et
    # la boucle pouvait poster entre notre lecture et notre écriture. Maintenant : sous verrou, et un code posté il y a
    # moins de 10 min (par la boucle ou par un !code) n'est jamais reposté, attente ou pas.
    nouveaux = []
    async with _verrou():
        registre = _lire()
        deja = registre.setdefault("_relayes", {})
        lignes = []
        for t in derniers.values():
            cle_r = f"{t['alias']}|{t['code']}"
            if _recent(deja.get(cle_r)):
                lignes.append("✅ Ton code est posté juste au-dessus.")
                continue
            lignes.append(ligne_code(t))
            if t.get("num") and cle_r not in deja:
                nouveaux.append(t["num"])
            deja[cle_r] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await _dire("\n".join(lignes))
        _ecrire(registre)
    if nouveaux:
        try:
            await _imap(_marquer_lus, nouveaux, delai=IMAP_TIMEOUT * 2)
        except Exception as erreur:                             # noqa: BLE001
            journal.warning("Marquage lu après !code : %s", _err(erreur))
    return True


async def _alerter_sans_adresse(message, alerter) -> bool:
    """01/10 (relecture) : un clipper sans adresse connue tape `!code` au salon commun → une ligne au salon admin, une fois
    par clipper et par jour (clé `_sans_adresse` du registre). Vrai si l'équipe est prévenue (maintenant ou plus tôt)."""
    if alerter is None:
        return False
    uid = str(getattr(message.author, "id", ""))
    jour = datetime.now(timezone.utc).date().isoformat()
    registre = _lire()
    faits = registre.setdefault("_sans_adresse", {})
    if faits.get(uid) == jour:
        return True
    prenom = getattr(message.author, "display_name", "") or f"<@{uid}>"
    try:
        await alerter(f"🔐 `!code` : aucune adresse pour **{prenom}** (<@{uid}>) : sa fiche n'a aucun accès. "
                      "Ajoute ses comptes à sa fiche, puis réponds-lui dans son salon perso.")
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Alerte « aucune adresse » : %s", _err(erreur))
        return False
    faits[uid] = jour
    _ecrire(registre)
    return True


async def _commande_salon_commun(message, recup: bool, manager: bool = True, adresses_de_membre=None,
                                 adresse: str = "", alerter=None) -> bool:
    """`!code` / `!recup` dans le salon commun : les codes reçus dans les dernières minutes (boîte de réception et Spam),
    adresse masquée, le plus récent par adresse. Rien n'est marqué lu.
    01/10 : un clipper n'y reçoit que les codes de SES adresses (adresses_de_membre). Le message qui porte un code s'efface
    seul après EFFACER_MIN minutes. 01/10 (relecture : « chacun ses codes ») : le staff non plus ne voit plus tout ici —
    ses adresses à lui, ou `!code adresse` pour celle d'un clipper (`adresse`)."""
    if not actif():
        await message.reply("Relais des codes éteint : `CODES_IMAP_USER` / `CODES_IMAP_PASSWORD` absents.")
        return True
    adresses = set()
    if adresse:
        adresses = {adresse.strip().lower()}
    else:
        try:
            adresses = {str(a).strip().lower() for a in (adresses_de_membre() if adresses_de_membre else []) if a and "@" in str(a)}
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Adresses du clipper (salon commun) : %s", _err(erreur))
    if not adresses:
        if manager:
            await message.reply("Ici, chacun ses codes : je ne liste pas ceux de tout le monde.\n\n"
                                "Pour l'adresse d'un clipper : `!code adresse@icloud.com`.")
            return True
        # 01/10 (relecture : « Écris à Gaëtan sur WhatsApp » sortait de la règle 21) : l'équipe est prévenue au salon admin
        if await _alerter_sans_adresse(message, alerter):
            await message.reply("Je ne trouve pas ton adresse.\n\nL'équipe est prévenue : elle te répond dans ton salon perso.")
        else:
            await message.reply("Je ne trouve pas ton adresse.\n\nDis-le à ton manager dans ton salon perso.")
        return True
    fenetre = SALON_CODES_MINUTES                                       # 30/09 : une seule fenêtre, une seule commande
    dossiers = [IMAP_DOSSIER] + ([DOSSIER_SPAM] if DOSSIER_SPAM and DOSSIER_SPAM != IMAP_DOSSIER else [])

    def _filtrer(trouves):
        return [t for t in trouves if t["code"] and t.get("alias") in adresses
                and (not recup or t.get("type") == TYPE_RECUP)]

    async def _lire():
        return _filtrer(await _imap(_lire_boite, False, None, fenetre, dossiers))

    try:
        codes = await _lire()
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("IMAP (salon commun) : %s", _err(erreur))
        await message.reply("⚠️ Je n'arrive pas à lire la boîte mail. Réessaie dans 2 minutes.")
        return True
    # 01/10 : les codes n'arrivent plus tout seuls dans les salons perso (CODES_PUSH_SALON_PERSO) : le salon commun guette
    # aussi longtemps que `!code` le faisait en salon perso (ATTENTE_SEC), une seule fois par personne.
    duree = ATTENTE_SEC if not PUSH_SALON_PERSO else min(ATTENTE_SEC, 60)
    cle_guet = f"commun|{getattr(message.author, 'id', '')}"
    attente = None
    lecture_ok = True
    if not codes and duree > 0 and cle_guet in _guets:
        await message.reply("⏳ Je guette déjà ton code : il s'affiche ici dès qu'il arrive. Pas besoin de retaper.")
        return True
    if not codes and duree > 0:
        _guets.add(cle_guet)
        attente = await message.reply(f"⏳ Pas encore reçu. Je guette {max(1, duree // 60)} minute{'s' if duree >= 120 else ''} "
                                      "et je le mets ici tout seul. Pas besoin de retaper.")
        debut = time.monotonic()
        try:
            while time.monotonic() - debut < duree:
                await asyncio.sleep(ATTENTE_PAS)
                try:
                    codes = await _lire()
                    lecture_ok = True
                except Exception as erreur:                             # noqa: BLE001
                    journal.warning("IMAP (salon commun, attente) : %s", _err(erreur))
                    codes, lecture_ok = [], False
                if codes:
                    break
        finally:
            _guets.discard(cle_guet)

    async def _dire(texte, effacer=False):
        apres = EFFACER_MIN * 60 if effacer and EFFACER_MIN > 0 else None
        if attente is not None:
            try:
                await attente.edit(content=texte, delete_after=apres)
                return
            except Exception:                                           # noqa: BLE001
                pass
        await message.reply(texte, delete_after=apres)

    if not codes and not lecture_ok:                                    # 01/10 : boîte illisible ≠ pas de code
        await _dire("⚠️ Je n'arrive pas à lire la boîte mail. Réessaie dans 2 minutes.")
        return True
    if not codes:
        await _dire(f"Pas de code reçu depuis {fenetre} min{' sur cette adresse' if adresse else ' sur tes adresses'}.\n\n"
                    "Sur Instagram, appuie sur « Renvoyer le code », attends 30 secondes, puis retape `!code`.")
        return True
    derniers = {}
    for t in sorted(codes, key=lambda x: x.get("age_min", 0), reverse=True):
        derniers[(t["alias"], t.get("type", TYPE_CONNEXION))] = t          # le plus récent par adresse et par type
    lignes = [ligne_code_masquee(t) for t in sorted(derniers.values(), key=lambda x: x.get("age_min", 0))[:5]]
    if len(lignes) > 1:
        lignes.insert(0, f"{len(lignes)} codes sur cette adresse : connexion et récupération." if adresse else
                      f"{len(lignes)} codes sur tes adresses : prends celui de l'adresse que tu as donnée à Instagram.")
    if EFFACER_MIN > 0:
        lignes.append(f"-# Ce message s'efface dans {EFFACER_MIN} min.")
    await _dire(f"{message.author.mention}\n\n" + "\n\n".join(lignes), effacer=True)
    return True


async def boucle_codes(client, canal_admin_async, admin_ids):
    """Toutes les INTERVALLE secondes : les codes non lus partent dans le salon du manager
    propriétaire de l'alias ; alias inconnu → salon admin (rien ne se perd).
    01/10 : sauf CODES_PUSH_SALON_PERSO=1, rien ne part plus dans le salon perso d'un clipper ni à tous dans le salon
    commun : ces codes attendent `!code` au salon commun."""
    if not actif():
        journal.info("Relais codes 2FA désactivé (CODES_IMAP_USER absent)")
        return
    await client.wait_until_ready()
    pannes, alerte_faite = 0, False
    while not client.is_closed():
        try:
            trouves = await _imap(_lire_boite, True, None, 30)
            pannes = 0
            if alerte_faite:
                alerte_faite = False
                salon_a = await canal_admin_async()
                if salon_a is not None:
                    try:
                        await salon_a.send("✅ Relais des codes 2FA : boîte mail de nouveau joignable.")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            relayes = []
            async with _verrou():                                # 01/10 : jamais en même temps qu'un !code (doublon du 30/09)
                registre = _lire()
                deja = registre.setdefault("_relayes", {})       # 25/09 : un code posté deux fois (redéploiement, deux instances)
                limite = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
                for k in [k for k, v in deja.items() if str(v) < limite]:
                    deja.pop(k, None)
                if trouves:
                    journal.info("Relais 2FA : %d mail(s) Meta non lus, %d avec code", len(trouves), sum(1 for t in trouves if t["code"]))
                for t in trouves:
                    if t.get("type") == TYPE_SENSIBLE:                 # 30/09 : jamais relayé ; l'admin le sait, une fois
                        cle_s = f"sensible|{t.get('num')}|{t.get('alias')}"
                        if cle_s not in deja:
                            deja[cle_s] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                            _ecrire(registre)
                            salon_a = await canal_admin_async()
                            if salon_a is not None:
                                # 01/10 : « mot de passe changé » / « adresse e-mail modifiée » n'a pas de code, mais c'est pire
                                texte_s = (f"⛔ Instagram dit qu'une information a été **changée** sur `{_masquer(t.get('alias', ''))}` "
                                           f"(« {str(t.get('sujet', ''))[:80]} »). On ne change jamais le mot de passe ni l'e-mail : "
                                           "vérifie qui l'a fait." if t.get("changement") else
                                           f"⛔ Code de changement d'informations sensibles reçu pour `{_masquer(t.get('alias', ''))}` "
                                           f"(« {str(t.get('sujet', ''))[:80]} ») : **non transmis**. Si ce n'est pas toi, "
                                           "quelqu'un essaie de modifier ce compte.")
                                try:
                                    await salon_a.send(texte_s)
                                except (discord.Forbidden, discord.HTTPException):
                                    pass
                        if t.get("num"):
                            relayes.append(t["num"])
                        continue
                    if not t["code"]:
                        continue
                    cle_r = f"{t['alias']}|{t['code']}"
                    if cle_r in deja:                                # déjà posté : on le marque lu sans le reposter
                        relayes.append(t["num"])
                        continue
                    entree = registre.get(t["alias"]) if isinstance(registre.get(t["alias"]), dict) else {}
                    cible = entree.get("canal_id")
                    commun = (registre.get("_salon_codes") or {}).get("id")
                    # 01/10 (Gaëtan : « les codes se demandent UNIQUEMENT dans #🔐-code-instagram ») : plus de code poussé dans
                    # le salon perso d'un clipper (adresse rattachée par l'onboarding), ni affiché à tous dans le salon
                    # commun (adresse inconnue) : il reste disponible pour `!code` au salon commun, seulement pour son
                    # propriétaire. Les salons de manager rattachés par `!alias` reçoivent toujours les leurs.
                    if not PUSH_SALON_PERSO and (entree.get("par") == "onboarding" or (not cible and commun)):
                        if t.get("num"):
                            relayes.append(t["num"])
                        journal.info("Code %s pour %s gardé pour !code (salon commun)", t.get("type", TYPE_CONNEXION),
                                     _masquer(t.get("alias", "")))
                        continue
                    salon = client.get_channel(int(cible)) if cible else (client.get_channel(int(commun)) if commun else None)
                    if salon is None and not cible:
                        salon = await canal_admin_async()
                    if salon is None:
                        continue
                    texte = ligne_code(t)
                    if not cible and commun and str(getattr(salon, "id", "")) == str(commun):
                        texte = ligne_code_masquee(t)                   # 29/09 : alias inconnu → le salon commun, adresse masquée
                    elif not cible:
                        texte += "\n-# Alias non rattaché — un manager peut se l'attribuer : `!alias ajouter <alias>`."
                    try:
                        await salon.send(texte)
                        relayes.append(t["num"])
                        deja[cle_r] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        _ecrire(registre)
                        journal.info("Code %s relayé pour %s → salon %s", t.get("type", TYPE_CONNEXION), t["alias"] or "alias inconnu", getattr(salon, "name", salon.id))
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            if relayes:
                await _imap(_marquer_lus, relayes, delai=IMAP_TIMEOUT * 2)
        except Exception as erreur:                     # jamais tuer le bot pour un mail
            pannes += 1
            journal.warning("Boucle codes 2FA (%d de suite) : %s", pannes, _err(erreur))
            if pannes >= 5 and not alerte_faite:
                # 5 échecs de suite (~4 min) : les managers attendent des codes qui n'arrivent pas
                # sans que personne ne le sache — on le dit UNE fois, et on dit quand ça revient.
                alerte_faite = True
                salon_a = await canal_admin_async()
                if salon_a is not None:
                    try:
                        await salon_a.send(f"⚠️ **Relais des codes 2FA en panne** ({pannes} lectures échouées de suite) : "
                                           f"{type(erreur).__name__} — vérifie CODES_IMAP_USER / mot de passe d'application / "
                                           "IMAP activé. Les managers ne reçoivent plus les codes.")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
        await asyncio.sleep(INTERVALLE)
