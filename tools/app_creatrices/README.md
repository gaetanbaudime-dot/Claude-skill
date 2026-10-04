# App créatrices G&M

Petite application web mobile (PWA) pour les créatrices : un lien secret par créatrice, à ajouter sur l'écran d'accueil du téléphone. Trois onglets en bas :

- **Drive** : quatre tuiles (Reels, Photos, Feed MYM, Scripts MYM) qui ouvrent le bon dossier du moment dans l'application Google Drive de la créatrice. Reels = le dossier de la semaine en cours, Photos = le dossier du mois, Feed MYM = le dossier « Feed MYM <Mois> <Année> », Scripts MYM = le dossier du mois s'il existe. Un dossier pas encore créé fait reculer au plus récent existant : la tuile ouvre toujours quelque chose d'utile. Les dossiers ne sont jamais créés ici, c'est le script Drive de l'agence qui le fait.
- **Reels** : le duplicateur de Reels, écran « Bientôt » pour l'instant.
- **Stats** : Hier, 7J, 30J, M (mois en cours), M-1 (mois précédent). Revenus nets OnlyFans + MYM en euros (les dollars OnlyFans sont convertis au taux BCE du jour via Frankfurter, repli 0,88), nouveaux abonnés par jour (jamais de cumul), comparaison avec la période précédente, deux graphiques (revenus par jour empilés, nouveaux abonnés par jour). Source : le classeur Data G&M, onglet de la créatrice.

## Pile

Next.js 14 (App Router), Tailwind, Recharts, TypeScript. Déployée sur Vercel depuis ce dépôt avec `tools/app_creatrices` comme répertoire racine ; `vercel.json` ignore les commits qui ne touchent pas ce dossier.

## Variables d'environnement (Vercel, jamais dans le dépôt)

| Variable | Contenu |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | le JSON du compte de service de l'agence (lecture seule Sheets + Drive) |
| `DATA_GM_ID` | l'identifiant du classeur Data G&M |
| `CREATRICES_JSON` | un objet `{ "<jeton>": { "prenom", "onglet", "racine", "reels", "photos", "feed", "scripts" } }` par créatrice, le jeton étant un secret aléatoire de 12 à 64 caractères (`[A-Za-z0-9_-]`) |

`.env.local` sert au test en local et reste ignoré par Git. Les jetons et identifiants de dossiers des six créatrices sont conservés hors dépôt, dans le scratchpad de la session et sur Vercel.

## Sécurité

- Aucun mot de passe : le jeton dans l'URL est la clé. Un jeton inconnu renvoie 404 sans détail.
- `X-Robots-Tag: noindex`, `Referrer-Policy: no-referrer` : le lien ne fuit pas dans les en-têtes vers Drive.
- Le compte de service n'a que des droits de lecture.
- L'API ne renvoie que des chiffres déjà convertis et des identifiants de dossiers Drive que la créatrice peut ouvrir.

## Routes

- `/c/<jeton>` : l'application.
- `/api/c/<jeton>/stats?periode=hier|j7|j30|m|m1` : chiffres de la période (JSON).
- `/api/c/<jeton>/drive` : libellés des dossiers visés par les quatre tuiles.
- `/api/c/<jeton>/drive/<reels|photos|feed|scripts>` : redirection 302 vers le dossier Drive du moment.

## Ajouter une créatrice

1. Ajouter son onglet dans Data G&M (mêmes colonnes que les autres : A date, B abonnés OF, C CA OF en $, E abonnés MYM, F CA MYM en €).
2. Partager son dossier `[C] Créatrices / <Prénom>` avec le compte de service (lecture).
3. Ajouter une entrée dans `CREATRICES_JSON` sur Vercel avec un nouveau jeton aléatoire et les identifiants de ses dossiers Reels / Photos / Feed MYM / Script.
4. Redéployer, puis lui envoyer `https://<domaine>/c/<jeton>`.

## En local

```
npm install
cp .env.local.exemple .env.local   # puis remplir les trois variables
npm run dev
```
