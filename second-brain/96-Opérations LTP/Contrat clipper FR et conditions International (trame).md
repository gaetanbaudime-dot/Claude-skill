---
titre: "Contrat clipper FR et conditions International (trame)"
type: sop
cluster: "96-Opérations LTP"
statut: to-verify
créé: 2026-07-18
tags: [ops/recrutement, ops/contrat, ops/conformité]
liens_forts: ["[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Machine de recrutement clippers (100 leads par mois)]]", "[[Conformité recrutement (droit FR, RGPD, CGU)]]"]
---

# Contrat clipper FR + conditions International (trame du 18/07)

> [!tip] Verdict
> Une trame **prête à coller dans un modèle Yousign ou DocuSign** avec des **champs remplis par le signataire** (nom, date de naissance, adresse, e-mail) — tu n'envoies que vers son e-mail, tu ne demandes plus rien en privé. Circuit acté le 18/07 : **FR = contrat avant le rôle** ; **International = pas de contrat, mais une acceptation de conditions enregistrée** (texte court en fin de page, envoyé par le bot à l'onboarding). ⚠️ `statut: to-verify` assumé : cette trame est une **base de travail rédigée par IA, à faire relire par un juriste avant le premier envoi** — surtout l'article 2 (indépendance) et le choix de l'entité signataire.

## Le choix de l'outil — étude comparative du 18/07 (2 agents, ~16 services, pages tarifs officielles)

