---
titre: "Machine Instagram-Facebook en masse"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-10
tags: [ops/trafic, ops/instagram, ops/sop, contexte/business]
liens_forts: ["[[Trafic et réseaux sociaux pour l'OFM]]", "[[Reporting clippers]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Risques légaux et éthiques de l'OFM]]"]
---

# Machine Instagram-Facebook en masse (le modèle Geelark)

> [!tip] Verdict
> L'unité de base de la machine n'est pas « le compte », c'est **le pod : 1 VA × 1 créatrice × 3 comptes Instagram + 3 pages Facebook**, chacun dans son environnement Geelark isolé avec son proxy français dédié. La règle d'or : **1 compte = 1 profil cloud = 1 IP = 1 identité comportementale, pour toujours**. 80 % des bans viennent de la violation de cette règle (logins croisés, IP partagées, cadence de robot). Tu scales en ajoutant des pods, jamais en surchargeant un pod. Et tu pilotes au [[Reporting clippers|reporting individuel]] : BAN / actifs / cadence / clics — pas aux vues.

> [!warning] À lire les yeux ouverts
> Le multi-comptes coordonné et déguisé **viole les CGU de Meta** (« inauthentic behavior »). Ce n'est pas une zone grise, c'est une dette existentielle documentée dans [[Risques légaux et éthiques de l'OFM]] : l'espérance de vie des tactiques décroît, les purges arrivent par vagues, et un réseau détecté peut sauter **en entier** (détection par graphe : mêmes contenus, mêmes liens, mêmes patterns). Le modèle se construit donc en **assumant un taux de perte permanent** (les bans sont un coût d'exploitation, pas un accident) et en diversifiant : les pages Facebook, le SFS et le canal propriétaire ne meurent pas quand un batch IG saute. C'est exactement pour ça que Maxime tourne à grande échelle : il a industrialisé le remplacement, pas l'immortalité des comptes.

## L'architecture (ce que fait Maxime, formalisé)

```
Créatrice → rushs (Emma) → clips uniquisés (Rianah/Opus Clip)
    → POD (1 VA) : 3 IG + 3 pages FB sur Geelark + proxies FR
        → link-in-bio intermédiaire → OF/MYM (tracking par lien dédié)
            → chatting (Maxence) → LTV
```

- **Geelark** : téléphones Android dans le cloud — chaque profil est un vrai environnement mobile isolé (empreinte device unique), avec gestion d'équipe intégrée (rôles, permissions par profil, logs d'opérations, transfert de profils). C'est ce qui permet de donner à un VA malgache l'accès à SES 6 profils et rien d'autre — et de récupérer le pod en 1 clic si la personne part. Déjà dans ta stack ([[LTP Models]]).
- **Proxies** : 1 proxy **français résidentiel ou mobile 4G** dédié par compte (jamais de datacenter, jamais partagé entre comptes). L'IP fait partie de l'identité du compte : elle ne change pas de pays, jamais.
- **Le pod de 6** (3 IG + 3 FB) : c'est le maximum qu'un humain peut opérer **de façon humaine** (scroll, réponses, stories, publication) sans que le comportement devienne robotique. Plus de comptes par personne = cadence de robot = détection comportementale.

## Créer des comptes ciblant la France depuis Madagascar

**Oui, c'est faisable — la géographie de l'audience vient du contenu, pas du passeport de l'opérateur.** Ce qui détermine qui voit tes Reels : la langue, les hashtags, les sons, les interactions initiales, et l'IP du compte. Le protocole :

1. **Création directement dans Geelark** avec le proxy FR déjà actif (le compte « naît » français) — jamais depuis le téléphone perso du VA avec une IP malgache puis « déménagé ».
2. **Vérification SMS** : numéros français (SIM physiques FR en stock chez toi, ou service de numéros dédiés — éviter les numéros jetables recyclés, taux de ban élevé). C'est TON goulot logistique à toi, pas celui des VAs : fournis-leur des comptes déjà créés/vérifiés quand c'est possible.
3. **Alternative** : comptes IG **aged français** achetés — plus rapides mais risqués (origine invérifiable, revente multiple) ; si tu en achètes, change tout (mot de passe, mail, 2FA) et warmup 2 semaines avant le premier post.
4. **Cohérence permanente** : le VA se connecte toujours via Geelark (donc IP FR), jamais depuis son appareil. Fuseau de publication = heures françaises (géré par la planification, pas par le VA qui se lève la nuit).

### Le test targeting MG (lancé semaine du 14 juillet, verdict à J+15-20)

Décision de Gaëtan : tester d'abord la **création depuis les téléphones malgaches** (zéro coût, zéro friction) avant d'imposer Geelark. Honnêteté sur le pari : un compte né sur IP malgache démarre avec un signal géo défavorable (l'explore initial servira de l'audience locale/africaine francophone) — la langue, les sons FR et les hashtags peuvent le rattraper, mais ce n'est pas garanti. D'où le test empirique, **avec les critères écrits AVANT** (sinon le verdict se fera au feeling) :

| Critère (à J+15-20) | Seuil de succès | Où le lire |
|---|---|---|
| Audience FR + Europe francophone | **≥ 40-50 %** des vues | Statistiques IG (audience/villes) |
| Clics link-in-bio géolocalisés FR | Majorité FR | GetAllMyLinks/Infloww |
| Subs attribués | > 0 et LTV normale | Tracking par compte |
| Taux de ban du batch | < 25 % | Reporting dimanche |

**Verdict** (~31 juil.-5 août, depuis la France) : seuils atteints → on continue sur téléphones MG (économie réelle) ; seuils ratés → bascule **Geelark + proxies FR** pour les MG (la ligne budget était prévue) ; la **ferme de téléphones physiques** reste l'option de septembre, à construire en France ([[Semaine de passation (14-20 juillet)|hors périmètre de la semaine de départ]]). Ne pas prolonger un test raté « pour voir » : 20 jours suffisent, chaque semaine de plus coûte du volume sur les créatrices ([[Coût d'opportunité]]).

