// Simple shell to demo layout interactions and stubs (no framework)
const state = {
  mode: 'main',
};

const qs = sel => document.querySelector(sel);
const qsa = sel => Array.from(document.querySelectorAll(sel));

function setMode(m) {
  state.mode = m;
  qs('#mode-main').classList.toggle('active', m==='main');
  qs('#mode-wiki').classList.toggle('active', m==='wiki');
  qs('#inline-main').classList.toggle('active', m==='main');
  qs('#inline-wiki').classList.toggle('active', m==='wiki');
  // inject a card hinting mode-specific actions
  addCard({title: m==='main' ? 'Main Mode' : 'Wiki Mode', body: m==='main' ? 'Ask to operate on reports, graphs, findings.' : 'Ask for explanations and walkthroughs.', kind: m});
}

function addCard({title, body, kind='main'}) {
  const host = qs('#thread');
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <div class="card-title">${title}</div>
    <div class="card-body">${body}</div>
    <div class="card-actions">
      <button class="ghost small" data-act="detach">Detach</button>
      <button class="ghost small" data-act="explain">Explain</button>
      <button class="ghost small" data-act="explain-csuite">Explain for C‑suite</button>
      <button class="ghost small" data-act="export">Export</button>
      <button class="ghost small" data-act="add-report">Add to Report</button>
      <button class="ghost small" data-act="guided">Guided Mode</button>
      <button class="ghost small" data-act="story">Add to Story</button>
    </div>
  `;
  card.querySelector('[data-act="detach"]').onclick = () => openMetrics();
  card.querySelector('[data-act="add-report"]').onclick = () => {
    const evt = new CustomEvent('add-to-report', { detail: { card } });
    document.dispatchEvent(evt);
  };
  card.querySelector('[data-act="explain"]').onclick = () => qs('#explain').textContent = 'Explanation: … (ELI5 toggle TBD)';
  card.querySelector('[data-act="explain-csuite"]').onclick = () => qs('#explain').textContent = 'C‑suite: Business impact and plain terms …';
  card.querySelector('[data-act="guided"]').onclick = () => alert('Guided Mode: highlight UI steps (writes require approval).');
  card.querySelector('[data-act="story"]').onclick = () => alert('Added to Story timeline.');
  host.appendChild(card);
  host.scrollTop = host.scrollHeight;
}

function addToReport(node) {
  qs('#win-report').classList.remove('hidden');
  qs('#report-canvas').appendChild(node);
}

function openReport() { qs('#win-report').classList.remove('hidden'); }
function openMetrics() { qs('#win-metrics').classList.remove('hidden'); }

function bindPalette() {
  const pal = qs('#palette');
  const input = qs('#palette-input');
  const list = qs('#palette-list');
  const items = [
    {label:'Open Editable Report', run: openReport},
    {label:'Open Metrics & Findings Hub', run: openMetrics},
    {label:'Switch to Main', run: () => setMode('main')},
    {label:'Switch to Wiki', run: () => setMode('wiki')},
  ];
  function render(filter='') {
    list.innerHTML='';
    items.filter(i => i.label.toLowerCase().includes(filter.toLowerCase()))
      .forEach(i => {
        const li = document.createElement('li');
        li.textContent = i.label; li.onclick = () => { i.run(); hide(); };
        list.appendChild(li);
      });
  }
  function show(){ pal.classList.remove('hidden'); input.value=''; render(); input.focus(); }
  function hide(){ pal.classList.add('hidden'); }
  qs('#open-palette').onclick = show;
  input.oninput = () => render(input.value);
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase()==='k') { e.preventDefault(); show(); }
    if (e.key==='Escape') hide();
  });
}

function bindWindows() {
  qsa('.window').forEach(win => {
    win.querySelector('[data-action="close"]').onclick = () => win.classList.add('hidden');
    win.querySelector('[data-action="snapl"]').onclick = () => { win.style.left='40px'; win.style.right=''; win.style.width='48vw'; };
    win.querySelector('[data-action="snapr"]').onclick = () => { win.style.right='40px'; win.style.left=''; win.style.width='48vw'; };
  });
}

function bindTabs() {
  qsa('.tab').forEach(btn => {
    btn.onclick = () => {
      qsa('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      qsa('.tab-body').forEach(x => x.classList.add('hidden'));
      const body = qs('#tab-'+btn.dataset.tab);
      body.classList.remove('hidden');
      // If switching to Graphs, set/refresh iframe URL via backend proxy
      if (btn.dataset.tab === 'graphs') {
        try {
          const iframe = qs('#grafana-iframe');
          const banner = qs('#graphs-error');
          const conn = qs('#graphs-conn');
          const panelId = '1'; // default panel; can be made dynamic
          const tenantSel = qs('#tenant-select');
          const timeSel = qs('#time-select');
          const tenant = (tenantSel?.value) || (localStorage.getItem('tenant')||'tenant_fx');
          if (tenantSel && !tenantSel.value) tenantSel.value = tenant;
          localStorage.setItem('tenant', tenant);
          const vars = JSON.stringify({ tenant });
          const fr = (timeSel?.value)||'now-6h'; const to = 'now';
          const url = `/proxy/grafana/iframe?panelId=${encodeURIComponent(panelId)}&vars=${encodeURIComponent(vars)}&fr=${encodeURIComponent(fr)}&to=${encodeURIComponent(to)}`;
          // Fetch the resolved URL from backend (keeps tokens server-side)
          const hdrs = (typeof apiHeaders === 'function') ? apiHeaders() : {};
          fetch(apiUrl(url), { headers: hdrs })
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(j => {
              if (j && j.url) {
                iframe.src = j.url;
                if (banner) banner.classList.add('hidden');
                if (conn) conn.textContent = 'Conn: OK';
              }
            })
            .catch(() => {
              iframe.src = 'about:blank';
              if (banner){ banner.classList.remove('hidden'); banner.textContent = 'Graphs unavailable (proxy error or unconfigured).'; }
              if (conn) conn.textContent = 'Conn: ERR';
            });
        } catch { /* noop */ }
      }
    };
  });
}

function bindComposer() {
  const input = qs('#input');
  const send = qs('#send');
  function submit(){
    const q = input.value.trim(); if (!q) return;
    addCard({title: state.mode==='main'?'Query (Main)':'Query (Wiki)', body: q, kind: state.mode});
    input.value=''; input.style.height='';
  }
  input.addEventListener('keydown', (e) => {
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  });
  input.addEventListener('input', () => {
    input.style.height='auto';
    input.style.height=Math.min(input.scrollHeight, 220)+'px';
  });
  send.onclick = submit;
  qs('#inline-main').onclick = () => setMode('main');
  qs('#inline-wiki').onclick = () => setMode('wiki');
  // ELI5 toggle influences Explain panel text simplification
  const eli5 = qs('#eli5');
  eli5?.addEventListener('change', () => {
    const base = qs('#explain').textContent || '';
    if (eli5.checked) qs('#explain').textContent = (base || 'Explanation') + ' — simplified for C‑suite.';
  });

  // Watchers add/remove (UI only; backend integration pending)
  const wInput = qs('#watcher-input');
  const wAdd = qs('#add-watcher');
  const wList = qs('#watcher-list');
  wAdd?.addEventListener('click', () => {
    const v = (wInput.value||'').trim(); if (!v) return;
    const li = document.createElement('li');
    li.textContent = v + ' (watching)';
    const rm = document.createElement('button'); rm.className='ghost small'; rm.textContent='Remove'; rm.onclick=()=>li.remove();
    li.appendChild(document.createTextNode(' ')); li.appendChild(rm);
    wList.appendChild(li); wInput.value='';
  });

  // Report toolbar buttons
  qs('#apply-recommended')?.addEventListener('click', () => alert('Applied Recommended View.'));
  qs('#share-view')?.addEventListener('click', () => alert('Generated read-only shareable link.'));
  qs('#story-mode')?.addEventListener('click', () => alert('Story Mode: open timeline composer.'));
}

function init() {
  bindPalette();
  bindWindows();
  bindTabs();
  bindComposer();
  setMode('main');
  // API key helper
  const setKey = qs('#set-api-key');
  const apiKeyIndicator = qs('#api-key-indicator');
  const updateKeyIndicator = () => {
    const has = !!(localStorage.getItem('X_API_KEY')||'').trim();
    if (apiKeyIndicator) apiKeyIndicator.classList.toggle('set', has);
  };
  updateKeyIndicator();
  setKey?.addEventListener('click', () => {
    const curr = localStorage.getItem('X_API_KEY') || '';
    const v = prompt('Enter API Key (predict/admin):', curr || '');
    if (v !== null) {
      const trimmed = v.trim();
      if (trimmed) {
        localStorage.setItem('X_API_KEY', trimmed);
        alert('API key saved to local storage.');
      } else {
        localStorage.removeItem('X_API_KEY');
        alert('API key cleared from local storage.');
      }
      updateKeyIndicator();
    }
  });
  // Bind Graphs controls
  const tSel = qs('#tenant-select'); const tiSel = qs('#time-select'); const btn = qs('#refresh-graphs');
  const refresh = () => {
    const graphsTabBtn = qsa('.tab').find(b => b.dataset.tab==='graphs');
    if (graphsTabBtn){ graphsTabBtn.click(); }
  };
  tSel?.addEventListener('change', () => { localStorage.setItem('tenant', tSel.value); refresh(); });
  tiSel?.addEventListener('change', refresh);
  btn?.addEventListener('click', refresh);
  // seed example cards
  addCard({title:'Anomaly Timeline', body:'Chart + annotations…'});
  addCard({title:'CVEs EPSS>0.6', body:'23 findings • Export CSV'});

  // Approvals simulation
  const approvals = qs('#approvals');
  const reqBtn = qs('#request-approval');
  reqBtn?.addEventListener('click', () => {
    const id = 'APP-' + Math.random().toString(36).slice(2,7).toUpperCase();
    const li = document.createElement('li');
    li.textContent = `${id}: Tuner change (2h) pending`;
    const approve = document.createElement('button'); approve.className='ghost small'; approve.textContent='Approve';
    const reject = document.createElement('button'); reject.className='ghost small'; reject.textContent='Reject';
    const rollback = document.createElement('button'); rollback.className='ghost small'; rollback.textContent='Rollback'; rollback.disabled=true;
    approve.onclick = () => { li.firstChild.textContent = `${id}: Approved (active)`; approve.disabled=true; reject.disabled=true; rollback.disabled=false; alert('Approved. Change will auto-revert in 2h.'); };
    reject.onclick = () => { li.firstChild.textContent = `${id}: Rejected`; approve.disabled=true; reject.disabled=true; };
    rollback.onclick = () => { li.firstChild.textContent = `${id}: Rolled back`; rollback.disabled=true; };
    li.appendChild(document.createTextNode(' ')); li.appendChild(approve); li.appendChild(reject); li.appendChild(rollback);
    approvals?.appendChild(li);
  });
  // Sidebar navigation wiring
  const on = (id, fn) => { const el = qs(id); if (el) el.addEventListener('click', fn); };
  on('#nav-objectives', async () => {
    try {
      const data = await getJSON('/dashboard/latest');
      addCard({ title: 'Today’s Objectives', body: `Cached: ${!!data.cached} • Fusion Keys: ${Object.keys(data.fusion||{}).length}` });
    } catch (e) {
      addCard({ title: 'Today’s Objectives', body: 'Failed to load dashboard snapshot.' });
    }
  });
  on('#nav-sla-risks', async () => {
    try {
      const data = await getJSON('/findings/sla/upcoming');
      const cnt = (data?.items||[]).length;
      addCard({ title: 'SLA Risks', body: `Upcoming SLA items: ${cnt}` });
    } catch {
      addCard({ title: 'SLA Risks', body: 'Failed to load SLA risks.' });
    }
  });
  on('#nav-open-tickets', () => {
    try {
      fetch(apiUrl('/tickets'), { headers: (typeof apiHeaders==='function')?apiHeaders():{} })
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(j => {
          const items = (j?.items)||[];
          addCard({ title: 'Open Tickets', body: `Tickets listed: ${items.length} (see /tickets)` });
        })
        .catch(() => addCard({ title: 'Open Tickets', body: 'Failed to load tickets.' }));
    } catch { /* noop */ }
  });
  on('#nav-saved-views', () => addCard({ title: 'Saved Views', body: 'Coming soon — will list saved report layouts.' }));
  on('#nav-playbooks', () => addCard({ title: 'Playbooks', body: 'Coming soon — guided response playbooks.' }));
  on('#nav-exec-summary', () => openReport());
  on('#nav-hunt', async () => {
    try {
      const body = { pattern: 'ransom', field: 'message', limit: 10 };
      const res = await fetch(apiUrl('/hunt/query'), { method:'POST', headers: apiHeaders(), body: JSON.stringify(body) });
      if (!res.ok) throw new Error(String(res.status));
      const j = await res.json();
      const cnt = (j?.items||j?.results||[]).length;
      addCard({ title: 'Ransomware Hunt', body: `Pattern: ${body.pattern} • Matches: ${cnt}` });
    } catch (e) {
      addCard({ title: 'Ransomware Hunt', body: 'Hunt query failed.' });
    }
  });
  on('#nav-forensics', async () => {
    try {
      // Create a quick triage job
      const created = await fetch(apiUrl('/forensics/jobs'), { method:'POST', headers: apiHeaders(), body: JSON.stringify({ kind:'triage', note:'UI trigger' }) })
        .then(r => r.ok ? r.json() : Promise.reject(r.status));
      const jobId = created?.job?.id || created?.id || 'unknown';
      // Verify custody best-effort
      const custody = await fetch(apiUrl(`/forensics/custody/verify?job_id=${encodeURIComponent(jobId)}`), { headers: apiHeaders() })
        .then(r => r.ok ? r.json() : { ok:false });
      // List recent jobs
      const jobs = await fetch(apiUrl('/forensics/jobs/recent'), { headers: apiHeaders() })
        .then(r => r.ok ? r.json() : { items:[] });
      const jcnt = (jobs?.items||[]).length;
      const cmsg = custody?.ok ? 'Custody OK' : 'Custody check failed';
      addCard({ title: 'Forensics Triage', body: `Job ${jobId} created • Recent jobs: ${jcnt} • ${cmsg}` });
    } catch (e) {
      addCard({ title: 'Forensics Triage', body: 'Forensics API failed.' });
    }
  });
}

init();

// Health/readiness summary and status popover
(function(){
  const statusEl = qs('#status');
  const pop = qs('#status-popover');
  const healthEl = qs('#health-summary');
  const proxyEl = qs('#proxy-ready');
  const hdrs = (typeof apiHeaders === 'function') ? apiHeaders() : {};

  // Toggle popover
  statusEl?.addEventListener('click', () => {
    pop?.classList.toggle('hidden');
  });
  // Hide on outside click
  document.addEventListener('click', (e) => {
    if (!pop || pop.classList.contains('hidden')) return;
    if (e.target === pop || e.target === statusEl || pop.contains(e.target)) return;
    pop.classList.add('hidden');
  });

  // Fetch readiness
  fetch('/health/ready', { headers: hdrs })
    .then(async (r) => {
      if (r.ok) {
        const j = await r.json().catch(() => null);
        const mode = j && j.mode ? j.mode : 'strict';
        statusEl && (statusEl.textContent = mode === 'partial' ? 'Ready: Degraded' : 'Ready: OK');
        healthEl && (healthEl.textContent = mode === 'partial' ? 'Readiness: degraded (ALLOW_PARTIAL_READINESS=1)' : 'Readiness: OK');
      } else if (r.status === 503) {
        statusEl && (statusEl.textContent = 'Ready: Not Ready');
        healthEl && (healthEl.textContent = 'Readiness: not ready (503)');
      } else {
        statusEl && (statusEl.textContent = 'Ready: Unknown');
        healthEl && (healthEl.textContent = 'Readiness: unknown');
      }
    })
    .catch(() => {
      statusEl && (statusEl.textContent = 'Ready: Unreachable');
      healthEl && (healthEl.textContent = 'Readiness: unreachable');
    })
    .finally(() => {
      // Fetch proxy readiness (predict/admin key may be required if configured)
      fetch('/proxy/ready', { headers: hdrs })
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(j => {
          const prom = j && j.prometheus_configured ? 'Prometheus: configured' : 'Prometheus: not set';
          const graf = j && j.grafana_configured ? 'Grafana: configured' : 'Grafana: not set';
          proxyEl && (proxyEl.textContent = `${prom} • ${graf}`);
        })
        .catch(() => {
          proxyEl && (proxyEl.textContent = 'Proxies: unreachable or unauthorized');
        });
    });
})();
