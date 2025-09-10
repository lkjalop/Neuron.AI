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
      qs('#tab-'+btn.dataset.tab).classList.remove('hidden');
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
}

init();
