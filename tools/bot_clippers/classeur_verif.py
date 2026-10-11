"""Bouchon inerte (11/10, revue du recrutement, lot L12) : la vérification du classeur après le scan (29/09) est FONDUE dans le
contrôle d'attribution (controle.py), `!classeur` est retiré.

Avant : deux contrôles du même classeur, deux messages au salon admin. Ce que seul ce module voyait est devenu une famille du
contrôle, calculée toutes les 15 minutes et affichée dans la section CONTRÔLE du Dashboard :

  - e-mail en double, infos d'un compte BAN réutilisées → C13 ;
  - ligne BAN qui garde un Gérant → C14 ;
  - réservation « à créer » jamais vue sur Instagram après 7 jours de scan → C15 ;
  - plus de 3 comptes vivants pour un clipper → C16.

Le pseudo en double était déjà C11. Mêmes règles, mêmes variables Railway (CLASSEUR_SCANS_MIN, CLASSEUR_MAX_COMPTES), mêmes
exclus (etats_comptes.dashboard_exclus). Le salon admin n'est prévenu que quand la liste des points bloquants ou importants change.

11/10 (vérification du lot L12) : bot_discord n'importe plus ce module ni ne l'appelle (`!classeur` sort aussi des commandes du
Manager). Le fichier reste, inerte, pour les tests qui l'importent encore ; il se supprime avec eux. classeur_verif.json, s'il reste
sur le volume, n'est plus lu ni écrit.
"""
import logging

journal = logging.getLogger("bot.classeur_verif")
RETIRE = ("Retiré le 11/10 : `!classeur` n'existe plus.\n\n"
          "Ses contrôles sont dans le contrôle d'attribution : C13 e-mail en double ou info d'un BAN, C14 BAN qui garde un Gérant, "
          "C15 réservation jamais créée, C16 plus de 3 comptes vivants.\n\n"
          "Tu les lis dans l'onglet Dashboard, section CONTRÔLE. Le salon admin est prévenu quand la liste change.")
_dits = set()


def _dire(quoi: str):
    """Une ligne de journal par processus et par appel retiré (pas une à chaque scan)."""
    if quoi not in _dits:
        _dits.add(quoi)
        journal.info("classeur_verif.%s : retiré le 11/10 (lot L12, fondu dans controle C13 à C16), appel ignoré — le lot W le "
                     "retire de bot_discord", quoi)


def configurer(deps: dict = None):
    """Retiré le 11/10 : ne fait rien."""
    _dire("configurer")


async def verifier(comptes=None, historique=None, force: bool = False):
    """Retiré le 11/10 : plus de message au salon admin après le scan (controle.passage le fait, toutes les 15 min). None."""
    _dire("verifier")
    return None


async def commande(message, texte_cmd: str) -> bool:
    """`!classeur`, `!verif`, `!vérif` répondent qu'ils sont retirés, et où lire la même chose ; tout le reste : False."""
    if ((texte_cmd or "").split() or [""])[0].lower() not in ("!classeur", "!verif", "!vérif"):
        return False
    _dire("commande")
    await message.reply(RETIRE)
    return True
