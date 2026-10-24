# App clippers G&M

Petite application web mobile (PWA) pour les clippers, jumelle de l'app créatrices : un lien personnel par clipper, à ajouter sur l'écran d'accueil du téléphone (iPhone Safari « Sur l'écran d'accueil », Android Chrome « Ajouter à l'écran d'accueil »). Trois onglets en bas, dans l'ordre du dessin de Gaëtan (nuage, flèche, dollar) :

- **Drive** (onglet par défaut) : quatre tuiles, **Carrousel · TOP 20 Reels · Story · Reels** (les deux tuiles Reels à droite, sous le pouce), qui ouvrent le **dossier racine** de la section dans l'application Google Drive du téléphone ; le clipper fouille dedans (mois, semaines, tenues). Pas d'état ni d'emoji : un texte explicatif en haut, un en bas. Carrousel, Reels et Story = les sous-dossiers du dossier Instagram de sa créatrice (le parent de « 🎬 Clippers »), trouvés par leur nom ; en secours, les sources `DRIVE_SOURCES` (Reels, Photos, Stories) puis les dossiers de `CREATRICES_JSON`. TOP 20 Reels = le sous-dossier « TOP 20 Reels » de son dossier personnel (`🎬 Clippers / <Prénom>`), où le bot dépose ses variantes uniques ; s'il n'existe pas encore, le « TOP 20 Reels » de la créatrice, sinon son dossier personnel. Racines en cache 10 minutes. Les dossiers ne sont jamais créés ici.
- **Reels** : le Duplicateur commun https://duplicateur-de-reels.vercel.app est embarqué directement dans cet onglet, sans clic vers un autre site. Six variantes HD et téléchargements MP4, sans ZIP. Le module est chargé à la première visite et reste monté lors des changements d’onglet pour conserver l’envoi et le suivi en cours. Aucun jeton ni référent personnel ne lui est transmis ; les protections des routes et en-têtes restent inchangées. « Plein écran » reste un secours si le navigateur bloque le stockage intégré ; la reprise dépend du stockage du même navigateur et du même contexte, sans partage garanti entre apps.
- **Versements** : ses visites francophones GetAllMyLinks jour par jour (14 jours, ou la période de paie en cours si elle est plus longue), le montant de la période en cours, la phrase « Prochain versement : 40,65 $ le 20 octobre », aujourd'hui, hier, les périodes précédentes (montant et date de versement), et son lien GAML à mettre dans la bio de son compte privé, avec un bouton Copier. Le jour en cours se rafraîchit toutes les 5 minutes tant que l'onglet est ouvert. Sous le lien, **l'adresse USDC (ERC-20)** du clipper : il la colle, l'app la valide (`0x` + 40 caractères hexadécimaux), l'enregistre dans l'onglet « Adresses USDC » du tableur « App clippers · usage » (une ligne par clipper, remplacée à chaque modification, avec la date) et l'affiche en entier pour qu'il la vérifie. C'est là que l'agence lit les adresses pour les virements du 5 et du 20.

  **Team Leader et manager (11/10, lot L11)** : une carte de plus, « Ton équipe ». Elle montre la **prime d'équipe en cours** (10 $ par VA de son équipe à 500 visites payées ou plus, 75 $ par équipe managée à 3 000 ou plus, telle que la liste de paie la porterait aujourd'hui), puis chaque VA avec ses visites payées de la période et un ✓ au seuil, et le total de chaque équipe managée. Les chiffres viennent du bot, pas de GAML : l'onglet « Équipes » du tableur d'usage, écrit à chaque relecture horaire par `paie_clics.publier_equipes` (`src/lib/equipes.ts`, cache 10 minutes). Ce sont les visites payées comptées comme la paie, jusqu'à hier. Le TL ne compte pas dans son équipe. Un VA dont des jours ne sont pas encore relevés dans GAML est affiché « 384 · 2 j non relevés » (colonne « Jours non relevés » de l'onglet) : la somme montera quand ils arriveront. Avant le 20/10/2026, la carte dit « Pas de prime d'équipe sur cette période ». Un clipper qui n'est ni TL ni manager ne voit rien de plus.

