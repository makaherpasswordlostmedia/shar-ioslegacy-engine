// Правки Роба 224/237/251 (швы «мигают»): растеризатор номеров треугольников для модели GE (tools/seams_ge.py).
// Вершины — экранные 12.4 (1/16 пикселя, как у GE после вьюпорта), глубина — метры вдоль взгляда; покрытие по центрам
// пикселей, правило «верх-лево» (общее ребро с одинаковыми вершинами закрашивается ровно один раз — без дыр).
// В пикселе остаётся ближайший треугольник: его номер (id, -1 — пусто) и глубина.
// Сборка: clang -O2 -shared -o seams_ge.dylib seams_ge.c (делает tools/seams_ge.py сам)
#include <stdint.h>

void raster_id(int n, const int32_t *xy, const float *z, const int32_t *tid, int W, int H, int32_t *id, float *dep) {
  for (int t = 0; t < n; t++) {
    int64_t x0 = xy[6 * t], y0 = xy[6 * t + 1], x1 = xy[6 * t + 2], y1 = xy[6 * t + 3], x2 = xy[6 * t + 4], y2 = xy[6 * t + 5];
    float z0 = z[3 * t], z1 = z[3 * t + 1], z2 = z[3 * t + 2];
    int64_t area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (area == 0) continue;
    if (area < 0) { int64_t tx = x1, ty = y1; x1 = x2; y1 = y2; x2 = tx; y2 = ty; float tz = z1; z1 = z2; z2 = tz; area = -area; }
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
        double w0 = (double)e[1] / (double)area, w1 = (double)e[2] / (double)area, w2 = (double)e[0] / (double)area;
        float zz = (float)(1.0 / (w0 / z0 + w1 / z1 + w2 / z2));
        int k = py * W + px;
        if (id[k] < 0 || zz < dep[k]) { dep[k] = zz; id[k] = tid[t]; }
      }
    }
  }
}
