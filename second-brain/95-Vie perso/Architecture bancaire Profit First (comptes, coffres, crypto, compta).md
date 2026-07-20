---
titre: "Architecture bancaire Profit First (comptes, coffres, crypto, compta)"
type: sop
cluster: "95-Vie perso"
statut: verified
créé: 2026-07-20
tags: [perso/finances, ops/finances, perso/fiscalité, méthode/allocation]
liens_forts: ["[[Profit First (Mike Michalowicz)]]", "[[SOP clôture mensuelle avec Maxence]]", "[[Plan richesse (100 actions triées par levier)]]", "[[Opération fiscalité propre (France → Dubaï)]]", "[[Pacte d'association LTP (partenariat 50-50 avec Maxence)]]", "[[Brief fiscaliste unique (LLC US en tête)]]", "[[Journal de coaching]]"]
---

# Architecture bancaire Profit First — comptes, coffres, crypto, compta (synthèse 3 agents, 20/07)

> [!tip] Verdict
> **Trois comptes, chacun un rôle étanche ; le business ne touche JAMAIS le perso, le coffre ne touche JAMAIS un flux plateforme.** ① **Wio Business** encaisse les commissions (€, facturées aux créatrices) et porte tout le business (paie chatteurs en crypto depuis un compte Binance **corporate**, réserves, part Maxence). ② **Wio Perso** reçoit ta part et sert à vivre (2 500 €/mois) — l'extraction en part d'abord. ③ **FAB (First Abu Dhabi Bank)** = le coffre intouchable, sans carte, en AED. **La vérité brutale des agents** : ce coffre externe rend **moins** que Wio (2-3,25 % vs 4,4-6 %) — tu ne le prends pas pour le rendement mais pour la **friction** (Profit First) et la **résilience compliance** (si Wio gèle un jour ta catégorie, le coffre ailleurs survit). Côté fiscal, **pas de montage malin à faire : le Small Business Relief te met à 0 % en 2026** (CA ~720 k AED ≪ 3 M) — il suffit de l'élire. Et le hop `Wio Business → Wio Perso → Binance` pour payer les chatteurs est le **seul vrai trou** du montage actuel : il casse la déductibilité CT, mélange les patrimoines et fragilise ta résidence 0 %.

## Le flux d'argent (corrigé le 20/07)

Les créatrices encaissent OF ($) et MYM (€) sur **leurs propres comptes en France** ; **tu leur factures la commission d'agence** (Chloé 40 %, Sarah/Maddy/Sophie 50 %, le reste 50 %). **Le revenu de LTP = la somme des commissions facturées**, qui arrivent en **€** sur Wio Business. Pas de pass-through créatrice chez toi. → La conversion de devises se joue donc à l'**entrée** (€ → AED/USDT), pas sur les payouts plateforme.

## Les 5 poches et leurs rôles

| Compte | Rôle | Spaces / sous-comptes |
|---|---|---|
| **① Wio Business** (banque, pas EMI¹) | Encaisse les commissions €, porte le business | Paie chatteurs · Réserve CT 5 % · Coffre boîte 10 % (cible 15-20 k€) · Part Maxence · Fond de roulement |
| **② Wio Perso** | Ta part → ta vie (2 500 €/mois) | Extraction 15-30 % (transit coffre) · budget DCA BTC |
| **③ FAB — coffre intouchable** | Le « Vault » Profit First, sans carte | iSave (~3,25 %, liquide) + **échelle de DAT AED** (bloqué) |
| **④ Coffre crypto** | Spéculation bornée décorrélée | **BTC ≤ 5 %**, cold storage (Ledger/Trezor) |
| **⑤ IBKR** | Au-delà du coffre plein | Monétaire USD (~3,6 %) → ETF monde UCITS |

## La cascade mensuelle

