---
titre: "Architecture Discord - simple au quotidien (14 septembre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-14
tags: [ops/discord, ops/clippers, ops/délégation, méthode/simplification]
liens_forts: ["[[Bot FAQ clippers (Discord)]]", "[[Fiche de poste - Manager marketing (Jonas)]]", "[[Analyse complète de l'agence et plan de simplification (14 septembre 2026)]]", "[[Journal de coaching]]", "[[Théorie des contraintes]]"]
---

# Architecture Discord : simple au quotidien (14 septembre 2026)

> [!tip] Verdict
> **Le serveur doit répondre à une seule question par personne : « où je vais ce matin ? ».** Aujourd'hui il y a ~20 salons fixes, 5 rôles, 4 grilles de permissions, des compteurs qui se renomment et des salons dont personne ne connaît la fonction. La cible : **5 catégories, 12 salons fixes**, et pour chacun des quatre rôles humains, **trois endroits maximum** dans une journée. Tout ce qui n'est pas dans cette carte s'archive (`!archiver`), et la visibilité s'applique en une commande (`!acces appliquer`), parce que le bot range les salons par leur nom.

## 1. Ce qui existe (lu dans le code du bot et la base)

Le bot connaît trois étages d'accès, appliqués par `!acces` selon le **nom** du salon : **vitrine** (tout le monde : candidature, annonces, formation, assistant, tips, dopamine, bump, compteurs), **paie par grille** (rémunération-fr / -int et bonus-fr / -int, visibles dès la candidature reliée par les rôles Grille France / Grille International, puis par les signés), **réservé aux signés** (ressources, reporting, discussion-fr / discussion-int). À côté : une catégorie par créatrice (le salon de ses rushs et modèles, plus un salon privé par clipper créé par `!creatrice`, où tombent le bilan du matin et les codes 2FA), un salon admin, un salon manager, deux salons-compteurs renommés toutes les dix minutes. Rôles : Clipper, Team France, Team Madagascar (alias International), Grille France, Grille International, Manager, admin.

**Ce qui complique la vie** : quatre salons de paie pour deux grilles ; deux salons de discussion pour une équipe qui parle français des deux côtés ; #tips séparé de #ressources ; #dopamine à côté de #annonces ; #bump et deux compteurs qui n'ont plus de raison d'être (recrutement FR fermé, [[Analyse complète de l'agence et plan de simplification (14 septembre 2026)|kill-list du 14/09]]) ; un rôle « Clipper » qui ne sert qu'à compter. Et la vraie source de confusion : personne n'a de carte. Les clippers demandent « où je poste ma question ? » et Jonas « où je regarde ça ? » ([[Journal de coaching]], entrée 5 du 14/09).

## 2. La cible : 5 catégories, 12 salons fixes

| Catégorie | Salons | Qui voit | À quoi ça sert, en une phrase |
|---|---|---|---|
| 🚪 **ARRIVÉE** | #bienvenue · #candidature · forum #formation · #assistant-ia | tout le monde | Comment ça marche, le formulaire, la vidéo et les 6 fiches, le bot 24 h/24 |
| 💶 **PAIE** | #rémunération-fr · #rémunération-int | par grille, puis signés | Un message épinglé par grille : fixe, commission, prime, dates du 16 et du 1er (les bonus y sont, plus de salon #bonus) |
| 🎬 **ÉQUIPE** | #annonces · #ressources · #reporting · #discussion | signés | Les annonces et les victoires (ex-#dopamine), captions + liste des créatrices (ex-#tips), le formulaire du dimanche, une seule discussion pour les deux équipes |
| 👩 **CRÉATRICES** | une catégorie par créatrice active : #chloé (rushs et modèles) + un salon privé par clipper | les clippers de cette créatrice, le manager | Le lieu de travail : rushs, retours, bilan du matin, codes |
| 🛠️ **STAFF** | #manager · #admin | Manager / Gaëtan | Le rapport du matin et les candidats (manager) ; l'hebdo du lundi et les pannes (Gaëtan) |

**Ce qui disparaît** : #tips, #dopamine, #bump, les deux compteurs, #bonus-fr, #bonus-int, #discussion-fr, #discussion-int, et toute catégorie d'une créatrice gelée (Amanda, Lila, Capucine, Lily, Alice : archivées, pas supprimées). **Rôles** : Candidat (= Grille France / Grille International, donnés par le bot à la candidature reliée), Team France, Team International, Manager, Admin. Le rôle « Clipper » ne sert qu'au compteur : il part avec lui.

## 3. La journée de chacun (trois endroits maximum)

- **Le candidat** : ses messages privés avec le bot (numéro, quiz, test, J'ACCEPTE) et #assistant-ia. Il ne navigue jamais : le bot lui envoie chaque étape.
- **Le clipper** : ① son salon privé le matin (4 lignes : hier, vues et abonnés, journée validée, alerte) ; ② le salon de sa créatrice (rushs, ses retours) ; ③ le dimanche, #reporting. Une question : #assistant-ia, puis son manager dans le salon de la créatrice.
- **Jonas** : ① #manager le matin (un seul rapport : marketing + candidats) ; ② les salons créatrices pour les relectures ; ③ les salons privés au créneau (codes, comptes). Ses commandes : `!creatrice`, `!sortie`, `!subs`, `!primes`, `!test-ok`, `!aide`.
- **Gaëtan** : #admin le lundi (`!hebdo`, `!ltv`), et rien d'autre. Il n'est mentionné que pour contrat, paiement, facture, parrainage, arnaque, comme le dit la base ([[Bot FAQ clippers (Discord)]]).

## 4. Comment on y va (une demi-heure, une fois, réversible)

1. **Renommer et fusionner** : épingler les bonus dans #rémunération-fr et #rémunération-int ; épingler les captions et la liste des créatrices dans #ressources ; renommer #discussion-int en #discussion.
2. **Archiver** : `!archiver #tips #dopamine #bonus-fr #bonus-int #discussion-fr` puis les catégories des créatrices gelées ; supprimer #bump et les deux compteurs (et leurs variables Railway).
3. **Appliquer la visibilité** : `!acces` (aperçu) puis `!acces appliquer` : le bot range chaque salon dans son étage d'après son nom ; #discussion est désormais reconnu comme salon des signés (règle ajoutée le 14/09).
4. **Vérifier** : `!audit` (carte du serveur et écarts à la doctrine) et `!pourquoi @membre #salon` si quelqu'un ne voit pas ce qu'il devrait.
5. **Épingler la carte** : dans #bienvenue, le tableau de la section 2 en cinq lignes. C'est la seule documentation dont un nouveau a besoin.

## 5. Ce qui casse ça (avocat du diable)

- **La fusion des discussions** mélange Français et Malgaches : c'est voulu (même langue, même méthode, même paie au 16 et au 1er), mais si les Français se plaignent d'une grille différente en public, la séparer à nouveau prend une minute.
- **Le bot repère les salons par leur nom** : un salon renommé hors convention sort de la doctrine et devient visible ou invisible par accident. Règle : on ne renomme pas sans `!acces` derrière.
- **Archiver n'est pas supprimer** : les archives restent lisibles par les admins ; un salon archivé avec des identifiants dedans (cas du message épinglé WhatsApp du 14/09) reste une fuite en attente. Les identifiants vivent dans les salons privés des clippers, nulle part ailleurs.
- **La simplicité tient à la discipline** : un nouveau salon « juste pour ça » est le début du prochain bordel. Le test avant d'en créer un : dans quelle catégorie, pour quel rôle, quelle question du matin ça résout.
