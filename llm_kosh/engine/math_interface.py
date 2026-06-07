try:
    from llm_kosh.engine import math_core
    HAS_CPP_CORE = True
except ImportError:
    from llm_kosh.engine import math_fallback as math_core
    HAS_CPP_CORE = False
