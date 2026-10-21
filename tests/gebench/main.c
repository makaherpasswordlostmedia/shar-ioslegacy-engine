// GEBENCH — шаг 0 аудита оптимизации (docs/АУДИТ_ОПТИМИЗАЦИИ_2026-09-27.md): одна и та же сцена
// (худший вид bench v8: 345 -81 курс 1, город, ближние версии кусков, ~11 тыс. треуг.) в нескольких вариантах
// подачи геометрии, по 200 кадров, время GE в gebench.txt рядом с EBOOT. Данные — cell.bin (tools/strips.py).
// Служебное (эмулятор): show.txt = буква варианта -> рисовать только его (для снимка окна), ff.txt = cw/ccw,
// autoexit -> выйти после замера.
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspgu.h>
#include <pspgum.h>
#include <pspge.h>
#include <psprtc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>

PSP_MODULE_INFO("GEBENCH", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define WARM 20
#define NFR 200
#define NSET 5
#define VRAM_DATA 0x154000   // после двух кадров 8888 и глубины

typedef struct { unsigned short w, h, levels, pad; unsigned pal, lv[8], pad2; } TexRec;      // 48 Б
typedef struct { unsigned cnt, nv, voff, ioff; } SetRec;
typedef struct { int tex, flags, dbl, far; float sc, ox, oy, oz; SetRec s[NSET]; } PieceRec; // 112 Б
typedef struct {
  char magic[4]; unsigned ntex, npc, nset; float eye[3], at[3]; unsigned fog, frontCcw; unsigned set[NSET][4];
} Hdr;                                                                                     // 128 Б

typedef struct { const char *name, *desc; int set, strip, indexed, vram, c5650, cull, inl; } Var;
// cull: 0 выкл, 1 везде, 2 везде кроме «смешанных» кусков (dbl); inl: список строится CPU в кадре, как в движке
static const Var VAR[] = {
  {"a", "list, np.unique order (engine now)", 0, 0, 1, 0, 0, 0, 0},
  {"b", "list, verts by first use", 1, 0, 1, 0, 0, 0, 0},
  {"c", "idx strips + degenerates", 2, 1, 1, 0, 0, 0, 0},
  {"d", "non-indexed strips", 3, 1, 0, 0, 0, 0, 0},
  {"e", "c, verts+idx in VRAM", 2, 1, 1, 1, 0, 0, 0},
  {"f", "c(fixed winding) + 5650 dither + cull", 4, 1, 1, 0, 1, 2, 0},
  {"g", "c + cull everywhere (no fix), 8888", 2, 1, 1, 0, 0, 1, 0},
  {"h", "c + 5650 dither only", 2, 1, 1, 0, 1, 0, 0},
  {"a*", "a, list built by CPU each frame", 0, 0, 1, 0, 0, 0, 1},
  {"c*", "c, list built by CPU each frame", 2, 1, 1, 0, 0, 0, 1},
  {"a2", "a again (drift check)", 0, 0, 1, 0, 0, 0, 0},
};
#define NVAR (int)(sizeof VAR / sizeof VAR[0])

static unsigned int __attribute__((aligned(64))) list[262144];
static unsigned *pre[NVAR];
static unsigned char *D; static Hdr *H; static TexRec *T; static PieceRec *P;
static unsigned char *vramSet;   // копия набора 2 в VRAM (вершины, потом индексы)
static char path[256];
static int ffOverride = -1;

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static void sibling(char *out, const char *name) {
  strcpy(out, path); char *sl = strrchr(out, '/'); strcpy(sl ? sl + 1 : out, name);
}
static void fail(const char *m) { pspDebugScreenInit(); pspDebugScreenPrintf("GEBENCH\n\n%s\n\nHOME to exit.", m); sceKernelSleepThread(); }
static int readSmall(const char *name, char *b, int n) {
  char fn[256]; sibling(fn, name); SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0);
  if (f < 0) return -1; int r = sceIoRead(f, b, n - 1); sceIoClose(f); b[r > 0 ? r : 0] = 0; return r > 0 ? r : 0;
}

