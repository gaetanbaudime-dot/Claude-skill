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

## Distribution aux clippers

Rien à distribuer ! Ils sont déjà dans le serveur. Dis-leur juste : « pose tes questions dans ton salon perso » (27/09).
Pour retirer quelqu'un : retire-le du serveur Discord (ou du canal). Aucun code à gérer.

## Coût

Modèle par défaut **`claude-haiku-4-5`** (rapide, quasi gratuit). Coût API ≈ **1-2 €/mois** même à fort
volume. Le total est dominé par l'hébergement (~5 $/mois Railway). Total réaliste : **~5-7 $/mois**.
Pour des réponses plus fines : `MODELE=claude-opus-4-8` (~5x plus cher, reste sous ~10 €/mois).

## Commandes v2 en un coup d'œil

`!aide` (liste adaptée au rôle : admin, manager, clipper, candidat) ·
`!paiement @x 50 [raison]` · `!ajuster -150 [raison]` (corrige/rattrape le compteur) ·
`!compteur` · `!rang @x Rookie|Confirmé|Élite` ·
`!verifier` (audit config) · `!audit` (carte du serveur) · (depuis le 28/09, `#ressources` et `#rémunération` sont **publics** dans la doctrine — `NOMS_PUBLICS` et premier étage de `_doctrine_acces` — plus d'écart signalé, `!acces appliquer` les ouvre ; `#reporting` reste réservé) · `!stats` · `!apprendre Q | R` ·
`!creatrice @x Prénom` · `!sortie @x raison` · `!relance @x` ·
`!alias` / `!code` (relais 2FA, managers). Une commande inconnue est signalée (plus de silence).

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

**Lien GAML = tracking OnlyFans du POD (27/09 soir)** : Gaëtan pose le lien de tracking OnlyFans de chaque POD dans la colonne
« Lien Infloww Tracking » du classeur (première ligne du POD). À l'onboarding, le lien du clipper est cloné depuis le DERNIER lien
de clipper de la créatrice (« tu dupliques celui d'avant ») et sa carte « Plateforme privée » reçoit le tracking de son POD
(`paie_clics.poser_tracking`, PATCH de la carte) ; le bilan le dit (`tracking OF ✅ (c9)`) ou signale un POD sans tracking.
`onboarding.verifier_trackings` (au démarrage, 3 min après, et `!trackings`) compare la carte de chaque lien de clipper au tracking
de son POD, corrige les écarts, et liste les POD sans tracking. Clara est dans `DRIVE_SOURCES` (dossier « 🎬 Clippers » créé
dans son Instagram Drive). Depuis le 27/09 (« on s'en fout de ceux qui sont virés »), la vérification ne parle que des clippers du roster actif, remet aussi la colonne « Lien GAML associé » du classeur d'équerre, et son bilan n'est posté au salon admin que s'il contient une correction ou si ses avertissements ont changé depuis le dernier bilan posté (`onboarding.bilan_a_poster`, signature dans `onboarding.json`) ; `!trackings` répond toujours. Les TOP 20 Reels refaits au démarrage ne s'annoncent plus au début et ne listent à la fin que les clippers qui ont reçu des Reels ou une erreur.

**Un accès par jour, anciens sans salon, classeur des candidatures (27/09, fin de journée)** : la livraison ne poste plus les trois
comptes d'un coup — une ligne (`message_comptes_court`), puis chaque étape 1, 2, 3 du parcours donne l'identifiant, l'e-mail et le
mot de passe du compte du jour (`acces` mémorisés à la livraison, `COMPTES_UN_PAR_JOUR=0` pour revenir) ; les prénoms « sans
salon » du roster (anciens gérés par Jonas sur WhatsApp) ne reçoivent jamais de salon d'arrivée et un salon recréé par erreur est
supprimé à chaque démarrage. Classeur des candidatures : la colonne Source prend la réponse « sur quel réseau as-tu vu l'annonce »
(les « web » sont corrigés), une nouvelle ligne s'écrit à la suite du bloc (`_premiere_ligne_vide`, plus après les 1 000 lignes
vides de la Table, et `compacter_candidatures_sheet` remonte celles qui y étaient), et deux colonnes « Note /8 » et « Points » au
bout des deux onglets sont remplies d'après `score_candidature` au démarrage (`entretien_candidatures_sheet`) et à chaque
candidature (`noter_candidatures_sheet`). `!paiement` d'un parti : le même message dans #dopamine.

**Salon perso dès l'arrivée, plus d'assistant global, rétrospective nocturne (27/09)** : chaque arrivant reçoit son salon
perso dans « 🎬 Clippers » à la seconde où il arrive (`assurer_salon_arrivee`, aussi à la liaison par numéro et au démarrage
pour les candidats en cours depuis moins de 14 jours) ; tout ce que le tunnel envoyait en MP y va (`envoyer_mp` route vers
le salon perso pour un non-staff), et les réponses du candidat y sont lues comme en MP (`en_prive` : numéro, STOP, e-mail,
J'ACCEPTE, test rendu). Gaëtan voit donc formation, quiz, test et règles se dérouler ; à l'attribution, le salon part sous la
créatrice. Le bot ne répond plus dans l'ancien salon assistant ni dans le forum (`ASSISTANT_GLOBAL` retiré le 29/09) et ne
répond aux mentions hors salon perso qu'au staff (`SALON_ARRIVEE=0` pour revenir aux MP). **Rétrospective (`retro.py`)** :
chaque soir entre 20 h et 22 h (Paris), le bot relit les salons persos actifs des 24 h, se note, et apprend : les leçons
(question ou confusion + bonne réponse) vont dans la FAQ apprise (`!faq`, `!faq retirer N`), les consignes de style (2 par
jour au plus, 12 gardées, `consignes_apprises.json`) sont injectées dans son prompt après les règles, et un digest part au
salon admin. Garde-fous : jamais de nom, numéro, e-mail, mot de passe ou identifiant ; la doctrine est rappelée dans le
prompt d'analyse et la base curée prime ; 3 leçons par salon, 20 par jour, doublons écartés. `!retro` lance la même chose.

**Reels uniques v2 et dossier du clipper (27/09, « fais gaffe au mirroring »)** : la recette ne fait plus jamais de miroir (les
TOP 20 ont des sous-titres incrustés, un miroir les écrit à l'envers), le zoom est limité à 4 % et le décalage à ± 30 % pour ne
pas rogner un sous-titre ; chaque variante passe un **contrôle qualité** ffprobe (1080×1920, durée cohérente avec la coupe et la
vitesse, piste audio conservée, recette sans miroir) et une variante défaillante n'est pas déposée. Les variantes faites avec
l'ancienne recette (`versions` dans `reels_uniques.json`) sont **effacées et refaites au démarrage** (`demarrage`, suppression
par le script de l'agence, sinon par le compte de service), et `!reels-uniques Créatrice refaire` force la même chose. Le **Boucle automatique (27/09 soir)** : 4 minutes après le démarrage puis toutes les 6 heures (`REELS_UNIQUES_BOUCLE_SEC`), le bot décline le TOP 20 de chaque créatrice du roster pour tous ses clippers qui ont un dossier Drive, seulement les vidéos qui manquent encore ; un TOP 20 complété est donc repris sans commande, et le salon admin ne voit que les dépôts. Une seule déclinaison tourne à la fois (verrou partagé avec le démarrage et l'onboarding d'un nouveau).
sous-dossier du clipper s'appelle **« TOP 20 Reels »** (un ancien « Reels uniques » est renommé). **Structure du dossier de
chaque clipper** (`onboarding.dossier_drive`, posée pour tout le roster au démarrage une fois, `restructurer_drives`) : des
raccourcis « Photos », « Reels », « Stories » vers les sources de la créatrice (rien de copié, partagés à son Gmail dès qu'il
le donne ; les anciens « Photos — Chloé » sont renommés), et le sous-dossier « TOP 20 Reels » avec ses variantes. OpusClip :
le passage par l'API est **désactivé par défaut** (`REELS_UNIQUES_OPUSCLIP=1` pour l'activer) — le template « Créatrices OFM »
ajoute ses propres sous-titres karaoké, ce qui double ceux des TOP 20, et l'API n'accepte pas un lien Drive (422 « Unsupported
video link », il faudrait téléverser le fichier).

**Salon admin plus court (27/09, « supprime, ça sert à rien, simplifie tout ça »)** : « Bot redémarré » tient en une ligne et ne
liste que ce qui devrait tourner et ne tourne pas (plus de « éteint : bump, DocuSeal », plus de « à poser dans Railway ») ; un test
rendu = un seul message avec la note du bot, ses deux points à corriger et la commande prête (`!test-ok Prénom`), au lieu de
« test rendu » puis « avis du bot » ; `!fiche` tient en quatre lignes (numéro, pays, parcours, créatrice), sans porte d'entrée
ni grille, les réponses du formulaire seulement avec `!fiche Prénom detail`, et marche pour quelqu'un parti du serveur ;
le digest du matin liste les signés sans « appelle-les » ni numéros ; l'alerte BAN ne part plus en double quand le salon
manager est le salon admin (`notifier_manager_seul`) ; les Reels uniques ne postent rien quand le dossier TOP 20 manque
(journal seulement) ; l'attribution automatique et `!creatrice` répondent en une ligne (`attribution.bilan_court`), le nom
de la créatrice est canonisé (« sarah » → Sarah, d'après le roster ou l'ordre d'attribution), et un changement de créatrice
avec des comptes déjà livrés d'une autre est signalé (`!liberer` puis `!onboarding`).

**Reels uniques : un échec ne se répète plus, et les variantes pèsent moins (28/09, Clarisse)** : le Reel 20 de Sarah (105 s, 16,5 Mo en 720p) donnait une variante de 39 Mo en crf 22 ; envoyée en base64 au script Drive, elle dépassait les 340 s (`asyncio.TimeoutError`, sans texte) et le bot le redisait au salon admin à chaque démarrage et à chaque passage de la boucle. Désormais `commande_ffmpeg` plafonne le débit (crf 24, 2 Mbit/s, 28 Mo pour ce Reel) et `_variante_sync` refait un passage léger (crf 27, 1,4 Mbit/s) au-dessus de `REELS_UNIQUES_MAX_MO` (30). Chaque vidéo a son compteur d'échecs dans `reels_uniques.json` (`echecs`, motif en français via `_motif`) : premier échec signalé une fois, deuxième essai silencieux (ligne « ⏸️ » que la boucle ne poste pas), abandon au troisième (`REELS_UNIQUES_MAX_ECHECS`) signalé une fois avec la commande `!reels-uniques Créatrice Prénom refaire` qui remet le compteur à zéro ; un clipper dont le reste est abandonné passe « déjà à jour » et n'est plus refait au démarrage. Au redéploiement, la variante allégée (28 Mo) a encore raté depuis Railway, cette fois avec une page HTML 404 renvoyée par la redirection d'Apps Script, alors que le même fichier est passé en 60 s depuis une autre machine : `drive_agence.appeler` refait une tentative après 5 s sur un 404/5xx et nomme le délai dépassé.

**Hors clipping (28/09, Gaëtan : « Julien et Rianah, on va les exclure totalement du clipping »)** : les prénoms de `DASHBOARD_EXCLUS` (défaut « Julien, Rianah ») n'apparaissent pas dans le Dashboard ni dans ses totaux (remplacé le 30/09 : voir « Julien et Rianah remis au Dashboard ») ; `!dashboard exclure Prénom` et `!dashboard inclure Prénom` tiennent la liste dans `etats_comptes.json` (`dashboard_exclus`, prioritaire sur la variable) et réécrivent l'onglet ; `!dashboard` seul réécrit et rappelle la liste. Rianah reviendra par `!dashboard inclure Rianah` quand elle testera sur Sophie. Le roster n'est pas touché.

**Dashboard mis en forme (28/09, « des couleurs, des groupes, des cards »)** : à chaque écriture, `etats_comptes.requetes_mise_en_forme` recalcule la mise en forme sur les lignes réellement écrites et l'envoie par `google_api.sheets_batch_update` : titre en bandeau sombre, un bloc par créatrice avec son bandeau de couleur (`PALETTE_DASHBOARD`), en-têtes gris, lignes en zébrure, « Créés » en vert quand tout est créé, « À créer » en orange, « BAN » en rouge, « Visites 7 j » en dégradé vert (racine carrée du ratio au maximum), cadre coloré autour de chaque bloc, quadrillage masqué, titre et colonne des prénoms figés, largeurs fixes, aucune fusion (une colonne figée ne se fusionne pas). Une mise en forme qui échoue n'arrête jamais le scan (avertissement dans le journal).

**Appel d'un compte banni : le clipper le fait lui-même (30/09, décision de Gaëtan)** : « Contester la décision » tout de suite ; le code avec `!code` (salon code-instagram ou salon perso) ; selfie vidéo, numéro de téléphone ou pièce d'identité demandés par Instagram : les siens ; jamais les papiers d'un autre, jamais de faux, jamais sa pièce d'identité dans Discord ; capture de la réponse dans son salon. Gaëtan n'intervient qu'après un appel refusé. Mis à jour partout : règles 20, 21, 23 de l'assistant, Fiche 6 et FAQ de `connaissances.md`, contexte du salon perso, état des comptes (ligne BAN), doctrine de la rétrospective, `!aide`. L'alerte « compte désactivé » au salon admin reste.

**Blocs par Gérant complet, Clics mis en forme, Metricool dans le Dashboard (30/09, Gaëtan : « considère Rianah (Metricool) et Julien (Metricool) comme des clippeurs, ajoute-les au dashboard ; regroupe ces clics last 7d par clippeur, même mise en forme que les gérants avec leurs liens ; détecte automatiquement les gérants et mets-les en groupes avec ton code couleur »)** : `classeur_forme.blocs` prend le Gérant en entier (« Rianah (Metricool) » n'est plus fondu dans « Rianah ») et toute Utilisation (Metricool, Geelark) ; la colonne Clics entre dans le bloc (teinte, cadre, total en gras centré sur la ligne du milieu, anciennes valeurs répétées rendues invisibles). Dashboard : une ligne par Gérant complet, l'exclusion « hors clipping » ne vise plus que le Gérant écrit exactement « Julien » ou « Rianah », les comptes Metricool comptent dans les followers. `DASHBOARD_VERSION` 7 : Dashboard et mise en forme des onglets réécrits au démarrage.

**Julien et Rianah remis au Dashboard (30/09, Gaëtan : « inclus Julien et Rianah dans le dashboard aussi »)** : le Dashboard ne masque plus personne par défaut. Il a sa propre liste, `dashboard_masques` dans `etats_comptes.json` (variable `DASHBOARD_MASQUES`, vide par défaut), tenue par `!dashboard exclure Prénom` / `!dashboard inclure Prénom`. L'ancienne liste « hors clipping » (`DASHBOARD_EXCLUS`, « Julien, Rianah ») ne sert plus qu'à la vérification du classeur et au rapport du jour : Rianah gère des comptes de tout le monde, le plafond de trois comptes la signalerait chaque matin. `DASHBOARD_VERSION` 8 : Dashboard réécrit au démarrage.

**Un compte restreint n'est pas BAN (30/09, Gaëtan : « pourquoi ce compte est marqué BAN alors que Caroline publie dessus et que c'est lui qui ramène beaucoup de trafic ? »)** : erreur de la règle du 28/09, qui comptait un profil « restreint » comme absent. Restreint = Instagram cache le profil aux visiteurs non connectés (contenu jugé sensible) : le compte vit, publie et ramène des clics, seuls ses followers et ses Reels sont illisibles pour le scan. Désormais un jour restreint est sauté : ni absence (jamais BAN), ni jour sans Reel (ni relance, ni sortie automatique, ni « 0 Reel » dans le message du matin), ni fin de série GOOD ; la colonne Reels Hier reste vide au lieu de 0. Un BAN posé par le bot revient à l'état d'avant le BAN (retenu dans `avant_ban`), sinon GOOD si le compte a déjà publié, sinon WARMUP ; un BAN posé à la main n'est jamais touché. Le bilan du scan liste les comptes restreints (🔒). `VERSION` 5 : un passage complet au déploiement, qui rend leur état aux comptes concernés.

**`!dashboard` vérifie tous les comptes d'abord (30/09, Gaëtan : « pareil pour ces comptes-là ; tous les comptes GOOD, BAN et WARMUP, fais des vérifications à chaque fois que je fais !dashboard »)** : `!dashboard` lance le passage complet de `!etats-comptes` (Instagram pour tous les comptes créés ou réservés, états, followers, Reels hier, regroupement, clics, bilan dans le salon), puis réécrit l'onglet. `!dashboard rapide` réécrit l'onglet seul, sans scan payant. Un verrou empêche deux passages en même temps (boucle du matin et commande). Tout BAN, **posé à la main compris**, revient à son état d'avant (sinon GOOD s'il a déjà publié, sinon WARMUP) dès que le scan voit le compte vivant, restreint compris : un compte vivant qu'on veut garder hors jeu prend un autre état (PERDU LOGS…) ou perd son Gérant. Les comptes absents de la réponse d'Apify sont redemandés une fois à part avant d'être déclarés introuvables.

**Après le premier `!dashboard` vérifiant (30/09)** : les trois comptes restreints passés BAN à tort sont revenus, mais en WARMUP (état d'avant inconnu, Reels illisibles). Désormais un BAN rétabli dont l'état d'avant est inconnu revient **GOOD** s'il est restreint ou a déjà publié (un restreint en WARMUP n'en sortirait jamais seul, le scan ne voit pas ses Reels). « Logs perdus » ne compte plus dans le plafond de trois comptes vivants de la vérification du classeur (Caroline signalée à 4). Une ligne rendue au vivier (réservation expirée, `!liberer`) perd son ancien chiffre de Clics last 7d. (des « 0 » restaient sur des lignes sans Gérant).

**Rien d'un compte BAN n'est réutilisé (30/09, Gaëtan : « ON NE RÉUTILISE JAMAIS LES INFOS D'UN COMPTE BAN, on change mdp, username, mail, téléphone »)** : `onboarding.infos_brulees` rassemble l'identifiant, le mot de passe, l'e-mail et le téléphone (9 derniers chiffres) de toutes les lignes BAN, tous onglets confondus ; `disponibles` ne livre jamais une ligne qui en partage un. La vérification du classeur ajoute la ligne « 🔥 Infos d'un compte BAN réutilisées » : chaque compte en service concerné (avec l'info en cause, jamais sa valeur), puis le nombre de lignes libres bloquées par onglet.

**Sortie de Jonas, remplacement de Clarisse (30/09)** : Jonas ne clippe plus (manageur) → entrée de `sorties_a_appliquer.json` avec `garder_salons` (nouveau : la sortie ne supprime aucun salon). Clarisse (3 comptes BAN) → `remplacements_a_appliquer.json` lu par `remplacements.py` au démarrage : ses lignes BAN rendues, trois comptes neufs livrés par `onboarding.livrer` (règle ci-dessus), parcours remis à l'étape du prochain compte à créer (dates effacées, notes gardées), bilan au salon admin ; trace par id sur le volume.

**Onglet « Build capacity » (30/09, Gaëtan : « mes coefficients d'attribution et les clippers que je peux onboarder avec, pour savoir précisément combien de mails créer pour quelles créatrices »)** : `capacite.py`, réécrit avec chaque Dashboard (donc à chaque `!dashboard` et après chaque scan), à chaque `!attribution` et sur `!capacite`. En tête : les coefficients, l'**objectif** en B2 (case jaune, tapée par Gaëtan, relue et gardée à chaque réécriture, 20 par défaut, `CAPACITE_OBJECTIF`) et le nombre de clippers onboardables en suivant la séquence d'attribution avant la première créatrice à sec. Par créatrice : coefficient, part des nouveaux, comptes prêts (exactement ceux que `onboarding.disponibles` livrerait, donc jamais une info d'un BAN), clippers onboardables (÷ 3), lignes « à créer » sans e-mail, lignes bloquées (infos d'un BAN), puis pour l'objectif : les nouveaux qui iront chez elle (séquence suivie depuis sa position actuelle), comptes nécessaires, comptes qui manquent, dont e-mails à ajouter sur des lignes existantes et comptes entiers à créer. Onglet exclu de la lecture des comptes (`ONGLETS_EXCLUS`).

**Annonces aux clippers acceptés seulement (30/09, Gaëtan : « oui, seulement aux clippers acceptés »)** : la règle des 48 h du 29/09 était partie dans TOUS les salons perso, candidats compris (Joaoo, sans aucun compte). `salons_clippers_acceptes()` = les salons des clippers signés avec une créatrice au registre : c'est la cible de `annoncer_regle_48h` et de l'option `"tous_clippers": true` des messages déposés (forme de toute annonce de règle). `salons_persos_actifs()` (candidats compris) ne sert plus qu'à la lecture de la rétrospective.

**Un nouveau commence toujours au compte 1 (30/09, Gaëtan : « pourquoi Steeve, on lui donne directement 2 comptes ? Tu fais n'importe quoi »)** : à l'acceptation, l'onboarding lançait le parcours « selon le classeur » (`demarrer_selon_classeur`, fait pour les anciens clippers arrivés avec leurs comptes) ; le compte 1 de Steeve était un compte déjà créé, rendu par un sortant, donc compté comme fait : départ à l'étape 2, sans compte 1 ni période d'essai. Désormais un clipper au test validé (état `valide`) sans parcours démarre à l'étape 1 (`demarrer_parcours`, le compte déjà créé passe en « connecte-toi »). Au démarrage, `parcours.mal_partis` retrouve les nouveaux partis à l'étape 2 ou 3 sans étape 1 : `reprendre_au_compte_1` efface leur calendrier (notes gardées), écrit « Petite erreur de ma part : on reprend dans l'ordre » et renvoie l'étape 1 ; bilan au salon admin, une fois par clipper (`parcours_repares.json`).

**Relance quotidienne des nouveaux jusqu'au test de montage (30/09, Gaëtan : « une relance simple tous les jours pour les nouveaux, afin qu'ils fassent le test de montage vidéo »)** : `relance_nouveaux.py`. Chaque jour à 11 h (Paris), dans son salon, une ligne selon l'étape : quiz pas réussi → « ton test de montage arrive juste après le quiz », avec son lien ; test envoyé pas rendu → le lien du dossier et les heures qui restent. Jamais dans les 20 h qui suivent l'arrivée ou l'envoi du test, jamais deux fois le même jour, jamais après un STOP, jamais pour un signé, le staff, un test rendu, validé, refusé ou expiré. Remplace les relances 24/48 h du quiz et la relance « moins de 24 h » du test (`RELANCE_NOUVEAUX=0` les rétablit). La sortie à 7 jours sans quiz reste.

**Identifiants neufs versés dans les onglets, tableaux étendus (30/09, Gaëtan : « ajoute tous les nouveaux @ et mdp dans chacune des bonnes feuilles en fonction de la créatrice et étends les tableaux pour que ça rentre ; la feuille Chloé déborde du tableau »)** : `capacite.ajouter_aux_onglets` écrit la réserve de chaque créatrice sous la dernière ligne remplie de son onglet — ÉTAT « à créer », @ IG, MDP, Utilisation Clipper, Créatrice, Numéro Mail suivant, POD de trois (le dernier POD entamé complété d'abord), sans e-mail (les iCloud restent à créer : la colonne « À créer sans e-mail » les compte) — puis étend le tableau Google de l'onglet (`updateTable`, lignes ajoutées à la grille si besoin) jusqu'à la dernière ligne remplie, lignes qui débordaient déjà comprises. Fait une fois tout seul au démarrage (trace `identifiants_ajouts.json`), ensuite `!capacite ajouter`. Un tableau que l'API refuse d'étendre est signalé, les valeurs s'écrivent quand même ; la réserve se reconstitue au passage suivant du Build capacity.

**Rôle de la créatrice posé à coup sûr (30/09, Gaëtan : « tu n'ajoutes pas le rôle de la créatrice aux clippeurs qu'on accepte ; en fonction du coefficient et de la créatrice attribuée, donne-lui le rôle »)** : `role_creatrice` ne reconnaissait que le nom exact du rôle et l'échec était silencieux (Mathias : Chloé attribuée, pseudo posé, rôle absent). Il reconnaît maintenant le nom sans emoji ni signe (« Chloé 💖 »), puis le prénom en mot entier hors rôles d'équipe (« Team Chloé », jamais « Manager Chloé »), puis les 4 premières lettres (Maddy ↔ Maddie). L'onboarding (attribution automatique comme `!creatrice`) écrit dans son bilan « rôle Chloé », « ⚠️ aucun rôle « Chloé » sur le serveur » ou « ⚠️ rôle refusé : monte le rôle du bot au-dessus ». Au démarrage, `roles_creatrices_manquants` rattrape tous les signés du registre qui n'ont pas le rôle de leur créatrice et poste le bilan au salon admin.

**Build capacity : l'urgence d'abord, 20 identifiants neufs par créatrice (30/09, Gaëtan : « la créatrice en manque de mail iCloud en premier, avec ces coefficients » ; « prépare-moi 20 username et mdp nouveaux pour chaque créatrice, garde le branding d'après les @ existants, originaux, de préférence disponibles, un chiffre ou xo, x, ., _ en fin ou en liaison, toutes les créatrices d'un coup »)** : colonne « À sec après » (nouveaux clippers, toutes créatrices confondues, avant qu'elle n'ait plus de comptes prêts, en suivant la séquence d'attribution), tableau trié par là, ligne 3 « 👉 E-mails iCloud à créer d'abord pour : … ». Sous le tableau, `identifiants.py` : les pseudos de chaque onglet découpés en prénom / mots de style / mots de marque (programmation dynamique), des candidats recomposés avec liaison et touche finale, jamais un pseudo du classeur ni son double à la ponctuation près, passés au scan Instagram (Apify) — seuls ceux que le scan ne trouve pas sont gardés, « (?) » si le scan n'a pas pu tourner — et un mot de passe neuf (`secrets`) chacun. Réserve de 20 par créatrice sur le volume (`identifiants.json`), un identifiant copié dans un onglet est remplacé au passage suivant ; `!capacite neufs` refait toute la série. **Rien de tout ça n'est dans le dépôt** : calculé dans le bot, écrit seulement dans le classeur.

**Une information à la fois, au bon moment (30/09, Gaëtan : « arrête de spammer les clippeurs d'informations ; un compte par un compte, on distille l'information et on ne la donne que quand il en a réellement besoin »)** : chaque compte se fait en trois temps, un message chacun. 1) L'étape : identifiant, e-mail, mot de passe, trois lignes de création, bouton « ✅ Compte n créé » (plus de Drive, de warm-up ni de « compte suivant dans 48 h » dedans). 2) Au bouton : le profil en UN message (photo en pièce jointe ou lien du dossier Photos, nom, bio), bouton « ✅ Profil fait » (`profil.envoyer(..., vue=)` ; un compte rendu par un sortant garde son profil et saute ce temps). 3) Au bouton : une ligne de warm-up et la date du compte suivant. **La règle des 48 h est tenue par le bot** (avant, le compte 2 tombait dès le bouton du compte 1) : `programme` de la fiche parcours, lu chaque heure par `parcours.programme_du_jour` — 24 h après un compte, « ton compte n peut publier » avec le Drive et la règle de modification ; 48 h après, l'étape du compte suivant. Pendant l'attente, la ligne du matin donne la date, les relances et les bloqués du matin ne comptent pas. Période d'essai : le message d'essai ne dit plus que le warm-up ; « 5 Reels en 72 h » arrive avec « il peut publier ». Étape 5 : plus de « il est prêt, rien à monter ». `PARCOURS_ATTENTE_COMPTE_H` (48), `PARCOURS_WARMUP_H` (24).

**Montage toujours (30/09)** : la fiche 3 de `connaissances.md` disait que les TOP 20 pouvaient être publiés tels quels la première semaine ; le bot l'a répété à Daniella contre la consigne de Gaëtan. Corrigé, plus la règle 30 de l'assistant : toute vidéo du Drive (« Reels » ou « TOP 20 Reels ») est modifiée avant publication, hook le plus accrocheur possible.

**Comptes d'avance en bas de feuille (30/09, Gaëtan : « mets toujours les comptes sans gérant à créer en bas, pour voir combien j'ai de comptes d'avance en capacité d'onboarding »)** : le regroupement range en dernier les lignes « à créer » sans Gérant (dans leur ordre, les POD restent groupés), et le bilan de `!etats-comptes` affiche « 📦 Comptes d'avance : total · par créatrice ». Stéphane (viré le 30/09) est dans `sorties_a_appliquer.json` : comptes rendus au vivier, lien libéré, salon supprimé au démarrage.

**Comptes regroupés par clipper (30/09, Gaëtan : « regroupe les comptes des clippeurs, regroupe les clics last 7d »)** : à chaque scan (`!etats-comptes` ou le passage du matin), avant les Clics, `onboarding.regrouper_comptes` range chaque onglet : une ligne sans Gérant dont le « Lien GAML associé » est celui d'un seul Gérant reçoit son nom (lignes de Ricado, de Stéphane restées sans nom), puis toutes les lignes d'un même Gérant sont déplacées ensemble à la place de sa première ligne (lignes entières : état, liens, followers suivent) ; les autres lignes gardent leur ordre. Onglet aux lignes non continues (doublon écarté) : rien n'est déplacé. Les Clics sont ensuite écrits une fois au milieu de chaque bloc.

**Subs de la veille, v2 (30/09, Gaëtan : ordre Chloé, Sarah, Sophie, Maddie, Jade, Clara ; « annonce OF ou MYM en fonction de si on manage l'un ou l'autre ou les deux » ; le message des clics du bot chatting « on annule complètement »)** : une plateforme est affichée pour une créatrice si elle a eu au moins un sub ou du CA dessus dans Data G&M sur les 30 derniers jours (`ACQUISITION_SUBS_PLATEFORMES` en ajoute toujours ; défaut « Jade=OF », Gaëtan : « Jade on a OF, attention ») ; une créatrice sans aucune donnée n'est pas affichée (l'aperçu la nomme). Le bot chatting redevient ce qu'il était : plus de module acquisition, plus de `!acquisition` ni de `!cle-gaml`, et l'ancienne clé GAML est effacée de son volume au démarrage.

**Subs de la veille au salon acquisition du serveur chatting (30/09, Gaëtan : « on va plutôt afficher les subs de la veille, plus cohérent pour les clippeurs ; Chloé OF / Chloé MYM, Sarah OF / MYM, Sophie OF / MYM »)** : `acquisition_subs.py` lit la veille dans Data G&M (`rapport_quotidien.data_gm`) et poste « Hier (29 septembre) » puis, par créatrice (`ACQUISITION_SUBS_CREATRICES`, défaut Chloé, Sarah, Sophie), « Chloé OF n » / « Chloé MYM n ». Le serveur chatting est un autre serveur : envoi par le webhook du salon acquisition, donné une fois avec `!acquisition-webhook <url>` (gardé sur le volume, message effacé). Envoi dès que la veille est saisie pour toutes (entre 10 h et 18 h, Paris ; à 18 h même incomplet, « pas encore saisi »). `!acquisition-subs` : aperçu ; `!acquisition-subs envoyer` : envoi immédiat. Le message automatique des clics GAML du bot chatting est éteint (`ACQUISITION_AUTO=1` pour le rallumer), `!acquisition` y reste à la demande.

**Clics last 7d., correctif (30/09, Gaëtan : « ça marche pas le regroupement des clics par clipper »)** : les onglets sont des tableaux Google, où les cellules fusionnées sont impossibles (le Gérant est tapé sur chaque ligne, les blocs ne sont que des bordures) — la fusion ne se faisait jamais et le chiffre restait répété. Désormais le total est écrit UNE fois, sur la ligne du milieu de chaque bloc (lignes qui se suivent avec le même Gérant), les autres lignes vidées, comme la colonne des liens. Les liens comptés = ceux de la colonne « Lien GAML associé » PLUS ceux dont la note GAML porte le nom du Gérant (Lilian a deux liens « Clipping Lilian », /4 et /5 ; le classeur ne portait que /5 alors que le trafic était sur /4) ; Metricool et Clipping ne se mélangent pas. Sans lien trouvé : case vide (l'ancien calcul par prénom additionnait les liens de toutes les créatrices).

**Clics last 7d. associés à chaque clipper (30/09, Gaëtan : « associe automatiquement les clics last 7d avec le clippeur, comme les liens de tracking à droite »)** : `onboarding.clics_classeur` (appelé par le scan du matin) calcule un chiffre par bloc de clipper (même Gérant dans un onglet) = les visites payables des 7 derniers jours de SES liens GAML : le lien de sa colonne « Lien GAML associé », sinon les liens de la créatrice dont la note GAML contient tous les mots du Gérant (« Rianah (Metricool) » → notes « Rianah Metricool » et « Rianah Metricool 2 »), sinon l'ancien calcul par prénom. Avant, « Rianah (Metricool) », « Rianah (Clipping) » ou « Gaëtan » (exclu de la paie) restaient à 0 malgré leur lien, et Julien cumulait ses liens de toutes les créatrices. Un Gérant fusionné sur plusieurs lignes → le chiffre va dans la première cellule et la colonne Clics est fusionnée pareil. `lire_comptes` lit désormais les cellules fusionnées (`google_api.sheets_fusions`, `_remplir_fusions`) : chaque ligne d'un bloc reçoit le Gérant, les Clics et les liens de la première cellule. Détails des liens GAML (URL, note, groupe) relus une fois par jour ; un appel GAML par lien pour les 7 jours (`paie_clics.payes_periode`).

**Drives des salons ℹ️ ouverts par le lien (30/09, Gaëtan : « ces liens dans les salons informations des créatrices demandent des autorisations à chaque fois dans mes mails »)** : les dossiers postés dans les salons ℹ️-créatrice étaient en accès « Limité » (partagés e-mail par e-mail) ; chaque clic d'un clipper sans accès envoyait une demande à Gaëtan. `ouvrir_drives_salons_info` lit ces salons au démarrage puis toutes les 6 h, repère chaque lien de dossier Drive et l'ouvre en lecture par le lien (le bot en est éditeur) ; un refus (bot pas éditeur) est signalé au salon admin avec le geste à faire à la main. État dans `drives_info.json`.

**Période d'essai sur un seul compte (30/09, Gaëtan : GO)** : pour tout parcours dont l'étape 1 commence à partir d'`ESSAI_DEPUIS` (30/09), le compte 1 validé n'ouvre pas l'étape 2 : le salon reçoit « Période d'essai : ton compte 1 seulement… publie 5 Reels en 72 h » (`ESSAI_REELS`). Le scan du matin additionne les Reels du compte 1 sur ses trois derniers passages ; à 5, « Essai réussi » et l'étape 2 arrive (`parcours.reconcilier`, argument `reels_72h`). Pendant l'essai : la prochaine étape, l'état des comptes de l'assistant (« compte 2 : fermé, période d'essai »), la base de connaissances et la rétrospective disent la même chose ; la liste des bloqués juge le clipper sur ses Reels, pas sur le compte 2. Celui qui ne publie pas est averti à 3 jours et sorti à 7 : il n'aura coûté qu'un compte. Les parcours déjà en cours ne changent pas. `ESSAI_UN_COMPTE=0` éteint.

**Un seul message de suivi, les bloqués du matin, WhatsApp en un appui (30/09, Gaëtan : GO n° 2, 3 et 4)** : (4) le message du matin, les relances d'étape et le jour de warm-up passent par `matin.remplacer` — le message de suivi précédent du salon est effacé et le nouveau arrive en bas ; une étape validée efface aussi l'ancien suivi (`matin.effacer`). Les messages d'étape (identifiants, boutons) restent. (3) `bloques.py` : chaque matin à `BLOQUES_HEURE` (11 h Paris, après le scan), le salon admin reçoit les clippers du roster bloqués — compte 1 à créer depuis plus de 2 jours, compte 2 ou 3 depuis plus de 4 jours, ou aucun Reel depuis `BLOQUES_JOURS_SANS_REEL` (3) jours (`sortie_auto.jours_sans_reel`) — le plus bloqué d'abord, 25 au plus ; `!bloques` la sort tout de suite. (2) Chaque ligne porte un lien WhatsApp (`wa.me/<numéro>?text=…`) qui ouvre la conversation avec le message déjà écrit : rien ne part sans l'appui de Gaëtan (un envoi automatique fait bannir un numéro). Les relances des candidats (`relances.py`) ont le même lien WhatsApp à côté de Telegram, et un candidat sans Telegram lisible mais avec un numéro y figure désormais.

**Classeur des logins : colonne « Reels Hier » et Clics à droite du Gérant (30/09, Gaëtan : « combien de Reels a posté chaque compte IG hier ; déplace Clics last 7d à droite de son gérant, on a un lien par clipper »)** : au démarrage, une fois (`STRUCTURE_LOGINS`, état `structure_logins`), `onboarding.structurer_onglets` range chaque onglet de logins : une colonne « Reels Hier » insérée juste après Followers si elle manque, « Clics last 7d. » déplacée juste à droite de Gérant si elle n'y est pas (un onglet déjà rangé, comme Sarah, n'est pas touché). Le scan du matin y écrit, compte par compte, les Reels des 24 h avant le scan (vide si le compte n'existe pas sur Instagram), en un seul appel et seulement les cellules qui changent. Les colonnes se trouvent par leur en-tête : le reste du bot suit sans réglage.

**Dashboard : « Reels hier » à 0 partout (30/09, Gaëtan)** : la colonne ne lisait que le scan daté du jour de l'écriture ; le Dashboard réécrit le matin avant le scan du jour (redémarrage du bot, `!dashboard`) mettait 0 à tout le monde alors que « Dernier Reel » disait 29/09. Elle lit maintenant le scan le plus récent, celui du jour sinon celui de la veille (les 24 h qu'il couvre) ; plus de scan depuis deux jours = 0.

**Salon admin allégé et rétrospective remise à jour (30/09, extrait de #bot-gaetan)** : une arrivée dans l'agence = une ligne (« a rejoint l'agence (règles acceptées au formulaire) · WhatsApp … »), la créatrice et les comptes suivent dans le message d'attribution ; `!test-ok` répond « ✅ Prénom validé. » ; l'arrivée par invitation du staff ne parle plus de J'ACCEPTE ni de fr|int. **Double salon** (#ez_exe puis #noël pour le même arrivant qui a changé de pseudo) : `trouver_salon_perso` retrouve désormais le salon où le membre est le seul à avoir un droit direct. **Rétrospective** : sa doctrine datait du 25/09 (« un compte par jour », « lien en bio du compte privé ») et lui a fait apprendre « à l'essai 3 raté, c'est terminé » et « aucun humain sur les tests » ; doctrine réécrite sur les règles du 30/09, et toute leçon qui en contredit une est déclarée fausse. Les leçons fausses déjà apprises se retirent avec `!faq` puis `!faq retirer N`.

**Parcours simplifié, langage collège (30/09, Gaëtan sur le salon de Mathias : « simplifie encore »)** : accueil en trois étapes numérotées sans double mention ni ligne « Ton parcours » ; test en trois gestes et **une seule vidéo** (le bot note la première et valide dès 7/10 ; rappels et retest disent « ta vidéo ») ; avis du bot = « Ta note : 6/10 », un 👍 et deux ✏️, sans résolution ni mot technique (consigne au modèle : 8 mots par point, jamais netteté, fondu, transition…), et la suite (« Il faut 7/10… Essai 1 sur 3 », « Test validé », « Un manager regarde ») s'ajoute sous l'avis au lieu d'un deuxième message ; « tu as rejoint l'agence » tient en une phrase, la ligne « tes accès arrivent… » disparaît, l'étape 1 perd « chaque bloc se copie d'un geste » et met le Drive après le warm-up ; la photo de profil ne prend que des images sous la limite Discord et, faute de photo, donne le lien direct du dossier Photos (le Drive de l'étape 1 ouvre le TOP 20).

**Leçons du salon de Daniella (30/09, Gaëtan : « apprends au bot »)** : en une soirée l'assistant a dit « publie demain », « ton compte 1 finit son warm-up demain aussi » et « pas de story ni de publication », alors que le message d'étape disait « comptes 1 et 2 : 2 Reels par jour ». Cause : ses consignes se contredisaient (« le premier Reel arrive après le warm-up du compte 3 » contre « chaque compte publie après ses 24 h »), et le message du warm-up disait « sur chaque compte… pas de Reel ». Corrigé : (1) `parcours.etat_des_comptes` calcule l'état de CHAQUE compte (pas créé · WARM-UP jusqu'au JJ/MM à H h · PUBLIE · BAN d'après le dernier scan du classeur, mis en cache par `reconcilier`) et la mémoire le donne à l'assistant comme « fait foi » ; (2) consignes réécrites : chaque compte publie à la fin de SES 24 h, un BAN ne change rien pour les autres, jamais de compte neuf promis « demain » ; (3) la story du jour se prend dans le dossier Photos du Drive, jamais un dossier inventé (« Stories », « À publier »), et « où je prends la story ? » reçoit le où, pas le widget ; (4) textes de l'étape 4, du warm-up du jour et de `PROCHAINES[4]` limités au compte 3 ; « compte privé » → « compte 3 » ; (5) `alerter_admin_salon` : un compte désactivé ou un accès refusé écrit dans un salon perso part au salon admin, une fois par clipper, sujet et jour ; (6) « Okey c'est clair merci » = accusé de réception, 👍 sans réponse.

**Leçons du parcours de Ricardo (30/09, Gaëtan : « apprends »)** : (1) **Photos inaccessibles** — le dossier du clipper se lit par le lien depuis le 28/09, mais Photos et Reels y sont des raccourcis vers les sources de la créatrice, partagées seulement à l'e-mail du clipper : « Vous devez disposer d'une autorisation ». `onboarding.ouvrir_sources_par_lien` ouvre chaque source par le lien au démarrage et à chaque nouveau Drive. (2) **Photo de profil promise, jamais envoyée** — `profil.envoyer` dit maintenant où la prendre quand elle manque (et le journalise), la photo est plafonnée à 9,5 Mo (limite Discord), son échec n'emporte plus la bio. (3) **« Ajoutez votre nom »** — un bloc « Nom du profil » (le prénom de la créatrice) part avec la bio ; règle 26 de l'assistant. (4) **« code » tapé 3 fois** — `!code` guette 5 min (`CODES_ATTENTE_SEC=300`) et remplace son message par le code dès qu'il arrive ; un 2e `!code` pendant le guet répond « je guette déjà » ; le salon commun reste à 1 min (et la variable `canal_id` inexistante qui l'aurait fait planter est retirée). (5) **L'assistant a contredit l'écran et s'est dit manager** — règles 27 (jamais contredire une erreur visible) et 29 (« tu es l'assistant, pas le manager »), base de connaissances corrigée. (6) **« avant le 2026-09-30 », « en MP »** — `date_fr` (« 30/09 à 14 h ») dans `ou_en_es_tu`, plus de « en MP », règle 28. (7) « Tes accès arrivent un par jour » → « un compte tous les 48 h ». Déjà corrigé le matin même : les 5 règles + J'ACCEPTE après le test et la ligne « Ton salon perso ».

**Numéro WhatsApp vérifié au formulaire (30/09, Gaëtan : « assure-toi qu'ils ne mettent pas des numéros erronés »)** : `numeros.verifier` (bibliothèque `phonenumbers`, ajoutée à `requirements.txt`) lit le numéro avec le pays choisi. Numéro qui n'existe pas (trop court, trop long, « +220 » Gambie pour un Béninois) → formulaire réaffiché avec l'indicatif attendu et un exemple du pays, rien d'enregistré. Numéro valide mais d'un autre pays que celui choisi, ou fixe → réaffiché une fois (champ caché `tel_ok`), accepté s'il est renvoyé tel quel. Corrigé sans rien demander : ancien numéro béninois à 8 chiffres (« 01 » ajouté), numéro local sans indicatif, indicatif sans « + », « +33 06… ». Le classeur reçoit le numéro au format international propre (« +229 01 23 45 67 89 »). Limite : un numéro valide avec un chiffre faux ne se détecte pas sans envoyer un message. Sans `phonenumbers`, ancienne lecture du bot, aucun blocage.

**Test de montage : seuil gardé, effort valorisé, zéro attente (30/09 soir, Gaëtan : « important de garder le seuil, le bot
doit voir que le Reel est différent du rush de base, bien monté, bon hook ; peu d'attente ; valorise l'effort plus que le
résultat »)** : `TEST_TOUT_ACCEPTER` repasse à 0 (seuil `TEST_AUTO_SEUIL` = 7). Grille : travail visible sur le rush (4),
accroche de la première seconde (3), lisibilité (1), format et durée (2), avec la consigne de valoriser l'effort. Le modèle voit
d'abord deux images de deux rushes du dossier du test (`rushes_reference`, lus sur le Drive de `LIEN_TEST`, cache 6 h), puis le
Reel ; `copie_du_rush` (même durée à 1 s près, trois images 16×16 quasi identiques) plafonne la note à 3, comme un
`differe_du_rush: false` du modèle. Sous le seuil : pas de review, « Presque ! … renvoie ta vidéo ici » et l'état repasse à
`test_envoye` (`essais_rendu`) ; le manager ne voit que le 3ᵉ raté (`TEST_ESSAIS`), avec « réponse sous 24 h ». Bug corrigé : la
réécriture de l'état lu avant l'avis effaçait la validation automatique (« valide » repassait à « test_rendu ») ; les liens admin
s'écrivent maintenant sur un état relu. Le message d'arrivée ne dit plus « Ton salon perso : #… » (il y est déjà posté).

**Un seul recrutement, test accepté par le bot (30/09, Gaëtan : « on associe le recrutement FR et INT, on les félicite d'avoir
rejoint l'agence et on donne les prochaines étapes ; accepte toi-même le test de montage »)** : toute vidéo de test rendue dans
les temps est validée par le bot, quelle que soit la note (`test_accepte`, `TEST_TOUT_ACCEPTER=0` rend le seuil de 7) ; l'avis
reste, en conseils, et la réponse devient « Bien reçu ! Test validé ✅ ». `INT_EN_PAUSE` est forcé à faux. Le message d'arrivée
est le même pour tous : « 🎉 Félicitations Prénom, tu as rejoint l'agence ! », le salon perso, puis trois prochaines étapes
(créatrice et premier compte, un compte tous les 48 h avec `!code`, 2 Reels par jour pris dans le TOP 20) ; plus de « Team
International / France » ni de renvoi aux fiches dans ce message.

**Moins d'informations au clipper, le TOP 20 en direct, codes sur 60 min (30/09, Gaëtan)** : le lien Drive donné au clipper
ouvre directement son dossier « TOP 20 Reels » (`dossier_drive` renvoie ce sous-dossier ; le partage par lien du parent vaut
pour lui) et n'apparaît qu'une fois, dans l'étape 1 (« 📁 Tes Reels à publier (TOP 20) ») puis à l'étape 5 ; le message
d'accès redevient une ligne, sans lien de paie ni Drive (le lien arrive à l'étape 6). Salon des codes : fenêtre de 15 → 60 min
(Tara a tapé `!code` 21 min après le mail de son appel ; Gaëtan a dû lui donner le code à la main), et sans code trouvé, le bot
rappelle que les codes arrivent aussi tout seuls dans le salon perso. Mode d'emploi épinglé v4.

**Plus d'étape « 5 règles + bouton » après le test (30/09, Gaëtan : « supprime cette étape, on l'a déjà faite dans le
formulaire »)** : `suite_validation` accepte d'office (`accepter_conditions(uid, "site")`) — test validé = rôle, salon perso,
créatrice et comptes, avec un seul message « Test validé » suivi de la suite. Au démarrage, `acceptation.envoyer_boutons_en_attente`
accepte d'office les validés qui attendaient encore devant le bouton (trace `acceptation_auto`) ; un ancien bouton déjà envoyé
marche toujours si quelqu'un clique.

**Fiche contacts (30/09, Gaëtan : « le WhatsApp ou Telegram de tous les clippeurs du roster, et de ceux en attente sous
Clippers »)** : `!contacts`, admins seulement, affichée dans le salon admin ou envoyée en message privé (elle contient des
numéros). Deux parties : le roster par créatrice, puis les membres des salons « 🎬 Clippers » hors roster et hors staff, avec
leur étape. Pour chacun, lien WhatsApp (`wa.me`) et lien Telegram ; le numéro vient de la liaison du formulaire, sinon du
classeur des candidatures (par numéro, puis par prénom : « trouvé par prénom, à vérifier »). Rien n'est écrit dans le dépôt.

**Relances Telegram en un appui (30/09, Gaëtan : « go idée 3 avec Telegram uniquement »)** : `relances.py`. Chaque matin à 10 h
(Paris), le salon admin reçoit les candidats qui ont envoyé le formulaire depuis plus de 24 h sans réussir le quizz ni arriver
sur Discord : un message par candidat, le lien qui ouvre sa conversation Telegram (`t.me/@pseudo`, sinon `t.me/+numéro`,
signalé « par numéro ») et le message à copier avec SON lien vers `/formation`. Rien ne part tout seul. Deux relances au plus (24 h
puis 72 h), 30 par jour (`RELANCES_MAX`), candidatures des 7 derniers jours ; rien n'est posté le matin quand il n'y a personne.
`!relances` : la liste tout de suite ; `!relances voir` : l'aperçu sans rien compter ; `RELANCES=0` éteint.

**Premier Reel fêté dans #dopamine (30/09, Gaëtan)** : le scan quotidien (`etats_comptes.scanner`) garde l'image de couverture
et le lien du dernier Reel des 24 h ; au premier Reel vu pour un Gérant, `premier_reel_dopamine` poste « 🎉 Bravo @clippeur pour
ton premier Reel ! » dans #dopamine avec l'image et le lien (le lien seul si l'image ne se télécharge pas), une seule fois par
clipper (`premiers_reels` dans l'état). Au premier passage, ceux qui ont déjà publié sont notés sans message.

**Une seule commande `!code`, jamais les codes sensibles (30/09, Gaëtan)** : `!code` donne le code pour créer un compte, se
connecter ou faire appel après un ban (fenêtre de 15 minutes dans #🔐-code-instagram, 2 h dans un salon perso) ; `!recup`,
`!appel`, `!unban` font exactement la même chose. `codes_2fa.est_sensible` lit le sujet et le mail jusqu'à la fin de la phrase
qui porte le code (jamais le bas du mail, où les codes de connexion disent « si ce n'était pas vous, changez votre mot de
passe ») : changer ou réinitialiser le mot de passe, l'e-mail, le numéro, la double authentification, désactiver ou supprimer
le compte → le code n'est donné à personne, ni au staff, et le salon admin reçoit une ligne « non transmis ». Testé sur 17
mails types (8 à donner, 9 à bloquer) : zéro erreur. Mode d'emploi épinglé v3 (création / connexion / appel, sans la ligne de
l'adresse masquée) ; base de connaissances : « déconnecté » = se reconnecter avec le mot de passe du message de comptes, jamais
« Mot de passe oublié », WhatsApp Gaëtan sinon.

**Site plus rapide et plus fluide (30/09, Gaëtan)** : l'envoi du formulaire n'attend plus Discord — l'invitation personnelle se
crée en arrière-plan pendant la formation (`_lancer_invitation`), `/discord/invitation` l'attend ou la recrée après un
redémarrage (`_invitation_prete`) ; mesuré en test avec un Discord à 2 s : la page formation arrive en quelques millisecondes.
Pages compressées (gzip, 7,4 → 3,1 Ko), connexion à Loom préparée dès le formulaire (preconnect + prefetch de la vidéo), boutons
qui réagissent au toucher, et un seul envoi par formulaire (« ⏳ Un instant… », fin des candidatures en double par double appui).
La page formation n'a plus de paragraphe d'étapes : « 1️⃣ Regarder la formation », la vidéo, « 2️⃣ Passer le quizz ».

**Sortie automatique : averti à 3 jours sans Reel, sorti à 7 (30/09, GO de Gaëtan)** : `sortie_auto.py` compte les jours depuis la
DERNIÈRE publication (une hausse du nombre de publications d'un de ses comptes entre deux scans ; la première valeur d'un compte
ne compte que s'il est vu après l'arrivée du clipper, un compte rendu garde les Reels d'avant), ou depuis la créatrice s'il n'a
jamais publié, jamais avant le 30/09 (`SORTIE_AUTO_DEPUIS`). À 3 jours (`SORTIE_AUTO_AVERT_JOURS`) : un message dans son salon
perso avec la date de sortie, une fois par silence. À 7 jours (`SORTIE_AUTO_JOURS`, 14 avant) avec au moins 5 jours de scan où
un de ses comptes existe pendant le silence (`SORTIE_AUTO_SCANS_MIN`) : la sortie habituelle, comptes et lien au suivant. Un
compte banni ou un scan en panne ne fait sortir personne ; la note « garde » et la liste de Jonas protègent toujours.
`!sortie-auto` montre les avertis et les sortants du jour, `!sortie-auto go` l'applique. Règle 5 du formulaire, du message
d'acceptation et de la base : « 3 jours sans publier = avertissement, 7 jours = licenciement ».

**POD neufs, coefficients d'attribution, règles (30/09, Gaëtan)** : `!pods` (staff, `pods.py`) montre par onglet le dernier POD et
les lignes « à créer » sans e-mail ; `!pods Chloé 5 voir` affiche l'aperçu ; `!pods Chloé 5` écrit 5 POD de 3 lignes sous la
dernière ligne de l'onglet (ETAT « à créer », @ neufs au format du classeur — alias + expression pour les deux premiers,
alias + mot court + « .vip/.prive/.club/.clic » pour le troisième, sans le nom chez Maddie —, MDP de 18 caractères, Utilisation
et Créatrice recopiées, Numéro Mail et POD qui suivent), mise en forme de la ligne du dessus recopiée ; Mail, Gérant, Phone vides
(une ligne sans e-mail n'est jamais livrée). Unicité des @ vérifiée contre tout le classeur, pas la disponibilité sur Instagram.
`!attribution` montre l'ordre pondéré et les clippers livrables par créatrice ; `!attribution Chloé:4,Sophie:3,Sarah:2,Jade:1`
le change (0 = exclue, gardé aux redémarrages, prime sur ATTRIBUTION_ORDRE) ; `!attribution défaut` y revient. `!parrain-top`
est maintenant reçu par le bot (seul `!parrain` exact l'était). Formulaire : encadré paie sur plusieurs lignes (1 000 / 5 000 /
10 000 / 20 000 visites), règles 4 et 5 « faux clics = licenciement », « 3 jours sans publier = licenciement » (même texte dans
`acceptation.REGLES`) ; la page `/formation` a deux boutons, « Voir la formation » et « Passer le quiz », plus de lecteur intégré.

**Formulaire relu (29/09 soir, Gaëtan : « enlève l'âge », « plus lisible », « simplifie les 5 règles », et sa capture « Merci,
candidature reçue » sans lien de formation)** : la page « Merci » était celle du pot de miel — le champ caché `site_web` se faisait
remplir par la saisie automatique du navigateur, et un vrai candidat voyait « candidature reçue » sans que rien soit enregistré ni
journalisé. Le pot de miel est retiré ; à la place, un jeton signé posé à l'affichage (`f`) : absent, faux, ou renvoyé en moins de
3 secondes → le formulaire revient avec « Petit souci technique… », jamais un faux merci, et le refus est journalisé. Le champ âge
disparaît : « J'ai 18 ans ou plus et j'accepte les 5 règles » dans la case (la note sur 8 compte « majeur » sur cette case). Le
formulaire est groupé en quatre étapes numérotées (Toi, Te joindre, Ton matériel et ton expérience, Les règles), l'aide se lit sous
chaque libellé, et la présentation a un encadré paie et « Comment ça se passe » en quatre étapes (`questions_candidature.json` :
une liste = étapes numérotées, `## ` = sous-titre, `!! ` = encadré, `-# ` = petit texte, `\n` = retour à la ligne ; `section` par
question). Les 5 règles gardent leur fond, en phrases courtes (même texte dans `acceptation.REGLES_SITE`). Sous la vidéo de
`/formation`, un lien « Ouvre-la ici » si le lecteur Loom ne s'affiche pas.

**Formation et quiz avant Discord, parrainage par lien, délai et déclencheurs au tableau (29/09 après-midi, GO des axes 1, 4 et 8)** :
(1) le formulaire envoyé mène à `/formation` (la vidéo Loom intégrée, les 5 mots-clés, le bouton du quiz) et le quiz se passe sur
le site, rattaché à la candidature (`/quiz?c=jeton`, deux essais, deux nouveaux 24 h après, ligne « avant Discord » dans l'onglet
« Quiz bot ») ; l'invitation Discord s'affiche au quiz réussi, et à l'arrivée le bot pose l'état `quiz_ok`, dit « ton test arrive »
et envoie le test de montage par le circuit habituel (`preparer_arrivee_site` / `suite_arrivee_site`). Un lien « rejoindre le
Discord tout de suite » reste sur la page pour qui n'a pas le temps. `QUIZ_AVANT_DISCORD=0` rend l'ancien ordre. Au passage, la
ligne « Candidatures bot » du classeur s'écrit à nouveau pour chaque formulaire : depuis l'invitation personnelle du matin, ce
chemin sortait avant de l'écrire. (8) Le lundi, après le classement de #dopamine, les cinq premiers reçoivent dans leur salon
leur lien personnel du formulaire (`/candidature?p=jeton`, au plus une fois tous les 28 jours, `PARRAINAGE_TOP_JOURS`) ; la
candidature venue par ce lien porte le parrain, et le parrainage s'enregistre tout seul à l'arrivée du filleul (5 $ à sa
première paie, comme `!parrain`). `!parrain-top` (staff) l'envoie tout de suite au top 5 des sept derniers jours. (4) `!tableau`
et l'envoi du lundi ajoutent le délai formulaire → premier Reel (médiane et 80 %, en jours) et les trois déclencheurs pour doubler
le recrutement sur 14 jours : formulaire → quiz réussi ≥ 30 % (arrivés sur Discord à côté), validés → premier Reel ≥ 50 %,
clippers livrables ≥ 2 × les validés des 30 derniers jours.

**Rapport quotidien compact (29/09, Gaëtan : « simplifie le GAML Report Bot, le plus pertinent et compact possible »)** : `rapport_quotidien.py` remplace le rapport GitHub Actions du dépôt reporting-marketing (dont la clé GAML était révoquée, l'onglet Tracking cassé et les inputs Apify morts) — son cron est retiré, il reste lançable à la main. Huit lignes sur la veille : subs et CA OF/MYM par créatrice (classeur Data G&M lu par le compte de service, `DATA_GM_ID`), 7 jours et variation, €/sub ; visites payables (relevés GAML du bot, `clics_7j`) par créatrice ; Reels (scan du classeur) par créatrice, clippers qui ont publié sur l'effectif ; top 5 visites ; silencieux (un compte créé, aucun Reel depuis 3 jours) ; Metricool si `METRICOOL_API_KEY` et `METRICOOL_USER_ID` sont posés (posts et vues par créatrice, créatrices absentes) ; saisie manquante (Rianah). Hors clipping (`dashboard_exclus`) exclu partout. Envoyé chaque jour à `RAPPORT_HEURE_PARIS` (13 h) sur Telegram (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`) et dans le salon admin ; `!rapport` l'affiche tout de suite, `!rapport telegram` l'envoie aussi ; `RAPPORT_QUOTIDIEN=0` éteint.

**Liens GAML alignés sur la page de chaque créatrice (29/09, `outils/gaml_aligner.py`)** : les 19 liens numérotés de Chloé, Sarah et Jade portent le design, la bio, le fond et les cartes (Miam → MYM, 0F → OnlyFans, mêmes images, mêmes effets, même ordre) de la page de référence de leur créatrice, avec les codes de tracking du bloc du classeur qui porte le lien ; jamais le code de la référence sur un lien (leçon du clone d'Eddy). Les cartes neuves sont créées avant que les anciennes soient retirées. Les liens `:fb`, `:ytb` et les références ne sont pas touchés. À relancer après un changement de la page de référence. Le classeur reçoit une colonne « Lien MYM Tracking » sur Sophie et Clara (insérée après la colonne OnlyFans).

**Onglets créatrices : un bloc par clipper (29/09, Gaëtan : « les POD regroupés, les mêmes liens OnlyFans / MYM / GAML de chaque clipper, par clipper et plus lisibles, uniquement ces colonnes, sans effacer aucune donnée »)** : `classeur_forme.py`. Un bloc = les lignes consécutives d'un même Gérant (Utilisation Clipper ou vide). Sur les colonnes Gérant, POD, Lien Infloww/OnlyFans, Lien MYM, Lien GAML : teinte de la créatrice (deux teintes en alternance), cadre, Gérant en gras, POD et liens visibles sur **la ligne du milieu du bloc** (29/09 soir, Gaëtan : « les liens OF / MYM / GAML au milieu du pod du clippeur »), les mêmes valeurs des autres lignes écrites dans la couleur du fond (ça se lit comme une fusion, rien n'est fusionné : le bot lit toujours chaque ligne ; une valeur différente reste visible), et les liens ou le POD absents d'une ligne recopiés depuis la première ligne du bloc qui les a (« ses 3 liens à mettre sur les 3 comptes »). **Clippers regroupés** (29/09 soir, Gaëtan : « associer les clippeurs ensemble si ça ne détruit pas toute la structure ») : un Gérant dont les comptes sont éparpillés dans l'onglet voit ses petits blocs déplacés juste après son plus grand (`moveDimension`, la ligne entière, rien d'effacé, le reste de l'onglet garde son ordre ; le 29/09 : 7 blocs déplacés sur Chloé, Sarah et Sophie). Rejoué après chaque scan, sur `!dashboard` et au démarrage quand la structure change (`DASHBOARD_VERSION`). La colonne MYM est reconnue par « Lien MYM » / « MYM Track » (jamais « Clics vers MYM », le tableau du mois), OnlyFans par « Infloww », « Lien OnlyFans », « OnlyFans Track ». La cadence de publication n'est pas dans ce classeur : elle est dans le Dashboard (Reels 7 j / hier).

**Bans Instagram vus par mail, push immédiat (29/09, Gaëtan : « pour les comptes bannis je veux plus de réactivité… trouve un moyen de chopper ces mails et de m'envoyer un push »)** : `bans_mail.py`. Quand Instagram suspend un compte, il écrit « Action requise sur votre compte, pseudo » (« Votre compte Instagram a été suspendu ») à l'alias iCloud du compte, qui renvoie vers la boîte Gmail que le relais des codes lit déjà (`CODES_IMAP_*`). Toutes les `BANS_INTERVALLE_SEC` (3 min), le bot lit INBOX **et** `[Gmail]/Spam` (ces mails y tombent souvent), sans rien marquer lu, sur `BANS_JOURS` jours ; **les mails Meta importants trouvés dans le Spam sont remis dans la boîte de réception et la pub Meta de la boîte de réception repart dans le Spam** (UID MOVE ; `BANS_DEPLACER_SPAM=0` / `BANS_PUB_VERS_SPAM=0` pour éteindre l'un ou l'autre) : c'est le filtre Gmail fait par le bot (29/09, Gaëtan : « fais le filtre Gmail pour moi… uniquement les mails FB et IG importants : sign in, sign up, ban, appel, informations importantes, demande de vérification. Je veux pas la pub »). `categorie()` : important = code, confirmation, connexion, inscription, bienvenue, suspension, action requise, appel, sécurité, mot de passe, récupération, paramètres, « de retour » ; pub = expéditeur posts-recap / follow-suggestions / stories-recap ou sujet « Découvrez… », « ont partagé », « ont commencé à vous suivre », « veut vous suivre », « ajouté du contenu », « rattrapez… » ; un mot important l'emporte toujours. Le relais des codes voit alors les codes qui se perdaient dans le Spam. Un mail « Vous êtes de retour sur Instagram, pseudo » (appel accepté) est poussé comme ✅, la ligne n'est jamais réécrite : Gaëtan décide s'il reprend le compte. un mail de suspension pas encore traité → la ligne du classeur (retrouvée par le pseudo, sinon par l'alias, une ligne vivante avant une ligne BAN) passe **BAN**, `bans_auto` retient le ban (le scan rend WARMUP si le compte réapparaît après appel), et une ligne part sur Telegram et dans le salon admin : `🚫 @pseudo — suspendu (28/09 11:24) · Tara · Sarah · mail n° 7 · ligne passée BAN` (ou « déjà BAN », ou « hors classeur »). Du mail, seuls le pseudo, l'alias et la date sont gardés. `!bans [jours]` (staff) : passage immédiat puis la liste des bans vus par mail. Les avis de paramètres, de connexion et les codes ne sont jamais pris pour un ban (le sujet décide, le corps confirme « suspendu »).

**Un compte tous les 48 h, réservation à 48 h, un BAN ne se réutilise jamais (29/09, Gaëtan)** : les textes des étapes 1 à 3 (`parcours.py`), l'assistant du salon perso, le message d'acceptation et la base de connaissances disent désormais « un compte tous les 48 h, jamais plus vite » (compte 1, 48 h, compte 2, 48 h, compte 3 ; le warm-up reste 24 h par compte, `WARMUP_JOURS`). Au premier démarrage après la mise en ligne, `annoncer_regle_48h` poste la règle une fois dans chaque salon perso (retenu dans `annonces.json`). `RESERVATION_JOURS` vaut **2** (48 h au lieu de 5 jours ; deux scans sans voir le compte suffisent) : une ligne « à créer » réservée et jamais créée retourne au vivier, elle est réutilisable. Une ligne **BAN** ne l'est jamais : identifiant, e-mail, mot de passe et lien GAML sont brûlés (`ETATS_DISPONIBLES` ne contient pas BAN ; la vérification du classeur marque « mail brûlé (ligne BAN) réutilisé » quand un e-mail de ligne BAN ressert).

**Le salon commun « code Instagram », pour tout le monde (29/09, Gaëtan : « un salon code Instagram pour tout le monde, les anciens de Jonas aussi ont des comptes à créer et des appels à faire ; le clipper tape !code et ça sort le code 2FA, sans e-mail ni mot de passe »)** : au démarrage, `codes_2fa.assurer_salon_codes` trouve ou crée le salon `CANAL_CODES_NOM` (🔐-code-instagram), **réservé aux rôles de l'équipe** (`CODES_SALON_ROLES` : Clippeur, Rookie, Confirmé, Elite) et aux managers (29/09, Gaëtan : « restreins le salon au rôle Clippeur »), droits reposés à chaque démarrage, et y épingle le mode d'emploi (court, émojis, niveau collège ; remplacé quand `VERSION_EXPLICATION` change). Dans ce salon, `!code` (ou le mot `code` seul) répond à n'importe qui avec les codes Instagram/Facebook reçus dans les `CODES_SALON_MINUTES` (10) dernières minutes, boîte de réception **et** Spam, le plus récent par adresse, **adresse masquée** (`orb…8i@icloud.com`), le pseudo du compte quand le mail le donne, jamais l'e-mail entier ni un mot de passe ; plusieurs codes en même temps → « repère le tien à l'adresse masquée ». `!recup` : les codes de récupération sur `CODES_SALON_RECUP_MINUTES` (30). Rien n'y est marqué lu : le relais des salons persos continue. Les codes d'un alias inconnu (les anciens de Jonas) partent désormais dans ce salon, adresse masquée, au lieu du salon admin. Limite connue : deux clippers qui créent un compte à la même minute voient deux codes et se repèrent à l'adresse masquée.

**Le classeur se vérifie seul (29/09, Gaëtan : GO)** : `classeur_verif.py`. Après chaque scan (et sur `!classeur`), cinq familles d'anomalies : un même e-mail sur deux lignes, un même pseudo sur deux lignes, une ligne BAN qui garde un Gérant, une ligne « à créer » réservée et jamais vue après `CLASSEUR_SCANS_MIN` (7) scans, un clipper avec plus de `CLASSEUR_MAX_COMPTES` (3) comptes vivants. Posté dans le salon admin quand la liste change (silence sinon, silence quand tout est propre), les gérants hors clipping (`DASHBOARD_EXCLUS`) ignorés pour les BAN, les réservations et le plafond. **Rien n'est corrigé** : c'est Gaëtan qui tranche dans le classeur.

**Nettoyage des candidatures de test (29/09)** : au démarrage, `nettoyer_candidatures_test` retire du pipeline toute candidature marquée « test technique du site » ou dont le prénom commence par « Test », son invitation Discord et sa ligne du classeur des candidatures, puis le dit au salon admin. Les réponses qui commencent par `+`, `=`, `-` ou `@` sont écrites en texte dans le classeur des candidatures (un numéro « +261… » donnait #ERROR!).

**Invitation personnelle à la place de l'autorisation Discord (29/09, GO de Gaëtan)** : sur 25 candidats arrivés sur la page « Rejoindre le Discord » les 27 et 28/09, 5 seulement sont revenus par l'OAuth. Désormais, à l'envoi du formulaire, le site demande au bot une invitation personnelle (`invitation_site` : même mécanique que `!inviter`, 7 jours, `max_uses=2`, notée `source: site` dans `invitations` avec le numéro et le prénom) et affiche `/discord/invitation` : un bouton, l'appli Discord s'ouvre, « Accepter ». À l'arrivée, `accueillir_site` consomme l'invitation, pose le prénom, ouvre le salon perso et relie par le numéro (`traiter_liaison`) ; un ancien passage (quiz raté, sorti) est remis à zéro. Si l'invitation n'a pas pu être identifiée mais qu'une invitation du site de moins de 20 minutes est en attente (`invitation_site_recente`), l'arrivant n'est pas raccompagné malgré le serveur fermé : accueil classique, liaison par le numéro. Si le bot ne peut pas créer d'invitation, l'OAuth reste en secours (`/discord/connexion`).

**Échéance du quiz et droit de recommencer (29/09, GO de Gaëtan)** : le message d'arrivée dit « ⏳ Tu as 72 h pour le faire » (`QUIZ_DELAI_H`), les relances à 24 h et 48 h comptent à rebours, et `candidats_a_sortir` fait sortir (MP, kick, salon supprimé par `on_member_remove`) tout candidat sans quiz réussi depuis `CANDIDAT_SORTIE_JOURS` (7) jours — jamais un signé, un parcours au-delà du quiz, un membre avec un rôle autre que Clippeur/rangs, et jamais pour un retard antérieur au 29/09 (`SORTIE_QUIZ_DEPUIS` : ceux qui étaient là ont leurs 7 jours à partir de la règle). Il peut recommencer : refaire le formulaire donne une nouvelle invitation et deux nouveaux essais. Deux quiz ratés ouvrent un nouveau cycle de deux essais `QUIZ_CYCLE_H` (24) heures après le dernier échec (`essais_quiz_cycle`, `prochain_essai_quiz` pour la page d'attente du site, même lien).

**Rétrospective : les consignes apprises ne s'appliquent plus toutes seules (29/09)** : le 28/09 au soir elle avait appris « attendre la réponse du humain avant de continuer le parcours » et « jamais vidéo + quiz dans le même message », deux contresens du process, injectés dans le prompt de l'assistant. Désormais `retro.consignes_texte` ne lit que les consignes posées par le staff (`!retro consigne Le texte.`, `!retro consignes`, `!retro oublier n`, source « staff » dans `consignes_apprises.json`) ; les consignes que la rétrospective propose restent dans le digest, marquées « NON appliquées », et l'ancien fichier est ignoré. Les leçons (questions/réponses de la FAQ apprise) restent apprises toutes seules.

**Rôles « Grille » retirés (29/09)** : « Grille France / Grille International » n'ont jamais été créés sur le serveur et `#rémunération` est public depuis le 28/09 ; l'avertissement « Grille non attribuée » partait au salon admin à chaque arrivée. Plus d'attribution à l'arrivée ni à la liaison, plus de retrait à la signature, à `!equipe` ni à la sortie, plus de lignes dans `!verifier`, plus de variables `ROLE_GRILLE_*`. La base de connaissances répond aussi à « payé chaque semaine ou chaque mois ? », « qui est mon manager ? », « pourquoi je n'ai pas été retenu ? » (les trois lacunes encore d'actualité).

**Formulaire et passage vers Discord (29/09, deux candidats « n'arrivent pas à rejoindre »)** : les 5 règles s'affichent en liste, une par ligne, espacées, la case à cocher en ligne avec son texte (`_regles`, CSS `.ck` / `.regles`). Sur les 10 derniers candidats arrivés sur la page « Rejoindre le Discord », 2 seulement sont revenus par le callback Discord ; un lien avec la signature altérée (navigateur Samsung) a fini sur « Lien invalide ». Désormais `_cand_depuis` accepte l'identifiant de candidature seul s'il existe côté serveur (72 bits d'aléa, pas devinable), chaque page journalise son passage, un refus Discord (`error=access_denied`) est journalisé avec son motif, la page « Rejoindre » explique connexion, création de compte et ouverture de l'appli, la page « Presque » ne renvoie plus vers « le lien de l'annonce » (serveur fermé) mais propose de réessayer, et chaque page Discord porte le filet **WhatsApp de Gaëtan** (`WHATSAPP_GAETAN_URL`, passé au site). Le retour Discord est idempotent : le 27/09, quatre retours en double (l'appli et le navigateur ouvrent tous les deux le lien, même code à 400 ms d'écart) ont fini en « Invalid code » ; le premier retour gagne et les suivants revoient sa page pendant 10 minutes (`_retours`).

**Le quiz, c'est le site, plus jamais le Google Form (28/09, David)** : les trois derniers endroits qui fabriquaient encore le lien pré-rempli `LIEN_QUIZ` (quiz raté → deuxième essai, `ou_en_es_tu` qui nourrit l'assistant, relance « formation + quiz ») passent par `lien_quiz_pour` (le site d'abord, le formulaire seulement si le site n'est pas prêt), et `corriger_lien_quiz` remplace dans chaque réponse de l'assistant un lien Google Forms pré-rempli (`entry.`) par le lien de quiz du site du membre ; le formulaire du dimanche (forms.gle) n'est pas touché. `!quiz` donne à n'importe qui son lien personnel du site en MP.

**Dashboard par clipper dans le classeur, BAN dès que le compte n'est plus lisible, @everyone du dimanche (28/09)** : après chaque scan (et sur `!dashboard`, sans scan), l'onglet **« Dashboard »** du classeur des logins (`ONGLET_DASHBOARD`, exclu de la lecture des onglets créatrices) est réécrit : par créatrice, une ligne par clipper — comptes, créés, à créer, BAN, followers cumulés des comptes qu'il a en gestion (Utilisation Clipper ou vide, BAN exclus, tous les autres états comptent ; un compte passé Metricool reste dans le détail mais ne compte plus — 28/09, Gaëtan : « la somme des followers des 3 comptes que le clipper a en gestion »), visites payables des 7 derniers jours (la colonne « Clics last 7d. » de l'onglet, comptée une fois par clipper ; le total du clipper via `clics_7j` si la colonne est vide), **visites d'hier** (`clics_7j(prénom, 1)`, vide tant que le bot n'a pas réécrit l'onglet), Reels vus par le scan sur une fenêtre de 7 jours et **Reels d'hier** (le scan du jour), dernier Reel en format date dd/MM (28/09 : « pourquoi 46 293 partout ? » — une date ISO reformatée en nombre), Reels vus par le scan sur 7 jours, dernier Reel, détail compte par compte (`etats_comptes.lignes_dashboard`), trié par visites, avec un total par créatrice et un total général. `ETATS_BAN_JOURS` vaut désormais **1** : un compte WARMUP/GOOD/PRIVE introuvable passe BAN au premier scan (le « restreint » ne compte plus depuis le 30/09, voir « Un compte restreint n'est pas BAN ») (l'historique garde `restreint` et `followers`), et revient WARMUP s'il réapparaît. Le rappel reporting du dimanche mentionne `@everyone`.

**Les cinq GO du 28/09 soir (Gaëtan : « simple, supprime, dopamine, qu'ils gagnent vite »)** : (1) **la réservation qui expire** — `onboarding.reservations_expirees`, appelé après chaque scan du classeur : un clipper livré depuis `RESERVATION_JOURS` (5) jours dont aucun compte n'existe (toutes ses lignes « à créer », trois scans au moins sans le voir) rend ses lignes au vivier (Gérant vidé, alias 2FA détachés, fiche vidée) ; `expirer_reservations` remet son parcours à zéro, poste un message court avec le bouton persistant « 🔄 Je reprends » (`BoutonReprise`, `reprise:<uid>`) qui relivre trois lignes et relance l'étape 1, et une ligne part à l'admin ; un clipper qui a créé au moins un compte n'est pas touché (la sortie à 14 jours juge). (4) **le parcours avance par le scan** — `parcours.reconcilier` reçoit aussi les comptes qui ont publié : le premier Reel vu ferme l'étape 5 tout seul (les étapes 1 à 3 se fermaient déjà quand le compte apparaît). (5) **le profil prêt à coller** — `profil.py` : après chaque étape 1 à 3, une photo du dossier « Photos » de la créatrice (DRIVE_SOURCES, en rotation, `profil.json`) en pièce jointe et une bio tirée d'une banque de vingt (jamais deux fois de suite), dans un bloc copiable ; `PROFIL=0` éteint ; le texte de création dit « mets la photo et la bio que je t'envoie ». (7) **silence et classement** — la ligne du matin se tait déjà quand tout est à zéro ; le lundi, `paie_clics.texte_classement` poste dans #dopamine (`CANAL_DOPAMINE_ID`) les cinq premiers en visites payées sur sept jours. (8) **la paie qui s'affiche** — la ligne du matin dit « quinzaine : N = X $ · virée le JJ/MM » (`prochaine_paie`) et `!mesclics` ouvre sur « Ta paie en cours : X $, virée le JJ/MM ». Le n° 10 (Data G&M par Infloww) attend une API qui n'existe pas encore.

**Le lien direct de la vidéo de formation (28/09, deux clippers sur WhatsApp : « je ne trouve pas la vidéo, c'est dans quel salon ? »)** : `LIEN_VIDEO_FORMATION` (défaut : le Loom de 15 minutes) remplace la mention du post « Bienvenue » dans `lien_formation()` — message d'arrivée, relances « quiz à repasser », étape de recrutement — et la base de connaissances porte le lien pour que l'assistant le donne quand on le lui demande. Le post du forum reste le repli si la variable est vide.

**Parrainage et ordre d'attribution (28/09 soir, deux « oui » de Gaëtan)** : `parrainage.py` — `!parrain @lui`, tapé par l'un ou l'autre dans son salon perso ou en MP : le plus ancien des deux sur le serveur est le parrain, l'autre le filleul (un seul parrain par filleul, filleul arrivé depuis moins de `PARRAINAGE_JOURS_MAX` = 30 jours, jamais le staff) ; le parrain touche `PARRAINAGE_PRIME_USD` (5 $) une seule fois, portée sur sa ligne de la liste `!paie-clics` le jour où le filleul y apparaît avec un montant (`primes_dues`, mémorisé par période dans `parrainage.json` : une liste retapée la garde, la période suivante non ; un parrain absent de la liste y reçoit une ligne à 0 visite). Rien n'est dit au filleul ; l'étape 7 (routine), `!aide` et la base de connaissances portent la seule phrase utile ; `PARRAINAGE=0` éteint. L'ordre d'attribution par défaut passe à « Chloé:3,Sarah:3,Sophie:3,Jade:1 » (Clara et Maddie à 0 tant qu'aucun e-mail de compte n'arrive ; `ATTRIBUTION_ORDRE` pour changer).

**Le Drive arrive avec le premier compte (28/09 soir, Simon)** : l'étape 1 du parcours affiche « 📁 Ton Drive (photos, Reels, TOP 20) » sous les accès ; un clipper livré sans Drive (créatrice écrite en minuscules dans sa fiche — `_source_de` cherche désormais l'entrée `DRIVE_SOURCES` sans casse ni accent —, source absente ou Drive en panne à ce moment-là) le reçoit au passage suivant de la boucle du classeur (`drives_manquants`, trois par passage, toutes les 15 minutes) : dossier créé ou retrouvé, partagé par le lien, message `texte_drive` dans son salon perso, TOP 20 décliné dans la foulée (`reels_pour_nouveau`).

**Qui quitte le serveur est sorti tout seul, et les accès se copient d'un geste (28/09 soir, Marias et Simon)** : `on_member_remove` → `traiter_depart` — un signé (registre ou roster) qui part reçoit le traitement de `!roster sortie` (`roster.appliquer_sortis`, revu le 28/09) : fiche → sortis.json, **comptes rendus au vivier** (`onboarding.liberer(pool=True)`, le suivant de la même créatrice les reçoit en premier), **lien GAML libéré pour le suivant** (`paie_clics.liberer_liens`, par uid ou par la note « Clipping Prénom » d'un lien sans clipper connu), **salon perso supprimé** (avant : renommé « sorti-prenom »), roster à jour, une ligne au salon admin ; un candidat qui part : salon supprimé, fiche retirée, relances coupées ; staff et anciens de Jonas : rien. Un homonyme encore sur le serveur protège le classeur, les liens et le salon reconnu par son seul nom. `sorties_a_appliquer.json` est un dépôt comme `messages_a_envoyer.json` : `[{"id", "prenom", "raison"}]`, chaque entrée est appliquée une fois au démarrage (`roster.sorties_deposees`, trace dans `roster_sorties_deposees.json`) — c'est ainsi que Marias, parti avant le déploiement, a été sorti. Identifiant, e-mail, mot de passe et code 2FA arrivent chacun **dans son propre bloc de code** (étapes 1 à 3 du parcours, `message_comptes`, `codes_2fa.ligne_code`) : sur le téléphone, le bouton du bloc copie la valeur seule, plus de sélection à la main dans Discord.

**Formulaire du site à sept champs plus la case (28/09, décision de Gaëtan)** : `questions_candidature.json` ne pose plus que prénom, âge (nombre, « il faut avoir 18 ans »), WhatsApp, Telegram (pour le message privé), pays, téléphones réservés à ce travail (nombre et modèle de chacun) et une seule question ouverte « ton expérience » (Instagram, TikTok, montage, clipping, « détaille le plus possible », avec les pistes en aide : comptes gérés, vues, application de montage, heures par jour), puis la case des 5 règles. `score_candidature` garde sa note sur 8 mais la lit dans ces réponses : majeur (âge ≥ 18), iPhone et ≥ 2 téléphones dans la réponse « téléphones », expérience non vide, un outil de montage cité (`OUTILS_MONTAGE`), des chiffres (vues, abonnés, k, millions), ≥ 3 h par jour ou « temps plein », réponse détaillée (≥ 250 caractères) ; les colonnes de l'ancien Google Form (montage, Reels/jour, heures/jour, shadowban) comptent encore pour les anciennes lignes. `journaliser_candidature_sheet` écrit chaque réponse dans la colonne de l'onglet « Candidatures bot » dont l'en-tête correspond (libellé exact, sinon mot-clé via `CHAMP_PAR_QUESTION`, sinon une colonne ajoutée au bout avec son en-tête), `!fiche` montre Telegram et l'expérience sur 320 caractères, et n'affiche les anciennes questions que si elles sont remplies.

**J'ACCEPTE devient une case cochée (27/09, `acceptation.py`)** : les 5 règles sont une case obligatoire du formulaire du
site (question `conditions`, type `checkbox`) ; la liaison porte `conditions_site`, et à la validation du test l'accès
s'ouvre tout de suite (`accepter_conditions(uid, "site")` : rôle, registre, salon perso, créatrice automatique) sans rien
écrire. Un validé passé avant la case reçoit les règles en MP avec le bouton persistant « ✅ J'accepte, on y va »
(`BoutonAccepte`, custom_id `accepte:<uid>`) ; le mot J'ACCEPTE tapé marche toujours. Au démarrage, une fois par personne,
les validés encore en attente reçoivent le bouton (`bouton_accepte` dans le pipeline). **Attribution automatique des
créatrices (27/09, `attribution.py`)** : dès l'acceptation, le clipper reçoit la créatrice suivante de la séquence pondérée
`ATTRIBUTION_ORDRE` (défaut « Chloé:3,Sarah:3,Sophie:3,Jade:2,Clara:1,Maddie:1 » : trois d'affilée chez Chloé, trois chez Sarah, trois chez Sophie, deux chez Jade, un chez Clara, un chez Maddie, puis on recommence ; un ordre changé remet le compteur au début) avec tout ce que `!creatrice` faisait ; une créatrice sans
catégorie ni rôle sur le serveur est sautée et signalée ; au démarrage (après `ATTRIBUTION_DELAI_DEMARRAGE_SEC`, 120 s),
les signés présents sans créatrice sont rattrapés un par un, `ATTRIBUTION_PAUSE_SEC` (90 s) entre deux ; `ATTRIBUTION_AUTO=0`
éteint ; état et historique dans `attribution.json`. **Tableau de bord du lundi (27/09, `tableau_bord.py`)** : le lundi
entre 8 h et 10 h (Paris), une ligne dans le salon admin — candidats → validés → premier Reel → jour 7 tenu → premier
paiement, sur les 7 derniers jours, la semaine d'avant entre parenthèses, et le ratio validés → premier Reel, la seule
décision de recrutement ; `!tableau` à la demande. Sources : classeur des candidatures, `validation` du pipeline, premier
jour avec un Reel dans `etats_comptes.json` (scan du classeur, 27/09) puis 7 jours dont 5 à 2 Reels ou plus, `paiements.jsonl` et les listes
`!paie-clics` mémorisées dans `clics.json` (`paies`). **Candidat en MP (27/09)** : l'assistant reçoit où en est le candidat
(numéro, quiz, test, échéance) pour l'aider pendant le test sans inventer. **Règle 21 (27/09)** : trois cas seulement vont
à un humain — ban, numéro refusé, paiement — via WhatsApp ; tout le reste, c'est la base, la fiche ou « je ne sais pas ».

**Messages déposés (27/09, `messages_deposes.py`)** : un message écrit dans `messages_a_envoyer.json` (dans le dépôt, à côté
du bot) est posté UNE fois au démarrage suivant — dans le salon perso d'un clipper (`"pour": "Daniella"`), dans un salon
nommé (`"salon": "#annonces"`) ou dans le salon admin, avec le bouton WhatsApp si `"bouton_whatsapp": true`. Trace dans
`messages_envoyes.json` (jamais deux fois) ; un salon introuvable est signalé dans le salon admin et retenté au démarrage
suivant. C'est le canal pour « envoie ça à X dans son salon » depuis une session sans accès à Discord. **`!paiement` pour
un clipper parti (27/09)** : `!paiement Quentin 50 fixe` sans mention marche même si Quentin n'est plus sur le serveur —
son identifiant vient de `sortis.json` (les `!sortie` et le roster), sinon du registre des signés, sinon un identifiant
Discord en chiffres ; un prénom inconnu de tout registre est quand même enregistré (sous `nom:prenom`, le bot le dit) pour
que le compteur « Déjà payés » soit juste. Un paiement à un parti ne passe pas dans le salon dopamine : il est confirmé
dans le salon de la commande avec le nouveau total. Plusieurs lignes `!paiement` dans un message = rafale.

**Moins de bruit dans le salon perso (27/09, relecture du salon de Daniella)** : un « ok », « merci », « d'accord »
ou un emoji seul reçoit un 👍 et rien d'autre (`est_acquiescement`) ; un message qui mentionne un humain (« @Gaëtan et je
fais quoi ? ») n'est pas pour le bot (`mentionne_humain`) ; quand un admin ou un manager a parlé dans le salon il y a moins
de 30 minutes, le bot se tait sauf question (`staff_a_parle`). L'assistant ne pose plus de question inutile (« iPhone ou
Android ? », « dis-moi quand c'est fait »), ne ferme sa réponse par « 👉 Prochaine étape » que si elle diffère de l'étape
déjà affichée, ne donne jamais la cause d'un blocage (règle 23 : « déconnecté, mot de passe modifié » = « Mot de passe
oublié » puis `!recup` ; « en révision » = capture + WhatsApp), n'invente pas de pseudo quand celui du classeur est pris
(règle 24 : se connecter d'abord, sinon un point ou un chiffre en plus et le pseudo exact écrit dans le salon), et ne
parle que des comptes créés (règle 25, la mémoire porte « Comptes créés : N sur 3 »). `!code` / `!recup` attendent le
mail jusqu'à `CODES_ATTENTE_SEC` (60 s, pas de `CODES_ATTENTE_PAS_SEC` 15 s) avant de dire non, en éditant leur message
« ⏳ Pas encore reçu » ; un code donné par la commande est noté relayé et marqué lu, la boucle ne le reposte plus ; le
message « pas de code » ne liste plus les adresses. La ligne du matin « Visites hier : 0 · quinzaine : 0 » n'est plus
envoyée tant que tout est à zéro.

**Codes de récupération (27/09)** : Instagram envoie « 956472 is your Instagram recovery code » quand on
fait « mot de passe oublié » ou quand on **fait appel** pour un compte banni. Le mail suit le même chemin
que le 2FA (même alias, même boîte, même salon) mais le bot le reconnaît au sujet (`recovery`, `récupér`,
`reset`, `réinitialis`, `get back`) et le poste avec son libellé (`🛟 Code de récupération Instagram : 956472
pour alias · compte @pseudo (reçu il y a 2 min)`) : le clipper ou le manager sait quel code Instagram attend.
`!recup [alias]` (alias `!appel`, `!unban`, `!deban` ; « recup » seul dans le salon perso) redonne le dernier
code de récupération de chaque adresse rattachée au salon, 6 h en arrière (un 2FA n'en remonte que 2), et
`!code` montre le dernier code de chaque type. Mêmes droits que `!code` : le clipper dans son salon perso,
le manager sur ses alias, l'admin partout. Le pseudo du compte (`Hi chloe.xxx,`) n'est lu que pour
l'afficher à côté du code, le corps du mail n'est jamais relayé.

## v2 — le bot du programme clippers (compteur, paiements, invitations, rangs)

Le bot fait maintenant tourner la boucle « paiement → preuve → contenu → clippers » :

### Commandes admin (depuis n'importe quel canal)

- **`!paiement @clippeur 50 fixe semaine 1`** → poste « 💸 X vient de recevoir 50 € ! » dans
  `#dopamine`, met à jour le compteur épinglé, trace dans `paiements.jsonl`. Le lundi des
  virements : une commande par virement effectué = la preuve publique instantanée.
- **`!compteur`** → (re)crée/met à jour le message épinglé « X € déjà versés aux clippers ».
- **`!rang @clippeur Rookie|Confirmé|Elite`** → assigne le rôle (crée d'abord les 3 rôles
  dans les réglages du serveur ; le rôle du bot doit être AU-DESSUS d'eux dans la liste).
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
  `!tests`, `!test-ok`, `!test-non`, `!quiz-ok`, `!reset @membre` (remet le parcours candidat à zéro pour le rejouer — quiz, test, validation ; liaison, rôles et équipe conservés), `!pipeline`, `!relance`,
  `!sortie`, `!alias`, `!code`. `!aide` lui donne sa liste. Avant le 10/09, tout était réservé
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
- **`!relance @x`** : envoie en MP la prochaine étape de SON parcours (numéro, quiz, test,
  J'ACCEPTE), sans rien réinitialiser ; respecte son STOP (`… forcer` sinon).
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
est relancé à 24 h et 48 h. `!purge-int` et `!annonce-int` ont été retirées le 29/09 (voir « Retiré »).

**Relancer le stock après une pause (dans l'ordre)** :
1. Vérifie que `PAUSE_INT` est absent ou à `0` dans Railway (redéploiement automatique).
2. Feuille Google du quiz → Extensions → Apps Script → exécute **`rejouerReussites()`** une fois : elle
   re-poste un `QUIZ_OK` pour toutes les réussites (≥ 30/34, `QUIZ_SEUIL`, tenu aussi par le bot qui rétrograde en échec un QUIZ_OK sous le seuil) — le bot envoie le test à ceux qui ne l'ont
   jamais reçu et ignore les autres (idempotent). Les réussites survenues PENDANT la pause n'ont pas
   d'état dans le pipeline : c'est la seule façon de leur envoyer le test.
3. Mets à jour le salon **Grille International** (rémunération/bonus) : le bot n'y écrit pas.

## 🔒 Serveur fermé : le tunnel candidat hors Discord (14/09, soir)

Décision du 14/09 : **plus personne n'arrive sur Discord avant validation** — le serveur est réservé aux
clippers validés. Le tunnel (formation → quiz → test 48 h → rendu) se déroule par e-mail et formulaires ;
Discord ne commence qu'au J'ACCEPTE (le contrat DocuSeal a été retiré le 29/09).

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
   suite habituelle — conditions → J'ACCEPTE (France comme International depuis le 23/09). Plus de numéro
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
- **Contrats** : retirés le 29/09 avec DocuSeal (voir « Retiré ») — un e-mail envoyé en MP est simplement enregistré.
- **STOP** est respecté partout (relances de test, J+7/J+14, `!relancer-lien`).
- **Digest du matin** (toujours actif, plus conditionné à la trésorerie) : signés sans créatrice depuis
  48 h (manager mentionné), validés sans J'ACCEPTE, avertissements
  techniques des 24 h. Message de démarrage dans le salon admin : automatisations actives, éteintes,
  variables manquantes.
- **Codes 2FA** : délai IMAP borné, mail marqué lu seulement après relais réussi, rôle Manager par égalité
  exacte, mails Meta sans mot « code/confirmation » ignorés, panne signalée une fois puis « revenu ».
- **Assistant** : escalade vers le manager pour l'opérationnel, jamais de délai ou de montant inventé,
  jamais de contournement, étiquette de source unique en fin de réponse.

## 💶 Paie en deux fois et valeur d'un abonné (14/09)

**La paie tombe le 16 et le 1er**, comme pour les chatteurs (fini le lundi hebdo du premier mois). Les commandes
`!primes` et `!primes acompte` (paie variable de l'ancien modèle) sont parties le 29/09 avec les inputs. Les montants
du fixe restent dans #rémunération : le bot ne les connaît pas.

**`!ltv [jours]`** lit le classeur « Data G&M Créatrices » (module `creatrices.py`)
et sortent, par créatrice, la valeur d'un abonné OF contre MYM sur 30 jours (OF converti en € au taux
`TAUX_USD_EUR`, défaut 0,92). Réglage, une fois : Fichier → Partager → **Publier sur le web** →
*Document entier* → format **Microsoft Excel (.xlsx)** → Publier → coller le lien dans Railway :
`SHEET_CREATRICES_XLSX_URL`. Les onglets « Synthèse » et « Notice » sont ignorés ; les onglets créatrices
doivent garder leur structure (ligne « Date », colonnes B/C = OF, E/F = MYM).

## 🧭 Trois rapports, pas douze (simplification du 14/09)

« Même moi je comprends rien » (14/09) : le bot produisait un bilan long par clipper, un récap Telegram, une copie
admin, un digest candidats en admin ET sur Telegram, des salons-compteurs… Les bilans des inputs (4 lignes au
clipper, rapport MARKETING au manager, hebdo du lundi et `!hebdo`) sont partis avec le module `inputs_clippers`
le 29/09 (voir « Retiré »). Ce qui reste : le message du matin de chaque clipper (`matin.py`), le rapport GAML du
manager (`rapport_stats.py`, #jonas-stats), le tableau de bord du lundi (`tableau_bord.py`), le digest candidats
(copie Telegram si `TELEGRAM_QUOTIDIEN=1`). Les salons-compteurs (`CANAL_STAT_*`) : supprimer les salons
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

Dès `!creatrice @clipper Prénom`, le bot livre dans le salon perso du clipper (ou en MP) : ses **comptes Instagram** pris dans le classeur des logins (`CLASSEUR_LOGINS_ID`, **un onglet par créatrice** depuis le 27/09 : Chloé, Sarah, Sophie, Jade, Maddie, Clara… découverts tout seuls par leur en-tête, liste relue toutes les 10 minutes ; Gaetan, Tracking et Backup ignorés (`ONGLETS_EXCLUS`), les onglets masqués dans Google Sheets ne sont jamais lus, l'ancien onglet global « Instagram » n'est lu que s'il n'y a aucun onglet créatrice, `ONGLET_LOGINS` = « Sarah, Sophie » pour forcer une liste ; une ligne sans Créatrice prend le nom de son onglet, chaque ligne garde son onglet et toute écriture y retourne, un compte copié-collé sur deux onglets ne compte que dans celui de sa créatrice ; lignes Utilisation = Clipper, Gérant vide ou x/y/z, état à créer / GOOD / WARMUP / PRIVÉ / ACTIF, Créatrice = la sienne ; les comptes déjà créés passent d'abord ; `COMPTES_PAR_CLIPPER`, 3 par défaut) en écrivant son prénom dans la colonne Gérant ; son **lien GAML** (cloné depuis un lien « Clipping » de la créatrice s'il n'en a pas) ; son **Drive personnel** si le script de l'agence est déployé. `!creatrice` pose aussi le rôle de la créatrice s'il existe (même prénom en mot entier) et le rôle Team s'il manque (25/09). Sans e-mail connu, le message du clipper lui demande son adresse Gmail : dès qu'il la poste dans son salon perso ou en MP, le Drive lui est partagé. Le classeur est aussi une télécommande : toutes les 15 minutes, un compte dont la colonne Gérant porte le prénom d'un membre signé, jamais livré à ce membre, part dans son salon perso (état dans `onboarding.json`). **Personne ne se perd dans #général (27/09 soir, Ascartel)** : au démarrage, tout membre arrivé depuis moins de 14 jours sans salon perso reçoit le sien (`salons_arrivants_recents`, en plus des candidats du site : une arrivée pendant un redéploiement n'est plus perdue) ; un arrivant sans salon qui écrit dans un salon public reçoit son salon sur-le-champ, un mot qui l'y envoie et son message recopié dedans (`orienter_arrivant`, une fois par jour par membre) ; le message d'accueil dit le parcours en une ligne, l'étape en cours en gras (« **Formation** → Quiz → Test de montage → Création du compte Instagram → Publication », `ligne_parcours`) et la seule prochaine chose à faire (`etape_recrutement`). **28/09 (Gaëtan)** : s'il est sur Discord, il a rempli le formulaire, on ne le lui rappelle jamais ; l'arrivée par le site envoie UN message (`texte_accueil_liaison` : bienvenue, parcours, formation, lien du quiz sans aperçu, ni numéro ni grille), des lignes vides entre les blocs. Les messages déposés acceptent `effacer_bot` (les messages du bot du salon sont effacés d'abord) et `accueil_liaison` (le texte est le message d'arrivée du membre, calculé à l'envoi). **Quiz du site (28/09)** : `quiz.json` porte le quiz de la formation de 15 minutes, 10 questions (5 mots-clés à écrire, champ libre noté sans accents, sans majuscules, sans « s » final ; 5 questions à choix sur la vidéo) et `"seuil": 8` ; dès qu'il existe, `lien_quiz_pour` donne le lien du site (`/quiz?t=jeton`) au lieu du Google Form, la page affiche le seuil du fichier, `web_candidature.noter` note, le résultat repasse par `traiter_quiz_web` → `traiter_quiz_webhook` (test envoyé ou second essai, dans le salon perso, à la seconde) et une ligne par essai (date, prénom, identifiant Discord, score, essai, réussite, mots-clés donnés) part dans l'onglet « Quiz bot » du classeur des candidatures. Le Google Form reste accepté (seuil 30/34 tenu par le bot seulement pour un total de 34) ; `seuil_quiz_texte()` écrit « 8/10 » ou « 30/34 » dans tous les textes. **Décisions du 28/09 (Gaëtan)** : la bascule au clic est le **05/10** (`BILAN_FIXE_DATE`, défaut 2026-10-05) ; **le lien ne va plus qu'en story à la une**, une seule fois sur chaque compte (les @ en bio font des bans), avec chaque jour une story « widget du profil » vers la story à la une ; **trois comptes de croissance, plus de compte privé**, 24 h de warm-up par compte après sa création puis il publie (étapes 1 à 7 et base v12 réécrites) ; **le Drive du clipper s'ouvre par son lien** (`drive_partager_public`), plus d'adresse e-mail demandée ; **relances courtes** (`PARCOURS_RELANCE_JOURS`, 2) : une étape qui traîne reçoit une ligne « 👉 … Bloqué ? Écris ici. » tous les deux jours ; **sortie automatique** (`sortie_auto.py`, `SORTIE_AUTO=0` pour éteindre) : chaque jour à `SORTIE_AUTO_HEURE_UTC` (8 h), un clipper attribué depuis `SORTIE_AUTO_JOURS` (14) jours dont les comptes ont été scannés au moins `SORTIE_AUTO_SCANS_MIN` (7) fois sans une publication sort comme par `!sortie` (`sortir_membre`), mais ses comptes créés **restent dans le vivier** (`liberer(pool=True)`) et son lien GAML est **libéré** (`paie_clics.liberer_liens`) : le prochain clipper de la même créatrice reçoit ces comptes en premier (`disponibles`), avec une étape « connecte-toi » au lieu de « crée » (`parcours.CONNEXION`, le code de connexion arrive dans son salon) et le lien repris (`reprendre_lien`, ses visites comptent depuis la reprise, `somme` respecte `depuis`). La première passe ne sort personne : elle poste la liste au salon admin, le lendemain ça part tout seul ; `!sortie-auto` montre la liste, `!sortie-auto go` l'applique, une note manager contenant « garde » protège un clipper, les anciens de Jonas (`sans_salon`) ne sont jamais concernés. **Contrôle par Reel** : le scan quotidien lit les légendes des Reels de la veille (`etats_comptes.RE_FAUTE` : lien, domaine, @) → « ❌ … enlève-le » dans la ligne du matin du clipper et une ligne à l'admin. **Rapport du matin** : tous les clippers dans le salon admin, seulement les anciens de Jonas (`sans_salon`) dans #jonas-stats (`rapport_stats.clippers_de_jonas`). `!bilan-fixe [jours]` : le verdict des clippers encore au fixe (visites payables, équivalent au clic, point mort ≈ 32 visites/jour pour 100 €, 65 pour 200 €), posté tout seul dans le salon admin le `BILAN_FIXE_DATE` (2026-10-09, décision du 25/09 : deux semaines puis clic ou sortie). `ROLE_EQUIPE_UNIQUE` (défaut « Rookie ») : le premier rang remplace Team France / Team International pour tout le monde au J'ACCEPTE (plus de distinction de pays) ; un Confirmé ou une Élite est déjà dans l'équipe, rien n'est reposé. `!salons-equipe Sophie: Thia ; Chloé: Romaric, Hasina ; Sarah: Yves` (admin) : ouvre le salon perso des clippers déjà en place dans la catégorie de leur créatrice, y ajoute les managers humains (rôle Manager, ou pseudo contenant « manageur »), livre comptes du classeur, lien, Drive et alias 2FA, et démarre le parcours directement à la routine. Sans liste : tous les signés avec une créatrice au registre. Si la catégorie de la créatrice est **fermée au bot** (catégorie privée où son rôle n'est pas : Voir le salon, Gérer les salons, Gérer les permissions), le salon s'ouvre dans « 🎬 Clippers » et le bilan dit quoi corriger ; à la commande suivante, le salon est déplacé sous la créatrice. `!verifier` liste les catégories fermées. **Pseudos « Prénom - Créatrice » (25/09)** : le bot prend le prénom avant le séparateur partout (contexte de l'assistant, mémoire, classeur) ; le salon perso s'appelle par le prénom seul (`#thia`, ou `#prenom-creatrice` en cas d'homonyme), son identifiant est mémorisé au registre (`salon_id`) et les salons existants sont renommés au démarrage. Le rôle d'équipe unique est « Clippeur » (`ROLE_EQUIPE_UNIQUE`, Rookie encore accepté) et le rôle manager « Manager » ou « Manageur ». Un clipper qui tape `!etape` seul dans son salon revoit son étape en cours. **Classeur des logins suivi par le parcours (25/09)** : compte 1/2/3 validé → sa ligne passe à WARMUP, warm-up fini → les trois lignes passent à GOOD (une cellule ETAT à la fois, jamais la structure) ; une ligne « à créer » sans e-mail n'est plus livrée, `!comptes-libres` compte les livrables (créés + à créer avec e-mail). **États du classeur depuis Instagram (26/09, `etats_comptes.py`)** : chaque jour à `ETATS_HEURE_UTC` (7 h), le bot passe à Apify les comptes des onglets créatrices qui ont un Gérant (Utilisation = Clipper) et met à jour la colonne ETAT, une cellule à la fois : à créer → WARMUP dès que le compte existe ; WARMUP → GOOD après `ETATS_GOOD_JOURS` (3) jours de publication de suite ; WARMUP → PRIVE si le compte est passé en privé ; WARMUP/GOOD/PRIVE → BAN après `ETATS_BAN_JOURS` (1 depuis le 28/09, 2 avant) jour introuvable ou restreint (BAN posé par le bot, rendu à WARMUP s'il réapparaît) ; les états manuels (PERDU LOGS, à vérifier, BIZARRE…) et les lignes sans Gérant ne bougent jamais ; la colonne Followers est remplie pour **tous** les comptes créés du classeur, clippers, créatrices sous Metricool et comptes libérés (≈ 130 profils par jour, appels Apify par lots de 50, écriture seulement si le chiffre a changé). Chaque ligne qui a un Gérant reçoit aussi ses **visites payables des 7 derniers jours** (colonne « Clics GAML last 7d. »). La colonne **« Lien GAML associé »** est tenue par l'onboarding (27/09, « c'est le bazar ») : une ligne = LE lien du gérant pour la créatrice de la ligne (Julien : son lien Sophie sur ses lignes Sophie, son lien Chloé sur ses lignes Chloé, rien sur ses lignes Maddie ; deux liens pour la même créatrice → le plus récent ; la créatrice d'un lien se lit dans son nom GAML, sinon dans la mémoire du bot, sinon dans le domaine), remise d'équerre à chaque livraison, toutes les 15 minutes et sur `!trackings`, seulement les cellules qui changent. Les colonnes de chaque onglet sont reconnues par leur en-tête (26/09 : Gaëtan insère des colonnes ; 27/09 : onglet par onglet), jamais par position. Le code couleur de la colonne ETAT est une mise en forme conditionnelle posée le 26/09 (GOOD vert, WARMUP orange, BAN rouge, PRIVE bleu, à créer gris, PERDU LOGS violet, à vérifier jaune). Bilan dans le salon admin quand quelque chose change, alerte manager sur les BAN. `!etats-comptes [test]` lance un passage à la main. **Inputs clippers retirés (éteints le 27/09, décision de Gaëtan : « c'est l'ancien système » ; code supprimé le 29/09, voir « Retiré »)**. Le tableau du lundi lit « premier Reel » et « jour 7 tenu » dans l'historique d'`etats_comptes` (publications comptées par le scan quotidien du classeur, `tableau_bord.premiers_reels_etats`) et le message du matin reçoit sa ligne « 🎬 Hier : N publication(s) sur tes comptes » du même scan (`etats_comptes.lignes_reels`). La carte de tracking d'un lien GAML est aussi reconnue quand elle s'appelle « OF » ou « 0F » (Clara). Historique dans `etats_comptes.json`, `ETATS_CLASSEUR=0` pour éteindre. **Textes niveau collège (25/09, demande de Gaëtan)** : tout ce que le bot dit aux clippers (étapes du parcours, message de comptes, codes, visites et paie, bilan du matin, conditions, test, aide) est écrit en phrases de 10 mots, une action par ligne, sans parenthèses ; la base de connaissances porte une règle « Comment je parle » et ses fiches 1 à 6 sont réécrites au même niveau (v8). `CANAL_CANDIDATURE_ID` se répare par le nom (#bienvenue). **Parcours guidé (25/09, `parcours.py`)** : dès `!creatrice`, le salon perso déroule 7 étapes (compte 1, compte 2, compte privé, warm-up de 7 jours compté chaque matin puis ouverture automatique des Reels, premier Reel, lien en bio, routine) avec des boutons-liens vers la fiche du forum et le salon d'infos de la créatrice, et un bouton « ✅ C'est fait » persistant (DynamicItem). Dans ce salon, l'assistant IA reçoit la mémoire du clipper (étape, comptes, lien, Drive, visites 7 j, notes du manager) et joue le manager. Commandes manager : `!etape @clipper [n]`, `!note @clipper texte`, `!memoire @clipper`. État dans `parcours.json`. Commandes manager : `!comptes-libres [Créatrice]`, `!onboarding @clipper [Créatrice]`, `!liberer Prénom [handle …] [pool]` (rend les comptes d'un clipper parti : Gérant vidé, comptes créés en Utilisation « à mettre Metricool », ceux à créer de retour au pool ; `!sortie` le fait tout seul). Garde-fou homonyme (24/09, Eddy) : un membre arrivé depuis moins de 45 jours (`ONBOARDING_JOURS_NOUVEAU`) et jamais onboardé ne reçoit pas de comptes **déjà créés** portant son prénom — l'admin est prévenu (ancien clipper du même prénom ?) et tranche avec `!onboarding @clipper` (forcer) ou `!liberer`. Le trio livré fait 2 comptes de croissance + 1 privé (état PRIVÉ ou handle en priv/secret/perso).

**Google, deux voies** (`google_api.py`, `drive_agence.py`) : le **compte de service** (`GOOGLE_SERVICE_ACCOUNT_JSON`) lit et écrit les classeurs et lit le Drive, mais Google ne lui donne **aucun espace de stockage** (« Service Accounts do not have storage quota ») : il crée des dossiers, pas des fichiers. Tout ce qui copie ou dépose des fichiers passe par le **script Apps Script** `apps_script/drive_agence.gs`, déployé le 24/09 sous le compte Google de l'agence (le bot suit la redirection Apps Script à la main, en GET nu, sinon Google renvoie du HTML) (application web, exécuter en tant que moi, accès tout le monde) : `DRIVE_AGENCE_URL` + `DRIVE_AGENCE_SECRET`. Les sources par créatrice sont dans `DRIVE_SOURCES` (JSON : dossier parent « 🎬 Clippers » dans son dossier Instagram, sources Reels et Photos). **Depuis le 24/09, plus de copies limitées** (Gaëtan : « il faudra donner plus de contenu à chaque clipper ») : le dossier du clipper, créé par le compte de service, contient un **raccourci vers chaque source** (tout le contenu, aucun espace consommé), les sources et le dossier sont partagés en lecture à l'e-mail donné dans le tunnel (compte de service d'abord, script de l'agence en secours), et un sous-dossier « Reels spoofés » attend le spoofer. Le script de l'agence sert aux dépôts de fichiers (Reels spoofés) et aux copies si on en veut un jour.

## 🎬 Reels uniques par clipper (26/09, `reels_uniques.py`)

Gaëtan met les **TOP 20 Reels** de chaque créatrice dans « 📁 Reels › TOP 20 Reels » de son Instagram Drive. Le bot les décline pour chaque clipper en une version **différente et stable** (même clipper + même vidéo = même recette) : miroir ou non, zoom léger avec recadrage décalé, vitesse ± 3 %, saturation, contraste, luminosité, teinte, coupe d'attaque, ré-encodage 1080×1920 à 30 i/s (ffmpeg, présent sur Railway). Les variantes sont déposées dans le sous-dossier **« Reels uniques »** du dossier Drive du clipper (script de l'agence, le compte de service ne peut pas téléverser), nommées « Créatrice · Reel 07 · Prénom.mp4 ». Idempotent par nom de fichier et par état (`DONNEES/reels_uniques.json`). `!reels-uniques Chloé` (tout son roster) ou `!reels-uniques Chloé Ricado` ; et **chaque nouveau clipper reçoit les siens tout seul** à l'onboarding, en tâche de fond, bilan au salon admin. Option `OPUSCLIP_API_KEY` (clé du tableau de bord OpusClip, plan Pro ou plus) : chaque Reel repasse d'abord dans OpusClip sans découpe avec le template « Créatrices OFM » (sous-titres, recadrage) avant la déclinaison, ≈ 1 crédit par minute ; sans clé, ou si OpusClip échoue, on part de l'original. Les dossiers « Reels OpusClip » des créatrices ont été renommés « Reels extraits YTB » et `DRIVE_SOURCES` pointe sur les dossiers actuels (📁 Reels, 📁 Carrousel, 📁 Story), l'ancien identifiant Reels de Chloé était mort (404 sur les raccourcis).

## 🔁 Le process refondu du 26/09 (soir) : formulaire → quiz 30/34 → test jugé par le bot → 3 comptes, un par jour, 24 h de warm-up

Gaëtan a redit le process de bout en bout pour préparer une formation condensée ; le bot le porte partout (base de connaissances v10, INSTRUCTIONS, textes des étapes, aide, J'ACCEPTE). **Le parcours** : le formulaire du site (3 minutes) connecte le Discord ; vidéo de formation ; quiz `!quiz` à **30/34** ; test de montage rendu **en message privé au bot** (une vidéo brute à retravailler : texte, musique, format, coupes) ; **le bot regarde la vidéo** : `ffprobe` (format, durée), 4 images extraites par `ffmpeg` (installé par les variables Railway `RAILPACK_BUILD_APT_PACKAGES` et `RAILPACK_DEPLOY_APT_PACKAGES`, builder Railpack), jugement du modèle sur une grille en 10 points (format vertical, durée, accroche, sous-titres, travail sur la brute), note sur 10 postée au candidat et au salon admin ; **au-dessus de `TEST_AUTO_SEUIL` (7), le test est validé tout seul** (même chemin que `!test-ok`, `TEST_AUTO=0` pour revenir à la review humaine), en dessous le manager tranche avec l'avis sous les yeux. Puis J'ACCEPTE, salon perso, 3 comptes du classeur, et **un compte par jour avec 24 h de warm-up sur chacun** (`WARMUP_JOURS` vaut 1 : l'étape 4 est le dernier warm-up avant les Reels), option 2 comptes qui publient + 1 privé avec le lien, ou 3 qui publient et le lien en story à la une ; le lien ne va jamais dans un Reel ni en rafale dans les stories. Escalade : l'assistant dans #assistant-ia, le salon perso, puis **Gaëtan sur WhatsApp** : un bouton lien « 💬 Écrire à Gaëtan (WhatsApp) » (`WHATSAPP_GAETAN_URL`) est posé sous l'accueil du salon perso et sous chaque étape du parcours.

**Salons persos réservés aux nouveaux (26/09)** : « enlève tous les salons des clippeurs sous gestion de Jonas, ils comprennent rien et ça se mélange avec l'ancien système ». `roster.json` porte `sans_salon` (Thia, Caroline, Rianah, Ckycia, Hasina, Lilian, Romaric, Lucas, Josué, Tara, Yves, Clarisse) : au démarrage, leur salon perso est **supprimé une seule fois** (`DONNEES/roster_salons_supprimes.json`), leur `salon_id` retiré du registre, leur parcours oublié ; `!salons-equipe` sans liste, l'onboarding du roster et `!creatrice` ne leur en recréent jamais (une liste explicite dans `!salons-equipe` force). Leurs visites et bilans repartent là où ils allaient avant (MP ou salon du manager). **Textes du salon perso raccourcis** (« hyper long, trop d'informations ») : accueil en une ligne, message des comptes en 3 blocs et une règle, étapes en 5 lignes, Drive sans aperçu. **`!relance-telegram [jours] [min=4]`** : les meilleurs candidats du Google Form des N derniers jours (score sur 8, majeurs, pas déjà sur Discord ni dans l'équipe) avec liens t.me et wa.me et message prêt à coller, dans un onglet du classeur et au salon admin — un bot Telegram ne pouvant écrire qu'à qui lui a déjà parlé, l'envoi reste humain.

## 👥 Le roster actif : la liste de Gaëtan fait foi (26/09, `roster.py`, `roster.json`)

Gaëtan a donné sa liste de clippers par créatrice (« comme ça tu peux mettre à jour le compteur ») : elle vit dans `roster.json` à côté du bot (édité par Claude ou par Gaëtan) et dans `DONNEES/roster.json` (écrit par `!roster`), le plus récent des deux gagne. Elle sert au salon-compteur **« 🎬 Clippers : N »** (plus de comptage par rôle, remis à zéro à chaque renommage de rôle), aux groupes de **#jonas-stats**, à `!salons-equipe` sans liste, à `!actifs`. Commandes : `!roster` (afficher), `!roster Sophie: Thia, Rianah ; Chloé: Hasina` (remplacer), `!roster sortie Prénom` (un départ), `!roster nouveau Prénom` (un signé sans créatrice, compté). `!creatrice` ajoute au roster, `!sortie` en retire. `alias` dans le fichier : le surnom que Gaëtan emploie (« Pepita ») pour un pseudo Discord différent (« Ricado »), compris par toutes les commandes. **Au démarrage** : les `sortis` du fichier sont nettoyés une seule fois (fiche → `sortis.json`, parcours candidat « sorti », comptes du classeur rendus, salon perso renommé `sorti-prenom`, jamais supprimé) ; un prénom du roster présent sur le serveur mais sans créatrice au registre est **onboardé tout seul** comme par `!salons-equipe` ; une créatrice du registre différente du roster est corrigée (Lucas mis sous « pepita » par un `!creatrice` inversé) ; un membre qui porte le rôle Clippeur sans être au roster est listé « à vérifier », jamais compté.

**Un nouveau = 3 comptes neufs et leurs e-mails, dans le POD le plus bas (26/09, Gaëtan)** : `onboarding.disponibles` prend les 3 lignes « à créer » libres avec e-mail d'une même colonne POD (le POD le plus bas où la créatrice en a 3), plus jamais un compte déjà créé rendu par un ancien (ceux-là partent « à mettre Metricool »). `!creatrice @x Prénom` (ou `!creatrice Prénom @x`, l'ordre inversé est compris) : pseudo Discord **« Prénom - Créatrice »**, rôle Clippeur garanti même sans grille, rôle de la créatrice, roster, salon perso, comptes, parcours à l'étape 1 ; **plus aucun manager n'est ajouté aux nouveaux salons persos** (`SALON_PERSO_MANAGERS=1` pour revenir). **Numéro de téléphone (26/09, décision de Gaëtan)** : un SMS de l'agence coûte trop cher, le clipper met **le sien** quand Instagram le demande et reçoit le SMS ; un numéro = ses 3 comptes, jamais un numéro déjà lié à d'autres comptes (ban en chaîne) ; sa vraie date de naissance ; le manager est informé une fois par jour. **Selfie vidéo** demandé par Instagram : le clipper le fait lui-même. **Escalade** : un problème que la base ne couvre pas (compte bloqué, numéro refusé) renvoie vers Gaëtan sur WhatsApp (`WHATSAPP_GAETAN_URL`) en se présentant, avec le problème en une phrase et une capture ; le bot n'invente plus de « compte prêt à l'emploi ». Le message du matin prend le prénom du salon dans le registre (plus de « Bonjour Maxence ») et ne part jamais hors de la fenêtre 8 h-11 h UTC. Le parcours se recale sur le **nombre de comptes créés** (un compte créé = étape 2, pas le warm-up) avec une correction unique depuis l'étape 4.

**`!pipeline` et `!fiche` (26/09, « 100 % va venir du formulaire »)** : plus de webhooks, de numéros liés ni de portes d'entrée. `!pipeline` lit le classeur des candidatures (Google Form + site, onglets `SHEET_CANDIDATURES_FORM_ONGLET` et `SHEET_CANDIDATURES_ONGLET`, cache 10 min) : total, 7 jours, hier, par source ; puis les parcours des gens **encore sur le serveur** (les partis ne sont plus comptés), les signés présents, le roster actif, et les actions : tests à reviewer, validés sans J'ACCEPTE, signés sans créatrice. `!fiche @x` ajoute la **candidature du classeur** (retrouvée par les 8 derniers chiffres du numéro, sinon par prénom) : pays, âge, métier, téléphones, expérience, montage, Reels et heures par jour, vidéo qui a marché, connaissance des bans, motivation, niche, source de l'annonce, et une **note indicative sur 8** (iPhone, ≥ 2 téléphones, expérience, monte déjà, ≥ 2 Reels/j, ≥ 3 h/j, connaît les bans, majeur) pour juger avant d'attribuer.

## ☀️ Un seul message du matin, et un parcours recalé sur le classeur (26/09, `matin.py`)

Relecture de sept salons persos le 26/09 : trop de messages, des contradictions, des commandes non comprises. Ce qui change. **Un seul message du matin par clipper** : la ligne de visites (`paie_clics`), la ligne des Reels d'hier (`etats_comptes`) et le compteur de warm-up (`parcours`) sont **déposés** dans `matin.py` (`deposer(salon_id, cle, texte)`) et assemblés en un message entre `MATIN_HEURE_MIN` (8 h UTC) et `MATIN_HEURE_MAX` (10 h UTC). **Livraison des comptes idempotente** : un clipper qui a reçu ses comptes depuis moins de 24 h ne les reçoit pas une deuxième fois (sauf `!onboarding` explicite) ; c'est ce qui doublait le message quand `!salons-equipe` et la télécommande du classeur se suivaient. **Parcours recalé sur le classeur** : `!salons-equipe` démarre chaque clipper à l'étape que ses lignes du classeur impliquent (à créer → compte 1, WARMUP → warm-up, GOOD → routine) et chaque passage Apify appelle `parcours.reconcilier` pour avancer un parcours en retard sur la réalité (jamais de recul). **Assistant dans le salon perso** : 3 phrases ou 3 puces maximum, une seule ligne « 👉 Prochaine étape : … » à la fin, plus d'étiquette de source, plus de « [Contexte…] » recopié, plus de quota de questions (le quota reste en MP et dans les salons publics). `code`, `! code`, `Code` seuls valent `!code`. **Mur téléphone** : si Instagram réclame un numéro, le bot dit stop, prend la capture et prévient le manager (une alerte par jour et par clipper, `alertes_tel` dans les compteurs) ; il n'invente plus de bouton « Envoyer un code ». **Candidatures web** : écrites à la première ligne vide sous l'en-tête de l'onglet « Candidatures bot » (les Tables Google Sheets ont 1 000 lignes vides qui cachaient les nouvelles lignes en 1003+), et le manager + l'admin sont prévenus à chaque candidature.

## 📊 Rapport GAML du manager : #jonas-stats (24/09, `rapport_stats.py`)

Chaque matin, une fois les relevés de la veille faits, le bot poste dans le salon du manager (nom et groupes dans `rapport_jonas.json`, salon créé par le bot s'il manque : privé, rôle Manager et admins) les visiteurs GAML de la veille des clippers suivis, par créatrice : visiteurs hors robots, dont francophones payables, cumul 7 jours, robots exclus, clippers sans lien signalés. Un lien est rattaché à un clipper quand sa note contient le prénom et que son nom commence par la créatrice (« Rianah Metricool » et « Rianah Metricool 2 » comptent pour Rianah sous Sophie) ; ces liens sont relevés même sans membre Discord. `!stats-jonas [AAAA-MM-JJ]` (26/09 : rapport réduit à un chiffre par clipper, rangé par créatrice, et deux totaux : hier et 7 jours) relance le rapport.

**Roster actif et salon-compteur « 🎬 Clippers : N » (26/09).** `groupes` dans `rapport_jonas.json` est la liste active des clippers par créatrice, donnée par Gaëtan (26/09 : Sophie 5, Chloé 6, Sarah 4 ; Laure, Quentin et Meiji sortis) et datée par `mis_a_jour`. Le roster vivant (`rapport_stats.groupes_actifs`) y ajoute les fiches du registre qui ont reçu une créatrice (`!creatrice`) après cette date et en retire les `!sortie` faites après cette date ; il sert au rapport du matin et au salon-compteur, qui ne compte plus les membres d'un rôle Discord (le renommage Rookie → Clippeur l'avait remis à zéro, et les anciens n'avaient jamais reçu le rôle). `!actifs` affiche les prénoms comptés par créatrice ; pour changer la liste de fond, éditer le fichier et redéployer. Une sortie doit passer par `!sortie` (comptes rendus au classeur, salon perso fermé, rôles retirés) : virer quelqu'un en dehors du bot ne change ni le compteur ni le classeur.

## ✍️ Plus d'étape contrat dans le tunnel (23/09)

Décision de Gaëtan : « on ne va pas embêter les Malgaches avec ça ». Tout test validé, grille France comme International (et grille indéterminée, France par défaut), reçoit les **conditions en MP** et répond **J'ACCEPTE** ; le rôle Team de sa grille s'ouvre à l'acceptation (`conditions_grille` dans le pipeline), les relances 24/48 h s'appliquent à tous. Un e-mail envoyé en MP est simplement enregistré. **29/09** : le code DocuSeal (`!contrat`, création et sondage des contrats, relances de signature, retentatives) et `CONTRAT_ACTIVER` sont retirés, voir « Retiré ».

## 🌐 Le site du tunnel candidat (23/09)

**Présentation et rémunération (23/09, après-midi)** : le formulaire reprend l'annonce de Gaëtan (« Recherche Clippeur Reels 🎥 Instagram »), 100 % Instagram (création de comptes puis publication de Reels), et annonce noir sur blanc le nouveau modèle : **0,05 $ par visite réelle sur le lien en bio Instagram** (visiteurs depuis la France, hors robots), payé le 5 et le 20, avec les repères 1 000 visites = 50 $ et 5 000 visites = 250 $. La présentation est une liste de paragraphes dans `questions_candidature.json` (`intro`), `**gras**` et `---` acceptés. La question « Es-tu OK avec ce modèle ? » décrit le même modèle, et les conditions Team International envoyées après le test disent la même chose (plus de fixe ni de 0,50 € par abonné pour les nouveaux). : formulaire, connexion Discord, quiz

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
| Digest : « Signés sans créatrice » à J+66, « tests expirés », « candidatures sans Discord », « avertissement technique » répétés tous les jours | En semaine : les signés récents (≤ 14 j) hors équipe ; le lundi : les anciens et les compteurs de fond. Un avertissement technique n'apparaît qu'une fois |
| Relance du soir « N tests attendent ton OUI/NON » le jour même du rendu | Seulement pour les tests qui attendent depuis 24 h ou plus |
| Sauvegarde hebdo : dix fichiers JSON avec aperçu | Une archive zip, une ligne |

Ce qui reste immédiat : un test rendu (avec ses fichiers), un candidat qui accepte les conditions,
une panne. Pour vider le salon admin du quotidien (rapport MARKETING, digest, alertes cadence), pose
`CANAL_MANAGER_ID` : ils partent chez le manager et l'admin ne garde que l'hebdo du lundi.

## ⚠️ Compteurs remis à zéro ? (persistance des données)

Vécu le 17/07 : « Déjà payés : 0 € ». Cause : les données
(`compteur_verse.json`, `paiements.jsonl`, `faq_apprise.md`…) vivent dans `DONNEES_DIR`
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
épinglé.

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

## Retiré le 29/09/2026 (élagage)

Décision de Gaëtan du 28/09 : élaguer le bot des fonctionnalités mortes. Chaque ligne dit ce qui a disparu et par quoi c'est remplacé.

- **Inputs clippers** (`inputs_clippers.py`, `historique_inputs.gs`, `!inputs`, `!comptes`, `!primes`, `!subs`, `!hebdo`, boucle Apify quotidienne, bilans aux clippers, rapport MARKETING du manager, hebdo du lundi, fichiers `inputs_clippers.json` et `subs.json`) : éteints le 27/09 (« c'est l'ancien système »), retirés. Remplacés par le scan quotidien du classeur (`etats_comptes.py` : états, followers, Reels d'hier dans le message du matin), la paie au clic (`paie_clics.py`), le rapport GAML du manager (`rapport_stats.py`) et le tableau de bord du lundi (`tableau_bord.py`). L'alerte Telegram (acceptation, sortie d'équipe, copie du digest) vit dans `telegram.py`. Variables Railway devenues inutiles : `INPUTS_CLIPPERS`, `SHEET_CSV_URL`, `SHEET_CSV_FB_URL`, `SHEET_ETATS_MORTS`, `SHEET_HISTORIQUE_URL`, `SHEET_HISTORIQUE_SECRET`, `APIFY_ACTOR_FB`, `FB_POSTS_MAX`, `CADENCE_REELS_MIN`, `NOUVEAU_JOURS`, `OBJECTIF_COMPTES_IG`, `TOP_CREATRICES`, `STRUCTURE_IG_MIN`, `STRUCTURE_FB_MIN`, `STRUCTURE_PRIVE_MIN`, `PRIME_JOURS_MIN`, `PRIME_CLIPPER_EUR`, `MANAGER_PAR_CLIPPER_EUR`, `MANAGER_BONUS_EQUIPE_EUR`, `COMMISSION_CLIPPER_EUR`, `COMMISSION_MANAGER_EUR`, `MANAGER_PRENOM`, `SUBS_MIN_PREMIER_MOIS`, `ACTIF_TAUX_MIN`, `HEURE_RAPPORT_INPUTS`, `RAPPORT_CLIPPER`, `SALONS_RESERVE`, `INPUTS_EXCLURE` (`APIFY_TOKEN` et `APIFY_ACTOR_IG` restent : `etats_comptes.py` s'en sert ; `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_QUOTIDIEN` restent : `telegram.py`).
- **DocuSeal — contrats signés** (`docuseal_requete`, `creer_contrat_docuseal`, `!contrat`, sondage des signatures et auto-onboarding à la signature dans `boucle_pipeline`, relances « signe ton contrat » 24 h / 48 h / J+7 / expiration J+14, retentatives après échec, lignes « contrats » du digest et de `!pipeline`, envoi du contrat à la réception de l'e-mail) : sans contrat depuis le 23/09 (`CONTRAT_ACTIVER=0`, « on ne va pas embêter les Malgaches avec ça »), retirés. Remplacés par les conditions en MP et le J'ACCEPTE (case cochée sur le site, bouton ✅ ou mot en MP, `acceptation.py`, 27/09). Variables Railway devenues inutiles : `DOCUSEAL_API_KEY`, `DOCUSEAL_TEMPLATE_ID`, `DOCUSEAL_URL`, `DOCUSEAL_EMAIL_AGENCE`, `DOCUSEAL_CONTRESIGNATURE`, `DOCUSEAL_ONBOARDING_AUTO`, `CONTRAT_ACTIVER`.
- **Rappel de /bump Disboard** (`detecter_bump`, `boucle_bump`, `!bumps`, classement mensuel, fichier `bump.json`, `CANAL_BUMP_ID`, `DISBOARD_ID`) : le salon #bump se supprime depuis le 14/09 et le module était « éteint par décision » (variable vide), retiré. Pas de remplacement : le serveur est fermé, il ne se promeut plus sur Disboard. Variable Railway devenue inutile : `CANAL_BUMP_ID`.
- **Annonce et purge internationales** (`!annonce-int [envoyer]`, `!purge-int [appliquer] [tout]`, clé `annonce_lancement` du pipeline) : `!purge-int` était neutralisée tant que `PAUSE_INT` vaut 0 (défaut, recrutement ouvert depuis le 08/09) et `!annonce-int` était l'annonce unique du lancement du 08/09, sans objet depuis que le serveur est fermé (14/09) et que tout arrive par le formulaire du site. Retirées. `PAUSE_INT` et `PURGE_INT_EXEMPTS` restent : la pause du quiz international et `!purge-candidats` s'en servent.
- **`!invites`** (classement des invitations trackées) : derrière `ACTIVER_V2` (vide par défaut) et sans usage depuis que le parrainage passe par `!parrain @lui` (`parrainage.py`, 28/09). Retirée. Le tracking des invitations à l'arrivée (`cacher_invites`, `trouver_invitation`, `invites.json`) reste : il sert à l'accueil, aux portes d'entrée (`SOURCES_INVITES`) et aux invitations personnelles `!inviter`.
- **`ASSISTANT_GLOBAL`** (l'ancien salon assistant `CANAL_BOT_ID` et le forum `FORUM_BOT_ID` comme lieux de réponse, mention servie à tout le monde) : à 0 par défaut depuis le 27/09 (« plus d'assistant global »), retiré. L'assistant vit dans le salon perso de chaque clipper et en MP ; une mention hors salon perso n'est servie qu'au staff. `CANAL_BOT_ID` reste le repli du salon admin, `CANAL_ASSISTANT_ID` reste protégé par `!archiver` ; la section « Canal propre + tri automatique par sujet (salon Forum) » du README est partie avec. Variables Railway devenues inutiles : `ASSISTANT_GLOBAL`, `FORUM_BOT_ID`.
