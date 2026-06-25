/* Shared widgets + formatters used by every page. window.W */
(function () {
  const { el } = window.UI;

  // ---- formatters (most metric values are FRACTIONS from the engine) ----
  const pct = (v, dp = 1) => v == null ? '-' : (v * 100).toFixed(dp) + '%';
  const pctSigned = (v, dp = 1) => v == null ? '-' : (v >= 0 ? '+' : '') + (v * 100).toFixed(dp) + '%';
  const pctRaw = (v, dp = 1) => v == null ? '-' : v.toFixed(dp) + '%';      // already in %
  const num = (v, dp = 2) => v == null ? '-' : Number(v).toFixed(dp);
  const money = (v) => v == null ? '-' : '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
  const int = (v) => v == null ? '-' : Math.round(v).toLocaleString();

  // ---- controls (return a .ctrl element) ----
  function field(label, input) {
    return el('div', { class: 'ctrl' }, label ? el('label', {}, label) : null, input);
  }
  function select(label, options, value, onChange) {
    const s = el('select');
    options.forEach(o => {
      const [val, txt] = Array.isArray(o) ? o : [o, o];
      const op = el('option', { value: val }, txt);
      if (String(val) === String(value)) op.selected = true;
      s.append(op);
    });
    s.addEventListener('change', () => onChange(s.value));
    return field(label, s);
  }
  function numInput(label, value, opts = {}) {
    const i = el('input', { type: 'number', value });
    if (opts.step != null) i.step = opts.step;
    if (opts.min != null) i.min = opts.min;
    if (opts.onChange) i.addEventListener('change', () => opts.onChange(i.value));
    return opts.bare ? i : field(label, i);
  }
  function textInput(label, value, onChange, placeholder) {
    const i = el('input', { type: 'text', value: value || '', placeholder: placeholder || '' });
    if (onChange) i.addEventListener('input', () => onChange(i.value));
    return field(label, i);
  }
  function dateInput(label, value, opts = {}) {
    const i = el('input', { type: 'date', value });
    if (opts.min) i.min = opts.min;
    if (opts.max) i.max = opts.max;
    if (opts.onChange) i.addEventListener('change', () => opts.onChange(i.value));
    return field(label, i);
  }
  function slider(label, { min, max, step, value, fmt, onChange }) {
    const valSpan = el('span', { class: 'range-val' }, fmt ? fmt(value) : value);
    const i = el('input', { type: 'range', min, max, step, value });
    i.addEventListener('input', () => {
      valSpan.textContent = fmt ? fmt(+i.value) : i.value;
      if (onChange) onChange(+i.value);
    });
    const head = el('div', { style: 'display:flex;justify-content:space-between;' },
      el('label', {}, label), valSpan);
    return el('div', { class: 'ctrl' }, head, i);
  }
  function multiChips(options, selected, onChange) {
    const wrap = el('div', { class: 'chips-multi' });
    options.forEach(o => {
      const chip = el('span', { class: 'chip' + (selected.has(o) ? ' active' : '') }, o);
      chip.addEventListener('click', () => {
        if (selected.has(o)) selected.delete(o); else selected.add(o);
        chip.classList.toggle('active');
        onChange([...selected]);
      });
      wrap.append(chip);
    });
    return wrap;
  }

  // ---- tabs ----
  function tabs(items, active, onChange) {
    const bar = el('div', { class: 'tabs' });
    items.forEach(it => {
      const t = el('div', { class: 'tab' + (it === active ? ' active' : '') }, it);
      t.addEventListener('click', () => onChange(it));
      bar.append(t);
    });
    return bar;
  }

  // ---- progress (green bar + ETA text) ----
  function progress(initialText) {
    const fill = el('div');
    const bar = el('div', { class: 'prog' }, fill);
    const label = el('div', { class: 'prog-label' }, initialText || '');
    const wrap = el('div', {}, bar, label);
    return {
      el: wrap,
      set(frac, text) { fill.style.width = Math.round(frac * 100) + '%'; if (text != null) label.textContent = text; },
      remove() { wrap.remove(); }
    };
  }

  // ---- flag (colored read-out box) ----
  function flag(kind, html) {
    return el('div', { class: 'flag ' + kind, html: html });
  }

  // ---- card ----
  function card(title, body, hint) {
    const head = title ? el('div', { class: 'card-head' },
      el('h3', {}, title), hint ? el('span', { class: 'hint' }, hint) : null) : null;
    return el('div', { class: 'card' }, head, body);
  }
  function chartCard(title, heightClass, hint) {
    const box = el('div', { class: 'chart ' + (heightClass || '') });
    const c = card(title, box, hint);
    return { card: c, box };
  }
  const loading = (msg) => el('div', { class: 'loading' },
    el('div', { class: 'spinner' }), el('div', {}, msg || 'Loading...'));

  window.W = {
    pct, pctSigned, pctRaw, num, money, int,
    field, select, numInput, textInput, dateInput, slider, multiChips, tabs,
    progress, flag, card, chartCard, loading
  };
})();
