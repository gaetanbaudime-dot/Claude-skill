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
// 31/10 : la cadence ne compte que ses comptes de croissance (le Reel du compte privé le 22 n'y est pas)
eq(s.jours.map(j => j.reels), [3, 0, 0, 2, 0, 0, 7]);
assert.equal(s.reels, 12); assert.equal(s.cadence, 1.7);
assert.equal(s.vues, 30500); assert.equal(s.followers, 1540); assert.equal(s.clics, 120);
assert.equal(s.parJour, true);
// … compte par compte : barres empilées et moyenne de chacun (« Compte 1 », « Compte 2 » dans l'ordre de l'app)
eq(s.jours[6].parCompte, [4, 3]);
eq(s.croissance, [{ handle: 'c1', rang: 1, reels: 9, moyenne: 1.3 }, { handle: 'c2', rang: 2, reels: 3, moyenne: 0.4 }]);

// Colonne pas encore publiée : on retombe sur « Reels 7 j », sans graphique ; clics inconnus = null, jamais 0
s = a.semaine([{ ...croissance1, jours: undefined }, { ...prive, jours: undefined }], auj, null);
assert.equal(s.parJour, false); assert.equal(s.reels, 9); assert.equal(s.cadence, 1.3); assert.equal(s.clics, null);
// Aucun compte lu par le bot : « – », jamais 0 Reel (le cas d'un clipper à 1 129 clics le 24/10)
const nonLu = { handle: 'n', etat: 'GOOD', role: 'croissance', followers: 4, reels7: null, vues7: null, jours: {} };
s = a.semaine([nonLu, { ...nonLu, handle: 'n2' }], auj, { '2026-10-23': 50 });
assert.equal(s.reels, null); assert.equal(s.cadence, null); assert.equal(s.parJour, false); assert.equal(s.clics, 50);
assert.equal(a.reelsPrime([nonLu, { ...prive, jours: {} }], '2026-10-20', '2026-11-04', auj).mesure, false);
// Des Reels vus avant la fenêtre ne prouvent pas que le compte est lu aujourd'hui (le cas réel du 24/10)
const ancien = { ...nonLu, etat: 'Faire appel', jours: { '2026-10-12': 1, '2026-10-13': 2 } };
s = a.semaine([ancien, nonLu], auj, { '2026-10-23': 50 });
assert.equal(s.reels, null); assert.equal(s.cadence, null);
assert.equal(a.reelsPrime([ancien, nonLu], '2026-10-20', '2026-11-04', auj).mesure, false);
// Un compte relevé à 0 (Reels 7 j = 0) est mesuré : 0 est alors un vrai chiffre
s = a.semaine([{ ...nonLu, reels7: 0 }], auj, null);
assert.equal(s.reels, 0); assert.equal(s.cadence, 0);
s = a.semaine([], auj, null);
assert.equal(s.reels, null); assert.equal(s.vues, null); assert.equal(s.followers, null);

// Prime volume : jours clos de la période, comptes de croissance seulement, moyenne par compte (2 comptes)
let p = a.reelsPrime([croissance1, croissance2, prive], '2026-10-20', '2026-11-04', auj);
assert.equal(p.joursEcoules, 4);                       // 20, 21, 22, 23
assert.equal(p.reels, 9);                              // 2 + 4 + 3, le privé et aujourd'hui exclus
assert.equal(p.moyenne, 0.8);                          // 24/10 : compte par compte, 6/4 = 1,5 et 3/4 = 0,8 → le moins actif
eq(p.parCompte.map(c => [c.handle, c.moyenne]), [['c1', 1.5], ['c2', 0.8]]);
assert.equal(p.comptes, 2); assert.equal(p.mesure, true); assert.equal(p.manque, '');
// « La prime est la cadence moyenne sur chaque compte de croissance » : 6 par jour sur l'un et 0 sur l'autre, c'est 0
const fort = { handle: 'fort', etat: 'GOOD', role: 'croissance', followers: 1, reels7: 42, vues7: 1,
  jours: { '2026-10-20': 6, '2026-10-21': 6, '2026-10-22': 6, '2026-10-23': 6 } };
