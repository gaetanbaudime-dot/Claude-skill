---
titre: "Kit Clippers - mode d'emploi"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-14
tags: [ops/formation, ops/clipping, ops/onboarding]
liens_forts: ["[[Checklist formation clipping]]", "[[Machine Instagram-Facebook en masse]]", "[[Recruter et déléguer 20-30 marketeurs (playbook)]]", "[[Kit Emma - mode d'emploi]]"]
---

# Kit Clippers : la refonte de la formation (mode d'emploi)

> [!tip] Verdict
> La formation Loom de 36 min était bonne mais mal packagée : linéaire, sans point de contrôle, donc « ils posent les mêmes questions et ne regardent pas ». La refonte : **le Loom reste la bibliothèque** (chapitré, on n'y touche pas), l'exécution passe sur **UN SEUL PDF de 7 pages** (`Kit Clippers/Kit Clipper LTP (v2).pdf` : page de bienvenue + 6 fiches, une page = une étape, langage collégien) + **un quiz de 10 questions obligatoire avant le premier compte** + **la règle du renvoi** (question déjà couverte → lien du chapitre, jamais de re-réponse). Diagnostic et décision [[Journal de coaching|journalisés]].

## Le PDF v2 (14/07 — relecture ligne à ligne de Gaëtan + consignes Discord du 09/07)

| Page | Quand la donner | Contenu |
|---|---|---|
| **Bienvenue** | Avec le quiz | L'objectif en 5 étapes, le setup cible visuel (2 IG croissance + 1 IG privé + 3 pages FB), LA règle (jamais de rush brut), le parcours |
| **1 — Créer tes comptes (J0)** | Après le quiz validé | 1 compte/jour (jamais 2-3 d'un coup), mail+mdp+photo+bio+arobase uniques notés dans Discord, **jamais de numéro de téléphone** (vérif. Informations personnelles), piège de l'association (dissocier), lien GetAllMyLinks **J+7 sur le compte privé uniquement** (croissance = arobase en bio), compte FB mère → 10 pages max, 3 pages/créatrice, lien FB dès J0 |
| **2 — Warm-up** | Avec la fiche 1 | 48 h sans publier, consommation niche FR, notifications, **LE test de l'Explorer**, les erreurs qui cassent un warm-up |
| **3 — Monter et poster un Reel** | Quand l'Explorer est bon | Boucle Edits **sans renommage** (les clippers sont en lecteur sur le Drive), la question unique avant de publier (≠ rush brut), hook + partage, tableau autorisé/interdit |
| **4 — Routine et semaine** | Avec la fiche 3 | Routine du jour, montée S1=1 → S2=2 → S3=3 Reels/jour/compte, ~500 abonnés visés vers J+30, **reporting hebdomadaire : LE formulaire chaque dimanche, lié à la rémunération** + retours libres dans le canal Discord privé, la traversée du désert |
| **5 — Reels d'essai & évolutions** | À 200 abonnés | Variantes non-abonnés, paliers (compte pro, republication auto, Metricool, 2e téléphone, Clipper Manager) |
| **6 — Quand ça coince** | Toujours (avec la 1) | Ban → noter dans le canal Discord + mentionner Gaëtan (créneau) ; bans en chaîne → recréer + **diagnostic Gaëtan** (comptes connectés par mail, numéro ou appareil) ; circuit question (Loom → #faq → formulaire du dimanche), la règle du renvoi |

La théorie derrière la fiche 3 (pourquoi hook + partage sont LES deux critères) : [[Mécanique de contenu (hook, retain, reward)]] — à injecter dans la prochaine version des fiches si les clips plafonnent.

Régénération : `python3 tools/kit_clippers/generer_fiches.py` (générateur versionné, même outil que le [[Kit Emma - mode d'emploi|Kit Emma]]).

**Deux formats produits** (15/07) : le **PDF complet** `Kit Clipper LTP (v2).pdf` (les 7 pages à la suite, pour tout donner d'un coup) ET **chaque fiche en fichier séparé** dans `Kit Clippers/Fiches séparées/` (une fiche = un PDF d'une page, remise étape par étape au fil de l'onboarding : Bienvenue, puis Fiche 1 le jour 0, Fiche 2 avec, etc.). Les deux sont toujours identiques puisqu'ils sortent du même générateur.

## Le quiz d'onboarding (à coller dans un Google Form, mode « quiz auto-corrigé »)

**Réglage** : Google Forms → Paramètres → « Convertir en quiz » → note auto. **Seuil : 8/10** pour recevoir la fiche 1 et créer le premier compte. En dessous : on re-regarde les chapitres ratés, on repasse le quiz. ✅ = bonne réponse.

1. **Combien de comptes Instagram crées-tu par jour ?** — a) Les 3 d'un coup pour gagner du temps · b) ✅ Un seul par jour · c) Deux le matin, un le soir
2. **Où et quand mets-tu ton lien GetAllMyLinks ?** — a) Sur tous les comptes dès la création · b) ✅ Uniquement sur le compte Instagram privé, à J+7 · c) Sur les comptes de croissance à J+7
3. **Et sur une page Facebook ?** — a) ✅ Dès J0, bio + profil · b) À J+7 · c) Jamais de lien sur Facebook
4. **Peut-on associer les comptes Instagram entre eux (Meta Center) ?** — a) Oui, c'est plus pratique · b) Seulement les comptes de la même créatrice · c) ✅ Jamais : un ban peut emporter tous les comptes d'un coup (dissocier si Instagram crée un compte sans demander mail + mot de passe)
5. **Comment sais-tu que ton warm-up Instagram est terminé ?** — a) Après exactement 48 h · b) ✅ Quand l'Explorer montre des créatrices françaises · c) Quand j'ai 100 abonnements
6. **Les 2 critères qui font performer un Reel ?** — a) La durée et le filtre · b) ✅ Le hook et le taux de partage · c) Le nombre de hashtags et l'heure de publication
7. **Ton numéro de téléphone sur un compte Instagram ?** — a) Oui, pour sécuriser le compte · b) Seulement sur le compte privé · c) ✅ Jamais — vérifier dans Profil → Paramètres → Informations personnelles, et l'enlever s'il y en a un
8. **La montée en cadence, c'est :** — a) 10 Reels/jour dès la semaine 1 · b) ✅ +1 Reel/jour chaque semaine et par compte (semaine 1 = 1/jour, semaine 2 = 2/jour, semaine 3 = 3/jour) · c) On publie quand on a l'inspiration
9. **Les Reels d'essai se débloquent à :** — a) ✅ 200 abonnés, variantes montrées aux non-abonnés · b) 1 000 abonnés · c) Ils sont disponibles dès la création
10. **Le reporting, c'est :** — a) Un message quand j'y pense · b) ✅ LE formulaire chaque dimanche — sans lui : pas de suivi, pas d'évolution, pas de rémunération · c) Uniquement quand un compte est banni
*(Bonus/11 : on publie sur TikTok ? → Non : pas de clics ni d'abonnés OnlyFans — Instagram + pages Facebook uniquement.)*

## Les 3 règles de fonctionnement (côté Gaëtan/manager)

1. **La règle du renvoi** : toute question dont la réponse est dans la formation ou la FAQ → **on renvoie le lien du chapitre**, on ne re-répond pas. Répondre récompense le non-visionnage (« ce que tu récompenses, tu l'obtiens »). Le temps gagné va dans les retours sur les Reels — ce qui fait vraiment progresser. Version automatisée : le [[Bot FAQ clippers (Discord)]] répond 24/7 sur le périmètre du kit et cite la fiche.
2. **FAQ vivante** : une question posée 2 fois = une ligne dans le canal `#faq` (« expliqué 2 fois = écrit », [[Documentation et SOP]]). La FAQ est triée par fiche (J0 / warm-up / posting / cadence / essais).
3. **Mesurer au lieu de deviner** : Loom donne le **taux de complétion par viewer** — à regarder avant de conclure « ils ne regardent pas ». Le quiz donne la vraie mesure d'entrée ; les fiches réduisent le besoin de re-visionnage.

## Ce qui a changé vs la formation d'origine

Le **mindset (8 min) passe à la fin** du parcours — c'est la partie la plus zappée en ouverture, et la plus utile les jours de traversée du désert (la fiche 4 y renvoie). L'opérationnel commence à la 30e seconde. Le Loom n'est pas re-tourné : on le re-chapitre au besoin, c'est tout.

**v2 (14/07)** — relecture ligne à ligne de Gaëtan : un seul PDF au lieu de 6 fichiers, setup cible corrigé (2 IG croissance + 1 IG privé + 3 pages FB — fin des « 4 paires » et des 3 méthodes de lien : une seule méthode, arobase → compte privé → lien), règle « jamais de numéro de téléphone » ajoutée, étape de renommage des rushs supprimée (les clippers sont en lecteur sur le Drive), **reporting quotidien remplacé par LE formulaire du dimanche lié à la rémunération**, langage simplifié niveau collège, aération et logos. Les émojis natifs ne passant pas dans le moteur PDF, ils sont remplacés par des glyphes sûrs (✔ ✘ ⚠ ★ ☑) et des logos SVG (Instagram, Facebook, téléphone, flamme).

> [!warning] Sécurité
> Ces fiches et la formation décrivent des tactiques multi-comptes qui vivent en zone grise CGU ([[Machine Instagram-Facebook en masse|dette structurelle documentée]], [[Risques légaux et éthiques de l'OFM]]) — **documents internes, jamais publics**. ⚠️ Rappel du flag journalisé : la vidéo YouTube « stratégie » publique référencée dans le Loom est à passer **en non répertoriée**.
