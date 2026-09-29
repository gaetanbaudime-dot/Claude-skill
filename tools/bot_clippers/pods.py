"""Ajout de POD au classeur des logins (30/09, Gaëtan : « rajoute des lignes pour préparer mon ajout de mails iCloud ;
duplique la ligne du dessus et rajoute POD après POD ; garde ETAT, @ (3 uniques par POD), MDP aléatoire, Utilisation,
Numéro Mail, Créatrice, POD »).

`!pods` (staff) : par onglet, le dernier POD, le dernier numéro de mail, les lignes « à créer » sans e-mail.
`!pods Chloé 5 voir` : aperçu des 15 lignes (sans les mots de passe), rien d'écrit.
`!pods Chloé 5` : écrit 5 POD de 3 lignes sous la dernière ligne de l'onglet, avec la mise en forme de la ligne du dessus.

Chaque ligne : ETAT « à créer », @ neuf, MDP de 18 caractères (minuscules, majuscules, chiffres, symboles, jamais un signe en
tête : le classeur lirait une formule), Utilisation et Créatrice recopiées de la dernière ligne à POD, Numéro Mail qui suit le
plus grand de l'onglet, POD qui suit le plus grand. Mail, Gérant, Phone et liens restent vides : Gaëtan pose l'e-mail iCloud,
et une ligne sans e-mail n'est jamais livrée à un clipper (onboarding.disponibles).

Les @ suivent la forme du classeur (relevé du 30/09) : les deux premiers d'un POD = alias de la créatrice + expression, en
minuscules collées ; le troisième = alias + mot court + « . » + vip / prive / club / clic / secret. Les alias sont ceux déjà
vus dans l'onglet (partie avant le point des troisièmes comptes) ; chez Maddie, des expressions anglaises sans son nom, comme
ses derniers comptes. Unicité vérifiée contre tous les @ du classeur, tous onglets ; la disponibilité sur Instagram n'est
PAS vérifiée (un @ pris se voit à la création : le clipper ajoute une lettre et le scan suit le handle du classeur)."""

import logging
import random
import re
import secrets
import string
import unicodedata

journal = logging.getLogger("pods")
_deps = {}
MAX_PODS = 30
SUFFIXES = ("vip", "prive", "club", "clic", "secret", "privee")
MOTS_COURTS = ("ici", "off", "bis", "mood", "vibe", "daily", "now", "zen", "doux", "soir", "live", "top")
EXPRESSIONS_FR = ("enpause", "auquotidien", "lesoir", "entrenous", "coulisses", "dimanche", "apresminuit", "envrai", "sansfiltre",
                  "toutdoux", "aucalme", "pourtoi", "envacances", "lematin", "enroute", "douceur", "cafeetmoi", "danslavie",
                  "parici", "envoyage", "aftershift", "enmode", "petitbonheur", "sesmoments", "sonmonde", "aujourdhui",
                  "tranquille", "enbalade", "lajournee", "sesreels", "enfamille", "auparc", "alamaison", "enliberte")
PREFIXES_FR = ("journalde", "toutsur", "lemondede", "levraide", "lesvideosde", "lecoinde", "lesreelsde", "unjouravec")
EXPRESSIONS_EN = ("offthemaptoday", "latenightloop", "softchaosdaily", "quietafterdark", "slowmotionlife", "midnightnotes",
                  "lowkeymoments", "goldenhourclub", "daydreamfiles", "nightshiftvibes", "cozychaosdaily", "afterhoursdiary",
                  "behindthelens", "rawmomentsonly", "velvetmornings", "sundayresetclub", "citylightsdiary", "nofilterdays",
                  "offdutymood", "secretgardenlog", "moonlitroutine", "softlaunchlife", "slowsundaysonly", "pastelhours")
ONGLETS_SANS_NOM = {"maddie"}                                         # 30/09 : ses derniers @ n'ont pas son nom


def configurer(deps: dict):
    """deps : google_api, onboarding (lire_comptes, onglets_logins, colonnes, onglet_a1, CLASSEUR_LOGINS_ID), est_staff."""
    _deps.update(deps)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def _alias_texte(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(t))


def mot_de_passe(n: int = 18) -> str:
    """18 caractères, au moins une minuscule, une majuscule, un chiffre, un symbole ; commence par une lettre."""
    symboles = "!#$%&*?"
    tous = string.ascii_letters + string.digits + symboles
    while True:
        mdp = secrets.choice(string.ascii_letters) + "".join(secrets.choice(tous) for _ in range(n - 1))
        if (any(c.islower() for c in mdp) and any(c.isupper() for c in mdp) and any(c.isdigit() for c in mdp)
                and any(c in symboles for c in mdp)):
            return mdp