const vide = { handle: 'vide', etat: 'GOOD', role: 'croissance', followers: 1, reels7: 0, vues7: null, jours: {} };
p = a.reelsPrime([fort, vide], '2026-10-20', '2026-11-04', auj);
assert.equal(p.moyenne, 0); eq(p.parCompte.map(c => c.moyenne), [6, 0]);
// Trois comptes de croissance : on garde ses 2 plus actifs
p = a.reelsPrime([fort, vide, { ...fort, handle: 'fort2', jours: { '2026-10-20': 4, '2026-10-21': 4, '2026-10-22': 4, '2026-10-23': 4 } }], '2026-10-20', '2026-11-04', auj);
assert.equal(p.moyenne, 4);
// Un seul compte de croissance : la prime en demande 2, la cadence retenue est 0
p = a.reelsPrime([fort, prive], '2026-10-20', '2026-11-04', auj);
assert.equal(p.manque, 'deuxieme_compte'); assert.equal(p.moyenne, 0);
// Le 2e compte n'est pas lu par le bot : on ne conclut pas
p = a.reelsPrime([fort, { ...vide, reels7: null }], '2026-10-20', '2026-11-04', auj);
assert.equal(p.manque, 'deuxieme_non_lu'); assert.equal(p.moyenne, null); assert.equal(p.mesure, true);
// Le 2e compte est suspendu (« appel à faire ») : le suivi ne le relit plus, il ne publie rien, il compte pour 0 (« comptes en
// règle »), on conclut quand même (le cas de 3 clippers le 24/10)
const suspendu = { ...vide, handle: 'susp', etat: 'Appel à faire', reels7: null };
p = a.reelsPrime([fort, suspendu], '2026-10-20', '2026-11-04', auj);
assert.equal(p.manque, ''); assert.equal(p.moyenne, 0); assert.equal(p.mesure, true);
eq(p.parCompte.map(c => [c.handle, c.moyenne, Boolean(c.suspendu)]), [['fort', 6, false], ['susp', 0, true]]);
// Deux bons comptes et un suspendu : on garde les 2 bons
p = a.reelsPrime([suspendu, fort, { ...fort, handle: 'fort2' }], '2026-10-20', '2026-11-04', auj);
assert.equal(p.moyenne, 6); eq(p.parCompte.slice(0, 2).map(c => c.handle), ['fort', 'fort2']);
// 28/10 : un compte introuvable sur Instagram (actif au LOG) compte pour 0 lui aussi, au lieu de « 2e compte pas encore suivi »
const parti = { ...vide, handle: 'parti', etat: 'INTROUVABLE', reels7: null };
p = a.reelsPrime([fort, parti], '2026-10-20', '2026-11-04', auj);
assert.equal(p.manque, ''); assert.equal(p.moyenne, 0);
eq(p.parCompte.map(c => [c.handle, c.moyenne, Boolean(c.suspendu), Boolean(c.introuvable)]), [['fort', 6, false, false], ['parti', 0, true, true]]);
// Un compte suspendu seul ne fait pas un clipper « suivi »
assert.equal(a.reelsPrime([suspendu, { ...suspendu, handle: 'susp2' }], '2026-10-20', '2026-11-04', auj).mesure, false);
p = a.reelsPrime([croissance1], '2026-10-24', '2026-11-04', auj);
assert.equal(p.joursEcoules, 0); assert.equal(p.moyenne, null);
p = a.reelsPrime([croissance1], '2026-10-05', '2026-10-19', auj);           // période close : s'arrête à sa fin
assert.equal(p.joursEcoules, 15); assert.equal(p.reels, 9);               // 10/10 et 17/10
assert.equal(a.reelsPrime([{ ...croissance1, jours: undefined }], '2026-10-20', '2026-11-04', auj).mesure, false);