// ---- отрисовка, состояние GE как в viewer/main.c (лёгкая привязка текстуры командами) ----
static int bound, curFlags, curCull;
static int ilog2(int v) { return 31 - __builtin_clz(v); }
static void bindTex(int t) {
  if (t == bound) return; bound = t;
  if (t < 0) { sceGuDisable(GU_TEXTURE_2D); return; }
  sceGuEnable(GU_TEXTURE_2D);
  TexRec *x = &T[t]; unsigned p = (unsigned)(D + x->pal);
  sceGuSendCommandi(0xb0, p & 0xffffff); sceGuSendCommandi(0xb1, (p >> 8) & 0xf0000); sceGuSendCommandi(0xc4, 32);
  sceGuSendCommandi(0xc2, ((x->levels - 1) << 16) | 1);
  sceGuSendCommandi(0xc3, GU_PSM_T8);
  int lw = x->w, lh = x->h;
  for (int l = 0; l < x->levels; l++) {
    unsigned a = (unsigned)(D + x->lv[l]);
    sceGuSendCommandi(0xa0 + l, a & 0xffffff);
    sceGuSendCommandi(0xa8 + l, ((a >> 8) & 0x0f0000) | lw);
    sceGuSendCommandi(0xb8 + l, (ilog2(lh) << 8) | ilog2(lw));
    lw >>= 1; lh = lh > 1 ? lh >> 1 : 1;
  }
  sceGuSendCommandi(0xcb, 0);
  sceGuTexFilter(x->levels > 1 ? GU_LINEAR_MIPMAP_LINEAR : GU_LINEAR, GU_LINEAR);
}
static void setFlags(int fl) {
  fl &= 7; if (fl == curFlags) return; curFlags = fl;
  if (fl & 1) sceGuEnable(GU_ALPHA_TEST); else sceGuDisable(GU_ALPHA_TEST);
  if (fl & 2) sceGuEnable(GU_BLEND); else sceGuDisable(GU_BLEND);
  sceGuDepthMask((fl & 6) ? GU_TRUE : GU_FALSE);
}
static void setCull(int on) {
  if (on == curCull) return; curCull = on;
  if (on) sceGuEnable(GU_CULL_FACE); else sceGuDisable(GU_CULL_FACE);
}
static long drawIdxCount;
static void emit(const Var *v) {
  bound = -2; curFlags = -1; curCull = -1; drawIdxCount = 0;
  int vt = GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_3D | (v->indexed ? GU_INDEX_16BIT : 0);
  int prim = v->strip ? GU_TRIANGLE_STRIP : GU_TRIANGLES;
  for (unsigned i = 0; i < H->npc; i++) {
    PieceRec *p = &P[i]; SetRec *s = &p->s[v->set];
    if (!s->cnt) continue;
    bindTex(p->tex); setFlags(p->flags);
    setCull(v->cull == 1 || (v->cull == 2 && !p->dbl));
    float k = p->sc;
    ScePspFMatrix4 m = {{k, 0, 0, 0}, {0, k, 0, 0}, {0, 0, k, 0}, {p->ox, p->oy, p->oz, 1}};
    sceGuSetMatrix(GU_MODEL, &m);
    unsigned char *vb, *ib;
    if (v->vram) { vb = vramSet + (s->voff - H->set[2][0]); ib = vramSet + H->set[2][1] + (s->ioff - H->set[2][2]); }
    else { vb = D + s->voff; ib = v->indexed ? D + s->ioff : 0; }
    drawIdxCount += s->cnt;
    if (!v->strip) {
      for (unsigned o = 0; o < s->cnt; o += 65532) {
        unsigned n = s->cnt - o; if (n > 65532) n = 65532;
        sceGuDrawArray(prim, vt, n, ib + o * 2, vb);
      }
    } else if (v->indexed) {                       // длинная полоса: куски с перекрытием 2, начало на чётной позиции
      for (unsigned o = 0; o + 2 < s->cnt; o += 65532) {
        unsigned n = s->cnt - o; if (n > 65534) n = 65534;
        sceGuDrawArray(prim, vt, n, ib + o * 2, vb);
      }
    } else {
      for (unsigned o = 0; o + 2 < s->cnt; o += 65532) {
        unsigned n = s->cnt - o; if (n > 65534) n = 65534;
        sceGuDrawArray(prim, vt, n, 0, vb + o * 16);
      }
    }
  }
}

