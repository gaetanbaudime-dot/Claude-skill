// Routes publiques — zéro cookie, zéro traceur.
const express = require('express');
const { db, reglagesAll, upsertClient, normaliseTel } = require('./db');
const { disponibilites, estFerme, creneaux, creneauPasse, creneauDisponible } = require('./capacite');
const carte = require('./carte-data');

const router = express.Router();

// Anti-abus minimal : 6 tentatives de résa / 10 min / IP (en mémoire).
const tentatives = new Map();
function rateLimit(req) {
  const ip = req.ip || 'inconnu';
  const now = Date.now();
  const liste = (tentatives.get(ip) || []).filter((t) => now - t < 10 * 60 * 1000);
  liste.push(now);
  tentatives.set(ip, liste);
  return liste.length > 6;
}

router.get('/', (req, res) => {
  res.render('accueil', {
    titre: 'Atmosphère des Dunes — Brasserie, pizzeria & glacier à Bretignolles-sur-Mer',
    description:
      'Brasserie-pizzeria face au Camping des Dunes à Bretignolles-sur-Mer : terrasse plein sud, moules-frites, pizzas, glaces artisanales, préfou vendéen. Réservez votre table en ligne.',
    carte,
  });
});

router.get('/carte', (req, res) => {
  res.render('carte', {
    titre: 'La carte — Atmosphère des Dunes, Bretignolles-sur-Mer',
    description: 'Pizzas, moules-frites, burgers maison, glaces artisanales et cocktails : la carte complète avec les prix.',
    carte,
  });
});

router.get('/reserver', (req, res) => {
  res.render('reserver', {
    titre: 'Réserver une table — Atmosphère des Dunes',
    description: 'Réservation en ligne, confirmation immédiate. Choisissez votre créneau, votre nombre de couverts et votre préférence terrasse ou salle.',
    erreurs: [],
    valeurs: {},
  });
});

router.get('/api/disponibilites', (req, res) => {
  const date = String(req.query.date || '');
  const couverts = Math.max(1, Math.min(parseInt(req.query.couverts, 10) || 2, 60));
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return res.status(400).json({ erreur: 'Date invalide.' });
  res.json(disponibilites(date, couverts));
});

router.post('/reserver', (req, res) => {
  const reglages = reglagesAll();
  const v = {
    nom: String(req.body.nom || '').trim().slice(0, 80),
    telephone: String(req.body.telephone || '').trim().slice(0, 20),
    email: String(req.body.email || '').trim().slice(0, 120),
    date: String(req.body.date || '').trim(),
    service: String(req.body.service || '').trim(),
    heure: String(req.body.heure || '').trim(),
    couverts: parseInt(req.body.couverts, 10) || 0,
    preference: ['terrasse', 'interieur', 'indifferent'].includes(req.body.preference) ? req.body.preference : 'indifferent',
    note_service: String(req.body.note_service || '').trim().slice(0, 300),
  };

  // Pot de miel anti-robots : champ caché « site_web » — un humain le laisse vide.
  if (String(req.body.site_web || '') !== '') return res.render('merci', { titre: 'Réservation enregistrée', resa: v, reglages });

  const erreurs = [];
  if (rateLimit(req)) erreurs.push('Trop de tentatives depuis votre connexion — réessayez dans quelques minutes ou appelez-nous.');
  if (v.nom.length < 2) erreurs.push('Votre nom est requis.');
  if (normaliseTel(v.telephone).length < 9) erreurs.push('Un numéro de téléphone valide est requis (pour vous joindre en cas d’imprévu).');
  if (v.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email)) erreurs.push('L’email saisi est invalide.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date)) erreurs.push('Choisissez une date.');
  const maxCouverts = parseInt(reglages.resa_max_couverts, 10) || 12;
  if (v.couverts < 1 || v.couverts > maxCouverts)
    erreurs.push(`Entre 1 et ${maxCouverts} couverts en ligne — au-delà, appelez-nous au ${reglages.telephone}.`);
  if (!['midi', 'soir'].includes(v.service)) erreurs.push('Choisissez un service (midi ou soir).');

  if (erreurs.length === 0) {
    const fermeture = estFerme(v.date, reglages);
    if (fermeture) erreurs.push(fermeture);
    else if (!creneaux(v.service, reglages).includes(v.heure)) erreurs.push('Choisissez un créneau horaire.');
    else if (creneauPasse(v.date, v.heure, reglages)) erreurs.push('Ce créneau est déjà passé ou trop proche — choisissez plus tard.');
  }

  if (erreurs.length === 0) {
    // Transaction : re-vérifier la capacité au moment de l'écriture (anti double-réservation).
    db.exec('BEGIN IMMEDIATE');
    try {
      if (!creneauDisponible(v.date, v.service, v.heure, v.couverts, reglages)) {
        erreurs.push('Ce créneau vient de se remplir — choisissez un autre horaire.');
        db.exec('ROLLBACK');
      } else {
        const clientId = upsertClient(v);
        db.prepare(
          `INSERT INTO reservations (client_id, date, service, heure, couverts, preference, note_service, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'web')`
        ).run(clientId, v.date, v.service, v.heure, v.couverts, v.preference, v.note_service);
        db.exec('COMMIT');
        return res.render('merci', { titre: 'Réservation confirmée', resa: v, reglages });
      }
    } catch (e) {
      db.exec('ROLLBACK');
      erreurs.push('Erreur technique — réessayez ou appelez-nous.');
    }
  }

  res.status(erreurs.length ? 422 : 200).render('reserver', {
    titre: 'Réserver une table — Atmosphère des Dunes',
    description: 'Réservation en ligne, confirmation immédiate.',
    erreurs,
    valeurs: v,
  });
});

router.get('/contact', (req, res) => {
  res.render('contact', {
    titre: 'Accès & contact — Atmosphère des Dunes, Bretignolles-sur-Mer',
    description: '57 avenue des Dunes, 85470 Bretignolles-sur-Mer — face au Camping des Dunes, à 200 m de la plage.',
  });
});

router.get('/mentions-legales', (req, res) => {
  res.render('legal', { titre: 'Mentions légales — Atmosphère des Dunes', description: 'Mentions légales du site.' });
});

router.get('/confidentialite', (req, res) => {
  res.render('confidentialite', {
    titre: 'Données personnelles — Atmosphère des Dunes',
    description: 'Ce que nous faisons de vos données de réservation (peu de choses), et vos droits.',
  });
});

router.get('/robots.txt', (req, res) => {
  const base = res.locals.siteUrl || `${req.protocol}://${req.get('host')}`;
  res.type('text/plain').send(`User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: ${base}/sitemap.xml\n`);
});

router.get('/sitemap.xml', (req, res) => {
  const base = res.locals.siteUrl || `${req.protocol}://${req.get('host')}`;
  const pages = ['/', '/carte', '/reserver', '/contact', '/mentions-legales', '/confidentialite'];
  res.type('application/xml').send(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
      pages.map((p) => `  <url><loc>${base}${p}</loc></url>`).join('\n') +
      `\n</urlset>\n`
  );
});

module.exports = router;
