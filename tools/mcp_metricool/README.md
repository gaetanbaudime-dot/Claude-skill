# Connecteur MCP Metricool

> [!tip] Verdict
> Ce serveur branche les 18 comptes Metricool de l'agence directement dans la conversation.
> Il répond en une question à **« est-ce que l'équipe publie ? »** — le chiffre AMONT qui
> manquait entre GAML (clics) et Infloww (abonnés + revenus).
> **Déploiement conseillé : Railway, en HTTP**, puis ajout de l'URL comme connecteur
> personnalisé sur claude.ai. L'URL contient un secret : elle ne se partage pas.

## Ce qu'il expose

| Outil | Question à laquelle il répond |
|---|---|
| `metricool_brands` | Quels comptes existent, et quels réseaux sont **réellement** branchés ? |
| `metricool_posts` | Qu'est-ce qui a marché sur le TikTok de Chloé 1 ce mois-ci ? |
| `metricool_summary` | Qui a posté cette semaine, combien, pour quelles vues — par créatrice ? |

Les trois sont en lecture seule : le serveur ne publie rien et ne modifie rien dans Metricool.

## Deux pièges déjà encaissés (à ne pas redécouvrir)

1. **Plusieurs marques Metricool pointent vers le même compte réseau.** Les 7 marques
   « Chloé » partagent **une seule chaîne YouTube** ; Maddie 1/2 et Sophie 1/3 aussi.
   Un résumé naïf comptait 2 997 posts / 1 942 451 vues là où la réalité est
   **1 565 posts / 1 479 133 vues** (44 couples marque×réseau → 34 comptes réels).
   `metricool_summary` dédoublonne par `(réseau, identifiant du compte)` et liste les
   comptes partagés en bas de son rapport. Le détail par marque, lui, affiche la valeur
   sur chaque ligne concernée — d'où des lignes qui se ressemblent, ce n'est pas un bug.
2. **Instagram est quasi absent d'ici, et c'est normal.** L'agence a **deux machines de
   distribution** : les **clippers** travaillent **Facebook + Instagram** (suivis par GAML,
   Infloww et le bot Discord), et Metricool couvre **l'autre** — **Facebook, TikTok, YouTube**,
   comptes tenus par Rianah (`- R`) et Julien (`- J`). Une seule marque sur 18 a Instagram
   branché (`Maddie 2 - R`). Ne jamais lire ça comme une erreur de configuration, ni conclure
   que « Metricool ne voit pas le canal qui rapporte » : ce n'est pas son périmètre.

## Variables d'environnement

| Variable | Obligatoire | Rôle |
|---|---|---|
| `METRICOOL_TOKEN` | **oui** | Jeton d'API (Metricool → paramètres → API). **Jamais dans le code, jamais commité.** |
| `MCP_TRANSPORT` | non | `http` pour le mode distant. Vide/absent = `stdio` (local). |
| `MCP_PATH` | en HTTP, **oui** | Segment secret de l'URL — voir sécurité ci-dessous. Défaut `mcp`. |
| `PORT` | non | Posé automatiquement par Railway. |
| `METRICOOL_USER_ID` | non | Porte de sortie si l'API se met à exiger le `userId` (valeur connue : `2302746`). |

## Sécurité : pourquoi l'URL est un mot de passe

claude.ai ne propose **pas** de champ « en-tête personnalisé » pour un connecteur
personnalisé : un serveur MCP en HTTP sans OAuth est donc joignable par quiconque
connaît son URL. La parade retenue est de rendre l'URL indevinable :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

On pose le résultat dans `MCP_PATH`. L'URL du connecteur devient
`https://<projet>.up.railway.app/<ce-secret>/mcp`. Conséquences à assumer :

- cette URL ne se colle **ni dans Discord, ni dans le vault, ni dans un commit** ;
- pour la révoquer, il suffit de changer `MCP_PATH` dans Railway (redéploiement auto) ;
- si le jeton Metricool fuite, on le régénère dans Metricool et on met à jour la variable.

Les réponses de l'outil peuvent contenir les **identifiants réels** des comptes
(handles TikTok, IDs de pages Facebook et de chaînes YouTube). C'est utile en conversation,
mais ça ne descend jamais dans le second cerveau : le vault ne connaît que les noms de scène.

## Déploiement Railway (mode distant, pour claude.ai)

1. Railway → **New Project** → *Deploy from GitHub repo* → ce dépôt.
2. **Settings → Root Directory** : `tools/mcp_metricool`
   (sinon Railway lit le `Procfile` du bot Discord à la racine).
3. **Variables** :
   - `METRICOOL_TOKEN` = le jeton
   - `MCP_TRANSPORT` = `http`
   - `MCP_PATH` = le secret généré plus haut
4. **Settings → Networking → Generate Domain** (Railway expose `PORT` tout seul).
5. Sur claude.ai → **Paramètres → Connecteurs → Ajouter un connecteur personnalisé**,
   coller `https://<domaine>/<MCP_PATH>/mcp`, sans authentification.

Le serveur tourne en **streamable-http, stateless, réponses JSON** : pas de session à
garder chaude, un redémarrage Railway ne casse aucune conversation en cours.

## Usage local (stdio, dans Claude Code)

```bash
pip install -r requirements.txt
export METRICOOL_TOKEN="…"
python metricool_mcp.py            # stdio, à déclarer dans .mcp.json
```

## Vérifier que tout marche

```bash
python metricool_mcp.py --selftest            # jeton + un appel réel + contrôle de dédoublonnage
python metricool_mcp.py --selftest --complet  # + le résumé 7 jours de tous les comptes
```

`--selftest` fonctionne **sans le SDK MCP installé** : il appelle les implémentations
directement. C'est le premier réflexe quand le connecteur répond mal — il sépare
« problème de jeton / d'API Metricool » de « problème de transport MCP ».

## Notes d'API (reverse-engineering du 12/08/2026)

- Base `https://app.metricool.com/api`, authentification par en-tête **`X-Mc-Auth`**.
- Dates au format **`yyyy-MM-dd'T'HH:mm:ss`** (le `AAAA-MM-JJ` seul renvoie un 400).
- `GET /admin/simpleProfiles` → les marques + les identifiants de chaque réseau connecté.
- `GET /v2/analytics/posts/{réseau}?blogId=&userId=&from=&to=` → les publications.
- Chaque réseau nomme ses métriques différemment (`viewCount` chez TikTok, `views` chez
  YouTube, `videoViews`/`impressions` chez Facebook) : `_metriques()` les ramène à un
  socle commun vues/likes/commentaires/partages.
- Le SDK MCP a renommé sa classe entre la 1.x (`FastMCP`) et la 2.x (`MCPServer`) :
  le code gère les deux, un `pip install mcp` récent ne casse donc pas le démarrage.
