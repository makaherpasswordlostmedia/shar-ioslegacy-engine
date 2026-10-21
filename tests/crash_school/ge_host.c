// Гейт правки 103 (повтор 01.10 «спортивная площадка у школы»): 3D после города укладывается в бюджет списка GE.
// Настоящие viewer/skin.c и viewer/msnart.c (версия под проверкой — копии в каталоге сборки, tests/crash_school/ge_host.sh) с
// заглушками pspsdk (tests/crash_school/stub): список GE — счётчик слов, как пишет pspgu. Данные — диск Роба: модели
// build/chars/*.chr (персонажи — skinDraw: фоновые, миссий, пешеходы) и build/msnart.shr (пропы уличной гонки l1_sr2p — 505 мешей).
//   ge_host BUILD_DIR ARRAY_KB      ARRAY_KB — длина массива list в main.c этой версии (256 до правки, 320 после: бюджет + GE_TAIL)
// Сцены (как main.c: город остановлен на GE_HARD = 90 % бюджета 256 КБ, дальше персонажи и рисунки миссий, потом интерфейс 24 КБ):
//   quiet — список на 40 %: всё рисуется (новая проверка не прячет лишнего: байты те же, что у старого кода);
//   full  — список у черты 90 %: за черту не должно уйти ничего, кроме служебных команд (<= 256 Б), конец кадра — внутри массива.
// Выход 0 — зелёный; старый код (без skinGeRoom / msnartGeRoom) обязан упасть.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "pspkernel.h"
#include "pspgu.h"
#include "skin.h"
#include "msnart.h"

#define BUDGET (256u << 10)
#define HARD (BUDGET / 100u * 90u)   // main.c geRoomHard: geCap / 100 * GE_HARD
#define UI_BYTES (24u << 10)         // интерфейс кадра (пузырь, радар, счётчики) — рисуется без проверки

// ---------------------------------------------------------------- список GE: счётчик
static unsigned geUsed;
#define W(n) (geUsed += 4u * (unsigned)(n))
void sceGuEnable(int s) { (void)s; W(1); }
void sceGuDisable(int s) { (void)s; W(1); }
void sceGuDepthOffset(unsigned o) { (void)o; W(1); }
float camNearNow = 0.5f;   // camnear.h: ближняя плоскость камеры (в гейте постоянная)
int camNearOld = 0;
void geDeferFree(void *p) { free(p); }   // msnart.c: отложенное освобождение (в гейте сразу)
int uiMarkerSmall(int t, const float *c, const float *h) { (void)t; (void)c; (void)h; return 0; }
void sceGuDepthMask(int m) { (void)m; W(1); }
void sceGuSetMatrix(int t, const ScePspFMatrix4 *m) { (void)m; W(t == GU_PROJECTION ? 17 : 13); }
void sceGuBoneMatrix(unsigned i, const ScePspFMatrix4 *m) { (void)i; (void)m; W(13); }
void sceGuTexFunc(int a, int b) { (void)a; (void)b; W(1); }
void sceGuTexFilter(int a, int b) { (void)a; (void)b; W(1); }
void sceGuTexScale(float u, float v) { (void)u; (void)v; W(2); }
void sceGuTexOffset(float u, float v) { (void)u; (void)v; W(2); }
void sceGuTexWrap(int u, int v) { (void)u; (void)v; W(1); }
void sceGuTexMode(int a, int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; W(2); }
void sceGuTexImage(int a, int w, int h, int tbw, const void *p) { (void)a; (void)w; (void)h; (void)tbw; (void)p; W(4); }
void sceGuClutMode(unsigned a, unsigned b, unsigned c, unsigned d) { (void)a; (void)b; (void)c; (void)d; W(1); }
void sceGuClutLoad(int n, const void *p) { (void)n; (void)p; W(3); }
void sceGuLight(int l, int t, int c, const ScePspFVector3 *p) { (void)l; (void)t; (void)c; (void)p; W(5); }
void sceGuLightColor(int l, int c, unsigned col) { (void)l; (void)c; (void)col; W(1); }
void sceGuAmbient(unsigned c) { (void)c; W(2); }
void sceGuAmbientColor(unsigned c) { (void)c; W(2); }
void sceGuModelColor(unsigned a, unsigned b, unsigned c, unsigned d) { (void)a; (void)b; (void)c; (void)d; W(4); }
void sceGuAlphaFunc(int a, int b, int c) { (void)a; (void)b; (void)c; W(1); }
void sceGuBlendFunc(int op, int s, int d, unsigned a, unsigned b) { (void)op; (void)s; (void)d; (void)a; (void)b; W(3); }
void sceGuDrawArray(int prim, int vt, int n, const void *i, const void *v) { (void)prim; (void)vt; (void)n; (void)v; W(i ? 5 : 4); }
void *sceGuGetMemory(int size) {   // pspgu: прыжок через блок (2 слова) + сам блок
  static unsigned char mem[1 << 16]; W(2); geUsed += ((unsigned)size + 3u) & ~3u;
  return mem;
}
int sceGuCheckList(void) { return (int)geUsed; }

