// 27/10 : un lien noté « Clipping UID:<id Discord> » par le bot garde sa clé (donc son jeton) et prend le prénom de « Comptes app ».
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
process.env.CLIPPERS_SECRET = 'secret-de-test';
const mod = {};
const deps = { crypto: require('node:crypto'), './gaml': { liensGaml: async () => [] }, './comptesApp': {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/clippers.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: mod, require: (n) => deps[n], process, Map, Set, Promise, String, Object, Array });
const c = mod;
const lien = (note, name, createdAt, url) => ({ id: url, url, note, name, createdAt, enabled: true });
const liste = c.regrouper([
  lien('Clipping UID:1560000000000000001', 'Chloé', '2026-10-24T06:17:52Z', 'https://exemple.fr/5'),
  lien('Clipping Caroline', 'Chloé', '2026-09-02T10:00:00Z', 'https://exemple.fr/3'),
  lien('Clipping libre (ex-Esperance)', 'Chloé', '2026-09-26T13:55:06Z', 'https://exemple.fr/13'),
]);
assert.equal(liste.length, 2);
const uid = liste.find((x) => x.cle.startsWith('uid:'));
assert.equal(uid.cle, 'uid:1560000000000000001'); assert.equal(uid.prenom, 'UID:1560000000000000001');
assert.equal(c.estCleUid(uid.cle), true); assert.equal(c.estCleUid('caroline'), false);
const noms = new Map([['uid:1560000000000000001', 'Esperance'], ['caroline', 'Autre']]);
const nommes = c.nommer(liste, noms);
const e = nommes.find((x) => x.cle === uid.cle);
assert.equal(e.prenom, 'Esperance');                     // le prénom vient de « Comptes app »
assert.equal(e.jeton, uid.jeton);                        // la clé et le jeton ne changent pas : le lien de l'app reste le même
assert.equal(nommes.find((x) => x.cle === 'caroline').prenom, 'Caroline');   // une clé prénom n'est jamais renommée
assert.equal(c.nommer(liste, null), liste);             // onglet illisible : comme avant
assert.equal(c.nommer(liste, new Map()).find((x) => x.cle === uid.cle).prenom, 'UID:1560000000000000001');
console.log('Clés « uid:… » : prénom repris de « Comptes app », clé et jeton inchangés, repli sans onglet vérifiés.');
