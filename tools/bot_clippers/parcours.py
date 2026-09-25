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
WARMUP_JOURS = int(os.environ.get("WARMUP_JOURS", "7") or 7)
LIEN_REPORTING = os.environ.get("LIEN_REPORTING", "https://forms.gle/uhPewryox7R4jifv5").strip()   # formulaire du dimanche

ETAPES = {
    1: {"titre": "Étape 1 · Crée ton compte 1 (croissance)", "fiche": "1", "bouton": "✅ Compte 1 créé", "salons": ["info"],
        "texte": ("Tu as maintenant accès à **{creatrice}** : ses infos, ses comptes Instagram et sa bio modèle sont dans {info}. "
                  "Prends de préférence un **iPhone dédié** à cette activité, sans ton compte Instagram perso dessus.\n\n"
                  "**Compte 1 : `{compte1}`**\n"
                  "1. Ouvre Instagram → **Créer un compte** → **avec un e-mail**.\n"
                  "2. Colle l'e-mail : `{mail1}`\n"
                  "3. **Recevoir le code** → reviens ici et tape `!code` : je te le donne.\n"
                  "4. Entre le code, puis le **mot de passe** donné plus haut dans ce salon (jamais un autre).\n"
                  "5. Nom, date de naissance adulte, **jamais ton numéro de téléphone**.\n"
                  "6. Photo de profil + bio : inspire-toi des comptes de {creatrice} dans {info}. Pas de lien, pas de ville.\n\n"
                  "Un seul compte aujourd'hui. Quand c'est fait, clique sur le bouton, on passe au compte 2 demain.")},
    2: {"titre": "Étape 2 · Crée ton compte 2 (croissance)", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": ["info"],
        "texte": ("Même méthode que le compte 1, sur le **même téléphone**, en ajoutant un compte (pas en te déconnectant).\n\n"
                  "**Compte 2 : `{compte2}`** · e-mail : `{mail2}`\n"
                  "Créer un compte → avec un e-mail → `!code` ici pour le code → mot de passe donné plus haut → photo + bio "
                  "différentes du compte 1.\n\n"
                  "⚠️ Si Instagram crée le compte **sans** te demander d'e-mail, il le relie au compte 1 : arrête, écris-le ici.")},
    3: {"titre": "Étape 3 · Crée ton compte privé", "fiche": "1", "bouton": "✅ Compte privé créé", "salons": ["info"],
        "texte": ("Le compte privé ne publie pas : c'est lui qui portera ton lien, plus tard.\n\n"
                  "**Compte 3 : `{compte3}`** · e-mail : `{mail3}`\n"
                  "Créer un compte → avec un e-mail → `!code` → mot de passe → **compte privé** (cadenas dans les réglages).\n"
                  "Bio : le prénom de {creatrice} et une phrase douce. **Aucun lien pour l'instant** : je te dirai quand le poser.\n\n"
                  "Quand c'est fait, clique sur le bouton : le warm-up commence.")},
    4: {"titre": "Étape 4 · Le warm-up, {jours} jours (Fiche 2)", "fiche": "2", "bouton": "✅ J'ai fini mes {jours} jours", "salons": ["ressources"],
        "texte": ("Pendant {jours} jours, tes comptes apprennent à Instagram qui tu es. **Pas de Reel avant le jour {jour_suivant}.**\n\n"
                  "Chaque jour, sur chaque compte :\n"
                  "• 10 minutes à regarder des Reels de la niche (la liste des créatrices à suivre est dans {ressources})\n"
                  "• 5 likes, 2 abonnements à des comptes de la niche, 1 ou 2 commentaires courts\n"
                  "• 1 story sans lien (lifestyle, sondage)\n\n"
                  "Je te compte les jours ici chaque matin. Au jour {jour_suivant}, je t'ouvre les Reels.")},
    5: {"titre": "Étape 5 · Ton premier Reel (Fiche 3)", "fiche": "3", "bouton": "✅ Premier Reel publié", "salons": ["ressources"],
        "texte": ("Tes rushs sont dans ton Drive : {drive}\n\n"
                  "1. Télécharge un rush, ouvre **Edits** (l'appli gratuite d'Instagram).\n"
                  "2. Coupe le début : le **hook** dans la première seconde, durée proche du rush.\n"
                  "3. Sous-titres lisibles, une miniature claire.\n"
                  "4. Une caption simple et soft : des exemples dans {ressources}.\n"
                  "5. Publie sur `{compte1}`, puis pareil sur `{compte2}`.\n\n"
                  "Quand ton premier Reel est en ligne, clique sur le bouton.")},
    6: {"titre": "Étape 6 · Pose ton lien en bio (Fiche 4)", "fiche": "4", "bouton": "✅ Lien posé", "salons": [],
        "texte": ("**Ton lien** (le même pour tout) : {lien}\n\n"
                  "1. Dans la bio de `{compte3}` (le privé) : colle ce lien.\n"
                  "2. Dans la bio de `{compte1}` et de `{compte2}` : écris **@{compte3}**, rien d'autre. Jamais le lien sur un compte qui publie.\n"
                  "3. Tape `!mesclics` ici : c'est ce lien qui compte tes visites, payées le 5 et le 20.\n\n"
                  "Quand c'est fait, clique sur le bouton.")},
    7: {"titre": "🎉 Parcours terminé · Ta routine", "fiche": "4", "bouton": "", "salons": ["reporting"],
        "texte": ("Chaque jour : **2 Reels sur `{compte1}`, 2 Reels sur `{compte2}`**, 1 story, quelques commentaires. "
                  "Chaque matin je t'écris tes visites de la veille ici. Chaque dimanche, ton reporting : le formulaire {lien_reporting}, "
                  "et les consignes dans {reporting}.\n\n"
                  "Je reste ici tous les jours : une question sur un compte, un code, un Reel, ta paie, écris-la ici. "
                  "Ton manager lit ce salon aussi.")},
}
WARMUP_JOUR_TEXTE = ("🔥 **Warm-up, jour {j}/{jours}** — aujourd'hui sur chaque compte : 10 minutes de Reels de la niche, "
                     "5 likes, 2 abonnements, 1 story sans lien. Pas de Reel.")


