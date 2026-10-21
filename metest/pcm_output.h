#pragma once
#ifndef PCM_OUTPUT_BUFFERS
#define PCM_OUTPUT_BUFFERS 2
#endif
// sceAudioOutputBlocking queues a pointer; a returned buffer is still in use
typedef struct {short sample[PCM_OUTPUT_BUFFERS][512*2];unsigned next;} PcmOutput __attribute__((aligned(64)));
static short *pcmOutputBuffer(PcmOutput *p){return p->sample[p->next];}
static void pcmOutputQueued(PcmOutput *p){p->next=(p->next+1)%PCM_OUTPUT_BUFFERS;}
