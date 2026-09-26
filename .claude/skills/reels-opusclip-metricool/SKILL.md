---
name: reels-opusclip-metricool
description: Reels des créatrices (Sophie, Chloé, Sarah) — clipper leurs vidéos YouTube longues avec OpusClip, retravailler chaque clip, bipper les mots vulgaires, décliner les sous-titres par marque, écrire textes et hashtags par réseau, contrôler la qualité et programmer sur Metricool (Instagram, Facebook, TikTok, YouTube). À charger dès qu'une session touche à OpusClip, à Metricool ou aux Reels des créatrices. Passation complète du 26/09/2026.
---

# Reels des créatrices : OpusClip → Metricool

> [!tip] Verdict
> Tout ce que Gaëtan a demandé sur ce chantier est ici, avec les identifiants et l'état exact au 26/09. Une session neuve charge cette skill, lit `etat.json` à côté, et exécute **sans reposer les questions déjà tranchées**. Elle avance par vagues (copies → retravail → censure → export → contrôle → programmation), met `etat.json` à jour après chaque vague et journalise la fin dans `second-brain/00-Contexte/Journal de coaching.md`.

## 1. La doctrine (identique au reste du repo)

- 100 % français, verdict d'abord, honnêteté brutale : dire ce qui casse, chiffrer, ne rien inventer.
- **Qualité avant volume, bans avant tout.** Consigne de Gaëtan (25/09) : « il faut clipper les vidéos longues, pas les Reels. Faire hyper attention à la qualité des vidéos et aux bans. Surtout pour Sophie, elle a des trucs très sexy sur sa chaîne. » Un clip douteux n'est pas programmé, point.
- Jamais de nom de plateforme adulte dans un texte publié (OnlyFans, MYM, « OF »). Les clips parlent de « créatrice de contenu », « plateforme », « abonnés » : c'est le vocabulaire à garder.
- Sécurité du repo : aucun handle Instagram/TikTok réel, aucun e-mail, aucun mot de passe dans un fichier commité. Les marques Metricool se désignent par leur libellé (« Sophie 1 - R ») et leur `blogId`. Les réponses de `getBrandSettings` et `getScheduledPosts` contiennent des handles et des e-mails de créateurs : on les lit, on ne les recopie pas.
- Les posts programmés par d'autres personnes sur les mêmes marques (Rianah sur Sophie 1, Julien sur Chloé 1) sont intouchables.

## 2. Sources : les chaînes YouTube des créatrices

| Créatrice | Chaîne | Matière |
|---|---|---|
| Chloé | https://www.youtube.com/@chloecallista | contenu parlé (FAQ, clichés du métier) : OpusClip sort beaucoup de clips |
| Sarah | https://www.youtube.com/@Sarah_Ivnv | questions-réponses (projet OpusClip P3092508sokv déjà traité, aucune marque Metricool Sarah pour l'instant) |
| Sophie | https://youtube.com/@sophiechoeur_2.0 | vlogs van life, peu parlés : choisir les vidéos techniques/parlées (construction du van), éviter tout passage suggestif |

Règle : **une vidéo longue = un projet OpusClip** (`opusclip_submit_project` avec `videoUrl` YouTube, `brandTemplateId` du template « Créatrices OFM », `sourceLang: "fr"`). Vérifier `opusclip_get_usage` avant : ≈ 1 crédit par minute de vidéo, 900 crédits par mois, remise à zéro le 1er.

## 3. OpusClip : ce qui marche et les pièges

- Un seul template : « Créatrices OFM » (`cmcaokhia041t7ypf070b4wmu`, karaoké mot à mot, surlignage de fond). Il n'existe **aucun outil pour créer un template** : les autres styles de sous-titres se font sur les clips avec `opusclip_edit_clip` (`set_style`, `set_emoji`, `set_keyword_highlight`).
- `opusclip_list_clips` sur un projet de 32 clips dépasse la taille de réponse : le résultat est sauvegardé dans un fichier, le lire par tranches. Les identifiants et titres des clips sont déjà dans `etat.json`.
- `opusclip_duplicate_clip` n'est **pas idempotent** : chaque appel crée une copie de plus. Vérifier `etat.json` avant de dupliquer.
- `opusclip_edit_clip` : plusieurs opérations en un appel = un seul rendu. Retravail standard de chaque clip : `remove_filler_words` puis `remove_pauses` (`minPauseSec` 0,7). `dryRun: true` montre sans rien changer. Après un appel, `render_pending: true` : attendre, puis `opusclip_describe_clip` jusqu'à `render_pending: false`.
- `opusclip_create_censor_job` avec `beepSound: true` = **bip sur les mots vulgaires** (demande de Gaëtan : « bipper ou masquer les mots vulgaires avant export, ça protège des bans »). Un rendu de plus : attendre `render_pending: false` avant d'exporter.
- `opusclip_export_clip` (`target: "hd"`) : `rendering` → rappeler jusqu'à `ready`. L'URL est signée et expire (≈ 2 jours) : programmer sur Metricool dans la foulée, Metricool copie le fichier chez lui à la création du post (les brouillons du 25/09 pointent sur `static.metricool.com`).
- Le seul compte social branché à OpusClip est un YouTube « Gaëtan OFM » sans intérêt : la publication passe par **Metricool**, jamais par `opusclip_schedule_publish`. Les textes sont écrits par Claude (section 6), pas par `create_social_copy_job`.

