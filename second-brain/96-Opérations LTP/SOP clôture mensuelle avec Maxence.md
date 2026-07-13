---
titre: "SOP clôture mensuelle avec Maxence"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-13
tags: [ops/finances, ofm/agence, perso/finances, ops/sop]
liens_forts: ["[[Analyse finances perso (13 juillet 2026)]]", "[[Suivi trésorerie quotidien]]", "[[Opération fiscalité propre (France → Dubaï)]]", "[[LTP Models]]"]
---

# SOP clôture mensuelle : le 1er du mois, en 3 couches, dans un Sheet

> [!tip] Verdict
> Votre calcul de juin (fait le 1er juillet sur WhatsApp) est **honnête mais construit pour ne jamais accumuler** : les dépenses perso passent AVANT le split, **0 % du profit reste dans la boîte**, et ~3 500 € de dépenses ne sont pas détaillées. Résultat mécanique : 9 416 € de profit en juin → **0 € capitalisé**. La nouvelle clôture garde exactement votre logique (vous savez déjà la faire à deux) mais la passe en **3 couches étanches** : P&L agence → **allocations avant distribution** (réserve impôts + coffre boîte) → perso chacun chez soi. Tu ne pars pas de zéro : c'est le système d'allocations que vous aviez **déjà sur le Qonto en 2024-2025** (Taxes 15 % / Profit 20 % / Owner Pay 10 %) et que le déménagement à Dubaï a perdu ([[Analyse finances perso (13 juillet 2026)|la preuve dans les données]]). Sur juin, cette mécanique aurait capitalisé **~2 600 €** au lieu de 0 — soit ~15 k€ au 31/12 sans effort supplémentaire.

## Le calcul de juin, relu (les vrais chiffres du 01/07)

| Étape | Montant | Détail |
|---|---:|---|
| Commissions d'agence | **14 890 €** | Chloé 5 661 · Sophie 3 687 · Marie 2 310 · Jade 2 074 (58 % de part MYM+OF) · Amanda 657 · Sarah 501 |
| − Dépenses business | **−5 474 €** | dont visibles : prestataire vidéo 638 € · Emma 420 € · MyPulse ×4 ~194 € dus · Metricool ×3 114 € · Rulta/DMCA 100 € · GAML 51 $ · BioSpoofer 99 $ · Loom 32 € · Opus Clip 15 € · frais de change ~150 € — **~3 500 € non détaillés dans les captures** |
| = Profit agence | **9 416 €** | marge 63 % sur commissions |
| − Dépenses perso partagées | −2 350 € | ⚠️ le défaut n°1 (inclut ton loyer 7 500 AED, période colocation) |
| = Solde partagé | 7 066 € → **3 533 € chacun** | ajustements tracés : Amanda 657 déjà chez Maxence, +35 de rabe → **2 911 € versés** |

**Ce qui marche déjà** : le rituel existe, il est fait à deux, les ajustements sont écrits. **Les 3 défauts qui garantissent le plafond** :
1. **Le perso avant le split** : le business paie vos vies avant de dégager un profit réel — personne ne voit ce qu'il consomme, et le profit affiché n'atterrit jamais. La colocation étant finie, cette couche meurt de toute façon.
2. **0 % retenu dans la boîte** : pas de réserve impôts, pas de coffre opérationnel — chaque mois repart de ~0, et chaque vague de clippers se finance au feeling ([[Suivi trésorerie quotidien|le garde-fou runway]]).
3. **WhatsApp comme registre** : pas d'historique exploitable, ~3 500 € de dépenses en bloc opaque, et des frais invisibles qui durent (le change EUR→AED a coûté **~150 € sur une seule conversion de 6 350 €, ~2,4 %** — annualisé, ~1 800-2 200 € qui partent en spread : à batcher en 1 conversion/mois et à comparer avec une alternative type Wise).

## La nouvelle clôture (30 min, le 1er du mois, Google Sheet partagé)

### Couche 1 — Le P&L agence (ce que vous faites déjà, en propre)
Commissions par créatrice (mêmes colonnes chaque mois) − **dépenses business ligne à ligne** (fini le bloc opaque : chaque ligne a un nom et une catégorie — outils / paies / ads / DMCA / frais bancaires) = **profit agence**.

