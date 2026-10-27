"""Les comptes « à trancher » vérifiés sur Instagram par le suivi RapidAPI (27/10/2026).

Le bot (rapprochement_mail, sur Railway, sans accès à Instagram) écrit dans l'onglet « IG · À trancher » du tableur App clippers ·
usage chaque compte dont le @ donné au clipper sur Discord diffère du @ du classeur (même e-mail, ligne encore « à créer »). Ce
module, lancé par le suivi Instagram (GitHub Actions), regarde les deux @ sur Instagram (1 requête chacun, plus le profil s'il
existe : abonnés, publications, bio) et écrit le résultat sur la même ligne. Le bot décide ensuite (rapprochement_mail.decision).
Une ligne est revue au plus toutes les REVOIR_H heures ; jamais plus de PAR_PASSAGE lignes par passage."""
import logging
from datetime import datetime, timedelta, timezone

journal = logging.getLogger("a_trancher_ig")

ONGLET = "IG · À trancher"
ENTETE = ["@ reçu (Discord)", "@ du classeur", "Onglet", "Ligne", "Clipper", "Compte",
          "Reçu : statut", "Reçu : abonnés", "Reçu : publications", "Reçu : bio",
          "Classeur : statut", "Classeur : abonnés", "Classeur : publications", "Classeur : bio", "Vérifié le"]
COL_VERIF = 6                                                            # G : première colonne écrite par ce module
REVOIR_H = 20
PAR_PASSAGE = 20


def _instant(t):
    try:
        d = datetime.fromisoformat(str(t))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def a_verifier(lignes: list, maintenant: datetime) -> list:
    """Pur : [(numéro de ligne du tableur, @ reçu, @ du classeur)] à regarder, les plus anciennes vérifications d'abord."""
    out = []
    for i, l in enumerate(lignes or [], start=1):
        if i == 1 or len(l) < 2:
            continue
        recu, classeur = str(l[0] or "").strip().lower(), str(l[1] or "").strip().lower()
        if not recu or not classeur:
            continue
        le = _instant(l[14]) if len(l) > 14 else None
        if le is None or maintenant - le >= timedelta(hours=REVOIR_H):
            out.append((i, recu, classeur, le))
    out.sort(key=lambda x: x[3] or datetime.min.replace(tzinfo=timezone.utc))
    return [(i, r, c) for i, r, c, _ in out[:PAR_PASSAGE]]


async def _regarder(session, ig, handle: str):
    """[statut, abonnés, publications, bio] d'un @ ; None si la réponse est douteuse (quota, erreur) : revu au passage suivant."""
    chemin, params = ig.API["id"]
    code, corps = await ig.appeler(session, chemin, params(handle))
    i = ig.lire_id(corps) if code == 200 else None
    if not i:
        fini = ig.introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False)
        return ["introuvable", "", "", ""] if fini else None
    chemin, params = ig.API["profil"]
    code, corps = await ig.appeler(session, chemin, params(i))
    if code != 200 or not isinstance(corps, dict):
        return None
    p, b = ig.lire_profil(corps), ig.lire_bio(corps)
    return ["existe", p.get("followers") or 0, p.get("publications") or 0, str(b.get("bio") or "")[:200]]


async def verifier(session, maintenant: datetime = None) -> dict:
    """Un passage : lit l'onglet, regarde les deux @ des lignes dues, écrit le résultat ligne par ligne."""
    import google_api
    import instagram_rapidapi as ig
    import paie_clics
    maintenant = maintenant or datetime.now(timezone.utc)
    bilan = {"vues": 0, "ecrites": 0}
    classeur = await paie_clics._classeur_usage()
    if not classeur:
        return bilan
    try:
        lignes = await google_api.sheets_lire(classeur, f"'{ONGLET}'!A1:O")
    except Exception as erreur:                                         # noqa: BLE001 — onglet pas encore créé par le bot
        journal.info("À trancher : onglet illisible (%s)", str(erreur)[:120])
        return bilan
    for numero, recu, classeur_h in a_verifier(lignes, maintenant):
        if not ig._quota_ok(ig.RESERVE):
            break
        r = await _regarder(session, ig, recu)
        c = await _regarder(session, ig, classeur_h)
        bilan["vues"] += 1
        if r is None or c is None:
            continue
        await google_api.sheets_ecrire(classeur, f"'{ONGLET}'!G{numero}:O{numero}",
                                       [r + c + [maintenant.isoformat(timespec="seconds")]], brut=True)
        bilan["ecrites"] += 1
    if bilan["vues"]:
        journal.info("À trancher : %s ligne(s) regardée(s), %s écrite(s)", bilan["vues"], bilan["ecrites"])
    return bilan
