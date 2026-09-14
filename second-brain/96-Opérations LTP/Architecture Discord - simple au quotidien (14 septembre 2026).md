---
titre: "Architecture Discord - simple au quotidien (14 septembre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-14
màj: 2026-09-14
tags: [ops/discord, ops/clippers, ops/recrutement, ops/délégation, méthode/simplification]
liens_forts: ["[[Bot FAQ clippers (Discord)]]", "[[Fiche de poste - Manager marketing (Jonas)]]", "[[Analyse complète de l'agence et plan de simplification (14 septembre 2026)]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Journal de coaching]]", "[[Théorie des contraintes]]", "[[Kill-list (NON, pas maintenant)]]"]
---

# Architecture Discord : simple au quotidien (14 septembre 2026, v2 en profondeur)

> [!tip] Verdict
> **Le serveur était compliqué parce qu'il servait deux populations qui n'ont rien à faire ensemble : des candidats (des inconnus, par centaines) et une équipe (une quinzaine de signés).** Tout ce qui pèse aujourd'hui — trois étages d'accès, rôles de grille, filet anti-spam, accueil numéroté, parrainage, Disboard, quiz et test en messages privés, trois séries de relances — n'existe que pour la première. **La décision du 14 septembre au soir (« plus personne n'arrive sur le Discord ») supprime cette population**, et avec elle la moitié du serveur et la moitié du bot. Ce qui reste : **4 catégories, 11 salons, un seul public, trois endroits par personne et par jour**. Le tunnel candidat (formation, quiz, test) vit désormais par e-mail, formulaires et WhatsApp ; Discord commence au contrat.

## 1. Ce que le serveur est aujourd'hui (inventaire lu dans le code du bot et la base)

Je n'ai pas accès au serveur en direct : cet inventaire vient du code (`tools/bot_clippers/`), de la base de connaissances v6.2 et du journal. `!audit` sur le serveur donne la carte réelle ; ce qui suit dit ce que le système est **conçu** pour faire.

**Deux populations, deux systèmes.** Le lien de fin du formulaire de candidature envoyait tout candidat sur le serveur (porte « formulaire » des invitations étiquetées), à côté de Disboard et d'Indeed. Le bot accueillait chacun en message privé, lui demandait son numéro, lui donnait un lien de quiz personnel, lui envoyait le test en MP, recevait le rendu en MP, relançait à 24 h et 48 h à trois moments (arrivé sans numéro, test non rendu, J'ACCEPTE manquant), gérait le mot STOP, purgeait les internationaux, annonçait les réouvertures. L'équipe, elle, utilise le salon de sa créatrice, son salon privé, #reporting et #discussion.

| Couche | Ce qui existe | Pour qui |
|---|---|---|
| Catégories et salons | vitrine (candidature, annonces, formation, assistant, tips, dopamine, bump, deux compteurs), paie (rémunération-fr / -int, bonus-fr / -int), signés (ressources, reporting, discussion-fr / -int), une catégorie par créatrice avec un salon privé par clipper, admin, manager | candidats + équipe |
| Rôles | Grille France, Grille International (candidats), Team France, Team Madagascar dit International (signés), Clipper + Rookie / Confirmé / Elite (compteur et rangs), Manager, admin | les deux |
| Doctrine d'accès | 3 étages appliqués par `!acces` d'après le **nom** du salon ; `!audit`, `!pourquoi` | candidats + équipe |
| Automatismes permanents | 7 boucles : compteurs (titres de salons, 10 min), bump Disboard, pipeline candidat (relances), rappels quotidiens et hebdo, index des fiches du forum, codes 2FA vers les managers, inputs Metricool (rapport du matin) | les deux |
| Commandes | 51 commandes `!` (admin), dont 15 ouvertes au manager | staff |
| Réglages | 83 variables d'environnement, 15 fichiers de données sur le volume persistant | Gaëtan |
| Webhooks entrants | `CANDIDATURE` (formulaire), `QUIZ_OK` / `QUIZ_KO` (quiz) | candidats |

