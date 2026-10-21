#!/bin/bash
# Правка 410 (09.10, docs/handoff/ME_ПЛАН_2026-10-09.md): тур всех уровней на PSP — звук на главном против звука на ME с новым дешёвым
# сбросом (К1) и против прежнего сброса целиком. Одна сборка EBOOT, одна дорога (tests/me/psp_tour_all_levels.txt), отличаются только
# флаг-файлы. Частицы во всех трёх — на главном процессоре (mefx не кладётся: по T3 частицы на ME дают минус, Роб слышал треск).
#   SHARTEST4 «SHAR TEST4 CPU»     — без ME (как T1)
#   SHARTEST5 «SHAR TEST5 ME K1»   — meaudio=u, сброс по частям (новое)
#   SHARTEST6 «SHAR TEST6 ME OLD»  — meaudio=u + mewbold, сброс целиком (как T2)
# Что смотреть в ОТЧЁТ.md каждой апки (tools/tour_report.py): «Звук: опоздания» — опоздавших буферов 0 (это и есть треск), разбивка отдачи
# на ME (сброс кэша / meSvcSubmit / ожидание / mixPre / mixPost, строк кэша); доля audio_mix в таблице процессора; в smoke.txt — MEPROF mixbuf_us.
#   tools/tour_me_k1.sh --deploy   положить три апки на PSP (PSP по USB)
#   tools/tour_me_k1.sh --fetch    забрать три отчёта в build/psp-tour/
# Выкладывает только по слову Роба (тур ~15 мин на апку)
set -u
cd "$(dirname "$0")/.."
case "${1:-}" in
  --deploy)
    TOUR_DIR=SHARTEST4 TOUR_TITLE="SHAR TEST4 CPU" tools/tour_psp.sh --deploy --all-levels || exit 1
    TOUR_DIR=SHARTEST5 TOUR_TITLE="SHAR TEST5 ME K1" TOUR_MEAUDIO=u tools/tour_psp.sh --deploy --all-levels || exit 1
    TOUR_DIR=SHARTEST6 TOUR_TITLE="SHAR TEST6 ME OLD" TOUR_MEAUDIO=u TOUR_MEWBOLD=1 tools/tour_psp.sh --deploy --all-levels || exit 1 ;;
  --fetch)
    for d in SHARTEST4 SHARTEST5 SHARTEST6; do TOUR_DIR=$d tools/tour_psp.sh --fetch; done ;;
  *) echo "tools/tour_me_k1.sh --deploy | --fetch"; exit 2 ;;
esac
