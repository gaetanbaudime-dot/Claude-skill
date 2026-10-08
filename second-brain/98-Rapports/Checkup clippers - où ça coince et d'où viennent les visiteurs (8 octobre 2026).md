---
titre: "Checkup clippers - où ça coince et d'où viennent les visiteurs (8 octobre 2026)"
type: rapport
cluster: "98-Rapports"
statut: verified
créé: 2026-10-08
tags: [rapport/analyse, ops/clippers, marketing/acquisition, ops/automatisation, outil/bot]
liens_forts: ["[[LTP Models]]", "[[Journal de coaching]]", "[[Rapport GAML - d'où vient le trafic, créatrice par créatrice (16 septembre 2026)]]", "[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)]]", "[[App clippers - une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)]]", "[[Théorie des contraintes]]"]
---

# Checkup clippers : où ça coince, et d'où viennent les visiteurs (8 octobre 2026)

> [!tip] Verdict
> **La moitié des visiteurs GetAllMyLinks vient de nous, l'autre moitié des comptes des créatrices. Mais le goulot n'est ni Instagram ni le contenu : c'est le bot lui-même, qui cassait le passage « signé → compte créé → lien en bio ».** Sur 7 jours (02 au 08/10), 12 249 visiteurs : **49 % comptes des créatrices, 51 % agence** (clippers 32 %, Metricool 11 %, Facebook et YouTube 8 %). Huit des neuf anciens les plus productifs n'avaient pas de salon, les nouveaux recevaient leurs trois comptes d'un coup, un oubli de bouton figeait le parcours, le bouton WhatsApp ouvrait le mauvais écran, des réponses à l'appel étaient effacées, et un clipper qui publiait allait être expulsé. **Tout est corrigé et poussé le 08/10 (cinq lots).** Deux alertes restent pour cette semaine : **le moteur Metricool a perdu 54 % de ses visites en une semaine**, et **les abonnés MYM de Sophie, Jade et Clara arrivent surtout hors GAML**. La vraie part « créatrices contre nous » se tranche avec l'export MyPulse par lien de tracking, pas avec les visites.

## 1. La part des visiteurs : créatrices contre nous

Source : API GetAllMyLinks, 49 liens lus un par un, robots exclus, heure de Paris, 164 appels le 08/10. « 7 j » = 02 au 08/10 (le 08 en cours) ; « 30 j » = 09/09 au 08/10.

| Source | 7 j | Part 7 j | 30 j | Part 30 j | Le 16/09 (30 j) |
|---|---|---|---|---|---|
| **Comptes des créatrices** (lien de bio de leur compte) | 6 031 | **49 %** | 22 752 | 41 % | 34 % |
| **Clippers** (liens « Clipping Prénom ») | 3 902 | **32 %** | 14 429 | 26 % | 24 % |
| **Metricool** (Rianah, Julien) | 1 393 | **11 %** | 12 996 | 23 % | 25 % |
| Pages Facebook | 164 | 1 % | 3 267 | 6 % | 13 % |
| Chaînes YouTube | 759 | 6 % | 2 284 | 4 % | 5 % |
| **Total** | **12 249** | | **55 728** | | 43 004 |
| **Agence (tout sauf les créatrices)** | **6 218** | **51 %** | **32 976** | **59 %** | 66 % |

Par créatrice, sur 7 jours :

| Créatrice | Visiteurs | Son compte | Clippers | Metricool | Facebook / YouTube |
|---|---|---|---|---|---|
| Chloé | 4 551 | 55 % | 40 % | 2 % | 3 % |
| Sarah | 3 714 | 46 % | 53 % | 0 % | 1 % |
| Maddie | 2 097 | 69 % | 1 % | 14 % | 16 % |
| Sophie | 1 256 | 0 % | 9 % | 56 % | 35 % |
| Clara | 342 | 100 % | 0 % | 0 % | 0 % |
| Jade | 289 | 0 % | 2 % | 98 % | 0 % |

