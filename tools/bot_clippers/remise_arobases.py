"""Remise de tous les @ restants aux clippers en route (30/10/2026, 9 h 36).

Gaëtan : « Pour tous ceux qui n'ont pas encore terminé la création de leur compte, vérifie à la main s'ils ont bien créé leur compte
ou pas, c'est hyper important. Et ceux qui ne l'ont pas créé, envoie-leur leur arobase dans leur salon privé sur Discord… S'il y a un
clipper qui est ancien, qui a un compte sur trois, tu lui envoies ses deux comptes restants… l'arobas qui est bien disponible, tu
fais attention, directement dans leur salle personnelle. »

Pour chaque clipper en route (fiche du parcours, encore sur le serveur ; ni staff, ni identités multiples, ni sorti), comptes 1 à 3 :
1. créé d'après le bot (étape fermée, accès « cree ») ou d'après le LOG (état autre que « à créer ») : rien ;
2. sinon son @ est examiné sur Instagram (arobase_libre.examen, profil compris) :
   - libre : pas créé. Il est donné (redonné s'il l'avait déjà). Un @ libre est aussi cherché sous les
     suggestions d'Instagram (instagram_rapidapi.variantes_instagram) : un compte tout neuf avec une preuve qu'il est à nous = créé
     sous ce nom, signalé, rien envoyé ;
   - pris : preuve que c'est le sien (bio du bot, prénom de la créatrice, lien) → créé ; compte tout neuf et @ déjà donné (ou vu
     libre par le bot avant) → créé ; @ déjà donné, compte installé sans preuve → à trancher (jamais un @ qu'il a en main changé
     d'office) ; compte neuf jamais donné → à trancher, rien envoyé ; sinon pris par un inconnu → variante
     libre (arobase_libre.variantes : points ↔ tirets bas, « xo » à la fin) écrite dans la même ligne du LOG (parcours.renommer),
     puis donnée ;
   - doute (API muette, quota) : rien, revu à la remise suivante.
3. Un seul message par clipper, dans son salon perso : ses @ à créer, dans l'ordre, chacun avec sa date (un compte toutes les 48 h
   après le dernier créé). Chaque @ donné est noté dans sa fiche (« donnes ») : la vérification de l'étape ne le remplacera jamais
   (il peut l'avoir créé entre-temps).

Les étapes du parcours ne bougent pas : le message de chaque compte arrive toujours à son heure, avec son bouton « ✅ Compte créé ».
Deux modes : aperçu (rien envoyé, rien écrit dans le LOG ni dans les fiches) et envoi. Rapport dans l'onglet « Remise des @ » du
tableur App clippers · usage et au salon admin. Déclenchement : `remise_arobases.json` (dépôt, une fois par id) ou
`!remise-arobases` (staff ; `go` pour envoyer)."""
import asyncio
import json
import logging
import os
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

journal = logging.getLogger("remise_arobases")

ONGLET = "Remise des @"
ENTETE = ["Clipper", "Créatrice", "Compte", "@", "Créé (bot)", "LOG", "Instagram", "Abonnés", "Publications", "Nom / bio",
          "Verdict", "Action", "@ donné", "Mode", "Le"]
FICHIER = Path(__file__).with_name("remise_arobases.json")
DELAI_DEMARRAGE_S = int(os.environ.get("REMISE_AROBASES_DELAI_S", "150") or 150)   # le démarrage lit beaucoup le classeur
SUGGESTIONS_MAX = 5                                                     # suggestions d'Instagram lues pour un @ donné et libre
_deps: dict = {}
_verrou = asyncio.Lock()

# verdicts
CREE, CREE_SOUS, PAS_CREE, A_TRANCHER, PRIS_INCONNU, DOUTE, SANS_LIGNE = (
    "créé", "créé sous une suggestion d'Instagram", "pas créé", "à trancher", "pris par un inconnu", "pas lu", "pas de ligne")
