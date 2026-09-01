// ── Splash ────────────────────────────────────────────────────────────────
const _splashSteps = [
  [10,'Загрузка интерфейса…'],[30,'Подключение компонентов…'],
  [55,'Загрузка конфигурации…'],[75,'Инициализация модулей…'],[90,'Почти готово…'],
];
let _splashTimer = null;
function _splashProgress(pct, hint) {
  const fill = document.getElementById('splash-fill');
  const hintEl = document.getElementById('splash-hint');
  if (fill) fill.style.width = pct + '%';
  if (hintEl && hint) hintEl.textContent = hint;
}
function _startSplashAnim() {
  let i = 0;
  _splashTimer = setInterval(() => {
    if (i < _splashSteps.length) { _splashProgress(_splashSteps[i][0], _splashSteps[i][1]); i++; }
    else clearInterval(_splashTimer);
  }, 320);
}
function _hideSplash() {
  clearInterval(_splashTimer); _splashProgress(100, 'Готово!');
  setTimeout(() => {
    const s = document.getElementById('splash');
    if (s) s.classList.add('hidden');
    setTimeout(() => { if (s) s.remove(); }, 450);
  }, 350);
}
_startSplashAnim();

// ── State ─────────────────────────────────────────────────────────────────
const S = {
  page: 'promodate', stage: 'all',
  skuAllResults: [], skuSelected: new Set(), skuRefPath: '',
  skuAllNew: [], skuActiveTab: 'match', skuNewSelected: new Set(),
  skuMode: 'ml',
  pcLastOutput: '',
};

// ── Python event handler ──────────────────────────────────────────────────
window.__pyEvent = function(payload) {
  const { type, data } = payload;
  switch (type) {
    case 'log':           addLog(data); break;
    case 'progress':      updateProgress(data.done, data.total); break;
    case 'hide_progress': hideProgress(); break;
    case 'done':          hideProgress(); break;
    case 'set_title':     setStatus(data); break;
    case 'toast':         showToast(data.type, data.message); break;
    case 'sku_log':       skuLog(data); break;
    case 'sku_results':   skuRenderResults(data); break;
    case 'sku_all_new':   skuRenderAllNew(data); break;
    case 'sku_error':     skuLog('✗ Ошибка: ' + data); skuUnlock(); break;
    // ── Price comparison events ──
    case 'pc_started':    pcOnStarted(); break;
    case 'pc_log':        pcAddLog(data); break;
    case 'pc_done':       pcOnDone(data); break;
    case 'pc_error':      pcOnError(data); break;
    case 'scheduler_fired': schedUpdateStatus(new Date().toISOString().slice(0,19),'running'); break;
    case 'scheduler_done':  schedUpdateStatus(data.ts||'', data.status); break;
  }
};

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('pywebviewready', async () => {
  buildSelects();
  const cfg = await pywebview.api.get_config();
  applyConfig(cfg);
  applyThemeFromConfig(cfg);
  const cats = await pywebview.api.get_filter_options();
  const sel = document.getElementById('sel-category');
  sel.innerHTML = cats.map(c => `<option>${c}</option>`).join('');
  if (cfg.category) sel.value = cfg.category;
  const months = await pywebview.api.get_month_labels();
  const ms = document.getElementById('sel-prod-month');
  ms.innerHTML = months.map(m => `<option>${m}</option>`).join('');
  if (cfg.prod_month) ms.value = cfg.prod_month;
  // restore threshold display
  if (cfg.pc_threshold) {
    const sl = document.querySelector('[data-field="pc_threshold"]');
    if (sl) { sl.value = cfg.pc_threshold; document.getElementById('pc-thresh-val').textContent = parseFloat(cfg.pc_threshold).toFixed(2); }
  }
  const DATE_FIELDS = new Set(['month_from','month_to','year_from','year_to']);
  document.querySelectorAll('[data-field]').forEach(el => {
    if (DATE_FIELDS.has(el.dataset.field)) return;
    el.addEventListener('change', autoSave);
  });
  dlCalInit(cfg);
  syncPromoModeUI(cfg.promodata_mode || 'co');
  PAGE_PROFILES = (cfg.page_profiles && Object.keys(cfg.page_profiles).length) ? cfg.page_profiles : {};
  pageProfilesInitAll();
  navigate('promodate');
  schedLoad();
  _hideSplash();
  
});

function buildSelects() {
  const now = new Date();
  const months = Array.from({length:12},(_,i)=>i+1);
  const years  = Array.from({length:11},(_,i)=>2020+i);
  ['sel-month-from','sel-month-to'].forEach(id => {
    const s = document.getElementById(id);
    s.innerHTML = months.map(m=>`<option value="${m}">${m}</option>`).join('');
    s.value = now.getMonth()+1;
  });
  ['sel-year-from','sel-year-to'].forEach(id => {
    const s = document.getElementById(id);
    s.innerHTML = years.map(y=>`<option value="${y}">${y}</option>`).join('');
    s.value = now.getFullYear();
  });

  // Автосдвиг: FROM не может быть позже TO и наоборот
  function clampDates() {
    const mf = parseInt(document.getElementById('sel-month-from').value);
    const mt = parseInt(document.getElementById('sel-month-to').value);
    const yf = parseInt(document.getElementById('sel-year-from').value);
    const yt = parseInt(document.getElementById('sel-year-to').value);
    const from = yf * 12 + mf;
    const to   = yt * 12 + mt;
    return { mf, mt, yf, yt, from, to };
  }

  // Date pickers now handled by dlCalRender() / dlOnDayClick()
  document.getElementById('sel-month-to').addEventListener('change', function() {
    const { mf, mt, yf, yt, from, to } = clampDates();
    if (to < from) {
      document.getElementById('sel-month-from').value = mt;
      document.getElementById('sel-year-from').value  = yt;
    }
    autoSave();
  });
  document.getElementById('sel-year-to').addEventListener('change', function() {
    const { mf, mt, yf, yt, from, to } = clampDates();
    if (to < from) {
      document.getElementById('sel-month-from').value = mt;
      document.getElementById('sel-year-from').value  = yt;
    }
    autoSave();
  });
}

function applyConfig(cfg) {
  // Устанавливаем значения без триггера input-событий
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (cfg[key] !== undefined && cfg[key] !== null && cfg[key] !== '') {
      el.value = cfg[key];
    }
  });
  // Восстанавливаем пути SKU Matcher
  if (cfg.sku_ref_path) {
    document.getElementById('sku-ref-path').value = cfg.sku_ref_path;
    S.skuRefPath = cfg.sku_ref_path;
  }
  if (cfg.sku_csv_folder) {
    document.getElementById('sku-csv-folder').value = cfg.sku_csv_folder;
    pywebview.api.get_csv_count(cfg.sku_csv_folder).then(cnt => {
      if (cnt) document.getElementById('sku-csv-count').textContent = `${cnt} файлов CSV`;
    });
  }
  // Отчёт без OOS — Кетчуп
  const need2026Cb = document.getElementById('oos-ketchup-need-2026');
  if (need2026Cb) {
    need2026Cb.checked = cfg.oos_ketchup_need_2026 !== '';
    document.getElementById('oos-ketchup-2026-row').style.opacity = need2026Cb.checked ? '1' : '.4';
  }
  if (cfg.oos_ketchup_folder) {
    pywebview.api.scan_ketchup_folder(
      cfg.oos_ketchup_folder,
      cfg.oos_ketchup_report_2026 || '',
      cfg.oos_ketchup_report_2024_2026 || ''
    ).then(oosKetchupRenderScan);
  }
}

function autoSave() {
  pywebview.api.save_config(collectFormConfig());
  pageProfileSyncActive(S.page);
}

function collectFormConfig() {
  const cfg = {};
  document.querySelectorAll('[data-field]').forEach(el => { cfg[el.dataset.field] = el.value; });
  cfg.dark_theme = document.body.classList.contains('dark');
  return cfg;
}

// ── OOS Report ────────────────────────────────────────────────────────────
let _oosLastFile = '';
let _oosCategory = 'Майонез';

const OOS_REPORT_FIELDS = {
  sloboda:    'oos-report-sloboda',
  provansale: 'oos-report-provansale',
  olive:      'oos-report-olive',
};

function oosSetCategory(cat, btn) {
  document.querySelectorAll('#pane-oos .seg-btn[onclick*="oosSetCategory"]').forEach(b => b.classList.toggle('active', b===btn));
  _oosCategory = cat;
  const isKetchup = cat === 'Кетчуп';
  document.getElementById('oos-mayo-fields').style.display = isKetchup ? 'none' : '';
  document.getElementById('oos-ketchup-fields').style.display = isKetchup ? '' : 'none';
}

async function oosPickFile(inputId, fieldKey) {
  const path = await pywebview.api.browse_file();
  if (!path) return;
  document.getElementById(inputId).value = path;
  const cfg = collectFormConfig();
  cfg[fieldKey] = path;
  pywebview.api.save_config(cfg);
  pageProfileSyncActive(S.page);
  S[fieldKey] = path;
}

async function oosRunAll() {
  if (_oosCategory === 'Кетчуп') { await oosKetchupRunAll(); return; }
  const kub = document.getElementById('oos-kub-file').value.trim();
  const elt = document.getElementById('oos-elt-file').value.trim();
  if (!kub || !elt) { addLog('⚠️ Укажите КУБ-файл и ELT-файл'); return; }
  const tasks = [];
  for (const [type, fieldId] of Object.entries(OOS_REPORT_FIELDS)) {
    const rep = document.getElementById(fieldId).value.trim();
    if (rep) tasks.push({ report_type: type, report_file: rep });
    else addLog(`⚠️ Пропускаем «${type}» — файл отчёта не указан`);
  }
  if (!tasks.length) { addLog('⚠️ Нет ни одного файла отчёта'); return; }
  document.getElementById('oos-open-btn').style.display = 'none';
  await pywebview.api.run_oos_all({ kub_file: kub, elt_file: elt, tasks });
}

function oosOpenFolder() {
  if (_oosLastFile) pywebview.api.open_oos_folder(_oosLastFile);
}

