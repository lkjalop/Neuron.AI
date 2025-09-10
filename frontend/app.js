const apiBase = '';
const messagesEl = document.getElementById('messages');
const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const topkSel = document.getElementById('topk');
const contextsEl = document.getElementById('contexts');
const timingsEl = document.getElementById('timings');
const ctxCountEl = document.getElementById('ctx-count');
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');
const detachChatBtn = document.getElementById('detach-chat');
const detachDashBtn = document.getElementById('detach-dashboard');
const dashboardBtn = document.getElementById('open-dashboard');
const historyEl = document.getElementById('chat-history');
const errorBanner = document.getElementById('error-banner');
const confidenceBadge = document.getElementById('confidence-badge');
const socBtn = document.getElementById('soc-chat');

let pending = 0;
function setLoading(on) {
  pending += on ? 1 : -1;
  pending = Math.max(0,pending);
  if (on) {
    if (!document.getElementById('global-spinner')) {
      const sp = document.createElement('div');
      sp.id='global-spinner';
      sp.className='spinner-overlay';
      sp.innerHTML='<div class="spinner"></div>';
      document.body.appendChild(sp);
    }
  } else if (pending===0) {
    const sp = document.getElementById('global-spinner');
    if (sp) sp.remove();
  }
}
function showError(msg) { errorBanner.textContent = msg; errorBanner.style.display='block'; }
function clearError() { errorBanner.style.display='none'; }
function setConfidence(v) {
  if (v==null) { confidenceBadge.textContent=''; return; }
  let tier='LOW'; let cls='low';
  if (v>=0.7) { tier='HIGH'; cls='high'; }
  else if (v>=0.4) { tier='MED'; cls='med'; }
  confidenceBadge.className='confidence badge '+cls;
  confidenceBadge.textContent=`Confidence: ${tier} ${(v*100).toFixed(1)}%`;
}

let chatId = Date.now().toString(36);
let history = [];

function addMessage(role, content, extra={}) {
  const div = document.createElement('div');
  div.className = 'message ' + role + ' fade-in';
  div.textContent = content;
  if (role === 'assistant' && extra.citations) {
    const cwrap = document.createElement('div');
    cwrap.className = 'citations';
    extra.citations.forEach(c => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className='citation';
      b.textContent = c.chunk_id != null ? `${c.doc}#${c.chunk_id}` : c.doc;
      b.onclick = () => scrollToContext(c.doc, c.chunk_id);
      cwrap.appendChild(b);
    });
    div.appendChild(cwrap);
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function scrollToContext(doc, chunk) {
  const el = document.querySelector(`[data-doc="${doc}"][data-chunk='${chunk}']`);
  if (el) {
    el.classList.add('highlight');
    el.scrollIntoView({behavior:'smooth', block:'center'});
    setTimeout(()=>el.classList.remove('highlight'), 1200);
  }
}

function renderContexts(contexts) {
  contextsEl.innerHTML='';
  contexts.forEach(c => {
    const div = document.createElement('div');
    div.className='context-item fade-in';
    div.dataset.doc = c.doc;
    div.dataset.chunk = c.chunk_id;
    const meta = document.createElement('div');
    meta.className='meta';
    meta.textContent = `${c.doc} • score=${(c.score||0).toFixed(3)} • chunk=${c.chunk_id}`;
    const text = document.createElement('div');
    text.textContent = c.preview;
    div.appendChild(meta); div.appendChild(text);
    contextsEl.appendChild(div);
  });
  ctxCountEl.textContent = contexts.length ? `(${contexts.length})` : '';
}

function renderTimings(t) {
  timingsEl.innerHTML='';
  Object.entries(t || {}).forEach(([k,v]) => {
    const li = document.createElement('li');
    li.textContent = `${k}: ${(v*1000).toFixed(1)} ms`;
    timingsEl.appendChild(li);
  });
}

async function sendMessage(q) {
  addMessage('user', q);
  input.value=''; input.style.height='';
  const k = topkSel.value;
  const payload = { query: q, k: parseInt(k,10) };
  const t0 = performance.now();
  let resp;
  clearError(); setConfidence(null); setLoading(true);
  try {
    resp = await fetch(apiBase + '/chat', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
  } catch (e) {
    addMessage('assistant', 'Network error: '+ e.message);
    showError('Network error — retry?');
    setLoading(false);
    return;
  }
  if (!resp.ok) {
    const txt = await resp.text();
    addMessage('assistant', 'Error: '+ resp.status + ' '+ txt);
    showError('Backend error '+resp.status+' — '+txt);
    setLoading(false);
    return;
  }
  const data = await resp.json();
  const latency = performance.now() - t0;
  addMessage('assistant', data.answer || '[empty answer]', { citations: data.citations });
  renderContexts(data.contexts || []);
  renderTimings(data.timings || {});
  setConfidence(data.confidence);
  history.push({id: Date.now(), q, answer: data.answer, t: latency});
  renderHistory();
  setLoading(false);
}

function renderHistory() {
  historyEl.innerHTML='';
  history.slice().reverse().forEach(item => {
    const div = document.createElement('div');
    div.className='history-item';
    div.textContent = item.q.slice(0,60);
    div.title = item.answer || '';
    div.onclick = () => {
      input.value = item.q; input.focus();
    };
    historyEl.appendChild(div);
  });
}

form.addEventListener('submit', e => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;
  sendMessage(q);
});

input.addEventListener('input', () => {
  input.style.height='auto';
  input.style.height = Math.min(input.scrollHeight, 220) + 'px';
});

toggleSidebarBtn.addEventListener('click', () => {
  sidebar.classList.toggle('open');
});

detachChatBtn.addEventListener('click', () => {
  window.open(window.location.origin + '/app', '_blank','noopener');
});

detachDashBtn.addEventListener('click', () => {
  window.open(window.location.origin + '/app/dashboard.html', '_blank','noopener');
});

socBtn?.addEventListener('click', () => {
  window.open(window.location.origin + '/app/soc.html', '_blank','noopener');
});

dashboardBtn.addEventListener('click', () => {
  window.open(window.location.origin + '/app/dashboard.html', '_blank','noopener');
});

// Keyboard shortcut: Ctrl+Enter
input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

addMessage('system', 'New session started. Ask me something.');
