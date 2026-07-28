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

> [!tip] Verdict (mis à jour le 28/07 — passage à 400 Go)
> **173,82 Go, 2 669 fichiers, 17 dossiers.** Avec 400 Go de quota, tout rentre : **346,56 Go libres**, il en faut 173,82, il restera 172,74 Go de marge. La question n'est donc plus « quoi copier » mais « comment, sans rien perdre ».
> **La réponse : deux phases, et surtout pas 2 669 copies individuelles.** Phase A — copie brute intégrale des 17 dossiers vers une zone de réception, adressés par ID Drive, **côté serveur Google** : aucun octet ne transite par ta connexion, la durée dépend du nombre de fichiers et pas du volume, et rien ne peut être perdu puisqu'on ne renomme rien. Phase B — rangement et renommage **à l'intérieur de ton propre Drive**, où un déplacement est une écriture de métadonnées : instantané, gratuit en stockage, et entièrement réversible si le classement ne te plaît pas.
> **Compte 30 à 60 minutes en tout, dont 10 de configuration.** Les deux scripts sont écrits et testés syntaxiquement. Seule chose qui manque encore : **l'accord d'Alice**, que tu ne m'as toujours pas donné.

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

**Le stockage. Résolu le 28/07** : quota passé de 100 à 400 Go, soit **346,56 Go libres** pour 173,82 Go à copier — il restera 172,74 Go. Le calcul qui suit garde sa valeur pour les huit autres créatrices, et pour le jour où le quota se remplira à nouveau : c'est le même arbitrage qui se reposera.

**La concentration.** 90 fichiers font 154,66 Go, soit **89,0 % du volume pour 3,4 % des fichiers**. Ce sont des masters de tournage bruts de 2022-2023 : le plus lourd fait 8,7 Go à lui seul, et 12 fichiers d'un seul mois d'avril 2023 pèsent 42,18 Go. Le seuil est net :

| Si tu écartes les fichiers au-dessus de… | Il reste à copier |
|---|---|
| 1 Go | 2 613 fichiers, 36,71 Go |
| 500 Mo | 2 595 fichiers, 23,96 Go |
| **200 Mo** | **2 579 fichiers, 19,16 Go** |
| 100 Mo | 2 554 fichiers, 15,91 Go |

Ce tableau ne sert plus à décider quoi copier, mais à comprendre où va l'espace : **90 fichiers occuperont 89 % du nouveau quota**. Le jour où les 400 Go seront pleins, c'est là qu'il faudra couper, et nulle part ailleurs.

**L'utilité.** Le contenu de 2024-2026 — celui qu'Emma et les clippers peuvent réellement exploiter — représente **1 116 fichiers pour 3,68 Go**. Les archives 2022-2023 pèsent 166,25 Go, dont **23,85 Go déjà publiés** (929 fichiers rangés dans des sous-dossiers `USED`, `Posted`, `Uploaded on OF & MYM`).

C'est ce déséquilibre qui dicte le traitement, et c'est la [[Théorie des contraintes|théorie des contraintes]] qui tranche : on copie tout puisque la place existe, mais **on ne dépense de l'effort de rangement que sur les 3,68 Go qui servent**. Les 166 Go d'archives gardent leur arborescence d'origine — leurs dossiers de sessions, de lieux et de mois portent déjà de l'information qu'un renommage automatique détruirait. Renommer 1 551 fichiers d'archives serait exactement le [[Coût d'opportunité|coût d'opportunité]] déguisé en travail : beaucoup d'activité sur un non-goulot.

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

## 7. Le plan d'exécution : deux phases, 30 à 60 minutes

### Pourquoi deux phases et pas une

L'erreur naturelle serait de lancer 2 669 opérations « copie et renomme en même temps ». C'est fragile : une opération qui échoue au milieu laisse un état illisible, et la moindre erreur de destination dans la matrice est déjà écrite dans le nom du fichier. En séparant, chaque phase a une seule responsabilité et une propriété utile.

La **phase A** ne fait que copier, à l'identique, sans rien renommer. C'est l'assurance « aucun fichier perdu » : la vérification se réduit à comparer deux compteurs. Elle s'exécute **côté serveur Google** — les octets ne descendent jamais sur ta machine et ne remontent jamais, donc les 174 Go n'ont aucun impact sur ta connexion. La durée dépend du **nombre de fichiers**, pas du volume : copier un fichier de 8,7 Go coûte le même temps qu'un de 300 Ko.

La **phase B** ne fait que ranger, à l'intérieur de ton propre Drive, où tu es désormais propriétaire. Un déplacement Google n'est pas une copie : c'est une écriture de métadonnées, instantanée, qui ne consomme pas un octet de stockage supplémentaire. Et c'est **réversible** : si le classement ne te convient pas, les fichiers sont déjà chez toi, on retrie sans rien re-télécharger.

### La préparation (10 minutes, une seule fois)

Installe `rclone` — un binaire unique, pas d'installation lourde : `brew install rclone` sur Mac, ou le téléchargement direct depuis `rclone.org/downloads`. Puis lance `rclone config` et crée **un seul** remote nommé `drive` sur ton compte Google : choisis le type `drive`, laisse `client_id` et `client_secret` vides, prends le scope `1` (accès complet), refuse la configuration avancée, accepte la configuration automatique — ton navigateur s'ouvre pour l'autorisation Google, et c'est fini.

