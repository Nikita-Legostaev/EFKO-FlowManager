/* ═══════════════════════════════════════════════════════════════════════
 * addons.js — надстройка интерфейса EFKO FlowManager
 *
 * Подключается ОДНОЙ строкой в конце web/index.html, сразу после app.js:
 *     <script src="app.js"></script>
 *     <script src="addons.js"></script>   ← добавить эту
 *
 * Сам дорисовывает в существующий интерфейс:
 *   • кнопку «⚙️ Сделать CSV» на главном экране (только обработка xlsx → CSV);
 *   • кнопку «Проверить обновления» в сайдбаре + уведомление о новой версии;
 *   • вкладку «Парсинг ЖДСК» со списком сетей, справкой и вводом API-ключей.
 *
 * index.html и app.js править больше не нужно — вся разметка и логика здесь.
 * Требует методов бэкенда: start_process_csv, check_updates_manual,
 * install_update_now, get_parsing_config, browse_parsing_output,
 * get_parser_help, get_parser_key, save_parser_key, open_key_url,
 * run_parser_one, run_parser_batch, open_parsing_folder.
 * ═══════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── Утилиты ──────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  function toast(type, msg) {
    if (typeof showToast === 'function') showToast(type, msg);
    else console.log(type, msg);
  }
  function log(msg) {
    if (typeof addLog === 'function') addLog(msg);
  }
  function api() {
    return (window.pywebview && window.pywebview.api) || null;
  }

  // ═════════════════════════════════════════════════════════════════════
  // РАЗМЕТКА
  // ═════════════════════════════════════════════════════════════════════

  function injectStyles() {
    const css = document.createElement('style');
    css.textContent = `
      .pz-card{display:flex;align-items:center;gap:8px;padding:10px 12px;
        border-radius:10px;border:1.5px solid var(--border);
        background:var(--surface2);transition:border-color .15s}
      .pz-card.sel{border-color:var(--green,#1e8c42)}
      .pz-card.missing{opacity:.45}
      .pz-name{font-size:13px;font-weight:600;color:var(--text);
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .pz-sub{font-size:10px;color:var(--text3);overflow:hidden;
        text-overflow:ellipsis;white-space:nowrap}
      .pz-mini{width:24px;height:24px;border-radius:50%;
        border:1px solid var(--border2);background:none;color:var(--text3);
        font-size:11px;font-weight:700;cursor:pointer;flex-shrink:0;
        display:flex;align-items:center;justify-content:center}
      .pz-mini:hover{border-color:var(--green,#1e8c42);color:var(--green,#1e8c42)}
      .pz-mini.key-off{border-color:var(--orange,#e08b2a)}
      .pz-mini.key-on{border-color:var(--green,#1e8c42)}
      .pz-run{width:26px;height:26px;border-radius:8px;border:none;
        background:var(--green-muted,#e7f5ec);color:var(--green-dark,#186b34);
        font-size:12px;cursor:pointer;flex-shrink:0}
      .pz-run:disabled{opacity:.4;cursor:default}
      .pz-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);
        z-index:1000;align-items:center;justify-content:center}
      .pz-modal{background:var(--surface);border-radius:12px;width:580px;
        max-width:92vw;max-height:85vh;display:flex;flex-direction:column;
        box-shadow:0 8px 40px rgba(0,0,0,.4)}
      .pz-modal-hd{padding:16px 20px;border-bottom:1px solid var(--border);
        display:flex;align-items:center;gap:10px}
      .pz-modal-bd{padding:18px 20px;overflow-y:auto;flex:1;font-size:13px;
        line-height:1.6;color:var(--text2)}
      .pz-x{margin-left:auto;background:none;border:none;color:var(--text3);
        font-size:20px;cursor:pointer;line-height:1}
    `;
    document.head.appendChild(css);
  }

  function injectNavItem() {
    const nav = document.querySelector('.sb-nav');
    if (!nav || $('nav-parsing')) return;
    const btn = document.createElement('button');
    btn.className = 'nav-item';
    btn.id = 'nav-parsing';
    btn.dataset.page = 'parsing';
    btn.innerHTML = '<span class="nav-icon">🕸</span> Парсинг ЖДСК';
    btn.addEventListener('click', () => navigate('parsing'));
    nav.appendChild(btn);
  }

  function injectUpdateButton() {
    const footer = document.querySelector('.sb-footer');
    if (!footer || $('update-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'nav-item';
    btn.id = 'update-btn';
    btn.style.fontSize = '12px';
    btn.innerHTML =
      '<span class="nav-icon" id="update-icon">⬆️</span>' +
      '<span id="update-label">Проверить обновления</span>';
    btn.addEventListener('click', () => checkUpdates(false));
    const themeBtn = $('theme-btn');
    if (themeBtn) footer.insertBefore(btn, themeBtn);
    else footer.appendChild(btn);
  }

  function injectCsvButton() {
    const bar = $('bar-promodate');
    if (!bar || $('promo-csv-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost';
    btn.id = 'promo-csv-btn';
    btn.title = 'Только обработка: xlsx из «Скаченное» → CSV. Без FTP, Query и макросов';
    btn.textContent = '⚙️ Сделать CSV';
    btn.addEventListener('click', promoMakeCsv);
    // ставим перед «▶ Запустить»
    const primary = bar.querySelector('.btn-primary');
    if (primary) bar.insertBefore(btn, primary);
    else bar.appendChild(btn);
  }

  function injectParsingPane() {
    const scroll = $('scroll-area');
    if (!scroll || $('pane-parsing')) return;
    const pane = document.createElement('div');
    pane.className = 'pane';
    pane.id = 'pane-parsing';
    pane.innerHTML = `
      <div class="card">
        <div class="card-section">
          <span class="card-section-icon">📂</span>
          <span class="card-section-title">Куда сохранять результаты</span>
          <span id="pz-folder-badge" style="margin-left:auto;font-size:11px;
                font-weight:600;padding:2px 10px;border-radius:20px;
                background:var(--surface2);color:var(--text3)">проверяю…</span>
        </div>
        <div class="card-body">
          <div class="form-row">
            <label class="form-label">Папка для Excel по сетям:</label>
            <input class="form-input" type="text" id="pz-folder" readonly
                   placeholder="Выберите папку — например, C:\\Парсинг">
            <button class="form-btn-pick" id="pz-pick">Обзор</button>
            <button class="form-btn-clear" id="pz-reload" title="Обновить список">↻</button>
          </div>
          <div style="font-size:11px;color:var(--text3);margin-top:4px">
            По каждой сети создаётся свой Excel. Туда же складываются кэши и
            чекпоинты — повторный запуск за счёт них идёт быстрее, поэтому
            папку лучше не чистить. Сами скрипты входят в состав приложения и
            обновляются вместе с ним.
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-section">
          <span class="card-section-icon">🕸</span>
          <span class="card-section-title">Сети</span>
          <span style="margin-left:auto;display:flex;gap:6px">
            <button class="cal-preset" id="pz-all">Выбрать все</button>
            <button class="cal-preset" id="pz-none">Снять</button>
          </span>
        </div>
        <div class="card-body">
          <div id="pz-list" style="display:grid;
               grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px">
            <span style="color:var(--text3);font-size:12px;grid-column:1/-1">Загрузка…</span>
          </div>
        </div>
      </div>`;
    // перед карточкой лога, чтобы лог остался внизу
    const logCard = $('log-card');
    if (logCard) scroll.insertBefore(pane, logCard);
    else scroll.appendChild(pane);

    $('pz-pick').addEventListener('click', pickFolder);
    $('pz-reload').addEventListener('click', () => loadParsers(true));
    $('pz-all').addEventListener('click', () => selectAll(true));
    $('pz-none').addEventListener('click', () => selectAll(false));
  }

  function injectParsingBar() {
    const bar = $('action-bar');
    if (!bar || $('bar-parsing')) return;
    const g = document.createElement('div');
    g.id = 'bar-parsing';
    g.className = 'bar-group';
    g.style.cssText = 'display:none;align-items:center;gap:8px;width:100%';
    g.innerHTML = `
      <button class="btn btn-ghost" id="pz-open-folder">📁 Открыть результаты</button>
      <div class="action-spacer"></div>
      <span id="pz-status" style="font-size:12px;color:var(--text3)"></span>
      <button class="btn btn-primary" id="pz-run-sel">▶ Запустить выбранные</button>
      <button class="btn btn-danger" id="pz-stop">■ Стоп</button>`;
    bar.appendChild(g);

    $('pz-open-folder').addEventListener('click', () => api() && api().open_parsing_folder());
    $('pz-run-sel').addEventListener('click', runSelected);
    $('pz-stop').addEventListener('click', () => {
      if (typeof stopAction === 'function') stopAction();
    });
  }

  function injectModals() {
    if ($('pz-help-overlay')) return;

    const help = document.createElement('div');
    help.id = 'pz-help-overlay';
    help.className = 'pz-overlay';
    help.innerHTML = `
      <div class="pz-modal">
        <div class="pz-modal-hd">
          <span style="font-size:18px">❔</span>
          <span id="pz-help-title" style="font-weight:600;font-size:15px"></span>
          <button class="pz-x" id="pz-help-x">✕</button>
        </div>
        <div class="pz-modal-bd" id="pz-help-body" style="white-space:pre-wrap"></div>
        <div style="padding:12px 20px;border-top:1px solid var(--border);text-align:right">
          <button class="btn btn-ghost" id="pz-help-close">Закрыть</button>
        </div>
      </div>`;
    document.body.appendChild(help);

    const key = document.createElement('div');
    key.id = 'pz-key-overlay';
    key.className = 'pz-overlay';
    key.innerHTML = `
      <div class="pz-modal">
        <div class="pz-modal-hd">
          <span style="font-size:18px">🔑</span>
          <span id="pz-key-title" style="font-weight:600;font-size:15px"></span>
          <button class="pz-x" id="pz-key-x">✕</button>
        </div>
        <div class="pz-modal-bd">
          <div style="font-size:11px;color:var(--text3);margin-bottom:6px" id="pz-key-env"></div>
          <div style="display:flex;gap:8px;align-items:center">
            <input id="pz-key-input" class="form-input" type="text" spellcheck="false"
                   placeholder="Вставьте ключ сюда"
                   style="flex:1;font-family:monospace">
            <button class="btn btn-primary" id="pz-key-save">Сохранить</button>
          </div>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-ghost" id="pz-key-site">🌐 Открыть сайт</button>
            <button class="btn btn-ghost" id="pz-key-clear">🗑 Удалить ключ</button>
          </div>
          <div id="pz-key-help" style="margin-top:14px;padding-top:14px;
               border-top:1px solid var(--border);white-space:pre-wrap"></div>
        </div>
      </div>`;
    document.body.appendChild(key);

    const closeHelp = () => { help.style.display = 'none'; };
    const closeKey = () => { key.style.display = 'none'; };
    $('pz-help-x').addEventListener('click', closeHelp);
    $('pz-help-close').addEventListener('click', closeHelp);
    help.addEventListener('click', e => { if (e.target === help) closeHelp(); });
    $('pz-key-x').addEventListener('click', closeKey);
    key.addEventListener('click', e => { if (e.target === key) closeKey(); });
    $('pz-key-save').addEventListener('click', saveKey);
    $('pz-key-clear').addEventListener('click', clearKey);
    $('pz-key-site').addEventListener('click', () => {
      if (K.url && api()) api().open_key_url(K.url);
    });
    $('pz-key-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') saveKey();
    });
  }

  // ═════════════════════════════════════════════════════════════════════
  // 1. КНОПКА «СДЕЛАТЬ CSV»
  // ═════════════════════════════════════════════════════════════════════

  async function promoMakeCsv() {
    const cat = getField('category');
    const out = getField('output_folder');
    if (!cat) { toast('warning', 'Выберите категорию'); return; }
    if (!out) { toast('warning', 'Укажите папку сохранения CSV'); return; }

    const btn = $('promo-csv-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Обрабатываю…'; }

    try {
      await api().save_config(collectFormConfig());
      if (typeof showProgress === 'function') showProgress();
      log(`⚙️ Обработка в CSV — категория «${cat}»`);
      await api().start_process_csv({
        output_folder: out,
        category: cat,
        networks: (typeof getSelectedNetworks === 'function') ? getSelectedNetworks() : null,
      });
    } catch (e) {
      toast('error', 'Не удалось запустить обработку: ' + e);
      if (typeof hideProgress === 'function') hideProgress();
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⚙️ Сделать CSV'; }
    }
  }

  // ═════════════════════════════════════════════════════════════════════
  // 2. ОБНОВЛЕНИЯ
  // ═════════════════════════════════════════════════════════════════════

  async function checkUpdates(silent) {
    const label = $('update-label'), icon = $('update-icon');
    if (label && !silent) label.textContent = 'Проверяю…';
    try {
      const info = await api().check_updates_manual();
      if (!info.ok) {
        if (!silent) toast('warning', info.msg || 'Папка обновлений недоступна');
        if (label) label.textContent = 'Проверить обновления';
        return;
      }
      if (!info.available) {
        if (!silent) toast('success', `Установлена последняя версия (${info.current})`);
        if (label) label.textContent = `Версия ${info.current}`;
        if (icon) icon.textContent = '✅';
        return;
      }
      onUpdateAvailable(info);
    } catch (e) {
      if (!silent) toast('error', 'Ошибка проверки обновлений');
      if (label) label.textContent = 'Проверить обновления';
    }
  }

  function onUpdateAvailable(info) {
    const label = $('update-label'), icon = $('update-icon');
    if (label) label.textContent = `Обновить до ${info.remote}`;
    if (icon) icon.textContent = '🆕';

    const text =
      `Доступна новая версия ${info.remote} (у вас ${info.current}).\n\n` +
      (info.notes ? `Что нового:\n${info.notes}\n\n` : '') +
      `Обновить сейчас? Приложение закроется и запустится заново.`;
    if (!confirm(text)) return;

    api().install_update_now().then(res => {
      if (res && !res.ok) toast('error', res.msg || 'Не удалось обновиться');
    });
  }

  // ═════════════════════════════════════════════════════════════════════
  // 3. ВКЛАДКА ПАРСИНГА
  // ═════════════════════════════════════════════════════════════════════

  const P = { parsers: [], selected: new Set(), loaded: false, running: false };
  const K = { parserKey: '', envKey: '', url: '' };

  async function loadParsers(force) {
    if (P.loaded && !force) return;
    const list = $('pz-list');
    if (list) list.innerHTML =
      '<span style="color:var(--text3);font-size:12px;grid-column:1/-1">Загрузка…</span>';
    try {
      const cfg = await api().get_parsing_config();
      applyParsingConfig(cfg);
      P.loaded = true;
    } catch (e) {
      if (list) list.innerHTML =
        '<span style="color:var(--red);font-size:12px;grid-column:1/-1">' +
        'Не удалось получить список парсеров</span>';
      setFolderBadge('', false, 0);
    }
  }

  function applyParsingConfig(cfg) {
    if (!cfg) return;
    P.parsers = cfg.parsers || [];
    const inp = $('pz-folder');
    if (inp) inp.value = cfg.output || '';
    setFolderBadge(cfg.output, cfg.scripts_ok, P.parsers.length);
    // выкидываем из выбора то, чего больше нет
    P.selected = new Set([...P.selected].filter(k => P.parsers.some(p => p.key === k)));
    render();
  }

  async function pickFolder() {
    const a = api();
    if (!a) { toast('error', 'Связь с приложением не готова, подождите пару секунд'); return; }

    try {
      let cfg = null;

      if (typeof a.browse_parsing_output === 'function') {
        cfg = await a.browse_parsing_output();
      } else if (typeof a.browse_folder === 'function') {
        // Запасной путь: метода вкладки нет (старый бэкенд) — берём общий
        // диалог выбора папки и сохраняем путь отдельным вызовом.
        console.warn('browse_parsing_output отсутствует, использую browse_folder');
        const path = await a.browse_folder();
        if (!path) return;                       // пользователь нажал «Отмена»
        if (typeof a.save_parsing_output === 'function') {
          cfg = await a.save_parsing_output(path);
        } else {
          const inp = $('pz-folder');
          if (inp) inp.value = path;
          toast('warning', 'Путь показан, но сохранить его не удалось — ' +
                           'обновите api_parsing.py');
          return;
        }
      } else {
        toast('error', 'В приложении нет метода выбора папки — ' +
                       'проверьте, что api_parsing.py подключён в app.py');
        return;
      }

      if (cfg) { applyParsingConfig(cfg); P.loaded = true; }
    } catch (e) {
      console.error('pickFolder', e);
      toast('error', 'Не удалось выбрать папку: ' + (e && e.message ? e.message : e));
      if (a.js_error) { try { a.js_error('pickFolder: ' + e); } catch (_) {} }
    }
  }

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
    return many;
  }

  function setFolderBadge(output, scriptsOk, n) {
    const b = $('pz-folder-badge');
    if (!b) return;
    if (!scriptsOk || !n) {
      b.textContent = '⚠ скрипты не найдены в сборке';
      b.style.background = 'var(--surface2)';
      b.style.color = 'var(--red)';
    } else if (!output) {
      b.textContent = '⚠ выберите папку результатов';
      b.style.background = 'var(--surface2)';
      b.style.color = 'var(--orange, #e08b2a)';
    } else {
      b.textContent = `✅ ${n} ${plural(n, 'сеть', 'сети', 'сетей')} готовы к запуску`;
      b.style.background = 'var(--green-muted)';
      b.style.color = 'var(--green-dark)';
    }
  }

  function render() {
    const list = $('pz-list');
    if (!list) return;
    if (!P.parsers.length) {
      list.innerHTML =
        '<span style="color:var(--text3);font-size:12px;grid-column:1/-1">' +
        'Скрипты парсинга не найдены в сборке приложения. ' +
        'Проверьте, что папка parsers/ попала в сборку.</span>';
      return;
    }
    list.innerHTML = '';

    P.parsers.forEach(p => {
      const sel = P.selected.has(p.key);
      const card = document.createElement('div');
      card.className = 'pz-card' + (sel ? ' sel' : '') + (p.exists ? '' : ' missing');

      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = sel;
      chk.disabled = !p.exists || P.running;
      chk.addEventListener('change', () => {
        if (chk.checked) P.selected.add(p.key); else P.selected.delete(p.key);
        render();
      });

      const title = document.createElement('div');
      title.style.cssText = 'flex:1;min-width:0';
      const marks = [];
      if (!p.exists) marks.push('файла нет');
      if (!p.known) marks.push('не в реестре');
      if (p.needs_key && !p.key_set) marks.push('<span style="color:var(--orange)">нужен ключ</span>');
      title.innerHTML =
        `<div class="pz-name">${p.icon || '🏬'} ${esc(p.name)}</div>` +
        `<div class="pz-sub">${esc(p.script)}${marks.length ? ' · ' + marks.join(' · ') : ''}</div>`;

      card.appendChild(chk);
      card.appendChild(title);

      if (p.needs_key) {
        const kb = document.createElement('button');
        kb.className = 'pz-mini ' + (p.key_set ? 'key-on' : 'key-off');
        kb.textContent = '🔑';
        kb.title = p.key_set ? 'Ключ задан — нажмите, чтобы изменить'
                             : 'Нужен API-ключ — нажмите, чтобы указать';
        kb.addEventListener('click', e => { e.stopPropagation(); openKey(p.key); });
        card.appendChild(kb);
      }

      const hb = document.createElement('button');
      hb.className = 'pz-mini';
      hb.textContent = '?';
      hb.title = 'Инструкция по этой сети';
      hb.addEventListener('click', e => { e.stopPropagation(); openHelp(p.key); });
      card.appendChild(hb);

      const rb = document.createElement('button');
      rb.className = 'pz-run';
      rb.textContent = '▶';
      rb.title = 'Запустить только эту сеть';
      rb.disabled = !p.exists || P.running;
      rb.addEventListener('click', e => { e.stopPropagation(); runOne(p.key); });
      card.appendChild(rb);

      list.appendChild(card);
    });
  }

  function selectAll(on) {
    P.selected.clear();
    if (on) P.parsers.filter(p => p.exists).forEach(p => P.selected.add(p.key));
    render();
  }

  // ── Справка ──────────────────────────────────────────────────────────

  async function openHelp(key) {
    const info = await api().get_parser_help(key);
    $('pz-help-title').textContent = info.name + (info.script ? ` · ${info.script}` : '');
    let body = info.help || '';
    if (info.outputs && info.outputs.length) {
      body += `\n\nФайлы результата:\n• ${info.outputs.join('\n• ')}`;
    }
    $('pz-help-body').textContent = body;
    $('pz-help-overlay').style.display = 'flex';
  }

  // ── Ключи ────────────────────────────────────────────────────────────

  async function openKey(key) {
    const info = await api().get_parser_key(key);
    if (!info || !info.ok) {
      toast('error', (info && info.msg) || 'Не удалось открыть настройки ключа');
      return;
    }
    K.parserKey = key;
    K.envKey = info.env_key || '';
    K.url = info.key_url || '';

    $('pz-key-title').textContent = `${info.key_title} — ${info.name}`;
    $('pz-key-env').textContent = K.envKey ? `Переменная окружения: ${K.envKey}` : '';
    $('pz-key-input').value = info.value || '';
    $('pz-key-help').textContent = info.key_help || '';
    $('pz-key-site').style.display = K.url ? '' : 'none';
    $('pz-key-overlay').style.display = 'flex';
    setTimeout(() => $('pz-key-input').focus(), 50);
  }

  async function saveKey() {
    const value = $('pz-key-input').value.trim();
    if (!value) { toast('warning', 'Поле ключа пустое'); return; }
    const res = await api().save_parser_key({ env_key: K.envKey, value });
    if (res && res.ok) {
      $('pz-key-overlay').style.display = 'none';
      loadParsers(true);
    }
  }

  async function clearKey() {
    if (!confirm('Удалить сохранённый ключ?')) return;
    await api().save_parser_key({ env_key: K.envKey, value: '' });
    $('pz-key-input').value = '';
    $('pz-key-overlay').style.display = 'none';
    loadParsers(true);
  }

  // ── Запуск ───────────────────────────────────────────────────────────

  async function runOne(key) {
    if (P.running) { toast('warning', 'Парсер уже выполняется'); return; }
    if (!requireOutput()) return;
    const p = P.parsers.find(x => x.key === key);
    if (p && p.needs_key && !p.key_set) {
      const goSetKey = confirm(
        `Для «${p.name}» не задан API-ключ.\n\n` +
        `Без него скрипт вернёт ошибку авторизации или неполные данные.\n\n` +
        `OK — указать ключ сейчас\nОтмена — запустить всё равно`);
      if (goSetKey) { openKey(key); return; }
    }
    await api().run_parser_one({ key });
  }

  function requireOutput() {
    const v = ($('pz-folder') || {}).value || '';
    if (!v) {
      toast('warning', 'Сначала выберите папку для сохранения результатов');
      const btn = $('pz-pick');
      if (btn) btn.focus();
      return false;
    }
    return true;
  }

  async function runSelected() {
    if (P.running) { toast('warning', 'Парсер уже выполняется'); return; }
    if (!requireOutput()) return;
    const keys = [...P.selected];
    if (!keys.length) { toast('warning', 'Отметьте хотя бы одну сеть'); return; }

    const noKey = P.parsers.filter(p => keys.includes(p.key) && p.needs_key && !p.key_set);
    let warn = '';
    if (noKey.length) {
      warn = `\n\nБез API-ключа: ${noKey.map(p => p.name).join(', ')} — ` +
             `эти сети вернут ошибку или неполные данные.`;
    }
    if (!confirm(
        `Запустить ${keys.length} ${keys.length === 1 ? 'парсер' : 'парсеров'} подряд?\n\n` +
        `Они выполняются последовательно и в сумме могут идти очень долго.${warn}`)) return;

    await api().run_parser_batch({ keys });
  }

  function setRunning(on, label) {
    P.running = on;
    const btn = $('pz-run-sel'), st = $('pz-status');
    if (btn) {
      btn.disabled = on;
      btn.textContent = on ? '⏳ Выполняется…' : '▶ Запустить выбранные';
    }
    if (st) st.textContent = label || '';
    render();
  }

  // ═════════════════════════════════════════════════════════════════════
  // ИНТЕГРАЦИЯ С ПРИЛОЖЕНИЕМ
  // ═════════════════════════════════════════════════════════════════════

  // Навигация: оборачиваем штатную navigate(), не трогая app.js
  function hookNavigation() {
    if (typeof window.navigate !== 'function') return;
    const orig = window.navigate;
    window.navigate = function (page) {
      orig(page);
      if (page !== 'parsing') return;
      document.querySelectorAll('.bar-group').forEach(g => g.style.display = 'none');
      const bar = $('bar-parsing');
      if (bar) bar.style.display = 'flex';
      const title = $('page-title');
      if (title) title.textContent = 'Парсинг ЖДСК';
      loadParsers(false);
    };
  }

  // События из Python: подписываемся поверх существующего обработчика
  function hookEvents() {
    const prev = window.__pyEvent || function () {};
    window.__pyEvent = function (payload) {
      try {
        if (payload && payload.type === 'update_available') {
          onUpdateAvailable(payload.data);
          return;
        }
        if (payload && payload.type === 'parse_started') {
          setRunning(true, 'идёт сбор данных…');
          if (typeof showProgress === 'function') showProgress();
          return;
        }
        if (payload && payload.type === 'parse_done') {
          setRunning(false, '');
          if (typeof hideProgress === 'function') hideProgress();
          const outs = payload.data && payload.data.outputs;
          if (outs && outs.length) {
            log('📂 Готовые файлы: ' +
                outs.map(o => String(o).split('\\').pop()).join(', '));
          }
          loadParsers(true);
          return;
        }
      } catch (e) {
        console.error('addons __pyEvent', e);
      }
      prev(payload);
    };
  }

  // Молчаливо падающие промисы — главная причина «кнопка ничего не делает».
  // Выводим их в консоль и в лог приложения, чтобы было видно причину.
  function hookErrors() {
    window.addEventListener('unhandledrejection', function (e) {
      const msg = 'JS promise: ' + (e.reason && e.reason.message ? e.reason.message : e.reason);
      console.error(msg);
      const a = api();
      if (a && a.js_error) { try { a.js_error(msg); } catch (_) {} }
    });
  }

  function build() {
    hookErrors();
    injectStyles();
    injectNavItem();
    injectUpdateButton();
    injectCsvButton();
    injectParsingPane();
    injectParsingBar();
    injectModals();
    hookNavigation();
    hookEvents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }

  // Экспорт наружу — чтобы можно было дёрнуть из консоли или onclick
  window.promoMakeCsv = promoMakeCsv;
  window.checkUpdates = checkUpdates;
  window.parsingLoad = loadParsers;
  window.parsingRunOne = runOne;
  window.parsingKeyOpen = openKey;
})();