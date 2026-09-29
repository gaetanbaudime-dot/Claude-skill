"""Le classeur se vérifie seul (29/09, Gaëtan : GO — « au scan du matin : mail ou handle en double, ligne BAN qui garde un
Gérant, réservation jamais créée. Signalé dans bot-gaetan, jamais corrigé seul »).

Après chaque scan (et sur `!classeur`), les lignes du classeur des logins sont passées au crible : un même e-mail sur deux
lignes, un même pseudo sur deux lignes, une ligne BAN qui garde le nom d'un clipper, une ligne « à créer » réservée par un
clipper et jamais vue sur Instagram après SCANS_MIN scans, un clipper avec plus de trois comptes vivants. Le résultat part dans
le salon admin quand la liste change (silence quand rien ne bouge, silence quand tout est propre) ; `!classeur` le redonne
à la demande. Rien n'est corrigé : c'est Gaëtan qui tranche dans le classeur. Les gérants hors clipping (DASHBOARD_EXCLUS :
Julien, Rianah) ne comptent pas pour les BAN, les réservations et le plafond de trois comptes."""
import hashlib
import logging
import os
from datetime import datetime, timezone

journal = logging.getLogger("bot.classeur_verif")
SCANS_MIN = int(os.environ.get("CLASSEUR_SCANS_MIN", "7") or 7)
MAX_COMPTES = int(os.environ.get("CLASSEUR_MAX_COMPTES", "3") or 3)
LIBRES = {"", "x", "y", "z", "aaa", "?", "-", "libre", "dispo"}
A_CREER = ("a creer", "à créer")
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER_VERIF, canal_admin, est_staff, normaliser, exclus() (prénoms hors clipping),
    lire_comptes, historique() (dict handle → scans)."""
    _deps.update(deps)


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _prenom(c) -> str:
    g = str(c.get("gerant") or "").strip()
    return g.split()[0] if g else ""


def _en_gestion(c) -> bool:
    return _n(c.get("utilisation") or "clipper") in ("clipper", "") and _n(_prenom(c)) not in LIBRES


def _etiquette(c) -> str:
    """« Josué (GOOD) » — le clipper et l'état de la ligne."""
    return f"{_prenom(c) or 'sans gérant'} ({c.get('etat') or '?'})"


def _compter(paires: list) -> str:
    """[(onglet, prénom)…] → « Sarah → Jonas 3, Tara 1 · Sophie → Raphael 1 »."""
    par_onglet = {}
    for onglet, prenom in paires:
        par_onglet.setdefault(onglet, {}).setdefault(prenom, 0)
        par_onglet[onglet][prenom] += 1
    return " · ".join(f"{o} → " + ", ".join(f"{p} {n}" for p, n in sorted(cs.items(), key=lambda kv: (-kv[1], kv[0])))
                      for o, cs in par_onglet.items())


