/* App shell: API helper, sidebar nav, hash router. Pages register into window.PAGES
   (one file per page) and expose render(main). No framework, no build step. */
(function () {
  const { el } = window.UI;

  // ---- API helpers ----
  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    return r.json();
  }
  const get = (p) => api(p);
  const post = (p, body) => api(p, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  window.API = { get, post, raw: api };

  // ---- nav ----
  const NAV = [
    { id: 'analyzer', label: 'Analyzer', sub: 'Run & optimize' },
    { id: 'strategies', label: 'Strategies', sub: 'Compare strategies' },
    { id: 'runs', label: 'Runs', sub: 'Browse & compare runs' },
  ];

  function renderSidebar(active) {
    const side = document.getElementById('side');
    side.innerHTML = '';
    side.append(el('div', { class: 'brand' },
      el('div', { class: 'logo' }, 'A'),
      el('div', {},
        el('div', { class: 'title' }, 'algoproj'),
        el('div', { class: 'sub' }, 'Quant Analyzer'))));
    const group = el('div', { class: 'nav-group' });
    group.append(el('div', { class: 'label' }, 'Workspace'));
    const nav = el('div', { class: 'nav' });
    NAV.forEach(n => {
      const a = el('a', { href: '#' + n.id, class: n.id === active ? 'active' : '' },
        el('span', {}, n.label));
      nav.append(a);
    });
    group.append(nav);
    side.append(group);
    const foot = el('div', { class: 'nav-group', style: 'margin-top:auto;padding-top:20px;' });
    foot.append(el('div', { class: 'note', style: 'margin:0 8px;' },
      'Reuses the algokit engine + run registry. Backtests run on 15m bars (1d HTF gate).'));
    side.append(foot);
  }

  function route() {
    const id = (location.hash.replace('#', '') || 'runs');
    const page = window.PAGES[id] || window.PAGES.runs;
    renderSidebar(page.id);
    document.getElementById('topbar').innerHTML = '';
    const main = document.getElementById('main');
    main.innerHTML = '';
    if (window.Charts) window.Charts.disposeAll();
    Promise.resolve(page.render(main, { topbar: document.getElementById('topbar') }))
      .catch(err => { main.innerHTML = ''; main.append(el('div', { class: 'note' }, 'Error: ' + err.message)); });
  }

  window.addEventListener('hashchange', route);
  window.addEventListener('DOMContentLoaded', route);
  if (document.readyState !== 'loading') route();
})();
