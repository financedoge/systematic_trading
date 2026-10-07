const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
function boot(url){
 const nodes=new Map(),events=new Map(),calls=[],location={href:url},root={dataset:{}};
 const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,checked:false,attrs:{},setAttribute(k,v){this.attrs[k]=v}});return nodes.get(id)};
 const window={addEventListener:(name,fn)=>events.set(name,fn),dispatchEvent:event=>calls.push(['event',event.type,event.detail.enabled])};
 const context=vm.createContext({URL,location,window,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail}},
  document:{documentElement:root,getElementById:node},history:{replaceState:(_,__,url)=>{location.href=String(url)}}});
 vm.runInContext(input.controller.match(/<script>([\s\S]*?)<\/script>/)[1],context);
 for(const view of ['history','bars','raw'])window.MarketHistory.register(view,()=>calls.push(['load',view]));
 events.get('DOMContentLoaded')();
 return {node,window,calls,root,location};
}
let app=boot('http://localhost/platform/market-data-audit?view=history');
assert.equal(app.root.dataset.marketDebug,'false');assert.equal(app.node('market-debug').checked,false);
assert.equal(app.node('governed-panel').hidden,false);assert.equal(app.node('research-panel').hidden,true);
assert.deepEqual(app.calls,[['load','history']]);
app.node('market-bars-tab').onclick();assert.equal(app.node('market-bars-panel').hidden,false);
assert.equal(app.node('governed-panel').hidden,true);
app.node('market-debug').onchange({target:{checked:true}});
assert.equal(app.root.dataset.marketDebug,'true');assert.equal(new URL(app.location.href).searchParams.get('debug'),'1');
app.node('research-tab').onclick();assert.equal(app.window.MarketHistory.active,'raw');
assert.equal(app.node('research-panel').hidden,false);
app.node('market-debug').onchange({target:{checked:false}});
assert.equal(app.node('research-panel').hidden,true);assert.equal(app.node('governed-panel').hidden,false);
assert.equal(new URL(app.location.href).searchParams.has('debug'),false);
assert.deepEqual(app.calls.at(-1),['event','market-debug-change',false]);
for(const view of ['raw','research']){
 app=boot('http://localhost/?view='+view);assert.equal(app.window.MarketHistory.active,'history');
 assert(!app.calls.some(x=>x[1]==='raw'));
 app=boot('http://localhost/?view='+view+'&debug=1');assert.equal(app.window.MarketHistory.active,'raw');
}
app=boot('http://localhost/?view=usd');assert.equal(app.window.MarketHistory.active,'history');
app=boot('http://localhost/?view=governed');assert.equal(app.window.MarketHistory.active,'history');
// Public archive data is fetched only after explicit activation in Debug mode.
const nodes=new Map(),callbacks=new Map(),requests=[];
const archiveContext=vm.createContext({
 document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:''});return nodes.get(id)}},
 window:{MarketHistory:{register:(name,fn)=>callbacks.set(name,fn)}},
 fetch:async url=>{requests.push(url);return {ok:true,json:async()=>({datasets:[]})}},URLSearchParams,
});
vm.runInContext(input.archive.match(/<script>([\s\S]*?)<\/script>/)[1],archiveContext);
assert.equal(requests.length,0);callbacks.get('raw')();assert.equal(requests.length,1);
assert.match(input.page,/class="panel raw-section market-debug-only"/);
assert.match(input.page,/<th class="market-debug-only">Flags<\/th>/);
assert.match(input.page,/html:not\(\[data-market-debug="true"\]\) .market-debug-only\{display:none!important\}/);
assert.doesNotMatch(input.page,/id="usd-panel"|id="usd-tab"|id="governed-usd-select"|Audited Series|Recorded Bars/);
console.log('Debug navigation, legacy links, diagnostic visibility and lazy source loading passed');
