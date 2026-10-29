#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "audio.h"
#include "savegame.h"

// Stubs for collect/sp symbols referenced by unused svCapture/svApply in savegame.o
uint8_t collectCards(const void *c, int l) { (void)c; (void)l; return 0; }
uint64_t collectGags(const void *c, int l) { (void)c; (void)l; return 0; }
uint32_t collectWasps(const void *c, int l) { (void)c; (void)l; return 0; }
void collectSetProgress(void *c, int l, uint8_t cards, uint32_t wasps, uint64_t gags) { (void)c; (void)l; (void)cards; (void)wasps; (void)gags; }
int spOnceOld = 0;
int spOnce(const StateProps *sp, unsigned i) { (void)sp; (void)i; return -1; }
void spRestore(StateProps *sp, unsigned i, int s) { (void)sp; (void)i; (void)s; }

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

  // 1. Setup music (stream 0) and ambience (stream 1)
  int tMusic = audioTrack("simpsons_theme");
  if (tMusic < 0) tMusic = 0;
  audioMusic(tMusic, 0);

  int tAmb = audioTrack("amb_suburbs_day");
  if (tAmb < 0) tAmb = 144;
  if (tAmb >= audioTrackCount()) tAmb = 0;
  audioAmbience(tAmb, 0);

  // 2. Setup engine motor (resident voice loop in RAM)
  audioEngine(60.f, 120.f, 0.8f, AUDIO_ENGINE_ON);

  // 3. Trigger resident SFX
  int crashId = audioFind("medium_car_crash");
  if (crashId < 0) crashId = audioFind("skid");
  if (crashId >= 0) audioPlay(crashId, 1.f, 0.f, 1.f);

  // 4. Create and serialize a pre-sleep savegame
  SaveGame s1, s2;
  svClear(&s1);
  s1.level = 2;
  s1.msnLevel = 2;
  s1.coins = 750;
  s1.seq = 101;
  s1.cards[1] = 0x7f;
  s1.msnCompleted = 0x1f;
  uint8_t saveBuf[SV_BYTES];
  int w = svWrite(&s1, saveBuf);
  if (w != SV_BYTES) {
    fprintf(stderr, "FAIL: svWrite failed (bytes=%d)\n", w);
    return 1;
  }
  char savePath[256];
  snprintf(savePath, sizeof savePath, "/tmp/test_save_psp_%d.bin", getpid());
  FILE *sf = fopen(savePath, "wb");
  if (!sf || fwrite(saveBuf, 1, SV_BYTES, sf) != SV_BYTES) {
    fprintf(stderr, "FAIL: could not write savegame to file\n");
    return 1;
  }
  fclose(sf);

  short pcm[512 * 2];
  // 5. Initial playback advance before sleep
  for (int i = 0; i < 25; i++) {
    audioHostMix(pcm, 512);
  }

  AudioStats st;
  audioStats(&st);
  printf("Initial: music=%d (fill=%d%%), amb=%d (fill=%d%%), engineVol=%.2f, voices=%d\n",
         st.track[0], st.fill[0], st.track[1], st.fill[1], st.engineVol, st.voices);

  if (st.track[0] < 0 || st.track[1] < 0 || st.voices <= 0) {
    fprintf(stderr, "FAIL: initial audio setup did not activate all subsystems!\n");
    unlink(savePath);
    return 1;
  }

  // 6. Simulate PSP sleep: power event suspend + invalidate file descriptors on ms0:
  audioTestPwrEvent(0x00010000 /* PSP_POWER_CB_SUSPENDING */);
  audioTestSimulateFdInvalidate();

  for (int i = 0; i < 5; i++) {
    audioHostMix(pcm, 512);
  }

  // 7. Simulate PSP wake / resume
  audioTestPwrEvent(0x00040000 /* PSP_POWER_CB_RESUME_COMPLETE */);

  // 8. Mix 450 buffers after resume (~5.2 seconds, drains ring buffer if not refilled)
  int nonZeroPcm = 0;
  for (int i = 0; i < 450; i++) {
    audioHostMix(pcm, 512);
    for (int k = 0; k < 512 * 2; k++) {
      if (pcm[k] != 0) nonZeroPcm++;
    }
  }

  audioStats(&st);
  printf("After resume (450 bufs): music=%d (fill=%d%%), amb=%d (fill=%d%%), engineVol=%.2f, voices=%d, nonZeroPcm=%d\n",
         st.track[0], st.fill[0], st.track[1], st.fill[1], st.engineVol, st.voices, nonZeroPcm);

  // 9. Verify audio subsystems survived sleep/resume
  int audioOk = 1;
  if (st.track[0] < 0 || st.fill[0] == 0) {
    fprintf(stderr, "FAIL: music died after sleep! (track[0]=%d, fill[0]=%d%%)\n", st.track[0], st.fill[0]);
    audioOk = 0;
  }
  if (st.track[1] < 0 || st.fill[1] == 0) {
    fprintf(stderr, "FAIL: ambience died after sleep! (track[1]=%d, fill[1]=%d%%)\n", st.track[1], st.fill[1]);
    audioOk = 0;
  }
  if (st.engineVol <= 0.f || st.voices <= 0) {
    fprintf(stderr, "FAIL: motor engine voices died after sleep! (engineVol=%.2f, voices=%d)\n", st.engineVol, st.voices);
    audioOk = 0;
  }
  if (nonZeroPcm == 0) {
    fprintf(stderr, "FAIL: output PCM was completely silent after resume!\n");
    audioOk = 0;
  }

  // 10. Verify savegame integrity across sleep/resume
  FILE *rf = fopen(savePath, "rb");
  if (!rf) {
    fprintf(stderr, "FAIL: could not reopen savegame file after sleep\n");
    return 1;
  }
  uint8_t readBuf[SV_BYTES];
  size_t rd = fread(readBuf, 1, SV_BYTES, rf);
  fclose(rf);
  unlink(savePath);

  if (rd != SV_BYTES) {
    fprintf(stderr, "FAIL: savegame file size corrupted (read %zu vs %d)\n", rd, SV_BYTES);
    return 1;
  }

  int r = svRead(readBuf, SV_BYTES, &s2);
  if (r != SV_OK) {
    fprintf(stderr, "FAIL: svRead returned %d (damaged save!)\n", r);
    return 1;
  }

  if (s2.level != s1.level || s2.coins != s1.coins || s2.cards[1] != s1.cards[1] || s2.seq != s1.seq) {
    fprintf(stderr, "FAIL: savegame field mismatch: level %d vs %d, coins %d vs %d, seq %d vs %d\n",
            s2.level, s1.level, s2.coins, s1.coins, s2.seq, s1.seq);
    return 1;
  }

  if (!audioOk) {
    return 1;
  }

  printf("PASS: All subsystems (music, ambience, engine motor, sfx voices, savegame) survived PSP sleep/resume!\n");
  audioShutdown();
  return 0;
}
