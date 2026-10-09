/**
 * Quiz Clipper G&M — notificateur QUIZ_OK / QUIZ_KO vers Discord (v4, 14/09/2026 — serveur fermé).
 *
 * v4 — SERVEUR FERMÉ : le candidat n'est plus sur Discord quand il passe le quiz. La ligne
 * postée devient "QUIZ_OK|<idDiscord ou vide>|<score>|<email>|<numéro WhatsApp>" et, quand
 * l'identifiant Discord est vide, CE SCRIPT envoie les e-mails à la place du bot :
 *   - réussite → e-mail « test de montage 48 h » (LIEN_TEST + formulaire de rendu LIEN_RENDU) ;
 *   - échec    → e-mail « score, seuil, deuxième essai » (ou « parcours terminé » au 2ᵉ échec).
 * À faire une fois : dans le quiz, remplacer la question « Identifiant Discord » par
 * « Ton numéro WhatsApp (le même que dans ta candidature) » (ou l'ajouter et rendre l'autre
 * facultative pendant la transition) ; propriétés du script : ENVOYER_MAILS = 1 ·
 * LIEN_TEST = <dossier de rushs> · LIEN_RENDU = <formulaire « Rendu du test »> ·
 * LIEN_VIDEO = <vidéo de formation> · LIEN_QUIZ = <ce quiz, lien générique>.
 * Un candidat qui a encore un identifiant Discord (ancien tunnel) reste géré par le bot en MP.
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

const SEUIL       = 30;   // note minimale (sur 34) pour valider le quiz (24/09 : 27 → 30)
const COL_SCORE   = 3;    // repli : colonne C = "Score"           (1-indexé)
const COL_DISCORD = 4;    // (v4 : plus utilisé en temps réel — l'identifiant se lit par titre de question)
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
  // v4 : l'identifiant Discord se lit par TITRE uniquement (plus de repli sur la colonne D : quand la
  // question est renommée « numéro WhatsApp », la colonne D contient le numéro, pas un identifiant).
  let idDiscord   = valeurQuestion(e, ['discord', 'identifiant'], 0).replace(/\D/g, '');
  if (idDiscord.length < 15) idDiscord = '';          // un identifiant Discord fait 17 à 20 chiffres
  const email     = valeurQuestion(e, ['e-mail', 'email', 'mail'], COL_EMAIL).replace(/\|/g, '/');
  // v4 : le numéro WhatsApp est la clé du candidat hors Discord (le bot le croise avec la candidature).
  const tel       = valeurQuestion(e, ['whatsapp', 'téléphone', 'telephone', 'numéro', 'numero'], 0).replace(/\|/g, '/');

  const m = scoreRaw.match(/(\d+)\s*\/\s*(\d+)/);
  const note = m ? parseInt(m[1], 10) : parseInt(scoreRaw, 10);
  if (isNaN(note)) { console.warn('Score illisible : "' + scoreRaw + '" — rien envoyé.'); return; }

  const prefixe = (note >= SEUIL) ? 'QUIZ_OK' : 'QUIZ_KO';
  if (!idDiscord && !tel && !email) console.warn(prefixe + ' (' + scoreRaw + ') sans identifiant, numéro ni e-mail — le bot ne pourra rattacher personne.');
  const code = posterDiscord(url, prefixe + '|' + idDiscord + '|' + scoreRaw + '|' + email + '|' + tel);
  console.log(prefixe + ' posté pour ' + (idDiscord || tel || email || '?') + ' (' + scoreRaw + ') — HTTP ' + code);

  // Serveur fermé : sans identifiant Discord, la suite part par e-mail depuis ici.
  if (!idDiscord) envoyerMailQuiz(note >= SEUIL, scoreRaw, email, compterEssais(email));
}

/** Nombre de quiz déjà passés avec cet e-mail (la ligne courante comprise) — deux essais maximum. */
function compterEssais(email) {
  if (!email) return 1;
  try {
    const feuille = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    const donnees = feuille.getDataRange().getValues();
    const entetes = donnees[0].map(function (x) { return String(x).toLowerCase(); });
    let iMail = -1;
    for (let i = 0; i < entetes.length; i++) {
      if (['e-mail', 'email', 'mail'].some(function (m) { return entetes[i].indexOf(m) !== -1; })) { iMail = i; break; }
    }
    if (iMail < 0) iMail = COL_EMAIL - 1;
    let n = 0;
    for (let l = 1; l < donnees.length; l++) {
      if (String(donnees[l][iMail] || '').trim().toLowerCase() === email.toLowerCase()) n++;
    }
    return Math.max(1, n);
  } catch (err) { return 1; }
}