**Ce que ça coûte, concrètement.** Un candidat recevait au minimum huit messages privés du bot avant son premier jour de travail. Le filet anti-spam (bans automatiques sur liens d'invitation, suppression des liens postés par des membres sans rôle) existe parce que des inconnus entrent : incidents « Evergreen-Nische » du 15/08 et « SafeBet » du 19/08. Les rôles de grille existent pour qu'un candidat puisse lire la paie avant de signer. Les compteurs et Disboard existent pour attirer des candidats. Le parrainage existe pour que des candidats en amènent d'autres. **Aucune de ces mécaniques ne sert un clipper signé.**

## 2. Ce qui rend la vie compliquée (classé, avec la preuve)

1. **Deux publics dans un même lieu** : la doctrine à trois étages, les huit rôles et les quatre grilles de permissions n'existent que pour séparer ce que voit un inconnu de ce que voit un signé. Chaque salon doit être rangé à la main dans un étage ; un salon renommé hors convention devient visible ou invisible par accident.
2. **Le tunnel candidat dans Discord** : la moitié des 51 commandes et 3 des 7 boucles servent le pipeline (numéro, quiz, test, relances, contrat). C'est la partie du bot qui a produit le plus d'incidents en deux mois (numéro mal lu, ID Discord vide, test renvoyé aux refusés, rôle donné avant le J'ACCEPTE, relances à des gens qui avaient dit STOP).
3. **Quatre salons de paie pour deux grilles**, deux discussions pour une équipe qui parle la même langue : déjà tranché le 14/09 (entrée 5 du [[Journal de coaching]]), fusion en cours.
4. **Des salons sans fonction** : #tips à côté de #ressources, #dopamine à côté de #annonces, #bump et deux compteurs pour un recrutement FR fermé.
5. **Un rôle qui ne sert qu'à compter** (Clipper) et trois rangs (Rookie / Confirmé / Elite) que personne n'attribue.
6. **Personne n'a de carte** : les clippers demandent « où je poste ma question ? », Jonas « où je regarde ça ? » (entrée 5 du 14/09).
7. **Le fondateur opère tout** : 83 variables, 15 fichiers, chaque réglage passe par Railway. Le manager n'a que 15 commandes et pas la main sur la porte d'entrée.
8. **Le risque sécurité est structurel** : tant que des inconnus entrent, les MP d'arnaque (« offres » lives TikTok, affiliation) atteignent les clippers ; le bot avertit, il ne peut pas empêcher.

## 3. La décision qui simplifie tout : fermer le serveur aux candidats

**Ce que ça retire, sans rien casser** (le code reste, il ne se déclenche plus) : accueil numéroté et guide d'arrivée, parrainage, portes d'entrée étiquetées, Disboard et bump, compteurs, filet anti-spam, `!lier`, `!quiz`, test et rendu en MP, relances « arrivé sans numéro » et « test non rendu », `!annonce-int`, `!purge-int`, `!relancer-lien`, `!importer`, rôles de grille comme rôles de candidat. Deux webhooks sur trois changent de sens (le quiz porte le numéro WhatsApp, un rendu de test arrive par formulaire).

**Ce que ça ajoute, en une seule commande pour le manager** : `!inviter Prénom` (test validé → invitation personnelle valable 7 jours, une seule personne, détruite à l'arrivée, avec le message WhatsApp prêt à coller). Tout le reste est automatique : à l'arrivée par cette invitation, le bot relie le numéro, écrit le prénom, pose la grille et enchaîne contrat (France) ou conditions + J'ACCEPTE (International). Un arrivant sans invitation validée est raccompagné (MP d'explication + expulsion) ; invité par un admin ou le manager, il est gardé ; porte indécidable, il est gardé et signalé.

**Le nouveau tunnel, étape par étape**

| Étape | Où | Qui fait | Ce qui se passe |
|---|---|---|---|
| 1. Candidature | Google Form | le candidat | prénom, pays, WhatsApp, e-mail. Le message de fin ne donne **plus** le lien Discord |
| 2. Porte | WhatsApp ou e-mail | Jonas (porte manuelle) ou l'Apps Script (porte automatique) | vidéo de formation + lien du quiz, voir la section 4 |
| 3. Quiz | Google Form | le candidat | question « numéro WhatsApp » à la place de l'identifiant Discord ; seuil 27/34, deux essais |
| 4. Test | e-mail (Apps Script quiz v4) | automatique | ≥ 27 : dossier de rushs + formulaire de rendu + échéance 48 h ; sinon score + deuxième essai |
| 5. Rendu | Google Form « Rendu du test » | le candidat | lien Drive / WeTransfer / Swisstransfer ; l'Apps Script poste `TEST_RENDU` au bot |
| 6. Jugement | #manager | Jonas | fiche (prénom, pays, score, lien) → `!inviter Prénom` ou `!refuser Prénom motif` |
| 7. Arrivée | Discord | automatique | liaison, prénom, grille, contrat ou conditions, manager prévenu |
| 8. Équipe | Discord | Jonas | `!creatrice`, créneau de création, salon privé |

Un candidat validé reçoit désormais **un** message privé du bot sur Discord (contrat ou conditions) au lieu de huit.

## 4. La porte : manuelle ou automatique ? (question de Gaëtan du 14/09 au soir)

Gaëtan propose : « une fois par semaine, DM à la main les meilleures candidatures sur WhatsApp directement ». **Oui pour la porte manuelle, non pour remplacer le tunnel automatique** : la sélection humaine se place à l'étape 2 et déclenche le reste, qui ne coûte plus une minute à personne.

- **Pourquoi la porte manuelle est meilleure que l'e-mail automatique à tous** : WhatsApp est le canal où les candidats malgaches répondent (l'e-mail part en spam, un Gmail perso plafonne à 100 envois par jour) ; le formulaire contient des signaux que l'automate ignore (iPhone, expérience, disponibilité, qualité de l'écriture) ; un message personnel d'un manager convertit mieux qu'un robot ; et c'est une heure de Jonas par semaine, pas de Gaëtan.
- **Pourquoi pas seulement à la main** : le quiz, l'e-mail de test, l'accusé de rendu et la fiche au manager coûtent zéro une fois posés ; les faire à la main, c'est réintroduire du travail humain là où il ne trie rien. Le vrai filtre reste le test rendu, pas la lecture d'un formulaire.
- **Le rythme** : hebdomadaire est trop lent pour un candidat chaud (un Malgache contacté sept jours après sa candidature a souvent trouvé autre chose). **Deux créneaux fixes, lundi et jeudi, 30 minutes**, dans la fiche de poste de Jonas.
- **Les critères écrits, sinon la sélection dépend de l'humeur** : iPhone (obligatoire), 18 ans ou plus, expérience de montage ou de gestion de comptes, disponibilité quotidienne déclarée, pays cohérent avec l'indicatif du numéro. Pas de note subjective : quatre cases cochées = message envoyé.
- **Le message WhatsApp de la porte** (langage collège, à coller) :

