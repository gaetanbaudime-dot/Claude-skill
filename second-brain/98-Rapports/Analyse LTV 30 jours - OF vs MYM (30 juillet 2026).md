---
titre: "Analyse LTV 30 jours - OF vs MYM (30 juillet 2026)"
type: rapport
cluster: "98-Rapports"
statut: to-verify
créé: 2026-07-30
tags: [rapport/analyse, ofm/roster, méthode/ltv, ofm/trafic]
liens_forts: ["[[LTP Models]]", "[[Goulot de l'agence - l'équation du scale]]", "[[Supervision chatting (top 5) et le cas Sarah]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Analyse créatrices 30-60 jours (13 juillet 2026)]]", "[[Journal de coaching]]"]
---

# Analyse LTV 30 jours — OnlyFans vs MYM, toutes créatrices

> [!tip] Verdict
> **OnlyFans ne monétise pas mieux que MYM. C'est l'inverse, et l'écart apparent est un artefact.** Le blended brut dit OF **6,33 €/sub** contre MYM **5,34 €/sub** (+19 % pour OF) — mais retire la vague de trafic interne de Sarah (3 000 subs à 2,83 €, coût d'acquisition zéro) et MYM remonte à **7,53-9,67 €/sub**, au-dessus de l'OF hors SFS mesuré à **7,45 €/sub**. Sur les 3 créatrices présentes sur les deux plateformes, **2 monétisent mieux sur MYM** (Chloé +71 %, Jade +16 %) et une seule mieux sur OF (Amanda +48 %, cas déjà documenté). **La plateforme n'est pas le facteur de LTV — la source du trafic et le % du deal le sont.**
>
> **La conséquence la plus chère, et elle est structurelle : ta grille clippers ne paie que les subs OF.** Tu rémunères tes clippers pour alimenter la plateforme qui monétise le moins bien, et tu paies **0 €** pour un sub envoyé sur Maddy — qui est MYM-only, pèse 14 % du CA et est **priorité 1** de ta propre matrice d'allocation. C'est l'incohérence n°1 à corriger avant de recruter le clipper suivant.
>
> **Et l'honnêteté d'abord : ce rapport n'est pas la mesure que tu as demandée, parce qu'elle n'existe pas.** Il n'y a aucun compte de nouveaux subs sur la fenêtre 30/06-30/07, et les deux sources de subs existantes se contredisent **d'un facteur 2 à 5** sur la même période. Ce qui suit est le maximum défendable avec les données du vault, avec chaque incertitude étiquetée. Les 4 exports qui rendraient ça exact sont listés en fin de page — c'est 20 minutes de ton temps.

## 1. D'abord le trou : pourquoi la LTV 30 j exacte n'existe pas aujourd'hui

Trois problèmes, dont deux sont **structurels** et ne se règlent pas par un export de plus.

**① Aucun compte de subs sur la fenêtre demandée.** Les exports les plus frais (MyPulse + Infloww du **28/07**, période 01-28/07) sont des exports **chatteurs** : ils donnent le CA par créatrice et par plateforme, jamais les nouveaux abonnés. Le dernier compte de subs par plateforme date du **19/07** (dicté, 30 j glissants) et du **13/07** (dashboard MYM). Ta fenêtre réelle 30/06-30/07 n'est couverte par aucun comptage.

**② Les deux sources de subs se contredisent d'un facteur 2 à 5**, sur des fenêtres décalées de 6 jours seulement :

| Créatrice | Nouveaux subs MYM — dashboard 13/07 | Nouveaux subs MYM — dicté 19/07 | Écart | LTV qui en découle |
|---|---:|---:|---:|---|
| **Chloé** | 129 | 540 | **×4,2** | 48,84 € **ou** 12,59 € |
| **Maddy** | 1 329 | 640 | ×2,1 | 6,09 € **ou** 12,50 € |
| **Sarah** | 883 | 3 000 | **×3,4** | 5,58 € **ou** 2,83 € |
| **Jade** | 358 | 121 | ×3,0 | 5,33 € **ou** 9,92 € |
| **Amanda** | 443 | 440 | ×1,0 | 1,60 € **ou** 1,89 € |