def alias_de(lignes_onglet: list, handle_i: int, creatrice: str) -> list:
    """Les alias de la créatrice : partie avant le point des @ à point de l'onglet, plus son prénom."""
    vus = []
    for l in lignes_onglet:
        h = str(l[handle_i] if handle_i < len(l) else "").strip().lstrip("@").lower()
        if "." in h:
            a = _alias_texte(h.split(".")[0])
            if 2 <= len(a) <= 14 and a not in vus:
                vus.append(a)
    base = _alias_texte(creatrice)
    if base and base not in vus:
        vus.insert(0, base)
    return vus or ["clip"]


def generer_handles(n_pods: int, alias: list, existants: set, sans_nom: bool = False, rng=None) -> list:
    """[[h1, h2, h3], …] pour n_pods POD, uniques entre eux et contre `existants` (minuscules)."""
    rng = rng or random.SystemRandom()
    pris = set(existants)
    out = []

    def libre(h):
        return h and h not in pris and 5 <= len(h) <= 30

    for _ in range(n_pods):
        trio = []
        for k in range(2):
            h = ""
            for _essai in range(200):
                if sans_nom:
                    h = rng.choice(EXPRESSIONS_EN)
                    if not libre(h):
                        h = rng.choice(EXPRESSIONS_EN) + rng.choice(("club", "diary", "daily", "files", "notes"))
                else:
                    a = rng.choice(alias)
                    h = (a + rng.choice(EXPRESSIONS_FR)) if (k == 0 or rng.random() < 0.5) else (rng.choice(PREFIXES_FR) + a)
                if libre(h):
                    break
            else:
                h = h + secrets.token_hex(2)
            pris.add(h); trio.append(h)
        h = ""
        for _essai in range(200):
            h = f"{rng.choice(alias)}{rng.choice(MOTS_COURTS)}.{rng.choice(SUFFIXES)}"
            if libre(h):
                break
        else:
            h = h + secrets.token_hex(1)
        pris.add(h); trio.append(h)
        out.append(trio)
    return out


def _nombre(v) -> float | None:
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def preparer(lignes: list, cols: dict, n_pods: int, creatrice_onglet: str, tous_handles: set, rng=None) -> tuple:
    """(nouvelles lignes [liste de valeurs de A à la dernière colonne utile], infos) pour n_pods POD sous la dernière ligne."""
    corps = [(l + [""] * 30)[:30] for l in lignes[1:]]
    ip, inum, ih = cols["pod"], cols["numero"], cols["handle"]
    avec_pod = [l for l in corps if _nombre(l[ip]) is not None]
    modele = avec_pod[-1] if avec_pod else (corps[-1] if corps else [""] * 30)
    dernier_pod = int(max((_nombre(l[ip]) for l in avec_pod), default=0))
    dernier_num = int(max((_nombre(l[inum]) or 0 for l in corps), default=0))
    utilisation = modele[cols["utilisation"]].strip() or "Clipper"
    creatrice = modele[cols["creatrice"]].strip() or creatrice_onglet
    sans_nom = _norm(creatrice_onglet) in ONGLETS_SANS_NOM
    alias = alias_de(corps, ih, creatrice)
    if sans_nom:                                                        # ni dans les deux premiers, ni dans le troisième
        alias = [a for a in alias if a != _alias_texte(creatrice)] or ["soft"]
    trios = generer_handles(n_pods, alias, tous_handles, sans_nom=sans_nom, rng=rng)
    derniere_col = max(cols[c] for c in ("etat", "handle", "mdp", "utilisation", "numero", "creatrice", "pod"))
    nouvelles, num = [], dernier_num
    for k, trio in enumerate(trios, 1):
        for h in trio:
            num += 1
            l = [""] * (derniere_col + 1)
            l[cols["etat"]], l[ih], l[cols["mdp"]] = "à créer", h, mot_de_passe()
            l[cols["utilisation"]], l[inum], l[cols["creatrice"]], l[ip] = utilisation, num, creatrice, dernier_pod + k
            nouvelles.append(l)
    return nouvelles, {"dernier_pod": dernier_pod, "dernier_num": dernier_num, "alias": alias, "utilisation": utilisation,
                       "creatrice": creatrice, "premiere_ligne": len(lignes) + 1}


async def _onglet(nom: str) -> str:
    titres = await _deps["onboarding"].onglets_logins(forcer=True)
    return next((t for t in titres if _norm(t) == _norm(nom)), "")


