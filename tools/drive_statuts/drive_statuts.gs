/**
 * Statuts automatiques des dossiers Drive (✅ ⏳ ❌) — LTP, 11/09/2026.
 *
 * RÔLE : parcourir tout le Drive des créatrices (Instagram, Facebook… → Reels, Carrousel, Stories…)
 * et tenir à jour, chaque matin, le nom de chaque dossier mensuel :
 *   ⏳ 9. Septembre   = le mois en cours (dossier en train d'être rempli)
 *   ✅ 8. Aout        = un mois passé ou à venir qui CONTIENT des fichiers
 *   ❌ 10. Octobre    = un dossier vide (hors mois en cours)
 * Le script crée les mois manquants (1. Janvier … 12. Décembre) là où il en trouve déjà, et
 * range les fichiers oubliés à la racine (ex. « AA 1.jpg » dans Carrousel) dans le dossier du
 * mois de leur date de création. Il ne supprime jamais rien.
 *
 * INSTALLATION (une seule fois, depuis le compte Google LTP qui voit les dossiers partagés) :
 *  1. script.google.com → Nouveau projet → colle ce fichier → Enregistrer (nom : « Drive statuts »).
 *  2. Roue crantée « Paramètres du projet » → Propriétés du script → ajoute :
 *       DOSSIERS_RACINE = <id du dossier Instagram>[,<id d'un autre dossier racine>…]
 *       (l'id = la fin de l'URL du dossier : drive.google.com/drive/folders/<ID>)
 *       DISCORD_WEBHOOK_URL = <webhook du salon admin>   (facultatif : un bilan par matin)
 *  3. Exécute UNE fois `lancerMaintenant` depuis l'éditeur (autorise l'accès Drive).
 *  4. Exécute UNE fois `installerDeclencheur` : le script tourne ensuite tous les jours à 6 h.
 *
 * LIMITES HONNÊTES : un dossier partagé en LECTURE SEULE par une créatrice ne peut pas être
 * renommé — il apparaît dans le bilan comme « lecture seule ». Les dossiers mensuels n'ont pas
 * d'année : le mois en cours est déterminé par la date du jour (fuseau Europe/Paris).
 */

const MOIS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Aout',
              'Septembre', 'Octobre', 'Novembre', 'Décembre'];
const FUSEAU = 'Europe/Paris';
const EMOJIS = ['✅', '⏳', '❌'];
// « 1. Janvier », « ✅ 08. Aout », « ⏳ 9 - septembre », « août »/« aout »/« Décembre »/« decembre »…
const MOTIF_MOIS = /^\s*(?:[✅⏳❌]\s*)?(\d{1,2})?\s*[.\-–]?\s*([A-Za-zÀ-ÿ]+)\s*$/;

function lancerMaintenant() {
  const props = PropertiesService.getScriptProperties();
  const racines = (props.getProperty('DOSSIERS_RACINE') || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!racines.length) {
    console.error('DOSSIERS_RACINE absent des propriétés du script — rien fait.');
    return;
  }
  const bilan = { ok: 0, encours: 0, vides: 0, crees: 0, tries: 0, lectureSeule: [], erreurs: [] };
  const maintenant = new Date();
  const moisCourant = parseInt(Utilities.formatDate(maintenant, FUSEAU, 'M'), 10);
  for (const id of racines) {
    try {
      traiterArbre(DriveApp.getFolderById(id), moisCourant, bilan, 0);
    } catch (e) {
      bilan.erreurs.push('racine ' + id + ' : ' + e);
    }
  }
  const texte = '📁 Drive créatrices — ' + Utilities.formatDate(maintenant, FUSEAU, 'dd/MM HH:mm')
    + '\n✅ ' + bilan.ok + ' mois avec contenu · ⏳ ' + bilan.encours + ' en cours · ❌ ' + bilan.vides + ' vides'
    + (bilan.crees ? '\n➕ ' + bilan.crees + ' dossier(s) de mois créé(s)' : '')
    + (bilan.tries ? '\n🗂️ ' + bilan.tries + ' fichier(s) rangé(s) dans leur mois' : '')
    + (bilan.lectureSeule.length ? '\n🔒 Lecture seule (non renommables) : ' + bilan.lectureSeule.slice(0, 8).join(', ') : '')
    + (bilan.erreurs.length ? '\n⚠️ ' + bilan.erreurs.slice(0, 5).join(' · ') : '');
  console.log(texte);
  const url = props.getProperty('DISCORD_WEBHOOK_URL');
  if (url) {
    UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json',
                             payload: JSON.stringify({ content: texte.slice(0, 1900) }), muteHttpExceptions: true });
  }
}

