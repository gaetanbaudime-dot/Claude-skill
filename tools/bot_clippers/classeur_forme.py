"""Mise en forme des onglets créatrices du classeur des logins (29/09, Gaëtan : « les POD regroupés, les mêmes liens OnlyFans /
MYM / GAML de chaque clipper, par clipper et plus lisibles, uniquement ces colonnes, une belle mise en forme comme le Dashboard,
sans effacer aucune donnée »).

Un BLOC = les lignes consécutives d'un même Gérant (Utilisation Clipper ou vide) : ses comptes. Sur les colonnes du bloc (Gérant,
POD, Lien Infloww, Lien MYM, Lien GAML), le bloc reçoit la teinte de sa créatrice (deux teintes en alternance), un cadre, le
Gérant en gras sur la première ligne ; les valeurs répétées des lignes suivantes (même POD, même lien) sont écrites dans la couleur
du fond : ça se lit comme une cellule fusionnée, mais rien n'est fusionné ni effacé, le bot continue de lire chaque ligne. Les
liens du bloc absents des lignes 2 et 3 sont recopiés depuis la première ligne (« ses 3 liens à mettre sur les 3 comptes »).
Rejoué après chaque scan, sur `!dashboard` et quand la structure change : les lignes bougent, la mise en forme suit."""
import logging

journal = logging.getLogger("bot.classeur_forme")
COLONNES_BLOC = ("gerant", "pod", "lien_infloww", "lien_mym", "lien_gaml")
COLONNES_RECOPIEES = ("pod", "lien_infloww", "lien_mym", "lien_gaml")
GERANTS_LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
_deps: dict = {}


def configurer(deps: dict):
    """deps : google_api, classeur_id, colonnes_par_onglet (dict onglet → {champ: index}), palette (créatrice → (bande, teinte)),
    palette_defaut, melange(hexa, t), rgb(hexa), normaliser, onglet_a1, colonne_lettre."""
    _deps.update(deps)


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def blocs(comptes_onglet: list) -> list:
    """[(gérant, [lignes du bloc triées par numéro de ligne])] — lignes consécutives d'un même Gérant, Utilisation Clipper ou vide."""
    out, courant = [], None
    for c in sorted(comptes_onglet, key=lambda x: int(x.get("ligne") or 0)):
        g = _n(str(c.get("gerant") or "").split()[0] if str(c.get("gerant") or "").strip() else "")
        en_gestion = _n(c.get("utilisation") or "clipper") in ("clipper", "")
        if not g or g in GERANTS_LIBRES or not en_gestion:
            courant = None
            continue
        if courant and courant[0] == g and int(c["ligne"]) == courant[1][-1]["ligne"] + 1:
            courant[1].append(c)
        else:
            courant = (g, [c])
            out.append(courant)
    return out