> Bonjour [Prénom], c'est Jonas, manager de l'équipe clippers G&M. Ta candidature nous plaît. Deux étapes pour continuer, dans l'ordre : 1) la formation en vidéo (54 min, regarde-la en entier, 4 mots-clés y sont cachés) : [LIEN_VIDEO] ; 2) le quiz (27/34 minimum, 2 essais, mets bien ce numéro WhatsApp) : [LIEN_QUIZ]. Quiz réussi = tu reçois le test de montage par e-mail (48 h). Test validé = ton invitation personnelle au Discord de l'équipe. Tu as jusqu'à dimanche pour le quiz. Bon courage !

- **Réglage qui en découle** : dans l'Apps Script de candidature, `ENVOYER_MAILS` reste à `0` (pas d'e-mail automatique à tous, la porte est Jonas) ; dans l'Apps Script du quiz et celui du rendu, `ENVOYER_MAILS=1` (test, deuxième essai, accusé de réception : automatiques). Si Jonas déborde ou part, on bascule la candidature à `1` et la porte redevient automatique sans toucher au reste.

## 5. La cible : 4 catégories, 11 salons, un seul public

| Catégorie | Salons | Qui voit | À quoi ça sert, en une phrase |
|---|---|---|---|
| 🎬 **ÉQUIPE** | #bienvenue · #annonces · #ressources · #reporting · #discussion · #assistant-ia · forum #formation | tous les signés | La carte épinglée, les annonces et victoires, captions + liste des créatrices, le formulaire du dimanche, une seule discussion, le bot 24 h/24, le Loom et les 6 fiches |
| 💶 **PAIE** | #rémunération-fr · #rémunération-int | par équipe | Un message épinglé par grille : fixe, commission, prime, le 16 et le 1er (les bonus dedans) |
| 👩 **CRÉATRICES** | une catégorie par créatrice active : #chloé (rushs, modèles) + un salon privé par clipper | ses clippers, le manager | Le lieu de travail : rushs, retours, bilan du matin en 4 lignes, codes |
| 🛠️ **STAFF** | #manager · #admin | Manager / Gaëtan | Le rapport du matin, les tests rendus et les arrivées (manager) ; l'hebdo du lundi et les pannes (Gaëtan) |

