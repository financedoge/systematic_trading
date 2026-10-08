const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const html=fs.readFileSync(0,'utf8'),nodes=new Map(),handlers=new Map(),requests=[];
function node(id){if(!nodes.has(id)){let markup='';nodes.set(id,{value:'',textContent:'',disabled:false,
 get innerHTML(){return markup},set innerHTML(v){markup=v;if(id==='economic-series'||id==='economic-vintage')this.value=v.match(/value="([^"]+)"/)?.[1]||''}})}return nodes.get(id)}
let failed=false;
const series={id:'ICSA',name:'Claims',units:'Number',role:'Labor'},catalog={completed:2,expected:2,through:'2026-10-06',config:{series:[series],source_gaps:[{name:'National PMI',status:'Access pending',detail:'Regional surveys < national coverage'}]},snapshots:[{series:'ICSA',vintage:'2026-10-06',usable:true},{series:'ICSA',vintage:'2026-09-29',usable:true}],recorder:{enabled:true,failures:[]},limitations:['Date-level only']};
const data={series,vintage:'2026-10-06',usable:true,observations:[{date:'2026-09-05',value:'200000'},{date:'2026-09-12',value:null},{date:'2026-09-19',value:'210000'}],rows:3,missing:1,last:'2026-09-19',first_seen_at:'2026-10-07T12:00:00+00:00',archive_available_at:'2026-10-07T03:59:59.999999+00:00',receipt:{},policy:'test'};
const context=vm.createContext({document:{getElementById:node},window:{MarketHistory:{register:(k,v)=>handlers.set(k,v)}},URLSearchParams,
 fetch:async url=>{requests.push(url);return {ok:!failed,json:async()=>url.endsWith('/catalog')?catalog:data}}});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
async function settle(){for(let i=0;i<12;i++)await Promise.resolve()}
(async()=>{
 assert.equal(requests.length,0);handlers.get('economics')();await settle();
 assert.equal(requests.length,2);assert.match(requests[1],/series=ICSA&vintage=2026-10-06/);
 assert.equal(node('economic-export').disabled,false);assert.match(node('economic-summary').innerHTML,/Claims/);
 assert.match(node('economic-availability').textContent,/First captured by this app/);
 assert.match(node('economic-records').innerHTML,/Missing/);
 assert.match(node('economic-source-gaps').innerHTML,/National PMI/);
 assert.match(node('economic-source-gaps').innerHTML,/&lt; national coverage/);
 assert.equal((node('economic-chart').innerHTML.match(/M[0-9]/g)||[]).length,2); // break on missing observation
 node('economic-vintage').value='2026-09-29';node('economic-vintage').onchange();await settle();
 assert.match(requests.at(-1),/vintage=2026-09-29/);
 failed=true;node('economic-filters').onsubmit({preventDefault(){}});await settle();
 assert.equal(node('economic-export').disabled,true);assert.equal(node('economic-chart').textContent,'');
 assert.match(node('economic-status').textContent,/unavailable/);
 console.log('Economic loading, vintage choice, missing values and failure clearing passed');
})().catch(e=>{console.error(e);process.exit(1)});
