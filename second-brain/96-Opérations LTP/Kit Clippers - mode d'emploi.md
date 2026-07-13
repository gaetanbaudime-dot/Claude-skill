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
> La formation Loom de 36 min était bonne mais mal packagée : linéaire, sans point de contrôle, donc « ils posent les mêmes questions et ne regardent pas ». La refonte : **le Loom reste la bibliothèque** (chapitré, on n'y touche pas), l'exécution passe sur **6 fiches A4** (dossier `Kit Clippers/`, une page = une étape) + **un quiz de 10 questions obligatoire avant le premier compte** + **la règle du renvoi** (question déjà couverte → lien du chapitre, jamais de re-réponse). Diagnostic et décision [[Journal de coaching|journalisés]].

## Les 6 fiches (une par étape, remises au fil de l'onboarding)

| Fiche | Quand la donner | Contenu |
|---|---|---|
| **1 — J0 : création des comptes** | Après le quiz validé | 1 compte/jour, identités uniques, jamais Meta Center, lien J+7 IG / J0 FB, les 4 paires, les 3 méthodes de lien |
| **2 — Warm-up Instagram** | Avec la fiche 1 | 48 h sans publier, consommation niche FR, notifications, **LE test de l'Explorer** |
| **3 — Posting quotidien** | Quand l'Explorer est bon | La checklist Edit complète (bases → rush 👍 → variantes → brouillons matin), hook + partage |
| **4 — Cadence** | Avec la fiche 3 | 1→10 Reels/jour (+1/sem), carrousels, commentaires, stories, reporting quotidien, la traversée du désert |
| **5 — Reels d'essai & évolutions** | À 200 followers | Variantes non-followers, paliers (compte pro, repost auto, Metricool, 2e téléphone, Clipper Manager) |
| **6 — Quand ça coince** | Toujours (avec la 1) | Bans = coût d'exploitation, le circuit question (Loom → #faq → reporting), la règle du renvoi |

Régénération : `python3 tools/kit_clippers/generer_fiches.py` (générateur versionné, même outil que le [[Kit Emma - mode d'emploi|Kit Emma]]).

## Le quiz d'onboarding (à coller dans un Google Form, mode « quiz auto-corrigé »)

**Réglage** : Google Forms → Paramètres → « Convertir en quiz » → note auto. **Seuil : 8/10** pour recevoir la fiche 1 et créer le premier compte. En dessous : on re-regarde les chapitres ratés, on repasse le quiz. ✅ = bonne réponse.

1. **Combien de comptes Instagram crées-tu par jour ?** — a) Les 4 d'un coup pour gagner du temps · b) ✅ Un seul par jour · c) Deux le matin, deux le soir
2. **Quand mets-tu le lien sur un compte Instagram neuf ?** — a) Dès la création · b) ✅ À J+7 · c) Quand le compte atteint 1 000 followers
3. **Et sur une page Facebook ?** — a) ✅ Dès J0, bio + profil · b) À J+7 · c) Jamais de lien sur Facebook
4. **Peut-on associer les comptes dans le Meta Center ?** — a) Oui, c'est plus pratique · b) Seulement les comptes de la même créatrice · c) ✅ Jamais : ça provoque des bans en chaîne
5. **Comment sais-tu que ton warm-up Instagram est terminé ?** — a) Après exactement 48 h · b) ✅ Quand l'Explorer montre des créatrices OF françaises · c) Quand j'ai 100 follows
6. **Les 2 critères qui font performer un Reel ?** — a) La durée et le filtre · b) ✅ Le hook et le taux de partage · c) Le nombre de hashtags et l'heure de publication
7. **Que fais-tu AVANT d'utiliser un rush du Drive ?** — a) Je le compresse · b) ✅ Je le renomme avec un 👍 pour qu'aucun autre clipper ne le reprenne · c) Je demande l'autorisation
8. **La montée en cadence, c'est :** — a) 10 Reels/jour dès la semaine 1 · b) ✅ +1 Reel/jour chaque semaine (semaine 1 = 1/jour, semaine 2 = 2/jour…) · c) On publie quand on a l'inspiration
9. **Les Reels d'essai se débloquent à :** — a) ✅ 200 followers, variantes montrées aux non-followers · b) 1 000 followers · c) Ils sont disponibles dès la création
10. **On publie sur TikTok ?** — a) Oui, c'est le plus gros volume · b) ✅ Non : pas de clics ni de subs — Instagram + pages Facebook uniquement
*(Bonus/11 : la fréquence du reporting Discord ? → quotidienne.)*

## Les 3 règles de fonctionnement (côté Gaëtan/manager)

1. **La règle du renvoi** : toute question dont la réponse est dans la formation ou la FAQ → **on renvoie le lien du chapitre**, on ne re-répond pas. Répondre récompense le non-visionnage (« ce que tu récompenses, tu l'obtiens »). Le temps gagné va dans les retours sur les Reels — ce qui fait vraiment progresser.
2. **FAQ vivante** : une question posée 2 fois = une ligne dans le canal `#faq` (« expliqué 2 fois = écrit », [[Documentation et SOP]]). La FAQ est triée par fiche (J0 / warm-up / posting / cadence / essais).
3. **Mesurer au lieu de deviner** : Loom donne le **taux de complétion par viewer** — à regarder avant de conclure « ils ne regardent pas ». Le quiz donne la vraie mesure d'entrée ; les fiches réduisent le besoin de re-visionnage.

## Ce qui a changé vs la formation d'origine

Le **mindset (8 min) passe à la fin** du parcours — c'est la partie la plus zappée en ouverture, et la plus utile les jours de traversée du désert (la fiche 4 y renvoie). L'opérationnel commence à la 30e seconde. Le Loom n'est pas re-tourné : on le re-chapitre au besoin, c'est tout.

> [!warning] Sécurité
> Ces fiches et la formation décrivent des tactiques multi-comptes qui vivent en zone grise CGU ([[Machine Instagram-Facebook en masse|dette structurelle documentée]], [[Risques légaux et éthiques de l'OFM]]) — **documents internes, jamais publics**. ⚠️ Rappel du flag journalisé : la vidéo YouTube « stratégie » publique référencée dans le Loom est à passer **en non répertoriée**.