// 31/10 : un compte « à créer » n'est pas un 2e compte de croissance (avant : « 2e compte pas encore suivi »)
p = a.reelsPrime([fort, { ...vide, handle: 'neuf', etat: 'à créer', reels7: null }], '2026-10-20', '2026-11-04', auj);
assert.equal(p.manque, 'deuxieme_compte'); assert.equal(p.comptes, 1);
// … le n° de chaque compte (« Compte 1 », « Compte 2 ») suit l'ordre de l'app, pas l'activité ; jours de la période et restants
p = a.reelsPrime([vide, fort], '2026-10-20', '2026-11-04', auj);
eq(p.parCompte.map(c => [c.handle, c.rang]), [['fort', 2], ['vide', 1]]);
assert.equal(p.totalJours, 16); assert.equal(p.joursEcoules, 4); assert.equal(p.joursRestants, 12);
assert.equal(a.reelsPrime([fort], '2026-10-05', '2026-10-19', auj).joursRestants, 0);   // période close

// 31/10 : le rythme à tenir jusqu'à la fin de la période pour finir à la cible
assert.equal(a.rythmeNecessaire(10, 16, 12, 3), 3.2);      // 48 Reels pour 3/jour sur 16 jours, il en reste 38 en 12 jours
assert.equal(a.rythmeNecessaire(48, 16, 12, 3), 0);        // déjà assuré
assert.equal(a.rythmeNecessaire(12, 16, 12, 3), 3);        // 36 en 12 jours : 3 pile, sans arrondi parasite
assert.equal(a.rythmeNecessaire(5, 16, 0, 3), null);       // période finie

// 31/10 : Reels → vues → clics sur 14 jours (vues des Reels publiés ce jour-là)
const v1 = { ...croissance1, vuesJours: { '2026-10-17': 9000, '2026-10-20': 4000, '2026-10-23': 30000 } };
const v2 = { ...croissance2, vuesJours: { '2026-10-23': 6000 } };
let k = a.correlation([v1, v2, prive], auj, { '2026-10-23': 120, '2026-10-20': 30 }, 14);
assert.equal(k.jours.length, 14); assert.equal(k.jours[13].jour, '2026-10-23'); assert.equal(k.jours[0].jour, '2026-10-10');
eq(k.jours[13].reels, [4, 3]); assert.equal(k.jours[13].vues, 36000); assert.equal(k.jours[13].clics, 120);
assert.equal(k.reels, 18);                                 // 6 le 10 + 3 + 2 + 7 ; le privé ne compte pas
assert.equal(k.vues, 49000); assert.equal(k.clics, 150);
assert.equal(k.vuesParReel, 2722); assert.equal(k.clicsParReel, 8.3);
eq(k.meilleur, { jour: '2026-10-23', reels: 7, vues: 36000, clics: 120 });
eq(k.croissance, [{ handle: 'c1', rang: 1 }, { handle: 'c2', rang: 2 }]);
// Sans suivi des vues ni clics : les rangées manquantes sont null, jamais 0 inventé
k = a.correlation([croissance1, croissance2], auj, null, 14);
assert.equal(k.vues, null); assert.equal(k.clics, null); assert.equal(k.vuesParReel, null);
assert.equal(a.correlation([nonLu], auj, null, 14), null);   // aucun Reel suivi : pas de graphique

// Paliers : il faut les Reels ET les clics
let e = a.evaluerPrime(6.2, 410);
eq(e.paliers.map(x => x.atteint), [true, true, false]); assert.equal(e.atteint.bonus, 20);
assert.equal(e.paliers[2].manqueReels, 2.8); assert.equal(e.paliers[2].manqueClics, 190);
e = a.evaluerPrime(9.5, 150);
assert.equal(e.atteint, null); assert.equal(e.paliers[0].okReels, true); assert.equal(e.paliers[0].manqueClics, 50);
e = a.evaluerPrime(null, null);
assert.equal(e.atteint, null); assert.equal(e.paliers[0].okReels, false);
console.log('Activité : 7 jours clos par compte de croissance, Reels → vues → clics, prime (suspendus à 0, rythme à tenir) et paliers vérifiés.');
