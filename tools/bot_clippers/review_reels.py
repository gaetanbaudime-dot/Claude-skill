"""Review des Reels des clippers (01/10/2026, Gaëtan : « Il faut qu'il soit capable de faire des reviews des Reels des clippeurs »).

Deux temps, une seule grille « publication » :

1. AVANT PUBLICATION (le plus utile) : un clipper dont le parcours a commencé envoie une vidéo dans son salon perso (ou en MP)
   → le bot la relit avec le juge vidéo du test de montage (ffprobe, images extraites par ffmpeg, modèle MODELE), mais avec la
   grille de publication : accroche dans la première seconde, sous-titres lisibles, vraie modification par rapport à la vidéo
   du Drive (pas un TOP 20 tel quel), format vertical, 7 à 30 secondes, texte à l'écran, et RISQUE CGU (nudité, contenu trop
   explicite, personne qui paraît mineure, lien ou @ à l'image → « ⛔ Ne la publie pas »). Réponse en 4 lignes au plus : note
   sur 10 et verdict, un point fort, une ou deux corrections. Un candidat en test de montage garde son circuit (bot_discord
   l'intercepte avant), jamais confondu. Juge en échec → aucune note, une phrase : « Je n'ai pas pu regarder ta vidéo… ».
2. APRÈS PUBLICATION (léger) : le scan Apify du matin (etats_comptes) connaît déjà, pour chaque Reel des dernières 24 h, son
   URL, son image de couverture, sa légende, ses dimensions et sa date. Un échantillon (REVIEW_REELS_MAX_JOUR, 30 par jour)
   est relu sur la seule couverture et la légende, sans autre appel Apify. Au plus UNE ligne par clipper et par jour dans le
   message du matin de son salon perso, seulement si une correction est utile ; le lundi, un résumé au salon du manager.

État dans DONNEES/review_reels.json ; empreintes des TOP 20 par créatrice dans DONNEES/review_reels_top20.json (construites en
tâche de fond, une fois par semaine, jamais pendant une relecture). Le module ne connaît pas bot_discord : tout passe par
`configurer(deps)`. Aucune donnée personnelle n'est écrite au journal (comptes et prénoms seulement dans l'état, sur le volume).
"""
import asyncio
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone

journal = logging.getLogger("review_reels")

# 01/10 (Gaëtan) : « 1 » par défaut, « 0 » coupe tout (relecture avant, relecture après, résumé du lundi, ligne proposée)
ACTIF = (os.environ.get("REVIEW_REELS", "1").strip() or "1") != "0"
AVANT_PROPOSER = int(os.environ.get("REVIEW_AVANT_PROPOSER", "5") or 5)        # la relecture est proposée pour les 5 premiers Reels
MAX_JOUR = int(os.environ.get("REVIEW_REELS_MAX_JOUR", "30") or 30)            # Reels publiés relus par jour, tous clippers confondus
# Garde-fou de coût (01/10) : un clipper qui enverrait 50 vidéos dans la journée ne coûte pas 50 relectures.
AVANT_MAX_CLIPPER_JOUR = int(os.environ.get("REVIEW_AVANT_MAX_JOUR", "15") or 15)
SEUIL = 7                                                                      # « ✅ Publie-la » à partir de 7/10, comme le test
DUREE_MIN, DUREE_MAX = 7, 30
TOP20_JOURS = 7                                                                # empreintes des TOP 20 refaites chaque semaine
ETATS_TEST = ("test_envoye", "test_rendu", "test_expire", "refuse")          # candidat en test : circuit du test, jamais la review

TEXTE_ECHEC = "Je n'ai pas pu regarder ta vidéo, réessaie dans 2 minutes."
LIGNE_PROPOSITION = "Avant de publier, envoie-moi ta vidéo ici : je te dis en 1 minute si elle est prête."

# Les risques CGU (01/10, Gaëtan : « nudité, contenu trop explicite, mineur apparent, lien ou @ à l'image → ne publie pas »)
# 06/10 (Gaëtan : « ton système trop de peau est faux, j'ai mis que des rush soft dans les drive ») : 14 clippers sur 15 avaient des
# Reels « à retirer » pour un décolleté ou un crop top. Les deux grilles disent maintenant ce qui est autorisé (le soft du Drive) et
# ce qui ne l'est pas (vraie nudité, acte sexuel) ; le doute profite à la vidéo, sauf pour un mineur.
RISQUES = {"nudite": "on voit de la nudité",
           "explicite": "c'est trop explicite pour Instagram",
           "mineur": "une personne paraît mineure",
           "lien": "un lien ou un @ se voit à l'image"}
# Les défauts, en catégories fixes : c'est ce qui permet de dire « la correction la plus fréquente » le lundi
DEFAUTS = {"accroche": "l'accroche de la 1re seconde", "sous_titres": "les sous-titres", "texte": "le texte à l'écran",
           "format": "le format vertical", "duree": "la durée", "copie": "une vidéo du Drive pas assez modifiée",
           "legende": "un lien ou un @ dans la légende", "couverture": "l'image de couverture", "autre": "autre"}
