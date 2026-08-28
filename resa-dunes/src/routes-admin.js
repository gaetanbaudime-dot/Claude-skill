// CRM admin — planning du service, fichier clients, stats, réglages, exports.
const express = require('express');
const {
  db,
  reglagesAll,
  setReglage,
  hashMotDePasse,
  verifieMotDePasse,
  upsertClient,
  purgeRGPD,
} = require('./db');
const { couvertsPris, creneaux, estFerme, creneauDisponible } = require('./capacite');

const router = express.Router();

function requireAuth(req, res, next) {
  if (req.session && req.session.admin) return next();
  res.redirect('/admin/login');
}
function aujourdhui() {
  return new Date().toISOString().slice(0, 10);
}
function csvLigne(valeurs) {
  return valeurs.map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(';');
}

// --- Authentification ---
router.get('/login', (req, res) => res.render('admin/login', { titre: 'Connexion', erreur: null }));

router.post('/login', (req, res) => {
  const compte = db.prepare('SELECT * FROM admins WHERE login = ?').get(String(req.body.login || '').trim());
  if (compte && verifieMotDePasse(String(req.body.motdepasse || ''), compte.sel, compte.hash)) {
    req.session.admin = compte.login;
    return res.redirect('/admin');
  }
  res.status(401).render('admin/login', { titre: 'Connexion', erreur: 'Identifiants incorrects.' });
});

router.post('/logout', (req, res) => req.session.destroy(() => res.redirect('/admin/login')));

router.use(requireAuth);

// --- Tableau de bord du jour ---
router.get('/', (req, res) => {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(req.query.date || '') ? req.query.date : aujourdhui();
  const reglages = reglagesAll();
  const services = {};
  for (const service of ['midi', 'soir']) {
    const resas = db
      .prepare(
        `SELECT r.*, c.nom AS client_nom, c.telephone AS client_tel, c.notes AS client_notes,
                (SELECT COUNT(*) FROM reservations x WHERE x.client_id = r.client_id AND x.statut = 'no_show') AS no_shows_client
         FROM reservations r JOIN clients c ON c.id = r.client_id
         WHERE r.date = ? AND r.service = ? ORDER BY r.heure, r.id`
      )
      .all(date, service);
    services[service] = {
      resas,
      couverts: couvertsPris(date, service),
      capacite: parseInt(reglages['capacite_' + service], 10) || 0,
    };
  }
  res.render('admin/dashboard', { titre: 'Service du jour', date, services, fermeture: estFerme(date, reglages) });
});

router.post('/reservations/:id/statut', (req, res) => {
  const statut = String(req.body.statut || '');
  if (['confirmee', 'arrivee', 'no_show', 'annulee'].includes(statut)) {
    db.prepare('UPDATE reservations SET statut = ? WHERE id = ?').run(statut, parseInt(req.params.id, 10));
  }
  res.redirect(req.get('referer') || '/admin');
});

// --- Nouvelle réservation (téléphone / comptoir) ---
router.get('/nouvelle', (req, res) => {
  res.render('admin/nouvelle', {
    titre: 'Nouvelle réservation',
    erreurs: [],
    valeurs: { date: req.query.date || aujourdhui(), service: req.query.service || 'soir' },
  });
});

