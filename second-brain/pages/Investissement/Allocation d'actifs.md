---
titre: "Allocation d'actifs"
type: méthode
cluster: "Investissement"
statut: verified
controverse: low
importance: pilier
source_knowledge: internal
sources_count: 3
tags: [investissement/allocation]
créé: 2026-07-06
liens_forts: ["[[Intérêts composés]]", "[[Bourse indicielle]]", "[[Espérance mathématique et asymétries]]"]
liens_opposition: []
---

# Allocation d'actifs

> [!info] Résumé
> La répartition du patrimoine entre classes d'actifs (actions, obligations, immobilier, cash, éventuellement or et crypto) détermine l'essentiel du couple rendement-risque d'un portefeuille, très loin devant le choix des titres individuels ou le timing. C'est LA décision d'investissement ; le reste est du détail d'exécution.

## Définition

Allouer, c'est répondre à trois questions dans l'ordre. **Horizon** : quand aurai-je besoin de cet argent ? L'argent à moins de 5 ans n'a rien à faire en actions (la volatilité peut le confisquer au mauvais moment), l'argent à 20 ans n'a rien à faire en livret (l'inflation le confisque sûrement). **Capacité de risque** : quelle perte maximale mon plan de vie supporte-t-il sans casser (revente forcée, panique) ? Elle se mesure en euros de baisse tolérable, pas en pourcentages abstraits, un portefeuille 100% actions perd 40-55% dans les grands krachs, chiffre à convertir en euros et à regarder en face. **Tolérance psychologique** : indépendamment de la capacité, qu'est-ce que je tiendrai réellement sans vendre au pire moment ? Voir [[Psychologie de l'investisseur]] ; la meilleure allocation est celle qu'on tient, pas celle qui optimise une moyenne sur papier.

Les principes d'exécution : diversifier entre classes ET à l'intérieur (un indice mondial plutôt que trois titres), rééquilibrer mécaniquement à date ou à seuil (vendre ce qui a monté, racheter ce qui a baissé : la seule machine à "acheter bas, vendre haut" qui fonctionne sans prédiction), et garder la structure simple, chaque ligne ajoutée devant justifier son rôle.

## Contexte et origine

La primauté de l'allocation vient de la théorie moderne du portefeuille (Markowitz, 1952 : la diversification est le seul repas gratuit) et de l'étude classique de Brinson, Hood et Beebower (1986), souvent citée comme "l'allocation explique plus de 90% de la variance des rendements des fonds", chiffre exact discuté et raffiné depuis, mais la hiérarchie qu'il établit (structure > sélection > timing) a survécu à tous les réexamens[^1]. La mise en pratique grand public doit tout au courant Bogleheads (John Bogle, Vanguard) : quelques fonds indiciels mondiaux, une part d'obligations selon l'âge et le risque, des apports réguliers, du rééquilibrage, rien d'autre, voir [[Bourse indicielle]].

## Mécanismes

Pourquoi ça marche : les classes d'actifs ne chutent pas toutes ensemble (corrélations imparfaites), donc le portefeuille total est moins volatil que ses composants, ce qui protège la variable décisive, la capacité à rester investi ([[Intérêts composés]]). Le rééquilibrage exploite mécaniquement le retour vers la moyenne des valorisations relatives et neutralise le comportement, il force à faire à froid l'inverse de ce que la foule fait à chaud. L'automatisation (virement programmé, investissement à date fixe) retire les décisions du chemin de l'émotion : chaque décision évitée est un biais évité, philosophie directement héritée du verdict [[Débiaisage|procédures > vigilance]].

## Nuances, critiques, limites

Un : la diversification protège des risques idiosyncratiques, pas des krachs systémiques où les corrélations convergent vers 1 au pire moment ; la seule vraie protection courte est la part non risquée (obligations de qualité, cash). Deux : les allocations modèles (60/40 et héritiers) reposent sur des corrélations historiques instables, 2022 a rappelé que actions et obligations peuvent chuter ensemble en régime d'inflation. Trois : pour un entrepreneur, le business propre est déjà une position massive, concentrée et illiquide ; le patrimoine investi doit se construire en DÉCORRÉLATION de cette position (secteurs, géographies), pas en la redoublant, l'erreur type du fondateur tech sur-investi en tech. Quatre : l'immobilier locatif est une classe à part, levier et travail inclus, voir la page dédiée au prochain run et les précautions du rapport.

## Liens et implications

L'allocation exécute les principes d'[[Espérance mathématique et asymétries]] (survie d'abord, asymétries ensuite) au niveau patrimonial, et prépare le terrain psychologique de la [[Psychologie de l'investisseur]]. Allocation type par horizon et check-list de rééquilibrage dans `98-Rapports/Rapport Investissement`. Rien ici n'est un conseil personnalisé : c'est la structure du raisonnement, à adapter à ta situation fiscale et personnelle.

## Sources

[^1]: Harry Markowitz, "Portfolio Selection", *Journal of Finance*, 1952 ; Gary Brinson, Randolph Hood, Gilbert Beebower, "Determinants of Portfolio Performance", *Financial Analysts Journal*, 1986.
[^2]: John C. Bogle, *The Little Book of Common Sense Investing*, 2007.
[^3]: William J. Bernstein, *The Intelligent Asset Allocator*, 2000.