CORRECTION = {"copie": "Modifie-la : texte, coupes, musique, pas la vidéo du Drive telle quelle",
              "format": "Mets-la en vertical, format 9:16",
              "duree_courte": f"Allonge-la : {DUREE_MIN} secondes minimum",
              "duree_longue": f"Coupe-la : {DUREE_MAX} secondes maximum",
              "accroche": "Mets un texte qui accroche dès la 1re seconde",
              "sous_titres": "Grossis les sous-titres pour qu'on les lise",
              "texte": "Ajoute un texte à l'écran",
              "legende": "Enlève le lien ou le @ de la légende"}
# La même expression que le contrôle des légendes du scan (etats_comptes.RE_FAUTE, 28/09), recopiée pour rester autonome
RE_LIEN = re.compile(r"https?://|www\.|getallmylinks|gaml\.|\.fr/|\.app/|(?<![\w.])@[A-Za-z0-9_.]{3,}")

GRILLE_AVANT = (
    "Tu relis un Reel Instagram vertical qu'un clipper d'une agence va publier, monté à partir d'une vidéo de créatrice.{base} "
    "Tu vois {n} images prises à des moments différents de SA vidéo, et ses caractéristiques : {largeur}×{hauteur}, "
    "{duree:.0f} secondes.\n\n"
    "Grille de publication (10 points) : accroche de la première seconde, un texte ou une image forte qui donne envie de rester "
    "(3) ; vidéo vraiment modifiée par rapport à la vidéo de base : coupes, zoom, texte, sous-titres, son (3) ; texte à "
    "l'écran et sous-titres lisibles (2) ; format vertical 9:16 et durée entre 7 et 30 s (2).\n\n"
    "RISQUE CGU Instagram, à regarder sur CHAQUE image : nudité ou trop de peau (\"nudite\"), pose ou contenu trop explicite "
    "(\"explicite\"), une personne qui paraît avoir moins de 18 ans (\"mineur\"), un lien, une adresse web ou un @ écrit à "
    "l'image (\"lien\"). Sinon \"aucun\". En cas de doute sur un mineur, mets \"mineur\".\n\n"
    "Les vidéos viennent du Drive de la créatrice, déjà choisi SOFT par l'agence : un décolleté, un crop top, un maillot de "
    "bain, une tenue moulante ou courte, de la lingerie qui couvre, une pose sexy ou suggestive sont AUTORISÉS, c'est \"aucun\". "
    "\"nudite\" seulement si on voit un téton, un sexe ou des fesses nues, ou un vêtement transparent qui les montre. "
    "\"explicite\" seulement pour un acte sexuel, réel ou mimé, sans ambiguïté. En cas de doute sur \"nudite\" ou "
    "\"explicite\", mets \"aucun\" (le doute sur un mineur, lui, reste \"mineur\").\n\n"
    "Réponds UNIQUEMENT en JSON : {{\"note\": entier 0-10, \"differe_du_rush\": true/false, \"accroche\": true/false, "
    "\"sous_titres_lisibles\": true/false, \"texte_ecran\": true/false, \"risque\": \"aucun\" | \"nudite\" | \"explicite\" | "
    "\"mineur\" | \"lien\", \"defaut\": \"accroche\" | \"sous_titres\" | \"texte\" | \"format\" | \"duree\" | \"copie\" | "
    "\"autre\" | \"aucun\", \"bien\": \"1 point fort court\", \"a_corriger\": [1 ou 2 corrections concrètes et courtes]}}. "
    "Écris pour un élève de collège : 8 mots maximum par point, tutoiement, français, un geste à faire. Aucun mot technique "
    "(netteté, fondu, transition, rythme dynamique, recadrage, résolution, plan) : « Coupe plus tôt », « Zoome sur son visage », "
    "« Mets un texte dès la 1re seconde »."
)
GRILLE_APRES = (
    "Tu relis vite un Reel Instagram DÉJÀ publié par un clipper d'une agence. Tu vois seulement son image de couverture et sa "
    "légende. Format : {format}.{duree_txt}\n\nLégende : « {legende} »\n\n"
    "Note sur 10 : la couverture accroche (texte lisible ou image forte, visage ou action) (5) ; texte à l'écran lisible (3) ; "
    "légende courte, simple, sage (2).\n\n"
    "RISQUE CGU Instagram sur la couverture : nudité ou trop de peau (\"nudite\"), trop explicite (\"explicite\"), une personne "
    "qui paraît avoir moins de 18 ans (\"mineur\"), un lien ou un @ écrit à l'image (\"lien\"). Sinon \"aucun\". En cas de "
    "doute sur un mineur, mets \"mineur\".\n\n"
    "Les vidéos viennent du Drive de la créatrice, déjà choisi SOFT par l'agence : un décolleté, un crop top, un maillot de "
    "bain, une tenue moulante ou courte, de la lingerie qui couvre, une pose sexy ou suggestive sont AUTORISÉS, c'est \"aucun\". "
    "\"nudite\" seulement si on voit un téton, un sexe ou des fesses nues, ou un vêtement transparent qui les montre. "
    "\"explicite\" seulement pour un acte sexuel, réel ou mimé, sans ambiguïté. En cas de doute sur \"nudite\" ou "
    "\"explicite\", mets \"aucun\" (le doute sur un mineur, lui, reste \"mineur\").\n\n"
    "Réponds UNIQUEMENT en JSON : {{\"note\": entier 0-10, \"risque\": \"aucun\" | \"nudite\" | \"explicite\" | \"mineur\" | "
    "\"lien\", \"defaut\": \"accroche\" | \"texte\" | \"couverture\" | \"autre\" | \"aucun\", \"bien\": \"1 point fort court\", "
    "\"correction\": \"1 correction concrète pour le prochain Reel, 8 mots maximum, tutoiement, sans mot technique\"}}."
)

