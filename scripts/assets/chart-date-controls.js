// Session-exact selection for the self-contained multiscale report.
let visibleIndices=[], selectionStart=null;
function selectionText(){
  const c=DATA.charts[key()];if(!c)return;
  const a=$('date-start').value,b=$('date-end').value;
  $('selection-text').value=`${selected} · ${$('era').value} · ${$('variant').value} · ${a} to ${b}`;
}
function resetDates(){
  const c=DATA.charts[key()];if(!c)return;
  for(const id of ['date-start','date-end','inspect-date']){$(id).min=c.days[0];$(id).max=c.days.at(-1);}
  $('date-start').value=c.days[0];$('date-end').value=c.days.at(-1);
  selectionStart=null;selectionText();
}
function chartIndices(c){
  const mode=$('window').value;
  return c.days.map((d,i)=>i).filter(i=>mode==='custom'?(c.days[i]>=$('date-start').value&&c.days[i]<=$('date-end').value):mode==='all'||c.days[i].startsWith(mode));
}
function applyDates(){
  const a=$('date-start').value,b=$('date-end').value;
  if(!a||!b||a>b){$('date-status').textContent='Enter a start date on or before the end date.';return;}
  $('date-status').textContent='';$('window').value='custom';selectionText();plot();
}
function inspectDate(){
  const c=DATA.charts[key()];if(!c)return;
  const day=$('inspect-date').value;
  const i=c.days.findIndex(d=>d>=day);$('cursor').value=i<0?c.days.length-1:i;readout();
}
function moveCrosshair(){
  const c=DATA.charts[key()],i=Number($('cursor').value);if(!c||!visibleIndices.length)return;
  $('inspect-date').value=c.days[i];
  const a=visibleIndices[0],b=visibleIndices.at(-1),line=$('date-crosshair'),label=$('date-hover');
  if(!line||!label)return;
  const x=70+(i-a)/Math.max(1,b-a)*1000,show=i>=a&&i<=b;
  line.setAttribute('d',show?`M${x} 35V820`:'');
  label.setAttribute('x',Math.max(135,Math.min(1000,x)));label.textContent=show?c.days[i]:'';
}
function chartPointer(e,select){
  const svg=$('chart').querySelector('svg');if(!svg||!visibleIndices.length)return;
  const box=svg.getBoundingClientRect(),x=(e.clientX-box.left)/box.width*1140;
  const a=visibleIndices[0],b=visibleIndices.at(-1),i=Math.max(a,Math.min(b,Math.round(a+(x-70)/1000*(b-a))));
  $('cursor').value=i;readout();
  if(select){
    const d=DATA.charts[key()].days[i];
    if(selectionStart===null){selectionStart=d;$('date-status').textContent=`Start ${d} selected. Click the end of your interval.`;}
    else{const pair=[selectionStart,d].sort();$('date-start').value=pair[0];$('date-end').value=pair[1];selectionStart=null;$('date-status').textContent='Interval selected. Choose Zoom to interval, or copy the text below.';selectionText();}
  }
}
function installDateControls(){
  $('date-start').onchange=selectionText;$('date-end').onchange=selectionText;
  $('date-apply').onclick=applyDates;$('date-reset').onclick=()=>{resetDates();$('window').value='all';plot();};
  $('inspect-date').onchange=inspectDate;
  $('chart').onmousemove=e=>chartPointer(e,false);$('chart').onclick=e=>chartPointer(e,true);
  $('selection-text').onclick=()=>{$('selection-text').select();};
}
