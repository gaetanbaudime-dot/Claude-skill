---
titre: Audit Drive Alice — état des lieux avant réorganisation
type: sop
cluster: Opérations LTP
statut: to-verify
créé: 2026-07-28
tags:
  - ops/contenu
  - ops/drive
  - créatrice/alice
liens_forts: []
---

> [!tip] Verdict
> Le Drive d'Alice est lisible et j'ai les droits pour y créer des dossiers, mais **le connecteur Drive ne sait pas déplacer, renommer ni supprimer un fichier** — il sait seulement lire, créer des dossiers et copier. Une « réorganisation » au sens strict est donc impossible en l'état. La seule voie automatisable est la **copie vers une arborescence neuve dans ton Drive**, ce qui règle au passage ton problème de propriété. Avant de lancer quoi que ce soit, il me manque une seule chose bloquante : **ton arborescence de référence**.

## 1. Ce que la contrainte technique change

Ce que le connecteur sait faire : chercher, lire les métadonnées, lire les permissions, télécharger, créer un dossier, créer un fichier, **copier** un fichier.

Ce qu'il ne sait pas faire : **déplacer**, **renommer**, **supprimer**, modifier un fichier existant.

Conséquence directe : je ne peux pas « ranger » les fichiers là où ils sont. Chaque fichier rangé est nécessairement une **copie** créée ailleurs, avec le nom que je choisis à la création. L'original reste en vrac chez Alice, intact.

Ce n'est pas que du négatif : tu m'as dit ne pas avoir la propriété du contenu. Une copie créée depuis ton compte **t'appartient**. Le rangement et la reprise de propriété se font donc dans le même geste.

## 2. Ce que j'ai trouvé

Cinq dossiers liés à Alice, deux régimes de partage distincts.

| Dossier | Partage | Mes droits | État | Volume |
|---|---|---|---|---|
| IG Photos | lien public | fileOrganizer | vrac + sous-dossier `USED` | > 50 fichiers |
| IG Reels | lien public | fileOrganizer | vrac + sous-dossier `USED` | > 50 fichiers |
| IG Filler Stories | lien public | fileOrganizer | vrac total | > 50 fichiers |
| Reddit Alice | lien public | fileOrganizer | vrac total | > 50 fichiers |
| Contenu Alice Wild - Sophie | partage nominatif (Sophie) | éditeur | **déjà rangé** par mois | 3 sous-dossiers |

**Statut épistémique.** Les volumes sont des minorants : l'API pagine par 50 et chaque dossier renvoyait un jeton de page suivante. Le compte exact reste à établir. Les droits `fileOrganizer` sont **vérifiés sur IG Reels uniquement** ; pour les trois autres c'est probable (créés le même jour, partagés de la même façon, propriétaire non exposé) mais non vérifié.

Les quatre dossiers en vrac couvrent la période **juin → août 2025**. Le dossier de Sophie couvre **décembre 2025 → février 2026** et suit une logique mensuelle numérotée (`1. Décembre`, `2. Janvier`, `3. Février`). Il ne se recoupe donc ni en période ni en logique avec les quatre autres.

## 3. Les trois problèmes de fond

### 3.1 Deux conventions concurrentes pour dire « déjà posté »

Quelqu'un a déjà commencé à ranger, avec deux systèmes incompatibles :

- un sous-dossier `USED` créé le 26 août 2025 dans IG Photos et dans IG Reels ;
- un **renommage en `Posted`** dans IG Reels : une douzaine de fichiers s'appellent tous `Posted.mp4` ou `Posted.mov`, modifiés fin juin / début juillet 2025.

Le renommage est le pire des deux : douze fichiers portant le même nom sont indistinguables les uns des autres sans les ouvrir. L'information « posté » a été gagnée au prix de l'information « qu'est-ce que c'est ».

À trancher dans ton process : le statut posté/non-posté vit-il dans le **dossier** ou dans le **nom de fichier** ? Les deux à la fois, c'est ce qui a produit le bazar actuel.

### 3.2 Des doublons vrais

Vérifiés par identité nom + taille exacte :

- `IMG_3187.JPG` en double dans IG Photos (312 620 o) ;
- `IMG_3221.JPG` en double dans IG Filler Stories (607 796 o) ;
- `89CBB090-D2CD-4232-8268-B9DC2EB04B16.mp4` présent **à la fois** dans IG Filler Stories et dans IG Reels (12 762 777 o) — même fichier, deux dossiers.

### 3.3 Des faux doublons, plus dangereux que les vrais

