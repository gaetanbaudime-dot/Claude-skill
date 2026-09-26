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


async def appliquer_sortis(client, seulement: str = "") -> list:
    """Pour chaque prénom de `sortis` pas encore traité : fiche du registre → sortis.json, parcours candidat « sorti »,
    comptes du classeur rendus (`onboarding.liberer`), salon perso renommé « sorti-prenom ». Idempotent (trace dans
    DONNEES/roster_sortis_traites.json). Renvoie une ligne de bilan par prénom traité."""
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
        # 1. Registre des signés → sortis.json (prénom en mot entier dans le nom enregistré ou le pseudo Discord).
        registre = lire_json(_deps["FICHIER_EQUIPES"], {}) if _deps.get("FICHIER_EQUIPES") else {}
        uids = []
        for uid, fiche in list(registre.items()):
            nom_f = fiche.get("nom") or fiche.get("pseudo") or ""
            m = None
            if client is not None:
                for g in client.guilds:
                    m = g.get_member(int(uid)) if uid.isdigit() else None
                    if m is not None:
                        break
            candidats = [nom_f] + ([m.display_name] if m is not None else [])
            if any(_n(x).split(" - ")[0].split()[0] == _n(prenom) for x in candidats if _n(x)):
                uids.append(uid)
        if uids:
            sortis = lire_json(_deps["FICHIER_SORTIS"], []) if _deps.get("FICHIER_SORTIS") else []
            for uid in uids:
                fiche = registre.pop(uid, {}) or {}
                sortis.append({"uid": uid, "nom": prenom, "equipe": fiche.get("equipe", ""), "creatrice": fiche.get("creatrice", ""),
                               "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "par": "roster", "raison": "roster (viré)"})
            ecrire_json(_deps["FICHIER_EQUIPES"], registre)
            if _deps.get("FICHIER_SORTIS"):
                ecrire_json(_deps["FICHIER_SORTIS"], sortis[-500:])
            pipe = lire_json(_deps["FICHIER_PIPELINE"], {"liaisons": {}, "etats": {}}) if _deps.get("FICHIER_PIPELINE") else None
            if pipe is not None:
                for uid in uids:
                    info = pipe.setdefault("etats", {}).setdefault(uid, {})
                    info["etat"] = "sorti"; info.setdefault("relances", {})["stop"] = True
                ecrire_json(_deps["FICHIER_PIPELINE"], pipe)
            detail.append(f"{len(uids)} fiche(s) au registre des sortis")
        # 2. Classeur des logins : ses comptes rendus.
        onb = _deps.get("onboarding")
        if onb is not None and onb.actif():
            try:
                libere = [b for b in await onb.liberer(prenom) if b.startswith("·")]
                if libere:
                    detail.append(f"{len(libere)} compte(s) du classeur rendu(s)")
            except Exception as erreur:                                     # noqa: BLE001
                detail.append(f"classeur : {type(erreur).__name__}")
        # 3. Salon perso archivé (renommé, jamais supprimé).
        if client is not None:
            for g in client.guilds:
                for c in g.text_channels:
                    if _n(c.name) == _n(prenom) or _n(c.name).startswith(_n(prenom) + "-"):
                        ancien = c.name
                        try:
                            await c.edit(name=f"sorti-{_n(prenom)}", reason="Roster : clipper sorti")
                            detail.append(f"salon #{ancien} → #sorti-{_n(prenom)}")
                        except Exception as erreur:                         # noqa: BLE001
                            detail.append(f"salon #{c.name} non renommé ({type(erreur).__name__})")
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
    for prenom in lire()["sans_salon"]:
        if _n(prenom) in {_n(x) for x in faits}:
            continue
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
        await supprimer_salons(client)
        await completer_depuis_pseudos(client)
        if _deps.get("onboarder_manquants"):
            await _deps["onboarder_manquants"]()
        if _deps.get("mettre_a_jour_stats"):
            await _deps["mettre_a_jour_stats"]()
        journal.info("Roster : %s clippers actifs (%s)", effectif(), "; ".join(f"{c} {len(n)}" for c, n in lire()["equipes"].items()))
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Roster au démarrage : %s", erreur)
