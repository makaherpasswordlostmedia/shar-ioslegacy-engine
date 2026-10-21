// Real mixer regression: host one-pass helper must finish a looping track and stop it on -1.
#include <stdio.h>
#include <limits.h>
#include "audio.h"
int main(int argc, char **argv) {
  if (argc != 2 || audioInit(argv[1])) return 2;
  audioTestForceUnity(0);
  int chosen = -1; unsigned samples = UINT_MAX;
  for (int t = 0; t < audioTrackCount(); t++) {
    int loop, next, bus; unsigned ns, ls, le;
    audioTestTrackInfo(t, &loop, &next, &bus, &ns, &ls, &le);
    if (loop && next < 0 && ns && ns < samples) { chosen = t; samples = ns; }
  }
  if (chosen < 0) { puts("FAIL missing real looping track"); return 2; }
  short b[1024]; AudioStats s; int started = 0, ended = 0;
  unsigned max = (samples * 2 + 511) / 512 + 128;
  audioTestMusicOnce(chosen);
  for (unsigned k = 0; k < max; k++) {
    audioHostMix(b, 512); audioStats(&s);
    if (s.track[0] == chosen) started = 1;
    if (started && s.track[0] < 0) { ended = 1; break; }
  }
  int once = started && ended;
  audioMusic(chosen, 0);
  for (unsigned k = 0; k < max; k++) audioHostMix(b, 512);
  audioStats(&s); int loops = s.track[0] == chosen;
  audioTestMusicOnce(-1);
  for (unsigned k = 0; k < 128; k++) audioHostMix(b, 512);
  audioStats(&s); int stopped = s.track[0] < 0;
  printf("track=%s samples=%u once=%d normal_loop=%d stop=%d\n", audioTrackName(chosen), samples, once, loops, stopped);
  audioShutdown();
  puts(once && loops && stopped ? "PASS" : "FAIL once/loop/stop");
  return once && loops && stopped ? 0 : 1;
}
