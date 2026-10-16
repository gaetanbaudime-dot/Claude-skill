# Recrutement : identité stable et cohortes

PR brouillon : revue requise avant fusion et déploiement. Périmètre approuvé le 16 octobre 2026 : points **1, 2, 3, 4, 5, 6 et 10** du plan recrutement. Cette numérotation est distincte des anciens axes de `recrutement-axes-valides.md`. Pas de nouvelles initiatives sur les points 7–9.

## Audit et décisions

- Tunnel canonique existant : `/candidature` → formation → quiz réussi → Discord. Telegram, Facebook et Discord peuvent utiliser ce même formulaire avec `src` et `campagne`. Aucune annonce publiée.
- L'ancien tableau par téléphone servait de dernière fiche pour plusieurs candidatures. Il ne prouve pas une identité. Les snapshots par candidature deviennent la référence ; le cache de contact est conservé pour compatibilité, ses anciennes valeurs sont archivées avant remplacement. Aucun rapprochement par prénom ou téléphone partagé.
- Le formulaire doit présenter un nonce signé. Les anciennes pages sans nonce sont réaffichées avec leurs réponses, sans compter de candidature. Un même envoi rejoué reprend le même dossier, avant tout nouvel effet. Nouvelle page sans lien de reprise = nouveau dossier provisoire ; impossible d'affirmer qu'il s'agit d'une nouvelle personne avant preuve Discord.
- Identifiants : `candidate_id` opaque généré côté serveur ; `submission_id=soumission:<candidate_id>` pour la soumission initiale ; `event_id=candidature:<candidate_id>`. Le préfixe qualifie l'événement, il ne contient aucun contact. Le nonce signé ne doit jamais être exporté dans les rapports. Les identifiants d'événements quiz utilisent leur tentative stable, distincte à chaque retake.
- Le dossier conserve source, campagne, réponses et date originale. Les paramètres de campagne sont déclaratifs, normalisés, jamais utilisés comme autorisation ou preuve d'identité.
- Liaisons Discord seulement par invitation consommée ou OAuth. Plusieurs UID pour la même candidature : conflit conservé, pas de validation automatique. Le parcours manuel par téléphone ne peut plus importer une candidature ; le responsable aide à retrouver le lien personnel. Il faut vérifier ce changement de repli pendant la revue.
- Quiz : résultat figé et historique par tentative avec révision ; première réussite par candidature. Les tentatives Discord sont aussi conservées. Les notes anciennes absentes ou erronées ne sont ni reconstituées ni converties arbitrairement vers /8. Une réussite ancienne datée sans fuseau ne devient pas une réussite datée UTC.
- Publications : jointure par UID et shortcode vérifié, dédoublonnée à travers les alias ; une URL Reel et son shortcode désignent la même preuve. Pas de jointure avec un prénom de gérant. Les nouveaux dossiers d'un même UID exposent leurs IDs, sans attribuer rétroactivement les anciens Reels à une nouvelle admission.

## Rémunération : aucune modification de contrat

Sources locales : `questions_candidature.json` annonce actuellement 0,05 dollar par visite réelle, sans fixe, payé les 5 et 20. `README.md`, section « Présentation et rémunération (23/09) », décrit la décision pour les nouveaux. `paie_clics.py` définit 0,05 dollar par visite payable, pays admissibles configurés, robots exclus, et conserve des exceptions au fixe. La documentation ancienne n'est donc pas une base suffisante pour généraliser une offre.

Lecture de configuration Railway le 16 octobre : aucune variable de surcharge `TAUX_CLIC`, `PAYS_PAYES` ou `PAIE_FIXE` présentée par le connecteur ; valeurs masquées. Cela confirme l'absence de ces surcharges, pas la portée juridique des accords individuels. Les exceptions restent intactes ; aucune migration d'un clippeur existant. Le montant et la formulation de paie publics restent inchangés dans cette PR. **Avant harmonisation publique : préciser si cette offre s'applique à tous les nouveaux recrutements ou seulement à une équipe.** Aucun besoin de nouveau secret ou accès pour cette clarification.

Seule correction de promesse dans le formulaire : remplacer la menace de sortie à 48 h par l'objectif indicatif « premier Reel moins de 48 h après validation », avec aide du responsable en cas de blocage technique. Les rappels existants sont déjà non punitifs par défaut ; aucun seuil de sortie ni accord historique modifié ici.

## Test opérationnel et responsabilité

Le test opérationnel reste le premier lot de quatre Reels de croissance 1, à partir du brief et des ressources réelles de la créatrice déjà transmis par le parcours. Aucun entretien, deuxième examen de montage ou validation TL systématique ajouté. Les paliers restent quatre Reels vérifiés sur G1, puis quatre sur G2, puis privé. Le registre à vie reste inchangé : trois identités maximum créées/réservées/incertaines, jamais zéro par défaut pour un historique inconnu.

