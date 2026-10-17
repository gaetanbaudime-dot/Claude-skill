const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), ts = require(require.resolve('typescript',{paths:[require('node:path').join(__dirname,'../../app_clippers')]}));
const compiled = ts.transpileModule(fs.readFileSync('src/lib/downloads.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const mod = { exports: {} }, navigation = {}, requests = [], received = [];
const labels = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/lib/variant-labels.ts','utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, {module: labels, exports: labels.exports});
let clicks = 0, permitted = Infinity;
const payload = Uint8Array.from([1, 2, 3, 4]);
const context = { exports: mod.exports, module: mod, File, URL, Uint8Array, DOMException, AbortController,
  require: name => { assert.equal(name, './variant-labels'); return labels.exports; },
  setTimeout: callback => { callback(); },
  navigator: navigation,
  document: { body: { appendChild() {} }, createElement: () => ({ click() { if (clicks++ < permitted) received.push(this.href); }, remove() {} }) },
  fetch: async url => { requests.push(String(url)); return new Response(payload, { headers: { 'Content-Type': 'video/mp4' } }); },
};
vm.runInNewContext(compiled, context);
const { canShareFiles, prepareShareFiles, sharePreparedFiles, downloadVideos, createVideoFileCache, MAX_SHARE_BYTES } = mod.exports;
const variants = Array.from({ length: 6 }, (_, index) => ({ index, name: `version-${index+1}.mp4`, size: 4,
  url: `https://storage.test/media/gm-final/job/version-${index+1}.mp4`, downloadUrl: `https://storage.test/media/gm-final/job/version-${index+1}.mp4?download=1` }));
(async () => {
  assert.equal(canShareFiles(), false, 'Desktop without Web Share remains downloadable');
  await downloadVideos(variants); assert.equal(received.length, 6);
  assert(received.every(url => url.startsWith('blob:')), 'Downloads cannot cancel each other as cross-origin navigations');
  received.length = 0; clicks = 0; permitted = 1;
  assert.equal(await downloadVideos(variants), undefined, 'A browser silently blocking five downloads is never reported as saved');
  assert.equal(received.length, 1);
  let progress = [];
  const files = await prepareShareFiles(variants, new AbortController().signal, n => progress.push(n));
  assert.equal(files.length, 6); assert.deepEqual(progress, [1,2,3,4,5,6]);
  assert(requests.every(u => u.endsWith('?share=1')));
  for (const file of files) assert.deepEqual(Buffer.from(await file.arrayBuffer()), Buffer.from(payload), 'Sharing preserves MP4 bytes');
  assert.deepEqual(Array.from(files,file=>file.name), ['GM-Variante-1-Hook.mp4','GM-Variante-2-Verticale.mp4','GM-Variante-3-Bleue.mp4','GM-Variante-4-Hook.mp4','GM-Variante-5-Classique.mp4','GM-Variante-6-Mouvement.mp4']);
  const operation = new AbortController(), cache = createVideoFileCache(operation.signal);
  const beforeCache = requests.length;
  const [background, tapped] = await Promise.all([cache.prepare(variants), cache.prepare([variants[0]])]);
  assert.equal(requests.length-beforeCache,6,'A tap during prefetch reuses in-flight MP4 bytes');
  assert.equal(background[0],tapped[0]); assert.equal(cache.get(variants)[0],background[0]);
  await cache.prepare(variants); assert.equal(requests.length-beforeCache,6,'Repeated saves use the bounded cache');
  operation.abort(); assert.equal(cache.get(variants),null,'Unmount drops the phone file cache');
  await assert.rejects(prepareShareFiles([{...variants[0], size: MAX_SHARE_BYTES+1}], new AbortController().signal,()=>{}), /volumineux/);
  await assert.rejects(prepareShareFiles([{...variants[0], size: 3}], new AbortController().signal,()=>{}), /taille/);
  await assert.rejects(prepareShareFiles([{...variants[0], size: 5}], new AbortController().signal,()=>{}), /incomplète/);
  let invoked = false;
  navigation.canShare = ({files}) => files.every(f => f.type === 'video/mp4');
  navigation.share = () => { invoked = true; return Promise.resolve(); };
  const sharing = sharePreparedFiles(files);
  assert(invoked, 'Share is invoked synchronously within the fresh user gesture');
  assert.equal(await sharing, 'handed-off');
  navigation.share = () => Promise.reject(new DOMException('cancelled', 'AbortError'));
  assert.equal(await sharePreparedFiles(files), 'cancelled');
  navigation.share = () => Promise.reject(new DOMException('denied', 'NotAllowedError'));
  assert.equal(await sharePreparedFiles(files), 'unavailable');
  navigation.canShare = () => false;
  assert.equal(await sharePreparedFiles(files), 'unavailable');
  navigation.canShare = () => { throw new TypeError('unsupported'); };
  assert.equal(canShareFiles(files), false);
  console.log('Downloads passed: exact file bytes, six/blocked downloads, mobile preparation, fresh activation, cancellation, denied/unsupported share, memory and truncation bounds.');
})().catch(error => { console.error(error); process.exitCode = 1; });