_deps: dict = {}
_construction = set()                                                         # créatrices dont les TOP 20 se calculent
_taches = set()


def configurer(deps: dict):
    global _deps
    _deps = deps


def actif() -> bool:
    return ACTIF and bool(_deps)


# ------------------------------------------------------------------ état
def _fichier():
    return _deps["FICHIER"]


def _lire() -> dict:
    d = _deps["lire_json"](_fichier(), {})
    for cle in ("avant", "a_relire", "relus", "lignes", "quota"):
        d.setdefault(cle, {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_fichier(), d)


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _jour() -> str:
    """Le jour de Paris (le même que le message du matin)."""
    return (_deps["heure_paris"]() if _deps.get("heure_paris") else _maintenant()).strftime("%Y-%m-%d")


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _premier_mot(t: str) -> str:
    t = re.split(r"\s+-\s+|\s", str(t or "").strip())[0] if str(t or "").strip() else ""
    return t


# ------------------------------------------------------------------ qui a droit à la relecture avant publication
def est_video(piece) -> bool:
    return (getattr(piece, "content_type", "") or "").startswith("video/") or \
        (getattr(piece, "filename", "") or "").lower().endswith((".mp4", ".mov", ".m4v", ".webm"))


def eligible(uid) -> bool:
    """01/10 : un clipper validé dont le parcours a commencé (fiche du parcours, étape 1 ou plus), jamais un candidat en test."""
    if not actif():
        return False
    uid = str(uid)
    etat = ((_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("etats") or {}).get(uid) or {}).get("etat", "")
    if etat in ETATS_TEST:
        return False
    fiche = _deps["lire_json"](_deps["FICHIER_PARCOURS"], {}).get(uid) or {}
    try:
        return int(fiche.get("etape", 0) or 0) >= 1
    except (TypeError, ValueError):
        return False


def video_a_relire(message) -> bool:
    """La vidéo jointe part à la relecture (et plus au marqueur « vidéo que tu ne peux pas voir »)."""
    if not actif() or not any(est_video(p) for p in getattr(message, "attachments", None) or []):
        return False
    if _deps.get("est_staff") and _deps["est_staff"](message.author):
        return False
    return eligible(message.author.id)


def quota_ok(uid) -> bool:
    q = _lire()["quota"].get(str(uid)) or {}
    return q.get("jour") != _jour() or int(q.get("n", 0) or 0) < AVANT_MAX_CLIPPER_JOUR


def _compter(uid):
    d = _lire()
    q = d["quota"].get(str(uid)) or {}
    if q.get("jour") != _jour():
        q = {"jour": _jour(), "n": 0}
    q["n"] = int(q.get("n", 0) or 0) + 1
    d["quota"][str(uid)] = q
    _ecrire(d)


def ligne_proposition(uid) -> str:
    """01/10 : la ligne ajoutée au message « ton compte peut publier » (et à l'étape 5), tant que le clipper a fait moins de
    REVIEW_AVANT_PROPOSER relectures ET publié moins de REVIEW_AVANT_PROPOSER Reels vus par le scan. Ensuite, plus proposée,
    mais toujours disponible."""
    if not actif():
        return ""
    uid = str(uid)
    faites = len(_lire()["avant"].get(uid) or [])
    fiche = _deps["lire_json"](_deps["FICHIER_PARCOURS"], {}).get(uid) or {}
    publies = sum(int((s or {}).get("vus", 0) or 0) for s in (fiche.get("reels") or {}).values() if isinstance(s, dict))
    return LIGNE_PROPOSITION if faites < AVANT_PROPOSER and publies < AVANT_PROPOSER else ""


# ------------------------------------------------------------------ les TOP 20 de la créatrice : la « vidéo de base »
def _image_reduite(chemin: str, t: float, largeur: int = 360) -> str:
    """Une image de la vidéo à `t` secondes, réduite (360 px de large : une image coûte ~300 jetons), en base64. '' si ratée."""
    with tempfile.TemporaryDirectory() as tmp:
        sortie = os.path.join(tmp, "i.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", chemin, "-frames:v", "1",
                        "-vf", f"scale={largeur}:-2", "-q:v", "6", sortie], capture_output=True, timeout=60)
        if not os.path.exists(sortie):
            return ""
        with open(sortie, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")


def _fichier_top20():
    return _deps.get("FICHIER_TOP20")


def references(creatrice: str) -> list:
    """Les TOP 20 connus de la créatrice : [{nom, duree, empreintes (hex), image}]. Jamais d'appel réseau ici : sans cache (ou
    cache de plus de TOP20_JOURS jours), la construction part en tâche de fond et cette relecture se fait sans vidéo de base."""
    if not creatrice or not _fichier_top20():
        return []
    cache = (_deps["lire_json"](_fichier_top20(), {}) or {}).get(creatrice) or {}
    try:
        age = (_maintenant() - datetime.fromisoformat(cache.get("quand", ""))).days
    except ValueError:
        age = 999
    if age >= TOP20_JOURS and _deps.get("top20_auto", True):
        try:
            tache = asyncio.get_running_loop().create_task(construire_top20(creatrice))
            _taches.add(tache)                                                 # gardée jusqu'à la fin (sinon le ramasse-miettes)
            tache.add_done_callback(_taches.discard)
        except RuntimeError:                                                   # pas de boucle (appel synchrone) : rien
            pass
    return list(cache.get("items") or [])


async def construire_top20(creatrice: str) -> int:
    """Télécharge une fois les TOP 20 de la créatrice (dossier « TOP 20 Reels » de son Drive, comme reels_uniques), garde pour
    chacun sa durée, 3 empreintes 16×16 et une image réduite. Un seul calcul à la fois par créatrice. Renvoie le nombre gardé."""
    if creatrice in _construction or not shutil.which("ffmpeg") or not all(
            _deps.get(k) for k in ("dossier_top20", "videos_top20", "drive_telecharger", "ffprobe", "empreintes")):
        return 0
    _construction.add(creatrice)
    items = []
    try:
        top_id, _ = await _deps["dossier_top20"](creatrice)
        if not top_id:
            return 0
        for v in await _deps["videos_top20"](top_id):
            try:
                donnees = await _deps["drive_telecharger"](v["id"], 80_000_000)
                with tempfile.TemporaryDirectory() as tmp:
                    chemin = os.path.join(tmp, "top.mp4")
                    with open(chemin, "wb") as f:
                        f.write(donnees)
                    meta = await asyncio.to_thread(_deps["ffprobe"], chemin)
                    duree = float(meta.get("duree") or 0)
                    emp = await asyncio.to_thread(_deps["empreintes"], chemin, duree or 10)
                    image = await asyncio.to_thread(_image_reduite, chemin, (duree or 10) * 0.25)
                items.append({"nom": str(v.get("name") or "")[:80], "duree": duree, "empreintes": [e.hex() for e in emp],
                              "image": image})
            except Exception as erreur:                                        # noqa: BLE001 — une vidéo ratée n'arrête rien
                journal.warning("TOP 20 (empreinte) : %s", type(erreur).__name__)
        if items:
            cache = _deps["lire_json"](_fichier_top20(), {}) or {}
            cache[creatrice] = {"quand": _maintenant().isoformat(timespec="seconds"), "items": items}
            _deps["ecrire_json"](_fichier_top20(), cache)
            journal.info("TOP 20 d'une créatrice prêts pour la relecture : %d vidéo(s)", len(items))
    except Exception as erreur:                                                # noqa: BLE001
        journal.warning("TOP 20 pour la relecture : %s", type(erreur).__name__)
    finally:
        _construction.discard(creatrice)
    return len(items)


def _ecart(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / 256.0 if a and b and len(a) == len(b) else 255.0


def plus_proche(emp: list, duree: float, refs: list):
    """(référence la plus proche, écart moyen des 3 empreintes, durée compatible) ; (None, 255, False) sans référence."""
    meilleur, ecart_min, duree_ok = None, 255.0, False
    for r in refs:
        emp_r = [bytes.fromhex(x) for x in (r.get("empreintes") or []) if x]
        ecarts = [_ecart(a, b) for a, b in zip(emp or [], emp_r)]
        if not ecarts:
            continue
        moyen = sum(ecarts) / len(ecarts)
        if moyen < ecart_min:
            # Les Reels uniques bougent la vitesse de ±4 % et coupent jusqu'à 0,5 s : tolérance de 6 % (1,5 s au moins)
            tol = max(1.5, 0.06 * float(r.get("duree") or 0))
            meilleur, ecart_min, duree_ok = r, moyen, abs(float(r.get("duree") or 0) - float(duree or 0)) <= tol
    return meilleur, ecart_min, duree_ok


def copie_du_top20(emp: list, duree: float, refs: list) -> bool:
    """Probable copie d'un TOP 20 (ou de sa variante « Reels uniques ») : même durée à 6 % près et les 3 images quasi
    identiques. Les variantes changent couleurs et zoom de quelques pour cent : le seuil (14) est plus large que celui du test."""
    r, ecart, duree_ok = plus_proche(emp, duree, refs)
    return r is not None and duree_ok and ecart < 14


# ------------------------------------------------------------------ AVANT publication : contenu, lecture, texte
def contenu_avant(images: list, meta: dict, base_image: str = "", nom_fichier: str = "") -> list:
    """Les blocs envoyés au modèle : l'image de la vidéo de base si on la connaît, puis les images du clipper et la grille."""
    img = lambda b: {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b}}   # noqa: E731
    contenu = []
    if base_image:
        contenu += [{"type": "text", "text": "Image de la VIDÉO DE BASE du Drive, avant montage :"}, img(base_image),
                    {"type": "text", "text": "Images de la VIDÉO DU CLIPPER :"}]
    contenu += [img(b) for b in images]
    base_txt = (" Tu vois d'abord une image de la vidéo de base du Drive, pour juger ce que le clipper a changé." if base_image else "")
    if re.search(r"·\s*Reel\s*\d+\s*·", nom_fichier or ""):
        base_txt += " Le fichier porte encore le nom du Drive : regarde bien s'il a vraiment été modifié."
    contenu.append({"type": "text", "text": GRILLE_AVANT.format(n=len(images), base=base_txt,
                                                                 largeur=int(meta.get("largeur") or 0),
                                                                 hauteur=int(meta.get("hauteur") or 0),
                                                                 duree=float(meta.get("duree") or 0))})
    return contenu


def _json(brut: str) -> dict:
    m = re.search(r"\{.*\}", brut or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _phrase(t) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip().rstrip(".!").strip()[:120]


def lire_avis_avant(brut: str, meta: dict, copie: bool = False) -> dict:
    """La réponse du modèle + les règles fixes (format, durée, copie, risque). {"erreur"} si la réponse est illisible : jamais
    de note inventée."""
    avis = _json(brut)
    try:
        note = int(avis.get("note", -1))
    except (TypeError, ValueError):
        note = -1
    if not 0 <= note <= 10:
        return {"erreur": "réponse du modèle illisible"}
    risque = str(avis.get("risque") or "aucun").strip().lower()
    risque = risque if risque in RISQUES else ""
    fixes = []                                                                # (défaut, correction) des règles fixes
    if copie or avis.get("differe_du_rush") is False:
        note = min(note, 3)
        fixes.append(("copie", CORRECTION["copie"]))
    largeur, hauteur, duree = int(meta.get("largeur") or 0), int(meta.get("hauteur") or 0), float(meta.get("duree") or 0)
    if largeur and hauteur and hauteur <= largeur:
        fixes.append(("format", CORRECTION["format"]))
    if duree and duree < DUREE_MIN:
        fixes.append(("duree", CORRECTION["duree_courte"]))
    elif duree > DUREE_MAX:
        fixes.append(("duree", CORRECTION["duree_longue"]))
    modele = [_phrase(c) for c in (avis.get("a_corriger") or []) if _phrase(c)]
    if avis.get("accroche") is False and not modele:
        modele.append(CORRECTION["accroche"])
    if avis.get("sous_titres_lisibles") is False and len(modele) < 2:
        modele.append(CORRECTION["sous_titres"])
    if avis.get("texte_ecran") is False and len(modele) < 2:
        modele.append(CORRECTION["texte"])
    corrections = list(dict.fromkeys([c for _, c in fixes] + modele))[:2]
    defaut = fixes[0][0] if fixes else str(avis.get("defaut") or "").strip().lower()
    defaut = defaut if defaut in DEFAUTS else ("autre" if corrections else "")
    if fixes:                                                                 # une règle fixe ratée : jamais « ✅ »
        note = min(note, SEUIL - 1)
    verdict = "risque" if risque else ("publie" if note >= SEUIL else "corrige")
    if verdict == "corrige" and not corrections:
        corrections = [CORRECTION["accroche"]]
        defaut = defaut or "accroche"
    return {"note": note, "verdict": verdict, "risque": risque, "defaut": defaut if verdict != "publie" or corrections else "",
            "bien": _phrase(avis.get("bien") if not isinstance(avis.get("bien"), list) else (avis.get("bien") or [""])[0]),
            "a_corriger": corrections, "copie": bool(copie), "meta": meta}


def _minuscule(t: str) -> str:
    return t[:1].lower() + t[1:] if t else t


def texte_avant(avis: dict) -> str:
    """4 lignes au plus : la note et le verdict d'abord, un point fort, une ou deux corrections. Ligne vide après le verdict."""
    if not avis or avis.get("erreur"):
        return TEXTE_ECHEC
    note, corr = avis["note"], list(avis.get("a_corriger") or [])
    if avis["verdict"] == "risque":
        tete, reste = f"⛔ Ne la publie pas : {RISQUES.get(avis.get('risque'), 'risque pour le compte')}.", []
    elif avis["verdict"] == "publie":
        tete, reste = "✅ Publie-la.", corr[:1]
    else:
        tete, reste = f"✏️ Corrige d'abord : {_minuscule(corr[0])}.", corr[1:2]
    lignes = ([f"👍 {avis['bien']}"] if avis.get("bien") else []) + [f"✏️ {c}" for c in reste]
    return f"🎬 **{note}/10** · {tete}" + ("\n\n" + "\n".join(lignes) if lignes else "")


def noter_avant(uid, avis: dict):
    """Garde la relecture (date, note, verdict, défaut, risque) pour le résumé du lundi. Une relecture ratée ne compte pas."""
    if not avis or avis.get("erreur"):
        return
    d = _lire()
    liste = d["avant"].setdefault(str(uid), [])
    liste.append({"date": _maintenant().isoformat(timespec="seconds"), "note": avis["note"], "verdict": avis["verdict"],
                  "defaut": avis.get("defaut", ""), "risque": avis.get("risque", "")})
    del liste[:-60]
    _ecrire(d)


async def relire_avant(message) -> str:
    """La relecture d'une vidéo reçue d'un clipper éligible : le texte posté en réponse. Juge en échec → TEXTE_ECHEC, rien noté."""
    uid = str(message.author.id)
    if not quota_ok(uid):
        return (f"Tu m'as déjà montré {AVANT_MAX_CLIPPER_JOUR} vidéos aujourd'hui.\n\n"
                "Publie celles qui sont prêtes. Je regarde les suivantes demain.")
    try:
        avis = await _deps["juger_avant"](message)
    except Exception as erreur:                                                # noqa: BLE001 — jamais de note inventée
        journal.warning("Relecture avant publication : %s", type(erreur).__name__)
        avis = {"erreur": type(erreur).__name__}
    if avis and not avis.get("erreur"):
        _compter(uid)
        noter_avant(uid, avis)
        if avis.get("risque") == "mineur" and _deps.get("alerter"):          # mineurs : non négociable, l'équipe le sait
            try:
                await _deps["alerter"](f"⛔ Relecture avant publication : une personne paraît mineure sur la vidéo de <@{uid}>. "
                                       "Je lui ai dit de ne pas la publier. À vérifier.")
            except Exception as erreur:                                        # noqa: BLE001
                journal.warning("Alerte mineur : %s", type(erreur).__name__)
    return texte_avant(avis)


# ------------------------------------------------------------------ APRÈS publication : ce que le scan sait déjà
def enregistrer_publies(jour: str, reels: list) -> int:
    """Appelé par le scan du matin (etats_comptes) : les Reels des dernières 24 h des comptes de clippers, avec URL, couverture,
    légende, dimensions, date. Gardés à relire (dédoublonnés par URL) ; rien n'est relu ici. Renvoie le nombre de nouveaux."""
    if not actif() or not reels:
        return 0
    d = _lire()
    nouveaux = 0
    for r in reels:
        url = str(r.get("url") or "").strip()
        if not url or url in d["a_relire"] or url in d["relus"]:
            continue
        d["a_relire"][url] = {"jour": jour, "handle": str(r.get("handle") or "").lower(), "gerant": _premier_mot(r.get("gerant")),
                              "image": str(r.get("image") or ""), "legende": str(r.get("legende") or "")[:400],
                              "quand": str(r.get("quand") or ""), "largeur": int(r.get("largeur") or 0),
                              "hauteur": int(r.get("hauteur") or 0), "duree": float(r.get("duree") or 0)}
        nouveaux += 1
    if nouveaux:
        _ecrire(d)
    return nouveaux


def echantillon(a_relire: dict, budget: int) -> list:
    """Au plus `budget` URL, réparties entre les clippers (un Reel de chacun à tour de rôle, le plus récent d'abord)."""
    par = {}
    for url, r in sorted(a_relire.items(), key=lambda kv: kv[1].get("quand", ""), reverse=True):
        par.setdefault(_norm(r.get("gerant")), []).append(url)
    choisis = []
    while len(choisis) < budget and any(par.values()):
        for g in sorted(par):
            if par[g] and len(choisis) < budget:
                choisis.append(par[g].pop(0))
    return choisis


def contenu_apres(image_b64: str, r: dict) -> list:
    largeur, hauteur = int(r.get("largeur") or 0), int(r.get("hauteur") or 0)
    fmt = (f"{largeur}×{hauteur}, " + ("vertical" if hauteur > largeur else "PAS vertical")) if largeur and hauteur else "inconnu"
    duree = float(r.get("duree") or 0)
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
            {"type": "text", "text": GRILLE_APRES.format(format=fmt, duree_txt=(f" Durée : {duree:.0f} s." if duree else ""),
                                                         legende=(r.get("legende") or "(vide)")[:400])}]


def lire_avis_apres(brut: str, r: dict) -> dict:
    """La réponse du modèle + les règles fixes (légende avec lien ou @, format, durée). {"erreur"} si illisible."""
    avis = _json(brut)
    try:
        note = int(avis.get("note", -1))
    except (TypeError, ValueError):
        note = -1
    if not 0 <= note <= 10:
        return {"erreur": "réponse du modèle illisible"}
    risque = str(avis.get("risque") or "").strip().lower()
    risque = risque if risque in RISQUES else ""
    correction, defaut = _phrase(avis.get("correction")), str(avis.get("defaut") or "").strip().lower()
    largeur, hauteur, duree = int(r.get("largeur") or 0), int(r.get("hauteur") or 0), float(r.get("duree") or 0)
    if RE_LIEN.search(r.get("legende") or ""):
        correction, defaut, note = CORRECTION["legende"], "legende", min(note, SEUIL - 1)
    elif largeur and hauteur and hauteur <= largeur:
        correction, defaut, note = CORRECTION["format"], "format", min(note, SEUIL - 1)
    elif duree and (duree < DUREE_MIN or duree > DUREE_MAX):
        correction, defaut = CORRECTION["duree_courte" if duree < DUREE_MIN else "duree_longue"], "duree"
    defaut = defaut if defaut in DEFAUTS else ("autre" if correction else "")
    utile = bool(risque) or (bool(correction) and note < SEUIL) or defaut in ("legende", "format")
    return {"note": note, "risque": risque, "defaut": defaut if utile else "", "correction": correction if utile else "",
            "bien": _phrase(avis.get("bien"))}


def ligne_clipper(avis_du_jour: list) -> str:
    """UNE ligne pour le clipper, sur le Reel d'hier qui en a le plus besoin ; '' si aucune correction n'est utile."""
    a_dire = [a for a in avis_du_jour if a.get("risque") or a.get("correction")]
    if not a_dire:
        return ""
    a = sorted(a_dire, key=lambda x: (not x.get("risque"), x.get("defaut") != "legende", x.get("note", 10)))[0]
    if a.get("risque"):
        return f"⛔ Ton Reel d'hier : {RISQUES[a['risque']]}. Retire-le d'Instagram : <{a.get('url', '')}>"
    return f"✏️ Ton Reel d'hier : {_minuscule(a['correction'])}. Fais-le dès le prochain."


async def _image_couverture(url: str) -> str:
    """La couverture du Reel (lien de l'image donné par le scan, valable quelques jours), réduite si ffmpeg est là. '' si ratée."""
    if not url or not _deps.get("telecharger"):
        return ""
    donnees = await _deps["telecharger"](url)
    if not donnees:
        return ""
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, "c.jpg"), os.path.join(tmp, "r.jpg")
            with open(src, "wb") as f:
                f.write(donnees)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=360:-2", "-q:v", "6", dst],
                           capture_output=True, timeout=60)
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    donnees = f.read()
    return base64.standard_b64encode(donnees).decode("utf-8")


