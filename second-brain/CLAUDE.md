# Second cerveau de Gaëtan : conventions du vault

## Périmètre (mise à jour 2026-07-12 — le vault a dépassé son pilote)

Ce vault n'est plus le pilote « Biais cognitifs » : c'est le **second cerveau complet** de Gaëtan — business (agence OFM LTP Models, objectif 500 K€/mois), vie perso (santé, logement Dubaï, finances), opérations (SOP, recrutement, annonces), plans datés, et une bibliothèque de 12 clusters. La méthode de travail complète est dans la skill `.claude/skills/second-brain/SKILL.md` et son miroir lisible `99-Meta/Méthode de travail Claude.md`.

## Arborescence

- `_MOC.md` : index maître orienté action — à lire en premier.
- `00-Contexte/` : profil, hub business ([[LTP Models]] = première lecture), projets, insights, [[Journal de coaching]] (toute décision s'y journalise avec prédiction datée).
- `95-Vie perso/` · `96-Opérations LTP/` · `97-Plan Maître/` · `98-Rapports/` · `99-Meta/`.
- `pages/<Cluster>/` : la bibliothèque (Alex Hormozi, Biais cognitifs, Décision business, Finance, Investissement, Livres, Management humain, Marketing, OFM, Recrutement, Santé, Scaling), un `_MOC` par cluster.

## Conventions

- **Langue** : français intégral (contenu, titres, YAML, tags, commits). Jargon plateforme conservé uniquement s'il est d'usage chez Gaëtan (SFS, MOD, PPV, push, KPI, SOP, LTV, pod, warmup) ; titres d'œuvres conservés.
- **Style** : verdict d'abord (callout `> [!tip] Verdict` pour l'action, `> [!info] Résumé` pour la théorie), dense, phrases complètes, tableaux pour les chiffres, tutoiement direct.
- **YAML** : schéma dans `99-Meta/Schema.md` — titre, type, cluster, statut, créé, tags (max 5, français), liens_forts ; pages bibliothèque : + controverse, importance, source_knowledge, sources_count, liens_opposition.
- **Wikilinks** : 7-12 sortants par page, intégrés dans des phrases qui les justifient, cross-linkés dans les deux sens ; jamais de listing brut hors `_MOC`.
- **Sources** : footnotes (`[^1]:`), minimum 2 pour les pages sensibles.
- **Application LTP** : chaque page théorique dit ce qu'elle change dans SON business, avec ses chiffres réels.

## Règles d'édition

1. Fusionner plutôt que dupliquer : vérifier `_MOC.md` et le MOC du cluster avant de créer une page.
2. Aucun nom, date, chiffre ou citation non vérifié : `statut: to-verify` + mention dans le corps.
3. Théorie débunkée ou contestée : le dire frontalement (`statut: débunké` ou `débattu`).
4. Corrections factuelles consignées dans `99-Meta/Fact-Check-Log.md`.
5. Données volatiles datées dans le texte (« à jour 2026-07-XX »).
6. Chaque MOC garde sa section « À densifier lors des prochains runs » à jour.

## Sécurité (avant chaque commit)

Créatrices par nom de scène/prénom d'usage uniquement (jamais de handles réels ni de noms légaux), équipe par prénoms, jamais de téléphones/emails/IDs/adresses, jamais de raw exports commités (distiller au scratchpad puis supprimer). Scan PII sur les fichiers modifiés + audit wikilinks (zéro lien fantôme) avant commit. Commits en français, descriptifs.
