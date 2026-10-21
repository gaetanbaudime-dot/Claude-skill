const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const appRequire=require('node:module').createRequire(path.resolve('../app_clippers/package.json'));
const React=appRequire('react'),{act,create}=appRequire('react-test-renderer'),ts=appRequire('typescript');
const cache=new Map();let fetches=0,shares=0,freshTap=false,downloads=0,mode='ok',paused=0;
const observers=[];
class ViewportObserver {
 constructor(callback){this.callback=callback;observers.push(this)}
 observe(target){this.target=target} disconnect(){}
}
const nav={userAgent:'iPhone',platform:'iPhone',maxTouchPoints:1,canShare:()=>true,share:()=>{assert(freshTap,'Native share must start synchronously in a tap');shares++;return mode==='cancel'?Promise.reject(new DOMException('cancelled','AbortError')):Promise.resolve()}};
const context={File,URL,Uint8Array,DOMException,AbortController,navigator:nav,IntersectionObserver:ViewportObserver,
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
const options={createNodeMock:node=>node.type==='video'?{currentTime:0,pause(){paused++}}:node.type==='dialog'?{open:false,showModal(){this.open=true},close(){this.open=false}}:null};
(async()=>{
 let view;await act(async()=>{view=create(React.createElement(Component,{variants:videos}),options);await flush()});
 assert.equal(fetches,0,'Unknown mobile connections never prefetch six full HD videos');
 labels.forEach(label=>assert(text(view.toJSON()).includes(label)));
 assert(!text(view.toJSON()).includes('Deep Diver'),'Old provider metadata is never displayed');
 const previews=view.root.findAllByType('video');
 assert.equal(previews.length,6,'Every variant has a visible player');
 assert(previews.every(preview=>!preview.props.src),'Offscreen previews do not start six competing requests');
 await act(async()=>{observers[0].callback([{isIntersecting:true}]);await flush()});
 view.root.findAllByType('li').forEach((card,index)=>{
  const preview=card.findByType('video');
  assert.equal(preview.props.src,index===0?videos[index].url:undefined);
  assert(preview.props.controls&&preview.props.playsInline,'Preview can play inline with native controls');
  assert.equal(preview.props.preload,index===0?'metadata':'none','Only a nearby preview loads metadata');
  assert(!preview.props.autoPlay);
  assert(!preview.parent||preview.parent.type!=='details','Preview is never collapsed');
  const children=card.children.filter(child=>typeof child!=='string');
  const actions=children.findIndex(child=>child.findAllByType('button').length>0);
  const player=children.findIndex(child=>child.findAllByType('video').length>0);
  assert(player<actions,'Photos save button sits below the preview');
 });
 await act(async()=>{previews[0].props.onPlay({currentTarget:observers[0].target});previews[1].props.onPlay({currentTarget:observers[1].target})});
 assert.equal(paused,1,'Starting another preview pauses the previous video');
 await act(async()=>{previews[0].props.onPause();previews[1].props.onPause();previews[0].props.onPlay({currentTarget:observers[0].target})});
 observers[0].target.currentTime=1.25;
 const all=()=>view.root.findAllByType('button').find(n=>text(n)==='Enregistrer les 6 dans Photos');
 await tap(all());assert.equal(shares,0,'The first mobile tap prepares without sharing after an await');
 assert.equal(fetches,6,'Saving fetches each HD file exactly once');
 assert.equal(view.root.findAllByType('video')[0].props.src,videos[0].url,'A newly cached file never replaces the source while its preview plays');
 await act(async()=>{view.root.findAllByType('video')[0].props.onPause();await flush()});
 assert(view.root.findAllByType('video')[0].props.src.startsWith('blob:'),'Prepared HD bytes become the preview source after pause');
 const switchedPlayer={currentTime:0,duration:8};
 view.root.findAllByType('video')[0].props.onLoadedMetadata({currentTarget:switchedPlayer});
 assert.equal(switchedPlayer.currentTime,1.25,'Switching to prepared bytes preserves the playback position');
 const confirmAll=view.root.findAllByType('button').find(n=>!n.props['aria-label']&&text(n)==='Enregistrer dans Photos');
 await tap(confirmAll);assert.equal(shares,1,'A fresh confirmation tap opens native Photos sharing');
 assert(view.root.findAllByType('video')[0].props.src.startsWith('blob:'),'Prepared HD bytes are reused for playback');
 await tap(view.root.findAllByType('button').find(n=>n.props['aria-label']==='Fermer'));
 mode='cancel';await tap(all());assert.equal(shares,2);assert(text(view.toJSON()).includes('Partage annulé'));
 mode='ok';await tap(all());assert.equal(shares,3);assert.equal(fetches,6,'Cancellation retains prepared files');
 await act(async()=>view.unmount());
 fetches=0;shares=0;
 await act(async()=>{view=create(React.createElement(Component,{variants:videos.slice(0,1)}),options);await flush()});
 const save=()=>view.root.findAllByType('button').find(n=>n.props['aria-label']?.startsWith('Enregistrer dans Photos'));
 await tap(save());assert.equal(fetches,1);assert.equal(shares,0,'Cold tap only prepares and never shares after awaiting');
 const confirm=view.root.findAllByType('button').find(n=>!n.props['aria-label']&&text(n)==='Enregistrer dans Photos');
 await tap(confirm);assert.equal(shares,1,'Prepared confirmation gets a fresh gesture');
 await act(async()=>view.unmount());
 nav.userAgent='Android';nav.canShare=()=>false;
 await act(async()=>{view=create(React.createElement(Component,{variants:videos}),options);await flush()});
 assert.equal(view.root.findAllByType('button').length,0,'Unsupported sharing falls back directly to MP4 links');
 assert.equal(view.root.findAllByType('a').length,6);
 await act(async()=>view.unmount());
 let mapReads=0,tick;
 const stableVariants=new Proxy(videos,{get(target,key,receiver){if(key==='map')mapReads++;return Reflect.get(target,key,receiver)}});
 function Parent(){const [value,setValue]=React.useState(0);tick=setValue;return React.createElement('div',{'data-tick':value},React.createElement(Component,{variants:stableVariants}))}
 await act(async()=>{view=create(React.createElement(Parent),options);await flush()});
 const firstRenderReads=mapReads;
 for(let n=1;n<=3;n++)await act(async()=>tick(n));
 assert.equal(mapReads,firstRenderReads,'Unrelated parent elapsed ticks do not redraw the six-player result list');
 await act(async()=>view.unmount());
 console.log('Mobile save UI passed: zero full-file prefetches on unknown/mobile networks, viewport-only previews, single active player, uninterrupted playback during preparation, reused playback blobs with preserved position, no timer redraws, fresh Photos tap, cancellation/retry without refetch, Android fallback.');
})().catch(e=>{console.error(e);process.exitCode=1});

