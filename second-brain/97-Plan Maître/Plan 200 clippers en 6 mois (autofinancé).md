---
titre: "Plan 200 clippers en 6 mois (autofinancé)"
type: plan
cluster: "97-Plan Maître"
statut: to-verify
créé: 2026-07-18
tags: [plan/scaling, ops/clippers, finance/tresorerie]
liens_forts: ["[[Machine de recrutement clippers (100 leads par mois)]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Plan Maître 500K]]", "[[Journal de coaching]]"]
---

# Plan 200 clippers en 6 mois — croissance autofinancée par cohortes

> [!tip] Verdict
> Objectif de Gaëtan (18/07, mode roue libre) : ~200 clippers actifs et **≥ 3 000 subs OF par créatrice sur 6 mois**, en « abusant un peu » sur la durée grâce à l'accélération du CA. Le plan tient sur UNE règle : **les fixes de la cohorte suivante sont financés par la marge nette clippers de la cohorte précédente** — le ratio de pilotage est `R = marge nette clippers du mois ÷ fixes versés du mois`. **R ≥ 1,2 → on ouvre la vague suivante ; R < 1 deux mois de suite → gel des entrées** (les commissions, elles, ne gèlent jamais). `statut: to-verify` : toutes les hypothèses se recalent au premier `!pipeline` du dimanche et à chaque clôture mensuelle.

## Les hypothèses (à recaler sur le réel chaque mois)

| Hypothèse | Valeur retenue | Source |
|---|---|---|
| Marge boîte par sub (avant commission clipper) | ~1,4 € (LTV 5 $ × marge 25-35 %) | [[LTP Models]] |
| Marge **nette** par sub (après 0,50 € clipper) | **~0,9 €** | économie unitaire du 18/07 |
| Médiane subs/clipper actif/mois (mature, M+2) | 150-250 (loi de puissance : le top fait ×5) | à vérifier — Julien : 600 le 1er mois |
| Fixe réellement versé / actif / mois | ~100 € (mix 40 % FR à 200 € · 60 % INT à 100 €, conditions remplies ~70 %) | grille + verrou |
| Churn mensuel | ~20 % (chiffre de Gaëtan) | à vérifier dès M1 |
| Funnel candidature → actif | ~8-12 % (133 fiches → à mesurer dimanche) | `!pipeline` |

## La trajectoire par cohortes (simulation churn 20 %)

`Actifs(M) = Actifs(M-1) × 0,8 + Recrues(M)` — départ 8 actifs :

| Mois | Recrues | Actifs fin de mois | Fixes (~100 €/actif) | Subs attendus (médiane 175, ramp 50 % le 1er mois) | Marge nette clippers | R |
|---|---|---|---|---|---|---|
| M1 (août) | 20 | ~26 | ~2,6 k€ | ~3 200 | ~2,9 k€ | ~1,1 |
| M2 | 30 | ~51 | ~5,1 k€ | ~7 100 | ~6,4 k€ | ~1,3 |
| M3 | 40 | ~81 | ~8,1 k€ | ~12 400 | ~11,2 k€ | ~1,4 |
| M4 | 50 | ~115 | ~11,5 k€ | ~18 100 | ~16,3 k€ | ~1,4 |
| M5 | 60 | ~152 | ~15,2 k€ | ~24 400 | ~22 k€ | ~1,4 |
| M6 (janvier) | 70 | **~192** | ~19,2 k€ | ~31 300 | ~28,2 k€ | ~1,5 |

Lecture honnête : **M1 est le mois fragile** (R ≈ 1,1, ramp des débutants) — c'est pour ça que le garde-fou trésorerie existant (~1 k€/mois de budget programme) saute progressivement et pas d'un coup. Cumul 6 mois ≈ **95 000 subs** ; sur ~10 créatrices ≈ 9 500/créatrice — **l'objectif « 3 000 subs/créatrice » est atteint même si la médiane réelle fait le TIERS de l'hypothèse**. Le vrai risque n'est pas l'objectif, c'est le churn et la médiane.

## Ce que chaque palier casse (à préparer AVANT d'y arriver)

| Palier | Ce qui casse | La parade à installer |
|---|---|---|
| ~30 actifs | Toi seul ne review plus tous les tests ni les reportings | **1er clipper manager promu** (track record tracké, jamais l'ancienneté) — commission de manager sur l'équipe, review des tests déléguée |
| ~60 actifs | Le contenu : 60 × 6 comptes = 360 comptes affamés | **Le format long → shorts** ([[Sprint été - croissance sans moi|étude Legend en cours]]) : 1 h de tournage = 40-60 clips vs 10 trends/semaine — c'est le déblocage n°1 |
| ~100 actifs | Le quiz/les réponses circulent, la formation se copie | Rotation de la banque de questions par cohorte + 2ᵉ manager + paie semi-automatisée (export `!pipeline` → virements groupés Wise) |
| ~150-200 | Toi = goulot des paiements et des contrats | 3-4 managers (1/25-30 actifs), paie déléguée avec double contrôle, DocuSeal en API (déjà fait ✅) |

## Ce qui ferait échouer le plan (avocat du diable)

1. **La médiane réelle < 100 subs/mois** → R passe sous 1 dès M2 : le gel automatique protège la trésorerie, mais l'objectif glisse de 2-3 mois. Premier signal : le `!pipeline` + tracking des 20 recrues d'août.
2. **Le churn réel > 30 %** (typique du travail à la tâche débutant) → il faut 2× plus de recrues pour la même base : la parade est la rétention des 2 premières semaines (quick wins, célébration publique — rapport de l'agent management en cours).
3. **Le contenu ne suit pas** : 200 clippers sans rushs frais = 200 démissions silencieuses. Le format long n'est pas un « bonus créatif », c'est la **condition d'existence** du palier 100+.
4. **Un incident CGU de masse** (vague de bans Meta sur les comptes) — dette structurelle assumée du modèle, non assurable : diversification FB (pages plus résistantes) + rampe warm-up stricte restent les seuls amortisseurs.

**Revues** : chaque dimanche (`!pipeline` + ratio R au reporting) · clôture mensuelle avec Maxence (R officiel) · gel automatique si R < 1 deux mois consécutifs. Prédiction au [[Journal de coaching]].
