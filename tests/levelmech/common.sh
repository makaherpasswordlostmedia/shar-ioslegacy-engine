# Общее для гейтов tests/levelmech/*.sh: пути, сборка хост-проверки, «красный/зелёный». Подключается через `. common.sh`.
cd "$(dirname "$0")/../.." || exit 2
MAIN=${SHAR_MAIN:-$HOME/Downloads/shar-psp}          # основная копия: данные уровней только читаем
PY=${PY:-$MAIN/.venv/bin/python}
HOMER=${HOMER:-$MAIN/build/homer.shr}
LV() { # путь к файлу уровня N: сначала эта копия build/levels/lN/, иначе основная (только чтение)
  if [ -f "build/levels/l$1/$2" ]; then echo "build/levels/l$1/$2"; else echo "$MAIN/build/levels/l$1/$2"; fi
}
export BW_NO_TRAFFIC=1 BW_NO_ROOMS=1 BW_NO_AUDIO=1
FAILS=0
red() {   # red "описание" команда... — команда обязана дать код != 0
  local what="$1"; shift
  if "$@" > "$LOGD/red_$(echo "$what" | tr -c 'a-zA-Z0-9_' '_').log" 2>&1; then echo "RED НЕ ПОЙМАН: $what"; FAILS=$((FAILS + 1)); else echo "RED OK: $what"; fi
}
green() { # green "описание" команда... — команда обязана дать код 0
  local what="$1"; shift
  if "$@" > "$LOGD/green_$(echo "$what" | tr -c 'a-zA-Z0-9_' '_').log" 2>&1; then echo "GREEN OK: $what"; else echo "GREEN FAIL: $what"; FAILS=$((FAILS + 1)); fi
}
LOGD=build/gates/levelmech/$(date '+%Y%m%d-%H%M%S')-$(basename "$0" .sh); mkdir -p "$LOGD"
build_host() {
  bash tests/levelmech/build_host.sh > /dev/null || { echo "сборка lvmech не удалась"; exit 2; }
}
