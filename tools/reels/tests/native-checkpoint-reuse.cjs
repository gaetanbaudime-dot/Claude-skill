// The public browser entry point, two isolated JS tabs and shared storage/locks.
// Every HTTP request, upload and provider mutation below is a fixture only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto, createHash } = require('node:crypto');
const ts = require(require.resolve('typescript',{paths:[require('node:path').join(__dirname,'../../app_clippers')]}));
const source = fs.readFileSync(path.join(__dirname, '../src/lib/opus-native.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const BASE = 1791955000000, HOUR = 3600000;
const PROFILE = 'gm-native-clean-headline-20261014-v2';
const CONFIG = 'gm-mirror-h264-fr-clipanything-autohook-20261014-v1';
const FINISH = 'gm-native-polish-20261014-v1';
const bytes = Buffer.from('synthetic file identity fixture');
const digest = value => createHash('sha256').update(value).digest('hex');
const hash = digest(bytes), key = 'gm:native-job:v3:' + hash;
const file = (name = 'rush.mp4', value = bytes) => ({ name, size: value.length, lastModified: 1,
  arrayBuffer: async () => Uint8Array.from(value).buffer });
const final = i => ({url:`https://storage.example.test/media/job/version-${i + 1}.mp4`,
  downloadUrl:`https://storage.example.test/media/job/version-${i + 1}.mp4?download=1`,size:100+i});
function clip(id, index = null, version = 2) {
  return {projectId:'project',clipId:id,title:'Fixture',durationSec:15,score:90,
    previewUrl:`https://signed-ext.cdn.opus.pro/project/${id}/preview?v=${version}`,
    exportUrl:`https://signed-ext.cdn.opus.pro/project/${id}/hd?v=${version}&Signature=fresh`,
    styleIndex:index,renderKnown:true,pending:false,exportKnown:true,exportPending:false,
    editorial:{headlineCount:index===0||index===3?1:0,headlineTop:true,remainingPauses:0}};
}
function checkpoint(ageHours = 1, completed = true) {
  return {createdAt:BASE-ageHours*HOUR,profileRevision:PROFILE,sourceConfiguration:CONFIG,finishRevision:FINISH,
    sourceHash:hash,projectId:'project',uploadId:'gm-source:original-upload',sourceToken:'expired-upload-capability',
    mirroredBeforeCaptions:true,sourceClips:[clip('original')],selected:Array.from({length:6},(_,i)=>clip('copy-'+i,i)),
    styled:Array(6).fill(true),styleRequested:Array(6).fill(true),
    oldPreview:Array.from({length:6},(_,i)=>clip('copy-'+i,i,1).previewUrl),
    oldExport:Array.from({length:6},(_,i)=>clip('copy-'+i,i,1).exportUrl),seenPending:[],seenHD:[],
    polishResults:completed?Array.from({length:6},(_,i)=>final(i)):[],exported:true};
}
function environment(initial, options = {}) {
  let now=BASE, timerId=0, duplicateNumber=0, submitted=0;
  const storage=new Map(initial?[[key,JSON.stringify(initial)]]:[]), timers=new Map(), locks=new Map(), calls=[], phases=[], resumes=[], delivered=[], progress=[];
  const provider=new Map([['original',clip('original')],...(initial?.selected||[]).map(c=>[c.clipId,clip(c.clipId,c.styleIndex)])]);
  const localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),
    get length(){return storage.size},key:i=>[...storage.keys()][i]??null};
  class Clock extends Date {constructor(...args){super(...(args.length?args:[now]))} static now(){return now}}
  const setTimer=(fn,ms=0)=>{const id=++timerId;timers.set(id,{at:now+ms,fn});return id};
  const reply=(body,status=200,headers={})=>new Response(body===null?null:JSON.stringify(body),{status,headers:{
    'X-GM-Upstream-Calls':'1','X-GM-Api-Next-At':String(now),Date:new Clock().toUTCString(),...headers}});
  const network=async (input,init={})=>{
    const url=new URL(String(input),'https://app.example.test'),body=init.body?JSON.parse(init.body):{};
    const requestPath=url.pathname;
    url.pathname=url.pathname.replace(/^\/api\/[kc]\/[^/]+\/reels(?=\/)/,'/api');
    const action=body.action||url.searchParams.get('action');
    calls.push({path:url.pathname,requestPath,method:init.method||'GET',action,body});
    if(url.origin==='https://storage.example.test'){
      assert.equal(init.method,'HEAD');
      if(options.headError) throw new Error('offline network failure');
      const index=Number(url.pathname.match(/version-(\d+)/)[1])-1;
      if(options.slowFinal===index)await new Promise(resolve=>setTimer(resolve,1000));
      if(options.headErrorIndex===index)throw new Error('offline network failure for one file');
      return reply(null,options.headStatuses?.[index]||options.headStatus||(options.missingFinal===index?404:200),{
        'Content-Length':String(100+index),'Content-Type':options.badType?'text/plain':'video/mp4'});
    }
    if(url.pathname==='/api/finish'){
      if(action==='health')return reply({ready:true});
      assert(body.url.includes('Signature=fresh'),'Expired native signatures must be refreshed by a read');
      return reply(final(body.index));
    }
    if(url.pathname==='/api/source'){
      if(action==='create')return reply({sourceToken:'fixture-capability'});
      if(action==='target')return reply({uploaded:true});
      if(action==='prepare')return reply({ready:true,uploadId:'gm-source:fixture',mirroredBeforeCaptions:true});
      throw new Error('Unexpected source action');
    }
    assert.equal(url.pathname,'/api/opus');
    if(action==='submit'){
      submitted++;
      if(options.lostSubmit && submitted===1)throw new Error('Lost submit confirmation');
      return reply({projectId:'project'});
    }
    if(action==='recover')return reply({projectId:options.recoveryMissing?null:'project'});
    if(action==='clips')return options.nativeUnavailable?reply({error:'Native project temporarily unavailable'},503)
      :reply({clips:options.missingNative?[]:[...provider.values()]});
    if(action==='project-state')return reply({stage:'COMPLETE',clipCount:provider.size});
    if(action==='duplicate'){
      assert(provider.has(body.clipId));
      const copy=clip('new-copy-'+duplicateNumber++,null,1);provider.set(copy.clipId,copy);
      if(duplicateNumber===options.loseDuplicateConfirmationAfter+1)throw new Error('Fixture interruption: next copy created but confirmation lost');
      return reply(copy);
    }
    if(action==='style'){
      provider.set(body.clipId,clip(body.clipId,body.index));return reply({pending:true});
    }
    if(action==='export-pack')return reply({collectionId:'collection'});
    throw new Error('Unexpected fixture action '+action);
  };
  function tab(configuration) {
    const module={exports:{}};
    const navigator={locks:options.noLocks?undefined:{request(name,opts,callback){
      const run=callback||opts, previous=locks.get(name)||Promise.resolve();
      const next=previous.catch(()=>{}).then(()=>{if(opts?.signal?.aborted)throw new DOMException('Aborted','AbortError');return run()});
      locks.set(name,next);return next;
    }}};
    vm.runInNewContext(compiled,{module,exports:module.exports,window:{localStorage},navigator,crypto:webcrypto,
      Date:Clock,performance:{now:()=>now-BASE},URL,URLSearchParams,Response,Headers,AbortController,AbortSignal,DOMException,
      setTimeout:setTimer,clearTimeout:id=>timers.delete(id),fetch:network,console});
    const client=configuration?module.exports.createNativeClient(configuration):module.exports;
    return input=>client.generateOpusVariations(input,{onPhase:phase=>phases.push(phase),onResume:resume=>resumes.push(resume),
      onVariant:variant=>delivered.push({variant,at:now-BASE}),onProgress:value=>progress.push(value)});
  }
  async function settle(promises){
    let done=false, results;
    Promise.allSettled(promises).then(value=>{results=value;done=true});
    for(let i=0;!done && i<10000;i++){
      await new Promise(resolve=>setImmediate(resolve));
      if(done)break;
      if(timers.size){now=Math.min(...[...timers.values()].map(t=>t.at));for(const [id,t]of [...timers])if(t.at===now){timers.delete(id);t.fn()}}
    }
    assert(done,'Fixture jobs must settle');return results;
  }
  return {storage,calls,phases,resumes,delivered,progress,tab,settle,advanceTime:ms=>{now+=ms},run:async f=>(await settle([tab()(f||file())]))[0]};
}
async function main(){
  let checks=0;
  const yes=(value,message)=>{assert(value,message);checks++};
  const noWork=e=>yes(!e.calls.some(c=>['create','submit','duplicate','style','export-pack'].includes(c.action)||c.path==='/api/finish'&&!c.action),'No mutation/import');
  for(const age of [23,25,30*24-1]){
    const e=environment(checkpoint(age)),r=await e.run();
    yes(r.status==='fulfilled');yes(r.value.variants.length===6);yes(e.calls.length===6&&e.calls.every(c=>c.method==='HEAD'),'Finals bypass health and every native read');
    yes(r.value.variants.every((v,i)=>v.url===final(i).url&&v.downloadUrl===final(i).downloadUrl&&v.size===final(i).size),'Identical immutable final references');noWork(e);
    yes(e.resumes[0]===true&&e.phases.join(',')==='checking,cached','Completed resume reports actual cached phase');
    yes(e.delivered.length===6&&new Set(e.delivered.map(item=>item.variant.index)).size===6,'Each ready final is delivered once');
  }
  for(const age of [30*24,31*24]){
    const e=environment(checkpoint(age)),before=e.storage.get(key),r=await e.run();
    yes(r.status==='rejected'&&/30 jours/.test(r.reason.message));yes(e.calls.length===0);yes(e.storage.get(key)===before,'Expired record retained byte for byte');
  }
  for(const opts of [{headStatus:403},{headStatus:503},{headError:true},{badType:true}]){
    const cp=checkpoint(25),e=environment(cp,opts),r=await e.run();
    yes(r.status==='rejected');noWork(e);yes(e.calls.every(c=>c.method==='HEAD'));
    yes(JSON.stringify(JSON.parse(e.storage.get(key)).polishResults)===JSON.stringify(cp.polishResults));
  }
  for(const opts of [{headStatuses:{0:403}},{headStatuses:{0:503}},{headErrorIndex:0},
    {missingFinal:0,missingNative:true},{missingFinal:0,nativeUnavailable:true}]){
    const cp=checkpoint(25),e=environment(cp,{...opts,slowFinal:5}),r=await e.run();
    yes(r.status==='rejected','One unavailable final or native project leaves the attempt incomplete');
    yes(e.delivered.length===5&&e.delivered.map(item=>item.variant.index).sort().join(',')==='1,2,3,4,5',
      'All five independently validated files remain available when the sixth fails');
    yes(e.delivered.every(({variant:v})=>v.url===final(v.index).url&&v.downloadUrl===final(v.index).downloadUrl&&v.size===final(v.index).size),
      'Partial downloads retain the original verified MP4 references');
    yes(e.delivered.some(item=>item.at===0)&&e.delivered.some(item=>item.at===1000),
      'Fast finals are delivered immediately; slower validations drain before rejection');
    yes(!e.progress.includes(100),'A partial result never reports completion');noWork(e);
    yes(!e.calls.some(c=>c.path==='/api/opus'&&c.method!=='GET'),'A missing final never triggers a native render');
    yes(JSON.stringify(JSON.parse(e.storage.get(key)).polishResults)===JSON.stringify(cp.polishResults),'Partial failure preserves every saved reference');
  }
  for(const missingReference of ['null','short'])for(const opts of [{missingNative:true},{nativeUnavailable:true}]){
    const cp=checkpoint(25);
    if(missingReference==='null')cp.polishResults[5]=null;else cp.polishResults.pop();
    const e=environment(cp,opts),r=await e.run();
    yes(r.status==='rejected');
    yes(e.delivered.length===5&&e.delivered.map(item=>item.variant.index).sort().join(',')==='0,1,2,3,4',
      'Five completed downloads survive native failure when the sixth reference was never saved');
    yes(e.calls.filter(c=>c.method==='HEAD').length===5,'Only existing final references are checked');
    yes(!e.progress.includes(100));noWork(e);
    yes(JSON.stringify(JSON.parse(e.storage.get(key)).polishResults)===JSON.stringify(cp.polishResults));
  }
  for(const corrupt of ['url','size','style']){
    const cp=checkpoint(25);
    if(corrupt==='style')cp.styled[0]=false;
    else if(corrupt==='url')cp.polishResults[0].url='invalid-url';
    else cp.polishResults[0].size=0;
    const e=environment(cp),r=await e.run();
    yes(r.status==='rejected');yes(e.delivered.length===5&&e.delivered.every(item=>item.variant.index!==0),
      'One inconsistent reference cannot hide five independently valid files');
    yes(!e.progress.includes(100));noWork(e);yes(e.calls.every(c=>c.method==='HEAD'));
  }
  const duplicateFinals=checkpoint(25);duplicateFinals.polishResults[0]=duplicateFinals.polishResults[1];
  const duplicates=environment(duplicateFinals),duplicateResult=await duplicates.run();
  yes(duplicateResult.status==='rejected');yes(duplicates.delivered.length===4&&duplicates.delivered.every(item=>item.variant.index>1),
    'Ambiguous duplicate URLs are withheld without hiding independent valid files');noWork(duplicates);
  for(const selectedCount of [4,5]){
    // Start without a checkpoint. The real public orchestrator saves its first
    // two finishes, then loses the provider's confirmation of the next copy.
    const opts={loseDuplicateConfirmationAfter:selectedCount},e=environment(undefined,opts),interrupted=await e.run();
    yes(interrupted.status==='rejected'&&/Fixture interruption/.test(interrupted.reason.message));
    const saved=e.storage.get(key),partial=JSON.parse(saved);
    yes(partial.selected.length===selectedCount,'The interrupted orchestrator created the partial selected list');
    yes(partial.polishResults.filter(Boolean).length===2&&e.delivered.length===2,'Two MP4s finished before all six copies existed');
    yes(e.calls.filter(c=>c.action==='submit').length===1);
    const originalFinals=e.delivered.map(item=>item.variant);
    let callCount=e.calls.length;
    e.delivered.length=0;e.progress.length=0;
    const immediate=await e.run(),immediateCalls=e.calls.slice(callCount);
    yes(immediate.status==='rejected'&&/Aucun doublon/.test(immediate.reason.message),'Unconfirmed duplication still blocks an immediate retry');
    yes(immediateCalls.filter(c=>c.method==='HEAD').length===2,'Immediate retry validates both completed files');
    yes(JSON.stringify(e.delivered.map(item=>item.variant))===JSON.stringify(originalFinals),'Cleared UI receives the same two files despite unconfirmed duplication');
    yes(!e.progress.includes(100));noWork({calls:immediateCalls});
    yes(e.storage.get(key)===saved,'Immediate retry retains the real interrupted checkpoint');
    callCount=e.calls.length;
    e.delivered.length=0;e.progress.length=0;
    e.advanceTime(25*HOUR);opts.nativeUnavailable=true;
    const resumed=await e.run(),resumeCalls=e.calls.slice(callCount);
    yes(resumed.status==='rejected'&&/Native project temporarily unavailable/.test(resumed.reason.message));
    yes(resumeCalls.filter(c=>c.method==='HEAD').length===2,'Both saved MP4s are checked before the unavailable native project');
    yes(JSON.stringify(e.delivered.map(item=>item.variant))===JSON.stringify(originalFinals),'Both original downloads remain available on the interrupted job resume');
    yes(!e.progress.includes(100),'An interrupted four/five-copy job never reports completion');
    noWork({calls:resumeCalls});
    yes(!resumeCalls.some(c=>c.path==='/api/opus'&&c.method!=='GET'),'No duplicate or style is replayed on the failed resume');
    yes(e.storage.get(key)===saved,'The orchestrator-produced checkpoint is retained unchanged');
    yes(e.calls.filter(c=>c.action==='submit').length===1,'The initial import is never duplicated');
  }
  const missing=environment(checkpoint(25),{missingFinal:2}),missingResult=await missing.run();
  yes(missingResult.status==='fulfilled');yes(missing.calls.filter(c=>c.path==='/api/finish'&&!c.action).length===1,'Only explicitly missing final is regenerated');
  yes(!missing.calls.some(c=>['create','submit','duplicate','style'].includes(c.action)));
  yes(missing.delivered.length===6&&new Set(missing.delivered.map(item=>item.variant.index)).size===6,'Recovery publishes cached finals once, then the recovered file');
  const cp=checkpoint(25,false);delete cp.uploadId;delete cp.sourceToken;
  cp.selected.forEach(c=>c.exportUrl=c.exportUrl.replace('fresh','expired'));
  const existing=environment(cp),existingResult=await existing.run();
  yes(existingResult.status==='fulfilled');yes(!existing.calls.some(c=>c.path==='/api/source'||c.action==='submit'),'Project reuse is independent of upload capability');
  yes(existing.calls.filter(c=>c.path==='/api/finish'&&!c.action).every(c=>c.body.url.includes('Signature=fresh')));
  const unavailable=environment(cp,{missingNative:true}),gone=await unavailable.run();yes(gone.status==='rejected');noWork(unavailable);
  const wrongConfig=checkpoint();wrongConfig.sourceConfiguration='another-configuration';
  const wrongSource=checkpoint();wrongSource.sourceHash='different-bytes';
  for(const value of [wrongConfig,wrongSource]){
    const e=environment(value),before=e.storage.get(key),r=await e.run();yes(r.status==='rejected');yes(e.calls.length===0);yes(e.storage.get(key)===before);
  }
  const rename=environment(checkpoint()),renamed=await rename.run(file('another-name.mov'));
  yes(renamed.status==='fulfilled');yes(renamed.value.variants[0].name==='another-name-variante-1.mp4');noWork(rename);
  const different=environment(checkpoint()),old=different.storage.get(key),differentResult=await different.run(file('rush.mp4',Buffer.from('different bytes')));
  yes(differentResult.status==='fulfilled');yes(different.calls.filter(c=>c.action==='submit').length===1,'Different file gets its own explicitly requested job');yes(different.storage.get(key)===old);
  yes(different.resumes[0]===false);yes(['checking','upload','preparing','native','variants','exports'].every(p=>different.phases.includes(p)),'Every actual initial-processing phase is emitted');
  const legacy=checkpoint(25);delete legacy.sourceHash;delete legacy.sourceConfiguration;delete legacy.finishRevision;
  const legacyKey='gm:native-job:v2:old-scope:'+hash;
  const migrated=environment();migrated.storage.set(legacyKey,JSON.stringify(legacy));
  const legacyBytes=migrated.storage.get(legacyKey),migratedResult=await migrated.run();
  yes(migratedResult.status==='fulfilled');yes(migrated.storage.get(legacyKey)===legacyBytes);yes(JSON.parse(migrated.storage.get(key)).projectId==='project');noWork(migrated);
  const migrationTabs=environment();migrationTabs.storage.set(legacyKey,legacyBytes);
  const migrationResults=await migrationTabs.settle([migrationTabs.tab()(file()),migrationTabs.tab()(file('renamed.mp4'))]);
  yes(migrationResults.every(r=>r.status==='fulfilled'));yes(migrationTabs.storage.get(legacyKey)===legacyBytes);noWork(migrationTabs);
  const scopes=environment();scopes.storage.set(legacyKey,legacyBytes);scopes.storage.set('gm:native-job:v2:other-scope:'+hash,legacyBytes);
  const scopesResult=await scopes.run();yes(scopesResult.status==='rejected');yes(!scopes.storage.has(key));yes(scopes.calls.length===0);
  const current=environment(checkpoint());current.storage.set(legacyKey,JSON.stringify({...legacy,projectId:'other-project'}));
  const currentResult=await current.run();yes(currentResult.status==='fulfilled'&&currentResult.value.jobId==='project');
  for(const damaged of ['{',JSON.stringify({createdAt:BASE,selected:[]})]){
    const e=environment();e.storage.set(key,damaged);const r=await e.run();yes(r.status==='rejected');yes(e.storage.get(key)===damaged);yes(e.calls.length===0);
  }
  const invalidProject=checkpoint();invalidProject.projectId=0;
  const invalid=environment(invalidProject),invalidResult=await invalid.run();yes(invalidResult.status==='rejected');yes(invalid.calls.length===0);
  const malformedLegacy=environment();malformedLegacy.storage.set(legacyKey,'{');
  const malformedLegacyResult=await malformedLegacy.run();yes(malformedLegacyResult.status==='rejected');yes(malformedLegacy.storage.get(legacyKey)==='{');yes(!malformedLegacy.storage.has(key));yes(malformedLegacy.calls.length===0);
  const revision=checkpoint(25);revision.profileRevision='previous-caption-revision';
  const revised=environment(revision),revisedResult=await revised.run();
  yes(revisedResult.status==='fulfilled');const saved=JSON.parse(revised.storage.get(key));
  yes(saved.sourceClips[0].clipId==='original');yes(saved.previousGeneration.selected[0].clipId==='copy-0');
  yes(revised.calls.filter(c=>c.action==='duplicate').length===6&&revised.calls.filter(c=>c.action==='duplicate').every(c=>c.body.clipId==='original'),'All revised copies come from preserved masters');
  yes(!revised.calls.some(c=>c.action==='submit'||c.path==='/api/source'));
  const noMasters=structuredClone(revision);delete noMasters.sourceClips;
  const unknown=environment(noMasters),unknownResult=await unknown.run();yes(unknownResult.status==='rejected');noWork(unknown);
  const ambiguousRevision=structuredClone(revision);ambiguousRevision.duplicateRequested={sourceClipId:'original',version:6};
  const pendingRevision=environment(ambiguousRevision),pendingRevisionResult=await pendingRevision.run();yes(pendingRevisionResult.status==='rejected');yes(pendingRevision.calls.length===0);
  const finishRevision=checkpoint();finishRevision.finishRevision='older-finishing';
  const refinish=environment(finishRevision),refinishResult=await refinish.run();yes(refinishResult.status==='fulfilled');
  yes(refinish.calls.filter(c=>c.path==='/api/finish'&&!c.action).length===6);yes(!refinish.calls.some(c=>['submit','style','duplicate'].includes(c.action)));
  const upload=checkpoint(25,false);delete upload.projectId;upload.selected=[];upload.sourceClips=[];
  upload.styled=[];upload.styleRequested=[];upload.oldPreview=[];upload.oldExport=[];
  const expiredUpload=environment(upload),expiredUploadResult=await expiredUpload.run();yes(expiredUploadResult.status==='rejected');yes(expiredUpload.calls.length===0);yes(JSON.parse(expiredUpload.storage.get(key)).uploadId===upload.uploadId);
  const ambiguous=structuredClone(upload);ambiguous.submitting=true;
  const recovery=environment(ambiguous),recoveryResult=await recovery.run();yes(recoveryResult.status==='fulfilled');yes(recovery.calls.filter(c=>c.action==='recover').length===1);yes(!recovery.calls.some(c=>c.action==='submit'||c.path==='/api/source'));
  const absent=environment(ambiguous,{recoveryMissing:true}),absentResult=await absent.run();yes(absentResult.status==='rejected');noWork(absent);
  const noUpload=structuredClone(ambiguous);delete noUpload.uploadId;
  const noRef=environment(noUpload),noRefResult=await noRef.run();yes(noRefResult.status==='rejected');noWork(noRef);
  const lost=environment(undefined,{lostSubmit:true});const lostResult=await lost.run();yes(lostResult.status==='rejected');
  yes(JSON.parse(lost.storage.get(key)).submitting===true);const resumed=await lost.run();yes(resumed.status==='fulfilled');yes(lost.calls.filter(c=>c.action==='submit').length===1,'Never replay an ambiguous paid submit');
  const tabs=environment();const parallel=await tabs.settle([tabs.tab()(file()),tabs.tab()(file('renamed.mp4'))]);
  yes(parallel.every(r=>r.status==='fulfilled'));yes(tabs.calls.filter(c=>c.action==='submit').length===1,'Two independent tabs share the entire job lock');
  yes(tabs.calls.filter(c=>c.action==='duplicate').length===6);yes(parallel[0].value.variants.every((v,i)=>v.url===parallel[1].value.variants[i].url));
  const unsupported=environment(undefined,{noLocks:true}),unsupportedResult=await unsupported.run();yes(unsupportedResult.status==='rejected');yes(unsupported.calls.length===0);yes(unsupported.storage.size===0);
  return checks;
}
module.exports=main;
module.exports.environment=environment;
module.exports.file=file;
if(require.main===module)main().then(checks=>console.log(JSON.stringify({offline:true,checkpointReuseChecks:checks,networkRequests:0}))).catch(e=>{console.error(e);process.exitCode=1});
