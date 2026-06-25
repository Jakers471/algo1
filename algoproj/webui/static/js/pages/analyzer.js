/* Analyzer page - NinjaTrader-style: Backtest type, strategy, params, run/optimize, plus
   result views (Summary | Trades | Equity | Chart | Validation) and the WFO results view.
   Ports app/analyzer.py + app/sidebar.py + app/views/{summary,trades,equity,chart,validation}.py */
(function () {
  const { el, sortableTable } = window.UI;
  const W = window.W, Ch = window.Charts;
  const enc = encodeURIComponent;
  const MODES = ['Backtest', 'Walk-Forward Optimization', 'Anchored Walk-Forward Optimization'];
  const OBJECTIVES = ['sharpe', 'total_return', 'cagr', 'profit_factor', 'expectancy'];

  const TRADE_HELP = {
    '#': 'Trade number, chronological.', entry: 'Entry timestamp (UTC bar).', exit: 'Exit timestamp.',
    entry_px: 'Entry fill price (index points).', exit_px: 'Exit fill price (index points).',
    'ret_%': 'Gross price return of the trade, %.', result: 'WIN if profitable, else LOSS.',
    reason: 'Why the trade exited (signal vs stop).', hold_bars: 'Bars held (15m bars).',
    hour_et: 'Hour of day US/Eastern entered (0-23).', dow: 'Day of week: 0=Mon .. 4=Fri.',
    bull15: '15m bull regime score at entry (0-100).', consol15: '15m consolidation score at entry.',
    bull1d: 'Daily (HTF) bull regime score at entry.'
  };
  const SUMMARY_ORDER = ['total_return', 'cagr', 'sharpe', 'sortino', 'calmar', 'annual_vol',
    'max_drawdown', 'exposure', 'round_trips', 'win_rate', 'expectancy', 'avg_win', 'avg_loss',
    'profit_factor', 'payoff_ratio', 'max_consec_losses', 'total_pnl', 'avg_pnl',
    'mc_median_dd', 'mc_p95_worst_dd', 'P(dd<-20%)', 'P(dd<-50%)'];
  const IOS_ROWS = ['total_return', 'cagr', 'sharpe', 'max_drawdown', 'exposure', 'round_trips',
    'win_rate', 'expectancy', 'profit_factor'];

  // ---- grid helpers (mirror algokit.optimize) ----
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

  // ===================== result views =====================
  function viewSummary(host, run) {
    const m = run.metrics || {};
    const keys = SUMMARY_ORDER.filter(k => k in m).concat(Object.keys(m).filter(k => !SUMMARY_ORDER.includes(k) && !k.startsWith('vs_bench')));
    const t = el('table', { class: 'data' });
    t.append(el('thead', {}, el('tr', {}, el('th', {}, 'metric'), el('th', { class: 'num' }, 'value'), el('th', {}, 'what it means'))));
    const tb = el('tbody');
    keys.forEach(k => tb.append(el('tr', {},
      el('td', { html: `<b>${k}</b>` }),
      el('td', { class: 'num mono' }, window.fmtMetric(k, m[k])),
      el('td', { class: 'dim' }, window.EXPLAIN[k] || ''))));
    t.append(tb);
    host.append(W.card('Performance & risk', el('div', { class: 'tbl-wrap' }, t)));
    host.append(el('div', { class: 'note' }, 'Strategy is long-only, so All trades = Long trades.'));
  }

  async function viewTrades(host, path) {
    const ld = W.loading('Loading trades...'); host.append(ld);
    const tr = await window.API.get('/api/run/trades?path=' + enc(path));
    ld.remove();
    const rows = tr.map((r, i) => Object.assign({ '#': i + 1, 'ret_%': r.ret * 100, result: r.ret > 0 ? 'WIN' : 'LOSS' }, r));
    const C = (k, num) => ({ key: k, label: `<span title="${TRADE_HELP[k] || ''}">${k}</span>`, num });
    const cols = [C('#', true), C('entry'), C('exit'), C('entry_px', true), C('exit_px', true),
      { key: 'ret_%', label: `<span title="${TRADE_HELP['ret_%']}">ret_%</span>`, num: true, html: r => `<span class="${r['ret_%'] >= 0 ? 'pos' : 'neg'}">${W.num(r['ret_%'], 3)}</span>` },
      C('result'), C('reason'), C('hold_bars', true), C('hour_et', true), C('dow', true),
      C('bull15', true), C('consol15', true), C('bull1d', true)];
    host.append(el('div', { class: 'section-title' }, `Trades (${tr.length}) - hover a header for what it means`));
    host.append(W.card(null, sortableTable(cols, rows, { initialSort: { key: '#', dir: 'asc' }, maxHeight: '640px' })));
  }

  async function viewEquity(host, path) {
    const cc = W.chartCard('Equity & drawdown', 'xtall'); host.append(cc.card);
    const eq = await window.API.get('/api/run/equity?path=' + enc(path));
    let peak = -Infinity;
    const dd = eq.equity.map(v => { peak = Math.max(peak, v); return +((v / peak - 1) * 100).toFixed(2); });
    Ch.equityDD(cc.box, { dates: eq.dates, equity: eq.equity, dd });
  }

  async function viewChart(host, path) {
    const cc = W.chartCard('Candles + orders', 'xtall'); host.append(cc.card);
    const ld = W.loading('Building chart (re-running strategy, ~3s)...'); cc.box.append(ld);
    const d = await window.API.get('/api/run/chart?path=' + enc(path));
    ld.remove();
    Ch.candles(cc.box, d);
  }

  function iosVerdict(is, oos) {
    const a = is.sharpe, b = oos.sharpe;
    if (a == null || b == null) return ['off', 'Not enough data to judge.'];
    if (b < 0) return ['bad', 'Edge DIES out-of-sample - in-sample Sharpe is positive but OOS is negative. Classic overfit signature.'];
    if (b < a * 0.5) return ['warn', 'Edge weakens sharply out-of-sample (OOS Sharpe < half of in-sample).'];
    return ['good', 'Edge holds up reasonably out-of-sample.'];
  }

  function viewValidation(host, path, run) {
    const ctl = el('div', { class: 'toolbar', style: 'margin-bottom:12px;' });
    const out = el('div');
    host.append(ctl, out);
    const state = { mode: 'Fraction', frac: 0.70, date: null };

    function buildCtl() {
      ctl.innerHTML = '';
      ctl.append(W.select('Split by', ['Fraction', 'Date'], state.mode, v => { state.mode = v; buildCtl(); recompute(); }));
      if (state.mode === 'Fraction') {
        ctl.append(W.slider('In-sample fraction', { min: 0.5, max: 0.95, step: 0.05, value: state.frac, fmt: v => (v * 100).toFixed(0) + '%', onChange: v => { state.frac = v; recompute(); } }));
      } else {
        ctl.append(W.dateInput('Train up to', state.date || '2019-02-06', { onChange: v => { state.date = v; recompute(); } }));
      }
    }
    let timer = null;
    function recompute() { clearTimeout(timer); timer = setTimeout(doRecompute, 120); }
    async function doRecompute() {
      const split = state.mode === 'Fraction' ? state.frac : (state.date || '2019-02-06');
      const ios = await window.API.get(`/api/run/validation?path=${enc(path)}&split=${split}`);
      out.innerHTML = '';
      out.append(el('div', { class: 'section-title' }, 'In-sample vs Out-of-sample'));
      out.append(el('div', { class: 'note', style: 'margin-bottom:10px;',
        html: `Train on the first <b>${ios.in_pct}%</b> (in-sample), test on the unseen last <b>${(100 - ios.in_pct).toFixed(0)}%</b>. `
          + `Split at <b>${(ios.split_time || '').slice(0, 16)}</b>. Params chosen on in-sample, so OOS is the honest number.` }));
      const t = el('table', { class: 'data' });
      t.append(el('thead', {}, el('tr', {}, el('th', {}, 'metric'), el('th', {}, 'what it means'),
        el('th', { class: 'num' }, 'in-sample'), el('th', { class: 'num' }, 'out-of-sample'))));
      const tb = el('tbody');
      IOS_ROWS.forEach(k => tb.append(el('tr', {}, el('td', { html: `<b>${k}</b>` }),
        el('td', { class: 'dim' }, window.EXPLAIN[k] || ''),
        el('td', { class: 'num mono' }, window.fmtMetric(k, ios.in_sample[k])),
        el('td', { class: 'num mono' }, window.fmtMetric(k, ios.out_of_sample[k])))));
      t.append(tb);
      out.append(el('div', { class: 'tbl-wrap' }, t));
      const [kind, msg] = iosVerdict(ios.in_sample, ios.out_of_sample);
      out.append(W.flag(kind, '<b>Read:</b> ' + msg));
      renderStatic(out, run);
    }
    buildCtl(); doRecompute();
  }

  function renderStatic(host, run) {
    const a = run.analysis || {};
    // walk-forward folds
    const wf = a.walk_forward || [];
    if (wf.length) {
      host.append(el('div', { class: 'section-title' }, 'Walk-forward (sequential folds, fixed config)'));
      const t = el('table', { class: 'data' });
      t.append(el('thead', {}, el('tr', {}, ...['fold', 'from', 'to', 'net', 'sharpe', 'win', 'trips', 'profit_factor']
        .map((h, i) => el('th', { class: i >= 3 ? 'num' : '' }, h)))));
      const tb = el('tbody');
      wf.forEach(f => tb.append(el('tr', {},
        el('td', {}, String(Math.round(f.fold))), el('td', { class: 'mono' }, (f.from || '').slice(0, 10)), el('td', { class: 'mono' }, (f.to || '').slice(0, 10)),
        el('td', { class: 'num mono ' + (f.total_return >= 0 ? 'pos' : 'neg') }, window.fmtMetric('total_return', f.total_return)),
        el('td', { class: 'num mono' }, W.num(f.sharpe)), el('td', { class: 'num mono' }, window.fmtMetric('win_rate', f.win_rate)),
        el('td', { class: 'num mono' }, String(Math.round(f.round_trips))), el('td', { class: 'num mono' }, W.num(f.profit_factor)))));
      t.append(tb);
      host.append(W.card(null, el('div', { class: 'tbl-wrap' }, t)));
      const pos = wf.filter(f => (f.sharpe || 0) > 0).length;
      host.append(W.flag(pos === wf.length ? 'good' : pos >= wf.length / 2 ? 'warn' : 'bad',
        `<b>Read:</b> ${pos} of ${wf.length} folds had a positive Sharpe.`));
    }
    // significance + benchmark
    const sig = a.significance || {}, bench = a.benchmark || {}, h = run.meta.headline || {};
    host.append(el('div', { class: 'section-title' }, 'Significance & benchmark'));
    const g = el('div', { class: 'grid cols-2' });
    const tt = sig.trade_t || {}, re = sig.random_entry || {};
    const sigT = el('table', { class: 'data' });
    const sigRows = [
      ['Per-trade t-stat', W.num(tt.t)], ['Per-trade p-value', tt.p == null ? '-' : tt.p.toFixed(3)],
      ['# trades', tt.n == null ? '-' : String(Math.round(tt.n))],
      ['Random-entry p', re.p == null ? '-' : re.p.toFixed(3)],
      ['Deflated Sharpe', W.num(sig.deflated_sharpe)], ['Configs tried', sig.n_trials == null ? '-' : String(Math.round(sig.n_trials))]];
    sigT.append(el('tbody', {}, ...sigRows.map(([k, v]) => el('tr', {}, el('td', {}, k), el('td', { class: 'num mono' }, v)))));
    const sigOk = tt.p != null && tt.p < 0.05 && re.p != null && re.p < 0.05;
    g.append(el('div', {}, W.card('Is the edge real, or luck?', sigT),
      W.flag(sigOk ? 'good' : 'bad', '<b>Read:</b> ' + (sigOk ? 'Trades beat zero AND timing beats random.' : 'Not statistically convincing - the edge is not separable from luck yet.'))));
    const cmpT = el('table', { class: 'data' });
    cmpT.append(el('thead', {}, el('tr', {}, el('th', {}, 'metric'), el('th', { class: 'num' }, 'strategy'), el('th', { class: 'num' }, 'buy & hold'))));
    const cmpRows = [['total_return', 'Net'], ['cagr', 'CAGR'], ['sharpe', 'Sharpe'], ['max_drawdown', 'Max DD']];
    cmpT.append(el('tbody', {}, ...cmpRows.map(([k, lab]) => el('tr', {}, el('td', {}, lab),
      el('td', { class: 'num mono' }, window.fmtMetric(k, h[k])), el('td', { class: 'num mono' }, window.fmtMetric(k, bench[k]))))));
    const beat = (h.total_return || 0) > (bench.total_return || 0);
    g.append(el('div', {}, W.card('Strategy vs buy & hold', cmpT),
      W.flag(beat ? 'good' : 'bad', '<b>Read:</b> ' + (beat ? 'Strategy beats buy & hold on net return.' : 'Buy & hold still wins on net return.'))));
    host.append(g);
  }

  async function showRun(host, path) {
    host.innerHTML = '';
    const ld = W.loading('Loading run...'); host.append(ld);
    const run = await window.API.get('/api/run?path=' + enc(path));
    ld.remove();
    if (run.meta.kind === 'wfo') { window.renderWFO(host, window.normalizeWFO(run)); return; }
    const m = run.meta, diff = m.config_diff;
    let changed = '';
    if (diff && diff.changed && Object.keys(diff.changed).length)
      changed = ' | changed: ' + Object.entries(diff.changed).map(([k, v]) => `${k} ${v[0]}->${v[1]}`).join(', ');
    host.append(el('div', { class: 'note', style: 'margin-bottom:10px;',
      html: `<b>${m.name}</b> &nbsp;|&nbsp; ${m.strategy} &nbsp;|&nbsp; ${m.timestamp} &nbsp;|&nbsp; parent ${m.parent || '-'}${changed}` }));
    const views = ['Summary', 'Trades', 'Equity', 'Chart', 'Validation'];
    let active = 'Summary';
    const tabHost = el('div'), barHost = el('div');
    host.append(barHost, tabHost);
    function draw() {
      barHost.innerHTML = ''; barHost.append(W.tabs(views, active, v => { active = v; draw(); }));
      tabHost.innerHTML = '';
      if (active === 'Summary') viewSummary(tabHost, run);
      else if (active === 'Trades') viewTrades(tabHost, path);
      else if (active === 'Equity') viewEquity(tabHost, path);
      else if (active === 'Chart') viewChart(tabHost, path);
      else viewValidation(tabHost, path, run);
    }
    draw();
  }

  // ===================== config panel =====================
  function render(main) {
    main.innerHTML = '';
    main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Analyzer')));
    const layout = el('div', { class: 'layout-side' });
    const resultHost = el('div');
    const cfgWrap = el('div', { class: 'sticky-cfg' });
    layout.append(resultHost, cfgWrap);
    main.append(layout);

    const ctx = { strategies: [], runs: [], dateRange: ['2005-01-11', '2025-01-10'],
      mode: 'Backtest', strat: null, overrides: {}, sweep: {}, execOpen: false,
      objective: 'sharpe', start: null, end: null, train_days: 1095, test_days: 365 };

    Promise.all([
      window.API.get('/api/strategies'),
      window.API.get('/api/runs'),
      window.API.get('/api/date-range?ltf=15m').catch(() => ['2005-01-11', '2025-01-10'])
    ]).then(([strategies, runs, dr]) => {
      ctx.strategies = strategies; ctx.runs = runs; ctx.dateRange = dr;
      ctx.strat = strategies[0].name; ctx.start = dr[0]; ctx.end = dr[1];
      initOverrides();
      buildPanel();
      const initPath = sessionStorage.getItem('analyzer_run');
      if (initPath) { sessionStorage.removeItem('analyzer_run'); showRun(resultHost, initPath); }
      else resultHost.append(W.flag('off', 'Set parameters on the right and Run a backtest, or load a saved run.'));
    });

    function strategy() { return ctx.strategies.find(s => s.name === ctx.strat); }
    function initOverrides() {
      const s = strategy(); ctx.overrides = {}; ctx.sweep = {};
      for (const k in s.default) { const v = s.default[k]; if (typeof v === 'number' || k === 'sizing') ctx.overrides[k] = v; }
    }

    function buildPanel() {
      cfgWrap.innerHTML = '';
      const s = strategy();
      const isWFO = ctx.mode !== 'Backtest';
      const panel = el('div', { class: 'card' });
      panel.append(el('div', { class: 'card-head' }, el('h3', {}, 'Settings')));

      panel.append(W.select('Backtest type', MODES, ctx.mode, v => { ctx.mode = v; buildPanel(); }));
      panel.append(W.select('Strategy', ctx.strategies.map(x => x.name), ctx.strat, v => { ctx.strat = v; initOverrides(); buildPanel(); }));
      panel.append(el('div', { class: 'note', style: 'margin:6px 0;',
        html: `<b>${s.default.symbol}</b> &nbsp; HTF ${s.default.htf_tf} &nbsp; LTF ${s.default.ltf_tf} &nbsp; full history` }));

      // strategy parameters (numeric signal params)
      const sigNum = s.signal.filter(k => typeof s.default[k] === 'number');
      const pg = el('div', {}, el('div', { class: 'section-title', style: 'margin:10px 0 6px;' }, 'Strategy parameters'));
      sigNum.forEach(k => {
        if (isWFO) {
          const swept = k in ctx.sweep;
          const cb = el('input', { type: 'checkbox' }); cb.checked = swept;
          const row = el('div', { class: 'ctrl' });
          const head = el('label', { style: 'display:flex;gap:6px;align-items:center;' }, cb, 'sweep ' + k);
          row.append(head);
          cb.addEventListener('change', () => {
            if (cb.checked) ctx.sweep[k] = `${s.default[k]};${s.default[k]};${Number.isInteger(s.default[k]) ? 1 : 0.5}`;
            else delete ctx.sweep[k];
            buildPanel();
          });
          if (swept) {
            const inp = el('input', { type: 'text', value: ctx.sweep[k] });
            inp.addEventListener('input', () => { ctx.sweep[k] = inp.value; updateEstimate(); });
            row.append(inp);
            const ok = parseMinMax(ctx.sweep[k]);
            if (!ok) row.append(el('div', { class: 'dim', style: 'font-size:11px;' }, 'use min;max;incr e.g. 60;80;10'));
          } else {
            row.append(W.numInput(null, ctx.overrides[k], { bare: true, step: Number.isInteger(s.default[k]) ? 1 : 'any', onChange: v => ctx.overrides[k] = Number(v) }));
          }
          pg.append(row);
        } else {
          pg.append(W.numInput(k, ctx.overrides[k], { step: Number.isInteger(s.default[k]) ? 1 : 'any', onChange: v => ctx.overrides[k] = Number(v) }));
        }
      });
      panel.append(pg);

      // account & execution (collapsible)
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

      // optimize panel
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

      // run + progress
      const prog = W.progress('');
      const btn = el('button', { class: 'btn', style: 'width:100%;margin-top:14px;' }, isWFO ? 'Run walk-forward' : 'Run backtest');
      btn.addEventListener('click', () => isWFO ? runWFO(btn, prog) : runBacktest(btn, prog));
      panel.append(btn, el('div', { style: 'margin-top:10px;' }, prog.el));

      // load saved run
      panel.append(el('div', { class: 'section-title', style: 'margin:14px 0 6px;' }, 'Load saved run'));
      const loadSel = el('select');
      loadSel.append(el('option', { value: '' }, '-- select --'));
      ctx.runs.slice().reverse().forEach(m => loadSel.append(el('option', { value: m.path }, `${m.strategy} / ${m.name}`)));
      loadSel.addEventListener('change', () => { if (loadSel.value) showRun(resultHost, loadSel.value); });
      panel.append(W.field(null, loadSel));

      cfgWrap.append(panel);
      ctx._estimate = estimate;
      updateEstimate();

      function updateEstimate() {
        if (!ctx._estimate) return;
        const total = Math.max(1, (new Date(ctx.end) - new Date(ctx.start)) / 86400000);
        const tr = ctx.train_days, te = ctx.test_days;
        const nCfg = gridSize(ctx.sweep);
        let html = `Selected timeline: ${Math.round(total).toLocaleString()} days<br>`;
        html += `Optimization period = ${(tr / total * 100).toFixed(0)}% &nbsp; Test period = ${(te / total * 100).toFixed(0)}%<br>`;
        if (total <= tr) html += 'Optimization period longer than timeline - widen dates.';
        else {
          const nwin = Math.max(1, Math.floor((total - tr) / te)); const oos = nwin * te;
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
        prog.set(1, (meta.unchanged ? 'Unchanged - reused ' : 'Saved ') + meta.name);
        ctx.runs = await window.API.get('/api/runs');
        // dedup branch returns an old meta that may lack .path; resolve from the registry by name
        const path = meta.path || (ctx.runs.find(r => r.name === meta.name) || {}).path;
        await showRun(resultHost, path); buildPanel();
      } catch (e) { prog.set(0, 'Error: ' + e.message); }
      btn.disabled = false;
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
        prog.set(1, 'Saved ' + res.meta.name);
        window.renderWFO(resultHost, res.result);
        ctx.runs = await window.API.get('/api/runs'); buildPanel();
      } catch (e) { prog.set(0, 'Error: ' + e.message); }
      btn.disabled = false;
    }
  }

  window.PAGES = window.PAGES || {};
  window.PAGES.analyzer = { id: 'analyzer', render };
})();
