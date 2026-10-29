// RESET CAR выручает (миссионер Б2 28.09: m0 застряла в углу у x 126 z 220, RESET ставил туда же). Тот же car.c/col.c, что на PSP.
//   A) машина едет в стену и 5 с давит в неё газом; RESET CAR -> центр машины не ближе 5 м от места застревания и с нового
//      места едет (газ прямо, 3+ м за 5 с) — на 3–4 стенах уровня (большие ящики-не-кусты с ровной землёй перед ними)
//   B) обычная езда без застревания: RESET возвращает на надёжное место не дальше 60 м (не выбрасывает в начало уровня)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W; static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }
static void run(Car *c, float thr, float st, float secs) { for (int f = 0; f < (int)(secs * 60); f++) { CarInput in = {thr, 0, st}; carUpdate(c, &W, &in, 1 / 60.f); } }
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  int walls = 0, freed = 0;
  for (unsigned i = 0; i < W.nbox && walls < 4; i++) {   // стены: высокие ящики-не-кусты, рядом ровная земля
    const ColBox *B = &W.box[i]; float ex = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
    float ey = fabsf(B->ax[1]) * B->h[0] + fabsf(B->ay[1]) * B->h[1] + fabsf(B->az[1]) * B->h[2];
    float ez = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2];
    if (B->pad == 1.f || ex < 6.f || ez < 6.f || ey < 2.f) continue;
    float sx = B->c[0] + ex + 22.f, sz = B->c[2], g, g2;
    if (!colGround(&W, sx, sz, B->c[1] + 3.f, B->c[1] - ey - 3.f, &g, 0) || !colGround(&W, B->c[0] + ex + 2.f, sz, g + 1.f, g - 1.f, &g2, 0)) continue;
    int flat = 1; for (float x = sx; x > B->c[0] + ex + 2.f; x -= 2.f) { float gg; if (!colGround(&W, x, sz, g + 1.f, g - 1.f, &gg, 0) || fabsf(gg - g) > .4f) flat = 0; }
    if (!flat) continue;
    Car c; carInit(&c, NULL, &W, sx, g, sz, -1.5708f); run(&c, 0, 0, .3f);
    float x00 = c.x, z00 = c.z;
    run(&c, 1, 0, 3.f);                 // разгон к стене
    if (hypotf(c.x - x00, c.z - z00) < 10.f) continue;   // не разогналась (старт неудачный) — не этот случай
    run(&c, 1, 0, 5.f);                 // давит в стену
    float wx = c.x, wz = c.z; carResetNearby(&c, &W); run(&c, 0, 0, .3f);
    float away = hypotf(c.x - wx, c.z - wz), x0 = c.x, z0 = c.z;
    run(&c, 1, 0, 5.f);                 // газ прямо — уезжает?
    float drove = hypotf(c.x - x0, c.z - z0);
    int wheels = c.wheels; walls++; freed += away >= 5.f && drove >= 3.f && wheels >= 3;   // и после RESET на колёсах (≥ 3), как выход игрока из ловушки
    printf("  стена ящик %u у %.0f %.0f: застряла у %.1f %.1f, RESET -> в %.1f м, колёс %d, потом уехала на %.1f м\n", i, B->c[0], B->c[2], wx, wz, away, wheels, drove);
  }
  check("A: после RESET CAR машина не у места застревания, на колёсах и уезжает (3–4 стены: на данных L1 набора TEST28 подходящих ящиков 3)", walls >= 3 && freed == walls);
  { // B: обычная езда по спавну уровня и RESET недалеко
    float hd[14]; memcpy(hd, d + 12, sizeof hd); Car c; carInit(&c, NULL, &W, hd[6], hd[7], hd[8], hd[9]);
    run(&c, 1, 0, 4.f); float x1 = c.x, z1 = c.z; carResetNearby(&c, &W);
    float back = hypotf(c.x - x1, c.z - z1);
    printf("  езда от спавна 4 с, RESET -> в %.1f м от места\n", back);
    check("B: RESET при обычной езде — недалеко (до 60 м)", back <= 60.f);
  }
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails != 0;
}
