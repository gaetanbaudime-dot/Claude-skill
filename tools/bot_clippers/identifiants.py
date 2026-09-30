"""Identifiants neufs par créatrice (30/09, Gaëtan : « prépare-moi 20 username et mdp nouveaux pour chaque créatrice ; garde le
branding de la créatrice en te basant sur les @ déjà existants ; originaux et de préférence disponibles sur Instagram ; un chiffre,
ou "xo", "x", ".", "_" en fin ou en liaison ; pour toutes les créatrices d'un coup »).

Tout se calcule AU MOMENT, dans le bot, à partir du classeur : rien de ces identifiants ni des pseudos existants n'est écrit
dans le dépôt (règle de sécurité : jamais de handles ni de mots de passe commités).
  1. Les pseudos de chaque onglet sont découpés en mots (prénom de la créatrice, mots de style connus, et le reste = mots de
     marque : le nom de scène et ses variantes, ce qui reste une fois prénom et mots de style retirés).
  2. Des candidats combinent prénom / mots de marque / mots de style, avec une liaison (« », « . », « _ ») et une touche
     finale (« xo », « x », « _ », un nombre) ; jamais un pseudo du classeur, ni son double à la ponctuation près.
  3. Les candidats passent au scan Instagram (Apify, comme les états des comptes) : seuls ceux que le scan ne trouve pas
     sont gardés (« libres » : probable, pas garanti — Instagram bloque aussi les noms de comptes supprimés).
  4. Mot de passe neuf pour chacun (module `secrets`), jamais celui d'une ligne du classeur.
La réserve (CIBLE par créatrice) est gardée sur le volume ; un identifiant qui apparaît dans un onglet est considéré comme
utilisé et remplacé au passage suivant."""
import logging
import os
import random
import re
import secrets
import unicodedata
from datetime import datetime, timezone

journal = logging.getLogger("bot.identifiants")
CIBLE = int(os.environ.get("IDENTIFIANTS_PAR_CREATRICE", "20") or 20)
_deps: dict = {}

# Mots de style (fr/en) : servent à découper les pseudos existants et à en fabriquer de nouveaux.
STYLE = sorted(set("""la le les its iam i am the petite petit vraie vrai backstage coulisses coulisse secret secrets prive privee prv
daily diary journal club vip clic mood vibes vibe gaming game plays parle level live en hors horsgame apres garde images image photo
photos pause captured capture blouse sans filtre signature room enprive campus life girl cute pretty douce douceur nomade route voyage
libre boheme sur de du jesuis cest off offline after story stories cafe chill soft only me my her un une chez avec moi toi nuit
matin weekend week love lov real side""".split()), key=len, reverse=True)
# Mots d'ambiance (pseudos sans prénom, style Maddie) : découpage des pseudos existants et nouvelles combinaisons.
AMBIANCE = sorted(set("""quiet morning side somewhere soft window seat story midnight postcard halo secret weekend detour cloud clouds
after five velvet tiny city lights light moon nothing serious here softly offline orbit another wrong turn late checkout slow days
only echo paper planes plane mood again nox ordinary escape blurry weekends muse noon just one iris map today passing by lost seven
lune nova golden hour sunday rain honey dusk dawn cherry vanilla silk satin pearl blue hazy daydream window seats notes letters
postcards somewhere else nowhere wander wanderer sleepy dreamy dream dreams calm bloom petals lavender film roll analog""".split()),
                  key=len, reverse=True)
# Mots-outils : servent au découpage, jamais comme mot final d'un pseudo neuf.
OUTILS = {"la", "le", "les", "its", "iam", "i", "am", "the", "en", "de", "du", "sur", "cest", "jesuis", "chez", "avec", "un", "une",
          "my", "me", "her", "moi", "toi", "apres", "hors", "sans", "petite", "petit", "vraie", "vrai", "garde", "parle", "only", "side"}