// ---------------------------------------------------------------- файлы: stdio Мака
static FILE *fds[16];
SceUID sceIoOpen(const char *f, int flags, int mode) {
  (void)flags; (void)mode;
  for (int i = 1; i < 16; i++) if (!fds[i]) { fds[i] = fopen(f, "rb"); return fds[i] ? i : -1; }
  return -1;
}
int sceIoRead(SceUID fd, void *d, SceSize n) { return fd > 0 && fd < 16 && fds[fd] ? (int)fread(d, 1, n, fds[fd]) : -1; }
int sceIoClose(SceUID fd) { if (fd > 0 && fd < 16 && fds[fd]) { fclose(fds[fd]); fds[fd] = 0; } return 0; }
int sceIoLseek32(SceUID fd, int off, int wh) {
  if (fd <= 0 || fd >= 16 || !fds[fd]) return -1;
  fseek(fds[fd], off, wh == PSP_SEEK_END ? SEEK_END : wh == PSP_SEEK_CUR ? SEEK_CUR : SEEK_SET);
  return (int)ftell(fds[fd]);
}
static SceInt64 asyncRes[16];
int sceIoReadAsync(SceUID fd, void *d, SceSize n) { int r = sceIoRead(fd, d, n); if (r < 0) return r; asyncRes[fd] = r; return 0; }
int sceIoPollAsync(SceUID fd, SceInt64 *res) { *res = asyncRes[fd]; return 0; }
int sceIoWaitAsync(SceUID fd, SceInt64 *res) { *res = asyncRes[fd]; return 0; }
void sceKernelDcacheWritebackRange(const void *p, unsigned n) { (void)p; (void)n; }
unsigned sceKernelGetSystemTimeLow(void) { return 0; }
void *memalign(size_t a, size_t n) { void *p = 0; return posix_memalign(&p, a < sizeof(void *) ? sizeof(void *) : a, n ? n : 1) ? 0 : p; }
void uiSetObjIconImage(const void *pix, int tw, int th, int w, int h) { (void)pix; (void)tw; (void)th; (void)w; (void)h; }
void bbOp(const char *op, const char *arg, int sync) { (void)op; (void)arg; (void)sync; }   // самописец main.c — здесь не нужен

// крючки бюджета: у старого кода их нет — слабые определения (новый skin.c / msnart.c дают свои, сильные)
__attribute__((weak)) int (*skinGeRoom)(unsigned bytes) = 0;
__attribute__((weak)) int (*msnartGeRoom)(unsigned bytes) = 0;
static unsigned skips;
static int roomHard(unsigned bytes) { if (geUsed + bytes <= HARD) return 1; skips++; return 0; }   // как main.c geRoomHard

