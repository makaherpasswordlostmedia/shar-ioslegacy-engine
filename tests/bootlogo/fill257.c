// Гейт правки Роба 257 (раскладка): «как спонсорские, аккуратно снизу логотипа». viewer/bootmarks.h, поток BMK2 на наборе
// правки 257 (ширины и высоты знаков — как в build/bootmarks.bin 03.10): блок начинается в 12 px под знаком GONE, ряды не шире
// знака GONE и стоят по центру (поля слева и справа равны ±1 px), знаки не налезают, El Barto и PSP — в последнем ряду.
// Красный: -DBMK_257_OLD (прежние слоты правки 254: ряды разнесены до низа экрана, PSP не в последнем ряду рядом с El Barto) -> FAIL
#include <stdio.h>
#include <stdlib.h>
#include "bootseq.h"
int main(void) {
  static const int W[8] = {50, 28, 58, 62, 110, 60, 57, 91}, Hh[8] = {24, 24, 24, 23, 11, 24, 24, 16};   // simpsons … psp
  bmkV = 2; bmkSW = 112; bmkSH = 24; bmkSc = 1; bmkN = 8; int bad = 0, rowW = BOOTANIM_PW * BOOTANIM_SCALE;
#ifndef BMK_257_OLD
  bmkFlowLayout(W, Hh, 8); bmkFlow = 1;
#else
  bmkSW = 72;
#endif
  int top = BUI_LOGO_Y + BOOTANIM_PH * BOOTANIM_SCALE + 12, y0 = 1 << 30;
  for (int k = 0; k < 8; k++) if (bmkSlotY(k) < y0) y0 = bmkSlotY(k);
  if (y0 < top || y0 > top + 2) { printf("FAIL: блок начинается на y=%d, ждали %d (12 px под GONE)\n", y0, top); bad++; }
  for (int k = 0; k < 8; k++) {   // ряд: знаки с одинаковой серединой по высоте
    int cy = bmkSlotY(k) + (bmkFlow ? Hh[k] : bmkSH) / 2, l = 1 << 30, r = -1;
    for (int j = 0; j < 8; j++) if (abs(bmkSlotY(j) + (bmkFlow ? Hh[j] : bmkSH) / 2 - cy) <= 2) {   // один ряд: середины по высоте ±2
      int x = bmkSlotX(j), w = bmkFlow ? W[j] : bmkSW; if (x < l) l = x; if (x + w > r) r = x + w; }
    int ml = l - BUI_LOGO_X, mr = BUI_LOGO_X + rowW - r;
    if (ml < 0 || mr < 0 || (ml - mr > 1 || mr - ml > 1)) { printf("FAIL: ряд знака %d не по центру (поля %d / %d)\n", k, ml, mr); bad++; break; }
  }
  for (int k = 0; k < 8; k++) for (int j = 0; j < k; j++) {
    int ax = bmkSlotX(k), ay = bmkSlotY(k), bx = bmkSlotX(j), by = bmkSlotY(j), aw = bmkFlow ? W[k] : bmkSW, ah = bmkFlow ? Hh[k] : bmkSH,
        bw = bmkFlow ? W[j] : bmkSW, bh = bmkFlow ? Hh[j] : bmkSH;
    if (ax < bx + bw && bx < ax + aw && ay < by + bh && by < ay + ah) { printf("FAIL: знаки %d и %d налезают\n", j, k); bad++; }
  }
  {   // компактно (спонсорский блок): между низом одного знака и верхом следующего ряда не больше BMK_FLOW_GY + 2 px
    int ys[8], ye[8]; for (int k = 0; k < 8; k++) { ys[k] = bmkSlotY(k); ye[k] = ys[k] + (bmkFlow ? Hh[k] : bmkSH); }
    for (int k = 0; k < 8; k++) {
      int nextTop = 1 << 30; for (int j = 0; j < 8; j++) if (ys[j] >= ye[k] && ys[j] < nextTop) nextTop = ys[j];
      if (nextTop != 1 << 30 && nextTop - ye[k] > 8 + 2 + 13) { printf("FAIL: разрыв %d px под знаком %d — блок не компактный\n", nextTop - ye[k], k); bad++; break; }
    }
  }
  int last = bmkSlotY(7) + (bmkFlow ? Hh[7] : bmkSH) / 2, prev = bmkSlotY(6) + (bmkFlow ? Hh[6] : bmkSH) / 2;
  if (abs(last - prev) > 2) { printf("FAIL: El Barto и PSP не в одном ряду\n"); bad++; }
  for (int k = 0; k < 6; k++) if (bmkSlotY(k) + (bmkFlow ? Hh[k] : bmkSH) / 2 >= last - 2) { printf("FAIL: знак %d ниже ряда El Barto/PSP\n", k); bad++; break; }
  printf("рядов %d, блок с y=%d (под GONE %d)\nRESULT: %s\n", bmkFlow ? bmkFRows : 0, y0, top, bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
