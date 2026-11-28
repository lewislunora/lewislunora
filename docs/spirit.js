/*!
 * AI 精靈 — 單檔、零依賴、按需建立 DOM。
 * 意圖在前端用關鍵字判讀，不打額外 LLM；所有能力都复用既有 API。
 * 公開功能免登入；私人功能由後端回 401，不自行判斷身份。
 */
(function () {
  'use strict';
  if (window.__spiritLoaded) return;
  window.__spiritLoaded = true;

  var API = /\.github\.io/i.test(location.hostname)
    ? 'https://lewislunora.onrender.com'
    : location.origin;

  // 唯一功能白名單：AI 永不為自己編造能力。
  var CAPS = [
    ['🧮 計算', '/計算 (1+2)*3'],
    ['📝 筆記', '/筆記 內容｜列表｜刪除 3（需登入）'],
    ['⏰ 提醒', '/提醒 30分鐘後 喝水｜列表｜取消 3（需登入）'],
    ['🎤 語音', '點 💿 上傳音訊轉文字（需登入）'],
    ['🌐 搜尋', '/搜尋 gov:空氣品質'],
    ['🌍 翻譯', '/翻譯 en:你好（需登入）'],
    ['💡 靈感', '/靈感 一人公司'],
    ['🖼️ 生圖', '/生圖 一隻貓（需登入）'],
    ['📊 狀態', '/狀態'],
    ['❓ 協助', '/help']
  ];
  var HELP = '✨ 我只會這些：\n' + CAPS.map(function (c) {
    return c[0] + ' ' + c[1];
  }).join('\n');

  var S = { panel: null, open: false, busy: false, status: null, statusAt: 0, history: [] };

  var CSS = [
    '#spiritBubble{position:fixed;bottom:1.5rem;right:1.5rem;z-index:10001;width:52px;height:52px;border-radius:50%;',
    'border:1px solid rgba(255,255,255,.22);background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;',
    'font-size:1.35rem;cursor:pointer;box-shadow:0 6px 24px rgba(0,212,255,.35);transition:transform .2s}',
    '#spiritBubble:hover{transform:scale(1.08)}',
    '#spiritBubble::after{content:"";position:absolute;inset:-4px;border-radius:50%;border:1px solid rgba(0,212,255,.35)}',
    '.spirit-panel{position:fixed;bottom:5.2rem;right:1.5rem;z-index:10000;width:min(370px,calc(100vw - 2rem));height:min(540px,78vh);',
    'display:flex;flex-direction:column;overflow:hidden;border-radius:18px;background:rgba(16,21,48,.97);',
    'border:1px solid rgba(255,255,255,.12);box-shadow:0 12px 50px rgba(0,0,0,.5);backdrop-filter:blur(16px);color:#e8ecf4}',
    '.spirit-panel[hidden]{display:none}',
    '.spirit-head{padding:.8rem 1rem;display:flex;align-items:center;justify-content:space-between;',
    'border-bottom:1px solid rgba(255,255,255,.08);background:linear-gradient(135deg,rgba(0,212,255,.1),rgba(123,104,238,.1))}',
    '.spirit-title{font-size:.95rem;font-weight:700}.spirit-title small{font-weight:400;font-size:.65rem;color:rgba(255,255,255,.45);margin-left:.4rem}',
    '.spirit-x{background:none;border:none;color:rgba(255,255,255,.5);font-size:1.1rem;cursor:pointer}',
    '.spirit-chips{display:flex;gap:.35rem;flex-wrap:wrap;padding:.6rem .8rem .2rem}',
    '.spirit-chips button{font-size:.7rem;padding:.28rem .55rem;border-radius:12px;cursor:pointer;',
    'background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.2);color:#8ee9ff}',
    '.spirit-chips button:hover{background:rgba(0,212,255,.2)}',
    '.spirit-msgs{flex:1;overflow-y:auto;padding:.7rem .8rem;display:flex;flex-direction:column;gap:.5rem;font-size:.85rem;line-height:1.55}',
    '.spirit-msg{max-width:90%;padding:.5rem .75rem;border-radius:12px;white-space:pre-wrap;word-break:break-word;animation:spiritIn .18s ease-out}',
    '@keyframes spiritIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}',
    '.spirit-msg.ai{align-self:flex-start;background:rgba(255,255,255,.07);border-bottom-left-radius:4px}',
    '.spirit-msg.me{align-self:flex-end;background:linear-gradient(135deg,rgba(0,212,255,.22),rgba(123,104,238,.22));border-bottom-right-radius:4px}',
    '.spirit-msg img{display:block;max-width:100%;border-radius:8px;margin-top:.5rem}',
    '.spirit-form{display:flex;gap:.4rem;padding:.7rem .8rem;border-top:1px solid rgba(255,255,255,.08)}',
    '.spirit-form input[type=text]{flex:1;min-width:0;padding:.55rem .8rem;border-radius:20px;outline:none;',
    'background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);color:#fff;font-size:.85rem}',
    '.spirit-form input[type=text]:focus{border-color:rgba(0,212,255,.5)}',
    '.spirit-form button{border:none;cursor:pointer;color:#fff;border-radius:50%;width:36px;height:36px;flex:none}',
    '.spirit-mic{background:rgba(255,255,255,.08)}.spirit-send{background:linear-gradient(135deg,#00d4ff,#7b68ee)}',
    '.spirit-form button:disabled{opacity:.45;cursor:default}',
    '@media(max-width:480px){.spirit-panel{bottom:4.6rem;right:.6rem;left:.6rem;width:auto;height:70vh}#spiritBubble{right:1rem;bottom:1rem}}',
    '@media(prefers-color-scheme:light){.spirit-panel{background:rgba(250,251,255,.98);color:#1a1a2e}',
    '.spirit-msg.ai{background:rgba(26,26,46,.07)}.spirit-form input[type=text]{color:#1a1a2e}}'
  ].join('\n');

  function inject() {
    var st = document.createElement('style');
    st.id = 'spiritStyle';
    st.textContent = CSS;
    document.head.appendChild(st);

    // 舊版客服氣泡由本精靈取代，避免兩個按鈕重疊。
    ['chatBubble', 'chatPanel'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });

    var bubble = document.createElement('button');
    bubble.id = 'spiritBubble';
    bubble.type = 'button';
    bubble.title = 'AI 精靈（輸入 /help 看功能）';
    bubble.setAttribute('aria-label', '開啟 AI 精靈');
    bubble.textContent = '✨';
    bubble.addEventListener('click', function () { toggle(!S.open); });
    document.body.appendChild(bubble);
  }

  function build() {
    if (S.panel) return S.panel;
    var p = document.createElement('div');
    p.id = 'spiritPanel';
    p.className = 'spirit-panel';
    p.hidden = true;
    p.setAttribute('role', 'dialog');
    p.setAttribute('aria-label', 'AI 精靈');
    p.innerHTML =
      '<div class="spirit-head"><span class="spirit-title">✨ AI 精靈<small>最小資源・最大功能</small></span>' +
      '<button type="button" class="spirit-x" aria-label="關閉">✕</button></div>' +
      '<div class="spirit-chips"></div><div class="spirit-msgs" aria-live="polite"></div>' +
      '<form class="spirit-form"><button type="button" class="spirit-mic" title="語音轉文字">💿</button>' +
      '<input type="text" maxlength="500" autocomplete="off" placeholder="問我，或輸入 /help">' +
      '<button type="submit" class="spirit-send" aria-label="送出">➤</button></form>' +
      '<input type="file" accept="audio/*" hidden>';
    document.body.appendChild(p);
    S.panel = p;

    p.querySelector('.spirit-x').addEventListener('click', function () { toggle(false); });
    var chips = [
      ['🧮 計算', '計算 (1+2)*3'], ['📝 筆記', '筆記 列表'], ['⏰ 提醒', '提醒 列表'],
      ['🌐 搜尋', '搜尋 空氣品質'], ['🌍 翻譯', '翻譯 en:你好'], ['💡 靈感', '靈感 一人公司'],
      ['📊 狀態', '狀態'], ['❓ 功能', '/help']
    ];
    chips.forEach(function (c) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = c[0];
      b.addEventListener('click', function () { ask(c[1]); });
      p.querySelector('.spirit-chips').appendChild(b);
    });

    p.querySelector('form').addEventListener('submit', function (e) {
      e.preventDefault();
      var input = p.querySelector('input[type=text]');
      ask(input.value);
      input.value = '';
    });
    p.querySelector('.spirit-mic').addEventListener('click', function () {
      p.querySelector('input[type=file]').click();
    });
    p.querySelector('input[type=file]').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (f) voice(f);
      e.target.value = '';
    });
    return p;
  }

  function toggle(open) {
    S.open = open;
    var p = build();
    p.hidden = !open;
    if (open) {
      if (!p.querySelector('.spirit-msg')) say(HELP);
      var input = p.querySelector('input[type=text]');
      if (input) input.focus();
    }
  }

  function msg(role, text, image) {
    var box = build().querySelector('.spirit-msgs');
    var div = document.createElement('div');
    div.className = 'spirit-msg ' + role;
    div.textContent = String(text == null ? '' : text);
    if (image) {
      var img = document.createElement('img');
      img.src = image;
      img.alt = 'AI 生成的圖片';
      div.appendChild(img);
    }
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    var t = String(text == null ? '' : text).trim();
    // 只記正常對話；錯誤提示不進脈絡，避免污染回覆
    if (t && !/^[⚠🔒]/.test(t)) {
      S.history.push({ role: role === 'me' ? 'user' : 'ai', text: t.slice(0, 200) });
      if (S.history.length > 12) S.history = S.history.slice(-12);
    }
  }

  function say(text, image) { msg('ai', text, image); }

  function api(path, opts) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 15000) : null;
    opts = opts || {};
    if (ctl) opts.signal = ctl.signal;
    opts.credentials = 'include';
    return fetch(API + path, opts).then(function (r) {
      if (r.status === 401) {
        var e = new Error('🔒 這項功能需要登入（點右上角「登入」）。');
        e.code = 401;
        throw e;
      }
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status));
        return j;
      });
    }).then(function (j) {
      if (timer) clearTimeout(timer);
      return j;
    }, function (e) {
      if (timer) clearTimeout(timer);
      throw e;
    });
  }

  function post(path, body) {
    return api(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
  }

  // ── 意圖路由：純前端、零額外模型呼叫 ─────────────────────────────
  function route(text) {
    var t = String(text || '').trim();
    var m;
    if (!t) return null;
    var low = t.toLowerCase();

    if (/^\/?(help|說明|協助|功能|能做什麼|有哪些指令|你會什麼|列出功能)/i.test(t) ||
        /what can you do|all commands/i.test(low)) return { k: 'help' };

    if ((m = t.match(/^\/?(?:計算|算一下|算|calc|calculate)\s*[:：]?\s*(.+)$/i)))
      return { k: 'calc', q: m[1] };
    if ((m = t.match(/^\/?(?:筆記|note|記一下)\s*[:：]?\s*(.*)$/i)))
      return { k: 'note', q: m[1] };
    if ((m = t.match(/^\/?(?:提醒|remind)(?:我)?\s*[:：]?\s*(.*)$/i)))
      return { k: 'remind', q: m[1] };
    if ((m = t.match(/^\/?(?:翻譯|翻译|translate)\s*[:：]?\s*(.*)$/i)))
      return { k: 'translate', q: m[1] };
    if ((m = t.match(/^\/?(?:搜尋|搜索|search)\s*[:：]?\s*(.*)$/i)))
      return { k: 'search', q: m[1] };
    if ((m = t.match(/^\/?(?:靈感|灵感|idea)\s*[:：]?\s*(.*)$/i)))
      return { k: 'idea', q: m[1] };
    if ((m = t.match(/^\/?(?:生圖|生图|image)\s*[:：]?\s*(.+)$/i)))
      return { k: 'image', q: m[1] };
    if (/^\/?(?:狀態|状态|status)\s*$/i.test(t)) return { k: 'status' };
    return { k: 'fallback', q: t };
  }

  var LANGS = {
    en: 'en', 英文: 'en', 英: 'en', english: 'en',
    zh: 'zh-TW', 'zh-tw': 'zh-TW', 中文: 'zh-TW', 繁中: 'zh-TW',
    ja: 'ja', 日文: 'ja', 日: 'ja', ko: 'ko', 韓文: 'ko'
  };

  var handlers = {
    help: function () { return Promise.resolve(HELP); },

    calc: function (r) {
      return post('/api/tools/calculate', { expression: r.q }).then(function (j) {
        return '🧮 ' + r.q + ' = ' + j.result;
      });
    },

    note: function (r) {
      var q = r.q.trim();
      if (/^(列表|list|查看|全部)$/i.test(q)) {
        return api('/api/tools/notes').then(function (j) {
          if (!j.items || !j.items.length) return '📝 目前沒有筆記。';
          return j.items.map(function (n) {
            return '#' + n.id + ' ' + n.content;
          }).join('\n');
        });
      }
      var del = q.match(/^(?:刪除|删除|del|rm)\s*#?(\d+)$/i);
      if (del) {
        return api('/api/tools/notes/' + del[1], { method: 'DELETE' })
          .then(function () { return '🗑️ 已刪除筆記 #' + del[1]; });
      }
      if (!q) return Promise.resolve('📝 用法：/筆記 內容｜/筆記 列表｜/筆記 刪除 3');
      return post('/api/tools/notes', { content: q }).then(function () {
        return '📝 已記錄：「' + q.slice(0, 60) + '」';
      });
    },

    remind: function (r) {
      var q = r.q.trim();
      if (/^(列表|list|查看)$/i.test(q)) {
        return api('/api/tools/reminders').then(function (j) {
          if (!j.items || !j.items.length) return '⏰ 目前沒有提醒。';
          return j.items.map(function (n) {
            return '#' + n.id + ' ' + n.text + '（' + n.due_at + '）';
          }).join('\n');
        });
      }
      var cancel = q.match(/^(?:取消|cancel)\s*#?(\d+)$/i);
      if (cancel) {
        return api('/api/tools/reminders/' + cancel[1], { method: 'DELETE' })
          .then(function () { return '⏰ 已取消提醒 #' + cancel[1]; });
      }
      var m = q.match(/^(.+?)\s+(.+)$/);
      if (!m) return Promise.resolve('⏰ 用法：/提醒 30分鐘後 喝水｜/提醒 列表｜/提醒 取消 3');
      return post('/api/tools/reminders', { text: m[2], due_at: m[1] }).then(function () {
        return '⏰ 已設定：' + m[1] + '「' + m[2] + '」';
      });
    },

    translate: function (r) {
      var q = r.q.trim(), target = 'en', body = q, m;
      if ((m = q.match(/^([A-Za-z\-]+|中文|英文|日文|韓文)\s*[:：]\s*(.+)$/))) {
        target = LANGS[m[1].toLowerCase()] || m[1];
        body = m[2];
      } else if ((m = q.match(/^(?:成|為|到)\s*(中文|英文|日文|韓文|en|ja|ko)\s*[:：]?\s*(.+)$/i))) {
        target = LANGS[m[1].toLowerCase()] || m[1];
        body = m[2];
      }
      if (!body) return Promise.resolve('🌍 用法：/翻譯 en:你好');
      return post('/api/ai/translate', { text: body, target: target, source: 'auto' })
        .then(function (j) { return '🌍 ' + j.text; });
    },

    search: function (r) {
      var q = r.q.trim(), scope = 'all', m = q.match(/^(gov|kb|web|all)\s*[:：]\s*(.+)$/i);
      if (m) { scope = m[1].toLowerCase(); q = m[2]; }
      if (!q) return Promise.resolve('🌐 用法：/搜尋 gov:空氣品質（scope=all/gov/kb/web）');
      return post('/api/ai/search', { q: q, scope: scope, limit: 5 }).then(function (j) {
        if (!j.items || !j.items.length) return '🔍 找不到「' + q + '」的結果。';
        return j.items.slice(0, 5).map(function (it) {
          return '• ' + (it.title || '無標題') + (it.url ? '\n  ' + it.url : '');
        }).join('\n');
      });
    },

    idea: function (r) {
      var topic = r.q.trim() || '一人公司 AI 自動化';
      return post('/api/content/ai-generate', {
        template: '社群貼文', variables: { '主題': topic }
      }).then(function (j) { return '💡 ' + j.text; });
    },

    image: function (r) {
      return post('/api/ai/image', { prompt: r.q, size: '1024x1024' }).then(function (j) {
        return { text: '🖼️ 已生成：（' + (j.revised_prompt || r.q).slice(0, 80) + '）', image: j.image };
      });
    },

    status: function () {
      if (S.status && Date.now() - S.statusAt < 60000) return Promise.resolve(S.status);
      return api('/api/status').then(function (j) {
        var hooks = (j.auto_engine && j.auto_engine.hooks) || [];
        S.status = '📊 狀態\n' +
          '• AI：' + (j.ai_available ? '可用' : '未設定') + '\n' +
          '• 郵件：' + (j.smtp_configured ? '已設定' : '未設定') + '\n' +
          '• 排程：' + hooks.length + ' 個任務' + (hooks.indexOf('reminders') >= 0 ? '（含提醒）' : '') + '\n' +
          '• 版本：' + (j.build_fingerprint || '未知');
        S.statusAt = Date.now();
        return S.status;
      });
    },

    fallback: function (r) {
      // 交給後端共用引擎：先查知識庫，再用模型接話，一樣限制句數與字數。
      return post('/api/assistant/chat', { text: r.q, history: S.history.slice(-6) })
        .then(function (j) {
          if (j.reply) return j.reply;
          return '我還不會這項。輸入 /help 看我實際會的功能。';
        });
    }
  };

  function voice(file) {
    if (file.size > 25 * 1024 * 1024) return say('⚠️ 音訊請小於 25MB。');
    if (S.busy) return say('⏳ 上一個請求還在處理。');
    S.busy = true;
    msg('me', '🎤 ' + (file.name || '語音'));
    var fd = new FormData();
    fd.append('file', file, file.name || 'voice.ogg');
    return api('/api/tools/transcribe', { method: 'POST', body: fd })
      .then(function (j) { say('🎤 ' + j.text); }, errorText)
      .then(function () { S.busy = false; });
  }

  function errorText(e) {
    say(e && e.code === 401
      ? '🔒 這項功能需要登入（點右上角「登入」）。'
      : '⚠️ ' + ((e && e.message) || '請求失敗，請稍後再試。'));
  }

  function ask(text) {
    if (S.busy) return;
    var t = String(text || '').trim();
    if (!t) return;
    var r = route(t);
    if (!r) return;
    S.busy = true;
    build().querySelector('.spirit-send').disabled = true;
    msg('me', t);
    Promise.resolve()
      .then(function () { return handlers[r.k](r); })
      .then(function (out) {
        if (typeof out === 'string') say(out);
        else say(out.text, out.image);
      }, errorText)
      .then(function () {
        S.busy = false;
        var b = build().querySelector('.spirit-send');
        if (b) b.disabled = false;
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
