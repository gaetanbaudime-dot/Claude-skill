"""Parcours guidé du clipper dans son salon perso, et mémoire par clipper (25/09/2026).

Dès `!creatrice`, une fois ses comptes livrés, le bot déroule dans le salon perso un parcours en étapes :
créer le compte 1, le compte 2, le compte privé, le warm-up (7 jours comptés chaque matin), le premier Reel,
le lien en bio, la routine. Chaque étape = un message court, des boutons-liens vers la bonne fiche du forum
formation et le salon d'infos de la créatrice, et un bouton « ✅ C'est fait » qui ouvre l'étape suivante.
Dans ce salon, l'assistant IA joue le manager : il reçoit la mémoire du clipper (étape, comptes, lien, clics,
notes du manager) avec chaque question.

État dans parcours.json : {uid: {"prenom", "creatrice", "salon_id", "etape", "dates": {n: iso}, "messages": {n: id},
"notes": [{"date", "par", "texte"}], "warmup_jour"}}. Commandes manager : `!etape @clipper [n]`, `!note @clipper texte`,
`!memoire @clipper`. Le module ne connaît pas bot_discord : tout passe par `configurer(deps)`.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import discord

import onboarding
import paie_clics

journal = logging.getLogger("parcours")
_deps = {}
WARMUP_JOURS = int(os.environ.get("WARMUP_JOURS", "1") or 1)
# 30/09 (Gaëtan, GO : « période d'essai sur 1 seul compte : le clippeur validé reçoit 1 compte, il débloque les comptes 2 et 3
# seulement après 5 Reels publiés en 72 h ; ceux qui ne publient pas ne coûtent qu'un compte ») : pour les parcours commencés
# à partir d'ESSAI_DEPUIS. Le scan du matin compte les Reels du compte 1 sur ses trois derniers passages.
ESSAI = os.environ.get("ESSAI_UN_COMPTE", "1").strip() != "0"
ESSAI_REELS = int(os.environ.get("ESSAI_REELS", "5") or 5)
ESSAI_DEPUIS = os.environ.get("ESSAI_DEPUIS", "2026-09-30").strip()
TEXTE_ESSAI = ("🎯 **Période d'essai : ton compte 1 seulement.**\n\n"
               "D'abord 24 h de warm-up dessus : regarde des Reels, mets des likes, abonne-toi à 2 comptes. Pas de Reel.\n\n"
               "Je te dis ici quand il peut publier.")                   # 30/09 : la suite (5 Reels en 72 h) arrive quand elle sert
# 30/09 (Gaëtan : « arrête de spammer les clippeurs : une information à la fois, au bon moment ; un compte par un compte, on
# distille l'information et on ne la donne que quand il en a réellement besoin ») : chaque compte se fait en trois temps,
# un message chacun — 1) identifiants et création, bouton « créé » ; 2) photo, nom et bio en UN message, bouton « profil
# fait » ; 3) une ligne de warm-up. Le compte suivant arrive tout seul 48 h plus tard (la règle des 48 h n'était qu'une
# phrase : le compte 2 tombait dès le bouton du compte 1), et « il peut publier » arrive 24 h plus tard, avec le Drive.
DISTILLE_DEPUIS = "2026-09-30T06:40:00+00:00"   # une étape envoyée avant : son profil est déjà parti (ancien déroulé), pas de doublon
ATTENTE_COMPTE_H = int(os.environ.get("PARCOURS_ATTENTE_COMPTE_H", "48") or 48)
WARMUP_H = int(os.environ.get("PARCOURS_WARMUP_H", "24") or 24)
TEXTE_WARMUP = ("🔥 **Compte {n} : 24 h de warm-up.** Regarde des Reels, mets des likes, abonne-toi à 2 comptes. Pas de Reel.\n\n"
                "Ton compte {suivant} arrive ici le {quand}.")
TEXTE_PUBLIER = {1: ("✅ **Ton compte 1 peut publier.** {rythme}\n\n"
                     "Prends une vidéo dans ton Drive : {drive}\n\n"
                     "Modifie-la toujours avant : musique, texte, un début qui accroche (Fiche 3)."),
                 2: "✅ **Ton compte 2 peut publier.** 2 Reels par jour dessus aussi, comme sur le compte 1."}   # 26/09 (Gaëtan) : 24 h de warm-up par compte, plus une semaine
LIEN_REPORTING = os.environ.get("LIEN_REPORTING", "https://forms.gle/uhPewryox7R4jifv5").strip()   # formulaire du dimanche

ETAPES = {
    # 26/09 (Gaëtan) : textes courts, 24 h de warm-up sur chaque compte, puis les Reels.
    # 29/09 (Gaëtan) : « un compte tous les 48 h » — jamais plus vite, c'est ce qui limite les bans (7 comptes perdus le 28/09).
    1: {"titre": "Étape 1 · Crée ton compte 1", "fiche": "1", "bouton": "✅ Compte 1 créé", "salons": [],
        "texte": ("Identifiant :\n```\n{compte1}\n```\nE-mail :\n```\n{mail1}\n```\nMot de passe :\n```\n{mdp1}\n```\n"
                  "{creation1}\n\n"
                  "Créé ? Appuie sur le bouton.")},
    2: {"titre": "Étape 2 · Crée ton compte 2", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": [],
        "texte": ("Identifiant :\n```\n{compte2}\n```\nE-mail :\n```\n{mail2}\n```\nMot de passe :\n```\n{mdp2}\n```\n"
                  "{creation2}\n\n"
                  "Créé ? Appuie sur le bouton.")},
    3: {"titre": "Étape 3 · Crée ton compte 3", "fiche": "1", "bouton": "✅ Compte 3 créé", "salons": [],
        "texte": ("Identifiant :\n```\n{compte3}\n```\nE-mail :\n```\n{mail3}\n```\nMot de passe :\n```\n{mdp3}\n```\n"
                  "{creation3}\n\n"
                  "Créé ? Appuie sur le bouton.")},
    4: {"titre": "Étape 4 · 24 h de warm-up sur le compte 3 (Fiche 2)", "fiche": "2", "bouton": "✅ Warm-up fini", "salons": ["ressources"],
        "texte": ("**Compte 3, pendant 24 h** : pas de Reel. 10 min de Reels de créatrices françaises ({ressources}), "
                  "5 likes, 2 abonnements, 1 story sans lien.\n\n"
                  "**Comptes 1 et 2** : ils ont fini leur warm-up. 2 Reels par jour sur chacun, pris dans ton Drive, "
                  "et 1 story par jour (une photo du dossier Photos de ton Drive).\n\n"
                  "Dans 24 h, le compte 3 publie aussi.")},
    5: {"titre": "Étape 5 · Tes Reels sur les 3 comptes (Fiche 3)", "fiche": "3", "bouton": "✅ Premier Reel publié", "salons": ["ressources"],
        "texte": ("Tes vidéos : {drive}\n\n"
                  "1. Prends une vidéo dans ce dossier. Modifie-la toujours : musique, texte, un début qui accroche.\n"
                  "2. Publie-la sur `{compte1}`, `{compte2}` et `{compte3}`. Jamais la même vidéo sur deux comptes le même jour.\n\n"
                  "Premier Reel en ligne ? Appuie sur le bouton.")},
    6: {"titre": "Étape 6 · Mets ton lien, une seule fois (Fiche 4)", "fiche": "4", "bouton": "✅ Lien mis", "salons": [],
        "texte": ("**Ton lien** : {lien}\n\n"
                  "1. Sur chaque compte : le lien dans une story, puis cette story **à la une** (épinglée sur ton profil).\n"
                  "2. Une seule fois. Ensuite tu n'y touches plus.\n"
                  "3. Jamais de lien ni d'@ dans la bio, jamais dans un Reel. Les @ en bio font des bans.\n"
                  "4. Chaque jour, une story avec le widget Instagram de ton profil et une capture : elle envoie les gens vers ta story à la une.\n"
                  "5. `!mesclics` ici : ce lien compte tes visites, donc ta paie, tous les 15 jours.\n\n"
                  "Fini ? Appuie sur le bouton.")},
    7: {"titre": "🎉 Bravo, tu as fini · Ta routine de chaque jour", "fiche": "4", "bouton": "", "salons": [],
        "texte": ("Chaque jour : 2 Reels sur chacun de tes 3 comptes, 1 story avec le widget vers ta story à la une, quelques commentaires.\n\n"
                  "Chaque semaine, ajoute 1 Reel par jour sur chaque compte, jusqu'à 10. Le matin tu montes, tu mets en brouillon, tu publies dans la journée.\n\n"
                  "Chaque matin, tes visites d'hier ici.\n\n"
                  "Tu connais quelqu'un de sérieux ? Tape `!parrain @lui` ici : 5 $ pour toi le jour de sa première paie.\n\n"
                  "Une question ? Écris ici.")},
}
# 28/09 : un compte rendu par un sortant existe déjà → on s'y connecte (le code de CONNEXION arrive dans le salon), pas d'inscription
CREATION = ("1. Instagram → Créer un compte → avec cet e-mail.\n"
            "2. Un code est demandé ? Écris `!code` ici.\n"
            "3. Mets ce mot de passe. Numéro demandé ? Le tien. Date de naissance : la vraie.",
            "Même chose que le compte 1, sur le même téléphone : tu ajoutes un compte, sans te déconnecter.\n"
            "⚠️ Instagram ne demande pas d'e-mail ? Arrête et écris-le ici.",
            "Crée-le comme les autres, sur le même téléphone.")
CONNEXION = ("Ce compte existe déjà, il a déjà chauffé.\n"
             "1. Instagram → Se connecter → cet identifiant et ce mot de passe.\n"
             "2. Code demandé ? Il arrive ici tout seul. Sinon écris `!code`.\n"
             "3. Numéro demandé ? Mets le tien. Ne change ni la photo ni la bio pour l'instant.",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter, sans te déconnecter du compte 1. Code demandé ? Il arrive ici.",
             "Ce compte existe déjà. Ajoute-le sur le même téléphone : Se connecter. Code demandé ? Il arrive ici.")
RELANCE_JOURS = int(os.environ.get("PARCOURS_RELANCE_JOURS", "2") or 2)   # 28/09 (Gaëtan) : « des relances simples, courtes »
# 30/09 (Daniella) : « sur chaque compte… pas de Reel » contredisait l'étape 4 (comptes 1 et 2 publient déjà) — le warm-up du
# jour ne concerne que le compte 3.
WARMUP_JOUR_TEXTE = ("🔥 **Warm-up du compte 3 : jour {j} sur {jours}.** Sur le compte 3 : 10 minutes de Reels, 5 likes, "
                     "2 abonnements, 1 story sans lien, pas de Reel. Comptes 1 et 2 : 2 Reels et 1 story chacun, comme d'habitude.")


def configurer(deps: dict):
    global _deps
    _deps = deps


def en_essai_neuf(fiche_p: dict) -> bool:
    """Le parcours entre-t-il dans la période d'essai ? Seulement ceux dont l'étape 1 a commencé depuis ESSAI_DEPUIS."""
    debut = str((fiche_p.get("dates") or {}).get("1", ""))[:10]
    return ESSAI and bool(debut) and debut >= ESSAI_DEPUIS and not fiche_p.get("essai")


def en_essai(fiche_p: dict) -> bool:
    """Compte 1 seul, comptes 2 et 3 encore fermés."""
    return bool(fiche_p.get("essai")) and not (fiche_p.get("essai") or {}).get("fini")


async def _suite(salon, texte: str):
    """Le message de suivi du salon : il remplace le précédent (matin.remplacer), sinon un envoi simple."""
    if _deps.get("remplacer_suite"):
        return await _deps["remplacer_suite"](salon, texte)
    return await salon.send(texte)


def _lire() -> dict:
    return _deps["lire_json"](_deps["FICHIER_PARCOURS"], {})


def _ecrire(d: dict):
    _deps["ecrire_json"](_deps["FICHIER_PARCOURS"], d)


def _norm(t: str) -> str:
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").lower()


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ liens et contexte
def _url(guild, cid) -> str:
    return f"https://discord.com/channels/{guild.id}/{cid}"


def _salon_nom(guild, *mots):
    """Premier salon texte dont le nom normalisé contient tous les mots."""
    for c in guild.text_channels:
        n = _norm(c.name)
        if all(m in n for m in mots):
            return c
    return None


def _salon_info(guild, creatrice: str):
    """Le salon d'infos de la créatrice (ℹ️-sophie / i-sophie), sinon le premier salon de sa catégorie."""
    cat = _deps["categorie_de_creatrice"](guild, creatrice) if _deps.get("categorie_de_creatrice") else None
    if cat is None:
        return None
    for c in cat.text_channels:
        n = _norm(c.name)
        if "ℹ" in c.name or n.startswith("i-") or "info" in n:
            return c
    return cat.text_channels[0] if cat.text_channels else None


