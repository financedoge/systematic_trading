const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('node:fs').readFileSync(0, 'utf8');
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, {
    value:'', textContent:'', innerHTML:'', hidden:false,
    classList:{toggle(){}}, querySelectorAll:()=>[]
  });
  return elements.get(id);
};
el('order-date-filter').value='today';
el('order-filter').value='all';
const now = '2026-09-25T14:10:00Z';
class Clock extends Date {
  constructor(...args) { super(...(args.length ? args : [now])); }
  static now() { return Date.parse(now); }
}
const test = String.raw`
const row=(id,date,status='filled',submitted='2026-09-25T13:44:26Z')=>({
  local_order_id:id,order_ref:id,broker_order_id:id,environment:'paper',status,
  submitted_at:submitted,updated_at:now,filled_quantity:10,remaining_quantity:0,
  order:{symbol:id,side:'buy',order_type:'twap',quantity:10,intended_trade_date:date},
  broker_observation:{status:'Filled',filled:10,quantity:10}
});
const filled=row('CURRENT','2026-09-25');
const missed=row('OLD-MISSED','2026-05-25','missed',null);
missed.broker_observation={};
const unknown=row('UNDATED',null,'filled',null);
const working=row('PREVIOUS-WORKING','2026-09-24','submitted','2026-09-24T14:00:00Z');
working.broker_observation.status='Submitted';
workspace={records:[missed,unknown,working,filled],client_id:101,snapshot:{checked_at:now,orders:[
  {order_ref:working.order_ref,broker_order_id:working.broker_order_id,client_id:101,status:'Submitted',source:'open'},
  {order_ref:'ext',broker_order_id:88,symbol:'EXTERNAL-WORKING',status:'Submitted',source:'open',side:'BUY',quantity:1,checked_at:now},
  {order_ref:'ext-old',broker_order_id:89,symbol:'EXTERNAL-COMPLETED',status:'Filled',source:'completed',side:'BUY',quantity:1,checked_at:now}
]}};
renderWorkspace();
let html=el('gateway-order-table').innerHTML;
assert.match(html,/CURRENT/);
assert.doesNotMatch(html,/OLD-MISSED|UNDATED|PREVIOUS-WORKING|EXTERNAL-COMPLETED/);
assert.match(html,/EXTERNAL-WORKING/);
assert.match(html,/Submission unknown/);
assert.equal(el('orders-total').textContent,1);
assert.match(el('order-filter-summary').textContent,/1 working outside this date range/);
assert.match(el('order-timezone-note').textContent,/Trade dates: New York/);
assert.match(html,/Submitted \/ updated/);
assert.match(html,/2026-09-25/);

// Completed orders remain in the durable ledger when Gateway no longer retains them.
workspace.snapshot={checked_at:now,orders:[]};
renderWorkspace();
assert.match(el('gateway-order-table').innerHTML,/CURRENT/);
assert.match(el('gateway-order-table').innerHTML,/Recorded execution history/);
el('order-filter').value='working'; renderWorkspace();
assert.match(el('gateway-order-table').innerHTML,/Filled orders remain available/);
el('order-filter').value='filled'; renderWorkspace();
assert.match(el('gateway-order-table').innerHTML,/CURRENT/);
el('order-filter').value='missed'; renderWorkspace();
assert.doesNotMatch(el('gateway-order-table').innerHTML,/OLD-MISSED/);
el('order-date-filter').value='all'; renderWorkspace();
assert.match(el('gateway-order-table').innerHTML,/OLD-MISSED/);
assert.match(el('gateway-order-table').innerHTML,/Not submitted/);
el('order-filter').value='terminal'; renderWorkspace();
assert.doesNotMatch(el('gateway-order-table').innerHTML,/OLD-MISSED/);
assert.match(el('gateway-order-table').innerHTML,/UNDATED/);

el('order-filter').value='all'; renderWorkspace();
html=el('gateway-order-table').innerHTML;
assert.ok(html.indexOf('CURRENT')<html.indexOf('OLD-MISSED'));
el('order-date-filter').value='week';
assert.deepEqual(orderDateBounds(),{start:'2026-09-19',end:'2026-09-25'});
assert.equal(orderTradeDate({...unknown,submitted_at:'2026-09-26T00:30:00Z'}),'2026-09-25');
assert.equal(orderTradeDate(missed),'2026-05-25');
assert.equal(orderTradeDate(unknown),'');
assert.equal(orderDateAt('2026-11-01T04:30:00Z'),'2026-11-01');
assert.equal(orderDateAt('2026-11-02T04:30:00Z'),'2026-11-01');
el('order-date-filter').value='range';
el('order-date-start').value='2026-05-25'; el('order-date-end').value='2026-05-25';
renderWorkspace();
assert.equal(el('order-date-range').hidden,false);
assert.match(el('gateway-order-table').innerHTML,/OLD-MISSED/);
assert.doesNotMatch(el('gateway-order-table').innerHTML,/CURRENT/);
el('order-date-start').value='2026-09-25'; renderWorkspace();
assert.match(el('order-filter-summary').textContent,/valid start and end/);

// Durable full fills take precedence over a stale working observation.
filled.broker_observation.status='Submitted'; filled.broker_observation.filled=0;
filled.broker_observation.quantity=0;
assert.equal(category(filled),'terminal');
assert.equal(displayedOrderQuantity(filled),10);
assert.equal(displayedOrderQuantity({...working,broker_observation:{quantity:0}}),10);
el('order-date-filter').value='today'; renderWorkspace();
html=el('gateway-order-table').innerHTML;
assert.match(html,/10 \/ 10/);
assert.match(html,/data-action="cancel"[^>]*disabled/);
assert.match(html,/Filled/);
filled.average_fill_price='101.1234'; filled.order.currency='USD';
executionAnalytics[filled.local_order_id]={status:'ready',twap_price:'100',slippage_bps:'112.34',price_cost:'11.234',currency:'USD',coverage:'100%',bar_count:30,window_start:now,window_end:now};
renderWorkspace(); html=el('gateway-order-table').innerHTML;
assert.match(html,/Avg fill/); assert.match(html,/TWAP estimate/);
assert.match(html,/101.1234/); assert.match(html,/112.34 bps/); assert.match(html,/11.23 USD/);
assert.match(html,/100% coverage/);
executionAnalytics[filled.local_order_id]={status:'unavailable',message:'Missing coverage'};
renderWorkspace(); html=el('gateway-order-table').innerHTML;
assert.doesNotMatch(html,/112.34 bps/); assert.match(html,/Missing coverage/);
`;
vm.runInNewContext(source.split("    el('close-order-dialog')")[0]+test,
  {assert,el,Date:Clock,Intl,now,esc:String,fmtDateTime:String,fmtMoney:String,fmtMaybeMoney:String});
console.log('Blotter date, status, history, timezone, ordering and action checks passed.');
