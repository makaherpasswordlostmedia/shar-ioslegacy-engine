// Scripted sound test, shared by the PSP EBOOT (tests/sound/main.c) and the Mac render (tests/sound/host).
// 44 s: free-roam music, engine sweep through the gears + coast/brake/reverse, horn, skid, 3 crash sizes, every
// resident effect in turn, coins, Homer's feet/jump/land/stomp, Homer's lines, music states, ambience gates and
// the tire-fire positional loop. Coordinates: level 1 game space (spawn 220, 3.5, 172).
#include "sound.h"
#include "audio.h"
#include <math.h>

#define SCN_END 44.f
typedef struct { float v, px, py, pz, cx, cy, cz; int step, sfx, say, coins, feet; float next; } Scn;

static void scnPos(Scn *s, float x, float y, float z) { s->px = x; s->py = y; s->pz = z; s->cx = x - 6.8f; s->cy = y + 2.4f; s->cz = z; }

// returns 0 when finished
static int scenario(Scn *s, float t, float dt) {
  if (s->step == 0) {
    scnPos(s, 220.f, 3.5f, 172.f); sndCarSetup(33.3f); sndLevelStart(s->px, s->py, s->pz);
    sndMusic(SND_MUS_FREEROAM); s->step = 1; s->next = 14.f;
  }
  // car: 1-9 s gas, 9-11 coast, 11-12.2 brake, 12.2-13.5 reverse
  float thr = t > 1 && t < 9 ? 1.f : t > 12.2f && t < 13.5f ? .7f : 0.f;
  int rev = t > 12.2f && t < 13.5f;
  if (rev) s->v = s->v > -6.f ? s->v - 8.f * dt : s->v;
  else if (t > 11 && t < 12.2f) s->v = s->v > 0 ? s->v - 25.f * dt : 0;
  else if (t >= 13.5f && s->v < 0) s->v = fminf(0.f, s->v + 10.f * dt);
  else s->v += (thr * 10.f * (1 - s->v / 33.3f) - (s->v > 0 ? .8f : 0)) * dt;
  sndEngine(s->v, thr, SND_ENG_ON | (s->v < 0 ? SND_ENG_REVERSE : 0) | (t > 9 && t < 11 ? SND_ENG_DAMAGED : 0));
  sndHorn(t > 9.5f && t < 10.2f);
  sndSkid(t > 10.3f && t < 11.2f ? .8f : 0.f, t > 10.8f);
  sndCarAir(t > 7.f && t < 7.8f);
  if (s->step == 1 && t > 7.8f) { sndCarLand(9.f); s->step = 2; }
  if (s->step == 2 && t > 13.6f) { sndCarHit(3.f, s->px + 2, s->py, s->pz); s->step = 3; }
  if (s->step == 3 && t > 14.0f) { sndCarHit(8.f, s->px - 2, s->py, s->pz); s->step = 4; }   // medium, may say mcrash
  if (s->step == 4 && t > 14.4f) { sndCarHit(15.f, s->px, s->py, s->pz + 2); s->step = 5; }  // large, may say bcrash
  // every resident effect in turn (loops are stopped after 0.3 s)
  static int h;
  if (t > 14.8f && t < 26.f && t >= s->next && s->sfx < audioSoundCount()) {
    if (h) sndStop(h);
    float side = (s->sfx % 3 - 1) * 8.f;
    h = sndPlayId(s->sfx, s->px + side, s->py, s->pz + 3.f, 1.f);
    s->sfx++; s->next = t + .17f;
  }
  if (t > 26.f && h) { sndStop(h); h = 0; }
  // pickups and Homer 26-29
  if (t > 26.2f && s->coins < 3 && t > 26.2f + s->coins * .25f) { sndCoin(); s->coins++; }
  if (s->step == 5 && t > 27.f) { sndCoinLose(s->px, s->py, s->pz); sndCarDoor(1); s->step = 6; }
  if (t > 27.3f && t < 29.f && s->feet < 8 && t > 27.3f + s->feet * .2f) { sndFootstep(s->feet / 2, s->px, s->py, s->pz); s->feet++; }
  if (s->step == 6 && t > 29.f) { sndJump(s->px, s->py, s->pz); s->step = 7; }
  if (s->step == 7 && t > 29.5f) { sndLand(SND_GROUND_DIRT, s->px, s->py, s->pz); sndStomp(s->px, s->py, s->pz); s->step = 8; }
  // Homer's lines (forced; the 5 s gap still applies) 29.6 / 35
  if (s->step == 8 && t > 29.6f) { sndSay(SND_SAY_DAMAGE, 1); s->step = 9; }
  // music states: on foot 30.5, mission 32, win 34 (-> free roam after the ending)
  if (s->step == 9 && t > 30.5f) { sndMusic(SND_MUS_ONFOOT); s->step = 10; }
  if (s->step == 10 && t > 32.f) { sndMusic(SND_MUS_MISSION); s->step = 11; }
  if (s->step == 11 && t > 34.f) { sndMusic(SND_MUS_MISSION_WIN); s->step = 12; }
  if (s->step == 12 && t > 35.f) { sndSay(SND_SAY_AIR, 1); sndCarExplode(s->px + 5, s->py, s->pz); s->step = 13; }
  // 36-40: drive through the suburbs -> country gates (game z -205 -> -225 at x 336), 40-44: at the tire fire
  if (t > 36.f && t < 40.f) scnPos(s, 336.f, 1.f, -205.f - (t - 36.f) * 5.f);
  if (t >= 40.f) scnPos(s, 286.75f + 40.f - (t - 40.f) * 8.f, 5.2f, -511.17f);
  return t < SCN_END;
}
