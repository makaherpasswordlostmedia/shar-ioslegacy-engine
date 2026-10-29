// camnear.h — слово Роба №502 («камера никогда не должна попадать внутрь»: когда мимо проходит персонаж и знак миссии над ним, рядом дом,
// человек или машина — видны их внутренности). Ближняя плоскость режет модель, а задние грани не рисуются — внутри пусто, видна изнанка.
// Общее правило: то, что стоит к глазу ближе порога, не рисуется (не «внутрь», а исчезает, как в играх от третьего лица). Пороги — запас к
// ближней плоскости кадра (0,25–1,5 м; homer.c camNear, chaseNear), чтобы объект исчез до того, как плоскость войдёт в его объём.
// -DCAM_NEARHIDE_OLD=1 — прежнее (всё рисуется). Хост-проверка: tests/camera/nearhide.c
#ifndef CAMNEAR_H
#define CAMNEAR_H
#include <math.h>
#ifndef CAM_NEARHIDE_OLD
#define CAM_NEARHIDE_OLD 0
#endif
#define CAM_HIDE_NPC 0.8f    // м от оси тела персонажа (радиус тела ~0,35 + запас к плоскости)
#define CAM_HIDE_ICON 1.0f   // м от точки знака (значок миссии над головой, кольцо): его размер до ~0,6 м
#define CAM_HIDE_BOX 0.5f    // м от коробки машины/пешехода трафика, пропа
// ближняя плоскость текущего кадра (frameNear; ставит main_loop.h перед рисованием, 0 — не задана): объект, который она режет, не рисуем
// и на подходе к ней: порог = max(постоянный, ближняя плоскость + запас). Определена в msn_view.c
extern float camNearNow;
// №602 (Роб 15.10: «то, что проезжает мимо, пропадает раньше, чем ушло из кадра»): камера сама не входит в кузова/людей/геометрию (camsafe), ближняя
// плоскость по ним сжимается, поэтому объект гаснет только когда её плоскость вот-вот войдёт в его объём (ближняя плоскость + тело + малый запас),
// а не в 0,5–1,0 м от глаза. NEAR_CULL_OLD=1 / «flag nearcullold 1» — прежние пороги №502
extern int camNearOld;
static inline float camThr(float base, float pad) { float t = camNearNow + pad; return t > base ? t : base; }
static inline float camPointBoxD2(float ex, float ey, float ez, const float b[6]) {   // квадрат расстояния от глаза до коробки (0 — внутри)
  float dx = fmaxf(fmaxf(b[0] - ex, ex - b[3]), 0.f), dy = fmaxf(fmaxf(b[1] - ey, ey - b[4]), 0.f), dz = fmaxf(fmaxf(b[2] - ez, ez - b[5]), 0.f);
  return dx * dx + dy * dy + dz * dz;
}
static inline int camNearBox(float ex, float ey, float ez, const float b[6], float m) { float t = camNearOld ? camThr(m, .1f) : camNearNow + .05f; return !CAM_NEARHIDE_OLD && camPointBoxD2(ex, ey, ez, b) < t * t; }
static inline int camNearPoint(float ex, float ey, float ez, float x, float y, float z, float r) {
  float dx = x - ex, dy = y - ey, dz = z - ez, t = camNearOld ? camThr(r, .7f) : camNearNow + .15f; return !CAM_NEARHIDE_OLD && dx * dx + dy * dy + dz * dz < t * t;   // знак: r — его размер, плоскость + .7 м
}
static inline int camNearBody(float ex, float ey, float ez, float x, float y0, float y1, float z, float r) {   // вертикальный отрезок (ноги — макушка)
  float cy = ey < y0 ? y0 : ey > y1 ? y1 : ey, dx = x - ex, dy = cy - ey, dz = z - ez, t = camNearOld ? camThr(r, .35f) : camNearNow + .35f + .05f; return !CAM_NEARHIDE_OLD && dx * dx + dy * dy + dz * dz < t * t;
}
static inline int camNearSphere(float ex, float ey, float ez, float x, float y, float z, float rad) {   // проп/стейтпроп: центр и радиус
  float dx = x - ex, dy = y - ey, dz = z - ez, t = camNearOld ? camThr(rad + .6f, rad + .1f) : rad + camNearNow + .05f; return !CAM_NEARHIDE_OLD && dx * dx + dy * dy + dz * dz < t * t;
}
#endif
