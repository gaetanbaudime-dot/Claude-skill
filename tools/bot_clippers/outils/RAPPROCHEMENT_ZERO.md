# Rapprochement zéro propriétaire

Commande désactivée par défaut. Après revue, configurer `RAPPROCHEMENT_ZERO_UIDS` avec les deux UID concernés, séparés par une virgule. Aucune identité réelle dans le dépôt. Plus de deux UID ferme le périmètre. Aucun nouveau rôle, endpoint ou accès au volume.

Le propriétaire du serveur, également présent dans `ADMIN_IDS`, confirme le total de comptes créés depuis toujours avec `!rapprocher-zero UID confirme-zero`. Le message Discord, son auteur et sa date constituent la nouvelle preuve propriétaire sourcée ; les références du registre antérieur sont conservées. La commande ne reprend pas une déclaration rapportée par un tiers.

Les six sources JSON et le registre doivent déjà être présents et lisibles. Tout compte SQLite, même annulé, toute réservation, livraison, ressource ou opération associée interdit le zéro. Une sauvegarde privée des sources et du registre est obligatoire, synchronisée sur disque et relue. Les JSON sont relus après sauvegarde ; SQLite est verrouillé pendant la transaction. Aucun fichier historique n'est supprimé.

Après succès, l'allocation et la reprise automatique restent bloquées. Une commande `!creatrice UID Prénom` séparée, autorisée par les contrôles existants, est nécessaire. Ne lancer cette reprise qu'après vérification du TL attendu, de la créatrice et de la preuve récente de disponibilité du pseudo. Un blocage conserve les données pour revue ; ne pas utiliser `forcer` pour contourner un prérequis.

La commande historique d'import CLI refuse désormais les listes de comptes vides. L'API interne `Store.reconcile` reste disponible pour les imports historiques et les tests : ce n'est pas une commande propriétaire.

## Vérifications avant reprise

Le bot bloque automatiquement sans quiz réussi, historique rapproché, rôle créatrice cohérent, TL résolvable et présent, Drive résolvable, capacité à vie ou preuve récente de disponibilité du pseudo. L'ajout d'un TL sans accès à un salon déjà non vide est également retenu. La preuve de pseudo est vérifiée avant envoi ; une réservation peut déjà exister à ce stade.

Le bot ne compare pas le TL résolu à une décision humaine externe : vérifier son identité attendue manuellement. La disponibilité réelle doit être vérifiée dans le formulaire Instagram ; un profil invisible ne suffit pas. Le bot valide la provenance et la fraîcheur enregistrées, sans effectuer cette vérification externe lui-même.
