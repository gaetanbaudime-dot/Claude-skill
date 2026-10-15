"""Règles du 15 octobre. Fonctions pures, aucune inscription ni appel réseau."""
from uuid import uuid4

LIMITE_COMPTES = 3
ETATS = (("Good", "#008000"), ("Faire appel", "#FFA500"),
         ("Ban", "#FF0000"), ("À créer", "#FFFFFF"))


def cle(handle):
    return str(handle or "").strip().lower().lstrip("@")


def registre(d, uid):
    """Conserve les identités réservées à vie ; une réservation incertaine consomme une place.

    Le passé déjà effacé ne peut pas être reconstitué : audit préalable requis.
    Les alias de renommage ne consomment jamais une nouvelle place.
    """
    uid = str(uid)
    comptes = d.setdefault("comptes_a_vie", {}).setdefault(uid, [])
    fiche = (d.get("clippers") or {}).get(uid) or {}
    handles = list(fiche.get("comptes") or [])
    handles += [a.get("handle") for a in fiche.get("acces") or [] if isinstance(a, dict)]
    handles += [a.get("handle") for telephone in (fiche.get("telephones") or {}).values()
                for a in (telephone or {}).get("acces") or [] if isinstance(a, dict)]
    handles += [h for h, v in (d.get("livres") or {}).items() if str(v.get("uid")) == uid]
    for r in fiche.get("renommes") or []:
        ancien, nouveau = cle(r.get("ancien")), cle(r.get("nouveau"))
        c = next((c for c in comptes if ancien in c["aliases"] or nouveau in c["aliases"]), None)
        if c:
            c["aliases"] = sorted((set(c["aliases"]) | {ancien, nouveau}) - {""})
    for h in handles:
        h = cle(h)
        if h and not any(h in c["aliases"] for c in comptes):
            comptes.append({"id": str(uuid4()), "aliases": [h], "origine": "historique"})
    for r in fiche.get("renommes") or []:
        ancien, nouveau = cle(r.get("ancien")), cle(r.get("nouveau"))
        c = next((c for c in comptes if nouveau in c["aliases"] or ancien in c["aliases"]), None)
        if c:
            c["aliases"] = sorted(set(c["aliases"]) | {ancien, nouveau} - {""})
    return comptes


def reserver_identites(d, uid, handles):
    """Valide tout le lot avant mutation ; à persister AVANT les écritures externes."""
    uid = str(uid)
    for autre in list(d.get("clippers") or {}):
        registre(d, autre)
    comptes = registre(d, uid)
    demandes = set(map(cle, handles)) - {""}
    connues = {h for c in comptes for h in c["aliases"]}
    for autre, entrees in d.get("comptes_a_vie", {}).items():
        if autre != uid and demandes & {h for c in entrees for h in c["aliases"]}:
            raise RuntimeError("Compte déjà réservé à un autre clippeur, réattribution interdite")
    nouveaux = demandes - connues
    if len(comptes) + len(nouveaux) > LIMITE_COMPTES:
        raise RuntimeError("Maximum de trois comptes à vie atteint ; aucun remplacement autorisé")
    for h in sorted(nouveaux):
        comptes.append({"id": str(uuid4()), "aliases": [h], "origine": "reservation"})
    return comptes


def cumuler_publications(suivi, publications, creation, maintenant):
    """Union des preuves datées ; même Reel revu ou épinglé = une publication."""
    from datetime import datetime
    verifies = dict((suivi or {}).get("publications_verifiees") or {})
    for publication in publications or []:
        try:
            instant = datetime.fromisoformat(str(publication.get("publie")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        code = publication.get("code")
        if code and instant.tzinfo is not None and creation is not None and creation <= instant <= maintenant:
            verifies[str(code)] = publication["publie"]
    return verifies
