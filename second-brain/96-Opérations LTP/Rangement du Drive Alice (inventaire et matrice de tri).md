---
titre: Rangement du Drive Alice (inventaire et matrice de tri)
type: sop
cluster: Opérations LTP
statut: verified
créé: 2026-07-28
tags:
  - ops/contenu
  - ops/drive
  - créatrice/alice
liens_forts:
  - "[[SOP - Machine à contenu hebdomadaire]]"
  - "[[LTP Models]]"
---

> [!tip] Verdict
> **173,82 Go, 2 669 fichiers, 17 dossiers.** Ça ne rentre pas : ton Drive a **46,56 Go libres** sur 100, il manque **127 Go**. Mais le vrai chiffre est ailleurs — **90 fichiers pèsent 89 % du total** (154,66 Go de rushes bruts 2022-2023, jusqu'à 8,7 Go pièce). Sors ces 90-là et il reste **19,16 Go**, qui tiennent sans rien payer, avec 27 Go de marge. Et le contenu réellement exploitable pour faire tourner Alice aujourd'hui — 2024 à 2026 — pèse **3,68 Go**. Tu allais donc déplacer 174 Go pour en utiliser 3,7. **Copie le vivant maintenant (3,68 Go), arbitre les 90 gros un par un, ne touche pas au reste.** Et ne me fais pas exécuter la copie via le connecteur : 2 669 appels d'API un par un, là où `rclone` le fait en une commande, côté serveur, sans repasser par ton réseau. Le script est écrit, il attend l'accord d'Alice.

## 1. Ce qui a été mesuré, et ce qui ne l'a pas été

Inventaire récursif complet des **17 dossiers** que tu m'as désignés, pagination épuisée à chaque niveau. Aucun média n'a été ouvert ni téléchargé : je n'ai lu que les métadonnées (nom, taille, dates, type MIME). Le contrôle de cohérence passe partout — le nombre de fichiers déclaré par branche égale le nombre de lignes remontées, et la somme des octets égale le total annoncé.

**Deux angles morts, dits franchement :**

Le dossier de Sophie (`Contenu Alice Wild - Sophie`) n'a **pas** été inventorié. C'est le périmètre par défaut que j'avais posé et que tu n'as pas contredit, et le garde-fou de sécurité a bloqué la tentative — deux fois la même conclusion, je la garde : ce dossier a déjà une logique mensuelle voulue par quelqu'un d'autre, il n'est pas à toi, on le laisse.

Le dossier `Reels` ne contient **aucun média** : deux archives ZIP de 3,89 Go au total, un export Drive en deux parties daté d'avril 2026, dont le suffixe suggère qu'une troisième partie existe ailleurs. Impossible de savoir ce qu'il y a dedans sans les ouvrir. **3,89 Go de contenu inconnu, et probablement un doublon de ce que tu possèdes déjà.**

## 2. Le volume, dossier par dossier

| Dossier source | Fichiers | Volume | Période (ajout Drive) | Nature |
|---|---:|---:|---|---|
| 2023 | 1 189 | **143,19 Go** | 01/2023 → 08/2024 | 286 vidéos (140,5 Go) + 903 photos |
| 2022 | 362 | **23,07 Go** | 11/2022 → 08/2023 | 122 vidéos (22,8 Go) + 240 photos |
| Reels (2 ZIP) | 2 | 3,89 Go | 06/2026 | contenu inconnu |
| IG Reels | 59 | 0,63 Go | 06 → 07/2025 | 100 % vidéo |
| Measuring tape | 38 | 0,49 Go | 03 → 04/2024 | 100 % vidéo |
| Reddit Alice | 52 | 0,42 Go | 06 → 08/2025 | 100 % vidéo |
| Today I learnt how to say | 48 | 0,41 Go | 03 → 05/2024 | 100 % vidéo |
| Teasing videos and photos | 34 | 0,40 Go | 09 → 10/2025 | 9 vidéos + 25 photos |
| Sexting Morning | 13 | 0,30 Go | 04/2026 | 6 vidéos + 7 photos |
| SFW PHOTOS | 91 | 0,24 Go | 10/2023 → 02/2026 | 85 photos + 6 vidéos |
| Tenu rouge | 6 | 0,21 Go | 01/2024 | 5 vidéos + 1 photo |
| Lifestyle photos for stories | 120 | 0,20 Go | 10 → 11/2024 | 100 % photo |
| IG Filler Stories | 52 | 0,15 Go | 06 → 07/2025 | 37 photos + 15 vidéos |
| IG Photos | 50 | 0,10 Go | 06 → 07/2025 | 100 % photo |
| Feed bot mym | 503 | 0,10 Go | 12/2025 | 100 % photo (petites) |
| New York pics nov 25 | 12 | 0,02 Go | 11 → 12/2025 | 9 photos + 3 vidéos |
| tommek session | 38 | 0,01 Go | 10 → 11/2024 | 100 % photo |
| **TOTAL** | **2 669** | **173,82 Go** | 11/2022 → 06/2026 | |

En unités Google (Gio) : **161,88 Gio**. C'est ce chiffre-là que ton compteur de stockage affichera.

## 3. Les trois chiffres qui décident

**Le stockage.** Tu utilises 53,44 Go sur 100. Il reste **46,56 Go**. Copier les 173,82 Go demande **127,26 Go de plus que ce que tu as**. Et le transfert de propriété ne sauve pas : dès que tu deviens propriétaire, le volume est décompté chez toi. Payer ou élaguer, il n'y a pas de troisième porte.

**La concentration.** 90 fichiers font 154,66 Go, soit **89,0 % du volume pour 3,4 % des fichiers**. Ce sont des masters de tournage bruts de 2022-2023 : le plus lourd fait 8,7 Go à lui seul, et 12 fichiers d'un seul mois d'avril 2023 pèsent 42,18 Go. Le seuil est net :

| Si tu écartes les fichiers au-dessus de… | Il reste à copier |
|---|---|
| 1 Go | 2 613 fichiers, 36,71 Go |
| 500 Mo | 2 595 fichiers, 23,96 Go |
| **200 Mo** | **2 579 fichiers, 19,16 Go** ✅ tient dans tes 46,56 Go |
| 100 Mo | 2 554 fichiers, 15,91 Go |

**L'utilité.** Le contenu de 2024-2026 — celui qu'Emma et les clippers peuvent réellement exploiter — représente **1 116 fichiers pour 3,68 Go**. Les archives 2022-2023 pèsent 166,25 Go, dont **23,85 Go déjà publiés** (929 fichiers rangés dans des sous-dossiers `USED`, `Posted`, `Uploaded on OF & MYM`). Rapporté au but poursuivi, c'est un rapport de **1 à 47** entre ce que tu déplaces et ce qui te sert.

C'est le raisonnement de la [[Théorie des contraintes|théorie des contraintes]] appliqué au stockage : le goulot de la machine à contenu n'a jamais été « les fichiers d'Alice sont mal rangés », c'est « personne ne pioche dedans ». Ranger 174 Go d'archives ne débloque rien ; ranger 3,68 Go de contenu vivant et le rendre lisible pour Emma, oui. Le reste est du [[Coût d'opportunité|coût d'opportunité]] déguisé en travail.

## 4. La matrice de tri

Cinq axes, appliqués aux 2 669 fichiers sans exception (contrôle : 2 669 entrants = 2 669 classés, 0 non classé, 173,82 Go en entrée comme en sortie).

**Axe 1 — Destination.** Héritée du dossier source, car c'est la seule information fiable dont je dispose. Résultat :

| Branche cible | Fichiers | Volume |
|---|---:|---:|
| 📣 Marketing/📱Instagram/📁 Story | 557 | 0,45 Go |
| 📣 Marketing/📱Instagram/📁 Carrousel | 179 | 0,35 Go |
| 📣 Marketing/📱Instagram/📁 Reels | 59 | 0,63 Go |
| 📣 Marketing/🤝 Reddit | 52 | 0,42 Go |
| 🔞 Plateformes Privées/📁 Feed | 170 | 0,63 Go |
| 🔞 Plateformes Privées/📁 PPV & Custom | 99 | 1,20 Go |
| 🗄️ Archives 2022-2023 (hors Drive de travail) | 1 551 | 166,25 Go |
| ⏳ À trier (les 2 ZIP) | 2 | 3,89 Go |

**Axe 2 — Nature.** 2 018 photos (3,58 Go) contre 649 vidéos (166,36 Go). Les vidéos sont **24 % des fichiers et 95,7 % du poids** — toute décision de stockage se joue sur elles seules, jamais sur les photos.

**Axe 3 — Niveau d'explicite.** 795 fichiers classés publiables sur les réseaux, 1 786 réservés aux plateformes adultes, 86 à trancher à l'œil. **Cette colonne est une présomption, pas un constat** : je l'ai déduite du dossier d'origine sans jamais regarder une image. Un fichier explicite égaré dans `SFW PHOTOS` sera classé publiable à tort — et sur Instagram, cette erreur-là coûte le compte. Quelqu'un doit valider visuellement la branche Marketing avant toute publication, c'est non négociable.

**Axe 4 — Date.** La date retenue est celle de l'**ajout au Drive**, pas celle du tournage : le connecteur ne donne pas l'EXIF. L'écart est parfois massif — dans `Feed bot mym`, tous les fichiers sont datés de décembre 2025 alors que les prises de vue s'étalent de février 2023 à décembre 2025. Le classement mensuel est donc un classement d'archivage, pas une chronologie de shooting.

**Axe 5 — Statut de publication.** 929 fichiers (23,85 Go) sont marqués déjà publiés, déduits des dossiers `USED`, `Posted` et `Uploaded on OF & MYM`. **Règle qui tranche le conflit actuel : le statut vit dans le dossier, jamais dans le nom de fichier.** C'est la double convention qui a produit les 13 fichiers tous nommés `Posted.mp4` dans `IG Reels` — treize contenus distincts devenus indiscernables sans les ouvrir. Un suffixe `_PUB` reste dans le nom comme filet si le fichier sort de son dossier, mais le dossier fait foi.

## 5. L'arborescence cible et le nommage

L'arbre reprend ton gabarit `gdrive_v2` à l'identique, avec deux écarts assumés :

```
📁 Alice World/
├── 📋 Documents Créatrice/
├── 📣 Marketing/
│   ├── 📱 Instagram/
│   │   ├── 📁 Carrousel/ {2026/1..12 · Archives 2025 · Archives 2024 · Archives 2023}
│   │   ├── 📁 Reels/     {idem, + Semaine/Tenue à partir de 2026 seulement}
│   │   └── 📁 Story/     {idem}
│   ├── 🤝 SFS/
│   └── 🤝 Reddit/                          ← ajout : Alice a un canal Reddit actif
└── 🔞 Plateformes Privées/                  ← plutôt que « OnlyFans » : Alice n'y est pas lancée
    ├── 📁 Feed/ · 📁 PPV & Custom/ · 📁 Script/
```

Le premier écart ajoute une branche Reddit que le gabarit ne prévoit pas mais que le contenu impose (52 vidéos). Le second renomme `🔞 OnlyFans` en `🔞 Plateformes Privées`, ce qui colle à la fois à la réalité d'Alice et à ce que j'observe déjà chez les créatrices du même lot dans `[C] Créatrices`.

Un troisième point mérite ton arbitrage : le gabarit prévoit `Semaine 1-4 / Tenue 1-5` sous Reels, soit 240 dossiers par an. Le contenu 2025 d'Alice n'a aucune information de tenue — créer ces 240 dossiers pour y ranger du legacy produirait 240 dossiers vides. **Je ne crée cette granularité qu'à partir des tournages 2026**, quand l'information existe.

**Nommage :** `AAAA-MM_ALICE_CANAL_TYPE_NNN[_PUB].ext`, par exemple `2025-07_ALICE_IG_CARROUSEL_003.jpg` ou `2025-06_ALICE_IG_REEL_012_PUB.mov`. Il trie chronologiquement, dit le canal et le type sans ouvrir le fichier, et reste lisible hors de son dossier. Le jour peut être ajouté à la copie (le connecteur l'a, mon inventaire l'a agrégé au mois) — dis-le si tu le veux, c'est une ligne à changer.

## 6. Ce qui est cassé dans le Drive actuel

**Les doublons vrais** sont marginaux : 15 paires internes et 5 fichiers présents dans deux dossiers, **0,14 Go au total**. Ce n'est pas là que se joue l'espace.

**Les faux doublons sont le vrai danger.** Dans `Reddit Alice`, **cinq fichiers distincts** portent exactement le même nom, avec des tailles allant de 6,4 à 15,3 Mo — cinq exports successifs d'un même rush. Dédupliquer par nom détruirait quatre contenus uniques. Toute passe de nettoyage se fait sur **nom + taille**, jamais sur le nom seul, et même ainsi le seul juge fiable serait un hash que le connecteur ne fournit pas.

**Les dossiers `USED` créés en août 2025 dans `IG Photos` et `IG Reels` sont vides.** Quelqu'un a mis en place un système de tri et ne l'a jamais utilisé — les 109 fichiers sont restés à la racine. C'est le symptôme habituel : une convention posée sans personne pour la tenir ne survit pas trois semaines. Elle tiendra cette fois si elle entre dans la [[SOP - Machine à contenu hebdomadaire|SOP hebdomadaire]] avec un responsable nommé, pas autrement.

**Deux flags qu'il faut lever avant de copier quoi que ce soit.**

Le premier est juridique. Les archives 2023 contiennent des tournages réalisés avec des partenaires tiers et au moins deux scènes produites pour des studios. Une scène tournée pour un studio appartient très probablement au studio, pas à Alice — la copier dans le Drive de l'agence, c'est héberger du contenu sous licence tierce sans en avoir vérifié les droits. **Statut : spéculatif, je n'ai vu aucun contrat.** À vérifier avant, pas après, dans la logique des [[Risques légaux et éthiques de l'OFM|garde-fous OFM]].

