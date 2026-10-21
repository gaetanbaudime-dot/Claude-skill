const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.join(__dirname,'../../app_clippers/package.json')),ts=appRequire('typescript');
let backend;
function load(name){const module={exports:{}};const file=path.join(__dirname,'../src/server',name+'.ts');
  const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  vm.runInNewContext(source,{module,exports:module.exports,require:n=>n.startsWith('.')?load(n.slice(2)):require(n),Request,Response,Headers,URL,URLSearchParams,AbortController,AbortSignal,Uint8Array,TextDecoder,fetch:(...args)=>backend(...args)});return module.exports;}
const proxy=load('proxy').forwardReelsRequest,{fingerprint,resource}=load('ownership');
let checks=0,requests=0,serial=0,reads=0,writes=0,failRead=false,failWrite=false,dropWrite=false,corruptReply=false,failUpstream=false,beforeReply;
const ledger=[];
const store=()=>({read:async()=>{reads++;if(failRead)throw Error('private ledger diagnostic');return ledger.map(r=>({...r}))},append:async rows=>{writes++;if(failWrite)throw Error('private write diagnostic');if(!dropWrite)ledger.push(...rows.map(r=>({...r})))}});
const clips=(projectId)=>Array.from({length:6},(_,i)=>({projectId,clipId:'clip-'+i,pending:false,exportUrl:`https://media.example.test/${projectId}/clip-${i}.mp4?sig=fixture`}));
backend=async(target,init)=>{
  requests++;if(failUpstream)throw Error('private provider diagnostic');
  const url=new URL(target),b=init.body?JSON.parse(init.body):Object.fromEntries(url.searchParams),op=url.pathname.split('/').at(-1);let data={ready:true};
  if(op==='source'&&b.action==='create')data={sourceToken:'source-'+(++serial),uploadUrl:'https://upload.example.test/fixture'};
  else if(op==='source')data={ready:true,uploadId:'upload-'+b.sourceToken,mirroredBeforeCaptions:true};
  else if(b.action==='submit'||b.action==='recover')data={projectId:'project-'+b.uploadId};
  else if(b.action==='clips')data={projectId:b.projectId,clips:clips(b.projectId)};
  else if(b.action==='duplicate')data={projectId:b.projectId,clipId:'copy-'+(++serial),pending:false,exportUrl:null};
  else if(b.action==='export-pack')data={collectionId:b.collectionId||'collection-'+(++serial),clips:b.clipIds.map(id=>({id:b.projectId+'.'+id,exportUrl:`https://media.example.test/${b.projectId}/${id}.mp4?sig=fixture`}))};
  else if(op==='finish'&&!b.action)data={url:'https://final.example.test/'+(++serial)+'.mp4',downloadUrl:'https://final.example.test/'+serial+'.mp4?download=1',size:1024};
  if(corruptReply&&b.action==='clips')data.clips[0].projectId='another-project';
  beforeReply?.();
  return Response.json(data);
};
const ownerA={app:'clippers',id:'stable-person-a'},ownerB={app:'clippers',id:'stable-person-b'};
async function call(owner,op,input={},get=false){const request=new Request('https://app.example.test/api/k/private-fixture/reels/'+op+(get?'?'+new URLSearchParams(input):''),{method:get?'GET':'POST',headers:{'Content-Type':'application/json','Origin':'https://app.example.test'},...(get?{}:{body:JSON.stringify(input)})});return proxy(request,op,owner,store());}
async function ok(owner,op,input,get=false){const r=await call(owner,op,input,get);assert.equal(r.status,200,await r.clone().text());checks++;return r.json();}
async function deny(owner,op,input,get=false,status=403){const before=requests,r=await call(owner,op,input,get);assert.equal(r.status,status,await r.clone().text());assert.equal(requests,before,'Forbidden reference never leaves host');checks++;}
async function setup(owner){const source=await ok(owner,'source',{action:'create',size:1024,extension:'mp4'});const prepared=await ok(owner,'source',{action:'prepare',sourceToken:source.sourceToken});const submitted=await ok(owner,'opus',{action:'submit',sourceToken:source.sourceToken,uploadId:prepared.uploadId,title:'fixture'});const {projectId}=submitted;const list=await ok(owner,'opus',{action:'clips',projectId},true);const ids=list.clips.map(c=>c.clipId);const pack=await ok(owner,'opus',{action:'export-pack',projectId,clipIds:ids});return {...source,...prepared,...submitted,clipIds:ids,...pack,exportUrl:list.clips[0].exportUrl};}
(async()=>{
 const ownerC={app:'creatrices',id:ownerA.id};
 const a=await setup(ownerA),b=await setup(ownerB),c=await setup(ownerC);
 // A repeated poll validates its existing claims against a fresh durable read,
 // but never writes or performs a third read solely to confirm no mutation.
 let priorReads=reads,priorWrites=writes,priorRows=ledger.length;
 await ok(ownerA,'opus',{action:'clips',projectId:a.projectId},true);
 assert.equal(reads-priorReads,2,'Registered poll uses authorization + fresh reply validation');
 assert.equal(writes-priorWrites,0,'Registered poll never appends duplicate claims');
 assert.equal(ledger.length,priorRows);
 // A new capability is not released until its append has been independently
 // read back, including when the storage layer reports success but loses it.
 priorReads=reads;priorWrites=writes;
 const newCopy=await ok(ownerA,'opus',{action:'duplicate',projectId:a.projectId,clipId:a.clipIds[0]});
 assert.equal(reads-priorReads,3,'New claims retain independent write confirmation');
 assert.equal(writes-priorWrites,1);
 assert(ledger.some(row=>row.kind==='clip'&&row.resource===resource('clip',a.projectId,newCopy.clipId)));
 dropWrite=true;priorReads=reads;priorWrites=writes;
 let lost=await call(ownerA,'source',{action:'create',size:1024,extension:'mp4'});
 assert.equal(lost.status,502);assert.equal((await lost.json()).sourceToken,undefined);
 assert.equal(reads-priorReads,3);assert.equal(writes-priorWrites,1);dropWrite=false;
 // A conflict introduced while the backend works must still fail, even for
 // a claim which was valid in the initial authorization snapshot.
 priorWrites=writes;
 beforeReply=()=>ledger.push({kind:'export',resource:resource('export',a.exportUrl),parent:resource('clip',a.projectId,a.clipIds[0]),owner:fingerprint([ownerB.app,ownerB.id])});
 const conflicted=await call(ownerA,'opus',{action:'clips',projectId:a.projectId},true);
 assert.equal(conflicted.status,502);assert.equal(writes,priorWrites);beforeReply=undefined;ledger.pop();
 // A single durable ledger may serve both apps. Even identical canonical IDs
 // remain distinct; exercise both directions for every read/mutation below.
 for(const [owner,foreign,own]of [[ownerA,b,a],[ownerB,a,b],[ownerA,c,a],[ownerC,a,c]]){
   await deny(owner,'source',{action:'target',sourceToken:foreign.sourceToken});
   await deny(owner,'source',{action:'prepare',sourceToken:foreign.sourceToken});
   await deny(owner,'opus',{action:'submit',sourceToken:foreign.sourceToken,uploadId:foreign.uploadId,title:'foreign'});
   await deny(owner,'opus',{action:'submit',sourceToken:own.sourceToken,uploadId:foreign.uploadId,title:'mixed'});
   await deny(owner,'opus',{action:'recover',uploadId:foreign.uploadId},true);
   await deny(owner,'opus',{action:'clips',projectId:foreign.projectId},true);
   await deny(owner,'opus',{action:'project-state',projectId:foreign.projectId},true);
   await deny(owner,'opus',{action:'duplicate',projectId:foreign.projectId,clipId:foreign.clipIds[0]});
   await deny(owner,'opus',{action:'style',projectId:foreign.projectId,clipId:foreign.clipIds[0],index:0});
   await deny(owner,'opus',{action:'export-pack',projectId:foreign.projectId,clipIds:foreign.clipIds});
   await deny(owner,'opus',{action:'export-pack',projectId:own.projectId,clipIds:own.clipIds,collectionId:foreign.collectionId});
   await deny(owner,'finish',{url:foreign.exportUrl,index:0});
   await deny(owner,'finish',{url:own.exportUrl+'&foreign=1',index:0});
   for(const action of ['clips','project-state'])await deny(owner,'opus',{action,projectId:'unregistered'},true);
   await deny(owner,'opus',{action:'clips',projectId:own.projectId,clipIds:'unregistered'},true);
   for(const action of ['duplicate','style'])await deny(owner,'opus',{action,projectId:own.projectId,clipId:'unregistered',...(action==='style'?{index:0}:{})});
   await deny(owner,'opus',{action:'export-pack',projectId:own.projectId,clipIds:[...own.clipIds.slice(0,5),'unregistered']});
   await deny(owner,'opus',{action:'export-pack',projectId:own.projectId,clipIds:own.clipIds,collectionId:'unregistered'});
   await deny(owner,'finish',{url:'https://media.example.test/unregistered.mp4',index:0});
   await ok(owner,'opus',{action:'recover',uploadId:own.uploadId},true);
   await ok(owner,'opus',{action:'project-state',projectId:own.projectId},true);
   await ok(owner,'opus',{action:'clips',projectId:own.projectId,clipIds:own.clipIds.join(',')},true);
   const copy=await ok(owner,'opus',{action:'duplicate',projectId:own.projectId,clipId:own.clipIds[0]});
   await ok(owner,'opus',{action:'style',projectId:own.projectId,clipId:copy.clipId,index:0});
   await ok(owner,'opus',{action:'export-pack',projectId:own.projectId,clipIds:own.clipIds,collectionId:own.collectionId});
   await deny(owner,'opus',{action:'export-pack',projectId:own.projectId,clipIds:[...own.clipIds.slice(0,5),copy.clipId],collectionId:own.collectionId});
   await ok(owner,'finish',{url:own.exportUrl,index:0});
 }
 // Same user retains ownership with a fresh server store; the app namespace is
 // part of the identity. Caller-supplied identity/token fields are not accepted.
 await deny({app:'creatrices',id:ownerA.id},'opus',{action:'clips',projectId:a.projectId},true);
 await deny(ownerB,'opus',{action:'clips',projectId:a.projectId,owner:ownerA.id},true,400);
 failRead=true;await deny(ownerA,'source',{action:'create',size:1024,extension:'mp4'},false,503);failRead=false;
 failWrite=true;let before=requests,r=await call(ownerA,'source',{action:'create',size:1024,extension:'mp4'});assert.equal(r.status,502);assert.equal(requests,before+1);assert(!('sourceToken' in await r.json()));checks++;failWrite=false;
 corruptReply=true;r=await call(ownerA,'opus',{action:'clips',projectId:a.projectId},true);assert.equal(r.status,502);checks++;corruptReply=false;
 failUpstream=true;before=requests;r=await call(ownerA,'opus',{action:'duplicate',projectId:a.projectId,clipId:a.clipIds[0]});assert.equal(r.status,502);assert.equal(requests,before+1);assert.equal((await r.json()).definitelyRejected,undefined);checks++;failUpstream=false;
 // An ownership conflict or a vanished ledger cannot fall back to accepting a
 // browser checkpoint or merely checking the vendor hostname.
 ledger.push({kind:'project',resource:resource('project',a.projectId),parent:resource('upload',a.uploadId),owner:fingerprint([ownerB.app,ownerB.id])});
 await deny(ownerA,'opus',{action:'clips',projectId:a.projectId},true);
 const snapshot=JSON.stringify(ledger);assert(!snapshot.includes(ownerA.id));assert(!snapshot.includes(a.sourceToken));assert(!snapshot.includes(a.projectId));assert(!snapshot.includes('https://'));
 ledger.length=0;await deny(ownerA,'opus',{action:'clips',projectId:a.projectId},true);
 console.log(JSON.stringify({checks,paidCalls:0,tests:'Multiple identities and both app namespaces in one ledger, trusted reply registration, parent relationships, exact export URL, new process/store, ledger loss/conflict/unavailability, no credential persistence, no mutation retry'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1});
