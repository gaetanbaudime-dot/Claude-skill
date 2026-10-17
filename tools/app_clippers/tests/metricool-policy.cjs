// Run: node tests/metricool-policy.cjs (uses the project's TypeScript dependency).
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/metricoolPolicy.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const context = { exports: {}, URL, Date };
vm.runInNewContext(compiled, context);
const { eligible, connexionAutorisee, lienMetricool } = context.exports;
const now = Date.parse('2026-10-17T10:00:00Z');
const iso = hours => new Date(now - hours * 3600000).toISOString();
for (const followers of [null, -1, 0, 499, 499.9, NaN, Infinity]) assert.equal(eligible({ followers, followersVerifiesLe: iso(0) }, now), false);
for (const followers of [500, 501, 10000]) assert.equal(eligible({ followers, followersVerifiesLe: iso(1) }, now), true);
for (const date of [undefined, '', 'bad', iso(-1), iso(49)]) assert.equal(eligible({ followers: 500, followersVerifiesLe: date }, now), false);
assert.equal(eligible({ followers: 500, followersVerifiesLe: iso(48) }, now), true);
const v = { marque: 'brand-123', proprietaireMarque: 'oui', accesAgence: 'oui', nombreMarques: '25',
  capaciteVerifieeLe: iso(1), lien: 'https://app.metricool.com/connection-fixture?token=test', creeLe: iso(2) };
assert.equal(connexionAutorisee(v, now), v.lien);
for (const patch of [{ marque: '' }, { proprietaireMarque: '' }, { accesAgence: '' }, { nombreMarques: '26' },
  { nombreMarques: '' }, { nombreMarques: '-1' }, { capaciteVerifieeLe: iso(25) }, { creeLe: iso(72) },
  { creeLe: iso(-1) }, { lien: 'https://evil.example/connect' }]) assert.equal(connexionAutorisee({ ...v, ...patch }, now), null);
for (const url of ['http://app.metricool.com/connect', 'https://app.metricool.com.evil.example/connect',
  'https://user:pass@app.metricool.com/connect', 'javascript:alert(1)', 'https://app.metricool.com/']) assert.equal(lienMetricool(url), null);
console.log('Metricool policy: threshold, freshness, ownership, capacity, expiry and URL checks passed.');