async def _contexte(guild, uid: str, fiche_p: dict) -> dict:
    """Les valeurs des gabarits : comptes (handle + e-mail, croissance d'abord, privé en 3), lien, Drive, salons."""
    ctx = {"prenom": fiche_p.get("prenom", ""), "creatrice": fiche_p.get("creatrice", ""),
           "jours": WARMUP_JOURS, "jour_suivant": WARMUP_JOURS + 1}
    try:
        onb = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(uid, {})
    except Exception:
        onb = {}
    handles = list(onb.get("comptes", []))
    mails = {}
    try:
        if onboarding.actif() and handles:
            for c in await onboarding.lire_comptes():
                if c["handle"] in handles:
                    mails[c["handle"]] = c.get("mail", "")
    except Exception as erreur:
        journal.info("Classeur indisponible pour le parcours : %s", erreur)
    prives = [h for h in handles if onboarding._est_prive({"handle": h, "etat": ""})]
    croissance = [h for h in handles if h not in prives]
    ordonnes = croissance[:2] + prives[:1]
    if len(ordonnes) < 3:
        ordonnes += [h for h in handles if h not in ordonnes][:3 - len(ordonnes)]
    acces = {a.get("handle"): a for a in (onb.get("acces") or []) if isinstance(a, dict)}   # 27/09 : mot de passe et e-mail par compte
    for i in range(3):
        h = ordonnes[i] if i < len(ordonnes) else "?"
        ctx[f"compte{i + 1}"] = h
        ctx[f"mail{i + 1}"] = acces.get(h, {}).get("mail") or mails.get(h, "(dans ton message de comptes plus haut)")
        ctx[f"mdp{i + 1}"] = acces.get(h, {}).get("mdp") or "(celui de ton message de comptes)"
    ctx["lien"] = onb.get("lien") or "(ton manager te le donne avec `!lien`)"
    ctx["drive"] = onb.get("drive") or "(pas encore prêt, je te le donne ici dès qu'il l'est)"
    creatrice = ctx["creatrice"]
    info = _salon_info(guild, creatrice) if guild is not None else None
    ctx["info"] = f"<#{info.id}>" if info is not None else f"le salon d'infos de {creatrice}"
    res = _salon_nom(guild, "ressources") if guild is not None else None
    ctx["ressources"] = f"<#{res.id}>" if res is not None else "#ressources"
    for i in range(3):                                                  # 28/09 : création, ou connexion à un compte rendu par un sortant
        a = acces.get(ctx[f"compte{i + 1}"], {})
        ctx[f"creation{i + 1}"] = (CONNEXION[i] if a.get("cree") else CREATION[i]).format(info=ctx["info"])
    rep = _salon_nom(guild, "reporting") if guild is not None else None
    ctx["reporting"] = f"<#{rep.id}>" if rep is not None else "#reporting"
    ctx["lien_reporting"] = LIEN_REPORTING
    ctx["_info_id"] = info.id if info is not None else None
    ctx["_res_id"] = res.id if res is not None else None
    ctx["_rep_id"] = rep.id if rep is not None else None
    return ctx


