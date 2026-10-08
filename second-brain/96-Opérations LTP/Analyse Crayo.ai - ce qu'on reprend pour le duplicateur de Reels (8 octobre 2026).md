---
titre: "Analyse Crayo.ai - ce qu'on reprend pour le duplicateur de Reels (8 octobre 2026)"
type: décision
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-08
tags: [ops/clippers, outil/app, marketing/reels, legal/cgu, finance/coût]
liens_forts: ["[[App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)]]", "[[App clippers - une app par clipper pour le Drive, les Reels et les versements (6 octobre 2026)]]", "[[Brief montage clipper (standard anti-crackdown 2026)]]", "[[Podcast Open Source - le clipping vu par un studio SaaS, ce qu'on en tire (28 septembre 2026)]]", "[[Formation clippers en une page et 10 simplifications (26 septembre 2026)]]", "[[État de l'art clipping Instagram (juillet 2026)]]", "[[Journal de coaching]]"]
---

# Analyse Crayo.ai : ce qu'on reprend pour le duplicateur de Reels (8 octobre 2026)

> [!tip] Verdict
> **Ne pas s'abonner à Crayo pour le duplicateur, et ne pas chercher à le reproduire « à l'identique » : copier les trois fonctions qui comptent, avec ce qu'on a déjà.** Crayo a bien une API (REST, 34 points d'accès), mais **elle ne couvre ni le Subtitle Remover, ni le Video Crop, ni le Video Cutter, ni le YouTube Downloader** : ces quatre outils n'existent que dans leur éditeur web, à la main, un fichier à la fois. L'API sert l'AutoClip (qu'OpusClip fait déjà chez nous, 900 crédits par mois, connecteur branché), la voix off, les images et le rendu de vidéos « faceless ». Ses conditions d'utilisation (21/03/2024) accordent une licence **« personnelle, non commerciale »**, interdisent le contenu « vulgaire ou obscène » et donnent à Crayo une licence mondiale gratuite sur tout ce qu'on y envoie : pour une agence qui pousse vers des plateformes adultes, c'est une dépendance qu'on ne veut pas. **Le duplicateur v1 se construit avec ce qui est déjà payé et déployé** : les masters OpusClip sans sous-titres (les exports ne coûtent rien), le bot et sa recette ffmpeg de variantes uniques, un style de sous-titres par clipper, un hook réécrit, une coupe du début, et le dépôt dans son Drive. Le « Subtitle Remover » devient inutile sur nos propres TOP 20 ; pour les fichiers hérités, un service d'inpainting à ≈ 0,01 $ la seconde suffit. Coût de calcul estimé : moins de 30 € par mois pour 2 000 variantes, contre 27 à 55 $ par mois chez Crayo pour un outil manuel qui ne fait pas le travail.

Légende : [C] confirmé (pages Crayo lues le 08/10/2026), [P] probable, [S] spéculatif.

## 1. Ce que Crayo est, fonction par fonction [C]

Crayo se présente comme « The AI Video Editor », « 3,2 millions d'utilisateurs », orienté clippers, chaînes faceless, streamers et agences[^1]. Les sept pages demandées par Gaëtan, et ce qu'elles disent vraiment :

| Fonction | Ce que la page promet | Ce qu'elle ne dit pas | Dans l'API ? |
|---|---|---|---|
| **Subtitle Remover**[^2] | détecte la zone des sous-titres incrustés et « reconstruit le fond image par image » plutôt que de flouter ; résultat « propre sur la plupart des vidéos » ; réservé aux « vidéos dont vous avez les droits » | aucune limite de durée, de taille, de résolution, aucun prix, aucun exemple avant/après | **non** |
| **YouTube Downloader**[^3] | coller un lien, choisir la qualité (1080p, 4K), télécharger, puis envoyer dans AutoClip ou l'éditeur ; « respecter les conditions de YouTube, c'est à vous » | formats, limites, filigrane | **non** |
| **Auto Clip**[^4] | l'IA « cherche les accroches : histoires, punchlines, segments à forte énergie », score chaque clip, sous-titres stylés automatiques, retouche dans l'éditeur ; source : fichier ou lien YouTube | durée maximale, nombre et longueur des clips, méthode du score | **oui** (`/v1/autoclip`, 2 à 20 clips, source de 1 min à 3 h) |
| **Video Crop**[^5] | recadrage 9:16, 1:1, 4:5, 16:9 ou libre, cadre déplacé **à la main** avec une grille des tiers, export à la résolution de la source, sans filigrane | **aucun suivi de visage ni de sujet** (la page ne le mentionne pas) | **non** |
| **Video Cutter**[^6] | coupe « à l'image près » dans le navigateur, autant de segments qu'on veut, résolution conservée, MP4 sans filigrane | fusion, suppression des silences, découpe par transcription : absents | **non** |
| **Vue d'ensemble**[^1] | 14 outils payants (AutoClip, faux SMS, voix off, images, cutter, crop, subtitle remover, fond, voix, face swap, YouTube downloader, icônes, API) + 12 outils gratuits **exécutés dans le navigateur** (trim, compresseur, convertisseur, vitesse, fusion, muet…) | aucun modèle d'IA nommé, aucune intégration tierce, pas d'application mobile, **pas de MCP** | — |
| **Developer API**[^7] | REST, `api.crayo.ai`, une clé « bearer », 34 points d'accès en 9 groupes, webhooks signés, pas de forfait API séparé (« No separate API plan and no separate bill ») | SDK, documentation publique détaillée (la console `/developers` est derrière la connexion) | — |