// ── OOS Report — Кетчуп (обновление через query, папка с кубами) ──────────
async function oosKetchupPickFolder() {
  const path = await pywebview.api.browse_folder();
  if (!path) return;
  document.getElementById('oos-ketchup-folder').value = path;
  const cfg = collectFormConfig();
  cfg.oos_ketchup_folder = path;
  pywebview.api.save_config(cfg);
  pageProfileSyncActive(S.page);
  await oosKetchupRescan();
}

async function oosKetchupRescan() {
  const folder = document.getElementById('oos-ketchup-folder').value.trim();
  if (!folder) { oosKetchupRenderScan([]); return; }
  const report2026 = document.getElementById('oos-ketchup-report-2026').value.trim();
  const report20242026 = document.getElementById('oos-ketchup-report-2024-2026').value.trim();
  const scan = await pywebview.api.scan_ketchup_folder(folder, report2026, report20242026);
  oosKetchupRenderScan(scan);
}

function oosKetchupRenderScan(files) {
  const el = document.getElementById('oos-ketchup-scan');
  if (!el) return;
  files = files || [];
  if (!files.length) { el.innerHTML = ''; return; }
  el.innerHTML =
    `<div class="ketchup-scan-count">Найдено кубов: ${files.length}</div>` +
    `<ul class="ketchup-scan-list">` +
    files.map(name => `<li class="ketchup-scan-item">📄 <span>${name}</span></li>`).join('') +
    `</ul>`;
}

function oosKetchupSaveNeed2026() {
  const checked = document.getElementById('oos-ketchup-need-2026').checked;
  document.getElementById('oos-ketchup-2026-row').style.opacity = checked ? '1' : '.4';
  const cfg = collectFormConfig();
  cfg.oos_ketchup_need_2026 = checked ? '1' : '';
  pywebview.api.save_config(cfg);
  pageProfileSyncActive(S.page);
}

async function oosKetchupPickReportFile(inputId, fieldKey) {
  await oosPickFile(inputId, fieldKey);
  await oosKetchupRescan();
}

async function oosKetchupRunAll() {
  const folder = document.getElementById('oos-ketchup-folder').value.trim();
  if (!folder) { addLog('⚠️ Укажите папку с кубами'); return; }
  const need2026 = document.getElementById('oos-ketchup-need-2026').checked;
  const report2026 = document.getElementById('oos-ketchup-report-2026').value.trim();
  const report20242026 = document.getElementById('oos-ketchup-report-2024-2026').value.trim();
  if (need2026 && !report2026) addLog('⚠️ Файл отчёта 2026 не указан — этот шаг будет пропущен');
  if (!report20242026) addLog('⚠️ Файл отчёта 2024-2026 не указан — этот шаг будет пропущен');
  document.getElementById('oos-open-btn').style.display = 'none';
  await pywebview.api.run_oos_ketchup({
    kub_folder: folder,
    report_2026: report2026,
    report_2024_2026: report20242026,
    need_2026: need2026,
  });
}

window.__pyEvent = window.__pyEvent || function(){};
const __origEvent = window.__pyEvent;
window.__pyEvent = function(payload) {
  if (payload.type === 'oos_done') {
    _oosLastFile = payload.data.report_file || '';
    document.getElementById('oos-open-btn').style.display = _oosLastFile ? '' : 'none';
  }
  if (payload.type === 'query_refresh_done' && payload.data.page) {
    _refreshLastFile[payload.data.page] = payload.data.file || '';
    _refreshUpdateOpenBtn();
  }
  if (payload.type === 'market_share_brands_done') {
    _refreshLastFile['market_share_brands'] = payload.data.file || '';
    _refreshUpdateOpenBtn();
  }
  __origEvent(payload);
};

// ── Общий бар «Обновить квери» (дистрибуция / доли рынка) ─────────────────
let _refreshLastFile = {};
function _refreshUpdateOpenBtn() {
  const btn = document.getElementById('refresh-open-btn');
  if (!btn) return;
  const f = _refreshLastFile[S.page];
  btn.style.display = f ? '' : 'none';
}
function refreshOpenFile() {
  const f = _refreshLastFile[S.page];
  if (f) pywebview.api.open_file(f);
}

// ── Универсальная модалка вместо window.prompt()/confirm() ────────────────
let _appModalResolveFn = null;
let _appModalMode = 'prompt';

function _appModal({ title, message, defaultValue, placeholder, okLabel, danger }) {
  return new Promise(resolve => {
    _appModalResolveFn = resolve;
    _appModalMode = (defaultValue !== undefined) ? 'prompt' : 'confirm';
    document.getElementById('app-modal-title').textContent = title || '';
    const msgEl = document.getElementById('app-modal-message');
    const inputEl = document.getElementById('app-modal-input');
    if (_appModalMode === 'prompt') {
      msgEl.style.display = 'none';
      inputEl.style.display = '';
      inputEl.value = defaultValue || '';
      inputEl.placeholder = placeholder || '';
    } else {
      msgEl.style.display = '';
      msgEl.textContent = message || '';
      inputEl.style.display = 'none';
    }
    const okBtn = document.getElementById('app-modal-ok-btn');
    okBtn.textContent = okLabel || 'OK';
    okBtn.className = 'btn ' + (danger ? 'btn-danger' : 'btn-primary');
    document.getElementById('app-modal-overlay').style.display = 'flex';
    if (_appModalMode === 'prompt') setTimeout(() => { inputEl.focus(); inputEl.select(); }, 30);
  });
}
function _appModalResolve(value) {
  document.getElementById('app-modal-overlay').style.display = 'none';
  if (_appModalResolveFn) { const fn = _appModalResolveFn; _appModalResolveFn = null; fn(value); }
}
function _appModalSubmit() {
  _appModalResolve(_appModalMode === 'prompt' ? document.getElementById('app-modal-input').value : true);
}

// ── Page profiles («под-страницы» 1/2/3 с разными наборами данных) ────────
// Каждая вкладка может хранить несколько именованных наборов значений всех
// [data-field]/чекбоксов внутри своей #pane-<page>. Переключение наборов не
// стирает предыдущие — они остаются сохранёнными в cfg.page_profiles.
let PAGE_PROFILES = {};
const DEFAULT_PROFILE_NAME = 'Основной';

const PAGE_PROFILE_CUSTOM = {
  oos: {
    capture: () => ({ category: _oosCategory }),
    apply: (data) => {
      if (!data || !data.category) return;
      const btn = document.getElementById(data.category === 'Кетчуп' ? 'oos-cat-ketchup' : 'oos-cat-mayo');
      if (btn) oosSetCategory(data.category, btn);
    },
  },
};

function pageProfileCapture(page) {
  const scope = document.getElementById('pane-' + page);
  const out = {};
  if (scope) {
    scope.querySelectorAll('[data-field]').forEach(el => {
      out['df:' + el.dataset.field] = (el.type === 'checkbox') ? el.checked : el.value;
    });
    scope.querySelectorAll('input[type="checkbox"]:not([data-field])[id]').forEach(el => {
      out['id:' + el.id] = el.checked;
    });
  }
  const custom = PAGE_PROFILE_CUSTOM[page];
  if (custom && custom.capture) out.__custom = custom.capture();
  return out;
}

function pageProfileApply(page, snapshot) {
  const scope = document.getElementById('pane-' + page);
  snapshot = snapshot || {};
  if (scope) {
    // Всегда сбрасываем поля на значение из набора (или на пусто, если в
    // наборе его нет) — иначе при переключении на новый пустой набор
    // остались бы значения от предыдущего.
    scope.querySelectorAll('[data-field]').forEach(el => {
      const v = snapshot['df:' + el.dataset.field];
      if (el.type === 'checkbox') el.checked = !!v;
      else el.value = (v !== undefined && v !== null) ? v : '';
    });
    scope.querySelectorAll('input[type="checkbox"]:not([data-field])[id]').forEach(el => {
      el.checked = !!snapshot['id:' + el.id];
    });
  }
  const custom = PAGE_PROFILE_CUSTOM[page];
  if (custom && custom.apply) custom.apply(snapshot.__custom);
  pageProfilePostApply(page);
}

function pageProfilePostApply(page) {
  if (page === 'promodate') {
    syncPromoModeUI(getField('promodata_mode') || 'co');
    const thr = getField('pc_threshold');
    const lbl = document.getElementById('pc-thresh-val');
    if (thr && lbl) lbl.textContent = parseFloat(thr).toFixed(2);
  }
  if (page === 'oos' && typeof oosKetchupRescan === 'function') {
    const cb = document.getElementById('oos-ketchup-need-2026');
    const row = document.getElementById('oos-ketchup-2026-row');
    if (cb && row) row.style.opacity = cb.checked ? '1' : '.4';
    oosKetchupRescan();
  }
}

function pageProfileStore(page) {
  let store = PAGE_PROFILES[page];
  if (!store || !store.profiles || !Object.keys(store.profiles).length) {
    store = { active: DEFAULT_PROFILE_NAME, profiles: {} };
    store.profiles[DEFAULT_PROFILE_NAME] = pageProfileCapture(page);
    PAGE_PROFILES[page] = store;
  }
  if (!store.profiles[store.active]) store.active = Object.keys(store.profiles)[0];
  return store;
}

function pageProfilesPersist() {
  pywebview.api.save_config({ page_profiles: PAGE_PROFILES });
}

function pageProfileSyncActive(page) {
  const store = PAGE_PROFILES[page];
  if (!store) return;
  store.profiles[store.active] = pageProfileCapture(page);
  pageProfilesPersist();
}

function ensureProfileBar(page) {
  const pane = document.getElementById('pane-' + page);
  if (!pane) return null;
  let bar = pane.querySelector(':scope > .page-profile-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'page-profile-bar';
    bar.id = 'profile-bar-' + page;
    pane.insertBefore(bar, pane.firstChild);
  }
  return bar;
}

