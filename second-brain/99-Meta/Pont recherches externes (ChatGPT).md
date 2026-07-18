---
titre: "Pont recherches externes (ChatGPT)"
type: méthode
cluster: "99-Meta"
statut: verified
créé: 2026-07-18
tags: [méthode/recherche, méthode/vault]
liens_forts: ["[[Méthode de travail Claude]]", "[[Fact-Check-Log]]", "[[Journal de coaching]]"]
---

# Pont recherches externes : ChatGPT (et autres) → le vault

> [!tip] Verdict
> Il n'existe **aucune synchronisation technique** entre ChatGPT Plus et Claude Code — pas d'API entre les deux interfaces, et en brancher une serait fragile et sans intérêt. Le pont efficace est **éditorial** : ChatGPT fait des deep research jetables, le vault garde la connaissance distillée. Protocole en 3 gestes : ① tu lances ta deep research dans ChatGPT → ② tu **colles le rapport dans le chat Claude** (ou tu déposes le fichier .md/.pdf) → ③ je le **distille en pages vault** avec croisement de sources, statut `to-verify` tant que non recoupé, et consignation au [[Fact-Check-Log]] si ça contredit l'existant. Le rapport brut ne rentre JAMAIS tel quel dans le vault (règle des raw exports).

## Qui fait quoi (la division du travail)

| Besoin | Outil | Pourquoi |
|---|---|---|
| Recherche intégrée au vault (contexte business complet, pages liées, prédictions) | **Mes agents** (Claude) | Ils connaissent LTP, écrivent directement les pages, croisent avec l'existant |
| Balayage massif de sources publiques, seconde opinion indépendante, sujets hors business | **ChatGPT deep research** | Interface différente, biais différents — une 2ᵉ opinion n'a de valeur que si elle vient d'un autre système |
| Vérification d'un chiffre contesté | Les deux, séparément | Si deux systèmes indépendants convergent, le chiffre passe `verified` |

## Les 3 règles de sécurité (non négociables)

1. **Jamais de données clients/créatrices dans ChatGPT** : mêmes règles d'alias que le vault — noms de scène, jamais de handles, téléphones, e-mails, chiffres bancaires. Une deep research se lance avec un contexte anonymisé (« agence de marketing de créatrices, ~50 k€/mois »).
2. **Un rapport externe = une source, pas une vérité** : tout arrive en `to-verify`, les chiffres clés se recoupent avant d'entrer dans une décision.
3. **Distiller puis jeter** : le rapport brut vit dans le chat ou le scratchpad, seule la synthèse aliasée entre au vault (`98-Rapports/` pour les synthèses datées, pages de bibliothèque pour le durable).

## Modèle de prompt pour tes deep research ChatGPT

« Agis comme un analyste. Contexte : agence de marketing d'influence francophone, ~50 k€/mois, équipe distribuée de monteurs vidéo payés à la performance. Recherche : [SUJET]. Je veux : chiffres sourcés et datés, top 3 actionnable, contre-arguments. Format : markdown, sources en liens. » — puis colle le résultat ici avec une ligne de contexte (« deep research du JJ/MM sur X »).
