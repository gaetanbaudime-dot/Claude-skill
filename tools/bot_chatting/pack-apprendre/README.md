# Pack `!apprendre` — les blocs de la base, un par fichier

Ces 40 fichiers sont **exactement les mêmes blocs** que `connaissances_depart.md`,
découpés un par un. Ils servent à deux choses :

1. **Modèle de format** : pour apprendre quelque chose au bot, écris un fichier comme
   ceux-là (un titre `## `, puis des phrases courtes et simples) et glisse-le dans
   Discord avec `!apprendre` en pièce jointe. Pour un ajout court : `!apprendre <texte>`.
2. **Restauration** : un bloc retiré par erreur avec `!oublier` ? Glisse le fichier
   correspondant avec `!apprendre`. Pas besoin de redéployer le bot.

Au premier démarrage, le bot charge déjà tout `connaissances_depart.md` : ce pack n'est
PAS à ingérer en plus (ce serait du doublon). Si la graine du dépôt a été réécrite
après le premier démarrage, `!graine remplace` recharge TOUTE la base d'un coup
(attention : ça efface les ajouts `!apprendre` faits entre-temps).

Règles d'écriture des nouveaux blocs : français simple (niveau collège), phrases
courtes, un sujet par bloc, les règles d'usage des scripts — jamais leur texte mot à
mot (il reste dans le CRM), jamais de données personnelles de fans.
