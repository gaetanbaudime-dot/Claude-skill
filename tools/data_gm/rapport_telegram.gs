/**
 * Pilotage G&M — rapport Telegram quotidien v3 (30/09/2026), pour le classeur « Data G&M Créatrices ».
 * 30/09 (Gaëtan : « une ligne OF, une ligne MYM, une ligne Hier pour chaque créatrice, sauf celles qui n'ont que MYM ; le
 * €/sub n'est pas mesurable comme ça ; sans perturber le formatage, lisible sur téléphone ») : même présentation que le
 * rapport actuel (titre, blocs numérotés, bloc copiable), une créatrice = un titre « Chloé — 23 219 € last 30d », puis
 *             subs     CA €  LTV €
 *       OF    1078    7 731   7,17     (30 derniers jours, $ convertis en € ; LTV = CA ÷ abonnés sur 30 jours)
 *       MYM   1882   15 488   8,23
 *       Hier   105    1 594            (OF + MYM de la veille)
 * Une plateforme sans aucun abonné ni euro sur 30 jours n'a pas de ligne (Maddy : MYM seul ; Sophie : OF seul).
 * Lignes de 26 à 28 caractères : elles tiennent sur un écran de téléphone sans retour à la ligne.
 *
 * Mise en place (une fois, 3 minutes) : Extensions → Apps Script → remplacer le code par ce fichier → Enregistrer →
 * Paramètres du projet → Propriétés du script : TELEGRAM_TOKEN et TELEGRAM_CHAT_ID (déjà là si vous remplacez l'ancien
 * code) → exécuter `installerDeclencheur` une fois (autoriser). `envoyerRapportTelegram` teste l'envoi immédiat.
 *
 * Réglages : CREATRICES = les onglets lus ; MARGE = part nette du CA pour le profit (le rapport actuel : 936 € de profit
 * pour 3 118 € de CA, soit 30 %).
 */
const CREATRICES = ["Chloé", "Sophie", "Maddy", "Sarah", "Jade", "Clara"];
const MARGE = 0.30;
const HEURE_ENVOI = 8;           // heure locale du classeur

function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === "envoyerRapportTelegram") ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger("envoyerRapportTelegram").timeBased().everyDays(1).atHour(HEURE_ENVOI).create();
}

function _taux(ss) {
  const notice = ss.getSheetByName("Notice");                // absent dans l'ancien classeur : 0,92 par défaut
  const v = notice ? Number(notice.getRange("B3").getValue()) : 0;
  return (v > 0 && v < 5) ? v : 0.92;
}

function _cle(t) { return String(t).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "").slice(0, 4); }

function _onglet(ss, nom) {                                   // « Maddy » trouve « Maddie », accents ignorés
  return ss.getSheetByName(nom) || ss.getSheets().find(f => _cle(f.getName()) === _cle(nom)) || null;
}

function _lire(ss, nom) {
  const f = _onglet(ss, nom);
  if (!f) return [];
  const last = f.getLastRow();
  if (last < 5) return [];
  return f.getRange(5, 1, last - 4, 6).getValues()
    .filter(r => r[0] instanceof Date)
    .map(r => ({ d: r[0], ofS: Number(r[1]) || 0, ofUsd: Number(r[2]) || 0, myS: Number(r[4]) || 0, myEur: Number(r[5]) || 0 }));
}

function _somme(lignes, debut, fin, taux) {
  const sel = lignes.filter(l => l.d > debut && l.d <= fin);
  const ofS = sel.reduce((a, l) => a + l.ofS, 0), ofE = sel.reduce((a, l) => a + l.ofUsd, 0) * taux;
  const myS = sel.reduce((a, l) => a + l.myS, 0), myE = sel.reduce((a, l) => a + l.myEur, 0);
  return { ofS, ofE, myS, myE, tot: ofE + myE, subs: ofS + myS };
}

function _eur(x) { return Math.round(x).toLocaleString("fr-FR").replace(/[\u202f\u00a0 ]/g, "\u00a0") + "€"; }
function _parSub(e, s) { return s ? (e / s).toFixed(2).replace(".", ",") + " €" : "—"; }
function _jour(d) { return Utilities.formatDate(d, Session.getScriptTimeZone(), "dd/MM"); }

function _nb(x) { return Math.round(x).toLocaleString("fr-FR").replace(/[\u202f\u00a0 ]/g, "\u00a0"); }
function _ltv(e, s) { return s ? (e / s).toFixed(2).replace(".", ",") : ""; }

// 30/09 (Gaëtan : « la LTV 30 jours par plateforme, sur la même ligne ») : un petit tableau aligné, 26 caractères, titres de
// colonnes en première ligne ; chaque ligne en <code> (police à chasse fixe, sans le bouton « copier » d'un bloc <pre>)
const TETE = `${"".padEnd(4)}${"subs".padStart(6)}${"CA€".padStart(9)}${"LTV€".padStart(7)}`;
function _ligne(libelle, subs, eur, ltv) {
  return `${libelle.padEnd(4)}${String(Math.round(subs)).padStart(6)}${_nb(eur).padStart(9)}${(ltv || "").padStart(7)}`.replace(/\s+$/, "");
}

function construireRapport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const taux = _taux(ss);
  const hier = new Date(); hier.setHours(0, 0, 0, 0); hier.setDate(hier.getDate() - 1);
  const avantHier = new Date(hier); avantHier.setDate(avantHier.getDate() - 1);
  const debut30 = new Date(hier); debut30.setDate(debut30.getDate() - 30);
  const blocs = [], totalHier = { tot: 0 };
  CREATRICES.forEach(nom => {
    const L = _lire(ss, nom);
    const m = _somme(L, debut30, hier, taux), h = _somme(L, avantHier, hier, taux);
    totalHier.tot += h.tot;
    const lignes = [TETE, "─".repeat(26)];                // 30/09 : un trait sous les titres de colonnes
    if (m.ofS || m.ofE) lignes.push(_ligne("OF", m.ofS, m.ofE, _ltv(m.ofE, m.ofS)));
    if (m.myS || m.myE) lignes.push(_ligne("MYM", m.myS, m.myE, _ltv(m.myE, m.myS)));
    lignes.push(_ligne("Hier", h.subs, h.tot));
    blocs.push({ nom, tot: m.tot, texte: `<b>${nom}</b> — ${_eur(m.tot)} last 30d\n${lignes.map(l => `<code>${l}</code>`).join("\n")}` });   // 30/09 : <code> par ligne, plus de bloc ni de bouton « copier »
  });
  blocs.sort((a, b) => b.tot - a.tot);
  const entete = `📊 <b>G&amp;M — ${_jour(hier)}</b>\n30 derniers jours ➡️ OF · MYM · LTV\nHier : ${_jour(hier)}\n————————————\n\n`;
  const corps = blocs.map((b, i) => `${i + 1}. ${b.texte}`).join("\n\n");
  const pied = `\n\n————————————\n💰 <b>CA HIER : ${_eur(totalHier.tot)}</b>\n🏦 <b>PROFIT HIER : ${_eur(totalHier.tot * MARGE)}</b>`;
  return entete + corps + pied;
}

function envoyerRapportTelegram() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty("TELEGRAM_TOKEN"), chat = props.getProperty("TELEGRAM_CHAT_ID");
  if (!token || !chat) throw new Error("TELEGRAM_TOKEN et TELEGRAM_CHAT_ID manquent dans les propriétés du script.");
  const texte = construireRapport();
  UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "post", payload: { chat_id: chat, text: texte, parse_mode: "HTML", disable_web_page_preview: "true" }, muteHttpExceptions: true });
}
