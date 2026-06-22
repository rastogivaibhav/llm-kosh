HAS_CPP_CORE = False

try:
    from llm_kosh.engine import math_core
    HAS_CPP_CORE = True
except ImportError:
    pass

if not HAS_CPP_CORE:
    from llm_kosh.engine import math_fallback as math_core
