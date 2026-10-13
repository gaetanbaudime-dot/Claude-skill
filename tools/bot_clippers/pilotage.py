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
import unicodedata
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
                  "Clics 7 j", "Clics 7 j d'avant", "Dernier Reel", "Mesure", "Vues 7 j (dernier relevé)"]   # 13/10 : + vues récentes
ENTETE_CLICS = ["Jour", "Créatrice", "Axe", "Source", "Qui", "Visites payables", "Visites hors robots", "Liens", "Liens non relevés"]
ENTETE_SUBS = ["Jour", "Créatrice", "Subs OF", "CA OF ($)", "Subs MYM", "CA MYM (€)", "Saisi"]
# 13/10 : les clics sur les boutons OnlyFans et MYM des pages (boutons.py), jour × créatrice × axe × source × personne
ONGLET_BOUTONS = "Pilotage boutons"
ENTETE_BOUTONS = ["Jour", "Créatrice", "Axe", "Source", "Qui", "Clics OF", "Clics MYM", "Autres boutons"]
SUBS_TTL_S = 30 * 60
# 12/10 (Gaëtan : app des Team Leaders, et « dans l'app clippeur, un onglet où il peut mettre à jour le @ de ses 3 comptes ») :
# « Comptes app » = les comptes de chaque clipper dans l'ordre du parcours, avec son TL (onglets Comptes et Équipe de l'app) ;
# « Pseudos app » = les @ corrigés depuis l'app (écrits par l'app), appliqués ici avec parcours.renommer (la règle de `!pseudo`)
ONGLET_COMPTES_APP = "Comptes app"
ENTETE_COMPTES_APP = ["Clé app", "Prénom", "Créatrice", "N°", "@", "ETAT", "Followers", "Reels 7 j", "Vues 7 j (48 h)", "Clé app TL",
                      "Prénom TL"]
ONGLET_PSEUDOS = "Pseudos app"
ENTETE_PSEUDOS = ["Date", "Clé app", "N°", "Nouveau @", "Statut", "Détail"]

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


def _txt(v) -> str:
    return "" if v is None or isinstance(v, bool) else str(v)


def lignes_comptes_app(cles_app: dict, comptes_de, tl_de: dict, nom, classeur: dict, chiffres: dict, cle=None) -> list:
    """Pur : une ligne par compte de chaque clipper qui a une clé d'app (uid → clé), dans l'ordre de son parcours (compte 1, 2, 3),
    avec l'ETAT et les chiffres du Dashboard et la clé d'app de son TL. Un clipper sans compte : une ligne sans @ (il voit son
    équipe, rien d'autre)."""
    cle = cle or (lambda h: str(h or "").strip().lstrip("@").lower())
    out = []
    # 13/10 (Gaëtan : « mets à jour les apps TL en fonction des clippeurs qu'ils managent ») : un clipper de l'équipe d'un TL qui
    # n'a pas encore son lien GAML (donc pas d'app) apparaît quand même chez son TL, sous une clé « ~prénom » (aucune app ne
    # l'ouvre) : le TL suit la création de ses comptes dès le premier jour
    sans_app = {}
    for va in (tl_de or {}):
        if str(va) not in {str(u) for u in (cles_app or {})}:
            p = "".join(ch for ch in unicodedata.normalize("NFD", str(nom(va) or "").lower()) if unicodedata.category(ch) != "Mn").strip()
            if p:
                sans_app[str(va)] = "~" + p
    for uid, c_app in sorted(list((cles_app or {}).items()) + list(sans_app.items()), key=lambda x: x[1]):
        tl = str((tl_de or {}).get(str(uid)) or "")
        tl_cle, tl_nom = ((cles_app or {}).get(tl, ""), nom(tl)) if tl else ("", "")
        try:
            handles = [h for h in (comptes_de(uid) or []) if h]
        except Exception:                                               # noqa: BLE001 — fiche illisible : sans compte
            handles = []
        if not handles:
            out.append([c_app, nom(uid), "", "", "", "", "", "", "", tl_cle, tl_nom])
            continue
        for n, h in enumerate(handles, start=1):
            k = cle(h)
            cl, ch = (classeur or {}).get(k) or {}, (chiffres or {}).get(k) or {}
            out.append([c_app, nom(uid), str(cl.get("creatrice") or ""), str(n), k, str(cl.get("etat") or ""),
                        _txt(ch.get("followers")), _txt(ch.get("r7")), _txt(ch.get("v7")), tl_cle, tl_nom])
    return out


