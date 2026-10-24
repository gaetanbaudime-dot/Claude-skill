const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const eq = (a, b) => assert.deepEqual(JSON.parse(JSON.stringify(a)), b);   // objets nés dans un autre contexte vm
function load(file, deps = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText, { exports, URL, Date, require: n => { if (!(n in deps)) throw Error(n); return deps[n]; } });
  return exports;
}

// « À suivre » de Mon équipe : un compte GOOD ne remonte jamais, bans et appels d'abord marqués graves.
const { pointsDe } = load('lib/suiviEquipe.ts');
const c = (n, etat, handle = `compte${n}`) => ({ n, handle, etat, followers: null, reels7: null, vues7: null });
const m = (comptes, manquants = 0) => ({ cle: 'x', prenom: 'X', creatrice: 'Sarah', comptes, visites: null, auSeuil: false, manquants });

eq(pointsDe(m([c(1, 'GOOD'), c(2, 'GOOD'), c(3, 'GOOD')])), []);
eq(pointsDe(m([])), [{ texte: 'Aucun compte renseigné', grave: false }]);
let p = pointsDe(m([c(1, 'BAN'), c(2, 'APPEL A FAIRE'), c(3, 'Faire appel')]));
eq(p.map(x => [x.texte, x.grave]), [['banni', true], ['appel à faire', true], ['appel à faire', true]]);
p = pointsDe(m([c(1, 'à créer'), c(2, 'a creer'), c(3, '')]));
eq(p.map(x => x.texte), ['à créer', 'à créer', 'état à vérifier']);
eq(pointsDe(m([c(1, 'BIZARRE')])).map(x => x.texte), ['bizarre']);
// Les jours non relevés ne comptent que pour un clipper qui a un compte actif.
assert.equal(pointsDe(m([c(1, 'à créer')], 2)).some(x => x.texte.startsWith('clics')), false);
eq(pointsDe(m([c(1, 'GOOD')], 2)).map(x => x.texte), ['clics : 2 jour(s) pas encore relevé(s)']);

// La route de l'équipe : 404 pour un jeton inconnu ou un clipper sans équipe, sinon seulement les clippers du TL et leurs comptes 1 à 3.
const calc = load('components/pilotage/calc.ts');
const model = load('lib/classement.ts', { '@/components/pilotage/calc': calc });
const tl = { prenom: 'Yves', cle: 'yves', creatrice: 'Sarah' };
const clipper = { prenom: 'Simon', cle: 'simon', creatrice: 'Sarah' };
const equipe = [{ cle: 'simon', prenom: 'Simon', creatrice: 'Sarah', comptes: [c(1, 'GOOD', 'simon1'), c(2, 'GOOD', 'simon2'), c(4, 'GOOD', 'simon4')] }];
const compte = (handle, gerant, numero) => ({ handle, gerant, numero, creatrice: 'Sarah', axe: 'Horizontal', type: 'Clipper', etat: 'GOOD' });
const data = { aujourdhui: '2026-10-24', boutons: [{ x: 1 }], subs: [{ caMymEur: 1000 }],
  comptes: [compte('simon1', 'Simon', 1), compte('simon2', 'Simon', 2), compte('simon4', 'Simon', 4), compte('autre', 'Romaric', 1)],
  clippers: [{ uid: '1', prenom: 'Simon', role: 'Clipper', creatrice: 'Sarah', comptes: [{ handle: 'simon1', numero: 1 }, { handle: 'simon2', numero: 2 }, { handle: 'simon4', numero: 4 }] },
    { uid: '2', prenom: 'Romaric', role: 'Clipper', creatrice: 'Chloé', comptes: [{ handle: 'autre', numero: 1 }] }],
  clics: ['Simon', 'Romaric'].map(qui => ({ jour: '2026-10-23', qui, axe: 'Horizontal', source: 'Clipper', visites: 10, manquants: 0, creatrice: 'Sarah' })) };
const route = load('app/api/k/[token]/equipe/route.ts', {
  'next/server': { NextResponse: { json: (body, init = {}) => ({ body, status: init.status || 200, headers: init.headers }) } },
  '@/lib/clippers': { clipperParJeton: async t => (t === 'tl' ? tl : t === 'clipper' ? clipper : null), normaliser: s => s.toLowerCase() },
  '@/lib/comptesApp': { monEquipe: async cle => (cle === 'yves' ? equipe : []) },
  '@/lib/equipes': { equipeDe: async () => null },
  '@/lib/pilotage': { pilotage: async () => data },
  '@/lib/classement': model,
});
(async () => {
  assert.equal((await route.GET({}, { params: { token: 'inconnu' } })).status, 404);
  assert.equal((await route.GET({}, { params: { token: 'clipper' } })).status, 404);
  const r = await route.GET({}, { params: { token: 'tl' } });
  assert.equal(r.status, 200);
  eq(r.body.membres.map(x => x.prenom), ['Simon']);
  eq(r.body.membres[0].comptes.map(x => x.n), [1, 2]);
  assert.ok(r.body.pilotage.comptes.every(x => x.gerant === 'Simon' && x.numero <= 3));
  assert.ok(r.body.pilotage.clics.every(x => x.qui === 'Simon'));
  assert.equal(r.body.pilotage.subs.length, 0); assert.equal(r.body.pilotage.boutons.length, 0);
  assert.equal(r.headers['Cache-Control'], 'private, no-store');
  console.log('Mon équipe : points à suivre, équipe du seul TL, comptes 1 à 3, ni subs ni CA vérifiés.');
})().catch(e => { console.error(e); process.exitCode = 1; });
