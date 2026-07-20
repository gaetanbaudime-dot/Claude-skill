---
titre: "SOP paie chatteurs (Binance corporate)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-20
tags: [ops/finances, ops/sop, ofm/agence, perso/fiscalité]
liens_forts: ["[[Architecture bancaire Profit First (comptes, coffres, crypto, compta)]]", "[[SOP clôture mensuelle avec Maxence]]", "[[Continuité du bot et paie sacrée (plan anti-panne)]]", "[[Opération fiscalité propre (France → Dubaï)]]", "[[Risques légaux et éthiques de l'OFM]]", "[[LTP Models]]", "[[Journal de coaching]]"]
---

# SOP paie chatteurs — le rail Binance corporate (Binance Pay)

> [!tip] Verdict
> **Le rail propre = un compte Binance CORPORATE (au nom de LTP FZ-LLC, via l'entité VARA Binance FZE), financé depuis Wio Business, qui paie les chatteurs en USDT via Binance Pay (transfert gratuit entre comptes Binance).** Jamais ton compte perso (= violation CGU + gel + casse la déductibilité CT). Sur Binance ne dort que le **fond de roulement de paie** (2 cycles max), rien d'autre. Coût du rail ≈ **0,1-0,5 % tout compris** (vs 2-7 % en virement bancaire classique), règlement en minutes. **Le vrai risque n'est pas technique, c'est le KYB** : une agence de contenu adulte peut déclencher une due diligence renforcée ou un refus → **déclare honnêtement + prépare un fallback** (Rain/BitOasis corporate, ou un prestataire de payout licencié). Ne jamais maquiller l'activité pour passer le KYC — c'est ça qui te fait geler *après* onboarding, le pire moment.

## Étape 0 — À faire à Dubaï AVANT le départ (présence quasi exigée)

Réunis les documents du KYB (Know-Your-Business). Tu en as besoin **physiquement/scannés** :
- **Ta pièce d'identité** (passeport, recto-verso) — toi = applicant + « actual controller » (UBO).
- **Certificate of Incorporation** de LTP International FZ-LLC (tu l'as, incorp. 09/10/2025).
- **Trade license / Operating License** RAKEZ en cours de validité.
- **Preuve d'adresse** : siège (registered address RAKEZ) + adresse d'exploitation.
- **N° de registre RAKEZ** (à saisir, **ne pas le commiter dans le vault**).
- **La déclaration Source of Funds / Wealth / Capital** préparée honnêtement (voir Étape 1.4).

## Étape 1 — Ouvrir le compte corporate (KYB, 4 étapes)

Sur Binance (entité **Binance FZE**, licenciée VARA), section **Entity / Corporate Account** → le KYB se fait en **4 étapes** :

1. **Basic info** : Entity Name (LTP International FZ-LLC), Registration Number, Date of Incorporation (09/10/2025), Registered + Operating Business Address.
2. **Related parties** : identifie le **contrôleur effectif (UBO)** = toi (et Maxence si co-détenteur au registre — à vérifier selon l'acte). Upload de la pièce d'identité de chaque partie.
3. **Documents** : Certificate of Incorporation + Operating License + ta pièce (recto-verso).
4. **Source Declaration** : Source of **Capital** (apport initial), Source of **Wealth** (revenus de l'agence), Source of **Funds** (commissions d'agence marketing/contenu). **Décris l'activité réelle, sans mentir** — un faux déclaratif = motif de gel post-onboarding.

⚠️ **Délai + risque** : compte **quelques jours à quelques semaines**, et la due diligence peut buter sur le **nexus adulte**. Si refus : ce n'est pas un échec du plan, c'est le **point à débloquer** (voir Fallback plus bas). Lance ce KYB **en premier**, c'est le maillon incertain.

## Étape 2 — Financer le compte (depuis Wio Business, jamais le perso)

- **Virement `Wio Business → Binance corporate`** en **AED ou USD** (IBAN corporate). C'est la charge d'exploitation « paie chatteurs » → **déductible CT** (couvre l'art. 238A côté FR).
- **Jamais** `Wio Business → compte perso → Binance` : le hop perso casse la déductibilité (~6,5-13 k$/an d'enjeu dès 2027), mêle les patrimoines, fragilise la résidence 0 %, viole les CGU. (Le trou historique — coupé.)

## Étape 3 — Convertir en USDT (au meilleur coût)

- Le plus simple : **Binance Convert** (€/AED/USD → USDT, spread ~0,1-0,2 %, pas d'ordre à gérer).
- Le moins cher à volume : **P2P marketplace** en **taker** (0 % de frais taker ; les makers paient 0,15-0,35 %) — mais plus manuel.
- **Achète depuis la devise que tu tiens déjà** (tes € de commission → USDT direct, pas de détour par l'AED).
- Ne convertis que le **fond de roulement du cycle** (voir garde-fous), pas un stock.

## Étape 4 — Payer les chatteurs (Binance Pay)

Chaque chatteur doit avoir **son propre compte Binance** (KYC fait de son côté). Ensuite :
1. **Binance Pay → Send** vers son **Pay ID / email / téléphone Binance**, en **USDT**.
2. **Transfert gratuit et instantané** entre comptes Binance (c'est le cœur du rail : 0 frais, pas de réseau blockchain à payer).
3. Le chatteur **cash-out de son côté** via P2P vers sa monnaie/banque locale (0 % taker) — **sa responsabilité**, pas la tienne.
4. **Garde un relevé de payout par chatteur** (montant, date, Pay ID) → pièce comptable pour la déductibilité, à archiver avec son contrat.

*(Fallback wallet propre : si un chatteur veut son propre wallet non-custodial, USDC sur un L2 — coût ~0,50 $ — plutôt qu'un retrait ERC-20 cher.)*

## Étape 5 — Les garde-fous (compliance, CGU, tréso)

| Garde-fou | Pourquoi |
|---|---|
| **Compte corporate uniquement**, jamais le perso | CGU Binance (perso pour de la paie = motif de gel) + déductibilité + commingling |
| **Seul le fond de roulement de paie** dort sur Binance (≤ 2 cycles) | Un exchange n'est pas un coffre ; le patrimoine est ailleurs (IBKR), **0 % crypto détenu** ([[Setup argent (le plan riche en 10 actions)|décision 0 % crypto]]) |
| **Contrat de sous-traitance + facture/relevé par chatteur** | Statut *contractor* (pas salarié déguisé) + charge déductible substantiable |
| **Déclaration source honnête** + **fallback prêt** | Le nexus adulte peut déclencher EDD/refus — mentir = gel post-onboarding |
| **Chatteurs = contractors** dans leur juridiction | Certains pays restreignent le paiement crypto ; c'est leur cash-out qui doit être clean ([[Risques légaux et éthiques de l'OFM]]) |
| **La paie est sacrée** (les 1er/15) | Un cycle raté = confiance détruite → [[Continuité du bot et paie sacrée (plan anti-panne)|préparation déléguée + ta validation]] |

## Le risque n°1 : le KYB adulte — et le fallback

Si Binance corporate **refuse ou gèle** sur le nexus adulte :
- **Rain** ou **BitOasis** (les deux **licenciés VARA**) en compte corporate = 2ᵉ on-ramp de secours.
- Ou un **prestataire de payout crypto** dédié (0xProcessing, Transfi…) qui gère la conformité — coût plus élevé (~0,5-1 %) mais assume le risque.
- **Ne réagis jamais en maquillant l'activité** : ouvre plutôt le rail chez qui l'accepte déclaré. La règle : le rail doit survivre à un audit, pas juste à l'onboarding.

## Rattachement

Le « pourquoi » stratégique (firewall Wio Business, décorrélation, 0 % crypto) est dans [[Architecture bancaire Profit First (comptes, coffres, crypto, compta)|l'architecture bancaire]]. Le montant à provisionner sort de [[SOP clôture mensuelle avec Maxence|la clôture mensuelle]] (frais communs, avant le 50/50). La continuité (jamais un cycle raté) est dans [[Continuité du bot et paie sacrée (plan anti-panne)]].

## Sources

[^1]: Binance Support — *How to Complete Your Business Verification (KYB): A Step-by-Step Guide* (4 étapes : basic info / related parties / documents / source declaration) ; VARA Public Register — *Binance FZE* (entité licenciée EAU). Recherche web du 20/07/2026.
[^2]: Binance — *Fees for Binance Pay « Send Cash » (P2P Option)* (transfert entre comptes Binance sans frais) ; Binance *P2P Fee Rate* (0 % taker, 0,15-0,35 % maker, 2026) ; Transfi/0xProcessing 2026 — payouts stablecoins ~0,1-0,5 % tout compris vs 2-7 % rails classiques. **`to-verify`** (volatils) : frais exacts, acceptation du KYB corporate pour une agence à nexus adulte, statut VARA à jour de Rain/BitOasis.
