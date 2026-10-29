#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "skid.h"
#include "../../viewer/audio.c"

static int bad = 0;
#define CHECK(cond, msg) do { if (!(cond)) { bad++; printf("FAIL: %s (line %d)\n", msg, __LINE__); } } while(0)

int main(int argc, char **argv) {
  if (argc != 2 || audioInit(argv[1])) return 2;
  const SabCar *profiles = (const SabCar *)(bank + H->carOff);

  for (unsigned j = 0; j < H->ncar; j++) {
    const char *name = profiles[j].name;
    Car c = {0};
    carParamsFor(name, &c.p);
    c.q[0] = 1; c.grounded = 1; c.wheels = 4;
    audioPlayerCar(name);

    // 1. Standing still with brake held
    c.vel[0] = c.vel[1] = c.vel[2] = c.v = 0.f;
    CarInput inBrake = {0}; inBrake.brake = 1.0f;
    float lvlBrake = skidSoundLevel(&c, &inBrake);
#if !SKID_OLD
    CHECK(lvlBrake == 0.f, "standing still with brake must have skid level 0");
#else
    // Under OLD: returns 1.0f
    if (lvlBrake > 0.f) {
      printf("OLD RED CONTROL: standing still brake produced level %.2f\n", lvlBrake);
      audioShutdown();
      return 1; // Expected failure under OLD
    }
#endif

    // 2. Standing still on handbrake with full throttle
    CarInput inHb = {0}; inHb.handbrake = 1.0f; inHb.throttle = 1.0f;
    float lvlHb = skidSoundLevel(&c, &inHb);
#if !SKID_OLD
    CHECK(lvlHb == 0.f, "standing on handbrake with throttle must have skid level 0");
#endif

    // 3. Stalled against wall (sp = 0.15 m/s) with throttle
    c.vel[2] = 0.15f; c.v = 0.15f;
    CarInput inWall = {0}; inWall.throttle = 1.0f;
    float lvlWall = skidSoundLevel(&c, &inWall);
#if !SKID_OLD
    CHECK(lvlWall == 0.f, "stalled in wall with throttle must have skid level 0");
#endif

    // 4. Moving at 25% top speed and braking: skid must be active and <= 0.65
    c.vel[2] = c.p.topSpeed * 0.25f; c.v = c.vel[2];
    CarInput inMoveBrake = {0}; inMoveBrake.brake = 1.0f;
    float lvlMove = skidSoundLevel(&c, &inMoveBrake);
    int isSilent = car->skid < 0;
    if (!isSilent) {
      int id = car->skid;
      isSilent = R[id].nVar > 0;
      for (unsigned k = 0; k < R[id].nVar; k++)
        if (VAR[R[id].firstVar + k] != blankFile) isSilent = 0;
    }
    if (!isSilent) {
      CHECK(lvlMove > 0.f, "moving car with brake must produce skid sound");
      CHECK(lvlMove <= 0.66f, "skid sound volume must be scaled <= 0.65");
    }
  }

  audioShutdown();
  printf("%s skid562 failures=%d\n", bad ? "FAIL" : "PASS", bad);
  return bad ? 1 : 0;
}