class _Gabarit(dict):
    def __missing__(self, cle):
        return "…"


def _rendre(texte: str, ctx: dict) -> str:
    return texte.format_map(_Gabarit(ctx))


# ------------------------------------------------------------------ boutons
class BoutonEtape(discord.ui.DynamicItem[discord.ui.Button], template=r"parcours:(?P<uid>[0-9]+):(?P<etape>[0-9]+)"):
    """« ✅ C'est fait » : persistant (custom_id), donc il survit aux redémarrages du bot."""

    def __init__(self, uid: str, etape: int, label: str = "✅ C'est fait"):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.success,
                                           custom_id=f"parcours:{uid}:{etape}"))
        self.uid, self.etape = str(uid), int(etape)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["uid"], int(match["etape"]), item.label or "✅ C'est fait")

    async def callback(self, interaction: discord.Interaction):
        staff = _deps.get("est_staff")
        if str(interaction.user.id) != self.uid and not (staff and staff(interaction.user)):
            await interaction.response.send_message("Ce bouton est pour le clipper de ce salon 🙂", ephemeral=True)
            return
        await interaction.response.defer()
        await valider_etape(interaction.channel, self.uid, self.etape, par=str(interaction.user.id))


def _vue(guild, uid: str, n: int, ctx: dict):
    vue = discord.ui.View(timeout=None)
    e = ETAPES[n]
    posts = _deps.get("POSTS_FORMATION") or {}
    if e.get("fiche") and posts.get(e["fiche"]) and guild is not None:
        vue.add_item(discord.ui.Button(label=f"📄 Fiche {e['fiche']}", style=discord.ButtonStyle.link,
                                       url=_url(guild, posts[e["fiche"]])))
    for s in e.get("salons", []):
        cid = ctx.get({"info": "_info_id", "ressources": "_res_id", "reporting": "_rep_id"}[s])
        if cid and guild is not None:
            libelle = {"info": f"ℹ️ Infos {ctx.get('creatrice', '')}", "ressources": "💡 Ressources", "reporting": "📊 Reporting"}[s]
            vue.add_item(discord.ui.Button(label=libelle[:80], style=discord.ButtonStyle.link, url=_url(guild, cid)))
    if e.get("bouton"):
        vue.add_item(BoutonEtape(uid, n, _rendre(e["bouton"], ctx)))
    if _deps.get("whatsapp"):                                            # 26/09 (Gaëtan) : « un bouton, envoyer un message à Gaëtan »
        vue.add_item(discord.ui.Button(label="💬 Écrire à Gaëtan (WhatsApp)", style=discord.ButtonStyle.link, url=_deps["whatsapp"]))
    return vue


# ------------------------------------------------------------------ déroulé
async def envoyer_etape(salon, membre, n: int) -> None:
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.setdefault(uid, {"prenom": _prenom(membre),
                                 "creatrice": "", "salon_id": str(salon.id), "etape": n, "dates": {}, "notes": []})
    fiche_p["etape"] = n
    fiche_p["salon_id"] = str(salon.id)
    fiche_p.setdefault("dates", {})[str(n)] = _maintenant()
    ctx = await _contexte(getattr(salon, "guild", None), uid, fiche_p)
    e = ETAPES[n]
    texte = f"{membre.mention} **{_rendre(e['titre'], ctx)}**\n\n{_rendre(e['texte'], ctx)}"
    try:
        msg = await salon.send(texte[:1990], view=_vue(getattr(salon, "guild", None), uid, n, ctx))
        fiche_p.setdefault("messages", {})[str(n)] = str(msg.id)
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Étape %s pour %s : %s", n, uid, erreur)
    _ecrire(d)


