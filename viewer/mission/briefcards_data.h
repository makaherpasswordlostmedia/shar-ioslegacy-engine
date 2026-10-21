/* Original-disc facts: SLES_518.97 0x19e378..0x19e770.
   Regenerate/check from tools/briefcards_source.py; this contains data names, not original source. */
#ifndef MSN_BRIEFCARDS_DATA_H
#define MSN_BRIEFCARDS_DATA_H
static const char *msnBriefBuiltin(const char *npc) {
 static const struct { const char *npc,*path; } pairs[] = {
  {"nelson", "art/frontend/dynaload/images/misxx_ct.p3d"},
  {"milhouse", "art/frontend/dynaload/images/misxx_tt.p3d"},
  {"ralph", "art/frontend/dynaload/images/misxx_cp.p3d"},
  {"louie", "art/frontend/dynaload/images/misxx_gb.p3d"},
  {"witch", "art/frontend/dynaload/images/misxx_hw.p3d"},
  {"zfem1", "art/frontend/dynaload/images/misxx_hw.p3d"},
  {"zmale1", "art/frontend/dynaload/images/misxx_hw.p3d"},
  {"zmale3", "art/frontend/dynaload/images/misxx_hw.p3d"},
  {"cletus", "art/frontend/dynaload/images/mis01_08.p3d"},
  {"grandpa", "art/frontend/dynaload/images/mis02_08.p3d"},
  {"skinner", "art/frontend/dynaload/images/mis03_08.p3d"},
  {"cbg", "art/frontend/dynaload/images/mis04_08.p3d"},
  {"frink", "art/frontend/dynaload/images/mis05_08.p3d"},
  {"snake", "art/frontend/dynaload/images/mis06_08.p3d"},
  {"smithers", "art/frontend/dynaload/images/mis07_08.p3d"},
 };
 if(!npc)return 0;
 if(npc[0]=='b'&&npc[1]=='_')npc+=2;
 for(unsigned i=0;i<sizeof pairs/sizeof pairs[0];i++) if(msn_streq(npc,pairs[i].npc))return pairs[i].path;
 return 0;
}
#endif