def configurer(deps: dict):
    global _deps
    _deps = deps


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
    for i in range(3):
        h = ordonnes[i] if i < len(ordonnes) else "?"
        ctx[f"compte{i + 1}"] = h
        ctx[f"mail{i + 1}"] = mails.get(h, "(dans ton message de comptes plus haut)")
    ctx["lien"] = onb.get("lien") or "(ton manager te le donne avec `!lien`)"
    ctx["drive"] = onb.get("drive") or "(pas encore partagé : envoie-moi ton adresse Gmail ici)"
    creatrice = ctx["creatrice"]
    info = _salon_info(guild, creatrice) if guild is not None else None
    ctx["info"] = f"<#{info.id}>" if info is not None else f"le salon d'infos de {creatrice}"
    res = _salon_nom(guild, "ressources") if guild is not None else None
    ctx["ressources"] = f"<#{res.id}>" if res is not None else "#ressources"
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
    fiche_p.setdefault("dates", {})[f"{n}_fait"] = _maintenant()
    fiche_p["etape"] = n + 1
    _ecrire(d)
    mid = (fiche_p.get("messages") or {}).get(str(n))
    if mid:
        try:
            ancien = await salon.fetch_message(int(mid))
            await ancien.edit(view=None)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass
    membre = _deps["membre_par_id"](uid)
    if membre is None:
        return True
    if n + 1 in ETAPES:
        await envoyer_etape(salon, membre, n + 1)
    return True


async def boucle(client) -> None:
    """Chaque heure : le compte des jours de warm-up dans le salon (le matin), et l'ouverture automatique des Reels
    au jour WARMUP_JOURS + 1."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
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
                        await salon.send(f"🎉 <@{uid}> tes {WARMUP_JOURS} jours de warm-up sont faits : place aux Reels.")
                        await valider_etape(salon, uid, 4, par="bot")
                    else:
                        await salon.send(f"<@{uid}> " + WARMUP_JOUR_TEXTE.format(j=j, jours=WARMUP_JOURS))
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
    lignes = [f"Clipper : {nom} (Discord {uid}) · créatrice : {creatrice} · signé le {str(equipes.get('date', ''))[:10] or '?'} "
              f"· paie : {regime}",
              f"Étape en cours : {titre}" + (f" (depuis le {date_etape})" if date_etape else "")
              + (f" · warm-up jour {fiche_p['warmup_jour']}/{WARMUP_JOURS}" if fiche_p.get("warmup_jour") else "")]
    if onb.get("comptes"):
        lignes.append("Comptes Instagram : " + ", ".join(onb["comptes"]) + " (mots de passe déjà dans le salon, ne jamais les redonner)")
    if onb.get("lien"):
        lignes.append(f"Lien en bio : {onb['lien']}")
    lignes.append("Drive : " + (onb["drive"] if onb.get("drive") else "pas encore partagé (il faut son adresse Gmail)"))
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


def _prenom(membre) -> str:
    """Prénom d'un membre au pseudo « Prénom - Créatrice » (25/09) : avant le séparateur, puis premier mot."""
    nom = (getattr(membre, "display_name", "") or "").strip()
    for sep in (" - ", " – ", " — ", " | ", " · "):
        if sep in nom:
            nom = nom.split(sep, 1)[0].strip()
            break
    return nom.split()[0] if nom.split() else nom


def contexte_llm(uid: str) -> str:
    """Le bloc de contexte ajouté à chaque question posée dans le salon perso : le bot y est le manager."""
    return ("[Salon perso : ici tu es le MANAGER du clipper au quotidien. Réponds court, une action à la fois, tutoie, "
            "guide-le selon son étape en cours, renvoie aux fiches du forum et aux commandes `!code` (son code de "
            "vérification), `!mesclics` (ses visites). Les comptes se créent ici, guidés par le parcours : plus de créneau "
            "lundi/mercredi/vendredi, plus de contrat, plus de distinction France/International. Ne redonne jamais un mot "
            "de passe. Paie : 0,05 $ par visite francophone réelle sur son lien, le 5 et le 20, USDC ou virement. "
            "Règle des 24 h : compte 1 aujourd'hui, compte 2 demain, compte privé après-demain, jamais deux comptes le "
            "même jour ; le warm-up de chaque compte commence dès sa création (interactions, zéro publication) et le "
            f"premier Reel attend les {WARMUP_JOURS} jours de l'étape 4 — ne dis jamais « dans 7 jours on crée le compte 2 ». "
            "Quand il dit qu'une étape est faite, dis-lui de cliquer le bouton ✅ sous le message de l'étape, ou d'écrire "
            "`!etape` pour la revoir. Appelle-le par son prénom (celui de la mémoire), jamais par celui de la créatrice.]\n"
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
            await message.reply("Ton parcours n'a pas encore démarré ici : ton manager le lance avec `!creatrice`." if n == 0
                                else "Ton parcours est terminé : tu es en routine, `!mesclics` pour tes visites.")
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