# 31/10 (Esperance : sa fiche portait @lasoir_, absent du LOG, quand elle avait créé @lasoir_c ; l'aperçu proposait de lui « donner »
# @lasoir_) : un @ de la fiche sans ligne dans le LOG n'est jamais donné (Gaëtan, 30/10 : les @ envoyés sont ceux du sheet)
HORS_LOG = "à trancher : @ absent du LOG"
# actions
RIEN, DONNER, VARIANTE = "rien", "donner", "variante"


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, DONNEES, notifier (coroutine texte, guild)."""
    _deps.update(deps)


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def cree_selon_log(etat) -> bool:
    """Pur : la ligne du LOG dit que le compte existe (GOOD, BAN, appel, privé…), pas « à créer » ni vide."""
    e = _n(etat)
    return bool(e) and e not in ("a creer", "a  creer")


def decider(cree: bool, ex: dict, donne: bool, vu_libre: bool) -> tuple:
    """Pur : (verdict, action) d'un compte. `ex` : arobase_libre.examen ; `donne` : le @ a déjà été remis au clipper ;
    `vu_libre` : le bot l'a déjà vu libre (s'il existe ensuite, c'est le clipper qui l'a créé)."""
    import arobase_libre as a
    if cree:
        return CREE, RIEN
    v = (ex or {}).get("verdict")
    if v == a.LIBRE:
        return PAS_CREE, DONNER
    if v != a.PRIS:
        return DOUTE, RIEN
    if ex.get("a_nous"):
        return CREE, RIEN
    if donne and (vu_libre or ex.get("neuf")):
        return CREE, RIEN
    if donne:
        return A_TRANCHER, RIEN                                         # jamais un @ déjà dans ses mains changé d'office
    if ex.get("neuf") or ex.get("profil_lu") is False:
        return A_TRANCHER, RIEN                                         # jamais un @ remplacé sur un profil illisible
    return PRIS_INCONNU, VARIANTE


def echeances(base, nombre: int, maintenant: datetime, heures: int = 48) -> list:
    """Pur : la date de chaque compte à créer, dans l'ordre : le premier 48 h après le dernier compte créé (`base`, None si aucun),
    jamais avant maintenant ; les suivants 48 h après le précédent."""
    out, prec = [], base
    for _ in range(max(0, nombre)):
        q = maintenant if prec is None else max(maintenant, prec + timedelta(hours=heures))
        out.append(q)
        prec = q
    return out


def _quand(q: datetime, maintenant: datetime) -> str:
    if q <= maintenant + timedelta(minutes=30):
        return "aujourd'hui"
    from zoneinfo import ZoneInfo
    d = q.astimezone(ZoneInfo("Europe/Paris"))
    return "à partir du " + d.strftime("%d/%m à ") + f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "") + " (heure de Paris)"


def message(mention: str, items: list, maintenant: datetime) -> str:
    """Pur : le message du salon perso. items = [(n, handle, échéance, privé)], dans l'ordre de création."""
    lignes = [f"{mention} 📋 **Tes comptes Instagram à créer**", "",
              "La formation a changé : tu crées toi-même tes comptes, avec l'@ que je te donne. Chaque @ est vérifié : il est libre."]
    for n, h, q, prive in items:
        lignes += ["", f"**Compte {n} · {'privé' if prive else 'croissance'}** · {_quand(q, maintenant)}", f"```\n{h}\n```"]
    lignes += ["", "Pour chaque compte : ton e-mail et ton mot de passe. Un e-mail différent à chaque fois.",
               "", "Le code d'Instagram arrive sur ton e-mail.",
               "", "Un compte toutes les 48 h, dans l'ordre. Pas plus vite : c'est comme ça qu'on évite les bans.",
               "", "Un @ pas disponible sur Instagram ? Change le point en tiret du bas ou ajoute xo à la fin. "
               "Puis écris ici ton @ exact."]
    if any(p for _, _, _, p in items):
        lignes += ["", "Le compte privé : passe-le en privé dès sa création. Il ne publie jamais."]
    return "\n".join(lignes)


