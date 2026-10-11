"""Liens GAML suivis des clippers du roster (24/09, ex-rapport #jonas-stats).

10/10 (revue du recrutement, lot L9a) : le rapport quotidien du manager (#jonas-stats, sa copie au salon admin, `!stats-jonas`,
`!stats-manager`, la liste CLIPPERS_JONAS et rapport_jonas.json) est supprimé : le Dashboard donne les visites d'hier et des
7 jours par clipper. Le roster vivant et `!actifs` vivent dans roster.py (groupes_actifs, total_actifs, texte_actifs).

Reste ici `associer_suivi`, branché sur la boucle des clics (paie_clics, dépendance « associer_suivi ») : un lien GAML est rattaché
à un clipper du roster quand sa note contient le prénom en mot entier et que son nom commence par la créatrice (ex. note
« Clipping Prénom », nom « Créatrice 🌸 » ; « Prénom Metricool » compte aussi pour ce prénom). Ces liens sont relevés même sans
membre Discord attribué (`suivi` dans clics.json).

`demarrer` et `apres_releves` sont des bouchons inertes, le temps que le lot W retire leurs branchements (on_ready, paie_clics).
`commande_staff` (11/10) répond à `!actifs`, `!equipe-active` (le roster compté) et à `!stats-jonas`, `!stats-manager`
(« retiré »), sinon commande_admin les prend pour `!equipe` et `!stats` : son appel dans on_message reste. texte_rapport n'existe plus : la passe 3 du Dashboard
(lot CLICS) ne doit plus y toucher ; à la fusion, rapport_stats.py de L9a est pris en entier.
"""

import logging
import re

import paie_clics

journal = logging.getLogger("rapport")

_deps = {}


def configurer(deps: dict):
    global _deps
    _deps = deps


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").lower().strip()


# ------------------------------------------------------------------ roster actif (26/09, déplacé dans roster.py le 10/10)
def groupes_actifs() -> dict:
    """{créatrice: [prénoms]} : la dépendance « roster » quand le bot est branché (roster.groupes), sinon roster.groupes_actifs."""
    if _deps.get("roster"):
        try:
            return dict(_deps["roster"]() or {})
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Roster illisible : %s", erreur)
            return {}
    import roster
    return roster.groupes_actifs()


def total_actifs(groupes: dict = None) -> int:
    """Le chiffre du salon-compteur : prénoms distincts, toutes créatrices confondues (voir roster.total_actifs)."""
    import roster
    return roster.total_actifs(groupes if groupes is not None else groupes_actifs())


def texte_actifs() -> str:
    """`!actifs` : voir roster.texte_actifs."""
    import roster
    return roster.texte_actifs()


# ------------------------------------------------------------------ liens suivis
def _mots(t: str) -> list:
    """Les mots d'un texte, sans accents ni casse ni ponctuation (« Clipping Anaïs » → ["clipping", "anais"])."""
    return re.findall(r"[a-z0-9]+", paie_clics._n_note(t))


def associer_suivi(d: dict, liens: list) -> int:
    """Marque dans clics.json les liens GAML des clippers du roster (relevés même sans membre Discord).
    Renvoie le nombre de liens nouvellement suivis. 09/10 (dashboard) : le prénom est cherché comme MOT ENTIER de la note (tous
    ses mots, dans l'ordre de la note ou non) : « Ana » ne prend plus « Clipping Anaïs », « Rianah » prend toujours « Rianah
    Metricool ». Un suivi déjà posé dont la note GAML actuelle ne contient plus le prénom suivi en mot entier (posé par l'ancienne
    règle, « Ana » sur « Clipping Anaïs ») est retiré, puis rattaché au bon prénom s'il y en a un ; le lien reste relevé
    (paie_clics.marquer_releves). Renvoie le nombre de liens nouvellement suivis ou retirés (l'appelant écrit si > 0)."""
    nouveaux = 0
    notes = {l.get("id"): str(l.get("note") or "") for l in liens if l.get("id") and "note" in l}
    for lid, info in d.get("liens", {}).items():
        if not info.get("suivi") or lid not in notes:
            continue
        mots_note = set(_mots(re.sub(r"\(\s*ex[^)]*\)", " ", notes[lid], flags=re.I)))
        if set(_mots(info.get("suivi_nom"))) and set(_mots(info.get("suivi_nom"))) <= mots_note:
            continue
        for cle in ("suivi", "suivi_nom", "suivi_creatrice"):
            info.pop(cle, None)
        nouveaux += 1
    for creatrice, noms in groupes_actifs().items():
        for nom in noms:
            mots_nom = set(_mots(nom))
            for l in liens:
                # 09/10 (revue) : « (ex-Julien) » dit l'ancien propriétaire, jamais le clipper suivi ; un lien « Clipping libre » n'est à personne
                lid, note = l.get("id"), _n(re.sub(r"\(\s*ex[^)]*\)", " ", str(l.get("note") or ""), flags=re.I))
                cr = _n(str(l.get("name", "")).split()[0] if l.get("name") else "")
                if (not lid or not mots_nom or not mots_nom <= set(_mots(note)) or cr != _n(creatrice)
                        or note.strip().startswith("clipping libre")):
                    continue
                info = d["liens"].setdefault(lid, {"uid": "", "note": l.get("note"), "url": l.get("url"),
                                                   "creatrice": creatrice, "depuis": paie_clics.CLICS_DEPUIS, "par": "rapport"})
                if not info.get("suivi"):
                    nouveaux += 1
                info.update({"suivi": True, "suivi_nom": nom, "suivi_creatrice": creatrice,
                             "note": l.get("note") or info.get("note"), "url": l.get("url") or info.get("url")})
    return nouveaux


# ------------------------------------------------------------------ bouchons (10/10), retirés par le lot W
async def demarrer(client):
    """Bouchon : plus de salon #jonas-stats créé au démarrage."""
    return None


async def apres_releves(client, d: dict):
    """Bouchon : plus de rapport du manager après les relevés (le Dashboard donne les visites par clipper)."""
    return None


RETIRE_STATS = "Retiré le 10/10 : le Dashboard donne les visites par clipper."


async def commande_staff(message, texte: str) -> bool:
    """`!stats-jonas` et `!stats-manager` sont retirés : ils le disent. 11/10 (revue de L9a) : sans réponse ici, ils tombaient
    dans `!stats` de commande_admin (« 📊 N questions au total »), et `!equipe-active` dans `!equipe @membre fr` (« Format : … »).
    `!actifs` et `!equipe-active` donnent le roster compté (roster.texte_actifs). Le lot W GARDE cet appel dans on_message, avant
    commande_admin : retiré, `!stats-jonas` retomberait dans `!stats` (préfixe)."""
    premier = (texte.split() or [""])[0].lower()
    if premier in ("!actifs", "!equipe-active"):
        import roster
        await message.reply(roster.texte_actifs()[:1990])
        return True
    if premier in ("!stats-jonas", "!stats-manager"):
        await message.reply(RETIRE_STATS)
        return True
    return False
