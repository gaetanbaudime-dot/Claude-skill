---
titre: "Automatisation et agents IA (SOP par des agents)"
type: concept
cluster: "Scaling"
statut: verified
controverse: medium
importance: haute
source_knowledge: internal
sources_count: 2
créé: 2026-07-20
tags: [scaling/automatisation, scaling/ia, ops/outils, méthode/levier]
liens_forts: ["[[Documentation et SOP]]", "[[Effet de levier]]", "[[Systèmes et process]]", "[[Se licencier de son propre poste]]", "[[Manager 200 clippers par un système]]"]
liens_opposition: []
---

# Automatisation et agents IA : la SOP exécutée par une machine

> [!info] Résumé
> L'automatisation est le **levier au coût marginal nul** ([[Effet de levier]]) : tu écris la règle une fois, elle s'exécute mille fois sans fatiguer ni oublier. Les agents IA sont l'étage au-dessus : ils n'exécutent pas seulement des règles fixes, ils **produisent le travail cognitif** (rédiger une SOP, nettoyer un tableur, faire une recherche, trier des candidatures). Mais le piège est partout dans le marketing 2026 (« un stack IA remplace une équipe entière ») : **l'IA est le multiplicateur d'un système, jamais sa source.** Elle amplifie une SOP claire et une donnée propre ; elle amplifie aussi le chaos si le système n'existe pas. La règle d'or : **automatiser ce qui est réglé, déléguer ce qui est relationnel, garder ce qui est jugement.**

## La frontière automatiser / déléguer / garder

| Couche | Quoi | Exemple LTP |
|---|---|---|
| **Automatiser** (coût marginal 0) | Ce qui est réglé, répétable, vérifiable | Bot : vérif subs, prépa des batchs de paie, FAQ onboarding, relances buddy, collecte du reporting |
| **Agent IA** (travail cognitif scalable) | Rédiger/faire évoluer SOP, nettoyer les sheets, trier, rechercher, drafter | Claude : SOP, scorecards, scripts d'entretien, distillation vault, les 10 agents du plan richesse |
| **Déléguer** (relationnel/humain) | Ce qui exige de la confiance et du contact | Emma (créatrices), Rianah (SFS), managers de pods (coaching) |
| **Garder** (jugement) | Règles, allocations, culture, deals, signature de la paie | Toi seul |

Confondre les couches = payer un humain pour ce qu'une règle fait mieux, OU confier à un bot une relation qui exige un humain.

## La SOP est le substrat commun

Une [[Documentation et SOP|SOP écrite]] est lisible par un humain **et** par un agent — c'est ce qui rend le savoir transférable aux deux. D'où la [[Buy Back Your Time (Dan Martell)|Camcorder Method]] doublée d'une transcription : le Loom forme l'humain, la SOP écrite alimente le bot FAQ et sert de prompt à l'agent. Pas de SOP = pas d'automatisation possible (tu ne peux pas automatiser un flou), et pas d'agent fiable (il hallucine le process manquant).

## L'avocat du diable (la dette et l'illusion)

- **« L'IA remplace l'équipe »** = marketing spéculatif. L'IA ne recrute pas tes clippers, ne monte pas tes créatrices, ne tient pas une relation créatrice. Elle rend chaque humain **plus productif** — le prochain euro va à l'acquisition de candidats, pas à un 3e abonnement premium.
- **Le bot est un point de défaillance unique** : automatiser concentre le risque. Un bot sur Railway sans moniteur, sans sauvegarde, sans payeur de secours = un lundi sans paie qui fait tout tomber → [[Continuité du bot et paie sacrée (plan anti-panne)]]. **Plus tu automatises, plus tu dois durcir.**
- **Garbage in, garbage out** : un agent sur une donnée sale (les stats d'atterrissage tirées d'une bascule payant→gratuit) produit une conclusion fausse avec assurance. La mesure propre précède l'automatisation de la décision.

## Application LTP

- **Le bot Discord (tunnel v5)** EST ta couche 0 : de l'annonce Indeed à la signature DocuSeal sans étape sans outil (liaison téléphone→Discord, quiz→test, contrat, grille de rôle, rappels, backup). Ce qui reste humain par design : la review des 2 clips, le contreseing 18+, la paie.
- **Les agents IA en action** : les 10 agents du [[Plan richesse (100 actions triées par levier)|plan richesse]] (recherche croisée vault + web), Claude pour distiller ce vault et écrire les SOP/scorecards. Multiplicateur du système, pas le système.
- **La règle d'allocation** : chaque nouvelle tâche passe la frontière ci-dessus AVANT d'embaucher. Beaucoup de « il me faut quelqu'un » sont en réalité « il me faut une règle dans le bot » ou « il me faut une SOP + un agent ».

## Sources

[^1]: Frontière automatiser/déléguer/garder et le bot comme couche 0 : [[Machine de recrutement clippers (100 leads par mois)]], [[Se licencier de son propre poste]], [[Continuité du bot et paie sacrée (plan anti-panne)]]. Réserve « l'IA remplace les équipes » = marketing : rapports agent du 19/07 (Fortune 2026, blog.mean.ceo) filtrés.
[^2]: SOP comme substrat lisible humain + agent : [[Documentation et SOP]], [[Buy Back Your Time (Dan Martell)]] (Camcorder Method).
