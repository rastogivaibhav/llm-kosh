import os
import re
from pathlib import Path

def apply_replacements(content, is_python_file):
    # KOUSH -> LLM_KOSH
    content = content.replace("KOUSH", "LLM_KOSH")
    
    # Koush -> LlmKosh
    content = content.replace("Koush", "LlmKosh")
    
    # koush.spec -> llm-kosh.spec
    content = content.replace("koush.spec", "llm-kosh.spec")
    
    # koush_cli -> llm_kosh_cli
    content = content.replace("koush_cli", "llm_kosh_cli")
    
    # Python files need special care for imports and variables
    if is_python_file:
        # replace import/module references and snake_case
        content = re.sub(r'\bkoush\b(?!-)', 'llm_kosh', content)
        # However, the CLI command in strings might be "koush"
        # sys.argv = ["koush", ...] -> ["llm-kosh", ...]
        content = content.replace('"llm_kosh"', '"llm-kosh"')
        content = content.replace("'llm_kosh'", "'llm-kosh'")
    else:
        # For non-python files (markdown, html, scripts)
        # koush_ -> llm_kosh_
        content = content.replace("koush_", "llm_kosh_")
        # word 'koush' -> 'llm-kosh'
        content = re.sub(r'\bkoush\b', 'llm-kosh', content)
        
    # fix any double replacement
    content = content.replace("llm-kosh.json", "LLM_KOSH.json")
    content = content.replace("llm_kosh.json", "LLM_KOSH.json")

    return content

def process_directory(root_dir):
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'htmlcov'}
    skip_exts = {'.png', '.jpg', '.zip', '.pyc', '.pyd'}

    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to skip hidden/build directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            # Skip this script
            if file == 'rename_script.py':
                continue
            
            ext = os.path.splitext(file)[1]
            if ext in skip_exts:
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except UnicodeDecodeError:
                # Binary file or different encoding, skip
                continue

            is_python_file = filepath.endswith('.py')
            new_content = apply_replacements(original_content, is_python_file)

            if new_content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")

if __name__ == "__main__":
    process_directory(".")
