/* V2: calibrated point projection. No image synthesis or inferred geometry. */
(()=>{
 const canvas=document.createElement('canvas');canvas.id='calibrated-gpu';canvas.style.cssText='position:absolute;left:0;top:0;pointer-events:none;background:#0f172a';canvas.hidden=true;
 document.getElementById('camera-view').insertAdjacentElement('afterend',canvas);
 const gl=canvas.getContext('webgl',{alpha:false,antialias:true});
 const state=window.vggtGPU={ready:false,error:null,mapPoints:0,draws:0,frames:0,buffers:new Map(),scene:null,path:[],pathKey:null,loading:false};
 if(!gl){state.error='WebGL unavailable';action('gpu_fallback',{enabled:true}).catch(console.debug);return}
 const debug=gl.getExtension('WEBGL_debug_renderer_info');state.renderer=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);state.software=/SwiftShader|llvmpipe|software/i.test(state.renderer);state.autoBudget=state.software?90000:Infinity;state.frameMs=16;state.lastAdjust=0;
 const vs=`attribute vec3 aPosition;attribute vec3 aColor;uniform mat4 uProjection;uniform float uSize;varying vec3 color;void main(){gl_Position=uProjection*vec4(aPosition,1.0);gl_PointSize=uSize;color=aColor;}`;
 const fs=`precision mediump float;varying vec3 color;uniform float uPoints;void main(){float alpha=1.0;if(uPoints>0.5){float r=length(gl_PointCoord*2.0-1.0);if(r>1.0)discard;alpha=1.0-smoothstep(.75,1.0,r);}gl_FragColor=vec4(color,alpha);}`;
 function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
 let program;
 try{program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vs));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));}catch(e){state.error=String(e);return}
 const pos=gl.getAttribLocation(program,'aPosition'),col=gl.getAttribLocation(program,'aColor');
 const projection=gl.getUniformLocation(program,'uProjection'),size=gl.getUniformLocation(program,'uSize'),points=gl.getUniformLocation(program,'uPoints');
 let epoch=null,active=[],lastPathRequest=null;
 function quat(a,b,t){let dot=a.reduce((s,v,i)=>s+v*b[i],0);b=[...b];if(dot<0){b=b.map(v=>-v);dot=-dot}if(dot>.9995){const q=a.map((v,i)=>v+t*(b[i]-v)),n=Math.hypot(...q);return q.map(v=>v/n)}const theta=Math.acos(Math.min(1,dot)),s=Math.sin(theta);return a.map((v,i)=>(Math.sin((1-t)*theta)*v+Math.sin(t*theta)*b[i])/s)}
 function poseAt(samples,t){if(!samples.length)return null;let i=0;while(i+1<samples.length&&samples[i+1].time<=t)i++;const a=samples[i],b=samples[Math.min(i+1,samples.length-1)],f=b.time>a.time?Math.max(0,Math.min(1,(t-a.time)/(b.time-a.time))):0;return {position:a.position.map((v,j)=>v+(b.position[j]-v)*f),wxyz:quat(a.wxyz,b.wxyz,f),intrinsic:a.intrinsic.map((row,j)=>row.map((v,k)=>v+(b.intrinsic[j][k]-v)*f)),shape:a.shape}}
 function pixelProjection(pose){const [w,x,y,z]=pose.wxyz,R=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]];return pose.intrinsic.map(row=>{const m=[0,1,2].map(j=>row.reduce((s,v,k)=>s+v*R[j][k],0));return [...m,-m.reduce((s,v,j)=>s+v*pose.position[j],0)]})}
 function clipMatrix(p,shape){const [h,w]=shape,n=.001,f=10000,A=(f+n)/(f-n),B=-2*f*n/(f-n),out=[];for(let j=0;j<4;j++)out.push(2*p[0][j]/w-p[2][j],p[2][j]-2*p[1][j]/h,A*p[2][j]+(j===3?B:0),p[2][j]);return new Float32Array(out)}
 // Export pure math for pixel-alignment regression checks.
 state.pixelProjection=pixelProjection;state.poseAt=poseAt;state.clipMatrix=clipMatrix;
 async function load(){if(state.loading)return;state.loading=true;try{
  const d=typeof lastSmoothStatus==='undefined'?null:lastSmoothStatus;if(!d)return;
  const scene=d.gpu_scene;if(!scene||!scene.chunks)return;
  const key=JSON.stringify(d.camera_path_key);
  if(key!==state.pathKey&&lastPathRequest!==key){lastPathRequest=key;try{const data=await(await fetch('/api/camera_path')).json();if(JSON.stringify(data.key)===key){state.path=data.samples;state.pathKey=key}}finally{lastPathRequest=null}}
  if(epoch!==scene.epoch){state.ready=false;for(const b of state.buffers.values())gl.deleteBuffer(b.buffer);state.buffers.clear();epoch=scene.epoch}
  active=scene.chunks;state.scene=scene;state.mapPoints=scene.map_points;
  const keep=new Set(active.map(c=>c.id));for(const [id,b] of state.buffers){if(!keep.has(id)){gl.deleteBuffer(b.buffer);state.buffers.delete(id)}}
  const missing=active.filter(c=>c.count>0&&!state.buffers.has(c.id));
  for(let offset=0;offset<missing.length;offset+=6){await Promise.all(missing.slice(offset,offset+6).map(async c=>{const generation=epoch,r=await fetch('/gpu_chunk/'+generation+'/'+c.id);if(!r.ok)return;const data=await r.arrayBuffer();if(generation!==epoch)return;const view=new DataView(data);if(view.getUint32(0,true)!==0x32504756)throw Error('Invalid point packet');const n=view.getUint32(4,true),buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);state.buffers.set(c.id,{buffer,count:n,offset:view.getUint32(8,true),color:view.getUint32(12,true)})}))}
  state.ready=state.path.length>0&&active.some(c=>state.buffers.has(c.id));
 }catch(e){state.error=String(e);console.debug(e)}finally{state.loading=false;setTimeout(load,150)}}
 let previousFrame=performance.now();
 function render(){try{const now=performance.now();state.frameMs=state.frameMs*.9+(now-previousFrame)*.1;previousFrame=now;
  const d=typeof lastSmoothStatus==='undefined'?null:lastSmoothStatus,show=!!(state.ready&&d&&d.playing&&d.follow_rgb&&state.pathKey===JSON.stringify(d.camera_path_key)&&state.scene.frame_index<=d.frame_index&&state.scene.epoch===d.gpu_scene?.epoch);canvas.hidden=!show;state.visible=show;
  if(show){const bar=document.getElementById('height-split').getBoundingClientRect(),r={width:bar.width,height:bar.top},dpr=Math.min(devicePixelRatio||1,2),cap=Math.min(1,(state.software&&d.playback_quality==='자동'?640:1920)/(r.width*dpr),(state.software&&d.playback_quality==='자동'?360:1080)/(r.height*dpr)),w=Math.max(1,Math.round(r.width*dpr*cap)),h=Math.max(1,Math.round(r.height*dpr*cap));canvas.style.width=r.width+'px';canvas.style.height=r.height+'px';if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}
   const video=document.getElementById('native-rgb'),t=d.media&&!video.paused?video.currentTime:d.time,pose=poseAt(state.path,t);
   if(pose){gl.clearColor(15/255,23/255,42/255,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);const ratio=pose.shape[1]/pose.shape[0],vw=Math.min(w,h*ratio),vh=vw/ratio;gl.viewport(Math.round((w-vw)/2),Math.round((h-vh)/2),Math.round(vw),Math.round(vh));gl.useProgram(program);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.uniformMatrix4fv(projection,false,clipMatrix(pixelProjection(pose),pose.shape));gl.uniform1f(size,Math.min(16,Math.max(1.2,vw/pose.shape[1]*1.5*(d.point_scale||1))));
    gl.enableVertexAttribArray(pos);gl.enableVertexAttribArray(col);state.draws=0;
    let planned=active.filter(c=>c.kind==='points'&&!c.id.startsWith('road_')).map(c=>({...c}));
    if(d.playback_quality==='자동'){
     if(now-state.lastAdjust>1500){if(state.frameMs>65)state.autoBudget=Math.max(state.software?90000:120000,Math.min(state.autoBudget,state.mapPoints)*.7);else if(state.frameMs<25)state.autoBudget=Math.min(state.software?90000:state.mapPoints,Number.isFinite(state.autoBudget)?state.autoBudget*1.2:state.mapPoints);state.lastAdjust=now}
     let remaining=Math.min(state.mapPoints,Math.floor(state.autoBudget));
     for(const near of [true,false]){const group=planned.filter(c=>c.near===near),sum=group.reduce((s,c)=>s+c.count,0),allocation=Math.min(remaining,sum);for(const c of group)c.count=Math.floor(c.count*allocation/Math.max(1,sum));remaining-=allocation}
    }
    const counts=new Map(planned.map(c=>[c.id,c.count]));state.drawnMapPoints=planned.reduce((s,c)=>s+c.count,0);
    for(const c of active){const b=state.buffers.get(c.id);if(!b)continue;gl.bindBuffer(gl.ARRAY_BUFFER,b.buffer);gl.vertexAttribPointer(pos,3,gl.FLOAT,false,0,b.offset);gl.vertexAttribPointer(col,3,gl.UNSIGNED_BYTE,true,0,b.color);gl.uniform1f(points,c.kind==='lines'?0:1);gl.drawArrays(c.kind==='lines'?gl.LINES:gl.POINTS,0,Math.min(counts.has(c.id)?counts.get(c.id):(state.software&&d.playback_quality==='자동'&&c.id.startsWith('road_')?Math.min(c.count,10000):c.count),b.count));state.draws++}state.frames++;
   }
  }
 }catch(e){state.error=String(e)}requestAnimationFrame(render)}
 load();render();
})();
