---
titre: "Théorie des contraintes"
type: théorie
cluster: "Scaling"
statut: verified
controverse: low
importance: pilier
source_knowledge: internal
sources_count: 2
tags: [scaling/goulots, théorie/opérations]
créé: 2026-07-06
liens_forts: ["[[Systèmes et process]]", "[[Tunnel de conversion]]"]
liens_opposition: []
---

# Théorie des contraintes

> [!info] Résumé
> Tout système a un goulot d'étranglement unique qui détermine son débit global ; améliorer quoi que ce soit d'autre est une illusion d'optique. La théorie de Goldratt fournit la discipline de focalisation la plus rentable du management : identifier LA contrainte, l'exploiter, tout y subordonner, l'élever, recommencer.

## Définition

La théorie des contraintes (TOC) modélise l'entreprise comme une chaîne : sa résistance est celle de son maillon le plus faible, et son débit celui de son étape la plus lente. Les cinq étapes de focalisation de Goldratt. **Identifier** la contrainte (où le travail s'empile, ce que tout le monde attend). **L'exploiter** à fond : la contrainte ne doit jamais attendre, jamais traiter de déchets, jamais faire ce qu'un non-goulot peut faire ; une heure perdue au goulot est une heure perdue pour tout le système, une heure gagnée sur un non-goulot est un mirage. **Subordonner** tout le reste à son rythme : produire plus vite que le goulot n'absorbe fabrique des stocks, pas du débit. **Élever** la contrainte (investir : capacité, embauche, outillage) seulement après l'avoir exploitée. **Recommencer** : la contrainte s'est déplacée, l'inertie est l'ennemi[^1].

## Contexte et origine

Eliyahu Goldratt, physicien israélien, publie la théorie sous forme de roman industriel (*The Goal*, 1984), best-seller improbable devenu lecture obligatoire d'écoles d'opérations et de dirigeants (Bezos l'a fait lire à ses cadres). Le cadre, né en usine, s'est généralisé à tout flux : projets (chaîne critique), ventes, services, et connaissance. Sa parenté avec le lean de Toyota est réelle (flux, gaspillages) avec une différence d'accent : le lean chasse tous les gaspillages, la TOC ne s'intéresse qu'à ceux du goulot, ce qui en fait l'outil de focalisation par excellence pour les petites structures qui ne peuvent pas tout optimiser.

## Mécanismes

L'application business courante. **Dans un pipeline de vente** ([[Tunnel de conversion]]) : le goulot est l'étape au taux anormal ; y concentrer toute l'énergie, ignorer le reste. **Dans une entreprise de services** : le goulot est souvent le fondateur lui-même, par qui toute décision et toute qualité passent ; les cinq étapes s'appliquent littéralement, exploiter (protéger son temps des tâches de non-goulot, [[Coût d'opportunité]]), subordonner (l'équipe prépare, il tranche), élever ([[Délégation]] et [[Documentation et SOP|documentation]]). **Dans la croissance** : à chaque palier, la contrainte se déplace (leads → capacité de livraison → cash → management), et le plan stratégique honnête tient en une question, quelle est la contrainte ACTUELLE ?, toute initiative hors contrainte étant du confort déguisé en travail.

Le lien psychologique : sans discipline de contrainte, l'attention va aux améliorations disponibles et agréables ([[Heuristique de disponibilité]], on optimise ce qu'on voit et ce qu'on aime faire) plutôt qu'au goulot, souvent inconfortable précisément parce qu'il est le goulot.

## Nuances, critiques, limites

La contrainte unique est une simplification puissante mais une simplification : les systèmes très interconnectés ont des contraintes couplées ou oscillantes, et la TOC orthodoxe sous-traite mal la variabilité (que le lean et la théorie des files d'attente traitent mieux, marges de capacité sur les non-goulots incluses). Le diagnostic peut aussi se tromper d'étage : la vraie contrainte est parfois une politique (règle interne, croyance du dirigeant) plutôt qu'une capacité physique, la version la plus profonde de la théorie que Goldratt considérait comme la plus fréquente. Enfin, l'obsession du débit peut écraser la qualité et les personnes si la métrique de sortie est mal choisie.

## Liens et implications

La TOC est la discipline de focalisation du [[_MOC Scaling|scaling]] : elle ordonne les chantiers de [[Systèmes et process]], borne les investissements d'[[Effet de levier]] et recycle la logique goulot du [[Tunnel de conversion]]. Diagnostic de contrainte en 5 questions dans `98-Rapports/Rapport Scaling`.

## Sources

[^1]: Eliyahu M. Goldratt, Jeff Cox, *The Goal: A Process of Ongoing Improvement*, North River Press, 1984.
[^2]: Eliyahu M. Goldratt, *Critical Chain*, 1997 (application aux projets).
