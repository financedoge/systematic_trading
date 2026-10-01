"""Progress and publication updates for an open saved strategy report."""
from html import escape
import json


def report_refresh_banner(publication, status):
    published = str(publication["published_at"])
    message = status.get("strategy_freshness_message", "")
    if status.get("errors"):
        message += " Refresh needs attention; retaining the last complete report."
    # JSON string escaping also prevents a publication field from ending script.
    version = json.dumps(publication["version"]).replace("<", "\\u003c")
    label = json.dumps(f"Saved analytical report · calculated {published} UTC").replace("<", "\\u003c")
    return (
        '<div id="strategy-refresh-status" role="status" style="padding:8px;background:#edf2f7;'
        'color:#334155;font:13px sans-serif">'
        f"Saved analytical report · calculated {escape(published)} UTC · {escape(message)}</div>"
        + _POLL_SCRIPT.replace("__VERSION__", version).replace("__LABEL__", label)
    )


_POLL_SCRIPT = """<script>
(()=>{
  const version=__VERSION__, label=__LABEL__;
  const banner=document.getElementById('strategy-refresh-status');
  async function poll(){
    try {
      const response=await fetch('/api/v1/analytics/status',{cache:'no-store'});
      if(!response.ok) throw new Error('Status unavailable');
      const status=await response.json();
      if(status.strategy_serving_version && status.strategy_serving_version!==version){
        window.location.reload(); return;
      }
      const messages=[label,status.strategy_freshness_message];
      const job=status.research_job;
      if(job==='tracked-strategies'){
        const count=(status.compute?.completed||[]).length;
        const total=status.compute?.resources?.jobs;
        messages.push('Calculating strategies'+(total?` (${count}/${total} runs complete)`:'')+'; showing the last complete report.');
      } else if(job==='strategy-fx'){
        messages.push('Checking observed FX for daily valuations.');
      } else if(job==='governed-publication'){
        messages.push('Checking audited daily price publication.');
      } else if(job==='strategy-serving'){
        messages.push('Publishing updated reports.');
      }
      if(Object.keys(status.errors||{}).length){
        messages.push('Refresh needs attention: '+Object.values(status.errors).join('; '));
      }
      banner.textContent=messages.filter(Boolean).join(' · ');
    } catch(error){
      banner.textContent=label+' · Update status unavailable; retrying automatically.';
    }
    window.setTimeout(poll,10000);
  }
  poll();
})();
</script>"""
