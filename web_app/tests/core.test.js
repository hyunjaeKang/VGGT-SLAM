'use strict';
const assert=require('node:assert/strict');
const C=require('../dist/core.js');
const results=[];
function test(name,fn){fn();results.push({name,status:'passed'})}
function scene(time=52,blocked=false,r=.8,unknown=false){const g=C.grid(time,blocked),d=C.clearance(g),c=C.costmap(g,d,r,unknown);return {g,d,c}}
test('Open passage: concrete route is collision-free and stays in known cells',()=>{
 const {g,c}=scene(),r=C.search(c,[10,26],[62,26]);assert.ok(r.path.length>0);assert.ok(r.length>26);
 for(let i=0;i<r.path.length;i++){const [x,y]=r.path[i];assert.equal(g[y*C.W+x],0);assert.ok(c[y*C.W+x]<254);if(i){const [px,py]=r.path[i-1];assert.ok(Math.abs(x-px)<=1&&Math.abs(y-py)<=1);if(x!==px&&y!==py){assert.ok(c[y*C.W+px]<254);assert.ok(c[py*C.W+x]<254)}}}
});
test('A wall changes reachability and separates free-space components',()=>{
 const open=scene(),closed=scene(52,true);assert.equal(C.components(open.c).count,1);assert.equal(C.components(closed.c).count,2);assert.equal(C.search(closed.c,[10,26],[62,26]).path.length,0);
});
test('Unknown is blocked by default and provisional traversal is explicit',()=>{
 const blocked=scene(0,false,.3,false),allowed=scene(0,false,.3,true);
 assert.equal(C.search(blocked.c,[10,18],[62,26]).path.length,0);
 assert.ok(C.search(allowed.c,[10,18],[62,26]).path.length>0);assert.equal(blocked.c[50*C.W+65],255);assert.equal(allowed.c[50*C.W+65],220);
});
test('Larger footprint never opens cells blocked for the smaller footprint',()=>{
 const small=scene(52,false,.3),large=scene(52,false,2.5);let changed=0;
 small.c.forEach((v,i)=>{if(v>=254)assert.ok(large.c[i]>=254);if(v<254&&large.c[i]>=254)changed++});assert.ok(changed>100);
});
test('Diagonal corner cutting is rejected',()=>{
 const c=new Uint8Array(C.W*C.H).fill(254);c[10*C.W+10]=0;c[11*C.W+11]=0;assert.equal(C.search(c,[10,10],[11,11]).path.length,0);
});
test('Backward replay restores unknown rather than retaining future observations',()=>{
 const early=scene(0),late=scene(52);assert.ok(early.g.some(v=>v===-1));assert.ok(late.g.every(v=>v>=0));assert.deepEqual(C.grid(0),early.g);
});
test('Path endpoints and invalid coordinates are handled deterministically',()=>{
 const {c}=scene();assert.equal(C.search(c,[-1,10],[20,20]).reason,'Outside map');assert.equal(C.search(c,[10,26],[10,26]).length,0);assert.equal(C.search(c,[15,10],[62,26]).path.length,0);
});
test('Synthetic geometry is deterministic, finite and independent of video',()=>{
 const a=C.makePoints(),b=C.makePoints();assert.deepEqual(a,b);assert.ok(a.length>10000);for(const p of a)assert.ok(p.slice(0,3).every(Number.isFinite));
});
console.log(JSON.stringify({kind:'core',tests:results},null,2));
