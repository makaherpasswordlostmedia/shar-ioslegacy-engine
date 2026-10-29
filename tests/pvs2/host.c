// Хост-проверка pvs2.h (PVS по курсу): синтетический блок — поиск клетки, сектора и гистерезис, границы; настоящий level.shr с PV2S (если дан) — разбор тем же кодом,
// списки отсортированы и укладываются в число кусков уровня. Красный контроль: -DPVS_SECTOR_OLD не нужен, контроль — испорченный блок должен отвергаться.
//   cc -std=c99 -O2 -I viewer tests/pvs2/host.c -lm -o build/pvs2_host && build/pvs2_host [level.shr ...]
#include <stdio.h>
#include <stdlib.h>
#include "pvs2.h"
static int bad, n;
#define CHECK(c, msg) do { n++; if (!(c)) { bad++; printf("FAIL: %s\n", msg); } } while (0)
int main(int argc, char **argv) {
  // синтетика: 2 горячие клетки (7 и 42), по 8 секторов
  unsigned blk[8 + 2 + 2 * 8 * 2 + 12] = {0x53325650u /* 'PV2S' */, 2, 8, 12, 0xABCD1234u, 0, 0, 0, 7, 42}; unsigned short *pool; memcpy(&blk[0], "PV2S", 4);
  unsigned *sec = &blk[10]; for (int h = 0; h < 2; h++) for (int s = 0; s < 8; s++) { sec[2 * (h * 8 + s)] = (unsigned)((h * 8 + s) % 6); sec[2 * (h * 8 + s) + 1] = 2; }
  pool = (unsigned short *)(sec + 32); for (int i = 0; i < 12; i++) pool[i] = (unsigned short)(100 + i);
  Pvs2 p; CHECK(pvs2Init(&p, blk, sizeof blk, 0xABCD1234u), "синтетический блок принят"); CHECK(!pvs2Init(&p, blk, sizeof blk, 0xABCD1235u), "чужая сигнатура — отвергается"); pvs2Init(&p, blk, sizeof blk, 0xABCD1234u);
  CHECK(pvs2Find(&p, 7) == 0 && pvs2Find(&p, 42) == 1 && pvs2Find(&p, 8) == -1 && pvs2Find(&p, 0) == -1 && pvs2Find(&p, 1000) == -1, "поиск горячей клетки");
  const unsigned short *l; int m = pvs2List(&p, 1, 3, &l); CHECK(m == 2 && l == pool + (11 % 6), "список (клетка 42, сектор 3)");
  CHECK(pvs2List(&p, 2, 0, &l) == -1 && pvs2List(&p, 0, 8, &l) == -1 && pvs2List(&p, -1, 0, &l) == -1, "границы списка");
  const float st = 6.2831853f / 8.f;
  CHECK(pvs2Sector(0.f, -1) == 0 && pvs2Sector(st, -1) == 1 && pvs2Sector(-st, -1) == 7 && pvs2Sector(3.14159f, -1) == 4 && pvs2Sector(-3.14159f, -1) == 4, "сектор по курсу без истории");
  CHECK(pvs2Sector(st * .6f, 0) == 0 && pvs2Sector(st * 1.0f, 0) == 1, "гистерезис: 27° остаётся, 45° от центра 0 уходит в 1");
  CHECK(pvs2Sector(0.5236f - .01f, 0) == 0 && pvs2Sector(0.5236f + .02f, 0) == 1, "порог гистерезиса ±30°");
  CHECK(pvs2Sector(6.2831853f - .3f, 0) == 0 && pvs2Sector(-.3f, 0) == 0, "переход через ±π и 2π: сектор 0 держится на ±17°");
  int flips = 0, cur = -1; float prev = 0; for (int i = 0; i < 20000; i++) { float yaw = .07f * sinf(i * .01f) + 0.3927f + .05f * sinf(i * .7f); int s = pvs2Sector(yaw, cur); if (cur >= 0 && s != cur) flips++; cur = s; prev = yaw; } (void)prev;
  CHECK(flips == 0, "дрожание курса ±7° вокруг границы секторов 0/1 (22,5°) не переключает сектор");
  unsigned bad1[8 + 2 + 32 + 12]; memcpy(bad1, blk, sizeof bad1); bad1[8] = 42; bad1[9] = 7; CHECK(!pvs2Init(&p, bad1, sizeof bad1, 0xABCD1234u), "клетки не по возрастанию — блок отвергается");
  memcpy(bad1, blk, sizeof bad1); bad1[10] = 11; bad1[11] = 5; CHECK(!pvs2Init(&p, bad1, sizeof bad1, 0xABCD1234u), "диапазон списка вне пула — отвергается");
  CHECK(!pvs2Init(&p, blk, 40, 0xABCD1234u), "короткий блок — отвергается");
  for (int a = 1; a < argc; a++) {   // настоящий уровень
    FILE *f = fopen(argv[a], "rb"); if (!f) { printf("нет файла %s\n", argv[a]); bad++; continue; } fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *d = malloc(len); if (fread(d, 1, len, f) != (size_t)len) return 2; fclose(f);
    unsigned npc = *(unsigned *)(d + 8), pvsOff = *(unsigned *)(d + 88); unsigned *pu = (unsigned *)(d + pvsOff + 16); unsigned sz = pu[0] * pu[1] * 8 + pu[2] * 2; unsigned o2 = (pvsOff + 32 + sz + 15u) & ~15u;
    Pvs2 q; unsigned tableOff = *(unsigned *)(d + 76); int ok = o2 + 32 <= (unsigned)len && pvs2Init(&q, d + o2, (unsigned)len - o2, pvs2Sig(d + tableOff, npc)); CHECK(ok, "PV2S в файле разобран");
    if (ok) {
      unsigned maxp = 0, tot = 0, unsorted = 0, over = 0; for (unsigned h = 0; h < q.nhot; h++) for (int s = 0; s < 8; s++) { const unsigned short *ll; int mm = pvs2List(&q, (int)h, s, &ll); tot += (unsigned)mm;
          for (int i = 0; i < mm; i++) { if (ll[i] >= npc) over++; if (i && ll[i - 1] >= ll[i]) unsorted++; if (ll[i] > maxp) maxp = ll[i]; } }
      CHECK(over == 0 && unsorted == 0, "списки сортированы, номера кусков меньше числа кусков уровня");
      printf("%s: горячих клеток %u, записей %u (%.0f КБ), ключ в PVS1: %s\n", argv[a], q.nhot, tot, (32 + 4 * q.nhot + 64 * q.nhot + 2 * q.npool) / 1024.0, "ok");
    }
    free(d);
  }
  printf("%d проверок, ошибок %d\n%s\n", n, bad, bad ? "FAIL" : "OK"); return bad ? 1 : 0;
}
