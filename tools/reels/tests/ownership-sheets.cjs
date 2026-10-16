const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.join(__dirname,'../../app_clippers/package.json')),ts=appRequire('typescript');
let mode='',calls=[],values=[['version','owner_sha256','kind','resource_sha256','parent_sha256']];
const unavailable=class extends Error{};
const moduleFixture={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/server/ownership-sheets.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{
 module:moduleFixture,exports:moduleFixture.exports,require:()=>({OwnershipUnavailable:unavailable}),URLSearchParams,AbortSignal,
 fetch:async(url,init)=>{calls.push({url:String(url),init});assert.equal(init.headers.Authorization,'Bearer server-only-fixture');assert.equal(init.cache,'no-store');assert.equal(init.redirect,'error');
   if(mode==='down')return new Response('{}',{status:503});
   if(String(url).includes('drive/v3'))return Response.json({files:mode==='missing'?[]:mode==='ambiguous'?[{id:'one'},{id:'two'}]:mode==='malformed-id'?[{}]:[{id:'existing-workbook'}]});
   if(init.method==='POST'){assert(String(url).includes(':append'));const rows=JSON.parse(init.body).values;values.push(...rows);return Response.json({updates:{updatedRows:mode==='lost-write'?0:rows.length}})}
   if(mode==='missing-tab')return new Response('{}',{status:400});
   return Response.json({values:mode==='bad-header'?[['bad']]:mode==='bad-row'?[values[0],['v1','raw-name','source','raw-token','-']]:values});
 }});
const make=app=>moduleFixture.exports.createSheetsOwnershipStore(app,async()=> 'server-only-fixture');
(async()=>{
 for(const app of ['clippers','creatrices']){
   const store=make(app);assert.equal((await store.read()).length,0);assert(decodeURIComponent(calls.at(-2).url).includes(app==='clippers'?'App+clippers':'App+créatrices'));
 }
 const row={owner:'a'.repeat(64),kind:'source',resource:'b'.repeat(64),parent:'-'};
 await make('clippers').append([row]);assert.equal((await make('clippers').read())[0].resource,row.resource,'New process reads durable records');
 for(mode of ['missing','ambiguous','malformed-id','missing-tab','bad-header','bad-row','down'])await assert.rejects(()=>make('clippers').read());
 mode='lost-write';await assert.rejects(()=>make('clippers').append([row]));mode='';
 assert(calls.every(call=>!call.url.includes('permissions')&&!call.url.includes(':batchUpdate')),'No provisioning or permission changes');
 assert(calls.filter(call=>call.init.method==='POST').every(call=>call.url.includes(':append')),'No file, tab or infrastructure creation');
 console.log('Sheets ownership passed: existing workbook only, durable fresh reads, exact schema, missing/ambiguous/down/corrupt store rejected, writes verified, no provisioning or permissions.');
})().catch(e=>{console.error(e);process.exitCode=1});
