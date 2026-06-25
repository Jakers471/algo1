/* Strategies page - strategy-vs-strategy, "which strategy is best?".
   Each strategy is represented by its CHAMPION run (the run maximizing a metric you pick
   live). Aggregate leaderboard (one row per strategy) + champion bar chart + head-to-head
   champion compare (metrics matrix + equity overlay). No param-diff (meaningless across
   strategies). Ported from app/views/strategies_browser.py. */
(function () {
  const { el, sortableTable } = window.UI;
  const W = window.W, Ch = window.Charts;

  // metric -> [label, isPercent]. net/cagr/max_dd/win are fractions; sharpe is raw.
  const METRICS = {
    net: ['Net return', true], cagr: ['CAGR', true], sharpe: ['Sharpe', false],
    max_dd: ['Max drawdown', true], win: ['Win rate', true]
  };

  const median = arr => {
    const a = arr.filter(v => v != null).sort((x, y) => x - y);
    if (!a.length) return null;
    const m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  };

  // per strategy: the row maximizing `metric` (skip nulls)
  function champions(rows, metric) {
    const byStrat = {};
    rows.forEach(r => (byStrat[r.strategy] = byStrat[r.strategy] || []).push(r));
    const champs = {};
    for (const s in byStrat) {
      const cand = byStrat[s].filter(r => r[metric] != null);
      if (cand.length) champs[s] = cand.reduce((a, b) => (b[metric] > a[metric] ? b : a));
    }
    return { byStrat, champs };
  }

  const numCell = (v, kind) => v == null ? '<span class="dim">-</span>'
    : kind === 'sharpe' ? W.num(v) : `<span class="${v >= 0 ? 'pos' : 'neg'}">${W.pctSigned(v)}</span>`;

  function aggregate(host, rows, metric) {
    const { byStrat, champs } = champions(rows, metric);
    const aggRows = Object.keys(byStrat).map(s => {
      const g = byStrat[s], ch = champs[s];
      return {
        strategy: s, runs: g.length, champion: ch ? ch.run : '-',
        champ_net: ch ? ch.net : null, champ_sharpe: ch ? ch.sharpe : null,
        champ_max_dd: ch ? ch.max_dd : null,
        best_sharpe: Math.max(...g.map(r => r.sharpe ?? -Infinity)),
        median_sharpe: median(g.map(r => r.sharpe)),
        _sort: ch ? ch[metric] : null
      };
    }).sort((a, b) => (b._sort ?? -1e9) - (a._sort ?? -1e9));

    // best value per numeric column (to highlight)
    const colMax = {};
    ['champ_net', 'champ_sharpe', 'champ_max_dd', 'best_sharpe'].forEach(k =>
      colMax[k] = Math.max(...aggRows.map(r => r[k] ?? -Infinity)));
    const hl = (r, k, kind) => {
      const inner = numCell(r[k], kind);
      return (r[k] != null && r[k] === colMax[k]) ? `<span class="cell-hl">${inner}</span>` : inner;
    };

    const cols = [
      { key: 'strategy', label: 'Strategy', html: r => `<b>${r.strategy}</b>` },
      { key: 'runs', label: 'Runs', num: true },
      { key: 'champion', label: 'Champion', html: r => `<span class="mono">${r.champion}</span>` },
      { key: 'champ_net', label: 'Net', num: true, html: r => hl(r, 'champ_net'), sortVal: r => r.champ_net ?? -1e9 },
      { key: 'champ_sharpe', label: 'Sharpe', num: true, html: r => hl(r, 'champ_sharpe', 'sharpe'), sortVal: r => r.champ_sharpe ?? -1e9 },
      { key: 'champ_max_dd', label: 'Max DD', num: true, html: r => hl(r, 'champ_max_dd'), sortVal: r => r.champ_max_dd ?? -1e9 },
      { key: 'best_sharpe', label: 'Best Sharpe', num: true, html: r => hl(r, 'best_sharpe', 'sharpe'), sortVal: r => r.best_sharpe ?? -1e9 },
      { key: 'median_sharpe', label: 'Median Sharpe', num: true, html: r => W.num(r.median_sharpe), sortVal: r => r.median_sharpe ?? -1e9 },
    ];
    const sortKey = { net: 'champ_net', sharpe: 'champ_sharpe', max_dd: 'champ_max_dd' }[metric] || 'best_sharpe';
    host.append(W.card(null, sortableTable(cols, aggRows, { initialSort: { key: sortKey, dir: 'desc' } })));

    // champion ranking bar (>= 2 strategies)
    const champList = Object.entries(champs);
    if (champList.length >= 2) {
      const [label, isPct] = METRICS[metric];
      const sorted = champList
        .map(([s, ch]) => ({ s, v: isPct ? +(ch[metric] * 100).toFixed(2) : +ch[metric].toFixed(2) }))
        .sort((a, b) => a.v - b.v); // ascending -> biggest on top in hbar
      const cc = W.chartCard('Champion ' + label + ' by strategy', 'tall');
      host.append(cc.card);
      Ch.hbar(cc.box, { cats: sorted.map(d => d.s), data: sorted.map(d => d.v), suffix: isPct ? '%' : '' });
    } else {
      host.append(el('div', { class: 'note', style: 'margin-top:12px;' },
        'Only one strategy so far - the champion ranking and head-to-head come alive once you add another strategy under strategies/ and run it.'));
    }
    return champs;
  }

  async function compareChampions(host, champs) {
    const entries = Object.entries(champs); // [stratName, row]
    if (!entries.length) return;
    host.append(el('div', { class: 'section-title' }, 'Compare strategy champions'));
    const sel = new Set(entries.map(([s]) => s));
    const labels = entries.map(([s, ch]) => `${s} - ${ch.run}`);
    const chips = W.multiChips(labels, new Set(labels), () => { });
    chips.querySelectorAll('.chip').forEach((c, i) => c.addEventListener('click', () => {
      const s = entries[i][0]; if (sel.has(s)) sel.delete(s); else sel.add(s); draw();
    }));
    const body = el('div');
    host.append(chips, body);

    async function draw() {
      body.innerHTML = '';
      const chosen = entries.filter(([s]) => sel.has(s)).map(([, ch]) => ch);
      if (!chosen.length) return;
      const details = await Promise.all(chosen.map(r => window.API.get('/api/run?path=' + encodeURIComponent(r.path))));

      const ROWS = ['total_return', 'cagr', 'sharpe', 'sortino', 'calmar', 'max_drawdown', 'profit_factor', 'win_rate', 'expectancy', 'exposure', 'round_trips'];
      const PCT = ['total_return', 'cagr', 'max_drawdown', 'win_rate', 'expectancy', 'exposure'];
      const mtable = el('table', { class: 'data' });
      const thead = el('tr', {}, el('th', {}, 'metric'));
      chosen.forEach(r => thead.append(el('th', { class: 'num' }, r.strategy + (r.kind === 'wfo' ? ' (OOS)' : ''))));
      mtable.append(el('thead', {}, thead));
      const tb = el('tbody');
      ROWS.forEach(k => {
        const tr = el('tr', {}, el('td', {}, k));
        details.forEach(d => {
          const m = d.kind === 'wfo' ? (d.result || {}).oos || {} : (d.metrics || {});
          const v = m[k];
          tr.append(el('td', { class: 'num mono' }, v == null ? '-' : PCT.includes(k) ? W.pct(v) : W.num(v)));
        });
        tb.append(tr);
      });
      mtable.append(tb);
      body.append(W.card('Metrics', el('div', { class: 'tbl-wrap' }, mtable)));

      const bt = chosen.filter(r => r.kind !== 'wfo');
      if (bt.length) {
        const eqs = await Promise.all(bt.map(r => window.API.get('/api/run/equity?path=' + encodeURIComponent(r.path))));
        const cc = W.chartCard('Equity curves (% return from start)', 'tall');
        body.append(cc.card);
        Ch.multiLine(cc.box, {
          x: eqs[0].dates, yFormatter: v => v.toFixed(0) + '%',
          series: bt.map((r, i) => ({ name: r.strategy + ' / ' + r.run, color: Ch.PALETTE[i], data: eqs[i].pct }))
        });
      }
    }
    draw();
  }

  window.PAGES = window.PAGES || {};
  window.PAGES.strategies = {
    id: 'strategies',
    async render(main) {
      main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Strategies')));
      const loading = W.loading('Loading strategies...');
      main.append(loading);
      const metas = await window.API.get('/api/runs');
      loading.remove();
      const rows = window.runRows(metas);
      if (!rows.length) { main.append(W.flag('off', 'No runs yet. Run a backtest or walk-forward optimization in the Analyzer.')); return; }

      const state = { metric: 'sharpe' };
      const bar = el('div', { class: 'toolbar', style: 'margin-bottom:10px;' });
      const caption = el('div', { class: 'crumbs', style: 'margin-bottom:14px;' });
      const body = el('div');
      main.append(bar, caption, body);

      function redraw() {
        bar.innerHTML = '';
        bar.append(W.select('Champion metric', Object.entries(METRICS).map(([k, v]) => [k, v[0]]),
          state.metric, v => { state.metric = v; redraw(); }));
        const nStrat = new Set(rows.map(r => r.strategy)).size;
        caption.textContent = `${nStrat} strateg${nStrat === 1 ? 'y' : 'ies'} - ${rows.length} total runs - champion = best ${METRICS[state.metric][0]} run of each`;
        body.innerHTML = '';
        const champs = aggregate(body, rows, state.metric);
        compareChampions(body, champs);
      }
      redraw();
    }
  };
})();
