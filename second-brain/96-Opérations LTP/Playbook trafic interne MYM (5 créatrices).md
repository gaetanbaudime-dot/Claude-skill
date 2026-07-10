---
titre: "Playbook trafic interne MYM (5 créatrices)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-07-10
tags: [ops/mym, ops/trafic, ops/sop, contexte/business]
liens_forts: ["[[Stratégie trafic interne MYM]]", "[[Sprint été - croissance sans moi]]", "[[LTP Models]]", "[[SOP - Machine à contenu hebdomadaire]]"]
---

# Playbook trafic interne MYM — 5 créatrices

> [!tip] Verdict
> Le plan actuel est **quasi le bon** : 5 publics/jour à 8/12/16/20/23h, les 2 meilleurs restent publics à vie, les 3 autres passent privés à J+3/J+4, 5 stories/jour. On le rend **expérimental et pilotable** : 3 stratégies réparties sur 5 créatrices (2 « full public », 2 « hybrid 48h », 1 « hybrid 4 j »), tout le reste tenu constant, décision sur **CA net / post public** et **fans intéressés**, jamais sur les vues seules. Durée : **21 à 30 jours**, puis crossover. Le pilotage se fait depuis un dashboard (une ligne par post). C'est le pôle « trafic MYM » du [[Sprint été - croissance sans moi|sprint été]].

## Diagnostic du rapport Judith (juillet 2026) — où est vraiment le goulot

**Deal juillet : target 20 000 € → 2 slots carousel en août.** Condition ⚠️ : la target est atteinte **et** les deux créatrices sous condition (rôles *Flagship* et *Rebuild* ci-dessous) **ne baissent pas** vs juin. Au 8 juillet : **6 574 € = 33 %**, soit ~822 €/jour → sur un rythme d'environ **25 k€/mois**, donc **en avance** sur la target (il restait ~13 400 € à faire, ~560 €/jour). La target est atteignable ; le vrai enjeu est de **ne pas laisser Flagship/Rebuild décrocher** et de réparer les KPI amont.

Tendance CA net G&M (portefeuille à date) : **17,2 k (fév) → 16,3 (mars) → 14,1 (avr) → 14,8 (mai) → 14,7 (juin) → 6,6 (juil., arrêté au 8)**. Le CA total a glissé sur le S1 ; juillet repart. Les 5 KPI du rapport disent *pourquoi* :

| KPI (définition MYM) | Lecture actuelle | Benchmark MYM | Verdict |
|---|---:|---|---|
| **External traffic contribution** (part des nouveaux fans externes) | ~6 % | moy 10 % / top 35 % | ❌ **Goulot n°1** : pas assez de fans externes qualifiés amenés sur MYM |
| **Qualified / willing to pay** (intention de payer du trafic acquis) | ~4 % | — | ❌ Trafic acquis pas assez acheteur |
| **Profile attraction** (abos / vues profil) | ~8 % | moy 13 % / top 18 % | ❌ **Goulot n°2** : le profil ne convertit pas assez les visiteurs |
| **Ability to convert** (1ers achats payants / 1ers abos) | ~23 % | moy 8 % / top 20 % | ✅ Au-dessus du top — **ne pas casser** |
| **Qualified chatting** (achats PPV / abos) | ~39 % | — | ✅ Fort — le chat/PPV est solide |

