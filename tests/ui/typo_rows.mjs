// The row pitch control moves text, status icons and selection together,
// both over a captured game background and over a generated mockup.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html=fs.readFileSync(process.argv[2],'utf8');
const blocks=[...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const c={atob:s=>Buffer.from(s,'base64').toString('binary'),Math,Float32Array,Float64Array,Uint8Array,Int32Array,Object,JSON,Date};
c.window=c;c.globalThis=c;vm.createContext(c);vm.runInContext(blocks[0],c);vm.runInContext(blocks[1],c);
const tc=c.TC,sc=tc.T.scenes.find(s=>s.id==='msel');
assert(sc && sc.bg_a,'MISSION SELECT must have a real game frame');
let checks=0,bad=0;
for(const carry of [false,true]) {
  sc.statics.filter(s=>s.group==='ms_rows').forEach(s=>s.carry=carry);
  tc.loadJson({groups:{}});const base=tc.applyTypo(sc);
  const rows=base.texts.filter(t=>/^Mission[0-6]$/.test(t.name)).sort((a,b)=>a.name.localeCompare(b.name));
  assert.equal(rows.length,7);const p0=(rows[6].dst[1]-rows[0].dst[1])/6;
  const stat=base.stat.filter(s=>s.group==='ms_rows');assert.equal(stat.length,8);
  for(const pitch of [12,18,24,30]) {
    tc.loadJson({groups:{ms_rows:{pitch}}});const actual=tc.applyTypo(sc);
    for(const before of stat) {
      const row=Number(before.name.match(/[0-6]$/)[0]);
      const text=actual.texts.find(t=>t.name==='Mission'+row);
      const icon=actual.stat.find(s=>s.name===before.name);
      const expected=rows[row].dst[1]+3*(p0-pitch)+row*(pitch-p0);
      checks++;if(text.dst[1]!==expected || icon.cur[1]-before.cur[1]!==expected-rows[row].dst[1])bad++;
    }
  }
}
console.log(`${bad?'FAIL':'PASS'} mission row controls checks=${checks} failures=${bad}`);
assert.equal(bad,0,'status and selection must follow their own row');
