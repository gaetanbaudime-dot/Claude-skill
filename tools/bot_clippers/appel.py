"""L'appel de présence (05/10, Gaëtan : « vire tous les clippeurs qui ne répondent pas et qui sont inactifs sur le serveur, je veux
que ça réponde et qu'ils viennent sur WhatsApp »).

Deux moments :
1. **L'appel général**, une fois, au premier démarrage (APPEL_GENERAL=1) : dans le salon perso de chaque clipper signé, « réponds ici
   dans les 48 h, un mot suffit, et écris à Gaëtan sur WhatsApp » (bouton wa.me avec le message déjà écrit). `!appel go` le relance
   pour ceux qui n'ont pas d'appel en cours.
2. **L'appel individuel**, automatique : un clipper signé sans aucune activité sur le serveur depuis APPEL_INACTIF_JOURS jours (aucun
   message, aucun bouton d'étape, aucun Reel vu par le scan) reçoit le même appel.

Dans les deux cas : une réponse = n'importe quel message de lui sur le serveur ou un bouton d'étape (noter_activite). Sans réponse à
APPEL_HEURES (48) : sortie comme `!sortie` avec expulsion (APPEL_KICK=1) — comptes au vivier, lien libéré, salon supprimé, parcours oublié.
A répondu mais pas venu sur WhatsApp (`!wa @clipper` jamais tapé) : une relance WhatsApp 24 h plus tard et une ligne à Gaëtan ; pas
d'expulsion automatique pour ça (Gaëtan tranche avec `!sortie`). Protégés : staff, anciens de Jonas (`sans_salon`), note « garde ».
État dans appel.json : {"appels": {uid: {date, salon_id, motif, repondu, relance_wa, sorti}}, "activite": {uid: iso}, "general": {date, n}}.
`!appel` (staff) : l'état ; `!appel go` : l'appel général ; `!appel @clipper` : un appel individuel ; APPEL=0 éteint.

10/10 (revue du recrutement, L9a : l'appel est gardé, son défaut corrigé) : il expulsait des clippers qui publient quand le scan ne
lisait plus leurs comptes (budget Apify coupé, compte restreint, passage raté) : le silence du scan passait pour de l'inactivité.
Désormais, un clipper dont le scan n'a lu aucun compte public récemment (sortie_auto.mesures) est « non mesuré » : jamais appelé
pour inactivité, jamais purgé (sortie_auto.compte_lu). Le calcul des visites vit dans sortie_auto.visites.

11/10 (revue de L9a) : seul ce défaut est corrigé, la règle du 05/10 reste entière. Un clipper mesuré, sans réponse à l'échéance
et sans visites, sort même s'il publie (coût accepté le 05/10 : « ceux qui publient mais ne lisent pas Discord vont sortir »).
À l'échéance :
- mesure illisible (classeur ou scan en panne à ce passage) : rien n'est écrit, il est repris 30 min plus tard ;
- clipper non mesuré : l'appel reste OUVERT (une seule ligne ⏸️, au point du matin, drapeau `non_mesure_signale`), une réponse le
  solde toujours ; il est jugé au premier passage où le scan lit ses comptes, et l'appel n'est clos sans sortie (`non_mesure`)
  qu'après APPEL_MESURE_ATTENTE jours (7) sans mesure. Jamais un deuxième appel pendant ce temps.
Mesure illisible depuis APPEL_ILLISIBLE_ALERTE_H heures (6) d'affilée : une ligne ⚠️ au salon admin (« appel suspendu »), puis une
par jour tant que ça dure, et une ligne ✅ quand elle revient, au point du matin (état `illisible` dans appel.json, visible
dans `!appel`).
Branchements gardés au démarrage (lot W, amendement B) : `import appel`, appel.configurer, parcours._deps["activite"] =
appel.noter_activite, la tâche appel.boucle, appel.noter_activite et appel.commande dans on_message, `!appel` et `!purge` dans
COMMANDES_MANAGER.

11/10 (lot W, « en direct, uniquement ce qui demande un geste ») : les lignes ⏸️, ✅, 🔇 et 📢 du passage attendent le point du
matin (trier_bilan, bilan_pour_digest) ; 🚪, 📲, ⚠️ et ❌ restent en direct. Un appel clos sans sortie (`non_mesure`) n'est plus
soldé par un message écrit après coup."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord

journal = logging.getLogger("appel")
ACTIF = os.environ.get("APPEL", "1").strip() != "0"
HEURES = int(os.environ.get("APPEL_HEURES", "48") or 48)
INACTIF_JOURS = int(os.environ.get("APPEL_INACTIF_JOURS", "2") or 2)       # 05/10, 15 h 30 : 2 jours (4 avant)
KICK = os.environ.get("APPEL_KICK", "1").strip() != "0"
# Calls are non-punitive by default; the central removal guard independently requires opt-in.
SORTIE_AUTOMATIQUE = os.environ.get("APPEL_SORTIE_AUTO", "0").strip() == "1"
GENERAL = os.environ.get("APPEL_GENERAL", "1").strip() != "0"
# 05/10 (Gaëtan : « vire directement les clippeurs qui n'ont pas créé de compte dans les 72 h et n'ont pas répondu sur leur salon
# privé ») : la purge, une fois au démarrage (PURGE_72H=1), puis `!purge` / `!purge go`.
PURGE = os.environ.get("PURGE_72H", "1").strip() != "0"
PURGE_HEURES = int(os.environ.get("PURGE_HEURES", "48") or 48)         # 05/10, 15 h 30 : compte 1 en 48 h (72 avant)
# 05/10, 15 h (Gaëtan : « premier compte IG créé en 3 jours », « applique à tout le monde ») : le compte 1 non créé suffit, qu'il ait
# parlé ou non dans son salon (PURGE_SILENCE=1 pour revenir à « et pas un mot ») ; la purge tourne à chaque passage (30 min).
PURGE_SILENCE = os.environ.get("PURGE_SILENCE", "0").strip() == "1"
RAISON_PURGE = (f"{PURGE_HEURES} h sans créer ton compte 1 et sans un mot dans ton salon" if PURGE_SILENCE
                else f"compte 1 Instagram non créé {PURGE_HEURES} h après l'avoir reçu")
_deps = {}

TEXTE_APPEL = ("📢 **{prenom}, petit point de présence : peux-tu répondre ici ?** Un mot suffit : « présent ».\n\n"
               "Et écris à Gaëtan sur WhatsApp (bouton ci-dessous, {wa}) pour que l'équipe puisse t'aider.\n\n"
               "Une absence de réponse sera signalée au manager pour vérification ; "
               "elle ne déclenche aucune exclusion automatique.")
TEXTE_RELANCE_WA = ("📲 {prenom}, merci pour ta réponse. Il manque WhatsApp : écris à Gaëtan maintenant (bouton ci-dessous), "
                    "il ouvre ton groupe. C'est là que tout se passe.\n\nDéjà fait ? Appuie sur « ✅ J'ai écrit à Gaëtan ».")
RAISON = f"sans réponse à l'appel depuis {HEURES} h"
# 08/10 (audit : les anciens rouverts, muets sur Discord, comptes restreints, allaient être appelés puis expulsés alors que leur lien
# ramène du monde) : des visites sur ses liens GAML sur INACTIF_JOURS jours = une activité. Au-dessous du seuil, nos propres
# clics de contrôle.
VISITES_ACTIF = int(os.environ.get("APPEL_VISITES_ACTIF", "5") or 5)
# 11/10 (revue de L9a) : un appel échu sur un clipper non mesuré attend la mesure du scan au plus ce nombre de jours, puis il est
# clos sans sortie
MESURE_ATTENTE = int(os.environ.get("APPEL_MESURE_ATTENTE", "7") or 7)
# 11/10 (rejeu de L9a) : mesure du scan illisible depuis ce nombre d'heures d'affilée → une ligne au salon admin (puis une par jour
# tant que ça dure) : l'appel est suspendu, Gaëtan doit le savoir. Une panne d'un passage ne fait pas de bruit.
ILLISIBLE_ALERTE_H = int(os.environ.get("APPEL_ILLISIBLE_ALERTE_H", "6") or 6)


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, salons_clippers (async -> [(salon, membre)]), salon_perso (uid -> salon),
    parcours_lire (-> fiches), sortir (async membre, raison, pool, expulser), canal_admin (async), prenom_de, notes (uid -> [textes]),
    roster, normaliser, heure_paris, jours_sans_reel (async -> {uid: jours}), lien_whatsapp (uid -> url), est_staff, membre_par_id."""
    _deps.update(deps)


