#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "audio.h"

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "Usage: %s <packdir/>\n", argv[0]);
    return 2;
  }
  char dir[512];
  snprintf(dir, sizeof dir, "%s%s", argv[1], argv[1][strlen(argv[1]) - 1] == '/' ? "" : "/");
  if (audioInit(dir) < 0) {
    fprintf(stderr, "audioInit failed: %s\n", audioError());
    return 2;
  }

  int track = audioTrack("simpsons_theme");
  if (track < 0) track = 0;
  audioMusic(track, 0);

  short pcm[512 * 2];
  // 1. Advance playback so music starts and streams
  for (int i = 0; i < 20; i++) {
    audioHostMix(pcm, 512);
  }

  AudioStats st;
  audioStats(&st);
  if (st.track[0] < 0) {
    fprintf(stderr, "FAIL: music failed to start (track[0] = %d)\n", st.track[0]);
    return 1;
  }
  printf("Music initial: track=%d pos=%.2fs fill=%d%%\n", st.track[0], st.trackPos[0], st.fill[0]);

  // 2. Simulate PSP sleep: power event suspend + invalidate file descriptors
  audioTestPwrEvent(0x00010000 /* PSP_POWER_CB_SUSPENDING */);
  audioTestSimulateFdInvalidate();

  for (int i = 0; i < 5; i++) {
    audioHostMix(pcm, 512);
  }

  // 3. Simulate PSP resume: power event resume
  audioTestPwrEvent(0x00040000 /* PSP_POWER_CB_RESUME_COMPLETE */);

  // 4. Mix buffers after resume - drain enough buffers to exceed initial ring buffer
  int nonZeroPcm = 0;
  for (int i = 0; i < 450; i++) {
    audioHostMix(pcm, 512);
    for (int k = 0; k < 512 * 2; k++) {
      if (pcm[k] != 0) nonZeroPcm++;
    }
  }

  audioStats(&st);
  printf("After resume (450 bufs): track[0]=%d pos=%.2fs nonZeroPcm=%d fill=%d%%\n",
         st.track[0], st.trackPos[0], nonZeroPcm, st.fill[0]);

  // If music died, st.track[0] will be -1 (stream stopped) and fill will be 0%
  if (st.track[0] < 0 || st.fill[0] == 0) {
    fprintf(stderr, "FAIL: music stopped/dead after sleep/resume! (track=%d, fill=%d%%)\n", st.track[0], st.fill[0]);
    return 1;
  }

  printf("PASS #560: music successfully resumed and continued streaming after PSP sleep\n");
  audioShutdown();
  return 0;
}
