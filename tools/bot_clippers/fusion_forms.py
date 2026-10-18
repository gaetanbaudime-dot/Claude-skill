"""18/10 (Gaëtan : « les Forms sont fermés, leurs réponses transférées en haut du classeur où arrivent les nouvelles
candidatures, je veux garder la data ») : une seule fois, les réponses des anciens Google Forms remontent EN HAUT de l'onglet
« Candidatures bot », chaque réponse sous la colonne de la même question (libellé, sinon mot-clé du champ, sinon une colonne
ajoutée au bout : rien n'est perdu).

Sources : l'onglet « Réponses au formulaire 1 » du même classeur (Form principal) et, si le compte Google du bot y a accès, les
classeurs de réponses des Forms Malgaches et Français (FORMS_ARCHIVES, « source=id » séparés par des virgules).

Une ligne déjà importée (même horodatage, mêmes 8 derniers chiffres de téléphone, même prénom) ne l'est jamais deux fois : la
fusion peut tourner à chaque démarrage. Après la fusion du Form principal, le bot ne lit plus son onglet (sinon chaque réponse
compterait deux fois) : les lignes importées portent « form-… » en Source et sont lues comme « formulaire ».
"""
import json
import logging
import os
import re
from pathlib import Path

journal = logging.getLogger("fusion_forms")

# Les classeurs de réponses des deux autres Forms (ids Drive, pas de donnée personnelle). Vide = Form principal seul.
FORMS_ARCHIVES = os.environ.get(
    "FORMS_ARCHIVES",
    "form-malgaches=1M4EFF0KprSScbHUsC6ZiL2pImlnlsBSxmYyJlNRrsJ0,form-francais=1fN3ciesNxfuSj0ZlFk_wL6FUNqoTxeyreCVJrsi0njI").strip()
SOURCE_PRINCIPAL = "form-principal"
# Libellés qui disent la même chose sans partager de mot-clé du bot (normalisés, sous-chaîne)
ALIAS = (("reseau social as-tu vu", "vu annonce"), ("reseau social as tu vu", "vu annonce"))


def archives() -> list:
    """[(source, classeur_id)] depuis FORMS_ARCHIVES."""
    out = []
    for morceau in FORMS_ARCHIVES.split(","):
        if "=" in morceau:
            src, ident = (x.strip() for x in morceau.split("=", 1))
            if src and ident:
                out.append((src, ident))
    return out


def _chiffres(t) -> str:
    return re.sub(r"\D", "", str(t or ""))


def cle_ligne(date, tel, prenom, normaliser) -> tuple:
    return (str(date or "").strip()[:16], _chiffres(tel)[-8:], normaliser(prenom or "").strip())


def colonne_cible(libelle: str, en_tete: list, normaliser, colonnes_fn) -> int | None:
    """La colonne de l'onglet du bot pour une question d'un Form : même libellé, sinon même champ (mots-clés du bot), sinon alias."""
    ln = normaliser(libelle).strip()
    if not ln:
        return None
    for i, h in enumerate(en_tete):
        if normaliser(h).strip() == ln:
            return i
    champ = next(iter(colonnes_fn([libelle])), None)
    if champ is not None:
        cols = colonnes_fn(en_tete)
        if champ in cols:
            return cols[champ]
    for mot_form, mot_bot in ALIAS:
        if mot_form in ln:
            for i, h in enumerate(en_tete):
                if mot_bot in normaliser(h):
                    return i
    return None


def plan(en_tete: list, lignes_bot: list, sources: list, normaliser, colonnes_fn) -> tuple:
    """Fonction pure. `sources` : [(source, lignes brutes avec l'en-tête en premier)]. Renvoie (en_tete, lignes, importées par
    source) : l'en-tête éventuellement allongé, puis les lignes importées (par source, dans l'ordre du Form) AVANT les lignes
    déjà là, les déjà importées sautées."""
    en_tete = list(en_tete)
    cols = colonnes_fn(en_tete)
    i_src = next((i for i, h in enumerate(en_tete) if normaliser(h).strip() == "source"), 1)

    def cle_bot(r):
        g = lambda champ: r[cols[champ]] if champ in cols and cols[champ] < len(r) else ""
        return cle_ligne(g("date") or (r[0] if r else ""), g("tel"), g("prenom"), normaliser)

    vues = {cle_bot(r) for r in lignes_bot}
    nouvelles, compte = [], {}
    for source, brut in sources:
        if not brut:
            compte[source] = 0
            continue
        tete = [str(x) for x in brut[0]]
        cibles = []
        for libelle in tete:
            c = colonne_cible(libelle, en_tete, normaliser, colonnes_fn)
            if c is None and normaliser(libelle).strip():
                en_tete.append(libelle.strip())                         # question sans équivalent : colonne au bout, rien de perdu
                c = len(en_tete) - 1
            cibles.append(c)
        cols_src = colonnes_fn(tete)
        n = 0
        for r in brut[1:]:
            r = [str(x) for x in r]
            if not any(x.strip() for x in r):
                continue
            g = lambda champ: r[cols_src[champ]] if champ in cols_src and cols_src[champ] < len(r) else ""
            k = cle_ligne(g("date") or r[0], g("tel"), g("prenom"), normaliser)
            if k in vues:
                continue
            vues.add(k)
            ligne = [""] * len(en_tete)
            for j, v in enumerate(r):
                c = cibles[j] if j < len(cibles) else None
                if c is not None and v.strip():
                    while len(ligne) <= c:
                        ligne.append("")
                    ligne[c] = v if not ligne[c] else ligne[c] + " · " + v
            ligne[i_src] = source
            nouvelles.append(ligne)
            n += 1
        compte[source] = n
    largeur = len(en_tete)
    tout = [l + [""] * (largeur - len(l)) for l in nouvelles] + [list(r) + [""] * (largeur - len(r)) for r in lignes_bot]
    return en_tete, tout, compte


