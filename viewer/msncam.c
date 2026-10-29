// Камеры старта миссий — см. msncam.h. Чистый C99.
#include <string.h>
#include <math.h>
#include "msncam.h"

static unsigned u32(const unsigned char *b) { unsigned v; memcpy(&v, b, 4); return v; }

int msncamParse(MsnCam *out, int max, const unsigned char *b, unsigned size) {
  if (size < 16 || memcmp(b, "MCM1", 4)) return -1;
  unsigned n = u32(b + 4);
  if (n > (unsigned)max || 16 + 64ull * n > size) return -1;
  for (unsigned i = 0; i < n; i++) {
    const unsigned char *r = b + 16 + 64 * i; MsnCam *c = &out[i];
    memcpy(c->name, r, 32); c->name[31] = 0; memcpy(&c->mission, r + 32, 4); c->nfr = u32(r + 36); memcpy(&c->fps, r + 40, 4);
    unsigned off = u32(r + 44);
    if (!c->nfr || c->nfr > 10000 || !(c->fps > 1.f && c->fps < 240.f) || (off & 3) || off + 40ull * c->nfr > size) return -1;
    c->fr = (const float *)(b + off);
    memcpy(c->phase, r + 48, 16); c->phase[15] = 0;
    if (!c->phase[0] && c->mission >= 0 && c->mission < 100) {   // версия 1: фаза по номеру миссии
      c->phase[0] = 'm'; int k = 1; if (c->mission >= 10) c->phase[k++] = (char)('0' + c->mission / 10);
      c->phase[k++] = (char)('0' + c->mission % 10); c->phase[k++] = 's'; c->phase[k++] = 'd'; c->phase[k] = 0;
    }
  }
  return (int)n;
}

static int ieq(const char *a, const char *b) {
  for (; *a && *b; a++, b++) { char x = *a, y = *b; if (x >= 'A' && x <= 'Z') x += 32; if (y >= 'A' && y <= 'Z') y += 32; if (x != y) return 0; }
  return *a == *b;
}
const MsnCam *msncamFind(const MsnCam *c, int n, const char *phase, const char *cam) {
  if (!phase) return 0;
  for (int i = 0; i < n; i++) if (ieq(c[i].phase, phase)) return !cam || ieq(c[i].name, cam) ? &c[i] : 0;
  return 0;
}

int msncamPose(const MsnCam *c, float t, float eye[3], float look[3], float up[3], float *fovY) {
  float f = t * c->fps; int last = (int)c->nfr - 1, going = f < (float)last;
  if (f < 0.f) f = 0.f; if (f > (float)last) f = (float)last;
  int i = (int)f; if (i >= last) i = last > 0 ? last - 1 : 0;
  float u = last > 0 ? f - (float)i : 0.f;
  const float *a = c->fr + 10 * i, *b = c->fr + 10 * (last > 0 ? i + 1 : i);
  float L[3], U[3], ll = 0.f, ul = 0.f;
  for (int k = 0; k < 3; k++) {
    eye[k] = a[k] + (b[k] - a[k]) * u; L[k] = a[3 + k] + (b[3 + k] - a[3 + k]) * u; U[k] = a[6 + k] + (b[6 + k] - a[6 + k]) * u;
    ll += L[k] * L[k]; ul += U[k] * U[k];
  }
  ll = ll > 1e-12f ? 1.f / sqrtf(ll) : 0.f; ul = ul > 1e-12f ? 1.f / sqrtf(ul) : 0.f;
  for (int k = 0; k < 3; k++) { look[k] = eye[k] + L[k] * ll; up[k] = U[k] * ul; }
  float fov = a[9] + (b[9] - a[9]) * u;
  *fovY = 2.f * atanf(tanf(fov * .5f) * .75f) * (180.f / 3.14159265f);
  return going;
}
