import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

@dataclass
class Memory:
    title: str
    body: str
    kind: str = "file"
    extra_meta: Dict[str, Any] = field(default_factory=dict)

class BaseIntakeConverter(ABC):
    @abstractmethod
    def convert_to_memory(self, file_path: Path) -> Memory:
        pass

class MarkItDownAdapter(BaseIntakeConverter):
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir
        try:
            from markitdown import MarkItDown
        except ImportError:
            raise ImportError(
                "The 'markitdown' library is not installed. "
                "Please install it using: pip install llm-kosh[ingest]"
            )
        
        # Determine if we should set up an LLM client for MarkItDown (OCR, captioning, etc.)
        llm_client = None
        llm_model = None
        
        # 1. Check LLM_KOSH.json in root_dir if provided
        if self.root_dir:
            from llm_kosh.core.utils import read_json
            config_path = self.root_dir / "LLM_KOSH.json"
            if config_path.exists():
                try:
                    config = read_json(config_path)
                    llm_config = config.get("llm", {})
                    if llm_config and llm_config.get("provider") == "openai":
                        from openai import OpenAI
                        api_key = llm_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
                        base_url = llm_config.get("base_url")
                        llm_client = OpenAI(api_key=api_key, base_url=base_url)
                        llm_model = llm_config.get("model", "gpt-4o")
                except Exception:
                    # Fail silently on config parsing issues
                    pass
        
        # 2. Fallback: Check environment variables for OpenAI
        if not llm_client and os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                llm_client = OpenAI()
                llm_model = "gpt-4o"
            except ImportError:
                pass
                
        if llm_client:
            self.converter = MarkItDown(llm_client=llm_client, llm_model=llm_model)
        else:
            self.converter = MarkItDown()
            
    def convert_to_memory(self, file_path: Path) -> Memory:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        try:
            result = self.converter.convert(str(file_path))
            body = result.text_content
        except Exception as e:
            # Let exceptions propagate upward as requested by Part 5 (Future-Proofing)
            raise e

        # Extract title from first top-level header or fall back to file name stem
        title = file_path.stem
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break
                
        # Generate clean title and metadata
        extra_meta = {
            "source_origin": str(file_path.resolve()),
            "converter": "markitdown"
        }
        
        return Memory(
            title=title,
            body=body,
            kind="file",
            extra_meta=extra_meta
        )
