import os
import sys
from pathlib import Path

HAS_CPP_CORE = False

try:
    from llm_kosh.engine import math_core
    HAS_CPP_CORE = True
except ImportError:
    # On Windows, MinGW compiled binaries require runtime DLLs in the search path
    if sys.platform == "win32":
        mingw_bin = Path(r"C:\Users\vrast\AppData\Local\Microsoft\WinGet\Packages\MartinStorsjo.LLVM-MinGW.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\llvm-mingw-20260602-ucrt-x86_64\bin")
        if mingw_bin.exists():
            try:
                cookie = os.add_dll_directory(str(mingw_bin))
                from llm_kosh.engine import math_core
                HAS_CPP_CORE = True
            except Exception:
                pass

if not HAS_CPP_CORE:
    from llm_kosh.engine import math_fallback as math_core
