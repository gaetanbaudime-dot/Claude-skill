---
titre: "Fiscalité des créatrices FR (seuils, sortie du micro, commission agence)"
type: plan
cluster: "96-Opérations LTP"
statut: to-verify
créé: 2026-07-16
tags: [ops/creatrices, perso/fiscalité, ofm/agence, contexte/décision]
liens_forts: ["[[Opération fiscalité propre (France → Dubaï)]]", "[[LTP Models]]", "[[Rétention et motivation des marketeurs]]", "[[SOP clôture mensuelle avec Maxence]]"]
---

# Fiscalité des créatrices FR : le piège du micro quand l'agence prend 50 %

> [!tip] Verdict
> Une créatrice française en **micro-entreprise** qui reverse **50 % à l'agence** est taxée sur **la totalité de son CA, y compris la part qu'elle nous reverse** — le micro applique un abattement forfaitaire, pas tes vraies charges, donc la commission agence n'est **pas déductible**. Résultat : elle paie impôts + cotisations sur notre argent. Dès qu'une créatrice a une grosse charge (nos 50 %), la solution est de **sortir du micro pour le régime réel** (ou une société), où la commission devient déductible. ⚠️ Mais les 50 % filent vers l'**entité Dubaï du fondateur** et la structure FR de Gaëtan n'est pas encore assainie ([[Opération fiscalité propre (France → Dubaï)]]) : **ça se construit par un comptable spécialisé, jamais au feeling.** Cette page est le **brief à apporter au comptable**, pas un conseil fiscal (`to-verify` sur chaque règle).

## Les deux seuils à ne pas confondre (vérifiés 2026)

| Seuil | Montant 2026 (services) | Au-dessus |
|---|---:|---|
| **Franchise en base de TVA** | **37 500 €** (majoré 41 250 €) | Doit **facturer la TVA** (compte MYM/OF PRO). Reste en micro. |
| **Plafond du régime micro** (BNC) | **83 600 €** | **Sort du micro** → régime réel / société. |

