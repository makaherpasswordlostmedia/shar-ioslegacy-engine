# Mac build of the PSP audio runtime (viewer/audio.c with AUDIO_HOST) + test harness.
CFLAGS ?= -O2 -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare
audio_host: audio_host.c ../../../viewer/audio.c ../../../viewer/audio.h
	$(CC) $(CFLAGS) -DAUDIO_HOST -I../../../viewer -o $@ audio_host.c ../../../viewer/audio.c -lm
clean:
	rm -f audio_host
