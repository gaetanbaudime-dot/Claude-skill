---
titre: "Machine horizontale v2 - plan de chantier (23 septembre 2026)"
type: plan
cluster: "96-Opérations LTP"
statut: verified
créé: 2026-09-23
màj: 2026-09-23
tags: [ops/clippers, ops/automatisation, marketing/acquisition, décision/business, finance/marge]
liens_forts: ["[[Machine horizontale v2 - paie au clic, ce que les clippers rapportent (23 septembre 2026)]]", "[[Machine de recrutement clippers (100 leads par mois)]]", "[[Machine Instagram-Facebook en masse]]", "[[État de l'art clipping Instagram (juillet 2026)]]", "[[Équipe marketing - structure et rémunération (FR × MG)]]", "[[Bot FAQ clippers (Discord)]]", "[[LTP Models]]", "[[Journal de coaching]]", "[[Théorie des contraintes]]"]
---

# Machine horizontale v2 : plan de chantier (23 septembre 2026)

> [!tip] Verdict
> **Chantier lancé, sur le bot existant, en quatre phases, la première livrable en une semaine.** Le rapport Deep Research de ChatGPT et l'analyse du vault disent la même chose sur l'essentiel : le variable est juste, le registre de clics acceptés avec motifs de rejet est le cœur financier, la liste de paie se génère et le virement reste humain, Drive et Gmail s'automatisent par API, la création de comptes Instagram ne se construit pas comme un contournement. Ils divergent sur l'échelle de la construction : ChatGPT propose une plateforme neuve (PostgreSQL, deux ingénieurs, 12 à 18 semaines) ; ici on garde le bot qui tourne (tunnel, quiz, test, contrats, 2FA, suivi, paie) et on lui ajoute des briques, un registre SQLite pour les clics, et on migre plus tard si le volume l'exige. Deux « bloquants » de ChatGPT sont levés : « Ghetto Minings » est GetAllMyLinks, qui a une API (clonage de liens, visiteurs par jour, pays, robots exclus) ; Infloww a une API en lecture seule (liens, transactions, fans) qui suffit à mesurer la rentabilité par clipper.

## 1. Ce qui est tranché (Gaëtan, 22-23/09)

| Sujet | Décision |
|---|---|
| Paie | 0,05 $ par visiteur GAML francophone hors robots, liste de paie le 5 et le 20, virement USDC ERC20 manuel sur Binance, même rythme que les chatteurs |
| Mesure de rentabilité | 100 liens de tracking Infloww créés d'avance par créatrice ; le lien GAML cloné pour chaque clipper pointe sur le prochain lien Infloww libre ; rentable ou viré se lit dans Infloww |
| Plateforme | Instagram seul : deux comptes de croissance et un compte privé par clipper, sur ses téléphones |
| Contenu | Un dossier Drive personnel par clipper (photos et Reels de sa créatrice), variantes produites par le spoofer reconstruit |
| Tunnel | Formulaire → Discord → liaison → formation → quiz plus sélectif → test de montage → créatrice attribuée par ordre et quotas → logins, lien, Drive envoyés en MP |
| Google | Compte de service Drive et Sheets, mot de passe d'application Gmail : API officielles, aucun risque pour les comptes |

Ce qui reste ouvert et se règle en phase 1 : les garde-fous du taux (plancher de conversion, plafond par lien), l'ordre des créatrices et la taille des files, la grille du test de montage.

## 2. Croisement avec le rapport Deep Research (ChatGPT)

| Point | ChatGPT | Vault | Retenu |
|---|---|---|---|
| Paie au clic | Registre de clics acceptés, motifs de rejet, batch le 5 et le 20, virement humain | Idem, plus : un clic de clipper vaut 0,30 $ de CA OF, 0,05 $ est cher sans garde-fou | Registre + taux 0,05 $ + garde-fous configurables |
| Identité candidat | Jeton unique après le formulaire plutôt que le téléphone | Le bot lie déjà par numéro, ça marche | Numéro conservé, jeton ajouté en phase 2 comme voie principale |
| Discord | Boutons et messages éphémères plutôt que 15 MP | Les MP marchent, avec relance si fermés | MP conservés, boutons ajoutés là où ça évite une erreur (choix, accusé) |
| Test de montage | Règles ffmpeg + multimodal + zone de revue humaine, grille 100 points, seuils 85 / 70 | IA = filtre, humain = cas limites, Reels d'essai = juge final | Identique ; Claude sur images extraites + transcription, déjà fait pour le Reel Edits |
| Créatrice | Table capacité / priorité, jamais codé en dur | Idem | Identique |
| Drive | API, un dossier par clipper, partage lecture | Idem | Identique |
| Secrets | Jamais de mots de passe en clair dans Sheets ou Discord, coffre dédié | Le Sheet est l'inventaire de Gaëtan | Compromis : le Sheet garde identifiants et statuts, les mots de passe sont chiffrés côté bot et envoyés une fois en MP |
| Instagram | Ne pas bâtir de mécanisme anti-ban ; « 100 % automatisé sans risque de ban » est contradictoire | Dette CGU signalée, isolation totale, comptes de rotation à 8-15 € et point mort 15-45 clics | Identique : le bot gère le cycle de vie des comptes, pas la recréation industrielle |
| Tracking | « Ghetto Minings » introuvable, bloquant | C'est GetAllMyLinks, API disponible | Bloquant levé |
| Construction | PostgreSQL, 2 ingénieurs, 12-18 semaines | Bot existant + briques | Bot existant, SQLite pour le registre, migration si besoin |

