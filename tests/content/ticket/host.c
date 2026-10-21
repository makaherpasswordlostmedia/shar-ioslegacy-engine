/* Real authored action radius -> collect event -> ticket/voice/movie decision -> real SaveGame bytes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ticket_view.h"
#include "audio.h"
#include "sound.h"
static Collect C;static TicketView V;static int fails;static unsigned checks;
static void check(const char *name,int pass){checks++;fails+=!pass;printf("CHECK %s %s\n",name,pass?"PASS":"FAIL");}
static void logger(const char*s){printf("%s",s);}
static void *readfile(const char *fn,size_t *n){FILE*f=fopen(fn,"rb");if(!f)return 0;fseek(f,0,SEEK_END);*n=ftell(f);rewind(f);void*b=malloc(*n);fread(b,1,*n,f);fclose(f);return b;}
static int gag(int kind){for(unsigned i=0;i<C.ngag;i++)if(C.gag[i].pad==kind)return i;return -1;}
static void clearq(void){CollEvent e;while(collectPop(&C,&e)){};}
static int fire(int kind,int allowed){
 ticketViewSkip(&V);int i=gag(kind);if(i<0){check("authored-gag",0);return 0;}
 const CollGag*g=&C.gag[i];CollPlayer p={g->tx,g->ty,g->tz,1,g->room,0};
 collectStep(&C,&p,0,0,0,0,1.f/60.f);clearq();check("nearest-action",(collectWantsAction(&C)==i)==allowed);
 p.action=1;collectStep(&C,&p,0,0,0,0,1.f/60.f);CollEvent e;int seen=0,movie=0;
 while(collectPop(&C,&e))if(e.type==CE_TICKET&&e.idx==i){seen++;movie=ticketViewAction(&V,&C,e.idx);}
 check("conditional-event",seen==allowed);return movie;
}
static void heard(const char *name){
 check(name,V.audio.active&&V.audio.nlines==1&&!strcmp(V.audio.conv,name)&&V.audio.voiced>0&&V.audio.missing==0);
 int t=V.audio.track;check("original-voice-stream",t>=0&&audioTrackBus(t)==2);
 short pcm[4096*2];double sum=0;for(int k=0;k<12;k++){audioHostMix(pcm,4096);for(unsigned j=0;j<sizeof pcm/sizeof pcm[0];j++)sum+=(double)pcm[j]*pcm[j];}
 check("mixer-output",sum>0);
}
int main(int argc,char **argv){
 if(argc!=4)return 2;setvbuf(stdout,0,_IONBF,0);size_t n;void*b=readfile(argv[1],&n);
 if(!b||collectInit(&C,b,n)||ticketViewLoad(&V,argv[2],logger)!=1||sndInit(argv[3]))return 2;
 check("authoring-level3",C.level==3);int cg=gag(1),mg=gag(2);check("two-distinct-routes",cg>=0&&mg>=0&&cg!=mg);
 if(cg<0||mg<0)return 1;
 const CollGag*g=&C.gag[cg];CollPlayer p={g->tx+g->tr+.05f,g->ty,g->tz,1,g->room,0};
 collectStep(&C,&p,0,0,0,0,1.f/60.f);check("outside-radius",collectWantsAction(&C)!=cg);
 p.x=g->tx;p.onFoot=0;collectStep(&C,&p,0,0,0,0,1.f/60.f);check("in-car-no-action",collectWantsAction(&C)!=cg);
 p.onFoot=1;p.room=-1;collectStep(&C,&p,0,0,0,0,1.f/60.f);check("wrong-room-no-action",collectWantsAction(&C)!=cg);
 check("movie-before-ticket-reject",!fire(2,1));heard("aztec");
 C.st.cards[3]=127;fire(1,1);heard("rewardintro");check("seven-L3-not-enough",!(V.st.flags&TICKET_OWNED));
 fire(1,1);heard("rewardfail");
 for(int i=1;i<=7;i++)C.st.cards[i]=127;C.st.cards[7]=126;
 fire(1,1);heard("rewardfail");check("48-not-enough",!(V.st.flags&TICKET_OWNED));
 C.st.cards[7]=127;fire(1,1);heard("rewardsuccess");check("49-reward-ticket-before-movie",(V.st.flags&(TICKET_OWNED|TICKET_ADMIT))==(TICKET_OWNED|TICKET_ADMIT));
 fire(1,0);check("no-repeat-reward",!V.audio.active);
 check("movie-after-ticket",fire(2,1));check("no-reject-on-admission",!V.audio.active);
 SaveGame save,restored;svClear(&save);ticketSave(&V.st,&save);uint8_t blob[SV_BYTES];
 check("save-write",svWrite(&save,blob)==SV_BYTES);check("save-read",svRead(blob,SV_BYTES,&restored)==SV_OK);
 ticketViewNewGame(&V);ticketRestore(&V.st,&restored);C.st.ticketFlags=V.st.flags;memset(C.st.cards,0,sizeof C.st.cards);
 check("ticket-persisted",(V.st.flags&(TICKET_OWNED|TICKET_ADMIT))==(TICKET_OWNED|TICKET_ADMIT));check("saved-admission-without-current-cards",fire(2,1));
 ticketViewNewGame(&V);C.st.ticketFlags=0;check("newgame-clears-ticket",!V.st.flags);check("newgame-movie-reject",!fire(2,1));heard("aztec");
 memset(&restored,0,sizeof restored);ticketRestore(&V.st,&restored);check("legacy-zero-no-ticket",!V.st.flags);
 sndShutdown();printf("RESULT %s failures=%d checks=%u\n",fails?"FAIL":"PASS",fails,checks);return !!fails;
}
