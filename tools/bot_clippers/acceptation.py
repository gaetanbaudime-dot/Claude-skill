"""J'ACCEPTE devient une case cochée (27/09, décision de Gaëtan : « Applique juste ça »).

AVANT : test validé → les 5 règles en MP → le candidat doit écrire « J'ACCEPTE » → rôle. Le 27/09, 21 validés
étaient bloqués sur ce mot. APRÈS : les 5 règles sont une case cochée sur le formulaire du site (obligatoire), donc
un candidat validé a déjà accepté : son accès s'ouvre à la validation, sans rien écrire. Pour ceux qui sont passés
avant la case (ou par invitation), le message des règles porte un BOUTON « ✅ J'accepte, on y va » — une case cochée,
pas un mot à recopier — et le mot J'ACCEPTE tapé marche toujours. Au démarrage, une fois par personne, les validés
encore en attente reçoivent les règles avec le bouton."""

from datetime import datetime, timezone

import discord

journal = __import__("logging").getLogger("bot_clippers")
_deps = {}


def configurer(deps: dict):
    """deps : accepter (async (uid, via) -> texte), lire_json, ecrire_json, FICHIER_PIPELINE, membre_par_id, est_signe (uid -> bool).
    09/10, facultatif : repli (async (membre) -> bool), le seul message après une acceptation d'office quand l'attribution est
    manuelle (bot_discord.envoyer_repli_attente) ; absent, rien n'est envoyé."""
    _deps.update(deps)


# 09/10 (relecture du lot L1) : un « valide » plus récent que ça est en cours de validation (valider_candidat, migration
# automatique au même démarrage) : l'acceptation d'office ne le touche pas, elle le traiterait en double.
VALIDATION_EN_COURS_MIN = 10


def _age_minutes(*dates) -> float:
    """Minutes depuis la plus récente des dates ISO données ; très grand si aucune n'est lisible (un vieux « valide »)."""
    plus_recente = None
    for d in dates:
        try:
            v = datetime.fromisoformat(str(d))
        except (TypeError, ValueError):
            continue
        v = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        plus_recente = v if plus_recente is None or v > plus_recente else plus_recente
    if plus_recente is None:
        return float("inf")
    return (datetime.now(timezone.utc) - plus_recente).total_seconds() / 60


REGLES = ("1. Les comptes de la mission sont **à l'agence**. Le téléphone aussi, si on te le prête. "
          "Tu rends les accès quand on te le demande.\n"
          "2. La formation, la méthode et les vidéos sont **secrètes**. Tu ne partages rien. Tu ne copies rien.\n"
          "3. Tu as **18 ans ou plus**.\n"
          "4. Ta paie : **0,05 $ par visite qui compte sur ton lien**. Une visite qui compte vient de France "
          "ou d'un pays francophone. Pas un robot. Payé le 5 et le 20, en USDC ou par virement. "
          "Pas de fixe. 1 000 visites = 50 $. 5 000 visites = 250 $. "
          "Robots, clics achetés ou clics forcés = licenciement.\n"
          "5. 2 Reels par jour sur chaque compte de croissance. Ton compte 1 : créé dans les 48 h, sinon tu sors du serveur "
          "et ta place va au suivant.")   # 30/09 (Gaëtan) ; 05/10 : la règle unique de sortie ; 08/10 : 48 h (consigne du 05/10, 15 h 30) ; 09/10 : paie le 5 et le 20 (A5)

# La même chose, en une ligne pour le formulaire du site (aide sous la case à cocher)
REGLES_SITE = ("1. Tu as 18 ans ou plus. 2. Les comptes Instagram sont à l'agence. Tu rends les accès si on te les demande. 3. La formation reste entre nous. Tu ne la partages pas. 4. Tu es payé 0,05 $ par visite réelle, sans fixe. Les faux clics, c'est le licenciement. 5. Tu publies 2 Reels par jour sur chaque compte de croissance. Ton compte 1 doit être créé dans les 48 h, sinon tu sors.")   # 30/09 : mêmes règles, formulées court (formulaire du site) ; 05/10 : règle de sortie unique


def conditions_texte(titre: str = "") -> str:
    return (titre or "") + "Les 5 règles de l'équipe :\n" + REGLES


class BoutonAccepte(discord.ui.DynamicItem[discord.ui.Button], template=r"accepte:(?P<uid>[0-9]+)"):
    """« ✅ J'accepte, on y va » : persistant (custom_id), il survit aux redémarrages ; seul le destinataire peut cliquer."""

    def __init__(self, uid: str):
        super().__init__(discord.ui.Button(label="✅ J'accepte, on y va", style=discord.ButtonStyle.success,
                                           custom_id=f"accepte:{uid}"))
        self.uid = str(uid)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["uid"])

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("Ce bouton est pour la personne à qui je l'ai envoyé 🙂", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            texte = await _deps["accepter"](self.uid, "bouton")
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Acceptation par bouton (%s) : %s", self.uid, erreur)
            texte = "Petit souci technique de mon côté, déjà signalé. Réponds **J'ACCEPTE** ici, ça marche aussi."
        try:
            await interaction.followup.send(texte[:1990])
        except (discord.Forbidden, discord.HTTPException):
            pass


def vue(uid: str) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(BoutonAccepte(str(uid)))
    return v


async def envoyer_boutons_en_attente(client) -> list:
    """Au démarrage : chaque validé encore sans acceptation, présent sur le serveur (il attendait devant le bouton), est
    accepté d'office — 30/09 (Gaëtan : « supprime cette étape, on l'a déjà faite dans le formulaire ») : les 5 règles sont
    acceptées dans le formulaire, l'accès s'ouvre sans bouton. Trace `acceptation_auto` dans son état du pipeline.
    09/10 (Gaëtan : « Les clippeurs se font submerger d'informations… Chaque étape à la fois ») : c'est aussi le filet d'une
    validation qui n'a pas abouti (réseau, membre absent un instant). Plus de « 🎉 Félicitations » en MP : l'attribution
    envoie le message de sa créatrice ; attribution manuelle, le seul repli (dépendance « repli »). Un « valide » de moins de
    VALIDATION_EN_COURS_MIN minutes est en cours de validation : pas touché."""
    await client.wait_until_ready()
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    faits = []
    for uid, info in list(pipe.get("etats", {}).items()):
        if info.get("etat") != "valide" or not info.get("conditions_envoyees") or info.get("acceptation_auto"):
            continue
        if _age_minutes(info.get("validation"), info.get("conditions_envoyees")) < VALIDATION_EN_COURS_MIN:
            continue
        if _deps["est_signe"](uid) or _deps["membre_par_id"](uid) is None:
            continue
        try:
            texte = await _deps["accepter"](uid, "site", info.get("conditions_grille", ""))
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Acceptation d'office de %s : %s", uid, erreur)
            continue
        if texte.startswith(("Je n'ai pas", "Je ne te trouve")):          # rien à ouvrir (recrutement en pause, parti…)
            continue
        pipe = lire(fichier, {"liaisons": {}, "etats": {}})
        pipe.setdefault("etats", {}).setdefault(uid, {})["acceptation_auto"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ecrire(fichier, pipe)
        if _deps.get("repli"):
            try:
                await _deps["repli"](_deps["membre_par_id"](uid))
            except Exception as erreur:                                     # noqa: BLE001
                journal.warning("Acceptation d'office de %s : repli non envoyé (%s)", uid, erreur)
        faits.append(uid)
    if faits:
        journal.info("Acceptation d'office de %d validé(s) qui attendaient le bouton", len(faits))
    return faits
