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

## Dépannage

| Symptôme | Cause probable | Fix |
|---|---|---|
| Le dashboard refuse `http://localhost:8788/callback` | Politique redirect URI | Enregistre `https://localhost:8788/callback` et remplace `http` par `https` dans `REDIRECT` de `auth.py` (ignore l'avertissement TLS) |
| `invalid_client` à l'échange | Client ID / Secret erroné | Revérifie les deux, relance `auth.py` |
| Les outils `whoop_*` n'apparaissent pas | Session pas rechargée | Redémarre Claude Code |
| `claude mcp list` : « Failed to connect » | `uv` pas trouvé par Claude Code | Utilise le chemin absolu de `uv` (`which uv`) dans la commande `mcp add` |
| Erreur 401 persistante | Refresh token invalidé | Relance `auth.py` pour ré-autoriser |
| Réponses vides | Abonnement WHOOP inactif | L'API ne renvoie des données que pour un membre actif |