async def relire_publies(client=None) -> dict:
    """Un passage : relit l'échantillon du jour (plafond MAX_JOUR, compté sur la journée), puis pose au plus une ligne par
    clipper dans son message du matin. Renvoie {"relus", "lignes"}. Le juge en échec : le Reel n'est pas noté (2 essais)."""
    bilan = {"relus": 0, "lignes": 0}
    if not actif() or not _deps.get("juger"):
        return bilan
    jour = _jour()
    d = _lire()
    limite = (date.fromisoformat(jour) - timedelta(days=2)).isoformat()
    for url in [u for u, r in d["a_relire"].items() if str(r.get("jour", "")) < limite]:   # couvertures périmées : oubliées
        d["a_relire"].pop(url, None)
    deja = sum(1 for r in d["relus"].values() if r.get("relu") == jour and not r.get("erreur"))
    budget = max(0, MAX_JOUR - deja)
    _ecrire(d)
    for url in echantillon(d["a_relire"], budget):
        r = _lire()["a_relire"].get(url)
        if not r:
            continue
        avis = {"erreur": "couverture illisible"}
        try:
            image = await _image_couverture(r.get("image", ""))
            if image:
                avis = lire_avis_apres(await _deps["juger"](contenu_apres(image, r)), r)
        except Exception as erreur:                                            # noqa: BLE001
            avis = {"erreur": type(erreur).__name__}
        d = _lire()
        if avis.get("erreur"):
            r["essais"] = int(r.get("essais", 0) or 0) + 1
            if r["essais"] >= 2:                                               # deux échecs : on n'insiste pas, rien n'est noté
                d["a_relire"].pop(url, None)
            else:
                d["a_relire"][url] = r
            _ecrire(d)
            continue
        d["a_relire"].pop(url, None)
        d["relus"][url] = {**avis, "url": url, "gerant": r.get("gerant", ""), "handle": r.get("handle", ""),
                           "jour": r.get("jour", jour), "relu": jour}
        _ecrire(d)
        bilan["relus"] += 1
    bilan["lignes"] = await poser_lignes(jour)
    _nettoyer()
    if bilan["relus"]:
        journal.info("Reels publiés relus : %d, lignes aux clippers : %d", bilan["relus"], bilan["lignes"])
    return bilan