def _n(t) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else str(t or "").strip().lower()


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER"], {})
    d.setdefault("appels", {}); d.setdefault("activite", {}); d.setdefault("general", {})
    return d


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER"], d)


def _iso(dt) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _dt(iso):
    try:
        d = datetime.fromisoformat(str(iso)[:25])
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


# ------------------------------------------------------------------ activité
def noter_activite(uid, quand=None) -> bool:
    """Un message du clipper sur le serveur, ou un bouton d'étape : sa dernière activité, et la réponse à son appel en cours.
    Renvoie True si un appel vient d'être soldé."""
    if not _deps:
        return False
    quand = quand or datetime.now(timezone.utc)
    d = _lire()
    uid = str(uid)
    d["activite"][uid] = _iso(quand)
    a = d["appels"].get(uid)
    solde = False
    # 11/10 (lot W, contre-vérification du lot L9a) : un appel clos sans sortie (`non_mesure`) n'est plus soldé par un message
    # écrit des semaines plus tard (le clipper recevait « merci pour ta réponse » et passait dans « Ont répondu »)
    if a and not a.get("repondu") and not a.get("sorti") and not a.get("non_mesure") and (_dt(a.get("date")) or quand) <= quand:
        a["repondu"] = _iso(quand)
        solde = True
    _ecrire(d)
    return solde


async def derniere_activite_salon(salon, membre, limite: int = 100):
    """La date du dernier message du membre dans son salon (lecture de l'historique), None s'il n'y a rien."""
    try:
        async for m in salon.history(limit=limite):
            if getattr(m.author, "id", None) == membre.id:
                return m.created_at
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.info("Historique de #%s illisible : %s", getattr(salon, "name", "?"), erreur)
    return None


def _protege(uid: str, prenom: str) -> bool:
    roster = _deps.get("roster")
    if roster is not None and prenom and roster.sans_salon(prenom):
        return True
    notes = _deps.get("notes")
    return any("garde" in _n(t) for t in (notes(uid) if notes else []))


def _consigne_wa(uid: str) -> str:
    """08/10 : « le message est déjà écrit » seulement si le lien le porte (parcours.consigne_whatsapp), sinon le message à envoyer."""
    try:
        return _deps["consigne_whatsapp"](uid) if _deps.get("consigne_whatsapp") else "le message est déjà écrit"
    except Exception:                                                   # noqa: BLE001
        return "dis-lui ton prénom et ta créatrice"


def _vue(uid: str):
    url = _deps["lien_whatsapp"](uid) if _deps.get("lien_whatsapp") else ""
    if not url:
        return None
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="📲 Écrire à Gaëtan sur WhatsApp", style=discord.ButtonStyle.link, url=url))
    if _deps.get("bouton_wa"):                                          # 08/10 : « ✅ J'ai écrit à Gaëtan » (parcours.BoutonWhatsApp)
        vue.add_item(_deps["bouton_wa"](uid))
    return vue


