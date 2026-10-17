const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
function load(name, requireMock) {
  const source = fs.readFileSync(path.join(__dirname, `../src/lib/${name}.ts`), 'utf8');
  const ctx = { exports: {}, URL, Date, require: requireMock };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, ctx);
  return ctx.exports;
}
const policy = load('metricoolPolicy');
let rows = [], pending = [], count = 500, fresh = true, fail = false;
const handle = 'talent';
const now = () => new Date().toISOString();
const usage = { tableur: async () => 'test-sheet', assurerOnglet: async () => {},
  lirePlage: async () => { if (fail) throw Error('offline'); return rows; },
  ajouterLignes: async (_id, _range, values) => { rows.push(...values); } };
const comptes = { nettoyerHandle: h => h.replace(/^@/, ''), mesDemandes: async () => pending,
  mesComptes: async cle => ({ comptes: cle === 'owner' ? [{ n: 1, handle, followers: count, followersVerifiesLe: fresh ? now() : '' }] : [] }) };
const service = load('metricool', name => ({ './usage': usage, './comptesApp': comptes, './metricoolPolicy': policy })[name]);
(async () => {
  assert.equal(await service.demanderMetricool('other-user', 1), false);
  count = 499; assert.equal(await service.demanderMetricool('owner', 1), false);
  count = 500; fresh = false; assert.equal(await service.demanderMetricool('owner', 1), false);
  fresh = true; pending = [{ n: 1, handle: 'new', statut: '' }]; assert.equal(await service.demanderMetricool('owner', 1), false);
  pending = []; assert.equal(await service.demanderMetricool('owner', 1), true);
  assert.equal(rows.length, 1);
  await service.demanderMetricool('owner', 1); assert.equal(rows.length, 1);
  assert.equal(await service.connexionMetricool('owner', 1), null);
  rows[0].splice(6, 8, 'prêt', 'brand-1', 'oui', 'oui', '25', now(), 'https://app.metricool.com/connection-fixture?token=test', now());
  assert.ok(await service.connexionMetricool('owner', 1));
  assert.equal(await service.connexionMetricool('other-user', 1), null);
  rows[0][3] = 'former-handle'; assert.equal(await service.connexionMetricool('owner', 1), null);
  rows[0][3] = handle; count = 499; assert.equal(await service.connexionMetricool('owner', 1), null);
  count = 500; rows[0][6] = 'demandé'; assert.equal(await service.connexionMetricool('owner', 1), null);
  fail = true; await assert.rejects(service.etatsMetricool('owner'));
  console.log('Metricool service: authorization, identity changes, threshold, duplicates, approval and failure checks passed.');
})().catch(e => { console.error(e); process.exitCode = 1; });
