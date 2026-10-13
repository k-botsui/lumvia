"""Executed in a fresh interpreter before starting the media subprocess."""

import os
import resource
import shutil
import sys

timeout = int(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU, (timeout + 5, timeout + 10))
output_limit = min(40 * 1024**3, max(1024**2, int(os.environ.get("LUMVIA_PROCESS_MAX_BYTES", 1024**3))))
resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
if sys.platform == "linux":
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
executable = shutil.which(sys.argv[2]) or sys.argv[2]
os.execv(executable, [executable, *sys.argv[3:]])
