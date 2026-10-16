const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.join(__dirname,'../../app_clippers/package.json')),ts=appRequire('typescript');
function load(filename,dependencies={},extra={}){
  const module={exports:{}};
  const source=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  vm.runInNewContext(source,{module,exports:module.exports,require:n=>dependencies[n],Request,Response,Headers,URL,AbortController,AbortSignal,Uint8Array,TextDecoder,...extra});
  return module.exports;
}
(async()=>{
  const calls=[];
  let fail=false,html=false;
  const proxy=load(path.join(__dirname,'../src/server/proxy.ts'),{'./ownership':{authorize:async()=>async()=>{},OwnershipDenied:class extends Error{}},'./ownership-sheets':{}},{fetch:async(url,init)=>{
    calls.push({url:String(url),init});
    if(fail)throw new Error('private fixture diagnostic');
    return new Response(html?'private HTML':JSON.stringify({ready:true}),{status:html?502:200,headers:{'Content-Type':html?'text/html':'application/json',
      'X-GM-Upstream-Calls':'2','X-GM-Api-Wait-Ms':'4200','Retry-After':'5','Set-Cookie':'never-forward=this','Access-Control-Allow-Origin':'*'}});
  }}).forwardReelsRequest;
  const request=(method='POST',body={action:'health'},suffix='',headers={})=>new Request('https://host.example/api/k/personal-fixture/reels/finish'+suffix,{method,
    headers:{'Content-Type':'application/json','Authorization':'Bearer app-private','Cookie':'host-session=private','Origin':'https://host.example',...headers},...(method==='POST'?{body:JSON.stringify(body)}:{})});
  let r=await proxy(request(),'finish');assert.equal(r.status,200);assert.equal(r.headers.get('X-GM-Upstream-Calls'),'2');assert.equal(r.headers.get('X-GM-Api-Wait-Ms'),'4200');
  assert.equal(r.headers.get('Retry-After'),'5');assert.equal(r.headers.get('Set-Cookie'),null);assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
  assert.equal(calls[0].url,'https://duplicateur-de-reels.vercel.app/api/finish');
  assert.deepEqual(Object.keys(calls[0].init.headers).sort(),['Accept','Content-Type']);
  assert(!JSON.stringify(calls[0]).includes('personal-fixture'));assert(!JSON.stringify(calls[0]).includes('app-private'));
  const before=calls.length;
  for(const [req,operation,status]of [[request(),'../../private',404],[request('POST',{},'',{'Origin':'https://outside.example'}),'finish',403],
    [request('POST',{action:'unlisted'}),'source',400],[request('GET',{},'?action=clips&url=https://outside.example'),'opus',400],
    [request('POST',{action:'health'},'',{'Content-Type':'text/plain'}),'finish',415],[request('POST',{action:'health',data:'x'.repeat(262144)}),'finish',413]])assert.equal((await proxy(req,operation)).status,status);
  assert.equal(calls.length,before);
  // Every native client payload is accepted intact; extra fields never reach
  // the provider, even when the request is well below the body size limit.
  const payloads = [
    ['source',{action:'create',size:1024,extension:'mp4'}],
    ['source',{action:'target',sourceToken:'fixture-source'}],
    ['source',{action:'prepare',sourceToken:'fixture-source'}],
    ['finish',{action:'health'}], ['finish',{url:'https://media.example.test/fixture.mp4',index:0}],
    ['opus',{action:'submit',uploadId:'fixture-upload',title:'Fixture',sourceToken:'fixture-source'}],
    ['opus',{action:'duplicate',projectId:'fixture-project',clipId:'fixture-clip',sourceEditTicket:'fixture-ticket'}],
    ['opus',{action:'style',projectId:'fixture-project',clipId:'fixture-clip',index:0,editTicket:'fixture-ticket'}],
    ['opus',{action:'export-pack',projectId:'fixture-project',clipIds:['fixture-clip'],collectionId:'fixture-collection'}],
  ];
  for (const [operation,payload] of payloads) {
    assert.equal((await proxy(request('POST',payload),operation)).status,200);
    assert.deepEqual(JSON.parse(calls.at(-1).init.body),payload);
    const count=calls.length;
    assert.equal((await proxy(request('POST',{...payload,authorization:'must-not-leave-host'}),operation)).status,400);
    assert.equal(calls.length,count);
  }
  r=await proxy(request('GET',{},'?action=clips&projectId=existing&target=hd'),'opus');assert.equal(r.status,200);assert(calls.at(-1).url.includes('projectId=existing'));
  fail=true;const count=calls.length;r=await proxy(request('POST',{action:'submit',uploadId:'fixture-upload'}),'opus');assert.equal(r.status,502);assert.equal(calls.length,count+1,'Ambiguous paid operation is never retried');
  assert(!(await r.text()).includes('private fixture'));
  fail=false;html=true;r=await proxy(request(),'finish');assert.equal(r.status,502);assert(!(await r.text()).includes('private HTML'));
  for(const [app,prefix,guard,lib]of [['app_clippers','k','clipperParJeton','clippers'],['app_creatrices','c','creatriceParJeton','config']]){
    let allowed=false,forwarded=0,checked=0;
    const route=load(path.join(__dirname,`../../${app}/src/app/api/${prefix}/[token]/reels/[operation]/route.ts`),{
      ['@/lib/'+lib]:{[guard]:prefix==='k'?async token=>{checked++;assert.equal(token,'fixture');return allowed?{cle:'stable-clipper',racine:'stable-root'}:null}:token=>{checked++;assert.equal(token,'fixture');return allowed?{cle:'stable-clipper',racine:'stable-root'}:null}},
      '@/lib/google':{jetonGoogle:async()=>{throw new Error('Must not request real credentials')}},
      '@gm/reels/server':{createSheetsOwnershipStore:()=>({fixture:true}),forwardReelsRequest:async(req,op,owner,store)=>{forwarded++;assert.equal(owner.app,prefix==='k'?'clippers':'creatrices');assert.equal(owner.id,prefix==='k'?'stable-clipper':'stable-root');assert.equal(store.fixture,true);return Response.json({ready:true})}}});
    const context={params:{token:'fixture',operation:'finish'}};
    assert.equal((await route.POST(request(),context)).status,404);assert.equal(forwarded,0);
    allowed=true;assert.equal((await route.POST(request(),context)).status,200);assert.equal(forwarded,1);assert.equal(checked,2);
  }
  console.log('Proxy passed: existing host guards, fixed upstream, no credentials/CORS leakage, bounded JSON, pacing headers and zero mutation retries.');
})().catch(e=>{console.error(e);process.exitCode=1});
