# Statuts automatiques des dossiers Drive (✅ ⏳ ❌)

Un script Apps Script (`drive_statuts.gs`) qui parcourt tout le Drive des créatrices chaque matin et
tient à jour le nom de chaque dossier mensuel :

- `⏳ 9. Septembre` : le mois en cours, en train d'être rempli ;
- `✅ 8. Aout` : un mois qui contient des fichiers ;
- `❌ 10. Octobre` : un dossier vide (hors mois en cours).

Il crée les mois manquants là où il trouve déjà des dossiers de mois (Reels, Carrousel, Stories, quelle
que soit la créatrice ou la plateforme), range les fichiers laissés en vrac à la racine dans le mois de
leur date de création, et ne supprime jamais rien. Un bilan part chaque matin dans le salon admin
Discord si `DISCORD_WEBHOOK_URL` est renseigné.

## Installation (5 min, une seule fois, depuis le compte Google LTP)

1. script.google.com → Nouveau projet → coller `drive_statuts.gs` → Enregistrer.
2. Paramètres du projet → Propriétés du script → `DOSSIERS_RACINE` = l'identifiant du dossier « Instagram »
   (fin de l'URL du dossier ; plusieurs identifiants séparés par des virgules pour couvrir Facebook ou
   d'autres créatrices) ; `DISCORD_WEBHOOK_URL` facultatif.
3. Exécuter `lancerMaintenant` une fois (autoriser Drive), lire le bilan dans « Journal d'exécution ».
4. Exécuter `installerDeclencheur` une fois : tous les jours à 6 h ensuite.

## Limites

- Un dossier partagé en lecture seule par une créatrice ne peut pas être renommé : il apparaît dans le
  bilan sous « lecture seule ». Demander à la créatrice le droit « Éditeur » sur son dossier.
- Les dossiers de mois ne portent pas d'année : le mois en cours est celui de la date du jour (Paris).
- Le script s'exécute avec le compte qui l'installe : il doit voir les dossiers partagés.
