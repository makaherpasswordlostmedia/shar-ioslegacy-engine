# Standalone PSP test EBOOT for the mission runtime (does not touch the main engine).
#   export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH
#   psp-cmake -S tools/missions/psptest -B <builddir> && cmake --build <builddir>
#   cp <builddir>/EBOOT.PBP build/missions/     (next to level01.msn .. level07.msn)
cmake_minimum_required(VERSION 3.10)
project(sharmsn C)
set(RT ${CMAKE_CURRENT_SOURCE_DIR}/../../../viewer/mission)
set(FK ${CMAKE_CURRENT_SOURCE_DIR}/../dryrun)
add_executable(sharmsn main.c ${FK}/fake_engine.c ${RT}/msn_file.c ${RT}/msn_run.c ${RT}/msn_ops.c ${RT}/msn_game.c)
target_include_directories(sharmsn PRIVATE ${RT} ${FK})
target_compile_options(sharmsn PRIVATE -O2 -std=gnu99 -Wall -fno-math-errno -fsingle-precision-constant)
target_link_libraries(sharmsn pspdebug pspdisplay pspctrl psprtc pspge m)
create_pbp_file(TARGET sharmsn TITLE "SHAR mission runtime test" BUILD_PRX)
