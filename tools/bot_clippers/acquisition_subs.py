"""Les subs de la veille dans le salon acquisition du serveur chatting (30/09, Gaëtan : « on va plutôt afficher les subs de la
veille, ce sera plus cohérent pour les clippeurs ; diviser Chloé OF / Chloé MYM, Sarah OF / Sarah MYM, Sophie OF / Sophie MYM »).

Les subs viennent du classeur Data G&M (saisi par Rianah vers 13 h, lu par le compte de service : rapport_quotidien.data_gm).
Le serveur chatting est un autre serveur Discord, où ce bot n'est pas : le message part par un WEBHOOK du salon acquisition,
donné une fois avec `!acquisition-webhook <url>` (gardé sur le volume, jamais dans le dépôt ; le message qui le contient est
effacé). Envoi une fois par jour, dès que la veille est saisie pour toutes les créatrices de la liste (entre SUBS_HEURE_MIN et
SUBS_HEURE_MAX, heure de Paris) ; à SUBS_HEURE_MAX, il part même incomplet (« pas encore saisi »). `!acquisition-subs`
(staff) : l'aperçu ici ; `!acquisition-subs envoyer` : l'envoi tout de suite dans le salon acquisition.

    Hier (29 septembre)

    Chloé OF 12
    Chloé MYM 8

    Sarah OF 20
    Sarah MYM 30
    …"""

import asyncio
import logging
import os
import re
import unicodedata
from datetime import timedelta

import aiohttp