Tant que ce n'est pas tranché, **toute LTV MYM par créatrice est fausse d'un facteur 2 à 5** et ne peut pas porter une décision d'allocation. Ce n'est pas une nuance de méthode : c'est la différence entre « Chloé vaut 4× Maddy » et « Maddy vaut 2× Chloé ». Les deux lectures existent aujourd'hui dans le vault. Hypothèses de cause (aucune confirmée) : définitions différentes de « nouveau sub » (payant vs gratuit vs unique), inclusion ou non du trafic interne MYM, ou chiffres du 19/07 arrondis de mémoire. **Fait remarquable et rassurant** : les **blended** convergent (5,34 € vs 6,98 €), donc c'est un problème de **répartition entre créatrices**, pas un dataset cassé. Les conclusions agrégées de ce rapport tiennent ; les conclusions par créatrice sont `to-verify`.

**③ La formule utilisée dans le vault n'est pas une LTV.** « CA 30 j ÷ nouveaux subs 30 j » divise le revenu de **toute la base** par le **flux entrant du mois**. Ce ratio bouge mécaniquement à l'**inverse de la croissance** : une créatrice dont l'acquisition s'arrête voit sa « LTV » exploser sans qu'un fan ne dépense un euro de plus. C'est exactement ce qui a produit le **48,84 € de Chloé** en juin-juillet (129 nouveaux subs seulement, page payante) — un chiffre qui a servi de référence « haute LTV » dans plusieurs décisions alors qu'il ne mesurait que la sécheresse de son acquisition. Une vraie LTV se mesure **par cohorte** : les subs entrés en semaine N, suivis sur 30/60/90 jours. Le protocole existe déjà dans [[Atterrissage du funnel (mesure propre avant optimisation)|le protocole d'atterrissage]] — il n'a jamais été exécuté.

## 2. Ce qui est solide : le CA par créatrice ET par plateforme (01-28/07)

Source : exports MyPulse et Infloww du 28/07, **93 % de la fenêtre demandée**. Périmètre : **CA de chat uniquement** (MYM : médias privés + pourboires ; OF : messages/PPV) — soit 66 à 94 % du CA réel selon la créatrice. Conversion à **0,90 €/$**.

| Créatrice | MYM (€) | OF (€) | Total | Part OF | Part du CA agence |
|---|---:|---:|---:|---:|---:|
| **Chloé** | 8 056 | 6 490 | **14 546** | 45 % | **36 %** |
| **Sarah** | 7 819 | 111 *(Lila Doré)* | **7 930** | 1 % | 20 % |
| **Sophie** | 0 | 7 888 | **7 888** | 100 % | 20 % |
| **Maddy** | 5 793 | 0 | **5 793** | 0 % | 14 % |
| **Jade** | 1 564 | 1 130 | **2 694** | 42 % | 7 % |
| **Amanda** | 771 | 519 | **1 290** | 40 % | 3 % |
| Alice · Capucine · Lily | 0 | 0 | **0** | — | 0 % |
| **TOTAL** | **24 003** | **16 139** | **40 142** | **40 %** | 100 % |

**Trois lectures immédiates.** ① **MYM porte 60 % du CA de chat, OF 40 %** — l'agence est plus MYM qu'OF, ce que le discours interne (« subs OF », grille de paie OF) ne reflète pas. ② Les trois créatrices bi-plateformes répartissent leur CA de façon quasi identique (**55-60 % MYM**), ce qui suggère un effet de plateforme, pas de créatrice. ③ **Lily : 223 000 vues amenées par Jonas → 0 €.** Sur 9 noms au roster, 3 sont à zéro absolu et un quatrième (Lila Doré) à 111 € — le CAC y est infini, pas élevé.

## 3. La réponse à ta question : OF vs MYM, LTV par plateforme

Seule la fenêtre dictée du 19/07 (~19/06-19/07) sépare les plateformes **avec** des comptes de subs. Elle porte la réserve du §1-②.