def _plage(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _fmt(sid, r0, r1, c0, c1, fond=None, texte=None, gras=None, aligne=None, reset=False):
    fmt, champs = {}, []
    if reset:
        return {"repeatCell": {"range": _plage(sid, r0, r1, c0, c1), "cell": {"userEnteredFormat": {"backgroundColor": _deps["rgb"]("#FFFFFF")}},
                               "fields": "userEnteredFormat(backgroundColor,textFormat.bold,textFormat.foregroundColor)"}}
    if fond:
        fmt["backgroundColor"] = _deps["rgb"](fond); champs.append("backgroundColor")
    tf = {}
    if texte:
        tf["foregroundColor"] = _deps["rgb"](texte); champs.append("textFormat.foregroundColor")
    if gras is not None:
        tf["bold"] = gras; champs.append("textFormat.bold")
    if tf:
        fmt["textFormat"] = tf
    if aligne:
        fmt["horizontalAlignment"] = aligne; champs.append("horizontalAlignment")
    return {"repeatCell": {"range": _plage(sid, r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt},
                           "fields": "userEnteredFormat(" + ",".join(champs) + ")"}}


def _bordure(sid, r0, r1, c0, c1, couleur, interieur=False):
    trait = {"style": "SOLID_MEDIUM", "color": _deps["rgb"](couleur)}
    req = {"updateBorders": {"range": _plage(sid, r0, r1, c0, c1), "top": trait, "bottom": trait, "left": trait, "right": trait}}
    if interieur:
        req["updateBorders"]["innerHorizontal"] = {"style": "NONE"}
    return req


def _runs(indices: list) -> list:
    """[3, 11, 12, 13, 14] → [(3, 4), (11, 15)] : plages de colonnes contiguës."""
    out = []
    for i in sorted(set(indices)):
        if out and out[-1][1] == i:
            out[-1] = (out[-1][0], i + 1)
        else:
            out.append((i, i + 1))
    return out


def requetes_onglet(sid: int, titre: str, cols: dict, comptes_onglet: list) -> tuple:
    """(requêtes batchUpdate, écritures [(plage A1, [[valeur]])]) pour un onglet."""
    idx = {ch: cols[ch] for ch in COLONNES_BLOC if ch in cols}
    if "gerant" not in idx or not comptes_onglet:
        return [], []
    bande, teinte = (_deps.get("palette") or {}).get(_n(titre).split()[0] if _n(titre) else "", _deps.get("palette_defaut", ("#455A64", "#ECEFF1")))
    teinte2 = _deps["melange"](bande, 0.06)
    derniere = max(int(c.get("ligne") or 1) for c in comptes_onglet)
    req = []
    for c0, c1 in _runs(list(idx.values())):
        req.append(_fmt(sid, 1, derniere + 50, c0, c1, reset=True))
        req.append({"updateBorders": {"range": _plage(sid, 1, derniere + 50, c0, c1), "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
                                      "left": {"style": "NONE"}, "right": {"style": "NONE"}, "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}}})
    ecritures = []
    lettre, a1 = _deps["colonne_lettre"], _deps["onglet_a1"]
    for k, (g, lignes) in enumerate(blocs(comptes_onglet)):
        fond = teinte if k % 2 == 0 else teinte2
        r0, r1 = int(lignes[0]["ligne"]) - 1, int(lignes[-1]["ligne"])           # index 0-based, fin exclusive
        ancre = lignes[0]
        for c0, c1 in _runs(list(idx.values())):
            req.append(_fmt(sid, r0, r1, c0, c1, fond=fond, gras=False))
            req.append(_bordure(sid, r0, r1, c0, c1, bande))
        req.append(_fmt(sid, r0, r0 + 1, idx["gerant"], idx["gerant"] + 1, fond=fond, gras=True))
        if "pod" in idx:
            req.append(_fmt(sid, r0, r1, idx["pod"], idx["pod"] + 1, fond=fond, aligne="CENTER"))
        for c in lignes[1:]:
            rr = int(c["ligne"]) - 1
            req.append(_fmt(sid, rr, rr + 1, idx["gerant"], idx["gerant"] + 1, fond=fond, texte=fond))     # Gérant répété : discret
            for ch in COLONNES_RECOPIEES:
                if ch not in idx:
                    continue
                v_ancre, v = str(ancre.get(ch) or "").strip(), str(c.get(ch) or "").strip()
                if v_ancre and not v:                                          # le lien du bloc manque sur cette ligne : recopié
                    ecritures.append((f"{a1(titre)}!{lettre(idx[ch])}{c['ligne']}", [[v_ancre]]))
                    c[ch] = v_ancre; v = v_ancre
                if v and v == v_ancre:
                    req.append(_fmt(sid, rr, rr + 1, idx[ch], idx[ch] + 1, fond=fond, texte=fond))         # même valeur : cachée
    return req, ecritures


async def formater(comptes: list) -> dict:
    """Met en forme tous les onglets créatrices présents dans `comptes` (lus par onboarding.lire_comptes). Renvoie un bilan."""
    g = _deps["google_api"]
    cid = _deps["classeur_id"]
    props = await g.sheets_proprietes(cid)
    par_onglet = {}
    for c in comptes:
        par_onglet.setdefault(c.get("onglet") or "", []).append(c)
    bilan = {"onglets": 0, "blocs": 0, "recopies": 0}
    for titre, lignes in par_onglet.items():
        sid = props.get(titre, {}).get("id")
        cols = (_deps.get("colonnes_par_onglet") or {}).get(titre) or {}
        if sid is None or not cols:
            continue
        req, ecritures = requetes_onglet(sid, titre, cols, lignes)
        if not req:
            continue
        await g.sheets_batch_update(cid, req)
        if ecritures:
            bilan["recopies"] += await g.sheets_ecrire_plusieurs(cid, ecritures)
        bilan["onglets"] += 1
        bilan["blocs"] += len(blocs(lignes))
    journal.info("Classeur : %d onglet(s) mis en forme, %d bloc(s), %d lien(s) recopié(s)", bilan["onglets"], bilan["blocs"], bilan["recopies"])
    return bilan
