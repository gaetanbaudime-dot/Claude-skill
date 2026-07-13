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

## Statut des clusters (mis à jour 2026-07-13)

> [!info] Les 11 clusters de bibliothèque sont livrés. Le vault a changé de phase : de « poser la bibliothèque » à « piloter le business sur les vraies données ». Le travail actif s'est déplacé vers `95-Vie perso/`, `96-Opérations LTP/`, `97-Plan Maître/` et `98-Rapports/` (voir [[Debrief-Production]], section « Suite 13/07 »).

| Cluster | Piliers prévus | Statut |
|---|---|---|
| Biais cognitifs | 40 pages | ✅ terminé (pilote) |
| Marketing | Offre, Acquisition, Copywriting, Tunnel de conversion, Rétention et LTV, Positionnement | ✅ livré |
| Finance | Unit economics, Trésorerie, Pricing, Marges, Lecture des états financiers | ✅ livré |
| OFM | Modèle d'agence, Acquisition de modèles, Chatting, Trafic, Risques légaux et éthiques | ✅ livré |
| Santé | Sommeil, Nutrition, Entraînement, Stress et récupération, Énergie et productivité | ✅ livré |
| Décision business | Cadres de décision, Coût d'opportunité, Espérance et asymétries, Vitesse vs justesse, Pré-mortem | ✅ livré |
| Investissement | Intérêts composés, Allocation d'actifs, Bourse indicielle, Immobilier, Psychologie de l'investisseur | ✅ livré |
| Recrutement | Scorecard, Sourcing, Entretien structuré, Onboarding, Erreurs de casting | ✅ livré |
| Management humain | Motivation, Feedback, Délégation, Culture, Rituels de management | ✅ livré |
| Scaling | Systèmes et process, Théorie des contraintes, Effet de levier, Documentation, Équipe A-players | ✅ livré |
| Alex Hormozi | Alex Hormozi, Grand Slam Offer, Équation de valeur, Core Four (leads), Philosophie volume et compétences | ✅ livré |
| **Livres** | Who, Buy Back Your Time, E-Myth, The One Thing, Deep Work, Principles, Brunson, Leila Hormozi | ✅ ajouté (hors plan initial) |
| 00-Contexte | Profil, Projets, Insights, Journal de coaching | ✅ **nourri en données réelles** (roster, CA MYM/OF, 3 comptes bancaires, 126k messages, équipe) — [[LTP Models]] réécrit sur les vrais chiffres |

## Règles héritées du pilote

Conventions YAML, wikilinks et structure de page identiques (voir `Schema.md`), avec ajustements du Debrief : pages de 500 à 1000 mots, fact-check groupé, section "faits non re-vérifiés" au log. Cluster Santé : contenu général evidence-based uniquement, pas de conseil médical individuel, statuts prudents (le guide du kit déconseille le médical sans validation experte, on reste au niveau hygiène de vie).

## Croisements inter-clusters prévus

Décision business ↔ Biais cognitifs (débiaisage appliqué), Recrutement ↔ Effet de halo et Entretien structuré, Investissement ↔ Aversion à la perte et Excès de confiance, Marketing ↔ Effet de simple exposition, Ancrage, Cadrage, Hormozi ↔ Marketing/Scaling, OFM ↔ Marketing/Management, Santé ↔ Scaling personnel (énergie).
