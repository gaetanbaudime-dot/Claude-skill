// Résa Dunes — site de réservation + CRM restaurant.
// Public : zéro cookie, zéro traceur (exemption bandeau CNIL). Session uniquement sous /admin.
const path = require('node:path');
const crypto = require('node:crypto');
const express = require('express');
const session = require('express-session');
const { reglagesAll, purgeRGPD } = require('./src/db');
const publicRoutes = require('./src/routes-public');
const adminRoutes = require('./src/routes-admin');

const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.set('trust proxy', 1);
app.disable('x-powered-by');

app.use(express.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, 'public'), { maxAge: '7d' }));

app.use((req, res, next) => {
  res.locals.reglages = reglagesAll();
  res.locals.siteUrl = process.env.SITE_URL || '';
  res.locals.chemin = req.path;
  next();
});

app.use(
  '/admin',
  session({
    name: 'resa.sid',
    secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
    resave: false,
    saveUninitialized: false,
    cookie: { httpOnly: true, sameSite: 'lax', secure: 'auto', maxAge: 12 * 3600 * 1000 },
  }),
  adminRoutes
);

app.use('/', publicRoutes);
app.use((req, res) => res.status(404).render('404'));

// Purge RGPD au démarrage (notes de service > 2 jours, historique > rétention).
purgeRGPD();

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Résa Dunes en écoute sur http://localhost:${PORT}`));