journal = logging.getLogger("acquisition_subs")
# 30/09 (Gaëtan) : cet ordre-là ; OF et/ou MYM selon ce qu'on gère pour chaque créatrice
CREATRICES = [c.strip() for c in os.environ.get("ACQUISITION_SUBS_CREATRICES", "Chloé,Sarah,Sophie,Maddie,Jade,Clara").split(",") if c.strip()]
# Plateformes gérées : déduites de Data G&M (une plateforme sans aucun sub ni CA sur 30 jours n'est pas gérée) ; ce réglage en
# AJOUTE toujours, ex. « Jade=OF;Sophie=OF+MYM ». 30/09 (Gaëtan : « Jade on a OF, attention ») : Jade=OF par défaut.
FORCE = {k.strip(): v.strip().upper() for k, v in (x.split("=", 1) for x in os.environ.get("ACQUISITION_SUBS_PLATEFORMES", "Jade=OF").split(";") if "=" in x)}
HEURE_MIN = int(os.environ.get("SUBS_HEURE_MIN", "10") or 10)
HEURE_MAX = int(os.environ.get("SUBS_HEURE_MAX", "18") or 18)
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
RE_WEBHOOK = re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+")
_deps = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (état : webhook, dernier), data_gm (async date -> {onglet: lignes}), heure_paris,
    est_staff."""
    _deps.update(deps)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", t)


def _etat() -> dict:
    return _deps["lire_json"](_deps["FICHIER"], {})


def _jour_fr(j) -> str:
    return f"{j.day}{'er' if j.day == 1 else ''} {MOIS[j.month - 1]}"


def _onglet(donnees: dict, crea: str):
    cle = _norm(crea)[:4]                                               # « Maddie » trouve l'onglet « Maddy »
    return next((t for t in donnees if _norm(t).startswith(cle)), None)


def plateformes(lignes: list, jour) -> tuple:
    """(OF géré, MYM géré) d'après les 30 jours avant `jour` : une plateforme sans aucun sub ni CA n'est pas gérée."""
    recentes = [l for l in lignes if jour - timedelta(days=30) <= l["date"] <= jour]
    of = any((l.get("of_subs") or 0) or (l.get("of_usd") or 0) for l in recentes)
    mym = any((l.get("mym_subs") or 0) or (l.get("mym_eur") or 0) for l in recentes)
    return of, mym


def lignes_du_jour(donnees: dict, jour) -> list:
    """[(créatrice, ligne du jour ou None, OF géré, MYM géré, raison)] dans l'ordre de CREATRICES ; une créatrice sans
    aucune donnée sur 30 jours (ni OF ni MYM) est laissée de côté."""
    out = []
    for crea in CREATRICES:
        onglet = _onglet(donnees, crea)
        lignes = donnees.get(onglet) or [] if onglet else []
        of, mym = plateformes(lignes, jour)
        force = next((v for k, v in FORCE.items() if _norm(k)[:4] == _norm(crea)[:4]), "")
        if force:                                                       # toujours affichée(s), en plus de ce que dit Data G&M
            of, mym = of or "OF" in force, mym or "MYM" in force
        if not (of or mym):
            continue
        ligne = next((l for l in lignes if l["date"] == jour), None)
        raison = "" if (ligne and ligne.get("saisi")) else ("onglet introuvable dans Data G&M" if not onglet else "pas encore saisi")
        out.append((crea, ligne if not raison else None, of, mym, raison))
    return out


def texte(jour, lignes: list, titre: str = "Hier") -> str:
    blocs = [f"{titre} ({_jour_fr(jour)})"]
    for crea, l, of, mym, raison in lignes:
        if l is None:
            blocs.append(f"{crea} : {raison}")
            continue
        morceaux = ([f"{crea} OF {int(l.get('of_subs') or 0)}"] if of else []) + ([f"{crea} MYM {int(l.get('mym_subs') or 0)}"] if mym else [])
        blocs.append("\n".join(morceaux))
    return "\n\n".join(blocs)


async def poster(texte_: str) -> bool:
    url = _etat().get("webhook", "")
    if not url:
        return False
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        async with s.post(url, json={"content": texte_[:1990], "allowed_mentions": {"parse": []}}) as r:
            if r.status >= 300:
                raise RuntimeError(f"webhook {r.status} : {(await r.text())[:120]}")
    return True


async def preparer(forcer: bool = False):
    """(texte, complet) pour la veille."""
    hier = _deps["heure_paris"]().date() - timedelta(days=1)
    lignes = lignes_du_jour(await _deps["data_gm"](hier + timedelta(days=1)), hier)
    return texte(hier, lignes), bool(lignes) and all(l is not None for _, l, _, _, _ in lignes)


async def commande(message, texte_cmd: str) -> bool:
    mots = texte_cmd.split()
    if not mots or mots[0].lower() not in ("!acquisition-webhook", "!acquisition-subs"):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Commande réservée au staff.")
        return True
    if mots[0].lower() == "!acquisition-webhook":
        try:
            await message.delete()                                       # l'URL du webhook ne reste pas affichée
        except Exception:                                                # noqa: BLE001
            pass
        m = RE_WEBHOOK.search(texte_cmd)
        if not m:
            await message.channel.send("Donne l'URL du webhook du salon acquisition : `!acquisition-webhook https://discord.com/api/webhooks/…`")
            return True
        etat = _etat()
        etat["webhook"] = m.group(0)
        _deps["ecrire_json"](_deps["FICHIER"], etat)
        await message.channel.send("🔗 Webhook du salon acquisition enregistré (message effacé). `!acquisition-subs envoyer` pour tester.")
        return True
    texte_, complet = await preparer()
    if len(mots) > 1 and mots[1].lower() == "envoyer":
        try:
            ok = await poster(texte_)
        except Exception as erreur:                                      # noqa: BLE001
            await message.reply(f"⚠️ Envoi impossible : {erreur}")
            return True
        await message.reply("✅ Envoyé dans le salon acquisition." if ok else "Pas de webhook : `!acquisition-webhook <url>` d'abord.")
        return True
    absentes = [c for c in CREATRICES if not re.search(rf"(?m)^{re.escape(c)}\b", texte_)]
    await message.reply("Aperçu" + ("" if complet else " (pas encore complet)") + " :\n```\n" + texte_ + "\n```"
                        + (f"\n-# Non affichées (aucun sub ni CA sur 30 jours dans Data G&M) : {', '.join(absentes)}" if absentes else ""))
    return True


async def boucle(client):
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            etat = _etat()
            if etat.get("webhook") and etat.get("dernier") != jour and HEURE_MIN <= maintenant.hour:
                texte_, complet = await preparer()
                if complet or maintenant.hour >= HEURE_MAX:
                    if await poster(texte_):
                        etat = _etat()
                        etat["dernier"] = jour
                        _deps["ecrire_json"](_deps["FICHIER"], etat)
                        journal.info("Subs de la veille envoyés au salon acquisition%s", "" if complet else " (incomplet)")
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Subs de la veille : %s", erreur)
        await asyncio.sleep(600)
