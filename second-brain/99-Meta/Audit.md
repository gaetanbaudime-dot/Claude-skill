# Audit qualité du vault

Audit final du run pilote, réalisé le 2026-07-05 après rédaction complète. Chaque point liste le constat et l'action.

## 1. Conformité YAML

Vérification automatisée : les 40 pages possèdent tous les champs obligatoires (titre, type, cluster, statut, controverse, importance, source_knowledge, sources_count, tags, créé, liens_forts). Toutes les valeurs de `type` et `statut` appartiennent aux énumérations du Schema. Répartition : 26 verified, 11 débattu, 3 débunké ; aucun to-verify, stub ou à-sourcer en fin de run. **Action : aucune.**

## 2. Doublons

Aucune paire de pages quasi-synonymes dans le produit final. Deux fusions préventives ont eu lieu dès la phase de plan (avocat du diable) : "Biais de statu quo" absorbé par [[Effet de dotation]], "Effet de faux consensus" absorbé par [[Biais d'autocomplaisance]], signalées dans les pages hôtes. **Action : aucune.**

## 3. Contradictions

Recherche de contradictions inter-pages sur les faits partagés : chiffres d'Asch (un tiers des réponses, trois quarts des sujets) cohérents entre [[Expérience de conformité d'Asch]] et le MOC ; coefficient d'aversion à la perte présenté partout comme "proche de 2" avec la précision 2,25 uniquement dans [[Aversion à la perte]] ; statut de l'amorçage social identique dans les 5 pages qui le mentionnent (débunké version comportementale, cognitif préservé). Une tension assumée et documentée, non contradictoire : [[Le programme heuristiques et biais]] présente les biais comme défauts, [[Rationalité écologique]] comme adaptations ; c'est l'objet de [[Le débat biais ou rationalité]], et les deux pages se citent mutuellement. **Action : aucune.**

## 4. Pages orphelines

Zéro page à 0 backlink entrant (vérification automatisée). Nœuds les moins connectés : [[Effet Barnum]] (2 backlinks après densification), [[Le test du marshmallow]] (2), [[Malédiction de la connaissance]] (2). Acceptable pour des deep-cuts. **Action : effectuée en Phase 4 (ajout d'un backlink vers Barnum depuis [[Biais d'autocomplaisance]]).**

## 5. Pages anémiques

Aucune page sous 600 mots (minimum constaté : ~700 mots hors YAML ; moyenne 826). La cible basse de 800 mots n'est pas strictement atteinte par quelques pages courtes (terme et deep-cuts), jugé conforme à l'esprit de la consigne (densité plutôt que remplissage). **Action : aucune.**

## 6. Pages survoltées

Aucune page au-dessus de 2000 mots (maximum constaté ~1000 mots hors YAML). Le style retenu est dense et sans remplissage ; si un usage futur exige des pages plus longues, les candidates naturelles à extension sont les piliers ([[Biais de confirmation]], [[Aversion à la perte]]). **Action : aucune.**

## 7. Sources manquantes

Toutes les pages sensibles (personne, expérience, controverse) ont au moins 2 footnotes ; minimum constaté sur l'ensemble du vault : 3 sources par page. Les faits non re-vérifiés par WebSearch sont explicitement listés dans `Fact-Check-Log.md`, section dédiée. **Action : aucune ; à la relecture humaine, prioriser la vérification des faits de cette liste.**

## 8. Cohérence des tags

Tags en minuscules avec préfixe thématique (concept/, personne/, expérience/, controverse/, école/, méthode/, débat/, théorie/, pont/), maximum 4 tags par page, aucune variante orthographique détectée (vérification par tri-unicité). **Action : aucune.**

## 9. Wikilinks

~490 wikilinks au total (moyenne 12 par page, YAML compris ; cible 8-12 atteinte), 0 wikilink fantôme (toutes les cibles [[...]] correspondent à une page existante), 0 orpheline. Tous les wikilinks du corps de texte sont intégrés dans des phrases, le listing brut étant réservé au MOC conformément aux conventions. **Action : aucune.**

## Verdict global

Vault conforme aux conventions du prompt pilote sur les 9 points d'audit. Deux réserves à arbitrage humain : (1) la liste des faits non re-vérifiés par WebSearch (Fact-Check-Log, section dédiée) mérite une passe de vérification si le vault sert de référence publique ; (2) quelques pages courtes (~700 mots) sous la cible basse de 800, à étoffer seulement si le besoin s'en fait sentir à l'usage.
