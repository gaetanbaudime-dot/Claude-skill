# Bot FAQ Clippers (Discord + Claude)

Un bot **Discord** qui répond aux questions des clippers **uniquement à partir de `connaissances.md`**
(Kit Clipper + stratégie marketing officielle, **Instagram uniquement depuis le 14/09/2026**). S'il ne sait
pas → il renvoie vers Gaëtan. Il n'invente jamais. Réponses courtes, niveau collège.

**Pourquoi Discord et pas Telegram :** tes clippers vivent déjà dans Discord (le #faq, le reporting).
Le bot vit là où ils travaillent → **zéro nouvelle appli, zéro code d'accès** (être dans ton serveur =
accès). Ils tapent leur question dans un canal, ou mentionnent le bot. UX maximale.

> Le fichier `bot_discord.py` est le bot principal. `bot.py` (Telegram) est gardé en option mais n'est
> pas utilisé.

## Ce que les clippers peuvent envoyer

- **Du texte** : leur question, dans le canal dédié (ou en mentionnant le bot).
- **Des captures d'écran** (ex. un message de blocage Instagram) : le bot lit l'image et répond.
- **Des vocaux** : pas encore — le bot demande gentiment d'écrire.

## Mise en service (~15 min, une seule fois)

### 1. Créer le bot Discord (5 min)
1. Va sur **discord.com/developers/applications** → **New Application** (nomme-la « LTP Assistant »).
2. Onglet **Bot** → **Reset Token** → copie le token → c'est `DISCORD_TOKEN`.
3. Toujours dans **Bot**, active **Message Content Intent** (obligatoire pour lire les messages).
4. Onglet **OAuth2 → URL Generator** → coche **bot** → dans les permissions coche **View Channels**,
   **Send Messages**, **Read Message History** → copie l'URL en bas → ouvre-la → ajoute le bot à ton serveur.

### 2. Créer la clé API Claude (5 min)
1. **console.anthropic.com** → connexion → **Billing** : ajoute une carte + une **limite à 25 $/mois**.
2. **API Keys → Create Key** → copie la clé (`sk-ant-…`) → c'est `ANTHROPIC_API_KEY`.