Le second est humain, et il n'a toujours pas de réponse. Ce contenu est celui d'Alice. Une copie en crée une seconde instance hors de son contrôle, chez toi, définitivement. **Rien ne part tant que tu ne m'as pas dit que c'est acté avec elle** — c'est la question que j'ai posée et à laquelle tu n'as pas répondu, et je ne la traite pas comme un détail administratif.

## 7. Pourquoi la copie ne doit pas passer par moi

Le connecteur Drive copie **un fichier par appel**. Les 2 669 fichiers demandent 2 669 allers-retours, soit plusieurs heures de run, un coût en jetons hors de proportion, et une reprise manuelle à chaque échec. Un signal de fiabilité s'est d'ailleurs déjà manifesté pendant l'inventaire : le connecteur refuse de lister les dossiers les plus chargés — le dossier de Chloé, celui de Sarah, les branches Instagram de deux autres créatrices ont tous renvoyé une erreur backend. Les branches les plus utiles sont précisément celles qu'il ne sait pas lire.

`rclone` fait le même travail en une commande, **côté serveur Google** (les octets ne transitent jamais par ton réseau), avec reprise automatique et journal. Le script est écrit à partir du plan de rangement : il crée les 30 dossiers cibles et exécute les 1 116 copies renommées du contenu vivant, avec un mode simulation à lancer en premier. Mon apport utile n'était pas de copier des fichiers, c'était de produire la matrice et le plan que la machine exécute.

