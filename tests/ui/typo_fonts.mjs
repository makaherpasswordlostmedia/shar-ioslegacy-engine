// Правка Роба 312: гейт порта граней твик-панели. Страница build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html рисует буквы своим портом
// tools/ui_export.py FontCache (PIL BOX float32, жирность, 16 уровней, обрезка, отступ и шаг) — он обязан совпасть с Python побайтно:
// ширина, отступ, шаг, строка и уровни альфы каждой буквы, как их кладёт атлас T4 игры.
//   python tools/typo_panel.py --fontref /tmp/fontref.json && node tests/ui/typo_fonts.mjs build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html /tmp/fontref.json
// КРАСНЫЙ: TYPO_PLANT=box (фильтр BOX с другой границей полуинтервала) или TYPO_PLANT=bold (без жирности) — гейт обязан упасть. 0 = PASS
import fs from 'node:fs';
import vm from 'node:vm';
const [page, refPath] = process.argv.slice(2);
const html = fs.readFileSync(page, 'utf8'), ref = JSON.parse(fs.readFileSync(refPath, 'utf8'));
const blocks = [...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
let core = blocks[1];
const plant = process.env.TYPO_PLANT || '';
if (plant === 'box') core = core.replace('(v > -0.5 && v <= 0.5)', '(v >= -0.5 && v < 0.5)');
if (plant === 'bold') core = core.replace('f32(1 - f32(q * q))', 'v');
const ctx = {atob: s => Buffer.from(s, 'base64').toString('binary'), Math, Float32Array, Float64Array, Uint8Array, Int32Array, Object, JSON, Date};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(blocks[0], ctx); vm.runInContext(core, ctx);
const TC = ctx.TC;
let bad = 0, glyphs = 0;
for (const [face, R] of Object.entries(ref)) {
  const f = TC.getFace(face);
  const issues = [];
  if (f.lh !== R.lh) issues.push(`строка ${f.lh} != ${R.lh}`);
  if ((f.gh || 0) !== (R.gh || 0)) issues.push(`ячейка ${f.gh} != ${R.gh}`);
  for (const [code, g] of Object.entries(R.glyphs)) {
    const j = f.glyphs[code]; glyphs++;
    if (!j) { issues.push(`нет буквы ${code}`); continue; }
    const [w, left, adv, lev] = g;
    if (j.w !== w || j.left !== left || j.adv !== adv) { issues.push(`буква ${code}: w ${j.w}/${w} left ${j.left}/${left} adv ${j.adv}/${adv}`); continue; }
    if (!lev) { if (j.bm) issues.push(`буква ${code}: лишний рисунок`); continue; }
    const rows = lev[0], data = Buffer.from(lev[1], 'base64');
    if (!j.bm || j.h !== rows || j.bm.length !== data.length) { issues.push(`буква ${code}: размер ${j.h}x${j.w} != ${rows}`); continue; }
    let d = 0; for (let i = 0; i < data.length; i++) if (j.bm[i] !== data[i]) d++;
    if (d) issues.push(`буква ${code}: ${d} пикс. уровней разошлись`);
  }
  bad += issues.length;
  console.log(`${issues.length ? 'FAIL' : 'ok  '} ${face.padEnd(22)} строка ${f.lh} букв ${Object.keys(R.glyphs).length}${issues.length ? ' — ' + issues.slice(0, 3).join('; ') : ''}`);
}
console.log(`${bad ? 'FAIL' : 'PASS'}: граней ${Object.keys(ref).length}, букв ${glyphs}, расхождений ${bad}${plant ? ' (подброска ' + plant + ')' : ''}`);
process.exit(bad ? 1 : 0);
