const $=id=>document.getElementById(id), names={fixed:'A · Existing policy',streak:'B · Streak feedback',severity:'C · Streak + large-loss / stop warnings'};
let current, visible=[],firstClick=null;
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
 $('metrics').textContent=`${names[row.arm]} | return ${percent(row.cumulative)} · Sharpe ${row.sharpe.toFixed(3)} · Calmar ${row.calmar==null?'—':row.calmar.toFixed(2)} · max drawdown ${percent(-row.maxdd)} · exposure ${percent(row.exposure)} · ${row.closed_trades} closed trades · ${row.pause_sessions} paused sessions · matched buy-and-hold ${percent(row.buyhold)} · idle cash 0%`;
 $('parameters').textContent=`Training through ${c.calibration.training_end}: ${c.calibration.winning_trades} winning / ${c.calibration.completed_trades} completed trades; winner σ = ${percent(c.calibration.winner_sigma)}; loss threshold = ${percent(row.threshold)}. Market policy: ${JSON.stringify(c.parameters)}. Before evaluation, only observed price/volume context is displayed.`;
 $('weakestNote').textContent=`Weakest C case for ${$('era').value}: ${DATA.weakest[$('era').value].symbol}, ${percent(DATA.weakest[$('era').value].cumulative)} net. Criterion: lowest net return, fixed C rules applied to each ETF's training-selected market policy, excluding BIL.`;
 const trades=a.trades.filter(t=>t.entry_date<=$('to').value&&(!t.exit_date||t.exit_date>=$('from').value));
 $('trades').innerHTML=trades.map(t=>`<tr><td>${t.entry_date}</td><td>${t.exit_date||'Open'}</td><td>${t.entry_mode}</td><td>${percent(t.entry_weight)}</td><td>${percent(t.net_return)}</td><td>${t.exit_reason||'—'}</td></tr>`).join('');
 $('events').innerHTML=a.health_events.filter(e=>e.day>=$('from').value&&e.day<=$('to').value).map(e=>`<tr><td>${e.day}</td><td>${e.mode}</td><td>${e.reason.replaceAll('_',' ')}</td><td>${e.source}</td></tr>`).join('');
 if(!visible.length){$('chart').innerHTML='<text x="60" y="80">No sessions in this date range.</text>';return}
 const W=1200,left=85,right=1170,range=visible.length-1,xx=j=>left+j/Math.max(1,range)*(right-left);
 let out='<rect width="1200" height="1090" fill="white"/>';
 const text=(x,y,s,fill='#335268',size=12)=>`<text x="${x}" y="${y}" fill="${fill}" font-size="${size}">${s}</text>`;
 const lines=(arrays,top,bottom,label,fixed=null)=>{
  const vals=arrays.flatMap(v=>visible.map(i=>v.data[i])).filter(v=>v!=null&&Number.isFinite(v));
  let min=fixed?fixed[0]:Math.min(...vals),max=fixed?fixed[1]:Math.max(...vals);
  if(!vals.length&&!fixed){min=0;max=1}if(max===min)max=min+1;
  if(!fixed){const pad=(max-min)*.07;min-=pad;max+=pad}
  const yy=v=>bottom-(v-min)/(max-min)*(bottom-top);
  out+=text(left,top-12,label);
  for(let k=0;k<4;k++){let v=min+(max-min)*k/3,y=yy(v);out+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#e4ebef"/>`+text(5,y+4,v.toFixed(2))}
  for(const s of arrays){let path='',active=false;visible.forEach((i,j)=>{const v=s.data[i];if(v==null||!Number.isFinite(v)){active=false;return}path+=(active?'L':'M')+xx(j).toFixed(2)+','+yy(v).toFixed(2);active=true});out+=`<path d="${path}" stroke="${s.color}" stroke-width="1.7" fill="none"/>`}
  return yy;
 };
 const floor=c.days.map(()=>null);
 if($('arm').value==='severity'&&row.threshold!=null)for(const t of a.trades)for(const i of visible)if(c.days[i]>=t.entry_date&&(!t.exit_date||c.days[i]<t.exit_date))floor[i]=t.entry*(1-row.threshold)*1.0005/.9995;
 const py=lines([{data:c.close,color:'#173d54'},{data:a.stop,color:'#b64f61'},{data:floor,color:'#8656ad'}],40,330,'Adjusted close (navy), adopted protection (red), one-sigma loss level (purple)');
 for(const t of a.trades){for(const [day,price,buy] of [[t.entry_date,t.entry,true],[t.exit_date,t.exit_price,false]]){const j=visible.findIndex(i=>c.days[i]===day);if(j<0)continue;const x=xx(j),y=py(price),sign=buy?1:-1;out+=`<polygon points="${x},${y-6*sign} ${x-5},${y+4*sign} ${x+5},${y+4*sign}" fill="${buy?'#008675':'#ba465b'}"/>`}}
 lines([{data:c.volume.map(v=>v/1e6),color:'#819cad'}],380,465,'Audited raw ETF share volume (millions)');
 const hide=v=>v.map((x,i)=>c.days[i]>=c.evaluation_start?x:null);
 lines([{data:hide(c.fast_up),color:'#008675'},{data:hide(c.slow_down),color:'#b64f61'}],515,610,'Fast up probability (green); slow down probability (red)',[0,1]);
 const colors={normal:'#d3e9df',defensive:'#f4dfb3',paused:'#efbec5',probation:'#d9ceee'};
 out+=text(left,650,'Strategy health: green normal · amber defensive · red paused · purple probation');
 visible.forEach((i,j)=>{if(c.days[i]>=c.evaluation_start)out+=`<rect x="${xx(j)}" y="665" width="${Math.max(1,(right-left)/Math.max(1,range))}" height="32" fill="${colors[a.modes[i]]}"/>`});
 lines([{data:c.arms.fixed.nav,color:'#9da9b4'},{data:c.arms.streak.nav,color:'#ce9229'},{data:c.arms.severity.nav,color:'#008675'}],745,990,'NAV: A grey · B amber · C green · initial cash 100');
 for(let k=0;k<7;k++){const j=Math.round(k*range/6);out+=text(Math.min(1090,xx(j)-35),1020,c.days[visible[j]],'#335268',11)}
 const evaluation=visible.findIndex(i=>c.days[i]>=c.evaluation_start);if(evaluation>=0)out+=`<line x1="${xx(evaluation)}" x2="${xx(evaluation)}" y1="25" y2="1000" stroke="#697987" stroke-dasharray="4 4"/>`;
 $('chart').innerHTML=out+text(left,1060,'Hover for an exact date; click two dates to select an interval. Fills use next open; no peak-sale assumption.');
}
function atEvent(e){if(!visible.length)return null;const box=$('chart').getBoundingClientRect();const x=(e.clientX-box.left)*1200/box.width;return visible[Math.max(0,Math.min(visible.length-1,Math.round((x-85)/(1170-85)*(visible.length-1))))]}
function readPoint(e){const i=atEvent(e);if(i==null)return;const c=current,a=c.arms[$('arm').value];$('readout').textContent=`${c.days[i]} | close ${c.close[i].toFixed(3)} | volume ${Math.round(c.volume[i]).toLocaleString()} | NAV ${a.nav[i]==null?'before evaluation':a.nav[i].toFixed(2)} | ${c.days[i]<c.evaluation_start?'context only':a.modes[i]}`}
$('era').addEventListener('change',()=>selectCase(true));$('etf').addEventListener('change',()=>selectCase(false));$('arm').addEventListener('change',render);
for(const id of ['from','to'])$(id).addEventListener('change',render);
$('weakest').addEventListener('click',()=>{$('etf').value=DATA.weakest[$('era').value].symbol;$('arm').value='severity';selectCase(true)});
$('weat').addEventListener('click',()=>{$('era').value='late';selectCase(true);$('etf').value='WEAT';selectCase(true)});
$('reset').addEventListener('click',()=>selectCase(true));$('chart').addEventListener('mousemove',readPoint);
$('chart').addEventListener('click',e=>{const i=atEvent(e);if(i==null)return;const d=current.days[i];if(firstClick==null){firstClick=d;$('readout').textContent='Start '+d+'; click the end date.'}else{[$('from').value,$('to').value]=[firstClick,d].sort();firstClick=null;render()}});
$('era').value='late';$('arm').value='severity';$('etf').value=DATA.weakest.late.symbol;selectCase(true);
