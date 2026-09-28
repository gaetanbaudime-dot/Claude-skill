---
titre: "Process clippers - audit complet et 10 automatisations (28 septembre 2026)"
type: rapport
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-28
tags: [ops/clipping, ops/simplification, ops/automatisation, ops/bot, ops/paie]
liens_forts: ["[[Bilan des 20 simplifications - fait, plus besoin, à faire (27 septembre 2026)]]", "[[Process clippers de bout en bout - 10 simplifications (27 septembre 2026)]]", "[[Process clippers - 10 simplifications de plus, avec recherche (27 septembre 2026)]]", "[[Trois exceptions humaines - ban, numéro, paiement (27 septembre 2026)]]", "[[Formation clippers en une page et 10 simplifications (26 septembre 2026)]]", "[[Podcast Open Source - le clipping vu par un studio SaaS, ce qu'on en tire (28 septembre 2026)]]", "[[Machine horizontale v2 - plan de chantier (23 septembre 2026)]]"]
---

# Process clippers : audit complet et 10 automatisations (28 septembre 2026)

> [!tip] Verdict
> **Le process est automatique de l'annonce à la sortie, sauf six endroits, et un seul d'entre eux bloque vraiment : les e-mails des comptes.** Le classeur compte **284 lignes, dont 110 « à créer » sans e-mail** (Jade 39, Maddie 37, Clara 29, Sarah 5) : c'est ce que Gaëtan doit créer à la main, à 3 minutes l'alias, soit 5 h 30 devant lui, et c'est ce qui décide combien de clippers peuvent être servis chez ces créatrices. Les cinq autres manuels (paie le 5 et le 20, TOP 20 mensuel par créatrice, tests notés 5 à 7, nouvelle créatrice à monter dans Discord et Railway, les 12 anciens de Jonas hors bot) coûtent ensemble **15 à 20 heures par mois** (estimation), aucun ne bloque. Les dix automatisations ci-dessous en enlèvent huit ; les deux qui restent sont des décisions (les anciens de Jonas le 07/10) ou du contenu (le TOP 20, que le bot peut préparer mais pas choisir). Ordre : **n° 2, 4 et 8 cette semaine** (six heures de bot, zéro décision), puis n° 3 et 6 dès que Gaëtan donne cinq hashtags et une légende par créatrice, puis n° 1 testé sur cinq comptes avant d'y croire.

## 1. Le parcours complet, lien par lien

Ce qui se passe le 28/09 pour un clipper qui arrive, avec l'endroit ou le lien, et qui fait le geste. Les pages qui l'ont construit : [[Process clippers de bout en bout - 10 simplifications (27 septembre 2026)]] et [[Formation clippers en une page et 10 simplifications (26 septembre 2026)]].

