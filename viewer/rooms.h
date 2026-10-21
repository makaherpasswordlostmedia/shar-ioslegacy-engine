// Комнаты уровня (пункт 11.2): пакет SHI1 (tools/interior_export.py) — коллизия, старт и выход каждой комнаты, двери
// в городе — и переходы «дверь -> старт комнаты», «локатор выхода -> к двери». Один код для EBOOT (viewer/main.c) и
// ботов на Маке (tools/bots/world.c). Чистый C99 без PSP; память — один буфер пакета, коллизия — colInit по нему.
// Рисование комнат (пакет SHG1) — только в main.c.
#ifndef ROOMS_H
#define ROOMS_H
#include <stddef.h>
#include "col.h"
#include "game.h"
#include "roomcam.h"

#define ROOMS_MAX 8
#define ROOMS_DOORS 16
// Вход и выход — по триггерам из данных (TriggerVolume локатора двери и локатора *_exit, пакет версии 2): Гомер пешком
// внутри объёма; каждый объём «взводится», когда Гомер побывал снаружи (после выхода он стоит в триггере двери, старт
// комнаты — на краю или рядом с триггером выхода). Пакеты без триггеров (версии 0–1) — прежние радиусы:
#define ROOM_DOOR_R 1.5f      // вход: Гомер пешком ближе 1.5 м к локатору двери и не дальше 3 м по высоте
#define ROOM_DOOR_REARM 3.f   // после выхода дверь снова «взводится», когда Гомер отошёл дальше 3 м от всех дверей
#define ROOM_EXIT_R 1.0f      // выход: ближе 1 м к локатору *_exit ...
#define ROOM_EXIT_ARM 1.8f    // ... после того как хоть раз отошёл от него дальше 1.8 м (старт стоит в 1–2 м от выхода)

// RoomTrig и roomTrigIn — viewer/roomcam.h (объёмы TriggerVolume: двери, выходы, зоны камер)
typedef struct { char name[32]; float start[4], exit[3]; RoomTrig exitTrig; ColWorld col; } Room;   // start: x y z курс (куда Гомер входит)
typedef struct { char name[32]; float p[3], h; int room; RoomTrig trig; } RoomDoor;   // h — курс наружу (NAN: в пакете нет, версия 0)
typedef struct { Room room[ROOMS_MAX]; int nroom; RoomDoor door[ROOMS_DOORS]; int ndoor; void *mem; } Rooms;
typedef struct { int room, lastDoor, doorArmed, exitArmed; int needAction, action; } RoomState;   // комната Гомера (-1 — город), дверь входа, взводы
// Вход и выход по △ (правка Роба 41, видео с PSP 4:07: «вход и выход только с треугольником, при подходе значок мигает»):
// needAction = 1 (EBOOT) — Гомер в триггере взведённой двери / выхода только показывает △ (roomsDoorNear), переход — по △
// этого кадра (action = 1); needAction = 0 — по самому триггеру, как раньше (боты tools/bots/world.c, позиционная инициализация).
// Данные: у двери — локатор входа в интерьер (вид 7) с триггером, кнопки в нём нет; «только по △» — слово Роба и
// ActionButton оригинала (правило порта, сверить с эталоном PS2)

// Пакет в памяти (буфер выровнен на 16; при успехе переходит во владение Rooms — roomsFree освобождает его free()).
// Всё или ничего: битый пакет (размеры, смещения, номер комнаты у двери, COL1) — отказ, R пуст. 0 = ок, <0 — причина
int roomsParse(Rooms *R, void *buf, size_t n);
const char *roomsError(int code);
void roomsFree(Rooms *R);
void roomStateInit(RoomState *s);
// Кадр, после gameAfterCar: пешком у двери — вход (G->pHomerWorld = коллизия комнаты, Гомер на старт), у выхода —
// к той же двери (pHomerWorld = NULL, курс наружу). canEnter (NULL — всегда можно): 0 — комнату не открыть (нет
// рисования, нет памяти), Гомер остаётся на улице, дверь снимается с взвода. 1 — вошёл, -1 — вышел, 0 — ничего
enum { ROOM_EV_NONE = 0, ROOM_EV_ENTER = 1, ROOM_EV_EXIT = -1 };
int roomsStep(const Rooms *R, RoomState *s, Game *G, int (*canEnter)(void *u, int room), void *u);
// Гомер пешком в триггере взведённой двери (в городе) или выхода (в комнате): 1 — △ сейчас войдёт / выйдет
int roomsDoorNear(const Rooms *R, const RoomState *s, const Game *G);
// Цель метки «купи костюм» (этап buyskin, комната-гардероб): spot(i, out4) — места выбора костюма x y z r (wardrobeSpot / skins.txt), curRoom — комната Гомера (-1 — город).
// Место в комнате k: Гомер в k — до самого места, иначе — до двери города комнаты k; побеждает ближайшее. out — место (если Гомер уже в его комнате) или дверь.
// 0 — мест нет или ни одно не лежит ни в одной комнате (тогда метки нет). Правило порта: оригинал метку этапа не показывает/не сверено (записей PS2 L3–L5 нет)
int roomsSpotTarget(const Rooms *R, int curRoom, int (*spot)(int i, float *out4), float px, float py, float pz, float out[3]);
// имя текущей комнаты, как в скриптах миссий (KwikEMart, SimpsonsHouse, SpringfieldElementary); NULL — город
const char *roomsName(const Rooms *R, const RoomState *s);
#endif