async def demarrer_parcours(salon, membre, creatrice: str) -> None:
    """Après la livraison des comptes : étape 1. Rejoué sur un clipper déjà en route : on ne repart pas de zéro."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.get(uid)
    if fiche_p and fiche_p.get("etape", 0) >= 1 and fiche_p.get("creatrice") == creatrice:
        return
    d[uid] = {"prenom": _prenom(membre),
              "creatrice": creatrice, "salon_id": str(salon.id), "etape": 0, "dates": {}, "notes": (fiche_p or {}).get("notes", [])}
    _ecrire(d)
    await envoyer_etape(salon, membre, 1)


def mal_partis(fiches: dict, valides: set) -> list:
    """30/09 (Steeve) : les nouveaux (test validé) partis à l'étape 2 ou 3 sans jamais avoir eu l'étape 1 — [uid]."""
    out = []
    for uid, f in fiches.items():
        dates = f.get("dates") or {}
        if uid in valides and int(f.get("etape", 0)) in (2, 3) and not dates.get("1") and not dates.get("1_fait"):
            out.append(uid)
    return out


async def reprendre_au_compte_1(salon, membre, creatrice: str) -> None:
    """Remet un nouveau parti trop loin à l'étape 1 (calendrier, profils et programme effacés, notes gardées), avec une ligne
    d'excuse, puis l'étape 1."""
    d = _lire()
    f = d.get(str(membre.id)) or {}
    for cle in ("dates", "messages", "profils", "programme", "essai", "reconcilie", "corrige_4", "warmup_jour"):
        f.pop(cle, None)
    f["etape"] = 0
    d[str(membre.id)] = f
    _ecrire(d)
    try:
        await salon.send(f"{membre.mention} Petite erreur de ma part : on reprend dans l'ordre. Oublie le compte 2, commence par ton compte 1 👇")
    except (discord.Forbidden, discord.HTTPException):
        pass
    await forcer_etape(salon, membre, creatrice or f.get("creatrice", ""), 1)


async def demarrer_routine(salon, membre, creatrice: str) -> None:
    """Clipper déjà en place (comptes créés avant le bot) : le parcours démarre directement à la routine (étape 7),
    sans repasser par la création des comptes. Rejoué : rien."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.get(uid)
    if fiche_p and fiche_p.get("etape", 0) >= 7:
        return
    d[uid] = {"prenom": _prenom(membre),
              "creatrice": creatrice, "salon_id": str(salon.id), "etape": 7, "dates": {"7": _maintenant()},
              "notes": (fiche_p or {}).get("notes", [])}
    _ecrire(d)
    ctx = await _contexte(getattr(salon, "guild", None), uid, d[uid])
    e = ETAPES[7]
    try:
        await salon.send((f"{membre.mention} **{_rendre(e['titre'], ctx)}**\n\n{_rendre(e['texte'], ctx)}")[:1990],
                         view=_vue(getattr(salon, "guild", None), uid, 7, ctx))
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.warning("Routine pour %s : %s", uid, erreur)


async def valider_etape(salon, uid: str, n: int, par: str = "") -> bool:
    """Le bouton (ou le manager) ferme l'étape n et ouvre la suivante. Idempotent : un double clic ne saute rien."""
    d = _lire()
    fiche_p = d.get(str(uid))
    if not fiche_p or int(fiche_p.get("etape", 0)) != int(n):
        return False
    # 30/09 : compte créé → d'abord son profil (photo, nom, bio en UN message, bouton « profil fait »), rien d'autre ; le
    # deuxième appui (ou le scan qui voit le compte) ferme l'étape. Un compte rendu par un sortant garde son profil.
    if n in (1, 2, 3) and not (fiche_p.get("profils") or {}).get(str(n)) and _deps.get("profil_envoyer") \
            and str((fiche_p.get("dates") or {}).get(str(n)) or "9") >= DISTILLE_DEPUIS:
        ctx = await _contexte(getattr(salon, "guild", None), str(uid), fiche_p)
        if not str(ctx.get(f"creation{n}", "")).startswith("Ce compte existe déjà"):
            fiche_p.setdefault("profils", {})[str(n)] = _maintenant()
            _ecrire(d)
            await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get(str(n)))
            vue = discord.ui.View(timeout=None)
            vue.add_item(BoutonEtape(uid, n, "✅ Profil fait"))
            try:
                msg = await _deps["profil_envoyer"](salon, uid, n, fiche_p.get("creatrice", ""), vue=vue)
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Profil du compte %s pour %s : %s", n, uid, erreur)
                msg = None
            if msg is not None:
                d = _lire()
                d[str(uid)].setdefault("messages", {})[f"{n}p"] = str(getattr(msg, "id", ""))
                _ecrire(d)
                return True
            d = _lire()
            fiche_p = d.get(str(uid))                                   # profil impossible : on ferme l'étape quand même
    fiche_p.setdefault("dates", {})[f"{n}_fait"] = _maintenant()
    fiche_p["etape"] = n + 1
    _ecrire(d)
    for cle in (str(n), f"{n}p"):
        await _retirer_bouton(salon, (fiche_p.get("messages") or {}).get(cle))
    await _classeur_etat(uid, n)
    membre = _deps["membre_par_id"](uid)
    if membre is None:
        return True
    if _deps.get("effacer_suite"):                                      # 30/09 (GO n° 4) : l'ancien « prochaine étape » s'en va
        try:
            await _deps["effacer_suite"](salon)
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Message de suivi de %s : %s", uid, erreur)
    maintenant = datetime.now(timezone.utc)
    if n == 1 and en_essai_neuf(fiche_p):                               # 30/09 : période d'essai, le compte 2 attend
        d = _lire()
        d[str(uid)]["essai"] = {"depuis": _maintenant()}
        d[str(uid)]["programme"] = [{"quand": (maintenant + timedelta(hours=WARMUP_H)).isoformat(timespec="seconds"), "type": "publier", "n": 1}]
        _ecrire(d)
        await _suite(salon, f"{membre.mention} " + TEXTE_ESSAI.format(n=ESSAI_REELS))
        return True
    if n in (1, 2):                                                     # 30/09 : règle des 48 h tenue par le bot
        quand = maintenant + timedelta(hours=ATTENTE_COMPTE_H)
        d = _lire()
        d[str(uid)]["programme"] = [{"quand": (maintenant + timedelta(hours=WARMUP_H)).isoformat(timespec="seconds"), "type": "publier", "n": n},
                                    {"quand": quand.isoformat(timespec="seconds"), "type": "etape", "n": n + 1}]
        _ecrire(d)
        await _suite(salon, f"{membre.mention} " + TEXTE_WARMUP.format(n=n, suivant=n + 1, quand=_date_fr(quand)))
        return True
    if n + 1 in ETAPES:
        await envoyer_etape(salon, membre, n + 1)
    return True


async def _retirer_bouton(salon, mid) -> None:
    if not mid or not str(mid).isdigit():
        return
    try:
        ancien = await salon.fetch_message(int(mid))
        await ancien.edit(view=None)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        pass


