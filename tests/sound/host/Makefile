# Mac render of tests/sound (viewer/sound.c + viewer/audio.c with AUDIO_HOST)
CFLAGS ?= -O2 -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare -Wno-unused-function
V = ../../../viewer
sound_host: sound_host.c ../scenario.h $(V)/sound.c $(V)/sound.h $(V)/audio.c $(V)/audio.h
	$(CC) $(CFLAGS) -DAUDIO_HOST -I$(V) -o $@ sound_host.c $(V)/sound.c $(V)/audio.c -lm
clean:
	rm -f sound_host
