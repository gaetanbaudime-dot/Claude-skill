// 31/10 (Pierre) : un groupe dont tous les liens sont rattachés par le bot à UNE autre clé rejoint ce clipper ; son ancien jeton
// mène toujours à lui. Rien ne bouge sans onglet, ni pour un clipper que le bot publie sous sa propre clé, ni sur un doute.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
process.env.CLIPPERS_SECRET = 'secret-de-test';
const mod = {};
const deps = { crypto: require('node:crypto'), './gaml': { liensGaml: async () => [] }, './comptesApp': {}, './regimes': {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/clippers.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: mod, require: (n) => deps[n], process, Map, Set, Promise, String, Object, Array });
const c = mod;
const lien = (id, note, createdAt) => ({ id, url: `https://exemple.fr/${id}`, note, name: 'Sophie', createdAt, enabled: true });
const UID = 'uid:1471000000000000001';
const base = c.nommer(c.regrouper([
  lien('l14', 'Clipping Pierre', '2026-10-08T10:00:00Z'),
  lien('l1', 'Clipping UID:1471000000000000001', '2026-10-26T10:00:00Z'),
  lien('l7', 'Clipping Thia', '2026-09-16T10:00:00Z'),
]), new Map([[UID, 'Pierre']]));
assert.equal(base.length, 3);
const jetonPierre = base.find((x) => x.cle === 'pierre').jeton;
const jetonUid = base.find((x) => x.cle === UID).jeton;

// le bot rattache /14 et /1 à la clé uid : une seule app, deux liens, clé et jeton de la clé uid
const cles = new Map([[UID, new Set(['l14', 'l1'])], ['thia', new Set(['l7'])]]);
const { liste, anciennes } = c.fusionner(base, cles);
assert.equal(liste.length, 2);
const p = liste.find((x) => x.cle === UID);
assert.equal(p.prenom, 'Pierre');
assert.equal(p.jeton, jetonUid);
assert.equal(p.liens.map((l) => l.id).join(','), 'l1,l14');             // le plus récent d'abord
assert.equal(anciennes.get(jetonPierre), UID);                           // l'ancien lien de l'app mène à Pierre
assert.equal(liste.find((x) => x.cle === 'thia').liens.length, 1);
assert.equal(base.find((x) => x.cle === UID).liens.length, 1);          // l'entrée n'est pas modifiée

// rien ne bouge : onglet illisible, vide, ou clé publiée telle quelle par le bot (ancien régime « pierre »)
assert.equal(c.fusionner(base, null).liste, base);
assert.equal(c.fusionner(base, new Map()).liste, base);
assert.equal(c.fusionner(base, new Map([['pierre', new Set(['l14'])], [UID, new Set(['l1'])]])).liste.length, 3);
// un seul lien du groupe rattaché ailleurs : pas de fusion (tous les liens, ou rien)
const deux = c.regrouper([lien('a1', 'Clipping Pierre', '2026-10-01T00:00:00Z'), lien('a2', 'Clipping Pierre', '2026-10-02T00:00:00Z'),
  lien('l1', 'Clipping UID:1471000000000000001', '2026-10-26T10:00:00Z')]);
assert.equal(c.fusionner(deux, new Map([[UID, new Set(['a1', 'l1'])]])).liste.length, 2);
// deux clés candidates : on ne choisit pas
const trois = c.regrouper([lien('l14', 'Clipping Pierre', '2026-10-08T10:00:00Z'), lien('x', 'Clipping UID:1', '2026-10-26T10:00:00Z'),
  lien('y', 'Clipping UID:2', '2026-10-27T10:00:00Z')]);
assert.equal(c.fusionner(trois, new Map([['uid:1', new Set(['l14', 'x'])], ['uid:2', new Set(['l14', 'y'])]])).liste.length, 3);
// clé d'arrivée absente de l'app : pas de fusion vers un clipper fantôme
assert.equal(c.fusionner(c.regrouper([lien('l14', 'Clipping Pierre', '2026-10-08T10:00:00Z')]), new Map([[UID, new Set(['l14'])]])).liste.length, 1);
console.log('Fusion des apps d\'un même clipper : une app, ancien lien valable, aucun doute fusionné vérifiés.');
