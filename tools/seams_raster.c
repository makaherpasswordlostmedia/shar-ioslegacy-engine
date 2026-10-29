// Правка Роба 106 (швы): растеризатор покрытия кадра PSP на Маке — «clearchk без эмулятора» (tools/seams_raster.py).
// Вершины уже в экранных координатах GE: 12.4 фиксированная точка (1/16 пикселя, как у GE после вьюпорта), глубина — метры
// вдоль взгляда. Покрытие — по центрам пикселей, правило «верх-лево» (общее ребро двух треугольников с одинаковыми вершинами
// закрашивается ровно один раз: без дыр и без двойных). Т-стык и щель между кусками дают пиксели без покрытия — как пурпур
// служебного режима clearchk (viewer/main.c), но без увеличения и плавающей точки эмулятора.
// Сборка: clang -O2 -shared -o seams_raster.dylib seams_raster.c (делает tools/seams_raster.py сам)
#include <stdint.h>

// tri: n треугольников по 3 вершины (x16, y16) int32; z: глубина вершин float; cov: W*H байт (покрыт = 1), dep: W*H float
// (наименьшая глубина), gnd: 1 — треугольник земли (наклон до 60°), gb: W*H — земля ли ближайшее; кадр [0,W)x[0,H)
void raster(int n, const int32_t *xy, const float *z, const uint8_t *gnd, int W, int H, uint8_t *cov, float *dep, uint8_t *gb) {
  for (int t = 0; t < n; t++) {
    int64_t x0 = xy[6 * t], y0 = xy[6 * t + 1], x1 = xy[6 * t + 2], y1 = xy[6 * t + 3], x2 = xy[6 * t + 4], y2 = xy[6 * t + 5];
    float z0 = z[3 * t], z1 = z[3 * t + 1], z2 = z[3 * t + 2];
    int64_t area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (area == 0) continue;
    if (area < 0) {   // обход к одному виду (отсечения изнанки в городе нет: O_CULL выключен)
      int64_t tx = x1, ty = y1; x1 = x2; y1 = y2; x2 = tx; y2 = ty; float tz = z1; z1 = z2; z2 = tz; area = -area;
    }
    int64_t mnx = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2), mxx = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    int64_t mny = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2), mxy = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    int px0 = (int)((mnx - 8 + 15) >> 4), px1 = (int)((mxx - 8) >> 4), py0 = (int)((mny - 8 + 15) >> 4), py1 = (int)((mxy - 8) >> 4);
    if (px0 < 0) px0 = 0; if (py0 < 0) py0 = 0; if (px1 >= W) px1 = W - 1; if (py1 >= H) py1 = H - 1;
    if (px0 > px1 || py0 > py1) continue;
    // рёбра e_i(p) = (b - a) x (p - a); при area > 0 внутри все > 0; ребро верх/лево включает 0
    int64_t ax[3] = {x0, x1, x2}, ay[3] = {y0, y1, y2}, bx[3] = {x1, x2, x0}, by[3] = {y1, y2, y0}, bias[3];
    for (int i = 0; i < 3; i++) {
      int64_t dx = bx[i] - ax[i], dy = by[i] - ay[i];
      int topleft = (dy < 0) || (dy == 0 && dx > 0);   // y вниз, обход «положительный»: левое ребро идёт вверх, верхнее — вправо
      bias[i] = topleft ? 0 : -1;
    }
    for (int py = py0; py <= py1; py++) {
      int64_t sy = (int64_t)py * 16 + 8;
      for (int px = px0; px <= px1; px++) {
        int64_t sx = (int64_t)px * 16 + 8, e[3]; int in = 1;
        for (int i = 0; i < 3; i++) {
          e[i] = (bx[i] - ax[i]) * (sy - ay[i]) - (by[i] - ay[i]) * (sx - ax[i]);
          if (e[i] + bias[i] < 0) { in = 0; break; }
        }
        if (!in) continue;
        // e[1] — вес вершины 0, e[2] — вершины 1, e[0] — вершины 2. Глубина с перспективой: по экрану линейна 1/w (как z/w
        // у GE), не сама w — у длинного треугольника (юбка вдоль дороги на 100+ м) линейная w врёт на десятки метров и
        // рисует ложное «сквозь»
        double w0 = (double)e[1] / (double)area, w1 = (double)e[2] / (double)area, w2 = (double)e[0] / (double)area;
        float zz = (float)(1.0 / (w0 / z0 + w1 / z1 + w2 / z2));
        int k = py * W + px;
        if (!cov[k] || zz < dep[k]) { dep[k] = zz; gb[k] = gnd[t]; }
        cov[k] = 1;
      }
    }
  }
}

