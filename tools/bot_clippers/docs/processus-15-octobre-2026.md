# Processus clippeur — corrections préparées le 15 octobre 2026

Statut : **draft, non déployé ; validation complète du processus encore nécessaire**.

Base : `origin/main` à `5556a88`. La fusion du duplicateur `4f0fb9d` est conservée. Aucun fichier du checkout initial en conflit n’a été modifié. Aucun déploiement du duplicateur, de Railway ou de Vercel, aucune inscription, aucun partage Drive et aucun départ réel n’ont été exécutés.

## Corrections incluses

- Un scan public ne déduit plus BAN d’une absence, ni propriété d’un profil devenu visible. Les anciens états ambigus restent en place. Une absence ne vaut pas disponibilité d’un pseudo.
- Les mails de suspension sans date exploitable sont écartés ; les preuves reconnues distinguent appel possible et désactivation définitive. Les autres preuves restent à vérifier, sans écrasement de l’état. Leur type et référence sont conservés dans l’historique existant.
- Ordre d’affichage préparé : Good vert, Faire appel orange, Ban rouge, À créer blanc. Un ancien PRIVE apparaît comme type privé à vérifier, pas comme preuve de santé. La création d’un privé n’écrit plus PRIVE dans l’état de santé.
- Nouveau parcours fixé à croissance 1 → croissance 2 après quatre Reels vérifiés sur 1 → privé après quatre Reels vérifiés sur 2. Aucun supplément de Reels sur 1 ; aucun délai entre les paliers. Les anciens ordres privé-en-2 restent bloqués pour vérification, sans renumérotation.
- Les publications sont cumulées par shortcode et date vérifiée, au passage complet comme au passage léger. Les totaux glissants historiques sont conservés mais n’ouvrent plus les paliers. Les publications antérieures à la création, futures ou sans date ne comptent pas. Un même shortcode ne compte qu’une fois.
- Réservation limitée à trois identités à vie par UID Discord, conservée avant écriture Sheets et avant libération. Le registre conserve les alias et une identité stable lors des renommages. Une réservation interrompue consomme sa place jusqu’à résolution ; elle n’autorise pas un quatrième compte.
- Les comptes déjà créés ne reviennent plus dans le vivier, même avec l’ancien réglage COMPTES_RENDUS. Le mécanisme de remplacement automatique est neutralisé. Le lien libéré d’un sortant n’est plus repris par ce chemin d’onboarding.
- Le privé et l’étape de livraison de l’app attendent au minimum un lien GAML présent. Un échec d’envoi de l’étape retire la fausse date de livraison ; le programme réessaie les comptes 2 et 3 lorsque l’envoi échoue.

## Vérification locale

Suite exécutée sous Python 3.11, avec les dépendances du bot dans un environnement isolé :

```sh
python -m unittest discover -s tools/bot_clippers/tests
```

Les nouveaux tests sont dans `tests/test_process_15_octobre.py` : quota, rejeu, départ/retour fictif, exclusion d’une réattribution, renommage, échec partiel de réservation, concurrence sous verrou, paliers distincts, suppression des anciens délais, déduplication et dates des publications, qualification de mails synthétiques, remplacement sans effet.

La compilation Python et `git diff --check` sont aussi vérifiés. Le graphe demandé par CLAUDE.md n’est pas disponible : ni `graphify-out`, ni exécutable `graphify` installé.

## Conditions bloquant le déploiement

1. **Historique à vie incomplet** : le registre récupère seulement les comptes encore présents dans les fiches, les livraisons et les alias. Les comptes déjà effacés avant ce changement doivent être rapprochés des historiques de production. Une réservation est comptée de manière conservatrice, ce n’est pas une preuve de création effective. Aucun ancien compteur ne doit être remis à zéro.
2. **Liens uniques pas encore garantis de bout en bout** : le contrôle d’un lien GAML présent ne valide pas ses deux destinations. L’allocation MYM n’est pas encore testée en reprise partielle ; OF est encore choisi par POD. Il faut vérifier la capacité réelle, empêcher le partage de tracking entre clippers, persister chaque étape et conditionner la livraison à MYM + OF tous deux prêts. Les clones externes peuvent encore réussir avant l’écriture locale : reprise idempotente à terminer.
3. **Concurrence limitée au processus** : les appels de réservation existants utilisent le verrou asyncio partagé ; le test de concurrence est synthétique. Aucune garantie multi-réplicas ni transaction Sheets/disque n’est démontrée. Vérifier la topologie Railway et tester les interruptions réelles avec doublures avant production.
4. **Discord/Drive et candidature** : les parcours Telegram/Facebook/Discord → formation → quiz → Discord, salon unique, team leader, coefficients réellement configurés, rôles et accès Drive doivent encore être vérifiés avec doublures et lecture de configuration autorisée. Ces services n’ont pas été contactés dans ce chantier.
5. **Disponibilité des pseudos** : aucun endpoint de disponibilité fiable n’a été validé ; l’absence publique reste un signal insuffisant. Ne pas annoncer un pseudo disponible sur cette seule base.
6. **Sortie réelle** : archiver le lien avec préfixe X, préparer Metricool, puis exclure Discord reste à vérifier pour l’ordre, les reprises et l’idempotence. Aucun test de sortie réel n’est autorisé.
7. **Affichage et preuves** : les couleurs/labels sont préparés pour le dashboard simple, pas migrés sur les feuilles de production ni validés dans toutes les vues des apps. La classification textuelle des mails reste volontairement restrictive et demande des fixtures supplémentaires anonymisées.

Ne pas fusionner/déployer cette draft comme si l’ensemble du nouveau processus était validé. Aucune migration destructive n’est incluse.
