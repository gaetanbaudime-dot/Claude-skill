const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const appRequire=require('node:module').createRequire(path.join(__dirname,'../../app_clippers/package.json'));
const ts = appRequire('typescript');
const React = appRequire('react');
const {renderToStaticMarkup} = appRequire('react-dom/server');
function load(relative, dependencies={}){
  const module={exports:{}};
  const compiled=ts.transpileModule(fs.readFileSync(path.join(__dirname,'..',relative),'utf8'),{compilerOptions:{
    module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  vm.runInNewContext(compiled,{module,exports:module.exports,require:name=>dependencies[name]||appRequire(name)});
  return module.exports;
}
const model=load('src/lib/processing-status.ts');
const Component=load('src/components/ProcessingStatus.tsx',{'../lib/processing-status':model,'../reels.module.css':{default:new Proxy({},{get:(_,name)=>String(name)})}}).default;
function main(){
  let checks=0;
  const yes=(v,m)=>{assert(v,m);checks++};
  const status=(seconds,options={})=>model.processingStatus(options.stage||'processing',options.phase||'native',seconds,
    options.resuming===undefined?false:options.resuming,options.count||0);
  const initial=status(0);yes(initial.estimate.includes('4–5 min'));yes(initial.width===0&&!initial.complete);
  let simulatedClock=7000;const started=simulatedClock;
  simulatedClock+=90000;
  const elapsed=model.elapsedSince(started,simulatedClock),ninety=status(elapsed);
  yes(elapsed===90);yes(ninety.elapsed==='1 min 30 s');yes(ninety.estimate.includes('3–4 min'));yes(ninety.width===30);
  yes(model.elapsedSince(100,50)===0);
  for(const seconds of [239,240,299]){
    const s=status(seconds);yes(!s.indeterminate);yes(s.width<100);yes(!s.estimate.includes('0 min'));
  }
  for(const seconds of [300,301,600,1800]){
    const s=status(seconds);yes(s.indeterminate);yes(s.estimate.includes('toujours en cours'));yes(s.estimate.includes('indéterminée'));yes(!s.complete);
  }
  const resumed=status(180,{resuming:true});yes(resumed.indeterminate);yes(!resumed.showReference);yes(resumed.timingLabel.includes('reprise'));yes(!/\d+.*min/.test(resumed.estimate));
  const checking=status(0,{resuming:null,phase:'checking'});yes(checking.indeterminate);yes(checking.estimate.includes('Recherche'));
  const partial=status(180,{phase:'exports',count:3});yes(partial.count===3&&!partial.complete);yes(partial.title==='Exports et finitions');
  const incomplete=status(400,{stage:'done',count:5});yes(!incomplete.complete&&!incomplete.active);yes(incomplete.title==='Montage incomplet');
  const error=status(190,{stage:'error',count:2});yes(!error.active&&!error.complete);yes(error.estimate.includes('interrompu'));yes(!error.estimate.includes('en cours'));yes(error.elapsed==='3 min 10 s');
  const done=status(306,{stage:'done',count:6});yes(done.complete&&done.width===100&&!done.active);yes(done.count===6);yes(!done.estimate.includes('prévu'));
  const allButNotConfirmed=status(306,{count:6});yes(!allButNotConfirmed.complete,'Only confirmed completion produces 100%');
  for(const phase of ['checking','upload','preparing','native','variants','exports','cached'])yes(!!model.PHASE_LABELS[phase]);
  for(const props of [
    {stage:'processing',phase:'native',elapsedSeconds:90,resuming:false,readyCount:0},
    {stage:'processing',phase:'exports',elapsedSeconds:600,resuming:false,readyCount:3},
    {stage:'processing',phase:'cached',elapsedSeconds:5,resuming:true,readyCount:0},
    {stage:'error',phase:'exports',elapsedSeconds:200,resuming:false,readyCount:2},
    {stage:'done',phase:'exports',elapsedSeconds:306,resuming:false,readyCount:6},
  ]){
    const html=renderToStaticMarkup(React.createElement(Component,props));
    yes(html.includes('role="progressbar"'));yes(html.includes('progressHeading'));yes(html.includes('elapsed'));yes(html.includes('estimate'));
    yes(!html.includes('99%'));yes(html.includes(`${props.readyCount}/6`));
    if(props.stage==='done')yes(html.includes('aria-valuenow="100"'));
    else yes(!html.includes('aria-valuenow='),'No invented completion percentage');
    if(props.readyCount>0&&props.readyCount<6)yes(html.includes(`${props.readyCount}/6 prêts`));
    if(props.elapsedSeconds>=300&&props.stage==='processing')yes(html.includes('indeterminate'));
    if(props.stage==='error')yes(!html.includes('indeterminate'));
  }
  return checks;
}
module.exports=main;
if(require.main===module)console.log(JSON.stringify({offline:true,processingStatusChecks:main()}));
