# Accueil TL, support et diagnostic privé

Lot séparé de PR34, basé sur son commit corrigé 2f5c752. Aucune modification de l'iframe PR35.

## Application

L'accueil des team leaders utilise l'onglet Équipe existant, avec trois vues : À traiter, Équipe, Résultats. Les utilisateurs sans rôle TL n'obtiennent aucun nouvel accès. Les routes authentifiées restent les mêmes. Les visites manquantes et primes indisponibles restent inconnues. Les états sont affichés Good vert, Faire appel orange, Ban rouge, À créer blanc ; PRIVE reste un type à vérifier et non un état de santé. Les détails des comptes sont repliables. Marge/J30 restent non mesurés.

## Support

Un ticket SQLite par UID et catégorie de problème ouverte conserve uniquement les IDs des messages sources et le nombre de pièces jointes, jamais leurs contenus. La notification d'équipe renvoie au message Discord existant, avec problème, conséquence et action. Un nouveau signalement enrichit le ticket sans nouvelle notification tant que le ticket est ouvert, y compris après redémarrage.

La livraison confirmée est enregistrée après l'envoi. Un timeout reste `envoi_incertain` : pas de prétention « transmis », ni renvoi automatique susceptible de doubler la notification. Une absence de canal reste `a_envoyer` et peut être retentée au prochain signalement. L'admin vérifie les liens avec ses droits actuels et prend en charge le problème. Aucune résolution automatique n'est déduite d'un silence.

Commandes ADMIN_IDS uniquement, réponses en MP : `!support UID` liste les tickets et références ; `!support-resolu UID numéro_ticket` clôt le ticket après vérification humaine. Un nouveau problème de même catégorie peut alors rouvrir un ticket. Le contexte privé de l'assistant lui indique les tickets et preuves déjà reçus pour éviter une nouvelle demande. Les fautes proches des commandes clippeur donnent une suggestion sans exécuter d'ordre ni recopier les arguments.

## Diagnostic exploitable sans transfert de secrets

Après la collecte revue de PR34 : `!audit-discussions diagnostic` envoie en MP administrateur un JSON de catégories fermées, dates, IDs Discord et références de messages. Aucun contenu libre, nom, embed ou pièce jointe n'est repris, même si la base contenait un texte insuffisamment nettoyé. Les catégories signalent des sujets et non des états confirmés. Maximum 1000 messages par lot ; la réponse donne `!audit-discussions diagnostic CURSEUR` si une suite existe.

L'administrateur peut joindre ce JSON à la conversation d'analyse ; les outils du présent environnement n'ont pas de lecteur de volume Railway. Pas de nouvel endpoint, secret, accès permanent ou publication publique. Les références Discord permettent une vérification humaine avec les droits existants. Cette voie permet l'analyse de récurrences sans transférer les conversations.

## Validation

Tests fictifs : concurrence/dédoublonnage, envoi incertain, reprise, clôture ciblée, contrôle ADMIN_IDS, suggestion sans fuite d'arguments, diagnostic sans texte libre et curseur. Compilation Python et build Next.js. Aucun appel réel Discord, aucun message réel, aucune migration destructive, aucun élargissement de droits. Inspection navigateur non effectuée : ce poste est réservé à l'autre tâche.

## Corrections de revue support

Un refus HTTP 4xx certain (hors 408) remet la notification en `a_envoyer` : le prochain signalement peut la retenter. Timeout, 408 et 5xx restent `envoi_incertain`. Après contrôle de non-livraison, l'administrateur peut utiliser `!support-reprendre UID ticket confirme-non-livre` ; une notification déjà transmise ne peut pas être renvoyée par cette commande.

Chaque suivi du même auteur dans le même salon conserve la référence et le nombre de pièces jointes, même sans répéter le motif. Avec plusieurs tickets ouverts, le rattachement est explicitement contextuel et doit être vérifié ; il n'affirme pas que la pièce prouve chaque problème. Aucun contenu ou URL de pièce jointe n'est copié.

Les escalades de l'assistant IA utilisent désormais les mêmes tickets et la même livraison vérifiée. Une confirmation visible dépend du retour réel ; refus et timeout ne peuvent plus produire « transmis ». Les variantes de formulation du modèle passent par cette vérification. Les demandes en MP ne recopient pas leur contenu dans le salon d'équipe.
