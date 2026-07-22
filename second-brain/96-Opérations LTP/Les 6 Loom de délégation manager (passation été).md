---
titre: "Les 6 Loom de délégation manager (passation été)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-22
tags: [ops/délégation, ops/management, ops/clippers, ops/sop, plan/richesse]
liens_forts: ["[[Les 5 Loom de passation]]", "[[Manager 200 clippers par un système]]", "[[Continuité du bot et paie sacrée (plan anti-panne)]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Se licencier de son propre poste]]"]
---

# Les 6 Loom de délégation manager (passation été)

> [!tip] Verdict
> **Tu pars dimanche 26/07 pour ~2 mois. Ces 6 Loom sont ce qui fait tourner le tunnel clipper SANS toi — c'est la casquette « manager d'opérations » que tu rends, pas la formation d'un clipper (ça, c'est [[Les 5 Loom de passation]] + [[Checklist formation clipping]]).** Distinction nette : les 5 Loom de passation apprennent à un clipper à FAIRE le travail ; ces 6-là apprennent à ton **Manager clippers** à FAIRE TOURNER LA MACHINE (piloter le funnel, valider, contractualiser, payer, arbitrer les blocages). ~2 h de tournage qui transfèrent le pilotage d'un tunnel de 50 recrues. Règle de production identique : **1 Loom ≤ 8 min + 1 checklist écrite + les captures des écrans risqués** — un Loom non doublé d'une checklist est un savoir qui meurt à la première question ([[Buy Back Your Time (Dan Martell)|Camcorder Method]]). Le test de fin ([[Se licencier de son propre poste|Gerber]]) : *le tunnel tourne-t-il tenu par une personne au niveau de compétence minimal, avec la vidéo + la checklist seules ?* Si une exception remonte jusqu'à toi à Paris pour autre chose qu'un **conflit de règles**, le Loom n'est pas fini.

## Avant de tourner — 3 décisions à trancher (sinon les Loom mentent)

Je ne les invente pas à ta place — trois points de ton workflow réel que je n'ai pas confirmés et qui changent le contenu des Loom. **Décide-les avant de récorder** :

1. **Droits bot du manager.** Les commandes admin (`!pipeline`, `!test-ok`, `!equipe`, `!paiement`, `!rang`, `!apprendre`) marchent depuis n'importe quel canal mais **uniquement pour les `ADMIN_IDS`**. Pour déléguer, il faut **ajouter l'ID Discord du manager à `ADMIN_IDS`** (variable Railway) — sinon il ne peut rien piloter. → à faire avant son 1er jour. **Garde-fou** : `!paiement` et `!equipe` sont les deux commandes à conséquence financière/juridique — tu peux vouloir garder `!paiement` pour toi seul le mois 1 (voir Loom 5).
2. **Qui vérifie les subs payables.** La grille paie **le sub tracké vérifié** (GetAllMyLinks réconcilié Infloww). Est-ce le manager qui fait la réconciliation, ou tu la gardes ? Mon défaut recommandé : **le manager prépare, tu valides le montant le mois 1**, puis tu lâches quand la confiance est faite.
3. **Le plafond de décision du manager.** Jusqu'où il décide seul (valider un test, envoyer un contrat, geler un fixe) vs. ce qui remonte à toi (virer quelqu'un, changer la grille, gérer un litige de paie public). Mon défaut : **il exécute les règles écrites, tu gardes les exceptions de règle** — c'est exactement la ligne [[Manager 200 clippers par un système|Dalio×Gerber]].

---

## Loom 1 — « Comment produire 30 Reels avec Opus Clip ? » (la compétence transmise aux pods FR)

