"""Executed in a fresh interpreter before starting the media subprocess."""

import os
import resource
import shutil
import sys

timeout = int(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU, (timeout + 5, timeout + 10))
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
if sys.platform == "linux":
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
executable = shutil.which(sys.argv[2]) or sys.argv[2]
os.execv(executable, [executable, *sys.argv[3:]])