function renderProfileBar(page) {
  const bar = ensureProfileBar(page);
  if (!bar) return;
  const store = pageProfileStore(page);
  bar.innerHTML = '';

  const label = document.createElement('span');
  label.className = 'profile-bar-label';
  label.textContent = 'Набор данных:';
  bar.appendChild(label);

  Object.keys(store.profiles).forEach(name => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'profile-chip' + (name === store.active ? ' active' : '');
    btn.textContent = name;
    btn.title = `Переключиться на «${name}»`;
    btn.addEventListener('click', () => pageProfileSwitch(page, name));
    bar.appendChild(btn);
  });

  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'profile-chip profile-chip-add';
  addBtn.textContent = '+ Добавить';
  addBtn.title = 'Новый набор данных (старые не удаляются)';
  addBtn.addEventListener('click', () => pageProfileAdd(page));
  bar.appendChild(addBtn);

  const renBtn = document.createElement('button');
  renBtn.type = 'button';
  renBtn.className = 'profile-chip profile-chip-icon';
  renBtn.textContent = '✎';
  renBtn.title = 'Переименовать текущий набор';
  renBtn.addEventListener('click', () => pageProfileRename(page));
  bar.appendChild(renBtn);

  if (Object.keys(store.profiles).length > 1) {
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'profile-chip profile-chip-icon profile-chip-del';
    delBtn.textContent = '🗑';
    delBtn.title = 'Удалить текущий набор';
    delBtn.addEventListener('click', () => pageProfileDelete(page));
    bar.appendChild(delBtn);
  }
}

function pageProfileSwitch(page, name) {
  const store = pageProfileStore(page);
  if (name === store.active) return;
  store.profiles[store.active] = pageProfileCapture(page);
  store.active = name;
  pageProfileApply(page, store.profiles[name]);
  renderProfileBar(page);
  pageProfilesPersist();
}

async function pageProfileAdd(page) {
  const raw = await _appModal({ title: 'Новый набор данных', defaultValue: '', placeholder: 'Например «Кетчуп 2025»' });
  const name = (raw || '').trim();
  if (!name) return;
  const store = pageProfileStore(page);
  if (store.profiles[name]) { showToast('warning', 'Набор с таким названием уже есть'); return; }
  store.profiles[store.active] = pageProfileCapture(page);
  store.profiles[name] = {};
  store.active = name;
  pageProfileApply(page, {});
  renderProfileBar(page);
  pageProfilesPersist();
  showToast('success', `Создан набор «${name}» — заполните поля новыми данными`);
}

async function pageProfileRename(page) {
  const store = pageProfileStore(page);
  const oldName = store.active;
  const raw = await _appModal({ title: 'Переименовать набор', defaultValue: oldName });
  const newName = (raw || '').trim();
  if (!newName || newName === oldName) return;
  if (store.profiles[newName]) { showToast('warning', 'Набор с таким названием уже есть'); return; }
  store.profiles[newName] = store.profiles[oldName];
  delete store.profiles[oldName];
  store.active = newName;
  renderProfileBar(page);
  pageProfilesPersist();
}

async function pageProfileDelete(page) {
  const store = pageProfileStore(page);
  const names = Object.keys(store.profiles);
  if (names.length <= 1) return;
  const ok = await _appModal({
    title: 'Удалить набор данных',
    message: `Удалить набор «${store.active}»? Данные в нём будут потеряны.`,
    okLabel: 'Удалить', danger: true,
  });
  if (!ok) return;
  delete store.profiles[store.active];
  store.active = Object.keys(store.profiles)[0];
  pageProfileApply(page, store.profiles[store.active]);
  renderProfileBar(page);
  pageProfilesPersist();
}

function pageProfilesInitAll() {
  document.querySelectorAll('.pane[id^="pane-"]').forEach(pane => {
    const page = pane.id.replace('pane-', '');
    pageProfileStore(page);
    renderProfileBar(page);
  });
}

// ── Navigation ────────────────────────────────────────────────────────────
const PAGE_TITLES = {
  promodate:'Промодата', competitors:'Конкуренты', nielsen:'Nielsen',
  query_refresh:'Обновить квери', production:'Производство', oos:'Отчёт без OOS',
  dist_competitors:'Дистрибуция конкурентов',
  market_share_territory:'Доли рынка по территориям',
  market_share_brands:'Доли рынка брендов',
};
const REFRESH_PAGES = new Set(['dist_competitors', 'market_share_territory', 'market_share_brands']);
function navigate(page) {
  S.page = page;
  document.querySelectorAll('.nav-item[data-page]').forEach(b => b.classList.toggle('active', b.dataset.page===page));
  document.querySelectorAll('.pane').forEach(p => p.classList.toggle('active', p.id===`pane-${page}`));
  document.getElementById('page-title').textContent = PAGE_TITLES[page] || page;
  document.querySelectorAll('.bar-group').forEach(g => g.style.display='none');
  const barId = page==='promodate' ? 'bar-promodate'
              : page==='competitors' ? 'bar-competitors'
              : page==='oos' ? 'bar-oos'
              : REFRESH_PAGES.has(page) ? 'bar-refresh'
              : 'bar-default';
  const bar = document.getElementById(barId);
  if (bar) bar.style.display = 'flex';
  if (barId === 'bar-refresh') _refreshUpdateOpenBtn();
}
document.querySelectorAll('.nav-item[data-page]').forEach(b => b.addEventListener('click', ()=>navigate(b.dataset.page)));

// ── Stage selector ────────────────────────────────────────────────────────
function setStage(btn) {
  S.stage = btn.dataset.stage;
  document.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('active', b===btn));
}

// ── File pickers ──────────────────────────────────────────────────────────
function clearField(btn) {
  const row = btn.closest('.form-row');
  if (!row) return;
  const input = row.querySelector('.form-input[data-field]');
  if (!input) return;
  input.value = '';
  autoSave();
}

async function pickFile(field) {
  const path = await pywebview.api.browse_file();
  if (path) { const el = document.querySelector(`[data-field="${field}"]`); if(el){el.value=path;autoSave();} }
}
async function pickAnyFile(field) {
  const path = await pywebview.api.browse_any_file();
  if (path) { const el = document.querySelector(`[data-field="${field}"]`); if(el){el.value=path;autoSave();} }
}
async function pickFolder(field) {
  const path = await pywebview.api.browse_folder();
  if (path) { const el = document.querySelector(`[data-field="${field}"]`); if(el){el.value=path;autoSave();} }
}
async function pcPickOutput() {
  const path = await pywebview.api.browse_save_file();
  if (path) { const el=document.querySelector('[data-field="pc_output_file"]'); if(el){el.value=path;autoSave();} }
}
function getField(field) {
  const el = document.querySelector(`[data-field="${field}"]`);
  return el ? el.value : '';
}

// ── Режим промодаты (ЦО / Мониторинг цен / Дополнительно) ──────────────────
function syncPromoModeUI(mode) {
  document.querySelectorAll('#promo-mode-ctrl .seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.mode === mode);
  });
  const hidden = document.getElementById('sel-promodata-mode');
  if (hidden) hidden.value = mode;
}

const PROMO_MODE_FIELDS = ['output_folder', 'pq_file1', 'pq_file2', 'macro1', 'macro2'];

async function promoSetMode(mode) {
  const cfg = await pywebview.api.set_promodata_mode(mode);
  syncPromoModeUI(cfg.promodata_mode);
  PROMO_MODE_FIELDS.forEach(field => {
    const el = document.querySelector(`[data-field="${field}"]`);
    if (el) el.value = cfg[field] || '';
  });
  const label = document.querySelector(`#promo-mode-ctrl .seg-btn[data-mode="${cfg.promodata_mode}"]`);
  showToast('success', `Режим: ${label ? label.textContent : cfg.promodata_mode}`);
}

// ── Run action ────────────────────────────────────────────────────────────
async function runAction() {
  showProgress();
  if (S.page === 'promodate') {
    const p = {
      month_from:getField('month_from'), year_from:getField('year_from'),
      month_to:getField('month_to'),     year_to:getField('year_to'),
      date_from:   _dlMode==='multi' ? null : (_dlFrom ? _dateKey(_dlFrom) : null),
      date_to:     _dlMode==='multi' ? null : (_dlTo   ? _dateKey(_dlTo)   : null),
      dates_list:  _dlMode==='multi' ? [..._dlDates].sort() : null,
      output_folder:getField('output_folder'), category:getField('category'),
      pq_file1:getField('pq_file1'), pq_file2:getField('pq_file2'),
      macro1:getField('macro1'), macro2:getField('macro2'),
      networks: getSelectedNetworks(),
      promodata_mode: getField('promodata_mode'),
    };
    if (S.stage==='all')    await pywebview.api.start_process(p);
    else if (S.stage==='query1') await pywebview.api.run_stage_q1(p);
    else if (S.stage==='query2') await pywebview.api.run_stage_q2(p);
    else if (S.stage==='macros') await pywebview.api.run_stage_macros(p);
  } else if (S.page==='competitors') {
    await pywebview.api.run_competitors({olap_file:getField('olap_file'),competitors_file:getField('competitors_file')});
  } else if (S.page==='nielsen') {
    await pywebview.api.run_nielsen({input_file:getField('nielsen_input'),input_file2:getField('nielsen_input2'),output_dir:getField('nielsen_output'),output_dir2:getField('nielsen_output2'),format:getField('nielsen_format'),category:getField('nielsen_category'),sprav_path:getField('nielsen_sprav_path'),pq_file:getField('nielsen_pq_file'),pq_file_nu:getField('nielsen_pq_file_nu'),arch_input:getField('nielsen_arch_input'),arch_input2:getField('nielsen_arch_input2'),arch_enabled:document.getElementById('nielsen_arch_enabled')?.checked||false});
    // Снимаем галочку архива после запуска — однократный прогон
    const archCb = document.getElementById('nielsen_arch_enabled');
    if (archCb) { archCb.checked = false; autoSave(); }
  } else if (S.page==='query_refresh') {
    await pywebview.api.run_query_refresh({file:getField('query_refresh_file'), page:'query_refresh'});
  } else if (S.page==='dist_competitors') {
    const f = getField('dist_competitors_file');
    if (!f) { addLog('⚠️ Укажите файл отчёта'); return; }
    document.getElementById('refresh-open-btn').style.display = 'none';
    await pywebview.api.run_query_refresh({file:f, page:'dist_competitors'});
  } else if (S.page==='market_share_territory') {
    const f = getField('market_share_territory_file');
    if (!f) { addLog('⚠️ Укажите файл отчёта'); return; }
    document.getElementById('refresh-open-btn').style.display = 'none';
    await pywebview.api.run_query_refresh({file:f, page:'market_share_territory'});
  } else if (S.page==='market_share_brands') {
    const f1 = getField('msb_file1'), f2 = getField('msb_file2'), f3 = getField('msb_file3');
    if (!f1 || !f2 || !f3) { addLog('⚠️ Укажите все 3 файла'); return; }
    document.getElementById('refresh-open-btn').style.display = 'none';
    await pywebview.api.run_market_share_brands({file1:f1, file2:f2, file3:f3});
  } else if (S.page==='production') {
    const monthLabel = getField('prod_month');
    await pywebview.api.run_production({
      svod_folder:getField('prod_svod_folder'),
      npk_file:getField('prod_npk_file'),
      tolyatti_folder:getField('prod_tolyatti'), target_file:getField('prod_target'),
      mapping_file:getField('prod_mapping'), month_str:monthLabel.split(' - ')[0],
      year:getField('prod_year'),
    });
  }
}
function stopAction() { pywebview.api.stop(); hideProgress(); }

