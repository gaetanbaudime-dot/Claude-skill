// Local binary/file fixtures only: no upload, render, provider or storage calls.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { webcrypto, createHash } = require('node:crypto');
const appRequire = require('node:module').createRequire(path.resolve(__dirname, '../../app_clippers/package.json'));
const ts = appRequire('typescript');
const input = fs.readFileSync(path.resolve(__dirname, '../src/lib/opus-native.ts'), 'utf8')
  .replace('return { generateOpusVariations };', 'return { generateOpusVariations, checkpointKey, gcsUpload, uploadPreparedSource };');
const compiled = ts.transpileModule(input, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const prefix = 'gm:native-job:v3:';
function environment({ network, xhrScenario, onYield } = {}) {
  let now = 0, yields = 0;
  const xhrs = [], module = { exports: {} };
  class XHR {
    constructor() { this.upload = {}; this.headers = {}; xhrs.push(this); }
    open(method, target) { this.method = method; this.target = target; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send(file) { this.sent = file; xhrScenario?.(this, file, value => { now = value; }); }
    abort() { this.onabort?.(); this.onloadend?.(); }
  }
  const timeout = (fn, ms) => setTimeout(() => { if (ms === 0) { yields++; onYield?.(); } fn(); }, ms);
  vm.runInNewContext(compiled, { module, exports: module.exports, require: appRequire, XMLHttpRequest: XHR,
    crypto: webcrypto, performance: { now: () => now }, Uint8Array, ArrayBuffer,
    URL, URLSearchParams, AbortController, AbortSignal, DOMException, setTimeout: timeout, clearTimeout,
    window: { localStorage: { length: 0, key: () => null, getItem: () => null, setItem() {} } },
    navigator: { locks: { request: (_key, options, callback) => (callback || options)() } }, fetch: network,
  });
  return { ...module.exports.createNativeClient(), xhrs, get yields() { return yields; } };
}
async function main() {
  let checks = 0;
  for (const size of [0, 31, 1024 * 1024 + 17, 8 * 1024 * 1024, 8 * 1024 * 1024 + 1, 17 * 1024 * 1024 + 127]) {
    const bytes = new Uint8Array(size);
    for (let i = 0; i < size; i++) bytes[i] = i % 251;
    const file = new File([bytes], 'unchanged.mov', { type: 'video/quicktime' });
    const originalSlice = file.slice.bind(file), originalBuffer = file.arrayBuffer.bind(file);
    let wholeReads = 0; const slices = [];
    file.arrayBuffer = async () => { wholeReads++; return originalBuffer(); };
    file.slice = (start, end) => { const part = originalSlice(start, end); slices.push(part.size); return part; };
    const e = environment();
    const actual = await e.checkpointKey(file);
    const expected = Buffer.from(await webcrypto.subtle.digest('SHA-256', bytes)).toString('hex');
    assert.equal(actual, prefix + expected, 'Old and bounded hash have the identical full-content checkpoint identity'); checks++;
    if (size > 8 * 1024 * 1024) {
      assert.equal(wholeReads, 0, 'A large rush is never read as one ArrayBuffer'); checks++;
      assert(Math.max(...slices) <= 1024 * 1024); checks++;
      assert.equal(slices.reduce((a, b) => a + b, 0), size, 'Every original byte is hashed once'); checks++;
      assert(e.yields >= Math.floor(size / (4 * 1024 * 1024)), 'UI gets a turn between bounded batches'); checks++;
    }
  }
  // Represent the maximum supported rush without allocating a 250 MiB test
  // buffer. Both engines consume exactly the same 250 original chunks.
  const maximum = 250 * 1024 * 1024, piece = new Uint8Array(1024 * 1024).fill(90);
  const expectedMaximum = createHash('sha256');
  for (let i = 0; i < 250; i++) expectedMaximum.update(piece);
  let maximumRead = 0, totalRead = 0;
  const large = { size: maximum, arrayBuffer: () => { throw new Error('Whole-file read forbidden'); },
    slice(start, end) { const size = Math.min(end, maximum) - start; maximumRead = Math.max(maximumRead, size); totalRead += size;
      return { arrayBuffer: async () => piece.slice(0, size).buffer }; } };
  assert.equal(await environment().checkpointKey(large), prefix + expectedMaximum.digest('hex')); checks++;
  assert.equal(maximumRead, 1024 * 1024); checks++;
  assert.equal(totalRead, maximum); checks++;
  const cancelled = new AbortController();
  const e = environment({ onYield: () => cancelled.abort() });
  await assert.rejects(e.checkpointKey(new File([new Uint8Array(16 * 1024 * 1024)], 'abort.mp4'), cancelled.signal), { name: 'AbortError' }); checks++;
  const raw = new File([new Uint8Array(1000)], 'raw.mov', { type: 'video/quicktime' });
  const uploaded = environment({ xhrScenario(xhr, file, clock) {
    assert.equal(file, raw, 'Upload sends the original File without encoding or compression'); checks++;
    clock(1000); xhr.upload.onprogress({ lengthComputable: true, loaded: 500, total: 1000 });
    clock(2000); xhr.status = 200; xhr.onload(); xhr.onloadend();
  } });
  const reports = [], progress = [];
  await uploaded.gcsUpload(raw, 'https://storage.example.test/raw-upload/fixture/raw.mov', {
    onUploadProgress: value => reports.push(value), onProgress: value => progress.push(value),
  });
  assert.deepEqual(reports.map(r => r.loaded), [0, 500, 1000]); checks++;
  assert(reports.every(r => r.total === 1000)); checks++;
  assert.equal(reports[1].bytesPerSecond, 500); checks++;
  assert.equal(reports[2].elapsedSeconds, 2); checks++;
  assert.deepEqual(progress, [5, 15, 25]); checks++;
  assert.equal(uploaded.xhrs[0].timeout, 10 * 60 * 1000); checks++;
  for (const event of ['onerror', 'ontimeout']) {
    const failed = environment({ xhrScenario(xhr) { xhr[event](); xhr.onloadend(); } });
    await assert.rejects(failed.gcsUpload(raw, 'https://storage.example.test/raw-upload/fixture/raw.mov', {})); checks++;
    assert.equal(failed.xhrs.length, 1, 'Ambiguous upload is never automatically replayed'); checks++;
  }
  const stopped = new AbortController();
  const aborting = environment({ xhrScenario() { stopped.abort(); } });
  await assert.rejects(aborting.gcsUpload(raw, 'https://storage.example.test/raw-upload/fixture/raw.mov', { signal: stopped.signal }), { name: 'AbortError' }); checks++;
  for (const confirmed of [true, false]) {
    const calls = []; let targetReads = 0;
    const recovery = environment({
      network: async (_url, init) => {
        const body = JSON.parse(init.body); calls.push(body.action);
        if (body.action === 'create') return Response.json({ sourceToken: 'fixture-source' });
        if (body.action === 'target') return Response.json({ uploaded: ++targetReads > 1 && confirmed,
          uploadUrl: 'https://storage.example.test/raw-upload/fixture/raw.mov' });
        if (body.action === 'prepare') return Response.json({ ready: true, uploadId: 'gm-source:fixture', mirroredBeforeCaptions: true });
        throw new Error('Forbidden fixture action ' + body.action);
      },
      xhrScenario(xhr) { xhr.onerror(); xhr.onloadend(); },
    });
    const state = {};
    if (confirmed) {
      assert.equal(await recovery.uploadPreparedSource(raw, state, () => {}, {}), 'gm-source:fixture'); checks++;
      assert.equal(state.mirroredBeforeCaptions, true); checks++;
      assert.equal(calls.at(-1), 'prepare'); checks++;
    } else {
      await assert.rejects(recovery.uploadPreparedSource(raw, state, () => {}, {})); checks++;
      assert(!calls.includes('prepare')); checks++;
    }
    assert.equal(recovery.xhrs.length, 1, 'Only the original upload is attempted'); checks++;
    assert.equal(targetReads, 2, 'A lost reply is reconciled with a read-only exact-size target check'); checks++;
    assert(!calls.includes('submit'), 'Recovery cannot launch paid work'); checks++;
  }
  for (const ready of [true, false]) {
    const events = [];
    let resolveHash, resolveHealth;
    const hashGate = new Promise(resolve => { resolveHash = resolve; });
    const healthGate = new Promise(resolve => { resolveHealth = resolve; });
    const firstUse = environment({ network: async (_url, init) => {
      const body = JSON.parse(init.body);
      if (body.action === 'health') {
        events.push('health-start'); await healthGate; events.push('health-end');
        return Response.json({ ready });
      }
      events.push(body.action);
      throw new Error('Fixture stops before actual upload or paid work');
    } });
    const source = { name: 'first-use.mp4', size: 4, arrayBuffer: async () => {
      events.push('hash-start'); await hashGate; events.push('hash-end'); return Uint8Array.from([1, 2, 3, 4]).buffer;
    } };
    const work = firstUse.generateOpusVariations(source);
    assert.deepEqual(events, ['health-start', 'hash-start'], 'Read-only preflight and fingerprint run concurrently on first use'); checks++;
    resolveHash();
    await new Promise(resolve => setImmediate(resolve));
    assert(!events.includes('create'), 'No source mutation may precede a confirmed storage preflight'); checks++;
    resolveHealth(); await assert.rejects(work); checks++;
    assert.equal(events.includes('create'), ready, 'Storage refusal blocks every upload/create operation'); checks++;
    if (ready) { assert(events.indexOf('create') > events.indexOf('health-end')); checks++; }
    assert(!events.includes('submit')); checks++;
  }
  console.log(JSON.stringify({ checks, maxHashReadBytes: 1024 * 1024, fullSha256Identity: true, uploadBytesUnchanged: true,
    realUploadProgress: true, uploadReplay: false, lostReplyReconciled: true, offline: true }));
}
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
module.exports = main;