async def programme_du_jour(client, maintenant=None) -> list:
    """30/09 : les messages programmés qui arrivent à échéance — « ton compte n peut publier » (24 h après sa création) et
    l'étape du compte suivant (48 h après). Chaque élément échu est retiré de la fiche AVANT l'envoi (jamais deux fois) ;
    un salon ou un membre introuvable le garde pour le passage suivant. Renvoie [(uid, type, n)] envoyés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    faits = []
    for uid, fiche_p in list(_lire().items()):
        programme = fiche_p.get("programme") or []
        echus = [x for x in programme if _echu(x, maintenant)]
        if not echus:
            continue
        salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
        membre = _deps["membre_par_id"](uid)
        if salon is None or membre is None:
            continue
        d = _lire()
        d[uid]["programme"] = [x for x in programme if x not in echus]
        _ecrire(d)
        for item in echus:
            n = int(item.get("n") or 0)
            fiche_p = _lire().get(uid, {})
            try:
                if item.get("type") == "publier" and n in TEXTE_PUBLIER:
                    ctx = await _contexte(getattr(salon, "guild", None), uid, fiche_p)
                    rythme = (f"Objectif : **{ESSAI_REELS} Reels en 72 h** dessus. Tes comptes 2 et 3 s'ouvrent ensuite tout seuls."
                              if en_essai(fiche_p) else "2 Reels par jour dessus.")
                    await salon.send(f"{membre.mention} " + TEXTE_PUBLIER[n].format(rythme=rythme, drive=ctx.get("drive", "ton Drive")))
                    faits.append((uid, "publier", n))
                elif item.get("type") == "etape" and int(fiche_p.get("etape", 0)) == n and not (fiche_p.get("dates") or {}).get(str(n)):
                    await envoyer_etape(salon, membre, n)
                    faits.append((uid, "etape", n))
            except (discord.Forbidden, discord.HTTPException) as erreur:
                journal.warning("Programme de %s (%s %s) : %s", uid, item.get("type"), n, erreur)
    return faits


def _echu(item: dict, maintenant) -> bool:
    try:
        return datetime.fromisoformat(str(item.get("quand"))) <= maintenant
    except ValueError:
        return True                                                     # date illisible : on ne la garde pas indéfiniment


def attente(fiche_p: dict):
    """(n, date) du compte qui attend ses 48 h, sinon None."""
    for item in fiche_p.get("programme") or []:
        if item.get("type") == "etape" and int(fiche_p.get("etape", 0)) == int(item.get("n") or 0) \
                and not (fiche_p.get("dates") or {}).get(str(item.get("n"))):
            try:
                return int(item["n"]), datetime.fromisoformat(str(item["quand"]))
            except (KeyError, ValueError):
                return None
    return None


async def _classeur_etat(uid: str, n: int) -> None:
    """25/09 : le classeur des logins suit le parcours — compte 1/2/3 validé → sa ligne passe à WARMUP, warm-up
    fini (étape 4) → les trois lignes passent à GOOD. Sans le classeur (ou sans la dépendance), rien."""
    marquer = _deps.get("marquer_etat")
    if marquer is None or n not in (1, 2, 3, 4):
        return
    comptes = (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(str(uid), {}) or {}).get("comptes") or []
    cibles = comptes[n - 1:n] if n <= 3 else comptes[:3]
    for h in cibles:
        try:
            await marquer(h, "WARMUP" if n <= 3 else "GOOD")
        except Exception as erreur:
            journal.warning("Classeur étape %s de %s : %s", n, uid, erreur)


async def boucle(client) -> None:
    """Chaque heure : le compte des jours de warm-up dans le salon (le matin), et l'ouverture automatique des Reels
    au jour WARMUP_JOURS + 1."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            try:
                await programme_du_jour(client)                         # 30/09 : « il peut publier », compte suivant à 48 h
            except Exception as erreur:                                 # noqa: BLE001
                journal.warning("Programme du parcours : %s", erreur)
            maintenant = _deps["heure_paris"]()
            if maintenant.hour >= paie_clics.CLICS_HEURE:
                d = _lire()
                for uid, fiche_p in list(d.items()):
                    if int(fiche_p.get("etape", 0)) != 4 or not fiche_p.get("dates", {}).get("4"):
                        continue
                    debut = datetime.fromisoformat(fiche_p["dates"]["4"]).date()
                    j = (maintenant.date() - debut).days + 1
                    if j == fiche_p.get("warmup_jour"):
                        continue
                    salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
                    if salon is None:
                        continue
                    fiche_p["warmup_jour"] = j
                    _ecrire(d)
                    if j > WARMUP_JOURS:
                        await salon.send(f"🎉 <@{uid}> tes {WARMUP_JOURS} jours de warm-up sont finis. Tu peux publier tes Reels !")
                        await valider_etape(salon, uid, 4, par="bot")
                    else:
                        texte_w = WARMUP_JOUR_TEXTE.format(j=j, jours=WARMUP_JOURS)
                        if not (_deps.get("deposer") and _deps["deposer"](salon.id, "warmup", texte_w)):
                            await _suite(salon, f"<@{uid}> " + texte_w)
                # 28/09 : relance courte — une étape (1 à 3, 5, 6) qui traîne depuis RELANCE_JOURS jours → une ligne, tous les RELANCE_JOURS jours
                for uid, fiche_p in list(d.items()):
                    n = int(fiche_p.get("etape", 0))
                    if n not in (1, 2, 3, 5, 6) or not fiche_p.get("dates", {}).get(str(n)):
                        continue
                    try:
                        depuis = (maintenant.date() - datetime.fromisoformat(fiche_p["dates"][str(n)]).date()).days
                    except ValueError:
                        continue
                    jour_s = maintenant.date().isoformat()
                    derniere = fiche_p.get("relance", "")
                    if depuis < RELANCE_JOURS or derniere == jour_s or (derniere and (maintenant.date() - datetime.fromisoformat(derniere).date()).days < RELANCE_JOURS):
                        continue
                    salon = client.get_channel(int(fiche_p.get("salon_id", 0) or 0))
                    if salon is None:
                        continue
                    fiche_p["relance"] = jour_s
                    _ecrire(d)
                    suite = prochaine_etape(salon.id)
                    texte_r = f"👉 <@{uid}> {suite}\n\nBloqué ? Écris ici." if suite else f"👉 <@{uid}> Étape {n} toujours en cours : `!etape` pour la revoir.\n\nBloqué ? Écris ici."
                    if not (_deps.get("deposer") and _deps["deposer"](salon.id, "relance", texte_r)):
                        await _suite(salon, texte_r)                    # 30/09 (GO n° 4) : remplace, n'empile pas
        except Exception as erreur:                                 # la boucle ne meurt jamais
            journal.warning("Boucle parcours : %s", erreur)
        await asyncio.sleep(3600)


# ------------------------------------------------------------------ mémoire
def memoire(uid: str) -> str:
    """Tout ce que le bot sait du clipper, en texte : pour le manager (`!memoire`) et pour l'assistant IA."""
    uid = str(uid)
    fiche_p = _lire().get(uid, {})
    equipes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {})
    onb = _deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(uid, {})
    membre = _deps["membre_par_id"](uid)
    nom = _prenom(membre) if membre else fiche_p.get("prenom", f"id {uid}")
    creatrice = fiche_p.get("creatrice") or equipes.get("creatrice") or onb.get("creatrice") or "aucune"
    n = int(fiche_p.get("etape", 0))
    titre = ETAPES[n]["titre"].format(jours=WARMUP_JOURS) if n in ETAPES else ("parcours non commencé" if n == 0 else "parcours terminé")
    date_etape = (fiche_p.get("dates") or {}).get(str(n), "")[:10]
    try:
        regime = paie_clics.regime(uid)
    except Exception:
        regime = "?"
    # 27/09 : le nombre de comptes CRÉÉS se déduit de l'étape (étape 1 = aucun, 2 = un, 3 = deux, 4 et plus = trois) —
    # l'assistant disait « continue sur tes deux autres comptes » à Daniella qui n'en avait qu'un.
    crees = 3 if n >= 4 else max(0, n - 1)
    lignes = [f"Clipper : {nom} (Discord {uid}) · créatrice : {creatrice} · signé le {str(equipes.get('date', ''))[:10] or '?'} "
              f"· paie : {regime}",
              f"Étape en cours : {titre}" + (f" (depuis le {date_etape})" if date_etape else "")
              + (f" · warm-up jour {fiche_p['warmup_jour']}/{WARMUP_JOURS}" if fiche_p.get("warmup_jour") else ""),
              f"Comptes créés : {crees} sur 3" + (" — les autres n'existent pas encore, n'en parle pas" if crees < 3 else "")]
    try:
        lignes.append(etat_des_comptes(uid))
    except Exception as erreur:                                     # noqa: BLE001
        journal.warning("État des comptes de %s : %s", uid, erreur)
    if onb.get("comptes"):
        lignes.append("Comptes Instagram : " + ", ".join(onb["comptes"]) + " (mots de passe déjà dans le salon, ne jamais les redonner)")
    if onb.get("lien"):
        lignes.append(f"Lien (en story à la une sur chaque compte) : {onb['lien']}")
    lignes.append("Drive : " + (onb["drive"] if onb.get("drive") else "pas encore prêt"))
    try:
        if paie_clics.actif():
            d = paie_clics._lire()
            lids = paie_clics.liens_de(d, uid)
            if lids:
                hier = paie_clics._aujourdhui() - timedelta(days=1)
                s7 = paie_clics.somme(d, lids, hier - timedelta(days=6), hier)
                lignes.append(f"Visites payables : {s7['payes']} sur 7 jours ({s7['payes'] / 7:.0f}/jour)")
    except Exception:
        pass
    for note in (fiche_p.get("notes") or [])[-5:]:
        lignes.append(f"Note du manager ({str(note.get('date', ''))[:10]}) : {note.get('texte', '')}")
    return "\n".join(lignes)


