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
const SEUIL_SUBS = 800, SEUIL_LTV_JAUNE = 8, SEUIL_LTV = 15;
function _larg(t) { return [...t].reduce((a, ch) => a + (ch.codePointAt(0) > 0xffff ? 2 : 1), 0); }
function _gauche(t, n) { return t + " ".repeat(Math.max(0, n - _larg(t))); }
function _droite(t, n) { return " ".repeat(Math.max(0, n - _larg(t))) + t; }
const TETE = `${_gauche("", 5)}${_droite("subs", 7)}${_droite("CA€", 8)}${_droite("LTV€", 8)}`;
function _ligne(libelle, subs, eur, ltv) {
  let lib = libelle, s = String(Math.round(subs)), l = ltv || "";
  if (ltv !== undefined) {                                  // lignes OF / MYM : la règle des 800 subs et des 15 €
    const valeur = subs ? eur / subs : 0;
    if (subs < SEUIL_SUBS) s = "🔴" + s;
    else if (valeur < SEUIL_LTV_JAUNE) l = "🔴" + l;
    else if (valeur < SEUIL_LTV) l = "🟡" + l;
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
  const alerte = nonSaisi.length ? `\n⚠️ Hier non saisi : ${nonSaisi.join(", ")}` : "";
  const pied = `\n\n————————————\n💰 <b>CA HIER : ${_eur(totalHier.tot)}</b>\n🤝 COMMISSION HIER : ${_eur(totalHier.com)}` +
    `\n🏦 <b>PROFIT HIER : ${_eur(totalHier.profit)}</b>\n📆 Profit 30 j : ${_eur(total30.profit)}${alerte}`;
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

// 03/10 : crée l'onglet « Commission & profit ». Relancer la fonction le reconstruit en gardant les taux saisis.
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

function creerOngletCommission() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ancien = ss.getSheetByName(ONGLET_PROFIT), garde = ancien ? _tauxProfit(ss) : null;
  if (ancien) ss.deleteSheet(ancien);
  const f = ss.insertSheet(ONGLET_PROFIT, (ss.getSheetByName("Synthèse") || ss.getSheets()[0]).getIndex());
  const { sep, fx } = _ecrivain(f);
  const n = CREATRICES.length, ref = nom => `'${(_onglet(ss, nom) || { getName: () => nom }).getName()}'`;
  const plage = (nom, col) => `${ref(nom)}!$${col}$3:$${col}$1000`;
  const dates = nom => plage(nom, "A");
  const EUR = '#,##0 "€"', PCT = "0%";
  const titre = (ligne, texte) => f.getRange(ligne, 1).setValue(texte).setFontWeight("bold").setFontColor("#4A6FA5");
  const tete = (ligne, cols) => f.getRange(ligne, 1, 1, cols.length).setValues([cols]).setFontWeight("bold").setBackground("#E8E8EC");
  const total = (ligne, de, a, cols) => {
    f.getRange(ligne, 1).setValue("TOTAL");
    cols.forEach(c => fx(`${c}${ligne}`, `=SUM(${c}${de}:${c}${a})`));
    f.getRange(ligne, 1, 1, cols.length + 1).setFontWeight("bold");
  };
  f.getRange("A1:H1").merge().setValue("COMMISSION & PROFIT — calcul automatique ; seules les cases jaunes (taux) se modifient")
    .setFontWeight("bold").setFontColor("#FFFFFF").setBackground("#6B6B7B");

  // 1. Taux (lignes 4 à 9) : lus aussi par le rapport Telegram
  titre(2, "Taux — profit = CA × (commission − frais)");
  tete(3, ["Créatrice", "Commission agence", "Frais + chatting", "Marge nette"]);
  CREATRICES.forEach((nom, i) => {
    const l = 4 + i;
    const tx = garde ? garde[nom] : { com: COMMISSIONS[nom], frais: FRAIS };
    f.getRange(l, 1, 1, 3).setValues([[nom, tx.com, tx.frais]]);
    fx(`D${l}`, `=B${l}-C${l}`);
  });
  f.getRange(4, 2, n, 2).setBackground("#FFF9C4");
  f.getRange(4, 2, n, 3).setNumberFormat(PCT);

  // 2. 30 derniers jours complets, du J-30 à hier (03/10 : même fenêtre que le rapport Telegram ; la Synthèse compte aujourd'hui)
  const l30 = 4 + n + 2;                                     // 12
  titre(l30 - 1, "30 derniers jours glissants");
  tete(l30, ["Créatrice", "CA 30 j", "Commission", "Frais + chatting", "Profit", "Nouveaux subs", "Profit / sub"]);
  CREATRICES.forEach((nom, i) => {
    const l = l30 + 1 + i, t = 4 + i, fen = `${dates(nom)},">="&TODAY()-30,${dates(nom)},"<="&TODAY()-1`;
    f.getRange(l, 1).setValue(nom);
    fx(`B${l}`, `=SUMIFS(${plage(nom, "I")},${fen})`);
    fx(`C${l}`, `=B${l}*$B$${t}`);
    fx(`D${l}`, `=B${l}*$C$${t}`);
    fx(`E${l}`, `=C${l}-D${l}`);
    fx(`F${l}`, `=SUMIFS(${plage(nom, "H")},${fen})`);
    fx(`G${l}`, `=IFERROR(E${l}/F${l},"—")`);
  });
  const t30 = l30 + n + 1;
  total(t30, l30 + 1, l30 + n, ["B", "C", "D", "E", "F"]);
  fx(`G${t30}`, `=IFERROR(E${t30}/F${t30},"—")`);
  f.getRange(l30 + 1, 2, n + 1, 4).setNumberFormat(EUR);
  f.getRange(l30 + 1, 7, n + 1, 1).setNumberFormat('0.00 "€"');

  // 3. Hier
  const lh = t30 + 3;
  titre(lh - 1, "Hier");
  tete(lh, ["Créatrice", "CA hier", "Commission", "Frais + chatting", "Profit"]);
  CREATRICES.forEach((nom, i) => {
    const l = lh + 1 + i, t = 4 + i;
    f.getRange(l, 1).setValue(nom);
    fx(`B${l}`, `=SUMIFS(${plage(nom, "I")},${dates(nom)},TODAY()-1)`);
    fx(`C${l}`, `=B${l}*$B$${t}`);
    fx(`D${l}`, `=B${l}*$C$${t}`);
    fx(`E${l}`, `=C${l}-D${l}`);
  });
  const th = lh + n + 1;
  total(th, lh + 1, lh + n, ["B", "C", "D", "E"]);
  f.getRange(lh + 1, 2, n + 1, 4).setNumberFormat(EUR);

  // 4. Commission puis profit par mois (juillet → décembre 2026)
  [["Commission par mois", "B"], ["Profit par mois", "D"]].forEach(([texte, colTaux], bloc) => {
    const lm = th + 3 + bloc * (n + 5);
    titre(lm - 1, texte);
    tete(lm, ["Créatrice"]);
    ["B", "C", "D", "E", "F", "G"].forEach((c, k) => fx(`${c}${lm}`, `=DATE(2026,${7 + k},1)`));
    f.getRange(lm, 2, 1, 6).setNumberFormat("mmmm").setFontWeight("bold").setBackground("#E8E8EC");
    CREATRICES.forEach((nom, i) => {
      const l = lm + 1 + i, t = 4 + i;
      f.getRange(l, 1).setValue(nom);
      ["B", "C", "D", "E", "F", "G"].forEach(c => fx(`${c}${l}`, 
        `=SUMIFS(${plage(nom, "I")},${dates(nom)},">="&${c}$${lm},${dates(nom)},"<"&EDATE(${c}$${lm},1))*$${colTaux}$${t}`));
    });
    total(lm + n + 1, lm + 1, lm + n, ["B", "C", "D", "E", "F", "G"]);
    f.getRange(lm + 1, 2, n + 1, 6).setNumberFormat(EUR);
  });
  f.setColumnWidth(1, 110); f.setColumnWidths(2, 7, 115); f.setFrozenRows(1);
  SpreadsheetApp.flush();
  const erreurs = f.getRange(1, 1, f.getLastRow(), 8).getDisplayValues().flat().filter(v => /^#/.test(v)).length;
  Logger.log(`Onglet « ${ONGLET_PROFIT} » ${ancien ? "reconstruit (taux gardés)" : "créé"}, séparateur « ${sep} », ${erreurs} cellule(s) en erreur.`);
}

// 03/10 (Gaëtan : « aligne aussi la Synthèse », puis « trie par créatrice comme le rapport Telegram : Chloé OF, Chloé MYM,
// Chloé Total, une ligne vide, Sophie… ; subs, CA, LTV sur 30 jours, un espace, puis sur 90 jours ») : le bloc du haut de la
// Synthèse est reconstruit — un groupe de 3 lignes par créatrice (OF, MYM, Total) + une ligne vide, rangées par CA 30 jours
// décroissant au moment du lancement (comme le rapport), puis le groupe AGENCE. Fenêtres complètes jusqu'à hier : du J-30 et du
// J-90 à J-1, OF converti au taux de Notice!B3. Les blocs « par mois » en dessous sont décalés (lignes insérées ou retirées),
// leurs formules suivent. Relancer la fonction refait le bloc au propre et le re-trie.
function alignerSynthese() {
  const ss = SpreadsheetApp.getActiveSpreadsheet(), f = ss.getSheetByName("Synthèse");
  if (!f) throw new Error("Onglet « Synthèse » introuvable.");
  const { sep, fx } = _ecrivain(f);
  const colA = f.getRange(1, 1, f.getLastRow(), 1).getDisplayValues().map(r => r[0]);
  const titreMois = colA.findIndex(v => /^CA total/.test(v)) + 1;
  if (titreMois < 1) throw new Error("Bloc « CA total (€) par mois » introuvable dans la Synthèse.");

  // ordre : CA 30 jours décroissant, comme le rapport
  const taux = _taux(ss), hier = _numJour(new Date(), ss.getSpreadsheetTimeZone()) - 1;
  const crea = CREATRICES.map(nom => ({ nom, o: _onglet(ss, nom) })).filter(c => c.o)
    .map(c => ({ ...c, ca: _somme(_lire(ss, c.nom), hier - 30, hier, taux).tot })).sort((a, b) => b.ca - a.ca);

  // place : titre + en-tête + 4 lignes par groupe (créatrices + agence) + 1 ligne vide avant les blocs par mois
  const G = crea.length + 1, voulu = 3 + 2 + 4 * G + 1;
  if (titreMois < voulu) f.insertRowsBefore(titreMois, voulu - titreMois);
  if (titreMois > voulu) f.deleteRows(voulu, titreMois - voulu);
  f.getRange(3, 1, voulu - 3, 13).clear();

  f.getRange("A3").setValue("30 et 90 derniers jours complets (jusqu'à hier), par créatrice et par plateforme — OF converti en € au taux de Notice!B3")
    .setFontWeight("bold");
  f.getRange(4, 1, 1, 9).setValues([["Créatrice", "Plateforme", "Subs 30 j", "CA 30 j", "LTV 30 j", "", "Subs 90 j", "CA 90 j", "LTV 90 j"]])
    .setFontWeight("bold").setBackground("#DCE6F1");
  const fin = 5 + 4 * crea.length - 2;                         // dernière ligne « Total » d'une créatrice
  const ltv = (l, ca, subs) => `=IFERROR(${ca}${l}/${subs}${l},"—")`;
  const groupe = (r0, nom, plat) => {
    f.getRange(r0, 1, 3, 2).setValues([[nom, "OF"], [nom, "MYM"], [nom, "Total"]]);
    plat(r0);
    ["E", "I"].forEach(c => [0, 1, 2].forEach(k => fx(`${c}${r0 + k}`, ltv(r0 + k, c === "E" ? "D" : "H", c === "E" ? "C" : "G"))));
    f.getRange(r0 + 2, 1, 1, 9).setFontWeight("bold").setBackground("#F2F2F5");
    f.getRange(r0, 3, 3, 1).setNumberFormat("#,##0"); f.getRange(r0, 7, 3, 1).setNumberFormat("#,##0");
    f.getRange(r0, 4, 3, 1).setNumberFormat('#,##0.00 "€"'); f.getRange(r0, 8, 3, 1).setNumberFormat('#,##0.00 "€"');
    f.getRange(r0, 5, 3, 1).setNumberFormat('0.00 "€"'); f.getRange(r0, 9, 3, 1).setNumberFormat('0.00 "€"');
  };
  crea.forEach((c, g) => groupe(5 + 4 * g, c.nom, r0 => {
    const r = col => `'${c.o.getName()}'!$${col}$3:$${col}$1000`;
    const fen = j => `${r("A")},">="&TODAY()-${j},${r("A")},"<="&TODAY()-1`;
    [[r0, "B", "C", "*Notice!$B$3"], [r0 + 1, "E", "F", ""]].forEach(([l, subs, ca, conv]) => {
      fx(`C${l}`, `=SUMIFS(${r(subs)},${fen(30)})`); fx(`D${l}`, `=SUMIFS(${r(ca)},${fen(30)})${conv}`);
      fx(`G${l}`, `=SUMIFS(${r(subs)},${fen(90)})`); fx(`H${l}`, `=SUMIFS(${r(ca)},${fen(90)})${conv}`);
    });
    ["C", "D", "G", "H"].forEach(c2 => fx(`${c2}${r0 + 2}`, `=${c2}${r0}+${c2}${r0 + 1}`));
  }));
  const ra = 5 + 4 * crea.length;                              // groupe AGENCE
  groupe(ra, "AGENCE", r0 => ["OF", "MYM", "Total"].forEach((pl, k) => ["C", "D", "G", "H"].forEach(c2 =>
    fx(`${c2}${r0 + k}`, `=SUMIFS(${c2}$5:${c2}$${fin},$B$5:$B$${fin},"${pl}")`))));
  f.getRange(ra, 1, 3, 9).setFontWeight("bold");
  f.setColumnWidth(6, 24);
  Logger.log(`Synthèse : bloc 30 / 90 jours par créatrice (${crea.map(c => c.nom).join(", ")}, puis AGENCE), séparateur « ${sep} ».`);
}

// 03/10 : tout en un clic — envoi automatique (orphelins retirés), Synthèse alignée, onglet Commission & profit, rapport de test
function miseEnPlace() {
  installerDeclencheur();
  alignerSynthese();
  creerOngletCommission();
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
