// Камеры разговора — см. convcam.h. Чистый C99.
#include <string.h>
#include <math.h>
#include "convcam.h"

// ПРАВИЛО ПОРТА (кадры записи PS2, tools/convcam_fit.py; вертикальный FOV кадра 4:3 — 40°, в кадре 16:9 Hor+):
//   дальний план: глаз за «передним» (тот, кто НЕ говорит) на FAR_BACK м по оси, на FAR_SIDE м в лучшую сторону, на высоте
//   FAR_H над его ногами; взгляд — на FAR_K расстояния от переднего к говорящему, на высоте FAR_HT;
//   крупный план: то же с NEAR_* (голова переднего — на краю кадра, говорящий по колено); высоты — по лицу говорящего.
#define CONV_FOVY 40.f
#define FAR_BACK 1.94f
#define FAR_SIDE 4.57f
#define FAR_H 2.16f
#define FAR_K 0.48f
#define FAR_HT 1.09f
#define NEAR_BACK 1.36f
#define NEAR_SIDE 0.42f
#define NEAR_H 1.91f
#define NEAR_K 0.19f
#define NEAR_HT 1.42f
#define FACE_DEF 1.5f   // лицо Гомера: сустав Head 1.42 м + 0.08

static const char *const names[] = {"", "npc_far", "npc_near", "pc_far", "pc_near"};
static int ieq(const char *a, const char *b) {
  for (; *a && *b; a++, b++) { char x = *a, y = *b; if (x >= 'A' && x <= 'Z') x += 32; if (y >= 'A' && y <= 'Z') y += 32; if (x != y) return 0; }
  return *a == *b;
}
int convShot(const char *name) {
  if (!name) return CONV_NONE;
  for (int i = 1; i < 5; i++) if (ieq(name, names[i])) return i;
  return CONV_NONE;
}
const char *convShotName(int shot) { return shot > 0 && shot < 5 ? names[shot] : "none"; }
int convShotOnPc(int shot) { return shot == CONV_PC_FAR || shot == CONV_PC_NEAR; }

int convShotFor(const char *const *cams, int ncam, int line, int pcSpeaks, int *fromData) {
  int shot = CONV_NONE;
  for (int i = 0; cams && i < ncam && i <= line; i++) { int s = convShot(cams[i]); if (s) shot = s; }
  if (fromData) *fromData = shot != CONV_NONE;
  if (shot) return shot;
  if (line <= 0) return CONV_NPC_FAR;                     // запись PS2 10:45 и 39:30: первая реплика — общий план
  return pcSpeaks ? CONV_PC_NEAR : CONV_NPC_NEAR;          // дальше — говорящий крупно
}

static float headOf(const ConvScene *s, int who) { float h = who ? s->npcHead : s->pcHead; return h > .05f ? h : FACE_DEF; }
int convSide(const ConvScene *s, const float prevEye[3]) {
  float ax = s->npc[0] - s->pc[0], az = s->npc[2] - s->pc[2], lx = az, lz = -ax;   // лево оси = up x a
  const float *p = s->hasBest ? s->best : prevEye;
  if (!p) return 1;
  float mx = (s->pc[0] + s->npc[0]) * .5f, mz = (s->pc[2] + s->npc[2]) * .5f;
  return (p[0] - mx) * lx + (p[2] - mz) * lz >= 0.f ? 1 : -1;
}
void convPose(const ConvScene *s, int shot, int side, float eye[3], float look[3], float *fovY) {
  int onPc = convShotOnPc(shot), near = shot == CONV_NPC_NEAR || shot == CONV_PC_NEAR;
  const float *F = onPc ? s->npc : s->pc, *S = onPc ? s->pc : s->npc;   // передний (слушает) и говорящий
  float ax = S[0] - F[0], az = S[2] - F[2], d = sqrtf(ax * ax + az * az);
  if (d < 1e-3f) { ax = 0.f; az = 1.f; d = 1e-3f; } else { ax /= d; az /= d; }
  float px = s->npc[0] - s->pc[0], pz = s->npc[2] - s->pc[2], pl = sqrtf(px * px + pz * pz);   // сторона — от оси игрок -> собеседник
  if (pl < 1e-3f) { px = 0.f; pz = 1.f; pl = 1.f; }
  float vx = pz / pl * (float)side, vz = -px / pl * (float)side;
  float back = near ? NEAR_BACK : FAR_BACK, sd = near ? NEAR_SIDE : FAR_SIDE, h = near ? NEAR_H : FAR_H, k = near ? NEAR_K : FAR_K, ht = near ? NEAR_HT : FAR_HT;
  if (near) {   // ребёнок / низкий говорящий: крупный план ниже (правило порта), взрослые — как у записи PS2
    float r = headOf(s, onPc ? 0 : 1) / FACE_DEF; if (r < .5f) r = .5f; if (r > 1.2f) r = 1.2f;
    ht *= r; h *= .35f + .65f * r;
  }
  eye[0] = F[0] - ax * back + vx * sd; eye[1] = F[1] + h; eye[2] = F[2] - az * back + vz * sd;
  look[0] = F[0] + ax * k * d; look[1] = F[1] + ht; look[2] = F[2] + az * k * d;
  *fovY = CONV_FOVY;
}
float convNear(const ConvScene *s, const float eye[3]) {
  float a = hypotf(eye[0] - s->pc[0], eye[2] - s->pc[2]), b = hypotf(eye[0] - s->npc[0], eye[2] - s->npc[2]);
  float n = (a < b ? a : b) - .5f;
  return n > .3f ? n : .3f;
}
void convFace(const ConvScene *s, int who, float out[3]) {
  const float *p = who ? s->npc : s->pc;
  out[0] = p[0]; out[1] = p[1] + headOf(s, who); out[2] = p[2];
}
int convProject(const float eye[3], const float look[3], float fovY, const float p[3], float *x, float *y, float *depth) {
  float f[3] = {look[0] - eye[0], look[1] - eye[1], look[2] - eye[2]}, fl = sqrtf(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]);
  if (fl < 1e-6f) return 0;
  for (int k = 0; k < 3; k++) f[k] /= fl;
  float r[3] = {-f[2], 0.f, f[0]}, rl = sqrtf(r[0] * r[0] + r[2] * r[2]);   // f x up
  if (rl < 1e-6f) return 0;
  r[0] /= rl; r[2] /= rl;
  float u[3] = {r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]};
  float q[3] = {p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]};
  float z = q[0] * f[0] + q[1] * f[1] + q[2] * f[2];
  if (depth) *depth = z;
  if (z <= 1e-4f) return 0;
  float t = tanf(fovY * .5f * 3.14159265f / 180.f);
  float xn = (q[0] * r[0] + q[1] * r[1] + q[2] * r[2]) / z / (t * 16.f / 9.f), yn = (q[0] * u[0] + q[1] * u[1] + q[2] * u[2]) / z / t;
  *x = .5f + .5f * xn; *y = .5f - .5f * yn;
  return 1;
}