- **Objectif** : le manager sait produire, et surtout **onboarder un pod FR à Opus Clip** (l'accès est fourni aux FR — [[Équipe marketing - structure et rémunération (FR × MG)|grille]]). Une vidéo longue → ~30 variantes de Reels prêtes à poster, sans repartir de zéro et sans dépendre de Rianah.
- **Durée cible** : 6-7 min · **À partager à l'écran** : le dashboard Opus Clip, l'import d'une vidéo YouTube de créatrice, les réglages, l'export, le dépôt Drive.
- **Les beats** :
  1. Pourquoi Opus Clip : 1 vidéo longue (YouTube de Chloé = matière première abondante) → ~30 clips → une semaine de posts. C'est ce qui **casse la dépendance à Rianah** comme point de défaillance unique.
  2. Import par URL de la vidéo longue → laisser l'IA détecter les moments forts.
  3. Réglages qui comptent : ratio **9:16**, longueur des clips, **sous-titres FR activés**, reframe auto sur le visage.
  4. Le tri humain : garder ceux qui ont une **accroche dans les 3 premières secondes** (le critère du quiz Q26), jeter les mous.
  5. **Varier chaque exécution** (jamais le même fichier partout — anti-détection de doublons, Q15 du quiz).
  6. Nommer proprement + déposer dans le **dossier Drive de la créatrice** (accès par rôle, plus de circuit Gmail depuis le 18/07).
- **Phrase de clôture** : « Une vidéo longue, c'est ta semaine de contenu. Un pod FR qui maîtrise ça ne te demande plus jamais “je poste quoi”. »
- **Checklist écrite** : les 6 réglages Opus Clip + la règle de nommage Drive + « 1 exécution = 1 variante ».

## Loom 2 — « Comment lire le tunnel chaque matin ? » (le pilotage avec `!pipeline`)

- **Objectif** : en 1 commande, le manager sait **qui est où** dans le funnel et **qui relancer**. C'est son rituel de 5 min chaque matin.
- **Durée cible** : 5 min · **À partager à l'écran** : Discord, la commande `!pipeline`, un candidat à chaque étape.
- **Les beats** :
  1. Le funnel, dans l'ordre (le dire clairement, c'est la carte mentale) : **liaison tél + candidature → rôle Grille FR/INT** (selon indicatif/pays) **→ quiz (27/34) → test de montage 48 h → FR : contrat DocuSeal → Team FR · INT : `!test-ok` → Team INT**.
  2. `!pipeline` : lire les compteurs (en attente de test, testés, sous contrat). Le chiffre qui compte : **les gens bloqués à une étape depuis > 48 h**.
  3. `!fiche @candidat` (ou `!contrat @candidat`) : le diagnostic complet d'UNE personne quand elle semble coincée — où elle bute exactement.
  4. La règle de relance : un candidat qui a réussi le quiz mais n'a pas rendu son test à H+40 → un MP de relance (le bot envoie le test auto au `QUIZ_OK`, mais l'humain relance).
  5. Ce qui n'est PAS son travail : répondre aux questions kit (c'est l'**assistant** dans `#assistant`) — il pilote le flux, il n'est pas le SAV.
- **Phrase de clôture** : « Chaque matin : `!pipeline`, tu repères les bloqués, tu relances. 5 minutes, et personne ne tombe entre deux étapes. »
- **Checklist écrite** : l'ordre du funnel + `!pipeline` / `!fiche` / `!contrat` + la règle « bloqué > 48 h = relance ».

## Loom 3 — « Comment valider (ou refuser) un test de montage ? » (`!test-ok` / `!test-non`)

- **Objectif** : le manager applique **les mêmes critères que toi** pour dire go/no-go sur le test 48 h — le point où la qualité de l'équipe se joue.
- **Durée cible** : 6 min · **À partager à l'écran** : un test rendu (bon), un test rendu (faible), les commandes.
- **Les beats** :
  1. Ce qu'on juge sur le test (⚠️ **à confirmer/fixer par toi** — mets TES 3-4 critères exacts, je ne les invente pas) : accroche 3 premières secondes · sous-titres propres · rythme/coupes · respect du brief (safe, zéro sollicitation) · variation vs. simple repost.
  2. Le seuil : « est-ce postable en l'état sur un compte de créatrice ? » Si oui → `!test-ok @membre`. Si non → `!test-non @membre [raison courte et actionnable]`.
  3. `!test-ok` sur un **INT** : attribue le rôle + onboarding directs et **retire la Grille INT** (parité FR, corrigé le 22/07). Sur un **FR** : le `!test-ok` ne donne PAS encore l'accès — il ouvre la voie au **contrat** (Loom 4).
  4. `!test-non` : la raison est un feedback, pas un couperet — un candidat peut re-rendre. Toujours dire **quoi corriger**.
  5. Le piège à éviter : valider par sympathie. Un test faible validé = un clipper qui poste du contenu qui fait bannir un compte de créatrice.
- **Phrase de clôture** : « Un seul critère au fond : est-ce que je posterais ça sur le compte de Chloé demain ? Oui → `!test-ok`. Non → `!test-non` avec le quoi-corriger. »
- **Checklist écrite** : TES critères de validation (à figer) + `!test-ok` (INT = accès direct, FR = ouvre le contrat) + `!test-non @x [raison]`.

## Loom 4 — « Comment contractualiser et onboarder ? » (FR DocuSeal → Team FR · INT direct)

