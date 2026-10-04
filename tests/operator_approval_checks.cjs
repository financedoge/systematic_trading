const assert = require('node:assert/strict'), vm = require('node:vm');
const html = require('node:fs').readFileSync(0, 'utf8');
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, {innerHTML:'', textContent:'', value:'', disabled:false,
    hidden:false, querySelectorAll:()=>[], addEventListener(){}});
  return elements.get(id);
};
const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const ctx = vm.createContext({assert, el, esc, console, process, encodeURIComponent,
  fmtMoney:String, fmtDateTime:String, fmtPct:String,
  AssetNames:{cell:symbol=>`<td class="asset-name">${esc(symbol)} asset</td>`},
  confirm:()=>true});
vm.runInContext(html.slice(html.indexOf('const state ='), html.indexOf('const state =')+html.slice(html.indexOf('const state =')).indexOf('\n    };')+7), ctx);
vm.runInContext(html.slice(html.indexOf('function renderList()'), html.indexOf('async function resetPortfolioToIb()')), ctx);
vm.runInContext(String.raw`
(async () => {
  const proposal = id => ({proposal_id:id,status:'pending',orders:[{symbol:'GLD',side:'buy',quantity:2,
    currency:'USD',reference_price:400,notional_cnh:5600,order_type:'market',rationale:'<unsafe>',
    execution_start_time:'09:30:00 America/New_York',execution_end_time:'10:00:00 America/New_York'}],
    targets:[],as_of:'2026-10-02',intended_trade_date:'2026-10-05',summary:'Trade <unsafe>',reasoning:{drivers:[]}});
  state.proposals=[proposal('A'),proposal('B')]; state.selectedId='A';
  assert.match(submitResultMessage({records:[{status:'pending_submit'}]},'Approved',6),/0 of 6.*1 uncertain.*5 not attempted/);
  assert.match(submitResultMessage({records:[{status:'submitted'}]},'Approved',6),/1 of 6.*5 not attempted/);
  assert.equal(submitResultMessage({records:[{status:'submitted'}]},'Approved and submitted',1),'Approved and submitted 1 TWAP paper order(s)');
  state.reconciliation={has_breaks:false,unavailable:false};
  api=async()=>[];
  state.decisionDrafts.A='Keep A comment';
  await renderSelected();
  assert.equal(el('decision-comment').value,'Keep A comment');
  assert.equal(el('approve-btn').disabled,false);
  assert.equal(el('approve-btn').textContent,'Approve & submit paper orders');
  assert.match(el('orders-table').innerHTML,/USD/);
  assert.match(el('orders-table').innerHTML,/America\/New_York/);
  assert.match(el('orders-table').innerHTML,/&lt;unsafe&gt;/);
  assert.ok(!el('proposal-detail').innerHTML.includes('<unsafe>'));
  state.selectedId='B'; await renderSelected();
  assert.equal(el('decision-comment').value,'');
  state.selectedId='A'; await renderSelected();
  assert.equal(el('decision-comment').value,'Keep A comment');

  // Late responses from another proposal, or an older request for this one,
  // must not overwrite the current proposal's execution evidence.
  const pending=[]; api=()=>new Promise(resolve=>pending.push(resolve));
  const a=renderBrokerRecords('A');
  state.selectedId='B'; const b=renderBrokerRecords('B');
  pending[1]([]); await b;
  pending[0]([{order_index:0,filled_quantity:99}]); await a;
  assert.equal(state.brokerRecords.length,0);
  assert.equal(el('metric-filled').textContent,'0 / 2');
  const c=renderBrokerRecords('B'), d=renderBrokerRecords('B');
  pending[3]([]); await d;
  pending[2]([{order_index:0,filled_quantity:99}]); await c;
  assert.equal(state.brokerRecords.length,0);
  api=async()=>{throw Error('offline');};
  await renderBrokerRecords('B');
  assert.equal(el('approve-btn').disabled,true);
  assert.equal(el('resubmit-failed-btn').hidden,true);
  assert.match(el('broker-records').innerHTML,/unavailable/);
  api=async()=>[]; await renderBrokerRecords('B');
  assert.equal(el('approve-btn').disabled,false);
  state.reconciliation.has_breaks=true; setButtons(true);
  assert.equal(el('approve-btn').disabled,true);
  state.reconciliation.has_breaks=false; setButtons(true);

  // Background refresh cannot undo the busy guard or permit double submission.
  let posts=0, finish;
  api=async(path,options)=>{
    if(options?.method==='POST') {posts++; assert.match(path,/B\/approve-and-submit$/);
      assert.equal(JSON.parse(options.body).comment,'Decision B');
      return new Promise(resolve=>finish=resolve);}
    return [];
  };
  loadProposals=async()=>setButtons(true);
  el('decision-comment').value='Decision B';
  const decision=decide('approved');
  setButtons(true);
  assert.equal(el('approve-btn').disabled,true);
  await decide('approved');
  assert.equal(posts,1);
  finish({broker_submission:{records:[]}}); await decision;
  assert.equal(state.decisionBusy,false);
  state.selectedId=null; await renderSelected();
  assert.equal(el('approve-btn').disabled,true);
  assert.equal(el('decision-comment').value,'');
  console.log('Approval selection, drafts, stale responses, failed reads, gates and duplicate-submit protection passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
`, ctx);