**Ce qui disparaît par rapport à la v1 du matin** : #candidature (plus de candidats ; renommé #bienvenue pour la carte) et la catégorie « Arrivée ». **Ce qui disparaît par rapport à aujourd'hui** : #tips, #dopamine, #bump, les deux compteurs, #bonus-fr, #bonus-int, #discussion-fr, #discussion-int, les catégories des créatrices gelées (archivées, pas supprimées).

**Rôles** : Team France, Team International (le rôle « Team Madagascar » peut être renommé, la variable `ROLE_TEAM_MG_NOM` suit), Manager, Admin. Les deux rôles Grille restent comme **rôles de transit** (un validé les porte 48 h au plus, entre son arrivée et sa signature, pour lire sa paie) : les supprimer ferait râler le bot à chaque arrivée pour rien. Le rôle Clipper et les trois rangs partent avec les compteurs.

**La doctrine d'accès passe de trois étages à un** : tout salon hors STAFF et CRÉATRICES est visible par tout signé. `!acces appliquer` continue de marcher (les salons « vitrine » sont maintenant vus par des signés, ce qui est le but), mais on n'a plus besoin de la comprendre.

## 6. La journée de chacun (trois endroits maximum)

- **Le candidat** : WhatsApp (Jonas), sa boîte mail (test, accusé), le formulaire de rendu. Il n'est sur Discord qu'une fois validé, et le bot lui parle une fois.
- **Le clipper** : ① son salon privé le matin (4 lignes) ; ② le salon de sa créatrice ; ③ #reporting le dimanche. Une question : #assistant-ia, puis son manager.
- **Jonas** : ① #manager le matin (un rapport marketing + les tests rendus + les arrivées) ; ② lundi et jeudi, 30 minutes, la porte WhatsApp ; ③ les salons créatrices et les créneaux de création. Ses commandes du tunnel tiennent en trois : `!candidats`, `!inviter`, `!refuser`.
- **Gaëtan** : #admin le lundi (`!hebdo`, `!ltv`), et rien d'autre.

## 7. Mise en place (45 minutes, une fois, dans cet ordre, réversible)

