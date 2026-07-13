# Debrief du run de production multi-clusters

Run du 2026-07-06, à la suite du pilote (voir `Debrief.md`). Demande : 10 clusters (marketing, finance, OFM, santé, décision, investissement, recrutement, management, scaling, Hormozi) + contexte personnel + rapports de synthèse, en full-auto.

## Livré

- 10 nouveaux clusters : 48 pages piliers (500-900 mots, YAML conforme, sourcées), 10 MOC de cluster, 10 rapports de synthèse actionnables (`98-Rapports/`).
- Réorganisation hiérarchique : `pages/<Cluster>/`, MOC maître refondu, hub [[Biais cognitifs]], README et conventions à jour.
- Cluster `00-Contexte` : structure profil/projets/insights/coaching, prête à être nourrie (Claude n'a pas accès aux conversations claude.ai ; le contexte doit être collé en session ou édité dans le vault).
- Totaux vault : ~115 pages, ~71 500 mots, ~1 670 wikilinks, 0 fantôme après correction (4 fantômes détectés et corrigés en consolidation), 0 orpheline structurelle.

## Écarts assumés vs demande

- **"1000 références par sujet"** : infaisable en une session (≈10 000 pages). Livré : les piliers + l'architecture d'extension ; chaque MOC liste ses pistes de densification, cadence réaliste 30-40 pages/cluster/session.
- **Fact-checking web** : contrairement au pilote (14 recherches), ce run s'appuie sur le savoir interne pour des contenus de synthèse à faible risque factuel (cadres classiques, littérature établie), les références étant des ouvrages et études canoniques. Les pages à chiffres sensibles signalent leurs incertitudes dans le texte. Pour une densification à visée de référence publique, réactiver le protocole WebSearch du pilote.
- **Santé** : borné à l'hygiène de vie evidence-based, conformément au guide du kit (pas de médical sans validation experte).
- **OFM** : traité en modèle d'affaires avec page risques légaux/éthiques en lecture conditionnelle du cluster, les pratiques du secteur l'exigeant.

## Ce qui a bien marché

- Le croisement inter-clusters est la vraie valeur ajoutée de ce run : chaque cluster business est câblé sur le cluster Biais cognitifs (entretien structuré ← halo, pricing ← ancrage, investissement ← aversion à la perte...), ce qu'aucune génération cluster-par-cluster isolée n'aurait produit.
- Les rapports de synthèse (98-Rapports) répondent au besoin "utilisable" mieux que les pages : checklists, grilles, protocoles.
- Le commit-push par cluster a rendu le run résilient aux coupures de session, et le vault arrivait dans Obsidian au fil de l'eau via l'auto-pull.

## À faire au prochain run (recommandé dans l'ordre)

1. Nourrir `00-Contexte` (coller contexte, projets, objectifs) : c'est le multiplicateur de toutes les sessions futures.
2. Densifier le cluster prioritaire pour ton business du moment (30-40 pages, avec fact-check web réactivé).
3. Rapport croisé sur mesure (ex. "plan 90 jours" croisant Décision + Marketing + Santé sur tes objectifs réels).
4. Envisager la fusion vers `main` pour simplifier la synchro.

---

## Suite 13/07 — bascule en phase « données réelles » (les 4 points ci-dessus sont faits)

Depuis ce debrief, le vault a changé de nature. Les 4 recommandations sont traitées : `00-Contexte` est **nourri des vrais chiffres** (roster, CA MYM/OF par créatrice, 3 comptes bancaires sur 5 ans, 126k messages de chat, structure d'équipe), le cluster prioritaire (OFM/Opérations) est densifié, plusieurs rapports croisés sur mesure existent ([[Analyse dashboard OFM (13 juillet 2026)]], [[Analyse finances perso (13 juillet 2026)]], [[Plan Maître 500K]]), et la branche a été **fusionnée dans `main`**.

### Ce qui a marché (à reproduire)

- **La donnée réelle bat le savoir générique, à chaque fois.** Le tournant du vault, c'est le jour où Gaëtan a collé ses vrais exports. Une analyse de SES 126k messages / SON roster / SES 3 comptes vaut dix deep research « marché OFM ». Cf. [[Croisement des deep research marché OFM]] : les 3 rapports de marché, écrits à l'aveugle, se sont révélés être surtout un **déclencheur** pour produire la vraie donnée. **Leçon skill** : réclamer la donnée réelle avant d'écrire ; ne jamais citer un chiffre de marché générique comme un fait.
- **Les sub-agents par tâche isolée** (1 agent = 1 relevé bancaire) ont bien tenu : parallélisables, chacun avec un périmètre net, synthèse fusionnée ensuite. Le bon usage du multi-agent = **un jeu de données lourd et séparable par agent**, pas « écris-moi 3 pages ».
- **Le verdict-first callout + tout chiffrer** : c'est ce que Gaëtan lit en premier et ce sur quoi il agit. Les pages sans verdict chiffré en tête sont ignorées.
- **Le journal de coaching avec prédiction datée** : posé sur la trésorerie (« coffre avant 1 août → >20k avant 30 sept »), c'est le mécanisme qui rend le coaching falsifiable.

### Ce qui a coincé (à corriger dans la méthode)

- **Les pièces jointes hors-repo (xlsx, Google Sheet) sont fragiles.** Un upload base64 tronqué a échoué ; les formules GOOGLEFINANCE ont cassé à l'import CSV (locale FR). **Leçon** : pour les artefacts externes, préférer une **recette manuelle courte** que l'utilisateur exécute chez lui à un fichier généré fragile ; les chiffres sensibles restent dans SON Drive, jamais dans le repo.
- **Le PII des fans** : Gaëtan pensait que « tout le monde a un pseudo », mais beaucoup de top-fans sont des noms réels complets. J'ai maintenu l'anonymisation contre sa demande initiale (RGPD + contenu adulte = risque réel). **Leçon skill** : le lookup pseudo↔nom réel des fans reste dans son outil ops (Infloww), jamais dans le vault.
- **Juger sur le mauvais canal** : Amanda était classée « à couper » sur sa LTV MYM alors qu'elle est n°1 OF ($38k). **Leçon** : ne jamais trancher sur une créatrice sans croiser TOUS ses canaux.

### Le seul gros manque ops identifié (prochain run)

**La SOP chatting « anti-churn »** : séquence de bienvenue automatisée, 1er PPV < 48h, relance win-back sur chaque désabo, clonage des scripts du top 5 chatteurs. C'est le levier n°1 confirmé à la fois par les données (48 % du CA = médias privés) et par les 3 deep research. À densifier dans [[Opérations de chatting]].
