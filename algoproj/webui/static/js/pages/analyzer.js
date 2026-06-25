/* Analyzer - BUILD & RUN only (one job): pick a strategy + backtest type, set params (or a
   sweep), and launch. On completion it hands the saved run to the Run Report (Performance /
   Robustness). Inspecting results lives in report.js; the run library lives in runs.js.
   Ports the config half of app/analyzer.py + app/sidebar.py. */
(function () {
  const { el } = window.UI;
  const W = window.W;
  const MODES = ['Backtest', 'Walk-Forward Optimization', 'Anchored Walk-Forward Optimization'];
  const OBJECTIVES = ['sharpe', 'total_return', 'cagr', 'profit_factor', 'expectancy'];

  function parseMinMax(text) {
    const p = String(text).replace(/,/g, ';').split(';').map(s => s.trim()).filter(Boolean);
    if (p.length !== 3) return null;
    const n = p.map(Number); if (n.some(isNaN)) return null;
    return n;
  }
  function gridSize(sweep) {
    let n = 1;
    for (const k in sweep) { const s = parseMinMax(sweep[k]); if (s) n *= Math.max(1, Math.floor((s[1] - s[0]) / s[2]) + 1); }
    return n;
  }

  function toReport(path) {
    if (!path) return;
    sessionStorage.setItem('report_run', path);
    location.hash = 'report';
  }

  function render(main) {
    main.innerHTML = '';
    main.append(el('div', { class: 'page-head' },
      el('h1', {}, 'Analyzer'),
      el('div', { class: 'crumbs' }, 'Build & run - results open in the Run report')));
    const wrap = el('div', { style: 'max-width:560px;' });
    main.append(wrap);

    const ctx = { strategies: [], dateRange: ['2005-01-11', '2025-01-10'],
      mode: 'Backtest', strat: null, overrides: {}, sweep: {}, execOpen: false,
      objective: 'sharpe', start: null, end: null, train_days: 1095, test_days: 365 };

    Promise.all([
      window.API.get('/api/strategies'),
      window.API.get('/api/date-range?ltf=15m').catch(() => ['2005-01-11', '2025-01-10'])
    ]).then(([strategies, dr]) => {
      ctx.strategies = strategies; ctx.dateRange = dr;
      ctx.strat = strategies[0].name; ctx.start = dr[0]; ctx.end = dr[1];
      initOverrides(); buildPanel();
    });

    function strategy() { return ctx.strategies.find(s => s.name === ctx.strat); }
    function initOverrides() {
      const s = strategy(); ctx.overrides = {}; ctx.sweep = {};
      for (const k in s.default) { const v = s.default[k]; if (typeof v === 'number' || k === 'sizing') ctx.overrides[k] = v; }
    }

    function buildPanel() {
      wrap.innerHTML = '';
      const s = strategy();
      const isWFO = ctx.mode !== 'Backtest';
      const panel = el('div', { class: 'card' });
      panel.append(el('div', { class: 'card-head' }, el('h3', {}, 'Settings')));

      panel.append(W.select('Backtest type', MODES, ctx.mode, v => { ctx.mode = v; buildPanel(); }));
      panel.append(W.select('Strategy', ctx.strategies.map(x => x.name), ctx.strat, v => { ctx.strat = v; initOverrides(); buildPanel(); }));
      panel.append(el('div', { class: 'note', style: 'margin:6px 0;',
        html: `<b>${s.default.symbol}</b> &nbsp; HTF ${s.default.htf_tf} &nbsp; LTF ${s.default.ltf_tf} &nbsp; full history` }));

      const sigNum = s.signal.filter(k => typeof s.default[k] === 'number');
      const pg = el('div', {}, el('div', { class: 'section-title', style: 'margin:10px 0 6px;' }, 'Strategy parameters'));
      sigNum.forEach(k => {
        if (isWFO) {
          const swept = k in ctx.sweep;
          const cb = el('input', { type: 'checkbox' }); cb.checked = swept;
          const row = el('div', { class: 'ctrl' });
          row.append(el('label', { style: 'display:flex;gap:6px;align-items:center;' }, cb, 'sweep ' + k));
          cb.addEventListener('change', () => {
            if (cb.checked) ctx.sweep[k] = `${s.default[k]};${s.default[k]};${Number.isInteger(s.default[k]) ? 1 : 0.5}`;
            else delete ctx.sweep[k];
            buildPanel();
          });
          if (swept) {
            const inp = el('input', { type: 'text', value: ctx.sweep[k] });
            inp.addEventListener('input', () => { ctx.sweep[k] = inp.value; updateEstimate(); });
            row.append(inp);
            if (!parseMinMax(ctx.sweep[k])) row.append(el('div', { class: 'dim', style: 'font-size:11px;' }, 'use min;max;incr e.g. 60;80;10'));
          } else {
            row.append(W.numInput(null, ctx.overrides[k], { bare: true, step: Number.isInteger(s.default[k]) ? 1 : 'any', onChange: v => ctx.overrides[k] = Number(v) }));
          }
          pg.append(row);
        } else {
          pg.append(W.numInput(k, ctx.overrides[k], { step: Number.isInteger(s.default[k]) ? 1 : 'any', onChange: v => ctx.overrides[k] = Number(v) }));
        }
      });
      panel.append(pg);

      const exHead = el('div', { class: 'section-title', style: 'margin:12px 0 6px;cursor:pointer;' },
        (ctx.execOpen ? 'v ' : '> ') + 'Account & execution');
      exHead.addEventListener('click', () => { ctx.execOpen = !ctx.execOpen; buildPanel(); });
      panel.append(exHead);
      if (ctx.execOpen) {
        s.execution.forEach(k => {
          if (k === 'sizing') panel.append(W.select(k, ['fixed', 'risk_pct'], ctx.overrides[k], v => ctx.overrides[k] = v));
          else panel.append(W.numInput(k, ctx.overrides[k], { step: Number.isInteger(s.default[k]) ? 1 : 'any', onChange: v => ctx.overrides[k] = Number(v) }));
        });
      }

      let estimate = null;
      if (isWFO) {
        panel.append(el('div', { class: 'section-title', style: 'margin:12px 0 6px;' }, 'Optimize'));
        panel.append(W.select('Optimize on', OBJECTIVES, ctx.objective, v => ctx.objective = v));
        panel.append(W.dateInput('Start date', ctx.start, { min: ctx.dateRange[0], max: ctx.dateRange[1], onChange: v => { ctx.start = v; updateEstimate(); } }));
        panel.append(W.dateInput('End date', ctx.end, { min: ctx.dateRange[0], max: ctx.dateRange[1], onChange: v => { ctx.end = v; updateEstimate(); } }));
        panel.append(W.numInput('Optimization period (days)', ctx.train_days, { step: 30, min: 30, onChange: v => { ctx.train_days = +v; updateEstimate(); } }));
        panel.append(W.numInput('Test period (days)', ctx.test_days, { step: 7, min: 7, onChange: v => { ctx.test_days = +v; updateEstimate(); } }));
        estimate = el('div', { class: 'note', style: 'margin-top:8px;' });
        panel.append(estimate);
      }

      const prog = W.progress('');
      const btn = el('button', { class: 'btn', style: 'width:100%;margin-top:14px;' }, isWFO ? 'Run walk-forward' : 'Run backtest');
      btn.addEventListener('click', () => isWFO ? runWFO(btn, prog) : runBacktest(btn, prog));
      panel.append(btn, el('div', { style: 'margin-top:10px;' }, prog.el));

      wrap.append(panel);
      ctx._estimate = estimate;
      updateEstimate();

      function updateEstimate() {
        if (!ctx._estimate) return;
        const total = Math.max(1, (new Date(ctx.end) - new Date(ctx.start)) / 86400000);
        const tr = ctx.train_days, te = ctx.test_days, nCfg = gridSize(ctx.sweep);
        let html = `Selected timeline: ${Math.round(total).toLocaleString()} days<br>`;
        html += `Optimization period = ${(tr / total * 100).toFixed(0)}% &nbsp; Test period = ${(te / total * 100).toFixed(0)}%<br>`;
        if (total <= tr) html += 'Optimization period longer than timeline - widen dates.';
        else {
          const nwin = Math.max(1, Math.floor((total - tr) / te)), oos = nwin * te;
          html += `approx ${nwin} windows (each ${tr}d train -> ${te}d test)<br>`;
          html += `in-sample warm-up: ${tr}d (${(tr / total * 100).toFixed(0)}%) &middot; out-of-sample: ~${oos.toLocaleString()}d (${(oos / total * 100).toFixed(0)}%)<br>`;
        }
        html += nCfg ? `<b>${nCfg} configs</b> &middot; ~${Math.round(nCfg * 2.4)}s estimated` : 'Enable sweep on a parameter to define the grid.';
        ctx._estimate.innerHTML = html;
      }
      window._anUpdateEstimate = updateEstimate;
    }
    function updateEstimate() { if (window._anUpdateEstimate) window._anUpdateEstimate(); }

    async function runBacktest(btn, prog) {
      btn.disabled = true; prog.set(0.3, 'Running backtest (~3s estimated)...');
      try {
        const meta = await window.API.post('/api/backtest', { strategy: ctx.strat, overrides: ctx.overrides });
        prog.set(1, (meta.unchanged ? 'Unchanged - reused ' : 'Saved ') + meta.name + ' - opening report...');
        let path = meta.path;
        if (!path) { const runs = await window.API.get('/api/runs'); path = (runs.find(r => r.name === meta.name) || {}).path; }
        toReport(path);
      } catch (e) { prog.set(0, 'Error: ' + e.message); btn.disabled = false; }
    }
    async function runWFO(btn, prog) {
      const specs = {};
      for (const k in ctx.sweep) { const s = parseMinMax(ctx.sweep[k]); if (s) specs[k] = s; }
      if (!Object.keys(specs).length) { prog.set(0, 'Enable sweep on at least one parameter.'); return; }
      const n = gridSize(ctx.sweep);
      btn.disabled = true; prog.set(0.05, `Running ${n} configs (~${Math.round(n * 2.4)}s estimated)...`);
      try {
        const res = await window.API.post('/api/wfo', {
          strategy: ctx.strat, overrides: ctx.overrides, specs, objective: ctx.objective,
          train_days: ctx.train_days, test_days: ctx.test_days, anchored: ctx.mode.startsWith('Anchored'),
          start_date: ctx.start, end_date: ctx.end, mode: ctx.mode
        });
        prog.set(1, 'Saved ' + res.meta.name + ' - opening report...');
        toReport(res.meta.path);
      } catch (e) { prog.set(0, 'Error: ' + e.message); btn.disabled = false; }
    }
  }

  window.PAGES = window.PAGES || {};
  window.PAGES.analyzer = { id: 'analyzer', render };
})();
