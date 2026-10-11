"""Les bloqués du matin, avec leur relance WhatsApp en un appui (30/09, Gaëtan : « GO la liste des bloqués chaque matin »,
« GO relances WhatsApp en un appui » ; les clippers répondent plus vite sur WhatsApp que sur Discord).

Chaque matin à BLOQUES_HEURE (11 h Paris, après le scan Instagram), le salon admin reçoit la liste des clippers du roster qui
n'avancent pas, le plus bloqué d'abord :
- compte à créer depuis trop longtemps : étape 1 depuis plus de 2 jours, étape 2 ou 3 depuis plus de 4 jours (48 h
  d'attente normale entre deux comptes, plus 48 h) ;
- plus de Reel depuis BLOQUES_JOURS_SANS_REEL jours (3) une fois les comptes créés.
Pour chacun : prénom, créatrice, où il bloque, et un lien WhatsApp qui ouvre SA conversation avec le message déjà écrit.
Rien ne part tout seul : Gaëtan appuie, relit, envoie (les envois automatiques font bannir un numéro WhatsApp). BLOQUES_MAX
par jour (25). `!bloques` (staff) : la liste tout de suite. BLOQUES=0 éteint.

10/10 (revue du recrutement, lot L9b : « un seul digest admin ») : la liste part DANS le digest du matin (bot_discord.boucle_rappels,
lignes_digest), seulement s'il y a quelqu'un ; la boucle de 11 h est inerte tant que DIGEST=1 (défaut). Plus jamais « personne 🎉 ».
Nouveau cas « compte illisible » : un clipper qui attend son compte suivant (2 ou 3) alors que le compte dont les Reels l'ouvrent
(et qui n'a pas encore ses Reels) est restreint au dernier relevé (series.dernier_releve, lecture seule), ou n'a aucun Reel vu
par le scan (le total du compte, jamais le « de plus » du compte 3) ILLISIBLE_H heures (24) après « ton compte n arrive dès que
je vois… » (attente dite). Avant, il n'était listé nulle part : sortie_auto.silences saute tout clipper qui a un compte
restreint. Lignes : « Léa (compte 1, Chloé) · compte restreint au dernier relevé. `!etape @Léa 2` s'il publie. » ou
« · 0 Reel vu sur ce compte. … ». BLOQUES=0 éteint aussi le bloc du digest."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

journal = logging.getLogger("bloques")
ACTIF = os.environ.get("BLOQUES", "1").strip() != "0"
HEURE = int(os.environ.get("BLOQUES_HEURE", "11") or 11)
MAX_JOUR = int(os.environ.get("BLOQUES_MAX", "25") or 25)
JOURS_SANS_REEL = int(os.environ.get("BLOQUES_JOURS_SANS_REEL", "3") or 3)
# 10/10 (lot L9b) : la liste passe dans le digest du matin ; DIGEST=0 rend sa boucle de 11 h (retour arrière)
DIGEST = os.environ.get("DIGEST", "1").strip() != "0"
ILLISIBLE_H = int(os.environ.get("BLOQUES_ILLISIBLE_H", "24") or 24)   # après l'attente dite, sans un Reel lisible
# jours au-delà desquels une étape de compte bloque. 08/10 (critique de l'audit) : étape 1 dès 1 jour, le jour de
# l'avertissement — à « plus de 2 jours », le clipper était déjà sorti par la règle des 48 h avant d'être jamais listé.
JOURS_ETAPE = {1: 0, 2: 4, 3: 4}
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état), FICHIER_PARCOURS, roster_groupes (-> {créatrice: [prénoms]}),
    membre_par_prenom, tel_de (uid -> numéro), jours_sans_reel (async -> {uid: jours}), canal_admin (async), heure_paris,
    est_staff, normaliser. 10/10 (facultatif) : dernier_releve (clé du compte -> dernier relevé ou None ; sinon
    series.dernier_releve, lu sans rien écrire)."""
    _deps.update(deps)


def lien_whatsapp(tel: str, texte: str) -> str:
    """wa.me/<numéro>?text=… : ouvre la conversation avec le message prêt, rien n'est envoyé sans appui."""
    chiffres = "".join(c for c in str(tel or "") if c.isdigit())
    if len(chiffres) < 8:
        return ""
    return f"https://wa.me/{chiffres}?text={quote(texte)}"


