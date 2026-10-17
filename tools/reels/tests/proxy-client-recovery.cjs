// Actual browser orchestration + actual proxy/ownership modules. Only Sheets
// and the provider transport are simulated. Never uses credentials or network.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const ts = require(require.resolve('typescript', { paths: [path.join(__dirname, '../../app_clippers')] }));
const { scenario, latestSource } = require('./native-speed-orchestration.cjs');

function bridge(target, failure = '') {
  const calls = [], replies = [];
  let failed = false;
  const transport = (provider, initial) => {
    let backend;
    const modules = new Map();
    const load = name => {
      if (modules.has(name)) return modules.get(name);
      const module = { exports: {} };
      const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/server', name + '.ts'), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      }).outputText;
      vm.runInNewContext(code, { module, exports: module.exports,
        require: name => name.startsWith('.') ? load(name.slice(2)) : require(name),
        fetch: (...args) => backend(...args), Request, Response, Headers, URL, URLSearchParams,
        AbortSignal, AbortController, Uint8Array, TextDecoder });
      modules.set(name, module.exports); return module.exports;
    };
    const { fingerprint, resource } = load('ownership');
    const { forwardReelsRequest } = load('proxy');
    const owner = { app: 'clippers', id: 'offline-owner' };
    const ownerHash = fingerprint([owner.app, owner.id]);
    const rows = [];
    const add = (kind, key, parent = '-') => rows.push({ kind, resource: key, parent, owner: ownerHash });
    const source = resource('source', initial.sourceToken || 'fixture-source');
    const upload = resource('upload', initial.uploadId);
    const project = resource('project', 'existing-project');
    add('source', source); add('upload', upload, source); add('project', project, upload);
    for (const clip of [...initial.selected, ...(initial.sourceClips || [])]) {
      add('clip', resource('clip', clip.projectId, clip.clipId), project);
    }
    if (initial.collectionId) {
      const collection = resource('collection', initial.collectionId);
      add('collection', collection, project);
      add('collection-set', resource('collection-set', initial.collectionId, ...initial.selected.map(c => c.clipId).sort()), collection);
    }
    backend = async (url, init) => {
      const u = new URL(url), body = init.body ? JSON.parse(init.body) : Object.fromEntries(u.searchParams);
      const action = body.action || 'finish';
      calls.push({ action, index: body.index, clipId: body.clipId });
      const response = await provider(url, init);
      // A lost reply after style application remains ambiguous.
      if (!failed && failure === 'lost' && action === target) { failed = true; throw Error('lost provider response'); }
      const payload = await response.json();
      if (action === 'clips') payload.projectId = body.projectId;
      if (action === 'clips' && failure === 'unknownStyle') payload.clips[0].styleIndex = null;
      if (action === 'export-pack' && response.ok) payload.clips = [];
      if (failure === 'partial429' && action === target) payload.upstreamNotCalled = true;
      const headers = new Headers(response.headers); headers.set('Content-Type', 'application/json');
      return Response.json(payload, { status: response.status, headers });
    };
    return async (input, init = {}) => {
      const u = new URL(String(input), 'https://app.example.test');
      if (!u.pathname.startsWith('/api/')) return provider(input, init);
      const body = init.body ? JSON.parse(init.body) : Object.fromEntries(u.searchParams);
      const action = body.action || 'finish';
      const before = calls.length;
      const store = {
        read: async () => {
          if (!failed && action === target && (failure === 'pre' || (failure === 'post' && calls.length > before))) {
            failed = true; throw Error('simulated Sheets unavailable');
          }
          return rows.map(row => ({ ...row }));
        },
        append: async additions => { rows.push(...additions.map(row => ({ ...row }))); },
      };
      const request = new Request(u, { ...init, headers: { ...init.headers, Origin: u.origin } });
      const reply = await forwardReelsRequest(request, u.pathname.split('/').at(-1), owner, store);
      if (!reply.ok) replies.push({ action, status: reply.status, body: await reply.clone().json(), calls: calls.length - before });
      return reply;
    };
  };
  return { transport, calls, replies };
}

const configs = {
  submit: { submitFlow: true, available: Array(6).fill(0), durations: Array(6).fill(1) },
  duplicate: { createFlow: true, renderLatency: Array(6).fill(1), durations: Array(6).fill(1) },
  style: { styleFlow: true, available: Array(6).fill(0), durations: Array(6).fill(1) },
  'export-pack': { needsExport: true, noCollection: true, missingHD: true, available: Array(6).fill(0), durations: Array(6).fill(1) },
};
const marked = (state, action) => action === 'submit' ? state.submitting : action === 'duplicate' ? !!state.duplicateRequested
  : action === 'style' ? state.styleRequested[0] : state.collectionSetupRequested;
const status = { submit: 'détection des accroches', duplicate: 'préparation de la variante 1/', style: 'sous-titres natifs, variante 1/', 'export-pack': 'préparation des exports HD manquants' };
function resumedSuccessfully(run, action) {
  if (action === 'submit') {
    // Stop the fixture at the next read: the import response and its durable
    // association are confirmed without inventing an unrelated source analysis.
    assert.equal(run.checkpoint.projectId, 'existing-project');
    assert.equal(run.checkpoint.submitting, false);
  } else {
    assert(!run.error, action + ': ' + run.error?.message); assert.equal(run.result.variants.length, 6);
  }
}

