// 24/10 (Gaëtan : « on ne voit pas les comptes Instagram que le clipper gère ») : la liste de l'onglet Comptes.
// Cas tirés des vraies lignes « Comptes app » du 24/10, avec des @ fictifs.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const mod = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/comptesVisibles.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: mod });
const { comptesAffiches, etatAffiche, etatEffectif } = mod;
const c = (n, handle, etat) => ({ n, handle, etat });

// Un compte refait porte le n° 5 : il doit apparaître, et en premier puisqu'il est le seul actif.
// Les @ sans ETAT (anciens @ remplacés, absents du classeur) disparaissent.
let r = comptesAffiches([c(1, 'ancien_a', ''), c(2, 'compte_b', 'à créer'), c(3, 'compte_c', 'à créer'), c(4, 'ancien_d', ''),
  c(5, 'compte_a2', 'GOOD'), c(6, 'ancien_e', '')]);
assert.deepEqual(r.map(x => x.handle), ['compte_a2', 'compte_b', 'compte_c']);

// Le BAN ne s'affiche pas ; « APPEL A FAIRE » reste visible juste après les actifs.
r = comptesAffiches([c(1, 'banni', 'BAN'), c(2, 'suspendu', 'APPEL A FAIRE'), c(3, 'prive', 'GOOD'), c(5, 'stock', 'à créer')]);
assert.deepEqual(r.map(x => x.handle), ['prive', 'suspendu', 'stock']);

// Un même @ listé deux fois ne s'affiche qu'une fois.
r = comptesAffiches([c(1, 'meme', 'GOOD'), c(2, '@Meme', 'GOOD'), c(3, 'autre', 'GOOD')]);
assert.deepEqual(r.map(x => x.n), [1, 3]);

// Un clipper sans compte : liste vide, l'app affiche « Pas encore de compte ».
assert.deepEqual(comptesAffiches([]), []);

// Libellés montrés au clipper, accents et casse ignorés.
assert.equal(etatAffiche('GOOD').libelle, 'Actif');
assert.equal(etatAffiche('warmup').libelle, 'Actif');
assert.equal(etatAffiche('Faire appel').libelle, 'Appel à faire');
assert.equal(etatAffiche('a creer').libelle, 'À créer');
assert.equal(etatAffiche('a creer').enLigne, false);
assert.equal(etatAffiche('BIZARRE').libelle, 'À vérifier');
assert.equal(etatAffiche('BAN').masque, true);
assert.equal(etatAffiche('').masque, true);
// 28/10 (audit) : croissance actifs, puis le privé, puis ce qui demande une action, puis à créer (avant : le privé n° 3 avant la
// croissance n° 7 de Mathieu)
const cr = (n, handle, etat, role) => ({ n, handle, etat, role });
r = comptesAffiches([cr(3, 'lien', 'GOOD', 'privé'), cr(7, 'croissance', 'GOOD', 'croissance'), cr(2, 'appel', 'APPEL A FAIRE', 'croissance'),
  cr(1, 'parti', 'INTROUVABLE', 'croissance'), cr(4, 'neuf', 'à créer', 'croissance')]);
assert.deepEqual(r.map(x => x.handle), ['croissance', 'lien', 'parti', 'appel', 'neuf']);
assert.equal(etatAffiche('INTROUVABLE').libelle, 'Introuvable');
assert.equal(etatAffiche('INTROUVABLE').enLigne, true);
// État effectif : le suivi Instagram corrige le badge, jamais qui gère le compte
assert.equal(etatEffectif('Faire appel', 'lu (RapidAPI)', 16), 'GOOD');
assert.equal(etatEffectif('Faire appel', 'lu (RapidAPI)', 0), 'Faire appel');
assert.equal(etatEffectif('Faire appel', 'introuvable (RapidAPI)', 7), 'Faire appel');
assert.equal(etatEffectif('GOOD', 'introuvable (RapidAPI)', null), 'INTROUVABLE');
assert.equal(etatEffectif('à créer', 'introuvable (RapidAPI)', null), 'à créer');
assert.equal(etatEffectif('GOOD', 'lu (RapidAPI)', 3), 'GOOD');
console.log('Comptes visibles : n° 4+ affichés, BAN et anciens @ masqués, doublons retirés, croissance puis privé puis le reste, état suivi.');