def message(prenom: str, cas: str, n: int, jours: int) -> str:
    """Le message WhatsApp, court, en mots simples."""
    if cas == "compte":
        return (f"Salut {prenom} ! Ton compte {n} t'attend dans ton salon Discord. "
                "Tu bloques où ? Réponds-moi ici, je t'aide 🙂")
    if cas == "whatsapp":                                                # 05/10 : compte 1 créé, il n'a pas encore écrit
        return (f"Salut {prenom} ! Ton compte 1 est créé, bravo. C'est ici qu'on se parle : "
                "réponds-moi un mot, j'ouvre ton groupe 🙂")                    # 10/10 : le groupe, sans nom de manager
    if cas == "restreint":                                               # 10/10 : restreint au dernier relevé
        return (f"Salut {prenom} ! Ton compte {n} a l'air restreint : je ne vois plus ses Reels. "
                "Envoie-moi une capture de ton profil, on regarde ensemble 🙂")
    if cas == "illisible":                                               # 10/10 : aucun Reel vu sur ce compte
        return (f"Salut {prenom} ! Je ne vois encore aucun Reel sur ton compte {n}. "
                "Tu publies bien dessus ? Envoie-moi une capture de ton profil 🙂")
    return (f"Salut {prenom} ! Pas de Reel depuis {jours} jours sur tes comptes. "
            "Tout va bien ? Dis-moi ce qui bloque, on règle ça ensemble 💪")


def _jours_depuis(iso, maintenant) -> int:
    try:
        d = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return -1
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return (maintenant - d).days


def _instant(x):
    """Un horodatage (datetime ou ISO), avec fuseau (UTC s'il n'en a pas) ; None s'il est illisible."""
    try:
        d = x if isinstance(x, datetime) else datetime.fromisoformat(str(x))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def reels_vus_sur(fiche: dict, h: str, parcours_mod=None) -> int:
    """10/10 (vérification du lot L9b) : TOUS les Reels vus par le scan sur le compte h depuis sa création (cumul `reels` de la
    fiche, plus ceux du scan du soir), jamais le compte « de plus » de reels_detail : un compte 1 à 12 Reels, sans nouveau depuis
    la base du compte 3, est lisible."""
    suivi = ((fiche or {}).get("reels") or {}).get(str(h or "").lower()) or {}
    try:
        vus = int(suivi.get("vus", 0) or 0)
    except (TypeError, ValueError):
        vus = 0
    soir = getattr(parcours_mod, "_reels_soir", None) if parcours_mod is not None else None
    if callable(soir):
        try:
            vus += int(soir(fiche or {}, h) or 0)
        except Exception:                                               # noqa: BLE001 — le cumul suffit
            pass
    return vus


