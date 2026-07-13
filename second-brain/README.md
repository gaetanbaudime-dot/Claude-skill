# Second cerveau : vault multi-clusters

Base de connaissances Obsidian générée et maintenue par Claude Code (pattern "Knowledge Vault Generator" : compiler une fois, réutiliser toujours), étendue du pilote Biais cognitifs à 11 clusters.

- **Point d'entrée** : [[_MOC]] (Map of Content maître)
- **Conventions** : `CLAUDE.md` et `99-Meta/Schema.md`
- **Rapports actionnables** : dossier `98-Rapports/` (un par cluster)
- **Contexte personnel** : dossier `00-Contexte/` (à nourrir)

## Stats du vault (2026-07-06)

| Indicateur | Valeur |
|---|---|
| Clusters | 11 + contexte personnel |
| Pages de contenu | ~115 |
| Mots | ~71 500 |
| Wikilinks | ~1 670 |
| Rapports de synthèse | 10 |
| Statuts épistémiques | verified / débattu / débunké, par page (YAML) |

## Structure

```
_MOC.md              → index maître (action-first)
00-Contexte/         → profil, LTP Models, projets, insights, journal de coaching
95-Vie perso/        → santé, logement, finances perso, fiscalité, focus
96-Opérations LTP/   → SOP, scorecards, annonces, checklists (la couche exécution)
97-Plan Maître/      → 3 pages : Plan Maître 500K (stratégie par gates) + Sprint été (exécution) + Se licencier de son propre poste (organisation)
pages/<Cluster>/     → pages + _MOC par cluster (12 clusters dont Livres)
98-Rapports/         → rapports de synthèse actionnables + analyses chiffrées datées
99-Meta/             → plans, schéma YAML, fact-check log, audit, debriefs, méthode
```

## Utilisation

1. Ouvrir ce dossier comme vault dans Obsidian ; Graph view coloré par type préconfiguré (`.obsidian/graph.json`).
2. Naviguer depuis [[_MOC]], ou par cluster via les `_MOC <Cluster>`.
3. Synchronisation : le vault est un dépôt Git ; le plugin Obsidian Git (auto-pull) reçoit les mises à jour poussées par Claude.

## Extension

Chaque MOC de cluster liste ses pistes "à densifier". Une session Claude ≈ 30-40 pages de qualité. Méthode, conventions et coûts : `99-Meta/Plan-Production.md` et `99-Meta/Debrief-Production.md`.
