#include <stdio.h>
#include "ui_radial.h"
int main(void) {
  const int values[]={0,30,60,125,250,500,750,1000};
  for(unsigned k=0;k<sizeof values/sizeof values[0];k++) {
    UiRadialPoint p[UI_RADIAL_MAX];int n=uiRadialFan(values[k],p);
    printf("%d %d",values[k],n);
    for(int i=0;i<n;i++)printf(" %.8f %.8f",p[i].u,p[i].v);
    puts("");
  }
}
