#ifndef SHAR_FE_AUDIO_H
#define SHAR_FE_AUDIO_H
#define FE_AUDIO_FILE "fe_audio.sap"
/* Root owns menu clock/RNG. Select once, pass the SAME pair to both events:
 * 180: prepare two seconds before the gag; 181: start without reseeking.
 * index0 = Homer, segment0..4; indices1..7 ignore segment.
 * Load after sndInit, path is sibling fe_audio.sap. Callback signature is void.
 * PORT RULE: dialogue slot only in FE; a non-FE conversation is never replaced.
 * Free stops owned audio; the extra bank FD closes safely at audioShutdown. */
int feAudioLoad(const char *path);
void feAudioEvent(int event,int index,int segment);
void feAudioStop(void);
void feAudioFree(void);
const char *feAudioName(int index,int segment);
int feAudioPrepared(void);
int feAudioStatus(void); /* 1 accepted, 0 ignored, -1 missing/invalid, -2 busy/stale */
#endif
