"""Relance quotidienne des arrivés sur Discord sans quizz réussi (30/09) : SUPPRIMÉE le 10/10 (revue du recrutement, lot L9a).

Depuis le 09/10, le quizz se passe sur le site, AVANT Discord : presque personne n'arrive sans l'avoir réussi, et le module était
éteint par défaut (RELANCE_NOUVEAUX=0). La sortie à 48 h sans quizz reste (bot_discord.boucle_pipeline ⑥).

Ce fichier n'est qu'un bouchon inerte, le temps que le lot W retire `import relance_nouveaux` et son branchement de on_ready ;
il sera supprimé avec eux. RELANCE_NOUVEAUX et RELANCE_NOUVEAUX_HEURE ne servent plus."""

_deps = {}


def configurer(deps: dict):
    """Bouchon : garde les dépendances, n'en fait rien."""
    _deps.update(deps)


async def boucle(client):
    """Bouchon : plus aucune relance."""
    return None
