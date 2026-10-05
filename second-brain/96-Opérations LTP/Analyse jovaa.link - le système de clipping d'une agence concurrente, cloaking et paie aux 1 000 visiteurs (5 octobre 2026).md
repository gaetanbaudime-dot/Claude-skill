---
titre: "Analyse jovaa.link - le système de clipping d'une agence concurrente, cloaking et paie aux 1 000 visiteurs (5 octobre 2026)"
type: décision
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-05
tags: [ops/clipping, ops/cgu, ops/trafic, ofm/risques, ops/outils]
liens_forts: ["[[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]]", "[[Analyse annabeatse.com - le pont neutre à deux sauts devant OF-MYM (5 octobre 2026)]]", "[[Continuité du bot et paie sacrée (plan anti-panne)]]", "[[Programme clipping public (analyse concurrents + plan septembre)]]", "[[Journal de coaching]]"]
---

# Analyse jovaa.link - le système de clipping d'une agence concurrente, cloaking et paie aux 1 000 visiteurs (5 octobre 2026)

> [!tip] Verdict
> `jovaa.link/ambretonyy` n'est pas une page de créatrice, c'est **un lien de clipper mort** (« Page introuvable » pour un humain) dans l'outil maison d'une agence concurrente, « Jovany Agency », qui fait exactement notre métier : des clippers, un lien de suivi par clipper, une page d'atterrissage par lien, une école en ligne, un bot Telegram, une paie automatisée. Trois choses à retenir. **Un** : leur page sert une fausse vitrine lifestyle aux robots de Meta et de Google (2 Ko) et la vraie page aux humains (55 Ko), avec une deuxième détection côté client : c'est le cloaking mot pour mot que notre plan du 02/10 a décidé de couper ; ça ne protège pas plus que notre shield, ça documente l'infraction. **Deux** : ils paient leurs clippers **aux 1 000 visiteurs uniques par plateforme** (Instagram 4 $, TikTok 3 $, YouTube 5 $), pas au clic : une base plus difficile à gonfler que la nôtre, à chiffrer sur nos propres liens GAML (visiteurs hors robots contre clics) avant le passage au variable. **Trois** : leur base de données se lit sans mot de passe depuis n'importe quel navigateur ; la nôtre est derrière un compte de service et des jetons, on garde ça.

## 1. Ce qu'il y a derrière l'adresse [C]

Vérifié le 05/10 au matin : page téléchargée avec sept identités (iPhone, Android dans Instagram, Chrome Windows, curl, robot Facebook, robot Meta, robot Google), scripts du site lus, et la même requête de base de données que celle que la page exécute.

| Identité du visiteur | Ce que le serveur renvoie |
|---|---|
| iPhone, Android dans l'app Instagram, Chrome Windows, curl | la vraie page, 55 Ko : avatar avec point vert « En ligne », badge « Profil vérifié », galerie ou fond façon story avec barre de progression, bouton « Cliquer pour voir la suite », compte à rebours « Gratuit pendant 14:59 · Offre limitée » |
| robot Facebook, robot Meta, robot Google | une page de 2 Ko : avatar 🌸, « Mon univers ✨ », « Passionnée de photo, voyage et lifestyle ✈️ », trois boutons Instagram / Mon site / Me contacter qui ne mènent nulle part (`href="#"`) |

Dans la vraie page, un second filet : une liste d'une quarantaine de robots (Facebook, Meta, Twitter, LinkedIn, Slack, Google, Bing, Discord, Telegram, WhatsApp, Pinterest, Snapchat, Reddit, ByteDance…) reconnus à l'identité du navigateur, à qui la page affiche un texte générique et un bouton sans destination. C'est **l'inverse** de ce que fait le pont neutre d'[[Analyse annabeatse.com - le pont neutre à deux sauts devant OF-MYM (5 octobre 2026)|annabeatse.com]], qui sert la même page à tout le monde.

Le reste du mécanisme, lu dans le code :