Trois remarques de lecture. **Sophie n'a plus aucun lien de son propre compte qui ramène du trafic** : sa page racine porte la note « Rianah Metricool » (les comptes de l'agence), et le lien « Compte de la créatrice » créé le 05/10 est désactivé, à 0 visite. **Le chiffre 30 jours sous-estime les créatrices** : les pages de Sarah et de Clara n'existent que depuis le 27-28/09. **Et il sous-estime les clippers** : les liens supprimés pendant la période (sortants, clones d'Andry) ne sont plus listés. Le 7 jours est le chiffre juste ; il dit que les clippers sont passés de 24 % à 32 % du trafic en trois semaines, pendant que le Metricool est passé de 25 % à 11 % (référence : [[Rapport GAML - d'où vient le trafic, créatrice par créatrice (16 septembre 2026)|le rapport GAML du 16/09]]).

## 2. Ce qui bouge : la semaine contre la moyenne du mois

Chaque lien comparé à sa moyenne hebdomadaire sur 30 jours (liens de plus de 250 visiteurs en 30 jours), courbes jour par jour relues pour les cas extrêmes.

| En chute | Écart | Depuis quand |
|---|---|---|
| Tara (clipper Sarah) | −98 % | 28/09, le jour où le lien est passé « en story à la une seulement » (voir [[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)|les règles des liens]]) |
| Hugo (clipper Maddie, hors roster) | −97 % | depuis fin septembre |
| Facebook Maddie | −89 % | |
| Ckycia (sortie le 05/10) | −88 % | |
| Metricool Sophie 2 | −68 % | 30/09 |
| Metricool Maddie (Rianah) | −68 % | 05/10 (743 et 543 visiteurs les 29-30/09, 18 le 07/10) |
| Facebook Sophie | −67 % | |
| Metricool Sophie (page racine) | −49 % | 02/10 |
| Metricool Julien (Chloé) | −48 % | |
| Lilian (clipper Chloé) | −38 % | 30/09 |
| Compte de Chloé | −37 % | creux du 30/09 au 03/10, remonté à 400-700 par jour du 04 au 07/10 |

| En hausse | Écart |
|---|---|
| Clarisse (clipper Sarah) | +271 %, de 23 à 144 visiteurs par jour du 01 au 07/10 |
| **Hasina (sortie le 05/10)** | **+265 %** : son lien tourne encore, 301 visiteurs cette semaine |
| Compte de Sarah | +173 % (page créée le 28/09) |
| Romaric (clipper Chloé) | +169 % |
| Compte de Maddie | +165 % |
| Compte de Clara | +153 % (page créée le 27/09) |
| Yves (clipper Sarah) | +100 % |
| YouTube Maddie, Sophie | +97 %, +50 % |

**Concentration** : Caroline, Josué, Yves et Clarisse font 73 % du trafic des clippers (2 848 sur 3 902), les mêmes qu'au [[Rapport détaillé par clipper - Caroline, Yves, Ckycia, Josué, Lilian (5 octobre 2026)|rapport détaillé du 05/10]] : quatre anciens de l'équipe de Jonas. Josué tire 46 % de ses visites de Facebook et 12,5 % d'une autre page de destination ; Caroline 90 % d'Instagram. Les douze autres liens de clippers actifs font moins de 10 visiteurs par semaine chacun : ce sont surtout nos propres ouvertures de contrôle du 02/10.

## 3. MyPulse : les abonnés que GAML ne voit pas

Export MyPulse du 01 au 08/10 (MYM seulement, OnlyFans passe par Infloww), nouveaux abonnés du 02 au 08/10, mis en face des visiteurs GAML de la même semaine :

| Créatrice | Visiteurs GAML | Nouveaux abonnés MYM | Abonnés pour 100 visiteurs |
|---|---|---|---|
| Chloé | 4 551 | 308 | 6,8 |
| Sarah | 3 714 | 413 | 11,1 |
| Maddie | 2 097 | 76 | 3,6 |
| **Sophie** | 1 256 | **1 243** | **99** |
| Jade | 289 | 152 | 53 |
| Clara | 342 | 76 | 22 |

Pour Chloé, Sarah et Maddie, les visites expliquent les abonnés (avec OnlyFans en plus, non compté ici). **Pour Sophie, Jade et Clara, non** : Sophie passe de 2 nouveaux abonnés le 01/10 à 352 le 02/10, 298 le 03, 205 le 04, avec un chiffre d'affaires d'abonnement d'environ 0,20 € par abonné : une promo, arrivée **le jour même où les visites de ses liens Metricool décrochent**. Hypothèse probable, à confirmer par Gaëtan : un lien MYM direct (promo) a remplacé GAML dans les bios de Sophie le 02/10. Si c'est vrai, la part « créatrices contre nous » en visites sous-estime l'agence pour Sophie, et le moteur Metricool n'a pas perdu son public, seulement son compteur.

## 4. Où ça coince : le parcours du clipper

Grille [[Théorie des contraintes]] : le débit du moteur clippers de [[LTP Models]], ce sont des clippers qui publient avec leur lien en bio. Le goulot n'est pas le recrutement (19 candidatures en 7 jours, 11 le 07/10) ni Instagram : c'est le passage **signé → compte 1 créé → lien en bio**, où le bot perdait les gens.

**Ce que vit un nouveau aujourd'hui** (audit du code, 08/10) : premier Reel au mieux 24 h 20 après le J'ACCEPTE, 25 à 26 h en pratique ; lien en bio du compte 3 au mieux à J+4, vers J+6 en pratique (48 h et 4 Reels par compte, mesurés par un seul scan Instagram par jour) ; 6 messages du bot avant le premier Reel, 14 jusqu'à la routine. **Conséquence directe : un nouveau ne ramène aucun visiteur traçable pendant ses 4 à 6 premiers jours**, même si un Reel du compte 1 perce (Mohamed le 05/10 : « un poste qui vient de percer », aucun lien nulle part).

Les pannes trouvées, toutes confirmées dans le code ou dans les messages du bot :

| Panne | Qui | Effet | Le 08/10 |
|---|---|---|---|
| Recherche du membre sur le pseudo entier (« Yves » ≠ « Yves - Sarah ») | Caroline, Lilian, Josué, Yves, Romaric, Lucas, Tara, Clarisse (les anciens de l'équipe de [[Fiche de poste - Manager marketing (Jonas)|Jonas]]), puis Jonas et Julien | 8 anciens sur 9, les plus productifs, sans salon, sans logins, sans app ; jamais retentés | corrigé, rouverts au démarrage |
| Le « pavé » : la boucle « lien manquant » renvoyait les 3 comptes d'un coup, le compte 3 « il publie », le lien sans consigne | tout nouveau, 15 min après l'étape 1 (Mohamed deux fois) | « un compte à la fois » annulé, comptes créés dans le désordre, sans les boutons | corrigé |
| « Profil fait » oublié | tout clipper | parcours figé sans un mot | fermé seul après 6 h |
| Bouton WhatsApp : « ?text= » ajouté au lien court WhatsApp Business | tous (Mathieu) | WhatsApp ouvre le choix d'un contact | corrigé, et bouton « J'ai écrit à Gaëtan » |
| Appel de présence : la copie de l'état lue avant les envois était réécrite après | ceux qui répondaient vite | réponse effacée, sortie 48 h plus tard « sans réponse » | corrigé (bug reproduit puis réparé) |
| Sortie « compte 1 pas créé » sur le seul bouton | Mohamed, qui publiait | averti le 07/10, expulsion prévue le 08/10 | le scan vaut le bouton |
| Deux règles : « 3 jours » annoncé, purge à 48 h sans prévenir | tous | expulsion surprise | une règle, 48 h, avertissement obligatoire |
| Identifiant prévu déjà pris, variante inconnue du bot | Mohamed | scan aveugle, compte suivant bloqué | `!pseudo 1 identifiant` |
| Paie « 0,00 $, `!wallet` maintenant » | nouveaux | bruit, peur de ne pas être payé | supprimée |
| Base de l'assistant : 2 ou 4 Reels, bikinis « interdits », « chiffre chaque matin » | tous | l'assistant se contredit trois fois en trois messages | alignée |
| L'app clippers n'était envoyée à personne | tous | `!mesclics` tapé en boucle (Simon : 8 fois en 3 jours) | envoyée seule après les 3 comptes |

## 5. Ce qui a été livré le 08/10

1. **L'app part toute seule** dans le salon perso dès que l'étape du compte 3 est fermée, avec le lien GAML et les gestes pour l'écran d'accueil, sans rien à configurer : l'app écrit « clipper → lien de l'app » dans son tableur d'usage, le bot le lit (vérifié en ligne : 29 clippers écrits). `!app` pour la renvoyer. Détail : [[App clippers - une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)]].
2. **Les pannes du tableau** ci-dessus, en quatre lots poussés sur GitHub (Railway redéploie seul), trois jours après la refonte de l'[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)|audit du 05/10]] dont plusieurs pannes sont des effets de bord. Détail technique dans le README du bot, section « Checkup du 08/10 ».

## 6. À trancher par Gaëtan

| Décision | Ma recommandation |
|---|---|
| **Metricool −54 % en une semaine** : lien de bio changé, comptes restreints, ou temps de Rianah passé au clipping ? | Vérifier les bios des comptes Metricool de Sophie et Maddie aujourd'hui ; si un lien MYM direct a remplacé GAML, le remettre derrière un lien GAML avec son tracking MyPulse, sinon on pilote à l'aveugle |
| **Le compte privé en 2e position** au lieu de 3e | Oui : le lien existe à J+2 au lieu de J+5-6, les Reels du compte 1 ont enfin une destination ; le compte privé ne publie pas, il ne change rien au rythme anti-ban d'un compte tous les 48 h |
| **Un 2e scan Instagram à 19 h** pour les seuls comptes en attente | Oui (quelques dizaines de profils, coût Apify faible) : un jour gagné par compte, soit 2 jours sur les trois |
| « **Tu es au fixe** » dit par `!mesclics` aux inscrits d'avant le 24/09 (Simon, Yves) alors que l'app leur affiche une paie au clic | Tout le monde au clic sauf Rianah (`!paie @x clic`), comme le prévoit la [[Machine horizontale v2 - paie au clic, ce que les clippers rapportent (23 septembre 2026)|paie au clic]] ; sinon l'app ment |
| **Lien d'Hasina** (sortie, 301 visiteurs cette semaine) | Le garder actif et savoir qui publie ; si c'est elle, décider de la payer au clic plutôt que de perdre ce trafic (voir la [[Rentabilité des clippers de Jonas, de Jonas et de Julien - paie de septembre (5 octobre 2026)|rentabilité de septembre]]) |
| **Forfait GAML** : 48 liens actifs sur 50 | Supprimer les liens morts des sortants (Eddy, Steeve, Ricado, LATE2, Mie02, Mathias, Georgial, Antoinr, Andry ×2 : 1 à 6 visiteurs chacun, nos propres clics) avant la vague malgache |
| **Questions dans #assistant seulement** (GO 2) | À revoir avec l'audit de l'assistant : le salon perso muet perd les clippers (Mohamed : « pourquoi vous ne me répondez plus ? ») |
| **Export MyPulse par lien de tracking** | Le demander une fois par semaine : c'est lui qui dit qui ramène des abonnés, pas les visites |

## 7. Avocat du diable

- **Des visiteurs ne sont pas des abonnés.** La part « 51 % agence » est une part de visites ; la section 3 montre qu'elle ne suit pas les abonnés pour la moitié des créatrices. Conclure « les clippers font la moitié du chiffre » serait faux.
- **Les correctifs sont poussés, pas observés.** Je n'ai pas accès aux journaux Railway : les salons des anciens, l'envoi de l'app et la fin des sorties à tort se vérifient demain dans #bot-gaetan (`!roster`, `!audit`, `!appel`).
- **Le bouton « J'ai écrit à Gaëtan » est déclaratif** : un clipper peut mentir. Le prix est faible (une relance en moins) et Gaëtan est prévenu à chaque appui.
- **La fermeture automatique du profil** fait avancer un clipper qui n'a peut-être pas mis sa photo ni sa bio : un compte sans profil vit moins longtemps. Six heures laissent le temps de le faire ; à surveiller dans les bans.
- **48 h pour le compte 1** sortira aussi des gens de bonne foi (Mohamed a eu trois jours de coupure internet). L'avertissement à 24 h et la preuve du scan limitent le risque, sans l'annuler.
- **CGU Instagram** : trois comptes par personne, du contenu repris d'une même créatrice et des comptes « repris » d'un sortant, c'est le cœur du comportement non authentique que l'Instagram sanctionne. La dette est connue ; ce checkup ne la réduit pas, il évite seulement d'y ajouter des erreurs du bot.

## 8. Prédictions (écrites le 08/10, avant observation, reprises au [[Journal de coaching]])

- D'ici le 15/10, au moins 6 des 8 anciens rouverts ont leur salon et ont reçu leur app (onglet « Liens app », `!audit`) — 75 %.
- Sur la semaine du 09 au 15/10, la part agence reste entre 45 et 55 % des visiteurs GAML — 60 % ; sans action sur le Metricool, sa part tombe sous 8 % — 65 %.
- Aucune sortie automatique contestée (clipper qui publiait) d'ici le 20/10 — 70 %.
