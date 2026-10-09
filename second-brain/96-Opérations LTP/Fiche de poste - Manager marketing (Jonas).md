---
titre: "Fiche de poste - Manager marketing (Jonas)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-07
modifié: 2026-10-06
tags: [ops/équipe, ops/rémunération, ops/clippers, business/scaling, ops/paie]
liens_forts: ["[[Rentabilité des clippers de Jonas, de Jonas et de Julien - paie de septembre (5 octobre 2026)]]", "[[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)]]", "[[Développer un manager clipper (Julien et Jonas)]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Octobre lean - Loris en vertical, tout au variable, tout sur MYM (3 octobre 2026, soir)]]", "[[Journal de coaching]]", "[[LTP Models]]"]
---

# Fiche de poste — Manager marketing (Jonas)

> [!danger] Poste vacant depuis le 09/10/2026
> Jonas a quitté l'agence le 09/10. Cette fiche reste comme référence (règles du process, grille v3). La suite recommandée n'est pas un nouveau manager mais un Team Leader joueur-entraîneur : [[Team Leader clippers - le premier poste après Jonas (9 octobre 2026)]].

> [!tip] Verdict (v3, avenant du 06/10/2026)
> **Jonas lance et fait tenir 50 à 100 clippers malgaches payés au résultat, et il est payé sur ce qu'ils ramènent, pas sur leur nombre.** Plus de fixe par clipper : 0,30 € par abonné OnlyFans ou MYM, 1 € par clipper qui tient 26 jours de cadence, bonus équipe inchangés (300 / 800 / 1 600 €), +150 € quand 80 % de l'équipe tient. Septembre reste à 500 € (premier mois garanti par la fiche du 07/09). Les règles du process sont celles du bot depuis le 05/10 : 2 comptes de croissance + 1 privé avec le lien en bio, 4 Reels par jour, compte suivant après 48 h et 4 Reels, sortie automatique à 3 jours sans compte 1 et à 48 h sans réponse à l'appel de présence, WhatsApp obligatoire. Un seul chiffre pour l'essai : **600 abonnés OF + MYM en octobre**, sinon fin de période d'essai le 05/11. *Le PDF v3 (deux pages, signable) est généré depuis cette page ; toute modification se fait ici et dans le PDF.*

> [!warning] La ligne de paie est une proposition de Claude, pas encore une décision de Gaëtan
> Gaëtan a décidé le 05/10 : « 50 à 100 Malgaches au variable, on fait du volume, je compte sur lui pour mériter son salaire ». Le montant exact de la nouvelle grille n'a pas été fixé. La grille ci-dessous (0,30 € par abonné + 1 € par clipper tenu, zéro fixe) est celle recommandée dans le [[Rentabilité des clippers de Jonas, de Jonas et de Julien - paie de septembre (5 octobre 2026)|rapport du 05/10]] et dans la réponse du 05/10 ; l'alternative chiffrée était « 100 € par clipper rentable (≥ 50 abonnés) + 0,30 € ». À trancher avant le call du 07/10 ; le PDF se régénère en une minute.

## 0. Ce qui change par rapport à la fiche du 7 septembre

