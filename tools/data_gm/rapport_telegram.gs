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
 * Réglages : CREATRICES = les onglets lus ; taux de commission et de frais : voir le 03/10 plus bas.
 *
 * 03/10 (dernier rapport reçu : 29/09, la veille du collage de la v3 ; Gaëtan : « rétablir ce bot afin que Maxence voie tous
 * les jours les LTV ») : la panne ne vient pas du classeur (saisi jusqu'au 02/10). Cause probable : l'ancien déclencheur
 * appelle une fonction de l'ancien code qui n'existe plus, et `installerDeclencheur` n'a pas été lancé. Donc :
 * `installerDeclencheur` retire aussi les déclencheurs orphelins ; les propriétés de l'ancien script sont reconnues même sous
 * un autre nom ; une erreur Telegram fait échouer l'exécution (visible dans « Exécutions ») au lieu de passer en silence ;
 * une erreur de construction envoie une alerte dans le canal ; le pied signale les créatrices dont la veille n'est pas saisie.
 * `diagnostic` (à lancer une fois) écrit dans le journal les déclencheurs, les propriétés et la dernière date saisie, puis
 * envoie le rapport.
 *
 * 03/10 (Gaëtan : « commission d'agence sur le CA : Chloé 40 %, Sarah, Sophie, Maddie, Clara 50 %, Jade 60 % ; ensuite tu
 * retires 15 % de CA de dépenses (frais + chatting) et on a notre profit précisément ») : la marge unique de 30 % disparaît.
 * Profit = CA × (commission − 15 %). `creerOngletCommission` (à lancer une fois) crée l'onglet « Commission & profit » :
 * taux modifiables (cases jaunes), 30 derniers jours, hier, commission et profit par mois. Le rapport lit ses taux dans cet
 * onglet (repli : COMMISSIONS et FRAIS ci-dessous) et donne en pied la commission et le profit d'hier et des 30 jours.
 */
const CREATRICES = ["Chloé", "Sophie", "Maddy", "Sarah", "Jade", "Clara"];
const COMMISSIONS = { "Chloé": 0.40, "Sophie": 0.50, "Maddy": 0.50, "Sarah": 0.50, "Jade": 0.60, "Clara": 0.50 };
const FRAIS = 0.15;              // frais + chatting, en part du CA
const ONGLET_PROFIT = "Commission & profit";
// 03/10 (Gaëtan : « fais en sorte qu'il s'envoie tous les jours proprement ») : un déclencheur toutes les heures appelle
// `envoiQuotidien`, qui envoie UNE fois par jour : dès HEURE_ENVOI si la veille est saisie pour toutes les créatrices actives,
// sinon il attend la saisie jusqu'à HEURE_LIMITE puis envoie quand même (avec « ⚠️ Hier non saisi »). Un envoi raté (Telegram,
// Google) est retenté l'heure suivante. Les heures et les jours sont ceux du FUSEAU DU CLASSEUR (Dubaï), quel que soit celui
// du projet Apps Script (Paris le 03/10).
const HEURE_ENVOI = 8, HEURE_LIMITE = 12;
const PREMIERE_LIGNE = 3;        // 03/10 : « 1 juillet » est en ligne 3 (titres en lignes 1-2)

function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(t => {
    const f = t.getHandlerFunction();
    if (["envoyerRapportTelegram", "envoiQuotidien"].includes(f) || typeof globalThis[f] !== "function") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("envoiQuotidien").timeBased().everyHours(1).create();
}

function envoiQuotidien() {
  const ss = SpreadsheetApp.getActiveSpreadsheet(), tz = ss.getSpreadsheetTimeZone(), maintenant = new Date();
  const jour = _numJour(maintenant, tz), heure = Number(Utilities.formatDate(maintenant, tz, "H"));
  const props = PropertiesService.getScriptProperties();
  if (Number(props.getProperty("DERNIER_ENVOI")) === jour || heure < HEURE_ENVOI) return;    // déjà envoyé, ou trop tôt
  if (heure < HEURE_LIMITE && _nonSaisis(ss, jour - 1).length) return;                       // on attend la saisie de la veille
  envoyerRapportTelegram();                                                                    // marque le jour lui-même
}

// créatrices actives sur 30 jours dont la ligne de la veille est vide (Notice, règle 3 : vide = « non saisi »)
function _nonSaisis(ss, hier) {
  return CREATRICES.filter(nom => {
    const L = _lire(ss, nom);
    const active = L.some(l => l.n > hier - 30 && l.n <= hier && !l.vide), ligne = L.find(l => l.n === hier);
    return active && (!ligne || ligne.vide);
  });
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
    .map(r => ({ n: _numJour(r[0], ss.getSpreadsheetTimeZone()), ofS: Number(r[1]) || 0, ofUsd: Number(r[2]) || 0, myS: Number(r[4]) || 0, myEur: Number(r[5]) || 0,
                 vide: [1, 2, 4, 5].every(i => r[i] === "") }));   // Notice, règle 3 : une case vide = « non saisi »
}

function _somme(lignes, debut, fin, taux) {
  const sel = lignes.filter(l => l.n > debut && l.n <= fin);
  const ofS = sel.reduce((a, l) => a + l.ofS, 0), ofE = sel.reduce((a, l) => a + l.ofUsd, 0) * taux;
  const myS = sel.reduce((a, l) => a + l.myS, 0), myE = sel.reduce((a, l) => a + l.myEur, 0);
  return { ofS, ofE, myS, myE, tot: ofE + myE, subs: ofS + myS };
}

function _eur(x) { return Math.round(x).toLocaleString("fr-FR").replace(/[\u202f\u00a0 ]/g, "\u00a0") + "€"; }
function _parSub(e, s) { return s ? (e / s).toFixed(2).replace(".", ",") + " €" : "—"; }
// 03/10 (Gaëtan : « ça dit hier 2 octobre et ça affiche les stats du 1 octobre ») : le projet Apps Script et le classeur
// n'ont pas le même fuseau ; une date du classeur (minuit, fuseau du classeur) tombait la veille côté script. Les jours se
// comparent maintenant en numéro de jour du calendrier, tout dans le fuseau du classeur (réglé sur Dubaï le 03/10).
function _numJour(d, tz) {
  const [a, m, j] = Utilities.formatDate(d, tz, "yyyy-MM-dd").split("-").map(Number);
  return Date.UTC(a, m - 1, j) / 864e5;
}
function _jour(n) { return Utilities.formatDate(new Date(n * 864e5), "UTC", "dd/MM"); }

function _nb(x) { return Math.round(x).toLocaleString("fr-FR").replace(/[\u202f\u00a0 ]/g, "\u00a0"); }
function _ltv(e, s) { return s ? (e / s).toFixed(2).replace(".", ",") : ""; }

// 30/09 (Gaëtan : « la LTV 30 jours par plateforme, sur la même ligne ») : un petit tableau aligné, 26 caractères, titres de
// colonnes en première ligne (le bouton « copier » du bloc Telegram se pose dessus, plus sur un chiffre)
// 03/10 (Gaëtan : « si subs last 30d < 800 : subs en rouge ; si > 800 et LTV < 15 € : LTV en rouge ; si > 800 et LTV > 15 € :
// plateforme en vert ») : Telegram ne colore pas le texte → pastille 🔴 / 🟢 collée à la valeur visée, sur les lignes OF et MYM
// (pas sur « Hier »). 800 tout rond compte comme « au moins 800 », 15 € tout rond comme « au moins 15 € ». Colonnes élargies
// pour garder l'alignement (une pastille occupe deux caractères) : 28 caractères. 03/10 : palier 🟡 sur la LTV entre 8 et
// 15 € (Gaëtan : « ajoute le palier jaune à 8 € » ; la règle est épinglée dans le groupe, pas de légende dans le rapport).
// 03/10 (Gaëtan : « au-dessus de 800 subs, 15 € de LTV, c'est pour OnlyFans ; MYM a du trafic interne en masse mais peu
// qualifié, LTV à 3 € : on met 15 € sur OF et 10 € sur MYM ») : cibles et paliers de LTV propres à chaque plateforme.
const SEUIL_SUBS = 800;
const CIBLES = { OF: { jaune: 8, vert: 15 }, MYM: { jaune: 5, vert: 10 } };
function _larg(t) { return [...t].reduce((a, ch) => a + (ch.codePointAt(0) > 0xffff ? 2 : 1), 0); }
function _gauche(t, n) { return t + " ".repeat(Math.max(0, n - _larg(t))); }
function _droite(t, n) { return " ".repeat(Math.max(0, n - _larg(t))) + t; }
const TETE = `${_gauche("", 5)}${_droite("subs", 7)}${_droite("CA€", 8)}${_droite("LTV€", 8)}`;
function _ligne(libelle, subs, eur, ltv) {
  let lib = libelle, s = String(Math.round(subs)), l = ltv || "";
  if (ltv !== undefined) {                                  // lignes OF / MYM : 800 subs, puis la LTV cible de la plateforme
    const valeur = subs ? eur / subs : 0, cible = CIBLES[libelle];
    if (subs < SEUIL_SUBS) s = "🔴" + s;
    else if (valeur < cible.jaune) l = "🔴" + l;
    else if (valeur < cible.vert) l = "🟡" + l;
    else lib = "🟢" + lib;
  }
  return `${_gauche(lib, 5)}${_droite(s, 7)}${_droite(_nb(eur), 8)}${_droite(l, 8)}`.replace(/\s+$/, "");
}

function construireRapport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const taux = _taux(ss);
  const hier = _numJour(new Date(), ss.getSpreadsheetTimeZone()) - 1;     // la veille, au calendrier du classeur
  const avantHier = hier - 1, debut30 = hier - 30;                         // 30 jours = du J-30 à hier inclus
  const tx = _tauxProfit(ss);
  const blocs = [], totalHier = { tot: 0, com: 0, profit: 0 }, total30 = { com: 0, profit: 0 }, nonSaisi = _nonSaisis(ss, hier);
  CREATRICES.forEach(nom => {
    const L = _lire(ss, nom);
    const m = _somme(L, debut30, hier, taux), h = _somme(L, avantHier, hier, taux);
    const { com, frais } = tx[nom];
    totalHier.tot += h.tot; totalHier.com += h.tot * com; totalHier.profit += h.tot * (com - frais);
    total30.com += m.tot * com; total30.profit += m.tot * (com - frais);
    const lignes = [TETE, "┈".repeat(28)];                // 30/09 : un trait fin sous les titres de colonnes
    if (m.ofS || m.ofE) lignes.push(_ligne("OF", m.ofS, m.ofE, _ltv(m.ofE, m.ofS)));
    if (m.myS || m.myE) lignes.push(_ligne("MYM", m.myS, m.myE, _ltv(m.myE, m.myS)));
    lignes.push(_ligne("Hier", h.subs, h.tot));
    blocs.push({ nom, tot: m.tot, texte: `<b>${nom}</b> — ${_eur(m.tot)} last 30d\n<pre>${lignes.join("\n")}</pre>` });
  });
  blocs.sort((a, b) => b.tot - a.tot);
  const entete = `📊 <b>G&amp;M — ${_jour(hier)}</b>\n30 derniers jours ➡️ OF · MYM · LTV\nHier : ${_jour(hier)}\n————————————\n\n`;
  const corps = blocs.map((b, i) => `${i + 1}. ${b.texte}`).join("\n\n");
  // 03/10 (Gaëtan) : pied réduit à trois lignes séparées par une ligne vide, sans la commission
  const alerte = nonSaisi.length ? `\n\n⚠️ Hier non saisi : ${nonSaisi.join(", ")}` : "";
  const pied = `\n\n————————————\n💰 <b>CA HIER : ${_eur(totalHier.tot)}</b>\n\n🏦 <b>PROFIT HIER : ${_eur(totalHier.profit)}</b>` +
    `\n\n📆 Profit 30 j : ${_eur(total30.profit)}${alerte}`;
  return entete + corps + pied;
}

// 03/10 : taux de commission et de frais lus dans l'onglet « Commission & profit » (A4:C9), sinon les constantes
function _tauxProfit(ss) {
  const tx = {};
  CREATRICES.forEach(nom => { tx[nom] = { com: COMMISSIONS[nom], frais: FRAIS }; });
  const f = ss.getSheetByName(ONGLET_PROFIT);
  if (f) f.getRange(4, 1, CREATRICES.length, 3).getValues().forEach(([nom, com, frais]) => {
    const cible = CREATRICES.find(c => _cle(c) === _cle(nom));
    if (cible && typeof com === "number" && typeof frais === "number") tx[cible] = { com, frais };
  });
  return tx;
}

// 03/10 (premier essai : #ERROR! partout dans le classeur en français) : le séparateur d'arguments accepté par le classeur
// est testé d'abord (« , » ou « ; »), toutes les formules l'utilisent ; les mois sont des formules DATE() (une date écrite par
// le script prenait le fuseau du projet et tombait la veille).
function _separateur(f) {
  const essai = f.getRange("Z1");
  for (const sep of [",", ";"]) {
    essai.setFormula(`=SUM(1${sep}1)`); SpreadsheetApp.flush();
    if (essai.getValue() === 2) { essai.clear(); return sep; }
  }
  essai.clear();
  throw new Error("Le classeur n'accepte ni « , » ni « ; » comme séparateur de formule.");
}

function _ecrivain(f) {
  const sep = _separateur(f);
  return { sep, fx: (a1, t) => f.getRange(a1).setFormula(sep === "," ? t : t.replace(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/g, ";")) };
}

// ============================================================================================================================
// TABLEAUX DE BORD (03/10/2026, Gaëtan : « 3 ou 4 dashboards lisibles à 75 % de zoom, que je peux partager avec Maxence, pour
// savoir créatrice par créatrice si on doit scaler le chatting ou le marketing, l'objectif et ce que ça rapporte »).
// Quatre onglets, reconstruits EN PLACE (jamais supprimés : les formules qui pointent vers eux ne cassent pas, les cadenas
// restent) par `construireDashboards` :
//   Synthèse              — par créatrice et plateforme : 30 j, 90 j ; puis UNE décision par créatrice (levier, objectif, gains)
//   Commission & profit   — taux (cases jaunes, lus aussi par le rapport Telegram), 30 j et 90 j, commission et profit par mois
//   CA par mois           — CA total, OF et MYM par mois et par créatrice, total et part de l'agence
//   Subs & LTV par mois   — nouveaux subs et LTV par mois, total / OF / MYM
// Règles « immuables » (2e version du 03/10, voir alignerSynthese) : sur 30 jours et par créatrice, subs < 800 → MARKETING ;
// sinon une plateforme sous sa LTV cible (OF 15 €, MYM 10 €) → CHATTING ; sinon → SCALER. Couleurs de LTV par plateforme :
// OF rouge < 8 €, jaune 8-15 €, vert ≥ 15 € ; MYM rouge < 5 €, jaune 5-10 €, vert ≥ 10 €. Sur 90 jours, seuil de subs × 3.
// Dollars : le CA OF ($) est converti au taux du jour de Notice!B3, partout (comme les colonnes « TOTAL € » des onglets).
// Fenêtres « 30 / 90 jours » : jours complets, du J-30 (J-90) à hier. Mois : mois civils, juillet → décembre 2026.
// ============================================================================================================================
const T_SOMBRE = "#3D3D5C", T_CLAIR = "#F2F2F5", T_GRIS = "#E8E8EC", T_TUILE = "#F4F4F9";
const C_ROUGE = "#F4CCCC", C_JAUNE = "#FFF2CC", C_VERT = "#D9EAD3", C_BLEU = "#CFE2F3", C_ROSE = "#EAD1DC";
const F_SUBS = '#,##0;-#,##0;"—"', F_EUR = '#,##0 "€";-#,##0 "€";"—"', F_LTV = '0.00 "€"', F_PCT = "0%";
const ONGLET_CA = "CA par mois", ONGLET_SUBS = "Subs & LTV par mois";
const MOIS_DEBUT = [2026, 7], NB_MOIS = 6;

function _lettre(n) { let s = ""; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = (n - m - 1) / 26; } return s; }