// ---- кадр ----
static void *drawBuf = (void *)0, *dispBuf = (void *)(BUF_W * SCR_H * 4);
static const ScePspIMatrix4 dith = {{-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2}};
static void setMode(const Var *v) {
  sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(v->c5650 ? GU_PSM_5650 : GU_PSM_8888, drawBuf, BUF_W);
  sceGuDispBuffer(SCR_W, SCR_H, dispBuf, BUF_W);
  sceGuDepthBuffer((void *)(BUF_W * SCR_H * 8), BUF_W);
  sceGuFinish(); sceGuSync(0, 0);
}
static void frameBegin(const Var *v) {
  sceGuStart(GU_DIRECT, list);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuDepthRange(65535, 0); sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDepthFunc(GU_GEQUAL); sceGuEnable(GU_DEPTH_TEST); sceGuShadeModel(GU_SMOOTH); sceGuEnable(GU_CLIP_PLANES);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0); sceGuAlphaFunc(GU_GREATER, 0x40, 0xff);
  int ccw = ffOverride >= 0 ? ffOverride : (int)H->frontCcw;
  sceGuFrontFace(ccw ? GU_CCW : GU_CW);
  if (v->c5650) { sceGuSetDither(&dith); sceGuEnable(GU_DITHER); } else sceGuDisable(GU_DITHER);
  sceGuTexWrap(GU_REPEAT, GU_REPEAT); sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
  sceGuTexScale(128.f, 128.f); sceGuTexOffset(0.f, 0.f); sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0);
  sceGuEnable(GU_FOG); sceGuFog(115.f * .5f, 115.f, H->fog);
  sceGuClearColor(0xff000000 | H->fog); sceGuClearDepth(0);
  sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
  sceGumMatrixMode(GU_PROJECTION); sceGumLoadIdentity(); sceGumPerspective(62.f, 16.f / 9.f, 0.7f, 125.f);
  sceGumMatrixMode(GU_VIEW); sceGumLoadIdentity();
  ScePspFVector3 eye = {H->eye[0], H->eye[1], H->eye[2]}, at = {H->at[0], H->at[1], H->at[2]}, up = {0, 1, 0};
  sceGumLookAt(&eye, &at, &up);
  sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity(); sceGumUpdateMatrix();
}
static float ge[NFR], fr[NFR];
static void runFrame(int vi, float *geMs, float *frMs) {
  const Var *v = &VAR[vi];
  unsigned t0 = sceKernelGetSystemTimeLow();
  frameBegin(v);
  if (v->inl) emit(v); else sceGuCallList(pre[vi]);
  sceGuFinish();
  unsigned t1 = sceKernelGetSystemTimeLow();
  sceGuSync(0, 0);
  unsigned t2 = sceKernelGetSystemTimeLow();
  *geMs = (t2 - t1) / 1000.f; *frMs = (t2 - t0) / 1000.f;
}
static void swap(int vsync) {
  if (vsync) sceDisplayWaitVblankStart();
  void *n = sceGuSwapBuffers(); dispBuf = drawBuf; drawBuf = n;
}
static int cmpF(const void *a, const void *b) { float x = *(const float *)a, y = *(const float *)b; return x < y ? -1 : x > y; }
typedef struct { float med, p90, max, avg; } St;
static St stats(float *a) {
  float s[NFR]; memcpy(s, a, sizeof s); qsort(s, NFR, sizeof(float), cmpF);
  St r = {s[NFR / 2], s[NFR * 9 / 10], s[NFR - 1], 0}; for (int i = 0; i < NFR; i++) r.avg += s[i]; r.avg /= NFR; return r;
}

