import re
from pathlib import Path

src = Path("cartridge.py").read_text(encoding="utf-8")

# Extract the CLI portion
cli_match = re.search(r"(def main\(\) -> None:.*)", src, re.DOTALL)
if not cli_match:
    print("Could not find main()")
    exit(1)

cli_body = cli_match.group(1)

# Write cli.py
imports = """import argparse
import os
from pathlib import Path

from ai_cartridge.core.constants import APP_VERSION, KINDS, VISIBILITIES, DEFAULT_ROOT_NAME, PACK_PROFILES
from ai_cartridge.core.memory import add_memory, ensure_root
from ai_cartridge.engine.search import query_memory, semantic_search, print_query_results, rebuild_index, build_vector_index
from ai_cartridge.engine.compiler import pack_context, validate_pack, explain_pack
from ai_cartridge.engine.healing import absorb_receipt, resolve

# We will import the rest from cartridge for now until fully extracted, 
# or assume they are in commands.py
import cartridge

"""

Path("ai_cartridge/cli.py").write_text(imports + cli_body, encoding="utf-8")
print("Wrote cli.py")