/** Mise en forme e-mail pour les humains (règle du 14/09) : des <div> séparés par une ligne vide, jamais de <p>. */
function enHtml(lignes) {
  return lignes.map(function (l) {
    if (!l) return '<div><br></div>';
    const sain = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return '<div>' + sain.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1">$1</a>') + '</div>';
  }).join('');
}

/** E-mail après le quiz : le test 48 h (réussite) ou le score + deuxième essai (échec). */
function envoyerMailQuiz(reussite, scoreRaw, email, essais) {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('ENVOYER_MAILS') !== '1') return;
  if (!email || email.indexOf('@') === -1) { console.warn('Quiz sans e-mail : pas de mail.'); return; }
  let sujet, lignes;
  if (reussite) {
    const lienTest = props.getProperty('LIEN_TEST') || '', lienRendu = props.getProperty('LIEN_RENDU') || '';
    if (!lienTest || !lienRendu) { console.warn('LIEN_TEST / LIEN_RENDU manquants — mail de test non envoyé.'); return; }
    const echeance = Utilities.formatDate(new Date(Date.now() + 48 * 3600 * 1000), 'Europe/Paris', "dd/MM/yyyy 'à' HH'h'mm");
    sujet = 'Quiz réussi (' + scoreRaw + ') : ton test de montage, 48 h';
    lignes = [
      'Bravo, quiz réussi : ' + scoreRaw + '.',
      '',
      'Dernière étape avant l\'équipe : le test de montage.',
      '',
      '1. Le dossier de rushs : ' + lienTest,
      '2. Tu choisis 2 rushs et tu montes 2 Reels (format vertical, méthode de la formation).',
      '3. Tu les rends ici, avant le ' + echeance + ' (heure de Paris) : ' + lienRendu,
      '(un lien Drive, WeTransfer ou Swisstransfer vers tes 2 vidéos suffit)',
      '',
      'Une personne regarde ton test. Réponse en général sous 72 h, sur WhatsApp. Test validé : tu reçois ton invitation personnelle au Discord de l\'équipe.',
      '',
      'La régularité et le respect du brief comptent autant que le style. Bonne chance !',
      'L\'équipe G&M'
    ];
  } else if (essais < 2) {
    sujet = 'Quiz : ' + scoreRaw + ', il te reste un essai';
    lignes = [
      'Ton score : ' + scoreRaw + '. Il faut 30/34 pour passer au test.',
      '',
      'Pas grave : tu as un deuxième essai.',
      '',
      '1. Revois la vidéo de formation (les 4 mots-clés) : ' + (props.getProperty('LIEN_VIDEO') || ''),
      '2. Repasse le quiz : ' + (props.getProperty('LIEN_QUIZ') || ''),
      '',
      'Courage,',
      'L\'équipe G&M'
    ];
  } else {
    sujet = 'Quiz : ' + scoreRaw + ', le parcours s\'arrête là pour cette fois';
    lignes = [
      'Ton score : ' + scoreRaw + '. C\'était ton deuxième essai : le parcours s\'arrête là pour cette fois.',
      '',
      'Merci d\'avoir joué le jeu. Si tu veux retenter dans quelques semaines, refais simplement une candidature.',
      '',
      'L\'équipe G&M'
    ];
  }
  MailApp.sendEmail({ to: email, subject: sujet, name: 'Programme Clippers G&M',
                      body: lignes.join('\n'), htmlBody: enHtml(lignes) });
  console.log('Mail quiz envoyé (' + (reussite ? 'test' : 'échec ' + essais + '/2') + ') à ' + email);
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
