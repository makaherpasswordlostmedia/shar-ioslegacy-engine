#!/usr/bin/env python3
"""Compare real UIP1 glyph geometry and actual ui.c hint flow with the panel.

No PSP/GU calls are mocked as successful: this is a host layout check. The atlas
metrics, wrapping, fitting and glyph placement are the production code; badd
records the submitted rectangles instead of drawing them. Only ordinary font
items are accepted by this probe (the failure pack uses those, not pix8).
"""
import argparse
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def function(source, declaration):
    start = source.index(declaration + ' {')
    at = source.index('{', start)
    depth = 1
    end = at + 1
    while depth:
        if source[end] == '{': depth += 1
        if source[end] == '}': depth -= 1
        end += 1
    return source[start:end]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--panel', type=Path, required=True)
    ap.add_argument('--pack', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--old', action='store_true')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    page = (args.panel / 'index.html').read_text()
    start = page.index('window.TYPO = ') + len('window.TYPO = ')
    data = json.loads(page[start:page.index(';\n</script>', start)])
    over = next(s for s in data['scenes'] if s['id'] == 'over')
    src = (ROOT / 'viewer/ui.c').read_text()
    types = src[src.index('typedef struct {'):src.index('#define VT_SPR')]
    text = src[src.index('static int lineWidth('):src.index('static int curScreen;')]
    fit = function(src, 'static int fitW(const UiItem *t, int sidx, int *maxLines)')
    flow = function(src, 'static int failureMenuDy(const UiScreen *sc, int *menuY, int *left, int *right)')
    apply = re.search(r'    if \(failureDy && it->type == T_TEXT[^\n]+\n      gDy \+= failureDy;', src)
    if not apply:
        raise ValueError('production drawScreen does not apply failure flow')
    if args.old:
        flow = 'static int failureMenuDy(const UiScreen *sc,int *y,int *l,int *r){return 0;}'
    examples = ',\n'.join('{' + json.dumps(e['text']['MSN_FAIL']) + ',' + json.dumps(e['text']['MSN_HINT']) + '}' for e in over['examples'])
    c = '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <math.h>\n#include "ui.h"\n#include "ui_layout.h"\n' + types + r'''
static const UiHdr *H; static const UiItem *items; static const UiScreen *screens; static const UiFont *fonts;
static char ovHint[192];static int dx0,dy0,dx1,dy1,gDy;
#define PIX8_TEXID 65535
static void badd(int tex,int u,int v,int w,int h,int x,int y,unsigned color) {
  (void)tex;(void)u;(void)v;(void)color;y+=gDy;
  if(x<dx0)dx0=x;if(y<dy0)dy0=y;if(x+w>dx1)dx1=x+w;if(y+h>dy1)dy1=y+h;
}
static const UiFont *itemFont(const UiItem *it,int screen) {
  (void)screen;if(ITEM_PIX8(it)){puts("unsupported pix8 failure item");exit(2);}
  return &fonts[it->font < H->nfont ? it->font : 0];
}
''' + text + fit + flow + '\nstatic const char *const examples[][2]={' + examples + r'''};
int main(int argc,char **argv) {
  if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(!b||fread(b,1,n,f)!=(size_t)n)return 2;fclose(f);
  H=(const UiHdr *)b;items=(const UiItem *)(b+H->offItem);screens=(const UiScreen *)(b+H->offScreen);
  fonts=(const UiFont *)(b+H->offFont);const UiScreen *sc=&screens[UI_SCREEN_MISSIONOVER];
  for(unsigned e=0;e<sizeof examples/sizeof *examples;e++) {
    snprintf(ovHint,sizeof ovHint,"%s",examples[e][1]);int my=272,left=0,right=0,dy=failureMenuDy(sc,&my,&left,&right);
    for(unsigned i=0;i<sc->count;i++) {
      const UiItem *t=&items[sc->first+i];if(t->type!=T_TEXT||t->tag!=UI_T_ALWAYS||!t->count)continue;
      const char *s;
      if(t->field==UI_F_MSN_HINT)s=examples[e][1];else if(t->field==UI_F_MSN_FAIL)s=examples[e][0];
      else s=(const char *)b+((const unsigned *)(b+H->offStr))[t->first];
      if(!s[0])continue;
      gDy=0;{const UiItem *it=t;int failureDy=dy,failureY=my,failureLeft=left,failureRight=right;
''' + apply.group() + r'''
      }
      dx0=dy0=100000;dx1=dy1=-100000;int ml,w=t->w;if(t->flags&F_WRAP)w=fitW(t,UI_SCREEN_MISSIONOVER,&ml);
      textGlyphs(itemFont(t,UI_SCREEN_MISSIONOVER),s,t->x,t->y,w,t->h,t->halign,t->valign,t->flags&F_WRAP,0,0,t->color);
      printf("%u %u %d %d %d %d %d\n",e,i,dy,dx0,dy0,dx1,dy1);
    }
  }
  free(b);return 0;
}
'''
    file = args.out / 'layout.c'; file.write_text(c)
    binary = args.out / 'layout'
    subprocess.run(['cc', '-std=c99', '-O2', '-I', str(ROOT / 'viewer'), str(file), '-lm', '-o', str(binary)], check=True)
    run = subprocess.run([str(binary.resolve()), str(args.pack.resolve())], capture_output=True, text=True, check=True)
    (args.out / 'native.tsv').write_text(run.stdout)
    script = args.out / 'panel.mjs'
    script.write_text(r'''
import fs from 'node:fs';import vm from 'node:vm';
const [file,out]=process.argv.slice(2), html=fs.readFileSync(file,'utf8');
const b=[...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const c={atob:s=>Buffer.from(s,'base64').toString('binary'),Math,Float32Array,Float64Array,Uint8Array,Int32Array,Object,JSON,Date};
c.window=c;c.globalThis=c;vm.createContext(c);vm.runInContext(b[0],c);vm.runInContext(b[1],c);
const tc=c.TC,sc=tc.T.scenes.find(s=>s.id==='over'),rows=[];
sc.examples.forEach((e,i)=>{tc.setTextExample(sc,e.id);const M=tc.applyTypo(sc);tc.sceneLayout(sc,M);
  M.texts.filter(t=>t.vis&&t.text).forEach(t=>{const r=tc.layoutText(sc,t,[]);if(r)rows.push([i,t.i,...r.box]);});});
fs.writeFileSync(out,JSON.stringify(rows));
''')
    subprocess.run(['node', str(script), str((args.panel / 'index.html').resolve()), str((args.out / 'panel.json').resolve())], check=True)
    native = {(int(v[0]), int(v[1])):list(map(int, v[3:])) for line in run.stdout.splitlines() if (v:=line.split())}
    panel = {(v[0],v[1]):v[2:] for v in json.loads((args.out / 'panel.json').read_text())}
    mismatch = [(key, native.get(key), panel.get(key)) for key in sorted(set(native) | set(panel)) if native.get(key) != panel.get(key)]
    report = dict(examples=len(over['examples']), glyph_blocks=len(panel), mismatch=mismatch)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2))
    print(('FAIL' if mismatch else 'PASS'), 'original failure examples', report['examples'], 'native/panel glyph blocks', len(panel), 'mismatch', len(mismatch))
    return 1 if mismatch else 0


if __name__ == '__main__':
    raise SystemExit(main())