- **Le bouton** : premier clic = « Êtes-vous majeur ? Cliquez pour entrer » (compté comme « confirmation 18+ »), second clic = départ vers l'adresse OnlyFans du modèle (ou `onlyfans.com/<slug>` par défaut). Pas d'écran 18+ à part : la majorité se « confirme » sans question posée.
- **Le compte à rebours** repart à 14:59 à chaque visite (899 secondes codées en dur) : fausse rareté, et « Gratuit » est un signal de prix, les deux interdits par les règles de Meta vérifiées le 02/10.
- **Le pixel maison** relève empreinte du navigateur (agent, langue, écran, fuseau, cœurs, points de contact), pays, source (Instagram, TikTok, YouTube, Snapchat, X, Telegram, Facebook, Discord, Reddit), UTM, défilement, clics, rebond, et l'envoie dans leur base. Aucun bandeau de consentement : dette RGPD chez eux.
- **Navigateur intégré** : si la page s'ouvre dans Instagram, une invite « Ouvrez dans Safari : appuyez sur ••• puis Ouvrir dans le navigateur » avec un bouton « Copier le lien ». Pas de sortie automatique comme GAML.
- **Marchés** : français par défaut, anglais si le modèle est marqué « US » (« Tap to see more », « Free for », « Limited offer »).
- **Le lien testé est mort** : aucun clipper dans leur base ne porte l'identifiant `ambretonyy` ; un humain voit « Page introuvable ». Leur propre code parle d'un « audit du 02/10 : 109 faux lp en base », des liens créés avec des fautes de frappe ou des espaces, rattachés à aucun clipper. Les mêmes liens morts que nos 48 du 02/10.

## 2. L'outil derrière : une agence de clipping comme la nôtre [C]

Le site est l'outil maison de l'agence (commentaires de code en français signés « KENTOOLS »), hébergé sur Netlify avec une base Firebase. Ses pages sont téléchargeables sans connexion ; leurs libellés décrivent toute l'organisation :

| Chez eux | Chez nous |
|---|---|
| Tableau de bord « CEO », vue « Responsable », vue « Manager », vue « Rapporteur clippeur » (lecture seule des visiteurs uniques) | Discord : Gaëtan, Jonas, les managers, le bot |
| Modèles : nom, slug, URL OnlyFans, groupe Telegram, marché FR/US, « modèle jumeau » | Créatrices dans Data G&M et dans GAML |
| Liens de suivi et pages d'atterrissage par clipper (slug, nom affiché, accroche, plusieurs boutons, langue) | un lien GAML cloné par clipper, bio et libellés alignés par le bot |
| « Mes stats » pour le clipper par jeton d'invitation : visiteurs uniques, clics, confirmations 18+, CTR, classement, tendance 7 jours, top pays, moyen de paiement, facturation par période close | rapports du bot dans le salon du clipper, `!paiement`, paie sacrée |
| **Paie = (visiteurs uniques ÷ 1000) × taux de la plateforme** : Instagram 4 $, TikTok 3 $, YouTube 5 $ ; « c'est cette métrique qui détermine votre paie » | paie indexée sur les clics GAML (`paie_clics`), passage au variable le 05/10 |
| Entonnoir mesuré en quatre marches : visite de la page → clic sur le bouton → arrivée sur la page de redirection → clic sur le lien final | visiteurs GAML, clics, puis abonnés dans Data G&M |
| « École » : cours par blocs (titre, texte, image, vidéo) et questionnaire, vue « student » | parcours d'onboarding et quiz dans Discord |
| « Recrutement en cours », « À relancer (aucun progrès depuis 7 jours) », « Clippers inactifs : 0 visite sur la période », alertes automatiques Telegram | roster actif, compteur, rapport Jonas |
| « Qualité subs (OF) », « IG Tracking : vues et vélocité », « Social Analytics », comptes réseaux sociaux | classeur des logins, `!classeur`, détecteur de bans, Metricool |
| Paie clippers, historique des paiements, paie management, mentions légales | `!paiement`, Wio, le pacte |