/** Parcours récursif : un dossier qui contient au moins un dossier « mois » est un dossier de contenu. */
function traiterArbre(dossier, moisCourant, bilan, profondeur) {
  if (profondeur > 6) return;                         // garde-fou contre les raccourcis en boucle
  const sousDossiers = [];
  const it = dossier.getFolders();
  while (it.hasNext()) sousDossiers.push(it.next());
  const mensuels = sousDossiers.filter(d => lireMois(d.getName()) !== null);
  if (mensuels.length) {
    traiterDossierDeContenu(dossier, sousDossiers, moisCourant, bilan);
  }
  for (const d of sousDossiers) {
    if (lireMois(d.getName()) === null) traiterArbre(d, moisCourant, bilan, profondeur + 1);
  }
}

/** Dans un dossier de contenu (Reels, Carrousel…) : mois manquants créés, fichiers en vrac rangés, noms mis à jour. */
function traiterDossierDeContenu(dossier, sousDossiers, moisCourant, bilan) {
  const parMois = {};
  for (const d of sousDossiers) {
    const m = lireMois(d.getName());
    if (m !== null && !parMois[m]) parMois[m] = d;
  }
  // 1. Les 12 mois existent.
  for (let m = 1; m <= 12; m++) {
    if (!parMois[m]) {
      try {
        parMois[m] = dossier.createFolder(nomDeMois(m, moisCourant, false));
        bilan.crees++;
      } catch (e) {
        bilan.lectureSeule.push(dossier.getName() + ' (création de ' + MOIS[m - 1] + ')');
        return;                                       // pas le droit d'écrire ici : on passe
      }
    }
  }
  // 2. Les fichiers oubliés à la racine vont dans le mois de leur date de création.
  const fichiers = dossier.getFiles();
  while (fichiers.hasNext()) {
    const f = fichiers.next();
    const m = parseInt(Utilities.formatDate(f.getDateCreated(), FUSEAU, 'M'), 10);
    try {
      f.moveTo(parMois[m]);
      bilan.tries++;
    } catch (e) {
      bilan.erreurs.push(dossier.getName() + '/' + f.getName() + ' non déplaçable');
    }
  }
  // 3. Le nom de chaque mois = son statut.
  for (let m = 1; m <= 12; m++) {
    const d = parMois[m];
    const aDuContenu = contientDesFichiers(d);
    const nouveau = nomDeMois(m, moisCourant, aDuContenu);
    if (m === moisCourant) bilan.encours++; else if (aDuContenu) bilan.ok++; else bilan.vides++;
    if (d.getName() !== nouveau) {
      try {
        d.setName(nouveau);
      } catch (e) {
        bilan.lectureSeule.push(dossier.getName() + '/' + d.getName());
      }
    }
  }
}

function nomDeMois(m, moisCourant, aDuContenu) {
  const statut = (m === moisCourant) ? '⏳' : (aDuContenu ? '✅' : '❌');
  return statut + ' ' + m + '. ' + MOIS[m - 1];
}

/** Numéro de mois (1-12) lu dans un nom de dossier, ou null si ce n'est pas un dossier de mois. */
function lireMois(nom) {
  const m = MOTIF_MOIS.exec(nom || '');
  if (!m) return null;
  const mot = normaliser(m[2]);
  const index = MOIS.map(normaliser).indexOf(mot);
  if (index >= 0) return index + 1;
  if (m[1] && (mot === '' || mot === 'mois')) {         // « 9. » seul, sans nom
    const n = parseInt(m[1], 10);
    return (n >= 1 && n <= 12) ? n : null;
  }
  return null;
}

function normaliser(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]/g, '');
}

/** Vrai si le dossier (ou un de ses sous-dossiers) contient au moins un fichier. */
function contientDesFichiers(dossier) {
  if (dossier.getFiles().hasNext()) return true;
  const it = dossier.getFolders();
  while (it.hasNext()) {
    if (contientDesFichiers(it.next())) return true;
  }
  return false;
}

/** Déclencheur quotidien à 6 h (heure du script). À lancer une fois. */
function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'lancerMaintenant') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('lancerMaintenant').timeBased().everyDays(1).atHour(6).create();
  console.log('Déclencheur installé : lancerMaintenant tous les jours à 6 h.');
}
