---
titre: "Rationalité écologique"
type: école
cluster: "Biais cognitifs"
statut: verified
controverse: medium
importance: standard
source_knowledge: internal
sources_count: 3
tags: [école/rationalité, concept/heuristique, débat/épistémologie]
créé: 2026-07-05
liens_forts: ["[[Gerd Gigerenzer]]", "[[Rationalité limitée]]", "[[Le débat biais ou rationalité]]"]
liens_opposition: ["[[Le programme heuristiques et biais]]"]
---

# Rationalité écologique

> [!info] Résumé
> L'école de pensée pour laquelle la rationalité d'une stratégie ne se juge pas à sa conformité aux lois de la logique ou des probabilités, mais à son adéquation à la structure de l'environnement où elle s'exerce. Les heuristiques simples n'y sont pas des défauts à corriger mais une boîte à outils adaptative, parfois supérieure aux modèles complexes.

## Définition

La rationalité écologique renverse la question du cluster. Là où le [[Le programme heuristiques et biais]] demande "en quoi le jugement humain dévie-t-il de la norme ?", elle demande "dans quels environnements cette stratégie réussit-elle ?". Une heuristique est écologiquement rationnelle quand sa structure épouse la structure statistique de l'environnement : ignorer de l'information, loin d'être un péché, devient une vertu dans les mondes incertains où les modèles complexes surajustent le bruit. Le concept clé est l'adaptation heuristique-environnement, hérité des "ciseaux" de Herbert Simon : la rationalité a deux lames, l'esprit et l'environnement, et juger l'une sans l'autre ne coupe rien.

Le programme s'incarne dans la "boîte à outils adaptative" : l'heuristique de reconnaissance (choisir l'option reconnue), "take the best" (décider sur le premier indice discriminant, ignorer le reste), les arbres frugaux de classification, l'imitation, le "satisficing". Le résultat phare, "less is more" : dans des tâches réelles de prédiction (résultats sportifs, tailles de villes, diagnostics), ces règles simples égalent ou battent régressions multiples et modèles bayésiens, surtout en petit échantillon[^1].

## Contexte et origine

L'école se cristallise dans les années 1990 autour de [[Gerd Gigerenzer]] et de l'ABC Research Group du Max Planck Institute de Berlin, avec le manifeste *Simple Heuristics That Make Us Smart* (1999)[^1]. Elle se réclame de la [[Rationalité limitée]] de Simon, dont elle conteste la lecture "économies de moyens, résultats dégradés" : les heuristiques ne sont pas un pis-aller pour esprits limités, elles sont souvent l'outil optimal en environnement incertain. La filiation remonte aussi à Egon Brunswik et sa psychologie écologique, pour qui les indices perceptifs se jugent à leur validité dans l'environnement. Le domaine parallèle du "bias-variance tradeoff" en apprentissage statistique a donné au "less is more" son fondement formel : un modèle simple à fort biais mais faible variance prédit mieux hors échantillon qu'un modèle complexe surajusté, dès que les données sont rares et bruitées.

## Mécanismes

Trois résultats emblématiques. L'heuristique de reconnaissance : des étudiants américains prédisent mieux les tailles de villes allemandes que les allemandes elles-mêmes... et réciproquement, l'ignorance partielle étant informative quand la reconnaissance corrèle avec le critère. "Take the best" : dans des dizaines de jeux de données réels, décider sur le meilleur indice discriminant et ignorer les autres égale la régression multiple en précision prédictive, pour une fraction du coût. Les arbres frugaux : trois questions séquentielles pour orienter un patient douleur thoracique en unité coronarienne font mieux, en sensibilité et fausses alarmes, que le score logistique en usage, tout en étant exécutables de tête[^2].

La méthode diffère aussi : plutôt que des vignettes de laboratoire à réponse normative unique, des compétitions de prédiction sur données réelles, où le critère est la performance hors échantillon, pas la conformité à un axiome.

## Nuances, critiques, limites

Les limites sont le miroir des forces. Un : les succès "less is more" dépendent de la structure des environnements choisis (indices à validités très inégales, échantillons courts, forte incertitude) ; dans les environnements riches en données et stables, les modèles complexes reprennent l'avantage, ce que l'apprentissage automatique moderne illustre massivement. Deux : la boîte à outils pose le problème de la sélection, comment l'esprit choisit-il la bonne heuristique au bon moment ? La réponse (apprentissage par renforcement du choix de stratégie) reste le maillon le moins développé du programme. Trois : le versant critique de l'école (les biais comme artefacts) a des succès inégaux, forts sur le raisonnement bayésien et la conjonction, faibles sur l'ancrage ou le cadrage, qui résistent à tous les formats. Quatre : l'opposition frontale avec le camp Kahneman s'est partiellement dissoute dans les synthèses récentes, beaucoup y voyant deux régimes complémentaires, risque calculable contre incertitude radicale, plutôt que deux anthropologies rivales.

## Liens et implications

La rationalité écologique fournit la moitié dialectique du [[Le débat biais ou rationalité]] et le cadre pour relire chaque biais du vault : avant de conclure au défaut, chercher l'environnement dans lequel le comportement serait adaptatif, exercice appliqué dans les pages [[Biais de confirmation]] (test positif), [[Heuristique de disponibilité]] (environnement médiatique manipulé) et [[Biais de négativité]] (asymétrie des coûts d'erreur). Son alternative au [[Nudge]], le "boosting" (enseigner des compétences de risque plutôt qu'architecturer les choix), gagne du terrain dans le débat de politiques publiques. Pour le praticien, sa leçon opérationnelle : en incertitude radicale et données rares, préférer les règles simples robustes, et réserver la sophistication aux mondes stables et riches en données.

## Sources

[^1]: Gerd Gigerenzer, Peter M. Todd, ABC Research Group, *Simple Heuristics That Make Us Smart*, Oxford University Press, 1999.
[^2]: Laura Martignon, Vivien Reimer, travaux sur les fast-and-frugal trees ; Green & Mehr, "What alters physicians' decisions to admit to the coronary care unit?", *Journal of Family Practice*, 1997.
[^3]: Gerd Gigerenzer, Daniel G. Goldstein, "Reasoning the fast and frugal way: Models of bounded rationality", *Psychological Review*, 1996.
