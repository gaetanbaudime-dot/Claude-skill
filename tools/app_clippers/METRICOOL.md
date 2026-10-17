# Metricool · TOP talents

## Mise à jour : provisioning automatique côté agence

Le bouton « Préparer Metricool » écrit une demande privée. Après une attente initiale de 100 secondes au démarrage, puis à chaque passage de sa boucle indépendante (60 secondes entre deux traitements), le bot utilise les identifiants administrateur déjà configurés dans Railway. Il vérifie le relevé réel de moins de 48 h et les 500 abonnés, l'affectation du compte et la récupération agence : mot de passe présent dans le classeur privé, email enregistré dans le système de codes agence actif, ou validation explicite de l'administrateur en J. Juste avant le provisioning, il relit `Comptes app` et `Pseudos app` : une identité différente, une dernière demande de pseudo différente sans statut, ou une lecture impossible retient la demande sans création ni publication du résultat. Cette relecture ne constitue pas une transaction atomique avec les modifications ultérieures du tableur. Ce contrôle constate les accès conservés ; il ne transfère aucune propriété Instagram et ne garantit pas une session Meta valide.

Le bot relit `/admin/max-profiles` et `/v2/settings/brands`, applique le plus petit plafond entre l'API et 25, réutilise une marque du propriétaire déjà reliée au même Instagram ou crée une nouvelle marque via `POST /v2/settings/brands`. Aucun changement d'abonnement. Les marques sans réseaux déjà présentes ne sont pas réaffectées automatiquement.

Le lien est obtenu via `GET/POST /v2/settings/brands/connections/anonymous-link`, disponible à partir d'Advanced. L'URL retournée doit être HTTPS sur app.metricool.com, mtr.cool ou un sous-domaine de mtr.cool. Sa véritable expiration est enregistrée en O. L'app garde ses contrôles côté serveur. Le bot renouvelle un lien expiré et rafraîchit la capacité pendant la préparation ; il passe à « connecté » seulement si l'API retourne le bon Instagram sur la marque.

La création est protégée par un verrou de processus et de fichier sur le volume `/data`, un nom déterministe et un journal atomique écrit AVANT l'appel de création. Une réponse incertaine ne déclenche pas de nouvel essai aveugle : récupération par ID/nom, sinon contrôle administrateur. Ne jamais supprimer le journal pour relancer une création sans rapprochement des marques existantes.

Sources supplémentaires vérifiées le 17 octobre 2026 : https://app.metricool.com/api/swagger.json et https://help.metricool.com/wli-brand-connections-panel-for-end-clients-through-api-4m5b3 . La description actuelle de l'API confirme Advanced ou supérieur pour les liens, même si l'introduction de l'article mentionne les intégrateurs.

La procédure manuelle ci-dessous décrit les vérifications de reprise par l'agence. La file est traitée automatiquement : une intervention manuelle doit être coordonnée pour éviter une création concurrente. Cette documentation ne vaut pas autorisation de créer ou partager de nouveaux accès.

## Parcours livré

Dans Comptes, le clipper voit « Demander la connexion Metricool » seulement à partir de **500 abonnés**, relevés depuis moins de **48 heures**. Les valeurs sont relues côté serveur depuis Comptes app. Une demande de changement de @ en attente bloque l'accès. Un changement de @ invalide l'ancien rattachement.

Le bot ajoute une colonne L, « Followers vérifiés le (ISO) », sans déplacer A:K. La date vient du relevé réel ayant fourni le nombre (série Apify/Metricool), jamais de l'heure de publication ni d'une valeur de repli saisie dans le classeur. Tant que cette version du bot n'est pas en service, le parcours reste masqué. Les autres fonctions de l'app restent utilisables si Metricool est indisponible.

## Advanced 25 : ce qui est réellement possible

Seul le propriétaire du compte payant peut créer des marques. Un collaborateur Advanced peut connecter des réseaux à une marque existante avec les permissions adaptées. Le lien temporaire ne crée pas de marque.

Sources officielles vérifiées le 17 octobre 2026 :

- https://help.metricool.com/shared-brands-in-metricool-uf4oz
- https://help.metricool.com/how-to-share-a-link-so-your-clients-can-connect-their-social-networks-without-a-metricool-account-7ocal

Le lien de connexion est disponible sur Advanced/Custom, généré depuis Connections > Share > Create link, valable 71 heures et révocable. Le code traite automatiquement la file via les endpoints décrits ci-dessus. Le lien anonyme autorise la connexion de réseaux à la marque ; il ne donne pas accès à tout l'espace de la marque. Sa génération exige la permission Management selon la documentation officielle. Les permissions détaillées de l'endpoint API et l'audience effective du tableur restent à valider avant toute nouvelle mise en service de ce partage.

