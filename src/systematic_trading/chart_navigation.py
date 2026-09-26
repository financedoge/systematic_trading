"""Dependency-free time-window controls, embedded in pages and exported reports."""

CHART_NAVIGATION_HTML = r'''
<style id="time-chart-navigation-style">
.time-chart-tools{display:flex;align-items:center;flex-wrap:wrap;gap:7px;padding:10px 16px;color:#657083;font:12px system-ui}
.time-chart-tools button{border:1px solid #cbd5e1;background:#fff;color:#24364b;border-radius:5px;padding:6px 10px;cursor:pointer}
.time-chart-tools button[aria-pressed="true"]{background:#2456a6;border-color:#2456a6;color:white}
.time-chart-tools .time-chart-range{font-variant-numeric:tabular-nums}
.time-chart-host svg{touch-action:none;user-select:none;cursor:crosshair}
.time-chart-host[data-navigation-mode="pan"] svg{cursor:grab}
.time-chart-host.time-chart-dragging svg{cursor:grabbing}
.time-chart-host:focus-visible{outline:2px solid #2456a6;outline-offset:-2px}
</style>
<script id="time-chart-navigation">
(() => {
  const instances = new Map();
  const clamp = (range, extent) => {
    if (!range || !extent) return null;
    let [a,b] = range.slice().sort((x,y)=>x-y);
    const span = Math.min(b-a, extent[1]-extent[0]);
    a = Math.max(extent[0], Math.min(a, extent[1]-span));
    return [a,a+span];
  };
  const date = (value, intraday) => new Date(value).toISOString().slice(0,intraday?19:10).replace('T',' ');
  function create(id) {
    const host = document.getElementById(id);
    if (!host) return null;
    const c = {id,host,extent:null,range:null,mode:'zoom',gesture:null,frame:null};
    instances.set(id,c);
    host.classList.add('time-chart-host');host.tabIndex=0;
    host.setAttribute('aria-description','Drag to zoom. Choose Pan or hold Shift while dragging. Left and right arrows pan; Home restores the full range; Escape cancels a drag.');
    const tools = document.createElement('div');tools.className='time-chart-tools';
    tools.setAttribute('role','group');tools.setAttribute('aria-label',`${id.replaceAll('-',' ')} navigation`);
    c.tools=tools;c.buttons={};
    for(const [key,label] of [['zoom','Zoom'],['pan','Pan'],['reset','Full history']]) {
      const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.navigationAction=key;
      button.onclick=()=>{if(key==='reset'){cancel(c);apply(c,null)}else{cancel(c);c.mode=key;controls(c)}};
      c.buttons[key]=button;tools.appendChild(button);
    }
    c.label=document.createElement('span');c.label.className='time-chart-range';c.label.setAttribute('aria-live','polite');tools.appendChild(c.label);
    const help=document.createElement('span');help.textContent='Drag to zoom · Pan or Shift + drag to move · Home to reset';tools.appendChild(help);
    host.before(tools);
    const point = event => {
      const svg=host.querySelector('svg'), matrix=svg?.getScreenCTM();
      if(!matrix)return null;
      return new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
    };
    const at = (x,g) => g.range[0]+(Math.max(g.bounds.left,Math.min(g.bounds.right,x))-g.bounds.left)/(g.bounds.right-g.bounds.left)*(g.range[1]-g.range[0]);
    host.addEventListener('pointerdown',event=>{
      if(event.button!==0||c.gesture||!c.extent||c.extent[0]===c.extent[1])return;
      const p=point(event),bounds=c.bounds;
      if(!p||p.x<bounds.left||p.x>bounds.right||p.y<bounds.top||p.y>bounds.bottom)return;
      event.preventDefault();host.focus();host.setPointerCapture(event.pointerId);
      c.gesture={id:event.pointerId,x:p.x,last:p.x,range:(c.range||c.extent).slice(),original:c.range?.slice()||null,bounds:{...bounds},pan:c.mode==='pan'||event.shiftKey};
      host.classList.add('time-chart-dragging');
    });
    host.addEventListener('pointermove',event=>{
      const g=c.gesture;if(!g||event.pointerId!==g.id)return;
      const p=point(event);if(!p)return;g.last=p.x;
      if(g.pan){
        const delta=(p.x-g.x)/(g.bounds.right-g.bounds.left)*(g.range[1]-g.range[0]);
        g.pending=clamp(g.range.map(t=>t-delta),c.extent);
        if(!c.frame)c.frame=requestAnimationFrame(()=>{c.frame=null;if(c.gesture===g)apply(c,g.pending)});
      }else{
        let selection=host.querySelector('.time-chart-selection');
        if(!selection){selection=document.createElementNS('http://www.w3.org/2000/svg','rect');selection.setAttribute('class','time-chart-selection');selection.setAttribute('fill','#2456a6');selection.setAttribute('opacity','.16');selection.setAttribute('pointer-events','none');host.querySelector('svg').appendChild(selection)}
        const x=Math.max(g.bounds.left,Math.min(g.bounds.right,p.x));
        for(const [k,v]of Object.entries({x:Math.min(g.x,x),y:g.bounds.top,width:Math.abs(x-g.x),height:g.bounds.bottom-g.bounds.top}))selection.setAttribute(k,v);
      }
    });
    host.addEventListener('pointerup',event=>{
      const g=c.gesture;if(!g||event.pointerId!==g.id)return;
      const p=point(event);const xx=p?.x??g.last;
      finish(c);
      if(g.pan){const delta=(xx-g.x)/(g.bounds.right-g.bounds.left)*(g.range[1]-g.range[0]);apply(c,g.range.map(t=>t-delta))}
      else if(Math.abs(xx-g.x)>=6){const next=[at(g.x,g),at(xx,g)].sort((a,b)=>a-b);if(next[1]>next[0])apply(c,next)}
    });
    host.addEventListener('pointercancel',()=>cancel(c));
    host.addEventListener('lostpointercapture',()=>{if(c.gesture)cancel(c)});
    host.addEventListener('keydown',event=>{
      if(event.defaultPrevented)return;
      if(event.key==='Escape'){event.preventDefault();cancel(c)}
      if(event.key==='Home'){event.preventDefault();cancel(c);apply(c,null)}
      if(['ArrowLeft','ArrowRight'].includes(event.key)&&c.extent){event.preventDefault();cancel(c);const r=c.range||c.extent,d=(r[1]-r[0])*.2*(event.key==='ArrowLeft'?-1:1);apply(c,r.map(x=>x+d))}
    });
    return c;
  }
  function finish(c){
    const g=c.gesture;c.gesture=null;
    if(c.frame){cancelAnimationFrame(c.frame);c.frame=null}
    c.host.querySelector('.time-chart-selection')?.remove();c.host.classList.remove('time-chart-dragging');
    if(g&&c.host.hasPointerCapture(g.id))c.host.releasePointerCapture(g.id);
  }
  function cancel(c){const g=c.gesture;finish(c);if(g?.pan)apply(c,g.original)}
  function controls(c){
    c.tools.hidden=!c.extent;
    c.host.dataset.navigationMode=c.mode;
    for(const key of ['zoom','pan'])c.buttons[key].setAttribute('aria-pressed',String(c.mode===key));
    c.buttons.reset.textContent=c.options.resetLabel||'Full history';
    c.buttons.reset.disabled=!c.extent;
    const r=c.range||c.extent;
    c.label.textContent=r?`${date(r[0],c.options.intraday)} — ${date(r[1],c.options.intraday)}${c.options.scope?' · '+c.options.scope:''}`:'No observations';
  }
  function apply(c,range){
    c.range=clamp(range,c.extent);controls(c);
    if(c.options.onChange)c.options.onChange(c.range?.slice()||null);
    else c.redraw();
  }
  function view(id, rows, timeOf, redraw, bounds, options={}){
    const c=instances.get(id)||create(id);
    const times=rows.map(timeOf).filter(Number.isFinite);
    const extent=times.length?[Math.min(...times),Math.max(...times)]:null;
    if(!c)return {rows,range:extent,extent};
    if(c.key!==options.key){finish(c);c.range=null;c.key=options.key}
    c.extent=extent;c.options=options;c.bounds=bounds;c.redraw=redraw;
    if(Object.hasOwn(options,'range'))c.range=clamp(options.range,extent);else c.range=clamp(c.range,extent);
    controls(c);
    const range=c.range||extent;
    return {rows:range?rows.filter(row=>{const t=timeOf(row);return t>=range[0]&&t<=range[1]}):[],range,extent};
  }
  globalThis.ChartNavigation={view,clamp,
    clear:id=>{const c=instances.get(id);if(c){finish(c);c.extent=null;c.range=null;c.redraw=()=>{};controls(c)}},
    reset:id=>{const c=instances.get(id);if(c){cancel(c);apply(c,null)}}};
})();
</script>
'''


def with_chart_navigation(page: str) -> str:
    """Place controls before page code; standalone exports need no external assets."""
    if 'id="time-chart-navigation"' in page:
        return page
    return page.replace('</head>', CHART_NAVIGATION_HTML + '</head>', 1)
