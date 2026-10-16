# Reels natifs dans les deux apps

`@gm/reels` remplace l’iframe par une interface React partagée. Chaque `App.tsx` possède son `useReelsJob` : changer d’onglet conserve le montage et les fichiers disponibles. Le panneau reste dans le défilement de la page, au-dessus de la navigation existante.

Le moteur provient de TikFusion PR15 ; voir [UPSTREAM.md](UPSTREAM.md). Les presets natifs et les paramètres HD restent inchangés. Le navigateur utilise les routes privées de son app (`/api/k/[token]/reels/*` ou `/api/c/[token]/reels/*`), protégées par les gardes existantes. Le proxy transmet uniquement les opérations et champs autorisés vers le Duplicateur, sans cookie, en-tête d’authentification ni jeton d’app. Les transferts vidéo utilisent les URL temporaires fournies par le service existant.

## Vérification locale sans rendu payant

Depuis chacune des deux apps, exécuter `npm ci --ignore-scripts --no-audit --no-fund` puis `npm run build`. L’option locale `install-links=true` copie le package voisin, et `transpilePackages` permet sa compilation par Next.js. Incrémenter la version du package partagé et les deux entrées de lockfile quand son code change : le cache de build Next.js traite les dépendances installées comme immuables.

Après installation des dépendances de `app_clippers`, depuis `tools/reels` :

```sh
node tests/native-speed-orchestration.cjs
node tests/downloads.cjs
node tests/transport.cjs
node tests/proxy.cjs
node tests/ownership.cjs
node tests/ownership-sheets.cjs
node tests/app-lifecycle.cjs
```

Ces tests simulent le fournisseur et les médias. Ils couvrent la reprise, les appels ambigus, l’isolement des contextes, les téléchargements et le changement d’onglet. Les cas 320/375/390 du test de cycle de vie sont des contrôles de composants et de CSS, pas des captures d’écran ni une mesure de performance réelle.

Le contrôle d’appartenance et la préparation du registre existant sont décrits dans [OWNERSHIP.md](OWNERSHIP.md). Les références étrangères ou non enregistrées sont refusées avant transfert.

## Avant publication

- Effectuer une revue indépendante et une vérification visuelle mobile des deux apps : import, progression, reprise, six résultats, défilement et navigation basse.
- Vérifier que le contexte de build Vercel inclut le package voisin `tools/reels`. Les deux configurations de build ignoré suivent aussi ce dossier ; aucun réglage d’accès Vercel n’est modifié par cette PR.
- Ne pas annoncer une durée garantie de 50 secondes : les rendus OpusClip restent une dépendance externe et aucun essai représentatif payant n’est exécuté ici.
- Ne pas promettre l’enregistrement automatique dans la galerie, ni la reprise entre apps, appareils ou après fermeture. Le cache de l’ancienne iframe reste sur son origine.

Le workflow `app-reels.yml` construit les deux apps et lance les tests hors ligne. Il ne publie rien et ne modifie aucun workflow du bot.