## Règles de paie (reprises de `tools/bot_clippers/paie_clics.py`)

0,05 $ par visite « francophone » (France, Belgique, Suisse, Canada, Luxembourg, Monaco, Réunion, Guadeloupe, Martinique, Guyane, Mayotte, Nouvelle-Calédonie, Polynésie), robots exclus par GAML, heure de Paris. Paie le 5 et le 20 de chaque mois : du 5 au 19 inclus → versé le 20, du 20 au 4 inclus → versé le 5 du mois suivant (règle du 09/10, `periodeDe` ; la paie au clic a commencé le 05/10, première période 5 → 19/10, rien avant). L'app l'affiche sous le montant (pastille « Payé le 5 et le 20 », barre « jour X sur N »). L'app annonce, le virement reste humain.

## Zéro configuration par clipper

La liste des clippers vient en direct de GAML : tous les liens dont la note est « Clipping Prénom » (même règle que `_prenom_note` du bot), regroupés par prénom normalisé (minuscules, sans accents). Un clipper avec plusieurs liens (chez plusieurs créatrices) voit ses visites additionnées ; sa créatrice est le premier mot du `name` de son lien le plus récent. Les prénoms de `CLICS_EXCLURE` du bot (rianah, gaetan, jonas, x, y) sont ignorés. Le jeton d'un clipper = HMAC-SHA256(`CLIPPERS_SECRET`, prénom normalisé) en base64url, tronqué à 24 caractères : un nouveau clipper est dans l'app dès que son lien GAML existe. Changer `CLIPPERS_SECRET` change tous les liens d'un coup.

## Budget d'appels GAML (60 par minute pour toute l'agence, bot compris)

- Liste des liens : cache serveur 10 minutes.
- Jours passés : immuables, relevés une fois et gardés 7 jours (`unstable_cache`).
- Jour en cours : relu au plus toutes les 5 minutes.
- Périodes de paie passées : un appel par période, gardé 7 jours.
- Première ouverture d'un clipper : environ 15 appels (14 jours + l'historique), par lots de 4 ; ensuite une ouverture coûte au plus 1 à 2 appels (le jour en cours, et le jour qui vient de se terminer).
- Un 429, ou une limite annoncée par les en-têtes `X-RateLimit-*`, n'est jamais une erreur pour le clipper : les appels s'arrêtent, l'app rend ce qu'elle a avec la mention « chiffres en cours de mise à jour ». Les appels sont lancés par ordre d'importance (aujourd'hui, hier, puis les jours plus anciens).

## Installation sur l'écran d'accueil (ce qui est vrai, ce qu'on fait)

Aucun navigateur ne permet d'installer une app web en un geste depuis un lien reçu : iPhone n'offre aucune invite (Partager → « Sur l'écran d'accueil » → Ajouter, trois gestes dans Safari), et les navigateurs intégrés de WhatsApp, Instagram ou Facebook ne savent pas installer du tout. L'app réduit la friction au minimum :

- un **service worker** (`public/sw.js`, rien en cache, une page hors ligne) rend l'app installable sur Android : Chrome propose alors l'événement `beforeinstallprompt`, et la carte affiche un seul bouton **« Installer l'app »** qui ouvre la fenêtre d'installation native ; Samsung Internet affiche son icône d'installation dans la barre d'adresse ;
- une **carte « Mets l'app sur ton écran d'accueil »** (`Installer.tsx`), visible tant que l'app tourne dans un navigateur, qui détecte le cas : navigateur intégré (dire d'abord d'ouvrir dans Safari ou Chrome), iPhone (les trois gestes avec les icônes), Android (le bouton, sinon les gestes du menu Chrome ou Samsung Internet). « Plus tard » la cache pour la session, « C'est fait » pour 30 jours ; une fois installée (`appinstalled` ou mode standalone) elle disparaît ;
- le manifeste par jeton (`start_url` avec le jeton, icônes `any` et `maskable`, `standalone`, couleur de thème) et les icônes Apple, pour que l'icône ouvre directement l'espace du clipper, en plein écran.

Le journal d'usage reçoit `install:affiche`, `install:prompt`, `install:accepte`, `install:refuse`, `install:fait`, `install:plus_tard`, `install:ok` : on sait combien ont vu la carte et combien ont installé.

