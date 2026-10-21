import CoreGraphics
// окно (id) процесса с заданным PID, высотой больше 100 px; сначала среди видимых, иначе среди всех
// (окно на другом рабочем столе или под полноэкранным приложением — screencapture -l снимает и его)
let pid = Int(CommandLine.arguments[1]) ?? -1
func find(_ o: CGWindowListOption) -> [Int] {
  let l = CGWindowListCopyWindowInfo(o, kCGNullWindowID) as? [[String: Any]] ?? []
  return l.compactMap { w in
    guard let p = w["kCGWindowOwnerPID"] as? Int, p == pid, let n = w["kCGWindowNumber"] as? Int,
          let b = w["kCGWindowBounds"] as? [String: Any], (b["Height"] as? Double ?? 0) > 100,
          (w["kCGWindowLayer"] as? Int ?? 0) == 0 else { return nil }
    return n
  }
}
var ids = find([.optionOnScreenOnly]); if ids.isEmpty { ids = find([.optionAll]) }
for n in ids { print(n) }