On peut être **micro ET assujetti à la TVA en même temps** (entre 37 500 € et 83 600 €). La réforme 2025 qui devait abaisser la franchise à 25 000 € a été **abandonnée** — les seuils 2026 sont inchangés[^1][^2]. Classification BNC vs BIC du contenu OF/MYM : `to-verify` (impacte l'abattement : 34 % BNC / 50 % BIC services).

## Pourquoi le micro devient un piège (le chiffrage)

Illustratif sur **60 k€ de CA/an** dont 30 k€ reversés à l'agence (à confirmer par un comptable) :

| | Micro-BNC | Régime réel |
|---|---|---|
| Base taxable | 60 k€ × 66 % (abattement 34 %) = **39,6 k€** | 60 k€ − 30 k€ commission − dépenses réelles ≈ **25-27 k€** |
| Cotisations | ~24 % de **60 k€** ≈ 14 k€ | sur le bénéfice réel (~25 k€) |
| Ce qu'elle garde vraiment | 30 k€ (après agence) | 30 k€ |
| **Taxée sur** | **60 k€ (dont l'argent de l'agence)** | **ce qu'elle garde** |

**Écart estimé : 8 000 à 12 000 €/an** en faveur du réel dès qu'il y a une charge de 50 % non déductible. La déductibilité de la commission agence, c'est tout le jeu.

## Les 3 mines (avant de conseiller quoi que ce soit)

1. **La commission agence doit être une vraie prestation facturée** (contrat + factures marketing/chatting) pour être déductible. Des virements informels « la créatrice reverse 50 % » ne sont pas déductibles et sentent le montage. → Chantier agence : l'invoicing créatrices doit être propre et contractualisé.
2. **Les 50 % partent vers l'entité Dubaï du fondateur, dont la structure FR n'est pas assainie** ([[Opération fiscalité propre (France → Dubaï)]]). Déduire des paiements vers l'offshore du fondateur = drapeau rouge classique (prix de transfert, acte anormal de gestion) ; un contrôle sur la créatrice **remonte le fil jusqu'à Gaëtan**. Les deux chantiers sont liés — assainir la structure de Gaëtan **avant** d'industrialiser la déduction côté créatrices.
3. **Bloquer les versements entrants MYM ≠ défère l'impôt** (à confirmer, mais fragile) et casse le cash : la créatrice ne peut plus payer sa commission à l'agence. À déconseiller — le comptable gère proprement.

## Ce n'est pas un cas isolé — c'est un risque roster (à jour 2026-07-16)

Le mail TVA de MYM est arrivé à **Maddy** (~30 k€/12 mois, accélération ~10 k€/mois → dépassera 83 600 € dans l'année). Mais **Chloé** a fait **60 411 € de MYM annuel + son OF** ([[LTP Models|hub]]) : elle est **très au-dessus** des seuils TVA et probablement du plafond micro, sans forcément le savoir. **Sarah** accélère fort. → **Risque fiscal sur tout le roster FR simultané**, avec le fil qui remonte vers la structure du fondateur. Maddy est juste la première alertée.

## Fausses pistes déjà écartées (ne pas re-creuser)

**Portage salarial (Jump, ~99 €/mois) — écarté le 16/07.** Trois verrous : (1) les frais professionnels y sont **plafonnés à ~30 % du salaire brut** et validés un par un → la commission agence de 50 % vers une entité Dubaï ne passera jamais ; (2) le portage vise les **prestations intellectuelles facturées à des entreprises clientes** (conseil, dev, formation) — une créatrice n'y rentre pas et le contenu adulte serait très probablement refusé par la société de portage (`to-verify` sur les CGU exactes de Jump, mais le plafond des frais suffit à écarter) ; (3) portage = salariat = **~45-50 % de cotisations** sur ce qui devient salaire, plus cher que le réel. Le « entre SAS et micro sans gérer une boîte » qui marche vraiment = **EI au régime réel** (charges réelles déductibles, pas de société à créer), SASU pour les plus grosses — arbitrage comptable.

## La marche à suivre (guider sans être le conseiller fiscal)

1. **Ne jamais donner de conseil fiscal engageant à une créatrice** (responsabilité + hors périmètre). Le rôle de l'agence : orienter, pas prescrire.
2. **Trouver un comptable spécialisé création de contenu / OFM** et le proposer aux créatrices FR (frais ~50-80 €/mois, vite rentabilisés). Idéalement le même que celui de la structure de Gaëtan → cohérence entre les deux côtés de la facture.
3. **Assainir l'invoicing agence → créatrices** (contrat de prestation, factures mensuelles propres) : condition pour que la déduction des 50 % tienne. C'est aussi le prérequis de la [[SOP clôture mensuelle avec Maxence|clôture mensuelle]].
4. **Rétention** : une créatrice qui gère mal ce virage se sent seule et churne ([[Rétention et motivation des marketeurs]]). Accompagner Maddy (top-4 du CA, 23 %) sur ce point est un **investissement de rétention**, pas de l'administratif.

## Concrètement pour la créatrice : deux étages, un seul vrai choix (à jour 2026-07-27)

Question posée par Gaëtan le 27/07 (« Elle doit passer dans un régime différent ? Qu'est-ce qu'elle doit faire concrètement ? ») — la réponse tient en deux étages qu'il ne faut pas confondre :

**Étage 1 — TVA : automatique, PAS un changement de régime.** Elle reste micro-entrepreneuse. Sous 37 500 € de CA annuel : rien. Entre 37 500 et 41 250 € : TVA à partir du 1er janvier suivant. Au-delà de 41 250 € : TVA immédiate dès le dépassement. En pratique : compte **MYM PRO**, numéro de TVA via son SIE (démarche faite par le comptable), déclarations TVA = comptable. Économiquement ≈ **neutre** : MYM (société française) récupère la TVA facturée, et la TVA sur ses achats pro devient déductible (`to-verify` le circuit exact MYM PRO).

**Étage 2 — micro → réel : le vrai choix, optionnel avant 83 600 €.** C'est là que se joue l'écart chiffré plus haut (~7-8 k€/an à son rythme, jusqu'à 8-12 k€/an à 60 k€ de CA). Concrètement ce n'est **pas créer une société** : elle reste entreprise individuelle, l'option pour la déclaration contrôlée (BNC réel) est **une lettre au SIE** que le comptable rédige en choisissant la date d'effet optimale (`to-verify` les fenêtres d'option), puis le comptable tient la compta et les cotisations passent sur le bénéfice réel. La seule action de la créatrice : poser au comptable LA question (« micro ou réel, vu que je reverse 50 % à mon agence ? »).

**Condition côté agence** : la facture de commission envoyée le 27/07 à Maddy (paiement attendu au 1er août) est exactement la pièce qui rend la déduction possible — libellé de prestation réel, numérotation, contrat derrière. Sans ça, l'étage 2 ne tient pas (mine n°1 ci-dessus).

## Le récap type à envoyer à une créatrice qui reçoit le mail seuil MYM (validé 27/07, envoyé à Maddy)

Message WhatsApp prêt à copier — remplacer [Prénom] :

> Hello [Prénom] ! J'ai regardé le mail MYM en détail, voilà le récap simple 👇
>
> 1️⃣ **Ce que dit le mail** : MYM prévient dès 30 000 € de CA, mais c'est leur alerte interne — le vrai seuil légal 2026 c'est **37 500 €** (avec une tolérance jusqu'à 41 250 €). Rien d'urgent, rien d'illégal, tu n'as rien fait de mal.
>
> 2️⃣ **Ce qui ne change PAS** : aucun impôt rétroactif, tu restes micro-entrepreneuse (le plafond micro est bien plus haut, ~83 600 €), et la facture avec l'agence ne change pas.
>
> 3️⃣ **Ce qui change au passage du seuil** : tu factureras la TVA sur MYM (quasi transparent pour toi avec le compte MYM PRO), et en bonus la TVA sur tes achats pro devient récupérable. L'administratif, c'est le boulot du comptable, pas le tien.
>
> 4️⃣ **Tes 3 actions** : ① passer ton compte en MYM PRO, ② prendre un comptable (50-80 €/mois, vite rentabilisé — je peux t'en présenter un), ③ garder toutes tes factures.
>
> 5️⃣ **LA question à poser au comptable** : « est-ce que je reste en micro ou est-ce que je passe au réel, sachant que je reverse 50 % de mon CA à mon agence ? » — en micro tu es taxée sur TOUT ton CA, y compris la moitié que tu reverses. C'est la question qui peut te faire économiser plusieurs milliers d'euros par an.
>
> Je suis là si tu veux qu'on en parle 5 min, et je te fais l'intro comptable quand tu veux 🙌

**Les 3 notes côté agence (à garder pour soi)** : (1) l'enjeu micro-vs-réel à son rythme (~60 k€/an) ≈ **7-8 k€/an** de cotisations+impôts payés sur de l'argent qu'elle ne garde pas — c'est un argument de rétention, pas de l'administratif ; (2) les seuils du message sont les **vrais seuils 2026 vérifiés** (le « 30 000 € » de MYM est leur alerte précoce, pas la loi) ; (3) nuance de timing à ne pas promettre à sa place : 37,5-41,25 k€ → TVA au 1er janvier suivant, > 41,25 k€ → TVA immédiate — le comptable date la bascule exacte.

## Sources

[^1]: Autoentrepreneur.urssaf.fr, « 2026 : modification des seuils de chiffre d'affaires ou de recettes », 2026 — plafonds micro et abandon de la réforme franchise TVA.
[^2]: LégiFiscal, « Nouveaux seuils micro-entreprises 2026 » ; Portail Auto-Entrepreneur, « TVA auto-entrepreneur 2026 » — seuil franchise TVA services 37 500 € / 41 250 €, plafond micro BNC 83 600 €.