// créatrices présentes, rangées par CA 30 jours décroissant (comme le rapport) ; idx = ligne de taux dans Commission & profit
function _ordre(ss) {
  const taux = _taux(ss), hier = _numJour(new Date(), ss.getSpreadsheetTimeZone()) - 1;
  return CREATRICES.map((nom, i) => ({ nom, o: _onglet(ss, nom), t: 4 + i })).filter(c => c.o)
    .map(c => ({ ...c, ca: _somme(_lire(ss, c.nom), hier - 30, hier, taux).tot })).sort((a, b) => b.ca - a.ca);
}

// onglet repris en place (ou créé après `apres`) : contenu, formats, fusions et couleurs conditionnelles remis à zéro
function _feuille(ss, nom, apres) {
  let f = ss.getSheetByName(nom);
  if (!f) f = ss.insertSheet(nom, apres ? apres.getIndex() : ss.getNumSheets());
  else {
    const tout = f.getRange(1, 1, f.getMaxRows(), f.getMaxColumns());
    tout.breakApart(); tout.clear();
    f.setConditionalFormatRules([]);
  }
  f.setHiddenGridlines(true); f.setFrozenRows(0);
  return f;
}

// cadenas : seul le propriétaire (et la personne qui lance le script) modifie ; rien n'est touché si l'onglet en a déjà un
function _proteger(f, texte) {
  try {
    if (f.getProtections(SpreadsheetApp.ProtectionType.SHEET).length) return;
    const p = f.protect().setDescription(texte);
    p.removeEditors(p.getEditors());
    if (p.canDomainEdit()) p.setDomainEdit(false);
  } catch (e) { Logger.log(`Cadenas non posé sur « ${f.getName()} » : ${e.message}`); }
}

