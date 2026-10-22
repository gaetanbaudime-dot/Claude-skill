// Actual host App + shared UI/hook. Provider, usage signals and other tabs are
// fixtures. Width cases verify the mobile UI contract, not screenshot pixels.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const toolsRoot=path.resolve(__dirname,'../..'),shared=path.join(toolsRoot,'reels/src');
const appRequire=require('node:module').createRequire(path.join(toolsRoot,'app_clippers/package.json'));
const React=appRequire('react'),renderer=appRequire('react-test-renderer'),ts=appRequire('typescript'),{act}=renderer;
const cases=[];
const output=i=>({id:'fixture-'+i,index:i,name:`fixture-${i}.mp4`,captionPreset:['Deep Diver','Simple','PopLine','Soft Landing','Grow','Baby Steps'][i],url:`https://media.example.test/version-${i}.mp4`,downloadUrl:`https://media.example.test/version-${i}.mp4?download=1`,size:1024,mirror:false,orientation:'vertical'});

function harness(app,width){
  const tasks=[],signals=[],timers=new Map(),cache=new Map(),storage=new Map();let timerId=0,now=0;
  const engine={createNativeClient:configuration=>({generateOpusVariations:async(file,options)=>{
    options.onPhase('native');options.onResume(tasks.length>0);
    return new Promise((resolve,reject)=>{const task={file,options,configuration,resolve,reject};tasks.push(task);
      options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true});});
  }})};
  const context={console,URL:{createObjectURL:()=>`blob:fixture-${Math.random()}`,revokeObjectURL:()=>{}},File,DOMException,AbortController,
    crypto:{subtle:{digest:async()=>new Uint8Array(32).buffer}},TextEncoder,performance:{now:()=>now},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},navigator:{},location:{protocol:'http:'},
    window:{innerWidth:width,setInterval:fn=>{timers.set(++timerId,fn);return timerId},clearInterval:id=>timers.delete(id)}};
  context.window.localStorage=context.localStorage;
  function load(filename){
    if(cache.has(filename))return cache.get(filename);
    const module={exports:{}};cache.set(filename,module.exports);
    const localRequire=name=>{
      if(name==='react'||name.startsWith('react/'))return appRequire(name);
      if(name==='@gm/reels')return load(path.join(shared,'ReelsPanel.tsx'));
      if(name==='@gm/reels/use-reels-job')return load(path.join(shared,'use-reels-job.ts'));
      if(name==='@/lib/signal')return {modeApp:()=>"fixture",signaler:(_jeton,evenement)=>{if(evenement==='duplicateur:ouvrir')signals.push(evenement);}};
      if(name.endsWith('.module.css'))return {__esModule:true,default:new Proxy({},{get:(_,k)=>String(k)})};
      if(name.endsWith('/opus-native'))return engine;
      if(name.endsWith('/downloads'))return {shouldPrefetchVideos:()=>false,createVideoFileCache:()=>({get:()=>null,prepare:async()=>[],progress:()=>({loadedBytes:0,totalBytes:0}),subscribe:()=>()=>{}}),downloadPreparedFiles:()=>{},canShareFiles:()=>false,downloadVideos:async()=>{},prepareShareFiles:async()=>[],sharePreparedFiles:async()=>"unavailable"};
      if(filename.includes('/'+app+'/')&&/^\.\//.test(name)&&!['./ReelsTab','./Logo'].includes(name))return {__esModule:true,default:()=>React.createElement('div',{'data-fixture':name})};
      if(name.startsWith('.')){const base=path.resolve(path.dirname(filename),name);return load(fs.existsSync(base+'.tsx')?base+'.tsx':base+'.ts');}
      throw new Error('Unexpected fixture import '+name);
    };
    vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,
      {...context,module,exports:module.exports,require:localRequire});
    cache.set(filename,module.exports);return module.exports;
  }
  return {App:load(path.join(toolsRoot,app,'src/components/App.tsx')).default,tasks,signals,tick:seconds=>{now+=seconds*1000;for(const fn of timers.values())fn()}};
}
const text=node=>typeof node==='string'?node:Array.isArray(node)?node.map(text).join(''):node?.children?node.children.map(text).join(''):'';
async function flush(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
  // Since 22/10 the Reels tab opens the maintained Duplicateur de Reels in its own
  // tab (button), instead of embedding the engine.
  for(const app of ['app_clippers','app_creatrices'])for(const width of [320,375,390]){
    const h=harness(app,width),props={prenom:'Fixture',creatrice:'Test',jeton:'fixture-person-a',tl:true,mym:false};let view;
    await act(async()=>{view=renderer.create(React.createElement(h.App,props));});
    const button=label=>view.root.findAllByType('button').find(b=>text(b)===label);
    const chooseTab=async label=>{await act(async()=>button(label).props.onClick());};
    await chooseTab('Reels');
    assert.equal(view.root.findAllByType('iframe').length,0);assert.equal(view.root.findAllByType('header').length,1);assert.equal(view.root.findAllByType('main').length,1);
    const link=view.root.findAllByType('a').find(a=>text(a).includes('Ouvrir le Duplicateur de Reels'));
    assert(link,'Duplicateur button');assert.equal(link.props.href,'https://duplicateur-de-reels.vercel.app/');
    assert.equal(link.props.target,'_blank');assert(/noopener/.test(link.props.rel));
    assert(text(view.toJSON()).includes('10 à 30 secondes'),'Import rules shown');
    assert.equal(h.signals.length,0);await act(async()=>link.props.onClick());assert.deepEqual(h.signals,['duplicateur:ouvrir']);
    await chooseTab('Drive');assert.equal(view.root.findAllByProps({'aria-label':'Duplicateur de Reels'}).length,0,'Panel only on the Reels tab');
    assert.equal(h.tasks.length,0,'No embedded montage');
    await act(async()=>view.unmount());
    cases.push({app,width,button:true,oneHeader:true,onePageMain:true,noEmbeddedEngine:true});
  }
  console.log(JSON.stringify({offline:true,kind:'React contract of the Reels tab button; not a visual pixel check',cases},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
