"""18/10 (action 16 du plan : « table Parcours, une ligne par clipper, clé ID Discord, horodatages écrits par le bot ») : l'onglet
« Parcours » du classeur des candidatures, réécrit chaque matin avec le point du jour.

Une ligne par clipper connu du parcours ou du registre. Les dates viennent de ce que le bot écrit déjà à l'événement :
  - quiz réussi et arrivée sur Discord : pipeline.json (etats[uid].date_quiz / validation, arrivees[uid].date) ;
  - comptes 1, 2, 3 remis puis créés, app remise : parcours.json (dates « n » et « n_fait », profils, et depuis le 31/10 les comptes
    vus créés sur Instagram par le suivi des créations, « crees_ig ») ;
  - premier jour tenu (5 visites payées ou plus) et visites payées des 7 derniers jours : la mesure de la paie (paie_clics.payees).
Rien n'est deviné : une date absente reste vide. Fonctions pures, aucun réseau ; le bot écrit l'onglet (ecrire_onglet_parcours).
"""
from datetime import date, datetime, timedelta, timezone

JOUR_TENU = 5
ENTETE = ["ID Discord", "Clipper", "Créatrice", "Quiz réussi", "Arrivée Discord", "Compte 1 remis", "Compte 1 créé",
          "Compte 2 remis", "Compte 2 créé", "Compte 3 remis", "Compte 3 créé", "App remise", "Premier jour tenu",
          "Visites payées 7 j", "Jours quiz → compte 1 créé", "Statut"]


def _instant(v):
    try:
        d = datetime.fromisoformat(str(v or ""))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _jour(v, fuseau) -> date | None:
    d = _instant(v)
    return d.astimezone(fuseau).date() if d else None


def _fr(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def premier_jour_tenu(paie: dict, uid: str, payees, debut: date, fin: date) -> date | None:
    """Le premier jour, entre debut et fin, où le clipper a eu JOUR_TENU visites payées ou plus."""
    j = debut
    while j <= fin:
        try:
            if payees(paie, uid, j, j) >= JOUR_TENU:
                return j
        except (ValueError, KeyError, TypeError):
            return None
        j += timedelta(days=1)
    return None


def lignes(parcours: dict, pipe: dict, registre: dict, paie: dict, payees, noms: dict, aujourdhui: date, fuseau,
           exclus=frozenset(), fenetre_jours: int = 60) -> list:
    """[ENTETE, …] : une ligne par clipper, les plus récents (arrivée) en haut. `noms` : uid -> pseudo affiché."""
    etats = (pipe or {}).get("etats") or {}
    arrivees = (pipe or {}).get("arrivees") or {}
    uids = (set(parcours or {}) | set(registre or {})) - set(map(str, exclus))
    avec_paie = {str(i.get("uid")) for i in ((paie or {}).get("liens") or {}).values() if i.get("uid")}
    hier = aujourdhui - timedelta(days=1)
    corps = []
    for uid in uids:
        f = (parcours or {}).get(uid) or {}
        reg = (registre or {}).get(uid) or {}
        info = etats.get(uid) or {}
        dates = f.get("dates") or {}
        profils = f.get("profils") or {}
        quiz = _jour(info.get("date_quiz") or info.get("validation"), fuseau) \
            if (info.get("etat") in ("quiz_ok", "valide", "attente_attribution", "sorti") or info.get("valide_par")) else None
        arrivee = _jour((arrivees.get(uid) or {}).get("date"), fuseau)
        remis = {n: _jour(dates.get(str(n)), fuseau) for n in (1, 2, 3)}
        # 31/10 (audit : « l'onglet Parcours dit compte 1 à créer pour des comptes GOOD au LOG ») : un compte vu créé sur Instagram par
        # le suivi des créations (suivi_creation : « crees_ig », avant que son étape s'ouvre) compte aussi, à la date où il a été vu
        vus_ig = f.get("crees_ig") or {}
        crees = {n: _jour(dates.get(f"{n}_fait") or profils.get(str(n)) or (vus_ig.get(str(n)) or {}).get("le"), fuseau)
                 for n in (1, 2, 3)}
        app = _jour(dates.get("7") or dates.get("6"), fuseau)
        tenu, sept = None, ""
        if uid in avec_paie and payees is not None:
            debut = max([d for d in (arrivee, remis[1]) if d] or [aujourdhui - timedelta(days=fenetre_jours)])
            tenu = premier_jour_tenu(paie, uid, payees, max(debut, aujourdhui - timedelta(days=fenetre_jours)), hier)
            try:
                sept = int(payees(paie, uid, aujourdhui - timedelta(days=7), hier))
            except (ValueError, KeyError, TypeError):
                sept = ""
        delai = (crees[1] - quiz).days if (quiz and crees[1] and crees[1] >= quiz) else ""
        if info.get("etat") == "sorti":
            statut = "sorti"
        elif crees[3]:
            statut = "3 comptes"
        elif crees[1]:
            statut = f"compte {max(n for n in (1, 2, 3) if crees[n])} créé"
        elif remis[1]:
            statut = "compte 1 à créer" + (" (accès en attente)" if f.get("acces_en_attente") else "")
        else:
            statut = "attend sa créatrice" if not (f.get("creatrice") or reg.get("creatrice")) else "créatrice attribuée"
        corps.append(([arrivee or quiz or date.min],
                      ["'" + uid, noms.get(uid) or f.get("prenom") or "", f.get("creatrice") or reg.get("creatrice") or "",
                       _fr(quiz), _fr(arrivee), _fr(remis[1]), _fr(crees[1]), _fr(remis[2]), _fr(crees[2]), _fr(remis[3]),
                       _fr(crees[3]), _fr(app), _fr(tenu), sept, delai, statut]))
    corps.sort(key=lambda x: x[0], reverse=True)
    return [ENTETE] + [l for _, l in corps]
