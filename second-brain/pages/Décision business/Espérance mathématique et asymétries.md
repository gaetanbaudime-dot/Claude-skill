---
titre: "Espérance mathématique et asymétries"
type: concept
cluster: "Décision business"
statut: verified
controverse: low
importance: pilier
source_knowledge: internal
sources_count: 3
tags: [décision/probabilités, pont/investissement]
créé: 2026-07-06
liens_forts: ["[[Cadres de décision]]", "[[Théorie des perspectives]]", "[[Psychologie de l'investisseur]]"]
liens_opposition: []
---

# Espérance mathématique et asymétries

> [!info] Résumé
> Penser en espérance (probabilité × gain, sommé sur les issues) est le B.A.-BA du raisonnement décisionnel ; penser en asymétries (chercher les paris à perte bornée et gain non borné) en est l'étage supérieur. Le business bien joué consiste à prendre beaucoup de petits paris asymétriques et à éviter les risques de ruine, même à espérance positive.

## Définition

L'espérance mathématique (EV) d'une décision est la moyenne pondérée de ses issues : un pari à 30% de chances de gagner 100k€ et 70% de perdre 20k€ vaut 0,3×100 − 0,7×20 = +16k€. Décider en EV, c'est accepter de perdre souvent pour gagner en moyenne, ce qui exige de dissocier qualité de la décision et résultat d'un coup (le "resulting" d'Annie Duke, voir [[Cadres de décision]]).

Deux correctifs indispensables rendent l'EV utilisable dans la vraie vie. **Le risque de ruine** : une EV positive ne justifie jamais un pari qui peut tuer le joueur (faillite, réputation détruite, santé) ; la ruine interdit de rejouer, donc les moyennes ne s'appliquent plus, argument central de Taleb et fondement du critère de Kelly en dimensionnement de mise[^1]. **L'asymétrie** : les meilleures décisions ont un profil convexe, perte maximale petite et connue, gain potentiel grand et non borné, contenu du "barbell" de Taleb et de l'optionalité ; l'entrepreneur rationnel collectionne ces options (tester un canal à 1k€, écrire en public, rencontrer des gens) et fuit leur inverse, gain petit et borné contre perte potentielle énorme (économiser sur l'assurance, le juridique, les sauvegardes).

## Contexte et origine

L'EV vient de la théorie des probabilités classique (Pascal, Bernoulli, qui la corrige déjà en utilité logarithmique pour expliquer pourquoi on refuse des paris EV-positifs trop risqués). La [[Théorie des perspectives]] documente comment l'humain s'en écarte systématiquement : surpondération des petites probabilités, [[Aversion à la perte]], recherche de risque dans les pertes. Taleb (*Fooled by Randomness*, *Antifragile*) a popularisé la pensée par asymétries et le primat du risque de ruine ; Kelly (1956) a formalisé la taille de mise optimale en croissance composée.

## Mécanismes

En pratique, trois disciplines. **Expliciter les probabilités** : remplacer "je pense que ça peut marcher" par un chiffre et un intervalle force la confrontation ultérieure avec le réel et calibre le jugement, l'entraînement documenté des superforecasters de Tetlock ([[Débiaisage]]). **Décomposer les issues** : lister les 3-5 scénarios avec leurs valeurs, y compris le pire crédible ; la [[Le problème de Linda|erreur de conjonction]] rappelle que les scénarios détaillés séduisent en devenant moins probables, décomposer proprement protège. **Dimensionner la mise** : la question n'est pas seulement "ce pari est-il bon ?" mais "quelle fraction de mes ressources y engager ?" ; sur-miser un bon pari est la façon la plus élégante de faire faillite, leçon de Kelly que les fondateurs apprennent cher.

L'asymétrie a une conséquence organisationnelle : multiplier les petits tests bon marché (chaque test est une option achetée) et ne scaler que les gagnants, exactement la logique du pilote de 40 pages avant les 500 de ce vault, ou du budget test avant le budget de campagne.

## Nuances, critiques, limites

L'EV suppose des probabilités estimables : dans l'incertitude radicale (marchés nouveaux, ruptures), les chiffres sont des costumes sur de l'ignorance, et les heuristiques robustes de la [[Rationalité écologique]] (règles simples, marges de sécurité) font mieux que la fausse précision, distinction risque/incertitude qui remonte à Knight. Deuxième nuance : l'utilité n'est pas linéaire, perdre 50k€ ne vaut pas −50k€ pour tout le monde ; l'EV se raisonne en utilité (ou en logarithme de la richesse) dès que les montants sont significatifs par rapport au patrimoine. Troisième : les probabilités subjectives héritent de tous les biais du cluster voisin, [[Excès de confiance|surprécision]] en tête ; sans calibration (prédictions écrites, revues), penser "en EV" revient souvent à maquiller son intuition en mathématiques.

## Liens et implications

Ce cadre alimente les [[Cadres de décision]] (le calcul derrière le tri), l'[[Psychologie de l'investisseur|investissement]] (où l'asymétrie et la ruine dominent tout), et la lecture du [[Grand Slam Offer]] côté vendeur (la garantie est un transfert d'asymétrie). Exercice de calibration et registre de paris dans `98-Rapports/Rapport Décision business` et [[Journal de coaching]].

## Sources

[^1]: Nassim Nicholas Taleb, *Fooled by Randomness* (2001), *Antifragile* (2012) ; J. L. Kelly, "A New Interpretation of Information Rate", 1956.
[^2]: Annie Duke, *Thinking in Bets*, 2018.
[^3]: Philip Tetlock, Dan Gardner, *Superforecasting*, 2015.