| Avant (07/09, PDF v2) | Maintenant (06/10, v3) |
|---|---|
| 5 Français + 2 à 3 Malgaches par semaine | **50 à 100 Malgaches**, par vagues, **tous au variable** |
| 2 comptes de croissance + 1 privé + 3 pages Facebook, 10 publications par jour | **2 comptes Instagram de croissance + 1 compte privé, 4 Reels par jour.** Plus de Facebook |
| Créneaux lundi, mercredi, vendredi 17 h avec Gaëtan | **Le bot livre les comptes un par un** : compte 2 après 48 h et 4 Reels, compte 3 (privé) après 48 h et 4 Reels de plus |
| Lien tagué dans la bio des deux comptes de croissance | **Le lien est dans la bio du compte 3 privé, et nulle part ailleurs** ; les comptes 1 et 2 le montrent par une story à la une (photo ou vidéo) et le widget de mention |
| 100 € par clipper actif et par mois | **Plus de fixe par clipper** : 0,30 € par abonné, 1 € par clipper-mois tenu, bonus équipe inchangés |
| Sorties jugées par Jonas le lundi | **Sorties automatiques par le bot** (3 jours sans compte 1 ; 48 h sans réponse à l'appel de présence ; purge 72 h) + tri du lundi (50 abonnés) |
| WhatsApp facultatif | **Chaque clipper écrit à Gaëtan sur WhatsApp dès son compte 1 créé** ; `!wa @clipper` le note |

## 1. Ce que chaque clipper doit tenir

**Ses comptes, dans l'ordre, donnés par le bot** ([[Audit du bot Discord clippers - inventaire et refonte en trois lots (5 octobre 2026)|refonte du 05/10]]) : compte 1 (croissance) → profil → 24 h de warm-up → il publie ; compte 2 (croissance) 48 h plus tard, quand 4 Reels sont publiés sur le 1 ; compte 3 (privé) 48 h après le 2, quand 4 Reels de plus sont publiés. Le compte 3 porte le lien GetAllMyLinks dans sa bio et ne publie pas. Sur les comptes 1 et 2 : story à la une (photo ou vidéo) + widget de mention vers le compte 3.

**Sa cadence** : 2 Reels par jour sur chaque compte de croissance = **4 Reels par jour**, 26 jours sur 30. Les Reels viennent du Drive de sa créatrice (TOP 20 décliné par le bot) ou de son propre montage.

## 2. Les règles de sortie (le bot les applique, Jonas les explique)

- **3 jours sans compte 1** après sa livraison → avertissement la veille, puis sortie du serveur et expulsion (`sortie_auto`, depuis le 05/10).
- **Appel de présence** : 4 jours sans message, sans bouton d'étape et sans Reel → le bot l'appelle ; 48 h sans réponse → sortie et expulsion. A répondu mais pas écrit à Gaëtan sur WhatsApp → relance 24 h après (`appel.py`).
- **Purge** : compte 1 livré depuis 72 h, jamais créé, et pas un mot dans le salon perso → sortie immédiate (`!purge`).
- **Tri du lundi (Jonas)** : moins de **50 abonnés OnlyFans + MYM dans son premier mois de publication** → il le signale, le clipper sort, sa place va à un nouveau. **2 jours sans Reel** → relance sous 24 h, notée dans le salon admin.

Un clipper qui sort rend ses comptes au vivier et son lien est libéré.

## 3. Les 7 missions (v3)

1. **Faire publier tous les jours** : le Dashboard du classeur et le rapport du bot disent qui publie et qui est à zéro ; relance sous 24 h en MP Discord et sur WhatsApp.
2. **Lancer chaque vague** : Gaëtan recrute et signe ; Jonas accueille chaque nouveau sur Discord et WhatsApp, vérifie le compte 1 sous 3 jours et le suivi des étapes (1 → 2 → 3 → lien → routine).
3. **Garantir le tunnel** : pour chaque clipper au compte 3, lien dans la bio du compte 3, story à la une et widget sur 1 et 2, page GetAllMyLinks avec bouton OnlyFans **et** bouton MYM (le cas Lilian du 05/10 : pas de bouton MYM, abonnés perdus), lien de tracking OnlyFans existant.
4. **Former et corriger** : 10 Reels relus par semaine en groupe sur WhatsApp (les meilleurs et les pires), un conseil simple à chaque fois ; les nouveaux lancés avec les fiches et `#assistant`.
5. **Trier** chaque lundi (50 abonnés, 2 jours sans Reel) : Jonas propose, Gaëtan tranche, le bot exécute.
6. **Rendre compte** : cinq lignes par jour dans le salon admin (publiés / à zéro / comptes créés / bans / blocages), un call de 30 min par semaine.
7. **Remonter les blocages** (ban, numéro, paiement) à Gaëtan sur WhatsApp le jour même ([[Trois exceptions humaines - ban, numéro, paiement (27 septembre 2026)]]).

Temps : 2 à 3 h par jour à 100 clippers. Il ne gère pas : la paie et les montants, les contrats, le choix des créatrices, le recrutement.

## 4. La paie (à partir du 1er octobre 2026)

| Ligne | Montant | Condition |
|---|---|---|
| **Septembre** | **500 €** | Premier mois garanti (fiche du 07/09), versé le 05/10 sur facture. Au variable, septembre aurait fait 92 € (≈ 300 abonnés × 0,30 € + 2 clippers tenus). |
| **Commission** | **0,30 € par abonné OnlyFans ou MYM vérifié** | Venu des liens de ses clippers, sans plafond, jamais gelée. |
| **Prime par clipper tenu** | **1 € par clipper** à 26 jours sur 30 | Cadence 4 Reels par jour, mesurée par le bot (comptes du classeur). Remplace le fixe. |
| **Bonus équipe** | +300 € au-delà de 1 000 abonnés dans le mois · +800 € au-delà de 2 500 · +1 600 € au-delà de 5 000 | Palier atteint, non cumulés. Inchangé. |
| **Bonus discipline** | +150 € | Quand 80 % des clippers tiennent 26 jours le même mois. |
| **Fixe** | aucun | Plus de fixe par clipper ni de minimum garanti après septembre. Paie le 5 du mois, sur facture. |

Exemples : 12 clippers · 300 abonnés · 2 tenus = **92 €** (septembre tel quel) · 50 clippers · 1 000 abonnés · 30 tenus = **630 €** · 100 · 1 500 · 60 = **810 €** · 100 · 2 500 · 80 = **1 780 €** · 100 · 5 000 · 90 = **3 340 €**.

Ce que ça coûte à l'agence : à 0,30 € pour Jonas plus ≈ 0,50 € pour le clipper, l'abonné coûte ≈ 0,80 € de paie pour un profit moyen de 1,5 à 2 € ([[Octobre lean - Loris en vertical, tout au variable, tout sur MYM (3 octobre 2026, soir)]]). La marge tient tant que les abonnés sont vérifiés sur les liens.

## 5. Les chiffres regardés chaque semaine et la réussite

| Quoi | Objectif |
|---|---|
| Clippers au compte 3 avec un tunnel complet | tous ceux arrivés au compte 3 depuis plus de 48 h |
| Jours tenus (4 Reels par jour) | 26 par mois par clipper · 2 jours sans Reel = relance sous 24 h |
| Abonnés OF + MYM | 50 par clipper le premier mois · **600 pour l'équipe en octobre · 1 000 en novembre · 2 500 en décembre** |
| Sorties | faites dans la semaine |
| Compte rendu | 5 lignes par jour · le call de la semaine tenu |

**J+60 (06/11)** : 50 clippers au compte 3, 600 abonnés OF + MYM en octobre. **J+90 (06/12)** : 100 clippers, 2 500 abonnés dans le mois. Sous 600 abonnés au 05/11, la période d'essai s'arrête.

## 6. Avocat du diable [P]

- **La prime de 1 € par clipper tenu dépend de la lecture Apify** des comptes du classeur : un compte restreint ou non déclaré compte zéro (Caroline, Yves le 05/10). Avant de payer, le bot doit marquer « non lisible » plutôt que zéro, sinon Jonas contestera à raison.
- **Au variable pur, Jonas peut partir** : son octobre réaliste est 300 à 800 €. Si Gaëtan veut le garder à tout prix, l'alternative « 100 € par clipper rentable » coûte 300 à 400 € pour 2 à 3 clippers rentables aujourd'hui.
- **50 à 100 Malgaches au variable, c'est 100 à 300 comptes Instagram à créer** par le bot : le goulot devient les bans et les numéros, pas Jonas. La fiche lui demande de remonter les blocages, pas de les résoudre.
- **Les abonnés MYM ne sont vérifiables par clipper que depuis le 28/09** et trois clones partagent encore un lien MYM : la commission MYM d'octobre sera contestable si ce n'est pas nettoyé avant le 15/10.

## 7. Historique

- **07/09 (v1 → PDF v2 « aéré », signé)** : 5 Français puis 2 à 3 Malgaches par semaine ; 2 comptes de croissance + 1 privé + 3 pages Facebook, 10 publications par jour ; créneaux lundi, mercredi, vendredi 17 h ; téléphones cloud iRemoteTech ; **100 € par clipper actif et par mois (≥ 80 % de cadence), 500 € garantis le premier mois, 0,30 € par abonné OnlyFans, +150 € si tous tiennent 26 jours, paliers 300 / 800 / 1 600 €** ; deux règles de sortie (2 jours ratés de suite → dehors le lundi ; moins de 50 abonnés le premier mois → dehors) ; paie le 5 sur facture. Ce texte sert de référence pour la paie de septembre (500 €).
- **27/09** : revue du pôle à 10 jours décidée ; plus de Facebook, plus de créneaux, paie des clippers au clic.
- **05/10** : [[Rentabilité des clippers de Jonas, de Jonas et de Julien - paie de septembre (5 octobre 2026)|rapport de rentabilité]] (285 abonnés estimés pour 600 attendus, 2 à 3 clippers à la cadence, ≈ 1 950 € de paie pour ≈ 630 € de profit) ; refonte du bot ; décision « 50 à 100 Malgaches au variable ».
- **06/10 (v3)** : cette page et le PDF v3 ; chiffres de septembre revérifiés depuis les exports bruts (section 3 quinquies du rapport du 05/10). Le développement du poste sur 90 jours reste dans [[Développer un manager clipper (Julien et Jonas)]].
