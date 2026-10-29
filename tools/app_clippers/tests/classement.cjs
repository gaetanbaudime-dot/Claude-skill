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
const salaries = load('lib/salaries.ts');
const { classementClippers, pilotageEquipe, identiteDe, liensPublics } = load('lib/classement.ts', { '@/components/pilotage/calc': calc, '@/lib/salaries': salaries });
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
// 24/10 : le 4e compte actif s'affiche en plus des trois emplacements (➕) et compte dans les totaux de croissance
assert.equal(c.reels7, 21); assert.equal(c.vues7, 3000); assert.equal(c.comptes.length, 4);
assert.equal(c.comptes[2].numero, 3); assert.equal(c.comptes[2].etat, 'PRIVE'); assert.equal(c.comptes[2].prive, true);
assert.equal(c.comptes[3].handle, 'compte4'); assert.equal(c.comptes[3].extra, true); assert.equal(c.comptes[3].prive, false);
// Ban : numéros d'origine conservés ; le 4e compte actif reste un ➕, jamais promu à la place du 1.
let variant = { ...d, comptes: d.comptes.map(x => x.handle === 'compte1' ? { ...x, etat: 'BAN' } : x) };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.comptes.length, 3); assert.equal(c.comptes[0].numero, 2); assert.equal(c.reels7, 14);
assert.deepEqual(c.comptes.map(x => x.handle).join(), 'compte2,compte3,compte4'); assert.equal(c.comptes[2].extra, true);
// Un 4e compte qui n'est pas actif (à créer, ancien @) ne s'ajoute jamais
variant = { ...d, comptes: d.comptes.map(x => x.handle === 'compte4' ? { ...x, etat: 'à créer' } : x) };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.comptes.length, 3); assert.equal(c.reels7, 14);
// Un compte actif privé hors parcours (mesure « privé ») est un 🔒 en plus, hors des totaux de croissance
variant = { ...d, comptes: d.comptes.map(x => x.handle === 'compte4' ? { ...x, mesure: 'privé' } : x) };
c = classementClippers(variant).find(x => x.id === '1');
assert.equal(c.comptes[3].prive, true); assert.equal(c.reels7, 14);
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
// 24/10 : l'équipe d'un TL (tousActifs) garde aussi le 4e compte actif ; jamais les comptes d'une autre équipe
const scopedTl = pilotageEquipe(d, [{ prenom: 'Caroline', comptes: [1, 2, 3, 4].map(n => ({ handle: `compte${n}`, n })) }], { tousActifs: true });
assert.equal(scopedTl.comptes.length, 4); assert.ok(scopedTl.comptes.every(x => x.gerant === 'Caroline'));
assert.equal(classementClippers(scopedTl)[0].comptes.length, 4);
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
// 26/10 (Gaëtan : « enlève Rianah de tous les trucs, elle est au salaire ») : toutes ses identités sont au salaire ; le pilotage de
// l'admin (sansSalaries) la retire du classement, son app à elle garde sa fiche, sous son prénom
for (const nom of ['Rianah', 'Rianah Clipping Chloé', 'Rianah Metricool', 'Rianah (Metricool)', 'RIANAH']) assert.equal(salaries.estSalarie(nom), true, nom);
for (const nom of ['Caroline', 'Riana', '', 'Clipping Rianah']) assert.equal(salaries.estSalarie(nom), false, nom);
const avecRianah = { ...d, clippers: [...d.clippers, ref('9', 'Rianah', [{ handle: 'demo.rianah', numero: 1 }])],
  comptes: [...d.comptes, compte(1, { handle: 'demo.rianah', gerant: 'Rianah Clipping Chloé' })],
  clics: [...d.clics, clic('2026-10-16', 5000, { qui: 'Rianah Clipping Chloé' })] };
assert.equal(classementClippers(avecRianah, '', { sansSalaries: true }).some(x => /rianah/i.test(x.prenom)), false);
assert.equal(classementClippers(avecRianah, '', { sansSalaries: true }).length, classementClippers(d).length);
const sienne = classementClippers(avecRianah).find(x => x.id === '9');
assert.equal(sienne.prenom, 'Rianah'); assert.equal(sienne.clics7, 5000);
console.log('Classement: fenêtres 7j, totaux croissance, bans, privé en 2, données absentes, homonymes, cloisonnement TL et salaire validés.');
// 29/10 : une évolution énorme se lit en multiple (Ricardo de 1 à 346 clics : « × 346 », plus « 34500 % »)
assert.equal(calc.texteDelta(calc.variation(346, 1)), '× 346');
assert.equal(calc.texteDelta(899), '899 %');
assert.equal(calc.texteDelta(-12), '12 %');
assert.equal(calc.texteDelta(900), '× 10');
console.log('Évolutions : multiple au-delà de +900 %.');
