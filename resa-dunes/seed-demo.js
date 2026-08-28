// Données de DÉMONSTRATION — clients fictifs, à ne jamais utiliser en production.
// Usage : node seed-demo.js (à lancer une fois, base vide de préférence).
const { db, upsertClient } = require('./src/db');

const jour = (delta) => {
  const d = new Date(Date.now() + delta * 86400000);
  return d.toISOString().slice(0, 10);
};

const CLIENTS = [
  { nom: 'Martin Prevost', telephone: '0612000001', email: 'demo1@example.fr', notes: 'Table 12 préférée, vin blanc.' },
  { nom: 'Sophie Ligner', telephone: '0612000002', email: '', notes: '' },
  { nom: 'Famille Roussel', telephone: '0612000003', email: 'demo3@example.fr', notes: 'Chaise bébé.' },
  { nom: 'Paul Angevin', telephone: '0612000004', email: '', notes: '' },
  { nom: 'Claire Dumas', telephone: '0612000005', email: '', notes: 'Allergie fruits à coque (voir note du jour).' },
  { nom: 'Hugo Betton', telephone: '0612000006', email: '', notes: '' },
  { nom: 'Les Vacanciers du 12', telephone: '0612000007', email: '', notes: 'Camping Les Dunes, emplacement 12.' },
  { nom: 'Anne Kerloch', telephone: '0612000008', email: 'demo8@example.fr', notes: '' },
  { nom: 'Julien Fabre', telephone: '0612000009', email: '', notes: '' },
  { nom: 'Mme Garnier', telephone: '0612000010', email: '', notes: 'Habituée du dimanche midi.' },
];

const ids = {};
for (const c of CLIENTS) ids[c.telephone] = upsertClient(c);
for (const c of CLIENTS) if (c.notes) db.prepare('UPDATE clients SET notes = ? WHERE id = ?').run(c.notes, ids[c.telephone]);

const RESAS = [
  // Historique (stats + habitués + no-shows).
  [ids['0612000001'], jour(-21), 'soir', '20:00', 2, 'terrasse', '', 'arrivee', 'web'],
  [ids['0612000001'], jour(-7), 'soir', '20:15', 4, 'terrasse', '', 'arrivee', 'web'],
  [ids['0612000010'], jour(-14), 'midi', '12:30', 3, 'interieur', '', 'arrivee', 'telephone'],
  [ids['0612000010'], jour(-7), 'midi', '12:30', 3, 'interieur', '', 'arrivee', 'telephone'],
  [ids['0612000004'], jour(-10), 'soir', '19:30', 2, 'indifferent', '', 'no_show', 'web'],
  [ids['0612000006'], jour(-3), 'soir', '21:00', 5, 'terrasse', '', 'arrivee', 'web'],
  [ids['0612000008'], jour(-2), 'midi', '12:00', 2, 'terrasse', '', 'arrivee', 'web'],
  // Aujourd'hui.
  [ids['0612000002'], jour(0), 'midi', '12:15', 2, 'terrasse', '', 'confirmee', 'web'],
  [ids['0612000003'], jour(0), 'midi', '12:30', 5, 'interieur', 'Chaise bébé', 'confirmee', 'telephone'],
  [ids['0612000005'], jour(0), 'soir', '19:30', 2, 'terrasse', 'Allergie fruits à coque', 'confirmee', 'web'],
  [ids['0612000007'], jour(0), 'soir', '20:00', 8, 'terrasse', 'Anniversaire — dessert bougie', 'confirmee', 'web'],
  [ids['0612000009'], jour(0), 'soir', '20:30', 2, 'indifferent', '', 'confirmee', 'comptoir'],
  // Demain.
  [ids['0612000001'], jour(1), 'soir', '20:00', 2, 'terrasse', '', 'confirmee', 'web'],
  [ids['0612000004'], jour(1), 'midi', '13:00', 4, 'indifferent', '', 'confirmee', 'web'],
  [ids['0612000010'], jour(3), 'midi', '12:30', 3, 'interieur', '', 'confirmee', 'telephone'],
];

const ins = db.prepare(
  `INSERT INTO reservations (client_id, date, service, heure, couverts, preference, note_service, statut, source)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
);
for (const r of RESAS) ins.run(...r);

console.log(`Démo insérée : ${CLIENTS.length} clients, ${RESAS.length} réservations (fictifs).`);