def _texte(x) -> str:
    """Relu brut, réécrit en USER_ENTERED : « +261… » ou « =… » en tête restent du texte (même règle que le compactage)."""
    x = str(x)
    return "'" + x if x[:1] in ("+", "=", "-", "@") else x


def _etat(fichier: Path) -> dict:
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def principal_fusionne(fichier: Path) -> bool:
    """Vrai quand l'onglet du Form principal est passé dans « Candidatures bot » : le bot ne doit plus le lire."""
    return SOURCE_PRINCIPAL in _etat(fichier)


async def executer(google_api, classeur: str, onglet_bot: str, onglet_form: str, fichier: Path, normaliser, colonnes_fn,
                   lire_onglet) -> str:
    """La fusion, une fois par source. Renvoie le bilan à dire au salon admin ('' si rien de neuf)."""
    etat = _etat(fichier)
    sources, refus = [], []
    if onglet_form and SOURCE_PRINCIPAL not in etat:
        try:
            sources.append((SOURCE_PRINCIPAL, await lire_onglet(onglet_form)))
        except Exception as erreur:                                     # noqa: BLE001
            refus.append(f"{onglet_form} illisible ({type(erreur).__name__})")
    for source, ident in archives():
        if source in etat:
            continue
        try:
            onglets = await google_api.sheets_onglets(ident)
            sources.append((source, await google_api.sheets_lire(ident, "'" + onglets[0].replace("'", "''") + "'")))
        except Exception as erreur:                                     # noqa: BLE001 — pas partagé avec le compte du bot
            refus.append(f"{source} : classeur non partagé avec {google_api.email_compte() or 'le compte Google du bot'}"
                         f" ({type(erreur).__name__})")
    if not sources:
        return ("📥 Fusion des Forms : " + " ; ".join(refus)) if refus else ""
    brut = await lire_onglet(onglet_bot)
    en_tete, lignes_bot = [str(x) for x in (brut[0] if brut else [])], [[str(x) for x in r] for r in brut[1:]
                                                                          if any(str(x).strip() for x in r[:6])]
    nouvel_en_tete, tout, compte = plan(en_tete, lignes_bot, sources, normaliser, colonnes_fn)
    if sum(compte.values()):
        await google_api.sheets_assurer_colonnes(classeur, onglet_bot, len(nouvel_en_tete))
        props = (await google_api.sheets_proprietes(classeur)).get(onglet_bot) or {}
        manque = len(tout) + 1 - int(props.get("lignes") or 0)
        if props and manque > 0:
            await google_api.sheets_batch_update(classeur, [{"appendDimension": {"sheetId": props["id"], "dimension": "ROWS",
                                                                                 "length": manque + 50}}])
        if nouvel_en_tete != en_tete:
            await google_api.sheets_ecrire(classeur, f"{onglet_bot}!A1", [nouvel_en_tete])
        await google_api.sheets_ecrire(classeur, f"{onglet_bot}!A2", [[_texte(x) for x in r] for r in tout])
    for source, _ in sources:
        etat[source] = compte.get(source, 0)
    try:
        fichier.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as erreur:
        journal.warning("Fusion des Forms : état non écrit (%s)", erreur)
    morceaux = [f"{s} : {n} réponse(s)" for s, n in compte.items()]
    return ("📥 Fusion des Forms dans « " + onglet_bot + " » (en haut) : " + " · ".join(morceaux)
            + (". ⚠️ " + " ; ".join(refus) if refus else "") + ".")
