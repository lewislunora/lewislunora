(function(){
if(document.getElementById('_feats_'))return;
document.documentElement.setAttribute('data-features','loading');

var css=document.createElement('style');
css.id='_feats_';
css.textContent=
/* ─── Reading Progress ─── */
'.reading-progress{position:fixed;top:0;left:0;width:0;height:2px;background:linear-gradient(90deg,#00d4ff,#7b68ee);z-index:999;transition:width .1s linear}'+
/* ─── Particle Canvas ─── */
'#particle-canvas{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0}'+
'.hero{position:relative;overflow:hidden}'+
'.hero>*:not(#particle-canvas){position:relative;z-index:1}'+
/* ─── 3D Tilt ─── */
'.tilt-3d{transition:transform .2s ease-out;will-change:transform}'+
/* ─── Ripple ─── */
'.ripple{position:relative;overflow:hidden}'+
'.ripple::after{content:"";position:absolute;border-radius:50%;background:rgba(255,255,255,.3);transform:scale(0);animation:ripple-anim .6s ease-out;pointer-events:none}'+
'@keyframes ripple-anim{to{transform:scale(4);opacity:0}}'+
/* ─── Skeleton ─── */
'.skeleton{background:linear-gradient(90deg,rgba(255,255,255,.03) 25%,rgba(255,255,255,.06) 50%,rgba(255,255,255,.03) 75%);background-size:200% 100%;animation:skeleton-shimmer 1.5s infinite;border-radius:6px}'+
'@keyframes skeleton-shimmer{0%{background-position:200% 0}to{background-position:-200% 0}}'+
/* ─── Scrollytelling Parallax ─── */
'.parallax-layer{will-change:transform}'+
/* ─── Voice UI ─── */
'.voice-btn{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:20px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:rgba(255,255,255,.4);font-size:10px;cursor:pointer;transition:all .3s}'+
'.voice-btn:hover{border-color:rgba(0,212,255,.3);color:#00d4ff}'+
'.voice-btn.listening{background:rgba(0,212,255,.12);border-color:#00d4ff;color:#00d4ff;animation:voice-pulse 1s infinite}'+
'@keyframes voice-pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,212,255,.2)}50%{box-shadow:0 0 0 6px rgba(0,212,255,0)}}'+
/* ─── Generative UI badge ─── */
'.gen-ui-badge{position:fixed;bottom:90px;right:16px;z-index:50;font-size:9px;padding:4px 10px;border-radius:20px;background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.15);color:rgba(255,255,255,.3);pointer-events:none;backdrop-filter:blur(8px);transition:opacity .5s}'+
'.gen-ui-badge span{color:#00d4ff}'+
/* ─── Skip link ─── */
'.skip-link{position:fixed;top:-100%;left:8px;z-index:9999;padding:8px 16px;background:#00d4ff;color:#0a0e27;font-size:12px;font-weight:600;border-radius:0 0 6px 6px;text-decoration:none;transition:top .2s}'+
'.skip-link:focus{top:0}'+
/* ─── Enhanced Focus ─── */
'a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #00d4ff;outline-offset:2px;border-radius:4px}'+
/* ─── Scrollbar ─── */
'::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(0,212,255,.2);border-radius:4px}::-webkit-scrollbar-thumb:hover{background:rgba(0,212,255,.4)}'+
/* ─── Reduced motion overrides ─── */
'@media(prefers-reduced-motion:reduce){#particle-canvas{display:none}.tilt-3d{transform:none!important}.parallax-layer{transform:none!important}}'+
/* ─── Light mode adjustments ─── */
'@media(prefers-color-scheme:light){.reading-progress{background:linear-gradient(90deg,#0891b2,#6366f1)}.gen-ui-badge{background:rgba(8,145,178,.08);border-color:rgba(8,145,178,.15)}.gen-ui-badge span{color:#0891b2}}';
document.head.appendChild(css);

// ─── Skip Link ───
var skip=document.createElement('a');
skip.href='#main-content';
skip.className='skip-link';
skip.textContent='跳到主要內容';
document.body.insertBefore(skip,document.body.firstChild);
var mainEl=document.querySelector('main')||document.querySelector('.container')||document.querySelector('.hero');
if(mainEl)mainEl.id=mainEl.id||'main-content';

// ─── Reading Progress ───
if(document.querySelector('.container')){
  var prog=document.createElement('div');
  prog.className='reading-progress';
  prog.id='readingProgress';
  document.body.appendChild(prog);
  var ticking=false;
  window.addEventListener('scroll',function(){
    if(!ticking){requestAnimationFrame(function(){
      var scrollTop=window.scrollY;
      var docHeight=document.documentElement.scrollHeight-window.innerHeight;
      prog.style.width=(docHeight>0?Math.min(scrollTop/docHeight*100,100):0)+'%';
      ticking=false
    });ticking=true}
  });
}

// ─── Hero Particle Canvas ───
var hero=document.querySelector('.hero');
if(hero&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
  var canvas=document.createElement('canvas');
  canvas.id='particle-canvas';
  hero.insertBefore(canvas,hero.firstChild);
  var ctx=canvas.getContext('2d');
  var particles=[];
  var W,H;
  function resize(){
    W=canvas.width=hero.offsetWidth;
    H=canvas.height=hero.offsetHeight;
  }
  resize();
  window.addEventListener('resize',resize);
  for(var i=0;i<80;i++){
    particles.push({
      x:Math.random()*W,y:Math.random()*H,
      vx:(Math.random()-.5)*.3,vy:(Math.random()-.5)*.3,
      r:Math.random()*1.5+.5,o:Math.random()*.4+.2
    })
  }
  var mouse={x:W/2,y:H/2};
  hero.addEventListener('mousemove',function(e){
    mouse.x=e.clientX-hero.getBoundingClientRect().left;
    mouse.y=e.clientY-hero.getBoundingClientRect().top;
  });
  function draw(){
    ctx.clearRect(0,0,W,H);
    for(var i=0;i<particles.length;i++){
      var p=particles[i];
      var dx=mouse.x-p.x,dy=mouse.y-p.y,dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<200){p.vx-=dx/dist*.002;p.vy-=dy/dist*.002}
      p.vx*=0.99;p.vy*=0.99;
      p.x+=p.vx;p.y+=p.vy;
      if(p.x<0)p.x=W;if(p.x>W)p.x=0;
      if(p.y<0)p.y=H;if(p.y>H)p.y=0;
      ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle='rgba(0,212,255,'+p.o+')';
      ctx.fill();
    }
    // connections
    for(i=0;i<particles.length;i++){
      for(var j=i+1;j<particles.length;j++){
        var a=particles[i],b=particles[j];
        var dx=a.x-b.x,dy=a.y-b.y,dist=Math.sqrt(dx*dx+dy*dy);
        if(dist<120){
          ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
          ctx.strokeStyle='rgba(0,212,255,'+(.08*(1-dist/120))+')';
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
}

// ─── 3D Tilt on Cards ───
if(!matchMedia('(prefers-reduced-motion:reduce)').matches&&!matchMedia('(hover:none)').matches){
  document.querySelectorAll('.pain-card,.svc-card,.svc-tech-card,.bento-stat,.guide-card').forEach(function(card){
    card.classList.add('tilt-3d');
    card.addEventListener('mousemove',function(e){
      var rect=card.getBoundingClientRect();
      var x=e.clientX-rect.left,y=e.clientY-rect.top;
      var rotX=((y/rect.height)-.5)*-12;
      var rotY=((x/rect.width)-.5)*12;
      card.style.transform='perspective(600px) rotateX('+rotX+'deg) rotateY('+rotY+'deg) translateY(-4px)';
    });
    card.addEventListener('mouseleave',function(){
      card.style.transform='perspective(600px) rotateX(0) rotateY(0) translateY(0)';
    });
  });
}

// ─── Button Ripple ───
document.querySelectorAll('.btn,.comment-submit,.new-thread-btn,.chat-send,.reaction-btn,.btn-submit').forEach(function(btn){
  btn.classList.add('ripple');
  btn.addEventListener('click',function(e){
    var ripple=document.createElement('span');
    var rect=btn.getBoundingClientRect();
    var size=Math.max(rect.width,rect.height);
    ripple.style.width=ripple.style.height=size+'px';
    ripple.style.left=(e.clientX-rect.left-size/2)+'px';
    ripple.style.top=(e.clientY-rect.top-size/2)+'px';
    ripple.style.position='absolute';
    ripple.style.borderRadius='50%';
    ripple.style.background='rgba(255,255,255,.3)';
    ripple.style.transform='scale(0)';
    ripple.style.animation='ripple-anim .6s ease-out';
    ripple.style.pointerEvents='none';
    btn.appendChild(ripple);
    setTimeout(function(){ripple.remove()},600);
  });
});

// ─── Parallax Scroll Layers ───
if(!matchMedia('(prefers-reduced-motion:reduce)').matches){
  document.querySelectorAll('.hero h1,.hero p,.hero-actions,.bento-stats,.pain-bento,.svcs-bento').forEach(function(el,i){
    el.classList.add('parallax-layer');
    el.setAttribute('data-speed',(1+(i%3)*.1).toFixed(1));
  });
  var parallaxTicking=false;
  window.addEventListener('scroll',function(){
    if(!parallaxTicking){requestAnimationFrame(function(){
      var st=window.scrollY;
      document.querySelectorAll('.parallax-layer').forEach(function(el){
        var speed=parseFloat(el.getAttribute('data-speed')||'1');
        var rect=el.getBoundingClientRect();
        if(rect.top<window.innerHeight&&rect.bottom>0){
          var offset=(window.innerHeight-rect.top)*speed*.05;
          var maxOffset=40;
          offset=Math.max(-maxOffset,Math.min(maxOffset,offset));
          el.style.transform='translateY('+offset+'px)';
        }
      });
      parallaxTicking=false
    });parallaxTicking=true}
  });
}

// ─── Voice Search UI ───
var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SpeechRecognition&&document.querySelector('.lang-select')){
  var nav=document.querySelector('.nav-links')||document.querySelector('.nav-links');
  if(nav){
    var voiceBtn=document.createElement('button');
    voiceBtn.className='voice-btn';
    voiceBtn.innerHTML='🎤 語音';
    voiceBtn.title='語音搜尋';
    voiceBtn.setAttribute('aria-label','語音搜尋');
    var recognition=new SpeechRecognition();
    recognition.lang='zh-TW';
    recognition.continuous=false;
    recognition.interimResults=false;
    voiceBtn.addEventListener('click',function(){
      if(voiceBtn.classList.contains('listening')){recognition.abort();voiceBtn.classList.remove('listening');voiceBtn.innerHTML='🎤 語音';return}
      voiceBtn.classList.add('listening');
      voiceBtn.innerHTML='⏺ 聆聽中...';
      recognition.start();
    });
    recognition.onresult=function(e){
      var transcript=e.results[0][0].transcript;
      voiceBtn.innerHTML='🔍 "'+transcript+'"';
      voiceBtn.classList.remove('listening');
      window.find(transcript)||alert('搜尋：'+transcript);
    };
    recognition.onend=function(){
      voiceBtn.classList.remove('listening');
      if(voiceBtn.innerHTML==='⏺ 聆聽中...')voiceBtn.innerHTML='🎤 語音';
    };
    recognition.onerror=function(){
      voiceBtn.classList.remove('listening');
      voiceBtn.innerHTML='❌ 語音';
      setTimeout(function(){voiceBtn.innerHTML='🎤 語音'},2000);
    };
    nav.insertBefore(voiceBtn,nav.querySelector('.lang-select'));
  }
}

// ─── Generative UI: Dynamic Greeting ───
var heroTitle=document.querySelector('.hero h1 .line1');
if(heroTitle){
  var hour=new Date().getHours();
  var greetings={
    'zh-TW':{m:'🌅 早安',a:'☀️ 午安',e:'🌆 晚安',n:'🌙 深夜'},
    'zh-CN':{m:'🌅 早上好',a:'☀️ 下午好',e:'🌆 晚上好',n:'🌙 夜深了'},
    'en':{m:'🌅 Good Morning',a:'☀️ Good Afternoon',e:'🌆 Good Evening',n:'🌙 Late Night'}
  };
  var lang=document.documentElement.lang||'zh-TW';
  var g=greetings[lang]||greetings['zh-TW'];
  var period=hour<5?'n':hour<12?'m':hour<18?'a':'e';
  // Add badge
  var badge=document.createElement('div');
  badge.className='gen-ui-badge';
  var label={'zh-TW':'✨ 為你動態生成','zh-CN':'✨ 为你动态生成','en':'✨ Generated for you'};
  badge.innerHTML=(label[lang]||label['zh-TW'])+' · <span>'+g[period]+'</span>';
  document.body.appendChild(badge);
  setTimeout(function(){badge.style.opacity='0';setTimeout(function(){badge.remove()},1000)},4000);
}

// ─── Skeleton Loading for Feed ───
document.querySelectorAll('.feed-list').forEach(function(el){
  if(!el.querySelector('.feed-item')){
    var html='';
    for(var i=0;i<3;i++){
      html+='<div style="padding:1rem 0;border-bottom:1px solid rgba(255,255,255,.03)">'+
        '<div class="skeleton" style="width:80px;height:12px;margin-bottom:6px"></div>'+
        '<div class="skeleton" style="width:100%;height:14px;margin-bottom:4px"></div>'+
        '<div class="skeleton" style="width:60%;height:14px"></div>'+
      '</div>';
    }
    el.innerHTML=html;
  }
});

// ─── Accessibility: aria labels ───
document.querySelectorAll('.btn-primary').forEach(function(el,i){
  if(!el.getAttribute('aria-label'))el.setAttribute('aria-label','主要操作按鈕');
});
document.querySelectorAll('nav a').forEach(function(el){
  if(!el.getAttribute('aria-label'))el.setAttribute('aria-label','導航：'+el.textContent.trim());
});
document.querySelectorAll('img:not([alt])').forEach(function(el){
  el.setAttribute('alt','');
});

document.documentElement.setAttribute('data-features','loaded');
console.log('⚡ 2026 features loaded');
})();
