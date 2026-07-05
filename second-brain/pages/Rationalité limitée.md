---
titre: "Rationalité limitée"
type: théorie
cluster: "Biais cognitifs"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 3
tags: [théorie/fondations, pont/économie, concept/décision]
créé: 2026-07-05
liens_forts: ["[[Le programme heuristiques et biais]]", "[[Rationalité écologique]]"]
liens_opposition: []
---

# Rationalité limitée

> [!info] Résumé
> Le concept fondateur de Herbert Simon (Nobel 1978) : la rationalité réelle est bornée par l'information disponible, les capacités de calcul et le temps. L'agent réel ne maximise pas, il "satisfait" : il cherche jusqu'à trouver une option assez bonne. Ancêtre commun revendiqué par les deux camps du cluster.

## Définition

La rationalité limitée ("bounded rationality") est la thèse selon laquelle les modèles de choix rationnel classiques, agent omniscient calculant l'option optimale parmi toutes les alternatives, décrivent un être qui n'existe pas. L'agent réel connaît une fraction des options, évalue imparfaitement leurs conséquences, et dispose d'une capacité de calcul et d'un temps finis. Sa rationalité est procédurale, non substantielle : ce qui peut être rationnel, c'est la procédure de recherche et de décision compte tenu des contraintes, pas le résultat mesuré à l'aune d'un optimum inaccessible.

Le concept opérationnel central est le "satisficing" (mot-valise de satisfy et suffice) : fixer un seuil d'aspiration, chercher séquentiellement, s'arrêter à la première option qui dépasse le seuil. Le vendeur de maison de Simon ne calcule pas le prix optimal sur la distribution complète des acheteurs futurs ; il a un prix de réserve et accepte la première offre au-dessus, comportement à la fois modeste et remarquablement robuste[^1].

## Contexte et origine

Herbert Simon, polymathe (science politique, économie, psychologie cognitive, intelligence artificielle, il est aussi un des pères fondateurs de l'IA avec le General Problem Solver), introduit l'idée dans "A Behavioral Model of Rational Choice" (1955) et *Models of Man* (1957), contre l'économie néoclassique de son temps[^1]. Le Nobel d'économie 1978 récompense cette "recherche pionnière sur le processus de décision dans les organisations économiques". Sa métaphore des ciseaux est le legs conceptuel le plus durable : le comportement rationnel se découpe avec deux lames, la structure de l'environnement et les capacités computationnelles de l'acteur ; étudier une lame seule ne coupe rien.

L'histoire du cluster peut se raconter comme la querelle d'héritage de Simon. Le [[Le programme heuristiques et biais]] retient la lame cognitive : des capacités limitées, donc des raccourcis, donc des écarts à la norme, catalogués comme biais. La [[Rationalité écologique]] retient les deux lames : des heuristiques adaptées à des environnements, à juger sur leur performance écologique, et [[Gerd Gigerenzer]] revendique explicitement la filiation légitime contre ce qu'il considère être un contresens "optimisation sous contraintes" ou "irrationalité systématique".

## Mécanismes

Trois idées mécaniques structurent la théorie. La recherche séquentielle avec seuil d'arrêt d'abord, dont la théorie de la recherche optimale a montré qu'elle peut être étonnamment proche de l'optimal quand la recherche est coûteuse, réhabilitation formelle du satisficing. Les niveaux d'aspiration adaptatifs ensuite : le seuil monte quand les options abondent, descend quand elles se raréfient, thermostat qui rend le satisficing auto-régulé. La décomposition hiérarchique enfin : face à la complexité, l'agent limité découpe les problèmes en sous-problèmes quasi indépendants, thème que Simon développe dans *The Sciences of the Artificial* et qui irrigue l'IA, la théorie des organisations et l'architecture logicielle.

En psychologie de la consommation, la distinction maximiseurs-satisficeurs de Schwartz (2002) en est la déclinaison différentielle : les maximiseurs, qui prolongent la recherche du mieux, obtiennent objectivement un peu plus et sont subjectivement moins satisfaits, le coût de la recherche et les regrets mangeant le gain[^2].

## Nuances, critiques, limites

Les critiques portent moins sur la thèse, difficilement contestable, que sur son contenu prédictif. Un : "les capacités sont limitées" ne dit pas où passent les limites ni quelles heuristiques sont utilisées, la théorie est un cadre plus qu'un modèle, et ses héritiers se disputent précisément le remplissage. Deux : l'économie a partiellement absorbé le choc en réintégrant les limites comme coûts d'information et d'attention dans des modèles d'optimisation ("rational inattention" de Sims), ce que les simoniens jugent être une trahison élégante, l'optimisation revenant par la fenêtre. Trois : le satisficing décrit bien les choix séquentiels à options exogènes, moins bien les jugements probabilistes fins où le [[Le programme heuristiques et biais]] documente ses écarts.

## Liens et implications

Cette page est la racine historique du vault : lire Simon d'abord rend intelligibles à la fois Kahneman et Gigerenzer, et [[Le débat biais ou rationalité]] apparaît pour ce qu'il est, un désaccord sur la lame des ciseaux à privilégier. Applications directes : en design d'organisations, accepter que les décideurs satisfassent et concevoir les circuits d'information en conséquence ; en produit et en marketing, comprendre que l'utilisateur ne compare pas tout le marché mais s'arrête au premier "assez bien", d'où la prime au placement précoce dans le parcours de recherche ; en vie personnelle, la leçon de Schwartz, choisir quand satisficer (presque toujours) et quand maximiser (rarement, sur les décisions irréversibles). Se lit avec la [[Théorie des perspectives]] pour l'autre grande formalisation des écarts au modèle rationnel, et avec le [[Sophisme des coûts irrécupérables]] pour un cas où la comptabilité mentale limitée coûte cher.

## Sources

[^1]: Herbert A. Simon, "A Behavioral Model of Rational Choice", *Quarterly Journal of Economics*, 1955 ; *Models of Man*, Wiley, 1957.
[^2]: Barry Schwartz et al., "Maximizing versus satisficing: Happiness is a matter of choice", *Journal of Personality and Social Psychology*, 2002.
[^3]: Comité Nobel, prix de sciences économiques 1978, motivations ; Herbert A. Simon, *The Sciences of the Artificial*, MIT Press, 1969.