## 4. Metricool : marques, réseaux, créneaux

Fuseau : Europe/Paris. Les six marques cibles, leurs réseaux et le style de sous-titres attribué sont dans `etat.json` (`marques_metricool`). Points durs :

- **Une chaîne YouTube partagée** : Sophie 1 et Sophie 3 publient sur la même chaîne, Chloé 1 à 7 aussi. Le même clip trois fois sur une chaîne = spam YouTube. Donc YouTube **uniquement sur la marque 1** de chaque créatrice (et sur Sophie 2, qui a sa propre chaîne).
- Sophie 1 reçoit déjà 5 Reels par jour de Rianah (07:30, 10:00, 12:30, 15:30, 18:00), Chloé 1 six de Julien (10:00 à 17:30 toutes les 90 minutes, Instagram à 12:00). Nos créneaux : **09:00 et 20:00** (Sophie), **09:00 et 19:30** (Chloé), deux Reels par jour et par marque, à partir du 28/09. Si Gaëtan veut moins dense, passer à un par jour à 09:00.
- Format d'un post (tous les réseaux de la marque en un appel `createScheduledPost`) :

```json
{"autoPublish": true, "draft": false, "shortener": false, "hasNotReadNotes": false,
 "media": ["<URL export OpusClip>"], "mediaAltText": [], "descendants": [], "firstCommentText": "",
 "providers": [{"network": "instagram"}, {"network": "facebook"}, {"network": "tiktok"}, {"network": "youtube"}],
 "publicationDate": {"dateTime": "2026-09-28T09:00:00", "timezone": "Europe/Paris"},
 "text": "<texte + hashtags>",
 "instagramData": {"type": "REEL", "showReelOnFeed": true, "isAiGenerated": false},
 "facebookData": {"type": "REEL", "title": "<titre court>"},
 "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "<titre court>", "disableComment": false, "disableDuet": false, "disableStitch": false},
 "youtubeData": {"title": "<titre ≤ 100 caractères>", "type": "short", "privacy": "public", "madeForKids": false}}
```

  Ne mettre que les `xxxData` des réseaux présents dans `providers`. Pas de `videoThumbnailUrl`.
- **Brouillons à publier** (`brouillons_metricool_a_publier` dans `etat.json`, 8 posts Trial Reel Instagram créés le 25/09) : `updateScheduledPost` avec `id` + `uuid`, `draft: false`, tous les réseaux de la marque, `instagramData.type` = `REEL`, date déplacée à 09:00 (le 10:00 est pris par Rianah), média remplacé par le nouvel export retravaillé et censuré du même clip. Un update change l'`id`, jamais l'`uuid`.

## 5. Le programme demandé le 26/09 (mot pour mot, puis le plan)

Gaëtan : « Publie les brouillons et lance. Applique le contrôle qualité, programme 32 Reels × 1 vidéo sur une marque entière. Puis tu prends la même vidéo, 32 Reels × autre type de sous-titres sur une autre marque. Fais ça 3× pour Chloé et 3× pour Sophie sur leurs 3 premières marques. Bipper ou masquer les mots vulgaires d'un clip avant export, ce qui protège des bans, applique ça aussi. Écrire les textes et hashtags par réseau, fais ça aussi. Essaye de retravailler chaque Reel, programme tout directement, je te fais confiance. »

Plan retenu :

1. **Copies** : chaque clip existe en trois exemplaires, l'original (style A) et deux copies (B, C). Sophie : 32 × 3, Chloé : 25 × 3 (la vidéo de Chloé n'a donné que 25 clips ; le dire, ne pas en inventer).
2. **Retravail** de chaque exemplaire : `remove_filler_words` + `remove_pauses` 0,7 s, dans le même appel que le style.
3. **Styles de sous-titres** (un par marque, pour que la même vidéo ne soit pas identique d'une marque à l'autre) :
   - A (Sophie 1, Chloé 1) : template tel quel.
   - B (Sophie 2, Chloé 2) : `set_style` majuscules, texte blanc `#FFFFFF`, surlignage jaune `#FFE600`, position `bottom`.
   - C (Sophie 3, Chloé 3) : `set_style` texte blanc, surlignage rose `#FF3DA5`, position `bottom` + `set_emoji` activé.
