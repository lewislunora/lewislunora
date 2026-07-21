(function(){
var BASE=location.hostname.includes('github.io')?'https://lewislunora.onrender.com':'';

var css=document.createElement('style');
css.textContent=
'.reactions-widget{margin:2rem 0 1rem;padding:1.2rem 1.5rem;background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.05);border-radius:12px}'+
'.reactions-label{display:block;font-size:12px;color:rgba(255,255,255,.3);margin-bottom:.6rem}'+
'.reactions-bar{display:flex;gap:.4rem;flex-wrap:wrap}'+
'.reaction-btn{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:.3rem .7rem;font-size:13px;cursor:pointer;transition:all .2s;color:rgba(255,255,255,.5)}'+
'.reaction-btn:hover{background:rgba(123,104,238,.15);border-color:rgba(123,104,238,.25);color:#fff}'+
'.reaction-btn .count{font-size:11px;margin-left:2px}'+
'.comments-widget{margin:1rem 0 2rem;padding:1.5rem;background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.05);border-radius:12px}'+
'.comments-title{font-size:1rem;font-weight:600;margin-bottom:1rem;color:rgba(255,255,255,.6)}'+
'.comments-form{display:flex;flex-direction:column;gap:.5rem;margin-bottom:1.2rem}'+
'.comment-name{padding:.5rem .7rem;border-radius:6px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);color:#e8ecf4;font-size:13px;outline:none;font-family:inherit;max-width:220px}'+
'.comment-name:focus{border-color:rgba(123,104,238,.3)}'+
'.comment-input{padding:.6rem .7rem;border-radius:6px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);color:#e8ecf4;font-size:13px;outline:none;font-family:inherit;resize:vertical}'+
'.comment-input:focus{border-color:rgba(123,104,238,.3)}'+
'.comment-submit{align-self:flex-start;padding:.45rem 1.2rem;border-radius:6px;border:none;font-size:12px;font-weight:600;cursor:pointer;background:linear-gradient(135deg,#7b68ee,#00d4ff);color:#fff;transition:all .2s}'+
'.comment-submit:hover{transform:translateY(-1px);box-shadow:0 4px 15px rgba(123,104,238,.3)}'+
'.comment-submit:disabled{opacity:.5;cursor:not-allowed}'+
'.comment-item{padding:.7rem 0;border-bottom:1px solid rgba(255,255,255,.03)}'+
'.comment-item:last-child{border-bottom:none}'+
'.comment-header{display:flex;gap:.6rem;align-items:center;margin-bottom:.2rem}'+
'.comment-author{font-size:12px;font-weight:600;color:rgba(255,255,255,.5)}'+
'.comment-time{font-size:11px;color:rgba(255,255,255,.2)}'+
'.comment-body{font-size:14px;color:rgba(255,255,255,.65);line-height:1.5}'+
'.comment-replies{margin-top:.4rem;margin-left:1rem;padding-left:.6rem;border-left:2px solid rgba(123,104,238,.15)}'+
'.comment-reply{padding:.3rem 0;font-size:13px;color:rgba(255,255,255,.5)}'+
'.ai-summary-section{margin:1.5rem 0 0}'+
'.ai-summary-widget{padding:1rem 1.2rem;background:rgba(123,104,238,.06);border:1px solid rgba(123,104,238,.12);border-radius:10px}'+
'.ai-summary-inner{display:flex;align-items:flex-start;gap:.5rem}'+
'.ai-summary-icon{font-size:1.1rem;margin-top:1px}'+
'.ai-summary-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#7b68ee;margin-top:3px;white-space:nowrap}'+
'.ai-summary-text{font-size:13px;color:rgba(255,255,255,.6);line-height:1.6;flex:1}';
document.head.appendChild(css);

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

// ─── Reactions ───
document.querySelectorAll('[data-reactions]').forEach(function(el){
  var path=el.dataset.reactions;
  var EMOJIS=['👍','❤️','🔥','💡','😂','😮'];
  el.className='reactions-widget';
  el.innerHTML='<span class="reactions-label">你覺得這篇如何？</span><div class="reactions-bar"></div>';
  var bar=el.querySelector('.reactions-bar');
  EMOJIS.forEach(function(emoji){
    var btn=document.createElement('button');
    btn.className='reaction-btn';
    btn.dataset.emoji=emoji;
    btn.innerHTML=emoji+' <span class="count">0</span>';
    btn.onclick=function(){
      fetch(BASE+'/api/reactions/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page_path:path,emoji:emoji})}).then(function(){loadR()}).catch(function(){});
    };
    bar.appendChild(btn);
  });
  function loadR(){
    fetch(BASE+'/api/reactions?path='+encodeURIComponent(path)).then(function(r){return r.json()}).then(function(d){
      d.items.forEach(function(item){
        var btn=bar.querySelector('[data-emoji="'+item.emoji+'"]');
        if(btn)btn.querySelector('.count').textContent=item.count;
      });
    }).catch(function(){});
  }
  loadR();
});

// ─── Comments ───
document.querySelectorAll('[data-comments]').forEach(function(el){
  var path=el.dataset.comments;
  el.className='comments-widget';
  el.innerHTML=
    '<h3 class="comments-title">💬 留言討論</h3>'+
    '<div class="comments-form">'+
      '<input type="text" class="comment-name" placeholder="你的暱稱（選填）" maxlength="30">'+
      '<textarea class="comment-input" placeholder="寫下你的想法..." rows="3"></textarea>'+
      '<button class="comment-submit">送出留言</button>'+
    '</div>'+
    '<div class="comments-list"></div>';
  var list=el.querySelector('.comments-list');
  var nameInput=el.querySelector('.comment-name');
  var textInput=el.querySelector('.comment-input');
  var submitBtn=el.querySelector('.comment-submit');
  submitBtn.onclick=function(){
    var name=nameInput.value.trim()||'匿名';
    var content=textInput.value.trim();
    if(!content)return;
    submitBtn.disabled=true;submitBtn.textContent='送出中...';
    fetch(BASE+'/api/comments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page_path:path,author_name:name,content:content})}).then(function(){
      textInput.value='';loadC();
    }).catch(function(){}).then(function(){submitBtn.disabled=false;submitBtn.textContent='送出留言'});
  };
  function loadC(){
    fetch(BASE+'/api/comments?path='+encodeURIComponent(path)).then(function(r){return r.json()}).then(function(d){
      list.innerHTML=d.items.map(function(c){
        var replies=(c.replies||[]).map(function(r){
          return '<div class="comment-reply"><span class="comment-author">'+esc(r.author_name)+'</span> '+esc(r.content)+'</div>';
        }).join('');
        return '<div class="comment-item">'+
          '<div class="comment-header"><span class="comment-author">'+esc(c.author_name)+'</span><span class="comment-time">'+timeAgo(c.created_at)+'</span></div>'+
          '<div class="comment-body">'+esc(c.content)+'</div>'+
          (replies?'<div class="comment-replies">'+replies+'</div>':'')+
        '</div>';
      }).join('');
    }).catch(function(){});
  }
  loadC();
});

// ─── AI Summary ───
document.querySelectorAll('[data-ai-summary]').forEach(function(el){
  var textSource=document.querySelector(el.dataset.aiSummary);
  if(!textSource)return;
  var text=textSource.textContent.trim().slice(0,3000);
  var lang=document.documentElement.lang||'zh-TW';
  el.className='ai-summary-widget';
  el.innerHTML='<div class="ai-summary-inner"><span class="ai-summary-icon">🤖</span><span class="ai-summary-label">AI 摘要</span><span class="ai-summary-text">載入中...</span></div>';
  fetch(BASE+'/api/ai/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,language:lang})}).then(function(r){return r.json()}).then(function(d){
    if(d.summary)el.querySelector('.ai-summary-text').textContent=d.summary;
    else el.querySelector('.ai-summary-text').textContent='⚠️ 摘要功能暫時無法使用';
  }).catch(function(){el.querySelector('.ai-summary-text').textContent='⚠️ 摘要功能暫時無法使用'});
});
})();
