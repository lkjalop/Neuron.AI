(function(){
  const apiKeyEl = document.getElementById('apiKey');
  const iocValueEl = document.getElementById('iocValue');
  const iocTypeEl = document.getElementById('iocType');
  const huntQueryEl = document.getElementById('huntQuery');
  const iocTBody = document.querySelector('#iocTable tbody');
  const huntTBody = document.querySelector('#huntTable tbody');
  // spinner/toast helpers
  let pending=0; function setLoading(on){ pending+=on?1:-1; pending=Math.max(0,pending); if(on && !document.getElementById('global-spinner')){ const el=document.createElement('div'); el.id='global-spinner'; el.className='spinner-overlay'; el.innerHTML='<div class="spinner"></div>'; document.body.appendChild(el);} else if(!on && pending===0){ const el=document.getElementById('global-spinner'); if(el) el.remove(); } }
  function toast(msg, kind){ const t=document.createElement('div'); t.textContent=msg; t.style.cssText='position:fixed;right:12px;top:12px;background:'+(kind==='error'?'#3f1d1d':'#22313f')+';color:#fff;padding:8px 10px;border-radius:8px;z-index:110;box-shadow:0 2px 8px rgba(0,0,0,.25)'; document.body.appendChild(t); setTimeout(()=>t.remove(), 2600); }
  function headers(){ const h={}; if(apiKeyEl.value) h['x-api-key']=apiKeyEl.value; return h; }
  async function addIoc(){
    const value = iocValueEl.value.trim(); if(!value){ toast('Enter IOC','error'); return; }
    const type = iocTypeEl.value || 'generic';
    setLoading(true);
    try {
      const r = await fetch('/ioc', { method:'POST', headers: { ...headers(), 'Content-Type':'application/json' }, body: JSON.stringify({ value, type }) });
      if(!r.ok) throw new Error(r.status);
      await listIocs();
      iocValueEl.value='';
    } catch(e){ toast('Add error '+e.message, 'error'); }
    finally { setLoading(false); }
  }
  async function listIocs(){
    setLoading(true);
    try {
      const r = await fetch('/ioc?limit=100', { headers: headers() });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      iocTBody.innerHTML='';
      (j.items||[]).forEach(it => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${it.id||''}</td><td>${it.value||''}</td><td>${it.type||''}</td>`+
                       `<td>${it.added_ts? new Date(it.added_ts*1000).toISOString():'—'}</td>`;
        iocTBody.appendChild(tr);
      });
    } catch(e){ toast('List IOCs error','error'); }
    finally { setLoading(false); }
  }
  async function runHunt(){
    const q = huntQueryEl.value.trim(); if(!q){ toast('Enter pattern','error'); return; }
    setLoading(true);
    try {
      const r = await fetch('/hunt/query', { method:'POST', headers: { ...headers(), 'Content-Type':'application/json' }, body: JSON.stringify({ value: q }) });
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      huntTBody.innerHTML='';
      (j.items||[]).forEach(it => {
        const tr=document.createElement('tr');
        tr.innerHTML = `<td>${it.value||''}</td><td>${it.type||''}</td>`;
        huntTBody.appendChild(tr);
      });
    } catch(e){ toast('Hunt error '+e.message, 'error'); }
    finally { setLoading(false); }
  }
  document.getElementById('addIoc').addEventListener('click', addIoc);
  document.getElementById('runHunt').addEventListener('click', runHunt);
  document.getElementById('refresh').addEventListener('click', listIocs);
  listIocs();
})();
