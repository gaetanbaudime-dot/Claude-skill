"""Onglet « Build capacity » du classeur des logins (30/09, Gaëtan : « une feuille avec mes coefficients d'attribution des
clippeurs et les clippeurs que je peux onboarder avec, pour savoir précisément combien de mails je dois créer pour quelles
créatrices »).

Réécrit à chaque `!dashboard`, après chaque scan, à chaque `!attribution` et sur `!capacite`. Par créatrice :
  coefficient d'attribution · part des nouveaux · comptes prêts (ceux que le bot livrerait vraiment : `onboarding.disponibles`,
  jamais une ligne qui partage une info d'un compte BAN) · clippers onboardables maintenant (prêts ÷ 3) · lignes « à créer »
  sans e-mail · lignes bloquées (infos d'un BAN) · puis, pour l'OBJECTIF tapé en B2 (gardé d'une réécriture à l'autre) :
  les nouveaux clippers qui iront chez elle en suivant la séquence d'attribution à partir de sa position actuelle, les comptes
  qu'il faut, ce qui manque, dont les e-mails à ajouter sur des lignes existantes et les comptes entiers à créer.
En tête : combien de clippers passent avant la première créatrice à sec, en suivant les coefficients.
30/09 (Gaëtan : « ajoute-moi la créatrice en manque de mail iCloud en premier, avec ces coefficients ») : colonne « À sec
après » (combien de nouveaux clippers, toutes créatrices confondues, avant qu'ELLE n'ait plus de comptes prêts, en suivant la
séquence) ; le tableau est trié par là, la plus urgente en premier, et la ligne 3 donne l'ordre des e-mails à créer.
Sous le tableau : 20 identifiants neufs par créatrice avec leur mot de passe (`identifiants.py`, calculés dans le bot)."""
import logging
import os
from datetime import datetime, timezone

import attribution
import google_api
import onboarding

journal = logging.getLogger("bot.capacite")
ONGLET = os.environ.get("ONGLET_CAPACITE", "Build capacity").strip() or "Build capacity"
OBJECTIF_DEFAUT = int(os.environ.get("CAPACITE_OBJECTIF", "20") or 20)
ENTETE = ["Créatrice", "À sec après (nouveaux clippers)", "Coefficient", "Part des nouveaux", "Comptes prêts", "Clippers onboardables", "À créer sans e-mail",
          "Bloquées (infos d'un BAN)", "Nouveaux clippers de l'objectif", "Comptes nécessaires", "Comptes qui manquent",
          "dont e-mails à ajouter", "dont comptes entiers à créer"]
LIGNE_ENTETE = 4                                                        # index 0-based de la ligne d'en-tête du tableau
LARGEURS = (150, 150, 150, 104, 150, 118, 150, 132, 150, 128, 150, 128, 160)   # colonnes paires larges : identifiants dessous


def _n(t) -> str:
    return onboarding._norm(t or "")


def _cle(nom: str) -> str:
    return _n(nom).split()[0] if _n(nom).split() else ""


def creatrices(comptes: list) -> list:
    """L'ordre d'attribution d'abord, puis les autres créatrices du classeur (coefficient 0)."""
    vus, out = set(), []
    for nom in list(attribution.ORDRE) + sorted({str(c.get("creatrice") or "").strip() for c in comptes if str(c.get("creatrice") or "").strip()}):
        if _cle(nom) and _cle(nom) not in vus:
            vus.add(_cle(nom)); out.append(nom)
    return out


def _index_attribution() -> int:
    try:
        e = attribution._etat()
        return int(e.get("index", 0)) if e.get("ordre") == attribution.ORDRE_TEXTE else 0
    except Exception:                                                   # noqa: BLE001 — sans état (tests) : début de séquence
        return 0


def prochains(n: int, index: int = 0) -> list:
    """Les créatrices des n prochains clippers, dans la séquence pondérée, à partir de sa position actuelle."""
    seq = attribution.SEQUENCE
    return [seq[(index + k) % len(seq)] for k in range(n)] if seq else []


