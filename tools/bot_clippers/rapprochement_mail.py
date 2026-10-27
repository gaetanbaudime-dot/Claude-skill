"""Un compte = une adresse e-mail : la fiche du bot et le classeur rapprochés par l'e-mail (27/10/2026).

Gaëtan (27/10) : « on lui donne un compte et c'est un compte différent de celui du tableau de bord ; quand j'analyse ses comptes, ça
m'envoie sur un compte qui n'existe pas ». Le bot retrouvait la ligne d'un compte par son @ seulement. Quand le @ change d'un côté
(cellule corrigée à la main, identifiant pris remplacé, compte renommé sur Instagram), la fiche du clipper (ce que Discord lui a
donné) et le classeur (ce que voient le Cockpit et le suivi) divergent sans que personne ne le voie : accès « non remis », Reels
comptés sur un compte qui n'existe pas, compte affiché « à créer » alors qu'il publie.

L'adresse e-mail de l'agence ne change jamais pour un compte : c'est la clé. À chaque passage, chaque compte de chaque fiche est
cherché dans le classeur par son e-mail (et, si l'adresse est en double, par son Gérant) :
  - même @ : rien ;
  - autre @ sur une ligne qui existe (GOOD, BAN, appel, privé…) : le classeur a raison, la fiche le suit (onboarding.suivre_classeur) ;
  - autre @ sur une ligne « à créer » : le clipper a reçu un @, le classeur en montre un autre. Le couple part dans l'onglet
    « IG · À trancher » ; le suivi Instagram regarde les deux @ (a_trancher_ig) et le passage suivant tranche (decision). Ce
    qu'Instagram ne tranche pas part au salon admin avec la commande (`!pseudo @clipper n <le vrai @>`).
Le salon admin ne reçoit la liste que quand elle change. RAPPROCHEMENT_MAIL=0 coupe tout."""
import hashlib
import json
import logging
import os
import unicodedata

journal = logging.getLogger("bot.rapprochement_mail")
ACTIF = os.environ.get("RAPPROCHEMENT_MAIL", "1").strip() != "0"
ONGLET = "IG · À trancher"                                               # même onglet que a_trancher_ig.ONGLET


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _mail(x) -> str:
    return str(x or "").strip().lower()


def _cle(h) -> str:
    return str(h or "").strip().lstrip("@").lower()


def ecarts(fiches: dict, comptes: list, cle=_cle, prenoms=None) -> list:
    """Pur : [{uid, prenom, n, fiche, classeur, etat, gerant, onglet, ligne, type}] — les comptes dont la ligne du classeur (même
    e-mail) porte un autre @ que la fiche. type : « existe » (la fiche suivra le classeur), « a_creer » (à trancher), « absente »
    (aucune ligne pour cet e-mail) ou « ambigue » (plusieurs lignes, Gérant compris). `comptes` : onboarding.lire_comptes()."""
    par_mail = {}
    for c in comptes or []:
        m = _mail(c.get("mail"))
        if "@" in m:
            par_mail.setdefault(m, []).append(c)
    out = []
    for uid, f in sorted((fiches or {}).items()):
        if not isinstance(f, dict) or f.get("sorti"):
            continue
        # 27/10 : les fiches des Team Leaders n'ont pas de « gerant » : le prénom du parcours
        prenom = str(f.get("gerant") or (prenoms or {}).get(str(uid)) or "").strip()
        ordre = [cle(h) for h in f.get("comptes") or [] if cle(h)]
        for a in f.get("acces") or []:
            if not isinstance(a, dict):
                continue
            hf, m = cle(a.get("handle")), _mail(a.get("mail"))
            if not hf or "@" not in m or hf not in ordre:
                continue
            lignes = par_mail.get(m) or []
            if len(lignes) > 1 and prenom:
                lignes = [c for c in lignes if _n(c.get("gerant")) == _n(prenom)] or lignes
            base = {"uid": str(uid), "prenom": prenom, "n": ordre.index(hf) + 1, "fiche": hf, "mail": m}
            if not lignes:
                out.append({**base, "classeur": "", "etat": "", "gerant": "", "onglet": "", "ligne": "", "type": "absente"})
                continue
            if len(lignes) > 1:
                out.append({**base, "classeur": "", "etat": "", "gerant": "", "onglet": "", "ligne": "", "type": "ambigue"})
                continue
            ligne = lignes[0]
            hs = cle(ligne.get("handle"))
            if not hs or hs == hf:
                continue
            a_creer = "creer" in _n(ligne.get("etat"))
            out.append({**base, "classeur": hs, "etat": str(ligne.get("etat") or ""), "gerant": str(ligne.get("gerant") or ""),
                        "onglet": str(ligne.get("onglet") or ""), "ligne": ligne.get("ligne") or "",
                        "type": "a_creer" if a_creer else "existe"})
    return out


