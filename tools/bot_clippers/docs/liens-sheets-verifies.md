# Restitution Sheets — contrat proposé, non déployé

Cette branche est distincte de PR 37. Ne pas fusionner avant coordination avec l'unique éditeur Sheets et contre-vérification. Aucun batch réel, création GAML, partage ou compte réel exécuté pour les tests.

## Colonnes du Dashboard généré

A:K conservées : Gérant, @ IG, ETAT, Followers, Reels hier, Reels 7 j, Vues 7 j, Clics hier, Clics 7 j, Évolution clics, Team Leader.

Ajouts : L = Type de compte ; M = Qualité / vérification. Les valeurs de ETAT sont GOOD, Faire appel, Ban, À créer, dans cet ordre et vert/orange/rouge/blanc. Une santé inconnue laisse ETAT vide ; PRIVE produit Type de compte = Privé et une demande de vérification en M. WARMUP n'est pas converti implicitement en GOOD. Les valeurs ambiguës des sources ne sont pas effacées.

Le tri porte seulement sur les lignes générées : POD contigus par créatrice, classés par leur meilleur état (GOOD, appel, Ban, puis entièrement À créer), puis comptes triés à l’intérieur du POD ; les inconnus restent signalés. Le gérant et le TL sont répétés sur les lignes pour éviter les fusions à travers plusieurs états ; les clics restent affichés une fois par groupe. Aucune source ni référence de ligne source n'est déplacée.

## Trois liens sur les lignes attribuées

La synchronisation périodique existante reprend les jobs GAML prêts. Elle relit le clone (un GET par job), son activation et ses deux destinations, les réservations exclusives MYM/OF, le propriétaire SQLite et l'attribution courante par UID. Aucun rapprochement par prénom. Une reprise ne passe jamais par la création de lien.

Chaque ligne est retrouvée par pseudo exact et onglet après relecture. Les champs Lien GAML associé, Lien MYM et Lien Infloww Tracking sont remplis seulement s'ils sont vides ; les valeurs identiques ne sont pas réécrites. Toute valeur divergente, colonne manquante, fusion ou attribution ambiguë bloque le lot de cette ligne et produit un code de conflit au journal. L'ancienne synchronisation GAML est neutralisée pour toutes les lignes : sans job vérifié, les données restent intactes et le contrôle renvoie historique_sans_job_verifie.

Un verrou interprocessus exclut une allocation ou un départ simultané pendant la synchronisation. Les valeurs sont relues après écriture ; une réponse incertaine se reprend par lecture, sans re-clonage. Aucun effacement compensatoire.

Limite API : Sheets ne fournit pas ici de compare-and-swap. Il reste une fenêtre entre dernière relecture et écriture ; le worker humain/cloud ne doit pas modifier simultanément ces mêmes cellules. Les liens historiques sans job vérifié ne sont pas rapprochés automatiquement. Les cellules fusionnées de liens demandent une décision explicite, elles ne sont pas défusionnées par cette synchronisation.

## Corrections après revue

Une ancienne fiche onboarding et le propriétaire SQLite ne prouvent pas le détenteur courant de la ligne. Le registre doit porter une liaison explicitement attestée `attribution-sheet:<onglet>:<handle_normalisé>` avec `uid`, `gerant` exact, `creatrice` canonique et `preuve`. Aucune liaison n’est inventée ou créée automatiquement ici. En son absence, la restitution bloque ; une attribution changée Alice → Bob bloque également. Un changement légitime de libellé nécessite une nouvelle attestation.

Créatrice : égalité canonique normalisée, ou entrée `alias-creatrice:<libellé_normalisé>` avec `canonique` et `preuve` explicites. Sarah2 n’est jamais un préfixe accepté pour Sarah.

Les fusions sont relues strictement, avec présence obligatoire de chaque onglet ; toute intersection horizontale ou verticale avec une cellule cible bloque. Une panne bloque aussi. Les vues gid 1900160410 et 1900160402 sont interdites au générateur Dashboard, même renommées. La configuration réelle ONGLET_DASHBOARD et son gid devront être contrôlés avant déploiement ; aucune activation autorisée par ce document.

## POD et mesures

Un POD attendu correspond à trois IG, deux croissance et un privé, et un lien GAML avec destinations MYM/OF uniques. Les écarts historiques de nombre, de types ou de liens sont signalés séparément, sans suppression ni réattribution. Le type est explicite ou reste À vérifier ; aucun pseudo ne suffit à inventer un type.

Followers et Reels restent par compte. Les clics sont affichés une seule fois par groupe et chaque identifiant GAML est dédupliqué avant somme. Les périodes sont visibles (J−7 à J−1 inclus, Paris), le nombre zéro reste distinct de Non relevé. Le calcul existant fournit des visites GAML payables issues de clics.json/paie_clics.clics_lien, et non les visites brutes GAML ; le libellé de contexte l’explicite. Aucune donnée manquante d’historique à vie n’est convertie en zéro.

Contrôle réel en lecture seule : Dashboard gid 569057685 ; vues protégées Comptes · Pilotage live gid 1900160410 et Clippers · Règles gid 1900160402. Railway ne définit pas ONGLET_DASHBOARD, donc nom par défaut Dashboard. L’identifiant du classeur configuré reste masqué par le connecteur et doit encore être confirmé avant déploiement.

La garde d’exécution compare maintenant le classeur configuré au seul classeur autorisé et le gid résolu à 569057685. Toute divergence, onglet absent ou métadonnée illisible arrête le générateur sans mutation ni création d’onglet, avec un diagnostic fermé non sensible. La garde précède aussi les mises à jour associées lancées par ecrire. Les deux gid des vues cloud restent explicitement interdits.