```
Commissions facturées (€ sur Wio Business)      ← le CA de TA société (~15 k€/mois)
  − Frais communs : chatteurs (Binance corp.), VA, ads, outils   ← coûts d'exploitation, avant partage
  = Profit mensuel
      → 50 % Maxence : sa société te FACTURE ses services (charge déductible arm's length ;
                       il paie SA propre CT dessus) → virement interne Wio → son Wio (zéro FX)
      → 50 % TOI = ton dû. Ça reste dans TA société (à toi à 100 %).
                   Tes allocations Profit First, sur TA part :
                     · Réserve CT (ta CT — ~0 % en 2026 via SBR, provision 2027)
                     · Coffre boîte (TA réserve opérationnelle, cible 15-20 k€)
                     · Extraction 15-20 % (→30 %) → Wio Perso → coffre FAB (AVANT de vivre)
                     · reste = ta vie 2 500 € + DCA BTC
```
> **Pourquoi les réserves sont APRÈS le 50/50** : Maxence n'est pas actionnaire de LTP, c'est un prestataire payé 50 % du profit (sa société facture, charge déductible → il paie sa propre CT). Donc sa part sort comme un **coût**, et ce qui reste est **ta société = à toi**. Mettre la réserve CT ou le coffre boîte *avant* le partage reviendrait à faire co-financer par Maxence des réserves qu'il ne possède pas. ⚠️ Contrepartie à assumer : c'est donc **toi seul** qui finances le coffre boîte (le filet qui protège l'opération commune) — si un jour vous voulez en faire un fonds vraiment commun, ça se formalise au pacte.

## Le coffre perso — FAB, en AED, sans carte

**Banque : First Abu Dhabi Bank** (la plus systémique des EAU, ~Aa3/AA-, souverain Abou Dhabi). Emirates NBD = équivalent si tu veux des agences dans ta ville.
- **Poche liquide = FAB iSave** (~3,25 %, 0 AED de minimum, **sans carte par défaut**, 100 % dans l'app) — reçoit ton virement mensuel d'extraction.
- **Poche verrouillée = échelle de dépôts à terme AED** : dès que iSave dépasse ~5 000 AED, découpe en **4 tranches à 3/6/9/12 mois**, renouvellement auto à 12 mois. Friction maximale + une échéance tous les 3 mois pour une liquidité *planifiée* (rééquilibrage vers IBKR) + lissage du taux.
- **Devise = AED** (pegué à l'USD, et les DAT AED ~2-2,85 % rendent plus que les DAT USD de la même banque ; ta base de coûts est en AED). L'EUR ne sert à rien ici.
- **Plafond ≤ AED 100 000/banque** (voir garantie ci-dessous) ; au-delà de ~50 k€ → IBKR.

> [!info] « Pourquoi FAB à ~3 % plutôt que Wio Fixed Saving à 6 % ? » (question du 20/07)
> Légitime — 3 % vs 6 % sur 20 k€ = ~600 €/an. Trois vérités : **① Le 6 % est un taux conditionnel/promo** (boosté par un virement de salaire, et au-dessus du taux sans risque ~3,5-4,5 % → un taux d'acquisition, pas durable ; ne bâtis pas dessus). **② Wio Fixed Saving EST un coffre verrouillé** (bloqué sur la durée = la friction que tu cherches) — donc côté friction, Wio le fait. **③ MAIS garder le coffre dans Wio annule sa seule vraie mission** : survivre à un **gel de ton compte Wio** (revenu adulte = risque de gel réel). Si Wio gèle ta catégorie, opérationnel ET coffre partent ensemble.
> **La reco = découper par usage, pas choisir un taux** : le **coussin de survie 6-12 mois** (celui qui DOIT survivre à un gel) → **FAB, décorrélé** — tu n'optimises pas le rendement de ton extincteur. La **partie patrimoine au-delà** → **IBKR** (monétaire ~3,6-4 % puis ETF ~7 %, ségrégué, décorrélé de Wio ET du business — ça **bat** le 6 % Wio sur la durée). Et le **6 % Wio Fixed Saving**, garde-le pour ce qui reste **de toute façon dans Wio** (le **coffre boîte** opérationnel, déjà côté business). Bonus : ta preuve de salaire (mise en place pour le visa) peut débloquer le taux « salaire » Wio — `to-verify`.

> [!info] Deux corrections factuelles au vault (agents du 20/07 → [[Fact-Check-Log]])
> **¹ Wio n'est PAS un EMI** : c'est une **banque à part entière licenciée CBUAE** (capital 2,3 Md AED, 65 % ADQ + Alpha Dhabi = souverain Abou Dhabi, 10 % FAB). Le vrai EMI de ton montage, c'est **Yoursafe** côté flux FR. Donc le coffre externe n'est pas un « upgrade de sûreté d'établissement » — Wio est déjà solide ; le gain est la **friction + la séparation compliance**. **² La garantie des dépôts EAU existe désormais** : **AED 100 000 / déposant / banque** (~23-24 k€), Federal Decree-Law 6/2025 en vigueur le 16/09/2025 (Art. 122 CBUAE Rulebook). → Le haut de ta cible coffre (30 k€) **dépasse** le plafond garanti : plafonne à ~AED 100k/banque, ou bascule l'excédent en IBKR (titres ségrégués).

## Le setup Wio concret + Wio Invest (2 agents du 20/07)

> [!tip] Verdict Wio
> **Wio = ton orchestrateur Profit First quotidien (comptes, Spaces, Autopilot, export Sheet), PAS ton coffre-fort ultime.** Trois vérités qui cassent le fantasme « tout dans Wio, bloqué » : ① le **« 6 % » est un taux promo 1 mois conditionnel** (salaire + dépense) ; ② **« bloqué » est un mythe** — un Fixed Space se casse à tout moment (pénalité = intérêt réduit, pas un mur) ; ③ tout consolider dans Wio recrée le **point de défaillance unique** (un gel emporte flux + épargne + patrimoine ensemble). Donc : **Wio pour l'opérationnel, FAB pour le vrai coussin verrouillé, IBKR pour l'ETF.**

**Les plans** : **Wio Business Essential (99 AED/mois)**, pas Grow — Grow (249) ne débloque les Fixed Spaces + 1 % que si tu épargnes > ~90 k AED dans la boîte (pas ton cas). Sur Essential, l'épargne business = **0 %** → le coffre boîte y dort sans rendement (accepté : c'est du cash de sécurité, ~450-600 €/an de manque, pas un placement). **Wio Perso : Salary Plan (gratuit)**.

**Le 6 %** : salaire ≥ **15 000 AED/mois** (ta part ~16 000, OK) + dépense ≥ 5 000 AED/mois, **uniquement sur le Fixed Space 1 mois** (les termes longs rendent 4,4-4,5 %). ⚠️ **MAIS** un salaire auto-versé Wio Business → Wio Perso est un virement **interne** — il ne passe ni par le WPS ni par le FTS, donc **rien ne garantit qu'il déclenche le plan Salary**. **À demander à Wio Care (care@wio.io) avant de compter dessus.**

**Les Spaces** : max **10 par compte**. Flexible (pas de blocage, ~3 %) vs Fixed (1/3/6/12 mois). ⚠️ **Un Fixed Space se casse à tout moment** (pénalité douce) — friction, pas verrou. Le vrai « intouchable » = **DAT FAB**.

**Automatisation** : **Autopilot** (montant FIXE programmé, journalier/hebdo/mensuel) + Scheduled Transfers vers tout IBAN. ⚠️ **Pas de split en % du flux entrant** → tu poses des **montants fixes en AED** à chaque clôture, réajustés quand le CA bouge. C'est ça, ton Profit First automatisé chez Wio.

**Multi-devise** : Business tient AED/USD/EUR/GBP (IBAN par devise). Conversion Perso = **markup 1,5 % (cher)** → convertis tes € via **Wise (~0,4 %)**.

**Tracking Google Sheet** : **export CSV mensuel gratuit** calé sur ta clôture → import dans le Sheet (le meilleur rapport friction/valeur ; intégrations Wafeq/Fiskl si tu veux du temps réel, mais + une brique).

**Wio Invest (ETF)** : depuis le **10/06/2026**, Wio propose des **ETF UCITS irlandais iShares** (dès 10 $, USD, capitalisants) = fiscalement propre (15 % dividendes, **pas d'estate tax US**). ⚠️ **MAIS l'app vend AUSSI des actions US / ETF US-situs** (piège estate tax 40 % > 60 k$, jusqu'à ~176 k$ sur 500 k$) → **ne clique QUE l'UCITS** (domicile IE, tickers CSPX/VUAA/SWDA). Pour le patrimoine long terme, **IBKR reste meilleur** (FX ~0,002 % vs spread caché Wio, univers complet, titres ségrégués, **décorrélé**). Wio Invest = **rampe de démarrage UCITS acceptable** pendant le KYC IBKR (2-3 sem.), UCITS-only. **Jamais ton BTC sur Wio Invest** (cold storage).

**La carte finale (où va chaque box)** :

| Poche | Compte | Rendement | Vrai verrou ? |
|---|---|---|---|
| Fond de roulement (frais, Maxence transit) | Wio Business Essential | 0 % | non (opérationnel) |
| **Coffre boîte** (10 % de ta moitié, cible 15-20 k€) | Wio Business, Space Flexible | 0 % (Essential) | non |
| Paie chatteurs (provision) | Wio Business, Space Flexible | — | non |
| **Ta vie** (~75 %) | Wio Perso | 3 % courant | non (2 500 € charges) |
| **BTC** (5 %) | → Binance corp → cold storage | — | cold |
| **Coussin survie 6-12 mois** | **FAB, échelle DAT** | ~3 % | ✅ vrai verrou |
| **Extraction → patrimoine** (10 %→25 %) | **IBKR, ETF UCITS** | ~7 % LT | politique signée |

L'extraction remplit d'abord le **coussin FAB** (jusqu'à 15-30 k€), puis bascule sur l'**ETF IBKR**. Le 6 % Wio n'a de place que sur une **poche liquide accessoire** que tu acceptes de garder dans Wio — jamais le coussin de survie ni le patrimoine.

## Le rail crypto — payer les chatteurs proprement

**Le trou actuel à boucher** : `Wio Business → Wio Perso → Binance` fait transiter une charge business par ton compte perso. Ça casse trois choses qui valent des 5-6 chiffres : la **déductibilité CT** du coût chatteurs (~6,5-13 k$/an d'enjeu à 9 % dès 2027), l'**absence de commingling**, ta **story résidence 0 %** — et c'est une **violation des CGU Binance** (compte perso pour de la paie = motif de gel).

**La cible** :
1. **Compte Binance au nom de LTP International FZ-LLC** (corporate KYC), financé **directement depuis Wio Business**.
2. **Paie en Binance Pay P2P — gratuit** (0 € vs 64-190 $/mois pour les alternatives) ; fallback USDC sur L2 (~0,50 $) pour qui veut son propre wallet.
3. **Achète l'USDT dans la devise que tu tiens déjà** (tes € de commission → USDT, spread ~0,1 %) — **pas de détour par l'AED**.
4. **Un contrat de sous-traitance + relevé de payout par chatteur** → charge déductible substantiable (et couvre l'art. 238A côté FR).
5. Garde-fous : ne laisse sur Binance que le **fond de roulement de paie** (le coffre crypto est ailleurs, en cold storage) ; un **2ᵉ on-ramp licencié VARA en secours** (BitOasis ou Rain).

## Le coffre crypto — BTC borné, cold storage

**BTC uniquement, ≤ 5 % de l'investissable, DCA automatique** (jamais en manuel — tes 6 058 € de rafales impulsives sont documentés). Tu achètes sur un exchange **VARA licencié** (Binance FZE, BitOasis, Rain) puis tu **retires sur un Ledger/Trezor** — « not your keys, not your coins » (leçon FTX). **Un coffre crypto n'est PAS un tas de stablecoins** (UST → 0,04 $, USDC dépeg à 0,87 $ chez SVB, Celsius/BlockFi en faillite) : ta réserve stable, c'est le monétaire USD (IBKR) ou le DAT AED, jamais un « USDT à 8 % ». Dimensionne pour qu'un **−80 %** (drawdowns BTC historiques : −77 à −86 %) soit tenable par écrit avant d'entrer ; à 5 % d'alloc, −80 % = −4 % du total, encaissable.

## La conversion de devises

Tes commissions arrivent en **€**. Tu **gagnes** en € — donc tu convertis depuis ce que tu tiens, pas depuis l'AED.
- **Garde les € sur Wio** tant que tu n'en as pas besoin ; convertis vers USD via **Wise (~0,4 %)** plutôt que la banque UAE (~1,5-3 %). Ne convertis en AED que le **living**.
- **Maxence** : virement **interne Wio Business → Wio Business, même devise = zéro FX**.
- **Binance** : € → USDT directement, pas de round-trip par l'AED.
- **Batch : 1 conversion/mois**, calée sur la clôture ; pré-achète l'USDT du mois en une fois (pas 2 petits achats). Gain estimé : **~1 500-2 300 $/an** de frais évités.

## La compta et la Corporate Tax (RAKEZ, incorp. 09/10/2025)

> [!warning] La « déclaration de novembre » n'existe probablement pas côté société
> Rien de Corporate Tax ne tombe en novembre 2026 pour une boîte incorporée le 09/10/2025. Ce « novembre » = presque sûrement ton **TRC perso** (25/11), pas une obligation société. Le vrai calendrier : **enregistrement CT** dû ~9 janvier 2026 (fait, à confirmer via le TRN dans EmaraTax) ; **1re déclaration CT** due ~**30 septembre 2027** (période probable 09/10/2025 → 31/12/2026).

- **L'inconnue n°1 à lever** : la **date de clôture d'exercice dans ton acte (MoA/AoA)** — elle fixe ta période fiscale et l'échéance. Lis cette ligne.
- **0 % en 2026 via le Small Business Relief** (CA ≤ 3 M AED ; tu es à ~720 k). **À élire dans la déclaration** (pas automatique). Le QFZP est écarté (audit annuel + incompatible avec le SBR). Rappel : **les dividendes ne réduisent PAS la CT** (payés après impôt) — le 0 % vient du SBR, pas d'un montage.
- **Comptable : oui** (bookkeeper + déclaration CT ~5-10 k AED/an). **Auditeur : non** sous SBR (audit imposé seulement si QFZP ou CA > 50 M AED — `to-verify` que RAKEZ n'en demande pas au renouvellement). Registres conservés **7 ans**, compta de caisse autorisée sous 3 M.
- **Salaire** : pas obligatoire pour l'obligation WPS (RAKEZ hors WPS). Mais **verse-toi un salaire mensuel modeste, documenté** (contrat de travail + virement fixe libellé « Salary » + bulletin PDF) : zéro coût fiscal en 2026, mais **preuve de revenu** pour ton visa et un futur crédit immo, + base déductible prête pour 2027. Le surplus se sort en tirage (0 % perso). ⚠️ Ce salaire pourrait aussi débloquer le **6 % du Wio Salary Plan** — mais un virement **interne** Business→Perso ne qualifie peut-être pas (le plan reconnaît un crédit WPS/FTS) : à confirmer avec Wio Care avant de compter dessus.
- **Maxence** : sa société **te facture** ses services chaque mois (charge déductible arm's length, traitez-vous comme related parties par prudence) — jamais un « dividende ». Les créatrices co-signées qui paient déjà 50/50 les deux entités ne nécessitent pas de facture inter-sociétés.

## La checklist AVANT le départ (~26/07)

- [ ] **Ouvrir le compte FAB** (impossible à distance depuis la France — présence physique quasi exigée) ; iSave sans carte + prévoir l'échelle DAT.
- [ ] **Ouvrir le compte Binance corporate** (LTP FZ-LLC) et couper le hop par le perso.
- [ ] **Garder la SIM UAE active + tester les apps bancaires depuis l'étranger** (OTP/géofencing = piège d'accès à distance).
- [ ] **Lire le MoA** pour la date de clôture d'exercice + **confirmer le TRN CT** dans EmaraTax.
- [ ] **Formaliser** : contrat de salaire + 1er virement « Salary », et la facture inter-sociétés mensuelle de Maxence.
- [ ] **Trouver un bookkeeper** (mensuel, sépare de la clôture WhatsApp).

## Les 3 questions au comptable/fiscaliste (même RDV que le [[Brief fiscaliste unique (LLC US en tête)|brief fiscaliste]])

1. Date de clôture d'exercice (MoA) → période fiscale et échéance CT exactes ; j'élis le SBR (pas le QFZP), sans audit obligatoire — confirmes-tu ?
2. Reversement 50 % à Maxence : facture de services à quel taux arm's length, avec ou sans 5 % de VAT, related parties ou non ?
3. Quel salaire mensuel « raisonnable » me verser pour une preuve de revenu solide (visa, crédit immo) ET une charge déductible valable en 2027, sans requalification en dividende déguisé ?

## Prédiction falsifiable ([[Journal de coaching|journal]])

Si l'architecture est câblée avant le départ (FAB ouvert, Binance corporate, hop perso coupé, salaire documenté) : au prochain closing, **0 flux business sur un compte perso**, la paie chatteurs sort du business, et l'extraction perso démarre (≥ 600 €/mois vers le coffre FAB). Si le hop perso persiste, c'est le compte Binance corporate qui a bloqué (KYC adulte) — le point à débloquer en priorité.

## Sources & épistémique

[^1]: Synthèse de 3 agents de recherche du 20/07/2026 (banque physique + placements ; crypto/rails/conversion ; compta/CT/salaire), croisant le vault avec des sources officielles et marché 2025-2026 : CBUAE Rulebook Art. 122 + Federal Decree-Law 6/2025 (garantie des dépôts AED 100k) ; FTA/MoF (CT, Small Business Relief MD 73/2023, First Tax Period, audit MD 84/2025) ; VARA public register (Binance FZE, BitOasis, Rain licenciés) ; grilles de taux datées (FAB/ENBD/ADCB/Mashreq/Wio, 01/10/25→09/07/26) ; Binance Pay/Payouts fees ; Wise (mid-market, pas de transfert depuis l'AED). **Confirmé** : garantie AED 100k, Wio = banque CBUAE, SBR 0 % éligible, DAT physiques < Wio, dividendes non déductibles. **Probable** : ouverture FZ sans blocage chez FAB/ENBD/ADCB, coûts compta 5-10 k AED/an. **`to-verify`** (datés/volatils) : tous les taux exacts, l'audit sous SBR côté RAKEZ, la VAT inter-sociétés, la date de clôture d'exercice (à lire dans le MoA). Documents société (n° de registre, référence) **non commités** — hygiène PII.
