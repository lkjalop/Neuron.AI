// Adapter & guard stubs (Batch 3)
function apiHeaders() {
  const key = localStorage.getItem('X_API_KEY') || localStorage.getItem('x-api-key');
  const h = { 'Content-Type': 'application/json' };
  if (key) h['X-API-Key'] = key;
  return h;
}

async function getJSON(url) {
  const res = await fetch(url, { headers: apiHeaders() });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return res.json();
}
async function postJSON(url, body) {
  const res = await fetch(url, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(body || {}) });
  if (!res.ok) throw new Error(`POST ${url} -> ${res.status}`);
  return res.json();
}

export const DashboardAdapter = {
  latest: async (scope) => {
    const qs = scope?.maxAge ? `?max_age_s=${encodeURIComponent(scope.maxAge)}` : '';
    const data = await getJSON(`/dashboard/latest${qs}`);
    return { ok: true, ts: Date.now(), raw: data };
  }
};

export const InsightsAdapter = {
  list: async (tenant) => {
    const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : '';
    const data = await getJSON(`/insights${qs}`);
    return data?.insights || [];
  }
};

export const MetricsAdapter = {
  // Prefer backend proxy for Prometheus queries
  queryPromQL: async (q, range) => {
    const p = new URLSearchParams({ q });
    if (range && range.start && range.end && range.step) {
      p.set('start', String(range.start));
      p.set('end', String(range.end));
      p.set('step', String(range.step));
    }
    const data = await getJSON(`/proxy/prom?${p.toString()}`);
    return data; // raw Prometheus response
  }
};

export const GrafanaAdapter = {
  iframeUrl(panelId, vars){
    const p = new URLSearchParams({ panelId });
    if (vars) p.set('vars', typeof vars==='string' ? vars : JSON.stringify(vars));
    return `/proxy/grafana/iframe?${p.toString()}`;
  },
  renderImage: async (panelId, vars) => {
    const p = new URLSearchParams({ panelId });
    if (vars) p.set('vars', typeof vars==='string' ? vars : JSON.stringify(vars));
    const res = await fetch(`/proxy/grafana/render?${p.toString()}`, { headers: apiHeaders() });
    if (!res.ok) throw new Error(`render ${panelId} -> ${res.status}`);
    return res.blob();
  }
};

export const FindingsAdapter = {
  slaUpcoming: async (scope) => {
    const data = await getJSON(`/findings/sla/upcoming`);
    return data?.items || [];
  },
  cves: async (filter) => {
    // TODO: GET /findings/cves?...
    return [];
  }
};

export const TicketsAdapter = {
  createRemediation: async (input) => {
    const data = await postJSON(`/tickets/remediation`, input);
    return { ok: true, ...data };
  }
};

export const FeedbackAdapter = {
  submit: async (input) => {
    const data = await postJSON(`/feedback`, input);
    return { ok: true, ...data };
  }
};

// Guards for tuner changes
export const TunerGuards = {
  canPreview: (user) => true,
  canApply: (user) => user?.role === 'soc_lead' || user?.role === 'platform_admin',
  // time-bounded approval enforcement stub
  withinWindow: (approval) => {
    if (!approval) return false;
    const now = Date.now();
    return now >= approval.start && now <= approval.end;
  }
};
