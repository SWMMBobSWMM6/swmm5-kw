// compare two SWMM .out files value by value (all periods, all objects)
const fs=require('fs');
function readAll(buf){ const dv=new DataView(buf.buffer,buf.byteOffset,buf.byteLength), n=buf.byteLength, I=o=>dv.getInt32(o,true);
  const nP=I(n-12), outPos=I(n-16); const vals=new Float32Array(buf.buffer.slice(buf.byteOffset+outPos, buf.byteOffset+n-24)); return {nP, vals}; }
module.exports=function(a,b){ const A=readAll(a),B=readAll(b); if(A.vals.length!==B.vals.length) return {len:[A.vals.length,B.vals.length]};
  let maxAbs=0,maxRel=0,nd=0; for(let i=0;i<A.vals.length;i++){ const d=Math.abs(A.vals[i]-B.vals[i]); if(d>0){nd++; maxAbs=Math.max(maxAbs,d); const s=Math.max(Math.abs(A.vals[i]),Math.abs(B.vals[i])); if(s>1e-3) maxRel=Math.max(maxRel,d/s);} }
  return {values:A.vals.length, differing:nd, maxAbs, maxRel}; };
