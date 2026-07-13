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

## Comment ça marche (zéro friction)

1. **Chaque matin**, ouvre cette page sur Obsidian mobile → ajoute une ligne : date, Revolut, Wio perso, Wio business. Le total se fait de tête ou je le recalcule.
2. Ça se synchronise via Git (ton repo) → je le lis dans n'importe quelle session.
3. **1×/semaine** (ou quand tu me pings), je te sors l'analyse : tendance, burn hebdo, runway agence, et la décision recrutement.

> [!warning] Choix sur la confidentialité des montants (à toi de trancher)
> Ce sont **tes propres comptes** (pas des tiers), donc le risque est le tien. Deux options : **(A)** tu logges les montants ici, ils partent dans le repo (simple, tout au même endroit) ; **(B)** si tu préfères qu'ils ne quittent jamais tes appareils, on met ce fichier en `.gitignore` et tu me colles les chiffres en session au lieu de les pousser. Par défaut = A. Dis-moi si tu veux B et je bascule.

## Le tableau (à remplir chaque matin)

| Date | Revolut | Wio perso | Wio business | Total cash | Note (entrée/sortie du jour) |
|---|---:|---:|---:|---:|---|
| 2026-07-13 | | | | | *cash agence ~2 000 € (contexte) ; gros encaissement prévu le 15* |
| | | | | | |
| | | | | | |

*(Ajoute une ligne par jour. Garde 30-60 jours visibles, archive le reste plus bas si ça devient long.)*

## Ce que je surveille pour toi (les règles de lecture)

- **Runway agence** = cash business ÷ burn mensuel (fixes clippers + VAs + outils). À 2 000 € de cash et 200 €/clipper de fixe, chaque vague de recrutement se juge au runway, pas à l'envie ([[Analyse dashboard OFM (13 juillet 2026)|le garde-fou trésorerie]]).
- **Burn hebdo** = combien tu brûles par semaine (sorties − entrées). S'il dépasse les encaissements récurrents, alerte.
- **Seuils de décision recrutement** (à calibrer avec tes vrais chiffres) :
  - Cash agence **> 1 mois de burn projeté** → feu vert vague de clippers suivante.
  - Cash agence **< 2-3 semaines de burn** → pause recrutement, on encaisse avant.
- **Le cycle mensuel des créatrices** : les fans FR paient début et fin de mois → tes encaissements suivent, planifie les grosses sorties (paies, vagues) juste après les pics d'encaissement ([[Analyse dashboard OFM (13 juillet 2026)|créneaux]]).
- **Séparer les 3 poches** : Revolut + Wio perso = ta vie (loyer 4 k/2 mois inclus) ; Wio business = le carburant de l'agence. Ne jamais financer le business avec la poche loyer sans le savoir ([[Finances perso - 14 leçons de la vingtaine|mesurer chaque matin]]).

## Contexte de départ (au 13/07)

Cash agence ~2 000 € · perso ~2 000 € (réservé loyer) · loyer ~4 000 €/2 mois · **gros encaissement attendu le 15/07** (assouplit la contrainte, permet la 1re vague de clippers). Recrutement clippers **par vagues financées par le cash** (décidé : « petit à petit »), jamais 50 d'un bloc ([[Journal de coaching]]).

## Ce que je ne peux pas faire (honnêteté)

Je **ne peux pas** t'envoyer une notification push chaque matin ni faire tourner un canal Telegram automatique depuis ici — je n'ai pas d'outil qui pousse vers ton téléphone en continu. Le rappel quotidien est de ton côté (une alarme téléphone à 8h, ou le plugin Daily Notes d'Obsidian). **Ma part** : rendre le log trivial (cette page) et faire l'analyse dès que tu m'apportes les chiffres. Si un jour tu veux un vrai bot Telegram qui compile ça automatiquement, c'est un petit outil à coder (API Telegram + un Google Sheet) — faisable, mais c'est un projet à part, pas quelque chose que je branche depuis cette conversation.
