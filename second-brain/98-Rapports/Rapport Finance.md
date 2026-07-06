# Rapport de synthèse : Finance

> [!tip] Usage
> Le cluster [[_MOC Finance|Finance]] en routines et modèles. Deux questions de survie (unité rentable ? cash suffisant ?), un levier (le prix), une vérification mensuelle.

## Modèle d'unit economics (à remplir par offre ET par canal)

```
Revenu unitaire                          ______
- Coûts directs (produit, livraison,
  paiement, support, remboursements)     ______
- CAC complet (pub + salaires + outils
  ÷ nouveaux clients)                    ______
= Contribution unitaire                  ______
LTV 12 mois (en MARGE BRUTE)             ______
LTV/CAC (cible ≥ 3)                      ______
Payback (cible ≤ 12 mois)                ______
```
Règle : si contribution < 0, on ne scale RIEN, on répare (prix, coûts, ou segment à couper).

## Plan de trésorerie 13 semaines (hebdo, 30 min)

1. Solde de départ → encaissements prévus (prudents : clients paient TOUJOURS plus tard) → décaissements engagés → solde de fin, semaine par semaine.
2. Alerte si une semaine passe sous 1 mois de charges fixes.
3. Runway < 6 mois = priorité absolue n°1, tout le reste attend.

## Procédure de hausse de prix

1. Calcule l'élasticité de survie : à +20% de prix, combien de clients peux-tu perdre sans perdre de marge ? (Souvent 30-40% : la peur est irrationnelle, voir [[Aversion à la perte]].)
2. Nouveaux clients d'abord : nouveau tarif immédiat, aucun risque sur l'existant.
3. Existants ensuite : préavis, date, justification par la valeur ajoutée depuis leur arrivée, option de verrouillage (prépaiement annuel à l'ancien tarif = cash immédiat, voir [[Trésorerie]]).
4. Jamais de remise nue : toute remise s'échange (volume, prépaiement, témoignage, engagement).

## Routine mensuelle de lecture (30 min, voir [[Lecture des états financiers]])

- [ ] Flux d'exploitation : positif ? pourquoi ?
- [ ] Compte de résultat en % du CA vs M-1 et N-1 : toute dérive ≥ 2 points = une question posée
- [ ] DSO (jours d'encaissement) : stable ?
- [ ] Si profit ↑ et cash ↓ : trouver où (créances ? stocks ? capex ?) avant de sortir de la réunion
- [ ] Chercher LA ligne la plus inquiétante de chaque document (anti-[[Biais de confirmation]])

## Les 3 erreurs qui tuent

1. **Compter la LTV en chiffre d'affaires** au lieu de marge brute (surestime tout de 2-3x).
2. **Confondre profit et cash** : la croissance rentable qui meurt d'un BFR positif est un classique.
3. **Sous-facturer par peur** : le levier prix rapporte plus que toute optimisation de coûts, et les clients perdus à la hausse sont les moins rentables.
