# -*- coding: utf-8 -*-
"""Lecture du classeur « Data G&M Créatrices » (publié sur le web au format XLSX) :
valeur d'un abonné OnlyFans contre MYM, par créatrice, sur 30 jours — pour le rapport du
lundi et la commande `!ltv` (demande du 14/09 : « la différence de LTV OF/MYM dans le
reporting Telegram »).

Structure attendue de chaque onglet créatrice (celle du classeur du 14/09) : une ligne
d'en-tête qui commence par « Date », puis colonnes B = nouveaux abonnés OF, C = CA OF en $,
E = nouveaux abonnés MYM, F = CA MYM en €. Les onglets « Synthèse » et « Notice » sont ignorés.
Le taux $→€ vient de TAUX_USD_EUR (défaut 0,92) ; la Notice du classeur a le taux du jour,
mais on ne dépend pas de sa position.

Réglage Railway : SHEET_CREATRICES_XLSX_URL = le lien « Publier sur le web » du document
entier au format XLSX (Fichier → Partager → Publier sur le web → Document entier → Microsoft
Excel). Sans lui, le module est inerte. Aucune donnée n'est écrite nulle part."""
import asyncio
import io
import logging
import os
import re
from datetime import date, datetime, timedelta

import aiohttp

journal = logging.getLogger("creatrices")

SHEET_CREATRICES_XLSX_URL = os.environ.get("SHEET_CREATRICES_XLSX_URL", "").strip()
TAUX_USD_EUR = float(os.environ.get("TAUX_USD_EUR", "0.92").replace(",", "."))
ONGLETS_IGNORES = ("synth", "notice", "param", "config")

MOIS_FR = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
           "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
           "decembre": 12, "décembre": 12}


