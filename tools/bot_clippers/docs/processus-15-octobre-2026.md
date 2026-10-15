# Processus clippeur — 15 octobre 2026

## Règles implémentées

Trois comptes Instagram créés au total par UID Discord, jamais réinitialisés après ban ou départ. Croissance 1 immédiatement, croissance 2 après quatre Reels publiés et vérifiés sur croissance 1, privé après quatre sur croissance 2. Aucun délai ni quatre publications supplémentaires sur le premier compte. Les shortcodes datés sont dédupliqués et conservés au renommage ; les anciens agrégats ne prouvent pas des publications.

Le registre SQLite `process_clippeur.sqlite3` conserve identités, alias, créations, réservations, résultats incertains et opérations. Une réservation interrompue consomme sa place ; seule une preuve de non-création permet son annulation. Un historique absent n'est jamais assimilé à zéro. `outils/rapprocher_processus.py` simule par défaut l'import additif d'un historique explicitement revu. Aucun import de production effectué.

Les transactions SQLite arbitrent les allocations concurrentes ; les verrous de fichiers protègent les opérations externes entre processus sur le même volume. Un POST de clone sans réponse reste incertain et interdit un second clone. Après obtention de son ID, chaque étape GAML/MYM/OF peut être reprise. La livraison attend les deux destinations vérifiées, la réserve marquée et un inventaire distant complet prouvant leur unicité. Les doublons historiques sont conservés et bloquent leur réutilisation ; ils ne sont pas réparés automatiquement.

Le quiz est requis. L'onboarding vérifie le team leader configuré, l'accès Drive existant, le rôle équipe et le rôle créatrice. Il respecte les coefficients configurés. Le salon porte l'UID stable, est recherché à distance avant création et ne peut pas être recréé automatiquement après un résultat incertain. Aucun nouveau partage Drive public. Les identifiants sensibles ne sont plus inclus dans le texte automatique des étapes : remise personnelle par le responsable.

Un profil invisible ne prouve ni disponibilité ni ban. La disponibilité exige une preuve récente et référencée issue du formulaire Instagram. Les candidats générés restent à vérifier. Une preuve mail datée distingue appel possible et désactivation définitive ; les anciennes données ambiguës sont conservées. Affichage du dashboard simple : Good vert, Faire appel orange, Ban rouge, À créer blanc ; privé est un type.

Départ : archivage X relu dans GAML, conservation de l'UID et des dus, préparation des lignes Metricool puis exclusion Discord. La préparation n'exécute aucun transfert Metricool. Les liens archivés sont exclus des nouveaux revenus du clippeur et de la réattribution automatique ; les dus historiques restent calculables. Le garde-fou existant sur les sorties automatiques est conservé.

## Vérifications

175 tests Python 3.11 passent : suite existante et scénarios fictifs dans `test_process_15_octobre.py`, `test_process_transactions.py`, `test_process_onboarding.py`, `test_process_adapters.py`. Réservations concurrentes via connexions SQLite distinctes, quatrième compte refusé, événements rejoués, alias, paliers, timeout de salon/clone, refus de rôle, absence de Drive/TL/quiz, reprise MYM/OF, tracking dupliqué distant/historique, départ ordonné et dus conservés. Aucun compte, départ, partage, secret ni inscription réel utilisé.

Compilation Python et `git diff --check` vérifiés. `graphify` et son graphe local sont absents. Les tests avec doublures ne prouvent pas la compatibilité des données réelles ni le fonctionnement en production.

## Production et blocages

Lecture Railway : projet BOT Marketing, environnement production, service Claude-skill ; une réplique, volume `/data`, source `main`, racine `tools/bot_clippers`. Déploiement observé : `a217f2cd-099e-4f61-9a2c-b9ee8d20b5dd`, SUCCESS du 14 octobre. Le merge de main peut déclencher le déploiement sans attendre les checks (`checkSuites: false`). Aucun nouveau déploiement lancé dans ce chantier ; ni duplicateur ni Vercel modifiés.

Avant fusion/déploiement de ce lot complet :

1. Rapprocher les historiques à vie réels, y compris archives et pseudonymes. Une ligne « à créer » ne prouve pas une création. Sauvegarder le volume puis simuler l'import ; ne jamais présumer zéro.
2. Rapprocher les liens déjà attribués avec les nouveaux journaux. Les liens existants sans journal restent bloqués ; l'adoption et la résolution d'un clone incertain exigent une vérification explicite. Vérifier la capacité unique MYM/OF disponible ; ne pas réutiliser les doublons signalés.
3. Vérifier les coefficients, mappings TL, rôles et permissions Drive réels. L'accès OAuth Railway consulté ne fournit que les noms de variables et aucun fichier du volume ; ces preuves n'ont pas pu être obtenues ici.
4. Vérifier les vues des autres apps et du classeur avant de considérer l'affichage global migré. Aucun changement Sheets de production réalisé.

Le déploiement est autorisé par l'utilisateur, mais la compatibilité des données n'est pas encore démontrée : déployer maintenant bloquerait les dossiers non rapprochés. Cette limite n'est pas une demande d'autorisation supplémentaire.

## Retour arrière

Conserver une sauvegarde cohérente SQLite et des JSON avant activation. En cas d'incident, suspendre allocations et sorties avant tout retour de code : l'ancien code ignore le registre. Ne jamais restaurer un ancien compteur par-dessus des réservations/créations plus récentes. Préserver les journaux et rapprocher les opérations externes incertaines avant reprise. Aucune migration destructive incluse.

## Activation compatible validée (complément)

Le flux officiel GitHub a été validé par l'utilisateur pour la seule permission supplémentaire `workflow`. Le commit 54ca803 a passé les 175 tests CI Python 3.12. Le lot compatible ajoute cinq tests (180 localement) et remplace le blocage global de déploiement ci-dessus par les restrictions opérationnelles suivantes :

- Suivi existant, scans, reporting et rémunération courante conservés sans import global. Une lecture d'ancien lien ne l'efface jamais. Une app déjà livrée reste reconnue et peut être rappelée ; aucune première livraison n'est autorisée sans les nouveaux contrôles.
- Un renommage d'un compte déjà lié à l'UID conserve ses alias sous statut inconnu si l'historique est incomplet. Cette observation ne valide jamais l'historique ni une place disponible.
- Onboarding et nouvelles réservations restent bloqués avec alerte explicite si l'historique est incomplet. Aucun remplacement ni quatrième compte, aucun contournement par le reporting.
- Corrections des preuves de ban, publications dédupliquées, paliers 4 + 4 et suppression du délai supplémentaire actives. Les anciens parcours privés en deuxième position restent à examiner, sans créer un autre compte.
- Au démarrage, sauvegarde locale additive des JSON et du registre SQLite éventuel dans `sauvegarde-processus-20261015`, permissions privées, avant les opérations du bot. Le snapshot n'est jamais remplacé. Aucune migration globale ni partage externe.

Accès vérifié : pas de CLI Railway installée, pas de configuration d'authentification CLI locale, pas d'outil SSH/lecture du volume exposé par le connecteur. Aucune nouvelle authentification ou permission Railway demandée. Déployer ce lot n'implique pas que les historiques soient rapprochés ni que le provisionnement réel ait été testé.
