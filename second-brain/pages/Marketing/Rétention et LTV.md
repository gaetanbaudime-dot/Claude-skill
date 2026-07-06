---
titre: "Rétention et LTV"
type: concept
cluster: "Marketing"
statut: verified
controverse: low
importance: pilier
source_knowledge: internal
sources_count: 3
tags: [marketing/rétention, finance/ltv]
créé: 2026-07-06
liens_forts: ["[[Unit economics]]", "[[Acquisition de clients]]", "[[L'offre et la valeur perçue]]"]
liens_opposition: []
---

# Rétention et LTV

> [!info] Résumé
> La LTV (valeur vie client) est la quantité de marge brute qu'un client génère avant de partir ; la rétention est ce qui la fabrique. C'est la variable la plus puissante et la moins sexy du marketing : elle plafonne ce que tu peux payer en acquisition, donc elle décide qui peut scaler et qui ne peut pas.

## Définition

La LTV se calcule en marge brute, pas en chiffre d'affaires : panier moyen × fréquence × durée de vie × marge brute. Pour un abonnement, l'approximation standard est ARPU × marge brute ÷ churn mensuel, avec le piège classique : cette formule suppose un churn constant, alors que le churn réel décroît avec l'ancienneté (les fragiles partent tôt), ce qui sous-estime la LTV des cohortes fidélisées. La seule mesure honnête est l'analyse par cohortes : suivre chaque promotion mensuelle de clients dans le temps et regarder où sa courbe de rétention s'aplatit.

La rétention se décompose en trois moments : l'activation (le client vit-il la valeur promise, vite ?), l'habitude (l'usage s'installe-t-il dans une routine ?) et l'approfondissement (le client augmente-t-il son engagement, upsell et cross-sell). La revenue retention nette supérieure à 100%, où l'expansion des clients restants compense les départs, est le graal du SaaS : la croissance sans acquisition.

## Contexte et origine

Le corpus vient de trois traditions : le marketing relationnel et les travaux de Reichheld (Bain) sur la fidélité, popularisés par le chiffre, à manier comme ordre de grandeur, qu'augmenter la rétention de 5 points augmente les profits de 25 à 95%[^1] ; la culture SaaS des années 2010 (cohortes, churn, NRR) ; et l'école du produit (Nir Eyal, *Hooked*, sur la formation d'habitude). Hormozi le formule brutalement : le business qui peut dépenser le plus pour acquérir un client gagne, et c'est la LTV qui donne ce droit.

## Mécanismes

Pourquoi la rétention bat l'acquisition en rendement : elle est composée. Un point de churn mensuel en moins se cumule sur toutes les cohortes futures, quand un point de conversion en plus ne s'applique qu'au flux entrant. Le mécanisme psychologique de la fidélité mobilise le cluster voisin : le [[Biais de statu quo|statu quo]] et l'[[Effet de dotation]] retiennent le client installé (ses données, ses habitudes, son paramétrage sont une dotation qu'il répugne à perdre), l'[[Effet de simple exposition]] rend le produit familier donc préféré, et les coûts de changement réels ou perçus verrouillent le reste. La face sombre existe : la rétention par la friction de sortie (désabonnement caché, engagement forcé) gonfle les chiffres à court terme et fabrique du ressentiment, des rétrofacturations et du bouche-à-oreille négatif.

Le diagnostic type : si la courbe de rétention d'une cohorte ne s'aplatit jamais, le produit n'a pas de product-market fit sur ce segment, et scaler l'acquisition revient à remplir un seau percé, l'erreur la plus chère du marketing de croissance.

## Nuances, critiques, limites

La LTV est une projection, pas un fait : elle extrapole des comportements passés sur des cohortes futures, et les modèles se trompent aux changements de marché ou de mix client. Règle de prudence : décider sur la LTV à 12 mois plutôt que sur la LTV "à vie", et ne jamais lever de la dette d'acquisition sur une LTV modélisée à 5 ans. Deuxième nuance : la moyenne cache la distribution, une LTV moyenne correcte peut mélanger un segment très rentable et un segment destructeur ; segmenter par canal, offre et persona avant tout arbitrage. Troisième : Byron Sharp et l'école d'Ehrenberg-Bass rappellent que dans les catégories à faible engagement, la "fidélité" observée est surtout de la disponibilité mentale et physique, pas de l'amour de marque ; la rétention s'y gagne en distribution et en saillance plus qu'en programmes de fidélité.

## Liens et implications

La LTV fixe le budget de l'[[Acquisition de clients|acquisition]] et boucle les [[Unit economics]] ; l'offre qui sur-promet la détruit ([[L'offre et la valeur perçue]], [[Copywriting et persuasion]]). Plan de mesure et seuils dans `98-Rapports/Rapport Marketing`.

## Sources

[^1]: Frederick Reichheld, "Zero Defections: Quality Comes to Services", *Harvard Business Review*, 1990 ; *The Loyalty Effect*, 1996.
[^2]: Nir Eyal, *Hooked: How to Build Habit-Forming Products*, 2014.
[^3]: Byron Sharp, *How Brands Grow*, Oxford University Press, 2010.
