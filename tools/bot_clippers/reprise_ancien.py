"""18/10 (Gaëtan : Moutakabirou bloqué « Historique à vie non rapproché ») : `!reprise @membre Créatrice`, réservée aux ADMIN_IDS.

Un ancien clipper (fiche dans sortis.json, quiz refait) ne peut pas recevoir de compte tant que son historique à vie n'est pas
dans le registre du processus (règle C1 : trois comptes au total par clipper, jamais de compteur remis à zéro). `!rapprocher-zero`
refuse exprès un ancien sorti, et l'import revu ne tourne que sur le serveur. La reprise écrit cet historique d'après ce que le
bot connaît déjà de lui :

  - les @ de sa fiche d'onboarding (comptes réservés ou livrés), ceux de ses accès, et les comptes déjà au registre ;
  - chaque @ connu compte comme « incertain » (unknown) dans ses trois places : rien n'est jamais retiré ni diminué ;
  - aucun @ connu : historique zéro, avec la provenance (message, admin, date) gardée comme preuve.

Refusée si un départ avec lien est enregistré au registre (sortie:<uid>) : revue humaine. Puis le parcours repart comme
`!creatrice @membre Créatrice` (même verrou, même décision explicite).
"""
import json
import re

from process_store import Bloque

_HANDLE = re.compile(r"[a-z0-9._]{1,30}")


def handles_connus(uid: str, onboarding: dict | None, parcours: dict | None) -> list:
    """Les @ que le bot associe déjà à ce clipper (fiche d'onboarding : comptes et accès ; parcours : profils), normalisés, triés."""
    uid = str(uid)
    vus = set()
    fiche = ((onboarding or {}).get("clippers") or {}).get(uid) or {}
    for h in fiche.get("comptes") or []:
        vus.add(str(h))
    for a in fiche.get("acces") or []:
        if isinstance(a, dict):
            vus.add(str(a.get("handle") or ""))
    p = (parcours or {}).get(uid) or {}
    for cle in ("profils", "comptes"):
        v = p.get(cle)
        if isinstance(v, dict):
            vus.update(str(x) for x in v.values() if isinstance(x, str))
        elif isinstance(v, list):
            vus.update(str(x) for x in v if isinstance(x, str))
    propres = {h.strip().lstrip("@").lower() for h in vus}
    return sorted(h for h in propres if _HANDLE.fullmatch(h))


def reprendre(store, uid: str, handles: list, provenance: dict) -> dict:
    """Écrit l'historique à vie de l'ancien (additif). Renvoie {"comptes": n, "deja": bool}."""
    uid = str(uid)
    if not all(str(provenance.get(k) or "").strip() for k in ("source", "par", "date")):
        raise Bloque("Provenance de la reprise incomplète")
    if store.get("sortie:" + uid):
        raise Bloque("Départ avec lien enregistré : reprise refusée, revue humaine")
    connus = store.counts(uid)
    deja = bool(store.get("reprise-ancien:" + uid))
    preuve = json.dumps({"type": "reprise_ancien_staff", "provenance": provenance, "handles": handles,
                         "comptes_registre_avant": connus}, ensure_ascii=False, sort_keys=True)
    store.reconcile(uid, [{"aliases": [h], "status": "unknown", "evidence": preuve} for h in handles], preuve)
    store.put("reprise-ancien:" + uid, {"provenance": provenance, "handles": handles, "avant": connus})
    total = sum(n for s, n in store.counts(uid).items() if s in ("created", "reserved", "unknown"))
    return {"comptes": total, "deja": deja}
