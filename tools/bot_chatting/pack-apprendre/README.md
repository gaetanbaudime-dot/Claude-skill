# Pack `!apprendre` — les blocs de la base, un par fichier

Ces 25 fichiers sont **exactement les mêmes blocs** que `connaissances_depart.md`,
découpés un par un. Ils servent à deux choses :

1. **Modèle de format** : pour ajouter un savoir au bot, écris un fichier comme ceux-là
   (un titre `## `, puis des puces courtes) et glisse-le dans Discord avec `!apprendre`
   en pièce jointe. Ou tape directement `!apprendre <texte>` pour un ajout court.
2. **Restauration** : si un bloc a été retiré avec `!oublier` et qu'il faut le remettre,
   glisse le fichier correspondant avec `!apprendre` — pas besoin de redéployer le bot.

Au premier démarrage, le bot charge déjà tout `connaissances_depart.md` : ce pack n'est
PAS à ingérer en plus (ce serait du doublon). Il ne sert qu'après, à la carte.

Rappel : le verbatim des scripts (Négociation, PostMedia, Relance…) reste dans le CRM.
Si tu ajoutes des blocs, mets les règles d'usage, pas le texte des messages aux fans.