def avant_panne(onboardables: dict, index: int = 0) -> tuple:
    """(clippers onboardables en suivant la séquence avant qu'une créatrice n'ait plus de comptes, cette créatrice)."""
    seq = attribution.SEQUENCE
    if not seq:
        return 0, ""
    reste = {_cle(k): v for k, v in onboardables.items()}
    for k in range(10_000):
        cr = seq[(index + k) % len(seq)]
        if reste.get(_cle(cr), 0) <= 0:
            return k, cr
        reste[_cle(cr)] -= 1
    return 10_000, ""


def a_sec_apres(onboardables: dict, creatrice: str, index: int = 0):
    """Nouveaux clippers (toutes créatrices) avant que `creatrice` soit demandée sans compte prêt ; None si hors séquence."""
    seq = attribution.SEQUENCE
    cle = _cle(creatrice)
    if not seq or cle not in {_cle(x) for x in seq}:
        return None
    reste = onboardables.get(cle, 0)
    for k in range(100_000):
        if _cle(seq[(index + k) % len(seq)]) == cle:
            if reste <= 0:
                return k
            reste -= 1
    return None


def calcul(comptes: list, objectif: int, index: int = 0) -> list:
    """Une ligne de chiffres par créatrice (dict), dans l'ordre de `creatrices`."""
    brulees = onboarding.infos_brulees(comptes)
    n_par = onboarding.COMPTES_PAR_CLIPPER
    total_poids = sum(attribution.POIDS.values()) or 1
    objectif_par = {}
    for cr in prochains(objectif, index):
        objectif_par[_cle(cr)] = objectif_par.get(_cle(cr), 0) + 1
    out = []
    for cr in creatrices(comptes):
        libres = [c for c in comptes if _n(c.get("utilisation")) == "clipper" and _n(c.get("gerant")) in onboarding.GERANTS_LIBRES
                  and _n(c.get("etat")) in onboarding.ETATS_DISPONIBLES and c.get("handle") and onboarding._pour_creatrice(c, cr)]
        bloquees = [c for c in libres if onboarding.infos_d_un_ban(c, brulees)]
        sans_mail = [c for c in libres if c not in bloquees and _n(c.get("etat")) in onboarding.A_CREER and not c.get("mail")]
        prets = len(onboarding.disponibles(comptes, cr, 999))
        poids = next((p for k, p in attribution.POIDS.items() if _cle(k) == _cle(cr)), 0)
        nouveaux = objectif_par.get(_cle(cr), 0)
        manque = max(0, nouveaux * n_par - prets)
        mails = min(manque, len(sans_mail))
        out.append({"creatrice": cr, "poids": poids, "part": poids / total_poids if poids else 0, "prets": prets,
                    "onboardables": prets // n_par, "sans_mail": len(sans_mail), "bloquees": len(bloquees), "nouveaux": nouveaux,
                    "necessaires": nouveaux * n_par, "manque": manque, "mails": mails, "entiers": manque - mails})
    onb = {_cle(c["creatrice"]): c["onboardables"] for c in out}
    for c in out:
        c["a_sec"] = a_sec_apres(onb, c["creatrice"], index)
    # la plus urgente d'abord : dans la séquence, à sec le plus tôt ; hors séquence ensuite, les plus pauvres en comptes d'abord
    out.sort(key=lambda c: (c["a_sec"] is None, c["a_sec"] if c["a_sec"] is not None else c["prets"]))
    return out


