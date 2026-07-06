---
titre: "Tunnel de conversion"
type: méthode
cluster: "Marketing"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 3
tags: [marketing/funnel, marketing/conversion]
créé: 2026-07-06
liens_forts: ["[[Acquisition de clients]]", "[[L'offre et la valeur perçue]]", "[[Rétention et LTV]]"]
liens_opposition: []
---

# Tunnel de conversion

> [!info] Résumé
> Le tunnel (funnel) est la séquence d'étapes qui transforme un inconnu en client : attention, capture, nurturing, vente, upsell. Sa gestion est un exercice de mesure : identifier l'étape qui fuit le plus, la réparer, recommencer. Le tunnel n'invente rien, il révèle la force ou la faiblesse de l'offre.

## Définition

Un tunnel de conversion modélise le parcours d'achat en étapes mesurables, chacune avec son taux de passage : impression → clic (taux de clic), clic → inscrit (taux d'opt-in), inscrit → prospect qualifié, prospect → client (taux de closing), client → client récurrent ou upsellé. La multiplication des taux donne l'économie du tout : un tunnel à cinq étapes de 20% chacune convertit 0,03% du trafic entrant, ce qui rappelle une règle d'or, un tunnel court et honnête bat presque toujours un tunnel long et astucieux, chaque étape ajoutée étant une fuite ajoutée.

Les architectures types : le tunnel direct (page de vente, adapté aux petits paniers et aux audiences chaudes), le tunnel à aimant (lead magnet, séquence e-mail, offre, adapté aux paniers moyens), le tunnel à rendez-vous (contenu ou publicité, formulaire qualifiant, appel de vente, adapté aux offres chères), et le tunnel produit (essai gratuit ou freemium, activation, conversion payante, standard du SaaS).

## Contexte et origine

Le modèle descend de l'entonnoir AIDA du marketing classique, industrialisé par le direct response en ligne des années 2000-2010 (pages de capture, séquences automatisées, split-tests), puis raffiné par la culture produit du SaaS avec la notion d'activation : le moment "aha" où l'utilisateur vit la valeur promise, meilleur prédicteur de conversion que toute optimisation cosmétique en amont.

## Mécanismes

L'optimisation rationnelle suit trois principes. Le goulot d'abord : on n'améliore pas "le tunnel", on améliore l'étape au taux anormalement bas ; c'est l'application marketing de la [[Théorie des contraintes]], tout gain hors du goulot est invisible dans le résultat final. La friction ensuite : chaque champ de formulaire, chaque clic, chaque seconde de chargement coûte des points de conversion ; le [[Effet de dotation|biais de statu quo]] et la paresse cognitive du [[Système 1 et Système 2|Système 1]] jouent contre tout effort demandé, d'où la puissance des valeurs par défaut et du pré-rempli, logique [[Nudge]] assumée. La congruence enfin : la promesse de l'annonce doit se retrouver mot pour mot sur la page, toute rupture de cadre ([[Effet de cadrage]]) fait chuter la confiance et la conversion ; le message match est l'optimisation la moins chère qui existe.

Le levier de mesure : instrumenter chaque étape avant d'optimiser quoi que ce soit, sinon on optimise à l'aveugle, et se méfier des tests A/B sous-puissants qui font "gagner" des variations par bruit statistique, exactement la leçon de la [[Crise de la réplication en psychologie]] appliquée au marketing.

## Nuances, critiques, limites

Le modèle en entonnoir linéaire est une simplification : les parcours réels bouclent, comparent, reviennent des semaines plus tard, et les modèles d'attribution en souffrent (voir [[Acquisition de clients]]). L'obsession du micro-test est un piège d'échelle : sous quelques milliers de conversions par mois, les tests A/B fins n'ont pas la puissance statistique nécessaire, et l'énergie va mieux dans l'offre et l'angle. Enfin le tunnel sur-optimisé qui presse trop fort dégrade la qualité des clients acquis, remboursements et churn se payant en [[Rétention et LTV]].

## Liens et implications

Le tunnel exécute l'[[L'offre et la valeur perçue|offre]] portée par le [[Copywriting et persuasion|copy]] et alimentée par l'[[Acquisition de clients|acquisition]] ; ses sorties nourrissent la [[Rétention et LTV|rétention]]. Métriques et seuils de référence dans `98-Rapports/Rapport Marketing`.

## Sources

[^1]: Russell Brunson, *DotCom Secrets*, 2015 (architectures de tunnels du direct response).
[^2]: Sean Ellis, Morgan Brown, *Hacking Growth*, 2017 (activation, north star metric).
[^3]: Ronny Kohavi et al., *Trustworthy Online Controlled Experiments*, Cambridge, 2020 (rigueur des tests A/B).
