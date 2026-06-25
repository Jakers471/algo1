/* Walk-forward / Anchored result page. Shows the page that pops up after a walk-forward run
   (and when opening a WF/Anchored run from the Runs tab) via window.renderWFO. Reads the run
   path from sessionStorage 'wfo_run', or accepts a fresh result via window.WFO_RESULT. */
(function () {
  const { el } = window.UI;
  const W = window.W;

  window.PAGES = window.PAGES || {};
  window.PAGES.wforesult = {
    id: 'wforesult',
    async render(main) {
      // a freshly-run result handed over in memory (skips a reload)
      if (window.WFO_RESULT) {
        const res = window.WFO_RESULT; window.WFO_RESULT = null;
        main.append(el('div', { class: 'page-head' }, el('h1', {}, 'Walk-forward result')));
        const host = el('div'); main.append(host);
        window.renderWFO(host, res);
        return;
      }
      const path = sessionStorage.getItem('wfo_run');
      const isAnchored = path && path.includes('/anchored/');
      main.append(el('div', { class: 'page-head' },
        el('h1', {}, (isAnchored ? 'Anchored' : 'Walk-forward') + ' result'),
        el('div', { class: 'crumbs', html: '<a href="#runs">Runs</a> / <b>' + (path ? path.split('/').pop() : '-') + '</b>' })));
      if (!path) { main.append(W.flag('off', 'No run selected. Open a Walk-Forward or Anchored run from the Runs tab.')); return; }
      const ld = W.loading('Loading result...'); main.append(ld);
      const run = await window.API.get('/api/run?path=' + encodeURIComponent(path));
      ld.remove();
      const m = run.meta;
      main.append(el('div', { class: 'note', style: 'margin-bottom:12px;',
        html: `<b>${m.name}</b> &nbsp;|&nbsp; <span class="pill">${m.backtest_type}</span> &nbsp;|&nbsp; ${m.strategy} &nbsp;|&nbsp; ${m.timestamp || m.date || ''}` }));
      const host = el('div'); main.append(host);
      window.renderWFO(host, window.normalizeWFO(run));
    }
  };
})();
