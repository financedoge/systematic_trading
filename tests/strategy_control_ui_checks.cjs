const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(0, 'utf8').replace(/\r\n/g,'\n');
const nodes = new Map();
const weights = [{value:'100',dataset:{weight:'A'}}];
let focused, responseKind='ok', finishPreview, timeoutCallback, timerCleared=false;
const requests=[];
const previewResponse={effects:'test',approval_policy:'test',blockers:[],evidence:{},rollback:[]};
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {id, value:'', disabled:false,attributes:{},
    setAttribute(key,value) { this.attributes[key]=value;if (key==='disabled') this.disabled=true; },
    focus(){focused=id;},
    scrollIntoView(){}, addEventListener(){}});
  return nodes.get(id);
}
const root = {querySelector:s=>node(s.slice(1)),querySelectorAll:()=>weights,
  scrollIntoView(){}};
let calls=0;
const context = {document:{createElement:()=>root,querySelector:()=>({prepend(){}}),addEventListener(){}},
  location:{pathname:'/strategies'}, setInterval(){}, URLSearchParams,
  AbortController, setTimeout(callback){timeoutCallback=callback;timerCleared=false;return 1},clearTimeout(){timerCleared=true},
  crypto:{randomUUID:()=>'test-event'},
  fetch:async(url,options)=>{calls++;requests.push({url,body:options.body?JSON.parse(options.body):null});
    if(responseKind==='timeout')return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('Aborted'))));
    if(responseKind==='delayed')return new Promise(resolve=>finishPreview=()=>resolve({ok:true,json:async()=>previewResponse}));
    return responseKind==='ok'?{ok:true,json:async()=>previewResponse}:{ok:false,json:async()=>({detail:[
      {type:'string_too_short',loc:['body','change','reason'],msg:'String should have at least 1 character',input:''}]})};}};
vm.createContext(context);
const instrumented = source.replace('  load();\n  setInterval(', `
  globalThis.reviewTest={
    setup(){data={state:{active:{allocations:[{strategy_key:'A',weight:'1'}]},sota_key:'A'},candidates:[{strategy_key:'A',name:'A'}]};edit()},
    review(){preview={effects:'test',approval_policy:'test',blockers:[],evidence:{},rollback:[]};change={allocations:[]};renderPreview()},
    preview:previewEditor,cancel:cancelEditor,errorText,call,
    readiness:renderCalculationStatus,
    blocked(){data={state:{sota_key:'A',active:{allocations:[]},pending:{change:{effective_close:'2026-10-07',reason:'Test'}}},candidates:[],rules:{},history:[],activation_blockers:[],pending_phase:'blocked',pending_status:'Native replay failed through 2026-10-07',calculation_status:{severity:'error',message:'F3: three attempts exhausted'}};render();return root.innerHTML}
  };
  setInterval(`);
