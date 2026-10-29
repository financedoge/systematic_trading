const el=id=>document.getElementById(id),pct=x=>x==null?'—':(100*x).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(3);
function rankTable(){const n=el('n').value,k=el('weight').value,a=DATA.rank.allocations[n][k],w=Object.fromEntries(a.symbols.map((s,i)=>[s,a.weights[i]]));let effective=1/a.weights.reduce((s,x)=>s+x*x,0);
 el('allocation').textContent=`Historical indicative preview ${DATA.rank.asof}. ${a.symbols.length} selected sleeves; effective capital breadth ${effective.toFixed(1)}; indicated ETF exposure ${pct(a.invested)}, sleeve cash ${pct(a.cash)}. Largest sleeve ${pct(Math.max(...a.weights))}. N is not optimized; no portfolio performance is implied.`;
 el('rankrows').innerHTML=DATA.rank.rows.map(r=>`<tr class="${w[r.symbol]!=null?'selected':''}"><td><button data-symbol="${r.symbol}">${r.rank} · ${r.symbol}</button></td><td>${pct(r.short_return)}</td><td>${num(r.short_sharpe)}</td><td>${pct(r.long_return)}</td><td>${num(r.long_sharpe)}</td><td>${pct(r.volatility)}</td><td>${(100*r.score).toFixed(1)}</td><td>${r.active?'Invested':'Cash'}</td><td>${w[r.symbol]!=null?'Yes':'—'}</td><td>${pct(w[r.symbol]||0)}</td><td>${pct(r.active?(w[r.symbol]||0):0)}</td></tr>`).join('');
}
const symbols=()=>Object.keys(DATA.charts).filter(k=>k.endsWith('_'+el('era').value)).map(k=>k.split('_')[0]).sort();
let indices=[],pin=null;
function c(){return DATA.charts[el('etf').value+'_'+el('era').value]}
function choose(full=true){const old=el('etf').value,ss=symbols();el('etf').innerHTML=ss.map(s=>`<option>${s}</option>`).join('');el('etf').value=ss.includes(old)?old:ss[0];if(full){let q=c();el('from').value=q.days[0];el('to').value=q.days.at(-1)}pin=null;render()}
function render(){const q=c(),key=el('etf').value+'_'+el('era').value;indices=q.days.map((d,i)=>d>=el('from').value&&d<=el('to').value?i:-1).filter(i=>i>=0);
 el('parameters').textContent=JSON.stringify(DATA.models[key],null,2);
 if(indices.length<2){el('chart').innerHTML='<text x="40" y="50">No complete date interval.</text>';el('chartmetrics').textContent='Select at least two available sessions.';el('trades').innerHTML='';return}
 const first=indices[0],last=indices.at(-1),vals=indices.map(i=>q.nav[i]).filter(x=>x!=null);let ret=vals.length>1?vals.at(-1)/vals[0]-1:null;
 el('chartmetrics').textContent=`${el('etf').value}: ${q.days[first]}–${q.days[last]}. Selected-interval account return ${pct(ret)} (existing account, not restarted). Training cutoff ${DATA.models[key].training_end}. Full daily model; 5 bp per side; next-open fills.`;
 const x=j=>75+1090*j/(indices.length-1),panels=[[25,290],[320,415],[450,555],[585,680],[725,905]];let svg='';
 function panel(bounds,label){let [lo,hi]=bounds;svg+=`<rect x="75" y="${lo}" width="1090" height="${hi-lo}" fill="white" stroke="#cfdee3"/><text x="80" y="${lo+16}" font-size="13">${label}</text>`}
 function line(values,bounds,color,min,max){let [lo,hi]=bounds,path='',on=false;const y=v=>hi-10-(hi-lo-35)*(v-min)/(max-min||1);indices.forEach((i,j)=>{const v=values[i];if(v==null||!Number.isFinite(v)){on=false;return}path+=(on?'L':'M')+x(j).toFixed(1)+','+y(v).toFixed(1);on=true});svg+=`<path d="${path}" fill="none" stroke="${color}" stroke-width="1.4"/>`;return y}
 const prices=indices.flatMap(i=>[q.high[i],q.low[i],q.stop[i]]).filter(v=>v!=null),pmin=Math.min(...prices),pmax=Math.max(...prices);panel(panels[0],'Adjusted OHLC / close · red closing boundary · green buys / red sells');const py=line(q.close,panels[0],'#244c61',pmin,pmax);line(q.stop,panels[0],'#ba465a',pmin,pmax);
 indices.forEach((i,j)=>{svg+=`<path d="M${x(j)},${py(q.high[i])}V${py(q.low[i])}" stroke="#8da2b1" opacity=".55"/>`});
 q.fills.filter(f=>f.day>=q.days[first]&&f.day<=q.days[last]).forEach(f=>{const j=indices.findIndex(i=>q.days[i]===f.day);if(j<0)return;const xx=x(j),yy=py(f.price),b=f.side==='buy';svg+=`<path d="M${xx-4},${yy+(b?4:-4)}L${xx},${yy+(b?-4:4)}L${xx+4},${yy+(b?4:-4)}Z" fill="${b?'#008776':'#ba465a'}"/>`});
 panel(panels[1],'Audited raw ETF share volume');let vm=Math.max(...indices.map(i=>q.volume[i]));indices.forEach((i,j)=>{let h=55*q.volume[i]/vm;svg+=`<rect x="${x(j)}" y="${405-h}" width="${Math.max(.5,1000/indices.length)}" height="${h}" fill="#94a9b4"/>`});
 panel(panels[2],'Fast HMM: green up / gold neutral / red down');[['fast_up','#008776'],['neutral','#b29538'],['fast_down','#ba465a']].forEach(([k,col])=>line(q[k],panels[2],col,0,1));
 panel(panels[3],'Slow slope: green up / red down');[['slow_up','#008776'],['slow_down','#ba465a']].forEach(([k,col])=>line(q[k],panels[3],col,0,1));
 panel(panels[4],'Strategy account NAV (initial 100)');line(q.nav,panels[4],'#008776',Math.min(...vals),Math.max(...vals));
 for(let j=0;j<5;j++){let a=Math.round(j*(indices.length-1)/4);svg+=`<text x="${x(a)}" y="930" font-size="12" text-anchor="middle">${q.days[indices[a]]}</text>`}
 el('chart').innerHTML=svg;
 el('trades').innerHTML=q.trades.filter(t=>t.entry_date<=q.days[last]&&(!t.exit_date||t.exit_date>=q.days[first])).map(t=>`<tr><td>${t.entry_date}</td><td>${t.exit_date||'Open'}</td><td>${t.entry.toFixed(2)}</td><td>${t.exit_price==null?'—':t.exit_price.toFixed(2)}</td><td>${pct(t.net_return)}</td><td>${t.exit_reason||'Holding'}</td><td>${pct(t.initial_risk_fraction)}</td></tr>`).join('');
}
function at(event){let rect=el('chart').getBoundingClientRect();let f=((event.clientX-rect.left)/rect.width*1200-75)/1090;return indices[Math.max(0,Math.min(indices.length-1,Math.round(f*(indices.length-1))))]}
el('n').value='15';el('weight').value='equal';el('era').value='late';el('etf').value='CORN';rankTable();choose();
el('n').addEventListener('change',rankTable);el('weight').addEventListener('change',rankTable);
el('rankrows').addEventListener('click',e=>{const s=e.target.dataset?.symbol;if(s){el('era').value='late';choose();el('etf').value=s;choose();el('chart').scrollIntoView?.({behavior:'smooth'})}});
el('era').addEventListener('change',()=>choose());el('etf').addEventListener('change',()=>choose());el('full').addEventListener('click',()=>choose());
el('weakest').addEventListener('click',()=>{el('etf').value=DATA.weakest[el('era').value];choose()});
for(const k of ['from','to'])el(k).addEventListener('change',()=>{pin=null;render()});
el('chart').addEventListener('mousemove',e=>{let i=at(e);if(i==null)return;let q=c();el('readout').textContent=`${q.days[i]} · O ${q.open[i].toFixed(2)} H ${q.high[i].toFixed(2)} L ${q.low[i].toFixed(2)} C ${q.close[i].toFixed(2)} · raw volume ${q.volume[i].toLocaleString()} · boundary ${q.stop[i]==null?'—':q.stop[i].toFixed(2)} · fast up ${pct(q.fast_up[i])} / down ${pct(q.fast_down[i])} · NAV ${q.nav[i]==null?'—':q.nav[i].toFixed(2)}`});
el('chart').addEventListener('click',e=>{let i=at(e);if(i==null)return;if(pin==null){pin=i;el('readout').textContent='Start '+c().days[i]+' selected; click the other endpoint.'}else{el('from').value=c().days[Math.min(i,pin)];el('to').value=c().days[Math.max(i,pin)];pin=null;render()}});
