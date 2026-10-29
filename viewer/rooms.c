// Комнаты уровня (пункт 11.2): разбор SHI1 и переходы через двери — см. rooms.h. Логика перехода перенесена из
// tools/bots/world.c (пороги-радиусы — для старых пакетов без триггеров, поведение то же); новое — из данных: курс старта
// (от InteriorEntryStart к InteriorEntryEnd) и курс наружу у двери (версия 1), триггеры двери и выхода (версия 2), и
// отказ от входа, если комнату не открыть (canEnter).
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "rooms.h"

static const char *errs[] = {"ok", "нет данных", "не SHI1", "версия", "комнат/дверей больше предела", "таблицы не в файле",
                             "смещение COL1", "COL1 не читается", "номер комнаты у двери", "не число в координатах", "триггер"};
const char *roomsError(int code) { return code <= 0 && -code < (int)(sizeof errs / sizeof *errs) ? errs[-code] : "?"; }

static unsigned u32at(const unsigned char *b) { unsigned v; memcpy(&v, b, 4); return v; }
static int finite3(const float *v) { return isfinite(v[0]) && isfinite(v[1]) && isfinite(v[2]); }

void roomsFree(Rooms *R) {
  for (int i = 0; i < R->nroom; i++) colFree(&R->room[i].col);
  free(R->mem); memset(R, 0, sizeof *R);
}

int roomsParse(Rooms *R, void *buf, size_t n) {
  memset(R, 0, sizeof *R);
  const unsigned char *b = buf;
  if (!b || n < 16) return -1;
  if (memcmp(b, "SHI1", 4)) return -2;
  unsigned nr = u32at(b + 4), nd = u32at(b + 8), ver = u32at(b + 12);
  if (ver > 2) return -3;
  unsigned rrec = ver >= 2 ? 128 : 64, drec = ver == 0 ? 48 : ver == 1 ? 64 : 128;   // версия 2: + триггер 64 Б в каждой записи
  if (nr > ROOMS_MAX || nd > ROOMS_DOORS) return -4;
  size_t tab = 16 + (size_t)nr * rrec + (size_t)nd * drec;
  if (tab > n) return -5;
  unsigned off[ROOMS_MAX + 1];
  for (unsigned i = 0; i < nr; i++) {
    const unsigned char *r = b + 16 + (size_t)i * rrec; Room *m = &R->room[i];
    memcpy(m->name, r, 32); m->name[31] = 0; memcpy(m->start, r + 32, 16); memcpy(m->exit, r + 48, 12); off[i] = u32at(r + 60);
    if (!finite3(m->start) || !isfinite(m->start[3]) || !finite3(m->exit)) return -9;
    if (ver >= 2) { if (roomTrigRead(&m->exitTrig, r + 64)) return -10; } else m->exitTrig.kind = -1;
  }
  off[nr] = (unsigned)n;   // блобы подряд до конца файла
  for (unsigned i = 0; i < nr; i++) if (off[i] < tab || (off[i] & 3) || off[i] >= off[i + 1]) return -6;
  for (unsigned i = 0; i < nd; i++) {
    const unsigned char *d = b + 16 + (size_t)nr * rrec + (size_t)i * drec; RoomDoor *m = &R->door[i];
    memcpy(m->name, d, 32); m->name[31] = 0; memcpy(m->p, d + 32, 12); memcpy(&m->room, d + 44, 4);
    if (ver >= 1) memcpy(&m->h, d + 48, 4); else m->h = NAN;
    if (m->room < -1 || m->room >= (int)nr) return -8;
    if (!finite3(m->p) || isinf(m->h)) return -9;
    if (ver >= 2) { if (roomTrigRead(&m->trig, d + 64)) return -10; } else m->trig.kind = -1;
  }
  for (unsigned i = 0; i < nr; i++)
    if (colInit(&R->room[i].col, b + off[i], off[i + 1] - off[i])) { for (unsigned k = 0; k < i; k++) colFree(&R->room[k].col); memset(R, 0, sizeof *R); return -7; }
  R->nroom = (int)nr; R->ndoor = (int)nd; R->mem = buf;
  return 0;
}

void roomStateInit(RoomState *s) { s->room = -1; s->lastDoor = -1; s->doorArmed = 1; s->exitArmed = 0; }

const char *roomsName(const Rooms *R, const RoomState *s) { return s->room >= 0 && s->room < R->nroom ? R->room[s->room].name : 0; }

