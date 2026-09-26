const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
for(const page of input.pages){
  assert.equal((page.match(/id="time-chart-navigation"/g)||[]).length,1);
  for(const match of page.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
}
class Element {
  constructor(){this.children=[];this.attrs={};this.events={};this.dataset={};this.capture=new Set();this.classList={add(){},remove(){}}}
  setAttribute(k,v){this.attrs[k]=String(v)}
  appendChild(n){this.children.push(n);n.parent=this;return n}
  before(n){this.toolbar=n}
  addEventListener(k,f){this.events[k]=f}
  focus(){}
  setPointerCapture(id){this.capture.add(id)}
  hasPointerCapture(id){return this.capture.has(id)}
  releasePointerCapture(id){this.capture.delete(id)}
  remove(){this.parent.children=this.parent.children.filter(x=>x!==this)}
  querySelector(q){if(q==='svg')return this.svg;return this.svg?.children.find(x=>x.attrs.class===q.slice(1))||null}
  getScreenCTM(){return {inverse:()=>({scale:2,dx:10,dy:20})}}
}
const elements=new Map(),get=id=>{if(!elements.has(id)){const e=new Element();e.svg=new Element();elements.set(id,e)}return elements.get(id)};
let frameId=0;const frames=new Map();
const context=vm.createContext({assert,document:{getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element()},
  DOMPoint:class {constructor(x,y){this.x=x;this.y=y}matrixTransform(m){return{x:(this.x-m.dx)/m.scale,y:(this.y-m.dy)/m.scale}}},
  requestAnimationFrame:f=>{frames.set(++frameId,f);return frameId},cancelAnimationFrame:id=>frames.delete(id)});
vm.runInContext(input.helper.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],context);
const nav=context.ChartNavigation,base=Date.UTC(2020,0,1),day=86400000;
let rows=Array.from({length:11},(_,i)=>({t:base+i*day,value:100+i})),view,redraws=0,key='A';
const draw=()=>{redraws++;view=nav.view('prices',rows,p=>p.t,draw,{left:50,right:950,top:20,bottom:200},{key});get('prices').svg=new Element()};
const host=get('prices');
function event(type,x,extra={}){host.events[type]({clientX:x*2+10,clientY:220,button:0,pointerId:1,preventDefault(){},...extra})}
const button=action=>host.toolbar.children.find(x=>x.dataset.navigationAction===action);
draw();assert.equal(view.rows.length,11);assert.deepEqual(Array.from(view.range),[base,base+10*day]);
// CSS-scaled SVG, reverse selection, small clicks and pointer replacement.
event('pointerdown',770);event('pointermove',230);event('pointerup',230);
assert.deepEqual(Array.from(view.range),[base+2*day,base+8*day]);assert.equal(view.rows[0].value,102);
event('pointerdown',500);event('pointerup',501);assert.equal(view.rows.length,7);
// Pan drags retain width, clamp to the full domain and capture on stable host.
button('pan').onclick();event('pointerdown',500);event('pointermove',950);
for(const f of frames.values())f();frames.clear();assert(host.hasPointerCapture(1));event('pointerup',950);
assert.deepEqual(Array.from(view.range),[base,base+6*day]);
// Escape and cancellation undo a live pan.
event('pointerdown',500);event('pointermove',100);for(const f of frames.values())f();frames.clear();
host.events.keydown({key:'Escape',preventDefault(){}});assert.deepEqual(Array.from(view.range),[base,base+6*day]);
event('pointerdown',500);event('pointermove',100);event('pointercancel',100);assert.deepEqual(Array.from(view.range),[base,base+6*day]);
// Refresh expands the available domain but keeps the selected window.
rows.push({t:base+11*day,value:111});draw();assert.equal(view.range[1],base+6*day);
host.events.keydown({key:'ArrowRight',preventDefault(){}});assert.equal(view.range[1]-view.range[0],6*day);
button('reset').onclick();assert.equal(view.rows.length,12);
button('zoom').onclick();event('pointerdown',230);event('pointerup',770);
const selected=Array.from(view.range);event('pointerdown',500,{shiftKey:true});event('pointerup',600);assert.equal(view.range[1]-view.range[0],selected[1]-selected[0]);
// Switching underlying resets; a singleton and empty series remain safe.
key='B';draw();assert.equal(view.rows.length,12);rows=[rows[0]];draw();event('pointerdown',500);assert.equal(host.capture.size,0);
rows=[];draw();assert.equal(view.range,null);assert.equal(button('reset').disabled,true);
assert(redraws>8);
// Independent charts and intraday precision; no rounding to whole dates.
let minuteView;const minutes=[0,60000,120000].map(t=>({t:base+t}));
const minuteDraw=()=>minuteView=nav.view('minutes',minutes,p=>p.t,minuteDraw,{left:0,right:100,top:0,bottom:200},{intraday:true});minuteDraw();
const minuteHost=get('minutes');minuteHost.events.pointerdown({clientX:10,clientY:100,button:0,pointerId:2,preventDefault(){}});
minuteHost.events.pointerup({clientX:110,clientY:100,button:0,pointerId:2,preventDefault(){}});
assert.equal(minuteView.range[1]-minuteView.range[0],60000);assert.equal(view.range,null);
// Exercise the actual archived chart adapter. Its denominator stays at the full-series origin.
const archived=input.pages[1].match(/function chartSvg[\s\S]*?(?=function comparisonTable)/)[0];
let selectedRange=[base+day,base+2*day];
const archivedContext=vm.createContext({ChartNavigation:{view:(id,rows,time)=>({rows,range:selectedRange})},document:{getElementById:get},esc:String});
vm.runInContext(archived,archivedContext);
const dates=['2020-01-01','2020-01-02','2020-01-03'];
const strategy=dates.map((trade_date,i)=>({trade_date,nav_cnh:[100,200,300][i]}));
const benchmark=dates.map((trade_date,i)=>({trade_date,nav_cnh:[100,100,100][i]}));
const svg=archivedContext.chartSvg(strategy,benchmark);assert.doesNotMatch(svg,/NaN|undefined|Infinity/);
assert.match(svg,/2020-01-02/);assert.match(svg,/2020-01-03/);
// Zoomed strategy begins well above the benchmark, not rebased to meet it.
const sy=Number(svg.match(/class="line" d="M [\d.]+ ([\d.]+)/)[1]);const by=Number(svg.match(/class="bench" d="M [\d.]+ ([\d.]+)/)[1]);
assert(sy<by-50);
// The exported report uses full-history index values and skips off-window drawdowns.
const reportSource=input.pages[3].match(/function svgEl[\s\S]*?(?=function renderMetrics)/)[0];
const reportNodes=new Map();const reportElement=id=>{if(!reportNodes.has(id)){const e=new Element();e.clientWidth=1000;e.clientHeight=600;reportNodes.set(id,e)}return reportNodes.get(id)};
const reportContext=vm.createContext({document:{getElementById:reportElement,createElementNS:()=>new Element()},
  ChartNavigation:{view:(id,rows,time)=>({rows:rows.filter(p=>time(p)>=selectedRange[0]&&time(p)<=selectedRange[1]),range:selectedRange})},
  report:{chart:dates.map((date,i)=>({date,navIndex:[100,200,300][i],weights:{SPY:1},benchmarkIndex:100})),allocationOrder:['SPY'],colors:{SPY:'#123456'},drawdownPeriods:[{start:'2018-01-01',end:'2018-03-01',depth:-.2}]},
  currentBenchmark:p=>({index:p.benchmarkIndex}),benchmarkColor:'#green',strategyColor:'#blue',fmtNum:v=>String(v)});
vm.runInContext(reportSource,reportContext);reportContext.renderChart();
const reportSvg=reportElement('chartSvg');assert(!reportSvg.children.some(e=>e.attrs.fill==='#b91c1c'));
const navPath=reportSvg.children.find(e=>e.attrs.stroke==='#blue'),benchPath=reportSvg.children.find(e=>e.attrs.stroke==='#green');
assert(Number(navPath.attrs.d.match(/^M[\d.]+,([\d.]+)/)[1])<Number(benchPath.attrs.d.match(/^M[\d.]+,([\d.]+)/)[1])-50);
assert(reportSvg.children.some(e=>e.textContent==='2020-01-02'));
console.log('All page scripts parse; shared navigation and archived normalization checks passed');