Ce qu'ils ont et que nous n'avons pas : la paie aux visiteurs uniques par plateforme, une page « Mes stats » lisible par le clipper sans passer par Discord, l'entonnoir en quatre marches, le marché US. Ce que nous avons et qu'ils n'ont pas (d'après ce qui est visible) : MYM, la règle d'un compte tous les 48 h et le détecteur de bans par mail, la sortie automatique du navigateur Instagram, le code 2FA partagé, l'avis automatique sur le test de montage.

## 3. Ce qu'on copie, ce qu'on ne copie pas

**On chiffre avant de copier la paie aux visiteurs uniques.** GAML donne déjà les visiteurs hors robots par lien (c'est ce que lit le module Telegram des visites). Avant le passage au variable du 05/10 : sortir pour chaque lien de clipper actif les clics et les visiteurs uniques des 30 derniers jours ; si l'écart dépasse 30 % sur une part notable des liens, la paie au clic rémunère du bruit (revisites, robots, clics répétés) et la base « visiteurs uniques hors robots » est plus juste et plus difficile à gonfler, dans l'esprit du plan anti-Goodhart de [[Continuité du bot et paie sacrée (plan anti-panne)]]. Le taux par plateforme (YouTube payé plus qu'Instagram) est une idée à garder si les abonnés par visiteur diffèrent vraiment par source, ce que Data G&M ne sait pas encore dire.

**On copie l'idée d'une page « Mes stats » par clipper**, à bas coût : l'[[App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)|app créatrices]] a déjà le modèle (un lien secret, des chiffres lus en direct) ; la même base peut servir une vue clipper (visiteurs du jour, 7 jours, 30 jours, classement) quand le variable sera en place et que les chiffres seront propres.

**On ne copie pas** : le cloaking (les deux couches), le faux « En ligne », le faux « Profil vérifié », le compte à rebours, la confirmation 18+ déguisée en double clic, le pixel à empreinte sans consentement, les liens morts qui restent en ligne. Et on ne copie surtout pas leur base de données ouverte : n'importe qui peut lire leurs modèles et leurs liens depuis un navigateur ; la nôtre reste derrière un compte de service et des jetons.

## 4. Avocat du diable [P]

- **Ils tournent peut-être très bien avec tout ça.** Rien ne dit que leur cloaking leur coûte des comptes ; notre propre expérience (la moitié des comptes à l'orange avec shield, l'autre moitié jamais) dit seulement qu'il ne protège pas, pas qu'il tue. Le refus du cloaking chez nous est une décision de risque et de principe, pas une preuve de rendement.
- **Les 1 000 visiteurs uniques se gonflent aussi** : une empreinte de navigateur change avec un mode privé ou une autre connexion. Plus dur que le clic, pas inviolable ; la vraie base reste l'abonné, que nous mesurons et pas eux (rien d'OF dans leur entonnoir au-delà du clic final, à part « Qualité subs (OF) »).
- **Tirer des conclusions d'un lien mort** : la page que Gaëtan a vue est l'état d'erreur ; ce que voient leurs vrais visiteurs est reconstitué depuis le code et les pages du site, pas observé sur un lien vivant.
- **Lire leur base** : une seule requête, celle que la page exécute elle-même, pour savoir si le lien était vivant. Rien d'autre n'a été lu ni enregistré, et rien de leur base n'entre dans ce vault.

## Prédictions (05/10, revue le 12/10)

- Sur nos liens de clippers actifs, l'écart entre clics et visiteurs uniques hors robots sur 30 jours dépasse 30 % pour au moins un lien sur quatre (55 %).
- `jovaa.link/ambretonyy` affiche encore « Page introuvable » le 12/10 (80 %).
- Leur page conserve le cloaking par identité du navigateur le 12/10 (85 %).

Le classement des pages concurrentes est dans [[Liens Instagram vers OF-MYM - règles, vague de septembre et plan (2 octobre 2026)]] (section 4), les programmes de clipping publics dans [[Programme clipping public (analyse concurrents + plan septembre)]], la décision et ses prédictions dans le [[Journal de coaching]] (entrée du 5 octobre 2026).
