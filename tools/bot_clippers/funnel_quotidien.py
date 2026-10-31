"""18/10 (actions 16-17 du plan, définitions gelées) : les trois chiffres du funnel, jour par jour.

  M1 · lead      = nouvelle personne : comptée UNE fois, le jour de sa toute première candidature (24/10, voir plus bas) ;
  M2 · qualifié  = quiz réussi ET arrivé sur Discord le jour même ou le lendemain du quiz, compté le jour de l'arrivée ;
  M3 · actif     = clipper qui a tenu sa journée : 5 visites payées ou plus sur son lien (paie_clics.payees, la mesure de la paie).

24/10 (Gaëtan : « corrige le compteur Leads pour qu'il compte des personnes uniques, sans les tests ») : le 29/09 affichait 33
leads pour 10 vraies nouvelles personnes. Trois causes : les lignes du classeur sans numéro lisible n'étaient jamais
dédoublonnées, la même candidature était comptée deux fois (ligne du classeur + fiche du pipeline), et 8 envois « Test » du
déploiement passaient. Une personne = un numéro (8 derniers chiffres) ou un pseudo Telegram ; deux envois qui partagent l'un
des deux sont la même personne. Une re-candidature ne compte plus.

Fonctions pures (aucun réseau) ; le bot les branche dans le digest, `!funnel` et l'onglet « Funnel quotidien ».
"""
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

JOUR_TENU = 5
ETATS_QUIZ_OK = ("quiz_ok", "valide", "attente_attribution")
# Réponses du champ Telegram qui ne désignent personne (« même numéro », « non »…) : jamais une clé d'identité
PSEUDOS_VIDES = {"", "non", "pas", "aucun", "rien", "meme numero", "meme", "pareil", "idem", "none", "na", "n a", "test",
                 "pas de telegram", "je n ai pas", "x", "xx", "xxx"}
# Les pseudos du staff (ceux de l'annonce) : jamais l'identité d'un candidat
CLES_STAFF = {"tg:gaetan", "tg:gaetanofm", "tg:gaetan_ofm"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9@_.+ ]", " ", s)).strip()


def est_test(prenom) -> bool:
    """Un envoi de test : prénom « Test », « TEst », « test Claude »… (même règle que le nettoyage du classeur)."""
    p = _norm(prenom)
    return p == "test" or p.startswith("test ")


def cles_identite(tel="", telegram="", prenom="", pays="") -> set:
    """Les clés qui désignent une personne : son numéro (8 derniers chiffres), son pseudo Telegram ; un « pseudo » qui n'est
    qu'un numéro compte comme numéro. Ni l'un ni l'autre : prénom + pays (à défaut de mieux). Rien du tout : ensemble vide."""
    cles = set()
    chiffres = re.sub(r"\D", "", str(tel or ""))
    if len(chiffres) >= 8:
        cles.add("tel:" + chiffres[-8:])
    brut = re.sub(r"^(https?://)?(www\.)?t\.me/", "", str(telegram or "").strip(), flags=re.I)
    pseudo = _norm(brut).lstrip("@").replace(" ", "")
    if re.fullmatch(r"[\d+\s().\-]+", brut.strip()) and len(re.sub(r"\D", "", brut)) >= 8:
        cles.add("tel:" + re.sub(r"\D", "", brut)[-8:])
    elif len(pseudo) >= 3 and _norm(brut).lstrip("@") not in PSEUDOS_VIDES:
        cles.add("tg:" + pseudo)
    if not cles and _norm(prenom):
        cles.add("nom:" + _norm(prenom) + "|" + _norm(pays))
    return cles


