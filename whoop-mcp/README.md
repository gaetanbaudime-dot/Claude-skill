# WHOOP ↔ Claude Code

Connecte Claude Code à tes vraies données WHOOP via un petit serveur MCP local
(deux fichiers Python) qui parle à l'**API officielle WHOOP v2** en OAuth 2.0.
Tout reste sur ta machine : pas de service tiers, pas de scraping.

Une fois branché, tu demandes à Claude Code « quel est mon recovery et mon sommeil
des 7 derniers jours ? » et il lit tes données.

## Prérequis

- **macOS ou Linux** (Windows : via WSL).
- **Claude Code** installé (`claude --version`).
- **`uv`** (gestionnaire Python d'Astral) : `curl -LsSf https://astral.sh/uv/install.sh | sh`.
  Il gère Python et les dépendances tout seul.
- **Un compte WHOOP avec abonnement actif** — l'API ne renvoie des données que pour un membre actif.

## Installation

### 1. Créer une app développeur WHOOP

Sur [developer.whoop.com](https://developer.whoop.com), connecte-toi, crée une **Team**
si demandé, puis une **App** :

| Champ | Valeur |
|---|---|
| **Name** | ce que tu veux (ex. `Claude`) |
| **Redirect URI** | `http://localhost:8788/callback` (exactement ça) |
| **Scopes** | tout cocher : `read:recovery`, `read:cycles`, `read:sleep`, `read:workout`, `read:profile`, `read:body_measurement`, + **offline** |

Valide. WHOOP affiche un **Client ID** et un **Client Secret** — **le secret n'est montré
qu'une fois, copie-le tout de suite**. Ne le partage jamais, ne le versionne jamais.

### 2. Copier les fichiers dans un dossier sécurisé

```bash
mkdir -p ~/.whoop-mcp && chmod 700 ~/.whoop-mcp
cp whoop-mcp/server.py whoop-mcp/auth.py ~/.whoop-mcp/
```

### 3. S'authentifier (une seule fois)

```bash
uv run --python 3.11 --script ~/.whoop-mcp/auth.py
```

Colle ton **Client ID** puis ton **Client Secret** (saisie masquée, c'est normal).
Le navigateur s'ouvre sur l'écran de consentement WHOOP → clique **Allow**.
Le terminal affiche `OK : tokens sauvegardés...`.

### 4. Enregistrer le serveur dans Claude Code

```bash
claude mcp add whoop -s user -- uv run --python 3.11 --script ~/.whoop-mcp/server.py
claude mcp list   # doit afficher : whoop: ... - ✔ Connected
```

Puis **redémarre Claude Code** — les serveurs MCP ne sont chargés qu'au démarrage.

### 5. Tester

Dans Claude Code :

- « Quel est mon recovery et mon sommeil des 7 derniers jours ? »
- « Résume mon état WHOOP du jour. »
- « Montre-moi mes 5 dernières séances avec le strain. »

## Outils exposés

| Outil | Ce qu'il renvoie |
|---|---|
| `whoop_profile` | Prénom, nom, email, user id |
| `whoop_body_measurement` | Taille, poids, FC max |
| `whoop_recovery` | Score %, HRV, FC de repos, SpO2, température de peau |
| `whoop_sleep` | Performance %, durée par stade, fréquence respiratoire, efficacité |
| `whoop_cycles` | Strain du jour, FC moyenne/max, dépense (kJ) |
| `whoop_workouts` | Sport, strain, FC moyenne/max, zones, distance |
| `whoop_daily_summary` | Dernier cycle + dernière recovery + dernier sommeil |

Les outils de collection (`recovery`, `sleep`, `cycles`, `workouts`) acceptent
`start` / `end` en ISO-8601 et `max_records`.

## Sécurité

- Les tokens vivent dans `~/.whoop-mcp/credentials.json` en `chmod 600`, dossier en `700`.
- Le `Client Secret` reste sur ta machine et est saisi en masqué.
- L'access token dure ~1 h et se **rafraîchit tout seul** (refresh token rotatif).
- **Ne versionne jamais `credentials.json`.**

## Aller plus loin : entrepôt SQLite + requêtes + dashboard

Le serveur ci-dessus lit tes données **à la demande**. Pour donner à Claude tout ton
historique et des tendances longues sans saturer le contexte, trois fichiers en plus
(même connexion OAuth, mêmes `credentials.json`) :

| Fichier | Rôle |
|---|---|
| `sync.py` | Tire tout l'historique (recovery, sommeil, cycles, workouts) dans `~/.whoop-mcp/whoop.db`. Idempotent : 1er run = complet, runs suivants = fenêtre glissante de 60 j. |
| `dashboard.py` | Génère un dashboard HTML autonome (graphiques SVG, zéro dépendance) et l'ouvre dans le navigateur. |
| `launchd/com.whoop.sync.plist` | Sync quotidien automatique à 7 h 30 (macOS). |

Le serveur MCP (`server.py`) expose en plus **2 outils entrepôt** dès que `whoop.db` existe :

- `whoop_tables` — schéma des tables (à consulter avant une requête).
- `whoop_query` — SQL **lecture seule** (SELECT / WITH) sur tout l'historique, pour
  calculer n'importe quelle tendance ou corrélation. Ex. dans Claude Code :
  « corrèle le strain de la veille avec la recovery du lendemain sur 6 mois ».

### Mise en place

```bash
# 1. Copie les 3 nouveaux fichiers (en plus de server.py / auth.py)
cp whoop-mcp/sync.py whoop-mcp/dashboard.py ~/.whoop-mcp/

# 2. Premier sync : tire tout l'historique (peut prendre 1-2 min)
uv run --python 3.11 --script ~/.whoop-mcp/sync.py

# 3. Génère le dashboard (90 j par défaut, ou passe un nombre de jours)
uv run --python 3.11 --script ~/.whoop-mcp/dashboard.py 120

# 4. (macOS) Sync quotidien automatique
cp whoop-mcp/launchd/com.whoop.sync.plist ~/Library/LaunchAgents/
launchctl load  ~/Library/LaunchAgents/com.whoop.sync.plist
launchctl start com.whoop.sync        # test immédiat ; logs -> ~/.whoop-mcp/sync.log
```

Après le premier sync, **redémarre Claude Code** : `whoop_query` et `whoop_tables`
apparaîtront. Exemples de questions :

- « Quel est mon HRV moyen par jour de la semaine sur les 3 derniers mois ? »
- « Montre l'évolution de ma performance de sommeil sur 90 jours. »
- « Y a-t-il une corrélation entre mes jours de gros strain et une recovery basse le lendemain ? »

### Tables de `whoop.db`

`cycles` (strain, kJ, FC), `recovery` (score, HRV, FC repos, SpO2, temp. peau),
`sleep` (perf, efficacité, stades, fréquence respiratoire), `workouts` (sport, strain, distance).
Chaque table garde aussi la réponse brute de l'API dans une colonne `raw` (JSON).

## Dépannage

| Symptôme | Cause probable | Fix |
|---|---|---|
| Le dashboard refuse `http://localhost:8788/callback` | Politique redirect URI | Enregistre `https://localhost:8788/callback` et remplace `http` par `https` dans `REDIRECT` de `auth.py` (ignore l'avertissement TLS) |
| `invalid_client` à l'échange | Client ID / Secret erroné | Revérifie les deux, relance `auth.py` |
| Les outils `whoop_*` n'apparaissent pas | Session pas rechargée | Redémarre Claude Code |
| `claude mcp list` : « Failed to connect » | `uv` pas trouvé par Claude Code | Utilise le chemin absolu de `uv` (`which uv`) dans la commande `mcp add` |
| Erreur 401 persistante | Refresh token invalidé | Relance `auth.py` pour ré-autoriser |
| Réponses vides | Abonnement WHOOP inactif | L'API ne renvoie des données que pour un membre actif |
