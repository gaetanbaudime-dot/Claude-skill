# Schéma YAML du vault

Chaque page de `pages/` porte ce frontmatter. Les champs sont tous obligatoires sauf mention contraire.

```yaml
---
titre: "Nom exact de la page"
type: concept | théorie | personne | expérience | controverse | école | méthode | terme | débat
cluster: "Biais cognitifs"
statut: verified | to-verify | débattu | débunké | hypothétique | stub | à-sourcer
controverse: low | medium | high
importance: pilier | standard | deep-cut
source_knowledge: internal | web-checked | mixed
sources_count: N
tags: [tag1, tag2]
créé: AAAA-MM-JJ
liens_forts: ["[[Page1]]", "[[Page2]]"]
liens_opposition: ["[[Page3]]"]
---
```

## Sémantique des champs

| Champ | Valeurs | Signification |
|---|---|---|
| `type` | concept, théorie, personne, expérience, controverse, école, méthode, terme, débat | Nature de la page, pilote la couleur du graph view |
| `statut` | verified | Faits vérifiés par WebSearch ou consensus stable |
| | to-verify | Un ou plusieurs faits n'ont pas pu être confirmés |
| | débattu | Le phénomène existe mais son interprétation ou son ampleur est contestée |
| | débunké | Réfuté ou non-répliqué par la recherche récente |
| | hypothétique | Proposition théorique sans validation empirique solide |
| | stub | Page squelette à enrichir |
| | à-sourcer | Contenu correct mais footnotes insuffisantes |
| `controverse` | low, medium, high | Intensité du débat scientifique autour du sujet |
| `importance` | pilier, standard, deep-cut | Centralité dans le cluster (priorités 1, 2, 3 du plan) |
| `source_knowledge` | internal | Rédigé depuis le savoir du modèle uniquement |
| | web-checked | Faits clés vérifiés par WebSearch (voir Fact-Check-Log) |
| | mixed | Partiellement vérifié |
| `sources_count` | entier | Nombre de footnotes dans la page |
| `liens_forts` | wikilinks | Pages conceptuellement les plus proches |
| `liens_opposition` | wikilinks | Pages en tension ou en contradiction avec celle-ci |

## Règles de cohérence

1. `type: personne`, `expérience` ou `controverse` implique `sources_count >= 2`, sinon `statut: à-sourcer`.
2. `statut: débunké` implique une section "Nuances, critiques, limites" détaillant la réfutation.
3. `controverse: high` implique au moins un wikilink dans `liens_opposition`.
4. Les tags suivent le format `domaine/sous-domaine` : `concept/heuristique`, `concept/meta-biais`, `personne/psychologue`, `expérience/classique`, `controverse/réplication`, `méthode/intervention`, `école/rationalité`, `débat/épistémologie`, `pont/marketing`, `pont/économie`, etc. Les tags `pont/*` marquent les pages qui connectent le cluster à d'autres domaines.
