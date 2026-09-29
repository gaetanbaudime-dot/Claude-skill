"""Bans Instagram vus par les mails (29/09, Gaëtan : « pour les comptes bannis je veux plus de réactivité. Dès que tu vois un
compte vert inaccessible, note-le en BAN. Ensuite trouve un moyen de chopper ces mails afin de savoir mes bans et de m'envoyer
un push sur Telegram ou Discord »).

Quand Instagram suspend un compte, il écrit « Action requise sur votre compte, <pseudo> » (« Votre compte Instagram a été
suspendu… vous avez jusqu'au … pour faire appel ») à l'adresse du compte : l'alias iCloud qui renvoie vers la boîte Gmail que
le relais des codes lit déjà (CODES_IMAP_*). Ces mails tombent souvent dans le Spam de Gmail : on lit INBOX **et** [Gmail]/Spam,
en lecture seule (BODY.PEEK, rien n'est marqué lu, rien n'est déplacé). Toutes les BANS_INTERVALLE_SEC (10 min) : les mails de
suspension des BANS_JOURS derniers jours pas encore traités → la ligne du classeur (retrouvée par le pseudo, sinon par l'alias
du mail) passe BAN, `bans_auto` retient le ban (le scan rend WARMUP si le compte réapparaît après appel), et un push part sur
Telegram et dans le salon admin. Du mail, on ne garde que le pseudo, l'alias et la date : jamais le corps."""
import asyncio
import email
import email.utils
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from html import unescape

import codes_2fa
import google_api
import onboarding
import telegram

journal = logging.getLogger("bot.bans_mail")
INTERVALLE = int(os.environ.get("BANS_INTERVALLE_SEC", "180") or 180)
# 29/09 (Gaëtan : « fais le filtre Gmail pour moi… uniquement les mails FB et IG importants : sign in, sign up, ban, appel,
# informations importantes, demande de vérification. Je veux pas la pub ») : les mails Meta IMPORTANTS trouvés dans le Spam
# sont remis dans la boîte de réception (UID MOVE), et la pub Meta trouvée dans la boîte de réception repart dans le Spam.
DEPLACER_SPAM = os.environ.get("BANS_DEPLACER_SPAM", "1").strip() != "0"
PUB_VERS_SPAM = os.environ.get("BANS_PUB_VERS_SPAM", "1").strip() != "0"
DOSSIER_SPAM = os.environ.get("BANS_DOSSIER_SPAM", "[Gmail]/Spam").strip() or "[Gmail]/Spam"
MOTS_IMPORTANT = ("code", "confirm", "verif", "verify", "login", "log in", "connexion", "connecter", "sign in", "sign up",
                  "inscription", "bienvenue", "welcome", "suspend", "desactiv", "disabled", "restre", "restrict", "action requise",
                  "action required", "appel", "appeal", "important", "securit", "security", "mot de passe", "password", "recover",
                  "recup", "reset", "reinitialis", "identit", "de retour", "back on", "demande", "request", "parametre", "settings",
                  "compte", "account", "profil")
MOTS_PUB = ("decouvrez", "ont partage", "a partage", "commence a vous suivre", "started following", "veut vous suivre",
            "wants to follow", "ajoute du contenu", "rattrapez", "regardez les reels", "suggestion", "shared", "you may know",
            "manque", "nouveaute", "tendance", "trending", "recap", "highlights", "en direct", "is live")
PREFIXES_PUB = ("posts-recap", "follow-sugg", "stories-rec", "digest", "news", "marketing", "promo", "reels-recap", "live-")
MOTS_RETOUR = ("de retour sur instagram", "back on instagram", "de nouveau utiliser", "can use", "again")
JOURS = int(os.environ.get("BANS_JOURS", "3") or 3)
DOSSIERS = tuple(d.strip() for d in os.environ.get("BANS_IMAP_DOSSIERS", "INBOX,[Gmail]/Spam").split(",") if d.strip())
MOTS_EXPEDITEUR = ("instagram", "facebookmail")
# Le sujet décide, le corps confirme : « Action requise sur votre compte, pseudo » seul peut aussi servir à d'autres avis Meta.
SUJETS_BAN = ("action requise sur votre compte", "action required on your account", "suspendu", "suspended", "désactivé",
              "desactive", "disabled", "compte restreint", "account restricted")
MOTS_CORPS = ("a été suspendu", "a ete suspendu", "been suspended", "we suspended", "we've suspended", "nous avons suspendu",
              "a été désactivé", "been disabled", "we disabled", "perdrez l'accès", "perdrez l’accès", "lose access")
MOTIF_SUJET_COMPTE = re.compile(r",\s*@?([A-Za-z0-9][A-Za-z0-9._]{0,40})\s*$")
MOTIF_CORPS_COMPTE = re.compile(r"(?:Bonjour|Hi|Hello|accès à|access to)\s+@?([A-Za-z0-9][A-Za-z0-9._]{0,40})\s*[,.!\s|]")
MOTIF_ADRESSE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_deps: dict = {}