int roomsStep(const Rooms *R, RoomState *s, Game *G, int (*canEnter)(void *u, int room), void *u) {
  if (!R->nroom || !*G->pHaveHomer || !gameOnFoot(G)) return ROOM_EV_NONE;
  Homer *H = G->pHomer;
  if (s->room < 0) {
    int near = 0;   // Гомер в триггере какой-нибудь двери (без триггера — ближе ROOM_DOOR_REARM): взвод не возвращается
    for (int i = 0; i < R->ndoor; i++) {
      const RoomDoor *d = &R->door[i]; float dd = hypotf(H->x - d->p[0], H->z - d->p[2]);
      int tr = d->trig.kind >= 0, in = tr ? roomTrigIn(&d->trig, H->x, H->y, H->z, HOMER_RADIUS) : dd < ROOM_DOOR_R && fabsf(H->y - d->p[1]) < 3.f;
      if (tr ? in : dd <= ROOM_DOOR_REARM) near = 1;
      if (s->doorArmed && d->room >= 0 && d->room < R->nroom && in && (!s->needAction || s->action)) {   // дверь в незагруженную комнату — не вход; по △ (правка 41)
        if (canEnter && !canEnter(u, d->room)) { s->doorArmed = 0; return ROOM_EV_NONE; }   // не открыть — остаётся на улице
        const Room *r = &R->room[d->room]; s->room = d->room; s->lastDoor = i; s->exitArmed = 0; G->pHomerWorld = &r->col;
        homerPlace(H, &r->col, r->start[0], r->start[1], r->start[2], r->start[3]);
        return ROOM_EV_ENTER;
      }
    }
    if (!s->doorArmed && !near) s->doorArmed = 1;   // от двери отошёл — снова вход
  } else if (s->room < R->nroom) {
    const Room *r = &R->room[s->room]; float dx = hypotf(H->x - r->exit[0], H->z - r->exit[2]);
    int tr = r->exitTrig.kind >= 0, in = tr ? roomTrigIn(&r->exitTrig, H->x, H->y, H->z, HOMER_RADIUS) : dx < ROOM_EXIT_R;
    if (!s->exitArmed && (tr ? !in : dx > ROOM_EXIT_ARM)) s->exitArmed = 1;
    if (s->exitArmed && in && (!s->needAction || s->action)) {   // выход: к той же двери, вход снова только когда отойдёт; по △ (правка 41)
      const RoomDoor *d = &R->door[s->lastDoor >= 0 && s->lastDoor < R->ndoor ? s->lastDoor : 0];
      s->room = -1; G->pHomerWorld = 0; s->doorArmed = 0;
      homerPlace(H, G->pWorld, d->p[0], d->p[1], d->p[2], isnan(d->h) ? H->h + 3.14159265f : d->h);   // курс наружу из данных двери
      return ROOM_EV_EXIT;
    }
  }
  return ROOM_EV_NONE;
}

int roomsDoorNear(const Rooms *R, const RoomState *s, const Game *G) {   // те же триггеры, что у roomsStep
  if (!R->nroom || !*G->pHaveHomer || !gameOnFoot(G)) return 0;
  const Homer *H = G->pHomer;
  if (s->room < 0) {
    if (!s->doorArmed) return 0;
    for (int i = 0; i < R->ndoor; i++) {
      const RoomDoor *d = &R->door[i];
      if (d->room < 0 || d->room >= R->nroom) continue;
      int in = d->trig.kind >= 0 ? roomTrigIn(&d->trig, H->x, H->y, H->z, HOMER_RADIUS)
                                 : hypotf(H->x - d->p[0], H->z - d->p[2]) < ROOM_DOOR_R && fabsf(H->y - d->p[1]) < 3.f;
      if (in) return 1;
    }
    return 0;
  }
  if (s->room >= R->nroom || !s->exitArmed) return 0;
  const Room *r = &R->room[s->room];
  return r->exitTrig.kind >= 0 ? roomTrigIn(&r->exitTrig, H->x, H->y, H->z, HOMER_RADIUS) : hypotf(H->x - r->exit[0], H->z - r->exit[2]) < ROOM_EXIT_R;
}

int roomsSpotTarget(const Rooms *R, int curRoom, int (*spot)(int i, float *out4), float px, float py, float pz, float out[3]) {
  float best = 1e30f; int found = 0; float sp[4];
  for (int i = 0; spot && spot(i, sp); i++) {
    int room = -1; float g, n[3];
    for (int k = 0; k < R->nroom && room < 0; k++) if (colGround(&R->room[k].col, sp[0], sp[2], sp[1] + 1.5f, sp[1] - 3.f, &g, n)) room = k;
    if (room < 0) continue;
    float t[3], d;
    if (room == curRoom) { t[0] = sp[0]; t[1] = sp[1]; t[2] = sp[2]; d = hypotf(px - sp[0], pz - sp[2]); }
    else {
      int dr = -1; float bd = 1e30f;
      for (int j = 0; j < R->ndoor; j++) if (R->door[j].room == room) { float dd = hypotf(px - R->door[j].p[0], pz - R->door[j].p[2]); if (dd < bd) { bd = dd; dr = j; } }
      if (dr < 0) continue;
      memcpy(t, R->door[dr].p, sizeof t); d = bd;
    }
    if (d < best) { best = d; memcpy(out, t, sizeof t); found = 1; }
  }
  (void)py; return found;
}
