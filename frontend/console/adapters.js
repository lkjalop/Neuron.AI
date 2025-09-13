// Adapter & guard stubs (Batch 3)
(function(){
  function getApiBase(){
    // Prefer explicit API_BASE in window or localStorage
    const fromWin = (typeof window !== 'undefined' && window.API_BASE) ? String(window.API_BASE) : '';
    const fromLS = localStorage.getItem('API_BASE') || '';
    if (fromWin) return fromWin.replace(/\/$/, '');
    if (fromLS) return fromLS.replace(/\/$/, '');
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }
  function apiUrl(path){
    const base = getApiBase();
    if (!path) return base;
    return path.startsWith('http') ? path : base + (path.startsWith('/') ? path : ('/' + path));
  }
  function apiHeaders() {
    const key = localStorage.getItem('X_API_KEY') || localStorage.getItem('x-api-key');
    const h = { 'Content-Type': 'application/json' };
    if (key) h['X-API-Key'] = key;
    return h;
  }
  async function getJSON(url) {
    const full = apiUrl(url);
    const res = await fetch(full, { headers: apiHeaders() });
    if (!res.ok) throw new Error(`GET ${full} -> ${res.status}`);
    return res.json();
  }
  async function postJSON(url, body) {
    const full = apiUrl(url);
    const res = await fetch(full, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(body || {}) });
    if (!res.ok) throw new Error(`POST ${full} -> ${res.status}`);
    return res.json();
  }

  const DashboardAdapter = {
    latest: async (scope) => {
      const qs = scope?.maxAge ? `?max_age_s=${encodeURIComponent(scope.maxAge)}` : '';
      const data = await getJSON(`/dashboard/latest${qs}`);
      return { ok: true, ts: Date.now(), raw: data };
    }
  };

  const InsightsAdapter = {
    list: async (tenant) => {
      const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : '';
      const data = await getJSON(`/insights${qs}`);
      return data?.insights || [];
    }
  };

  const MetricsAdapter = {
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

  const GrafanaAdapter = {
    iframeUrl(panelId, vars){
      const p = new URLSearchParams({ panelId });
      if (vars) p.set('vars', typeof vars==='string' ? vars : JSON.stringify(vars));
      return apiUrl(`/proxy/grafana/iframe?${p.toString()}`);
    },
    renderImage: async (panelId, vars) => {
      const p = new URLSearchParams({ panelId });
      if (vars) p.set('vars', typeof vars==='string' ? vars : JSON.stringify(vars));
      const res = await fetch(apiUrl(`/proxy/grafana/render?${p.toString()}`), { headers: apiHeaders() });
      if (!res.ok) throw new Error(`render ${panelId} -> ${res.status}`);
      return res.blob();
    }
  };

  const FindingsAdapter = {
    slaUpcoming: async () => {
      const data = await getJSON(`/findings/sla/upcoming`);
      return data?.items || [];
    },
    cves: async (_filter) => {
      return [];
    }
  };

  const TicketsAdapter = {
    createRemediation: async (input) => {
      const data = await postJSON(`/tickets/remediation`, input);
      return { ok: true, ...data };
    }
  };

  const FeedbackAdapter = {
    submit: async (input) => {
      const data = await postJSON(`/feedback`, input);
      return { ok: true, ...data };
    }
  };

  // Guards for tuner changes
  const TunerGuards = {
    canPreview: (user) => true,
    canApply: (user) => user?.role === 'soc_lead' || user?.role === 'platform_admin',
    withinWindow: (approval) => {
      if (!approval) return false;
      const now = Date.now();
      return now >= approval.start && now <= approval.end;
    }
  };

  // expose globals
  window.apiHeaders = apiHeaders;
  window.getJSON = getJSON;
  window.postJSON = postJSON;
  window.apiUrl = apiUrl;
  window.DashboardAdapter = DashboardAdapter;
  window.InsightsAdapter = InsightsAdapter;
  window.MetricsAdapter = MetricsAdapter;
  window.GrafanaAdapter = GrafanaAdapter;
  window.FindingsAdapter = FindingsAdapter;
  window.TicketsAdapter = TicketsAdapter;
  window.FeedbackAdapter = FeedbackAdapter;
  window.TunerGuards = TunerGuards;
})();
