// Ввод в эмулятор PS2 (эталон, пункт 4в): нажать клавиши и держать, как пальцем.
//   key <pid> <клавиша>[+<клавиша>...] <секунды> [<клавиша>... <секунды>] ...
// Клавиши (от раскладки не зависят): x=крест(5) circle(6) square(7) tri(Home) l1(9) r1(0) l2(1) r2(3) start(End) bs=Select\n//   up down left right = левый стик, dup ddown = крестовина, del сохранить состояние, help загрузить (F1/F3 с Mac не доходят), esc меню
// Окно процесса <pid> выводится вперёд (ввод PCSX2 берёт из окна в фокусе)
import Cocoa
let codes: [String: CGKeyCode] = ["x": 23, "circle": 22, "square": 26, "tri": 115, "l1": 25, "r1": 29, "l2": 18, "r2": 20,
  "start": 119, "ret": 36, "bs": 51, "up": 126, "down": 125, "left": 123, "right": 124, "dup": 116, "ddown": 121, "del": 117, "help": 114,
  "f1": 122, "f2": 120, "f3": 99, "esc": 53, "space": 49]
let a = CommandLine.arguments
guard a.count >= 4, let pid = pid_t(a[1]) else { print("usage: key <pid> keys secs ..."); exit(2) }
if let app = NSRunningApplication(processIdentifier: pid) { app.activate(options: [.activateIgnoringOtherApps]) }
usleep(250_000)
// фокус в окно картинки: клик мышью по центру самого большого окна процесса (ввод PCSX2 идёт только оттуда)
func focusGameWindow() {
  let l = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
  var best: CGRect? = nil
  for w in l {
    guard let p = w["kCGWindowOwnerPID"] as? Int, p == Int(pid), let b = w["kCGWindowBounds"] as? [String: Any],
          let r = CGRect(dictionaryRepresentation: b as CFDictionary) else { continue }
    if best == nil || r.width * r.height > best!.width * best!.height { best = r }
  }
  guard let r = best else { return }
  let c = CGPoint(x: r.midX, y: r.midY)
  CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: c, mouseButton: .left)?.post(tap: .cghidEventTap)
  usleep(50_000)
  CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: c, mouseButton: .left)?.post(tap: .cghidEventTap)
  usleep(50_000)
  CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: c, mouseButton: .left)?.post(tap: .cghidEventTap)
  usleep(150_000)
}
if ProcessInfo.processInfo.environment["PS2_CLICK"] != "0" { focusGameWindow() }
var i = 2
while i + 1 < a.count {
  let keys = a[i].split(separator: "+").map(String.init), secs = Double(a[i + 1]) ?? 0.1
  let ks = keys.compactMap { codes[$0] }
  if ks.count != keys.count { print("unknown key in \(a[i])"); exit(2) }
  for k in ks { CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: true)?.post(tap: .cghidEventTap) }
  usleep(useconds_t(secs * 1_000_000))
  for k in ks.reversed() { CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: false)?.post(tap: .cghidEventTap) }
  usleep(60_000)
  i += 2
}