def comptes_illisibles(uid, fiche: dict, maintenant=None, dernier_releve=None, parcours_mod=None) -> list:
    """10/10 (lot L9b) : [(compte source, compte attendu, heures d'attente, raison)] d'un clipper qui attend son compte 2 ou 3
    (48 h passées, Reels pas encore là : parcours.attente) alors que le compte dont les Reels l'ouvrent est illisible. Raison
    « restreint » : restreint au dernier relevé (series.dernier_releve, lecture seule). Raison « illisible » : AUCUN Reel vu sur
    ce compte (reels_vus_sur, le total, jamais le « de plus » de reels_detail) ILLISIBLE_H heures après l'attente dite
    (« attente_dite » de la fiche). Une source qui a déjà ses REELS_OUVERTURE Reels n'est jamais listée : ce n'est pas elle qui
    bloque, et `!etape` ne doit pas contourner l'autre. Jamais avant la fin des 48 h : `!etape` ne court-circuite pas la règle.
    Un compte BAN n'y est pas : l'alerte BAN du parcours le dit déjà. Rien n'est écrit."""
    if parcours_mod is None:
        import parcours as parcours_mod                                 # import tardif : parcours importe discord et onboarding
    if dernier_releve is None:
        dernier_releve = _deps.get("dernier_releve")
    if dernier_releve is None:
        import series                                                   # le seul lecteur des séries ; lecture seule ici
        dernier_releve = series.dernier_releve
    maintenant = maintenant or datetime.now(timezone.utc)
    fiche = fiche or {}
    att = parcours_mod.attente(fiche)
    if not att:
        return []
    w, quand = att
    quand = _instant(quand)
    if quand is None or maintenant < quand:
        return []
    comptes = parcours_mod._comptes_ordonnes(uid, fiche_p=fiche)
    comptent = dict(parcours_mod.reels_detail(uid, fiche, w))            # ce qui compte pour l'ouverture (« de plus » compris)
    seuil = int(getattr(parcours_mod, "REELS_OUVERTURE", 4) or 4)
    dite = fiche.get("attente_dite") == w and maintenant - quand >= timedelta(hours=ILLISIBLE_H)
    heures = int((maintenant - quand).total_seconds() // 3600)
    out = []
    for src in parcours_mod.sources_reels(fiche, w):
        h = comptes[src - 1] if 0 < src <= len(comptes) else ""
        if not h or parcours_mod._est_ban(h, fiche):
            continue
        if src in comptent and int(comptent.get(src, 0) or 0) >= seuil:
            continue                                                    # cette source a ses Reels : elle ne bloque pas
        try:
            releve = dernier_releve(h) or {}
        except Exception as erreur:                                     # noqa: BLE001 — séries illisibles : le seul compteur
            journal.info("Bloqués : dernier relevé de %s illisible (%s)", h, erreur)
            releve = {}
        if releve.get("restreint"):
            out.append((src, w, heures, "restreint"))
        elif dite and reels_vus_sur(fiche, h, parcours_mod) <= 0:
            out.append((src, w, heures, "illisible"))
    return out


def liste(parcours: dict, groupes: dict, uid_de, tel_de, sans_reel: dict, maintenant=None, illisibles=None) -> list:
    """[(jours, prénom, créatrice, où il bloque, lien WhatsApp)], le plus bloqué d'abord, MAX_JOUR au plus.
    10/10 : `illisibles` (uid, fiche, maintenant) -> comptes_illisibles ; le cas « compte illisible » passe juste après « compte
    à créer » : « (compte 1, Chloé) · compte restreint au dernier relevé. `!etape @Léa 2` s'il publie. », ou « · 0 Reel vu sur
    ce compte. … » quand le scan n'y a vu aucun Reel."""
    maintenant = maintenant or datetime.now(timezone.utc)
    out = []
    for creatrice, prenoms in (groupes or {}).items():
        for prenom in prenoms or []:
            uid = uid_de(prenom)
            if not uid:
                continue
            fiche = parcours.get(str(uid)) or {}
            n = int(fiche.get("etape", 0) or 0)
            jours = _jours_depuis((fiche.get("dates") or {}).get(str(n)), maintenant) if n in JOURS_ETAPE else -1
            fait1 = (fiche.get("dates") or {}).get("1_fait")
            ill = []
            if illisibles is not None and n in (2, 3) and not (jours > JOURS_ETAPE[n]):
                try:
                    ill = illisibles(str(uid), fiche, maintenant) or []
                except Exception as erreur:                             # noqa: BLE001 — dans le doute, les autres cas
                    journal.warning("Bloqués : comptes illisibles de %s (%s)", prenom, erreur)
            crea = creatrice
            if n in JOURS_ETAPE and jours > JOURS_ETAPE[n]:
                ou, texte = f"compte {n} à créer depuis {jours} j", message(prenom, "compte", n, jours)
            elif ill:
                src, attendu, heures = ill[0][:3]
                raison = ill[0][3] if len(ill[0]) > 3 else "illisible"
                jours, crea = heures // 24, f"compte {src}, {creatrice}"
                # 10/10 (vérification L9b) : « restreint » ne dit pas « 0 Reel » (il peut en avoir de comptés) ; « 0 Reel » seulement
                # quand le scan n'en a vu aucun sur ce compte
                ou = ("compte restreint au dernier relevé" if raison == "restreint" else "0 Reel vu sur ce compte") \
                    + f". `!etape @{prenom} {attendu}` s'il publie."
                texte = message(prenom, raison, src, jours)
            elif fait1 and not fiche.get("whatsapp") and _jours_depuis(fait1, maintenant) >= 1:
                # 05/10 (Gaëtan : WhatsApp demandé après le compte 1, pas bloquant) : il n'a pas écrit, Gaëtan le relance d'un appui
                jours = _jours_depuis(fait1, maintenant)
                ou, texte = f"compte 1 créé depuis {jours} j, pas de WhatsApp (`!wa @{prenom}` quand c'est fait)", message(prenom, "whatsapp", 1, jours)
            elif n == 1:
                continue
            else:
                # 01/10 (Antoinr, étape 2 depuis 4 jours sans un Reel, jamais listé) : aux étapes 2 et 3, un clipper sans Reel est
                # signalé même si l'étape est jeune — et c'est ce qui bloque l'ouverture de son compte suivant (règle du 01/10)
                jours = int(sans_reel.get(str(uid), -1))
                if jours < JOURS_SANS_REEL:
                    continue
                ou, texte = f"aucun Reel depuis {jours} j", message(prenom, "reel", n, jours)
            out.append((jours, prenom, crea, ou, lien_whatsapp(tel_de(uid), texte)))
    out.sort(key=lambda x: -x[0])
    return out[:MAX_JOUR]


def lignes(bloques: list) -> list:
    """10/10 (lot L9b) : [] quand personne n'est bloqué — plus jamais « personne 🎉 » : un message sans action est du bruit."""
    if not bloques:
        return []
    out = [f"🚧 **Bloqués ce matin ({len(bloques)})** : appuie sur WhatsApp, relis, envoie."]
    for _, prenom, creatrice, ou, lien in bloques:
        out.append(f"· **{prenom}** ({creatrice}) · {ou} · " + (f"[WhatsApp]({lien})" if lien else "pas de numéro"))
    return out


async def calculer() -> list:
    """La liste du moment (liste), avec le cas « compte illisible » (comptes_illisibles)."""
    parcours = _deps["lire_json"](_deps["FICHIER_PARCOURS"], {})
    try:
        sans_reel = await _deps["jours_sans_reel"]()
    except Exception as erreur:                                          # noqa: BLE001 — sans le classeur, les comptes seulement
        journal.warning("Bloqués : jours sans Reel illisibles (%s)", erreur)
        sans_reel = {}

    def uid_de(prenom):
        m = _deps["membre_par_prenom"](_deps["normaliser"](str(prenom).split()[0]))
        return str(m.id) if m is not None else ""
    return liste(parcours, _deps["roster_groupes"](), uid_de, _deps["tel_de"], sans_reel,
                 illisibles=lambda u, f, t: comptes_illisibles(u, f, t))


async def lignes_digest() -> list:
    """10/10 (lot L9b) : les lignes du bloc « bloqués » du digest du matin ; [] s'il n'y a personne (le bloc n'apparaît pas), ou
    si la liste est éteinte (BLOQUES=0 : plus rien le matin, `!bloques` répond toujours)."""
    if not ACTIF:
        return []
    bloques = await calculer()
    journal.info("Bloqués du matin (digest) : %d", len(bloques))
    return lignes(bloques)


async def envoyer(canal) -> int:
    """La liste dans `canal` (plusieurs messages si elle dépasse 2 000 caractères). Personne : rien n'est posté, renvoie 0."""
    bloques = await calculer()
    morceau = ""
    for ligne in lignes(bloques):                                       # plusieurs messages si la liste dépasse 2 000 caractères
        if len(morceau) + len(ligne) + 1 > 1900:
            await canal.send(morceau, suppress_embeds=True)
            morceau = ""
        morceau += ("\n" if morceau else "") + ligne
    if morceau:
        await canal.send(morceau, suppress_embeds=True)
    journal.info("Bloqués du matin : %d", len(bloques))
    return len(bloques)


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith(("!bloques", "!bloqués")):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    if not await envoyer(message.channel):                              # 10/10 : la commande répond toujours, sans emoji de fête
        await message.reply("Personne n'est bloqué en ce moment.")
    return True


async def boucle(client):
    await client.wait_until_ready()
    if not ACTIF:
        journal.info("Liste des bloqués éteinte (BLOQUES=0)")
        return
    if DIGEST:                                                          # 10/10 (lot L9b) : la liste part dans le digest du matin
        journal.info("Liste des bloqués : dans le digest du matin (DIGEST=1), plus de message à %d h", HEURE)
        return
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            etat = _deps["lire_json"](_deps["FICHIER"], {})
            if maintenant.hour >= HEURE and etat.get("dernier") != jour:
                canal = await _deps["canal_admin"]()
                if canal is not None:
                    await envoyer(canal)
                    etat["dernier"] = jour
                    _deps["ecrire_json"](_deps["FICHIER"], etat)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Boucle des bloqués : %s", erreur)
        await asyncio.sleep(1200)