def a_suivre(e: dict) -> bool:
    """Pur : la fiche peut suivre le classeur — ligne qui existe, Gérant de la ligne = le clipper (jamais une ligne réattribuée)."""
    return e.get("type") == "existe" and bool(e.get("prenom")) and _n(e.get("gerant")) == _n(e.get("prenom"))


NEUF_ABONNES = 300                                                       # un compte de clipper tout juste créé


def _txt(t) -> str:
    return "".join(ch for ch in _n(t) if ch.isalnum())


def bio_du_bot(bio: str, creatrice: str) -> bool:
    """Pur : la bio est l'une de celles que le bot donne avec chaque compte (profil.BIOS, prénom de la créatrice)."""
    try:
        import profil
        bios = profil.BIOS
    except Exception:                                                   # noqa: BLE001
        return False
    prenom = (str(creatrice or "").split() or [""])[0]
    cible = _txt(bio)
    return bool(cible) and any(_txt(b.format(prenom=prenom)) == cible for b in bios)


def _verif(l: list, debut: int) -> dict:
    v = (list(l) + [""] * 15)[debut:debut + 4]
    try:
        abonnes = int(float(str(v[1] or 0).replace(",", ".")))
    except ValueError:
        abonnes = 0
    return {"statut": str(v[0] or "").strip().lower(), "abonnes": abonnes, "bio": str(v[3] or "")}


def lire_verifs(lignes: list) -> dict:
    """Pur : onglet « IG · À trancher » relu → {(@ reçu, @ du classeur): {recu, classeur, le, ligne}} (seulement les lignes vérifiées)."""
    out = {}
    for l in (lignes or [])[1:]:
        if len(l) < 15 or not str(l[14] or "").strip():
            continue
        out[(str(l[0]).strip().lower(), str(l[1]).strip().lower())] = {
            "recu": _verif(l, 6), "classeur": _verif(l, 10), "le": str(l[14]).strip(), "ligne": list(l)}
    return out


def decision(e: dict, v: dict, maintenant) -> str:
    """Pur (27/10) : ce que la vérification Instagram permet de trancher pour un compte « à trancher ».
      - aucun des deux @ n'existe : rien n'est créé, le clipper a le @ de Discord en main → le classeur prend ce @ ;
      - seul le @ du classeur existe : le clipper l'a créé → la fiche suit le classeur ;
      - seul le @ reçu existe, avec la bio que le bot donne et peu d'abonnés : c'est son compte → le classeur prend ce @, GOOD ;
      - sinon (les deux existent, ou un compte d'inconnu sous le @ reçu) : '' (au salon admin)."""
    from datetime import datetime, timezone
    if not v:
        return ""
    try:
        le = datetime.fromisoformat(v["le"])
        le = le if le.tzinfo else le.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return ""
    if (maintenant - le).total_seconds() > 48 * 3600:
        return ""
    r, c = v["recu"]["statut"], v["classeur"]["statut"]
    if r == "introuvable" and c == "introuvable":
        return "classeur_suit_fiche"
    if c == "existe" and r == "introuvable":
        return "fiche_suit_classeur"
    if r == "existe" and c == "introuvable" and v["recu"]["abonnes"] <= NEUF_ABONNES \
            and bio_du_bot(v["recu"]["bio"], e.get("onglet")):
        return "classeur_suit_fiche_cree"
    return ""


