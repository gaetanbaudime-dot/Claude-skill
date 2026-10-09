/**
 * Candidatures Clipper G&M — notificateur CANDIDATURE vers Discord.
 *
 * RÔLE : à chaque soumission du formulaire de candidature (« Recherche Clipper »),
 * poste "CANDIDATURE|<prénom>|<tel>|<pays>|<pseudo>" sur le webhook Discord du
 * salon admin. Le bot (bot_discord.py, traiter_candidature_webhook) capte ce
 * message, enregistre la candidature et ouvre la grille au candidat.
 *
 * POURQUOI CE FICHIER : le 21/07, le code du projet Apps Script de la feuille
 * candidatures a été remplacé par erreur (collage du script quiz), effaçant la
 * fonction `surCandidature`. Le déclencheur formSubmit, lui, est resté et pointe
 * toujours vers `surCandidature` → « Script function not found » à chaque
 * soumission (10 candidatures des 21-22/07 jamais transmises au bot). Ce fichier
 * REDÉFINIT `surCandidature` (même nom, exactement) : le déclencheur existant
 * se remet à marcher tout seul, sans rien recréer.
 *
 * INSTALLATION (3 min) — sur la feuille « Recherche Clipper (réponses) » :
 *  1. Extensions > Apps Script (le projet « Projet sans titre ») → remplace tout
 *     le code par ce fichier, enregistre.
 *  2. Roue crantée « Paramètres du projet » > Propriétés du script > ajoute :
 *     DISCORD_WEBHOOK_URL = <URL du webhook du salon admin> (le même que le quiz).
 *     (Le collage du 21/07 a pu vider cette propriété — vérifie-la.)
 *  3. NE TOUCHE PAS aux déclencheurs : celui qui existe (formSubmit →
 *     surCandidature) redevient fonctionnel dès que ce code est enregistré.
 *  4. Lance `rejouerCandidatures()` UNE fois depuis l'éditeur : rejoue TOUTE la
 *     feuille par paquets de 10 (le bot déduplique par numéro : sans risque) —
 *     c'est ce qui donne au bot le PAYS de chaque candidat pour croiser la grille.
 *  5. Vérifie dans « Exécutions » : surCandidature doit passer « Terminée ».
 *
 * ROBUSTESSE COLONNES : on lit e.namedValues (titre de question → réponse) et on
 * matche par mots-clés (prénom / whatsapp-téléphone-numéro / pays-résides /
 * discord-pseudo) — l'ordre des colonnes de la feuille n'a aucune importance.
 *
 * v2 — SERVEUR FERMÉ (14/09/2026) : plus personne n'arrive sur Discord avant validation.
 * Le tunnel continue par E-MAIL : ce script envoie au candidat, dès sa candidature, la
 * vidéo de formation + le lien du quiz (le formulaire ne donne plus le lien Discord).
 * Pour l'activer (3 réglages, une fois) :
 *  a. Dans le formulaire de candidature : Paramètres → Réponses → « Collecter les adresses
 *     e-mail » (Vérifié) — sans e-mail, pas de mail (la ligne CANDIDATURE part quand même).
 *  b. Message de confirmation du formulaire (Paramètres → Présentation) : « Merci ! Regarde
 *     tes e-mails : la formation et le quiz t'attendent » — et on RETIRE le lien Discord.
 *  c. Propriétés du script : ENVOYER_MAILS = 1 · LIEN_VIDEO = <vidéo de formation> ·
 *     LIEN_QUIZ = <formulaire du quiz, version générique sans identifiant Discord>.
 * Quota Gmail : 100 mails/jour (compte perso) ou 1 500 (Workspace) — largement assez.
 */

/** Envoi Discord avec 3 tentatives (rate-limit 429 ou erreur passagère) — 10/09. */
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

const NB_REJOUER = 400;  // rejouerCandidatures : nombre de dernières lignes rejouées (400 = toute la
                         // feuille actuelle — le bot déduplique par numéro, rejouer est sans risque)
const PAR_MESSAGE = 10;  // lignes CANDIDATURE groupées par message Discord (le bot sait les lire en lot)

