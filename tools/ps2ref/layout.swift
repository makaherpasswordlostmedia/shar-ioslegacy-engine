// раскладка на время управления PCSX2: layout get | layout set <id>   (например com.apple.keylayout.ABC)
import Carbon
let a = CommandLine.arguments
if a.count >= 2 && a[1] == "get" {
  let s = TISCopyCurrentKeyboardInputSource().takeRetainedValue()
  print(Unmanaged<CFString>.fromOpaque(TISGetInputSourceProperty(s, kTISPropertyInputSourceID)!).takeUnretainedValue() as String)
} else if a.count >= 3 && a[1] == "set" {
  let f = [kTISPropertyInputSourceID as String: a[2]] as CFDictionary
  guard let l = TISCreateInputSourceList(f, true)?.takeRetainedValue() as? [TISInputSource], let s = l.first else { print("нет раскладки \(a[2])"); exit(1) }
  TISEnableInputSource(s); let r = TISSelectInputSource(s); print(r == noErr ? "ok" : "ошибка \(r)")
}
