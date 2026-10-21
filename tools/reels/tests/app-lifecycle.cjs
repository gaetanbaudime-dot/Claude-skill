// Actual host App + shared UI/hook. Provider, usage signals and other tabs are
// fixtures. Width cases verify the mobile UI contract, not screenshot pixels.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const toolsRoot=path.resolve(__dirname,'../..'),shared=path.join(toolsRoot,'reels/src');
const appRequire=require('node:module').createRequire(path.join(toolsRoot,'app_clippers/package.json'));
const React=appRequire('react'),renderer=appRequire('react-test-renderer'),ts=appRequire('typescript'),{act}=renderer;
const cases=[];
const output=i=>({id:'fixture-'+i,index:i,name:`fixture-${i}.mp4`,captionPreset:['Deep Diver','Simple','PopLine','Soft Landing','Grow','Baby Steps'][i],url:`https://media.example.test/version-${i}.mp4`,downloadUrl:`https://media.example.test/version-${i}.mp4?download=1`,size:1024,mirror:false,orientation:'vertical'});

function harness(app,width){
  const tasks=[],timers=new Map(),cache=new Map(),storage=new Map();let timerId=0,now=0;
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
      if(name==='@/lib/signal')return {modeApp:()=>"fixture",signaler:()=>{}};
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
  return {App:load(path.join(toolsRoot,app,'src/components/App.tsx')).default,tasks,tick:seconds=>{now+=seconds*1000;for(const fn of timers.values())fn()}};
}
const text=node=>typeof node==='string'?node:Array.isArray(node)?node.map(text).join(''):node?.children?node.children.map(text).join(''):'';
async function flush(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
  for(const app of ['app_clippers','app_creatrices'])for(const width of [320,375,390]){
    const h=harness(app,width),props={prenom:'Fixture',creatrice:'Test',jeton:'fixture-person-a',tl:true,mym:false};let view;
    await act(async()=>{view=renderer.create(React.createElement(h.App,props),{createNodeMock:element=>element.type==='input'?{value:'',click:()=>{}}:null});});
    const button=label=>view.root.findAllByType('button').find(b=>text(b)===label);
    const chooseTab=async label=>{await act(async()=>button(label).props.onClick());};
    await chooseTab('Reels');
    assert.equal(view.root.findAllByType('iframe').length,0);assert.equal(view.root.findAllByType('header').length,1);assert.equal(view.root.findAllByType('main').length,1);
    assert(button('Choisir une vidéo'));assert(!text(view.toJSON()).includes('Plein écran'));assert(!text(view.toJSON()).includes('Un rush.Six variantes propres.'));
    const file=new File(['fixture'],'mon-rush-tres-long-pour-verifier-la-troncature.mp4',{type:'video/mp4'});
    await act(async()=>view.root.findByType('input').props.onChange({target:{files:[file]}}));
    assert.equal(button('Créer mes 6 Reels').props.disabled,true,'Metadata required before submitting');
    await act(async()=>view.root.findByType('video').props.onLoadedMetadata({currentTarget:{duration:181}}));
    assert.equal(button('Créer mes 6 Reels').props.disabled,true,'Three-minute limit blocks submission');
    await act(async()=>view.root.findByType('video').props.onLoadedMetadata({currentTarget:{duration:61}}));
    assert.equal(button('Créer mes 6 Reels').props.disabled,false);
    const start=button('Créer mes 6 Reels').props.onClick;
    await act(async()=>{start();start();await flush();});
    assert.equal(h.tasks.length,1,'Rapid clicks do not launch two jobs');assert.equal(button('Créer mes 6 Reels'),undefined,'Progress replaces upload form');
    const task=h.tasks[0],section=view.root.findByProps({'aria-label':'Duplicateur de Réel'});
    await chooseTab('Drive');assert.equal(section.props.hidden,true);
    await act(async()=>{task.options.onPhase('exports');task.options.onVariant(output(0));task.options.onVariant(output(1));h.tick(70);});
    await chooseTab(app==='app_clippers'?'Versements':'Stats');await chooseTab('Reels');
    assert.equal(view.root.findByProps({'aria-label':'Duplicateur de Réel'}),section,'Same native section remains mounted');
    assert.equal(h.tasks.length,1);assert(text(view.toJSON()).includes('2/6 prêts'));assert(text(view.toJSON()).includes('1 min 10 s'));
    assert.equal(view.root.findAllByProps({className:'resultCard'}).length,2,'Results emitted while hidden are retained');
    await act(async()=>{task.reject(new Error('Fixture interruption'));await flush();});
    assert(button('Reprendre ce montage'));assert.equal(view.root.findAllByProps({className:'resultCard'}).length,2);
    await act(async()=>{button('Reprendre ce montage').props.onClick();await flush();});
    assert.equal(h.tasks.length,2);assert.equal(view.root.findAllByProps({className:'resultCard'}).length,2,'Retry does not clear verified downloads');
    await act(async()=>{h.tasks[1].resolve({variants:Array.from({length:6},(_,i)=>output(i))});await flush();});
    assert.equal(view.root.findAllByProps({className:'resultCard'}).length,6);assert.equal(view.root.findByProps({role:'progressbar'}).props['aria-valuenow'],100);
    await act(async()=>{button('Choisir une nouvelle vidéo').props.onClick();});assert(button('Choisir une vidéo'));
    // Switching the existing app identity cannot expose the prior account's job.
    await act(async()=>view.root.findByType('input').props.onChange({target:{files:[file]}}));
    await act(async()=>view.root.findByType('video').props.onLoadedMetadata({currentTarget:{duration:30}}));
    await act(async()=>{button('Créer mes 6 Reels').props.onClick();await flush();});
    const old=h.tasks.at(-1);await act(async()=>{view.update(React.createElement(h.App,{...props,jeton:'fixture-person-b'}));await flush();});
    assert(old.options.signal.aborted);assert(button('Choisir une vidéo'));assert.equal(view.root.findAllByType('li').length,0);
    await act(async()=>view.unmount());
    cases.push({app,width,nativeComponent:true,oneHeader:true,onePageMain:true,jobSurvivesTabs:true,partialResultsRetained:true,noDuplicateSubmission:true,identityChangeClearsJob:true});
  }
  const css=fs.readFileSync(path.join(shared,'reels.module.css'),'utf8');
  assert(!/overflow(?:-y)?:\s*(auto|scroll)|100d?vh|position:\s*fixed/.test(css),'No nested viewport or scrolling page');
  assert(css.includes('grid-template-columns:minmax(0,1fr)'),'Results use one mobile column');assert(css.includes('min-height:44px'));
  console.log(JSON.stringify({offline:true,kind:'React lifecycle and mobile layout contract; not a visual pixel check',cases},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});

