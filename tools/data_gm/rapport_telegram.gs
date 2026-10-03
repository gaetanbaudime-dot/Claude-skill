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
 *
 * 03/10 (dernier rapport reçu : 29/09, la veille du collage de la v3 ; Gaëtan : « rétablir ce bot afin que Maxence voie tous
 * les jours les LTV ») : la panne ne vient pas du classeur (saisi jusqu'au 02/10). Cause probable : l'ancien déclencheur
 * appelle une fonction de l'ancien code qui n'existe plus, et `installerDeclencheur` n'a pas été lancé. Donc :
 * `installerDeclencheur` retire aussi les déclencheurs orphelins ; les propriétés de l'ancien script sont reconnues même sous
 * un autre nom ; une erreur Telegram fait échouer l'exécution (visible dans « Exécutions ») au lieu de passer en silence ;
 * une erreur de construction envoie une alerte dans le canal ; le pied signale les créatrices dont la veille n'est pas saisie.
 * `diagnostic` (à lancer une fois) écrit dans le journal les déclencheurs, les propriétés et la dernière date saisie, puis
 * envoie le rapport.
 */
const CREATRICES = ["Chloé", "Sophie", "Maddy", "Sarah", "Jade", "Clara"];
const MARGE = 0.30;
const HEURE_ENVOI = 8;           // heure locale du classeur
const PREMIERE_LIGNE = 3;        // 03/10 : « 1 juillet » est en ligne 3 (titres en lignes 1-2)

function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(t => {
    const f = t.getHandlerFunction();
    if (f === "envoyerRapportTelegram" || typeof globalThis[f] !== "function") ScriptApp.deleteTrigger(t);   // orphelins compris
  });
  ScriptApp.newTrigger("envoyerRapportTelegram").timeBased().everyDays(1).atHour(HEURE_ENVOI).create();
}

// 03/10 : l'ancien script « Pilotage G&M » rangeait peut-être le jeton et le canal sous d'autres noms → on les reconnaît
function _proprietes() {
  const p = PropertiesService.getScriptProperties().getProperties();
  const cles = Object.keys(p);
  const token = p.TELEGRAM_TOKEN || p[cles.find(k => /token/i.test(k))];
  const chat = p.TELEGRAM_CHAT_ID || p[cles.find(k => /chat|canal|channel/i.test(k))];
  return { token, chat, cles };
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
  if (last < PREMIERE_LIGNE) return [];
  return f.getRange(PREMIERE_LIGNE, 1, last - PREMIERE_LIGNE + 1, 6).getValues()
    .filter(r => r[0] instanceof Date)
    .map(r => ({ d: r[0], ofS: Number(r[1]) || 0, ofUsd: Number(r[2]) || 0, myS: Number(r[4]) || 0, myEur: Number(r[5]) || 0,
                 vide: [1, 2, 4, 5].every(i => r[i] === "") }));   // Notice, règle 3 : une case vide = « non saisi »
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
// colonnes en première ligne (le bouton « copier » du bloc Telegram se pose dessus, plus sur un chiffre)
const TETE = `${"".padEnd(4)}${"subs".padStart(6)}${"CA€".padStart(9)}${"LTV€".padStart(7)}  `;
function _ligne(libelle, subs, eur, ltv) {
  return `${libelle.padEnd(4)}${String(Math.round(subs)).padStart(6)}${_nb(eur).padStart(9)}${(ltv || "").padStart(7)}`.replace(/\s+$/, "");
}

function construireRapport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const taux = _taux(ss);
  const hier = new Date(); hier.setHours(0, 0, 0, 0); hier.setDate(hier.getDate() - 1);
  const avantHier = new Date(hier); avantHier.setDate(avantHier.getDate() - 1);
  const debut30 = new Date(hier); debut30.setDate(debut30.getDate() - 30);
  const blocs = [], totalHier = { tot: 0 }, nonSaisi = [];
  CREATRICES.forEach(nom => {
    const L = _lire(ss, nom);
    const m = _somme(L, debut30, hier, taux), h = _somme(L, avantHier, hier, taux);
    totalHier.tot += h.tot;
    const ligneHier = L.find(l => l.d > avantHier && l.d <= hier);
    if ((m.subs || m.tot) && (!ligneHier || ligneHier.vide)) nonSaisi.push(nom);
    const lignes = [TETE, "┈".repeat(26)];                // 30/09 : un trait fin sous les titres de colonnes
    if (m.ofS || m.ofE) lignes.push(_ligne("OF", m.ofS, m.ofE, _ltv(m.ofE, m.ofS)));
    if (m.myS || m.myE) lignes.push(_ligne("MYM", m.myS, m.myE, _ltv(m.myE, m.myS)));
    lignes.push(_ligne("Hier", h.subs, h.tot));
    blocs.push({ nom, tot: m.tot, texte: `<b>${nom}</b> — ${_eur(m.tot)} last 30d\n<pre>${lignes.join("\n")}</pre>` });
  });
  blocs.sort((a, b) => b.tot - a.tot);
  const entete = `📊 <b>G&amp;M — ${_jour(hier)}</b>\n30 derniers jours ➡️ OF · MYM · LTV\nHier : ${_jour(hier)}\n————————————\n\n`;
  const corps = blocs.map((b, i) => `${i + 1}. ${b.texte}`).join("\n\n");
  const alerte = nonSaisi.length ? `\n⚠️ Hier non saisi : ${nonSaisi.join(", ")}` : "";
  const pied = `\n\n————————————\n💰 <b>CA HIER : ${_eur(totalHier.tot)}</b>\n🏦 <b>PROFIT HIER : ${_eur(totalHier.tot * MARGE)}</b>${alerte}`;
  return entete + corps + pied;
}

