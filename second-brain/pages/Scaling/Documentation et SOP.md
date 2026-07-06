---
titre: "Documentation et SOP"
type: méthode
cluster: "Scaling"
statut: verified
controverse: low
importance: standard
source_knowledge: internal
sources_count: 2
tags: [scaling/documentation, pont/ia]
créé: 2026-07-06
liens_forts: ["[[Systèmes et process]]", "[[Délégation]]", "[[Malédiction de la connaissance]]"]
liens_opposition: []
---

# Documentation et SOP

> [!info] Résumé
> La documentation est la mémoire externe de l'entreprise : les SOP (standard operating procedures) transforment le savoir-faire des têtes en actif transférable, délégable et améliorable. À l'ère des agents IA, la documentation change de statut : un SOP bien écrit est un programme exécutable par un humain OU par une IA, ce qui en fait l'investissement au meilleur rendement du scaling.

## Définition

Un SOP est la description exécutable d'un processus : déclencheur, étapes dans l'ordre, critères de qualité, cas limites, et propriétaire. Le format qui marche : une checklist d'actions concrètes (verbes, écrans, exemples), pas une prose de principes ; testable par la règle d'or, une personne compétente mais nouvelle doit pouvoir exécuter sans poser de question, chaque question posée signalant un trou à combler ([[Onboarding et intégration|l'onboarding comme banc de test]]). La hiérarchie documentaire complète d'une PME : les SOP (comment faire), les playbooks (comment décider dans un domaine : vente, support), et la base de connaissances (ce qu'on sait : clients, marché, décisions passées et leurs raisons), ce vault appartenant à la troisième catégorie.

## Contexte et origine

La tradition vient de l'aéronautique et de la médecine, où la checklist a des résultats mesurés spectaculaires (la checklist chirurgicale OMS réduit les complications de façon substantielle, popularisée par Gawande[^1]), et de la culture qualité industrielle ([[Systèmes et process]]). La culture remote l'a promue en avantage compétitif : les entreprises distribuées performantes (GitLab et son handbook public en étant l'exemple extrême) écrivent tout, parce que l'écrit est asynchrone, scalable et débuggable là où l'oral s'évapore. L'IA générative achève la promotion : les agents exécutent d'autant mieux que le process est documenté, et la friction de production documentaire s'effondre (dicter, faire transcrire une session d'écran, faire rédiger le brouillon par l'IA).

## Mécanismes

Pourquoi on ne documente pas, et les correctifs. **La [[Malédiction de la connaissance]]** : l'expert trouve tout évident et écrit des documents à trous ; correctif, faire écrire le junior qui apprend (il voit les marches) et faire valider l'expert. **Le coût immédiat contre le bénéfice différé** : documenter coûte une heure aujourd'hui pour économiser cent heures diffuses ([[Coût d'opportunité]] inversé, le même mécanisme qui fait négliger [[Intérêts composés|la composition]]) ; correctif, documenter EN faisant (la règle "si tu l'expliques une deuxième fois, tu l'écris"). **La pourriture documentaire** : la doc fausse est pire que pas de doc (elle détruit la confiance dans toute la base) ; correctif, chaque document a un propriétaire et une date de revue, et la doc vit là où le travail se fait, pas dans un cimetière SharePoint.

Le rendement composé est le mécanisme central : chaque SOP libère du temps qui peut documenter le suivant, chaque question d'un nouveau améliore la base, et la base entière devient le manuel d'entraînement des humains ET le contexte des agents IA, double dividende propre à cette décennie.

## Nuances, critiques, limites

Sur-documenter est une pathologie réelle : documenter l'exceptionnel, le changeant ou le trivial produit de la bureaucratie ; la cible est le répétable stable à enjeu. Le handbook public à la GitLab est un choix stratégique, pas une norme : la plupart des entreprises documentent en interne. Et la documentation ne remplace ni la formation (lire n'est pas savoir faire) ni le jugement : les playbooks encadrent les décisions, ils ne les prennent pas, voir [[Cadres de décision]].

## Liens et implications

La documentation est l'infrastructure de la [[Délégation]], la matière des [[Systèmes et process]], le multiplicateur de l'[[Effet de levier]] (levier "code" du pauvre, immédiatement accessible), et l'actif que ce vault incarne. Méthode de production de SOP en 5 étapes dans `98-Rapports/Rapport Scaling`.

## Sources

[^1]: Atul Gawande, *The Checklist Manifesto*, Metropolitan Books, 2009.
[^2]: GitLab, *The GitLab Handbook* (documentation publique d'entreprise, le cas d'école du genre).
