/* WFO results renderer + shared metric formatter/EXPLAIN (used by analyzer.js too).
   window.renderWFO(host, result) mirrors app/views/wfopt.py. window.normalizeWFO assembles a
   result-shaped object from a saved /api/run payload (meta+settings+result+steps). */
(function () {
  const { el } = window.UI;
  const W = window.W, Ch = window.Charts;

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
      stability: r.stability, steps: api.steps || [], equity: r.equity,
      wfe: r.wfe, consistency: r.consistency, is_avg: r.is_avg
    };
  };

  const ROWS = ['total_return', 'cagr', 'sharpe', 'max_drawdown', 'exposure', 'round_trips',
    'win_rate', 'profit_factor'];
  const RATING_FLAG = { excellent: 'good', good: 'good', weak: 'warn', overfit: 'bad', na: 'off' };
  const RATING_TXT = { excellent: 'excellent (>70%)', good: 'good (50-70%)', weak: 'weak (30-50%)', overfit: 'overfit (<30%)', na: 'undefined' };

  function tabOverview(host, res) {
    const wfe = res.wfe || {}, cons = res.consistency || {}, oos = res.oos || {}, isA = res.is_avg || {};
    const wval = wfe.wfe == null ? 'n/a' : (wfe.wfe * 100).toFixed(0) + '%';
    // headline KPIs: WFE + the two CAGRs it's built from
    host.append(el('div', { class: 'grid cols-3', style: 'margin-bottom:12px;' },
      el('div', { class: 'card kpi' }, el('div', { class: 'k-label' }, 'Walk-forward efficiency (OOS / IS return)'),
        el('div', { class: 'k-value ' + (wfe.wfe == null ? '' : wfe.wfe >= 0.5 ? 'pos' : 'neg') }, wval),
        el('div', { class: 'k-sub' }, RATING_TXT[wfe.rating] || '')),
      el('div', { class: 'card kpi' }, el('div', { class: 'k-label' }, 'In-sample CAGR (avg)'),
        el('div', { class: 'k-value' }, fmtMetric('cagr', wfe.is_cagr_mean))),
      el('div', { class: 'card kpi' }, el('div', { class: 'k-label' }, 'Out-of-sample CAGR'),
        el('div', { class: 'k-value ' + ((wfe.oos_cagr || 0) >= 0 ? 'pos' : 'neg') }, fmtMetric('cagr', wfe.oos_cagr)))));
    host.append(W.flag(RATING_FLAG[wfe.rating] || 'off', '<b>Read:</b> ' + (wfe.wfe == null
      ? (wfe.note || 'WFE undefined.')
      : `Walk-forward efficiency ${wval} (${RATING_TXT[wfe.rating]}) - out-of-sample kept ${wval} of the in-sample edge. `
        + (wfe.wfe >= 0.5 ? 'A real edge survives re-tuning.' : 'Most of the in-sample edge did not generalize.'))));

    // IS vs OOS aggregate table
    const t = el('table', { class: 'data' });
    t.append(el('thead', {}, el('tr', {}, el('th', {}, 'metric'), el('th', {}, 'what it means'),
      el('th', { class: 'num' }, 'in-sample (avg)'), el('th', { class: 'num' }, 'out-of-sample'))));
    const tb = el('tbody');
    ROWS.forEach(k => tb.append(el('tr', {}, el('td', { html: `<b>${k}</b>` }),
      el('td', { class: 'dim' }, window.EXPLAIN[k] || ''),
      el('td', { class: 'num mono' }, fmtMetric(k, isA[k])),
      el('td', { class: 'num mono' }, fmtMetric(k, oos[k])))));
    t.append(tb);
    host.append(W.card('In-sample (training) vs Out-of-sample (honest)', el('div', { class: 'tbl-wrap' }, t)));

    // consistency + validity flags
    const np = cons.n_pos_oos || 0, nw = cons.n_windows || 1;
    const g = el('div', { class: 'grid cols-2', style: 'margin-top:6px;' });
    g.append(W.flag(np >= nw * 0.6 ? 'good' : np >= nw * 0.4 ? 'warn' : 'bad',
      `<b>Consistency:</b> ${np} of ${nw} windows positive OOS. Sharpe dispersion ${W.num(cons.oos_sharpe_std)} `
      + `(lower = steadier). Worst window drawdown ${fmtMetric('max_drawdown', cons.worst_window_dd)}.`));
    g.append(W.flag(cons.concentrated ? 'bad' : 'good',
      `<b>Validity:</b> biggest single window made ${((cons.concentration_pct || 0) * 100).toFixed(0)}% of OOS profit. `
      + (cons.concentrated ? 'Over 50% from one window - fragile / lucky period.' : 'No single window dominates - healthy.')));
    host.append(g);

    // overfit ceiling - secondary reference only
    const full = (res.full_best || {}).metrics || {};
    host.append(el('div', { class: 'note', style: 'margin-top:10px;',
      html: `Overfit ceiling (reference only): the single best config chosen with hindsight, measured on the SAME OOS span, `
        + `returns <b>${fmtMetric('total_return', full.total_return)}</b> vs the honest <b>${fmtMetric('total_return', oos.total_return)}</b>. `
        + `A ceiling, not an expectation. Config <code>${JSON.stringify((res.full_best || {}).params || {})}</code>.` }));
  }

  function tabEquity(host, res) {
    const eq = res.equity || {}, oosC = eq.oos || { dates: [], pct: [] }, fullC = eq.full || { dates: [], pct: [] };
    if ((oosC.dates || []).length || (fullC.dates || []).length) {
      const cc = W.chartCard('Out-of-sample equity (honest) vs overfit ceiling - same span, % from start', 'xtall');
      host.append(cc.card);
      const dates = [...new Set([...(fullC.dates || []), ...(oosC.dates || [])])].sort();
      const onto = c => { const m = {}; (c.dates || []).forEach((d, i) => m[d] = c.pct[i]); return dates.map(d => d in m ? m[d] : null); };
      Ch.multiLine(cc.box, {
        x: dates, yFormatter: v => v == null ? '-' : v.toFixed(0) + '%',
        series: [
          { name: 'Overfit ceiling (hindsight)', color: Ch.C.amber, data: onto(fullC) },
          { name: 'Walk-forward OOS (honest)', color: Ch.C.accent, data: onto(oosC) },
        ]
      });
      host.append(el('div', { class: 'note', style: 'margin-top:6px;' },
        'Both lines now cover the SAME out-of-sample span. Teal = honest re-tuned-per-window result '
        + '(what you would expect). Amber = the one config you would have picked with hindsight (a ceiling).'));
    } else {
      host.append(W.flag('off', 'No equity curves saved for this run (it predates the curve feature). Re-run to generate.'));
    }
    // side-by-side stats
    const oos = res.oos || {}, full = (res.full_best || {}).metrics || {};
    const STAT = [['total_return', 'Net'], ['cagr', 'CAGR'], ['sharpe', 'Sharpe'], ['max_drawdown', 'Max DD'],
      ['win_rate', 'Win rate'], ['exposure', 'Exposure'], ['round_trips', 'Trades'], ['profit_factor', 'Profit factor']];
    const statCard = (title, m) => {
      const t = el('table', { class: 'data' });
      t.append(el('tbody', {}, ...STAT.map(([k, lab]) => el('tr', {}, el('td', {}, lab),
        el('td', { class: 'num mono' }, fmtMetric(k, m[k]))))));
      return W.card(title, t);
    };
    const g = el('div', { class: 'grid cols-2', style: 'margin-top:14px;' });
    g.append(statCard('Walk-forward OOS (honest)', oos), statCard('Overfit ceiling (hindsight, same span)', full));
    host.append(g);
  }

  function tabWindows(host, res) {
    const pw = res.wfe ? (res.wfe.per_window || []) : [];
    const ft = el('table', { class: 'data' });
    ft.append(el('thead', {}, el('tr', {},
      ...['fold', 'test window', 'picked params', 'IS net', 'IS sharpe', 'OOS net', 'OOS sharpe', 'WFE']
        .map((h, i) => el('th', { class: i >= 3 ? 'num' : '' }, h)))));
    const ftb = el('tbody');
    (res.steps || []).forEach((s, i) => {
      const is = s.is || {}, t = s.test || {};
      const p = Object.entries(s.params || {}).map(([k, v]) => `${k}=${v}`).join(', ');
      const w = pw[i];
      ftb.append(el('tr', {}, el('td', {}, String(s.fold)),
        el('td', { class: 'mono' }, `${s.test_from} -> ${s.test_to}`),
        el('td', { class: 'mono' }, p),
        el('td', { class: 'num mono ' + ((is.total_return || 0) >= 0 ? 'pos' : 'neg') }, fmtMetric('total_return', is.total_return)),
        el('td', { class: 'num mono' }, W.num(is.sharpe)),
        el('td', { class: 'num mono ' + ((t.total_return || 0) >= 0 ? 'pos' : 'neg') }, fmtMetric('total_return', t.total_return)),
        el('td', { class: 'num mono' }, W.num(t.sharpe)),
        el('td', { class: 'num mono' }, w == null ? 'n/a' : (w * 100).toFixed(0) + '%')));
    });
    ft.append(ftb);
    host.append(W.card('Per window: in-sample (train) vs out-of-sample (test), and efficiency', el('div', { class: 'tbl-wrap' }, ft)));
    host.append(el('div', { class: 'note', style: 'margin-top:6px;' },
      'WFE per window = OOS return / IS return; it is noisy when IS return is tiny (shown n/a when IS <= 0). '
      + 'The aggregate WFE on the Overview tab is the reliable number.'));
  }

  function tabStability(host, res) {
    const stab = res.stability || {};
    if (!Object.keys(stab).length) { host.append(el('div', { class: 'note' }, 'No swept parameters.')); return; }
    host.append(el('div', { class: 'note', style: 'margin-bottom:10px;' },
      'How often each swept value was re-chosen across folds. A param that jumps around fold-to-fold has no stable optimum.'));
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
    host.append(grid);
  }

  window.renderWFO = function (host, res) {
    host.innerHTML = '';
    const win = res.anchored ? 'Anchored' : 'Rolling';
    const dr = res.date_range || ['?', '?'];
    host.append(el('div', { class: 'note', style: 'margin-bottom:14px;',
      html: `<b>${win} walk-forward</b> &nbsp;|&nbsp; optimize on <code>${res.objective}</code> `
        + `&nbsp;|&nbsp; train ${res.train_days}d / test ${res.test_days}d &nbsp;|&nbsp; ${res.n_windows} windows `
        + `&nbsp;|&nbsp; ${res.n_configs} configs &nbsp;|&nbsp; range ${dr[0]} -> ${dr[1]} `
        + `&nbsp;|&nbsp; OOS ${(res.oos_span || [])[0]} -> ${(res.oos_span || [])[1]}` }));
    const tabs = ['Overview', 'Equity', 'Windows', 'Stability'];
    let active = 'Overview';
    const bar = el('div'), body = el('div');
    host.append(bar, body);
    function draw() {
      bar.innerHTML = ''; bar.append(W.tabs(tabs, active, v => { active = v; draw(); }));
      body.innerHTML = '';
      if (active === 'Overview') tabOverview(body, res);
      else if (active === 'Equity') tabEquity(body, res);
      else if (active === 'Windows') tabWindows(body, res);
      else tabStability(body, res);
    }
    draw();
  };
})();