def _plat(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def categorie(sujet: str, expediteur: str = "") -> str:
    """« important » (codes, connexion, inscription, ban, appel, sécurité, paramètres…), « pub » (récaps, suggestions, qui
    vous suit…) ou « autre ». La pub se reconnaît d'abord à l'expéditeur (posts-recap, follow-suggestions, stories-recap),
    puis au sujet ; un mot important dans le sujet l'emporte toujours (« Découvrez … » n'est jamais un code)."""
    s, e = _plat(sujet), _plat(expediteur)
    local = e.split("@")[0]
    pub_exp = any(local.startswith(p) for p in PREFIXES_PUB)
    pub_sujet = any(m in s for m in MOTS_PUB)
    fort = any(m in s for m in MOTS_IMPORTANT if m not in ("compte", "account", "profil"))
    if fort:
        return "important"
    if pub_exp or pub_sujet:
        return "pub"
    if any(m in s for m in ("compte", "account", "profil")):
        return "important"
    return "autre"


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER_BANS, canal_admin, est_staff, normaliser, etat_scan (lecture/écriture du fichier
    des états : bans_auto), lire_comptes (défaut onboarding.lire_comptes)."""
    _deps.update(deps)


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER_BANS"], {}) if _deps.get("lire_json") else {}
    d.setdefault("vus", {}); d.setdefault("bans", [])
    return d


def _ecrire(d: dict):
    if _deps.get("ecrire_json"):
        _deps["ecrire_json"](_deps["FICHIER_BANS"], d)


def _texte(msg) -> str:
    """Le texte du mail (text/plain, sinon le HTML dépouillé), 6 000 caractères."""
    morceaux = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        try:
            brut = part.get_payload(decode=True) or b""
            t = brut.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:                                               # noqa: BLE001
            continue
        if part.get_content_type() == "text/html":
            t = re.sub(r"<[^>]+>", " ", t)
        morceaux.append(unescape(t))
    return re.sub(r"\s+", " ", " ".join(morceaux))[:6000]


def extraire(msg) -> dict | None:
    """{pseudo, alias, sujet, date, id} pour un mail de suspension Instagram, None pour tout autre mail Meta (connexion,
    code, paramètres, nouveautés…)."""
    sujet = str(make_header(decode_header(msg.get("Subject") or ""))).strip()
    s = sujet.lower()
    genre = "ban"
    if any(m in s for m in ("de retour sur instagram", "back on instagram")):
        genre = "retour"                                                 # appel accepté : « Vous pouvez de nouveau utiliser … »
    elif not any(m in s for m in SUJETS_BAN):
        return None
    corps = _texte(msg)
    c = corps.lower()
    if genre == "ban":
        fort = any(m in s for m in ("suspendu", "suspended", "désactivé", "desactive", "disabled", "restreint", "restricted"))
        if not fort and not any(m in c for m in MOTS_CORPS):
            return None
    m = MOTIF_SUJET_COMPTE.search(sujet)
    pseudo = m.group(1) if m else ""
    if not pseudo:
        m = MOTIF_CORPS_COMPTE.search(corps[:800])
        pseudo = m.group(1) if m else ""
    pseudo = pseudo.rstrip(".").lower()
    m_al = MOTIF_ADRESSE.search(str(msg.get("To") or "") + " " + str(msg.get("Delivered-To") or ""))
    alias = m_al.group(0).lower() if m_al else ""
    try:
        date = email.utils.parsedate_to_datetime(msg.get("Date")).astimezone(timezone.utc)
    except Exception:                                                   # noqa: BLE001
        date = datetime.now(timezone.utc)
    ident = (msg.get("Message-ID") or "").strip() or f"{date.isoformat(timespec='minutes')}|{sujet}"
    return {"pseudo": pseudo, "alias": alias, "sujet": sujet[:120], "date": date.isoformat(timespec="minutes"), "id": ident, "type": genre}


def _lire_boite(jours: int = JOURS) -> list:
    """Bloquant (à appeler via to_thread) : les mails de suspension Instagram des `jours` derniers jours, INBOX et Spam.
    Rien n'est marqué lu (BODY.PEEK) ; dans le Spam, les mails Meta sont remis dans INBOX (le filtre Gmail que le bot fait
    lui-même). Le corps n'est lu que pour confirmer le mot « suspendu » et trouver le pseudo."""
    out, vus = [], set()
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%d-%b-%Y")
    with imaplib.IMAP4_SSL(codes_2fa.IMAP_HOST, timeout=codes_2fa.IMAP_TIMEOUT) as boite:
        boite.login(codes_2fa.IMAP_USER, codes_2fa.IMAP_PASSWORD)
        for dossier in DOSSIERS:
            spam = dossier.upper() != "INBOX"
            bouge = (spam and DEPLACER_SPAM) or (not spam and PUB_VERS_SPAM)
            try:
                ok, _ = boite.select(dossier, readonly=not bouge)
            except imaplib.IMAP4.error:
                ok = "NO"
            if ok != "OK":
                journal.warning("Bans par mail : dossier %s illisible", dossier)
                continue
            uids = set()
            for mot in MOTS_EXPEDITEUR:
                ok, ids = boite.uid("SEARCH", None, f'(SINCE {depuis} FROM "{mot}")')
                if ok == "OK" and ids and ids[0]:
                    uids.update(ids[0].split())
            a_remonter, a_descendre = [], []
            for uid in sorted(uids, key=int)[-120:]:
                ok, brut = boite.uid("FETCH", uid, "(BODY.PEEK[]<0.30000>)")
                if ok != "OK" or not brut or not brut[0]:
                    continue
                msg = email.message_from_bytes(brut[0][1])
                sujet = str(make_header(decode_header(msg.get("Subject") or ""))).strip()
                cat = categorie(sujet, str(msg.get("From") or ""))
                if spam and cat == "important":
                    a_remonter.append(uid)
                elif not spam and cat == "pub":
                    a_descendre.append(uid)
                info = extraire(msg)
                if info and info["id"] not in vus:
                    vus.add(info["id"])
                    info["dossier"] = dossier
                    out.append(info)
            for cibles, destination, libelle in ((a_remonter if spam and DEPLACER_SPAM else [], "INBOX", "important(s) remis dans la boîte de réception"),
                                                 (a_descendre if not spam and PUB_VERS_SPAM else [], DOSSIER_SPAM, "pub renvoyé(s) dans le Spam")):
                deplaces = 0
                for uid in cibles:
                    try:
                        if boite.uid("MOVE", uid, destination)[0] == "OK":
                            deplaces += 1
                    except imaplib.IMAP4.error as erreur:
                        journal.warning("Bans par mail : déplacement depuis %s : %s", dossier, erreur)
                        break
                if deplaces:
                    journal.info("Bans par mail : %d mail(s) Meta %s (depuis %s)", deplaces, libelle, dossier)
    return out


