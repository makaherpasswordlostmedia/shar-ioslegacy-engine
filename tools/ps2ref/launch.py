#!/usr/bin/env python3
"""Launch only observer1 portable profile; optional state under build/ps2ref."""
import sys
from profile import launch
launch(1, sys.argv[1] if len(sys.argv) > 1 else None)