// ── Фильтр по сетям (модальное окно) ─────────────────────────────────────────
function openNetworksModal() {
  const overlay = document.getElementById('networks-modal-overlay');
  overlay.style.display = 'flex';
  // Если список ещё не загружен — загружаем автоматически
  const list = document.getElementById('network-filter-list');
  if (!list.querySelector('.net-chk')) loadNetworks();
}

function closeNetworksModal() {
  document.getElementById('networks-modal-overlay').style.display = 'none';
  _updateNetworksBtnLabel();
}

function _updateNetworksBtnLabel() {
  const checks  = document.querySelectorAll('#network-filter-list .net-chk');
  const checked = document.querySelectorAll('#network-filter-list .net-chk:checked');
  const label   = document.getElementById('networks-btn-label');
  const count   = document.getElementById('networks-count-label');
  if (!checks.length) {
    if (label) label.textContent = 'Все по умолчанию';
    if (count) count.textContent = '';
    return;
  }
  if (checked.length === checks.length) {
    if (label) label.textContent = `Все сети (${checks.length})`;
  } else {
    if (label) label.textContent = `Выбрано: ${checked.length} из ${checks.length}`;
  }
  if (count) count.textContent = `Выбрано ${checked.length} из ${checks.length} сетей`;
}

async function loadNetworks() {
  const btn = document.getElementById('load-networks-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    const nets = await pywebview.api.get_networks();
    const container = document.getElementById('network-filter-list');
    if (!container) return;
    container.innerHTML = '';
    nets.forEach(n => {
      const label = document.createElement('label');
      label.className = 'network-filter-item';
      label.dataset.name = n.toLowerCase();
      label.style.cssText = 'display:flex;align-items:center;gap:6px;padding:6px 10px;background:var(--input-bg);border-radius:6px;cursor:pointer;font-size:13px;user-select:none';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.className = 'net-chk';
      chk.value = n;
      chk.checked = true;
      chk.onchange = _updateNetworksBtnLabel;
      label.appendChild(chk);
      label.appendChild(document.createTextNode(n));
      container.appendChild(label);
    });
    _updateNetworksBtnLabel();
  } catch(e) {
    showToast('error', 'Не удалось загрузить список сетей');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '↻ Загрузить'; }
  }
}

function filterNetworksList() {
  const q = (document.getElementById('networks-search')?.value || '').toLowerCase();
  document.querySelectorAll('#network-filter-list .network-filter-item').forEach(el => {
    el.style.display = el.dataset.name?.includes(q) ? '' : 'none';
  });
}

function getSelectedNetworks() {
  const checks  = document.querySelectorAll('#network-filter-list .net-chk');
  if (!checks.length) return null;
  const selected = Array.from(checks).filter(c => c.checked).map(c => c.value);
  if (selected.length === checks.length) return null;
  return selected.length ? selected : null;
}

function toggleAllNetworks(checked) {
  document.querySelectorAll('#network-filter-list .net-chk').forEach(c => c.checked = checked);
  _updateNetworksBtnLabel();
}

function resetNetworksToDefault() {
  document.getElementById('network-filter-list').innerHTML =
    '<span style="color:var(--text-muted);font-size:12px;grid-column:1/-1">Список сброшен — используется фильтр по умолчанию</span>';
  const label = document.getElementById('networks-btn-label');
  if (label) label.textContent = 'Все по умолчанию';
  const count = document.getElementById('networks-count-label');
  if (count) count.textContent = '';
}

// Закрытие по клику на оверлей
document.addEventListener('click', e => {
  if (e.target.id === 'networks-modal-overlay') closeNetworksModal();
});

async function doDownload() {
  showProgress();
  await pywebview.api.start_download({
    month_from:  getField('month_from'), year_from: getField('year_from'),
    month_to:    getField('month_to'),   year_to:   getField('year_to'),
    date_from:   _dlMode === 'multi' ? null : (_dlFrom ? _dateKey(_dlFrom) : null),
    date_to:     _dlMode === 'multi' ? null : (_dlTo   ? _dateKey(_dlTo)   : null),
    dates_list:  _dlMode === 'multi' ? [..._dlDates].sort() : null,
    promodata_mode: getField('promodata_mode'),
  });
}
function confirmClearDownloads() { if(confirm('Удалить все файлы из папки скачивания текущего режима?')) pywebview.api.clear_downloads(); }
function confirmClearOutput() {
  const p=getField('output_folder');
  if(!p){showToast('warning','Папка сохранения не задана');return;}
  if(confirm('Удалить все CSV из папки сохранения?')) pywebview.api.clear_output(p);
}
function openOutputFolder() {
  const p=getField('output_folder');
  if(p) pywebview.api.open_folder(p); else showToast('warning','Папка сохранения не задана');
}

// ── Price comparison logic ────────────────────────────────────────────────
async function pcRun() {
  const kuper  = getField('pc_kuper_file');
  const promo  = getField('pc_promo_file');
  const sprav  = getField('pc_sprav_file');
  const output = getField('pc_output_file');

  if (!kuper)  { showToast('warning','Укажите файл Купера');     return; }
  if (!promo)  { showToast('warning','Укажите файл PromoData');   return; }
  if (!sprav)  { showToast('warning','Укажите справочник SKU');   return; }
  if (!output) { showToast('warning','Укажите путь для сохранения'); return; }

  const thresh = parseFloat(getField('pc_threshold') || '0.5');

  showProgress();
  document.getElementById('pc-run-btn').disabled = true;
  document.getElementById('pc-open-btn').style.display = 'none';
  document.getElementById('pc-log-box').textContent = '';

  await pywebview.api.run_price_comparison({
    kuper_file: kuper, promo_file: promo, sprav_file: sprav,
    output_file: output, threshold: thresh,
  });
}

function pcOnStarted() {
  pcAddLog('▶ Запуск сравнения цен…');
  document.getElementById('pc-stat-total').textContent = '…';
  document.getElementById('pc-stat-ketch').textContent = '…';
  document.getElementById('pc-stat-mayo').textContent  = '…';
}

function pcAddLog(msg) {
  const box = document.getElementById('pc-log-box');
  box.textContent += msg + '\n';
  box.scrollTop = box.scrollHeight;
}

function pcOnDone(data) {
  hideProgress();
  document.getElementById('pc-run-btn').disabled = false;
  document.getElementById('pc-stat-total').textContent = data.rows ?? '—';
  S.pcLastOutput = data.output || '';
  if (S.pcLastOutput) {
    document.getElementById('pc-open-btn').style.display = '';
  }
  // Кетчуп/Майонез из лога не парсим — показываем только total
  // (точные числа возвращаются в toast)
  pcAddLog(`✅ Готово! Строк: ${data.rows}`);
}

function pcOnError(msg) {
  hideProgress();
  document.getElementById('pc-run-btn').disabled = false;
  pcAddLog(`❌ Ошибка: ${msg}`);
}

function pcOpenResult() {
  if (S.pcLastOutput) pywebview.api.open_pc_result(S.pcLastOutput);
}

// ── Progress ──────────────────────────────────────────────────────────────
function showProgress() { document.getElementById('progress-wrap').classList.add('visible'); }
function hideProgress() {
  document.getElementById('progress-fill').style.width='0%';
  document.getElementById('progress-text').textContent='';
  document.getElementById('progress-wrap').classList.remove('visible');
}
function updateProgress(done,total) {
  showProgress();
  const pct=total?(done/total*100):0;
  document.getElementById('progress-fill').style.width=pct+'%';
  document.getElementById('progress-text').textContent=`${done} / ${total}`;
}
function setStatus(text) {
  const el=document.getElementById('page-status');
  if(text){el.textContent=text;el.classList.add('visible');}
  else{el.textContent='';el.classList.remove('visible');}
}

