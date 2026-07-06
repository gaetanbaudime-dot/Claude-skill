---
titre: "Unit economics"
type: concept
cluster: "Finance"
statut: verified
controverse: low
importance: pilier
source_knowledge: internal
sources_count: 2
tags: [finance/rentabilité, pont/marketing]
créé: 2026-07-06
liens_forts: ["[[Rétention et LTV]]", "[[Acquisition de clients]]", "[[Marges et structure de coûts]]"]
liens_opposition: []
---

# Unit economics

> [!info] Résumé
> L'économie unitaire répond à la seule question qui compte avant de scaler : est-ce que je gagne de l'argent sur UNE unité (un client, une commande, une prestation), une fois tous les coûts réellement imputés ? Un business aux unit economics négatives ne se répare pas en volume : il industrialise sa perte.

## Définition

L'unité d'analyse dépend du modèle : le client (SaaS, abonnements, services récurrents), la commande (e-commerce), la mission (agence, freelance). Pour chaque unité, on établit la contribution : revenu de l'unité, moins coûts variables directs (produit, livraison, paiement, support, commissions), moins coût d'acquisition amorti ([[Acquisition de clients|CAC]]). La règle de lecture : la contribution doit être positive et couvrir, en cumul, les coûts fixes ; le trio de contrôle est LTV/CAC (santé du modèle), payback (pression de trésorerie) et marge de contribution (résistance aux chocs).

L'erreur canonique : compter en chiffre d'affaires ce qui doit se compter en marge. Une LTV en CA avec 30% de marge brute est trois fois plus petite qu'elle n'en a l'air, et les décisions prises dessus sont fausses d'autant, voir [[Rétention et LTV]].

## Contexte et origine

Le concept s'est imposé avec l'e-commerce et le SaaS des années 2000-2010, où la croissance à perte financée par le capital-risque a rendu vital de distinguer "perdre de l'argent en construisant un actif" (CAC récupéré en 12 mois sur des cohortes fidèles) de "perdre de l'argent structurellement" (chaque vente détruit de la valeur). Les post-mortems des faillites emblématiques de la période ZIRP tiennent souvent en une phrase : les unit economics n'ont jamais existé, le volume les a cachées.

## Mécanismes

Trois disciplines d'analyse. **Tout imputer** : le CAC complet inclut salaires et outils marketing, pas seulement la publicité ; le coût de service inclut le support et les remboursements ; l'oubli systématique de ces lignes est un [[Biais de confirmation]] comptable, on trouve rentable ce qu'on veut trouver rentable. **Analyser par segment** : les moyennes mentent, un segment rentable subventionne souvent un segment destructeur (petits clients chers à servir, canal à trafic médiocre) ; couper le segment négatif est la plus rapide amélioration de rentabilité qui existe. **Suivre par cohorte** : les unit economics se dégradent ou s'améliorent avec l'échelle (saturation des canaux, effets d'apprentissage) ; la cohorte du mois dit la vérité que le cumul masque.

## Nuances, critiques, limites

Les unit economics peuvent être temporairement négatives par choix rationnel : effets de réseau à amorcer, coûts fixes à amortir sur un volume futur, apprentissage payé d'avance ; la différence entre stratégie et fuite en avant est un plan daté et chiffré de retour à la contribution positive. Deuxième nuance : la granularité a un coût, l'imputation parfaite des coûts partagés est un puits sans fond ; viser l'ordre de grandeur juste plutôt que la précision fausse. Troisième : l'unité peut être mal choisie, un marketplace se lit côté offre ET demande, un produit viral se lit avec le coefficient de parrainage.

## Liens et implications

Les unit economics sont le juge de paix du [[_MOC Marketing|Marketing]] (elles bornent le CAC), l'entrée de la [[Trésorerie]] (le payback dicte le besoin de fonds de roulement) et la base du [[Pricing]] (la marge de contribution encaisse les remises). Modèle de calcul prêt à remplir dans `98-Rapports/Rapport Finance`.

## Sources

[^1]: David Skok, "SaaS Metrics 2.0", forEntrepreneurs.com.
[^2]: Bill Gurley, "The Dangerous Seduction of the Lifetime Value (LTV) Formula", Above the Crowd, 2012.
