"""Onglet « Build capacity » du classeur des logins (30/09, Gaëtan : « une feuille avec mes coefficients d'attribution des
clippeurs et les clippeurs que je peux onboarder avec, pour savoir précisément combien de mails je dois créer pour quelles
créatrices »).

Réécrit à chaque `!dashboard`, après chaque scan, à chaque `!attribution` et sur `!capacite`. Par créatrice :
  coefficient d'attribution · part des nouveaux · comptes prêts (ceux que le bot livrerait vraiment : `onboarding.disponibles`,
  jamais une ligne qui partage une info d'un compte BAN) · clippers onboardables maintenant (prêts ÷ 3) · lignes « à créer »
  sans e-mail · lignes bloquées (infos d'un BAN) · puis, pour l'OBJECTIF tapé en B2 (gardé d'une réécriture à l'autre) :
  les nouveaux clippers qui iront chez elle en suivant la séquence d'attribution à partir de sa position actuelle, les comptes
  qu'il faut, ce qui manque, dont les e-mails à ajouter sur des lignes existantes et les comptes entiers à créer.
En tête : combien de clippers passent avant la première créatrice à sec, en suivant les coefficients."""
import logging
import os
from datetime import datetime, timezone

import attribution
import google_api
import onboarding

journal = logging.getLogger("bot.capacite")
ONGLET = os.environ.get("ONGLET_CAPACITE", "Build capacity").strip() or "Build capacity"
OBJECTIF_DEFAUT = int(os.environ.get("CAPACITE_OBJECTIF", "20") or 20)
ENTETE = ["Créatrice", "Coefficient", "Part des nouveaux", "Comptes prêts", "Clippers onboardables", "À créer sans e-mail",
          "Bloquées (infos d'un BAN)", "Nouveaux clippers de l'objectif", "Comptes nécessaires", "Comptes qui manquent",
          "dont e-mails à ajouter", "dont comptes entiers à créer"]
LIGNE_ENTETE = 4                                                        # index 0-based de la ligne d'en-tête du tableau
LARGEURS = (120, 92, 104, 104, 118, 118, 132, 150, 128, 128, 128, 160)


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
    return out


def lignes(chiffres: list, objectif: int, index: int = 0, jour: str = "") -> list:
    panne, qui = avant_panne({c["creatrice"]: c["onboardables"] for c in chiffres if c["poids"]}, index)
    total = lambda k: sum(c[k] for c in chiffres)                       # noqa: E731
    out = [[f"Build capacity — mis à jour le {jour or datetime.now(timezone.utc).strftime('%d/%m %H:%M')} UTC · coefficients : "
            + (attribution.ordre_texte() or "aucun")],
           ["Objectif : nouveaux clippers à onboarder ✏️", objectif, "← tape ton chiffre, le bot le garde et recalcule"],
           [f"En suivant tes coefficients, tu peux onboarder {panne} clipper(s) avant la première panne"
            + (f" (chez {qui} : plus de comptes prêts)" if qui else "") + f" · pour ton objectif, il manque {total('manque')} compte(s) : "
            f"{total('mails')} e-mail(s) à ajouter sur des lignes existantes, {total('entiers')} compte(s) entier(s) à créer"],
           [], list(ENTETE)]
    for c in chiffres:
        out.append([c["creatrice"], c["poids"], round(c["part"], 4), c["prets"], c["onboardables"], c["sans_mail"], c["bloquees"],
                    c["nouveaux"], c["necessaires"], c["manque"], c["mails"], c["entiers"]])
    out.append(["TOTAL", sum(c["poids"] for c in chiffres), 1 if any(c["poids"] for c in chiffres) else 0, total("prets"),
                total("onboardables"), total("sans_mail"), total("bloquees"), total("nouveaux"), total("necessaires"),
                total("manque"), total("mails"), total("entiers")])
    out += [[], ["Comment lire"],
            [f"· Un clipper reçoit {onboarding.COMPTES_PAR_CLIPPER} comptes. Compte prêt = Utilisation Clipper, sans Gérant, déjà créé ou « à créer » AVEC e-mail, "
             "et qui ne partage ni identifiant, ni mot de passe, ni e-mail, ni téléphone avec un compte BAN."],
            ["· « E-mails à ajouter » : des lignes « à créer » existent déjà sans e-mail, il suffit d'y mettre un e-mail neuf (iCloud « Masquer mon adresse »)."],
            ["· « Comptes entiers à créer » : de nouvelles lignes, avec identifiant, mot de passe et e-mail neufs."],
            ["· « Bloquées » : lignes libres qui portent une info d'un compte BAN. Jamais livrées : change leurs infos pour les récupérer."],
            ["· Les nouveaux de l'objectif suivent la séquence d'attribution à partir de sa position actuelle. Changer les coefficients : "
             "`!attribution Chloé:3,Sarah:3,Sophie:3,Jade:1` dans bot-gaetan (0 = exclue)."]]
    return out


