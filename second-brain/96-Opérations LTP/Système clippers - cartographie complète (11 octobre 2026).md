---
titre: "Système clippers - cartographie complète (11 octobre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-11
tags: [ops/clippers, ops/bot, ops/recrutement, ops/paie, ops/tableau-de-bord]
liens_forts: ["[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)]]", "[[Team Leader clippers - le premier poste après Jonas (9 octobre 2026)]]", "[[App clippers - une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)]]", "[[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]", "[[Journal de coaching]]", "[[LTP Models]]"]
---

# Système clippers : cartographie complète (11 octobre 2026)

> [!tip] Verdict
> **Tout le pôle clipping tient sur un seul bot Discord (Railway, déployé depuis `main`) qui pilote le recrutement, les comptes Instagram, les codes, les liens GAML, la paie au clic et le tableau de bord.** Les humains ne gardent que quatre gestes : créer les groupes WhatsApp, créer les comptes dans le classeur, faire les virements du 5 et du 20, trancher les exceptions (ban, numéro, mineur).
>
> **Le goulot actuel n'est plus le recrutement mais le stock** : 3 lignes de comptes libres par nouveau dans le classeur des logins, et un forfait GAML de **50 liens (49 pris le 08/10)**. Sans lien, pas de compte 3, pas d'app, pas de paie ([[Théorie des contraintes|une seule contrainte à la fois]]).
>
> État au 11/10 : en production (`main` e79d25d) le funnel du 09/10, le tableau de bord en continu et les codes 2FA en liste blanche ; prêts sur la branche de travail mais pas encore déployés, la vague 1 (parcours sans attente, places, digest, équipes TL) et la vague 2 en vérification (relectures, colonnes, primes TL).

Cette page est la carte d'ensemble. Le détail technique vit dans le README du bot (`tools/bot_clippers/README.md`, sections datées en tête) ; l'historique de la refonte est dans l'[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)|audit du 05/10]] et les décisions dans le [[Journal de coaching]].

## 1. Le parcours d'un clipper, en 10 étapes

C'est la liste de Gaëtan du 10/10, telle que le bot l'exécute (vague 1 comprise).

| # | Étape | Ce qui se passe | Délai |
|---|---|---|---|
| 1 | **Telegram** | Gaëtan colle le texte de `!annonce <groupe>` (« 18 ans minimum », un lien par groupe pour suivre la source) | un clic |
| 2 | **Formulaire** | Le **site du bot** (`/candidature`), plus Google Forms : 7 champs dont l'âge, les 5 règles, mention RGPD | 2 min |
| 3 | **Formation** | Vidéo Loom, 5 mots-clés à noter | 15 min |
| 4 | **Quiz** | 10 questions, 8/10 pour passer, ordre mélangé ; la promesse « ta créatrice t'attend » dépend des places réelles | 3 min |
| 5 | **Discord** | Invitation directe, salon perso créé, prénom en pseudo | immédiat |
| 6 | **Créatrice** | Attribution automatique : rôle de la créatrice, salon rangé dans sa catégorie, lien de ses **vidéos d'origine** (plus de Drive perso) | < 1 min |
| 7 | **WhatsApp** | Bouton « écris à Gaëtan » ; il crée le groupe à la main ; « J'ai écrit » ne bloque rien | à la main |
| 8 | **Compte 1** | Identifiants **tout de suite** sous la bienvenue, code de création par « 📩 Mon code », un message de profil qui annonce 24 h de warm-up | ~10 min + 24 h |
| 9 | **Compte 2** | Au plus tôt 48 h après le compte 1 **et** 4 Reels vus dessus | ~H+57 à 2 Reels/jour |
| 10 | **Compte 3 privé** | 48 h + 4 Reels sur le compte 2 + 4 de plus sur le compte 1 ; lien GAML dans le profil, story à la une, **app clipper** | ~5 jours au total |

**Ce qu'on a retiré** (09-11/10) : le test de montage vidéo, le Drive perso aux variantes ré-encodées (la « qualité pourrie »), le raccourci « rejoins Discord sans quiz », l'attente de 3 h avant le compte 1, les boutons « Profil fait » des comptes 1 et 2, la routine « jusqu'à 10 Reels par jour » à J+7. **Ce qu'on garde exprès** : 24 h de warm-up, 48 h entre deux comptes (décision du 29/09 après 7 bans), 4 Reels par palier — le plancher de 4 jours jusqu'à l'app est voulu.

