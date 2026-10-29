#ifndef TICKET_H
#define TICKET_H
#include <stdint.h>
#include "savegame.h"
#ifndef TICKET_CONTENT_C3_OLD
#define TICKET_CONTENT_C3_OLD 0
#endif
#ifndef TICKET_PERSIST_C3_OLD
#define TICKET_PERSIST_C3_OLD 0
#endif
enum { TICKET_INTRO=1, TICKET_OWNED=2, TICKET_ADMIT=4 };
typedef struct { uint32_t kind,gag; char pc[32],npc[32],yes[32],intro[32],no[32],movie[16]; } TicketRoute;
typedef struct { char conv[32],actor[8],file[128]; } TicketVoice;
typedef struct { uint8_t flags; unsigned variant; } TicketState;
typedef struct { int movie; const char *dialogue; } TicketDecision;
TicketDecision ticketAction(TicketState *s,const TicketRoute *r,const uint8_t cards[8]);
void ticketSave(const TicketState *s,SaveGame *out);
void ticketRestore(TicketState *s,const SaveGame *in);
#endif