def _comptes_app(pil: dict) -> list:
    """Les lignes « Comptes app » avec les modules du bot (parcours, equipes_tl) ; [] s'ils manquent."""
    try:
        import dashboard
        import equipes_tl
        import parcours
    except Exception:                                                   # noqa: BLE001
        return []
    tl_de = {}
    try:
        for e in (equipes_tl.composition() if equipes_tl.branche() else {}).values():
            for va in e.get("vas") or []:
                if e.get("tl"):
                    tl_de[str(va)] = str(e["tl"])
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Pilotage : équipes illisibles (%s)", str(erreur)[:120])

    def nom(uid):
        try:
            return str(equipes_tl.nom_de(uid)).split(" - ")[0].strip()
        except Exception:                                               # noqa: BLE001
            return ""
    return lignes_comptes_app(pil.get("cles_app") or {}, parcours._comptes_ordonnes, tl_de, nom,
                              pil.get("comptes_classeur") or {}, pil.get("chiffres") or {}, dashboard._cle)


async def traiter_pseudos(classeur: str, cles_app: dict, faits: list = None) -> int:
    """Les @ corrigés depuis l'app (onglet « Pseudos app », Statut vide) : appliqués avec parcours.renommer (mêmes contrôles que
    `!pseudo` : un compte à lui, jamais le @ d'un autre de ses comptes, ni un nom de compte privé pour un compte de croissance),
    puis Statut « fait » ou « refusé » et la raison. Renvoie le nombre de demandes traitées. Jamais d'exception."""
    try:
        lignes = await google_api.sheets_lire(classeur, f"'{ONGLET_PSEUDOS}'!A2:F")
    except Exception:                                                   # noqa: BLE001 — onglet pas encore créé par l'app
        return 0
    uid_de = {str(c): str(u) for u, c in (cles_app or {}).items()}
    n_traites = 0
    for i, l in enumerate(lignes, start=2):
        l = (list(l) + [""] * 6)[:6]
        if not l[1].strip() or l[4].strip():
            continue
        uid = uid_de.get(l[1].strip())
        try:
            n = int(str(l[2]).strip())
        except ValueError:
            n = 0
        if not uid:
            statut, detail = "refusé", "clipper inconnu du bot (lien GAML « Clipping Prénom » absent ?)"
        else:
            try:
                import parcours
                ancien, raison = await parcours.renommer(uid, n, l[3].strip())
            except Exception as erreur:                                 # noqa: BLE001
                ancien, raison = "", f"erreur du bot ({type(erreur).__name__}), réessaie dans quelques minutes"
            statut, detail = ("fait", f"{ancien} → {l[3].strip().lstrip('@').lower()}") if not raison else ("refusé", raison)
            if not raison and faits is not None and ancien:             # 13/10 : l'onglet « Comptes app » suit dans le même passage
                faits.append((str(ancien).lstrip("@").lower(), l[3].strip().lstrip("@").lower()))
        try:
            await google_api.sheets_ecrire(classeur, f"'{ONGLET_PSEUDOS}'!E{i}:F{i}", [[statut, detail]], brut=True)
            n_traites += 1
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Pseudos app : statut non écrit (%s)", str(erreur)[:120])
    if n_traites:
        journal.info("Pseudos app : %d demande(s) traitée(s)", n_traites)
    return n_traites


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


_taches = set()


def _relever_boutons(pil: dict, aujourdhui: date) -> None:
    """13/10 : boutons.maj en tâche de fond (jamais au prix de la publication) ; rien hors boucle asyncio."""
    try:
        import boutons
        tache = asyncio.get_running_loop().create_task(boutons.maj(list(pil.get("lids_boutons") or []), aujourdhui))
    except Exception:                                                   # noqa: BLE001
        return
    _taches.add(tache)
    tache.add_done_callback(_taches.discard)


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
            _relever_boutons(pil, aujourdhui)                           # 13/10 : en tâche de fond, au plus toutes les 3 h
            for titre, entete, lignes in ((ONGLET_COMPTES, ENTETE_COMPTES, pil.get("comptes")),
                                          (ONGLET_CLICS, ENTETE_CLICS, pil.get("clics")),
                                          (ONGLET_BOUTONS, ENTETE_BOUTONS, pil.get("boutons"))):
                if isinstance(lignes, list) and await _ecrire(classeur, titre, entete, lignes):
                    ecrits += 1
            # 13/10 (Gaëtan : « si le clippeur met à jour ses @, mets à jour le sheet et l'application de son team leader ») : les @
            # corrigés depuis l'app d'abord (classeur réécrit par parcours.renommer), puis « Comptes app » avec les nouveaux @ —
            # l'app du clipper et celle de son TL les montrent dès ce passage
            faits = []
            await traiter_pseudos(classeur, pil.get("cles_app") or {}, faits)
            comptes_app = _comptes_app(pil)                             # 12/10 : onglets Comptes et Équipe de l'app clippers
            nouveaux = dict(faits)
            for ligne in comptes_app or []:
                if len(ligne) > 4 and str(ligne[4]).lower() in nouveaux:
                    ligne[4] = nouveaux[str(ligne[4]).lower()]
            if comptes_app and await _ecrire(classeur, ONGLET_COMPTES_APP, ENTETE_COMPTES_APP, comptes_app):
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