router.post('/nouvelle', (req, res) => {
  const reglages = reglagesAll();
  const v = {
    nom: String(req.body.nom || '').trim().slice(0, 80),
    telephone: String(req.body.telephone || '').trim().slice(0, 20),
    email: String(req.body.email || '').trim().slice(0, 120),
    date: String(req.body.date || '').trim(),
    service: ['midi', 'soir'].includes(req.body.service) ? req.body.service : 'soir',
    heure: String(req.body.heure || '').trim(),
    couverts: parseInt(req.body.couverts, 10) || 0,
    preference: ['terrasse', 'interieur', 'indifferent'].includes(req.body.preference) ? req.body.preference : 'indifferent',
    note_service: String(req.body.note_service || '').trim().slice(0, 300),
    source: ['telephone', 'comptoir'].includes(req.body.source) ? req.body.source : 'telephone',
    forcer: req.body.forcer === '1',
  };
  const erreurs = [];
  if (v.nom.length < 2) erreurs.push('Nom requis.');
  if (v.couverts < 1) erreurs.push('Nombre de couverts requis.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date)) erreurs.push('Date invalide.');
  if (!/^\d{2}:\d{2}$/.test(v.heure)) erreurs.push('Heure invalide (HH:MM).');
  if (erreurs.length === 0 && !v.forcer && !creneauDisponible(v.date, v.service, v.heure, v.couverts, reglages)) {
    erreurs.push('Capacité dépassée sur ce créneau — cochez « forcer » pour passer outre (sur-réservation assumée).');
  }
  if (erreurs.length === 0) {
    const clientId = upsertClient(v);
    db.prepare(
      `INSERT INTO reservations (client_id, date, service, heure, couverts, preference, note_service, source)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).run(clientId, v.date, v.service, v.heure, v.couverts, v.preference, v.note_service, v.source);
    return res.redirect('/admin?date=' + v.date);
  }
  res.status(422).render('admin/nouvelle', { titre: 'Nouvelle réservation', erreurs, valeurs: v });
});

// --- Liste des réservations ---
router.get('/reservations', (req, res) => {
  const du = /^\d{4}-\d{2}-\d{2}$/.test(req.query.du || '') ? req.query.du : aujourdhui();
  const au = /^\d{4}-\d{2}-\d{2}$/.test(req.query.au || '') ? req.query.au : '';
  const statut = ['confirmee', 'arrivee', 'no_show', 'annulee'].includes(req.query.statut) ? req.query.statut : '';
  const q = String(req.query.q || '').trim();
  let sql = `SELECT r.*, c.nom AS client_nom, c.telephone AS client_tel
             FROM reservations r JOIN clients c ON c.id = r.client_id WHERE r.date >= ?`;
  const args = [du];
  if (au) { sql += ' AND r.date <= ?'; args.push(au); }
  if (statut) { sql += ' AND r.statut = ?'; args.push(statut); }
  if (q) { sql += ' AND (c.nom LIKE ? OR c.telephone LIKE ?)'; args.push(`%${q}%`, `%${q}%`); }
  sql += ' ORDER BY r.date, r.service DESC, r.heure LIMIT 500';
  const resas = db.prepare(sql).all(...args);
  res.render('admin/reservations', { titre: 'Réservations', resas, filtres: { du, au, statut, q } });
});

// --- Fichier clients ---
router.get('/clients', (req, res) => {
  const q = String(req.query.q || '').trim();
  let sql = `SELECT c.*,
      COUNT(r.id) AS nb_resas,
      COALESCE(SUM(CASE WHEN r.statut IN ('confirmee','arrivee') THEN r.couverts END), 0) AS couverts_cumules,
      SUM(CASE WHEN r.statut = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
      MAX(r.date) AS derniere_visite
    FROM clients c LEFT JOIN reservations r ON r.client_id = c.id`;
  const args = [];
  if (q) { sql += ' WHERE c.nom LIKE ? OR c.telephone LIKE ?'; args.push(`%${q}%`, `%${q}%`); }
  sql += ' GROUP BY c.id ORDER BY nb_resas DESC, c.nom LIMIT 500';
  const clients = db.prepare(sql).all(...args);
  res.render('admin/clients', { titre: 'Fichier clients', clients, q });
});

router.get('/clients/:id', (req, res) => {
  const client = db.prepare('SELECT * FROM clients WHERE id = ?').get(parseInt(req.params.id, 10));
  if (!client) return res.redirect('/admin/clients');
  const resas = db
    .prepare('SELECT * FROM reservations WHERE client_id = ? ORDER BY date DESC, heure DESC LIMIT 200')
    .all(client.id);
  res.render('admin/client', { titre: client.nom, client, resas });
});

router.post('/clients/:id/notes', (req, res) => {
  db.prepare('UPDATE clients SET notes = ? WHERE id = ?').run(
    String(req.body.notes || '').slice(0, 1000),
    parseInt(req.params.id, 10)
  );
  res.redirect('/admin/clients/' + parseInt(req.params.id, 10));
});

// --- Statistiques ---
router.get('/stats', (req, res) => {
  const semaines = db
    .prepare(
      `SELECT strftime('%Y-%W', date) AS semaine,
              MIN(date) AS debut,
              COUNT(*) AS resas,
              SUM(CASE WHEN statut IN ('confirmee','arrivee') THEN couverts ELSE 0 END) AS couverts,
              SUM(CASE WHEN statut = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
              SUM(CASE WHEN source = 'web' THEN 1 ELSE 0 END) AS via_web
       FROM reservations WHERE date >= date('now', '-56 day') AND date <= date('now', '+14 day')
       GROUP BY semaine ORDER BY semaine DESC LIMIT 10`
    )
    .all();
  const totaux = db
    .prepare(
      `SELECT COUNT(*) AS resas,
              SUM(CASE WHEN statut IN ('confirmee','arrivee') THEN couverts ELSE 0 END) AS couverts,
              SUM(CASE WHEN statut = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
              SUM(CASE WHEN source = 'web' THEN 1 ELSE 0 END) AS via_web
       FROM reservations`
    )
    .get();
  const habitues = db
    .prepare(
      `SELECT c.id, c.nom, c.telephone, COUNT(r.id) AS nb, MAX(r.date) AS derniere
       FROM clients c JOIN reservations r ON r.client_id = c.id AND r.statut IN ('confirmee','arrivee')
       GROUP BY c.id HAVING nb >= 2 ORDER BY nb DESC LIMIT 15`
    )
    .all();
  res.render('admin/stats', { titre: 'Statistiques', semaines, totaux, habitues });
});

// --- Réglages ---
router.get('/reglages', (req, res) => {
  res.render('admin/reglages', { titre: 'Réglages', message: req.query.ok ? 'Enregistré.' : null, erreur: null });
});

router.post('/reglages', (req, res) => {
  const cles = [
    'nom_resto', 'adresse', 'telephone', 'email_resto',
    'capacite_midi', 'capacite_soir', 'creneaux_midi', 'creneaux_soir',
    'resa_max_couverts', 'delai_min_minutes', 'jours_fermes', 'fermetures', 'retention_mois',
  ];
  for (const cle of cles) if (cle in req.body) setReglage(cle, String(req.body[cle]).trim());
  res.redirect('/admin/reglages?ok=1');
});

router.post('/motdepasse', (req, res) => {
  const nouveau = String(req.body.nouveau || '');
  if (nouveau.length < 8) {
    return res.status(422).render('admin/reglages', { titre: 'Réglages', message: null, erreur: '8 caractères minimum.' });
  }
  const { sel, hash } = hashMotDePasse(nouveau);
  db.prepare('UPDATE admins SET hash = ?, sel = ? WHERE login = ?').run(hash, sel, req.session.admin);
  res.redirect('/admin/reglages?ok=1');
});

router.post('/purge', (req, res) => {
  purgeRGPD();
  res.redirect('/admin/reglages?ok=1');
});

// --- Exports CSV ---
router.get('/export/reservations.csv', (req, res) => {
  const lignes = db
    .prepare(
      `SELECT r.date, r.service, r.heure, c.nom, c.telephone, c.email, r.couverts, r.preference, r.statut, r.source, r.cree_le
       FROM reservations r JOIN clients c ON c.id = r.client_id ORDER BY r.date DESC, r.heure`
    )
    .all();
  const csv = [csvLigne(['date', 'service', 'heure', 'nom', 'telephone', 'email', 'couverts', 'preference', 'statut', 'source', 'creee_le'])]
    .concat(lignes.map((l) => csvLigne([l.date, l.service, l.heure, l.nom, l.telephone, l.email, l.couverts, l.preference, l.statut, l.source, l.cree_le])))
    .join('\r\n');
  res.type('text/csv').attachment('reservations.csv').send('﻿' + csv);
});

router.get('/export/clients.csv', (req, res) => {
  const lignes = db
    .prepare(
      `SELECT c.nom, c.telephone, c.email, c.notes, COUNT(r.id) AS nb_resas,
              SUM(CASE WHEN r.statut = 'no_show' THEN 1 ELSE 0 END) AS no_shows, MAX(r.date) AS derniere_visite
       FROM clients c LEFT JOIN reservations r ON r.client_id = c.id GROUP BY c.id ORDER BY c.nom`
    )
    .all();
  const csv = [csvLigne(['nom', 'telephone', 'email', 'notes', 'nb_resas', 'no_shows', 'derniere_visite'])]
    .concat(lignes.map((l) => csvLigne([l.nom, l.telephone, l.email, l.notes, l.nb_resas, l.no_shows, l.derniere_visite])))
    .join('\r\n');
  res.type('text/csv').attachment('clients.csv').send('﻿' + csv);
});

module.exports = router;