Ce que le Deep Research ajoute et qu'on prend tel quel : versionner formation et quiz, ne jamais écraser une tentative, idempotence (un clipper = un Drive, un lien, un paiement), file d'attente pour les rafales Discord, réconciliation des paiements (dû, payé, écart), et le KPI qui compte : coût et délai pour obtenir un clipper actif qui produit des clics acceptés.

## 3. Trois vérifications faites le 23/09

- **Tableau de bord GAML par clipper, en lecture seule sur son seul lien** : non disponible par l'API (aucune fonction d'invitation ni de droits par lien), et non vérifiable sur le site public. Équivalent livré par le bot : chaque matin, dans son salon privé, le clipper reçoit ses visiteurs de la veille, sa part francophone, ses robots exclus, son cumul de la quinzaine et le montant en cours ; `!mesclics` à la demande. Il ne voit que lui, et il n'a aucun accès à GAML.
- **Infloww** : API en lecture seule (liens, transactions, remboursements, créatrices connectées, fans), 60 requêtes par minute, pas de création de lien par API. Donc : Gaëtan crée les 100 liens d'avance dans Infloww, le bot les lit, attribue le prochain libre et suit clics, abonnés et CA par clipper sans export manuel.
- **GetAllMyLinks** : l'API fait tout ce qu'il faut (cloner un lien, le renommer, changer le bouton OnlyFans vers le lien Infloww du clipper, visiteurs par jour robots exclus, pays). Le bot ne l'utilise pas encore : la clé doit être posée dans Railway.

## 4. Les phases

| Phase | Contenu | Prérequis | Livraison |
|---|---|---|---|
| **1. Paie et liens** (semaine du 29/09) | Registre de clics acceptés (visiteurs GAML par lien et par jour, pays, robots exclus, motifs de rejet), taux et garde-fous configurables, `!paie-clics` qui sort la liste adresse-montant du 5 et du 20, clonage du lien GAML avec le lien Infloww à l'onboarding, `!mesclics` et la ligne du matin dans le salon privé, adresse USDC collectée en MP | Clé API GAML dans Railway ; 100 liens Infloww par créatrice ; clé API Infloww | Première paie au clic le 20/10 |
| **2. Onboarding sans Gaëtan** (semaine du 06/10) | Table créatrices (priorité, capacité, actifs), attribution automatique, logins des trois comptes envoyés depuis le Sheet, codes 2FA d'inscription relayés, jeton de liaison en sortie de formulaire | Compte de service Google (Drive + Sheets), mot de passe d'application Gmail, ordre des créatrices | Un candidat validé reçoit créatrice, comptes et lien sans intervention |
| **3. Contenu** (semaine du 13/10) | Dossier Drive personnel par clipper copié depuis le dossier source de la créatrice, partagé en lecture, lien envoyé en MP ; test de montage trié par l'IA sur la grille, cas limites à Gaëtan | Dossiers sources organisés Créatrice → Photos / Reels ; grille du test ; 20 anciens tests classés | Zéro lien Drive envoyé à la main |
| **4. Volume** (à partir du 20/10) | Spoofer reconstruit (variantes réelles : hooks, coupes, sous-titres, cadrages), inventaire des comptes avec états (disponible, attribué, actif, restreint, mort), retrait automatique des inactifs à 7 jours, tableau de bord | Le code de l'ancien TikFusion | Mesure : coût par compte vivant, clics par compte |

## 5. Ce qui casse le plan

- **Le taux sans garde-fou** : 1 000 clics « France » s'achètent 5 à 10 $. Les garde-fous sont dans le code dès la phase 1, désactivables, mais ils existent : conversion minimale du lien Infloww, plafond de clics payés par lien et par quinzaine, paiement à J+15.
- **Le flux de candidats** : 140 par mois aujourd'hui, 100 comptes par mois ; à 60 % de perte mensuelle, 300 comptes vivants en demandent 180 par mois. Sans doubler le flux ou changer d'infra, le plafond réel est autour de 150 à 200 comptes vivants.
- **La contamination** : le pari « aucun lien entre clippers et créatrices » tient si les e-mails de récupération, les téléphones et les IP ne touchent jamais les comptes principaux. Une seule connexion croisée et le pari tombe.
- **Le juge de qualité** : l'IA trie, elle ne prédit pas ; les Reels d'essai restent le vrai test.

## 6. Prédictions (23/09)

- Gaëtan : 20 à 30 % de bans en moins que ses concurrents. Mesure retenue : survie des comptes à 30 jours ≥ 50 % sur la première cohorte de phase 2 (contre 30 à 40 % chez le pote). Revue le 30/11.
- Phase 1 livrée et première paie au clic exécutée le 20/10 (70 %).
- Coût clippers d'octobre < 800 $ pour ≥ 10 000 visiteurs (65 %).
- Au moins un lien suspendu pour clics suspects avant le 30/11 (55 %).
