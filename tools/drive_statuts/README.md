# Auto-Status Drive v5 (✅ ⏳ ❌ sur tout le Marketing des créatrices)

`drive_statuts.gs` est la v5 du script « MAJ Drive » (Apps Script, compte LTP) qui tourne chaque matin
avec le déclencheur `_lancerAuto`. Mêmes conventions que la v4 (emoji en fin de nom, années → mois →
semaines → tenues, verrou, reprise par créatrice, dry-run, scan complet), et en plus :

- **tout le dossier Marketing** de chaque créatrice est parcouru (Instagram, Facebook, TikTok, Stories…
  et tous les dossiers de contenu, quel que soit leur nom) ;
- **mois sans année** (ex. Instagram/Carrousel/1. Janvier) traités comme l'année en cours — la v4 les
  ignorait, d'où les Carrousels jamais marqués ;
- **mois manquants créés** dans l'année en cours (jamais dans les archives) ;
- **fichiers en vrac rangés** dans le mois de leur date de création, si l'année correspond ;
- **bilan Discord** facultatif (propriété `DISCORD_WEBHOOK_URL`).

Mise à jour : dans le projet Apps Script existant, remplacer tout le code par ce fichier et renseigner
les identifiants des dossiers Marketing dans `CREATRICES` (ils ne sont pas versionnés ici), Enregistrer.
Le déclencheur déjà installé continue de fonctionner. `lancerEnDryRun` simule sans rien modifier.
