"""Pilotage (12/10/2026, Gaëtan : « développe une app Vercel pour que je puisse tracker au quotidien les clics de toute la team ; un
onglet vertical, un onglet horizontal, un onglet subs ; vertical avec les stats des créatrices et de leurs gros comptes »).

Le bot mesure déjà tout (clics GAML relevés toutes les 15 minutes, followers et Reels des comptes, subs saisis dans Data G&M) ;
l'app « pilotage » (tools/app_clippers, route /p/<jeton>) ne fait AUCUN appel GAML, Apify ni Metricool : elle lit quatre onglets que
ce module écrit dans le tableur « App clippers · usage » (Drive agence, privé : Gaëtan et le compte de service), comme l'onglet
« Équipes » :

  - « Pilotage comptes » : une ligne par compte Instagram montré au Dashboard (créatrice, axe Vertical / Horizontal, type, Gérant, @,
    ETAT, followers, écarts 24 h et 7 j, followers des 7 derniers jours, Reels, vues à 48 h, clics), l'état du moment ;
  - « Pilotage clics » : une ligne par jour × créatrice × axe × source × personne, visites payables (francophones, hors robots) et
    hors robots, sur PILOTAGE_JOURS jours dont aujourd'hui jusqu'au dernier relevé ; « Liens non relevés » > 0 = somme partielle ;
  - « Pilotage subs » : une ligne par jour × créatrice (subs et CA OnlyFans, subs et CA MYM, saisi ou non), lue dans Data G&M
    (rapport_quotidien.data_gm, au plus toutes les 30 minutes) ;
  - « Pilotage infos » : l'heure de publication, la fraîcheur des sources (celle du titre du Dashboard), le taux USD → EUR.

Les tables viennent de dashboard.construire (`r["pilotage"]`, mêmes chiffres que le Dashboard, jamais un faux 0) ; ce module ne fait
qu'écrire, chaque onglet seulement s'il a changé, valeurs brutes (RAW : la locale française du tableur ne réinterprète rien).
Jamais d'exception : une publication ratée est retentée au passage suivant du Dashboard (15 minutes).
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone

import google_api

journal = logging.getLogger("pilotage")

ONGLET_COMPTES = "Pilotage comptes"
ONGLET_CLICS = "Pilotage clics"
ONGLET_SUBS = "Pilotage subs"
ONGLET_INFOS = "Pilotage infos"
ENTETE_COMPTES = ["Créatrice", "Axe", "Type", "Gérant", "@", "ETAT", "Followers", "Δ 24 h", "Δ 7 j", "Followers 7 j",
                  "Reels auj.", "Reels hier", "Reels 7 j", "Vues 7 j (48 h)", "Vues 7 j d'avant", "Clics auj.", "Clics hier",
                  "Clics 7 j", "Clics 7 j d'avant", "Dernier Reel", "Mesure"]
ENTETE_CLICS = ["Jour", "Créatrice", "Axe", "Source", "Qui", "Visites payables", "Visites hors robots", "Liens", "Liens non relevés"]
ENTETE_SUBS = ["Jour", "Créatrice", "Subs OF", "CA OF ($)", "Subs MYM", "CA MYM (€)", "Saisi"]
SUBS_TTL_S = 30 * 60

_signatures: dict = {}                 # onglet → signature de la dernière version écrite (cette instance du bot)
_onglets_crees: set = set()            # (classeur, onglet) déjà créés ou vus
_subs_cache = {"t": 0.0, "jour": "", "lignes": None}
_verrou = None


def _nombre(x) -> str:
    """Un nombre de Data G&M en texte sans zéros inutiles (« 12 », « 45.5 »)."""
    try:
        v = float(x or 0)
    except (TypeError, ValueError):
        return ""
    return str(int(v)) if v == int(v) else f"{v:.2f}".rstrip("0").rstrip(".")


def lignes_subs(donnees: dict, aujourdhui: date, jours: int) -> list:
    """{onglet créatrice: [{date, of_subs, of_usd, mym_subs, mym_eur, saisi}]} → lignes de l'onglet « Pilotage subs », du plus
    ancien au plus récent, sur `jours` jours finissant aujourd'hui. Pur, testé."""
    debut = aujourdhui - timedelta(days=jours - 1)
    out = []
    for creatrice in sorted(donnees or {}):
        par_jour = {}
        for l in donnees[creatrice] or []:
            d = l.get("date") if isinstance(l, dict) else None
            if isinstance(d, date) and debut <= d <= aujourdhui:
                par_jour[d] = l                                          # une date en double : la dernière ligne de l'onglet gagne
        for d in sorted(par_jour):
            l = par_jour[d]
            out.append([d.isoformat(), str(creatrice).strip(), _nombre(l.get("of_subs")), _nombre(l.get("of_usd")),
                        _nombre(l.get("mym_subs")), _nombre(l.get("mym_eur")), "oui" if l.get("saisi") else "non"])
    return out


