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
> **Trois comptes, chacun un rôle étanche (restructuré le 20/07).** ① **Wio Business** encaisse les commissions (€, facturées aux créatrices) et porte tout le business (paie chatteurs depuis un compte Binance **corporate**, réserves, coffre boîte, part Maxence) — **c'est le FIREWALL : le business ne sort vers ton perso que par un salaire/drawing propre.** ② **FAB perso** (remplace Wio Perso) = ton **hub personnel** : ton salaire documenté y atterrit (via Wio Business Payroll), ta vie et ta carte AECB y tournent, une **échelle DAT AED sans carte** y fait le coffre local. ③ **IBKR** = ton **patrimoine ségrégué et décorrélé** (coussin monétaire + ETF UCITS) — l'argent « je reste en jeu quoi qu'il arrive ». **Les 3 garde-fous gravés** : FAB ne voit **JAMAIS** un flux business/adulte (une banque traditionnelle ferme vite → ça tuerait ta bankabilité), le coffre reste **sans carte** (friction Profit First), et le patrimoine n'est **JAMAIS** dans la même banque que ton income (sinon income + épargne gelés ensemble). Côté fiscal, **pas de montage malin : le Small Business Relief te met à 0 % en 2026** (CA ~720 k AED ≪ 3 M) — il suffit de l'élire. Le hop `Wio Business → Wio Perso → Binance` pour payer les chatteurs, c'était le **trou** du montage : coupé (Binance corporate direct).

## Le flux d'argent (corrigé le 20/07)

Les créatrices encaissent OF ($) et MYM (€) sur **leurs propres comptes en France** ; **tu leur factures la commission d'agence** (Chloé 40 %, Sarah/Maddy/Sophie 50 %, le reste 50 %). **Le revenu de LTP = la somme des commissions facturées**, qui arrivent en **€** sur Wio Business. Pas de pass-through créatrice chez toi. → La conversion de devises se joue donc à l'**entrée** (€ → AED/USDT), pas sur les payouts plateforme.

## Les 3 comptes et leurs rôles (restructuré le 20/07 — Wio Perso retiré)

*(Le « coffre crypto » a été **retiré le 20/07** — décision 0 % crypto, section dédiée plus bas ; il ne reste de crypto que le **rail Binance corporate pour PAYER les chatteurs**. Et **Wio Perso est retiré** : FAB devient le hub personnel, pour ne pas avoir income + savings éclatés sur deux banques.)*