- **Objectif** : transformer un test validé en clipper **sous contrat avec ses accès**, par les deux circuits, sans jamais sauter la vérification d'âge.
- **Durée cible** : 6 min · **À partager à l'écran** : l'envoi DocuSeal (FR), le résultat côté bot, l'attribution de rôle.
- **Les beats** :
  1. **Non négociable absolu** : **vérification d'âge manuelle à la signature** — mineurs = risque existentiel, jamais un accès avant. Le déclaratif ne suffit pas.
  2. **Circuit FR** : test validé → envoi du **contrat DocuSeal** → à la signature, le bot attribue **automatiquement Team France + onboarding** (parcours du 20/07, plus besoin de `!equipe` à la main). Si l'auto-onboarding rate, secours manuel : `!equipe @membre fr`. Audit du registre : `!equipes`.
  3. **Circuit INT** : pas de DocuSeal — l'acceptation « J'ACCEPTE » est enregistrée par le bot, puis `!test-ok` donne le rôle **Team INT** direct (grille retirée).
  4. Les accès donnés au bon niveau : serveur opérationnel **role-gated par créatrice**, jamais le serveur public ; **les comptes appartiennent à l'agence** (récupérables — condition d'onboarding).
  5. Le 1:1 J+7 : un seul appel court avec chaque nouveau (feedback sur 3 clips) — c'est le geste de rétention le plus rentable ([[Manager 200 clippers par un système|protocole J0-J30]]).
- **Phrase de clôture** : « FR : contrat signé = accès auto. INT : `!test-ok` = accès. Dans les deux cas, l'âge est vérifié AVANT, et les comptes restent à l'agence. »
- **Checklist écrite** : vérif âge → circuit FR (DocuSeal→auto, secours `!equipe fr`) / circuit INT (`!test-ok`) → role-gate par créatrice → 1:1 J+7.

## Loom 5 — « Comment payer, sans jamais casser la confiance ? » (la paie sacrée, `!paiement`)

- **Objectif** : le manager exécute la paie **à la lettre et à l'heure** — c'est la condition n°1 de survie du modèle. Un seul cycle contesté en public dans un Discord de 150 personnes déclenche la spirale ([[Manager 200 clippers par un système|condition ①]]).
- **Durée cible** : 7 min · **À partager à l'écran** : la grille, un calcul de sub vérifié, `!paiement`, le compteur épinglé.
- **Les beats** :
  1. La grille (la dire exactement) : **FR 200 €/mois fixe conditionnel + 0,50 €/sub vérifié · MG 100 € + 0,50 €/sub**. **Mois 1 : paie hebdo, 50 €/semaine (FR) le lundi**, versée APRÈS la semaine, jamais d'avance. Puis mensuel.
  2. Le fixe hebdo tombe si et seulement si **les 4 conditions SLA sont vertes** : volume publié ≥ 90 % (analytics natifs, jamais de captures) · 6 comptes sains (ban signalé < 24 h = neutralisé) · **≥ 5 subs trackés / 14 j** (semaines 1-2 exemptées, warmup) · reporting du dimanche envoyé. **1 rouge = pas de fixe cette semaine, pas de négo, pas de rétroactif.** 2 semaines rouges = gel du pod + conversation.
  3. **La commission n'est JAMAIS gelée** : les 0,50 €/sub vérifiés restent dus même quand le fixe saute — le fixe paie le process, la commission paie le résultat. C'est ce qui rend le gel incontestable (et propre juridiquement : on ne retient jamais du travail livré).
  4. Le rythme sacré : vues/subs **vérifiés à J+7**, **virement à J+8**, jamais un retard. `!paiement @clippeur 50 [raison]` → annonce dopamine + **compteur épinglé « X € déjà versés »** + trace `paiements.jsonl`.
  5. Le rituel : **dimanche** reporting → **lundi** appel de groupe (20 min : wins → chiffre focus → shoutouts) **+ paie hebdo dans les 24 h**. La boucle reporting→reconnaissance→paiement en < 24 h est le système de confiance le plus puissant à distance.
  6. **Anti-fraude (à annoncer AVANT le premier cas)** : sub vérifié uniquement, audit aléatoire 10 % des posts, clawback contractuel, bannissement public documenté du 1er fraudeur — annoncée avant = politique, après = injustice ([[Manager 200 clippers par un système|anti-Goodhart]]).
  7. ⚠️ **Décision à trancher** (voir en-tête) : garde-tu `!paiement` pour toi le mois 1, ou tu le délègues avec validation du montant ? Le rail de secours si tu es injoignable : **Maxence payeur de secours** ([[Continuité du bot et paie sacrée (plan anti-panne)]]).
- **Phrase de clôture** : « La paie n'est jamais en retard, jamais discutée, jamais rétroactive. J+7 on vérifie, J+8 on vire. C'est la seule règle qu'on ne casse jamais. »
- **Checklist écrite** : grille + 4 conditions SLA + « commission jamais gelée » + J+7/J+8 + `!paiement` + rituel dim/lun + plan anti-fraude + qui appuie sur le bouton.