| Créatrice | MYM €/sub | OF $/sub | OF €/sub | Qui gagne |
|---|---:|---:|---:|---|
| **Chloé** | **12,59** | 8,17 | 7,35 | **MYM +71 %** |
| **Jade** | **9,92** | 9,50 | 8,55 | **MYM +16 %** |
| **Amanda** | 1,89 | 3,11 | **2,80** | **OF +48 %** |
| Maddy | 12,50 | — | — | MYM only |
| Sophie | — | 6,77 | 6,10 | OF only |
| Sarah | 2,83 | *(lancement)* | — | MYM only |
| **BLENDED** | **5,34** | 7,04 | **6,33** | *OF +19 % — et c'est faux, voir ci-dessous* |

**Le +19 % d'OF est entièrement fabriqué par une seule ligne.** Sarah encaisse ~3 000 subs/mois de **trafic interne MYM gratuit** à 2,83 € — un canal que l'OF n'a tout simplement pas. Ces subs écrasent le blended MYM sans rien dire de la qualité de la plateforme. En les retirant :

| Mesure | Périmètre | LTV | Source |
|---|---|---:|---|
| **MYM hors trafic interne** | fenêtre dictée 19/07 | **9,67 €/sub** | dicté, `to-verify` |
| **MYM hors trafic interne** | dashboard 14/06-13/07 | **7,53 €/sub** | dashboard MyPulse, dur |
| **OF hors SFS** | 10 400 subs, liens trackés | **7,45 €/sub** (8,28 $) | Infloww 29/07, dur |
| OF tous liens confondus | 12 500 subs | 6,98 €/sub (7,76 $) | Infloww 29/07, dur |
| OF — SFS seul | 2 100 subs | 4,67 €/sub (5,19 $) | Infloww 29/07, dur |
| MYM — trafic interne seul | ~3 000 subs/mois | **2,83 €/sub** | dicté + confirmé Maxime |

> **Verdict : à source comparable, MYM (7,5-9,7 €) est au-dessus d'OF (7,5 €), et l'écart entre les deux plateformes est plus petit que l'écart entre deux sources de trafic sur la même plateforme.** Le facteur de LTV n'est pas la plateforme. C'est la **source** (interne 2,83 € · SFS 4,67 € · organique 7,5-9,7 €) et le **% du deal**.

**Nuance qui contredit l'enthousiasme du 29/07** : le SFS convertit magnifiquement (CVR 60-85 % contre 7 % en organique) mais ses subs valent **5,19 $ contre 7,76 $ en moyenne** et 8,28 $ hors SFS. Le SFS gagne sur le **coût** (≈ 0 €) et sur le rendement par clic, **pas sur la valeur du sub** — un fan qui butine déjà chez une autre créatrice dépense moins. Ça ne retire rien à la décision de rotation interne : à coût zéro, 5,19 $/sub reste imbattable. Ça interdit juste d'écrire « le SFS amène les meilleurs subs ».

## 4. Le classement qui devrait piloter le budget : marge € par sub marginal

La LTV seule ne décide rien — le % agence varie de 40 % (Chloé) à 60 % (Jade), et c'est lui qui transforme un sub en marge. `marge €/sub = LTV × % de marge` (Chloé 25 %, Jade 45 %, les autres 35 %) :

| Rang | Cible | LTV | × marge | **Marge €/sub** |
|---:|---|---:|---:|---:|
| 1 | 💎 **Jade — MYM** | 9,92 € | 45 % | **4,46 €** |
| 2 | 💎 **Maddy — MYM** | 12,50 € | 35 % | **4,38 €** |
| 3 | **Jade — OF** | 8,55 € | 45 % | **3,85 €** |
| 4 | Chloé — MYM | 12,59 € | 25 % | 3,15 € |
| 5 | Sophie — OF | 6,10 € | 35 % | 2,13 € |
| 6 | Chloé — OF | 7,35 € | 25 % | 1,84 € |
| 7 | Sarah — MYM | 2,83 € | 35 % | 0,99 € |
| 8 | Amanda — OF | 2,80 € | 35 % | 0,98 € |
| 9 | Amanda — MYM | 1,89 € | 35 % | 0,66 € |