| Compte | Rôle | Sous-comptes / usage |
|---|---|---|
| **① Wio Business** (banque, pas EMI¹) — *le firewall* | Encaisse les commissions €, porte tout le business | Paie chatteurs (Binance corp) · Réserve CT · Coffre boîte 10 % (cible 15-20 k€) · Part Maxence · Fond de roulement · **Payroll (SIF/WPS) → verse ton salaire** |
| **② FAB perso** — *le hub personnel* | Ton salaire y atterrit, ta vie y tourne | **Compte courant** (dépenses) + **carte de crédit payée à 100 %** (bâtit l'AECB) + **échelle DAT AED sans carte** (coffre local visible) |
| **③ IBKR** — *le patrimoine* | Le moteur, ségrégué et décorrélé | Coussin monétaire USD (~3,6 %) → **ETF monde UCITS** |

## La cascade mensuelle — le waterfall parfait (3 comptes)

```
COMMISSIONS facturées (€ → Wio Business)            le CA de TA société (~15 k€/mois)
  − Frais communs : chatteurs (Binance corp), VA, ads, outils   coûts d'exploitation, avant partage
  = PROFIT (~9,4 k€)
     │
     ├─► 50 % MAXENCE : sa société te FACTURE (charge déductible arm's length ; il paie SA CT)
     │                  → virement interne Wio → son Wio (zéro FX)
     │
     └─► 50 % TOI (~4 k€) — reste dans TA société (Wio Business), à toi à 100 %.
            Sur TA part, dans l'ordre :
              ① Réserve CT        → Space Wio Business    (~0 % en 2026 via SBR ; provision selon l'échelle)
              ② Coffre boîte 10 % → Space Wio Business    (cible 15-20 k€ PUIS stop → bascule en extraction)
              ③ SALAIRE documenté → Wio Business Payroll (fichier SIF) → FAB perso
              │        └─ ta VIE : dépenses + carte AECB + échelle DAT AED visible (savings locale)
              └─ ④ EXTRACTION 20 %→30 % (drawing) → FAB perso (ton nom) → sweep IBKR
                       └─ Phase 1 : coussin monétaire USD (15-30 k€)
                       └─ Phase 2 : ETF monde UCITS (le moteur)

  ═══ Les 3 garde-fous ═══
  • Wio Business = FIREWALL : le business ne sort vers FAB QUE par ③ salaire / ④ drawing propres.
    JAMAIS une commission ou une paie chatteur ne touche FAB (fermeture assurée sinon).
  • FAB ne voit qu'un SALARIÉ QUI ÉPARGNE (income + savings visibles = bankabilité), rien du business.
  • IBKR ≠ FAB : le patrimoine n'est jamais dans la banque qui tient ton income (anti-gel simultané).
```
> **Pourquoi l'extraction transite par FAB avant IBKR** : IBKR se finance depuis un compte **à ton nom** (règle anti-tiers). Wio Business est au nom de la société → l'extraction sort d'abord en drawing sur **FAB perso (ton nom)**, puis tu la **sweep vers IBKR**. Bonus : ce flux visible d'épargne renforce ton dossier bankabilité.
> **Pourquoi les réserves sont APRÈS le 50/50** : Maxence n'est pas actionnaire de LTP, c'est un prestataire payé 50 % du profit (sa société facture, charge déductible → il paie sa propre CT). Donc sa part sort comme un **coût**, et ce qui reste est **ta société = à toi**. Mettre la réserve CT ou le coffre boîte *avant* le partage reviendrait à faire co-financer par Maxence des réserves qu'il ne possède pas. ⚠️ Contrepartie à assumer : c'est donc **toi seul** qui finances le coffre boîte (le filet qui protège l'opération commune) — si un jour vous voulez en faire un fonds vraiment commun, ça se formalise au pacte.

## Le hub perso — FAB (compte courant + carte AECB + coffre sans carte)

**Banque : First Abu Dhabi Bank** (la plus systémique des EAU, ~Aa3/AA-, souverain Abou Dhabi). Emirates NBD = équivalent si tu veux des agences dans ta ville. **FAB remplace Wio Perso** et porte 3 usages distincts (même banque, comptes séparés) :
- **Compte courant + carte** = ta vie quotidienne : **ton salaire documenté y atterrit**, tes dépenses en sortent. Une **carte de crédit payée à 100 % chaque mois** bâtit ton **AECB** (le score crédit = le nerf de la bankabilité).
- **Poche liquide = FAB iSave** (~3,25 %, 0 AED de minimum, **sans carte par défaut**, 100 % dans l'app) — tampon + savings locale visible (la banque aime voir que tu épargnes).
- **Poche verrouillée = échelle de dépôts à terme AED** : dès que iSave dépasse ~5 000 AED, découpe en **4 tranches à 3/6/9/12 mois**, renouvellement auto à 12 mois. Friction maximale + une échéance tous les 3 mois pour une liquidité *planifiée* (rééquilibrage vers IBKR) + lissage du taux.
- **Devise = AED** (pegué à l'USD, et les DAT AED ~2-2,85 % rendent plus que les DAT USD de la même banque ; ta base de coûts est en AED). L'EUR ne sert à rien ici.
- **Plafond ≤ AED 100 000/banque** (voir garantie ci-dessous) ; au-delà de ~50 k€ → IBKR.
- **Double rôle si l'immo 2027 est sérieux (reframe du 20/07)** : au-delà du coffre, le compte FAB où **atterrit ton salaire documenté** + une **carte de crédit dédiée** (distincte du coffre sans carte, payée à 100 % chaque mois) fait office de **rail de bankabilité** — relation prêteur + historique AECB pour un futur crédit immo. Le crédit vient de la *trace* (revenu documenté + AECB + apport + DBR ≤ 50 %), pas du logo. Convergence « bankable ≈ fin 2027 » (dossier self-employed, ancienneté de trading, boîte incorporée 09/10/2025) détaillée dans [[Kill-list (NON, pas maintenant)|la kill-list, ligne 7]].

> [!info] « Pourquoi FAB à ~3 % plutôt que Wio Fixed Saving à 6 % ? » (question du 20/07)
> Légitime — 3 % vs 6 % sur 20 k€ = ~600 €/an. Trois vérités : **① Le 6 % est un taux conditionnel/promo** (boosté par un virement de salaire, et au-dessus du taux sans risque ~3,5-4,5 % → un taux d'acquisition, pas durable ; ne bâtis pas dessus). **② Wio Fixed Saving EST un coffre verrouillé** (bloqué sur la durée = la friction que tu cherches) — donc côté friction, Wio le fait. **③ MAIS garder le coffre dans Wio annule sa seule vraie mission** : survivre à un **gel de ton compte Wio** (revenu adulte = risque de gel réel). Si Wio gèle ta catégorie, opérationnel ET coffre partent ensemble.
> **La reco = découper par usage, pas choisir un taux** : le **coussin de survie 6-12 mois** (celui qui DOIT survivre à un gel) → **FAB, décorrélé** — tu n'optimises pas le rendement de ton extincteur. La **partie patrimoine au-delà** → **IBKR** (monétaire ~3,6-4 % puis ETF ~7 %, ségrégué, décorrélé de Wio ET du business — ça **bat** le 6 % Wio sur la durée). Et le **6 % Wio Fixed Saving**, garde-le pour ce qui reste **de toute façon dans Wio** (le **coffre boîte** opérationnel, déjà côté business). Bonus : ta preuve de salaire (mise en place pour le visa) peut débloquer le taux « salaire » Wio — `to-verify`.

> [!info] Deux corrections factuelles au vault (agents du 20/07 → [[Fact-Check-Log]])
> **¹ Wio n'est PAS un EMI** : c'est une **banque à part entière licenciée CBUAE** (capital 2,3 Md AED, 65 % ADQ + Alpha Dhabi = souverain Abou Dhabi, 10 % FAB). Le vrai EMI de ton montage, c'est **Yoursafe** côté flux FR. Donc le coffre externe n'est pas un « upgrade de sûreté d'établissement » — Wio est déjà solide ; le gain est la **friction + la séparation compliance**. **² La garantie des dépôts EAU existe désormais** : **AED 100 000 / déposant / banque** (~23-24 k€), Federal Decree-Law 6/2025 en vigueur le 16/09/2025 (Art. 122 CBUAE Rulebook). → Le haut de ta cible coffre (30 k€) **dépasse** le plafond garanti : plafonne à ~AED 100k/banque, ou bascule l'excédent en IBKR (titres ségrégués).

## Le setup Wio concret + Wio Invest (2 agents du 20/07)

> [!tip] Verdict Wio
> **Wio = ton orchestrateur Profit First quotidien (comptes, Spaces, Autopilot, export Sheet), PAS ton coffre-fort ultime.** Trois vérités qui cassent le fantasme « tout dans Wio, bloqué » : ① le **« 6 % » est un taux promo 1 mois conditionnel** (salaire + dépense) ; ② **« bloqué » est un mythe** — un Fixed Space se casse à tout moment (pénalité = intérêt réduit, pas un mur) ; ③ tout consolider dans Wio recrée le **point de défaillance unique** (un gel emporte flux + épargne + patrimoine ensemble). Donc : **Wio pour l'opérationnel, FAB pour le vrai coussin verrouillé, IBKR pour l'ETF.**

**Les plans** : **Wio Business Essential (99 AED/mois)**, pas Grow — Grow (249) ne débloque les Fixed Spaces + 1 % que si tu épargnes > ~90 k AED dans la boîte (pas ton cas). Sur Essential, l'épargne business = **0 %** → le coffre boîte y dort sans rendement (accepté : c'est du cash de sécurité, ~450-600 €/an de manque, pas un placement). **Plus de Wio Perso** : ta vie perso est passée sur **FAB** (hub perso, restructuration 20/07) ; Wio ne sert plus qu'au **business**.

**Le 6 % Wio Salary Plan : abandonné** — il dépendait de Wio Perso, désormais retiré. C'était de toute façon un **taux promo 1 mois conditionnel** (salaire ≥ 15 k AED + dépense ≥ 5 k AED, uniquement sur le Fixed Space 1 mois ; les termes longs rendent 4,4-4,5 %). Rien à regretter : ton patrimoine est chez **IBKR** (décorrélé, mieux sur la durée), pas dans un coffre Wio à taux d'appel. Ton salaire part maintenant en **WPS/SIF vers FAB**, pas en virement interne Wio.

**Les Spaces** : max **10 par compte**. Flexible (pas de blocage, ~3 %) vs Fixed (1/3/6/12 mois). ⚠️ **Un Fixed Space se casse à tout moment** (pénalité douce) — friction, pas verrou. Le vrai « intouchable » = **DAT FAB**.

**Automatisation** : **Autopilot** (montant FIXE programmé, journalier/hebdo/mensuel) + Scheduled Transfers vers tout IBAN. ⚠️ **Pas de split en % du flux entrant** → tu poses des **montants fixes en AED** à chaque clôture, réajustés quand le CA bouge. C'est ça, ton Profit First automatisé chez Wio.

**Multi-devise** : Business tient AED/USD/EUR/GBP (IBAN par devise). Conversion Perso = **markup 1,5 % (cher)** → convertis tes € via **Wise (~0,4 %)**.

**Tracking Google Sheet** : **export CSV mensuel gratuit** calé sur ta clôture → import dans le Sheet (le meilleur rapport friction/valeur ; intégrations Wafeq/Fiskl si tu veux du temps réel, mais + une brique).

**Wio Invest (ETF)** : depuis le **10/06/2026**, Wio propose des **ETF UCITS irlandais iShares** (dès 10 $, USD, capitalisants) = fiscalement propre (15 % dividendes, **pas d'estate tax US**). ⚠️ **MAIS l'app vend AUSSI des actions US / ETF US-situs** (piège estate tax 40 % > 60 k$, jusqu'à ~176 k$ sur 500 k$) → **ne clique QUE l'UCITS** (domicile IE, tickers CSPX/VUAA/SWDA). Pour le patrimoine long terme, **IBKR reste meilleur** (FX ~0,002 % vs spread caché Wio, univers complet, titres ségrégués, **décorrélé**). Wio Invest = **rampe de démarrage UCITS acceptable** pendant le KYC IBKR (2-3 sem.), UCITS-only.

**La carte finale (où va chaque box)** :

| Poche | Compte | Rendement | Vrai verrou ? |
|---|---|---|---|
| Fond de roulement (frais, Maxence transit) | Wio Business Essential | 0 % | non (opérationnel) |
| **Coffre boîte** (10 % de ta moitié, cible 15-20 k€) | Wio Business, Space Flexible | 0 % (Essential) | non |
| Paie chatteurs (provision) | Wio Business, Space Flexible | — | non |
| **Ta vie** (salaire documenté, ~70 %) | **FAB perso** (courant + carte AECB) | 3 % courant | non (2 500 € charges) |
| **Savings locale visible** | **FAB, échelle DAT AED sans carte** | ~3 % | ✅ vrai verrou local |
| **Coussin survie 6-12 mois** | **IBKR, monétaire USD** | ~3,6-4 % | décorrélé (anti-gel) |
| **Extraction → patrimoine** (20 %→30 %) | **IBKR, ETF UCITS** | ~7 % LT | politique signée |

L'extraction transite par **FAB perso (ton nom)** puis sweep vers **IBKR** : d'abord le **coussin monétaire** (jusqu'à 15-30 k€), puis l'**ETF**. Le coussin de survie vit chez **IBKR** (décorrélé de FAB qui tient ton income) ; FAB ne garde qu'une **savings locale visible** (DAT AED) utile au dossier bankabilité.

## Le rail crypto — payer les chatteurs proprement

**Le trou actuel à boucher** : `Wio Business → Wio Perso → Binance` fait transiter une charge business par ton compte perso. Ça casse trois choses qui valent des 5-6 chiffres : la **déductibilité CT** du coût chatteurs (~6,5-13 k$/an d'enjeu à 9 % dès 2027), l'**absence de commingling**, ta **story résidence 0 %** — et c'est une **violation des CGU Binance** (compte perso pour de la paie = motif de gel).

**La cible** :
1. **Compte Binance au nom de LTP International FZ-LLC** (corporate KYC), financé **directement depuis Wio Business**.
2. **Paie en Binance Pay P2P — gratuit** (0 € vs 64-190 $/mois pour les alternatives) ; fallback USDC sur L2 (~0,50 $) pour qui veut son propre wallet.
3. **Achète l'USDT dans la devise que tu tiens déjà** (tes € de commission → USDT, spread ~0,1 %) — **pas de détour par l'AED**.
4. **Un contrat de sous-traitance + relevé de payout par chatteur** → charge déductible substantiable (et couvre l'art. 238A côté FR).
5. Garde-fous : ne laisse sur Binance que le **fond de roulement de paie**, rien qui dorme dessus ; un **2ᵉ on-ramp licencié VARA en secours** (BitOasis ou Rain).

## Le crypto — décision : 0 % (tranché le 20/07)

**Décision de Gaëtan (20/07) : aucune détention crypto dans le patrimoine — 0 %, pas « 5 % borné ».** Le raisonnement, gardé ici pour ne pas le reperdre dans 6 mois :
- **Le BTC n'est pas un diversifieur.** Il s'effondre **AVEC** les actions dans les paniques (mars 2020 : −50 % en même temps que le S&P ; 2022 : −65 %). Le vrai décorrélateur du portefeuille, c'est le **monétaire USD**, pas le BTC — c'est un pari asymétrique, pas une assurance.
- **C'est la ligne la plus dangereuse pour CE profil.** Rafales Binance à **6 058 €** documentées ([[Analyse finances perso (13 juillet 2026)|ta pire fuite]]) : le crypto est exactement le terrain où l'impulsivité se rallume. Mettre 0 % **supprime la tentation à la source**, au lieu de la « borner » et de miser sur la volonté les mois durs.
- **Les 5 % qui y allaient financent l'ETF.** Le total mis de côté ne bouge pas (~30 %) : le pari devient du moteur, et **100 % du patrimoine est décorrélé et propre** ([[Setup argent (le plan riche en 10 actions)|le plan à jour]]).
- **Ce qui resterait vrai si tu y revenais un jour** (à froid, jamais dans l'élan, et par défaut : **non**) : BTC seul, ≤ 5 %, **DCA 100 % automatique**, **cold storage** (Ledger/Trezor — « not your keys, not your coins », leçon FTX), et **jamais de stablecoins comme réserve** (UST → 0,04 $, USDC dépeg SVB) — la réserve stable reste le monétaire USD / DAT AED. Mais le défaut, désormais, c'est **0**.

⚠️ **À ne pas confondre avec le rail de paie** : le compte **Binance corporate** (section précédente) sert à **payer les chatteurs** en Binance Pay P2P — c'est un rail de règlement, pas une détention patrimoniale. Il reste, indépendamment de la décision 0 % crypto-patrimoine.

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
- **Salaire** : verse-toi un **salaire mensuel documenté** via **Wio Business Payroll** (fichier SIF) → atterrit sur FAB perso ; zéro coût fiscal en 2026 (0 % perso), preuve de revenu (visa, immo), charge déductible prête pour 2027. Conditions WPS, nuance owner et impact crédit immo : **section dédiée ci-dessous**.
- **Maxence** : sa société **te facture** ses services chaque mois (charge déductible arm's length, traitez-vous comme related parties par prudence) — jamais un « dividende ». Les créatrices co-signées qui paient déjà 50/50 les deux entités ne nécessitent pas de facture inter-sociétés.

## Le salaire depuis Wio Business — fiche de paie, WPS, conditions (recherche 20/07)

> [!tip] Verdict salaire
> **Oui, Wio Business fait la paie WPS.** Tu te verses un salaire documenté depuis **Wio Business Payroll** (fichier **SIF**), qui atterrit sur **FAB perso** avec une vraie trace de bulletin. **MAIS** — le point qui compte pour ton immo — **te payer un salaire ne fait PAS de toi un « salarié » aux yeux d'une banque : pour un crédit, tu restes un self-employed**, underwrité sur ton trade license (2 ans) + états financiers audités + un haircut de 20-40 % sur tes revenus. Le salaire sert la **preuve de revenu / le visa / la déductibilité**, pas le tapis roulant « salarié ».

- **La mécanique** : Wio Business a un **produit Payroll intégré** (banque CBUAE) — paiements **WPS-compliant**, salaires programmés, **jusqu'à 3 fichiers SIF gratuits/mois**. Le **SIF (Salary Information File)** est le format standard CBUAE/MoHRE : une ligne **SCR** (qui paie + total + mois) puis une ligne **EDR** par employé (toi). Résultat : `Wio Business (employeur) → SIF/WPS → FAB perso (employé)`, avec bulletin.
- **⚠️ Correction au vault** : l'ancienne note « RAKEZ hors WPS » était **fausse**. RAKEZ émet des permis routés **MoHRE** → il est **dans le périmètre WPS fédéral**. Depuis le **01/06/2026** (Résolution 340/2026), échéance unifiée = **le 1er du mois** (fini les 15 j de grâce) ; cash/chèque/virement non-WPS ne comptent pas comme paie conforme pour un titulaire de permis MoHRE.
- **La nuance owner** (`to-verify` avec l'agent RAKEZ) : selon ton **visa** — *employé* (permis MoHRE sous ta boîte → WPS s'applique à ton salaire) vs *investisseur/partner* (tu n'es pas « employé » → **owner's salary/drawing documenté** + salary certificate émis par ta société, hors WPS). Les deux marchent pour la preuve de revenu ; le WPS est du droit du travail, pas une condition d'octroi de crédit.
- **Le levier 0 %** : comme le revenu perso est à **0 %**, tu peux te verser un salaire **solide et rond** (défendable vs ton profit ~460 k AED), pas « modeste » — plus d'income sur le papier renforce le dossier, sans coût fiscal. Garde-le **« raisonnable » et adossé au profit** (risque de requalification, `to-verify` fiscaliste).
- **La réalité crédit immo (self-employed)** : 2+ ans de **trade license** (ta boîte : incorp. **09/10/2025** → oct 2027) + **états financiers audités** (même si le SBR ne t'impose pas d'audit CT, **la banque peut l'exiger** → prévoir de commander un audit pour le dossier) · **LTV 75 %** (vs 80 % salarié) · prime ~10-25 bps · délai 10-21 j · **haircut 20-40 %** sur le revenu · revenu min ~**AED 25 000/mois**. → La convergence **« bankable ≈ fin 2027 »** est confirmée **et durcie** (il faut aussi l'audit). Chiffrage réel via un courtier gratuit (Mortgage Finder / Holo / Huspy).

## La checklist AVANT le départ (~26/07)

- [ ] **Ouvrir le compte FAB perso** (impossible à distance — présence physique quasi exigée) : **compte courant + carte de crédit** (pour l'AECB) + iSave + échelle DAT sans carte. → c'est ton hub perso (Wio Perso retiré).
- [ ] **Activer Wio Business Payroll** (SIF/WPS) et poser ton **salaire mensuel documenté** vers FAB perso.
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

Si l'architecture est câblée avant le départ (FAB perso ouvert, Wio Business Payroll actif, Binance corporate, hop perso coupé) : au prochain closing, **0 flux business sur un compte perso** (hors salaire/drawing propres), la paie chatteurs sort du business, le salaire documenté atterrit sur FAB, et l'extraction perso démarre (≥ 800 €/mois transitant FAB → IBKR). Si le hop perso persiste, c'est le compte Binance corporate qui a bloqué (KYC adulte) — le point à débloquer en priorité.

## Sources & épistémique

[^1]: Synthèse de 3 agents de recherche du 20/07/2026 (banque physique + placements ; crypto/rails/conversion ; compta/CT/salaire), croisant le vault avec des sources officielles et marché 2025-2026 : CBUAE Rulebook Art. 122 + Federal Decree-Law 6/2025 (garantie des dépôts AED 100k) ; FTA/MoF (CT, Small Business Relief MD 73/2023, First Tax Period, audit MD 84/2025) ; VARA public register (Binance FZE, BitOasis, Rain licenciés) ; grilles de taux datées (FAB/ENBD/ADCB/Mashreq/Wio, 01/10/25→09/07/26) ; Binance Pay/Payouts fees ; Wise (mid-market, pas de transfert depuis l'AED). **Confirmé** : garantie AED 100k, Wio = banque CBUAE, SBR 0 % éligible, DAT physiques < Wio, dividendes non déductibles. **Probable** : ouverture FZ sans blocage chez FAB/ENBD/ADCB, coûts compta 5-10 k AED/an. **`to-verify`** (datés/volatils) : tous les taux exacts, l'audit sous SBR côté RAKEZ, la VAT inter-sociétés, la date de clôture d'exercice (à lire dans le MoA). Documents société (n° de registre, référence) **non commités** — hygiène PII.
