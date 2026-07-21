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
> **Le rail propre = un compte Binance CORPORATE (au nom de LTP FZ-LLC, via l'entité VARA Binance FZE), financé depuis Wio Business, qui paie les chatteurs en USDT via Binance Pay (transfert gratuit entre comptes Binance).** Jamais ton compte perso (= violation CGU + gel + casse la déductibilité CT). Sur Binance ne dort que le **fond de roulement de paie** (1 cycle max), rien d'autre. Coût du rail ≈ **0,1-0,5 % tout compris** (vs 2-7 % en virement bancaire classique), règlement en minutes.
> **⚠️ Le principe qui prime sur tout le reste (peur légitime de Gaëtan) : tu ne rendras JAMAIS ce compte imbannable — un gel arrive même sur un corporate propre (faux positifs AML, volumes de payout qui ressemblent à un MSB, décision opaque, appel = semaines). Donc on ne vise PAS « ne jamais se faire ban » : on rend le ban NON-FATAL.** Ton business ne repose pas sur Binance, il repose sur *payer les chatteurs à l'heure* → **2 rails allumés en permanence + ≤ 1 cycle de fonds dessus + un rail non-crypto de secours** (voir section Résilience). Le vrai risque à l'ouverture, c'est le **KYB** (nexus adulte) : **déclare honnêtement, jamais maquiller** (le maquillage = gel *après* onboarding, le pire moment).

> [!warning] Mise à jour 21/07 — 2 agents de recherche (CGU Binance FZE + BitOasis lues verbatim) : corrections qui priment sur le texte ci-dessous → [[Fact-Check-Log]]
> **① Binance Pay n'est PAS gratuit** (l'ancienne note « transfert gratuit » plus bas était fausse) : Send **0,5-1 $/envoi**, Payout batch **0,8 % plafonné à 5 $**. Le rail stablecoin reste bien moins cher qu'un virement bancaire (2-7 %), mais pas « 0 ».
> **② L'onboarding Binance Pay MERCHANT interdit explicitement l'adulte** (« adult industry and/or any sale of sexual services »). → On ne s'onboarde **PAS** comme *marchand*. On paie ses **propres contractants** depuis le **compte d'échange** (l'adulte n'y est pas nominalement interdit, mais EDD).
> **③ Clause « on behalf of third party » (CGU 27d)** : payer TES contractants = OK ; faire transiter l'argent DES créatrices = motif de gel. Bénéficiaires stables + contrat + facture par chatteur.
> **④ 2ᵉ rail = OKX UAE, PAS BitOasis** (remplace les mentions « Rain/BitOasis » plus bas). BitOasis liste **« adult live chat » en Prohibited Business** ET se réserve de bloquer les transferts vers des « unknown third-party beneficiaries » (double risque), conversion ~5-6× plus chère, pas de batch, USDC seulement ERC20/Base. **Rain = IPA seulement → interdit de servir Dubaï, inutilisable.** **OKX UAE** = full VASP VARA, AED via Zand Bank, frais spot ~0,08-0,10 %, large choix de réseaux USDC.
> **⑤ Aucune plateforme ne tolère un nexus adulte DÉCLARÉ** → framing d'entité **honnête mais neutre** (« social media marketing / gestion de contenu » = activité réellement licenciée), jamais un faux métier (la fausse déclaration = le seul ban inappelable). Dette CGU à documenter, pas à normaliser.
> **⑥ Question licence VARA « Transfer & Settlement »** de l'agence (transfert de VA pour compte de tiers) → à trancher avec un **avocat UAE avant de monter en volume** (point le plus sous-estimé).
> **⑦ USDC : réseau Base ~0,50 $ vs ERC20 ~2,79 $** — jamais Solana/Polygon/Tron (perte de fonds). Wallets chatteurs sur **Base** pour minimiser les frais.

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
| **Seul le fond de roulement de paie** dort sur Binance (≤ 1 cycle) | Un exchange n'est pas un coffre ; un gel ne piège alors que 2 semaines de paie, jamais ta tréso ; patrimoine ailleurs (IBKR), **0 % crypto détenu** ([[Setup argent (le plan riche en 10 actions)|décision 0 % crypto]]) |
| **2 rails VARA allumés en permanence** (Binance + Rain/BitOasis) + 1 rail non-crypto de secours | Un ban arrive un jour ; la redondance rend le gel indolore (bascule en 10 min) — voir Résilience |
| **Contrat de sous-traitance + facture/relevé par chatteur** | Statut *contractor* (pas salarié déguisé) + charge déductible substantiable |
| **Déclaration source honnête** + **fallback prêt** | Le nexus adulte peut déclencher EDD/refus — mentir = gel post-onboarding |
| **Chatteurs = contractors** dans leur juridiction | Certains pays restreignent le paiement crypto ; c'est leur cash-out qui doit être clean ([[Risques légaux et éthiques de l'OFM]]) |
| **La paie est sacrée** (les 1er/15) | Un cycle raté = confiance détruite → [[Continuité du bot et paie sacrée (plan anti-panne)|préparation déléguée + ta validation]] |