int main(int argc, char **argv) {
  SceUID th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0); if (th >= 0) sceKernelStartThread(th, 0, 0);
  strncpy(path, argc > 0 && argv[0] ? argv[0] : "ms0:/PSP/GAME/GEBENCH/EBOOT.PBP", sizeof path - 1);
  char fn[256]; sibling(fn, "cell.bin");
  SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f < 0) fail("cell.bin not found next to EBOOT.PBP");
  int sz = sceIoLseek32(f, 0, PSP_SEEK_END); sceIoLseek32(f, 0, PSP_SEEK_SET);
  D = memalign(64, sz); if (!D) fail("no memory");
  if (sceIoRead(f, D, sz) != sz) fail("read error"); sceIoClose(f);
  H = (Hdr *)D; if (memcmp(H->magic, "GEB1", 4) || H->nset != NSET) fail("cell.bin: wrong format");
  T = (TexRec *)(D + 128); P = (PieceRec *)(D + 128 + 48 * H->ntex);
  char b[64];
  if (readSmall("ff.txt", b, sizeof b) > 0) ffOverride = !strncmp(b, "ccw", 3) ? 1 : 0;

  // набор 2 в VRAM: вершины, потом индексы
  unsigned vsz = H->set[2][1], isz = H->set[2][3];
  vramSet = (unsigned char *)(0x44000000u | (unsigned)VRAM_DATA);
  int vramOk = VRAM_DATA + vsz + isz <= 0x200000;
  if (vramOk) { memcpy(vramSet, D + H->set[2][0], vsz); memcpy(vramSet + vsz, D + H->set[2][2], isz); }

  sceGuInit();
  sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, drawBuf, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, dispBuf, BUF_W);
  sceGuDepthBuffer((void *)(BUF_W * SCR_H * 8), BUF_W);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);

  // готовые списки команд на каждый вариант: время кадра = время GE, без построения списка процессором
  long idxN[NVAR]; long tris = 0;
  for (unsigned i = 0; i < H->npc; i++) tris += P[i].s[0].cnt / 3;
  for (int vi = 0; vi < NVAR; vi++) {
    pre[vi] = memalign(64, 256 * 1024); if (!pre[vi]) fail("no memory for lists");
    if (VAR[vi].vram && !vramOk) { idxN[vi] = -1; continue; }
    sceGuStart(GU_CALL, pre[vi]); emit(&VAR[vi]); sceGuFinish(); idxN[vi] = drawIdxCount;
  }
  sceKernelDcacheWritebackAll();

  // служебное: show.txt — рисовать один вариант (снимок окна в эмуляторе)
  if (readSmall("show.txt", b, sizeof b) > 0) {
    int vi = 0; for (int i = 0; i < NVAR; i++) if (!strncmp(b, VAR[i].name, strlen(VAR[i].name)) && (b[strlen(VAR[i].name)] < 'a')) vi = i;
    setMode(&VAR[vi]);
    for (;;) { float g, r; runFrame(vi, &g, &r); swap(1); }
  }

  int autoexit = readSmall("autoexit", b, sizeof b) >= 0;
  static St sg[NVAR], sf[NVAR];
  for (int vi = 0; vi < NVAR; vi++) {
    if (idxN[vi] < 0) continue;
    setMode(&VAR[vi]);
    for (int k = 0; k < WARM + NFR; k++) {
      float g, r; runFrame(vi, &g, &r); swap(0);
      if (k >= WARM) { ge[k - WARM] = g; fr[k - WARM] = r; }
    }
    sg[vi] = stats(ge); sf[vi] = stats(fr);
  }
  setMode(&VAR[0]);

  static char out[4096]; int n = 0;
  n += snprintf(out + n, sizeof out - n,
    "GEBENCH v1 (%s %s)  view 345 -81 heading 1, city only, near versions\n"
    "pieces %u, tris %ld, textures %u; %d frames per variant after %d warm-up, no vsync; 480x272\n"
    "ge = sceGuFinish->sceGuSync, frame = sceGuStart->sceGuSync (ms). Rows without * use a prebuilt call list.\n\n"
    "var  frame: med    p90    max   | ge: med    p90    max   | verts sent  Mtri/s  vs a   what\n",
    __DATE__, __TIME__, H->npc, tris, H->ntex, NFR, WARM);
  for (int vi = 0; vi < NVAR; vi++) {
    if (idxN[vi] < 0) { n += snprintf(out + n, sizeof out - n, "%-3s  (skipped: does not fit VRAM)\n", VAR[vi].name); continue; }
    n += snprintf(out + n, sizeof out - n, "%-3s  %6.2f %6.2f %6.2f | %6.2f %6.2f %6.2f | %9ld  %6.2f  %4.2fx  %s\n",
      VAR[vi].name, sf[vi].med, sf[vi].p90, sf[vi].max, sg[vi].med, sg[vi].p90, sg[vi].max, idxN[vi],
      tris / (sf[vi].med * 1000.f), sf[0].med / sf[vi].med, VAR[vi].desc);
  }
  n += snprintf(out + n, sizeof out - n, "\nfront face %s%s\n", (ffOverride >= 0 ? ffOverride : (int)H->frontCcw) ? "CCW" : "CW",
                ffOverride >= 0 ? " (ff.txt)" : "");
  sibling(fn, "gebench.txt");
  f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f >= 0) { sceIoWrite(f, out, n); sceIoClose(f); }
  if (autoexit) sceKernelExitGame();

  pspDebugScreenInit(); pspDebugScreenSetXY(0, 0);
  pspDebugScreenPrintf("GEBENCH  %ld tris, frame median ms (x faster than a)\n\n", tris);
  for (int vi = 0; vi < NVAR; vi++)
    if (idxN[vi] >= 0) pspDebugScreenPrintf(" %-3s %6.2f ms  %4.2fx  %s\n", VAR[vi].name, sf[vi].med, sf[0].med / sf[vi].med, VAR[vi].desc);
  pspDebugScreenPrintf("\nFull report: gebench.txt next to EBOOT.\nHOME to exit.");
  sceKernelSleepThreadCB();
  return 0;
}
