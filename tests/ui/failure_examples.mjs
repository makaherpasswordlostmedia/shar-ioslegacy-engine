// Original failure previews must preserve text, fit, and leave game settings untouched.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const [page, plant] = process.argv.slice(2);
const html = fs.readFileSync(page, 'utf8');
const blocks = [...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
const context = {atob:s=>Buffer.from(s,'base64').toString('binary'), Math, Float32Array, Float64Array,
  Uint8Array, Int32Array, Object, JSON, Date};
context.window=context;context.globalThis=context;vm.createContext(context);
vm.runInContext(blocks[0],context);vm.runInContext(blocks[1],context);
const tc=context.TC, sc=tc.T.scenes.find(s=>s.id==='over');
assert(sc?.examples?.length>7 && tc.setTextExample, 'missing original dynamic failure previews');
const initial=JSON.stringify(sc.texts.map(t=>t.text)), settings=JSON.stringify(tc.typoJson());
let variants=0, glyphs=0;
for(const example of sc.examples) {
  tc.setTextExample(sc,example.id);
  if(plant==='empty')sc.texts.filter(t=>Object.hasOwn(example.text,t.field)).forEach(t=>{t.text='';});
  const M=tc.applyTypo(sc);
  tc.sceneLayout(sc,M); // applies the same fitting rectangles as the visible preview
  for(const t of M.texts.filter(t=>Object.hasOwn(example.text,t.field))) {
    assert.equal(t.text,example.text[t.field],`${example.id}: missing original ${t.field}`);
    if(!t.text)continue;
    if(plant==='small') {
      const p=tc.parseFace(t.font);t.font=p.base+'*'+(Number(p.mul||1)*.4);
    }
    const out=[], r=tc.layoutText(sc,t,out);
    assert(r && out.length,`${example.id}: no rendered glyphs`);
    assert(tc.capPx(r.font)>=9,`${example.id}: raster capitals below 9 px`);
    const cs=tc.codes(t.text), wrapped=tc.uiWrap(cs,r.frame[2],t.wrap?1:0,r.font);
    const letters=v=>v.filter(c=>c!==32 && c!==10 && c!==92).join(',');
    const retained=[];wrapped.st.forEach((start,i)=>{retained.push(...cs.slice(start,start+wrapped.len[i]));});
    assert.equal(letters(retained),letters(cs),`${example.id}: truncated lines`);
    const [x,y,w,h]=r.frame,[x0,y0,x1,y1]=r.box;
    assert(x0>=x-1 && x1<=x+w+1,`${example.id}: text exceeds its width ${r.box}/${r.frame}`);
    assert(x0>=0 && y0>=0 && x1<=480 && y1<=272,`${example.id}: outside PSP screen`);
    glyphs+=out.length;
  }
  const visible=M.texts.filter(t=>t.vis && t.text).map(t=>({t,r:tc.layoutText(sc,t,[])})).filter(q=>q.r?.box);
  const hint=visible.find(q=>q.t.field==='MSN_HINT');
  if(hint) for(const q of visible.filter(q=>q.t.field==='NONE' && q.t.dst[1]>hint.t.dst[1] && q.t.dst[0]<hint.r.box[2] && q.t.dst[0]+q.t.dst[2]>hint.r.box[0]))
    assert(q.r.box[1]>=hint.r.box[3]+Math.trunc(hint.r.lh/2),`${example.id}: hint collides with retry/answers`);
  assert.equal(JSON.stringify(tc.typoJson()),settings,'preview changed exported game typography');
  variants++;
}
tc.setTextExample(sc,'sample');
assert.equal(JSON.stringify(sc.texts.map(t=>t.text)),initial,'captured sample not restored exactly');
tc.loadJson(tc.typoJson());assert.equal(JSON.stringify(tc.typoJson()),settings,'preview polluted JSON roundtrip');
assert.throws(()=>tc.setTextExample(sc,'missing-example'),'unknown example accepted');
assert.equal(JSON.stringify(sc.texts.map(t=>t.text)),initial,'invalid choice modified sample');
console.log(`PASS original failure examples=${variants}, rendered glyph quads=${glyphs}, fit/capitals/sample/settings`);
