const grid = document.getElementById('grid');
const statusEl = document.getElementById('status');
// spinner/toast helpers
let pending = 0;
function setLoading(on) {
  pending += on ? 1 : -1; pending = Math.max(0,pending);
  if (on && !document.getElementById('global-spinner')) {
    const el = document.createElement('div'); el.id='global-spinner'; el.className='spinner-overlay'; el.innerHTML='<div class="spinner"></div>';
    document.body.appendChild(el);
  } else if (!on && pending===0) {
    const el = document.getElementById('global-spinner'); if (el) el.remove();
  }
}
function toast(msg, ms=2200) {
  const t = document.getElementById('toast'); if (!t) return; t.textContent = msg; t.style.display='block';
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(()=>{ t.style.display='none'; }, ms);
}

function fmt(n, d=2) { if(n==null||isNaN(n)) return '—'; return Number(n).toFixed(d); }

function render(data) {
  grid.innerHTML='';
  if(!data) return;
  const fusion = data.fusion||{}; const det = data.detection||{}; const gov = data.governance||{}; const exp = data.exposure||{};
  const cards = [
    { title:'Fusion Overlap Avg', value: fmt(fusion.overlap_ratio_avg,3) },
    { title:'SNN Unique Avg', value: fmt(fusion.snn_unique_ratio_avg,3) },
    { title:'Suppression Rate', value: fmt(fusion.suppression_rate_avg,3) },
    { title:'Baseline Anomalies', value: det.baseline_anomalies },
    { title:'SNN Anomalies', value: det.snn_anomalies },
    { title:'Param Changes', value: gov.param_changes },
    { title:'Guard Trips', value: Object.keys(gov.guard_trips||{}).length },
    { title:'Governance Composite', value: fmt(gov.composite_signal,4) },
    { title:'Exposure Total', value: fmt(exp.last_total,2) },
    { title:'Exposure 7d', value: fmt(exp.rolling_7d,2) },
    { title:'Exposure 30d', value: fmt(exp.rolling_30d,2) },
  ];
  cards.forEach(c => {
    const div = document.createElement('div'); div.className='card';
    div.innerHTML = `<h3>${c.title}</h3><div class="value">${c.value}</div>`;
    grid.appendChild(div);
  });
  // Flags card
  const flags = data.flags || {};
  const fdiv = document.createElement('div'); fdiv.className='card';
  const bad = Object.entries(flags).filter(([k,v])=>v);
  fdiv.innerHTML = `<h3>Flags</h3><div class='flex'>${bad.length? bad.map(([k])=>`<span class='badge'>${k}</span>`).join('') : '<small>None active</small>'}</div>`;
  grid.appendChild(fdiv);

  // Governance composite sparkline
  const gdiv = document.createElement('div'); gdiv.className='card';
  const band = gov.composite_band || 'unknown';
  const bandCls = band==='high' ? 'badge' : 'badge'; // same style; could colorize
  gdiv.innerHTML = `<h3>Governance Composite <span class="${bandCls}">${band}</span></h3><canvas id="govSpark" class="spark" width="300" height="48"></canvas><small>current: ${fmt(gov.composite_signal,4)} • points: ${(gov.composite_history||[]).length||0}</small>`;
  grid.appendChild(gdiv);
  try { drawSpark('govSpark', gov.composite_history || []); } catch(e) { /*noop*/ }
}

async function load() {
  statusEl.textContent = 'Refreshing...'; setLoading(true);
  try {
    const resp = await fetch('/executive/kpis');
    if(!resp.ok) throw new Error(resp.status);
    const data = await resp.json();
    render(data);
    statusEl.textContent = 'Updated ' + new Date().toLocaleTimeString();
    // toast('Dashboard updated');
  } catch(e) {
    statusEl.textContent = 'Error loading: ' + e.message;
    toast('Error loading dashboard: '+ e.message, 2600);
  } finally {
    setLoading(false);
  }
}

load();
setInterval(load, 15000);

function drawSpark(id, arr) {
  const el = document.getElementById(id);
  if (!el) return;
  const ctx = el.getContext('2d');
  const w = el.width, h = el.height;
  ctx.clearRect(0,0,w,h);
  if (!arr || !arr.length) return;
  // Normalize values to [0,1]
  const vals = arr.map(v => typeof v === 'number' ? v : 0).slice(-120); // last ~2h if 1/min
  const min = Math.min(...vals, 0);
  const max = Math.max(...vals, 1);
  const rng = (max - min) || 1;
  // Draw background baseline
  ctx.strokeStyle = '#233047';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, h-1);
  ctx.lineTo(w, h-1);
  ctx.stroke();
  // Line path
  ctx.strokeStyle = '#5eb5ff';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  vals.forEach((v, i) => {
    const x = (i / Math.max(vals.length-1,1)) * (w-2) + 1;
    const y = h - 2 - ((v - min) / rng) * (h-4);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  // Current point
  const last = vals[vals.length-1];
  const lx = (w-2) + 1; const ly = h - 2 - ((last - min)/rng) * (h-4);
  ctx.fillStyle = '#5eb5ff';
  ctx.beginPath(); ctx.arc(lx, ly, 2, 0, Math.PI*2); ctx.fill();
}
