// Анимация логотипа GONE Makers на заставке (пункт Л, Роб 28.09): знак 1:1 по пикселям bootlogo.h (115×39 px).
// Появление по ровной сетке клеток 4×4 пикселя знака (29×10 клеток): символ рисуется в поле 3×3 со сдвигом (1,1),
// строка 0 и столбец 0 клетки — зазор, поэтому символы соседних клеток и уже собранный знак НИКОГДА не касаются
// (правка Роба 28.09 вечер: «черточки классно, квадратики слишком толстые и сливаются с логотипом — меньше, тоньше»).
// Стадии клетки: / → | → \ → ■ (точка 1 px — было 2×2, «в строке толстые») → точный рисунок знака. Диагональная волна по
// x + 2y, цвет от блика к покою по каждому пикселю (не клеткой — иначе светлые квадраты 4×4); второй проход — волна чёрточек \ | / по готовому знаку. Масштаб всё время 1:1.
// Чистый C без PSP: общий для viewer/bootscreen.h и проверки на Маке (tests/bootlogo); превью — tools/bootscreen_preview.
#ifndef BOOTANIM_H
#define BOOTANIM_H
#include "bootlogo.h"

#define BOOTANIM_CELL 4        // клетка сетки, пикселей знака
#ifndef BOOTANIM_SCALE
#define BOOTANIM_SCALE 2       // правка Роба 189 (01.10 23:0x): «больше GONE Makers сделай» — знак ×2 (232×80), самый крупный на экране (169); было 1:1 (148)
#endif
#ifndef BOOTANIM_DOT_W
#define BOOTANIM_DOT_W 2       // правка 189: ×2 — пиксель знака целым квадратом 2×2 (в правке 101 было 2×1, строки развёртки)
#endif
#ifndef BOOTANIM_DOT_H
#define BOOTANIM_DOT_H 2
#endif
#define BOOTANIM_STAGE 4.f     // пикселей хода фронта на одну стадию
#define BOOTANIM_SPEED 2.f     // пикселей хода фронта за кадр (16 мс)
#define BOOTANIM_WIDTH 26.f    // ширина блика за фронтом
#define BOOTANIM_REST 0xFFC8C8C8u    // правка Роба 101: системные цвета — покой светло-серый (#C8C8C8), ABGR (было #80725A)
#define BOOTANIM_GLINT 0xFFFFFFFFu   // гребень волны: белый (правка 101; было #F2E6C0)
#define BOOTANIM_BW ((BOOTLOGO_W + BOOTANIM_CELL - 1) / BOOTANIM_CELL)   // 29 клеток по горизонтали
#define BOOTANIM_BH ((BOOTLOGO_H + BOOTANIM_CELL - 1) / BOOTANIM_CELL)   // 10 по вертикали
#define BOOTANIM_PW (BOOTANIM_BW * BOOTANIM_CELL)                        // 116 × 40: занятое знаком место на сетке
#define BOOTANIM_PH (BOOTANIM_BH * BOOTANIM_CELL)
#define BOOTANIM_NSYM 4        // символов до рисунка
// символы в поле 3×3, бит r*3+c (r — строка, c — столбец поля): / | \ по 3 px толщиной 1 px, ■ — точка 1 px в центре
#ifndef BOOTANIM_GLYPHS
#define BOOTANIM_GLYPHS {0x054, 0x092, 0x111, 0x010}   // /  |  \  ■ (■ — одна точка 1 px в центре поля; Роб 28.09 21:00: «пиксели меньше, в строке толстые»)
#endif
static const unsigned short bootAnimGlyph[BOOTANIM_NSYM] = BOOTANIM_GLYPHS;