Le responsable est lu depuis l'équipe et ses TL déjà configurés (`chef` de la créatrice). Aucun changement de rotation, coefficient ou rémunération TL. Plusieurs TL ou TL absent : responsable « manager », sans choisir arbitrairement. Une attribution ne prouve pas que le compte est prêt : `pret_le` exige `preuve_pret`. Cette attestation n'est pas produite par tous les chemins actuels ; elle reste inconnue et ne bloque pas le parcours.

## Contrat des mesures

Rapport UTC explicite, durées écoulées, pas dates locales tronquées. Un changement d'heure ne modifie pas la durée de 168/336 heures. Une date ancienne sans fuseau reste non résolue.

- Origine : validation explicite de l'agence dans le pipeline, pas candidature, quiz, réservation ou attribution substituée.
- Activation J7 : au moins un Reel vérifié dans `[validation, validation + 7 jours[`. Seules les cohortes ayant atteint +7 jours sont matures.
- Rétention J14 : au moins un Reel vérifié dans `[validation + 7 jours, validation + 14 jours[`. À +7 exactement, la publication compte en J14, pas J7 ; à +14, elle est hors de cette fenêtre.
- Les blocages techniques **restent au dénominateur** quand la cohorte est mature et la couverture mesurable. Leur nombre est affiché séparément. Un lecteur en panne ou une couverture non attestée rend la mesure inconnue, jamais zéro ; exclusions non mesurées et immatures séparées.
- Actif récent : au moins un Reel dans les sept jours glissants. Cadence : nombre de Reels / 7, distinct de l'activité et de la cible de publication existante. Aucune nouvelle cible inventée.
- Premier Reel : première preuve observée après validation. `premier_reel_complet` distingue une collecte complète d'un minimum observé. Pas de verdict sur l'objectif 48 h en collecte incomplète ; blocage technique affiché sans échec candidat.
- Comptes réservés, créés avec preuve, date d'attribution, date effectivement prêt et premier Reel séparés. Un statut créé sans date de création ne permet pas d'inventer cette date.

## Rapport local, raccordement et montée en volume

`outils/mesurer_recrutement.py instantane.json --maintenant <date ISO avec fuseau>` lit un instantané autorisé contenant `pipeline`, `equipes`, `parcours`, `comptes` (registre à vie). Il ne lit pas le réseau et n'écrit pas de données. `couverture_publications=true` ne doit venir que d'une attestation serveur de collecte complète. Sans elle, indicateurs de cohortes non mesurés. Les deux dossiers sans Discord restent deux identités `candidature:<id>` distinctes, jamais une identité commune « avant Discord ».

Les seuils de montée en volume restent **à valider**, sans valeur économique inventée. Le contrat exige capacité d'aide disponible/requise sur une même période, taux d'activation J7, rétention J14, effectif mature minimal et preuve d'approbation des seuils. Même si les seuils passent, résultat « revue de montée possible », jamais lancement, dépense ou annonce automatique.

Première grille **proposée pour arbitrage, non configurée** : cohorte mature d'au moins 20 personnes, activation J7 ≥ 70 %, rétention J14 ≥ 50 %, capacité d'aide disponible couvrant la charge projetée avec 20 % de réserve. Ces valeurs sont des hypothèses de démarrage, pas des performances observées ni des règles approuvées ; les premières cohortes doivent servir à les recalibrer. Une hausse demanderait une revue humaine des blocages techniques et de la charge réelle avant une décision de volume.

Activation externe non effectuée : fusion/déploiement après revue ; branchement d'un lecteur complet vers le rapport ; éventuel ajout des IDs aux colonnes des Sheets de candidatures/quiz après validation de leur schéma. Les append Sheets actuels restent inchangés : les historiques Sheet seuls ne permettent toujours pas une jointure fiable. Aucun nouveau transport, onglet, partage, autorisation, secret ou envoi candidat. Les données historiques inconnues ne sont pas migrées.

## Vérification

Tests fictifs : replay concurrent dans l'unique boucle du bot, retakes, historique quiz, contact partagé, deux candidats avant Discord, alias et URL doublon, réservation sans création, maturité, bornes +7/+14, heure d'hiver, dates sans fuseau, couverture absente, schémas historiques de quiz. Le pipeline JSON reste prévu pour une seule réplique ; cette PR n'autorise pas un déploiement multiréplique sur des disques indépendants.

Skills locaux inspectés : second-brain, vidéo dimanche et Reels/Metricool ; aucun ne gouverne ce changement du bot, et le vault n'est pas modifié. `graphify-out` et l'exécutable `graphify` sont absents du checkout : pas de graphe à mettre à jour.
