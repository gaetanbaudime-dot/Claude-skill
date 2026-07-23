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
> **Cette page = tes actions. Le reste du dossier 96 = la doc de référence** (tu l'ouvres seulement quand tu creuses un point). Ici : ce que tu fais, dans l'ordre, coché ou pas. Mis à jour le **2026-07-23**. Tu pars **dimanche 26/07 pour ~2 mois** → tout est rangé par urgence : rouge = avant l'avion, jaune = tourne sans toi, vert = au retour.

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

## 🟡 PENDANT L'ABSENCE — qui tient quoi (rien ne remonte à toi hors conflit de règle)

| Machine | Qui | L'action qui tourne | Garde-fou |
|---|---|---|---|
| **Tunnel clippers** | Manager clippers | recrute → valide tests → contrat → paie (les 6 Loom) | Zéro exception remonte à Paris sauf règle qui manque |
| **Paie** | Toi le mois 1, puis Manager | `!paiement`, **J+7 vérif → J+8 virement**, jamais un retard | Maxence = payeur de secours ([[Continuité du bot et paie sacrée (plan anti-panne)]]) |
| **Quiz → test** | Automatique (Apps Script réparé) | quiz réussi → test envoyé tout seul | `!pipeline` pour vérifier le flux |
| **Chatting + créatrices** | Maxence / Emma | séquences anti-churn + machine à contenu | [[SOP chatting anti-churn]] · [[SOP - Machine à contenu hebdomadaire]] |
| **Loyer** | Toi, à distance | prochain **15 000 AED ~22/09** viré depuis Wio | rappel calé au 10/08 |

## 🟢 AU RETOUR (septembre) — les priorités stratégiques, dans l'ordre

1. **Standard anti-crackdown clippers** : imposer le [[Brief montage clipper (standard anti-crackdown 2026)|brief montage]] (transformation matérielle) + faire activer **Content Protection par Chloé et Sophie** sur leurs fan pages. ([[État de l'art clipping Instagram (juillet 2026)|le pourquoi]])
2. **Concentration des ressources** : pods sur les top LTV **Chloé → Sophie → Maddie → Sarah** ; trancher Amanda (cut-ou-garde). ([[Équipe marketing - structure et rémunération (FR × MG)|règle d'allocation]])
3. **International** : reprise sur **Geelark + proxy FR** (pas de test « téléphone brut »). ([[Machine Instagram-Facebook en masse]])
4. **Crypto** : 2 rails allumés (OKX + Binance), **≤ 1 cycle de paie** sur chacun. ([[SOP paie chatteurs (Binance corporate)]])
5. **Fiches Emma** + **SFS août** (déléguer, pas exécuter).
6. **Fiscalité SAS France** : confirmer le **sursis** sur les pénalités IS 1 200 € en instruction. ([[Opération fiscalité propre (France → Dubaï)]])

## ✅ Déjà fait cette semaine (pour ne pas le rejouer)

- IBKR **approuvé** · OKX **soumis** (6/6, under review) · quiz→test **réparé et vérifié en prod** · grille INT retirée à l'attribution Team INT · assistant bot : mémoire de conversation + règle DM ajoutée · 6 Loom délégation + 6 scripts formation **écrits** · veille clipping 2026 **distillée** + 7 corrections de doctrine · scan marché logement (JGC 52-55k) · script candidatures **écrit** (à coller).

## Règle de tenue

Une décision prise → une ligne au [[Journal de coaching]] (avec prédiction datée), et **ce cockpit** se met à jour : on coche, on descend d'un cran (rouge→jaune→vert), on supprime ce qui est mort. Si une ligne n'a pas bougé en 2 semaines, elle est soit **faite**, soit **pas vraiment prioritaire** — on tranche, on ne la laisse pas pourrir.