def nouvelles_personnes_par_jour(envois: list) -> dict:
    """M1 : {jour: nombre de personnes dont c'est la toute première candidature}. `envois` : un dict par envoi connu
    {date (datetime ou date, heure de Paris), tel, telegram, prenom, pays}, toutes sources et toutes dates confondues.
    Les tests sont écartés ; deux envois qui partagent une clé (cles_identite) sont la même personne, de proche en proche."""
    parent = {}

    def racine(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    gardes = []                                     # (jour, clés) des envois gardés
    for e in envois or []:
        d = e.get("date")
        jour = d.date() if isinstance(d, datetime) else d
        if not isinstance(jour, date) or est_test(e.get("prenom")):
            continue
        cles = cles_identite(e.get("tel"), e.get("telegram"), e.get("prenom"), e.get("pays"))
        if cles & CLES_STAFF:
            # le pseudo de l'annonce recopié par un candidat (« @gaetan_ofm ») n'est pas son identité ; sans numéro, c'est un
            # envoi du staff lui-même (test du 24/09, du 28/09)
            cles -= CLES_STAFF
            if not any(c.startswith("tel:") for c in cles):
                continue
        if not cles:
            continue                                # ligne vide (ni numéro, ni pseudo, ni prénom) : pas un lead
        gardes.append((jour, cles))
    # un pseudo porté par deux numéros différents (famille, recopie) ne relie personne
    tels_par_pseudo = {}
    for _, cles in gardes:
        tels = {c for c in cles if c.startswith("tel:")}
        for c in cles:
            if c.startswith("tg:"):
                tels_par_pseudo.setdefault(c, set()).update(tels)
    partages = {c for c, tels in tels_par_pseudo.items() if len(tels) >= 2}
    premiers = []
    for jour, cles in gardes:
        cles = (cles - partages) or cles
        for c in cles:
            parent.setdefault(c, c)
        premiere = next(iter(sorted(cles)))
        for c in cles:
            parent[racine(c)] = racine(premiere)
        premiers.append((jour, premiere))
    debut = {}
    for jour, cle in premiers:
        r = racine(cle)
        if r not in debut or jour < debut[r]:
            debut[r] = jour
    par_jour = {}
    for jour in debut.values():
        par_jour[jour] = par_jour.get(jour, 0) + 1
    return par_jour


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


def formation_quiz(pipe: dict, debut: date, fin: date, fuseau, exclu=None) -> dict:
    """31/10 (audit : « 64 % des leads ne tentent jamais le quiz… mesurer où ils décrochent, vidéo ou quiz ») : les personnes (un
    numéro = une personne) qui ont envoyé le formulaire du site entre `debut` et `fin`, celles qui ont ouvert le quiz (une tentative
    s'ouvre à l'affichage, quiz_tentatives_web), celles qui l'ont envoyé et celles qui l'ont réussi. Ouvrir le quiz suppose d'avoir
    passé la page de la vidéo : formulaires - quiz ouverts = décrochés avant le quiz. `exclu(tel)` : le staff. Pur."""
    tentatives = (pipe or {}).get("quiz_tentatives_web") or {}
    historique = (pipe or {}).get("quiz_historique_web") or {}
    personnes = {}
    for cid, fiche in ((pipe or {}).get("candidatures_web") or {}).items():
        if not isinstance(fiche, dict):
            continue
        j = _jour(fiche.get("date"), fuseau)
        tel = "".join(ch for ch in str(fiche.get("tel") or "") if ch.isdigit())[-9:]
        if j is None or not (debut <= j <= fin) or (exclu is not None and exclu(fiche.get("tel"))):
            continue
        q = fiche.get("quiz") or {}
        envoye = int(q.get("essais", 0) or 0) > 0 or any(k.startswith(f"quiz:c:{cid}:") for k in historique)
        ouvert = envoye or f"c:{cid}" in tentatives
        p_ = personnes.setdefault(tel or cid, {"ouvert": False, "envoye": False, "reussi": False})
        p_["ouvert"] |= ouvert
        p_["envoye"] |= envoye
        p_["reussi"] |= bool(q.get("reussi"))
    return {"formulaires": len(personnes), "quiz_ouvert": sum(1 for x in personnes.values() if x["ouvert"]),
            "quiz_envoye": sum(1 for x in personnes.values() if x["envoye"]),
            "reussi": sum(1 for x in personnes.values() if x["reussi"])}


def ligne_formation(c: dict, jours: int) -> str:
    """La ligne du point du lundi ; '' sans formulaire."""
    if not c or not c.get("formulaires"):
        return ""
    pct = lambda x: f"{round(100 * x / c['formulaires'])} %"                  # noqa: E731
    return (f"🎬 **Formation → quiz ({jours} j)** : {c['formulaires']} formulaire(s) → {c['quiz_ouvert']} ont ouvert le quiz "
            f"({pct(c['quiz_ouvert'])}) → {c['quiz_envoye']} l'ont envoyé ({pct(c['quiz_envoye'])}) → {c['reussi']} réussi(s)"
            f"\n-# Formulaire envoyé sans ouvrir le quiz : décroché sur la page de la vidéo ({c['formulaires'] - c['quiz_ouvert']}).")


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
    return ("📈 **Funnel par jour** · M1 leads (nouvelles personnes, tests exclus) · M2 qualifiés (quiz + Discord sous 24 h)"
            " · M3 actifs (5 visites payées ou plus)\n\n"
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
    # 21/10 (Gaëtan : « simplifie ») : leads et qualifiés d'hier sont déjà dans « Recrutement hier » ; restent les actifs et la
    # tendance de la semaine, en mots
    return (f"📈 **{c} clipper(s) actif(s) hier** · moyenne 7 j : {_moy(x[1] for x in sept)} lead(s), "
            f"{_moy(x[2] for x in sept)} qualifié(s), {_moy(x[3] for x in sept)} actif(s) par jour")


def lignes_feuille(lignes: list) -> list:
    """L'onglet « Funnel quotidien » : en-tête puis un jour par ligne, du plus ancien au plus récent (dates JJ/MM/AAAA)."""
    return [["Date", "Leads (M1)", "Qualifiés (M2)", "Actifs (M3)"]] + [
        [j.strftime("%d/%m/%Y"), a, b, c] for j, a, b, c in sorted(lignes)]
