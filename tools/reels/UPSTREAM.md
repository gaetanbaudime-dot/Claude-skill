# Moteur partagé des apps G&M

L’orchestration navigateur provient de `DavidDayanAI/TikFusion`, PR 15, commit fusionné `04035412e2de569c761b0fcc4543b0d6a6826ab7` (head revu `8ea22b94b636b7016dd2cac73946a5700fdbdd92`). Les fonctions de téléchargement et le modèle de durée proviennent du même commit.

Le moteur native Opus, la préparation, les six presets et les finitions HD restent sur le backend du Duplicateur existant. Le client partagé adapte seulement le préfixe des routes et le contexte de stockage du navigateur. Les requêtes JSON passent par les gardes de jeton existantes des apps puis un proxy à destination fixe. Aucun jeton personnel d’app, cookie ou secret fournisseur n’est envoyé au Duplicateur.

Le nouveau contexte de navigateur utilise un hash du jeton déjà présent dans l’app pour séparer les checkpoints locaux. Les anciennes données de l’iframe restent sur son origine et ne sont ni lues, ni fusionnées, ni supprimées. La reprise de PR15 s’applique aux nouveaux montages dans le même contexte de l’app ; aucune reprise automatique entre apps, appareils ou après fermeture n’est promise.

Ne pas mettre à jour le moteur sans reporter les suites de non-régression de reprise, doublons et téléchargement. Les tests utilisent des échanges HTTP simulés et ne créent aucun rendu réel.

Les routes des apps ajoutent un registre serveur d’appartenance : voir [OWNERSHIP.md](OWNERSHIP.md). Cela ne sécurise pas l’accès direct au moteur. Une finition dont la réponse a été perdue peut être réencodée lors de la reprise ; aucune exécution exactement une fois n’est garantie.
