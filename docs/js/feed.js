(function(){
var BASE=location.hostname.includes('github.io')?'https://lewislunora.onrender.com':'';

var css=document.createElement('style');
css.textContent=
'.feed-widget{padding:clamp(3.5rem,5vw,7rem) clamp(1rem,3vw,2rem);max-width:1100px;margin:0 auto}'+
'.feed-list{max-width:620px;margin:0 auto}'+
'.feed-item{padding:.8rem 0;border-bottom:1px solid rgba(255,255,255,.03)}'+
'.feed-item:last-child{border-bottom:none}'+
'.feed-meta{display:flex;gap:.6rem;align-items:center;margin-bottom:.2rem}'+
'.feed-type{font-size:10px;font-weight:600;color:#7b68ee;letter-spacing:.5px}'+
'.feed-time{font-size:11px;color:rgba(255,255,255,.2)}'+
'.feed-content{font-size:var(--fs-sm);color:rgba(255,255,255,.55);line-height:1.6}'+
'.feed-author{font-size:11px;color:rgba(255,255,255,.2);margin-top:.2rem}';
document.head.appendChild(css);

document.querySelectorAll('[data-feed]').forEach(function(el){
  el.className='feed-widget';
  el.innerHTML=
    '<div class="section-label" data-i18n="feed_label">最新動態</div>'+
    '<h2 class="section-title" data-i18n="feed_title">👀 翔川日常</h2>'+
    '<p class="section-sub" data-i18n="feed_sub">觀點分享 · 技術筆記 · 專案進度</p>'+
    '<div class="feed-list"></div>'+
    '<div class="feed-empty" style="display:none;text-align:center;padding:2rem;color:rgba(255,255,255,.2);font-size:var(--fs-sm)">📭 暫無動態</div>';
  var list=el.querySelector('.feed-list');
  var empty=el.querySelector('.feed-empty');
  fetch(BASE+'/api/feed').then(function(r){return r.json()}).then(function(d){
    if(!d.items||!d.items.length){
      list.style.display='none';empty.style.display='block';
      return;
    }
    list.innerHTML=d.items.map(function(p){
      var labels={tip:'💡 技巧',announcement:'📢 公告',case_study:'📋 案例'};
      return '<div class="feed-item">'+
        '<div class="feed-meta">'+
          '<span class="feed-type">'+(labels[p.post_type]||p.post_type)+'</span>'+
          '<span class="feed-time">'+timeAgo(p.created_at)+'</span>'+
        '</div>'+
        '<div class="feed-content">'+esc(p.content)+'</div>'+
        (p.author?'<div class="feed-author">— '+esc(p.author)+'</div>':'')+
      '</div>';
    }).join('');
  }).catch(function(){list.style.display='none';empty.style.display='block'});
});

function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
function timeAgo(ts){
  var diff=Date.now()-new Date(ts.replace(' ','T')+'Z').getTime();
  var mins=Math.floor(diff/6e4);
  if(mins<1)return'剛剛';
  if(mins<60)return mins+'分鐘前';
  var hrs=Math.floor(mins/60);
  if(hrs<24)return hrs+'小時前';
  return Math.floor(hrs/24)+'天前';
}
})();
