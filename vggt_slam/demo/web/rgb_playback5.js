/* V5: server clock owns playback; RGB decoding never rewinds the map clock. */
(()=>{
const video=document.getElementById('native-rgb'), image=document.getElementById('rgb');
let mediaKey=null, appliedGeneration=null, failed=false, pendingPlay=false, fallbackBusy=false;
let lastSeek=0,lastAdvance=performance.now(),lastVideoTime=-1,lastFallback=0,fallbackURL=null;
const text=(id,value)=>{const node=document.getElementById(id);if(node&&node.textContent!==value)node.textContent=value};
async function fallback(){
 if(fallbackBusy||performance.now()-lastFallback<250)return;
 fallbackBusy=true;lastFallback=performance.now();const key=mediaKey;
 try{
  const response=await fetch('/rgb.jpg?latest='+Date.now(),{cache:'no-store'});
  if(!response.ok)return;
  const url=URL.createObjectURL(await response.blob());const probe=new Image();probe.src=url;await probe.decode();
  if(key!==mediaKey){URL.revokeObjectURL(url);return}
  image.src=url;if(fallbackURL)URL.revokeObjectURL(fallbackURL);fallbackURL=url;
 }catch(error){console.debug('RGB frame fallback',error)}finally{fallbackBusy=false}
}
video.addEventListener('error',()=>{failed=true;video.pause()});
video.addEventListener('seeked',()=>{lastAdvance=performance.now()});
async function poll(){
 try{
  const response=await fetch('/api/smooth',{cache:'no-store'});if(!response.ok)throw Error('Playback status unavailable');
  const d=await response.json();lastSmoothStatus=d;
  const now=performance.now(),key=d.media?d.run+'|'+d.media:null;
  if(key!==mediaKey){
   video.pause();mediaKey=key;appliedGeneration=null;failed=false;pendingPlay=false;lastSeek=0;lastVideoTime=-1;lastAdvance=now;
   if(d.media){video.src=d.media;video.load()}else{video.removeAttribute('src');video.load()}
  }
  const target=Math.max(0,Math.min(d.time,Number.isFinite(video.duration)?Math.max(0,video.duration-.01):d.duration));
  if(d.media&&!failed&&video.readyState>=1){
   const generationChanged=appliedGeneration!==d.generation;
   const drift=Math.abs(video.currentTime-target);
   // Let a decoder finish one seek before correcting drift again. Repeated
   // currentTime assignments while HAVE_METADATA can starve decoded frames.
   const correctDrift=video.readyState>=2&&!video.seeking&&!pendingPlay&&now-lastSeek>1500&&
     ((!d.playing&&drift>.04)||(d.playing&&drift>.75));
   if(generationChanged||correctDrift){
    appliedGeneration=d.generation;
    if(drift>.02){video.currentTime=target;lastSeek=now}
   }
   if(!d.playing){video.pause()}
   else if(!video.seeking&&video.paused&&!pendingPlay){
    pendingPlay=true;
    video.play().catch(error=>{if(error.name!=='AbortError'){failed=true;console.debug('RGB native playback fallback',error)}}).finally(()=>pendingPlay=false);
   }
  }
  if(video.currentTime!==lastVideoTime){lastVideoTime=video.currentTime;lastAdvance=now}
  const stalled=d.playing&&now-lastAdvance>1200;
  const overlay=d.selected_query&&(d.mask_rgb||d.box_rgb);
  const visible=!!(d.media&&!overlay&&!failed&&video.readyState>=2&&!video.error&&!stalled&&(!video.seeking||now-lastSeek<400));
  window.smoothRGBVisible=visible;video.style.display=visible?'block':'none';image.style.display=visible?'none':'';
  if(!visible)fallback();
  text('rgb-label',visible?'영상 '+video.currentTime.toFixed(2)+' s · 지도 '+d.rendered_time.toFixed(2)+' s':(overlay?'검색 결과 RGB · 지도 ':'RGB 프레임 · 지도 ')+d.rendered_time.toFixed(2)+' s'+(failed?' · 원본 영상 읽기 실패':''));
  const mode=d.view_mode||(d.follow_rgb?'rgb':'free');
  document.getElementById('chase').setAttribute('aria-pressed',String(mode==='chase'));
  if(mode==='chase'){
   document.getElementById('camera-view').hidden=true;text('mode','Chase View · RGB 카메라 뒤에서 추적');
  }else if(d.playing&&d.follow_rgb){
   document.getElementById('camera-view').hidden=!!window.vggtGPU?.visible;
   text('mode','SLAM V5 · 보정 GPU · '+(window.vggtGPU?.drawnMapPoints||d.gpu_scene?.map_points||0).toLocaleString()+'점');
  }else{
   if(d.follow_rgb)document.getElementById('camera-view').hidden=false;
   text('mode',d.follow_rgb?'RGB 카메라 시점':'자유 3D 시점');
  }
  text('status',d.playing?'▶ 재생 중 · RGB / 지도 동기화':'⏸ 정지 · 고화질');
  window.vggtRGBDebug={mode:visible?'native':'frames',serverTime:d.time,videoTime:video.currentTime,readyState:video.readyState,error:video.error?.code||null,generation:d.generation,playing:d.playing,viewMode:mode,stalled};
 }catch(error){console.debug('V5 playback',error)}finally{setTimeout(poll,100)}
}
poll();
})();
