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
"""

import asyncio
import email
import imaplib
import json
import os
import re
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
IMAP_TIMEOUT = int(os.environ.get("CODES_IMAP_TIMEOUT_SEC", "30"))
# Mots attendus dans le SUJET d'un mail de code (Meta en envoie aussi sur les connexions, les
# nouveautés, la sécurité…) : un mail sans l'un d'eux ne relaie jamais un nombre pris au hasard.
MOTS_SUJET = tuple(m.strip().lower() for m in os.environ.get(
    "CODES_MOTS_SUJET", "code,confirm,vérif,verif,connexion,login,sécurité,security,verify").split(",") if m.strip())
EXPEDITEURS = tuple(e.strip().lower() for e in os.environ.get(
    "CODES_EXPEDITEURS", "instagram.com,facebookmail.com,facebook.com,meta.com").split(",") if e.strip())

FICHIER_ALIAS = None            # injecté par bot_discord.py (volume persistant)

# Sous-chaînes cherchées côté serveur dans l'en-tête From (IMAP FROM) : courtes pour attraper les expéditeurs
# réécrits par iCloud, sans « meta » seul qui ramènerait Metricool.
MOTS_EXPEDITEUR = ("instagram", "facebook", "meta.com", "meta_com")
MOTIF_CODE = re.compile(r"(?<!\d)(?:FB-?)?(\d{5,8})(?!\d)")
MOTIF_ALIAS = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def actif() -> bool:
    return bool(IMAP_USER and IMAP_PASSWORD)


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
    if MOTS_SUJET and not any(m in sujet.lower() for m in MOTS_SUJET):
        return {"expediteur": expediteur, "alias": alias, "code": None, "sujet": sujet, "plateforme": plateforme}
    code = None
    for source in (sujet, _corps(msg)[:3000]):
        m = MOTIF_CODE.search(source)
        if m:
            code = m.group(0) if m.group(0).upper().startswith("FB") else m.group(1)
            break
    return {"expediteur": expediteur, "alias": alias, "code": code, "sujet": sujet, "plateforme": plateforme}


def _lire_boite(uniquement_non_lus=True, alias=None, minutes=30) -> list:
    """Bloquant (à appeler via to_thread) : les codes des mails Meta récents. Un mail n'est PLUS
    marqué lu ici : c'est le relais réussi qui le marque (_marquer_lus), sinon un code lu puis
    jamais posté (Discord en panne) était perdu — audit 10/09."""
    resultats = []
    with imaplib.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT) as boite:
        boite.login(IMAP_USER, IMAP_PASSWORD)
        boite.select(IMAP_DOSSIER)
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
            info["num"] = num
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


def _est_manager(membre, admin_ids) -> bool:
    """Admin, ou porteur du rôle Manager au nom EXACT (accents/casse/emoji ignorés). La sous-chaîne
    d'avant faisait d'un rôle « Community manager » ou « bot-manager » un manager."""
    if str(membre.id) in admin_ids:
        return True
    cibles = {_cle(ROLE_MANAGER_NOM), _cle("Manager"), _cle("Manageur")} - {""}   # 25/09 : le serveur dit « Manageur »
    return any(_cle(r.name) in cibles for r in getattr(membre, "roles", []))


async def commande(message, admin_ids) -> bool:
    """`!alias ajouter <alias>` (dans le salon qui recevra les codes) · `!alias retirer <alias>` ·
    `!alias liste` · `!code <alias>` (recherche à la demande, 30 dernières minutes).
    Réservé aux admins et aux membres portant le rôle manager. Renvoie True si traité."""
    texte = message.content.strip()
    if not texte.lower().startswith(("!alias", "!code")):
        return False
    registre = _lire()
    mots = texte.split()
    canal_id = str(message.channel.id) if message.guild is not None else ""
    miens = [a for a, v in registre.items() if canal_id and v.get("canal_id") == canal_id]
    manager = message.guild is not None and _est_manager(message.author, admin_ids)
    # 25/09 : dans son salon perso, le clipper tape `!code` tout court et reçoit le dernier code de SES adresses
    # (le message de livraison le lui promettait, la commande était réservée aux managers).
    if not manager and not (mots[0].lower() == "!code" and miens):
        await message.reply("Réservé aux managers (rôle « Manager ») et aux admins." if message.guild is not None else
                            "`!code` se tape dans ton salon perso sur le serveur, pas en message privé.")
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
        await message.reply("Format : `!code alias@icloud.com` — je cherche le dernier code reçu (2 h). "
                            "Dans un salon perso avec des adresses rattachées, `!code` tout court suffit.")
        return True
    try:
        trouves = await asyncio.wait_for(asyncio.to_thread(_lire_boite, False, None, 120), timeout=IMAP_TIMEOUT * 3)
    except Exception as erreur:
        journal.warning("IMAP : %s", erreur)
        await message.reply("⚠️ Boîte mail injoignable (identifiants, IMAP désactivé ou délai dépassé).")
        return True
    codes = [t for t in trouves if t["code"] and t["alias"] in cibles]
    if not codes:
        await message.reply(f"Aucun code reçu dans les 2 dernières heures pour {', '.join(f'`{a}`' for a in cibles)}. "
                            "Redemande le code sur Instagram, il arrive ici en moins d'une minute.")
    else:
        derniers = {}
        for t in codes:                                        # le plus récent par adresse
            derniers[t["alias"]] = t
        await message.reply("\n".join(f"🔐 **{t['plateforme']} — code pour `{a}` : `{t['code']}`**" for a, t in derniers.items()))
    return True


async def boucle_codes(client, canal_admin_async, admin_ids):
    """Toutes les INTERVALLE secondes : les codes non lus partent dans le salon du manager
    propriétaire de l'alias ; alias inconnu → salon admin (rien ne se perd)."""
    if not actif():
        journal.info("Relais codes 2FA désactivé (CODES_IMAP_USER absent)")
        return
    await client.wait_until_ready()
    pannes, alerte_faite = 0, False
    while not client.is_closed():
        try:
            trouves = await asyncio.wait_for(asyncio.to_thread(_lire_boite, True, None, 30), timeout=IMAP_TIMEOUT * 3)
            pannes = 0
            if alerte_faite:
                alerte_faite = False
                salon_a = await canal_admin_async()
                if salon_a is not None:
                    try:
                        await salon_a.send("✅ Relais des codes 2FA : boîte mail de nouveau joignable.")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            registre = _lire()
            relayes = []
            deja = registre.setdefault("_relayes", {})           # 25/09 : un code posté deux fois (redéploiement, deux instances)
            limite = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
            for k in [k for k, v in deja.items() if str(v) < limite]:
                deja.pop(k, None)
            if trouves:
                journal.info("Relais 2FA : %d mail(s) Meta non lus, %d avec code", len(trouves), sum(1 for t in trouves if t["code"]))
            for t in trouves:
                if not t["code"]:
                    continue
                cle_r = f"{t['alias']}|{t['code']}"
                if cle_r in deja:                                    # déjà posté : on le marque lu sans le reposter
                    relayes.append(t["num"])
                    continue
                cible = registre.get(t["alias"], {}).get("canal_id")
                salon = client.get_channel(int(cible)) if cible else await canal_admin_async()
                if salon is None:
                    continue
                texte = f"🔐 **{t['plateforme']} — code pour `{t['alias'] or 'alias inconnu'}` : `{t['code']}`**"
                if not cible:
                    texte += "\n-# Alias non rattaché — un manager peut se l'attribuer : `!alias ajouter <alias>`."
                try:
                    await salon.send(texte)
                    relayes.append(t["num"])
                    deja[cle_r] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    _ecrire(registre)
                    journal.info("Code 2FA relayé pour %s → salon %s", t["alias"] or "alias inconnu", getattr(salon, "name", salon.id))
                except (discord.Forbidden, discord.HTTPException):
                    pass
            if relayes:
                await asyncio.wait_for(asyncio.to_thread(_marquer_lus, relayes), timeout=IMAP_TIMEOUT * 2)
        except Exception as erreur:                     # jamais tuer le bot pour un mail
            pannes += 1
            journal.warning("Boucle codes 2FA (%d de suite) : %s", pannes, erreur)
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