ENTETE_ONGLET = ["@ reçu (Discord)", "@ du classeur", "Onglet", "Ligne", "Clipper", "Compte",
                 "Reçu : statut", "Reçu : abonnés", "Reçu : publications", "Reçu : bio",
                 "Classeur : statut", "Classeur : abonnés", "Classeur : publications", "Classeur : bio", "Vérifié le"]


def lignes_onglet(a_trancher: list, verifs: dict) -> list:
    """Pur : les lignes de « IG · À trancher » (sans l'en-tête) ; la vérification déjà faite d'un même couple de @ est gardée."""
    out = []
    for e in a_trancher:
        base = [e["fiche"], e["classeur"], e.get("onglet", ""), str(e.get("ligne", "")), e.get("prenom", ""), str(e.get("n", ""))]
        ancienne = (verifs.get((e["fiche"], e["classeur"])) or {}).get("ligne") or []
        out.append(base + [str(x) for x in (list(ancienne) + [""] * 15)[6:15]])
    return out


def texte_admin(suivis: list, a_trancher: list, refus: list, tranches: list = ()) -> str:
    """Le bilan pour le salon admin, court, une ligne par compte."""
    lignes = ["🔗 **Rapprochement fiche ↔ classeur par l'e-mail du compte**"]
    if suivis:
        lignes.append("\n**La fiche suit le classeur** (le compte existe sous le @ du classeur) :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : `{e['fiche']}` → `{e['classeur']}` ({e['etat']})" for e in suivis]
    if a_trancher:
        lignes.append("\n**À trancher** (le clipper a reçu un @, le classeur en montre un autre, encore « à créer ») :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : reçu `{e['fiche']}`, classeur `{e['classeur']}` ({e['onglet']} l. "
                   f"{e['ligne']}) → demande-lui son @ exact, puis `!pseudo @{e['prenom']} {e['n']} <son @>`" for e in a_trancher]
    if tranches:
        lignes.append("\n**Tranché par Instagram** (les deux @ regardés) :")
        quoi = {"classeur_suit_fiche": "rien de créé : le classeur prend le @ donné sur Discord",
                "classeur_suit_fiche_cree": "créé sous le @ donné sur Discord (bio du bot) : classeur à ce @, GOOD",
                "fiche_suit_classeur": "créé sous le @ du classeur : la fiche suit"}
        lignes += [f"• {e['prenom']} · compte {e['n']} : `{e['fiche']}` / `{e['classeur']}` → {quoi.get(e['decision'], e['decision'])}"
                   for e in tranches]
    if refus:
        lignes.append("\n**Pas aligné** :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : `{e['fiche']}` / `{e['classeur']}` : {e['raison']}" for e in refus]
    return "\n".join(lignes)[:1900]


