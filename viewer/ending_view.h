#ifndef ENDING_VIEW_H
#define ENDING_VIEW_H
// Synchronous original post-FMV credits. Callbacks retain main's GE state, swap and smoke lifecycle
int endingRun(const char *file, void *geList, void (*reset)(void), void *(*swap)(void),
              unsigned (*frame)(float, int), void (*log)(const char *), void **fbp);
#endif
