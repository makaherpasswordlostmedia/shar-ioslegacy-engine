#!/bin/sh
# Расписание ночного автоисследователя (launchd, как tools/bots/night_schedule.sh): ua.heartbeat.shar-autoexplore, каждый день в 23:10,
# открывает Ночь-автоисследователь.command Терминалом (launchd не пускает фоновый sh в ~/Downloads). Только от сети (проверяет сам .command).
#   sh tools/autoexplore/sborka/schedule.sh install | remove | status
cd "$(dirname "$0")/../../.." || exit 1
ROOT="$PWD"; UIDN=$(id -u); LA="$HOME/Library/LaunchAgents"; L=ua.heartbeat.shar-autoexplore
case "$1" in
  install)
    cat > "$LA/$L.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$L</string>
<key>ProgramArguments</key><array><string>/usr/bin/open</string><string>-a</string><string>Terminal</string><string>$ROOT/tools/autoexplore/sborka/Ночь-автоисследователь.command</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>10</integer></dict>
<key>StandardOutPath</key><string>$HOME/Library/Logs/shar-autoexplore.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/shar-autoexplore.log</string>
</dict></plist>
P
    launchctl bootout "gui/$UIDN/$L" 2>/dev/null; launchctl bootstrap "gui/$UIDN" "$LA/$L.plist"; launchctl list | grep shar-autoexplore ;;
  remove) launchctl bootout "gui/$UIDN/$L" 2>/dev/null; rm -f "$LA/$L.plist"; echo "выключено" ;;
  status) launchctl list | grep shar-autoexplore || echo "не установлено" ;;
  *) echo "sh $0 install|remove|status"; exit 2 ;;
esac