| # | Étape | Où, quel lien | Qui fait | État |
|---|---|---|---|---|
| 1 | Annonce | Telegram, Indeed, bouche à oreille → le lien du site (`/candidature`) | Gaëtan, Jonas | Manuel (contenu) |
| 2 | Formulaire | Site du bot : prénom, âge, WhatsApp, Telegram, pays, téléphones, expérience, case des 5 règles → onglet « Candidatures bot » du classeur, note sur 8 | Bot | Auto (28/09) |
| 3 | Connexion Discord | Le site (`/connexion` → Discord → `/callback`) ajoute le candidat au serveur ; la fuite entre 2 et 3 n'est pas mesurée | Bot | Auto, non mesuré |
| 4 | Arrivée | Salon perso dans « 🎬 Clippers », un seul message : le parcours en une ligne, la formation, le lien personnel du quiz | Bot | Auto |
| 5 | Formation | Loom de 15 minutes, cinq mots-clés, tourné le 28/09 | Gaëtan (une fois) | Manuel à chaque changement de process |
| 6 | Quiz | Page du site (`/quiz?t=jeton`), 10 questions, 8 sur 10, deux essais, résultat dans le salon, ligne dans « Quiz bot » | Bot | Auto (28/09) |
| 7 | Test de montage | La vidéo brute arrive dans le salon, le clipper rend sa vidéo, le bot la regarde (ffmpeg + vision), 7 sur 10 ou plus = validé ; 5 à 7 = `!test-ok` ou `!test-non` | Bot, manager pour 5 à 7 | Semi |
| 8 | Acceptation | La case du formulaire vaut J'ACCEPTE : rôle Clippeur, registre | Bot | Auto |
| 9 | Créatrice | Séquence pondérée (Chloé 3, Sarah 3, Sophie 3, Jade 2, Clara 1, Maddie 1), rôle, salon déplacé sous sa catégorie ; une créatrice sans catégorie ou sans rôle Discord est sautée | Bot ; Gaëtan pour la catégorie et le rôle | Auto, sauf nouvelle créatrice |
| 10 | Comptes | Trois lignes de l'onglet de la créatrice (rendus d'abord, puis « à créer » avec e-mail), Gérant = prénom, un accès par jour dans les étapes 1 à 3, identifiant / e-mail / mot de passe en blocs copiables, code 2FA relayé depuis l'alias | Bot ; Gaëtan pour les alias et les lignes | **Manuel : 110 lignes sans e-mail** |
| 11 | Lien | Lien GAML cloné depuis le lien modèle de la créatrice, carte OF → tracking Infloww du POD, domaine par créatrice ; en story à la une, une seule fois | Bot ; Gaëtan pour le lien modèle, le domaine et les trackings | Auto, sauf par créatrice |
| 12 | Drive | Dossier du clipper (raccourcis Photos, Reels, Stories + « TOP 20 Reels » décliné par ffmpeg), ouvert par le lien | Bot ; Gaëtan pour le TOP 20 source | Auto, sauf la matière |
| 13 | Parcours | Sept étapes (compte 1, 2, 3 avec 24 h de warm-up chacun, premier Reel, lien, routine 2 Reels par jour par compte puis +1 par semaine jusqu'à 10), bouton ✅, relance tous les deux jours | Bot | Auto |
| 14 | Contrôle | Scan Apify à 7 h UTC : état des comptes, followers, publications, légende sans lien ni @ (✅ ou ❌), ligne du matin, rapport admin et Jonas | Bot ; Gaëtan pour le budget Apify (23,3 $ sur 29 le 28/09) | Auto |
| 15 | Paie | 0,05 $ la visite francophone hors robots ; `!paie-clics` le 5 et le 20 ; virement USDC sur Binance ; `!paiement` par clipper ; #dopamine | Bot pour la liste ; Gaëtan pour les virements et les `!paiement` | **Semi** |
| 16 | Sortie | 14 jours sans publication (liste la veille, note « garde ») ; départ du serveur = sortie complète (28/09) ; `!sortie` ; comptes au vivier, lien libéré pour le suivant | Bot | Auto |
| 17 | Exceptions | Ban, numéro refusé, paiement → WhatsApp Gaëtan ([[Trois exceptions humaines - ban, numéro, paiement (27 septembre 2026)]]) | Gaëtan | Manuel par choix |
| 18 | Les anciens | Douze clippers gérés par Jonas sur WhatsApp, fixe, `!stats-jonas`, hors salons persos et hors sortie automatique | Jonas | Manuel, deux systèmes |

Les liens du process, et ce qui casse quand l'un est faux :

| Lien | Qui le tient | S'il est faux |
|---|---|---|
| Site : `/candidature`, `/connexion`, `/quiz` | Bot (Railway) | Zéro arrivée ; le formulaire s'est déjà cassé en silence (relance Telegram du 26/09) |
| Loom de formation | Gaëtan | Quiz raté en série : le quiz est écrit sur la vidéo |
| Vidéo brute du test | Variable Railway | Test impossible, candidats bloqués à l'étape 7 |
| Drive du clipper et « TOP 20 Reels » | Bot, matière de Gaëtan | Étape 5 sans vidéos : le clipper attend |
| Lien GAML du clipper (domaine de la créatrice, numéro) | Bot, modèle de Gaëtan | Visites non comptées, paie fausse ; la racine sans numéro ne répond pas chez Sarah, Jade et Clara |
| Tracking Infloww du POD | Gaëtan | Rentabilité par clipper invisible ; `!trackings` le dit |
| Classeur des logins (six onglets, en-têtes) | Gaëtan, écrit par le bot | Comptes non livrés, états faux ; les onglets masqués ne sont pas lus |
| Classeur des candidatures (trois onglets) | Bot | Sauvegarde des formulaires et des quiz perdue |
| Bouton WhatsApp Gaëtan | Variable Railway | Les trois exceptions n'ont plus de porte |
| Post « Bienvenue » de #candidature | Gaëtan | Dit encore « slash code » et l'ancien quiz |

## 2. Tout ce qui est encore manuel

| Tâche | Qui | Quand | Temps (estimation) | Chiffre du jour | Automatisable |
|---|---|---|---|---|---|
| Alias iCloud et lignes « à créer » du classeur | Gaëtan | À chaque vague | 3 min par compte | 110 lignes sans e-mail | Oui, n° 1 |
| TOP 20 par créatrice | Gaëtan | Mensuel | 30 à 60 min × 6 | Six faits le 27/09 | Assisté, n° 10 |
| Lien GAML modèle et domaine par créatrice | Gaëtan | Par créatrice | 15 min | Six en place | Le lien oui (n° 5), le domaine non |
| Trackings Infloww par POD | Gaëtan | Par créatrice | 30 à 60 min | 31 posés, 0 manquant | Non : l'API Infloww est en lecture seule |
| Virements USDC et `!paiement` | Gaëtan | Le 5 et le 20 | 20 à 40 min par liste | 23 actifs au clic le 05/10 | En partie, n° 4 |
| Tests notés 5 à 7 | Manager | Par test | 5 min | Mathieu validé à 5 deux fois | Oui, n° 2 |
| Ban, numéro, paiement | Gaëtan | Chaque jour | 15 min par jour | — | Non, par choix ; n° 3 réduit les bans de mots de passe partagés |
| Liste de sortie automatique à relire | Gaëtan | 12 h Dubaï | 1 min | Première liste le 29/09 | Déjà automatique, lecture seule |
| Nouvelle créatrice : catégorie, rôle, salon ℹ️, onglet, roster, `DRIVE_SOURCES` | Gaëtan | Par créatrice | 30 min + un redéploiement | — | Oui, n° 5 |
| Post « Bienvenue », fiches, carte de la créatrice | Gaëtan | À chaque changement | 15 min | En retard (« slash code », ancien quiz) | Oui, n° 6 |
| Annonces Telegram et Indeed | Gaëtan, Jonas | Chaque semaine | 30 min | 462 candidatures en trois mois | Non (contenu) ; mesurer la fuite, n° 7 |
| Rattrapages `!onboarding`, `!liberer` | Gaëtan | Ponctuel | 10 min | Simon ce matin : deux accès différents sous les yeux | En partie : une seule source d'accès par clipper |
| Budget Apify | Gaëtan | Mensuel | 5 min | 23,3 $ sur 29 | Oui, n° 8 |
| Mot de passe d'un compte rendu | Personne | À chaque sortie | 0 | L'ancien garde l'accès | Oui, n° 3 |
| Les 12 anciens de Jonas | Jonas | Chaque jour | 1 à 2 h par jour | Ultimatum du 27/09, échéance 07/10 | Décision, n° 9 |
| Refaire le Loom quand le process bouge | Gaëtan | À chaque changement | 1 h | Version du 28/09 | Non |

Total pour Gaëtan, hors la dette des 110 alias : environ 15 à 20 heures par mois (estimation, à mesurer une semaine avec `!hebdo`). Le goulot au sens de la [[Théorie des contraintes]] n'est ni le recrutement (462 candidatures), ni le bot : c'est l'e-mail de chaque compte, puis la matière.

## 3. Les dix automatisations

Chacune dit ce qu'elle enlève, ce qu'elle coûte, ce qui peut casser, et si c'est confirmé (tout existe déjà), probable (à tester) ou spéculatif.

1. **Les e-mails des comptes par un domaine à nous.** Un domaine avec redirection « tout courrier » vers la boîte IMAP que le relais 2FA lit déjà ; le bot écrit lui-même la ligne « à créer » avec un e-mail `prenom.n@domaine` et le code arrive au même endroit. Enlève : les 110 alias à la main et toutes les vagues suivantes. Coût : un jour. Risque : Instagram se méfie des domaines jeunes et peut demander plus de vérifications ; **à tester sur cinq comptes** avant d'abandonner iCloud. Probable.
2. **Le test se juge seul.** Note de 5 à 7 : second essai automatique avec les deux points à corriger ; encore sous 7 : refus automatique ; `!test-ok` reste pour forcer. Enlève : la décision du manager sur chaque test moyen. Coût : une heure. Risque : un bon candidat maladroit perdu ; la sortie à 14 jours corrige l'erreur inverse, pas celle-ci. Confirmé.
3. **Mot de passe changé à la reprise d'un compte rendu.** Le bot génère le nouveau mot de passe, l'étape « connexion » demande de le poser, un bouton « ✅ Mot de passe changé » l'écrit au classeur, relance à J+2 sinon. Enlève : l'ancien clipper qui garde l'accès (aujourd'hui, personne ne change rien). Coût : deux heures. Risque : le clipper ne le fait pas, d'où la relance et le blocage de l'étape suivante. Probable.
4. **La paie en un geste.** `!paie-clics` sort déjà la liste ; y ajouter le wallet et le montant au format à coller dans Binance, puis `!payé tout` (ou `!payé tout sauf Prénom`) clôture la liste, poste #dopamine et écrit le registre. Enlève : vingt-trois `!paiement` à la main. Coût : deux heures. Risque : un virement raté marqué payé, d'où le « sauf ». Confirmé. Un paiement groupé côté Binance : à vérifier, pas promis.
5. **Une nouvelle créatrice en une commande.** `!creatrice-nouvelle Prénom` crée la catégorie, le rôle, le salon ℹ️ avec sa carte, l'onglet du classeur avec les en-têtes, l'entrée du roster et de l'ordre d'attribution, le dossier « 🎬 Clippers » du Drive (lien donné dans la commande) et clone le lien GAML modèle depuis un gabarit ; `DRIVE_SOURCES` vit dans un fichier au lieu d'une variable Railway. Enlève : trente minutes et un redéploiement par créatrice. Reste manuel : le domaine GAML et les trackings Infloww. Coût : une demi-journée. Probable.
6. **La carte de campagne, générée.** Par créatrice, une carte en tête de son salon ℹ️ et du salon perso de chaque clipper : le taux, le lien modèle, le Drive, le TOP 20, les cinq règles, **cinq hashtags et une légende type** (ce que Gaëtan demandait le 28/09 : une légende courte et sage, toujours la même, que le clipper colle sous chaque Reel avec les cinq hashtags de la créatrice, pour qu'il n'écrive jamais rien lui-même ni ne mette de lien), et deux Reels exemples. Le post « Bienvenue » et les fiches sont régénérés depuis la base v13 à chaque déploiement. Enlève : les textes en retard (« slash code », l'ancien quiz), les légendes improvisées. Coût : une demi-journée. Il faut de Gaëtan : cinq hashtags et une légende par créatrice, cinq minutes chacune. Confirmé.
7. **Mesurer la fuite formulaire → Discord avant de relancer.** Une ligne « formulaires → Discord liés » dans le tableau du lundi (une heure). Si la fuite dépasse 30 %, un bot Telegram lié au formulaire (le candidat écrit /start à la fin du formulaire pour recevoir son lien) relance à J+1 et J+3. Enlève : les relances WhatsApp de Jonas du lundi et du jeudi. Coût : un jour pour le bot Telegram. Spéculatif tant que la fuite n'est pas mesurée : 227 des 462 candidats n'étaient jamais arrivés au temps du Google Form, on ignore le chiffre depuis le site.
8. **Apify à moitié prix, et « visites pour 1 000 vues ».** Scanner chaque jour seulement les comptes des actifs, le reste chaque semaine ; croiser vues (Apify) et visites (GAML) par clipper dans le tableau du lundi. Enlève : le risque de dépasser le budget, qui couperait le scan, donc la sortie automatique et les ✅ ; et l'aveuglement sur ce qui convertit (voir [[Podcast Open Source - le clipping vu par un studio SaaS, ce qu'on en tire (28 septembre 2026)]]). Coût : trois heures. Confirmé.
9. **Un seul système.** Le 07/10, les douze anciens de Jonas entrent dans le bot (salon perso, paie au clic) ou sortent ; disparaissent alors `sans_salon`, `!stats-jonas`, les exclusions de la sortie automatique et le rapport scindé. Enlève : une classe d'exceptions dans le code, deux systèmes de paie, le temps de Jonas. Coût : zéro ligne, une décision. Décision de Gaëtan.
10. **Le TOP 20 assisté.** Le 1er et le 15, le bot classe les Reels de chaque créatrice par vues (Apify) et poste la liste des vingt meilleurs avec leurs liens ; Gaëtan glisse les fichiers depuis le Drive source en dix minutes au lieu de les chercher. Ne remplace pas le choix, et ne télécharge rien depuis Instagram (CGU). Coût : deux heures. Probable.

