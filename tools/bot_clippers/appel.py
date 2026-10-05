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
`!appel` (staff) : l'état ; `!appel go` : l'appel général ; `!appel @clipper` : un appel individuel ; APPEL=0 éteint."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord

journal = logging.getLogger("appel")
ACTIF = os.environ.get("APPEL", "1").strip() != "0"
HEURES = int(os.environ.get("APPEL_HEURES", "48") or 48)
INACTIF_JOURS = int(os.environ.get("APPEL_INACTIF_JOURS", "4") or 4)
KICK = os.environ.get("APPEL_KICK", "1").strip() != "0"
GENERAL = os.environ.get("APPEL_GENERAL", "1").strip() != "0"
# 05/10 (Gaëtan : « vire directement les clippeurs qui n'ont pas créé de compte dans les 72 h et n'ont pas répondu sur leur salon
# privé ») : la purge, une fois au démarrage (PURGE_72H=1), puis `!purge` / `!purge go`.
PURGE = os.environ.get("PURGE_72H", "1").strip() != "0"
PURGE_HEURES = int(os.environ.get("PURGE_HEURES", "72") or 72)
# 05/10, 15 h (Gaëtan : « premier compte IG créé en 3 jours », « applique à tout le monde ») : le compte 1 non créé suffit, qu'il ait
# parlé ou non dans son salon (PURGE_SILENCE=1 pour revenir à « et pas un mot ») ; la purge tourne à chaque passage (30 min).
PURGE_SILENCE = os.environ.get("PURGE_SILENCE", "0").strip() == "1"
RAISON_PURGE = (f"{PURGE_HEURES} h sans créer ton compte 1 et sans un mot dans ton salon" if PURGE_SILENCE
                else f"compte 1 Instagram non créé {PURGE_HEURES // 24} jours après l'avoir reçu")
_deps = {}

TEXTE_APPEL = ("📢 **{prenom}, réponds ici dans les {heures} h.** Un mot suffit : « présent ».\n\n"
               "Et écris à Gaëtan sur WhatsApp (bouton ci-dessous, le message est déjà écrit) : c'est là que l'équipe te parle.\n\n"
               "Sans réponse ici dans {heures} h, tu sors du serveur et ta place va au suivant.")
TEXTE_RELANCE_WA = ("📲 {prenom}, merci pour ta réponse. Il manque WhatsApp : écris à Gaëtan maintenant (bouton ci-dessous), "
                    "il ouvre ton groupe. C'est là que tout se passe.")
RAISON = f"sans réponse à l'appel depuis {HEURES} h"


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
    if a and not a.get("repondu") and not a.get("sorti") and (_dt(a.get("date")) or quand) <= quand:
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


def _vue(uid: str):
    url = _deps["lien_whatsapp"](uid) if _deps.get("lien_whatsapp") else ""
    if not url:
        return None
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="📲 Écrire à Gaëtan sur WhatsApp", style=discord.ButtonStyle.link, url=url))
    return vue


# ------------------------------------------------------------------ l'appel
async def lancer_appel(cibles: list, motif: str, maintenant=None) -> list:
    """Poste l'appel dans le salon perso de chaque (salon, membre) sans appel en cours. Renvoie les prénoms appelés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    d = _lire()
    appeles = []
    for salon, membre in cibles:
        uid = str(membre.id)
        prenom = _deps["prenom_de"](membre) if _deps.get("prenom_de") else getattr(membre, "display_name", uid)
        a = d["appels"].get(uid)
        if a and not a.get("sorti") and not a.get("repondu") and (_dt(a.get("date")) or maintenant) + timedelta(hours=HEURES) > maintenant:
            continue                                                    # un appel court déjà
        if _protege(uid, prenom):
            continue
        try:
            vue = _vue(uid)
            texte = f"{membre.mention} " + TEXTE_APPEL.format(prenom=prenom, heures=HEURES)
            msg = await (salon.send(texte, view=vue) if vue is not None else salon.send(texte))
        except (discord.Forbidden, discord.HTTPException) as erreur:
            journal.warning("Appel de %s : %s", prenom, erreur)
            continue
        d["appels"][uid] = {"date": _iso(maintenant), "salon_id": str(salon.id), "message_id": str(getattr(msg, "id", "")),
                            "motif": motif, "prenom": prenom, "repondu": None, "relance_wa": None, "sorti": None}
        appeles.append(prenom)
        await asyncio.sleep(0.5)
    _ecrire(d)
    if appeles:
        journal.info("Appel (%s) posté à %d clipper(s)", motif, len(appeles))
    return appeles


def a_sortir(d: dict, maintenant=None) -> list:
    """[(uid, appel)] : appel sans réponse depuis HEURES heures ou plus."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for uid, a in d.get("appels", {}).items():
        if a.get("repondu") or a.get("sorti"):
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
        if not a.get("repondu") or a.get("sorti") or a.get("relance_wa"):
            continue
        if (parcours.get(uid) or {}).get("whatsapp"):
            continue
        rep = _dt(a.get("repondu"))
        if rep is not None and maintenant >= rep + timedelta(hours=24):
            out.append((uid, a))
    return out


