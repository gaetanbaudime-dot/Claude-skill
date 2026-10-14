# Collecte Instagram mutualisée

Le bot conserve Apify, Discord, Sheets et son volume Railway. Supabase n'est pas nécessaire pour 250 comptes.

## Comportement

- Toutes les lectures passent par `etats_comptes.scanner` : parcours, relevés, scans du matin et rapports.
- Une seule collecte en vol dans le processus. Deux demandes qui se chevauchent réutilisent les comptes déjà mesurés.
- Cache de 15 minutes, réglable par `APIFY_CACHE_MINUTES`. Les doublons et variations de casse sont nettoyés avant la collecte.
- Le cache est persistant dans `DONNEES_DIR/apify_cache.json` ; il respecte le jour civil de Paris et la profondeur de lecture demandée. Une grille seule ne remplace pas une lecture de l'onglet Reels.
- La date d'origine reste attachée aux mesures : aucun nouveau point de followers ou de vues n'est inventé à la relecture.
- Les fiches non lues ne deviennent pas des zéros. Après une panne, refroidissement de cinq minutes dans le processus. `scanner(..., forcer=True)` permet une lecture volontaire ; elle reste soumise au budget.
- Un lot refusé pour accès/quota arrête les suivants. Un lot en timeout n'est pas relancé automatiquement : sa course peut encore tourner et être facturée.
- La réservation des Reels correspond au plafond réellement demandé. Un timeout conserve une estimation prudente au lieu de comptabiliser zéro ; l'API de consommation sert ensuite à réconcilier le budget.
- Le plafond Apify existant reste à 25 dollars par cycle. Les prix locaux sont des estimations configurables, pas des tarifs fournisseurs vérifiés.

## Historique

`series_comptes.json` conserve désormais 100 jours et jusqu'à 120 points par Reel. Les bornes des comparaisons de 90 jours restent ainsi disponibles plus longtemps.

L'archive `releves_instagram.sqlite` conserve chaque relevé validé, sans amincissement des points, pendant 100 jours. Elle est écrite après le contrôle des faux zéros. La clé compte + timestamp empêche les doublons du cache. Seuls les champs métriques sont conservés, sans bio, clé API ou données Discord.

Cette évolution ne reconstitue pas les followers ou les vues des jours antérieurs à la collecte. Elle ne garantit pas la récupération des anciens Reels sortis de la grille ou de la fenêtre de l'actor. Aucun rattrapage payant sur 90 jours n'est lancé automatiquement. Les décomptes restent soumis aux indicateurs de couverture déjà présents ; une période non couverte n'est pas déclarée exacte.

À titre de calcul de dimensionnement uniquement, au prix local configuré de 2,30 dollars pour mille profils : 250 profils × 30 relevés = 7 500 profils, soit 17,25 dollars, avant les Reels, les relances et les relectures. La réserve restante sous 25 dollars est donc limitée. Les économies de production doivent être mesurées sur la consommation Apify réelle, pas déduites des seuls tests.

## Déploiement Railway

Utiliser le service Marketing Bot existant, sa clé `APIFY_TOKEN`, ses actors, ses variables et son volume. Ne pas recréer un bot Discord, une application Railway ou une base distante.

1. Conserver un seul worker actif ; le verrou de collecte est local au processus et ne coordonne pas plusieurs réplicas.
2. Vérifier que `DONNEES_DIR` pointe sur le volume persistant ; conserver `APIFY_BUDGET_MOIS=25`.
3. Déployer le code et les deux nouveaux modules Python ensemble. Aucun changement de dépendance, de Procfile ou de commandes Discord n'est nécessaire.
4. Vérifier les lignes de journal « Apify mutualisé » : nombre en cache et nombre demandé. Ne jamais afficher la clé API ni les handles dans les comptes rendus publics.
5. Vérifier sur un petit lot deux demandes rapprochées, dont la seconde doit réutiliser le timestamp et les compteurs, puis comparer les runs et la consommation dans Apify.
6. Un rollback revient au commit précédent ; les fichiers de cache/SQLite sont additifs. Sauvegarder le volume avant toute suppression de données.

Validation locale, sans crédits Apify et sans message Discord :

```sh
cd tools/bot_clippers
python -m unittest discover -s tests -v
```

Les tests vérifient concurrence, chevauchements, TTL, profondeur, minuit, persistance, dates d'origine, erreurs et budget, archivage et conservation sur 90 jours. L'accès en production à Apify et Railway reste à vérifier séparément.