def associer(t: dict, comptes: list) -> dict | None:
    """La ligne du classeur visée par le mail : le pseudo d'abord, sinon l'alias (l'adresse du compte) — un compte renommé
    garde son adresse. Une ligne déjà BAN passe après une ligne vivante quand le pseudo est en double."""
    pseudo, alias = t.get("pseudo", ""), t.get("alias", "")
    candidats = [c for c in comptes if pseudo and c.get("handle", "").lower().lstrip("@") == pseudo] or \
                [c for c in comptes if alias and (c.get("mail") or "").strip().lower() == alias]
    if not candidats:
        return None
    return sorted(candidats, key=lambda c: (_n(c.get("etat")) == "ban", int(c.get("ligne") or 0)))[0]


def _quand(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def ligne_push(t: dict, c: dict | None, ecrit: bool) -> str:
    """Une ligne par ban : le pseudo, le clipper, la créatrice, le numéro de mail, ce qui a été fait."""
    pseudo = f"@{t['pseudo']}" if t.get("pseudo") else (t.get("alias") or "compte inconnu")
    if t.get("type") == "retour":
        qui = "" if c is None else f" · {str(c.get('gerant') or '').split()[0] if str(c.get('gerant') or '').strip() else 'sans gérant'} · {c.get('onglet') or '?'}" + (f" · mail n° {c['numero']}" if c.get("numero") else "")
        etat = "" if c is None else f" · ligne {c.get('etat') or '?'} dans le classeur, à toi de la remettre WARMUP si tu le reprends"
        return f"✅ {pseudo} — de retour sur Instagram, appel accepté ({_quand(t['date'])}){qui}{etat}"
    if c is None:
        return f"🚫 {pseudo} — suspendu ({_quand(t['date'])}), hors classeur (alias inconnu)"
    gerant = str(c.get("gerant") or "").split()[0] if str(c.get("gerant") or "").strip() else "sans gérant"
    numero = f" · mail n° {c['numero']}" if c.get("numero") else ""
    fait = "ligne passée BAN" if ecrit else "déjà BAN dans le classeur"
    return f"🚫 {pseudo} — suspendu ({_quand(t['date'])}) · {gerant} · {c.get('onglet') or c.get('creatrice') or '?'}{numero} · {fait}"


async def traiter(trouves: list | None = None) -> dict:
    """Un passage : les mails de suspension pas encore vus → BAN dans le classeur + push. Renvoie {nouveaux, ecrits, lignes}."""
    bilan = {"nouveaux": 0, "ecrits": 0, "lignes": []}
    if trouves is None:
        if not (codes_2fa.actif() and onboarding.actif()):
            return bilan
        trouves = await asyncio.wait_for(asyncio.to_thread(_lire_boite, JOURS), timeout=codes_2fa.IMAP_TIMEOUT * 4)
    d = _lire()
    nouveaux = [t for t in trouves if t["id"] not in d["vus"]]
    if not nouveaux:
        return bilan
    comptes = await (_deps.get("lire_comptes") or onboarding.lire_comptes)()
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    etat_scan = _deps["etat_scan"]() if _deps.get("etat_scan") else None
    for t in sorted(nouveaux, key=lambda x: x["date"]):
        c = associer(t, comptes)
        ecrit = False
        if t.get("type") == "retour":                                   # appel accepté : signalé, jamais réécrit (règle BAN de Gaëtan)
            d["vus"][t["id"]] = t["date"]
            bilan["nouveaux"] += 1
            bilan["lignes"].append(ligne_push(t, c, False))
            continue
        if c is not None and _n(c.get("etat")) != "ban":
            try:
                await google_api.sheets_ecrire(onboarding.CLASSEUR_LOGINS_ID, onboarding.cellule(c, "etat"), [["BAN"]])
                c["etat"] = "BAN"; ecrit = True
                if etat_scan is not None and c.get("handle"):
                    etat_scan.setdefault("bans_auto", {})[c["handle"].lower()] = jour
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Bans par mail : BAN de %s non écrit : %s", t.get("pseudo"), erreur)
                continue                                                # réessayé au prochain passage (mail pas marqué vu)
        d["vus"][t["id"]] = t["date"]
        d["bans"].append({"pseudo": t.get("pseudo"), "date": t["date"], "gerant": (c or {}).get("gerant", ""),
                          "onglet": (c or {}).get("onglet", ""), "numero": (c or {}).get("numero", ""), "ecrit": ecrit})
        bilan["nouveaux"] += 1; bilan["ecrits"] += int(ecrit)
        bilan["lignes"].append(ligne_push(t, c, ecrit))
    if etat_scan is not None and bilan["ecrits"] and _deps.get("ecrire_etat_scan"):
        _deps["ecrire_etat_scan"](etat_scan)
    limite = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    d["vus"] = {k: v for k, v in d["vus"].items() if v >= limite}
    d["bans"] = d["bans"][-300:]
    _ecrire(d)
    if bilan["lignes"]:
        texte = "\n".join(bilan["lignes"])
        journal.info("Bans par mail : %d nouveau(x), %d ligne(s) passée(s) BAN", bilan["nouveaux"], bilan["ecrits"])
        await telegram.envoyer_telegram(texte)
        if _deps.get("canal_admin"):
            try:
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await canal.send(texte[:1900])
            except Exception as erreur:                                  # noqa: BLE001
                journal.warning("Bans par mail : salon admin : %s", erreur)
    return bilan


async def boucle(client):
    """Toutes les INTERVALLE secondes, dès le démarrage."""
    if not codes_2fa.actif():
        journal.info("Bans par mail désactivés (CODES_IMAP_USER absent)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await traiter()
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Bans par mail : %s", erreur)
        await asyncio.sleep(INTERVALLE)


async def commande(message, texte: str) -> bool:
    """`!bans [jours]` : passage immédiat puis la liste des bans vus par mail sur `jours` jours (7 par défaut)."""
    mots = texte.split()
    if not mots or mots[0].lower() != "!bans":
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if not codes_2fa.actif():
        await message.reply("Bans par mail éteints : `CODES_IMAP_USER` / `CODES_IMAP_PASSWORD` absents.")
        return True
    jours = int(mots[1]) if len(mots) > 1 and mots[1].isdigit() else 7
    try:
        bilan = await traiter()
    except Exception as erreur:                                          # noqa: BLE001
        await message.reply(f"Boîte mail illisible : {erreur}")
        return True
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
    recents = [b for b in _lire()["bans"] if b.get("date", "") >= depuis]
    if not recents:
        await message.reply(f"Aucun mail de suspension Instagram sur {jours} jours ({bilan['nouveaux']} nouveau(x) à l'instant).")
        return True
    lignes = [f"🚫 Bans vus par mail sur {jours} jours : {len(recents)} ({bilan['nouveaux']} nouveau(x) à l'instant)"]
    for b in sorted(recents, key=lambda x: x["date"], reverse=True)[:30]:
        g = str(b.get("gerant") or "").split()[0] if str(b.get("gerant") or "").strip() else "hors classeur"
        lignes.append(f"• {_quand(b['date'])} @{b.get('pseudo') or '?'} · {g} · {b.get('onglet') or '?'}"
                      + (f" · n° {b['numero']}" if b.get("numero") else ""))
    await message.reply("\n".join(lignes)[:1900])
    return True
