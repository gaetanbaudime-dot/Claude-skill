"""Roster actif des clippers par créatrice — la source de vérité unique (26/09, demande de Gaëtan).

Sert au compteur « 🎬 Clippers : N » de STATS G&M, aux groupes du rapport #jonas-stats, à la liste par défaut de
`!salons-equipe`, et aux sorties (`sortis` : fiches retirées du registre, comptes du classeur rendus, salon perso archivé).

Deux fichiers, le plus récent (`maj`) gagne : `roster.json` à côté du bot (dans le repo, édité par Gaëtan ou par Claude) et
`DONNEES/roster.json` (écrit par `!roster`). Format :
  {"maj": "…", "equipes": {"Sophie": ["Thia", …], …}, "nouveaux": ["Pepita"], "sortis": ["Laure", …]}
`nouveaux` : signés dont la créatrice n'est pas encore attribuée (comptés dans l'effectif) ; `!creatrice` les range.
`sans_salon` : les anciens (équipe Jonas) qui n'ont plus de salon perso (supprimé une fois au démarrage, jamais recréé).
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

journal = logging.getLogger("bot.roster")
FICHIER_REPO = Path(__file__).parent / "roster.json"
_deps: dict = {}


def configurer(deps: dict):
    """deps : DONNEES (Path), normaliser, lire_json, ecrire_json, FICHIER_EQUIPES, FICHIER_SORTIS, FICHIER_PIPELINE,
    onboarding (module), est_manager, ADMIN_IDS, notifier (coroutine texte, guild), mettre_a_jour_stats (coroutine)."""
    global _deps
    _deps = deps


def _n(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _fichier_donnees():
    return (_deps["DONNEES"] / "roster.json") if _deps.get("DONNEES") else None


def _charger(p) -> dict:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    d.setdefault("maj", ""); d.setdefault("equipes", {}); d.setdefault("nouveaux", []); d.setdefault("sortis", [])
    d.setdefault("alias", {}); d.setdefault("a_verifier", []); d.setdefault("sans_salon", [])
    return d


def lire() -> dict:
    """Le roster en vigueur : le plus récent des deux fichiers (vide = {"equipes": {}} et tout le monde retombe
    sur l'ancien comportement)."""
    repo, donnees = _charger(FICHIER_REPO), _charger(_fichier_donnees()) if _fichier_donnees() else {}
    if donnees and donnees.get("maj", "") >= repo.get("maj", ""):
        return donnees
    return repo or {"maj": "", "equipes": {}, "nouveaux": [], "sortis": [], "alias": {}, "a_verifier": [], "sans_salon": []}


def ecrire(d: dict):
    d["maj"] = max(datetime.now(timezone.utc).isoformat(timespec="seconds"), _charger(FICHIER_REPO).get("maj", ""))
    p = _fichier_donnees()
    if p is not None and _deps.get("ecrire_json"):
        _deps["ecrire_json"](p, d)


def sans_salon(prenom: str) -> bool:
    """26/09 (Gaëtan) : les clippers historiques de Jonas n'ont plus de salon perso (« ils comprennent rien, ça se mélange avec
    l'ancien système ») ; le salon perso reste réservé aux nouveaux. Ces prénoms ne reçoivent jamais de salon."""
    return _n(prenom) in {_n(x) for x in lire()["sans_salon"]}


def resoudre_alias(nom: str) -> str:
    """« pepita » → « Ricado » quand roster.json porte {"alias": {"Pepita": "Ricado"}} (surnom que Gaëtan emploie ≠ pseudo Discord)."""
    for surnom, vrai in lire()["alias"].items():
        if _n(surnom) == _n(nom):
            return vrai
    return nom


def actif() -> bool:
    return bool(lire()["equipes"])


def groupes() -> dict:
    """{créatrice: [prénoms]} — ce que le rapport Jonas consomme."""
    return {c: list(noms) for c, noms in lire()["equipes"].items()}


def noms_actifs() -> list:
    vus, out = set(), []
    for noms in list(lire()["equipes"].values()) + [lire()["nouveaux"]]:
        for nom in noms:
            if _n(nom) and _n(nom) not in vus:
                vus.add(_n(nom)); out.append(nom)
    return out


def effectif():
    """Nombre de clippers actifs (créatrice attribuée ou non), ou None si le roster est vide."""
    return len(noms_actifs()) if actif() else None


def creatrice_de(prenom: str):
    for c, noms in lire()["equipes"].items():
        if _n(prenom) in {_n(x) for x in noms}:
            return c
    return None


def est_actif(prenom: str) -> bool:
    return _n(prenom) in {_n(x) for x in noms_actifs()}


def ajouter(creatrice: str, prenom: str) -> bool:
    """Range `prenom` sous `creatrice` (le retire d'une autre créatrice, des nouveaux et des sortis). True si changé."""
    d = lire()
    if not d["equipes"] and not creatrice:
        return False
    change = False
    for c, noms in d["equipes"].items():
        if _n(prenom) in {_n(x) for x in noms} and _n(c) != _n(creatrice):
            d["equipes"][c] = [x for x in noms if _n(x) != _n(prenom)]; change = True
    for cle in ("nouveaux", "sortis", "a_verifier"):
        if _n(prenom) in {_n(x) for x in d[cle]}:
            d[cle] = [x for x in d[cle] if _n(x) != _n(prenom)]; change = True
    cible = next((c for c in d["equipes"] if _n(c) == _n(creatrice)), None)
    if cible is None:
        cible = creatrice.strip().capitalize(); d["equipes"][cible] = []; change = True
    if _n(prenom) not in {_n(x) for x in d["equipes"][cible]}:
        d["equipes"][cible].append(prenom.strip()); change = True
    if change:
        ecrire(d)
    return change


def retirer(prenom: str, sorti: bool = True) -> bool:
    """Sort `prenom` de toutes les équipes et des nouveaux ; l'ajoute aux sortis. True si changé."""
    d = lire()
    change = False
    for c, noms in d["equipes"].items():
        if _n(prenom) in {_n(x) for x in noms}:
            d["equipes"][c] = [x for x in noms if _n(x) != _n(prenom)]; change = True
    if _n(prenom) in {_n(x) for x in d["nouveaux"]}:
        d["nouveaux"] = [x for x in d["nouveaux"] if _n(x) != _n(prenom)]; change = True
    if sorti and _n(prenom) not in {_n(x) for x in d["sortis"]}:
        d["sortis"].append(prenom.strip()); change = True
    if change:
        ecrire(d)
    return change


def texte() -> str:
    d = lire()
    if not d["equipes"]:
        return "Roster vide : `!roster Sophie: Thia, Rianah ; Chloé: Hasina ; Sarah: Tara`."
    lignes = [f"👥 **Roster actif : {effectif()} clippers**"]
    for c, noms in d["equipes"].items():
        lignes.append(f"· **{c}** ({len(noms)}) : {', '.join(noms) or '—'}")
    if d["nouveaux"]:
        lignes.append(f"· **Sans créatrice** ({len(d['nouveaux'])}) : {', '.join(d['nouveaux'])} → `!creatrice @x Prénom`")
    if d["a_verifier"]:
        lignes.append(f"· **À vérifier** (rôle Clippeur mais absents de ton roster, pas comptés) : {', '.join(d['a_verifier'])}")
    if d["sortis"]:
        lignes.append(f"-# Sortis : {', '.join(d['sortis'][-12:])}")
    return "\n".join(lignes)


def analyser(corps: str) -> dict:
    """« Sophie: Thia, Rianah ; Chloé: Hasina » → {"Sophie": ["Thia", "Rianah"], "Chloé": ["Hasina"]} (doublons ôtés)."""
    out = {}
    for groupe in [g for g in corps.replace("\n", ";").split(";") if g.strip()]:
        if ":" not in groupe:
            continue
        c, noms = groupe.split(":", 1)
        vus, liste = set(), []
        for nom in [n.strip(" ,.") for n in noms.replace("\n", ",").split(",")]:
            if nom and _n(nom) not in vus:
                vus.add(_n(nom)); liste.append(nom)
        if c.strip():
            out[c.strip().capitalize()] = liste
    return out


# ------------------------------------------------------------------ commande !roster (admin, manager)
async def commande(message, texte_msg: str) -> bool:
    if not texte_msg.lower().startswith("!roster"):
        return False
    auteur = message.author
    if not (str(auteur.id) in _deps.get("ADMIN_IDS", ()) or (_deps.get("est_manager") and _deps["est_manager"](auteur))):
        await message.reply("Commande réservée aux managers et aux admins.")
        return True
    corps = texte_msg[len("!roster"):].strip()
    if not corps:
        await message.reply(texte())
        return True
    mots = corps.split()
    if _n(mots[0]) in ("sortie", "sorti", "retirer") and len(mots) >= 2:
        prenom = " ".join(mots[1:]).strip()
        retirer(prenom)
        bilan = await appliquer_sortis(message.guild.client if message.guild else None, seulement=prenom)
        await message.reply(f"🚪 {prenom} retiré du roster." + (" " + " · ".join(bilan) if bilan else "") + "\n" + texte())
        if _deps.get("mettre_a_jour_stats"):
            await _deps["mettre_a_jour_stats"]()
        return True
    if _n(mots[0]) in ("nouveau", "nouvelle", "ajouter") and len(mots) >= 2:
        d = lire(); prenom = " ".join(mots[1:]).strip()
        if not est_actif(prenom):
            d["nouveaux"].append(prenom); d["sortis"] = [x for x in d["sortis"] if _n(x) != _n(prenom)]; ecrire(d)
        await message.reply(f"🆕 {prenom} ajouté (sans créatrice pour l'instant).\n" + texte())
        if _deps.get("mettre_a_jour_stats"):
            await _deps["mettre_a_jour_stats"]()
        return True
    equipes = analyser(corps)
    if not equipes:
        await message.reply("Format : `!roster Sophie: Thia, Rianah ; Chloé: Hasina, Lilian ; Sarah: Tara` — remplace le roster. "
                            "`!roster` : l'afficher. `!roster sortie Prénom` : une sortie. `!roster nouveau Prénom` : un signé sans créatrice.")
        return True
    d = lire()
    d["equipes"] = equipes
    actifs = {_n(x) for noms in equipes.values() for x in noms}
    d["nouveaux"] = [x for x in d["nouveaux"] if _n(x) not in actifs]
    d["sortis"] = [x for x in d["sortis"] if _n(x) not in actifs]
    ecrire(d)
    await message.reply("✅ Roster remplacé.\n" + texte())
    if _deps.get("mettre_a_jour_stats"):
        await _deps["mettre_a_jour_stats"]()
    return True


# ------------------------------------------------------------------ sorties : nettoyage idempotent
def _fichier_traites():
    return (_deps["DONNEES"] / "roster_sortis_traites.json") if _deps.get("DONNEES") else None


async def appliquer_sortis(client, seulement: str = "", uid: str = "", raison: str = "roster (viré)", garder_salons: bool = False) -> list:
    """Pour chaque prénom de `sortis` pas encore traité (ou `seulement` ce prénom, `uid` connu ou non) : fiche du registre →
    sortis.json, parcours candidat « sorti », comptes du classeur rendus AU VIVIER (`onboarding.liberer(pool=True)` : le
    suivant de la même créatrice les reçoit en premier), lien GAML libéré pour le suivant (`liberer_liens`), salon perso
    SUPPRIMÉ. 28/09 (Gaëtan, Marias parti du serveur) : « delete son salon et attribue ses comptes / liens au prochain » ;
    avant, le salon était renommé « sorti-prenom » et les comptes créés partaient en « à mettre Metricool ».
    Idempotent (trace dans DONNEES/roster_sortis_traites.json). Renvoie une ligne de bilan par prénom traité."""
    d = lire()
    lire_json, ecrire_json = _deps.get("lire_json"), _deps.get("ecrire_json")
    if lire_json is None or _fichier_traites() is None:
        return []
    traites = lire_json(_fichier_traites(), [])
    bilan = []
    for prenom in d["sortis"]:
        if seulement and _n(prenom) != _n(seulement):
            continue
        if not seulement and _n(prenom) in {_n(x) for x in traites}:
            continue
        detail = []
        # 1. Registre des signés → sortis.json : l'uid donné, le prénom en mot entier dans le nom enregistré ou le pseudo Discord,
        #    ou le salon perso enregistré qui porte son prénom (un parti n'a plus de pseudo à comparer).
        registre = lire_json(_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
        salons = []
        if client is not None:
            for g in client.guilds:
                for c in g.text_channels:
                    if _n(c.name) == _n(prenom) or _n(c.name).startswith(_n(prenom) + "-"):
                        salons.append(c)
        uids = [str(uid)] if str(uid) and str(uid) in registre else []
        for uid_f, fiche in list(registre.items()):
            if uid_f in uids:
                continue
            nom_f = fiche.get("nom") or fiche.get("pseudo") or ""
            m = None
            if client is not None:
                for g in client.guilds:
                    m = g.get_member(int(uid_f)) if uid_f.isdigit() else None
                    if m is not None:
                        break
            candidats = [nom_f] + ([m.display_name] if m is not None else [])
            if any(_n(x).split(" - ")[0].split()[0] == _n(prenom) for x in candidats if _n(x)) \
                    or any(str(fiche.get("salon_id") or "") == str(c.id) for c in salons):
                uids.append(uid_f)
        # Un homonyme encore sur le serveur (Julien ×2) : ni le classeur, ni les liens, ni un salon reconnu par son seul nom.
        homonyme = bool(client is not None and _deps.get("prenom_de") and any(
            _n(_deps["prenom_de"](m)) == _n(prenom) and str(m.id) not in uids for g in client.guilds for m in getattr(g, "members", [])))
        salons_fiche = []
        if uids:
            sortis = lire_json(_deps["FICHIER_SORTIS"], []) if _deps.get("FICHIER_SORTIS") else []
            for uid_f in uids:
                fiche = registre.pop(uid_f, {}) or {}
                sid = str(fiche.get("salon_id") or "")
                if sid.isdigit() and client is not None:
                    ch = client.get_channel(int(sid))
                    if ch is not None and ch not in salons_fiche:
                        salons_fiche.append(ch)
                sortis.append({"uid": uid_f, "nom": prenom, "equipe": fiche.get("equipe", ""), "creatrice": fiche.get("creatrice", ""),
                               "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "par": "roster", "raison": raison})
                if _deps.get("oublier_parcours"):
                    try:
                        _deps["oublier_parcours"](uid_f)
                    except Exception:                                       # noqa: BLE001
                        pass
            ecrire_json(_deps["FICHIER_EQUIPES"], registre)
            if _deps.get("FICHIER_SORTIS"):
                ecrire_json(_deps["FICHIER_SORTIS"], sortis[-500:])
            pipe = lire_json(_deps["FICHIER_PIPELINE"], {"liaisons": {}, "etats": {}}) if _deps.get("FICHIER_PIPELINE") else None
            if pipe is not None:
                for uid_f in uids:
                    info = pipe.setdefault("etats", {}).setdefault(uid_f, {})
                    info["etat"] = "sorti"; info.setdefault("relances", {})["stop"] = True
                ecrire_json(_deps["FICHIER_PIPELINE"], pipe)
            detail.append(f"{len(uids)} fiche(s) au registre des sortis")
        # 2. Classeur des logins : ses comptes rendus au vivier — sauf si un homonyme est encore sur le serveur (Julien ×2).
        onb = _deps.get("onboarding")
        if onb is not None and onb.actif() and homonyme:
            detail.append(f"classeur non touché (un autre {prenom} est sur le serveur : `!liberer {prenom} <handles> pool`)")
        elif onb is not None and onb.actif():
            try:
                libere = [b for b in await onb.liberer(prenom, pool=True) if b.startswith("·")]
                if libere:
                    detail.append(f"{len(libere)} compte(s) rendu(s) au vivier")
            except Exception as erreur:                                     # noqa: BLE001
                detail.append(f"classeur : {type(erreur).__name__}")
        # 2b. Lien GAML : libéré pour le suivant de la même créatrice.
        if _deps.get("liberer_liens") and not homonyme:
            try:
                n_liens = _deps["liberer_liens"](uids, prenom, set(registre.keys()))
                if n_liens:
                    detail.append(f"{n_liens} lien(s) GAML libéré(s) pour le suivant")
            except Exception as erreur:                                     # noqa: BLE001
                detail.append(f"liens : {type(erreur).__name__}")
        # 3. Salon perso supprimé (28/09 ; avant : renommé « sorti-prenom ») : celui des fiches, et ceux qui portent son prénom sans homonyme.
        # 30/09 (Jonas, devenu manageur) : `garder_salons` → aucun salon supprimé
        for c in ([] if garder_salons else salons_fiche + ([c for c in salons if c not in salons_fiche] if not homonyme else [])):
            nom_c = c.name
            try:
                await c.delete(reason=f"Roster : {prenom} sorti ({raison})")
                detail.append(f"salon #{nom_c} supprimé")
            except Exception as erreur:                                     # noqa: BLE001
                detail.append(f"salon #{nom_c} non supprimé ({type(erreur).__name__})")
        traites.append(prenom)
        ecrire_json(_fichier_traites(), traites[-300:])
        ligne = f"🚪 {prenom} : " + (", ".join(detail) if detail else "rien à nettoyer")
        bilan.append(ligne)
        journal.info("Roster, sortie traitée : %s", ligne)
    if bilan and _deps.get("notifier") and not seulement:
        try:
            await _deps["notifier"]("**Roster : sorties appliquées**\n" + "\n".join(bilan), client.guilds[0] if client and client.guilds else None)
        except Exception:                                                   # noqa: BLE001
            pass
    return bilan


FICHIER_SORTIES_DEPOSEES = Path(__file__).parent / "sorties_a_appliquer.json"


def _fichier_deposees_faites():
    return (_deps["DONNEES"] / "roster_sorties_deposees.json") if _deps.get("DONNEES") else None


async def sorties_deposees(client) -> list:
    """28/09 : `sorties_a_appliquer.json` (un dépôt, comme les messages) — [{"id", "prenom", "raison"}]. Chaque entrée est
    appliquée une fois au démarrage (retirée du roster, puis `appliquer_sortis`), trace par id. Pour sortir quelqu'un qui a
    déjà quitté le serveur sans taper de commande (Marias, 28/09)."""
    if client is None or not FICHIER_SORTIES_DEPOSEES.exists() or _fichier_deposees_faites() is None or not _deps.get("lire_json"):
        return []
    try:
        entrees = json.loads(FICHIER_SORTIES_DEPOSEES.read_text(encoding="utf-8"))
    except ValueError as erreur:
        journal.warning("sorties_a_appliquer.json illisible : %s", erreur)
        return []
    faits = _deps["lire_json"](_fichier_deposees_faites(), {})
    bilan = []
    for e in entrees if isinstance(entrees, list) else []:
        ident, prenom = str(e.get("id") or ""), str(e.get("prenom") or "").strip()
        if not ident or not prenom or ident in faits:
            continue
        raison_e = str(e.get("raison") or "sortie déposée")
        # 05/10 (Gaëtan : « on vire Hasina et Ckycia ») : "expulser": true → la vraie sortie (`!sortie` : accès, comptes au vivier,
        # lien libéré, salon) avec expulsion du serveur, si le membre est trouvé par son prénom exact ; sinon le nettoyage habituel.
        membre_e = _deps["chercher_membre"](prenom) if e.get("expulser") and _deps.get("chercher_membre") and _deps.get("sortir") else None
        if membre_e is not None:
            try:
                res = await _deps["sortir"](membre_e, raison_e)
                lignes = [f"🚪 {prenom} : sorti" + (" et expulsé" if res.get("expulse") else " (⚠️ pas expulsé)")
                          + f" · {res.get('comptes', 0)} compte(s) au vivier · {res.get('liens', 0)} lien(s) libéré(s)"]
            except Exception as erreur:                                     # noqa: BLE001
                lignes = [f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}"]
            retirer(prenom)
        else:
            retirer(prenom)
            lignes = await appliquer_sortis(client, seulement=prenom, raison=raison_e, garder_salons=bool(e.get("garder_salons")))
        faits[ident] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bilan": lignes}
        _deps["ecrire_json"](_fichier_deposees_faites(), faits)
        bilan.extend(lignes or [f"🚪 {prenom} : rien à nettoyer"])
    if bilan and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Sorties déposées appliquées**\n" + "\n".join(bilan), client.guilds[0] if client.guilds else None)
        except Exception:                                                   # noqa: BLE001
            pass
    return bilan


FICHIER_SALONS_DEPOSES = Path(__file__).parent / "salons_a_ouvrir.json"


async def salons_deposes(client) -> list:
    """06/10 (Gaëtan : « créer un salon personnel dans le discord avec ses login de comptes pour les clippeurs suivants ») :
    `salons_a_ouvrir.json` = [{"id", "prenoms": [...]}]. Chaque entrée, une fois : les prénoms sortent de `sans_salon` (sinon
    `supprimer_salons` effacerait le salon au démarrage suivant), puis `ouvrir_salon` (bot_discord) crée le salon dans la
    catégorie de la créatrice et livre tous les logins. Trace dans DONNEES/roster_salons_ouverts.json."""
    if client is None or not FICHIER_SALONS_DEPOSES.exists() or not _deps.get("DONNEES") or not _deps.get("lire_json") \
            or not _deps.get("ouvrir_salon"):
        return []
    try:
        entrees = json.loads(FICHIER_SALONS_DEPOSES.read_text(encoding="utf-8"))
    except ValueError as erreur:
        journal.warning("salons_a_ouvrir.json illisible : %s", erreur)
        return []
    trace = _deps["DONNEES"] / "roster_salons_ouverts.json"
    faits = _deps["lire_json"](trace, {})
    bilan = []
    for e in entrees if isinstance(entrees, list) else []:
        ident = str(e.get("id") or "")
        prenoms = [str(p).strip() for p in e.get("prenoms") or [] if str(p).strip()]
        if not ident or not prenoms or ident in faits:
            continue
        d = lire()
        cles = {_n(p) for p in prenoms}
        d["sans_salon"] = [x for x in d.get("sans_salon", []) if _n(x) not in cles]
        ecrire(d)
        lignes = []
        ouvrir = _deps.get("ouvrir_salon_simple") if e.get("simple") else _deps["ouvrir_salon"]   # 07/10 : salon seul, sans logins
        for p in prenoms:
            try:
                lignes.append(await ouvrir(p) if ouvrir else f"⚠️ {p} : ouverture simple indisponible")
            except Exception as erreur:                                     # noqa: BLE001
                lignes.append(f"❌ {p} : {type(erreur).__name__} {str(erreur)[:100]}")
        faits[ident] = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bilan": lignes}
        _deps["ecrire_json"](trace, faits)
        bilan.extend(lignes)
    if bilan and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Salons perso ouverts**\n" + "\n".join(bilan), client.guilds[0] if client.guilds else None)
        except Exception:                                                   # noqa: BLE001
            pass
    return bilan


def _dernier_mot(nom: str) -> str:
    parts = _n(nom).split("-")
    return parts[-1] if parts else ""


async def completer_depuis_pseudos(client) -> list:
    """Un membre qui porte un rang (Clippeur/Confirmé/Élite) et un pseudo « Prénom - Créatrice » sans être au roster
    y entre tout seul (Gaëtan renomme tout le monde ainsi). Renvoie les ajouts."""
    if client is None or not actif():
        return []
    rangs = tuple(_n(x) for x in _deps.get("NOMS_RANGS", ("clippeur", "rookie", "confirme", "elite")))
    ajouts = []
    for g in client.guilds:
        for m in g.members:
            if m.bot or str(m.id) in _deps.get("ADMIN_IDS", ()) or (_deps.get("est_manager") and _deps["est_manager"](m)):
                continue
            if not any(any(r_ in _n(role.name) for r_ in rangs) for role in m.roles):
                continue
            prenom = _deps["prenom_de"](m) if _deps.get("prenom_de") else m.display_name.split()[0]
            if est_actif(prenom) or _n(prenom) in {_n(x) for x in lire()["sortis"]}:
                continue
            d = lire()
            if _n(prenom) in {_n(x) for x in d["a_verifier"]}:
                continue
            d["a_verifier"].append(prenom); ecrire(d); ajouts.append(prenom)         # jamais compté sans l'aval de Gaëtan
    if ajouts:
        journal.info("Roster complété depuis les pseudos : %s", ", ".join(ajouts))
    return ajouts


def _creatrice_du_pseudo(pseudo: str) -> str:
    for sep in (" - ", " – ", " — ", " | ", " · "):
        if sep in pseudo:
            reste = pseudo.split(sep, 1)[1].strip()
            for c in lire()["equipes"]:
                if _n(reste).startswith(_n(c)):
                    return c
            return reste.split()[0].capitalize() if reste else ""
    return ""


def _fichier_salons_supprimes():
    return (_deps["DONNEES"] / "roster_salons_supprimes.json") if _deps.get("DONNEES") else None


async def supprimer_salons(client) -> list:
    """Une seule fois par prénom de `sans_salon` : son salon perso est supprimé (liste explicite de Gaëtan du 26/09), son
    `salon_id` retiré du registre, son parcours oublié. Ne touche qu'à un salon texte dont le nom est le prénom (ou
    « prenom-creatrice »), jamais à autre chose."""
    if client is None or not _deps.get("lire_json") or _fichier_salons_supprimes() is None:
        return []
    faits = _deps["lire_json"](_fichier_salons_supprimes(), [])
    bilan = []
    # 27/09 : plus de « une seule fois » — un salon recréé par erreur pour un ancien (Yves, Hasina, Clarisse, Thia, Romaric
    # le 27/09) est supprimé à chaque démarrage tant que le prénom est dans `sans_salon`.
    for prenom in lire()["sans_salon"]:
        registre = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
        cibles, uids = [], []
        for g in client.guilds:
            for c in g.text_channels:
                if _n(c.name) == _n(prenom) or _n(c.name).startswith(_n(prenom) + "-"):
                    cibles.append(c)
        for uid, fiche in registre.items():
            m = next((g.get_member(int(uid)) for g in client.guilds if uid.isdigit() and g.get_member(int(uid))), None)
            nom_m = _deps["prenom_de"](m) if (m is not None and _deps.get("prenom_de")) else ""
            if _n(nom_m) == _n(prenom) or any(str(fiche.get("salon_id") or "") == str(c.id) for c in cibles):
                uids.append(uid)
                sid = str(fiche.get("salon_id") or "")
                if sid.isdigit():
                    ch = client.get_channel(int(sid))
                    if ch is not None and ch not in cibles:
                        cibles.append(ch)
        if not cibles:                                                  # aucun salon : rien à faire, rien à dire
            continue
        detail = []
        for c in cibles:
            nom_c = c.name
            try:
                await c.delete(reason=f"Roster : plus de salon perso pour {prenom} (liste de Gaëtan du 26/09)")
                detail.append(f"#{nom_c} supprimé")
            except Exception as erreur:                                     # noqa: BLE001
                detail.append(f"#{nom_c} non supprimé ({type(erreur).__name__})")
        if uids:
            for uid in uids:
                registre.get(uid, {}).pop("salon_id", None)
                if _deps.get("oublier_parcours"):
                    try:
                        _deps["oublier_parcours"](uid)
                    except Exception:                                       # noqa: BLE001
                        pass
            _deps["ecrire_json"](_deps["FICHIER_EQUIPES"], registre)
        faits.append(prenom)
        _deps["ecrire_json"](_fichier_salons_supprimes(), faits[-300:])
        ligne = f"🗑️ {prenom} : " + (", ".join(detail) if detail else "aucun salon trouvé")
        bilan.append(ligne)
        journal.info("Roster, salon perso retiré : %s", ligne)
    if bilan and _deps.get("notifier"):
        try:
            await _deps["notifier"]("**Roster : salons persos des anciens supprimés**\n" + "\n".join(bilan), client.guilds[0] if client.guilds else None)
        except Exception:                                                   # noqa: BLE001
            pass
    return bilan


async def demarrage(client):
    """Au démarrage : sorties appliquées, roster complété depuis les pseudos, compteur rafraîchi."""
    try:
        await appliquer_sortis(client)
        await sorties_deposees(client)                                     # 28/09 : sorties écrites dans le dépôt
        await salons_deposes(client)                                       # 06/10 : AVANT supprimer_salons (qui viderait les nouveaux)
        await supprimer_salons(client)
        await completer_depuis_pseudos(client)
        if _deps.get("onboarder_manquants"):
            await _deps["onboarder_manquants"]()
        if _deps.get("mettre_a_jour_stats"):
            await _deps["mettre_a_jour_stats"]()
        journal.info("Roster : %s clippers actifs (%s)", effectif(), "; ".join(f"{c} {len(n)}" for c, n in lire()["equipes"].items()))
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Roster au démarrage : %s", erreur)