function _bandeau(f, a1, texte) {
  f.getRange(a1).merge().setValue(texte).setBackground(T_SOMBRE).setFontColor("#FFFFFF").setFontWeight("bold").setFontSize(13)
    .setVerticalAlignment("middle");
  f.setRowHeight(f.getRange(a1).getRow(), 30);
}
function _legende(f, a1, texte) {
  f.getRange(a1).merge().setValue(texte).setFontSize(9).setFontStyle("italic").setFontColor("#55556A").setWrap(true)
    .setVerticalAlignment("middle");
}
// en-tête sombre ; une cellule vide ("") reste blanche (colonne d'espace)
function _tete(f, ligne, col, libelles) {
  libelles.forEach((t, i) => {
    const c = f.getRange(ligne, col + i);
    if (t === "") return;
    c.setValue(t).setBackground(T_SOMBRE).setFontColor("#FFFFFF").setFontWeight("bold").setHorizontalAlignment("center");
  });
}
function _titreBloc(f, a1, texte) {
  f.getRange(a1).merge().setValue(texte).setFontWeight("bold").setFontColor(T_SOMBRE).setFontSize(11)
    .setBorder(null, null, true, null, null, null, T_SOMBRE, SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
}

// expressions de lecture des onglets créatrices (colonnes : A date, B subs OF, C CA OF $, E subs MYM, F CA MYM €, H subs, I CA €)
function _src(c) {
  const r = col => `'${c.o.getName()}'!$${col}$3:$${col}$1000`;
  const jours = j => `${r("A")},">="&TODAY()-${j},${r("A")},"<="&TODAY()-1`;
  const mois = h => `${r("A")},">="&${h},${r("A")},"<"&EDATE(${h},1)`;
  const v = (col, crit, usd) => `SUMIFS(${r(col)},${crit})${usd ? "*Notice!$B$3" : ""}`;
  return {
    subsOF: k => v("B", k), caOF: k => v("C", k, true), subsMYM: k => v("E", k), caMYM: k => v("F", k),
    subs: k => v("H", k), ca: k => v("I", k), jours, mois };
}

// ---------------------------------------------------------------------------------------------- Commission & profit
function creerOngletCommission() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const garde = ss.getSheetByName(ONGLET_PROFIT) ? _tauxProfit(ss) : null;     // taux saisis à la main : conservés
  const f = _feuille(ss, ONGLET_PROFIT, ss.getSheetByName("Synthèse"));
  const { sep, fx } = _ecrivain(f), crea = _ordre(ss), n = crea.length;
  [110, 88, 88, 88, 88, 88, 88, 20, 110, 88, 88, 88, 88, 88, 88].forEach((w, i) => f.setColumnWidth(i + 1, w));
  _bandeau(f, "A1:O1", "COMMISSION & PROFIT — mise à jour automatique ; seules les cases jaunes (taux) se modifient");
  _legende(f, "A2:O2", "Profit = CA × (commission agence − frais & chatting). Les taux jaunes sont lus aussi par la Synthèse et par le " +
    "rapport Telegram. OF converti en € au taux du jour (Notice!B3). 30 / 90 jours = jours complets jusqu'à hier.");

  // taux (A3:D9, ordre fixe de CREATRICES : le rapport Telegram les lit par prénom)
  _tete(f, 3, 1, ["Créatrice", "Commission", "Frais + chat", "Marge nette"]);
  CREATRICES.forEach((nom, i) => {
    const l = 4 + i, tx = garde ? garde[nom] : { com: COMMISSIONS[nom], frais: FRAIS };
    f.getRange(l, 1, 1, 3).setValues([[nom, tx.com, tx.frais]]);
    fx(`D${l}`, `=B${l}-C${l}`);
  });
  f.getRange(4, 2, CREATRICES.length, 2).setBackground("#FFF9C4");
  f.getRange(4, 2, CREATRICES.length, 3).setNumberFormat(F_PCT).setHorizontalAlignment("center");
  f.getRange(4, 4, CREATRICES.length, 1).setFontWeight("bold");

  // blocs 30 j (A11:G19) et 90 j (I11:O19) — le profit 30 j de l'agence est en E(13 + nb de créatrices), lu par la Synthèse
  const l0 = 13, lt = l0 + n;
  [[1, 30, "30 DERNIERS JOURS"], [9, 90, "90 DERNIERS JOURS"]].forEach(([c0, j, titre]) => {
    const L = k => _lettre(c0 + k);
    _titreBloc(f, `${L(0)}11:${L(6)}11`, titre);
    _tete(f, 12, c0, ["Créatrice", "CA", "Commission", "Frais + chat", "Profit", "Nouveaux subs", "Profit / sub"]);
    crea.forEach((c, i) => {
      const l = l0 + i, s = _src(c);
      f.getRange(l, c0).setValue(c.nom);
      fx(`${L(1)}${l}`, `=${s.ca(s.jours(j))}`);
      fx(`${L(2)}${l}`, `=${L(1)}${l}*$B$${c.t}`);
      fx(`${L(3)}${l}`, `=${L(1)}${l}*$C$${c.t}`);
      fx(`${L(4)}${l}`, `=${L(2)}${l}-${L(3)}${l}`);
      fx(`${L(5)}${l}`, `=${s.subs(s.jours(j))}`);
      fx(`${L(6)}${l}`, `=IFERROR(${L(4)}${l}/${L(5)}${l},"—")`);
    });
    f.getRange(lt, c0).setValue("TOTAL");
    [1, 2, 3, 4, 5].forEach(k => fx(`${L(k)}${lt}`, `=SUM(${L(k)}${l0}:${L(k)}${lt - 1})`));
    fx(`${L(6)}${lt}`, `=IFERROR(${L(4)}${lt}/${L(5)}${lt},"—")`);
    f.getRange(l0, c0 + 1, n + 1, 4).setNumberFormat(F_EUR);
    f.getRange(l0, c0 + 5, n + 1, 1).setNumberFormat(F_SUBS);
    f.getRange(l0, c0 + 6, n + 1, 1).setNumberFormat(F_LTV).setHorizontalAlignment("right");
    f.getRange(l0, c0 + 4, n + 1, 1).setFontWeight("bold");
    f.getRange(lt, c0, 1, 7).setFontWeight("bold").setBackground(T_GRIS);
  });

  // commission par mois (A21:G29) et profit par mois (I21:O29)
  [[1, "COMMISSION PAR MOIS", "B"], [9, "PROFIT PAR MOIS", "D"]].forEach(([c0, titre, colTaux]) =>
    _blocMois(f, fx, 21, c0, titre, crea, (c, h) => `=${_src(c).ca(_src(c).mois(h))}*$${colTaux}$${c.t}`, null, F_EUR, false));
  _proteger(f, "Commission & profit — mise à jour automatique (seuls les taux jaunes se modifient)");
  Logger.log(`Onglet « ${ONGLET_PROFIT} » reconstruit (taux ${garde ? "gardés" : "par défaut"}), séparateur « ${sep} ».`);
}

