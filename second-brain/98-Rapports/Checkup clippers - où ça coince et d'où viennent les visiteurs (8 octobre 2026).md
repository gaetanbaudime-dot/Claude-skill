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
> **La moitié des visiteurs GetAllMyLinks vient de nous, l'autre moitié des comptes des créatrices. Mais le goulot n'est ni Instagram ni le contenu : c'est le bot lui-même, qui cassait le passage « signé → compte créé → lien en bio ».** Sur 7 jours (02 au 08/10), 12 249 visiteurs : **49 % comptes des créatrices, 51 % agence** (clippers 32 %, Metricool 11 %, Facebook et YouTube 8 %). Huit des neuf anciens les plus productifs n'avaient pas de salon, les nouveaux recevaient leurs trois comptes d'un coup, un oubli de bouton figeait le parcours, le bouton WhatsApp ouvrait le mauvais écran, des réponses à l'appel étaient effacées, et un clipper qui publiait allait être expulsé. **Tout est corrigé et poussé le 08/10 (cinq lots).** Deux alertes restent pour cette semaine : **le moteur Metricool a perdu 54 % de ses visites en une semaine**, et **les abonnés MYM de Sophie, Jade et Clara arrivent surtout hors GAML**. La vraie part « créatrices contre nous » se tranche avec l'export MyPulse par lien de tracking, pas avec les visites. **Les cinq décisions du 08/10 sont en place le jour même** (privé en 2, scan du soir, paie au clic sauf sept fixes, ménage GAML par désactivation, comptes d'Hasina sur Metricool) : section 6.

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

## 6. Tranché par Gaëtan le 08/10, et en place le jour même

> [!important] Mise à jour du 09/10 : deux décisions revues par Gaëtan
> **Paie** : « tout le monde passe au clic depuis le 5 octobre, sauf Rianah, Caroline, Lilian, Josué et Yves qui restent au fixe » : un ancien fixe est payé au clic à partir du 05/10 (et non du 08/10), dans le bot comme dans l'app. **Compte privé** : « garde-le en 3e position et fais-le créer uniquement si le clippeur publie bien sur les deux premiers comptes » : le privé en 2 est annulé (seuls les parcours dont le privé était déjà ouvert le gardent), et le compte 3 privé ne s'ouvre que 48 h après le compte 2, quand le scan voit 4 Reels sur le compte 2 et 4 Reels de plus sur le compte 1. Le lien arrive donc à J+4 au plus tôt, mais seulement chez un clipper qui publie vraiment. **@ changés** : le bouton « Compte créé » demande le @ exact, et le scan retrouve un compte créé sous un @ proche (nom et bio donnés par le bot) au lieu de le passer BAN.
>
> **Julien** (même jour) : « Julien arrête tout, il va juste faire le monteur vidéo maintenant pour moi ». Il sort du clipping par `!monteur @Julien` (par son identifiant Discord : un nouveau Julien clipper est signé), sans message ni expulsion ; « julien » sort de la liste des fixes. Détail et prédictions : [[Journal de coaching]], entrée « 2026-10-09 (Julien) ».

> [!warning] Correction de ma propre recommandation
> J'avais écrit « supprimer les liens morts des sortants ». **C'était une erreur** : un lien libéré garde la carte et le tracking MYM de sa créatrice, et le bot le redonne au clipper suivant. L'effacer détruisait la réserve de liens réutilisables et forçait des clones. La bonne version, en place : **désactiver** (un lien désactivé ne compte pas dans le forfait), **jamais effacer**, et réactiver à la reprise.