def inactifs(activite: dict, sans_reel: dict, cibles: list, appels: dict, maintenant=None, jours: int = None) -> list:
    """[(salon, membre, jours d'inactivité)] : signés sans appel en cours, dont la dernière activité connue (message, bouton)
    ET le dernier Reel vu remontent à `jours` jours ou plus. Sans aucune activité connue : considéré inactif (l'historique a été lu)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jours = INACTIF_JOURS if jours is None else jours
    out = []
    for salon, membre in cibles:
        uid = str(membre.id)
        a = appels.get(uid)
        if a and (a.get("sorti") or not a.get("repondu") or (_dt(a.get("date")) or maintenant) + timedelta(days=jours) > maintenant):
            continue                                                    # déjà sorti (jamais rappelé tout seul), appel en cours, ou répondu récemment
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
    # 1. sans réponse → sortie + expulsion
    for uid, a in a_sortir(d, maintenant):
        prenom = a.get("prenom") or uid
        if not appliquer:
            bilan.append(f"· {prenom} : sans réponse depuis {HEURES} h → sortirait" + (" et expulsé" if KICK else ""))
            continue
        m = _deps["membre_par_id"](uid) if _deps.get("membre_par_id") else None
        d = _lire()
        if m is None:                                                   # déjà parti du serveur : on solde
            d["appels"][uid]["sorti"] = _iso(maintenant); _ecrire(d)
            bilan.append(f"· {prenom} : plus sur le serveur, appel clos")
            continue
        try:
            res = await _deps["sortir"](m, RAISON, pool=True, expulser=KICK)
            d = _lire(); d["appels"][uid]["sorti"] = _iso(maintenant); d["appels"][uid]["expulse"] = bool(res.get("expulse")); _ecrire(d)
            bilan.append(f"🚪 {prenom} : sorti ({RAISON})" + (" · expulsé" if res.get("expulse") else " · ⚠️ pas expulsé")
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
        bilan.append(f"📲 {prenom} : a répondu, pas de WhatsApp → relancé (`!wa @{prenom}` quand c'est fait, `!sortie` sinon)")
    # 3. inactifs → appel individuel
    if _deps.get("salons_clippers"):
        try:
            cibles = await _deps["salons_clippers"]()
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Salons des clippers illisibles : %s", erreur)
            cibles = []
        try:
            sans_reel = await _deps["jours_sans_reel"]() if _deps.get("jours_sans_reel") else {}
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Jours sans Reel illisibles : %s", erreur)
            sans_reel = {}
        d = _lire()
        for salon, membre in cibles:                                    # dernière activité inconnue → lue une fois dans l'historique
            uid = str(membre.id)
            if uid not in d["activite"]:
                quand = await derniere_activite_salon(salon, membre)
                d["activite"][uid] = _iso(quand) if quand else ""
        _ecrire(d)
        lents = inactifs(d["activite"], sans_reel, cibles, d["appels"], maintenant)
        lents = [(s, m, j) for s, m, j in lents if not _protege(str(m.id), _deps["prenom_de"](m) if _deps.get("prenom_de") else "")]
        if lents and appliquer:
            appeles = await lancer_appel([(s, m) for s, m, _ in lents], f"inactif depuis {INACTIF_JOURS} j ou plus", maintenant)
            bilan += [f"📢 {p} : inactif, appelé (réponse attendue sous {HEURES} h)" for p in appeles]
        elif lents:
            bilan += [f"· {_deps['prenom_de'](m) if _deps.get('prenom_de') else m.id} : inactif depuis {j} j → serait appelé" for _, m, j in lents]
    return bilan


async def appel_general(client) -> list:
    """L'appel à tous les clippers signés qui ont un salon perso ; retenu dans l'état pour ne jamais repartir."""
    if not _deps.get("salons_clippers"):
        return []
    cibles = await _deps["salons_clippers"]()
    maintenant = datetime.now(timezone.utc)
    d = _lire()
    for salon, membre in cibles:                                        # 05/10 : la dernière activité lue avant l'appel, pour l'état
        uid = str(membre.id)
        if uid not in d["activite"]:
            quand = await derniere_activite_salon(salon, membre)
            d["activite"][uid] = _iso(quand) if quand else ""
    _ecrire(d)
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
        cree, livraison = _compte_cree_ou_vu(uid, parcours, onboarding)
        if cree or livraison is None or maintenant - livraison < timedelta(hours=PURGE_HEURES):
            continue
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
    attente, repondus, sortis = [], [], []
    for uid, a in d["appels"].items():
        p = a.get("prenom") or uid
        if a.get("sorti"):
            sortis.append(p)
        elif a.get("repondu"):
            repondus.append(p + ("" if (_deps["parcours_lire"]() if _deps.get("parcours_lire") else {}).get(uid, {}).get("whatsapp") else " (pas de WhatsApp)"))
        else:
            fin = (_dt(a.get("date")) or maintenant) + timedelta(hours=HEURES)
            reste = max(0, int((fin - maintenant).total_seconds() // 3600))
            attente.append(f"{p} ({reste} h)")
    g = d.get("general") or {}
    lignes = [f"📢 **Appel de présence** — général : " + (f"{str(g.get('date', ''))[:10]}, {g.get('n', 0)} appelé(s)" if g else "pas encore lancé (`!appel go`)")]
    lignes.append(f"⏳ Sans réponse ({len(attente)}) : " + (", ".join(attente) or "personne"))
    lignes.append(f"✅ Ont répondu ({len(repondus)}) : " + (", ".join(repondus) or "personne"))
    lignes.append(f"🚪 Sortis ({len(sortis)}) : " + (", ".join(sortis) or "personne"))
    lignes.append(f"-# Règle : {HEURES} h pour répondre, inactif {INACTIF_JOURS} j = appelé, expulsion {'ON' if KICK else 'OFF'}. "
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
    journal.info("Appel de présence actif : %d h pour répondre, inactif %d j = appelé, expulsion %s", HEURES, INACTIF_JOURS, "ON" if KICK else "OFF")
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
            if bilan and _deps.get("canal_admin"):
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await canal.send(("📢 **Appel de présence**\n" + "\n".join(bilan))[:1990])
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Boucle de l'appel : %s", erreur)
        await asyncio.sleep(1800)
