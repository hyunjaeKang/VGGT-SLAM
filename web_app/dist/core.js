/* TerraScene prototype: deterministic geometry and real grid search.
   All input geometry is synthetic. No reconstruction model is loaded. */
(function(root){
  'use strict';
  const W=72,H=52,RES=.5;
  const boxes=[
    {id:'obj-01',label:'Storage building',kind:'building',x:14,y:7,w:19,h:10,z:5.2,color:'#9fb7c7',conf:.94},
    {id:'obj-02',label:'Utility vehicle',kind:'vehicle',x:44,y:16,w:9,h:5,z:2.2,color:'#e4ae68',conf:.91},
    {id:'obj-03',label:'Equipment crates',kind:'obstacle',x:24,y:34,w:7,h:6,z:1.4,color:'#d18779',conf:.88},
    {id:'obj-04',label:'Tree cluster',kind:'vegetation',x:54,y:34,w:8,h:8,z:5,color:'#63be99',conf:.92},
    {id:'obj-05',label:'Boundary wall',kind:'wall',x:37,y:2,w:2,h:27,z:2.8,color:'#a8b6ca',conf:.96}
  ];
  function occupied(x,y,blocked=false){
    return x<=1||y<=1||x>=W-2||y>=H-2||boxes.some(b=>x>=b.x&&x<b.x+b.w&&y>=b.y&&y<b.y+b.h)||(blocked&&x>=37&&x<39);
  }
  function observed(x,y,time){
    // A deterministic replay mask, not an inferred sensor visibility model.
    return x<Math.min(W,19+time*1.12)&&y<Math.min(H,21+time*.83);
  }
  function grid(time=52,blocked=false){
    const a=new Int8Array(W*H);
    for(let y=0;y<H;y++)for(let x=0;x<W;x++)a[y*W+x]=observed(x,y,time)?(occupied(x,y,blocked)?1:0):-1;
    return a;
  }
  function clearance(a){
    const out=new Float32Array(a.length),obs=[];
    a.forEach((v,i)=>{if(v===1)obs.push([i%W,Math.floor(i/W)])});
    for(let i=0;i<a.length;i++){
      const x=i%W,y=Math.floor(i/W);let d=Infinity;
      for(const o of obs)d=Math.min(d,(x-o[0])**2+(y-o[1])**2);
      // Conservative cell-square distance from an obstacle center.
      out[i]=Math.max(0,(Math.sqrt(d)-Math.SQRT1_2)*RES);
    }return out;
  }
  function costmap(a,d,radius=.8,allowUnknown=false){
    const c=new Uint8Array(a.length);
    a.forEach((v,i)=>{c[i]=v<0?(allowUnknown?220:255):v===1||d[i]<=radius?254:Math.round(180*Math.exp(-(d[i]-radius)*1.8));});return c;
  }
  const index=(p)=>p[1]*W+p[0];
  function search(cost,start,goal){
    const si=index(start),gi=index(goal);
    if(!start.every(Number.isInteger)||!goal.every(Number.isInteger)||start[0]<0||start[0]>=W||start[1]<0||start[1]>=H||goal[0]<0||goal[0]>=W||goal[1]<0||goal[1]>=H)return {path:[],reason:'Outside map',length:0};
    if(cost[si]>=254||cost[gi]>=254)return {path:[],reason:'Endpoint blocked or unobserved',length:0};
    const g=new Float64Array(cost.length).fill(Infinity),parent=new Int32Array(cost.length).fill(-1),closed=new Uint8Array(cost.length),open=[si];g[si]=0;
    const heuristic=(i)=>Math.hypot(i%W-goal[0],Math.floor(i/W)-goal[1]);
    while(open.length){
      let best=0;for(let j=1;j<open.length;j++)if(g[open[j]]+heuristic(open[j])<g[open[best]]+heuristic(open[best]))best=j;
      const cur=open.splice(best,1)[0];if(closed[cur])continue;closed[cur]=1;
      if(cur===gi){let p=[],k=gi;while(k>=0){p.push([k%W,Math.floor(k/W)]);k=parent[k]}p.reverse();let len=0;for(let j=1;j<p.length;j++)len+=Math.hypot(p[j][0]-p[j-1][0],p[j][1]-p[j-1][1])*RES;return {path:p,reason:'Connected',length:len,visited:closed.reduce((s,v)=>s+v,0)};}
      const x=cur%W,y=Math.floor(cur/W);
      for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
        if(!dx&&!dy)continue;const nx=x+dx,ny=y+dy;if(nx<0||ny<0||nx>=W||ny>=H)continue;
        const ni=ny*W+nx;if(cost[ni]>=254||closed[ni])continue;
        if(dx&&dy&&(cost[y*W+nx]>=254||cost[ny*W+x]>=254))continue;
        const ng=g[cur]+Math.hypot(dx,dy)*(1+cost[ni]/90);
        if(ng<g[ni]){g[ni]=ng;parent[ni]=cur;open.push(ni);}
      }
    }return {path:[],reason:'No connected route',length:0,visited:closed.reduce((s,v)=>s+v,0)};
  }
  function components(cost){
    const labels=new Int32Array(cost.length).fill(-1);let n=0;
    for(let i=0;i<cost.length;i++){
      if(labels[i]>=0||cost[i]>=254)continue;const q=[i];labels[i]=n;
      for(let j=0;j<q.length;j++){const k=q[j],x=k%W,y=Math.floor(k/W);for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const nx=x+dx,ny=y+dy;if(nx<0||ny<0||nx>=W||ny>=H)continue;const z=ny*W+nx;if(labels[z]===-1&&cost[z]<254){labels[z]=n;q.push(z)}}}n++;
    }return {labels,count:n};
  }
  function makePoints(){
    const p=[];let seed=82;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    for(let y=2;y<H-2;y+=.6)for(let x=2;x<W-2;x+=.6)if(!occupied(x,y)){p.push([x*RES,y*RES,(rand()-.5)*.08,'#49746d','ground',x,y]);}
    for(const b of boxes){
      for(let y=b.y;y<b.y+b.h;y+=.38)for(let x=b.x;x<b.x+b.w;x+=.38){
        if(b.kind==='vegetation'){
          const cx=b.x+b.w/2,cy=b.y+b.h/2,r=Math.hypot((x-cx)/(b.w/2),(y-cy)/(b.h/2));
          if(r<1)p.push([x*RES,y*RES,2.5+2.1*Math.sqrt(1-r*r)+(rand()-.5)*.4,b.color,b.id,x,y]);
        }else p.push([x*RES,y*RES,b.z,b.color,b.id,x,y]);
      }
      for(let z=0;z<b.z;z+=.22)for(let u=0;u<2*(b.w+b.h);u+=.42){
        let x,y;if(u<b.w){x=b.x+u;y=b.y}else if(u<b.w+b.h){x=b.x+b.w;y=b.y+u-b.w}else if(u<2*b.w+b.h){x=b.x+2*b.w+b.h-u;y=b.y+b.h}else{x=b.x;y=b.y+2*(b.w+b.h)-u}
        p.push([x*RES,y*RES,z,b.color,b.id,x,y]);
      }
    }return p;
  }
  const api={W,H,RES,boxes,occupied,observed,grid,clearance,costmap,search,components,makePoints};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TerraCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