## Loom 6 — « Comment gérer les blocages : bans, non-performeurs, questions ? » (qualité & arbitrage)

- **Objectif** : le manager gère seul les 3 blocages du quotidien — un compte banni, un clipper qui ne produit pas, l'assistant IA qui sèche — et sait **quand ça remonte à toi**.
- **Durée cible** : 7 min · **À partager à l'écran** : un signalement de ban, `!lacunes`, `!apprendre`, la scorecard.
- **Les beats** :
  1. **Compte banni** : le clipper le signale < 24 h (condition SLA neutralisée). Refabrication propre = **1 profil = 1 IP**, warmup 48 h, on **ne re-crée jamais** dans la panique ni en masse. Ce qu'on ne fait JAMAIS : ferme de comptes / anti-detect (dette CGU jamais normalisée, [[Manager 200 clippers par un système|risque plateforme]]).
  2. **Non-performeur** (⚠️ **pas maintenant** : à 10 sous contrat c'est prématuré de virer — [[Journal de coaching|décision du 22/07]]). La règle quand ça viendra : 2 semaines SLA rouges consécutives → gel du fixe → conversation → **récupération des accès** (comptes = agence) → sortie si pas de plan crédible. La commission déjà due reste versée. Ne **jamais** promouvoir le meilleur clipper en manager (principe de Peter — on promeut celui qui **aide déjà les autres** dans le Discord).
  3. **L'assistant IA** : quand un clipper pose une question, c'est l'assistant qui répond dans `#assistant`. Le manager surveille `!lacunes` (les questions hors kit) et **comble avec `!apprendre La question ? | La réponse.`** — mais **jamais** de mot-clé ni de réponse du quiz dans la base (interdit absolu). `!stats` pour suivre l'usage.
  4. **La ligne d'escalade** ([[Manager 200 clippers par un système|pipeline d'exceptions]]) : bot (collecte/tracking/relances) → **manager** (exceptions qualité/humaines) → **toi** (exceptions de *système* : une règle manque ou deux se contredisent). Ce qui remonte à Paris : litige de paie public, changement de grille, décision de virer, mineur suspecté. Le reste : il tranche.
  5. Ton seul travail hebdo non délégable (60 min) : lire l'issue log ([[Journal de coaching]]), ajuster les règles, décider les promotions — **pas** reprendre l'opérationnel (le piège du fondateur qui casse la machine).
- **Phrase de clôture** : « Tu gères le ban, le mou, la question. Ce qui monte jusqu'à moi, c'est seulement quand une règle manque ou se contredit — le reste, tu tranches. »
- **Checklist écrite** : refabrication propre (1 IP/profil, jamais en masse) + escalade non-performeur (gelée pour l'instant) + `!lacunes`/`!apprendre`/`!stats` (jamais le quiz) + la ligne d'escalade + ce qui remonte à toi.

---

## Les règles de production (identiques aux [[Les 5 Loom de passation|5 Loom de passation]])

1. **Tu fais en vrai, tu ne présentes pas** — filme le pilotage réel, `!pipeline` d'un vrai matin, un vrai `!test-ok`.
2. **Chaque Loom se double d'une checklist écrite** le jour même (Claude transcrit, tu relis 5 min) — éditable en minutes quand un process change ; re-tourner une vidéo ne l'est pas.
3. **Câblage bot FAQ** : toute question du manager posée 2 fois → entrée `!apprendre` pointant vers le bon Loom au bon timestamp.
4. **Interdit** : les mots-clés/réponses du quiz, les identités réelles des créatrices, les chiffres de l'agence hors périmètre du rôle.
5. **Ordre de tournage recommandé** (priorité départ) : **5 (paie) → 2 (pipeline) → 3 (tests) → 4 (contrat) → 6 (blocages) → 1 (Opus Clip)** — la paie et le pilotage d'abord, ce sont eux qui cassent si tu manques.

## Le test de fin (Gerber, mesurable pendant ton absence)

Chaque Loom passe le test : *le tunnel tourne-t-il tenu par le manager au niveau de compétence minimal, avec la vidéo + la checklist seules ?* **Critère de réussite mesurable depuis Paris** : pendant 2 mois, **zéro exception qui remonte jusqu'à toi hors conflit de règle** — les tests se valident, les contrats partent, la paie tombe J+8, les bans se refabriquent, sans toi. Si tu reprends l'opérationnel une seule fois « parce que c'est plus rapide », tu casses la machine ([[Se licencier de son propre poste|le piège du fondateur]]).
