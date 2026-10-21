// SHAR PSP v7: город клетками 40x40 м подгружается по мере езды (как в Crash на PS1), машина, туман.
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <pspgu.h>
#include <pspgum.h>
#include <psprtc.h>
#include <psppower.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <math.h>

PSP_MODULE_INFO("SHARVIEW", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define DRAW_DIST 115.f
#define LOAD_DIST 150.f
#define DROP_DIST 200.f
#define FOG_NEAR 60.f
#define LOD_DIST 50.f
#define CONE_COS 0.60f
#define CONE_SIN 0.80f
#define SKY 0xffe0b070
static unsigned int __attribute__((aligned(16))) list[262144];

typedef struct { short u, v; unsigned int c; short x, y, z, pad; } Vert;
typedef struct { int w, h, levels; void *pal; void *lv[8]; } Tex;
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
typedef struct { unsigned key; unsigned short p, far; } DrawItem;

static Tex *tex; static unsigned ntex, npc, ncell;
static Piece *pc; static Cell *cl;
static short *hm, *wl; static float hox, hoz, hcell; static int hw, hh;
static char path[256];
static SceUID sema; static volatile int req = -1; static volatile unsigned loadedBytes = 0;
#define MAXDRAW 2048
static DrawItem dl[MAXDRAW];

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static void fail(const char *msg) {
  pspDebugScreenInit(); pspDebugScreenPrintf("SHAR PSP\n\n%s\n\nPress HOME to exit.", msg);
  sceKernelSleepThread();
}

// клетка целиком одним чтением: вершины и индексы всех её кусков
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
  c->state = 2;
}
static int loaderThread(SceSize a, void *b) {
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  for (;;) {
    sceKernelWaitSema(sema, 1, NULL);
    int i = req; if (i >= 0 && fd >= 0) loadCell(fd, i);
    req = -1;
  }
  return 0;
}
static void unloadCell(Cell *c) {
  if (c->state == 2) { loadedBytes -= c->size; free(c->mem); c->mem = 0; }
  c->state = 0;
}

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

static int bound = -2;
static void bindTex(int t) {
  if (t == bound) return; bound = t;
  if (t < 0 || t >= (int)ntex) { sceGuDisable(GU_TEXTURE_2D); return; }
  Tex *x = &tex[t];
  sceGuEnable(GU_TEXTURE_2D);
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0); sceGuClutLoad(32, x->pal);
  sceGuTexMode(GU_PSM_T8, x->levels - 1, 0, 0);
  int lw = x->w, lh = x->h;
  for (int l = 0; l < x->levels; l++) { sceGuTexImage(l, lw, lh, lw, x->lv[l]); lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
  sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
  sceGuTexFilter(x->levels > 1 ? GU_LINEAR_MIPMAP_LINEAR : GU_LINEAR, GU_LINEAR);
  sceGuTexOffset(0.f, 0.f);
}

static long drawnTris;
static void drawPiece(Piece *d, int far) {
  unsigned short *ix = far ? d->fidx : d->idx; int cnt = far ? (int)d->r.nf : d->r.ni;
  if (cnt <= 0) return; drawnTris += cnt / 3;
  bindTex(d->r.tex); sceGuTexScale(128.f, 128.f);
  if (d->r.flags & 1) sceGuEnable(GU_ALPHA_TEST); else sceGuDisable(GU_ALPHA_TEST);
  if (d->r.flags & 2) { sceGuEnable(GU_BLEND); sceGuDepthMask(GU_TRUE); }
  else { sceGuDisable(GU_BLEND); sceGuDepthMask((d->r.flags & 4) ? GU_TRUE : GU_FALSE); }
  sceGumPushMatrix();
  ScePspFVector3 o = {d->r.ox, d->r.oy, d->r.oz}, s = {d->r.sc, d->r.sc, d->r.sc};
  sceGumTranslate(&o); sceGumScale(&s);
  for (int k = 0; k < cnt; k += 65532) {
    int n = cnt - k; if (n > 65532) n = 65532;
    sceGumDrawArray(GU_TRIANGLES, GU_INDEX_16BIT | GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_3D,
                    n, ix + k, d->v);
  }
  sceGumPopMatrix();
}
static void drawOwner(unsigned owner) {
  for (unsigned i = 0; i < ncell; i++) {
    Cell *c = &cl[i]; if (c->owner != owner || c->state != 2) continue;
    for (unsigned k = c->first; k < c->first + c->n; k++) drawPiece(&pc[k], 0);
  }
}
static int cmpDraw(const void *a, const void *b) {
  unsigned x = ((const DrawItem *)a)->key, y = ((const DrawItem *)b)->key; return x < y ? -1 : x > y;
}

