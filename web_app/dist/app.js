/* Browser-only interface prototype. Synthetic geometry is explicit in every export. */
(()=>{
'use strict';
const C=TerraCore,$=id=>document.getElementById(id),all=s=>[...document.querySelectorAll(s)];
const state={time:52,duration:90,playing:false,speed:1,radius:.8,unknown:false,blocked:false,start:[10,26],goal:[62,26],set:'goal',mapMode:'cost',sceneMode:'rgb',height:6,yaw:-.63,pitch:.88,zoom:1,trajectory:true,selected:null,local:false,full:false};
let cells,dist,cost,route,components,visible=[],objectURL=null,toastTimer,lastFrame=0,lastMap=-1,mapRect=null,focusedElement=null;
const points=C.makePoints();
const fmt=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(1).padStart(4,'0')}`;
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(msg){$('toast').textContent=msg;$('toast').classList.remove('hide');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.add('hide'),4600)}
function modal(html){focusedElement=document.activeElement;$('modal-content').innerHTML=html;$('modal').classList.remove('hide');$('modal-close').focus()}
function closeModal(){$('modal').classList.add('hide');if(focusedElement)focusedElement.focus()}
function canvas(id){const el=$(id),r=el.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2),w=Math.max(1,r.width),h=Math.max(1,r.height);if(el.width!==Math.round(w*dpr)||el.height!==Math.round(h*dpr)){el.width=Math.round(w*dpr);el.height=Math.round(h*dpr)}const ctx=el.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return {ctx,w,h}}
function line(ctx,pts,color,width=1,dash=[]){ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([])}
function polygon(ctx,pts,fill,stroke){ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();if(fill){ctx.fillStyle=fill;ctx.fill()}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=.7;ctx.stroke()}}
function recompute(rebuild=true){
 if(rebuild){cells=C.grid(state.time,state.blocked);dist=C.clearance(cells);visible=points.filter(p=>C.observed(p[5],p[6],state.time));}
 cost=C.costmap(cells,dist,state.radius,state.unknown);route=C.search(cost,state.start,state.goal);components=C.components(cost);
 updateLabels();drawMap();drawScene();drawVoxels();renderObjects();
}
function updateLabels(){
 const known=cells.reduce((s,v)=>s+(v>=0),0),rev=Math.floor(state.time/6)+1;
 $('stat-points').textContent=visible.length.toLocaleString();$('stat-area').textContent=(known*C.RES*C.RES).toFixed(0);$('stat-known').textContent=`${Math.round(known/cells.length*100)}% observed`;
 $('stat-keyframes').textContent=Math.floor(state.time*2).toString().padStart(3,'0');$('stat-revision').textContent=`sample revision ${String(rev).padStart(2,'0')}`;
 $('stat-route').textContent=route.path.length?'Connected':'Disconnected';$('stat-route').style.color=route.path.length?'var(--mint)':'var(--red)';
 $('stat-components').textContent=`${components.count} component${components.count===1?'':'s'}`;$('stat-components').style.color=route.path.length?'var(--mint)':'var(--red)';
 $('map-rev').textContent=String(rev).padStart(3,'0');$('scene-revision').textContent=`MAP r${String(rev).padStart(3,'0')} · SYNTHETIC METRIC SCALE`;
 $('route-text').textContent=route.path.length?'Connected route':'Route unavailable';$('route-status').classList.toggle('bad',!route.path.length);
 $('route-detail').textContent=route.path.length?(state.unknown?'Unknown traversal enabled · provisional':'Known free space · inflated footprint'):route.reason;
 $('route-length').textContent=route.path.length?`${route.length.toFixed(1)} m`:'—';$('components').textContent=components.count;
 $('start-value').textContent=state.start.map(x=>((x+.5)*C.RES).toFixed(2)).join(', ')+' m';$('goal-value').textContent=state.goal.map(x=>((x+.5)*C.RES).toFixed(2)).join(', ')+' m';
 $('radius-value').textContent=state.radius.toFixed(2)+' m';$('height-value').textContent=state.height.toFixed(1)+' m';$('height-label').textContent=`HEIGHT SLICE · 0.0 - ${state.height.toFixed(1)} m`;
 $('unknown-label').textContent=state.unknown?'ALLOWED':'BLOCKED';$('unknown-label').style.color=state.unknown?'var(--orange)':'var(--muted)';
 $('elapsed').textContent=fmt(state.time);$('duration').textContent=fmt(state.duration);$('timeline').value=state.time;$('camera-time').textContent=fmt(state.time);$('frame-label').textContent=state.local?'LOCAL VIDEO':`SAMPLE FRAME ${String(Math.floor(state.time*20)).padStart(4,'0')}`;
}
function project(x,y,z,w,h,small=false){
 const yaw=small?-.69:state.yaw,pitch=small?.93:state.pitch;
 const cx=x-18,cy=y-13,rx=cx*Math.cos(yaw)-cy*Math.sin(yaw),ry=cx*Math.sin(yaw)+cy*Math.cos(yaw);
 const zz=ry*Math.sin(pitch)+z*Math.cos(pitch),depth=ry*Math.cos(pitch)-z*Math.sin(pitch);
 const unit=Math.min(w/43,h/29)*(small?1.23:state.zoom),persp=1/(1+depth/90);
 return [w*.5+rx*unit*persp,h*.56-zz*unit*persp,depth,unit*persp];
}
function drawScene(){
 const {ctx,w,h}=canvas('scene');const p=(x,y,z=0)=>project(x,y,z,w,h);
 const bg=ctx.createRadialGradient(w*.5,h*.5,0,w*.5,h*.5,w*.6);bg.addColorStop(0,'#152330');bg.addColorStop(1,'#0a121d');ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
 for(let x=0;x<=36;x+=2)line(ctx,[p(x,0).slice(0,2),p(x,26).slice(0,2)],'#243847',.5);
 for(let y=0;y<=26;y+=2)line(ctx,[p(0,y).slice(0,2),p(36,y).slice(0,2)],'#243847',.5);
 const render=visible.map(v=>({v,q:p(v[0],v[1],v[2])})).sort((a,b)=>b.q[2]-a.q[2]);
 for(const {v,q} of render){
   let col=v[3];if(state.sceneMode==='semantic')col=v[4]==='ground'?'#4da98c':C.boxes.find(b=>b.id===v[4])?.color||col;
   if(state.sceneMode==='height')col=`hsl(${170-v[2]*22},62%,${42+v[2]*3}%)`;
   if(state.selected&&v[4]!==state.selected)ctx.globalAlpha=.28;else ctx.globalAlpha=v[4]==='ground'?.5:.85;
   ctx.fillStyle=col;const s=Math.max(.8,Math.min(2.2,q[3]*.12));ctx.fillRect(q[0],q[1],s,s);
 }ctx.globalAlpha=1;
 if(state.blocked){for(let z=0;z<2;z+=.3)line(ctx,[p(18.5,1,z).slice(0,2),p(18.5,25,z).slice(0,2)],'#eb8d83',1.2)}
 if(state.trajectory){
   const tr=[];for(let u=0;u<=state.time;u+=1)tr.push(p(5+u/90*26,12.5+Math.sin(u/13)*2,.12).slice(0,2));line(ctx,tr,'#77e7c7',1.6);
   for(let u=0;u<=state.time;u+=6){const q=p(5+u/90*26,12.5+Math.sin(u/13)*2,.9);ctx.strokeStyle='#60bca4';ctx.lineWidth=.7;ctx.strokeRect(q[0]-2.3,q[1]-1.8,4.6,3.6)}
 }
 if(route.path.length)line(ctx,route.path.map(r=>p((r[0]+.5)*.5,(r[1]+.5)*.5,.13).slice(0,2)),'#edc58a',1.1,[4,3]);
 for(const b of C.boxes)if(C.observed(b.x+b.w/2,b.y+b.h/2,state.time)){
   const q=p((b.x+b.w/2)*.5,(b.y+b.h/2)*.5,b.z+.3);ctx.font='9px ui-sans-serif, sans-serif';const label=b.label.toUpperCase(),tw=ctx.measureText(label).width;
   ctx.fillStyle='#0a1421d9';ctx.fillRect(q[0]-tw/2-5,q[1]-10,tw+10,16);ctx.fillStyle=state.selected===b.id?'#a7ffdc':'#b7c6d7';ctx.fillText(label,q[0]-tw/2,q[1]+1);
 }
 const o=[w-42,h-39];line(ctx,[o,[o[0]+19,o[1]+6]],'#cc8a7d');line(ctx,[o,[o[0]-14,o[1]+9]],'#83bb9c');line(ctx,[o,[o[0],o[1]-20]],'#87bce5');ctx.font='8px sans-serif';ctx.fillStyle='#a4b2c1';ctx.fillText('X',o[0]+21,o[1]+9);ctx.fillText('Y',o[0]-21,o[1]+13);ctx.fillText('Z',o[0]-2,o[1]-24);
}
function drawCamera(){
 if(state.local)return;const {ctx,w,h}=canvas('camera');const horizon=h*.43;
 const sky=ctx.createLinearGradient(0,0,0,horizon);sky.addColorStop(0,'#5e7f91');sky.addColorStop(1,'#a8bbbc');ctx.fillStyle=sky;ctx.fillRect(0,0,w,horizon);
 polygon(ctx,[[0,horizon],[0,horizon-22],[w*.1,horizon-36],[w*.22,horizon-16],[w*.32,horizon-27],[w*.47,horizon-4],[w*.63,horizon-23],[w*.8,horizon-16],[w,horizon-27],[w,horizon]],'#5a7170');
 const earth=ctx.createLinearGradient(0,horizon,0,h);earth.addColorStop(0,'#6a796f');earth.addColorStop(1,'#777c6b');ctx.fillStyle=earth;ctx.fillRect(0,horizon,w,h-horizon);
 polygon(ctx,[[w*.45,horizon],[w*.57,horizon],[w*.95,h],[w*.12,h]],'#848776');
 for(let i=0;i<110;i++){const y=horizon+((i*93.7+state.time*2)%(h-horizon)),x=(i*71.3)%w;ctx.fillStyle=i%2?'#a8a59428':'#353e302b';ctx.fillRect(x,y,1+(y-horizon)/30,1)}
 // Perspective building and vehicle. These are generated illustrations.
 polygon(ctx,[[0,h*.28],[w*.32,h*.37],[w*.32,h*.65],[0,h*.77]],'#8a9e9d','#6e8382');
 polygon(ctx,[[0,h*.25],[w*.11,h*.19],[w*.35,h*.35],[w*.32,h*.4]],'#566f77','#6b848b');
 for(let u=0;u<6;u++){const x=w*.018+u*w*.052;line(ctx,[[x,h*.31+u*2.5],[x,h*.76-u*5.5]],'#6b84848f',1)}
 polygon(ctx,[[w*.72,h*.48],[w*.9,h*.46],[w*.96,h*.59],[w*.76,h*.62]],'#c2a37e','#d3bd9a');
 polygon(ctx,[[w*.75,h*.44],[w*.85,h*.43],[w*.88,h*.49],[w*.76,h*.51]],'#6c8b91','#b8c9c0');
 for(const [x,y] of [[.78,.615],[.92,.59]]){ctx.fillStyle='#263035';ctx.beginPath();ctx.ellipse(w*x,h*y,w*.022,h*.037,0,0,Math.PI*2);ctx.fill()}
 for(let i=0;i<4;i++){const x=w*(.48+i*.09),y=h*(.42-i*.005);ctx.fillStyle='#3f5944';ctx.beginPath();ctx.ellipse(x,y,8+i*3,13+i*2,-.2,0,Math.PI*2);ctx.fill();line(ctx,[[x,y],[x,h*.51]],'#60573f',2)}
 if(state.blocked)polygon(ctx,[[w*.38,h*.57],[w*.76,h*.54],[w*.78,h*.69],[w*.36,h*.73]],'#a07360','#d7a58d');
 ctx.strokeStyle='#e8b879';ctx.lineWidth=1.2;ctx.strokeRect(w*.71,h*.4,w*.26,h*.25);ctx.fillStyle='#14212ad9';ctx.fillRect(w*.71,h*.4-18,106,18);ctx.font='9px sans-serif';ctx.fillStyle='#e8c28f';ctx.fillText('VEHICLE · SAMPLE',w*.71+5,h*.4-6);
 line(ctx,[[w*.42,h*.95],[w*.47,h*.71],[w*.51,h*.56],[w*.53,h*.48]],'#8ef2d3',2,[7,5]);
 const shade=ctx.createRadialGradient(w/2,h/2,h*.2,w/2,h/2,w*.8);shade.addColorStop(0,'#0000');shade.addColorStop(1,'#0b142352');ctx.fillStyle=shade;ctx.fillRect(0,0,w,h);
}
function drawMap(){
 const {ctx,w,h}=canvas('map'),s=Math.min((w-42)/C.W,(h-27)/C.H),ox=(w-C.W*s)/2,oy=(h-C.H*s)/2;mapRect={s,ox,oy};
 for(let y=0;y<C.H;y++)for(let x=0;x<C.W;x++){
   const i=y*C.W+x,v=cells[i];let col;
   if(v<0)col=(x+y)%3===0?'#23303e':'#1b2734';
   else if(v===1)col='#b2c4d2';
   else if(state.mapMode==='cost'){
     const z=cost[i];if(z>=254)col='#ba746b';else if(z>100)col=`rgb(${75+z*.35},${64+z*.16},${51+z*.09})`;else col=`rgb(${18+z*.35},${44+z*.21},${44+z*.02})`;
   }else if(state.mapMode==='connectivity'){const n=components.labels[i];col=n<0?'#a66e67':['#2c7667','#536f9f','#8b6e9d','#9a844f'][n%4];}
   else col='#275346';
   ctx.fillStyle=col;ctx.fillRect(ox+x*s,oy+y*s,Math.ceil(s),Math.ceil(s));
 }
 for(let x=0;x<=C.W;x+=10)line(ctx,[[ox+x*s,oy],[ox+x*s,oy+C.H*s]],'#5f87931f',.7);
 for(let y=0;y<=C.H;y+=10)line(ctx,[[ox,oy+y*s],[ox+C.W*s,oy+y*s]],'#5f87931f',.7);
 const xy=r=>[ox+(r[0]+.5)*s,oy+(r[1]+.5)*s];
 if(route.path.length){line(ctx,route.path.map(xy),'#080d12',4);line(ctx,route.path.map(xy),'#7df1ca',2);}
 for(const [v,label,color] of [[state.start,'A','#9de9d0'],[state.goal,'B','#ebc58e']]){const q=xy(v);ctx.beginPath();ctx.arc(...q,7,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#111d26';ctx.lineWidth=2;ctx.stroke();ctx.fillStyle='#102019';ctx.font='bold 9px sans-serif';ctx.textAlign='center';ctx.fillText(label,q[0],q[1]+3);ctx.textAlign='start';}
 line(ctx,[[w-58,h-21],[w-58+s*10,h-21]],'#b7c7d7',2);ctx.font='8px monospace';ctx.fillStyle='#9aabba';ctx.fillText('N ↑',w-33,35);
 $('map-caption').textContent={occupancy:'2D OCCUPANCY · FREE / OCCUPIED / UNKNOWN',cost:'COST MAP · 0.50 m / cell',connectivity:`CONNECTIVITY · ${components.count} FREE-SPACE COMPONENTS`}[state.mapMode];
}
function drawVoxels(){
 const {ctx,w,h}=canvas('voxels');let n=0;const occupiedVoxels=new Map();
 for(const v of visible)if(v[4]!=='ground'&&v[2]<=state.height){const k=[Math.floor(v[0]/.5),Math.floor(v[1]/.5),Math.floor(v[2]/.5)].join(',');if(!occupiedVoxels.has(k))occupiedVoxels.set(k,v)}
 const sorted=[...occupiedVoxels.values()].map(v=>({v,q:project(v[0],v[1],v[2],w,h,true)})).sort((a,b)=>b.q[2]-a.q[2]);
 for(const {v,q} of sorted){const size=Math.max(1.5,q[3]*.43);ctx.fillStyle=v[4]===state.selected?'#b5ffdb':v[3];ctx.globalAlpha=.67;ctx.fillRect(q[0],q[1],size,size);ctx.strokeStyle='#13232c';ctx.lineWidth=.3;ctx.strokeRect(q[0],q[1],size,size);n++;}ctx.globalAlpha=1;
 const p=(x,y)=>project(x,y,0,w,h,true).slice(0,2);for(let x=0;x<=36;x+=4)line(ctx,[p(x,0),p(x,26)],'#304858',.5);for(let y=0;y<=26;y+=4)line(ctx,[p(0,y),p(36,y)],'#304858',.5);
 $('voxel-count').textContent=n.toLocaleString()+' occupied';
}
function renderObjects(){
 const text=$('search').value.trim().toLowerCase();const objs=C.boxes.filter(b=>C.observed(b.x+b.w/2,b.y+b.h/2,state.time)&&(b.label.toLowerCase().includes(text)||b.kind.includes(text)));
 $('objects-count').textContent=objs.length+' sample objects';$('object-list').innerHTML=objs.length?objs.map(b=>`<button class="object-row" data-object="${b.id}" aria-pressed="${state.selected===b.id}"><span><i class="swatch" style="background:${b.color}"></i>${b.label}</span><span class="muted mono">${state.selected===b.id?'●':'↗'}</span></button>`).join(''):'<div class="empty">일치하는 예시 객체가 없습니다.</div>';
 all('[data-object]').forEach(b=>b.onclick=()=>{state.selected=state.selected===b.dataset.object?null:b.dataset.object;$('selected-object').textContent=state.selected?'SELECTED · '+C.boxes.find(o=>o.id===state.selected).label:'Sample point cloud · 0 objects selected';renderObjects();drawScene();drawVoxels()});
}
function setPlaying(value){state.playing=value;$('play-icon').innerHTML=`<use href="#i-${value?'pause':'play'}"/>`;$('play').setAttribute('aria-label',value?'Pause replay':'Play replay');if(state.local){if(value)$('local-video').play().catch(()=>{setPlaying(false);toast('이 브라우저에서 영상을 재생할 수 없습니다.')});else $('local-video').pause()}}
function seek(t){state.time=Math.max(0,Math.min(state.duration,t));if(state.local)$('local-video').currentTime=state.time;recompute();drawCamera();}
function help(){modal(`<h2 id="modal-title">TerraScene 사용법</h2><p>이 화면은 실제 모델을 연결하기 전에 작업 흐름을 검토하기 위한 시제품입니다. 장면·객체·관측 영역·키프레임은 생성된 예시이며, 비용 지도와 경로 탐색은 예시 격자에서 브라우저가 직접 계산합니다. 객체의 신뢰도·추론 시간·모델 성능은 측정하지 않습니다.</p><p>재생 막대로 관측 영역 변화를 확인하세요. 지도에서 시작점과 목적지를 지정하고 차량의 원형 점유 반경을 조절할 수 있습니다. 두 번째 시나리오는 통로를 완전히 차단합니다. 3차원 장면은 끌어 회전하고 휠로 확대합니다. 로컬 영상은 브라우저에서 재생하며 업로드하지 않습니다. 로컬 영상과 예시 지도 사이에는 추론 연결이 없습니다.</p><h3>용어 설명</h3><dl><dt>VGGT</dt><dd>Visual Geometry Grounded Transformer: 여러 이미지에서 카메라와 장면의 기하 구조를 예측하는 모델.</dd><dt>SLAM</dt><dd>Simultaneous Localization and Mapping: 자신의 위치 추정과 지도 생성을 함께 수행하는 기술.</dd><dt>3D / 2D</dt><dd>Three-dimensional / Two-dimensional: 3차원 / 2차원.</dd><dt>UI</dt><dd>User Interface: 사용자 조작 화면.</dd><dt>RGB</dt><dd>Red, Green, Blue: 빨강·초록·파랑으로 표현한 영상 색상.</dd><dt>Occupancy map</dt><dd>공간을 점유·비점유·미관측 상태로 구분한 지도. 이 시제품의 3차원 화면은 점유 표면 예시만 표시합니다.</dd><dt>Cost map</dt><dd>장애물, 장애물과의 거리, 차량 크기에 따라 이동 비용을 나타내는 지도.</dd><dt>A*</dt><dd>A-star: 목적지까지의 예상 거리를 이용하는 경로 탐색 알고리즘. 이 시제품은 8방향 이동과 모서리 통과 금지를 적용합니다.</dd><dt>Voxel</dt><dd>Volume element: 3차원 공간을 나눈 작은 격자 단위.</dd><dt>Map revision</dt><dd>동일한 지형·비용·경로 결과를 묶는 지도 버전. 시제품의 버전은 재생 시간으로 생성합니다.</dd></dl><div class="help-links"><a href="plan.html" target="_blank" rel="noopener">전체 개발 계획서 ↗</a><a href="https://github.com/MIT-SPARK/VGGT-SLAM" target="_blank" rel="noopener">공식 저장소 ↗</a></div>`)}
function download(name,text,type='application/json'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportData(){modal(`<h2 id="modal-title">Export sample results</h2><p>아래 파일은 현재 화면의 합성 지도와 실제 격자 경로 계산 결과입니다. 로컬 영상에서 복원한 결과가 아닙니다. 메타데이터에 <b>synthetic=true</b>를 기록합니다.</p><div class="export-options"><button id="export-json"><b>Session + map</b><small>JSON · cells, costs, path, settings</small></button><button id="export-ply"><b>Visible point cloud</b><small>PLY · sample colored points</small></button></div><p>JSON (JavaScript Object Notation)은 구조화된 데이터 형식이며, PLY (Polygon File Format)는 점군·표면 데이터를 저장하는 형식입니다. 모델 체크포인트와 실제 영상은 포함하지 않습니다.</p>`);
 $('export-json').onclick=()=>{const result={schema_version:'0.1',synthetic:true,inference_connected:false,source:state.local?'local_video_unrelated_to_sample_map':'synthetic_replay',time_s:state.time,map_revision:Math.floor(state.time/6)+1,grid:{width:C.W,height:C.H,resolution_m:C.RES,origin_m:[0,0],axis:'x right, y down in map canvas; z up',states:Array.from(cells),state_encoding:{unknown:-1,free:0,occupied:1},costs:Array.from(cost)},footprint:{model:'circle',radius_m:state.radius},unknown_traversal_allowed:state.unknown,route:{...route,start:state.start,goal:state.goal,grid_coordinates:true},components:components.count};download('terrascene_sample_session.json',JSON.stringify(result,null,2));toast('현재 예시 지도와 경로를 저장했습니다.')};
 $('export-ply').onclick=()=>{const rgb=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));const header=`ply\nformat ascii 1.0\ncomment synthetic_sample_not_vggt_inference\nelement vertex ${visible.length}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n`;download('terrascene_sample_points.ply',header+visible.map(p=>`${p[0].toFixed(3)} ${p[1].toFixed(3)} ${p[2].toFixed(3)} ${rgb(p[3]).join(' ')}`).join('\n'),'text/plain');toast('보이는 합성 점군을 저장했습니다.')};
}
$('play').onclick=()=>{if(state.time>=state.duration)seek(0);setPlaying(!state.playing)};$('restart').onclick=()=>seek(0);$('timeline').oninput=e=>seek(Number(e.target.value));$('speed').onchange=e=>{state.speed=Number(e.target.value);if(state.local)$('local-video').playbackRate=state.speed};
$('radius').oninput=e=>{state.radius=Number(e.target.value);recompute(false)};$('height').oninput=e=>{state.height=Number(e.target.value);updateLabels();drawVoxels()};$('unknown').onchange=e=>{state.unknown=e.target.checked;recompute(false);if(state.unknown)toast('미관측 구역을 허용한 경로는 잠정 경로입니다.')};
$('scenario').onchange=e=>{
 if(state.local){setPlaying(false);state.local=false;$('local-video').classList.add('hide');$('camera').classList.remove('hide');if(objectURL)URL.revokeObjectURL(objectURL);objectURL=null;$('local-video').removeAttribute('src');$('input-name').textContent='research_yard · generated sample';$('video-source').textContent='Synthetic camera preview';$('camera-label').textContent='SYNTHETIC · FORWARD CAMERA';$('camera-state').classList.remove('hide');$('transport-title').textContent='SAMPLE REPLAY';$('data-notice').textContent='합성 장면을 이용한 화면 시제품입니다. VGGT-SLAM 추론 결과가 아니며, 모델은 연결되어 있지 않습니다.'}
 state.duration=90;$('timeline').max=90;state.blocked=e.target.value==='blocked';state.radius=e.target.value==='narrow'?2.5:.8;$('radius').value=state.radius;state.start=[10,26];state.goal=[62,26];state.time=52;lastMap=-1;recompute();drawCamera();toast(state.blocked?'가상 차단벽을 추가했습니다. 연결성이 다시 계산됩니다.':'예시 장면을 불러왔습니다.')
};
all('#scene-tabs button').forEach(b=>b.onclick=()=>{state.sceneMode=b.dataset.mode;all('#scene-tabs button').forEach(x=>x.classList.toggle('active',x===b));drawScene()});
all('#map-tabs button').forEach(b=>b.onclick=()=>{state.mapMode=b.dataset.mode;all('#map-tabs button').forEach(x=>x.classList.toggle('active',x===b));drawMap()});
$('set-start').onclick=()=>setPointMode('start');$('set-goal').onclick=()=>setPointMode('goal');function setPointMode(m){state.set=m;$('set-start').classList.toggle('active',m==='start');$('set-goal').classList.toggle('active',m==='goal');$('map-mode-label').textContent='CLICK TO SET '+m.toUpperCase()}
$('swap').onclick=()=>{[state.start,state.goal]=[state.goal,state.start];recompute(false)};$('map').onclick=e=>{if(!mapRect)return;const r=$('map').getBoundingClientRect(),x=Math.floor((e.clientX-r.left-mapRect.ox)/mapRect.s),y=Math.floor((e.clientY-r.top-mapRect.oy)/mapRect.s);if(x<0||x>=C.W||y<0||y>=C.H)return;state[state.set]=[x,y];recompute(false)};
$('search').oninput=renderObjects;$('toggle-trajectory').onclick=e=>{state.trajectory=!state.trajectory;e.target.classList.toggle('active',state.trajectory);e.target.setAttribute('aria-pressed',state.trajectory);drawScene()};$('reset-view').onclick=()=>{state.yaw=-.63;state.pitch=.88;state.zoom=1;drawScene()};
let drag=null;$('scene').onpointerdown=e=>{drag=[e.clientX,e.clientY,state.yaw,state.pitch];$('scene').setPointerCapture(e.pointerId)};$('scene').onpointermove=e=>{if(!drag)return;state.yaw=drag[2]+(e.clientX-drag[0])*.006;state.pitch=Math.max(.15,Math.min(1.48,drag[3]+(e.clientY-drag[1])*.004));drawScene()};$('scene').onpointerup=()=>drag=null;$('scene').onpointercancel=()=>drag=null;$('scene').addEventListener('wheel',e=>{e.preventDefault();state.zoom=Math.max(.5,Math.min(2.5,state.zoom*Math.exp(-e.deltaY*.001)));drawScene()},{passive:false});
function focusScene(){state.full=!state.full;$('workspace').classList.toggle('mode-full',state.full);setTimeout(drawScene,50)}$('expand').onclick=focusScene;$('nav-scene').onclick=focusScene;$('nav-studio').onclick=()=>{state.full=false;$('workspace').classList.remove('mode-full');window.scrollTo({top:0,behavior:'smooth'});setTimeout(drawScene,50)};$('nav-maps').onclick=()=>$('mapping').scrollIntoView({behavior:'smooth',block:'center'});
for(const id of ['help','glossary','about-data'])$(id).onclick=help;for(const id of ['export','nav-export'])$(id).onclick=exportData;
$('modal-close').onclick=closeModal;$('modal').onclick=e=>{if(e.target===$('modal'))closeModal()};document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if(e.key==='Tab'&&!$('modal').classList.contains('hide')){const focusables=[...$('modal').querySelectorAll('a,button,input,select,[tabindex]')].filter(x=>!x.disabled);if(!focusables.length)return;const first=focusables[0],last=focusables[focusables.length-1];if(e.shiftKey&&document.activeElement===first){last.focus();e.preventDefault()}else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault()}}if(e.code==='Space'&&!/INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName)&&$('modal').classList.contains('hide')){e.preventDefault();setPlaying(!state.playing)}});
$('import-video').onclick=()=>$('file').click();$('file').onchange=e=>{const f=e.target.files[0];if(!f)return;setPlaying(false);if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(f);const v=$('local-video');v.src=objectURL;v.onloadedmetadata=()=>{if(!Number.isFinite(v.duration)||v.duration<=0){toast('재생 길이를 확인할 수 없는 파일입니다.');return}state.local=true;state.time=0;state.duration=v.duration;v.classList.remove('hide');$('camera').classList.add('hide');$('timeline').max=state.duration;v.playbackRate=state.speed;$('video-source').textContent='Local video · playback only';$('input-name').textContent=f.name;$('camera-label').textContent='LOCAL VIDEO · NO INFERENCE';$('camera-state').classList.add('hide');$('transport-title').textContent='LOCAL VIDEO';$('data-notice').textContent='로컬 영상은 재생만 합니다. 아래 지도·객체·3차원 장면은 영상과 무관한 합성 예시입니다. 영상 파일은 서버로 전송하지 않습니다.';recompute();toast('로컬 영상을 열었습니다. 지도는 합성 예시로 유지됩니다.')};v.onerror=()=>toast('영상을 열 수 없습니다. 브라우저가 지원하는 형식을 선택하세요.');};
window.addEventListener('resize',()=>{drawScene();drawCamera();drawMap();drawVoxels()});
function frame(now){const dt=Math.min((now-lastFrame)/1000,.1)||0;lastFrame=now;if(state.playing){state.time=state.local?$('local-video').currentTime:Math.min(state.duration,state.time+dt*state.speed);if(state.time>=state.duration||state.local&&$('local-video').ended)setPlaying(false);if(Math.floor(state.time*2)!==lastMap){lastMap=Math.floor(state.time*2);recompute();drawCamera()}else updateLabels()}requestAnimationFrame(frame)}
recompute();drawCamera();requestAnimationFrame(frame);
// A read-only hook for controlled integration and browser diagnostics.
window.TerraScenePreview={getState:()=>({...state,synthetic:true,inference_connected:false}),getRoute:()=>({...route}),getGeometryCount:()=>points.length};
})();
