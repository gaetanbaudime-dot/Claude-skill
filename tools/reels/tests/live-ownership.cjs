// Explicit, preview-only integration check. Never part of the default build.
// Uses the selected app's existing Google helper and the real ownership modules.
// Appends four synthetic, hashed source associations; no media/provider calls,
// provisioning, permission changes, credential export or deletion of live data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { randomUUID, createHash } = require('node:crypto');
const { execFileSync } = require('node:child_process');

let stage = 'guard';
async function main() {
  const app = process.env.REELS_LIVE_VERIFY;
  assert(['clippers', 'creatrices'].includes(app));
  assert.equal(process.env.VERCEL_ENV, 'preview');
  const workbookId = process.env.REELS_OWNERSHIP_SPREADSHEET_ID;
  assert(typeof workbookId === 'string' && /^[a-zA-Z0-9_-]{1,200}$/.test(workbookId));
  assert(process.env.GOOGLE_SERVICE_ACCOUNT_JSON);
  const toolsRoot = path.resolve(__dirname, '../..');
  const appRoot = path.join(toolsRoot, 'app_' + app);
  assert.equal(fs.realpathSync(process.cwd()), fs.realpathSync(appRoot));
  const appRequire = require('node:module').createRequire(path.join(appRoot, 'package.json'));
  const ts = appRequire('typescript');
  const sourcePaths = new Set([
    path.join(appRoot, 'src/lib/google.ts'),
    path.join(toolsRoot, 'reels/src/server/ownership.ts'),
    path.join(toolsRoot, 'reels/src/server/ownership-sheets.ts'),
  ]);
  let googleRequests = 0;
  const guardedFetch = async (value, init = {}) => {
    const url = new URL(String(value));
    const method = init.method || 'GET';
    const oauth = url.origin === 'https://oauth2.googleapis.com' && url.pathname === '/token' && method === 'POST';
    const registry = url.origin === 'https://sheets.googleapis.com' &&
      url.pathname.startsWith('/v4/spreadsheets/' + workbookId + '/values/');
    assert(oauth || (registry && (method === 'GET' || (method === 'POST' && url.pathname.endsWith(':append')))));
    googleRequests++;
    return fetch(url, { ...init, redirect: 'error', signal: init.signal || AbortSignal.timeout(15000) });
  };
  const modules = new Map();
  function load(filename) {
    assert(sourcePaths.has(filename));
    if (modules.has(filename)) return modules.get(filename);
    const mod = { exports: {} };
    modules.set(filename, mod.exports);
    const localRequire = name => {
      if (name === 'crypto' || name === 'node:crypto') return require(name);
      if (name === './ownership') return load(path.join(toolsRoot, 'reels/src/server/ownership.ts'));
      throw new Error('Unexpected module');
    };
    const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    vm.runInNewContext(compiled, {
      module: mod, exports: mod.exports, require: localRequire,
      process: { env: { GOOGLE_SERVICE_ACCOUNT_JSON: process.env.GOOGLE_SERVICE_ACCOUNT_JSON } },
      Buffer, URL, URLSearchParams, AbortSignal, fetch: guardedFetch,
    }, { filename, timeout: 5000 });
    return mod.exports;
  }
  const { jetonGoogle } = load(path.join(appRoot, 'src/lib/google.ts'));
  const { createSheetsOwnershipStore } = load(path.join(toolsRoot, 'reels/src/server/ownership-sheets.ts'));
  const { authorize, OwnershipDenied, fingerprint, resource } = load(path.join(toolsRoot, 'reels/src/server/ownership.ts'));
  const runId = process.argv[2] === '--read' ? process.argv[3] : randomUUID();
  assert(typeof runId === 'string' && /^[a-f0-9-]{36}$/.test(runId));
  const cases = ['clippers', 'creatrices'].flatMap(namespace => ['a', 'b'].map(label => ({
    owner: { app: namespace, id: 'reels-integration-test:' + runId + ':' + label },
    sourceToken: 'reels-test-source:' + runId + ':' + namespace + ':' + label,
  })));
  const store = () => createSheetsOwnershipStore(app, jetonGoogle, { workbookId });
  if (process.argv[2] === '--read') {
    stage = 'independent-read-and-isolation';
    let foreignReferencesDenied = 0;
    for (const item of cases) {
      await authorize(item.owner, store(), 'source', 'target', { sourceToken: item.sourceToken });
      for (const other of cases.filter(candidate => candidate !== item)) {
        await assert.rejects(() => authorize(other.owner, store(), 'source', 'target', { sourceToken: item.sourceToken }),
          error => error instanceof OwnershipDenied);
        foreignReferencesDenied++;
      }
    }
    await assert.rejects(() => authorize(cases[0].owner, store(), 'source', 'target', { sourceToken: 'unknown:' + runId }),
      error => error instanceof OwnershipDenied);
    const snapshot = await store().read();
    const ownRows = snapshot.filter(row => cases.some(item =>
      row.owner === fingerprint([item.owner.app, item.owner.id]) && row.resource === resource('source', item.sourceToken)));
    assert.equal(ownRows.length, 4);
    console.log(JSON.stringify({ ok: true, freshProcess: true, persistedRows: 4, foreignReferencesDenied,
      unknownReferenceDenied: true, providerCalls: 0, googleRequests }));
    return;
  }
  stage = 'read-existing-registry';
  await store().read();
  stage = 'append-synthetic-associations';
  for (const item of cases) {
    const record = await authorize(item.owner, store(), 'source', 'create', {});
    await record({ sourceToken: item.sourceToken });
  }
  stage = 'fresh-process-verification';
  const child = JSON.parse(execFileSync(process.execPath, [__filename, '--read', runId], {
    cwd: appRoot, env: process.env, encoding: 'utf8', timeout: 180000, stdio: ['ignore', 'pipe', 'pipe'],
  }).trim());
  assert.equal(child.ok, true);
  console.log(JSON.stringify({ ok: true, app, stage: 'complete', syntheticRowsAppended: 4,
    workbookFingerprint: createHash('sha256').update(workbookId).digest('hex'),
    commit: process.env.VERCEL_GIT_COMMIT_SHA || null, verification: child,
    providerCalls: 0, parentGoogleRequests: googleRequests }));
}
main().catch(() => {
  // Never serialize exceptions: malformed credentials or upstream errors may
  // include private values. Partial test rows remain harmless hashed records.
  console.error(JSON.stringify({ ok: false, stage, code: 'REGISTRY_VERIFICATION_FAILED', providerCalls: 0 }));
  process.exitCode = 1;
});
