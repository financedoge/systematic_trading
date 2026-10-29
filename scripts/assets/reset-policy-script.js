const $=id=>document.getElementById(id), names={continuous:'A · Continuous learning',loss_reset:'B · Reset after losses / drawdown',regime_reset:'C · Also reset on HMM transition'};
let current,visible=[],firstClick=null;
const percent=x=>x==null?'unavailable':(100*x).toFixed(2)+'%';
function symbols(){return Object.keys(DATA.charts).filter(k=>k.endsWith('_'+$('era').value)).map(k=>k.split('_')[0]).sort()}
function selectCase(reset=false){
 const all=symbols(),old=$('etf').value;$('etf').innerHTML=all.map(s=>`<option>${s}</option>`).join('');
 $('etf').value=all.includes(old)?old:DATA.weakest[$('era').value].symbol;
 current=DATA.charts[$('etf').value+'_'+$('era').value];
 if(reset||!$('from').value){$('from').value=current.days[0];$('to').value=current.days.at(-1)}
 render();
}
function render(){
 const c=current,a=c.arms[$('arm').value];visible=c.days.map((_,i)=>i).filter(i=>c.days[i]>=$('from').value&&c.days[i]<=$('to').value);
 const row=DATA.rows.find(r=>r.symbol===$('etf').value&&r.era===$('era').value&&r.arm===$('arm').value);
 $('metrics').textContent=`${names[row.arm]} | return ${percent(row.cumulative)} · Sharpe ${row.sharpe.toFixed(3)} · Calmar ${row.calmar==null?'—':row.calmar.toFixed(2)} · max drawdown ${percent(-row.maxdd)} · exposure ${percent(row.exposure)} · ${row.closed_trades} closed trades · ${row.changes} parameter changes · ${row.reset_count} full resets · ${row.empty_evidence_sessions} sessions without fresh outcomes · frozen return ${percent(row.frozen_cumulative)} · buy-and-hold ${percent(row.buyhold)}`;
 $('parameters').textContent=`Training through ${c.calibration.training_end}; winner σ = ${percent(c.calibration.winner_sigma)}. Base parameters: ${JSON.stringify(c.parameters)}. No health pause; reset clears evidence but does not liquidate or force re-entry. Underlying trend filters retain their original fitted parameters. Context before evaluation is not a trading result.`;
 $('weakestNote').textContent=`Weakest C case for ${$('era').value}: ${DATA.weakest[$('era').value].symbol}, ${percent(DATA.weakest[$('era').value].cumulative)} net. Criterion: lowest primary net return, excluding BIL. C is declared in advance; no retrospective per-ETF winner selection.`;
 $('grid').innerHTML=c.grid.map((p,j)=>`<tr><td>${j}</td><td>${p.entry.toFixed(2)}</td><td>${p.exit.toFixed(2)}</td><td>${p.aligned_exit.toFixed(2)}</td><td>${p.tight.toFixed(2)}</td><td>${p.wide.toFixed(2)}</td></tr>`).join('');
 const trades=a.trades.filter(t=>t.entry_date<=$('to').value&&(!t.exit_date||t.exit_date>=$('from').value));
 $('trades').innerHTML=trades.map(t=>`<tr><td>${t.entry_date}</td><td>${t.exit_date||'Open'}</td><td>${t.entry_policy}</td><td>${t.exit_policy??'—'}</td><td>${percent(t.net_return)}</td><td>${t.exit_reason||'—'}</td></tr>`).join('');
 $('events').innerHTML=a.events.filter(e=>e.day>=$('from').value&&e.day<=$('to').value).map(e=>`<tr><td>${e.day}</td><td>${e.old_policy} → ${e.policy}</td><td>${e.reason.replaceAll('_',' ')}</td><td>${e.reset?'Yes':'No'}</td><td>${e.posterior_mean.toFixed(3)}</td><td>${percent(e.win_probability)}</td><td>${e.effective_count.toFixed(2)}</td></tr>`).join('');
 if(!visible.length){$('chart').innerHTML='<text x="60" y="80">No sessions in this date range.</text>';return}
 const left=85,right=1170,range=visible.length-1,xx=j=>left+j/Math.max(1,range)*(right-left);
 let out='<rect width="1200" height="1140" fill="white"/>';
 const text=(x,y,s,fill='#335268',size=12)=>`<text x="${x}" y="${y}" fill="${fill}" font-size="${size}">${s}</text>`;
 const lines=(arrays,top,bottom,label,continuous=null)=>{
  const vals=arrays.flatMap(v=>visible.map(i=>v.data[i])).filter(v=>v!=null&&Number.isFinite(v));
  let min=continuous?continuous[0]:Math.min(...vals),max=continuous?continuous[1]:Math.max(...vals);
  if(!vals.length&&!continuous){min=0;max=1}if(max===min)max=min+1;
  if(!continuous){const pad=(max-min)*.07;min-=pad;max+=pad}
  const yy=v=>bottom-(v-min)/(max-min)*(bottom-top);out+=text(left,top-12,label);
  for(let k=0;k<4;k++){let v=min+(max-min)*k/3,y=yy(v);out+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#e4ebef"/>`+text(5,y+4,v.toFixed(2))}
  for(const s of arrays){let path='',active=false;visible.forEach((i,j)=>{const v=s.data[i];if(v==null||!Number.isFinite(v)){active=false;return}path+=(active?'L':'M')+xx(j).toFixed(2)+','+yy(v).toFixed(2);active=true});out+=`<path d="${path}" stroke="${s.color}" stroke-width="1.7" fill="none"/>`}
  return yy;
 };
 const py=lines([{data:c.close,color:'#173d54'},{data:a.stop,color:'#b64f61'}],40,330,'Adjusted close (navy), adopted protection (red), buys / sells (green / red triangles)');
 for(const t of a.trades)for(const [day,price,buy] of [[t.entry_date,t.entry,true],[t.exit_date,t.exit_price,false]]){const j=visible.findIndex(i=>c.days[i]===day);if(j<0)continue;const x=xx(j),y=py(price),sign=buy?1:-1;out+=`<polygon points="${x},${y-6*sign} ${x-5},${y+4*sign} ${x+5},${y+4*sign}" fill="${buy?'#008675':'#ba465b'}"/>`}
 for(const e of a.events.filter(e=>e.reset)){const j=visible.findIndex(i=>c.days[i]===e.day);if(j>=0)out+=`<line x1="${xx(j)}" x2="${xx(j)}" y1="40" y2="330" stroke="#c58b25" stroke-dasharray="3 5"/>`}
 lines([{data:c.volume.map(v=>v==null?null:v/1e6),color:'#819cad'}],380,465,'Audited raw ETF share volume (millions)');
 const hide=v=>v.map((x,i)=>c.days[i]>=c.evaluation_start?x:null);
 lines([{data:hide(c.fast_up),color:'#008675'},{data:hide(c.hmm_change),color:'#b64f61'},{data:a.entry_threshold,color:'#c58b25'}],515,630,'Fast up (green), HMM transition probability (red), current entry threshold (amber)',[0,1]);
 lines([{data:a.effective_count,color:'#8154a5'}],680,780,'Effective observations for the selected policy; amber marks above = full posterior reset');
 lines([{data:c.arms.continuous.nav,color:'#9da9b4'},{data:c.arms.loss_reset.nav,color:'#ce9229'},{data:c.arms.regime_reset.nav,color:'#008675'}],830,1040,'NAV: A grey · B amber · C green · initial cash 100');
 for(let k=0;k<7;k++){const j=Math.round(k*range/6);out+=text(Math.min(1090,xx(j)-35),1070,c.days[visible[j]],'#335268',11)}
 $('chart').innerHTML=out+text(left,1110,'Hover for exact date and learned parameters; click two dates to select an interval. Fills use later opens.');
}
function atEvent(e){if(!visible.length)return null;const box=$('chart').getBoundingClientRect();const x=(e.clientX-box.left)*1200/box.width;return visible[Math.max(0,Math.min(visible.length-1,Math.round((x-85)/(1170-85)*(visible.length-1))))]}
function readPoint(e){const i=atEvent(e);if(i==null)return;const c=current,a=c.arms[$('arm').value],num=v=>v==null?'—':v.toFixed(3);$('readout').textContent=`${c.days[i]} | close ${num(c.close[i])} | policy ${a.policy[i]??'context'} | entry ${num(a.entry_threshold[i])} | down exit ${num(a.exit_threshold[i])} | distance ${num(a.distance[i])} | payoff mean ${num(a.posterior_mean[i])} | evidence ${num(a.effective_count[i])} | days since reset ${num(a.reset_age[i])} | win estimate ${percent(a.win_probability[i])} | NAV ${num(a.nav[i])}`}
$('era').addEventListener('change',()=>selectCase(true));$('etf').addEventListener('change',()=>selectCase(false));$('arm').addEventListener('change',render);
for(const id of ['from','to'])$(id).addEventListener('change',render);
$('weakest').addEventListener('click',()=>{$('etf').value=DATA.weakest[$('era').value].symbol;$('arm').value='regime_reset';selectCase(true)});
$('weat').addEventListener('click',()=>{$('era').value='late';selectCase(true);$('etf').value='WEAT';selectCase(true)});
$('reset').addEventListener('click',()=>selectCase(true));$('chart').addEventListener('mousemove',readPoint);
$('chart').addEventListener('click',e=>{const i=atEvent(e);if(i==null)return;const d=current.days[i];if(firstClick==null){firstClick=d;$('readout').textContent='Start '+d+'; click the end date.'}else{[$('from').value,$('to').value]=[firstClick,d].sort();firstClick=null;render()}});
$('era').value='late';$('arm').value='regime_reset';$('etf').value=DATA.weakest.late.symbol;selectCase(true);
