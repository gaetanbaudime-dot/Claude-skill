// Run from either host app after npm ci. A green source test is insufficient
// if npm/Vercel retained an older packed file: dependency in node_modules.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const source = path.resolve(__dirname, '..');
const app = process.cwd();
assert(['app_clippers', 'app_creatrices'].includes(path.basename(app)));
const installed = path.join(app, 'node_modules/@gm/reels');
const manifest = JSON.parse(fs.readFileSync(path.join(source, 'package.json'), 'utf8'));
const actual = JSON.parse(fs.readFileSync(path.join(installed, 'package.json'), 'utf8'));
const lock = JSON.parse(fs.readFileSync(path.join(app, 'package-lock.json'), 'utf8'));
assert.equal(actual.version, manifest.version, 'Installed shared package version is stale');
assert.equal(lock.packages['node_modules/@gm/reels'].version, manifest.version, 'Lock and source versions differ');
assert.deepEqual(actual.exports, manifest.exports);
let checked = 0;
function compare(relative) {
  for (const entry of fs.readdirSync(path.join(source, relative), { withFileTypes: true })) {
    const file = path.join(relative, entry.name);
    if (entry.isDirectory()) compare(file);
    else {
      assert(fs.readFileSync(path.join(source, file)).equals(fs.readFileSync(path.join(installed, file))), 'Stale installed file: ' + file);
      checked++;
    }
  }
}
compare('src');
assert(fs.readFileSync(path.join(source, 'UPSTREAM.md')).equals(fs.readFileSync(path.join(installed, 'UPSTREAM.md'))));
console.log(JSON.stringify({ app: path.basename(app), package: manifest.name, version: manifest.version, sourceFilesIdentical: checked }));