function surCandidature(e) {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) {
    console.error('DISCORD_WEBHOOK_URL absent des propriétés du script — rien envoyé.');
    return;
  }
  const nv = (e && e.namedValues) ? e.namedValues : {};
  const prendre = function (mots) {
    for (const cle in nv) {
      const c = cle.toLowerCase();
      if (mots.some(function (m) { return c.indexOf(m) !== -1; })) {
        const v = (nv[cle] && nv[cle][0]) ? String(nv[cle][0]).trim() : '';
        if (v) return v.replace(/\|/g, '/');   // un « | » dans une réponse casserait le format
      }
    }
    return '';
  };
  // ⚠️ CORRECTIF DU 10/08 — le numéro ne se prend PAS avec `prendre`.
  // Pourquoi : `for (const cle in nv)` parcourt un OBJET, dont l'ordre des clés
  // n'est pas celui des colonnes de la feuille. Avec une liste large
  // (whatsapp OU téléphone OU numéro…), la question parasite « Combien tu as
  // de Téléphones ? Quel est le modèle ? » pouvait sortir en premier : le bot
  // recevait « iPhone 15 pro » à la place du numéro, et la candidature était
  // perdue alors que le formulaire contenait un numéro valide (Yannik, Josué,
  // Matea, Kloriane, Safia, Bastien, Marwane, Lou, Charlotte, Quentin —
  // 10 candidats en 3 jours). Deux garde-fous : priorité absolue au mot-clé
  // « whatsapp » (seul discriminant), et la valeur doit contenir ≥ 8 chiffres.
  const estUnNumero = function (v) { return String(v).replace(/\D/g, '').length >= 8; };
  const prendreTel = function () {
    const essai = function (mots) {
      for (const cle in nv) {
        const c = cle.toLowerCase();
        if (!mots.some(function (m) { return c.indexOf(m) !== -1; })) continue;
        const v = (nv[cle] && nv[cle][0]) ? String(nv[cle][0]).trim() : '';
        if (v && estUnNumero(v)) return v.replace(/\|/g, '/');
      }
      return '';
    };
    return essai(['whatsapp'])                                            // 1) le bon champ
        || essai(['téléphone', 'telephone', 'numéro', 'numero', 'tel']);  // 2) repli si le form change
  };

  const prenom = prendre(['prénom', 'prenom']);
  const tel    = prendreTel();
  const pays   = prendre(['pays', 'résides', 'resides']);
  const pseudo = prendre(['discord', 'pseudo']);
  if (!tel) { console.warn('Candidature sans numéro exploitable — rien envoyé.'); return; }

  const code = posterDiscord(url, 'CANDIDATURE|' + prenom + '|' + tel + '|' + pays + '|' + pseudo);
  console.log('CANDIDATURE postée (' + (prenom || '?') + ') — HTTP ' + code);
  // Serveur fermé (14/09) : la suite arrive par e-mail — vidéo + quiz.
  envoyerMailBienvenue(prenom, prendre(['e-mail', 'email', 'adresse mail']));
}

/** Mise en forme e-mail pour les humains (règle du 14/09) : Gmail écrase les marges des <p>,
 *  donc des <div> séparés par une ligne vide, et la version texte garde ses lignes vides. */
function enHtml(lignes) {
  return lignes.map(function (l) {
    if (!l) return '<div><br></div>';
    const sain = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return '<div>' + sain.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1">$1</a>') + '</div>';
  }).join('');
}

