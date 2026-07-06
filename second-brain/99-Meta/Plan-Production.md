# Plan de production multi-clusters

Run de production lancé le 2026-07-06 sur demande : "marketing, finance, OFM, santé, business decision, investissement, recrutement, management humain, scaling, Alex Hormozi + contexte personnel organisé + rapports de synthèse".

## Architecture cible

```
second-brain/
├── _MOC.md                     # MOC maître (index des clusters)
├── 00-Contexte/                # Contexte personnel (profil, projets, insights, coaching)
├── pages/
│   ├── Biais cognitifs/        # Cluster pilote (40 pages, terminé)
│   ├── Marketing/              # + 1 MOC par cluster
│   ├── Finance/
│   ├── OFM/
│   ├── Santé/
│   ├── Décision business/
│   ├── Investissement/
│   ├── Recrutement/
│   ├── Management humain/
│   ├── Scaling/
│   └── Alex Hormozi/
├── 98-Rapports/                # 1 rapport de synthèse actionnable par cluster
└── 99-Meta/                    # Plans, logs, audits, debriefs
```

## Périmètre de ce run

Chaque cluster reçoit ses **pages piliers** (5-6 pages denses, interconnectées), son **MOC**, et son **rapport de synthèse actionnable** dans `98-Rapports/`. Objectif : une fondation navigable et utilisable immédiatement, extensible cluster par cluster lors des prochains runs (le pilote a montré ~40 pages de qualité par session).

La demande "1000 références par sujet" est traitée comme un objectif de long terme : ce run pose l'architecture et les piliers ; chaque session ultérieure densifie un cluster (30-40 pages/session, voir `Debrief.md` du pilote pour les coûts et la méthode multi-agent).

## Statut des clusters

| Cluster | Piliers prévus | Statut |
|---|---|---|
| Biais cognitifs | 40 pages | ✅ terminé (pilote) |
| Marketing | Offre, Acquisition, Copywriting, Tunnel de conversion, Rétention et LTV, Positionnement | ce run |
| Finance | Unit economics, Trésorerie, Pricing, Marges, Lecture des états financiers | ce run |
| OFM | Modèle d'agence, Acquisition de modèles, Chatting, Trafic, Risques légaux et éthiques | ce run |
| Santé | Sommeil, Nutrition, Entraînement, Stress et récupération, Énergie et productivité | ce run |
| Décision business | Cadres de décision, Coût d'opportunité, Espérance et asymétries, Vitesse vs justesse, Pré-mortem | ce run |
| Investissement | Intérêts composés, Allocation d'actifs, Bourse indicielle, Immobilier, Psychologie de l'investisseur | ce run |
| Recrutement | Scorecard, Sourcing, Entretien structuré, Onboarding, Erreurs de casting | ce run |
| Management humain | Motivation, Feedback, Délégation, Culture, Rituels de management | ce run |
| Scaling | Systèmes et process, Théorie des contraintes, Effet de levier, Documentation, Équipe A-players | ce run |
| Alex Hormozi | Alex Hormozi, Grand Slam Offer, Équation de valeur, Core Four (leads), Philosophie volume et compétences | ce run |
| 00-Contexte | Profil, Projets, Insights, Journal de coaching | structure + templates (à nourrir par l'utilisateur) |

## Règles héritées du pilote

Conventions YAML, wikilinks et structure de page identiques (voir `Schema.md`), avec ajustements du Debrief : pages de 500 à 1000 mots, fact-check groupé, section "faits non re-vérifiés" au log. Cluster Santé : contenu général evidence-based uniquement, pas de conseil médical individuel, statuts prudents (le guide du kit déconseille le médical sans validation experte, on reste au niveau hygiène de vie).

## Croisements inter-clusters prévus

Décision business ↔ Biais cognitifs (débiaisage appliqué), Recrutement ↔ Effet de halo et Entretien structuré, Investissement ↔ Aversion à la perte et Excès de confiance, Marketing ↔ Effet de simple exposition, Ancrage, Cadrage, Hormozi ↔ Marketing/Scaling, OFM ↔ Marketing/Management, Santé ↔ Scaling personnel (énergie).