# ------------------------------------------------------------------ l'appel
async def _completer_activite(cibles: list) -> None:
    """La dernière activité inconnue de chaque cible, lue une fois dans l'historique de son salon. 08/10 : les lectures d'abord
    (elles attendent Discord), puis l'état relu et complété sans attente : l'ancienne version réécrivait une copie lue AVANT ces
    attentes et effaçait une réponse à l'appel arrivée entre-temps (« repondu » perdu = sortie pour « sans réponse »)."""
    connues = _lire()["activite"]
    lues = {}
    for salon, membre in cibles:
        uid = str(membre.id)
        if uid not in connues and uid not in lues:
            quand = await derniere_activite_salon(salon, membre)
            # 08/10 : rien écrit dans le salon → la date de création du salon (un salon neuf a ses jours de grâce)
            quand = quand or getattr(salon, "created_at", None)
            lues[uid] = _iso(quand) if quand else ""
    if lues:
        d = _lire()
        for uid, v in lues.items():
            d["activite"].setdefault(uid, v)
        _ecrire(d)


async def lancer_appel(cibles: list, motif: str, maintenant=None) -> list:
    """Poste l'appel dans le salon perso de chaque (salon, membre) sans appel en cours. Renvoie les prénoms appelés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    d = _lire()
    appeles = []
    for salon, membre in cibles:
        uid = str(membre.id)
        prenom = _deps["prenom_de"](membre) if _deps.get("prenom_de") else getattr(membre, "display_name", uid)
        a = d["appels"].get(uid)
        if a and not a.get("sorti") and not a.get("repondu") and not a.get("non_mesure") and (
                a.get("non_mesure_signale") or a.get("verification_humaine") or
                (_dt(a.get("date")) or maintenant) + timedelta(hours=HEURES) > maintenant):
            continue                                                    # un appel court déjà (11/10 : ou échu, il attend la mesure)
        if _protege(uid, prenom):
            continue
        try:
            vue = _vue(uid)
            texte = f"{membre.mention} " + TEXTE_APPEL.format(prenom=prenom, heures=HEURES, wa=_consigne_wa(uid))
            msg = await (salon.send(texte, view=vue) if vue is not None else salon.send(texte))
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Appel de %s : %s", prenom, erreur)
            continue
        # 08/10 : l'appel est écrit tout de suite, dans l'état relu, sans attente entre la lecture et l'écriture. Avant, la copie lue
        # au début était réécrite après tous les envois (pauses comprises) : une réponse arrivée pendant ces secondes (un clipper qui
        # répond « présent » dès la notification) était effacée, et il sortait 48 h plus tard « sans réponse ».
        d_a = _lire()
        d_a["appels"][uid] = {"date": _iso(maintenant), "salon_id": str(salon.id), "message_id": str(getattr(msg, "id", "")),
                              "motif": motif, "prenom": prenom, "repondu": None, "relance_wa": None, "sorti": None}
        _ecrire(d_a)
        appeles.append(f"{prenom} (<@{uid}>)")                           # 08/10 : deux « Andry » → la mention lève le doute
        await asyncio.sleep(0.5)
    if appeles:
        journal.info("Appel (%s) posté à %d clipper(s)", motif, len(appeles))
    return appeles


def visites(uid: str, jours: int) -> int:
    """08/10 : visiteurs (hors robots) sur ses liens GAML les `jours` derniers jours, hier compris ; 0 sans paie au clic.
    10/10 (L9a) : le calcul vit dans sortie_auto.visites (une seule source)."""
    import sortie_auto                                                  # import tardif, comme paie_clics avant
    return sortie_auto.visites(uid, jours)


async def _mesures():
    """10/10 (L9a) : {uid: True/False}, le scan a-t-il lu les comptes de chaque clipper (sortie_auto.mesures) ? None si
    illisible : personne n'est alors appelé ni sorti à ce passage."""
    try:
        if _deps.get("mesures"):
            return await _deps["mesures"]()
        import sortie_auto                                              # configuré au démarrage avant l'appel
        return await sortie_auto.mesures()
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Mesure du scan illisible : %s", erreur)
        return None


def _comptes_lus(handles) -> bool:
    """10/10 (L9a) : un de ces comptes a-t-il un relevé récent du scan (sortie_auto.compte_lu) ? Non, ou illisible : non mesuré."""
    if not handles:
        return False
    try:
        if _deps.get("compte_lu"):
            return bool(_deps["compte_lu"](handles))
        import sortie_auto
        return bool(sortie_auto.compte_lu(handles))
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Relevés du scan illisibles : %s", erreur)
        return False


def est_mesure(uid: str, mesures, sans_reel) -> bool:
    """10/10 (L9a) : le scan lit ses comptes (mesures) ET son silence Instagram est compté (jours_sans_reel)."""
    return mesures is not None and sans_reel is not None and bool(mesures.get(str(uid))) and str(uid) in sans_reel


def a_sortir(d: dict, maintenant=None) -> list:
    """[(uid, appel)] : appel sans réponse depuis HEURES heures ou plus (10/10 : un appel clos « non mesuré » n'y est plus ; 11/10 :
    un appel échu qui attend la mesure du scan, `non_mesure_signale`, y reste jusqu'à ce qu'il soit jugé ou clos)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for uid, a in d.get("appels", {}).items():
        if a.get("repondu") or a.get("sorti") or a.get("non_mesure") or a.get("verification_humaine"):
            continue
        debut = _dt(a.get("date"))
        if debut is not None and maintenant >= debut + timedelta(hours=HEURES):
            out.append((uid, a))
    return out


def a_relancer_wa(d: dict, parcours: dict, maintenant=None) -> list:
    """[(uid, appel)] : a répondu il y a 24 h ou plus, pas de `!wa`, pas encore relancé pour WhatsApp."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for uid, a in d.get("appels", {}).items():
        if not a.get("repondu") or a.get("sorti") or a.get("relance_wa") or a.get("repondu_par") == "visites":
            continue                                                    # 08/10 : muet mais actif : pas de « merci pour ta réponse »
        if (parcours.get(uid) or {}).get("whatsapp"):
            continue
        rep = _dt(a.get("repondu"))
        if rep is not None and maintenant >= rep + timedelta(hours=24):
            out.append((uid, a))
    return out