def _ligne(prenom, creatrice, n, h, cree_bot, etat, ex, verdict, action, donne_h, mode, maintenant) -> list:
    ex = ex or {}
    ig = {"libre": "libre", "pris": "existe", "inconnu": "pas lu"}.get(ex.get("verdict"), "")
    nom_bio = " · ".join(x for x in (ex.get("nom"), ex.get("bio")) if x)[:160]
    return [prenom, creatrice, str(n), h or "", "oui" if cree_bot else "", str(etat or ""), ig,
            "" if ex.get("abonnes") is None else str(ex["abonnes"]), "" if ex.get("publications") is None else str(ex["publications"]),
            nom_bio, verdict, action, donne_h or "", mode, maintenant.isoformat(timespec="minutes")]


async def _suggestion_creee(h: str, creatrice: str) -> str:
    """La suggestion d'Instagram (variantes_instagram) sous laquelle le clipper a créé ce compte : exactement un compte neuf avec une
    preuve qu'il est à nous ; '' sinon."""
    import arobase_libre as a
    import instagram_rapidapi as ig
    trouves = []
    for v in ig.variantes_instagram(h)[:SUGGESTIONS_MAX]:
        ex = await a.examen(v, creatrice)
        if ex.get("verdict") == a.PRIS and ex.get("neuf"):
            trouves.append((v, ex.get("a_nous")))
    return trouves[0][0] if len(trouves) == 1 and trouves[0][1] else ""


async def remise(client, envoyer: bool = False, seulement: set = None) -> dict:
    """La remise (aperçu si `envoyer` est faux). Renvoie {lignes, messages, clippers, bilan}. Jamais deux en même temps."""
    async with _verrou:
        return await _remise(client, envoyer, seulement)