## Traitement par l'agence

L'app prépare l'onglet **Metricool · demandes** dans le tableur privé **App clippers · usage**. A:F sont les données serveur de la demande. Ne jamais partager ce tableur avec les clippers : il contient des clés personnelles et des liens de connexion.

Pour une reprise manuelle coordonnée avec le traitement automatique, l'administrateur vérifie les points suivants :

1. Vérifier le @, son affectation actuelle au clipper et l'absence de marque existante pour ce même compte. Plusieurs requêtes simultanées peuvent produire des lignes doublonnées : les dédupliquer avant toute création. L'écriture initiale de la demande ne crée aucune marque ; le bot peut ensuite en créer une après ses contrôles.
2. Vérifier **en direct** le nombre de marques sur le compte Metricool propriétaire. Le bot relit la capacité et les marques via l'API ; un contrôle manuel doit lui aussi utiliser des valeurs actuelles. Ne créer une marque que si le total est inférieur à 25. Au plafond, garder « demandé » et attendre une décision de l'agence ; aucun changement de forfait automatique.
3. Vérifier les droits de l'agence sur Instagram et les moyens de récupération (email, téléphone, double authentification, accès Meta adaptés). Une connexion Metricool ne transfère pas la propriété Instagram et peut expirer ou être révoquée. Ne stocker aucun mot de passe ni code 2FA dans cet onglet.
4. Le propriétaire crée la marque ou réutilise la marque correcte appartenant déjà à l'agence. Reporter son ID en H ; mettre « oui » en I uniquement après vérification de sa propriété ; « oui » en J après vérification des accès de récupération de l'agence.
5. Reporter en K le **total utilisé après création**, entre 1 et 25 ; en L la date de contrôle en ISO avec fuseau (par exemple 2026-10-17T10:00:00Z). Ce contrôle doit dater de moins de 24 h.
6. Générer le vrai lien sur la marque exacte, le coller en M et reporter son heure réelle de création ISO en N. Passer G à « prêt » seulement ensuite. Reporter aussi l'expiration réelle en O. L'app accepte HTTPS sur app.metricool.com, mtr.cool et ses sous-domaines.
7. « Connecter Metricool » apparaît. Chaque ouverture revérifie éligibilité, capacité, propriété déclarée et âge du lien. Après 71 h (ou contrôle de capacité datant de plus de 24 h), renouveler les champs concernés. Si le lien est révoqué dans Metricool, repasser G à « demandé » immédiatement.
8. Vérifier dans Metricool que **le bon Instagram** est connecté à la bonne marque avant de passer G à « connecté ». Le simple clic n'est jamais considéré comme une connexion réussie.

Au départ du clipper, retirer son accès collaborateur, révoquer les liens temporaires et vérifier les accès Meta/Instagram et la connexion Metricool. Tester la publication avec l'autorisation appropriée ; aucune continuité n'est garantie par le seul rattachement Metricool.

## Validation et mise en service

Tests : `node tests/metricool-policy.cjs`, `npx tsc --noEmit`, `npm run build` ; tests Python existants pour Comptes app et Dashboard. Tester aussi avec des données de test : 499/500, relevé absent/périmé, clé d'un autre clipper, changement de @, 25/26 marques, lien expiré et indisponibilité Sheets.

Déployer l'app via le projet Vercel **app-clippers**, racine tools/app_clippers, et livrer séparément le bot. Ne pas redémarrer un autre service. Sans les accès d'exécution du bot et une vraie demande de test, la validation de bout en bout reste à faire. Le bot peut créer une marque et générer ou renouveler son lien de connexion ; il ne crée pas de compte Instagram et ne change pas d'abonnement. Il écrit le lien en colonne M du tableur ; la route de l'app le délivre par redirection après contrôle du jeton personnel et des conditions serveur. Ce correctif de relecture d'identité ne change ni cette capacité existante, ni les ACL, ni les identifiants. Leur présence dans le code ne valide pas un nouveau partage.

## Prévisualisation protégée

Les connexions existantes GAML et Google peuvent être réutilisées uniquement sur une branche de test explicitement autorisée. Limiter chaque entrée Preview à cette branche ; ne pas élargir les variables Production à toutes les prévisualisations. Utiliser une valeur `CLIPPERS_SECRET` distincte pour conserver les liens Production. Reconstruire la prévisualisation après l'ajout des variables, puis tester avec un lien dérivé de sa clé propre. La configuration créatrices peut rester vide pour un test Metricool sur un tableur existant ; cela ne valide pas les parcours de création de dossiers.
