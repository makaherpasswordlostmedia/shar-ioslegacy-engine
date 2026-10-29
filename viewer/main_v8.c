// SHAR PSP v8: город клетками 40x40 м подгружается по мере езды, PVS, отсечение пирамидой видимости,
// swizzle текстур, HUD через GE, тест-прогон v2 (кнопка O).
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <pspgu.h>
#include <pspgum.h>
#include <psppower.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <math.h>
#include <pspge.h>
#include "hud.h"

PSP_MODULE_INFO("SHARVIEW", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define LOAD_DIST 150.f
#define DROP_DIST 200.f
#define LOD_DIST 50.f
#define CONE_COS 0.60f
#define CONE_SIN 0.80f
#define FOVY 62.f
#define ASPECT (16.f / 9.f)
#define SKY 0xffe0b070

// переключатели: всё, что влияет на скорость, можно выключить по отдельности (тест P2 так и меряет)
enum {
  O_SWZ = 1, O_TEX = 2, O_TRI = 4, O_PVS = 8, O_PLANES = 16, O_LEAN = 32, O_FAR = 64, O_SKY = 128,
  O_SKYCULL = 256, O_QVP = 512, O_D100 = 1024, O_HUD = 2048
};
#define O_DEFAULT (O_SWZ | O_TEX | O_TRI | O_PVS | O_PLANES | O_LEAN | O_FAR | O_SKY | O_SKYCULL | O_HUD)
static unsigned opt = O_DEFAULT;

static unsigned int __attribute__((aligned(64))) list[65536];

typedef struct { short u, v; unsigned int c; short x, y, z, pad; } Vert;
typedef struct { int w, h, levels; void *pal; void *lv[8]; void *slv[8]; } Tex;
typedef struct {
  float bb[6]; int tex, flags, nv, ni, owner; float ox, oy, oz, sc; unsigned off, nf, cell, pad[2];
} Rec;
typedef struct { Rec r; float cx, cy, cz, rad; Vert *v; unsigned short *idx, *fidx; } Piece;
typedef struct {
  float bb[6]; unsigned first, n, owner, off, size, pad;
  float cx, cy, cz, rad;
  volatile int state;           // 0 нет, 1 грузится, 2 готов, 3 нет памяти
  void *mem;
} Cell;

static Tex *tex; static unsigned ntex, npc, ncell;
static Piece *pc; static Cell *cl;
static unsigned short *carP, *skyP; static int ncarP, nskyP;
static short *hm, *wl; static float hox, hoz, hcell; static int hw, hh;
static unsigned *pvsEnt; static unsigned short *pvsPool; static float pvsOx, pvsOz, pvsCell; static int pvsW, pvsH;
static char path[256];
static SceUID sema; static volatile int req = -1; static volatile unsigned loadedBytes = 0;

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static void fail(const char *msg) {
  pspDebugScreenInit(); pspDebugScreenPrintf("SHAR PSP\n\n%s\n\nPress HOME to exit.", msg);
  sceKernelSleepThread();
}
static void sibling(char *out, const char *name) {   // путь к файлу рядом с EBOOT
  strcpy(out, path); char *sl = strrchr(out, '/'); strcpy(sl ? sl + 1 : out, name);
}

// ---------- стриминг клеток ----------
static void loadCell(SceUID fd, int i) {
  Cell *c = &cl[i];
  void *m = memalign(16, c->size);
  if (!m) { c->state = 3; return; }
  sceIoLseek32(fd, c->off, PSP_SEEK_SET);
  if (sceIoRead(fd, m, c->size) != (int)c->size) { free(m); c->state = 3; return; }
  sceKernelDcacheWritebackRange(m, c->size);
  for (unsigned k = c->first; k < c->first + c->n; k++) {
    Piece *d = &pc[k]; char *b = (char *)m + d->r.off;
    d->v = (Vert *)b;
    d->idx = (unsigned short *)(b + ((d->r.nv * sizeof(Vert) + 15) & ~15));
    d->fidx = (unsigned short *)((char *)d->idx + ((d->r.ni * 2 + 15) & ~15));
  }
  c->mem = m; loadedBytes += c->size;
  __asm__ volatile("" ::: "memory");      // указатели кусков записаны раньше, чем state = 2
  c->state = 2;
}
static int loaderThread(SceSize a, void *b) {
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  for (;;) {
    sceKernelWaitSema(sema, 1, NULL);
    int i = req; if (i >= 0 && fd >= 0) loadCell(fd, i);
    __asm__ volatile("" ::: "memory");
    req = -1;
  }
  return 0;
}
static void unloadCell(Cell *c) {
  if (c->state == 2) { loadedBytes -= c->size; free(c->mem); c->mem = 0; }
  c->state = 0;
}
static float cellDist(Cell *c, float x, float y, float z) {
  float dx = c->cx - x, dy = c->cy - y, dz = c->cz - z;
  return sqrtf(dx * dx + dy * dy + dz * dz) - c->rad;
}
// выгрузить далёкое, отдать загрузчику ближайшую нужную клетку; 1 = ещё что-то грузится
static int stream(float x, float y, float z) {
  int pend = req >= 0, bi = -1; float best = LOAD_DIST;
  for (unsigned i = 0; i < ncell; i++) {
    Cell *c = &cl[i]; if (c->owner) continue;
    float dx = c->cx - x, dy = c->cy - y, dz = c->cz - z, d2 = dx * dx + dy * dy + dz * dz;
    if (c->state >= 2) { float lim = DROP_DIST + c->rad; if (d2 > lim * lim) unloadCell(c); }
    else if (c->state == 0 && !pend) {
      float lim = LOAD_DIST + c->rad;
      if (d2 < lim * lim) { float d = sqrtf(d2) - c->rad; if (d < best) { best = d; bi = i; } }
    }
  }
  if (bi >= 0) { cl[bi].state = 1; req = bi; sceKernelSignalSema(sema, 1); return 1; }
  return pend;
}

// ---------- карта высот и стены ----------
static int ground(float x, float z, float y, float step, float *out) {
  int gx = (int)((x - hox) / hcell), gz = (int)((z - hoz) / hcell);
  if (gx < 0 || gz < 0 || gx >= hw || gz >= hh) return 0;
  short *c = hm + ((size_t)gz * hw + gx) * 4; int found = 0; float best = -1e9f;
  for (int i = 0; i < 4; i++) {
    if (c[i] == -32768) continue;
    float h = c[i] * .01f;
    if (h <= y + step && h > best) { best = h; found = 1; }
  }
  if (found) *out = best;
  return found;
}
// стена в клетке перекрывает высоты кузова машины?
static int wallAt(float x, float z, float y) {
  int gx = (int)((x - hox) / hcell), gz = (int)((z - hoz) / hcell);
  if (gx < 0 || gz < 0 || gx >= hw || gz >= hh) return 1;
  short *w = wl + ((size_t)gz * hw + gx) * 2;
  if (w[0] > w[1]) return 0;
  float lo = w[0] * .01f, hi = w[1] * .01f;
  return hi > y + 0.45f && lo < y + 1.6f;
}

// ---------- текстуры ----------
static int ilog2(int v) { return 31 - __builtin_clz(v); }
// swizzle: блоки 16 байт x 8 строк, как любит кэш текстур GE; высота добивается до кратной 8
static void swizzleLevel(unsigned char *out, const unsigned char *in, int w, int h) {
  int hp = (h + 7) & ~7, rb = w / 16;
  for (int j = 0; j < hp; j++) {
    const unsigned char *row = in + (j < h ? j : h - 1) * w;
    for (int bx = 0; bx < rb; bx++)
      memcpy(out + ((j >> 3) * rb + bx) * 128 + (j & 7) * 16, row + bx * 16, 16);
  }
}
static void swizzleAll(void) {
  for (unsigned i = 0; i < ntex; i++) {
    Tex *t = &tex[i]; size_t sz = 0; int lw = t->w, lh = t->h;
    for (int l = 0; l < t->levels; l++) { sz += (size_t)lw * ((lh + 7) & ~7); lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
    unsigned char *b = memalign(16, sz); if (!b) return;           // нет памяти — останемся на линейных
    lw = t->w; lh = t->h;
    for (int l = 0; l < t->levels; l++) {
      t->slv[l] = b; swizzleLevel(b, t->lv[l], lw, lh);
      b += (size_t)lw * ((lh + 7) & ~7); lw >>= 1; lh = lh > 1 ? lh >> 1 : 1;
    }
  }
}

// ---------- состояние GE: шлём только то, что поменялось ----------
static int bound, texOn, curFlags, curFilt, binds;
static void resetState(void) { bound = -2; texOn = -1; curFlags = -1; curFilt = -1; }
static void texEnable(int on) {
  if (on == texOn) return; texOn = on;
  if (on) sceGuEnable(GU_TEXTURE_2D); else sceGuDisable(GU_TEXTURE_2D);
}
static void bindTexLean(int t) {
  if (!(opt & O_TEX)) t = -1;
  if (t == bound) return; bound = t;
  if (t < 0 || t >= (int)ntex) { texEnable(0); return; }
  texEnable(1); binds++;
  Tex *x = &tex[t]; int swz = (opt & O_SWZ) && x->slv[0];
  unsigned p = (unsigned)x->pal;
  sceGuSendCommandi(0xb0, p & 0xffffff); sceGuSendCommandi(0xb1, (p >> 8) & 0xf0000); sceGuSendCommandi(0xc4, 32);
  sceGuSendCommandi(0xc2, ((x->levels - 1) << 16) | swz);       // TEX_MODE: уровни, swizzle
  sceGuSendCommandi(0xc3, GU_PSM_T8);                            // TEX_FORMAT
  int lw = x->w, lh = x->h;
  for (int l = 0; l < x->levels; l++) {
    unsigned a = (unsigned)(swz ? x->slv[l] : x->lv[l]);
    sceGuSendCommandi(0xa0 + l, a & 0xffffff);
    sceGuSendCommandi(0xa8 + l, ((a >> 8) & 0x0f0000) | lw);
    sceGuSendCommandi(0xb8 + l, (ilog2(lh) << 8) | ilog2(lw));
    lw >>= 1; lh = lh > 1 ? lh >> 1 : 1;
  }
  sceGuSendCommandi(0xcb, 0);                                    // один TEX_FLUSH на привязку
  int f = x->levels > 1 ? ((opt & O_TRI) ? GU_LINEAR_MIPMAP_LINEAR : GU_LINEAR_MIPMAP_NEAREST) : GU_LINEAR;
  if (f != curFilt) { curFilt = f; sceGuTexFilter(f, GU_LINEAR); }
}
static void setFlags(int fl) {
  fl &= 7; if (fl == curFlags) return; curFlags = fl;
  if (fl & 1) sceGuEnable(GU_ALPHA_TEST); else sceGuDisable(GU_ALPHA_TEST);
  if (fl & 2) sceGuEnable(GU_BLEND); else sceGuDisable(GU_BLEND);
  sceGuDepthMask((fl & 6) ? GU_TRUE : GU_FALSE);                 // прозрачное и небо глубину не пишут
}
// старый путь v7 (для сравнения в тесте: вариант LEGACY)
static void bindTexLegacy(int t) {
  if (!(opt & O_TEX)) t = -1;
  if (t == bound) return; bound = t;
  if (t < 0 || t >= (int)ntex) { sceGuDisable(GU_TEXTURE_2D); texOn = 0; return; }
  Tex *x = &tex[t]; int swz = (opt & O_SWZ) && x->slv[0]; binds++;
  sceGuEnable(GU_TEXTURE_2D); texOn = 1;
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0); sceGuClutLoad(32, x->pal);
  sceGuTexMode(GU_PSM_T8, x->levels - 1, 0, swz);
  int lw = x->w, lh = x->h;
  for (int l = 0; l < x->levels; l++) { sceGuTexImage(l, lw, lh, lw, swz ? x->slv[l] : x->lv[l]); lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
  sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
  sceGuTexFilter(x->levels > 1 ? ((opt & O_TRI) ? GU_LINEAR_MIPMAP_LINEAR : GU_LINEAR_MIPMAP_NEAREST) : GU_LINEAR, GU_LINEAR);
  sceGuTexOffset(0.f, 0.f); curFilt = -1;
}

// ---------- отрисовка кусков ----------
static long drawnTris; static int draws;
static void drawIdx(Piece *d, unsigned short *ix, int cnt) {
  for (int k = 0; k < cnt; k += 65532) {
    int n = cnt - k; if (n > 65532) n = 65532;
    sceGuDrawArray(GU_TRIANGLES, GU_INDEX_16BIT | GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_3D,
                   n, ix + k, d->v);
  }
}
// мир = T + R(угол) * (центр куска + масштаб * вершина); матрица модели сразу в GE, без стека gum
static void drawPiece(Piece *d, int far, float tx, float ty, float tz, float c, float s) {
  unsigned short *ix = far ? d->fidx : d->idx; int cnt = far ? (int)d->r.nf : d->r.ni;
  if (cnt <= 0) return; drawnTris += cnt / 3; draws++;
  bindTexLean(d->r.tex); setFlags(d->r.flags);
  float k = d->r.sc, ox = d->r.ox, oy = d->r.oy, oz = d->r.oz;
  ScePspFMatrix4 m = {
    {c * k, 0, -s * k, 0}, {0, k, 0, 0}, {s * k, 0, c * k, 0},
    {tx + c * ox + s * oz, ty + oy, tz - s * ox + c * oz, 1}};
  sceGuSetMatrix(GU_MODEL, &m);
  drawIdx(d, ix, cnt);
}
static void drawPieceLegacy(Piece *d, int far) {
  unsigned short *ix = far ? d->fidx : d->idx; int cnt = far ? (int)d->r.nf : d->r.ni;
  if (cnt <= 0) return; drawnTris += cnt / 3; draws++;
  bindTexLegacy(d->r.tex); sceGuTexScale(128.f, 128.f);
  if (d->r.flags & 1) sceGuEnable(GU_ALPHA_TEST); else sceGuDisable(GU_ALPHA_TEST);
  if (d->r.flags & 2) { sceGuEnable(GU_BLEND); sceGuDepthMask(GU_TRUE); }
  else { sceGuDisable(GU_BLEND); sceGuDepthMask(GU_FALSE); }
  curFlags = -1;
  sceGumPushMatrix();
  ScePspFVector3 o = {d->r.ox, d->r.oy, d->r.oz}, sv = {d->r.sc, d->r.sc, d->r.sc};
  sceGumTranslate(&o); sceGumScale(&sv);
  for (int k = 0; k < cnt; k += 65532) {
    int n = cnt - k; if (n > 65532) n = 65532;
    sceGumDrawArray(GU_TRIANGLES, GU_INDEX_16BIT | GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_3D,
                    n, ix + k, d->v);
  }
  sceGumPopMatrix();
}

// ---------- отсечение ----------
static float pl[4][3], eyeX, eyeY, eyeZ, cfX, cfY, cfZ, drawDist;
static void setupPlanes(float fx, float fy, float fz) {
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl;                                   // вправо = взгляд x вверх
  float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;   // вверх камеры = вправо x взгляд
  float tv = tanf(FOVY * .5f * GU_PI / 180.f) * 1.03f, th = tv * ASPECT;
  float n[4][3] = {
    {fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz},
    {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof pl);
}
// ящик целиком снаружи одной из 4 боковых плоскостей? (ox,oy,oz — сдвиг ящика, для неба = глаз)
static int visBox(const float *b, float ox, float oy, float oz) {
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? b[3] : b[0]) + ox - eyeX;
    float py = (pl[i][1] > 0 ? b[4] : b[1]) + oy - eyeY;
    float pz = (pl[i][2] > 0 ? b[5] : b[2]) + oz - eyeZ;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
  }
  return 1;
}
static float boxD2(const float *b) {
  float dx = b[0] - eyeX > 0 ? b[0] - eyeX : (eyeX - b[3] > 0 ? eyeX - b[3] : 0);
  float dy = b[1] - eyeY > 0 ? b[1] - eyeY : (eyeY - b[4] > 0 ? eyeY - b[4] : 0);
  float dz = b[2] - eyeZ > 0 ? b[2] - eyeZ : (eyeZ - b[5] > 0 ? eyeZ - b[5] : 0);
  return dx * dx + dy * dy + dz * dz;
}
static int coneOut(float cx, float cy, float cz, float rad, float *dist) {   // старое отсечение v7
  float dx = cx - eyeX, dy = cy - eyeY, dz = cz - eyeZ, d2 = dx * dx + dy * dy + dz * dz, d = sqrtf(d2);
  *dist = d - rad; if (d - rad > drawDist) return 1;
  float f = dx * cfX + dy * cfY + dz * cfZ, l = sqrtf(fmaxf(0.f, d2 - f * f));
  return l * CONE_COS - f * CONE_SIN > rad;
}

#define MAXDRAW 2048
static unsigned short tk[MAXDRAW], tp[MAXDRAW], sp[MAXDRAW], cnt2k[2048]; static unsigned char tf[MAXDRAW], sf[MAXDRAW];
static int nd;
static void cullPiece(unsigned k) {
  Piece *d = &pc[k]; int far;
  if (opt & O_PLANES) {
    float d2 = boxD2(d->r.bb);
    if (d2 > drawDist * drawDist || !visBox(d->r.bb, 0, 0, 0)) return;
    far = d2 > LOD_DIST * LOD_DIST;
  } else {
    float dist; if (coneOut(d->cx, d->cy, d->cz, d->rad, &dist)) return;
    far = dist > LOD_DIST;
  }
  if (!(opt & O_FAR)) far = 0;
  if (nd >= MAXDRAW) return;
  int t = d->r.tex < 0 || d->r.tex > 510 ? 511 : d->r.tex;
  tk[nd] = ((d->r.flags & 3) << 9) | t; tp[nd] = k; tf[nd] = far; nd++;
}
static int pvsList(float x, float z, unsigned short **out) {
  if (!pvsEnt) return -1;
  int gx = (int)floorf((x - pvsOx) / pvsCell), gz = (int)floorf((z - pvsOz) / pvsCell);
  if (gx < 0 || gz < 0 || gx >= pvsW || gz >= pvsH) return -1;
  unsigned *e = pvsEnt + 2 * (gz * pvsW + gx);
  if (e[1] == 0xFFFFFFFFu) return -1;
  *out = pvsPool + e[0]; return (int)e[1];
}
static int pvsUsed;
static void cullCity(int fly) {
  nd = 0; pvsUsed = 0;
  unsigned short *pl_; int n = (opt & O_PVS) && !fly ? pvsList(eyeX, eyeZ, &pl_) : -1;
  if (n >= 0) {                                        // PVS: только куски, видимые из этой клетки 20x20 м
    pvsUsed = 1;
    for (int i = 0; i < n; i++) { unsigned k = pl_[i]; if (k < npc && cl[pc[k].r.cell].state == 2) cullPiece(k); }
  } else {
    for (unsigned i = 0; i < ncell; i++) {
      Cell *c = &cl[i]; if (c->owner || c->state != 2) continue;
      if (opt & O_PLANES) { if (boxD2(c->bb) > drawDist * drawDist || !visBox(c->bb, 0, 0, 0)) continue; }
      else { float dist; if (coneOut(c->cx, c->cy, c->cz, c->rad, &dist)) continue; }
      for (unsigned k = c->first; k < c->first + c->n; k++) cullPiece(k);
    }
  }
  // сортировка подсчётом по (прозрачность, текстура): меньше смен текстур, прозрачное после непрозрачного
  memset(cnt2k, 0, sizeof cnt2k);
  for (int i = 0; i < nd; i++) cnt2k[tk[i]]++;
  unsigned s = 0; for (int k = 0; k < 2048; k++) { unsigned c = cnt2k[k]; cnt2k[k] = s; s += c; }
  for (int i = 0; i < nd; i++) { int p = cnt2k[tk[i]]++; sp[p] = tp[i]; sf[p] = tf[i]; }
}

// ---------- тест-прогон v2 ----------
// P1: весь уровень (как v1: 169 точек x 4 направления), P2: 16 худших видов x варианты-переключатели,
// P3: 8 худших видов с настоящей вертикальной синхронизацией, считаем пропущенные кадры. Отчёт bench.txt.
#define MAXBP 1024
#define NW2 16
#define NW3 8
static const struct { const char *name; unsigned set, clr; } VAR[] = {
  {"BASE", 0, 0}, {"NOSWZ", 0, O_SWZ}, {"NOTEX", 0, O_TEX}, {"BILIN", 0, O_TRI}, {"NOPVS", 0, O_PVS},
  {"CONE", 0, O_PLANES}, {"LEGACY", 0, O_LEAN}, {"ALLNEAR", 0, O_FAR}, {"NOSKY", 0, O_SKY},
  {"NOSKYCULL", 0, O_SKYCULL}, {"QVP", O_QVP, 0}, {"D100", O_D100, 0}, {"NOHUD", 0, O_HUD},
  {"FAST", O_D100, O_TRI},
};
#define NVAR ((int)(sizeof VAR / sizeof VAR[0]))
static float bpx[MAXBP], bpy[MAXBP], bpz[MAXBP]; static int nbp;
static float p1w[MAXBP * 4], p1all[MAXBP * 8]; static int p1n;
static double p1cpu, p1tris, p1draws; static float p1cpuMax; static int p1trisMax, p1drawsMax, p1pvs;
static int w2[NW2], nw2, w3[NW3], nw3;
static float p2res[NW2][NVAR], p2tri[NVAR], p2drw[NVAR], bm[3]; static int bmn;
static int p3miss[NW3], p3missAll; static float p3max; static unsigned lastVc;
static int bpass, bview, bsub, bvar, bwait, bwaitIdle, bVsync, bMeasure; static unsigned bwaitT0;
static char brep[4][64];
// проверка PVS (служебный файл pvscheck): каждый вид рисуем с PVS и без и сравниваем пиксели
static unsigned *fbA, *curFb; static int pcDiff[MAXBP * 4];
static void pvscheckWrite(void) {
  char fn[256]; sibling(fn, "pvscheck.txt");
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f < 0) return;
  static char b[4096]; int n = 0, nv = nbp * 4, bad = 0, over100 = 0; long tot = 0;
  for (int v = 0; v < nv; v++) { if (pcDiff[v]) bad++; if (pcDiff[v] > 100) over100++; tot += pcDiff[v]; }
  n += snprintf(b + n, sizeof b - n, "PVSCHECK %d views: with diff %d, diff>100px %d, total diff px %ld, pvs %s\nworst (x z heading px):\n",
                nv, bad, over100, tot, pvsEnt ? "yes" : "no");
  for (int k = 0; k < 25; k++) {
    int bi = -1; for (int v = 0; v < nv; v++) if (pcDiff[v] > 0 && (bi < 0 || pcDiff[v] > pcDiff[bi])) bi = v;
    if (bi < 0) break;
    n += snprintf(b + n, sizeof b - n, "   %.1f %.1f %d %d\n", bpx[bi / 4], bpz[bi / 4], bi % 4, pcDiff[bi]); pcDiff[bi] = -pcDiff[bi];
  }
  for (int v = 0; v < nv; v++) if (pcDiff[v] < 0) pcDiff[v] = -pcDiff[v];
  sceIoWrite(f, b, n); sceIoClose(f);
}

