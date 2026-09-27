---
titre: "Process clippers de bout en bout - 10 simplifications (27 septembre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-27
tags: [ops/recrutement, ops/onboarding, ops/clipping, ops/simplification, ops/paie]
liens_forts: ["[[Formation clippers en une page et 10 simplifications (26 septembre 2026)]]", "[[Machine de recrutement clippers (100 leads par mois)]]", "[[Manager 200 clippers par un système]]", "[[Goulot de l'agence - l'équation du scale]]", "[[Architecture Discord - simple au quotidien (14 septembre 2026)]]"]
---

# Process clippers de bout en bout - 10 simplifications (27 septembre 2026)

> [!tip] Verdict
> Le process a **cinq portes** entre le formulaire et le premier Reel (quiz, test, J'ACCEPTE, créatrice, trois comptes) et **une seule** rapporte : le premier Reel publié. Les chiffres du 27/09 le disent sans nuance : **462 candidatures, 19 actifs, 3 au point mort**. Le goulot n'est pas le recrutement, c'est **l'activation** : 21 validés bloqués sur un clic « J'ACCEPTE », 4 signés sans créatrice depuis deux mois, 35 partis du serveur en silence, et Daniella qui a mis **48 h et cinq blocages pour un seul compte**. Les 10 simplifications ci-dessous ramènent le chemin à **deux portes** (un test jugé par le bot, un premier Reel), **un compte au lieu de trois** la première semaine, **un seul endroit** (le salon perso), **un seul régime de paie** généré par le bot, et une **sortie automatique** à 14 jours. Les deux plus rentables : une cohorte par semaine avec une créatrice imposée, et poster des Reels fournis avant d'apprendre à monter.

## 1. Le process aujourd'hui, en une ligne par étape

| Étape | Ce qui se passe | Ce que ça coûte (27/09) |
|---|---|---|
| Recrutement | Google Form + site, Telegram, Indeed | 462 candidatures, 24 par semaine, 227 jamais arrivées sur Discord (Form) |
| Quiz | vidéo de 54 min, 30/34, deux essais | une porte de plus, un webhook, un Google Form |
| Test de montage | un ou deux Reels en MP, avis du bot, `!test-ok` | Mathieu 5/10 deux fois, validé quand même |
| J'ACCEPTE | conditions en MP, rôle posé au clic | **21 validés bloqués ici** |
| Créatrice | `!creatrice` à la main, un par un | **4 signés sans créatrice depuis J+57 à J+70** |
| Comptes | 3 comptes, un par jour, numéro perso, selfie, warm-up 24 h | Daniella : 48 h, 5 blocages, 1 compte |
| Formation | 6 fiches, forum, salon assistant, salon créatrice, salon perso | 5 endroits, 3 200 mots avant le premier Reel |
| Posting | 2 Reels par jour par compte, contenu à monter | 25/09 : 5 clippers sur 16 ont publié |
| Paie | clic pour les nouveaux, fixe pour les anciens, `!paiement` à la main | un mois de retard, 4 refus de commande le 27/09 |
| Sortie | `!sortie` à la main | 35 partis du serveur sans que rien ne bouge |

## 2. Les 10 simplifications (dans l'ordre de rendement)

1. **Fermer le robinet, ouvrir par cohortes.** Le recrutement n'est pas le goulot : 462 candidatures pour 19 actifs. Une cohorte de 10 par semaine, formulaire fermé le reste du temps. Ce qui saute : la file d'attente permanente, les relances au fil de l'eau, l'impression de manquer de candidats. Risque : rater un très bon profil pendant une semaine fermée ; il repostule la semaine suivante.
2. **Deux portes au lieu de cinq.** Le quiz devient trois questions dans le formulaire du site (regardé la vidéo de 15 min, majeur, téléphone dédié). Le test est rendu **sur le site**, jugé par le bot : 7 et plus entre, moins de 5 sort, entre les deux tu tranches une fois par semaine en rafale. Le J'ACCEPTE est une case cochée sur le site, le rôle est posé à l'arrivée sur Discord. Ce qui saute : 21 bloqués sur un clic, deux webhooks, le tunnel en MP. Risque : moins de friction laisse passer des touristes ; c'est la sortie automatique (n° 9) qui les évacue, pas la porte.
3. **Une cohorte, une créatrice, un mercredi.** Chaque cohorte reçoit la même créatrice, celle dont le dossier TOP 20 et les sources sont prêts, en rotation. `!creatrice` en rafale le mercredi, plus de décision par personne. Ce qui saute : les 4 signés en attente depuis deux mois, le choix au cas par cas. Risque : une créatrice reçoit une cohorte faible ; la rotation lisse sur un mois.
4. **Un compte d'abord, trois ensuite.** Le nouveau crée **un** compte, publie dessus une semaine ; les comptes 2 et 3 se débloquent après 7 jours à 2 Reels par jour. Ce qui saute : deux tiers des créations chez ceux qui partent la première semaine (la majorité), deux tiers de l'exposition aux bans, le mur « numéro déjà utilisé ». Risque : moins de volume le premier mois par clipper ; compensé par plus de clippers qui arrivent au jour 7.
5. **Semaine 1 : poster, pas monter.** Les Reels uniques (TOP 20 de la créatrice déclinés pour chaque clipper) sont la matière de la première semaine : 2 par jour, à poster tel quel, avec la légende fournie. Le montage arrive en semaine 2, pour ceux qui sont encore là. Ce qui saute : la Fiche 3 et la moitié de la formation avant le premier Reel, la panne « je ne sais pas quoi poster ». Risque : du contenu proche d'un clipper à l'autre ; les variantes ffmpeg et le passage OpusClip existent pour ça.
6. **Un seul endroit : le salon perso.** Les trois fiches sont épinglées dedans, les boutons font le reste. Plus de salons de créatrice, de forum formation ni de salon assistant pour un nouveau. Ce qui saute : cinq endroits à surveiller pour lui, cinq pour toi. Risque : la vie d'équipe disparaît ; elle n'existait pas pour les nouveaux.
7. **Trois exceptions humaines, tout le reste au bot.** Ban, numéro refusé, paiement : WhatsApp Gaëtan. Tout le reste, le bot répond ou se tait (silence sur « ok », silence après un humain, jamais de cause inventée, en place depuis le 27/09). Plus de manager intermédiaire pour les nouveaux. Ce qui saute : les contradictions bot-humain, les « demain matin » inventés, le manager à qui rien n'est délégué. Risque : tu restes seul point d'escalade ; trois motifs seulement, c'est tenable.
8. **Un seul régime de paie, généré par le bot.** Clic pour tout le monde dès le 9 octobre, `!paie-clics` le 5 et le 20, un virement par ligne, fini. `!paiement` à la main ne sert plus qu'aux exceptions. Ce qui saute : le fixe, les rangs, un mois de retard, quatre commandes refusées. Risque : trois anciens perdent leur fixe ; c'était la décision du 25/09.
9. **Sortie automatique.** 14 jours sans Reel après l'attribution : sorti (rôles retirés, salon fermé, comptes libérés, message clair). Signé sans créatrice depuis 14 jours : retour au pool. Ce qui saute : 35 partis en silence avec des comptes réservés, les salons qui rotent, le compteur qui ment. Risque : un clipper malade ou en voyage est sorti ; il écrit sur WhatsApp et tu le remets en une commande.
10. **Un tableau de bord d'une ligne.** Chaque lundi, `!pipeline` donne cinq nombres : candidats → validés → premier Reel → jour 7 à 2 par jour → premier paiement. Toute décision de recrutement se prend sur « validés → premier Reel », jamais sur le volume de candidatures. Ce qui saute : les impressions, les rapports que personne ne lit. Risque : aucun.

## 3. Ce que ça donne en chiffres (réaliste vs optimiste)

| Mesure | Aujourd'hui (27/09) | Réaliste après simplification | Optimiste |
|---|---|---|---|
| Portes avant le premier Reel | 5 | 2 | 2 |
| Comptes à créer la première semaine | 3 par clipper | 1 | 1 |
| Délai formulaire → premier Reel | 7 à 14 jours | 4 jours | 48 h |
| Signés sans créatrice | 4, jusqu'à J+70 | 0 (cohorte du mercredi) | 0 |
| Validés bloqués sur un clic | 21 | 0 | 0 |
| Clippers qui publient à J+7 | 31 % (5 sur 16, le 25/09) | 50 % | 70 % |
| Tâches humaines par nouveau | 5 (review, J'ACCEPTE, créatrice, comptes, sortie) | 1 (trancher les tests 5-7, en rafale) | 0 |
| Point mort par clipper | 32 visites par jour pour 100 € | inchangé | inchangé |

Ces cibles sont des hypothèses. La seule mesure qui compte est la ligne « validés → premier Reel » du lundi.

## 4. Ce qui ferait échouer ça

- **Garder les cinq portes « au cas où ».** Chaque porte gardée coûte des clippers sans en filtrer un seul de plus : Mathieu est passé avec 5/10.
- **Trois comptes dès le jour 1 par habitude.** C'est là que Daniella a perdu 48 h. Un compte, c'est la moitié du process en moins.
- **Un contenu fourni de mauvaise qualité.** Si les Reels uniques sont moches, la semaine 1 confirme au clipper que ça ne marche pas. Le dossier TOP 20 doit être le vrai top, pas les 20 derniers.
- **Toi qui réponds à tout.** Trois exceptions, pas quinze. Sinon le bot redevient un décor.
- **Ne pas sortir les inactifs.** Sans la sortie automatique, les cohortes s'empilent et le roster remonte à 30 noms pour 5 actifs.

## 5. Prochaine action

1. Décider le n° 4 (un compte d'abord) : c'est la réponse à la question « 2 comptes puis 3, ou 3 d'un coup » restée ouverte depuis le 26/09.
2. Constituer le dossier TOP 20 de Sophie et de Sarah (Chloé est fait), lancer `!reels-uniques` : sans ça, le n° 5 n'existe pas.
3. Me donner le feu vert sur le n° 2 et le n° 9 : ce sont deux chantiers bot d'une demi-journée chacun (test sur le site, sortie automatique).

Le reste, c'est de la formation : [[Formation clippers en une page et 10 simplifications (26 septembre 2026)]] reste le script de la vidéo de 15 minutes. Le cadre business est celui du [[Goulot de l'agence - l'équation du scale]] et de [[Manager 200 clippers par un système]] ; le flux d'entrée, celui de la [[Machine de recrutement clippers (100 leads par mois)]] ; l'organisation Discord, celle de [[Architecture Discord - simple au quotidien (14 septembre 2026)]]. Décision et prédiction dans le [[Journal de coaching]]. Où en est chaque simplification le soir même : [[Bilan des 20 simplifications - fait, plus besoin, à faire (27 septembre 2026)]].