> [!tip] Verdict croisé
> **DocuSeal Cloud Pro** (20 $/mois + 0,20 $/contrat signé, **sans engagement**) en **architecture API intégrée au bot Discord** : coût 6 mois ≈ **140 $ ≈ 130 €** pour ~90 contrats à **zéro minute humaine par contrat**. Le facteur décisif : son API (vérifiée en profondeur) livre le **lien de signature directement dans le MP Discord** (`send_email: false`) et pré-remplit prénom/e-mail depuis la base du bot, interface signataire en français (auto-détection, 14 langues), contresignature automatisable, webhooks « signé » → notification + archivage Drive, et une **porte de sortie open source** (auto-hébergeable sur le Railway existant, ~5 $/mois, si l'éditeur déçoit). Hypothèses du dimensionnement : ~100 clippers visés, ~20 % de churn mensuel, 10-15 signatures/mois sur 6 mois.

**Le podium coût total 6 mois / 90 contrats** (palier minimal à fonctions complètes : modèle + champs signataire + ordre de signature + rappels) : ① **eSignatures.com ~44 $** (0,49 $/contrat à l'usage, zéro abonnement, liens publics + API, français confirmé — l'alternative plancher si le paiement à l'usage séduit, mais éditeur peu connu et intégration non vérifiée en profondeur) · ② **DocuSeal 30-140 $** selon le mode (auto-hébergé ~30 $ / cloud Pro ~140 $ avec API) · ③ **SignWell Light 72 $** (liens de modèle dès 12 $/mois, mais français signataire non garanti — à tester avant tout achat). Les mastodontes coûtent 3-12× plus pour ce besoin : DocuSign 360-540 $ (et PowerForms exige Business Pro), Yousign/Youtrust Plus 180 € (API à part, 1 248 €/an !), Adobe ~180-240 $, PandaDoc 210 $+.

**Les pièges relevés (à retenir pour toute renégociation)** : SignNow affiche « illimité » mais cache **100 invitations/an** en FAQ (1,50 $ l'excédent) ; DocuSign « illimité » = **100 enveloppes/an** ; Yousign One (9 €) est capé à 10 demandes/mois ; les prix vitrines supposent presque tous un **engagement annuel** (+25 à +150 % en mensuel réel) ; Skribble facture **par signature** (la contresignature double le coût) et n'a pas de modèles avant le palier sur devis ; marché instable (Yousign→Youtrust été 2026, Universign absorbé par Signaturit). Entité hors UE : vérifier la TVA avec le comptable.

**L'architecture retenue (C)** : test validé → le bot appelle l'API DocuSeal (modèle + valeurs pré-remplies, pas d'e-mail) → **lien de signature dans le MP du candidat** → il remplit nom/date de naissance/adresse et signe en français → contresignature (automatisable, ou en lot hebdo de 15 min — plus solide juridiquement) → webhook « signé » → notification #bot-gaetan + PDF archivé sur Drive → `!equipe Prénom`. Filet si le bot tombe pendant l'absence : le **lien de partage public du modèle** épinglé dans un salon privé (libre-service dégradé, gratuit). Chemin : compte gratuit + modèle J1 → intégration + tests J2-J3 → bascule Pro et 1er contrat réel J4-J5 — jouable avant le 26/07.

**Ce qui ferait échouer la reco** : la contresignature 100 % automatisée est le point juridique le plus mou (parade : lot hebdo manuel) ; « 0,20 $/complétion » à clarifier (par contrat ou par signataire — au pire ~40 $ au lieu de 20 $ sur 6 mois) ; DocuSeal est un petit éditeur (parades : archivage Drive au fil de l'eau + migration auto-hébergée possible en un jour) ; et le vrai point de défaillance unique reste **le bot lui-même** — son monitoring vaut plus que le choix du service de signature.

## La décision encore ouverte AVANT le premier envoi

**Qui signe côté agence ?** La SAS est en liquidation, la micro est radiée — il ne reste vraisemblablement que la **LLC Dubaï**, dont les capacités de contracter (et la fiscalité des paiements sortants) font partie des 5 questions LLC/Cosmo encore sans réponse. À trancher en premier : un contrat signé par une entité bancale vaut moins que pas de contrat.

## La trame (à coller dans le modèle — les [CHAMPS] deviennent des champs signataire)

```
CONTRAT DE PRESTATION DE SERVICES
Création, montage et publication de contenus (« clipping »)

ENTRE
[ENTITÉ AGENCE — raison sociale, forme, siège, immatriculation],
représentée par [représentant], ci-après « l'Agence »,

ET
[CHAMP SIGNATAIRE : Nom et prénom complets],
né(e) le [CHAMP : date de naissance],
demeurant [CHAMP : adresse complète],
e-mail [CHAMP], téléphone [CHAMP],
ci-après « le Prestataire ».

Article 1 — Objet
L'Agence confie au Prestataire, qui l'accepte, des prestations indépendantes de
montage vidéo et de publication de contenus sur des comptes de réseaux sociaux
fournis et détenus par l'Agence, selon la méthode et les contenus fournis par
l'Agence.

Article 2 — Indépendance
Le Prestataire exerce en toute indépendance, sans lien de subordination :
il organise librement son temps et ses moyens, utilise son propre matériel et
demeure libre de toute autre activité. Il fait son affaire de ses obligations
fiscales et sociales dans son pays de résidence.

Article 3 — Majorité et identité
Le Prestataire certifie être âgé de 18 ans révolus à la date de signature.
Une pièce d'identité est vérifiée par l'Agence avant contresignature ; toute
fausse déclaration entraîne la nullité immédiate du contrat.

Article 4 — Propriété des comptes et des livrables
Tous les comptes, pages et profils créés ou exploités dans le cadre de la
mission, ainsi que les identifiants associés, sont la propriété exclusive de
l'Agence. Le Prestataire remet les accès à première demande et restitue
l'intégralité des accès et contenus à la fin du contrat. Les contenus montés
dans le cadre de la mission sont cédés à l'Agence au fur et à mesure de leur
création.

Article 5 — Rémunération
Le Prestataire perçoit : (a) une commission de 0,50 € par abonnement vérifié
apporté via son lien de suivi personnel, sans plafond ; (b) un fixe de
démarrage conditionnel selon la grille en vigueur (Annexe 1). Versements
chaque lundi le premier mois, puis mensuels. Le fixe est conditionné au
respect des conditions de l'Annexe 1 (volume de publication, intégrité des
comptes, reporting hebdomadaire) ; les commissions restent dues même lorsque
le fixe ne l'est pas.

Article 6 — Conformité des contenus
Le Prestataire publie exclusivement les contenus fournis ou validés par
l'Agence, conformes aux conditions d'utilisation des plateformes, sans nudité
ni sollicitation. Achat d'abonnés, robots et automatisations interdits — seuls
les abonnements réels et vérifiés sont rémunérés. Le Prestataire est informé
que les clientes finales de l'Agence exercent sur des plateformes réservées
aux adultes ; son propre travail demeure exclusivement tout public.

Article 7 — Confidentialité
Méthodes, contenus de formation, identités des créatrices, rémunérations et
données de l'Agence sont strictement confidentiels, pendant le contrat et
24 mois après. Toute copie, divulgation ou réutilisation du kit de formation
est interdite.

Article 8 — Données personnelles
L'Agence traite les données du Prestataire pour la seule gestion du contrat
et des paiements, conformément à la réglementation applicable. Le Prestataire
dispose d'un droit d'accès, de rectification et de suppression.

Article 9 — Durée et résiliation
Contrat à durée indéterminée. Chaque partie peut y mettre fin avec un préavis
de 7 jours. En cas de manquement grave (fraude au suivi, fuite de contenus ou
d'informations, publication non conforme), résiliation immédiate ; les
commissions sur abonnements vérifiés restent dues, le fixe non encore versé
ne l'est pas.

Article 10 — Divers
Contrat régi par le droit [de l'entité signataire — à adapter]. Les parties
recherchent une solution amiable avant toute action. Si une clause est nulle,
les autres demeurent.

Fait en deux exemplaires électroniques.
[CHAMP : Signature du Prestataire + date]        [Signature de l'Agence]

ANNEXE 1 — Grille de rémunération et conditions du fixe (version 18/07/2026)
Grille FR : fixe de démarrage 200 €/mois (versé 50 €/semaine le 1er mois)
+ 0,50 €/abonnement vérifié. Conditions cumulatives du fixe hebdomadaire :
(1) volume de publication ≥ 90 % du volume convenu, vérifié sur les
statistiques natives des comptes ; (2) comptes confiés maintenus sains et
accessibles ; (3) à partir de la 3ᵉ semaine, au moins 5 abonnements vérifiés
par période de 14 jours ; (4) reporting hebdomadaire remis chaque dimanche.
Un manquement = fixe de la semaine suspendu ; deux manquements = gel du fixe
et récupération des accès. Les commissions ne sont jamais suspendues.
```

Champs signataire à configurer dans l'outil : nom complet · date de naissance · adresse · e-mail · téléphone · signature + date. Ordre de signature : 1. le Prestataire (remplit et signe) → 2. Gaëtan (vérifie la pièce d'identité sur WhatsApp, contresigne) → signature reçue = `!equipe Prénom` (la grille se déduit seule).

## Conditions Team International (pas de contrat — acceptation enregistrée)

Texte court que le bot envoie dans le MP d'onboarding International ; le candidat répond **J'ACCEPTE** et la réponse reste dans l'historique MP (horodatée) :

```
Avant de commencer, confirme que tu acceptes les règles de l'équipe :
1. Les comptes créés pour la mission appartiennent à l'agence — tu remets
   les accès à la demande.
2. La formation, les méthodes et les contenus sont confidentiels : rien ne
   se partage, rien ne se copie.
3. Tu as 18 ans ou plus.
4. Paie : 0,50 € par abonné vérifié via TON lien + fixe selon la grille,
   conditionné au travail réel (volume, comptes sains, reporting du
   dimanche). Toute fraude au suivi = exclusion immédiate.
Réponds « J'ACCEPTE » pour ouvrir ton accès au Drive.
```

Cette acceptation ne vaut pas un contrat — c'est la dette assumée du 18/07 ([[Machine de recrutement clippers (100 leads par mois)|décision]]) : le risque International est borné par le [[Équipe marketing - structure et rémunération (FR × MG)|verrou du fixe]] à ~100 €/personne. Si un incident de fuite ou de détournement de comptes survient côté International, on repasse au contrat pour tous.

## Ce qui ferait échouer ça

- **La requalification en salariat (FR)** : des consignes horaires strictes ou une cadence imposée jour par jour ressembleraient à de la subordination — les objectifs de volume doivent rester des **conditions de prime** (annexe), jamais des ordres d'emploi du temps. Détail dans [[Conformité recrutement (droit FR, RGPD, CGU)]].
- **L'entité signataire non tranchée** : tant que les questions LLC/Cosmo sont ouvertes, chaque contrat signé est fragile — trancher avant la première vague de signatures.
- **L'outil sous-dimensionné** : DocuSign Personal (≈ 5 envois/mois) bloquerait la 2ᵉ semaine de recrutement.
