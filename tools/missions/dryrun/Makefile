# Mac build of the mission runtime + fake engine.   make -C tools/missions/dryrun && make -C tools/missions/dryrun run
RT      := ../../../viewer/mission
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra -pedantic
SRC     := main.c fake_engine.c $(RT)/msn_file.c $(RT)/msn_run.c $(RT)/msn_ops.c $(RT)/msn_game.c
PACKS   := ../../../build/missions

dryrun: $(SRC) fake_engine.h $(RT)/msn.h $(RT)/msn_game.h $(RT)/msn_format.h $(RT)/msn_ops.h
	$(CC) $(CFLAGS) -I$(RT) -o $@ $(SRC) -lm

run: dryrun
	./dryrun ../../../build/missions.shr --bonus --fail-test --save-test

all-levels: dryrun
	for l in 1 2 3 4 5 6 7; do ./dryrun $(PACKS)/level0$$l.msn --bonus --quiet | tail -8; done

clean:
	rm -f dryrun
