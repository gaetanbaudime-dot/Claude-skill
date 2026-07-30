/**
 * Historique des inputs clippers — récepteur à coller sur le classeur « LOGIN IG / TiKTok ».
 *
 * RÔLE : le bot Discord envoie chaque jour le bilan de chaque compte (Reels publiés, vues,
 * abonnés) ; ce script l'ajoute dans un onglet « Historique ». Une ligne par compte et par jour
 * → tu gardes la courbe complète de chaque clipper, exploitable en tableau croisé dynamique.
 *
 * POURQUOI : le bot stocke déjà 90 jours sur son volume Railway, mais ce volume est technique et
 * volatil. Le Sheet, lui, est ton archive : consultable, filtrable, et elle survit à tout.
 *
 * INSTALLATION (3 min, une seule fois) :
 *  1. Sur le classeur : Extensions > Apps Script > colle ce fichier (nouveau fichier si le projet
 *     contient déjà autre chose) > Enregistrer.
 *  2. Change SECRET ci-dessous pour une phrase à toi (n'importe quoi de long et unique).
 *  3. Déployer > Nouveau déploiement > type « Application Web » :
 *     - Exécuter en tant que : MOI
 *     - Qui a accès : TOUT LE MONDE   (obligatoire pour que le bot puisse écrire ; c'est le
 *       SECRET qui protège, pas l'URL)
 *     > Déployer > autorise > copie l'URL /exec.
 *  4. Sur Railway : SHEET_HISTORIQUE_URL = <l'URL /exec> et SHEET_HISTORIQUE_SECRET = <ton secret>.
 *
 * L'onglet « Historique » est créé automatiquement à la première écriture, avec ses entêtes.
 */

const SECRET = 'change-moi-par-une-phrase-a-toi';
const ONGLET = 'Historique';
const ENTETES = ['Date', 'Clipper', 'Créatrice', 'Compte', 'Plateforme',
                 'Posts 24h', 'Vues 24h', 'Abonnés', 'Δ Abonnés', 'État'];

function doPost(e) {
  try {
    const charge = JSON.parse(e.postData.contents);
    if (charge.secret !== SECRET) {
      return reponse({ ok: false, erreur: 'secret invalide' });
    }
    const lignes = charge.lignes || [];
    if (!lignes.length) {
      return reponse({ ok: true, ajoutees: 0 });
    }
    const classeur = SpreadsheetApp.getActiveSpreadsheet();
    let feuille = classeur.getSheetByName(ONGLET);
    if (!feuille) {
      feuille = classeur.insertSheet(ONGLET);
      feuille.appendRow(ENTETES);
      feuille.getRange(1, 1, 1, ENTETES.length).setFontWeight('bold');
      feuille.setFrozenRows(1);
    }
    // Anti-doublon : si le bot rejoue la même journée, on efface d'abord les lignes de cette date.
    const dateDuLot = String(lignes[0][0] || '');
    if (dateDuLot) {
      const existantes = feuille.getDataRange().getValues();
      for (let i = existantes.length - 1; i >= 1; i--) {
        const d = existantes[i][0];
        const texte = (d instanceof Date) ? Utilities.formatDate(d, 'UTC', 'yyyy-MM-dd') : String(d);
        if (texte === dateDuLot) feuille.deleteRow(i + 1);
      }
    }
    feuille.getRange(feuille.getLastRow() + 1, 1, lignes.length, ENTETES.length).setValues(lignes);
    return reponse({ ok: true, ajoutees: lignes.length });
  } catch (erreur) {
    return reponse({ ok: false, erreur: String(erreur) });
  }
}

function reponse(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet))
                       .setMimeType(ContentService.MimeType.JSON);
}

/** Diagnostic : confirme le classeur et l'état de l'onglet. */
function verifierHistorique() {
  const classeur = SpreadsheetApp.getActiveSpreadsheet();
  const feuille = classeur.getSheetByName(ONGLET);
  console.log('Classeur : ' + classeur.getName());
  console.log(feuille ? ('Onglet « ' + ONGLET + ' » : ' + (feuille.getLastRow() - 1) + ' ligne(s)')
                      : ('Onglet « ' + ONGLET + ' » pas encore créé (normal avant le 1er envoi)'));
}
