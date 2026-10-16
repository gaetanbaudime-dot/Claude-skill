# Recrutement : axes validés le 16 octobre

Le quiz reste obligatoire. Les quatre premiers Reels réellement publiés et vérifiés sur croissance 1 constituent le test opérationnel existant : aucune épreuve supplémentaire, aucun quota ni délai ajouté. Trois comptes créés au total à vie, sans remplacement après ban ou départ. Axes 2, 4 et 9 exclus.

## Cartographie et écarts

| Axe | Présent sur main | Écart et traitement dans cette branche |
| --- | --- | --- |
| 1 — Fiche unique | `ops_identity.build_rows`, équipes et registre SQLite utilisent le Discord UID ; alias historiques et renommages conservés. | `fiches_uniques` réunit retours et pseudonymes par UID. Les candidatures sans UID restent indépendantes jusqu’à une liaison explicite. Une candidature liée à plusieurs UID reste en conflit, sans fusion arbitraire. Aucun rapprochement par nom. |
| 3 — Capacité préparée | `capacite.calcul` mesure le stock, `process_liens.preparer` réserve les destinations, onboarding gère rôle/salon/Drive. | Un stock de comptes ne prouve pas une admission prête. `projection` exige créatrice, TL, disponibilité du @ et tracking vérifiés et liés au même UID. C’est une précondition de lecture, pas une réservation ou une admission. |
| 5 — Quiz + test opérationnel | Quiz web ; paliers G1 → G2 et G2 → privé sur quatre Reels typés, distincts et datés dans `reels_verifies_v2`. | Le texte canonique `parcours.regle_comptes` nomme le premier lot « test opérationnel ». La projection utilise le même cumul de preuves, sans validation TL systématique ni nouveau test. |
| 6 — Prochaine action | `parcours.prochaine_etape` renvoie une phrase ; les états de l’app sont répartis dans plusieurs exports. | Contrat structuré : une seule `prochaine_action`, sa `preuve_attendue`, son responsable. Raccordement app non réalisé pour éviter les modifications concurrentes. |
| 7 — Preuves / exceptions TL | Les paliers n’utilisent plus les simples totaux publics ; états de ban fondés sur preuves mail. | Progression ordinaire automatique sur preuves ; incertitude de création, ancien ordre ou santé du compte dirigés vers le TL, avec repli manager si TL absent. Aucune absence Instagram transformée en ban. |
| 8 — Blocages attribués | Contrôles et messages opérationnels existent, sans schéma commun. | Chaque blocage exporté porte code, responsable et preuve manquante. Le premier détermine la prochaine action ; les autres restent consultables, sans multiplier les actions principales. |
| 10 — Cinq métriques | Pilotage clics/subs, paie et preuves de publications existent. | Calculateur pur de cinq métriques, couverture obligatoire, montant inconnu = `null`, jamais zéro inventé. Pas de collecte ni publication de résultats réels dans ce chantier. |

## Périmètre réellement modifié

- `recrutement.py` : fonctions pures, aucun appel réseau, aucune écriture, aucun import du client Discord.
- `parcours.py` : uniquement le texte canonique décrivant le premier lot. Aucun changement de seuil ni d’exécution.
- Tests fictifs et ce contrat de raccordement.

Les projections ne sont pas encore branchées aux exports ou écrans de production. Aucun fichier de `tools/app_clippers`, `tools/app_creatrices`, du duplicateur ou de Georgial n’est modifié. Cette branche a été créée sur main avant #32/#33 ; leur intégration, ensuite autorisée explicitement, est un chantier distinct. Aucun commit du duplicateur ni changement d’app n’est inclus dans cette proposition. Aucune migration, nouvelle permission, nouvelle étape d’admission ou opération sur candidat réel.

## Raccordements proposés à l’intégration app

1. Le serveur construit le dossier à partir des sources existantes, **jamais à partir d’une déclaration du navigateur**. Réutiliser l’authentification et le périmètre UID de l’app ; ne pas ajouter de route publique qui accepte arbitrairement un UID.
2. Appeler `projection(dossier, maintenant)` dans le constructeur serveur du tableau de bord et afficher `prochaine_action.texte` avec `preuve_attendue`. Le TL voit les seuls blocages de son équipe ; le clippeur voit sa fiche. Réutiliser les contrôles d’accès existants.
3. Sources : liaison explicite issue des invitations/OAuth (`pipeline.invitations`, `web_attendus`), équipes pour le TL, journal `histories/accounts/aliases` pour l’historique complet à vie, onboarding pour l’ordre, parcours pour dates et `reels_verifies_v2`, journal de préparation GAML pour les réservations et preuves. **Ne pas exporter accès, mots de passe, e-mails ni clés app dans ce contrat.**
4. Un `admission_prete=True` est un avis sur un instantané. Le workflow d’exécution doit relire et réclamer les ressources via les transactions existantes immédiatement avant admission. Ne jamais utiliser ce booléen comme autorisation d’allouer ou de partager.
5. Par « admission », ce contrat entend attribution dans l’agence après liaison Discord : il ne bloque pas le quiz avant Discord et ne crée pas d’étape dans le tunnel. Le branchement effectif du garde-fou à `valider_candidat` demande de coordonner la préparation actuelle, qui intervient plus tard. Ne pas ajouter un garde-fou qui attendrait ses propres effets et bloquerait tout le tunnel.

