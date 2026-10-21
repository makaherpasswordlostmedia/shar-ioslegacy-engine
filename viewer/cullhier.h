// Иерархическое отсечение города (план оптимизации А3, 10.10.2026): прежний цикл по списку PVS глаза проверял КАЖДЫЙ кусок (расстояние до ящика, 4 боковые плоскости,
// чтение горячей записи 32 Б): cull_calls 919–1212 на кадр, cull_us 1,8–2,4 мс, ≈600 тактов на кусок (память). Список PVS не знает, куда смотрит камера, и
// на 70 % состоит из кусков вне пирамиды. Теперь ящик КЛЕТКИ (куски лежат внутри него, как у прежней ветки без PVS) классифицируется один раз за кадр:
// 0 — вне (дальше дальности или целиком за боковой плоскостью): куски не читаются вовсе; 2 — целиком внутри всех плоскостей: куски без проверки плоскостей;
// 1 — иначе, как прежде. Множество принятых кусков то же (проверка tests/cullhier/host.c на случайных позах уровней 1–7). CULL_HIER_OLD=1 — прежний цикл.
// Чистые функции без зависимостей от PSP: хост-тест подключает этот файл.
#ifndef CULLHIER_H
#define CULLHIER_H
static inline float chBoxD2(const float *b, float ex, float ey, float ez) {   // как boxD2 (main_render.h)
  float dx = b[0] - ex > 0 ? b[0] - ex : (ex - b[3] > 0 ? ex - b[3] : 0);
  float dy = b[1] - ey > 0 ? b[1] - ey : (ey - b[4] > 0 ? ey - b[4] : 0);
  float dz = b[2] - ez > 0 ? b[2] - ez : (ez - b[5] > 0 ? ez - b[5] : 0);
  return dx * dx + dy * dy + dz * dz;
}
static inline int chVisBox(const float *b, const float pl[4][3], float ex, float ey, float ez) {   // как visBox: ящик целиком снаружи одной боковой плоскости — 0
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? b[3] : b[0]) - ex, py = (pl[i][1] > 0 ? b[4] : b[1]) - ey, pz = (pl[i][2] > 0 ? b[5] : b[2]) - ez;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
  }
  return 1;
}
// 0 — куски клетки отброшены (дальность или боковая плоскость, то же решение, что у каждого её куска), 1 — проверять как прежде, 2 — плоскости пройдены всеми кусками
static inline int chClassify(const float *bb, const float pl[4][3], float ex, float ey, float ez, float drawDist) {
  if (chBoxD2(bb, ex, ey, ez) > drawDist * drawDist) return 0;
  int r = 2;
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? bb[3] : bb[0]) - ex, py = (pl[i][1] > 0 ? bb[4] : bb[1]) - ey, pz = (pl[i][2] > 0 ? bb[5] : bb[2]) - ez;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
    float qx = (pl[i][0] > 0 ? bb[0] : bb[3]) - ex, qy = (pl[i][1] > 0 ? bb[1] : bb[4]) - ey, qz = (pl[i][2] > 0 ? bb[2] : bb[5]) - ez;
    if (qx * pl[i][0] + qy * pl[i][1] + qz * pl[i][2] < 0) r = 1;
  }
  return r;
}
#endif