## 2. Les systèmes

| Brique | Rôle | Fréquence |
|---|---|---|
| **Bot Discord** (Python, Railway) | Tout le parcours, les salons, les commandes, l'assistant IA (Claude) qui répond dans le salon du clipper | permanent |
| **Site du bot** | Formulaire, formation, quiz, invitation Discord | à la demande |
| **Scan Apify** | Lit les profils Instagram (followers, Reels, état) | passage complet le matin + relectures légères |
| **Relevé GAML** | Clics par lien et par jour (pays payés, hors robots) | toutes les 15 min |
| **Metricool** | Relevés officiels des comptes branchés (Reels, vues) | quotidien |
| **Contrôle d'attribution** | 12 familles d'anomalies (compte sans clipper, lien d'un autre, ligne « Rianah Metricool »…) avec la commande à taper | à chaque passage |
| **Lecteur des codes** | Une seule connexion à la boîte mail des alias, codes classés en liste blanche | IDLE ou 20 s |
| **App clipper** | Une page par clipper : visites, gains, adresse de paie | lue par le clipper |
| **Paie au clic** | Liste du 5 et du 20, feuille « Paie du … » | 2 fois par mois |

## 3. Les connecteurs et intégrations

Côté bot (variables sur Railway, **jamais de clé dans le vault ni le repo**) : GAML (liens, notes, statistiques), Apify (profils Instagram, budget plafonné), Metricool (API REST), Google Sheets et Drive (compte de service), boîte Gmail des codes en IMAP (mot de passe d'application), Telegram (alertes à Gaëtan), Claude (assistant et relecture des Reels), Discord.

Côté sessions Claude : GAML, Metricool, OpusClip, Google Drive, GitHub, Canva, Vercel, Fathom, Wispr Flow ; Gmail demande une autorisation dans les réglages des connecteurs claude.ai.

## 4. Les liens GAML

- **Un lien par clipper et par créatrice**, créé à l'ouverture du compte 3 (cloné depuis un lien « Clipping » de la créatrice), porté par le compte privé dans le champ Liens — jamais de lien sur les comptes 1 et 2 ([[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)|règles du 02/10]]).
- **La note GAML fait foi** : « Clipping Prénom » = lien du clipper ; « Rianah Metricool N (ex-Prénom) » = lien d'un sortant dont les comptes passent sur Metricool chez Rianah (trackings OF et MYM gardés) ; « Clipping libre (ex-Prénom) » = lien redonnable au suivant de la créatrice.
- **Décisions sur les identifiants, jamais sur un prénom** (deux Julien, deux Andry) : `!monteur` et `!sortie` passent les liens chez Rianah, `!lien` attribue à la main.
- **Goulot** : forfait de 50 liens actifs. Le prix au-delà est la question n°1 à poser à GAML.

## 5. Les sheets

Les identifiants des classeurs vivent sur Railway, pas ici.

| Classeur | Onglets | Qui écrit |
|---|---|---|
| **Classeur des logins** | Un onglet par créatrice (Chloé, Sarah, Sophie, Jade…) : @, e-mail, mot de passe, Gérant, Utilisation, État, followers, Reels hier et 7 j ; onglet **Dashboard** | Gaëtan crée les lignes ; le bot réserve, renomme, met à jour les états |
| **Classeur des candidatures** | « Candidatures bot » (source tg-groupe), « Quiz bot » | le bot |
| **App clippers · usage** | « Adresses USDC » (collées par les clippers dans l'app), « Paie du JJ/MM/AAAA » (prénom, créatrice, adresse, visites, montant) | le bot ; Gaëtan vire |

Rappel locale : toute formule livrée à Gaëtan est en français (`;`, `SOMME`, `SI`…), ou mieux une référence directe sans fonction.

## 6. Le tableau de bord

L'onglet **Dashboard** du classeur des logins, réécrit seulement s'il a changé : une ligne par compte avec clipper, créatrice, état, followers et tendance, clics, Reels hier et 7 jours, dernière lecture ; en tête la fraîcheur des sources et le budget Apify (« X $ / 25 $ », coupure à 100 %). Les clics se rafraîchissent toutes les 15 min (gratuit) ; followers et Reels coûtent de l'Apify. **Plafond : 25 $ par mois** (décision du 09/10), soit environ 3 à 4 lectures par jour de chaque compte public ; une lecture par heure coûterait ~63 $. La vague 2 ajoute les relectures de 12, 14, 16, 18, 20 et 22 h, avec priorité aux clippers qui attendent leur compte suivant, et les colonnes manquantes.

## 7. Les codes 2FA (en production depuis le 10/10)

**Liste blanche stricte** : seuls les codes de **connexion** et de **création** d'un compte partent au clipper, s'ils viennent d'une adresse Instagram (6 langues reconnues). Tout le reste (mot de passe oublié, e-mail, numéro, 2FA, Espace Comptes) est **gardé** : une ligne au salon admin sans le code. Un changement fait sur un compte déclenche une alerte. Le clipper appuie sur « 📩 Mon code » dans #🔐-code-instagram et **lui seul** voit la réponse. Code d'appel après un ban : gardé par défaut (`CODES_APPEL=1` pour l'ouvrir). Limite honnête : le filtre n'empêche pas un clipper de changer le mot de passe dans l'app ou par SMS — on détecte et on reprend par la boîte de l'agence.

## 8. Paie et équipes

- **Clipper** : 0,05 $ par visite payée (francophone, hors robots), périodes 5 → 19 payée le 20 et 20 → 4 payée le 5, au clic depuis le 05/10.
- **TL** (grille de Gaëtan du 10/10) : sa paie de clipper + **10 $ par VA de son équipe à 500 visites payées ou plus** sur la période, TL exclu du compte. Rôle « Team Leader » sans aucune permission, nommé par `!tl Chloé @X`.
- **Manager** : **75 $ par TL dont l'équipe fait 3 000 ou plus**. Avocat du diable : à 3 000 pile, la visite coûte 0,095 $ contre 0,06 à 0,07 $ de marge OnlyFans seule (à vérifier) ; recommandation : aucun manager avant deux équipes à 3 000 deux quinzaines de suite ([[Team Leader clippers - le premier poste après Jonas (9 octobre 2026)|analyse du 09/10]]). Première période primée : 20/10 → 04/11, payée le 05/11 ; contrôle de 5 abonnés par VA primé avant virement.

## 9. Les commandes à connaître

`!annonce <groupe>` (annonce + places), `!tl liste`, `!tl Chloé @X`, `!manager @X Chloé Sarah`, `!monteur @X` (sortie vers un autre rôle, liens chez Rianah), `!sortie @X raison`, `!lien @X <url>`, `!fiche @X`, `!etape @X n`, `!paie-clics 5|20`, `!dashboard`, `!verifier`. Les sorties et ouvertures sans commande passent par les fichiers de dépôt (`sorties_a_appliquer.json`, `salons_a_ouvrir.json`) appliqués au démarrage.

## 10. Ce qui reste à faire

**Claude** : déployer la vague 1 (branchée, 122 tests verts), finir la vague 2 (relectures, colonnes, primes TL sur la paie, ménage), mettre à jour le README. **Gaëtan** : retirer le rôle Manager à Jonas ; fermer les 3 anciens Google Forms ; annoncer avec `!annonce` ; demander le prix GAML au-delà de 50 liens ; préciser si les 25 $ Apify incluent l'abonnement ; ouvrir une Gmail dédiée aux codes ; retirer les variables Railway mortes après une journée sans incident ; confirmer la grille TL (TL exclu, première période, contrôle des abonnés).

## Ce qui ferait échouer ça

- **Le stock** : sans lignes créées ni liens GAML, ouvrir les vannes ne crée que de l'attente — `!annonce` dit « 0 place » pour cette raison.
- **Gaëtan goulot WhatsApp** : un groupe à créer par recrue ; à 10 recrues par jour, c'est la première mission à confier à un TL.
- **Dette CGU, à ne jamais normaliser** : comptes de l'agence aux identifiants distribués, comptes repris d'un sortant, trois comptes par personne sur le contenu d'une créatrice, relais des codes, collecte Apify ([[Risques légaux et éthiques de l'OFM]]). Mineurs : contrôle de la relecture des Reels maintenu, doute = sortie.
- **Juridique** : TL et managers payés sur des résultats d'équipe augmentent le risque de salariat déguisé en France ([[Conformité recrutement (droit FR, RGPD, CGU)]]) — avis d'expert-comptable avant le premier manager.
- **Panne du bot** : tout repose sur lui ; le [[Continuité du bot et paie sacrée (plan anti-panne)|plan anti-panne]] reste la référence, et la paie se refait à la main depuis la feuille si besoin.
