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
    if not any(d in expediteur for d in EXPEDITEURS):
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
        critere = f'(UNSEEN SINCE {depuis})' if uniquement_non_lus else f'(SINCE {depuis})'
        ok, ids = boite.search(None, critere)
        if ok != "OK" or not ids or not ids[0]:
            return []
        for num in ids[0].split()[-40:]:
            ok, brut = boite.fetch(num, "(BODY.PEEK[])")
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


def _est_manager(membre, admin_ids) -> bool:
    """Admin, ou porteur du rôle Manager au nom EXACT (accents/casse/emoji ignorés). La sous-chaîne
    d'avant faisait d'un rôle « Community manager » ou « bot-manager » un manager."""
    if str(membre.id) in admin_ids:
        return True
    cible = _cle(ROLE_MANAGER_NOM)
    return bool(cible) and any(_cle(r.name) == cible for r in getattr(membre, "roles", []))


async def commande(message, admin_ids) -> bool:
    """`!alias ajouter <alias>` (dans le salon qui recevra les codes) · `!alias retirer <alias>` ·
    `!alias liste` · `!code <alias>` (recherche à la demande, 30 dernières minutes).
    Réservé aux admins et aux membres portant le rôle manager. Renvoie True si traité."""
    texte = message.content.strip()
    if not texte.lower().startswith(("!alias", "!code")):
        return False
    if message.guild is None or not _est_manager(message.author, admin_ids):
        await message.reply("Réservé aux managers (rôle « Manager ») et aux admins.")
        return True
    if not actif():
        await message.reply("Relais des codes éteint : `CODES_IMAP_USER` / `CODES_IMAP_PASSWORD` absents.")
        return True
    registre = _lire()
    mots = texte.split()
    canal_id = str(message.channel.id)

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

    # !code <alias>
    if len(mots) < 2 or "@" not in mots[1]:
        await message.reply("Format : `!code alias@icloud.com` — je cherche le dernier code reçu (30 min).")
        return True
    alias = mots[1].lower()
    proprietaire = registre.get(alias, {}).get("canal_id")
    if proprietaire != canal_id and str(message.author.id) not in admin_ids:
        await message.reply("Cet alias n'est pas rattaché à ce salon — `!alias ajouter` d'abord.")
        return True
    try:
        trouves = await asyncio.wait_for(asyncio.to_thread(_lire_boite, False, alias, 30), timeout=IMAP_TIMEOUT * 3)
    except Exception as erreur:
        journal.warning("IMAP : %s", erreur)
        await message.reply("⚠️ Boîte mail injoignable (identifiants, IMAP désactivé ou délai dépassé).")
        return True
    codes = [t for t in trouves if t["code"]]
    if not codes:
        await message.reply(f"Aucun code reçu pour `{alias}` dans les 30 dernières minutes. "
                            "Redemande le code sur Instagram, il arrive ici en moins d'une minute.")
    else:
        dernier = codes[-1]
        await message.reply(f"🔐 **{dernier['plateforme']} — code pour `{alias}` : `{dernier['code']}`**")
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
            for t in trouves:
                if not t["code"]:
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