## La résilience — un ban Binance est INÉVITABLE un jour, rends-le NON-FATAL

> [!warning] La bonne peur, la mauvaise cible
> Se faire geler/bannir un exchange **arrive** — même avec un corporate propre (faux positifs AML, volumes de payout qui « ressemblent » à un money-service-business non licencié, décision opaque, appel de plusieurs semaines). **Tu ne rendras JAMAIS un compte tiers imbannable.** Donc on ne vise pas « ne jamais se faire ban » (impossible) — on vise « **un ban = une contrariété d'une journée, jamais une catastrophe** ». Ton business ne repose pas sur *Binance*, il repose sur *payer les chatteurs à l'heure* : **découple la fonction du fournisseur** ([[Systèmes et process|systèmes > héros]], [[Espérance mathématique et asymétries|survivre à la perte de n'importe quelle pièce]]).

**Les 5 moves qui rendent un ban indolore :**
1. **Deux rails ALLUMÉS en permanence — pas un + un « fallback » sur étagère.** Binance corporate **ET** Rain ou BitOasis (les deux **VARA**) déjà ouverts et testés (un vrai petit paiement/mois pour les garder vivants). Un gel = tu bascules le batch en **10 min**, tu ne t'arrêtes pas.
2. **≤ 1 cycle de paie sur le rail.** Jamais plus que la paie du cycle en cours ne dort sur Binance → un gel piège **au pire 2 semaines**, jamais ta tréso (Wio Business + IBKR).
3. **Portabilité par l'USDT/USDC.** Tu paies en stablecoin → si tu changes de rail, **les wallets des chatteurs ne bougent pas**, juste ton point d'envoi. Zéro friction côté équipe.
4. **Un rail NON-crypto de secours** (Wise Business / Payoneer, prêts) — pour survivre à un **de-risking crypto total**, le seul scénario que le crypto seul ne couvre pas. Plus cher, mais c'est l'extincteur du pire cas. (Ou un prestataire payout dédié type Transfi/0xProcessing, ~0,5-1 %, qui assume la conformité.)
5. **La tréso vit AILLEURS** (déjà acté) : Binance ne tient que le fond de roulement de paie. Un gel Binance ne touche **rien** d'autre.

**Réduire les déclencheurs (ce qui fait geler, concrètement) :**
- **Corporate + KYB honnête** (déjà acté) : un compte corporate déclaré *supporte* des flux business ; un perso, non. **Ne maquille jamais l'activité** — ouvre le rail chez qui l'accepte déclaré (le rail doit survivre à un audit, pas juste à l'onboarding).
- **Volumes réguliers et prévisibles** — pas de pic soudain, pas de rafale vers 30 nouveaux comptes le même jour (ça crie « MSB non licencié »). Lisse, garde les mêmes bénéficiaires.
- **Contrats + relevés par chatteur archivés**, montrables sous 24 h si due diligence.
- **Pas d'aller-retour fiat perso** sur le compte, pas de structuring · bénéficiaires **KYC'd de leur côté** (un chatteur au P2P douteux contamine la réputation de tes transferts).

> **Le renversement à retenir** : « tout mon business repose sur Binance » **EST** le problème — pas Binance. Deux rails en parallèle + 2 semaines de fonds max sur chacun = tu peux te faire bannir un lundi et payer tes chatteurs le mardi **sur l'autre rail, sans qu'ils le remarquent**. La sécurité n'est pas un compte parfait ; c'est un système qui survit à la perte de n'importe quelle pièce.

## Rattachement

Le « pourquoi » stratégique (firewall Wio Business, décorrélation, 0 % crypto) est dans [[Architecture bancaire Profit First (comptes, coffres, crypto, compta)|l'architecture bancaire]]. Le montant à provisionner sort de [[SOP clôture mensuelle avec Maxence|la clôture mensuelle]] (frais communs, avant le 50/50). La continuité (jamais un cycle raté) est dans [[Continuité du bot et paie sacrée (plan anti-panne)]].

## Sources

[^1]: Binance Support — *How to Complete Your Business Verification (KYB): A Step-by-Step Guide* (4 étapes : basic info / related parties / documents / source declaration) ; VARA Public Register — *Binance FZE* (entité licenciée EAU). Recherche web du 20/07/2026.
[^2]: Binance — *Fees for Binance Pay « Send Cash » (P2P Option)* (transfert entre comptes Binance sans frais) ; Binance *P2P Fee Rate* (0 % taker, 0,15-0,35 % maker, 2026) ; Transfi/0xProcessing 2026 — payouts stablecoins ~0,1-0,5 % tout compris vs 2-7 % rails classiques. **`to-verify`** (volatils) : frais exacts, acceptation du KYB corporate pour une agence à nexus adulte, statut VARA à jour de Rain/BitOasis.
