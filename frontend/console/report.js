// Editable Report prototype logic (Batch 4 skeleton)
(function(){
  const win = document.getElementById('win-report');
  if (!win) return;
  const canvas = document.getElementById('report-canvas');
  let lastSnapshotTs = Date.now();

  // Snapshot-by-default flag per embed (attribute data-live)
  function addEmbedFromCard(card) {
    const embed = document.createElement('div');
    embed.className = 'card';
    embed.setAttribute('data-live','false');
    const title = card.querySelector('.card-title')?.textContent || 'Embed';
    embed.innerHTML = `
      <div class="card-title">${title}</div>
      <div class="card-body">Snapshot content captured at ${new Date().toLocaleString()}</div>
      <div class="card-actions">
        <button class="ghost small" data-act="toggle-live">Live: Off</button>
        <button class="ghost small" data-act="provenance">Provenance</button>
        <button class="ghost small" data-act="remove">Remove</button>
      </div>
    `;
    embed.querySelector('[data-act="toggle-live"]').onclick = () => toggleLive(embed);
    embed.querySelector('[data-act="remove"]').onclick = () => embed.remove();
    embed.querySelector('[data-act="provenance"]').onclick = () => alert('Dataset/time/query hash…');
    canvas.appendChild(embed);
  }

  function toggleLive(embed){
    const live = embed.getAttribute('data-live') === 'true';
    embed.setAttribute('data-live', String(!live));
    const btn = embed.querySelector('[data-act="toggle-live"]');
    btn.textContent = `Live: ${!live ? 'On' : 'Off'}`;
  }

  // Listen for synthetic "add-to-report" events from cards
  document.addEventListener('add-to-report', (e) => {
    win.classList.remove('hidden');
    addEmbedFromCard(e.detail.card);
    lastSnapshotTs = Date.now();
  });

  // Simulate new findings detection and show a toast offering update
  function showToast(msg, actions=[]) {
    const t = document.createElement('div');
    t.className='toast';
    const span = document.createElement('span');
    span.textContent = msg;
    t.appendChild(span);
    actions.forEach(a => {
      const b = document.createElement('button');
      b.textContent = a.label; b.onclick = () => { a.run(); t.remove(); };
      t.appendChild(b);
    });
    document.body.appendChild(t);
    setTimeout(()=>t.remove(), 8000);
  }

  function simulateNewFindings() {
    const sinceMin = Math.round((Date.now() - lastSnapshotTs)/60000);
    if (sinceMin < 1) return; // only after some time
    showToast('New findings since your snapshot — update embeds?', [
      {label:'Preview Diff', run: () => alert('Diff: +2 CVEs, EPSS median +0.03')},
      {label:'Update All', run: () => {
        canvas.querySelectorAll('.card').forEach(c => {
          if (c.getAttribute('data-live') !== 'true') {
            const body = c.querySelector('.card-body');
            if (body) body.textContent = 'Snapshot refreshed at ' + new Date().toLocaleString();
          }
        });
        lastSnapshotTs = Date.now();
      }},
      {label:'Keep', run: () => {/* no-op */}},
    ]);
  }

  // Demo: poll every 20s to simulate new findings
  setInterval(simulateNewFindings, 20000);
})();
