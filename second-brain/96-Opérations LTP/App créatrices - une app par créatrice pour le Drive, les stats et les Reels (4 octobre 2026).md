---
titre: "App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)"
type: sop
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-10-04
tags: [ops/créatrices, ops/outils, ops/contenu, ofm/stats]
liens_forts: ["[[Cockpit opérationnel LTP (actions)]]", "[[SOP - Machine à contenu hebdomadaire]]", "[[Octobre lean - Loris en vertical, tout au variable, tout sur MYM (3 octobre 2026, soir)]]", "[[Automatisation et agents IA (SOP par des agents)]]", "[[Journal de coaching]]"]
---

# App créatrices - une app par créatrice pour le Drive, les stats et les Reels (4 octobre 2026)

> [!tip] Verdict
> L'app est construite, testée avec les vraies données des six créatrices et poussée sur GitHub (`tools/app_creatrices`). Une seule chose la sépare de la mise en ligne : **importer le dépôt sur Vercel avec les trois variables d'environnement**, deux minutes sur ordinateur, que seul Gaëtan peut faire (le connecteur Vercel de la session n'a pas le droit de créer un projet). Ensuite, envoyer à chaque créatrice son lien secret et le message « ajoute-la à ton écran d'accueil ». Le reste (dossiers de la semaine, stats, conversion dollar-euro) tourne tout seul.

## Ce que c'est

Une application web mobile (PWA) au branding G&M, nuit et argent, qui s'ajoute à l'écran d'accueil du téléphone comme une vraie app. **Un lien secret par créatrice**, pas de mot de passe, pas de code : qui a le lien voit l'app. Trois onglets en bas d'écran, dans l'esprit de la [[SOP - Machine à contenu hebdomadaire]] : la créatrice dépose son contenu au bon endroit sans réfléchir et voit ce que ça rapporte.

| Onglet | Ce qu'il fait | Source |
|---|---|---|
| **Drive** | Quatre tuiles (Reels, Photos, Feed MYM, Scripts MYM). Chacune ouvre l'application Google Drive de la créatrice **directement dans le bon dossier du moment** : Reels → `2026 / 10.Octobre / Semaine N` (semaine 1 = jours 1 à 7, 2 = 8 à 14, 3 = 15 à 21, 4 = 22 à 31) ; Photos → `2026 / 10. Octobre` ; Feed MYM → `Feed MYM Octobre 2026` ; Scripts → le dossier du mois s'il existe | Structure Drive existante, lue par le compte de service en lecture seule ; aucun dossier n'est créé par l'app, c'est le script Drive de l'agence qui le fait |
| **Reels** | Écran « Le duplicateur de Reels arrive » | À construire : décliner les meilleurs Reels en variantes prêtes à publier |
| **Stats** | Cinq boutons : Hier, 7J, 30J, M (mois en cours), M-1 (mois précédent). Revenus nets OnlyFans + MYM **en euros**, nouveaux abonnés **par jour** (jamais de cumul), comparaison avec la période précédente, graphique des revenus par jour (OF et MYM empilés) et des nouveaux abonnés par jour | Onglet de la créatrice dans Data G&M (A date, B abonnés OF, C CA OF en dollars, E abonnés MYM, F CA MYM en euros) ; dollars convertis au taux BCE du jour (Frankfurter, repli 0,88) |

Quand le dossier du jour n'existe pas encore (le mois n'est pas créé, la semaine non plus), la tuile **recule au plus récent existant** et le dit sous la tuile : « 2026 · Août » chez Chloé pour les photos, « Juin » chez Sophie. Le bouton ouvre toujours quelque chose d'utile, jamais une erreur.

## Ce qui a été vérifié le 4 octobre [C]

- Les six liens répondent ; un jeton inconnu renvoie une page 404 muette.
- Reels : les six créatrices ont bien `2026 / Octobre / Semaine 1`.
- Photos : Chloé et Jade tombent sur le dernier mois créé (août, septembre), Clara a son octobre, Sarah et Maddie n'ont pas de dossier par mois (la tuile ouvre leur dossier Photos), Sophie n'a pas d'année (les mois sont à la racine, la tuile ouvre « 6. Juin »).
- Feed et Scripts MYM : dossiers trouvés chez Chloé (feed d'octobre) et Jade (scripts jusqu'à décembre 2025). Sarah, Sophie, Clara et Maddie n'ont pas de dossier MYM connu : la tuile ouvre leur dossier Drive principal, en attendant que les dossiers existent et soient ajoutés à la configuration.
- Stats de Chloé : 7 jours = 6 475 € net (OF 1 992 €, MYM 4 483 €, 504 nouveaux abonnés), septembre = 23 405 € (contre 19 237 € en août). Quand un jour n'est saisi que d'un côté, le bas de page le dit (« OnlyFans pas encore saisi pour le 03/10 »).
- Captures iPhone (390 × 844) des trois onglets et des cinq périodes : lisibles, animations fluides, aucune erreur console.