async def _remise(client, envoyer: bool, seulement: set) -> dict:
    import arobase_libre as a
    import onboarding
    import parcours
    maintenant = datetime.now(timezone.utc)
    mode = "envoi" if envoyer else "aperçu"
    guild = client.guilds[0] if getattr(client, "guilds", None) else None
    comptes_log = await onboarding.lire_comptes()
    par_handle = {onboarding.normaliser_handle(c.get("handle")).lower(): c for c in comptes_log if c.get("handle")}
    dans_le_log = set(par_handle)
    try:
        import identites_clipping
        multi = set(identites_clipping._uids_multi())
    except Exception:                                                   # noqa: BLE001
        multi = set()
    sortis = {u for u, f in (onboarding._lire_etat().get("clippers") or {}).items() if isinstance(f, dict) and f.get("sorti")}
    est_staff = parcours._deps.get("est_staff") or (lambda m: False)
    lignes, bilan, envoyes, clippers = [], [], 0, 0
    for uid, f in sorted((parcours._lire() or {}).items(), key=lambda x: str((x[1] or {}).get("prenom") or "") if isinstance(x[1], dict) else ""):
        if not isinstance(f, dict) or uid in multi or uid in sortis or (seulement and uid not in seulement):
            continue
        membre = guild.get_member(int(uid)) if guild is not None and str(uid).isdigit() else None
        if membre is None or getattr(membre, "bot", False) or est_staff(membre):
            continue
        prenom = f.get("prenom") or parcours._prenom(membre)
        creatrice = f.get("creatrice") or (parcours._onb(uid) or {}).get("creatrice") or ""
        handles = parcours._comptes_ordonnes(uid, fiche_p=f)
        if all(parcours._cree(f, n) for n in (1, 2, 3)):
            continue
        salon = guild.get_channel(int(f["salon_id"])) if str(f.get("salon_id") or "").isdigit() else None
        a_donner, crees_dates, lignes_c = [], [], []
        for n in (1, 2, 3):
            prive = n == parcours.n_prive(f)
            h = handles[n - 1] if len(handles) >= n else ""
            if not h and envoyer and salon is not None:
                if await parcours._ligne_du_compte(salon, membre, uid, n):
                    handles = parcours._comptes_ordonnes(uid, fiche_p=parcours._lire().get(uid) or f)
                    h = handles[n - 1] if len(handles) >= n else ""
            if not h:
                lignes_c.append(_ligne(prenom, creatrice, n, "", False, "", {}, SANS_LIGNE, RIEN, "", mode, maintenant))
                continue
            cree_bot = parcours._cree(f, n) or parcours.compte_deja_cree(uid, h)
            etat = (par_handle.get(h.lower()) or {}).get("etat", "")
            if not cree_bot and onboarding.normaliser_handle(h).lower() not in par_handle:
                lignes_c.append(_ligne(prenom, creatrice, n, h, False, "", {}, HORS_LOG, RIEN, "", mode, maintenant))
                continue
            if cree_bot or cree_selon_log(etat):
                dc = parcours._date_creation(f, n)
                if dc is not None:
                    crees_dates.append(dc)
                lignes_c.append(_ligne(prenom, creatrice, n, h, cree_bot, etat, {}, CREE, RIEN, "", mode, maintenant))
                continue
            donne = bool((f.get("messages") or {}).get(str(n))) or parcours.arobase_donne(f, n, h)
            ex = await a.examen(h, creatrice)
            verdict, action = decider(False, ex, donne, a.vu_libre(h))
            if verdict == PAS_CREE:                                     # il voit ses @ dans son app : il a pu le créer
                sous = await _suggestion_creee(h, creatrice)
                if sous:
                    verdict, action = f"{CREE_SOUS} : @{sous}", RIEN
            final = h
            if action == VARIANTE:
                v = await a.variante_libre(h, exclus=dans_le_log)
                if not v:
                    verdict, action = f"{PRIS_INCONNU}, aucune variante libre", RIEN
                elif envoyer:
                    _, raison = await parcours.renommer(uid, n, v)
                    if raison:
                        verdict, action = f"{PRIS_INCONNU}, variante @{v} refusée ({raison})", RIEN
                    else:
                        final = v
                        dans_le_log.add(v)
                else:
                    final = v
                    dans_le_log.add(v)
            if action in (DONNER, VARIANTE):
                a_donner.append((n, final, prive))
            lignes_c.append(_ligne(prenom, creatrice, n, h, False, etat, ex, verdict, action,
                                   final if action in (DONNER, VARIANTE) else "", mode, maintenant))
        if any(l[10] != CREE for l in lignes_c):                        # un clipper à 3 comptes créés n'encombre pas le rapport
            lignes += lignes_c
        if not a_donner:
            continue
        clippers += 1
        quand = echeances(max(crees_dates) if crees_dates else None, len(a_donner), maintenant, parcours.ATTENTE_SIMPLE_H)
        items = [(n, h, q, p) for (n, h, p), q in zip(a_donner, quand)]
        bilan.append(f"• {prenom} ({creatrice}) : " + ", ".join(f"compte {n} `{h}`" for n, h, _, _ in items))
        if not envoyer:
            continue
        if salon is None:
            bilan[-1] += " ⚠️ pas de salon perso : rien envoyé"
            continue
        try:
            await salon.send(message(membre.mention, items, maintenant)[:1990])
        except Exception as erreur:                                     # noqa: BLE001 — le suivant passe quand même
            bilan[-1] += f" ⚠️ envoi refusé ({type(erreur).__name__})"
            continue
        envoyes += 1
        d = parcours._lire()
        if uid in d:
            for n, h, q, _ in items:
                d[uid].setdefault("donnes", {})[str(n)] = {"handle": h, "le": maintenant.isoformat(timespec="seconds"),
                                                          "a_partir_de": q.isoformat(timespec="seconds")}
            parcours._ecrire(d)
    await _rapport(lignes)
    return {"lignes": lignes, "messages": envoyes, "clippers": clippers, "bilan": bilan, "mode": mode}


