"""Un @ Instagram n'est donné que s'il est libre (30/10/2026).

Gaëtan (30/10) : « Fais en sorte qu'on arrive vraiment à déterminer si les arobas des comptes Instagram qu'on va donner sont
disponibles ou pas. Il ne faut jamais donner un arobas qui n'est pas disponible. Je compte sur toi par rapport à ça. Comme ça, on
est sûr d'avoir la bonne attribution des clippers. »

Le cas réel qui le justifie (onglet « IG · À trancher », 29/10) : un clipper a reçu `journaldesarah`, un compte qui existait déjà
chez une inconnue (141 abonnés, une bio) ; il a créé une variante, et le suivi a perdu son compte.

Avant d'envoyer le message d'un compte (parcours.envoyer_etape), le bot demande à RapidAPI l'ID Instagram de ce @ (la même route que
le suivi, `instagram_rapidapi.API["id"]`) :

- un ID revient : le @ est **pris**. Il n'est jamais donné ; la ligne du classeur passe en Utilisation « @ pris sur Instagram » et
  une autre ligne est réservée (onboarding.remplacer_arobase_pris) ;
- Instagram ne connaît pas ce @ (introuvable) : il est **libre**, le message part ;
- pas de réponse claire (quota, erreur, délai) : **inconnu**. Le compte n'est pas envoyé, le bot réessaie au tour suivant. Jamais
  de @ donné sur un doute.

Le verdict « pris » est gardé pour toujours (DONNEES/arobases_verifies.json) ; « libre » vaut LIBRE_VALIDE_H heures, puis le @ est
revu. `!arobase @x` (staff) vérifie un @ à la main ; `!arobase-ok @x` le déclare libre après un contrôle humain sur Instagram.

Limites connues :
- un @ d'un compte supprimé ou banni peut rester bloqué par Instagram un moment tout en répondant « introuvable » : le clipper le
  dit alors avec le bouton « ✅ Compte créé » ou `!pseudo`, comme avant ;
- la vérification passe par une API tierce qui lit Instagram : c'est la même dette CGU Meta que le suivi RapidAPI.
Sans RAPIDAPI_KEY, ou avec AROBASE_VERIF=0, rien n'est vérifié (journal au démarrage) : l'ancien comportement."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

journal = logging.getLogger("arobase_libre")

LIBRE, PRIS, INCONNU = "libre", "pris", "inconnu"
ACTIVE = os.environ.get("AROBASE_VERIF", "1").strip() != "0"
LIBRE_VALIDE_H = int(os.environ.get("AROBASE_LIBRE_VALIDE_H", "6") or 6)
RESERVE_QUOTA = int(os.environ.get("AROBASE_RESERVE_QUOTA", "20") or 20)   # sous ce reste annoncé par RapidAPI : « inconnu »
DELAI_S = int(os.environ.get("AROBASE_DELAI_S", "25") or 25)
FICHIER = Path(os.environ.get("DONNEES_DIR", Path(__file__).with_name("donnees"))) / "arobases_verifies.json"


def norm(handle) -> str:
    return str(handle or "").strip().lower().lstrip("@")


def actif() -> bool:
    """Vrai quand le bot peut vérifier : interrupteur allumé et clé RapidAPI présente."""
    if not ACTIVE:
        return False
    try:
        import instagram_rapidapi as ig
        return bool(ig.CLE)
    except Exception:                                                   # noqa: BLE001
        return False


def _lire() -> dict:
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire(donnees: dict) -> None:
    try:
        FICHIER.parent.mkdir(parents=True, exist_ok=True)
        tmp = FICHIER.with_suffix(".tmp")
        tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FICHIER)
    except OSError as erreur:
        journal.warning("Vérifications des @ non écrites : %s", erreur)


def _noter(handle: str, etat: str, **extra) -> None:
    d = _lire()
    d[norm(handle)] = {"etat": etat, "le": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
    _ecrire(d)


def connu_pris(handle) -> bool:
    """Pur sur le fichier : ce @ a déjà été vu pris sur Instagram (sert à écarter la ligne des stocks, sans appel)."""
    return (_lire().get(norm(handle)) or {}).get("etat") == PRIS


def pris_connus() -> list:
    return sorted(h for h, e in _lire().items() if (e or {}).get("etat") == PRIS)


def forcer_libre(handle, par: str = "") -> None:
    """`!arobase-ok` : un humain a vérifié sur Instagram que le @ est libre (l'API se trompe, ou reste muette)."""
    _noter(handle, "force_libre", par=str(par))


def lire_reponse(code: int, corps) -> tuple:
    """Pur : (verdict, id) d'une réponse de la route « id » de RapidAPI. Un ID = pris ; introuvable = libre ; le reste = inconnu."""
    import instagram_rapidapi as ig
    i = ig.lire_id(corps) if code == 200 else None
    if i:
        return PRIS, i
    if ig.introuvable(code, corps) or (code == 200 and isinstance(corps, dict) and corps.get("status") is False):
        return LIBRE, None
    return INCONNU, None


def _encore_libre(e: dict) -> bool:
    try:
        le = datetime.fromisoformat(str(e.get("le")))
        le = le if le.tzinfo else le.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) - le < timedelta(hours=LIBRE_VALIDE_H)


async def verdict(handle) -> str:
    """LIBRE, PRIS ou INCONNU pour ce @, avant de le donner. Jamais d'exception. Sans vérification possible (actif() faux) : LIBRE,
    l'ancien comportement."""
    h = norm(handle)
    if not h:
        return INCONNU
    if not actif():
        return LIBRE
    e = _lire().get(h) or {}
    if e.get("etat") == PRIS:
        return PRIS
    if e.get("etat") == "force_libre" or (e.get("etat") == LIBRE and _encore_libre(e)):
        return LIBRE
    try:
        import aiohttp
        import instagram_rapidapi as ig
        if not ig._quota_ok(RESERVE_QUOTA):
            journal.warning("@%s non vérifié : quota RapidAPI trop bas", h)
            return INCONNU
        chemin, params = ig.API["id"]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DELAI_S)) as session:
            code, corps = await ig.appeler(session, chemin, params(h))
        resultat, i = lire_reponse(code, corps)
    except Exception as erreur:                                         # noqa: BLE001 — un doute, jamais un @ donné
        journal.warning("@%s non vérifié : %s", h, type(erreur).__name__)
        return INCONNU
    if resultat == INCONNU:
        journal.warning("@%s non vérifié : réponse RapidAPI %s", h, code)
        return INCONNU
    _noter(h, resultat, **({"id": i} if i else {}))
    journal.info("@%s vérifié sur Instagram : %s", h, resultat)
    return resultat
