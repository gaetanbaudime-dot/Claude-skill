# Assistant chatting — bot Discord (propriété : Maxence)

Bot totalement séparé du bot clippers : autre application Discord, autre service Railway,
autre volume, aucune donnée partagée avec le marketing. Il répond aux questions des
chatteurs à partir de SA base de connaissances, et loggue en « lacunes » tout ce qu'il ne
sait pas — c'est comme ça qu'on sait quoi lui apprendre ensuite.

La base de départ (`connaissances_depart.md`, chargée au premier démarrage) contient déjà
toute la formation interne distillée en 25 blocs : KPI (golden 1-3 %, unlock cible
40-50 %), tunnel de prix minimum 7→112 €, règles cams (paiement d'avance, validation
TL + Maxence), qualification des fans, profils TW→Whale, roue des émotions, objections,
back-office (Fan Note, titrage, passation), organisation (team leaders, paie), sécurité.
Les scripts verbatim restent dans le CRM : le bot dit quand les utiliser, jamais leur
texte. Le dossier `pack-apprendre/` contient les mêmes 25 blocs en fichiers séparés,
comme modèle de format `!apprendre` et pour restaurer un bloc retiré.

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