def _signature(liste: list) -> str:
    return hashlib.sha1(json.dumps(liste, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def _trancher(onboarding, e: dict, quoi: str) -> str:
    """Applique une décision ; '' si c'est fait, sinon la raison."""
    if quoi == "fiche_suit_classeur":
        return await onboarding.suivre_classeur(e["uid"], e["fiche"], e["classeur"], e.get("mail", ""))
    raison = await onboarding.classeur_suit_fiche(e["uid"], e["classeur"], e["fiche"], e.get("mail", ""))
    if not raison and quoi == "classeur_suit_fiche_cree":
        try:
            await onboarding.marquer_etat(e["fiche"], "GOOD")
        except Exception as erreur:                                     # noqa: BLE001 — le @ est déjà juste
            journal.warning("À trancher : GOOD de %s non écrit (%s)", e["fiche"], erreur)
    return raison


async def passer(onboarding, admin=None, lire_json=None, ecrire_json=None, fichier=None, prenoms=None,
                 lire_onglet=None, ecrire_onglet=None, maintenant=None) -> dict:
    """Un passage : écarts calculés, fiches alignées quand le classeur a raison, bilan au salon admin s'il a changé. Jamais une
    écriture dans le classeur. Renvoie le bilan {ecarts, suivis, a_trancher, refus}."""
    bilan = {"ecarts": 0, "suivis": 0, "a_trancher": 0, "refus": 0, "absentes": 0}
    if not ACTIF or not onboarding.actif():
        return bilan
    comptes = await onboarding.lire_comptes()
    fiches = (onboarding._lire_etat().get("clippers") or {})
    liste = ecarts(fiches, comptes, cle=onboarding._cle_handle, prenoms=prenoms)
    bilan["ecarts"] = len(liste)
    bilan["absentes"] = sum(1 for e in liste if e["type"] in ("absente", "ambigue"))
    suivis, refus = [], []
    for e in [x for x in liste if a_suivre(x)]:
        raison = await onboarding.suivre_classeur(e["uid"], e["fiche"], e["classeur"], e.get("mail", ""))
        if raison:
            refus.append({**e, "raison": raison})
        else:
            suivis.append(e)
    a_trancher = [e for e in liste if e["type"] == "a_creer"]
    # 27/10 : les deux @ regardés sur Instagram par le suivi (a_trancher_ig) tranchent ce qui peut l'être sans personne
    from datetime import datetime, timezone
    maintenant = maintenant or datetime.now(timezone.utc)
    verifs, tranches = {}, []
    if lire_onglet:
        try:
            verifs = lire_verifs(await lire_onglet())
        except Exception as erreur:                                     # noqa: BLE001 — pas encore d'onglet : rien à trancher
            journal.info("Rapprochement par e-mail : onglet À trancher illisible (%s)", type(erreur).__name__)
    restent = []
    for e in a_trancher:
        quoi = decision(e, verifs.get((e["fiche"], e["classeur"])), maintenant)
        raison = await _trancher(onboarding, e, quoi) if quoi else "pas encore tranché"
        if quoi and not raison:
            tranches.append({**e, "decision": quoi})
            journal.info("Rapprochement par e-mail : %s compte %s %s / %s tranché : %s", e["prenom"] or e["uid"], e["n"], e["fiche"],
                         e["classeur"], quoi)
        else:
            if quoi:
                journal.info("Rapprochement par e-mail : %s compte %s %s / %s : %s refusé (%s)", e["prenom"] or e["uid"], e["n"],
                             e["fiche"], e["classeur"], quoi, raison)
            restent.append(e)
    a_trancher = restent
    if ecrire_onglet:
        try:
            await ecrire_onglet(lignes_onglet(a_trancher, verifs))
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Rapprochement par e-mail : onglet À trancher non écrit (%s)", erreur)
    bilan["tranches"] = len(tranches)
    refus += [{**e, "raison": f"ligne au Gérant « {e['gerant'] or 'vide'} »"} for e in liste
              if e["type"] == "existe" and not a_suivre(e)]
    bilan.update(suivis=len(suivis), a_trancher=len(a_trancher), refus=len(refus))
    for e in refus:
        journal.info("Rapprochement par e-mail : %s compte %s %s → %s pas aligné : %s", e["prenom"] or e["uid"], e["n"], e["fiche"],
                     e["classeur"], e["raison"])
    journal.info("Rapprochement par e-mail : %s écart(s), %s fiche(s) alignée(s), %s à trancher, %s pas aligné(s), %s sans ligne%s",
                 bilan["ecarts"], bilan["suivis"], bilan["a_trancher"], bilan["refus"], bilan["absentes"],
                 (" : " + " · ".join(f"{e['prenom'] or e['uid']} c{e['n']} {e['fiche']}→{e['classeur'] or '?'} ({e['type']})"
                                     for e in liste)) if liste else "")
    if admin and (suivis or a_trancher or refus or tranches):
        # les fiches alignées sont des changements faits : toujours dites ; la liste à trancher seulement quand elle change
        sig = _signature([[e["uid"], e["n"], e["fiche"], e["classeur"], e["type"]] for e in a_trancher + refus])
        memo = (lire_json(fichier, {}) if (lire_json and fichier) else {}) or {}
        if suivis or tranches or memo.get("signature") != sig:
            try:
                await admin(texte_admin(suivis, a_trancher, refus, tranches))
                if ecrire_json and fichier:
                    ecrire_json(fichier, {"signature": sig})
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Rapprochement par e-mail : bilan non posté (%s)", erreur)
    return bilan
