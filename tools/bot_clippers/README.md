# Bot FAQ Clippers (Telegram + Claude)

Un bot Telegram qui répond aux questions des clippers **uniquement à partir de `connaissances.md`**
(Kit Clipper v2 + stratégie marketing officielle, Instagram + Facebook uniquement). S'il ne sait
pas → il renvoie vers le canal Discord. Il n'invente jamais. Réponses courtes, niveau collège.
Accès protégé par un code. Chaque question est journalisée (mesure du besoin réel).

## Ce que les clippers peuvent envoyer

- **Du texte** : leur question, en une phrase.
- **Des photos / captures d'écran** (ex. un message de blocage Instagram) : le bot lit l'image et répond.
- **Des vocaux** : pas encore — le bot demande gentiment d'écrire la question. (L'API Claude ne
  transcrit pas l'audio ; ajoutable plus tard avec un service de transcription si le besoin est réel.)

## Le lien à partager sur Discord

Une fois le bot créé chez @BotFather, son lien est **`t.me/<nom_du_bot>`** (ex. `t.me/ltp_assistant_bot`).
Ce lien ne change JAMAIS, même si tu redémarres, redéploies ou modifies le bot — épingle-le dans
Discord avec le code d'accès et c'est réglé.

## L'améliorer avec le temps (sans toucher au code)

- **Depuis ton téléphone** : `/apprendre La question ? | La réponse.` ajoute une entrée à la FAQ
  vivante — le bot l'utilise **immédiatement** (les connaissances se rechargent toutes seules).
- **`/stats`** : volume de questions, % hors kit, nombre de clippers autorisés.
- **Depuis Claude Code** : demande-moi de mettre à jour `connaissances.md` (il est versionné dans
  le repo) — à chaque évolution du kit ou du SOP, je le mets à jour en même temps.
- **Il s'améliore tout seul ?** Presque : chaque question hors kit est marquée `escalade` dans le
  journal. Ce journal me sert à enrichir la base à chaque session. Le bot n'écrit jamais lui-même
  dans sa base sans validation humaine — c'est voulu (sinon une erreur inventée deviendrait une règle).

## Ce qu'il te reste à faire (~15 minutes, une seule fois)

### 1. Créer le bot Telegram (5 min)
1. Dans Telegram, ouvre **@BotFather** → envoie `/newbot`.
2. Donne-lui un nom (ex. « LTP Assistant ») et un identifiant (ex. `ltp_assistant_bot`).
3. BotFather te donne un **token** (`123456:ABC-DEF...`) → c'est `TELEGRAM_TOKEN`.
4. Optionnel : `/setjoingroups` → Disable (le bot ne répond qu'en privé).

### 2. Créer la clé API Claude (5 min)
1. Va sur **console.anthropic.com** → crée un compte (ou connecte-toi).
2. Ajoute un moyen de paiement (Billing) et mets une **limite de dépense** (ex. 25 $/mois).
3. API Keys → **Create Key** → copie la clé (`sk-ant-...`) → c'est `ANTHROPIC_API_KEY`.

### 3. Configurer et lancer (5 min)
```bash
cd tools/bot_clippers
cp .env.example .env        # puis remplis les 4 valeurs dans .env (dont ADMIN_IDS = ton id Telegram)
pip install -r requirements.txt
python3 bot.py
```
Le bot tourne tant que le terminal est ouvert. Envoie-lui `/start` sur Telegram,
puis le code d'accès, puis une question test (« combien de comptes je crée par jour ? »).

### 4. Le faire tourner 24 h/24 sur un serveur (recommandé — tu voyages)
Le bot doit rester allumé quand ton Mac est éteint. Le plus simple : **Railway.app** (~5 $/mois).

1. Va sur **railway.app** → connecte ton compte GitHub → **New Project → Deploy from GitHub repo** → choisis `gaetanbaudime-dot/Claude-skill`.
2. **Settings → Root Directory** → mets `tools/bot_clippers` (le `Procfile` et `requirements.txt` y sont, Railway détecte tout seul).
3. **Variables** → ajoute les mêmes qu'en local : `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY`, `CODE_ACCES`, `ADMIN_IDS`. Ajoute aussi **`DONNEES_DIR=/data`**.
4. **Volume** (pour que le journal et la FAQ apprise survivent aux redémarrages) : **New → Volume**, monté sur **`/data`**. C'est ce que pointe `DONNEES_DIR`.
5. Déploie. Les logs doivent afficher « Bot démarré ». Envoie `/start` à ton bot sur Telegram pour vérifier.

> Sans le volume (étape 4), le bot marche quand même, mais il oublie qui est autorisé et son journal à chaque redéploiement. Le volume est ce qui rend la mesure (déclencheur de septembre) fiable.

**Pour tester d'abord sur ton Mac** (facultatif, avant de déployer) : suis l'étape 3 ci-dessus, `python3 bot.py`. Ça tourne tant que le terminal est ouvert — bien pour valider en 5 min, pas pour la production.

## Distribution aux clippers

Donne-leur : le @ du bot + le code d'accès (`CODE_ACCES`). C'est tout.
Pour révoquer quelqu'un : supprime sa ligne dans `donnees/autorises.json` et change le code.

## Coût (ordre de grandeur)

Avec le modèle par défaut (`claude-opus-4-8`) et le cache activé : **~1 centime par question**
(≈ 5-10 €/mois pour 500-1000 questions). Pour diviser par ~5, mets `MODELE=claude-haiku-4-5`
dans `.env` (réponses un peu moins fines — à tester sur tes questions réelles).

## Mettre à jour les connaissances

1. Modifie `connaissances.md` (ou demande à Claude Code de le faire — il est versionné dans le repo).
2. Ajoute les questions récurrentes dans la section « FAQ vivante » du même fichier.
3. Redémarre le bot. C'est tout.

## Mesurer (le déclencheur de septembre)

Chaque question est ajoutée à `donnees/journal_questions.jsonl` avec un marqueur `escalade`
(vrai = la réponse n'était pas dans le kit). À la rentrée :
```bash
wc -l donnees/journal_questions.jsonl                      # volume total
grep -c '"escalade": true' donnees/journal_questions.jsonl # trous du kit à combler
```
Beaucoup d'escalades = enrichir `connaissances.md`. Peu de questions = le kit v2 suffit.

## Sécurité (règles gravées dans le code)

- La base de connaissances = **le kit v2 uniquement** (que les clippers ont déjà en PDF → aucune exposition nouvelle). Jamais le playbook complet, jamais d'identités de créatrices, jamais de chiffres de l'agence.
- Le bot refuse : questions hors kit, demandes d'ignorer ses règles, tactiques dangereuses pour les comptes.
- `.env` (les clés) et `donnees/` (journal + accès) ne sont **jamais commités** (exclus par le .gitignore).
- Limite : 30 questions/jour/personne (réglable via `QUESTIONS_MAX_PAR_JOUR`).
