// 28/10 (audit) : un refus de @ du 12/10 s'affichait encore le 28/10, sur un autre compte. Seules les demandes récentes s'affichent.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const eq = (x, y) => assert.deepEqual(JSON.parse(JSON.stringify(x)), y);
const mod = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/comptesApp.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: mod, require: () => ({ lireJours: () => ({}) }), Map, Date, Number, parseInt, Infinity });
const maintenant = Date.parse('2026-10-28T08:00:00Z');
const brut = [
  ['2026-10-12 15:09:56', 'clarisse', '1', 'vieux_refus', 'refusé', 'je ne trouve pas ce compte'],
  ['2026-10-26 07:13:42', 'yves', '1', 'refus_recent', 'refusé', 'ligne déplacée'],
  ['2026-10-28 07:30:00', 'yves', '2', 'en_cours', '', ''],
  ['2026-10-26 07:30:00', 'yves', '3', 'bloque', '', ''],
  ['2026-10-28 07:00:00', 'yves', '3', 'fait_aujourdhui', 'fait', 'a → b'],
];
eq(mod.demandesRecentes(brut, 'clarisse', maintenant), []);
eq(mod.demandesRecentes(brut, 'yves', maintenant).map((d) => [d.n, d.handle]), [[1, 'refus_recent'], [2, 'en_cours']]);
console.log('Demandes de @ : en attente moins de 24 h, refus moins de 3 jours, rien de plus vieux.');
