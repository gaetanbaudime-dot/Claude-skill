---
titre: "Biais du survivant"
type: concept
cluster: "Biais cognitifs"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 3
tags: [concept/échantillonnage, pont/statistiques, pont/entrepreneuriat]
créé: 2026-07-05
liens_forts: ["[[Heuristique de disponibilité]]", "[[Biais rétrospectif]]"]
liens_opposition: []
---

# Biais du survivant

> [!info] Résumé
> Tirer des conclusions à partir des seuls cas qui ont "survécu" à un processus de sélection, en oubliant les disparus qu'on ne voit pas. Des impacts sur les avions de Wald aux biographies de milliardaires décrocheurs, c'est le biais d'échantillonnage le plus coûteux de la culture du succès.

## Définition

Le biais du survivant est un cas particulier de biais de sélection : l'échantillon observable a été filtré par un processus (mortalité, faillite, désabonnement, publication) et raisonner sur lui comme s'il représentait la population de départ produit des conclusions systématiquement fausses. Sa dangerosité vient de l'invisibilité du filtre : les survivants sont là, disponibles, interviewables ; les éliminés n'ont laissé ni trace ni porte-parole. On n'a pas l'impression d'ignorer des données, puisqu'on ne voit pas qu'il en manque.

L'anecdote fondatrice est celle du statisticien Abraham Wald pendant la Seconde Guerre mondiale : chargé d'optimiser le blindage des bombardiers, il examine la distribution des impacts sur les avions rentrés de mission. L'intuition commande de blinder les zones criblées ; Wald recommande l'inverse, blinder les zones intactes, car les avions touchés là ne sont pas rentrés. Les impacts visibles cartographient ce qui est survivable, les zones vierges cartographient ce qui tue[^1].

## Contexte et origine

Le raisonnement de Wald est documenté par ses mémorandums pour le Statistical Research Group de Columbia, redécouverts et popularisés dans les années 1980-2010, l'anecdote circulant aujourd'hui sous des formes simplifiées mais fidèles au principe. En finance, le biais a été quantifié tôt : les performances moyennes des fonds d'investissement sont surestimées quand on calcule sur les fonds existants, les fonds liquidés pour mauvaise performance ayant disparu des bases de données ; les études classiques d'Elton, Gruber et Blake ont mesuré cette distorsion, désormais corrigée dans les bases sérieuses[^2]. En histoire et en archéologie, le principe est un réflexe métier : on ne connaît du passé que ce qui a survécu, cathédrales et non masures, manuscrits copiés et non brouillons.

## Mécanismes

Le biais opère par la conjonction de deux mécanismes du cluster. L'[[Heuristique de disponibilité]] fournit le carburant : les survivants sont médiatisés, célébrés, disponibles en mémoire, tandis que les échecs sont statistiquement majoritaires et narrativement absents. Le [[Biais rétrospectif]] et la construction de récit font le reste : une fois le succès connu, on reconstruit la trajectoire du survivant comme une suite de causes ("il a osé, il a persévéré"), traits que les éliminés partageaient pourtant en proportion inconnue. Le résultat est une épistémologie du succès frelatée : les "secrets de la réussite" extraits des seuls gagnants (lever à 5h, abandonner ses études, tout miser) sont des propriétés de l'échantillon filtré, pas des causes, et certains sont peut-être des facteurs de risque que seuls les chanceux ont survécus.

La structure formelle est le conditionnement sur la survie : estimer P(trait | succès) et le prendre pour P(succès | trait), inversion des conditionnelles que l'[[Heuristique de représentativité]] rend naturelle et que seuls les taux de base des éliminés permettraient de corriger.

## Nuances, critiques, limites

Le biais est une vérité mathématique appliquée, pas un effet de laboratoire discutable : il n'y a pas de débat de réplication, seulement des débats de mesure au cas par cas. Les nuances sont pratiques. Un : le filtre n'invalide pas toute inférence ; si le taux de survie est connu ou estimable, la correction est possible, c'est le travail quotidien de l'actuariat et de l'épidémiologie. Deux : l'anecdote de Wald, souvent racontée avec des détails embellis, mérite sa prudence philologique, le cœur mathématique (estimer la vulnérabilité en modélisant les avions non rentrés) étant authentique. Trois : le concept est parfois surétendu en ligne à tout raisonnement sur des exemples réussis ; le diagnostic strict exige un processus de sélection identifiable qui retire des cas de l'échantillon observable.

## Liens et implications

Page-pont par excellence vers les statistiques, l'entrepreneuriat et la finance. Applications immédiates : lire toute étude de "meilleures pratiques" en cherchant le cimetière (combien d'entreprises appliquant ces pratiques ont disparu ?), corriger les performances historiques de tout univers d'investissement, et se méfier des retours d'expérience de communautés dont les déçus sont partis (avis clients, forums, anciens élèves). Le biais éclaire aussi la [[Crise de la réplication en psychologie]] : la littérature publiée est un échantillon de survivants du filtre de publication, les résultats nuls dormant dans les tiroirs, ce qui explique l'effondrement de méta-analyses entières corrigées du biais de publication comme dans le dossier [[Nudge]]. Se lit avec l'[[Excès de confiance]] des entrepreneurs nourris aux biographies de gagnants, et avec le [[Biais de confirmation]] qui rend le cimetière si facile à ne jamais visiter.

## Sources

[^1]: Abraham Wald, "A Method of Estimating Plane Vulnerability Based on Damage of Survivors", mémorandums du Statistical Research Group, Columbia University, 1943, réédités par le Center for Naval Analyses en 1980.
[^2]: Edwin J. Elton, Martin J. Gruber, Christopher R. Blake, "Survivorship Bias and Mutual Fund Performance", *Review of Financial Studies*, 1996.
[^3]: Marc Mangel, Francisco J. Samaniego, "Abraham Wald's work on aircraft survivability", *Journal of the American Statistical Association*, 1984.
