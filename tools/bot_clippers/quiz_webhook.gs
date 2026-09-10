/**
 * Quiz Clipper G&M — notificateur QUIZ_OK / QUIZ_KO vers Discord (v3, 10/09/2026).
 *
 * RÔLE : à chaque soumission du formulaire de quiz, poste sur le webhook Discord du salon admin :
 *   - "QUIZ_OK|<idDiscord>|<score>|<email>"  si le score >= SEUIL  → le bot envoie le test 48 h ;
 *   - "QUIZ_KO|<idDiscord>|<score>|<email>"  sinon                 → le bot PRÉVIENT le candidat
 *     (score, lien, deuxième essai). Avant, un quiz raté = silence total, le candidat tournait en
 *     rond pendant des jours (cas Zakaria, 08/09).
 *   L'ID Discord vide n'est plus un abandon silencieux : la ligne part avec l'e-mail du quiz, le bot
 *   alerte l'admin qui retrouve le candidat (`!quiz-ok @membre`).
 *
 * ROBUSTESSE : les colonnes sont lues par TITRE de question (e.namedValues : « score », « discord »,
 * « e-mail ») avec repli sur les positions COL_* si les titres ne matchent pas ; l'envoi Discord
 * est retenté 3 fois (Discord rate-limite parfois le webhook).
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
 * REPLI COLONNES : si aucun titre ne matche, le script lit le score en colonne C et l'ID Discord
 * en colonne D (A Horodateur · B Email · C Score · D Identifiant Discord). Ajuste COL_* au besoin.
 */

const SEUIL       = 27;   // note minimale (sur 34) pour valider le quiz
const COL_SCORE   = 3;    // repli : colonne C = "Score"           (1-indexé)
const COL_DISCORD = 4;    // repli : colonne D = "Identifiant Discord" (1-indexé)
const COL_EMAIL   = 2;    // repli : colonne B = "Adresse e-mail"

/** Envoi Discord avec 3 tentatives (rate-limit 429 ou erreur passagère). */
function posterDiscord(url, contenu) {
  for (let essai = 1; essai <= 3; essai++) {
    const reponse = UrlFetchApp.fetch(url, {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify({ content: contenu }), muteHttpExceptions: true
    });
    const code = reponse.getResponseCode();
    if (code < 300) return code;
    console.warn('Discord HTTP ' + code + ' (essai ' + essai + '/3)');
    Utilities.sleep(1500 * essai);
  }
  return -1;
}

/** Valeur d'une question par mots-clés dans son TITRE (namedValues), sinon repli positionnel. */
function valeurQuestion(e, mots, colRepli) {
  const nv = (e && e.namedValues) ? e.namedValues : {};
  for (const cle in nv) {
    const c = cle.toLowerCase();
    if (mots.some(function (m) { return c.indexOf(m) !== -1; })) {
      const v = (nv[cle] && nv[cle][0]) ? String(nv[cle][0]).trim() : '';
      if (v) return v;
    }
  }
  const vals = (e && e.values) ? e.values : [];
  return String(vals[colRepli - 1] || '').trim();
}

function onQuizSubmit(e) {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) {
    console.error('DISCORD_WEBHOOK_URL absent des propriétés du script — rien envoyé.');
    return;
  }
  const scoreRaw  = valeurQuestion(e, ['score', 'note', 'points'], COL_SCORE);      // ex "32 / 34"
  const idDiscord = valeurQuestion(e, ['discord', 'identifiant'], COL_DISCORD).replace(/\D/g, '');
  const email     = valeurQuestion(e, ['e-mail', 'email', 'mail'], COL_EMAIL).replace(/\|/g, '/');

  const m = scoreRaw.match(/(\d+)\s*\/\s*(\d+)/);
  const note = m ? parseInt(m[1], 10) : parseInt(scoreRaw, 10);
  if (isNaN(note)) { console.warn('Score illisible : "' + scoreRaw + '" — rien envoyé.'); return; }

  const prefixe = (note >= SEUIL) ? 'QUIZ_OK' : 'QUIZ_KO';
  if (!idDiscord) console.warn(prefixe + ' (' + scoreRaw + ') mais ID Discord vide — envoyé avec l\'e-mail pour que l\'admin retrouve le candidat.');
  const code = posterDiscord(url, prefixe + '|' + idDiscord + '|' + scoreRaw + '|' + email);
  console.log(prefixe + ' posté pour ' + (idDiscord || email || '?') + ' (' + scoreRaw + ') — HTTP ' + code);
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
  const entetes = donnees[0].map(function (x) { return String(x).toLowerCase(); });
  const idx = function (mots, repli) {
    for (let i = 0; i < entetes.length; i++) {
      if (mots.some(function (m) { return entetes[i].indexOf(m) !== -1; })) return i;
    }
    return repli - 1;
  };
  const iScore = idx(['score', 'note', 'points'], COL_SCORE);
  const iId    = idx(['discord', 'identifiant'], COL_DISCORD);
  const iMail  = idx(['e-mail', 'email', 'mail'], COL_EMAIL);
  let n = 0;
  for (let i = 1; i < donnees.length; i++) {           // saute l'en-tête
    const scoreRaw = String(donnees[i][iScore] || '').trim();
    const idDiscord = String(donnees[i][iId] || '').trim().replace(/\D/g, '');
    const email = String(donnees[i][iMail] || '').trim().replace(/\|/g, '/');
    const m = scoreRaw.match(/(\d+)\s*\/\s*(\d+)/);
    const note = m ? parseInt(m[1], 10) : parseInt(scoreRaw, 10);
    if (isNaN(note) || note < SEUIL || !idDiscord) continue;
    if (!/^\d{15,20}$/.test(idDiscord)) continue;       // ignore les ID de test bidons
    posterDiscord(url, 'QUIZ_OK|' + idDiscord + '|' + scoreRaw + '|' + email);
    n++;
    Utilities.sleep(400);                                // ménage le rate-limit Discord
  }
  console.log('Rattrapage terminé : ' + n + ' réussite(s) rejouée(s). Le bot ignore celles déjà traitées.');
}
