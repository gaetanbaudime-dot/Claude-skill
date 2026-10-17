const assert=require('node:assert/strict');
const {environment,file}=require('./native-checkpoint-reuse.cjs');
(async()=>{
  const e=environment(),a={apiBase:'/api/k/fixture-person-a/reels',storageScope:'a'.repeat(64)},b={apiBase:'/api/c/fixture-person-b/reels',storageScope:'b'.repeat(64)};
  let r=(await e.settle([e.tab(a)(file())]))[0];assert.equal(r.status,'fulfilled');
  const first=e.calls.length;
  r=(await e.settle([e.tab(a)(file('rename.mp4'))]))[0];assert.equal(r.status,'fulfilled');
  assert(e.calls.slice(first).every(c=>c.method==='HEAD'),'Same account resumes immutable finals without a native request');
  r=(await e.settle([e.tab(b)(file())]))[0];assert.equal(r.status,'fulfilled');
  assert.equal(e.calls.filter(c=>c.action==='submit').length,2,'Another account cannot reuse the first account browser job');
  assert.equal([...e.storage.keys()].filter(k=>k.startsWith('gm:native-job:v3:')).length,2);
  assert([...e.storage.keys()].every(k=>!k.includes('fixture-person')),'No raw personal token in checkpoint keys');
  assert(e.calls.filter(c=>c.path.startsWith('/api/')).every(c=>/^\/api\/[kc]\/fixture-person-[ab]\/reels\/(source|opus|finish)$/.test(c.requestPath)));
  assert(e.calls.every(c=>!JSON.stringify(c.body).includes('fixture-person')),'App identity never enters provider payloads');
  assert.throws(()=>e.tab({apiBase:'https://another.example/api',storageScope:'a'.repeat(64)}));
  assert.throws(()=>e.tab({apiBase:'/api/k/a/reels',storageScope:'raw-token'}));
  console.log('Transport passed: same-origin private app paths, separate browser contexts, unchanged immutable files, no token forwarding.');
})().catch(e=>{console.error(e);process.exitCode=1});