static float cellDist(Cell *c, float x, float y, float z) {
  float dx = c->cx - x, dy = c->cy - y, dz = c->cz - z;
  return sqrtf(dx * dx + dy * dy + dz * dz) - c->rad;
}

// планировщик: выгрузить далёкое, отдать загрузчику ближайшую нужную клетку
static int stream(float x, float y, float z) {   // 1 = ещё что-то грузится
  for (unsigned i = 0; i < ncell; i++)
    if (!cl[i].owner && cl[i].state >= 2 && cellDist(&cl[i], x, y, z) > DROP_DIST) unloadCell(&cl[i]);
  if (req >= 0) return 1;
  int best = -1; float bd = LOAD_DIST;
  for (unsigned i = 0; i < ncell; i++) {
    if (cl[i].state != 0) continue;
    float d = cellDist(&cl[i], x, y, z);
    if (d < bd) { bd = d; best = i; }
  }
  if (best >= 0) { cl[best].state = 1; req = best; sceKernelSignalSema(sema, 1); return 1; }
  return 0;
}

// тест-прогон (кнопка O): камера объезжает весь уровень, меряем время кадра, пишем bench.txt
#define MAXBP 1024
#define BSUB 24                 // 4 направления x 6 кадров, первые 2 кадра направления не считаем
typedef struct { float ms, x, z, h; int tris, draws; } BenchHit;
static float bpx[MAXBP], bpy[MAXBP], bpz[MAXBP]; static int nbp;
static BenchHit worst[10]; static double bsum; static int bcount, bover, bstage, bwait;
static float bworst;
static char bline[3][96];
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
static void benchRecord(float ms, float x, float z, float h, int tris, int draws) {
  bsum += ms; bcount++; if (ms > 16.7f) bover++; if (ms > bworst) bworst = ms;
  int k = 9; if (ms <= worst[k].ms) return;
  while (k > 0 && worst[k - 1].ms < ms) { worst[k] = worst[k - 1]; k--; }
  worst[k] = (BenchHit){ms, x, z, h, tris, draws};
}
static void benchWrite(void) {
  snprintf(bline[0], 96, "BENCH %d pts: avg %.1f ms, worst %.1f ms", nbp, bcount ? bsum / bcount : 0., bworst);
  snprintf(bline[1], 96, "frames over 16.7ms: %d of %d (%.1f%%)", bover, bcount, bcount ? 100.f * bover / bcount : 0.f);
  snprintf(bline[2], 96, "report: bench.txt   O: close");
  char fn[256]; strcpy(fn, path); char *sl = strrchr(fn, '/'); strcpy(sl ? sl + 1 : fn, "bench.txt");
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f < 0) return;
  char b[4096]; int n = snprintf(b, sizeof b, "%s\n%s\nworst frames (ms x z heading tris draws):\n", bline[0], bline[1]);
  for (int i = 0; i < 10 && n < (int)sizeof b - 100; i++)
    n += snprintf(b + n, sizeof b - n, "%.2f %.0f %.0f %.2f %d %d\n", worst[i].ms, worst[i].x, worst[i].z, worst[i].h, worst[i].tris, worst[i].draws);
  sceIoWrite(f, b, n); sceIoClose(f);
}

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  pspDebugScreenInit(); pspDebugScreenPrintf("Loading Springfield...\n");

  strncpy(path, argv[0], sizeof(path) - 16); path[sizeof(path) - 16] = 0;
  char *slash = strrchr(path, '/'); if (slash) slash[1] = 0; else path[0] = 0;
  strcat(path, "level.shr");

  // резидентная часть: заголовок, карта высот, текстуры, таблица кусков
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  if (fd < 0) fail("level.shr not found next to EBOOT.PBP.");
  unsigned char hdr[96];
  if (sceIoRead(fd, hdr, 96) != 96 || memcmp(hdr, "SHR7", 4)) fail("level.shr is an old version. Run the export again.");
  ntex = *(unsigned *)(hdr + 4); npc = *(unsigned *)(hdr + 8);
  float *hd = (float *)(hdr + 12);
  float spx = hd[6], spy = hd[7], spz = hd[8], sph = hd[9], lift = hd[10];
  hox = hd[11]; hoz = hd[12]; hcell = hd[13]; hw = *(int *)(hd + 14); hh = *(int *)(hd + 15);
  unsigned tableOff = *(unsigned *)(hdr + 76);
  ncell = *(unsigned *)(hdr + 80); unsigned cellOff = *(unsigned *)(hdr + 84);
  unsigned residentSize = cellOff + 48 * ncell;
  unsigned char *data = memalign(16, residentSize);
  if (!data) {
    char m[160]; snprintf(m, sizeof m, "Not enough memory: %.1f MB needed, %.1f MB free.",
      residentSize / 1048576.f, sceKernelMaxFreeMemSize() / 1048576.f); fail(m);
  }
  sceIoLseek32(fd, 0, PSP_SEEK_SET);
  if (sceIoRead(fd, data, residentSize) != (int)residentSize) fail("Read error.");
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
  pc = calloc(npc ? npc : 1, sizeof(Piece));
  for (unsigned i = 0; i < npc; i++) {
    memcpy(&pc[i].r, data + tableOff + 80 * i, 80);
    float *b = pc[i].r.bb;
    pc[i].cx = (b[0] + b[3]) * .5f; pc[i].cy = (b[1] + b[4]) * .5f; pc[i].cz = (b[2] + b[5]) * .5f;
    float dx = b[3] - b[0], dy = b[4] - b[1], dz = b[5] - b[2]; pc[i].rad = .5f * sqrtf(dx * dx + dy * dy + dz * dz);
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
    if (cl[i].owner || cellDist(&cl[i], spx, spy, spz) < DRAW_DIST * .6f) loadCell(lfd, i);
  sceIoClose(lfd);
  sema = sceKernelCreateSema("load", 0, 0, 1, NULL);
  SceUID lt = sceKernelCreateThread("loader", loaderThread, 0x18, 0x4000, 0, 0);
  if (lt >= 0) sceKernelStartThread(lt, 0, 0);

  void *fbp0 = (void *)0, *fbp1 = (void *)(BUF_W * SCR_H * 4), *zbp = (void *)(BUF_W * SCR_H * 8);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W);
  sceGuDepthBuffer(zbp, BUF_W);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuDepthRange(65535, 0); sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDepthFunc(GU_GEQUAL); sceGuEnable(GU_DEPTH_TEST); sceGuDisable(GU_CULL_FACE);
  sceGuShadeModel(GU_SMOOTH); sceGuEnable(GU_CLIP_PLANES);
  sceGuTexWrap(GU_REPEAT, GU_REPEAT); sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuAlphaFunc(GU_GREATER, 0x40, 0xff);
  sceGuFog(FOG_NEAR, DRAW_DIST, SKY & 0xffffff); sceGuEnable(GU_FOG);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);

  float x = spx, y = spy, z = spz, h = sph, v = 0, vy = 0, steer = 0;
  { float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }
  int fly = 0, hud = 1, bench = -1, benchDone = 0, pending = 0; unsigned prev = 0; float workMs = 0, workMax = 0;
  float fx = x, fy = y + 3, fz = z, fyaw = 0, fpitch = -.2f;
  float camx = x - sinf(h) * 7, camy = y + 3, camz = z - cosf(h) * 7;
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG);
  u64 last, now, acc; sceRtcGetCurrentTick(&last); acc = last; float fps = 0; int frames = 0, drawn = 0;
  SceCtrlData pad;
  // служебное: файл autobench рядом с EBOOT -> тест-прогон сразу и выход (для проверки в эмуляторе)
  int autob = 0;
  { char fn[256]; strcpy(fn, path); char *sl = strrchr(fn, '/'); strcpy(sl ? sl + 1 : fn, "autobench");
    SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); autob = 1; } }

  for (;;) {
    sceCtrlPeekBufferPositive(&pad, 1);
    sceRtcGetCurrentTick(&now); float dt = (now - last) / 1000000.f; last = now; if (dt > .05f) dt = .05f;
    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;
    float ax = (pad.Lx - 128) / 128.f, ay = (pad.Ly - 128) / 128.f;
    if (fabsf(ax) < .2f) ax = 0; if (fabsf(ay) < .2f) ay = 0;
    if (hit & PSP_CTRL_SELECT) hud = !hud;
    if (hit & PSP_CTRL_TRIANGLE) { fly = !fly; fx = camx; fy = camy; fz = camz; fyaw = atan2f(x - camx, -(z - camz)); fpitch = -.2f; }
    if (autob == 1) { hit |= PSP_CTRL_CIRCLE; autob = 2; }
    if (autob == 2 && benchDone) sceKernelExitGame();
    if (hit & PSP_CTRL_CIRCLE) {
      if (bench >= 0 || benchDone) { bench = -1; benchDone = 0; }
      else { benchPoints(); bench = 0; bstage = 0; bwait = 0; bsum = 0; bcount = bover = 0; bworst = 0; memset(worst, 0, sizeof worst); fly = 0; }
    }
    int measure = 0;
    if (bench >= 0) {
      if (bstage == 0) {
        x = bpx[bench]; y = bpy[bench]; z = bpz[bench]; v = vy = 0;
        if (pending && ++bwait < 600) {} else { bstage = 1; bwait = 0; }
      } else if (++bstage > BSUB) { bstage = 0; if (++bench >= nbp) { bench = -1; benchDone = 1; benchWrite(); } }
      if (bench >= 0) {
        h = sph + (bstage > 0 ? ((bstage - 1) / 6) * GU_PI * .5f : 0.f);
        measure = bstage > 0 && (bstage - 1) % 6 >= 2;
        camx = x - sinf(h) * 7.5f; camy = y + 3.2f; camz = z - cosf(h) * 7.5f;
      }
    }
    if (hit & PSP_CTRL_START) { x = spx; y = spy; z = spz; h = sph; v = vy = 0; float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }

    float cfx, cfy, cfz, eyex, eyey, eyez;
    if (bench >= 0) {
      eyex = camx; eyey = camy; eyez = camz;
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
      eyex = camx; eyey = camy; eyez = camz;
      cfx = x - camx; cfy = (y + 1.4f) - camy; cfz = z - camz;
      float l = sqrtf(cfx * cfx + cfy * cfy + cfz * cfz); cfx /= l; cfy /= l; cfz /= l;
    } else {
      fyaw += ax * 2.f * dt; fpitch -= ay * 1.5f * dt;
      if (fpitch > 1.5f) fpitch = 1.5f; if (fpitch < -1.5f) fpitch = -1.5f;
      float sp = (pad.Buttons & PSP_CTRL_CROSS) ? 60.f : 15.f;
      cfx = sinf(fyaw) * cosf(fpitch); cfy = sinf(fpitch); cfz = -cosf(fyaw) * cosf(fpitch);
      float rx = cosf(fyaw), rz = sinf(fyaw);
      if (pad.Buttons & PSP_CTRL_UP) { fx += cfx * sp * dt; fy += cfy * sp * dt; fz += cfz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_DOWN) { fx -= cfx * sp * dt; fy -= cfy * sp * dt; fz -= cfz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_RIGHT) { fx += rx * sp * dt; fz += rz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_LEFT) { fx -= rx * sp * dt; fz -= rz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_RTRIGGER) fy += sp * dt;
      if (pad.Buttons & PSP_CTRL_LTRIGGER) fy -= sp * dt;
      eyex = fx; eyey = fy; eyez = fz;
    }

    pending = stream(eyex, eyey, eyez);

    sceGuStart(GU_DIRECT, list);
    sceGuClearColor(SKY); sceGuClearDepth(0);
    sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
    sceGumMatrixMode(GU_PROJECTION); sceGumLoadIdentity();
    sceGumPerspective(62.f, 16.f / 9.f, 0.7f, DRAW_DIST + 10.f);
    sceGumMatrixMode(GU_VIEW); sceGumLoadIdentity();
    ScePspFVector3 eye = {eyex, eyey, eyez}, at = {eyex + cfx, eyey + cfy, eyez + cfz}, up = {0, 1, 0};
    sceGumLookAt(&eye, &at, &up);
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity();

    drawn = 0; drawnTris = 0; bound = -2;
    // небо: вокруг камеры, без тумана и без глубины
    sceGumPushMatrix(); ScePspFVector3 ep = {eyex, eyey, eyez}; sceGumTranslate(&ep);
    sceGuDisable(GU_FOG); sceGuDisable(GU_DEPTH_TEST);
    drawOwner(2);
    sceGuEnable(GU_DEPTH_TEST); sceGuEnable(GU_FOG); sceGumPopMatrix();
    // город: видимые клетки -> список кусков, сортируем по текстуре
    int nd = 0;
    for (unsigned i = 0; i < ncell; i++) {
      Cell *c = &cl[i]; if (c->owner || c->state != 2) continue;
      float dx = c->cx - eyex, dy = c->cy - eyey, dz = c->cz - eyez;
      float dist2 = dx * dx + dy * dy + dz * dz, dist = sqrtf(dist2);
      if (dist - c->rad > DRAW_DIST) continue;
      float f = dx * cfx + dy * cfy + dz * cfz;                 // вдоль взгляда
      float l = sqrtf(fmaxf(0.f, dist2 - f * f));               // вбок от взгляда
      if (l * CONE_COS - f * CONE_SIN > c->rad) continue;       // вне конуса обзора
      for (unsigned k = c->first; k < c->first + c->n && nd < MAXDRAW; k++) {
        Piece *d = &pc[k];
        float ex = d->cx - eyex, ey = d->cy - eyey, ez = d->cz - eyez;
        float pd2 = ex * ex + ey * ey + ez * ez, pd = sqrtf(pd2);
        if (pd - d->rad > DRAW_DIST) continue;
        float pf = ex * cfx + ey * cfy + ez * cfz, pl = sqrtf(fmaxf(0.f, pd2 - pf * pf));
        if (pl * CONE_COS - pf * CONE_SIN > d->rad) continue;
        dl[nd].key = ((d->r.flags & 3) << 16) | (unsigned)(d->r.tex & 0xffff);
        dl[nd].p = k; dl[nd].far = pd - d->rad > LOD_DIST; nd++;
      }
    }
    qsort(dl, nd, sizeof(DrawItem), cmpDraw);
    for (int i = 0; i < nd; i++) drawPiece(&pc[dl[i].p], dl[i].far);
    drawn = nd;
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity();
    ScePspFVector3 cp = {x, y + lift, z}; sceGumTranslate(&cp); sceGumRotateY(h + GU_PI);
    drawOwner(1);
    sceGumLoadIdentity();
    sceGuDepthMask(GU_FALSE);
    sceGuFinish(); sceGuSync(0, 0);

    frames++; if (now - acc >= 1000000) { fps = frames * 1000000.f / (now - acc); frames = 0; acc = now; workMax = 0; }
    if (hud) {
      pspDebugScreenSetOffset((int)fbp0); pspDebugScreenSetXY(0, 0);
      pspDebugScreenPrintf("FPS %4.1f  tris %4.1fk  draws %d  RAM %.1fMB  %s %3.0f km/h\n", fps, drawnTris / 1000.f, drawn,
                           loadedBytes / 1048576.f, fly ? "FLY" : "CAR", fabsf(v) * 3.6f);
      pspDebugScreenPrintf(fly ? "stick:look dpad:move L/R:down/up X:fast  /\\:car START:reset"
                               : "X/R:gas []/L:brake stick/dpad:steer  /\\:fly  O:bench START:reset");
      pspDebugScreenPrintf("\nwork %4.1f ms (max/sec %4.1f)\n", workMs, workMax);
      if (bench >= 0) pspDebugScreenPrintf("BENCH %d / %d ...\n", bench, nbp);
      if (benchDone) pspDebugScreenPrintf("%s\n%s\n%s\n", bline[0], bline[1], bline[2]);
    }
    { u64 t1; sceRtcGetCurrentTick(&t1); float ms = (t1 - now) / 1000.f;
      workMs = ms; if (ms > workMax) workMax = ms;
      if (measure) benchRecord(ms, x, z, h, (int)drawnTris, drawn); }
    sceDisplayWaitVblankStart(); fbp0 = sceGuSwapBuffers();
  }
  return 0;
}