static unsigned bootAnimMix(unsigned a, unsigned b, float t) {   // ABGR: a -> b
  unsigned o = 0xFF000000u;
  for (int sh = 0; sh < 24; sh += 8) { float ca = (a >> sh) & 255, cb = (b >> sh) & 255; o |= ((unsigned)(ca + (cb - ca) * t) & 255) << sh; }
  return o;
}
static unsigned short bootAnimTab[BOOTANIM_BH][BOOTANIM_BW]; static int bootAnimTabOk;
// рисунок знака в клетке: бит y*4+x (x, y — пиксель клетки 0..3); 0 — в клетке знака нет. Таблица считается один раз
static unsigned bootAnimRest(int bx, int by) {
  if (!bootAnimTabOk) {
    for (int y = 0; y < BOOTLOGO_H; y++) {
      int n = 0; while (bootLogo[y][n]) n++;
      for (int x = 0; x < n; x++) if (bootLogo[y][x] == '#')
        bootAnimTab[y / BOOTANIM_CELL][x / BOOTANIM_CELL] |= (unsigned short)(1u << ((y % BOOTANIM_CELL) * BOOTANIM_CELL + x % BOOTANIM_CELL));
    }
    bootAnimTabOk = 1;
  }
  return bootAnimTab[by][bx];
}
// символ k (поле 3×3) -> маска клетки 4×4 (бит y*4+x) со сдвигом (1,1): строка 0 и столбец 0 клетки остаются зазором.
// Зазор слева-сверху, а не справа-снизу: волна идёт слева-сверху, там у символа уже собранный знак — с ним и не касаемся
#ifndef BOOTANIM_GOFS
#define BOOTANIM_GOFS 1   // tests/bootlogo: -DBOOTANIM_GOFS=0 (зазор справа-снизу) -> символы касаются знака -> FAIL
#endif
static unsigned bootAnimGlyphCell(int k) {
  unsigned g = bootAnimGlyph[k], m = 0;
  for (int b = 0; b < 9; b++) if (g >> b & 1) m |= 1u << ((b / 3 + BOOTANIM_GOFS) * BOOTANIM_CELL + b % 3 + BOOTANIM_GOFS);
  return m;
}
static int bootAnimSpan(void) { return BOOTANIM_PW + 2 * BOOTANIM_PH; }
// стадия клетки (-1 нет, 0..3 символ, 4 рисунок) и цвет при фронте front в проходе pass
static int bootAnimCell(int pass, float front, int bx, int by, unsigned *abgr) {
  float d = front - (float)(BOOTANIM_CELL * bx + 2 * BOOTANIM_CELL * by); int k;
  if (pass == 0) { if (d < 0.f) return -1; k = (int)(d / BOOTANIM_STAGE); if (k > BOOTANIM_NSYM) k = BOOTANIM_NSYM; }
  else k = (d < 0.f || d >= 3.f * BOOTANIM_STAGE) ? BOOTANIM_NSYM : 2 - (int)(d / BOOTANIM_STAGE);   // \ | / и снова рисунок
  float t = d >= 0.f ? d / BOOTANIM_WIDTH : 1.f; if (t > 1.f) t = 1.f;
  *abgr = d < BOOTANIM_WIDTH ? bootAnimMix(BOOTANIM_GLINT, BOOTANIM_REST, t * t) : BOOTANIM_REST;
  return k;
}
// один кадр: каждая клетка со знаком стирается (4×4 цветом bg) и рисуется своей стадией; put(u, x, y, abgr)
static void bootAnimFrame(int pass, float front, int ox, int oy, unsigned bg, void (*put)(void *, int, int, unsigned), void *u) {
  for (int by = 0; by < BOOTANIM_BH; by++)
    for (int bx = 0; bx < BOOTANIM_BW; bx++) {
      unsigned rest = bootAnimRest(bx, by); if (!rest) continue;
      unsigned c = 0; int k = bootAnimCell(pass, front, bx, by, &c);
      unsigned m = k < 0 ? 0 : k < BOOTANIM_NSYM ? bootAnimGlyphCell(k) : rest;
      for (int b = 0; b < BOOTANIM_CELL * BOOTANIM_CELL; b++) {
        int px = BOOTANIM_CELL * bx + b % BOOTANIM_CELL, py = BOOTANIM_CELL * by + b / BOOTANIM_CELL;
#ifndef BOOTANIM_CELL_GLINT   // блик по пикселю, не по клетке: клетка 4×4 одним цветом давала светлые квадраты в волне (Роб 28.09 21:00)
        if ((m >> b) & 1) { float d = front - (float)(px + 2 * py), t = d >= 0.f ? d / BOOTANIM_WIDTH : 1.f; if (t > 1.f) t = 1.f;
                            c = d < BOOTANIM_WIDTH ? bootAnimMix(BOOTANIM_GLINT, BOOTANIM_REST, t * t) : BOOTANIM_REST; }
#endif
        for (int sy = 0; sy < BOOTANIM_SCALE; sy++) for (int sx = 0; sx < BOOTANIM_SCALE; sx++)
          put(u, ox + px * BOOTANIM_SCALE + sx, oy + py * BOOTANIM_SCALE + sy, ((m >> b) & 1) && sx < BOOTANIM_DOT_W && sy < BOOTANIM_DOT_H ? c : bg);
      }
    }
}
#endif