def inactifs(activite: dict, sans_reel: dict, cibles: list, appels: dict, maintenant=None, jours: int = None, vues=None,
             mesures=None) -> list:
    """[(salon, membre, jours d'inactivité)] : signés sans appel en cours, dont la dernière activité connue (message, bouton)
    ET le dernier Reel vu remontent à `jours` jours ou plus. Sans aucune activité connue : considéré inactif (l'historique a été lu).
    10/10 (L9a) : avec `mesures` ({uid: bool}), un clipper que le scan ne lit pas (est_mesure faux) n'est jamais inactif."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jours = INACTIF_JOURS if jours is None else jours
    out = []
    for salon, membre in cibles:
        uid = str(membre.id)
        if mesures is not None and not est_mesure(uid, mesures, sans_reel):
            continue                                                    # 10/10 : non mesuré (scan coupé, restreint, passage raté)
        a = appels.get(uid)
        clos = a.get("repondu") or a.get("non_mesure") if a else None
        if a and (a.get("sorti") or not clos or (_dt(a.get("date")) or maintenant) + timedelta(days=jours) > maintenant):
            continue                                                    # déjà sorti (jamais rappelé tout seul), appel en cours, ou répondu récemment
        if vues is not None and vues(uid, jours) >= VISITES_ACTIF:
            continue                                                    # 08/10 : son lien ramène du monde, il travaille
        derniere = _dt(activite.get(uid))
        jr = sans_reel.get(uid)
        if jr is not None and jr >= 0:
            d_reel = maintenant - timedelta(days=int(jr))
            derniere = d_reel if derniere is None or d_reel > derniere else derniere
        if derniere is None:
            out.append((salon, membre, jours))
        elif maintenant - derniere >= timedelta(days=jours):
            out.append((salon, membre, (maintenant - derniere).days))
    return out


async def executer(client, appliquer: bool = True, maintenant=None) -> list:
    """Un passage : sorties des sans-réponse, relances WhatsApp, appels individuels des inactifs. Renvoie le bilan (lignes)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    bilan = []
    d = _lire()
    parcours = _deps["parcours_lire"]() if _deps.get("parcours_lire") else {}
    expires = a_sortir(d, maintenant)
    sans_reel, mesures = None, None
    scan_lu = False

    async def _scan():
        """10/10 (L9a) : le silence Instagram ({uid: jours}) et la mesure ({uid: lu ?}), lus une fois par passage."""
        nonlocal sans_reel, mesures, scan_lu
        scan_lu = True
        try:
            sans_reel = await _deps["jours_sans_reel"]() if _deps.get("jours_sans_reel") else {}
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Jours sans Reel illisibles : %s", erreur)
            sans_reel = None                                            # 08/10 : scan illisible → personne n'est appelé à ce passage
        mesures = await _mesures() if sans_reel is not None else None
    if expires:
        await _scan()
    # 1. sans réponse → sortie + expulsion, seulement s'il est mesuré (10/10) ; 11/10 : mesure illisible = rien à ce passage,
    # non mesuré = appel laissé ouvert jusqu'à la mesure (MESURE_ATTENTE jours au plus)
    for uid, a in expires:
        prenom = a.get("prenom") or uid
        n_vis = visites(uid, max(1, HEURES // 24))
        illisible = sans_reel is None or mesures is None
        mesure = est_mesure(uid, mesures, sans_reel)
        if not appliquer:
            suite = ("muet mais actif (visites) → pas sorti" if n_vis >= VISITES_ACTIF
                     else "mesure du scan illisible → rien à ce passage" if illisible
                     else "non mesuré (le scan ne lit pas ses comptes) → pas sorti, jugé dès qu'il est mesuré" if not mesure
                     else "à vérifier par un manager (sans exclusion automatique)" if not SORTIE_AUTOMATIQUE
                     else "sortirait" + (" et expulsé" if KICK else ""))
            bilan.append(f"· {prenom} : sans réponse depuis {HEURES} h, {suite}")
            continue
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        d = _lire()
        if (d["appels"].get(uid) or {}).get("repondu"):
            continue                                                    # 08/10 : a répondu pendant le passage
        if n_vis >= VISITES_ACTIF:
            # 08/10 (audit : les six sorties du 07/10 ignoraient Reels et visites) : muet sur Discord mais son lien travaille
            d["appels"][uid]["repondu"] = _iso(maintenant)
            d["appels"][uid]["repondu_par"] = "visites"
            _ecrire(d)
            bilan.append(f"🔇 {prenom} (<@{uid}>) : muet sur Discord mais actif ({n_vis} visiteurs en {max(1, HEURES // 24) * 24} h) → pas sorti")
            continue
        if m is None:                                                   # déjà parti du serveur : on solde
            d["appels"][uid]["sorti"] = _iso(maintenant); _ecrire(d)
            bilan.append(f"· {prenom} (<@{uid}>) : plus sur le serveur, appel clos")
            continue
        if illisible:
            continue                                                    # 11/10 : classeur ou scan en panne : rien d'écrit, repris dans 30 min
        if not mesure:
            # 10/10 (L9a) : budget Apify coupé, compte restreint ou passage raté : son silence ne prouve rien → pas de sortie.
            # 11/10 : l'appel reste ouvert (une réponse le solde), une seule ligne ; jugé dès qu'il est mesuré, clos après
            # MESURE_ATTENTE jours sans mesure (avant : clos tout de suite, puis rappelé du même message au passage suivant)
            a_d = d["appels"][uid]
            signale = _dt(a_d.get("non_mesure_signale"))
            if signale is None:
                a_d["non_mesure_signale"] = _iso(maintenant); _ecrire(d)
                bilan.append(f"⏸️ {prenom} (<@{uid}>) : sans réponse, mais le scan ne lit pas ses comptes (non mesuré) → pas sorti. "
                             f"Jugé dès que le scan les relit ; appel clos sans sortie dans {MESURE_ATTENTE} j sinon")
            elif maintenant >= signale + timedelta(days=MESURE_ATTENTE):
                a_d["non_mesure"] = _iso(maintenant); _ecrire(d)
                bilan.append(f"⏸️ {prenom} (<@{uid}>) : {MESURE_ATTENTE} j sans mesure du scan → appel clos, pas sorti")
            continue
        if not SORTIE_AUTOMATIQUE:
            # An expired call can only trigger a human review, never touch the account.
            a_d = d["appels"].get(uid, {})
            a_d["verification_humaine"] = _iso(maintenant)
            d["appels"][uid] = a_d
            _ecrire(d)
            bilan.append(f"⚠️ {prenom} (<@{uid}>) : appel sans réponse ; "
                         "à vérifier manuellement, AUCUNE sortie ni réattribution.")
            continue
        try:
            res = await _deps["sortir"](m, RAISON, pool=True, expulser=KICK)
            d = _lire(); d["appels"][uid]["sorti"] = _iso(maintenant); d["appels"][uid]["expulse"] = bool(res.get("expulse")); _ecrire(d)
            bilan.append(f"🚪 {prenom} (<@{uid}>) : sorti ({RAISON})" + (" · expulsé" if res.get("expulse") else " · ⚠️ pas expulsé")
                         + (f" · refus : {', '.join(res.get('refus') or [])}" if res.get("refus") else ""))
        except Exception as erreur:                                     # noqa: BLE001
            bilan.append(f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}")
            journal.warning("Sortie après appel de %s : %s", prenom, erreur)
    # 2. a répondu, pas de WhatsApp → une relance, une ligne à Gaëtan
    for uid, a in a_relancer_wa(_lire(), parcours, maintenant):
        prenom = a.get("prenom") or uid
        if not appliquer:
            bilan.append(f"· {prenom} : a répondu, pas de WhatsApp → relance")
            continue
        salon = client.get_channel(int(a.get("salon_id") or 0)) if client is not None else None
        d = _lire(); d["appels"][uid]["relance_wa"] = _iso(maintenant); _ecrire(d)
        if salon is not None:
            try:
                vue = _vue(uid)
                texte = f"<@{uid}> " + TEXTE_RELANCE_WA.format(prenom=prenom)
                await (salon.send(texte, view=vue) if vue is not None else salon.send(texte))
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Relance WhatsApp de %s : %s", prenom, erreur)
        bilan.append(f"📲 {prenom} (<@{uid}>) : a répondu, pas de WhatsApp → relancé (`!wa @{prenom}` quand c'est fait)")
    # 3. inactifs → appel individuel (10/10 : seulement parmi les clippers mesurés)
    if _deps.get("salons_clippers"):
        try:
            cibles = await _deps["salons_clippers"]()
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Salons des clippers illisibles : %s", erreur)
            cibles = []
        if not expires:
            await _scan()
        await _completer_activite(cibles)
        d = _lire()
        lents = (inactifs(d["activite"], sans_reel, cibles, d["appels"], maintenant, vues=visites, mesures=mesures)
                 if sans_reel is not None and mesures is not None else [])
        lents = [(s, m, j) for s, m, j in lents if not _protege(str(m.id), _deps["prenom_de"](m) if _deps.get("prenom_de") else "")]
        illisible = sans_reel is None or mesures is None
        non_mes = [] if illisible else [_deps["prenom_de"](m) if _deps.get("prenom_de") else str(m.id) for _, m in cibles
                                        if not est_mesure(str(m.id), mesures, sans_reel)]
        if appliquer and not illisible:                                 # 10/10 : pour `!appel`, pas de ligne au salon toutes les 30 min
            d = _lire(); d["non_mesures"] = {"date": _iso(maintenant), "prenoms": non_mes}; _ecrire(d)
        elif not appliquer and illisible:                               # 11/10 : illisible ≠ tout le monde non mesuré
            bilan.append("⚠️ Mesure du scan illisible à ce passage : personne n'est appelé ni sorti, repris 30 min plus tard")
        elif not appliquer and non_mes:
            bilan.append(f"⏸️ {len(non_mes)} non mesuré(s), le scan ne lit pas leurs comptes : pas d'appel ({', '.join(non_mes[:15])})")
        if lents and appliquer:
            appeles = await lancer_appel([(s, m) for s, m, _ in lents], f"inactif depuis {INACTIF_JOURS} j ou plus", maintenant)
            bilan += [f"📢 {p} : inactif, appelé (réponse attendue sous {HEURES} h)" for p in appeles]
        elif lents:
            bilan += [f"· {_deps['prenom_de'](m) if _deps.get('prenom_de') else m.id} : inactif depuis {j} j → serait appelé" for _, m, j in lents]
    # 4. 11/10 (rejeu de L9a) : une mesure illisible qui dure suspend l'appel ; Gaëtan le sait (avant : 3 jours sans une ligne)
    if appliquer and scan_lu:
        bilan += _suivi_illisible(sans_reel is None or mesures is None, maintenant)
    return bilan


def _suivi_illisible(illisible: bool, maintenant) -> list:
    """11/10 (rejeu de L9a) : la mesure du scan est illisible (classeur ou scan en panne) depuis ILLISIBLE_ALERTE_H heures d'affilée
    → une ligne ⚠️ au salon admin, puis une par 24 h tant que ça dure ; une ligne ✅ quand elle revient, seulement si un ⚠️ est
    parti. État dans appel.json : {"illisible": {depuis, signale}}. Une panne d'un seul passage ne fait aucun bruit."""
    d = _lire()
    etat = d.get("illisible") or {}
    if not illisible:
        if not etat:
            return []
        d.pop("illisible", None); _ecrire(d)
        return (["✅ Mesure du scan relue : l'appel de présence reprend, les appels échus sont jugés à partir de ce passage"]
                if etat.get("signale") else [])
    depuis = _dt(etat.get("depuis"))
    if depuis is None:
        d["illisible"] = {"depuis": _iso(maintenant)}; _ecrire(d)
        return []
    signale = _dt(etat.get("signale"))
    if maintenant - depuis < timedelta(hours=ILLISIBLE_ALERTE_H) or (
            signale is not None and maintenant - signale < timedelta(hours=24)):
        return []
    etat["signale"] = _iso(maintenant); d["illisible"] = etat; _ecrire(d)
    echus = len(a_sortir(d, maintenant))
    heures = int((maintenant - depuis).total_seconds() // 3600)
    return [f"⚠️ Appel de présence suspendu : la mesure du scan est illisible depuis {heures} h (classeur ou scan en panne). "
            "Personne n'est appelé ni sorti" + (f", {echus} appel(s) échu(s) en attente" if echus else "")
            + ". Il reprend tout seul dès que la mesure revient."]


async def appel_general(client) -> list:
    """L'appel à tous les clippers signés qui ont un salon perso ; retenu dans l'état pour ne jamais repartir."""
    if not _deps.get("salons_clippers"):
        return []
    cibles = await _deps["salons_clippers"]()
    maintenant = datetime.now(timezone.utc)
    await _completer_activite(cibles)                                   # 05/10 : la dernière activité lue avant l'appel, pour l'état
    appeles = await lancer_appel(cibles, f"appel général du {maintenant.strftime('%d/%m')}", maintenant)
    d = _lire(); d["general"] = {"date": _iso(maintenant), "n": len(appeles)}; _ecrire(d)
    return appeles


def _compte_cree(uid: str, parcours: dict, onboarding: dict):
    """(compte créé ?, date de livraison du compte 1 ou None) d'après la fiche de parcours, sinon la fiche d'onboarding."""
    f = parcours.get(uid) or {}
    if f:
        dates = f.get("dates") or {}
        cree = bool(dates.get("1_fait") or (f.get("profils") or {}).get("1") or int(f.get("etape", 0) or 0) >= 2)
        return cree, _dt(dates.get("1")) or _dt((onboarding.get("clippers", {}).get(uid) or {}).get("date"))
    onb = onboarding.get("clippers", {}).get(uid) or {}
    if not onb.get("comptes"):
        return True, None                                               # rien livré : rien à juger
    cree = any(isinstance(a, dict) and a.get("cree") for a in onb.get("acces") or [])
    return cree, _dt(onb.get("date"))


def _compte_cree_ou_vu(uid: str, parcours: dict, onboarding: dict):
    """05/10, 15 h : la règle « compte 1 créé en 3 jours » est stricte (le silence ne protège plus) ; un compte créé sans appuyer sur
    le bouton ne doit pas faire sortir son clipper → un de ses comptes livrés vu existant par le scan Instagram compte comme créé."""
    cree, livraison = _compte_cree(uid, parcours, onboarding)
    if cree or not _deps.get("compte_vu"):
        return cree, livraison
    handles = (onboarding.get("clippers", {}).get(uid) or {}).get("comptes") or []
    try:
        return bool(handles and _deps["compte_vu"](handles)), livraison
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Scan des comptes de %s illisible : %s", uid, erreur)
        return True, livraison                                          # dans le doute, personne ne sort


async def candidats_purge(cibles: list, maintenant=None) -> list:
    """[(salon, membre, heures depuis la livraison, dernier message iso ou '')] : compte 1 livré depuis PURGE_HEURES ou plus, jamais
    créé (ni bouton, ni profil, ni étape 2), et aucun message du clipper dans son salon depuis PURGE_HEURES. Protégés exclus."""
    maintenant = maintenant or datetime.now(timezone.utc)
    parcours = _deps["parcours_lire"]() if _deps.get("parcours_lire") else {}
    onboarding = _deps["onboarding_lire"]() if _deps.get("onboarding_lire") else {}
    deja = {str(x.get("uid")) for x in _lire().get("purges", [])}      # jamais purgé deux fois (expulsion refusée : Gaëtan tranche)
    out = []
    for salon, membre in cibles:
        uid = str(membre.id)
        prenom = _deps["prenom_de"](membre) if _deps.get("prenom_de") else getattr(membre, "display_name", uid)
        if uid in deja or _protege(uid, prenom):
            continue
        if uid in parcours:
            continue                                                    # 08/10 : une seule règle, sortie_auto (avertissement à 24 h, preuve du scan)
        cree, livraison = _compte_cree_ou_vu(uid, parcours, onboarding)
        if cree or livraison is None or maintenant - livraison < timedelta(hours=PURGE_HEURES):
            continue
        if not _comptes_lus((onboarding.get("clippers", {}).get(uid) or {}).get("comptes") or []):
            continue                                                    # 10/10 (L9a) : non mesuré (scan pas lu) → jamais purgé
        dernier = await derniere_activite_salon(salon, membre, limite=300)
        if PURGE_SILENCE and dernier is not None and maintenant - dernier < timedelta(hours=PURGE_HEURES):
            continue
        out.append((salon, membre, int((maintenant - livraison).total_seconds() // 3600), _iso(dernier) if dernier else ""))
    return out


async def purger(client, appliquer: bool = True, maintenant=None) -> list:
    """La purge : sortie + expulsion immédiate des candidats_purge. Renvoie le bilan (lignes)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if not _deps.get("salons_clippers"):
        return []
    cibles = await _deps["salons_clippers"]()
    bilan = []
    for salon, membre, heures, dernier in await candidats_purge(cibles, maintenant):
        prenom = _deps["prenom_de"](membre) if _deps.get("prenom_de") else membre.display_name
        detail = f"compte 1 livré il y a {heures} h, jamais créé, " + (f"dernier message le {dernier[:10]}" if dernier else "aucun message dans son salon")
        if not appliquer:
            bilan.append(f"· {prenom} : {detail} → sortirait" + (" et expulsé" if KICK else ""))
            continue
        try:
            res = await _deps["sortir"](membre, RAISON_PURGE, pool=True, expulser=KICK)
            d = _lire()
            d.setdefault("purges", []).append({"uid": str(membre.id), "prenom": prenom, "date": _iso(maintenant), "heures": heures,
                                               "expulse": bool(res.get("expulse"))})
            a = d["appels"].get(str(membre.id))
            if a and not a.get("sorti"):
                a["sorti"] = _iso(maintenant)
            _ecrire(d)
            bilan.append(f"🚪 {prenom} : sorti ({detail})" + (" · expulsé" if res.get("expulse") else " · ⚠️ pas expulsé")
                         + (f" · refus : {', '.join(res.get('refus') or [])}" if res.get("refus") else ""))
        except Exception as erreur:                                     # noqa: BLE001
            bilan.append(f"❌ {prenom} : {type(erreur).__name__} {str(erreur)[:100]}")
            journal.warning("Purge de %s : %s", prenom, erreur)
    if appliquer:
        d = _lire(); d["purge_72h"] = {"date": _iso(maintenant), "n": sum(1 for b in bilan if b.startswith("🚪"))}; _ecrire(d)
        journal.info("Purge 72 h : %d sortie(s)", d["purge_72h"]["n"])
    return bilan


def etat_texte(maintenant=None) -> str:
    maintenant = maintenant or datetime.now(timezone.utc)
    d = _lire()
    attente, repondus, sortis, non_mesures, verifications = [], [], [], [], []
    for uid, a in d["appels"].items():
        p = a.get("prenom") or uid
        if a.get("sorti"):
            sortis.append(p)
        elif a.get("repondu"):
            repondus.append(p + ("" if (_deps["parcours_lire"]() if _deps.get("parcours_lire") else {}).get(uid, {}).get("whatsapp") else " (pas de WhatsApp)"))
        elif a.get("non_mesure"):
            non_mesures.append(p)
        elif a.get("verification_humaine"):
            verifications.append(p)
        elif a.get("non_mesure_signale"):                               # 11/10 : échu, jugé dès que le scan lit ses comptes
            attente.append(f"{p} (échu, attend la mesure du scan)")
        else:
            fin = (_dt(a.get("date")) or maintenant) + timedelta(hours=HEURES)
            reste = max(0, int((fin - maintenant).total_seconds() // 3600))
            attente.append(f"{p} ({reste} h)")
    g = d.get("general") or {}
    lignes = ["📢 **Appel de présence** — général : " + (f"{str(g.get('date', ''))[:10]}, {g.get('n', 0)} appelé(s)" if g else "pas encore lancé (`!appel go`)")]
    lignes.append(f"⏳ Sans réponse ({len(attente)}) : " + (", ".join(attente) or "personne"))
    lignes.append(f"✅ Ont répondu ({len(repondus)}) : " + (", ".join(repondus) or "personne"))
    lignes.append(f"🚪 Sortis ({len(sortis)}) : " + (", ".join(sortis) or "personne"))
    lignes.append(f"🛡️ A vérifier sans sortie ({len(verifications)}) : " + (", ".join(verifications) or "personne"))
    if non_mesures:
        lignes.append(f"⏸️ Appels clos sans sortie, {MESURE_ATTENTE} j sans mesure ({len(non_mesures)}) : " + ", ".join(non_mesures))
    nm = d.get("non_mesures") or {}
    if nm.get("prenoms"):
        lignes.append(f"⏸️ Non mesurés au dernier passage ({len(nm['prenoms'])}) : " + ", ".join(nm["prenoms"][:25]))
    ill = _dt((d.get("illisible") or {}).get("depuis"))
    if ill is not None:                                                 # 11/10 (rejeu de L9a) : l'appel est suspendu, on le dit
        lignes.append(f"⚠️ Mesure du scan illisible depuis {max(0, int((maintenant - ill).total_seconds() // 3600))} h : "
                      "personne n'est appelé ni sorti tant qu'elle ne revient pas")
    lignes.append(f"-# Règle : {HEURES} h pour répondre, inactif {INACTIF_JOURS} j = appelé, expulsion {'ON' if (KICK and SORTIE_AUTOMATIQUE) else 'OFF'}. "
                  "Non mesuré (le scan ne lit pas ses comptes) = pas d'appel ; un appel échu attend la mesure, "
                  f"clos sans sortie après {MESURE_ATTENTE} j. "
                  "`!wa @clipper` note WhatsApp, `!appel @clipper` appelle, `!appel go` relance l'appel général.")
    return "\n".join(lignes)


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith(("!appel", "!purge")):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    mots = texte.split()[1:]
    if texte.lower().startswith("!purge"):                              # 05/10 : `!purge` = liste, `!purge go` = sortie + expulsion
        go = mots[:1] == ["go"]
        bilan = await purger(message.client if hasattr(message, "client") else None, appliquer=go)
        if not bilan:
            await message.reply(f"✅ Personne à purger : aucun compte 1 livré depuis {PURGE_HEURES} h sans création ni réponse.")
            return True
        await message.reply((("🚪 **Purge faite**\n" if go else f"🔎 **Purge {PURGE_HEURES} h : ce que `!purge go` ferait**\n") + "\n".join(bilan))[:1990])
        return True
    if message.mentions:
        m = message.mentions[0]
        salon = _deps["salon_perso"](str(m.id)) if _deps.get("salon_perso") else None
        if salon is None:
            await message.reply(f"{m.display_name} n'a pas de salon perso.")
            return True
        appeles = await lancer_appel([(salon, m)], f"appel de {getattr(message.author, 'display_name', 'staff')}")
        await message.reply(f"📢 Appel posté à {', '.join(appeles)}." if appeles else f"{m.display_name} a déjà un appel en cours (ou est protégé).")
        return True
    if mots[:1] == ["go"]:
        appeles = await appel_general(message.client if hasattr(message, "client") else None)
        await message.reply(f"📢 Appel général posté à {len(appeles)} clipper(s)" + (f" : {', '.join(appeles)}" if appeles else "") + ".")
        return True
    if mots[:1] in (["passe"], ["test"]):
        bilan = await executer(None, appliquer=False)
        await message.reply(("🔎 **Ce que le prochain passage ferait**\n" + "\n".join(bilan))[:1990] if bilan else "Rien à faire au prochain passage.")
        return True
    await message.reply(etat_texte()[:1990])
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Appel de présence éteint (APPEL=0)")
        return
    journal.info("Appel de présence actif : %d h pour répondre, inactif %d j = appelé, expulsion %s", HEURES, INACTIF_JOURS, "ON" if (KICK and SORTIE_AUTOMATIQUE) else "OFF")
    await asyncio.sleep(90)                                             # le reste du démarrage d'abord (salons, registre)
    try:
        if GENERAL and not _lire().get("general"):
            appeles = await appel_general(client)
            canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
            if canal is not None:
                await canal.send(f"📢 **Appel de présence général** posté dans {len(appeles)} salon(s) perso. Sans réponse sous {HEURES} h : sortie"
                                 + (" et expulsion" if KICK else "") + ". `!appel` pour suivre, `!wa @clipper` quand il est venu sur WhatsApp.")
    except Exception as erreur:                                         # noqa: BLE001
        journal.warning("Appel général : %s", erreur)
    while not client.is_closed():
        try:                                                            # 05/10, 15 h : la purge à chaque passage, plus une seule fois
            if PURGE:
                bilan_p = await purger(client, appliquer=True)
                canal = await _deps["canal_admin"]() if _deps.get("canal_admin") else None
                if bilan_p and canal is not None:
                    await canal.send((f"🚪 **Purge** ({RAISON_PURGE}) : {sum(1 for b in bilan_p if b.startswith('🚪'))} sortie(s)\n"
                                      + "\n".join(bilan_p))[:1990])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Purge : %s", erreur)
        try:
            bilan = await executer(client, appliquer=True)
            direct, plus_tard = trier_bilan(bilan)
            if plus_tard:
                garder_pour_digest(plus_tard)
            if direct and _deps.get("canal_admin"):
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await canal.send(("📢 **Appel de présence**\n" + "\n".join(direct))[:1990])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Boucle de l'appel : %s", erreur)
        await asyncio.sleep(1800)


# ------------------------------------------------------------------ 11/10 : ce qui n'attend aucun geste va au digest du matin
# Lot W (Gaëtan : « Admin : un seul digest à 9 h. En direct, uniquement ce qui demande un geste de ta part ») : les lignes ⏸️ (non
# mesuré), ✅ (mesure revenue), 🔇 (muet mais actif) et 📢 (appelé) attendent le point du matin (bot_discord.boucle_rappels) ; restent
# en direct 🚪 (sortie, expulsion refusée), 📲 (WhatsApp à ajouter), ⚠️ (appel suspendu) et ❌ (erreur). DIGEST=0 : tout en direct.
DIGEST = os.environ.get("DIGEST", "1").strip() != "0"
EN_DIRECT = ("🚪", "📲", "⚠️", "❌")
DIGEST_MAX = 60                                                         # lignes gardées au plus (les plus récentes)


def trier_bilan(bilan: list) -> tuple:
    """([lignes en direct], [lignes pour le digest]) d'un bilan de passage. DIGEST=0 : tout en direct."""
    if not DIGEST:
        return list(bilan or []), []
    direct = [l for l in bilan or [] if str(l).startswith(EN_DIRECT)]
    return direct, [l for l in bilan or [] if not str(l).startswith(EN_DIRECT)]


def garder_pour_digest(lignes: list) -> None:
    """Ajoute des lignes au bloc « appel de présence » du prochain digest (appel.json, clé « digest »)."""
    if not lignes:
        return
    d = _lire()
    d["digest"] = (list(d.get("digest") or []) + [str(l)[:300] for l in lignes])[-DIGEST_MAX:]
    _ecrire(d)


def bilan_pour_digest() -> list:
    """Les lignes gardées pour le digest du matin ; lecture seule (oublier_digest(n) une fois le digest posté)."""
    if not _deps:
        return []
    return [str(l) for l in (_lire().get("digest") or [])]


def oublier_digest(n: int) -> None:
    """Le digest est parti avec les `n` premières lignes : elles sont oubliées (une ligne arrivée entre-temps reste)."""
    if not _deps or n <= 0:
        return
    d = _lire()
    d["digest"] = list(d.get("digest") or [])[int(n):]
    _ecrire(d)
