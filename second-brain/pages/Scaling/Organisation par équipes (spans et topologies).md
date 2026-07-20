---
titre: "Organisation par équipes (spans et topologies)"
type: concept
cluster: "Scaling"
statut: verified
controverse: low
importance: haute
source_knowledge: internal
sources_count: 2
créé: 2026-07-20
tags: [scaling/organisation, ops/management, méthode/structure]
liens_forts: ["[[Manager 200 clippers par un système]]", "[[Se licencier de son propre poste]]", "[[Théorie des contraintes]]", "[[Délégation]]", "[[Rituels de management]]"]
liens_opposition: []
---

# Organisation par équipes : spans de contrôle et topologies

> [!info] Résumé
> Une organisation ne scale pas en ajoutant des gens — elle scale en **ajoutant des couches au bon moment, avec le bon span**. Deux variables gouvernent tout : le **span de contrôle** (combien de personnes une couche encadre) et la **topologie** (comment les couches s'emboîtent). Se tromper de span = soit un manager débordé (span trop large), soit une hiérarchie obèse qui étouffe (span trop étroit). Se tromper de topologie = un fondateur qui redevient le goulot parce que tout remonte à lui. La règle-mère : **la structure suit la contrainte** ([[Théorie des contraintes]]), et un fondateur absent a un span effectif bien plus petit qu'un fondateur présent.

## Les spans de contrôle (les ratios qui tiennent)

| Type de travail | Span sain | Pourquoi |
|---|---|---|
| Travail répétitif, mesuré automatiquement (clipping, posting) | **1:15-20** | Le tracking fait le contrôle ; le manager coache les exceptions |
| Travail avec coaching réel (chatting, vente) | **1:8-15** | Le feedback humain fréquent limite le nombre |
| Travail créatif/complexe (créatrices, stratégie) | **1:5-8** | Chaque cas est singulier |
| **Fondateur ABSENT** | **~5-8 exceptions**, pas des personnes | Tu ne pilotes pas des gens à distance, tu pilotes les *exceptions* que la machine fait remonter |

**Le piège de Peter** : ne jamais promouvoir le meilleur producteur (la perf de production prédit *négativement* la valeur managériale — Benson, Li & Shue 2019, 53 000 commerciaux). On promeut **celui qui aide déjà les autres**, payé fixe + override sur son pod, jamais sur ses recrutements (dérive MLM).

## Les topologies (comment on empile les couches)

- **Couche 0 — l'automatisation** : le bot collecte, vérifie, relance, répond aux FAQ. Coût marginal nul, ne fatigue pas. Elle absorbe tout le travail sans jugement ([[Automatisation et agents IA (SOP par des agents)]]).
- **Couche 1 — les managers de pods** : exceptions qualité + humaines (un test litigieux, une baisse de cadence).
- **Couche 2 — les leads seniors** : exceptions de règles (un cas que la règle ne couvre pas).
- **Couche 3 — toi** : exceptions de *système* (une règle manque, ou deux se contredisent). Ton seul travail hebdo non délégable : lire l'issue-log, modifier les règles, décider les promotions.

Une info qui n'exige pas TA décision ne doit jamais t'atteindre (Dalio) — sinon tu redeviens le goulot. C'est la mécanique qui rend le [[Se licencier de son propre poste|fondateur absent]] viable.

## Les seuils de déclenchement (quand ajouter une couche)

- **Avant 25 actifs** : nommer le 1er manager de pod (au-delà, tu ne peux plus reviewer les tests ni les reportings).
- **Deux-pizza teams** (Bezos) : une équipe qui ne se nourrit pas de 2 pizzas est trop grosse — au-delà de ~8-10, scinde en pods.
- **La couche se justifie par la contrainte, pas par l'ego** : ajouter un manager sur un process non prouvé = déléguer du chaos. On systématise (couche 0) AVANT de manager (couche 1).

## Application LTP

- **Le plan 200 clippers** = 10-13 managers en pods de 15-20 + 2-3 leads seniors + 1 rôle QA/paie : **trois couches, pas deux** ([[Manager 200 clippers par un système]]). Le 1er manager (Julien candidat) se nomme avant 25 actifs, sur le comportement d'aide observé dans le Discord.
- **Le pipeline d'exceptions est déjà câblé** : bot (tunnel v5) → manager → lead → toi. Pendant l'absence, seules les exceptions remontent (MP admin, reporting du dimanche) — le reste tourne.
- **Deux organisations parallèles** : ton pôle (acquisition : pods clippers + Emma CSM + Rianah SFS) et celui de Maxence (chatting : ~40 chatteurs + ~5 managers). Le pacte (Art 4) sépare les spans ; toi tu ne manages jamais les chatteurs, lui jamais les clippers.
- **Emma = un span de CSM sur les créatrices** : point de défaillance unique à doubler (doc + lien fondateur) — [[Se licencier de son propre poste|casquette 8]].

## Sources

[^1]: Spans de contrôle (BPO 1:8-15, travail tracké 1:15-20), principe de Peter (Benson, Li & Shue, QJE 2019), pipeline d'exceptions (Dalio/Gerber/Gawande) : distillés dans [[Manager 200 clippers par un système]] (recherche agent du 18/07, sources croisées). Two-pizza teams : doctrine Amazon (Bezos).
[^2]: Application chiffrée au roster et à l'organisation LTP : [[LTP Models]], [[Plan 200 clippers en 6 mois (autofinancé)]].
