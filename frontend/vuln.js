(function(){
  const apiKeyEl = document.getElementById('apiKey');
  const statusEl = document.getElementById('status');
  const findingsTBody = document.querySelector('#findingsTable tbody');
  const sbomInfo = document.getElementById('sbomInfo');
  const fileEl = document.getElementById('sbomFile');
  // spinner/toast helpers
  let pending = 0;
  function setLoading(on){
    pending += on?1:-1; pending = Math.max(0,pending);
    if(on && !document.getElementById('global-spinner')){
      const el=document.createElement('div'); el.id='global-spinner'; el.className='spinner-overlay'; el.innerHTML='<div class="spinner"></div>';
      document.body.appendChild(el);
    } else if(!on && pending===0){ const el=document.getElementById('global-spinner'); if(el) el.remove(); }
  }
  function toast(msg, kind){
    const t=document.createElement('div'); t.textContent=msg;
    t.style.cssText='position:fixed;right:12px;top:12px;background:'+(kind==='error'?'#3f1d1d':'#22313f')+';color:#fff;padding:8px 10px;border-radius:8px;z-index:110;box-shadow:0 2px 8px rgba(0,0,0,.25)';
    document.body.appendChild(t); setTimeout(()=>t.remove(), 2600);
  }
  function headers(){ const h={}; if(apiKeyEl.value) h['x-api-key']=apiKeyEl.value; return h; }
  async function listFindings(){
    statusEl.textContent='Loading findings...'; setLoading(true);
    try {
      const r = await fetch('/vuln/findings?limit=100', { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      findingsTBody.innerHTML='';
      (j.items||[]).forEach(it=>{
        const tr=document.createElement('tr');
        const sla = it.sla_due_days!=null ? `${it.sla_due_days}d` : '—';
        tr.innerHTML = `<td>${it.id||''}</td><td>${it.package||''}</td><td>${it.version||''}</td><td>${(it.cve||[]).join(', ')}</td><td>${(it.risk||0).toFixed?it.risk.toFixed(2):it.risk}</td><td>${sla}</td>`;
        findingsTBody.appendChild(tr);
      });
      statusEl.textContent='OK';
    } catch(e) { statusEl.textContent='Error '+e.message; toast('Findings error: '+e.message,'error'); }
    finally { setLoading(false); }
  }
  async function listSbomJobs(){
    setLoading(true);
    try {
      const r = await fetch('/scanner/sbom/jobs?limit=20', { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      sbomInfo.textContent = `Jobs: ${j.count||0}`;
    } catch(e) { sbomInfo.textContent = 'Jobs error'; toast('SBOM jobs error','error'); }
    finally { setLoading(false); }
  }
  async function uploadSbom(){
    const f = fileEl.files && fileEl.files[0]; if(!f){ toast('Choose a file','error'); return; }
    setLoading(true);
    try {
      const text = await f.text();
      const r = await fetch('/scanner/sbom/ingest', { method:'POST', headers: { ...headers(), 'Content-Type':'application/json' }, body: text });
      if(!r.ok) throw new Error(r.status);
      await listSbomJobs();
      toast('SBOM uploaded');
    } catch(e) { toast('Upload error '+e.message, 'error'); }
    finally { setLoading(false); }
  }
  document.getElementById('uploadSbom').addEventListener('click', uploadSbom);
  document.getElementById('refresh').addEventListener('click', ()=>{ listFindings(); listSbomJobs(); });
  // bootstrap
  listFindings(); listSbomJobs();
})();
