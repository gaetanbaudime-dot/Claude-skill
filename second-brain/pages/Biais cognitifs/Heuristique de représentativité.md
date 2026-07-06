---
titre: "Heuristique de représentativité"
type: concept
cluster: "Biais cognitifs"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 3
tags: [concept/heuristique, concept/probabilités]
créé: 2026-07-05
liens_forts: ["[[Le problème de Linda]]", "[[Heuristique de disponibilité]]", "[[Le programme heuristiques et biais]]"]
liens_opposition: []
---

# Heuristique de représentativité

> [!info] Résumé
> Juger la probabilité qu'un cas appartienne à une catégorie par sa ressemblance au prototype de la catégorie, en ignorant les taux de base et la taille des échantillons. Première des trois heuristiques fondatrices, elle engendre certaines des erreurs probabilistes les plus spectaculaires du cluster.

## Définition

La représentativité substitue une question de similarité à une question de probabilité : "Steve, timide et ordonné, est-il plus probablement bibliothécaire ou agriculteur ?" est traitée comme "Steve ressemble-t-il plus au bibliothécaire type ou à l'agriculteur type ?". La ressemblance répond bibliothécaire ; la statistique répond agriculteur, car les agriculteurs sont beaucoup plus nombreux. L'information écrasée au passage est le taux de base, c'est l'oubli de la fréquence de base ("base rate neglect"), démontré aussi par le problème des taxis bleus et verts et par les vignettes ingénieur-avocat de Kahneman et Tversky[^1].

L'heuristique produit une famille entière d'erreurs : l'erreur de conjonction du [[Le problème de Linda]] (le détail représentatif rend le scénario plus "probable" alors qu'il le rend logiquement moins probable), l'insensibilité à la taille de l'échantillon (la "loi des petits nombres"), l'illusion du joueur (après cinq rouges, le noir paraît "dû", car une séquence alternée est plus représentative du hasard), et la méconnaissance de la régression vers la moyenne.

## Contexte et origine

C'est la première heuristique formalisée par le duo, dès "Belief in the law of small numbers" (1971), où même des statisticiens chevronnés attendent des petits échantillons qu'ils reproduisent fidèlement la population[^2]. L'article de *Science* de 1974 la place en tête du triptyque du [[Le programme heuristiques et biais]]. L'exemple de la régression vers la moyenne vient d'une anecdote fondatrice : Kahneman, enseignant aux instructeurs de l'aviation israélienne, s'entend dire que féliciter un pilote est suivi d'une contre-performance et le réprimander d'un progrès ; l'instructeur prenait une pure régression statistique pour un effet causal de la punition.

## Mécanismes

Le mécanisme profond est la substitution d'attribut : la similarité est calculée automatiquement et sans effort par le [[Système 1 et Système 2|Système 1]], tandis que la probabilité conditionnelle exigerait une intégration bayésienne coûteuse. La similarité est un bon indice quand les catégories ont des taux de base comparables et des stéréotypes fiables ; elle déraille quand les taux de base sont très asymétriques ou que le stéréotype est faux, deux conditions fréquentes dans les problèmes socialement importants (diagnostic de maladies rares, profilage, recrutement).

L'exemple médical est le plus lourd de conséquences : face à un test fiable à 90% pour une maladie touchant 1 personne sur 1000, la plupart des médecins interrogés dans les études classiques surestiment massivement la probabilité qu'un patient positif soit malade, car ils raisonnent sur la ressemblance ("test positif, donc malade") et non sur les taux de base, qui font qu'une écrasante majorité des positifs sont des faux positifs.

## Nuances, critiques, limites

C'est ici que la critique de [[Gerd Gigerenzer]] a son terrain le plus solide : présentés en fréquences naturelles ("sur 1000 patients, 1 est malade ; sur les 999 sains, environ 100 seront positifs à tort..."), médecins comme profanes retrouvent largement le raisonnement bayésien correct[^3]. Une part de l'oubli des taux de base est donc un problème de format de l'information, pas une incapacité cognitive, résultat aux implications directes pour la communication du risque, l'éducation statistique et le [[Débiaisage]]. La réponse du camp Kahneman-Tversky : le format fréquentiel aide mais n'élimine pas l'erreur, et la vie réelle ne présente pas ses données en fréquences naturelles.

Autre nuance : le raisonnement par ressemblance n'est pas irrationnel en soi, c'est un cas de la [[Rationalité écologique]] quand l'environnement est stable et les stéréotypes calibrés. La leçon fine du cluster n'est pas "n'utilisez jamais la ressemblance" mais "sachez repérer les situations à taux de base extrêmes, c'est là qu'elle trahit".

## Liens et implications

La représentativité forme avec l'[[Heuristique de disponibilité]] et le [[Biais d'ancrage]] le noyau du [[Le programme heuristiques et biais]]. Elle fournit le mécanisme du [[Le problème de Linda]] et une partie de l'[[Effet de halo]] : l'impression globale sert de prototype qui contamine les jugements spécifiques. Elle éclaire aussi le [[Biais du survivant]] version recrutement : sélectionner "ceux qui ressemblent aux réussites passées" reconduit les taux de base cachés du passé. Sa maîtrise pratique passe par un réflexe unique : avant de juger une probabilité par la ressemblance, demander "combien y en a-t-il de chaque sorte au départ ?".

## Sources

[^1]: Amos Tversky, Daniel Kahneman, "Judgment under Uncertainty: Heuristics and Biases", *Science*, 1974 ; Daniel Kahneman, Amos Tversky, "On the psychology of prediction", *Psychological Review*, 1973.
[^2]: Amos Tversky, Daniel Kahneman, "Belief in the law of small numbers", *Psychological Bulletin*, 1971.
[^3]: Gerd Gigerenzer, Ulrich Hoffrage, "How to improve Bayesian reasoning without instruction: Frequency formats", *Psychological Review*, 1995.