async def poser_lignes(jour: str) -> int:
    """Au plus une ligne par clipper et par jour, dans le message du matin (matin.deposer). Le message du matin déjà parti : la
    ligne part seule dans son salon, mais seulement dans la fenêtre du matin (jamais d'envoi groupé l'après-midi ni au
    redémarrage) ; sinon elle reste pour le résumé du lundi."""
    d = _lire()
    par = {}
    for r in d["relus"].values():
        if r.get("relu") == jour and r.get("gerant"):
            par.setdefault(_norm(r["gerant"]), []).append(r)
    poses = 0
    for g, avis in par.items():
        if d["lignes"].get(g) == jour:
            continue
        ligne = ligne_clipper(avis)
        if not ligne:
            continue
        salon_id = _deps["salon_de_prenom"](avis[0]["gerant"]) if _deps.get("salon_de_prenom") else None
        if not salon_id:
            continue
        envoye = bool(_deps.get("deposer") and _deps["deposer"](salon_id, "review", ligne))
        if not envoye and _deps.get("dans_fenetre_matin", lambda: False)() and _deps.get("envoyer_salon"):
            try:
                envoye = bool(await _deps["envoyer_salon"](salon_id, ligne))
            except Exception as erreur:                                        # noqa: BLE001
                journal.warning("Ligne de review : %s", type(erreur).__name__)
        if envoye:
            d = _lire()
            d["lignes"][g] = jour
            _ecrire(d)
            poses += 1
    return poses