4. **Censure** avec bip sur chaque exemplaire, après le retravail, avant l'export.
5. **Export HD** de chaque exemplaire, puis **contrôle qualité** (section 7).
6. **Textes et hashtags** par réseau (section 6).
7. **Programmation** Metricool : marque 1 (tous réseaux), marque 2, marque 3, deux par jour, ordre de score décroissant ; les 8 brouillons du 25/09 publiés en premier.
8. `etat.json` mis à jour après chaque vague ; bilan à Gaëtan avec le nombre de posts par marque, les clips écartés et pourquoi, les crédits restants.

État au moment de la passation : les deux clips pilotes de Sophie sont retravaillés (l'un rendu en cours), les 8 premiers clips Sophie sont dupliqués (identifiants des copies B et C dans `etat.json`), rien d'autre n'est fait : aucun style posé, aucune censure, aucun export, aucun post créé.

## 6. Textes et hashtags par réseau

Un seul champ `text` sert à tous les réseaux du post ; la différence par réseau passe par les titres (`youtubeData.title`, `tiktokData.title`, `facebookData.title`). Règles :

- **Texte commun** (Instagram/Facebook) : une accroche de 8 à 12 mots tirée du clip, une question ou un appel à commenter, une ligne vide, 6 à 10 hashtags. Français, tutoiement, un ou deux emojis maximum, aucun lien (« lien en bio » autorisé). Jamais le mot OnlyFans, MYM ni « OF ».
- **Titre YouTube** : le titre du clip reformulé en moins de 70 caractères, sans emoji ni majuscules criardes.
- **Titre TikTok et Facebook** : l'accroche seule, ≤ 60 caractères.
- Hashtags par créatrice : Sophie = `#vanlife #vanaménagé #vieenvan #roadtrip #fourgonaménagé #voyage #aventure #astucevan` ; Chloé = `#créatricedecontenu #sansfiltre #clichés #réseauxsociaux #vlog #humour #vérité #pourtoi`. Compléter avec 2 hashtags propres au clip (ceux proposés par OpusClip, sans accents cassés ni doublons). Varier légèrement l'accroche d'une marque à l'autre (marque 2 et 3 : reformuler) pour éviter des captions identiques.

## 7. Contrôle qualité (avant chaque programmation)

1. **Contenu** : lire le transcript (`opusclip_describe_clip`). Écarter un clip qui nomme explicitement une plateforme adulte, qui montre ou décrit une scène suggestive (Sophie surtout), ou qui n'a pas de sens sorti de son contexte (score de cohérence < 7). « Marmelade » est un mot de code entendu dans la vidéo de Chloé : toléré tel quel.
2. **Durée** : 12 à 60 secondes (les clips actuels vont de 14 à 43 s).
3. **Fichier** : `ffprobe` sur l'URL d'export : 1080×1920, piste audio présente, durée cohérente avec le retravail.
4. **Sous-titres lisibles** : extraire 3 images (`ffmpeg -ss … -frames:v 1`) d'au moins un clip par style, les regarder : texte entier dans le cadre, pas sur le visage, contraste correct, bip/astérisques présents là où la censure a joué.
5. **Doublons** : jamais deux fois le même clip sur la même chaîne YouTube ni sur le même compte ; les 8 brouillons du 25/09 sont ces mêmes clips, on les met à jour, on ne les recrée pas.
6. **Calendrier** : aucun de nos posts au même horaire qu'un post existant de la marque (`getScheduledPosts` sur la période avant de créer).

## 8. Autorisations : pour ne plus « Autoriser une fois »

- `.claude/settings.json` du repo autorise déjà `mcp__OpusClip__*` et `mcp__Metricool_Social_Media_Management__*` (syntaxe validée par la documentation : un glob de nom d'outil après `mcp__<serveur>__`). Ces règles ne s'appliquent qu'aux sessions ouvertes après leur ajout.
- La documentation précise aussi qu'un outil de connecteur claude.ai réglé sur « demander » **force le prompt à chaque appel, quel que soit le mode**. Le réglage qui compte est donc celui de Gaëtan sur https://claude.ai/customize/connecteurs : ouvrir OpusClip puis Metricool, « permissions des outils », passer chaque outil sur autorisé (sans demander). Fait une fois, valable pour toutes les sessions suivantes.

## 9. Journalisation

À la fin de chaque vague importante : une puce datée dans `second-brain/00-Contexte/Journal de coaching.md` (section 2026-09-26 ou nouvelle date), avec les chiffres (posts créés par marque, clips écartés, crédits OpusClip consommés) et une prédiction datée sur les vues à J+7. Commit en français, push sur `main` avec 4 tentatives, puis miroir sur la branche de travail si elle existe.