// bloc mensuel : bandeau (ligne r), en-tête (r+1 : Créatrice + mois [+ Total, Part]), une ligne par créatrice, TOTAL.
// cellule(c, "B$x") → formule d'une créatrice pour le mois de l'en-tête ; totalMois(h) → formule de la ligne TOTAL (sinon SOMME)
function _blocMois(f, fx, r, c0, titre, crea, cellule, totalMois, fmt, avecTotal) {
  const L = k => _lettre(c0 + k), n = crea.length, lh = r + 1, l0 = r + 2, lt = l0 + n, larg = 7 + (avecTotal ? 2 : 0);
  _titreBloc(f, `${L(0)}${r}:${L(larg - 1)}${r}`, titre);
  _tete(f, lh, c0, ["Créatrice", "", "", "", "", "", ""].concat(avecTotal ? ["Total", "Part"] : []));
  for (let k = 1; k <= NB_MOIS; k++) {
    fx(`${L(k)}${lh}`, `=DATE(${MOIS_DEBUT[0]},${MOIS_DEBUT[1] + k - 1},1)`);
  }
  f.getRange(lh, c0, 1, larg).setBackground(T_SOMBRE).setFontColor("#FFFFFF").setFontWeight("bold").setHorizontalAlignment("center");
  f.getRange(lh, c0 + 1, 1, NB_MOIS).setNumberFormat("mmmm");
  crea.forEach((c, i) => {
    const l = l0 + i;
    f.getRange(l, c0).setValue(c.nom);
    for (let k = 1; k <= NB_MOIS; k++) fx(`${L(k)}${l}`, cellule(c, `${L(k)}$${lh}`));
  });
  f.getRange(lt, c0).setValue("TOTAL");
  for (let k = 1; k <= NB_MOIS; k++) {
    fx(`${L(k)}${lt}`, totalMois ? totalMois(`${L(k)}$${lh}`) : `=SUM(${L(k)}${l0}:${L(k)}${lt - 1})`);
  }
  if (avecTotal) {
    for (let l = l0; l <= lt; l++) {
      fx(`${L(7)}${l}`, `=SUM(${L(1)}${l}:${L(NB_MOIS)}${l})`);
      fx(`${L(8)}${l}`, `=IFERROR(${L(7)}${l}/${L(7)}$${lt},0)`);
    }
    f.getRange(l0, c0 + 8, n + 1, 1).setNumberFormat(F_PCT).setHorizontalAlignment("center");
    f.getRange(l0, c0 + 7, n + 1, 1).setFontWeight("bold").setBackground(T_CLAIR);
  }
  f.getRange(l0, c0 + 1, n + 1, NB_MOIS + (avecTotal ? 1 : 0)).setNumberFormat(fmt);
  if (fmt === F_LTV) f.getRange(l0, c0 + 1, n + 1, NB_MOIS).setHorizontalAlignment("right");
  f.getRange(lt, c0, 1, larg).setFontWeight("bold").setBackground(T_GRIS);
  return f.getRange(l0, c0 + 1, n + 1, NB_MOIS);                // plage des valeurs (pour les couleurs)
}

