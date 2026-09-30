"""Comptes BAN d'un clipper remplacés, déposé dans le dépôt (01/10, Gaëtan : « Clarisse, donne-lui de nouveaux comptes »).

`remplacements_a_appliquer.json` : [{"id", "prenom", "creatrice"}], appliqué une fois au démarrage (trace par id sur le volume) :
1. ses lignes BAN sont rendues (Gérant vidé ; la ligne reste BAN, rien d'elle n'est jamais réutilisé) ;
2. des comptes neufs complètent son trio (`onboarding.livrer` : jamais un compte qui partage l'identifiant, le mot de passe,
   l'e-mail ou le téléphone d'un compte BAN — règle de Gaëtan du 01/10) ;
3. son parcours repart à l'étape du prochain compte à créer (un compte tous les 48 h), dates remises à zéro, notes gardées.
Le bilan part au salon admin."""
import json
import logging
from pathlib import Path

import onboarding
import parcours

journal = logging.getLogger("bot.remplacements")
FICHIER = Path(__file__).parent / "remplacements_a_appliquer.json"
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, DONNEES, normaliser, membre_par_prenom, salon_perso, notifier."""
    _deps.update(deps)


def _n(t) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else str(t or "").strip().lower()


async def remplacer(prenom: str, creatrice: str) -> str:
    """Un remplacement ; renvoie la ligne de bilan. Lève LookupError si le clipper est introuvable (réessayé au démarrage suivant)."""
    comptes = await onboarding.lire_comptes()
    bans = [c["handle"] for c in comptes if _n(c.get("gerant")) == _n(prenom) and _n(c.get("etat")) == "ban" and c.get("handle")]
    vivants = [c for c in comptes if _n(c.get("gerant")) == _n(prenom) and _n(c.get("etat")) != "ban" and c.get("handle")]
    if bans:
        await onboarding.liberer(prenom, bans, pool=True)
    membre = _deps["membre_par_prenom"](_n(prenom)) if _deps.get("membre_par_prenom") else None
    if membre is None:
        raise LookupError(f"{prenom} introuvable au registre (ou deux homonymes)")
    salon = _deps["salon_perso"](str(membre.id)) if _deps.get("salon_perso") else None
    bilan = await onboarding.livrer(membre, creatrice, salon, declencheur="remplacement des comptes BAN")
    if salon is not None:
        d = parcours._lire()
        fiche = d.get(str(membre.id))
        if fiche is not None:                                           # nouveau trio : l'ancien calendrier ne vaut plus rien
            fiche["dates"] = {}
            for cle in ("reconcilie", "corrige_4", "warmup_jour"):
                fiche.pop(cle, None)
            parcours._ecrire(d)
        await parcours.forcer_etape(salon, membre, creatrice, min(3, len(vivants)) + 1)
    return f"🔁 {prenom} : {len(bans)} compte(s) BAN rendu(s) · {bilan}" + ("" if salon is not None else " · pas de salon perso, parcours non relancé")


async def demarrage(client) -> list:
    await client.wait_until_ready()
    if not FICHIER.exists() or not _deps.get("DONNEES") or not onboarding.actif():
        return []
    try:
        entrees = json.loads(FICHIER.read_text(encoding="utf-8"))
    except ValueError as erreur:
        journal.warning("remplacements_a_appliquer.json illisible : %s", erreur)
        return []
    trace = _deps["DONNEES"] / "remplacements_faits.json"
    faits = _deps["lire_json"](trace, {})
    lignes = []
    for e in entrees if isinstance(entrees, list) else []:
        ident, prenom, creatrice = str(e.get("id") or ""), str(e.get("prenom") or "").strip(), str(e.get("creatrice") or "").strip()
        if not ident or not prenom or not creatrice or ident in faits:
            continue
        try:
            ligne = await remplacer(prenom, creatrice)
        except LookupError as erreur:
            lignes.append(f"⚠️ {prenom} : {erreur}, réessayé au prochain démarrage")
            continue
        except Exception as erreur:                                     # noqa: BLE001 — jamais tuer le bot
            journal.exception("Remplacement de %s", prenom)
            ligne = f"⚠️ {prenom} : {type(erreur).__name__} {str(erreur)[:120]}"
        faits[ident] = {"bilan": ligne}
        _deps["ecrire_json"](trace, faits)
        lignes.append(ligne)
    if lignes and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Remplacements de comptes appliqués**\n" + "\n".join(lignes), client.guilds[0] if client.guilds else None)
        except Exception:                                               # noqa: BLE001
            pass
    return lignes