def lignes(chiffres: list, objectif: int, index: int = 0, jour: str = "") -> list:
    panne, qui = avant_panne({c["creatrice"]: c["onboardables"] for c in chiffres if c["poids"]}, index)
    total = lambda k: sum(c[k] for c in chiffres)                       # noqa: E731
    out = [[f"Build capacity — mis à jour le {jour or datetime.now(timezone.utc).strftime('%d/%m %H:%M')} UTC · coefficients : "
            + (attribution.ordre_texte() or "aucun")],
           ["Objectif : nouveaux clippers à onboarder ✏️", objectif, "← tape ton chiffre, le bot le garde et recalcule"],
           ["👉 E-mails iCloud à créer d'abord pour : " + (" → ".join(f"{c['creatrice']} (à sec après {c['a_sec']})" for c in chiffres if c["a_sec"] is not None) or "—")
            + f" · en suivant tes coefficients, {panne} clipper(s) avant la première panne" + (f" (chez {qui})" if qui else "")
            + f" · pour ton objectif, il manque {total('manque')} compte(s) : {total('mails')} e-mail(s) à ajouter sur des lignes existantes, "
            f"{total('entiers')} compte(s) entier(s) à créer"],
           [], list(ENTETE)]
    for c in chiffres:
        out.append([c["creatrice"], c["a_sec"] if c["a_sec"] is not None else "—", c["poids"], round(c["part"], 4), c["prets"],
                    c["onboardables"], c["sans_mail"], c["bloquees"], c["nouveaux"], c["necessaires"], c["manque"], c["mails"], c["entiers"]])
    out.append(["TOTAL", panne, sum(c["poids"] for c in chiffres), 1 if any(c["poids"] for c in chiffres) else 0, total("prets"),
                total("onboardables"), total("sans_mail"), total("bloquees"), total("nouveaux"), total("necessaires"),
                total("manque"), total("mails"), total("entiers")])
    out += [[], ["Comment lire"],
            [f"· Un clipper reçoit {onboarding.COMPTES_PAR_CLIPPER} comptes. Compte prêt = Utilisation Clipper, sans Gérant, déjà créé ou « à créer » AVEC e-mail, "
             "et qui ne partage ni identifiant, ni mot de passe, ni e-mail, ni téléphone avec un compte BAN."],
            ["· « E-mails à ajouter » : des lignes « à créer » existent déjà sans e-mail, il suffit d'y mettre un e-mail neuf (iCloud « Masquer mon adresse »)."],
            ["· « Comptes entiers à créer » : de nouvelles lignes, avec identifiant, mot de passe et e-mail neufs."],
            ["· « Bloquées » : lignes libres qui portent une info d'un compte BAN. Jamais livrées : change leurs infos pour les récupérer."],
            ["· Les nouveaux de l'objectif suivent la séquence d'attribution à partir de sa position actuelle. Changer les coefficients : "
             "`!attribution Chloé:3,Sarah:3,Sophie:3,Jade:1` dans bot-gaetan (0 = exclue)."],
            ["· « À sec après » : combien de nouveaux clippers, toutes créatrices confondues, avant qu'elle n'ait plus de comptes prêts. "
             "La plus petite = la créatrice pour qui créer des e-mails en premier."]]
    return out


def lignes_identifiants(reserve_: dict) -> list:
    import identifiants
    return [[], [f"Identifiants neufs — {identifiants.CIBLE} par créatrice, dans l'ordre d'urgence · « libres » d'après le scan Instagram "
                 f"(probable, pas garanti) · (?) = pas encore vérifié · un identifiant copié dans un onglet est remplacé au passage suivant"]] \
        + identifiants.lignes(reserve_)