(async () => {
  let checks = 0;
  for (const [action, config] of Object.entries(configs)) {
    const firstBridge = bridge(action, 'pre');
    const first = await scenario(latestSource, { ...config, transport: firstBridge.transport });
    assert(first.error, action); assert(!marked(first.checkpoint, action), action + ': rejected operation is resumable');
    const rejected = firstBridge.replies.find(reply => reply.action === action);
    assert(rejected, action + ': expected target failure, got ' + first.error?.message);
    assert.equal(rejected.status, 503); assert.equal(rejected.calls, 0);
    assert.equal(rejected.body.definitelyRejected, true); assert.equal(rejected.body.upstreamNotCalled, true);
    const retryBridge = bridge(action);
    const retry = await scenario(latestSource, { ...config, checkpoint: first.checkpoint, transport: retryBridge.transport });
    resumedSuccessfully(retry, action);
    const targetCalls = retryBridge.calls.filter(call => call.action === action);
    assert.equal(firstBridge.calls.filter(call => call.action === action).length, 0);
    assert.equal(targetCalls.length, ['duplicate', 'style'].includes(action) ? 6 : 1);
    if (action === 'style') assert.equal(new Set(targetCalls.map(call => call.index)).size, 6);
    checks += 10;

    const waitingBridge = bridge(action);
    const stopped = await scenario(latestSource, { ...config, transport: waitingBridge.transport,
      waitForQuota: true, abortOnStatus: status[action] });
    assert(stopped.error, action + ': stopped'); assert(!marked(stopped.checkpoint, action));
    assert.equal(stopped.abortReason.upstreamNotCalled, undefined, 'Shared AbortSignal reason is never relabelled');
    assert.equal(waitingBridge.calls.filter(call => call.action === action).length, 0, action + ': quota stop sends no mutation');
    const resumeBridge = bridge(action);
    const resumed = await scenario(latestSource, { ...config, checkpoint: stopped.checkpoint, transport: resumeBridge.transport });
    resumedSuccessfully(resumed, action);
    assert.equal(resumeBridge.calls.filter(call => call.action === action).length, ['duplicate', 'style'].includes(action) ? 6 : 1);
    checks += 6;
  }

  for (const action of ['submit', 'duplicate', 'export-pack']) {
    const firstBridge = bridge(action, 'post');
    const first = await scenario(latestSource, { ...configs[action], transport: firstBridge.transport });
    assert(first.error); assert(marked(first.checkpoint, action));
    const ambiguous = firstBridge.replies.find(reply => reply.action === action);
    assert.equal(ambiguous.status, 502); assert.equal(ambiguous.calls, 1);
    assert.equal(ambiguous.body.definitelyRejected, undefined); assert.equal(ambiguous.body.upstreamNotCalled, undefined);
    const retryBridge = bridge(action);
    const retry = await scenario(latestSource, { ...configs[action], checkpoint: first.checkpoint, transport: retryBridge.transport });
    assert(retry.error); assert.equal(retryBridge.calls.filter(call => call.action === action).length, 0);
    checks += 8;
  }
  const partialBridge = bridge('export-pack', 'partial429');
  const partial = await scenario(latestSource, { ...configs['export-pack'], collectionFailure: 429, transport: partialBridge.transport });
  assert(partial.error); assert.equal(partial.checkpoint.collectionSetupRequested, true);
  assert.equal(partialBridge.replies.find(reply => reply.action === 'export-pack').body.upstreamNotCalled, undefined);
  const retryBridge = bridge('export-pack');
  const retry = await scenario(latestSource, { ...configs['export-pack'], checkpoint: partial.checkpoint, transport: retryBridge.transport });
  assert(retry.error); assert.equal(retryBridge.calls.filter(call => call.action === 'export-pack').length, 0);
  checks += 5;
  const lostStyleBridge = bridge('style', 'lost');
  const lostStyle = await scenario(latestSource, { ...configs.style, transport: lostStyleBridge.transport });
  assert(lostStyle.error); assert.equal(lostStyle.checkpoint.styleRequested[0], true);
  assert.equal(lostStyleBridge.replies.find(reply => reply.action === 'style').body.upstreamNotCalled, undefined);
  const styleRetryBridge = bridge('style', 'unknownStyle');
  const styleRetry = await scenario(latestSource, { createFlow: true, checkpoint: lostStyle.checkpoint, transport: styleRetryBridge.transport });
  assert.match(styleRetry.error?.message, /confirmation du style/);
  assert.equal(styleRetryBridge.calls.filter(call => call.action === 'style').length, 0);
  checks += 9;
  console.log(JSON.stringify({ checks, offline: true, providerCalls: 0,
    verified: 'Sheets outage and quota abort before transfer resume all four mutations; post-transfer persistence failure and partial provider 429 retain uncertainty without replay.' }));
})().catch(error => { console.error(error); process.exitCode = 1; });