// 16-битная глубина GE (DepthRange(65535, 0), GEQUAL, очистка 0): z16 вершин уже со сдвигом слоя (sceGuDepthOffset),
// глубина интерполируется по экрану линейно и пишется целым. Треугольники идут в порядке отрисовки движка. win: номер
// треугольника, чей пиксель остался в кадре (-1 — пусто), zb: буфер глубины (W*H int32).
void raster16(int n, const int32_t *xy, const float *z16, const float *zf, const int32_t *id, int W, int H, int32_t *zb, int32_t *win, float *wd) {
  for (int t = 0; t < n; t++) {
    int64_t x0 = xy[6 * t], y0 = xy[6 * t + 1], x1 = xy[6 * t + 2], y1 = xy[6 * t + 3], x2 = xy[6 * t + 4], y2 = xy[6 * t + 5];
    float z0 = z16[3 * t], z1 = z16[3 * t + 1], z2 = z16[3 * t + 2], f0 = zf[3 * t], f1 = zf[3 * t + 1], f2 = zf[3 * t + 2];
    int64_t area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (area == 0) continue;
    if (area < 0) { int64_t tx = x1, ty = y1; x1 = x2; y1 = y2; x2 = tx; y2 = ty; float tz = z1; z1 = z2; z2 = tz; tz = f1; f1 = f2; f2 = tz; area = -area; }
    int64_t mnx = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2), mxx = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    int64_t mny = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2), mxy = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    int px0 = (int)((mnx - 8 + 15) >> 4), px1 = (int)((mxx - 8) >> 4), py0 = (int)((mny - 8 + 15) >> 4), py1 = (int)((mxy - 8) >> 4);
    if (px0 < 0) px0 = 0; if (py0 < 0) py0 = 0; if (px1 >= W) px1 = W - 1; if (py1 >= H) py1 = H - 1;
    if (px0 > px1 || py0 > py1) continue;
    int64_t ax[3] = {x0, x1, x2}, ay[3] = {y0, y1, y2}, bx[3] = {x1, x2, x0}, by[3] = {y1, y2, y0}, bias[3];
    for (int i = 0; i < 3; i++) { int64_t dx = bx[i] - ax[i], dy = by[i] - ay[i]; bias[i] = ((dy < 0) || (dy == 0 && dx > 0)) ? 0 : -1; }
    for (int py = py0; py <= py1; py++) {
      int64_t sy = (int64_t)py * 16 + 8;
      for (int px = px0; px <= px1; px++) {
        int64_t sx = (int64_t)px * 16 + 8, e[3]; int in = 1;
        for (int i = 0; i < 3; i++) { e[i] = (bx[i] - ax[i]) * (sy - ay[i]) - (by[i] - ay[i]) * (sx - ax[i]); if (e[i] + bias[i] < 0) { in = 0; break; } }
        if (!in) continue;
        double zz = ((double)e[1] * z0 + (double)e[2] * z1 + (double)e[0] * z2) / (double)area;
        int32_t zi = (int32_t)zz; if (zi < 0) zi = 0; if (zi > 65535) zi = 65535;
        int k = py * W + px;
        if (zi >= zb[k]) { zb[k] = zi; win[k] = id[t]; wd[k] = (float)(1.0 / (((double)e[1] / f0 + (double)e[2] / f1 + (double)e[0] / f2) / (double)area)); }   // wd — метры с перспективой
      }
    }
  }
}
