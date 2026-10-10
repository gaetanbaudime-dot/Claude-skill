"""Bans Instagram vus par les mails (29/09, Gaëtan : « pour les comptes bannis je veux plus de réactivité. Dès que tu vois un
compte vert inaccessible, note-le en BAN. Ensuite trouve un moyen de chopper ces mails afin de savoir mes bans et de m'envoyer
un push sur Telegram ou Discord »).

Quand Instagram suspend un compte, il écrit « Action requise sur votre compte, <pseudo> » (« Votre compte Instagram a été
suspendu… vous avez jusqu'au … pour faire appel ») à l'adresse du compte : l'alias iCloud qui renvoie vers la boîte Gmail des
codes. 10/10 : ce module n'ouvre plus de connexion IMAP. Il s'abonne au lecteur UNIQUE de codes_2fa (UID, IDLE) : chaque
nouveau mail Meta lui est passé une fois (recevoir), boîte de réception et Spam ; le tri (pub Meta → Spam, mails Meta
importants du Spam → boîte de réception) est fait par ce même lecteur (destination). Un mail n'est retenu que si l'ADRESSE de
l'expéditeur est Meta (le nom affiché ne compte plus : « Action requise… <pseudo d'un autre> » écrit par un clipper ne passe
plus un compte en BAN). Les mails de suspension attendent dans une file ; toutes les BANS_INTERVALLE_SEC (ou dès qu'un mail
arrive) : la ligne du classeur (retrouvée par le pseudo, sinon par l'alias) passe BAN, `bans_auto` retient le ban (le scan rend
WARMUP si le compte réapparaît après appel), et un push part sur Telegram et dans le salon admin. Du mail, on ne garde que le
pseudo, l'alias et la date : jamais le corps."""
import asyncio
import email
import email.utils
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

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
# Le sujet décide, le corps confirme : « Action requise sur votre compte, pseudo » seul peut aussi servir à d'autres avis Meta.
SUJETS_BAN = ("action requise sur votre compte", "action required on your account", "suspendu", "suspended", "désactivé",
              "desactive", "disabled", "compte restreint", "account restricted")
MOTS_CORPS = ("a été suspendu", "a ete suspendu", "been suspended", "we suspended", "we've suspended", "nous avons suspendu",
              "a été désactivé", "been disabled", "we disabled", "perdrez l'accès", "perdrez l’accès", "lose access")
MOTIF_SUJET_COMPTE = re.compile(r",\s*@?([A-Za-z0-9][A-Za-z0-9._]{0,40})\s*$")
MOTIF_CORPS_COMPTE = re.compile(r"(?:Bonjour|Hi|Hello|accès à|access to)\s+@?([A-Za-z0-9][A-Za-z0-9._]{0,40})\s*[,.!\s|]")
MOTIF_ADRESSE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_deps: dict = {}
_en_attente: dict = {}                                                  # 10/10 : id du mail → info, en attente de traiter()
_evenement = (None, None)


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
    """Le texte du mail (text/plain, sinon le HTML converti : CSS et scripts retirés), 6 000 caractères."""
    return re.sub(r"\s+", " ", codes_2fa.texte_du_mail(msg))[:6000]


def extraire(msg) -> dict | None:
    """{pseudo, alias, sujet, date, id} pour un mail de suspension Instagram, None pour tout autre mail (connexion, code,
    paramètres, nouveautés…). 10/10 : l'ADRESSE de l'expéditeur doit être Meta, jamais le seul nom affiché."""
    if not codes_2fa.expediteur_meta(msg.get("From")):
        return None
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


def destination(dossier: str, sujet: str, expediteur: str = ""):
    """Le tri du 29/09, appliqué par le lecteur unique de codes_2fa sur chaque mail Meta : un mail important trouvé dans le
    Spam remonte dans la boîte de réception, la pub Meta de la boîte de réception part dans le Spam. None = on ne bouge rien."""
    spam = dossier.upper() != "INBOX"
    cat = categorie(sujet, expediteur)
    if spam and DEPLACER_SPAM and cat == "important":
        return "INBOX"
    if not spam and PUB_VERS_SPAM and cat == "pub":
        return DOSSIER_SPAM
    return None


def recevoir(msg, dossier: str = "INBOX"):
    """Appelé par le lecteur unique pour chaque nouveau mail Meta : un mail de suspension (ou de retour) entre dans la file."""
    info = extraire(msg)
    if info is None:
        return
    info["dossier"] = dossier
    _en_attente[info["id"]] = info
    evenement = _evenement[1]
    if evenement is not None:
        evenement.set()


def abonner():
    """S'abonne au lecteur unique (idempotent) : la file et le tri."""
    codes_2fa.abonner(recevoir, trieur=destination)


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
        limite_file = (datetime.now(timezone.utc) - timedelta(days=JOURS)).isoformat(timespec="minutes")
        for cle in [k for k, v in _en_attente.items() if str(v.get("date", "")) < limite_file]:
            _en_attente.pop(cle, None)                                  # plus vieux que BANS_JOURS : oublié
        trouves = list(_en_attente.values())                            # 10/10 : la file du lecteur unique, plus d'IMAP ici
    d = _lire()
    for t in trouves:
        if t["id"] in d["vus"]:
            _en_attente.pop(t["id"], None)
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
    for t in nouveaux:                                                  # traité : hors de la file (un BAN non écrit y reste)
        if t["id"] in d["vus"]:
            _en_attente.pop(t["id"], None)
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
    """Dès le démarrage : abonné au lecteur unique, puis la file traitée dès qu'un mail de suspension arrive, au plus tard
    toutes les INTERVALLE secondes. Aucune connexion IMAP ici (10/10)."""
    global _evenement
    if not codes_2fa.actif():
        journal.info("Bans par mail désactivés (CODES_IMAP_USER absent)")
        return
    abonner()
    _evenement = (asyncio.get_running_loop(), asyncio.Event())
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await traiter()
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Bans par mail : %s", erreur)
        evenement = _evenement[1]
        try:
            await asyncio.wait_for(evenement.wait(), timeout=INTERVALLE)
        except asyncio.TimeoutError:
            pass
        evenement.clear()


async def commande(message, texte: str) -> bool:
    """`!bans [jours]` : la file traitée tout de suite, puis la liste des bans vus par mail sur `jours` jours (7 par défaut)."""
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
        await message.reply(f"Bans par mail : {erreur}")
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