## Team Leaders et comptes Instagram (12/10)

Gaëtan (12/10) : « Crée une application pour les team leaders… un onglet avec un lien direct vers Instagram pour voir les comptes de ses clippeurs… un onglet paye… il fait les deux jobs, il faut séparer ses revenus… et dans l'app clippeur, un onglet où il peut mettre à jour le @ de ses 3 comptes ». Ce n'est pas une app de plus : c'est la même app clippers, avec deux onglets en plus.

- **Comptes** (tout le monde) : ses comptes dans l'ordre du parcours (1, 2, 3), l'ETAT, les followers et les Reels sur 7 jours. Chaque @ ouvre Instagram. « Ce n'est pas le bon @ ? Modifier » : le nouveau @ est vérifié (lettres, chiffres, point, tiret bas ; un lien instagram.com est accepté), puis ajouté à l'onglet « Pseudos app » du tableur d'usage. Le bot l'applique sous 15 minutes avec la règle de `!pseudo` (classeur, fiche, scan), puis l'app affiche « en cours », la réussite, ou la raison du refus.
- **Équipe** (Team Leader seulement) : la prime d'équipe en cours (10 $ par clipper à 500 visites payées ou plus sur la quinzaine), puis chaque clipper de son équipe avec ses visites payées de la période, une barre vers les 500, et ses comptes, chacun ouvrant Instagram d'un appui pour faire un retour.
- **Versements** d'un TL : le montant de la période est séparé en « Tes clics (clipper) » et « Prime de Team Leader », avec le total et le prochain versement qui les additionne.

**24/10 — l'équipe passe dans Comptes.** Gaëtan : « dans les comptes, les comptes du team leader et ensuite les comptes de son équipe… deux onglets ». L'onglet Équipe disparaît : tout le monde a les quatre mêmes onglets (Drive, Reels, Comptes, Versements) et un TL arrive sur Comptes, qui a deux vues retenues sur le téléphone :

- **Mes comptes** : exactement l'onglet d'un clipper (son activité, ses @ modifiables, Metricool).
- **Mon équipe** (`src/components/MonEquipe.tsx`, route `/api/k/<jeton>/equipe` inchangée) : « À suivre », replié, regroupe par clipper ce qui demande une action (banni, appel à faire, à créer, aucun compte, clics pas encore relevés ; règle dans `src/lib/suiviEquipe.ts`, testée par `tests/suivi-equipe.cjs`), puis le même pilotage horizontal que l'app d'un clipper sur ses seuls clippers : clics, Reels postés, vues, chaque @ ouvre Instagram. La prime d'équipe reste dans Versements. Le journal d'usage garde `onglet:equipe` pour la vue Mon équipe.

Tout ce qui est lu dans le tableur d'usage (Comptes, Mon équipe, pilotage, le fait d'être TL) dépend de `GOOGLE_SERVICE_ACCOUNT_JSON` sur Vercel : si Google refuse la clé (« Google OAuth 400 » dans les logs, panne du 22/10), un TL voit l'app d'un simple clipper et Comptes reste « en cours de mise à jour ». La clé doit être la même que celle du bot sur Railway (projet « BOT Marketing », service « Claude-skill », variable `GOOGLE_SERVICE_ACCOUNT_JSON`). Le 24/10 à 10 h 09 (Dubaï), le déploiement de la #117 était encore refusé par Google : la clé collée sur Vercel n'était pas la bonne.

**24/10 — la clé surveillée.** `/api/sante` dit si Google accepte la clé de l'app (`{"google":"ok"}`, sinon 503 avec la raison de Google et le début de l'identifiant public de la clé, jamais la clé). Le bot l'interroge toutes les 5 minutes (`bot_discord.surveiller_google`) : refus tenu 10 minutes → alerte au salon admin avec le remède, rappel toutes les 12 h, « ✅ » au retour. `APP_SANTE_URL` vide côté Railway coupe la surveillance. Les erreurs de `src/lib/google.ts` donnent maintenant la raison de Google (« invalid_grant: Invalid JWT Signature »…) au lieu d'un simple « 400 ».

