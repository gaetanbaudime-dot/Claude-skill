---
titre: "Vitesse de décision"
type: concept
cluster: "Décision business"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 2
tags: [décision/exécution]
créé: 2026-07-06
liens_forts: ["[[Cadres de décision]]", "[[Coût d'opportunité]]"]
liens_opposition: []
---

# Vitesse de décision

> [!info] Résumé
> Dans la plupart des contextes business, la lenteur de décision coûte plus cher que les erreurs de décision : le retard a un coût certain et invisible, l'erreur un coût possible et visible. La règle de Bezos, décider avec ~70% de l'information qu'on voudrait, est un correctif délibéré contre l'asymétrie psychologique qui favorise l'attente.

## Définition

La vitesse de décision est la latence entre l'apparition d'une question et son tranchage effectif. Elle se dégrade par trois mécanismes : la recherche d'information au-delà du point de rendement décroissant (les 30% manquants coûtent plus à obtenir qu'ils n'améliorent le choix), la recherche de consensus au-delà du nécessaire (chaque partie prenante ajoutée est un délai multiplié), et l'évitement pur, la décision différée étant émotionnellement gratuite aujourd'hui et facturée plus tard. Bezos formule le correctif : la plupart des décisions devraient être prises avec environ 70% de l'information souhaitée ; à 90%, on est en retard, et être bon à corriger vite rend l'erreur moins chère qu'on ne le croit[^1].

L'indécision est une décision : celle de maintenir le statu quo en payant le [[Coût d'opportunité]] de toutes les alternatives, sans l'assumer. Le [[Effet de dotation|biais de statu quo]] la rend confortable, l'asymétrie action/inaction la rend socialement sûre (on reproche plus les erreurs commises que les occasions manquées, biais d'omission), et le perfectionnisme la déguise en rigueur.

## Contexte et origine

Le thème traverse la littérature stratégique : la boucle OODA du colonel Boyd (observer, s'orienter, décider, agir), née du combat aérien, pose que l'acteur qui itère sa boucle plus vite que l'adversaire gagne même avec des décisions individuellement moins bonnes ; les travaux d'Eisenhardt sur les équipes dirigeantes en environnements rapides montrent que les décideurs rapides utilisent plus d'information en temps réel et plus d'alternatives simultanées, pas moins, la vitesse venant du parallélisme et non du bâclage[^2].

## Mécanismes

Les pratiques qui achètent de la vitesse sans sacrifier la qualité. **Le tri par réversibilité** d'abord ([[Cadres de décision]]) : 90% des décisions sont des portes à double sens qui méritent des minutes, pas des semaines. **Les délais par défaut** ensuite : toute décision reçoit une échéance à sa naissance ("on tranche vendredi"), l'absence d'échéance étant le mécanisme par lequel les décisions s'entassent. **Le désaccord engagé** ("disagree and commit") : les parties expriment leur désaccord, la décision est prise, tous exécutent ; le consensus intégral est remplacé par la clarté sur qui décide. **Les alternatives simultanées** enfin : évaluer trois options en parallèle décide plus vite qu'évaluer une option en série (accepter/rejeter, puis chercher la suivante), et améliore le choix, résultat robuste d'Eisenhardt.

## Nuances, critiques, limites

La vitesse est une variable à optimiser sous contrainte, pas à maximiser : les décisions de type 1 (irréversibles, à fort enjeu) justifient la lenteur délibérée, et la culture du "move fast" appliquée sans tri produit les catastrophes qu'elle prétend éviter. Deuxième nuance : la vitesse individuelle n'est pas la vitesse organisationnelle, une organisation lente avec des décideurs rapides a un problème de circuits (qui décide quoi, avec quelle autonomie), pas de personnes, voir [[Délégation]]. Troisième : les 70% de Bezos sont une image, pas une mesure ; l'étalonnage honnête est rétrospectif, sur les dix dernières décisions retardées, combien ont bénéficié de l'attente ? L'expérience générale : très peu.

## Liens et implications

La vitesse s'arbitre avec le [[Coût d'opportunité]] (le prix du retard) et se sécurise par les critères de sortie des [[Cadres de décision]] (décider vite se paie en surveillance de la décision, pas en analyse préalable). Auto-diagnostic des décisions en attente dans `98-Rapports/Rapport Décision business`.

## Sources

[^1]: Jeff Bezos, lettre aux actionnaires d'Amazon, 2016.
[^2]: Kathleen M. Eisenhardt, "Making Fast Strategic Decisions in High-Velocity Environments", *Academy of Management Journal*, 1989 ; John Boyd, exposés sur la boucle OODA.
