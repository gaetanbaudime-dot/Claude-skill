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
    # 26/09 (Gaëtan : « hyper long, trop d'informations pour les clippeurs ») : 5 lignes par étape, une action par ligne.
    1: {"titre": "Étape 1 · Crée ton compte 1", "fiche": "1", "bouton": "✅ Compte 1 créé", "salons": ["info"],
        "texte": ("**Compte 1 : `{compte1}`**\n"
                  "1. Instagram → Créer un compte → avec un e-mail : `{mail1}`\n"
                  "2. Code demandé ? Écris `!code` ici.\n"
                  "3. Mot de passe : celui du message des comptes.\n"
                  "4. Numéro demandé ? Mets le tien. Date de naissance : la vraie.\n"
                  "5. Photo + bio sage, comme les comptes dans {info}. Pas de lien.\n\n"
                  "Fini ? Appuie sur le bouton. Compte 2 demain.")},
    2: {"titre": "Étape 2 · Crée ton compte 2", "fiche": "1", "bouton": "✅ Compte 2 créé", "salons": ["info"],
        "texte": ("**Compte 2 : `{compte2}`** · e-mail `{mail2}`\n"
                  "Même chose que le compte 1, sur le même téléphone : tu ajoutes un compte, sans te déconnecter.\n"
                  "Photo et bio différentes du compte 1.\n\n"
                  "⚠️ Instagram ne demande pas d'e-mail ? Arrête et écris-le ici.")},
    3: {"titre": "Étape 3 · Crée ton compte privé", "fiche": "1", "bouton": "✅ Compte privé créé", "salons": ["info"],
        "texte": ("**Compte 3 : `{compte3}`** · e-mail `{mail3}` · ton compte secret, il ne publie pas.\n"
                  "1. Crée-le comme les autres.\n"
                  "2. Réglages → compte **privé** (le cadenas).\n"
                  "3. Bio : le prénom de {creatrice} + une phrase gentille. Pas de lien, je te dirai quand.\n\n"
                  "Fini ? Appuie sur le bouton. Ensuite, on chauffe les comptes.")},
    4: {"titre": "Étape 4 · Le warm-up : {jours} jours (Fiche 2)", "fiche": "2", "bouton": "✅ Mes {jours} jours sont finis", "salons": ["ressources"],
        "texte": ("{jours} jours sans publier : Instagram apprend qui tu es.\n"
                  "Chaque jour, sur chaque compte : 10 min de Reels de créatrices françaises ({ressources}), 5 likes, "
                  "2 abonnements, 1 ou 2 commentaires, 1 story sans lien.\n\n"
                  "Chaque matin, je te dis à quel jour tu es. Au jour {jour_suivant}, on publie.")},
    5: {"titre": "Étape 5 · Ton premier Reel (Fiche 3)", "fiche": "3", "bouton": "✅ Premier Reel publié", "salons": ["ressources"],
        "texte": ("Tes vidéos : {drive}\n"
                  "1. Télécharge une vidéo, ouvre **Edits** (l'appli gratuite d'Instagram).\n"
                  "2. Coupe le début : la première seconde doit accrocher.\n"
                  "3. Sous-titres lisibles, couverture claire, petit texte (exemples dans {ressources}).\n"
                  "4. Publie sur `{compte1}`, puis sur `{compte2}`.\n\n"
                  "Premier Reel en ligne ? Appuie sur le bouton.")},
    6: {"titre": "Étape 6 · Mets ton lien (Fiche 4)", "fiche": "4", "bouton": "✅ Lien mis", "salons": [],
        "texte": ("**Ton lien** : {lien}\n"
                  "1. Sur `{compte3}`, le privé : le lien dans la bio.\n"
                  "2. Sur `{compte1}` et `{compte2}` : seulement **@{compte3}** dans la bio. Jamais le lien.\n"
                  "3. `!mesclics` ici : ce lien compte tes visites, donc ta paie, le 5 et le 20.\n\n"
                  "Fini ? Appuie sur le bouton.")},
    7: {"titre": "🎉 Bravo, tu as fini · Ta routine de chaque jour", "fiche": "4", "bouton": "", "salons": ["reporting"],
        "texte": ("Chaque jour : 2 Reels sur `{compte1}`, 2 sur `{compte2}`, 1 story, quelques commentaires.\n"
                  "Chaque matin, tes visites d'hier ici. Chaque dimanche, le formulaire : {lien_reporting} ({reporting}).\n\n"
                  "Une question ? Écris ici.")},
}
WARMUP_JOUR_TEXTE = ("🔥 **Warm-up : jour {j} sur {jours}.** Aujourd'hui, sur chaque compte : 10 minutes de Reels, "
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
    await _classeur_etat(uid, n)
    membre = _deps["membre_par_id"](uid)
    if membre is None:
        return True
    if n + 1 in ETAPES:
        await envoyer_etape(salon, membre, n + 1)
    return True


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
                            await salon.send(f"<@{uid}> " + texte_w)
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


PROCHAINES = {1: "crée ton compte 1, `{compte1}`. Clique ✅ dans le message d'étape quand c'est fait.",
              2: "crée ton compte 2, `{compte2}`. Clique ✅ quand c'est fait.",
              3: "crée ton compte privé, `{compte3}`. Clique ✅ quand c'est fait.",
              4: "warm-up : 10 minutes de Reels, 5 likes, 2 abonnements, 1 story sur chaque compte. Pas de Reel.",
              5: "monte et publie ton premier Reel sur `{compte1}` puis `{compte2}`. Clique ✅ quand c'est fait.",
              6: "mets ton lien dans la bio de `{compte3}`, et @{compte3} dans la bio des deux autres. Clique ✅ quand c'est fait.",
              7: "2 Reels sur `{compte1}`, 2 Reels sur `{compte2}`, 1 story."}


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


async def reconcilier(client, etats_par_handle: dict) -> list:
    """Après chaque scan du classeur : un compte créé sur Instagram valide tout seul l'étape 1, 2 ou 3 ; un clipper mis
    en routine par erreur alors que ses comptes sont à créer ou en warm-up est remis à la bonne étape (une seule fois)."""
    faits = []
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
            elif n in (1, 2, 3) and n - 1 < len(etats):
                h, e = etats[n - 1]
                if e and e not in ("a creer", "à créer") and await valider_etape(salon, uid, n, par="classeur"):
                    faits.append((_prenom(membre), n, n + 1))
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
    return ("[Salon perso : ici tu es le MANAGER du clipper au quotidien. Tu parles comme à un élève de collège : phrases de "
            "10 mots maximum, mots simples, une action par ligne, jamais de parenthèses. Réponds court, une action à la fois, tutoie, "
            "guide-le selon son étape en cours, renvoie aux fiches du forum et aux commandes `!code` (son code de "
            "vérification), `!mesclics` (ses visites). Les comptes se créent ici, guidés par le parcours : plus de créneau "
            "lundi/mercredi/vendredi, plus de contrat, plus de distinction France/International. Ne redonne jamais un mot "
            "de passe. Paie : 0,05 $ par visite francophone réelle sur son lien, le 5 et le 20, USDC ou virement. "
            "Règle des 24 h : compte 1 aujourd'hui, compte 2 demain, compte privé après-demain, jamais deux comptes le "
            "même jour ; le warm-up de chaque compte commence dès sa création (interactions, zéro publication) et le "
            f"premier Reel attend les {WARMUP_JOURS} jours de l'étape 4 — ne dis jamais « dans 7 jours on crée le compte 2 ». "
            "Quand il dit qu'une étape est faite, dis-lui de cliquer le bouton ✅ sous le message de l'étape, ou d'écrire "
            "`!etape` pour la revoir. Appelle-le par son prénom (celui de la mémoire), jamais par celui de la créatrice. "
            "Trois lignes maximum, et finis toujours par « 👉 Prochaine étape : … ». `!code` ne donne QUE les codes reçus par "
            "e-mail. Instagram demande un NUMÉRO de téléphone : il met LE SIEN et reçoit le SMS (décision du 26/09), ce numéro ne "
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