Ordre recommandé : 2, 4, 8 cette semaine ; 3 et 6 dès les hashtags reçus ; 1 sur cinq comptes ; 5 et 10 ensuite ; 7 après la mesure ; 9 le 07/10. Le chantier de fond reste celui du 23/09 ([[Machine horizontale v2 - plan de chantier (23 septembre 2026)]]) ; la valeur d'un clic, dans [[Machine horizontale v2 - paie au clic, ce que les clippers rapportent (23 septembre 2026)]].

## 4. Ce qui ferait échouer ça

- **Automatiser les e-mails sans le test sur cinq comptes.** Cinq comptes bloqués à la création coûtent moins que cent lignes inutilisables.
- **Deux sources d'accès pour un même clipper.** Simon avait ce matin un compte « déjà créé » livré par la colonne Gérant et un compte « à créer » dans son étape 1 : il ne savait plus s'il devait créer ou se connecter. Règle : les accès ne viennent que du parcours.
- **Lancer sans le chiffre du lundi.** « Validés → premier Reel » (31 % le 25/09) est le seul juge ; les automatisations 2, 4 et 8 se mesurent dessus une semaine avant la suite.
- **Croire que le bot fait la matière.** Le TOP 20 reste un choix humain ; sans lui, tout le reste tourne à vide.

**Prédiction (28/09, revue le 12/10)** : si les n° 2, 4 et 8 sont en ligne avant le 05/10, la liste du 20/10 se clôture en une commande, aucun test ne reste à juger plus de 24 h, et chaque actif a sa ligne « visites pour 1 000 vues » (65 %) ; le compteur de lignes sans e-mail passe de 110 à moins de 60, par le domaine ou par Gaëtan (50 %).

Décisions et prédictions dans le [[Journal de coaching]] ; l'architecture Discord dans [[Architecture Discord - simple au quotidien (14 septembre 2026)]] ; le formulaire et les annonces dans [[Recrutement clippers - annonces et formulaire]] ; le hub business : [[LTP Models]].

**Suite (28/09 soir)** : dix idées de plus, lues dans le classeur du soir (36 lignes « à créer » jamais créées, 24 lignes BAN avec un Gérant), dans [[Process clippers - 10 automatisations de plus (28 septembre 2026, soir)]].
