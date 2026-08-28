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

> [!warning] Mise à jour doctrine (23/07/2026)
> Plusieurs consignes de cette page ont été **actualisées par la veille** [[État de l'art clipping Instagram (juillet 2026)]] : le warmup « 48 h pour éduquer l'Explorer » est partiellement périmé (Mosseri a démonté le lien consommation→reach ; consensus 7-14 j) ; l'**uniquisation cosmétique** (varier chaque exécution) ne suffit plus depuis le crackdown du 30/04/2026 et vaut évasion de détection ⚠️ → la parade propre est **transformation matérielle + collab posts + Content Protection activé par la créatrice**. Les 3 pages FB de reposts sont en 1re ligne de la répression. Lire l'état de l'art avant d'appliquer les cadences ci-dessous.

> [!tip] Verdict
> L'unité de base de la machine n'est pas « le compte », c'est **le pod : 1 VA × 1 créatrice × 3 comptes Instagram + 3 pages Facebook**, chacun dans son environnement Geelark isolé avec son proxy français dédié. La règle d'or : **1 compte = 1 profil cloud = 1 IP = 1 identité comportementale, pour toujours**. 80 % des bans viennent de la violation de cette règle (logins croisés, IP partagées, cadence de robot). Tu scales en ajoutant des pods, jamais en surchargeant un pod. Et tu pilotes au [[Reporting clippers|reporting individuel]] : BAN / actifs / cadence / clics — pas aux vues.

> [!warning] À lire les yeux ouverts
> Le multi-comptes coordonné et déguisé **viole les CGU de Meta** (« inauthentic behavior »). Ce n'est pas une zone grise, c'est une dette existentielle documentée dans [[Risques légaux et éthiques de l'OFM]] : l'espérance de vie des tactiques décroît, les purges arrivent par vagues, et un réseau détecté peut sauter **en entier** (détection par graphe : mêmes contenus, mêmes liens, mêmes patterns). Le modèle se construit donc en **assumant un taux de perte permanent** (les bans sont un coût d'exploitation, pas un accident) et en diversifiant : les pages Facebook, le SFS et le canal propriétaire ne meurent pas quand un batch IG saute. C'est exactement pour ça que Maxime tourne à grande échelle : il a industrialisé le remplacement, pas l'immortalité des comptes.

## L'architecture (ce que fait Maxime, formalisé)

```
Emma (trends + management) → créatrice filme → Drive / vidéos YouTube
    → POD (1 VA) : clippe (Opus Clip) + poste sur 3 IG + 3 pages FB
        → link-in-bio intermédiaire → subs OF/MYM (tracking par lien dédié)
            → chatting + masse messages payants (Maxence) → €€€
```

Le pod **clippe ET poste** (accès Opus Clip fourni aux FR ; les MG démarrent avec les clips fournis par Rianah puis montent en autonomie) : un maillon de moins dans la chaîne, une file d'attente et un point de défaillance en moins ([[Théorie des contraintes|note TOC]]).

- **Geelark** : téléphones Android dans le cloud — chaque profil est un vrai environnement mobile isolé (empreinte device unique), avec gestion d'équipe intégrée (rôles, permissions par profil, logs d'opérations, transfert de profils). C'est ce qui permet de donner à un VA malgache l'accès à SES 6 profils et rien d'autre — et de récupérer le pod en 1 clic si la personne part. Déjà dans ta stack ([[LTP Models]]).
- **Proxies** : 1 proxy **français résidentiel ou mobile 4G** dédié par compte (jamais de datacenter, jamais partagé entre comptes). L'IP fait partie de l'identité du compte : elle ne change pas de pays, jamais.
- **Le pod de 6** (3 IG + 3 FB) : c'est le maximum qu'un humain peut opérer **de façon humaine** (scroll, réponses, stories, publication) sans que le comportement devienne robotique. Plus de comptes par personne = cadence de robot = détection comportementale.

## Créer des comptes ciblant la France depuis Madagascar

**Oui, c'est faisable — la géographie de l'audience vient du contenu, pas du passeport de l'opérateur.** Ce qui détermine qui voit tes Reels : la langue, les hashtags, les sons, les interactions initiales, et l'IP du compte. Le protocole :

1. **Création directement dans Geelark** avec le proxy FR déjà actif (le compte « naît » français) — jamais depuis le téléphone perso du VA avec une IP malgache puis « déménagé ».
2. **Vérification SMS** : numéros français (SIM physiques FR en stock chez toi, ou service de numéros dédiés — éviter les numéros jetables recyclés, taux de ban élevé). C'est TON goulot logistique à toi, pas celui des VAs : fournis-leur des comptes déjà créés/vérifiés quand c'est possible.
3. **Alternative** : comptes IG **aged français** achetés — plus rapides mais risqués (origine invérifiable, revente multiple) ; si tu en achètes, change tout (mot de passe, mail, 2FA) et warmup 2 semaines avant le premier post.
4. **Cohérence permanente** : le VA se connecte toujours via Geelark (donc IP FR), jamais depuis son appareil. Fuseau de publication = heures françaises (géré par la planification, pas par le VA qui se lève la nuit).

### Peut-on cibler la France depuis un téléphone au Bénin / Madagascar ? (la réponse ferme)

**Oui, c'est possible — mais ce n'est PAS automatique, et l'IP est le handicap réel à compenser.** Instagram décide où pousser un Reel à partir de plusieurs signaux de localisation : **IP, SIM/opérateur, langue de l'appareil, langue du contenu, sons utilisés, hashtags, et géographie de l'audience déjà acquise**. Un téléphone brut au Bénin/Madagascar donne une **IP africaine** = le signal le plus fort pointe vers la mauvaise géo, et l'explore initial servira de l'audience locale. La bonne nouvelle : les **Reels ont un moteur de distribution à part, très piloté par l'audio et la langue** — donc les signaux de contenu peuvent dominer si on les empile délibérément. Ce n'est jamais garanti à 100 %, d'où le test.

**Les 6 leviers pour forcer le ciblage FR depuis l'Afrique (à appliquer TOUS, pas au choix) :**
1. **Langue de l'appareil ET du compte en français** (réglages téléphone inclus).
2. **Audio tendance FR** sur chaque Reel (le signal n°1 du moteur Reels — un son FR viral tire la distribution vers la France).
3. **Hashtags FR réels** (ceux qu'utilisent les créateurs FR de la niche, pas des traductions).
4. **Légendes + texte à l'écran en français.**
5. **Warmup ciblé FR** (phase 1 ci-dessous) : suivre et interagir avec des comptes FR de la niche → tu **ensemences la géographie de l'audience**, que l'algo réutilise ensuite (point clé : l'algo montre d'abord tes Reels à une audience proche de tes premiers followers).
6. **Heures de publication françaises.**

**La limite honnête** : sans IP française, tu joues « contenu vs IP ». Sur Reels c'est jouable (l'audio/langue pèsent lourd), mais tu pars avec un frein. Le **fix fiable à 100 %** = une **IP française** : soit **Geelark + proxy FR résidentiel/mobile** (l'IP devient française, tout s'aligne, et tu **possèdes/récupères** le compte — imbattable), soit la ferme de téléphones physiques en France. Un proxy FR installé sur le téléphone perso du VA est fragile (il l'oublie, le wifi maison fuit) → pas fiable à distance.

**Donc la stratégie en escalier** : (1) tester le téléphone brut MG/Bénin avec les 6 leviers à fond (budget zéro) ; (2) si le test échoue, **Geelark + proxy FR** pour ces pods (c'est le vrai « sûr à 100 % » que tu demandes) ; (3) ferme physique = option de septembre. Ne compte pas sur le téléphone brut comme solution définitive : compte dessus comme sur un pari à valider, avec le repli Geelark déjà budgété.

### Le test targeting MG/Bénin — ⏸️ REPORTÉ À SEPTEMBRE (décision ALL IN FR du 2026-07-12)

**Ce test ne se lance plus cet été** : la décision [[Journal de coaching|ALL IN français]] met tout le circuit international en phase 2. Les pods FR utilisent leurs téléphones en France = IP FR native = **zéro problème de targeting**. En septembre, l'international repartira directement sur **Geelark + proxy FR** (la voie sûre) — le test « téléphone brut » ci-dessous reste documenté si on veut quand même le tenter à ce moment-là, avec ses critères écrits :

| Critère (à J+15-20) | Seuil de succès | Où le lire |
|---|---|---|
| Audience FR + Europe francophone | **≥ 40-50 %** des vues | Statistiques IG (audience/villes) |
| Clics link-in-bio géolocalisés FR | Majorité FR | GetAllMyLinks/Infloww |
| Subs attribués | > 0 et LTV normale | Tracking par compte |
| Taux de ban du batch | < 25 % | Reporting dimanche |

**Verdict** (~31 juil.-5 août, depuis la France) : seuils atteints → on continue sur téléphones MG (économie réelle) ; seuils ratés → bascule **Geelark + proxies FR** pour les MG (la ligne budget était prévue) ; la **ferme de téléphones physiques** reste l'option de septembre, à construire en France ([[Sprint été - croissance sans moi|hors périmètre de la semaine de départ]]). Ne pas prolonger un test raté « pour voir » : 20 jours suffisent, chaque semaine de plus coûte du volume sur les créatrices ([[Coût d'opportunité]]).

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