1. **Google Forms (10 min)** : candidature → « Collecter les adresses e-mail », message de fin « Merci ! Jonas te contacte sur WhatsApp sous 72 h » (sans lien Discord) ; quiz → question « Ton numéro WhatsApp (le même que dans ta candidature) », identifiant Discord facultatif pendant la transition ; créer le formulaire « Rendu du test » (5 questions, en-tête de `rendu_webhook.gs`).
2. **Apps Script (10 min)** : recoller `candidature_webhook.gs` (v2), `quiz_webhook.gs` (v4), `rendu_webhook.gs` (nouveau) ; propriétés `LIEN_TEST`, `LIEN_RENDU`, `LIEN_VIDEO`, `LIEN_QUIZ`, `ENVOYER_MAILS` (0 candidature, 1 quiz et rendu), `DISCORD_WEBHOOK_URL` sur le rendu ; déclencheur `surRendu`.
3. **Discord (15 min)** : `!fermer invitations` (verrou + révocation de toutes les invitations sauf celles du bot, dont le lien de fin de formulaire) → `!purge-candidats` (aperçu) → `!purge-candidats appliquer` (garde rôles, signés, exemptés, parcours en cours) → renommer #candidature en #bienvenue et y épingler le tableau de la section 5 → `!archiver #tips #dopamine #bonus-fr #bonus-int #discussion-fr` et les créatrices gelées → supprimer #bump et les compteurs → `!acces appliquer` → `!audit`.
4. **Annonce Telegram malgache** : **après** l'étape 1, jamais avant (sinon les candidats de l'annonce arrivent sur un serveur qui les raccompagne).
5. **Fiche de poste de Jonas** : ajouter la porte du lundi et du jeudi avec les quatre critères et le message type ([[Fiche de poste - Manager marketing (Jonas)]]).

Réversible : `!ouvrir` rend le serveur ouvert, le tunnel en MP repart tel quel.

## 8. Ce qui casse ça (avocat du diable)

- **La transition** : les candidats malgaches déjà sur le serveur en cours de test restent gérés en MP (la purge les protège par défaut) ; ceux qui ont reçu l'ancien lien de fin de formulaire mais ne sont pas encore entrés seront raccompagnés — le MP leur donne le formulaire, et Jonas les a de toute façon sur WhatsApp.
- **La clé n'est plus infaillible** : l'identifiant Discord pré-rempli reliait un quiz à un membre sans erreur possible ; le numéro WhatsApp tapé deux fois peut différer (espaces, indicatif). Le bot canonise et croise avec la candidature ; en cas d'échec la fiche arrive sans prénom, et `!inviter +261…` marche par numéro.
- **L'invitation transmise à un copain** : elle admet deux personnes pour être identifiable, mais la deuxième arrive après consommation et est raccompagnée. Un candidat qui donne son lien perd sa place : le message WhatsApp le dit.
- **Les MP fermés** : un validé qui n'a pas ouvert ses messages privés ne reçoit ni contrat ni conditions ; le message WhatsApp de `!inviter` le prévient, et le manager voit l'arrivée dans #manager.
- **L'expulsion à l'aveugle** : quand le bot ne sait pas par quelle porte quelqu'un est entré (invitations illisibles), il garde et signale plutôt que d'exclure. Le prix : un inconnu peut rester jusqu'à la prochaine `!purge-candidats`. Le contraire (sortir une créatrice ou Rianah) coûterait plus cher.
- **Le manager comme goulot de la porte** : deux créneaux fixes ou rien ; si Jonas rate une semaine, les candidats refroidissent. Le repli est écrit (candidature `ENVOYER_MAILS=1`).
- **La kill-list** : ce verrou ajoute des fonctionnalités au bot pendant le gel de la ligne 17 ([[Kill-list (NON, pas maintenant)]]). Exception assumée sur demande explicite, parce qu'il retire plus de flux qu'il n'en ajoute ; aucun autre ajout avant le 30/09.
- **La discipline** : un nouveau salon « juste pour ça » est le début du prochain bordel. Le test avant d'en créer un : quelle catégorie, quel rôle, quelle question du matin il résout.

## 9. Comment on saura que c'est simple (trois mesures, revues le 28/09)

1. **Part des membres du serveur avec un rôle Team** : cible ≥ 90 % (aujourd'hui : inconnue, `!audit` la donne).
2. **Messages privés du bot par candidat validé, sur Discord** : 1 (contre 8).
3. **Questions « où je regarde ça ? » de Jonas et « où je poste ? » des clippers** : 0 entre le 21 et le 28/09 (les lacunes du bot les comptent).
