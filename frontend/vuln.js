(function(){
  const apiKeyEl = document.getElementById('apiKey');
  const statusEl = document.getElementById('status');
  const findingsTBody = document.querySelector('#findingsTable tbody');
  const sbomInfo = document.getElementById('sbomInfo');
  const sourceBanner = document.getElementById('sourceBanner');
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
  function headers(){ 
    const h = (typeof window.apiHeaders==='function') ? window.apiHeaders() : {};
    const inlineKey = (apiKeyEl && apiKeyEl.value || '').trim();
    if (inlineKey) { h['X-API-Key'] = inlineKey; localStorage.setItem('X_API_KEY', inlineKey); }
    return h; 
  }
  async function listFindings(){
    statusEl.textContent='Loading findings...'; setLoading(true);
    try {
  const r = await fetch((typeof window.apiUrl==='function'?window.apiUrl('/vuln/findings?limit=100'):'/vuln/findings?limit=100'), { headers: headers() });
      if(!r.ok) throw new Error(r.status);
  const j = await r.json();
      findingsTBody.innerHTML='';
      (j.items||[]).forEach(it=>{
        const tr=document.createElement('tr');
        const sla = it.sla_due_days!=null ? `${it.sla_due_days}d` : '—';
        const riskv = (it.risk!=null? it.risk : it.risk_score);
        const riskStr = (typeof riskv==='number' && riskv.toFixed) ? riskv.toFixed(2) : (riskv||'');
        tr.innerHTML = `<td>${it.id||''}</td><td>${it.package||''}</td><td>${it.version||''}</td><td>${(it.cve||[]).join(', ')}</td><td>${riskStr}</td><td>${sla}</td>`;
        findingsTBody.appendChild(tr);
      });
      statusEl.textContent='OK';
      try {
        const src = (j && j.source) || 'memory';
        if (sourceBanner) {
          sourceBanner.classList.remove('hidden','postgres','memory','mock');
          sourceBanner.classList.add(src);
          const label = src === 'postgres' ? 'Postgres (persistent DB)' : src === 'mock' ? 'Mock (SBOM-based demo data)' : 'Memory (ephemeral)';
          sourceBanner.textContent = `Findings source: ${label}`;
        }
      } catch {}
    } catch(e) { statusEl.textContent='Error '+e.message; toast('Findings error: '+e.message,'error'); }
    finally { setLoading(false); }
  }
  async function listSbomJobs(){
    setLoading(true);
    try {
      // No job listing endpoint available, show upload status instead
      sbomInfo.textContent = 'Ready for upload';
    } catch(e) { sbomInfo.textContent = 'Jobs error'; toast('SBOM jobs error','error'); }
    finally { setLoading(false); }
  }
  async function uploadSbom(){
    const f = fileEl.files && fileEl.files[0]; 
    if(!f){ 
      console.log('No file selected');
      toast('Choose a file','error'); 
      return; 
    }
    
    console.log('Starting upload for file:', f.name);
    setLoading(true);
    
    try {
      const text = await f.text();
      console.log('File text length:', text.length);
      
      const sbomData = JSON.parse(text);
      console.log('Parsed SBOM successfully, components:', sbomData.components?.length || 0);
      
      // Use the correct endpoint: /vuln/ingest_sbom
      const payload = {
        asset_name: f.name.replace('.json', ''),
        document: sbomData
      };
      console.log('Payload created:', payload);
      
      const requestHeaders = { ...headers(), 'Content-Type':'application/json' };
      console.log('Request headers:', requestHeaders);
      
      const r = await fetch((typeof window.apiUrl==='function'?window.apiUrl('/vuln/ingest_sbom'):'/vuln/ingest_sbom'), { 
        method:'POST', 
        headers: requestHeaders, 
        body: JSON.stringify(payload) 
      });
      
      console.log('Response status:', r.status);
      console.log('Response ok:', r.ok);
      
      if(!r.ok) {
        const errorText = await r.text();
        console.error('Response error text:', errorText);
        throw new Error(`${r.status} ${r.statusText}: ${errorText}`);
      }
      
      const result = await r.json();
      console.log('Upload result:', result);
      
      sbomInfo.textContent = `Uploaded: ${result.count || 0} components`;
      toast(`SBOM uploaded successfully! Found ${result.count || 0} components`);
      
      // Refresh findings after upload
      setTimeout(() => listFindings(), 1000);
      
    } catch(e) { 
      console.error('Upload error:', e);
      toast('Upload error: ' + e.message, 'error'); 
    }
    finally { 
      console.log('Upload finished, clearing loading state');
      setLoading(false); 
    }
  }
  document.getElementById('uploadSbom').addEventListener('click', uploadSbom);
  document.getElementById('refresh').addEventListener('click', ()=>{ listFindings(); listSbomJobs(); });
  // bootstrap
  // Set default API key
  apiKeyEl.value = localStorage.getItem('X_API_KEY') || 'neuron-ai-demo-key-2024';
  listFindings(); listSbomJobs();
})();
