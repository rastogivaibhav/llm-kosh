import ast

cmd_src = open('ai_cartridge/engine/commands.py', encoding='utf-8').read()
search_src = open('ai_cartridge/engine/search.py', encoding='utf-8').read()

# remove from search.py the import of commands:
# from ai_cartridge.engine.commands import _vmeta, semantic_search, build_vector_index
search_src = search_src.replace('from ai_cartridge.engine.commands import _vmeta, semantic_search, build_vector_index\n', '')

tree = ast.parse(cmd_src)
to_move = ['_get_vmodel', '_vmeta', 'build_vector_index', 'semantic_search']

moved_code = []
remaining_nodes = []

for node in tree.body:
    name = getattr(node, 'name', None)
    if name in to_move:
        moved_code.append(ast.get_source_segment(cmd_src, node))
    else:
        remaining_nodes.append(node)

# append to search_src
search_src += "\n\n" + "\n\n".join(moved_code) + "\n"
with open('ai_cartridge/engine/search.py', 'w', encoding='utf-8') as f:
    f.write(search_src)

# rewrite commands.py
out_cmd = []
for node in remaining_nodes:
    out_cmd.append(ast.get_source_segment(cmd_src, node))

# Also add imports to the top of commands.py:
# commands.py needs rebuild_index, query_memory, etc.
# Actually we can just add them safely now since search doesn't import commands!
header = """
from ai_cartridge.core.constants import *
from ai_cartridge.core.utils import *
from ai_cartridge.core.memory import *
from ai_cartridge.engine.search import *
from ai_cartridge.engine.safety import *
from ai_cartridge.engine.compiler import *
from ai_cartridge.engine.healing import *
"""

# wait, we removed * from healing. let's just restore them and let it work since the cycle is broken!
# Wait, healing imports add_memory from memory. memory imports rebuild_index from search. search imports nothing.
# compiler imports query_memory from search. 
# This means search.py is a leaf! It imports from memory (ensure_root, etc). Wait, memory imports from search.
# We fixed memory.py to import locally!

with open('ai_cartridge/engine/commands.py', 'w', encoding='utf-8') as f:
    f.write(header + "\n\n".join(out_cmd))

print("Moved semantic functions to search.py and fixed imports!")
