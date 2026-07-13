---
titre: "Suivi trésorerie quotidien"
type: sop
cluster: "95-Vie perso"
statut: verified
créé: 2026-07-13
tags: [perso/finances, ops/trésorerie, perso/routine]
liens_forts: ["[[LTP Models]]", "[[Analyse dashboard OFM (13 juillet 2026)]]", "[[Finances perso - 14 leçons de la vingtaine]]", "[[Allocation budget recrutement et IA]]"]
---

# Suivi trésorerie quotidien (le rituel Hormozi)

> [!tip] Verdict
> Hormozi le répète : **connais ton solde chaque matin.** Ce n'est pas de la compta, c'est de la conscience — le simple fait de regarder tes 3 comptes chaque jour change tes décisions (tu ne lances pas une vague de clippers un matin où le cash agence est à 1 200 €). Cette page est **ton endroit sur le téléphone** : chaque matin, tu ajoutes une ligne dans le tableau ci-dessous depuis Obsidian mobile (3 chiffres, 20 secondes). Quand tu me l'apportes en session, je te sors la lecture : burn, runway, et le feu vert/rouge pour la prochaine vague de recrutement.

## Comment ça marche (décision 2026-07-13 : Google Sheet, pas markdown)

**Les données vivent dans un Google Sheet** (« Suivi Trésorerie Quotidien — Gaëtan », créé par Claude dans ton Drive) — pas dans cette page. Raisons : un tableau de chiffres quotidiens en markdown mobile casse (ta crainte est fondée), le Sheet est fait pour ça (app mobile native, zéro risque pour le vault), et **Claude lit ton Drive en session** → il retrouve le Sheet et sort l'analyse à la demande. Cette page garde les **règles de lecture** ; le Sheet garde les **chiffres**.

1. **Chaque matin (20 s)** : ouvre l'app Google Sheets → **« 💰 TRÉSORERIE Gaëtan ✅ »** (dans ton Drive) → ligne du jour → 3 soldes bruts : **Revolut en €, Wio perso et Wio business en AED** (tu tapes les AED tels quels, la colonne EUR se calcule toute seule) + une note si gros mouvement. Épingle le Sheet en favori. Le rappel = une alarme téléphone à heure fixe.
   - **AED→EUR automatique** : le taux est en case **B1** (= combien d'AED pour 1 €, mets **4**, ou affine à **3,95**). Les colonnes « … (EUR) » et le **TOTAL (EUR)** se recalculent seuls. Un **convertisseur rapide** est en ligne 2 (tape des AED en B2 → EUR en D2).
   - ⚠️ J'ai créé plusieurs brouillons en calant les formules — **garde uniquement celui avec le ✅ dans le titre, supprime les autres** (« Suivi Trésorerie… », « (AED→EUR) », « VERSION FINALE »).
2. **Quand tu veux l'analyse** (1×/semaine ou avant une décision) : demande en session « lis mon suivi trésorerie » → Claude lit le Sheet via Drive et sort burn, runway, feu vert/rouge recrutement.
3. Les montants restent dans TON Drive — rien n'est commité dans le repo (meilleure hygiène que l'option markdown).
4. Apple Notes : écarté — Claude ne peut pas le lire, données piégées, aucune structure.

## Ce que je surveille pour toi (les règles de lecture)

- **Runway agence** = cash business ÷ burn mensuel (fixes clippers + VAs + outils). À 2 000 € de cash et 200 €/clipper de fixe, chaque vague de recrutement se juge au runway, pas à l'envie ([[Analyse dashboard OFM (13 juillet 2026)|le garde-fou trésorerie]]).
- **Burn hebdo** = combien tu brûles par semaine (sorties − entrées). S'il dépasse les encaissements récurrents, alerte.
- **Seuils de décision recrutement** (à calibrer avec tes vrais chiffres) :
  - Cash agence **> 1 mois de burn projeté** → feu vert vague de clippers suivante.
  - Cash agence **< 2-3 semaines de burn** → pause recrutement, on encaisse avant.
- **Le cycle mensuel des créatrices** : les fans FR paient début et fin de mois → tes encaissements suivent, planifie les grosses sorties (paies, vagues) juste après les pics d'encaissement ([[Analyse dashboard OFM (13 juillet 2026)|créneaux]]).
- **Séparer les 3 poches** : Revolut + Wio perso = ta vie (loyer 4 k/2 mois inclus) ; Wio business = le carburant de l'agence. Ne jamais financer le business avec la poche loyer sans le savoir ([[Finances perso - 14 leçons de la vingtaine|mesurer chaque matin]]).

## L'objectif et la règle (arbitré 2026-07-13)

**Cible : 50 k€ de trésorerie totale au 31/12/2026** (= ×5 le record historique de 10 042 € — voir [[Analyse finances perso (13 juillet 2026)]] ; 100k = north star mi-2027). La mécanique : **30 % de ta part de profit part au coffre intouchable le jour même du partage avec Maxence, avant toute dépense.** Le coffre = autre banque, pas de carte, de la friction. Et la règle anti-fuite n°1 : tout « investissement » doit nommer par écrit la contrainte qu'il lève + son payback, sinon c'est de la consommation déguisée → refusé.

## Contexte de départ (au 13/07)

Cash agence ~2 000 € · perso ~2 000 € (réservé loyer) · loyer ~4 000 €/2 mois · **gros encaissement attendu le 15/07** (assouplit la contrainte, permet la 1re vague de clippers). Recrutement clippers **par vagues financées par le cash** (décidé : « petit à petit »), jamais 50 d'un bloc ([[Journal de coaching]]).

## Ce que je ne peux pas faire (honnêteté)

Je **ne peux pas** t'envoyer une notification push chaque matin ni faire tourner un canal Telegram automatique depuis ici — je n'ai pas d'outil qui pousse vers ton téléphone en continu. Le rappel quotidien est de ton côté (une alarme téléphone à 8h, ou le plugin Daily Notes d'Obsidian). **Ma part** : rendre le log trivial (cette page) et faire l'analyse dès que tu m'apportes les chiffres. Si un jour tu veux un vrai bot Telegram qui compile ça automatiquement, c'est un petit outil à coder (API Telegram + un Google Sheet) — faisable, mais c'est un projet à part, pas quelque chose que je branche depuis cette conversation.
