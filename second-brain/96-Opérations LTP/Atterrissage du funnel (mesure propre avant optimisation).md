---
titre: "Atterrissage du funnel (mesure propre avant optimisation)"
type: méthode
cluster: "96-Opérations LTP"
statut: to-verify
créé: 2026-07-19
tags: [ops/marketing, ops/clippers, méthode/mesure, plan/richesse]
liens_forts: ["[[LTP Models]]", "[[Plan richesse (100 actions triées par levier)]]", "[[Fact-Check-Log]]", "[[Machine de recrutement clippers (100 leads par mois)]]", "[[Journal de coaching]]"]
---

# Atterrissage du funnel — fondamental n°6, rétracté puis reconstruit (19/07)

> [!tip] Verdict
> **La version du 19/07 matin était fausse, Gaëtan l'a démontée : les stats fondatrices (« part de trafic externe 4 % », « LinkMe 18 % vs GAML 2 % = ×9 ») étaient des artefacts de la bascule payant → gratuit sur le compte de Jade** — un compte qui change de régime convertit mécaniquement différemment, comparer les deux périodes ne mesure rien. Le « ×3-4 le rendement de chaque clipper » est **rétracté** ([[Fact-Check-Log]]). **Ce qui survit** : le principe qu'un clic payé mérite un atterrissage mesuré — mais on ne sait aujourd'hui **ni** si l'atterrissage est bon **ni** s'il est mauvais, parce que la mesure n'a jamais été propre. Le fondamental n°6 devient donc : **construire la baseline propre d'abord, optimiser ensuite** — et il descend en priorité derrière les fondamentaux 1-5 tant que la baseline n'existe pas.

## Pourquoi la mesure était sale (la leçon de méthode)

Trois contaminations classiques, toutes présentes :
1. **Changement de régime** : payant → gratuit sur Jade au milieu de la fenêtre — la conversion clic→sub d'une page gratuite n'est pas comparable à celle d'une page payante.
2. **Sources mélangées** : un même lien recevait du trafic de canaux différents (clips, bio, SFS) — la « conversion du lien » moyenne des choses incomparables.
3. **Fenêtres non alignées** : comparer un outil sur une période A à un autre sur une période B mesure la saisonnalité, pas l'outil.

**Règle gravée** : toute stat de conversion s'accompagne de son régime (payant/gratuit), de sa source et de sa fenêtre — sinon elle ne rentre pas dans une décision. (La même règle qui a produit l'encadré « deux devises, deux périodes » de [[LTP Models]].)

## Le protocole de baseline propre (pendant l'absence, sans toi)

1. **Un lien tracké PAR canal PAR créatrice** (GetAllMyLinks le permet déjà) : clips IG / clips TikTok / bio / SFS / trafic interne — jamais un lien partagé entre canaux.
2. **Fenêtre de 14 jours à régime constant** : aucune bascule payant/gratuit, aucun changement de pricing pendant la mesure.
3. **Trois chiffres par ligne** : clics → subs (conversion d'atterrissage) → **LTV 30 j par source** (le seul juge final — un canal qui convertit fort à 2 € perd contre un canal qui convertit faible à 10 €).
4. **Sortie** : un tableau canal × créatrice qui dit enfin où va l'euro marginal de clipping. C'est LUI qui décidera si l'optimisation d'atterrissage (bio, landing, routing) vaut des jours de travail — pas une intuition.

## Ce qu'on peut déjà faire sans attendre (coût ~0, sans risque de sur-optimiser du bruit)

- **Hygiène minimale des bios** : lien unique tracké, promesse claire, zéro lien mort — c'est de la maintenance, pas de l'optimisation.
- **Taguer la bascule de Chloé** (passage gratuit du 14/07) comme événement dans le suivi — pour ne pas refaire l'erreur Jade dans un mois.

## Prédiction falsifiable ([[Journal de coaching|journal]])

À fin août, le tableau canal × créatrice existe avec 14 jours propres par ligne. **Si l'écart de conversion entre canaux à régime constant dépasse ×2, l'optimisation d'atterrissage redevient un chantier prioritaire (chiffré cette fois) ; s'il est < ×2, le chantier est enterré** et l'énergie va ailleurs — dans les deux cas, on aura décidé sur une mesure, pas sur un artefact.

## Sources

[^1]: Correction de Gaëtan (19/07) : les stats LinkMe/GAML et « 4 % externe » proviennent de la période de bascule payant→gratuit de Jade — artefact consigné au [[Fact-Check-Log]]. Chiffres 30 j de référence : Jade MYM 1 200 € / 121 subs (LTV 10 €), OF 1 900 $ / 200 subs (9,5 $) — [[LTP Models]].
