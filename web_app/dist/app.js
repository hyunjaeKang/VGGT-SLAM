/* Browser-only interface prototype. Synthetic geometry is explicit in every export. */
(()=>{
'use strict';
const C=TerraCore,$=id=>document.getElementById(id),all=s=>[...document.querySelectorAll(s)];
const state={time:52,duration:90,playing:false,speed:1,radius:.8,unknown:false,blocked:false,start:[10,26],goal:[62,26],set:'goal',mapMode:'cost',sceneMode:'rgb',height:6,yaw:-.63,pitch:.88,zoom:1,trajectory:true,selected:null,local:false,full:false};
let cells,dist,cost,route,components,visible=[],objectURL=null,toastTimer,lastFrame=0,lastMap=-1,mapRect=null,focusedElement=null;
const points=C.makePoints();
const objectNames={'Storage building':'저장 건물','Utility vehicle':'작업 차량','Equipment crates':'장비 상자','Tree cluster':'나무 군집','Boundary wall':'경계 벽'};
const objectLabel=b=>b.label+' / '+objectNames[b.label];
const reasonLabel=reason=>({'Outside map':'Outside map / 지도 범위 밖','Endpoint blocked or unobserved':'Endpoint blocked or unobserved / 출발점 또는 목표점이 차단되었거나 미관측 상태','No connected route':'No connected route / 연결된 경로 없음','Connected':'Connected / 연결됨'}[reason]||reason);

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
 $('stat-points').textContent=visible.length.toLocaleString();$('stat-area').textContent=(known*C.RES*C.RES).toFixed(0);$('stat-known').textContent=`${Math.round(known/cells.length*100)}% observed / 관측됨`;
 $('stat-keyframes').textContent=Math.floor(state.time*2).toString().padStart(3,'0');$('stat-revision').textContent=`sample revision / 예시 버전 ${String(rev).padStart(2,'0')}`;
 $('stat-route').textContent=route.path.length?'Connected / 연결됨':'Disconnected / 연결 끊김';$('stat-route').style.color=route.path.length?'var(--mint)':'var(--red)';
 $('stat-components').textContent=`${components.count} component${components.count===1?'':'s'} / 연결 영역 ${components.count}개`;$('stat-components').style.color=route.path.length?'var(--mint)':'var(--red)';
 $('map-rev').textContent=String(rev).padStart(3,'0');$('scene-revision').textContent=`MAP / 지도 r${String(rev).padStart(3,'0')} · SYNTHETIC METRIC SCALE / 합성 미터 단위`;
 $('route-text').textContent=route.path.length?'Connected route / 연결된 경로':'Route unavailable / 경로 없음';$('route-status').classList.toggle('bad',!route.path.length);
 $('route-detail').textContent=route.path.length?(state.unknown?'Unknown traversal enabled · provisional / 미관측 공간 통과 허용 · 잠정 경로':'Known free space · inflated footprint / 관측된 비점유 공간 · 확장된 점유 반경'):reasonLabel(route.reason);
 $('route-length').textContent=route.path.length?`${route.length.toFixed(1)} m`:'—';$('components').textContent=components.count;
 $('start-value').textContent=state.start.map(x=>((x+.5)*C.RES).toFixed(2)).join(', ')+' m';$('goal-value').textContent=state.goal.map(x=>((x+.5)*C.RES).toFixed(2)).join(', ')+' m';
 $('radius-value').textContent=state.radius.toFixed(2)+' m';$('height-value').textContent=state.height.toFixed(1)+' m';$('height-label').textContent=`HEIGHT SLICE / 높이 범위 · 0.0 - ${state.height.toFixed(1)} m`;
 $('unknown-label').textContent=state.unknown?'ALLOWED / 허용':'BLOCKED / 차단';$('unknown-label').style.color=state.unknown?'var(--orange)':'var(--muted)';
 $('elapsed').textContent=fmt(state.time);$('duration').textContent=fmt(state.duration);$('timeline').value=state.time;$('camera-time').textContent=fmt(state.time);$('frame-label').textContent=state.local?'LOCAL VIDEO / 로컬 영상':`SAMPLE FRAME / 예시 프레임 ${String(Math.floor(state.time*20)).padStart(4,'0')}`;
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
   const q=p((b.x+b.w/2)*.5,(b.y+b.h/2)*.5,b.z+.3);ctx.font='9px ui-sans-serif, sans-serif';const label=objectLabel(b),tw=ctx.measureText(label).width;
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
 ctx.strokeStyle='#e8b879';ctx.lineWidth=1.2;ctx.strokeRect(w*.71,h*.4,w*.26,h*.25);ctx.fillStyle='#14212ad9';ctx.font='9px sans-serif';const cameraLabel='VEHICLE SAMPLE / 차량 예시',labelWidth=ctx.measureText(cameraLabel).width+10,labelX=Math.min(w*.71,w-labelWidth-5);ctx.fillRect(labelX,h*.4-18,labelWidth,18);ctx.fillStyle='#e8c28f';ctx.fillText(cameraLabel,labelX+5,h*.4-6);
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
 line(ctx,[[w-58,h-21],[w-58+s*10,h-21]],'#b7c7d7',2);ctx.font='8px monospace';ctx.fillStyle='#9aabba';ctx.fillText('N / 북 ↑',w-33,35);
 $('map-caption').textContent={occupancy:'2D OCCUPANCY / 2차원 점유 · FREE / 비점유 · OCCUPIED / 점유 · UNKNOWN / 미관측',cost:'COST MAP / 비용 지도 · 0.50 m / cell / 셀',connectivity:`CONNECTIVITY / 연결성 · ${components.count} FREE-SPACE COMPONENTS / 비점유 연결 영역`}[state.mapMode];
}
function drawVoxels(){
 const {ctx,w,h}=canvas('voxels');let n=0;const occupiedVoxels=new Map();
 for(const v of visible)if(v[4]!=='ground'&&v[2]<=state.height){const k=[Math.floor(v[0]/.5),Math.floor(v[1]/.5),Math.floor(v[2]/.5)].join(',');if(!occupiedVoxels.has(k))occupiedVoxels.set(k,v)}
 const sorted=[...occupiedVoxels.values()].map(v=>({v,q:project(v[0],v[1],v[2],w,h,true)})).sort((a,b)=>b.q[2]-a.q[2]);
 for(const {v,q} of sorted){const size=Math.max(1.5,q[3]*.43);ctx.fillStyle=v[4]===state.selected?'#b5ffdb':v[3];ctx.globalAlpha=.67;ctx.fillRect(q[0],q[1],size,size);ctx.strokeStyle='#13232c';ctx.lineWidth=.3;ctx.strokeRect(q[0],q[1],size,size);n++;}ctx.globalAlpha=1;
 const p=(x,y)=>project(x,y,0,w,h,true).slice(0,2);for(let x=0;x<=36;x+=4)line(ctx,[p(x,0),p(x,26)],'#304858',.5);for(let y=0;y<=26;y+=4)line(ctx,[p(0,y),p(36,y)],'#304858',.5);
 $('voxel-count').textContent=n.toLocaleString()+' occupied / 점유 복셀';
}
function renderObjects(){
 const text=$('search').value.trim().toLowerCase();const objs=C.boxes.filter(b=>C.observed(b.x+b.w/2,b.y+b.h/2,state.time)&&(objectLabel(b).toLowerCase().includes(text)||b.kind.includes(text)));
 $('objects-count').textContent=objs.length+' sample objects / 예시 객체';$('object-list').innerHTML=objs.length?objs.map(b=>`<button class="object-row" data-object="${b.id}" aria-pressed="${state.selected===b.id}"><span><i class="swatch" style="background:${b.color}"></i>${objectLabel(b)}</span><span class="muted mono">${state.selected===b.id?'●':'↗'}</span></button>`).join(''):'<div class="empty">No matching sample objects. / 일치하는 예시 객체가 없습니다.</div>';
 all('[data-object]').forEach(b=>b.onclick=()=>{state.selected=state.selected===b.dataset.object?null:b.dataset.object;$('selected-object').textContent=state.selected?'SELECTED / 선택됨 · '+objectLabel(C.boxes.find(o=>o.id===state.selected)):'Sample point cloud · 0 objects selected / 예시 점군 · 선택 객체 0개';renderObjects();drawScene();drawVoxels()});
}
function setPlaying(value){state.playing=value;$('play-icon').innerHTML=`<use href="#i-${value?'pause':'play'}"/>`;$('play').setAttribute('aria-label',value?'Pause replay / 재생 일시정지':'Play replay / 재생');if(state.local){if(value)$('local-video').play().catch(()=>{setPlaying(false);toast('This browser cannot play the video. / 이 브라우저에서 영상을 재생할 수 없습니다.')});else $('local-video').pause()}}
function seek(t){state.time=Math.max(0,Math.min(state.duration,t));if(state.local)$('local-video').currentTime=state.time;recompute();drawCamera();}
function help(){modal(`<h2 id="modal-title">TerraScene help / TerraScene 사용법</h2>
<p>This prototype lets you review the workflow before connecting a model. Scenes, objects, observed regions and keyframes are synthetic. The browser computes cost maps and routes on the sample grid. Object confidence, inference time and model performance are not measured.<br>이 화면은 실제 모델을 연결하기 전에 작업 흐름을 검토하기 위한 시제품입니다. 장면·객체·관측 영역·키프레임은 합성 예시이며, 비용 지도와 경로는 예시 격자에서 브라우저가 계산합니다. 객체 신뢰도·추론 시간·모델 성능은 측정하지 않습니다.</p>
<p>Use the timeline to inspect observed regions. Click the map to set a start or goal, and adjust the circular footprint radius. The second scenario blocks the passage. Drag the 3D scene to orbit and scroll to zoom. Local video plays in the browser without upload and has no inference connection to the sample map.<br>재생 막대로 관측 영역을 확인하세요. 지도에서 출발점과 목표점을 지정하고 원형 점유 반경을 조절할 수 있습니다. 두 번째 시나리오는 통로를 차단합니다. 3차원 장면은 끌어서 회전하고 스크롤로 확대합니다. 로컬 영상은 업로드 없이 브라우저에서 재생하며 예시 지도와 추론으로 연결되지 않습니다.</p>
<h3>Glossary / 용어 설명</h3><dl>
<dt>VGGT</dt><dd>Visual Geometry Grounded Transformer: predicts camera and scene geometry from multiple images. / 여러 이미지에서 카메라와 장면의 기하 구조를 예측하는 모델.</dd>
<dt>SLAM / 동시 위치 추정 및 지도 작성</dt><dd>Simultaneous Localization and Mapping: estimates position while building a map. / 자신의 위치 추정과 지도 생성을 함께 수행하는 기술.</dd>
<dt>3D / 2D · 3차원 / 2차원</dt><dd>Three-dimensional / two-dimensional space. / 3차원 공간과 2차원 공간.</dd>
<dt>UI / 사용자 인터페이스</dt><dd>User Interface: the controls and displays used to operate software. / 소프트웨어를 조작하는 화면과 도구.</dd>
<dt>RGB / 빨강·초록·파랑</dt><dd>Red, Green, Blue: the three channels used to represent image colors. / 영상 색상을 표현하는 세 가지 색상 채널.</dd>
<dt>Occupancy map / 점유 지도</dt><dd>A map of occupied, free and unknown space. The 3D prototype shows occupied surface samples only. / 점유·비점유·미관측 공간을 구분한 지도. 3차원 시제품은 점유 표면 예시만 표시합니다.</dd>
<dt>Cost map / 비용 지도</dt><dd>A map of travel costs based on obstacles, clearance and footprint size. / 장애물, 장애물과의 거리, 점유 크기에 따른 이동 비용 지도.</dd>
<dt>A* / 에이스타</dt><dd>A-star: a path search using estimated distance to the goal. This prototype uses eight-connected moves without corner cutting. / 목표점까지의 예상 거리를 이용하는 경로 탐색. 이 시제품은 8방향 이동을 사용하며 모서리 통과를 금지합니다.</dd>
<dt>Voxel / 복셀</dt><dd>Volume element: a small 3D grid cell. / 3차원 공간을 나눈 작은 격자 단위.</dd>
<dt>Map revision / 지도 버전</dt><dd>A version grouping matching terrain, costs and route results. Prototype revisions follow replay time. / 같은 지형·비용·경로 결과를 묶는 버전. 시제품의 버전은 재생 시간으로 생성합니다.</dd>
</dl><div class="help-links"><a href="plan.html" target="_blank" rel="noopener">Full development plan / 전체 개발 계획서 ↗</a><a href="https://github.com/MIT-SPARK/VGGT-SLAM" target="_blank" rel="noopener">Official repository / 공식 저장소 ↗</a></div>`)}

function download(name,text,type='application/json'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportData(){modal(`<h2 id="modal-title">Export sample results / 예시 결과 내보내기</h2><p>These files contain the current synthetic map and computed grid route, not a reconstruction of local video. Metadata records <b>synthetic=true</b>.<br>아래 파일은 현재 화면의 합성 지도와 격자 경로 계산 결과입니다. 로컬 영상의 복원 결과가 아닙니다. 메타데이터에 <b>synthetic=true</b>를 기록합니다.</p><div class="export-options"><button id="export-json"><b>Session + map / 세션과 지도</b><small>JSON · cells, costs, path, settings / 셀·비용·경로·설정</small></button><button id="export-ply"><b>Visible point cloud / 표시된 점군</b><small>PLY · sample colored points / 색상 점군 예시</small></button></div><p>JSON (JavaScript Object Notation) stores structured data; PLY (Polygon File Format) stores point clouds and surfaces. Model checkpoints and video files are excluded.<br>JSON (JavaScript Object Notation)은 구조화된 데이터 형식이며, PLY (Polygon File Format)는 점군·표면 데이터를 저장하는 형식입니다. 모델 체크포인트와 영상 파일은 포함하지 않습니다.</p>`);
 $('export-json').onclick=()=>{const result={schema_version:'0.1',synthetic:true,inference_connected:false,source:state.local?'local_video_unrelated_to_sample_map':'synthetic_replay',time_s:state.time,map_revision:Math.floor(state.time/6)+1,grid:{width:C.W,height:C.H,resolution_m:C.RES,origin_m:[0,0],axis:'x right, y down in map canvas; z up',states:Array.from(cells),state_encoding:{unknown:-1,free:0,occupied:1},costs:Array.from(cost)},footprint:{model:'circle',radius_m:state.radius},unknown_traversal_allowed:state.unknown,route:{...route,start:state.start,goal:state.goal,grid_coordinates:true},components:components.count};download('terrascene_sample_session.json',JSON.stringify(result,null,2));toast('Saved the current sample map and route. / 현재 예시 지도와 경로를 저장했습니다.')};
 $('export-ply').onclick=()=>{const rgb=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));const header=`ply\nformat ascii 1.0\ncomment synthetic_sample_not_vggt_inference\nelement vertex ${visible.length}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n`;download('terrascene_sample_points.ply',header+visible.map(p=>`${p[0].toFixed(3)} ${p[1].toFixed(3)} ${p[2].toFixed(3)} ${rgb(p[3]).join(' ')}`).join('\n'),'text/plain');toast('Saved the visible synthetic point cloud. / 보이는 합성 점군을 저장했습니다.')};
}
$('play').onclick=()=>{if(state.time>=state.duration)seek(0);setPlaying(!state.playing)};$('restart').onclick=()=>seek(0);$('timeline').oninput=e=>seek(Number(e.target.value));$('speed').onchange=e=>{state.speed=Number(e.target.value);if(state.local)$('local-video').playbackRate=state.speed};
$('radius').oninput=e=>{state.radius=Number(e.target.value);recompute(false)};$('height').oninput=e=>{state.height=Number(e.target.value);updateLabels();drawVoxels()};$('unknown').onchange=e=>{state.unknown=e.target.checked;recompute(false);if(state.unknown)toast('Routes through unknown space are provisional. / 미관측 구역을 허용한 경로는 잠정 경로입니다.')};
$('scenario').onchange=e=>{
 if(state.local){setPlaying(false);state.local=false;$('local-video').classList.add('hide');$('camera').classList.remove('hide');if(objectURL)URL.revokeObjectURL(objectURL);objectURL=null;$('local-video').removeAttribute('src');$('input-name').textContent='research_yard · generated sample / 생성된 연구장 예시';$('video-source').textContent='Synthetic camera preview / 합성 카메라 미리보기';$('camera-label').textContent='SYNTHETIC · FORWARD CAMERA / 합성 전방 카메라';$('camera-state').classList.remove('hide');$('transport-title').textContent='SAMPLE REPLAY / 예시 재생';$('data-notice').textContent='This interface uses synthetic scenes. It is not VGGT-SLAM inference output; no model is connected. / 합성 장면을 이용한 화면 시제품입니다. VGGT-SLAM 추론 결과가 아니며, 모델은 연결되어 있지 않습니다.'}
 state.duration=90;$('timeline').max=90;state.blocked=e.target.value==='blocked';state.radius=e.target.value==='narrow'?2.5:.8;$('radius').value=state.radius;state.start=[10,26];state.goal=[62,26];state.time=52;lastMap=-1;recompute();drawCamera();toast(state.blocked?'Added a synthetic barrier. Connectivity is recalculated. / 가상 차단벽을 추가했습니다. 연결성이 다시 계산됩니다.':'Loaded the sample scene. / 예시 장면을 불러왔습니다.')
};
all('#scene-tabs button').forEach(b=>b.onclick=()=>{state.sceneMode=b.dataset.mode;all('#scene-tabs button').forEach(x=>x.classList.toggle('active',x===b));drawScene()});
all('#map-tabs button').forEach(b=>b.onclick=()=>{state.mapMode=b.dataset.mode;all('#map-tabs button').forEach(x=>x.classList.toggle('active',x===b));drawMap()});
$('set-start').onclick=()=>setPointMode('start');$('set-goal').onclick=()=>setPointMode('goal');function setPointMode(m){state.set=m;$('set-start').classList.toggle('active',m==='start');$('set-goal').classList.toggle('active',m==='goal');$('map-mode-label').textContent=(m==='start'?'CLICK TO SET START / 클릭하여 출발점 지정':'CLICK TO SET GOAL / 클릭하여 목표점 지정')}
$('swap').onclick=()=>{[state.start,state.goal]=[state.goal,state.start];recompute(false)};$('map').onclick=e=>{if(!mapRect)return;const r=$('map').getBoundingClientRect(),x=Math.floor((e.clientX-r.left-mapRect.ox)/mapRect.s),y=Math.floor((e.clientY-r.top-mapRect.oy)/mapRect.s);if(x<0||x>=C.W||y<0||y>=C.H)return;state[state.set]=[x,y];recompute(false)};
$('search').oninput=renderObjects;$('toggle-trajectory').onclick=e=>{state.trajectory=!state.trajectory;e.target.classList.toggle('active',state.trajectory);e.target.setAttribute('aria-pressed',state.trajectory);drawScene()};$('reset-view').onclick=()=>{state.yaw=-.63;state.pitch=.88;state.zoom=1;drawScene()};
let drag=null;$('scene').onpointerdown=e=>{drag=[e.clientX,e.clientY,state.yaw,state.pitch];$('scene').setPointerCapture(e.pointerId)};$('scene').onpointermove=e=>{if(!drag)return;state.yaw=drag[2]+(e.clientX-drag[0])*.006;state.pitch=Math.max(.15,Math.min(1.48,drag[3]+(e.clientY-drag[1])*.004));drawScene()};$('scene').onpointerup=()=>drag=null;$('scene').onpointercancel=()=>drag=null;$('scene').addEventListener('wheel',e=>{e.preventDefault();state.zoom=Math.max(.5,Math.min(2.5,state.zoom*Math.exp(-e.deltaY*.001)));drawScene()},{passive:false});
function focusScene(){state.full=!state.full;$('workspace').classList.toggle('mode-full',state.full);setTimeout(drawScene,50)}$('expand').onclick=focusScene;$('nav-scene').onclick=focusScene;$('nav-studio').onclick=()=>{state.full=false;$('workspace').classList.remove('mode-full');window.scrollTo({top:0,behavior:'smooth'});setTimeout(drawScene,50)};$('nav-maps').onclick=()=>$('mapping').scrollIntoView({behavior:'smooth',block:'center'});
for(const id of ['help','glossary','about-data'])$(id).onclick=help;for(const id of ['export','nav-export'])$(id).onclick=exportData;
$('modal-close').onclick=closeModal;$('modal').onclick=e=>{if(e.target===$('modal'))closeModal()};document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if(e.key==='Tab'&&!$('modal').classList.contains('hide')){const focusables=[...$('modal').querySelectorAll('a,button,input,select,[tabindex]')].filter(x=>!x.disabled);if(!focusables.length)return;const first=focusables[0],last=focusables[focusables.length-1];if(e.shiftKey&&document.activeElement===first){last.focus();e.preventDefault()}else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault()}}if(e.code==='Space'&&!/INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName)&&$('modal').classList.contains('hide')){e.preventDefault();setPlaying(!state.playing)}});
$('import-video').onclick=()=>$('file').click();$('file').onchange=e=>{const f=e.target.files[0];if(!f)return;setPlaying(false);if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(f);const v=$('local-video');v.src=objectURL;v.onloadedmetadata=()=>{if(!Number.isFinite(v.duration)||v.duration<=0){toast('Cannot determine the video duration. / 재생 길이를 확인할 수 없는 파일입니다.');return}state.local=true;state.time=0;state.duration=v.duration;v.classList.remove('hide');$('camera').classList.add('hide');$('timeline').max=state.duration;v.playbackRate=state.speed;$('video-source').textContent='Local video · playback only / 로컬 영상 · 재생 전용';$('input-name').textContent=f.name;$('camera-label').textContent='LOCAL VIDEO · NO INFERENCE / 로컬 영상 · 추론 없음';$('camera-state').classList.add('hide');$('transport-title').textContent='LOCAL VIDEO / 로컬 영상';$('data-notice').textContent='Local video is for playback only. The maps, objects and 3D scene are unrelated synthetic examples. Video files are not uploaded. / 로컬 영상은 재생만 합니다. 아래 지도·객체·3차원 장면은 영상과 무관한 합성 예시입니다. 영상 파일은 서버로 전송하지 않습니다.';recompute();toast('Opened the local video. The map remains a synthetic example. / 로컬 영상을 열었습니다. 지도는 합성 예시로 유지됩니다.')};v.onerror=()=>toast('Cannot open the video. Choose a format supported by this browser. / 영상을 열 수 없습니다. 브라우저가 지원하는 형식을 선택하세요.');};
window.addEventListener('resize',()=>{drawScene();drawCamera();drawMap();drawVoxels()});
function frame(now){const dt=Math.min((now-lastFrame)/1000,.1)||0;lastFrame=now;if(state.playing){state.time=state.local?$('local-video').currentTime:Math.min(state.duration,state.time+dt*state.speed);if(state.time>=state.duration||state.local&&$('local-video').ended)setPlaying(false);if(Math.floor(state.time*2)!==lastMap){lastMap=Math.floor(state.time*2);recompute();drawCamera()}else updateLabels()}requestAnimationFrame(frame)}
recompute();drawCamera();requestAnimationFrame(frame);
// A read-only hook for controlled integration and browser diagnostics.
window.TerraScenePreview={getState:()=>({...state,synthetic:true,inference_connected:false}),getRoute:()=>({...route}),getGeometryCount:()=>points.length};
})();