// --------------------------------------------------------------------------------------------------------- Synthèse
// 03/10 (2e version, Gaëtan : « un levier par créatrice ; la règle des 15 € vaut pour OnlyFans, MYM c'est moins ; enlève la
// partie agence, déjà ailleurs ; pas d'information en double ; propre et lisible ») :
//   — une ligne de décision par créatrice (cellules fusionnées sur ses 3 lignes), calculée sur ses 30 derniers jours :
//     moins de 800 nouveaux subs (OF + MYM) → MARKETING ; sinon, une plateforme sous sa LTV cible → CHATTING ; sinon → SCALER ;
//   — LTV cible : OnlyFans 15 €, MYM 10 € (CIBLES) ; objectif écrit en clair, gain = objectif atteint, le reste constant :
//     Marketing : (800 − subs) × LTV actuelle ; Chatting : somme, plateforme par plateforme, de subs × LTV cible − CA ;
//   — plus de tuiles ni de bloc AGENCE (déjà dans Commission & profit et CA par mois), plus de colonne « Actuel » (les subs et
//     la LTV sont déjà dans le tableau).
function alignerSynthese() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName("Synthèse")) throw new Error("Onglet « Synthèse » introuvable.");
  const f = _feuille(ss, "Synthèse");
  const { sep, fx } = _ecrivain(f), crea = _ordre(ss);
  const S = SEUIL_SUBS, OF = CIBLES.OF, MY = CIBLES.MYM, P = `'${ONGLET_PROFIT}'`;
  // A créatrice | B plateforme | C espace | D-F 30 j | G espace | H-J 90 j | K espace | L-O scaling
  [110, 78, 14, 70, 88, 72, 14, 70, 88, 72, 14, 100, 175, 110, 110].forEach((w, i) => f.setColumnWidth(i + 1, w));
  const D0 = 5, der = D0 + 4 * crea.length - 2;

  _bandeau(f, "A1:O1", "SYNTHÈSE CRÉATRICES — mise à jour automatique, ne rien saisir ici");
  _legende(f, "A2:O2", `LEVIER (30 derniers jours, une décision par créatrice) : moins de ${S} nouveaux subs → MARKETING · ` +
    `sinon, une plateforme sous sa LTV cible → CHATTING · sinon → SCALER. LTV cible : OnlyFans ${OF.vert} €, MYM ${MY.vert} € ` +
    `(trafic interne MYM, moins qualifié). Couleurs LTV : OF rouge < ${OF.jaune} €, jaune ${OF.jaune}-${OF.vert} €, vert ≥ ` +
    `${OF.vert} € · MYM rouge < ${MY.jaune} €, jaune ${MY.jaune}-${MY.vert} €, vert ≥ ${MY.vert} €. Gain = objectif atteint, ` +
    `le reste constant, par mois. LTV = CA ÷ nouveaux subs. OF converti au taux du jour (Notice!B3).`);
  f.setRowHeight(2, 46);
  _tete(f, 3, 1, ["", "", "", "30 DERNIERS JOURS", "", "", "", "90 DERNIERS JOURS", "", "", "", "SCALING (30 derniers jours)", "", "", ""]);
  ["D3:F3", "H3:J3", "L3:O3"].forEach(a1 => f.getRange(a1).merge().setBackground(T_SOMBRE));
  f.getRange("A3:B3").setBackground(T_SOMBRE);
  _tete(f, 4, 1, ["Créatrice", "Plateforme", "", "Subs", "CA", "LTV", "", "Subs", "CA", "LTV", "",
    "Levier", "Objectif", "Gain CA / mois", "Gain profit / mois"]);

  const ltv = (l, ca, subs) => `=IFERROR(${ca}${l}/${subs}${l},"—")`;
  const lignes = { subs30: [], subs90: [], ltvOF: [], ltvMYM: [] };
  crea.forEach((c, g) => {
    const o = D0 + 4 * g, m = o + 1, t = o + 2, s = _src(c);
    f.getRange(o, 1, 3, 1).merge().setValue(c.nom).setFontWeight("bold").setVerticalAlignment("middle");
    f.getRange(o, 2, 3, 1).setValues([["OF"], ["MYM"], ["Total"]]);
    [[o, s.subsOF, s.caOF], [m, s.subsMYM, s.caMYM]].forEach(([l, subs, ca]) => {
      fx(`D${l}`, `=${subs(s.jours(30))}`); fx(`E${l}`, `=${ca(s.jours(30))}`);
      fx(`H${l}`, `=${subs(s.jours(90))}`); fx(`I${l}`, `=${ca(s.jours(90))}`);
    });
    ["D", "E", "H", "I"].forEach(col => fx(`${col}${t}`, `=${col}${o}+${col}${m}`));
    for (let l = o; l <= t; l++) { fx(`F${l}`, ltv(l, "E", "D")); fx(`J${l}`, ltv(l, "I", "H")); }

    // décision (fusionnée sur les 3 lignes) ; manque = ce qui sépare chaque plateforme de sa LTV cible, en € par mois
    const manqueOF = `MAX(0,D${o}*${OF.vert}-E${o})`, manqueMY = `MAX(0,D${m}*${MY.vert}-E${m})`;
    ["L", "M", "N", "O"].forEach(col => f.getRange(`${col}${o}:${col}${t}`).merge().setVerticalAlignment("middle")
      .setHorizontalAlignment("center"));
    fx(`L${o}`, `=IF(D${t}=0,"—",IF(D${t}<${S},"Marketing",IF(${manqueOF}+${manqueMY}>0,"Chatting","Scaler")))`);
    fx(`M${o}`, `=IF(L${o}="Marketing","${S} subs / mois",IF(L${o}="Chatting",` +
      `IF(${manqueOF}>0,"LTV OF ${OF.vert} €","")&IF(${manqueOF}*${manqueMY}>0," · ","")&IF(${manqueMY}>0,"LTV MYM ${MY.vert} €",""),` +
      `IF(L${o}="Scaler","plus de trafic","—")))`);
    fx(`N${o}`, `=IF(L${o}="Marketing",(${S}-D${t})*F${t},IF(L${o}="Chatting",${manqueOF}+${manqueMY},0))`);
    fx(`O${o}`, `=N${o}*${P}!$D$${c.t}`);
    f.getRange(`L${o}`).setFontWeight("bold");
    f.getRange(`N${o}:O${o}`).setNumberFormat(F_EUR).setFontWeight("bold");

    [4, 8].forEach(col => f.getRange(o, col, 3, 1).setNumberFormat(F_SUBS));
    [5, 9].forEach(col => f.getRange(o, col, 3, 1).setNumberFormat(F_EUR));
    [6, 10].forEach(col => f.getRange(o, col, 3, 1).setNumberFormat(F_LTV).setHorizontalAlignment("right"));
    f.getRange(t, 2, 1, 9).setFontWeight("bold");
    [[2, 1], [4, 3], [8, 3]].forEach(([col, k]) => f.getRange(t, col, 1, k).setBackground(T_CLAIR)
      .setBorder(true, null, null, null, null, null, "#9E9EB8", SpreadsheetApp.BorderStyle.SOLID));
    lignes.subs30.push(f.getRange(`D${t}`)); lignes.subs90.push(f.getRange(`H${t}`));
    lignes.ltvOF.push(f.getRange(`F${o}`), f.getRange(`J${o}`)); lignes.ltvMYM.push(f.getRange(`F${m}`), f.getRange(`J${m}`));
  });

  // couleurs : subs totaux sous le seuil (× 3 sur 90 jours) ; LTV OF et MYM selon leurs paliers ; levier
  const regle = () => SpreadsheetApp.newConditionalFormatRule();
  const paliers = (plages, c) => [regle().whenNumberLessThan(c.jaune).setBackground(C_ROUGE).setRanges(plages).build(),
    regle().whenNumberLessThan(c.vert).setBackground(C_JAUNE).setRanges(plages).build(),
    regle().whenNumberGreaterThanOrEqualTo(c.vert).setBackground(C_VERT).setRanges(plages).build()];
  const lev = [f.getRange(`L${D0}:L${der}`)];
  f.setConditionalFormatRules([
    regle().whenNumberLessThan(S).setBackground(C_ROUGE).setRanges(lignes.subs30).build(),
    regle().whenNumberLessThan(S * 3).setBackground(C_ROUGE).setRanges(lignes.subs90).build()]
    .concat(paliers(lignes.ltvOF, OF), paliers(lignes.ltvMYM, MY), [
    regle().whenTextEqualTo("Marketing").setBackground(C_BLEU).setRanges(lev).build(),
    regle().whenTextEqualTo("Chatting").setBackground(C_ROSE).setRanges(lev).build(),
    regle().whenTextEqualTo("Scaler").setBackground(C_VERT).setRanges(lev).build()]));
  f.setFrozenRows(4);
  _proteger(f, "Synthèse — mise à jour automatique");
  Logger.log(`Synthèse : ${crea.map(c => c.nom).join(", ")} ; un levier par créatrice ; séparateur « ${sep} ».`);
}

