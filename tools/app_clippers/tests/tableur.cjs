// 31/10 : une rafale d'ouvertures ne lance qu'une recherche du tableur ; un échec sans id connu ne bloque qu'une minute.
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
function charger(fetchSimule, maintenant) {
  const mod = {};
  const DateSimulee = class extends Date { static now() { return maintenant.t; } };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/usage.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports: mod, fetch: fetchSimule, Date: DateSimulee, Intl, encodeURIComponent, JSON, Promise, Error, Object,
    require: (n) => (n === './google' ? { jetonGoogle: async () => 'jeton' } : { creatrices: () => ({}) }) });
  return mod;
}
const reponse = (status, corps) => ({ ok: status < 400, status, json: async () => corps, text: async () => JSON.stringify(corps) });
(async () => {
  // 1. Cinq requêtes en même temps sur une instance neuve : une seule recherche Drive, un seul id
  let recherches = 0;
  const horloge = { t: 1_000_000 };
  let m = charger(async (url) => {
    if (url.includes('/drive/v3/files?q=')) { recherches++; await new Promise((ok) => setTimeout(ok, 20)); return reponse(200, { files: [{ id: 'ID1' }] }); }
    if (url.includes('fields=sheets.properties')) return reponse(200, { sheets: [{ properties: { sheetId: 0, title: 'Événements' } }] });
    return reponse(200, {});
  }, horloge);
  const ids = await Promise.all([1, 2, 3, 4, 5].map(() => m.tableur()));
  assert.deepEqual(ids, ['ID1', 'ID1', 'ID1', 'ID1', 'ID1']);
  assert.equal(recherches, 1);

  // 2. Instance neuve, Drive en quota dépassé : erreur, puis pas de nouvel appel pendant une minute, puis nouvel essai
  recherches = 0;
  let quota = true, quotaEcriture = false;
  m = charger(async (url) => {
    if (url.includes(':append')) return quotaEcriture ? reponse(429, { error: 'quota' }) : reponse(200, {});
    if (url.includes('/drive/v3/files?q=')) { recherches++; return quota ? reponse(429, { error: 'quota' }) : reponse(200, { files: [{ id: 'ID2' }] }); }
    if (url.includes('fields=sheets.properties')) return reponse(200, { sheets: [{ properties: { sheetId: 0, title: 'Événements' } }] });
    return reponse(200, {});
  }, horloge);
  await assert.rejects(m.tableur());
  await assert.rejects(m.tableur(), /une minute/);
  assert.equal(recherches, 1);
  horloge.t += 61_000; quota = false;
  assert.equal(await m.tableur(), 'ID2');
  assert.equal(recherches, 2);

  // 3. Un quota dépassé en écrivant un événement ne fait plus oublier l'id (avant : nouvelle recherche, puis blocage de l'app)
  quotaEcriture = true;
  const avant = recherches;
  const erreur = await m.enregistrer('Test', 'ouverture', 'web');
  assert.match(erreur, /429/);
  assert.equal(await m.tableur(), 'ID2');
  assert.equal(recherches, avant);
  console.log("Tableur d'usage : une recherche par rafale, une minute d'attente sans id, id gardé sur une erreur passagère.");
})().catch((e) => { console.error(e); process.exit(1); });