_derniers_etats = {}                                        # handle (minuscules) → état normalisé du classeur au dernier scan


def etat_des_comptes(uid: str, maintenant=None) -> str:
    """30/09 (Daniella, trois réponses contraires en une soirée : « publie demain », « ton compte 1 finit son warm-up demain
    aussi », « pas de story ni de publication ») : l'état de chaque compte, calculé, que l'assistant recopie au lieu de le
    déduire. Compte i créé à dates[« i_fait »] (sinon au début de l'étape i+1) ; warm-up WARMUP_JOURS × 24 h ; BAN d'après
    le dernier scan du classeur."""
    maintenant = maintenant or datetime.now(timezone.utc)
    fiche_p = _lire().get(str(uid), {})
    n = int(fiche_p.get("etape", 0))
    dates = fiche_p.get("dates") or {}
    comptes = (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(str(uid), {}) or {}).get("comptes") or []
    parts = []
    for i in (1, 2, 3):
        h = comptes[i - 1] if i - 1 < len(comptes) else ""
        nom = f"compte {i}" + (f" `{h}`" if h else "")
        if _derniers_etats.get(h.lower()) == "ban":
            parts.append(f"{nom} : BAN, il fait appel lui-même (Contester la décision, `!code`, selfie, son numéro ou sa pièce d'identité si demandés)")
            continue
        if i >= 2 and en_essai(fiche_p):
            parts.append(f"{nom} : fermé, période d'essai — il s'ouvre après {ESSAI_REELS} Reels en 72 h sur le compte 1")
            continue
        if n <= i and n < 7:
            parts.append(f"{nom} : pas encore créé")
            continue
        cree = dates.get(f"{i}_fait") or dates.get(str(i + 1)) or ""
        try:
            d = datetime.fromisoformat(cree)
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            d = None
        fin = d + timedelta(days=WARMUP_JOURS) if d else None
        if fin and maintenant < fin:
            parts.append(f"{nom} : WARM-UP jusqu'au {_date_fr(fin)}, pas de Reel, 1 story sans lien par jour")
        else:
            parts.append(f"{nom} : PUBLIE, 2 Reels et 1 story par jour")
    return "État de chaque compte (fait foi) : " + " ; ".join(parts)


def _date_fr(d) -> str:
    from zoneinfo import ZoneInfo
    d = d.astimezone(ZoneInfo("Europe/Paris"))
    return d.strftime("%d/%m à ") + f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "")


def _prenom(membre) -> str:
    """Prénom d'un membre au pseudo « Prénom - Créatrice » (25/09) : avant le séparateur, puis premier mot."""
    nom = (getattr(membre, "display_name", "") or "").strip()
    for sep in (" - ", " – ", " — ", " | ", " · "):
        if sep in nom:
            nom = nom.split(sep, 1)[0].strip()
            break
    return nom.split()[0] if nom.split() else nom


PROCHAINES = {1: "ouvre ton compte 1, `{compte1}` (création ou connexion, c'est dans l'étape). Clique ✅ quand c'est fait.",
              2: "crée ton compte 2, `{compte2}`. Clique ✅ quand c'est fait.",
              3: "crée ton compte 3, `{compte3}`. Clique ✅ quand c'est fait.",
              4: "compte 3 en warm-up (Reels, likes, 1 story, pas de Reel) ; comptes 1 et 2 : 2 Reels et 1 story chacun.",
              5: "publie un Reel de ton Drive sur `{compte1}`, `{compte2}` et `{compte3}`. Clique ✅ quand c'est fait.",
              6: "mets ton lien une seule fois, en story à la une, sur chaque compte. Jamais en bio. Clique ✅ quand c'est fait.",
              7: "2 Reels sur chacun de tes 3 comptes, 1 story avec le widget vers ta story à la une."}


def prochaine_etape(salon_id) -> str:
    """La ligne « 👉 Aujourd'hui » du message du matin, d'après l'étape du clipper dont c'est le salon."""
    for uid, fiche_p in _lire().items():
        if str(fiche_p.get("salon_id")) != str(salon_id):
            continue
        n = int(fiche_p.get("etape", 0))
        if n not in PROCHAINES:
            return "" if n else "attends ta créatrice, ton manager te l'attribue."
        comptes = (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(uid, {}) or {}).get("comptes") or []
        c = {f"compte{i + 1}": (comptes[i] if i < len(comptes) else "…") for i in range(3)}
        a = attente(fiche_p)
        if a:                                                           # 30/09 : le compte suivant attend ses 48 h
            return f"ton compte {a[0]} arrive ici le {_date_fr(a[1])}. Tes comptes prêts : 2 Reels par jour après leurs 24 h de warm-up."
        if n == 2 and en_essai(fiche_p):                                # 30/09 : période d'essai
            return (f"publie tes Reels sur `{c['compte1']}` : {ESSAI_REELS} en 72 h, et tes comptes 2 et 3 s'ouvrent.")
        return PROCHAINES[n].format(**c)
    return ""


def _etats_comptes(uid, etats_par_handle: dict) -> list:
    """[(handle, état normalisé du classeur)] des comptes livrés au clipper, dans l'ordre compte 1, 2, privé."""
    comptes = (_deps["lire_json"](_deps["FICHIER_ONBOARDING"], {}).get("clippers", {}).get(str(uid), {}) or {}).get("comptes") or []
    return [(h, _norm(etats_par_handle.get(h.lower(), "") or "")) for h in comptes]


