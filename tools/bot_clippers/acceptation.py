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
    """deps : accepter (async (uid, via) -> texte), lire_json, ecrire_json, FICHIER_PIPELINE, membre_par_id, est_signe (uid -> bool)."""
    _deps.update(deps)


REGLES = ("1. Les comptes de la mission sont **à l'agence**. Le téléphone aussi, si on te le prête. "
          "Tu rends les accès quand on te le demande.\n"
          "2. La formation, la méthode et les vidéos sont **secrètes**. Tu ne partages rien. Tu ne copies rien.\n"
          "3. Tu as **18 ans ou plus**.\n"
          "4. Ta paie : **0,05 $ par visite qui compte sur ton lien**. Une visite qui compte vient de France "
          "ou d'un pays francophone. Pas un robot. Payé tous les 15 jours, en USDC ou par virement. "
          "Pas de fixe. 1 000 visites = 50 $. 5 000 visites = 250 $. "
          "Robots, clics achetés ou clics forcés = licenciement.\n"
          "5. 2 Reels par jour sur chaque compte. 3 jours sans publier = avertissement. 7 jours = licenciement.")   # 30/09 (Gaëtan)

# La même chose, en une ligne pour le formulaire du site (aide sous la case à cocher)
REGLES_SITE = ("1. Tu as 18 ans ou plus. 2. Les comptes Instagram sont à l'agence. Tu rends les accès si on te les demande. 3. La formation reste entre nous. Tu ne la partages pas. 4. Tu es payé 0,05 $ par visite réelle, sans fixe. Les faux clics, c'est le licenciement. 5. Tu publies 2 Reels par jour sur chaque compte. 3 jours sans publier, c'est un avertissement. 7 jours, c'est le licenciement.")   # 30/09 : mêmes règles, formulées court (formulaire du site)


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
    """Au démarrage, une fois par personne : chaque validé encore sans acceptation, présent sur le serveur, reçoit les
    5 règles avec le bouton. Trace `bouton_accepte` dans son état du pipeline."""
    await client.wait_until_ready()
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    envoyes = []
    for uid, info in pipe.get("etats", {}).items():
        if info.get("etat") != "valide" or not info.get("conditions_envoyees") or info.get("bouton_accepte"):
            continue
        if _deps["est_signe"](uid):
            continue
        membre = _deps["membre_par_id"](uid)
        if membre is None:
            continue
        try:
            await membre.send("✍️ **Plus besoin d'écrire J'ACCEPTE : un bouton suffit.**\n\n"
                              "Ton test est validé. Il ne manque que ton accord sur les 5 règles.\n\n" + REGLES
                              + "\n\nAppuie sur le bouton. Ton accès s'ouvre tout de suite, ta créatrice et tes comptes arrivent.",
                              view=vue(uid))
        except (discord.Forbidden, discord.HTTPException):
            continue
        info["bouton_accepte"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        envoyes.append(uid)
    if envoyes:
        ecrire(fichier, pipe)
        journal.info("Bouton J'accepte envoyé à %d validé(s) en attente", len(envoyes))
    return envoyes
