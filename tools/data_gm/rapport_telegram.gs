/**
 * Pilotage G&M — rapport Telegram quotidien v2 (14/09/2026), pour le classeur « Data G&M Créatrices v2 ».
 * Ce que ça envoie chaque matin : par créatrice, la valeur d'un abonné OF et MYM sur 30 jours, la veille,
 * puis CA et profit de la veille. Même style que le rapport actuel, avec OF et MYM séparés.
 *
 * Mise en place (une fois, 3 minutes) : Extensions → Apps Script → coller ce fichier → Paramètres du projet →
 * Propriétés du script : TELEGRAM_TOKEN et TELEGRAM_CHAT_ID (les mêmes que l'ancien script) → exécuter
 * `installerDeclencheur` une fois (autoriser) → c'est fini. `envoyerRapportTelegram` teste l'envoi immédiat.
 *
 * Réglages : CREATRICES = les onglets lus (ordre du rapport) ; MARGE = part nette estimée du CA (le rapport
 * actuel affiche ~28 % : 644 € de profit pour 2 321 € de CA) — à ajuster ici si votre calcul diffère.
 */
const CREATRICES = ["Chloé", "Sophie", "Maddy", "Sarah", "Jade", "Clara"];
const MARGE = 0.28;
const HEURE_ENVOI = 8;           // heure locale du classeur

function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === "envoyerRapportTelegram") ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger("envoyerRapportTelegram").timeBased().everyDays(1).atHour(HEURE_ENVOI).create();
}

function _taux(ss) {
  const v = Number(ss.getSheetByName("Notice").getRange("B3").getValue());
  return (v > 0 && v < 5) ? v : 0.92;
}

function _lire(ss, nom) {
  const f = ss.getSheetByName(nom);
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

function _eur(x) { return Math.round(x).toLocaleString("fr-FR").replace(/ /g, " ") + " €"; }
function _parSub(e, s) { return s ? (e / s).toFixed(2).replace(".", ",") + " €" : "—"; }
function _jour(d) { return Utilities.formatDate(d, Session.getScriptTimeZone(), "dd/MM"); }

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
    const lignes = [];
    if (m.ofS || m.ofE) lignes.push(`OF   30 j : ${String(m.ofS).padStart(5)} subs · ${_eur(m.ofE).padStart(9)} · ${_parSub(m.ofE, m.ofS)}/sub`);
    if (m.myS || m.myE) lignes.push(`MYM  30 j : ${String(m.myS).padStart(5)} subs · ${_eur(m.myE).padStart(9)} · ${_parSub(m.myE, m.myS)}/sub`);
    lignes.push(`Hier      : ${String(h.subs).padStart(5)} subs · ${_eur(h.tot).padStart(9)}`);
    blocs.push({ nom, tot: m.tot, texte: `<b>${nom}</b>\n<pre>${lignes.join("\n")}</pre>` });
  });
  blocs.sort((a, b) => b.tot - a.tot);
  const entete = `📊 <b>G&amp;M — ${_jour(hier)}</b>\n30 derniers jours glissants ➡️ € par abonné, OF et MYM séparés\n————————————\n\n`;
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
