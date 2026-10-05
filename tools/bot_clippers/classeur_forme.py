"""Mise en forme des onglets créatrices du classeur des logins (29/09, Gaëtan : « les POD regroupés, les mêmes liens OnlyFans /
MYM / GAML de chaque clipper, par clipper et plus lisibles, uniquement ces colonnes, une belle mise en forme comme le Dashboard,
sans effacer aucune donnée »).

Un BLOC = les lignes consécutives d'un même Gérant (Utilisation Clipper ou vide) : ses comptes. Sur les colonnes du bloc (Gérant,
POD, Lien Infloww, Lien MYM, Lien GAML), le bloc reçoit la teinte de sa créatrice (deux teintes en alternance) et un cadre ; une
seule ligne du bloc montre le Gérant (en gras), le POD et les liens : **celle du milieu** (29/09, Gaëtan : « les liens OF / MYM /
GAML au milieu du pod du clippeur ») ; sur les autres lignes, les mêmes valeurs sont écrites dans la couleur du fond. Ça se lit
comme une cellule fusionnée, mais rien n'est fusionné ni effacé, le bot continue de lire chaque ligne. Une valeur différente sur une
ligne du bloc reste visible (un conflit se voit, il ne se cache pas). Les liens du bloc absents d'une ligne sont recopiés depuis la
première ligne du bloc qui les a (« ses 3 liens à mettre sur les 3 comptes »).

Regroupement (29/09, Gaëtan : « associer les clippeurs ensemble, si ça ne détruit pas toute la structure ») : un Gérant dont les
comptes sont éparpillés dans l'onglet (deux blocs ou plus) voit ses petits blocs déplacés juste après son plus grand (à taille égale
le premier reste en place) : le moins de lignes possible bougent, la ligne entière est déplacée (moveDimension), rien n'est effacé,
tout le reste de l'onglet garde son ordre. Rejoué après chaque scan, sur `!dashboard` et quand la structure change."""
import logging

journal = logging.getLogger("bot.classeur_forme")
# 30/09 (Gaëtan : « regroupe ces clics last 7d par clippeur, même mise en forme que les gérants avec leurs liens ») : Clics dans le bloc
# 05/10 : « Clics hier » suit la même règle que Clics (un chiffre par bloc, au milieu, les répétitions fondues)
COLONNES_BLOC = ("gerant", "clics", "clics_hier", "pod", "lien_infloww", "lien_mym", "lien_gaml")
COLONNES_CLICS = ("clics", "clics_hier")
COLONNES_RECOPIEES = ("pod", "lien_infloww", "lien_mym", "lien_gaml")
GERANTS_LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
PREMIERE_LIGNE = 2                                                          # la ligne 1 est l'en-tête
_deps: dict = {}


def configurer(deps: dict):
    """deps : google_api, classeur_id, colonnes_par_onglet (dict onglet → {champ: index}), palette (créatrice → (bande, teinte)),
    palette_defaut, melange(hexa, t), rgb(hexa), normaliser, onglet_a1, colonne_lettre, creatrices (05/10 : prénoms normalisés des
    créatrices — la ligne du compte principal d'une créatrice n'est jamais réécrite)."""
    _deps.update(deps)


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _est_creatrice(gerant: str) -> bool:
    """05/10 : le Gérant est une créatrice (Gérant = « Chloé » sur son compte principal) : mise en forme oui, écriture jamais."""
    return (_n(gerant or "").split() or [""])[0] in set(_deps.get("creatrices") or ())


def blocs(comptes_onglet: list) -> list:
    """[(gérant, [lignes du bloc triées par numéro de ligne])] — lignes consécutives d'un même Gérant. 30/09 (Gaëtan : « considère
    Rianah (Metricool) et Julien (Metricool) comme des clippeurs ; détecte automatiquement les gérants et mets-les en groupes ») : le
    Gérant compte en ENTIER (« Rianah (Metricool) » n'est pas « Rianah »), et toute Utilisation compte (Metricool, Geelark…)."""
    out, courant = [], None
    for c in sorted(comptes_onglet, key=lambda x: int(x.get("ligne") or 0)):
        g = _n(str(c.get("gerant") or "").strip())
        if not g or g in GERANTS_LIBRES:
            courant = None
            continue
        if courant and courant[0] == g and int(c["ligne"]) == int(courant[1][-1]["ligne"]) + 1:
            courant[1].append(c)
        else:
            courant = (g, [c])
            out.append(courant)
    return out


def requetes_regroupement(sid: int, comptes_onglet: list) -> tuple:
    """(requêtes moveDimension dans l'ordre d'application, {ancienne ligne: nouvelle ligne} pour toutes les lignes de l'onglet).
    Simulé sur la liste des lignes : chaque bloc déplacé est pris entier et posé juste après le plus grand bloc de son Gérant (puis
    à la suite des blocs déjà déplacés, dans leur ordre) ; un Gérant déjà réuni par un déplacement précédent n'est plus touché."""
    lignes = sorted(int(c["ligne"]) for c in comptes_onglet)
    if not lignes:
        return [], {}
    debut = min(PREMIERE_LIGNE, lignes[0])
    courant = list(range(debut, lignes[-1] + 1))
    par_gerant = {}
    for g, ls in blocs(comptes_onglet):
        par_gerant.setdefault(g, []).append([int(c["ligne"]) for c in ls])
    req = []
    for g, fragments in par_gerant.items():
        if len(fragments) < 2:
            continue
        ancre = max(fragments, key=lambda f: (len(f), -f[0]))
        queue = ancre[-1]
        for f in fragments:
            if f is ancre:
                continue
            positions = sorted(courant.index(l) for fr in fragments for l in fr)
            if positions[-1] - positions[0] + 1 == len(positions):           # déjà contigus (réunis par un déplacement précédent)
                break
            j0 = courant.index(f[0]); j1 = j0 + len(f)
            dest = courant.index(queue) + 1
            if dest != j0:
                req.append({"moveDimension": {"source": {"sheetId": sid, "dimension": "ROWS", "startIndex": debut - 1 + j0, "endIndex": debut - 1 + j1},
                                              "destinationIndex": debut - 1 + dest}})
                del courant[j0:j1]
                dest = courant.index(queue) + 1
                courant[dest:dest] = f
            queue = f[-1]
    return req, {l: debut + i for i, l in enumerate(courant)}


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


