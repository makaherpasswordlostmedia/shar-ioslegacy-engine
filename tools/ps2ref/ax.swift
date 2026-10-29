// Доступность macOS строго по PID (два процесса PCSX2 с одним именем; System Events адресует по имени и может попасть в личный).
//   ax <pid> tree                          — окна и элементы: роль | заголовок | значение
//   ax <pid> press <окно> <заголовок>       — нажать кнопку/радио/пункт с этим заголовком внутри окна
//   ax <pid> set <окно> <номер поля> <текст> — значение N-го текстового поля окна (с 1)
//   ax <pid> menu <пункт> <подпункт>...     — пункт главного меню этого процесса
// Окно ищется по подстроке заголовка. Фокус не переключается; для меню процесс должен быть впереди
import Cocoa
let a = CommandLine.arguments
guard a.count >= 3, let pid = pid_t(a[1]) else { print("usage: ax <pid> tree|press|set|menu ..."); exit(2) }
let app = AXUIElementCreateApplication(pid)
func attr(_ e: AXUIElement, _ n: String) -> AnyObject? { var v: AnyObject?; AXUIElementCopyAttributeValue(e, n as CFString, &v); return v }
func str(_ e: AXUIElement, _ n: String) -> String { (attr(e, n) as? String) ?? "" }
func kids(_ e: AXUIElement) -> [AXUIElement] { (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func title(_ e: AXUIElement) -> String { let t = str(e, kAXTitleAttribute); return t.isEmpty ? str(e, kAXDescriptionAttribute) : t }
func walk(_ e: AXUIElement, _ f: (AXUIElement, Int) -> Void, _ d: Int = 0) { f(e, d); for k in kids(e) { walk(k, f, d + 1) } }
func window(_ q: String) -> AXUIElement {
  let ws = (attr(app, kAXWindowsAttribute) as? [AXUIElement]) ?? []
  guard let w = ws.first(where: { str($0, kAXTitleAttribute).contains(q) }) else {
    print("FAIL: нет окна «\(q)» у pid \(pid); есть: \(ws.map { str($0, kAXTitleAttribute) })"); exit(1) }
  return w
}
switch a[2] {
case "tree":
  for w in (attr(app, kAXWindowsAttribute) as? [AXUIElement]) ?? [] {
    walk(w) { e, d in
      let v = attr(e, kAXValueAttribute).map { "\($0)" } ?? ""
      print(String(repeating: "  ", count: d) + str(e, kAXRoleAttribute) + " | " + title(e) + " | " + v)
    }
  }
case "press":
  var hit: AXUIElement?
  walk(window(a[3])) { e, _ in if hit == nil && title(e) == a[4] { hit = e } }
  guard let e = hit else { print("FAIL: нет элемента «\(a[4])»"); exit(1) }
  let r = AXUIElementPerformAction(e, kAXPressAction as CFString); print(r == .success ? "OK press \(a[4])" : "FAIL press \(r.rawValue)")
  exit(r == .success ? 0 : 1)
case "set":
  var fields: [AXUIElement] = []
  walk(window(a[3])) { e, _ in if str(e, kAXRoleAttribute) == kAXTextFieldRole { fields.append(e) } }
  guard let n = Int(a[4]), n >= 1, n <= fields.count else { print("FAIL: полей \(fields.count)"); exit(1) }
  let r = AXUIElementSetAttributeValue(fields[n - 1], kAXValueAttribute as CFString, a[5] as CFString)
  let now = str(fields[n - 1], kAXValueAttribute); print(now == a[5] ? "OK set \(n) = \(now)" : "FAIL set \(r.rawValue) now «\(now)»")
  exit(now == a[5] ? 0 : 1)
case "menu":
  guard var cur = attr(app, kAXMenuBarAttribute) as! AXUIElement? else { print("FAIL: нет меню"); exit(1) }
  for name in a[3...] {
    var hit: AXUIElement?
    walk(cur) { e, _ in if hit == nil && title(e) == name && str(e, kAXRoleAttribute).hasPrefix("AXMenu") && str(e, kAXRoleAttribute) != "AXMenu" { hit = e } }
    guard let e = hit else { print("FAIL: нет пункта «\(name)»"); exit(1) }
    if name == a.last! { let r = AXUIElementPerformAction(e, kAXPressAction as CFString); print(r == .success ? "OK menu \(name)" : "FAIL menu \(r.rawValue)"); exit(r == .success ? 0 : 1) }
    cur = e
  }
default: print("usage"); exit(2)
}