/** E-mail « bienvenue : formation + quiz » — le premier pas du tunnel hors Discord. */
function envoyerMailBienvenue(prenom, email) {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('ENVOYER_MAILS') !== '1') return;
  if (!email || email.indexOf('@') === -1) {
    console.warn('Candidature sans e-mail : pas de mail de bienvenue — active « Collecter les adresses e-mail » dans le formulaire.');
    return;
  }
  const video = props.getProperty('LIEN_VIDEO') || '';
  const quiz  = props.getProperty('LIEN_QUIZ') || '';
  if (!video || !quiz) { console.warn('LIEN_VIDEO / LIEN_QUIZ manquants dans les propriétés — pas de mail.'); return; }
  const lignes = [
    'Bonjour ' + (prenom || '') + ',',
    '',
    'Ta candidature au programme Clippers G&M est bien reçue. Deux étapes, dans l\'ordre :',
    '',
    '1. La formation (vidéo, 54 minutes) : ' + video,
    'Regarde-la en entier : 4 mots-clés y sont cachés, ils sont demandés au quiz.',
    '',
    '2. Le quiz : ' + quiz,
    'Seuil : 30/34, deux essais maximum. Indique le même numéro WhatsApp que dans ta candidature.',
    '',
    'Quiz réussi : tu reçois le test de montage (48 h) par e-mail. Test validé : tu reçois ton invitation personnelle au Discord de l\'équipe.',
    '',
    'À très vite,',
    'L\'équipe G&M'
  ];
  MailApp.sendEmail({ to: email, subject: 'Ta candidature Clipper G&M : formation + quiz',
                      name: 'Programme Clippers G&M', body: lignes.join('\n'), htmlBody: enHtml(lignes) });
  console.log('Mail de bienvenue envoyé (' + (prenom || '?') + ').');
}

/**
 * RATTRAPAGE MANUEL : rejoue les NB_REJOUER dernières lignes de la feuille
 * (couvre les soumissions perdues pendant que la fonction manquait). Le bot
 * enregistre par numéro de téléphone : une candidature déjà connue est
 * simplement mise à jour, jamais dupliquée.
 */
function rejouerCandidatures() {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) { console.error('DISCORD_WEBHOOK_URL absent.'); return; }
  const feuille = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  const donnees = feuille.getDataRange().getValues();
  if (donnees.length < 2) { console.log('Feuille vide.'); return; }
  const entetes = donnees[0].map(function (x) { return String(x).toLowerCase(); });
  const idx = function (mots) {
    for (let i = 0; i < entetes.length; i++) {
      if (mots.some(function (m) { return entetes[i].indexOf(m) !== -1; })) return i;
    }
    return -1;
  };
  const iPrenom = idx(['prénom', 'prenom']);
  // Même priorité qu'en temps réel : « whatsapp » d'abord, sinon repli — sinon
  // la colonne « Combien tu as de Téléphones ? » peut gagner et rejouer 400
  // lignes de modèles de téléphones à la place des numéros.
  const iTel    = idx(['whatsapp']) >= 0 ? idx(['whatsapp'])
                                         : idx(['téléphone', 'telephone', 'numéro', 'numero', 'tel']);
  const iPays   = idx(['pays', 'résides', 'resides']);
  const iPseudo = idx(['discord', 'pseudo']);
  if (iTel < 0) { console.error('Colonne du numéro introuvable — entêtes : ' + donnees[0].join(' · ')); return; }

  const nettoyer = function (ligne, i) {
    return (i >= 0 && ligne[i]) ? String(ligne[i]).trim().replace(/\|/g, '/') : '';
  };
  const lignes = [];
  const debut = Math.max(1, donnees.length - NB_REJOUER);
  for (let l = debut; l < donnees.length; l++) {
    const tel = nettoyer(donnees[l], iTel);
    if (!tel) continue;
    lignes.push('CANDIDATURE|' + nettoyer(donnees[l], iPrenom) + '|' + tel + '|'
                + nettoyer(donnees[l], iPays) + '|' + nettoyer(donnees[l], iPseudo));
  }
  let envoyees = 0;
  for (let d = 0; d < lignes.length; d += PAR_MESSAGE) {
    const paquet = lignes.slice(d, d + PAR_MESSAGE).join('\n');   // ≤ ~800 caractères, loin des 2000 max
    posterDiscord(url, paquet);
    envoyees += Math.min(PAR_MESSAGE, lignes.length - d);
    Utilities.sleep(700);                       // ménage le rate-limit Discord
  }
  console.log('Rattrapage terminé : ' + envoyees + ' candidature(s) rejouée(s) en '
              + Math.ceil(lignes.length / PAR_MESSAGE) + ' message(s). Vérifie !pipeline.');
}

/** Diagnostic : confirme sur quelle feuille ce script tourne. */
function quelleFeuille() {
  console.log(SpreadsheetApp.getActiveSpreadsheet().getName());
}
