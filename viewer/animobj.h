// Анимированные объекты уровня с коллизией и действиями (AnimCollision 0x3F00008 / Anim 0x3F0000C диска):
// грузовик Duff у Kwik-E-Mart (подъёмник по △), ветка у дома Симпсонов, платформы/двери/вентиляторы АЭС и т.п.
// Экспорт — tools/animobj_export.py: рисунок — типы SPR1 (viewer/stateprops.c рисует и крутит циклы), объёмы — ящики и
// цилиндры COL1 (по ним ездят и ходят), таблица ANM1 в секции PRP2 (@52 смещение, @56 размер) связывает объект с его
// экземплярами SPR1 и «живыми» объёмами COL1. Здесь: действия (△ / вход в объём / дверь), кадр клипа объектов с
// действием, перестановка живых объёмов COL1 по позе суставов каждый кадр. Чистый C99 без GU, без malloc в кадре.
#ifndef SHAR_ANIMOBJ_H
#define SHAR_ANIMOBJ_H
#include <stdint.h>
#include "col.h"
#include "stateprops.h"

#ifdef __cplusplus
extern "C" {
#endif

// действие из action-локатора (tools/animobj_export.py ACTIONS)
enum { AO_NONE, AO_PLAYANIM, AO_AUTOPLAY, AO_TOGGLE, AO_AUTODOOR, AO_DOORBELL };

typedef struct { uint16_t firstInst, nInst, firstVol, nVol; uint8_t action, trig; uint16_t pad; uint16_t nfr, pad2;
                 float fps, c[3], h[3], ax[9]; } AoObj;                                                   // 80 Б
typedef struct { uint8_t kind, pad; uint16_t obj; uint32_t col; uint16_t joint, pad2; float c[3], a[9], h[3]; } AoVol;   // 72 Б

typedef struct { float f; float delay; uint8_t playing, inTrig, pad[2]; } AoRun;   // pad[0] — объёмы поставлены; pad[1] — подъёмник: 0 не проверен, 1 да, 2 нет (DUFF_LIFT)   // delay: задержка нажатия до начала клипа (правка 462)
#define AO_MAXOBJ 64
#define AO_NEAR 90.f            // живые объёмы переставляются, пока игрок ближе этого (дальше машина за кадр не доедет)

typedef struct {
  const AoObj *obj; const AoVol *vol; unsigned nobj, nvol;
  AoRun run[AO_MAXOBJ];
  float liftK[AO_MAXOBJ];       // №519: растяжение вертикального хода подъёмника малого хода (1 — нет)
  float idleT[AO_MAXOBJ];       // №519: с без Гомера на платформе Toggle, пока она едет
  float liftF0[AO_MAXOBJ];      // №519: кадр клипа, с которого подъёмник начинает двигаться (минус 6 кадров); до него в клипе пауза ~2 с — при автозапуске её пропускаем
  int want;                     // объект, которому отдан бы △ (игрок пешком в его объёме), -1 нет
  unsigned presses, plays, moved;   // счётчики (гейты, отчёт)
} AnimObjs;

// prp2 — вся секция PRP2 уровня (как у propsInit). 0 — есть ANM1, 1 — таблицы нет (старый level.shr), <0 — битая
int  aoInit(AnimObjs *a, const void *prp2, unsigned size, const StateProps *sp, const ColWorld *w);
// кадр (после spUpdate): p — ступни Гомера / низ машины; onFoot — Гомер пешком; action — △ этого кадра отдан объекту.
// Ведёт кадр клипа объектов с действием и переставляет живые объёмы COL1 по позе (w пишется: секция COL1 в ОЗУ).
void aoStep(AnimObjs *a, StateProps *sp, ColWorld *w, float px, float py, float pz, int onFoot, int action, float dt);
// №519 (Роб 11.10): подъёмник Duff едет сам, как только Гомер встал на его ящики-платформу (в клипе живой объём поднимается больше LIFT_MIN_RISE), без △ и задержки;
// до верха не больше двух прыжков. Правило общее для объектов PlayAnim с подъёмом. DUFF_LIFT_OLD=1 — только по △ с задержкой AO_PRESS_DELAY (прежнее)
#ifndef DUFF_LIFT_OLD
#define DUFF_LIFT_OLD 0
#endif
#ifndef DUFF_LIFT_SKIP_OLD
#define DUFF_LIFT_SKIP_OLD 0   // =1 — автозапуск с кадра 0 клипа (пауза ~2 с до подъёма)
#endif
#ifndef DUFF_LIFT_BOOST_OLD
#define DUFF_LIFT_BOOST_OLD 0   // =1 — ход подъёмника как в клипе (с низкого ящика до крыши двойной прыжок)
#endif
#ifndef TOGGLE_AUTO_OLD
#define TOGGLE_AUTO_OLD 0       // =1 — платформы Toggle (АЭС) только по △ у выключателя
#endif
#define LIFT_SMALL_RISE 3.0f    // м: подъёмники малого хода (Duff 1,06 м) растягиваем; лифты на 8 и 13 м едут как в клипе
#define LIFT_KMAX 3.0f
#define TOGGLE_MIN_MOVE 3.0f    // м: платформа Toggle, которая сдвигается на столько и больше (АЭС 4 и 14 м), запускается посадкой
#define TOGGLE_IDLE_STOP 6.0f   // с: платформа, на которой давно никто не стоит, в начале цикла останавливается
#define LIFT_MIN_RISE 0.8f   // м: меньше — это не подъёмник (двери и створки АЭС с тем же действием не едут от того, что на них встали)
// Правка Роба 462 (10.10: грузовик Duff у Kwik-E-Mart): красное кольцо выключателя видно издалека и всегда пульсирует; после △ платформа поднимается
// с небольшой задержкой AO_PRESS_DELAY, чтобы успеть запрыгнуть. Кольцо — объекты с действием PlayAnim / ToggleOnOff и триггером. -> 1 и центр/радиус
// кольца на земле (мир), 0 — у объекта кольца нет. AO_SWITCH_OLD=1 — прежнее: без кольца и без задержки
#ifndef AO_SWITCH_OLD
#define AO_SWITCH_OLD 0
#endif
#define AO_PRESS_DELAY 0.8f   // с: ПРАВИЛО ПОРТА (в данных нет; на записи PS2 платформа стартует «с небольшой задержкой»)
#define AO_RING_FAR 60.f      // м: кольцо рисуется, пока игрок ближе (видно издалека)
int  aoSwitchRing(const AnimObjs *a, unsigned k, float c[3], float *r);
int  aoWantsAction(const AnimObjs *a);   // номер объекта для △ (по прошлому шагу) или -1
// правка 420 (ловушки бонус-игры): живые объёмы объекта k — по позе его первого экземпляра SPR1 сейчас (кадр ставит вызывающий в
// SpRun.poseF), без условия «игрок ближе AO_NEAR» (соперник ИИ въезжает в ловушку далеко от игрока)
void aoPlace(AnimObjs *a, StateProps *sp, ColWorld *w, unsigned k);

#ifdef __cplusplus
}
#endif
#endif