JOLIS = ["club", "vip", "diary", "daily", "secret", "mood", "vibes", "room", "life", "story", "cafe", "soft", "coulisses", "backstage",
         "journal", "prive", "privee", "offline", "after", "nuit", "weekend", "real", "cute", "pretty", "douce", "nomade", "voyage",
         "libre", "photo", "pause", "signature", "campus", "live", "capture", "filtre", "chill", "love"]
PREFIXES = ("la", "its", "iam", "lavraie", "lapetite", "cest", "hey", "just", "only")
FINS = ("xo", ".xo", "_xo", "x", "_x", ".x", "_", "__", ".off", "_off", ".life", "_club", ".club", ".vip", "_vip")
LIAISONS = ("", ".", "_")
MOTS_MDP = ("Glow", "Velvet", "Orbit", "Nova", "Muse", "Lune", "Poeme", "Quartz", "Amber", "Echo", "Halo", "Iris", "Opal", "Pearl",
            "Satin", "Silk", "Cloud", "Coral", "Ivory", "Aura", "Lotus", "Solstice", "Comet", "Maple", "Breeze", "Cedar", "Flora")
SYMBOLES = "!#%*@&?"
RE_VALIDE = re.compile(r"^[a-z0-9](?:[a-z0-9_]|\.(?!\.))*[a-z0-9_]$")


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (réserve), scanner (async [handles] -> {handle: {existe…}} ou None)."""
    _deps.update(deps)


def _ascii(t: str) -> str:
    return unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()


def _cle_creatrice(nom: str) -> str:
    return re.sub(r"[^a-z]", "", _ascii(nom).split()[0] if _ascii(nom).split() else "")


def variantes_prenom(nom: str) -> list:
    """« Maddie » → ["maddie", "maddy"] ; « Chloé » → ["chloe"]."""
    k = _cle_creatrice(nom)
    out = [k] if k else []
    if k.endswith("ie"):
        out.append(k[:-2] + "y")
    elif k.endswith("y"):
        out.append(k[:-1] + "ie")
    return out


def _squash(h: str) -> str:
    return re.sub(r"[._]", "", h.lower())


def decouper(morceau: str, connus: list) -> list:
    """Découpe « lapetitesarahiva » avec les mots connus : ["la", "petite", "sarah", "iva"]. Programmation dynamique : une
    lettre non reconnue coûte 1, un mot reconnu 0,6 (peu de morceaux), un reste contigu forme un seul mot (mot de marque) ;
    un mot connu de moins de 3 lettres n'est pris qu'en tête (« la », « le »), sinon un nom de scène était haché en petits morceaux."""
    n = len(morceau)
    meilleur = [(0.0, [])] + [None] * n                                # (coût, découpage) pour morceau[:i]
    for i in range(n):
        if meilleur[i] is None:
            continue
        cout, parts = meilleur[i]
        for mot in connus:
            if (len(mot) >= 3 or i == 0) and morceau.startswith(mot, i):
                j = i + len(mot)
                cand = (cout + 0.6, parts + [("mot", mot)])
                if meilleur[j] is None or cand[0] < meilleur[j][0]:
                    meilleur[j] = cand
        j = i + 1                                                       # une lettre inconnue, collée au reste inconnu
        nouv = (parts[:-1] + [("inconnu", parts[-1][1] + morceau[i])]) if parts and parts[-1][0] == "inconnu" else parts + [("inconnu", morceau[i])]
        cand = (cout + 1, nouv)
        if meilleur[j] is None or cand[0] < meilleur[j][0]:
            meilleur[j] = cand
    return [m for _, m in (meilleur[n] or (0, []))[1]]


def vocabulaire(handles: list, creatrice: str) -> dict:
    """{"prenoms", "marques", "style", "ambiance", "part_prenom"} tirés des pseudos existants de la créatrice."""
    prenoms = variantes_prenom(creatrice)
    avec_prenom = sum(1 for h in handles if any(p in _ascii(h) for p in prenoms))
    part = avec_prenom / len(handles) if handles else 1.0
    # une créatrice « à prénom » (Chloé, Sarah…) : les mots d'ambiance ne découpent pas ses mots de marque (un nom de scène qui contient « nova » ne doit pas être coupé en deux)
    connus = sorted(set(prenoms) | set(STYLE) | (set(AMBIANCE) if part < 0.6 else set()), key=len, reverse=True)
    marques, style, ambiance = {}, set(), set()
    for h in handles:
        h = _ascii(h).lstrip("@")
        for morceau in re.split(r"[._\d]+", h):
            if not morceau:
                continue
            for mot in decouper(morceau, connus):
                if mot in prenoms:
                    continue
                if mot in JOLIS:
                    style.add(mot)
                elif mot in STYLE or mot in OUTILS:
                    continue
                elif mot in AMBIANCE:
                    ambiance.add(mot)
                elif len(mot) >= 3 and mot not in STYLE:
                    marques[mot] = marques.get(mot, 0) + 1
    # un mot de marque = vu dans au moins deux pseudos, ou long et distinctif (5 lettres ou plus)
    marques_ok = [m for m, n in sorted(marques.items(), key=lambda kv: -kv[1]) if (n >= 2 or len(m) >= 5) and len(m) <= 10]
    return {"prenoms": prenoms, "marques": marques_ok[:6], "style": sorted(style), "ambiance": sorted(ambiance), "part_prenom": part}


def candidats(vocab: dict, n: int, interdits: set, rng: random.Random) -> list:
    """n pseudos neufs à la marque de la créatrice, valides pour Instagram, jamais dans `interdits` (comparés sans . ni _)."""
    p = vocab["prenoms"][0] if vocab["prenoms"] else ""
    marques = [m for m in vocab["marques"] if m != p]
    longues = [m for m in marques if len(m) >= 4]                       # « van » seul ne dit rien : il reste collé au prénom
    style = sorted(set(vocab["style"]) | {"club", "diary", "secret", "daily", "mood", "vibes", "room"})
    ambiance = vocab["ambiance"]
    fabriques = []
    for _ in range(n * 40):
        liaison, fin = rng.choice(LIAISONS), rng.choice(FINS + (str(rng.randint(10, 98)),) * 3)
        style_ambiance = len(ambiance) >= 2 and vocab["part_prenom"] < 0.6   # Maddie : des pseudos d'ambiance, sans prénom
        forme = 6 if style_ambiance and rng.random() < 0.5 else rng.randrange(6)
        if forme == 0 and p and marques:
            base = f"{p}{liaison}{rng.choice(marques)}"
        elif forme == 1 and p:
            base = f"{rng.choice(PREFIXES)}{p}"
        elif forme == 2 and p:
            base = f"{p}{liaison}{rng.choice(style)}"
        elif forme == 3 and longues:
            base = f"{rng.choice(longues)}{liaison}{rng.choice(style)}"
        elif forme == 4 and p:
            base = f"{rng.choice(style)}{liaison}{p}"
        elif forme == 5 and longues:
            base = f"{rng.choice(PREFIXES)}{rng.choice(longues)}"
        elif forme == 6 and style_ambiance:                             # un mot à elle + un mot d'ambiance (le sien ou neuf)
            a = rng.choice(ambiance)
            b = rng.choice([x for x in AMBIANCE if x != a and len(x) >= 4])
            base = f"{a}{liaison}{b}" if rng.random() < 0.5 else f"{b}{liaison}{a}"
        else:
            continue
        h = f"{base}{fin}".lower()
        if p and h.count(p) > 1:
            continue
        if not (6 <= len(h) <= 24) or not RE_VALIDE.match(h) or ".." in h or h.isdigit() or "69" in h:
            continue
        cle = _squash(h)
        if cle in interdits or any(_squash(x) == cle for x in fabriques):
            continue
        fabriques.append(h)
        if len(fabriques) >= n:
            break
    return fabriques


def mot_de_passe(interdits: set = frozenset()) -> str:
    """Comme ceux du classeur (« Velvet8!Jade#47 ») : Mot + chiffre + symbole + Mot + symbole + 2 chiffres, tiré au hasard sûr."""
    while True:
        m1, m2 = secrets.choice(MOTS_MDP), secrets.choice(MOTS_MDP)
        if m1 == m2:
            continue
        mdp = f"{m1}{secrets.randbelow(10)}{secrets.choice(SYMBOLES)}{m2}{secrets.choice(SYMBOLES)}{10 + secrets.randbelow(90)}"
        if mdp not in interdits:
            return mdp


async def reserve(comptes: list, creatrices: list) -> dict:
    """{créatrice: [{"handle", "mdp", "verifie"}]} : la réserve complétée à CIBLE par créatrice, sans ceux déjà passés dans le
    classeur. Les nouveaux candidats sont vérifiés sur Instagram en un seul scan pour toutes les créatrices."""
    etat = _deps["lire_json"](_deps["FICHIER"], {}) if _deps.get("lire_json") else {}
    existants = {_squash(str(c.get("handle") or "").lstrip("@")) for c in comptes if c.get("handle")}
    mdps = {str(c.get("mdp") or "").strip() for c in comptes if c.get("mdp")}
    rng = random.Random(secrets.randbits(64))
    besoins, gardes = {}, {}
    for cr in creatrices:
        cle = _cle_creatrice(cr)
        garde = [x for x in etat.get(cle, []) if _squash(x["handle"]) not in existants]
        gardes[cle] = garde
        if len(garde) < CIBLE:
            handles = [str(c.get("handle") or "") for c in comptes if _cle_creatrice(c.get("creatrice") or c.get("onglet") or "") == cle and c.get("handle")]
            interdits = existants | {_squash(x["handle"]) for v in gardes.values() for x in v} | {_squash(x) for v in besoins.values() for x in v}
            besoins[cle] = candidats(vocabulaire(handles, cr), (CIBLE - len(garde)) * 2, interdits, rng)
    a_verifier = [h for v in besoins.values() for h in v]
    mesures = None
    if a_verifier and _deps.get("scanner"):
        try:
            mesures = await _deps["scanner"](a_verifier)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Identifiants : scan Instagram impossible (%s)", erreur)
    for cr in creatrices:
        cle = _cle_creatrice(cr)
        for h in besoins.get(cle, []):
            if len(gardes[cle]) >= CIBLE:
                break
            pris = mesures is not None and (mesures.get(h) or {}).get("existe")
            if pris:
                continue
            mdp = mot_de_passe(mdps)
            mdps.add(mdp)
            gardes[cle].append({"handle": h, "mdp": mdp, "verifie": mesures is not None,
                                "depuis": datetime.now(timezone.utc).strftime("%d/%m")})
    etat.update(gardes)
    if _deps.get("ecrire_json"):
        _deps["ecrire_json"](_deps["FICHIER"], etat)
    return {cr: gardes[_cle_creatrice(cr)] for cr in creatrices}


def lignes(reserve_: dict) -> list:
    """Le bloc de l'onglet : deux colonnes par créatrice (identifiant, mot de passe), CIBLE lignes."""
    noms = list(reserve_)
    tete = []
    for cr in noms:
        tete += [f"{cr} · identifiant", "mot de passe"]
    out = [tete]
    for i in range(max((len(v) for v in reserve_.values()), default=0)):
        ligne = []
        for cr in noms:
            x = reserve_[cr][i] if i < len(reserve_[cr]) else None
            ligne += ([x["handle"] + ("" if x.get("verifie") else " (?)"), x["mdp"]] if x else ["", ""])
        out.append(ligne)
    return out
