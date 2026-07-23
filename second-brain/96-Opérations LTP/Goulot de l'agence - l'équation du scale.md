---
titre: "Goulot de l'agence - l'équation du scale"
type: plan
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-23
tags: [ops/scaling, ops/goulot, ops/pilotage, contexte/business]
liens_forts: ["[[Théorie des contraintes]]", "[[Cockpit opérationnel LTP (actions)]]", "[[Manager 200 clippers par un système]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Supervision chatting (top 5) et le cas Sarah]]"]
---

# Goulot de l'agence — l'équation du scale

> [!tip] Verdict
> **Ne re-débats plus jamais « je fais quoi pour scaler ». Réponse figée :**
> `CA = (clippers productifs) × (subs/clipper) × (€/sub)`
> Tes 3 goulots sont les 3 facteurs, et **ton temps** est le méta-facteur qui décide si tu peux seulement travailler dessus. Pour ×N, tu ne fais PAS ×N sur un facteur (surtout pas « recruter plus », le facteur qui fuit) — tu améliores **modérément chacun** et ça compose. La séquence est **fixe** : libère ton temps → bouche la fuite rétention → scale le trafic monétisé → PUIS recrute. Recruter dans un seau percé = financer du churn. Données à jour **2026-07-23**.

## Les chiffres réels (le point de départ)

| Métrique | Valeur (juillet 2026) |
|---|---|
| CA run-rate agence | ~**64 k€/mois** |
| Ta part | ~**15 %** (50 % part agence − ~20 % coûts, ÷2 Maxence) |
| Clippers sous contrat | ~**12** |
| Profit par clipper **productif** | ~**550 €/mois** |
| CPA par hire retenu | **700-1 200 €** |
| Objectif | **500 k€/mois** (~8× le run-rate actuel) |

## L'équation, décomposée (chaque facteur, son driver, son goulot)

| Facteur | = | Driver | Goulot | Où on agit |
|---|---|---|---|---|
| **Clippers productifs** | recrutés × **taux de rétention** | survie à J+30/J+90 | **#1 Rétention** — tu recrutes, ils churnent avant d'être productifs (réf. tâche : ~68 % partis à 6 mois) | [[Manager 200 clippers par un système\|protocole J0-J30]] + paie sacrée |
| **Subs / clipper** | cadence × **reach** | le clip sort-il des recos ? | **#2a Reach** — depuis le crackdown Meta (30/04/2026), un clip non transformé = 0 vue = 0 trafic | [[Brief montage clipper (standard anti-crackdown 2026)\|brief]] + Content Protection + collab posts |
| **€ / sub** | **LTV créatrice** × conversion chatting | le sub rapporte-t-il ? | **#2b Monétisation** — volume envoyé à une LTV faible ne se transforme pas en cash | [[Supervision chatting (top 5) et le cas Sarah\|clonage top 5]] + concentration hautes LTV |
| *(méta)* **Ton temps** | — | tout passe par toi | **#3 Founder-goulot** — une machine qui dépend de toi plafonne à tes heures | [[Les 6 Loom de délégation manager (passation été)\|Loom]] + Manager + pipeline d'exceptions |

## Pourquoi le multiplicatif change tout

Aucun facteur ne se fait ×8 seul. Mais **×2 sur chacun = ×8** (2³). Et pour doubler d'abord :

| Cible | Rétention | × Reach | × €/sub | = CA |
|---|---|---|---|---|
| 64 k → **128 k** | ×1,26 | ×1,26 | ×1,26 | **×2** |
| 64 k → **~500 k** | ×2 | ×2 | ×2 | **×8** |

Aucun de ces ×1,26 n'est héroïque. **C'est ça, la découverte** : « recruter plus » ne touche qu'UN facteur (et le plus fuyard). Le scale vient de la **composition**, pas d'un levier unique.

## Les faux goulots (ce qui SEMBLE être la réponse et ne l'est pas)

- ❌ **« Recruter plus »** — tu as les leads (133 dormants). Le débit n'est pas gated par l'entrée, mais par la survie.
- ❌ **Un 2ᵉ business / coaching** — split de focus, ne touche aucun facteur ([[Journal de coaching\|décision 23/07]]).
- ❌ **Coder des features de bot** — compétence-confort, pas le goulot.
- ❌ **Un nouveau rail crypto / outil** — de la plomberie, jamais le goulot.

## La séquence (l'ordre est fixe, pas au hasard — [[Théorie des contraintes]])

1. **Libère ton temps (#3)** — délègue/systématise (Loom + Manager). Sinon tu ne peux rien faire d'autre.
2. **Bouche la fuite (#1)** — rétention J0-J30 + paie J+7/J+8 sacrée. Sinon recruter = financer du churn.
3. **Scale le trafic monétisé (#2)** — reach crackdown-proof × pointé sur hautes LTV × chatting cloné.
4. **PUIS recrute** (tu as les leads) et signe des créatrices haute LTV.
5. Le goulot **bouge** (probablement vers ta capacité de management) → on re-diagnostique.

## Comment mesurer (le tableau de bord du scale)

- **KPI roi** : **subs générés / heure de TON temps**. Monte → tu scales. Stagne → tu es redevenu le goulot.
- Par facteur : rétention J+30/J+90 par cohorte (#1) · subs/pod/semaine × reach (#2a) · €/sub par créatrice (#2b) · exceptions qui remontent à toi/semaine (#3).

## Prédiction datée (2026-07-23)

**Le clonage du top 5 chatteurs (+3-5 k€/mois, coût marginal ~0) doit être activé AVANT de dépenser 700-1 200 € à recruter le clipper N+13.** Raison : c'est un *exploit* du facteur €/sub à ROI immédiat, alors que le 13ᵉ clipper est un *élargissement* du facteur clippers, discounté par le churn tant que la rétention n'est pas bouchée.

- **Pari** : clonage top 5 activé → **+3-5 k€/mois sous 4-6 semaines**, sans un seul clipper de plus.
- **Contre-scénario** : si Gaëtan recrute d'abord (facteur qui fuit) au lieu d'exploiter le chatting, le CA reste ~plat (le volume ajouté ne monétise pas mieux, et une partie churne).
- **Revue** : à la reprise (septembre), comparer le delta CA du clonage chatting vs le coût des recrues N+13→N+18.

## Le pont vers l'action

Cette page = le **pourquoi**. Le **quoi-faire-quand** vit dans [[Cockpit opérationnel LTP (actions)]] (mode owner 4h/jour, mêmes 3 facteurs). On ne relit cette page que pour re-trancher une priorité de scale — jamais pour agir au quotidien.
