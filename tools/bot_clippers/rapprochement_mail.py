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
  - autre @ sur une ligne « à créer » : le clipper a reçu un @, le classeur en montre un autre ; personne ne sait lequel il a créé.
    Rien n'est réécrit : la ligne part au salon admin avec la commande qui tranche (`!pseudo @clipper n <le vrai @>`).
Le salon admin ne reçoit la liste que quand elle change. RAPPROCHEMENT_MAIL=0 coupe tout."""
import hashlib
import json
import logging
import os
import unicodedata

journal = logging.getLogger("bot.rapprochement_mail")
ACTIF = os.environ.get("RAPPROCHEMENT_MAIL", "1").strip() != "0"


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _mail(x) -> str:
    return str(x or "").strip().lower()


def _cle(h) -> str:
    return str(h or "").strip().lstrip("@").lower()


def ecarts(fiches: dict, comptes: list, cle=_cle) -> list:
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
        prenom = str(f.get("gerant") or "").strip()
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
            base = {"uid": str(uid), "prenom": prenom, "n": ordre.index(hf) + 1, "fiche": hf}
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


def texte_admin(suivis: list, a_trancher: list, refus: list) -> str:
    """Le bilan pour le salon admin, court, une ligne par compte."""
    lignes = ["🔗 **Rapprochement fiche ↔ classeur par l'e-mail du compte**"]
    if suivis:
        lignes.append("\n**La fiche suit le classeur** (le compte existe sous le @ du classeur) :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : `{e['fiche']}` → `{e['classeur']}` ({e['etat']})" for e in suivis]
    if a_trancher:
        lignes.append("\n**À trancher** (le clipper a reçu un @, le classeur en montre un autre, encore « à créer ») :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : reçu `{e['fiche']}`, classeur `{e['classeur']}` ({e['onglet']} l. "
                   f"{e['ligne']}) → demande-lui son @ exact, puis `!pseudo @{e['prenom']} {e['n']} <son @>`" for e in a_trancher]
    if refus:
        lignes.append("\n**Pas aligné** :")
        lignes += [f"• {e['prenom']} · compte {e['n']} : `{e['fiche']}` / `{e['classeur']}` : {e['raison']}" for e in refus]
    return "\n".join(lignes)[:1900]


def _signature(liste: list) -> str:
    return hashlib.sha1(json.dumps(liste, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def passer(onboarding, admin=None, lire_json=None, ecrire_json=None, fichier=None) -> dict:
    """Un passage : écarts calculés, fiches alignées quand le classeur a raison, bilan au salon admin s'il a changé. Jamais une
    écriture dans le classeur. Renvoie le bilan {ecarts, suivis, a_trancher, refus}."""
    bilan = {"ecarts": 0, "suivis": 0, "a_trancher": 0, "refus": 0, "absentes": 0}
    if not ACTIF or not onboarding.actif():
        return bilan
    comptes = await onboarding.lire_comptes()
    fiches = (onboarding._lire_etat().get("clippers") or {})
    liste = ecarts(fiches, comptes, cle=onboarding._cle_handle)
    bilan["ecarts"] = len(liste)
    bilan["absentes"] = sum(1 for e in liste if e["type"] in ("absente", "ambigue"))
    suivis, refus = [], []
    for e in [x for x in liste if a_suivre(x)]:
        raison = await onboarding.suivre_classeur(e["uid"], e["fiche"], e["classeur"])
        if raison:
            refus.append({**e, "raison": raison})
        else:
            suivis.append(e)
    a_trancher = [e for e in liste if e["type"] == "a_creer"]
    refus += [{**e, "raison": f"ligne au Gérant « {e['gerant'] or 'vide'} »"} for e in liste
              if e["type"] == "existe" and not a_suivre(e)]
    bilan.update(suivis=len(suivis), a_trancher=len(a_trancher), refus=len(refus))
    journal.info("Rapprochement par e-mail : %s écart(s), %s fiche(s) alignée(s), %s à trancher, %s pas aligné(s), %s sans ligne%s",
                 bilan["ecarts"], bilan["suivis"], bilan["a_trancher"], bilan["refus"], bilan["absentes"],
                 (" : " + " · ".join(f"{e['prenom'] or e['uid']} c{e['n']} {e['fiche']}→{e['classeur'] or '?'} ({e['type']})"
                                     for e in liste)) if liste else "")
    if admin and (suivis or a_trancher or refus):
        # les fiches alignées sont des changements faits : toujours dites ; la liste à trancher seulement quand elle change
        sig = _signature([[e["uid"], e["n"], e["fiche"], e["classeur"], e["type"]] for e in a_trancher + refus])
        memo = (lire_json(fichier, {}) if (lire_json and fichier) else {}) or {}
        if suivis or memo.get("signature") != sig:
            try:
                await admin(texte_admin(suivis, a_trancher, refus))
                if ecrire_json and fichier:
                    ecrire_json(fichier, {"signature": sig})
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Rapprochement par e-mail : bilan non posté (%s)", erreur)
    return bilan
