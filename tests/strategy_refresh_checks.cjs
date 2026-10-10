const assert = require('node:assert/strict');
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const settle = () => new Promise(resolve => setImmediate(resolve));
const script = html => html.match(/<script>([\s\S]*?)<\/script>/)[1];

async function reportChecks() {
  const banner = {textContent: ''}, timers = [];
  let reloads = 0, requests = 0, reject = false;
  let payload = {strategy_serving_version:'v1', strategy_freshness_message:'NAV through September 25',
    research_job:'tracked-strategies', compute:{completed:['one'],resources:{jobs:5}}, errors:{}};
  const context = vm.createContext({document:{getElementById:() => banner},
    window:{location:{reload:() => reloads++}, setTimeout:fn => timers.push(fn)},
    fetch:async () => {requests++; if(reject) throw new Error('temporary outage');
      return {ok:true,json:async () => payload};}});
  vm.runInContext(script(input.report), context);
  await settle();
  assert.equal(requests, 1);
  assert.equal(timers.length, 1);
  assert.equal(reloads, 0);
  assert.match(banner.textContent, /Calculating strategies \(1\/5 runs complete\)/);
  assert.match(banner.textContent, /NAV through September 25/);
  reject = true;
  await timers.shift()();
  assert.equal(timers.length, 1);
  assert.match(banner.textContent, /retrying automatically/);
  assert.equal(reloads, 0);
  reject = false;
  payload = {...payload, strategy_serving_version:'v2'};
  await timers.shift()();
  assert.equal(reloads, 1);
  assert.equal(timers.length, 0); // Never reload because of an input-only change.
}

async function catalogChecks() {
  const elements = new Map(), timers = [];
  const get = id => {
    if(!elements.has(id)) elements.set(id,{textContent:'',innerHTML:''});
    return elements.get(id);
  };
  let reject=false;
  let payload={strategies:[{strategy_id:'tracked',name:'Tracked',lifecycle:'monitored',artifact_end_date:'2026-09-25',
    return_1m:.0123,return_ytd:-.025,return_1y:0}],
    warnings:['Waiting for FX']};
  const context=vm.createContext({document:{getElementById:get,querySelectorAll:() => [],addEventListener:()=>{}},
    window:{setTimeout:fn => timers.push(fn)},
    fetch:async () => {if(reject) throw new Error('offline');return {ok:true,json:async () => payload};}});
  vm.runInContext(script(input.catalog), context);
  await settle();
  assert.match(get('strategy-list').innerHTML,/2026-09-25/);
  assert.match(get('strategy-list').innerHTML,/<td class="num">1.23%<\/td><td class="num">-2.50%<\/td><td class="num">0.00%<\/td>/);
  for(const label of ['1M performance','YTD performance','1Y performance'])assert.ok(input.catalog.includes(label));
  assert.match(get('catalog-note').textContent,/Waiting for FX/);
  assert.equal(timers.length,1);
  reject=true;
  await timers.shift()();
  assert.match(get('strategy-list').innerHTML,/2026-09-25/); // Keep usable rows through a retry.
  reject=false;
  payload={strategies:[{strategy_id:'tracked',name:'Tracked',lifecycle:'monitored',artifact_end_date:'2026-09-29'}]};
  await timers.shift()();
  assert.match(get('strategy-list').innerHTML,/2026-09-29/);
  assert.match(get('strategy-list').innerHTML,/<td class="num">n\/a<\/td><td class="num">n\/a<\/td><td class="num">n\/a<\/td>/);
  assert.doesNotMatch(get('catalog-note').textContent,/Waiting for FX/);
  vm.runInContext("state.lifecycle='archived'",context);
  await timers.shift()();
  assert.match(get('strategy-list').innerHTML,/No strategies in this lifecycle/); // Preserve filter.
  assert.match(get('strategy-list').innerHTML,/colspan="11"/);
  assert.equal(timers.length,1);
}

(async()=>{await reportChecks(); await catalogChecks();})().catch(error=>{console.error(error);process.exit(1);});
