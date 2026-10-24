// 24/10 : les comptes d'un clipper selon le LOG DASHBOARD (lib/comptesReels.ts). Cas réels du 24/10, @ fictifs.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
function load(file, deps = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, require: n => { if (!(n in deps)) throw Error(n); return deps[n]; } });
  return exports;
}
const eq = (a, b) => assert.deepEqual(JSON.parse(JSON.stringify(a)), b);
const { comptesReels, alerteMesure, gerePar } = load('lib/comptesReels.ts');
const { comptesAffiches } = load('lib/comptesVisibles.ts');

const fiche = (n, handle, etat = 'GOOD') => ({ n, handle, etat, creatrice: 'Sophie', followers: 10, reels7: 1, vues7: 100 });
const ligne = (handle, gerant, etat = 'GOOD', patch = {}) => ({ handle, gerant, etat, type: 'Clipper', creatrice: 'Sophie',
  followers: 1000, reels7: 18, vues7: null, vuesRecentes: 150000, mesure: 'lu', dernierReel: 'hier', ...patch });

// Le Gérant décide : « Rianah Clipping Chloé » est à Rianah, « Gaetan » à Gaëtan, « Julien » n'est pas à « Jules »
assert.equal(gerePar('Rianah Clipping Chloé', 'Rianah'), true);
assert.equal(gerePar('Rianah (Metricool)', 'Rianah'), true);
assert.equal(gerePar('Gaetan', 'Gaëtan'), true);
assert.equal(gerePar('Julien', 'Jules'), false);
assert.equal(gerePar('', 'Mathieu'), false);

// Cas Mathieu : la fiche du bot porte une faute de frappe (« …troupe »), le LOG DASHBOARD le bon @ (« …troupee ») à 150 000 vues
const ficheMathieu = [fiche(1, 'demo.ban', 'BAN'), fiche(2, 'demo.appel', 'APPEL A FAIRE'), fiche(3, 'demo.secret'), fiche(7, 'demo.troupe', '')];
const classeur = [ligne('demo.ban', 'Mathieu', 'BAN'), ligne('demo.appel', 'Mathieu', 'APPEL A FAIRE'), ligne('demo.secret', 'Mathieu'),
  ligne('demo.troupee', 'Mathieu'), ligne('demo.autre', 'Tassiana')];
let r = comptesReels('Mathieu', ficheMathieu, classeur);
eq(r.map(c => [c.handle, c.source, c.modifiable]), [['demo.ban', 'fiche', true], ['demo.appel', 'fiche', true], ['demo.secret', 'fiche', true],
  ['demo.troupe', 'fiche', true], ['demo.troupee', 'classeur', false]]);
const affiches = comptesAffiches(r);
eq(affiches.map(c => c.handle), ['demo.secret', 'demo.troupee', 'demo.appel']);   // BAN et ancien @ masqués, le vrai compte visible
assert.equal(affiches[1].vues7, 150000); assert.equal(affiches[1].n >= 100, true);

// Cas Simon / Laure : la fiche de Laure porte les comptes que le LOG DASHBOARD donne à Simon → plus chez Laure
r = comptesReels('Laure', [fiche(1, 'demo.s1'), fiche(2, 'demo.s2')], [ligne('demo.s1', 'Simon'), ligne('demo.s2', 'Simon')]);
eq(r, []);
// Compte libéré (Gérant vide) : à personne
eq(comptesReels('Ricardo', [fiche(1, 'demo.libre')], [ligne('demo.libre', '')]), []);
// Un @ de la fiche absent du LOG DASHBOARD reste tel quel (son état vide le masque ensuite)
eq(comptesReels('Esperance', [fiche(1, 'demo.ancien', '')], [ligne('demo.vrai', 'Esperance')]).map(c => c.handle), ['demo.ancien', 'demo.vrai']);
// LOG DASHBOARD illisible : la fiche seule, comme avant
eq(comptesReels('Mathieu', ficheMathieu, null).map(c => c.handle), ficheMathieu.map(c => c.handle));
// Un privé du LOG DASHBOARD hors fiche est reconnu par son relevé « privé »
assert.equal(comptesReels('Thia', [], [ligne('demo.prv', 'Thia', 'GOOD', { mesure: 'privé' })])[0].role, 'privé');

// Rianah gère aussi des comptes Metricool (payés au fixe) : jamais ajoutés à son app de clippeuse ; ceux de sa fiche restent
r = comptesReels('Rianah', [fiche(1, 'demo.vibes')], [ligne('demo.vibes', 'Rianah Metricool', 'GOOD', { type: 'Metricool' }),
  ligne('demo.metricool', 'Rianah (Metricool)', 'GOOD', { type: 'Metricool' }), ligne('demo.clip', 'Rianah Clipping Chloé')]);
eq(r.map(c => c.handle), ['demo.vibes', 'demo.clip']);

// Alertes de relevé : le chiffre affiché n'est peut-être pas la réalité
assert.equal(alerteMesure({ etat: 'GOOD', mesure: 'introuvable · followers : classeur' }).grave, true);
assert.match(alerteMesure({ etat: 'GOOD', mesure: 'restreint' }).texte, /limite/);
assert.match(alerteMesure({ etat: 'Faire appel', mesure: 'restreint · followers non lus depuis le 13/10' }).texte, /limite/);
assert.match(alerteMesure({ etat: 'GOOD', mesure: 'lu · Reels non lus · followers non lus depuis le 12/10' }).texte, /12\/10/);
assert.match(alerteMesure({ etat: 'GOOD', mesure: 'lu', dernierReel: 'il y a 21 j' }).texte, /21 jours/);
assert.match(alerteMesure({ etat: 'GOOD', mesure: 'lu', dernierReel: 'aucun' }).texte, /aucun Reel/);
assert.equal(alerteMesure({ etat: 'GOOD', mesure: 'lu', dernierReel: 'il y a 2 j' }), null);
assert.equal(alerteMesure({ etat: 'GOOD', mesure: 'lu · vues 13/14 Reels mesurés à 48 h', dernierReel: 'hier' }), null);
assert.equal(alerteMesure({ etat: 'GOOD', mesure: 'privé', dernierReel: 'aucun', role: 'privé' }), null);   // un privé ne poste pas
assert.equal(alerteMesure({ etat: 'à créer', mesure: 'à créer' }), null);
assert.equal(alerteMesure({ etat: 'BAN', mesure: 'introuvable' }), null);
console.log('Comptes réels : le LOG DASHBOARD décide (@ hors fiche, faute de frappe, compte donné ou libéré), alertes de relevé vérifiées.');
