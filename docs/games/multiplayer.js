const MP2P = {
  mode: '1p', current: 1, scores: [0, 0], active: false,
  name: '', p1Start: null, p2Start: null, onDone: null,
  overlay: null, titleEl: null, msgEl: null, btn1: null, btn2: null,

  init(gameName, onP1, onP2, onCompare) {
    this.name = gameName; this.p1Start = onP1; this.p2Start = onP2; this.onDone = onCompare;
    this.buildUI();
  },

  buildUI() {
    this.overlay = document.createElement('div');
    this.overlay.id = 'mpOverlay';
    this.overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(10,14,39,.92);backdrop-filter:blur(10px);flex-direction:column;align-items:center;justify-content:center;z-index:999;gap:16px;padding:24px';
    this.overlay.innerHTML = `
      <div style="font-size:clamp(32px,8vw,48px)" id="mpIcon">🎮</div>
      <h2 id="mpTitle" style="font-size:clamp(22px,5vw,30px);font-weight:800;text-align:center"></h2>
      <p id="mpMsg" style="font-size:15px;color:rgba(255,255,255,.5);text-align:center;max-width:320px"></p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:4px" id="mpBtns"></div>`;
    document.body.appendChild(this.overlay);
  },

  showModeSelector() {
    this.overlay.style.display = 'flex';
    document.getElementById('mpIcon').textContent = '🎮';
    document.getElementById('mpTitle').textContent = `🎮 ${this.name}`;
    document.getElementById('mpMsg').textContent = '選擇遊戲模式';
    const btns = document.getElementById('mpBtns');
    btns.innerHTML = `
      <button class="mp-btn" data-m="1p" style="padding:14px 28px;border-radius:12px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.06);color:#fff;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .2s">👤 單人遊玩</button>
      <button class="mp-btn" data-m="2p" style="padding:14px 28px;border-radius:12px;border:1px solid rgba(0,212,255,.2);background:rgba(0,212,255,.1);color:#00d4ff;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .2s">👥 雙人輪流</button>`;
    btns.querySelectorAll('.mp-btn').forEach(b => {
      b.addEventListener('click', () => { this.mode = b.dataset.m; this.hide(); this.start(); });
      b.addEventListener('touchend', e => { e.preventDefault(); this.mode = b.dataset.m; this.hide(); this.start(); });
    });
  },

  start() {
    this.active = true; this.current = 1; this.scores = [0, 0];
    if (this.mode === '1p') { this.p1Start(); return; }
    this.showTurn(1);
  },

  showTurn(player) {
    this.overlay.style.display = 'flex';
    const icon = player === 1 ? '🔵' : '🔴';
    const label = player === 1 ? 'Player 1' : 'Player 2';
    document.getElementById('mpIcon').textContent = icon;
    document.getElementById('mpTitle').textContent = `👤 ${label} 的回合`;
    document.getElementById('mpMsg').textContent = `準備好了就開始吧！${player === 2 ? '\n(P1 分數: ' + this.scores[0] + ')' : ''}`;
    const btns = document.getElementById('mpBtns');
    btns.innerHTML = `<button class="mp-go" style="padding:14px 32px;border-radius:12px;border:none;background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;font-size:16px;font-weight:700;cursor:pointer;font-family:inherit">▶ 開始</button>`;
    btns.querySelector('.mp-go').onclick = () => { this.hide(); if (player === 1) this.p1Start(); else this.p2Start(); };
  },

  playerDone(score) {
    if (this.mode === '1p') return;
    this.scores[this.current - 1] = score;
    if (this.current === 1) {
      this.current = 2;
      this.showTurn(2);
      if (this.onDone) this.onDone(1, score);
    } else {
      this.showResult();
    }
  },

  showResult() {
    this.overlay.style.display = 'flex';
    const s1 = this.scores[0], s2 = this.scores[1];
    let icon, title, msg;
    if (s1 > s2) { icon = '🏆'; title = '🔵 Player 1 獲勝！'; msg = `${s1} : ${s2}`; }
    else if (s2 > s1) { icon = '🏆'; title = '🔴 Player 2 獲勝！'; msg = `${s1} : ${s2}`; }
    else { icon = '🤝'; title = '平手！'; msg = `雙方都是 ${s1}`; }
    document.getElementById('mpIcon').textContent = icon;
    document.getElementById('mpTitle').textContent = title;
    document.getElementById('mpMsg').textContent = msg;
    const btns = document.getElementById('mpBtns');
    btns.innerHTML = `
      <button class="mp-retry" style="padding:12px 28px;border-radius:10px;border:none;background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit">🔄 再玩一次</button>
      <button class="mp-menu" style="padding:12px 24px;border-radius:10px;border:1px solid rgba(255,255,255,.1);background:transparent;color:rgba(255,255,255,.5);font-size:14px;cursor:pointer;font-family:inherit">📋 選模式</button>`;
    btns.querySelector('.mp-retry').onclick = () => { this.hide(); this.start(); };
    btns.querySelector('.mp-menu').onclick = () => this.showModeSelector();
    if (this.onDone) this.onDone(2, s1, s2);
  },

  hide() { this.overlay.style.display = 'none'; }
};
