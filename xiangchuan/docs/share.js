// ─── 網路推廣系統 ───
// 浮動分享按鈕 · 推薦連結追蹤 · 一鍵分享 CTA

(function () {
  const SITE_URL = location.hostname.includes('github.io')
    ? 'https://lewislunora.github.io/lewislunora'
    : 'https://lewislunora.onrender.com'

  // ─── 推薦連結追蹤 ───
  const REF_KEY = 'td_ref'
  const params = new URLSearchParams(location.search)
  const refFrom = params.get('ref')
  if (refFrom) {
    localStorage.setItem(REF_KEY, refFrom)
    // 清除 URL 中的 ref 參數
    const url = new URL(location.href)
    url.searchParams.delete('ref')
    if (url.searchParams.toString() !== location.search.slice(1)) {
      history.replaceState(null, '', url.toString())
    }
  }
  const myRef = localStorage.getItem(REF_KEY) || ''

  // ─── 分享功能 ───
  window.sharePage = function (url, title) {
    const shareUrl = url || location.href
    const shareTitle = title || document.title
    if (navigator.share) {
      navigator.share({ title: shareTitle, url: shareUrl }).catch(() => {})
    }
  }

  window.shareToLine = function (url) {
    const u = encodeURIComponent(url || location.href)
    window.open(`https://line.me/R/msg/text/?${u}`, '_blank', 'width=600,height=500')
  }

  window.shareToFB = function (url) {
    const u = encodeURIComponent(url || location.href)
    window.open(`https://www.facebook.com/sharer/sharer.php?u=${u}`, '_blank', 'width=600,height=500')
  }

  window.shareToX = function (url, text) {
    const u = encodeURIComponent(url || location.href)
    const t = encodeURIComponent(text || document.title)
    window.open(`https://twitter.com/intent/tweet?text=${t}&url=${u}`, '_blank', 'width=600,height=500')
  }

  window.copyLink = function (url) {
    const u = url || location.href
    navigator.clipboard.writeText(u).then(() => {
      showToast('✅ 連結已複製！分享給朋友吧')
    }).catch(() => {
      // fallback
      const ta = document.createElement('textarea')
      ta.value = u
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      showToast('✅ 連結已複製！')
    })
  }

  window.copyRefLink = function (path) {
    // 含推薦碼的連結
    const ref = localStorage.getItem(REF_KEY) || ''
    const base = path ? `${SITE_URL}${path}` : location.href
    const sep = base.includes('?') ? '&' : '?'
    const refLink = ref ? `${base}${sep}ref=${ref}` : base
    copyLink(refLink)
  }

  window.getRefLink = function (path) {
    const base = path ? `${SITE_URL}${path}` : location.href
    const sep = base.includes('?') ? '&' : '?'
    return `${base}${sep}ref=${localStorage.getItem(REF_KEY) || 'self'}`
  }

  // ─── Toast ───
  function showToast(msg) {
    let el = document.getElementById('share-toast')
    if (!el) {
      el = document.createElement('div')
      el.id = 'share-toast'
      el.style.cssText =
        'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
        'background:rgba(0,212,255,.9);color:#fff;padding:12px 24px;' +
        'border-radius:12px;font-size:14px;z-index:9999;opacity:0;' +
        'transition:opacity .4s;pointer-events:none;white-space:nowrap'
      document.body.appendChild(el)
    }
    el.textContent = msg
    el.style.opacity = '1'
    setTimeout(() => { el.style.opacity = '0' }, 2500)
  }

  // ─── 浮動分享按鈕 ───
  function addFloatingShare() {
    if (document.getElementById('td-float-share')) return

    const container = document.createElement('div')
    container.id = 'td-float-share'
    container.style.cssText =
      'position:fixed;bottom:80px;left:16px;z-index:98;' +
      'display:flex;flex-direction:column;gap:8px;opacity:0;' +
      'transform:translateY(20px);transition:all .4s'

    const btns = [
      { icon: '💬', label: 'LINE', action: 'shareToLine()' },
      { icon: '📘', label: 'FB', action: 'shareToFB()' },
      { icon: '🐦', label: 'X', action: 'shareToX()' },
      { icon: '🔗', label: '複製', action: 'copyLink()' },
    ]

    btns.forEach((b) => {
      const btn = document.createElement('button')
      btn.innerHTML = b.icon
      btn.title = `分享到 ${b.label}`
      btn.setAttribute('onclick', b.action)
      btn.style.cssText =
        'width:40px;height:40px;border-radius:50%;border:none;' +
        'background:rgba(255,255,255,.08);backdrop-filter:blur(8px);' +
        'cursor:pointer;font-size:18px;transition:all .2s;' +
        'box-shadow:0 2px 8px rgba(0,0,0,.3)'
      btn.addEventListener('mouseenter', () => {
        btn.style.background = 'rgba(0,212,255,.2)'
        btn.style.transform = 'scale(1.15)'
      })
      btn.addEventListener('mouseleave', () => {
        btn.style.background = 'rgba(255,255,255,.08)'
        btn.style.transform = 'scale(1)'
      })
      container.appendChild(btn)
    })

    document.body.appendChild(container)

    // 滾動到一定距離才顯示
    let shown = false
    window.addEventListener('scroll', () => {
      if (window.scrollY > 400 && !shown) {
        container.style.opacity = '1'
        container.style.transform = 'translateY(0)'
        shown = true
      } else if (window.scrollY <= 400 && shown) {
        container.style.opacity = '0'
        container.style.transform = 'translateY(20px)'
        shown = false
      }
    }, { passive: true })
  }

  // ─── 推薦連結產出器（用在表單或會員區） ───
  window.showReferralLink = function () {
    const refLink = getRefLink()
    copyLink(refLink)
    showToast('✅ 你的專屬推薦連結已複製！')
  }

  // ─── 分享收益條（每個頁面底部可選用） ───
  window.renderShareCTA = function (containerId, customText) {
    const el = document.getElementById(containerId)
    if (!el) return
    el.innerHTML = `
      <div style="text-align:center;padding:2rem 1rem;margin-top:1rem;
                  background:rgba(255,255,255,.03);border-radius:16px;
                  border:1px solid rgba(255,255,255,.06)">
        <p style="font-size:1.1rem;color:rgba(255,255,255,.6);margin-bottom:1rem">
          ${customText || '覺得有幫助？分享給需要的朋友'}
        </p>
        <div style="display:flex;gap:.8rem;justify-content:center;flex-wrap:wrap">
          <button onclick="shareToLine()" style="padding:.6rem 1.2rem;border-radius:10px;border:none;
            background:#06C755;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem">
            💬 LINE
          </button>
          <button onclick="shareToFB()" style="padding:.6rem 1.2rem;border-radius:10px;border:none;
            background:#1877F2;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem">
            📘 Facebook
          </button>
          <button onclick="shareToX()" style="padding:.6rem 1.2rem;border-radius:10px;border:none;
            background:#000;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem">
            🐦 X
          </button>
          <button onclick="copyLink()" style="padding:.6rem 1.2rem;border-radius:10px;border:none;
            background:rgba(255,255,255,.1);color:#fff;font-weight:600;cursor:pointer;font-size:.9rem;
            border:1px solid rgba(255,255,255,.15)">
            🔗 複製連結
          </button>
        </div>
      </div>`
  }

  // ─── 初始化 ───
  document.addEventListener('DOMContentLoaded', () => {
    addFloatingShare()
  })

  // ─── 流量／分享追蹤 ───
  function trackShare(platform) {
    const api = location.hostname.includes('github.io')
      ? 'https://lewislunora.onrender.com/api/analytics/track'
      : '/api/analytics/track'
    try {
      const d = { event: 'share', platform, page: location.pathname, ref: myRef, ts: Date.now() }
      if (navigator.sendBeacon) {
        navigator.sendBeacon(api, JSON.stringify(d))
      }
    } catch (_) {}
  }
  // 覆蓋原本的分享函數以加入追蹤
  const origLine = window.shareToLine
  window.shareToLine = function (url) {
    trackShare('line')
    origLine(url)
  }
  const origFB = window.shareToFB
  window.shareToFB = function (url) {
    trackShare('facebook')
    origFB(url)
  }
  const origX = window.shareToX
  window.shareToX = function (url, text) {
    trackShare('twitter')
    origX(url, text)
  }
})()