// ── Log ───────────────────────────────────────────────────────────────────
function addLog(msg) {
  const box=document.getElementById('log-content');
  const line=document.createElement('div'); line.className='log-line';
  const m=String(msg).match(/^\[(\d{2}:\d{2}:\d{2})\]\s+(.*)/s);
  if(m){
    const mc=/ошибка|error|✗/i.test(m[2])?'err':/✅|завершён|готово|🎉/i.test(m[2])?'ok':/⚠|warning/i.test(m[2])?'warn':'';
    line.innerHTML=`<span class="log-ts">[${m[1]}]</span><span class="log-msg ${mc}">${esc(m[2])}</span>`;
  } else { line.innerHTML=`<span class="log-msg">${esc(String(msg))}</span>`; }
  box.appendChild(line);
  if(box.children.length>500) box.firstChild.remove();
  box.scrollTop=box.scrollHeight;
}
function clearLog() { document.getElementById('log-content').innerHTML=''; }
function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(type,message){
  const icons={success:'✅',warning:'⚠️',error:'❌',info:'ℹ️'};
  const wrap=document.getElementById('toast-wrap');
  const t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<span class="toast-icon">${icons[type]||'ℹ️'}</span><span>${esc(String(message))}</span>`;
  wrap.appendChild(t);
  setTimeout(()=>{t.style.opacity='0';t.style.transition='opacity .3s';setTimeout(()=>t.remove(),300);},3500);
}

// ── SKU Matcher ───────────────────────────────────────────────────────────
function openSkuMatcher()  { document.getElementById('sku-overlay').classList.add('open'); }
function closeSkuMatcher() { document.getElementById('sku-overlay').classList.remove('open'); }
function closeSkuIfBg(e)   { if(e.target===document.getElementById('sku-overlay')) closeSkuMatcher(); }
function skuSetMode(mode) {
  S.skuMode = mode;
  document.getElementById('sku-mode-ml').classList.toggle('active', mode === 'ml');
  document.getElementById('sku-mode-ensemble').classList.toggle('active', mode === 'ensemble');
  document.getElementById('sku-mode-classic').classList.toggle('active', mode === 'classic');
}
async function skuPickRef() {
  const p=await pywebview.api.browse_file();
  if(p){document.getElementById('sku-ref-path').value=p;S.skuRefPath=p;skuPersistPaths();}
}
async function skuPickFolder(){
  const p=await pywebview.api.browse_folder();
  if(p){
    document.getElementById('sku-csv-folder').value=p;
    const cnt=await pywebview.api.get_csv_count(p);
    document.getElementById('sku-csv-count').textContent=cnt?`${cnt} файлов CSV`:'';
    skuPersistPaths();
  }
}
function skuPersistPaths(){
  const cfg=collectFormConfig();
  cfg.sku_ref_path=document.getElementById('sku-ref-path').value;
  cfg.sku_csv_folder=document.getElementById('sku-csv-folder').value;
  pywebview.api.save_config(cfg);
}
async function skuRun(){
  const ref=document.getElementById('sku-ref-path').value;
  const folder=document.getElementById('sku-csv-folder').value;
  if(!ref){showToast('warning','Выбери файл справочника');return;}
  if(!folder){showToast('warning','Выбери папку с CSV');return;}
  const thresh=parseFloat(document.querySelector('.thresh-slider').value);
  document.getElementById('sku-run-btn').textContent='⏳ Анализирую…';
  document.getElementById('sku-run-btn').disabled=true;
  document.getElementById('sku-tbody').innerHTML='';
  document.getElementById('new-sku-tbody').innerHTML='';
  S.skuAllResults=[];S.skuSelected.clear();S.skuAllNew=[];S.skuNewSelected.clear();skuUpdateSel();
  skuUpdateTabCounts(0,0);
  skuSwitchTab('match');
  await pywebview.api.run_sku_matching({ref_path:ref,csv_folder:folder,threshold:thresh,mode:S.skuMode});
}
function skuUnlock(){document.getElementById('sku-run-btn').textContent='▶ Запустить матчинг';document.getElementById('sku-run-btn').disabled=false;}
function skuRenderResults(results){
  skuUnlock();S.skuAllResults=results;S.skuSelected=new Set(results.map((_,i)=>i));
  skuDisplayRows(results);
  const high=results.filter(r=>r['Уверенность']>=0.9).length;
  const mid=results.filter(r=>r['Уверенность']>=0.7&&r['Уверенность']<0.9).length;
  const low=results.filter(r=>r['Уверенность']<0.7).length;
  document.getElementById('sku-stat').innerHTML=`Всего: ${results.length}<br>≥0.9: ${high} &nbsp; 0.7–0.9: ${mid} &nbsp; &lt;0.7: ${low}`;
  skuUpdateSel();skuLog(`✓ ${results.length} совпадений`);
  skuUpdateTabCounts(results.length, S.skuAllNew.length);
}
function skuRenderAllNew(all){
  S.skuAllNew=all;
  S.skuNewSelected=new Set(all.map((_,i)=>i)); // все выбраны по умолчанию
  skuFillAllNewTable(all);
  skuLog(`★ Все новые SKU: ${all.length}`);
  skuUpdateTabCounts(S.skuAllResults.length, all.length);
  if(S.skuActiveTab==='allnew') skuUpdateSel();
}
function skuFillAllNewTable(rows){
  const tbody=document.getElementById('new-sku-tbody');tbody.innerHTML='';
  rows.forEach(r=>{
    const gi=S.skuAllNew.indexOf(r);
    const sel=S.skuNewSelected.has(gi);
    const tr=document.createElement('tr');tr.dataset.idx=gi;
    if(sel)tr.classList.add('selected');
    tr.innerHTML=`<td><span class="sku-chk ${sel?'on':''}">${sel?'●':'○'}</span></td>
      <td>${esc(r['SKU']||'')}</td><td>${esc(r['Бренд']||'')}</td><td>${esc(r['Категория']||'')}</td>`;
    tr.addEventListener('click',()=>skuNewToggleRow(tr,gi));
    tbody.appendChild(tr);
  });
}
function skuNewToggleRow(tr,idx){
  if(S.skuNewSelected.has(idx))S.skuNewSelected.delete(idx);else S.skuNewSelected.add(idx);
  const sel=S.skuNewSelected.has(idx);
  tr.classList.toggle('selected',sel);
  tr.querySelector('.sku-chk').className=`sku-chk ${sel?'on':''}`;
  tr.querySelector('.sku-chk').textContent=sel?'●':'○';
  skuUpdateSel();
}
function skuUpdateTabCounts(matchN, allNewN){
  const mc=document.getElementById('sku-tab-match-cnt');
  const ac=document.getElementById('sku-tab-allnew-cnt');
  if(mc) mc.textContent=matchN||'';
  if(ac) ac.textContent=allNewN||'';
}
function skuSwitchTab(tab){
  S.skuActiveTab=tab;
  document.getElementById('sku-tab-match').classList.toggle('active', tab==='match');
  document.getElementById('sku-tab-allnew').classList.toggle('active', tab==='allnew');
  document.getElementById('sku-table-wrap').style.display= tab==='match'?'':'none';
  document.getElementById('new-sku-wrap').style.display  = tab==='allnew'?'flex':'none';
  document.getElementById('sku-search').placeholder=
    tab==='match'?'Поиск: SKU, бренд, совпало…':'Поиск по наименованию или бренду…';
  skuUpdateSel();
}
function skuDisplayRows(rows){
  const tbody=document.getElementById('sku-tbody');tbody.innerHTML='';
  rows.forEach((r)=>{
    const gi=S.skuAllResults.indexOf(r);
    const conf=r['Уверенность'];
    const isAuto=!r['Совпало с'];  // авто-добавленные не имеют источника совпадения
    let badge;
    if(isAuto){
      badge=`<span class="conf-badge conf-auto">авто</span>`;
    } else {
      const cc=conf>=0.9?'high':conf>=0.7?'mid':'low';
      badge=`<span class="conf-badge conf-${cc}">${Math.round(conf*100)}%</span>`;
    }
    const sel=S.skuSelected.has(gi);
    const tr=document.createElement('tr');tr.dataset.idx=gi;
    if(sel)tr.classList.add('selected');
    tr.innerHTML=`<td><span class="sku-chk ${sel?'on':''}">${sel?'●':'○'}</span></td>
      <td>${esc(r['Категория']||'')}</td><td>${esc(r['Бренд']||'')}</td>
      <td>${esc(r['Наименование SKU']||'')}</td><td>${esc(r['Совпало с']||'')}</td>
      <td>${esc(r['SKU скорр']||'')}</td>
      <td style="text-align:center">${badge}</td>`;
    tr.addEventListener('click',()=>skuToggleRow(tr,gi));tbody.appendChild(tr);
  });
}
function skuToggleRow(tr,idx){
  const wasSelected = S.skuSelected.has(idx);
  if(wasSelected) {
    S.skuSelected.delete(idx);
    // Пользователь снял галочку — запоминаем отклонение
    const r = S.skuAllResults[idx];
    if(r) pywebview.api.save_sku_rejection({
      query:   r['Наименование SKU'] || '',
      ref_raw: r['Совпало с'] || '',
      ref_path: S.skuRefPath,
    }).catch(()=>{});
  } else {
    S.skuSelected.add(idx);
  }
  tr.classList.toggle('selected',S.skuSelected.has(idx));
  tr.querySelector('.sku-chk').className=`sku-chk ${S.skuSelected.has(idx)?'on':''}`;
  tr.querySelector('.sku-chk').textContent=S.skuSelected.has(idx)?'●':'○';
  skuUpdateSel();
}
function skuSelectAll(){
  if(S.skuActiveTab==='allnew'){S.skuAllNew.forEach((_,i)=>S.skuNewSelected.add(i));skuNewRefreshVisible();}
  else{S.skuAllResults.forEach((_,i)=>S.skuSelected.add(i));skuRefreshVisible();}
  skuUpdateSel();
}
function skuDeselectAll(){
  if(S.skuActiveTab==='allnew'){S.skuNewSelected.clear();skuNewRefreshVisible();}
  else{S.skuSelected.clear();skuRefreshVisible();}
  skuUpdateSel();
}
function skuInvert(){
  if(S.skuActiveTab==='allnew'){
    S.skuAllNew.forEach((_,i)=>{if(S.skuNewSelected.has(i))S.skuNewSelected.delete(i);else S.skuNewSelected.add(i);});
    skuNewRefreshVisible();
  } else {
    S.skuAllResults.forEach((_,i)=>{if(S.skuSelected.has(i))S.skuSelected.delete(i);else S.skuSelected.add(i);});
    skuRefreshVisible();
  }
  skuUpdateSel();
}
function skuRefreshVisible(){
  document.querySelectorAll('#sku-tbody tr').forEach(tr=>{
    const idx=parseInt(tr.dataset.idx);const sel=S.skuSelected.has(idx);
    tr.classList.toggle('selected',sel);
    tr.querySelector('.sku-chk').className=`sku-chk ${sel?'on':''}`;
    tr.querySelector('.sku-chk').textContent=sel?'●':'○';
  });
}
function skuNewRefreshVisible(){
  document.querySelectorAll('#new-sku-tbody tr').forEach(tr=>{
    const idx=parseInt(tr.dataset.idx);const sel=S.skuNewSelected.has(idx);
    tr.classList.toggle('selected',sel);
    tr.querySelector('.sku-chk').className=`sku-chk ${sel?'on':''}`;
    tr.querySelector('.sku-chk').textContent=sel?'●':'○';
  });
}
function skuUpdateSel(){
  const isNew=S.skuActiveTab==='allnew';
  const n=isNew?S.skuNewSelected.size:S.skuSelected.size;
  document.getElementById('sku-sel-stat').textContent=`Выбрано: ${n}`;
  document.getElementById('sku-save-btn').disabled=n===0;
}
function skuFilter(){
  const q=document.getElementById('sku-search').value.toLowerCase();
  if(S.skuActiveTab==='allnew'){
    const filtered=q?S.skuAllNew.filter(r=>(r['SKU']||'').toLowerCase().includes(q)||(r['Бренд']||'').toLowerCase().includes(q)||(r['Категория']||'').toLowerCase().includes(q)):S.skuAllNew;
    skuFillAllNewTable(filtered);
  } else {
    const filtered=q?S.skuAllResults.filter(r=>(r['Наименование SKU']||'').toLowerCase().includes(q)||(r['Бренд']||'').toLowerCase().includes(q)||(r['SKU скорр']||'').toLowerCase().includes(q)):S.skuAllResults;
    skuDisplayRows(filtered);
  }
}
async function skuSave(){
  let toSave;
  if(S.skuActiveTab==='allnew'){
    const rawNew=[...S.skuNewSelected].map(i=>S.skuAllNew[i]).filter(Boolean);
    if(!rawNew.length)return;
    if(!confirm(`Добавить ${rawNew.length} строк в справочник?`))return;
    toSave=rawNew.map(r=>({'Категория':r['Категория']||'','Бренд':r['Бренд']||'','Наименование SKU':r['SKU']||'','SKU скорр':'','Статус SKU':'индикативное','Уверенность':''}));
  } else {
    toSave=[...S.skuSelected].map(i=>S.skuAllResults[i]).filter(Boolean);
    if(!toSave.length)return;
    if(!confirm(`Добавить ${toSave.length} строк в справочник?`))return;
  }
  const result=await pywebview.api.save_sku_results({results:toSave,ref_path:S.skuRefPath});
  if(result.success){showToast('success',`Сохранено ${result.count} строк`);skuLog(`✓ Сохранено ${result.count} строк`);}
  else{showToast('error',result.error||'Ошибка сохранения');}
}
function skuLog(msg){const b=document.getElementById('sku-log-box');b.textContent+=msg+'\n';b.scrollTop=b.scrollHeight;}

// ── Theme ─────────────────────────────────────────────────────────────────
function toggleTheme(){
  const isDark=document.body.classList.toggle('dark');
  applyThemeUI(isDark);
  pywebview.api.save_config(collectFormConfig());
}
function applyThemeUI(isDark){
  document.getElementById('theme-icon').textContent=isDark?'☀️':'🌙';
  document.getElementById('theme-label').textContent=isDark?'Светлая тема':'Тёмная тема';
}
function applyThemeFromConfig(cfg){
  if(cfg.dark_theme){document.body.classList.add('dark');applyThemeUI(true);}
}

  // ══════════════════════════════════════════════════════════════════════
  // ПЛАНИРОВЩИК — ПРАВЫЙ DRAWER
  // ══════════════════════════════════════════════════════════════════════

  // ── Открытие / закрытие drawer ────────────────────────────────────────
  let _schedOpen = false;
  function schedDrawerOpen() {
    _schedOpen = true;
    document.getElementById('sched-drawer').style.transform = 'translateX(0)';
    const ov = document.getElementById('sched-overlay');
    ov.style.pointerEvents = 'all';
    ov.style.background    = 'rgba(0,0,0,.25)';
  }
  function schedDrawerClose() {
    _schedOpen = false;
    document.getElementById('sched-drawer').style.transform = 'translateX(100%)';
    const ov = document.getElementById('sched-overlay');
    ov.style.pointerEvents = 'none';
    ov.style.background    = 'rgba(0,0,0,0)';
  }

  // ── Toggle enabled ────────────────────────────────────────────────────
  let _schedEnabled = false;
  function schedToggleEnabled() {
    _schedEnabled = !_schedEnabled;
    _schedApplyToggle(_schedEnabled);
    schedSave();
  }
  function _schedApplyToggle(on) {
    const wrap  = document.getElementById('sched-toggle-wrap');
    const thumb = document.getElementById('sched-toggle-thumb');
    const lbl   = document.getElementById('sched-toggle-lbl');
    const dot   = document.getElementById('sched-dot');
    if (on) {
      wrap.style.background  = '#1e8c42';
      thumb.style.left       = '21px';
      lbl.textContent        = 'Вкл';
      lbl.style.color        = '#1e8c42';
      if (dot) { dot.style.background = '#1e8c42'; dot.style.boxShadow = '0 0 0 2px rgba(30,140,66,.3)'; }
    } else {
      wrap.style.background  = '#ccc';
      thumb.style.left       = '3px';
      lbl.textContent        = 'Выкл';
      lbl.style.color        = 'var(--text3)';
      if (dot) { dot.style.background = '#ccc'; dot.style.boxShadow = 'none'; }
    }
  }

  // ── Auto month toggle ─────────────────────────────────────────────────
  let _schedAutoMonth = true;
  function schedAutoToggle() {
    _schedAutoMonth = !_schedAutoMonth;
    _schedApplyAutoMonth(_schedAutoMonth);
    schedSave();
  }
  function _schedApplyAutoMonth(on) {
    const wrap  = document.getElementById('sched-auto-wrap');
    const thumb = document.getElementById('sched-auto-thumb');
    const cal   = document.getElementById('sched-cal-wrap');
    if (on) {
      wrap.style.background = 'var(--green)';
      thumb.style.left = '18px';
      cal.style.display = 'none';
    } else {
      wrap.style.background = '#ccc';
      thumb.style.left = '2px';
      cal.style.display = 'block';
      schedCalRender();
    }
  }

  // ── Calendar (month range picker) ─────────────────────────────────────
  const MONTH_NAMES_SHORT = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
  let _calYear   = new Date().getFullYear();
  let _calFrom   = null;  // {month:1-12, year}
  let _calTo     = null;
  let _calPhase  = 'from'; // 'from' | 'to'

  function schedCalPrevYear() { _calYear--; schedCalRender(); }
  function schedCalNextYear() { _calYear++; schedCalRender(); }

  function schedCalRender() {
    document.getElementById('sched-cal-year').textContent = _calYear;
    const grid = document.getElementById('sched-cal-grid');
    grid.innerHTML = '';
    for (let m = 1; m <= 12; m++) {
      const btn = document.createElement('button');
      btn.className = 'sched-cal-month';
      btn.textContent = MONTH_NAMES_SHORT[m-1];
      btn.dataset.m = m;
      btn.dataset.y = _calYear;

      const cur = _calYear * 12 + m;
      const from = _calFrom ? (_calFrom.year * 12 + _calFrom.month) : null;
      const to   = _calTo   ? (_calTo.year   * 12 + _calTo.month)   : null;

      if (from && cur === from) btn.classList.add('range-start');
      if (to   && cur === to)   btn.classList.add('range-end');
      if (from && to && cur > from && cur < to) btn.classList.add('in-range');

      btn.addEventListener('click', () => schedCalClick(parseInt(btn.dataset.m), parseInt(btn.dataset.y)));
      grid.appendChild(btn);
    }
    // Update range display
    const disp = document.getElementById('sched-range-display');
    if (_calFrom && _calTo) {
      disp.textContent = `${MONTH_NAMES_SHORT[_calFrom.month-1]} ${_calFrom.year} — ${MONTH_NAMES_SHORT[_calTo.month-1]} ${_calTo.year}`;
      disp.style.background = 'var(--green-muted)';
    } else if (_calFrom) {
      disp.textContent = `${MONTH_NAMES_SHORT[_calFrom.month-1]} ${_calFrom.year} — выберите конец`;
      disp.style.background = 'var(--surface2)';
    } else {
      disp.textContent = 'Нажмите месяц для начала диапазона';
      disp.style.background = 'var(--surface2)';
    }
  }

  function schedCalClick(m, y) {
    if (_calPhase === 'from') {
      _calFrom  = {month: m, year: y};
      _calTo    = null;
      _calPhase = 'to';
    } else {
      const cur  = y * 12 + m;
      const from = _calFrom.year * 12 + _calFrom.month;
      if (cur < from) {
        // Swap
        _calTo    = _calFrom;
        _calFrom  = {month: m, year: y};
      } else {
        _calTo = {month: m, year: y};
      }
      _calPhase = 'from';
      schedSave();
    }
    schedCalRender();
  }

  // ── Load config ───────────────────────────────────────────────────────
  async function schedLoad() {
    const cfg = await pywebview.api.get_scheduler_config();

    _schedEnabled = !!cfg.scheduler_enabled;
    _schedApplyToggle(_schedEnabled);

    document.getElementById('sched-time').value = cfg.scheduler_time || '08:00';

    const days = cfg.scheduler_days || ['mon','tue','wed','thu','fri'];
    document.querySelectorAll('.sd').forEach(el => {
      el.querySelector('input').checked = days.includes(el.dataset.day);
    });

    const steps = cfg.scheduler_steps || ['download','process','query1','query2','macros'];
    document.querySelectorAll('.sched-step-row').forEach(el => {
      if (el.dataset.step) el.querySelector('input').checked = steps.includes(el.dataset.step);
    });

    _schedAutoMonth = cfg.scheduler_auto_month !== false;
    _schedApplyAutoMonth(_schedAutoMonth);

    // Init day calendar from config
    if (!_schedAutoMonth) {
      if (cfg.scheduler_date_from) { _scFrom = new Date(cfg.scheduler_date_from); }
      if (cfg.scheduler_date_to)   { _scTo   = new Date(cfg.scheduler_date_to);   }
    }
    if (_scFrom) { _scViewYear = _scFrom.getFullYear(); _scViewMonth = _scFrom.getMonth(); }
    schedCalRender();

    schedUpdateStatus(cfg.scheduler_last_run, cfg.scheduler_last_status);
    winTaskRefresh();

    // Populate category from main selector options
    const mainCat = document.getElementById('sel-category');
    const schedCat = document.getElementById('sched-category');
    if (mainCat && schedCat) {
      schedCat.innerHTML = mainCat.innerHTML;
      const savedCat = cfg.scheduler_category || (mainCat.value);
      if (savedCat) schedCat.value = savedCat;
    }
  }

  // ── Save config ───────────────────────────────────────────────────────
  async function schedSave() {
    const days = [];
    document.querySelectorAll('.sd').forEach(el => {
      if (el.querySelector('input').checked) days.push(el.dataset.day);
    });
    const steps = [];
    document.querySelectorAll('.sched-step-row').forEach(el => {
      if (el.dataset.step && el.querySelector('input').checked) steps.push(el.dataset.step);
    });

    const now = new Date();
    await pywebview.api.save_scheduler_config({
      scheduler_enabled:     _schedEnabled,
      scheduler_time:        document.getElementById('sched-time').value,
      scheduler_days:        days,
      scheduler_steps:       steps,
      scheduler_auto_month:  _schedAutoMonth,
      scheduler_date_from:   _scFrom ? _dateKey(_scFrom) : null,
      scheduler_date_to:     _scTo   ? _dateKey(_scTo)   : null,
      scheduler_month_from:  _scFrom ? _scFrom.getMonth()+1 : now.getMonth()+1,
      scheduler_year_from:   _scFrom ? _scFrom.getFullYear() : now.getFullYear(),
      scheduler_month_to:    _scTo   ? _scTo.getMonth()+1 : now.getMonth()+1,
      scheduler_year_to:     _scTo   ? _scTo.getFullYear() : now.getFullYear(),
      scheduler_category:    document.getElementById('sched-category')?.value || '',
    });
  }

  // ── Run now ───────────────────────────────────────────────────────────
  async function schedRunNow() {
    const steps = [];
    document.querySelectorAll('.sched-step-row').forEach(el => {
      if (el.dataset.step && el.querySelector('input').checked) steps.push(el.dataset.step);
    });
    const now = new Date();
    await pywebview.api.scheduler_run_now({
      steps,
      auto_month:  _schedAutoMonth,
      date_from:   _scFrom ? _dateKey(_scFrom) : null,
      date_to:     _scTo   ? _dateKey(_scTo)   : null,
      month_from:  _scFrom ? _scFrom.getMonth()+1 : now.getMonth()+1,
      year_from:   _scFrom ? _scFrom.getFullYear() : now.getFullYear(),
      month_to:    _scTo   ? _scTo.getMonth()+1 : now.getMonth()+1,
      year_to:     _scTo   ? _scTo.getFullYear() : now.getFullYear(),
    });
    schedUpdateStatus(new Date().toISOString().slice(0,19), 'running');
    showToast('success', 'Промодата запущена в фоне');
  }

  // ── Status display ────────────────────────────────────────────────────
  function schedUpdateStatus(lastRun, lastStatus) {
    const icon = document.getElementById('sched-status-icon');
    const text = document.getElementById('sched-status-text');
    const ts   = document.getElementById('sched-status-ts');
    if (!lastRun) {
      if(icon) icon.textContent = '⏳';
      if(text) { text.textContent = 'Ещё не запускался'; text.style.color='var(--text2)'; }
      if(ts)   ts.textContent = '';
      return;
    }
    const dt = lastRun.replace('T',' ');
    if (lastStatus === 'success') {
      if(icon) icon.textContent = '✅';
      if(text) { text.textContent='Выполнено успешно'; text.style.color='#1e8c42'; }
    } else if (lastStatus === 'error') {
      if(icon) icon.textContent = '❌';
      if(text) { text.textContent='Ошибка выполнения'; text.style.color='var(--red)'; }
    } else if (lastStatus === 'running') {
      if(icon) icon.textContent = '⚙️';
      if(text) { text.textContent='Выполняется…'; text.style.color='var(--orange)'; }
    }
    if(ts) ts.textContent = dt;
  }

  // ══════════════════════════════════════════════════════════════════════
  // WINDOWS TASK SCHEDULER ИНТЕГРАЦИЯ
  // ══════════════════════════════════════════════════════════════════════

  function _schedGetDays() {
    const days = [];
    document.querySelectorAll('.sd').forEach(el => {
      if (el.querySelector('input').checked) days.push(el.dataset.day);
    });
    return days;
  }

  function schedDayPreset(preset) {
    const all = ['mon','tue','wed','thu','fri','sat','sun'];
    const workdays = ['mon','tue','wed','thu','fri'];
    document.querySelectorAll('.sd').forEach(el => {
      const day = el.dataset.day;
      if (preset === 'workdays') el.querySelector('input').checked = workdays.includes(day);
      else if (preset === 'all')  el.querySelector('input').checked = true;
      else                        el.querySelector('input').checked = false;
    });
    schedSave();
  }

  async function winTaskCreate() {
    const btn = document.getElementById('win-task-create');
    btn.textContent = '⏳ Создаю...';
    btn.disabled = true;
    try {
      const result = await pywebview.api.create_windows_task({
        time: document.getElementById('sched-time').value,
        days: _schedGetDays(),
      });
      if (result.ok) {
        winTaskRefresh();
      } else {
        showToast('error', 'Ошибка: ' + result.msg);
      }
    } finally {
      btn.textContent = '✚ Создать задачу';
      btn.disabled = false;
    }
  }

  async function winTaskDelete() {
    if (!confirm('Удалить задачу "EFKO PromoData Auto" из Планировщика Windows?')) return;
    const result = await pywebview.api.delete_windows_task();
    if (result.ok) winTaskRefresh();
  }

  async function winTaskRefresh() {
    const icon = document.getElementById('win-task-icon');
    const name = document.getElementById('win-task-name');
    const next = document.getElementById('win-task-next');
    if (!icon) return;

    icon.textContent = '⏳';
    const status = await pywebview.api.get_windows_task_status();

    if (!status.exists) {
      icon.textContent = '⬜';
      name.textContent = 'Планировщик задач Windows';
      next.textContent = 'Задача не зарегистрирована';
      next.style.color = 'var(--text3)';
      document.getElementById('win-task-card').style.borderColor = 'var(--border)';
    } else {
      const running = (status.status || '').toLowerCase().includes('выполн')
                   || (status.status || '').toLowerCase().includes('running');
      const ready   = (status.status || '').toLowerCase().includes('ожид')
                   || (status.status || '').toLowerCase().includes('ready');
      icon.textContent = ready ? '✅' : (running ? '⚙️' : '⚠️');
      name.textContent = 'EFKO PromoData Auto — ' + (status.status || 'Активна');
      next.textContent = status.next_run ? ('Следующий запуск: ' + status.next_run) : '';
      next.style.color = ready ? '#1e8c42' : 'var(--orange)';
      document.getElementById('win-task-card').style.borderColor = ready ? '#1e8c42' : 'var(--orange)';
    }
  }

  async function winExportIcs() {
    const result = await pywebview.api.export_ics({
      time: document.getElementById('sched-time').value,
      days: _schedGetDays(),
    });
    if (result.ok) {
      showToast('success', 'Файл открыт в Календаре Windows: ' + result.path.split('\\').pop());
    }
  }


  // ══════════════════════════════════════════════════════════════════════
  // ОБЩИЙ МОДУЛЬ: DAY-LEVEL CALENDAR RANGE PICKER
  // ══════════════════════════════════════════════════════════════════════

  const MONTH_RU  = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                     'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const MONTH_SHORT = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
  const DOW       = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

  function _dateKey(d) {
    return d ? `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` : null;
  }

  /** Рисует одну сетку дней в контейнер.
   *  from/to — Date objects или null (range highlight)
   *  onDayClick(date) — callback
   */
  function renderCalGrid(container, year, month, from, to, onDayClick, pickedDates) {
    container.innerHTML = '';
    // Day-of-week headers (Mon first)
    DOW.forEach(d => {
      const h = document.createElement('div');
      h.className = 'cal-dow'; h.textContent = d;
      container.appendChild(h);
    });

    const today   = new Date();
    const firstDay = new Date(year, month, 1);
    // Monday-based offset
    let startDow = firstDay.getDay(); // 0=Sun
    startDow = startDow === 0 ? 6 : startDow - 1;
    const daysInMonth  = new Date(year, month+1, 0).getDate();
    const daysInPrev   = new Date(year, month,   0).getDate();
    const totalCells   = Math.ceil((startDow + daysInMonth) / 7) * 7;

    const fromKey = _dateKey(from);
    const toKey   = _dateKey(to);

    for (let i = 0; i < totalCells; i++) {
      const btn = document.createElement('button');
      btn.className = 'cal-day';
      let d;
      if (i < startDow) {
        d = new Date(year, month-1, daysInPrev - startDow + i + 1);
        btn.classList.add('other-month');
      } else if (i >= startDow + daysInMonth) {
        d = new Date(year, month+1, i - startDow - daysInMonth + 1);
        btn.classList.add('other-month');
      } else {
        d = new Date(year, month, i - startDow + 1);
      }

      btn.textContent = d.getDate();
      const key = _dateKey(d);

      if (key === _dateKey(today) && !btn.classList.contains('other-month')) btn.classList.add('today');
      // Multi-mode: highlight picked days
      if (pickedDates && pickedDates.has(key)) {
        btn.classList.add('day-picked');
      } else {
        if (fromKey && key === fromKey) btn.classList.add('range-start');
        if (toKey   && key === toKey)   btn.classList.add('range-end');
        if (fromKey && toKey && key > fromKey && key < toKey) btn.classList.add('in-range');
      }

      btn.addEventListener('click', () => onDayClick(d));
      container.appendChild(btn);
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // ГЛАВНЫЙ ЭКРАН — ДВУХМЕСЯЧНЫЙ КАЛЕНДАРЬ СКАЧИВАНИЯ
  // ══════════════════════════════════════════════════════════════════════

  let _dlViewYear  = new Date().getFullYear();
  let _dlViewMonth = new Date().getMonth();   // left month
  let _dlFrom = null;   // Date
  let _dlTo   = null;   // Date
  let _dlPhase = 'from'; // 'from' | 'to'
  let _dlMode  = 'range'; // 'range' | 'single' | 'multi'
  let _dlDates = new Set(); // Date keys для multi-режима

  function dlToggleMode() {
    const modes = ['range', 'single', 'multi'];
    _dlMode = modes[(modes.indexOf(_dlMode) + 1) % 3];
    const btn = document.getElementById('dl-mode-btn');
    if (btn) {
      if (_dlMode === 'range')  { btn.textContent = '↔ Диапазон';      btn.classList.remove('active'); }
      if (_dlMode === 'single') { btn.textContent = '📍 Точка';          btn.classList.add('active'); }
      if (_dlMode === 'multi')  { btn.textContent = '✦ Несколько дней'; btn.classList.add('active'); }
    }
    if (_dlMode !== 'multi') { _dlDates.clear(); }
    if (_dlMode === 'single' && _dlFrom) { _dlTo = _dlFrom; _dlPhase = 'from'; dlCalRender(); dlSave(); }
    else { dlCalRender(); dlUpdateBadge(); }
  }

  function dlCalPrev() { _dlViewMonth--; if (_dlViewMonth < 0){ _dlViewMonth=11; _dlViewYear--; } dlCalRender(); }
  function dlCalNext() { _dlViewMonth++; if (_dlViewMonth > 11){ _dlViewMonth=0; _dlViewYear++; } dlCalRender(); }

  function dlCalRender() {
    const rightYear  = _dlViewMonth === 11 ? _dlViewYear+1 : _dlViewYear;
    const rightMonth = (_dlViewMonth+1) % 12;

    document.getElementById('dl-cal-title-l').textContent =
      MONTH_RU[_dlViewMonth] + ' ' + _dlViewYear;
    document.getElementById('dl-cal-title-r').textContent =
      MONTH_RU[rightMonth] + ' ' + rightYear;

    const picked = _dlMode === 'multi' ? _dlDates : null;
    const from   = _dlMode === 'multi' ? null : _dlFrom;
    const to     = _dlMode === 'multi' ? null : _dlTo;

    renderCalGrid(document.getElementById('dl-cal-left'),  _dlViewYear, _dlViewMonth, from, to, dlOnDayClick, picked);
    renderCalGrid(document.getElementById('dl-cal-right'), rightYear, rightMonth,     from, to, dlOnDayClick, picked);
    dlUpdateBadge();
  }

  function dlOnDayClick(d) {
    if (_dlMode === 'multi') {
      const key = _dateKey(d);
      if (_dlDates.has(key)) _dlDates.delete(key);
      else _dlDates.add(key);
      dlCalRender();
      dlSave();
      return;
    }
    if (_dlMode === 'single') {
      _dlFrom = d; _dlTo = d; _dlPhase = 'from';
      dlCalRender(); dlSave();
      return;
    }
    if (_dlPhase === 'from') {
      _dlFrom  = d; _dlTo = null; _dlPhase = 'to';
    } else {
      if (d < _dlFrom) { _dlTo = _dlFrom; _dlFrom = d; }
      else              { _dlTo = d; }
      _dlPhase = 'from';
      dlSave();
    }
    dlCalRender();
  }

  function dlUpdateBadge() {
    const badge = document.getElementById('dl-range-badge');
    if (!badge) return;
    if (_dlMode === 'multi') {
      const n = _dlDates.size;
      if (n > 0) {
        badge.textContent = `✦ ${n} ${n===1?'день':n<5?'дня':'дней'}`;
        badge.style.background = 'var(--green-muted)';
        badge.style.color      = 'var(--green-dark)';
      } else {
        badge.textContent = 'выберите дни';
        badge.style.background = 'var(--surface2)';
        badge.style.color      = 'var(--text3)';
      }
      return;
    }
    if (_dlFrom && _dlTo) {
      const isSingle = _dateKey(_dlFrom) === _dateKey(_dlTo);
      badge.textContent = isSingle
        ? '📍 ' + _dateKey(_dlFrom)
        : _dateKey(_dlFrom) + '  —  ' + _dateKey(_dlTo);
      badge.style.background = 'var(--green-muted)';
      badge.style.color      = 'var(--green-dark)';
    } else if (_dlFrom) {
      badge.textContent = _dateKey(_dlFrom) + '  →  ?';
      badge.style.background = 'var(--surface2)';
      badge.style.color      = 'var(--text3)';
    } else {
      badge.textContent = 'выберите даты';
      badge.style.background = 'var(--surface2)';
      badge.style.color      = 'var(--text3)';
    }
  }

  function dlSave() {
    if (_dlMode === 'multi') {
      // Сохраняем sorted список дат
      const sorted = [..._dlDates].sort();
      const cfg = collectFormConfig();
      cfg.dl_mode = 'multi';
      cfg.dates_list = JSON.stringify(sorted);
      cfg.date_from = sorted[0] || null;
      cfg.date_to   = sorted[sorted.length - 1] || null;
      pywebview.api.save_config(cfg);
      pageProfileSyncActive('promodate');
      return;
    }
    if (!_dlFrom || !_dlTo) return;
    // Sync hidden fields for backward compat
    document.getElementById('sel-month-from').value = _dlFrom.getMonth()+1;
    document.getElementById('sel-year-from').value  = _dlFrom.getFullYear();
    document.getElementById('sel-month-to').value   = _dlTo.getMonth()+1;
    document.getElementById('sel-year-to').value    = _dlTo.getFullYear();
    const cfg = collectFormConfig();
    cfg.dl_mode   = _dlMode;
    cfg.date_from = _dateKey(_dlFrom);
    cfg.date_to   = _dateKey(_dlTo);
    cfg.dates_list = null;
    pywebview.api.save_config(cfg);
    pageProfileSyncActive('promodate');
  }

  function dlPreset(p) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth();
    if (p === 'today')      { _dlFrom = new Date(y,m,now.getDate()); _dlTo = new Date(y,m,now.getDate()); }
    else if (p === 'week')  {
      const dow = now.getDay() === 0 ? 6 : now.getDay()-1;
      _dlFrom = new Date(y,m,now.getDate()-dow);
      _dlTo   = new Date(y,m,now.getDate()-dow+6);
    }
    else if (p === 'month')      { _dlFrom = new Date(y,m,1); _dlTo = new Date(y,m+1,0); }
    else if (p === 'prev_month') { _dlFrom = new Date(y,m-1,1); _dlTo = new Date(y,m,0); }
    else if (p === 'quarter')    {
      const qm = Math.floor(m/3)*3;
      _dlFrom = new Date(y,qm,1); _dlTo = new Date(y,qm+3,0);
    }
    else if (p === 'year')       { _dlFrom = new Date(y,0,1); _dlTo = new Date(y,11,31); }
    _dlPhase = 'from';
    // Navigate to show selected range
    if (_dlFrom) { _dlViewYear = _dlFrom.getFullYear(); _dlViewMonth = _dlFrom.getMonth(); }
    dlCalRender();
    dlSave();
  }

  function _parseLocalDate(s) {
    // "YYYY-MM-DD" → Date в локальном часовом поясе (не UTC)
    if (!s) return null;
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  function dlCalInit(cfg) {
    // Восстановить режим
    if (cfg.dl_mode) {
      _dlMode = cfg.dl_mode;
      const btn = document.getElementById('dl-mode-btn');
      if (btn) {
        if (_dlMode === 'range')  { btn.textContent = '↔ Диапазон';      btn.classList.remove('active'); }
        if (_dlMode === 'single') { btn.textContent = '📍 Точка';          btn.classList.add('active'); }
        if (_dlMode === 'multi')  { btn.textContent = '✦ Несколько дней'; btn.classList.add('active'); }
      }
    }
    // Восстановить multi-даты
    if (_dlMode === 'multi' && cfg.dates_list) {
      try { JSON.parse(cfg.dates_list).forEach(k => _dlDates.add(k)); } catch(e) {}
    }
    // Restore from config — парсим в локальном TZ, иначе UTC смещает дату
    if (cfg.date_from && cfg.date_to && _dlMode !== 'multi') {
      _dlFrom = _parseLocalDate(cfg.date_from);
      _dlTo   = _parseLocalDate(cfg.date_to);
      if (_dlFrom) { _dlViewYear = _dlFrom.getFullYear(); _dlViewMonth = _dlFrom.getMonth(); }
    } else if (_dlMode !== 'multi') {
      const now = new Date();
      _dlFrom = new Date(now.getFullYear(), now.getMonth(), 1);
      _dlTo   = new Date(now.getFullYear(), now.getMonth()+1, 0);
      _dlViewYear  = now.getFullYear();
      _dlViewMonth = now.getMonth();
    }
    dlCalRender();
  }

  // ══════════════════════════════════════════════════════════════════════
  // DRAWER — ОДНОМЕСЯЧНЫЙ КАЛЕНДАРЬ ДИАПАЗОНА ДАТ
  // ══════════════════════════════════════════════════════════════════════

  let _scViewYear  = new Date().getFullYear();
  let _scViewMonth = new Date().getMonth();
  let _scFrom = null;
  let _scTo   = null;
  let _scPhase = 'from';

  function schedCalPrev() { _scViewMonth--; if(_scViewMonth<0){_scViewMonth=11;_scViewYear--;} schedCalRender(); }
  function schedCalNext() { _scViewMonth++; if(_scViewMonth>11){_scViewMonth=0;_scViewYear++;} schedCalRender(); }

  // Keep old name aliases for backward compat
  function schedCalPrevYear() { schedCalPrev(); }
  function schedCalNextYear() { schedCalNext(); }

  function schedCalRender() {
    const titleEl = document.getElementById('sched-cal-title');
    if (titleEl) titleEl.textContent = MONTH_RU[_scViewMonth] + ' ' + _scViewYear;
    const grid = document.getElementById('sched-cal-grid');
    if (!grid) return;
    renderCalGrid(grid, _scViewYear, _scViewMonth, _scFrom, _scTo, schedCalDayClick);

    const disp = document.getElementById('sched-range-display');
    if (!disp) return;
    if (_scFrom && _scTo) {
      disp.textContent = _dateKey(_scFrom) + '  —  ' + _dateKey(_scTo);
      disp.style.background = 'var(--green-muted)'; disp.style.color = 'var(--green-dark)';
    } else if (_scFrom) {
      disp.textContent = _dateKey(_scFrom) + '  →  выберите конец';
      disp.style.background = 'var(--surface2)'; disp.style.color = 'var(--text3)';
    } else {
      disp.textContent = 'Выберите начало диапазона';
      disp.style.background = 'var(--surface2)'; disp.style.color = 'var(--text3)';
    }
  }

  function schedCalDayClick(d) {
    if (_scPhase === 'from') {
      _scFrom = d; _scTo = null; _scPhase = 'to';
    } else {
      if (d < _scFrom) { _scTo = _scFrom; _scFrom = d; }
      else              { _scTo = d; }
      _scPhase = 'from';
      schedSave();
    }
    schedCalRender();
  }

  // Keep old sched cal compat
  function schedCalClick(m, y) {
    // Not used in day mode
  }