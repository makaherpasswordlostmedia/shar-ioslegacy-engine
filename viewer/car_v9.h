// Машина: управление в духе v8 (разгон 14, тормоз 30, 30 м/с вперёд / 9 назад, сопротивление 1.2, руль 2.1 рад/с
// с поправкой на скорость), но с честной коллизией по COL1 (col.h). Чистый C99, float, без malloc.
// Мир: метры, y вверх; курс h: вперёд = (sin h, cos h), руль +1 = вправо (h уменьшается), как в main.c.
// Модель машины смотрит в -Z и рисуется с поворотом h + pi (см. carPieceMatrix).
#ifndef SHAR_CAR_H
#define SHAR_CAR_H
#include "col.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  // геометрия famil_v (куски owner == 1 в level.shr): кузов 2.21 x 5.35 м без зеркал, центр на 0.32 м позади
  // середины между осями; колёса x = +-0.91, передняя ось +1.47, задняя -1.82 (вдоль курса от начала машины)
  float halfW, halfL, bodyOfs;   // полуширина, полудлина, сдвиг центра кузова вдоль курса (м, минус = назад)
  float wheelX, wheelF, wheelR;  // колёса: вбок, передняя ось вперёд, задняя ось назад
  float bandLo, bandHi;          // твёрдый слой кузова над полом: ниже — бордюры (заезжаем), выше — стены
  float step;                    // на какую ступеньку колесо въезжает само
  // езда (как main.c v8)
  float accel, brake, revAccel, maxFwd, maxRev, drag;
  float steerRate, steerResp, steerFull, steerFade;   // 2.1 рад/с, отклик 8/с, полный руль с 6 м/с, спад /(1+v/25)
  float gravity, slopeK, grip;   // 22 м/с2 в воздухе; доля уклона в разгоне; гашение бокового скольжения, 1/с
  float bounce, hardHit;         // отскок от стены (доля) и с какой скорости удара — жёсткий удар (м/с)
  float snapDown;                // «подвеска»: на сколько за подшаг колёса дотягиваются вниз, не отрываясь
  float fallReset;               // приземлился ниже точки отрыва больше чем на это (ущелье под мостом ~30 м) —
                                 // через 1 с вернуть на последнее надёжное место; прыжки с трамплинов ~12 м не трогаем
  float sub;                     // фиксированный подшаг, с
} CarParams;

typedef struct { float throttle, brake, steer; } CarInput;   // газ 0..1, тормоз/назад 0..1, руль -1..1

#define CAR_SAFE 16

typedef struct {
  // состояние
  float x, y, z, h;         // начало машины: на земле, посередине между осями; y — высота пятна колёс
  float v, vl, vy;          // скорость вдоль курса (со знаком), вбок (вправо +), вверх
  float gx, gz;             // наклон пола под машиной (dY/dX, dY/dZ): пол Y(X,Z) = y + gx*(X-x) + gz*(Z-z)
  float pitch, roll;        // рад: нос вверх +, правый борт вверх +
  float steer;              // сглаженный руль
  int grounded, wheels;     // на земле; сколько колёс нашли опору
  // отрисовка (сглаженные высота/наклон — «подвеска»)
  float ry, rvy, rpitch, rroll;
  // последний кадр: контакты со стенами
  int contacts;             // сколько контактов было в последнем подшаге
  float cnx[4], cnz[4];     // их нормали (от стены к машине)
  unsigned char ctype[4];   // и типы (COL_TRI / COL_BOX / COL_CYL / COL_SEG)
  float hitSpeed;           // самый сильный удар за кадр, м/с (скорость в стену)
  float pen;                // остаточное проникновение после последнего подшага, м
  int reverts, recoveries;  // подшаги, отменённые целиком; возвраты на надёжное место (всего)
  int revWhy;               // причина последней отмены: 1 не вытолкнулось, 2 за забором, 4/8 путь через забор, 16 край мира,
                            // 32 земля выше, чем можно въехать (склон сбоку / низкий навес)
  // служебное
  float acc, t, airT, noGroundT, embedT, bellyT, fallTop, fallT0, fallPendT; int fallPending;
  struct { float x, y, z, h, t; } safe[CAR_SAFE]; int nsafe, safeHead; float safeT;
  float homeX, homeY, homeZ, homeH;
  CarParams p;
} Car;

void carDefaults(CarParams *p);
// поставить машину (x, z, курс h) на землю под высотой y + 2 м (START, телепорт, тест-прогон)
void carPlace(Car *c, const ColWorld *w, float x, float y, float z, float h);
// инициализация: параметры (или NULL = по умолчанию) + carPlace; эта же точка — запасной «дом» для возврата
void carInit(Car *c, const CarParams *p, const ColWorld *w, float x, float y, float z, float h);
// шаг кадра: dt любой (режется на подшаги p.sub, не больше 0.1 с за вызов)
void carUpdate(Car *c, const ColWorld *w, const CarInput *in, float dt);
// кузов в формате colPushCar/colProbeCar для текущего положения
void carBox(const Car *c, CarBox *b);
// матрица куска машины для GE (столбцы, как ScePspFMatrix4): мир = T + R * (o + sc * v); модель смотрит в -Z,
// её низ колёс на -lift. Учитывает курс, наклон и сглаженную высоту.
void carPieceMatrix(const Car *c, float lift, float ox, float oy, float oz, float sc, float m[16]);

#ifdef __cplusplus
}
#endif
#endif