def _nettoyer():
    """Relectures de plus de 21 jours, quotas et lignes d'avant-hier : effacés."""
    d = _lire()
    limite = (_maintenant() - timedelta(days=21)).date().isoformat()
    d["relus"] = {u: r for u, r in d["relus"].items() if str(r.get("relu", "")) >= limite}
    for uid in list(d["avant"]):
        d["avant"][uid] = [a for a in d["avant"][uid] if str(a.get("date", ""))[:10] >= limite]
        if not d["avant"][uid]:
            d["avant"].pop(uid)
    d["lignes"] = {g: j for g, j in d["lignes"].items() if j >= limite}
    _ecrire(d)


# ------------------------------------------------------------------ le résumé du lundi
def _virgule(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def resume_semaine(fin: date, prenom_de_uid=None) -> str:
    """Les 7 jours qui finissent la veille de `fin` (le lundi : lundi → dimanche d'avant), par clipper : Reels relus, note
    moyenne, la correction la plus fréquente, les Reels « ⛔ risque » à retirer, et les vidéos montrées avant. '' si rien."""
    debut = (fin - timedelta(days=7)).isoformat()
    fin_s = fin.isoformat()
    d = _lire()
    par = {}
    for r in d["relus"].values():
        if debut <= str(r.get("jour", "")) < fin_s and r.get("gerant"):
            par.setdefault(_norm(r["gerant"]), {"nom": r["gerant"], "apres": [], "avant": []})["apres"].append(r)
    for uid, liste in d["avant"].items():
        semaine = [a for a in liste if debut <= str(a.get("date", ""))[:10] < fin_s]
        if not semaine:
            continue
        nom = (prenom_de_uid(uid) if prenom_de_uid else "") or f"<@{uid}>"
        par.setdefault(_norm(nom), {"nom": nom, "apres": [], "avant": []})["avant"] += semaine
    if not par:
        return ""
    jj = lambda s: f"{s[8:10]}/{s[5:7]}"                                       # noqa: E731
    lignes = [f"🎬 **Review des Reels · du {jj(debut)} au {jj((fin - timedelta(days=1)).isoformat())}**"]
    for _, p in sorted(par.items()):
        tous = p["apres"] + p["avant"]
        morceaux = []
        if p["apres"]:
            morceaux.append(f"{len(p['apres'])} Reel(s) publiés relus")
        if p["avant"]:
            morceaux.append(f"{len(p['avant'])} vidéo(s) montrée(s) avant")
        morceaux.append(f"{_virgule(sum(int(a.get('note', 0)) for a in tous) / len(tous))}/10")
        frequents = Counter(a.get("defaut") for a in tous if a.get("defaut") and a.get("defaut") != "autre").most_common(1)
        if frequents:
            morceaux.append(f"à corriger le plus : {DEFAUTS[frequents[0][0]]}")
        bloc = f"**{p['nom']}** : " + " · ".join(morceaux)
        risques = [a for a in p["apres"] if a.get("risque")]
        if risques:
            bloc += "\n⛔ À retirer : " + " · ".join(f"<{a['url']}> ({RISQUES[a['risque']]})" for a in risques[:5])
        lignes.append(bloc)
    return "\n\n".join(lignes)


async def resume_lundi(force: bool = False) -> bool:
    """Le lundi (heure de Paris, à partir de 9 h), une fois par semaine : le résumé au salon du manager (canal_manager, qui
    retombe sur le salon admin). Un lundi manqué (bot éteint) ne se rattrape pas le mardi : pas d'envoi en retard."""
    if not actif() or not _deps.get("canal_manager"):
        return False
    maintenant = _deps["heure_paris"]() if _deps.get("heure_paris") else _maintenant()
    semaine = maintenant.strftime("%G-W%V")
    d = _lire()
    if not force and (maintenant.weekday() != 0 or maintenant.hour < 9 or d.get("hebdo") == semaine):
        return False
    texte = resume_semaine(maintenant.date(), _deps.get("prenom_de_uid"))
    d["hebdo"] = semaine                                                       # écrit AVANT l'envoi : jamais deux fois
    _ecrire(d)
    if not texte:
        return False
    canal = await _deps["canal_manager"]()
    if canal is None:
        return False
    morceau = ""
    for bloc in texte.split("\n\n"):                                          # limite Discord : 2 000 caractères par message
        if len(morceau) + len(bloc) + 2 > 1900:
            await canal.send(morceau)
            morceau = ""
        morceau = f"{morceau}\n\n{bloc}" if morceau else bloc
    if morceau:
        await canal.send(morceau)
    return True


async def boucle(client) -> None:
    """Toutes les 10 minutes : les Reels publiés à relire (après le scan du matin) et le résumé du lundi."""
    if not ACTIF:
        journal.info("Review des Reels coupée (REVIEW_REELS=0)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if _lire()["a_relire"]:
                await relire_publies(client)
            await resume_lundi()
        except Exception as erreur:                                            # noqa: BLE001 — la boucle ne meurt jamais
            journal.warning("Boucle de review des Reels : %s", type(erreur).__name__)
        await asyncio.sleep(600)
