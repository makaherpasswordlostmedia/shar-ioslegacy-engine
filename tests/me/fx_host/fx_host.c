// Правка 313 (частицы и свечение на Media Engine): сверка на Маке — прежний viewer/fx.c (до правки) и новый (viewer/fxdsp.h — та же
// функция, что считает ME) собираются этим же стендом и проходят один и тот же сценарий: системы частиц пакета уровня (дым и огонь
// машины, взрыв с биллбордами, обломки, искры, пыль), блёстки и спрайты (свечение), камера то далеко, то у самых частиц (бюджет
// ближней заливки, гашение у объектива, отсечение за камерой), шаги кадра 1/60…0.2 с. Печать — на каждый кадр: число частиц, заливка
// (биты float), пропуски бюджета, и на каждую команду рисования — смешивание, отпечаток текстуры, число индексов и CRC вершин.
// Вывод прежнего и нового обязан совпасть побайтно (tests/me/fx_test.py; там же красный контроль).
//   cc -O2 -ffp-contract=off -I tests/me/fx_host -I viewer -DFXD_EXPF=expf -o fx_new tests/me/fx_host/fx_host.c viewer/fx.c -lm
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "pspkernel.h"
#include "pspgu.h"
#include "pspiofilemgr.h"
#include "fx.h"

// ---------- заглушки PSP ----------
static FILE *fdt[16];
SceUID sceIoOpen(const char *p, int f, int m) { (void)f; (void)m; FILE *x = fopen(p, "rb"); if (!x) return -1;
  for (int i = 0; i < 16; i++) if (!fdt[i]) { fdt[i] = x; return i + 1; } fclose(x); return -1; }
static FILE *fdOf(SceUID fd) { return fd >= 1 && fd <= 16 ? fdt[fd - 1] : 0; }
int sceIoLseek32(SceUID fd, int off, int wh) { FILE *x = fdOf(fd); if (!x || fseek(x, off, wh == PSP_SEEK_END ? SEEK_END : SEEK_SET)) return -1; return (int)ftell(x); }
int sceIoRead(SceUID fd, void *d, unsigned n) { FILE *x = fdOf(fd); return x ? (int)fread(d, 1, n, x) : -1; }
int sceIoClose(SceUID fd) { FILE *x = fdOf(fd); if (x) { fclose(x); fdt[fd - 1] = 0; } return 0; }

static unsigned crc32(const void *p, unsigned n, unsigned c) {
  const unsigned char *b = p; c = ~c;
  for (unsigned i = 0; i < n; i++) { c ^= b[i]; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & -(c & 1)); }
  return ~c;
}
static unsigned char arena[1 << 20] __attribute__((aligned(64))); static unsigned arenaN;
static int bOp, bSrc, bDst; static unsigned bA, bB; static unsigned texId; static int nDraw; static FILE *out;
void sceGuDisable(int s) { (void)s; } void sceGuEnable(int s) { (void)s; }
void sceGuTexFunc(int a, int b) { (void)a; (void)b; } void sceGuTexFilter(int a, int b) { (void)a; (void)b; } void sceGuTexWrap(int a, int b) { (void)a; (void)b; }
void sceGuTexScale(float u, float v) { (void)u; (void)v; } void sceGuTexOffset(float u, float v) { (void)u; (void)v; } void sceGuDepthMask(int m) { (void)m; }
void sceGuSetMatrix(int t, const ScePspFMatrix4 *m) { (void)t; (void)m; }
void sceGuAlphaFunc(int func, int value, int mask) { (void)func; (void)value; (void)mask; }   // №731: заглушка, у стенда вырезка по альфе не считается
void sceGuBlendFunc(int op, int src, int dst, unsigned a, unsigned b) { bOp = op; bSrc = src; bDst = dst; bA = a; bB = b; }
void sceGuClutMode(unsigned c, unsigned s, unsigned m, unsigned a) { (void)c; (void)s; (void)m; (void)a; }
void sceGuClutLoad(int n, const void *p) { (void)n; (void)p; }
void sceGuTexMode(int t, int m, int a, int s) { (void)t; (void)m; (void)a; (void)s; }
void sceGuTexImage(int mip, int w, int h, int tbw, const void *p) { (void)mip; texId = crc32(p, 64, (unsigned)(w * 65536 + h * 256 + tbw)); }
void sceGuTexFlush(void) {}
void *sceGuGetMemory(int size) { size = (size + 63) & ~63; if (arenaN + size > sizeof arena) arenaN = 0; void *p = arena + arenaN; arenaN += size; return p; }
void sceGuDrawArray(int prim, int vtype, int count, const void *idx, const void *v) {
  (void)prim; (void)idx; nDraw++;
  unsigned nv = (unsigned)count / 6 * 4;   // четвёрки: 6 индексов на 4 вершины (qidx)
  fprintf(out, "D b=%d,%d,%d,%08x,%08x t=%08x vt=%x n=%d h=%08x\n", bOp, bSrc, bDst, bA, bB, texId, vtype, count, crc32(v, nv * 24, 0));
}