### Dossier normalisé version 1

- `uid`, `tl_uid`, `conflit_identite`, `admis`, `sorti`, `ordre_ancien` : informations serveur.
- `quiz_reussi` : `{verifie: true, source, reference, date}`. La référence doit désigner un résultat réussi réellement conservé, pas une simple présence sur Discord.
- `historique_vie` : `{complet: true, reference, comptes: [...]}`. Inclure **toutes** les identités créées/réservées/incertaines, y compris bannies et sorties, jamais seulement les comptes actifs. Ne pas convertir un historique manquant en liste vide complète.
- Chaque compte : `id` stable, `rang` 1/2/3, `statut` created/reserved/unknown, `etat`, `cree_le`, `preuve_creation`, `publications` typées `{code, publie, type_verifie: reel}`. Les alias doivent être résolus par le registre avant projection, afin qu’un changement de @ conserve ses preuves.
- `capacite.creatrice`, `.tl`, `.tracking` : `{uid, valeur, preuve}` ; preuve datée et référencée d’une vérification serveur. Tracking ajoute `gaml_id`, `mym`, `of`. Le contrôle d’unicité réel appartient au préparateur existant, pas à la présence des chaînes dans ce dossier.
- `capacite.handle` : `{uid, valeur, preuve}` ; attestation `instagram_formulaire` conforme à `pseudo_disponible`, valide 24 heures. Un profil invisible n’est pas une preuve de disponibilité.

Les données anciennes ambiguës restent des blocages avec responsable. Ce module ne les réécrit pas.

## Métriques et décisions restantes

Calcul en lecture seule, semaine UTC `[début, début + 7 jours[`. Un indicateur n’est mesuré que si son collecteur certifie explicitement une couverture complète. Une liste vide sans couverture est non mesurée. Les événements doivent venir de sources serveur vérifiées, porter identité stable, date et référence. Rapprocher les anciens IDs de candidature avec le Discord UID avant agrégation pour ne pas compter deux fois une personne qui revient.

- **Candidatures** : premières candidatures par identité dans la semaine. Les soumissions réitérées restent dans l’historique mais ne sont pas de nouveaux recrutés.
- **Quiz réussis** : première réussite vérifiée par identité ; les retries ne comptent pas à nouveau.
- **Premier lot publié** : quatre Reels vérifiés sur croissance 1. `evenement_premier_lot` prend la date du quatrième Reel, pas celle du scan. Aucun lot de croissance 2 compté comme un nouveau clippeur opérationnel.
- **Actifs à J30** : cohorte dont le trentième jour après admission tombe dans la semaine. La fenêtre d’activité doit être validée ; `fenetre_j30=None` laisse l’indicateur non mesuré. Proposition à arbitrer : au moins un Reel vérifié le jour 30, ou au cours des 7 jours se terminant à J30. Le nombre de membres dans Discord ne suffit pas.
- **Marge après rémunération et outils** : revenu attribuable moins rémunération totale (primes comprises) moins outils imputés, même période et même devise. Aucune conversion USD/EUR ou imputation des outils partagés implicite. Sans coûts complets, référence comptable et revenu attribuable, non mesurée. La méthode d’imputation des outils et d’attribution du revenu reste à définir.

Il reste donc à valider les définitions J30 et marge, raccorder les sources complètes puis intégrer l’affichage avec le chantier duplicateur. Ces décisions ne bloquent ni le quiz ni les paliers existants. Aucune métrique réelle n’est annoncée dans cette branche.

## Vérification

Tests sur données fictives uniquement : UID et retours, homonymes, conflit de liaison, quiz, preuve réelle de disponibilité, capacité incomplète, compteur à vie, bans, dates, typage des Reels, doublons, progression G2 → privé, premier lot, inconnues, cohorte J30 et marge décimale. Graphify et son graphe ne sont pas disponibles dans ce checkout ; aucune génération réseau lancée.
