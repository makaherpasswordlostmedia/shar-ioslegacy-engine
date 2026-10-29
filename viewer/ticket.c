#include <string.h>
#include "ticket.h"
/* SLES 15649c visits 0..6; 145218 returns count==7. Success sets is_ticket
   (global bit1) and L3 FMV-unlocked byte before starting rewardsuccess. */
TicketDecision ticketAction(TicketState *s,const TicketRoute *r,const uint8_t cards[8]) {
 TicketDecision d={0,0};if(!r||TICKET_CONTENT_C3_OLD)return d;
 if(r->kind==1){
  if(s->flags&TICKET_OWNED)return d;
  int all=1;for(int lv=1;lv<=7;lv++)if((cards[lv]&127)!=127)all=0;
  if(all){s->flags|=TICKET_OWNED|TICKET_ADMIT;d.dialogue=r->yes;}
  else if(s->flags&TICKET_INTRO)d.dialogue=r->no;
  else{s->flags|=TICKET_INTRO;d.dialogue=r->intro;}
 }else if(r->kind==2){if(s->flags&TICKET_ADMIT)d.movie=1;else d.dialogue=r->no;}
 return d;
}
void ticketSave(const TicketState *s,SaveGame *out){if(!TICKET_PERSIST_C3_OLD)out->ext[SV_EXT_TICKET]=(uint8_t)(SV_EXT_TICKET_SET|(s->flags&7));}
void ticketRestore(TicketState *s,const SaveGame *in){s->flags=!TICKET_PERSIST_C3_OLD&&(in->ext[SV_EXT_TICKET]&SV_EXT_TICKET_SET)?in->ext[SV_EXT_TICKET]&7:0;s->variant=0;}
