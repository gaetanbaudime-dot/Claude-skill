# Appartenance serveur des montages

Cette protection concerne les nouvelles routes Reels des apps. Le moteur TikFusion reste directement accessible selon sa configuration actuelle ; cette PR ne corrige pas son contrôle d’accès global. Les URLs temporaires des médias restent des capacités de téléchargement. Aucun secret fournisseur ni jeton personnel d’app n’est transmis par les nouvelles routes.

## Identités et registre

Les gardes existantes restent inchangées. Clippers passe `user.cle` (clé canonique, y compris l’alias déjà accepté par la garde), Créatrices passe `user.racine` (dossier canonique de la configuration serveur). Le nom affiché, le token soumis et tout champ d’identité venant du corps de la requête ne servent jamais d’autorité. Les namespaces `clippers` et `creatrices` sont distincts. Une modification administrative de ces clés canoniques nécessite une réconciliation ; aucune migration automatique n’est faite.

Le compte Google existant lit et écrit un onglet dédié dans un tableur interne existant. La variable serveur optionnelle `REELS_OWNERSHIP_SPREADSHEET_ID` sélectionne ce tableur par son ID. Les deux apps peuvent utiliser le même tableur après validation de sa destination, de son audience et des droits de leurs services existants : leurs namespaces restent distincts, y compris si deux identités canoniques ont la même valeur. Cet ID n’est jamais accepté depuis le navigateur. Un ID renseigné mais vide, invalide ou inaccessible bloque ; il ne déclenche aucune recherche de remplacement. Le code ne renseigne aucune variable de déploiement.

Si cette variable est absente, la découverte par nom historique reste disponible : `App clippers · usage` pour Clippers et `App créatrices · usage` pour Créatrices. Elle exige un unique résultat accessible au service, sans supposer que le fichier existe. Le journal d’usage historique peut échouer silencieusement ; le bon fonctionnement de l’app ne prouve donc pas l’existence de son classeur d’usage. Aucun fichier, onglet, compte, secret ou permission n’est créé par le registre. Les lignes ne contiennent que version, type et empreintes SHA-256 de l’identité, de la ressource et de son parent. Ces données sont pseudonymes : les empreintes servent à comparer, sans anonymiser ni chiffrer les identités prévisibles. Les administrateurs disposant déjà de l’écriture sur le tableur restent dans le périmètre de confiance.

Les lectures d’autorisation sont fraîches, sans cache de droits en mémoire ou dans le navigateur. Les écritures ajoutent des lignes ; un doublon identique est sans effet sur les droits. Une association conflictuelle bloque. Une nouvelle réponse n’est transmise au navigateur qu’après écriture et relecture de son association durable. Une panne avant transfert bloque l’appel ; une panne après l’action fournisseur produit une réponse ambiguë et ne rejoue pas l’action.

## Chaîne de confiance

| Ressource | Provenance serveur exigée | Parent vérifié |
| --- | --- | --- |
| Source | réponse `source:create` | identité authentifiée |
| Import | réponse prête de `source:target/prepare` | source appartenant à l’identité |
| Projet | réponse `submit/recover` | import enregistré ; submit vérifie aussi sa source |
| Clip | réponse `clips/duplicate` | projet autorisé et identifiant de projet concordant |
| Collection | réponse `export-pack` | projet et six clips autorisés ; l’ensemble exact est enregistré |
| Export | URL exacte dans `clips/duplicate/export-pack` | clip enregistré du projet autorisé |
| Fichier final | réponse de finition | URL d’export exacte appartenant à l’identité |

Une référence non enregistrée est refusée, même si elle est connue du fournisseur ou présente dans un ancien checkpoint navigateur. Les listes de paramètres sont fermées par action. Une collection existante ne peut pas être réutilisée avec un autre ensemble de six clips.

## Préparation avant activation, après revue

Aucune modification des tableurs réels ou des variables de déploiement n’a été exécutée pendant le développement. Avant activation, faire approuver la destination existante et la persistance des données pseudonymes auprès de son audience actuelle, puis vérifier les accès existants des deux services. Après cet accord seulement, renseigner l’ID retenu côté serveur et préparer un onglet `Reels ownership v1` dans le tableur approuvé, avec exactement ces cinq cellules en première ligne :

`version` | `owner_sha256` | `kind` | `resource_sha256` | `parent_sha256`

Ne pas partager le tableur avec les utilisateurs des apps ni élargir les permissions du compte de service. Ne pas créer de tableur de remplacement si l’existant est absent ou ambigu : clarifier le stockage d’abord. Tant que l’onglet valide n’existe pas, les routes renvoient 503 avant tout appel au moteur, y compris pour le contrôle préalable de santé. Ne pas importer des associations déclarées par les navigateurs. Les montages antérieurs non enregistrés nécessitent une réconciliation administrative avec des preuves serveur.

L’adaptateur ajoute des lignes avec `values.append` et `RAW`, sans remplacer des lignes existantes. Il bloque au-delà de 50 000 associations ou si le schéma est altéré. Les quotas, la latence et l’indisponibilité Google deviennent donc des dépendances du montage. Mesurer cette charge avant une montée en volume ; ce registre n’est pas une promesse de performance à 50 secondes. Références API : [ajout de valeurs](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append), [mises à jour de tableur](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate).

## Limites de reprise

Le proxy ne réessaie aucune mutation. Cela ne garantit pas une exécution exactement une fois : une réponse de finition perdue peut conduire le client à demander un nouvel encodage lors de la reprise. Une association persistée n’est pas un registre d’idempotence du fournisseur. L’accès direct au moteur et l’enregistrement des médias sur l’appareil restent des sujets distincts.

## Tests hors ligne

`node tests/ownership.cjs` vérifie les autorisations et réponses de confiance avec plusieurs identités dans un même registre, dont une valeur canonique identique dans les deux namespaces, les références étrangères/inconnues, les mélanges de parents, les collections, les URLs exactes, les pertes/conflits de registre et les réponses ambiguës. `node tests/ownership-sheets.cjs` vérifie la sélection explicite d’un ID commun, l’absence de découverte ou de repli dans ce mode et l’adaptateur persistant sans accès Google réel ni création d’infrastructure.
