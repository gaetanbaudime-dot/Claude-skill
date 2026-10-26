const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
function load(file, deps = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText, { exports, URL, Date, require: n => { if (!(n in deps)) throw Error(n); return deps[n]; } });
  return exports;
}
const calc = load('components/pilotage/calc.ts');
const model = load('lib/classement.ts', { '@/components/pilotage/calc': calc, '@/lib/salaries': load('lib/salaries.ts') });
const visibles = load('lib/comptesVisibles.ts');
const dates = load('lib/dates.ts');
const activite = load('lib/activite.ts', { './dates': dates });
const igSuivi = load('lib/igSuivi.ts');
const reels = load('lib/comptesReels.ts');
const me = { prenom: 'Caroline', creatrice: 'Chloé', cle: 'caroline' };
const compte = (handle, n, gerant) => ({ handle, n, numero: n, gerant, creatrice: 'Chloé', axe: 'Horizontal', type: 'Clipper', etat: 'GOOD' });
const mine = [1, 2, 3, 4].map(n => compte('mine'+n, n, 'Caroline'));
const other = compte('autre', 1, 'Romaric');
const data = { aujourdhui: '2026-10-17', comptes: [...mine, other], boutons: [{ secret: 'global' }], subs: [{ caMymEur: 1000 }],
  clippers: [{ uid: '1', prenom: 'Caroline', role: 'Clipper', creatrice: 'Chloé', comptes: mine.map(c => ({ handle: c.handle, numero: c.n })) },
    { uid: '2', prenom: 'Romaric', role: 'Clipper', creatrice: 'Chloé', comptes: [{ handle: 'autre', numero: 1 }] }],
  clics: ['Caroline', 'Romaric'].map(qui => ({ jour: '2026-10-16', qui, axe: 'Horizontal', source: 'Clipper', visites: 10, manquants: 0 })) };
let fail = false, reads = 0;
const route = load('app/api/k/[token]/comptes/route.ts', {
  'next/server': { NextResponse: { json: (body, init = {}) => ({ body, status: init.status || 200, headers: init.headers }) } },
  '@/lib/clippers': { clipperParJeton: async token => token === 'own-token' ? me : null },
  '@/lib/comptesApp': { mesComptes: async cle => { assert.equal(cle, 'caroline'); return { comptes: mine, tl: 'Mathieu' }; }, mesDemandes: async () => [] },
  '@/lib/pilotage': { pilotage: async () => { reads++; if (fail) throw Error('Sheets unavailable'); return data; } },
  '@/lib/classement': model,
  '@/lib/comptesVisibles': visibles,
  '@/lib/comptesReels': reels,
  '@/lib/activite': activite,
  '@/lib/igSuivi': igSuivi,
  '@/lib/igSource': { suiviIg: async () => null },                                // suivi RapidAPI illisible : l'ancien relevé reste
  '@/lib/dates': dates,
});
(async () => {
  let r = await route.GET({}, { params: { token: 'invalid-token' } });
  assert.equal(r.status, 404); assert.equal(reads, 0);
  r = await route.GET({ url: '?clipper=romaric' }, { params: { token: 'own-token' } });
  assert.equal(r.status, 200); assert.equal(r.body.comptes.length, 4);                 // 24/10 : la liste montre aussi le n° 4
  assert.equal(r.body.pilotage.clippers.length, 1); assert.equal(r.body.pilotage.clippers[0].prenom, 'Caroline');
  assert.ok(r.body.pilotage.comptes.every(c => c.gerant === 'Caroline' && c.numero <= 3));
  assert.ok(r.body.pilotage.clics.every(c => c.qui === 'Caroline'));
  assert.equal(r.body.semaine.clics, 10);                                          // ses 10 visites du 16/10, pas celles de Romaric
  assert.equal(r.body.semaine.jours.length, 7);
  assert.equal(r.body.pilotage.subs.length, 0); assert.equal(r.body.pilotage.boutons.length, 0);
  assert.equal(r.headers['Cache-Control'], 'private, no-store');
  fail = true;
  r = await route.GET({}, { params: { token: 'own-token' } });
  assert.equal(r.status, 200); assert.equal(r.body.pilotage, null); assert.equal(r.body.comptes.length, 4);
  assert.equal(r.body.semaine.clics, null);                                        // panne du pilotage : « – », jamais 0
  console.log('Pilotage personnel : jeton, propriétaire, limite 3 du pilotage, liste complète des comptes, absence de données tierces et panne de source vérifiés.');
})().catch(e => { console.error(e); process.exitCode = 1; });