async def _subs(aujourdhui: date, jours: int):
    """Les lignes subs (cache 30 minutes), None si Data G&M n'est pas lisible (l'onglet garde alors sa dernière version)."""
    if _subs_cache["lignes"] is not None and _subs_cache["jour"] == aujourdhui.isoformat() \
            and time.monotonic() - _subs_cache["t"] < SUBS_TTL_S:
        return _subs_cache["lignes"]
    try:
        import rapport_quotidien
        donnees = await rapport_quotidien.data_gm(aujourdhui)
    except Exception as erreur:                                          # noqa: BLE001
        journal.warning("Pilotage : Data G&M illisible (%s)", str(erreur)[:160])
        return None
    if not donnees:
        return None
    lignes = lignes_subs(donnees, aujourdhui, jours)
    _subs_cache.update(t=time.monotonic(), jour=aujourdhui.isoformat(), lignes=lignes)
    return lignes


async def _classeur() -> str:
    import paie_clics
    return await paie_clics._classeur_usage()


async def _ecrire(classeur: str, titre: str, entete: list, lignes: list) -> bool:
    """Réécrit l'onglet `titre` (en-tête + lignes) s'il a changé depuis la dernière écriture. True si écrit."""
    sig = json.dumps(lignes, ensure_ascii=False)
    if _signatures.get(titre) == sig:
        return False
    if (classeur, titre) not in _onglets_crees:
        await google_api.sheets_creer_onglet(classeur, titre)
        _onglets_crees.add((classeur, titre))
    p = (await google_api.sheets_proprietes(classeur)).get(titre) or {}
    besoin = len(lignes) + 51                                            # un onglet neuf a 1 000 lignes : la grille grandit d'abord
    if p.get("id") is not None and int(p.get("lignes") or 0) < besoin:
        await google_api._appel("POST", f"{google_api.SHEETS}/{classeur}:batchUpdate", corps={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": p["id"], "gridProperties": {"rowCount": besoin}}, "fields": "gridProperties.rowCount"}}]})
    await google_api.sheets_effacer(classeur, f"'{titre}'!A1:Z")
    await google_api.sheets_ecrire(classeur, f"'{titre}'!A1", [entete] + lignes, brut=True)
    _signatures[titre] = sig
    return True


async def publier(pil: dict, maintenant: datetime = None) -> int:
    """Écrit les onglets du pilotage qui ont changé. Renvoie le nombre d'onglets écrits (0 sinon). Jamais d'exception."""
    global _verrou
    if not pil or not google_api.actif():
        return 0
    _verrou = _verrou or asyncio.Lock()
    if _verrou.locked():
        return 0                                                         # une publication est déjà en cours : la suivante suffira
    async with _verrou:
        try:
            import dashboard
            maintenant = maintenant or datetime.now(timezone.utc)
            aujourdhui = dashboard._paris(maintenant).date()
            classeur = await _classeur()
            if not classeur:
                return 0
            ecrits = 0
            for titre, entete, lignes in ((ONGLET_COMPTES, ENTETE_COMPTES, pil.get("comptes")),
                                          (ONGLET_CLICS, ENTETE_CLICS, pil.get("clics"))):
                if isinstance(lignes, list) and await _ecrire(classeur, titre, entete, lignes):
                    ecrits += 1
            subs = await _subs(aujourdhui, int(getattr(dashboard, "PILOTAGE_JOURS", 62)))
            if subs is not None and await _ecrire(classeur, ONGLET_SUBS, ENTETE_SUBS, subs):
                ecrits += 1
            if ecrits:
                try:
                    import rapport_quotidien
                    taux = rapport_quotidien.TAUX_USD_EUR
                except Exception:                                        # noqa: BLE001
                    taux = 0.92
                infos = [["Publié", maintenant.astimezone(timezone.utc).isoformat(timespec="seconds")],
                         ["Fraîcheur", str(pil.get("fraicheur") or "")], ["Taux USD→EUR", str(taux)]]
                _signatures.pop(ONGLET_INFOS, None)                      # l'heure change à chaque publication : toujours réécrit
                await _ecrire(classeur, ONGLET_INFOS, ["Clé", "Valeur"], infos)
                journal.info("Pilotage publié : %d onglet(s)", ecrits)
            return ecrits
        except Exception as erreur:                                      # noqa: BLE001 — retentée au prochain passage
            _onglets_crees.clear()
            journal.warning("Pilotage : publication impossible (%s)", str(erreur)[:200])
            return 0
