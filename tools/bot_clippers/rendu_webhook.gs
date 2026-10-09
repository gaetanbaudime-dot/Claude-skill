/**
 * Rendu du test Clipper G&M — notificateur TEST_RENDU vers Discord (v1, 14/09/2026 — serveur fermé).
 *
 * RÔLE : le candidat n'est plus sur Discord quand il rend son test (décision du 14/09 : plus
 * personne n'arrive sur le serveur avant validation). Il le rend via un formulaire Google
 * « Rendu du test » ; à chaque soumission ce script poste sur le webhook Discord du salon admin :
 *   "TEST_RENDU|<prénom>|<numéro WhatsApp>|<e-mail>|<lien des vidéos>|<remarque>"
 * Le bot affiche la fiche au manager (prénom, pays, score du quiz, lien) qui juge puis tape
 * `!inviter Prénom` (validé : invitation personnelle + message WhatsApp prêt) ou `!refuser Prénom motif`.
 *
 * INSTALLATION (10 min, une fois) :
 *  1. Crée un formulaire Google « Rendu du test — Clippers G&M » avec 5 questions :
 *       Prénom (court) · Ton numéro WhatsApp, le même que dans ta candidature (court) ·
 *       Adresse e-mail (Paramètres → « Collecter les adresses e-mail », Vérifié) ·
 *       Le lien vers tes 2 Reels — Drive, WeTransfer ou Swisstransfer (court, obligatoire) ·
 *       Une remarque ? (paragraphe, facultatif)
 *     Message de confirmation : « Bien reçu ! Une personne regarde ton test, réponse sous 72 h sur WhatsApp. »
 *  2. Réponses → « Associer à Sheets » (nouvelle feuille) → sur cette feuille : Extensions → Apps Script,
 *     colle ce fichier, enregistre.
 *  3. Propriétés du script : DISCORD_WEBHOOK_URL = <webhook du salon admin, le même que quiz et candidature>
 *     · ENVOYER_MAILS = 1 (accusé de réception par e-mail, facultatif).
 *  4. Déclencheurs → Ajouter : fonction surRendu · source Depuis la feuille de calcul · type Lors de l'envoi
 *     du formulaire. Autorise. Teste avec une vraie soumission (« Exécutions » doit dire Terminée).
 *  5. Copie le lien du formulaire dans la propriété LIEN_RENDU du script du QUIZ : c'est lui qui
 *     l'envoie au candidat avec le dossier de rushs.
 */

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

/** Valeur d'une question par mots-clés dans son TITRE (namedValues) — l'ordre des colonnes n'importe pas. */
function prendre(nv, mots) {
  for (const cle in nv) {
    const c = cle.toLowerCase();
    if (mots.some(function (m) { return c.indexOf(m) !== -1; })) {
      const v = (nv[cle] && nv[cle][0]) ? String(nv[cle][0]).trim() : '';
      if (v) return v.replace(/\|/g, '/').replace(/\n/g, ' ');
    }
  }
  return '';
}

function surRendu(e) {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('DISCORD_WEBHOOK_URL');
  if (!url) { console.error('DISCORD_WEBHOOK_URL absent des propriétés du script — rien envoyé.'); return; }
  const nv = (e && e.namedValues) ? e.namedValues : {};
  const prenom   = prendre(nv, ['prénom', 'prenom']);
  const tel      = prendre(nv, ['whatsapp', 'téléphone', 'telephone', 'numéro', 'numero']);
  const email    = prendre(nv, ['e-mail', 'email', 'adresse mail']);
  const lien     = prendre(nv, ['lien', 'drive', 'transfer', 'vidéo', 'video', 'url', 'reels']);
  const remarque = prendre(nv, ['remarque', 'commentaire', 'message', 'précision']);
  if (!tel && !email) { console.warn('Rendu sans numéro ni e-mail — rien envoyé (le bot ne saurait pas à qui le rattacher).'); return; }
  const code = posterDiscord(url, 'TEST_RENDU|' + prenom + '|' + tel + '|' + email + '|' + lien + '|' + remarque.slice(0, 400));
  console.log('TEST_RENDU posté (' + (prenom || tel || email) + ') — HTTP ' + code);
  accuserReception(prenom, email);
}

/** Mise en forme e-mail pour les humains (règle du 14/09) : des <div> séparés par une ligne vide, jamais de <p>. */
function enHtml(lignes) {
  return lignes.map(function (l) {
    if (!l) return '<div><br></div>';
    const sain = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return '<div>' + sain.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1">$1</a>') + '</div>';
  }).join('');
}

/** Accusé de réception : le candidat sait que son test est bien arrivé et quand attendre la réponse. */
function accuserReception(prenom, email) {
  if (PropertiesService.getScriptProperties().getProperty('ENVOYER_MAILS') !== '1') return;
  if (!email || email.indexOf('@') === -1) return;
  const lignes = [
    'Bonjour ' + (prenom || '') + ',',
    '',
    'Ton test est bien reçu. Une personne le regarde : réponse en général sous 72 h, sur WhatsApp.',
    '',
    'Test validé : tu reçois ton invitation personnelle au Discord de l\'équipe, avec la suite (contrat ou conditions, puis ta créatrice).',
    '',
    'Merci pour le temps que tu y as mis,',
    'L\'équipe G&M'
  ];
  MailApp.sendEmail({ to: email, subject: 'Test bien reçu : réponse sous 72 h', name: 'Programme Clippers G&M',
                      body: lignes.join('\n'), htmlBody: enHtml(lignes) });
}

/** Diagnostic : confirme sur quelle feuille ce script tourne. */
function quelleFeuille() {
  console.log(SpreadsheetApp.getActiveSpreadsheet().getName());
}
