// №912: матрица оболочки контура машины — новая запись по диагонали против прежнего полного умножения: равенство чисел (знак нуля не в счёт) на случайных входах (Мак, только числа)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "../../viewer/hullmat912.h"
static float rnd(float a, float b) { return a + (b - a) * (float)(rand() & 0xffff) / 65535.f; }
int main(void) {
  srand(7); unsigned bad = 0, n = 2000000;
  for (unsigned i = 0; i < n; i++) {
    float yaw = rnd(0, 6.2831853f), pit = rnd(-.4f, .4f), k = rnd(.2f, 3.f), c = cosf(yaw), s = sinf(yaw), cp = cosf(pit), sp = sinf(pit);
    float m[16] = {c * k, 0, -s * k, 0,  s * sp * k, cp * k, c * sp * k, 0,  s * cp * k, -sp * k, c * cp * k, 0,  rnd(-900, 900), rnd(-90, 90), rnd(-900, 900), 1};
    float A[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
    for (int j = 0; j < 3; j++) { float sc = rnd(1.f, 1.5f); A[j * 5] = sc; A[12 + j] = rnd(-4.f, 4.f) * (1.f - sc); }
    float sc3[3], tr3[3]; for (int j = 0; j < 3; j++) { sc3[j] = A[j * 5]; tr3[j] = A[12 + j]; }
    float a[16], b[16]; hullMatFull(m, A, a); hullMatDiag(m, sc3, tr3, b);
#ifdef HULLMAT_BREAK
    b[13] += 1e-6f;   // красный контроль: ошибка в одном элементе
#endif
    int ne = 0; for (int q = 0; q < 16; q++) if (!(a[q] == b[q])) ne = 1;   // −0 и +0 равны: прежнее умножение складывало нули
    bad += ne;
  }
  printf("HULLMAT cases=%u mismatched=%u\n", n, bad); return bad ? 1 : 0;
}
