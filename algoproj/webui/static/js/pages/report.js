/* Run Report - inspect ONE finished run. Two clearly separated concerns:
     Performance  (descriptive: "what happened")  = Summary | Equity | Trades | Chart
     Robustness   (evaluative:  "can I trust it")  = IS/OOS + walk-forward + significance + benchmark
   For a WFO run the whole report IS the robustness story (renderWFO). Reached by selecting a
   run on the Runs page or after a run completes in the Analyzer (via sessionStorage 'report_run'). */
(function () {
  const { el, sortableTable } = window.UI;
  const W = window.W, Ch = window.Charts;
  const enc = encodeURIComponent;

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
  const KPI = [['total_return', 'Net return'], ['cagr', 'CAGR'], ['sharpe', 'Sharpe'],
    ['max_drawdown', 'Max drawdown'], ['win_rate', 'Win rate'], ['exposure', 'Exposure']];

  // ===================== PERFORMANCE views =====================
  function kpiStrip(m) {
    const grid = el('div', { class: 'grid cols-6', style: 'margin-bottom:14px;' });
    KPI.forEach(([k, label]) => {
      const v = m[k];
      const cls = (k === 'sharpe') ? '' : (v >= 0 ? 'pos' : 'neg');
      grid.append(el('div', { class: 'card kpi' }, el('div', { class: 'k-label' }, label),
        el('div', { class: 'k-value ' + (k === 'max_drawdown' ? 'neg' : cls) }, window.fmtMetric(k, v))));
    });
    return grid;
  }
  // only genuinely signed performance metrics get red/green (costs/counts stay neutral)
  const SIGNED = new Set(['total_pnl', 'total_return', 'cagr', 'sharpe', 'sortino', 'calmar',
    'expectancy', 'avg_pnl', 'avg_win', 'avg_loss', 'largest_win', 'largest_loss',
    'profit_per_month', 'max_drawdown', 'max_drawdown_usd', 'gross_profit']);
  function signClass(k, v) {
    if (!SIGNED.has(k) || typeof v !== 'number' || !isFinite(v) || v === 0) return '';
    return v > 0 ? 'pos' : 'neg';
  }
  // NinjaTrader-style sectioned performance report
  const PERF_SECTIONS = [
    ['Performance', [
      ['total_pnl', 'Total net profit'], ['gross_profit', 'Gross profit'], ['gross_loss', 'Gross loss'],
      ['commission_total', 'Commission'], ['slippage_total', 'Total slippage'], ['fees_total', 'Total fees'],
      ['profit_factor', 'Profit factor'], ['total_return', 'Total return'], ['cagr', 'CAGR'],
      ['max_drawdown', 'Max. drawdown (%)'], ['max_drawdown_usd', 'Max. drawdown ($)'],
      ['sharpe', 'Sharpe ratio'], ['sortino', 'Sortino ratio'], ['calmar', 'Calmar ratio'],
      ['ulcer_index', 'Ulcer index'], ['r_squared', 'R-squared (curve smoothness)'],
      ['annual_vol', 'Annual volatility']]],
    ['Trades', [
      ['round_trips', 'Total # of trades'], ['win_rate', 'Percent profitable'],
      ['n_winners', '# of winning trades'], ['n_losers', '# of losing trades'], ['n_even', '# of even trades'],
      ['expectancy', 'Expectancy / trade'], ['avg_pnl', 'Avg. trade'], ['avg_win', 'Avg. winning trade'],
      ['avg_loss', 'Avg. losing trade'], ['payoff_ratio', 'Ratio avg win / avg loss'],
      ['max_consec_winners', 'Max consecutive winners'], ['max_consec_losses', 'Max consecutive losers'],
      ['largest_win', 'Largest winning trade'], ['largest_loss', 'Largest losing trade']]],
    ['Time & exposure', [
      ['avg_trades_per_day', 'Avg # of trades per day'], ['exposure', 'Time in market'],
      ['avg_bars_in_trade', 'Avg bars in trade'], ['profit_per_month', 'Profit per month'],
      ['max_time_to_recover_days', 'Max time to recover'], ['longest_flat_days', 'Longest flat period']]],
    ['Excursion (per trade)', [
      ['avg_mae', 'Avg MAE (adverse)'], ['avg_mfe', 'Avg MFE (favorable)'], ['avg_etd', 'Avg ETD (give-back)']]],
    ['Risk of ruin (Monte Carlo, reshuffled order)', [
      ['mc_median_dd', 'Median drawdown'], ['mc_p95_worst_dd', 'Worst-5% drawdown'],
      ['P(dd<-20%)', 'Prob. drawdown < -20%'], ['P(dd<-50%)', 'Prob. drawdown < -50%']]],
  ];
  function _sectionCard(name, rows, m) {
    const t = el('table', { class: 'data' });
    t.append(el('thead', {}, el('tr', {}, el('th', {}, name),
      el('th', { class: 'num' }, 'All'), el('th', { class: 'num' }, 'Long'), el('th', { class: 'num' }, 'Short'))));
    const tb = el('tbody');
    rows.forEach(([k, label]) => {
      if (!(k in m)) return;
      const cls = signClass(k, m[k]), val = window.fmtMetric(k, m[k]);
      tb.append(el('tr', {}, el('td', { title: window.EXPLAIN[k] || '' }, label),
        el('td', { class: 'num mono ' + cls }, val), el('td', { class: 'num mono ' + cls }, val),
        el('td', { class: 'num mono dim' }, '-')));
    });
    t.append(tb);
    return W.card(null, el('div', { class: 'tbl-wrap' }, t));
  }
  async function viewSummary(host, run, path) {
    const m = run.metrics || {};
    host.append(kpiStrip(m));
    const cols = el('div', { class: 'report-cols' });
    try {
      const eq = await window.API.get('/api/run/equity?path=' + enc(path));
      const t = el('table', { class: 'data' });
      t.append(el('thead', {}, el('tr', {}, el('th', {}, 'Period'), el('th', { class: 'num' }, ''))));
      t.append(el('tbody', {}, ...[['Start date', eq.dates[0]], ['End date', eq.dates[eq.dates.length - 1]], ['Trading days', String(eq.dates.length)]]
        .map(([lab, v]) => el('tr', {}, el('td', {}, lab), el('td', { class: 'num mono' }, v)))));
      cols.append(W.card(null, t));
    } catch (e) { /* dates optional */ }
    PERF_SECTIONS.forEach(([name, rows]) => cols.append(_sectionCard(name, rows, m)));
    host.append(cols);
    host.append(el('div', { class: 'note' }, 'Long-only strategy: Long = All, Short = none. Hover a row label for what it means.'));
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

  function performance(host, run, path) {
    const views = ['Summary', 'Equity', 'Trades', 'Chart'];
    let active = 'Summary';
    const bar = el('div'), body = el('div');
    host.append(bar, body);
    function draw() {
      bar.innerHTML = ''; bar.append(W.tabs(views, active, v => { active = v; draw(); }));
      body.innerHTML = '';
      if (active === 'Summary') viewSummary(body, run, path);
      else if (active === 'Equity') viewEquity(body, path);
      else if (active === 'Trades') viewTrades(body, path);
      else viewChart(body, path);
    }
    draw();
  }

  // ===================== ROBUSTNESS view =====================
  function iosVerdict(is, oos) {
    const a = is.sharpe, b = oos.sharpe;
    if (a == null || b == null) return ['off', 'Not enough data to judge.'];
    if (b < 0) return ['bad', 'Edge DIES out-of-sample - in-sample Sharpe is positive but OOS is negative. Classic overfit signature.'];
    if (b < a * 0.5) return ['warn', 'Edge weakens sharply out-of-sample (OOS Sharpe < half of in-sample).'];
    return ['good', 'Edge holds up reasonably out-of-sample.'];
  }
  function robustness(host, run, path) {
    host.append(el('div', { class: 'note', style: 'margin-bottom:12px;' },
      'Can you trust this run? Out-of-sample split, walk-forward stability, statistical significance, and the buy-and-hold benchmark.'));
    const ctl = el('div', { class: 'toolbar', style: 'margin-bottom:12px;' });
    const out = el('div');
    host.append(ctl, out);
    const state = { mode: 'Fraction', frac: 0.70, date: null };
    function buildCtl() {
      ctl.innerHTML = '';
      ctl.append(W.select('Split by', ['Fraction', 'Date'], state.mode, v => { state.mode = v; buildCtl(); recompute(); }));
      if (state.mode === 'Fraction')
        ctl.append(W.slider('In-sample fraction', { min: 0.5, max: 0.95, step: 0.05, value: state.frac, fmt: v => (v * 100).toFixed(0) + '%', onChange: v => { state.frac = v; recompute(); } }));
      else
        ctl.append(W.dateInput('Train up to', state.date || '2019-02-06', { onChange: v => { state.date = v; recompute(); } }));
    }
    let timer = null;
    function recompute() { clearTimeout(timer); timer = setTimeout(doRecompute, 120); }
    async function doRecompute() {
      const split = state.mode === 'Fraction' ? state.frac : (state.date || '2019-02-06');
      const ios = await window.API.get(`/api/run/validation?path=${enc(path)}&split=${split}`);
      out.innerHTML = '';
      out.append(el('div', { class: 'section-title' }, 'In-sample vs Out-of-sample'));
      out.append(el('div', { class: 'note', style: 'margin-bottom:10px;',
        html: `Train on the first <b>${ios.in_pct}%</b> (in-sample), test on the unseen last <b>${(100 - ios.in_pct).toFixed(0)}%</b>. Split at <b>${(ios.split_time || '').slice(0, 16)}</b>. Params chosen on in-sample, so OOS is the honest number. Drag to re-split.` }));
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
    const sig = a.significance || {}, bench = a.benchmark || {}, h = run.meta.headline || {};
    host.append(el('div', { class: 'section-title' }, 'Significance & benchmark'));
    const g = el('div', { class: 'grid cols-2' });
    const tt = sig.trade_t || {}, re = sig.random_entry || {};
    const sigT = el('table', { class: 'data' });
    const sigRows = [['Per-trade t-stat', W.num(tt.t)], ['Per-trade p-value', tt.p == null ? '-' : tt.p.toFixed(3)],
      ['# trades', tt.n == null ? '-' : String(Math.round(tt.n))], ['Random-entry p', re.p == null ? '-' : re.p.toFixed(3)],
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

  // ===================== page =====================
  window.PAGES = window.PAGES || {};
  window.PAGES.report = {
    id: 'report',
    async render(main) {
      const path = sessionStorage.getItem('report_run');
      main.append(el('div', { class: 'page-head' },
        el('h1', {}, 'Run report'),
        el('div', { class: 'crumbs', html: '<a href="#runs">Runs</a> / <b>' + (path ? path.split('/').pop() : '-') + '</b>' })));
      if (!path) { main.append(W.flag('off', 'No run selected. Open a run from the Runs page, or run one in the Analyzer.')); return; }
      const ld = W.loading('Loading run...'); main.append(ld);
      const run = await window.API.get('/api/run?path=' + enc(path));
      ld.remove();
      const m = run.meta;
      let changed = '';
      const diff = m.config_diff;
      if (diff && diff.changed && Object.keys(diff.changed).length)
        changed = ' | changed: ' + Object.entries(diff.changed).map(([k, v]) => `${k} ${v[0]}->${v[1]}`).join(', ');
      main.append(el('div', { class: 'note', style: 'margin-bottom:14px;',
        html: `<b>${m.name}</b> &nbsp;|&nbsp; <span class="pill">${m.backtest_type || 'Backtest'}</span> &nbsp;|&nbsp; ${m.strategy} &nbsp;|&nbsp; ${m.timestamp || m.date || ''}${changed}` }));

      // WFO run: the whole report is the robustness/walk-forward story
      if (m.kind === 'wfo') {
        main.append(el('div', { class: 'section-title' }, 'Robustness - walk-forward optimization'));
        const host = el('div'); main.append(host);
        window.renderWFO(host, window.normalizeWFO(run));
        return;
      }

      // backtest: Performance (what happened) vs Robustness (can I trust it)
      let active = 'Performance';
      const bar = el('div'), body = el('div');
      main.append(bar, body);
      function draw() {
        bar.innerHTML = ''; bar.append(W.tabs(['Performance', 'Robustness'], active, v => { active = v; draw(); }));
        body.innerHTML = '';
        if (active === 'Performance') performance(body, run, path);
        else robustness(body, run, path);
      }
      draw();
    }
  };
})();