// ---------- сценарий ----------
static unsigned rs = 12345u;
static float rnd(void) { rs = rs * 1103515245u + 12345u; return (rs >> 8) * (1.f / 16777216.f); }
static unsigned fbits(float f) { unsigned u; memcpy(&u, &f, 4); return u; }

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "fx_host fx.shr out.txt [frames]\n"); return 2; }
  out = fopen(argv[2], "w"); if (!out) return 2;
  int frames = argc > 3 ? atoi(argv[3]) : 900;
  if (!fxLoad(argv[1])) { fprintf(stderr, "no fx.shr %s\n", argv[1]); return 3; }
  fxInit(1);
  int sysSmoke = fxFindInst(14), sysFire = fxFindInst(19), sysWrench = fxFind("wrench_collect2Shape"), sysCard = fxFind("card_collect_psShape");
  int tGlow = fxTexFind("glow2.bmp"), tScr = fxTexFind("scratch2.bmp"), tSkid = fxTexFind("skid.bmp");
  fprintf(out, "SYS smoke=%d fire=%d wrench=%d card=%d glow=%d scratch=%d skid=%d\n", sysSmoke, sysFire, sysWrench, sysCard, tGlow, tScr, tSkid);
  float car[3] = {220.f, 3.5f, 172.f}, dir[3] = {0, 1, 0};
  int hSmoke = 0, hFire = 0; unsigned sumN = 0, maxN = 0, sumDraw = 0;
  for (int f = 0; f < frames; f++) {
    float t = f / 30.f, dt = (f % 97 == 50) ? .2f : (f % 3 == 0 ? 1.f / 60.f : 1.f / 30.f);
    car[0] = 220.f + 8.f * sinf(t * .3f); car[2] = 172.f + 8.f * cosf(t * .3f);
    if (f == 10 && sysSmoke >= 0) hSmoke = fxStartSystem(sysSmoke, car, NULL);
    if (hSmoke) { fxMove(hSmoke, car, NULL); fxSetEmitRate(hSmoke, 0, f < 300 ? .4f : 1.f); fxSetEmitRate(hSmoke, 1, f > 200 ? 1.f : 0.f); fxSetEmitRate(hSmoke, 2, f > 250 ? 1.f : 0.f); }
    if (f == 120 && sysFire >= 0) { float p[3] = {car[0] + 3, car[1], car[2]}; hFire = fxStartSystem(sysFire, p, dir); }
    if (f == 700 && hFire) fxStop(hFire);
    if (f == 160 || f == 520) { float p[3] = {car[0], car[1], car[2] + 2}; fxBurstBreakable(24, p, NULL); }   // взрыв: биллборды
    if (f % 140 == 70) { float p[3] = {car[0] - 4, car[1], car[2]}; fxBurstBreakable(3 + (f / 140) % 18, p, NULL); }
    if (f == 90 && sysWrench >= 0) { float p[3] = {car[0], car[1] + .5f, car[2] - 3}; fxBurst(sysWrench, p, NULL); }
    if (f == 95 && sysCard >= 0) { float p[3] = {car[0] + 1, car[1] + .5f, car[2] - 3}; fxBurst(sysCard, p, NULL); }
    if (f % 7 == 0) for (int k = 0; k < 4; k++) fxSpawn(k % 6, car[0] + rnd() - .5f, car[1] + .5f, car[2] + rnd() - .5f, (rnd() - .5f) * 8, rnd() * 5, (rnd() - .5f) * 8);
    if (f % 23 == 0) fxHomerDust(f % 3, car[0], car[1], car[2], 4.f + rnd() * 14.f);
    for (int k = 0; k < 12; k++) fxSparkle(car[0] + k * 1.5f - 9, car[1] + 1.f, car[2] + 6.f, 1.1f, t * .5f + k * .37f);   // блёстки монет
    fxSparkleC(car[0], car[1] + 2, car[2] - 1, 1.3f, t, 0xff80ffc0u);
    if (tSkid >= 0) fxSprite(tSkid, car[0], car[1] + .02f, car[2] + 1, 1.f, 3.f, t, 0xc0ffffffu, f % 3, 1);   // лежит на земле
    if (tGlow >= 0) fxSprite(tGlow, car[0] + 2, car[1] + 1, car[2], 2.f, 2.f, t * 2, 0xffffffffu, 2, 0);    // вычитание
    // камера: облёт, то далеко (25 м), то вплотную (1.5–6 м: бюджет ближней заливки и гашение), временами спиной к частицам
    float r = 14.f + 12.f * sinf(t * .21f); if ((f / 60) % 5 == 3) r = 1.5f + 4.5f * (f % 60) / 60.f;
    float a = t * .4f, ex = car[0] + r * cosf(a), ez = car[2] + r * sinf(a), ey = car[1] + 1.6f + (r > 10 ? 3 : 0);
    float fx = car[0] - ex, fy = car[1] + .5f - ey, fz = car[2] - ez; if ((f / 45) % 7 == 5) { fx = -fx; fz = -fz; }
    float l = sqrtf(fx * fx + fy * fy + fz * fz); fx /= l; fy /= l; fz /= l;
    fxUpdate(dt);
    nDraw = 0; arenaN = 0;
    fxDraw(ex, ey, ez, fx, fy, fz);
    int n = fxCount(); sumN += (unsigned)n; if ((unsigned)n > maxN) maxN = (unsigned)n; sumDraw += (unsigned)nDraw;
    fprintf(out, "F %d n=%d fill=%08x skip=%d draws=%d\n", f, n, fbits(fxFill), fxSkipped, nDraw);
  }
  fprintf(out, "END frames=%d avg_n=%.1f max_n=%u draws=%u\n", frames, sumN / (float)frames, maxN, sumDraw);
  fclose(out);
  printf("frames=%d avg_n=%.1f max_n=%u draws=%u\n", frames, sumN / (float)frames, maxN, sumDraw);
  return 0;
}
