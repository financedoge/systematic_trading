/* Source-level report tests, without launching or controlling a browser.
   This checks formatter/data contracts and control handlers, not visual layout. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = 'research/gld-breakout-drilldown-20261018-v1/';
class Element {
  constructor(id) {this.id=id;this.innerHTML='';this.textContent='';this.value='';this.checked=false;this.style={};this.children=[];this.attrs={};}
  setAttribute(k,v) {this.attrs[k]=v;}
  appendChild(e) {this.children.push(e);return e;}
  addEventListener() {}
  getBoundingClientRect() {return {width:1250,left:0};}
}
const html=fs.readFileSync(root+'index.html','utf8');
const elements=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element(m[1])]));
elements.boxes.checked=true;
elements.price.parentElement=new Element('plot');
const context=vm.createContext({window:{},document:{getElementById:id=>{assert.ok(elements[id],id);return elements[id];},createElementNS:()=>new Element(),querySelectorAll:()=>[]},ResizeObserver:class {observe() {}},console});
vm.runInContext(fs.readFileSync(root+'data.js','utf8'),context);
const code=[...html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');
vm.runInContext(code,context);
assert.equal(elements.chartError.textContent,'');
assert.match(elements.state.innerHTML,/2024-02-29/);
assert.doesNotMatch(html,/monthly/i);
vm.runInContext("select(atDate('2026-10-16'))",context);
assert.match(elements.stops.innerHTML,/357\.4497/);
assert.match(elements.stops.innerHTML,/431\.9793/);
assert.match(elements.selectionExplanation.innerHTML,/Every daily variant failed/);
assert.match(elements.ISexplanation.innerHTML,/22,885 distinct evaluations/);
vm.runInContext("select(atDate('2024-10-01'))",context);
assert.match(elements.state.innerHTML,/[1-9][\d,]* adjusted units/);
assert.match(elements.state.innerHTML,/exit time no follow through/);
assert.match(elements.calculation.textContent,/249\.802099/);
vm.runInContext("select(atDate('2024-10-02'))",context);
assert.match(elements.state.innerHTML,/0 adjusted units/);
assert.match(elements.state.innerHTML,/exit_all/);
vm.runInContext("select(atDate('2024-02-29'));focus()",context);
assert.match(elements.rangeContext.innerHTML,/2023-02-28 through 2024-02-28/);
assert.match(elements.rangeContext.innerHTML,/178\.06–\$187\.57/);
assert.equal(elements.from.value,'2023-02-13');
elements.full.onclick();elements.oos.onclick();elements.next.onclick();elements.prev.onclick();
elements.allEpisodes.checked=true;elements.allEpisodes.onchange();
assert.match(elements.episodes.innerHTML,/R1<\/strong>/);
assert.equal(elements.chartError.textContent,'');
console.log('Report source/data/control-handler checks passed; browser rendering not exercised.');