async def _rapport(lignes: list) -> None:
    try:
        import paie_clics
        import pilotage
        classeur = await paie_clics._classeur_usage()
        if classeur:
            await pilotage._ecrire(classeur, ONGLET, ENTETE, lignes)
    except Exception as erreur:                                         # noqa: BLE001 — le rapport au salon admin reste
        journal.warning("Onglet %s non écrit : %s", ONGLET, str(erreur)[:160])


def resume(res: dict) -> str:
    """Pur : le bilan pour le salon admin (le détail est dans l'onglet « Remise des @ »)."""
    lignes = res.get("lignes") or []
    compte = {}
    for l in lignes:
        cle = l[10].split(" :")[0].split(",")[0]
        compte[cle] = compte.get(cle, 0) + 1
    tete = (f"📋 **Remise des @ ({res.get('mode')})** : {res.get('clippers', 0)} clipper(s) à qui donner des @"
            + (f", {res.get('messages', 0)} message(s) envoyé(s)" if res.get("mode") == "envoi" else ", rien envoyé"))
    detail = " · ".join(f"{k} : {v}" for k, v in sorted(compte.items()))
    return "\n".join([tete, detail, *res.get("bilan", []), f"Détail compte par compte : onglet « {ONGLET} » (App clippers · usage)."])


async def _dire(texte: str, client) -> None:
    if not _deps.get("notifier"):
        return
    for i in range(0, len(texte), 1900):
        try:
            await _deps["notifier"](texte[i:i + 1900], client.guilds[0] if client.guilds else None)
        except Exception:                                               # noqa: BLE001
            return


async def demarrage(client) -> None:
    """`remise_arobases.json` = {"id", "mode": "apercu" | "envoi"} : jouée une fois par id, DELAI_DEMARRAGE_S après le démarrage."""
    await client.wait_until_ready()
    if not FICHIER.exists() or not _deps.get("DONNEES"):
        return
    try:
        e = json.loads(FICHIER.read_text(encoding="utf-8"))
    except ValueError as erreur:
        journal.warning("remise_arobases.json illisible : %s", erreur)
        return
    ident = str((e or {}).get("id") or "") if isinstance(e, dict) else ""
    trace = _deps["DONNEES"] / "remise_arobases_faites.json"
    faits = _deps["lire_json"](trace, {})
    if not ident or ident in faits:
        return
    await asyncio.sleep(DELAI_DEMARRAGE_S)
    try:
        res = await remise(client, envoyer=str(e.get("mode") or "").lower() == "envoi")
    except Exception as erreur:                                         # noqa: BLE001 — jamais tuer le bot ; rejouée au démarrage suivant
        journal.exception("Remise des @")
        await _dire(f"⚠️ Remise des @ ({ident}) : {type(erreur).__name__} {str(erreur)[:150]}, rejouée au prochain démarrage", client)
        return
    faits[ident] = {"le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": res["mode"],
                    "messages": res["messages"], "clippers": res["clippers"]}
    _deps["ecrire_json"](trace, faits)
    await _dire(resume(res), client)


async def commande(message, texte: str, client) -> bool:
    """`!remise-arobases` (aperçu) · `!remise-arobases go` (envoi) · `@clipper` pour un seul. Staff seulement (appelant)."""
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!remise-arobases", "!remise-arobase"):
        return False
    envoyer = any(m.lower() == "go" for m in mots[1:])
    seulement = {str(m.id) for m in getattr(message, "mentions", []) or []} or None
    await message.reply(f"⏳ Remise des @ ({'envoi' if envoyer else 'aperçu'}) en cours : chaque @ est vérifié sur Instagram, "
                        "ça prend quelques minutes.")
    try:
        res = await remise(client, envoyer=envoyer, seulement=seulement)
    except Exception as erreur:                                         # noqa: BLE001
        await message.reply(f"❌ {type(erreur).__name__} {str(erreur)[:150]}")
        return True
    texte_r = resume(res)
    for i in range(0, len(texte_r), 1900):
        await message.channel.send(texte_r[i:i + 1900])
    return True
