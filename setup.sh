#!/usr/bin/env bash
# Ставит PSPDEV v20260601 в ./pspdev и нужные утилиты для распаковки PS2-диска.
set -e
cd "$(dirname "$0")"
V=v20260601; B=https://github.com/pspdev/pspdev/releases/download/$V
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  F=pspdev-macos-latest-arm64.tar.gz ;;
  Darwin-x86_64) F=pspdev-macos-15-intel-x86_64.tar.gz ;;
  Linux-x86_64)  F=pspdev-ubuntu-latest-x86_64.tar.gz ;;
  Linux-aarch64) F=pspdev-ubuntu-24.04-arm-arm64.tar.gz ;;
  *) echo "Windows: используй https://github.com/dmang-dev/pspdev-win"; exit 1 ;;
esac
[ -d pspdev ] || { echo "Качаю $F…"; curl -L "$B/$F" | tar xz; }
# №880 (сборка с чистого клона): компилятор PSPDEV для macOS связан с gmp, libmpc, mpfr, zstd, libusb из Homebrew — без них psp-gcc падает
# (dyld: libmpc.3.dylib); ffmpeg нужен с декодером IPU (ролики), пути — $FFMPEG или PATH
if [ "$(uname -s)" = Darwin ]; then brew install cmake sevenzip python@3.11 gmp libmpc mpfr zstd libusb ffmpeg || true
else sudo apt-get install -y cmake 7zip python3-pip python3-venv ffmpeg || true; fi
# своё окружение Python ≥ 3.11 (.venv): его включают build_level.sh, ship.sh, build_all_levels.sh
PY=$(command -v python3.11 || command -v python3.12 || command -v python3.13 || command -v python3)
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "нужен Python 3.11 или новее"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install -r hit-and-run-web/requirements.txt fast_simplification meshoptimizer segno
# donut (GPL-3.0) — рядом: tools/sound_export.py читает donut/dev/codegen/cmd.json
[ -d donut ] || git clone --depth 1 https://github.com/plowteam/donut.git donut || echo "donut не скачался: склонируй его в папку donut"

echo; echo "Готово. Перед работой:  export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:\$PATH; source .venv/bin/activate"