**24/10 — Ma semaine et la prime volume.** Gaëtan : « affiche la cadence sur les sept derniers jours, les vues, les followers et les clics » ; « dans les versements, un truc par rapport à l'objectif ».

- **Comptes** s'ouvre sur « Ma semaine » (`src/components/MaSemaine.tsx`) : cadence en Reels par jour, vues, followers et clics payés des 7 derniers jours clos, puis les Reels publiés jour par jour au-dessus des clics de chaque jour. Elle remplace « Mon activité » (le pilotage de l'admin). Puis « Mes comptes Instagram » : tous ses comptes, n° 4+ compris, sans les BAN ni les anciens @ (`src/lib/comptesVisibles.ts`).
- **Versements** porte la carte « Prime volume » (`src/components/PrimeVolume.tsx`, route `/api/k/<jeton>/prime`) pour ceux qui sont payés au clic : la moyenne de Reels par jour et par compte de croissance sur les jours clos de la période, et les trois paliers de l'annonce du 21/10 (3 Reels et 200 clics → +10 $, 6 et 400 → +20 $, 9 et 600 → +30 $). Règle confirmée par Gaëtan le 24/10 : « la prime est la cadence moyenne sur chaque compte de croissance ». Chaque compte doit tenir le palier : la cadence retenue est celle du moins actif de ses 2 comptes de croissance les plus actifs, et la carte montre chaque compte. C'est une estimation : la prime est validée par l'agence.
- Les Reels jour par jour viennent de la colonne N « Reels par jour (17 j) » de « Comptes app », publiée par le bot (`dashboard.reels_par_jour`, les Reels vus par le bot, un minimum). Tant qu'elle manque, la cadence retombe sur « Reels 7 j » et la carte de prime dit « en cours de relevé ». Les calculs sont dans `src/lib/activite.ts`, testés par `tests/activite.cjs`.

Qui est dans l'équipe de qui : la colonne **« Team leader »** des onglets créatrices du classeur des logins (le prénom du TL sur les lignes de chaque clipper, cellule fusionnée possible). Sans colonne remplie, la règle du 10/10 tient (`!tl Créatrice @X` : toute la créatrice). Le bot publie l'onglet **« Comptes app »** du tableur d'usage (Clé app, Prénom, Créatrice, N°, @, ETAT, Followers, Reels 7 j, Vues 7 j, Clé app TL, Prénom TL) à chaque passage du Dashboard ; l'app le lit avec 2 minutes de cache (`src/lib/comptesApp.ts`).

