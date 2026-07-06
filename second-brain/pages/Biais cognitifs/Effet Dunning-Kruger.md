---
titre: "Effet Dunning-Kruger"
type: concept
cluster: "Biais cognitifs"
statut: débattu
controverse: medium
importance: pilier
source_knowledge: web-checked
sources_count: 4
tags: [concept/métacognition, concept/auto-évaluation, controverse/réplication]
créé: 2026-07-05
liens_forts: ["[[Excès de confiance]]", "[[Biais de point aveugle]]"]
liens_opposition: ["[[Crise de la réplication en psychologie]]"]
---

# Effet Dunning-Kruger

> [!info] Résumé
> Les personnes les moins compétentes dans un domaine surestiment fortement leur compétence, faute des capacités métacognitives nécessaires pour percevoir leurs propres lacunes. L'effet existe dans les données, mais son interprétation classique est sérieusement contestée : une grande partie du pattern serait un artefact statistique.

## Définition

Dans leur article de 1999, "Unskilled and Unaware of It", Justin Kruger et David Dunning font passer des tests de logique, de grammaire et d'humour à des étudiants, puis leur demandent d'estimer leur performance relative. Résultat spectaculaire : le quartile le plus faible, situé en moyenne autour du 12e percentile réel, s'estime autour du 60e percentile[^1]. L'interprétation des auteurs est le "double fardeau" : l'incompétence prive à la fois de la capacité à bien faire et de la capacité à voir qu'on fait mal, car juger sa performance exige précisément les compétences qui manquent.

La version popularisée, "les idiots se croient des génies et les experts doutent d'eux", est une déformation. Dans les données originales, les faibles performeurs se jugent moins bons que les bons performeurs ne se jugent eux-mêmes : l'auto-évaluation monte avec la compétence réelle, elle monte simplement beaucoup moins vite. Personne ne se croit au sommet en étant au fond ; les gens du fond se croient légèrement au-dessus de la moyenne.

## Contexte et origine

L'article s'inscrit dans la tradition de l'[[Excès de confiance]] et des effets "mieux que la moyenne" documentés depuis les années 1970. Sa fortune médiatique doit beaucoup à son anecdote d'ouverture : McArthur Wheeler, braqueur de banques de Pittsburgh arrêté en 1995, persuadé que le jus de citron rendait son visage invisible aux caméras. L'effet a reçu le prix Ig Nobel en 2000, avant de devenir, ironie remarquable, l'insulte épistémique favorite d'Internet, généralement brandie avec une confiance que ses données ne justifient pas.

Dunning a étendu le cadre au-delà du laboratoire : auto-évaluations en médecine, en pilotage, en gestion. La littérature applicative a suivi avec un enthousiasme qui a largement précédé la vérification méthodologique.

## Mécanismes

L'explication métacognitive originale suppose que la compétence et l'évaluation de la compétence mobilisent les mêmes ressources. Un mauvais logicien ne peut pas détecter ses erreurs de logique, précisément parce que cette détection est de la logique. À l'appui, Kruger et Dunning montraient qu'entraîner les sujets faibles à la tâche améliore aussi la précision de leur auto-évaluation.

Mais deux mécanismes statistiques suffisent à produire l'essentiel du pattern sans aucune métacognition défaillante. Premièrement, la régression vers la moyenne : l'auto-évaluation étant imparfaitement corrélée à la performance, les scores extrêmes s'accompagnent mécaniquement d'auto-évaluations moins extrêmes, donc les derniers "surestiment" et les premiers "sous-estiment". Deuxièmement, l'effet mieux-que-la-moyenne : presque tout le monde se place au-dessus du 50e percentile, ce qui gonfle l'écart surtout en bas de la distribution. Gignac et Zajenkowski ont montré en 2020 qu'avec des méthodes qui testent réellement l'hypothèse (hétéroscédasticité, régression non linéaire), l'effet spécifiquement métacognitif devient faible ou nul : la relation entre QI réel et QI auto-évalué est à peu près linéaire[^2]. Des simulations ont même reproduit le graphique classique avec des données purement aléatoires[^3].

## Nuances, critiques, limites

L'état honnête du dossier en trois points. Un : le phénomène descriptif est réel et répliqué, les faibles performeurs se surestiment massivement, ce qui suffit pour la plupart des usages pratiques (formation, management). Deux : l'explication métacognitive, qui fait toute l'originalité de l'effet, est contestée ; une part substantielle du pattern est un artefact de mesure, et le débat technique se poursuit, avec commentaires et réponses jusqu'en 2023[^4]. Trois : la version pop-culture est simplement fausse et fonctionne elle-même comme illustration du [[Biais de point aveugle]] : diagnostiquer du Dunning-Kruger chez autrui est plus facile que d'évaluer sa propre calibration.

À noter aussi la question interculturelle : les auto-évaluations gonflées sont nettement plus faibles dans les échantillons est-asiatiques, signe que l'effet est en partie culturel, ce qui rejoint la critique WEIRD récurrente du cluster (échantillons occidentaux, éduqués, industrialisés, riches, démocratiques).

## Liens et implications

Cette page se lit comme un cas d'école de la maturation du cluster : un effet spectaculaire de 1999, une décennie de gloire, puis la contre-offensive méthodologique typique de la [[Crise de la réplication en psychologie]], avec un verdict nuancé plutôt que binaire. Il se rattache à l'[[Excès de confiance]] dont il est un cas limite, au [[Biais d'autocomplaisance]] pour la dimension protectrice de l'ego, et à l'[[Effet Dunning-Kruger|auto-évaluation]] défaillante que le [[Débiaisage]] tente de corriger par le feedback structuré. La leçon transversale rejoint [[Le débat biais ou rationalité]] : avant de conclure à un défaut de l'esprit, vérifier que le pattern n'est pas fabriqué par l'instrument de mesure.

## Sources

[^1]: Justin Kruger, David Dunning, "Unskilled and Unaware of It: How Difficulties in Recognizing One's Own Incompetence Lead to Inflated Self-Assessments", *Journal of Personality and Social Psychology*, 1999.
[^2]: Gilles E. Gignac, Marcin Zajenkowski, "The Dunning-Kruger effect is (mostly) a statistical artefact", *Intelligence*, 2020.
[^3]: Eric C. Gaze et al., "A Statistical Explanation of the Dunning-Kruger Effect", *Frontiers in Psychology*, 2022 ; Nuhfer et al., *Numeracy*, 2016-2017.
[^4]: Hiller, commentaire sur Gignac & Zajenkowski, *Intelligence*, 2023, et réponse des auteurs la même année.
