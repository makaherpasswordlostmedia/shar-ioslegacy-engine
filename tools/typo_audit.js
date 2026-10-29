// №596: аудит типографики панели в настоящем браузере (Playwright). Файл кладётся рядом со страницей панели (tools/typo_panel.py его копирует),
// из браузера: await import('/typo_audit.js'); await window.runAudit() -> {pairs:[...строки...], plaques:[...], raw:{pairs,plaques}}.
// Для каждой пары «значок + подпись» (✕ ○ △ и др.) мерит центр значка (по альфе картинки) против середины заглавных подписи и зазор значок -> буква;
// для плашек (MessageBox, внутренность Frame_*) — поля слева/справа/сверху/снизу по настоящим пикселям букв. Числа берутся из той же раскладки, что рисует панель.
window.runAudit = async function () {

    const D = window.TYPO_DEBUG, TC = window.TC, T = TC.T;
    const loadImg = (src) => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = src; });
    const bbCache = {};
    const iconBox = async (src) => {
      if (bbCache[src] !== undefined) return bbCache[src];
      const im = await loadImg(src); if (!im) return (bbCache[src] = null);
      const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
      const x = c.getContext('2d'); x.drawImage(im, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data;
      let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
      for (let y = 0; y < c.height; y++) for (let xx = 0; xx < c.width; xx++) if (d[(y * c.width + xx) * 4 + 3] > 40) { x0 = Math.min(x0, xx); x1 = Math.max(x1, xx); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
      return (bbCache[src] = x1 < 0 ? null : [x0, y0, x1 + 1, y1 + 1]);
    };
    const capMid = (t) => {
      if (t.pix8) return 3.5;
      const f = TC.getFace(t.font), g = f && f.glyphs[72]; let r0 = -1, r1 = -1;
      if (g && g.bm) for (let y = 0; y < g.h; y++) { let m = 0; for (let x = 0; x < g.w; x++) m = Math.max(m, g.bm[y * g.w + x]); if (m >= 8) { if (r0 < 0) r0 = y; r1 = y; } }
      return r0 < 0 ? f.lh / 2 : (r0 + r1 + 1) / 2;
    };
    const inkOf = (sc, t) => {
      const lo = []; const r = D.layoutText(sc, t, lo); if (!r) return null; let x0 = 1e9, x1 = -1, y0 = 1e9, y1 = -1;
      for (const e of (t.sh ? lo.slice(lo.length / 2) : lo)) { const [g, gx, gy, gh] = e; if (!g.bm) continue;
        for (let y = 0; y < Math.min(g.h, gh); y++) for (let x = 0; x < g.w; x++) if (g.bm[y * g.w + x] >= 8) { x0 = Math.min(x0, gx + x); x1 = Math.max(x1, gx + x + 1); y0 = Math.min(y0, gy + y); y1 = Math.max(y1, gy + y + 1); } }
      return x1 < 0 ? null : {x0, y0, x1, y1, r};
    };
    const pairs = [], plaques = [];
    for (const sc of T.scenes) {
      sc._fit = sc.fit; const M = D.applyTypo(sc);
      for (const t of M.texts) {
        if (!t.vis || !t.text) continue;
        const ics = M.stat.filter(q => q.show && q.page === t.page && (T.hint_pages.indexOf(t.page) >= 0 || q.name === t.name));
        if (!ics.length) continue;
        const k = inkOf(sc, t); if (!k) continue;
        const capY = k.r.y0 + capMid(t);
        for (const q of ics) {
          const bb = await iconBox(q.img); const kk = q.cur[3] / (q.dst[3] || 1);
          const ay0 = bb ? q.cur[1] + bb[1] * kk : q.cur[1], ay1 = bb ? q.cur[1] + bb[3] * kk : q.cur[1] + q.cur[3];
          const ax1 = bb ? q.cur[0] + bb[2] * kk : q.cur[0] + q.cur[2];
          pairs.push({ink: [k.x0, k.y0, k.x1, k.y1], icon: [q.cur[0], q.cur[1], q.cur[2], q.cur[3]], s: sc.id, scr: sc.screen, name: t.name, iconName: q.name, g: t.group, tx: t.text.slice(0, 16), iconCy: (ay0 + ay1) / 2, capCy: capY, dY: (ay0 + ay1) / 2 - capY, gap: k.x0 - ax1});
        }
      }
      const by = n => M.stat.find(q => q.name === n && q.show);
      const mb = by('MessageBox'), fl = by('Frame_Left'), fr = by('Frame_Right'), ft = by('Frame_Top'), fbt = by('Frame_Bottom');
      let box = null, kind = '';
      if (mb) { box = [mb.cur[0], mb.cur[1], mb.cur[0] + mb.cur[2], mb.cur[1] + mb.cur[3]]; kind = 'MessageBox'; }
      else if (fl && fr && ft && fbt) { box = [fl.cur[0] + fl.cur[2], ft.cur[1] + ft.cur[3], fr.cur[0], fbt.cur[1]]; kind = 'Frame interior'; }
      if (box) for (const t of M.texts) {
        if (!t.vis || !t.text) continue; const k = inkOf(sc, t); if (!k) continue;
        const cx = (k.x0 + k.x1) / 2, cy = (k.y0 + k.y1) / 2; if (cx < box[0] || cx > box[2] || cy < box[1] || cy > box[3]) continue;
        plaques.push({s: sc.id, kind, box, name: t.name, g: t.group, tx: t.text.slice(0, 22), L: k.x0 - box[0], R: box[2] - k.x1, T: k.y0 - box[1], B: box[3] - k.y1, lines: k.r.lines});
      }
    }
    const result = {pairs, plaques};
  const f1 = v => Math.round(v * 10) / 10;
  const out = result.pairs.filter(p => p.dY < 50 && p.dY > -50).map(p => [p.s, p.scr, p.iconName, p.tx, 'dY' + f1(p.dY), 'gap' + f1(p.gap)].join(' '));
  const pl = result.plaques.filter(p => p.lines > 1 || (p.kind === 'Frame interior' && Math.abs(p.L - p.R) > 2 && Math.abs(p.L - p.R) < 12)).map(p => [p.s, p.name, 'L' + p.L, 'R' + p.R, 'T' + p.T, 'B' + p.B, 'n' + p.lines].join(' '));
  return {pairs: out, plaques: pl, raw: result};
};
