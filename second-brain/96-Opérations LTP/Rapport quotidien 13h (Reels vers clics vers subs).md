---
titre: "Rapport quotidien 13h (Reels vers clics vers subs)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-30
tags: [ops/clippers, ops/reporting, ops/automatisation]
liens_forts: ["[[Reporting clippers]]", "[[Machine Instagram-Facebook en masse]]", "[[Atterrissage du funnel (mesure propre avant optimisation)]]"]
---

# Rapport quotidien 13h — Reels → clics → subs

> [!tip] Verdict
> Tu recevais un rapport qui mesurait le **milieu** de la chaîne (les clics) sans le **début** (les Reels publiés) ni la **fin** (les subs). Conséquence : un clipper qui publie 12 Reels qui flopent et un clipper qui ne publie rien étaient **strictement identiques** dans ton rapport. Tu ne pouvais pas piloter la discipline, seulement constater le trafic. Ce rapport ferme la chaîne : **chaque matin à 13h**, un message Telegram te dit qui a publié quoi, ce que ça a généré en clics, et combien de subs en sont sortis. La seule question qu'il répond, et c'est la bonne : **quel maillon casse aujourd'hui ?**

## La chaîne, et pourquoi elle seule compte

```
Reels publiés  →  clics  →  subs OF/MYM
   (Apify)        (GAML)    (Sheet, saisi par Rianah)
```

Trois maillons, trois diagnostics **mutuellement exclusifs**. Le rapport en choisit un et un seul, par ordre de gravité :

| Ce que tu lis | Ce que ça veut dire | Où est le goulot |
|---|---|---|
| 🔴 **Chaîne à l'arrêt** — 0 Reel | Personne ne publie. Rien d'autre ne compte. | La production |
| 🔴 **Maillon cassé Reels → clics** — des Reels, 0 clic | Le contenu sort mais le lien en bio n'est pas là, ou personne ne clique | Le CTA / la bio |
| 🔴 **Maillon cassé clics → subs** — des clics, 0 sub | Le trafic arrive, la page de vente ne convertit pas | La landing / la créatrice |
| ⛓️ **Chaîne** — X Reels → Y clics → Z subs | Tout tourne, on lit les ratios | Le rendement |

C'est directement la [[Théorie des contraintes|grille du goulot]] appliquée à ton funnel : **optimiser un maillon qui n'est pas le goulot, c'est du confort déguisé en travail**. Si personne ne publie, retravailler les bios ne sert à rien. Le rapport t'empêche de te tromper de chantier.

## Les deux ratios qui disent si la machine convertit

- **Clics par Reel** — le rendement de la distribution. Un Reel qui ne génère aucun clic est un Reel qui a coûté 5 minutes de montage pour rien.
- **Subs pour 100 clics** — le rendement de la conversion. C'est le chiffre qui dit si ton trafic vaut quelque chose ou si tu remplis un seau percé.

Ces deux ratios se lisent **par clipper**, pas seulement en global : c'est comme ça que tu vois que Yanil sort 3 clics/Reel quand un autre en sort 0,2 — et que tu peux copier ce qui marche plutôt que de sermonner tout le monde pareil.

Précision qui a son importance : quand le dénominateur est nul, le rapport affiche **« — »** et jamais « 0,0 ». Un jour à 0 clic afficherait sinon « 0,0 sub/100 clics », ce qui se lit comme un problème de conversion alors que le problème est **en amont**. Un ratio indéfini n'est pas un ratio nul.

## Ce que tu reçois exactement, à 13h

1. **🎬 Clippers** — Reels publiés, vues, clics, subs. Une ligne par clipper, puis le détail **compte par compte** : c'est là que tu vois quel compte dort et lequel est mort.
2. **📱 Metricool** — posts publiés hier par créatrice (Rianah + Julien).
3. **🔗 Liens** — trafic des deeplinks par clipper et par créatrice, CTR, évolution vs 7 jours.
4. **🎯 Analyse** — le verdict de chaîne, les clippers muets, les comptes restreints 18+, le meilleur rendement.
5. **✅ Actionnable** — 8 étapes maximum, **les actions clippers en tête** parce que c'est le seul levier amont.

