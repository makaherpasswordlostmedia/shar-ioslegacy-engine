#!/usr/bin/env python3
"""Read the actual main assembly for source contracts; all other files pass through."""
import re,sys
from pathlib import Path

def read_main(path, *, errors='strict'):
 path=Path(path);text=path.read_text(errors=errors)
 # Both routes exist for proving exact SDK code. Source consumers use shipping modules.
 if '#if MAIN_MODULES_OLD' in text:
  text=text.split('#else\n',1)[1].rsplit('#endif',1)[0]
 def expand(m):
  part=path.parent/m.group(1)
  if not part.is_file():raise FileNotFoundError(part)
  return read_main(part,errors=errors)
 return re.sub(r'^#include "(main_[A-Za-z0-9_]+\.h)"\n',expand,text,flags=re.M)

if __name__=='__main__':sys.stdout.write(read_main(sys.argv[1]))
