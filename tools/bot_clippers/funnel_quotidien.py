"""18/10 (actions 16-17 du plan, définitions gelées) : les trois chiffres du funnel, jour par jour.

  M1 · lead      = candidature soumise, dédoublonnée par numéro (candidatures_du_jour du bot, le même compteur que !pipeline) ;
  M2 · qualifié  = quiz réussi ET arrivé sur Discord le jour même ou le lendemain du quiz, compté le jour de l'arrivée ;
  M3 · actif     = clipper qui a tenu sa journée : 5 visites payées ou plus sur son lien (paie_clics.payees, la mesure de la paie).

Fonctions pures (aucun réseau) ; le bot les branche dans le digest, `!funnel` et l'onglet « Funnel quotidien ».
"""
from datetime import date, datetime, timedelta, timezone

JOUR_TENU = 5
ETATS_QUIZ_OK = ("quiz_ok", "valide", "attente_attribution")


def _jour(iso, fuseau) -> date | None:
    try:
        d = datetime.fromisoformat(str(iso or ""))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(fuseau).date()


def qualifies(pipe: dict, jour: date, fuseau) -> list:
    """Les uid qualifiés (M2) du jour : arrivés ce jour-là, quiz réussi la veille ou le jour même (quiz du site ou depuis Discord)."""
    etats = (pipe or {}).get("etats") or {}
    out = []
    for uid, arr in ((pipe or {}).get("arrivees") or {}).items():
        if _jour((arr or {}).get("date"), fuseau) != jour:
            continue
        info = etats.get(uid) or {}
        reussi = info.get("etat") in ETATS_QUIZ_OK or info.get("valide_par") == "quiz"
        if not reussi:
            continue
        quand = [_jour(info.get(k), fuseau) for k in ("date_quiz", "validation")]
        quand = [q for q in quand if q is not None]
        if quand and any(jour - timedelta(days=1) <= q <= jour for q in quand):
            out.append(str(uid))
    return sorted(out)


def actifs(paie: dict, jour: date, payees, exclus=frozenset()) -> list:
    """Les uid actifs (M3) du jour : JOUR_TENU visites payées ou plus ce jour-là, d'après la mesure de la paie."""
    uids = {str(info.get("uid")) for info in ((paie or {}).get("liens") or {}).values()
            if info.get("uid") and not info.get("archive")}
    out = []
    for uid in sorted(uids - set(exclus)):
        try:
            if payees(paie, uid, jour, jour) >= JOUR_TENU:
                out.append(uid)
        except (ValueError, KeyError, TypeError):
            continue
    return out


def serie(jours: list, m1, m2, m3) -> list:
    """[(jour, M1, M2, M3)] ; m1/m2/m3 : fonctions jour -> nombre."""
    return [(j, int(m1(j)), int(m2(j)), int(m3(j))) for j in jours]


def _moy(valeurs) -> str:
    v = list(valeurs)
    return f"{sum(v) / len(v):.1f}".replace(".", ",") if v else "0"


def texte(lignes: list) -> str:
    """Le tableau de `!funnel` (le plus récent en haut) et la moyenne 7 jours."""
    if not lignes:
        return "Aucun jour à afficher."
    corps = [f"`{j.strftime('%d/%m')}` · M1 **{a}** · M2 **{b}** · M3 **{c}**" for j, a, b, c in sorted(lignes, reverse=True)]
    sept = sorted(lignes)[-7:]
    taux = sum(b for _, _, b, _ in sept) / max(1, sum(a for _, a, _, _ in sept))
    return ("📈 **Funnel par jour** · M1 leads · M2 qualifiés (quiz + Discord sous 24 h) · M3 actifs (5 visites payées ou plus)\n\n"
            + "\n".join(corps)
            + f"\n\nMoyenne 7 jours : M1 {_moy(a for _, a, _, _ in sept)} · M2 {_moy(b for _, _, b, _ in sept)}"
            + f" · M3 {_moy(c for _, _, _, c in sept)} · M2/M1 {round(taux * 100)} %")


def ligne_digest(lignes: list) -> str:
    """Une ligne pour le digest : hier, et la moyenne des 7 derniers jours."""
    if not lignes:
        return ""
    ordre = sorted(lignes)
    _, a, b, c = ordre[-1]
    sept = ordre[-7:]
    return (f"📈 **M1 · M2 · M3 hier** : {a} lead(s) · {b} qualifié(s) · {c} actif(s)"
            f" (moyenne 7 j : {_moy(x[1] for x in sept)} · {_moy(x[2] for x in sept)} · {_moy(x[3] for x in sept)})")


def lignes_feuille(lignes: list) -> list:
    """L'onglet « Funnel quotidien » : en-tête puis un jour par ligne, du plus ancien au plus récent (dates JJ/MM/AAAA)."""
    return [["Date", "Leads (M1)", "Qualifiés (M2)", "Actifs (M3)"]] + [
        [j.strftime("%d/%m/%Y"), a, b, c] for j, a, b, c in sorted(lignes)]