Un seul remote suffit, et tu n'as **pas besoin des identifiants d'Alice** : chaque dossier est adressé par son identifiant Drive, ce qui fonctionne qu'il soit dans ton espace ou partagé avec toi. C'est aussi ce qui immunise le script contre les pièges de noms — quatre des dossiers d'Alice ont un espace en fin de nom, invisible à l'œil et fatal en ligne de commande.

### L'exécution

Lance chaque phase d'abord en simulation (`--dry-run`), qui n'écrit rien et te montre ce qui se passerait. Puis en réel. Entre les deux phases, vérifie le compteur : `rclone size` doit afficher **2 669 fichiers et environ 173,8 Go** dans la zone de réception. Si le compte y est, la phase A a fait son travail et plus rien ne peut être perdu ensuite.

Les deux scripts gèrent les échecs : `rclone` reprend là où il s'est arrêté sans recopier l'existant, il suffit de relancer. Un journal est écrit à côté (`phase_A.log`), consultable en direct avec `tail -f`.

### Ce qui peut coincer, dit d'avance

Google plafonne les écritures à **750 Go par jour** et par compte. Tes 174 Go passent largement dessous, mais si tu enchaînais plusieurs créatrices dans la même journée, la limite se manifesterait par des erreurs de quota — la parade est d'attendre le lendemain et de relancer, le script reprendra tout seul.

Le client d'API par défaut de `rclone` est partagé entre tous ses utilisateurs dans le monde, ce qui peut provoquer des ralentissements aux heures chargées. Si le transfert traîne, créer ton propre identifiant client dans Google Cloud règle le problème — c'est dix minutes de configuration, à ne faire que si le besoin s'en fait sentir.

Enfin, `rclone` refuse par défaut les fichiers que Google a signalés. Le drapeau `--drive-acknowledge-abuse` est déjà dans les scripts pour cette raison ; si un fichier bloque malgré tout, il apparaîtra nommément dans le journal et se traitera à la main.

### Après la copie

Trois choses restent à faire, et aucune n'est technique.

**Vérifier une branche à l'œil** avant de considérer le rangement comme acquis — `📁 Story` est la plus fournie, c'est le bon échantillon. Le point à contrôler en priorité est le classement publiable / non publiable : il est déduit du dossier d'origine, jamais du contenu, et une erreur dans ce sens-là coûte un compte Instagram.

**Ouvrir les deux archives compressées** (3,89 Go) pour savoir si elles doublonnent ce que tu possèdes déjà — c'est probable, leur nom indique un export Drive.

**Câbler le rangement dans la [[SOP - Machine à contenu hebdomadaire|SOP hebdomadaire]]** et le confier nommément à Emma via son [[Kit Emma - mode d'emploi|kit]]. C'est la seule étape qui décide si tout ce travail sert à quelque chose dans six mois. Les dossiers `USED` créés en août 2025 et toujours vides onze mois plus tard sont la démonstration que la structure ne suffit pas : sans responsable nommé, elle meurt.

Et la question qui reste ouverte : Alice continuera d'uploader dans son vrac à elle. Soit on prévoit une passe de rattrapage hebdomadaire, soit on lui demande de déposer directement dans la nouvelle arborescence. La seconde est la seule qui tienne dans la durée, et elle suppose que quelqu'un le lui demande et le vérifie — exactement le rôle décrit dans la [[Scorecard - Creator Success Manager (Emma)|scorecard d'Emma]], et ce que la [[Méthode de délégation - Emma (kit de passation)|méthode de délégation]] appelle rendre une casquette plutôt que la déposer.

Le point de bascule est à l'étape 6, pas à l'étape 2. Alice continuera d'uploader dans son vrac à elle : soit on prévoit une passe de rattrapage hebdomadaire, soit on lui demande de déposer directement dans la nouvelle arborescence. La seconde est la seule qui tienne dans la durée, et elle suppose que quelqu'un le lui demande et le vérifie — ce qui est exactement le rôle décrit dans la [[Scorecard - Creator Success Manager (Emma)|scorecard d'Emma]], et ce que la [[Méthode de délégation - Emma (kit de passation)|méthode de délégation]] appelle rendre une casquette plutôt que la déposer.

## Livrables hors vault

Les fichiers de travail sont remis directement (ils contiennent des noms de fichiers et de dossiers bruts, ils n'ont donc pas leur place dans le repo) : **`phase_A_copie.sh`** (copie brute des 17 dossiers par identifiant Drive), **`phase_B_rangement.sh`** (30 dossiers créés, 1 116 fichiers rangés et renommés, archives déplacées en bloc), le plan de rangement complet des 2 669 fichiers avec source, destination et nouveau nom, et la liste des 90 gros fichiers avec une colonne de décision — celle-ci ne bloque plus la copie, mais elle dira où couper le jour où les 400 Go se rempliront.

Rattachement : cette page prolonge la [[SOP - Machine à contenu hebdomadaire|machine à contenu]] côté matière première, s'appuie sur la [[Checklist créatrice - Tournage batch|checklist de tournage]] pour la partie amont, et relève du chantier de fond décrit dans [[Se licencier de son propre poste]] — un rangement qui dépend de toi n'est pas un système. Contexte roster : [[LTP Models]] (Alice fait partie des lancements à zéro, en attente de main-d'œuvre clipping).