def etape_selon_classeur(etats: list) -> int:
    """26/09 : l'étape est celle du prochain compte à créer. 0 compte créé → 1, 1 → 2, 2 → 3 ; les trois créés → 4 (warm-up) ;
    les deux comptes de croissance GOOD → 7 (routine). Daniella (26/09, soir) : un seul compte créé la mettait au warm-up."""
    if not etats:
        return 7
    e = [x for _, x in etats]
    crees = [x for x in e if x not in ("a creer", "à créer", "")]
    if len(crees) < min(3, len(e)):
        return 1 + len(crees)
    if len(e) >= 2 and all(x == "good" for x in e[:2]):
        return 7
    return 4


def oublier(uid: str) -> bool:
    """Retire la fiche de parcours d'un clipper (salon perso supprimé le 26/09) : plus de warm-up ni d'étape postés nulle part."""
    d = _lire()
    if str(uid) not in d:
        return False
    d.pop(str(uid), None)
    _ecrire(d)
    return True


async def forcer_etape(salon, membre, creatrice: str, n: int) -> None:
    """Pose l'étape n (date du jour, utile au compte des jours de warm-up) et l'envoie dans le salon."""
    d = _lire()
    uid = str(membre.id)
    fiche_p = d.setdefault(uid, {"prenom": _prenom(membre), "creatrice": creatrice, "salon_id": str(salon.id), "etape": 0,
                                 "dates": {}, "notes": []})
    fiche_p.update({"etape": n, "salon_id": str(salon.id), "creatrice": creatrice or fiche_p.get("creatrice", "")})
    fiche_p.setdefault("dates", {})[str(n)] = _maintenant()
    fiche_p.pop("warmup_jour", None)
    _ecrire(d)
    await envoyer_etape(salon, membre, n)


async def demarrer_selon_classeur(salon, membre, creatrice: str, etats_par_handle: dict) -> int:
    """Pour un clipper déjà en place : l'étape de départ dépend de l'état réel de ses comptes dans le classeur."""
    n = etape_selon_classeur(_etats_comptes(membre.id, etats_par_handle))
    if n == 1:
        await demarrer_parcours(salon, membre, creatrice)
    elif n == 7:
        await demarrer_routine(salon, membre, creatrice)
    else:
        await forcer_etape(salon, membre, creatrice, n)
    return n


async def reconcilier(client, etats_par_handle: dict, publies=None, reels_72h=None) -> list:
    """Après chaque scan du classeur : un compte créé sur Instagram valide tout seul l'étape 1, 2 ou 3 ; un clipper mis
    en routine par erreur alors que ses comptes sont à créer ou en warm-up est remis à la bonne étape (une seule fois)."""
    faits = []
    _derniers_etats.clear()
    _derniers_etats.update({str(h).lower(): _norm(e or "") for h, e in (etats_par_handle or {}).items()})
    for uid, fiche_p in list(_lire().items()):
        n = int(fiche_p.get("etape", 0))
        salon = client.get_channel(int(fiche_p.get("salon_id") or 0)) if fiche_p.get("salon_id") else None
        membre = _deps["membre_par_id"](uid)
        if salon is None or membre is None:
            continue
        etats = _etats_comptes(uid, etats_par_handle)
        if not etats:
            continue
        try:
            if n == 7 and not fiche_p.get("dates", {}).get("1_fait") and not fiche_p.get("reconcilie"):
                cible = etape_selon_classeur(etats)
                d = _lire()
                d[uid]["reconcilie"] = _maintenant()
                _ecrire(d)
                if cible != 7:
                    await forcer_etape(salon, membre, fiche_p.get("creatrice", ""), cible)
                    faits.append((_prenom(membre), 7, cible))
            elif n == 2 and en_essai(fiche_p):
                # 30/09 (période d'essai) : 5 Reels en 72 h sur le compte 1 → le compte 2 s'ouvre
                nb = int((reels_72h or {}).get(str(etats[0][0]).lower(), 0)) if etats else 0
                if nb >= ESSAI_REELS:
                    d = _lire()
                    d[uid]["essai"]["fini"] = _maintenant()
                    _ecrire(d)
                    await salon.send(f"{membre.mention} ✅ **Essai réussi : {nb} Reels en 72 h !** Ton compte 2 est juste en dessous.")
                    await envoyer_etape(salon, membre, 2)
                    faits.append((_prenom(membre), "essai", 2))
            elif n in (1, 2, 3) and n - 1 < len(etats):
                h, e = etats[n - 1]
                if e and e not in ("a creer", "à créer") and await valider_etape(salon, uid, n, par="classeur"):
                    faits.append((_prenom(membre), n, n + 1))
            elif n == 5 and publies and any(str(h).lower() in publies for h, _ in etats):
                # 28/09 (GO n° 4) : le premier Reel vu par le scan ferme l'étape 5 tout seul
                if await valider_etape(salon, uid, 5, par="scan"):
                    faits.append((_prenom(membre), 5, 6))
            elif n == 4 and not fiche_p.get("corrige_4"):
                # 26/09 (Daniella) : mise au warm-up avec un seul compte créé → retour à l'étape du prochain compte, une seule fois
                cible = etape_selon_classeur(etats)
                if cible < 4:
                    d = _lire()
                    d[uid]["corrige_4"] = _maintenant()
                    _ecrire(d)
                    await forcer_etape(salon, membre, fiche_p.get("creatrice", ""), cible)
                    faits.append((_prenom(membre), 4, cible))
        except Exception as erreur:                                      # noqa: BLE001
            journal.warning("Réconciliation du parcours de %s : %s", uid, erreur)
    if faits:
        journal.info("Parcours réconciliés avec le classeur : %s", faits)
    return faits


