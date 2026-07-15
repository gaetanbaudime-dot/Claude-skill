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

## Distribution aux clippers

Rien à distribuer ! Ils sont déjà dans le serveur. Dis-leur juste : « pose tes questions dans #assistant ».
Pour retirer quelqu'un : retire-le du serveur Discord (ou du canal). Aucun code à gérer.

## Coût

Modèle par défaut **`claude-haiku-4-5`** (rapide, quasi gratuit). Coût API ≈ **1-2 €/mois** même à fort
volume. Le total est dominé par l'hébergement (~5 $/mois Railway). Total réaliste : **~5-7 $/mois**.
Pour des réponses plus fines : `MODELE=claude-opus-4-8` (~5x plus cher, reste sous ~10 €/mois).

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