// ------------------------------------------------------------------------------------- CA par mois, Subs & LTV par mois
function creerOngletsMensuels() {
  const ss = SpreadsheetApp.getActiveSpreadsheet(), crea = _ordre(ss);
  const somme = (h, expr) => `(${crea.map(c => expr(_src(c), _src(c).mois(h))).join("+")})`;
  const regleLTV = (plage, cible) => {
    const regle = () => SpreadsheetApp.newConditionalFormatRule();
    return [regle().whenNumberLessThan(cible.jaune).setBackground(C_ROUGE).setRanges([plage]).build(),
      regle().whenNumberLessThan(cible.vert).setBackground(C_JAUNE).setRanges([plage]).build(),
      regle().whenNumberGreaterThanOrEqualTo(cible.vert).setBackground(C_VERT).setRanges([plage]).build()];
  };

  // CA par mois : total, OF, MYM empilés (A..I)
  const fca = _feuille(ss, ONGLET_CA, ss.getSheetByName(ONGLET_PROFIT));
  const e1 = _ecrivain(fca);
  [110, 92, 92, 92, 92, 92, 92, 100, 60].forEach((w, i) => fca.setColumnWidth(i + 1, w));
  _bandeau(fca, "A1:I1", "CA PAR MOIS — par créatrice et par plateforme");
  _legende(fca, "A2:I2", "Mois civils. OF converti en € au taux du jour (Notice!B3). Part = part de la créatrice dans le CA de " +
    "l'agence sur juillet → décembre. Le mois en cours est incomplet.");
  const pas = crea.length + 4;
  [["CA TOTAL (OF + MYM)", "ca"], ["CA ONLYFANS", "caOF"], ["CA MYM", "caMYM"]].forEach(([titre, cle], b) =>
    _blocMois(fca, e1.fx, 4 + b * pas, 1, titre, crea, (c, h) => `=${_src(c)[cle](_src(c).mois(h))}`, null, F_EUR, true));
  _proteger(fca, "CA par mois — mise à jour automatique");

  // Subs & LTV par mois : bandes (subs | LTV) × (total, OF, MYM)
  const fs = _feuille(ss, ONGLET_SUBS, fca);
  const e2 = _ecrivain(fs);
  [110, 80, 80, 80, 80, 80, 80, 22, 110, 80, 80, 80, 80, 80, 80].forEach((w, i) => fs.setColumnWidth(i + 1, w));
  _bandeau(fs, "A1:O1", "SUBS & LTV PAR MOIS — par créatrice et par plateforme");
  _legende(fs, "A2:O2", `LTV du mois = CA du mois ÷ nouveaux subs du mois. Couleurs : OnlyFans rouge < ${CIBLES.OF.jaune} €, ` +
    `jaune ${CIBLES.OF.jaune}-${CIBLES.OF.vert} €, vert ≥ ${CIBLES.OF.vert} € · MYM rouge < ${CIBLES.MYM.jaune} €, jaune ` +
    `${CIBLES.MYM.jaune}-${CIBLES.MYM.vert} €, vert ≥ ${CIBLES.MYM.vert} €. OF converti au taux du jour (Notice!B3). Mois en cours incomplet.`);
  const plages = {};
  [["TOTAL (OF + MYM)", "subs", "ca", ""], ["ONLYFANS", "subsOF", "caOF", "OF"], ["MYM", "subsMYM", "caMYM", "MYM"]].forEach(([nom, cs, cc, pl], b) => {
    const r = 4 + b * pas;
    _blocMois(fs, e2.fx, r, 1, `NOUVEAUX SUBS — ${nom}`, crea, (c, h) => `=${_src(c)[cs](_src(c).mois(h))}`, null, F_SUBS, false);
    plages[pl] = (_blocMois(fs, e2.fx, r, 9, `LTV — ${nom}`, crea,
      (c, h) => `=IFERROR(${_src(c)[cc](_src(c).mois(h))}/${_src(c)[cs](_src(c).mois(h))},"—")`,
      h => `=IFERROR(${somme(h, (s, k) => s[cc](k))}/${somme(h, (s, k) => s[cs](k))},"—")`, F_LTV, false));
  });
  // couleurs sur OF et MYM, chacun avec ses paliers ; le total (mélange des deux) reste neutre
  fs.setConditionalFormatRules(regleLTV(plages.OF, CIBLES.OF).concat(regleLTV(plages.MYM, CIBLES.MYM)));
  _proteger(fs, "Subs & LTV par mois — mise à jour automatique");
  Logger.log(`Onglets « ${ONGLET_CA} » et « ${ONGLET_SUBS} » reconstruits.`);
}