**Lecture.** Les quatre outils qui intéressent Gaëtan (enlever les sous-titres, télécharger, recadrer, couper) sont des outils **manuels** dans un éditeur web : un fichier à la fois, un humain devant l'écran. Rien, dans l'API, ne permet de les enchaîner pour 30, puis 100 clippers. Les douze « outils gratuits » tournent dans le navigateur (« le fichier est traité sur votre appareil et n'est jamais envoyé en ligne »), ce qui veut dire ffmpeg compilé en WebAssembly : c'est reproductible dans notre propre app, sans Crayo.

## 2. L'API, en détail [C]

Ce qui est exposé[^7] : compte (`GET /v1/account`), médias (envoi par fichier jusqu'à 1 Go, import par URL https jusqu'à 100 Mo), génération (images, icônes, face swap, voix off, changeur de voix, amélioration de la parole), catalogues (voix, styles de sous-titres, musiques), **transcriptions mot à mot** (`POST /v1/transcripts`), **projets** (jusqu'à 50 scènes, 10 minutes, narration, musique, style de sous-titres, puis `export` asynchrone), exports, **AutoClip** (`POST /v1/autoclip`, 3 tâches simultanées), webhooks (`export.completed`, `autoclip.completed`…). Limites : 2 requêtes par seconde, 50 par minute (10 par minute pour la génération), 2 exports en rendu à la fois, 200 projets par compte.

Crédits : les mêmes que l'application, débités à l'acceptation. Image 1 crédit ; voix off, changement de voix, amélioration, **transcription : 1 crédit par seconde** ; **export de projet : 1 crédit par seconde de vidéo rendue** ; **AutoClip : 1 crédit vidéo par clip**. Lectures, catalogues, envois, webhooks : gratuits. Compte gratuit : zéro crédit, les appels payants renvoient 402.

Ce qu'on pourrait en tirer, et pourquoi on ne le fera pas :

- **Re-sous-titrer un clip par l'API** est possible en théorie : envoyer le clip, créer un projet d'une scène avec un style de sous-titres du catalogue et la transcription, exporter (1 crédit par seconde : un Reel de 60 s = 60 crédits ; le plan Pro à 30 h d'export par mois permettrait ≈ 1 800 Reels). Mais la page décrit un moteur de vidéos « faceless » (scènes, narration, musique) : rien n'indique qu'il accepte un clip existant comme scène, ni qu'il sait couper, zoomer ou changer la vitesse. **À tester avant d'y croire** [S], et ça ne vaut la peine que si notre propre pipeline échouait.
- **AutoClip** fait ce qu'OpusClip fait déjà pour nous (projet par vidéo longue, template « Créatrices OFM », 900 crédits par mois, connecteur MCP branché ; 102 crédits utilisés au 26/09). Rien à gagner.
- **Pas de MCP**, pas de SDK, pas de documentation publique hors de la console connectée.

## 3. Le prix [C]

Page tarifs lue le 08/10[^8] : Hobby 13 $ par mois (160 $ par an), **Clipper 27 $ par mois (327 $ par an)**, Pro 55 $ par mois (664 $ par an), facturation annuelle « −30 % » ; en mensuel, les revues tierces citent 19, 39 et 79 $[^9]. Inclus par plan : 250 / 1 000 / 3 000 crédits de workflow, **2 h / 10 h / 30 h d'export par mois**, 30 / 120 / 180 min de voix off, 100 / 300 / 500 images, 25 / 100 / 500 Go. Tous les outils (dont le Subtitle Remover et le YouTube Downloader) sont dans tous les plans. **Aucun remboursement** (« Unfortunately, we do not offer refunds »), crédits non reportés d'un mois sur l'autre. Pas de plan gratuit documenté.

## 4. Les conditions d'utilisation : trois raisons de ne pas s'y attacher [C]

Conditions datées du 21/03/2024[^10] :

1. **Licence « personnelle, non commerciale »** : « non-exclusive, non-transferable, limited right to access and use the services… for your personal, non-commercial purposes ». Une agence qui produit pour des créatrices et des clippers payés est hors du texte. Rien sur l'API, la revente ou la marque blanche.
2. **Licence de Crayo sur nos contenus** : « You retain all ownership rights », mais on accorde « a worldwide, non-exclusive, royalty-free license to use, reproduce, distribute, and display the content ». Les vidéos des créatrices, envoyées chez un tiers qui peut les « distribuer et afficher » : non.
3. **Contenu « vulgaire, obscène »** interdit, résiliation « sans préavis » : nos clips sont safe par règle, mais l'origine des comptes et des liens (OF, MYM) fait de nous un client à risque de bannissement du jour au lendemain, avec des crédits perdus.

À quoi s'ajoute le **YouTube Downloader** : YouTube interdit le téléchargement hors de ses boutons (hors contenu dont on a les droits) ; Crayo renvoie la responsabilité à l'utilisateur. Pour les chaînes de nos créatrices, on a les droits ; pour tout le reste, c'est la même dette que la règle « contenu réutilisé = zéro recommandation » du [[Brief montage clipper (standard anti-crackdown 2026)|brief anti-crackdown]].

## 5. Fonction par fonction : utile pour nous ? comment on le fait ? combien ?

Le besoin réel, fixé par le brief anti-crackdown : un clip « postable » coche **cinq transformations** (hook réécrit, sous-titres à soi, voix off ou contexte, montage propre avec nouveau début, légende SEO), et jamais le même fichier sur deux comptes. Le duplicateur sert à ça, pas à « enlever des sous-titres ».

| Fonction Crayo | Utile au duplicateur ? | Comment on le reproduit | Coût |
|---|---|---|---|
| **Subtitle Remover** | **Peu** : nos TOP 20 ont des sous-titres incrustés parce qu'ils ont été exportés **avec** sous-titres depuis OpusClip, et les projets OpusClip sont toujours là | **Ne plus avoir à enlever** : réexporter chaque TOP 20 depuis OpusClip **sans sous-titres** (master), puis poser des sous-titres **différents par clipper** (police, couleur, position, animation) avec ffmpeg à partir de la transcription mot à mot ; OpusClip : « dupliquer, éditer, exporter ne coûtent rien ». Pour un fichier dont on n'a plus la source : service d'inpainting par API (WaveSpeed, APIXO ≈ 0,01 $ la seconde ; Muapi 0,005 à 0,013 $ ; Replicate ProPainter ≈ 0,025 $ par passage mais à bricoler)[^11], ou VSR auto-hébergé (STTN) sur un GPU, qui rend des « traces » sur fond mouvant comme chez Crayo | 0 € (masters) ; ≈ 0,60 $ par Reel hérité de 60 s |
| **YouTube Downloader** | **Non** : OpusClip prend déjà les liens YouTube des créatrices ; le bot n'en a pas besoin | `yt-dlp` côté serveur si un jour nécessaire, uniquement sur les chaînes des créatrices (droits) | 0 € |
| **Auto Clip** | **Déjà fait** par OpusClip (projet par vidéo longue, template, 900 crédits par mois) | rien à changer | déjà payé |
| **Video Crop** | **Rarement** : nos sources sont déjà en 9:16 ; le recadrage sert aux vidéos longues 16:9, qu'OpusClip recadre | ffmpeg `crop` pour les ratios fixes ; recadrage « intelligent » si besoin : Cloudinary `g_auto:face` (hébergé), ou AutoFlip de Google auto-hébergé ; OpusClip annonce une API de reframe en accès anticipé[^12] | 0 € |
| **Video Cutter** | **Oui**, c'est la transformation n° 4 du brief (nouveau début, coupes) | déjà dans la recette du bot (`-ss`, coupe de 0 à 0,5 s) ; à étendre : coupe de la première seconde complète + un point de coupe choisi dans l'app | 0 € |
| **Outils gratuits dans le navigateur** (trim, vitesse, muet, compresseur) | **Oui, comme idée d'interface** : le clipper règle sa variante sur son téléphone | ffmpeg.wasm dans la PWA pour l'aperçu et les réglages, rendu final côté serveur (un téléphone met plusieurs minutes à encoder 60 s en 1080p) | 0 € |
| **Voix off IA, Speech Enhancer** | **Oui, pour la transformation n° 3** (voix off ou contexte ajouté) | ElevenLabs ou l'API voix de notre choix, hors Crayo, par phrase courte en intro | ≈ 0,02 à 0,10 $ par Reel |

Ce que Crayo fait que nous ne ferons pas : les « campagnes de bibliothèque de contenu » (clippers payés aux vues, comme Whop Content Rewards, déjà analysé dans [[Process clippers - 10 simplifications de plus, avec recherche (27 septembre 2026)]]) ; les faux SMS et les vidéos Reddit « brainrot », hors sujet.

## 6. Le duplicateur v1 recommandé (octobre)

Une variante = **un fichier qu'Instagram ne reconnaît pas comme déjà vu, et qui coche le brief**. Pipeline, du plus simple au plus utile :

1. **Masters sans sous-titres** : pour chaque TOP 20 des six créatrices, un export OpusClip sans sous-titres + la transcription mot à mot (OpusClip la fournit ; sinon Whisper, ≈ 0,006 $ la minute). Déposés par le bot dans « 📁 Reels / TOP 20 Reels / masters ». Une fois.
2. **Recette par clipper, enrichie** (le bot a déjà zoom, vitesse, couleurs, coupe, dépôt Drive) : (a) coupe de la première seconde et nouveau point d'entrée ; (b) **sous-titres à lui** : police, couleur, position, animation parmi 6 styles, rendus par ffmpeg depuis la transcription (filtre `subtitles` ou `drawtext` mot à mot) ; (c) **hook à l'écran 3 s**, proposé par Claude à partir de la transcription, modifiable dans l'app ; (d) **piste audio retouchée** (gain, légère égalisation, 0,5 s de silence au début) pour casser l'empreinte audio, point faible noté le 26/09 (« les Reels uniques trompent l'empreinte d'un fichier, pas forcément la détection d'Instagram : même piste audio ») ; (e) **légende SEO** générée (nom de scène + thème), collée à côté du fichier.
3. **Dans l'app** (onglet Reels des deux PWA) : la liste des masters de sa créatrice, un bouton « Décliner pour moi » par vidéo, le hook éditable, le style de sous-titres choisi, puis « c'est prêt » avec le fichier dans son Drive et un bouton de téléchargement. Le rendu tourne sur le serveur du bot (Railway, ffmpeg déjà installé) ; une file d'attente, 30 à 60 s par Reel.
4. **Pour les créatrices** : même écran, mais la source est leur propre dossier Reels de la semaine, et la variante sert à publier sur leurs comptes secondaires ou les pages Facebook.

Coûts estimés [P] : rendu ffmpeg sur Railway, 2 000 variantes par mois × 45 s de calcul ≈ 25 h CPU, **10 à 25 € par mois** ; transcription des 120 TOP 20 : < 5 $ une fois ; hooks et légendes par Claude Haiku : < 3 $ par mois ; voix off si activée : 40 à 200 $ par mois à 2 000 Reels. Contre Crayo Clipper 27 à 39 $ par mois pour un outil manuel qui ne fait ni la recette ni le dépôt. Point mort sans objet : le duplicateur ne vend rien, il protège les vues ; le seul chiffre à suivre est la part de Reels uniques qui dépassent 1 000 vues, aujourd'hui inconnue.

## 7. Avocat du diable [P]

- **L'ennemi n'est pas l'empreinte du fichier, c'est le classement « non original »**. Depuis le crackdown Meta du 30/04/2026, recadrer, zoomer, changer la vitesse « ne suffit plus » ([[Brief montage clipper (standard anti-crackdown 2026)]]). Une variante automatique, même parfaite, reste un clip de la créatrice recopié ; ce qui le rend « original » aux yeux de Meta, c'est le hook, la voix off et le collab post, pas ffmpeg. Le duplicateur doit imposer le hook et proposer la voix off, sinon il industrialise le zéro vue.
- **Les sous-titres générés par ffmpeg sont moins beaux que ceux d'OpusClip ou de Crayo** (karaoké mot à mot, surlignage). Six styles ASS bien faits suffisent pour des clippers ; si Gaëtan veut l'animation « karaoké », OpusClip l'exporte déjà par style, et c'est gratuit en crédits : 20 masters × 3 styles = 60 exports, puis la recette ffmpeg par-dessus.
- **La détection audio d'Instagram** n'est pas documentée. Un gain et un silence au début ne suffiront peut-être pas ; la vraie parade est un son ajouté (voix off, musique libre sous le discours). À mesurer sur trois clippers avant de généraliser, comme prévu le 26/09.
- **Rendre sur Railway charge la machine du bot** (Discord, scans, Apify). Une file d'attente d'un rendu à la fois, la nuit pour les lots, ou un petit service séparé (le même conteneur, un deuxième service Railway à 5 $ par mois).
- **Crayo peut sortir une API de « subtitle removal » demain** ; ça ne changerait pas la décision : nos masters la rendent inutile, et les conditions d'utilisation restent celles d'un outil grand public.
- **Ce que je n'ai pas vérifié** : la qualité réelle du Subtitle Remover de Crayo (pas d'essai, pas d'exemple sur la page), la réponse de leur support sur l'usage commercial, et le comportement de l'API « projets » avec un clip existant. Trois questions à poser à leur Discord si un jour on y revient.

## Prédictions (08/10, revue le 08/11)

- Si le duplicateur v1 (masters + sous-titres par clipper + hook + coupe) est livré avant le 25/10, la part des Reels uniques à plus de 1 000 vues dépasse celle des Reels bruts du Drive sur les mêmes clippers — 60 %.
- Aucune fonction de Crayo n'aura été achetée ni appelée par API d'ici le 08/11 — 85 %.
- Au moins un clipper demandera « un outil pour enlever les sous-titres » malgré les masters, parce qu'il travaille sur d'anciens fichiers — 50 %.

Les décisions et prédictions sont dans le [[Journal de coaching]] (entrée du 8 octobre 2026).

[^1]: Crayo, « Features », https://crayo.ai/features, lu le 08/10/2026.
[^2]: Crayo, « Subtitle Remover », https://crayo.ai/features/subtitle-remover, lu le 08/10/2026.
[^3]: Crayo, « YouTube Downloader », https://crayo.ai/features/youtube-downloader, lu le 08/10/2026.
[^4]: Crayo, « Auto Clip », https://crayo.ai/features/auto-clip, lu le 08/10/2026.
[^5]: Crayo, « Video Crop », https://crayo.ai/features/video-crop, lu le 08/10/2026.
[^6]: Crayo, « Video Cutter », https://crayo.ai/features/video-cutter, lu le 08/10/2026.
[^7]: Crayo, « Developer API », https://crayo.ai/features/api, lu le 08/10/2026 (34 points d'accès, limites, crédits par appel).
[^8]: Crayo, « Pricing », https://crayo.ai/pricing, lu le 08/10/2026.
[^9]: Revues tierces de juin à août 2026 (Creatify, Prizmad, Tugan), chiffres mensuels divergents : à vérifier sur la page tarifs avant tout achat.
[^10]: Crayo, « Terms of Service », https://crayo.ai/tos, version du 21/03/2024, lue le 08/10/2026.
[^11]: Tarifs publics des API d'inpainting vidéo lus le 08/10/2026 : WaveSpeedAI (0,05 $ par 5 s), APIXO (0,01 $ la seconde, 600 s maximum), Muapi (0,065 $ par génération puis 0,013 $ la seconde ; variante LaMa 0,025 $ puis 0,005 $), Replicate `jd7h/propainter` (≈ 0,025 $ par passage, matériel L40S) ; projet libre `YaoFANGUK/video-subtitle-remover` (STTN, LAMA, ProPainter, GPU NVIDIA recommandé).
[^12]: OpusClip, « Auto-Resize Videos with the OpusClip API » (mai 2026, API en accès anticipé) ; Cloudinary, « Video gravity » (`g_auto:face`) ; Google AutoFlip (2020, code libre).
