// Logique de capacité et de créneaux — le cœur anti-surbooking.
const { db, reglagesAll } = require('./db');

const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];

function creneaux(service, reglages) {
  return (reglages['creneaux_' + service] || '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => /^\d{2}:\d{2}$/.test(s));
}

function estFerme(dateStr, reglages) {
  const d = new Date(dateStr + 'T12:00:00');
  if (Number.isNaN(d.getTime())) return 'Date invalide.';
  const jour = JOURS[d.getDay()];
  const fermes = (reglages.jours_fermes || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (fermes.includes(jour)) return `Le restaurant est fermé le ${jour}.`;
  const dates = (reglages.fermetures || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (dates.includes(dateStr)) return 'Le restaurant est exceptionnellement fermé ce jour-là.';
  return null;
}

function couvertsPris(dateStr, service, heure = null) {
  let sql = `SELECT COALESCE(SUM(couverts), 0) AS total FROM reservations
             WHERE date = ? AND service = ? AND statut IN ('confirmee','arrivee')`;
  const args = [dateStr, service];
  if (heure) {
    sql += ' AND heure = ?';
    args.push(heure);
  }
  return db.prepare(sql).get(...args).total;
}

// Un créneau accepte au plus 1/3 de la capacité du service (lissage de la charge cuisine).
function capaciteCreneau(service, reglages) {
  const cap = parseInt(reglages['capacite_' + service], 10) || 40;
  return Math.ceil(cap / 3);
}

function creneauDisponible(dateStr, service, heure, couverts, reglages) {
  const cap = parseInt(reglages['capacite_' + service], 10) || 40;
  if (couvertsPris(dateStr, service) + couverts > cap) return false;
  if (couvertsPris(dateStr, service, heure) + couverts > capaciteCreneau(service, reglages)) return false;
  return true;
}

function creneauPasse(dateStr, heure, reglages) {
  const delaiMin = parseInt(reglages.delai_min_minutes, 10) || 0;
  const limite = new Date(Date.now() + delaiMin * 60000);
  const creneau = new Date(dateStr + 'T' + heure + ':00');
  return creneau < limite;
}

// Vue complète des disponibilités d'une date pour N couverts.
function disponibilites(dateStr, couverts) {
  const reglages = reglagesAll();
  const fermeture = estFerme(dateStr, reglages);
  const out = { date: dateStr, ferme: fermeture, services: {} };
  if (fermeture) return out;
  for (const service of ['midi', 'soir']) {
    out.services[service] = creneaux(service, reglages).map((heure) => ({
      heure,
      dispo: !creneauPasse(dateStr, heure, reglages) && creneauDisponible(dateStr, service, heure, couverts, reglages),
    }));
  }
  return out;
}

module.exports = { creneaux, estFerme, couvertsPris, capaciteCreneau, creneauDisponible, creneauPasse, disponibilites, JOURS };
