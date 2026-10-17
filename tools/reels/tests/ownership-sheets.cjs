const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.join(__dirname,'../../app_clippers/package.json')),ts=appRequire('typescript');
let mode='',calls=[],tokenCalls=0,values=[['version','owner_sha256','kind','resource_sha256','parent_sha256']];
const unavailable=class extends Error{};
const moduleFixture={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/server/ownership-sheets.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{
 module:moduleFixture,exports:moduleFixture.exports,require:()=>({OwnershipUnavailable:unavailable}),URLSearchParams,AbortSignal,
 fetch:async(url,init)=>{calls.push({url:String(url),init});assert.equal(init.headers.Authorization,'Bearer server-only-fixture');assert.equal(init.cache,'no-store');assert.equal(init.redirect,'error');
   if(mode==='down'||mode==='denied')return new Response('{}',{status:mode==='denied'?403:503});
   if(String(url).includes('drive/v3'))return Response.json({files:mode==='missing'?[]:mode==='ambiguous'?[{id:'one'},{id:'two'}]:mode==='malformed-id'?[{}]:[{id:'existing-workbook'}]});
   if(init.method==='POST'){assert(String(url).includes(':append'));const rows=JSON.parse(init.body).values;values.push(...rows);return Response.json({updates:{updatedRows:mode==='lost-write'?0:rows.length}})}
   if(mode==='missing-tab')return new Response('{}',{status:400});
   return Response.json({values:mode==='bad-header'?[['bad']]:mode==='bad-row'?[values[0],['v1','raw-name','source','raw-token','-']]:values});
 }});
const make=(app,options)=>moduleFixture.exports.createSheetsOwnershipStore(app,async()=>{tokenCalls++;return 'server-only-fixture'},options);
(async()=>{
 for(const app of ['clippers','creatrices']){
   const store=make(app);assert.equal((await store.read()).length,0);assert(decodeURIComponent(calls.at(-2).url).includes(app==='clippers'?'App+clippers':'App+créatrices'));
 }
 const row={owner:'a'.repeat(64),kind:'source',resource:'b'.repeat(64),parent:'-'};
 await make('clippers').append([row]);assert.equal((await make('clippers').read())[0].resource,row.resource,'New process reads durable records');
 for(mode of ['missing','ambiguous','malformed-id','missing-tab','bad-header','bad-row','down'])await assert.rejects(()=>make('clippers').read());
 mode='lost-write';await assert.rejects(()=>make('clippers').append([row]));mode='';
 // Explicit server-selected ID can point both namespaces to the same existing
 // workbook; no discovery, creation or fallback occurs in this mode.
 const start=calls.length,sharedId='shared-existing-workbook';
 const clippers=make('clippers',{workbookId:sharedId}),creatrices=make('creatrices',{workbookId:sharedId});
 const creatorRow={owner:'c'.repeat(64),kind:'source',resource:'d'.repeat(64),parent:'-'};
 await creatrices.append([creatorRow]);
 assert((await clippers.read()).some(r=>r.owner===creatorRow.owner));
 assert((await creatrices.read()).some(r=>r.owner===row.owner));
 assert(calls.slice(start).every(c=>c.url.includes('/spreadsheets/'+sharedId+'/values/')));
 const invalidStart=calls.length,tokenStart=tokenCalls;
 for(const workbookId of ['', ' ', 'https://docs.google.com/spreadsheets/d/id', '../other', 'x'.repeat(201)]){
   await assert.rejects(()=>make('creatrices',{workbookId}).read());
   await assert.rejects(()=>make('creatrices',{workbookId}).append([row]));
 }
 assert.equal(calls.length,invalidStart);assert.equal(tokenCalls,tokenStart,'Invalid ID fails before credentials or network');
 for(mode of ['denied','missing-tab','down','bad-header']){
   const before=calls.length;await assert.rejects(()=>make('creatrices',{workbookId:sharedId}).read());
   assert.equal(calls.length,before+1);assert(calls.at(-1).url.includes('/spreadsheets/'+sharedId+'/'),'No fallback on failure');
 }
 mode='';
 assert(calls.every(call=>!call.url.includes('permissions')&&!call.url.includes(':batchUpdate')),'No provisioning or permission changes');
 assert(calls.filter(call=>call.init.method==='POST').every(call=>call.url.includes(':append')),'No file, tab or infrastructure creation');
 console.log('Sheets ownership passed: explicit existing ID shared by two app stores, no discovery/fallback in ID mode, invalid ID rejected before credentials/network; durable fresh reads, exact schema, missing/ambiguous/down/corrupt store rejected, writes verified, no provisioning or permissions.');
})().catch(e=>{console.error(e);process.exitCode=1});
