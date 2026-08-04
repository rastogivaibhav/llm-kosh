from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Memory:
    title: str
    body: str
    kind: str = "file"
    extra_meta: Dict[str, Any] = field(default_factory=dict)

def convert_to_memory(file_path: Path) -> Memory:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ImportError(
            "The 'markitdown' library is not installed. "
            "Please install it using: pip install llm-kosh[ingest]"
        ) from exc

    body = MarkItDown().convert(str(file_path)).text_content
    title = file_path.stem
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return Memory(
        title=title,
        body=body,
        extra_meta={"source_origin": str(file_path.resolve()), "converter": "markitdown"},
    )
