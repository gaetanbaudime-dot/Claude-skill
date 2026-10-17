const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.resolve('../app_clippers/package.json'));
const React=appRequire('react'),{act,create}=appRequire('react-test-renderer'),ts=appRequire('typescript');
const cache=new Map();let fetches=0,shares=0,freshTap=false,downloads=0,mode='ok';
const nav={userAgent:'iPhone',platform:'iPhone',maxTouchPoints:1,canShare:()=>true,share:()=>{assert(freshTap,'Native share must start synchronously in a tap');shares++;return mode==='cancel'?Promise.reject(new DOMException('cancelled','AbortError')):Promise.resolve()}};
const context={File,URL,Uint8Array,DOMException,AbortController,navigator:nav,
  setTimeout:(fn,ms)=>{if(ms<60000)fn()},
  document:{body:{appendChild(){}},createElement:()=>({click(){downloads++},remove(){}})},
  fetch:async()=>{fetches++;return new Response(Uint8Array.from([1,2,3,4]),{headers:{'Content-Type':'video/mp4'}})},
};
function load(filename){
 if(cache.has(filename))return cache.get(filename);
 const module={exports:{}};
 const req=name=>{
  if(name==='react'||name.startsWith('react/'))return appRequire(name);
  if(name.endsWith('.module.css'))return {__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};
  const p=path.resolve(path.dirname(filename),name);return load(fs.existsSync(p+'.tsx')?p+'.tsx':p+'.ts');
 };
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{...context,module,exports:module.exports,require:req});
 cache.set(filename,module.exports);return module.exports;
}
const Component=load(path.resolve('src/components/Downloads.tsx')).default;
const labels=['Variante 1 + Hook','Variante 2 Verticale','Variante 3 Bleue','Variante 4 + Hook','Variante 5 Classique','Variante 6 Mouvement'];
const videos=Array.from({length:6},(_,index)=>({id:'v'+index,index,size:4,name:'old-name.mp4',captionPreset:'Deep Diver',url:'https://example.test/v'+index+'.mp4',downloadUrl:'https://example.test/v'+index+'.mp4?download=1'}));
const text=n=>typeof n==='string'?n:Array.isArray(n)?n.map(text).join(''):n?.children?.map(text).join('')||'';
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function tap(node){await act(async()=>{freshTap=true;node.props.onClick();freshTap=false;await flush()})}
(async()=>{
 let view;await act(async()=>{view=create(React.createElement(Component,{variants:videos}));await flush()});
 assert.equal(fetches,6,'Completed small pack is prepared in background');
 labels.forEach(label=>assert(text(view.toJSON()).includes(label)));
 assert(!text(view.toJSON()).includes('Deep Diver'),'Old provider metadata is never displayed');
 const all=()=>view.root.findAllByType('button').find(n=>text(n)==='Enregistrer les 6 vidéos');
 await tap(all());assert.equal(shares,1);assert.equal(fetches,6,'First ready-pack tap shares without fetching');
 mode='cancel';await tap(all());assert.equal(shares,2);assert(text(view.toJSON()).includes('Partage annulé'));
 mode='ok';await tap(all());assert.equal(shares,3);assert.equal(fetches,6,'Cancellation retains prepared files');
 await act(async()=>view.unmount());
 fetches=0;shares=0;
 await act(async()=>{view=create(React.createElement(Component,{variants:videos.slice(0,1)}));await flush()});
 const save=()=>view.root.findAllByType('button').find(n=>n.props['aria-label']?.startsWith('Enregistrer dans Photos'));
 await tap(save());assert.equal(fetches,1);assert.equal(shares,0,'Cold tap only prepares and never shares after awaiting');
 const confirm=view.root.findAllByType('button').find(n=>!n.props['aria-label']&&text(n)==='Enregistrer dans Photos');
 await tap(confirm);assert.equal(shares,1,'Prepared confirmation gets a fresh gesture');
 await act(async()=>view.unmount());
 nav.userAgent='Android';nav.canShare=()=>false;
 await act(async()=>{view=create(React.createElement(Component,{variants:videos}));await flush()});
 assert.equal(view.root.findAllByType('button').length,0,'Unsupported sharing falls back directly to MP4 links');
 assert.equal(view.root.findAllByType('a').length,6);
 await act(async()=>view.unmount());
 console.log('Mobile save UI passed: six public labels, iPhone prefetch and one-tap handoff, cancellation/retry without refetch, cold preparation/fresh tap, Android unsupported fallback.');
})().catch(e=>{console.error(e);process.exitCode=1});

