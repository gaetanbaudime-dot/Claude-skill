# Audit autonome — code préparé, transport et cadence inactifs

## Destination proposée, à approuver

Classeur existant des logins, via son identifiant déjà configuré dans le bot. La lecture du connecteur Drive a retourné deux destinataires : propriétaire Lovely Top Models et compte de service bot-ltp. Aucune permission anyone, domaine ou groupe retournée. Ce constat n'autorise pas à lui seul la création des onglets ci-dessous. Ne pas toucher à Comptes · Pilotage ni à Règles du process.

Deux onglets dédiés proposés, avec en-têtes exacts :

- Audit-processus — couverture : Lot, Avant, Après, Collecte complète, Salons identifiés, Salons complets, Opérations découverte, Découvertes complètes, Messages, Lot prêt.
- Audit-processus — signaux : Lot, Jour, Catégories, Référence Discord, Bot.

Ils hériteraient de l'audience du classeur entier : un onglet masqué n'est pas une permission séparée. Aucun partage, droit ou secret supplémentaire. Le bot refuse une destination différente du classeur existant et des en-têtes absents/différents. Il ne crée aucun onglet. Le worker Sheets reste responsable de leur création après validation de la destination précise.

## Contrat de données

Chaque cellule exportée est reconstruite : identifiant numérique de lot, dates, catégories fermées, référence Discord numérique ou compteurs de couverture. Aucun UID séparé, nom, texte de conversation, embed, pièce jointe, identifiant d'accès ni secret. Les références Discord restent consultables seulement avec les droits Discord existants. Les écritures RAW n'interprètent pas de formules.

La couverture peut être publiée partielle. Lot prêt ne devient oui qu'après collecte complète, export paginé de toutes les lignes et relecture du manifeste. Une réponse réseau incertaine reprend la même plage, avec les mêmes valeurs. Pas d'append non idempotent. La couverture incomplète et la fraîcheur doivent être signalées par le consommateur ; des catégories ne prouvent ni une cause ni une résolution.

## Exécution bornée

Une seule tâche démarrée par le garde on_ready existant. Un serveur explicitement configuré, jamais tous les serveurs vers le même classeur. Au plus quatre tranches de 45 secondes et quatre pages de diagnostic de 1000 messages par passage, puis pause technique de 15 minutes. Le collecteur partage son verrou par serveur avec la commande manuelle. Chaque page SQLite conserve son curseur atomiquement. Le producteur garde son checkpoint JSON privé après chaque tranche/page exportée, s'arrête sans progrès et respecte les reprises différées du collecteur.

La photographie historique déjà présente est reprise. Après son export terminé, une nouvelle base incrémentale fige son cutoff et lit uniquement les messages depuis le précédent cutoff, sans perdre la borne commune. L'historique n'est ni effacé ni remis à zéro. Les fichiers SQLite sont plafonnés globalement à 256 MiB ; le transport à 100000 lignes. Un plafond bloque et exige une décision de rétention, jamais une suppression automatique. Les éditions/suppressions d'anciens messages ne sont pas suivies par ce mécanisme incrémental. Limite explicite : une photographie historique qui reste incomplète (par exemple un salon durablement inaccessible) retarde les deltas suivants. Le manifeste reste partiel ; ce lot ne garantit donc pas encore une fraîcheur continue en présence d'un historique bloqué. La séparation de ce reliquat et des nouveaux deltas doit être revue avant activation si ce cas apparaît.

## Amorçage et activation distincts

Tous les paramètres suivants sont non secrets et restent non configurés dans ce chantier : AUDIT_SERVEUR_ID, AUDIT_CLASSEUR_APPROUVE, AUDIT_DESTINATAIRES_VERIFIES_REF, AUDIT_LECTURE_CLOUD_REF et AUDIT_AUTONOME_ACTIF.

Après approbation de la destination et création des en-têtes, l'administrateur peut utiliser !audit-discussions publier pour amorcer un lot borné. La commande respecte les contrôles ADMIN_IDS actuels et n'active aucune cadence. Ce chantier n'exécute pas cette commande.

L'autonomie nécessite ensuite une vraie lecture du lot depuis le connecteur cloud, consignée dans AUDIT_LECTURE_CLOUD_REF, puis l'activation explicite du producteur. Une seule automatisation cloud tous les trois jours lit les nouveaux lots et propose cinq axes à valider ; elle reste à configurer séparément. Aucun second calendrier de propositions dans le bot, aucun message à l'équipe, aucune application automatique des propositions.

## Tests

Données fictives seulement : budgets, arrêt sans progrès, timeout, checkpoints, backoff, appels simultanés, export borné, reprise de même plage, changement de cutoff, absence de trou à la frontière, destination non approuvée, schéma absent, relecture, exclusion du texte libre et des UID du transport. Aucun lot réel publié, aucune mutation Sheets ou permission effectuée.