static void benchPoints(void) {
  int st = (int)(50.f / hcell); nbp = 0;
  for (int gz = st / 2, row = 0; gz < hh; gz += st, row++)
    for (int j = 0; j < hw / st + 1; j++) {
      int gx = st / 2 + (row & 1 ? (hw / st - j) : j) * st;
      if (gx < 0 || gx >= hw || nbp >= MAXBP) continue;
      short *c = hm + ((size_t)gz * hw + gx) * 4; int lo = 32767;
      for (int i = 0; i < 4; i++) if (c[i] != -32768 && c[i] < lo) lo = c[i];
      if (lo == 32767) continue;
      bpx[nbp] = hox + (gx + .5f) * hcell; bpz[nbp] = hoz + (gz + .5f) * hcell; bpy[nbp] = lo * .01f; nbp++;
    }
}
static int curView(void) { return bpass == 1 || bpass == 5 ? bview : bpass == 2 ? w2[bview] : w3[bview]; }
static void teleport(void) { bwait = 1; bwaitIdle = 0; bwaitT0 = sceKernelGetSystemTimeLow(); bsub = 0; }
static int cmpF(const void *a, const void *b) { float x = *(const float *)a, y = *(const float *)b; return x < y ? -1 : x > y; }
static void pickWorst(int *out, int n, int *nout) {    // n худших видов P1, по порядку обхода
  *nout = 0;
  for (int k = 0; k < n; k++) {
    int bi = -1;
    for (int v = 0; v < nbp * 4; v++) {
      int used = 0; for (int j = 0; j < *nout; j++) if (out[j] == v) used = 1;
      if (!used && (bi < 0 || p1w[v] > p1w[bi])) bi = v;
    }
    if (bi < 0) break; out[(*nout)++] = bi;
  }
  for (int i = 1; i < *nout; i++) for (int j = i; j > 0 && out[j] < out[j - 1]; j--) { int t = out[j]; out[j] = out[j - 1]; out[j - 1] = t; }
}
static void benchWrite(void) {
  char fn[256]; sibling(fn, "bench.txt");
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f < 0) return;
  static char b[8192]; int n = 0;
  n += snprintf(b + n, sizeof b - n, "BENCH2 v8 (%s %s)  opt %03x  pvs %s\n", __DATE__, __TIME__, O_DEFAULT, pvsEnt ? "yes" : "no");
  if (p1n) {
    static float s[MAXBP * 8]; memcpy(s, p1all, p1n * sizeof(float)); qsort(s, p1n, sizeof(float), cmpF);
    double sum = 0; int over = 0; for (int i = 0; i < p1n; i++) { sum += s[i]; if (s[i] > 16.7f) over++; }
    n += snprintf(b + n, sizeof b - n,
      "P1 %d views, %d frames: work avg %.2f p50 %.2f p90 %.2f p99 %.2f max %.2f ms; over 16.7ms %.1f%%\n"
      "   cpu avg %.2f max %.2f ms; tris avg %.1fk max %.1fk; draws avg %.0f max %d; pvs used %d%%\n"
      "   (v7: avg 16.8, worst 25.0, over 55.2%%)\n",
      nbp * 4, p1n, sum / p1n, s[p1n / 2], s[p1n * 9 / 10], s[p1n * 99 / 100], s[p1n - 1], 100.f * over / p1n,
      p1cpu / p1n, p1cpuMax, p1tris / p1n / 1000., p1trisMax / 1000.f, p1draws / p1n, p1drawsMax, 100 * p1pvs / p1n);
  }
  if (bpass >= 3 || (bpass == 0 && nw2)) {
    n += snprintf(b + n, sizeof b - n, "P2 %d worst views, median of 3 frames, no vsync:\n   variant     ms   delta   tris  draws\n", nw2);
    float base = 0; for (int v = 0; v < nw2; v++) base += p2res[v][0]; base /= nw2 ? nw2 : 1;
    for (int k = 0; k < NVAR; k++) {
      float m = 0; for (int v = 0; v < nw2; v++) m += p2res[v][k]; m /= nw2 ? nw2 : 1;
      n += snprintf(b + n, sizeof b - n, "   %-10s %5.2f %+6.2f %5.1fk %5.0f\n", VAR[k].name, m, m - base,
                    p2tri[k] / (nw2 * 3) / 1000.f, p2drw[k] / (nw2 * 3));
    }
  }
  if (bpass == 0 && nw3) {
    n += snprintf(b + n, sizeof b - n, "P3 vsync, %d worst views x 60 frames: missed vblanks total %d (", nw3, p3missAll);
    for (int i = 0; i < nw3; i++) n += snprintf(b + n, sizeof b - n, "%d%s", p3miss[i], i + 1 < nw3 ? " " : "");
    n += snprintf(b + n, sizeof b - n, "), worst work %.2f ms\n", p3max);
  }
  if (p1n) {
    n += snprintf(b + n, sizeof b - n, "worst P1 views (x z heading work):\n");
    for (int i = 0; i < nw2 && n < (int)sizeof b - 80; i++) {
      int v = w2[i]; n += snprintf(b + n, sizeof b - n, "   %.0f %.0f %d %.2f\n", bpx[v / 4], bpz[v / 4], v % 4, p1w[v]);
    }
  }
  sceIoWrite(f, b, n); sceIoClose(f);
}
static void benchStart(void) {
  benchPoints(); bpass = 1; bview = 0; p1n = 0; p1cpu = p1tris = p1draws = 0; p1cpuMax = 0; p1trisMax = p1drawsMax = p1pvs = 0;
  memset(p1w, 0, sizeof p1w); memset(p2res, 0, sizeof p2res); memset(p2tri, 0, sizeof p2tri); memset(p2drw, 0, sizeof p2drw);
  nw2 = nw3 = 0; p3missAll = 0; p3max = 0; memset(p3miss, 0, sizeof p3miss); bvar = 0; bmn = 0;
  teleport();
}
// перед кадром: куда смотрим, какие переключатели, меряем ли этот кадр
static void benchBefore(int pending, float sph, float *x, float *y, float *z, float *h) {
  int v = curView();
  *x = bpx[v / 4]; *y = bpy[v / 4]; *z = bpz[v / 4]; *h = sph + (v % 4) * GU_PI * .5f;
  opt = O_DEFAULT; bMeasure = 0; bVsync = bpass == 3;
  if (bwait) {
    if (!pending) bwaitIdle++; else bwaitIdle = 0;
    if (bwaitIdle >= 2 || sceKernelGetSystemTimeLow() - bwaitT0 > 5000000) bwait = 0;
    else { sceKernelDelayThread(2000); return; }        // ждём загрузку клеток, отдаём время загрузчику
  }
  if (bpass == 1) bMeasure = bsub >= 2;
  else if (bpass == 2) { opt = (O_DEFAULT | VAR[bvar].set) & ~VAR[bvar].clr; bMeasure = bsub >= 2; }
  else if (bpass == 3) bMeasure = bsub >= 2;
  else if (bpass == 5) { opt = O_DEFAULT & ~O_HUD & ~(bsub == 1 ? O_PVS : 0); bMeasure = 1; }
}
// после кадра: записать замер, сдвинуть состояние
static void benchAfter(float work, float cpu, int missed) {
  if (bwait) return;
  int v = curView();
  if (bpass == 5) {
    unsigned *fb = (unsigned *)PSP_UC((unsigned)curFb);
    if (bsub == 0) memcpy(fbA, fb, BUF_W * SCR_H * 4);
    else {
      int d = 0;
      for (int yy = 0; yy < SCR_H; yy++) for (int xx = 0; xx < SCR_W; xx++) {
        unsigned a = fbA[yy * BUF_W + xx], c = fb[yy * BUF_W + xx];
        int e = abs((int)(a & 255) - (int)(c & 255)) + abs((int)((a >> 8) & 255) - (int)((c >> 8) & 255)) + abs((int)((a >> 16) & 255) - (int)((c >> 16) & 255));
        if (e > 48) d++;
      }
      pcDiff[v] = d;
    }
    if (++bsub >= 2) {
      bsub = 0;
      if (++bview >= nbp * 4) { bpass = 0; pvscheckWrite(); snprintf(brep[0], 64, "PVSCHECK done"); snprintf(brep[1], 64, "pvscheck.txt"); }
      else if (bview % 4 == 0) teleport();
    }
    return;
  }
  if (bpass == 1) {
    if (bMeasure) {
      if (p1n < MAXBP * 8) p1all[p1n++] = work;
      if (work > p1w[v]) p1w[v] = work;
      p1cpu += cpu; if (cpu > p1cpuMax) p1cpuMax = cpu;
      p1tris += drawnTris; if (drawnTris > p1trisMax) p1trisMax = drawnTris;
      p1draws += draws; if (draws > p1drawsMax) p1drawsMax = draws; p1pvs += pvsUsed;
    }
    if (++bsub >= 4) {
      bsub = 0;
      if (++bview >= nbp * 4) {
        pickWorst(w2, NW2, &nw2); benchWrite();
        bpass = 2; bview = 0; bvar = 0; bmn = 0; teleport();
      } else if (bview % 4 == 0) teleport();
    }
  } else if (bpass == 2) {
    if (bMeasure) { bm[bmn++] = work; p2tri[bvar] += drawnTris; p2drw[bvar] += draws; }
    if (++bsub >= 5) {
      qsort(bm, bmn, sizeof(float), cmpF); p2res[bview][bvar] = bm[bmn / 2]; bmn = 0; bsub = 0;
      if (++bvar >= NVAR) {
        bvar = 0;
        if (++bview >= nw2) {
          pickWorst(w3, NW3, &nw3); benchWrite();
          bpass = 3; bview = 0; teleport();
        } else teleport();
      }
    }
  } else if (bpass == 3) {
    if (bMeasure) { if (missed) { p3miss[bview]++; p3missAll++; } if (work > p3max) p3max = work; }
    if (++bsub >= 62) {
      if (++bview >= nw3) {
        bpass = 0; benchWrite();
        snprintf(brep[0], 64, "BENCH v2 done. vsync misses: %d", p3missAll);
        snprintf(brep[1], 64, "report: bench.txt   O: close");
        brep[2][0] = 0;
      } else teleport();
    }
  }
}

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  pspDebugScreenInit(); pspDebugScreenPrintf("Loading Springfield...\n");

  strncpy(path, argv[0], sizeof(path) - 16); path[sizeof(path) - 16] = 0;
  char *slash = strrchr(path, '/'); if (slash) slash[1] = 0; else path[0] = 0;
  strcat(path, "level.shr");

  // резидентная часть: заголовок, карта высот, текстуры, таблицы кусков и клеток, PVS
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  if (fd < 0) fail("level.shr not found next to EBOOT.PBP.");
  unsigned char hdr[96];
  if (sceIoRead(fd, hdr, 96) != 96 || memcmp(hdr, "SHR7", 4)) fail("level.shr is an old version. Run the export again.");
  ntex = *(unsigned *)(hdr + 4); npc = *(unsigned *)(hdr + 8);
  float *hd = (float *)(hdr + 12);
  float spx = hd[6], spy = hd[7], spz = hd[8], sph = hd[9], lift = hd[10];
  hox = hd[11]; hoz = hd[12]; hcell = hd[13]; hw = *(int *)(hd + 14); hh = *(int *)(hd + 15);
  unsigned tableOff = *(unsigned *)(hdr + 76);
  ncell = *(unsigned *)(hdr + 80); unsigned cellOff = *(unsigned *)(hdr + 84), pvsOff = *(unsigned *)(hdr + 88);
  unsigned residentSize = cellOff + 48 * ncell;
  unsigned char *data = memalign(16, residentSize);
  if (!data) {
    char m[160]; snprintf(m, sizeof m, "Not enough memory: %.1f MB needed, %.1f MB free.",
      residentSize / 1048576.f, sceKernelMaxFreeMemSize() / 1048576.f); fail(m);
  }
  sceIoLseek32(fd, 0, PSP_SEEK_SET);
  if (sceIoRead(fd, data, residentSize) != (int)residentSize) fail("Read error.");
  if (pvsOff) {
    unsigned char ph[32];
    sceIoLseek32(fd, pvsOff, PSP_SEEK_SET);
    if (sceIoRead(fd, ph, 32) == 32 && !memcmp(ph, "PVS1", 4)) {
      float *pf = (float *)(ph + 4); unsigned *pu = (unsigned *)(ph + 16);
      pvsOx = pf[0]; pvsOz = pf[1]; pvsCell = pf[2]; pvsW = pu[0]; pvsH = pu[1];
      unsigned sz = pvsW * pvsH * 8 + pu[2] * 2;
      void *m = memalign(16, sz);
      if (m && sceIoRead(fd, m, sz) == (int)sz) { pvsEnt = m; pvsPool = (unsigned short *)((char *)m + pvsW * pvsH * 8); }
      else if (m) free(m);
    }
  }
  sceIoClose(fd);

  size_t p = 96;
  hm = (short *)(data + p); p += (size_t)hw * hh * 4 * 2; p = (p + 15) & ~15;
  wl = (short *)(data + p); p += (size_t)hw * hh * 2 * 2; p = (p + 15) & ~15;
  tex = calloc(ntex ? ntex : 1, sizeof(Tex));
  for (unsigned i = 0; i < ntex; i++) {
    unsigned short *t2 = (unsigned short *)(data + p);
    tex[i].w = t2[0]; tex[i].h = t2[1]; tex[i].levels = t2[2];
    tex[i].pal = data + p + 16; p += 16 + 1024;
    int lw = tex[i].w, lh = tex[i].h;
    for (int l = 0; l < tex[i].levels; l++) { tex[i].lv[l] = data + p; p += lw * lh; p = (p + 15) & ~15; lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
  }
  swizzleAll();
  pc = calloc(npc ? npc : 1, sizeof(Piece));
  carP = malloc(2 * (npc ? npc : 1)); skyP = malloc(2 * (npc ? npc : 1));
  for (unsigned i = 0; i < npc; i++) {
    memcpy(&pc[i].r, data + tableOff + 80 * i, 80);
    float *b = pc[i].r.bb;
    pc[i].cx = (b[0] + b[3]) * .5f; pc[i].cy = (b[1] + b[4]) * .5f; pc[i].cz = (b[2] + b[5]) * .5f;
    float dx = b[3] - b[0], dy = b[4] - b[1], dz = b[5] - b[2]; pc[i].rad = .5f * sqrtf(dx * dx + dy * dy + dz * dz);
    if (pc[i].r.owner == 1) carP[ncarP++] = i;
    if (pc[i].r.owner == 2) skyP[nskyP++] = i;
  }
  cl = calloc(ncell ? ncell : 1, sizeof(Cell));
  for (unsigned i = 0; i < ncell; i++) {
    memcpy(&cl[i], data + cellOff + 48 * i, 48);
    float *b = cl[i].bb;
    cl[i].cx = (b[0] + b[3]) * .5f; cl[i].cy = (b[1] + b[4]) * .5f; cl[i].cz = (b[2] + b[5]) * .5f;
    float dx = b[3] - b[0], dy = b[4] - b[1], dz = b[5] - b[2]; cl[i].rad = .5f * sqrtf(dx * dx + dy * dy + dz * dz);
    cl[i].state = 0; cl[i].mem = 0;
  }
  sceKernelDcacheWritebackAll();

  // машина, небо и всё вокруг старта — сразу, остальное фоном
  SceUID lfd = sceIoOpen(path, PSP_O_RDONLY, 0);
  for (unsigned i = 0; i < ncell; i++)
    if (cl[i].owner || cellDist(&cl[i], spx, spy, spz) < 115.f * .6f) loadCell(lfd, i);
  sceIoClose(lfd);
  sema = sceKernelCreateSema("load", 0, 0, 1, NULL);
  SceUID lt = sceKernelCreateThread("loader", loaderThread, 0x18, 0x4000, 0, 0);   // выше главного: чтение короткое, ждёт карту памяти
  if (lt >= 0) sceKernelStartThread(lt, 0, 0);

  void *fbp0 = (void *)0, *fbp1 = (void *)(BUF_W * SCR_H * 4), *zbp = (void *)(BUF_W * SCR_H * 8);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W);
  sceGuDepthBuffer(zbp, BUF_W);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuDepthRange(65535, 0); sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDepthFunc(GU_GEQUAL); sceGuEnable(GU_DEPTH_TEST); sceGuDisable(GU_CULL_FACE);
  sceGuShadeModel(GU_SMOOTH); sceGuEnable(GU_CLIP_PLANES);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuAlphaFunc(GU_GREATER, 0x40, 0xff);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);
  hudInit();

  float x = spx, y = spy, z = spz, h = sph, v = 0, vy = 0, steer = 0;
  { float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }
  int fly = 0, hud = 1, pending = 0, autob = 0, frames = 0, hudTick = 0; unsigned prev = 0;
  float fx = x, fy = y + 3, fz = z, fyaw = 0, fpitch = -.2f, fps = 0, workMs = 0, workMax = 0, cpuMs = 0, shownMax = 0;
  float camx = x - sinf(h) * 7, camy = y + 3, camz = z - cosf(h) * 7;
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG);
  unsigned last = sceKernelGetSystemTimeLow(), acc = last, optUser;
  SceCtrlData pad;
  // служебное: файл autobench рядом с EBOOT -> тест-прогон сразу и выход (для проверки в эмуляторе)
  { char fn[256]; sibling(fn, "autobench"); SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); autob = 1; }
    sibling(fn, "pvscheck"); f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); autob = 3; } }
  // служебное: opts.txt (маска переключателей, hex) и goto.txt (x z курс) — для сравнения картинок
  { char fn[256], b[64]; sibling(fn, "opts.txt"); SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0);
    if (f >= 0) { int n = sceIoRead(f, b, 63); sceIoClose(f); if (n > 0) { b[n] = 0; opt = strtoul(b, 0, 16); } }
    sibling(fn, "goto.txt"); f = sceIoOpen(fn, PSP_O_RDONLY, 0);
    if (f >= 0) { int n = sceIoRead(f, b, 63); sceIoClose(f);
      if (n > 0) { b[n] = 0; char *e; x = strtof(b, &e); z = strtof(e, &e); h = strtof(e, 0); y = 200; float g; if (ground(x, z, y, 0.f, &g)) y = g;
        camx = x - sinf(h) * 7.5f; camy = y + 3.2f; camz = z - cosf(h) * 7.5f; } } }

  optUser = opt;
  for (;;) {
    unsigned t0 = sceKernelGetSystemTimeLow();
    sceCtrlPeekBufferPositive(&pad, 1);
    float dt = (t0 - last) / 1000000.f; last = t0; if (dt > .05f) dt = .05f;
    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;
    float ax = (pad.Lx - 128) / 128.f, ay = (pad.Ly - 128) / 128.f;
    if (fabsf(ax) < .2f) ax = 0; if (fabsf(ay) < .2f) ay = 0;
    if (autob == 1) { hit |= PSP_CTRL_CIRCLE; autob = 2; }
    if (autob == 3) { benchStart(); bpass = 5; fbA = memalign(16, BUF_W * SCR_H * 4); memset(pcDiff, 0, sizeof pcDiff); autob = 2; }
    if (autob == 2 && bpass == 0 && brep[0][0]) sceKernelExitGame();
    if (hit & PSP_CTRL_SELECT) hud = !hud;
    if (hit & PSP_CTRL_CIRCLE) {
      if (bpass || brep[0][0]) { bpass = 0; brep[0][0] = 0; opt = optUser; }
      else { benchStart(); fly = 0; }
    }
    if (hit & PSP_CTRL_TRIANGLE) { fly = !fly; fx = camx; fy = camy; fz = camz; fyaw = atan2f(x - camx, -(z - camz)); fpitch = -.2f; }
    if (hit & PSP_CTRL_START) { x = spx; y = spy; z = spz; h = sph; v = vy = 0; float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }

    float cfx, cfy, cfz, ex, ey, ez;
    if (bpass) {
      benchBefore(pending, sph, &x, &y, &z, &h); v = vy = 0;
      camx = x - sinf(h) * 7.5f; camy = y + 3.2f; camz = z - cosf(h) * 7.5f;
      ex = camx; ey = camy; ez = camz;
      cfx = x - camx; cfy = (y + 1.4f) - camy; cfz = z - camz;
      float l = sqrtf(cfx * cfx + cfy * cfy + cfz * cfz); cfx /= l; cfy /= l; cfz /= l;
    } else if (!fly) {
      float st = ax;
      if (pad.Buttons & PSP_CTRL_LEFT) st = -1; if (pad.Buttons & PSP_CTRL_RIGHT) st = 1;
      steer += (st - steer) * fminf(1.f, dt * 8.f);
      int gas = pad.Buttons & (PSP_CTRL_CROSS | PSP_CTRL_RTRIGGER);
      int brake = pad.Buttons & (PSP_CTRL_SQUARE | PSP_CTRL_LTRIGGER);
      if (gas) v += (v < 0 ? 30.f : 14.f) * dt;
      else if (brake) v -= (v > 0 ? 30.f : 8.f) * dt;
      else v -= v * 1.2f * dt;
      if (v > 30.f) v = 30.f; if (v < -9.f) v = -9.f;
      float turn = steer * 2.1f * fminf(1.f, fabsf(v) / 6.f) / (1.f + fabsf(v) / 25.f);
      h -= turn * dt * (v >= 0 ? 1.f : -1.f);
      float nx = x + sinf(h) * v * dt, nz = z + cosf(h) * v * dt, g;
      float bump = v >= 0 ? 2.2f : -2.2f;   // нос/багажник машины
      float px = nx + sinf(h) * bump, pz = nz + cosf(h) * bump;
      int stuck = wallAt(x, z, y);          // если застряли в стене — выпускаем
      if (ground(nx, nz, y, 1.0f, &g) && g > y - 25.f && (stuck || (!wallAt(px, pz, y) && !wallAt(nx, nz, y)))) { x = nx; z = nz; }
      else v = -v * .2f;
      if (ground(x, z, y, 1.0f, &g)) {
        if (g >= y - .35f && vy <= 0) { y = g; vy = 0; }
        else { vy -= 22.f * dt; y += vy * dt; if (y < g) { y = g; vy = 0; } }
      } else { vy -= 22.f * dt; y += vy * dt; }
      if (y < -200) { x = spx; y = spy; z = spz; v = vy = 0; }
      float tx = x - sinf(h) * 7.5f, tz = z - cosf(h) * 7.5f, ty = y + 3.2f, k = fminf(1.f, dt * 5.f);
      camx += (tx - camx) * k; camy += (ty - camy) * k; camz += (tz - camz) * k;
      ex = camx; ey = camy; ez = camz;
      cfx = x - camx; cfy = (y + 1.4f) - camy; cfz = z - camz;
      float l = sqrtf(cfx * cfx + cfy * cfy + cfz * cfz); cfx /= l; cfy /= l; cfz /= l;
    } else {
      fyaw += ax * 2.f * dt; fpitch -= ay * 1.5f * dt;
      if (fpitch > 1.5f) fpitch = 1.5f; if (fpitch < -1.5f) fpitch = -1.5f;
      float sp_ = (pad.Buttons & PSP_CTRL_CROSS) ? 60.f : 15.f;
      cfx = sinf(fyaw) * cosf(fpitch); cfy = sinf(fpitch); cfz = -cosf(fyaw) * cosf(fpitch);
      float rx = cosf(fyaw), rz = sinf(fyaw);
      if (pad.Buttons & PSP_CTRL_UP) { fx += cfx * sp_ * dt; fy += cfy * sp_ * dt; fz += cfz * sp_ * dt; }
      if (pad.Buttons & PSP_CTRL_DOWN) { fx -= cfx * sp_ * dt; fy -= cfy * sp_ * dt; fz -= cfz * sp_ * dt; }
      if (pad.Buttons & PSP_CTRL_RIGHT) { fx += rx * sp_ * dt; fz += rz * sp_ * dt; }
      if (pad.Buttons & PSP_CTRL_LEFT) { fx -= rx * sp_ * dt; fz -= rz * sp_ * dt; }
      if (pad.Buttons & PSP_CTRL_RTRIGGER) fy += sp_ * dt;
      if (pad.Buttons & PSP_CTRL_LTRIGGER) fy -= sp_ * dt;
      ex = fx; ey = fy; ez = fz;
    }

    pending = stream(ex, ey, ez);
    drawDist = (opt & O_D100) ? 100.f : 115.f;
    eyeX = ex; eyeY = ey; eyeZ = ez; cfX = cfx; cfY = cfy; cfZ = cfz;
    setupPlanes(cfx, cfy, cfz);
    cullCity(fly);

    sceGuStart(GU_DIRECT, list);
    resetState(); drawnTris = 0; draws = 0; binds = 0;
    if (opt & O_QVP) { sceGuViewport(2048, 2048, SCR_W / 2, SCR_H / 2); sceGuScissor(SCR_W / 4, SCR_H / 4, SCR_W * 3 / 4, SCR_H * 3 / 4); }
    else { sceGuViewport(2048, 2048, SCR_W, SCR_H); sceGuScissor(0, 0, SCR_W, SCR_H); }
    sceGuEnable(GU_DEPTH_TEST); sceGuDepthFunc(GU_GEQUAL); sceGuShadeModel(GU_SMOOTH);
    sceGuTexWrap(GU_REPEAT, GU_REPEAT); sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
    sceGuTexScale(128.f, 128.f); sceGuTexOffset(0.f, 0.f); sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
    sceGuClutMode(GU_PSM_8888, 0, 0xff, 0);
    sceGuFog(drawDist * .52f, drawDist, SKY & 0xffffff);
    sceGuClearColor(SKY); sceGuClearDepth(0);
    sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
    sceGumMatrixMode(GU_PROJECTION); sceGumLoadIdentity();
    sceGumPerspective(FOVY, ASPECT, 0.7f, drawDist + 10.f);
    sceGumMatrixMode(GU_VIEW); sceGumLoadIdentity();
    ScePspFVector3 eye = {ex, ey, ez}, at = {ex + cfx, ey + cfy, ez + cfz}, up = {0, 1, 0};
    sceGumLookAt(&eye, &at, &up);
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity();
    sceGumUpdateMatrix();

    // небо: вокруг камеры, без тумана и без глубины (слои в порядке файла); сектора за кадром не рисуем
    if (opt & O_SKY) {
      sceGuDisable(GU_FOG); sceGuDisable(GU_DEPTH_TEST);
      for (int i = 0; i < nskyP; i++) {
        Piece *d = &pc[skyP[i]]; if (cl[d->r.cell].state != 2) continue;
        if ((opt & O_SKYCULL) && !visBox(d->r.bb, ex, ey, ez)) continue;
        drawPiece(d, 0, ex, ey, ez, 1, 0);
      }
      sceGuEnable(GU_DEPTH_TEST);
    }
    sceGuEnable(GU_FOG);
    // город: отсортированный список
    if (opt & O_LEAN) for (int i = 0; i < nd; i++) drawPiece(&pc[sp[i]], sf[i], 0, 0, 0, 1, 0);
    else {
      sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity(); resetState();
      for (int i = 0; i < nd; i++) drawPieceLegacy(&pc[sp[i]], sf[i]);
      resetState();
    }
    // машина
    { float ca = cosf(h + GU_PI), sa = sinf(h + GU_PI);
      for (int i = 0; i < ncarP; i++) { Piece *d = &pc[carP[i]]; if (cl[d->r.cell].state == 2) drawPiece(d, 0, x, y + lift, z, ca, sa); } }
    sceGuDepthMask(GU_FALSE);
    if (hud && (opt & O_HUD)) { sceGuScissor(0, 0, SCR_W, SCR_H); hudDraw(); resetState(); }
    sceGuFinish();
    unsigned t3 = sceKernelGetSystemTimeLow();
    sceGuSync(0, 0);
    unsigned t4 = sceKernelGetSystemTimeLow();
    workMs = (t4 - t0) / 1000.f; cpuMs = (t3 - t0) / 1000.f; if (workMs > workMax) workMax = workMs;

    curFb = (unsigned *)((unsigned)sceGeEdramGetAddr() + (unsigned)fbp0);
    int missed = 0;
    if (!bpass || bVsync) {
      sceDisplayWaitVblankStart();
      unsigned vc = sceDisplayGetVcount(); missed = vc - lastVc > 1; lastVc = vc;
    }
    if (bpass) benchAfter(workMs, cpuMs, missed);
    fbp0 = sceGuSwapBuffers();

    frames++;
    if (t4 - acc >= 1000000) { fps = frames * 1000000.f / (t4 - acc); frames = 0; acc = t4; shownMax = workMax; workMax = 0; }
    if (++hudTick >= 15) {                           // текст счётчика обновляем 4 раза в секунду
      hudTick = 0; char s[96];
      hudClear();
      snprintf(s, sizeof s, "FPS %4.1f  tris %4.1fk  draws %d  RAM %.1fMB  %s %3.0f km/h", fps, drawnTris / 1000.f, draws,
               loadedBytes / 1048576.f, fly ? "FLY" : "CAR", fabsf(v) * 3.6f);
      hudLine(0, 0xffffffff, s);
      snprintf(s, sizeof s, "work %4.1f ms (max %4.1f)  cpu %4.1f  %s", workMs, shownMax, cpuMs, pvsUsed ? "PVS" : "");
      hudLine(1, 0xffffffff, s);
      hudLine(2, 0xffc0c0c0, fly ? "stick:look dpad:move L/R:down/up X:fast  /\\:car START:reset"
                                 : "X/R:gas []/L:brake stick:steer  /\\:fly  O:bench START:reset");
      if (bpass) {
        static const char *pn[] = {"", "P1 whole level", "P2 variants", "P3 vsync"};
        int tot = bpass == 1 ? nbp * 4 : bpass == 2 ? nw2 : nw3;
        snprintf(s, sizeof s, "BENCH %s  %d / %d %s", pn[bpass], bview, tot, bpass == 2 ? VAR[bvar].name : "");
        hudLine(4, 0xff80ffff, s);
      } else if (brep[0][0]) { hudLine(4, 0xff80ffff, brep[0]); hudLine(5, 0xff80ffff, brep[1]); }
    }
  }
  return 0;
}