**Les deux meilleures cibles sont sur MYM — et la pire aussi.** C'est la démonstration la plus propre que la plateforme n'est pas la variable : elle apparaît en tête et en queue de classement. Ce qui trie, c'est source × deal. Direction confirmée de [[Goulot de l'agence - l'équation du scale|la règle d'allocation v2]] (Jade et Maddy d'abord), mais avec une précision qu'elle n'avait pas : **c'est le MYM de Jade et de Maddy qu'il faut viser, pas leur OF.**

## 5. L'incohérence à 0,50 € qui casse tout le reste

La grille clipper FR est **200 € de fixe conditionnel + 0,50 €/sub**, et [[Équipe marketing - structure et rémunération (FR × MG)|la commission porte explicitement sur les « subs OF gratuits vérifiés par le tracking »]]. Confronté au classement du §4 :

- Un clipper qui envoie 200 subs sur **Maddy** — priorité 1 de la matrice, 14 % du CA, la meilleure marge/sub de l'agence après Jade — **touche 0 €**. Maddy est MYM-only.
- Un clipper qui envoie 200 subs sur **Chloé OF** — dernier rendement marginal du roster hors Amanda — touche **100 €**.
- La consigne opérationnelle du 28/07 (« réaffecter Jonas vers Jade/Maddy ») demande donc à un clipper de travailler **pour moitié gratuitement**, sans que la grille ait été modifiée. C'est le genre de contradiction qui ne se voit pas en réunion et qui se paie en churn de clippers — or la rétention est ton goulot n°1 déclaré.

**Correction recommandée** : étendre la commission aux **subs MYM vérifiés**, au même tarif. Le tracking existe déjà — le [[Rapport quotidien 13h (Reels vers clics vers subs)|rapport quotidien de 13h]] fait saisir à Rianah `Date | Créatrice | Plateforme | Subs | Clipper`, la colonne Plateforme est déjà là. Coût : à volume égal, la masse de commission monte d'environ **+40 %** (la part MYM des subs), sur des subs qui rapportent **plus** de marge par tête. Le vrai risque n'est pas le coût, c'est la **vérifiabilité** : un sub MYM se vérifie moins proprement qu'un sub OF tracké par Infloww. À trancher avant d'ouvrir le robinet — sinon la fraude remplace l'incohérence.

## 6. Ce que ça change sur le point mort d'un clipper (la correction qui fait mal)

La règle v2 du 24/07 pose une **LTV organique de 10-15 €/fan**, explicitement `à confirmer par mesure`. La mesure est arrivée : **7,45 € sur OF** (10 400 subs trackés) et **7,53-9,67 € sur MYM** hors trafic interne. **L'hypothèse était optimiste de 40 à 70 %.** Point mort recalculé (`200 ÷ (LTV × marge − 0,50)`) :

| Cible du clipper | Point mort — hypothèse 12,5 € (règle v2) | Point mort — **LTV mesurée** | Écart |
|---|---:|---:|---:|
| **Jade** (45 %) | 39 subs/mois | **59-70 subs/mois** | ×1,7 |
| **Maddy · Sophie · Sarah · Amanda** (35 %) | 52 subs/mois | **80-95 subs/mois** | ×1,7 |
| **Chloé** (25 %) | 76 subs/mois | **121-147 subs/mois** | ×1,8 |

**Le clipper médian fait 80-100 subs/mois.** Il est donc, à la mesure : rentable sur Jade, **à l'équilibre** sur les créatrices à 35 %, et **structurellement déficitaire sur Chloé** — celle vers qui le flux part par défaut. Ce n'est pas un argument pour arrêter de recruter, c'est un argument pour **arrêter d'allouer par défaut** et pour tenir le seuil : un clipper sous 80 subs/mois sur une créatrice à 35 % coûte de l'argent, et le fixe de 200 € est ce qui décide, pas la commission.

**Le corollaire qui range le débat du 23/07** : un sub de **trafic interne MYM** rapporte 2,83 € × 35 % = **0,99 € de marge à coût zéro**. Un sub de clipper sur OF à 80 subs/mois rapporte 7,45 € × 35 % − 0,50 € − 2,50 € de fixe amorti = **−0,39 €**. Il faut ~**100 subs/mois** pour que le clipper repasse au-dessus de zéro, et ~**150** pour qu'il batte franchement le sub interne gratuit. **Comprendre le débordement de Sarah reste, chiffres en main, le meilleur rendement disponible de l'agence** — la prédiction du 23/07 (« exploiter avant d'élargir ») se vérifie par un second chemin.

## 7. Deux prédictions arrivées à échéance

**① Chloé MYM en gratuit (14-15/07) — pari GAGNÉ.** La prédiction du 13/07 disait : succès si le CA 30 j monte malgré la LTV/fan en chute. Son CA MYM passe de **210 €/jour** (dashboard 14/06-13/07) à **288 €/jour** (chat seul, 01-28/07) = **+37 % minimum**, et c'est un plancher puisque la mesure d'après exclut abonnements et renouvellements. Le volume a plus que compensé. À graver : le gratuit a marché sur une créatrice à forte demande latente — ça ne dit rien de sa transposabilité à Jade ou Amanda.

**② Les autres trajectoires, honnêtement illisibles.** Maddy affiche −23 % et Jade −12 %, mais on compare un CA **total** (avant) à un CA **de chat** (après) : à composition constante, les deux sont probablement stables à légèrement positifs. **Je ne conclus rien** sur ces deux-là avant un export à périmètre identique. Sarah, elle, monte de **+70 % en chat seul** — celle-là est réelle.

## 8. Ce qu'il faut exporter pour que ce rapport devienne exact (20 minutes)

1. **MyPulse — nouveaux abonnés par créatrice, 30/06 au 30/07**, avec la définition retenue écrite noir sur blanc (payant / gratuit / unique) — c'est ce qui lève la contradiction ×2-5 du §1.
2. **MyPulse — CA total par créatrice** sur la même fenêtre (pas seulement le chat) : abonnements + renouvellements + MOD + push inclus.
3. **Infloww — nouveaux subs par créatrice** sur la même fenêtre (le CA OF, lui, est déjà propre).
4. **Infloww — tracking links filtrés sur la fenêtre** plutôt qu'en cumul : ça donne la LTV **par source** et par créatrice, seule façon de valider ou casser le 7,45 €.

Avec ces 4 exports, le tableau `créatrice × plateforme × source` existe et la règle d'allocation devient mesurée au lieu d'estimée. **Sans eux, le §3 et le §4 restent `to-verify` — et je préfère te le dire que te vendre une précision que les données n'ont pas.**

## 9. Les trois actions qui sortent de ce rapport

1. **Trancher la grille clipper** (§5) : étendre la commission aux subs MYM ou assumer par écrit qu'on ne paie que l'OF — mais alors arrêter d'envoyer les clippers sur Maddy. L'état actuel est le pire des deux.
2. **Corriger la règle d'allocation v2** avec la LTV mesurée (§6) : les points morts montent de ~70 %, et le défaut « Chloé » est déficitaire pour un clipper médian.
3. **Lancer les 4 exports** (§8) avant la clôture du 1er août avec Maxence, pour que la [[SOP clôture mensuelle avec Maxence|clôture mensuelle]] intègre enfin une colonne LTV par source et pas seulement une commission.

## Sources

[^1]: Exports MyPulse (chat MYM, 01-28/07) et Infloww (chat OF, 01-28/07) distillés dans [[Supervision chatting (top 5) et le cas Sarah]] — CA par créatrice et par plateforme. Données brutes hors repo (PII fans/chatteurs).
[^2]: Export Infloww tracking links du 29/07 (12 500 subs, ~97 k$ cumulés, dont SFS ~2 100 subs / ~10,9 k$) — [[Journal de coaching|entrée du 29/07]]. Mesure cumulée, pas 30 j : sur un OF en croissance elle sous-estime probablement la LTV réelle.
[^3]: Comptes de subs par plateforme : chiffres dictés par Gaëtan ~19/07 et dashboard MyPulse 14/06-13/07, tous deux repris dans [[LTP Models]]. Contradiction ×2-5 non résolue, consignée au [[Fact-Check-Log]].
[^4]: Structure de commission par créatrice (Chloé 40 %, Jade 60 %, autres 50 % ; −15 % chatting) et grille clipper FR (200 € + 0,50 €/sub OF) : [[Équipe marketing - structure et rémunération (FR × MG)]] et [[Goulot de l'agence - l'équation du scale]].