## Le warmup (les 3 semaines qui décident de la durée de vie)

Un compte neuf qui poste du contenu sexy à J+1 avec un lien en bio est mort en 2 semaines. Le trust d'un compte se construit :

| Phase | Durée | Actions | Interdits |
|---|---|---|---|
| **1. Humain passif** | J1-J7 | Scroll 15-20 min/j, likes modérés, follow 5-10/j de comptes FR de la niche, regarder des Reels en entier | Poster, lien en bio, DM |
| **2. Éveil** | J8-J14 | Photo de profil, bio (SANS lien), 2-3 stories, 1er post soft, quelques commentaires | Lien OF/MYM, contenu suggestif |
| **3. Montée** | J15-J21 | 1 Reel/jour, stories quotidiennes, lien **link-in-bio intermédiaire** ajouté en fin de phase | Cadence max, DM de masse |
| **4. Production** | J22+ | Cadence cible (1-2 Reels/j, 2-4 stories/j), rotation des formats | Toujours : pas de nudité, pas de mention OF explicite |

**Règles de survie permanentes** : jamais de lien OnlyFans direct en bio (link-in-bio intermédiaire type GetAllMyLinks, déjà ta stack) ; contenu 100 % safe plateforme (ta doctrine existante : « safe sur plateforme, conversion hors plateforme ») ; pas de texte d'appel explicite ; varier les légendes/sons entre comptes (deux comptes qui postent le même clip avec la même légende à la même heure = signature de réseau) — c'est le rôle de l'uniquisation ([[Projets|TikFusion]], variantes Opus Clip).

## Les pages Facebook : la surface résiliente (ton avantage sous-exploité)

Déjà identifié dans [[LTP Models]] : Facebook Pages = **moins de détection, reach organique élevé sur l'audience 30+ (celle qui paie le mieux)**, et les Reels FB recyclent tels quels les Reels IG. Spécificités : une page FB s'adosse à un profil — les profils anciens/réels tiennent mieux que les profils neufs ; une page bannie ne tue pas les autres pages si les admins sont séparés (d'où les pods) ; la cadence peut être plus agressive qu'IG (2-4 posts/j). Verdict : dans chaque pod, les 3 pages FB ne sont pas la roue de secours — **c'est le deuxième moteur**, souvent meilleur en €/clic sur ta niche.

## Cadences et limites de sécurité (par compte, en production)

- IG : **1-2 Reels/jour**, 2-4 stories/jour, follows ≤ 30-50/jour espacés, pas de DM sortants de masse (le signal de sollicitation est le déclencheur n°1 des bans Meta sur ta niche — [[LTP Models|déjà documenté]]).
- FB : 2-4 posts/jour/page, groupes avec extrême parcimonie.
- **Tout pic soudain est un signal** : montée de cadence progressive, jamais ×3 du jour au lendemain.
- Un compte restreint (reach coupé, action block) : **pause 72 h totale**, puis reprise en phase 2 de warmup. Un compte banni : ne JAMAIS recréer immédiatement sur le même proxy/profil.

## KPI et pilotage (depuis ton téléphone)

Extension directe du [[Reporting clippers]] : par VA et par compte, chaque vendredi — **comptes actifs / bans de la semaine / cadence tenue (posts réels vs prévus) / reach moyen / clics link-in-bio / subs attribués** (lien tracké par compte : GetAllMyLinks/Infloww). Le KPI roi du pod : **subs attribués / semaine / pod**, et son garde-fou : le **taux de ban mensuel** (< 20-25 % des comptes = machine saine ; au-dessus = problème de process, on arrête d'ajouter des pods et on répare le warmup). La LTV reste le garde-fou global du [[Sprint été - croissance sans moi|sprint]] : un pod qui ramène du volume à LTV effondrée pollue le chatting.

## Scaling : l'ordre des opérations

1. **Prouver le pod standard** (1 VA, 6 comptes, 1 créatrice) avec le playbook ci-dessus → 4-6 semaines.
2. **Documenter** en Loom + checklist ([[Documentation et SOP]]) → la formation devient copiable ([[Checklist formation clipping|comme le clipping]]).
3. **Ajouter des pods** (recruter = [[Équipe marketing - structure et rémunération (FR × MG)|la vraie contrainte, voir la page rémunération]]), créatrices à plus forte LTV d'abord : Chloé et Sophie (équipe FR), puis Maddie/Sarah/Jade (équipe MG).
4. **Jamais** : surcharger un pod existant au lieu d'en créer un nouveau, ou lancer des pods sur les créatrices à LTV faible (Amanda : décision cut-ou-garde AVANT d'y mettre un pod — [[Coût d'opportunité]]).

## Sources

[^1]: GeeLark, plateforme cloud phone multi-comptes (environnements Android isolés, gestion d'équipe, automatisation), geelark.com, 2026.
[^2]: Doctrine trafic existante de l'agence et retours terrain (Maxime, clippers) — [[LTP Models]], [[Trafic et réseaux sociaux pour l'OFM]].
[^3]: Politiques Meta sur le comportement inauthentique et la sollicitation sexuelle (transparency.meta.com), évolutives — d'où le statut de dette CGU permanent.