Routes : `/api/k/<jeton>/comptes` (GET ses comptes et ses demandes ; POST `{ n, handle }`, 5 par minute au plus) et `/api/k/<jeton>/equipe` (GET, 404 si ce n'est pas un TL).

## Pilotage de Gaëtan (12/10) : Vertical, Horizontal, Subs

Gaëtan (12/10) : « une app Vercel pour tracker au quotidien les clics de toute la team : un onglet vertical, un onglet horizontal, un onglet subs ; vertical avec les stats des créatrices et de leurs gros comptes ». C'est une page de plus dans cette app, réservée à Gaëtan : **`/p/<jeton>`**, jeton = HMAC-SHA256(`ADMIN_SECRET`, "pilotage") en base64url, 24 caractères (aucune variable de plus sur Vercel). Pour l'avoir : **`!pilotage`** sur Discord (admins seulement, réponse en message privé), ou l'onglet « Accès pilotage » du tableur « App clippers · usage », ou `/api/admin/liens?cle=<ADMIN_SECRET>&format=texte` (première ligne).

**Aucun appel GAML, Apify ni Metricool ici.** Le bot publie quatre onglets dans le tableur « App clippers · usage » (`tools/bot_clippers/pilotage.py`, à chaque passage du Dashboard, toutes les 15 minutes, chaque onglet seulement s'il a changé) ; la page les lit en un appel (`src/lib/pilotage.ts`, 2 minutes de cache) et se relit toute seule toutes les 5 minutes :

| Onglet | Une ligne = | Colonnes |
|---|---|---|
| Pilotage comptes | un compte Instagram du Dashboard, état du moment | Créatrice, Axe, Type, Gérant, @, ETAT, Followers, Δ 24 h, Δ 7 j, Followers 7 j, Reels auj./hier/7 j, Vues 7 j (48 h) et 7 j d'avant, Clics auj./hier/7 j/7 j d'avant, Dernier Reel, Mesure |
| Pilotage clics | jour × créatrice × axe × source × personne, 62 jours | Jour, Créatrice, Axe, Source, Qui, Visites payables, Visites hors robots, Liens, Liens non relevés |
| Pilotage subs | jour × créatrice (Data G&M), 62 jours | Jour, Créatrice, Subs OF, CA OF ($), Subs MYM, CA MYM (€), Saisi |
| Pilotage infos | – | Publié, Fraîcheur (celle du titre du Dashboard), Taux USD→EUR |

Les trois onglets, avec un sélecteur **Auj. · Hier · 7 j · 30 j** (comparé à la période d'avant de même longueur ; « Auj. » n'est pas comparé, la journée n'est pas finie) et un filtre par créatrice :

- **Vertical** : ce que les créatrices font percer elles-mêmes. Visites payables de leurs pages (page principale, bio Instagram, YouTube, Facebook), followers de leurs gros comptes (écarts 24 h et 7 j, courbe 7 jours), Reels et vues à 48 h, puis une carte par créatrice : visites par source et chacun de ses comptes (lignes du classeur dont le Gérant est la créatrice ou dont l'Utilisation est « Compte de la créatrice »).
- **Horizontal** : visites payables, coût à 0,05 $, clippers actifs, comptes Instagram et graphique 30 jours inchangés. Le **classement** affiche directement chaque prénom, sa créatrice en couleur, ses clics et leur évolution sur 7 jours clos, une courbe 7 jours, puis les totaux Reels/vues des deux comptes de croissance. Les lignes 1️⃣, 2️⃣ et 🔒 portent les @ ouvrant Instagram, les followers, les vues (croissance) ou clics (privé). Sous chaque croissance : Reels 7 j et hier ; sous le privé : lien GAML attribué. Trois emplacements d'origine au maximum, bans masqués sans promotion d'un compte 4+. Les données manquantes restent « – », les totaux incomplets « ≥ ». La même interface est servie aux TL via `/api/k/<jeton>/equipe`, filtrée côté serveur par leur équipe, sans subs ni CA des autres équipes. Les redirections indiquées sont à vérifier sur Instagram, pas déclarées automatiquement conformes.
- **Subs** : nouveaux abonnés OnlyFans et MYM, CA net en euros (OnlyFans converti au taux du bot), € par abonné, **subs pour 100 visites** (abonnés rapportés aux visites payables de tous les liens de la période), une ligne par créatrice, et les jours non saisis dans Data G&M signalés.

Règle partout : jamais un faux 0. Un jour de lien pas encore relevé est compté à part (« ≈ » devant la somme, « relevé(s) en attente »), un followers illisible reste « – ». La pastille « MAJ il y a … » passe en orange au-delà d'une heure sans publication du bot.

**App de chaque clipper — Comptes** : le même composant Horizontal affiche son pilotage personnel (Auj., Hier, 7 j, 30 j et fiche 1️⃣/2️⃣/🔒). Le GET `/api/k/<jeton>/comptes` filtre les statistiques côté serveur sur le propriétaire du jeton ; il ne livre ni les autres clippers, ni leurs comptes, ni les subs ou CA. L'édition des @ et les connexions Metricool restent accessibles sous « Gérer mes comptes et Metricool ». Une panne de la source statistique ne bloque pas la gestion des comptes.

## Pile

Next.js 14 (App Router), Tailwind, Recharts, TypeScript. Déployée sur Vercel (projet `app-clippers`, domaine `app-clippers.vercel.app`) avec `tools/app_clippers` comme répertoire racine ; `vercel.json` ignore les commits qui ne touchent pas ce dossier. Mise en ligne le 6 octobre 2026.

## Variables d'environnement (Vercel, jamais dans le dépôt)

| Variable | Contenu |
|---|---|
| `GAML_API_KEY` | la clé API GetAllMyLinks de l'agence (lecture seule ici) |
| `CLIPPERS_SECRET` | 32 octets aléatoires (base64url) : la graine des jetons |
| `ADMIN_SECRET` | 32 octets aléatoires : la clé de la route d'administration |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | le JSON du compte de service de l'agence (lecture Drive, écriture du seul tableur d'usage), le même que l'app créatrices |
| `CREATRICES_JSON` | le même contenu que l'app créatrices (`prenom`, `racine`, `reels`, `photos` par créatrice ; les jetons des créatrices y sont ignorés) |
| `DRIVE_SOURCES` | le même JSON que le bot Discord : `{ "Chloé": { "parent": "<id de 🎬 Clippers>", "sources": [{ "id", "sous": "Reels|Photos|Stories|Carrousel" }] } }` |

`.env.local` sert au test en local et reste ignoré par Git (`.env.local.exemple` donne la forme).

## Sécurité

- Aucun mot de passe : le jeton dans l'URL est la clé. Un jeton inconnu renvoie 404 sans détail ; si GAML ne répond pas, la page dit « réouvre dans une minute » plutôt que « lien invalide ».
- `X-Robots-Tag: noindex`, `Referrer-Policy: no-referrer` : le lien ne fuit pas dans les en-têtes vers Drive.
- L'API ne renvoie que des chiffres, l'URL publique du lien GAML du clipper et des identifiants de dossiers Drive qu'il peut ouvrir. Jamais l'identifiant GAML interne.
- La route d'administration compare la clé en temps constant et répond 404 sans la bonne clé.
- `POST /api/liens` n'a pas de clé mais ne renvoie que le nombre de clippers : les liens personnels partent seulement dans l'onglet « Liens app » du tableur d'usage, privé (Gaëtan et le compte de service). Ce tableur donne accès à la paie et à l'adresse USDC de chaque clipper : ne jamais le partager.

## Journal d'usage (pour l'agence)

Même mécanisme que l'app créatrices : chaque ouverture, changement d'onglet, tuile Drive et copie du lien envoie un événement à `/api/k/<jeton>/ev`. L'app écrit une ligne (date, heure Paris, prénom, événement, mode app ou navigateur) dans un tableur nommé exactement « App clippers · usage », à créer une fois par l'agence dans son Drive (dossier « [A] G&M — Interne ») et à partager en modification avec le compte de service. L'app le trouve par son nom et prépare l'onglet « Événements » elle-même. Sans tableur, rien n'est écrit et l'app ne s'en plaint pas.

## Routes

- `/k/<jeton>` : l'application ; `/k/<jeton>/manifest.webmanifest` : son manifeste (start_url avec le jeton, icônes `any` et `maskable`).
- `/p/<jeton>` : le pilotage de Gaëtan ; `/api/p/<jeton>` : ses tables (JSON) ; `/p/<jeton>/manifest.webmanifest` : son manifeste.
- `/api/k/<jeton>/versements` : chiffres de la période (JSON).
- `/api/k/<jeton>/drive` : le dossier racine (nom, adresse) ouvert par chacune des quatre tuiles, pour vérification.
- `/api/k/<jeton>/adresse` : GET l'adresse USDC enregistrée (ou `null`), POST `{ "adresse" }` l'enregistre après validation (5 essais par minute).
- `/api/admin/adresses?cle=<ADMIN_SECRET>` : toutes les adresses USDC (JSON, ou `&format=csv` avec `;` pour Google Sheets), pour les paies du 5 et du 20.
- `/api/k/<jeton>/drive/<carrousel|top|story|reels>` : redirection 302 vers le dossier racine de la section.
- `/api/k/<jeton>/ev` (POST) : événement d'usage, liste fermée, 60 par minute et par clipper au plus.
- `/api/admin/liens?cle=<ADMIN_SECRET>` : « prénom → lien personnel » de tous les clippers (JSON), `&format=texte` pour une ligne par clipper à coller. Pour distribuer les liens à la main.
- `/api/liens` (POST, 08/10) : écrit l'onglet « Liens app » du tableur d'usage (Clipper, Créatrice, Lien de l'app, Liens GAML, Clé, Mis à jour), seulement si la liste a changé, une fois par minute au plus ; l'adresse des liens est toujours `APP_URL` (défaut `https://app-clippers.vercel.app`), jamais l'en-tête Host. Appelée par le bot Discord, qui lit ensuite l'onglet avec le compte de service (`tools/bot_clippers/lien_app.py`).

## Ajouter un clipper

Rien à faire ici : créer son lien GAML avec la note « Clipping Prénom » (ce que fait déjà `!lien` dans le bot). **Depuis le 08/10, le bot lui envoie son app tout seul** dans son salon perso dès que ses 3 comptes Instagram sont créés (étape du compte 3 fermée), avec son lien GAML ; `!app @clipper` la renvoie. Son dossier Drive et son « TOP 20 Reels » viennent du bot à l'onboarding.

## En local

```
npm install
cp .env.local.exemple .env.local   # puis remplir les six variables
npm run dev
```

## 24/10 — l'app part du LOG DASHBOARD (réalité d'abord)

Gaëtan : « j'en ai marre qu'on n'ait pas un visuel entre la réalité et ce qu'on affiche… je mets tout le temps à jour le sheet, log dashboard, pars de là ». Les comptes d'un clipper (Mes comptes, Mon équipe, classement) viennent de `src/lib/comptesReels.ts` (testé par `tests/comptes-reels.cjs`) :

- la colonne **Gérant** du LOG DASHBOARD (recopiée par le bot dans « Pilotage comptes ») décide : un @ de clipping dont le Gérant est le clipper s'affiche même s'il manque à la fiche du bot (n° 100+, sans « Modifier », le bot ne le connaît pas) ; un @ de sa fiche que la feuille donne à un autre, ou à personne, disparaît de chez lui ;
- la fiche du bot (« Comptes app ») garde les n° du parcours, seuls modifiables par « Modifier le @ » ; ses anciens @ (état vide) restent masqués ;
- **Mon équipe** montre tous les comptes actifs de chaque clipper, n° 4+ compris ; dans le classement, un compte actif hors des trois emplacements du parcours s'affiche en ➕, jamais promu à la place d'un 1, 2 ou 3 ;
- chaque compte en ligne porte une **alerte de relevé** quand le chiffre affiché n'est peut-être pas la réalité : introuvable sur Instagram (rouge), lecture limitée, abonnés non relus depuis une date, Reels non lus, aucun Reel ou dernier Reel vu il y a 3 jours ou plus (orange). Elles remontent aussi dans « À suivre ».

Cas qui l'ont motivé (24/10) : le meilleur compte de Mathieu (≈ 150 000 vues sur 7 jours) et celui de Pierre étaient invisibles, leur fiche du bot portant un @ à une lettre près de celui de la feuille ; le compte actif d'Esperance était son n° 5.

**24/10 — les chiffres Instagram viennent du suivi RapidAPI.** Gaëtan : « si le bot ne lit aucun compte du clipper, c'est nous le problème… on ne traque pas ses followers ». L'ancien relevé du bot (Apify, onglets « Comptes app » et « Pilotage comptes ») ne voit pas les comptes « restreints » : le compte de croissance de Caroline s'affichait vide alors que RapidAPI lui comptait 1 669 followers, 20 Reels et 223 683 vues en 7 jours. L'app lit maintenant « IG · Comptes » et « IG · Reels » (suivi RapidAPI, 3 passages par jour, `src/lib/igSource.ts`, cache 5 minutes, côté serveur seulement) et `src/lib/igSuivi.ts` remplace followers, Reels 7 j, vues 7 j, Reels jour par jour et dernier Reel de chaque compte que RapidAPI connaît, dans Mes comptes, Ma semaine, la prime volume et le pilotage (Mon équipe, classement). Le rôle suit ce que fait le compte : Reels publics → croissance, privé sur Instagram → privé, sinon la fiche du bot. Suivi illisible : l'ancien relevé reste. Testé par `tests/ig-suivi.cjs`.

La prime volume s'affiche compte par compte (« il faut que la moyenne du compte 1 soit supérieure à 3, il faut que la moyenne du compte 2 soit supérieure à 3 ») ; un seul compte de croissance : pas de prime.