Livré en trois exemplaires : le message Telegram (lecture en 30 secondes), le `.md` complet en pièce jointe, et une GitHub Issue en archive.

## Pourquoi 13h et pas 8h du matin

Parce que le rapport **attend que Rianah ait saisi les subs de la veille**. Sans cette saisie, la chaîne s'arrête aux clics et tu ne sais pas si ton trafic vaut quelque chose — c'est exactement le trou que ce rapport est censé boucher. Un rapport à 8h serait un rapport amputé de son maillon le plus important.

Si l'onglet est vide à 13h, le rapport le dit franchement (« Subs du JJ/MM non saisis — Rianah doit remplir l'onglet Subs ») et le met en action n°1. Le silence n'est jamais toléré : **un zéro déclaré vaut mieux qu'une case vide**, exactement comme pour le [[Reporting clippers|reporting du dimanche]].

## Ce que Rianah doit faire (5 minutes le matin)

Un onglet `Subs` dans le classeur de tracking, une ligne par créatrice et par plateforme :

| Date | Créatrice | Plateforme | Subs | Clipper |
|---|---|---|---|---|
| 30/07/2026 | Sophie | OF | 12 | Yanil |
| 30/07/2026 | Sophie | MYM | 4 | Yanil |
| 30/07/2026 | Maddie | OF | 3 | Hugo |

- La colonne **Clipper est facultative** mais c'est elle qui permet d'attribuer les subs à une personne. Sans elle, les subs restent agrégés par créatrice et tu perds la moitié de l'intérêt du rapport.
- Les deux formats de date sont acceptés (`30/07/2026` et `2026-07-30`).
- **Le clipper ne déclare jamais lui-même le chiffre qui détermine sa paie** — c'est la règle de fiabilité déjà posée dans [[Reporting clippers]], et elle vaut ici aussi.

## La jointure : tout tient sur le prénom

C'est la seule clé qui existe entre les trois mondes, et c'est aussi le point de fragilité :

```
Sheet Tracking, colonne « Gérant »  = "Julien"
GAML, champ « note »                = "Clipping Julien"
Sheet Subs, colonne « Clipper »     = "Julien"
```

Un « Ju » côté Sheet et un « Julien » côté GAML **ne se rejoindront jamais** : le clipper apparaîtra avec des Reels mais 0 clic, et le rapport diagnostiquera un maillon cassé qui n'existe pas. Discipline à tenir : **le même prénom, écrit pareil, partout**.

## Les états de compte (et le piège du compte privé)

| État | Sens | Action |
|---|---|---|
| 🟢 ok | Profil atteint, mesurable | — |
| 🔒 privé | **Normal, pas une alerte.** Les deux comptes publics de croissance envoient le trafic vers le petit compte privé dont la bio et le lien restent visibles de tous. Seules les publications sont masquées. | Aucune |
| 🔞 restreint 18+ | Invisible pour les visiteurs déconnectés → **reach organique détruit** | Lever la restriction |
| ⚫ injoignable | Banni, supprimé, ou pas encore créé | Nettoyer le Sheet |

Le compte privé est le design voulu du modèle en pods décrit dans [[Machine Instagram-Facebook en masse]] — le traiter comme une anomalie était une erreur d'analyse, corrigée. La vraie alerte, c'est le **18+** : un compte marqué GOOD dans ton Sheet mais restreint est un compte que tu crois vivant alors qu'il ne touche plus personne.

## Coût et risque de ban

