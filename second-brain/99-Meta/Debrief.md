# Debrief du run pilote

Livrable critique du pilote : ce qui s'est réellement passé, ce qui doit changer pour scaler à 500+ pages.

## Contexte d'exécution

Run exécuté en environnement Claude Code distant (session cloud non interactive), en mode full-auto : les checkpoints humains 1 et 2 du prompt n'ont pas pu être tenus de façon bloquante, la session ne permettant pas de dialogue en cours de run. Les livrables de contrôle (Plan, Fact-Check-Log, Audit, Debrief) ont été produits intégralement pour permettre la validation a posteriori, et le travail a été committé par batches sur la branche git pour rester auditable étape par étape.

## Stats finales

- Pages créées : 40 (8 piliers, 28 standard, 4 deep-cuts)
- Mots : ~33 000 hors YAML (moyenne 826/page, min ~700, max ~1000)
- Wikilinks : ~490 (moyenne 12/page), 0 fantôme, 0 orpheline
- WebSearch effectués : 14 (tous tracés dans Fact-Check-Log.md)
- Pages marquées to-verify : 0 (mais une liste de faits "connaissance interne non re-vérifiée" est tenue dans le log)
- Statuts : 26 verified, 11 débattu, 3 débunké
- Temps de run : une session de travail continue (de l'ordre de l'heure), bien sous la limite des 2h
- Tokens : non mesurables précisément depuis la session ; l'essentiel du coût est la génération des 40 pages (~45 000 tokens de sortie estimés) et les 14 recherches web

## Ce qui a bien marché

- La consigne "spectre consensus-controverse" est le meilleur atout du prompt : imposer 5+ pages controverses et 3+ théories débunkées produit un vault honnête, très supérieur aux listes de biais habituelles qui présentent tout comme établi.
- Le champ YAML `statut` (verified/débattu/débunké) s'est révélé structurant pour l'écriture elle-même : chaque page a dû prendre position sur la solidité de son sujet.
- L'avocat du diable sur le plan (Phase 1) a réellement servi : deux fusions de quasi-doublons avant rédaction, zéro doublon à l'arrivée.
- Le fact-check groupé par thème (une recherche couvrant les chiffres d'un dossier entier, ex. Reproducibility Project) est nettement plus efficace que 2 recherches par page.
- La vérification automatisée de fin de run (scripts : orphelines, fantômes, champs YAML, tirets cadratins, formules interdites) attrape en secondes ce qu'une relecture manuelle raterait.

## Ce qui a mal marché

- Les checkpoints humains bloquants sont incompatibles avec une session autonome : le prompt suppose un terminal interactif. Il faut une variante explicite "mode autonome" (celle-ci) et une variante "mode interactif".
- La fourchette 800-1500 mots est en tension avec "zéro verbosité" : le style dense converge naturellement vers 750-1000 mots ; viser 800-1500 pousse au remplissage. Recommandation : 700-1200.
- Compter les mots et wikilinks pendant la rédaction est peu fiable ; seule la mesure scriptée en fin de batch fait foi. Les stats des consignes doivent être vérifiées par script, pas promises par le rédacteur.
- Les recherches web renvoient parfois des sources secondaires de qualité inégale (agrégateurs) ; il a fallu privilégier systématiquement les sources primaires citées dans les résultats.

## Hallucinations détectées

- Aucune hallucination détectée a posteriori dans les 40 pages (audit croisé des chiffres partagés entre pages).
- Mesures préventives qui ont fonctionné : chiffres sensibles vérifiés par WebSearch avant rédaction ; faits classiques non re-vérifiés explicitement listés dans Fact-Check-Log (section dédiée) au lieu d'être silencieusement affirmés ; dates arrondies ("fin des années 1960") quand la précision n'était pas certaine.
- Zone de risque résiduel identifiée pour la relecture humaine : les détails de protocoles anciens (Forer 1948, Newton 1990, Wald 1943) reposent sur la connaissance interne du modèle.

## Ajustements recommandés pour le prompt de production (500 pages)

- **Format YAML** : à garder tel quel, ajouter un champ `vérifié_le: AAAA-MM-JJ` pour dater les fact-checks (les statuts vieillissent).
- **Structure de page** : à garder ; autoriser explicitement la fusion de sections Contexte+Mécanismes pour les pages type terme/deep-cut.
- **Règles wikilinks** : à garder (8-12/page) ; ajouter la règle appliquée ici : vérification scriptée fantômes/orphelines obligatoire en fin de chaque cluster, et densification ciblée des nœuds à moins de 2 backlinks.
- **Règles fact-check** : passer de "2 recherches max par page" à "1 recherche groupée par dossier controversé + 1 par personne", et imposer la section "faits non re-vérifiés" dans le log, qui rend le risque résiduel visible au lieu de le cacher.
- **Règles multi-agent** : pour 500 pages, paralléliser par cluster (1 agent par cluster de 30-50 pages) avec ce vault pilote comme référence de style, puis une passe centrale unique pour les liens inter-clusters et l'audit. Ne pas paralléliser à l'intérieur d'un cluster : la cohérence des wikilinks en souffrirait.
- **Rythme** : les pages controverses coûtent environ le double des pages concept (fact-check + prudence rédactionnelle) ; planifier les clusters en conséquence.

## Estimation pour scaling x10 (500 pages)

- Temps : 10 à 15 sessions de la taille de celle-ci (une par cluster), soit 12-20h de wall time agent, parallélisables par cluster.
- Coût tokens : le pilote a consommé de l'ordre de 45-60k tokens de sortie ; extrapolation 500 pages : ~600-800k tokens de sortie plus les recherches, soit un ordre de grandeur de 150-300€ selon le modèle utilisé, cohérent avec la fourchette annoncée par le guide (150-400€).
- Points de vigilance : dérive de style entre clusters (imposer 2-3 pages du pilote comme exemplaires dans chaque prompt de cluster), collisions de titres inter-clusters (tenir un index global des titres), vieillissement des statuts (re-vérifier les pages `débattu` à chaque extension), et wikilinks inter-clusters à faire dans une passe dédiée finale.

## Prochaine étape recommandée

1. Relire 3 pages au hasard + les 3 débunkées (le ton "tranché mais sourcé" est le plus dur à calibrer).
2. Vérifier la liste "faits non re-vérifiés" du Fact-Check-Log.
3. Choisir les 10-12 clusters suivants (candidats naturels listés en section Pages-ponts du MOC : mémoire, influence et persuasion, psychologie sociale des groupes, décision financière, désinformation, psychologie de l'apprentissage...).
4. Rédiger le prompt de production à partir des ajustements ci-dessus.
