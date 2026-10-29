#ifndef TICKET_VIEW_H
#define TICKET_VIEW_H
#include "ticket.h"
#include "collect.h"
#include "msn_audio.h"
typedef struct { TicketState st; void *pack; TicketRoute *route; TicketVoice *voice; unsigned nr,nv; MsnAudio audio; int savedMode; void (*log)(const char *); } TicketView;
int ticketViewLoad(TicketView *v,const char *path,void (*log)(const char *));
void ticketViewNewGame(TicketView *v);
int ticketViewAction(TicketView *v,Collect *c,int gag); /* 1 -> play the authored gag FMV now */
void ticketViewTick(TicketView *v,Collect *c,float dt);
int ticketViewBusy(const TicketView *v);
void ticketViewSkip(TicketView *v);
#endif
