# Bot FAQ Clippers (Telegram + Claude)

Un bot Telegram qui répond aux questions des clippers **uniquement à partir du Kit Clipper v2**
(`connaissances.md`). S'il ne sait pas → il renvoie vers le canal Discord. Il n'invente jamais.
Accès protégé par un code. Chaque question est journalisée (mesure du besoin réel).

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
cp .env.example .env        # puis remplis les 3 valeurs dans .env
pip install -r requirements.txt
python3 bot.py
```
Le bot tourne tant que le terminal est ouvert. Envoie-lui `/start` sur Telegram,
puis le code d'accès, puis une question test (« combien de comptes je crée par jour ? »).

### 4. Le faire tourner 24 h/24 (plus tard, quand validé)
Le plus simple : **Railway.app** (~5 $/mois) — nouveau projet → Deploy from repo →
variables d'environnement = le contenu de ton `.env` → start command `python3 tools/bot_clippers/bot.py`.
Alternative : n'importe quel petit VPS avec `nohup python3 bot.py &`.

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
