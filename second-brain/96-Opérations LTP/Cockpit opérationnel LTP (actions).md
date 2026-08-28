---
titre: "Cockpit opérationnel LTP (actions)"
type: cockpit
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-23
tags: [ops/pilotage, ops/départ, contexte/business]
liens_forts: ["[[_MOC Opérations LTP]]", "[[Journal de coaching]]", "[[Les 6 Loom de délégation manager (passation été)]]", "[[Architecture bancaire Profit First (comptes, coffres, crypto, compta)]]", "[[Décision logement Dubaï]]"]
---

# Cockpit opérationnel LTP — la seule page à ouvrir pour AGIR

> [!tip] Verdict
> **Cette page = tes actions. Le reste du dossier 96 = la doc de référence** (tu l'ouvres seulement quand tu creuses un point). Ici : ce que tu fais, dans l'ordre, coché ou pas. Mis à jour le **2026-07-23**. Tu pars **dimanche 26/07 pour ~2 mois** (**mode owner ~4h/jour**, objectif : scaler) → rangé par urgence : rouge = avant l'avion, jaune = tes 4h/jour + ce qui est délégué, vert = au retour.

## 🔴 AVANT DIMANCHE 26/07 — non négociables (dans l'ordre)

| # | Action | Statut | Détail |
|---|---|---|---|
| 1 | **FAB** : finir l'ouverture, **carte livrée à l'adresse UAE avant de partir** | ⬜ le seul avec date-couperet dure — relance-les aujourd'hui | [[Architecture bancaire Profit First (comptes, coffres, crypto, compta)]] |
| 2 | **Numéro UAE reste actif** (bascule prépayé, PAS résiliation) + roaming SMS FR testé | ⬜ sinon plus d'OTP Wio/FAB/OKX depuis Paris = lockout | — |
| 3 | **IBKR** : virement **test depuis Wio Personal** (compte à ton nom, jamais Wio Business) | ⬜ compte approuvé ✅, reste à valider le rail | — |
| 4 | **Bot** : ajouter l'**ID Discord du Manager clippers à `ADMIN_IDS`** (Railway) | ⬜ sans ça il ne peut rien piloter | [[Les 6 Loom de délégation manager (passation été)]] |
| 5 | **Bot** : coller le script **`surCandidature`** sur la feuille candidatures + lancer `rejouerCandidatures()` | ⬜ ~10 candidatures perdues depuis le 21/07 à récupérer | `tools/bot_clippers/candidature_webhook.gs` |
| 6 | **Loyer** : envoyer **Message A à Najwa** (ancre 65-70k) + **visiter 1-2 studios JGC** | ⬜ le levier n'existe que si tu peux partir | [[Décision logement Dubaï]] |
| 7 | **Tourner les 6 Loom de délégation** (ordre : paie → pipeline → tests → contrat → blocages → Opus Clip) | ⬜ la passation qui protège la continuité | [[Les 6 Loom de délégation manager (passation été)]] |

**Peut se finir à distance (pas un point dur du départ)** : OKX (test 500 AED **dès approbation**, under review), reste du funding IBKR, versement Profit First automatique.

## 🟡 MODE OWNER 4H/JOUR (2 mois France) — tes 4h ne touchent QUE ce qui scale

**Objectif unique : scaler.** `CA = (clippers productifs) × (subs/clipper) × (€/sub)`. Tes 4h vont aux 3 facteurs ; l'opérationnel est délégué pour ne pas les bouffer. Le KPI roi : **subs générés / heure de TON temps** — s'il monte, tu scales.

**DANS tes 4h/jour (le levier — non délégable) :**

| Bloc | L'action | Le facteur qu'il élargit |
|---|---|---|
| ~1h · **Exceptions + règles** | lire l'issue log, décider promotions, trancher les conflits de règles | ton temps (#3) — tu restes joignable, pas opérateur |
| ~2h · **Ton moat** | monter en compétence trafic + acquisition créatrices, imposer le standard anti-crackdown | subs/clipper (#2a) |
| reste · **Owner-level** | décider le **clonage top 5 chatteurs** (+3-5k€/mois), **signer 1-2 créatrices haute LTV**, allocation | €/sub (#2b) + talent |

**DÉLÉGUÉ (sinon ça mange tes 4h) :**

| Machine | Qui | Ce qui tourne |
|---|---|---|
| **Tunnel clippers** | Manager (les 6 Loom) | recrute → valide → contrat → paie ; il te remonte SEULEMENT les conflits de règle |
| **Paie** | Toi mois 1, puis Manager | `!paiement`, **J+7 vérif → J+8 virement**, jamais un retard ([[Continuité du bot et paie sacrée (plan anti-panne)|Maxence = secours]]) |
| **Rétention J0-J30** | Manager + bot | 1ʳᵉ victoire < 7 j, buddy, feedback J+3/7/14 — **le seau qui fuit, priorité #1** |
| **Quiz → test** | Automatique (Apps Script) | quiz réussi → test envoyé tout seul (`!pipeline` pour vérifier) |
| **Chatting + créatrices** | Maxence / Emma | séquences anti-churn + machine à contenu ([[SOP chatting anti-churn]] · [[SOP - Machine à contenu hebdomadaire]]) |
| **Loyer** | Toi, à distance | prochain **15 000 AED ~22/09** viré depuis Wio (rappel au 10/08) |

> **La séquence de scale** : libère ton temps (#3, délègue) → bouche la fuite rétention (#1) → scale le trafic monétisé (#2 : reach crackdown-proof × hautes LTV × chatting cloné) → **PUIS** recrute plus. Recruter dans un seau percé = financer du churn.

## 🟢 AU RETOUR (septembre) — les priorités stratégiques, dans l'ordre

1. **Standard anti-crackdown clippers** : imposer le [[Brief montage clipper (standard anti-crackdown 2026)|brief montage]] (transformation matérielle) + faire activer **Content Protection par Chloé et Sophie** sur leurs fan pages. ([[État de l'art clipping Instagram (juillet 2026)|le pourquoi]])
2. **Concentration des ressources (corrigée 24/07)** : le pod marginal suit la **marge €/sub organique** → **Jade (60 % !) et Maddy d'abord**, puis Sophie ≈ Chloé ; **poser 1 lien organique dédié par créatrice** avant tout pod sur Sarah/Amanda (blended pollué par le trafic interne MYM ~3 €) ; trancher les 4 zéros (Alice, Capucine, Lily, Lila Doré : lancer ou couper). ([[Goulot de l'agence - l'équation du scale|la règle v2]])
3. **International** : reprise sur **Geelark + proxy FR** (pas de test « téléphone brut »). ([[Machine Instagram-Facebook en masse]])
4. **Crypto** : 2 rails allumés (OKX + Binance), **≤ 1 cycle de paie** sur chacun. ([[SOP paie chatteurs (Binance corporate)]])
5. **Fiches Emma** + **SFS août** (déléguer, pas exécuter).
6. **Fiscalité SAS France** : confirmer le **sursis** sur les pénalités IS 1 200 € en instruction. ([[Opération fiscalité propre (France → Dubaï)]])

## ✅ Déjà fait cette semaine (pour ne pas le rejouer)

- IBKR **approuvé** · OKX **soumis** (6/6, under review) · quiz→test **réparé et vérifié en prod** · grille INT retirée à l'attribution Team INT · assistant bot : mémoire de conversation + règle DM ajoutée · 6 Loom délégation + 6 scripts formation **écrits** · veille clipping 2026 **distillée** + 7 corrections de doctrine · scan marché logement (JGC 52-55k) · script candidatures **écrit** (à coller).

## Règle de tenue

Une décision prise → une ligne au [[Journal de coaching]] (avec prédiction datée), et **ce cockpit** se met à jour : on coche, on descend d'un cran (rouge→jaune→vert), on supprime ce qui est mort. Si une ligne n'a pas bougé en 2 semaines, elle est soit **faite**, soit **pas vraiment prioritaire** — on tranche, on ne la laisse pas pourrir.