## 8. La séquence recommandée

1. **Obtenir l'accord d'Alice**, explicitement, sur la copie et sur la reprise de propriété. Bloquant.
2. **Lancer la copie du vivant** : 1 116 fichiers, 3,68 Go, mode simulation d'abord. Ton stockage encaisse sans broncher.
3. **Vérifier le résultat sur une branche** — Story, la plus fournie — avant de valider le reste.
4. **Arbitrer les 90 gros fichiers** un par un sur la liste fournie : garder / archiver hors Drive / supprimer. C'est une décision de valeur d'archive, pas une décision technique, et elle t'appartient. Un disque externe de 2 To coûte moins qu'un mois d'abonnement à l'année et sort ces 154 Go de l'équation pour de bon.
5. **Ouvrir les deux ZIP** pour savoir si ces 3,89 Go sont un doublon (probable) ou du contenu unique.
6. **Câbler le rangement dans la [[SOP - Machine à contenu hebdomadaire|SOP hebdomadaire]]** et le confier nommément à Emma dans son [[Kit Emma - mode d'emploi|kit]] — sinon la nouvelle arborescence rejoindra les dossiers `USED` vides d'ici la rentrée.

Le point de bascule est à l'étape 6, pas à l'étape 2. Alice continuera d'uploader dans son vrac à elle : soit on prévoit une passe de rattrapage hebdomadaire, soit on lui demande de déposer directement dans la nouvelle arborescence. La seconde est la seule qui tienne dans la durée, et elle suppose que quelqu'un le lui demande et le vérifie — ce qui est exactement le rôle décrit dans la [[Scorecard - Creator Success Manager (Emma)|scorecard d'Emma]], et ce que la [[Méthode de délégation - Emma (kit de passation)|méthode de délégation]] appelle rendre une casquette plutôt que la déposer.

## Livrables hors vault

Trois fichiers de travail t'ont été remis directement (ils contiennent des noms de fichiers et de dossiers bruts, ils n'ont donc pas leur place dans le repo) : le plan de rangement complet des 2 669 fichiers avec source, destination et nouveau nom ; la liste des 90 fichiers à arbitrer avec une colonne de décision à remplir ; et le script `rclone` prêt à tourner en simulation.

Rattachement : cette page prolonge la [[SOP - Machine à contenu hebdomadaire|machine à contenu]] côté matière première, s'appuie sur la [[Checklist créatrice - Tournage batch|checklist de tournage]] pour la partie amont, et relève du chantier de fond décrit dans [[Se licencier de son propre poste]] — un rangement qui dépend de toi n'est pas un système. Contexte roster : [[LTP Models]] (Alice fait partie des lancements à zéro, en attente de main-d'œuvre clipping).