def anomalies(comptes: list, historique: dict | None = None, exclus=None) -> list:
    """Les lignes du rapport, une par famille d'anomalie (vide quand le classeur est propre)."""
    historique = historique or {}
    exclus = {_n(x) for x in (exclus or [])}
    out = []
    # 1. un même e-mail sur plusieurs lignes (tous onglets)
    par_mail = {}
    for c in comptes:
        m = (c.get("mail") or "").strip().lower()
        if m:
            par_mail.setdefault(m, []).append(c)
    doublons = []
    for m, cs in par_mail.items():
        if len(cs) > 1:
            num = next((c["numero"] for c in cs if c.get("numero")), "")
            ref = f"{cs[0].get('onglet') or '?'} n° {num}" if num else f"{cs[0].get('onglet') or '?'} {m[:6]}…"
            brule = " ⚠️ mail brûlé (ligne BAN) réutilisé" if any(_n(c.get("etat")) == "ban" for c in cs) else ""
            doublons.append(f"{ref} → " + " + ".join(_etiquette(c) for c in cs) + brule)
    if doublons:
        out.append("• Mail en double : " + " · ".join(sorted(doublons)))
    # 2. un même pseudo sur plusieurs lignes
    par_handle = {}
    for c in comptes:
        h = (c.get("handle") or "").strip().lower().lstrip("@")
        if h:
            par_handle.setdefault(h, []).append(c)
    doublons = []
    for h, cs in par_handle.items():
        if len(cs) > 1:
            ou = ", ".join(f"{c.get('onglet') or '?'} n° {c['numero']}" if c.get("numero") else f"{c.get('onglet') or '?'} ligne {c.get('ligne')}" for c in cs)
            doublons.append(f"@{h} → " + " + ".join(sorted({_prenom(c) or 'sans gérant' for c in cs})) + f" ({ou})")
    if doublons:
        out.append("• Pseudo en double : " + " · ".join(sorted(doublons)))
    # 3. une ligne BAN qui garde un Gérant
    bans = [(c.get("onglet") or "?", _prenom(c)) for c in comptes
            if _n(c.get("etat")) == "ban" and _en_gestion(c) and _n(_prenom(c)) not in exclus]
    if bans:
        out.append(f"• BAN avec un Gérant ({len(bans)}) : " + _compter(bans))
    # 4. réservée, jamais créée : « à créer » avec un Gérant, jamais vue sur Instagram après SCANS_MIN scans
    jamais = []
    for c in comptes:
        if _n(c.get("etat")) not in A_CREER or not _en_gestion(c) or _n(_prenom(c)) in exclus:
            continue
        scans = historique.get((c.get("handle") or "").lower(), [])
        if len(scans) >= SCANS_MIN and not any(s.get("existe") for s in scans):
            jamais.append((c.get("onglet") or "?", _prenom(c)))
    if jamais:
        out.append(f"• À créer depuis {SCANS_MIN} scans ou plus ({len(jamais)}) : " + _compter(jamais))
    # 5. plus de MAX_COMPTES comptes vivants pour un clipper (BAN exclus)
    vivants = {}
    for c in comptes:
        if _en_gestion(c) and _n(c.get("etat")) != "ban" and _n(_prenom(c)) not in exclus and c.get("handle"):
            cle = (c.get("onglet") or "?", _n(_prenom(c)), _prenom(c))
            vivants[cle] = vivants.get(cle, 0) + 1
    trop = [f"{p} {n} ({o})" for (o, _, p), n in sorted(vivants.items()) if n > MAX_COMPTES]
    if trop:
        out.append(f"• Plus de {MAX_COMPTES} comptes vivants : " + ", ".join(trop))
    return out


def texte(lignes: list, jour: str | None = None) -> str:
    jour = jour or datetime.now(timezone.utc).strftime("%d/%m")
    if not lignes:
        return f"🧹 Classeur ({jour}) : rien à signaler."
    return f"🧹 Classeur ({jour}) : {len(lignes)} point(s) à trancher, rien corrigé\n" + "\n".join(lignes)


def _empreinte(lignes: list) -> str:
    return hashlib.sha1("\n".join(lignes).encode("utf-8")).hexdigest()[:16]


async def verifier(comptes: list, historique: dict | None = None, force: bool = False) -> str | None:
    """Calcule le rapport ; le poste dans le salon admin s'il a changé depuis le dernier envoi (ou `force`). Renvoie le texte
    posté, None sinon."""
    exclus = _deps["exclus"]() if _deps.get("exclus") else []
    lignes = anomalies(comptes, historique, exclus)
    d = _deps["lire_json"](_deps["FICHIER_VERIF"], {}) if _deps.get("lire_json") else {}
    empreinte = _empreinte(lignes)
    if not force and d.get("empreinte") == empreinte:
        return None
    if not force and not lignes:
        d.update({"empreinte": empreinte, "jour": datetime.now(timezone.utc).isoformat(timespec="minutes"), "n": 0})
        if _deps.get("ecrire_json"):
            _deps["ecrire_json"](_deps["FICHIER_VERIF"], d)
        return None
    t = texte(lignes)
    if _deps.get("canal_admin"):
        try:
            canal = await _deps["canal_admin"]()
            if canal is not None:
                await canal.send(t[:1950])
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Vérification du classeur : salon admin : %s", erreur)
    d.update({"empreinte": empreinte, "jour": datetime.now(timezone.utc).isoformat(timespec="minutes"), "n": len(lignes)})
    if _deps.get("ecrire_json"):
        _deps["ecrire_json"](_deps["FICHIER_VERIF"], d)
    journal.info("Vérification du classeur : %d famille(s) d'anomalies signalée(s)", len(lignes))
    return t


async def commande(message, texte_cmd: str) -> bool:
    """`!classeur` : le rapport tout de suite, même s'il n'a pas changé."""
    mots = texte_cmd.split()
    if not mots or mots[0].lower() not in ("!classeur", "!verif", "!vérif"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if not _deps.get("lire_comptes"):
        await message.reply("Classeur inactif.")
        return True
    comptes = await _deps["lire_comptes"]()
    historique = _deps["historique"]() if _deps.get("historique") else {}
    exclus = _deps["exclus"]() if _deps.get("exclus") else []
    await message.reply(texte(anomalies(comptes, historique, exclus))[:1950])
    return True