function _envoyer(token, chat, texte) {
  const r = UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "post", payload: { chat_id: chat, text: texte, parse_mode: "HTML", disable_web_page_preview: "true" }, muteHttpExceptions: true });
  const rep = JSON.parse(r.getContentText() || "{}");
  if (!rep.ok) throw new Error(`Telegram refuse l'envoi (${r.getResponseCode()}) : ${rep.description || r.getContentText()}`);
}

function envoyerRapportTelegram() {
  const { token, chat } = _proprietes();
  if (!token || !chat) throw new Error("TELEGRAM_TOKEN et TELEGRAM_CHAT_ID manquent dans les propriétés du script.");
  let texte;
  try { texte = construireRapport(); }
  catch (e) { _envoyer(token, chat, `⚠️ Rapport G&amp;M non construit : ${String(e.message || e).replace(/[<>&]/g, "")}`); throw e; }
  _envoyer(token, chat, texte);
}

// 03/10 : à lancer une fois depuis l'éditeur (▶ Exécuter), le résultat est dans le « Journal d'exécution »
function diagnostic() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log("Déclencheurs : " + (ScriptApp.getProjectTriggers().map(t => `${t.getHandlerFunction()}${typeof globalThis[t.getHandlerFunction()] === "function" ? "" : " (ORPHELIN)"}`).join(", ") || "aucun"));
  const { token, chat, cles } = _proprietes();
  Logger.log(`Propriétés : ${cles.join(", ") || "aucune"} → jeton ${token ? "trouvé" : "MANQUANT"}, canal ${chat ? "trouvé" : "MANQUANT"}`);
  CREATRICES.forEach(nom => {
    const L = _lire(ss, nom).filter(l => !l.vide);
    Logger.log(`${nom} : ${_onglet(ss, nom) ? "onglet trouvé" : "ONGLET ABSENT"}, dernière date saisie ${L.length ? _jour(L[L.length - 1].d) : "aucune"}`);
  });
  envoyerRapportTelegram();
  Logger.log("Rapport envoyé.");
}
