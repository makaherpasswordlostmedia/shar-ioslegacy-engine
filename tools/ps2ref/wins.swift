// Окна процесса без доступа к окнам (только чтение CGWindowList): wins PID → строки «onscreen слой x y w h альфа».
// Для гейта О1: наблюдатель не выводит окно на экран и не становится активным (активность — lsappinfo front).
import CoreGraphics
import Foundation
guard CommandLine.arguments.count >= 2, let pid = Int(CommandLine.arguments[1]) else { print("usage: wins PID"); exit(2) }
let list = (CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]]) ?? []
for w in list where (w[kCGWindowOwnerPID as String] as? Int) == pid {
  let b = (w[kCGWindowBounds as String] as? [String: Any]) ?? [:]
  let on = (w[kCGWindowIsOnscreen as String] as? Bool) ?? false
  let layer = (w[kCGWindowLayer as String] as? Int) ?? 0
  let alpha = (w[kCGWindowAlpha as String] as? Double) ?? 0
  print("\(on ? 1 : 0) \(layer) \(b["X"] ?? 0) \(b["Y"] ?? 0) \(b["Width"] ?? 0) \(b["Height"] ?? 0) \(alpha)")
}