def requetes(sid: int, n_createurs: int, n_identifiants: int = 0, noms: tuple = ()) -> list:
    import etats_comptes as E                                           # palettes et cellules du Dashboard (import tardif)
    fin = LIGNE_ENTETE + 1 + n_createurs                                # ligne TOTAL (0-based)
    nb = len(ENTETE)
    req = [{"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": LIGNE_ENTETE + 1}},
                                      "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount"}},
           E._cellules(sid, 0, fin + 12, 0, nb, fond=E.BLANC, texte="#212121", gras=False, taille=10, aligne="LEFT", coupe="CLIP"),
           {"updateBorders": {"range": E._plage(sid, 0, fin + 12, 0, nb), "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
                              "left": {"style": "NONE"}, "right": {"style": "NONE"}, "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}}},
           E._cellules(sid, 0, 1, 0, nb, fond=E.SOMBRE, texte=E.BLANC, gras=True, taille=12, coupe="OVERFLOW_CELL"),
           E._cellules(sid, 1, 2, 0, 1, fond="#FFF8E1", gras=True, coupe="OVERFLOW_CELL"),
           E._cellules(sid, 1, 2, 1, 2, fond="#FFEB3B", gras=True, taille=12, aligne="CENTER"),
           E._cellules(sid, 1, 2, 2, 3, texte=E.GRIS_TEXTE, coupe="OVERFLOW_CELL"),
           {"updateBorders": {"range": E._plage(sid, 1, 2, 1, 2), **{k: {"style": "SOLID_MEDIUM", "color": E._rgb("#F57F17")} for k in ("top", "bottom", "left", "right")}}},
           E._cellules(sid, 2, 3, 0, nb, gras=True, taille=11, coupe="OVERFLOW_CELL"),
           E._cellules(sid, LIGNE_ENTETE, LIGNE_ENTETE + 1, 0, nb, fond=E.GRIS_CLAIR, texte=E.SOMBRE, gras=True, aligne="CENTER", coupe="WRAP"),
           E._cellules(sid, LIGNE_ENTETE + 1, fin + 1, 1, nb, aligne="CENTER", format_nombre="0"),
           E._cellules(sid, LIGNE_ENTETE + 1, fin + 1, 3, 4, format_nombre="0%"),
           E._cellules(sid, LIGNE_ENTETE + 1, fin, 1, 2, fond="#FFEBEE", gras=True),           # à sec après : l'urgence
           E._cellules(sid, LIGNE_ENTETE + 1, LIGNE_ENTETE + 2, 0, 2, fond="#FFCDD2", gras=True),   # la plus urgente
           E._cellules(sid, LIGNE_ENTETE + 1, fin, 10, nb, fond="#FFF3E0", gras=True),         # ce qui manque : à créer
           E._cellules(sid, fin, fin + 1, 0, nb, fond=E.SOMBRE, texte=E.BLANC, gras=True),
           E._cellules(sid, fin + 2, fin + 3, 0, 1, gras=True),
           E._cellules(sid, fin + 3, fin + 9, 0, nb, texte=E.GRIS_TEXTE, coupe="OVERFLOW_CELL"),
           {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": LIGNE_ENTETE, "endIndex": LIGNE_ENTETE + 1},
                                          "properties": {"pixelSize": 44}, "fields": "pixelSize"}}]
    for i, largeur in enumerate(LARGEURS):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                  "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    if n_identifiants:                                                  # bloc des identifiants : une couleur par créatrice
        r0 = fin + 10                                                   # TOTAL, vide, « Comment lire », 6 notes, vide, puis le titre
        req += [_titre_idents(E, sid, r0, nb)]
        for i, cr in enumerate(noms):
            bandeau, teinte = E.PALETTE_DASHBOARD.get(_cle(cr), E.PALETTE_DEFAUT)
            req += [E._cellules(sid, r0 + 1, r0 + 2, 2 * i, 2 * i + 2, fond=bandeau, texte=E.BLANC, gras=True, aligne="CENTER"),
                    E._cellules(sid, r0 + 2, r0 + 2 + n_identifiants, 2 * i, 2 * i + 2, fond=teinte, taille=10, aligne="LEFT")]
    return req


def _titre_idents(E, sid, r0, nb):
    return E._cellules(sid, r0, r0 + 1, 0, nb, fond=E.SOMBRE, texte=E.BLANC, gras=True, taille=11, coupe="OVERFLOW_CELL")


def _objectif(valeur) -> int:
    try:
        return max(0, min(500, int(float(str(valeur).replace(",", ".").replace(" ", "").replace(" ", "")))))
    except (TypeError, ValueError):
        return OBJECTIF_DEFAUT


