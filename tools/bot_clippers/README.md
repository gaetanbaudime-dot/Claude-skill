# Bot FAQ Clippers (Discord + Claude)

Un bot **Discord** qui répond aux questions des clippers **uniquement à partir de `connaissances.md`**
(Kit Clipper v2 + stratégie marketing officielle, Instagram + Facebook uniquement). S'il ne sait
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