def _date(cellule, annee_defaut: int):
    """Une cellule de date : datetime Excel, ou texte « 1 juillet » / « 01/07/2026 » / « 2026-07-01 »."""
    if isinstance(cellule, datetime):
        return cellule.date()
    if isinstance(cellule, date):
        return cellule
    if not isinstance(cellule, str):
        return None
    t = cellule.strip().lower()
    m = re.fullmatch(r"(\d{1,2})\s+([a-zéû]+)(?:\s+(\d{4}))?", t)
    if m and m.group(2) in MOIS_FR:
        try:
            return date(int(m.group(3) or annee_defaut), MOIS_FR[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    for motif in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(t, motif).date()
        except ValueError:
            continue
    return None


def _nombre(cellule) -> float:
    if cellule is None or cellule == "":
        return 0.0
    if isinstance(cellule, (int, float)):
        return float(cellule)
    t = re.sub(r"[^\d,.\-]", "", str(cellule)).replace(",", ".")
    try:
        return float(t) if t not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


def lire_classeur(contenu: bytes, aujourdhui: date = None) -> dict:
    """{créatrice: [{date, of_subs, of_usd, mym_subs, mym_eur}, …]} depuis les octets du XLSX."""
    import openpyxl
    aujourdhui = aujourdhui or date.today()
    wb = openpyxl.load_workbook(io.BytesIO(contenu), data_only=True, read_only=True)
    donnees = {}
    for ws in wb.worksheets:
        nom = ws.title.strip()
        if any(nom.lower().startswith(p) for p in ONGLETS_IGNORES):
            continue
        lignes, en_tete_vu = [], False
        for ligne in ws.iter_rows(values_only=True):
            if not ligne:
                continue
            premier = str(ligne[0]).strip().lower() if ligne[0] is not None else ""
            if not en_tete_vu:
                if premier == "date":
                    en_tete_vu = True
                continue
            d = _date(ligne[0], aujourdhui.year)
            if d is None:
                continue
            if d > aujourdhui + timedelta(days=1):        # « 1 janvier » lu avec la mauvaise année
                d = d.replace(year=d.year - 1)
            def col(i):
                return _nombre(ligne[i]) if len(ligne) > i else 0.0
            lignes.append({"date": d, "of_subs": col(1), "of_usd": col(2), "mym_subs": col(4), "mym_eur": col(5)})
        if lignes:
            donnees[nom] = lignes
    return donnees


def calculer(donnees: dict, jours: int = 30, aujourdhui: date = None, taux: float = None) -> dict:
    """Par créatrice, sur la fenêtre glissante : abonnés et CA (€) OF et MYM, €/abonné de chaque
    plateforme, écart. Les jours sans saisie (case vide) comptent pour zéro, comme la Notice l'exige."""
    aujourdhui = aujourdhui or date.today()
    taux = taux or TAUX_USD_EUR
    debut = aujourdhui - timedelta(days=jours)
    resultat = {}
    for crea, lignes in donnees.items():
        sel = [l for l in lignes if debut < l["date"] <= aujourdhui]
        of_s = sum(l["of_subs"] for l in sel)
        of_e = sum(l["of_usd"] for l in sel) * taux
        my_s = sum(l["mym_subs"] for l in sel)
        my_e = sum(l["mym_eur"] for l in sel)
        if not (of_s or of_e or my_s or my_e):
            continue
        resultat[crea] = {
            "of_subs": int(of_s), "of_eur": of_e, "of_par_sub": (of_e / of_s) if of_s else None,
            "mym_subs": int(my_s), "mym_eur": my_e, "mym_par_sub": (my_e / my_s) if my_s else None,
            "total_eur": of_e + my_e, "total_subs": int(of_s + my_s), "jours_saisis": len(sel),
        }
    return resultat


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def _dec(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


def message_ltv(resultat: dict, jours: int = 30, aujourdhui: date = None) -> str:
    """Le bloc « valeur d'un abonné » : une ligne par créatrice, OF contre MYM, l'écart, puis le total.
    Écrit pour Telegram (astérisques simples) ; Discord remplace * par **."""
    if not resultat:
        return "💶 *Valeur d'un abonné* — classeur créatrices illisible ou vide (SHEET_CREATRICES_XLSX_URL)."
    aujourdhui = aujourdhui or date.today()
    lignes = [f"💶 *VALEUR D'UN ABONNÉ — {jours} jours au {aujourdhui.strftime('%d/%m')}* (OF converti en €)"]
    for crea, r in sorted(resultat.items(), key=lambda x: -x[1]["total_eur"]):
        morceaux = []
        if r["of_subs"] or r["of_eur"]:
            morceaux.append(f"OF {_n(r['of_subs'])} ab. → " + (f"*{_dec(r['of_par_sub'])} €/ab.*" if r["of_par_sub"] is not None else "—"))
        if r["mym_subs"] or r["mym_eur"]:
            morceaux.append(f"MYM {_n(r['mym_subs'])} ab. → " + (f"*{_dec(r['mym_par_sub'])} €/ab.*" if r["mym_par_sub"] is not None else "—"))
        if r["of_par_sub"] is not None and r["mym_par_sub"] is not None:
            ecart = r["mym_par_sub"] - r["of_par_sub"]
            morceaux.append(f"écart MYM {'+' if ecart >= 0 else '−'}{_dec(abs(ecart))} €")
        lignes.append(f"• {crea} ({_eur(r['total_eur'])}) : " + " · ".join(morceaux))
    of_s = sum(r["of_subs"] for r in resultat.values()); of_e = sum(r["of_eur"] for r in resultat.values())
    my_s = sum(r["mym_subs"] for r in resultat.values()); my_e = sum(r["mym_eur"] for r in resultat.values())
    tot = [f"TOTAL {_eur(of_e + my_e)}"]
    if of_s:
        tot.append(f"OF {_n(of_s)} ab. → {_dec(of_e / of_s)} €/ab.")
    if my_s:
        tot.append(f"MYM {_n(my_s)} ab. → {_dec(my_e / my_s)} €/ab.")
    lignes.append("_" + " · ".join(tot) + "_")
    return "\n".join(lignes)


async def telecharger_classeur(url: str = None) -> bytes:
    url = url or SHEET_CREATRICES_XLSX_URL
    if not url:
        return b""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(url) as reponse:
                if reponse.status >= 400:
                    journal.warning("Classeur créatrices HTTP %s", reponse.status)
                    return b""
                return await reponse.read()
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Classeur créatrices injoignable : %s", erreur)
        return b""


async def bloc_ltv(jours: int = 30) -> str:
    """Le bloc prêt à coller dans un rapport ; chaîne vide si le module n'est pas configuré."""
    if not SHEET_CREATRICES_XLSX_URL:
        return ""
    contenu = await telecharger_classeur()
    if not contenu:
        return "💶 Valeur d'un abonné : classeur créatrices injoignable aujourd'hui."
    try:
        donnees = await asyncio.get_event_loop().run_in_executor(None, lire_classeur, contenu)
    except Exception as erreur:                                   # noqa: BLE001
        journal.warning("Classeur créatrices illisible : %s", erreur)
        return "💶 Valeur d'un abonné : classeur créatrices illisible (format XLSX attendu)."
    return message_ltv(calculer(donnees, jours), jours)
