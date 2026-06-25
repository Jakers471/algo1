/* Runs page - run-vs-run, scoped to ONE strategy. Leaderboard, ranking, risk/reward
   scatter, and side-by-side compare (metrics + equity overlay + parameter diff). */
(function () {
  const { el, sortableTable } = window.UI;
  const W = window.W, Ch = window.Charts;

  // headline metric columns are FRACTIONS; net/cagr/dd/win shown as %, sharpe raw.
  const METRICS = { net: 'Net return', cagr: 'CAGR', sharpe: 'Sharpe', max_dd: 'Max drawdown', win: 'Win rate' };

  // meta -> flat row (shared with the Strategies page via window.runRows)
  window.runRows = function (metas) {
    return metas.map(m => {
      const h = m.headline || {};
      const wfo = m.kind === 'wfo';
      const g = k => wfo ? h['oos_' + k] : h[k];
      return {
        run: m.name, strategy: m.strategy, type: m.backtest_type || 'Backtest',
        date: m.date || (m.timestamp || '').slice(0, 10),
        net: g('total_return'), cagr: g('cagr'), sharpe: g('sharpe'),
        max_dd: g('max_drawdown'), win: g('win_rate'),
        kind: m.kind || 'backtest', path: m.path, basis: wfo ? 'OOS' : 'full'
      };
    });
  };

  const cell = (v, kind) => v == null ? '<span class="dim">-</span>'
    : kind === 'sharpe' ? W.num(v) : `<span class="${v >= 0 ? 'pos' : 'neg'}">${W.pctSigned(v)}</span>`;

  function leaderboard(rows, onClick) {
    const cols = [
      { key: 'run', label: 'Run', html: r => `<b>${r.run}</b>` },
      { key: 'type', label: 'Type', html: r => `<span class="pill">${r.type}</span>` },
      { key: 'basis', label: 'Basis' },
      { key: 'date', label: 'Date' },
      { key: 'net', label: 'Net', num: true, html: r => cell(r.net), sortVal: r => r.net ?? -1e9 },
      { key: 'cagr', label: 'CAGR', num: true, html: r => cell(r.cagr), sortVal: r => r.cagr ?? -1e9 },
      { key: 'sharpe', label: 'Sharpe', num: true, html: r => cell(r.sharpe, 'sharpe'), sortVal: r => r.sharpe ?? -1e9 },
      { key: 'max_dd', label: 'Max DD', num: true, html: r => cell(r.max_dd), sortVal: r => r.max_dd ?? -1e9 },
      { key: 'win', label: 'Win', num: true, html: r => r.win == null ? '-' : W.pctRaw(r.win * 100, 0), sortVal: r => r.win ?? -1 },
    ];
    return sortableTable(cols, rows, { rowClick: onClick, initialSort: { key: 'sharpe', dir: 'desc' }, maxHeight: '460px' });
  }

  function cards(rows) {
    const best = (k, fmt) => {
      const v = rows.filter(r => r[k] != null).sort((a, b) => b[k] - a[k])[0];
      return v ? { val: fmt(v[k]), sub: v.run } : { val: '-', sub: '' };
    };
    const defs = [
      ['Best net return', best('net', W.pctSigned)], ['Best Sharpe', best('sharpe', W.num)],
      ['Smallest drawdown', best('max_dd', W.pctSigned)], ['Best CAGR', best('cagr', W.pctSigned)],
    ];
    const grid = el('div', { class: 'grid cols-4' });
    defs.forEach(([label, b]) => grid.append(el('div', { class: 'card kpi' },
      el('div', { class: 'k-label' }, label), el('div', { class: 'k-value' }, b.val),
      el('div', { class: 'k-sub' }, b.sub))));
    return grid;
  }

  async function compare(host, rows) {
    const sel = new Set(rows.slice(0, 2).map(r => r.path));
    const body = el('div');
    const chips = W.multiChips(rows.map(r => r.run), new Set(rows.slice(0, 2).map(r => r.run)), () => { });
    // map run-name chips to a redraw
    chips.querySelectorAll('.chip').forEach((c, i) => c.addEventListener('click', () => {
      const r = rows[i]; if (sel.has(r.path)) sel.delete(r.path); else sel.add(r.path); draw();
    }));
    host.append(el('div', { class: 'section-title' }, 'Compare runs side by side'), chips, body);

    async function draw() {
      body.innerHTML = '';
      const chosen = rows.filter(r => sel.has(r.path));
      if (!chosen.length) return;
      const details = await Promise.all(chosen.map(r => window.API.get('/api/run?path=' + encodeURIComponent(r.path))));

      // metrics matrix
      const ROWS = ['total_return', 'cagr', 'sharpe', 'sortino', 'calmar', 'max_drawdown', 'profit_factor', 'win_rate', 'expectancy', 'exposure', 'round_trips'];
      const mtable = el('table', { class: 'data' });
      const thead = el('tr', {}, el('th', {}, 'metric'));
      chosen.forEach(r => thead.append(el('th', { class: 'num' }, r.run + (r.kind === 'wfo' ? ' (OOS)' : ''))));
      mtable.append(el('thead', {}, thead));
      const tb = el('tbody');
      ROWS.forEach(k => {
        const tr = el('tr', {}, el('td', {}, k));
        details.forEach(d => {
          const m = d.kind === 'wfo' ? (d.result || {}).oos || {} : (d.metrics || {});
          const v = m[k];
          const isPct = ['total_return', 'cagr', 'max_drawdown', 'win_rate', 'expectancy', 'exposure'].includes(k);
          tr.append(el('td', { class: 'num mono' }, v == null ? '-' : isPct ? W.pct(v) : W.num(v)));
        });
        tb.append(tr);
      });
      mtable.append(tb);
      body.append(W.card('Metrics', el('div', { class: 'tbl-wrap' }, mtable)));

      // equity overlay (backtests only)
      const bt = chosen.filter(r => r.kind !== 'wfo');
      if (bt.length) {
        const eqs = await Promise.all(bt.map(r => window.API.get('/api/run/equity?path=' + encodeURIComponent(r.path))));
        const cc = W.chartCard('Equity curves (% return from start)', 'tall');
        body.append(cc.card);
        const base = eqs[0].dates;
        Ch.multiLine(cc.box, { x: base, yFormatter: v => v.toFixed(0) + '%',
          series: bt.map((r, i) => ({ name: r.run, color: Ch.PALETTE[i], data: eqs[i].pct })) });
      }

      // parameter diff
      const cfgs = {}; chosen.forEach((r, i) => cfgs[r.run] = details[i].config);
      const keys = [...new Set(chosen.flatMap(r => Object.keys(cfgs[r.run])))];
      const diffKeys = keys.filter(k => new Set(chosen.map(r => JSON.stringify(cfgs[r.run][k] ?? null))).size > 1);
      const ptable = el('table', { class: 'data' });
      const ph = el('tr', {}, el('th', {}, 'param'));
      chosen.forEach(r => ph.append(el('th', {}, r.run)));
      ptable.append(el('thead', {}, ph));
      const ptb = el('tbody');
      diffKeys.forEach(k => {
        const tr = el('tr', {}, el('td', {}, k));
        chosen.forEach(r => {
          let v = cfgs[r.run][k];
          v = v == null ? '-' : Array.isArray(v) ? v.join(', ') : String(v);
          tr.append(el('td', { class: 'cell-hl mono' }, v));
        });
        ptb.append(tr);
      });
      ptable.append(ptb);
      body.append(W.card('Parameters that differ (' + diffKeys.length + ' of ' + keys.length + ')',
        diffKeys.length ? el('div', { class: 'tbl-wrap' }, ptable)
          : el('div', { class: 'note' }, 'All parameters identical across the selected runs.')));
    }
    draw();
  }

  window.PAGES = window.PAGES || {};
  window.PAGES.runs = {
    id: 'runs',
    async render(main) {
      main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Runs')));
      const loading = W.loading('Loading runs...');
      main.append(loading);
      const metas = await window.API.get('/api/runs');
      loading.remove();
      const all = window.runRows(metas);
      if (!all.length) { main.append(W.flag('off', 'No runs yet. Run a backtest or walk-forward optimization in the Analyzer.')); return; }

      const strategies = [...new Set(all.map(r => r.strategy))];
      const state = { strategy: strategies[0], types: new Set(), sort: 'sharpe', asc: false };
      const body = el('div');
      const bar = el('div', { class: 'toolbar', style: 'margin-bottom:14px;' });
      main.append(bar, body);

      function redraw() {
        let rows = all.filter(r => r.strategy === state.strategy);
        const types = [...new Set(rows.map(r => r.type))];
        if (!state.types.size) types.forEach(t => state.types.add(t));
        rows = rows.filter(r => state.types.has(r.type));
        rows.sort((a, b) => ((a[state.sort] ?? -1e9) - (b[state.sort] ?? -1e9)) * (state.asc ? 1 : -1));

        bar.innerHTML = '';
        bar.append(
          W.select('Strategy', strategies, state.strategy, v => { state.strategy = v; state.types.clear(); redraw(); }),
          W.field('Type', W.multiChips(types, state.types, () => redraw())),
          W.select('Sort by', Object.entries(METRICS).map(([k, v]) => [k, v]), state.sort, v => { state.sort = v; redraw(); }),
          W.select('Order', [['false', 'Best to worst'], ['true', 'Worst to best']], String(state.asc), v => { state.asc = v === 'true'; redraw(); }));

        body.innerHTML = '';
        body.append(cards(rows));
        body.append(el('div', { class: 'section-title' }, `${state.strategy} - ${rows.length} runs`));
        body.append(W.card(null, leaderboard(rows, r => {
          sessionStorage.setItem('report_run', r.path);
          location.hash = 'report';
        })));

        const g = el('div', { class: 'grid cols-2', style: 'margin-top:14px;' });
        const rank = W.chartCard('Ranked by ' + METRICS[state.sort], 'tall');
        const rr = W.chartCard('Risk / reward map', 'tall');
        g.append(rank.card, rr.card);
        body.append(g);
        const rd = rows.filter(r => r[state.sort] != null);
        Ch.barAvg(rank.box, { cats: rd.map(r => r.run), data: rd.map(r => +( (state.sort === 'sharpe' ? r[state.sort] : r[state.sort] * 100).toFixed(2))) });
        const sc = rows.filter(r => r.max_dd != null && r.net != null);
        Ch.scatter(rr.box, { xName: 'Max drawdown %', yName: 'Net return %',
          points: sc.map(r => ({ x: +(-r.max_dd * 100).toFixed(1), y: +(r.net * 100).toFixed(1), name: r.run, color: r.kind === 'wfo' ? Ch.C.amber : Ch.C.accent2, size: 13 })),
          xFmt: v => v + '%', yFmt: v => v + '%' });

        compare(body, rows);
      }
      redraw();
    }
  };
})();
