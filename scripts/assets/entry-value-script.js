const $=id=>document.getElementById(id),names={control:'A · Fixed policy, original detector',hmm:'B · Symmetric directional HMM',value:'C · HMM with entry-value forecast'};
const pct=x=>x==null?'—':(100*x).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(3);
let current,visible=[],firstClick=null;
function symbols(){return Object.keys(DATA.charts).filter(k=>k.endsWith('_'+$('era').value)).map(k=>k.split('_')[0]).sort()}
function selectCase(reset=false){
 const all=symbols(),old=$('etf').value;$('etf').innerHTML=all.map(s=>`<option>${s}</option>`).join('');
 $('etf').value=all.includes(old)?old:DATA.weakest[$('era').value].symbol;current=DATA.charts[$('etf').value+'_'+$('era').value];
 if(reset||!$('from').value){$('from').value=current.days[0];$('to').value=current.days.at(-1)}firstClick=null;render();
}
function render(){
 const c=current,a=c.arms[$('arm').value],row=DATA.rows.find(r=>r.symbol===$('etf').value&&r.era===$('era').value&&r.arm===$('arm').value);
 visible=c.days.map((_,i)=>i).filter(i=>c.days[i]>=$('from').value&&c.days[i]<=$('to').value);
 $('metrics').textContent=`${names[row.arm]} | return ${pct(row.cumulative)} · Sharpe ${num(row.sharpe)} · Calmar ${num(row.calmar)} · drawdown ${pct(-row.maxdd)} · exposure ${pct(row.exposure)} · ${row.closed_trades} closed / ${row.wins} winning trades · ${row.blocked_sessions} entry-days rejected`;
 $('dependence').textContent=`Daily correlation ${num(row.correlation)} · beta ${num(row.beta)} · annualized regression intercept ${pct(row.alpha_annual)} (HAC t ${num(row.alpha_t_hac)}) · five-session signal IC ${num(row.ic5)} · upside/downside capture ${pct(row.up_capture)} / ${pct(row.down_capture)}. Previous adaptive incumbent return ${pct(row.adaptive_incumbent_cumulative)}, Sharpe ${num(row.adaptive_incumbent_sharpe)}; buy-and-hold ${pct(row.buyhold)}.`;
 $('parameters').textContent=`Training through ${c.selection.training_end}; HMM means +/-${num(c.selection.hmm.model.means[2][0])}; forecast ${c.selection.forecast.kind}, half-life ${c.selection.forecast.memory} sessions, horizon ${c.selection.horizon} sessions. Online policy learning is fixed in all three comparisons; C updates its outcome forecasts every close. Gate: predicted return - roundtrip log fee - 0.25 * predicted adverse movement > 0.`;
 $('forecast').textContent=`Forecast IC ${num(row.forecast.ic)}; return MSE ${num(1e4*row.forecast.return_mse)} vs same-memory intercept ${num(1e4*row.forecast_null.return_mse)} (both x10^4). Mean predicted / realized return ${pct(row.forecast.mean_predicted_return)} / ${pct(row.forecast.mean_return)}; sampled adverse movement ${pct(row.forecast.mean_predicted_downside)} / ${pct(row.forecast.mean_downside)}. Forecast diagnostics describe C's next-open model, including when another arm is selected.`;
 $('fitparameters').textContent=JSON.stringify({original_policy:c.parameters,new_HMM:c.selection.hmm.model,thesis_exit:c.selection.exit_rule,forecast:c.selection.forecast,forecast_candidates:c.selection.candidates,horizon:c.selection.horizon,prefix_end:c.selection.prefix_end},null,2);
 $('weakestNote').textContent=`Weakest C in ${$('era').value}: ${DATA.weakest[$('era').value].symbol} (${pct(DATA.weakest[$('era').value].cumulative)}). Lowest net return, excluding BIL. No retrospective choice of best arm per ETF.`;
 $('trades').innerHTML=a.trades.filter(t=>t.entry_date<=$('to').value&&(!t.exit_date||t.exit_date>=$('from').value)).map(t=>`<tr><td>${t.entry_date}</td><td>${t.exit_date||'Open'}</td><td>${t.context}</td><td>${pct(t.net_return)}</td><td>${pct(t.initial_risk_fraction)}</td><td>${t.exit_reason||'—'}</td></tr>`).join('');
 $('regimes').innerHTML=Object.entries(row.regimes).map(([s,v])=>`<tr><td>${s}</td><td>${v.sessions}</td><td>${pct(v.exposure)}</td><td>${pct(v.strategy_mean)}</td><td>${pct(v.asset_mean)}</td><td>${v.closed}</td><td>${v.losing}</td><td>${pct(v.mean_trade)}</td></tr>`).join('');
 if(!visible.length){$('chart').innerHTML='<text x="60" y="80">No sessions in this date range.</text>';return}
 const left=85,right=1170,range=visible.length-1,xx=j=>left+j/Math.max(1,range)*(right-left);
 let out='<rect width="1200" height="1490" fill="white"/>';
 const text=(x,y,s,fill='#335268',size=12)=>`<text x="${x}" y="${y}" fill="${fill}" font-size="${size}">${s}</text>`;
 const lines=(arrays,top,bottom,label,bounds=null)=>{
  const vals=arrays.flatMap(s=>visible.map(i=>s.data[i])).filter(v=>v!=null&&Number.isFinite(v));
  let low=bounds?bounds[0]:Math.min(...vals),high=bounds?bounds[1]:Math.max(...vals);
  if(!vals.length&&!bounds){low=0;high=1}if(high===low)high=low+1;
  if(!bounds){const pad=(high-low)*.07;low-=pad;high+=pad}
  const yy=v=>bottom-(v-low)/(high-low)*(bottom-top);out+=text(left,top-12,label);
  for(let k=0;k<4;k++){const v=low+(high-low)*k/3,y=yy(v);out+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#e4ebef"/>`+text(5,y+4,v.toFixed(2))}
  for(const s of arrays){let path='',active=false;visible.forEach((i,j)=>{const v=s.data[i];if(v==null||!Number.isFinite(v)){active=false;return}path+=(active?'L':'M')+xx(j).toFixed(2)+','+yy(v).toFixed(2);active=true});out+=`<path d="${path}" stroke="${s.color}" stroke-width="1.7" fill="none"/>`}
  return yy;
 };
 const py=lines([{data:c.close,color:'#173d54'},{data:a.stop,color:'#b64f61'}],40,330,'Adjusted price (navy), protection (red), actual buys / sells (triangles)');
 for(const t of a.trades)for(const [day,price,buy] of [[t.entry_date,t.entry,true],[t.exit_date,t.exit_price,false]]){const j=visible.findIndex(i=>c.days[i]===day);if(j<0)continue;const x=xx(j),y=py(price),s=buy?1:-1;out+=`<polygon points="${x},${y-6*s} ${x-5},${y+4*s} ${x+5},${y+4*s}" fill="${buy?'#008675':'#ba465b'}"/>`}
 lines([{data:c.volume.map(v=>v==null?null:v/1e6),color:'#819cad'}],380,465,'Audited raw ETF share volume (millions)');
 lines([{data:a.fast_up,color:'#008675'},{data:a.neutral,color:'#b09a52'},{data:a.fast_down,color:'#b64f61'}],515,630,'Selected detector: up (green), range / neutral (gold), down (red)',[0,1]);
 const hide=v=>v.map((x,i)=>c.days[i]>=c.evaluation_start?x:null);
 lines([{data:hide(c.slow_up),color:'#008675'},{data:hide(c.slow_down),color:'#b64f61'}],680,780,'Slow context: up (green), down (red)',[0,1]);
 const pc=v=>v.map(x=>x==null?null:100*x);
 lines([{data:pc(a.predicted_return),color:'#008675'},{data:pc(a.predicted_downside),color:'#b64f61'},{data:pc(a.utility),color:'#294eab'}],830,950,'C forecast (% log): return green; sampled adverse movement red; net utility blue');
 lines([{data:c.arms.value.gate,color:'#008675'},{data:c.arms.value.blocked,color:'#b64f61'}],1000,1070,'C entry gate passes green; funded eligible entry rejected red',[0,1]);
 lines([{data:c.arms.control.nav,color:'#9da9b4'},{data:c.arms.hmm.nav,color:'#ce9229'},{data:c.arms.value.nav,color:'#008675'}],1120,1390,'NAV: A grey; B amber; C green; initial cash 100');
 for(let k=0;k<7;k++){const j=Math.round(k*range/6);out+=text(Math.min(1090,xx(j)-35),1420,c.days[visible[j]],'#335268',11)}
 $('chart').innerHTML=out+text(left,1470,'Hover for a dated readout. Click two dates to zoom. Date inputs also accept exact intervals.');
}
function atEvent(e){if(!visible.length)return null;const box=$('chart').getBoundingClientRect(),x=(e.clientX-box.left)*1200/box.width;return visible[Math.max(0,Math.min(visible.length-1,Math.round((x-85)/(1170-85)*(visible.length-1))))]}
function readPoint(e){const i=atEvent(e);if(i==null)return;const c=current,a=c.arms[$('arm').value];$('readout').textContent=`${c.days[i]} | adjusted close ${num(c.close[i])} | up ${num(a.fast_up[i])}, range ${num(a.neutral[i])}, down ${num(a.fast_down[i])} | normalized fast slope ${num(c.normalized_slope[i])} | slow down ${num(c.slow_down[i])} | C forecast return ${pct(a.predicted_return[i])}, adverse movement ${pct(a.predicted_downside[i])}, utility ${pct(a.utility[i])} | C entry blocked ${c.arms.value.blocked[i]===1?'yes':'no'} | stop ${num(a.stop[i])} | NAV ${num(a.nav[i])}`}
$('chart').addEventListener('mousemove',readPoint);
$('chart').addEventListener('click',e=>{const i=atEvent(e);if(i==null)return;const day=current.days[i];if(firstClick===null){firstClick=day;$('readout').textContent=`Selected ${day}. Click the other endpoint.`}else{[$('from').value,$('to').value]=[firstClick,day].sort();firstClick=null;render()}});
for(const id of ['era','etf'])$(id).addEventListener('change',()=>selectCase(true));
for(const id of ['arm','from','to'])$(id).addEventListener('change',()=>{firstClick=null;render()});
$('reset').addEventListener('click',()=>selectCase(true));
$('weakest').addEventListener('click',()=>{$('etf').value=DATA.weakest[$('era').value].symbol;$('arm').value='value';selectCase(true)});
function jump(symbol,era,from,to){$('era').value=era;$('etf').value=symbol;$('arm').value='value';selectCase(true);if(from){$('from').value=from;$('to').value=to;render()}}
$('weat').addEventListener('click',()=>jump('WEAT','late'));
$('tlt').addEventListener('click',()=>jump('TLT','late','2023-08-01','2024-12-31'));
$('inda').addEventListener('click',()=>jump('INDA','late','2024-11-01','2025-04-01'));
$('gold').addEventListener('click',()=>jump('GLD','early','2020-01-02','2020-09-01'));
$('cper').addEventListener('click',()=>jump('CPER','late','2025-06-15','2025-08-15'));
$('iwm').addEventListener('click',()=>jump('IWM','early','2020-10-01','2021-06-30'));
$('era').value='late';$('arm').value='value';$('etf').value=DATA.weakest.late.symbol;selectCase(true);
