#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ticket_view.h"
#include "audio.h"
#include "sound.h"
static int track(void *u,const char *n){(void)u;return audioTrack(n);}
static float seconds(void *u,int t){(void)u;return audioTrackSeconds(t);}
static void play(void *u,int t){(void)u;sndVoice(t);}
static int playing(void *u,int t){(void)u;return sndVoicePlaying(t);}
static void mode(void *u,int on){TicketView *v=u;if(on){v->savedMode=sndModeCur();sndMode(SND_MODE_DIALOGUE);}else sndMode(v->savedMode);}
static void logVoice(void *u,const char *s){TicketView *v=u;if(v->log)v->log(s);}
static MsnAudioBackend backend;
int ticketViewLoad(TicketView *v,const char *path,void (*log)(const char *)){
 if(v->pack){ticketViewSkip(v);free(v->pack);}v->pack=0;v->route=0;v->voice=0;v->nr=v->nv=0;v->log=log;
 backend=(MsnAudioBackend){v,track,seconds,play,playing,0,0,mode,logVoice,0};msnAudioInit(&v->audio,&backend);
 FILE *f=fopen(path,"rb");if(!f)return 0;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
 if(n<16||n>65536){fclose(f);return -1;}
 void *b=malloc((size_t)n);if(!b||fread(b,1,n,f)!=(size_t)n){free(b);fclose(f);return -1;}fclose(f);
 uint32_t *h=b;unsigned nr=h[2],nv=h[3];
 if(memcmp(b,"TKT1",4)||h[1]!=1||nr!=2||nv!=7||16+nr*sizeof(TicketRoute)+nv*sizeof(TicketVoice)!=(size_t)n){free(b);return -1;}
 v->pack=b;v->nr=nr;v->nv=nv;v->route=(TicketRoute*)((char*)b+16);v->voice=(TicketVoice*)(v->route+nr);return 1;
}
void ticketViewNewGame(TicketView *v){ticketViewSkip(v);memset(&v->st,0,sizeof v->st);}
int ticketViewBusy(const TicketView *v){return !TICKET_CONTENT_C3_OLD&&v->audio.active;}
void ticketViewSkip(TicketView *v){if(v->audio.active)msnAudioStopVoice(&v->audio);}
void ticketViewTick(TicketView *v,Collect *c,float dt){if(c)c->st.ticketFlags=v->st.flags;msnAudioTick(&v->audio,dt,1,-1);}
int ticketViewAction(TicketView *v,Collect *c,int gag){
 if(TICKET_CONTENT_C3_OLD||!v->pack||v->audio.active||gag<0)return 0;
 const TicketRoute *r=0;for(unsigned i=0;i<v->nr;i++)if(v->route[i].gag==(unsigned)gag)r=&v->route[i];
 if(!r||r->kind!=c->gag[gag].pad)return 0;
 TicketDecision d=ticketAction(&v->st,r,c->st.cards);c->st.ticketFlags=v->st.flags;
 if(v->log){char s[160];snprintf(s,sizeof s,"TICKET kind=%u gag=%d dialogue=%s movie=%d flags=%u\n",r->kind,gag,d.dialogue?d.dialogue:"-",d.movie,v->st.flags);v->log(s);}
 if(d.dialogue){
  MsnDialogue a;memset(&a,0,sizeof a);a.name=d.dialogue;a.pc=r->pc;a.npc=r->npc;
  for(unsigned i=0;i<v->nv;i++)if(!strcmp(v->voice[i].conv,d.dialogue)){a.file[0]=v->voice[i].file;a.actor[0]=v->voice[i].actor;a.nlines=1;break;}
  if(!a.nlines){/* Four original Aztec reject variants; fixed round-robin is a port selection policy. */
   unsigned k=v->st.variant++%4;char name[40];snprintf(name,sizeof name,"%s%u",d.dialogue,k+1);
   for(unsigned i=0;i<v->nv;i++)if(!strcmp(v->voice[i].conv,name)){a.file[0]=v->voice[i].file;a.actor[0]=v->voice[i].actor;a.nlines=1;break;}
  }
  if(a.nlines)msnAudioDialogue(&v->audio,&a,1);
 }
 return d.movie;
}
