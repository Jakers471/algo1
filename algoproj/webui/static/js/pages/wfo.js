/* WFO results renderer + shared metric formatter/EXPLAIN (used by analyzer.js too).
   window.renderWFO(host, result) mirrors app/views/wfopt.py. window.normalizeWFO assembles a
   result-shaped object from a saved /api/run payload (meta+settings+result+steps). */
(function () {
  const { el } = window.UI;
  const W = window.W;

  // ---- shared metric formatting (mirrors algokit/metrics.fmt) ----
  const PCT = new Set(['total_return', 'cagr', 'annual_vol', 'max_drawdown', 'exposure',
    'win_rate', 'expectancy', 'avg_win', 'avg_loss', 'mc_median_dd', 'mc_p95_worst_dd',
    'largest_win', 'largest_loss', 'avg_mae', 'avg_mfe', 'avg_etd']);
  const USD = new Set(['total_pnl', 'avg_pnl', 'gross_profit', 'gross_loss', 'commission_total',
    'slippage_total', 'fees_total', 'profit_per_month', 'max_drawdown_usd']);
  const COUNT = new Set(['round_trips', 'max_consec_losses', 'max_consec_winners',
    'n_winners', 'n_losers', 'n_even']);
  function fmtMetric(key, val) {
    if (val == null) return 'n/a';
    if (typeof val === 'string') return val;
    if (key.endsWith('_days')) return Math.round(val).toLocaleString() + 'd';
    if (key.startsWith('P(dd')) return (val * 100).toFixed(1) + '%';
    if (USD.has(key)) return '$' + Math.round(val).toLocaleString();
    if (PCT.has(key)) return (val * 100).toFixed(2) + '%';
    if (COUNT.has(key)) return String(Math.round(val));
    return Number(val).toFixed(2);
  }
  window.fmtMetric = fmtMetric;
  window.isPctMetric = k => PCT.has(k);

  window.EXPLAIN = {
    total_return: 'Total compounded gain over the whole backtest.',
    cagr: 'Compound Annual Growth Rate - return smoothed to a yearly rate.',
    annual_vol: 'How much returns swing (annualized) = risk.',
    sharpe: 'Return per unit of TOTAL risk. >1 good, <0.5 weak, <0 losing.',
    sortino: 'Like Sharpe but only DOWNSIDE swings count as risk.',
    calmar: 'Annual return / worst drawdown - reward vs pain.',
    max_drawdown: 'Worst peak-to-trough drop the account would have felt.',
    exposure: 'Share of time actually holding a position (rest = in cash).',
    round_trips: 'Number of completed buy->sell trades.',
    win_rate: 'Share of trades that made money.',
    expectancy: 'Average profit PER TRADE (your edge per trade).',
    avg_win: 'Average size of a winning trade.',
    avg_loss: 'Average size of a losing trade.',
    profit_factor: 'Gross profit / gross loss. >1 profitable; 2 = wins double the losses.',
    payoff_ratio: 'Average win size / average loss size.',
    max_consec_losses: 'Longest losing streak - what you must stomach.',
    total_pnl: 'Total realized net profit in USD (after commission + slippage).',
    avg_pnl: 'Average net profit per trade in USD (after costs).',
    mc_median_dd: 'Typical worst-drawdown across reshuffled trade orders (robustness).',
    mc_p95_worst_dd: 'A bad-luck-ordering drawdown (worst 5%).',
    'P(dd<-20%)': 'Chance of a >20% drawdown across reshuffled orders.',
    'P(dd<-50%)': 'Chance of a >50% drawdown across reshuffled orders.',
    gross_profit: 'Sum of all winning trades (USD).',
    gross_loss: 'Sum of all losing trades, shown positive (USD).',
    commission_total: 'Total commission paid across all fills (USD).',
    slippage_total: 'Total adverse slippage paid across all fills (USD).',
    fees_total: 'Commission + slippage combined (USD).',
    max_drawdown_usd: 'Worst peak-to-trough drop in dollars.',
    n_winners: 'Number of winning trades.', n_losers: 'Number of losing trades.',
    n_even: 'Number of break-even trades.',
    largest_win: 'Biggest single winning trade (% return).',
    largest_loss: 'Biggest single losing trade (% return).',
    max_consec_winners: 'Longest winning streak.',
    avg_bars_in_trade: 'Average number of 15m bars a trade is held.',
    avg_trades_per_day: 'Average completed trades per trading day.',
    profit_per_month: 'Average net profit per month (USD).',
    ulcer_index: 'RMS of the drawdown series - pain/lumpiness of the curve (lower better).',
    r_squared: 'How linear the equity curve is vs time (0-1). Near 1 = smooth steady climb.',
    max_time_to_recover_days: 'Longest time spent below a prior equity peak.',
    longest_flat_days: 'Longest stretch with no equity movement (no trades / flat).',
    avg_mae: 'Avg Maximum Adverse Excursion - how far trades go against you before closing.',
    avg_mfe: 'Avg Maximum Favorable Excursion - how far in profit trades reach.',
    avg_etd: 'Avg End Trade Drawdown - profit given back from the trade peak by exit.',
  };

  // ---- assemble a result-shaped object from a saved /api/run payload ----
  window.normalizeWFO = function (api) {
    if (api && api.oos && api.steps && api.objective != null) return api; // already a fresh result
    const m = api.meta || {}, r = api.result || {};
    return {
      objective: m.objective, anchored: m.anchored, train_days: m.train_days, test_days: m.test_days,
      n_windows: m.n_windows, n_configs: m.n_configs, date_range: m.date_range,
      oos_span: r.oos_span || m.oos_span, oos: r.oos, full_best: r.full_best,
      stability: r.stability, steps: api.steps || []
    };
  };

  const ROWS = ['total_return', 'cagr', 'sharpe', 'max_drawdown', 'exposure', 'round_trips',
    'win_rate', 'profit_factor'];

  window.renderWFO = function (host, res) {
    host.innerHTML = '';
    const win = res.anchored ? 'Anchored' : 'Rolling';
    const dr = res.date_range || ['?', '?'];
    host.append(el('div', { class: 'note', style: 'margin-bottom:14px;',
      html: `<b>Walk-Forward Optimization</b> (${win}) &nbsp;|&nbsp; optimize on <code>${res.objective}</code> `
        + `&nbsp;|&nbsp; train ${res.train_days}d / test ${res.test_days}d &nbsp;|&nbsp; ${res.n_windows} windows `
        + `&nbsp;|&nbsp; ${res.n_configs} configs &nbsp;|&nbsp; range ${dr[0]} -> ${dr[1]} `
        + `&nbsp;|&nbsp; OOS ${(res.oos_span || [])[0]} -> ${(res.oos_span || [])[1]}` }));

    // ---- OOS vs best-on-full ----
    const oos = res.oos || {}, full = (res.full_best || {}).metrics || {};
    const t = el('table', { class: 'data' });
    t.append(el('thead', {}, el('tr', {}, el('th', {}, 'metric'),
      el('th', {}, 'what it means'),
      el('th', { class: 'num' }, 'walk-forward OOS'), el('th', { class: 'num' }, 'best-on-full'))));
    const tb = el('tbody');
    ROWS.forEach(k => tb.append(el('tr', {},
      el('td', { html: `<b>${k}</b>` }),
      el('td', { class: 'dim' }, window.EXPLAIN[k] || ''),
      el('td', { class: 'num mono' }, fmtMetric(k, oos[k])),
      el('td', { class: 'num mono' }, fmtMetric(k, full[k])))));
    t.append(tb);
    host.append(W.card('Walk-forward (honest) vs best-on-full-history (overfit)', el('div', { class: 'tbl-wrap' }, t)));

    const oosR = oos.total_return || 0, fullR = full.total_return || 0, gap = fullR - oosR;
    const kind = oosR <= 0 ? 'bad' : gap > 0.10 ? 'warn' : 'good';
    host.append(W.flag(kind, `<b>Read:</b> best-on-full shows ${(fullR * 100).toFixed(0)}% but the honest `
      + `walk-forward OOS is ${(oosR * 100).toFixed(0)}% - a ${(gap * 100).toFixed(0)}-pt overfit gap. `
      + (oosR <= 0 ? 'The OOS result is negative: re-tuning did not rescue it.'
        : 'The walk-forward number is what you could realistically expect.')));
    host.append(el('div', { class: 'note', style: 'margin:6px 0 18px;',
      html: `Best-on-full config: <code>${JSON.stringify((res.full_best || {}).params || {})}</code> - looked best over the `
        + 'WHOLE history (uses future info; shown only as a yardstick).' }));

    // ---- per-fold ----
    const ft = el('table', { class: 'data' });
    ft.append(el('thead', {}, el('tr', {},
      ...['fold', 'train <=', 'picked params', 'train ' + res.objective, 'test window', 'test net', 'test sharpe', 'test win']
        .map((h, i) => el('th', { class: i >= 3 ? 'num' : '' }, h)))));
    const ftb = el('tbody');
    (res.steps || []).forEach(s => {
      const p = Object.entries(s.params || {}).map(([k, v]) => `${k}=${v}`).join(', ');
      ftb.append(el('tr', {},
        el('td', {}, String(s.fold)),
        el('td', { class: 'mono' }, s.train_to),
        el('td', { class: 'mono' }, p),
        el('td', { class: 'num mono' }, W.num(s.train_score)),
        el('td', { class: 'mono' }, `${s.test_from} -> ${s.test_to}`),
        el('td', { class: 'num mono ' + ((s.test || {}).total_return >= 0 ? 'pos' : 'neg') }, fmtMetric('total_return', (s.test || {}).total_return)),
        el('td', { class: 'num mono' }, W.num((s.test || {}).sharpe)),
        el('td', { class: 'num mono' }, fmtMetric('win_rate', (s.test || {}).win_rate))));
    });
    ft.append(ftb);
    host.append(W.card('Per-fold: trained -> picked -> tested out-of-sample', el('div', { class: 'tbl-wrap' }, ft)));

    // ---- parameter stability ----
    const stab = res.stability || {};
    const grid = el('div', { class: 'grid cols-3' });
    Object.entries(stab).forEach(([p, counts]) => {
      const st = el('table', { class: 'data' });
      st.append(el('thead', {}, el('tr', {}, el('th', {}, 'value'), el('th', { class: 'num' }, 'times picked'))));
      const stb = el('tbody');
      Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([v, c]) =>
        stb.append(el('tr', {}, el('td', { class: 'mono' }, v), el('td', { class: 'num mono' }, String(c)))));
      st.append(stb);
      grid.append(W.card(p, st));
    });
    if (Object.keys(stab).length) {
      host.append(el('div', { class: 'section-title' }, 'Parameter stability'));
      host.append(el('div', { class: 'note', style: 'margin-bottom:10px;' },
        'How often each swept value was re-chosen across folds. A param that jumps around fold-to-fold has no stable optimum.'));
      host.append(grid);
    }
  };
})();