## Mise en ligne (à faire par Gaëtan, une fois)

1. `vercel.com/new` → importer `gaetanbaudime-dot/Claude-skill` → nom `app-creatrices` → **Root Directory** `tools/app_creatrices`.
2. Coller le contenu du fichier `.env` fourni dans la session dans le champ des variables d'environnement (Vercel découpe les trois variables tout seul : le compte de service Google, l'identifiant de Data G&M, la configuration des créatrices avec leurs jetons et leurs dossiers).
3. Déployer. Les commits suivants se déploient seuls ; ceux qui ne touchent pas le dossier de l'app sont ignorés (`vercel.json`).
4. Envoyer à chaque créatrice son lien `/c/<jeton>` avec le message « Safari → Partager → Sur l'écran d'accueil ». Le guide complet et les six liens sont dans la session (fichier `app_creatrices_GUIDE.md`).

Pourquoi ce n'est pas déjà fait : le connecteur Vercel de la session peut déployer (le build depuis GitHub a réussi en 37 secondes) mais ne peut **ni créer un projet, ni écrire une variable** (403). L'écriture des variables sur l'hébergeur du bot a été refusée par le garde-fou de la session. Les secrets ne vont ni dans le dépôt ni dans le chat : la seule voie propre passe par Gaëtan. Cohérent avec la règle de [[Automatisation et agents IA (SOP par des agents)]] : l'agent construit et teste, l'humain tient les clés.

## Avocat du diable [P]

- **La saisie fait la valeur.** L'app n'invente rien : un jour non saisi dans Data G&M s'affiche à 0, et une créatrice qui voit « 0 € hier » appelle. Le signal « pas encore saisi » en bas de page limite la casse, pas plus. Si la saisie quotidienne est le goulot, c'est lui qu'il faut automatiser, comme le dit [[Goulot de l'agence - l'équation du scale]].
- **Un lien sans mot de passe.** Qui a le lien voit les revenus. C'est un choix assumé pour la simplicité (voulu par Gaëtan), au prix d'une règle : le lien se donne en privé, jamais dans un groupe, et se régénère si une créatrice quitte l'agence (changer son jeton dans la configuration suffit).
- **Les dossiers MYM manquent chez quatre créatrices.** Tant qu'ils n'existent pas, deux tuiles sur quatre ouvrent un dossier générique : l'app est à moitié utile pour Sarah, Sophie, Clara et Maddie côté MYM, précisément les créatrices que le cadre d'[[Octobre lean - Loris en vertical, tout au variable, tout sur MYM (3 octobre 2026, soir)|octobre]] pousse vers MYM.
- **Le duplicateur n'existe pas.** L'onglet « bientôt » crée une attente ; s'il reste vide un mois, il décrédibilise l'app. Soit on le livre en octobre, soit on retire l'onglet.
- **Dépendance au taux de change.** Le revenu OF affiché bouge avec le dollar, pas avec les ventes ; sur un jour, l'effet est négligeable, sur un mois il peut faire 2 à 3 % d'écart avec le relevé OnlyFans.

## Ce qui manque et ce qui suit [S]

- Ajouter les dossiers Feed et Scripts MYM des quatre créatrices dès qu'ils existent (une entrée de configuration, pas de code).
- Faire créer les dossiers de mois et de semaine à l'avance par le script Drive de l'agence, pour que le repli « plus récent existant » ne serve jamais.
- Le duplicateur de Reels, troisième onglet : la suite logique de la machine à contenu.
- Un domaine propre (`app.` sur le domaine de l'agence) pour que l'icône sur l'écran d'accueil ne porte pas un nom technique.

Les décisions et prédictions sont dans le [[Journal de coaching]] (entrée du 4 octobre 2026) ; l'action « mettre en ligne » est à cocher dans le [[Cockpit opérationnel LTP (actions)]].
