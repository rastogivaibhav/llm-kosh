import ast
from pathlib import Path

# Files we already extracted to
extracted_files = [
    "ai_cartridge/core/constants.py",
    "ai_cartridge/core/utils.py",
    "ai_cartridge/core/memory.py",
    "ai_cartridge/engine/search.py",
    "ai_cartridge/engine/safety.py",
    "ai_cartridge/engine/compiler.py",
    "ai_cartridge/engine/healing.py",
    "ai_cartridge/cli.py",
]

extracted_names = set()
for p in extracted_files:
    if not Path(p).exists():
        continue
    src = Path(p).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            extracted_names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            extracted_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    extracted_names.add(t.id)

# Now read legacy
legacy_src = Path("cartridge_legacy.py").read_text(encoding="utf-8")
tree = ast.parse(legacy_src)

remaining_nodes = []
for node in tree.body:
    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
        continue  # skip imports
    
    name = None
    if isinstance(node, ast.FunctionDef):
        name = node.name
    elif isinstance(node, ast.ClassDef):
        name = node.name
    elif isinstance(node, ast.Assign):
        if isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id

    if name == "main":
        continue

    # If this is a top level definition that hasn't been extracted, keep it
    if name and name not in extracted_names:
        remaining_nodes.append(node)
    elif not name:
        # Keep things like module level docstrings or random statements? No.
        pass

# Since python 3.8 we can use ast.get_source_segment
# Since python 3.8 we can use ast.get_source_segment
out_src = ["import os, re, json, uuid, shutil, zipfile, sqlite3, argparse, datetime as dt",
           "from datetime import timezone", "UTC = timezone.utc",
           "from pathlib import Path", "from typing import Dict, List, Optional, Tuple, Set",
           "from ai_cartridge.core.constants import *",
           "from ai_cartridge.core.utils import *",
           "from ai_cartridge.core.memory import *",
           "from ai_cartridge.engine.search import *",
           "from ai_cartridge.engine.safety import *",
           "from ai_cartridge.engine.compiler import *",
           "from ai_cartridge.engine.healing import *"]

for node in remaining_nodes:
    out_src.append(ast.get_source_segment(legacy_src, node))

Path("ai_cartridge/engine/commands.py").write_text("\n\n".join(out_src), encoding="utf-8")
print("Extracted leftover commands to ai_cartridge/engine/commands.py")

# Now write the proxy cartridge.py
proxy_src = ["from ai_cartridge.core.constants import *",
             "from ai_cartridge.core.utils import *",
             "from ai_cartridge.core.memory import *",
             "from ai_cartridge.engine.search import *",
             "from ai_cartridge.engine.safety import *",
             "from ai_cartridge.engine.compiler import *",
             "from ai_cartridge.engine.healing import *",
             "from ai_cartridge.engine.commands import *",
             "from ai_cartridge.cli import main",
             "",
             "if __name__ == '__main__':",
             "    main()"]
Path("cartridge.py").write_text("\n".join(proxy_src), encoding="utf-8")
print("Wrote cartridge.py proxy")
