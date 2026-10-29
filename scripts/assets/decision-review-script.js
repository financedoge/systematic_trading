const $=id=>document.getElementById(id),names={baseline:'A · Standing protection',stop:'B · Independent review',review:'C · Adaptive review'},policies=['Inherited fixed risk policy'];
const pct=x=>x==null?'—':(100*x).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(3);
let current,visible=[],firstClick=null;
function symbols(){return Object.keys(DATA.charts).filter(k=>k.endsWith('_'+$('era').value)).map(k=>k.split('_')[0]).sort()}
function selectCase(reset=false){const all=symbols(),old=$('etf').value;$('etf').innerHTML=all.map(s=>`<option>${s}</option>`).join('');$('etf').value=all.includes(old)?old:DATA.weakest[$('era').value].symbol;current=DATA.charts[$('etf').value+'_'+$('era').value];if(reset||!$('from').value){$('from').value=current.evaluation_start;$('to').value=current.days.at(-1)}firstClick=null;render()}
function render(){
 const c=current,a=c.arms[$('arm').value],row=DATA.rows.find(r=>r.symbol===$('etf').value&&r.era===$('era').value&&r.arm===$('arm').value);
 visible=c.days.map((_,i)=>i).filter(i=>c.days[i]>=$('from').value&&c.days[i]<=$('to').value);
 $('metrics').textContent=`${names[row.arm]} | Full-era return ${pct(row.cumulative)} · Sharpe ${num(row.sharpe)} · Calmar ${num(row.calmar)} · drawdown ${pct(-row.maxdd)} · ${row.closed_trades} closed / ${row.wins} winners · close exposure ${pct(row.exposure)}`;
 $('dependence').textContent=`Daily correlation ${num(row.correlation)} · beta ${num(row.beta)} · annual regression intercept ${pct(row.alpha_annual)} (HAC t ${num(row.alpha_t_hac)}) · raw-state IC5 ${num(row.ic5)} · ETF buy/hold ${pct(row.buyhold)}. Fees ${num(row.cost_bp_annual)} bp/year plus modeled stop slippage ${num(row.stop_slippage_bp_annual)} bp/year.`;
 $('learning').textContent=`${row.entry_invalidations} entry invalidations; ${row.recovery_closed} completed recoveries (${row.recovery_wins} winners); ${row.cancelled_recoveries} cancelled recovery orders; ${row.resets} accelerated review warnings. Forecast IC ${num(row.forecast_ic)}, Brier ${num(row.forecast_brier)}, log score ${num(row.forecast_logscore)}. No HMM refit or widened stop.`;
 $('fitparameters').textContent=JSON.stringify({base_policy:c.parameters,calibration:c.training,HMM:c.selection.hmm.model,thesis_exit:c.selection.exit_rule},null,2);
 $('weakestNote').textContent=`Weakest C in ${$('era').value}: ${DATA.weakest[$('era').value].symbol}, ${pct(DATA.weakest[$('era').value].cumulative)}. Ranked on net return excluding BIL; no per-ETF hindsight choice.`;
 $('trades').innerHTML=a.trades.filter(t=>t.entry_date<=$('to').value&&(!t.exit_date||t.exit_date>=$('from').value)).map(t=>`<tr><td>${t.entry_date}</td><td>${t.exit_date||'Open'}</td><td>${num(t.entry)} → ${num(t.exit_price)}</td><td>${t.entry_reason||'ordinary'}</td><td>${policies[t.entry_policy]}</td><td>${pct(t.net_return)}</td><td>${pct(t.initial_risk_fraction)}</td><td>${t.exit_reason||'—'}</td></tr>`).join('');
 $('events').innerHTML=a.events.filter(t=>t.day>=$('from').value&&t.day<=$('to').value).map(t=>`<tr><td>${t.day}</td><td>${t.reasons.join(', ')||'Policy reassessment'}</td><td>${t.reset?'Accelerated recent learning':'No acceleration'}</td><td>Recent weight ${pct(t.recent_weight)}</td></tr>`).join('');
 if(!visible.length){$('chart').innerHTML='<text x="60" y="80">No sessions in this date range.</text>';$('window').textContent='';return}
 const left=85,right=1170,range=visible.length-1,xx=j=>left+j/Math.max(1,range)*(right-left);
 const first=visible[0],last=visible.at(-1);$('window').textContent='Selected interval, continuously traded account (not restarted): '+Object.entries(c.arms).map(([key,v])=>`${names[key]} ${pct(v.nav[last]!=null&&v.nav[Math.max(0,first-1)]!=null?v.nav[last]/v.nav[Math.max(0,first-1)]-1:null)}`).join(' · ');
 let out='<rect width="1200" height="1550" fill="white"/>';
 const text=(x,y,s,fill='#335268',size=12)=>`<text x="${x}" y="${y}" fill="${fill}" font-size="${size}">${s}</text>`;
 const lines=(arrays,top,bottom,label,bounds=null,extras=[])=>{
  const vals=arrays.flatMap(s=>visible.map(i=>s.data[i])).concat(extras).filter(v=>v!=null&&Number.isFinite(v));let low=bounds?bounds[0]:Math.min(...vals),high=bounds?bounds[1]:Math.max(...vals);
  if(!vals.length&&!bounds){low=0;high=1}if(high===low)high=low+1;if(!bounds){const pad=(high-low)*.07;low-=pad;high+=pad}
  const yy=v=>bottom-(v-low)/(high-low)*(bottom-top);out+=text(left,top-12,label);
  for(let k=0;k<4;k++){const v=low+(high-low)*k/3,y=yy(v);out+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#e4ebef"/>`+text(5,y+4,v.toFixed(2))}
  for(const s of arrays){let path='',active=false;visible.forEach((i,j)=>{const v=s.data[i];if(v==null||!Number.isFinite(v)){active=false;return}path+=(active?'L':'M')+xx(j).toFixed(2)+','+yy(v).toFixed(2);active=true});out+=`<path d="${path}" stroke="${s.color}" stroke-width="1.6" fill="none"/>`}return yy;
 };
 const selectedFills=a.fills.filter(e=>e.day>=$('from').value&&e.day<=$('to').value);
 const py=lines([{data:c.close,color:'#173d54'},{data:a.stop,color:'#b64f61'}],40,350,'Adjusted OHLC, active stop red, buys green / sells red; recovery buys orange',null,visible.flatMap(i=>[c.low[i],c.high[i]]).concat(selectedFills.map(e=>e.price)));
 if(visible.length<=180)visible.forEach((i,j)=>{const x=xx(j),up=c.close[i]>=c.open[i],color=up?'#6bafa1':'#d78995',width=Math.max(1,Math.min(5,(right-left)/visible.length*.55));out+=`<line x1="${x}" x2="${x}" y1="${py(c.low[i])}" y2="${py(c.high[i])}" stroke="${color}"/><rect x="${x-width/2}" y="${py(Math.max(c.open[i],c.close[i]))}" width="${width}" height="${Math.max(.7,Math.abs(py(c.open[i])-py(c.close[i])))}" fill="${color}"/>`});
 for(const e of selectedFills){const j=visible.findIndex(i=>c.days[i]===e.day),x=xx(j),y=py(e.price),buy=e.side==='buy',s=buy?1:-1,reentry=a.trades.some(t=>t.entry_date===e.day&&t.entry_reason==='exit_review');out+=`<polygon points="${x},${y-7*s} ${x-6},${y+5*s} ${x+6},${y+5*s}" fill="${buy?(reentry?'#d58b20':'#008675'):'#ba465b'}"/>`}
 lines([{data:c.volume.map(v=>v/1e6),color:'#819cad'}],400,485,'Audited raw ETF share volume (millions)');
 lines([{data:c.fast_up,color:'#008675'},{data:c.neutral,color:'#b09a52'},{data:c.fast_down,color:'#b64f61'}],535,650,'Fast HMM: up green, neutral gold, down red (unchanged across all three)',[0,1]);
 lines([{data:c.slow_up,color:'#008675'},{data:c.slow_down,color:'#b64f61'}],700,790,'Slow context: up green, down red',[0,1]);
 lines([{data:a.probability,color:'#008675'},{data:a.recent_weight,color:'#c98a21'}],840,940,'Independent up forecast green; recent-model weight gold',[0,1]);
 lines([{data:a.up_evidence,color:'#008675'},{data:a.down_evidence,color:'#b64f61'},{data:c.days.map(()=>Math.log(4)),color:'#9da9b4'}],990,1090,'Accumulated recovery evidence green / exit evidence red; threshold log(4) grey');
 lines([{data:c.arms.baseline.nav,color:'#9da9b4'},{data:c.arms.stop.nav,color:'#ce9229'},{data:c.arms.review.nav,color:'#008675'}],1140,1450,'NAV: A protection grey; B independent review amber; C adaptive review green; initial cash 100');
 for(let k=0;k<7;k++){const j=Math.round(k*range/6);out+=text(Math.min(1090,xx(j)-35),1480,c.days[visible[j]],'#335268',11)}
 $('chart').innerHTML=out+text(left,1530,'Hover for date, OHLC and fills. Click two dates to zoom; candles appear below 181 sessions.');
}
function atEvent(e){if(!visible.length)return null;const box=$('chart').getBoundingClientRect(),x=(e.clientX-box.left)*1200/box.width;return visible[Math.max(0,Math.min(visible.length-1,Math.round((x-85)/(1170-85)*(visible.length-1))))]}
function readPoint(e){const i=atEvent(e);if(i==null)return;const c=current,a=c.arms[$('arm').value],fills=a.fills.filter(f=>f.day===c.days[i]).map(f=>`${f.side} ${num(f.price)} (${f.phase||'next open'})`).join('; ');$('readout').textContent=`${c.days[i]} | O ${num(c.open[i])} H ${num(c.high[i])} L ${num(c.low[i])} C ${num(c.close[i])} | volume ${Math.round(c.volume[i]).toLocaleString()} | up ${num(c.fast_up[i])}, down ${num(c.fast_down[i])}, slow down ${num(c.slow_down[i])} | stop ${num(a.stop[i])} | review up ${num(a.probability[i])}, expected 5d ${pct(a.forecast[i])}, G+ ${num(a.up_evidence[i])}, G- ${num(a.down_evidence[i])}, recent weight ${pct(a.recent_weight[i])} | ${fills||'No fill'} | NAV ${num(a.nav[i])}`}
$('chart').addEventListener('mousemove',readPoint);$('chart').addEventListener('click',e=>{const i=atEvent(e);if(i==null)return;const day=current.days[i];if(firstClick===null){firstClick=day;$('readout').textContent=`Selected ${day}. Click the other endpoint.`}else{[$('from').value,$('to').value]=[firstClick,day].sort();firstClick=null;render()}});
for(const id of ['era','etf'])$(id).addEventListener('change',()=>selectCase(true));for(const id of ['arm','from','to'])$(id).addEventListener('change',()=>{firstClick=null;render()});$('reset').addEventListener('click',()=>selectCase(true));
$('weakest').addEventListener('click',()=>{$('etf').value=DATA.weakest[$('era').value].symbol;$('arm').value='review';selectCase(true)});
function jump(symbol,era,from,to){$('era').value=era;$('etf').value=symbol;$('arm').value='review';selectCase(true);if(from){$('from').value=from;$('to').value=to;render()}}
$('weat').addEventListener('click',()=>jump('WEAT','late'));$('tlt').addEventListener('click',()=>jump('TLT','late','2023-08-01','2024-12-31'));
$('cper').addEventListener('click',()=>jump('CPER','late','2025-03-04','2025-09-04'));$('iwm').addEventListener('click',()=>jump('IWM','late','2024-07-01','2024-12-01'));
$('era').value='late';$('arm').value='review';$('etf').value='CPER';selectCase(true);
jump('CPER','late','2025-03-04','2025-09-04');