### 3. Trouver les identifiants Discord (2 min)
1. Dans Discord : **Réglages → Avancés → Mode développeur** = ON.
2. **Clic droit sur le canal** où le bot doit répondre → **Copier l'identifiant** → c'est `CANAL_BOT_ID`
   (crée un canal `#assistant` dédié, c'est le plus propre).
3. **Clic droit sur ton profil → Copier l'identifiant** → c'est `ADMIN_IDS` (pour `!stats` et `!apprendre`).

### 4. Déployer sur Railway pour le 24/7 (5 min)
Le bot doit rester allumé quand ton Mac est éteint.
1. **railway.app** → connecte GitHub → **New Project → Deploy from GitHub repo** → `gaetanbaudime-dot/Claude-skill`.
2. **Settings → Root Directory** → `tools/bot_clippers`.
3. **Variables** → `DISCORD_TOKEN`, `ANTHROPIC_API_KEY`, `CANAL_BOT_ID`, `ADMIN_IDS`, et **`DONNEES_DIR=/data`**.
4. **New → Volume** monté sur **`/data`** (pour que le journal et la FAQ apprise survivent aux redémarrages).
5. Déploie → les logs affichent « Bot Discord démarré ». Écris dans ton canal `#assistant` pour tester.

**Pour tester d'abord sur ton Mac** (facultatif) : remplis `.env`, `pip install -r requirements.txt`,
`python3 bot_discord.py`. Ça tourne tant que le terminal est ouvert.

## Canal propre + tri automatique par sujet (salon Forum, recommandé)

Pour que chaque question soit **son propre post rangé** (au lieu d'un mur qui défile) et que le tout
soit **trié par sujet**, utilise un **salon Forum** au lieu d'un canal texte :

1. Crée un **salon → Forum** (ex. `#assistant-ia`).
2. Dans ses réglages, crée ces **tags** (étiquettes de post), noms exacts :
   `Comptes`, `Warm-up`, `Reels`, `Routine`, `Blocages`, `Stratégie`, `Hors kit`.
3. Clic droit sur le forum → **Copier l'identifiant** → mets-le dans `FORUM_BOT_ID` (Railway).
4. **Auto-tri** : donne au bot la permission **Gérer les publications** sur ce forum (réglages du
   forum → Permissions → rôle du bot). Le bot pose alors tout seul le bon tag (il sait de quelle fiche
   il parle). Sans cette permission, il répond quand même — il ne pose juste pas le tag.

Le tag **`Hors kit`** est précieux : il marque les questions auxquelles le bot n'a pas su répondre →
tu filtres dessus pour voir exactement quoi ajouter au kit. `CANAL_BOT_ID` (canal texte) et
`FORUM_BOT_ID` peuvent coexister ; tu peux retirer le canal texte une fois le forum en place.

## Distribution aux clippers

Rien à distribuer ! Ils sont déjà dans le serveur. Dis-leur juste : « pose tes questions dans #assistant ».
Pour retirer quelqu'un : retire-le du serveur Discord (ou du canal). Aucun code à gérer.

## Coût

Modèle par défaut **`claude-haiku-4-5`** (rapide, quasi gratuit). Coût API ≈ **1-2 €/mois** même à fort
volume. Le total est dominé par l'hébergement (~5 $/mois Railway). Total réaliste : **~5-7 $/mois**.
Pour des réponses plus fines : `MODELE=claude-opus-4-8` (~5x plus cher, reste sous ~10 €/mois).

## Commandes v2 en un coup d'œil

`!aide` (liste adaptée au rôle : admin, manager, clipper, candidat) ·
`!paiement @x 50 [raison]` · `!ajuster -150 [raison]` (corrige/rattrape le compteur) ·
`!compteur` · `!rang @x Rookie|Confirmé|Élite` · `!invites` · `!bumps` (public, classement du mois) ·
`!verifier` (audit config) · `!audit` (carte du serveur) · `!stats` · `!apprendre Q | R` ·
`!comptes` · `!inputs [maintenant|test|detail]` (Reels publiés : nu = dernier bilan) · `!subs Prénom n` (abonnés OF du mois) ·
`!primes [AAAA-MM]` (paie variable) · `!creatrice @x Prénom` · `!sortie @x raison` · `!relance @x` ·
`!alias` / `!code` (relais 2FA, managers). Une commande inconnue est signalée (plus de silence).

## 🏅 Prime discipline et paie variable — `!primes`

**La grille du 07/09, passée en Instagram seul le 14/09** : un clipper = 2 comptes IG de croissance + 1 compte
privé (porte le lien), **2 Reels/jour sur CHAQUE compte de croissance** (par surface, pas en somme : 4 Reels
sur un compte et 0 sur l'autre = journée ratée). Les pages Facebook ne font plus partie de la structure
(`STRUCTURE_FB_MIN=0` par défaut ; remettre `3` pour les réactiver). La prime discipline (50 €)
est **tout-ou-rien** : structure complète (IG, compte privé) ET chaque surface à la cadence ;
la prime tombe à **26 journées validées** dans le mois. La **journée** est la journée calendaire de
la veille, minuit à minuit heure de Paris — plus une fenêtre glissante de 24 h.

**Ce qui ne pénalise pas** (depuis le 10/09) : une panne Apify Facebook → journée *non évaluée*
(⏸️), jamais invalidée ; un nouveau clipper (date de `!creatrice`) est en warm-up la semaine 1
(0 publication exigée) puis à 1 Reel/jour/surface la semaine 2 (`NOUVEAU_JOURS=14`).

**Le variable se saisit** : `!subs Prénom 37` (abonnés OF du mois, depuis les stats des liens de
tracking) → `!primes` calcule 0,50 €/abonné pour le clipper, et pour le manager : 100 € par clipper
**actif** (≥ 80 % des journées évaluées) + 0,30 €/abonné de l'équipe + palier sur le total
d'abonnés (>1 000 → 300 €, >2 500 → 800 €, >5 000 → 1 600 €, non cumulés) + 150 € **une fois** si
tous ses clippers ont leur prime. La règle des 50 abonnés du premier mois est signalée.

**Règle de sortie automatique** : deux journées ratées de suite → alerte immédiate au manager
(`CANAL_MANAGER_ID`) avec la commande `!sortie` prête ; la ligne apparaît aussi dans le récap.

Réglages Railway : `CADENCE_REELS_MIN=2` (défaut) · `STRUCTURE_IG_MIN=2` · `STRUCTURE_PRIVE_MIN=1` ·
`STRUCTURE_FB_MIN=0` (Instagram seul) · `PRIME_JOURS_MIN=26` · `PRIME_CLIPPER_EUR=50` · `MANAGER_PAR_CLIPPER_EUR=100` ·
`MANAGER_BONUS_EQUIPE_EUR=150` · `ACTIF_TAUX_MIN=0.8` · `MANAGER_PRENOM=Jonas` · `NOUVEAU_JOURS=14`.
Si des pages Facebook sont encore déclarées (onglet `FaceBook`, `SHEET_CSV_FB_URL`), elles sont mesurées
mais n'entrent plus dans la structure exigée. Le cycle quotidien est retenté 3 fois ; un jour d'échec n'est jamais marqué
fait. `!inputs` seul lit le dernier bilan ; `!inputs maintenant` relance le cycle.

## 🔐 Relais des codes 2FA vers les managers — `codes_2fa.py`

**Pourquoi** : les comptes Instagram sont créés avec des alias « Masquer mon adresse » iCloud qui
renvoient tous vers une seule boîte mail — chaque création de compte et chaque 2FA passait donc
par Gaëtan. Le relais lit une boîte mail **dédiée** et pousse le code dans le salon du manager qui
possède l'alias : un manager crée ses comptes sans l'admin.

**Mise en place (10 min, une seule fois) — sur ta boîte Gmail habituelle, sans en créer une autre** :
1. Gmail → crée un **filtre** : `De : instagram.com OU facebookmail.com` → *Appliquer le libellé* **Codes**
   (+ *Ignorer la boîte de réception* si tu veux ne plus les voir). Le bot ne lira QUE ce libellé.
2. Compte Google → Sécurité → validation en deux étapes activée → **Mots de passe des applications** →
   génère-en un pour « Bot codes ». Gmail → Paramètres → Transfert et POP/IMAP → **IMAP activé**.
3. Railway → Variables : `CODES_IMAP_USER=<ton adresse Gmail>` · `CODES_IMAP_PASSWORD=<mot de passe
   d'application>` · `CODES_IMAP_DOSSIER=Codes` · facultatif `ROLE_MANAGER_NOM=Manager`.
4. Le manager, **dans son salon privé** : `!alias ajouter prenom.xxx@icloud.com` (un ou plusieurs).

⚠️ Un mot de passe d'application donne un accès IMAP complet à la boîte : il ne vit que dans Railway,
et se révoque en un clic depuis le compte Google si l'hébergeur fuit. Le code, lui, ne lit que le
libellé `Codes` et n'en extrait que les codes d'expéditeurs Meta.

**Au quotidien** : dès qu'un code Instagram/Facebook arrive sur un alias rattaché, le bot le poste
dans le salon du manager sous 45 s (`🔐 Instagram — code pour alias : 482913`). À la demande :
`!code alias@icloud.com` (30 dernières minutes). Alias inconnu → le code remonte au salon admin,
rien ne se perd. `!alias liste` / `!alias retirer <alias>` pour gérer le registre.

**Sécurité** : seuls les mails des expéditeurs Meta sont lus, seul le code est relayé (jamais le corps
du mail), et un manager ne peut demander que les alias rattachés à son propre salon.

## Suivi des inputs clippers (Reels publiés par jour) — `inputs_clippers.py`

**Pourquoi** : les rapports GAML mesurent les clics (l'output). Un clipper qui publie 12 Reels qui
flopent et un clipper qui ne publie rien y sont identiques (0 clic) — impossible de piloter la
discipline. Ce module mesure ce que le clipper contrôle : **le nombre de Reels publiés**.

**La source de vérité : le Google Sheet** (`SHEET_CSV_URL`). À défaut, le bot retombe sur les
**descriptions (topics) des salons Discord** — ainsi une panne du Sheet n'arrête jamais le suivi.
Il interroge ensuite Apify une fois par jour et poste le bilan (4 lignes) dans le salon privé de chaque
clipper + le rapport du matin dans le salon du manager (Telegram : le lundi seulement, voir ci-dessous).

### 🔐 Brancher le Sheet en 3 minutes (à faire une seule fois)

⚠️ **Ne publie JAMAIS l'onglet qui contient les mots de passe.** On publie un onglet dédié qui n'a
que des colonnes non sensibles, alimenté automatiquement par formule.

1. Dans le classeur, crée un onglet **`Tracking`** à **3 colonnes** : `ETAT` · `Compte` · `Gérant`.
   Remplis-le par formules, en deux blocs empilés (locale FR : `=Instagram!A2:A` etc.) — un bloc
   Instagram, puis un bloc Facebook plus bas qui pointe la colonne des **URL de page**.
   **Une seule colonne « Compte » suffit pour les deux plateformes** : le bot reconnaît une page
   Facebook à son écriture (`facebook.com/…` ou `fb:nom`) et tout le reste comme un compte
   Instagram. Ainsi **un seul onglet est publié**, et les onglets Instagram et FaceBook — qui
   contiennent les mots de passe — ne quittent jamais le classeur.
2. **Fichier → Partager → Publier sur le web** → sélectionne **l'onglet `Tracking`** (jamais
   « Document entier ») → format **CSV** → **Publier** → copie l'URL.
3. Railway → Variables → `SHEET_CSV_URL=<l'URL copiée>`. Terminé.

Le bot lit les colonnes par mot-clé dans l'entête (ordre libre) : `@`/`compte`/`pseudo` →
identifiant Instagram · `gérant`/`clipper` → à qui il appartient · `état`/`statut` → filtre ·
`facebook`/`fb`/`page` → page Facebook (URL complète, `fb:nom` ou nom nu, au choix).

**États ignorés** (jamais scrapés, donc zéro crédit gaspillé et zéro faux « injoignable ») :
`ban`, `banni`, `mort`, `supprimé`, `fermé`, **`à créer`**, `à faire`, `attente`, `réserve` —
comparaison insensible aux accents et à la ponctuation. Personnalisable via `SHEET_ETATS_MORTS`.

**Pages Facebook depuis leur propre onglet** : si tes pages vivent dans un onglet `FaceBook` séparé
(colonnes `URL Page` et `Gérant`), publie-le aussi en CSV et pose `SHEET_CSV_FB_URL` — rien à
recopier. Un gérant qui n'a que des pages FB (opérateur Metricool sans compte Instagram) est ajouté
automatiquement à la cartographie.

Le **salon privé** de chaque clipper est retrouvé par son prénom : le salon doit s'appeler comme
le gérant écrit dans le Sheet (les emojis en préfixe sont ignorés). `!comptes` signale ceux dont
le salon n'a pas été trouvé. Les gérants nommés `xxx`, `yyy`, `zzz`, `reserve`… sont ignorés
(réserves de comptes non attribués).

Instagram porte la cadence exigée ; Facebook n'est qu'un second regard, puisque les Reels y sont
republiés depuis Instagram — sans page déclarée, aucun appel Facebook, donc aucun coût.

**Sécurité plateforme** : Apify interroge des profils **publics** depuis sa propre infrastructure,
**sans aucune authentification**. Meta voit un visiteur anonyme non attribuable à un compte de
l'agence : aucun risque de ban. ⚠️ **Ne jamais fournir de `sessionid`, de cookie ou d'identifiants
Instagram à un actor Apify** — c'est la seule chose qui créerait un risque réel.

**Sécurité données** : les topics contiennent aussi des mots de passe. Le module n'extrait que les
`@` et ne journalise jamais un topic brut.

| Variable | Rôle |
|---|---|
| `APIFY_TOKEN` | **Obligatoire.** Sans elle, tout le module reste inerte. Apify → Settings → API & Integrations |
| `SHEET_CSV_URL` | URL CSV de l'onglet `Tracking` publié (source de vérité des comptes Instagram) |
| `SHEET_CSV_FB_URL` | URL CSV de l'onglet `FaceBook` publié (colonnes `URL Page` + `Gérant`) — facultatif |
| `SHEET_ETATS_MORTS` | États du Sheet exclus du scraping (défaut `ban,banni,mort,supprime,ferme`) |
| `SHEET_HISTORIQUE_URL` / `SHEET_HISTORIQUE_SECRET` | Archivage quotidien dans l'onglet `Historique` (voir `historique_inputs.gs`) |
| `APIFY_ACTOR_IG` | Actor Instagram (défaut `apify~instagram-profile-scraper`) |
| `APIFY_ACTOR_FB` | Actor Facebook (défaut `apify~facebook-posts-scraper`) |
| `FB_POSTS_MAX` | Publications lues par page Facebook (défaut `6` — ~2 $/1 000) |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | Rapport hebdo du lundi sur Telegram (quotidien seulement si `TELEGRAM_QUOTIDIEN=1`) |
| `RAPPORT_CLIPPER` | `court` (défaut, 4 lignes) ou `long` |
| `CADENCE_REELS_MIN` | Reels/jour exigés par compte (défaut `3`) |
| `HEURE_RAPPORT_INPUTS` | Heure UTC d'envoi (défaut `9` — 11 h à Paris, 13 h à Dubaï) |
| `SALONS_RESERVE` | Salons ignorés, séparés par des virgules (défaut `xxx,yyy,zzz,reserve,…`) |
| `OBJECTIF_COMPTES_IG` | Objectif de comptes Instagram **vivants** par créatrice prioritaire (défaut `20`) |
| `TOP_CREATRICES` | Créatrices suivies dans la ligne « surfaces » du rapport (défaut `Chloé,Sarah,Sophie,Maddie`) |

**Mise en route** : `!comptes` vérifie la cartographie lue sur le serveur · `!inputs test` lance un
scrape sans rien envoyer aux clippers · `!inputs` lance le cycle complet · `!inputs detail` affiche
la version longue (ligne par clipper) — le rapport quotidien, lui, est court : total et tendance,
qui est à zéro, l'inventaire de surfaces face à l'objectif, et UNE priorité.

**La ligne « surfaces »** (`🏗️ IG vivants /20`) exige une colonne `Créatrice` dans l'onglet
`Tracking` publié : le bot compte les comptes non morts par créatrice et affiche le manque face à
`OBJECTIF_COMPTES_IG`, plus la file « à créer » déjà préparée dans le sheet.

**Coût** : ~1,60 $/1 000 profils. À 6 clippers (18 comptes), ≈ **4 $/mois** — le plan gratuit
(5 $ de crédits) suffit ; le plan Starter à 29 $ couvre jusqu'à ~20 clippers.

### 📈 Archiver l'historique dans le Sheet (`historique_inputs.gs`)

Le bot garde 90 jours sur son volume Railway — utile mais technique et volatil. Pour conserver la
courbe complète de chaque clipper : colle **`historique_inputs.gs`** dans l'Apps Script du classeur,
change `SECRET`, déploie en **Application Web** (« exécuter en tant que MOI », « accès TOUT LE
MONDE » — c'est le secret qui protège, pas l'URL), puis pose `SHEET_HISTORIQUE_URL` (l'URL `/exec`)
et `SHEET_HISTORIQUE_SECRET` sur Railway.

Chaque jour, une ligne **par compte** est ajoutée à l'onglet `Historique` : date, clipper, créatrice,
compte, plateforme, posts 24 h, vues, abonnés, delta, état. Le détail par compte (et non par clipper)
permet de voir quel compte porte réellement un clipper et de dater un ban au jour près. Rejouer une
journée écrase proprement les lignes de cette date — pas de doublon.

**Fuseau et secret** : l'anti-doublon compare les dates dans le fuseau du classeur (plus en UTC), et le
script refuse d'écrire tant que `SECRET` est resté à sa valeur par défaut (12 caractères minimum).

**Alerte 🔞** : un compte marqué « 18+ » par Instagram est **invisible aux visiteurs non connectés**
et sa portée organique est détruite — publier plus n'y change rien. Le module le détecte et le
remonte en priorité absolue, au clipper comme en admin.

## v2 — le bot du programme clippers (compteur, paiements, invitations, rangs)

Le bot fait maintenant tourner la boucle « paiement → preuve → contenu → clippers » :

### Commandes admin (depuis n'importe quel canal)

- **`!paiement @clippeur 50 fixe semaine 1`** → poste « 💸 X vient de recevoir 50 € ! » dans
  `#dopamine`, met à jour le compteur épinglé, trace dans `paiements.jsonl`. Le lundi des
  virements : une commande par virement effectué = la preuve publique instantanée.
- **`!compteur`** → (re)crée/met à jour le message épinglé « X € déjà versés aux clippers ».
- **`!rang @clippeur Rookie|Confirmé|Elite`** → assigne le rôle (crée d'abord les 3 rôles
  dans les réglages du serveur ; le rôle du bot doit être AU-DESSUS d'eux dans la liste).
- **`!invites`** → classement des invitations trackées (preuve d'attribution du parrainage).
- `!stats` et `!apprendre` inchangés.

### Tracking d'invitations + accueil numéroté (ACTIVER_V2=1)

Chaque clipper crée SON lien d'invitation ; le bot attribue chaque arrivée à son parrain,
poste « Bienvenue X — tu es le Nᵉ futur clipper ! » dans `#candidature` (avec le lien du
formulaire) et note l'attribution. **On tracke au join, on ne paie JAMAIS au join** — le
parrainage (50 €) se paie quand le filleul devient clipper actif.

⚠️ **Piège des salons verrouillés** : `#dopamine` et `#candidature` sont fermés à l'écriture
pour `@everyone` (voulu) — mais le bot hérite de ce blocage ! Ajoute une **exception pour le
rôle du bot** sur chaque salon verrouillé : Permissions → + → rôle du bot → ✅ Voir le salon,
✅ Envoyer des messages, ✅ **Gérer les messages** (nécessaire pour épingler le compteur).
Bonus : laisse « Ajouter des réactions » à ✅ pour `@everyone` (les 🔥 sans le bruit).

**Mise en service v2 (3 min, dans cet ordre)** :
1. Developer Portal → Bot → activer **SERVER MEMBERS INTENT** (2e interrupteur privilégié).
2. Donner au bot la permission **Gérer le serveur** (lecture des invitations) et
   **Gérer les rôles** (pour `!rang`), via son rôle sur le serveur.
3. Créer les rôles `Rookie`, `Confirmé`, `Elite` (réglages → Rôles), sous le rôle du bot.
4. Railway → Variables : `CANAL_DOPAMINE_ID`, `CANAL_CANDIDATURE_ID`, `LIEN_FORMULAIRE`,
   puis **`ACTIVER_V2=1`** en dernier. Redéploiement automatique.

⚠️ Sans l'étape 1, le bot **ne démarre pas** si `ACTIVER_V2=1`. Tant que `ACTIVER_V2`
n'est pas posé, tout le reste (paiements, compteur, rangs, FAQ) marche normalement —
le déploiement est sans risque.

## Le manager sur Discord : commandes, salon, contexte, liens des fiches (10/09)

- **Le rôle `Manager` (nom exact, `ROLE_MANAGER_NOM`) a sa liste blanche** : `!creatrice`, `!fiche`,
  `!tests`, `!test-ok`, `!test-non`, `!quiz-ok`, `!reset @membre` (remet le parcours candidat à zéro pour le rejouer — quiz, test, validation ; liaison, rôles et équipe conservés), `!pipeline`, `!relance`, `!inputs`, `!subs`, `!primes`,
  `!sortie`, `!comptes`, `!alias`, `!code`. `!aide` lui donne sa liste. Avant le 10/09, tout était réservé
  aux `ADMIN_IDS` alors que la base de connaissances promettait ces commandes au manager.
- **`CANAL_MANAGER_ID`** (Railway) : le salon privé du manager. Il y reçoit les tests rendus, les
  J'ACCEPTE, les alertes « 2 jours ratés », les sorties. Vide = tout reste dans le salon admin.
- **`!creatrice @clipper Chloé`** : ouvre au clipper les salons dont le nom contient le prénom de la
  créatrice **en mot entier** (les salons admin/bot/manager sont exclus — « gaetan » n'ouvre plus
  `#bot-gaetan`), **crée son salon perso** dans la catégorie de la créatrice (privé : lui, le manager,
  le bot — c'est là qu'arrive son bilan quotidien), note l'attribution au registre et le prévient en MP.
  Refusée sur un membre non signé (`… forcer` pour passer outre). `!creatrice @clipper` seul : l'attribution.
- **`!sortie @clipper raison`** : rôles Team/Grille/rangs retirés, accès nominatifs fermés, relances coupées,
  fiche déplacée dans `sortis.json`, MP au membre, alerte manager + admin + Telegram avec la liste des
  gestes manuels (Sheet, téléphone cloud, lien GAML, dernier décompte).
- **`!relance @x`** : envoie en MP la prochaine étape de SON parcours (numéro, quiz, test, e-mail,
  contrat, J'ACCEPTE), sans rien réinitialiser ; respecte son STOP (`… forcer` sinon).
- **`!fiche`** n'est acceptée qu'en salon privé ou en MP (elle affiche un numéro de téléphone).
- **Le bot sait où et à qui il parle** : chaque question lui arrive précédée de `[Contexte : salon #x ·
  rôles : …]`. Un `Manager` reçoit la section MANAGER de la base (missions, créneaux, commandes) ; un
  candidat reçoit le parcours. Fini le « tu es dans le mauvais salon » et le parcours candidat servi à Jonas.
- **Liens des fiches résolus tout seuls** : au démarrage puis toutes les 6 h, le bot lit le forum
  formation (`CANAL_FORMATION_ID`, sinon le premier forum dont le nom contient « formation ») et retrouve
  les posts par leur titre (« Bienvenue », « Fiche 1 » … « Fiche 6 », « Kit »). `POSTS_FORMATION` devient
  un simple secours, et un identifiant mort est purgé : plus de `#inconnu`. Un `<#id>` qui ne résout pas
  dans une réponse est remplacé par le libellé du post.
- **Réponses jamais coupées** : consigne « 900 caractères, 5 puces, jamais de tutoriel complet »,
  `MAX_TOKENS_REPONSE=700` (la limite de 420 du 10/09 coupait les réponses longues au milieu d'un mot), et si
  le modèle atteint quand même la limite, le texte est ramené à la dernière phrase complète avec la mention
  « réponse raccourcie ». Au-delà de 2 000 caractères, découpe sur des sauts de ligne.
- **Liens cliquables garantis (11/09)** : le bot pose les liens en post-traitement, sans dépendre du modèle —
  « Fiche 3 » devient le lien du post, « forum formation » le lien du forum, `#assistant-ia`, `#candidature`,
  `#bump`, `#dopamine`… les liens des salons (index des salons résolu au démarrage puis toutes les 6 h).
  L'étiquette finale « (Fiche 3 — …) » devient « (#Fiche 3 - Monter et Poster…) ». Le prompt porte une carte
  sujet → fiche (montage = Fiche 3, jamais la Fiche 2).
- **`EMAIL_FACTURATION`** (Railway, facultatif) : l'adresse où les clippers France envoient facture + RIB.
  Si elle est posée, le bot la donne quand on la lui demande ; sinon il renvoie vers le décompte du lundi.
- Les questions « hors kit » ne capturent plus les URL seules ni les messages de un ou deux mots.

## Recrutement international : pause et réouverture (`PAUSE_INT`)

Le tunnel international (quiz → test → conditions en MP → **J'ACCEPTE ouvre le rôle Team International
tout seul** → le manager attribue la créatrice) a été mis en pause le 15/08 et **rouvert le 08/09/2026**
(pôle malgache). Il est **ouvert par défaut** : ne pose `PAUSE_INT=1` dans Railway que pour re-suspendre
(le quiz d'un International n'envoie alors plus le test, il reçoit un message « en pause » unique, et les
relances se taisent). Depuis le 10/09 : le rôle n'est plus donné AVANT l'acceptation, le J'ACCEPTE manquant
est relancé à 24 h et 48 h, et `!purge-int` est neutralisée tant que le recrutement est ouvert.

**Relancer le stock après une pause (dans l'ordre)** :
1. Vérifie que `PAUSE_INT` est absent ou à `0` dans Railway (redéploiement automatique).
2. Feuille Google du quiz → Extensions → Apps Script → exécute **`rejouerReussites()`** une fois : elle
   re-poste un `QUIZ_OK` pour toutes les réussites (≥ 30/34, `QUIZ_SEUIL`, tenu aussi par le bot qui rétrograde en échec un QUIZ_OK sous le seuil) — le bot envoie le test à ceux qui ne l'ont
   jamais reçu et ignore les autres (idempotent). Les réussites survenues PENDANT la pause n'ont pas
   d'état dans le pipeline : c'est la seule façon de leur envoyer le test.
3. `!annonce-int` (simulation) puis `!annonce-int envoyer` : message de lancement en MP à tous les
   internationaux du serveur, une seule fois par membre.
4. Mets à jour le salon **Grille International** (rémunération/bonus) : le bot n'y écrit pas.

## 🔒 Serveur fermé : le tunnel candidat hors Discord (14/09, soir)

Décision du 14/09 : **plus personne n'arrive sur Discord avant validation** — le serveur est réservé aux
clippers validés. Le tunnel (formation → quiz → test 48 h → rendu) se déroule par e-mail et formulaires ;
Discord ne commence qu'au contrat (France) ou au J'ACCEPTE (International).

**Le tunnel, dans l'ordre**
1. **Formulaire de candidature** → `candidature_webhook.gs` (v2) poste `CANDIDATURE|…` comme avant **et
   envoie l'e-mail « formation + quiz »**. Le message de fin du formulaire ne donne plus le lien Discord.
2. **Quiz** (question « ton numéro WhatsApp » à la place de l'identifiant Discord) → `quiz_webhook.gs` (v4)
   poste `QUIZ_OK|<vide>|score|email|tel` et, **≥ 30/34, envoie le test par e-mail** (dossier de rushs +
   formulaire de rendu, 48 h) ; sinon score + deuxième essai (parcours terminé au 2ᵉ échec). Le bot tient le
   registre `hors_discord` (clé = numéro canonique) et prévient le manager.
3. **Formulaire « Rendu du test »** → `rendu_webhook.gs` (nouveau) poste `TEST_RENDU|prénom|tel|email|lien|remarque`
   → fiche dans le salon manager (prénom, pays, score du quiz, lien des Reels).
4. **Le manager juge** : `!inviter Prénom [fr|int]` crée une **invitation personnelle** (7 jours, une seule
   personne, détruite à l'arrivée) et rend le **message WhatsApp prêt à coller** ; `!refuser Prénom motif` idem
   pour un refus ; `!candidats` liste tout le monde par étape (tests à juger, invités pas arrivés, quiz en cours…).
5. **Arrivée par cette invitation** : liaison automatique (numéro, prénom, pays), état validé, grille, puis la
   suite habituelle — e-mail → contrat DocuSeal (FR) ou conditions → J'ACCEPTE (International). Plus de numéro
   à envoyer, plus de quiz, plus de test en MP. Le manager est prévenu.
6. **Tout autre arrivant, serveur fermé** : MP d'explication (le formulaire, la suite par e-mail) + expulsion.
   Deux exceptions : invité par un admin ou par un rôle protégé (manager, staff) → gardé, accueil léger ; porte
   d'entrée indécidable (invitations illisibles, lien de vanité) → gardé + alerte, jamais d'expulsion à l'aveugle.

**Mise en place (25 min, une fois)**
1. Formulaire de candidature : Paramètres → « Collecter les adresses e-mail » ; message de confirmation
   « Regarde tes e-mails (et tes spams) : la formation et le quiz t'attendent » — **sans lien Discord**.
2. Quiz : ajoute la question « Ton numéro WhatsApp (le même que dans ta candidature) » ; l'identifiant Discord
   devient facultatif (transition) puis disparaît.
3. Crée le formulaire « Rendu du test » (5 questions, voir l'en-tête de `rendu_webhook.gs`), associe une feuille,
   colle le script, propriété `DISCORD_WEBHOOK_URL` (le même webhook), déclencheur `surRendu`.
4. Propriétés des scripts : quiz → `ENVOYER_MAILS=1`, `LIEN_TEST`, `LIEN_RENDU`, `LIEN_VIDEO`, `LIEN_QUIZ` ;
   rendu → `ENVOYER_MAILS=1` ; candidature → `LIEN_VIDEO`, `LIEN_QUIZ` et **`ENVOYER_MAILS=0` si la porte est
   manuelle** (Jonas envoie vidéo + quiz sur WhatsApp aux candidatures retenues, lundi et jeudi), `1` pour
   l'e-mail automatique à tous. Recolle les trois fichiers `.gs` (v2 / v4 / v1).
5. Sur Discord : `!fermer invitations` (drapeau + révocation de toutes les invitations sauf celles du bot) →
   `!purge-candidats` (aperçu) → `!purge-candidats appliquer` → `!archiver #candidature` → `!acces appliquer`.

**Commandes** : `!fermer [invitations]` · `!ouvrir` · `!purge-candidats [jours] [appliquer] [tout]` (protège
rôles d'équipe et rôles particuliers, signés au registre, exemptés `PURGE_INT_EXEMPTS`, parcours en cours sauf
`tout`) · `!inviter` · `!refuser` · `!candidats` (les trois derniers : manager aussi).
**Variables** : `DISCORD_FERME=1` (facultatif, l'emporte sur `!ouvrir`) · `INVITATION_JOURS` (7).
**Transition** : les candidats déjà sur le serveur en cours de test restent gérés en MP par le bot ; les nouveaux
passent par l'e-mail. Publier l'annonce Telegram **après** la bascule des formulaires, sinon les candidats de
l'annonce arrivent sur un serveur qui les raccompagne.

## Ce que le bot fait tout seul depuis le 10/09 (audit complet)

- **Mémoire fiable** : chaque JSON s'écrit de façon atomique avec une copie `.bak` ; la boucle pipeline
  n'écrit plus que ce qu'elle a changé (fusion), elle n'écrase plus un numéro, un e-mail, un STOP ou un
  rendu de test arrivé pendant qu'elle tournait. Écriture garantie même si un tour plante.
- **Quiz** : idempotent par identifiant de message (un redéploiement ne renvoie plus le test aux refusés
  et aux expirés) ; un **quiz raté est prévenu** en MP (score, lien, essai 2/2) grâce au `QUIZ_KO` du
  nouveau `quiz_webhook.gs` (v3 — à recoller) ; un ID Discord vide part avec l'e-mail du quiz pour que
  l'admin retrouve le candidat.
- **MP fermés** : le test est retenté toutes les 5 min et l'horloge des 48 h ne démarre qu'à la réception.
- **En MP, le bot répond toujours** (l'assistant, avec le contexte du parcours). `VALIDÉ` en MP ou dans
  `#candidature` redemande le test après une expiration ou un refus (à la date du retest) ; un numéro
  écrit dans une phrase est reconnu ; renvoyer son numéro ne détruit plus la fiche ; un numéro déjà relié
  à un autre compte est bloqué et remonté.
- **Contrats** : un 2ᵉ e-mail renvoie le lien existant au lieu de créer un 2ᵉ contrat ; un échec DocuSeal
  est dit honnêtement au candidat, retenté 3 fois, puis remonté ; les contrats expirés ne sont plus sondés
  ni comptés ; une signature sur un modèle à deux parties est détectée et expliquée.
- **STOP** est respecté partout (relances de test, J+7/J+14, `!relancer-lien`, `!annonce-int`).
- **Digest du matin** (toujours actif, plus conditionné à la trésorerie) : signés sans créatrice depuis
  48 h (manager mentionné), validés International sans J'ACCEPTE, contrats en erreur, avertissements
  techniques des 24 h. Message de démarrage dans le salon admin : automatisations actives, éteintes,
  variables manquantes.
- **Codes 2FA** : délai IMAP borné, mail marqué lu seulement après relais réussi, rôle Manager par égalité
  exacte, mails Meta sans mot « code/confirmation » ignorés, panne signalée une fois puis « revenu ».
- **Assistant** : escalade vers le manager pour l'opérationnel, jamais de délai ou de montant inventé,
  jamais de contournement, étiquette de source unique en fin de réponse.

## 💶 Paie en deux fois et valeur d'un abonné (14/09)

**La paie tombe le 16 et le 1er**, comme pour les chatteurs (fini le lundi hebdo du premier mois) :
`!primes acompte [AAAA-MM]` liste qui a droit à l'acompte du 16 (la moitié du fixe si ≥ `ACTIF_TAUX_MIN`
des journées évaluées du 1er au 15 sont validées) ; `!primes [AAAA-MM]` reste le décompte du 1er
(solde, commissions, prime). Les montants du fixe restent dans #rémunération : le bot ne les connaît pas.

**`!ltv [jours]`** et le rapport du lundi lisent le classeur « Data G&M Créatrices » (module `creatrices.py`)
et sortent, par créatrice, la valeur d'un abonné OF contre MYM sur 30 jours (OF converti en € au taux
`TAUX_USD_EUR`, défaut 0,92). Réglage, une fois : Fichier → Partager → **Publier sur le web** →
*Document entier* → format **Microsoft Excel (.xlsx)** → Publier → coller le lien dans Railway :
`SHEET_CREATRICES_XLSX_URL`. Les onglets « Synthèse » et « Notice » sont ignorés ; les onglets créatrices
doivent garder leur structure (ligne « Date », colonnes B/C = OF, E/F = MYM).

## 🧭 Trois rapports, pas douze (simplification du 14/09)

« Même moi je comprends rien » : le bot produisait un bilan long par clipper, un récap Telegram, une copie
admin, un digest candidats en admin ET sur Telegram, des salons-compteurs… Depuis le 14/09 :

| Qui | Quand | Où | Quoi |
|---|---|---|---|
| **Le clipper** | chaque matin | son salon privé | **4 lignes** : hier (✅/⚠️/🔴), vues + abonnés, journée validée ou non pour la prime, une alerte seulement si elle existe |
| **Le manager** | chaque matin | son salon (`CANAL_MANAGER_ID`, repli admin) | le rapport MARKETING court (≤ 9 lignes, une priorité) + le point candidats (« Pipeline ») |
| **Gaëtan** | le lundi | salon admin + Telegram | le rapport de la **semaine** en 5 lignes (`!hebdo` à la demande) : Reels et tendance, clippers actifs, journées validées, surfaces face à l'objectif, abonnés OF saisis, podium et zéros, une priorité |

Réglages : `RAPPORT_CLIPPER=long` pour revenir au bilan détaillé · `TELEGRAM_QUOTIDIEN=1` pour recevoir aussi
le quotidien sur Telegram (défaut : hebdo seulement). Le salon admin ne reçoit plus que l'hebdo, les pannes
(3 échecs du cycle) et le message de démarrage. Les salons-compteurs (`CANAL_STAT_*`) : supprimer les salons
et leurs variables, rien d'autre à faire.

**`!archiver #salon #salon…`** (admin) range des salons dans une catégorie « 🗄️ Archives » masquée à tous —
rien n'est supprimé, un glisser-déposer hors de la catégorie les fait revenir. Les salons vitaux du bot
(admin, manager, assistant) sont refusés. Cible du 14/09 : `#tips` (captions épinglées dans `#ressources`),
`#dopamine` (victoires dans `#annonces`) ; `#bump` et les deux compteurs se suppriment.

## 💸 Paie au clic GAML (23/09, `paie_clics.py`)

**Le modèle** : 0,05 $ (`TAUX_CLIC`) par visite réelle sur le lien GetAllMyLinks du clipper, visiteurs **francophones** (`PAYS_PAYES`, par défaut France, Belgique, Suisse, Canada, Luxembourg, Monaco et les DOM-TOM, noms tels que GAML les renvoie ; le Maghreb et l'Afrique francophone, pays des clippers eux-mêmes, restent exclus par défaut), robots exclus par GAML. Payé le **5** (période du 16 à la fin du mois précédent) et le **20** (du 1 au 15).

**Ce que fait le bot** (actif dès que `GAML_API_KEY` est posée dans Railway) :

- **Attribution des liens** : au démarrage puis toutes les heures, chaque lien GAML dont la note est « Clipping Prénom » est rattaché au membre signé du même prénom (et de la même créatrice si possible) ; ambiguïté → ligne dans le salon admin, à trancher avec `!lien`. `CLICS_EXCLURE` (défaut : rianah, gaetan, jonas, x, y) écarte les liens du staff et les liens en attente.
- **Relevés** : deux appels par lien et par jour (pays hors robots, total avec robots), rangés dans `clics.json` sur le volume, rétroactivement depuis `CLICS_DEPUIS` (défaut 2026-09-16), 110 appels au plus par passage pour rester sous la limite GAML (60 par minute), un passage tous les quarts d'heure.
- **Ligne du matin** (`CLICS_HEURE`, défaut 7 h Paris) dans le salon perso de chaque clipper : visiteurs et visites payées de la veille, quinzaine en cours avec le montant, 7 jours. Une fois par jour, seulement quand la veille est relevée pour tous les liens.
- **Commandes clipper** (MP ou salon) : `!mesclics` (hier, 7 jours, quinzaine, montant en cours, part payable, robots exclus, son lien) · `!wallet 0x…` (USDC ERC20) ou `!wallet FR76…` (IBAN) pour son adresse de paiement.
- **Commandes manager** : `!clics` (tableau par clipper) · `!liens` (tous les liens « Clipping », attribués ou libres) · `!lien @clipper <url|slug>` (attribuer) · `!lien @clipper nouveau [Créatrice]` (cloner un lien de sa créatrice via l'API, le renommer « Clipping Prénom », l'activer) · `!lien @clipper retirer` · `!wallet @clipper <adresse>` · **`!paie-clics 5|20 [AAAA-MM]`** : la liste prénom, visites payées, montant, adresse, avec le CSV joint (`;` comme séparateur, décimales à virgule). Le virement reste humain.

**Ce qui manque encore** : le bouton OnlyFans d'un lien cloné pointe sur la destination du modèle ; il passera au lien de tracking Infloww du clipper quand l'export Infloww sera lu par le bot (API Infloww en bêta : Gaëtan exporte les liens de tracking tous les quinze jours, rappel agenda le 5 et le 20).

## 🏠 Le salon perso : tout ce qui concerne un clipper, sous les yeux de Gaëtan (24/09)

Décision de Gaëtan : plus rien d'important ne se passe en privé entre le bot et un clipper validé. Dès son **J'ACCEPTE**, le bot ouvre son salon nominatif (catégorie `CATEGORIE_CLIPPERS_NOM`, « 🎬 Clippers » par défaut, créée au besoin ; privé : lui, le rôle Manager, le bot ; les admins voient tout), puis `!creatrice` le range dans la catégorie de sa créatrice. Y arrivent : ses comptes (identifiants du classeur), **les codes de vérification** de ces adresses (l'onboarding rattache les e-mails des comptes au salon dans le registre des alias, comme `!alias ajouter`), son lien en bio, son Drive, sa ligne de clics chaque matin, son bilan des Reels, et **le 5 et le 20 sa ligne de paie** (visites payées, montant, adresse) pendant que la liste complète et le CSV partent au salon admin. Formation, quiz et test restent en MP : avant validation, rien à voir.

## 🔐 Onboarding automatique : comptes du classeur, lien GAML, Drive (23/09, `onboarding.py`)

Dès `!creatrice @clipper Prénom`, le bot livre dans le salon perso du clipper (ou en MP) : ses **comptes Instagram** pris dans l'onglet Instagram du classeur des logins (`CLASSEUR_LOGINS_ID`, lignes Utilisation = Clipper, Gérant vide ou x/y/z, état à créer / GOOD / WARMUP / PRIVÉ / ACTIF, Créatrice = la sienne ; les comptes déjà créés passent d'abord ; `COMPTES_PAR_CLIPPER`, 3 par défaut) en écrivant son prénom dans la colonne Gérant ; son **lien GAML** (cloné depuis un lien « Clipping » de la créatrice s'il n'en a pas) ; son **Drive personnel** si le script de l'agence est déployé. `!creatrice` pose aussi le rôle de la créatrice s'il existe (même prénom en mot entier) et le rôle Team s'il manque (25/09). Sans e-mail connu, le message du clipper lui demande son adresse Gmail : dès qu'il la poste dans son salon perso ou en MP, le Drive lui est partagé. Le classeur est aussi une télécommande : toutes les 15 minutes, un compte dont la colonne Gérant porte le prénom d'un membre signé, jamais livré à ce membre, part dans son salon perso (état dans `onboarding.json`). `!bilan-fixe [jours]` : le verdict des clippers encore au fixe (visites payables, équivalent au clic, point mort ≈ 32 visites/jour pour 100 €, 65 pour 200 €), posté tout seul dans le salon admin le `BILAN_FIXE_DATE` (2026-10-09, décision du 25/09 : deux semaines puis clic ou sortie). `ROLE_EQUIPE_UNIQUE` (défaut « Rookie ») : le premier rang remplace Team France / Team International pour tout le monde au J'ACCEPTE (plus de distinction de pays) ; un Confirmé ou une Élite est déjà dans l'équipe, rien n'est reposé. `!salons-equipe Sophie: Thia ; Chloé: Romaric, Hasina ; Sarah: Yves` (admin) : ouvre le salon perso des clippers déjà en place dans la catégorie de leur créatrice, y ajoute les managers humains (rôle Manager, ou pseudo contenant « manageur »), livre comptes du classeur, lien, Drive et alias 2FA, et démarre le parcours directement à la routine. Sans liste : tous les signés avec une créatrice au registre. Si la catégorie de la créatrice est **fermée au bot** (catégorie privée où son rôle n'est pas : Voir le salon, Gérer les salons, Gérer les permissions), le salon s'ouvre dans « 🎬 Clippers » et le bilan dit quoi corriger ; à la commande suivante, le salon est déplacé sous la créatrice. `!verifier` liste les catégories fermées. **Pseudos « Prénom - Créatrice » (25/09)** : le bot prend le prénom avant le séparateur partout (contexte de l'assistant, mémoire, classeur) ; le salon perso s'appelle par le prénom seul (`#thia`, ou `#prenom-creatrice` en cas d'homonyme), son identifiant est mémorisé au registre (`salon_id`) et les salons existants sont renommés au démarrage. Le rôle d'équipe unique est « Clippeur » (`ROLE_EQUIPE_UNIQUE`, Rookie encore accepté) et le rôle manager « Manager » ou « Manageur ». Un clipper qui tape `!etape` seul dans son salon revoit son étape en cours. **Classeur des logins suivi par le parcours (25/09)** : compte 1/2/3 validé → sa ligne passe à WARMUP, warm-up fini → les trois lignes passent à GOOD (une cellule ETAT à la fois, jamais la structure) ; une ligne « à créer » sans e-mail n'est plus livrée, `!comptes-libres` compte les livrables (créés + à créer avec e-mail). **États du classeur depuis Instagram (26/09, `etats_comptes.py`)** : chaque jour à `ETATS_HEURE_UTC` (7 h), le bot passe à Apify les comptes de l'onglet Instagram qui ont un Gérant (Utilisation = Clipper) et met à jour la colonne ETAT, une cellule à la fois : à créer → WARMUP dès que le compte existe ; WARMUP → GOOD après `ETATS_GOOD_JOURS` (3) jours de publication de suite ; WARMUP → PRIVE si le compte est passé en privé ; WARMUP/GOOD/PRIVE → BAN après `ETATS_BAN_JOURS` (2) jours introuvable (BAN posé par le bot, rendu à WARMUP s'il réapparaît) ; les états manuels (PERDU LOGS, à vérifier, BIZARRE…) et les lignes sans Gérant ne bougent jamais ; la colonne Followers est remplie pour **tous** les comptes créés du classeur, clippers, créatrices sous Metricool et comptes libérés (≈ 130 profils par jour, appels Apify par lots de 50, écriture seulement si le chiffre a changé). Chaque ligne qui a un Gérant reçoit aussi ses **visites payables des 7 derniers jours** (colonne « Clics GAML last 7d. ») et son **lien GAML** (colonne « Lien GAML associé »). Les colonnes de l'onglet sont reconnues par leur en-tête (26/09 : Gaëtan insère des colonnes), jamais par position. Le code couleur de la colonne ETAT est une mise en forme conditionnelle posée le 26/09 (GOOD vert, WARMUP orange, BAN rouge, PRIVE bleu, à créer gris, PERDU LOGS violet, à vérifier jaune). Bilan dans le salon admin quand quelque chose change, alerte manager sur les BAN. `!etats-comptes [test]` lance un passage à la main. Historique dans `etats_comptes.json`, `ETATS_CLASSEUR=0` pour éteindre. **Textes niveau collège (25/09, demande de Gaëtan)** : tout ce que le bot dit aux clippers (étapes du parcours, message de comptes, codes, visites et paie, bilan du matin, conditions, test, aide) est écrit en phrases de 10 mots, une action par ligne, sans parenthèses ; la base de connaissances porte une règle « Comment je parle » et ses fiches 1 à 6 sont réécrites au même niveau (v8). `CANAL_CANDIDATURE_ID` se répare par le nom (#bienvenue), `CANAL_BUMP_ID` s'éteint sans bruit si le salon a disparu. **Parcours guidé (25/09, `parcours.py`)** : dès `!creatrice`, le salon perso déroule 7 étapes (compte 1, compte 2, compte privé, warm-up de 7 jours compté chaque matin puis ouverture automatique des Reels, premier Reel, lien en bio, routine) avec des boutons-liens vers la fiche du forum et le salon d'infos de la créatrice, et un bouton « ✅ C'est fait » persistant (DynamicItem). Dans ce salon, l'assistant IA reçoit la mémoire du clipper (étape, comptes, lien, Drive, visites 7 j, notes du manager) et joue le manager. Commandes manager : `!etape @clipper [n]`, `!note @clipper texte`, `!memoire @clipper`. État dans `parcours.json`. Commandes manager : `!comptes-libres [Créatrice]`, `!onboarding @clipper [Créatrice]`, `!liberer Prénom [handle …] [pool]` (rend les comptes d'un clipper parti : Gérant vidé, comptes créés en Utilisation « à mettre Metricool », ceux à créer de retour au pool ; `!sortie` le fait tout seul). Garde-fou homonyme (24/09, Eddy) : un membre arrivé depuis moins de 45 jours (`ONBOARDING_JOURS_NOUVEAU`) et jamais onboardé ne reçoit pas de comptes **déjà créés** portant son prénom — l'admin est prévenu (ancien clipper du même prénom ?) et tranche avec `!onboarding @clipper` (forcer) ou `!liberer`. Le trio livré fait 2 comptes de croissance + 1 privé (état PRIVÉ ou handle en priv/secret/perso).

**Google, deux voies** (`google_api.py`, `drive_agence.py`) : le **compte de service** (`GOOGLE_SERVICE_ACCOUNT_JSON`) lit et écrit les classeurs et lit le Drive, mais Google ne lui donne **aucun espace de stockage** (« Service Accounts do not have storage quota ») : il crée des dossiers, pas des fichiers. Tout ce qui copie ou dépose des fichiers passe par le **script Apps Script** `apps_script/drive_agence.gs`, déployé le 24/09 sous le compte Google de l'agence (le bot suit la redirection Apps Script à la main, en GET nu, sinon Google renvoie du HTML) (application web, exécuter en tant que moi, accès tout le monde) : `DRIVE_AGENCE_URL` + `DRIVE_AGENCE_SECRET`. Les sources par créatrice sont dans `DRIVE_SOURCES` (JSON : dossier parent « 🎬 Clippers » dans son dossier Instagram, sources Reels et Photos). **Depuis le 24/09, plus de copies limitées** (Gaëtan : « il faudra donner plus de contenu à chaque clipper ») : le dossier du clipper, créé par le compte de service, contient un **raccourci vers chaque source** (tout le contenu, aucun espace consommé), les sources et le dossier sont partagés en lecture à l'e-mail donné dans le tunnel (compte de service d'abord, script de l'agence en secours), et un sous-dossier « Reels spoofés » attend le spoofer. Le script de l'agence sert aux dépôts de fichiers (Reels spoofés) et aux copies si on en veut un jour.

## 🔁 Le process refondu du 26/09 (soir) : formulaire → quiz 30/34 → test jugé par le bot → 3 comptes, un par jour, 24 h de warm-up

Gaëtan a redit le process de bout en bout pour préparer une formation condensée ; le bot le porte partout (base de connaissances v10, INSTRUCTIONS, textes des étapes, aide, J'ACCEPTE). **Le parcours** : le formulaire du site (3 minutes) connecte le Discord ; vidéo de formation ; quiz `!quiz` à **30/34** ; test de montage rendu **en message privé au bot** (une vidéo brute à retravailler : texte, musique, format, coupes) ; **le bot regarde la vidéo** : `ffprobe` (format, durée), 4 images extraites par `ffmpeg` (`nixpacks.toml` l'installe sur Railway), jugement du modèle sur une grille en 10 points (format vertical, durée, accroche, sous-titres, travail sur la brute), note sur 10 postée au candidat et au salon admin ; **au-dessus de `TEST_AUTO_SEUIL` (7), le test est validé tout seul** (même chemin que `!test-ok`, `TEST_AUTO=0` pour revenir à la review humaine), en dessous le manager tranche avec l'avis sous les yeux. Puis J'ACCEPTE, salon perso, 3 comptes du classeur, et **un compte par jour avec 24 h de warm-up sur chacun** (`WARMUP_JOURS` vaut 1 : l'étape 4 est le dernier warm-up avant les Reels), option 2 comptes qui publient + 1 privé avec le lien, ou 3 qui publient et le lien en story à la une ; le lien ne va jamais dans un Reel ni en rafale dans les stories. Escalade : l'assistant dans #assistant-ia, le salon perso, puis **Gaëtan sur WhatsApp** : un bouton lien « 💬 Écrire à Gaëtan (WhatsApp) » (`WHATSAPP_GAETAN_URL`) est posé sous l'accueil du salon perso et sous chaque étape du parcours.

**Salons persos réservés aux nouveaux (26/09)** : « enlève tous les salons des clippeurs sous gestion de Jonas, ils comprennent rien et ça se mélange avec l'ancien système ». `roster.json` porte `sans_salon` (Thia, Caroline, Rianah, Ckycia, Hasina, Lilian, Romaric, Lucas, Josué, Tara, Yves, Clarisse) : au démarrage, leur salon perso est **supprimé une seule fois** (`DONNEES/roster_salons_supprimes.json`), leur `salon_id` retiré du registre, leur parcours oublié ; `!salons-equipe` sans liste, l'onboarding du roster et `!creatrice` ne leur en recréent jamais (une liste explicite dans `!salons-equipe` force). Leurs visites et bilans repartent là où ils allaient avant (MP ou salon du manager). **Textes du salon perso raccourcis** (« hyper long, trop d'informations ») : accueil en une ligne, message des comptes en 3 blocs et une règle, étapes en 5 lignes, Drive sans aperçu. **`!relance-telegram [jours] [min=4]`** : les meilleurs candidats du Google Form des N derniers jours (score sur 8, majeurs, pas déjà sur Discord ni dans l'équipe) avec liens t.me et wa.me et message prêt à coller, dans un onglet du classeur et au salon admin — un bot Telegram ne pouvant écrire qu'à qui lui a déjà parlé, l'envoi reste humain.

## 👥 Le roster actif : la liste de Gaëtan fait foi (26/09, `roster.py`, `roster.json`)

Gaëtan a donné sa liste de clippers par créatrice (« comme ça tu peux mettre à jour le compteur ») : elle vit dans `roster.json` à côté du bot (édité par Claude ou par Gaëtan) et dans `DONNEES/roster.json` (écrit par `!roster`), le plus récent des deux gagne. Elle sert au salon-compteur **« 🎬 Clippers : N »** (plus de comptage par rôle, remis à zéro à chaque renommage de rôle), aux groupes de **#jonas-stats**, à `!salons-equipe` sans liste, à `!actifs`. Commandes : `!roster` (afficher), `!roster Sophie: Thia, Rianah ; Chloé: Hasina` (remplacer), `!roster sortie Prénom` (un départ), `!roster nouveau Prénom` (un signé sans créatrice, compté). `!creatrice` ajoute au roster, `!sortie` en retire. `alias` dans le fichier : le surnom que Gaëtan emploie (« Pepita ») pour un pseudo Discord différent (« Ricado »), compris par toutes les commandes. **Au démarrage** : les `sortis` du fichier sont nettoyés une seule fois (fiche → `sortis.json`, parcours candidat « sorti », comptes du classeur rendus, salon perso renommé `sorti-prenom`, jamais supprimé) ; un prénom du roster présent sur le serveur mais sans créatrice au registre est **onboardé tout seul** comme par `!salons-equipe` ; une créatrice du registre différente du roster est corrigée (Lucas mis sous « pepita » par un `!creatrice` inversé) ; un membre qui porte le rôle Clippeur sans être au roster est listé « à vérifier », jamais compté.

**Un nouveau = 3 comptes neufs et leurs e-mails, dans le POD le plus bas (26/09, Gaëtan)** : `onboarding.disponibles` prend les 3 lignes « à créer » libres avec e-mail d'une même colonne POD (le POD le plus bas où la créatrice en a 3), plus jamais un compte déjà créé rendu par un ancien (ceux-là partent « à mettre Metricool »). `!creatrice @x Prénom` (ou `!creatrice Prénom @x`, l'ordre inversé est compris) : pseudo Discord **« Prénom - Créatrice »**, rôle Clippeur garanti même sans grille, rôle de la créatrice, roster, salon perso, comptes, parcours à l'étape 1 ; **plus aucun manager n'est ajouté aux nouveaux salons persos** (`SALON_PERSO_MANAGERS=1` pour revenir). **Numéro de téléphone (26/09, décision de Gaëtan)** : un SMS de l'agence coûte trop cher, le clipper met **le sien** quand Instagram le demande et reçoit le SMS ; un numéro = ses 3 comptes, jamais un numéro déjà lié à d'autres comptes (ban en chaîne) ; sa vraie date de naissance ; le manager est informé une fois par jour. **Selfie vidéo** demandé par Instagram : le clipper le fait lui-même. **Escalade** : un problème que la base ne couvre pas (compte bloqué, numéro refusé) renvoie vers Gaëtan sur WhatsApp (`WHATSAPP_GAETAN_URL`) en se présentant, avec le problème en une phrase et une capture ; le bot n'invente plus de « compte prêt à l'emploi ». Le message du matin prend le prénom du salon dans le registre (plus de « Bonjour Maxence ») et ne part jamais hors de la fenêtre 8 h-11 h UTC. Le parcours se recale sur le **nombre de comptes créés** (un compte créé = étape 2, pas le warm-up) avec une correction unique depuis l'étape 4.

**`!pipeline` et `!fiche` (26/09, « 100 % va venir du formulaire »)** : plus de webhooks, de numéros liés ni de portes d'entrée. `!pipeline` lit le classeur des candidatures (Google Form + site, onglets `SHEET_CANDIDATURES_FORM_ONGLET` et `SHEET_CANDIDATURES_ONGLET`, cache 10 min) : total, 7 jours, hier, par source ; puis les parcours des gens **encore sur le serveur** (les partis ne sont plus comptés), les signés présents, le roster actif, et les actions : tests à reviewer, validés sans J'ACCEPTE, signés sans créatrice. `!fiche @x` ajoute la **candidature du classeur** (retrouvée par les 8 derniers chiffres du numéro, sinon par prénom) : pays, âge, métier, téléphones, expérience, montage, Reels et heures par jour, vidéo qui a marché, connaissance des bans, motivation, niche, source de l'annonce, et une **note indicative sur 8** (iPhone, ≥ 2 téléphones, expérience, monte déjà, ≥ 2 Reels/j, ≥ 3 h/j, connaît les bans, majeur) pour juger avant d'attribuer.

## ☀️ Un seul message du matin, et un parcours recalé sur le classeur (26/09, `matin.py`)

Relecture de sept salons persos le 26/09 : trop de messages, des contradictions, des commandes non comprises. Ce qui change. **Un seul message du matin par clipper** : la ligne de visites (`paie_clics`), le bilan des Reels (`inputs_clippers`) et le compteur de warm-up (`parcours`) sont **déposés** dans `matin.py` (`deposer(salon_id, cle, texte)`) et assemblés en un message entre `MATIN_HEURE_MIN` (8 h UTC) et `MATIN_HEURE_MAX` (10 h UTC) ; si le bilan des inputs tarde, le bot attend jusqu'à l'heure limite puis envoie ce qu'il a. **Livraison des comptes idempotente** : un clipper qui a reçu ses comptes depuis moins de 24 h ne les reçoit pas une deuxième fois (sauf `!onboarding` explicite) ; c'est ce qui doublait le message quand `!salons-equipe` et la télécommande du classeur se suivaient. **Parcours recalé sur le classeur** : `!salons-equipe` démarre chaque clipper à l'étape que ses lignes du classeur impliquent (à créer → compte 1, WARMUP → warm-up, GOOD → routine) et chaque passage Apify appelle `parcours.reconcilier` pour avancer un parcours en retard sur la réalité (jamais de recul). **Assistant dans le salon perso** : 3 phrases ou 3 puces maximum, une seule ligne « 👉 Prochaine étape : … » à la fin, plus d'étiquette de source, plus de « [Contexte…] » recopié, plus de quota de questions (le quota reste en MP et dans les salons publics). `code`, `! code`, `Code` seuls valent `!code`. **Mur téléphone** : si Instagram réclame un numéro, le bot dit stop, prend la capture et prévient le manager (une alerte par jour et par clipper, `alertes_tel` dans les compteurs) ; il n'invente plus de bouton « Envoyer un code ». **Candidatures web** : écrites à la première ligne vide sous l'en-tête de l'onglet « Candidatures bot » (les Tables Google Sheets ont 1 000 lignes vides qui cachaient les nouvelles lignes en 1003+), et le manager + l'admin sont prévenus à chaque candidature. **Bilans des inputs** : seuls les salons dont l'Utilisation est Clipper ou Metricool comptent, un salon dont le nom ne commence pas par une lettre ou un chiffre (les salons ℹ️ d'infos des créatrices) n'est jamais un salon de clipper.

## 📊 Rapport GAML du manager : #jonas-stats (24/09, `rapport_stats.py`)

Chaque matin, une fois les relevés de la veille faits, le bot poste dans le salon du manager (nom et groupes dans `rapport_jonas.json`, salon créé par le bot s'il manque : privé, rôle Manager et admins) les visiteurs GAML de la veille des clippers suivis, par créatrice : visiteurs hors robots, dont francophones payables, cumul 7 jours, robots exclus, clippers sans lien signalés. Un lien est rattaché à un clipper quand sa note contient le prénom et que son nom commence par la créatrice (« Rianah Metricool » et « Rianah Metricool 2 » comptent pour Rianah sous Sophie) ; ces liens sont relevés même sans membre Discord. `!stats-jonas [AAAA-MM-JJ]` (26/09 : rapport réduit à un chiffre par clipper, rangé par créatrice, et deux totaux : hier et 7 jours) relance le rapport.

**Roster actif et salon-compteur « 🎬 Clippers : N » (26/09).** `groupes` dans `rapport_jonas.json` est la liste active des clippers par créatrice, donnée par Gaëtan (26/09 : Sophie 5, Chloé 6, Sarah 4 ; Laure, Quentin et Meiji sortis) et datée par `mis_a_jour`. Le roster vivant (`rapport_stats.groupes_actifs`) y ajoute les fiches du registre qui ont reçu une créatrice (`!creatrice`) après cette date et en retire les `!sortie` faites après cette date ; il sert au rapport du matin et au salon-compteur, qui ne compte plus les membres d'un rôle Discord (le renommage Rookie → Clippeur l'avait remis à zéro, et les anciens n'avaient jamais reçu le rôle). `!actifs` affiche les prénoms comptés par créatrice ; pour changer la liste de fond, éditer le fichier et redéployer. Une sortie doit passer par `!sortie` (comptes rendus au classeur, salon perso fermé, rôles retirés) : virer quelqu'un en dehors du bot ne change ni le compteur ni le classeur.

## ✍️ Plus d'étape contrat dans le tunnel (23/09)

Décision de Gaëtan : « on ne va pas embêter les Malgaches avec ça ». `CONTRAT_ACTIVER` vaut `0` par défaut : tout test validé, grille France comme International (et grille indéterminée, France par défaut), reçoit les **conditions en MP** et répond **J'ACCEPTE** ; le rôle Team de sa grille s'ouvre à l'acceptation (`conditions_grille` dans le pipeline), les relances 24/48 h s'appliquent à tous. Un e-mail envoyé en MP est simplement enregistré (Drive), plus aucun contrat DocuSeal ne part. `CONTRAT_ACTIVER=1` rétablit le contrat pour la grille France.

## 🌐 Le site du tunnel candidat (23/09)

**Présentation et rémunération (23/09, après-midi)** : le formulaire reprend l'annonce de Gaëtan (« Recherche Clippeur Reels 🎥 Instagram »), 100 % Instagram (création de comptes puis publication de Reels), et annonce noir sur blanc le nouveau modèle : **0,05 $ par visite réelle sur le lien en bio Instagram** (visiteurs depuis la France, hors robots), payé le 5 et le 20, avec les repères 1 000 visites = 50 $ et 5 000 visites = 250 $. La présentation est une liste de paragraphes dans `questions_candidature.json` (`intro`), `**gras**` et `---` acceptés. La question « Es-tu OK avec ce modèle ? » décrit le même modèle, et les conditions Team International envoyées après le test disent la même chose (plus de fixe ni de 0,50 € par abonné pour les nouveaux). `!primes` reste pour les clippers déjà signés à l'ancien modèle. : formulaire, connexion Discord, quiz

Le bot sert lui-même quatre pages sur Railway (`web_candidature.py`) et remplace Google Forms, les deux
Apps Script et la liaison par téléphone :

| Page | Rôle |
|---|---|
| `/candidature` | Le formulaire, questions dans `questions_candidature.json` (texte, options, obligatoire : éditable sans code). Mineurs refusés, pot de miel anti-robot, 6 envois par heure et par adresse |
| `/discord/connexion` | Le bouton « Rejoindre le Discord » : autorisation Discord officielle (OAuth2, `identify` + `guilds.join`) qui porte l'identifiant de candidature signé. Le bot ajoute lui-même le candidat au serveur, déjà relié à ses réponses, surnom = prénom |
| `/quiz` | Le quiz servi ici (`quiz.json` : `{"titre", "questions": [{"q", "choix": [...], "bonne": index}]}`), lien personnel signé, score envoyé au même traitement que l'Apps Script (test 48 h automatique, essais comptés). Tant que `quiz.json` n'existe pas, le Google Form (`LIEN_QUIZ`) reste utilisé |
| `/health` | État du service |

Variables Railway : `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` (portail développeur Discord → OAuth2, redirection
`https://<domaine>/discord/callback`), `WEB_URL_PUBLIQUE` (le domaine public généré par Railway), `WEB_SECRET`
(facultatif, signe les liens), `QUIZ_SEUIL` (27), `QUIZ_ESSAIS_MAX` (2), `GUILD_ID` (facultatif). `WEB_ACTIVER=0`
coupe tout. Sans ces variables, le bot est inchangé. Un candidat arrivé par le site est reconnu dans
`on_member_join` (`web_attendus`) et reçoit l'étape 2 immédiatement ; s'il était déjà sur le serveur, la liaison
se fait dans la foulée. Le bot doit avoir « Créer une invitation » sur le serveur pour `guilds.join`.

## 🧹 Salon admin épuré (23/09)

Soixante-dix messages en trois jours, dont la moitié ne demandait rien : « c'est le bordel ». Depuis le 23/09, le
salon admin ne reçoit plus que ce qui appelle un geste ou une lecture.

| Avant | Maintenant |
|---|---|
| Ligne brute du webhook (`CANDIDATURE\|…`, `QUIZ_OK\|…`) qui reste dans le salon avec le numéro de téléphone | **Effacée** une fois traitée (`WEBHOOK_EFFACER=0` pour la garder ; il faut « Gérer les messages » au bot) |
| « 1 candidature(s) enregistrée(s) » et « Test envoyé automatiquement en MP » à chaque événement | Comptés dans le digest du matin : « Hier : 4 candidatures (FR 0 · International 4) · 2 tests envoyés · 6 en cours ». Seules les anomalies restent immédiates (pays ≠ indicatif, numéro illisible, MP fermés) |
| « a déjà reçu le test », « a donné son e-mail — fiche mise à jour » | Journal du bot seulement |
| « Cadence ratée 2 jours de suite » : la même liste de 19 noms chaque matin, avec l'équipe et des entrées de test dedans | Chaque clipper n'est signalé **qu'une fois par semaine** ; l'équipe (`INPUTS_EXCLURE`, défaut Gaëtan, Rianah, Jonas) et les noms de moins de 3 lettres ou faits d'une lettre répétée (« Aaa ») sont exclus des listes « zéro » et « cadence » (rapport quotidien et hebdo aussi). « Sans salon perso » : le lundi |
| Digest : « Signés sans créatrice » à J+66, « tests expirés », « candidatures sans Discord », « avertissement technique » répétés tous les jours | En semaine : les signés récents (≤ 14 j) hors équipe ; le lundi : les anciens et les compteurs de fond. Un avertissement technique n'apparaît qu'une fois |
| Relance du soir « N tests attendent ton OUI/NON » le jour même du rendu | Seulement pour les tests qui attendent depuis 24 h ou plus |
| Sauvegarde hebdo : dix fichiers JSON avec aperçu | Une archive zip, une ligne |

Ce qui reste immédiat : un test rendu (avec ses fichiers), un contrat signé, un candidat qui accepte les conditions,
une panne. Pour vider le salon admin du quotidien (rapport MARKETING, digest, alertes cadence), pose
`CANAL_MANAGER_ID` : ils partent chez le manager et l'admin ne garde que l'hebdo du lundi.

## ⚠️ Compteurs remis à zéro ? (persistance des données)

Vécu le 17/07 : « Déjà payés : 0 € » et classement des bumps reparti de zéro. Cause : les données
(`compteur_verse.json`, `bump.json`, `paiements.jsonl`, `faq_apprise.md`…) vivent dans `DONNEES_DIR`
— si la variable saute ou si le volume n'est plus monté, le bot écrit dans le conteneur, **effacé à
chaque déploiement**.

**Checklist Railway (dans l'ordre)** :
1. **Variables** → `DONNEES_DIR=/data` toujours présent ?
2. Le **Volume** est-il toujours attaché au service, monté sur **`/data`** ? (Un incident Railway
   peut le détacher — le réattacher suffit.)
3. **Settings → Watch Paths** → ajouter `tools/bot_clippers/**` : sans ça, **chaque push du repo
   (même le vault Obsidian) redéploie le bot** — restarts inutiles et fenêtres de perte.

**Auto-guérison intégrée** : au démarrage, si le compteur local est vide, le bot **relit le total
depuis son message épinglé dans #dopamine** (Discord sert de sauvegarde durable) — le compteur
public survit donc à toute perte du volume. `!verifier` contrôle désormais la persistance (variable,
écriture, historique). En dernier recours : `!ajuster 608,55 rattrapage` avec le montant du message
épinglé. Les compteurs de bumps, eux, ne sont pas restaurables — ils repartent du bump suivant.

## L'améliorer avec le temps (sans toucher au code)

- **Depuis Discord** : `!apprendre La question ? | La réponse.` ajoute une entrée — le bot l'utilise
  **immédiatement**. `!stats` → volume de questions + % hors kit.
- **Depuis Claude Code** : demande-moi de mettre à jour `connaissances.md` (versionné dans le repo) à
  chaque évolution du kit ou du SOP.
- **Séparation propre** : la base curée (`connaissances.md`) est dans le repo ; les ajouts `!apprendre`
  vont dans `faq_apprise.md` sur le volume persistant. Le bot charge les deux.
- **Il n'écrit jamais lui-même dans sa base sans validation humaine** — c'est voulu (sinon une erreur
  inventée deviendrait une règle pour tes clippers).

## Mesurer (le déclencheur de septembre)

Chaque question va dans `donnees/journal_questions.jsonl` avec un marqueur `escalade` (= pas dans le kit).
À la rentrée : `!stats` sur Discord, ou en ligne de commande :
```bash
grep -c '"escalade": true' <volume>/journal_questions.jsonl   # trous du kit à combler
```
Beaucoup d'escalades = enrichir `connaissances.md`. Peu de questions = le kit v2 suffit.

## Sécurité (gravée dans le code)

- Base = **le kit v2 + la stratégie**, uniquement (rien que les clippers n'aient déjà). Jamais le
  playbook complet, jamais d'identités de créatrices, jamais de chiffres de l'agence.
- Le bot refuse : hors-kit, injections (« ignore tes règles »), tactiques dangereuses pour les comptes.
- `.env` (les clés) et `donnees/` ne sont **jamais commités** (exclus par le .gitignore).
- Le bot ne répond que dans le canal dédié ou quand on le mentionne — il ne spamme pas le serveur.
- Limite : 30 questions/jour/personne (réglable via `QUESTIONS_MAX_PAR_JOUR`).