### Couche 2 — Les allocations AVANT distribution (le Profit First restauré)
Dans cet ordre, le jour même :
1. **Réserve impôts : 5 % du profit** → sous-compte dédié Wio. Voir l'encadré CT ci-dessous — même si l'impôt dû est probablement 0 % jusqu'à fin 2026, **la réserve se constitue quand même** (la discipline vaut plus que le taux, et 2027 arrive vite).
2. **Coffre boîte : 10 % du profit** → réserve opérationnelle, cible **3 mois de charges fixes (~15-20 k€)**. C'est elle qui finance les vagues de clippers sans stress et encaisse un ban plateforme ([[Analyse dashboard OFM (13 juillet 2026)|le risque n°1]]).
3. **Le reste = distribuable**, split 50/50, ajustements tracés dans le Sheet (Amanda → Maxence, etc.). ⚠️ **Rappel structurel** : Maxence a **sa propre société** — son versement est un **règlement inter-sociétés**, pas une distribution interne. Il doit s'appuyer sur un contrat + une facture mensuelle (point [[Opération fiscalité propre (France → Dubaï)|fiscaliste]]) ; la clôture fournit justement le montant à facturer.

### Couche 3 — Le perso (chacun chez soi, plus jamais dans le calcul)
Le jour où ta part arrive : **30 % → coffre intouchable AVANT toute dépense** ([[Analyse finances perso (13 juillet 2026)|le système anti-plafond]]), le reste = ta vie et tes investissements (filtrés par la règle anti-impulsion : quelle contrainte ça lève + payback écrit). Les dépenses perso **ne remontent jamais** dans la clôture business.

### Juin rejoué avec la mécanique (pour voir la différence)

| | Calcul réel de juin | Nouvelle mécanique |
|---|---:|---:|
| Profit agence | 9 416 € | 9 416 € |
| Réserve impôts (5 %) | 0 € | 471 € |
| Coffre boîte (10 %) | 0 € | 942 € |
| Part de chacun | 3 533 € (après perso partagé) | 4 001 € (brut, vie non déduite) |
| Ton coffre perso (30 % de ta part) | 0 € | 1 200 € |
| **Capitalisé ce mois** | **0 €** | **~2 613 €** |

## ⚠️ Encadré Corporate Tax UAE (to-verify — à trancher cette semaine)

- La CT émirienne = **9 % au-delà de ~375 000 AED de bénéfice/an** (~94 k€). Votre run-rate (~9,4 k€/mois ≈ 415 k AED/an) est **au-dessus du seuil** — vous êtes dans le champ.
- MAIS le **Small Business Relief** ramène l'impôt à 0 si le CA ≤ 3 M AED (élection à faire dans la déclaration), pour les exercices allant jusqu'à fin 2026. Votre CA (~800 k AED/an) est **largement éligible**.
- **L'enregistrement à la Corporate Tax : ✅ fait** (confirmé par Gaëtan le 13/07 — la FZ LLC est enregistrée, pas de pénalité). Reste UNE chose à verrouiller : **l'élection du Small Business Relief dans la déclaration CT** (elle ne s'applique pas automatiquement — à confirmer avec l'agent free zone / le fiscaliste, [[Opération fiscalité propre (France → Dubaï)|même rendez-vous]]).

## Les règles du rituel

1. **Un Sheet partagé, pas WhatsApp** : mêmes colonnes chaque mois, l'historique devient un actif (tendance de marge, saisonnalité, coût par pôle).
2. **Chaque ajustement s'écrit** (qui a reçu quoi en direct, les rabes) — vous le faites déjà, on le garde.
3. **La clôture nourrit le [[Suivi trésorerie quotidien]]** : après la clôture, les seuils de recrutement se relisent (cash ≥ 1 mois de burn → vague suivante).
4. **Désaccord → au call suivant**, pas en messages différés sur 3 semaines.
5. **Propriétaire : toi** (tu reçois les fonds et répartis), **Maxence contrôle** — 30 minutes, pas plus. Décision et prédiction [[Journal de coaching|journalisées]].

## Sources

[^1]: Calcul interne du 01/07/2026 (WhatsApp, captures) : commissions 14 890 €, dépenses 5 474 €, profit 9 416 €, versement final 2 911 € — chiffres conservés tels quels, périmètre partiel sur le détail des dépenses.
[^2]: Export OCR Qonto SAS 2024-2025 : sous-comptes d'allocation (Taxes/Profit/Owner Pay/Operating Expenses puis Créatrice/Team/Profit/TVA/ADS) — la preuve que le système a déjà existé. Cadre : Profit First (Michalowicz), pay-yourself-first (Hormozi). Règles CT UAE : `to-verify` auprès de l'agent free zone / fiscaliste.
