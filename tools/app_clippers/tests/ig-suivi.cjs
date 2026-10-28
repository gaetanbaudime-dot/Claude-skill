// 24/10 : l'app prend ses chiffres Instagram au suivi RapidAPI (« IG · Comptes », « IG · Reels »). @ fictifs, chiffres du cas réel.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const charger = (fichier, deps = {}) => {
  const m = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib', fichier), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports: m, Date, Intl, Number, Map, Set, String, Math, require: (n) => deps[n] });
  return m;
};
const visibles = charger('comptesVisibles.ts');
const mod = charger('igSuivi.ts', { './comptesVisibles': visibles });
const ig = mod;
const eq = (x, y) => assert.deepEqual(JSON.parse(JSON.stringify(x)), y);

// Une ligne « IG · Comptes » (A:W) : un compte « restreint » pour l'ancien relevé, bien lu par RapidAPI
const ligne = (h, statut, followers, pubs, r7, r30, v7, dernier, renomme = '') =>
  ['Chloé', 'Caroline', 'Clipper', h, '1', statut, String(followers), '', '', String(pubs), '', String(r7), '', String(r30), '', String(v7), '', '', '', dernier, '2026-10-24T06:11:57+00:00', '', renomme];
const comptes = ig.lireIgComptes([
  ligne('croissance.a', 'public', 1669, 118, 20, 70, 223683, '2026-10-23T19:51:26+00:00'),
  ligne('ancien.prv', 'public', 7, 34, 7, 33, 1094, '2026-10-23T19:52:03+00:00'),
  ligne('vrai.prive', 'privé', 179, 2, 0, 0, 0, ''),
  ligne('lien.ouvert', 'public', 152, 0, 0, 0, 0, ''),
  ligne('disparu', 'introuvable', '', '', '', '', '', ''),
  ligne('vieux.nom', 'public', 10, 3, 1, 2, 5, '2026-10-20T10:00:00+00:00', 'nouveau.nom'),
]);
assert.equal(comptes.get('croissance.a').followers, 1669);
assert.equal(comptes.get('nouveau.nom').followers, 10);            // un compte renommé se trouve sous ses deux @

// « IG · Reels » (D:H) : jour à Paris, un Reel compté une fois, rien avant la fenêtre
const jours = ig.lireIgJours([
  ['croissance.a', 'c1', 'l1', '2026-10-23T21:30:00+00:00', '10'],   // 23h30 à Paris : le 23
  ['croissance.a', 'c2', 'l2', '2026-10-23T22:30:00+00:00', '10'],   // 0h30 à Paris : le 24
  ['croissance.a', 'c2', 'l2', '2026-10-23T22:30:00+00:00', '10'],   // doublon
  ['croissance.a', 'c3', 'l3', '2026-10-01T10:00:00+00:00', '10'],   // avant la fenêtre
  ['ancien.prv', 'c4', 'l4', '2026-10-22T10:00:00+00:00', '5'],
], '2026-10-08');
eq(jours.get('croissance.a'), { '2026-10-23': 1, '2026-10-24': 1 });
const suivi = { comptes, jours };

// Les chiffres RapidAPI remplacent l'ancien relevé vide
const base = (handle, role) => ({ handle, role, followers: null, reels7: null, vues7: null, jours: {}, mesure: 'restreint', dernierReel: '' });
let c = ig.appliquerIg(base('croissance.a', 'croissance'), suivi, '2026-10-24');
assert.equal(c.followers, 1669); assert.equal(c.reels7, 20); assert.equal(c.vues7, 223683);
eq(c.jours, { '2026-10-23': 1, '2026-10-24': 1 });
assert.equal(c.mesure, 'lu (RapidAPI)'); assert.equal(c.dernierReel, 'hier');   // 19h51 UTC le 23 = 21h51 à Paris le 23
// Le rôle suit ce que fait le compte : Reels publics = croissance, même n° 3 dans la fiche ; privé sur Instagram = privé
assert.equal(ig.appliquerIg(base('ancien.prv', 'privé'), suivi, '2026-10-24').role, 'croissance');
assert.equal(ig.appliquerIg(base('vrai.prive', 'croissance'), suivi, '2026-10-24').role, 'privé');
assert.equal(ig.appliquerIg(base('lien.ouvert', 'privé'), suivi, '2026-10-24').role, 'privé');  // ouvert sans Reel : la fiche décide
// Le compte qui reçoit les clics GAML porte le lien : privé, même ouvert et même avec des Reels (compte du lien de Mathieu, 24/10)
const liens = ig.porteursDeLien([{ handle: '@Ancien.PRV', clics7: 41, clicsHier: 3 }, { handle: 'croissance.a', clics7: 0, clicsHier: 0 },
  { handle: 'vrai.prive', clics7: null }]);
