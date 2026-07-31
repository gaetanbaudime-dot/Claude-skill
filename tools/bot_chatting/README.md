# Assistant chatting — bot Discord (propriété : Maxence)

Bot totalement séparé du bot clippers : autre application Discord, autre service Railway,
autre volume, aucune donnée partagée avec le marketing. Il répond aux questions des
chatteurs à partir de SA base de connaissances, et loggue en « lacunes » tout ce qu'il ne
sait pas — c'est comme ça qu'on sait quoi lui apprendre ensuite.

La base de départ (`connaissances_depart.md`, chargée au premier démarrage) contient
toute la doctrine de l'agence distillée en 40 blocs, **écrite en français simple
(niveau collège)** pour les chatteurs dont le français est la deuxième langue : KPI,
tunnel de prix (avec la règle du cumul), cams/customs/packs, interdictions, KYC,
Fan Note/Nickname/titre/listes, relances (cadence 30-60 min / 2-3 h / lendemain, max 3),
prix (jamais à froid, jamais demander le budget, négociation en escalier), passation et
flambeau, priorités en rush, paie, pénalités, sécurité. Les scripts verbatim restent
dans le CRM : le bot dit quand les utiliser, jamais leur texte. Le dossier
`pack-apprendre/` contient les mêmes blocs en fichiers séparés (modèle de format
`!apprendre`, restauration à la carte). Si la graine du dépôt est réécrite APRÈS le
premier démarrage : `!graine remplace` recharge toute la base (attention : efface les
ajouts `!apprendre` faits entre-temps).

## Installation (~30 min, une seule fois)

1. **Application Discord** — discord.com/developers/applications > New Application
   « Assistant Chatting » > onglet Bot :
   - Reset Token → copier le token (il ne s'affiche qu'une fois) ;
   - activer **MESSAGE CONTENT INTENT** (obligatoire, sinon le bot ne lit rien).
   Onglet OAuth2 > URL Generator : cocher `bot`, permissions « Send Messages » +
   « Read Message History » + « Attach Files » → ouvrir l'URL générée → inviter le bot
   sur le serveur chatting.

2. **Clé API Claude dédiée** — console.anthropic.com > API Keys > nouvelle clé
   « bot-chatting ». Une clé À PART : le coût du chatting se lit alors séparément.

3. **Railway** — New > Deploy from GitHub repo `Claude-skill` :
   - Settings > **Root Directory : `tools/bot_chatting`** (c'est ce qui sépare les 2 bots) ;
   - Variables : `DISCORD_TOKEN`, `ANTHROPIC_API_KEY`, `ADMIN_IDS` (ids Discord de
     Maxence et Gaëtan, séparés par une virgule), `DONNEES_DIR=/data` ;
   - Volume monté sur `/data` (c'est la mémoire du bot : sans lui, tout ajout de
     connaissance disparaît au redéploiement).

4. **Test** — mentionner le bot avec une question ; `!ici` dans le salon FAQ pour qu'il y
   réponde sans mention ; `!aide` pour la liste des commandes.

## Comment Maxence fait vivre le bot (tout se passe dans Discord)

| Commande | Effet |
|---|---|
| `!apprendre <texte>` | Ajoute une connaissance (ou joindre un fichier .md/.txt) |
| `!oublier <n°>` | Retire le bloc n° |
| `!connaissances` | Liste numérotée de tout ce que le bot sait |
| `!lacunes` | Les questions restées sans réponse — la liste de courses |
| `!lacunes vider` | Purge après avoir comblé |
| `!ici` | Active/désactive le bot dans le salon courant |

Le rythme qui marche : une fois par semaine, `!lacunes` → répondre à chaque question via
`!apprendre` → `!lacunes vider`. La base grandit exactement là où les chatteurs butent.

## Coût

Claude Haiku : de l'ordre de 5-10 €/mois pour une équipe de ~40 chatteurs, plus ~5 $/mois
de Railway. Suivi visible sur console.anthropic.com avec la clé dédiée.