async def ecrire(comptes: list | None = None, neufs: bool = False) -> dict:
    """Réécrit l'onglet ; renvoie le résumé {objectif, panne, qui, manque, mails, entiers, chiffres}."""
    if not onboarding.actif():
        return {}
    cid = onboarding.CLASSEUR_LOGINS_ID
    comptes = comptes if comptes is not None else await onboarding.lire_comptes()
    try:
        await google_api.sheets_creer_onglet(cid, ONGLET)
    except Exception as erreur:                                         # noqa: BLE001 — il existe déjà
        journal.info("Onglet %s : %s", ONGLET, erreur)
    try:
        b2 = await google_api.sheets_lire(cid, f"{onboarding.onglet_a1(ONGLET)}!B2")
        objectif = _objectif(b2[0][0]) if b2 and b2[0] else OBJECTIF_DEFAUT
    except Exception:                                                   # noqa: BLE001
        objectif = OBJECTIF_DEFAUT
    index = _index_attribution()
    chiffres = calcul(comptes, objectif, index)
    contenu = lignes(chiffres, objectif, index)
    noms, n_idents = (), 0
    try:                                                                # 30/09 : 20 identifiants neufs par créatrice, les plus urgentes à gauche
        import identifiants
        if neufs and identifiants._deps.get("ecrire_json"):
            identifiants._deps["ecrire_json"](identifiants._deps["FICHIER"], {})
        res = await identifiants.reserve(comptes, [c["creatrice"] for c in chiffres])
        noms, n_idents = tuple(res), max((len(v) for v in res.values()), default=0)
        contenu += lignes_identifiants(res)
    except Exception as erreur:                                         # noqa: BLE001 — l'onglet s'écrit quand même
        journal.warning("Build capacity, identifiants : %s", erreur)
    await google_api.sheets_effacer(cid, f"{onboarding.onglet_a1(ONGLET)}!A1:M200")
    await google_api.sheets_ecrire(cid, f"{onboarding.onglet_a1(ONGLET)}!A1", contenu)
    try:
        sid = (await google_api.sheets_proprietes(cid)).get(ONGLET, {}).get("id")
        if sid is not None:
            await google_api.sheets_batch_update(cid, requetes(sid, len(chiffres), n_idents, noms))
    except Exception as erreur:                                         # noqa: BLE001 — la mise en forme ne bloque rien
        journal.warning("Build capacity : mise en forme impossible (%s)", erreur)
    panne, qui = avant_panne({c["creatrice"]: c["onboardables"] for c in chiffres if c["poids"]}, index)
    return {"objectif": objectif, "panne": panne, "qui": qui, "chiffres": chiffres,
            "manque": sum(c["manque"] for c in chiffres), "mails": sum(c["mails"] for c in chiffres), "entiers": sum(c["entiers"] for c in chiffres)}


def texte_resume(r: dict) -> str:
    if not r:
        return "Classeur inactif."
    detail = " · ".join(f"{c['creatrice']} {c['mails']}+{c['entiers']}" for c in r["chiffres"] if c["manque"])
    urgence = " → ".join(f"{c['creatrice']} ({c['a_sec']})" for c in r["chiffres"] if c.get("a_sec") is not None)
    return (f"📦 Onglet « {ONGLET} » réécrit · e-mails iCloud d'abord pour : {urgence or '—'}"
            f"\nObjectif {r['objectif']} nouveaux clippers · {r['panne']} onboardables avant la première panne"
            + (f" ({r['qui']})" if r["qui"] else "")
            + (f"\nÀ créer pour l'objectif : {r['mails']} e-mail(s) sur lignes existantes + {r['entiers']} compte(s) entier(s)"
               + (f" → {detail} (e-mails + comptes entiers)" if detail else "") if r["manque"] else "\nObjectif couvert : rien à créer."))
