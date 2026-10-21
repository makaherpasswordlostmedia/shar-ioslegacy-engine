#pragma once
// PSP joint 24 voices +128 elements: worst8.537ms; +400:25/32 late,12.515ms
// Count particles, billboards and sprites. Over budget runs the SAME full job on CPU
#ifndef ME_FX_MAX_ELEMENTS
#define ME_FX_MAX_ELEMENTS 128
#endif
// ME-доля (вариант B, 10.10): задание частиц на ME режется по размеру, чтобы не держать очередь ME дольше звука. Предел задаётся флаг-файлом mefxmax
// рядом с EBOOT (число элементов 8..400; по умолчанию 128, как было); меньше предел — больше заданий остаётся на главном процессоре
static int meFxMax = ME_FX_MAX_ELEMENTS;
static inline void meFxSetMax(int n){ if(n>=8&&n<=400)meFxMax=n; }
static inline int meFxWithinBudget(int particles,int billboards,int sprites){
  if(particles<0||billboards<0||sprites<0||particles>meFxMax||billboards>meFxMax||sprites>meFxMax)return 0;
  return particles+billboards+sprites<=meFxMax;
}
