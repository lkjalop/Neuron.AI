const messagesEl = document.getElementById('messages');
const input = document.getElementById('chat-input');
const form = document.getElementById('chat-form');
const timingsEl = document.getElementById('timings');
const contextsEl = document.getElementById('contexts');
const errorBanner = document.getElementById('error-banner');
const confidenceBadge = document.getElementById('confidence-badge');
const modeSel = document.getElementById('mode');
let pending = 0;
function addMessage(role, content) {
  const div=document.createElement('div');
  div.className='message '+role+' fade-in';
  div.textContent=content; messagesEl.appendChild(div); messagesEl.scrollTop=messagesEl.scrollHeight;
}
function showError(m){ errorBanner.textContent=m; errorBanner.style.display='block'; }
function clearError(){ errorBanner.style.display='none'; }
function setConfidence(v){ if(v==null){ confidenceBadge.textContent=''; return;} let t='LOW', cls='low'; if(v>=0.7){t='HIGH';cls='high';} else if(v>=0.4){t='MED';cls='med';} confidenceBadge.className='confidence badge '+cls; confidenceBadge.textContent=`Confidence: ${t} ${(v*100).toFixed(1)}%`; }
function renderContexts(items){ contextsEl.innerHTML=''; items.forEach(c=>{ const d=document.createElement('div'); d.className='context-item'; d.innerHTML=`<div class='meta'>${c.doc}#${c.chunk_id} score=${(c.score||0).toFixed(3)}</div><div>${c.preview}</div>`; contextsEl.appendChild(d); }); }
function renderTimings(t){ timingsEl.innerHTML=''; Object.entries(t||{}).forEach(([k,v])=>{ const li=document.createElement('li'); li.textContent=`${k}: ${(v*1000).toFixed(1)} ms`; timingsEl.appendChild(li); }); }
function setLoading(on){ pending += on?1:-1; pending=Math.max(0,pending); if(on){ if(!document.getElementById('global-spinner')){ const sp=document.createElement('div'); sp.id='global-spinner'; sp.className='spinner-overlay'; sp.innerHTML='<div class="spinner"></div>'; document.body.appendChild(sp);} } else if(pending===0){ const sp=document.getElementById('global-spinner'); if(sp) sp.remove(); } }
async function send(q){ addMessage('user', q); input.value=''; clearError(); setConfidence(null); setLoading(true); let prompt=q; const mode=modeSel.value; if(mode==='playbook'){ prompt = `Provide step-by-step SOC playbook guidance: ${q}`;} else if(mode==='hunting'){ prompt = `Return a concise hunting strategy (commands + rationale): ${q}`;} else if(mode==='ioc'){ prompt = `Enrich this IOC contextually: ${q}`;} let resp; try { resp = await fetch('/chat',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query: prompt, k:5})}); } catch(e){ showError('Network error'); addMessage('assistant', 'Network error: '+e.message); setLoading(false); return;} if(!resp.ok){ const txt=await resp.text(); showError('Backend error '+resp.status); addMessage('assistant','Error: '+resp.status+' '+txt); setLoading(false); return;} const data=await resp.json(); addMessage('assistant', data.answer || '[empty answer]'); renderContexts(data.contexts); renderTimings(data.timings); setConfidence(data.confidence); setLoading(false);} 
form.addEventListener('submit', e=>{ e.preventDefault(); const q=input.value.trim(); if(!q)return; send(q); });
input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); form.requestSubmit(); }});
addMessage('system','SOC Analyst session started. Select a mode and ask a question.');
