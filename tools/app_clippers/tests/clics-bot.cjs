// 28/10 (audit) : un jour que GAML n'a pas rendu est repris du relevé du bot (« Pilotage clics »). Lignes fictives.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const eq = (x, y) => assert.deepEqual(JSON.parse(JSON.stringify(x)), y);
const mod = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/clicsBot.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: mod, require: () => ({}), Map, Number, String, parseInt });
const { visitesBot, completer, periodeBot } = mod;
const L = (jour, crea, source, qui, payables, nonReleves = '0') => [jour, crea, 'Horizontal', source, qui, payables, payables, '1', nonReleves];
const lignes = [
  L('2026-10-26', 'Sarah', 'Clipper', 'Yves', '163'), L('2026-10-26', 'Chloé', 'Clipper', 'Yves', '7'),   // deux créatrices : additionnées
  L('2026-10-27', 'Sarah', 'Clipper', 'Yves', '49'),
  L('2026-10-28', 'Sarah', 'Clipper', 'Yves', '14', '1'),                                                // un lien pas relevé : incomplet
  L('2026-10-27', 'Sarah', 'Clipper', 'Simon', '15'),                                                     // un autre clipper
  L('2026-10-27', 'Sarah', 'Metricool', 'Yves', '999'),                                                   // pas une ligne de clipping
  L('2026-10-10', 'Sarah', 'Clipper', 'Yves', '50'),                                                      // avant la fenêtre
];
const bot = visitesBot(lignes, 'Yvés', '2026-10-20');
assert.deepEqual(JSON.parse(JSON.stringify([...bot])), [
  ['2026-10-26', { visites: 170, complet: true }], ['2026-10-27', { visites: 49, complet: true }], ['2026-10-28', { visites: 14, complet: false }]]);
// GAML : le 26 rendu, le 27 et le 28 refusés (limite) → le 27 repris du bot, le 28 reste incomplet
const parJour = new Map([['2026-10-26', { visites: 160, complet: true }], ['2026-10-27', { visites: 0, complet: false }], ['2026-10-28', { visites: 0, complet: false }]]);
assert.equal(completer(parJour, bot), 1);
eq(parJour.get('2026-10-26'), { visites: 160, complet: true });            // un jour GAML complet n'est jamais remplacé
eq(parJour.get('2026-10-27'), { visites: 49, complet: true });
eq(parJour.get('2026-10-28'), { visites: 0, complet: false });
// Période passée : seulement si le bot a tous ses jours
assert.equal(periodeBot(bot, '2026-10-26', '2026-10-27', ['2026-10-26', '2026-10-27']), 219);
assert.equal(periodeBot(bot, '2026-10-26', '2026-10-28', ['2026-10-26', '2026-10-27', '2026-10-28']), null);
assert.equal(periodeBot(bot, '2026-10-24', '2026-10-27', ['2026-10-24', '2026-10-25', '2026-10-26', '2026-10-27']), null);
assert.equal(visitesBot(lignes, '', '2026-10-01').size, 0);
console.log('Clics du bot : jours repris quand GAML refuse, jours complets seulement, périodes entières seulement.');