**Traduction actionnable.** Le chatting et la conversion en payant sont excellents (cohérent avec la LTV réparée côté Maxence, cf. [[LTP Models]]). Le problème est **en amont** : pas assez de trafic externe **et** un profil qui ne transforme pas assez les vues en abonnés. Donc la priorité n'est pas « plus de posts publics » dans le vide — c'est **plus de contenus publics recommandables → plus de fans intéressés → meilleure attraction profil → plus de nouveaux abonnés (internes + externes) → plus de CA PPV/MOD** (le [[Stratégie trafic interne MYM|modèle d'attractivité]]). Les deux chantiers qui bougent l'aiguille ce mois-ci : **(1) attraction profil** (bio, photo, bannière, 20-30 privés/floutés visibles, 10 MOD nommés, feed public clean) et **(2) trafic externe qualifié** (SFS + tracking links par source).

## La SOP quotidienne (par créatrice)

| Heure | Action |
|---|---|
| 08h00 | Post public 1 |
| 09h30 | Story 1 (teaser du post du matin) |
| 12h00 | Post public 2 |
| 13h30 | Story 2 (sondage / question = CTA d'interaction) |
| 16h00 | Post public 3 |
| 17h30 | Story 3 (behind-the-scenes / personnalité) |
| 20h00 | Post public 4 |
| 21h30 | Story 4 (teasing du meilleur post du jour + privé/MOD) |
| 23h00 | Post public 5 |
| 23h45 | Story 5 (CTA abonnement / MOD) |

**Mix public quotidien (fixe pendant le test) : 3 photos + 2 vidéos.** Répartition par « job créatif » : 2 découvrabilité clean (visage/ligne du corps, fond propre), 2 tease/tension (suggestif non explicite), 1 personnalité/lifestyle. **Règle stricte : pas de texte sur le média, pas d'emoji, pas d'explicite.** CTA uniquement en légende/story.

**En parallèle chaque jour :** 5 stories, **4-6 privés/floutés** (garder le feed global à ~80 %+ flouté), chat SLA < 30 min sur les heures staffées (réponses enregistrées + messages auto). **Chaque public doit mener vers un privé/MOD derrière.**

**Chaque semaine :** 2 pushs payants/abonnés + 1 push intéressés/anciens (fenêtre 7 j) ; chaque push payant est **ajouté au MOD** par défaut ; SFS au maximum (cf. cadence sprint : 2/sem/créa OF, 1/sem/créa MYM) ; codes promo PPV à **durée ou usage limité** (rareté).

## Règle publique/privé : quels posts restent publics

On note chaque post à sa fenêtre de revue (**J+2 pour hybrid 48h, J+4 pour hybrid 4 j**) avec un score :

```
Score public = 0,30·(index vues) + 0,25·(likes/100 vues) + 0,25·(intéressés/100 vues) + 0,20·(conversion abo/100 vues)
```

- Les **2 meilleurs scores du jour restent publics à vie** (bibliothèque de winners evergreen).
- Les **3 autres passent privés** à la fenêtre choisie.
- **Override** : un post reste public s'il est dans le **top quartile intéressés/100 vues** OU **CA net/100 vues** (protège les « sleepers » très monétisables même sans le plus de vues).
- Un post beaucoup de vues / zéro like/intention → privé plus vite.

## Le test sur les 5 créatrices (aliasées par rôle)

> Mapping rôle → compte réel gardé **hors repo**. Les deux créatrices sous condition du deal (Flagship, Rebuild) ne doivent pas baisser vs juin.

| Rôle | Stratégie | Règle de durée de vie publique | Question testée | Priorité |
|---|---|---|---|---|
| **Flagship** (premium, gros historique de vues) | Hybrid propre | top 2 publics à vie, 3 privés à **J+4** | Tenir le CA sans transformer le compte en gratuit cheap | Qualité > volume sale ; **ne pas baisser vs juin** |
| **Réactivation** (historique, posts récents plus faibles) | Hybrid agressif | top 2 publics, 3 privés à **J+3** | Raviver un compte via intéressés + PPV/MOD | Push intéressés/anciens + MOD agressif |
| **Rebuild** (attraction profil basse) | Acquisition / test créatif | garder publics les meilleurs ratios likes/vues, privé rapide sur les faibles | Faire remonter profile attraction 8 % → 11-13 % | Refaire bio/photo/bannière ; **ne pas baisser vs juin** |
| **Discovery** (jeune compte, vues correctes) | Full public | tout reste public | L'inventaire public permanent maximise-t-il la découverte ? | Maximiser les signaux algo propres |
| **Evergreen** (gros inventaire ancien à fortes vues) | Full public / protection | préserver les vieux winners publics, ne pas polluer | Les vieux posts publics continuent-ils de ramener du trafic ? | Protéger les assets qui rankent déjà |

**Règle d'or expérimentale :** ne bouge qu'**une** vraie variable (durée de vie publique). Tout le reste identique sur les 5 : horaires, mix de format, intensité stories, niveau de chat, pushs, qualité bio, logique MOD/PPV, tracking. 5 créatrices = **écran exploratoire**, pas une preuve causale → si un gagnant émerge, **crossover de 21 jours** où ≥ 2 créatrices échangent de stratégie.

## Le dashboard (piloter à distance, une ligne par post)

**KPI roi : CA net total / post public publié.** Puis : **fans intéressés / 100 vues publiques**, puis **abonnés / 100 vues profil**. Jamais les vues seules.

Colonnes post-level à logger : `Post ID · Créatrice · Stratégie · Format · Créneau · Public depuis · Vues H+6 · Vues J+1 · Vues J+3 · Likes · Likes/100 vues · Intéressés · Abos · CA net J+7 · Reste public ? · Raison`.

Colonnes day-level (par créatrice) : `Posts publics · Vues publiques · Likes · Intéressés · Abos · CA abo · CA PPV/MOD · CA total · CA/post public · Stories · Pushs · Visites externes · CA externe attribué`.

Revues : **diagnostic léger à J7**, mi-parcours J14, **lecture principale J21**, lecture forte J30. S'inscrit dans le [[Sprint été - croissance sans moi|rituel du vendredi]] (le trafic MYM devient une ligne du tableau de bord hebdo auto-reporté).

## Règles de décision (winner vs faux winner)

**Winner** — une stratégie gagne si : **+15 % de CA/post public** *ou* **+15 % d'intéressés/100 vues**, **sans** baisse de conversion profil→abo et **sans** baisse du CA PPV/MOD.
**Faux winner (piège du full public)** : plus de vues, mais moins de likes/vues, moins d'intéressés, moins de CA/post → **no-go**.
Seuils pratiques (échantillon opérationnel, pas académique) : gagnant seulement si il bat le suivant de **≥ 15 % sur CA/post** et ne perd pas > 5 % sur la conversion ; **±10 % = égalité → crossover** ; rejet auto si une stratégie augmente la portée mais baisse le CA/post de **> 10 % sur 2 semaines**.

## Plan 30 / 90 jours (condensé)

- **J1-3 — Setup & nettoyage** : bio ultra claire, photo/bannière clean, **20-30 privés/floutés visibles**, **10 MOD** nommés, retirer tout public avec texte/emoji/montage cheap, **tracking links par source** (IG, TikTok, X, SFS, Ads…). Objectif : un profil qui donne envie en < 5 s (attaque directe du KPI *profile attraction*).
- **J4-10 — Lancement du protocole public** (SOP ci-dessus).
- **J11-21 — Décision des winners** (score J+3/J+4, top 2 publics à vie).
- **J22-30 — Scaling des formats gagnants** : cloner les angles/horaires/ratios qui gagnent, arrêter le « random ».
- **Cibles J30** : External traffic 6 % → **10-12 %**, Profile attraction 8 % → **11-13 %**, Qualified 4 % → **5-6 %**, garder Ability to convert > 20 % et Qualified chatting > 35 %.
- **J31-60 — Crossover & scaling** : inverser les 2 meilleures stratégies, tests secondaires (5 vs 10 stories, mix photo/vidéo, J+3 vs J+7, top 2 vs top 3 publics). Test « bug MyPulse » **uniquement ici**, sur un compte secondaire, 7 j, arrêt si les ratios baissent.
- **J61-90 — Système agence** : SOP quotidienne/hebdo figée, revue perf chaque soir. **Cibles J90** : External 20-25 %, Profile attraction 15-18 %, Qualified 7-10 %, CA/post public maximisé.

## Garde-fous

**Bug MyPulse = risque CGU + relationnel** (contact AMB direct) → hors production les 30 premiers jours, cf. [[Stratégie trafic interne MYM]] et [[Risques légaux et éthiques de l'OFM]]. **Surexposition** : trop de public gratuit tue l'urgence d'abonnement → garder les winners evergreen seulement en B/C, backlog flouté fort. **Résultats confondus** : tout pic externe fausse le test → tracking links obligatoires ([[Espérance mathématique et asymétries|isoler le signal du bruit]]). **Chat bottleneck** : réponses enregistrées + scénarios de messages auto. Ancrage cadres : [[Systèmes et process]], [[Coût d'opportunité]], [[Documentation et SOP]], [[Théorie des contraintes]]. Cette SOP complète la [[SOP - Machine à contenu hebdomadaire|machine à contenu]] (le trafic MYM consomme le même flux de rushs) et se reporte dans le [[Reporting clippers|reporting]] hebdo.
