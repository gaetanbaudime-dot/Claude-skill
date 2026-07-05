# Vault pilote : Biais cognitifs

## Périmètre

- **Sujet global** : Psychologie
- **Cluster ciblé** : Biais cognitifs
- **Périmètre** : erreurs systématiques de jugement documentées par la recherche en psychologie cognitive, de Kahneman/Tversky à aujourd'hui. Inclut les biais classiques, les biais débattus (réplicabilité incertaine), les meta-biais et les débats d'école (Kahneman vs Gigerenzer). Exclut les biais purement motivationnels (freudiens, psychanalytiques) et les biais de perception sensorielle (illusions d'optique). Niveau : recherche académique mais accessible.

## Conventions

- **Langue** : français intégral (contenu, titres, YAML, tags). Terminologie anglaise conservée dans le corps uniquement quand c'est le nom consacré d'un concept.
- **YAML** : schéma détaillé dans `99-Meta/Schema.md`. Champs obligatoires : titre, type, cluster, statut, controverse, importance, source_knowledge, sources_count, tags, créé, liens_forts, liens_opposition.
- **Wikilinks** : `[[Page exacte]]` ou `[[Page|alias]]`, toujours intégrés dans une phrase complète qui les justifie. Jamais de listing brut hors `_MOC.md`. Cible : 7 à 12 wikilinks sortants par page.
- **Sources** : footnotes Markdown (`[^1]:` Auteur, *Titre*, Éditeur/Revue, année, URL si dispo). Minimum 2 sources pour les pages sensibles (personne, expérience, controverse).
- **Nommage** : titres en français naturel avec accents, espaces autorisés, pas de préfixes numérotés.
- **Tags** : minuscules, français, préfixe thématique (ex : `#concept/heuristique`, `#personne/psychologue`), max 5 par page.

## Règles d'édition future

1. Toute nouvelle page respecte la structure imposée : Résumé (callout) / Définition / Contexte et origine / Mécanismes / Nuances, critiques, limites / Liens et implications / Sources.
2. Aucun nom propre, date, chiffre ou citation non vérifié : statut `to-verify` et mention explicite dans le corps si le doute subsiste.
3. Théorie débunkée ou non-répliquée : le dire frontalement dans le texte et dans le YAML (`statut: débunké` ou `débattu`).
4. Toute correction factuelle est consignée dans `99-Meta/Fact-Check-Log.md`, section "Auto-corrections".
5. Fusionner plutôt que dupliquer : avant de créer une page, vérifier `_MOC.md` et `99-Meta/Plan.md`.
