// Base SQLite (node:sqlite, natif Node >= 22.5 — aucune dépendance à compiler).
const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, '..', 'data');
fs.mkdirSync(DATA_DIR, { recursive: true });
const db = new DatabaseSync(path.join(DATA_DIR, 'resa.db'));

db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA foreign_keys = ON;

  CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telephone TEXT NOT NULL,
    email TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    cree_le TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_clients_tel ON clients(telephone);

  CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    service TEXT NOT NULL CHECK (service IN ('midi','soir')),
    heure TEXT NOT NULL,
    couverts INTEGER NOT NULL CHECK (couverts BETWEEN 1 AND 60),
    preference TEXT NOT NULL DEFAULT 'indifferent',
    note_service TEXT DEFAULT '',
    statut TEXT NOT NULL DEFAULT 'confirmee'
      CHECK (statut IN ('confirmee','arrivee','no_show','annulee')),
    source TEXT NOT NULL DEFAULT 'web' CHECK (source IN ('web','telephone','comptoir')),
    cree_le TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_resa_date ON reservations(date, service);
  CREATE INDEX IF NOT EXISTS idx_resa_client ON reservations(client_id);

  CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);

  CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    hash TEXT NOT NULL,
    sel TEXT NOT NULL
  );
`);

const REGLAGES_DEFAUT = {
  nom_resto: 'Atmosphère des Dunes',
  adresse: '57 avenue des Dunes, 85470 Bretignolles-sur-Mer',
  telephone: '09 73 20 84 93',
  email_resto: '',
  capacite_midi: '45',
  capacite_soir: '70',
  creneaux_midi: '12:00,12:15,12:30,12:45,13:00,13:15',
  creneaux_soir: '19:00,19:15,19:30,19:45,20:00,20:15,20:30,20:45,21:00',
  resa_max_couverts: '12',
  delai_min_minutes: '45',
  jours_fermes: '',
  fermetures: '',
  retention_mois: '13',
};

function getReglage(cle) {
  const r = db.prepare('SELECT valeur FROM reglages WHERE cle = ?').get(cle);
  return r ? r.valeur : (REGLAGES_DEFAUT[cle] ?? '');
}
function setReglage(cle, valeur) {
  db.prepare(
    'INSERT INTO reglages (cle, valeur) VALUES (?, ?) ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur'
  ).run(cle, String(valeur));
}
function reglagesAll() {
  const out = { ...REGLAGES_DEFAUT };
  for (const row of db.prepare('SELECT cle, valeur FROM reglages').all()) out[row.cle] = row.valeur;
  return out;
}
for (const [cle, valeur] of Object.entries(REGLAGES_DEFAUT)) {
  if (!db.prepare('SELECT 1 FROM reglages WHERE cle = ?').get(cle)) setReglage(cle, valeur);
}

// --- Mots de passe (scrypt natif) ---
function hashMotDePasse(mdp) {
  const sel = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(mdp, sel, 64).toString('hex');
  return { sel, hash };
}
function verifieMotDePasse(mdp, sel, hash) {
  const h = crypto.scryptSync(mdp, sel, 64).toString('hex');
  return crypto.timingSafeEqual(Buffer.from(h, 'hex'), Buffer.from(hash, 'hex'));
}
// Compte admin par défaut (à changer dès la première connexion — page Réglages).
if (!db.prepare('SELECT 1 FROM admins LIMIT 1').get()) {
  const { sel, hash } = hashMotDePasse(process.env.ADMIN_PASSWORD || 'dunes2026');
  db.prepare('INSERT INTO admins (login, hash, sel) VALUES (?, ?, ?)').run('admin', hash, sel);
}

// --- Clients ---
function upsertClient({ nom, telephone, email }) {
  const tel = normaliseTel(telephone);
  const existant = db.prepare('SELECT * FROM clients WHERE telephone = ?').get(tel);
  if (existant) {
    db.prepare('UPDATE clients SET nom = ?, email = CASE WHEN ? != \'\' THEN ? ELSE email END WHERE id = ?')
      .run(nom, email || '', email || '', existant.id);
    return existant.id;
  }
  return db.prepare('INSERT INTO clients (nom, telephone, email) VALUES (?, ?, ?)').run(nom, tel, email || '')
    .lastInsertRowid;
}
function normaliseTel(t) {
  return String(t || '').replace(/[^\d+]/g, '').replace(/^00/, '+').replace(/^\+33/, '0');
}

// --- Purge RGPD ---
// 1) Les notes de service (allergies, demandes) sont effacées 2 jours après la date du repas.
// 2) Les réservations plus vieilles que `retention_mois` sont supprimées, et les clients
//    sans réservation restante ni note sont supprimés avec elles.
function purgeRGPD() {
  const retention = parseInt(getReglage('retention_mois'), 10) || 13;
  db.prepare("UPDATE reservations SET note_service = '' WHERE note_service != '' AND date < date('now', '-2 day')").run();
  db.prepare(`DELETE FROM reservations WHERE date < date('now', ?)`).run(`-${retention} months`);
  db.prepare(`DELETE FROM clients WHERE notes = '' AND id NOT IN (SELECT DISTINCT client_id FROM reservations)`).run();
}

module.exports = {
  db,
  getReglage,
  setReglage,
  reglagesAll,
  hashMotDePasse,
  verifieMotDePasse,
  upsertClient,
  normaliseTel,
  purgeRGPD,
};
