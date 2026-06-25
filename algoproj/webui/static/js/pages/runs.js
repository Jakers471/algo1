/* Runs page - the registry, scoped to ONE strategy, with the three test KINDS kept
   strictly separate: Backtests | Walk-Forward | Anchored. Each sub-tab is fully
   self-contained (own ranking, leaderboard, risk/reward, compare) - kinds are NEVER mixed
   in a ranked view. The one place all kinds appear together is the chronological
   "Sequence of tests" strip (the research journey, not a comparison). */
(function () {
  const { el, sortableTable } = window.UI;
  const W = window.W, Ch = window.Charts;
  const enc = encodeURIComponent;

  // ranked-by metric keys (runRows already maps OOS values into these for wfo/anchored)
  const METRICS = { net: 'Net return', cagr: 'CAGR', sharpe: 'Sharpe', max_dd: 'Max drawdown', win: 'Win rate' };
  const KIND_TABS = [['Backtests', 'backtest'], ['Walk-Forward', 'wfo'], ['Anchored', 'anchored']];
  const labelOf = kind => (KIND_TABS.find(t => t[1] === kind) || ['Backtests'])[0];
  const kindOf = label => (KIND_TABS.find(t => t[0] === label) || ['', 'backtest'])[1];

  // meta -> flat row (shared with the Strategies page via window.runRows)
  window.runRows = function (metas) {
    return metas.map(m => {
      const h = m.headline || {};
      const oos = (m.kind === 'wfo' || m.kind === 'anchored');
      const g = k => oos ? h['oos_' + k] : h[k];
      return {
        run: m.name, strategy: m.strategy, type: m.backtest_type || 'Backtest',
        date: m.date || (m.timestamp || '').slice(0, 10),
        net: g('total_return'), cagr: g('cagr'), sharpe: g('sharpe'),
        max_dd: g('max_drawdown'), win: g('win_rate'),
        kind: m.kind || 'backtest', path: m.path, basis: oos ? 'OOS' : 'full'
      };
    });
  };

  // copy a run's exact config to the clipboard (global so it can live in an inline onclick)
  window.__copyRunConfig = async function (btn, path) {
    try {
      const d = await window.API.get('/api/run?path=' + enc(path));
      await navigator.clipboard.writeText(JSON.stringify(d.config, null, 2));
      const old = btn.textContent; btn.textContent = 'copied'; setTimeout(() => { btn.textContent = old; }, 1200);
    } catch (e) { btn.textContent = 'failed'; }
  };

  function navTo(r) {
    if (r.kind === 'backtest') { sessionStorage.setItem('perf_run', r.path); location.hash = 'performance'; }
    else { sessionStorage.setItem('wfo_run', r.path); location.hash = 'wforesult'; }
  }

  const cell = (v, kind) => v == null ? '<span class="dim">-</span>'
    : kind === 'sharpe' ? `<span class="${v >= 0 ? 'pos' : 'neg'}">${W.num(v)}</span>`
      : `<span class="${v >= 0 ? 'pos' : 'neg'}">${W.pctSigned(v)}</span>`;
  const copyBtn = r => `<button class="btn ghost" style="padding:2px 8px;font-size:11px" `
    + `onclick="event.stopPropagation();window.__copyRunConfig(this,'${r.path}')">copy cfg</button>`;
  const winCell = r => r.win == null ? '-' : W.pctRaw(r.win * 100, 0);

  function leaderboard(rows, kind, metaByPath) {
    const base = [
      { key: 'run', label: 'Run', html: r => `<b>${r.run}</b>` },
      { key: '_copy', label: '', sortable: false, html: copyBtn },
      { key: 'date', label: 'Date' },
    ];
    let cols;
    if (kind === 'backtest') {
      cols = base.concat([
        { key: 'net', label: 'Net', num: true, html: r => cell(r.net), sortVal: r => r.net ?? -1e9 },
        { key: 'cagr', label: 'CAGR', num: true, html: r => cell(r.cagr), sortVal: r => r.cagr ?? -1e9 },
        { key: 'sharpe', label: 'Sharpe', num: true, html: r => cell(r.sharpe, 'sharpe'), sortVal: r => r.sharpe ?? -1e9 },
        { key: 'max_dd', label: 'Max DD', num: true, html: r => cell(r.max_dd), sortVal: r => r.max_dd ?? -1e9 },
        { key: 'win', label: 'Win', num: true, html: winCell, sortVal: r => r.win ?? -1 },
      ]);
    } else {
      const mw = r => (metaByPath[r.path] || {});
      cols = base.concat([
        { key: 'net', label: 'OOS Net', num: true, html: r => cell(r.net), sortVal: r => r.net ?? -1e9 },
        { key: 'sharpe', label: 'OOS Sharpe', num: true, html: r => cell(r.sharpe, 'sharpe'), sortVal: r => r.sharpe ?? -1e9 },
        { key: 'win', label: 'OOS Win', num: true, html: winCell, sortVal: r => r.win ?? -1 },
        { key: 'max_dd', label: 'OOS Max DD', num: true, html: r => cell(r.max_dd), sortVal: r => r.max_dd ?? -1e9 },
        { key: 'windows', label: 'Windows', num: true, html: r => String(mw(r).n_windows ?? '-'), sortVal: r => mw(r).n_windows ?? 0 },
        { key: 'configs', label: 'Configs', num: true, html: r => String(mw(r).n_configs ?? '-'), sortVal: r => mw(r).n_configs ?? 0 },
      ]);
    }
    return sortableTable(cols, rows, { rowClick: navTo, initialSort: { key: 'sharpe', dir: 'desc' }, maxHeight: '460px' });
  }

  function sequence(host, stratRows) {
    if (!stratRows.length) return;
    const sorted = [...stratRows].sort((a, b) => (a.date || '').localeCompare(b.date || '') || a.run.localeCompare(b.run));
    const strip = el('div', { style: 'display:flex;gap:8px;flex-wrap:wrap;' });
    sorted.forEach(r => {
      const c = el('div', { class: 'card', style: 'padding:8px 12px;min-width:128px;cursor:pointer;' },
        el('div', {}, el('span', { class: 'pill' }, r.type)),
        el('div', { class: 'mono', style: 'font-weight:700;margin-top:4px;' }, r.run),
        el('div', { class: 'dim', style: 'font-size:11px;' }, r.date),
        el('div', { class: (r.net >= 0 ? 'pos' : 'neg') + ' mono', style: 'font-size:12px;' },
          (r.basis === 'OOS' ? 'OOS ' : '') + (r.net == null ? '-' : W.pctSigned(r.net))));
      c.addEventListener('click', () => navTo(r));
      strip.append(c);
    });
    host.append(el('div', { class: 'section-title' }, 'Sequence of tests on ' + stratRows[0].strategy
      + ' (' + sorted.length + ', oldest first)'), strip);
  }

  async function compare(host, rows, kind) {
    if (!rows.length) return;
    const sel = new Set(rows.slice(0, 2).map(r => r.path));
    const body = el('div');
    const chips = W.multiChips(rows.map(r => r.run), new Set(rows.slice(0, 2).map(r => r.run)), () => { });
    chips.querySelectorAll('.chip').forEach((c, i) => c.addEventListener('click', () => {
      const r = rows[i]; if (sel.has(r.path)) sel.delete(r.path); else sel.add(r.path); draw();
    }));
    host.append(el('div', { class: 'section-title' }, 'Compare ' + labelOf(kind) + ' runs'), chips, body);

    async function draw() {
      body.innerHTML = '';
      const chosen = rows.filter(r => sel.has(r.path));
      if (!chosen.length) return;
      const details = await Promise.all(chosen.map(r => window.API.get('/api/run?path=' + enc(r.path))));

      const ROWS = ['total_return', 'cagr', 'sharpe', 'sortino', 'calmar', 'max_drawdown', 'profit_factor', 'win_rate', 'expectancy', 'exposure', 'round_trips'];
      const PCT = ['total_return', 'cagr', 'max_drawdown', 'win_rate', 'expectancy', 'exposure'];
      const mtable = el('table', { class: 'data' });
      const thead = el('tr', {}, el('th', {}, 'metric'));
      chosen.forEach(r => thead.append(el('th', { class: 'num' }, r.run + (kind !== 'backtest' ? ' (OOS)' : ''))));
      mtable.append(el('thead', {}, thead));
      const tb = el('tbody');
      ROWS.forEach(k => {
        const tr = el('tr', {}, el('td', {}, k));
        chosen.forEach((r, i) => {
          const d = details[i];
          // FIX: use the ROW's kind, not d.kind (which is undefined on the /api/run payload)
          const m = r.kind === 'backtest' ? (d.metrics || {}) : ((d.result || {}).oos || {});
          const v = m[k];
          tr.append(el('td', { class: 'num mono' }, v == null ? '-' : PCT.includes(k) ? W.pct(v) : W.num(v)));
        });
        tb.append(tr);
      });
      mtable.append(tb);
      body.append(W.card('Metrics', el('div', { class: 'tbl-wrap' }, mtable)));

      if (kind === 'backtest') {
        const eqs = await Promise.all(chosen.map(r => window.API.get('/api/run/equity?path=' + enc(r.path))));
        const cc = W.chartCard('Equity curves (% return from start)', 'tall');
        body.append(cc.card);
        Ch.multiLine(cc.box, { x: eqs[0].dates, yFormatter: v => v.toFixed(0) + '%',
          series: chosen.map((r, i) => ({ name: r.run, color: Ch.PALETTE[i], data: eqs[i].pct })) });
      }

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
          let v = cfgs[r.run][k]; v = v == null ? '-' : Array.isArray(v) ? v.join(', ') : String(v);
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
      const metaByPath = {}; metas.forEach(m => metaByPath[m.path] = m);
      const strategies = [...new Set(all.map(r => r.strategy))];
      const state = { strategy: strategies[0], kind: 'backtest', sort: 'sharpe', asc: false };

      const topbar = el('div', { class: 'toolbar', style: 'margin-bottom:14px;' });
      const seqHost = el('div', { style: 'margin-bottom:18px;' });
      const tabBar = el('div');
      const tabBody = el('div');
      main.append(topbar, seqHost, tabBar, tabBody);

      function drawTab() {
        tabBody.innerHTML = '';
        const kind = state.kind;
        const rows = all.filter(r => r.strategy === state.strategy && r.kind === kind);
        const ctrl = el('div', { class: 'toolbar', style: 'margin:12px 0;' });
        ctrl.append(
          W.select('Ranked by', Object.entries(METRICS), state.sort, v => { state.sort = v; drawTab(); }),
          W.select('Order', [['false', 'Best to worst'], ['true', 'Worst to best']], String(state.asc),
            v => { state.asc = v === 'true'; drawTab(); }));
        tabBody.append(ctrl);
        if (!rows.length) { tabBody.append(W.flag('off', 'No ' + labelOf(kind) + ' runs for ' + state.strategy + ' yet.')); return; }
        const sorted = [...rows].sort((a, b) => ((a[state.sort] ?? -1e9) - (b[state.sort] ?? -1e9)) * (state.asc ? 1 : -1));
        tabBody.append(el('div', { class: 'section-title' }, `${labelOf(kind)} - ${rows.length} runs`));
        tabBody.append(W.card(null, leaderboard(sorted, kind, metaByPath)));

        const g = el('div', { class: 'grid cols-2', style: 'margin-top:14px;' });
        const rank = W.chartCard('Ranked by ' + METRICS[state.sort], 'tall');
        const rr = W.chartCard('Risk / reward map' + (kind !== 'backtest' ? ' (out-of-sample)' : ''), 'tall');
        g.append(rank.card, rr.card);
        tabBody.append(g);
        const rd = sorted.filter(r => r[state.sort] != null);
        Ch.barAvg(rank.box, { cats: rd.map(r => r.run), data: rd.map(r => +((state.sort === 'sharpe' ? r[state.sort] : r[state.sort] * 100).toFixed(2))) });
        const sc = rows.filter(r => r.max_dd != null && r.net != null);
        Ch.scatter(rr.box, { xName: 'Max drawdown %', yName: (kind === 'backtest' ? 'Net' : 'OOS net') + ' return %',
          points: sc.map(r => ({ x: +(-r.max_dd * 100).toFixed(1), y: +(r.net * 100).toFixed(1), name: r.run, color: Ch.C.accent2, size: 13 })),
          xFmt: v => v + '%', yFmt: v => v + '%' });

        compare(tabBody, sorted, kind);
      }

      function drawAll() {
        const stratRows = all.filter(r => r.strategy === state.strategy);
        topbar.innerHTML = '';
        topbar.append(W.select('Strategy', strategies, state.strategy,
          v => { state.strategy = v; state.kind = 'backtest'; drawAll(); }));
        seqHost.innerHTML = '';
        sequence(seqHost, stratRows);
        tabBar.innerHTML = '';
        tabBar.append(W.tabs(KIND_TABS.map(t => t[0]), labelOf(state.kind),
          label => { state.kind = kindOf(label); state.sort = 'sharpe'; drawTab(); }));
        drawTab();
      }
      drawAll();
    }
  };
})();