// tout reconstruire, dans l'ordre des dépendances (la Synthèse lit Commission & profit), sans envoyer de rapport
function construireDashboards() {
  creerOngletCommission();
  alignerSynthese();
  creerOngletsMensuels();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setActiveSheet(ss.getSheetByName("Synthèse"));
}

// 03/10 : tout en un clic — envoi automatique (orphelins retirés), tableaux de bord, rapport de test
function miseEnPlace() {
  installerDeclencheur();
  construireDashboards();
  diagnostic();
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
  // 03/10 : tout envoi réussi, manuel compris (diagnostic, miseEnPlace), compte comme l'envoi du jour → jamais deux rapports
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  PropertiesService.getScriptProperties().setProperty("DERNIER_ENVOI", String(_numJour(new Date(), ss.getSpreadsheetTimeZone())));
}

// 03/10 : à lancer une fois depuis l'éditeur (▶ Exécuter), le résultat est dans le « Journal d'exécution »
function diagnostic() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log(`Fuseaux : script ${Session.getScriptTimeZone()}, classeur ${ss.getSpreadsheetTimeZone()}`);
  Logger.log("Déclencheurs : " + (ScriptApp.getProjectTriggers().map(t => `${t.getHandlerFunction()}${typeof globalThis[t.getHandlerFunction()] === "function" ? "" : " (ORPHELIN)"}`).join(", ") || "aucun"));
  const { token, chat, cles } = _proprietes();
  Logger.log(`Propriétés : ${cles.join(", ") || "aucune"} → jeton ${token ? "trouvé" : "MANQUANT"}, canal ${chat ? "trouvé" : "MANQUANT"}`);
  CREATRICES.forEach(nom => {
    const L = _lire(ss, nom).filter(l => !l.vide);
    Logger.log(`${nom} : ${_onglet(ss, nom) ? "onglet trouvé" : "ONGLET ABSENT"}, dernière date saisie ${L.length ? _jour(L[L.length - 1].n) : "aucune"}`);
  });
  envoyerRapportTelegram();
  Logger.log("Rapport envoyé.");
}
