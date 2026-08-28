# Résa Dunes — site de réservation + CRM restaurant

Produit white-label. Première instance configurée pour **Atmosphère des Dunes** (Bretignolles-sur-Mer).
Node ≥ 22.5, SQLite natif (`node:sqlite`), **3 dépendances** (express, ejs, express-session), zéro module natif à compiler.

## Ce que ça fait

**Site public** (zéro cookie, zéro traceur → aucun bandeau CNIL requis) :
accueil SEO (JSON-LD Restaurant, sitemap, robots.txt), carte avec les vrais prix,
**réservation en ligne** avec disponibilités en direct, anti-surbooking transactionnel,
préférence terrasse/salle, champ allergies conforme RGPD, pages mentions légales + confidentialité.

**CRM (`/admin`)** : planning du service (jauges de capacité, statuts arrivée/no-show/annulée en un clic,
imprimable = feuille de service), saisie des résas téléphone/comptoir, liste filtrable,
**fichier clients** (historique, habitués ★, compteur no-show, notes maison), stats hebdo,
réglages (capacités, créneaux, fermetures), exports CSV, purge RGPD automatique et manuelle.

## Démarrer en local

```bash
npm install
node seed-demo.js   # données de démo (clients FICTIFS) — facultatif
npm start           # http://localhost:3000  —  admin : http://localhost:3000/admin
```

Compte admin par défaut : `admin` / `dunes2026` (ou variable `ADMIN_PASSWORD` au premier démarrage).
**À changer immédiatement** dans Réglages → Mot de passe.

## Déployer (Railway, ~10 minutes)

1. Nouveau service depuis ce dossier (le `Dockerfile` est prêt).
2. **Volume persistant monté sur `/data`** (sinon la base disparaît à chaque déploiement).
3. Variables : `SESSION_SECRET` (64 caractères aléatoires), `SITE_URL` (https://…), `ADMIN_PASSWORD`.
4. Domaine : brancher le domaine du client (voir étude — récupérer la propriété du domaine d'abord).

## Check-list avant mise en production réelle

- [ ] Valider la carte et les prix avec le restaurateur (extraits du site actuel le 28/08/2026).
- [ ] Valider horaires réels, capacités midi/soir, jours de fermeture (Réglages).
- [ ] Compléter l'hébergeur dans `views/legal.ejs` (mention obligatoire LCEN).
- [ ] Photos : uniquement des photos dont le restaurateur détient les droits (⚠️ jamais la banque Wix ni les photos Google des clients — voir étude, section légale).
- [ ] Changer le mot de passe admin + `SESSION_SECRET`.
- [ ] Origine des viandes sur la carte publiée (décret n° 2022-65) — à compléter avec le restaurateur.
- [ ] Registre RGPD du restaurant : ajouter le traitement « réservations en ligne » (modèle CNIL simplifié).

## Limites v1 assumées (= options à vendre ensuite)

- Pas d'email/SMS de confirmation (la confirmation est instantanée à l'écran) → option n°2.
- Pas d'empreinte bancaire anti no-show (nécessite Stripe + CGV) → option n°3.
- Le bouton « Réserver une table » de la fiche Google exige un partenaire agréé Google — un moteur
  maison n'y a pas accès. Stratégie : lien du site sur la fiche Google + SEO. Documenté dans l'étude.
- Sessions admin en mémoire : une redéploiement déconnecte l'admin (sans perte de données).

## Architecture

```
server.js            Express, sessions admin uniquement, purge RGPD au boot
src/db.js            SQLite (node:sqlite), schéma, réglages, scrypt, purge
src/capacite.js      créneaux, fermetures, capacité par service et par créneau
src/routes-public.js pages + POST /reserver (transaction anti-surbooking) + API dispos
src/routes-admin.js  CRM complet
src/carte-data.js    la carte (prix réels extraits du site actuel)
views/               EJS (public + admin)  ·  public/  CSS + JS vanilla
```
