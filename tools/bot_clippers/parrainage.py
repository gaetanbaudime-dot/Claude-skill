"""Parrainage (28/09, Gaëtan : « oui, mais n'embrouille pas les clippers »).

Un clipper tape `!parrain @lui` dans son salon perso (ou en MP) : le plus ancien des deux sur le serveur est le parrain, l'autre
le filleul. Le parrain touche PRIME_USD (5 $) une seule fois, le jour où le filleul apparaît sur une liste de paie avec un
montant : la prime s'ajoute à la ligne du parrain sur la liste de ce jour-là. Rien n'est dit au filleul, rien n'est promis
avant. État dans DONNEES/parrainage.json : {"filleuls": {uid_filleul: {"parrain", "date", "periode"}}} ; `periode` = la clé
de la liste de paie qui a porté la prime (vide tant qu'elle n'est pas due). PARRAINAGE=0 éteint la commande."""

import logging
import os
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("parrainage")
ACTIF = os.environ.get("PARRAINAGE", "1").strip() != "0"
PRIME_USD = float(os.environ.get("PARRAINAGE_PRIME_USD", "5") or 5)
JOURS_MAX = int(os.environ.get("PARRAINAGE_JOURS_MAX", "30") or 30)     # le filleul est là depuis moins de 30 jours
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, prenom_de, est_staff (membre -> bool)."""
    _deps.update(deps)


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER"], {"filleuls": {}})
    d.setdefault("filleuls", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER"], d)


def _prime() -> str:
    return f"{PRIME_USD:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " $"


def declarer(auteur, autre, maintenant=None) -> tuple:
    """(parrain, filleul, texte de réponse). Le plus ancien sur le serveur parraine l'autre ; un filleul n'a qu'un parrain ;
    un filleul arrivé depuis plus de JOURS_MAX jours ne se parraine plus. Ne touche à rien si refus."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if autre is None or getattr(autre, "bot", False) or autre.id == auteur.id:
        return None, None, "Tape `!parrain @lui` en mentionnant l'autre clipper."
    if _deps.get("est_staff") and (_deps["est_staff"](auteur) or _deps["est_staff"](autre)):
        return None, None, "Le parrainage, c'est entre clippers."
    j_a, j_b = getattr(auteur, "joined_at", None) or maintenant, getattr(autre, "joined_at", None) or maintenant
    parrain, filleul = (auteur, autre) if j_a <= j_b else (autre, auteur)
    j_f = j_b if filleul is autre else j_a
    if maintenant - j_f > timedelta(days=JOURS_MAX):
        return None, None, f"Trop tard : {_deps['prenom_de'](filleul)} est là depuis plus de {JOURS_MAX} jours."
    d = _lire()
    deja = d["filleuls"].get(str(filleul.id))
    if deja:
        if deja.get("parrain") == str(parrain.id):
            return parrain, filleul, f"Déjà noté : {_deps['prenom_de'](parrain)} parraine {_deps['prenom_de'](filleul)}."
        return None, None, f"{_deps['prenom_de'](filleul)} a déjà un parrain."
    d["filleuls"][str(filleul.id)] = {"parrain": str(parrain.id), "date": maintenant.isoformat(timespec="seconds"), "periode": ""}
    _ecrire(d)
    journal.info("Parrainage : %s parraine %s", parrain.id, filleul.id)
    return parrain, filleul, (f"✅ {_deps['prenom_de'](parrain)} parraine {_deps['prenom_de'](filleul)}. "
                              f"{_prime()} pour {_deps['prenom_de'](parrain)} le jour de la première paie de {_deps['prenom_de'](filleul)}.")


async def commande(message, texte: str) -> bool:
    """`!parrain @lui` : par l'un ou l'autre des deux, dans son salon perso ou en MP."""
    if not texte.lower().startswith("!parrain"):
        return False
    if not ACTIF:
        await message.reply("Le parrainage n'est pas ouvert pour l'instant.")
        return True
    autre = message.mentions[0] if getattr(message, "mentions", None) else None
    _, _, reponse = declarer(message.author, autre)
    await message.reply(reponse)
    return True


def primes_dues(paies: dict, cle_periode: str) -> list:
    """Les primes à porter sur la liste de paie `cle_periode` (AAAA-MM-JJ) : [(uid_parrain, uid_filleul, montant)]. Un filleul
    payé (montant > 0) dont la prime n'a jamais été due la déclenche sur cette liste ; une prime déjà portée sur cette même
    liste (liste retapée) y reste ; une prime portée sur une liste passée ne revient pas."""
    if not ACTIF:
        return []
    d = _lire()
    out, change = [], False
    for uid_f, info in d["filleuls"].items():
        periode = info.get("periode") or ""
        if periode and periode != cle_periode:
            continue
        if not periode:
            if float(paies.get(uid_f, 0) or 0) <= 0:
                continue
            info["periode"] = cle_periode
            change = True
        out.append((str(info.get("parrain") or ""), uid_f, PRIME_USD))
    if change:
        _ecrire(d)
    return out
