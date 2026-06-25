/* Performance page - the BACKTEST output viewer. Lists backtest runs (filter by strategy);
   click one to see its full Summary | Equity | Trades | Chart. No robustness / no IS-OOS
   slider (that was fake validation on a single config - removed). Reached from the nav, from
   the Runs Backtests tab, or automatically after a backtest finishes (sessionStorage perf_run). */
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
  const KPI = [['total_return', 'Net return'], ['cagr', 'CAGR'], ['sharpe', 'Sharpe'],
    ['max_drawdown', 'Max drawdown'], ['win_rate', 'Win rate'], ['exposure', 'Exposure']];
  const SIGNED = new Set(['total_pnl', 'total_return', 'cagr', 'sharpe', 'sortino', 'calmar',
    'expectancy', 'avg_pnl', 'avg_win', 'avg_loss', 'largest_win', 'largest_loss',
    'profit_per_month', 'max_drawdown', 'max_drawdown_usd', 'gross_profit']);
  const signClass = (k, v) => (!SIGNED.has(k) || typeof v !== 'number' || !isFinite(v) || v === 0)
    ? '' : (v > 0 ? 'pos' : 'neg');

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

  // ---- the four views ----
  function kpiStrip(m) {
    const grid = el('div', { class: 'grid cols-6', style: 'margin-bottom:14px;' });
    KPI.forEach(([k, label]) => {
      const v = m[k], cls = (k === 'sharpe') ? '' : (v >= 0 ? 'pos' : 'neg');
      grid.append(el('div', { class: 'card kpi' }, el('div', { class: 'k-label' }, label),
        el('div', { class: 'k-value ' + (k === 'max_drawdown' ? 'neg' : cls) }, window.fmtMetric(k, v))));
    });
    return grid;
  }
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

  async function showDetail(main, path) {
    main.innerHTML = '';
    main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Performance'),
      el('div', { class: 'crumbs', html: '<a href="#performance">Performance</a> / <b>' + path.split('/').pop() + '</b>' })));
    const back = el('a', { href: '#performance', class: 'chip', style: 'margin-bottom:12px;display:inline-block;' }, '< all runs');
    main.append(back);
    const ld = W.loading('Loading run...'); main.append(ld);
    const run = await window.API.get('/api/run?path=' + enc(path));
    ld.remove();
    if (run.meta.kind !== 'backtest') {  // safety: WFO/anchored belong on the WFO result page
      sessionStorage.setItem('wfo_run', path); location.hash = 'wforesult'; return;
    }
    const m = run.meta, diff = m.config_diff;
    let changed = '';
    if (diff && diff.changed && Object.keys(diff.changed).length)
      changed = ' | changed: ' + Object.entries(diff.changed).map(([k, v]) => `${k} ${v[0]}->${v[1]}`).join(', ');
    main.append(el('div', { class: 'note', style: 'margin-bottom:12px;',
      html: `<b>${m.name}</b> &nbsp;|&nbsp; <span class="pill">${m.backtest_type || 'Backtest'}</span> &nbsp;|&nbsp; ${m.strategy} &nbsp;|&nbsp; ${m.timestamp || m.date || ''}${changed}` }));
    const views = ['Summary', 'Equity', 'Trades', 'Chart'];
    let active = 'Summary';
    const bar = el('div'), body = el('div');
    main.append(bar, body);
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

  async function showList(main) {
    main.innerHTML = '';
    main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Performance'),
      el('div', { class: 'crumbs' }, 'Backtest outputs - pick a run to see its full breakdown')));
    const ld = W.loading('Loading runs...'); main.append(ld);
    const metas = (await window.API.get('/api/runs')).filter(m => (m.kind || 'backtest') === 'backtest');
    ld.remove();
    if (!metas.length) { main.append(W.flag('off', 'No backtests yet. Run one in the Analyzer.')); return; }
    const strats = [...new Set(metas.map(m => m.strategy))];
    const state = { strategy: 'All' };
    const bar = el('div', { class: 'toolbar', style: 'margin-bottom:12px;' });
    const tableHost = el('div');
    main.append(bar, tableHost);
    function redraw() {
      bar.innerHTML = '';
      bar.append(W.select('Strategy', ['All', ...strats], state.strategy, v => { state.strategy = v; redraw(); }));
      const rows = metas.filter(m => state.strategy === 'All' || m.strategy === state.strategy)
        .map(m => ({ run: m.name, strategy: m.strategy, date: m.date || (m.timestamp || '').slice(0, 10),
          net: (m.headline || {}).total_return, sharpe: (m.headline || {}).sharpe,
          max_dd: (m.headline || {}).max_drawdown, win: (m.headline || {}).win_rate, path: m.path }))
        .reverse();
      const cell = (v, kind) => v == null ? '<span class="dim">-</span>'
        : kind === 'sharpe' ? W.num(v) : `<span class="${v >= 0 ? 'pos' : 'neg'}">${W.pctSigned(v)}</span>`;
      const cols = [
        { key: 'run', label: 'Run', html: r => `<b>${r.run}</b>` },
        { key: 'strategy', label: 'Strategy' }, { key: 'date', label: 'Date' },
        { key: 'net', label: 'Net', num: true, html: r => cell(r.net), sortVal: r => r.net ?? -1e9 },
        { key: 'sharpe', label: 'Sharpe', num: true, html: r => cell(r.sharpe, 'sharpe'), sortVal: r => r.sharpe ?? -1e9 },
        { key: 'max_dd', label: 'Max DD', num: true, html: r => cell(r.max_dd), sortVal: r => r.max_dd ?? -1e9 },
        { key: 'win', label: 'Win', num: true, html: r => r.win == null ? '-' : W.pctRaw(r.win * 100, 0), sortVal: r => r.win ?? -1 },
      ];
      tableHost.innerHTML = '';
      tableHost.append(W.card(null, sortableTable(cols, rows, {
        rowClick: r => showDetail(main, r.path), initialSort: { key: 'date', dir: 'desc' }, maxHeight: '640px' })));
    }
    redraw();
  }

  window.PAGES = window.PAGES || {};
  window.PAGES.performance = {
    id: 'performance',
    async render(main) {
      const path = sessionStorage.getItem('perf_run');
      if (path) { sessionStorage.removeItem('perf_run'); await showDetail(main, path); }
      else await showList(main);
    }
  };
})();
