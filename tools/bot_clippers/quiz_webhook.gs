/**
 * Quiz Clipper G&M — notificateur QUIZ_OK vers Discord.
 *
 * RÔLE : à chaque soumission du formulaire de quiz, si le score >= SEUIL,
 * poste "QUIZ_OK|<idDiscord>|<score>" sur le webhook Discord du salon admin.
 * Le bot (bot_discord.py, traiter_quiz_webhook) capte ce message et envoie
 * automatiquement le test de montage 48 h au candidat.
 *
 * POURQUOI CE FICHIER : le passage quiz -> test a cessé de se déclencher
 * (les réussites des 18-20/07 n'ont jamais généré de QUIZ_OK). Cause quasi
 * certaine : le déclencheur onFormSubmit a sauté ou le script erre. Ceci est
 * un remplaçant robuste et lisible.
 *
 * INSTALLATION (5 min) :
 *  1. Sur la feuille des réponses : Extensions > Apps Script.
 *  2. Colle ce code (remplace l'ancien), enregistre.
 *  3. Roue crantée « Paramètres du projet » > Propriétés du script >
 *     ajoute la propriété :  DISCORD_WEBHOOK_URL = <URL du webhook du salon admin>
 *     (le secret vit ici, JAMAIS en dur dans le code).
 *  4. Icône horloge « Déclencheurs » > Ajouter un déclencheur :
 *       fonction = onQuizSubmit
 *       source   = Depuis la feuille de calcul
 *       type     = Lors de l'envoi du formulaire
 *  5. Autorise l'accès. Teste avec une vraie soumission (regarde « Exécutions »).
 *
 * VÉRIFIE LES COLONNES : le script lit le score en colonne C et l'ID Discord
 * en colonne D (ordre de la feuille : A Horodateur · B Email · C Score ·
 * D Identifiant Discord). Si ton form change l'ordre, ajuste COL_SCORE / COL_DISCORD.
 */

const SEUIL       = 27;   // note minimale (sur 34) pour valider le quiz
const COL_SCORE   = 3;    // colonne C = "Score"           (1-indexé)
const COL_DISCORD = 4;    // colonne D = "Identifiant Discord" (1-indexé)

function onQuizSubmit(e) {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) {
    console.error('DISCORD_WEBHOOK_URL absent des propriétés du script — rien envoyé.');
    return;
  }

  // Sur un déclencheur "onFormSubmit" côté feuille, e.values = la ligne complète
  // dans l'ordre des colonnes : [Horodateur, Email, Score, IdDiscord, ...].
  const vals = (e && e.values) ? e.values : [];
  const scoreRaw = String(vals[COL_SCORE - 1]   || '').trim();   // ex "32 / 34"
  const idDiscord = String(vals[COL_DISCORD - 1] || '').trim();

  // Parse "X / Y" (ou juste "X") -> note numérique.
  const m = scoreRaw.match(/(\d+)\s*\/\s*(\d+)/);
  const note = m ? parseInt(m[1], 10) : parseInt(scoreRaw, 10);
  if (isNaN(note)) { console.warn('Score illisible : "' + scoreRaw + '" — rien envoyé.'); return; }

  if (note < SEUIL)  { console.log('Recalé (' + scoreRaw + ') — pas de QUIZ_OK.'); return; }
  if (!idDiscord)    { console.warn('Réussi (' + scoreRaw + ') mais ID Discord vide — rien envoyé.'); return; }

  const reponse = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ content: 'QUIZ_OK|' + idDiscord + '|' + scoreRaw }),
    muteHttpExceptions: true
  });
  console.log('QUIZ_OK posté pour ' + idDiscord + ' (' + scoreRaw + ') — HTTP ' + reponse.getResponseCode());
}

/**
 * RATTRAPAGE MANUEL : lance rejouerReussites() une fois depuis l'éditeur pour
 * re-poster un QUIZ_OK pour toutes les lignes déjà >= SEUIL (le bot est
 * idempotent : un candidat qui a déjà reçu le test est ignoré). Utile pour
 * récupérer les réussites bloquées pendant que le déclencheur était cassé.
 */
function rejouerReussites() {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) { console.error('DISCORD_WEBHOOK_URL absent.'); return; }
  const feuille = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  const donnees = feuille.getDataRange().getValues();
  for (let i = 1; i < donnees.length; i++) {           // saute l'en-tête
    const scoreRaw = String(donnees[i][COL_SCORE - 1]   || '').trim();
    const idDiscord = String(donnees[i][COL_DISCORD - 1] || '').trim();
    const m = scoreRaw.match(/(\d+)\s*\/\s*(\d+)/);
    const note = m ? parseInt(m[1], 10) : parseInt(scoreRaw, 10);
    if (isNaN(note) || note < SEUIL || !idDiscord) continue;
    if (!/^\d{15,20}$/.test(idDiscord)) continue;       // ignore les ID de test bidons
    UrlFetchApp.fetch(url, {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify({ content: 'QUIZ_OK|' + idDiscord + '|' + scoreRaw }),
      muteHttpExceptions: true
    });
    Utilities.sleep(400);                                // ménage le rate-limit Discord
  }
  console.log('Rattrapage terminé.');
}