eq([...liens], ['ancien.prv']);
assert.equal(ig.appliquerIg(base('ancien.prv', 'croissance'), suivi, '2026-10-24', liens).role, 'privé');
assert.equal(ig.appliquerIg(base('croissance.a', 'croissance'), suivi, '2026-10-24', liens).role, 'croissance');
assert.equal(ig.appliquerIg(base('pas.suivi', 'croissance'), suivi, '2026-10-24', new Set(['pas.suivi'])).role, 'privé');  // même inconnu de RapidAPI
// Des Reels il y a 3 semaines mais plus rien depuis 7 jours : ce n'est pas un compte de croissance, la fiche décide
const vieux = ig.lireIgComptes([ligne('vieux.reels', 'public', 150, 6, 0, 6, 0, '2026-10-05T10:00:00+00:00')]);
assert.equal(ig.appliquerIg(base('vieux.reels', 'privé'), { comptes: vieux, jours: new Map() }, '2026-10-24').role, 'privé');
// Introuvable : signalé, chiffres non inventés ; compte inconnu de RapidAPI ou suivi illisible : rien ne change
assert.equal(ig.appliquerIg(base('disparu', ''), suivi, '2026-10-24').mesure, 'introuvable (RapidAPI)');
const inconnu = base('pas.suivi', 'croissance');
assert.equal(ig.appliquerIg(inconnu, suivi, '2026-10-24'), inconnu);
assert.equal(ig.appliquerIg(inconnu, null, '2026-10-24'), inconnu);

// 28/10 : l'état affiché suit le suivi. « Faire appel » au LOG mais lu en public avec des Reels : actif ; actif au LOG mais
// introuvable : « Introuvable » (et le compte du lien reste privé)
const avecEtat = (handle, etat, role) => ({ ...base(handle, role), etat });
assert.equal(ig.appliquerIg(avecEtat('croissance.a', 'Faire appel', 'croissance'), suivi, '2026-10-24').etat, 'GOOD');
assert.equal(ig.appliquerIg(avecEtat('lien.ouvert', 'Faire appel', 'privé'), suivi, '2026-10-24').etat, 'Faire appel');   // 0 Reel : rien ne change
const disparu = ig.appliquerIg(avecEtat('disparu', 'GOOD', 'croissance'), suivi, '2026-10-24', new Set(['disparu']));
assert.equal(disparu.etat, 'INTROUVABLE'); assert.equal(disparu.role, 'privé');
assert.equal(ig.appliquerIg(avecEtat('disparu', 'APPEL A FAIRE', 'croissance'), suivi, '2026-10-24').etat, 'APPEL A FAIRE');
assert.equal(ig.appliquerIg(avecEtat('disparu', 'à créer', ''), suivi, '2026-10-24').etat, 'à créer');
assert.equal(ig.appliquerIg(base('croissance.a', 'croissance'), suivi, '2026-10-24').etat, undefined);   // sans état : rien d'ajouté

// Dernier Reel au format du bot (lu par alerteMesure)
assert.equal(ig.dernierReelRelatif('2026-10-23T10:00:00+00:00', '2026-10-24'), 'hier');
assert.equal(ig.dernierReelRelatif('2026-10-20T10:00:00+00:00', '2026-10-24'), 'il y a 4 j');
assert.equal(ig.dernierReelRelatif('', '2026-10-24'), 'aucun');
console.log('Suivi RapidAPI : comptes restreints lus, renommés trouvés, jours à Paris, rôles (lien GAML compris), introuvables et repli vérifiés.');
