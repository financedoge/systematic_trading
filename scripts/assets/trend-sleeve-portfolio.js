function portfolio(){return DATA.portfolio[el('pera').value+'_'+el('parm').value+'_c5d0']}
function portfolioDates(){const z=portfolio();el('pdate').innerHTML=z.decisions.map(d=>`<option>${d.date}</option>`).join('');el('pdate').value=z.decisions.at(-1).date;portfolioTable()}
function portfolioTable(){const z=portfolio(),d=z.decisions.find(d=>d.date===el('pdate').value),rr=z.ranks.find(x=>x.date===d.date);const rows=rr?rr.rows:z.symbols.map((symbol,index)=>({symbol,index}));
 el('pinfo').textContent=`Decision ${d.date}; execute ${d.execution_date}; ${d.weights.filter(w=>w>0).length} funded sleeves; intended cash ${pct(d.theoretical.at(-1))}. Holdings can differ at execution because pending daily exits take priority.`;
 el('pranks').innerHTML=rows.map((r,i)=>`<tr class="${d.weights[r.index]>0?'selected':''}"><td><button data-symbol="${r.symbol}">${i+1} · ${r.symbol}</button></td><td>${pct(r.short_return)}</td><td>${num(r.short_sharpe)}</td><td>${pct(r.long_return)}</td><td>${num(r.long_sharpe)}</td><td>${num(r.score)}</td><td>${pct(d.weights[r.index])}</td><td>${pct(d.theoretical[r.index])}</td></tr>`).join('');
 const a=DATA.attribution[el('pera').value+'_'+el('parm').value+'_c5d0'];el('pattrs').innerHTML=a.map(r=>`<tr><td><button data-symbol="${r.symbol}">${r.symbol}</button></td><td>${pct(r.pnl)}</td><td>${pct(r.fee)}</td><td>${pct(r.average_weight)}</td><td>${r.selected_days}</td><td>${r.fills}</td></tr>`).join('');
}
const shadowRender=render;
render=function(){shadowRender();if(indices.length<2){el('actualfills').innerHTML='';return}const q=c(),z=DATA.portfolio[el('era').value+'_equal_c5d0'];
 const fills=z.fills.filter(f=>f.symbol===el('etf').value&&f.date>=el('from').value&&f.date<=el('to').value);
 el('actualfills').innerHTML=fills.map(f=>`<tr><td>${f.date}</td><td>${f.side}</td><td>${f.reason}</td><td>${f.price.toFixed(2)}</td><td>${pct(f.notional)}</td><td>${pct(f.fee)}</td></tr>`).join('');
 const prices=indices.flatMap(i=>[q.high[i],q.low[i],q.stop[i]]).filter(v=>v!=null),lo=Math.min(...prices),hi=Math.max(...prices);let svg='';
 fills.forEach(f=>{const j=indices.findIndex(i=>q.days[i]===f.date);if(j<0)return;const x=75+1090*j/(indices.length-1),y=280-230*(f.price-lo)/(hi-lo||1);svg+=`<circle cx="${x}" cy="${y}" r="4.5" fill="none" stroke="#d78020" stroke-width="1.5"><title>${f.date} ${f.side} ${f.reason} ${f.price.toFixed(2)}</title></circle>`});el('chart').innerHTML+=svg;
};
for(const k of ['pera','parm'])el(k).addEventListener('change',portfolioDates);el('pdate').addEventListener('change',portfolioTable);
for(const k of ['pranks','pattrs'])el(k).addEventListener('click',e=>{const symbol=e.target.dataset?.symbol;if(!symbol)return;el('era').value=el('pera').value;choose();el('etf').value=symbol;choose();el('chart').scrollIntoView?.({behavior:'smooth'})});
el('worstcontributor').addEventListener('click',()=>{el('etf').value=DATA.attribution[el('era').value+'_equal_c5d0'][0].symbol;choose()});
el('pera').value='late';el('parm').value='equal';portfolioDates();render();
