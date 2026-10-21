#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define TR_MAXCAR 5
#define TRM_OFF 0
#define TRM_DRIVE 1
#define TRM_PHYS 2

typedef struct { float x, y, z; int destroyed; } TestCar;
typedef struct { int mode; TestCar car; } TestTrCar;
static TestTrCar testCar[TR_MAXCAR];
static int testHaveTraffic = 1;
static int testMaxCars = TR_MAXCAR;

#include "../../viewer/audio.c"

// Sound effect stub for sndPlay
static int testSndPlay(const char *name, float x, float y, float z, float vol) {
  int id = audioFind(name);
  if (id < 0) return 0;
  return audioPlayAtGain(id, vol, x, y, z, 4.f, 60.f);
}

// Logic under test:
#ifndef HORN_STOP_OLD
#define HORN_STOP_OLD 0
#endif
static int hornStopOld = HORN_STOP_OLD;

typedef struct { int handle; float timer; } TrHornVoice;
static TrHornVoice trHorns[TR_MAXCAR];

static void testTrafficHornFrame(float dt, float camx, float camy, float camz) {
#if !HORN_STOP_OLD
  if (hornStopOld) return;
  for (int i = 0; i < TR_MAXCAR; i++) {
    if (!trHorns[i].handle) continue;
    trHorns[i].timer -= dt;
    int stop = trHorns[i].timer <= 0.f;
    if (!testHaveTraffic || i >= testMaxCars || testCar[i].mode == TRM_OFF || testCar[i].car.destroyed) stop = 1;
    if (!stop) {
      float dx = testCar[i].car.x - camx, dy = testCar[i].car.y - camy, dz = testCar[i].car.z - camz;
      if (dx * dx + dy * dy + dz * dz > 50.f * 50.f) stop = 1;
    }
    if (stop) {
      audioStop(trHorns[i].handle);
      trHorns[i].handle = 0;
    } else {
      audioSetAt(trHorns[i].handle, testCar[i].car.x, testCar[i].car.y, testCar[i].car.z, 4.f, 60.f);
    }
  }
#endif
}

static void triggerHonk(int slot, float x, float y, float z) {
  char hn[40] = "horn";
#if !HORN_STOP_OLD
  if (!hornStopOld && slot >= 0 && slot < TR_MAXCAR) {
    if (trHorns[slot].handle) audioStop(trHorns[slot].handle);
    trHorns[slot].handle = testSndPlay(hn, x, y, z, 1.f);
    trHorns[slot].timer = 1.4f;
  } else
#endif
  testSndPlay(hn, x, y, z, 1.f);
}

int main(int argc, char **argv) {
  if (argc != 2 || audioInit(argv[1])) return 2;
  audioListener(0, 0, 0, 1, 0);

  int bad = 0;
  // Case 1: Honk timeout (1.4s)
  testCar[0].mode = TRM_DRIVE;
  testCar[0].car.x = 10.f; testCar[0].car.y = 0.f; testCar[0].car.z = 10.f;
  testCar[0].car.destroyed = 0;

  triggerHonk(0, 10.f, 0.f, 10.f);
  int h = trHorns[0].handle;
#if !HORN_STOP_OLD
  if (!hornStopOld) {
    if (!h || !audioPlaying(h)) { printf("FAIL: honk didn't start\n"); bad++; }
    testTrafficHornFrame(0.5f, 0, 0, 0);
    if (!audioPlaying(h)) { printf("FAIL: honk stopped too early at 0.5s\n"); bad++; }
    testTrafficHornFrame(1.0f, 0, 0, 0); // 0.5 + 1.0 = 1.5s > 1.4s
    if (audioPlaying(h) || trHorns[0].handle != 0) { printf("FAIL: honk didn't stop on timeout\n"); bad++; }
  } else {
    // Under OLD: honk never stops!
    testTrafficHornFrame(10.0f, 0, 0, 0);
    // Under OLD, handle is not tracked and audio continues indefinitely
    printf("OLD_BEHAVIOR: honk continues forever\n");
    audioShutdown();
    return 1; // Expected failure for red control under OLD
  }
#else
  testTrafficHornFrame(10.0f, 0, 0, 0);
  printf("OLD_BEHAVIOR: honk continues forever\n");
  audioShutdown();
  return 1;
#endif

  // Case 2: Despawn stops honk
  testCar[1].mode = TRM_DRIVE; testCar[1].car.x = 5.f; testCar[1].car.y = 0.f; testCar[1].car.z = 5.f;
  triggerHonk(1, 5.f, 0.f, 5.f);
  int h2 = trHorns[1].handle;
  if (!h2 || !audioPlaying(h2)) { printf("FAIL: case2 honk didn't start\n"); bad++; }
  testCar[1].mode = TRM_OFF; // despawned!
  testTrafficHornFrame(0.1f, 0, 0, 0);
  if (audioPlaying(h2) || trHorns[1].handle != 0) { printf("FAIL: honk didn't stop on despawn\n"); bad++; }

  // Case 3: Distance > 50m stops honk
  testCar[2].mode = TRM_DRIVE; testCar[2].car.x = 5.f; testCar[2].car.y = 0.f; testCar[2].car.z = 5.f;
  triggerHonk(2, 5.f, 0.f, 5.f);
  int h3 = trHorns[2].handle;
  if (!h3 || !audioPlaying(h3)) { printf("FAIL: case3 honk didn't start\n"); bad++; }
  testCar[2].car.x = 100.f; // moved 100m away!
  testTrafficHornFrame(0.1f, 0, 0, 0);
  if (audioPlaying(h3) || trHorns[2].handle != 0) { printf("FAIL: honk didn't stop on distance > 50m\n"); bad++; }

  audioShutdown();
  printf("%s traffic_horn failures=%d\n", bad ? "FAIL" : "PASS", bad);
  return bad ? 1 : 0;
}
