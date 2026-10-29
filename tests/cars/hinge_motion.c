// Model motion is independent of a virtual COM offset and initial velocity.
#include <math.h>
#include "hinge_fixture.h"
static int checks, bad;
static float worstSpin, worstFirst;
static void compare(const CarVis *a, const CarVis *b, float *worst) {
  for (int j = 0; j < a->nhinge; j++) {
    float error = fabsf(a->th[j] - b->th[j]) + fabsf(a->thv[j] - b->thv[j]);
    if (error > *worst) *worst = error;
    checks++; if (!isfinite(error) || error > .00002f) bad++;
  }
}
int main(int argc, char **argv) {
  CarVis original;
  if (!hingeFixture(&original, argc > 1 ? argv[1] : "build/ship_stage/level.shr") || original.nhinge != 4) return 2;
  Car base = {0}; carDefaults(&base.p); base.q[0] = 1; base.damage = .8f;
  for (int hz = 30; hz <= 120; hz *= 2) {
    CarVis a = original, b = original;
    a.prevDamage = b.prevDamage = base.damage;
    for (int j = 0; j < a.nhinge; j++) {
      a.latched[j] = b.latched[j] = 0;
      a.th[j] = b.th[j] = a.hinge[j].max * .3f;
    }
    Car ca = base, cb = base;
    float lift = carModelLift(&ca, original.lift), dt = 1.f / hz;
    ca.com[1] = lift; cb.com[1] = lift - .85f;
    // Analytic rotation around a fixed model origin, omega_z=6 rad/s.
    // The offset COM has v=omega cross r; the physical model does not move.
    for (int frame = 0; frame < hz * 2; frame++) {
      float t = frame * dt, angle = 6.f * t, s = sinf(angle), c = cosf(angle);
      ca.q[0] = cb.q[0] = cosf(angle * .5f); ca.q[3] = cb.q[3] = sinf(angle * .5f);
      ca.w[2] = cb.w[2] = 6;
      ca.x = cb.x = lift * s; ca.y = cb.y = -lift * c;
      cb.vel[0] = .85f * 6.f * c; cb.vel[1] = .85f * 6.f * s;
      carVisUpdate(&a, &ca, NULL, dt); carVisUpdate(&b, &cb, NULL, dt);
      compare(&a, &b, &worstSpin);
    }
    // Creation and repair at constant velocity cannot manufacture an impact.
    for (int repair = 0; repair < 2; repair++) {
      a = b = original; ca = cb = base; cb.vel[0] = 20; cb.vel[2] = 10;
      if (repair) {
        carVisUpdate(&a, &ca, NULL, dt); carVisUpdate(&b, &cb, NULL, dt);
        carVisReset(&a); carVisReset(&b);
      }
      for (int frame = 0; frame < hz; frame++) {
        cb.x += cb.vel[0] * dt; cb.z += cb.vel[2] * dt;
        carVisUpdate(&a, &ca, NULL, dt); carVisUpdate(&b, &cb, NULL, dt);
        compare(&a, &b, &worstFirst);
      }
    }
    // A genuine acceleration still drives the hinges; ignoring every sample
    // would pass the invariance tests above but must fail this control.
    a = b = original; ca = cb = base;
    carVisUpdate(&a, &ca, NULL, dt); carVisUpdate(&b, &cb, NULL, dt);
    cb.vel[2] += 13.f * dt;
    carVisUpdate(&a, &ca, NULL, dt); carVisUpdate(&b, &cb, NULL, dt);
    float motion = 0; for (int j = 0; j < a.nhinge; j++) motion += fabsf(a.thv[j] - b.thv[j]);
    checks++; if (motion < .001f) bad++;
  }
  printf("%s checks=%d failures=%d virtual-COM error=%.9g first/repair error=%.9g\n", bad ? "FAIL" : "PASS", checks, bad, worstSpin, worstFirst);
  return !!bad;
}
