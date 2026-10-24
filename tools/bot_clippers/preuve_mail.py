"""Comptes créés prouvés par les mails d'Instagram (24/10/2026).

Gaëtan (24/10, « MAJ serveur, bot, assistant ») : le point du matin listait Esperance, Moutakabirou et Pierre en « Compte 1 pas
créé » (avertis pour une sortie) alors qu'ils avaient créé leur compte : Esperance le disait à l'assistant dès le 19/10, Pierre
recevait des mails d'Instagram adressés à son compte. Ils n'avaient pas appuyé sur « ✅ Compte 1 créé », et le pseudo pris n'était
pas toujours celui prévu, donc le scan ne le voyait pas.

Un mail d'Instagram qui SALUE un compte (« Bonjour <pseudo>, », « Hi <pseudo>, ») envoyé à l'adresse de l'agence d'un compte
prouve que ce compte existe, sous ce pseudo. Ce module s'abonne au lecteur unique des codes (codes_2fa.abonner, comme
bans_mail) et, quand ce mail arrive sur l'adresse du compte n d'un clipper dont l'étape n est ouverte et pas fermée :
  - le pseudo prévu est remplacé par le vrai s'il diffère (la même fonction que `!pseudo`) ;
  - l'étape n se ferme comme à l'appui du bouton (profil, warm-up, et le compte suivant 48 h après) ;
  - une ligne part au salon admin.
Jamais pour un compte repris d'un sortant (il existait déjà), jamais pour un mail plus ancien que l'ouverture de l'étape,
jamais deux fois pour le même mail. Du mail, on ne garde que l'adresse, le pseudo et la date : jamais le corps ni un code.
PREUVE_MAIL=0 sur Railway coupe tout."""
import asyncio
import email.utils
import logging
import os
from datetime import datetime, timezone

import codes_2fa

journal = logging.getLogger("bot.preuve_mail")
ACTIF = os.environ.get("PREUVE_MAIL", "1").strip() != "0"
_deps = {}
_EN_COURS = set()


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER ; proprietaire(alias) → dict ou None ; renommer(uid, n, pseudo) → (ancien, raison) ;
    fermer(uid, n) → bool ; admin(texte)."""
    _deps.update(deps or {})


def abonner():
    if ACTIF:
        codes_2fa.abonner(recevoir)


def _date(msg):
    try:
        d = email.utils.parsedate_to_datetime(msg.get("Date"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except Exception:                                                   # noqa: BLE001
        return None


def lire_mail(msg):
    """(adresse, pseudo, date) d'un mail d'Instagram qui salue un compte, None sinon. L'expéditeur est jugé sur son ADRESSE
    (jamais le nom affiché), un relais iCloud non prouvé est ignoré comme partout ailleurs."""
    try:
        if not codes_2fa.expediteur_instagram(msg.get("From")) or not codes_2fa.relais_accepte(msg):
            return None
        alias = str(codes_2fa.alias_du_mail(msg) or "").strip().lower()
        if "@" not in alias:
            return None
        corps = codes_2fa.INVISIBLES.sub("", str(codes_2fa.texte_du_mail(msg) or ""))
        m = codes_2fa.MOTIF_COMPTE.search(corps[:400])
        date = _date(msg)
        if not m or date is None:
            return None
        pseudo = m.group(1).rstrip(".").lower()
        return (alias, pseudo, date) if len(pseudo) >= 3 else None
    except Exception as erreur:                                         # noqa: BLE001 — un abonné ne plante jamais le lecteur
        journal.warning("Preuve par mail : lecture : %s", erreur)
        return None


def recevoir(msg, dossier=None):
    """Abonné du lecteur unique : jamais bloquant, le traitement part dans une tâche."""
    lu = lire_mail(msg) if ACTIF else None
    if not lu:
        return
    try:
        asyncio.get_running_loop().create_task(traiter(*lu))
    except RuntimeError:                                                # hors boucle (tests) : rien
        pass


def _faits() -> dict:
    lire = _deps.get("lire_json")
    return dict((lire(_deps["FICHIER"], {}) if lire and _deps.get("FICHIER") else {}) or {})


def _noter(cle: str):
    if not (_deps.get("ecrire_json") and _deps.get("FICHIER")):
        return
    d = _faits()
    d[cle] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _deps["ecrire_json"](_deps["FICHIER"], dict(sorted(d.items(), key=lambda kv: kv[1])[-500:]))


def a_fermer(info, date) -> bool:
    """Le compte de cette adresse attend-il d'être marqué créé ? `info` vient de proprietaire(alias)."""
    if not info or info.get("cree") or info.get("recycle") or not info.get("ouverte"):
        return False
    try:
        ouverte = datetime.fromisoformat(str(info["ouverte"]))
        ouverte = ouverte if ouverte.tzinfo else ouverte.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return date >= ouverte


async def traiter(alias: str, pseudo: str, date) -> str:
    """Ferme l'étape du compte de cette adresse si le mail le prouve créé. Renvoie ce qui a été fait ('' si rien)."""
    cle = f"{alias}|{pseudo}|{date.isoformat(timespec='seconds')}"
    if cle in _EN_COURS or cle in _faits() or not _deps.get("proprietaire"):
        return ""
    _EN_COURS.add(cle)
    try:
        info = _deps["proprietaire"](alias)
        if not a_fermer(info, date):
            return ""
        uid, n, prevu = str(info["uid"]), int(info["n"]), str(info.get("handle") or "").lower().lstrip("@")
        _noter(cle)
        renomme = ""
        if prevu and pseudo != prevu and _deps.get("renommer"):
            _, raison = await _deps["renommer"](uid, n, pseudo)
            renomme = f" · pseudo `{prevu}` → `{pseudo}`" if not raison else f" · pseudo pas changé ({raison})"
        ferme = bool(_deps.get("fermer") and await _deps["fermer"](uid, n))
        qui = info.get("prenom") or uid
        texte = (f"📬 **Compte {n} de {qui} prouvé par un mail d'Instagram** (`@{pseudo}`){renomme} · "
                 + ("étape fermée comme à l'appui du bouton, la suite part toute seule." if ferme
                    else "étape PAS fermée : vérifie son salon."))
        if _deps.get("admin"):
            await _deps["admin"](texte)
        journal.info("Preuve par mail : compte %s de %s, pseudo %s, fermée=%s", n, uid, "changé" if renomme else "inchangé", ferme)
        return texte
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Preuve par mail : %s", erreur)
        return ""
    finally:
        _EN_COURS.discard(cle)
