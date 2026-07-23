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
 *  4. Lance `rejouerCandidatures()` UNE fois depuis l'éditeur pour rattraper les
 *     soumissions perdues (le bot déduplique par numéro : rejouer est sans risque).
 *  5. Vérifie dans « Exécutions » : surCandidature doit passer « Terminée ».
 *
 * ROBUSTESSE COLONNES : on lit e.namedValues (titre de question → réponse) et on
 * matche par mots-clés (prénom / whatsapp-téléphone-numéro / pays-résides /
 * discord-pseudo) — l'ordre des colonnes de la feuille n'a aucune importance.
 */

const NB_REJOUER = 25;   // rejouerCandidatures : nombre de dernières lignes rejouées

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
  const prenom = prendre(['prénom', 'prenom']);
  const tel    = prendre(['whatsapp', 'téléphone', 'telephone', 'numéro', 'numero', 'tel']);
  const pays   = prendre(['pays', 'résides', 'resides']);
  const pseudo = prendre(['discord', 'pseudo']);
  if (!tel) { console.warn('Candidature sans numéro exploitable — rien envoyé.'); return; }

  const reponse = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ content: 'CANDIDATURE|' + prenom + '|' + tel + '|' + pays + '|' + pseudo }),
    muteHttpExceptions: true
  });
  console.log('CANDIDATURE postée (' + (prenom || '?') + ') — HTTP ' + reponse.getResponseCode());
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
  const iTel    = idx(['whatsapp', 'téléphone', 'telephone', 'numéro', 'numero', 'tel']);
  const iPays   = idx(['pays', 'résides', 'resides']);
  const iPseudo = idx(['discord', 'pseudo']);
  if (iTel < 0) { console.error('Colonne du numéro introuvable — entêtes : ' + donnees[0].join(' · ')); return; }

  const nettoyer = function (ligne, i) {
    return (i >= 0 && ligne[i]) ? String(ligne[i]).trim().replace(/\|/g, '/') : '';
  };
  let envoyees = 0;
  const debut = Math.max(1, donnees.length - NB_REJOUER);
  for (let l = debut; l < donnees.length; l++) {
    const tel = nettoyer(donnees[l], iTel);
    if (!tel) continue;
    UrlFetchApp.fetch(url, {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify({
        content: 'CANDIDATURE|' + nettoyer(donnees[l], iPrenom) + '|' + tel + '|'
                 + nettoyer(donnees[l], iPays) + '|' + nettoyer(donnees[l], iPseudo)
      }),
      muteHttpExceptions: true
    });
    envoyees++;
    Utilities.sleep(400);                       // ménage le rate-limit Discord
  }
  console.log('Rattrapage terminé : ' + envoyees + ' candidature(s) rejouée(s). Vérifie !pipeline.');
}

/** Diagnostic : confirme sur quelle feuille ce script tourne. */
function quelleFeuille() {
  console.log(SpreadsheetApp.getActiveSpreadsheet().getName());
}
