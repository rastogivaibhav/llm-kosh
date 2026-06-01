import ast

cmd_src = open('ai_cartridge/engine/commands.py', encoding='utf-8').read()

tree = ast.parse(cmd_src)
to_remove = ['query_memory', 'best_match', 'make_snippet', 'top_matches', 'print_query_results', 'read_doc', '_fts_query', 'tokenize', '_build_idf', '_vec', '_cosine', '_doc_text']

remaining_nodes = []

for node in tree.body:
    name = getattr(node, 'name', None)
    if name not in to_remove:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) in to_remove:
            continue
        remaining_nodes.append(node)

out_cmd = []
for node in remaining_nodes:
    out_cmd.append(ast.get_source_segment(cmd_src, node))

# header for commands.py
header = """
from ai_cartridge.core.constants import *
from ai_cartridge.core.utils import *
from ai_cartridge.core.memory import *
from ai_cartridge.engine.search import *
from ai_cartridge.engine.safety import *
from ai_cartridge.engine.compiler import *
"""

with open('ai_cartridge/engine/commands.py', 'w', encoding='utf-8') as f:
    f.write(header + "\n\n".join(out_cmd))

print("Cleaned duplicate search functions from commands.py!")
