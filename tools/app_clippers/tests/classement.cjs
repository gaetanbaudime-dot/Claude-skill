const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
function load(file, deps = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText, { exports, URL, Date, require: n => { if (!(n in deps)) throw Error(n); return deps[n]; } });
  return exports;
}
const calc = load('components/pilotage/calc.ts');
const { classementClippers, pilotageEquipe, identiteDe, liensPublics } = load('lib/classement.ts', { '@/components/pilotage/calc': calc });
const compte = (numero, patch = {}) => ({ creatrice: 'Chloé', axe: 'Horizontal', type: 'Clipper', gerant: 'Caroline',
  numero, handle: `compte${numero}`, etat: 'GOOD', followers: 123, reels7: 7, reelsHier: 1, vuesRecentes: 1000,
  clics7: null, ...patch });
const ref = (uid, prenom, comptes = []) => ({ uid, prenom, role: 'Clipper', creatrice: 'Chloé', comptes,
  gaml: 'https://chloe-callista.fr/3', visites7: null });
const clic = (jour, visites, patch = {}) => ({ jour, visites, creatrice: 'Chloé', axe: 'Horizontal', source: 'Clipper', qui: 'Caroline', manquants: 0, ...patch });
const d = { aujourdhui: '2026-10-17', publie: 'now', fraicheur: '', taux: 0.92, subs: [{ caOfUsd: 999 }], boutons: [],
  clippers: [ref('1', 'Caroline', [1, 2, 3].map(n => ({ handle: `compte${n}`, numero: n }))), ref('2', 'Clara', [{ handle: 'clara', numero: 1 }])],
  comptes: [compte(1), compte(2), compte(3, { etat: 'PRIVE', reels7: 99, vuesRecentes: 99999 }), compte(4), compte(1, { handle: 'clara', gerant: 'Clara' })],
  clics: [...calc.jours('2026-10-03', '2026-10-09').map(j => clic(j, 10)), ...calc.jours('2026-10-10', '2026-10-16').map(j => clic(j, 20)), clic('2026-10-17', 9000), clic('2026-10-16', 3000, { qui: 'Clara' })] };
let c = classementClippers(d).find(x => x.id === '1');
assert.equal(c.clics7, 140); assert.equal(c.avant7, 70); assert.equal(c.serie.length, 7);
assert.equal(c.reels7, 14); assert.equal(c.vues7, 2000); assert.equal(c.comptes.length, 3);
assert.equal(c.comptes[2].numero, 3); assert.equal(c.comptes[2].etat, 'PRIVE');
// Ban : conserver les numéros d'origine, ne pas promouvoir un ancien quatrième compte.
let variant = { ...d, comptes: d.comptes.map(x => x.handle === 'compte1' ? { ...x, etat: 'BAN' } : x) };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.comptes.length, 2); assert.equal(c.comptes[0].numero, 2); assert.equal(c.reels7, 7);
// Ancien parcours : privé en 2, croissance en 3.
variant = { ...d, comptes: [compte(1, { roleCompte: 'croissance' }), compte(2, { roleCompte: 'privé' }), compte(3, { roleCompte: 'croissance' })] };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.comptes[1].handle, 'compte3'); assert.equal(c.comptes[2].handle, 'compte2');
// Une mesure absente n'est pas un zéro ; une somme connue mais incomplète est signalée.
variant = { ...d, comptes: [compte(1, { reels7: null, vuesRecentes: null }), compte(2), compte(3)] };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.reels7, 7); assert.equal(c.partielReels, true); assert.equal(c.partielVues, true);
variant = { ...d, clics: d.clics.map(x => x.jour === '2026-10-16' ? { ...x, manquants: 1 } : x) };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.serie[6], null); assert.equal(c.manquants, 1);
assert.equal(identiteDe('Alex', [ref('3', 'Alex Martin'), ref('4', 'Alex Paul')]), undefined);
// L'API TL doit retirer les autres équipes, le CA, les subs et les boutons.
const scoped = pilotageEquipe(d, [{ prenom: 'Caroline', comptes: [1, 2, 3].map(n => ({ handle: `compte${n}`, n })) }]);
assert.equal(scoped.comptes.length, 3); assert.equal(scoped.clippers.length, 1);
assert.ok(scoped.clics.every(x => x.qui === 'Caroline')); assert.equal(scoped.subs.length, 0); assert.equal(scoped.boutons.length, 0);
assert.equal(classementClippers(scoped).length, 1);
const renamed = { ...d, comptes: d.comptes.filter(x => x.numero !== 4).map(x => x.handle === 'compte1' ? { ...x, handle: 'nouveau', numero: undefined } : x) };
c = classementClippers(renamed).find(x => x.id === '1');
assert.equal(c.comptes.length, 3); assert.equal(c.comptes[0].handle, 'nouveau');
const renamedScope = pilotageEquipe(renamed, [{ prenom: 'Caroline', comptes: [1, 2, 3].map(n => ({ handle: `compte${n}`, n })) }]);
assert.ok(renamedScope.comptes.some(x => x.handle === 'nouveau'));
const waiting = pilotageEquipe(d, [{ prenom: 'Nouveau', creatrice: 'Sarah', comptes: [] }]);
assert.equal(classementClippers(waiting).length, 1); assert.equal(waiting.clics.length, 0);
assert.equal(liensPublics('javascript:alert(1) · https://chloe-callista.fr/3').length, 1);
assert.equal(classementClippers(d, 'Sarah').length, 0);
console.log('Classement: fenêtres 7j, totaux croissance, bans, privé en 2, données absentes, homonymes et cloisonnement TL validés.');