def requetes(sid: int, n_createurs: int) -> list:
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
           E._cellules(sid, LIGNE_ENTETE + 1, fin + 1, 2, 3, format_nombre="0%"),
           E._cellules(sid, LIGNE_ENTETE + 1, fin, 9, nb, fond="#FFF3E0", gras=True),          # ce qui manque : à créer
           E._cellules(sid, fin, fin + 1, 0, nb, fond=E.SOMBRE, texte=E.BLANC, gras=True),
           E._cellules(sid, fin + 2, fin + 3, 0, 1, gras=True),
           E._cellules(sid, fin + 3, fin + 8, 0, nb, texte=E.GRIS_TEXTE, coupe="OVERFLOW_CELL"),
           {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": LIGNE_ENTETE, "endIndex": LIGNE_ENTETE + 1},
                                          "properties": {"pixelSize": 44}, "fields": "pixelSize"}}]
    for i, largeur in enumerate(LARGEURS):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                  "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    return req


def _objectif(valeur) -> int:
    try:
        return max(0, min(500, int(float(str(valeur).replace(",", ".").replace(" ", "").replace(" ", "")))))
    except (TypeError, ValueError):
        return OBJECTIF_DEFAUT


async def ecrire(comptes: list | None = None) -> dict:
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
    await google_api.sheets_effacer(cid, f"{onboarding.onglet_a1(ONGLET)}!A1:L80")
    await google_api.sheets_ecrire(cid, f"{onboarding.onglet_a1(ONGLET)}!A1", contenu)
    try:
        sid = (await google_api.sheets_proprietes(cid)).get(ONGLET, {}).get("id")
        if sid is not None:
            await google_api.sheets_batch_update(cid, requetes(sid, len(chiffres)))
    except Exception as erreur:                                         # noqa: BLE001 — la mise en forme ne bloque rien
        journal.warning("Build capacity : mise en forme impossible (%s)", erreur)
    panne, qui = avant_panne({c["creatrice"]: c["onboardables"] for c in chiffres if c["poids"]}, index)
    return {"objectif": objectif, "panne": panne, "qui": qui, "chiffres": chiffres,
            "manque": sum(c["manque"] for c in chiffres), "mails": sum(c["mails"] for c in chiffres), "entiers": sum(c["entiers"] for c in chiffres)}


def texte_resume(r: dict) -> str:
    if not r:
        return "Classeur inactif."
    detail = " · ".join(f"{c['creatrice']} {c['mails']}+{c['entiers']}" for c in r["chiffres"] if c["manque"])
    return (f"📦 Onglet « {ONGLET} » réécrit · objectif {r['objectif']} nouveaux clippers · {r['panne']} onboardables avant la première panne"
            + (f" ({r['qui']})" if r["qui"] else "")
            + (f"\nÀ créer pour l'objectif : {r['mails']} e-mail(s) sur lignes existantes + {r['entiers']} compte(s) entier(s)"
               + (f" → {detail} (e-mails + comptes entiers)" if detail else "") if r["manque"] else "\nObjectif couvert : rien à créer."))