Le scraping passe par Apify, facturé à la consommation (~1,60 $/1000 profils Instagram, ~2 $/1000 posts Facebook). Les lignes dont l'état est mort (`ban`, `à créer`, `attente`, `réserve`) sont **exclues avant l'appel** — sinon elles brûlent des crédits payants pour scraper des comptes qui n'existent pas.

> [!warning] Risque de ban : nul, et c'est structurel
> Apify interroge des profils **publics** depuis **sa propre infrastructure**, avec des proxys résidentiels et **sans aucune authentification**. Meta voit un visiteur anonyme, non attribuable à un compte de l'agence. La règle absolue qui garantit ça : **ne jamais fournir de `sessionid`, de cookie ou d'identifiants Instagram à un scraper**. C'est la seule chose qui rendrait l'opération traçable, donc bannissable. Cette règle ne se négocie pas, même pour « avoir plus de données ».

## Sécurité du classeur

🔴 **Seul l'onglet `Tracking` sort du classeur.** Les onglets `Instagram` et `FaceBook` contiennent les mots de passe en clair : les publier en CSV les rendrait accessibles à toute personne ayant l'URL. C'est pour ça que la colonne `Compte` de l'onglet Tracking mélange IG et pages FB — le code devine la plateforme à l'écriture (une URL `facebook.com` = page FB, le reste = compte IG), ce qui permet de n'avoir **qu'un seul onglet publié**.

## Ce qui casserait ce rapport

L'avocat du diable, parce qu'un tableau de bord auquel on ne croit plus est pire que pas de tableau de bord :

- **Rianah ne saisit pas.** Le rapport perd son maillon final et redevient ce qu'il était. Garde-fou : l'alerte est en tête de rapport et en action n°1, tous les jours, jusqu'à saisie.
- **Les prénoms divergent** entre le Sheet et GAML → faux diagnostics de maillon cassé. Garde-fou : le rapport affiche les liens GAML rattachés à chaque clipper, donc une liste vide se voit.
- **Le Sheet n'est pas tenu à jour.** Un compte banni marqué GOOD, un compte réel absent → le rapport mesure une flotte fantôme. C'est aujourd'hui le point faible réel : sur 122 lignes auditées, ~65 sont des réserves « à créer » et 4 comptes marqués GOOD étaient morts.
- **Les crédits Apify s'épuisent.** Le rapport le dit (alerte « Apify n'a rien renvoyé ») mais la section Clippers est vide ce jour-là.
- **Le passage à l'heure d'hiver** décale le rapport à 12h (GitHub Actions ne connaît que l'UTC). Deux ajustements par an, à faire fin octobre et fin mars.

Aucune de ces pannes n'empêche la livraison : chaque source manquante devient une alerte en tête de message. Le rapport arrive **tous les jours**, même dégradé — un rapport qui ne part pas est un rapport auquel on cesse de penser.

## Lien avec le reste du pilotage

Ce rapport est le **quotidien** ; le [[Reporting clippers|formulaire du dimanche]] reste le **hebdomadaire** (bans, comptes actifs, cadence déclarée, blocages). Les deux ne se remplacent pas : le quotidien mesure ce qui s'est passé, l'hebdomadaire remonte ce que les chiffres ne disent pas. Le premier alimente les 1:1 et la paie ; le second alimente la stratégie du [[Sprint été - croissance sans moi|sprint]].

Il sert aussi de mesure propre au sens de [[Atterrissage du funnel (mesure propre avant optimisation)]] : avant d'optimiser quoi que ce soit dans le funnel, il faut savoir où le trafic se perd. C'est maintenant chiffré tous les jours, par clipper, sans avoir rien à faire — cohérent avec la logique de [[Se licencier de son propre poste|se licencier de son propre poste]] : le pilotage tourne sans toi, tu ne lis que le verdict.

## Historique

- **30/07/2026** — chaîne complète livrée (Apify + onglets Tracking/Subs), rapport déplacé de 8h Dubai à 13h Paris pour attendre la saisie des subs. Décision journalisée dans [[Journal de coaching]].
