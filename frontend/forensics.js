(function(){
  const apiKeyEl = document.getElementById('apiKey');
  const assetEl = document.getElementById('asset');
  const dumpEl = document.getElementById('dumpPath');
  const jobsTbody = document.querySelector('#jobsTable tbody');
  const statusEl = document.getElementById('status');
  const jobHeader = document.getElementById('jobHeader');
  const jobMeta = document.getElementById('jobMeta');
  const evTbody = document.querySelector('#evidenceTable tbody');
  const rawView = document.getElementById('rawView');
  const autoPollEl = document.getElementById('autoPoll');
  const verifyOut = document.getElementById('verifyOut');
  // Optional filter elements (added if present in HTML)
  const filterModality = document.getElementById('filterModality');
  const filterStatus = document.getElementById('filterStatus');
  const searchInput = document.getElementById('searchJobs');

  // spinner/toast helpers
  let pending = 0;
  function setLoading(on){ pending += on?1:-1; pending=Math.max(0,pending);
    if(on && !document.getElementById('global-spinner')){ const el=document.createElement('div'); el.id='global-spinner'; el.className='spinner-overlay'; el.innerHTML='<div class="spinner"></div>'; document.body.appendChild(el);} else if(!on && pending===0){ const el=document.getElementById('global-spinner'); if(el) el.remove(); }
  }
  function toast(msg, kind){ const t=document.createElement('div'); t.textContent=msg; t.style.cssText='position:fixed;right:12px;top:12px;background:'+(kind==='error'?'#3f1d1d':'#22313f')+';color:#fff;padding:8px 10px;border-radius:8px;z-index:110;box-shadow:0 2px 8px rgba(0,0,0,.25)'; document.body.appendChild(t); setTimeout(()=>t.remove(), 2600); }
  function headers(){ const h={}; if(apiKeyEl.value) h['x-api-key']=apiKeyEl.value; return h; }

  function badge(status){
    const map = {submitted:'#334155', queued:'#334155', running:'#3b82f6', done:'#16a34a', error:'#dc2626'};
    const bg = map[String(status||'').toLowerCase()] || '#334155';
    return `<span class=badge style="background:${bg}">${status||''}</span>`;
  }

  async function listJobs(){
    statusEl.textContent='Loading jobs...'; setLoading(true);
    try {
      const r = await fetch('/forensics/jobs?limit=50', { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      jobsTbody.innerHTML='';
      (j.items||[]).forEach(it => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><a href="#" data-jid="${it.id}">${it.id||''}</a></td>`+
                       `<td>${it.modality||'memory'}</td>`+
                       `<td>${badge(it.status)}</td>`+
                       `<td>${it.submitted_ts? new Date(it.submitted_ts*1000).toISOString():'—'}</td>`;
        tr.addEventListener('click', ()=> selectJob(it.id));
        jobsTbody.appendChild(tr);
      });
      statusEl.textContent='OK';
    } catch(e){ statusEl.textContent='Error '+e.message; toast('Jobs error: '+e.message,'error'); }
    finally { setLoading(false); }
  }

  let currentJobId = null; let pollTimer = null;
  async function selectJob(jobId){
    currentJobId = jobId; verifyOut.textContent = '';
    await loadJob(jobId);
    schedulePoll();
  }
  function schedulePoll(){
    if(pollTimer){ clearTimeout(pollTimer); pollTimer=null; }
    if(!autoPollEl.checked || !currentJobId) return;
    pollTimer = setTimeout(()=> loadJob(currentJobId).then(schedulePoll), 3000);
  }

  function summarizeArtifact(art){
    const t = String(art.type||''); const d = art.data||{};
    try{
      if(t.includes('windows.pslist')){
        const pid = d.PID ?? d.Pid ?? d.pid; const ppid = d.PPID ?? d.Ppid ?? d.ppid; const name = d.Name || d.ImageFileName || '';
        const user = d.User || d.Username || d.SessionName || '';
        const start = d.CreateTime || d.StartTime || d.Start || '';
        return `pid=${pid} ppid=${ppid} name=${name} user=${user} start=${start}`;
      }
      if(t.includes('windows.netscan')){
        const la = d.LocalAddr || d.LAddr || ''; const lp = d.LocalPort || d.LPort || '';
        const ra = d.ForeignAddr || d.RAddr || ''; const rp = d.ForeignPort || d.FPort || '';
        const state = d.State || '';
        const proc = d.Owner || d.Image || d.Process || '';
        return `${la}:${lp} ${state} ${ra}:${rp} ${proc}`;
      }
      if(t.includes('dlllist')){
        const proc = d.Process || d.Image || d.Name || '';
        const dll = d.Path || d.DLL || d.Module || '';
        const base = d.Base || d.BaseAddress || d.LoadAddress || '';
        return `${proc} -> ${dll} @ ${base}`;
      }
      if(t.includes('handles')){
        const pid = d.PID || d.Pid || '';
        const obj = d.Object || d.ObjectName || '';
        const typ = d.Type || d.ObjectType || '';
        const acc = d.GrantedAccess || d.Access || '';
        return `pid=${pid} ${typ} ${obj} access=${acc}`;
      }
      if(t === 'yara.match'){
        const rule = d.rule || ''; const tags = (d.tags||[]).join(',');
        const s = (d.strings||[]).slice(0,3).map(x=>x.id+':'+x.value).join(' | ');
        return `rule=${rule} tags=[${tags}] ${s}`;
      }
    }catch(e){ /* ignore */ }
    return JSON.stringify(art.data||{}).slice(0,160);
  }

  function renderArtifacts(arts){
    evTbody.innerHTML='';
    (arts||[]).forEach(a => {
      const tr = document.createElement('tr');
      const sev = String(a.severity||'low').toLowerCase();
      const color = sev==='high'? '#dc2626' : sev==='medium'? '#ca8a04' : '#334155';
      tr.innerHTML = `<td>${a.type||''}</td>`+
                     `<td>${summarizeArtifact(a)}</td>`+
                     `<td><span class=badge style="background:${color}">${sev}</span></td>`;
      tr.addEventListener('click', ()=> {
        rawView.textContent = JSON.stringify(a, null, 2);
      });
      evTbody.appendChild(tr);
    });
    if((arts||[]).length===0){ evTbody.innerHTML = '<tr><td colspan=3 style="color:#94a3b8">No artifacts</td></tr>'; }
  }

  async function loadJob(jobId){
    if(!jobId) return;
    setLoading(true);
    try {
      const r = await fetch(`/forensics/jobs/${jobId}`, { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      const job = j.job || j;
      const res = job.result || {};
      jobHeader.innerHTML = `Job <code>${job.id}</code> ${badge(job.status)}`;
      jobMeta.textContent = `submitted: ${fmtTs(job.submitted_ts)} | started: ${fmtTs(res.started)} | done: ${fmtTs(res.completed)}`;
      renderArtifacts(res.artifacts || []);
      // Surface summaries and warnings inline above the raw JSON
      const summaries = [];
      if(res.warnings && Array.isArray(res.warnings) && res.warnings.length){ summaries.push(`warnings: ${res.warnings.join('; ')}`); }
      if(res.volatility_summary){ summaries.push(`volatility: ${JSON.stringify(res.volatility_summary)}`); }
      if(res.yara_summary){ summaries.push(`yara: ${JSON.stringify(res.yara_summary)}`); }
      rawView.textContent = (summaries.length? summaries.join('\n')+'\n\n' : '') + JSON.stringify(job, null, 2);
    } catch(e){ toast('Load job error '+e.message, 'error'); }
    finally { setLoading(false); }
  }

  function fmtTs(ts){ return ts? new Date(ts*1000).toISOString() : '—'; }

  function artifactsToTimeline(job){
    const res = job.result || {};
    const ts = (res.completed||job.completed||job.submitted_ts||Date.now()/1000);
    return (res.artifacts||[]).map((a,i)=>({ idx:i, ts, type:a.type, severity:a.severity, summary:summarizeArtifact(a) }));
  }

  function exportJSON(job){
    const blob = new Blob([JSON.stringify(job, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`job-${job.id}.json`; a.click(); URL.revokeObjectURL(url);
  }
  function exportCSV(job){
    const rows = [['idx','ts','type','severity','summary']];
    artifactsToTimeline(job).forEach(r=> rows.push([r.idx, r.ts, r.type, r.severity, (r.summary||'').replace(/\n/g,' ').replace(/,/g,';')]));
    const csv = rows.map(r=> r.map(x=>`"${String(x??'').replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], {type:'text/csv'});
    const url = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`job-${job.id}.csv`; a.click(); URL.revokeObjectURL(url);
  }

  // Buttons
  document.getElementById('submitJob').addEventListener('click', async ()=>{
    const asset = assetEl.value.trim(); if(!asset){ toast('Enter asset','error'); return; }
    const dump = dumpEl.value.trim();
    setLoading(true);
    try {
      const body = { modality:'memory', params: { asset_id: asset } };
      if(dump) body.params.dump_path = dump;
      const r = await fetch('/forensics/jobs', { method:'POST', headers: { ...headers(), 'Content-Type':'application/json' }, body: JSON.stringify(body) });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      toast('Job submitted');
      await listJobs();
      if(j.job && j.job.id){ selectJob(j.job.id); }
    } catch(e){ toast('Submit error '+e.message,'error'); }
    finally { setLoading(false); }
  });
  document.getElementById('refresh').addEventListener('click', listJobs);
  document.getElementById('exportJson').addEventListener('click', async ()=>{
    if(!currentJobId) return; setLoading(true); try{ const r=await fetch(`/forensics/jobs/${currentJobId}`,{headers:headers()}); const j=await r.json(); exportJSON(j.job||j);} finally{ setLoading(false);} });
  document.getElementById('exportCsv').addEventListener('click', async ()=>{
    if(!currentJobId) return; setLoading(true); try{ const r=await fetch(`/forensics/jobs/${currentJobId}`,{headers:headers()}); const j=await r.json(); exportCSV(j.job||j);} finally{ setLoading(false);} });
  document.getElementById('verifyCustody').addEventListener('click', async ()=>{
    if(!currentJobId) return; setLoading(true); verifyOut.textContent='Verifying...';
    try{ const r = await fetch(`/forensics/custody/verify?job_id=${encodeURIComponent(currentJobId)}`, { headers: headers() }); if(!r.ok) throw new Error(r.status); const j = await r.json(); verifyOut.textContent = `matches=${j.matches} mismatches=${j.mismatches} chain=${j.chain_count} artifacts=${j.artifacts_count}`; }
    catch(e){ verifyOut.textContent = 'verify_error '+e.message; }
    finally{ setLoading(false); }
  });
  autoPollEl.addEventListener('change', schedulePoll);

  // Filters & search (if elements exist in page)
  async function applyFilters(){
    const mod = filterModality && filterModality.value ? filterModality.value : '';
    const st = filterStatus && filterStatus.value ? filterStatus.value : '';
    const q = searchInput && searchInput.value ? searchInput.value.toLowerCase() : '';
    setLoading(true);
    try{
      const qs = new URLSearchParams();
      if(mod) qs.set('modality', mod);
      if(st) qs.set('status', st);
      qs.set('limit', '50');
      const r = await fetch(`/forensics/jobs?${qs.toString()}`, { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      jobsTbody.innerHTML='';
      let items = j.items||[];
      if(q){ items = items.filter(it => String(it.id).toLowerCase().includes(q) || String(it.modality||'').toLowerCase().includes(q) || String(it.status||'').toLowerCase().includes(q)); }
      items.forEach(it => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><a href="#" data-jid="${it.id}">${it.id||''}</a></td>`+
                       `<td>${it.modality||'memory'}</td>`+
                       `<td>${badge(it.status)}</td>`+
                       `<td>${it.submitted_ts? new Date(it.submitted_ts*1000).toISOString():'—'}</td>`;
        tr.addEventListener('click', ()=> selectJob(it.id));
        jobsTbody.appendChild(tr);
      });
    }catch(e){ toast('Filter error '+e.message,'error'); }
    finally{ setLoading(false); }
  }
  if(filterModality) filterModality.addEventListener('change', applyFilters);
  if(filterStatus) filterStatus.addEventListener('change', applyFilters);
  if(searchInput) searchInput.addEventListener('input', debounce(applyFilters, 250));

  // Exponential backoff for polling on errors
  let backoffMs = 0;
  async function resilientLoad(){
    if(!currentJobId) return;
    try{
      await loadJob(currentJobId);
      backoffMs = 0; // reset on success
    }catch(_){
      backoffMs = backoffMs ? Math.min(backoffMs * 2, 15000) : 1000;
      setTimeout(resilientLoad, backoffMs);
    }
  }
  function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); } }

  // Init
  listJobs();
})();
