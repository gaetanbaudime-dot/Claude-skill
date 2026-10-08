# App clippers G&M

Petite application web mobile (PWA) pour les clippers, jumelle de l'app créatrices : un lien personnel par clipper, à ajouter sur l'écran d'accueil du téléphone (iPhone Safari « Sur l'écran d'accueil », Android Chrome « Ajouter à l'écran d'accueil »). Trois onglets en bas, dans l'ordre du dessin de Gaëtan (nuage, flèche, dollar) :

- **Drive** (onglet par défaut) : quatre tuiles, **Carrousel · TOP 20 Reels · Story · Reels** (les deux tuiles Reels à droite, sous le pouce), qui ouvrent le **dossier racine** de la section dans l'application Google Drive du téléphone ; le clipper fouille dedans (mois, semaines, tenues). Pas d'état ni d'emoji : un texte explicatif en haut, un en bas. Carrousel, Reels et Story = les sous-dossiers du dossier Instagram de sa créatrice (le parent de « 🎬 Clippers »), trouvés par leur nom ; en secours, les sources `DRIVE_SOURCES` (Reels, Photos, Stories) puis les dossiers de `CREATRICES_JSON`. TOP 20 Reels = le sous-dossier « TOP 20 Reels » de son dossier personnel (`🎬 Clippers / <Prénom>`), où le bot dépose ses variantes uniques ; s'il n'existe pas encore, le « TOP 20 Reels » de la créatrice, sinon son dossier personnel. Racines en cache 10 minutes. Les dossiers ne sont jamais créés ici.
- **Reels** : le duplicateur de Reels, écran « Bientôt », identique à celui de l'app créatrices.
- **Versements** : ses visites francophones GetAllMyLinks jour par jour (14 jours, ou la période de paie en cours si elle est plus longue), le montant de la période en cours, la phrase « Prochain versement : 40,65 $ le 20 octobre », aujourd'hui, hier, les périodes précédentes (montant et date de versement), et son lien GAML à mettre dans la bio de son compte privé, avec un bouton Copier. Le jour en cours se rafraîchit toutes les 5 minutes tant que l'onglet est ouvert. Sous le lien, **l'adresse USDC (ERC-20)** du clipper : il la colle, l'app la valide (`0x` + 40 caractères hexadécimaux), l'enregistre dans l'onglet « Adresses USDC » du tableur « App clippers · usage » (une ligne par clipper, remplacée à chaque modification, avec la date) et l'affiche en entier pour qu'il la vérifie. C'est là que l'agence lit les adresses pour les virements du 5 et du 20.

## Règles de paie (reprises de `tools/bot_clippers/paie_clics.py`)

0,05 $ par visite « francophone » (France, Belgique, Suisse, Canada, Luxembourg, Monaco, Réunion, Guadeloupe, Martinique, Guyane, Mayotte, Nouvelle-Calédonie, Polynésie), robots exclus par GAML, heure de Paris. Quinzaine du 1 au 15 → versée le 20 du mois ; du 16 à la fin du mois → versée le 5 du mois suivant (`periode_en_cours`, `prochaine_paie`). L'app annonce, le virement reste humain.

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