// ---------------------------------------------------------------- сцена
static const char *NPC[] = {"willie", "marge", "apu", "lisa", "moleman", "grandpa", "krusty", "lenny", "moe", "barney"};
#define NNPC (int)(sizeof NPC / sizeof *NPC)
static SkinModel *mdl[NNPC]; static SkinPlayer ply[NNPC];
static unsigned scene(const char *name, unsigned start, unsigned arrayBytes, int *bad) {
  geUsed = start; skips = 0;
  ScePspFMatrix4 w; skinPlace(&w, 0.f, 0.f, 0.f, 0.f);
  for (int i = 0; i < NNPC; i++) if (mdl[i]) skinDraw(&ply[i], &w);   // 4 персонажа миссий/фоновых + 6 пешеходов
  unsigned afterNpc = geUsed;
  msnartDraw("l1_sr2p", NULL, 0.f, 0.f, 0.f, 0.f);                    // пропы гонки: все меши (как в 70 м от трассы)
  unsigned after3d = geUsed, end = geUsed + UI_BYTES;                  // + интерфейс
  unsigned past = after3d > HARD ? after3d - (start > HARD ? start : HARD) : 0;
  printf("%-5s старт %6.1f КБ (%2u%% бюджета): персонажи +%5.1f КБ, пропы гонки +%5.1f КБ -> 3D %6.1f КБ, за чертой 90%% %5.1f КБ, "
         "пропущено %u; конец кадра с интерфейсом %6.1f КБ из массива %u КБ\n", name, start / 1024.f, start * 100u / BUDGET,
         (afterNpc - start) / 1024.f, (after3d - afterNpc) / 1024.f, after3d / 1024.f, past / 1024.f, skips, end / 1024.f, arrayBytes >> 10);
  if (start >= HARD - 2048 && past > 256) { printf("FAIL %s: 3D дописал %.1f КБ за черту GE_HARD (город там уже остановлен)\n", name, past / 1024.f); (*bad)++; }
  if (end > arrayBytes) { printf("FAIL %s: конец кадра %.1f КБ за концом массива list (%u КБ) — sceGu* пишут в чужую память, GE PSP исполняет мусор\n",
                                 name, end / 1024.f, arrayBytes >> 10); (*bad)++; }
  return after3d - start;
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "ge_host BUILD_DIR ARRAY_KB\n"); return 2; }
  const char *bd = argv[1]; unsigned arrayBytes = (unsigned)atoi(argv[2]) << 10;
  char fn[512]; int n = 0;
  for (int i = 0; i < NNPC; i++) {
    snprintf(fn, sizeof fn, "%s/chars/%s.chr", bd, NPC[i]);
    if ((mdl[i] = skinLoad(fn))) { skinInit(&ply[i], mdl[i]); n++; }
  }
  snprintf(fn, sizeof fn, "%s/", bd);
  if (n < 6 || msnartInit(fn)) { printf("FAIL нет данных: моделей %d из %d, msnart.shr %s\n", n, NNPC, fn); return 2; }
  msnartLoad("art/l1_sr2p.p3d", 0); for (int k = 0; k < 4; k++) msnartPump();
  skinGeRoom = roomHard; msnartGeRoom = roomHard;   // как main.c (у старого кода крючков нет — никто их не спросит)
  int bad = 0;
  unsigned q = scene("quiet", BUDGET * 40u / 100u, arrayBytes, &bad);
  if (q < 60000u) { printf("FAIL quiet: пропы гонки не нарисованы (%u Б) — данные или сцена\n", q); bad++; }
  if (skips) { printf("FAIL quiet: проверка спрятала %u рисований в спокойной сцене\n", skips); bad++; }
  scene("full", HARD - 1024u, arrayBytes, &bad);
  printf("RESULT %s\n", bad ? "FAIL" : "PASS");
  return bad ? 1 : 0;
}