Dans Reddit Alice, **quatre fichiers différents portent le nom `B0000C4A-2F45-46B3-9E71-375523F69BE6.mov`** — mais leurs tailles diffèrent (8,6 Mo / 15,3 Mo / 10,1 Mo / 6,4 Mo). Ce sont quatre contenus distincts sous un nom identique, probablement quatre exports successifs du même rush.

C'est le piège de toute déduplication naïve : dédupliquer par nom supprimerait trois contenus uniques. Toute passe de nettoyage doit se faire sur **nom + taille**, jamais sur le nom seul. Et même ainsi, deux exports au même réglage peuvent partager la taille — le seul juge fiable serait le hash, que le connecteur ne me donne pas.

Au-delà de ça, le vrac est du vrac de pellicule : `IMG_3187.JPG`, `IMG_2310.JPG`, et des UUID bruts type `7ad93ceb97a441e1a702ac7440f27a1a.mov`. Aucune information de contenu, de thème ou de destination dans les noms.

## 4. Les trois voies possibles

| Voie | Ce que ça donne | Coût | Risque |
|---|---|---|---|
| **A. Copie complète chez toi** | Arbo propre + renommage, tu deviens propriétaire de tout | Duplication de plusieurs Go de vidéo | Faible : le Drive d'Alice n'est jamais modifié |
| **B. Copie des actifs seulement** | Idem, mais `USED` / `Posted` / doublons exclus | Stockage réduit | Tu perds l'archive du déjà-posté, et le tri actif/archive repose sur des conventions déjà incohérentes (§3.1) |
| **C. Arbo vide + plan de rangement** | Je crée la structure cible chez Alice et je te livre un tableau fichier par fichier | Zéro duplication | Le glisser-déposer reste manuel sur plusieurs centaines de fichiers, et modifie le Drive d'Alice |

**Ma recommandation : la voie A.** Tu récupères la propriété, tu ne casses rien chez Alice, et si l'arbo ne te convient pas au premier essai, on recommence sans conséquence. La voie B est un raffinement à décider **après** avoir vu le volume réel — trancher maintenant, c'est arbitrer sur une convention `USED`/`Posted` dont on sait déjà qu'elle est incohérente.

**Ce qu'aucune des trois ne résout :** les futurs uploads d'Alice continueront d'arriver dans son vrac à elle. Soit on prévoit une passe de rattrapage périodique, soit tu lui demandes d'uploader directement dans la nouvelle arborescence. La deuxième option est la seule qui tienne dans la durée, mais elle suppose qu'Alice change son habitude — donc que quelqu'un le lui demande et le vérifie.

## 5. Ce dont j'ai besoin pour exécuter

### Bloquant

**Ton arborescence de référence.** Je n'ai trouvé aucune trace de ton process de rangement de contenu, ni dans le repo, ni dans la skill second-brain. Trois façons de me la donner, par ordre d'efficacité :

1. le lien d'un dossier de créatrice **déjà rangé comme tu veux** — je lis la structure et je la reproduis à l'identique (le plus fiable, et le plus rapide pour toi) ;
2. tu me l'écris dossier par dossier ;
3. je te propose une arbo et tu la corriges avant que je lance quoi que ce soit.

### Non bloquant — je tranche seul si tu ne réponds pas

- **Périmètre.** Par défaut je me limite aux quatre dossiers en vrac et je laisse le dossier de Sophie tranquille : il a déjà une logique mensuelle voulue, sur une autre période, et il n'est pas à toi non plus.
- **Nommage.** Par défaut `AAAA-MM-JJ_plateforme_type_001` (ex. `2025-07-21_IG_reel_003.mov`). La date est la **date d'ajout au Drive**, pas la date de prise de vue — le connecteur ne me donne pas l'EXIF. Si la chronologie réelle du shooting compte pour toi, ce nommage sera trompeur et il faut en discuter.
- **Statut posté.** Par défaut un dossier `Archive posté` par plateforme, et le statut disparaît du nom de fichier.

### Accord humain

Alice et Sophie sont-elles au courant ? Même en lecture-copie, c'est leur contenu, et la copie en fait une deuxième instance hors de leur contrôle. Je ne lance rien tant que tu ne me dis pas que c'est acté de leur côté.

## 6. Prochaine action proposée

Tu réponds au point bloquant du §5 dans la conversation second brain, tu me rapportes l'arborescence ici, et je lance la voie A sur un seul dossier pilote — **IG Photos**, le plus petit en volume de données. Tu valides le résultat avant que je traite les trois autres. Un pilote raté sur un dossier coûte dix minutes ; une arbo ratée sur quatre dossiers et plusieurs Go coûte une soirée.