def ligne_visible(lignes: list) -> dict:
    """La ligne du bloc qui montre le Gérant, le POD et les liens : celle du milieu (la première pour un bloc de 1 ou 2 lignes)."""
    return lignes[(len(lignes) - 1) // 2]


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
        visible = ligne_visible(lignes)
        rv = int(visible["ligne"]) - 1
        for c0, c1 in _runs(list(idx.values())):
            req.append(_fmt(sid, r0, r1, c0, c1, fond=fond, gras=False))
            req.append(_bordure(sid, r0, r1, c0, c1, bande))
        req.append(_fmt(sid, rv, rv + 1, idx["gerant"], idx["gerant"] + 1, fond=fond, gras=True))
        if "pod" in idx:
            req.append(_fmt(sid, r0, r1, idx["pod"], idx["pod"] + 1, fond=fond, aligne="CENTER"))
        for ch in COLONNES_CLICS:                                           # le total du clipper, en gras, au milieu du bloc
            if ch in idx:
                req.append(_fmt(sid, r0, r1, idx[ch], idx[ch] + 1, fond=fond, aligne="CENTER"))
                req.append(_fmt(sid, rv, rv + 1, idx[ch], idx[ch] + 1, fond=fond, gras=True))
        creatrice = _est_creatrice(lignes[0].get("gerant"))                 # 05/10 : jamais d'écriture sur la ligne d'une créatrice
        for ch in COLONNES_RECOPIEES:                                       # 1) la valeur du bloc = la première non vide ; recopiée où elle manque
            if ch not in idx or creatrice:
                continue
            v_bloc = next((str(c.get(ch) or "").strip() for c in lignes if str(c.get(ch) or "").strip()), "")
            for c in lignes:
                if v_bloc and not str(c.get(ch) or "").strip():
                    ecritures.append((f"{a1(titre)}!{lettre(idx[ch])}{c['ligne']}", [[v_bloc]]))
                    c[ch] = v_bloc
        for c in lignes:                                                    # 2) hors de la ligne visible, les mêmes valeurs se fondent
            if c is visible:
                continue
            rr = int(c["ligne"]) - 1
            req.append(_fmt(sid, rr, rr + 1, idx["gerant"], idx["gerant"] + 1, fond=fond, texte=fond))     # Gérant répété : discret
            for ch in COLONNES_CLICS:                                       # une ancienne valeur répétée ne se voit plus
                if ch in idx:
                    req.append(_fmt(sid, rr, rr + 1, idx[ch], idx[ch] + 1, fond=fond, texte=fond))
            for ch in COLONNES_RECOPIEES:
                if ch not in idx:
                    continue
                v, v_visible = str(c.get(ch) or "").strip(), str(visible.get(ch) or "").strip()
                if v and v == v_visible:
                    req.append(_fmt(sid, rr, rr + 1, idx[ch], idx[ch] + 1, fond=fond, texte=fond))         # même valeur : cachée
    return req, ecritures


async def formater(comptes: list, regrouper: bool = True) -> dict:
    """Met en forme tous les onglets créatrices présents dans `comptes` (lus par onboarding.lire_comptes), après avoir regroupé les
    lignes des clippers éparpillés (les numéros de ligne de `comptes` sont mis à jour). Renvoie un bilan."""
    g = _deps["google_api"]
    cid = _deps["classeur_id"]
    props = await g.sheets_proprietes(cid)
    par_onglet = {}
    for c in comptes:
        par_onglet.setdefault(c.get("onglet") or "", []).append(c)
    bilan = {"onglets": 0, "blocs": 0, "recopies": 0, "deplacees": 0}
    for titre, lignes in par_onglet.items():
        sid = props.get(titre, {}).get("id")
        cols = (_deps.get("colonnes_par_onglet") or {}).get(titre) or {}
        if sid is None or not cols or "gerant" not in cols:
            continue
        if regrouper:
            req_dep, correspondance = requetes_regroupement(sid, lignes)
            if req_dep:
                await g.sheets_batch_update(cid, req_dep)
                for c in lignes:
                    c["ligne"] = correspondance.get(int(c["ligne"]), int(c["ligne"]))
                bilan["deplacees"] += len(req_dep)
                journal.info("Classeur %s : %d bloc(s) déplacé(s) pour réunir les comptes d'un même clipper", titre, len(req_dep))
        req, ecritures = requetes_onglet(sid, titre, cols, lignes)
        if not req:
            continue
        await g.sheets_batch_update(cid, req)
        if ecritures:
            bilan["recopies"] += await g.sheets_ecrire_plusieurs(cid, ecritures)
        bilan["onglets"] += 1
        bilan["blocs"] += len(blocs(lignes))
    journal.info("Classeur : %d onglet(s) mis en forme, %d bloc(s), %d lien(s) recopié(s), %d bloc(s) déplacé(s)",
                 bilan["onglets"], bilan["blocs"], bilan["recopies"], bilan["deplacees"])
    return bilan