def contexte_llm(uid: str) -> str:
    """Le bloc de contexte ajouté à chaque question posée dans le salon perso : le bot y est le manager."""
    return ("[Salon perso : ici tu es l'ASSISTANT du clipper au quotidien (pas son manager). Tu parles comme à un élève de collège : phrases de "
            "10 mots maximum, mots simples, une action par ligne, jamais de parenthèses. Réponds court, une action à la fois, tutoie, "
            "guide-le selon son étape en cours, renvoie aux fiches du forum et aux commandes `!code` (son code de "
            "vérification), `!mesclics` (ses visites). Les comptes se créent ici, guidés par le parcours : plus de créneau "
            "lundi/mercredi/vendredi, plus de contrat, plus de distinction France/International. Ne redonne jamais un mot "
            "de passe. Paie : 0,05 $ par visite francophone réelle sur son lien, tous les 15 jours, USDC ou virement. "
            "Règle des 48 h (29/09) : un compte tous les 48 h, jamais plus vite (compte 1, 48 h, compte 2, 48 h, compte 3), 24 h de warm-up sur chaque compte "
            "après sa création (Reels, likes, abonnements, 1 story sans lien, zéro Reel), puis CE compte publie 2 Reels et 1 story par jour, "
            "sans attendre les autres — ne dis jamais « une semaine de warm-up » ni « dans 7 jours ». Période d'essai (30/09) : un "
            f"nouveau clipper n'a que son compte 1 ; ses comptes 2 et 3 s'ouvrent tout seuls après {ESSAI_REELS} Reels publiés en "
            "72 h sur le compte 1, jamais avant, jamais à la demande. La ligne « État de chaque "
            "compte » de la mémoire FAIT FOI : tu ne la contredis jamais, ni le message d'étape posté dans le salon. "
            "La story du jour se prend dans le dossier Photos de son Drive (une photo, ou une courte vidéo du dossier Reels) ; "
            "tu n'inventes jamais un dossier (« Stories », « À publier ») qui n'est pas dans le Drive. Il demande OÙ prendre "
            "la story : tu réponds au où, pas au widget. Un compte BAN ne change rien pour les autres : ils continuent. "
            "Un compte banni (30/09) : il fait appel lui-même, tout de suite (« Contester la décision », code avec `!code`, selfie vidéo, son "
            "numéro ou sa pièce d'identité si Instagram les demande, jamais ceux d'un autre, jamais sa pièce d'identité dans Discord) ; "
            "tu ne promets jamais un compte neuf "
            "ni une date (« demain ») : c'est Gaëtan qui le remplace. "
            "Le lien (28/09) : une seule fois, dans une story à la une sur chaque compte, et on n'y touche plus ; jamais en bio, "
            "jamais d'@ en bio (ça fait des bans), jamais dans un Reel ; chaque jour une story avec le widget du profil vers la story "
            "à la une. Trois comptes de croissance, plus de compte privé (28/09) : chaque compte fait ses 24 h de warm-up après sa "
            "création puis publie, sans attendre les autres. Un compte « qui existe déjà » (rendu par un ancien) : on s'y "
            "connecte, le code de connexion arrive dans le salon. Le Drive s'ouvre par son lien, jamais besoin d'une adresse e-mail. "
            "Quand il dit qu'une étape est faite, dis-lui de cliquer le bouton ✅ sous le message de l'étape, ou d'écrire "
            "`!etape` pour la revoir. Appelle-le par son prénom (celui de la mémoire), jamais par celui de la créatrice. "
            "Trois lignes maximum. La ligne « 👉 Prochaine étape : … » seulement si elle dit autre chose que l'étape déjà "
            "affichée dans le salon avec son bouton. Aucune question inutile (modèle de téléphone, « dis-moi quand c'est "
            "fait »). Tu ne parles que des comptes CRÉÉS d'après la mémoire : jamais « tes deux autres comptes » s'ils "
            "n'existent pas encore. Tu ne donnes jamais la cause d'un blocage, seulement la marche à suivre ; « déconnecté, "
            "mot de passe modifié » = se reconnecter avec le mot de passe du message de comptes puis `!code` ; s'il ne marche plus, "
            "WhatsApp Gaëtan, jamais « Mot de passe oublié ». `!code` ne donne QUE les codes reçus par e-mail (création, "
            "connexion, appel), jamais ceux qui changent l'e-mail, le mot de passe ou le numéro. Instagram demande un NUMÉRO de téléphone : il met LE SIEN et reçoit le SMS (décision du 26/09), ce numéro ne "
            "sert qu'à ses 3 comptes. Instagram demande un SELFIE VIDÉO : il le fait lui-même, avec son visage, c'est normal. "
            "Jamais de « compte prêt à l'emploi », jamais « ton manager a une autre solution » : si tu ne sais pas, renvoie vers "
            "Gaëtan sur WhatsApp (le lien est dans tes règles). Ne recopie jamais la ligne [Contexte : …].]\n"
            "[Mémoire du clipper]\n" + memoire(uid))


# ------------------------------------------------------------------ commandes manager
async def commande_staff(message, texte: str) -> bool:
    mots = texte.split()
    if not mots or mots[0].lower() not in ("!etape", "!note", "!memoire", "!mémoire"):
        return False
    est_staff = _deps.get("est_staff")
    if len(mots) == 1 and mots[0].lower() == "!etape" and est_staff is not None and not est_staff(message.author):
        # 25/09 (Daniella) : le clipper tape `!etape` seul dans son salon → je lui renvoie son étape en cours
        uid = str(message.author.id)
        fiche_p = _lire().get(uid, {})
        n = int(fiche_p.get("etape", 0))
        if n not in ETAPES:
            await message.reply("Ton parcours n'a pas encore commencé. Ton manager le lance." if n == 0
                                else "Ton parcours est fini. Écris `!mesclics` pour voir tes visites.")
            return True
        await envoyer_etape(message.channel, message.author, n)
        return True
    membre = message.mentions[0] if message.mentions else None
    reste = [m for m in mots[1:] if not m.startswith("<@")]
    if membre is None and reste and _deps.get("chercher_membre"):    # « !etape Gaëtan 1 » sans vraie mention Discord
        membre = _deps["chercher_membre"](reste[0].lstrip("@"))
        if membre is not None:
            reste = reste[1:]
    if membre is None:
        await message.reply("Format : `!etape @clipper [n]` (renvoyer ou forcer une étape) · `!note @clipper texte` "
                            "(mémoire du bot sur lui) · `!memoire @clipper` (ce que le bot sait). Le @ doit être une vraie "
                            "mention, ou tape le prénom tel quel.")
        return True
    uid = str(membre.id)
    if mots[0].lower() in ("!memoire", "!mémoire"):
        await _deps["envoyer_long"](message, [f"🧠 **Mémoire de {membre.display_name}**"] + memoire(uid).split("\n"))
        return True
    if mots[0].lower() == "!note":
        if not reste:
            await message.reply("Format : `!note @clipper texte` — ex. `!note @Eddy préfère Edits, a un iPhone 11, absent le 3/10`.")
            return True
        d = _lire()
        fiche_p = d.setdefault(uid, {"prenom": _prenom(membre), "creatrice": "", "salon_id": "", "etape": 0, "dates": {}, "notes": []})
        fiche_p.setdefault("notes", []).append({"date": _maintenant(), "par": str(message.author.id), "texte": " ".join(reste)[:400]})
        fiche_p["notes"] = fiche_p["notes"][-30:]
        _ecrire(d)
        await message.reply(f"🧠 Noté pour {membre.display_name} ({len(fiche_p['notes'])} note(s)). Le bot s'en sert dans son salon.")
        return True
    # !etape @clipper [n]
    salon = _deps["salon_perso"](uid)
    if salon is None:
        await message.reply(f"{membre.display_name} n'a pas de salon perso : `!creatrice @{membre.display_name} Prénom` d'abord.")
        return True
    d = _lire()
    fiche_p = d.get(uid) or {}
    n = next((int(m) for m in reste if m.isdigit() and int(m) in ETAPES), int(fiche_p.get("etape", 0)) or 1)
    if not fiche_p:
        equipes = _deps["lire_json"](_deps["FICHIER_EQUIPES"], {}).get(uid, {})
        d[uid] = {"prenom": _prenom(membre), "creatrice": equipes.get("creatrice", ""), "salon_id": str(salon.id),
                  "etape": 0, "dates": {}, "notes": []}
        _ecrire(d)
    await envoyer_etape(salon, membre, n)
    await message.reply(f"📍 Étape {n} envoyée à {membre.display_name} dans <#{salon.id}>.")
    return True
