"""Bouchon inerte (11/10, revue du recrutement, lot L12) : la cadence de publication par clipper (`!cadence`, lancement
automatique CADENCE_AUTO, cadence_reels.json) est RETIRÉE.

Pourquoi : le module servait la prime de Jonas (cadence tenue 80 % des jours), parti le 09/10. La paie décidée par Gaëtan est au
clic, et le Dashboard donne déjà, par compte et sans coût Apify, les Reels d'hier et des 7 jours, les vues et les followers (séries
du scan et de Metricool). Une lecture `!cadence` coûtait 1 à 5 $ sur le budget Apify de 25 $ par mois.

Rien ne servait ailleurs : la règle des vues d'une publication vit dans series.vues_post, le nettoyage des @ dans
onboarding.normaliser_handle.

11/10 (vérification du lot L12) : bot_discord n'importe plus ce module ni ne l'appelle (`!cadence` sort aussi des commandes du
Manager). Le fichier reste, inerte, pour les tests qui l'importent encore ; il se supprime avec eux. La variable
Railway CADENCE_AUTO n'est plus lue (à retirer de Railway quand tu veux), et cadence_reels.json, s'il reste sur le volume, n'est
plus lu ni écrit.
"""
import logging
import os

journal = logging.getLogger("bot.cadence")
# La variable n'allume plus rien : si elle est encore posée dans Railway, le journal le dit une fois (à retirer de Railway).
OBSOLETE = os.environ.get("CADENCE_AUTO", "").strip() != ""
RETIRE = ("Retiré le 11/10 : `!cadence` n'existe plus.\n\n"
          "Les Reels d'hier et des 7 jours, les vues et les followers de chaque compte sont dans l'onglet Dashboard, sans coût Apify.")
_dits = set()


def _dire(quoi: str):
    """Une ligne de journal par processus et par appel retiré (pas une à chaque tour)."""
    if quoi not in _dits:
        _dits.add(quoi)
        journal.info("cadence_reels.%s : retiré le 11/10 (lot L12), appel ignoré — le lot W le retire de bot_discord", quoi)


def configurer(deps: dict = None):
    """Retiré le 11/10 : ne fait rien (sauf dire, une fois, que CADENCE_AUTO est encore posée dans Railway)."""
    _dire("configurer")
    if OBSOLETE and "obsolete" not in _dits:
        _dits.add("obsolete")
        journal.warning("CADENCE_AUTO est encore posée dans Railway : elle n'est plus lue depuis le 11/10 (cadence retirée), retire-la")


async def boucle(client=None) -> None:
    """Retiré le 11/10 : plus de lecture automatique (ni Apify, ni salon admin)."""
    _dire("boucle")
    return None


async def commande(message, texte_msg: str) -> bool:
    """`!cadence` répond qu'elle est retirée (sinon elle tomberait dans « commande inconnue ») ; tout le reste : False."""
    if ((texte_msg or "").split() or [""])[0].lower() != "!cadence":
        return False
    _dire("commande")
    await message.reply(RETIRE)
    return True