| Décision | Tranché | Ce qui tourne depuis le 08/10 |
|---|---|---|
| **Compte privé en 2e position** | GO le 08/10, **annulé le 09/10** (privé en 3, seulement si les comptes 1 et 2 publient) | Nouveaux parcours : compte 1 croissance, **compte 2 privé avec le lien**, compte 3 croissance. Le lien existe à J+2 ; le compte 3 s'ouvre 48 h après le privé, à 4 Reels de plus sur le compte 1. Ceux dont le compte 2 était déjà ouvert gardent le privé en 3. |
| **2e scan Instagram à 19 h** | GO | Seuls les comptes dont les Reels ouvrent un compte en attente sont relus le soir ; le compte suivant s'ouvre le soir même s'ils ont leurs Reels. Le scan du soir n'écrit ni le classeur ni l'historique (pas de double compte). |
| **Paie** | « Tout le monde au variable sauf Caroline, Lilian, Josué, Yves et Rianah. Julien montage YouTube, Jonas manager » | Ces sept prénoms au fixe, tous les autres au clic. **Mon choix par défaut, à valider** : un ancien passé du fixe au clic est payé au clic **à partir du 08/10**, sa quinzaine d'avant reste au fixe (jamais payé deux fois). L'app affiche « au fixe » aux sept, et compte la même période que le bot. |
| **Forfait GAML** | « Combien coûte le supérieur ? On fait le ménage » | Paliers Agency : 10, 25, 50, 100 liens, puis sur devis à partir de 400. **Seul le palier 10 liens a un prix public : 29 $/mois** (−20 % à l'année) ; le prix du palier 100 n'est publié nulle part, il se demande au support sur Telegram. Ménage automatique chaque matin : un lien libéré sous 15 visiteurs en 7 jours est désactivé, réactivé pour le suivant ; les liens de clippers partis sans libération (orphelins) sont rattrapés. Résultat le 08/10 au matin : **8 liens morts désactivés** (3 par le bot : Eddy, Hugo, le 2e Andry ; 5 à la main après vérification des notes et des visites, pour les expulsés du 07/10 que le bot croyait encore rattachés : Mie02, LATE2, Mathias, Antoinr, Ghislain) → **41 liens actifs sur 50**. Restent actifs, faute de preuve de départ : Steeve, Ricado (doublon de Ricardo), Georgial, Stéphane, le 1er Andry. |
| **Comptes d'Hasina** | Sur Metricool, gérés par Rianah. « Rianah = Metricool désormais » | Note GAML du lien d'Hasina changée en « Rianah Metricool 3 (ex-Hasina) » : le bot le détache du clipping (plus compté pour un clipper, jamais redonné). |
| **Metricool −54 % en une semaine** | ouvert | Vérifier les bios des comptes Metricool de Sophie et Maddie ; un lien MYM direct à la place de GAML = pilotage à l'aveugle. |
| **Questions dans #assistant seulement** (GO 2 du 06/10) | ouvert | L'audit de l'assistant recommande de remettre l'IA dans le salon perso (`ASSISTANT_SALON_PERSO=1`) : #assistant est le salon où elle en sait le moins. |
| **Export MyPulse par lien de tracking** | ouvert | Une fois par semaine : c'est lui qui dit qui ramène des abonnés. |

**Le forfait, chiffré** : 48 liens actifs ce matin, **41 après le ménage**, dont environ 19 hors clipping (pages des créatrices, Facebook, YouTube, Metricool). Neuf places libres, soit neuf nouveaux clippers sans changer de palier, plus les liens libérés que le bot réactive pour les suivants ; le nouvel ordre ne crée pas plus de liens (un par clipper, comme avant). **Recommandation : ne pas monter de palier aujourd'hui, mais demander le prix du palier 100 au support cette semaine**, parce que la vague malgache prévue par Jonas (50 à 100 clippers) le rendra obligatoire, et un clone refusé, c'est un clipper sans lien, donc sans app et sans paie.

## 6 bis. Ce que les audits de l'assistant et le critique de complétude ont ajouté (corrigé le 08/10)

- **Le lien du compte privé n'était pas cliquable** (trouvé en relisant le message de profil) : le bot faisait coller le lien GAML **dans le texte de la bio**, où Instagram ne rend aucune adresse cliquable. Un privé « avec son lien » pouvait n'envoyer personne, ce qui colle avec les deux indices du critique (Lucas : 69 419 vues pour 86 visiteurs en 30 jours ; Tara : −98 % le jour où son lien est passé « story à la une seulement »). Le profil, l'étape du lien et la base disent maintenant « Modifier le profil → Liens → Ajouter un lien externe ». **Et le lien est vérifié chaque matin** par le scan (champ « Liens » du profil privé, visible même en privé) : absent 24 h après la création du privé → le clipper est prévenu dans son salon, l'admin aussi. Statut : probable, pas confirmé — le scan dira dès demain combien de privés n'ont pas leur lien cliquable.

- **Expulsions impossibles à éviter** : un clipper sans aucun compte livré (vivier vide) ou dont le compte 1 a été banni à la création sortait pour « compte 1 pas créé ». Il ne sort plus ; le salon admin reçoit « 🧱 à débloquer ».
- **La liste des bloqués arrivait après l'expulsion** : l'étape 1 n'y apparaissait qu'à plus de 2 jours, la sortie tombe à 48 h. Elle y est dès le 1er jour.
- **Les fiches des expulsés étaient effacées** : la trace du parcours (étape, dates) est gardée à la sortie, l'entonnoir par étape redevient mesurable.
- **L'assistant de #assistant mélangeait les clippers** : la réponse faite à l'un arrivait au modèle comme « ce que je t'ai dit » au suivant. Corrigé ; les anciens hors registre ne sont plus traités en candidats ; `!aide` reconnaît le rôle Clippeur ; le salon des codes a son lien cliquable.
- **La base de connaissances se contredisait une quinzaine de fois** : réécrite en v16 (une version de chaque règle).
- **Revue adversariale du code du jour** (trois relecteurs, un sceptique par trouvaille) : **19 bugs confirmés, tous corrigés le 08/10**, dont un bloquant (avec le privé en 2, un compte 1 banni pendant l'attente figeait le parcours sans alerte), une double paie possible après `!paie`, une app qui devinait le régime au lieu de le lire, et un clipper débloqué qui pouvait sortir 24 h après avoir reçu ses comptes.
- **Restent ouverts** (critique de complétude) : le seul instrument d'entonnoir (`!tableau`) est faux par construction, la source des candidats n'est pas tracée, et le bot reçoit plus de commits qu'on ne l'observe — un gel des fonctionnalités d'une semaine serait sain.

## 7. Avocat du diable

- **Des visiteurs ne sont pas des abonnés.** La part « 51 % agence » est une part de visites ; la section 3 montre qu'elle ne suit pas les abonnés pour la moitié des créatrices. Conclure « les clippers font la moitié du chiffre » serait faux.
- **Les correctifs sont poussés, pas observés.** Je n'ai pas accès aux journaux Railway : les salons des anciens, l'envoi de l'app et la fin des sorties à tort se vérifient demain dans #bot-gaetan (`!roster`, `!audit`, `!appel`).
- **Le bouton « J'ai écrit à Gaëtan » est déclaratif** : un clipper peut mentir. Le prix est faible (une relance en moins) et Gaëtan est prévenu à chaque appui.
- **La fermeture automatique du profil** fait avancer un clipper qui n'a peut-être pas mis sa photo ni sa bio : un compte sans profil vit moins longtemps. Six heures laissent le temps de le faire ; à surveiller dans les bans.
- **48 h pour le compte 1** sortira aussi des gens de bonne foi (Mohamed a eu trois jours de coupure internet). L'avertissement à 24 h et la preuve du scan limitent le risque, sans l'annuler.
- **Le privé en 2 rend le compte 3 dépendant du seul compte 1** : si le compte 1 est banni pendant l'attente, le compte 3 ne s'ouvre plus (aucun Reel ne peut arriver). L'alerte « bloqué par un BAN » existe, c'est Gaëtan qui débloque.
- **Le paiement des anciens au clic à partir du 08/10** est mon choix par défaut ; si leur dernier fixe ne couvrait pas le début d'octobre, ils perdent une semaine de visites. À confirmer avant la paie du 20/10.
- **CGU Instagram** : trois comptes par personne, du contenu repris d'une même créatrice et des comptes « repris » d'un sortant, c'est le cœur du comportement non authentique que l'Instagram sanctionne. La dette est connue ; ce checkup ne la réduit pas, il évite seulement d'y ajouter des erreurs du bot.

## 8. Prédictions (écrites le 08/10, avant observation, reprises au [[Journal de coaching]])

- D'ici le 15/10, au moins 6 des 8 anciens rouverts ont leur salon et ont reçu leur app (onglet « Liens app », `!audit`) — 75 %.
- Sur la semaine du 09 au 15/10, la part agence reste entre 45 et 55 % des visiteurs GAML — 60 % ; sans action sur le Metricool, sa part tombe sous 8 % — 65 %.
- Aucune sortie automatique contestée (clipper qui publiait) d'ici le 20/10 — 70 %.
- Avec le privé en 2, le délai médian « compte 1 créé → lien en bio » passe sous 3 jours pour les parcours ouverts après le 08/10 (contre 5 à 6) — 70 %.
- Le ménage libère au moins 8 places GAML d'ici le 10/10 sans couper un lien qui ramène des visiteurs — 75 %.
- Le premier contrôle du matin trouve au moins un tiers des comptes privés existants sans lien cliquable (lien collé dans le texte de la bio, ou absent) — 60 %.
