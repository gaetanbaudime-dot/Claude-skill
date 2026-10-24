// 24/10 : « Ma semaine » (onglet Comptes) et la prime volume (onglet Versements). @ fictifs.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
function load(file, deps = {}) {
  const mod = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports: mod, Date, Intl, require: n => { if (!(n in deps)) throw Error(n); return deps[n]; } });
  return mod;
}
const dates = load('lib/dates.ts');
const a = load('lib/activite.ts', { './dates': dates });
const eq = (x, y, m) => assert.deepEqual(JSON.parse(JSON.stringify(x)), y, m);

// La colonne du bot
eq(a.lireJours('2026-10-20:3 2026-10-22:2 nimporte 2026-10-22:1'), { '2026-10-20': 3, '2026-10-22': 3 });
eq(a.lireJours(''), {});

// Ma semaine : 7 jours clos (aujourd'hui exclu), Reels de tous ses comptes, clics payés par jour
const auj = '2026-10-24';
const croissance1 = { handle: 'c1', etat: 'GOOD', role: 'croissance', followers: 1200, reels7: 9, vues7: 30000,
  jours: { '2026-10-17': 3, '2026-10-20': 2, '2026-10-23': 4, '2026-10-24': 5, '2026-10-10': 6 } };
const croissance2 = { handle: 'c2', etat: 'GOOD', role: 'croissance', followers: 300, reels7: 3, vues7: null, jours: { '2026-10-23': 3 } };
const prive = { handle: 'p', etat: 'GOOD', role: 'privé', followers: 40, reels7: 1, vues7: 500, jours: { '2026-10-22': 1 } };
let s = a.semaine([croissance1, croissance2, prive], auj, { '2026-10-23': 120, '2026-10-16': 999 });
eq(s.jours.map(j => j.jour), ['2026-10-17', '2026-10-18', '2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23']);
eq(s.jours.map(j => j.reels), [3, 0, 0, 2, 0, 1, 7]);
assert.equal(s.reels, 13); assert.equal(s.cadence, 1.9);
assert.equal(s.vues, 30500); assert.equal(s.followers, 1540); assert.equal(s.clics, 120);
assert.equal(s.parJour, true);

// Colonne pas encore publiée : on retombe sur « Reels 7 j », sans graphique ; clics inconnus = null, jamais 0
s = a.semaine([{ ...croissance1, jours: undefined }, { ...prive, jours: undefined }], auj, null);
assert.equal(s.parJour, false); assert.equal(s.reels, 10); assert.equal(s.cadence, 1.4); assert.equal(s.clics, null);
s = a.semaine([], auj, null);
assert.equal(s.reels, null); assert.equal(s.vues, null); assert.equal(s.followers, null);

// Prime volume : jours clos de la période, comptes de croissance seulement, moyenne par compte (2 comptes)
let p = a.reelsPrime([croissance1, croissance2, prive], '2026-10-20', '2026-11-04', auj);
assert.equal(p.joursEcoules, 4);                       // 20, 21, 22, 23
assert.equal(p.reels, 9);                              // 2 + 4 + 3, le privé et aujourd'hui exclus
assert.equal(p.moyenne, 1.1);                          // 9 / 4 / 2
assert.equal(p.comptes, 2); assert.equal(p.mesure, true);
p = a.reelsPrime([croissance1], '2026-10-24', '2026-11-04', auj);
assert.equal(p.joursEcoules, 0); assert.equal(p.moyenne, null);
p = a.reelsPrime([croissance1], '2026-10-05', '2026-10-19', auj);           // période close : s'arrête à sa fin
assert.equal(p.joursEcoules, 15); assert.equal(p.reels, 9);               // 10/10 et 17/10
assert.equal(a.reelsPrime([{ ...croissance1, jours: undefined }], '2026-10-20', '2026-11-04', auj).mesure, false);

// Paliers : il faut les Reels ET les clics
let e = a.evaluerPrime(6.2, 410);
eq(e.paliers.map(x => x.atteint), [true, true, false]); assert.equal(e.atteint.bonus, 20);
assert.equal(e.paliers[2].manqueReels, 2.8); assert.equal(e.paliers[2].manqueClics, 190);
e = a.evaluerPrime(9.5, 150);
assert.equal(e.atteint, null); assert.equal(e.paliers[0].okReels, true); assert.equal(e.paliers[0].manqueClics, 50);
e = a.evaluerPrime(null, null);
assert.equal(e.atteint, null); assert.equal(e.paliers[0].okReels, false);
console.log('Activité : colonne du bot, 7 jours clos, repli sans colonne, prime sur les comptes de croissance et paliers vérifiés.');
