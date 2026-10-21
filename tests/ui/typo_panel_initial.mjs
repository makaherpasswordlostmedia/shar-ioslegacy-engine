// 382: compare startup rendering with a clean base panel + one explicit game JSON.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const [panel, baseline, jsonPath] = process.argv.slice(2);
function core(path) {
  const html=fs.readFileSync(path,'utf8');
  const blocks=[...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m=>m[1]);
  const c={atob:s=>Buffer.from(s,'base64').toString('binary'),Math,Float32Array,Float64Array,Uint8Array,Int32Array,Object,JSON,Date};
  c.window=c;c.globalThis=c;vm.createContext(c);
  vm.runInContext(blocks[0],c);vm.runInContext(blocks[1],c);return c.TC;
}
function layout(tc) {return JSON.stringify(tc.T.scenes.map(sc=>({id:sc.id,...tc.applyTypo(sc)})));}
const actual=core(panel),ref=core(baseline);
ref.loadJson(JSON.parse(fs.readFileSync(jsonPath,'utf8')));
const aa=JSON.parse(layout(actual)),bb=JSON.parse(layout(ref)); let errors=[]; for(let i=0;i<aa.length;i++) { for(const key of ['texts','nums','stat']) { if(!aa[i][key])continue; for(let j=0;j<aa[i][key].length;j++) {for(const k of Object.keys(aa[i][key][j])) if(JSON.stringify(aa[i][key][j][k])!==JSON.stringify(bb[i][key]?.[j]?.[k])) errors.push([aa[i].id,key,j,k,aa[i][key][j][k],bb[i][key]?.[j]?.[k]]);}} } if(errors.length) console.log(JSON.stringify(errors.slice(0,8))); assert.equal(errors.length,0,'startup must equal clean layout with settings applied once');
const expected=layout(actual),settings=JSON.stringify(actual.typoJson().groups);
assert(actual.T.scenes.some(sc=>sc.id==='over'),'failure screen must be available');
actual.loadJson(actual.typoJson());
assert.equal(layout(actual),expected,'export/import changed layout');
const gid=Object.keys(actual.ST).find(g=>typeof actual.ST[g].dx==='number');
actual.ST[gid].dx+=17;actual.resetGroup(gid);
assert.equal(JSON.stringify(actual.typoJson().groups),settings,'single-group reset lost current game settings');
actual.loadJson({groups:{}});actual.resetGame();
assert.equal(layout(actual),expected,'game reset did not restore current game settings');
console.log('PASS startup once, failure screen, JSON roundtrip, group reset, game reset:',actual.T.scenes.length,'screens');
