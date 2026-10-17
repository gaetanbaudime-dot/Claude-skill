// Offline scheduler verification. Every network operation is replaced; no
// video uploads, OpusClip mutations, vendor requests or storage writes occur.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const ts = require(require.resolve('typescript',{paths:[require('node:path').join(__dirname,'../../app_clippers')]}));
const sourcePath = path.join(__dirname, '../src/lib/opus-native.ts');
const latestSource = fs.readFileSync(sourcePath, 'utf8');
const baselineArgument = process.argv.indexOf('--baseline');
const baselinePath = baselineArgument >= 0 ? process.argv[baselineArgument + 1] : undefined;
if (baselineArgument >= 0 && (!baselinePath || !fs.existsSync(baselinePath))) {
  throw new Error('Use --baseline PATH with an existing TypeScript browser source file.');
}
const RealDate = Date;
const BASE = 1791955000000;

async function scenario(source, settings = {}) {
  let now = BASE, timerId = 0, active = 0, maxActive = 0;
  const timers = new Map(), events = [], progress = [], status = [], delivered = [];
  const storage = new Map();
  const oldURL = i => `https://signed-ext.cdn.opus.pro/project/c.clip_${i}/HD?v=1`;
  const newURL = i => `https://signed-ext.cdn.opus.pro/project/c.clip_${i}/HD?v=2`;
  const preview = i => `https://signed-ext.cdn.opus.pro/project/c.clip_${i}/PREVIEW?v=2`;
  const finalURL = i => `https://storage.example.test/media/variants/job/version-${i + 1}.mp4`;
  const key = 'gm:native-job:v3:test';
  const initial = settings.checkpoint || {
    profileRevision: 'gm-native-clean-headline-20261014-v2',
    createdAt: now, uploadId: 'already-uploaded', projectId: 'existing-project',
    selected: Array.from({ length: 6 }, (_, i) => ({
      projectId: 'existing-project', clipId: `clip_${i}`, title: `Clip ${i}`,
      durationSec: 15, score: 90, previewUrl: preview(i), exportUrl: oldURL(i),
      pending: false, styleIndex: i, renderKnown: true,
    })), styled: Array(6).fill(true), styleRequested: Array(6).fill(true),
    oldPreview: Array.from({ length: 6 }, (_, i) => preview(i).replace('v=2', 'v=1')),
    oldExport: Array.from({ length: 6 }, (_, i) => oldURL(i)),
    seenPending: [], seenHD: [], polishResults: settings.cached
      ? Array.from({ length: 6 }, (_, i) => ({ url: finalURL(i), downloadUrl: finalURL(i) + '?download=1', size: 100 + i })) : [],
    collectionId: 'existing-collection', exported: !settings.needsExport,
    ...(settings.cachedZip ? { packResult: {
      urls: Array.from({ length: 6 }, (_, i) => finalURL(i)),
      zipUrl: 'https://storage.example.test/media/packs/job/six.zip', size: 900,
    } } : {}),
  };
  if (settings.styleFlow) { initial.styled = []; initial.styleRequested = []; }
  if (settings.createFlow && !settings.checkpoint) {
    initial.sourceClips = [{ ...initial.selected[0], clipId: 'original-source' }];
    initial.selected = []; initial.styled = []; initial.styleRequested = [];
    initial.oldPreview = []; initial.oldExport = [];
  }
  if (settings.selectedCount) initial.selected = initial.selected.slice(0, settings.selectedCount);
  if (settings.noCollection) delete initial.collectionId;
  if (settings.submitFlow && !settings.checkpoint) {
    delete initial.projectId;
    initial.sourceToken = 'fixture-source';
    initial.selected = []; initial.styled = []; initial.styleRequested = [];
    initial.oldPreview = []; initial.oldExport = [];
    delete initial.collectionId; delete initial.sourceClips;
  }
  if (settings.reorderedZip) initial.packResult.urls.reverse();
  storage.set(key, JSON.stringify(initial));
  if (settings.waitForQuota) storage.set('gm:opus-next-api-at', String(now + 60000));
  const localStorage = {
    getItem: k => storage.get(k) ?? null,
    setItem: (k, value) => storage.set(k, String(value)),
    get length() { return storage.size; },
    key: i => [...storage.keys()][i] ?? null,
  };
  class FakeDate extends RealDate {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  const setTimer = (fn, ms) => {
    const id = ++timerId;
    timers.set(id, { at: now + Math.max(0, ms || 0), fn });
    return id;
  };
  const clearTimer = id => timers.delete(id);
  const delay = ms => new Promise(resolve => setTimer(resolve, ms));
  let reads = 0;
  const available = settings.available || [0, 0, 20000, 30000, 30000, 45000];
  const durations = settings.durations || [60000, 5000, 30000, 20000, 7000, 5000];
  const providerCopies = [...initial.selected];
  const styledAt = new Map();
  if (settings.checkpoint && settings.createFlow) initial.styled.forEach((styled,i)=>{ if(styled) styledAt.set(i,0); });
  const fakeFetch = async (input, init = {}) => {
    const url = new URL(String(input), 'https://app.example.test');
    const method = init.method || 'GET';
    const at = now - BASE;
    if (url.pathname === '/api/opus') {
      if (method === 'POST') {
        const body = JSON.parse(String(init.body));
        if (body.action === 'submit' && settings.submitFlow) {
          events.push({ action: 'submit', at });
          return Response.json({ projectId: 'existing-project' });
        }
        if (body.action === 'style' && (settings.styleFlow || settings.createFlow)) {
          events.push({ action:'style', index:body.index, at });
          assert.notEqual(body.clipId, 'original-source', 'Never edit the original source');
          if (settings.styleFailure === body.index) throw new TypeError('Lost style response');
          styledAt.set(body.index, at);
          return new Response('{}',{status:200,headers:{'X-GM-Upstream-Calls':'1','X-GM-Api-Wait-Ms':'2050'}});
        }
        if (body.action === 'duplicate' && settings.duplicateFailure &&
            (settings.failCopyIndex === undefined || settings.failCopyIndex === providerCopies.length)) {
          events.push({ action: 'duplicate', at });
          if (settings.duplicateFailure === 'network') throw new TypeError('Lost response');
          return new Response(JSON.stringify({ error: 'simulated duplicate failure',
            definitelyRejected: settings.duplicateFailure === 429 }), { status: settings.duplicateFailure });
        }
        if (body.action === 'duplicate' && settings.createFlow) {
          const index = providerCopies.length;
          events.push({ action: 'duplicate', index, at });
          assert.equal(body.clipId, initial.sourceClips?.[0]?.clipId || initial.selected[0].clipId);
          if (body.sourceEditTicket) assert.equal(body.sourceEditTicket, 'signed-original-snapshot');
          const calls = body.sourceEditTicket ? 1 : 2;
          await delay((calls - 1) * 2050);
          const copy = { projectId: 'existing-project', clipId: `clip_${index}`, title: `Copy ${index}`,
            durationSec: 15, score: 90, previewUrl: preview(index).replace('v=2','v=1'), exportUrl: oldURL(index),
            pending: false, renderKnown: true, editTicket: `signed-copy-${index}`, sourceEditTicket: 'signed-original-snapshot' };
          providerCopies.push(copy);
          return new Response(JSON.stringify(copy), {status:200,headers:{'X-GM-Upstream-Calls':String(calls),'X-GM-Api-Wait-Ms':'2050'}});
        }
        assert.equal(body.action, 'export-pack', 'Imports and native edits are forbidden in this test');
        assert.equal(body.clipIds.length, 6);
        events.push({ action: 'export-pack', at });
        await delay(100);
        if (settings.collectionFailure) return new Response(JSON.stringify({
          error: 'simulated failure after collection creation',
          definitelyRejected: settings.collectionFailure === 429,
        }), { status: settings.collectionFailure });
        return new Response('{"collectionId":"existing-collection"}', { status: 200,
          headers: { 'X-GM-Upstream-Calls': '8', 'X-GM-Api-Next-At': String(now + 2300) } });
      }
      assert.equal(method, 'GET');
      if (url.searchParams.get('action') === 'recover' && settings.submitFlow) {
        events.push({ action: 'recover', at });
        return Response.json({ projectId: null });
      }
      if (settings.submitFlow) throw new Error('Submit fixture ends after the project is recorded');
      assert.equal(url.searchParams.get('action'), 'clips');
      const requested = (url.searchParams.get('clipIds') || '').split(',').filter(Boolean);
      const target = url.searchParams.get('target') || (reads === 0 ? 'preview' : 'hd');
      events.push({ action: 'poll', at, target, requested });
      reads++;
      await delay(100);
      const clips = providerCopies.map((clip, i) => {
        const readyAt = settings.createFlow ? (styledAt.get(i) ?? Infinity) + (settings.renderLatency?.[i] ?? 15000) : available[i];
        const hdReady = now - BASE >= readyAt && !(settings.missingHD && !events.some(e => e.action === 'export-pack'));
        return { ...clip, previewUrl: preview(i), previewRevision: preview(i),
          exportUrl: target === 'preview' || hdReady ? newURL(i) : null,
          exportRevision: target === 'preview' || hdReady ? newURL(i) : oldURL(i),
          exportKnown: !(settings.unknownHD === i), exportPending: !hdReady && !settings.missingHD,
          pending: target === 'hd' && !hdReady && !settings.missingHD,
          editorial: { headlineCount: settings.wrongHeadline === i ? 7 : i === 0 || i === 3 ? 1 : 0, headlineTop: true, remainingPauses: settings.remainingPause === i ? 1 : 0 },
          styleIndex: target === 'hd' && settings.wrongStyle === i ? 5 - i : i,
          ...(target === 'hd' && settings.signingOnly === i ? {
            exportUrl: oldURL(i) + '&Signature=changed', exportRevision: oldURL(i),
          } : {}),
        };
      });
      const headers = settings.noMeter ? {} : {
        'X-GM-Upstream-Calls': String(settings.actualCalls ?? (settings.createFlow ? 1 + requested.filter(id => {
          const i = providerCopies.findIndex(c => c.clipId === id);
          return now - BASE >= (styledAt.get(i) ?? Infinity) + (settings.renderLatency?.[i] ?? 15000);
        }).length : 1)),
        'X-GM-Api-Next-At': String(now + 2300), Date: new FakeDate(now).toUTCString(),
      };
      return new Response(JSON.stringify({ clips }), { status: 200, headers });
    }
    if (url.pathname === '/api/finish') {
      const body = JSON.parse(String(init.body));
      if (body.action === 'health') return new Response('{"ready":true}', { status: 200 });
      const i = body.index;
      assert.equal(body.url, newURL(i), 'Only this target\'s fresh HD output can be finished');
      assert.equal(progress.includes(100), false, '100% must wait for all six completed MP4s');
      active++; maxActive = Math.max(maxActive, active);
      events.push({ action: 'finish-start', index: i, at });
      await delay(durations[i]);
      active--;
      events.push({ action: 'finish-end', index: i, at: now - BASE });
      if (settings.fail === i) return new Response('{"error":"simulated failure"}', { status: 502 });
      return new Response(JSON.stringify({ url: finalURL(i), downloadUrl: finalURL(i) + '?download=1', size: 100 + i }), { status: 200 });
    }
    if (method === 'HEAD' && url.origin === 'https://storage.example.test') {
      const isZip = url.pathname.endsWith('.zip');
      events.push({ action: isZip ? 'zip-head' : 'cached-head', at });
      return new Response(null, { status: isZip && settings.missingZip ? 404 : 200,
        headers: { 'Content-Length': isZip ? String(settings.badZipSize ? 899 : 900) : String(99 + Number(url.pathname.match(/version-(\d+)/)?.[1])),
          'Content-Type': isZip ? settings.badZipType ? 'text/html' : 'application/zip' : 'video/mp4' } });
    }
    if (url.pathname === '/api/pack') {
      const body = JSON.parse(String(init.body));
      assert.equal(body.urls.length, 6);
      assert.equal(new Set(body.urls).size, 6);
      assert.equal(active, 0, 'ZIP starts only after all six finishes settle');
      assert.equal(progress.includes(100), false);
      events.push({ action: 'pack', at });
      await delay(1000);
      return new Response('{"zipUrl":"https://storage.example.test/media/packs/job/six.zip","size":900}', { status: 200 });
    }
    throw new Error('Unexpected/offline-forbidden network request: ' + method + ' ' + url.pathname);
  };
  const locks = new Map();
  const navigator = { locks: { request(name, options, callback) {
    const run = callback || options;
    const previous = locks.get(name) || Promise.resolve();
    const work = previous.catch(() => {}).then(run);
    locks.set(name, work);
    return work;
  } } };
  const sandbox = {
    module: { exports: {} }, exports: {}, require,
    window: { localStorage }, navigator,
    Date: FakeDate, performance: { now: () => now - BASE },
    setTimeout: setTimer, clearTimeout: clearTimer,
    fetch: settings.transport ? settings.transport(fakeFetch, initial) : fakeFetch, URL, URLSearchParams, Response, Headers,
    AbortController, AbortSignal, DOMException, console,
  };
  sandbox.exports = sandbox.module.exports;
  vm.createContext(sandbox);
  const compiled = ts.transpileModule(source.replace('return { generateOpusVariations };', 'return { generateOpusVariations, generate };'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInContext(compiled + '\nexports.testGenerate = createNativeClient().generate;', sandbox);
  let result, error, done = false;
  const controller = new AbortController();
  sandbox.module.exports.testGenerate({ name: 'offline-test.mp4' }, {
    signal: controller.signal,
    onProgress: value => progress.push(value), onStatus: value => {
      status.push(value);
      if (settings.abortOnStatus && value.includes(settings.abortOnStatus)) setTimer(() => controller.abort(), 1);
    },
    onVariant: value => delivered.push({ index: value.index, at: now - BASE }),
  }, key).then(value => { result = value; done = true; }, value => { error = value; done = true; });
  for (let iteration = 0; !done && iteration < 3000; iteration++) {
    await new Promise(resolve => setImmediate(resolve));
    if (done) break;
    assert(timers.size > 0, 'Pending workflow has a scheduled timer');
    const nextAt = Math.min(...[...timers.values()].map(timer => timer.at));
    now = nextAt;
    for (const [id, timer] of [...timers]) if (timer.at === nextAt) { timers.delete(id); timer.fn(); }
  }
  assert(done, 'Workflow completed or surfaced its expected error');
  return { result, error, events, progress, status, delivered, maxActive, elapsed: now - BASE,
    checkpoint: JSON.parse(storage.get(key)), reservation: Number(storage.get('gm:opus-next-api-at')) - BASE,
    abortReason: controller.signal.reason };
}

module.exports = { scenario, latestSource };
if (require.main === module) (async () => {
  let checks = 0;
  const current = await scenario(latestSource);
  assert(!current.error); checks++;
  assert.equal(current.result.variants.length, 6); checks++;
  assert.equal(current.maxActive, 2); checks++;
  const started = i => current.events.find(e => e.action === 'finish-start' && e.index === i).at;
  const ended = i => current.events.find(e => e.action === 'finish-end' && e.index === i).at;
  assert(started(0) < 45000, 'First HD finishes before last native HD becomes available'); checks++;
  assert(started(2) < ended(0), 'Second slot refills before its slow original peer finishes'); checks++;
  assert(current.events.some(e => e.action === 'poll' && e.target === 'hd' && e.requested.length < 6)); checks++;
  for (let i = 0; i < 6; i++) {
    assert(started(i) >= [0, 0, 20000, 30000, 30000, 45000][i]); checks++;
    const laterPolls = current.events.filter(e => e.action === 'poll' && e.target === 'hd' && e.at > started(i));
    assert(laterPolls.every(e => !e.requested.includes(`clip_${i}`))); checks++;
  }
  assert.equal(current.progress.at(-1), 100); checks++;
  assert.equal(current.delivered.length, 6); checks++;
  assert(current.delivered.some(v => v.at < Math.max(...current.delivered.map(v => v.at))), 'Each MP4 is published before the slowest sibling finishes'); checks++;
  assert.equal(current.result.zipUrl, undefined, 'No ZIP is returned'); checks++;
  assert.equal(current.events.filter(e => e.action === 'pack').length, 0, 'No ZIP request blocks MP4 delivery'); checks++;
  assert(current.checkpoint.polishResults.every(Boolean)); checks++;

  const nativeHD = await scenario(latestSource, { needsExport: true, available: Array(6).fill(0) });
  assert(!nativeHD.error); checks++;
  assert.equal(nativeHD.events.some(e => e.action === 'export-pack'), false, 'Already verified fresh native HD does not request another export'); checks++;
  assert.equal(nativeHD.result.variants.length, 6); checks++;
  const pendingHD = await scenario(latestSource, { needsExport: true });
  assert(!pendingHD.error); checks++;
  assert.equal(pendingHD.events.filter(e => e.action === 'export-pack').length, 0, 'In-flight native HD is awaited without another render'); checks++;

  for (const duplicateFailure of ['network', 502]) {
    const interrupted = await scenario(latestSource, { selectedCount: 5, duplicateFailure });
    assert(interrupted.error); checks++;
    assert.equal(interrupted.checkpoint.duplicateRequested.version, 6); checks++;
    const retry = await scenario(latestSource, { checkpoint: interrupted.checkpoint, duplicateFailure });
    assert.match(retry.error.message, /Aucun doublon/); checks++;
    assert.equal(retry.events.filter(e => e.action === 'duplicate').length, 0, 'Lost duplicate reply must not create a second copy after reload'); checks++;
  }
  const refusedCopy = await scenario(latestSource, { selectedCount: 5, duplicateFailure: 429 });
  assert.equal(refusedCopy.checkpoint.duplicateRequested, undefined, 'A definitely refused single duplicate can be retried'); checks++;
  for (const collectionFailure of [502, 429]) {
    const interrupted = await scenario(latestSource, { needsExport: true, noCollection: true, collectionFailure, missingHD: true });
    assert(interrupted.error); checks++;
    assert.equal(interrupted.checkpoint.collectionSetupRequested, true); checks++;
    const retry = await scenario(latestSource, { checkpoint: interrupted.checkpoint, collectionFailure, missingHD: true });
    assert.match(retry.error.message, /Aucun groupe supplémentaire/); checks++;
    assert.equal(retry.events.filter(e => e.action === 'export-pack').length, 0, 'Partial collection setup must not create another collection, even when a later step was rejected'); checks++;
  }
  const unknownHD = await scenario(latestSource, { needsExport: true, unknownHD: 2, available: Array(6).fill(0), durations: Array(6).fill(1000) });
  assert(unknownHD.error); checks++;
  assert.equal(unknownHD.events.some(e => e.action === 'finish-start' && e.index === 2), false, 'Unknown HD render status cannot be finished'); checks++;
  assert.equal(unknownHD.events.filter(e => e.action === 'export-pack').length, 1); checks++;

  const failed = await scenario(latestSource, { available: Array(6).fill(0), durations: [10000, 4000, 8000, 8000, 8000, 8000], fail: 1 });
  assert(failed.error); checks++;
  assert.equal(failed.events.filter(e => e.action === 'finish-start').length, 2); checks++;
  assert.equal(failed.events.filter(e => e.action === 'finish-end').length, 2); checks++;
  assert.equal(failed.events.some(e => e.action === 'pack'), false); checks++;
  assert.equal(failed.progress.includes(100), false); checks++;
  assert.equal(failed.checkpoint.polishResults.filter(Boolean).length, 1); checks++;

  const cached = await scenario(latestSource, { available: Array(6).fill(0), cached: true });
  assert(!cached.error); checks++;
  assert.equal(cached.events.filter(e => e.action === 'finish-start').length, 0); checks++;
  assert.equal(cached.events.filter(e => e.action === 'cached-head').length, 6); checks++;
  assert.equal(cached.events.some(e => e.action === "pack"), false); checks++;

  const cachedZip = await scenario(latestSource, { available: Array(6).fill(0), cached: true, cachedZip: true });
  assert(!cachedZip.error); checks++;
  assert.equal(cachedZip.events.filter(e => e.action === 'pack').length, 0); checks++;
  assert.equal(cachedZip.events.filter(e => e.action === 'zip-head').length, 0, 'Legacy ZIP checkpoints are ignored'); checks++;
  assert.equal(cachedZip.progress.at(-1), 100); checks++;
  for (const mismatch of [{ badZipSize: true }, { badZipType: true }, { missingZip: true }, { reorderedZip: true }]) {
    const regeneratedZip = await scenario(latestSource, { available: Array(6).fill(0), cached: true, cachedZip: true, ...mismatch });
    assert(!regeneratedZip.error); checks++;
    assert.equal(regeneratedZip.events.filter(e => e.action === 'pack').length, 0); checks++;
    assert.equal(regeneratedZip.checkpoint.packResult.size, 900); checks++;
  }

  for (const rejection of [{ signingOnly: 2 }, { wrongStyle: 2 }, { wrongHeadline: 2 }, { remainingPause: 2 }]) {
    const stale = await scenario(latestSource, { available: Array(6).fill(0), durations: Array(6).fill(1000), ...rejection });
    assert(stale.error); checks++;
    assert.equal(stale.events.some(e => e.action === 'finish-start' && e.index === 2), false); checks++;
    assert.equal(stale.events.some(e => e.action === 'pack'), false); checks++;
    assert.equal(stale.progress.includes(100), false); checks++;
  }

  const fallback = await scenario(latestSource, { noMeter: true, durations: Array(6).fill(1000) });
  const polls = fallback.events.filter(e => e.action === 'poll');
  assert(polls[1].at - polls[0].at >= 7 * 2100, 'Absent server metadata keeps conservative seven-call reservation'); checks++;
  const measuredPolls = current.events.filter(e => e.action === 'poll');
  assert(measuredPolls[1].at - measuredPolls[0].at < 7 * 2100, 'Measured one-call list releases six unused slots'); checks++;
  assert(measuredPolls.every((e, i) => i === 0 || e.at - measuredPolls[i - 1].at >= 2100)); checks++;

  const overlapping = await scenario(latestSource, { styleFlow:true, available:Array(6).fill(0), durations:Array(6).fill(10000) });
  assert(!overlapping.error, overlapping.error); checks++;
  assert(overlapping.events.find(e=>e.action==='finish-start').at < overlapping.events.find(e=>e.action==='style'&&e.index===5).at, 'Finish an early fresh HD before the last native style dispatch'); checks++;
  assert.equal(overlapping.events.filter(e=>e.action==='finish-start').length,6,'No duplicate finishing across early and final polling'); checks++;

  const interleaved = await scenario(latestSource, {createFlow:true,durations:Array(6).fill(8000)});
  assert(!interleaved.error, interleaved.error); checks++;
  assert.equal(interleaved.result.variants.length,6); checks++;
  assert.equal(interleaved.events.filter(e=>e.action==='duplicate').length,6); checks++;
  assert.equal(interleaved.events.filter(e=>e.action==='style').length,6); checks++;
  for (let i=0;i<5;i++) {
    assert(interleaved.events.find(e=>e.action==='style'&&e.index===i).at <
      interleaved.events.find(e=>e.action==='duplicate'&&e.index===i+1).at,
      'Start each native render before preparing the next copy'); checks++;
  }
  const apiEvents = interleaved.events.filter(e=>['duplicate','style','poll'].includes(e.action));
  assert(apiEvents.every((e,i)=>i===0||e.at-apiEvents[i-1].at>=2100),'Interleaving retains the API pacing'); checks++;
  assert.equal(interleaved.maxActive,2); checks++;
  const refusedMidway=await scenario(latestSource,{createFlow:true,duplicateFailure:429,failCopyIndex:3});
  assert(refusedMidway.error); checks++;
  assert.equal(refusedMidway.checkpoint.duplicateRequested,undefined); checks++;
  const resumedMidway=await scenario(latestSource,{createFlow:true,checkpoint:refusedMidway.checkpoint,durations:Array(6).fill(1000)});
  assert(!resumedMidway.error,resumedMidway.error); checks++;
  assert.equal(resumedMidway.result.variants.length,6); checks++;
  assert.equal(resumedMidway.events.filter(e=>e.action==='duplicate').length,3,'Resume only missing copies'); checks++;
  assert.equal(resumedMidway.events.filter(e=>e.action==='style').length,3,'Do not restyle confirmed earlier copies'); checks++;
  const legacyCheckpoint=JSON.parse(JSON.stringify(refusedMidway.checkpoint));
  delete legacyCheckpoint.sourceClips;
  const legacyResume=await scenario(latestSource,{createFlow:true,styleFlow:true,checkpoint:legacyCheckpoint,durations:Array(6).fill(1000)});
  assert(!legacyResume.error,legacyResume.error); checks++;
  assert.equal(legacyResume.result.variants.length,6); checks++;
  assert(legacyResume.events.filter(e=>e.action==='duplicate').every(e=>e.at<legacyResume.events.find(e=>e.action==='style').at),
    'Legacy copies must be prepared before editing their shared source'); checks++;
  for (const failure of [{duplicateFailure:'network',failCopyIndex:4},{styleFailure:4}]) {
    const interrupted=await scenario(latestSource,{createFlow:true,durations:Array(6).fill(1000),renderLatency:Array(6).fill(0),...failure});
    assert(interrupted.error); checks++;
    assert.equal(interrupted.progress.includes(100),false); checks++;
    assert.equal(interrupted.events.filter(e=>e.action==='finish-start').length,
      interrupted.events.filter(e=>e.action==='finish-end').length,'Settle early finishes before reporting a later mutation failure'); checks++;
    if (failure.duplicateFailure) {
      const retry=await scenario(latestSource,{createFlow:true,checkpoint:interrupted.checkpoint,...failure});
      assert.match(retry.error.message,/Aucun doublon/); checks++;
      assert.equal(retry.events.filter(e=>['style','duplicate','finish-start'].includes(e.action)).length,0,'An uncertain copy blocks all new mutations on resume'); checks++;
    } else {
      assert.equal(interrupted.checkpoint.styleRequested[4],true,'Persist the uncertain style intent'); checks++;
      assert.equal(interrupted.checkpoint.selected.length,5,'Do not prepare later copies after a lost style reply'); checks++;
    }
  }

  let baseline;
  if (baselinePath) baseline = await scenario(fs.readFileSync(baselinePath, 'utf8'));
  const renderComparisons=[];
  if (baselinePath) for (const renderMs of [5000,15000,30000]) {
    const settings={createFlow:true,renderLatency:Array(6).fill(renderMs),durations:Array(6).fill(8000)};
    const before=await scenario(fs.readFileSync(baselinePath,'utf8'),settings);
    const after=await scenario(latestSource,settings);
    assert(!before.error,before.error); assert(!after.error,after.error); checks+=2;
    const first=(s,a)=>s.events.find(e=>e.action===a).at;
    renderComparisons.push({renderMs,beforeMs:before.elapsed,afterMs:after.elapsed,savingMs:before.elapsed-after.elapsed,
      firstStyleEarlierMs:first(before,'style')-first(after,'style'),
      firstFinishEarlierMs:first(before,'finish-start')-first(after,'finish-start')});
  }
  const checkpointReuseChecks = await require('./native-checkpoint-reuse.cjs')();
  const processingStatusChecks = require('./processing-status.cjs')();
  const summary = {
    checkpointReuseChecks, processingStatusChecks,
    offline: true, checks, maxConcurrentFinishes: current.maxActive,
    simulatedScenario: { freshHDReadyMs: [0, 0, 20000, 30000, 30000, 45000], finishingMs: [60000, 5000, 30000, 20000, 7000, 5000] },
    simulatedBeforeMs: baseline?.elapsed, simulatedAfterMs: current.elapsed,
    simulatedSavingMs: baseline ? baseline.elapsed - current.elapsed : undefined,
    firstFinishStartsMs: started(0), secondSlotRefillsMs: started(2),
    interleavedRenderComparisons:renderComparisons,
    nativeCallsUnchanged: 'No vendor requests occurred; clips, finish and pack were mocked.',
    limitation: 'Measures host orchestration only, not real upload/OpusClip render speed or encode throughput.',
  };
  console.log(JSON.stringify(summary, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