assert.notStrictEqual(instrumented, source);
vm.runInContext(instrumented, context);
assert.match(context.reviewTest.blocked(), /Allocation handover blocked/);
assert.match(root.innerHTML, /role="alert" class="sc-error">Native replay failed/);
assert.match(node('sc-calculation-status').innerHTML, /sc-error/);
assert.match(node('sc-calculation-status').innerHTML, /F3: three attempts exhausted/);
context.reviewTest.readiness({severity:'warning',message:'Expected Oct 7; FX Oct 6 <unsafe>'});
assert.match(node('sc-calculation-status').innerHTML, /sc-warning/);
assert.match(node('sc-calculation-status').innerHTML, /&lt;unsafe&gt;/);
context.reviewTest.readiness({severity:'ok',message:'Current'});
assert.strictEqual(node('sc-calculation-status').innerHTML,'');
context.reviewTest.setup();
context.reviewTest.review();
assert.strictEqual(typeof node('sc-editor').oninput,'function');
node('sc-editor').oninput({target:{id:'sc-reviewed'}});
node('sc-reviewed').onchange({target:{checked:true}});
assert.strictEqual(node('sc-confirm').disabled,false);
node('sc-editor').oninput({target:{id:'sc-cap'}});
assert.strictEqual(node('sc-confirm').disabled,true);
node('sc-reviewed').onchange({target:{checked:true}});
assert.strictEqual(node('sc-confirm').disabled,true,'Rechecking cannot revive an invalid preview');
(async()=>{
  await node('sc-confirm').onclick();assert.strictEqual(calls,0);
  node('sc-operator').value='  Tester  ';node('sc-reason').value='';
  await context.reviewTest.preview();
  assert.strictEqual(calls,0,'Empty reason must not call the API');
  assert.strictEqual(focused,'sc-reason');
  assert.strictEqual(node('sc-reason-error').textContent,'Enter a reason for this change.');
  assert.strictEqual(node('sc-reason').attributes['aria-invalid'],'true');
  assert.strictEqual(weights[0].value,'100','Validation must preserve the allocation');
  assert.strictEqual(node('sc-operator').value,'  Tester  ','Validation must preserve entered text');
  node('sc-reason').value='  \n  ';await context.reviewTest.preview();assert.strictEqual(calls,0);
  node('sc-operator').value='';node('sc-reason').value='Reviewed paper results';
  await context.reviewTest.preview();assert.strictEqual(calls,0);assert.strictEqual(focused,'sc-operator');
  node('sc-operator').value='  Tester  ';node('sc-reason').value='  Reviewed paper results  ';
  node('sc-editor').oninput({target:{id:'sc-reason'}});
  assert.strictEqual(node('sc-reason-error').hidden,true);
  assert.doesNotThrow(()=>node('sc-editor').oninput({target:{id:''}}));
  responseKind='server422';await context.reviewTest.preview();
  assert.strictEqual(node('sc-message').textContent,'Enter a reason for this change.');
  assert.strictEqual(focused,'sc-reason');assert.strictEqual(node('sc-preview').disabled,false);
  responseKind='ok';await context.reviewTest.preview();
  assert.strictEqual(requests.at(-1).body.operator,'Tester');
  assert.strictEqual(requests.at(-1).body.reason,'Reviewed paper results');
  assert.strictEqual(requests.at(-1).body.allocations[0].weight,'1');
  assert.strictEqual(node('sc-confirm').disabled,true,'Preview does not grant approval');
  assert.strictEqual(context.reviewTest.errorText('Account changed. Preview again.'),'Account changed. Preview again.');
  assert.strictEqual(context.reviewTest.errorText([{loc:['body','allocations',0,'weight'],msg:'Input should be greater than 0'}]),'Capital weight: Input should be greater than 0');
  const beforeCancel=calls;context.reviewTest.cancel();
  node('sc-cancel-operator').value='Tester';node('sc-cancel-reason').value='';
  await node('sc-cancel-confirm').onclick();assert.strictEqual(calls,beforeCancel);assert.strictEqual(focused,'sc-cancel-reason');
  assert.doesNotThrow(()=>node('sc-editor').oninput({target:{id:'sc-cancel-reason'}}));
  assert.strictEqual(node('sc-cancel-reason-error').hidden,true);
  // A second editor opening or input change can happen while the preview API is
  // still running. The stale response must neither dereference null change nor
  // approve the newly entered form with the previous form's review token.
  context.reviewTest.setup();node('sc-operator').value='Tester';node('sc-reason').value='Reason';
  node('sc-preview-result').innerHTML='';responseKind='delayed';
  const stale=context.reviewTest.preview();context.reviewTest.setup();
  node('sc-preview-result').innerHTML='new editor';finishPreview();await stale;
  assert.strictEqual(node('sc-preview-result').innerHTML,'new editor');
  assert.strictEqual(node('sc-message').textContent,'');
  const edited=context.reviewTest.preview();node('sc-editor').oninput({target:{id:'sc-cap'}});
  finishPreview();await edited;assert.strictEqual(node('sc-preview-result').innerHTML,'new editor');
  responseKind='ok';previewResponse.routing_warnings=['IB snapshot is stale'];
  await context.reviewTest.preview();
  assert.match(node('sc-preview-result').innerHTML,/sc-warning/);
  assert.ok(!node('sc-preview-result').innerHTML.includes('sc-error'), 'Non-blocking routing readiness must be yellow');
  responseKind='timeout';const stalled=context.reviewTest.call();timeoutCallback();
  await assert.rejects(stalled,/timed out after 20 seconds.*Freshness cannot be verified/);
  assert.strictEqual(timerCleared,true);
})().catch(error=>{console.error(error);process.exitCode=1;});