async def ajouter(nom: str, n_pods: int, ecrire: bool = True) -> str:
    onb, g = _deps["onboarding"], _deps["google_api"]
    titre = await _onglet(nom)
    if not titre:
        return f"❌ Pas d'onglet « {nom} » dans le classeur des logins."
    lignes = await g.sheets_lire(onb.CLASSEUR_LOGINS_ID, f"{onb.onglet_a1(titre)}!A1:Z")
    if not lignes:
        return f"❌ Onglet « {titre} » vide."
    cols = onb.colonnes(lignes[0])
    manque = [c for c in ("etat", "handle", "mdp", "utilisation", "numero", "creatrice", "pod") if c not in onb._colonnes_trouvees(lignes[0])]
    if manque:
        return f"❌ Colonnes introuvables dans « {titre} » : {', '.join(manque)}. Rien écrit."
    tous = {str(c.get("handle") or "").lower() for c in await onb.lire_comptes() if c.get("handle")}
    nouvelles, info = preparer(lignes, cols, n_pods, titre, tous)
    debut, fin = info["premiere_ligne"], info["premiere_ligne"] + len(nouvelles) - 1
    apercu = [f"POD {info['dernier_pod'] + 1 + i // 3} · ligne {debut + i} · n° {l[cols['numero']]} · @{l[cols['handle']]}"
              for i, l in enumerate(nouvelles)]
    entete = (f"**{titre}** : {n_pods} POD ({len(nouvelles)} lignes), POD {info['dernier_pod'] + 1} à {info['dernier_pod'] + n_pods}, "
              f"n° de mail {info['dernier_num'] + 1} à {info['dernier_num'] + len(nouvelles)}, lignes {debut} à {fin}. "
              f"ETAT « à créer », Utilisation « {info['utilisation']} », Créatrice « {info['creatrice']} », MDP de 18 caractères. "
              "Mail, Gérant, Phone vides.")
    if not ecrire:
        return "👀 Aperçu, rien d'écrit — " + entete + "\n" + "\n".join(apercu[:45]) + f"\n-# Pour écrire : `!pods {titre} {n_pods}`"
    plage = f"{onb.onglet_a1(titre)}!A{debut}:{g.colonne_lettre(len(nouvelles[0]) - 1)}{fin}"
    await g.sheets_ecrire(onb.CLASSEUR_LOGINS_ID, plage, nouvelles)
    try:                                                                # « duplique la ligne du dessus » : sa mise en forme
        sid = (await g.sheets_proprietes(onb.CLASSEUR_LOGINS_ID)).get(titre, {}).get("id")
        if sid is not None:
            await g.sheets_batch_update(onb.CLASSEUR_LOGINS_ID, [{"copyPaste": {
                "source": {"sheetId": sid, "startRowIndex": debut - 2, "endRowIndex": debut - 1},
                "destination": {"sheetId": sid, "startRowIndex": debut - 1, "endRowIndex": fin},
                "pasteType": "PASTE_FORMAT"}}])
    except Exception as erreur:                                         # noqa: BLE001 — les valeurs sont écrites, c'est l'essentiel
        journal.warning("POD : mise en forme non recopiée sur %s : %s", titre, erreur)
    journal.info("POD ajoutés : %s, %s POD, lignes %s-%s", titre, n_pods, debut, fin)
    return "✅ " + entete + "\n" + "\n".join(apercu[:45]) + "\n-# Il reste à poser l'e-mail iCloud de chaque ligne (colonne Mail)."


async def etat() -> str:
    onb, g = _deps["onboarding"], _deps["google_api"]
    out = ["🗂️ **POD par onglet**"]
    for titre in await onb.onglets_logins(forcer=True):
        lignes = await g.sheets_lire(onb.CLASSEUR_LOGINS_ID, f"{onb.onglet_a1(titre)}!A1:Z")
        if not lignes:
            continue
        cols = onb.colonnes(lignes[0])
        if "pod" not in onb._colonnes_trouvees(lignes[0]):
            continue
        corps = [(l + [""] * 30)[:30] for l in lignes[1:]]
        pods = [_nombre(l[cols["pod"]]) for l in corps if _nombre(l[cols["pod"]]) is not None]
        sans_mail = sum(1 for l in corps if _norm(l[cols["etat"]]) in ("a creer", "à créer") and not l[cols["mail"]].strip())
        out.append(f"· {titre} : dernier POD {int(max(pods)) if pods else '—'} · {sans_mail} ligne(s) « à créer » sans e-mail")
    out.append("-# `!pods Chloé 5 voir` pour un aperçu, `!pods Chloé 5` pour écrire.")
    return "\n".join(out)


async def commande(message, texte: str) -> bool:
    mots = texte.split()
    if not mots or mots[0].lower() != "!pods":
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    try:
        if len(mots) == 1:
            await message.reply((await etat())[:1990])
            return True
        voir = mots[-1].lower() in ("voir", "apercu", "aperçu")
        args = mots[1:-1] if voir else mots[1:]
        if len(args) < 2 or not args[-1].isdigit():
            await message.reply("Usage : `!pods Chloé 5` (5 POD = 15 lignes) · `!pods Chloé 5 voir` pour un aperçu · `!pods` pour l'état.")
            return True
        n = int(args[-1])
        if not 1 <= n <= MAX_PODS:
            await message.reply(f"Entre 1 et {MAX_PODS} POD à la fois.")
            return True
        rep = await ajouter(" ".join(args[:-1]), n, ecrire=not voir)
    except RuntimeError as erreur:
        rep = f"❌ {erreur}"
    for i in range(0, len(rep), 1900):
        await message.reply(rep[i:i + 1900])
    return True
