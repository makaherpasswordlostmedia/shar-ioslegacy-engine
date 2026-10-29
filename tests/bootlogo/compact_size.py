#!/usr/bin/env python3
import sys
from pathlib import Path

new, old = map(lambda x: Path(x).stat().st_size, sys.argv[1:3])
ratio = new / old
ok = new <= 7000 and ratio <= .55
print(f"{'PASS' if ok else 'FAIL'} bootmarks compact bytes={new}/{old} ratio={ratio:.3f} (limits 7000 and 0.55)")
raise SystemExit(0 if ok else 1)
