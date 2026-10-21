-- диалог выбора файла PCSX2 (доступность macOS, без клавиатуры): начать с папки боковой панели UP ("-" — с текущей),
-- потом по очереди выбрать строку с именем и нажать Open (папка -> войти, файл -> открыть)
on run argv
  set pid to (item 1 of argv) as integer
  set upTo to item 2 of argv
  tell application "System Events" to tell (first process whose unix id is pid)
    set ok to false
    repeat 40 times
      try
        set w to window 1
        set g to splitter group 1 of w
        set pb to (first UI element of g whose role is "AXPopUpButton")
        set ok to true
        exit repeat
      end try
      delay 0.25
    end repeat
    if not ok then return "нет диалога"
    if upTo is not "-" then   -- боковая панель диалога (Избранное): строка с этим именем (список «Where:» живёт в чужом процессе)
      set sb to outline 1 of scroll area 1 of g
      set hit to false
      repeat with r in rows of sb
        try
          if name of UI element 1 of r is upTo then
            set selected of r to true
            set hit to true
            exit repeat
          end if
        end try
      end repeat
      if not hit then return "нет в боковой панели " & upTo
      delay 1.0
    end if
    repeat with k from 3 to count of argv
      set nm to item k of argv
      set found to false
      repeat 30 times
        try
          set g to splitter group 1 of window 1
          set sg to splitter group 1 of g
          set o to outline 1 of scroll area 1 of sg
          -- по одной строке сверху (массовый запрос к удалённой панели виснет); свежие файлы и папки наверху
          repeat with i from 1 to count rows of o
            try
              if (value of text field 1 of UI element 1 of row i of o) is nm then
                set selected of row i of o to true
                set found to true
                exit repeat
              end if
            end try
          end repeat
        end try
        if found then exit repeat
        delay 0.3
      end repeat
      if not found then return "нет строки " & nm
      delay 0.3
      click button "Open" of splitter group 1 of window 1
      delay 0.8
    end repeat
    return "ок"
  end tell
end run
